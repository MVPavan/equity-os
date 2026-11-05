"""Shared fixtures and helpers for the first-party evidence tests (D1a Task 5).

Every PostgreSQL case runs in its own ``eqos_test_*`` database from the shared harness and
reads the retained Apar originals (hash-pinned, never edited). Marked copies — XBRL byte
edits and PDF text-layer redactions — are written under ``tmp_path`` from the originals.
Test modules import the fixtures by name and list them in ``__all__``.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Iterator, Mapping
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml
from pg_support import PgTestDatabase
from psycopg import sql
from retained_support import (
    REPO_ROOT,
    MarkedEdit,
    apar_catalog,
    apar_intake,
    apar_original,
    apar_store,
    marked_copy,
    seed_apar,
)

from equity_os.contracts.measurement.canonical import (
    Basis,
    PeriodKind,
    Representation,
    StatementFamily,
)
from equity_os.contracts.measurement.evidence import (
    FilingFamily,
    FilingPackage,
    Interpretation,
    MissingValueState,
    Occurrence,
)
from equity_os.contracts.measurement.evidence_tier import EvidenceTier
from equity_os.contracts.measurement.measurement_key import PeriodInterval
from equity_os.contracts.measurement.observation import AccountingFramework
from equity_os.contracts.measurement.qualification import QualificationContext
from equity_os.contracts.sourcing.source_catalog import SourceCatalog
from equity_os.extraction.packages.capture_intake import RetainedIntake
from equity_os.extraction.packages.first_party_ingest import IngestReport, ingest_first_party
from equity_os.extraction.results_pdf.pdf_statement_pages import (
    StatementPageSpec,
    specs_from_config,
)
from equity_os.interface.entry.config import load_config
from equity_os.normalisation.dictionary.dictionary import CanonicalDictionary, load_dictionary
from equity_os.normalisation.mapping.mapping import (
    MappingSet,
    NormalisationPolicy,
    load_mapping_set,
    load_normalisation_policy,
)
from equity_os.storage.records.repository import EvidenceRepository

CONFIG = REPO_ROOT / "config"
APAR_ISSUER_CONFIG = CONFIG / "runs/aparinds-fy26-q2.yaml"
Q2_FY26 = "FY26_Q2"
Q2_END = date(2025, 9, 30)
XBRL_KIND = "xbrl-consolidated"
PDF_KIND = "results"
BOTH = {Representation.XBRL: XBRL_KIND, Representation.PDF: PDF_KIND}
XBRL_ONLY = {Representation.XBRL: XBRL_KIND}
Q2_QUARTER = PeriodInterval.duration(date(2025, 7, 1), Q2_END)
Q2_HALF = PeriodInterval.duration(date(2025, 4, 1), Q2_END)
FY25_Q2_QUARTER = PeriodInterval.duration(date(2024, 7, 1), date(2024, 9, 30))
CAPMKT = "http://www.sebi.gov.in/xbrl/2025-01-31/in-capmkt"
PDF_LAYOUT = "sebi-lodr-results-layout"
NO_VALUE_STATES = {MissingValueState.NIL, MissingValueState.DASH, MissingValueState.BLANK}
EPS_DISCONTINUED_ONED = (
    b'<in-capmkt:BasicEarningsLossPerShareFromDiscontinuedOperations contextRef="OneD" '
    b'decimals="INF" unitRef="INRPerShare">0'
    b"</in-capmkt:BasicEarningsLossPerShareFromDiscontinuedOperations>"
)
EPS_DISCONTINUED_FOURD = EPS_DISCONTINUED_ONED.replace(b'"OneD"', b'"FourD"')
SCOPE_ID = "test-eps-total-when-discontinued-zero"


@pytest.fixture(scope="module")
def dictionary() -> CanonicalDictionary:
    """Canonical dictionary v1."""
    return load_dictionary(CONFIG / "normalisation/dictionary", "v1")


@pytest.fixture(scope="module")
def mapping_set(dictionary: CanonicalDictionary) -> MappingSet:
    """Mapping set v1."""
    return load_mapping_set(CONFIG / "normalisation/mappings", "v1", dictionary=dictionary)


@pytest.fixture(scope="module")
def policy() -> NormalisationPolicy:
    """Normalisation policy v1."""
    return load_normalisation_policy(CONFIG / "normalisation/normalisation_policy" / "v1.yaml")


def apar_pdf_specs() -> Mapping[StatementFamily, StatementPageSpec]:
    """The issuer config's PDF statement specs."""
    return specs_from_config(load_config(APAR_ISSUER_CONFIG).pdf_parse)


