import pytest
from unittest.mock import patch, MagicMock
from src.backend.dnf import DnfAdapter, PackageInfo, SYSTEM_PACKAGES


class TestDnfAdapter:
    @pytest.fixture
    def adapter(self):
        return DnfAdapter()

    def test_is_system_package_recognizes_critical_packages(self, adapter):
        critical_packages = [
            "systemd", "bash", "rpm", "dnf", "kernel", "glibc", "sudo",
        ]
        for pkg in critical_packages:
            assert adapter._is_system_package(pkg), f"{pkg} should be in SYSTEM_PACKAGES"

    def test_is_system_package_is_case_insensitive(self, adapter):
        assert adapter._is_system_package("SYSTEMD")
        assert adapter._is_system_package("Bash")
        assert adapter._is_system_package("GLIBC")

    def test_is_system_package_allows_safe_packages(self, adapter):
        safe_packages = ["vim", "curl", "git", "neovim", "htop", "firefox"]
        for pkg in safe_packages:
            assert not adapter._is_system_package(pkg), f"{pkg} should NOT be in SYSTEM_PACKAGES"

    @patch('subprocess.run')
    def test_get_installed_packages_returns_list(self, mock_run, adapter):
        mock_run.return_value = MagicMock(
            stdout="vim\t9.1.0-1.fc40\ngit\t2.45.1-1.fc40\ncurl\t8.5.0-1.fc40\n",
            stderr="",
            returncode=0
        )

        packages = adapter.get_installed_packages()

        assert isinstance(packages, list)
        assert len(packages) == 3
        assert packages[0].name == "vim"
        assert packages[0].version == "9.1.0-1.fc40"
        assert packages[1].name == "git"
        assert packages[2].name == "curl"

    @patch('subprocess.run')
    def test_get_installed_packages_handles_empty_output(self, mock_run, adapter):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        packages = adapter.get_installed_packages()

        assert packages == []

    @patch('subprocess.run')
    def test_get_cache_size_calculates_correctly(self, mock_run, adapter):
        def side_effect(cmd, *args, **kwargs):
            if cmd == ["du", "-sb", "/var/cache/dnf"]:
                return MagicMock(stdout="104857600\t/var/cache/dnf\n", stderr="", returncode=0)
            return MagicMock(stdout="", stderr="", returncode=0)

        mock_run.side_effect = side_effect

        size = adapter.get_cache_size()

        assert size == 104857600

    @patch('subprocess.run')
    def test_clean_cache_success(self, mock_run, adapter):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        result = adapter.clean_cache()

        assert result is True
        mock_run.assert_called_once_with(["dnf", "clean", "all"], capture_output=True, text=True, timeout=120)

    @patch('subprocess.run')
    def test_clean_cache_failure(self, mock_run, adapter):
        mock_run.return_value = MagicMock(stdout="", stderr="Error", returncode=1)

        result = adapter.clean_cache()

        assert result is False

    @patch('subprocess.run')
    def test_simulate_removal_blocks_system_packages(self, mock_run, adapter):
        plan = adapter.simulate_removal(["systemd", "vim", "bash"])

        assert plan.can_proceed is False
        assert "systemd" in plan.blocked_packages
        assert "bash" in plan.blocked_packages
        assert "vim" not in plan.blocked_packages

    @patch('subprocess.run')
    def test_simulate_removal_allows_safe_packages(self, mock_run, adapter):
        mock_run.return_value = MagicMock(
            stdout="vim\t102400\ncurl\t2048\n",
            stderr="",
            returncode=0
        )

        plan = adapter.simulate_removal(["vim", "curl"])

        assert plan.can_proceed is True
        assert len(plan.blocked_packages) == 0
        assert len(plan.packages) == 2
        assert plan.total_size == 104448

    @patch('subprocess.run')
    def test_remove_packages_fails_if_blocked_packages_exist(self, mock_run, adapter):
        result = adapter.remove_packages(["systemd", "bash"])

        assert result is False
        mock_run.assert_not_called()

    @patch('subprocess.run')
    def test_remove_packages_calls_dnf_remove(self, mock_run, adapter):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        result = adapter.remove_packages(["vim"])

        assert result is True
        dnf_calls = [call for call in mock_run.call_args_list if call[0][0][0] == "dnf"]
        assert len(dnf_calls) == 1
        assert dnf_calls[0][0][0] == ["dnf", "remove", "-y", "vim"]

    @patch('subprocess.run')
    def test_autoremove_calls_dnf_autoremove(self, mock_run, adapter):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        result = adapter.autoremove()

        assert result is True
        mock_run.assert_called_once_with(
            ["dnf", "autoremove", "-y"],
            capture_output=True, text=True, timeout=120
        )

    @patch('subprocess.run')
    def test_get_orphaned_packages(self, mock_run, adapter):
        mock_run.return_value = MagicMock(
            stdout="orphaned-pkg-1\norphaned-pkg-2\n",
            stderr="",
            returncode=0
        )

        orphaned = adapter.get_orphaned_packages()

        assert len(orphaned) == 2
        assert orphaned[0].name == "orphaned-pkg-1"
        assert orphaned[1].name == "orphaned-pkg-2"

    def test_run_cmd_handles_timeout(self, adapter):
        with patch('subprocess.run', side_effect=Exception("timeout")):
            stdout, stderr, code = adapter._run_cmd(["dnf", "list"])

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
        assert "dnf" in SYSTEM_PACKAGES
        assert "rpm" in SYSTEM_PACKAGES

    def test_system_packages_contains_security(self):
        assert "openssl" in SYSTEM_PACKAGES
        assert "ca-certificates" in SYSTEM_PACKAGES
