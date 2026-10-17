"""D9 Task 2: retention classes, catalog authority and registration (plan D9 cases C1-C7).

Why: purge decides from the class alone, so every intake path must write exactly one class row
(and an exchange capture its address, without which it can never be re-fetched); coverage must
follow the watchlist without extending vendor captures; and nothing may rest on a vendor whose
licence has ended, or quote a vendor's bytes, whatever the writing code does.
"""

from __future__ import annotations

import contextlib
import io
from datetime import UTC, datetime
from decimal import Decimal

import psycopg
import pytest
from coverage_support import SEED_RULING, watchlist
from evidence_support import (
    Q2_FY26,
    XBRL_KIND,
    XBRL_ONLY,
    Ingest,
    dictionary,
    ingest,
    mapping_set,
    policy,
)
from ledger_support import Ledger, ledger
from memory_support import Memory, memory
from pg_evidence_schema_support import _attempt, _insert, _occurrence, runtime, seeded
from pg_support import PgTestDatabase
from psycopg import errors, sql
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool
from retained_support import apar_store, manifest_entry
from retention_support import (
    RETENTION_TABLES,
    address_of,
    class_of,
    finish_migrations,
    pre_retention_db,
    synthetic,
)

from fundamentals.api.cli import main
from fundamentals.contracts.canonical import Representation
from fundamentals.contracts.comparison import SourceRole
from fundamentals.contracts.guidance_claim import EpistemicClass
from fundamentals.contracts.ledger import (
    Citation,
    CitationKind,
    DecisionKind,
    NumericClaim,
    Rounding,
    SubjectKind,
    ValueKind,
)
from fundamentals.contracts.memory import MemoryKind, SupportDraft, SupportTarget
from fundamentals.contracts.onboarding import VerificationUnit
from fundamentals.contracts.retention import RefusalCode, RetentionClass
from fundamentals.contracts.source_catalog import NSE_MASTER, VENDOR_SURFACES
from fundamentals.entity.discovery import OK, Capture, Request, Response, store_captures
from fundamentals.evidence import repository_rows as rows_sql
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.ingest.screener_source import SOURCE_ID as LEGACY_SCREENER_SOURCE
from fundamentals.ledger import lifecycle
from fundamentals.pg.settings import PgRole

pytestmark = pytest.mark.pg

__all__ = ["dictionary", "ingest", "ledger", "mapping_set", "memory", "policy", "runtime"]
__all__ += ["pre_retention_db", "seeded"]

# One capture per R2 row, Upstox instruments included, and its expected class.
R2_ROWS = {
    ("screener-subscriber", "SCREENER_FINANCIALS"): RetentionClass.VENDOR,
    ("screener", "SCREENER_DOCS"): RetentionClass.VENDOR,
    ("tijori", "company_search"): RetentionClass.VENDOR,
    ("upstox", "income-statement"): RetentionClass.VENDOR,
    ("upstox", "instruments"): RetentionClass.IDENTITY,
    ("nse", "EQUITY_L"): RetentionClass.IDENTITY,
    ("nse", "INTEGRATED_FILING_LISTING"): RetentionClass.IDENTITY,
    ("nse", "SHAREHOLDING_LISTING"): RetentionClass.IDENTITY,
    ("bse", "PEER_SMART_SEARCH"): RetentionClass.IDENTITY,
    ("nse-indas-xbrl-consolidated", "NSE_XBRL_INSTANCE"): RetentionClass.EXCHANGE_REFETCHABLE,
    ("aparinds-fy26-q2-results-pdf", "NSE_RESULTS_PDF"): RetentionClass.EXCHANGE_REFETCHABLE,
    ("aparinds-transcript", "NSE_TRANSCRIPT_PDF"): RetentionClass.EXCHANGE_REFETCHABLE,
    ("nse-shareholding-xbrl", "NSE_SHP_XBRL"): RetentionClass.EXCHANGE_REFETCHABLE,
    ("sebi", "REGULATION_TEXT"): RetentionClass.COVERED,
}
INTAKE, ONE_OFF = "INTAKE", "ONE_OFF"
COVERED = "SELECT eqos.capture_covered(%s)"
LIMITED = "SELECT capture_ref_id FROM eqos.retention_limited WHERE decision_id = %s"
LICENCE_END = "INSERT INTO eqos.licence_ends (source_id) VALUES (%s)"
NSE_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"


