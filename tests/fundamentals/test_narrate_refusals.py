"""RESEARCH-3 S3 Task 3: what ``ledger narrate`` and the panel refuse on the pilot.

Why: a refusal must leave every table unchanged, because a narrated version reaches a panel that
decides on it. Production names import through ``code``; see ``narrate_support``."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import narrate_support as ns
import pytest
import yaml
from ledger_cited_support import _figure
from narrate_support import code_exists, dictionary, ingest, mapping_set, pilot, policy
from pg_evidence_schema_support import _insert, _interpretation, _occurrence
from prep2b_support import Pilot
from purge_support import VENDOR, entity, ref_of
from retained_support import REPO_ROOT
from retention_support import record_of
from test_prep2b_run_draft import Q2_QUARTER, _append, _compare_run

from fundamentals.compare.run import load_results
from fundamentals.contracts.canonical import Representation, ValueIdentity
from fundamentals.contracts.comparison import SourceRole
from fundamentals.contracts.ledger import ClaimState, SubjectKind, VersionDraft, VersionState
from fundamentals.contracts.retention import OriginalExpiredError
from fundamentals.evidence.capture_retention import capture_registration
from fundamentals.ledger import lifecycle, panel, store
from fundamentals.ledger.citations import resolve_location
from fundamentals.ledger.display import content_hash
from fundamentals.thesis.client import ModelResponse, ThesisClientError

__all__ = ["code_exists", "dictionary", "ingest", "mapping_set", "pilot", "policy"]
pytestmark = [pytest.mark.pg, pytest.mark.retained]


def register(pilot: Pilot, payload: bytes, source: str, surface: str) -> Any:
    """A capture of ``payload`` registered now, first seen after every version's cutoff."""
    record = record_of(payload, source, surface)
    pilot.snapshots.put_capture(record, payload)
    with pilot.pg_db.runtime_pool() as pool, capture_registration(pool) as registration:
        return registration.insert(ref_of(record), url=None).capture_ref_id


def read_from(conn: Any, entity_id: int, capture: int, tag: str) -> int:
    """An interpretation of ``capture`` bound to ``entity_id``."""
    occurrence = _insert(conn, "occurrences", _occurrence(capture, tag))
    return int(_insert(conn, "interpretations", _interpretation(entity_id, capture, occurrence)))


def transcript_copy(pilot: Pilot, version: VersionDraft, entity_id: int) -> tuple[Any, Any]:
    """A first-party capture registered now of N's transcript plus one byte, bound to ``entity_id``:
    its id and a span that resolves. A new blob has no retrieval history, unlike every original."""
    cited: Any = next(c.citation for c in version.claims if c.citation.quote)
    columns = "SELECT source_id, surface, request_key, capture_id FROM eqos.capture_refs"
    ((source, surface, *identity),) = pilot.query(f"{columns} WHERE id = %s", cited.capture_ref_id)
    copied = pilot.snapshots.read_capture_verified(source, surface, *identity)[1] + b"\n"
    new = register(pilot, copied, source, surface)
    with pilot.pg_db.migrator_connection() as conn:
        read_from(conn, entity_id, new, "narrate-copy")
    return new, cited.anchor


def resolves(pilot: Pilot, capture: int, span: str, cutoff: datetime) -> Any:
    """``resolve_location`` at ``cutoff``, as the runtime role."""
    opts: dict[str, Any] = {"entity_id": pilot.entity_id, "cutoff": cutoff} | pilot.sources()
    return ns.reading(pilot, lambda cur: resolve_location(cur, str(capture), span, **opts))


