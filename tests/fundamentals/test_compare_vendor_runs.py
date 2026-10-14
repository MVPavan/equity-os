"""D1b.2 vendor sides over stored evidence on PostgreSQL (data spec §2, §4, §5).

Retained captures only; expected values read by hand from the files (crore).

- LAURUSLABS (the run test): Q3 FY25 consolidated XBRL (``data/raw/watchlist/lauruslabs``,
  SHA-256 2d50d29a…cfa6, ``decimals="-7"``, ± 0.5): revenue 14150500000 (1415.05),
  continuing PAT 90.61. Screener Dec 2024 Sales "1,415" (± 0.5). Tijori qt_c Dec 2024
  (2026-09-05) Net Sales 1415.05 rendered "1,415" (> 100: ± 0.5), Net Profit 90.61 (≤ 100:
  ± 0.005). No
  LAURUSLABS Upstox capture is retained.
- POLYCAB (cases b–d): Q3 FY25 XBRL revenue 5226.062, continuing PAT 464.348; Screener Dec
  2024 Sales "5,226", Mar 2026 Profit before tax "1,049"; Tijori qt_c Dec 2024 Net Sales
  5226.062. Upstox (2026-10-14): the quarterly summary starts at Sep 2025 (no Dec 2024), its
  Mar 2026 ``operating_profit`` is 1049.29; the yearly capture's summary ``revenue`` and
  ``full_statement`` "Total Revenue" for Mar 2026 are both 29120.04.

No retained first-party filing shares a key with an Upstox capture, so cases (b)–(d) pair the
stored vendor evidence with a constructed first-party side; with Upstox precision undocumented
(owner amendment 2026-10-14) every Upstox pair is ``NOT_COMPARABLE``/``PRECISION_UNSUPPORTED``
whatever that side holds.
"""

from __future__ import annotations

import hashlib
import shutil
from datetime import date
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any, NamedTuple

import pytest
from test_evidence_vendor import RETAINED, screener, tijori, upstox
from vendor_retained_support import RAW_ROOT, retained_page, stage_registered

from fundamentals.compare.resolve_loader import RunLoader
from fundamentals.compare.routing import route_pair_draft
from fundamentals.compare.run import (
    DatabaseIdentity,
    RunStatus,
    execute_run,
    load_results,
    replay_run,
    request_for,
)
from fundamentals.compare.run_config import ConfigVersions, load_run_config
from fundamentals.compare.run_models import PairRecord, ResultRow, RunRequest, SourceValue
from fundamentals.compare.tables import ComparisonSide, PairResult, SourceQualifiedPair
from fundamentals.compare.vendor_sides import VendorRow, VendorSides, internal_conflict
from fundamentals.contracts.basis_status import BasisStatus
from fundamentals.contracts.canonical import (
    ApplicabilityStatus,
    Basis,
    Representation,
    ValueKind,
)
from fundamentals.contracts.comparison import (
    CorroborationStatus,
    ExtractionStatus,
    PairKind,
    PairOutcome,
    ReasonCode,
    SourceState,
)
from fundamentals.contracts.evidence import FilingFamily
from fundamentals.contracts.evidence_tier import EvidenceTier
from fundamentals.contracts.interval import Interval
from fundamentals.contracts.measurement_key import DimensionSet, MeasurementKey, PeriodInterval
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.review_queue import QueueSeverity
from fundamentals.contracts.source_catalog import BUILTIN_SOURCES
from fundamentals.evidence import vendor_tijori
from fundamentals.evidence.capture_intake import retained_intake_from_manifest
from fundamentals.evidence.first_party_ingest import ingest_first_party
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.evidence.vendor_ingest import VendorIngestRequest, ingest_vendor
from fundamentals.ingest.screener_financials_models import Section
from fundamentals.pg.identity_seed import (
    IdentityCitation,
    IssuerIdentityInput,
    seed_issuer_identity,
)
from fundamentals.store.snapshot_store import SnapshotStore

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "config"
VERSIONS = ConfigVersions(dictionary="v2", mapping_set="v2")
CRORE = Decimal(10) ** 7
Q3_END = date(2024, 12, 31)
Q4_END = date(2026, 3, 31)
Q3 = PeriodInterval.duration(date(2024, 10, 1), Q3_END)
Q4 = PeriodInterval.duration(date(2026, 1, 1), Q4_END)
FY26 = PeriodInterval.duration(date(2025, 4, 1), Q4_END)


