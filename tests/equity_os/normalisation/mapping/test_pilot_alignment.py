"""PILOT-GAP alignment (eqos-4j2.33): the six required roles AGREE and are admitted in all four
Apar pilot quarters under dictionary v2, mapping set v6 and alignment rules v2, and every proof
fails closed where the evidence is unreadable, absent or out of position.

Each quarter is ingested from its retained originals through the production extractor and run
through the real ``compare run`` argument path, so the flag reaches the run's pins. Expected
proofs and statuses are those recorded by the plan's probes (``docs/plans/PILOT-GAP-alignment.md``).
"""

from __future__ import annotations

import argparse
import itertools
from collections import Counter
from contextlib import nullcontext
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from evidence_support import BOTH, CONFIG, Ingest, ingest, policy
from retained_support import apar_intake

from equity_os.contracts.measurement.canonical import (
    Basis,
    PeriodKind,
    Representation,
    StatementFamily,
    ValueIdentity,
)
from equity_os.contracts.measurement.evidence import (
    CaptureReference,
    FilingFamily,
    FilingPackage,
    Interpretation,
    InterpretationReason,
    InterpretationStatus,
    KeySelection,
    KnowledgeTimeStatus,
    Occurrence,
    PackageMember,
)
from equity_os.contracts.measurement.measurement_key import PeriodInterval
from equity_os.contracts.measurement.observation import AccountingFramework
from equity_os.contracts.sourcing.source_catalog import (
    BUILTIN_SOURCES,
    EvidenceRole,
    SourceClass,
    SourceDescriptor,
)
from equity_os.contracts.verification.comparison import (
    ExtractionStatus,
    SelectionSource,
    SourceRole,
    SourceState,
)
from equity_os.contracts.verification.config_versions import ConfigVersions
from equity_os.contracts.verification.vendor_first import FilingFailure
from equity_os.extraction.results_pdf.pdf_adapter import read_pdf_occurrences
from equity_os.extraction.results_pdf.pdf_source import compute_file_sha256, load_pdf
from equity_os.extraction.results_pdf.pdf_statement_pages import specs_from_config
from equity_os.extraction.xbrl.xbrl_adapter import read_xbrl_occurrences
from equity_os.interface.commands.verification import compare_cli
from equity_os.interface.commands.verification.compare_cli import add_compare_parser, run_compare
from equity_os.interface.entry.config import load_config
from equity_os.normalisation.dictionary.dictionary import CanonicalDictionary, load_dictionary
from equity_os.normalisation.mapping.alignment import load_alignment_rules, prove_alignment
from equity_os.normalisation.mapping.capture_interpretation import (
    CaptureScope,
    interpret_generation,
)
from equity_os.normalisation.mapping.mapping import (
    MappingSet,
    NormalisationPolicy,
    load_mapping_set,
    selects,
)
from equity_os.storage.facts.pg_fact_store import create_native_store
from equity_os.verification.admission.admission import AdmissionRefusal, admit_run
from equity_os.verification.comparison.run import load_results
from equity_os.verification.comparison.run_models import ResultRow

__all__ = ["ingest", "policy"]

