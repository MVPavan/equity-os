"""One admission path (VENDOR-1 spec §6.5, §6.6, §6.9; plan Task 8): every row of §6.5,
counterexamples recorded first, withdrawal of unchecked facts for later cutoffs only, and
retention of both witnesses.

LAURUSLABS consolidated under mapping set v9 (values in ``test_compare_vendor_runs``): Q3 FY25
revenue is ``VENDORS_AGREE`` at "1,415" crore against a filed 1,415.05; ``finance_costs`` is
``VENDORS_IMPRECISE``; Screener's annual Interest is ``RELATED_NOT_EQUIVALENT`` to FY
``finance_costs``. The eligibility fixture marks every agreeing class of a vendor-only Q3 run
eligible; it is a test artifact, not measured evidence.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from retained_support import MarkedEdit
from stage1_e2e_support import CONFIG, RUNS, Stage

from equity_os.companies.identity.identity_seed import EvidenceInputKind, SettingKey
from equity_os.contracts.measurement.canonical import Basis
from equity_os.contracts.measurement.evidence import RunMode
from equity_os.contracts.measurement.provenance import SourceAnchorType
from equity_os.contracts.verification.comparison import SourceState
from equity_os.contracts.verification.review_queue import (
    DispositionKind,
    QueueItemDraft,
    QueueSeverity,
)
from equity_os.contracts.verification.vendor_first import (
    AdmissionLabel,
    FilingFailure,
    VendorOutcome,
)
from equity_os.storage.facts.pg_fact_store import PgFactStore, create_native_store
from equity_os.verification.admission.admission import (
    AdmissionOutcome,
    AdmissionRecord,
    AdmissionRefusal,
    BridgeError,
    admit_run,
    key_identity,
    read_selected,
    select_admitted,
)
from equity_os.verification.admission.eligibility import (
    ClassEvidence,
    EligibilityArtifact,
    row_class,
)
from equity_os.verification.admission.vendor_first import (
    NON_FINANCIAL,
    check_class,
    vendor_outcome,
)
from equity_os.verification.comparison.run import load_results, replay_inputs
from equity_os.verification.comparison.run_config import (
    ELIGIBILITY_DIR,
    ConfigVersions,
    load_run_config,
)
from equity_os.verification.comparison.run_models import ResultRow
from equity_os.verification.review_queue.queue import (
    lock_queue,
    overlay_boundary,
    publish_queue_drafts,
    read_overlay,
    record_disposition,
)

pytestmark = [pytest.mark.pg, pytest.mark.retained]

V9 = ConfigVersions(dictionary="v2", mapping_set="v9", alignment_rules="v2")
Q3, Q4 = date(2024, 12, 31), date(2025, 3, 31)
CRORE = Decimal(10) ** 7
REVENUE = "revenue_from_operations|2024-10-01..2024-12-31|CONSOLIDATED|-|REPORTED"
REVENUE_Q4 = "revenue_from_operations|2025-01-01..2025-03-31|CONSOLIDATED|-|REPORTED"
FINANCE = "finance_costs|2024-10-01..2024-12-31|CONSOLIDATED|-|REPORTED"
FINANCE_FY = "finance_costs|2024-04-01..2025-03-31|CONSOLIDATED|-|REPORTED"
SCREENER, TIJORI = "screener-subscriber", "tijori"
# Test-private: the filed Q3 revenue moved 100 crore, outside both vendor intervals.
DIFFERS = MarkedEdit(
    label="revenue-differs",
    find=b':RevenueFromOperations contextRef="OneD" unitRef="INR" decimals="-7">14150500000.00<',
    replace=b':RevenueFromOperations contextRef="OneD" unitRef="INR" decimals="-7">14250500000.00<',
)
# Test-private: Apar's XBRL Q2 revenue moved 10 crore, so the XBRL and the PDF disagree.
XBRL_DIFFERS = MarkedEdit(
    label="xbrl-revenue-differs",
    find=b':RevenueFromOperations contextRef="OneD" decimals="-5" unitRef="INR">57154200000<',
    replace=b':RevenueFromOperations contextRef="OneD" decimals="-5" unitRef="INR">57254200000<',
)
APAR_REVENUE = "revenue_from_operations|2025-07-01..2025-09-30|CONSOLIDATED|-|REPORTED"
ONBOARDED = (
    "INSERT INTO eqos.onboarding_records (identifier, identifier_namespace, outcome, "
    "entity_id, evidence_input_id) VALUES (%s, 'NSE', 'PARTIAL', %s, %s)"
)
COUNTEREXAMPLES = (
    "SELECT class_digest, result_id FROM eqos.vendor_counterexamples WHERE run_id = %s"
)
RESULT_ID = "SELECT id FROM eqos.results WHERE run_id = %s AND key_digest = %s"
WITNESS_CAPTURE = (
    "SELECT c.id, c.source_id FROM eqos.interpretations i "
    "JOIN eqos.capture_refs c ON c.id = i.capture_ref_id WHERE i.id = %s"
)
CAPTURE_STATE = "INSERT INTO eqos.capture_states (capture_ref_id, state) VALUES (%s, %s)"


@pytest.fixture
def laurus(pg_db: Any, tmp_path: Path) -> Iterator[Stage]:
    """LAURUSLABS under v9 from a config copy, with onboarding provenance (issuer class) and
    both vendors' captures ingested for Q3 and Q4 FY25; no filing yet."""
    root = tmp_path / "config"
    shutil.copytree(CONFIG, root)
    with pg_db.runtime_pool() as pool:
        stage = Stage(pg_db, pool, tmp_path, RUNS["LAURUSLABS-Q3FY25"])
        stage.config, stage.config_root, stage.versions = load_run_config(root, V9), root, V9
        for end in (Q3, Q4):
            for vendor, label in stage.run["vendor_inputs"].items():
                stage.vendor(vendor, label.split()[0], end=end)
        repository = stage.repository
        discovery = repository.put_evidence_input(EvidenceInputKind.DISCOVERY, "LAURUS", "d" * 64)
        repository.put_settings_record(
            stage.entity_id, SettingKey.REPORTING_FRAMEWORK, "IND_AS", discovery
        )
        with pool.connection() as conn:
            conn.execute(ONBOARDED, ("LAURUSLABS", stage.entity_id, discovery))
        yield stage