class Company(NamedTuple):
    """One retained issuer: identity, Q3 FY25 consolidated XBRL and Tijori capture."""

    symbol: str
    name: str
    isin: str
    bse_scrip: str
    xbrl: Path
    xbrl_sha256: str
    pdf_sha256: str
    isin_cited: bool
    tijori: tuple[str, str, str, str]


POLYCAB = Company(
    symbol="POLYCAB",
    name="Polycab India Limited",
    isin="INE455K01017",
    bse_scrip="542652",
    xbrl=Path("nse") / "INDAS_117488_1357164_22012025051528.xml",
    xbrl_sha256="05ebba47a2a07015f107cc9ca3a616138e4a78b900f43074cbfd489db011518d",
    pdf_sha256="8602f194f97ca8f045f2c878c9c3a7e111bc73f1398a9e2ba5c0bb2a8b10a71c",
    isin_cited=True,
    tijori=("tijori", "financials", "polycab-india-ltd", "20260905T113246.459386Z-9bc61e44e378"),
)
LAURUS = Company(
    symbol="LAURUSLABS",
    name="Laurus Labs Limited",
    isin="NOT-EVIDENCED",  # no retained capture states it; no XBRL ISIN fact to check against
    bse_scrip="540222",
    xbrl=Path("nse") / "INDAS_117690_1360957_24012025084417.xml",
    xbrl_sha256="2d50d29a467b9035f8124f7a9576346b7d36888e9895befc3363e3c5d227cfa6",
    pdf_sha256="2b79047e7d2e7c4f46eb3dfe56e1aff03d5871b92df1b24e63ffd0cd89c5b517",
    isin_cited=False,
    tijori=("tijori", "financials", "laurus-labs", "20260905T113024.330612Z-a99ac5398de1"),
)
SCREENER_PAGE = ("screener-subscriber", "SCREENER_FINANCIALS")
UPSTOX_QUARTERLY = (
    "upstox",
    "income-statement",
    "default-cfca1e489fa27667b6cd3de0",
    "20261014T071522.096013Z-94ef72092672",
)
UPSTOX_YEARLY = (
    "upstox",
    "income-statement",
    "default-b636f635905a6e1bef09c66e",
    "20261014T071520.998756Z-54565f20a050",
)
UPSTOX_SURFACE = "income-statement"
UPSTOX_SUMMARY = "income-statement:upstox-income-statement-summary-v2"
UPSTOX_FULL = "income-statement:upstox-income-statement-full-statement-v2"
VENDORS = (SCREENER_PAGE, ("tijori", "financials"), ("upstox", UPSTOX_SURFACE))