def _classify(monkeypatch: pytest.MonkeyPatch, database: PgTestDatabase) -> tuple[int, str]:
    """``fundamentals retention classify`` against ``database``: exit code and stdout."""
    for name, value in database.cli_env().items():
        monkeypatch.setenv(name, value)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(["retention", "classify"])
    return code, out.getvalue()


def test_a_pre_retention_capture_is_unclassified_until_the_one_off_classify(
    pre_retention_db: tuple[PgTestDatabase, psycopg.Connection], monkeypatch: pytest.MonkeyPatch
) -> None:
    """C1: 0027 classifies nothing already registered; ``classify`` gives each R2 row its class
    once, and a rerun writes nothing."""
    database, migrator = pre_retention_db
    ids = {}
    for (source, surface), _ in R2_ROWS.items():
        query = rows_sql.INSERT_CAPTURE_REF + " RETURNING id"
        ((ids[source, surface],),) = migrator.execute(
            query, rows_sql.capture_params(synthetic(source, surface))
        ).fetchall()
    finish_migrations(migrator)
    assert {class_of(migrator, ref) for ref in ids.values()} == {(None, None)}

    assert _classify(monkeypatch, database) == (0, f"classified\t{len(R2_ROWS)}\n")
    for pair, expected in R2_ROWS.items():
        assert class_of(migrator, ids[pair]) == (expected, ONE_OFF), pair
    assert _classify(monkeypatch, database) == (0, "classified\t0\n")


