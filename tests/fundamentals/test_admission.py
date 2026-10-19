"""D2.4 admission (plan D2 Task 4): the §4 policy over real Stage 1 runs, the admission record,
idempotence and atomicity, the bridge, and the separate selection and read steps; and
admitted facts as ledger citations (PILOT-GAP-admission Task 1)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
import pytest
from retained_support import APAR_ISSUER_CONFIG, apar_catalog, apar_original
from stage1_e2e_support import RUNS, Stage, row_key

from fundamentals.api.config import load_config
from fundamentals.compare.queue import (
    lock_queue,
    overlay_boundary,
    publish_queue_drafts,
    read_overlay,
    record_disposition,
)
from fundamentals.compare.run import load_results
from fundamentals.compare.run_models import ResultRow
from fundamentals.contracts.canonical import Basis, Representation, StatementFamily, ValueKind
from fundamentals.contracts.comparison import ExtractionStatus, SourceRole
from fundamentals.contracts.evidence import InterpretationOrigin, PrecisionKind, RunMode
from fundamentals.contracts.fact import ReconciliationStatus
from fundamentals.contracts.guidance_claim import EpistemicClass
from fundamentals.contracts.ledger import (
    Citation,
    CitationKind,
    ClaimState,
    NumericClaim,
    Rounding,
)
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.contracts.review_queue import DispositionKind, QueueItemDraft, QueueSeverity
from fundamentals.evidence.admission import (
    AdmissionRecord,
    AdmissionRefusal,
    BridgeError,
    admit_run,
    fact_for,
    key_identity,
    read_selected,
    select_admitted,
)
from fundamentals.extract.pdf_statement_pages import (
    extract_statement_rows,
    locate_statement_pages,
    specs_from_config,
)
from fundamentals.ingest.pdf_source import load_pdf
from fundamentals.ledger.citations import resolve_citation
from fundamentals.ledger.claim_check import check_claim
from fundamentals.store.fact_store import (
    BarredAnchorFactError,
    CanonicalSelectionError,
    FactRef,
)
from fundamentals.store.pg_fact_store import PgFactStore, create_native_store
from fundamentals.store.snapshot_store import SnapshotStore

pytestmark = [pytest.mark.pg, pytest.mark.retained]

PAT, EPS = "profit_for_period|Q|-|REPORTED", "eps_basic|Q|-|REPORTED"
INCOME, TAX = "total_income|Q|-|REPORTED", "tax_expense|Q|-|REPORTED"
REFUSED = {
    TAX: AdmissionRefusal.EXTRACTION_NOT_AGREE,  # AGREE_UNQUALIFIED
    "profit_attributable_owners|Q|-|REPORTED": AdmissionRefusal.EXTRACTION_NOT_AGREE,  # INVALID
    "tax_earlier_years|Q|-|REPORTED": AdmissionRefusal.EXTRACTION_NOT_AGREE,  # no value
    "cf_profit_before_tax|Y|-|REPORTED": AdmissionRefusal.EXTRACTION_NOT_AGREE,  # one-sided
    "opm_pct|Q|-|DERIVED": AdmissionRefusal.NOT_REPORTED,
}
CONFIRMED = ReconciliationStatus.CROSS_SOURCE_CONFIRMED
COUNT_ROWS = "SELECT count(*) FROM eqos.fact_rows WHERE target_store = %s"
RESULT_ID = (
    "SELECT id FROM eqos.results WHERE run_id = %s AND key_digest = %s AND value_identity = %s"
)
REFUSE_TRIGGER = (
    "CREATE FUNCTION eqos.test_refuse() RETURNS trigger LANGUAGE plpgsql AS "
    "$$BEGIN RAISE EXCEPTION 'test refusal'; END$$",
    "CREATE TRIGGER test_refuse BEFORE INSERT ON eqos.fact_admissions "
    "FOR EACH ROW EXECUTE FUNCTION eqos.test_refuse()",
)

Ran = tuple[Stage, int, dict[str, ResultRow]]


def _ran(pg_db: Any, tmp_path: Path, run: str) -> Iterator[Ran]:
    """One manifest run executed over its retained first-party and vendor inputs."""
    with pg_db.runtime_pool() as pool:
        stage = Stage(pg_db, pool, tmp_path, RUNS[run])
        stage.first_party()
        stage.vendors()
        run_id = stage.execute().run_id
        rows = {row_key(stage.run, row): row for row in load_results(run_id, pool=pool)}
        yield stage, run_id, rows


@pytest.fixture
def apar(pg_db: Any, tmp_path: Path) -> Iterator[Ran]:
    """The Apar Q2 FY26 Stage 1 run."""
    yield from _ran(pg_db, tmp_path, "APARINDS-Q2FY26")


def _side(row: ResultRow, representation: Representation) -> int:
    """The interpretation the run selected for one first-party side of a row."""
    (value,) = [
        value
        for value in row.source_values
        if value.source_role is SourceRole.FIRST_PARTY and value.representation is representation
    ]
    assert value.interpretation_id is not None
    return value.interpretation_id


def _record(records: tuple[AdmissionRecord, ...], row: ResultRow) -> AdmissionRecord:
    """The admission record of a row's XBRL side."""
    xbrl = _side(row, Representation.XBRL)
    (found,) = [item for item in records if item.interpretation_id == xbrl]
    return found


