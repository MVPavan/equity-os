"""D9 Task 3: the citation-graph holds and the dry-run (plan D9 R4, R5, cases H1-H7).

Why: an original that anything durable cites must outlive every window, and nothing else may.
Each R4 edge is checked both ways in an isolated chain: the capture is eligible without the
edge and held with it, so the hold query can neither miss an edge nor hold by accident.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from datetime import date

import psycopg
import pytest
import yaml
from ledger_support import SECTION, claim, ledger
from memory_support import Memory, memory
from pg_evidence_schema_support import (
    _insert,
    _insert_ignoring_conflict,
    _interpretation,
    _occurrence,
    _trace,
    runtime,
    seeded,
)
from pg_support import PgTestDatabase
from retention_support import (
    CONFIG,
    dispose,
    facts_of,
    later,
    open_item,
    package,
    register,
    retention_cli,
    set_store_clock,
    verdict,
    verify,
)

from fundamentals.contracts.ledger import Citation, CitationKind, ReportSection
from fundamentals.contracts.memory import MemoryKind, SupportDraft, SupportTarget
from fundamentals.contracts.retention import (
    Eligibility,
    EligibilityKind,
    EligibleReason,
    HoldRoot,
)
from fundamentals.pg.settings import PgRole
from fundamentals.retention.eligibility import eligible_blobs
from fundamentals.retention.holds import HOLDS_FILE, capture_facts, pinned_roots

pytestmark = pytest.mark.pg

__all__ = ["ledger", "memory", "runtime", "seeded"]

ELIGIBLE, HELD = EligibilityKind.ELIGIBLE, EligibilityKind.HELD
IDENTITY = ("nse", "EQUITY_L")  # a non-vendor class aged from registration: every root holds
XBRL = ("nse-indas-xbrl-consolidated", "NSE_XBRL_INSTANCE")
# The LAURUSLABS fixture capture of config/mappings/xbrl/v3/in_bse_fin.yaml:93.
LAURUSLABS = "2d50d29a467b9035f8124f7a9576346b7d36888e9895befc3363e3c5d227cfa6"
FIXTURES_DIR = "tests/fundamentals/fixtures/data_foundation"
OPAQUE_MANIFEST = "stage4_manifest.yaml"


class World:
    """A seeded ledger with memory, written through autocommit runtime and owner connections."""

    def __init__(self, memory: Memory, runtime: psycopg.Connection, owner: psycopg.Connection):
        self.memory, self.ledger = memory, memory.ledger
        self.rt, self.owner = runtime, owner
        self.entity = self.ledger.entity_id
        self.run = self.one("SELECT id FROM eqos.runs ORDER BY id LIMIT 1")
        self.result = self.one("SELECT id FROM eqos.results ORDER BY id LIMIT 1")
        self.pins: dict[HoldRoot, frozenset[str]] = {}
        self._handles = 100

    def one(self, query: str, *params: int) -> int:
        row = self.rt.execute(query, params).fetchone()
        assert row is not None
        return int(row[0])

    def capture(self, kind: tuple[str, str] = IDENTITY, **options: str) -> int:
        return register(self.rt, *kind, **options)

    def occurrence(self, capture: int) -> int:
        return _insert(self.rt, "occurrences", _occurrence(capture, uuid.uuid4().hex))

    def interpretation(self, capture: int, *, constructed: bool = False) -> int:
        occurrence = None if constructed else self.occurrence(capture)
        row = _interpretation(self.entity, capture, occurrence, input_digest=uuid.uuid4().hex)
        if constructed:
            row |= {
                "origin": "CONSTRUCTED",
                "construction_rule_id": "rule",
                "mapping_entry_id": None,
            }
        return _insert(self.rt, "interpretations", row)

    def trace(self) -> int:
        return _insert(self.rt, "calculation_traces", _trace(uuid.uuid4().hex * 2))

    def operand(self, trace: int, **reference: int) -> int:
        row = {"calculation_trace_id": trace, "ordinal": 0, "operand_name": "x"}
        row |= {
            "key_digest": "k",
            "temporal_role": "DURATION",
            "scoped_tier": "EQUIVALENCE_UNPROVEN",
        }
        row |= {"selection_source": "PACKAGE_AS_REPORTED", "source_state": "VALUE"}
        return _insert(self.rt, "calculation_trace_operands", row | reference)

    def draft(
        self, *citations: Citation, body: str = SECTION.body, predecessor: int | None = None
    ) -> int:
        """A runtime draft citing each of ``citations`` once (none: the fixture claim)."""
        claims = tuple(
            claim(0, f"c.{n}").model_copy(update=_claim_update(citation))
            for n, citation in enumerate(citations)
        ) or (claim(self.ledger.trace_id),)
        sections = (ReportSection(ordinal=0, section_key=SECTION.section_key, body=body),)
        report = self.ledger.report() if predecessor is None else self.report_of(predecessor)
        return self.ledger.draft(report, predecessor, claims=claims, sections=sections)

    def report_of(self, version: int) -> int:
        return self.one("SELECT report_id FROM eqos.report_versions WHERE id = %s", version)

    def fact(self) -> tuple[str, int]:
        """SEED: a legacy fact-store row; returns its origin key."""
        self._handles += 1
        handle = self._handles
        row = {"target_store": "sqlite-seed", "handle": handle, "origin": "sqlite-seed"}
        row |= {"origin_id": handle, "content_identity": f"c{handle}", "value_hash": "v"}
        row |= {"revision_family": "f", "revision_ordinal": 1, "canonical_status": "canonical"}
        row |= {"source_id": "s", "file_sha256": "a" * 64, "anchor": "{}"}
        row |= {"valid_time_start": "2025-07-01", "knowledge_time": "t", "first_seen_time": "t"}
        row |= {"fact_json": "{}", "created_at": "t"}
        _insert_ignoring_conflict(self.rt, "fact_rows", row)
        return "sqlite-seed", handle

    def bind(self, fact: tuple[str, int], capture: int) -> None:
        self.rt.execute(
            "INSERT INTO eqos.legacy_evidence_bindings (target_store, row_handle, capture_ref_id,"
            " file_sha256, anchor) VALUES (%s, %s, %s, %s, '{}')",
            (*fact, capture, "a" * 64),
        )

    def evidence(self, capture: int) -> int:
        row = {
            "kind": "ISSUER_IDENTITY",
            "label": "fixture",
            "content_sha256": uuid.uuid4().hex * 2,
        }
        evidence = _insert(self.rt, "evidence_inputs", row)
        _insert(
            self.rt,
            "evidence_input_captures",
            {"evidence_input_id": evidence} | {"capture_ref_id": capture},
        )
        return evidence

    def item(self, *, disposed: bool = False, **evidence: int) -> int:
        item = open_item(self.rt, self.run, **evidence)
        if disposed:
            dispose(self.owner, item)
        return item

    def support(self, capture: int) -> None:
        target = SupportDraft(target=SupportTarget.CAPTURE, target_id=capture)
        self.memory.stage(kind=MemoryKind.SOURCE_QUIRK, supports=(target,))

    def identity_event(self, capture: int) -> None:
        row = {"kind": "DELISTING", "effective_date": date(2026, 1, 1)}
        _insert(self.rt, "identity_events", row | {"evidence_input_id": self.evidence(capture)})

    def onboarding(self, capture: int) -> None:
        row = {"identifier": "FIXT", "identifier_namespace": "NSE_SYMBOL", "outcome": "UNSUPPORTED"}
        row |= {"reason": "fixture", "evidence_input_id": self.evidence(capture)}
        _insert(self.rt, "onboarding_records", row)

    def entity_of_its_own(self) -> int:
        """SEED: a reporting entity nobody has added to the watchlist."""
        evidence = self.evidence(self.capture())
        row = {"entity_key": uuid.uuid4().hex, "market": "IN", "display_name": "Unwatched"}
        return _insert(self.rt, "reporting_entities", row | {"evidence_input_id": evidence})


def _claim_update(citation: Citation) -> dict[str, object]:
    """A claim's fields for ``citation`` (a quote carries no measurement key)."""
    quote = citation.kind is CitationKind.SOURCE_QUOTE
    return {"citation": citation} | ({"measurement_key": None} if quote else {})


