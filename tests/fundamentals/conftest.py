"""Shared fixtures for ``tests/fundamentals``.

``pytest_plugins`` is not allowed in a non-root conftest, so the PostgreSQL
fixtures are imported explicitly; any standalone ``pytest <file>`` collects them.
"""

from pg_support import pg_db, pg_template

__all__ = ["pg_db", "pg_template"]
