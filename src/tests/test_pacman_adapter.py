import pytest
from unittest.mock import patch, MagicMock
from src.backend.pacman import PacmanAdapter, PackageInfo, SYSTEM_PACKAGES


class TestPacmanAdapter:
    @pytest.fixture
    def adapter(self):
        return PacmanAdapter()

    def test_is_system_package_recognizes_critical_packages(self, adapter):
        critical_packages = [
            "systemd", "bash", "linux", "glibc", "sudo", "pacman",
        ]
        for pkg in critical_packages:
            assert adapter._is_system_package(pkg), f"{pkg} should be in SYSTEM_PACKAGES"

    def test_is_system_package_is_case_insensitive(self, adapter):
        assert adapter._is_system_package("SYSTEMD")
        assert adapter._is_system_package("Bash")
        assert adapter._is_system_package("PACMAN")

    def test_is_system_package_allows_safe_packages(self, adapter):
        safe_packages = ["firefox", "vlc", "spotify", "neovim", "htop"]
        for pkg in safe_packages:
            assert not adapter._is_system_package(pkg), f"{pkg} should NOT be in SYSTEM_PACKAGES"

    @patch('subprocess.run')
    def test_get_installed_packages_returns_list(self, mock_run, adapter):
        mock_run.return_value = MagicMock(
            stdout="vim 9.1.0-1\ncurl 8.5.0-2\ngit 2.45.1-1\n",
            stderr="",
            returncode=0
        )

        packages = adapter.get_installed_packages()

        assert isinstance(packages, list)
        assert len(packages) == 3
        assert packages[0].name == "vim"
        assert packages[0].version == "9.1.0-1"
        assert packages[1].name == "curl"
        assert packages[2].name == "git"

    @patch('subprocess.run')
    def test_get_installed_packages_handles_empty_output(self, mock_run, adapter):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        packages = adapter.get_installed_packages()

        assert packages == []

    @patch('subprocess.run')
    def test_get_cache_size_calculates_correctly(self, mock_run, adapter):
        def side_effect(cmd, *args, **kwargs):
            if cmd == ["du", "-sb", "/var/cache/pacman/pkg"]:
                return MagicMock(stdout="209715200\t/var/cache/pacman/pkg\n", stderr="", returncode=0)
            return MagicMock(stdout="", stderr="", returncode=0)

        mock_run.side_effect = side_effect

        size = adapter.get_cache_size()

        assert size == 209715200

    @patch('subprocess.run')
    def test_clean_cache_success(self, mock_run, adapter):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        result = adapter.clean_cache()

        assert result is True
        mock_run.assert_called_once_with(
            ["pacman", "-Scc", "--noconfirm"],
            capture_output=True, text=True, timeout=120
        )

    @patch('subprocess.run')
    def test_clean_cache_failure(self, mock_run, adapter):
        mock_run.return_value = MagicMock(stdout="", stderr="Error", returncode=1)

        result = adapter.clean_cache()

        assert result is False

    def test_parse_size_various_units(self):
        assert PacmanAdapter._parse_size("0 B") == 0
        assert PacmanAdapter._parse_size("512 B") == 512
        assert PacmanAdapter._parse_size("1.00 KiB") == 1024
        assert PacmanAdapter._parse_size("2.50 MiB") == int(2.5 * 1024 ** 2)
        assert PacmanAdapter._parse_size("1 GiB") == 1024 ** 3

    def test_parse_size_invalid_input(self):
        assert PacmanAdapter._parse_size("") == 0
        assert PacmanAdapter._parse_size("garbage") == 0
        assert PacmanAdapter._parse_size("1.5 XYZ") == 0

    @patch('subprocess.run')
    def test_simulate_removal_blocks_system_packages(self, mock_run, adapter):
        plan = adapter.simulate_removal(["systemd", "firefox", "bash"])

        assert plan.can_proceed is False
        assert "systemd" in plan.blocked_packages
        assert "bash" in plan.blocked_packages
        assert "firefox" not in plan.blocked_packages

    @patch('subprocess.run')
    def test_simulate_removal_allows_safe_packages(self, mock_run, adapter):
        mock_run.return_value = MagicMock(
            stdout="Name            : firefox\nInstalled Size   : 1.00 MiB\n",
            stderr="",
            returncode=0
        )

        plan = adapter.simulate_removal(["firefox", "vlc"])

        assert plan.can_proceed is True
        assert len(plan.blocked_packages) == 0
        assert len(plan.packages) == 2
        assert plan.total_size == 2 * 1024 ** 2

    @patch('subprocess.run')
    def test_remove_packages_fails_if_blocked_packages_exist(self, mock_run, adapter):
        result = adapter.remove_packages(["systemd", "bash"])

        assert result is False
        mock_run.assert_not_called()

    @patch('subprocess.run')
    def test_remove_packages_calls_pacman_remove(self, mock_run, adapter):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        result = adapter.remove_packages(["firefox"])

        assert result is True
        pacman_calls = [
            call for call in mock_run.call_args_list
            if call[0][0][0] == "pacman" and call[0][0][1] == "-R"
        ]
        assert len(pacman_calls) == 1
        assert pacman_calls[0][0][0] == ["pacman", "-R", "--noconfirm", "firefox"]

    @patch('subprocess.run')
    def test_get_orphaned_packages(self, mock_run, adapter):
        mock_run.return_value = MagicMock(
            stdout="old-dep-1\nold-dep-2\n",
            stderr="",
            returncode=0
        )

        orphaned = adapter.get_orphaned_packages()

        assert len(orphaned) == 2
        assert orphaned[0].name == "old-dep-1"
        assert orphaned[1].name == "old-dep-2"

    @patch('subprocess.run')
    def test_autoremove_removes_orphans(self, mock_run, adapter):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        with patch.object(adapter, "get_orphaned_packages") as mock_orphans, \
             patch.object(adapter, "remove_packages") as mock_remove:
            mock_orphans.return_value = [
                PackageInfo(name="old-dep", version="1.0", size=0, description="", is_installed=True)
            ]
            mock_remove.return_value = True
            result = adapter.autoremove()

        assert result is True
        mock_remove.assert_called_once_with(["old-dep"])

    @patch('subprocess.run')
    def test_autoremove_returns_true_if_no_orphans(self, mock_run, adapter):
        with patch.object(adapter, "get_orphaned_packages", return_value=[]), \
             patch.object(adapter, "remove_packages") as mock_remove:
            result = adapter.autoremove()

        assert result is True
        mock_remove.assert_not_called()

    def test_run_cmd_handles_timeout(self, adapter):
        with patch('subprocess.run', side_effect=Exception("timeout")):
            stdout, stderr, code = adapter._run_cmd(["pacman", "-Q"])

            assert stderr == "timeout"
            assert code == -1


class TestSystemPackagesBlacklist:
    def test_system_packages_not_empty(self):
        assert len(SYSTEM_PACKAGES) > 50

    def test_system_packages_all_lowercase(self):
        for pkg in SYSTEM_PACKAGES:
            assert pkg == pkg.lower(), f"{pkg} should be lowercase"

    def test_system_packages_contains_shells(self):
        assert "bash" in SYSTEM_PACKAGES
        assert "zsh" in SYSTEM_PACKAGES

    def test_system_packages_contains_package_managers(self):
        assert "pacman" in SYSTEM_PACKAGES

    def test_system_packages_contains_security(self):
        assert "openssl" in SYSTEM_PACKAGES
        assert "ca-certificates" in SYSTEM_PACKAGES
