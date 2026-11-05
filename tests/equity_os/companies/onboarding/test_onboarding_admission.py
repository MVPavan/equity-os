"""D6 Task 3 (T3): admission — stable-id resolution, its transaction, and the insertion gate.

Outcome paths run ``main(["onboard", …])`` in replay over ``onboarding_support`` roots; the
concurrency cases drive ``record`` on two connections against one guarded test database.
"""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import psycopg
import pytest
from evidence_support import CONFIG
from onboarding_support import (
    APAR,
    APAR_ISIN,
    APAR_SCRIP,
    FAILURE,
    INCOMPLETE,
    JUN,
    MAR,
    OC,
    VERIFIED_FIVE,
    ZZ_ISIN,
    S,
    U,
    cli,
    count,
    db_event,
    edit,
    event,
    evidence_counts,
    fresh_db,
    recorded,
    rename,
    rows,
    seed,
    seed_on,
    synthetic_isin,
    table_counts,
    world,
    write_root,
)
from pg_support import PgTestDatabase
from retained_support import apar_catalog, seed_apar
from test_evidence_vendor_screener import binding as screener_binding

from equity_os.companies.identity.identity_layers import IdentityEventKind, latest_slice
from equity_os.companies.onboarding.discovery import (
    Discovery,
    OnboardingAbortError,
    Recorded,
    discover,
    record,
    replay_fetch,
    store_captures,
)
from equity_os.companies.onboarding.discovery_gate import IneligibleCaptureError
from equity_os.contracts.companies.entity_identity import IdentifierNamespace
from equity_os.contracts.companies.onboarding import VerificationUnit
from equity_os.contracts.measurement.canonical import Basis, Representation
from equity_os.contracts.measurement.evidence import CaptureReference, FilingFamily
from equity_os.contracts.measurement.observation import AccountingFramework
from equity_os.contracts.sourcing.snapshot import INTAKE_RIGHTS
from equity_os.contracts.sourcing.source_catalog import VENDOR_SURFACES
from equity_os.extraction.packages.capture_intake import RetainedCaptureBinding, RetainedIntake
from equity_os.extraction.packages.first_party_extract import IngestError
from equity_os.extraction.packages.first_party_ingest import ingest_first_party
from equity_os.extraction.surfaces.vendor_ingest import VendorIngestRequest, ingest_vendor
from equity_os.extraction.vendors.screener import vendor_screener
from equity_os.extraction.vendors.screener.screener_financials_models import Section
from equity_os.interface.commands.companies import onboard_cli
from equity_os.interface.entry.cli import main
from equity_os.normalisation.derivation.interval import load_rounding_policy
from equity_os.normalisation.dictionary.dictionary import load_dictionary
from equity_os.normalisation.mapping.mapping import load_mapping_set, load_normalisation_policy
from equity_os.storage.database.settings import PgRole
from equity_os.storage.raw_files.snapshot_store import DirectoryAnchor, SnapshotStore
from equity_os.storage.records.repository import EvidenceRepository

__all__ = ["cli"]