class Issuer:
    """One seeded company entity with stored first-party and vendor evidence."""

    def __init__(
        self,
        company: Company,
        pg_db: Any,
        pool: Any,
        tmp_path: Path,
        versions: ConfigVersions = VERSIONS,
    ) -> None:
        self.company = company
        self.versions = versions
        self.pg_db = pg_db
        self.pool = pool
        self.repository = EvidenceRepository(pool)
        self.tmp_path = tmp_path
        self.config = load_run_config(CONFIG, versions)
        self.entity_id = _seed(pool, company)
        (tmp_path / "staged").mkdir(mode=0o700)
        self.staged = SnapshotStore(tmp_path / "staged")

    def first_party(self) -> None:
        """Ingest the retained Q3 FY25 consolidated XBRL (the only first-party member)."""
        inputs, store = self.tmp_path / "inputs", self.tmp_path / "store"
        for folder in (inputs, inputs / "nse", store):
            folder.mkdir(mode=0o700)
        xbrl = self.company.xbrl
        shutil.copyfile(RAW_ROOT / self.company.symbol.lower() / xbrl, inputs / xbrl)
        # filed_at_nse is the retained NSE listing's broadCastDate for this filing.
        intake = retained_intake_from_manifest(
            RAW_ROOT / self.company.symbol.lower() / "retrieval-manifest.json",
            issuer=self.company.symbol,
            quarter="FY25_Q3",
            kinds={Representation.XBRL: "xbrl-consolidated"},
            store_root=store.absolute(),
            input_root=inputs.absolute(),
            issuer_config=None,
        )
        report = ingest_first_party(
            intake=intake,
            catalog=BUILTIN_SOURCES,
            snapshot_store=SnapshotStore(store),
            repository=self.repository,
            dictionary=self.config.dictionary,
            mapping_set=self.config.mapping_set,
            policy=self.config.normalisation_policy,
            entity_id=self.entity_id,
            basis=Basis.CONSOLIDATED,
            framework=AccountingFramework.IND_AS,
            family=FilingFamily.FINANCIAL_RESULTS,
            reporting_period_end=Q3_END,
            pdf_specs=None,
        )
        assert report.package_id is not None

    def vendor(self, capture: tuple[str, ...], adapter: Any, version: str, end: date) -> Any:
        """Ingest one vendor capture (a Screener page is staged first) for a period end."""
        store = SnapshotStore(RETAINED)
        if capture[:2] == SCREENER_PAGE:
            request, _, _ = retained_page(self.company.symbol)
            staged = stage_registered(request, self.repository, self.staged)
            store, capture = self.staged, (*SCREENER_PAGE, staged.request_key, staged.capture_id)
        return ingest_vendor(
            VendorIngestRequest(
                source_id=capture[0],
                surface=capture[1],
                request_key=capture[2],
                capture_id=capture[3],
                representation=Representation.JSON
                if capture[0] == "upstox"
                else Representation.HTML,
                entity_id=self.entity_id,
                period_end=end,
                basis=Basis.CONSOLIDATED,
                framework=AccountingFramework.IND_AS,
            ),
            extract=adapter,
            extractor_version=version,
            snapshot_store=store,
            repository=self.repository,
            dictionary=self.config.dictionary,
            mapping_set=self.config.mapping_set,
            policy=self.config.normalisation_policy,
            rounding_policy=self.config.rounding,
            fiscal_year_end_month=3,
        )

    def screener(self, end: date) -> Any:
        return self.vendor(
            (*SCREENER_PAGE, "", ""),
            screener(self.company.symbol, Basis.CONSOLIDATED, Section.QUARTERS),
            "screener-v1",
            end,
        )

    def tijori(self, capture_id: str | None = None) -> Any:
        capture = (*self.company.tijori[:3], capture_id or self.company.tijori[3])
        adapter = tijori(self.company.tijori[2], self.company.symbol)
        return self.vendor(capture, adapter, vendor_tijori.EXTRACTOR_VERSION, Q3_END)

    def upstox(self, capture: tuple[str, ...]) -> Any:
        return self.vendor(capture, upstox(Basis.CONSOLIDATED), "upstox-v2", Q4_END)

    def request(self, end: date, vendors: tuple[tuple[str, str], ...] = VENDORS) -> RunRequest:
        settings = self.pg_db.settings
        return request_for(
            self.entity_id,
            end,
            Basis.CONSOLIDATED,
            cutoff=self.repository.store_clock(),
            config_root=CONFIG,
            code_version="test-commit",
            database_identity=DatabaseIdentity(
                host=settings.host, port=settings.port, name=self.pg_db.dbname
            ),
            vendors=vendors,
            versions=self.versions,
        )

    def sides(
        self,
        key: MeasurementKey,
        first_party: ComparisonSide,
        *,
        pdf: ComparisonSide | None = None,
        vendors: tuple[tuple[str, str], ...] = VENDORS,
        extraction: ExtractionStatus = ExtractionStatus.ONE_SIDE_XBRL,
    ) -> VendorRow:
        """The vendor sides of one key over the stored evidence the real loader reads."""
        request = self.request(Q4_END if key.period.end == Q4_END else Q3_END, vendors)
        loader = RunLoader(request, self.repository)
        loader.load()
        return VendorSides(loader.inputs(0), request, config=self.config).row(
            key,
            fiscal_month=3,
            applicability=ApplicabilityStatus.APPLICABLE,
            extraction=extraction,
            first_party={
                Representation.XBRL: first_party,
                Representation.PDF: pdf or _side(key, None),
            },
        )


