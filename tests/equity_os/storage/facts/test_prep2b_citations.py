"""PREP-2b Task 3: run-written native facts resolve as ``FIGURE`` citations, issuer-checked.

A native row is the run's own fact: its key comes from ``translate``, its capture is the
first-party capture of its file, and it resolves only when its observation names the report's
issuer. Without a selection it has no ``SELECTED`` time and stays past every cutoff; its row's
and selection's store-clock recording times bound it however early the writer dates it.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from ledger_cited_support import Cited, _figure, cited

from equity_os.contracts.measurement.evidence import RunMode
from equity_os.contracts.measurement.fact import Fact
from equity_os.contracts.publication.ledger import ClaimState, InputTime, NumericClaim
from equity_os.normalisation.dictionary.role_translation import translate
from equity_os.publication.checking.claim_check import check_claim
from equity_os.storage.database.settings import PgRole
from equity_os.storage.facts.pg_fact_store import NATIVE_ORIGIN, PgFactStore, create_native_store

__all__ = ["cited"]

pytestmark = [pytest.mark.pg, pytest.mark.retained]

_FACT_JSON = "SELECT fact_json FROM eqos.fact_rows WHERE origin = %s AND origin_id = %s"
_ROW = "SELECT handle, content_identity FROM eqos.fact_rows WHERE origin = %s AND origin_id = %s"
_CANDIDATE = """SELECT handle, origin_id FROM eqos.fact_rows
WHERE target_store = %s AND content_identity = %s AND handle <> %s"""
_OPEN_EVENT = """INSERT INTO eqos.fact_store_events (store_id, operation_id, state, recorded_at)
VALUES (%s, %s, 'OPEN', eqos.store_now())"""
# Sol r2's bypass: a copy of a native row and a selection of it, inserted with Sept 9 times.
_FORGED_ROW = """INSERT INTO eqos.fact_rows SELECT target_store, handle + 1, origin,
    nextval('eqos.fact_native_id'), content_identity, 'forged', revision_family,
    revision_ordinal + 1, canonical_status, canonical_selected_at, canonical_reason, source_id,
    file_sha256, anchor, valid_time_start, valid_time_end, knowledge_time, first_seen_time,
    fact_json, %(at)s FROM eqos.fact_rows WHERE origin = %(origin)s AND origin_id = %(id)s
RETURNING target_store, handle, origin_id, content_identity"""
_FORGED_SELECTION = """INSERT INTO eqos.fact_selections (target_store, handle, origin, origin_id,
    content_identity, row_handle, sequence, predecessor_handle, selected_at, reason,
    legacy_baseline, synthesized, selection_sha256, recorded_at)
VALUES (%s, 1, 'pg-native', nextval('eqos.fact_native_id'), %s, %s, 1, NULL, %s, 'forged',
    false, false, 'forged', %s)"""


def _native(
    cited: Cited,
    *,
    selected: bool = True,
    claimed: datetime | None = None,
    **observation: Any,
) -> NumericClaim:
    """A ``FIGURE`` on a native copy of the FY27_Q1 revenue fact, its observation updated;
    ``claimed``: the knowledge, first-seen and selection time the writer states."""
    ((fact_json,),) = cited.query(_FACT_JSON, cited.revenue_origin, cited.revenue_origin_id)
    fact = Fact.model_validate_json(fact_json)
    fact = fact.model_copy(update={"observation": fact.observation.model_copy(update=observation)})
    if claimed is not None:
        fact = fact.model_copy(update={"knowledge_time": claimed, "first_seen_time": claimed})
    pool = cited.pools[PgRole.RUNTIME]
    store = PgFactStore(pool, create_native_store(pool, "cited"))
    row_id = store.put(fact).row_id
    if selected:
        store.select_canonical(row_id, "test: run selection", claimed)
    ref = store.fact_ref(row_id)
    assert ref.origin == NATIVE_ORIGIN
    key = translate(fact, entity_id=cited.entity_id)
    return _figure(key, fact_origin=ref.origin, fact_origin_id=ref.origin_id)


def _state(cited: Cited, claim: NumericClaim, cutoff: datetime | None = None) -> ClaimState:
    """The AS_KNOWN claim check of ``claim`` at ``cutoff`` (default: now)."""
    resolved = cited.resolve(claim)
    at = cutoff or datetime.now(UTC)
    return check_claim(claim, resolved, mode=RunMode.AS_KNOWN, cutoff=at, imported=False)


def test_a_selected_native_fact_matches(cited: Cited) -> None:
    """The run's selected revenue row resolves to its value, key and times, and matches."""
    claim = _native(cited)
    resolved = cited.resolve(claim)
    assert resolved is not None and claim.measurement_key is not None
    assert (resolved.value, resolved.unit, resolved.scale, resolved.key_digest) == (
        claim.value,
        claim.unit,
        claim.scale,
        claim.measurement_key.digest(),
    )
    times = {InputTime.KNOWLEDGE, InputTime.FIRST_SEEN, InputTime.SELECTED, InputTime.RECORDED}
    assert {name for name, _ in resolved.times} == times
    assert _state(cited, claim) is ClaimState.MATCH


def test_an_unselected_native_fact_is_post_cutoff(cited: Cited) -> None:
    """A row the run never selected has no selection time: it cannot be cited as known."""
    assert _state(cited, _native(cited, selected=False)) is ClaimState.POST_CUTOFF


