"""Stage 1 end-to-end (D1b.6): every manifest run and fixture against the frozen oracle.

Each run goes through the real pipeline (first-party ingest, vendor ingest, ``execute_run``,
queue publication, replay) in an isolated ``eqos_test_*`` database and must match the manifest
exactly; each marked fixture applies its recorded alteration and checks its recorded outcome.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import stage1_provenance
import yaml
from retained_support import (
    MarkedEdit,
    PdfRedaction,
    marked_pdf,
)
from stage1_e2e_support import (
    BLOCKS,
    CONFIG,
    FY25_XBRL,
    MANIFEST,
    RUNS,
    SCREENER,
    SNAPSHOTS,
    UNITS,
    VERSIONS,
    Outcome,
    Stage,
    _name,
    cli,
    cli_run,
    fixture_side,
    full_run,
    fy25,
    manifest_lines,
    mark,
    stored,
)
from stage1_provenance import provenance
from test_compare_run_rules import FINANCE_PLUS_ONE_CRORE
from test_compare_vendor_runs import _key as vendor_key
from test_compare_vendor_runs import _qualified as qualified
from test_compare_vendor_runs import _side as no_value
from test_frozen_manifests import source

from fundamentals.compare.definitions import load_definition_set
from fundamentals.compare.policy import load_comparison_policy
from fundamentals.compare.resolve_loader import RunLoader
from fundamentals.compare.routing import route_pair_draft, route_status_draft
from fundamentals.compare.run_models import SourceRef
from fundamentals.compare.tables import SourceQualifiedSide, corroboration_result
from fundamentals.compare.vendor_sides import VendorRow, VendorSides, internal_conflict
from fundamentals.contracts.acquisition_outcome import OutcomeCode
from fundamentals.contracts.canonical import ApplicabilityStatus, Basis, Representation
from fundamentals.contracts.comparison import (
    CalculationState,
    CorroborationStatus,
    ExtractionStatus,
    PairKind,
    ReasonCode,
    SourceRole,
    SourceState,
)
from fundamentals.contracts.evidence import Interpretation, RevisionCause
from fundamentals.contracts.evidence_tier import EvidenceTier
from fundamentals.contracts.measurement_key import PeriodInterval
from fundamentals.contracts.review_queue import QueueSeverity
from fundamentals.contracts.snapshot import CAPTURE_ID_TIME_FORMAT
from fundamentals.store.snapshot_store import SnapshotStore


@pytest.fixture
def stage(pg_db: Any, tmp_path: Path, request: pytest.FixtureRequest) -> Iterator[Stage]:
    with pg_db.runtime_pool() as pool:
        yield Stage(pg_db, pool, tmp_path, RUNS[request.param])


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("stage", list(RUNS), indirect=True)
def test_run_matches_manifest(stage: Stage, monkeypatch: pytest.MonkeyPatch) -> None:
    outcome = full_run(stage)
    lines = manifest_lines(outcome) + provenance(outcome)
    assert not lines, f"{len(lines)} differences:\n" + "\n".join(lines[:60])
    stage1_provenance.check_mutations_caught(outcome)
    # Provenance is compared, not only numbers: relabelled selections and rules are caught.
    ids = [
        value.interpretation_id
        for row in outcome.rows
        for value in row.source_values
        if value.source_role is SourceRole.FIRST_PARTY and value.interpretation_id
    ]
    relabel = dict(zip(ids, ids[1:] + ids[:1], strict=True))
    relabelled = tuple(
        row.model_copy(
            update={
                "source_values": tuple(
                    value.model_copy(
                        update={"interpretation_id": relabel.get(value.interpretation_id)}
                    )
                    if value.source_role is SourceRole.FIRST_PARTY and value.interpretation_id
                    else value
                    for value in row.source_values
                ),
            }
        )
        for row in outcome.rows
    )
    lines = provenance(outcome, relabelled)
    assert not ids or (lines and not any(" rule:" in line for line in lines))
    ruled = tuple(
        row.model_copy(update={"applicability_rule_id": "relabelled"}) for row in outcome.rows
    )
    assert any(" rule:" in line for line in provenance(outcome, ruled))
    if not ids:
        return  # NETWEB runs without a first-party package: no selection to mutate
    # An unknown capture fails rather than skipping its locator check.
    with monkeypatch.context() as patch:
        patch.setattr(stage1_provenance, "SOURCES", {})
        assert any("no manifest source" in line for line in provenance(outcome))
    # An implicit (default) EQUIVALENCE_UNPROVEN tier is compared too: promotion is a difference.
    read = stage.repository.get_interpretations
    unproven = EvidenceTier.EQUIVALENCE_UNPROVEN
    demonstrated = EvidenceTier.EQUIVALENCE_DEMONSTRATED
    monkeypatch.setattr(
        stage.repository,
        "get_interpretations",
        lambda ids: tuple(
            item.model_copy(update={"tier": demonstrated}) if item.tier is unproven else item
            for item in read(ids)
        ),
    )
    assert any(f"want {unproven} got {demonstrated}" in line for line in provenance(outcome))


# --- marked fixtures (header.fixtures) -------------------------------------------------------

PAT, REVENUE = "profit_continuing_after_tax|Q|-|REPORTED", "revenue_from_operations|Q|-|REPORTED"
TIJ, SCR = "tijori/financials", "/".join(SCREENER)
TIJORI_FAILED = "20260905T000000.000000Z-000000000000"  # E12: no such capture, a failed attempt
UPSTOX_FAILED = "20261014T000000.000000Z-000000000000"  # H7c
# E12 / E13 c2: Tijori UNAVAILABLE, no fallback; Screener still corroborates revenue.
TIJORI_UNAVAILABLE: dict[str, dict[str, Any]] = {
    PAT: {f"sides.{TIJ}.s": "UNAVAILABLE", "cor.status": "UNAVAILABLE"},
    REVENUE: {
        f"sides.{TIJ}.s": "UNAVAILABLE",
        f"pair:xbrl>{SCR}": ("AGREE_UNQUALIFIED", None),
        "cor.status": "AGREES_UNQUALIFIED",
    },
}


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("stage", ["LAURUSLABS-Q3FY25"], indirect=True)
@pytest.mark.parametrize("complete_first", [False, True], ids=["E12", "E13"])
def test_failed_tijori_attempt_makes_the_run_incomplete(
    stage: Stage, complete_first: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    if complete_first:
        assert not manifest_lines(full_run(stage))  # c1: the frozen run
    else:
        stage.first_party()
        stage.vendor(SCR, "LAURUSLABS-SCR")
    failed = stage.vendor(TIJ, "LAURUSLABS-TIJ", TIJORI_FAILED)
    outcome = Outcome(stage)
    assert outcome.check(TIJORI_UNAVAILABLE) == []
    assert (outcome.status, outcome.exit) == ("INCOMPLETE", 4)
    assert outcome.record.manifest.operational_failures == (
        f"{TIJ}\tFAILED\tattempt={failed.attempt.attempt_id}",
    )
    assert cli_run(stage, monkeypatch) == 4


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("stage", ["LAURUSLABS-Q3FY25"], indirect=True)
def test_not_published_tijori_attempt_leaves_filing_only(
    stage: Stage, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E14: a later test-private ``not_offered`` record on the same route, no body."""
    assert not manifest_lines(full_run(stage))
    path = source(MANIFEST, "LAURUSLABS-TIJ")[0].relative_to(SNAPSHOTS).parts
    original = SnapshotStore(SNAPSHOTS).get_capture(*path[:4])
    private, later = stage.tmp_path / "private", original.retrieved_at + timedelta(hours=1)
    capture_id = f"{later.strftime(CAPTURE_ID_TIME_FORMAT)}-nobody"
    SnapshotStore(private).put_capture(
        original.model_copy(
            update={
                "capture_id": capture_id,
                "retrieved_at": later,
                "http_status": 404,
                "media_type": None,
                "body": None,
                "outcome": original.outcome.model_copy(
                    update={"code": OutcomeCode.NOT_OFFERED, "native_value": "TEST_NOT_OFFERED"}
                ),
            }
        ),
        None,
    )
    stage.vendor(TIJ, "LAURUSLABS-TIJ", capture_id, private)
    outcome = Outcome(stage)
    assert (
        outcome.check(
            {
                PAT: {
                    f"sides.{TIJ}.s": "NO_VALUE",
                    f"sides.{TIJ}.why": "NOT_PUBLISHED",
                    "cor.status": "FILING_ONLY",
                },
                REVENUE: {f"sides.{TIJ}.s": "NO_VALUE", "cor.status": "AGREES_UNQUALIFIED"},
            }
        )
        == []
    )
    assert (outcome.status, outcome.exit) == ("COMPLETE", 0)
    assert cli_run(stage, monkeypatch) == 0


