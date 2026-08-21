"""Slice 2 store tests: append-only, revision-aware provenance fact store.

Covers the roadmap §8 invariants: identical content identity + values is
idempotent (no duplicate); a same-identity different-value put appends a new
retained revision under the same family; canonical selection is a separate,
auditable step that supersedes (never deletes) the prior canonical revision; an
un-provenanced fact is rejected fail-closed; and canonical queries return the
selected revision.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from fundamentals.contracts.fact import CanonicalStatus, Fact, ReconciliationStatus
from fundamentals.contracts.observation import (
    AccountingFramework,
    Observation,
    PeriodType,
    Scope,
)
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.store.fact_store import FactStore, UnprovenancedFactError

_RETRIEVED_AT = datetime(2024, 7, 18, tzinfo=UTC)


def _provenance(file_sha256: str = "0" * 64) -> Provenance:
    return Provenance(
        source_id="nse-indas-xbrl-consolidated",
        file_sha256=file_sha256,
        anchor_type=SourceAnchorType.XBRL_CONTEXT,
        context_ref="OneD",
        retrieved_at=_RETRIEVED_AT,
    )


def _observation(
    normalized_value: str = "6374",
    raw_value: str = "63740000000",
    provenance: Provenance | None = None,
) -> Observation:
    return Observation(
        concept_qname="in-bse-fin:ProfitLossForPeriod",
        taxonomy_namespace="http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin",
        registry_version="in-bse-fin/2020-03-31",
        raw_value=raw_value,
        normalized_value=Decimal(normalized_value),
        normalized_unit="INR crore",
        context_ref="OneD",
        entity_scheme="nse-symbol",
        entity_id="INFY",
        scope=Scope.CONSOLIDATED,
        accounting_basis=AccountingFramework.IND_AS,
        period_type=PeriodType.DURATION,
        period_start=date(2024, 4, 1),
        period_end=date(2024, 6, 30),
        unit_ref="INR",
        currency="INR",
        scale=10_000_000,
        decimals=-7,
        provenance=provenance if provenance is not None else _provenance(),
    )


def _fact(observation: Observation | None = None) -> Fact:
    return Fact(
        observation=observation if observation is not None else _observation(),
        reconciliation_status=ReconciliationStatus.CROSS_FOOT_PASS,
        canonical_status=CanonicalStatus.CANDIDATE,
        revision_family="infy-fy25q1-profit",
        valid_time_start=date(2024, 4, 1),
        valid_time_end=date(2024, 6, 30),
        knowledge_time=_RETRIEVED_AT,
        first_seen_time=_RETRIEVED_AT,
    )


@pytest.fixture
def store(tmp_path: Path) -> FactStore:
    fact_store = FactStore(tmp_path / "facts.db")
    yield fact_store
    fact_store.close()


def test_round_trip_put_and_get(store: FactStore) -> None:
    stored = store.put(_fact())
    revisions = store.get_revisions(stored.content_identity)

    assert len(revisions) == 1
    only = revisions[0]
    assert only.fact.observation.normalized_value == Decimal("6374")
    assert only.fact.observation.provenance.file_sha256 == "0" * 64
    assert only.revision_family == "infy-fy25q1-profit"
    assert only.revision_ordinal == 1
    # Canonical selection is a separate step: a fresh put lands as CANDIDATE.
    assert only.canonical_status is CanonicalStatus.CANDIDATE


def test_reput_identical_fact_is_idempotent(store: FactStore) -> None:
    first = store.put(_fact())
    second = store.put(_fact())

    assert first.row_id == second.row_id
    assert len(store.get_revisions(first.content_identity)) == 1


def test_same_identity_different_value_appends_revision(store: FactStore) -> None:
    original = store.put(_fact())
    canonical = store.select_canonical(original.row_id, reason="initial extraction")
    assert canonical.canonical_status is CanonicalStatus.CANONICAL

    # A restatement: same comparison key, corrected value.
    restated = store.put(_fact(_observation(normalized_value="6400", raw_value="64000000000")))

    revisions = store.get_revisions(original.content_identity)
    assert len(revisions) == 2  # both retained
    assert restated.row_id != original.row_id
    assert restated.revision_family == original.revision_family
    assert restated.revision_ordinal == 2

    # The separate, auditable selection step promotes the restatement and
    # supersedes (does not delete) the prior canonical revision.
    promoted = store.select_canonical(restated.row_id, reason="restatement adopted")
    assert promoted.canonical_status is CanonicalStatus.CANONICAL
    assert promoted.canonical_reason == "restatement adopted"
    assert promoted.canonical_selected_at is not None

    after = {rev.row_id: rev for rev in store.get_revisions(original.content_identity)}
    assert after[original.row_id].canonical_status is CanonicalStatus.SUPERSEDED
    assert after[restated.row_id].canonical_status is CanonicalStatus.CANONICAL
    assert len(after) == 2  # nothing overwritten or removed


def test_unprovenanced_fact_is_rejected(store: FactStore) -> None:
    unprovenanced = _fact(_observation(provenance=_provenance(file_sha256="")))
    with pytest.raises(UnprovenancedFactError):
        store.put(unprovenanced)

    # Fail-closed: nothing was written.
    identity = FactStore.content_identity_for(unprovenanced.observation)
    assert store.get_revisions(identity) == ()


def test_query_returns_canonical_revision(store: FactStore) -> None:
    original = store.put(_fact())
    store.select_canonical(original.row_id, reason="initial extraction")
    restated = store.put(_fact(_observation(normalized_value="6400", raw_value="64000000000")))
    store.select_canonical(restated.row_id, reason="restatement adopted")

    canonical = store.get_canonical(original.content_identity)
    assert canonical is not None
    assert canonical.row_id == restated.row_id
    assert canonical.fact.observation.normalized_value == Decimal("6400")

    all_canonical = store.query_canonical()
    assert len(all_canonical) == 1
    assert all_canonical[0].row_id == restated.row_id
