"""Sealing one Tijori financials attempt before any table parser reads it.

The financials page answers an authentication failure, an identity mix-up and a
genuine schema change with the same HTML shape, and today all three reach the
operator as one parse exception with no bytes kept to re-check them against.
This module is the gate that separates them: it classifies a body into a
capture-level :class:`OutcomeRecord` — never raising for page content — so the
outcome is sealed and committed BEFORE ``fin_tables_data`` is looked at, and a
renewable credential can never be filed as vendor drift.

Feature locks are deliberately not consulted. ``financials_locks`` is a set of
UI flags, and reading a disabled comparison toggle as a refusal would discard
tables whose data is sitting on the page.

Transport lives here only as far as the request the adapter sends and the shape
of one attempt's result (:class:`PageEnvelope`); the adapter still owns the
call, and this module never retries anything.
"""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from typing import Any, Final, NamedTuple

from pydantic import BaseModel, ConfigDict, SecretStr, field_validator

from fundamentals.contracts.acquisition_outcome import OutcomeCode, OutcomeRecord
from fundamentals.contracts.snapshot import (
    A05_DECISION_005,
    NAIVE_RETRIEVED_AT,
    NON_UTC_RETRIEVED_AT,
    BlobRef,
    CaptureRecord,
    RequestIdentity,
    RequestMethod,
    SnapshotRights,
)
from fundamentals.ingest.tijori_page import JsonScriptCollector, decode_document
from fundamentals.ingest.tijori_tables import (
    TIJORI_SOURCE_ID,
    TijoriFetchError,
    TijoriParseError,
)

FINANCIALS_SURFACE: Final = "financials"
FINANCIALS_PAGE_OUTCOME_KIND: Final = "tijori_financials_page"
FINANCIALS_PAGE_LABEL: Final = "financials"

IS_AUTH_ISLAND: Final = "is_auth"
COMPANY_DETAILS_ISLAND: Final = "company_details"
_GATE_ISLANDS: Final = (IS_AUTH_ISLAND, COMPANY_DETAILS_ISLAND)
_SYMBOL_FIELD: Final = "symbol"
_COMPANY_ID_FIELD: Final = "company_id"

# The adapter's own vocabulary for what one financials attempt established. Each
# value survives verbatim inside the sealed record, so a stored outcome stays
# re-checkable against the classifier that produced it.
AUTHENTICATED_PAGE: Final = "AUTHENTICATED_PAGE"
NOT_UTF8: Final = "NOT_UTF8"
ISLAND_MISSING: Final = "ISLAND_MISSING"
ISLAND_INVALID: Final = "ISLAND_INVALID"
IS_AUTH_FALSE: Final = "IS_AUTH_FALSE"
SYMBOL_INVALID: Final = "SYMBOL_INVALID"
SYMBOL_MISMATCH: Final = "SYMBOL_MISMATCH"
COMPANY_ID_INVALID: Final = "COMPANY_ID_INVALID"
COMPANY_ID_MISMATCH: Final = "COMPANY_ID_MISMATCH"
REDIRECT: Final = "REDIRECT"
_HTTP_NATIVE_TEMPLATE: Final = "HTTP_{status}"

SESSION_COOKIE_REQUIRED: Final = (
    "tijori session cookie required for HTTP fetch; mint one via an "
    "authenticated login and inject it as credentials.session_cookie"
)
BODY_TRUNCATED: Final = "tijori response body was truncated"
BODY_OVERSIZE: Final = "tijori response exceeded maximum {limit} bytes"

_COOKIE_HEADER: Final = "Cookie"
_COOKIE_VALUE_TEMPLATE: Final = "sessionid={cookie}"
_USER_AGENT_HEADER: Final = "User-Agent"
_CONTENT_TYPE_HEADER: Final = "Content-Type"
_CONTENT_ENCODING_HEADER: Final = "Content-Encoding"
_CONTENT_LENGTH_HEADER: Final = "Content-Length"
_GET_METHOD: Final = "GET"

TIJORI_RIGHTS: Final = SnapshotRights(authority_refs=(A05_DECISION_005,))

_ZERO_OFFSET: Final = timedelta(0)


class PageEnvelope(NamedTuple):
    """One outbound attempt's result: what came back, or the reason nothing did.

    ``error`` is set only when no HTTP response was obtained at all, or when the
    body that arrived was truncated or oversize; an HTTP refusal is a response
    and carries its own ``status``.
    """

    payload: bytes | None = None
    status: int | None = None
    media_type: str | None = None
    content_encoding: str | None = None
    error: Exception | None = None


