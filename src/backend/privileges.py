"""Seamless privilege elevation helpers (UAC / polkit / osascript).

The backend tries to run unprivileged for as long as possible and only
requests elevated rights at the moment a privileged command is about to
run. On Linux this is done transparently through ``pkexec`` (polkit), on
macOS through ``osascript`` and on Windows by relaunching the target
through PowerShell ``Start-Process -Verb RunAs`` (UAC prompt).
"""

import os
import platform
import shlex
import shutil
import subprocess
import sys
from typing import Dict, List, Optional, Sequence


def current_platform() -> str:
    """Return a short identifier for the current operating system."""
    return platform.system().lower()


def command_available(name: str) -> bool:
    """Return True when the given executable is available on PATH."""
    return bool(shutil.which(name))


def _is_elevated_windows() -> bool:
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _is_elevated_unix() -> bool:
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False


def is_elevated() -> bool:
    """Return True when the current process already runs with full rights."""
    if os.name == "nt":
        return _is_elevated_windows()
    return _is_elevated_unix()


def privilege_status() -> Dict[str, object]:
    """Describe the current privilege state of the process."""
    elevated = is_elevated()
    if os.name == "nt":
        method = "admin" if elevated else "user"
        user = os.environ.get("USERNAME", "")
    else:
        method = "root" if elevated else "user"
        user = os.environ.get("USER", "")
    return {
        "os": current_platform(),
        "elevated": elevated,
        "method": method,
        "user": user,
    }


def _ps_quote(value: str) -> str:
    """Quote a value for use inside a single-quoted PowerShell string."""
    return "'" + value.replace("'", "''") + "'"


def _wrap_linux(command: Sequence[str]) -> List[str]:
    if command_available("pkexec"):
        return ["pkexec"] + list(command)
    return list(command)


def _wrap_windows(command: Sequence[str]) -> List[str]:
    if not command:
        return []
    if len(command) == 1:
        script = (
            "Start-Process -FilePath {exe} -Verb RunAs -Wait".format(
                exe=_ps_quote(command[0])
            )
        )
    else:
        script = (
            "Start-Process -FilePath {exe} -ArgumentList {args} "
            "-Verb RunAs -Wait".format(
                exe=_ps_quote(command[0]),
                args=",".join(_ps_quote(part) for part in command[1:]),
            )
        )
    return ["powershell", "-NoProfile", "-Command", script]


def _wrap_darwin(command: Sequence[str]) -> List[str]:
    if not command:
        return []
    inner = " ".join(_ps_quote(part) for part in command)
    script = "do shell script {} with administrator privileges".format(
        _ps_quote(inner)
    )
    return ["osascript", "-e", script]


def elevation_prefix(command: Sequence[str]) -> List[str]:
    """Return ``command`` wrapped with the least intrusive elevation layer.

    When the process is already elevated the command is returned unchanged.
    Otherwise the platform appropriate wrapper is prepended so the OS prompt
    (polkit, UAC or OSAuth) is shown only when the command actually runs.
    """
    if is_elevated():
        return list(command)

    system = current_platform()
    if system == "linux":
        return _wrap_linux(command)
    if system == "windows":
        return _wrap_windows(command)
    if system == "darwin":
        return _wrap_darwin(command)
    return list(command)


def _run_elevated(command: Sequence[str]) -> bool:
    try:
        result = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def request_elevation(argv: Optional[Sequence[str]] = None) -> bool:
    """Request elevated rights by relaunching the current command.

    ``argv`` defaults to the current process arguments. When the process is
    already elevated this is a no-op that returns True.
    """
    if is_elevated():
        return True

    if argv is None:
        argv = list(sys.argv)
    argv = list(argv)
    if not argv:
        return False

    system = current_platform()
    if system == "linux":
        if command_available("pkexec"):
            return _run_elevated(["pkexec"] + argv)
    elif system == "windows":
        if len(argv) == 1:
            script = "Start-Process -FilePath {exe} -Verb RunAs".format(
                exe=_ps_quote(argv[0])
            )
        else:
            script = (
                "Start-Process -FilePath {exe} -ArgumentList {args} "
                "-Verb RunAs".format(
                    exe=_ps_quote(argv[0]),
                    args=",".join(_ps_quote(part) for part in argv[1:]),
                )
            )
        return _run_elevated(["powershell", "-NoProfile", "-Command", script])
    elif system == "darwin":
        inner = " ".join(_ps_quote(part) for part in argv)
        script = "do shell script {} with administrator privileges".format(
            _ps_quote(inner)
        )
        return _run_elevated(["osascript", "-e", script])
    return False


def describe_elevation_wrapper(command: Sequence[str]) -> str:
    """Human readable rendering of how a command will be elevated."""
    wrapped = elevation_prefix(command)
    return " ".join(shlex.quote(part) for part in wrapped)


__all__ = [
    "command_available",
    "current_platform",
    "elevation_prefix",
    "is_elevated",
    "privilege_status",
    "request_elevation",
]