@pytest.fixture
def polycab(pg_db: Any, tmp_path: Path) -> Any:
    with pg_db.runtime_pool() as pool:
        yield Issuer(POLYCAB, pg_db, pool, tmp_path)


@pytest.fixture
def laurus(pg_db: Any, tmp_path: Path) -> Any:
    with pg_db.runtime_pool() as pool:
        yield Issuer(LAURUS, pg_db, pool, tmp_path)


@pytest.mark.pg
@pytest.mark.retained
def test_vendor_run_corroborates_fails_closed_and_replays(laurus: Issuer) -> None:
    """Corroboration pairs and state vector; a later failed Tijori attempt makes its cells
    ``UNAVAILABLE`` and the run ``INCOMPLETE`` (no fallback); replay reproduces both runs."""
    laurus.first_party()
    laurus.screener(Q3_END)
    laurus.tijori()
    record = execute_run(laurus.request(Q3_END), pool=laurus.pool, config_root=CONFIG)
    assert record.manifest.status is RunStatus.COMPLETE
    assert record.manifest.scope.vendors == tuple(sorted(VENDORS))
    assert [pin.source_id for pin in record.manifest.pinned.vendor_extractors] == [
        "screener-subscriber",
        "tijori",
        "upstox",
    ]
    rows = load_results(record.run_id, pool=laurus.pool)
    revenue = _row(rows, "revenue_from_operations")
    assert revenue.corroboration_status is CorroborationStatus.AGREES_UNQUALIFIED
    # XBRL-only package (no PDF member or attempt): no extraction pair (Sol D2).
    assert revenue.extraction_status is ExtractionStatus.NOT_APPLICABLE
    assert _states(revenue) == {
        "XBRL": SourceState.VALUE,
        "PDF": SourceState.NO_VALUE,
        "screener-subscriber/SCREENER_FINANCIALS": SourceState.VALUE,
        "tijori/financials": SourceState.VALUE,
    }
    assert _crore(revenue, "screener-subscriber/SCREENER_FINANCIALS") == (
        Decimal("1415"),
        Decimal("1414.5"),
        Decimal("1415.5"),
    )
    assert _crore(revenue, "tijori/financials") == (  # rendered "1,415" (island 1415.05)
        Decimal("1415"),
        Decimal("1414.5"),
        Decimal("1415.5"),
    )
    assert _pairs(revenue) == {
        ("CORROBORATION", "XBRL", "screener-subscriber/SCREENER_FINANCIALS"): (
            PairOutcome.AGREE_UNQUALIFIED,
            Decimal("0.05") * CRORE,
        ),
        ("CORROBORATION", "XBRL", "tijori/financials"): (
            PairOutcome.AGREE_UNQUALIFIED,
            Decimal("0.05") * CRORE,
        ),
    }
    pat = _row(rows, "profit_continuing_after_tax")
    assert pat.corroboration_status is CorroborationStatus.AGREES_UNQUALIFIED
    assert _crore(pat, "tijori/financials") == (
        Decimal("90.61"),
        Decimal("90.605"),
        Decimal("90.615"),
    )
    # Upstox (diagnostic) maps total income; no LAURUSLABS attempt exists, which never
    # makes the run incomplete.
    total_income = _row(rows, "total_income")
    assert total_income.corroboration_status is CorroborationStatus.FILING_ONLY
    upstox_value = _value(total_income, f"upstox/{UPSTOX_SUMMARY}")
    assert (upstox_value.state, upstox_value.reason) == (SourceState.UNAVAILABLE, "NO_ATTEMPT")
    assert replay_run(record.run_id, pool=laurus.pool, config_root=CONFIG) == rows

    failed = laurus.tijori("20260905T000000.000000Z-000000000000")
    rerun = execute_run(laurus.request(Q3_END), pool=laurus.pool, config_root=CONFIG)
    assert rerun.run_id != record.run_id
    assert rerun.manifest.status is RunStatus.INCOMPLETE
    assert rerun.manifest.operational_failures == (
        f"tijori/financials\tFAILED\tattempt={failed.attempt.attempt_id}",
    )
    rows = load_results(rerun.run_id, pool=laurus.pool)
    revenue = _row(rows, "revenue_from_operations")
    assert _states(revenue)["tijori/financials"] is SourceState.UNAVAILABLE
    assert revenue.corroboration_status is CorroborationStatus.AGREES_UNQUALIFIED  # Screener
    pat = _row(rows, "profit_continuing_after_tax")
    assert pat.corroboration_status is CorroborationStatus.UNAVAILABLE  # Tijori is its only vendor
    assert replay_run(rerun.run_id, pool=laurus.pool, config_root=CONFIG) == rows


