"""Shared fixtures for ``tests/equity_os``.

``pytest_plugins`` is not allowed in a non-root conftest, so the PostgreSQL
fixtures are imported explicitly; any standalone ``pytest <file>`` collects them.
"""

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from pg_support import PgTestDatabase, pg_db, pg_template

from equity_os.storage.facts.fact_store import FactStore, FactStoreLike
from equity_os.storage.facts.pg_fact_store import PgFactStore, create_native_store

__all__ = ["open_store", "pg_db", "pg_template", "store"]

StoreOpener = Callable[[], FactStoreLike]


@pytest.fixture(scope="session", autouse=True)
def _eager_worker_basetemp(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Create this worker's temp root at session start (eqos-1ir4).

    xdist workers otherwise create ``popen-gwN`` lazily, changing the shared
    ``pytest-NNN`` directory while another worker's approved-config read
    (``load_approved_config``) refuses on any ancestor ctime change.
    """
    tmp_path_factory.getbasetemp()


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