def test_each_bad_draft_writes_nothing(pilot: Pilot) -> None:
    """Spec §5's refusals, on one prepared N. A later disclosure and an uncited span of N's own
    transcript both resolve at N's cutoff (C-5), so citable membership is what refuses them."""
    version, held = ns.prepared(pilot)
    longest = max(ns.quotes(held), key=len)
    cited: Any = next(c for c in held.claims if c.citation.quote == longest)
    own, anchor, key = cited.citation.capture_ref_id, cited.citation.anchor, cited.claim_key
    tight = ns.limits(max_span_chars=len(longest) - 1)
    with pilot.pg_db.migrator_connection() as conn:
        other = transcript_copy(pilot, held, entity(conn))
    targets = (REPO_ROOT / "config/guidance_targets/aparinds.yaml").read_text("utf-8")
    late = next(e for e in yaml.safe_load(targets)["entries"] if e["id"].endswith("FY27_Q1"))
    captures = "SELECT id FROM eqos.capture_refs WHERE "
    ((later,),) = pilot.query(
        captures + "blob_sha256 = %s AND source_id LIKE %s", late["source_sha256"], "%transcript%"
    )
    ((outside,),) = pilot.query(captures + "source_id LIKE %s", "%fy26-q3-results%")
    start, end = anchor.rsplit(":", 1)
    uncited = f"{start}:{int(end) - 1}"
    assert resolves(pilot, later, late["anchor"], held.knowledge_cutoff)
    assert resolves(pilot, own, uncited, held.knowledge_cutoff)

    def said(text: str, section: str = "drivers") -> str:
        return ns.draft(held, **{section: ns.LABEL + text})

    def located(capture: int, span: str) -> str:
        return said(f"Said so {{{{s:{capture}|{span}}}}}.")

    rows: tuple[tuple[Any, ...], ...] = (
        (said("Revenue was forty."), "forty"),
        (said("amount:123"), "123"),
        (said("\n1. A numbered item."), "1"),
        (said("Down -{{c:fact.revenue|}}."), "fact.revenue"),
        (said("Many {{c:fact.revenue|}}x over."), "fact.revenue"),
        (said("Say amount:{{c:fact.revenue|}}."), "fact.revenue"),
        (said("Styled {{c:fact.revenue|x2}}."), "x2"),
        (said("Unknown {{c:fact.no_such_key|ref}}."), "fact.no_such_key"),
        (located(*other), re.escape(other[1])),
        (located(later, late["anchor"]), re.escape(late["anchor"])),
        (located(outside, "p1.b0.0:5"), "p1.b0.0:5"),
        (located(own, uncited), uncited),
        (ns.draft(held, conclusions=ns.LABEL + "Extra."), "conclusions"),
        (ns.draft(held, risk_probe=ns.LABEL + "Edited."), ns.PROBE),
        (ns.draft(held, risk_notes="{{e:inferred}} No note."), "probe.R6"),
        (said("The target was achieved.", "credibility_notes"), "achiev"),
        (ns.draft(held, risk_notes="{{e:inferred}}"), "risk_notes"),
        (located(own, anchor), anchor, tight),
        (said(f"Quoted {{{{c:{key}|quote}}}}."), key, tight),
        (said(f"Named {{{{c:{key}|ref}}}}."), key, tight),
    )
    for text, cause, *kept in rows:
        ns.refused(pilot, version, ns.FakeClient(text), cause, True, *kept)


