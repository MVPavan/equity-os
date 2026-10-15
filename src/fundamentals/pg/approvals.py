"""The one gate in front of every gated mutation (plan D2, design decision 6).

An approved file is a YAML payload plus one ``approval: {reviewer, verdict, date,
payload_sha256}`` line; the payload is the file's bytes without that line. Outside a test
database, an owner authorization record must also name the database, the operation and the
approved payload's hash, and be signed by the one designated owner.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any

import psycopg
import yaml
from pydantic import BaseModel, ConfigDict

from fundamentals.pg.settings import PgSettings

TEST_DATABASE_PREFIX = "eqos_test_"
SOL_REVIEWER = "gpt-6.1-sol"
FIXTURE_REVIEWER = "test-fixture"
APPROVE_VERDICT = "APPROVE"
OWNER = "PavanMV"
APPROVAL_KEY = "approval"
DATABASE_KEY = "database"
_APPROVAL_LINE = APPROVAL_KEY.encode() + b":"
_SAFE_NAME = re.compile(r"^[a-z_][a-z0-9_]*$")


class GatedOperation(StrEnum):
    """A mutation that must pass the gate before its first write."""

    IMPORT = "IMPORT"
    CUTOVER = "CUTOVER"
    REOPEN = "REOPEN"
    ROLLBACK = "ROLLBACK"


class GateRefusal(StrEnum):
    """Why the gate refused."""

    UNAPPROVED = "UNAPPROVED"
    PAYLOAD_MISMATCH = "PAYLOAD_MISMATCH"
    WRONG_DATABASE = "WRONG_DATABASE"
    OWNER_RECORD_MISSING = "OWNER_RECORD_MISSING"
    OWNER_RECORD_MISMATCH = "OWNER_RECORD_MISMATCH"
    NOT_OWNER = "NOT_OWNER"
    REVIEWER_NOT_ALLOWED = "REVIEWER_NOT_ALLOWED"
    APPROVAL_STALE = "APPROVAL_STALE"


class GateRefusedError(Exception):
    """The gate refused an operation; nothing was written."""

    def __init__(self, reason: GateRefusal) -> None:
        """Carry the refusal reason."""
        super().__init__(reason.value)
        self.reason = reason


class Approval(BaseModel):
    """A reviewer's verdict on one payload."""

    model_config = ConfigDict(frozen=True)

    reviewer: str
    verdict: str
    date: date
    payload_sha256: str


class OwnerAuthorization(BaseModel):
    """The owner's attestation that one approved payload may run against one database."""

    model_config = ConfigDict(frozen=True)

    by: str
    date: date
    database: str
    operations: tuple[GatedOperation, ...]
    approved_payload_sha256: str


def is_test_database(name: str) -> bool:
    """Whether ``name`` is a test database: the literal prefix and a safe identifier."""
    return name.startswith(TEST_DATABASE_PREFIX) and _SAFE_NAME.match(name) is not None


def split_approval(data: bytes) -> tuple[bytes, Approval | None]:
    """The payload bytes and the one approval line's record, if exactly one is present."""
    lines = data.splitlines(keepends=True)
    marked = [line for line in lines if line.startswith(_APPROVAL_LINE)]
    payload = b"".join(line for line in lines if not line.startswith(_APPROVAL_LINE))
    if len(marked) != 1:
        return payload, None
    return payload, Approval.model_validate(yaml.safe_load(marked[0])[APPROVAL_KEY])


def load_approved(path: Path) -> tuple[bytes, Approval]:
    """The approved payload and its approval, refusing a missing line or an edited payload."""
    payload, approval = split_approval(path.read_bytes())
    if approval is None:
        raise GateRefusedError(GateRefusal.UNAPPROVED)
    if hashlib.sha256(payload).hexdigest() != approval.payload_sha256:
        raise GateRefusedError(GateRefusal.PAYLOAD_MISMATCH)
    return payload, approval


def check_approval(approval: Approval, *, database: str) -> None:
    """Refuse a non-APPROVE verdict, or a reviewer not allowed for ``database``."""
    if approval.verdict != APPROVE_VERDICT:
        raise GateRefusedError(GateRefusal.UNAPPROVED)
    allowed = {SOL_REVIEWER, FIXTURE_REVIEWER} if is_test_database(database) else {SOL_REVIEWER}
    if approval.reviewer not in allowed:
        raise GateRefusedError(GateRefusal.REVIEWER_NOT_ALLOWED)


def check_gate(
    op: GatedOperation, *, database: str, approval: Approval, owner: OwnerAuthorization | None
) -> None:
    """The pure gate rule; returns only when ``op`` may run against ``database``."""
    check_approval(approval, database=database)
    if owner is None:
        if is_test_database(database):
            return
        raise GateRefusedError(GateRefusal.OWNER_RECORD_MISSING)
    if owner.by != OWNER:
        raise GateRefusedError(GateRefusal.NOT_OWNER)
    if owner.database != database:
        raise GateRefusedError(GateRefusal.WRONG_DATABASE)
    if op not in owner.operations or owner.approved_payload_sha256 != approval.payload_sha256:
        raise GateRefusedError(GateRefusal.OWNER_RECORD_MISMATCH)


def current_database(conn: psycopg.Connection[Any]) -> str:
    """The database this connection is actually on."""
    row = conn.execute("SELECT current_database()").fetchone()
    assert row is not None
    return str(row[0])


def authorize(
    conn: psycopg.Connection[Any],
    op: GatedOperation,
    *,
    approval_path: Path,
    owner_path: Path | None,
    settings: PgSettings,
) -> bytes:
    """Gate ``op`` on the connection it will use; return the approved payload.

    The payload must also record this database's identity (name, host, port).
    """
    payload, approval = load_approved(approval_path)
    owner = (
        OwnerAuthorization.model_validate(yaml.safe_load(owner_path.read_bytes()))
        if owner_path is not None
        else None
    )
    database = current_database(conn)
    check_gate(op, database=database, approval=approval, owner=owner)
    identity = {"name": database, "host": settings.host, "port": settings.port}
    if yaml.safe_load(payload).get(DATABASE_KEY) != identity:
        raise GateRefusedError(GateRefusal.WRONG_DATABASE)
    return payload
