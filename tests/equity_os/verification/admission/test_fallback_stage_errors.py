"""VENDOR-1 P1 phase-review finding 12: a recoverable fallback stage error after persistent
writes still ends the group with a terminal outcome. A retained results listing that does not
parse, and a rerun that does not resolve, store ``FILING_UNRESOLVED`` with each original trigger
and the stage's reason; any other error still propagates. SYNTHETIC: each case's edit of what is
served, or of the rerun."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from test_fallback import (
    FULL,
    INTEGRATED_URL,
    LEGACY_URL,
    OUTCOMES,
    Q2,
    _associates_omitted,
    _Fallback,
    _served,
)

from equity_os.contracts.measurement.canonical import Basis
from equity_os.contracts.verification.vendor_first import FallbackFailure
from equity_os.verification.admission import fallback
from equity_os.verification.comparison.engine_attempts import RunResolutionError
from equity_os.verification.comparison.run_models import RunExitStatus

pytestmark = [pytest.mark.pg, pytest.mark.retained]

_RERUN = "SYNTHETIC rerun resolution failure"


def _refuse_rerun(*_: Any, **__: Any) -> Any:
    """A rerun whose resolution refuses."""
    raise RunResolutionError(_RERUN)


def _broken_rerun(*_: Any, **__: Any) -> Any:
    """A rerun failing for a reason that is not a stage outcome."""
    raise KeyError(_RERUN)


@pytest.mark.parametrize(
    ("case", "reason", "fetched"),
    [
        ("json", FallbackFailure.LISTING_UNPARSED, FULL[:2]),
        ("date", FallbackFailure.LISTING_UNPARSED, FULL[:2]),
        ("rerun", FallbackFailure.RERUN_UNRESOLVED, FULL),
    ],
)
def test_stage_error_ends_unresolved(
    pg_db: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    case: str,
    reason: FallbackFailure,
    fetched: tuple[str, ...],
) -> None:
    """The group's outcome is FILING_UNRESOLVED with no rerun; each original trigger keeps its
    refusal with the stage's reason."""
    served = _served()
    issuer = _associates_omitted(served, tmp_path)  # admits when nothing fails
    if case == "json":
        served[LEGACY_URL] = b"{not json"
    elif case == "date":
        served[INTEGRATED_URL] = served[INTEGRATED_URL].replace(b"30-SEP-2025", b"2025-09-30", 1)
    else:
        monkeypatch.setattr(fallback, "execute_run", _refuse_rerun)
    with _Fallback(pg_db, tmp_path, monkeypatch, Basis.CONSOLIDATED) as run:
        assert run.main(served, issuer) == 4
        ((stored_run, period, _, outcome, rerun, cells),) = run.read(OUTCOMES)
    lines = capsys.readouterr().out.splitlines()
    assert [line.split("\t")[2] for line in lines if line.startswith("fetch\t")] == list(fetched)
    assert (stored_run, period, outcome, rerun) == (run.run_id, Q2, "FILING_UNRESOLVED", None)
    assert cells.keys() == run.triggers.keys()
    for row_id, (disposition, detail) in cells.items():
        assert disposition == run.triggers[row_id]
        assert detail == reason


def test_other_errors_propagate(
    pg_db: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An error that is not a source-parse or resolution failure escapes the fallback as a
    command failure; it is not turned into an outcome."""
    served = _served()
    issuer = _associates_omitted(served, tmp_path)
    monkeypatch.setattr(fallback, "execute_run", _broken_rerun)
    with _Fallback(pg_db, tmp_path, monkeypatch, Basis.CONSOLIDATED) as run:
        assert run.main(served, issuer) == RunExitStatus.FAILURE
        assert not run.read(OUTCOMES)
