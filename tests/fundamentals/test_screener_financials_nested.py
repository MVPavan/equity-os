"""Level-3 schedules: the schedules a level-2 sub-row advertises for itself.

What these pin is that depth is *earned*, not assumed. A level-3 family exists
only because a level-2 body said so in its own ``isExpandable`` call, is fetched
only at the URL that call names, is summed only against the level-2 sub-row it
expands — never the page row two levels up — and is proven only for the two
shapes a live capture registered. Everything else is retained and marked
unverified rather than absorbed.

The page, the bodies and the transport seam live in
:mod:`screener_financials_support`, which is the same seam the level-2 modules
use. Every figure here is invented; only the shapes follow the captures.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from screener_financials_support import (
    NESTED_MATERIAL_COST,
    NESTED_TRADE_RECEIVABLES,
    _family,
    _nested,
    _nested_bodies,
    _nested_call,
    _nested_page,
    _nested_read,
    _serve,
    _watchlist,
)

from fundamentals.api.cli import main
from fundamentals.api.screener_cli_dispatch import EXIT_REFUSED
from fundamentals.api.screener_financials_cli import META_FILENAME, SCHEDULES_DIRNAME
from fundamentals.ingest.screener_financials_models import (
    ReconciliationStatus,
    ScheduleStrategy,
    Section,
)

_SCREENER_ORIGIN = "https://www.screener.in"
_MATERIAL_COST_URL = (
    "https://www.screener.in/api/company/991001/schedules/"
    "?parent=Material+Cost+%25&section=profit-loss&consolidated="
)
_TRADE_RECEIVABLES_KEY = "balance-sheet/Other Assets/Trade receivables"


def _schedule_urls(requested: list[str]) -> list[str]:
    """Every schedule request of one run, in the order it was made."""
    return [url for url in requested if "/schedules/" in url]


# --------------------------------------------------------------------------
# L3-01: discovery is body-driven, and the call must describe its own sub-row.
# --------------------------------------------------------------------------


def test_a_sub_row_that_advertises_a_schedule_is_fetched_once_at_the_url_it_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # L3-01
    """The nested call is the whole address, so the request must be built from it.

    ``Material Cost %`` carries a character that changes meaning in a query
    string: unencoded, ``%`` truncates the parent and the API answers for a
    different row. And basis is still selected by the presence of the
    ``consolidated`` key, never its value, at level 3 exactly as at level 2.
    """
    _, requested = _nested_read(monkeypatch)
    schedules = _schedule_urls(requested)
    assert [url for url in schedules if "parent=Material" in url] == [_MATERIAL_COST_URL]
    assert all(url.endswith("&consolidated=") for url in schedules)


@pytest.mark.parametrize(
    ("call", "forbidden"),
    [
        (_nested_call(NESTED_MATERIAL_COST, Section.BALANCE_SHEET), "parent=Material+Cost"),
        (_nested_call("Raw material cost", Section.PROFIT_LOSS), "parent=Raw+material"),
    ],
)
def test_a_nested_call_that_does_not_describe_its_own_sub_row_is_refused_unfetched(
    monkeypatch: pytest.MonkeyPatch, call: str, forbidden: str
) -> None:
    # L3-01
    """A call naming another label or another section is not this row's schedule.

    Following it anyway would attach the level-2 sub-row's cells to a body that
    describes something else, and the reconciliation would then compare two
    unrelated rows. The body is evidence of drift, so the mismatch is recorded
    as a refusal — but no request is spent on it.
    """
    overrides = {
        ("profit-loss", "Expenses"): {
            NESTED_MATERIAL_COST: {"Mar 2025": "82%", "Mar 2026": "78%", "isExpandable": call}
        }
    }
    run, requested = _nested_read(monkeypatch, overrides=overrides)
    assert not any(forbidden in url for url in _schedule_urls(requested))
    refusals = [
        failure for failure in run.artifact.failures if failure.refusal == "ScheduleBodyError"
    ]
    assert len(refusals) == 1
    assert NESTED_MATERIAL_COST in f"{refusals[0].parent} {refusals[0].detail}"
    # No body exists, so there is no hash of one; recording a hash of nothing
    # would imply evidence that was never fetched. The address is still recorded
    # in full, because "which request was not made" is the whole of the report.
    assert refusals[0].body_sha256 is None
    assert refusals[0].expands == "Expenses"
    assert refusals[0].url == _MATERIAL_COST_URL
    assert refusals[0].document_id == _MATERIAL_COST_URL.removeprefix(_SCREENER_ORIGIN)


# --------------------------------------------------------------------------
# L3-03: strategy is registry-only, so novelty fails closed.
# --------------------------------------------------------------------------


def test_the_registered_trade_receivables_family_is_summed_and_reconciled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # L3-03
    """The one nested shape a capture proved summable, held to its parent sub-row.

    Three signed amount rows — over 6m, under 6m and a negative provision — add
    up to the level-2 ``Trade receivables`` cell. Nothing else about the run is
    unverified, so the artifact may claim ``verified`` only if this family was
    actually proven too.
    """
    run, _ = _nested_read(monkeypatch)
    nested = _nested(_family(run, Section.BALANCE_SHEET, "Other Assets"), NESTED_TRADE_RECEIVABLES)
    assert nested.strategy is ScheduleStrategy.FLAT_SUM
    assert nested.reconciliation is ReconciliationStatus.RECONCILED
    assert [sub_row.label for sub_row in nested.sub_rows] == [
        "Receivables over 6m",
        "Receivables under 6m",
        "Prov for Doubtful",
    ]
    assert run.artifact.metadata.verified is True
    assert run.artifact.metadata.schedule_families_unverified == ()


def test_a_nested_body_carrying_a_label_outside_its_signature_is_unverified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # L3-03
    """A registered signature covers a recorded shape, not a family name forever.

    An unknown row means the family may have changed what it decomposes into,
    and inheriting the registered treatment would hide that — even when the
    numbers still add up, as they do here.
    """
    overrides = {
        ("balance-sheet", NESTED_TRADE_RECEIVABLES): {
            "Receivables over 6m": {"Mar 2025": "120", "Mar 2026": "130"},
            "Receivables under 6m": {"Mar 2025": "400", "Mar 2026": "450"},
            "Prov for Doubtful": {"Mar 2025": "-20", "Mar 2026": "-20"},
            "Receivables disputed": {"Mar 2025": "0", "Mar 2026": "0"},
        }
    }
    run, _ = _nested_read(monkeypatch, overrides=overrides)
    nested = _nested(_family(run, Section.BALANCE_SHEET, "Other Assets"), NESTED_TRADE_RECEIVABLES)
    assert nested.reconciliation is ReconciliationStatus.UNVERIFIED
    assert "Receivables disputed" in nested.reconciliation_note
    assert _TRADE_RECEIVABLES_KEY in run.artifact.metadata.schedule_families_unverified
    assert run.artifact.metadata.verified is False


def test_an_unregistered_advertised_family_is_fetched_and_retained_but_unverified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # L3-03
    """Only two nested families were ever observed, so a third is drift to capture.

    It is still fetched and still retained — the body is the evidence of what
    changed — but no registry entry says what its rows mean, so the gate cannot
    run and the family must not be claimed as proven. Its sums here are correct,
    which is exactly why inference would wave it through.
    """
    overrides = {
        ("balance-sheet", "Other Assets"): {
            NESTED_TRADE_RECEIVABLES: {
                "Mar 2025": "500",
                "Mar 2026": "560",
                "isExpandable": _nested_call(NESTED_TRADE_RECEIVABLES, Section.BALANCE_SHEET),
            },
            "Inventories": {
                "Mar 2025": "400",
                "Mar 2026": "440",
                "isExpandable": _nested_call("Inventories", Section.BALANCE_SHEET),
            },
        },
        ("balance-sheet", "Inventories"): {
            "Stores and spares": {"Mar 2025": "250", "Mar 2026": "270"},
            "Finished goods": {"Mar 2025": "150", "Mar 2026": "170"},
        },
    }
    run, requested = _nested_read(monkeypatch, overrides=overrides)
    nested = _nested(_family(run, Section.BALANCE_SHEET, "Other Assets"), "Inventories")
    assert any("parent=Inventories" in url for url in _schedule_urls(requested))
    assert "Inventories" in [document.parent for document in run.schedule_documents]
    assert nested.strategy is ScheduleStrategy.UNVERIFIED
    assert nested.reconciliation is ReconciliationStatus.UNVERIFIED
    assert "balance-sheet/Other Assets/Inventories" in (
        run.artifact.metadata.schedule_families_unverified
    )


# --------------------------------------------------------------------------
# L3-04: the reference is the level-2 sub-row, and a level-3 miss is local.
# --------------------------------------------------------------------------


def test_a_nested_flat_sum_is_reconciled_against_the_level_2_sub_row_not_the_page_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # L3-04
    """The row a nested family decomposes is its parent sub-row, two levels down.

    The fixture makes the two candidates disagree on purpose: the page's ``Other
    Assets`` row is 900/1,000 while its ``Trade receivables`` sub-row is 500/560.
    A gate pointed at the page row would compare 500 against 900 and refuse
    correct data; only the recorded comparison values say which one it used.
    """
    run, _ = _nested_read(monkeypatch)
    nested = _nested(_family(run, Section.BALANCE_SHEET, "Other Assets"), NESTED_TRADE_RECEIVABLES)
    assert [comparison.period_label for comparison in nested.comparisons] == [
        "Mar 2025",
        "Mar 2026",
    ]
    assert [str(comparison.page_row_value) for comparison in nested.comparisons] == ["500", "560"]
    assert [str(comparison.sub_row_total) for comparison in nested.comparisons] == ["500", "560"]
    assert nested.reconciliation is ReconciliationStatus.RECONCILED


def test_a_nested_flat_sum_admits_the_rounding_band_of_its_three_addends(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # L3-04
    """Screener rounds each level-3 row and the level-2 cell to whole crores separately.

    Three addends and one total give a worst case of two crores, and the live
    capture lands exactly there: TITAN's Mar 2015 receivables miss by one. The
    same band as level 2 — this is one gate, not a second one with its own
    fudge factor.
    """
    overrides = {
        ("balance-sheet", NESTED_TRADE_RECEIVABLES): {
            "Receivables over 6m": {"Mar 2025": "119", "Mar 2026": "130"},
            "Receivables under 6m": {"Mar 2025": "400", "Mar 2026": "450"},
            "Prov for Doubtful": {"Mar 2025": "-20", "Mar 2026": "-20"},
        }
    }
    run, _ = _nested_read(monkeypatch, overrides=overrides)
    nested = _nested(_family(run, Section.BALANCE_SHEET, "Other Assets"), NESTED_TRADE_RECEIVABLES)
    assert nested.reconciliation is ReconciliationStatus.RECONCILED
    assert [str(comparison.difference) for comparison in nested.comparisons] == ["-1", "0"]
    assert run.artifact.failures == ()


def test_a_nested_reconciliation_failure_is_recorded_and_the_sweep_carries_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # L3-04
    """A level-3 miss under a reconciled parent is a nested-shape signal, not a basis one.

    At level 2 a failed gate stops the run, because a wrong basis makes every
    family of the run wrong the same way. Here the parent already reconciled
    against the page on the same basis, so the disagreement is local to this
    breakdown — stopping would discard the families still to come for nothing.
    """
    overrides = {
        ("balance-sheet", NESTED_TRADE_RECEIVABLES): {
            "Receivables over 6m": {"Mar 2025": "125", "Mar 2026": "130"},
            "Receivables under 6m": {"Mar 2025": "400", "Mar 2026": "450"},
            "Prov for Doubtful": {"Mar 2025": "-20", "Mar 2026": "-20"},
        }
    }
    run, requested = _nested_read(monkeypatch, overrides=overrides)
    metadata = run.artifact.metadata
    assert [failure.refusal for failure in run.artifact.failures] == ["ScheduleReconciliationError"]
    assert _family(run, Section.BALANCE_SHEET, "Other Assets").reconciliation is (
        ReconciliationStatus.RECONCILED
    )
    assert "balance-sheet/Borrowings" in metadata.schedule_families_fetched
    assert any("parent=Borrowings" in url for url in _schedule_urls(requested))
    assert metadata.complete is True
    assert metadata.verified is False


# --------------------------------------------------------------------------
# L3-05: percent of sales is an identity, not a sum.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw_material_cost", "reconciled"),
    [("130", True), ("123", False)],
)
def test_material_cost_percent_is_checked_as_a_ratio_of_the_page_sales_row(
    monkeypatch: pytest.MonkeyPatch, raw_material_cost: str, reconciled: bool
) -> None:
    # L3-05
    """The level-2 cell is a percent of sales; the level-3 rows are crore amounts.

    Summing them against their parent would compare 127 crore with 82 percent.
    The real relation is ``100 x (raw material + inventory change) / Sales``, and
    its band is the rounding of both sides propagated through the division —
    a flat half-point would refuse a correct 81.41 against a displayed 82.
    """
    overrides = {
        ("profit-loss", NESTED_MATERIAL_COST): {
            "Raw material cost": {"Mar 2025": raw_material_cost, "Mar 2026": "128"},
            "Change in inventory": {"Mar 2025": "-3", "Mar 2026": "-3"},
        }
    }
    run, _ = _nested_read(monkeypatch, overrides=overrides)
    if not reconciled:
        assert [failure.refusal for failure in run.artifact.failures] == [
            "ScheduleReconciliationError"
        ]
        return
    nested = _nested(_family(run, Section.PROFIT_LOSS, "Expenses"), NESTED_MATERIAL_COST)
    assert nested.strategy is ScheduleStrategy.PERCENT_OF_SALES
    assert nested.reconciliation is ReconciliationStatus.RECONCILED
    assert [str(comparison.page_row_value) for comparison in nested.comparisons] == ["82", "78"]
    ratios = [comparison.sub_row_total for comparison in nested.comparisons]
    assert [
        abs(ratio - expected) < Decimal("0.01")
        for ratio, expected in zip(ratios, (Decimal("81.41"), Decimal("78.13")), strict=True)
    ] == [True, True]
    assert "Sales" in nested.reconciliation_note


def test_a_percent_of_sales_family_with_no_sales_page_row_is_not_comparable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # L3-05
    """No denominator means the identity was never checked, which is not a refusal.

    Banks and NBFCs publish ``Revenue`` where this contract looks for ``Sales``,
    and no such company is on the watchlist — so an absent row is an unproven
    family to record, not evidence that the numbers are wrong.
    """
    run, _ = _nested_read(monkeypatch, sales_expandable=False)
    nested = _nested(_family(run, Section.PROFIT_LOSS, "Expenses"), NESTED_MATERIAL_COST)
    assert nested.strategy is ScheduleStrategy.PERCENT_OF_SALES
    assert nested.reconciliation is ReconciliationStatus.NOT_COMPARABLE
    assert nested.comparisons == ()
    assert run.artifact.failures == ()
    assert run.artifact.metadata.verified is False


# --------------------------------------------------------------------------
# L3-06, L3-07, L3-08: empty bodies, the depth bound, and where a family sits.
# --------------------------------------------------------------------------


def test_an_empty_nested_response_is_unverified_rather_than_a_verified_absence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # L3-06
    """``{}`` is also what a parent with no schedule at all returns.

    Captured live as the control: requesting a level-2 sub-row that carries no
    ``isExpandable`` answers ``{}`` with HTTP 200. So an empty body cannot mean
    "this breakdown is genuinely empty" — it is indistinguishable from an
    expired cookie, a soft block, or a row that never had a schedule.
    """
    overrides: dict[tuple[str, str], dict[str, object]] = {
        ("balance-sheet", NESTED_TRADE_RECEIVABLES): {}
    }
    run, _ = _nested_read(monkeypatch, overrides=overrides)
    nested = _nested(_family(run, Section.BALANCE_SHEET, "Other Assets"), NESTED_TRADE_RECEIVABLES)
    assert nested.sub_rows == ()
    assert nested.reconciliation is ReconciliationStatus.UNVERIFIED_EMPTY
    assert run.artifact.metadata.verified is False


def test_a_nested_body_carrying_a_period_the_page_does_not_is_unverified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # L3-08
    """A level-3 window wider than the page's is not a longer history, it is drift.

    Every capture returned exactly the parent family's window, so a column the
    page header does not carry cannot be aligned to a period — and a family
    reconciled on the columns that *did* align would be claiming the response
    describes the same periods as the page when part of it demonstrably does
    not. The reading is kept by name rather than dropped, and the family stays
    unverified all the way out to the exit code.
    """
    overrides = {
        ("balance-sheet", NESTED_TRADE_RECEIVABLES): {
            "Receivables over 6m": {"Mar 2024": "115", "Mar 2025": "120", "Mar 2026": "130"},
            "Receivables under 6m": {"Mar 2025": "400", "Mar 2026": "450"},
            "Prov for Doubtful": {"Mar 2025": "-20", "Mar 2026": "-20"},
        }
    }
    run, _ = _nested_read(monkeypatch, overrides=overrides)
    nested = _nested(_family(run, Section.BALANCE_SHEET, "Other Assets"), NESTED_TRADE_RECEIVABLES)
    assert nested.unaligned_periods == ("Mar 2024",)
    assert nested.reconciliation is ReconciliationStatus.UNVERIFIED
    assert nested.comparisons == ()
    assert run.artifact.metadata.verified is False
    assert _TRADE_RECEIVABLES_KEY in run.artifact.metadata.schedule_families_unverified

    _serve(monkeypatch, page=_nested_page(), bodies=_nested_bodies(overrides))
    exit_code = main(
        ["screener-financials", "--stock", "FIXTURECO", "--section", "balance-sheet"]
        + ["--out", str(tmp_path / "out"), "--config", str(_watchlist(tmp_path))]
    )
    assert exit_code == EXIT_REFUSED


def test_a_level_3_sub_row_that_is_itself_expandable_is_recorded_and_not_followed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # L3-07
    """Depth stops at three, and the row that would have gone deeper is named.

    No level-4 body was ever observed, so following one would be acquisition on
    speculation against a rate-limited source. Dropping the call instead would
    erase the only evidence that the site went deeper than this contract does.
    """
    overrides = {
        ("balance-sheet", NESTED_TRADE_RECEIVABLES): {
            "Receivables over 6m": {
                "Mar 2025": "120",
                "Mar 2026": "130",
                "isExpandable": _nested_call("Receivables over 6m", Section.BALANCE_SHEET),
            },
            "Receivables under 6m": {"Mar 2025": "400", "Mar 2026": "450"},
            "Prov for Doubtful": {"Mar 2025": "-20", "Mar 2026": "-20"},
        }
    }
    run, requested = _nested_read(monkeypatch, overrides=overrides)
    nested = _nested(_family(run, Section.BALANCE_SHEET, "Other Assets"), NESTED_TRADE_RECEIVABLES)
    deeper = next(row for row in nested.sub_rows if row.label == "Receivables over 6m")
    assert "showSchedule" in (deeper.nested_schedule_call or "")
    assert nested.deeper_not_acquired == ("Receivables over 6m",)
    assert not any("parent=Receivables+over+6m" in url for url in _schedule_urls(requested))
    assert "Receivables over 6m" not in [document.parent for document in run.schedule_documents]


def test_a_nested_family_hangs_under_the_level_2_family_whose_sub_row_it_expands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # L3-08
    """Position in the artifact is the statement of what a family decomposes.

    A nested family read as a peer of its parent would say "``Trade
    receivables`` is a breakdown of the balance sheet", and its numbers would be
    compared against the wrong row by anyone reading the artifact later.
    """
    run, _ = _nested_read(monkeypatch)
    parent = _family(run, Section.BALANCE_SHEET, "Other Assets")
    assert parent.expands is None
    assert _family(run, Section.BALANCE_SHEET, "Borrowings").nested == ()
    assert [child.parent for child in parent.nested] == [NESTED_TRADE_RECEIVABLES]
    assert parent.nested[0].expands == "Other Assets"
    assert parent.nested[0].section is Section.BALANCE_SHEET
    assert _TRADE_RECEIVABLES_KEY in run.artifact.metadata.schedule_families_fetched


# --------------------------------------------------------------------------
# L3-09, L3-10, L3-11: what the command writes, prints, and does when cut off.
# --------------------------------------------------------------------------


def test_the_command_retains_each_nested_body_under_a_three_part_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # L3-09
    """A nested body named by section and parent alone would collide with its parent's.

    ``profit-loss__expenses.raw.json`` is already taken by the level-2 response,
    and a no-clobber write would refuse the level-3 one — losing exactly the
    evidence the artifact's deepest claim rests on. The summary keys it the same
    three-part way so the file and the line name one thing.
    """
    _serve(monkeypatch, page=_nested_page(), bodies=_nested_bodies())
    out_dir = tmp_path / "out"
    exit_code = main(
        ["screener-financials", "--stock", "FIXTURECO", "--section", "profit-loss"]
        + ["--out", str(out_dir), "--config", str(_watchlist(tmp_path))]
    )
    assert exit_code == 0
    retained = out_dir / SCHEDULES_DIRNAME / "profit-loss__expenses__material-cost.raw.json"
    assert retained.read_bytes() == _nested_bodies()[("profit-loss", NESTED_MATERIAL_COST)]
    summary = capsys.readouterr().out
    assert "profit-loss/Expenses/Material Cost %\tpercent_of_sales\treconciled" in summary


def test_an_unverified_nested_family_makes_the_command_exit_non_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # L3-10
    """The exit code has to reach the deepest claim the artifact makes.

    A run whose level-2 families all reconcile but whose level-3 breakdown is an
    unrecognised shape is not a clean acquisition, and a watchlist loop reading
    only the exit status would otherwise mark it done.
    """
    overrides = {
        ("profit-loss", NESTED_MATERIAL_COST): {
            "Raw material cost": {"Mar 2025": "130", "Mar 2026": "128"},
            "Change in inventory": {"Mar 2025": "-3", "Mar 2026": "-3"},
            "Packing material cost": {"Mar 2025": "0", "Mar 2026": "0"},
        }
    }
    _serve(monkeypatch, page=_nested_page(), bodies=_nested_bodies(overrides))
    out_dir = tmp_path / "out"
    exit_code = main(
        ["screener-financials", "--stock", "FIXTURECO", "--section", "profit-loss"]
        + ["--out", str(out_dir), "--config", str(_watchlist(tmp_path))]
    )
    metadata = json.loads((out_dir / META_FILENAME).read_text(encoding="utf-8"))
    assert exit_code == EXIT_REFUSED
    assert metadata["verified"] is False
    assert "profit-loss/Expenses/Material Cost %" in metadata["schedule_families_unverified"]


def test_a_rate_limit_on_a_nested_request_stops_the_sweep_and_keeps_what_was_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # L3-11
    """Level-3 fetches spend the same 429 budget, so they can end the run mid-family.

    A nested fetch is not free depth: it happens inside the sweep loop, right
    after its parent is admitted. When the limit lands on one, everything
    already read stays and what is missing is named — the artifact must not read
    as a complete acquisition that simply found less.
    """
    run, requested = _nested_read(monkeypatch, rate_limit_after=4)
    metadata = run.artifact.metadata
    assert len(_schedule_urls(requested)) == 5
    assert metadata.complete is False
    assert "rate-limited" in (metadata.incomplete_reason or "")
    assert "balance-sheet/Other Assets" in metadata.schedule_families_fetched
    assert [document.parent for document in run.schedule_documents] == [
        "Sales",
        "Expenses",
        NESTED_MATERIAL_COST,
        "Other Assets",
    ]
