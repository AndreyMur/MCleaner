import platform
import shutil
from typing import Dict, List, Optional

from .apt import AptAdapter
from .dnf import DnfAdapter
from .homebrew import HomebrewAdapter
from .pacman import PacmanAdapter
from .winget import WingetAdapter
from .zypper import ZypperAdapter
from .base.adapter import PackageManagerAdapter


ADAPTERS = {
    "apt": AptAdapter,
    "dnf": DnfAdapter,
    "pacman": PacmanAdapter,
    "zypper": ZypperAdapter,
    "winget": WingetAdapter,
    "homebrew": HomebrewAdapter,
}

PM_BINARIES = {
    "apt": "apt",
    "dnf": "dnf",
    "pacman": "pacman",
    "zypper": "zypper",
    "winget": "winget",
    "homebrew": "brew",
}

DISTRO_FAMILIES = [
    (("ubuntu", "debian", "linuxmint", "pop", "elementary"), "apt"),
    (("fedora", "rhel", "centos", "rocky", "almalinux"), "dnf"),
    (("arch", "manjaro", "endeavouros", "arcolinux", "cachyos", "blackarch"), "pacman"),
    (("opensuse", "suse", "sles", "opensuse-leap", "opensuse-tumbleweed"), "zypper"),
]

LINUX_PACKAGE_MANAGERS = ["apt", "dnf", "pacman", "zypper"]


def _read_os_release(path: str = "/etc/os-release") -> Dict[str, str]:
    values = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                values[key] = value.strip().strip('"').strip("'")
    except (OSError, IOError):
        return {}
    return values


def _distribution_ids(os_release: Dict[str, str]) -> List[str]:
    ids = []
    for field in ("ID", "ID_LIKE"):
        value = os_release.get(field, "")
        ids.extend(part.strip().lower() for part in value.replace(",", " ").split())
    return ids


def _preferred_package_managers(distribution_ids: List[str]) -> List[str]:
    preferred = []
    for family, pm in DISTRO_FAMILIES:
        if any(distro in family for distro in distribution_ids):
            preferred.append(pm)
    return preferred


def detect_package_manager() -> Optional[str]:
    system = platform.system().lower()
    preferred = []

    if system == "windows":
        preferred = ["winget"]
    elif system == "darwin":
        preferred = ["homebrew"]
    elif system == "linux":
        preferred = _preferred_package_managers(
            _distribution_ids(_read_os_release())
        )
        preferred.extend(
            pm for pm in LINUX_PACKAGE_MANAGERS if pm not in preferred
        )
    else:
        return None

    for pm in preferred:
        if shutil.which(PM_BINARIES[pm]):
            return pm
    return None


def create_adapter(
    package_manager: Optional[str] = None,
) -> Optional[PackageManagerAdapter]:
    if package_manager is None:
        package_manager = detect_package_manager()
    if package_manager is None or package_manager not in ADAPTERS:
        return None
    return ADAPTERS[package_manager]()


__all__ = [
    "ADAPTERS",
    "create_adapter",
    "detect_package_manager",
]
