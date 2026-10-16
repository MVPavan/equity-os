"""D6 Task 2 (T2): temporal identity layers, entity-map agreement and period-ordered settings.

Every case runs in its own ``eqos_test_*`` database. Synthetic issuers carry invented
``ZZ``-prefixed identifiers; the only real companies are the development ones (Apar, the
ZOMATO/ETERNAL registry alias, the watchlist pins). Retained Apar bytes are read-only; the
renamed filing is a ``tmp_path`` rewrite.
"""

from __future__ import annotations

import hashlib
import shutil
import threading
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path

import psycopg
import pytest
from evidence_support import CONFIG, XBRL_ONLY, Ingest, ingest, policy
from ledger_support import IDENTITY_TABLES
from pg_evidence_schema_support import _update_column, migrator, runtime
from pg_support import PgTestDatabase
from psycopg import errors, sql
from retained_support import REPO_ROOT, MarkedEdit, apar_original, marked_copy
from run_support import Q2_END, Q3_END, Runner, runner

from fundamentals.canon.dictionary import CanonicalDictionary, load_dictionary
from fundamentals.compare.run import RunRequest
from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.basis_status import BasisStatus
from fundamentals.contracts.canonical import Representation
from fundamentals.contracts.entity_identity import (
    JOIN_NAMESPACES,
    CoverageStatus,
    EntityMap,
    IdentifierNamespace,
    MissingReason,
)
from fundamentals.contracts.measurement_key import PeriodInterval
from fundamentals.entity.entity_map import build_entity_map
from fundamentals.entity.entity_map_sources import load_s2_records
from fundamentals.entity.identity_layers import (
    IdentifierRef,
    IdentityConflictError,
    IdentityEventKind,
    issuer_values,
    latest_slice,
    record_event,
    record_relationship,
)
from fundamentals.evidence.first_party_ingest import IngestReport
from fundamentals.evidence.mapping import MappingSet, load_mapping_set
from fundamentals.pg.identity_seed import (
    EvidenceInputKind,
    IssuerIdentityInput,
    SettingKey,
    seed_identity,
    seed_issuer_identity,
)
from fundamentals.pg.settings import SCHEMA_NAME, PgRole

__all__ = ["ingest", "migrator", "policy", "runner", "runtime"]

pytestmark = pytest.mark.pg

ISIN, NSE, BSE = (
    IdentifierNamespace.ISIN,
    IdentifierNamespace.NSE_SYMBOL,
    IdentifierNamespace.BSE_SCRIP,
)
APARINDS, ZZAPAR = "APARINDS", "ZZAPAR"
RENAMED_ON = date(2025, 12, 1)  # between the FY26 Q2 (29-Oct-2025) and Q3 (29-Jan-2026) filings
WATCHLIST = REPO_ROOT / "config" / "watchlist.yaml"
ETERNAL_ISIN = "INE758T01015"  # ACCEPTED_ENTITY_IDS_BY_ISIN key (ZOMATO -> ETERNAL)
NOTICE = b"SYNTHETIC identity notice for tests; no exchange published this."
D1, D2 = date(2026, 1, 1), date(2026, 2, 1)


@pytest.fixture(scope="module")
def dictionary() -> CanonicalDictionary:
    """Canonical dictionary v2 (the onboarding pin)."""
    return load_dictionary(CONFIG / "dictionary", "v2")


@pytest.fixture(scope="module")
def mapping_set(dictionary: CanonicalDictionary) -> MappingSet:
    """Mapping set v5 (the onboarding pin)."""
    return load_mapping_set(CONFIG / "mappings", "v5", dictionary=dictionary)


@pytest.fixture
def conn(pg_db: PgTestDatabase) -> Iterator[psycopg.Connection]:
    """One autocommit runtime connection."""
    with pg_db.runtime_pool() as pool, pool.connection() as connection:
        connection.autocommit = True
        yield connection


