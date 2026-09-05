import pytest
from unittest.mock import patch
from src.backend import detect
from src.backend.apt import AptAdapter
from src.backend.dnf import DnfAdapter
from src.backend.homebrew import HomebrewAdapter
from src.backend.pacman import PacmanAdapter
from src.backend.winget import WingetAdapter
from src.backend.zypper import ZypperAdapter


class TestReadOsRelease:
    def test_parses_fields_and_quotes(self, tmp_path):
        os_release = tmp_path / "os-release"
        os_release.write_text(
            'NAME="Fedora Linux"\n'
            "ID=fedora\n"
            "ID_LIKE=\"\n"
            'PRETTY_NAME="Fedora Linux 40 (Workstation Edition)"\n'
            "# comment\n"
            "\n"
        )

        data = detect._read_os_release(str(os_release))

        assert data["ID"] == "fedora"
        assert data["NAME"] == "Fedora Linux"
        assert data["PRETTY_NAME"] == "Fedora Linux 40 (Workstation Edition)"
        assert "comment" not in data

    def test_missing_file_returns_empty(self):
        assert detect._read_os_release("/nonexistent/os-release") == {}

    def test_distribution_ids_splits_id_like(self):
        data = {"ID": "neon", "ID_LIKE": "ubuntu debian"}

        ids = detect._distribution_ids(data)

        assert "neon" in ids
        assert "ubuntu" in ids
        assert "debian" in ids

    def test_distribution_ids_handles_missing_fields(self):
        assert detect._distribution_ids({}) == []


class TestDetectPackageManager:
    @patch("shutil.which")
    @patch.object(detect, "_read_os_release", return_value={"ID": "fedora"})
    @patch("platform.system", return_value="Linux")
    def test_detects_dnf_on_fedora(self, mock_system, mock_release, mock_which):
        mock_which.side_effect = lambda name: name == "dnf"

        assert detect.detect_package_manager() == "dnf"

    @patch("shutil.which")
    @patch.object(detect, "_read_os_release", return_value={"ID": "debian"})
    @patch("platform.system", return_value="Linux")
    def test_detects_apt_on_debian(self, mock_system, mock_release, mock_which):
        mock_which.side_effect = lambda name: name == "apt"

        assert detect.detect_package_manager() == "apt"

    @patch("shutil.which")
    @patch.object(detect, "_read_os_release", return_value={"ID": "ubuntu", "ID_LIKE": "debian"})
    @patch("platform.system", return_value="Linux")
    def test_detects_apt_on_ubuntu(self, mock_system, mock_release, mock_which):
        mock_which.side_effect = lambda name: name == "apt"

        assert detect.detect_package_manager() == "apt"

    @patch("shutil.which")
    @patch.object(detect, "_read_os_release", return_value={"ID": "arch"})
    @patch("platform.system", return_value="Linux")
    def test_detects_pacman_on_arch(self, mock_system, mock_release, mock_which):
        mock_which.side_effect = lambda name: name == "pacman"

        assert detect.detect_package_manager() == "pacman"

    @patch("shutil.which")
    @patch.object(detect, "_read_os_release", return_value={"ID": "opensuse-tumbleweed"})
    @patch("platform.system", return_value="Linux")
    def test_detects_zypper_on_opensuse(self, mock_system, mock_release, mock_which):
        mock_which.side_effect = lambda name: name == "zypper"

        assert detect.detect_package_manager() == "zypper"

    @patch("shutil.which")
    @patch("platform.system", return_value="Windows")
    def test_detects_winget_on_windows(self, mock_system, mock_which):
        mock_which.return_value = "C:\\Windows\\winget.exe"

        assert detect.detect_package_manager() == "winget"

    @patch("shutil.which")
    @patch("platform.system", return_value="Darwin")
    def test_detects_homebrew_on_macos(self, mock_system, mock_which):
        mock_which.return_value = "/opt/homebrew/bin/brew"

        assert detect.detect_package_manager() == "homebrew"

    @patch("shutil.which")
    @patch.object(detect, "_read_os_release", return_value={"ID": "unknown-distro"})
    @patch("platform.system", return_value="Linux")
    def test_falls_back_to_available_binary(self, mock_system, mock_release, mock_which):
        mock_which.side_effect = lambda name: name == "pacman"

        assert detect.detect_package_manager() == "pacman"

    @patch("shutil.which", return_value=None)
    @patch.object(detect, "_read_os_release", return_value={"ID": "fedora"})
    @patch("platform.system", return_value="Linux")
    def test_returns_none_if_no_binary_available(self, mock_system, mock_release, mock_which):
        assert detect.detect_package_manager() is None


class TestCreateAdapter:
    def test_creates_apt_adapter(self):
        assert isinstance(detect.create_adapter("apt"), AptAdapter)

    def test_creates_dnf_adapter(self):
        assert isinstance(detect.create_adapter("dnf"), DnfAdapter)

    def test_creates_pacman_adapter(self):
        assert isinstance(detect.create_adapter("pacman"), PacmanAdapter)

    def test_creates_zypper_adapter(self):
        assert isinstance(detect.create_adapter("zypper"), ZypperAdapter)

    def test_creates_winget_adapter(self):
        assert isinstance(detect.create_adapter("winget"), WingetAdapter)

    def test_creates_homebrew_adapter(self):
        assert isinstance(detect.create_adapter("homebrew"), HomebrewAdapter)

    def test_unknown_manager_returns_none(self):
        assert detect.create_adapter("unknown-pm") is None

    @patch.object(detect, "detect_package_manager", return_value="dnf")
    def test_creates_adapter_using_detection(self, mock_detect):
        assert isinstance(detect.create_adapter(), DnfAdapter)

    @patch.object(detect, "detect_package_manager", return_value=None)
    def test_returns_none_when_detection_fails(self, mock_detect):
        assert detect.create_adapter() is None
