import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import List

from ..base.adapter import PackageManagerAdapter, PackageInfo, RemovalPlan


SYSTEM_PACKAGES = {
    # Windows core
    "windows", "windows10", "windows11", "windows-sdk",
    "microsoft-windows-terminal", "windows-terminal",
    "explorer", "file-explorer",
    # Kernel / system
    "microsoft-windows-nt-kernel",
    "microsoft-windows-installer", "windows-installer",
    # Security
    "windows-defender", "microsoft-defender",
    "microsoft-security-essentials",
    "windows-security", "security-health",
    # System critical
    "microsoft-edge", "edge",
    "internet-explorer", "ie",
    "microsoft.net-framework", "dotnet", "dotnet-runtime",
    "microsoft-windows-app-runtime",
    "microsoft-powerapps", "powerapps",
    # System tools
    "microsoft-powershell", "powershell", "powershell-core",
    "microsoft-windows-cmd", "cmd",
    "microsoft-windows-regedit", "regedit",
    "microsoft-windows-taskmgr", "task-manager",
    # Drivers and services
    "microsoft-windows-driver",
    "microsoft-windows-service",
    "microsoft-windows-update", "windows-update",
    # UWP system apps
    "microsoft.windowsstore", "microsoft.store",
    "microsoft.windows.shellexperiencehost",
    "microsoft.windows.startmenuexperiencehost",
    # Common critical MS components
    "microsoft.vclibs", "microsoft.vc++redist", "vc-redist",
    "microsoft.msix", "msix",
    "microsoft.ui.xaml", "microsoft.windowsappsdk",
    # Core infrastructure
    "microsoft-sysinternals",
    "nvidia-driver", "amd-driver", "intel-driver",
}

COLUMN_SPLIT_RE = re.compile(r"\s{2,}")


class WingetAdapter(PackageManagerAdapter):
    def __init__(self):
        self._cache_size: int = 0

    def _run_cmd(self, cmd: List[str]) -> tuple[str, str, int]:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                encoding="utf-8",
                errors="replace",
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
        name_lower = package_name.lower()
        if name_lower in SYSTEM_PACKAGES:
            return True
        return any(
            prefix in name_lower
            for prefix in ("microsoft.", "microsoft-windows")
        )

    def _get_winget_path(self) -> str:
        for candidate in (
            "winget",
            str(Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WindowsApps" / "winget.exe"),
        ):
            if candidate and self._command_exists(candidate):
                return candidate
        return "winget"

    def _command_exists(self, cmd: str) -> bool:
        return shutil.which(cmd) is not None

    @staticmethod
    def _is_header_or_separator(line: str) -> bool:
        if any(header in line for header in ("Name", "Id", "Version", "Available", "Source", "──", "───", "─")):
            return True
        return False

    @staticmethod
    def _split_columns(line: str) -> List[str]:
        return [part.strip() for part in COLUMN_SPLIT_RE.split(line) if part.strip()]

    def get_installed_packages(self) -> List[PackageInfo]:
        winget = self._get_winget_path()
        stdout, stderr, code = self._run_cmd(
            [winget, "list", "--accept-source-agreements", "--disable-interactivity", "--no-color"]
        )
        if code != 0:
            return []

        packages = []
        for line in stdout.strip().split("\n"):
            if not line.strip() or self._is_header_or_separator(line):
                continue
            columns = self._split_columns(line)
            if len(columns) < 2:
                continue
            if "@" in line and "\\" not in line:
                continue

            name = columns[0]
            version = columns[2] if len(columns) > 2 else ""

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
            Path(os.environ.get("TEMP", "")) / "WinGet",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Temp" / "WinGet",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Packages" / "Microsoft.DesktopAppInstaller_8wekyb3d8bbwe" / "LocalState" / "Microsoft.Winget.Source",
        ]

        total_size = 0
        for cache_dir in cache_dirs:
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
        cache_dirs = [
            Path(os.environ.get("TEMP", "")) / "WinGet",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Temp" / "WinGet",
        ]

        success = True
        for cache_dir in cache_dirs:
            if cache_dir.exists():
                try:
                    shutil.rmtree(cache_dir)
                except OSError:
                    success = False

        if success:
            self._cache_size = 0
        return success

    def simulate_removal(self, package_names: List[str]) -> RemovalPlan:
        blocked = [p for p in package_names if self._is_system_package(p)]
        safe_packages = [p for p in package_names if not self._is_system_package(p)]

        packages_info = []
        for name in safe_packages:
            packages_info.append(PackageInfo(
                name=name,
                version="",
                size=0,
                description="",
                is_installed=True,
            ))

        return RemovalPlan(
            packages=packages_info,
            total_size=0,
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

        winget = self._get_winget_path()
        for name in safe_packages:
            stdout, stderr, code = self._run_cmd(
                [winget, "uninstall", "--id", name, "--silent",
                 "--disable-interactivity", "--accept-source-agreements"]
            )
            if code != 0:
                return False
        return True

    def get_orphaned_packages(self) -> List[PackageInfo]:
        stdout, stderr, code = self._run_cmd(
            [self._get_winget_path(), "list", "--orphans",
             "--accept-source-agreements", "--disable-interactivity", "--no-color"]
        )
        if code != 0:
            return []

        orphaned = []
        for line in stdout.strip().split("\n"):
            if not line.strip() or self._is_header_or_separator(line):
                continue
            columns = self._split_columns(line)
            if len(columns) < 2:
                continue
            if "@" in line and "\\" not in line:
                continue
            orphaned.append(PackageInfo(
                name=columns[0],
                version=columns[2] if len(columns) > 2 else "",
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