def _notice(conn: psycopg.Connection, label: str = "synthetic-notice") -> int:
    """A labelled synthetic evidence input."""
    sha = hashlib.sha256(NOTICE + label.encode()).hexdigest()
    row = conn.execute(
        "INSERT INTO eqos.evidence_inputs (kind, label, content_sha256) VALUES (%s, %s, %s) "
        "RETURNING id",
        (EvidenceInputKind.DISCOVERY.value, label, sha),
    ).fetchone()
    assert row is not None
    return int(row[0])


def _issuer(conn: psycopg.Connection, key: str, isin: str, nse: str, bse: str) -> int:
    """Seed one synthetic issuer; returns its entity id."""
    identity = IssuerIdentityInput(
        entity_key=key,
        display_name=f"{key} Synthetic Limited",
        isin=isin,
        share_class="EQUITY",
        nse_symbol=nse,
        bse_scrip=bse,
        basis_status=BasisStatus.CONSOLIDATED_AND_STANDALONE,
        fiscal_year_end_month=3,
        citations=(),
        content_sha256=hashlib.sha256(key.encode()).hexdigest(),
    )
    return seed_issuer_identity(conn, identity).entity_ids[key]


def _ref(conn: psycopg.Connection, namespace: IdentifierNamespace, value: str) -> IdentifierRef:
    """The target currently holding a value."""
    (target,) = {
        item.security_id if namespace is ISIN else item.listing_id
        for item in latest_slice(conn)
        if item.namespace is namespace and item.value == value
    }
    assert target is not None
    return IdentifierRef(namespace=namespace, target_id=target)


def _held(conn: psycopg.Connection, entity_id: int, at: date | None) -> dict[str, str]:
    """An entity's identifiers at a date, by namespace."""
    return {
        item.namespace.value: item.value
        for item in latest_slice(conn, at)
        if item.entity_id == entity_id
    }


def _change(
    conn: psycopg.Connection,
    ref: IdentifierRef,
    value: str,
    at: date,
    kind: IdentityEventKind = IdentityEventKind.SYMBOL_CHANGE,
) -> int:
    """A one-for-one change event on one target."""
    return record_event(
        conn, kind, at, _notice(conn, f"{kind}-{value}-{at}"), ends=[ref], starts=[(ref, value)]
    )


# --- synthetic rename on Apar -----------------------------------------------------------------


def _xbrl_outcome(report: IngestReport) -> ExtractionOutcome:
    """The XBRL member's extraction outcome."""
    (outcome,) = {
        item.outcome for item in report.attempts if item.representation is Representation.XBRL
    }
    return outcome


@pytest.mark.retained
def test_a_symbol_change_moves_identity_at_its_effective_date_through_ingest(
    ingest: Ingest, tmp_path: Path
) -> None:
    """Each filing verifies against the identity in force on its filed date: the pre-rename
    filing under the old symbol, the post-rename filing only under the new one."""
    repository = ingest.repository
    with ingest.pg_db.runtime_pool() as pool, pool.connection() as conn:
        conn.autocommit = True
        listing = _ref(conn, NSE, APARINDS)
        with pytest.raises(IdentityConflictError, match="needs an identity event"):
            record_relationship(conn, listing, ZZAPAR, _notice(conn))
        _change(conn, listing, ZZAPAR, RENAMED_ON)
        before = _held(conn, ingest.entity_id, RENAMED_ON - timedelta(days=1))
        after = _held(conn, ingest.entity_id, RENAMED_ON)
    assert (before[NSE], after[NSE]) == (APARINDS, ZZAPAR)
    assert before[ISIN] == after[ISIN] and before[BSE] == after[BSE]
    on = repository.issuer_identifiers(ingest.entity_id, as_of=RENAMED_ON)
    day_before = repository.issuer_identifiers(
        ingest.entity_id, as_of=RENAMED_ON - timedelta(days=1)
    )
    assert (day_before.nse_symbol, on.nse_symbol) == (APARINDS, ZZAPAR)

    pre = ingest.run(ingest.intake(XBRL_ONLY, "FY26_Q2"), Q2_END)
    stale = ingest.run(ingest.intake(XBRL_ONLY, "FY26_Q3"), Q3_END)
    edit = MarkedEdit(label="renamed", find=b">APARINDS<", replace=b">ZZAPAR<")
    renamed = marked_copy(
        apar_original("FY26_Q3", "xbrl-consolidated"), edit=edit, tmp_path=tmp_path
    )
    marked = ingest.intake(XBRL_ONLY, "FY26_Q3", marked={Representation.XBRL: renamed})
    post = ingest.run(marked, Q3_END)
    assert _xbrl_outcome(pre) is ExtractionOutcome.COMPLETE
    assert _xbrl_outcome(stale) is ExtractionOutcome.IDENTITY_REJECTED
    assert _xbrl_outcome(post) is ExtractionOutcome.COMPLETE


