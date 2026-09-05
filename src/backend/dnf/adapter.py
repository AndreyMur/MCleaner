import subprocess
from typing import List

from ..base.adapter import PackageManagerAdapter, PackageInfo, RemovalPlan


SYSTEM_PACKAGES = {
    # Shells and core CLI
    "bash", "zsh", "sh", "dash",
    "coreutils", "findutils", "grep", "sed", "awk", "gawk", "mawk",
    "tar", "gzip", "bzip2", "xz", "zip", "unzip",
    "glibc", "glibc-common", "glibc-minimal-langpack", "libc", "libgcc",
    "sudo", "doas",
    "util-linux", "util-linux-core", "procps-ng", "psmisc",
    "chmod", "chown", "chgrp",
    # Package managers
    "rpm", "rpm-libs", "rpm-build-libs", "dnf", "yum", "libdnf",
    "libdnf5", "dnf5", "python3-dnf", "packagekit",
    # Init system / services
    "systemd", "systemd-libs", "systemd-udev", "systemd-pam",
    "systemd-boot-efi", "dracut", "udev", "dbus", "dbus-broker",
    "dbus-daemon", "polkit", "polkit-pkla-compat",
    "cryptsetup", "cryptsetup-libs", "lvm2", "device-mapper",
    "mdadm", "dmraid",
    # Kernel and boot
    "kernel", "kernel-core", "kernel-modules", "kernel-modules-extra",
    "kernel-devel", "kernel-tools", "kernel-headers",
    "linux", "linux-firmware", "linux-libc-dev",
    "grub2", "grub2-common", "grub2-efi-x64", "grub2-efi-ia32",
    "grubby", "shim", "shim-x64", "efibootmgr", "dracut",
    "intel-microcode", "amd-microcode", "microcode_ctl",
    # Networking
    "iproute", "iproute-tc", "iputils", "iwd",
    "networkmanager", "dhcp-client", "dhcpcd", "wpa_supplicant",
    "openssh", "openssh-server", "openssh-clients", "openssh-keygen",
    "firewalld", "iptables", "iptables-services", "nftables",
    "libnftables", "hostname",
    # Crypto / security
    "openssl", "openssl-libs", "openssl-pkcs11", "ca-certificates",
    "gnupg2", "gnutls", "nss", "nss-util", "nss-sysinit",
    # Time / logs / tools
    "chrony", "systemd-timesyncd", "rsyslog", "logrotate",
    "cronie", "crond", "anacron", "at",
    # Display / desktop (implicit protection)
    "gnome-shell", "gnome-session", "gnome-settings-daemon",
    "kwin", "kde-plasma-desktop", "plasma-desktop", "plasma-workspace",
    "xfce4-session", "mate-session", "cinnamon",
    "xorg-x11-server", "xorg-x11-server-xorg",
    "gdm", "lightdm", "sddm",
    "pulseaudio", "pipewire", "pipewire-pulse", "alsa-utils",
    "mesa", "mesa-libgl", "mesa-dri-drivers", "mesa-vulkan-drivers",
    # Interpreters / toolchains commonly required by the system
    "python3", "python3-libs", "python3.11", "python3.12",
    "perl", "perl-libs", "ruby", "php", "php-cli",
    "nodejs", "node", "npm",
    "gcc", "gcc-c++", "gcc-g++", "clang", "make", "cmake",
    "autoconf", "automake", "libtool", "binutils",
    "libgcc", "libstdc++", "libstdc++-devel",
    "patch", "diffutils", "diff", "file",
    # Firmware / hardware
    "fwupd", "fwupdmgr", "bluez", "bluez-libs", "cups", "cups-libs",
    # Snap/flatpak runtimes
    "snapd", "flatpak", "flatpak-libs",
    # Filesystem helpers
    "gvfs", "ntfs-3g", "udisks2", "lvm2", "parted",
}


class DnfAdapter(PackageManagerAdapter):
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
            "/var/cache/dnf",
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
        stdout, stderr, code = self._run_cmd(["dnf", "clean", "all"])
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
            ["dnf", "remove", "-y"] + safe_packages
        )
        return code == 0

    def get_orphaned_packages(self) -> List[PackageInfo]:
        stdout, stderr, code = self._run_cmd(
            ["dnf", "repoquery", "--unneeded"]
        )
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
        stdout, stderr, code = self._run_cmd(["dnf", "autoremove", "-y"])
        return code == 0