@pytest.mark.pg
@pytest.mark.retained
def test_upstox_diagnostic_pairs_against_first_party_and_screener(polycab: Issuer) -> None:
    """(b): Upstox pairs vs first-party and vs Screener are diagnostic, ``NOT_COMPARABLE``/
    ``PRECISION_UNSUPPORTED``, routed MEDIUM, and never change the status."""
    polycab.screener(Q4_END)
    attempt = polycab.upstox(UPSTOX_QUARTERLY).attempt.attempt_id
    key = _key("profit_before_tax", Q4, polycab.entity_id)
    first_party = _side(key, Decimal("1049.29"))
    found = polycab.sides(key, first_party)
    assert {value.surface: value.state for value in found.values} == {
        "SCREENER_FINANCIALS": SourceState.VALUE,
        UPSTOX_SUMMARY: SourceState.INVALID,
    }
    diagnostics = [pair for pair in found.pairs if pair.pair_kind is PairKind.DIAGNOSTIC]
    assert sorted((pair.left.source_id or "XBRL", pair.right.surface) for pair in diagnostics) == [
        ("XBRL", UPSTOX_SUMMARY),
        ("screener-subscriber", UPSTOX_SUMMARY),
    ]
    for pair in diagnostics:
        assert (pair.outcome, pair.reason) == (
            PairOutcome.NOT_COMPARABLE,
            ReasonCode.PRECISION_UNSUPPORTED,
        )
        draft = route_pair_draft(_qualified(pair, attempt), key=key)
        assert draft is not None and draft.severity is QueueSeverity.MEDIUM and draft.diagnostic
    without_upstox = polycab.sides(key, first_party, vendors=(SCREENER_PAGE,))
    assert (found.status, found.reason) == (without_upstox.status, without_upstox.reason)
    # Screener prints 1,049 (± 0.5): the corroboration pair is Screener's alone.
    assert found.status is CorroborationStatus.AGREES_UNQUALIFIED


