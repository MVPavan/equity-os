"""D8 stage D8.3 (Task 6): the R12 point check over stored runs, replay and marked evidence.

Runs come from ``test_shareholding_vendor`` (retained gen-2 generations, ``eqos_test_*``
databases, socket guard on). Expected point values are sums of the run's stored first-party
values, never vendor readings; Task 7's manifest freezes them.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pg_support import PgTestDatabase
from test_shareholding_compare import CONFIG_ROOT
from test_shareholding_filing import _seed
from test_shareholding_vendor import (
    APAR,
    BD,
    CATEGORY,
    SCREENER,
    TIJORI,
    UPSTOX,
    D,
    _ingest_marked,
    _marked_config,
    _printed,
    _results,
)
from test_shareholding_vendor import guarded as guarded  # the fixture, re-exported
from test_shareholding_vendor import ingested as ingested  # the fixture, re-exported
from test_shareholding_vendor import runs as runs  # the fixture, re-exported

from equity_os.contracts.measurement.canonical import Representation
from equity_os.contracts.measurement.evidence import Occurrence
from equity_os.contracts.sourcing.source_catalog import SCREENER_SHAREHOLDING
from equity_os.contracts.verification.comparison import PairOutcome, SourceRole
from equity_os.verification.comparison.point_check import (
    NO_PACKAGE,
    PointCheck,
    PointVerdict,
    point_checks,
)
from equity_os.verification.comparison.report import ZERO_LABEL, point_line
from equity_os.verification.comparison.run import ResultRow, load_results, replay_inputs, replay_run
from equity_os.verification.comparison.run_models import RunInput, RunInputDisposition, RunInputKind

# Plan D8 R12 Apar exit table (d8-probe.md §13.5): (vendor side, category or basket) -> labels.
APAR_TABLE = {
    (SCREENER, "sebi_promoter_group"): {D},
    (SCREENER, "non_institutions"): {D, BD},
    (SCREENER, "institutions_foreign"): {D, BD},
    (SCREENER, "institutions_domestic"): {D, BD},
    (TIJORI, "sebi_promoter_group"): {D},
    (TIJORI, "public_shareholding_plus_employee_benefit_trust"): {D, ZERO_LABEL},
    (TIJORI, "institutions_domestic_plus_institutions_foreign"): {D, BD},
    (UPSTOX, "sebi_promoter_group"): {D},
    (UPSTOX, "non_institutions_plus_employee_benefit_trust"): {D, BD, ZERO_LABEL},
    (UPSTOX, "institutions_foreign"): {D, BD},
}


def _checks(
    db: PgTestDatabase, run_id: int, rows: Any = None, root: Path = CONFIG_ROOT
) -> tuple[PointCheck, ...]:
    """The run's point checks over its frozen evidence, on its stored rows or ``rows``."""
    with db.runtime_pool() as pool:
        frozen = replay_inputs(run_id, pool=pool, config_root=root)
        return point_checks(load_results(run_id, pool=pool) if rows is None else rows, *frozen)


def _category(check: PointCheck) -> tuple[str, str]:
    return check.source, dict(check.key.dimensions.pairs)[CATEGORY]


def _labels(check: PointCheck) -> set[str]:
    return set(point_line(check).split("labels=")[1].split(";"))


def _first_party(rows: tuple[ResultRow, ...], category: str) -> Decimal:
    """The stored first-party value of a category at ``TOTAL_SHARES`` (the run's own row)."""
    (value,) = [
        v.value
        for r in rows
        if dict(r.key.dimensions.pairs).get(CATEGORY) == category
        and dict(r.key.dimensions.pairs)["denominator"] == "TOTAL_SHARES"
        for v in r.source_values
        if v.source_role is SourceRole.FIRST_PARTY and v.value is not None
    ]
    return value


