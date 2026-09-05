"""Acceptance tests for the offline three-source comparator (Phase 3, S5).

The seam is ``fundamentals.verify.three_source_inputs`` — the reader that turns
retained Screener sections, a retained Tijori page and a gold file into
precision-carrying ``SideValue``s — plus ``fundamentals.verify.three_source``,
the comparator that puts XBRL, Screener and Tijori on one row per concept. What
it protects is the difference between "these two numbers are the same" and "they
agree within the precision both sides declared": a comparison that invents its
tolerance manufactures agreement or reports rounding as a vendor defect.

Nothing here fetches: the Tijori page is retained through a real ``SnapshotStore``
with the transport patched at the committed envelope seam and read back with the
opener wired to raise, and the Screener sections are round-tripped through their
own validator before they are written. Every figure is synthetic, and the seam
modules are imported at call time, after each test's fixtures are built.
"""

from __future__ import annotations

import ast
import hashlib
import json
import urllib.request
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr, ValidationError

from fundamentals.contracts.observation import AccountingFramework, PeriodType, Scope
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.contracts.role import FactRole
from fundamentals.contracts.source_catalog import SourceClass
from fundamentals.ingest.screener_crosscheck import EvidenceTier
from fundamentals.ingest.screener_financials_models import (
    Cell,
    FinancialsMetadata,
    Period,
    PeriodKind,
    RowStatus,
    Section,
    SectionOutcome,
    SectionTable,
    TableRow,
    Unit,
)
from fundamentals.ingest.screener_session_models import Basis
from fundamentals.ingest.tijori_capture import PageEnvelope
from fundamentals.ingest.tijori_source import TijoriCredentials, TijoriSource, TijoriSourceConfig
from fundamentals.reconcile.agreement import AgreementStatus, SourceValue
from fundamentals.reconcile.gold_file import GOLD_SCHEMA_VERSION, GoldFact, GoldFile, canonical_json
from fundamentals.store.snapshot_store import SnapshotStore
from fundamentals.verify.comparison_key import ComparisonKey
from fundamentals.verify.crossfoot import half_ulp
from fundamentals.verify.laneb_sensitivity_model import MutationClass

SYMBOL, SLUG, COMPANY_ID = "TITAN", "titan-company-limited", 81
SESSION_VALUE, MEDIA_TYPE = "synthetic-fixture-session-value", "text/html; charset=utf-8"
SCREENER_SOURCE_ID, XBRL_SOURCE_ID = "screener-subscriber", "nse-indas-xbrl-consolidated"
CRORE_UNIT, PER_SHARE_UNIT, CRORE_SCALE, QUARTER = "INR crore", "INR per share", 10**7, "FY27Q4"

# Asked-for quarter, the quarter before it, a year end only the annual table has.
QUARTER_END, PRIOR_END, ANNUAL_END = date(2027, 3, 31), date(2026, 12, 31), date(2026, 3, 31)
FETCHED_AT = datetime(2027, 4, 20, 9, 30, tzinfo=UTC)

# The fixture's latest quarter, restated in the quarter every other side uses.
FIXTURE_LABEL, SYNTHETIC_LABEL = b"Mar 2025", b"Mar 2027"
AUTHENTICATED = b'<script id="is_auth" type="application/json">true</script>'
ANONYMOUS = b'<script id="is_auth" type="application/json">false</script>'

REVENUE_CONCEPT = "in-bse-fin:RevenueFromOperations"
PROFIT_CONCEPTS = (
    "in-bse-fin:ProfitLossForPeriod",
    "in-bse-fin:ProfitOrLossAttributableToOwnersOfParent",
)
EPS_CONCEPT = "in-bse-fin:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations"
ALPHA, BETA = "synthetic:AlphaConcept", "synthetic:BetaConcept"
EXCLUSION = ("synthetic exclusion stated by this test",)
TIER_ONE, TIER_THREE = EvidenceTier.EQUIVALENCE_DEMONSTRATED, EvidenceTier.EQUIVALENCE_UNPROVEN

SALES, PBT, NET_PROFIT = Decimal("17000"), Decimal("1300"), Decimal("950")
PRIOR_SALES, NEIGHBOUR_SALES = Decimal("16000"), Decimal("17740")

XBRL_DECIMALS, EPS_DECIMALS = -5, 2
XBRL_ULP, CRORE_ULP = half_ulp(XBRL_DECIMALS, CRORE_SCALE), half_ulp(0, 1)