def test_a_first_seen_capture_after_the_cutoff_refuses(
    pilot: Pilot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C-5: a capture handed in through a citable set still falls to ``resolve_location``'s own
    first-seen boundary: it resolves at a later cutoff and not at N's."""
    version, held = ns.prepared(pilot)
    capture, anchor = transcript_copy(pilot, held, pilot.entity_id)
    assert resolves(pilot, capture, anchor, datetime.now(UTC) + timedelta(days=1))
    assert not resolves(pilot, capture, anchor, held.knowledge_cutoff)
    real = ns.code().flow.build_bundle

    def citing(*args: Any, **kwargs: Any) -> Any:
        made = real(*args, **kwargs)
        return made.model_copy(update={"citable": made.citable | {(str(capture), anchor)}})

    monkeypatch.setattr(ns.code().flow, "build_bundle", citing)
    text = ns.draft(held, drivers=f"{ns.LABEL}Said so {{{{s:{capture}|{anchor}}}}}.")
    cause = f"UNCITED_PROSE|{re.escape(anchor)}"
    ns.refused(pilot, version, ns.FakeClient(text), cause, called=True)


def test_an_expired_capture_reached_only_through_a_dependency_refuses(pilot: Pilot) -> None:
    """V1: the cited trace's own interpretation is first-party; only its condition evidence rests
    on the expired vendor capture, which is what R13 follows. Refused before the client runs."""
    version, held = ns.prepared(pilot)
    trace = next(
        c.citation.calculation_trace_id for c in held.claims if c.citation.calculation_trace_id
    )
    ((operand,),) = pilot.query(
        "SELECT interpretation_id FROM eqos.calculation_trace_operands "
        "WHERE calculation_trace_id = %s AND interpretation_id IS NOT NULL LIMIT 1",
        trace,
    )
    vendor = register(pilot, b"vendor synthetic", *VENDOR)
    with pilot.pg_db.migrator_connection() as conn:
        rests_on = read_from(conn, pilot.entity_id, vendor, "narrate-vendor")
        evidence = {"interpretation_id": operand, "condition_id": "z", "holds": True}
        evidence |= {"evidence_interpretation_id": rests_on}
        _insert(conn, "interpretation_condition_evidence", evidence)
        states = "INSERT INTO eqos.capture_states (capture_ref_id, state) VALUES (%s, 'EXPIRED')"
        conn.execute(states, (vendor,))
    client = ns.FakeClient(ns.draft(held))
    error = (OriginalExpiredError, ns.code().flow.NarrateRefusedError)
    with ns.writes_nothing(pilot, "ORIGINAL_EXPIRED", error):
        ns.narrate(pilot, version, client)
    assert client.prompts == []


def test_narrate_refuses_the_wrong_version(pilot: Pilot) -> None:
    """Spec §4: only an approved head with no narrative is the one legal order, and a refusal comes
    before the model call. One pilot walks every wrong state."""
    client = ns.FakeClient()
    first = ns.q2_draft(pilot)
    ns.refused(pilot, first, client, "DRAFT")
    ns.submit(pilot, first)
    ns.refused(pilot, first, client, "IN_REVIEW")
    pilot.approve(first, submit=False)
    ((thesis,),) = pilot.query(ns.THESES)
    ns.refused(pilot, thesis, client, "head")
    head = ns.rerun_draft(pilot)
    ns.refused(pilot, first, client, "head")
    pilot.approve(head)
    client.text = ns.draft(pilot.version(head))
    narrated = ns.narrate(pilot, head, client)
    pilot.approve(narrated)
    ns.refused(pilot, narrated, ns.FakeClient(), "narrat")


def test_a_bundle_over_the_cap_refuses(pilot: Pilot, monkeypatch: pytest.MonkeyPatch) -> None:
    """A18, S4: each limit, a client failure and a changed disclosure write nothing; only what comes
    after the model call has called it."""
    version, held = ns.prepared(pilot)

    class Failing(ns.FakeClient):
        def generate(self, prompt: str) -> ModelResponse:
            raise ThesisClientError("the fake client failed")

    text = ns.draft(held)
    for cause, called in (
        ("max_total_bytes", False),
        ("max_prompt_bytes", False),
        ("max_response_bytes", True),
    ):
        ns.refused(pilot, version, ns.FakeClient(text), cause, called, ns.limits(**{cause: 1}))
    ns.refused(pilot, version, Failing(), "the fake client failed")
    other = ns.body(held, "not_performed").replace("- an earnings-driver analysis", "- other words")
    changed, real = ns.with_section(held, "not_performed", other), store.read_version
    monkeypatch.setattr(
        store, "read_version", lambda cur, id_: changed if id_ == version else real(cur, id_)
    )
    # This order, before the model call, is what the pure exemption test leans on.
    ns.refused(pilot, version, ns.FakeClient(text), "not_performed")


def test_a_failed_check_after_insert_rolls_back(
    pilot: Pilot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """S13: a passing run accepts ``MATCH_UNTRUSTED``, narrate does not (C-10), and whatever fails
    after ``create_version`` leaves no row. The bad check is injected: no honest way there."""
    version, held = ns.prepared(pilot)
    real = ns.code().flow.check_version

    def failing(*args: Any, **kwargs: Any) -> Any:
        states = (VersionState.UNCITED_PROSE,)
        return real(*args, **kwargs).model_copy(update={"version_states": states})

    with monkeypatch.context() as patch:
        patch.setattr(ns.code().flow, "check_version", failing)
        ns.refused(pilot, version, ns.FakeClient(ns.draft(held)), "UNCITED_PROSE", called=True)
    run_id = _compare_run(pilot, "FY26_Q2")
    with pilot.pg_db.runtime_pool() as pool:
        (row,) = (
            r
            for r in load_results(run_id, pool=pool)
            if (r.key.canonical_id, r.key.period) == ("profit_for_period", Q2_QUARTER)
            and not r.key.dimensions.pairs
            and r.value_identity is ValueIdentity.REPORTED
        )
        filed: Any
        (filed,) = (
            v
            for v in row.source_values
            if v.source_role is SourceRole.FIRST_PARTY and v.representation is Representation.XBRL
        )
        cell = _figure(row.key, interpretation_id=filed.interpretation_id, run_id=run_id)
        update: dict[str, Any] = {"value": filed.value / 10**7, "claim_key": "cell.profit"}
        claims = (*held.claims, cell.model_copy(update=update))
        update = {"predecessor_id": version, "claims": claims}
        update |= {"content_hash": content_hash(held.sections, claims)}
        with pool.connection() as conn, conn.transaction(), conn.cursor() as cursor:
            cursor.execute(lifecycle._LOCK, (SubjectKind.WATCHLIST.value, pilot.entity_id))
            untrusted = store.create_version(cursor, held.model_copy(update=update))
    assert ClaimState.MATCH_UNTRUSTED in dict(pilot.validate(untrusted).claim_states).values()
    pilot.approve(untrusted)
    with ns.writes_nothing(pilot, "MATCH_UNTRUSTED"):
        ns.narrate(pilot, untrusted, ns.FakeClient(ns.draft(pilot.version(untrusted))))


def test_the_panel_refuses_a_narrated_version(pilot: Pilot) -> None:
    """S13: no limits, or a rebuilt bundle whose hash is not the author's, means the panel would
    read other evidence than the model saw; the reviewer is never called."""
    version, held = ns.prepared(pilot)
    new = ns.narrate(pilot, version, ns.FakeClient(ns.draft(held)))
    ns.submit(pilot, new)
    reviewer = ns.FakeReviewer()
    opts: dict[str, Any] = {"subject_kind": SubjectKind.REPORT_VERSION, "subject_id": new}
    error = lifecycle.DecisionRefusedError
    for kept in (None, ns.limits(max_span_chars=len(max(ns.quotes(held), key=len)) - 1)):
        with ns.writes_nothing(pilot, "", error), pilot.pg_db.panel_pool() as pool:
            panel.review(pool, reviewer=reviewer, **(opts | {"limits": kept}), **pilot.sources())
        assert reviewer.calls == []


def test_a_stale_head_refuses_under_lock(pilot: Pilot) -> None:
    """P1: the model call runs outside any transaction, so the head can move during it; narrate
    rechecks under the lock and writes no second version."""
    version, held = ns.prepared(pilot)

    class Racing(ns.FakeClient):
        def generate(self, prompt: str) -> ModelResponse:
            prior: Any = SimpleNamespace(version_id=version, entity_id=pilot.entity_id)
            with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn, conn.transaction():
                _append(pilot, prior, conn)
            return super().generate(prompt)

    before = ns.all_counts(pilot)["report_versions"]
    with pytest.raises(ns.code().flow.NarrateRefusedError, match="head"):
        ns.narrate(pilot, version, Racing(ns.draft(held)))
    assert ns.all_counts(pilot)["report_versions"] == before + 1
