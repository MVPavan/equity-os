"""What one retained capture is, independent of where it is stored.

A capture is evidence of an attempt: the request identity that was asked, the
moment it was asked, what the vendor answered, and the sha256 of the bytes that
came back. The record is the primary key of the retained tree, so the id is
*derived* — from the retrieval instant and the body digest — rather than
assigned, which makes a mistyped or hand-set id unconstructible and two attempts
unable to collide silently.

A request identity is stored and read back verbatim, so it may never carry a
credential: a subscriber session's cookie or CSRF token inside a capture would
turn the whole retained tree into replayable credentials at rest. Both the
parameter names and the shape of their values are refused here, at construction,
rather than filtered later by whoever writes the capture.

This module is the bottom of the acquisition stack: every lane imports it, so it
imports no lane back.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Annotated, Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from fundamentals.contracts.acquisition_outcome import OutcomeRecord

SCHEMA_VERSION = 1

SHA256_PATTERN = r"^[0-9a-f]{64}$"
Sha256 = Annotated[str, StringConstraints(pattern=SHA256_PATTERN)]

# A request key is a directory name in the retained tree, so its alphabet is the
# one a directory name may safely use, and the two relative components are
# refused outright: "." and ".." pass the alphabet yet name another directory.
REQUEST_KEY_PATTERN = r"^[A-Za-z0-9._\-]+$"
RELATIVE_COMPONENTS = frozenset({".", ".."})

CAPTURE_ID_PATTERN = r"^\d{8}T\d{6}\.\d{6}Z-([0-9a-f]{12}|nobody)$"
CAPTURE_ID_TIME_FORMAT = "%Y%m%dT%H%M%S.%fZ"
CAPTURE_ID_DIGEST_LENGTH = 12
NO_BODY_SUFFIX = "nobody"

# Parameter names that are credentials wherever they appear, and the shape of an
# opaque bearer or session value: 40 or more characters of unbroken token
# alphabet is not a basis, a year or a symbol.
SECRET_PARAMETER_NAMES = frozenset(
    {
        "cookie",
        "sessionid",
        "csrfmiddlewaretoken",
        "csrftoken",
        "authorization",
        "token",
        "access_token",
        "api_key",
        "apikey",
        "password",
    }
)
SECRET_VALUE_PATTERN = r"^(Bearer\s+)?[A-Za-z0-9_\-]{40,}$"
_SECRET_VALUE_RE = re.compile(SECRET_VALUE_PATTERN)

A05_DECISION_005 = "A05-DECISION-005"

SECRET_NAME_REFUSED = "request parameter name is a credential: {name}"
SECRET_VALUE_REFUSED = "request parameter {name} carries a credential-shaped value"
TRAVERSING_REQUEST_KEY = "request key must name one directory, not a relative path: {key}"
NAIVE_RETRIEVED_AT = "retrieved_at must be an aware UTC datetime"
NON_UTC_RETRIEVED_AT = "retrieved_at must be UTC, not offset {offset}"
NO_AUTHORITY_REF = "a retained capture must cite at least one authority reference"
CAPTURE_ID_NOT_DERIVED = "capture_id must be {expected}, derived from the capture itself"

_ZERO_OFFSET = timedelta(0)
_JSON_SEPARATORS = (",", ":")


class SnapshotError(Exception):
    """Base of every refusal the snapshot contract and store raise."""


class CaptureConflictError(SnapshotError):
    """A different capture already occupies the path being published."""


class IntegrityError(SnapshotError):
    """Bytes on disk do not match the digest the record states."""


class UnsafePathError(SnapshotError):
    """A path component escapes the store root or is a symlink."""


class MissingSnapshotError(SnapshotError):
    """The requested capture, or its body, is not retained."""


class SnapshotIOError(SnapshotError):
    """The retained tree could not be read or written."""


class SecretParameterError(SnapshotError, ValueError):
    """A request parameter carries a credential and may not be retained."""


def canonical_json(payload: Any) -> str:
    """One canonical JSON text for a dumped model: sorted keys, no padding."""
    return json.dumps(payload, sort_keys=True, separators=_JSON_SEPARATORS)


def canonical_sha256(payload: Any) -> str:
    """The sha256 of a dumped model's canonical JSON."""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


class RequestMethod(StrEnum):
    """The HTTP method a retained request used."""

    GET = "GET"
    POST = "POST"