UPSTOX = "upstox/income-statement"
UPSTOX_SUMMARY = f"{UPSTOX}:upstox-income-statement-summary-v2"
UPSTOX_ROWS = ("total_income|Q|-|REPORTED", "profit_before_tax_incl_associates|Q|-|REPORTED")


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("stage", ["APARINDS-Q2FY26"], indirect=True)
def test_upstox_never_decides_a_status_or_the_run(stage: Stage) -> None:
    """H7a_3: the frozen Apar Upstox diagnostics change neither status when Upstox is not
    requested. H7c: a later failed Upstox attempt is UNAVAILABLE/FAILED (diagnostic) with no
    fallback and no Upstox pairs; statuses as frozen; COMPLETE, exit as Apar's (3, never 4)."""
    frozen = full_run(stage)

    def statuses(outcome: Outcome) -> dict[str, Any]:
        return {key: (outcome.got[key]["ext"], outcome.got[key]["cor"]) for key in UPSTOX_ROWS}

    others = [flag for flag in stage.run["vendor_flags"] if flag != UPSTOX]
    assert statuses(Outcome(stage, vendors=others)) == statuses(frozen)
    stage.vendor(UPSTOX, "A-UPQ", UPSTOX_FAILED)
    outcome = Outcome(stage)
    for key in UPSTOX_ROWS:
        row = outcome.got[key]
        assert (row["sides"][UPSTOX_SUMMARY]["s"], row["sides"][UPSTOX_SUMMARY]["why"]) == (
            "UNAVAILABLE",
            "FAILED",
        )
        assert [pair for pair in row["pairs"] if UPSTOX_SUMMARY in pair[:2]] == []
    assert statuses(outcome) == statuses(frozen)
    assert (outcome.status, outcome.exit) == ("COMPLETE", frozen.exit) == ("COMPLETE", 3)


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("stage", ["APARINDS-Q2FY26"], indirect=True)
def test_upstox_screener_diagnostic_on_a_shared_key(stage: Stage) -> None:
    """H7b (vendor-sides level, first party NO_VALUE): Apar FY26 revenue, Screener "22,902"
    VALUE, Upstox A-UPY 22902.12 INVALID/PRECISION_UNSUPPORTED; their diagnostic pair is
    NOT_COMPARABLE/PRECISION_UNSUPPORTED, MEDIUM; VENDOR_ONLY with or without Upstox."""
    end = date(2026, 3, 31)
    stage.vendor(SCR, "A-SCR", end=end)
    attempt = stage.vendor(UPSTOX, "A-UPY", end=end).attempt.attempt_id
    key = vendor_key(
        REVENUE.split("|")[0], PeriodInterval.duration(date(2025, 4, 1), end), stage.entity_id
    )

    def sides(vendors: list[str]) -> VendorRow:
        request = stage.request(end, vendors)
        loader = RunLoader(request, stage.repository)
        loader.load()
        return VendorSides(
            loader.inputs(0), request, config=stage.config, traces=stage.repository
        ).row(
            key,
            fiscal_month=3,
            applicability=ApplicabilityStatus.APPLICABLE,
            extraction=ExtractionStatus.NOT_APPLICABLE,
            first_party={
                rep: no_value(key, None) for rep in (Representation.XBRL, Representation.PDF)
            },
        )

    found = sides([SCR, UPSTOX])
    states = {(value.source_id, value.state.value, value.reason) for value in found.values}
    assert states == {
        ("screener-subscriber", "VALUE", None),
        ("upstox", "INVALID", "PRECISION_UNSUPPORTED"),
    }
    (pair,) = [pair for pair in found.pairs if pair.pair_kind is PairKind.DIAGNOSTIC]
    assert (pair.left.source_id, pair.right.source_id) == ("screener-subscriber", "upstox")
    assert (pair.outcome.value, pair.reason) == ("NOT_COMPARABLE", ReasonCode.PRECISION_UNSUPPORTED)
    draft = route_pair_draft(qualified(pair, attempt), key=key)
    assert draft is not None and (draft.severity, draft.diagnostic) == (QueueSeverity.MEDIUM, True)
    assert found.status is sides([SCR]).status is CorroborationStatus.VENDOR_ONLY