# --- stable ids (C6-C8, D3.4) -----------------------------------------------------------------


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize(
    "held", ["isin_under_other_symbol", "symbol_on_other_listing", "scrip_on_other_listing"]
)
def test_identifiers_held_elsewhere_conflict_without_new_rows(
    held: str, cli: Callable[..., int], pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """D3.4: the master ISIN under another current symbol, the symbol on another listing, or
    (an ISIN and symbol new to the store) the verified BSE scrip on another security's listing
    is IDENTITY_CONFLICT and writes no identity row."""
    if held == "isin_under_other_symbol":
        seed(pg_db, "ZZOTHER", APAR_ISIN, "ZZOTHER", "999001")
    elif held == "symbol_on_other_listing":
        seed(pg_db, "ZZOTHER", ZZ_ISIN, APAR, "999001")
    else:
        seed(pg_db, "ZZOTHER", ZZ_ISIN, "ZZOTHER", APAR_SCRIP)
    before = table_counts(pg_db)
    assert cli(APAR, write_root(tmp_path / "raw", world(APAR), APAR)) == FAILURE
    record, states = recorded(pg_db)
    assert record[1] == OC.IDENTITY_CONFLICT.value and states[U.EXCHANGE][0] == S.CONFLICT.value
    assert table_counts(pg_db) == before


@pytest.mark.pg
@pytest.mark.retained
def test_apar_on_a_seeded_database_resolves_to_its_d1a_ids(
    cli: Callable[..., int], pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """The seeded D1a layers are reused: same entity, no new identity rows."""
    entity_id = seed_apar(pg_db)
    before = table_counts(pg_db)
    assert cli(APAR, write_root(tmp_path / "raw", world(APAR), APAR)) == INCOMPLETE
    record, _ = recorded(pg_db)
    assert record[4] == entity_id and table_counts(pg_db) == before


NEW_SYMBOL, NEW_SCRIP, CHANGED_ON = (
    "ZZAPAR",
    "999001",  # SYNTHETIC scrip
    date(2026, 6, 1),
)  # between the Mar (28-May) and Jun (24-Jul) filings


@pytest.mark.pg
@pytest.mark.retained
def test_reonboarding_after_isin_and_symbol_change_keeps_ids(
    cli: Callable[..., int], pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """C6-C8: after an ISIN_CHANGE and NSE and BSE SYMBOL_CHANGEs between the two filings,
    fixtures carrying the new values (the older filing still the old ones, its ScripCode the
    old scrip) re-onboard to the same entity, security and listing ids; Upstox verifies against
    the new ISIN's rows."""
    assert cli(APAR, write_root(tmp_path / "raw1", world(APAR), APAR)) == INCOMPLETE
    first, states = recorded(pg_db)
    assert {u for u, (s, _) in states.items() if s == S.VERIFIED} == VERIFIED_FIVE
    before = table_counts(pg_db)
    new_isin = synthetic_isin("INE372A0199")
    db_event(
        pg_db,
        IdentityEventKind.ISIN_CHANGE,
        CHANGED_ON,
        (IdentifierNamespace.ISIN, APAR_ISIN),
        new_isin,
    )
    db_event(
        pg_db,
        IdentityEventKind.SYMBOL_CHANGE,
        CHANGED_ON,
        (IdentifierNamespace.NSE_SYMBOL, APAR),
        NEW_SYMBOL,
    )
    db_event(
        pg_db,
        IdentityEventKind.SYMBOL_CHANGE,
        CHANGED_ON,
        (IdentifierNamespace.BSE_SCRIP, APAR_SCRIP),
        NEW_SCRIP,
    )
    served = world(APAR)
    rename(served, APAR_ISIN, new_isin, keep=(MAR,))
    rename(served, APAR, NEW_SYMBOL, keep=(MAR,))
    rename(served, APAR_SCRIP, NEW_SCRIP, keep=(MAR,))
    assert cli(NEW_SYMBOL, write_root(tmp_path / "raw2", served, NEW_SYMBOL)) == INCOMPLETE
    records = rows(pg_db, "SELECT outcome, entity_id FROM eqos.onboarding_records ORDER BY id")
    assert records[-1] == (OC.PARTIAL.value, first[4])
    (latest,) = rows(pg_db, "SELECT id FROM eqos.onboarding_records ORDER BY id DESC LIMIT 1")
    upstox = rows(
        pg_db,
        "SELECT state FROM eqos.namespace_verifications "
        "WHERE onboarding_record_id = %s AND unit = 'UPSTOX'",
        latest[0],
    )
    assert upstox == [(S.VERIFIED.value,)]
    assert table_counts(pg_db) == before
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        old = {v.value for v in latest_slice(conn, CHANGED_ON - timedelta(days=1))}
        new = {v.value for v in latest_slice(conn)}
    assert {APAR_ISIN, APAR, APAR_SCRIP} <= old and {new_isin, NEW_SYMBOL, NEW_SCRIP} <= new
    assert APAR not in new and APAR_SCRIP not in new


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("variant", ["no_event", "post_change_filing_with_old_symbol"])
def test_discovery_across_a_change_needs_the_event_and_the_new_value(
    variant: str, cli: Callable[..., int], pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """C8: without the recorded event the new symbol conflicts; with it, a post-change filing
    still carrying the old symbol conflicts (expected identity at each filing date)."""
    assert cli(APAR, write_root(tmp_path / "raw1", world(APAR), APAR)) == INCOMPLETE
    served = world(APAR)
    if variant == "no_event":
        rename(served, APAR, NEW_SYMBOL, keep=(MAR,))
    else:
        db_event(
            pg_db,
            IdentityEventKind.SYMBOL_CHANGE,
            CHANGED_ON,
            (IdentifierNamespace.NSE_SYMBOL, APAR),
            NEW_SYMBOL,
        )
        rename(served, APAR, NEW_SYMBOL, keep=(MAR, JUN))  # the Jun filing keeps the old symbol
    assert cli(NEW_SYMBOL, write_root(tmp_path / "raw2", served, NEW_SYMBOL)) == FAILURE
    (last,) = rows(pg_db, "SELECT outcome FROM eqos.onboarding_records ORDER BY id DESC LIMIT 1")
    assert last == (OC.IDENTITY_CONFLICT.value,)


@pytest.mark.pg
@pytest.mark.retained
def test_symbol_reuse_resolves_to_the_reusing_listing_and_keeps_its_key(
    cli: Callable[..., int], pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """Entity A changes ZZOLD → ZZNEW; B's listing takes ZZOLD by SYMBOL_REUSE: onboarding
    ZZOLD resolves to B under B's key. Without B, a new issuer on the once-held ZZOLD conflicts."""
    seed(pg_db, "ZZOLD", ZZ_ISIN, "ZZOLD", "999001")
    db_event(
        pg_db,
        IdentityEventKind.SYMBOL_CHANGE,
        date(2026, 7, 1),
        (IdentifierNamespace.NSE_SYMBOL, "ZZOLD"),
        "ZZNEW",
    )
    served = world(APAR)
    rename(served, APAR, "ZZOLD", keep=(MAR, JUN))  # both filings precede the reuse
    root = write_root(tmp_path / "raw", served, "ZZOLD")
    assert cli("ZZOLD", root) == FAILURE  # once held, no reuse event: conflict
    b = seed(pg_db, "ZZB", APAR_ISIN, APAR, APAR_SCRIP)
    db_event(
        pg_db,
        IdentityEventKind.SYMBOL_REUSE,
        date(2026, 8, 1),
        (IdentifierNamespace.NSE_SYMBOL, APAR),
        "ZZOLD",
    )
    assert cli("ZZOLD", root) == INCOMPLETE
    (last,) = rows(
        pg_db,
        "SELECT r.outcome, r.entity_id, e.entity_key FROM eqos.onboarding_records r "
        "JOIN eqos.reporting_entities e ON e.id = r.entity_id ORDER BY r.id DESC LIMIT 1",
    )
    assert last == (OC.PARTIAL.value, b, "ZZB")


@pytest.mark.pg
@pytest.mark.retained
def test_new_issuer_on_an_occupied_key_gets_a_suffixed_key(
    cli: Callable[..., int], pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """The key is an internal label: an occupied key yields ``<symbol>-2``, never the occupant."""
    occupant = seed(pg_db, APAR, ZZ_ISIN, "ZZOTHER", "999001")
    assert cli(APAR, write_root(tmp_path / "raw", world(APAR), APAR)) == INCOMPLETE
    record, _ = recorded(pg_db)
    assert record[4] != occupant
    assert rows(
        pg_db, "SELECT entity_key FROM eqos.reporting_entities WHERE id = %s", record[4]
    ) == [(f"{APAR}-2",)]


# --- one transaction under the identity locks (D3.4, D4.6) -------------------------------------


Captured = list[tuple[VerificationUnit, CaptureReference]]


def _discovered(db: PgTestDatabase, tmp_path: Path) -> tuple[Discovery, Captured]:
    """Apar discovered in replay and its captures registered, not yet recorded."""
    dictionary = load_dictionary(CONFIG / "normalisation/dictionary", "v2")
    mapping_set = load_mapping_set(CONFIG / "normalisation/mappings", "v5", dictionary=dictionary)
    folder = write_root(tmp_path / "raw", world(APAR), APAR) / "gen-1"
    store = SnapshotStore(tmp_path / "snapshots")
    with db.runtime_pool() as pool:
        with pool.connection() as conn:
            found = discover(APAR, replay_fetch(folder), conn, VENDOR_SURFACES, mapping_set)
        with store.prepare_ordinary_output():
            return found, store_captures(store, EvidenceRepository(pool), found.captures)


def _record_while_held(
    db: PgTestDatabase, found: Discovery, refs: Captured, holder: Callable[[Any], object]
) -> Recorded | Exception:
    """``record`` on a second connection while ``holder`` runs uncommitted on the first; the
    second must wait on the identity locks until the first commits."""
    outcome: list[Recorded | Exception] = []

    def second() -> None:
        with psycopg.connect(db.conninfo(PgRole.RUNTIME)) as conn:
            try:
                outcome.append(record(conn, found, refs))
            except OnboardingAbortError as error:
                outcome.append(error)

    with psycopg.connect(db.conninfo(PgRole.RUNTIME)) as first, first.transaction():
        holder(first)
        racer = threading.Thread(target=second)
        racer.start()
        racer.join(timeout=1.0)
        assert racer.is_alive()  # blocked on the lock, not racing past it
    racer.join(timeout=30.0)
    (result,) = outcome
    return result


@pytest.mark.pg
@pytest.mark.retained
def test_concurrent_first_onboardings_share_one_new_issuer(
    pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """Two first onboardings of one new issuer: the second waits, re-resolves and reuses the
    first's new stable ids instead of inserting a second security for the ISIN."""
    found, refs = _discovered(pg_db, tmp_path)
    assert found.entity_id is None
    first: list[Recorded] = []
    second = _record_while_held(
        pg_db, found, refs, lambda conn: first.append(record(conn, found, refs))
    )
    assert isinstance(second, Recorded) and second.entity_id == first[0].entity_id
    assert table_counts(pg_db) == (1, 1, 2)
    assert count(pg_db, "onboarding_records") == 2


@pytest.mark.pg
@pytest.mark.retained
def test_an_identity_event_during_onboarding_refuses_the_stale_resolution(
    pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """A SYMBOL_CHANGE committed between discovery and recording moves the symbol off the
    resolved listing: recording waits for it, re-resolves, and refuses (no record) rather than
    admit against the stale entity."""
    entity_id = seed_apar(pg_db)
    found, refs = _discovered(pg_db, tmp_path)
    assert found.entity_id == entity_id
    change = (IdentifierNamespace.NSE_SYMBOL, APAR)
    result = _record_while_held(
        pg_db,
        found,
        refs,
        lambda conn: event(conn, IdentityEventKind.SYMBOL_CHANGE, CHANGED_ON, change, NEW_SYMBOL),
    )
    assert isinstance(result, OnboardingAbortError)
    assert count(pg_db, "onboarding_records") == 0


def _new_issuer_with_history(conn: Any) -> None:
    """A concurrent creation of Apar whose symbol was ``ZZOLD`` until a SYMBOL_CHANGE between
    the two filing dates, ending at today's APARINDS."""
    seed_on(conn, "ZZRACE", APAR_ISIN, "ZZOLD", APAR_SCRIP)
    event(
        conn,
        IdentityEventKind.SYMBOL_CHANGE,
        CHANGED_ON,
        (IdentifierNamespace.NSE_SYMBOL, "ZZOLD"),
        APAR,
    )


def _history_rewritten(conn: Any) -> None:
    """Apar's symbol was ``ZZOLD`` around the Mar filing date; its current symbol is unchanged."""
    symbol = IdentifierNamespace.NSE_SYMBOL
    event(conn, IdentityEventKind.SYMBOL_CHANGE, date(2026, 5, 1), (symbol, APAR), "ZZOLD")
    event(conn, IdentityEventKind.SYMBOL_CHANGE, CHANGED_ON, (symbol, "ZZOLD"), APAR)


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("existing", [False, True])
def test_a_dated_identity_change_during_onboarding_refuses_the_older_filing(
    existing: bool, pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """D3.4/C8 under the locks: the owner resolved at recording (created concurrently, or the
    existing one) holds today's values but held another symbol at the Mar filing's date, so
    that filing conflicts — recording refuses (no record) instead of reusing the owner."""
    if existing:
        seed_apar(pg_db)
    found, refs = _discovered(pg_db, tmp_path)
    assert all(
        state == S.VERIFIED for state, _ in (found.states[U.EXCHANGE], found.states[U.XBRL_ENTITY])
    )
    holder = _history_rewritten if existing else _new_issuer_with_history
    result = _record_while_held(pg_db, found, refs, holder)
    assert isinstance(result, OnboardingAbortError)
    assert count(pg_db, "onboarding_records") == 0


# --- the insertion-boundary gate through both real writers ------------------------------------


def _writers(db: PgTestDatabase, tmp_path: Path, snapshots: Path) -> dict[str, Callable[[], Any]]:
    """Ingest the Jun XBRL instance and each discovery capture through the real writers."""
    dictionary = load_dictionary(CONFIG / "normalisation/dictionary", "v2")
    mapping_set = load_mapping_set(CONFIG / "normalisation/mappings", "v5", dictionary=dictionary)
    policy = load_normalisation_policy(CONFIG / "normalisation/normalisation_policy" / "v1.yaml")
    rounding = load_rounding_policy(CONFIG / "normalisation/rounding_policy" / "v1.yaml")
    (entity_id,) = rows(db, "SELECT id FROM eqos.reporting_entities")[0]
    (jun,) = [item for item in world(APAR) if JUN in item["url"]]
    inputs, store = tmp_path / "inputs", tmp_path / "store"
    (inputs / "nse").mkdir(parents=True)
    store.mkdir(mode=0o700)
    (inputs / "nse" / "jun.xml").write_bytes(jun["body"])
    intake = RetainedIntake(
        bindings=(
            RetainedCaptureBinding(
                representation=Representation.XBRL,
                source_id="nse-indas-xbrl-consolidated",
                relative_path=Path("nse") / "jun.xml",
                expected_sha256=hashlib.sha256(jun["body"]).hexdigest(),
                filed_at_raw="24-Jul-2026 18:33:13",
            ),
        ),
        retrieval_manifest_sha256="0" * 64,
        issuer_config_sha256=None,
        authority_ref="A05-DECISION-004",
        rights=INTAKE_RIGHTS,
        store_anchor=DirectoryAnchor(store),
        input_anchor=DirectoryAnchor(inputs),
    )

    def vendor(surface: str) -> Any:
        (key, capture_id) = rows(
            db, "SELECT request_key, capture_id FROM eqos.capture_refs WHERE surface = %s", surface
        )[0]
        source = rows(db, "SELECT source_id FROM eqos.capture_refs WHERE surface = %s", surface)[0][
            0
        ]

        def extract(body: bytes, *, capture: Any, record: Any, extractor_version: str) -> Any:
            return vendor_screener.extract_screener_page(
                body,
                capture=capture,
                binding=screener_binding(APAR),
                basis=Basis.CONSOLIDATED,
                section=Section.QUARTERS,
                extractor_version=extractor_version,
            )

        with db.runtime_pool() as pool:
            return ingest_vendor(
                VendorIngestRequest(
                    source_id=source,
                    surface=surface,
                    request_key=key,
                    capture_id=capture_id,
                    representation=Representation.HTML,
                    entity_id=entity_id,
                    period_end=date(2026, 6, 30),
                    basis=Basis.CONSOLIDATED,
                    framework=AccountingFramework.IND_AS,
                ),
                extract=extract,
                extractor_version=vendor_screener.EXTRACTOR_VERSION,
                snapshot_store=SnapshotStore(snapshots),
                repository=EvidenceRepository(pool),
                dictionary=dictionary,
                mapping_set=mapping_set,
                policy=policy,
                rounding_policy=rounding,
                fiscal_year_end_month=3,
            )

    def first_party() -> Any:
        with db.runtime_pool() as pool:
            return ingest_first_party(
                intake=intake,
                catalog=apar_catalog(),
                snapshot_store=SnapshotStore(store),
                repository=EvidenceRepository(pool),
                dictionary=dictionary,
                mapping_set=mapping_set,
                policy=policy,
                entity_id=entity_id,
                basis=Basis.CONSOLIDATED,
                framework=AccountingFramework.IND_AS,
                family=FilingFamily.FINANCIAL_RESULTS,
                reporting_period_end=date(2026, 6, 30),
                pdf_specs=None,
            )

    return {
        "xbrl": first_party,
        "screener_page": lambda: vendor("SCREENER_FINANCIALS"),
        "screener_search": lambda: vendor("SCREENER_SEARCH"),
        "equity_l": lambda: vendor("EQUITY_L"),
    }


@pytest.mark.pg
@pytest.mark.retained
def test_gate_refuses_conflicted_and_identity_captures_and_admits_partial_ones(
    cli: Callable[..., int],
    pg_db: PgTestDatabase,
    pg_template: PgTestDatabase,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D4.5: EXCHANGE, XBRL_ENTITY and SCREENER verify, then Tijori conflicts: the verified XBRL
    instance and Screener page are refused by both real writers (nothing stored). In a fresh
    database the same bytes under a PARTIAL record are admitted; an IDENTITY capture never is."""
    seed_apar(pg_db)
    served = world(APAR)
    edit(served, "financials/", b'"symbol": "APARINDS"', b'"symbol": "ZZAPAR"')
    root = write_root(tmp_path / "raw", served, APAR)
    assert cli(APAR, root) == FAILURE
    _, states = recorded(pg_db)
    assert {u for u, (s, _) in states.items() if s == S.VERIFIED} == {
        U.EXCHANGE,
        U.XBRL_ENTITY,
        U.SCREENER,
    }
    writers = _writers(pg_db, tmp_path / "a", tmp_path / "snapshots")
    for name in ("xbrl", "screener_page"):
        with pytest.raises(IneligibleCaptureError):
            writers[name]()
    assert evidence_counts(pg_db) == (0, 0) and count(pg_db, "acquisition_attempts") == 0

    with fresh_db(pg_template) as db:
        for name, value in db.cli_env().items():
            monkeypatch.setenv(name, value)
        seed_apar(db)
        clean = write_root(tmp_path / "clean", world(APAR), APAR)
        assert (
            main(
                [
                    "onboard",
                    APAR,
                    "--raw-root",
                    str(clean),
                    "--snapshot-root",
                    str(tmp_path / "snap2"),
                ]
            )
            == INCOMPLETE
        )
        writers = _writers(db, tmp_path / "b", tmp_path / "snap2")
        assert writers["xbrl"]().package_id is not None
        admitted = rows(  # onboarding's own ingest of the verified page (D5)
            db,
            "SELECT count(*) FROM eqos.occurrences o JOIN eqos.capture_refs c "
            "ON c.id = o.capture_ref_id WHERE c.surface = 'SCREENER_FINANCIALS'",
        )
        assert admitted[0][0] > 0
        before = evidence_counts(db)
        with pytest.raises(IneligibleCaptureError):
            writers["screener_search"]()
        with pytest.raises((IneligibleCaptureError, KeyError)):
            writers["equity_l"]()
        assert evidence_counts(db) == before


@pytest.mark.pg
@pytest.mark.retained
def test_a_corrected_second_attempt_over_refused_bytes_fails_cleanly(
    cli: Callable[..., int],
    pg_db: PgTestDatabase,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """D4.5 at the command boundary: attempt 1 verifies the XBRL instances, then Tijori
    conflicts; attempt 2 corrects Tijori over the same XBRL bytes and is admitted (PARTIAL), but
    those bytes stay ineligible, so its ingest is refused: exit 5, nothing stored, and the
    refusal's identifying message is not echoed."""
    seed_apar(pg_db)
    served = world(APAR)
    edit(served, "financials/", b'"symbol": "APARINDS"', b'"symbol": "ZZAPAR"')
    assert cli(APAR, write_root(tmp_path / "raw1", served, APAR)) == FAILURE
    capsys.readouterr()
    assert cli(APAR, write_root(tmp_path / "raw2", world(APAR), APAR)) == FAILURE
    records = rows(pg_db, "SELECT outcome FROM eqos.onboarding_records ORDER BY id")
    assert records == [(OC.IDENTITY_CONFLICT.value,), (OC.PARTIAL.value,)]
    assert evidence_counts(pg_db) == (0, 0)
    logs = capsys.readouterr()
    assert "IneligibleCaptureError" in logs.out + logs.err
    assert "not eligible" not in logs.out + logs.err


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("later", ["refused_record", "symbol_event_before_publication"])
def test_a_previously_extracted_filing_is_rechecked_before_reuse(
    later: str, cli: Callable[..., int], pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """D4.5/C8 on reuse: the Jun instance is ingested (COMPLETE) before anything links its
    bytes. Later an onboarding conflict links the same bytes to a refused record, or a symbol
    change is recorded effective before the filing's publication; re-ingesting the capture is
    then refused before its cached generation is reused, and nothing stored changes."""
    seed_apar(pg_db)
    xbrl = _writers(pg_db, tmp_path / "a", tmp_path / "snapshots")["xbrl"]
    assert xbrl().package_id is not None
    before = evidence_counts(pg_db), count(pg_db, "acquisition_attempts")
    assert before[0][0] > 0
    if later == "refused_record":
        served = world(APAR)
        edit(served, "financials/", b'"symbol": "APARINDS"', b'"symbol": "ZZAPAR"')
        assert cli(APAR, write_root(tmp_path / "raw", served, APAR)) == FAILURE
        refusal: type[Exception] = IneligibleCaptureError
    else:
        nse = (IdentifierNamespace.NSE_SYMBOL, APAR)
        db_event(pg_db, IdentityEventKind.SYMBOL_CHANGE, CHANGED_ON, nse, NEW_SYMBOL)
        refusal = IngestError
    with pytest.raises(refusal):
        xbrl()
    assert (evidence_counts(pg_db), count(pg_db, "acquisition_attempts")) == before


@pytest.mark.parametrize("error", [IneligibleCaptureError, IngestError])
def test_an_ingest_refusal_exits_five_naming_only_its_type(
    error: type[Exception],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A refusal raised during ingest (an ineligible capture, or a cached generation failing its
    filing-date recheck after a concurrent identity event) is a clean FAILURE, not a crash, and
    its identifying message is not echoed."""

    def refuse(_: object) -> int:
        raise error("ISSUER-SPECIFIC DETAIL")

    monkeypatch.setattr(onboard_cli, "_onboard", refuse)
    code = onboard_cli.dispatch_onboard_command(
        SimpleNamespace(command=onboard_cli.ONBOARD_COMMAND)
    )
    logs = capsys.readouterr()
    assert code == FAILURE
    assert error.__name__ in logs.out + logs.err
    assert "ISSUER-SPECIFIC DETAIL" not in logs.out + logs.err