class FinancialsPage(BaseModel):
    """One financials attempt, already classified and not yet parsed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    url: str
    slug: str
    retrieved_at: datetime
    http_status: int | None
    media_type: str | None
    content_encoding: str | None
    raw: bytes | None
    outcome: OutcomeRecord

    @field_validator("retrieved_at")
    @classmethod
    def _demand_utc(cls, retrieved_at: datetime) -> datetime:
        """Refuse an instant that is ambiguous about the hour it names."""
        offset = retrieved_at.utcoffset()
        if offset is None:
            raise ValueError(NAIVE_RETRIEVED_AT)
        if offset != _ZERO_OFFSET:
            raise ValueError(NON_UTC_RETRIEVED_AT.format(offset=offset))
        return retrieved_at


def _outcome(code: OutcomeCode, native_value: str) -> OutcomeRecord:
    """One outcome in this adapter's vocabulary."""
    return OutcomeRecord(
        code=code, native_kind=FINANCIALS_PAGE_OUTCOME_KIND, native_value=native_value
    )


def _island_payload(
    collector: JsonScriptCollector, island_id: str
) -> tuple[Any, OutcomeRecord | None]:
    """Deserialize one gate island, or say why it cannot classify anything."""
    if island_id in collector.divergent_duplicates:
        return None, _outcome(OutcomeCode.SCHEMA_DRIFT, ISLAND_INVALID)
    body = collector.islands.get(island_id)
    if body is None:
        return None, _outcome(OutcomeCode.SCHEMA_DRIFT, ISLAND_MISSING)
    try:
        return json.loads(body), None
    except json.JSONDecodeError:
        return None, _outcome(OutcomeCode.SCHEMA_DRIFT, ISLAND_INVALID)


def _identity_outcome(
    details: dict[str, Any], *, expected_symbol: str, expected_company_id: int | None
) -> OutcomeRecord:
    """Classify the identity the page asserts against the one that was asked for."""
    symbol = details.get(_SYMBOL_FIELD)
    if not isinstance(symbol, str) or not symbol.strip():
        return _outcome(OutcomeCode.SCHEMA_DRIFT, SYMBOL_INVALID)
    if symbol.strip() != expected_symbol.strip():
        return _outcome(OutcomeCode.IDENTITY_MISMATCH, SYMBOL_MISMATCH)
    company_id = details.get(_COMPANY_ID_FIELD)
    if not isinstance(company_id, int) or isinstance(company_id, bool):
        return _outcome(OutcomeCode.SCHEMA_DRIFT, COMPANY_ID_INVALID)
    if expected_company_id is not None and company_id != expected_company_id:
        return _outcome(OutcomeCode.IDENTITY_MISMATCH, COMPANY_ID_MISMATCH)
    return _outcome(OutcomeCode.OK, AUTHENTICATED_PAGE)


def classify_financials_body(
    raw: bytes, *, expected_symbol: str, expected_company_id: int | None
) -> OutcomeRecord:
    """Seal what a 200 financials body is, without consulting any table data."""
    try:
        document = decode_document(raw, page_label=FINANCIALS_PAGE_LABEL)
    except TijoriParseError:
        return _outcome(OutcomeCode.SCHEMA_DRIFT, NOT_UTF8)
    collector = JsonScriptCollector(_GATE_ISLANDS)
    collector.feed(document)
    collector.close()
    payloads: dict[str, Any] = {}
    for island_id in _GATE_ISLANDS:
        payload, failure = _island_payload(collector, island_id)
        if failure is not None:
            return failure
        payloads[island_id] = payload
    if payloads[IS_AUTH_ISLAND] is not True:
        return _outcome(OutcomeCode.AUTH_EXPIRED, IS_AUTH_FALSE)
    details = payloads[COMPANY_DETAILS_ISLAND]
    if not isinstance(details, dict):
        return _outcome(OutcomeCode.SCHEMA_DRIFT, ISLAND_INVALID)
    return _identity_outcome(
        details, expected_symbol=expected_symbol, expected_company_id=expected_company_id
    )


def classify_http_status(status: int) -> OutcomeRecord:
    """Seal a non-200 response by its status alone; its body classifies nothing."""
    if 300 <= status < 400:
        return _outcome(OutcomeCode.REQUEST_REJECTED, REDIRECT)
    native_value = _HTTP_NATIVE_TEMPLATE.format(status=status)
    if status == 401:
        return _outcome(OutcomeCode.AUTH_EXPIRED, native_value)
    if status == 403:
        return _outcome(OutcomeCode.CLIENT_BLOCKED, native_value)
    if status == 429:
        return _outcome(OutcomeCode.RATE_LIMITED, native_value)
    if status >= 500:
        return _outcome(OutcomeCode.TRANSPORT_ERROR, native_value)
    return _outcome(OutcomeCode.REQUEST_REJECTED, native_value)