@pytest.mark.pg
@pytest.mark.retained
def test_vendor_pairs_against_other_representation_when_extraction_disagrees(
    polycab: Issuer,
) -> None:
    """(c): extraction not ``AGREE`` adds each vendor's diagnostic pair against the other
    representation; the status still comes from the representative's pairs only."""
    polycab.screener(Q3_END)
    polycab.tijori()
    key = _key("revenue_from_operations", Q3, polycab.entity_id)
    xbrl = _side(key, Decimal("5226.062"), half=Decimal("0.05"))
    pdf = _side(key, Decimal("52260.62"), half=Decimal("0.005"))  # a scale-fault PDF read
    found = polycab.sides(
        key, xbrl, pdf=pdf, vendors=VENDORS[:2], extraction=ExtractionStatus.DISAGREE
    )
    kinds = sorted((pair.pair_kind.value, pair.left.representation.value) for pair in found.pairs)
    assert kinds == [
        ("CORROBORATION", "XBRL"),
        ("CORROBORATION", "XBRL"),
        ("DIAGNOSTIC", "PDF"),
        ("DIAGNOSTIC", "PDF"),
    ]
    for pair in found.pairs:
        expected = PairOutcome.AGREE_UNQUALIFIED
        if pair.pair_kind is PairKind.DIAGNOSTIC:
            expected = PairOutcome.ANOMALY
        assert pair.outcome is expected
    assert found.status is CorroborationStatus.AGREES_UNQUALIFIED


@pytest.mark.pg
@pytest.mark.retained
def test_upstox_summary_and_full_statement_both_survive(polycab: Issuer) -> None:
    """(d): one Upstox capture's summary and ``full_statement`` on one key are two sides, both
    occurrences retained; equal declared periodicity and no precision raise no conflict, so
    each table's pair is ``NOT_COMPARABLE``/``PRECISION_UNSUPPORTED``, MEDIUM."""
    polycab.upstox(UPSTOX_YEARLY)
    key = _key("total_income", FY26, polycab.entity_id)
    found = polycab.sides(key, _side(key, Decimal("29120.04")))
    values = {value.surface: value for value in found.values}
    assert set(values) == {UPSTOX_SUMMARY, UPSTOX_FULL}
    assert all(value.state is SourceState.INVALID for value in values.values())
    assert all(value.reason == "PRECISION_UNSUPPORTED" for value in values.values())
    ids = {value.interpretation_id for value in values.values()}
    assert len(ids) == 2 and None not in ids
    assert sorted((pair.right.surface, pair.outcome, pair.reason) for pair in found.pairs) == [
        (UPSTOX_FULL, PairOutcome.NOT_COMPARABLE, ReasonCode.PRECISION_UNSUPPORTED),
        (UPSTOX_SUMMARY, PairOutcome.NOT_COMPARABLE, ReasonCode.PRECISION_UNSUPPORTED),
    ]
    assert found.status is CorroborationStatus.FILING_ONLY


@pytest.mark.parametrize(
    ("first", "other", "conflict"),
    [
        ((Decimal("100"), Decimal("0.5"), 3), (Decimal("102"), Decimal("0.5"), 3), True),
        ((Decimal("100"), Decimal("0.5"), 3), (Decimal("100.8"), Decimal("0.5"), 3), False),
        ((Decimal("100"), None, 3), (Decimal("100"), None, 12), True),
        ((Decimal("100"), None, 12), (Decimal("250"), None, 12), False),
    ],
    ids=["disjoint-intervals", "overlapping", "contradictory-periodicity", "no-evidence"],
)
def test_internal_conflict_rule(
    first: tuple[Decimal, Decimal | None, int],
    other: tuple[Decimal, Decimal | None, int],
    conflict: bool,
) -> None:
    """Within-vendor conflict (spec §2): disjoint intervals or contradictory declared
    periodicity; without precision (Upstox) only the periodicity route can fire."""
    key = _key("total_income", FY26)
    left, right = (_side(key, amount, half=half) for amount, half, _ in (first, other))
    assert internal_conflict(left, right, (first[2], other[2])) is conflict