def _quote(capture: int) -> Citation:
    return Citation(kind=CitationKind.SOURCE_QUOTE, capture_ref_id=capture, anchor="p1", quote="12")


# An edge fixture: the capture, the write adding the edge, the root it adds and roots it had.
Edge = tuple[int, Callable[[], object], HoldRoot, frozenset[HoldRoot]]
NONE: frozenset[HoldRoot] = frozenset()
VERSION, QUEUE, OPEN = HoldRoot.REPORT_VERSION, HoldRoot.QUEUE_ITEM, HoldRoot.OPEN_QUEUE_ITEM


def _figure(interpretation: int, w: World) -> Citation:
    return Citation(kind=CitationKind.FIGURE, interpretation_id=interpretation, run_id=w.run)


def quote_claim(w: World) -> Edge:
    c = w.capture()
    return c, lambda: w.draft(_quote(c)), VERSION, NONE


def interpretation_claim(w: World) -> Edge:
    c = w.capture()
    i = w.interpretation(c)
    return c, lambda: w.draft(_figure(i, w)), VERSION, NONE


def recursive_trace_operand(w: World) -> Edge:
    c = w.capture()
    inner, outer = w.trace(), w.trace()
    w.operand(inner, interpretation_id=w.interpretation(c))
    w.draft(Citation(kind=CitationKind.CALCULATION, calculation_trace_id=outer))
    return c, lambda: w.operand(outer, operand_trace_id=inner), VERSION, NONE


