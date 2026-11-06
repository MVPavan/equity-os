"""Coverage's expected set does not shrink with the interpretations it measures (VENDOR-1 spec
§6.11 #3; phase-review finding 5).

The expected set is both vendors' pinned entries over the vendor columns the store evidences,
so a vendor interpretation that is lost, invalid or never made leaves its key expected and the
gap shows as missing. Stored evidence is immutable, so the loss is replayed: the same run's
inputs without interpretations, and its rows without the vendor sides such a run publishes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from test_compare_vendor_runs import CONFIG, LAURUS
from test_eligibility import _compare, _issuer, pool  # noqa: F401  (``pool`` is a fixture)

from equity_os.contracts.sourcing.source_catalog import TIJORI_PAGE
from equity_os.verification.admission import eligibility
from equity_os.verification.admission.eligibility import coverage
from equity_os.verification.comparison.run import load_results, replay_inputs
from equity_os.verification.comparison.run_models import ResultRow


@pytest.mark.pg
@pytest.mark.retained
def test_lost_vendor_interpretations_leave_the_denominator_and_show_as_missing(
    pg_db: Any,
    pool: Any,  # noqa: F811
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One vendor side lost on one expected key: same denominator, one missing. Every vendor
    interpretation lost: same denominator, all missing, never ``expected = 0, missing = 0``."""
    run_id = _compare(_issuer(LAURUS, pg_db, pool, tmp_path, CONFIG), capsys)
    base = coverage(pool, run_id, config_root=CONFIG)
    assert base.expected > 0 and base.three_way == base.expected and base.missing == 0

    inputs, request, config = replay_inputs(run_id, pool=pool, config_root=CONFIG)
    bare = inputs.model_copy(update={"interpretations": ()})
    monkeypatch.setattr(eligibility, "replay_inputs", lambda *_, **__: (bare, request, config))
    rows = load_results(run_id, pool=pool)
    revenue = "revenue_from_operations|2024-10-01.."

    def published(lost: str | None) -> None:
        """Coverage reads rows whose vendor sides ``lost`` names are gone (any vendor: None)."""
        changed = tuple(
            row if lost is not None and not row.row_id.startswith(revenue) else _without(row, lost)
            for row in rows
        )
        monkeypatch.setattr(eligibility, "load_results", lambda *_, **__: changed)

    published(TIJORI_PAGE[0])
    one = coverage(pool, run_id, config_root=CONFIG)
    assert (one.expected, one.three_way, one.missing) == (base.expected, base.expected - 1, 1)

    published(None)
    every = coverage(pool, run_id, config_root=CONFIG)
    assert (every.expected, every.three_way, every.missing) == (base.expected, 0, base.expected)


def _without(row: ResultRow, source: str | None) -> ResultRow:
    """A row without the named vendor's side, or without every vendor side."""
    kept = tuple(
        value
        for value in row.source_values
        if value.source_id is None or (source is not None and value.source_id != source)
    )
    return row.model_copy(update={"source_values": kept})
