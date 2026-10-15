"""Panel and owner logins from 0600 credential files outside every runtime config (plan D3, D2).

Each file, ``<secrets_dir>/<group>.login``, holds one line ``<login>:<password>``. Only the
ledger commands, ``compare queue dispose`` and ``db bootstrap`` read them, at the CLI edge.
Errors name the path only, never the contents.
"""

from __future__ import annotations

import os
import re
import stat
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, SecretStr

from fundamentals.pg.settings import GROUP_ROLES, PgRole

SECRETS_DIR_ENV = "EQOS_SECRETS_DIR"
DEFAULT_SECRETS_DIR = "~/.secrets"
LOGIN_SUFFIX = ".login"
LOGIN_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*$")


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
    """
    path = secrets_dir / f"{GROUP_ROLES[role]}{LOGIN_SUFFIX}"
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
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
