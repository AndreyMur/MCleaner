import os
import shutil
import subprocess
from pathlib import Path
from typing import List

from ..base.adapter import PackageManagerAdapter, PackageInfo, RemovalPlan


SYSTEM_PACKAGES = {
    # macOS core (system-provided, not via Homebrew)
    "bash", "zsh", "sh", "dash",
    "systemd",  # placeholder, macOS uses launchd
    # Homebrew-managed critical CLI tools
    "python", "python3", "python@3.9", "python@3.10", "python@3.11", "python@3.12",
    "ruby", "perl", "php",
    "node", "node@18", "node@20",
    "gcc", "gcc@12", "gcc@13", "clang", "clang-format",
    "cmake", "make", "automake", "autoconf", "libtool",
    "binutils", "coreutils", "findutils", "grep", "sed", "awk",
    "gnu-sed", "gnu-grep", "gnu-tar", "gnu-coreutils",
    "openssl", "openssl@3", "libressl", "ca-certificates",
    "git", "git-lfs", "mercurial", "svn",
    "curl", "wget", "aria2",
    "sudo", "doas",
    # macOS system frameworks (should never be managed by brew)
    "libc", "libsystem", "crt", "dyld",
    "launchd", "mach_kernel", "xnu",
    "system-cmds", "shell_cmds", "adv_cmds",
    # Security
    "openssh", "ssh", "libssh2", "libgcrypt", "gnupg",
    "dnsmasq", "hostapd",
    "openldap", "kerberos",
    # Critical services
    "cups", "postfix", "ntp", "ntpd",
    "apache", "httpd", "nginx",
    # CLI essentials
    "zlib", "zstd", "xz", "bzip2", "lz4", "snappy",
    "icu4c", "icu4c@70", "oniguruma",
    "pcre", "pcre2", "readline", "libedit",
    "sqlite", "libxml2", "libxslt", "expat",
    "libpng", "libjpeg", "libtiff", "giflib",
    "gettext", "glib", "pkg-config", "pkgconf",
    "ncurses", "ncursesw",
    "openssl", "openssl@1.1", "openssl@3",
    "libffi", "libyaml", "libiconv",
}


class HomebrewAdapter(PackageManagerAdapter):
    def __init__(self):
        self._cache_size: int = 0

    def _run_cmd(self, cmd: List[str]) -> tuple[str, str, int]:
        env = os.environ.copy()
        env["HOMEBREW_NO_AUTO_UPDATE"] = "1"
        env["HOMEBREW_NO_INSTALL_CLEANUP"] = "1"
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
            )
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return "", "Command timed out", -1
        except FileNotFoundError:
            return "", f"Command not found: {cmd[0]}", -1
        except Exception as e:
            return "", str(e), -1

    def _is_system_package(self, package_name: str) -> bool:
        if not package_name:
            return False
        name = package_name.lower()
        if name in SYSTEM_PACKAGES:
            return True
        return name.startswith("macos-") or name in (
            "xcode", "xcode-select", "xcode-commandlinetools",
        )

    def _get_brew_path(self) -> str:
        candidates = [
            "/opt/homebrew/bin/brew",
            "/usr/local/bin/brew",
            "/home/linuxbrew/.linuxbrew/bin/brew",
        ]
        for candidate in candidates:
            if Path(candidate).exists():
                return candidate
        return "brew"

    def _get_cache_dir(self) -> Path:
        home = Path(Path.home())
        return home / "Library" / "Caches" / "Homebrew"

    def get_installed_packages(self) -> List[PackageInfo]:
        brew = self._get_brew_path()
        stdout, stderr, code = self._run_cmd([brew, "list", "--formula", "--versions"])
        if code != 0:
            return []

        packages = []
        for line in stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split()
            name = parts[0]
            version = parts[1] if len(parts) > 1 else ""
            packages.append(PackageInfo(
                name=name,
                version=version,
                size=0,
                description="",
                is_installed=True,
            ))

        return packages

    def get_cache_size(self) -> int:
        cache_dir = self._get_cache_dir()
        total_size = 0
        if cache_dir.exists():
            for root, dirs, files in os.walk(cache_dir):
                for file in files:
                    try:
                        total_size += (Path(root) / file).stat().st_size
                    except OSError:
                        pass
        self._cache_size = total_size
        return total_size

    def clean_cache(self) -> bool:
        brew = self._get_brew_path()
        stdout, stderr, code = self._run_cmd([brew, "cleanup", "--prune=all"])
        if code != 0:
            return False

        cache_dir = self._get_cache_dir()
        downloads = cache_dir / "downloads"
        if downloads.exists():
            try:
                shutil.rmtree(downloads)
            except OSError:
                pass

        self._cache_size = 0
        return True

    def simulate_removal(self, package_names: List[str]) -> RemovalPlan:
        blocked = [p for p in package_names if self._is_system_package(p)]
        safe_packages = [p for p in package_names if not self._is_system_package(p)]

        packages_info = []
        total_size = 0
        for name in safe_packages:
            size = self._get_package_size(name)
            total_size += size
            packages_info.append(PackageInfo(
                name=name,
                version="",
                size=size,
                description="",
                is_installed=True,
            ))

        return RemovalPlan(
            packages=packages_info,
            total_size=total_size,
            can_proceed=len(blocked) == 0,
            blocked_packages=blocked,
        )

    def _get_package_size(self, name: str) -> int:
        brew = self._get_brew_path()
        stdout, _, code = self._run_cmd([brew, "info", "--json=v2", "--formula", name])
        if code != 0 or not stdout.strip():
            return 0
        try:
            import json
            data = json.loads(stdout)
            formula = data.get("formulae", [{}])[0]
            installed = formula.get("installed", [{}])[0]
            return int(installed.get("size", 0))
        except (ValueError, IndexError, TypeError):
            return 0

    def remove_packages(self, package_names: List[str]) -> bool:
        plan = self.simulate_removal(package_names)
        if not plan.can_proceed:
            return False

        safe_packages = [p for p in package_names if not self._is_system_package(p)]
        if not safe_packages:
            return False

        brew = self._get_brew_path()
        stdout, stderr, code = self._run_cmd([brew, "uninstall", "--force"] + safe_packages)
        return code == 0

    def get_orphaned_packages(self) -> List[PackageInfo]:
        brew = self._get_brew_path()
        stdout, stderr, code = self._run_cmd(
            [brew, "autoremove", "--dry-run"]
        )
        if code != 0:
            return []

        orphaned = []
        for line in stdout.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            if "Would remove" not in line and "Autoremoving" not in line:
                continue
            for part in line.split():
                part = part.strip(",")
                if part and not part.isdigit() and not part.startswith("("):
                    orphaned.append(PackageInfo(
                        name=part,
                        version="",
                        size=0,
                        description="",
                        is_installed=True,
                    ))
        return orphaned

    def autoremove(self) -> bool:
        brew = self._get_brew_path()
        stdout, stderr, code = self._run_cmd([brew, "autoremove"])
        return code == 0
