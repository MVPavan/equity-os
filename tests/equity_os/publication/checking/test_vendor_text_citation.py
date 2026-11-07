"""VENDOR-1 Phase 2 Task 4: a vendor text span is citable only when bound to the report's issuer,
registered by the source cutoff S, extracted and bound by the knowledge cutoff K, present in the
retained bytes and numeral-free (readings 3, 4, 5 and 7). Vendor text is never a number source.

The world is Apar's retained concall summary and one retained announcements feed page, copied
into a test store and extracted by a scripted model. Spans are chosen by offsets at run time;
no vendor text is written here or printed.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import Mock

import psycopg
import pytest
from evidence_support import ingest, policy
from ledger_support import Ledger, ledger
from pg_evidence_schema_support import _insert, runtime, seeded
from retention_support import record_of
from test_vendor_citation import (
    REVENUE,
    UNCHECKED,
    WITNESS_PAIR,
    _resolve,
    approved,
    dictionary,
    mapping_set,
)
from test_vendor_surface_claims import (
    RETAINED,
    SCREENER,
    registered_addresses,
    retained_bodies,
    retained_texts,
)
from test_vendor_values_store import outcome

from equity_os.contracts.measurement.evidence import CaptureReference
from equity_os.contracts.publication.ledger import (
    Citation,
    CitationKind,
    ClaimState,
    DecisionKind,
    ReportKind,
    ReportSection,
    RunMode,
    SubjectKind,
    VersionState,
    VersionStatus,
)
from equity_os.contracts.sourcing.source_catalog import BUILTIN_SOURCES
from equity_os.extraction.model.vendor_surface_claims import extract_text
from equity_os.extraction.model.vendor_surface_model import ModelReply, ModelSettings
from equity_os.extraction.surfaces import vendor_text_readers
from equity_os.extraction.surfaces.vendor_text_readers import ReaderText
from equity_os.extraction.vendors.screener.screener_session_page import (
    parse_document,
    read_identity,
)
from equity_os.publication.approval import lifecycle
from equity_os.publication.approval.lifecycle import DecisionRefusedError
from equity_os.publication.checking.citations import resolve_location
from equity_os.publication.checking.claim_check import check_claim
from equity_os.publication.checking.numeral_scan import has_numeral
from equity_os.publication.drafting.display import content_hash
from equity_os.publication.drafting.vendor_summary import VENDOR_SUMMARY, vendor_summary_section
from equity_os.sourcing.surfaces.vendor_surface_fetch import Fetched, Site
from equity_os.storage.database.settings import PgRole
from equity_os.storage.raw_files.snapshot_store import SnapshotStore
from equity_os.storage.records import store as ledger_store
from equity_os.storage.records.repository import EvidenceRepository
from equity_os.storage.records.vendor_values_store import OutcomeStatus, VendorValuesStore, register

__all__ = [
    "approved",
    "dictionary",
    "ingest",
    "ledger",
    "mapping_set",
    "policy",
    "runtime",
    "seeded",
]

pytestmark = [pytest.mark.pg, pytest.mark.retained]

SOURCE = "screener-subscriber"
TICK = timedelta(microseconds=1)
SETTINGS = ModelSettings(
    model_id="fake",
    base_url="https://unused.example",
    key_file="unused",
    prompt_version="spans.v1",
    dictionary_version="v3",
)
SYNTHETIC_FEED = (
    '<div class="announcement-item"><a href="/doc">Plant opens</a></div>'
    '<div class="announcement-item"><a href="/company/APARINDS/">A</a>'
    '<a href="/company/OTHERCO/">B</a><a href="/doc">Order win</a></div>'
)
BOUND = "SELECT recorded_at FROM eqos.vendor_basis_bindings WHERE entity_id = %s"
EXTRACTED = "SELECT min(recorded_at) FROM eqos.vendor_outcomes WHERE parser_version = %s"
BINDING = (
    "INSERT INTO eqos.vendor_basis_bindings "
    "(entity_id, basis, screener_company_id, warehouse_id, capture_ref_id, evidence) "
    "VALUES (%s, %s, %s, 1, %s, 'FIRST_CAPTURE')"
)
LATE_CLAIM = (
    "INSERT INTO eqos.vendor_text_claims (capture_ref_id, surface, kind, span_start, span_end, "
    "text, model_id, prompt_version, epistemic_class) SELECT capture_ref_id, surface, 'CLAIM', "
    "%s, %s, %s, model_id, prompt_version, epistemic_class FROM eqos.vendor_text_claims "
    "WHERE capture_ref_id = %s LIMIT 1"
)
VERSION_ROWS = (
    "SELECT (SELECT count(*) FROM eqos.report_versions), "
    "(SELECT count(*) FROM eqos.import_sources), (SELECT count(*) FROM eqos.version_source_cutoffs)"
)


def windows(text: str, lo: int, hi: int) -> Iterator[tuple[int, int]]:
    """Word-aligned windows of one to three tokens inside ``[lo, hi)``."""
    tokens = [m.span() for m in re.finditer(r"\S+", text) if lo <= m.start() and m.end() <= hi]
    for size in (3, 2, 1):
        for first in range(len(tokens) - size + 1):
            yield tokens[first][0], tokens[first + size - 1][1]


def free(text: str, lo: int, hi: int, after: int = 0) -> tuple[int, int]:
    """The first numeral-free, marker-free window in ``[lo, hi)`` starting at or after ``after``."""
    return next(
        (s, e)
        for s, e in windows(text, lo, hi)
        if s >= after
        and not has_numeral(text[s:e])
        and "{{" not in text[s:e]
        and "}}" not in text[s:e]
    )


class World:
    """Apar (the ledger's entity) and a second issuer bound to a feed item's slug."""

    def __init__(self, ledger: Ledger, tmp: Any, pg_db: Any) -> None:
        self.ledger, self.pg_db = ledger, pg_db
        self.pool = ledger.pools[PgRole.RUNTIME]
        self.store = SnapshotStore(tmp / "store")
        retained = SnapshotStore(RETAINED.parent)
        urls = registered_addresses()
        refs: dict[str, CaptureReference] = {}

        def copy(surface: str, key: str, capture: str, url: str) -> CaptureReference:
            record = retained.get_capture(SOURCE, f"vs.{surface}", key, capture)
            self.store.put_capture(record, retained.read_body(record))
            return register(self.pool, Fetched(record=record, url=url, location=None))

        *_, (page_key, page_capture, page) = retained_bodies("company-page")
        apar_id, _ = read_identity(parse_document(page.decode()))
        refs["page"] = copy("company-page", page_key, page_capture, urls[page_key])
        key, capture, self.concall = next(
            (k, c, r) for k, c, r in retained_texts("concall-summary") if r.text
        )
        refs["concall"] = copy("concall-summary", key, capture, urls[key])
        key, capture, self.feed, self.pair = self._feed_pair()
        refs["feed"] = copy("announcements-feed", key, capture, SCREENER + "/announcements/")
        synthetic = SYNTHETIC_FEED.encode()
        record = record_of(synthetic, SOURCE, "vs.announcements-feed")
        self.store.put_capture(record, synthetic)
        fetched = Fetched(record=record, url=SCREENER + "/announcements/", location=None)
        refs["synthetic"] = register(self.pool, fetched)
        other = self.feed.items[self.pair + 1].company.value
        record = record_of(b"other", SOURCE, "vs.company-page")
        fetched = Fetched(record=record, url=f"{SCREENER}/company/{other}/", location=None)
        refs["other_page"] = register(self.pool, fetched)
        self.refs = refs
        with self.pool.connection() as conn:
            self.other = entity(conn, "OTHER", ledger.entity_id)
            page_id = refs["page"].capture_ref_id
            conn.execute(BINDING, (ledger.entity_id, "CONSOLIDATED", apar_id, page_id))
        self.spans = self._spans()
        self._extract()
        with self.pool.connection() as conn:  # the second issuer's binding comes after extraction
            other_id = refs["other_page"].capture_ref_id
            conn.execute(BINDING, (self.other, "CONSOLIDATED", 999_999_999, other_id))
        self.now = self.clock()

    def _feed_pair(self) -> tuple[str, str, ReaderText, int]:
        """A retained feed page with an Apar item followed by another issuer's item."""
        for key, capture, read in retained_texts("announcements-feed"):
            for at, (item, following) in enumerate(zip(read.items, read.items[1:], strict=False)):
                if item.company.value == "APARINDS" != following.company.value:
                    try:
                        free(read.text, following.start, following.end, after=following.start + 1)
                    except StopIteration:
                        continue
                    return key, capture, read, at
        raise AssertionError("no retained feed page pairs an Apar item with another issuer's")

    def _spans(self) -> dict[str, tuple[str, int, int]]:
        """The scripted selections by role: capture, start and end."""
        text = self.concall.text
        claim = free(text, 0, len(text))
        name = free(text, 0, len(text), after=claim[1] + 1)
        digit = next(
            m.span() for m in re.finditer(r"\S+", text[name[1] :]) if has_numeral(m.group())
        )
        apar, other = self.feed.items[self.pair], self.feed.items[self.pair + 1]
        tail = [m.start() for m in re.finditer(r"\S+", self.feed.text[: apar.end])][-1]
        head = re.compile(r"\S+").search(self.feed.text, other.start)
        assert head is not None
        return {
            "claim": ("concall", *claim),
            "name": ("concall", *name),
            "digit": ("concall", digit[0] + name[1], digit[1] + name[1]),
            "other_item": ("feed", *free(self.feed.text, other.start, other.end, head.end() + 1)),
            "crossing": ("feed", tail, head.end()),
            "no_link": ("synthetic", 0, 11),
            "two_links": ("synthetic", 12, 21),
        }

    def _extract(self) -> None:
        """Run ``extract_text`` with a model that returns the scripted offsets."""
        replies: dict[str, list[dict[str, Any]]] = {}
        texts = {"concall": self.concall.text, "feed": self.feed.text}
        texts["synthetic"] = "Plant opens Order win"
        for role, (where, start, end) in self.spans.items():
            kind = "NAME" if role == "name" else "CLAIM"
            replies.setdefault(texts[where], []).append({"kind": kind, "start": start, "end": end})

        def complete(system: str, source: str) -> ModelReply:
            return ModelReply(
                text=json.dumps(replies.get(source, [])), input_tokens=1, output_tokens=1
            )

        values = VendorValuesStore(self.pool)
        for where, surface in (
            ("concall", "concall-summary"),
            ("feed", "announcements-feed"),
            ("synthetic", "announcements-feed"),
        ):
            values.record(
                self.refs[where],
                outcome(version="kept.v1", surface=surface, values=()),
                row_count=0,
            )
        model = Mock(model_id="fake", complete=Mock(side_effect=complete))
        assert extract_text(self.pool, self.store, model, SETTINGS) == 3

    def clock(self) -> datetime:
        """The store clock."""
        return EvidenceRepository(self.pool).store_clock()

    def at(self, query: str, *args: Any) -> datetime:
        """One stored time."""
        with self.pool.connection() as conn:
            row = conn.execute(query, args).fetchone()
        assert row is not None
        value: datetime = row[0]
        return value

    def anchor(self, role: str, shift: int = 0) -> tuple[str, str]:
        """The location marker parts of a scripted span, its offsets moved by ``shift``."""
        where, start, end = self.spans[role]
        ref = self.refs[where]
        return str(ref.capture_ref_id), f"vt:{start + shift}-{end + shift}:{ref.blob_sha256}"

    def resolves(
        self,
        role: str,
        *,
        entity: int | None = None,
        source_cutoff: datetime | None = None,
        cutoff: datetime | None = None,
        anchor: str | None = None,
    ) -> bool:
        """Whether the span's location marker resolves for ``entity`` (Apar) at S and K (now)."""
        capture, own = self.anchor(role)
        with self.pool.connection() as conn, conn.cursor() as cursor:
            return resolve_location(
                cursor,
                capture,
                anchor or own,
                entity_id=entity or self.ledger.entity_id,
                cutoff=cutoff or self.now,
                catalog=BUILTIN_SOURCES,
                snapshots=self.store,
                source_cutoff=source_cutoff or self.now,
            )


def entity(conn: psycopg.Connection[Any], key: str, like: int) -> int:
    """A new reporting entity on ``like``'s evidence input."""
    row = conn.execute(
        "SELECT evidence_input_id FROM eqos.reporting_entities WHERE id = %s", (like,)
    ).fetchone()
    assert row is not None
    fields = {"entity_key": key, "market": "IN", "display_name": key, "evidence_input_id": row[0]}
    return _insert(conn, "reporting_entities", fields)


@pytest.fixture
def world(ledger: Ledger, tmp_path: Any, pg_db: Any) -> World:
    """The extracted vendor world."""
    return World(ledger, tmp_path, pg_db)


def test_only_a_span_bound_to_the_issuers_own_item_resolves(world: World) -> None:
    other = world.other
    assert world.resolves("claim")
    assert world.resolves("other_item", entity=other)
    assert not world.resolves("other_item")  # another issuer's feed item
    assert not world.resolves("crossing")  # starts in Apar's item, ends in the next
    assert not world.resolves("crossing", entity=other)
    assert not world.resolves("no_link") and not world.resolves("two_links")
    assert not world.resolves("digit")  # a numeral is never shown
    assert not world.resolves("name")  # only CLAIM rows
    _, anchor = world.anchor("claim")
    sha = anchor.rsplit(":", 1)[1]
    for moved in (
        world.anchor("claim", shift=1)[1],
        world.anchor("claim", shift=-1)[1],
        f"vt:0-{len(world.concall.text) + 1}:{sha}",
        anchor.replace(sha, "0" * 64),
    ):
        assert not world.resolves("claim", anchor=moved)
    # The issuer's own identity evidence: missing for a fresh entity, ambiguous when conflicting.
    with world.pool.connection() as conn:
        bare = entity(conn, "BARE", other)
    assert not world.resolves("claim", entity=bare)
    with world.pool.connection() as conn:
        page_id = world.refs["page"].capture_ref_id
        conn.execute(BINDING, (world.ledger.entity_id, "STANDALONE", 1, page_id))
    now = world.clock()
    assert not world.resolves("claim", cutoff=now, source_cutoff=now)  # conflicting ids


def test_two_clocks_select_what_was_registered_and_known(world: World) -> None:
    registered = world.refs["concall"].registered_at
    apar_bound = world.at(BOUND, world.ledger.entity_id)
    extracted = world.at(EXTRACTED, "claims:fake:spans.v3")
    other_bound = world.at(BOUND, world.other)
    assert registered < apar_bound < extracted < other_bound
    assert not world.resolves("claim", source_cutoff=registered - TICK)  # S < registration <= K
    assert world.resolves("claim", source_cutoff=registered)
    assert not world.resolves("claim", cutoff=extracted - TICK, source_cutoff=registered)
    assert world.resolves("claim", cutoff=other_bound - TICK)
    assert not world.resolves("other_item", entity=world.other, cutoff=other_bound - TICK)


def test_newer_empty_extraction_licence_end_and_moved_reader_hide_spans(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = world.clock()
    VendorValuesStore(world.pool).record(
        world.refs["concall"],
        outcome(
            version="claims:fake:spans.v9",
            surface="concall-summary",
            values=(),
            status=OutcomeStatus.EMPTY,
        ),
        row_count=0,
    )
    now = world.clock()
    assert not world.resolves("claim", cutoff=now, source_cutoff=now)
    assert world.resolves("claim", cutoff=before, source_cutoff=before)  # never revived later

    def moved(body: bytes, url: str) -> ReaderText:
        read = vendor_text_readers.concall_summary(body, url)
        return ReaderText(text=" " + read.text, items=read.items)

    monkeypatch.setitem(vendor_text_readers.READERS, (Site.SCREENER, "concall-summary"), moved)
    assert not world.resolves("claim", cutoff=before, source_cutoff=before)
    monkeypatch.undo()
    capture = world.refs["concall"].capture_ref_id
    with world.pg_db.migrator_connection() as migrator, migrator.transaction():
        migrator.execute("SELECT set_config('eqos.tombstone', %s, true)", (str(capture),))
        migrator.execute(
            "UPDATE eqos.vendor_text_claims SET text = NULL WHERE capture_ref_id = %s", (capture,)
        )
    assert not world.resolves("claim", cutoff=before, source_cutoff=before)
    assert world.resolves("other_item", entity=world.other)
    with world.ledger.pools[PgRole.OWNER].connection() as conn:
        conn.execute("INSERT INTO eqos.licence_ends (source_id) VALUES (%s)", (SOURCE,))
    assert not world.resolves("other_item", entity=world.other)


def _section(world: World, role: str) -> ReportSection:
    """An ordinary section citing one scripted span by its location marker (the vendor block
    itself must equal its rendering, which a bare anchor is not)."""
    capture, anchor = world.anchor(role)
    body = f"{{{{e:inferred}}}} {{{{s:{capture}|{anchor}}}}}"
    return ReportSection(ordinal=0, section_key="notes", body=body)


def test_the_versions_own_source_cutoff_governs_checking_and_sealing(world: World) -> None:
    ledger, pools = world.ledger, world.ledger.pools
    registered = world.refs["concall"].registered_at
    section = _section(world, "claim")
    fields = {
        "knowledge_cutoff": world.now,
        "sections": (section,),
        "claims": (),
        "content_hash": content_hash((section,), ()),
    }
    sources = {"catalog": BUILTIN_SOURCES, "snapshots": world.store}
    report = ledger.report()
    first = ledger.draft(report, source_cutoff=registered, **fields)
    assert not lifecycle.validate(
        pools[PgRole.RUNTIME], first, mode=RunMode.AS_KNOWN, **sources
    ).version_states
    lifecycle.submit(pools[PgRole.RUNTIME], first, **sources)
    ledger.decide(PgRole.OWNER, first, DecisionKind.REJECT)
    # A fresh same-period successor with an earlier S2 stores S2 and is checked against it.
    second = ledger.draft(report, first, source_cutoff=registered - TICK, **fields)
    with pools[PgRole.RUNTIME].connection() as conn, conn.cursor() as cursor:
        stored = ledger_store.read_version(cursor, second)
    assert stored.source_cutoff == registered - TICK
    checked = lifecycle.validate(pools[PgRole.RUNTIME], second, mode=RunMode.AS_KNOWN, **sources)
    assert checked.version_states == (VersionState.UNCITED_PROSE,)
    with pytest.raises(DecisionRefusedError, match="UNCITED_PROSE"):
        lifecycle.submit(pools[PgRole.RUNTIME], second, **sources)
    # Narration copies the stored draft: it keeps the predecessor's S, never widens it.
    with pools[PgRole.RUNTIME].connection() as conn, conn.cursor() as cursor:
        narrated = ledger_store.create_version(
            cursor, stored.model_copy(update={"predecessor_id": second})
        )
        inherited = ledger_store.create_version(
            cursor, ledger.version_draft(report, narrated, knowledge_cutoff=world.now)
        )
        none = ledger_store.create_version(cursor, ledger.version_draft(ledger.report(), **fields))
        cutoffs = [
            ledger_store.read_version(cursor, v).source_cutoff for v in (narrated, inherited, none)
        ]
    assert cutoffs == [registered - TICK, registered - TICK, None]
    checked = lifecycle.validate(pools[PgRole.RUNTIME], none, mode=RunMode.AS_KNOWN, **sources)
    assert checked.version_states == (VersionState.UNCITED_PROSE,)  # no row resolves nothing


def test_the_cutoff_row_is_written_once_with_its_version(world: World) -> None:
    ledger = world.ledger
    late = ledger.draft(ledger.report(), knowledge_cutoff=world.now)
    sealed = ledger.imported(ledger.report(), knowledge_cutoff=world.now, source_cutoff=world.now)
    for version in (late, sealed):
        with pytest.raises(psycopg.errors.CheckViolation):
            with ledger.pools[PgRole.RUNTIME].connection() as conn:
                conn.execute(
                    "INSERT INTO eqos.version_source_cutoffs VALUES (%s, %s)", (version, world.now)
                )
    for statement in (
        "UPDATE eqos.version_source_cutoffs SET source_cutoff = source_cutoff",
        "DELETE FROM eqos.version_source_cutoffs",
        "TRUNCATE eqos.version_source_cutoffs",
    ):
        with pytest.raises(psycopg.errors.RaiseException):
            with world.pg_db.migrator_connection() as migrator:
                migrator.execute(statement)
    count = "SELECT count(*) FROM eqos.report_versions"
    with ledger.pools[PgRole.RUNTIME].connection() as conn:
        (before,) = conn.execute(count).fetchone()
    with pytest.raises(psycopg.errors.CheckViolation):  # S > K, refused atomically
        ledger.draft(ledger.report(), knowledge_cutoff=world.now, source_cutoff=world.now + TICK)
    with ledger.pools[PgRole.RUNTIME].connection() as conn:
        assert conn.execute(count).fetchone() == (before,)


def test_a_numeric_claim_citing_a_span_is_unresolved_and_passes_with_a_fact_id(
    approved: tuple[Any, int, int],
) -> None:
    """Vendor text is never a number source: the revenue claim re-cited as a quote of Apar's
    concall summary is unresolved; citing its admitted fact it matches with Task 9's label, and
    retains both witnesses."""
    pilot, run_id, version_id = approved
    draft = pilot.version(version_id)
    revenue = next(c for c in draft.claims if c.claim_key == REVENUE)
    urls = registered_addresses()
    key, capture, read = next((k, c, r) for k, c, r in retained_texts("concall-summary") if r.text)
    record = SnapshotStore(RETAINED.parent).get_capture(SOURCE, "vs.concall-summary", key, capture)
    with pilot.pg_db.runtime_pool() as pool:
        ref = register(pool, Fetched(record=record, url=urls[key], location=None))
    start, end = free(read.text, 0, len(read.text))
    quoted = revenue.model_copy(
        update={
            "citation": Citation(
                kind=CitationKind.SOURCE_QUOTE,
                capture_ref_id=ref.capture_ref_id,
                anchor=f"vt:{start}-{end}:{ref.blob_sha256}",
                quote=read.text[start:end],
                source_sha256=ref.blob_sha256,
            )
        }
    )
    check = {"mode": RunMode.AS_KNOWN, "cutoff": draft.knowledge_cutoff, "imported": False}
    assert check_claim(quoted, _resolve(pilot, version_id, quoted), **check) is (
        ClaimState.UNRESOLVED
    )
    resolved = _resolve(pilot, version_id, revenue)
    assert resolved is not None and resolved.admission_label is UNCHECKED
    assert check_claim(revenue, resolved, **check) is ClaimState.MATCH
    witnesses = {row[0] for row in pilot.query(WITNESS_PAIR, version_id, REVENUE, run_id)}
    assert len(witnesses) == 2


def test_a_claim_row_recorded_after_k_is_unknown_though_its_extraction_is_known(
    world: World,
) -> None:
    """Reading 7's third clock: a ``CLAIM`` row appended after K to an extraction completed by K
    is not citable at K; the same row is at a later K."""
    known = world.clock()
    _, start, end = world.spans["name"]  # numeral-free; so far held only as a NAME row
    capture = world.refs["concall"].capture_ref_id
    with world.pool.connection() as conn:
        conn.execute(LATE_CLAIM, (start, end, world.concall.text[start:end], capture))
    now = world.clock()
    assert not world.resolves("name", cutoff=known, source_cutoff=known)
    assert world.resolves("name", cutoff=now, source_cutoff=now)


def test_an_imported_successor_inheriting_a_later_source_cutoff_is_refused_whole(
    world: World,
) -> None:
    """An imported successor stores no S of its own and inherits its predecessor's; when that S
    is after its own K the import is refused with no version, import source or cutoff row."""
    ledger, now = world.ledger, world.now
    report = ledger.report()
    head = ledger.imported(report, approve=True, knowledge_cutoff=now, source_cutoff=now)
    with world.pool.connection() as conn:
        before = conn.execute(VERSION_ROWS).fetchone()
    with pytest.raises(psycopg.errors.CheckViolation):
        ledger.imported(report, head, approve=True, knowledge_cutoff=now - TICK)
    with world.pool.connection() as conn:
        assert conn.execute(VERSION_ROWS).fetchone() == before
    successor = ledger.imported(report, head, approve=True, knowledge_cutoff=now)
    with world.pool.connection() as conn, conn.cursor() as cursor:
        assert ledger_store.read_version(cursor, successor).source_cutoff == now  # inherited


def test_another_issuers_report_shows_no_vendor_section_and_seals(world: World) -> None:
    """A third issuer bound to its own company page has no eligible text: Apar's held concall
    summary never becomes its vendor block. Its report, composed as the run draft composes one,
    has no vendor section, checks and seals; the same report showing Apar's block cannot."""
    ledger, pools = world.ledger, world.ledger.pools
    record = record_of(b"third", SOURCE, "vs.company-page")
    fetched = Fetched(record=record, url=f"{SCREENER}/company/THIRDCO/", location=None)
    page = register(world.pool, fetched)
    with world.pool.connection() as conn:
        third = entity(conn, "THIRD", ledger.entity_id)
        conn.execute(BINDING, (third, "CONSOLIDATED", 999_999_998, page.capture_ref_id))
    ledger.cover(third)
    now = world.clock()
    with world.pool.connection() as conn, conn.cursor() as cursor:
        blocks = {
            issuer: vendor_summary_section(
                cursor,
                entity_id=issuer,
                source_cutoff=now,
                knowledge_cutoff=now,
                snapshots=world.store,
            )
            for issuer in (ledger.entity_id, third)
        }
        borrowed, own = (
            ledger_store.create_report(
                cursor, entity_id=third, period=period, kind=ReportKind.EARNINGS_UPDATE
            )
            for period in ("FY27_Q1", "FY27_Q2")
        )
    apar = blocks[ledger.entity_id]
    absent = blocks[third] is None
    assert absent, "the third issuer has a vendor block"  # never printed
    assert apar is not None
    key, body = apar
    assert key == VENDOR_SUMMARY
    sources = {"catalog": BUILTIN_SOURCES, "snapshots": world.store}
    runtime = pools[PgRole.RUNTIME]
    fields = {"knowledge_cutoff": now, "source_cutoff": now, "claims": ()}
    heading = ReportSection(ordinal=0, section_key="heading", body="# FY27 update\n\n")
    shown = (heading, ReportSection(ordinal=1, section_key=key, body=body))
    shown_id = ledger.draft(
        borrowed, sections=shown, content_hash=content_hash(shown, ()), **fields
    )
    checked = lifecycle.validate(runtime, shown_id, mode=RunMode.AS_KNOWN, **sources)
    assert checked.version_states == (VersionState.UNCITED_PROSE,)
    with pytest.raises(DecisionRefusedError, match="UNCITED_PROSE"):
        lifecycle.submit(runtime, shown_id, **sources)
    own_id = ledger.draft(
        own, sections=(heading,), content_hash=content_hash((heading,), ()), **fields
    )
    lifecycle.submit(runtime, own_id, **sources)
    lifecycle.decide(
        pools[PgRole.OWNER],
        subject_kind=SubjectKind.REPORT_VERSION,
        subject_id=own_id,
        kind=DecisionKind.APPROVE,
        ruling="TEST: seal the other issuer's report",
        **sources,
    )
    with runtime.connection() as conn, conn.cursor() as cursor:
        assert lifecycle.version_status(cursor, own_id) is VersionStatus.APPROVED
        assert ledger_store.read_version(cursor, own_id).source_cutoff == now