@pytest.mark.pg
@pytest.mark.retained
def test_point_check_over_apar_and_eternal(
    runs: dict[str, int], ingested: tuple[PgTestDatabase, Path, dict[str, int]]
) -> None:
    """R12: every Apar table cell prints its check with exactly its labels, the C2-less baskets
    summing stored first-party values with C2 taken as zero; ETERNAL files C2, so no Z, and its
    printed Upstox promoter value checks against A = 0 (D, Z) with no A row, occurrence or
    interpretation. The report prints the same lines as replay's rows over the frozen evidence."""
    db = ingested[0]
    for symbol in (APAR, "ETERNAL"):
        run_id = runs[symbol]
        rows = _results(db, run_id)
        checks = _checks(db, run_id)
        with db.runtime_pool() as pool:
            replayed = _checks(db, run_id, replay_run(run_id, pool=pool, config_root=CONFIG_ROOT))
        printed = [line for line in _printed(run_id) if line.startswith("point\t")]
        assert printed == [point_line(c) for c in checks] == [point_line(c) for c in replayed]
        by_cell = {_category(check): check for check in checks}
        baskets = {
            (TIJORI, "public_shareholding_plus_employee_benefit_trust"): "public_shareholding",
            (UPSTOX, "non_institutions_plus_employee_benefit_trust"): "non_institutions",
        }
        for cell, filed in baskets.items():
            check = by_cell[cell]
            trust = Decimal(0) if symbol == APAR else _first_party(rows, "employee_benefit_trust")
            assert check.point_value == _first_party(rows, filed) + trust
            assert check.zero_members == (("employee_benefit_trust",) if symbol == APAR else ())
        if symbol == APAR:
            assert {cell: _labels(by_cell[cell]) for cell in APAR_TABLE} == APAR_TABLE
            assert {by_cell[cell].outcome for cell in APAR_TABLE} == {PairOutcome.NOT_COMPARABLE}
            continue
        promoter = by_cell[(UPSTOX, "sebi_promoter_group")]
        assert (promoter.point_value, promoter.zero_members) == (0, ("sebi_promoter_group",))
        assert promoter.outcome is None and _labels(promoter) == {D, ZERO_LABEL}
        assert promoter.verdict is PointVerdict.POINT_EQUAL  # Upstox prints 0
        # No other promoter candidate: Screener has no row and Tijori prints a dash (§13.5).
        assert [c for c in checks if _category(c)[1] == "sebi_promoter_group"] == [promoter]
        assert not [
            r for r in rows if dict(r.key.dimensions.pairs).get(CATEGORY) == "sebi_promoter_group"
        ]
        with db.runtime_pool() as pool:
            frozen = replay_inputs(run_id, pool=pool, config_root=CONFIG_ROOT)[0]
        promoters = "ShareholdingOfPromoterAndPromoterGroupMember"
        assert not [
            o
            for o in frozen.occurrences
            if promoters in json.dumps(o.native_context.get("dimensions"))
        ]
        assert not [
            i
            for i in frozen.interpretations
            if i.key
            and dict(i.key.dimensions.pairs).get(CATEGORY) == "sebi_promoter_group"
            and i.representation.value == "XBRL"
        ]


@pytest.mark.pg
@pytest.mark.retained
def test_point_check_one_unit_flips_the_verdict_not_the_outcome(
    runs: dict[str, int], ingested: tuple[PgTestDatabase, Path, dict[str, int]]
) -> None:
    """A vendor value marked one unit up in its last printed decimal turns ``POINT_EQUAL`` into
    ``POINT_CHECK``; the formal outcome stays ``NOT_COMPARABLE``. Without a selected package
    every candidate still prints, refused."""
    db = ingested[0]
    run_id = runs[APAR]
    with db.runtime_pool() as pool:
        inputs, request, config = replay_inputs(run_id, pool=pool, config_root=CONFIG_ROOT)
        rows = load_results(run_id, pool=pool)
    checks = point_checks(rows, inputs, request, config)
    cell = (SCREENER, "sebi_promoter_group")
    (equal,) = [c for c in checks if _category(c) == cell]
    assert equal.verdict is PointVerdict.POINT_EQUAL
    readings = {i.interpretation_id: i for i in inputs.interpretations}
    (side,) = [
        v
        for r in rows
        if r.key == equal.key
        for v in r.source_values
        if v.surface == SCREENER_SHAREHOLDING[1]
    ]
    occurrence_id = readings[side.interpretation_id].occurrence_id

    def bumped(item: Occurrence) -> Occurrence:
        if item.occurrence_id != occurrence_id:
            return item
        text = str(item.raw_value_text)
        number = text.rstrip("%")
        places = len(number.partition(".")[2])
        value = Decimal(number) + Decimal(1).scaleb(-places)
        return item.model_copy(
            update={"raw_value_text": f"{value:.{places}f}" + text[len(number) :]}
        )

    marked = inputs.model_copy(update={"occurrences": tuple(map(bumped, inputs.occurrences))})
    (flipped,) = [c for c in point_checks(rows, marked, request, config) if _category(c) == cell]
    assert flipped.verdict is PointVerdict.POINT_CHECK
    assert flipped.outcome is equal.outcome is PairOutcome.NOT_COMPARABLE
    absent = inputs.model_copy(
        update={
            "packages": (),
            "inputs": tuple(i for i in inputs.inputs if i.kind.value != "PACKAGE"),
        }
    )
    refused = point_checks(rows, absent, request, config)
    assert [_category(c) for c in refused] == [_category(c) for c in checks]
    assert {(c.verdict, c.reason) for c in refused} == {(PointVerdict.POINT_REFUSED, NO_PACKAGE)}