def test_admission_policy_records_bridge_selection_and_read(apar: Ran) -> None:
    stage, run_id, rows = apar
    pool, repository = stage.pool, stage.repository
    store_id = create_native_store(pool, "admit")
    store = PgFactStore(pool, store_id)

    # Atomic: a failing admission insert leaves the store without any revision.
    with stage.pg_db.migrator_connection() as conn:
        for statement in REFUSE_TRIGGER:
            conn.execute(statement)
    with pytest.raises(psycopg.errors.RaiseException):
        admit_run(run_id, pool=pool, store_id=store_id)
    with stage.pg_db.migrator_connection() as conn:
        conn.execute("DROP TRIGGER test_refuse ON eqos.fact_admissions")
        assert conn.execute(COUNT_ROWS, (store_id,)).fetchone() == (0,)

    outcome = admit_run(run_id, pool=pool, store_id=store_id)
    refusals = dict(outcome.refusals)
    assert {key: refusals[rows[key].row_id] for key in REFUSED} == REFUSED
    assert len(outcome.records) + len(refusals) == len(rows)
    assert outcome.created == len(outcome.records)

    # PAT (decimals -6) and EPS (decimals="INF") are admitted in the same run.
    pat, eps = _record(outcome.records, rows[PAT]), _record(outcome.records, rows[EPS])
    facts = {
        key: next(
            revision.fact
            for revision in store.get_revisions(key_identity(rows[key].key))
            if revision.row_id == record.handle
        )
        for key, record in ((PAT, pat), (EPS, eps))
    }
    observed = {
        key: (
            fact.observation.normalized_value,
            fact.observation.normalized_unit,
            fact.observation.decimals,
            fact.observation.provenance.anchor_type,
            fact.observation.provenance.context_ref,
        )
        for key, fact in facts.items()
    }
    assert observed == {
        PAT: (Decimal(2_517_000_000), "INR", -6, SourceAnchorType.XBRL_CONTEXT, "OneD"),
        EPS: (Decimal("62.66"), "INR/share", 15, SourceAnchorType.XBRL_CONTEXT, "OneD"),
    }

    # Each record names exactly its source rows, at one overlay position.
    for key, record in ((PAT, pat), (EPS, eps)):
        row = rows[key]
        assert record.key_digest == row.key.digest()
        with pool.connection() as conn:
            result = conn.execute(RESULT_ID, (run_id, row.key.digest(), row.value_identity.value))
            (result_id,) = result.fetchone() or ()
        (interpretation,) = repository.get_interpretations([record.interpretation_id])
        assert (record.run_id, record.result_id, record.occurrence_id) == (
            run_id,
            result_id,
            interpretation.occurrence_id,
        )
        assert record.ref == store.fact_ref(record.handle)
    assert len({record.overlay_position for record in outcome.records}) == 1

    # Vendor values are never admitted, and an API-document fact cannot enter the store.
    vendor = {
        value.interpretation_id
        for row in rows.values()
        for value in row.source_values
        if value.source_role is not SourceRole.FIRST_PARTY
    }
    assert vendor.isdisjoint(record.interpretation_id for record in outcome.records)
    api = Provenance(
        source_id="upstox",
        file_sha256="ab" * 32,
        anchor_type=SourceAnchorType.API_DOCUMENT,
        document_id="doc",
        context_ref="ctx",
        table_key="table",
        row_label="row",
        column_label="column",
        retrieved_at=facts[PAT].observation.provenance.retrieved_at,
    )
    observation = facts[PAT].observation.model_copy(update={"provenance": api})
    with pytest.raises(BarredAnchorFactError):
        store.put(facts[PAT].model_copy(update={"observation": observation}))

    # Idempotent, and admission never selects.
    again = admit_run(run_id, pool=pool, store_id=store_id)
    assert (again.created, again.records) == (0, outcome.records)
    assert store.get_selection_history(key_identity(rows[PAT].key)) == ()

    # Bridge: a constructed interpretation is refused; a PDF crore cell keeps its precision.
    (constructed,) = repository.get_interpretations([_side(rows[TAX], Representation.PDF)])
    assert constructed.origin is InterpretationOrigin.CONSTRUCTED
    with pytest.raises(BridgeError):
        fact_for(constructed, None, rows[TAX].key, run_id=run_id, reconciliation=CONFIRMED)
    (pdf,) = repository.get_interpretations([_side(rows[PAT], Representation.PDF)])
    assert pdf.occurrence_id is not None
    (occurrence,) = repository.get_occurrences([pdf.occurrence_id])
    assert (occurrence.precision_kind, occurrence.declared_precision, occurrence.raw_scale) == (
        PrecisionKind.FINITE,
        2,
        7,
    )
    bridged = fact_for(
        pdf, occurrence, rows[PAT].key, run_id=run_id, reconciliation=CONFIRMED
    ).observation
    assert (bridged.scale, bridged.decimals, bridged.raw_value) == (1, -5, "251.70")
    # The native cell locator re-finds the printed value in the retained original by re-banding.
    cell = bridged.provenance
    assert (cell.anchor_type, cell.page, cell.block) == (SourceAnchorType.PDF_CELL, 3, None)
    assert cell.table_key == occurrence.anchor_key and cell.row_path is not None
    original = apar_original("FY26_Q2", "results")
    pdf = load_pdf(source_id=cell.source_id, path=original, expected_sha256=cell.file_sha256)
    specs = specs_from_config(load_config(APAR_ISSUER_CONFIG).pdf_parse)
    family = StatementFamily(cell.table_key.split(":")[1])
    location = locate_statement_pages(pdf, specs, basis=Basis.CONSOLIDATED)[family]
    assert location is not None
    (printed,) = (
        found.raw_text.strip()
        for row in extract_statement_rows(pdf, location)
        if (row.page, row.line) == (cell.page, int(cell.row_path))
        for found in row.cells
        if found.column_index == cell.column_index
    )
    assert printed == "251.70"

    # Selection is a separate step; the read honours cutoff and mode.
    before = repository.store_clock()
    selected = select_admitted(
        pool,
        store_id=store_id,
        admission_id=pat.admission_id,
        reason="test: admitted PAT",
        expected_selection_id=0,
    )
    assert selected.canonical_selected_at is not None
    assert read_selected(store, rows[PAT].key, cutoff=before, mode=RunMode.AS_KNOWN) is None
    after = selected.canonical_selected_at + timedelta(microseconds=1)
    known = read_selected(store, rows[PAT].key, cutoff=after, mode=RunMode.AS_KNOWN)
    assert known is not None
    assert (known.value, known.unit, known.ref, known.provenance.context_ref) == (
        Decimal(2_517_000_000),
        "INR",
        FactRef(store_id=store_id, origin="pg-native", origin_id=pat.ref.origin_id),
        "OneD",
    )
    # Retrospective reads today's selection back to when its fact was known and first seen:
    # there, as-known has no selection yet. The test ingest stamps first-seen today, so the
    # quarter's own cutoff precedes it and even a retrospective read finds nothing.
    seen = max(facts[PAT].knowledge_time, facts[PAT].first_seen_time)
    assert read_selected(store, rows[PAT].key, cutoff=seen, mode=RunMode.AS_KNOWN) is None
    assert read_selected(store, rows[PAT].key, cutoff=seen, mode=RunMode.RETROSPECTIVE) == known
    cutoff = load_config(APAR_ISSUER_CONFIG).quarter.knowledge_cutoff
    assert read_selected(store, rows[PAT].key, cutoff=cutoff, mode=RunMode.RETROSPECTIVE) is None
    with pytest.raises(CanonicalSelectionError):
        select_admitted(
            pool,
            store_id=store_id,
            admission_id=pat.admission_id,
            reason="test: stale",
            expected_selection_id=0,
        )


