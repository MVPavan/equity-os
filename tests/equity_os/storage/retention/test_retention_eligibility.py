"""D9 Task 3: eligibility for purge (plan D9 R5, cases E1-E3).

Why: purge deletes exactly what eligibility says, irrecoverably for vendor bytes. The R5 order
(licence end over everything, coverage over holds, holds over windows), the vendor ceiling and
the month-end windows decide which originals survive; a shared blob may go only when every
capture using it may.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from coverage_support import watchlist
from evidence_support import XBRL_ONLY, Ingest, dictionary, ingest, mapping_set, policy
from pg_evidence_schema_support import _insert, _occurrence, runtime, seeded
from pg_support import PgTestDatabase
from retained_support import apar_store
from retention_support import (
    dispose,
    facts_of,
    finish_migrations,
    later,
    open_item,
    pre_retention_db,
    register,
    retention_cli,
    verdict,
    verify,
)

from equity_os.contracts.measurement.canonical import Representation
from equity_os.contracts.storage.retention import (
    CaptureFacts,
    CaptureState,
    Eligibility,
    EligibilityKind,
    EligibleBlob,
    EligibleReason,
    HoldRoot,
    RetentionClass,
)
from equity_os.storage.database.settings import PgRole
from equity_os.storage.retention.eligibility import add_months, eligibility, eligible_blobs
from equity_os.storage.retention.holds import capture_facts

__all__ = ["dictionary", "ingest", "mapping_set", "policy", "pre_retention_db", "runtime"]
__all__ += ["seeded"]

T0 = datetime(2026, 1, 31, 12, tzinfo=UTC)
KEEP = Eligibility(kind=EligibilityKind.KEEP)
ELIGIBLE, HELD = EligibilityKind.ELIGIBLE, EligibilityKind.HELD
URL = "https://nsearchives.nseindia.com/corporate/xbrl/fixture.xml"
VENDOR = {"base_class": RetentionClass.VENDOR, "vendor_bounded": True, "source_id": "tijori"}
EXCHANGE = {"base_class": RetentionClass.EXCHANGE_REFETCHABLE, "url": URL}


def _facts(**update: object) -> CaptureFacts:
    """A retained NSE identity capture registered at ``T0``, unheld, with ``update`` applied."""
    return CaptureFacts(
        capture_ref_id=1,
        source_id="nse",
        surface="EQUITY_L",
        blob_sha256="a" * 64,
        base_class=RetentionClass.IDENTITY,
        covered=False,
        vendor_bounded=False,
        registered_at=T0,
        verified_at=None,
        holds=frozenset(),
        licence_ended_at=None,
        state=CaptureState.RETAINED,
        url=None,
    ).model_copy(update=update)


def _eligible(since: datetime, reason: EligibleReason) -> Eligibility:
    return Eligibility(kind=ELIGIBLE, since=since, reason=reason)


YEAR = add_months(T0, 12)
FAR = add_months(T0, 30)
CASES = {
    "licence end over holds and coverage": (
        _facts(**VENDOR, covered=True, holds=frozenset({HoldRoot.OPEN_QUEUE_ITEM})).model_copy(
            update={"licence_ended_at": T0 + timedelta(days=1)}
        ),
        T0 + timedelta(days=2),
        _eligible(T0 + timedelta(days=1), EligibleReason.LICENCE_END),
    ),
    "coverage over holds and window": (
        _facts(**EXCHANGE, covered=True, verified_at=T0, holds=frozenset({HoldRoot.QUEUE_ITEM})),
        FAR,
        KEEP,
    ),
    "a non-vendor capture is held by any root": (
        _facts(holds=frozenset({HoldRoot.MEMORY_SUPPORT})),
        FAR,
        Eligibility(kind=HELD, held_by=frozenset({HoldRoot.MEMORY_SUPPORT})),
    ),
    "only an open queue item holds a vendor capture": (
        _facts(**VENDOR, holds=frozenset({HoldRoot.OPEN_QUEUE_ITEM, HoldRoot.MEMORY_SUPPORT})),
        FAR,
        Eligibility(kind=HELD, held_by=frozenset({HoldRoot.OPEN_QUEUE_ITEM})),
    ),
    "the vendor ceiling sets other holds aside at four quarters": (
        _facts(**VENDOR, holds=frozenset({HoldRoot.MEMORY_SUPPORT})),
        YEAR,
        _eligible(YEAR, EligibleReason.CATALOG_CEILING),
    ),
    "a vendor capture is kept until four quarters": (
        _facts(**VENDOR),
        YEAR - timedelta(microseconds=1),
        KEEP,
    ),
    "an identity capture is eligible at four quarters": (
        _facts(),
        YEAR,
        _eligible(YEAR, EligibleReason.WINDOW),
    ),
    "exchange: three months after verification, clamped to month end": (
        _facts(**EXCHANGE, verified_at=datetime(2027, 11, 30, tzinfo=UTC)),
        datetime(2028, 2, 29, tzinfo=UTC),
        _eligible(datetime(2028, 2, 29, tzinfo=UTC), EligibleReason.WINDOW),
    ),
    "an unverified exchange capture is kept": (_facts(**EXCHANGE), FAR, KEEP),
    "an address-less exchange capture is kept": (
        _facts(**EXCHANGE, verified_at=T0).model_copy(update={"url": None}),
        FAR,
        KEEP,
    ),
    "a COVERED-class capture is kept": (_facts(base_class=RetentionClass.COVERED), FAR, KEEP),
    "an unclassified capture is kept": (
        _facts(base_class=RetentionClass.UNCLASSIFIED),
        FAR,
        KEEP,
    ),
}


@pytest.mark.parametrize(("facts", "now", "expected"), CASES.values(), ids=CASES.keys())
def test_eligibility_follows_the_r5_order(
    facts: CaptureFacts, now: datetime, expected: Eligibility
) -> None:
    """E1: each R5 branch in order, the ceiling reason, month-end clamping and the
    address-less exchange capture."""
    assert eligibility(facts, now) == expected


@pytest.mark.parametrize(
    ("at", "months", "expected"),
    [
        (datetime(2026, 1, 31, tzinfo=UTC), 1, datetime(2026, 2, 28, tzinfo=UTC)),
        (datetime(2027, 11, 30, tzinfo=UTC), 3, datetime(2028, 2, 29, tzinfo=UTC)),
        (datetime(2026, 8, 31, tzinfo=UTC), 12, datetime(2027, 8, 31, tzinfo=UTC)),
        (datetime(2026, 12, 15, 9, tzinfo=UTC), 3, datetime(2027, 3, 15, 9, tzinfo=UTC)),
    ],
)
def test_windows_are_calendar_months_clamped_to_month_end(
    at: datetime, months: int, expected: datetime
) -> None:
    """E1: P4's calendar months; a day past the target month's end clamps to it."""
    assert add_months(at, months) == expected


def test_class_windows_over_real_and_synthetic_captures(
    ingest: Ingest, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """E2: Apar's retained XBRL is kept while unverified, eligible three months after a
    verifying run, kept again once the stock is covered; VENDOR and IDENTITY captures are
    eligible four quarters after registration."""
    report = ingest.run(ingest.intake(XBRL_ONLY))
    apar = ingest.capture_id(report, Representation.XBRL)
    assert report.package_id is not None
    pg_db = ingest.pg_db
    with pg_db.runtime_pool() as run_pool, pg_db.owner_pool() as owner_pool:
        with run_pool.connection() as conn:
            vendor = register(conn, "screener-subscriber", "SCREENER_FINANCIALS")
            identity = register(conn, "nse", "EQUITY_L")
            conn.commit()
            assert verdict(conn, apar) == KEEP
            verify(conn, report.package_id)
            facts = facts_of(conn, apar)
            assert facts.verified_at is not None and facts.url is not None
            expected = add_months(facts.verified_at, 3)
            assert verdict(conn, apar) == _eligible(expected, EligibleReason.WINDOW)
            for capture in (vendor, identity):
                since = add_months(facts_of(conn, capture).registered_at, 12)
                assert verdict(conn, capture) == _eligible(since, EligibleReason.WINDOW)
            conn.commit()
        pools = {PgRole.RUNTIME: run_pool, PgRole.OWNER: owner_pool}
        watchlist(pools, ingest.entity_id, apar_store(tmp_path_factory.mktemp("seed")))
        with run_pool.connection() as conn:
            assert verdict(conn, apar) == KEEP


def test_a_pre_existing_capture_is_kept_until_classified(
    pre_retention_db: tuple[PgTestDatabase, psycopg.Connection], monkeypatch: pytest.MonkeyPatch
) -> None:
    """E2: a capture registered before 0027 has no window (and the dry-run refuses) until the
    one-off classify gives it its class; then it ages like any other."""
    database, migrator = pre_retention_db
    capture = register(migrator, "nse", "EQUITY_L")
    finish_migrations(migrator)
    assert verdict(migrator, capture) == KEEP
    refused = retention_cli(monkeypatch, database, "purge", "--dry-run")
    assert refused == (2, "unclassified\tnse\tEQUITY_L\n")
    assert retention_cli(monkeypatch, database, "classify")[0] == 0
    since = add_months(facts_of(migrator, capture).registered_at, 12)
    assert verdict(migrator, capture) == _eligible(since, EligibleReason.WINDOW)


def test_a_shared_blob_goes_only_when_every_user_may(
    pg_db: PgTestDatabase, runtime: psycopg.Connection, seeded: dict[str, int]
) -> None:
    """E3: two Tijori captures share one blob; an open item on one keeps the blob, and once
    it is disposed the blob is eligible since the later of the two."""
    blob = "7" * 64
    first, second = (register(runtime, "tijori", "financials", blob=blob) for _ in range(2))
    occurrence = _insert(runtime, "occurrences", _occurrence(first, "tj-shared"))
    item = open_item(runtime, seeded["runs"], occurrence_id=occurrence)

    def shared() -> list[EligibleBlob]:
        blobs = eligible_blobs(capture_facts(runtime, {}), later())
        return [b for b in blobs if b.blob_sha256 == blob]

    assert verdict(runtime, first).kind is HELD and verdict(runtime, second).kind is ELIGIBLE
    assert shared() == []
    with psycopg.connect(pg_db.conninfo(PgRole.OWNER), autocommit=True) as owner:
        dispose(owner, item)
    (found,) = shared()
    since = max(add_months(facts_of(runtime, c).registered_at, 12) for c in (first, second))
    assert (found.capture_ref_ids, found.since) == ((first, second), since)


@pytest.mark.parametrize("ended", [False, True])
def test_vendor_surface_keep_at_48_months(ended: bool) -> None:
    """The explicit keep root survives age, but never licence end."""
    root = HoldRoot.VENDOR_SURFACE_KEEP
    facts = _facts(
        **VENDOR,
        surface="vs.chart-api",
        holds=frozenset({root}),
        licence_ended_at=T0 if ended else None,
    )
    expected = (
        _eligible(T0, EligibleReason.LICENCE_END)
        if ended
        else Eligibility(kind=HELD, held_by=frozenset({root}))
    )
    assert eligibility(facts, add_months(T0, 48)) == expected