def _seed(pool: Any, company: Company) -> int:
    """The company's identity, cited to its retained Q3 FY25 XBRL and results PDF."""
    xbrl = {"capture_sha256": company.xbrl_sha256, "context_ref": "OneD"}
    pdf = {"capture_sha256": company.pdf_sha256, "pages": (1,)}
    isin = (IdentityCitation(field="isin", **pdf),) if company.isin_cited else ()
    identity = IssuerIdentityInput(
        entity_key=company.symbol,
        display_name=company.name,
        isin=company.isin,
        share_class="EQUITY",
        nse_symbol=company.symbol,
        bse_scrip=company.bse_scrip,
        basis_status=BasisStatus.CONSOLIDATED_AND_STANDALONE,
        fiscal_year_end_month=3,
        citations=(
            IdentityCitation(field="display_name", native_field="NameOfTheCompany", **xbrl),
            *isin,
            IdentityCitation(field="nse_symbol", native_field="Symbol", **xbrl),
            IdentityCitation(field="bse_scrip", native_field="ScripCode", **xbrl),
            IdentityCitation(
                field="fiscal_year_end_month", native_field="DateOfEndOfFinancialYear", **xbrl
            ),
            IdentityCitation(field="basis_status", **pdf),
        ),
        content_sha256=hashlib.sha256(f"D1b.2 {company.symbol} test identity".encode()).hexdigest(),
    )
    with pool.connection() as conn:
        return seed_issuer_identity(conn, identity).entity_ids[company.symbol]


def _key(canonical_id: str, period: PeriodInterval, entity_id: int = 0) -> MeasurementKey:
    return MeasurementKey(
        entity_id=entity_id,
        canonical_id=canonical_id,
        period=period,
        basis=Basis.CONSOLIDATED,
        framework=AccountingFramework.IND_AS,
        currency="INR",
        value_kind=ValueKind.CURRENCY_AMOUNT,
        dimensions=DimensionSet(),
    )


def _side(
    key: MeasurementKey, crore: Decimal | None, *, half: Decimal | None = Decimal("0.005")
) -> ComparisonSide:
    """A constructed side (``NO_VALUE`` without an amount; no interval without precision)."""
    interval = None
    if crore is not None and half is not None:
        middle = Fraction(crore * CRORE)
        interval = Interval(
            lower=middle - Fraction(half * CRORE), upper=middle + Fraction(half * CRORE)
        )
    return ComparisonSide(
        key=key,
        state=SourceState.NO_VALUE if crore is None else SourceState.VALUE,
        value=None if crore is None else crore * CRORE,
        interval=interval,
        tier=EvidenceTier.EQUIVALENCE_UNPROVEN,
        aligned_by_proof=False,
        mapping_entry_ids=(),
        package_id=None,
        calculation_state=None,
        reasons=(),
    )


def _row(rows: tuple[ResultRow, ...], canonical_id: str) -> ResultRow:
    (found,) = [
        row
        for row in rows
        if row.key.canonical_id == canonical_id
        and row.key.period == Q3
        and row.value_identity.value == "REPORTED"
    ]
    return found


def _label(value: SourceValue | Any) -> str:
    return (
        value.representation.value
        if value.source_id is None
        else f"{value.source_id}/{value.surface}"
    )


def _states(row: ResultRow) -> dict[str, SourceState]:
    return {_label(value): value.state for value in row.source_values}


def _value(row: ResultRow, label: str) -> SourceValue:
    (value,) = [item for item in row.source_values if _label(item) == label]
    return value


def _crore(row: ResultRow, label: str) -> tuple[Decimal, Decimal, Decimal]:
    value = _value(row, label)
    assert value.value is not None and value.lower is not None and value.upper is not None
    return value.value / CRORE, value.lower / CRORE, value.upper / CRORE


def _pairs(row: ResultRow) -> dict[tuple[str, str, str], tuple[PairOutcome, Decimal | int]]:
    return {
        (pair.pair_kind.value, _label(pair.left), _label(pair.right)): (
            pair.outcome,
            pair.difference if pair.difference is not None else 0,
        )
        for pair in row.pairs
        if pair.pair_kind is not PairKind.EXTRACTION
    }


def _qualified(pair: PairRecord, attempt_id: int) -> SourceQualifiedPair:
    """A stored pair as routed, evidenced by the Upstox attempt."""
    return SourceQualifiedPair(
        attempt_ids=(attempt_id,),
        pair_kind=pair.pair_kind,
        left=pair.left,
        right=pair.right,
        result=PairResult.model_validate(pair.model_dump(include=set(PairResult.model_fields))),
    )