def test_a_registry_alias_isin_refuses_a_symbol_change(conn: psycopg.Connection) -> None:
    """ZOMATO -> ETERNAL is encoded by the registry; an event would be a second mechanism."""
    _issuer(conn, "ETERNAL", ETERNAL_ISIN, "ETERNAL", "543320")
    with pytest.raises(IdentityConflictError, match="registry alias"):
        _change(conn, _ref(conn, NSE, "ETERNAL"), "ZZETERNAL", D1)


# --- lifecycle --------------------------------------------------------------------------------


@pytest.fixture
def pair(conn: psycopg.Connection) -> tuple[int, int]:
    """Two synthetic issuers: ZZA and ZZB."""
    return (
        _issuer(conn, "ZZA", "ZZA000000001", "ZZA", "990001"),
        _issuer(conn, "ZZB", "ZZB000000002", "ZZB", "990002"),
    )


def test_boundaries_and_a_future_effective_change(
    conn: psycopg.Connection, pair: tuple[int, int]
) -> None:
    """Half-open intervals: the old value through the day before, the new one from the date;
    a future-effective event is recorded but not yet current."""
    alpha, _ = pair
    unchanged = _held(conn, alpha, None)
    assert unchanged == {ISIN: "ZZA000000001", NSE: "ZZA", BSE: "990001"}
    _change(
        conn, _ref(conn, ISIN, "ZZA000000001"), "ZZA000000009", D1, IdentityEventKind.ISIN_CHANGE
    )
    assert _held(conn, alpha, D1 - timedelta(days=1))[ISIN] == "ZZA000000001"
    assert _held(conn, alpha, D1)[ISIN] == "ZZA000000009"
    future = date.today() + timedelta(days=400)
    _change(conn, _ref(conn, NSE, "ZZA"), "ZZAFUT", future)
    assert _held(conn, alpha, None)[NSE] == "ZZA"
    assert _held(conn, alpha, future)[NSE] == "ZZAFUT"
    with pytest.raises(IdentityConflictError, match="precedes the start"):
        _change(
            conn,
            _ref(conn, ISIN, "ZZA000000009"),
            "ZZA000000008",
            D1 - timedelta(days=1),
            IdentityEventKind.ISIN_CHANGE,
        )


def test_a_live_or_once_held_symbol_is_refused_and_reuse_needs_the_prior_end(
    conn: psycopg.Connection, pair: tuple[int, int]
) -> None:
    """A symbol held by another listing is refused; once ended it moves only by
    ``SYMBOL_REUSE`` effective on/after the end."""
    alpha, bravo = pair
    with pytest.raises(IdentityConflictError, match="was held by another listing"):
        _change(conn, _ref(conn, NSE, "ZZB"), "ZZA", D1)
    alpha_listing = _ref(conn, NSE, "ZZA")
    _change(conn, alpha_listing, "ZZANEW", D1)
    bravo_listing = _ref(conn, NSE, "ZZB")
    with pytest.raises(IdentityConflictError, match="was held by another listing"):
        _change(conn, bravo_listing, "ZZA", D2)
    with pytest.raises(IdentityConflictError, match="still held"):
        _change(conn, bravo_listing, "ZZA", D1 - timedelta(days=1), IdentityEventKind.SYMBOL_REUSE)
    _change(conn, bravo_listing, "ZZA", D2, IdentityEventKind.SYMBOL_REUSE)
    assert _held(conn, alpha, D2)[NSE] == "ZZANEW"
    assert _held(conn, bravo, D2)[NSE] == "ZZA"
    assert _held(conn, alpha, D1 - timedelta(days=1))[NSE] == "ZZA"


