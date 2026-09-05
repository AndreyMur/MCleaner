import pytest
from unittest.mock import patch, MagicMock
from src.backend.winget import WingetAdapter, PackageInfo, SYSTEM_PACKAGES


class TestWingetAdapter:
    @pytest.fixture
    def adapter(self):
        return WingetAdapter()

    def test_is_system_package_recognizes_critical_packages(self, adapter):
        critical_packages = [
            "Microsoft.Powershell", "windows", "Microsoft.Edge",
            "Microsoft.VCLibs", "explorer", "Windows-Defender",
        ]
        for pkg in critical_packages:
            assert adapter._is_system_package(pkg), f"{pkg} should be in SYSTEM_PACKAGES"

    def test_is_system_package_is_case_insensitive(self, adapter):
        assert adapter._is_system_package("MICROSOFT.POWERSHELL")
        assert adapter._is_system_package("microsoft.edge")
        assert adapter._is_system_package("Windows-Defender")

    def test_is_system_package_allows_safe_packages(self, adapter):
        safe_packages = ["7zip.7zip", "Git.Git", "Notepad++.Notepad++", "VLC.VLC"]
        for pkg in safe_packages:
            assert not adapter._is_system_package(pkg), f"{pkg} should NOT be in SYSTEM_PACKAGES"

    @patch("shutil.which", return_value=True)
    @patch("subprocess.run")
    def test_get_installed_packages_returns_list(self, mock_run, mock_which, adapter):
        mock_run.return_value = MagicMock(
            stdout=(
                "Name     Id             Version    Source\n"
                "──────── ────────────── ─────────── ─────\n"
                "7-Zip    7zip.7zip      23.01      winget\n"
                "Git      Git.Git        2.45.1     winget\n"
                "VLC      VideoLAN.VLC   3.0.20     winget\n"
            ),
            stderr="",
            returncode=0,
        )

        packages = adapter.get_installed_packages()

        assert isinstance(packages, list)
        assert len(packages) == 3
        assert packages[0].name == "7-Zip"
        assert packages[1].name == "Git"
        assert packages[2].name == "VLC"

    @patch("shutil.which", return_value=True)
    @patch("subprocess.run")
    def test_get_installed_packages_handles_empty_output(self, mock_run, mock_which, adapter):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        packages = adapter.get_installed_packages()

        assert packages == []

    @patch("os.walk")
    @patch("os.environ.get")
    def test_get_cache_size_calculates_correctly(self, mock_environ, mock_walk, adapter):
        from pathlib import Path

        mock_environ.side_effect = lambda key, default="": (
            "C:\\Users\\test" if key in ("TEMP", "LOCALAPPDATA") else default
        )

        target_dir = "C:\\Users\\test\\Temp\\WinGet"
        mock_walk.return_value = iter([
            (target_dir, [], ["file1.bin"]),
            (target_dir + "\\sub", [], ["file2.bin"]),
        ])

        sizes = {
            target_dir + "\\file1.bin": 1024,
            target_dir + "\\sub\\file2.bin": 2048,
        }

        def fake_exists(self):
            return str(self) == target_dir

        def fake_stat(self, *args, **kwargs):
            return type("Stat", (), {"st_size": sizes.get(str(self), 0)})()

        with patch("pathlib.Path.exists", fake_exists), \
             patch.object(Path, "stat", fake_stat):
            size = adapter.get_cache_size()

        assert size == 3072

    @patch("os.environ.get")
    def test_clean_cache_success(self, mock_environ, adapter):
        mock_environ.return_value = "C:\\Users\\test"
        with patch("pathlib.Path.exists", return_value=True), \
             patch("shutil.rmtree") as mock_rmtree:
            result = adapter.clean_cache()

        assert result is True
        assert mock_rmtree.call_count >= 1

    @patch("os.environ.get")
    def test_clean_cache_failure(self, mock_environ, adapter):
        mock_environ.return_value = "C:\\Users\\test"
        with patch("pathlib.Path.exists", return_value=True), \
             patch("shutil.rmtree", side_effect=OSError("Permission denied")):
            result = adapter.clean_cache()

        assert result is False

    @patch("subprocess.run")
    def test_simulate_removal_blocks_system_packages(self, mock_run, adapter):
        plan = adapter.simulate_removal(["Microsoft.Powershell", "7zip.7zip", "Microsoft.Edge"])

        assert plan.can_proceed is False
        assert "Microsoft.Powershell" in plan.blocked_packages
        assert "Microsoft.Edge" in plan.blocked_packages
        assert "7zip.7zip" not in plan.blocked_packages

    @patch("subprocess.run")
    def test_simulate_removal_allows_safe_packages(self, mock_run, adapter):
        plan = adapter.simulate_removal(["7zip.7zip", "Git.Git"])

        assert plan.can_proceed is True
        assert len(plan.blocked_packages) == 0
        assert len(plan.packages) == 2

    @patch("shutil.which", return_value=True)
    @patch("subprocess.run")
    def test_remove_packages_fails_if_blocked_packages_exist(self, mock_run, mock_which, adapter):
        result = adapter.remove_packages(["Microsoft.Powershell", "Microsoft.Edge"])

        assert result is False
        mock_run.assert_not_called()

    @patch("shutil.which", return_value=True)
    @patch("subprocess.run")
    def test_remove_packages_calls_winget_uninstall(self, mock_run, mock_which, adapter):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        result = adapter.remove_packages(["7zip.7zip"])

        assert result is True
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "winget"
        assert cmd[1] == "uninstall"
        assert cmd[3] == "7zip.7zip"

    @patch("shutil.which", return_value=True)
    @patch("subprocess.run")
    def test_autoremove_calls_removal_of_orphans(self, mock_run, mock_which, adapter):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        with patch.object(adapter, "get_orphaned_packages") as mock_orphans:
            mock_orphans.return_value = [
                PackageInfo(name="OldPkg", version="1.0", size=0, description="", is_installed=True)
            ]
            result = adapter.autoremove()

        assert result is True

    @patch("shutil.which", return_value=True)
    @patch("subprocess.run")
    def test_autoremove_returns_true_if_no_orphans(self, mock_run, mock_which, adapter):
        with patch.object(adapter, "get_orphaned_packages", return_value=[]):
            result = adapter.autoremove()

        assert result is True
        mock_run.assert_not_called()

    @patch("shutil.which", return_value=True)
    @patch("subprocess.run")
    def test_get_orphaned_packages(self, mock_run, mock_which, adapter):
        mock_run.return_value = MagicMock(
            stdout=(
                "Name       Id            Version   Source\n"
                "─────────  ─────────────  ────────  ─────\n"
                "Orphan     Orphan.Pkg    1.0.0     winget\n"
            ),
            stderr="",
            returncode=0,
        )

        orphaned = adapter.get_orphaned_packages()

        assert len(orphaned) == 1
        assert orphaned[0].name == "Orphan"

    def test_run_cmd_handles_timeout(self, adapter):
        with patch("subprocess.run", side_effect=Exception("timeout")):
            stdout, stderr, code = adapter._run_cmd(["winget", "list"])

            assert stderr == "timeout"
            assert code == -1


class TestSystemPackagesBlacklist:
    def test_system_packages_not_empty(self):
        assert len(SYSTEM_PACKAGES) > 30

    def test_system_packages_all_lowercase(self):
        for pkg in SYSTEM_PACKAGES:
            assert pkg == pkg.lower(), f"{pkg} should be lowercase"

    def test_system_packages_contains_windows_core(self):
        assert "windows" in SYSTEM_PACKAGES
        assert "explorer" in SYSTEM_PACKAGES
        assert "microsoft-edge" in SYSTEM_PACKAGES
        assert "microsoft-powershell" in SYSTEM_PACKAGES

    def test_system_packages_contains_security(self):
        assert "windows-defender" in SYSTEM_PACKAGES
        assert "microsoft-security-essentials" in SYSTEM_PACKAGES
