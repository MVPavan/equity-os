"""The first-party revision fixture over retained Apar captures (D1a Task 6, steps 1–7).

FY25 Q2 (``in-bse-fin``, XBRL only) is the original for the Q2 FY25 keys; the FY26 Q2
package and a marked copy of its results PDF carry Q2 FY25 comparatives. Every cutoff is
read from the store (first-seen and ``recorded_at`` times), never written.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import date
from pathlib import Path

import pytest
from evidence_support import BOTH, PDF_KIND, Q2_END, Ingest
from pg_support import PgTestDatabase, create_database, drop_database, mint_name
from retained_support import CONSOLIDATED_X_MAX, PdfRedaction, marked_pdf

from fundamentals.canon.dictionary import CanonicalDictionary
from fundamentals.contracts.canonical import Basis, Representation, StatementFamily
from fundamentals.contracts.evidence import (
    EligibilityBoundary,
    FilingFamily,
    FilingPackage,
    Interpretation,
    InterpretationTriple,
    KeySelection,
    Occurrence,
    RunMode,
)
from fundamentals.contracts.measurement_key import MeasurementKey
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.evidence.first_party_ingest import IngestReport
from fundamentals.evidence.mapping import MappingSet, NormalisationPolicy
from fundamentals.evidence.pdf_adapter import PDF_EXTRACTOR_VERSION
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.evidence.selection import differing_restatement, select_key, select_package
from fundamentals.evidence.xbrl_adapter import XBRL_EXTRACTOR_VERSION

FY25_Q2 = "FY25_Q2"
FY25_Q2_END = date(2024, 9, 30)
COMPARATOR_KIND = "xbrl-consolidated-comparator"
V1 = InterpretationTriple(
    mapping_set="v1",
    normalisation_policy="v1",
    extractor_xbrl=XBRL_EXTRACTOR_VERSION,
    extractor_pdf=PDF_EXTRACTOR_VERSION,
)
# Page 3 prints Q2 FY25 consolidated revenue from operations as 4,644.51 crore; the marked
# copy prints another figure in that one cell (a test edit, never a filed value).
PRINTED_Q2_FY25_REVENUE = "4,644.51"
MARKED_Q2_FY25_REVENUE = "4,744.51"
SemanticKey = tuple[str, str, str]
# A capture's rows never change once its ingest returns (each database is fresh per test),
# so they are read once per database and capture.
_MEMBER_ROWS: dict[tuple[str, int], tuple[tuple[Occurrence, ...], tuple[Interpretation, ...]]] = {}


@pytest.fixture
def reverse_ingest(
    pg_template: PgTestDatabase,
    tmp_path_factory: pytest.TempPathFactory,
    dictionary: CanonicalDictionary,
    mapping_set: MappingSet,
    policy: NormalisationPolicy,
) -> Iterator[Ingest]:
    """A second fresh ``eqos_test_*`` database for the reverse ingest order."""
    settings = pg_template.settings
    name = mint_name(settings)
    create_database(settings, name, template=pg_template.dbname)
    try:
        database = PgTestDatabase(dbname=name, settings=settings)
        with database.runtime_pool() as pool:
            yield Ingest(
                database,
                EvidenceRepository(pool),
                tmp_path_factory.mktemp("reverse"),
                dictionary,
                mapping_set,
                policy,
            )
    finally:
        drop_database(settings, name)


def marked_revenue_pdf(tmp_path: Path) -> Path:
    """The FY26 Q2 results PDF with the Q2 FY25 consolidated revenue cell reprinted."""
    return marked_pdf(
        tmp_path,
        "restated-q2-fy25-revenue",
        PdfRedaction(
            page=3,
            row_of=PRINTED_Q2_FY25_REVENUE,
            words=(PRINTED_Q2_FY25_REVENUE,),
            x_max=CONSOLIDATED_X_MAX,
            replace=MARKED_Q2_FY25_REVENUE,
        ),
    )


def ingest_fy25_q2(ingest: Ingest) -> IngestReport:
    """The one-member FY25 Q2 original."""
    return ingest.run(ingest.intake({Representation.XBRL: COMPARATOR_KIND}, FY25_Q2), FY25_Q2_END)


def ingest_fy26_q2(ingest: Ingest) -> IngestReport:
    """The real FY26 Q2 package (XBRL and results PDF)."""
    return ingest.run(ingest.intake(BOTH))


def ingest_marked(ingest: Ingest, marked: Path) -> IngestReport:
    """The marked results PDF as a separate one-member package for the same period end."""
    return ingest.run(
        ingest.intake({Representation.PDF: PDF_KIND}, marked={Representation.PDF: marked})
    )


def packages(ingest: Ingest, period_end: date) -> tuple[FilingPackage, ...]:
    """Every stored results package of Apar for one period end."""
    return ingest.repository.list_packages(
        ingest.entity_id, FilingFamily.FINANCIAL_RESULTS, period_end
    )


def member_rows(
    ingest: Ingest, package: FilingPackage, representation: Representation
) -> tuple[tuple[Occurrence, ...], tuple[Interpretation, ...]]:
    """A member capture's occurrences and interpretations (read once)."""
    capture_ref_id = package.members[representation].capture.capture_ref_id
    assert capture_ref_id is not None
    cache_key = (ingest.pg_db.dbname, capture_ref_id)
    if cache_key not in _MEMBER_ROWS:
        _MEMBER_ROWS[cache_key] = (
            ingest.repository.list_capture_occurrences(capture_ref_id),
            ingest.repository.list_capture_interpretations(capture_ref_id),
        )
    return _MEMBER_ROWS[cache_key]