def test_every_intake_path_writes_the_class_and_the_non_vendor_paths_the_url(
    ingest: Ingest, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """C2: discovery, first-party and vendor intake each write the class at intake; discovery
    and first-party also record the address the bytes came from, vendor intake none."""
    first_party = ingest.capture_id(ingest.run(ingest.intake(XBRL_ONLY)), Representation.XBRL)
    store = apar_store(tmp_path_factory.mktemp("discovery"))
    discovered = Capture(
        request=Request(
            unit=VerificationUnit.EXCHANGE,
            source_id=NSE_MASTER[0],
            surface=NSE_MASTER[1],
            url=NSE_URL,
        ),
        response=Response(outcome=OK, body=b"SYMBOL,ISIN\n", retrieved_at=datetime.now(UTC)),
    )
    with store.prepare_ordinary_output():
        ((_, discovery),) = store_captures(store, ingest.repository, [discovered])
    vendor = ingest.repository.put_capture_ref(synthetic("tijori", "financials"))
    with ingest.pg_db.runtime_pool() as pool, pool.connection() as conn:
        assert class_of(conn, first_party) == (RetentionClass.EXCHANGE_REFETCHABLE, INTAKE)
        assert address_of(conn, first_party) == manifest_entry(Q2_FY26, XBRL_KIND)["url"]
        assert class_of(conn, discovery.capture_ref_id) == (RetentionClass.IDENTITY, INTAKE)
        assert address_of(conn, discovery.capture_ref_id) == NSE_URL
        assert class_of(conn, vendor.capture_ref_id) == (RetentionClass.VENDOR, INTAKE)
        assert address_of(conn, vendor.capture_ref_id) is None


def _link(conn: psycopg.Connection, entity_id: int, capture_ref_id: int | None) -> None:
    """SEED: an attempt making the capture evidence of the entity (``capture_entities``)."""
    row = conn.execute(rows_sql.CAPTURE_REFS_BY_ID, ([capture_ref_id],)).fetchone()
    assert row is not None and capture_ref_id is not None
    attempt = _attempt(entity_id, capture_ref_id) | {"source_id": row[1], "surface": row[2]}
    _insert(conn, "acquisition_attempts", attempt | {"representation": "HTML"})


def _covered(conn: psycopg.Connection, capture_ref_id: int | None) -> bool:
    """``eqos.capture_covered`` now."""
    row = conn.execute(COVERED, (capture_ref_id,)).fetchone()
    assert row is not None
    return bool(row[0])


def test_coverage_follows_the_watchlist_without_extending_vendor_captures(
    ingest: Ingest, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """C3: Apar's exchange capture is covered once the stock is added and stays covered after a
    REMOVE; one registered after the REMOVE is not; its Screener capture stays VENDOR and is
    listed as limited by the ADD."""
    entity = ingest.entity_id
    exchange = ingest.capture_id(ingest.run(ingest.intake(XBRL_ONLY)), Representation.XBRL)
    repository = ingest.repository
    screener = repository.put_capture_ref(synthetic("screener-subscriber", "SCREENER_FINANCIALS"))
    pg_db = ingest.pg_db
    with pg_db.runtime_pool() as run_pool, pg_db.owner_pool() as owner_pool:
        pools: dict[PgRole, ConnectionPool] = {PgRole.RUNTIME: run_pool, PgRole.OWNER: owner_pool}
        with run_pool.connection() as conn:
            _link(conn, entity, screener.capture_ref_id)
            assert class_of(conn, exchange) == (RetentionClass.EXCHANGE_REFETCHABLE, INTAKE)
            assert not _covered(conn, exchange)
            added = watchlist(pools, entity, apar_store(tmp_path_factory.mktemp("seed")))
            assert _covered(conn, exchange)
            assert class_of(conn, screener.capture_ref_id) == (RetentionClass.VENDOR, INTAKE)
            assert not _covered(conn, screener.capture_ref_id)
            limited = {row[0] for row in conn.execute(LIMITED, (added.id,)).fetchall()}
            assert screener.capture_ref_id in limited and exchange not in limited
            lifecycle.decide(
                owner_pool,
                subject_kind=SubjectKind.WATCHLIST,
                subject_id=entity,
                kind=DecisionKind.REMOVE,
                ruling=SEED_RULING,
            )
            later_ref = synthetic("nse-indas-xbrl-consolidated", "NSE_XBRL_INSTANCE")
            now = repository.store_clock()
            later = repository.put_capture_ref(
                later_ref.model_copy(update={"registered_at": now, "first_seen_at": now})
            )
            _link(conn, entity, later.capture_ref_id)
            assert _covered(conn, exchange)
            assert not _covered(conn, later.capture_ref_id)


def test_a_second_class_row_is_refused(pg_db: PgTestDatabase, seeded: dict[str, int]) -> None:
    """C4: a capture keeps the one class its intake gave it; retention tables never shrink."""
    capture = seeded["capture_refs"]
    row = (capture, RetentionClass.COVERED.value, ONE_OFF)
    insert = "INSERT INTO eqos.retention_classes VALUES (%s, %s, %s)"
    with pg_db.migrator_connection() as migrator:
        assert class_of(migrator, capture) == (RetentionClass.EXCHANGE_REFETCHABLE, INTAKE)
        with pytest.raises(errors.UniqueViolation):
            migrator.execute(insert, row)
        for table in RETENTION_TABLES:
            with pytest.raises(errors.RaiseException, match="immutable"):
                migrator.execute(sql.SQL("TRUNCATE eqos.{} CASCADE").format(sql.Identifier(table)))
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        with pytest.raises(errors.InsufficientPrivilege):
            conn.execute(insert, row)


def _support(memory: Memory, capture_ref_id: int | None) -> int:
    """Stage a source-quirk memory item supported by one capture."""
    assert capture_ref_id is not None
    capture = SupportDraft(target=SupportTarget.CAPTURE, target_id=capture_ref_id)
    return memory.stage(kind=MemoryKind.SOURCE_QUIRK, supports=(capture,))


def test_nothing_new_rests_on_a_licence_ended_vendor(
    memory: Memory, seeded: dict[str, int]
) -> None:
    """C5: after a ``tijori`` licence end, Tijori intake, an open queue input on a Tijori capture
    and a memory support on one are each refused BEYOND_AUTHORITY."""
    pools = memory.ledger.pools
    repository = EvidenceRepository(pools[PgRole.RUNTIME])
    tijori = repository.put_capture_ref(synthetic("tijori", "financials"))
    with pools[PgRole.RUNTIME].connection() as conn:
        occurrence = _insert(conn, "occurrences", _occurrence(tijori.capture_ref_id or 0, "tj-1"))
    with pools[PgRole.OWNER].connection() as conn:
        conn.execute(LICENCE_END, ("tijori",))
    with _refused():
        repository.put_capture_ref(synthetic("tijori", "financials"))
    with _refused(), pools[PgRole.RUNTIME].connection() as conn, conn.transaction():
        item = _insert(conn, "queue_items", _queue_item(seeded["runs"]))
        _insert(conn, "queue_item_inputs", {"item_id": item, "occurrence_id": occurrence})
    with _refused():
        _support(memory, tijori.capture_ref_id)


def _refused() -> pytest.RaisesExc[errors.InsufficientPrivilege]:
    """The database's BEYOND_AUTHORITY refusal."""
    return pytest.raises(errors.InsufficientPrivilege, match=RefusalCode.BEYOND_AUTHORITY)


def _queue_item(run_id: int) -> dict[str, object]:
    """An open queue item of ``run_id``."""
    return {
        "run_id": run_id,
        "pair_identity": "tijori-pair",
        "outcome": "UNMAPPED",
        "input_sha256": "6" * 64,
        "severity": "HIGH",
        "diagnostic": False,
        "routing_reason": "MAPPING_DEFINITION_OR_SOURCE_ERROR",
        "source_refs": Jsonb([]),
    }


def _quote(capture_ref_id: int | None) -> NumericClaim:
    """A ``SOURCE_QUOTE`` claim on one capture, keyed as the fixture section expects."""
    return NumericClaim(
        claim_key="calc.1",
        section_key="preamble",
        citation=Citation(
            kind=CitationKind.SOURCE_QUOTE, capture_ref_id=capture_ref_id, anchor="p1", quote="12%"
        ),
        value_kind=ValueKind.PERCENTAGE,
        unit="%",
        value=Decimal("12"),
        precision=0,
        rounding=Rounding.ROUND_HALF_UP,
        epistemic_class=EpistemicClass.FORECAST,
        metric="margin",
        metric_label="EBITDA margin",
        scope="consolidated",
        constant_currency=False,
    )


def test_a_vendor_capture_is_never_quoted_but_may_support_memory(
    ledger: Ledger, memory: Memory
) -> None:
    """C6: a ``SOURCE_QUOTE`` on a Screener capture is refused; a memory support is accepted."""
    repository = EvidenceRepository(ledger.pools[PgRole.RUNTIME])
    screener = repository.put_capture_ref(synthetic("screener-subscriber", "SCREENER_FINANCIALS"))
    with _refused():
        ledger.draft(ledger.report(), claims=(_quote(screener.capture_ref_id),))
    assert _support(memory, screener.capture_ref_id) > 0


def test_vendor_sources_are_the_catalogs_vendor_and_diagnostic_sources(
    pg_db: PgTestDatabase,
) -> None:
    """C7: ``eqos.is_vendor_source`` names exactly the sources of the catalog's independent-vendor
    and diagnostic surfaces, plus the legacy Screener source R2 names."""
    roles = (SourceRole.INDEPENDENT_VENDOR, SourceRole.DIAGNOSTIC)
    vendors = {a.source_id for a in VENDOR_SURFACES if a.role in roles} | {LEGACY_SCREENER_SOURCE}
    sources = {a.source_id for a in VENDOR_SURFACES} | vendors
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        found = {
            source
            for source in sources
            if conn.execute("SELECT eqos.is_vendor_source(%s)", (source,)).fetchone() == (True,)
        }
    assert found == vendors


INSERTERS = {
    "retention_classes": set(),
    "capture_addresses": {"eqos_runtime", "eqos_owner"},
    "licence_ends": {"eqos_owner", "eqos_purge"},
    "capture_states": set(),
    "purge_runs": set(),
    "purge_run_closures": set(),
}


def test_retention_grants_follow_the_plan(pg_db: PgTestDatabase) -> None:
    """Every role reads the retention tables; only the listed roles insert, nobody changes them
    (class rows come only from the definer trigger and ``classify_existing``)."""
    roles = ("eqos_runtime", "eqos_panel", "eqos_owner", "eqos_purge")
    privileges = "SELECT has_table_privilege(%s, %s, 'SELECT'), has_table_privilege(%s, %s, "
    privileges += "'INSERT'), has_table_privilege(%s, %s, 'UPDATE, DELETE, TRUNCATE')"
    with pg_db.migrator_connection() as conn:
        for table, inserters in INSERTERS.items():
            for role in roles:
                granted = conn.execute(privileges, (role, f"eqos.{table}") * 3).fetchone()
                assert granted == (True, role in inserters, False), (role, table)