# REQUIRED_ROLES through LEGACY_CONCEPTS (plan Finding 1).
ROLES = (
    "revenue_from_operations",
    "total_income",
    "total_expenses",
    "profit_before_tax",
    "profit_for_period",
    "eps_basic",
)
COMMON = {
    "total_income.revenue_plus_other_income",
    "revenue_from_operations.total_income_less_other_income",
    "other_income.total_income_less_revenue",
    "total_expenses.sum_of_expense_lines",
    "profit_before_tax.before_associates_position",
    "profit_for_period.total_comprehensive_income_less_oci",
    "eps_basic.basic_line",
}
PLUS_EXCEPTIONAL = "profit_before_tax.income_less_expenses_plus_exceptional"
LESS_TAX = "profit_for_period.pbt_incl_associates_less_tax"
# The plan's Decision table: no PDF tax line in Q2 FY26, PQ3's '.' cells in Q1 FY27.
QUARTERS = {
    "FY26_Q2": ("aparinds-fy26-q2.yaml", COMMON),
    "FY26_Q3": ("aparinds-fy26-q3.yaml", COMMON | {PLUS_EXCEPTIONAL, LESS_TAX}),
    "FY26_Q4": ("aparinds-fy26-q4-pg.yaml", COMMON | {PLUS_EXCEPTIONAL, LESS_TAX}),
    "FY27_Q1": ("aparinds-fy27-q1-pg.yaml", COMMON),
}
PBT_RULE = "profit_before_tax.before_associates_position"
PBT_INCL = "profit_before_tax_incl_associates"
UNREADABLE = ("pdf.exceptional_items_before_tax", "pdf.tax_earlier_years", "pdf.tax_expense")
SECTION_BOUND = (
    "pdf.current_tax",
    "pdf.deferred_tax",
    "pdf.tax_earlier_years",
    "pdf.cost_of_materials_consumed",
    "pdf.purchases_of_stock_in_trade",
    "pdf.changes_in_inventories",
    "pdf.employee_benefits_expense",
    "pdf.finance_costs",
    "pdf.depreciation_amortisation",
    "pdf.other_expenses",
    "pdf.total_expenses",
)
OTHER_SECTION = "Discontinued operations"
# probe11.out: PQ3's 168 P&L cells under the original and the -pg config, by anchor key.
PQ3_UNITS = Counter({(("", 0), ("INR", 7)): 160, (("INR per share", 0), ("INR per share", 0)): 8})
SURFACES = {Representation.PDF: "NSE_RESULTS_PDF", Representation.XBRL: "NSE_XBRL_INSTANCE"}
NOW = datetime(2026, 10, 19, tzinfo=UTC)
_IDS = itertools.count(1)
RULES_V2 = load_alignment_rules(CONFIG / "normalisation/mappings" / "alignment" / "v2.yaml")


@pytest.fixture(scope="module")
def dictionary() -> CanonicalDictionary:
    """Canonical dictionary v2."""
    return load_dictionary(CONFIG / "normalisation/dictionary", "v2")


@pytest.fixture(scope="module")
def mapping_set(dictionary: CanonicalDictionary) -> MappingSet:
    """Mapping set v6."""
    return load_mapping_set(CONFIG / "normalisation/mappings", "v6", dictionary=dictionary)


def _compare(period_end: date, alignment: str | None) -> argparse.Namespace:
    """Parsed ``compare run`` arguments for the v2 dictionary and v6 mapping set."""
    parser = argparse.ArgumentParser()
    add_compare_parser(parser.add_subparsers(dest="command"))
    flag = [] if alignment is None else ["--alignment-rules", alignment]
    return parser.parse_args(
        ["compare", "run", "--entity", "APARINDS", "--basis", "consolidated", "--period-end"]
        + [period_end.isoformat(), "--config-root", str(CONFIG), "--dictionary", "v2"]
        + ["--mapping-set", "v6", *flag]
    )


def _roles(run_id: int, ingest: Ingest, quarter: PeriodInterval) -> dict[str, ResultRow]:
    """The run's reported, undimensioned quarter rows of the six roles."""
    with ingest.pg_db.runtime_pool() as pool:
        rows = load_results(run_id, pool=pool)
    return {
        row.key.canonical_id: row
        for row in rows
        if row.key.canonical_id in ROLES
        and row.key.period == quarter
        and not row.key.dimensions.pairs
        and row.value_identity is ValueIdentity.REPORTED
    }


def _xbrl_side(row: ResultRow) -> int | None:
    """The XBRL interpretation a row selected."""
    (value,) = [
        v
        for v in row.source_values
        if v.source_role is SourceRole.FIRST_PARTY and v.representation is Representation.XBRL
    ]
    return value.interpretation_id


def _selections(
    items: list[Interpretation], package_id: int, quarter: PeriodInterval
) -> dict[tuple[str, Representation], KeySelection]:
    """One package selection per mapped, undimensioned quarter key."""
    return {
        (i.key.digest(), i.representation): KeySelection(
            key=i.key,
            representation=i.representation,
            state=SourceState.VALUE,
            interpretation=i,
            package_id=package_id,
            source=SelectionSource.PACKAGE_AS_REPORTED,
            reason=None,
            considered_interpretation_ids=(i.interpretation_id,),
            surfaced_restatements=(),
        )
        for i in items
        if i.status is InterpretationStatus.MAPPED
        and i.interval is not None
        and i.key is not None
        and i.key.period == quarter
        and not i.key.dimensions.pairs
        and i.interpretation_id is not None
    }


