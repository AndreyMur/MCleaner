import subprocess
import re
from typing import List
from ..base.adapter import PackageManagerAdapter, PackageInfo, RemovalPlan


SYSTEM_PACKAGES = {
    "bash", "zsh", "sh", "dash",
    "systemd", "sysvinit", "openrc", "runit",
    "init", "telinit",
    "glibc", "libc6", "libc-bin",
    "sudo", "doas",
    "coreutils", "findutils", "grep", "sed", "awk", "tar", "gzip", "bzip2", "xz",
    "apt", "dpkg", "apt-get", "dpkg-divert",
    "openssl", "libssl", "ca-certificates",
    "cryptsetup", "lvm2", "dmraid", "mdadm",
    "grub", "grub2", "grub-legacy", "linux", "linux-image", "linux-headers",
    "systemd", "systemd-sysv",
    "dbus", "polkit", "consolekit",
    "networkmanager", "network-manager", "dhcpcd", "dhclient", "wpa_supplicant",
    "cups", "cupsd",
    "ssh", "openssh-server", "openssh-client",
    "cron", "crond", "anacron", "atd",
    "rsyslog", "syslog-ng", "journald",
    "udev", "eudev", "systemd-udevd",
    "mount", "umount", "fstab", "mtab",
    "util-linux", "mount",
    "gawk", "mawk", "original-awk",
    "python3", "python2", "python", "python3.11", "python3.12",
    "perl", "ruby", "php", "nodejs", "node",
    "gcc", "g++", "clang", "make", "cmake", "autoconf", "automake",
    "libc-dev", "libc6-dev",
    "binutils", "ld", "ldd", "objdump", "ar", "ranlib",
    "strace", "ltrace", "gdb",
    "patch", "diff", "diffutils",
    "login", "passwd", "su", "shadow",
    "adduser", "useradd", "usermod", "userdel",
    "groupadd", "groupdel", "groupmod",
    "chmod", "chown", "chgrp", "sudo",
    "hostname", "hostnamectl",
    "localectl", "timedatectl",
    "journalctl", "systemctl", "systemd-analyze",
    "loginctl", "coreductctl",
    "shutdown", "reboot", "halt", "poweroff", "init",
    "udevd", "systemd-udevd",
    "dbus-daemon", "dbus-launch", "dbus-send",
    "polkitd", "polkit-agent",
    "gnome-shell", "gnome-session", "gnome-settings-daemon",
    "kwin", "kdeinit", "plasma-desktop",
    "xfce4-session", "xfce4-settings-manager",
    "mate-session", "mate-settings-daemon",
    "cinnamon", "cinnamon-session",
    "budgie-desktop", "budgie-wm",
    "lxde", "lxqt", "openbox", "i3", "sway",
    "xorg", "x", "xserver-xorg",
    "pulseaudio", "pipewire", "pipewire-pulse", "alsa-utils",
    "gdm", "lightdm", "sddm", "lxdm", "slim",
    "plymouth", "grub2-splash",
    "dracut", "mkinitcpio", "update-initramfs",
    "fwupd", "fwupdmgr",
    "snapd", "flatpak", "packagekit",
    "packagekit", "gnome-software", "plasma-discover",
    "dconf", "gsettings-desktop-schemas",
    "dmenu", "rofi", "alacritty", "kitty", "xterm",
    "gvfs", "gvfsd", "gvfs-fuse",
    "tracker", "zeitgeist",
    "colord", "colord-sane", "sane", "saned",
    "bluetooth", "bluetoothd", "bluez",
    "firewalld", "iptables", "nftables", "ufw",
    "docker", "containerd", "runc", "podman",
    "snap", "snapd",
    "plocate", "locate", "updatedb",
}


class AptAdapter(PackageManagerAdapter):
    def __init__(self):
        self._cache_size: int = 0

    def _run_cmd(self, cmd: List[str]) -> tuple[str, str, int]:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
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
            ["apt", "list", "--installed", "--quiet=2"]
        )
        if code != 0:
            return []

        packages = []
        for line in stdout.strip().split('\n'):
            if '/' not in line:
                continue
            name_part = line.split('/')[0]
            if not name_part or name_part.startswith('listing'):
                continue

            version = ""
            parts = line.split()
            for i, part in enumerate(parts):
                if part.startswith('[installed'):
                    version = part.replace('[installed,', '').replace(']', '').strip()
                    break

            packages.append(PackageInfo(
                name=name_part,
                version=version,
                size=0,
                description="",
                is_installed=True
            ))

        return packages

    def get_cache_size(self) -> int:
        cache_dirs = [
            "/var/cache/apt/archives",
            "/var/lib/apt/lists",
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
        stdout, stderr, code = self._run_cmd(["apt", "clean"])
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
            pkg_list = " ".join(safe_packages)
            stdout, _, code = self._run_cmd(
                ["dpkg-query", "-W", "-f=${Package}\t${Installed-Size}\n"] + safe_packages
            )
            if code == 0:
                for line in stdout.strip().split('\n'):
                    if '\t' in line:
                        name, size = line.split('\t')
                        try:
                            size_kb = int(size)
                            total_size += size_kb * 1024
                            packages_info.append(PackageInfo(
                                name=name,
                                version="",
                                size=size_kb * 1024,
                                description="",
                                is_installed=True
                            ))
                        except ValueError:
                            pass

        return RemovalPlan(
            packages=packages_info,
            total_size=total_size,
            can_proceed=len(blocked) == 0,
            blocked_packages=blocked
        )

    def remove_packages(self, package_names: List[str]) -> bool:
        plan = self.simulate_removal(package_names)
        if not plan.can_proceed:
            return False

        safe_packages = [p for p in package_names if not self._is_system_package(p)]
        if not safe_packages:
            return False

        stdout, stderr, code = self._run_cmd(
            ["apt", "remove", "-y"] + safe_packages
        )
        return code == 0

    def get_orphaned_packages(self) -> List[PackageInfo]:
        stdout, _, code = self._run_cmd(
            ["apt", "list", "--obsolete", "--quiet=2"]
        )
        if code != 0:
            return []

        orphaned = []
        for line in stdout.strip().split('\n'):
            if '/' not in line or line.startswith('listing'):
                continue
            name = line.split('/')[0]
            orphaned.append(PackageInfo(
                name=name,
                version="",
                size=0,
                description="",
                is_installed=True
            ))

        return orphaned

    def autoremove(self) -> bool:
        stdout, stderr, code = self._run_cmd(["apt", "autoremove", "-y"])
        return code == 0