def test_vendor_first_rows_counterexamples_and_withdrawal(laurus: Stage, tmp_path: Path) -> None:
    """Rows 1–6 and 0a on one issuer, in the order the evidence arrives (acceptance 5, 6, 8, 12;
    finding 6), then the retention of both witnesses (§6.9)."""
    stage, pool = laurus, laurus.pool

    # Vendor-only, no eligibility pin: agreeing vendors refuse CHECK_REQUIRED (row 4), imprecise
    # ones their T1 outcome (row 6); both are triggers for the company-period.
    unpinned = _run(stage, Q3)
    outcome = _admit(stage, unpinned, "unpinned")
    refusals = dict(outcome.refusals)
    assert (refusals[REVENUE], refusals[FINANCE]) == (
        AdmissionRefusal.CHECK_REQUIRED,
        AdmissionRefusal.VENDORS_IMPRECISE,
    )
    assert outcome.records == () and outcome.filing_failures == ()
    assert outcome.triggers == ((stage.entity_id, Q3, Basis.CONSOLIDATED),)
    revenue_class = _artifacts(stage, unpinned)

    # Pinned eligibility: row 3 (acceptance 5), the vendor value with both witnesses.
    pinned = _run(stage, Q3, "fixture")
    outcome = _admit(stage, pinned, "unchecked")
    unchecked = _records(stage, pinned, outcome)[REVENUE]
    assert unchecked.label is AdmissionLabel.VENDORS_AGREE_NOT_CHECKED
    assert unchecked.eligibility_version == "fixture" and unchecked.witness_interpretation_id
    assert dict(outcome.refusals)[FINANCE] is AdmissionRefusal.VENDORS_IMPRECISE
    fact = _fact(stage, unchecked)
    assert fact.observation.normalized_value == 1415 * CRORE
    assert fact.observation.provenance.anchor_type in (
        SourceAnchorType.HTML_TABLE,
        SourceAnchorType.JSON_ISLAND,
    )
    _select(stage, unchecked)
    known_unchecked = stage.repository.store_clock()

    # A class digest of other versions never matches: CHECK_REQUIRED (acceptance 8).
    mismatch = _admit(stage, _run(stage, Q3, "mismatch"), "mismatch")
    assert dict(mismatch.refusals)[REVENUE] is AdmissionRefusal.CHECK_REQUIRED

    # The filing arrives and agrees: row 1 keeps the vendor value and its precision; the
    # imprecise cell takes the filed value (row 5). Both labelled checked.
    first = stage.first_party()
    filed = _run(stage, Q3, "fixture")
    outcome = _admit(stage, filed, "checked")
    records = _records(stage, filed, outcome)
    checked = records[REVENUE]
    assert checked.label is AdmissionLabel.CHECKED_AGAINST_FILING
    assert checked.witness_interpretation_id is not None
    assert _fact(stage, checked).observation == fact.observation  # the vendor value, checked
    finance = _fact(stage, records[FINANCE]).observation
    assert records[FINANCE].label is AdmissionLabel.CHECKED_AGAINST_FILING
    assert records[FINANCE].witness_interpretation_id is None
    assert (finance.normalized_value, finance.provenance.anchor_type) == (
        Decimal(578_000_000),
        SourceAnchorType.XBRL_CONTEXT,
    )
    _select(stage, checked)

    # A superseding filing differs from agreeing vendors under an open HIGH item: REVIEW_OPEN
    # (row 0a), and the counterexample is still recorded (acceptance 6). Once the item is
    # disposed, the filed value is admitted (row 2).
    stage.tmp_path = tmp_path / "differs"
    stage.tmp_path.mkdir()
    stage.first_party(DIFFERS, supersedes=first)
    differs = _run(stage, Q3, "fixture")
    rows = {row.row_id: row for row in load_results(differs, pool=pool)}
    _open_high(stage, differs, rows[REVENUE])
    contested = create_native_store(pool, "contested")
    outcome = admit_run(differs, pool=pool, store_id=contested, config_root=stage.config_root)
    assert dict(outcome.refusals)[REVENUE] is AdmissionRefusal.REVIEW_OPEN
    with pool.connection() as conn:
        (revenue_result,) = conn.execute(
            RESULT_ID, (differs, rows[REVENUE].key.digest())
        ).fetchone()
        assert (revenue_class, revenue_result) in conn.execute(
            COUNTEREXAMPLES, (differs,)
        ).fetchall()
    _dispose_all(stage, differs, rows[REVENUE])
    outcome = admit_run(differs, pool=pool, store_id=contested, config_root=stage.config_root)
    record = _records(stage, differs, outcome)[REVENUE]
    assert record.label is AdmissionLabel.CHECKED_AGAINST_FILING
    assert _fact(stage, record).observation.normalized_value == Decimal(14_250_500_000)
    contradicted = stage.repository.store_clock()

    # Run N+1, another quarter of the same class, artifact unchanged: blocked (acceptance 8).
    # Screener's annual Interest never votes, so FY finance costs stay out of row 3 (acc. 12).
    later = _run(stage, Q4, "fixture")
    outcome = _admit(stage, later, "blocked")
    refusals = dict(outcome.refusals)
    assert refusals[REVENUE_Q4] is AdmissionRefusal.CHECK_REQUIRED
    assert refusals[FINANCE_FY] is AdmissionRefusal.VENDOR_UNMAPPED
    (finance_fy,) = [row for row in load_results(later, pool=pool) if row.row_id == FINANCE_FY]
    assert {
        value.source_id for value in finance_fy.source_values if value.state is SourceState.VALUE
    } >= {SCREENER, TIJORI}

    # Withdrawal: the unchecked fact for later cutoffs only; the checked one of the same
    # contradicted class stays (finding 6).
    unchecked_store = PgFactStore(pool, unchecked.ref.store_id)
    checked_store = PgFactStore(pool, checked.ref.store_id)
    key = rows[REVENUE].key
    before = read_selected(
        unchecked_store, key, cutoff=known_unchecked, mode=RunMode.AS_KNOWN, pool=pool
    )
    assert before is not None and before.label is AdmissionLabel.VENDORS_AGREE_NOT_CHECKED
    assert (before.value, before.decimals) == (1415 * CRORE, fact.observation.decimals)
    now = stage.repository.store_clock()
    assert contradicted < now
    assert read_selected(unchecked_store, key, cutoff=now, mode=RunMode.AS_KNOWN, pool=pool) is None
    still = read_selected(checked_store, key, cutoff=now, mode=RunMode.AS_KNOWN, pool=pool)
    assert still is not None and still.label is AdmissionLabel.CHECKED_AGAINST_FILING

    # A licence end on the witness's vendor withdraws even a historical read, and no new
    # admission may cite that witness, though the store's retention guard sees only the chosen.
    with pool.connection() as conn:
        sources = {
            tuple(
                conn.execute(WITNESS_CAPTURE, (interpretation,)).fetchone()[1]
                for interpretation in (r.interpretation_id, r.witness_interpretation_id)
            )
            for r in records.values()
            if r.witness_interpretation_id is not None
        }
    ((_, witness_source),) = sources  # one chosen vendor and one witness vendor for every cell
    with stage.pg_db.owner_pool() as owner, owner.connection() as conn:
        conn.execute("INSERT INTO eqos.licence_ends (source_id) VALUES (%s)", (witness_source,))
    assert (
        read_selected(
            unchecked_store, key, cutoff=known_unchecked, mode=RunMode.AS_KNOWN, pool=pool
        )
        is None
    )
    with pytest.raises(BridgeError, match="licence has ended"):
        _admit(stage, filed, "ended")