def original_selection(
    ingest: Ingest, key: MeasurementKey, boundary: EligibilityBoundary, mode: RunMode
) -> KeySelection:
    """The Q2 FY25 key selected from the FY25 Q2 package's XBRL member."""
    package = select_package(
        packages(ingest, FY25_Q2_END),
        entity_id=ingest.entity_id,
        family=FilingFamily.FINANCIAL_RESULTS,
        statement_family=StatementFamily.PL,
        basis=Basis.CONSOLIDATED,
        framework=AccountingFramework.IND_AS,
        period_end=FY25_Q2_END,
        boundary=boundary,
    )
    occurrences, interpretations = (
        member_rows(ingest, package, Representation.XBRL) if package else ((), ())
    )
    return select_key(
        key,
        Representation.XBRL,
        package=package,
        occurrences=occurrences,
        interpretations=interpretations,
        boundary=boundary,
        mode=mode,
        pinned=V1,
    )


def eligible_comparatives(
    ingest: Ingest, key: MeasurementKey, boundary: EligibilityBoundary, mode: RunMode
) -> list[Interpretation]:
    """Comparatives of ``key`` in eligible FY26 Q2-period packages, under v1 pins."""
    found = []
    for package in packages(ingest, Q2_END):
        if not package.eligible(boundary):
            continue
        for representation in package.members:
            _, rows = member_rows(ingest, package, representation)
            found += [
                row
                for row in rows
                if row.key == key
                and _under_v1(row)
                and (mode is RunMode.RETROSPECTIVE or row.recorded_at <= boundary.first_seen_cutoff)
            ]
    return found


def latest_recorded_at(rows: Sequence[Interpretation]) -> EligibilityBoundary:
    """A run boundary at the latest ``recorded_at`` of the given rows (read, never written)."""
    return EligibilityBoundary.at(max(row.recorded_at for row in rows))


def surfaced(ingest: Ingest, boundary: EligibilityBoundary) -> set[SemanticKey]:
    """Every surfaced restatement of every Q2 FY25 key, by semantic key, never row id."""
    (original,) = packages(ingest, FY25_Q2_END)
    occurrences, rows = member_rows(ingest, original, Representation.XBRL)
    later: list[Interpretation] = []
    for package in packages(ingest, Q2_END):
        if package.eligible(boundary):
            for representation in package.members:
                later += member_rows(ingest, package, representation)[1]
    ids: set[int] = set()
    for key in {row.key for row in rows if row.key is not None}:
        selection = select_key(
            key,
            Representation.XBRL,
            package=original if original.eligible(boundary) else None,
            occurrences=occurrences,
            interpretations=rows,
            boundary=boundary,
            mode=RunMode.AS_KNOWN,
            pinned=V1,
        )
        comparatives = [
            row
            for row in later
            if row.key == key and _under_v1(row) and row.recorded_at <= boundary.first_seen_cutoff
        ]
        ids.update(differing_restatement(selection, comparatives))
    return semantic_keys(ingest, ids)


def _under_v1(row: Interpretation) -> bool:
    """Whether a row is under the v1 triple."""
    return (
        row.mapping_set_version == V1.mapping_set
        and row.normalisation_policy_version == V1.normalisation_policy
        and row.extractor_version == V1.extractor(row.representation)
    )


def semantic_keys(ingest: Ingest, ids: set[int]) -> set[SemanticKey]:
    """(key digest, capture ``blob_sha256``, anchor key or construction rule) per row."""
    rows = ingest.repository.get_interpretations(sorted(ids))
    captures = {
        ref.capture_ref_id: ref.blob_sha256
        for ref in ingest.repository.get_capture_refs(sorted({row.capture_ref_id for row in rows}))
    }
    anchors = {
        item.occurrence_id: item.anchor_key
        for item in ingest.repository.get_occurrences(
            sorted(row.occurrence_id for row in rows if row.occurrence_id is not None)
        )
    }
    keys = set()
    for row in rows:
        assert row.key is not None
        anchor = anchors[row.occurrence_id] if row.occurrence_id else row.construction_rule_id
        keys.add((row.key.digest(), captures[row.capture_ref_id], str(anchor)))
    return keys
