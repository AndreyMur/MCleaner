"""Managed process execution with cancellation and timeouts.

Long running package-manager commands must never hang the UI. Every command
runs through :func:`run_operation` which:

* kills the child when the shared :class:`Operation` is cancelled
  (e.g. the user pressed "Abort");
* kills the child when a configurable deadline is exceeded;
* reports whether the run completed, was aborted or timed out.
"""

import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Optional, Sequence


@dataclass
class OperationResult:
    success: bool = False
    aborted: bool = False
    timed_out: bool = False
    message: str = ""
    output: str = ""
    error: str = ""


class Operation:
    """Cooperative cancellation token shared between the UI and the worker."""

    def __init__(self, label: str = "operation"):
        self.label = label
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled.is_set()


def _terminate(proc: subprocess.Popen) -> None:
    try:
        proc.terminate()
    except Exception:
        pass
    try:
        proc.kill()
    except Exception:
        pass
    try:
        proc.wait()
    except Exception:
        pass


def run_operation(
    command: Sequence[str],
    operation: Optional[Operation] = None,
    timeout: float = 120.0,
    poll_interval: float = 0.1,
) -> OperationResult:
    """Run ``command`` honouring cancellation and ``timeout`` (seconds)."""
    op = operation if operation is not None else Operation()
    if not command:
        return OperationResult(message="Empty command")

    try:
        proc = subprocess.Popen(
            list(command),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return OperationResult(
            message="Failed to start {}: {}".format(command[0], exc),
            error=str(exc),
        )

    deadline = time.monotonic() + timeout
    while proc.poll() is None:
        if op.is_cancelled:
            _terminate(proc)
            return OperationResult(
                aborted=True, message="Operation aborted"
            )
        if time.monotonic() >= deadline:
            _terminate(proc)
            return OperationResult(
                timed_out=True,
                message="Operation timed out after {:.0f}s".format(timeout),
            )
        time.sleep(poll_interval)

    try:
        stdout, stderr = proc.communicate()
    except (OSError, subprocess.SubprocessError) as exc:
        return OperationResult(
            message="Failed to read command output: {}".format(exc),
            error=str(exc),
        )

    return OperationResult(
        success=proc.returncode == 0,
        message="Completed" if proc.returncode == 0 else
                "Failed with exit code {}".format(proc.returncode),
        output=stdout or "",
        error=stderr or "",
    )


def run_command(
    command: Sequence[str],
    operation: Optional[Operation] = None,
    timeout: float = 120.0,
) -> str:
    """Small helper that returns combined output or raises on failure."""
    result = run_operation(command, operation=operation, timeout=timeout)
    if not result.success:
        detail = result.error.strip() or result.message
        raise RuntimeError(detail)
    return (result.output or "") + (result.error or "")


__all__ = ["Operation", "OperationResult", "run_operation", "run_command"]