def imported_fact_binding(w: World) -> Edge:
    c, fact = w.capture(), w.fact()
    w.bind(fact, c)
    cite = Citation(kind=CitationKind.FIGURE, fact_origin=fact[0], fact_origin_id=fact[1])
    return c, lambda: w.draft(cite), VERSION, frozenset({HoldRoot.LEGACY_BINDING})


def native_fact_admission(w: World) -> Edge:
    c, fact = w.capture(), w.fact()
    w.draft(Citation(kind=CitationKind.FIGURE, fact_origin=fact[0], fact_origin_id=fact[1]))
    i = w.interpretation(c)
    row = {"store_id": fact[0], "row_handle": fact[1], "fact_origin": fact[0]}
    row |= {"fact_origin_id": fact[1], "run_id": w.run, "result_id": w.result}
    row |= {
        "interpretation_id": i,
        "occurrence_id": w.one("SELECT occurrence_id FROM eqos.interpretations WHERE id = %s", i),
    }
    row |= {"overlay_position": later(), "bridge_version": "admission-bridge/1"}
    return c, lambda: _insert(w.rt, "fact_admissions", row), VERSION, NONE


def comparison_pair_value(w: World) -> Edge:
    c = w.capture()
    side = {"result_id": w.result, "source_role": "INDEPENDENT_VENDOR", "surface": "x"}
    side |= {"source_id": uuid.uuid4().hex, "representation": "HTML"}
    value = {"source_state": "VALUE", "interpretation_id": w.interpretation(c)}
    left = _insert(w.rt, "result_source_values", side | value)
    right = _insert(
        w.rt, "result_source_values", side | {"source_state": "NO_VALUE", "representation": "JSON"}
    )
    pair = {"result_id": w.result, "pair_kind": "EXTRACTION", "outcome": "NOT_COMPARABLE"}
    pair |= {"left_value_id": left, "right_value_id": right}
    cite = Citation(
        kind=CitationKind.COMPARISON,
        run_id=w.run,
        pair_outcome_id=_insert(w.rt, "pair_outcomes", pair),
    )
    return c, lambda: w.draft(cite), VERSION, NONE


def location_marker(w: World) -> Edge:
    c = w.capture()
    return c, lambda: w.draft(body=f"{SECTION.body} {{{{s:{c}|p1}}}}"), VERSION, NONE


def _cited_on_another_capture(w: World, *, constructed: bool = False) -> int:
    """An interpretation of another capture, cited by a draft claim."""
    cited = w.interpretation(w.capture(), constructed=constructed)
    w.draft(_figure(cited, w))
    return cited


def condition_evidence(w: World) -> Edge:
    c = w.capture()
    cited, evidence = _cited_on_another_capture(w), w.interpretation(c)
    row = {"interpretation_id": cited, "condition_id": "z", "holds": True}
    row |= {"evidence_interpretation_id": evidence}
    return c, lambda: _insert(w.rt, "interpretation_condition_evidence", row), VERSION, NONE