def transport_failure_outcome(error: Exception) -> OutcomeRecord:
    """Seal an attempt that produced no usable body, naming the failure type."""
    return _outcome(OutcomeCode.TRANSPORT_ERROR, type(error).__name__)


def financials_request(slug: str) -> RequestIdentity:
    """The retained route of the financials page: the slug, and never the cookie."""
    return RequestIdentity(
        source_id=TIJORI_SOURCE_ID,
        surface=FINANCIALS_SURFACE,
        request_key=slug,
        method=RequestMethod.GET,
        parameters=(),
    )


def build_page_request(
    url: str, *, session_cookie: SecretStr | None, user_agent: str
) -> urllib.request.Request:
    """Build one authenticated GET, refusing to fetch without a session cookie."""
    if session_cookie is None:
        raise TijoriFetchError(SESSION_COOKIE_REQUIRED)
    return urllib.request.Request(
        url,
        headers={
            _COOKIE_HEADER: _COOKIE_VALUE_TEMPLATE.format(cookie=session_cookie.get_secret_value()),
            _USER_AGENT_HEADER: user_agent,
        },
        method=_GET_METHOD,
    )


def _header(headers: Any, name: str) -> str | None:
    """One response header verbatim, or ``None`` when the response omits it."""
    if headers is None:
        return None
    value = headers.get(name)
    return None if value is None else str(value)


def complete_body(payload: bytes, headers: Any, *, max_bytes: int) -> Exception | None:
    """The reason a received body may not be treated as complete, if there is one."""
    if len(payload) > max_bytes:
        return TijoriFetchError(BODY_OVERSIZE.format(limit=max_bytes))
    declared = _header(headers, _CONTENT_LENGTH_HEADER)
    if declared is None:
        return None
    if not declared.strip().isdigit() or int(declared) != len(payload):
        return TijoriFetchError(BODY_TRUNCATED)
    return None


def envelope_from_http_error(error: urllib.error.HTTPError, *, max_bytes: int) -> PageEnvelope:
    """One refusal the vendor answered with: its status, and its body if readable."""
    try:
        payload: bytes | None = error.read(max_bytes + 1)
    except OSError:
        payload = None
    if payload is not None and len(payload) > max_bytes:
        payload = None
    return PageEnvelope(
        payload=payload,
        status=error.code,
        media_type=_header(error.headers, _CONTENT_TYPE_HEADER),
        content_encoding=_header(error.headers, _CONTENT_ENCODING_HEADER),
    )


def build_financials_page(
    envelope: PageEnvelope,
    *,
    url: str,
    slug: str,
    retrieved_at: datetime,
    expected_symbol: str,
    expected_company_id: int | None,
) -> FinancialsPage:
    """Turn one attempt's result into a classified, still-unparsed page."""
    if envelope.error is not None:
        return FinancialsPage(
            url=url,
            slug=slug,
            retrieved_at=retrieved_at,
            http_status=None,
            media_type=None,
            content_encoding=None,
            raw=None,
            outcome=transport_failure_outcome(envelope.error),
        )
    if envelope.status == 200 and envelope.payload is not None:
        outcome = classify_financials_body(
            envelope.payload,
            expected_symbol=expected_symbol,
            expected_company_id=expected_company_id,
        )
    else:
        outcome = classify_http_status(envelope.status or 0)
    return FinancialsPage(
        url=url,
        slug=slug,
        retrieved_at=retrieved_at,
        http_status=envelope.status,
        media_type=envelope.media_type,
        content_encoding=envelope.content_encoding,
        raw=envelope.payload,
        outcome=outcome,
    )


def capture_record_for(page: FinancialsPage) -> CaptureRecord:
    """Seal one classified page as the capture record that will be retained."""
    body = (
        None
        if page.raw is None
        else BlobRef(
            source_id=TIJORI_SOURCE_ID,
            content_sha256=hashlib.sha256(page.raw).hexdigest(),
            byte_count=len(page.raw),
        )
    )
    return CaptureRecord.make(
        financials_request(page.slug),
        page.retrieved_at,
        page.http_status,
        page.media_type,
        page.content_encoding,
        body,
        page.outcome,
        TIJORI_RIGHTS,
    )