def test_an_expired_witness_withdraws_a_checked_vendor_fact(laurus: Stage) -> None:
    """§6.9 for a row-1 fact: once its other witness's capture expires, nothing is read."""
    stage, pool = laurus, laurus.pool
    stage.first_party()
    run_id = _run(stage, Q3)
    record = _records(stage, run_id, _admit(stage, run_id, "checked"))[REVENUE]
    assert record.label is AdmissionLabel.CHECKED_AGAINST_FILING
    _select(stage, record)
    store = PgFactStore(pool, record.ref.store_id)
    (row,) = [row for row in load_results(run_id, pool=pool) if row.row_id == REVENUE]
    now = stage.repository.store_clock()
    found = read_selected(store, row.key, cutoff=now, mode=RunMode.AS_KNOWN, pool=pool)
    assert found is not None and found.value == 1415 * CRORE
    with pool.connection() as conn:
        (witness, _) = conn.execute(WITNESS_CAPTURE, (record.witness_interpretation_id,)).fetchone()
    with stage.pg_db.migrator_connection() as migrator:
        migrator.execute(CAPTURE_STATE, (witness, "EXPIRED"))
    assert read_selected(store, row.key, cutoff=now, mode=RunMode.AS_KNOWN, pool=pool) is None


def test_failed_filing_refuses_before_agreeing_vendors(pg_db: Any, tmp_path: Path) -> None:
    """Row 0b: a filing whose XBRL and PDF disagree refuses ``FILING_UNRESOLVED`` with its
    failure, although both vendors agree on the cell."""
    with pg_db.runtime_pool() as pool:
        stage = Stage(pg_db, pool, tmp_path, RUNS["APARINDS-Q2FY26"])
        stage.config, stage.versions = load_run_config(CONFIG, V9), V9
        stage.first_party(XBRL_DIFFERS)
        stage.vendors()
        run_id = stage.execute(
            vendors=[f"{SCREENER}/SCREENER_FINANCIALS", f"{TIJORI}/financials"]
        ).run_id
        (row,) = [row for row in load_results(run_id, pool=pool) if row.row_id == APAR_REVENUE]
        inputs, _, config = replay_inputs(run_id, pool=pool, config_root=CONFIG)
        interpretations = {item.interpretation_id: item for item in inputs.interpretations}
        assert config.vendor_first_policy is not None
        outcome, _ = vendor_outcome(
            row, interpretations, config.mapping_set, config.vendor_first_policy
        )
        assert outcome is VendorOutcome.VENDORS_AGREE
        _dispose_all(stage, run_id, row)  # the XBRL/PDF disagreement routes its own HIGH
        admitted = admit_run(run_id, pool=pool, store_id=create_native_store(pool, "failed"))
        assert dict(admitted.refusals)[row.row_id] is AdmissionRefusal.FILING_UNRESOLVED
        assert dict(admitted.filing_failures)[row.row_id] is FilingFailure.EXTRACTION_NOT_AGREE