SALES_MAPPING_ID, PROFIT_MAPPING_ID = "screener.quarters.sales", "screener.quarters.net_profit"
QUARTERS_MAPPING_IDS = frozenset({SALES_MAPPING_ID, PROFIT_MAPPING_ID, "screener.quarters.eps"})
TIJORI_MAPPING_IDS = frozenset(
    {"tijori.qt_c.net_sales", "tijori.qt_c.pbt", "tijori.qt_c.net_profit"}
)

SYNTHETIC_LINES: dict[str, tuple[str, str, str, FactRole]] = {
    "alpha": ("TIJORI", "Net Sales", "tijori:sales", FactRole.REVENUE),
    "beta": ("TIJORI", "Profit Before Tax", "tijori:pbt", FactRole.PROFIT_BEFORE_TAX),
    "screener": ("SCREENER", "Sales", "screener:Sales", FactRole.REVENUE),
}
SYNTHETIC_SECTIONS = {"TIJORI": "qt_c", "SCREENER": "quarters"}
VENDOR_ROWS: dict[str, tuple[tuple[str, str], tuple[str, str]]] = {
    "SCREENER": (("Sales", SALES_MAPPING_ID), ("Net Profit", PROFIT_MAPPING_ID)),
    "TIJORI": (("Net Sales", "tijori.qt_c.net_sales"), ("Net Profit", "tijori.qt_c.net_profit")),
}

_RowSpec = tuple[str, Unit, tuple[str, ...]]


def _repo_root() -> Path:
    """The checkout root, found by its marker file rather than a fixed depth."""
    here = Path(__file__).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise AssertionError("no pyproject.toml above this test file")


def _inputs() -> Any:
    """The S5 input seam, imported at call time so collection stays green."""
    return import_module("fundamentals.verify.three_source_inputs")


def _compare() -> Any:
    """The S5 comparator seam, imported at call time so collection stays green."""
    return import_module("fundamentals.verify.three_source")


def _registry_module() -> Any:
    """The S4 registry seam, imported at call time so collection stays green."""
    return import_module("fundamentals.verify.three_source_map")


def _fixture_page() -> bytes:
    """The committed synthetic Tijori page, restated in the synthetic quarter."""
    fixtures = _repo_root() / "tests" / "fundamentals" / "fixtures"
    page = (fixtures / "synthetic_tijori_financials.html").read_bytes()
    assert page.count(FIXTURE_LABEL) == 1, "the fixture's latest quarter moved"
    return page.replace(FIXTURE_LABEL, SYNTHETIC_LABEL)


def _anonymous_page() -> bytes:
    """The same page as a logged-out shell, which seals a non-OK capture."""
    page = _fixture_page()
    assert AUTHENTICATED in page, "the fixture's auth island moved"
    return page.replace(AUTHENTICATED, ANONYMOUS)


def _section_table(
    section: Section, ends: Sequence[date], rows: Sequence[_RowSpec]
) -> SectionTable:
    """One synthetic Screener section, built through the real section models."""
    table_id = f"{section.value}-data-table"
    sha = hashlib.sha256(section.value.encode("utf-8")).hexdigest()
    periods = tuple(
        Period(
            index=index,
            label=end.strftime("%b %Y"),
            kind=PeriodKind.DATE,
            date_key=end.isoformat(),
            period_end=end,
        )
        for index, end in enumerate(ends)
    )
    table_rows = tuple(
        TableRow(
            position=position,
            label=label,
            status=RowStatus.MODELED,
            unit=unit,
            cells=tuple(
                Cell(
                    period_index=index,
                    value=Decimal(raw_text),
                    raw_text=raw_text,
                    published=True,
                    provenance=Provenance(
                        source_id=SCREENER_SOURCE_ID,
                        file_sha256=sha,
                        retrieved_at=FETCHED_AT,
                        anchor_type=SourceAnchorType.HTML_TABLE,
                        table_id=table_id,
                        row_path=label,
                        column_label=periods[index].label,
                        column_index=index,
                    ),
                )
                for index, raw_text in enumerate(raw_texts)
            ),
        )
        for position, (label, unit, raw_texts) in enumerate(rows)
    )
    return SectionTable(
        section=section,
        table_id=table_id,
        outcome=SectionOutcome.OK,
        unit_statement="Consolidated Figures in Rs. Crores",
        periods=periods,
        rows=table_rows,
    )


