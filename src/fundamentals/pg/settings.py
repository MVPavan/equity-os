"""Connection settings for the compose PostgreSQL service (data spec §6).

Read once, at a composition root, from the untracked ``.env`` and the process
environment; business modules receive a pool or a connection, never settings.
Passwords are ``SecretStr`` and validation errors hide their input, so a missing
field can never echo a credential into a log or a test report.
"""

from __future__ import annotations

from enum import StrEnum

from psycopg.conninfo import make_conninfo
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

MIGRATOR_ROLE_NAME = "eqos_migrator"
RUNTIME_ROLE_NAME = "eqos_runtime"
SCHEMA_NAME = "eqos"

ENV_PREFIX = "EQOS_PG_"
ENV_FILE = ".env"
APPLICATION_NAME = "equity-os"
_STATEMENT_TIMEOUT_OPTION = "-c statement_timeout={ms}"


class PgRole(StrEnum):
    """Which of the three database roles a connection authenticates as."""

    ADMIN = "ADMIN"
    MIGRATOR = "MIGRATOR"
    RUNTIME = "RUNTIME"


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

    def conninfo(self, role: PgRole, *, dbname: str | None = None) -> str:
        """A libpq connection string for one role, with both timeouts applied."""
        user, password = self._credentials(role)
        return make_conninfo(
            host=self.host,
            port=self.port,
            dbname=dbname if dbname is not None else self.db,
            user=user,
            password=password.get_secret_value(),
            connect_timeout=self.connect_timeout_s,
            options=_STATEMENT_TIMEOUT_OPTION.format(ms=self.statement_timeout_ms),
            application_name=APPLICATION_NAME,
        )

    def _credentials(self, role: PgRole) -> tuple[str, SecretStr]:
        """The login name and password for one role."""
        if role is PgRole.ADMIN:
            return self.user, self.password
        if role is PgRole.MIGRATOR:
            return MIGRATOR_ROLE_NAME, self.migrator_password
        return RUNTIME_ROLE_NAME, self.runtime_password