def interpretation_operand(w: World) -> Edge:
    """Operands share their parent's capture (0001), so the edge is seen through the operand's
    own condition evidence on another capture."""
    c, other = w.capture(), w.capture()
    cited, operand = w.interpretation(other, constructed=True), w.interpretation(other)
    evidence = {"interpretation_id": operand, "condition_id": "z", "holds": True}
    evidence |= {"evidence_interpretation_id": w.interpretation(c)}
    _insert(w.rt, "interpretation_condition_evidence", evidence)
    w.draft(_figure(cited, w))
    row = {"interpretation_id": cited, "ordinal": 0, "operand_interpretation_id": operand}
    return c, lambda: _insert(w.rt, "interpretation_operands", row), VERSION, NONE


def construction_trace(w: World) -> Edge:
    c = w.capture()
    cited, trace = _cited_on_another_capture(w, constructed=True), w.trace()
    w.operand(trace, interpretation_id=w.interpretation(c))
    row = {"interpretation_id": cited, "calculation_trace_id": trace}
    return c, lambda: _insert(w.rt, "construction_traces", row), VERSION, NONE


def memory_support(w: World) -> Edge:
    c = w.capture()
    return c, lambda: w.support(c), HoldRoot.MEMORY_SUPPORT, NONE


def closed_disposition(w: World) -> Edge:
    c = w.capture()
    occurrence = w.occurrence(c)
    return c, lambda: w.item(disposed=True, occurrence_id=occurrence), QUEUE, NONE


def queue_input(w: World) -> Edge:
    c = w.capture()
    interpretation = w.interpretation(c)
    return c, lambda: w.item(interpretation_id=interpretation), OPEN, NONE


def queue_trace(w: World) -> Edge:
    c = w.capture()
    trace = w.trace()
    w.operand(trace, interpretation_id=w.interpretation(c))
    return c, lambda: w.item(calculation_trace_id=trace), OPEN, NONE


def legacy_binding(w: World) -> Edge:
    c, fact = w.capture(), w.fact()
    return c, lambda: w.bind(fact, c), HoldRoot.LEGACY_BINDING, NONE


def onboarding_record(w: World) -> Edge:
    c = w.capture()
    return c, lambda: w.onboarding(c), HoldRoot.ONBOARDING_RECORD, NONE


def identity_event(w: World) -> Edge:
    c = w.capture()
    return c, lambda: w.identity_event(c), HoldRoot.IDENTITY_EVENT, NONE


def qualification_fixture(w: World) -> Edge:
    c = w.capture(XBRL, blob=LAURUSLABS, url="https://nsearchives.nseindia.com/laurus.xml")
    verify(w.rt, package(w.rt, w.entity_of_its_own(), c))
    root = HoldRoot.QUALIFICATION_FIXTURE
    return c, lambda: w.pins.update({root: pinned_roots(CONFIG)[root]}), root, NONE


def manifest_input(w: World) -> Edge:
    root = HoldRoot.MANIFEST_INPUT
    pinned = pinned_roots(CONFIG)[root]
    c = w.capture(blob=min(pinned))
    return c, lambda: w.pins.update({root: pinned}), root, NONE


def superseded_version(w: World) -> Edge:
    c = w.capture()

    def add() -> None:
        w.draft(predecessor=w.draft(_quote(c)))

    return c, add, VERSION, NONE


EDGES = (
    quote_claim,
    interpretation_claim,
    recursive_trace_operand,
    imported_fact_binding,
    native_fact_admission,
    comparison_pair_value,
    location_marker,
    condition_evidence,
    interpretation_operand,
    construction_trace,
    memory_support,
    closed_disposition,
    queue_input,
    queue_trace,
    legacy_binding,
    onboarding_record,
    identity_event,
    qualification_fixture,
    manifest_input,
    superseded_version,
)


@pytest.fixture
def world(memory: Memory, runtime: psycopg.Connection, pg_db: PgTestDatabase) -> Iterator[World]:
    """The edge fixtures' world over the memory fixture's database."""
    with psycopg.connect(pg_db.conninfo(PgRole.OWNER), autocommit=True) as owner:
        yield World(memory, runtime, owner)