def test_a_backdated_native_fact_is_post_cutoff(cited: Cited) -> None:
    """A row written now that states 2026-09-09 knowledge, first-seen and selection times is
    held to its store-clock insertion and selection-recording times: past a 2026-09-10 cutoff
    (its capture was first seen 2026-09-06/07), known now."""
    claim = _native(cited, claimed=datetime(2026, 9, 9, tzinfo=UTC))
    assert _state(cited, claim, datetime(2026, 9, 10, tzinfo=UTC)) is ClaimState.POST_CUTOFF
    assert _state(cited, claim) is ClaimState.MATCH


def test_a_native_row_and_selection_inserted_with_backdated_times_are_post_cutoff(
    cited: Cited,
) -> None:
    """Runtime SQL that supplies Sept 9 ``created_at`` and ``recorded_at`` gets the store clock
    instead (migration 0037): the forged row is past a 2026-09-10 cutoff, known now."""
    claimed = datetime(2026, 9, 9, tzinfo=UTC)
    claim = _native(cited, selected=False, claimed=claimed)
    origin, origin_id = claim.citation.fact_origin, claim.citation.fact_origin_id
    with cited.runtime() as cursor:
        params = {"at": claimed.isoformat(), "origin": origin, "id": origin_id}
        row = cursor.execute(_FORGED_ROW, params).fetchone()
        assert row is not None
        store, handle, forged, identity = row
        at = claimed.isoformat()
        cursor.execute(_FORGED_SELECTION, (store, identity, handle, at, claimed))
    claim = claim.model_copy(
        update={"citation": claim.citation.model_copy(update={"fact_origin_id": forged})}
    )
    assert _state(cited, claim, datetime(2026, 9, 10, tzinfo=UTC)) is ClaimState.POST_CUTOFF
    assert _state(cited, claim) is ClaimState.MATCH


def test_another_issuers_fact_is_unresolved(cited: Cited) -> None:
    """Same value, another issuer: the report's entity does not own it."""
    claim = _native(cited, entity_id="INFY")
    assert cited.resolve(claim) is None
    assert _state(cited, claim) is ClaimState.UNRESOLVED


def test_a_fact_with_no_first_party_capture_is_unresolved(cited: Cited) -> None:
    """A fact whose file no first-party capture holds has no authority."""
    ((fact_json,),) = cited.query(_FACT_JSON, cited.revenue_origin, cited.revenue_origin_id)
    provenance = Fact.model_validate_json(fact_json).observation.provenance
    claim = _native(cited, provenance=provenance.model_copy(update={"file_sha256": "0" * 64}))
    assert _state(cited, claim) is ClaimState.UNRESOLVED


def _legacy(cited: Cited, origin_id: int) -> NumericClaim:
    """An unkeyed ``FIGURE`` on an imported fact of the legacy store, at its resolved value."""
    claim = _figure(None, fact_origin=cited.revenue_origin, fact_origin_id=origin_id)
    resolved = cited.resolve(claim)
    assert resolved is not None
    return claim.model_copy(update={"value": resolved.value})


def test_a_native_selection_of_an_imported_fact_is_held_to_its_recording_time(
    cited: Cited,
) -> None:
    """Closing r1 #1: the imported FY27_Q1 revenue candidate selected natively now, dated an
    hour after the import's selection, is past a 2026-09-08 cutoff — where ``get_canonical``
    still answers the imported canonical row, whose imported selection keeps its legacy time."""
    store_id, cutoff = cited.revenue_origin, datetime(2026, 9, 8, tzinfo=UTC)
    ((handle, identity),) = cited.query(_ROW, store_id, cited.revenue_origin_id)
    ((candidate, candidate_id),) = cited.query(_CANDIDATE, store_id, identity, handle)
    with cited.runtime() as cursor:
        cursor.execute(_OPEN_EVENT, (store_id, uuid.uuid4()))
    store = PgFactStore(cited.pools[PgRole.RUNTIME], store_id)
    imported = store.get_selection_history(identity)[-1].selected_at
    store.select_canonical(candidate, "test: native reselection", imported + timedelta(hours=1))
    canonical = store.get_canonical(identity, cutoff=cutoff)
    assert canonical is not None and canonical.row_id == handle
    reselected = _legacy(cited, candidate_id)
    resolved = cited.resolve(reselected)
    assert resolved is not None
    assert all(
        at is not None and at <= cutoff
        for name, at in resolved.times
        if name is not InputTime.SELECTED
    )
    assert _state(cited, reselected, cutoff) is ClaimState.POST_CUTOFF
    assert _state(cited, reselected) is ClaimState.MATCH
    assert _state(cited, _legacy(cited, cited.revenue_origin_id), cutoff) is ClaimState.MATCH


@pytest.mark.parametrize("case", ["legacy_revenue", "interpretation_figure", "comparison"])
def test_a_keyed_citation_resolves_only_for_its_issuer(cited: Cited, case: str) -> None:
    """Closing r1 #2: the issuer's legacy translation, run-bound figure or run comparison cited
    in another stock's report is ``UNRESOLVED`` — never a (trusted or untrusted) match."""
    claim = getattr(cited, case)()
    assert cited.resolve(claim) is not None
    assert cited.resolve(claim, cited.entity_id + 1) is None
