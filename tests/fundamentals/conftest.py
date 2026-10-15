"""Shared fixtures for ``tests/fundamentals``.

``pytest_plugins`` is not allowed in a non-root conftest, so the PostgreSQL
fixtures are imported explicitly; any standalone ``pytest <file>`` collects them.
"""

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from pg_support import PgTestDatabase, pg_db, pg_template

from fundamentals.store.fact_store import FactStore, FactStoreLike
from fundamentals.store.pg_fact_store import PgFactStore, create_native_store

__all__ = ["open_store", "pg_db", "pg_template", "store"]

StoreOpener = Callable[[], FactStoreLike]


@pytest.fixture(params=["sqlite", pytest.param("pg", marks=pytest.mark.pg)])
def open_store(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[StoreOpener]:
    """Open fresh instances over one new backing store: a SQLite file or a native PG store."""
    if request.param == "sqlite":
        yield lambda: FactStore(tmp_path / "facts.db")
        return
    database: PgTestDatabase = request.getfixturevalue("pg_db")
    with database.runtime_pool() as pool:
        store_id = create_native_store(pool, "test")
        yield lambda: PgFactStore(pool, store_id)


@pytest.fixture
def store(open_store: StoreOpener) -> Iterator[FactStoreLike]:
    """One open fact store on each backend."""
    opened = open_store()
    yield opened
    opened.close()