def _run(stage: Stage, end: date, eligibility: str | None = None) -> int:
    """A Screener and Tijori run of ``end`` pinning the policy and, if named, an eligibility."""
    stage.end, stage.versions = end, V9.model_copy(update={"eligibility": eligibility})
    return stage.execute().run_id


def _admit(stage: Stage, run_id: int, label: str) -> AdmissionOutcome:
    """``admit_run`` into a fresh store, under the stage's config root."""
    store_id = create_native_store(stage.pool, label)
    return admit_run(run_id, pool=stage.pool, store_id=store_id, config_root=stage.config_root)


def _artifacts(stage: Stage, run_id: int) -> str:
    """Write the ``fixture`` artifact (every agreeing class of the run eligible) and the
    ``mismatch`` one (the same cells under another policy version); the revenue class."""
    inputs, request, config = replay_inputs(run_id, pool=stage.pool, config_root=stage.config_root)
    policy = config.vendor_first_policy
    assert policy is not None
    interpretations = {item.interpretation_id: item for item in inputs.interpretations}
    agreeing = [
        row
        for row in load_results(run_id, pool=stage.pool)
        if vendor_outcome(row, interpretations, config.mapping_set, policy)[0]
        is VendorOutcome.VENDORS_AGREE
    ]
    classes = {
        row.row_id: row_class(row, interpretations, inputs, request, config, NON_FINANCIAL)
        for row in agreeing
    }
    other = [
        check_class(
            row,
            interpretations,
            mapping=config.mapping_set,
            extractor_pins=request.pinned.vendor_extractors,
            dictionary_version=config.dictionary.version,
            policy_version="v2",
            issuer_class=NON_FINANCIAL,
            period_kind=row.key.period.kind(3),
        )
        for row in agreeing
    ]
    folder = stage.config_root / ELIGIBILITY_DIR
    folder.mkdir(parents=True, exist_ok=True)
    for name, digests in (("fixture", classes.values()), ("mismatch", other)):
        artifact = EligibilityArtifact(
            available_from=datetime(2000, 1, 1, tzinfo=UTC),
            code_version="test",
            classes=tuple(
                ClassEvidence(class_digest=d, agrees=4, differs=0, run_ids=(run_id,), eligible=True)
                for d in sorted(set(digests))
            ),
        )
        (folder / f"{name}.yaml").write_text(yaml.safe_dump(artifact.model_dump(mode="json")))
    return classes[REVENUE]


