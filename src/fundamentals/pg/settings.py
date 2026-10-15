"""Connection settings for the compose PostgreSQL service (data spec §6).

Read once, at a composition root, from the untracked ``.env`` and the process
environment; business modules receive a pool or a connection, never settings.
Passwords are ``SecretStr`` and validation errors hide their input, so a missing
field can never echo a credential into a log or a test report.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from psycopg.conninfo import make_conninfo
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from fundamentals.pg.role_secrets import RoleLogin

MIGRATOR_ROLE_NAME = "eqos_migrator"
RUNTIME_ROLE_NAME = "eqos_runtime"
SCHEMA_NAME = "eqos"

ENV_PREFIX = "EQOS_PG_"
ENV_FILE = ".env"
APPLICATION_NAME = "equity-os"
_STATEMENT_TIMEOUT_OPTION = "-c statement_timeout={ms}"
_ROLE_OPTION = " -c role={group}"
_LOGIN_MISMATCH = "role {role} {verb} a login from a credential file"


class PgRole(StrEnum):
    """Which database role a connection authenticates as."""

    ADMIN = "ADMIN"
    MIGRATOR = "MIGRATOR"
    RUNTIME = "RUNTIME"
    PANEL = "PANEL"
    OWNER = "OWNER"
    READER = "READER"


# NOLOGIN group roles; a member login connects with ``role=<group>``, so ``current_user`` is the
# group inside the session (plan D3, D2; the reader: plan D5, D2).
GROUP_ROLES: dict[PgRole, str] = {
    PgRole.PANEL: "eqos_panel",
    PgRole.OWNER: "eqos_owner",
    PgRole.READER: "eqos_reader",
}


class PgSettings(BaseSettings):
    """Host, port, database, the three role credentials and the access limits.

    ``extra="ignore"`` because ``.env`` also holds keys only compose reads
    (``EQOS_PG_DATA_DIR``).
    """

    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX,
        env_file=ENV_FILE,
        extra="ignore",
        frozen=True,
        hide_input_in_errors=True,
    )

    host: str
    port: int
    db: str
    user: str
    password: SecretStr
    migrator_password: SecretStr
    runtime_password: SecretStr
    connect_timeout_s: int = 5
    statement_timeout_ms: int = 30000
    pool_min_size: int = 1
    pool_max_size: int = 4
    test_db_prefix: str = "eqos_test_"

    def conninfo(
        self, role: PgRole, *, dbname: str | None = None, login: RoleLogin | None = None
    ) -> str:
        """A libpq connection string for one role, with both timeouts applied.

        The ``GROUP_ROLES`` need a member ``login`` and act as their group role; the other roles
        refuse one.
        """
        group = GROUP_ROLES.get(role)
        if (group is None) != (login is None):
            verb = "needs" if login is None else "refuses"
            raise ValueError(_LOGIN_MISMATCH.format(role=role.value, verb=verb))
        options = _STATEMENT_TIMEOUT_OPTION.format(ms=self.statement_timeout_ms)
        if login is not None:
            user, password = login.login, login.password
            options += _ROLE_OPTION.format(group=group)
        else:
            user, password = self._credentials(role)
        return make_conninfo(
            host=self.host,
            port=self.port,
            dbname=dbname if dbname is not None else self.db,
            user=user,
            password=password.get_secret_value(),
            connect_timeout=self.connect_timeout_s,
            options=options,
            application_name=APPLICATION_NAME,
        )

    def _credentials(self, role: PgRole) -> tuple[str, SecretStr]:
        """The login name and password for one role."""
        if role is PgRole.ADMIN:
            return self.user, self.password
        if role is PgRole.MIGRATOR:
            return MIGRATOR_ROLE_NAME, self.migrator_password
        return RUNTIME_ROLE_NAME, self.runtime_password