def test_a_concurrent_competing_assignment_lets_exactly_one_win(
    pg_db: PgTestDatabase, conn: psycopg.Connection, pair: tuple[int, int]
) -> None:
    """Two connections race for one new symbol; the advisory lock serialises them."""
    del pair
    alpha, bravo = _ref(conn, NSE, "ZZA"), _ref(conn, NSE, "ZZB")
    notice = _notice(conn)
    errors_seen: list[Exception] = []

    def compete() -> None:
        with psycopg.connect(pg_db.conninfo(PgRole.RUNTIME), autocommit=True) as other:
            try:
                record_event(
                    other,
                    IdentityEventKind.SYMBOL_CHANGE,
                    D1,
                    notice,
                    ends=[bravo],
                    starts=[(bravo, "ZZWIN")],
                )
            except IdentityConflictError as error:
                errors_seen.append(error)

    with psycopg.connect(pg_db.conninfo(PgRole.RUNTIME)) as first:
        with first.transaction():
            record_event(
                first,
                IdentityEventKind.SYMBOL_CHANGE,
                D1,
                notice,
                ends=[alpha],
                starts=[(alpha, "ZZWIN")],
            )
            racer = threading.Thread(target=compete)
            racer.start()
            racer.join(timeout=1.0)
            assert racer.is_alive()  # blocked on the lock, not racing past it
        racer.join(timeout=10.0)
    assert len(errors_seen) == 1
    holders = [item for item in latest_slice(conn, D1) if item.value == "ZZWIN"]
    assert [item.listing_id for item in holders] == [alpha.target_id]


def test_delisting_merger_and_demerger_shapes(
    conn: psycopg.Connection, pair: tuple[int, int]
) -> None:
    """``DELISTING`` ends a listing's code once; a second end is refused; merger and demerger
    take disjoint predecessors and successors."""
    alpha, bravo = pair
    gamma = _issuer(conn, "ZZC", "ZZC000000003", "ZZC", "990003")
    bse = _ref(conn, BSE, "990001")
    record_event(conn, IdentityEventKind.DELISTING, D1, _notice(conn), ends=[bse])
    assert BSE not in _held(conn, alpha, D1)
    with pytest.raises(IdentityConflictError, match="holds no open value"):
        record_event(conn, IdentityEventKind.DELISTING, D2, _notice(conn, "again"), ends=[bse])
    with pytest.raises(LookupError):
        issuer_values(conn, alpha, D1)
    notice = _notice(conn, "corporate")
    record_event(
        conn,
        IdentityEventKind.DEMERGER,
        D1,
        notice,
        predecessors=[alpha],
        successors=[bravo, gamma],
    )
    record_event(
        conn, IdentityEventKind.MERGER, D2, notice, predecessors=[bravo, gamma], successors=[alpha]
    )
    for kind, predecessors, successors in (
        (IdentityEventKind.MERGER, [alpha], [alpha]),
        (IdentityEventKind.MERGER, [alpha], [bravo, gamma]),
        (IdentityEventKind.DEMERGER, [alpha, bravo], [gamma]),
    ):
        with pytest.raises(IdentityConflictError, match="disjoint entities"):
            record_event(conn, kind, D2, notice, predecessors=predecessors, successors=successors)
    edges = conn.execute(
        "SELECT role, count(*) FROM eqos.identity_event_edges GROUP BY role"
    ).fetchall()
    assert dict(edges) == {"ENDS": 1, "PREDECESSOR": 3, "SUCCESSOR": 3}