def test_open_high_refuses_until_disposed(apar: Ran) -> None:
    """The amended D1b diagnostic-fixture cell: an open MEDIUM diagnostic Upstox item does not
    block admission; an open non-diagnostic HIGH on the same key does, until disposed."""
    stage, run_id, rows = apar
    pool, row = stage.pool, rows[INCOME]
    overlay = read_overlay(pool, run_id=run_id, as_of=overlay_boundary(pool))
    assert [
        (item.severity, item.diagnostic)
        for item in overlay.open_items
        if item.key is not None and item.key.digest() == row.key.digest()
    ] == [(QueueSeverity.MEDIUM, True)]
    admitted = admit_run(run_id, pool=pool, store_id=create_native_store(pool, "diagnostic"))
    assert _record(admitted.records, row).run_id == run_id

    draft = QueueItemDraft(
        key=row.key,
        pair_identity="test-high",
        outcome="MISMATCH",
        severity=QueueSeverity.HIGH,
        evidence_interpretation_ids=(_side(row, Representation.XBRL),),
    )
    with pool.connection() as conn, conn.transaction(), conn.cursor() as cursor:
        lock_queue(cursor)
        (item_id,) = publish_queue_drafts(cursor, run_id=run_id, drafts=[draft])
    store_id = create_native_store(pool, "high")
    refused = admit_run(run_id, pool=pool, store_id=store_id)
    assert dict(refused.refusals)[row.row_id] is AdmissionRefusal.OPEN_HIGH

    with stage.pg_db.owner_pool() as owner:
        record_disposition(
            owner,
            item_id=item_id,
            kind=DispositionKind.DISMISSED,
            reason="test: closes the HIGH",
            decider="test",
            evidence_ref="test-only",
        )
    (disposition,) = read_overlay(pool, run_id=run_id, as_of=overlay_boundary(pool)).dispositions
    record = _record(admit_run(run_id, pool=pool, store_id=store_id).records, row)
    assert record.overlay_position > disposition.recorded_at