@pytest.mark.pg
@pytest.mark.retained
def test_point_check_refuses_rather_than_zero(
    guarded: PgTestDatabase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A marked set maps Screener ``Others`` to C (ETERNAL files C counts but no C percentage)
    and drops B2's first-party entries (B2 filed, uninterpreted): both print ``POINT_REFUSED``
    with the category named, never zero."""
    drop = {
        "shp.institutions_foreign.total_shares": None,
        "shp.institutions_foreign.voting_rights": None,
    }
    to_c = {
        "dimension_members": {CATEGORY: "non_promoter_non_public", "denominator": "TOTAL_SHARES"}
    }
    root = _marked_config(tmp_path / "config", {**drop, "screener.shp.others": to_c})
    expected = {
        "ETERNAL": ((SCREENER, "non_promoter_non_public"), "non_promoter_non_public is filed"),
        APAR: ((SCREENER, "institutions_foreign"), "institutions_foreign has no first-party"),
    }
    for symbol, (cell, reason) in expected.items():
        _seed(guarded, symbol)
        _, run_id = _ingest_marked(monkeypatch, root, tmp_path / "snapshots", symbol)
        (check,) = [c for c in _checks(guarded, run_id, root=root) if _category(c) == cell]
        assert check.verdict is PointVerdict.POINT_REFUSED and check.point_value is None
        assert check.reason is not None and reason in check.reason
        assert point_line(check) in _printed(run_id, root)


@pytest.mark.pg
@pytest.mark.retained
def test_point_check_refuses_zero_while_an_unmapped_descendant_is_filed(
    runs: dict[str, int], ingested: tuple[PgTestDatabase, Path, dict[str, int]]
) -> None:
    """R12: with Apar's B1 aggregate removed from the filing and its stored value, the filed
    (unmapped) mutual-funds subcategory still bears B1, so B1 is never taken as zero."""
    db = ingested[0]
    with db.runtime_pool() as pool:
        inputs, request, config = replay_inputs(runs[APAR], pool=pool, config_root=CONFIG_ROOT)
        rows = load_results(runs[APAR], pool=pool)
    filed = [
        o for o in inputs.occurrences if "InstitutionsDomesticMember" not in str(o.native_context)
    ]
    assert any("MutualFundsOrUTIMember" in str(o.native_context) for o in filed)
    unstored = [
        r for r in rows if dict(r.key.dimensions.pairs).get(CATEGORY) != "institutions_domestic"
    ]
    marked = inputs.model_copy(update={"occurrences": tuple(filed)})
    cell = (SCREENER, "institutions_domestic")
    (check,) = [c for c in point_checks(unstored, marked, request, config) if _category(c) == cell]
    assert check.verdict is PointVerdict.POINT_REFUSED and check.zero_members == ()
    assert check.reason is not None and "institutions_domestic is filed" in check.reason


@pytest.mark.pg
@pytest.mark.retained
def test_point_check_takes_each_key_s_own_instant_package(
    runs: dict[str, int], ingested: tuple[PgTestDatabase, Path, dict[str, int]]
) -> None:
    """R12: a second selected package at another instant, listed first and filing ETERNAL's
    absent promoter category, changes no check: each key reads its own instant's package, so
    the promoter zero and the cited package stand."""
    db = ingested[0]
    with db.runtime_pool() as pool:
        inputs, request, config = replay_inputs(runs["ETERNAL"], pool=pool, config_root=CONFIG_ROOT)
        rows = load_results(runs["ETERNAL"], pool=pool)
    checks = point_checks(rows, inputs, request, config)
    (package,) = inputs.packages
    member = package.members[Representation.XBRL]
    capture = member.capture.model_copy(update={"capture_ref_id": 10**9})
    other = package.model_copy(
        update={
            "package_id": 10**9,
            "reporting_period_end": date(2026, 3, 31),
            "members": {Representation.XBRL: member.model_copy(update={"capture": capture})},
        }
    )
    (attempt,) = [a for a in inputs.attempts if a.capture == member.capture]
    category = next(
        o for o in inputs.occurrences if "CategoryOfShareholdersAxis" in str(o.native_context)
    )
    axis = next(
        a
        for a, _ in category.native_context["dimensions"]
        if a.endswith("CategoryOfShareholdersAxis")
    )
    promoter = category.model_copy(
        update={
            "capture": capture,
            "native_context": category.native_context
            | {"dimensions": [[axis, "in-bse-shp:ShareholdingOfPromoterAndPromoterGroupMember"]]},
        }
    )
    marked = inputs.model_copy(
        update={
            "packages": (other, package),
            "attempts": (*inputs.attempts, attempt.model_copy(update={"capture": capture})),
            "occurrences": (*inputs.occurrences, promoter),
            "inputs": (
                RunInput(
                    kind=RunInputKind.PACKAGE,
                    ref_id=10**9,
                    disposition=RunInputDisposition.SELECTED,
                ),
                *inputs.inputs,
            ),
        }
    )
    assert point_checks(rows, marked, request, config) == checks
    zero = next(c for c in checks if _category(c) == (UPSTOX, "sebi_promoter_group"))
    assert zero.package_id == package.package_id and zero.zero_members == ("sebi_promoter_group",)
