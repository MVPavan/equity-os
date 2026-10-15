"""Pooled PostgreSQL access with explicit connect and statement timeouts (data spec §6)."""

from __future__ import annotations

from psycopg_pool import ConnectionPool, PoolTimeout

from fundamentals.pg.role_secrets import RoleLogin
from fundamentals.pg.settings import PgRole, PgSettings

_POOL_NAME = "eqos-{role}"
_UNAVAILABLE = "PostgreSQL unreachable at {host}:{port}/{dbname} as {role} within {timeout}s"


class DatabaseUnavailableError(Exception):
    """The database did not yield a first connection within the connect timeout."""


def open_pool(
    settings: PgSettings,
    role: PgRole,
    *,
    dbname: str | None = None,
    login: RoleLogin | None = None,
) -> ConnectionPool:
    """Open a pool for one role and wait for its first connection, or refuse.

    Every pooled connection carries the connect timeout and the per-connection
    ``statement_timeout`` from the settings. The error names host, port, database
    and role only — never a credential. ``PANEL`` and ``OWNER`` need their ``login``.
    """
    target = dbname if dbname is not None else settings.db
    pool = ConnectionPool(
        conninfo=settings.conninfo(role, dbname=target, login=login),
        min_size=settings.pool_min_size,
        max_size=settings.pool_max_size,
        timeout=settings.connect_timeout_s,
        name=_POOL_NAME.format(role=role.value.lower()),
        open=False,
    )
    try:
        pool.open(wait=True, timeout=settings.connect_timeout_s)
    except PoolTimeout as exc:
        pool.close()
        raise DatabaseUnavailableError(
            _UNAVAILABLE.format(
                host=settings.host,
                port=settings.port,
                dbname=target,
                role=role.value,
                timeout=settings.connect_timeout_s,
            )
        ) from exc
    return pool
