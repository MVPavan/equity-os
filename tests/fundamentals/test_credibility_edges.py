"""Plan-required credibility refusals and reasons the sealed tests reach no other way (S2)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from credibility_support import (
    chain,
    claim,
    cred_module,
    entry,
    registry,
    row,
    unresolved,
    write_targets,
)

from fundamentals.contracts.role import FactRole
from fundamentals.ledger.run_traces import RunDraftError


def _bound_open_window(root: Path, measures: Any) -> Any:
    """``bind_credibility`` of an FY28 target whose window is open at February 29."""
    cred = cred_module()
    held = claim(quote="growth of 10% in FY28")
    prep = cred.prepare(
        (held,),
        cred.Record(),
        cred.Record(),
        write_targets(root, entry("A", held, "FY28")),
        period="FY28_Q4",
        period_end=date(2028, 2, 29),
        month=3,
        filed_at={},
        actual_blobs=frozenset(),
    )
    update = SimpleNamespace(
        period_start="2027-12-01",
        period_end="2028-02-29",
        facts=[SimpleNamespace(role=FactRole.PROFIT_BEFORE_TAX, sources=[None])],
        comparatives=[],
    )
    versions = SimpleNamespace(dictionary="", mapping_set="", normalisation_policy="")
    return cred.bind_credibility(
        None, update, prep, (), entity_id=1, versions=versions, registry=measures
    )


def test_a_leap_day_period_end_has_no_comparator_window(tmp_path: Path) -> None:
    """Task 2: February 29 has no day a year earlier, so an open window states that, unscored."""
    built = _bound_open_window(tmp_path, registry())
    reason = "a leap day has no comparator"
    assert built.unavailable == {"cred.revenue_growth.consolidated.FY28.ytd": reason}
    unresolved(row(built.body, "revenue_growth.consolidated.FY28"), reason)


@pytest.mark.parametrize(
    ("measures", "reason"),
    [({}, "no filed measure"), (registry(interim=False), "no interim rule")],
    ids=["unregistered", "no-interim-rule"],
)
def test_a_window_without_a_usable_measure_binds_nothing(
    tmp_path: Path, measures: Any, reason: str
) -> None:
    """P7, Task 3: only a registered measure with a rule for this window may compute an actual."""
    built = _bound_open_window(tmp_path, measures)
    assert built.actuals == () and built.exact == {} and built.unavailable == {}
    unresolved(row(built.body, "revenue_growth.consolidated.FY28"), reason)


def test_a_retired_line_outside_its_block_refuses(tmp_path: Path) -> None:
    """Task 2: a retired line above the header could carry a pin the block never checks."""
    a = claim(page=1)
    b = claim(low="12", page=2, quote="growth of 12% in FY26")
    section = chain(a, b, write_targets(tmp_path, entry("A", a), entry("B", b)))
    stray = f"- retired Z sha256 {'0' * 64} successor A\n"
    body = section.body.replace(
        "{{e:computed}} Retired entries:", stray + "{{e:computed}} Retired entries:"
    )
    with pytest.raises(RunDraftError, match="does not parse"):
        cred_module().read_record(body, section.claims)