def _records(stage: Stage, run_id: int, outcome: AdmissionOutcome) -> dict[str, AdmissionRecord]:
    """An outcome's records by row id."""
    rows = {row.key.digest(): row.row_id for row in load_results(run_id, pool=stage.pool)}
    return {rows[record.key_digest]: record for record in outcome.records}


def _fact(stage: Stage, record: AdmissionRecord) -> Any:
    """The admitted fact a record names."""
    store = PgFactStore(stage.pool, record.ref.store_id)
    rows = load_results(record.run_id, pool=stage.pool)
    row = next(row for row in rows if row.key.digest() == record.key_digest)
    (revision,) = [
        item for item in store.get_revisions(key_identity(row.key)) if item.row_id == record.handle
    ]
    return revision.fact


def _select(stage: Stage, record: AdmissionRecord) -> None:
    """Select an admission's fact as the first selection of its store."""
    select_admitted(
        stage.pool,
        store_id=record.ref.store_id,
        admission_id=record.admission_id,
        reason="test: selected",
        expected_selection_id=0,
    )


def _open_high(stage: Stage, run_id: int, row: ResultRow) -> int:
    """Publish an open non-diagnostic HIGH item naming the row's key."""
    draft = QueueItemDraft(
        key=row.key,
        pair_identity="test-high",
        outcome="MISMATCH",
        severity=QueueSeverity.HIGH,
        evidence_interpretation_ids=tuple(
            value.interpretation_id
            for value in row.source_values
            if value.source_id is None and value.interpretation_id is not None
        ),
    )
    with stage.pool.connection() as conn, conn.transaction(), conn.cursor() as cursor:
        lock_queue(cursor)
        (item_id,) = publish_queue_drafts(cursor, run_id=run_id, drafts=[draft])
    return int(item_id)


def _dispose(stage: Stage, item_id: int) -> None:
    """Dismiss one queue item."""
    with stage.pg_db.owner_pool() as owner:
        record_disposition(
            owner,
            item_id=item_id,
            kind=DispositionKind.DISMISSED,
            reason="test: closes the HIGH",
            decider="test",
            evidence_ref="test-only",
        )


def _dispose_all(stage: Stage, run_id: int, row: ResultRow) -> None:
    """Dismiss every open HIGH item of the run naming the row's key."""
    overlay = read_overlay(stage.pool, run_id=run_id, as_of=overlay_boundary(stage.pool))
    for item in overlay.open_items:
        if item.key is not None and item.key.digest() == row.key.digest():
            if item.severity is QueueSeverity.HIGH:
                _dispose(stage, item.item_id)