def test_single_representation_not_applicable_is_admitted(pg_db: Any, tmp_path: Path) -> None:
    """LAURUSLABS Q3 FY25 files XBRL only: its continuing PAT is admitted on one value."""
    for stage, run_id, rows in _ran(pg_db, tmp_path, "LAURUSLABS-Q3FY25"):
        row = rows["profit_continuing_after_tax|Q|-|REPORTED"]
        assert row.extraction_status is ExtractionStatus.NOT_APPLICABLE
        store_id = create_native_store(stage.pool, "laurus")
        record = _record(admit_run(run_id, pool=stage.pool, store_id=store_id).records, row)
        (revision,) = PgFactStore(stage.pool, store_id).get_revisions(key_identity(row.key))
        fact = revision.fact
        assert revision.row_id == record.handle
        assert fact.reconciliation_status is ReconciliationStatus.UNRECONCILED
        assert fact.observation.normalized_value == Decimal(906_100_000)


# The rendered claims: PAT in INR crore and EPS in INR per share, as a draft states them.
CLAIMED = {
    PAT: ("INR crore", 10_000_000, ValueKind.CURRENCY_AMOUNT, Decimal("251.70")),
    EPS: ("INR per share", 1, ValueKind.PER_SHARE_AMOUNT, Decimal("62.66")),
}


def _claim(row: ResultRow, key: str, ref: FactRef, value: Decimal | None = None) -> NumericClaim:
    """A ``FIGURE`` claim on the admitted fact ``ref`` under the row's key."""
    unit, scale, kind, claimed = CLAIMED[key]
    return NumericClaim(
        claim_key=f"fact.{key}",
        section_key="results",
        citation=Citation(
            kind=CitationKind.FIGURE, fact_origin=ref.origin, fact_origin_id=ref.origin_id
        ),
        measurement_key=row.key,
        value_kind=kind,
        unit=unit,
        currency="INR",
        scale=scale,
        value=claimed if value is None else value,
        precision=2,
        rounding=Rounding.ROUND_HALF_UP,
        epistemic_class=EpistemicClass.OBSERVED,
    )


