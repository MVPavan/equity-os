"""Shared fixtures of the D9 retention tests (plan D9, verification cases).

Captures written here are SYNTHETIC registrations (random hashes, no stored bytes) unless a test
publishes real bytes through an intake path.
"""

from __future__ import annotations

import shutil
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import psycopg
import pytest
from pg_support import MIGRATIONS_DIR, PgTestDatabase, create_database, drop_database, mint_name

from fundamentals.contracts.evidence import CaptureReference
from fundamentals.pg.migrations import apply_migrations
from fundamentals.pg.settings import PgRole

# The tables the retention migrations add; each D9 migration extends this in its own change.
RETENTION_TABLES = frozenset({"retention_classes", "capture_addresses", "licence_ends"})
FIRST_RETENTION_MIGRATION = "0027_retention_classes.sql"
CLASS_OF = (
    "SELECT r.source_id, r.surface, c.retention_class, c.cause FROM eqos.capture_refs r "
    "LEFT JOIN eqos.retention_classes c ON c.capture_ref_id = r.id WHERE r.id = %s"
)
ADDRESS_OF = "SELECT url FROM eqos.capture_addresses WHERE capture_ref_id = %s"


def synthetic(source_id: str, surface: str) -> CaptureReference:
    """SYNTHETIC: an unregistered capture reference with random hashes, registered now."""
    now = datetime.now(UTC)
    return CaptureReference(
        capture_ref_id=None,
        source_id=source_id,
        surface=surface,
        request_key=uuid.uuid4().hex,
        capture_id=uuid.uuid4().hex,
        blob_sha256=uuid.uuid4().hex * 2,
        record_sha256=uuid.uuid4().hex * 2,
        registered_at=now,
        first_seen_at=now,
    )


def class_of(conn: psycopg.Connection, capture_ref_id: int | None) -> tuple[str | None, str | None]:
    """A capture's stored class and cause, ``(None, None)`` when unclassified."""
    row = conn.execute(CLASS_OF, (capture_ref_id,)).fetchone()
    assert row is not None
    return row[2], row[3]


def address_of(conn: psycopg.Connection, capture_ref_id: int | None) -> str | None:
    """A capture's recorded address, if any."""
    row = conn.execute(ADDRESS_OF, (capture_ref_id,)).fetchone()
    return None if row is None else str(row[0])


@pytest.fixture
def pre_retention_db(
    pg_template: PgTestDatabase, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[tuple[PgTestDatabase, psycopg.Connection]]:
    """A database migrated up to, not including, 0027, with an open migrator connection; the
    caller applies the rest through :func:`finish_migrations`."""
    settings = pg_template.settings
    name = mint_name(settings)
    create_database(settings, name)
    earlier = tmp_path_factory.mktemp("pre_retention_migrations")
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.name < FIRST_RETENTION_MIGRATION:
            shutil.copy(path, earlier / path.name)
    database = pg_template.model_copy(update={"dbname": name})
    try:
        with psycopg.connect(
            settings.conninfo(PgRole.MIGRATOR, dbname=name), autocommit=True
        ) as migrator:
            apply_migrations(migrator, earlier)
            yield database, migrator
    finally:
        drop_database(settings, name)


def finish_migrations(migrator: psycopg.Connection) -> None:
    """Apply every remaining migration, 0027 included."""
    apply_migrations(migrator, MIGRATIONS_DIR)