def test_malformed_edges_are_refused(conn: psycopg.Connection, pair: tuple[int, int]) -> None:
    """A venue code cannot change namespace, and an ISIN cannot sit on a listing."""
    del pair
    nse, bse = _ref(conn, NSE, "ZZA"), _ref(conn, BSE, "990001")
    with pytest.raises(IdentityConflictError, match="same listing"):
        record_event(
            conn,
            IdentityEventKind.SYMBOL_CHANGE,
            D1,
            _notice(conn),
            ends=[nse],
            starts=[(bse, "990009")],
        )
    with pytest.raises(errors.CheckViolation):
        conn.execute(
            "INSERT INTO eqos.identifier_relationships "
            "(listing_id, namespace, value, evidence_input_id) VALUES (%s, 'ISIN', %s, %s)",
            (nse.target_id, "ZZA000000001", _notice(conn, "isin-on-listing")),
        )


def test_identity_tables_are_append_only(
    conn: psycopg.Connection,
    pair: tuple[int, int],
    runtime: psycopg.Connection,
    migrator: psycopg.Connection,
) -> None:
    """Runtime lacks UPDATE and DELETE; the owner hits the immutability trigger."""
    alpha, _ = pair
    _change(conn, _ref(conn, NSE, "ZZA"), "ZZA2", D1)
    record = conn.execute(
        "INSERT INTO eqos.onboarding_records "
        "(identifier, identifier_namespace, outcome, entity_id) "
        "VALUES ('ZZA', 'NSE_SYMBOL', 'PARTIAL', %s) RETURNING id",
        (alpha,),
    ).fetchone()
    assert record is not None
    conn.execute(
        "INSERT INTO eqos.namespace_verifications (onboarding_record_id, unit, state, reason) "
        "VALUES (%s, 'RESULTS_PDF', 'UNAVAILABLE', 'R-PDF')",
        (record[0],),
    )
    for table in sorted(IDENTITY_TABLES):
        target = sql.Identifier(SCHEMA_NAME, table)
        column = sql.Identifier(_update_column(migrator, table))
        for statement in (
            sql.SQL("UPDATE {} SET {} = {}").format(target, column, column),
            sql.SQL("DELETE FROM {}").format(target),
        ):
            with pytest.raises(errors.InsufficientPrivilege):
                runtime.execute(statement)
            with pytest.raises(errors.RaiseException, match="immutable"):
                migrator.execute(statement)


# --- R-MAP: the entity map and the current slice agree --------------------------------------


def _map_identities(built: EntityMap) -> set[frozenset[tuple[str, str]]]:
    """Each unconflicted entity's verified ISIN, NSE symbol and BSE scrip."""
    found = set()
    for entity in built.entities:
        if entity.conflicted:
            continue
        found.add(
            frozenset(
                (namespace.value, held.value)
                for namespace in JOIN_NAMESPACES
                if entity.coverage(namespace).status is CoverageStatus.KNOWN
                for held in entity.coverage(namespace).values
                if held.verified
            )
        )
    return found


def _slice_identities(conn: psycopg.Connection) -> set[frozenset[tuple[str, str]]]:
    """Each security's current identifiers."""
    by_security: dict[int, set[tuple[str, str]]] = {}
    for item in latest_slice(conn):
        by_security.setdefault(item.security_id, set()).add((item.namespace.value, item.value))
    return {frozenset(values) for values in by_security.values()}


def test_the_entity_map_equals_the_current_slice_before_and_after_an_event(
    conn: psycopg.Connection, tmp_path: Path
) -> None:
    """The map is a projection of source artifacts; after an event plus the matching source
    update it agrees with ``latest_slice`` again."""
    built = build_entity_map(load_s2_records(WATCHLIST))
    seed_identity(conn, built, source_sha256=hashlib.sha256(WATCHLIST.read_bytes()).hexdigest())
    assert _slice_identities(conn) == _map_identities(built)

    _change(conn, _ref(conn, NSE, APARINDS), ZZAPAR, D1)
    updated = tmp_path / "watchlist.yaml"
    shutil.copyfile(WATCHLIST, updated)
    text = updated.read_text(encoding="utf-8")
    assert text.count(f'nse_symbol: "{APARINDS}"') == 1
    updated.write_text(text.replace(f'nse_symbol: "{APARINDS}"', f'nse_symbol: "{ZZAPAR}"'))
    rebuilt = build_entity_map(load_s2_records(updated))
    assert _slice_identities(conn) == _map_identities(rebuilt) != _map_identities(built)


