"""Integration tests for the safety layer (Phase 9).

These tests drive the full guarded pipeline — privilege elevation, managed
execution (timeout/cancel) and recovery points — against the real adapters
with the OS commands stubbed out.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.backend import guards, recovery
from src.backend.apt import AptAdapter
from src.backend.operations import Operation, run_operation


# ---------------------------------------------------------------------------
# Fake subprocess used by the managed runner tests
# ---------------------------------------------------------------------------

class FakePopen:
    instances = []

    def __init__(self, command, **kwargs):
        self.command = command
        self.kwargs = kwargs
        self.returncode = None
        self.killed = False
        self.terminated = False
        FakePopen.instances.append(self)

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True

    def wait(self):
        if self.returncode is None:
            self.returncode = -9
        return self.returncode

    def communicate(self):
        return "", ""


class TestPrivilegeElevation:
    @patch("platform.system", return_value="Linux")
    def test_linux_wraps_with_pkexec_when_not_elevated(self, mock_system):
        with patch("src.backend.privileges.is_elevated", return_value=False), \
             patch("src.backend.privileges.command_available", return_value=True):
            from src.backend import privileges

            command = privileges.elevation_prefix(["apt", "clean"])

            assert command == ["pkexec", "apt", "clean"]

    @patch("platform.system", return_value="Linux")
    def test_linux_keeps_command_when_already_elevated(self, mock_system):
        with patch("src.backend.privileges.is_elevated", return_value=True):
            from src.backend import privileges

            command = privileges.elevation_prefix(["apt", "clean"])

            assert command == ["apt", "clean"]

    @patch("platform.system", return_value="Windows")
    def test_windows_wraps_with_runas_powershell(self, mock_system):
        with patch("src.backend.privileges.is_elevated", return_value=False):
            from src.backend import privileges

            command = privileges.elevation_prefix(["winget", "uninstall", "x"])

            assert command[0] == "powershell"
            assert "-Verb RunAs" in command[-1]
            assert "Start-Process" in command[-1]

    @patch("platform.system", return_value="Linux")
    def test_request_elevation_is_noop_when_elevated(self, mock_system):
        with patch("src.backend.privileges.is_elevated", return_value=True), \
             patch("subprocess.run") as mock_run:
            from src.backend import privileges

            assert privileges.request_elevation() is True
            mock_run.assert_not_called()


class TestManagedOperations:
    def test_operation_aborts_and_kills_running_process(self):
        FakePopen.instances = []
        with patch("subprocess.Popen", FakePopen):
            operation = Operation("clean")
            operation.cancel()

            result = run_operation(["apt", "clean"], operation=operation)

        assert result.aborted is True
        assert result.success is False
        assert FakePopen.instances
        assert FakePopen.instances[0].killed is True

    def test_operation_times_out_when_process_never_exits(self):
        FakePopen.instances = []
        with patch("subprocess.Popen", FakePopen):
            result = run_operation(
                ["apt", "clean"],
                operation=Operation("clean"),
                timeout=0.05,
                poll_interval=0.01,
            )

        assert result.timed_out is True
        assert result.aborted is False
        assert "timed out" in result.message
        assert FakePopen.instances[0].killed is True

    def test_operation_success(self):
        FakePopen.instances = []
        proc = FakePopen(["apt", "clean"])
        proc.returncode = 0

        with patch("subprocess.Popen", return_value=proc):
            result = run_operation(["apt", "clean"])

        assert result.success is True
        assert result.aborted is False


# ---------------------------------------------------------------------------
# Recovery point integration
# ---------------------------------------------------------------------------

class TestRecoveryPoints:
    @patch("platform.system", return_value="Linux")
    def test_detects_timeshift_when_available(self, mock_system):
        with patch("src.backend.privileges.command_available", return_value=True):
            status = recovery.recovery_tool_status()

        assert status["available"] is True
        assert status["tool"] == "Timeshift"

    @patch("platform.system", return_value="Linux")
    def test_marks_missing_tool_as_unavailable(self, mock_system):
        with patch("src.backend.privileges.command_available", return_value=False):
            status = recovery.recovery_tool_status()

        assert status["available"] is False
        assert status["tool"] is None

    @patch("platform.system", return_value="Linux")
    @patch("subprocess.run")
    def test_creates_timeshift_snapshot(self, mock_run, mock_system):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        with patch("src.backend.privileges.command_available", return_value=True), \
             patch("src.backend.privileges.is_elevated", return_value=True):
            result = recovery.create_recovery_point("before bulk removal")

        assert result["success"] is True
        assert result["tool"] == "Timeshift"
        command = mock_run.call_args[0][0]
        assert command[0] == "timeshift"
        assert "--create" in command

    @patch("platform.system", return_value="Linux")
    @patch("subprocess.run")
    def test_no_tool_means_no_command_and_failure(self, mock_run, mock_system):
        with patch("src.backend.privileges.command_available", return_value=False):
            result = recovery.create_recovery_point()

        assert result["success"] is False
        assert result["tool"] is None
        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# Guarded removal pipeline (dry-run -> recovery -> removal)
# ---------------------------------------------------------------------------

def _apt_run_side_effect(command, **kwargs):
    if command[0] == "dpkg-query":
        return MagicMock(
            stdout="vim\t102400\ncurl\t4096\n",
            stderr="",
            returncode=0,
        )
    if command[0] == "apt" and "--obsolete" in command:
        return MagicMock(
            stdout="orphan-pkg/stable,now 1.0 amd64 [installed]\n",
            stderr="",
            returncode=0,
        )
    return MagicMock(stdout="", stderr="", returncode=0)


class TestGuardedRemoval:
    @patch("subprocess.run")
    def test_blocked_removal_never_touches_recovery_or_remove(self, mock_run):
        adapter = AptAdapter()
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        result = guards.safe_bulk_removal(adapter, ["systemd", "bash"])

        assert result["blocked"] == ["systemd", "bash"]
        assert result["removed"] is False
        apt_calls = [c for c in mock_run.call_args_list if c[0][0][0] == "apt"]
        assert apt_calls == []

    @patch("platform.system", return_value="Linux")
    @patch("subprocess.run")
    def test_guarded_removal_creates_recovery_point_before_apt(self, mock_run, mock_system):
        mock_run.side_effect = _apt_run_side_effect
        with patch("src.backend.privileges.command_available", return_value=True), \
             patch("src.backend.privileges.is_elevated", return_value=True):
            adapter = AptAdapter()
            result = guards.safe_bulk_removal(adapter, ["vim", "curl"])

        assert result["removed"] is True
        assert result["recovery"]["created"] is True

        order = [c[0][0][0] for c in mock_run.call_args_list]
        timeshift_index = order.index("timeshift")
        apt_remove_index = [i for i, name in enumerate(order) if name == "apt"][0]
        assert timeshift_index < apt_remove_index

    @patch("platform.system", return_value="Linux")
    @patch("subprocess.run")
    def test_require_recovery_blocks_removal_when_unavailable(self, mock_run, mock_system):
        mock_run.side_effect = _apt_run_side_effect
        with patch("src.backend.privileges.command_available", return_value=False):
            adapter = AptAdapter()
            result = guards.safe_bulk_removal(
                adapter,
                ["vim", "curl"],
                require_recovery=True,
            )

        assert result["removed"] is False
        assert "recovery" in result

    @patch("subprocess.run")
    def test_aborted_operation_skips_removal(self, mock_run):
        operation = Operation("cleanup")
        operation.cancel()
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        adapter = AptAdapter()

        result = guards.safe_bulk_removal(adapter, ["vim"], operation=operation)

        assert result["aborted"] is True
        assert result["removed"] is False

    @patch("platform.system", return_value="Linux")
    @patch("subprocess.run")
    def test_guarded_autoremove_records_recovery_point(self, mock_run, mock_system):
        mock_run.side_effect = _apt_run_side_effect
        with patch("src.backend.privileges.command_available", return_value=True), \
             patch("src.backend.privileges.is_elevated", return_value=True):
            adapter = AptAdapter()
            result = guards.safe_autoremove(adapter)

        assert result["removed"] is True
        assert result["recovery"]["created"] is True