LAURUS_PAT_WITHHELD = MarkedEdit(
    label="e7b-pat-withheld",
    find=b'<in-bse-fin:ProfitLossForPeriodFromContinuingOperations contextRef="OneD" unitRef="INR"'
    b' decimals="-7">906100000.00</in-bse-fin:ProfitLossForPeriodFromContinuingOperations>',
    replace=b"",
)
AMBIGUOUS = "INTERPRETATION_AMBIGUOUS"


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("stage", ["LAURUSLABS-Q3FY25"], indirect=True)
@pytest.mark.parametrize("withheld", [False, True], ids=["E7a", "E7b"])
def test_invalid_only_vendor_is_never_filing_only(stage: Stage, withheld: bool) -> None:
    """A second unsuperseded Tijori 'Net Profit' interpretation leaves Tijori its only,
    invalid vendor: NOT_COMPARABLE, never FILING_ONLY or NO_SOURCE, MEDIUM, not trusted."""
    stage.first_party(*([LAURUS_PAT_WITHHELD] if withheld else []))
    stage.vendors()
    tijori_pat = Outcome(stage).interpretation(PAT, TIJ)
    mark(stage, tijori_pat, "E7a second Net Profit")
    outcome = Outcome(stage)
    tijori_side = {f"sides.{TIJ}.s": "INVALID", f"sides.{TIJ}.why": AMBIGUOUS}
    expect: dict[str, Any]
    queue: list[Any]
    if withheld:  # row 4a: no pair, the corroboration status carries the reason
        expect = {"sides.xbrl.s": "NO_VALUE", "cor.status": "NOT_COMPARABLE", "cor.why": AMBIGUOUS}
        queue = [(("on", "corroboration"), ("out", "NOT_COMPARABLE"), ("sev", "MEDIUM"))]
    else:
        expect = {f"pair:xbrl>{TIJ}": ("NOT_COMPARABLE", AMBIGUOUS), "cor.status": "NOT_COMPARABLE"}
        queue = [
            (
                ("a", "xbrl"),
                ("b", TIJ),
                ("on", "pair"),
                ("out", "NOT_COMPARABLE"),
                ("sev", "MEDIUM"),
            )
        ]
    assert outcome.check({PAT: tijori_side | expect | {"queue": queue}}) == []
    assert not outcome.trusted(PAT)
    assert (outcome.status, outcome.exit) == ("COMPLETE", 0)


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("stage", ["LAURUSLABS-Q3FY25"], indirect=True)
def test_correction_cutoffs_and_two_unsuperseded_interpretations(stage: Stage) -> None:
    """K1: a manual correction selects only from its cutoff; two current ones are ambiguous."""
    original = full_run(stage).interpretation(REVENUE, "xbrl")
    before = stage.repository.store_clock()
    correction = mark(
        stage,
        original,
        "K1 C",
        supersedes_interpretation_id=original.interpretation_id,
        revision_cause=RevisionCause.MANUAL_CORRECTION,
    )
    agrees = {REVENUE: {"cor.status": "AGREES_UNQUALIFIED"}}
    for cutoff, selected in ((before, original), (None, correction)):
        outcome = Outcome(stage, cutoff)
        assert (
            outcome.interpretation(REVENUE, "xbrl").interpretation_id == selected.interpretation_id
        )
        assert outcome.check(agrees) == [] and (outcome.status, outcome.exit) == ("COMPLETE", 0)
    mark(stage, correction, "K1 D")
    outcome = Outcome(stage)
    assert (
        outcome.check(
            {
                REVENUE: {
                    "sides.xbrl.s": "INVALID",
                    "sides.xbrl.why": AMBIGUOUS,
                    f"pair:xbrl>{SCR}": ("NOT_COMPARABLE", AMBIGUOUS),
                    "cor.status": "NOT_COMPARABLE",
                }
            }
        )
        == []
    )
    assert any(
        entry == ("sev", "MEDIUM") for item in outcome.got[REVENUE]["queue"] for entry in item
    )
    assert (outcome.status, outcome.exit) == ("COMPLETE", 0)


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("stage", ["LAURUSLABS-Q3FY25", "HFCL-Q3FY25"], indirect=True)
def test_trusted_continuing_pat_and_diagnostic_overlay(stage: Stage) -> None:
    """H7a_1/H7a_2 (D3 split proof): the frozen CORROBORATED continuing-PAT cell is trusted; an
    open MEDIUM diagnostic Upstox item leaves it trusted, the same item as non-diagnostic HIGH
    does not. No Upstox value is claimed."""
    outcome = full_run(stage)
    assert outcome.trusted(PAT)
    row = outcome.row(PAT)
    item = outcome.items[0].model_copy(
        update={
            "key": row.key,
            "outcome": "NOT_COMPARABLE",
            "severity": QueueSeverity.MEDIUM,
            "diagnostic": True,
            "reason_code": "PRECISION_UNSUPPORTED",
        }
    )
    control = item.model_copy(update={"severity": QueueSeverity.HIGH, "diagnostic": False})
    for added, trusted_after in ((item, True), (control, False)):
        overlay = outcome.overlay.model_copy(update={"open_items": (*outcome.items, added)})
        assert outcome.trusted(PAT, overlay) is trusted_after


