import pytest
from unittest.mock import patch, MagicMock
from src.backend.homebrew import HomebrewAdapter, PackageInfo, SYSTEM_PACKAGES


class TestHomebrewAdapter:
    @pytest.fixture
    def adapter(self):
        return HomebrewAdapter()

    def test_is_system_package_recognizes_critical_packages(self, adapter):
        critical_packages = [
            "bash", "zsh", "openssl", "git", "python", "node",
            "gcc", "curl", "sudo", "launchd",
        ]
        for pkg in critical_packages:
            assert adapter._is_system_package(pkg), f"{pkg} should be in SYSTEM_PACKAGES"

    def test_is_system_package_is_case_insensitive(self, adapter):
        assert adapter._is_system_package("BASH")
        assert adapter._is_system_package("OpenSSL")
        assert adapter._is_system_package("Python")

    def test_is_system_package_allows_safe_packages(self, adapter):
        safe_packages = ["vlc", "firefox", "google-chrome", "iterm2", "rectangle"]
        for pkg in safe_packages:
            assert not adapter._is_system_package(pkg), f"{pkg} should NOT be in SYSTEM_PACKAGES"

    @patch("pathlib.Path.exists", return_value=True)
    @patch("subprocess.run")
    def test_get_installed_packages_returns_list(self, mock_run, mock_exists, adapter):
        mock_run.return_value = MagicMock(
            stdout="vim 9.0.1000\ncurl 8.4.0\ngit 2.43.0\n",
            stderr="",
            returncode=0,
        )

        packages = adapter.get_installed_packages()

        assert isinstance(packages, list)
        assert len(packages) == 3
        assert packages[0].name == "vim"
        assert packages[0].version == "9.0.1000"
        assert packages[1].name == "curl"
        assert packages[2].name == "git"

    @patch("pathlib.Path.exists", return_value=True)
    @patch("subprocess.run")
    def test_get_installed_packages_handles_empty_output(self, mock_run, mock_exists, adapter):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        packages = adapter.get_installed_packages()

        assert packages == []

    @patch("os.walk")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.home")
    def test_get_cache_size_calculates_correctly(self, mock_home, mock_exists, mock_walk, adapter):
        from pathlib import Path

        mock_home.return_value = Path("/Users/test")
        mock_exists.return_value = True

        cache_dir = str(Path("/Users/test") / "Library" / "Caches" / "Homebrew")
        downloads_dir = str(Path(cache_dir) / "downloads")

        mock_walk.return_value = iter([
            (cache_dir, [], ["downloads", "cache1.bottle"]),
            (downloads_dir, [], ["package.tar.gz"]),
        ])

        sizes = {
            str(Path(cache_dir) / "cache1.bottle"): 2048,
            str(Path(downloads_dir) / "package.tar.gz"): 4096,
        }

        def fake_stat(self, *args, **kwargs):
            return type("Stat", (), {"st_size": sizes.get(str(self), 0)})()

        with patch.object(Path, "stat", fake_stat):
            size = adapter.get_cache_size()

        assert size == 6144

    @patch("subprocess.run")
    @patch("pathlib.Path.home")
    @patch("pathlib.Path.exists", return_value=True)
    def test_clean_cache_success(self, mock_exists, mock_home, mock_run, adapter):
        mock_home.return_value = "/Users/test"
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        result = adapter.clean_cache()

        assert result is True
        assert mock_run.call_args[0][0][:2] == ["/opt/homebrew/bin/brew", "cleanup"]

    @patch("subprocess.run")
    @patch("pathlib.Path.home")
    @patch("pathlib.Path.exists", return_value=True)
    def test_clean_cache_failure(self, mock_exists, mock_home, mock_run, adapter):
        mock_home.return_value = "/Users/test"
        mock_run.return_value = MagicMock(stdout="", stderr="Error", returncode=1)

        result = adapter.clean_cache()

        assert result is False

    @patch("subprocess.run")
    def test_simulate_removal_blocks_system_packages(self, mock_run, adapter):
        plan = adapter.simulate_removal(["bash", "vim", "zsh", "firefox"])

        assert plan.can_proceed is False
        assert "bash" in plan.blocked_packages
        assert "zsh" in plan.blocked_packages
        assert "vim" not in plan.blocked_packages
        assert "firefox" not in plan.blocked_packages

    @patch("subprocess.run")
    def test_simulate_removal_allows_safe_packages(self, mock_run, adapter):
        mock_run.return_value = MagicMock(
            stdout='{"formulae":[{"installed":[{"size":1048576}]}]}',
            stderr="",
            returncode=0,
        )

        plan = adapter.simulate_removal(["firefox", "vlc"])

        assert plan.can_proceed is True
        assert len(plan.blocked_packages) == 0
        assert len(plan.packages) == 2
        assert plan.total_size == 2097152

    @patch("subprocess.run")
    def test_simulate_removal_handles_json_error(self, mock_run, adapter):
        mock_run.return_value = MagicMock(stdout="not json", stderr="", returncode=0)

        plan = adapter.simulate_removal(["firefox"])

        assert plan.can_proceed is True
        assert len(plan.packages) == 1
        assert plan.packages[0].size == 0

    @patch("subprocess.run")
    def test_remove_packages_fails_if_blocked_packages_exist(self, mock_run, adapter):
        result = adapter.remove_packages(["bash", "zsh"])

        assert result is False
        mock_run.assert_not_called()

    @patch("pathlib.Path.exists", return_value=True)
    @patch("subprocess.run")
    def test_remove_packages_calls_brew_uninstall(self, mock_run, mock_exists, adapter):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        result = adapter.remove_packages(["firefox"])

        assert result is True
        cmd = mock_run.call_args[0][0]
        assert cmd[-3:] == ["uninstall", "--force", "firefox"]

    @patch("pathlib.Path.exists", return_value=True)
    @patch("subprocess.run")
    def test_autoremove_calls_brew_autoremove(self, mock_run, mock_exists, adapter):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        result = adapter.autoremove()

        assert result is True
        assert mock_run.call_args[0][0][-1] == "autoremove"

    @patch("pathlib.Path.exists", return_value=True)
    @patch("subprocess.run")
    def test_get_orphaned_packages(self, mock_run, mock_exists, adapter):
        mock_run.return_value = MagicMock(
            stdout="Would remove: 42 formulae\n  old-dep-1\n  old-dep-2\n",
            stderr="",
            returncode=0,
        )

        orphaned = adapter.get_orphaned_packages()

        assert len(orphaned) >= 1

    def test_run_cmd_handles_timeout(self, adapter):
        with patch("subprocess.run", side_effect=Exception("timeout")):
            stdout, stderr, code = adapter._run_cmd(["brew", "list"])

            assert stderr == "timeout"
            assert code == -1


class TestSystemPackagesBlacklist:
    def test_system_packages_not_empty(self):
        assert len(SYSTEM_PACKAGES) > 30

    def test_system_packages_all_lowercase(self):
        for pkg in SYSTEM_PACKAGES:
            assert pkg == pkg.lower(), f"{pkg} should be lowercase"

    def test_system_packages_contains_shells(self):
        assert "bash" in SYSTEM_PACKAGES
        assert "zsh" in SYSTEM_PACKAGES

    def test_system_packages_contains_package_managers(self):
        assert "git" in SYSTEM_PACKAGES
        assert "curl" in SYSTEM_PACKAGES

    def test_system_packages_contains_security(self):
        assert "openssl" in SYSTEM_PACKAGES
        assert "gnupg" in SYSTEM_PACKAGES
