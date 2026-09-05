"""High level safety guards around destructive operations.

These helpers encode the "Safety First" rules shared by every adapter:

1. dry-run first (:meth:`simulate_removal`) so the blacklist can veto the
   plan before anything touches the system;
2. record a recovery point before bulk removals when a tool is available;
3. only then execute the real removal.
"""

from typing import Dict, List, Optional, Sequence

from . import recovery as recovery_mod
from .base.adapter import PackageManagerAdapter
from .operations import Operation
from .privileges import is_elevated, request_elevation

SAFETY_HOLD_SECONDS = 5


def ensure_elevation(argv: Optional[Sequence[str]] = None) -> Dict[str, object]:
    """Make sure the process is elevated before a privileged operation.

    Returns ``elevated: True`` straight away when already running with full
    rights, otherwise tries to relaunch through UAC/polkit/osascript.
    """
    if is_elevated():
        return {"elevated": True, "requested": False}
    ok = request_elevation(argv)
    return {"elevated": ok, "requested": True}


def _recovery_step(create_recovery: bool, require_recovery: bool) -> Optional[Dict[str, object]]:
    if not create_recovery:
        return None
    point = recovery_mod.create_recovery_point(recovery_mod.RECOVERY_HOLD_COMMENT)
    if require_recovery and not point.get("success"):
        return {"created": False, "blocked": True}
    return {"created": bool(point.get("success")), "blocked": False}


def safe_bulk_removal(
    adapter: PackageManagerAdapter,
    package_names: Sequence[str],
    *,
    create_recovery: bool = True,
    require_recovery: bool = False,
    operation: Optional[Operation] = None,
) -> Dict[str, object]:
    """Run the full guarded pipeline for a bulk removal.

    The removal is skipped entirely when the dry-run plan contains packages
    from the blacklist or (when ``require_recovery``) no recovery point could
    be recorded.
    """
    result: Dict[str, object] = {
        "blocked": [],
        "recovery": None,
        "removed": False,
        "aborted": False,
    }

    plan = adapter.simulate_removal(list(package_names))
    result["blocked"] = list(plan.blocked_packages)
    if plan.blocked_packages:
        result["message"] = (
            "Blocked by safety blacklist: {}".format(", ".join(plan.blocked_packages))
        )
        return result

    if operation is not None and operation.is_cancelled:
        result["aborted"] = True
        result["message"] = "Operation aborted before removal"
        return result

    recovery_step = _recovery_step(create_recovery, require_recovery)
    result["recovery"] = recovery_step
    if recovery_step is not None and recovery_step.get("blocked"):
        result["message"] = "No recovery point available; removal aborted"
        return result

    safe_names = [pkg.name for pkg in plan.packages]
    if not safe_names:
        result["message"] = "Nothing to remove"
        return result

    result["removed"] = bool(adapter.remove_packages(safe_names))
    result["message"] = (
        "Removed {} packages".format(len(safe_names))
        if result["removed"]
        else "Removal failed"
    )
    return result


def safe_autoremove(
    adapter: PackageManagerAdapter,
    *,
    create_recovery: bool = True,
    require_recovery: bool = False,
    operation: Optional[Operation] = None,
) -> Dict[str, object]:
    """Guarded orphan cleanup: recovery point first, then ``autoremove``."""
    result: Dict[str, object] = {
        "orphans": [],
        "recovery": None,
        "removed": False,
        "aborted": False,
    }

    orphans = adapter.get_orphaned_packages()
    result["orphans"] = [pkg.name for pkg in orphans]
    if not orphans:
        result["message"] = "No orphaned packages"
        return result

    if operation is not None and operation.is_cancelled:
        result["aborted"] = True
        result["message"] = "Operation aborted before autoremove"
        return result

    recovery_step = _recovery_step(create_recovery, require_recovery)
    result["recovery"] = recovery_step
    if recovery_step is not None and recovery_step.get("blocked"):
        result["message"] = "No recovery point available; autoremove aborted"
        return result

    result["removed"] = bool(adapter.autoremove())
    result["message"] = (
        "Removed {} orphaned packages".format(len(orphans))
        if result["removed"]
        else "Autoremove failed"
    )
    return result


__all__ = [
    "SAFETY_HOLD_SECONDS",
    "ensure_elevation",
    "safe_autoremove",
    "safe_bulk_removal",
]