def test_warehouse_ids_distinguish_present_reported_absent_and_not_supplied(
    tmp_path: Path,
) -> None:
    """NETWEB's null consolidated id is the company's fact; an omitted field is our gap."""
    config = tmp_path / "watchlist.yaml"
    text = WATCHLIST.read_text(encoding="utf-8")
    apar_standalone = "      screener_warehouse_id_standalone: 2446\n"
    assert text.count(apar_standalone) == 1
    config.write_text(text.replace(apar_standalone, ""))
    entities = {
        entity.coverage(NSE).values[0].value: entity
        for entity in build_entity_map(load_s2_records(config)).entities
    }
    consolidated = IdentifierNamespace.SCREENER_WAREHOUSE_ID_CONSOLIDATED
    standalone = IdentifierNamespace.SCREENER_WAREHOUSE_ID_STANDALONE
    apar, netweb = entities[APARINDS], entities["NETWEB"]
    assert [held.value for held in apar.coverage(consolidated).values] == ["6594631"]
    assert apar.coverage(standalone).missing_reason is MissingReason.NOT_SUPPLIED
    assert netweb.coverage(consolidated).missing_reason is MissingReason.SOURCE_REPORTED_ABSENT
    assert [held.value for held in netweb.coverage(standalone).values] == ["104235517"]


# --- settings governed by period (C4) ---------------------------------------------------------


@pytest.mark.retained
def test_fiscal_year_end_is_governed_by_period_in_ingest_execute_and_replay(
    runner: Runner,
) -> None:
    """Year end 3 governs Q2 FY26, 12 governs the Dec-2025 period end, the later-period row
    recorded first; ingest, a two-period run, per-period runs and replays all agree."""
    ingest, repository = runner.ingest, runner.repository
    entity = ingest.entity_id
    key = SettingKey.FISCAL_YEAR_END_MONTH
    today = repository.settings_as_of(entity, key, runner.now())
    assert today is not None
    for period_end in (Q2_END, Q3_END, None):
        assert repository.settings_as_of(entity, key, runner.now(), period_end) == today

    with ingest.pg_db.runtime_pool() as pool, pool.connection() as conn:
        conn.autocommit = True
        december, march = _notice(conn, "fye-12"), _notice(conn, "fye-3")
    later = repository.put_settings_record(entity, key, "12", december, valid_from=Q3_END)
    earlier = repository.put_settings_record(entity, key, "3", march, valid_from=Q2_END)
    governing = {
        end: repository.settings_as_of(entity, key, runner.now(), end) for end in (Q2_END, Q3_END)
    }
    assert {end: (row.id, row.value_text) for end, row in governing.items() if row} == {
        Q2_END: (earlier, "3"),
        Q3_END: (later, "12"),
    }

    reports = {
        end: ingest.run(ingest.intake(XBRL_ONLY, quarter), end)
        for end, quarter in ((Q2_END, "FY26_Q2"), (Q3_END, "FY26_Q3"))
    }
    kinds = {end: ingest.package(report).reporting_kind.value for end, report in reports.items()}
    assert kinds == {Q2_END: "HALF_YEAR", Q3_END: "QUARTER"}

    both = runner.request(Q2_END)
    both = RunRequest.model_validate(
        both.model_dump()
        | {"scope": both.scope.model_copy(update={"period_ends": (Q2_END, Q3_END)})}
    )
    year_to_date = {
        Q2_END: PeriodInterval.duration(date(2025, 4, 1), Q2_END),
        Q3_END: PeriodInterval.duration(date(2025, 1, 1), Q3_END),
    }
    for request in (both, runner.request(Q2_END), runner.request(Q3_END)):
        record = runner.execute(request)
        assert record.run_id is not None
        rows = runner.results(record.run_id)
        assert runner.replay(record.run_id) == rows
        periods = {row.key.period for row in rows}
        for end in request.scope.period_ends:
            assert year_to_date[end] in periods
