import subprocess
from typing import List

from ..base.adapter import PackageManagerAdapter, PackageInfo, RemovalPlan


SYSTEM_PACKAGES = {
    # Shells and core CLI
    "bash", "zsh", "sh", "dash",
    "coreutils", "findutils", "grep", "sed", "awk", "gawk",
    "tar", "gzip", "bzip2", "xz", "zip", "unzip",
    "glibc", "libc", "gcc-libs", "libgcc",
    "sudo", "doas",
    "util-linux", "util-linux-libs", "procps-ng", "psmisc",
    "shadow", "chmod", "chown", "chgrp",
    # Package managers
    "pacman", "pacman-mirrorlist", "archlinux-keyring",
    # Init system / services
    "systemd", "systemd-libs", "systemd-sysvcompat", "systemd-udev",
    "dbus", "dbus-daemon", "polkit", "polkit-qt5",
    "cryptsetup", "lvm2", "device-mapper", "mdadm", "dmraid",
    "udev",
    # Kernel and boot
    "linux", "linux-lts", "linux-hardened", "linux-zen",
    "linux-headers", "linux-lts-headers", "linux-firmware",
    "mkinitcpio", "mkinitcpio-busybox", "grub", "grub-legacy",
    "efibootmgr", "shim", "intel-ucode", "amd-ucode",
    # Networking
    "iproute2", "iputils", "iwd", "networkmanager", "dhcpcd",
    "openssh", "wpa_supplicant", "firewalld", "iptables", "nftables",
    "hostname", "inetutils", "bind",
    # Crypto / security
    "openssl", "openssl-1.1", "ca-certificates", "ca-certificates-utils",
    "gnupg", "gnutls", "nss", "nspr",
    # Time / logs / tools
    "tzdata", "rsyslog", "logrotate", "cronie", "at", "systemd-sysvcompat",
    "which", "file", "less", "vim", "vi", "nano",
    # Display / desktop
    "gnome-shell", "gnome-session", "gdm", "plasma-desktop",
    "kwin", "sddm", "lightdm", "xfce4-session", "mate-session",
    "cinnamon", "budgie-desktop",
    "xorg-server", "xorg-xinit", "xorg-drivers", "mesa",
    "pulseaudio", "pipewire", "pipewire-pulse", "alsa-utils",
    # Interpreters / toolchains commonly required by the system
    "python", "python3", "perl", "ruby", "php", "nodejs", "npm",
    "gcc", "clang", "make", "cmake", "autoconf", "automake",
    "binutils", "patch", "diffutils",
    # Firmware / hardware
    "fwupd", "bluez", "cups",
    # Flatpak/snap
    "flatpak", "snapd",
    # Filesystem helpers
    "gvfs", "ntfs-3g", "udisks2", "parted",
}


class PacmanAdapter(PackageManagerAdapter):
    def __init__(self):
        self._cache_size: int = 0

    def _run_cmd(self, cmd: List[str]) -> tuple[str, str, int]:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return "", "Command timed out", -1
        except FileNotFoundError:
            return "", f"Command not found: {cmd[0]}", -1
        except Exception as e:
            return "", str(e), -1

    def _is_system_package(self, package_name: str) -> bool:
        return package_name.lower() in SYSTEM_PACKAGES

    @staticmethod
    def _parse_size(size_str: str) -> int:
        parts = size_str.strip().split()
        if not parts:
            return 0
        try:
            value = float(parts[0])
        except ValueError:
            return 0

        unit = parts[1].lower() if len(parts) > 1 else "b"
        factor = {
            "b": 1,
            "kib": 1024,
            "mib": 1024 ** 2,
            "gib": 1024 ** 3,
            "tib": 1024 ** 4,
        }.get(unit)
        if factor is None:
            return 0
        return int(value * factor)

    def get_installed_packages(self) -> List[PackageInfo]:
        stdout, stderr, code = self._run_cmd(["pacman", "-Q"])
        if code != 0:
            return []

        packages = []
        for line in stdout.strip().split('\n'):
            if not line.strip():
                continue
            parts = line.split()
            packages.append(PackageInfo(
                name=parts[0],
                version=parts[1] if len(parts) > 1 else "",
                size=0,
                description="",
                is_installed=True,
            ))

        return packages

    def get_cache_size(self) -> int:
        cache_dirs = [
            "/var/cache/pacman/pkg",
        ]

        total_size = 0
        for cache_dir in cache_dirs:
            stdout, _, code = self._run_cmd(["du", "-sb", cache_dir])
            if code == 0:
                try:
                    size = int(stdout.split()[0])
                    total_size += size
                except (ValueError, IndexError):
                    pass

        self._cache_size = total_size
        return total_size

    def clean_cache(self) -> bool:
        stdout, stderr, code = self._run_cmd(["pacman", "-Scc", "--noconfirm"])
        if code == 0:
            self._cache_size = 0
            return True
        return False

    def simulate_removal(self, package_names: List[str]) -> RemovalPlan:
        blocked = [p for p in package_names if self._is_system_package(p)]
        safe_packages = [p for p in package_names if not self._is_system_package(p)]

        total_size = 0
        packages_info = []

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
        stdout, _, code = self._run_cmd(["pacman", "-Qi", name])
        if code != 0 or not stdout.strip():
            return 0
        for line in stdout.split('\n'):
            stripped = line.strip()
            if stripped.lower().startswith("installed size"):
                return self._parse_size(stripped.split(":", 1)[1])
        return 0

    def remove_packages(self, package_names: List[str]) -> bool:
        plan = self.simulate_removal(package_names)
        if not plan.can_proceed:
            return False

        safe_packages = [p for p in package_names if not self._is_system_package(p)]
        if not safe_packages:
            return False

        stdout, stderr, code = self._run_cmd(
            ["pacman", "-R", "--noconfirm"] + safe_packages
        )
        return code == 0

    def get_orphaned_packages(self) -> List[PackageInfo]:
        stdout, stderr, code = self._run_cmd(["pacman", "-Qdtq"])
        if code != 0:
            return []

        orphaned = []
        for line in stdout.strip().split('\n'):
            name = line.strip()
            if not name:
                continue
            orphaned.append(PackageInfo(
                name=name,
                version="",
                size=0,
                description="",
                is_installed=True,
            ))

        return orphaned

    def autoremove(self) -> bool:
        orphans = self.get_orphaned_packages()
        if not orphans:
            return True
        names = [o.name for o in orphans]
        return self.remove_packages(names)
