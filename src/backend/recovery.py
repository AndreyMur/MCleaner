"""Recovery point integration (Timeshift / System Restore / Time Machine).

Before bulk removals the cleaner asks the platform tool to record the
current state of the system:

* Linux  -> ``timeshift --create`` (requires polkit elevation);
* Windows-> ``Checkpoint-Computer`` (System Restore, requires UAC token);
* macOS  -> ``tmutil localsnapshot`` (Time Machine local snapshots).
"""

import subprocess
from typing import Dict, Optional, Sequence

from . import privileges

LINUX_TOOL = "timeshift"
DARWIN_TOOL = "tmutil"
WINDOWS_TOOL = "System Restore"

RECOVERY_HOLD_COMMENT = "MCleaner: before removing packages"

_CHECKPOINT_SCRIPT = (
    "Checkpoint-Computer -Description {comment} "
    "-RestorePointType MODIFY_SETTINGS"
)


def _powershell(script: str, timeout: float = 60.0) -> Optional[str]:
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return result.stdout
        return None
    except (OSError, subprocess.SubprocessError):
        return None


def _windows_restore_available() -> bool:
    probe = "try { $null = Get-ComputerRestorePoint -ErrorAction Stop; 'ok' } catch { 'no' }"
    output = _powershell(probe)
    return bool(output and "ok" in output.strip().lower())


def recovery_tool_status() -> Dict[str, object]:
    """Describe which recovery tool is available on the current platform."""
    system = privileges.current_platform()

    if system == "linux":
        present = privileges.command_available(LINUX_TOOL)
        return {
            "available": present,
            "tool": "Timeshift" if present else None,
            "command": (
                "timeshift --create --comments \"{}\" --yes".format(
                    RECOVERY_HOLD_COMMENT
                )
                if present
                else None
            ),
        }

    if system == "darwin":
        present = privileges.command_available(DARWIN_TOOL)
        return {
            "available": present,
            "tool": "Time Machine" if present else None,
            "command": "tmutil localsnapshot" if present else None,
        }

    if system == "windows":
        present = _windows_restore_available()
        return {
            "available": present,
            "tool": WINDOWS_TOOL if present else None,
            "command": (
                _CHECKPOINT_SCRIPT.format(comment="'MCleaner: safety'")
                if present
                else None
            ),
        }

    return {"available": False, "tool": None, "command": None}


def _create_command(comment: str) -> Sequence[str]:
    system = privileges.current_platform()
    if system == "linux":
        return ["timeshift", "--create", "--comments", comment, "--yes"]
    if system == "darwin":
        return ["tmutil", "localsnapshot", comment]
    if system == "windows":
        script = _CHECKPOINT_SCRIPT.format(comment=privileges._ps_quote(comment))
        return ["powershell", "-NoProfile", "-NonInteractive", "-Command", script]
    return []


def create_recovery_point(
    comment: str = RECOVERY_HOLD_COMMENT,
    timeout: float = 600.0,
) -> Dict[str, object]:
    """Create a recovery point before a destructive bulk operation.

    Returns a dict with ``success``, ``tool`` and ``message`` keys.
    Creation is best effort: when no tool is available the result reports a
    clear failure message instead of raising.
    """
    status = recovery_tool_status()
    if not status.get("available"):
        return {
            "success": False,
            "tool": None,
            "created": False,
            "message": (
                "No recovery tool detected "
                "(Timeshift / System Restore / Time Machine)."
            ),
        }

    command = _create_command(comment)
    wrapped = privileges.elevation_prefix(command)

    try:
        result = subprocess.run(
            list(wrapped),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        success = result.returncode == 0
        return {
            "success": success,
            "tool": status.get("tool"),
            "created": success,
            "message": (
                "Recovery point created"
                if success
                else "Recovery point creation failed"
            ),
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "tool": status.get("tool"),
            "created": False,
            "message": "Recovery point creation timed out",
        }
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "success": False,
            "tool": status.get("tool"),
            "created": False,
            "message": str(exc),
        }


__all__ = [
    "RECOVERY_HOLD_COMMENT",
    "create_recovery_point",
    "recovery_tool_status",
]