def _metadata(*, symbol: str = SYMBOL, basis: Basis = Basis.CONSOLIDATED) -> FinancialsMetadata:
    """The provenance record written beside one acquisition's sections."""
    return FinancialsMetadata(
        source_id=SCREENER_SOURCE_ID,
        symbol=symbol,
        slug=SLUG,
        basis=basis,
        company_id=COMPANY_ID,
        page_url=f"https://example.invalid/company/{symbol}/{basis.value}/",
        page_sha256=hashlib.sha256(symbol.encode("utf-8")).hexdigest(),
        sections_requested=(Section.QUARTERS, Section.PROFIT_LOSS),
        schedule_families_requested=(),
        schedule_families_fetched=(),
        schedule_families_refused=(),
        schedule_families_unverified=(),
        complete=True,
        verified=True,
        incomplete_reason=None,
        fetched_at=FETCHED_AT,
    )


def _write_screener(root: Path, metadata: FinancialsMetadata | None) -> Path:
    """Write one acquisition's sections and metadata in the Phase 2 layout."""
    directory = root / SYMBOL / Basis.CONSOLIDATED.value
    directory.mkdir(parents=True, exist_ok=True)
    quarterly: tuple[_RowSpec, ...] = (
        ("Sales", Unit.RS_CRORE, ("16000", "17000")),
        ("Net Profit", Unit.RS_CRORE, ("880", "950")),
        ("EPS in Rs", Unit.RUPEES, ("9.90", "11.80")),
    )
    annual: tuple[_RowSpec, ...] = (("Net Profit", Unit.RS_CRORE, ("3400", "3600")),)
    tables = (
        _section_table(Section.QUARTERS, (PRIOR_END, QUARTER_END), quarterly),
        _section_table(Section.PROFIT_LOSS, (ANNUAL_END, QUARTER_END), annual),
    )
    for table in tables:
        payload = table.model_dump(mode="json")
        assert SectionTable.model_validate(payload) == table, "section dump does not round-trip"
        name = f"section_{table.section.value}.json"
        (directory / name).write_text(json.dumps(payload), encoding="utf-8")
    if metadata is not None:
        document = json.dumps(metadata.model_dump(mode="json"))
        (directory / "screener_financials_meta.json").write_text(document, encoding="utf-8")
    return root


def _gold_fact(
    concept: str,
    amount: Decimal,
    *,
    decimals: int | None = XBRL_DECIMALS,
    unit: str = CRORE_UNIT,
    scale: int = CRORE_SCALE,
) -> GoldFact:
    """One gold fact whose XBRL source value is the spine the comparator reads."""
    provenance = Provenance(
        source_id=XBRL_SOURCE_ID,
        file_sha256="b" * 64,
        anchor_type=SourceAnchorType.XBRL_CONTEXT,
        context_ref="SyntheticQuarter",
        retrieved_at=FETCHED_AT,
    )
    source_value = SourceValue.model_validate(
        {
            "source_id": XBRL_SOURCE_ID,
            "source_class": SourceClass.FIRST_PARTY.value,
            "normalized_value": str(amount),
            "normalized_unit": unit,
            "decimals": decimals,
            "provenance": provenance.model_dump(mode="json"),
        }
    )
    key = ComparisonKey(
        entity_scheme="nse-symbol",
        entity_id=SYMBOL,
        concept_qname=concept,
        period_type=PeriodType.DURATION,
        period_start=date(QUARTER_END.year, 1, 1),
        period_end=QUARTER_END,
        scope=Scope.CONSOLIDATED,
        accounting_basis=AccountingFramework.IND_AS,
        currency="INR",
        unit=unit,
        scale=scale,
    )
    return GoldFact(
        concept_qname=concept,
        comparison_key=key,
        value=str(amount),
        normalized_unit=unit,
        agreement_status=AgreementStatus.SINGLE_FIRST_PARTY,
        agreed_sources=(XBRL_SOURCE_ID,),
        corroborating_sources=(),
        incompatible_sources=(),
        first_party_source_count=1,
        needs_human_review=False,
        source_values=(source_value,),
    )