class RequestParameter(BaseModel):
    """One name/value pair that is part of a request's identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Annotated[str, StringConstraints(min_length=1)]
    value: str

    @field_validator("name")
    @classmethod
    def _refuse_credential_name(cls, name: str) -> str:
        """Refuse a parameter whose name is a credential in any casing."""
        if name.strip().lower() in SECRET_PARAMETER_NAMES:
            raise SecretParameterError(SECRET_NAME_REFUSED.format(name=name))
        return name

    @model_validator(mode="after")
    def _refuse_credential_value(self) -> Self:
        """Refuse an opaque token value; the value itself is never echoed."""
        if _SECRET_VALUE_RE.match(self.value):
            raise SecretParameterError(SECRET_VALUE_REFUSED.format(name=self.name))
        return self


class RequestIdentity(BaseModel):
    """The route a capture came from, hashable to a stable request key."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = SCHEMA_VERSION
    source_id: Annotated[str, StringConstraints(min_length=1)]
    surface: Annotated[str, StringConstraints(min_length=1)]
    request_key: Annotated[str, StringConstraints(min_length=1, pattern=REQUEST_KEY_PATTERN)]
    method: RequestMethod = RequestMethod.GET
    parameters: tuple[RequestParameter, ...] = ()

    @field_validator("request_key")
    @classmethod
    def _refuse_relative_key(cls, request_key: str) -> str:
        """Refuse a key that names a relative directory rather than a route."""
        if request_key in RELATIVE_COMPONENTS:
            raise ValueError(TRAVERSING_REQUEST_KEY.format(key=request_key))
        return request_key

    @property
    def request_sha256(self) -> str:
        """The digest of this route, stable across constructions."""
        return canonical_sha256(self.model_dump(mode="json"))


class BlobRef(BaseModel):
    """The content-addressed body a capture retained."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: Annotated[str, StringConstraints(min_length=1)]
    content_sha256: Sha256
    byte_count: Annotated[int, Field(ge=0)]


class SnapshotUse(StrEnum):
    """What a retained capture may be used for."""

    PRIVATE_INTERNAL = "private_internal"


class Redistribution(StrEnum):
    """Whether a retained capture may leave the system."""

    PROHIBITED = "prohibited"


class SnapshotRights(BaseModel):
    """The basis on which a capture is held, and the limits of holding it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    use: SnapshotUse = SnapshotUse.PRIVATE_INTERNAL
    redistribution: Redistribution = Redistribution.PROHIBITED
    authority_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _demand_authority(self) -> Self:
        """Refuse a retained document with no stated basis for holding it."""
        if not self.authority_refs:
            raise ValueError(NO_AUTHORITY_REF)
        return self


class CaptureRecord(BaseModel):
    """One sealed attempt: what was asked, when, what came back, and under what basis."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = SCHEMA_VERSION
    capture_id: Annotated[str, StringConstraints(pattern=CAPTURE_ID_PATTERN)]
    request: RequestIdentity
    retrieved_at: datetime
    http_status: int | None
    media_type: str | None
    content_encoding: str | None
    body: BlobRef | None
    outcome: OutcomeRecord
    rights: SnapshotRights

    @field_validator("retrieved_at")
    @classmethod
    def _demand_utc(cls, retrieved_at: datetime) -> datetime:
        """Refuse a timestamp that is ambiguous about the hour it names."""
        offset = retrieved_at.utcoffset()
        if offset is None:
            raise ValueError(NAIVE_RETRIEVED_AT)
        if offset != _ZERO_OFFSET:
            raise ValueError(NON_UTC_RETRIEVED_AT.format(offset=offset))
        return retrieved_at

    @model_validator(mode="after")
    def _demand_derived_id(self) -> Self:
        """Refuse an id that is not the one this capture derives."""
        expected = derive_capture_id(self.retrieved_at, self.body)
        if self.capture_id != expected:
            raise ValueError(CAPTURE_ID_NOT_DERIVED.format(expected=expected))
        return self

    @property
    def record_sha256(self) -> str:
        """The digest of this record, over its canonical JSON."""
        return canonical_sha256(self.model_dump(mode="json"))

    @classmethod
    def make(
        cls,
        request: RequestIdentity,
        retrieved_at: datetime,
        http_status: int | None,
        media_type: str | None,
        content_encoding: str | None,
        body: BlobRef | None,
        outcome: OutcomeRecord,
        rights: SnapshotRights,
    ) -> Self:
        """Seal one capture, deriving its id from the instant and the body digest."""
        return cls(
            capture_id=derive_capture_id(retrieved_at, body),
            request=request,
            retrieved_at=retrieved_at,
            http_status=http_status,
            media_type=media_type,
            content_encoding=content_encoding,
            body=body,
            outcome=outcome,
            rights=rights,
        )


def derive_capture_id(retrieved_at: datetime, body: BlobRef | None) -> str:
    """The only id a capture may carry: its retrieval instant and body digest."""
    suffix = NO_BODY_SUFFIX if body is None else body.content_sha256[:CAPTURE_ID_DIGEST_LENGTH]
    return f"{retrieved_at.strftime(CAPTURE_ID_TIME_FORMAT)}-{suffix}"
