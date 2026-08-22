"""Bounded, watchdog-guarded subprocess execution shared by the CLI clients.

A model CLI can hang; every call therefore runs under an explicit timeout. On a
timeout (or a failed exit) the process is killed and the call is reissued once,
then the layer proceeds fail-closed by raising — the pipeline records the gap
rather than fabricating the missing side. The low-level runner is injectable so
the watchdog logic is unit-tested without spawning real processes.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Sequence
from typing import Protocol

import structlog
from pydantic import BaseModel, ConfigDict

from fundamentals.thesis.client import ThesisClientError, ThesisClientTimeoutError

_LOGGER = structlog.get_logger("fundamentals.thesis.subprocess")

# Only the tail of a failing process's stderr is surfaced in the error message.
_STDERR_TAIL_CHARS = 2000


class SubprocessResult(BaseModel):
    """Captured output of a completed subprocess call."""

    model_config = ConfigDict(frozen=True)

    stdout: str
    stderr: str
    returncode: int
    duration_seconds: float


class _LowLevelRun(Protocol):
    """The minimal ``subprocess.run`` surface the watchdog depends on."""

    def __call__(
        self, cmd: Sequence[str], *, timeout: float, stdin_devnull: bool
    ) -> subprocess.CompletedProcess[str]: ...


class CommandRunner(Protocol):
    """The runner surface a client depends on (satisfied by ``run_with_watchdog``)."""

    def __call__(
        self,
        cmd: Sequence[str],
        *,
        timeout_seconds: int,
        retries: int,
        stdin_devnull: bool,
    ) -> SubprocessResult: ...


def _default_run(
    cmd: Sequence[str], *, timeout: float, stdin_devnull: bool
) -> subprocess.CompletedProcess[str]:
    """Run a command, capturing text output, with stdin optionally closed.

    Closing stdin (``</dev/null``) is required for Codex, which otherwise hangs
    waiting on an interactive stream (known bug).
    """
    # argv is a fixed list built from config (never a shell string); shell=False.
    stdin = subprocess.DEVNULL if stdin_devnull else None
    return subprocess.run(
        list(cmd),
        capture_output=True,
        text=True,
        timeout=timeout,
        stdin=stdin,
        check=False,
    )


def run_with_watchdog(
    cmd: Sequence[str],
    *,
    timeout_seconds: int,
    retries: int,
    stdin_devnull: bool = True,
    run: _LowLevelRun = _default_run,
) -> SubprocessResult:
    """Run ``cmd`` under a timeout, killing and reissuing once before failing closed.

    Returns the captured output on a zero exit. Raises :class:`ThesisClientTimeoutError`
    if every attempt timed out, or :class:`ThesisClientError` on a non-zero exit
    or a launch failure. ``retries`` is the number of *extra* attempts after the
    first (so ``retries=1`` means at most two attempts).
    """
    if not cmd:
        raise ThesisClientError("empty command")
    attempts = max(1, retries + 1)
    last_timeout = False
    last_detail = ""
    for attempt in range(1, attempts + 1):
        start = time.monotonic()
        try:
            completed = run(cmd, timeout=float(timeout_seconds), stdin_devnull=stdin_devnull)
        except subprocess.TimeoutExpired:
            last_timeout = True
            last_detail = f"timed out after {timeout_seconds}s"
            _LOGGER.warning(
                "model_call_timeout", executable=cmd[0], attempt=attempt, attempts=attempts
            )
            continue
        except OSError as error:
            raise ThesisClientError(f"failed to launch {cmd[0]!r}: {error}") from error
        if completed.returncode != 0:
            last_timeout = False
            tail = (completed.stderr or "").strip()[-_STDERR_TAIL_CHARS:]
            last_detail = f"exited {completed.returncode}: {tail}"
            _LOGGER.warning(
                "model_call_nonzero_exit",
                executable=cmd[0],
                attempt=attempt,
                returncode=completed.returncode,
            )
            continue
        return SubprocessResult(
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            returncode=0,
            duration_seconds=time.monotonic() - start,
        )
    message = f"{cmd[0]} {last_detail} after {attempts} attempt(s)"
    if last_timeout:
        raise ThesisClientTimeoutError(message)
    raise ThesisClientError(message)