def _write_gold(path: Path, facts: Sequence[GoldFact]) -> Path:
    """Write a synthetic gold file in the canonical on-disk form."""
    gold = GoldFile(
        schema_version=GOLD_SCHEMA_VERSION, symbol=SYMBOL, quarter=QUARTER, facts=tuple(facts)
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(gold), encoding="utf-8")
    return path


def _spine(tmp_path: Path, name: str, facts: Sequence[GoldFact]) -> Any:
    """The XBRL spine, read back from a gold file written for this test."""
    path = _write_gold(tmp_path / "gold" / f"{name}.json", facts)
    return _inputs().read_gold_spine(path, symbol=SYMBOL, period_end=QUARTER_END)


def _side(side: str, amount: Decimal, ulp: Decimal, label: str, mapping_id: str | None) -> Any:
    """One side of a comparison, stated with the precision it declares."""
    inputs = _inputs()
    return inputs.SideValue(
        side=inputs.Side[side],
        amount=amount,
        half_ulp=ulp,
        unit=CRORE_UNIT,
        raw_label=label,
        period_end=QUARTER_END,
        origin="synthetic-origin",
        mapping_id=mapping_id,
    )


def _vendor_sides(side: str) -> tuple[Any, ...]:
    """One vendor's side of an otherwise-agreeing triple: sales, then net profit."""
    rows = VENDOR_ROWS[side]
    amounts = (SALES, NET_PROFIT)
    return tuple(
        _side(side, amount, CRORE_ULP, label, mapping_id)
        for amount, (label, mapping_id) in zip(amounts, rows, strict=True)
    )


def _mapping(suffix: str, concept: str, tier: EvidenceTier) -> Any:
    """One synthetic registry entry, built through the S4 model."""
    source_name, row_selector, alias_qname, role = SYNTHETIC_LINES[suffix]
    registry = _registry_module()
    return registry.SourceLineMapping(
        mapping_id=f"synthetic.{suffix}",
        source=registry.MappedSource[source_name],
        section=SYNTHETIC_SECTIONS[source_name],
        row_selector=row_selector,
        alias_qname=alias_qname,
        role=role,
        means="synthetic entry declared by this test, not a live measurement",
        exclusions=EXCLUSION if tier is TIER_ONE else (),
        tier=tier,
        concept_qnames=(concept,),
    )


def _use_registry(monkeypatch: pytest.MonkeyPatch, entries: tuple[Any, ...]) -> None:
    """Replace the seed registry for one test, wherever the comparator reads it."""
    registry = _registry_module()
    built = registry.build_registry(entries)
    monkeypatch.setattr(registry, "REGISTRY", built)
    comparator = _compare()
    if hasattr(comparator, "REGISTRY"):
        monkeypatch.setattr(comparator, "REGISTRY", built)


def _retain(monkeypatch: pytest.MonkeyPatch, root: Path, page: bytes) -> tuple[SnapshotStore, Any]:
    """Retain one scripted 200 response through the committed retention seam."""

    def envelope(source: TijoriSource, slug: str, credentials: TijoriCredentials) -> PageEnvelope:
        del source, credentials
        assert slug == SLUG
        return PageEnvelope(payload=page, status=200, media_type=MEDIA_TYPE)

    monkeypatch.setattr(TijoriSource, "_fetch_pl_envelope", envelope)
    source = TijoriSource(
        TijoriSourceConfig(
            credentials=TijoriCredentials(session_cookie=SecretStr(SESSION_VALUE)),
            expected_company_id=COMPANY_ID,
            max_retries=1,
        )
    )
    store = SnapshotStore(root)
    retention = import_module("fundamentals.ingest.tijori_retention").retain_tijori_tables(
        source, store, slug=SLUG, expected_symbol=SYMBOL
    )
    return store, retention