INVENTORIES = "inventories|I|-|REPORTED"
INVENTORIES_WITHHELD = MarkedEdit(
    label="k2-inventories-withheld",
    find=b'<in-capmkt:Inventories contextRef="OneI" decimals="-6" unitRef="INR">33645000000'
    b"</in-capmkt:Inventories>",
    replace=b"",
)


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("stage", ["APARINDS-Q2FY26"], indirect=True)
def test_issuer_correction_omitting_a_line_has_no_fallback(stage: Stage) -> None:
    """K2: an XBRL-only correction of A-X2 without Inventories supersedes the original; the
    line is NO_VALUE with no fallback to the superseded package."""
    original = stage.first_party(members={Representation.XBRL: "xbrl-consolidated"})
    assert Outcome(stage, vendors=[]).check({INVENTORIES: {"sides.xbrl.s": "VALUE"}}) == []
    stage.first_party(
        INVENTORIES_WITHHELD,
        members={Representation.XBRL: "xbrl-consolidated"},
        supersedes=original,
    )
    outcome = Outcome(stage, vendors=[])
    expect: dict[str, Any] = {
        "sides.xbrl.s": "NO_VALUE",
        "ext.status": "NOT_APPLICABLE",
        "cor.status": "NO_SOURCE",
    }
    expect["queue"] = [(("on", "corroboration"), ("out", "NO_SOURCE"), ("sev", "MEDIUM"))]
    assert outcome.check({INVENTORIES: expect}) == []
    assert outcome.status == "COMPLETE"