class Ingest:
    """One seeded test database plus the pinned versions, ready to ingest Apar packages."""

    def __init__(
        self,
        pg_db: PgTestDatabase,
        repository: EvidenceRepository,
        tmp_path: Path,
        dictionary: CanonicalDictionary,
        mapping_set: MappingSet,
        policy: NormalisationPolicy,
    ) -> None:
        self.pg_db = pg_db
        self.repository = repository
        self.tmp_path = tmp_path
        self.dictionary = dictionary
        self.mapping_set = mapping_set
        self.policy = policy
        self.entity_id = seed_apar(pg_db)

    def intake(
        self,
        members: Mapping[Representation, str] = BOTH,
        quarter: str = Q2_FY26,
        *,
        marked: Mapping[Representation, Path] | None = None,
    ) -> RetainedIntake:
        """A retained intake under this test's private directories."""
        return apar_intake(self.tmp_path, quarter, members, marked=marked)

    def run(
        self,
        intake: RetainedIntake,
        period_end: date = Q2_END,
        *,
        mapping_set: MappingSet | None = None,
        policy: NormalisationPolicy | None = None,
        catalog: SourceCatalog | None = None,
        basis: Basis = Basis.CONSOLIDATED,
        framework: AccountingFramework = AccountingFramework.IND_AS,
        entity_id: int | None = None,
        pdf_specs: Mapping[StatementFamily, StatementPageSpec] | None = None,
        supersedes_package_id: int | None = None,
        extractor_versions: Mapping[Representation, str] | None = None,
    ) -> IngestReport:
        """Ingest one package with the v1 pins and the issuer's specs unless overridden."""
        has_pdf = any(b.representation is Representation.PDF for b in intake.bindings)
        specs = pdf_specs or (apar_pdf_specs() if has_pdf else None)
        return ingest_first_party(
            intake=intake,
            catalog=catalog or apar_catalog(),
            snapshot_store=apar_store(self.tmp_path),
            repository=self.repository,
            dictionary=self.dictionary,
            mapping_set=mapping_set or self.mapping_set,
            policy=policy or self.policy,
            entity_id=self.entity_id if entity_id is None else entity_id,
            basis=basis,
            framework=framework,
            family=FilingFamily.FINANCIAL_RESULTS,
            reporting_period_end=period_end,
            pdf_specs=specs,
            supersedes_package_id=supersedes_package_id,
            extractor_versions=extractor_versions,
        )

    def package(self, report: IngestReport) -> FilingPackage:
        """The report's stored package."""
        assert report.package_id is not None
        (package,) = self.repository.get_packages([report.package_id])
        return package

    def capture_id(self, report: IngestReport, representation: Representation) -> int:
        """The capture id of one package member."""
        capture_ref_id = self.package(report).members[representation].capture.capture_ref_id
        assert capture_ref_id is not None
        return capture_ref_id

    def interpretations(self, report: IngestReport) -> list[Interpretation]:
        """Every interpretation of the report's package members."""
        found: list[Interpretation] = []
        for representation in self.package(report).members:
            found += self.repository.list_capture_interpretations(
                self.capture_id(report, representation)
            )
        return found

    def occurrences(self, report: IngestReport) -> dict[int, Occurrence]:
        """Every occurrence of the report's package members, by id."""
        found: dict[int, Occurrence] = {}
        for representation in self.package(report).members:
            for occurrence in self.repository.list_capture_occurrences(
                self.capture_id(report, representation)
            ):
                assert occurrence.occurrence_id is not None
                found[occurrence.occurrence_id] = occurrence
        return found

    def table_counts(self) -> dict[str, int]:
        """Row count of every ``eqos`` table."""
        with self.pg_db.runtime_pool() as pool, pool.connection() as conn:
            names = [
                row[0]
                for row in conn.execute(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'eqos' ORDER BY 1"
                ).fetchall()
            ]
            counts = {}
            for name in names:
                query = sql.SQL("SELECT count(*) FROM eqos.{}").format(sql.Identifier(name))
                row = conn.execute(query).fetchone()
                assert row is not None
                counts[name] = int(row[0])
            return counts


@pytest.fixture
def ingest(
    pg_db: PgTestDatabase,
    tmp_path: Path,
    dictionary: CanonicalDictionary,
    mapping_set: MappingSet,
    policy: NormalisationPolicy,
) -> Iterator[Ingest]:
    """A seeded database and private directories."""
    with pg_db.runtime_pool() as pool:
        yield Ingest(pg_db, EvidenceRepository(pool), tmp_path, dictionary, mapping_set, policy)


