"""Logins from 0600 credential files outside every runtime config (plan D3, D2; bead eqos-z53).

Each file, ``<secrets_dir>/<name>.login``, holds one line ``<login>:<password>``: the group-role
logins (panel, owner, reader, purge), the admin (``eqos_admin``) and the migrator
(``eqos_migrator``). Only the commands that need a role read its file, at the CLI edge; runtime
commands read none. Errors name the path only, never the contents.
"""

from __future__ import annotations

import os
import re
import stat
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, SecretStr

from equity_os.storage.database.settings import GROUP_ROLES, MIGRATOR_ROLE_NAME, PgRole, PgSettings

SECRETS_DIR_ENV = "EQOS_SECRETS_DIR"
DEFAULT_SECRETS_DIR = "~/.secrets"
LOGIN_SUFFIX = ".login"
LOGIN_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*$")
ADMIN_FILE_NAME = "eqos_admin"
CREDENTIAL_FILES: dict[PgRole, str] = {
    **GROUP_ROLES,
    PgRole.ADMIN: ADMIN_FILE_NAME,
    PgRole.MIGRATOR: MIGRATOR_ROLE_NAME,
}


class RoleLogin(BaseModel):
    """A member login of a group role and its password."""

    model_config = ConfigDict(frozen=True)

    login: str
    password: SecretStr


class RoleSecretError(ValueError):
    """A credential file is unsafe or malformed."""


class MissingRoleSecretError(RoleSecretError):
    """A credential file does not exist."""


def secrets_dir(environ: Mapping[str, str]) -> Path:
    """The credential directory: ``EQOS_SECRETS_DIR``, else ``~/.secrets``."""
    return Path(environ.get(SECRETS_DIR_ENV, DEFAULT_SECRETS_DIR)).expanduser()


def load_login(role: PgRole, secrets_dir: Path) -> RoleLogin:
    """The login and password for ``role`` from its credential file, or refuse.

    Refuses a missing file, a symlink or other non-regular file, a file not owned by this
    process's user, any group or other permission bit, and anything but one well-formed line.
    The open never blocks (a FIFO is refused, not waited on), and the file is judged by its open
    descriptor before any read.
    """
    path = secrets_dir / f"{CREDENTIAL_FILES[role]}{LOGIN_SUFFIX}"
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError as missing:
        raise MissingRoleSecretError(f"credential file missing: {path}") from missing
    except OSError as unreadable:
        raise RoleSecretError(f"credential file unsafe: {path}") from unreadable
    with os.fdopen(descriptor, encoding="utf-8") as handle:
        status = os.fstat(handle.fileno())
        if (
            not stat.S_ISREG(status.st_mode)
            or status.st_uid != os.getuid()
            or status.st_mode & (stat.S_IRWXG | stat.S_IRWXO)
        ):
            raise RoleSecretError(f"credential file unsafe: {path}")
        text = handle.read().removesuffix("\n")
    login, separator, password = text.partition(":")
    if not separator or not password or "\n" in password or not LOGIN_PATTERN.match(login):
        raise RoleSecretError(f"credential file malformed: {path}")
    return RoleLogin(login=login, password=SecretStr(password))


class PrivilegedPgSettings(PgSettings):
    """``PgSettings`` plus the admin and migrator logins, for bootstrap, migrate, backup, restore,
    test-database lifecycle and purge's final backup only."""

    admin: RoleLogin
    migrator: RoleLogin

    def _credentials(self, role: PgRole) -> tuple[str, SecretStr]:
        """The admin or migrator login from its credential file, else the runtime login."""
        if role is PgRole.ADMIN:
            return self.admin.login, self.admin.password
        if role is PgRole.MIGRATOR:
            return self.migrator.login, self.migrator.password
        return super()._credentials(role)


def load_privileged(environ: Mapping[str, str]) -> PrivilegedPgSettings:
    """Settings with the admin and migrator logins from the secrets directory, or refuse."""
    directory = secrets_dir(environ)
    return PrivilegedPgSettings(
        admin=load_login(PgRole.ADMIN, directory), migrator=load_login(PgRole.MIGRATOR, directory)
    )