def _forbid_fetching(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any outbound attempt an error, so 'never fetches' is provable."""

    def refuse(*args: object, **kwargs: object) -> Any:
        raise AssertionError("a fetch was attempted while reading a retained capture")

    monkeypatch.setattr(urllib.request, "build_opener", refuse)
    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr(urllib.request.AbstractHTTPHandler, "do_open", refuse)


def _imported_modules(path: Path) -> set[str]:
    """Every module name one file imports, by parsing it rather than running it."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
    return names


def test_quarters_and_annual_net_profit_stay_distinct(tmp_path: Path) -> None:
    """A quarterly compare reads the quarters table and never the annual one.

    Both carry a "Net Profit" row and, for a March quarter, a column with the
    same period end; the annual figure in a quarterly row compares a year
    against three months and calls the gap a vendor defect.
    """
    root = _write_screener(tmp_path / "screener", _metadata())
    inputs = _inputs()
    acquired = inputs.read_screener_sections(root, symbol=SYMBOL, basis=Basis.CONSOLIDATED.value)
    assert set(acquired.sections) == {Section.QUARTERS, Section.PROFIT_LOSS}

    quarterly = inputs.screener_side_values(acquired, period_end=QUARTER_END)
    net_profit = [value for value in quarterly if value.raw_label == "Net Profit"]
    assert len(net_profit) == 1
    assert net_profit[0].mapping_id == PROFIT_MAPPING_ID
    assert net_profit[0].amount == NET_PROFIT
    assert {value.mapping_id for value in quarterly} == QUARTERS_MAPPING_IDS

    assert inputs.screener_side_values(acquired, period_end=ANNUAL_END) == ()


@pytest.mark.parametrize(
    ("metadata", "error_name"),
    [
        pytest.param(_metadata(symbol="OTHER"), "IdentityMismatchError", id="wrong_symbol"),
        pytest.param(_metadata(basis=Basis.STANDALONE), "IdentityMismatchError", id="wrong_basis"),
        pytest.param(None, "UnreadableInputError", id="missing_metadata"),
    ],
)
def test_metadata_identity_refuses(
    metadata: FinancialsMetadata | None, error_name: str, tmp_path: Path
) -> None:
    """Sections are refused unless their own metadata says who and what they are.

    A directory name is a filing convention, not evidence: standalone figures
    read as consolidated reconcile against the wrong spine and report agreement.
    """
    root = _write_screener(tmp_path / "screener", metadata)
    inputs = _inputs()
    with pytest.raises(getattr(inputs, error_name)):
        inputs.read_screener_sections(root, symbol=SYMBOL, basis=Basis.CONSOLIDATED.value)


@pytest.mark.parametrize(
    ("side", "decimals", "scale", "expected"),
    [
        pytest.param("SCREENER", 0, 1, Decimal("0.5"), id="screener_crore_integer"),
        pytest.param("SCREENER", EPS_DECIMALS, 1, Decimal("0.005"), id="screener_eps_two_places"),
        pytest.param("XBRL", XBRL_DECIMALS, CRORE_SCALE, Decimal("0.005"), id="xbrl_decimals"),
        pytest.param("TIJORI", -7, CRORE_SCALE, Decimal("0.5"), id="tijori_crore"),
    ],
)
def test_precision_contract(side: str, decimals: int, scale: int, expected: Decimal) -> None:
    """Every side's tolerance is derived from its own declared precision.

    A constant tolerance absorbs a real defect when wide and reports whole-crore
    rounding as a mismatch when narrow. No positive half-ULP means no side.
    """
    assert half_ulp(decimals, scale) == expected
    assert half_ulp(-7, CRORE_SCALE) == Decimal("0.5")
    value = _side(side, Decimal("100"), half_ulp(decimals, scale), "Synthetic Row", None)
    assert value.half_ulp == expected
    with pytest.raises(ValidationError):
        _side(side, Decimal("100"), Decimal("0"), "Synthetic Row", None)


@pytest.mark.parametrize(
    ("tier", "outside_outcome"),
    [
        pytest.param(TIER_ONE, "MISMATCH", id="tier1"),
        pytest.param(EvidenceTier.RELATED_NOT_EQUIVALENT, "ANOMALY", id="tier2"),
        pytest.param(TIER_THREE, "ANOMALY", id="tier3"),
    ],
)
def test_residual_at_summed_half_ulp_agrees_and_one_unit_outside_does_not(
    tier: EvidenceTier, outside_outcome: str
) -> None:
    """The agreement boundary is the sum of both sides' half-ULPs, exactly.

    At the boundary the figures are consistent with the precision each side
    declared and must agree; one unit in the last place beyond it they are not.
    What that is called is the tier's business: only a demonstrated equivalence
    may say "mismatch", since elsewhere the mapping may be what differs.
    """
    compare, inputs = _compare(), _inputs()
    tolerance = XBRL_ULP + CRORE_ULP
    left = _side("XBRL", SALES, XBRL_ULP, "Revenue", None)
    at_boundary = _side("SCREENER", SALES + tolerance, CRORE_ULP, "Sales", SALES_MAPPING_ID)
    outside = at_boundary.model_copy(update={"amount": at_boundary.amount + Decimal("0.001")})

    def compared(right: Any) -> Any:
        return compare.compare_pair(
            left,
            right,
            tier=tier,
            mapping_id=SALES_MAPPING_ID,
            left_side=inputs.Side.XBRL,
            right_side=inputs.Side.SCREENER,
        )

    agreed = compared(at_boundary)
    assert agreed.outcome is compare.PairOutcome.AGREE
    assert agreed.triage is compare.PairTriage.NONE
    assert agreed.tolerance == tolerance
    assert agreed.difference == tolerance

    refused = compared(outside)
    assert refused.outcome is compare.PairOutcome[outside_outcome]
    assert refused.triage is compare.PairTriage.NOISE
    if tier is TIER_THREE:
        assert any("tier 3" in reason for reason in refused.reasons)


def test_missing_sides_are_named() -> None:
    """An absent side is reported as absent, by name, never as agreement.

    A pair with nothing on one side is a hole in the evidence, and "missing"
    alone does not say which source failed to produce the row.
    """
    compare, inputs = _compare(), _inputs()
    present = _side("SCREENER", SALES, CRORE_ULP, "Sales", SALES_MAPPING_ID)

    def compared(left: Any, right: Any) -> Any:
        return compare.compare_pair(
            left,
            right,
            tier=TIER_THREE,
            mapping_id=SALES_MAPPING_ID,
            left_side=inputs.Side.XBRL,
            right_side=inputs.Side.SCREENER,
        )

    missing_left = compared(None, present)
    assert missing_left.outcome is compare.PairOutcome.MISSING_LEFT
    assert missing_left.triage is compare.PairTriage.STRUCTURAL
    assert any(inputs.Side.XBRL.value in reason for reason in missing_left.reasons)

    missing_both = compared(None, None)
    assert missing_both.outcome is compare.PairOutcome.MISSING_BOTH
    assert missing_both.triage is compare.PairTriage.STRUCTURAL


def test_unknown_precision_refuses_the_spine(tmp_path: Path) -> None:
    """A spine value with no declared precision refuses the whole comparison.

    Guessing a precision is guessing a tolerance: full precision makes every
    rounding difference a defect, a coarse guess makes real drift agree. The
    refusal names the concept, so the gold file is regenerated, not narrowed.
    """
    eps = Decimal("11.80")
    blind = _write_gold(
        tmp_path / "gold" / "blind.json",
        (
            _gold_fact(REVENUE_CONCEPT, SALES),
            _gold_fact(EPS_CONCEPT, eps, decimals=None, unit=PER_SHARE_UNIT, scale=1),
        ),
    )
    inputs = _inputs()

    with pytest.raises(inputs.PrecisionError) as refusal:
        inputs.read_gold_spine(blind, symbol=SYMBOL, period_end=QUARTER_END)
    assert refusal.value.refusal is inputs.PrecisionRefusal.UNKNOWN_PRECISION
    assert EPS_CONCEPT in str(refusal.value)

    facts = (
        _gold_fact(REVENUE_CONCEPT, SALES),
        _gold_fact(EPS_CONCEPT, eps, decimals=EPS_DECIMALS, unit=PER_SHARE_UNIT, scale=1),
    )
    spine = _spine(tmp_path, "full", facts)
    assert set(spine.values) == {REVENUE_CONCEPT, EPS_CONCEPT}
    assert spine.values[EPS_CONCEPT].half_ulp == half_ulp(EPS_DECIMALS, 1)
    assert spine.values[EPS_CONCEPT].unit == PER_SHARE_UNIT


def _mutate(values: tuple[Any, ...], mutation: MutationClass) -> tuple[Any, ...]:
    """Apply one seeded parser defect to the Screener side of a triple."""
    sales, profit = values
    if mutation is MutationClass.DROP_ROW:
        return (profit,)
    if mutation is MutationClass.ROW_SWAP:
        return (
            sales.model_copy(update={"amount": profit.amount}),
            profit.model_copy(update={"amount": sales.amount}),
        )
    replacements: dict[MutationClass, dict[str, Any]] = {
        MutationClass.SIGN_FLIP: {"amount": -sales.amount},
        MutationClass.SCALE_10: {"amount": sales.amount * 10},
        MutationClass.SCALE_100: {"amount": sales.amount * 100},
        MutationClass.THOUSANDS_TRUNCATED: {"amount": sales.amount / 1000},
        MutationClass.UNIT_DRIFT: {"unit": "INR million"},
        MutationClass.STALE_PERIOD: {"amount": PRIOR_SALES},
        MutationClass.COLUMN_SHIFT: {"amount": NEIGHBOUR_SALES},
    }
    return (sales.model_copy(update=replacements[mutation]), profit)


@pytest.mark.parametrize(
    ("mutation", "expected_outcome", "names_itself"),
    [
        pytest.param(MutationClass.DROP_ROW, "MISSING_RIGHT", False, id="drop_row"),
        pytest.param(MutationClass.SIGN_FLIP, None, True, id="sign_flip"),
        pytest.param(MutationClass.SCALE_10, None, True, id="scale_10"),
        pytest.param(MutationClass.SCALE_100, None, True, id="scale_100"),
        pytest.param(MutationClass.THOUSANDS_TRUNCATED, None, True, id="thousands_truncated"),
        pytest.param(MutationClass.UNIT_DRIFT, "NOT_COMPARABLE", False, id="unit_drift"),
        pytest.param(MutationClass.STALE_PERIOD, None, False, id="stale_period"),
        pytest.param(MutationClass.COLUMN_SHIFT, None, False, id="column_shift"),
        pytest.param(MutationClass.ROW_SWAP, None, False, id="row_swap"),
    ],
)
def test_seeded_mutations_are_detected(
    mutation: MutationClass, expected_outcome: str | None, names_itself: bool, tmp_path: Path
) -> None:
    """Every seeded extractor defect breaks agreement on the side that carries it.

    This is the comparator's own sensitivity measurement: a class that survives
    is one this report would never surface. The untouched Tijori side must keep
    agreeing, which separates detection from a comparator that fails everything.
    """
    compare = _compare()
    facts = (
        _gold_fact(REVENUE_CONCEPT, SALES),
        _gold_fact(PROFIT_CONCEPTS[0], NET_PROFIT),
        _gold_fact(PROFIT_CONCEPTS[1], NET_PROFIT),
    )
    report = compare.compare_triple(
        _spine(tmp_path, "agreeing", facts),
        _mutate(_vendor_sides("SCREENER"), mutation),
        _vendor_sides("TIJORI"),
        symbol=SYMBOL,
        period_end=QUARTER_END,
    )

    revenue_row = next(row for row in report.rows if row.concept_qname == REVENUE_CONCEPT)
    screener_pair = revenue_row.pairs[0]
    assert screener_pair.outcome is not compare.PairOutcome.AGREE
    assert all(row.pairs[1].outcome is compare.PairOutcome.AGREE for row in report.rows)

    if expected_outcome is not None:
        assert screener_pair.outcome is compare.PairOutcome[expected_outcome]
    if names_itself:
        assert any(mutation.value in reason for reason in screener_pair.reasons)
        assert screener_pair.triage is compare.PairTriage.STRUCTURAL
    if mutation is MutationClass.ROW_SWAP:
        swapped = [row for row in report.rows if row.screener is not None]
        assert swapped and all(
            row.pairs[0].outcome is not compare.PairOutcome.AGREE for row in swapped
        )


def test_two_candidates_keep_their_own_tiers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each mapped line concludes only what its own tier entitles it to.

    Two lines can carry the identical number and still deserve different
    verdicts, because a tier describes the mapping, not the value. One tier for
    the whole run promotes unproven lines or silences demonstrated ones.
    """
    _use_registry(
        monkeypatch, (_mapping("alpha", ALPHA, TIER_ONE), _mapping("beta", BETA, TIER_THREE))
    )
    compare = _compare()
    drifted = SALES + Decimal("5")
    spine = _spine(tmp_path, "tiers", (_gold_fact(ALPHA, drifted), _gold_fact(BETA, drifted)))
    equal_values = tuple(
        _side("TIJORI", SALES, CRORE_ULP, SYNTHETIC_LINES[suffix][1], f"synthetic.{suffix}")
        for suffix in ("alpha", "beta")
    )

    report = compare.compare_triple(spine, (), equal_values, symbol=SYMBOL, period_end=QUARTER_END)
    rows = {row.concept_qname: row for row in report.rows}
    assert set(rows) == {ALPHA, BETA}
    demonstrated, unproven = rows[ALPHA].pairs[1], rows[BETA].pairs[1]
    assert demonstrated.tier is TIER_ONE
    assert demonstrated.outcome is compare.PairOutcome.MISMATCH
    assert unproven.tier is TIER_THREE
    assert unproven.outcome is compare.PairOutcome.ANOMALY


def test_tijori_capture_read_never_fetches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A retained Tijori capture becomes side values offline, or is refused.

    Re-deriving must work with the vendor unreachable and must carry the capture
    id forward, so a difference traces back to the exact retained bytes. A sealed
    non-OK capture is refused: a logged-out shell is not an empty company.
    """
    store, retention = _retain(monkeypatch, tmp_path / "snapshots", _fixture_page())
    record = retention.record
    inputs = _inputs()

    def read(retained: Any) -> Any:
        return inputs.read_tijori_capture(
            store,
            retained,
            slug=SLUG,
            expected_symbol=SYMBOL,
            expected_company_id=COMPANY_ID,
            period_end=QUARTER_END,
        )

    _forbid_fetching(monkeypatch)
    values = read(record)
    assert len(values) == 3
    assert {value.mapping_id for value in values} == TIJORI_MAPPING_IDS
    assert {value.amount for value in values} == {SALES, PBT, NET_PROFIT}
    assert all(value.origin == record.capture_id for value in values)
    assert all(value.half_ulp == Decimal("0.5") for value in values)
    assert all(value.unit == CRORE_UNIT for value in values)
    assert all(value.period_end == QUARTER_END for value in values)

    _, refused = _retain(monkeypatch, tmp_path / "refused", _anonymous_page())
    _forbid_fetching(monkeypatch)
    with pytest.raises(inputs.InputError):
        read(refused.record)


def test_report_counts_and_warn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The report totals what it found and warns only when a verdict earns it.

    An operator reads the header, not the rows: a warn flag raised by every
    unproven anomaly is ignored within a week, and one that stays down while a
    demonstrated line mismatches is worse. The inputs are echoed for re-derivation.
    """
    entries = (_mapping("screener", ALPHA, TIER_ONE), _mapping("alpha", ALPHA, TIER_ONE))
    _use_registry(monkeypatch, entries)
    compare = _compare()
    spine = _spine(tmp_path, "counts", (_gold_fact(ALPHA, SALES),))
    screener = _side("SCREENER", SALES, CRORE_ULP, "Sales", "synthetic.screener")
    tijori = _side("TIJORI", SALES, CRORE_ULP, "Net Sales", "synthetic.alpha")
    capture_ids = ("20270420T093000Z-synthetic",)

    def report(screener_sides: tuple[Any, ...], tijori_sides: tuple[Any, ...]) -> Any:
        return compare.compare_triple(
            spine,
            screener_sides,
            tijori_sides,
            symbol=SYMBOL,
            period_end=QUARTER_END,
            capture_ids=capture_ids,
        )

    agreed = report((screener,), (tijori,))
    assert agreed.counts[compare.PairOutcome.AGREE] == 3
    assert agreed.warn is False
    assert agreed.map_version == _registry_module().MAP_VERSION
    assert agreed.capture_ids == capture_ids
    assert agreed.gold_sha256 == spine.gold_sha256

    drifted = report((screener.model_copy(update={"amount": SALES + Decimal("40")}),), ())
    assert drifted.counts[compare.PairOutcome.MISMATCH] == 1
    assert drifted.warn is True


def test_package_rail() -> None:
    """The comparator stays a leaf: no command layer, no store, no reconciler.

    Its value is being re-runnable over retained evidence without an acquisition.
    An ``api`` import drags the CLI's exits into a pure comparison; ``store`` or
    ``reconcile`` lets a report re-fetch or re-adjudicate what it only reads.
    """
    verify_dir = _repo_root() / "src" / "fundamentals" / "verify"
    comparator, reader = verify_dir / "three_source.py", verify_dir / "three_source_inputs.py"
    for path in (comparator, reader):
        assert path.is_file(), f"{path.name} does not exist yet"
        imported = _imported_modules(path)
        assert not any(name.startswith("fundamentals.api") for name in imported), path.name
    comparator_imports = _imported_modules(comparator)
    for barred in ("fundamentals.store", "fundamentals.reconcile"):
        assert not any(name.startswith(barred) for name in comparator_imports), barred