def _member(representation: Representation, source_id: str, sha256: str) -> PackageMember:
    """An in-memory package member over one retained original."""
    capture = CaptureReference(
        capture_ref_id=next(_IDS),
        source_id=source_id,
        surface=SURFACES[representation],
        request_key="test",
        capture_id="test",
        blob_sha256=sha256,
        record_sha256=sha256,
        registered_at=NOW,
        first_seen_at=NOW,
    )
    return PackageMember(
        representation=representation,
        capture=capture,
        knowledge_time=NOW,
        knowledge_time_raw="test",
        knowledge_time_status=KnowledgeTimeStatus.KNOWN,
    )


def _pdf_occurrences(config_path: Path) -> tuple[PackageMember, tuple[Occurrence, ...]]:
    """The production PDF reader's occurrences of a config's results PDF, no database."""
    cfg = load_config(config_path)
    pdf = load_pdf(
        source_id=cfg.results_pdf.source_id,
        path=cfg.results_pdf_path(config_path),
        expected_sha256=cfg.results_pdf.sha256,
    )
    member = _member(Representation.PDF, cfg.results_pdf.source_id, cfg.results_pdf.sha256)
    found = read_pdf_occurrences(
        pdf,
        capture=member.capture,
        member=member,
        basis=Basis.CONSOLIDATED,
        specs=specs_from_config(cfg.pdf_parse),
    )
    return member, found.occurrences


def _interpreted(
    occurrences: tuple[Occurrence, ...],
    member: PackageMember,
    mapping_set: MappingSet,
    policy: NormalisationPolicy,
    dictionary: CanonicalDictionary,
) -> tuple[list[Occurrence], tuple[Interpretation, ...]]:
    """Occurrences given ids, and their production interpretations under ``mapping_set``."""
    numbered = [o.model_copy(update={"occurrence_id": next(_IDS)}) for o in occurrences]
    scope = CaptureScope(
        capture=member.capture,
        entity_id=1,
        basis=Basis.CONSOLIDATED,
        framework=AccountingFramework.IND_AS,
        mapping_set=mapping_set,
        policy=policy,
        dictionary=dictionary,
        fiscal_year_end_month=3,
    )
    items = interpret_generation(
        numbered,
        scope=scope,
        prior=(),
        prior_anchor_keys={},
        reserve_ids=lambda count: tuple(next(_IDS) for _ in range(count)),
        recorded_at=NOW,
    )
    return numbered, items


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("quarter_id", QUARTERS)
def test_six_roles_agree_and_admit(
    ingest: Ingest, monkeypatch: pytest.MonkeyPatch, quarter_id: str
) -> None:
    """All six roles AGREE and are admitted; the stored v2 proofs are exactly the plan's ✓
    cells; and the PBT layout rule, the section selectors and PQ3's '.' cells fail closed."""
    config_name, holding = QUARTERS[quarter_id]
    config_path = CONFIG / "runs" / config_name
    cfg = load_config(config_path)
    quarter = PeriodInterval.duration(cfg.quarter.period_start, cfg.quarter.period_end)
    catalog = BUILTIN_SOURCES.extend(
        SourceDescriptor(
            source_id=cfg.results_pdf.source_id,
            source_class=SourceClass.FIRST_PARTY,
            evidence_role=EvidenceRole.RECONCILABLE,
        )
    )
    intake = apar_intake(ingest.tmp_path, quarter_id, BOTH, issuer_config=config_path)
    report = ingest.run(
        intake,
        cfg.quarter.period_end,
        catalog=catalog,
        pdf_specs=specs_from_config(cfg.pdf_parse),
    )
    package = ingest.package(report)
    assert package.package_id is not None
    for name, value in ingest.pg_db.cli_env().items():
        monkeypatch.setenv(name, value)

    record = run_compare(_compare(cfg.quarter.period_end, "v2"))
    assert record.manifest.pinned.alignment_rules.version == "v2"
    rows = _roles(record.run_id, ingest, quarter)
    assert {cid: row.extraction_status for cid, row in rows.items()} == dict.fromkeys(
        ROLES, ExtractionStatus.AGREE
    )
    proofs = [
        p
        for p in ingest.repository.list_alignment_proofs(package.package_id)
        if p.rule_set_version == "v2" and p.key.period == quarter
    ]
    assert {(p.rule_id, p.holds) for p in proofs} == {(rule, True) for rule in holding}
    with ingest.pg_db.runtime_pool() as pool:
        outcome = admit_run(record.run_id, pool=pool, store_id=create_native_store(pool, "v2"))
    refused = dict(outcome.refusals)
    assert not {cid for cid, row in rows.items() if row.row_id in refused}
    admitted = {item.interpretation_id for item in outcome.records}
    assert {_xbrl_side(row) for row in rows.values()} <= admitted

    if quarter_id == "FY27_Q1":
        items = ingest.interpretations(report)
        # PQ3's '.' cells stay unreadable, and so does the tax construction over one.
        found = {
            i.mapping_entry_id or i.construction_rule_id: (i.status, i.reason)
            for i in items
            if (i.mapping_entry_id or i.construction_rule_id) in UNREADABLE
            and i.period == quarter
            and i.representation is Representation.PDF
        }
        assert found == dict.fromkeys(
            UNREADABLE, (InterpretationStatus.INVALID, InterpretationReason.UNREADABLE_CELL)
        )

    if quarter_id == "FY26_Q2":
        # Without alignment v2 (the flag omitted keeps v1), PQ0 PBT is unqualified and refused.
        legacy = run_compare(_compare(cfg.quarter.period_end, None))
        assert legacy.manifest.pinned.alignment_rules.version == "v1"
        pbt = _roles(legacy.run_id, ingest, quarter)["profit_before_tax"]
        assert pbt.extraction_status is ExtractionStatus.AGREE_UNQUALIFIED
        with ingest.pg_db.runtime_pool() as pool:
            refused = admit_run(legacy.run_id, pool=pool, store_id=create_native_store(pool, "v1"))
        assert dict(refused.refusals)[pbt.row_id] is AdmissionRefusal.FILING_UNRESOLVED
        assert dict(refused.filing_failures)[pbt.row_id] is FilingFailure.EXTRACTION_NOT_AGREE