FINANCE, DA = "finance_costs|Q|-|REPORTED", "depreciation_amortisation|Q|-|REPORTED"
OPEX = "opex_excl_finance_and_da|Q|-|DERIVED"
FC_TEST = {
    "record_id": "FC-TEST",
    "scope": "MAPPING",
    "scope_ref": "capmkt.finance_costs",
    "canonical_id": "finance_costs",
    "operand_name": "finance_costs",
    "evidence_ref": "test: marked XBRL copy, finance costs one crore above PDF p3 (e)",
    "explained_amount": "10000000",
    "unit": "CURRENCY_AMOUNT",
}
DA_ELEMENT = (
    b'<in-capmkt:DepreciationDepletionAndAmortisationExpense contextRef="OneD" decimals="-5"'
    b' unitRef="INR">%s</in-capmkt:DepreciationDepletionAndAmortisationExpense>'
)
DA_RELOCATED = MarkedEdit(  # the FourD lexeme under the OneD context, decimals unchanged
    label="c6-da-fourd-lexeme", find=DA_ELEMENT % b"398800000", replace=DA_ELEMENT % b"780900000"
)
HIGH_EXTRACTION = (("on", "extraction"), ("out", "DISAGREE"), ("sev", "HIGH"))


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("stage", ["APARINDS-Q2FY26"], indirect=True)
def test_unrelated_discrepancy_stays_high(stage: Stage) -> None:
    """C6: FC-TEST explains the finance-costs crore, but not the relocated D&A lexeme: opex
    applies and records FC-TEST, its intervals stay disjoint -> DISAGREE HIGH; exit 3."""
    stage.config_root = stage.tmp_path / "config"
    shutil.copytree(CONFIG, stage.config_root)
    definitions = stage.config_root / "definition_sets" / "v2.yaml"
    definitions.write_text(
        yaml.safe_dump({"version": "v2", "records": [FC_TEST]}), encoding="utf-8"
    )
    stage.versions = VERSIONS.model_copy(update={"definition_set": "v2"})
    stage.first_party(FINANCE_PLUS_ONE_CRORE, DA_RELOCATED)
    outcome = Outcome(stage, vendors=[])
    da_xbrl = (
        stored("78.09", UNITS["crore"]),
        (stored("78.085", UNITS["crore"]), stored("78.095", UNITS["crore"])),
    )
    assert (
        outcome.got[DA]["sides"]["xbrl"]["v"],
        outcome.got[DA]["sides"]["xbrl"]["iv"],
    ) == da_xbrl
    assert (
        outcome.check(
            {
                FINANCE: {"ext.status": "TAGGING_DIFFERENCE"},
                DA: {"ext.status": "DISAGREE", "queue": [HIGH_EXTRACTION]},
                OPEX: {"ext.status": "DISAGREE", "queue": [HIGH_EXTRACTION]},
            }
        )
        == []
    )
    (pair,) = [pair for pair in outcome.row(OPEX).pairs if pair.pair_kind is PairKind.EXTRACTION]
    assert [adjustment.definition_record_id for adjustment in pair.adjustments] == ["FC-TEST"]
    assert (outcome.status, outcome.exit) == ("COMPLETE", 3)


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("stage", ["APARINDS-Q2FY26"], indirect=True)
def test_screener_liabilities_construction(
    stage: Stage, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """E9: Screener Borrowings + Other Liabilities against the filing's Liabilities + NCI,
    AGREE_UNQUALIFIED; Screener 'Total Liabilities' populates no row (FILING_ONLY). The
    construction is a computed side naming its stored trace, in results and in the report."""
    spec = MANIFEST["fixtures"]["E9"]
    fy25(stage, [SCR])
    stage.first_party(quarter="FY25_Q4", members=FY25_XBRL)
    stage.vendor(SCR, "A-SCR")
    outcome = Outcome(stage)
    row = outcome.got["liabilities_incl_nci|I|-|DERIVED"]
    xbrl, screener = row["sides"]["xbrl"], row["sides"][SCR]
    assert (xbrl["v"], xbrl["iv"]) == fixture_side(spec["first_party_liabilities_incl_nci"], True)
    assert (screener["v"], screener["iv"]) == fixture_side(spec["screener_construction"], False)
    assert screener["calc"] == "COMPUTED"
    (value,) = [
        value
        for value in outcome.row("liabilities_incl_nci|I|-|DERIVED").source_values
        if _name(value) == SCR
    ]
    assert value.calculation_trace_id is not None and value.interpretation_id is None
    capsys.readouterr()
    assert cli(stage, monkeypatch, "report", "--run", str(outcome.record.run_id)) == 0
    printed = capsys.readouterr().out.splitlines()
    (line,) = [line for line in printed if f"\t{SCR}\t" in line and "6760.00 crore" in line]
    assert "class=COMPUTED" in line and f"trace={value.calculation_trace_id}" in line
    assert (
        outcome.check(
            {
                "liabilities_incl_nci|I|-|DERIVED": {
                    f"pair:xbrl>{SCR}": ("AGREE_UNQUALIFIED", None),
                    "cor.status": "AGREES_UNQUALIFIED",
                },
                "total_liabilities|I|-|REPORTED": {
                    f"sides.{SCR}": None,
                    "cor.status": "FILING_ONLY",
                },
            }
        )
        == []
    )
    total = spec["screener_total_liabilities"]
    with stage.pool.connection() as conn:
        (capture,) = conn.execute(
            "SELECT id FROM eqos.capture_refs WHERE source_id = %s", (SCREENER[0],)
        ).fetchone()
    cells = {
        cell.occurrence_id
        for cell in stage.repository.list_capture_occurrences(capture)
        if str(cell.anchor["row_path"]).endswith(f":{total['row']}")
        and cell.anchor["column_label"] == total["col"]
    }
    readings = [
        item.status.value
        for item in stage.repository.list_capture_interpretations(capture)
        if item.occurrence_id in cells
    ]
    assert cells and set(readings) == {"UNMAPPED"}


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("stage", ["NETWEB-Q3FY25"], indirect=True)
def test_upstox_summary_and_full_statement_both_retained(stage: Stage) -> None:
    """E6 (ingest level, no run): NETWEB's standalone Upstox revenue "2202.4" (summary) and
    "Total Revenue" "2202.41" (full statement) for FY26 are two STANDALONE interpretations,
    both INVALID/PRECISION_UNSUPPORTED, no internal conflict, both occurrences retained."""
    spec = MANIFEST["fixtures"]["E6"]
    end = date(2026, 3, 31)
    report = stage.vendor(UPSTOX, "N-UPS", end=end, basis=Basis.STANDALONE)
    capture = report.attempt.capture.capture_ref_id
    cells = {
        cell.occurrence_id: cell for cell in stage.repository.list_capture_occurrences(capture)
    }
    found = [
        item
        for item in stage.repository.list_capture_interpretations(capture)
        if item.canonical_id == "total_income"
        and item.period == PeriodInterval.duration(date(2025, 4, 1), end)
    ]

    def located(item: Interpretation) -> tuple[str, str, str | None]:
        cell = cells[item.occurrence_id]
        table = str(cell.anchor["table_key"])
        return BLOCKS.get(table, table), cell.native_field, cell.raw_value_text

    assert {located(item) for item in found} == {
        (spec[side]["block"], spec[side]["item"], spec[side]["lex"])
        for side in ("summary", "full_statement")
    }
    first, other = found
    assert first.interpretation_id != other.interpretation_id
    assert {(item.basis, item.status.value, item.reason) for item in found} == {
        (Basis.STANDALONE, "INVALID", "PRECISION_UNSUPPORTED")
    }
    assert first.key is not None
    left, right = (
        no_value(first.key, None).model_copy(update={"interval": item.interval}) for item in found
    )
    months = tuple(cells[item.occurrence_id].native_context["header_months"] for item in found)
    assert not internal_conflict(left, right, (months[0], months[1]))


RESTATED_9M = PdfRedaction(  # E16 marked_a_p3: the M9-1 revenue cell takes the Sales figure
    page=3, row_of="13,371.45", words=("13,371.45",), x_min=250, x_max=298, replace="13,303.75"
)
DERIVED_Q4 = "revenue_from_operations|Q|-|DERIVED"


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("stage", ["APARINDS-Q2FY26"], indirect=True)
def test_restatement_over_the_fy_and_nine_months(stage: Stage) -> None:
    """E16: Apar FY25 Q4 revenue derived FY - 9M agrees with the reported Q4 (no item); a
    marked A-P3 comparative restating the 9M surfaces, leaves the 9M selection unchanged and
    makes the derived side REVISION_INCOMPATIBLE: NOT_COMPARABLE, MEDIUM."""
    spec = MANIFEST["fixtures"]["E16"]
    fy25(stage, [])
    stage.first_party(quarter="FY25_Q3", members=FY25_XBRL, end=date(2024, 12, 31))
    stage.first_party(quarter="FY25_Q4", members=FY25_XBRL)
    c1 = Outcome(stage)
    side = c1.got[DERIVED_Q4]["sides"]["xbrl"]
    assert (side["v"], side["iv"]) == fixture_side(spec["derived_q4"], True)
    reported = c1.got[DERIVED_Q4]["sides"]["reported"]
    assert (reported["v"], reported["iv"]) == fixture_side(spec["reported_q4"], False)
    assert (
        c1.check({DERIVED_Q4: {"pair:reported>xbrl": ("AGREE_UNQUALIFIED", None), "queue": []}})
        == []
    )
    marked = marked_pdf(stage.tmp_path, "e16-a-p3", RESTATED_9M, quarter="FY26_Q3")
    package_id = stage.first_party(
        quarter="FY26_Q3",
        members={Representation.PDF: "results"},
        end=date(2025, 12, 31),
        pdf=marked,
    )
    (package,) = stage.repository.get_packages([package_id])
    capture = package.members[Representation.PDF].capture.capture_ref_id
    assert capture is not None
    comparative = [
        item.revision_cause.value
        for item in stage.repository.list_capture_interpretations(capture)
        if item.canonical_id == "revenue_from_operations"
        and item.period == PeriodInterval.duration(date(2024, 4, 1), date(2024, 12, 31))
    ]
    assert comparative == ["COMPARATIVE_RESTATEMENT"]
    c2 = Outcome(stage)
    restated = "REVISION_INCOMPATIBLE"
    assert (
        c2.check(
            {
                DERIVED_Q4: {
                    "sides.xbrl.s": "INVALID",
                    "sides.xbrl.why": restated,
                    "pair:reported>xbrl": ("NOT_COMPARABLE", restated),
                    "queue": [
                        (
                            ("a", "reported"),
                            ("b", "xbrl"),
                            ("on", "pair"),
                            ("out", "NOT_COMPARABLE"),
                            ("sev", "MEDIUM"),
                        )
                    ],
                }
            }
        )
        == []
    )
    assert (c1.status, c2.status) == ("COMPLETE", "COMPLETE")


OPM_CASES = {  # C5: the derived OPM side's calculation state -> (side state, reason, status)
    "OPERAND_MISSING": ("NO_VALUE", None, "VENDOR_ONLY"),
    "UNDEFINED": ("INVALID", "UNDEFINED", "NOT_COMPARABLE"),
    "REVISION_INCOMPATIBLE": ("INVALID", "REVISION_INCOMPATIBLE", "NOT_COMPARABLE"),
}


@pytest.mark.parametrize("calculation", sorted(OPM_CASES))
def test_derived_opm_states_against_a_vendor(calculation: str) -> None:
    """C5 (unit level, the recorded OPM fixture exception: constructed operands): each
    non-computed first-party OPM state against a vendor VALUE routes MEDIUM."""
    state, reason, status = OPM_CASES[calculation]
    key = vendor_key("opm_pct", PeriodInterval.duration(date(2025, 7, 1), date(2025, 9, 30)))
    first = no_value(key, None).model_copy(
        update={
            "state": SourceState(state),
            "reasons": () if reason is None else (ReasonCode(reason),),
            "calculation_state": CalculationState(calculation),
        }
    )
    vendor = no_value(key, Decimal("8.1"))
    result = corroboration_result(
        applicability=ApplicabilityStatus.APPLICABLE,
        first_party=SourceQualifiedSide(
            ref=SourceRef(source_role=SourceRole.FIRST_PARTY, representation=Representation.XBRL),
            side=first,
        ),
        vendors=(
            SourceQualifiedSide(
                ref=SourceRef(
                    source_role=SourceRole.INDEPENDENT_VENDOR,
                    representation=Representation.HTML,
                    source_id=SCREENER[0],
                    surface=SCREENER[1],
                ),
                side=vendor,
            ),
        ),
        definitions=load_definition_set(CONFIG / "definition_sets" / "v1.yaml"),
        policy=load_comparison_policy(CONFIG / "comparison_policy" / "v1.yaml"),
    )
    assert (result.status.value, result.reason) == (status, reason)
    drafts = [
        route_pair_draft(pair.model_copy(update={"attempt_ids": (1,)}), key=key)
        for pair in result.pairs
    ]
    if not (result.status is CorroborationStatus.NOT_COMPARABLE and result.pairs):
        drafts.append(route_status_draft(result.status, key=key, attempt_ids=(1,)))
    assert {draft.severity for draft in drafts if draft is not None} == {QueueSeverity.MEDIUM}


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("stage", ["APARINDS-Q2FY26"], indirect=True)
def test_apar_report_shows_every_source_status_and_queue_item(
    stage: Stage, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``fundamentals compare report --run <id>`` in the isolated database prints every row's
    source states and both statuses, and every open queue item."""
    outcome = full_run(stage)
    capsys.readouterr()
    assert cli(stage, monkeypatch, "report", "--run", str(outcome.record.run_id)) == 0
    printed = capsys.readouterr().out
    assert f"status\t{outcome.status}" in printed.splitlines()
    blocks = {
        head.rstrip("*"): rest  # "*": a headline row
        for head, *rest in (block.splitlines() for block in printed.split("\nrow\t")[1:])
    }
    for row in outcome.rows:
        lines = blocks[row.row_id]
        if row.applicability is ApplicabilityStatus.NOT_APPLICABLE:
            continue  # printed with its rule alone
        assert lines[0].split("\t")[:2] == ["  extraction", row.extraction_status.value]
        assert lines[1] == f"  corroboration\t{row.corroboration_status.value}"
        shown = {tuple(line.strip().split("\t")[:3]) for line in lines}
        for value in row.source_values:
            name = (
                value.representation.value
                if value.source_role is SourceRole.FIRST_PARTY
                else f"{value.source_id}/{value.surface}"
            )
            assert (value.source_role.value, name, value.state.value) in shown, (row.row_id, name)
    fields = [line.strip().split("\t") for line in printed.splitlines()]
    queue = [
        tuple(line[1:4]) for line in fields if line[0] == "queue"
    ]  # keyed items under their row
    assert sorted(queue) == sorted(
        (str(item.item_id), item.severity.value, item.outcome) for item in outcome.items
    )