def test_every_r4_edge_holds_and_its_absence_releases(world: World) -> None:
    """H1, H2: in an isolated chain each R4 edge holds its capture (a superseded version's
    included); without that edge the capture is eligible. Run outcomes alone never hold. The
    imported fact's binding is itself a root, so there the edge adds its root to the holds."""
    for build in EDGES:
        capture, add, root, before = build(world)
        released = facts_of(world.rt, capture, world.pins)
        assert released.holds == before, build.__name__
        assert verdict(world.rt, capture, world.pins).kind is (HELD if before else ELIGIBLE), (
            build.__name__
        )
        add()
        held = verdict(world.rt, capture, world.pins)
        assert held.kind is HELD and held.held_by == before | {root}, build.__name__


def test_vendor_captures_are_held_only_by_open_items_until_licence_end(world: World) -> None:
    """H3: a support and an onboarding record on a vendor capture do not hold it; an open item
    on a Tijori capture holds it until disposed. H4: an Upstox instrument list under an identity
    event is eligible at the catalog ceiling, an NSE ``EQUITY_L`` one held. H5: an ``upstox``
    licence end makes a held Upstox capture eligible from the licence end."""
    tijori = world.capture(("tijori", "financials"))
    world.support(tijori)
    world.onboarding(tijori)
    assert verdict(world.rt, tijori).reason is EligibleReason.CATALOG_CEILING
    item = world.item(occurrence_id=world.occurrence(tijori))
    assert verdict(world.rt, tijori).held_by == {HoldRoot.OPEN_QUEUE_ITEM}
    dispose(world.owner, item)
    assert verdict(world.rt, tijori).kind is ELIGIBLE

    instruments, listing = world.capture(("upstox", "instruments")), world.capture()
    for capture in (instruments, listing):
        world.identity_event(capture)
    assert verdict(world.rt, instruments).reason is EligibleReason.CATALOG_CEILING
    assert verdict(world.rt, listing).held_by == {HoldRoot.IDENTITY_EVENT}

    upstox = world.capture(("upstox", "income-statement"))
    world.item(occurrence_id=world.occurrence(upstox))
    assert verdict(world.rt, upstox).kind is HELD
    world.owner.execute("INSERT INTO eqos.licence_ends (source_id) VALUES ('upstox')")
    ended = facts_of(world.rt, upstox).licence_ended_at
    licence = Eligibility(kind=ELIGIBLE, since=ended, reason=EligibleReason.LICENCE_END)
    assert verdict(world.rt, upstox) == licence


def test_the_dry_run_lists_exactly_the_eligible_blobs(
    world: World, pg_db: PgTestDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """H6: with the store clock thirteen months on, ``retention purge --dry-run`` prints each
    eligible blob once with every capture using it, and nothing held or kept."""
    shared = "6" * 64
    eligible = [world.capture(("tijori", "financials"), blob=shared) for _ in range(2)]
    lone = world.capture()
    held = world.capture()
    world.identity_event(held)
    now = later()
    with pg_db.migrator_connection() as migrator:
        set_store_clock(migrator, now)
    expected = eligible_blobs(capture_facts(world.rt, pinned_roots(CONFIG)), now)
    listed = {b.capture_ref_ids for b in expected}
    assert tuple(eligible) in listed and (lone,) in listed and (held,) not in listed
    lines = [
        f"eligible\t{b.source_id}\t{b.blob_sha256}\t{b.since.isoformat()}\t"
        + ",".join(map(str, b.capture_ref_ids))
        for b in expected
    ]
    output = "".join(f"{line}\n" for line in [*lines, f"eligible_blobs\t{len(expected)}"])
    assert retention_cli(monkeypatch, pg_db, "purge", "--dry-run") == (0, output)
    assert retention_cli(monkeypatch, pg_db, "purge")[0] == 2


def test_holds_yaml_lists_the_public_manifests() -> None:
    """H7: the manifests that hold are the public ``*_manifest.yaml`` set minus the opaque
    Stage 4 manifest, compared by name only (it is never opened)."""
    listed = yaml.safe_load((CONFIG / HOLDS_FILE).read_text())["manifests"]
    public = sorted(
        f"{FIXTURES_DIR}/{path.name}"
        for path in (CONFIG.parent / FIXTURES_DIR).glob("*_manifest.yaml")
        if path.name != OPAQUE_MANIFEST
    )
    assert sorted(listed) == public