@pytest.mark.retained
@pytest.mark.parametrize("quarter_id", QUARTERS)
def test_pbt_layout_and_sections_fail_closed(
    quarter_id: str,
    dictionary: CanonicalDictionary,
    mapping_set: MappingSet,
    policy: NormalisationPolicy,
) -> None:
    """Over in-memory selections, the PBT layout rule holds only for its own anchors and its own
    PDF position; in PQ1 the tax and expense selectors are exact to their section."""
    config_path = CONFIG / "runs" / QUARTERS[quarter_id][0]
    cfg = load_config(config_path)
    quarter = PeriodInterval.duration(cfg.quarter.period_start, cfg.quarter.period_end)
    pdf_member, pdf_found = _pdf_occurrences(config_path)
    xbrl_path = cfg.xbrl_local_path(config_path)
    xbrl_member = _member(Representation.XBRL, cfg.xbrl.source_id, compute_file_sha256(xbrl_path))
    xbrl_found = read_xbrl_occurrences(
        xbrl_path.read_bytes(),
        capture=xbrl_member.capture,
        member=xbrl_member,
        mapping_set=mapping_set,
    )
    occurrences, pdf_items = _interpreted(pdf_found, pdf_member, mapping_set, policy, dictionary)
    _, xbrl_items = _interpreted(xbrl_found, xbrl_member, mapping_set, policy, dictionary)
    package = FilingPackage(
        package_id=1,
        entity_id=1,
        family=FilingFamily.FINANCIAL_RESULTS,
        reporting_period_end=cfg.quarter.period_end,
        basis=Basis.CONSOLIDATED,
        framework=AccountingFramework.IND_AS,
        reporting_kind=PeriodKind.QUARTER,
        knowledge_time=NOW,
        supersedes_package_id=None,
        replaced_statements=frozenset(),
        statements_present=frozenset(),
        members={Representation.PDF: pdf_member, Representation.XBRL: xbrl_member},
        evidence_sha256=cfg.results_pdf.sha256,
    )
    selected = _selections([*xbrl_items, *pdf_items], 1, quarter)
    (rule,) = [r for r in RULES_V2.rules if r.rule_id == PBT_RULE]
    pbt_key = next(s.key for s in selected.values() if s.key.canonical_id == "profit_before_tax")
    pdf_slot = (pbt_key.digest(), Representation.PDF)
    (incl,) = [
        s.interpretation
        for s in selected.values()
        if s.representation is Representation.PDF and s.key.canonical_id == PBT_INCL
    ]
    assert incl is not None
    assert incl.mapping_entry_id == f"pdf.{PBT_INCL}"
    moved = selected | {
        pdf_slot: selected[pdf_slot].model_copy(
            update={"interpretation": incl.model_copy(update={"key": pbt_key})}
        )
    }
    assert rule.layout_anchor is not None
    wrong_pdf = rule.model_copy(
        update={"layout_anchor": {**rule.layout_anchor, Representation.PDF: f"pdf.{PBT_INCL}"}}
    )
    wrong_xbrl = rule.model_copy(
        update={"layout_anchor": {**rule.layout_anchor, Representation.XBRL: f"capmkt.{PBT_INCL}"}}
    )
    for case, chosen, expected in (
        (rule, selected, True),
        (wrong_pdf, selected, False),
        (wrong_xbrl, selected, False),
        (rule, moved, False),
    ):
        found = prove_alignment(package, chosen, RULES_V2.model_copy(update={"rules": (case,)}))
        assert [p.holds for p in found if p.key == pbt_key] == [expected]

    if quarter_id == "FY26_Q3":
        # The tax and expense selectors are exact to their section (plan Findings 8, 15).
        entries = {e.entry_id: e for e in mapping_set.entries}
        by_id = {o.occurrence_id: o for o in occurrences}
        for entry_id in SECTION_BOUND:
            (row,) = [
                by_id[i.occurrence_id]
                for i in pdf_items
                if i.mapping_entry_id == entry_id and i.period == quarter
            ]
            moved_row = row.model_copy(
                update={"native_context": {**row.native_context, "section": OTHER_SECTION}}
            )
            assert row.native_context["section"] == "Expenses", entry_id
            assert selects(entries[entry_id], row), entry_id
            assert not selects(entries[entry_id], moved_row), entry_id