def rows_of(
    rows: list[Interpretation],
    canonical_id: str,
    period: PeriodInterval,
    representation: Representation,
    *,
    dimensions: tuple[tuple[str, str], ...] = (),
) -> list[Interpretation]:
    """Keyed rows of one canonical id, period, representation and dimension set."""
    return [
        row
        for row in rows
        if row.key is not None
        and row.key.canonical_id == canonical_id
        and row.key.period == period
        and row.representation is representation
        and row.key.dimensions.pairs == dimensions
    ]


def one(
    rows: list[Interpretation],
    canonical_id: str,
    period: PeriodInterval,
    representation: Representation,
    **kwargs: Any,
) -> Interpretation:
    """The single keyed row of one measurement."""
    (row,) = rows_of(rows, canonical_id, period, representation, **kwargs)
    return row


def constructed(rows: list[Interpretation], rule_id: str, period: PeriodInterval) -> Interpretation:
    """The single construction of one rule for one period, keyed or not."""
    (row,) = [row for row in rows if row.construction_rule_id == rule_id and row.period == period]
    return row


def by_occurrence(rows: list[Interpretation]) -> dict[int, Interpretation]:
    """Direct interpretations by occurrence id."""
    return {row.occurrence_id: row for row in rows if row.occurrence_id is not None}


def marked_xbrl(tmp_path: Path, edit: MarkedEdit, quarter: str = Q2_FY26) -> Path:
    """A marked copy of one quarter's retained XBRL instance."""
    return marked_copy(apar_original(quarter, XBRL_KIND), edit=edit, tmp_path=tmp_path)


def temp_mapping(
    tmp_path: Path,
    dictionary: CanonicalDictionary,
    edit: Callable[[dict[str, Any]], None],
    *,
    version: str = "v1",
    member: str = "xbrl/v1/in_capmkt.yaml",
) -> MappingSet:
    """A loaded copy of mapping set v1 with one member file edited, under ``version``.

    Content differing from a version already pinned in the test database is drift, so a
    database test gives every edited copy its own version.
    """
    root = tmp_path / f"mappings-{version}-{len(list(tmp_path.glob('mappings-*')))}"
    shutil.copytree(CONFIG / "normalisation/mappings", root)
    path = root / member
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    edit(data)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    if version != "v1":
        index = yaml.safe_load((root / "v1.yaml").read_text(encoding="utf-8"))
        index["version"] = version
        (root / f"{version}.yaml").write_text(yaml.safe_dump(index), encoding="utf-8")
    return load_mapping_set(root, version, dictionary=dictionary)


def entry_of(data: dict[str, Any], entry_id: str) -> dict[str, Any]:
    """One raw entry of a mapping member file."""
    (entry,) = [item for item in data["entries"] if item["entry_id"] == entry_id]
    return dict(entry)


def replace_entry(data: dict[str, Any], entry_id: str, entry: dict[str, Any]) -> None:
    """Swap one raw entry for an edited copy."""
    data["entries"] = [entry if item["entry_id"] == entry_id else item for item in data["entries"]]


def demonstrate_eps(period_kinds: list[str]) -> Callable[[dict[str, Any]], None]:
    """Edit: ``capmkt.eps_basic`` demonstrated when discontinued EPS is proven zero."""

    def edit(data: dict[str, Any]) -> None:
        entry = entry_of(data, "capmkt.eps_basic")
        entry["tier"] = EvidenceTier.EQUIVALENCE_DEMONSTRATED.value
        entry["qualification"] = {
            "scope_id": SCOPE_ID,
            "schema_identities": [CAPMKT],
            "surfaces": ["NSE_XBRL_INSTANCE"],
            "bases": ["CONSOLIDATED"],
            "period_kinds": period_kinds,
            "conditions": [
                {
                    "condition_id": "discontinued-eps-zero",
                    "canonical_id": "eps_basic_discontinued",
                    "predicate": "EQUALS_ZERO",
                }
            ],
        }
        replace_entry(data, "capmkt.eps_basic", entry)

    return edit


def pdf_context(kind: PeriodKind) -> QualificationContext:
    """A PDF qualification context with no proofs."""
    return QualificationContext(
        schema_identity=PDF_LAYOUT,
        surface="NSE_RESULTS_PDF",
        basis=Basis.CONSOLIDATED,
        period_kind=kind,
        proven={},
    )