def test_admitted_facts_resolve_through_pinned_admissions(apar: Ran, tmp_path: Path) -> None:
    """An admitted fact is citable only for its issuer and through an admission of a pinned
    run; the earliest such admission of the cited row bounds it as known."""
    stage, run_id, rows = apar
    pool, repository = stage.pool, stage.repository
    catalog, snapshots = apar_catalog(), SnapshotStore(tmp_path / "snapshots")

    def state(
        claim: NumericClaim,
        run_ids: tuple[int, ...],
        cutoff: datetime | None = None,
        entity_id: int | None = None,
    ) -> ClaimState:
        """The AS_KNOWN check of ``claim`` at ``cutoff`` (default: the store clock now)."""
        at = cutoff or repository.store_clock()
        with pool.connection() as conn, conn.cursor() as cursor:
            resolved = resolve_citation(
                cursor,
                claim,
                entity_id=stage.entity_id if entity_id is None else entity_id,
                overlay_position=at,
                catalog=catalog,
                snapshots=snapshots,
                run_ids=run_ids,
            )
        return check_claim(claim, resolved, mode=RunMode.AS_KNOWN, cutoff=at, imported=False)

    # Admitted and selected: the crore and per-share claims match; a wrong value or another
    # report's issuer does not.
    store_id = create_native_store(pool, "cite")
    store = PgFactStore(pool, store_id)
    records = admit_run(run_id, pool=pool, store_id=store_id).records
    claims: dict[str, NumericClaim] = {}
    for key in (PAT, EPS):
        record = _record(records, rows[key])
        select_admitted(
            pool,
            store_id=store_id,
            admission_id=record.admission_id,
            reason="test: cite",
            expected_selection_id=0,
        )
        claims[key] = _claim(rows[key], key, record.ref)
        assert state(claims[key], (run_id,)) is ClaimState.MATCH
    wrong = _claim(rows[PAT], PAT, _record(records, rows[PAT]).ref, Decimal("251.80"))
    assert state(wrong, (run_id,)) is ClaimState.VALUE_MISMATCH
    assert state(claims[PAT], (run_id,), entity_id=stage.entity_id + 1) is ClaimState.UNRESOLVED

    # The same admitted PAT row written and selected directly in another store at T1 is an
    # ``eqos:`` fact with no admission: unresolved.
    (revision,) = [
        item
        for item in store.get_revisions(key_identity(rows[PAT].key))
        if item.row_id == _record(records, rows[PAT]).handle
    ]
    direct_id = create_native_store(pool, "direct")
    direct = PgFactStore(pool, direct_id)
    row_id = direct.put(revision.fact).row_id
    direct.select_canonical(row_id, "test: selected before admission")
    shared = _claim(rows[PAT], PAT, direct.fact_ref(row_id))
    assert state(shared, (run_id,)) is ClaimState.UNRESOLVED

    # Admitted at T2 (the row is reused): past a cutoff in (T1, T2), known after T2. The first
    # store's earlier admission of the same run is another row and does not count.
    between = repository.store_clock()
    admitted = admit_run(run_id, pool=pool, store_id=direct_id).records
    assert _record(admitted, rows[PAT]).handle == row_id
    assert state(shared, (run_id,), between) is ClaimState.POST_CUTOFF
    assert state(shared, (run_id,)) is ClaimState.MATCH

    # A second comparison run (first-party only, so another identity) admits the same row at
    # T3: each pinned run's own admission time, the earliest when both are pinned, nothing when
    # neither is.
    second = stage.execute(vendors=[]).run_id
    assert second != run_id
    later = repository.store_clock()
    admitted = admit_run(second, pool=pool, store_id=direct_id).records
    assert _record(admitted, rows[PAT]).handle == row_id
    assert state(shared, (second,), later) is ClaimState.POST_CUTOFF
    assert state(shared, (run_id,), later) is ClaimState.MATCH
    assert state(shared, (run_id, second), later) is ClaimState.MATCH
    assert state(shared, (run_id, second), between) is ClaimState.POST_CUTOFF
    assert state(shared, (second,)) is ClaimState.MATCH
    assert state(shared, (max(run_id, second) + 1,)) is ClaimState.UNRESOLVED