@pytest.mark.retained
def test_pq3_pl_unit_needs_the_pg_marker() -> None:
    """Under aparinds-fy27-q1.yaml PQ3's P&L money cells carry no unit; the -pg config's exact
    'Ra.in crones' marker gives those same cells INR at scale 7 and leaves EPS as it was
    (plan Finding 2)."""
    cells = {}
    for name in ("aparinds-fy27-q1.yaml", "aparinds-fy27-q1-pg.yaml"):
        _, found = _pdf_occurrences(CONFIG / "runs" / name)
        cells[name] = {
            o.anchor_key: (o.raw_unit, o.raw_scale)
            for o in found
            if o.native_context["statement_family"] == StatementFamily.PL.value
        }
    original, marked = cells["aparinds-fy27-q1.yaml"], cells["aparinds-fy27-q1-pg.yaml"]
    assert original.keys() == marked.keys()
    assert Counter((original[k], marked[k]) for k in original) == PQ3_UNITS


@pytest.mark.parametrize(("flag", "expected"), [("v2", "v2"), (None, "v1")])
def test_compare_run_forwards_alignment_rules(
    monkeypatch: pytest.MonkeyPatch, flag: str | None, expected: str
) -> None:
    """``compare run --alignment-rules`` reaches the request's versions; omitted, it stays v1."""
    seen: list[ConfigVersions] = []

    class BuiltError(Exception):
        """Stops the run once the request is built."""

    def request_for(*_: object, versions: ConfigVersions, **__: object) -> None:
        seen.append(versions)
        raise BuiltError

    monkeypatch.setattr(compare_cli, "PgSettings", lambda: SimpleNamespace(host="", port=0, db=""))
    monkeypatch.setattr(compare_cli, "open_pool", lambda *_: nullcontext())
    monkeypatch.setattr(
        compare_cli,
        "EvidenceRepository",
        lambda _: SimpleNamespace(entity_id=lambda _: 1, store_clock=lambda: NOW),
    )
    monkeypatch.setattr(compare_cli, "request_for", request_for)
    with pytest.raises(BuiltError):
        run_compare(_compare(NOW.date(), flag))
    assert seen == [ConfigVersions(dictionary="v2", mapping_set="v6", alignment_rules=expected)]
