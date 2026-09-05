import subprocess
from typing import List

from ..base.adapter import PackageManagerAdapter, PackageInfo, RemovalPlan


SYSTEM_PACKAGES = {
    # Shells and core CLI
    "bash", "zsh", "sh", "dash",
    "coreutils", "findutils", "grep", "sed", "awk", "gawk",
    "tar", "gzip", "bzip2", "xz", "zip", "unzip",
    "glibc", "glibc-extra", "glibc-locale", "libc", "libgcc_s1",
    "sudo", "doas",
    "util-linux", "util-linux-systemd", "procps", "psmisc",
    # Package managers
    "zypper", "rpm", "rpm-ndb", "libzypp", "libzypp-bin", "libsolv-tools",
    "packagekit", "packagekit-backend-zypp",
    # Init system / services
    "systemd", "systemd-libs", "systemd-sysvinit", "systemd-udev",
    "dbus-1", "dbus-1-daemon", "dbus-1-x11", "polkit",
    "cryptsetup", "cryptsetup-libs", "lvm2", "device-mapper",
    "mdadm", "dmraid", "udev",
    # Kernel and boot
    "kernel-default", "kernel-default-base", "kernel-devel",
    "kernel-firmware-all", "kernel-firmware",
    "grub2", "grub2-branding", "grub2-i386-pc", "grub2-x86_64-efi",
    "shim", "shim-unsigned", "efibootmgr", "dracut", "dracut-mkinitrd-dep",
    # Networking
    "iproute2", "iputils",
    "networkmanager", "dhcp-client", "wpa_supplicant", "openssh", "openssh-server",
    "firewalld", "iptables", "nftables", "hostname",
    # Crypto / security
    "openssl", "libopenssl3", "openssl-3", "ca-certificates",
    "ca-certificates-mozilla", "gnupg2", "gnutls", "nss",
    # Time / logs / tools
    "timezone", "chrony", "rsyslog", "logrotate", "cronie", "at",
    # Display / desktop
    "gnome-shell", "gdm", "plasma5-workspace", "plasma6-workspace",
    "kwin5", "kwin6", "sddm", "lightdm", "xfce4-session",
    "cinnamon", "mate-session", "budgie-desktop",
    "xorg-x11-server", "xorg-x11-server-xorg", "mesa",
    "pulseaudio", "pipewire", "alsa", "alsa-utils",
    # Interpreters / toolchains commonly required by the system
    "python3", "python3-base", "python3-311", "python3-312",
    "perl", "perl-base", "ruby", "php8", "nodejs", "npm",
    "gcc", "gcc-c++", "clang", "make", "cmake",
    "autoconf", "automake", "binutils", "libtool",
    "patch", "diffutils",
    # Firmware / hardware
    "fwupd", "bluez", "cups", "cups-client",
    # Flatpak/snap
    "flatpak", "snapd",
    # Filesystem helpers
    "gvfs", "ntfs-3g", "udisks2", "parted",
}


class ZypperAdapter(PackageManagerAdapter):
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

    def get_installed_packages(self) -> List[PackageInfo]:
        stdout, stderr, code = self._run_cmd(
            ["rpm", "-qa", "--qf", "%{NAME}\t%{VERSION}-%{RELEASE}\n"]
        )
        if code != 0:
            return []

        packages = []
        for line in stdout.strip().split('\n'):
            if not line.strip() or '\t' not in line:
                continue
            name, version = line.split('\t', 1)
            packages.append(PackageInfo(
                name=name,
                version=version,
                size=0,
                description="",
                is_installed=True,
            ))

        return packages

    def get_cache_size(self) -> int:
        cache_dirs = [
            "/var/cache/zypp/packages",
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
        stdout, stderr, code = self._run_cmd(["zypper", "clean", "--all"])
        if code == 0:
            self._cache_size = 0
            return True
        return False

    def simulate_removal(self, package_names: List[str]) -> RemovalPlan:
        blocked = [p for p in package_names if self._is_system_package(p)]
        safe_packages = [p for p in package_names if not self._is_system_package(p)]

        total_size = 0
        packages_info = []

        if safe_packages:
            stdout, _, code = self._run_cmd(
                ["rpm", "-q", "--qf", "%{NAME}\t%{SIZE}\n"] + safe_packages
            )
            if code == 0:
                for line in stdout.strip().split('\n'):
                    if '\t' in line:
                        name, size = line.split('\t')
                        try:
                            size_bytes = int(size)
                            total_size += size_bytes
                            packages_info.append(PackageInfo(
                                name=name,
                                version="",
                                size=size_bytes,
                                description="",
                                is_installed=True,
                            ))
                        except ValueError:
                            pass

        return RemovalPlan(
            packages=packages_info,
            total_size=total_size,
            can_proceed=len(blocked) == 0,
            blocked_packages=blocked,
        )

    def remove_packages(self, package_names: List[str]) -> bool:
        plan = self.simulate_removal(package_names)
        if not plan.can_proceed:
            return False

        safe_packages = [p for p in package_names if not self._is_system_package(p)]
        if not safe_packages:
            return False

        stdout, stderr, code = self._run_cmd(
            ["zypper", "remove", "-y"] + safe_packages
        )
        return code == 0

    def get_orphaned_packages(self) -> List[PackageInfo]:
        stdout, stderr, code = self._run_cmd(
            ["zypper", "--no-refresh", "packages", "--orphaned"]
        )
        if code != 0:
            return []

        orphaned = []
        for line in stdout.strip().split('\n'):
            if '|' not in line:
                continue
            parts = [part.strip() for part in line.split('|')]
            if len(parts) < 3:
                continue
            if parts[0] in ("S", "--", "") or parts[0].startswith("S "):
                continue
            if parts[1] in ("Repository", "---") or parts[1].startswith("---"):
                continue
            name = parts[2]
            if not name or name.startswith("---"):
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
