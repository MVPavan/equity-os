"""Synthetic fixtures and the pinned transport for the ``screener-watchlist`` tests.

Nothing here is a captured page. Every body is built from the *structure* the
live surface was verified to have — a CSV whose rows are alphabetical rather
than in watchlist order, its identity labels ahead of the value block, and one
field quoted because it contains a comma — with invented names, codes, ids and
numbers throughout.

The page markup those bodies are served beside lives in
:mod:`screener_watchlist_markup`, split off only because the two halves together
exceed this repo's per-file ceiling. Every name it defines is re-exported here,
so a test module imports this one module and reaches both halves through it.

The transport is pinned at :func:`urllib.request.build_opener`, not at
``ScreenerSessionSource._fetch_bytes``. The export is a POST that does not go
through ``_fetch_bytes``, so a fake that replaces only that method leaves the
POST live against the real host. Pinning the opener means every request the
production code can make — GET or POST, old helper or new — arrives at
:class:`Transport`, which answers only the URLs a test offered and raises on any
other.

The Slice 4 modules are reached through :class:`_Module` rather than imported at
the top: these tests are written before the implementation exists, and a
top-level import would collapse every independently red test into one
collection error.

Fixtures are self-checking. A builder that claims to make N records asserts
that its own CSV parses back to N, because a Slice 3 fixture once produced zero
rows for months without any test noticing.
"""

from __future__ import annotations

import csv
import email.message
import importlib
import io
import urllib.error
import urllib.request
from http.cookies import SimpleCookie
from typing import Any
from urllib.parse import parse_qs

import pytest
from pydantic import BaseModel, ConfigDict, SecretStr
from screener_watchlist_markup import (
    ACCOUNT_LINK,
    CSRF_FORM_FIELD,
    CSRF_FORM_TOKEN,
    DECOY_DROPDOWNS,
    DEFAULT_COLUMNS,
    EXPORT_PATH,
    LIVE_HEADER_BLOCK,
    LIVE_MEMBER_COUNT,
    LOGOUT_FORM,
    PAGE_INFO_BLOCK,
    PAGINATION_BLOCK,
    TABLE_CLASS,
    WATCHLIST_ID,
    WATCHLIST_NAME,
    WIDE_COLUMNS,
    Column,
    Member,
    data_row,
    dropdown,
    export_action,
    export_form,
    export_url,
    header_cell,
    header_row,
    page,
    results_table,
    row_shapes,
    table_of,
    value_cell,
    watchlist_page,
)

from fundamentals.ingest.screener_session import ScreenerSessionSource
from fundamentals.ingest.screener_session_models import (
    SCREENER_ORIGIN,
    ScreenerCredentials,
    ScreenerSessionConfig,
)
from fundamentals.ingest.screener_session_page import parse_document

# Re-export, so a test module reaches both halves of the fixture corpus through
# this one module. Only the markup half is listed: everything below is defined
# here and needs no declaration.
__all__ = [
    "ACCOUNT_LINK",
    "CSRF_FORM_FIELD",
    "CSRF_FORM_TOKEN",
    "DECOY_DROPDOWNS",
    "DEFAULT_COLUMNS",
    "EXPORT_PATH",
    "LIVE_HEADER_BLOCK",
    "LIVE_MEMBER_COUNT",
    "LOGOUT_FORM",
    "PAGE_INFO_BLOCK",
    "PAGINATION_BLOCK",
    "TABLE_CLASS",
    "WATCHLIST_ID",
    "WATCHLIST_NAME",
    "WIDE_COLUMNS",
    "Column",
    "Member",
    "data_row",
    "dropdown",
    "export_action",
    "export_form",
    "export_url",
    "header_cell",
    "header_row",
    "page",
    "results_table",
    "row_shapes",
    "table_of",
    "value_cell",
    "watchlist_page",
]


class _Module:
    """Deferred attribute access into a Slice 4 module.

    Every lookup happens at call time, so a module that does not exist yet fails
    the one test that asked for it instead of the whole file.
    """

    def __init__(self, name: str) -> None:
        self._name = name

    def __getattr__(self, attribute: str) -> Any:
        """Resolve one public name out of the named module."""
        return getattr(importlib.import_module(self._name), attribute)


models = _Module("fundamentals.ingest.screener_watchlist_models")
watchlist = _Module("fundamentals.ingest.screener_watchlist")
watchlist_cli = _Module("fundamentals.api.screener_watchlist_cli")

COMMAND = "screener-watchlist"
SESSION_ENV = "SCREENER_SESSION_COOKIE"
SESSION_TOKEN = "fixture-session-token"

# The cookie half of two distinct synthetic tokens; the form half is
# ``CSRF_FORM_TOKEN``, beside the markup that embeds it. The contract forbids
# ever using the form token as the cookie value, so the two must differ for a
# test to tell them apart.
CSRF_COOKIE_VALUE = "fixture-csrf-cookie-value-0001"
CSRF_COOKIE_NAME = "csrftoken"
SESSION_COOKIE_NAME = "sessionid"

OTHER_WATCHLIST_ID = 5050505
OTHER_WATCHLIST_NAME = "Fixture Second List"
WATCHLIST_PAGE_URL = f"{SCREENER_ORIGIN}/watchlist/"
EXPORT_CONTENT_TYPE = "text/csv"
EXPORT_DISPOSITION = "attachment; filename=fixture-core-list.csv"
SOURCE_ID = "screener-subscriber"

# The CSV identity labels the source publishes ahead of the value block. They
# are located by label, never by counting to six.
IDENTITY_HEADERS = ("Name", "BSE Code", "NSE Code", "ISIN Code", "Industry Group", "Industry")

# A cookie the GET sets *before* the csrftoken, so a transport that keeps only
# the first Set-Cookie header never sees the token.
DEFAULT_SET_COOKIE = (
    "fixture_notice=seen; Path=/",
    f"{CSRF_COOKIE_NAME}={CSRF_COOKIE_VALUE}; Path=/; SameSite=Lax",
)


def _value(serial: int, position: int) -> str:
    """One synthetic cell text; every eleventh cell is legitimately empty."""
    if (serial + position) % 11 == 0:
        return ""
    if (serial + position) % 5 == 0:
        return f"-{serial}.{position}5"
    return f"{serial * 10 + position}.{position}5"


def members(
    count: int = 12, *, columns: tuple[Column, ...] = DEFAULT_COLUMNS
) -> tuple[Member, ...]:
    """``count`` members in watchlist order, which is not alphabetical order.

    Names run backwards so the HTML order differs from the CSV's alphabetical
    order on every fixture, and three names carry the shapes the source is known
    to render: one truncated to a trailing dot, one lower-cased, one with an
    apostrophe that the HTML encodes as an entity. Every tenth member is the
    id-routed, delisted shape (no exchange codes, an ISIN only); every fourth is
    BSE-only, whose slug is its BSE code.
    """
    built: list[Member] = []
    for serial in range(1, count + 1):
        name = f"Synth Member {count + 1 - serial:03d}"
        if serial == 4:
            name = f"Synth Member {count + 1 - serial:02d}."
        elif serial == 5:
            name = name.lower()
        elif serial == 7:
            name = f"Synth Member's {count + 1 - serial}"
        company_id = 8800000 + serial
        bse_code = f"55{serial:04d}"
        nse_code = f"SYNTH{serial:03d}"
        if serial % 10 == 9:
            nse_code, bse_code = "", ""
            href = f"/company/id/{company_id}/consolidated/"
        elif serial % 4 == 3:
            nse_code = ""
            href = f"/company/{bse_code}/consolidated/"
        elif serial % 3 == 0:
            href = f"/company/{nse_code}/"
        else:
            href = f"/company/{nse_code}/consolidated/"
        industry = (
            "Widgets, Gadgets & Gizmos" if serial % 7 == 5 else f"Synthetic Industry {serial % 5}"
        )
        built.append(
            Member(
                serial=serial,
                company_id=company_id,
                name=name,
                href=href,
                nse_code=nse_code,
                bse_code=bse_code,
                isin_code=f"SYN{serial:09d}",
                industry_group=f"Synthetic Group {serial % 3}",
                industry=industry,
                values=tuple(_value(serial, position) for position in range(len(columns))),
            )
        )
    return tuple(built)


def rebuilt(model: Any, **overrides: Any) -> Any:
    """The same model built again through validation with named fields replaced."""
    return type(model)(**{**model.model_dump(), **overrides})


def renamed_columns(columns: tuple[Column, ...], position: int, tooltip: str) -> tuple[Column, ...]:
    """The same columns with one tooltip replaced: the same width, one different name."""
    return tuple(
        rebuilt(column, tooltip=tooltip) if index == position else column
        for index, column in enumerate(columns)
    )


def with_member(roster: tuple[Member, ...], serial: int, **overrides: Any) -> tuple[Member, ...]:
    """The roster with one member's fields replaced."""
    return tuple(
        rebuilt(member, **overrides) if member.serial == serial else member for member in roster
    )


# --------------------------------------------------------------------------
# CSV
# --------------------------------------------------------------------------


def csv_header(
    columns: tuple[Column, ...], *, identity: tuple[str, ...] = IDENTITY_HEADERS
) -> tuple[str, ...]:
    """The export header: the identity labels, then the tooltips as value labels."""
    return (*identity, *(column.tooltip for column in columns))


def csv_record(member: Member, *, identity: tuple[str, ...] = IDENTITY_HEADERS) -> tuple[str, ...]:
    """One export record, its identity fields laid out in the order ``identity`` names."""
    fields = {
        "Name": member.name,
        "BSE Code": member.bse_code,
        "NSE Code": member.nse_code,
        "ISIN Code": member.isin_code,
        "Industry Group": member.industry_group,
        "Industry": member.industry,
    }
    return (*(fields[label] for label in identity), *member.values)


def csv_records(
    roster: tuple[Member, ...], *, identity: tuple[str, ...] = IDENTITY_HEADERS
) -> tuple[tuple[str, ...], ...]:
    """Every member's record, in the case-insensitive alphabetical order the export uses."""
    ordered = sorted(roster, key=lambda member: member.name.lower())
    return tuple(csv_record(member, identity=identity) for member in ordered)


def csv_text(header: tuple[str, ...], records: tuple[tuple[str, ...], ...]) -> str:
    """Serialise a header and records with a real CSV writer, checked by nobody.

    The writer quotes a field containing a comma on its own, which is how the
    one such field on the live export is rendered.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(records)
    return buffer.getvalue()


def csv_shape(text: str) -> tuple[int, int, bool]:
    """``(header width, record count, every record as wide as the header)`` of one CSV."""
    rows = list(csv.reader(io.StringIO(text)))
    header, records = rows[0], rows[1:]
    return len(header), len(records), all(len(record) == len(header) for record in records)


def export_csv(
    roster: tuple[Member, ...],
    *,
    columns: tuple[Column, ...] = DEFAULT_COLUMNS,
    identity: tuple[str, ...] = IDENTITY_HEADERS,
    records: tuple[tuple[str, ...], ...] | None = None,
) -> str:
    """The export for one roster, checked to hold exactly one record per member."""
    header = csv_header(columns, identity=identity)
    body = csv_records(roster, identity=identity) if records is None else records
    text = csv_text(header, body)
    width, count, rectangular = csv_shape(text)
    if records is None and (width, count, rectangular) != (len(header), len(roster), True):
        raise AssertionError(f"fixture CSV has {count} records of width {width}, not {len(roster)}")
    return text


# --------------------------------------------------------------------------
# The pinned transport
# --------------------------------------------------------------------------


class Exchange(BaseModel):
    """One request the pinned opener saw: method, URL, lower-cased headers, body."""

    model_config = ConfigDict(frozen=True)

    method: str
    url: str
    headers: dict[str, str]
    body: bytes | None


class UnofferedRequestError(AssertionError):
    """A request reached the pinned opener for a URL no test offered."""


class DialOutError(AssertionError):
    """An opener built before the seam was installed was used after it."""


class Transport:
    """Everything the pinned opener was asked, in order."""

    def __init__(self) -> None:
        self.exchanges: list[Exchange] = []

    @property
    def urls(self) -> list[str]:
        """Every requested URL, in order."""
        return [exchange.url for exchange in self.exchanges]

    @property
    def posts(self) -> list[Exchange]:
        """Only the POST requests."""
        return [exchange for exchange in self.exchanges if exchange.method == "POST"]


class _Response:
    """The minimum of a urllib response the transport reads: status, body, headers."""

    def __init__(self, status: int, payload: bytes, headers: email.message.Message) -> None:
        self.status = status
        self.headers = headers
        self._payload = payload

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def getcode(self) -> int:
        """The HTTP status."""
        return self.status

    def info(self) -> email.message.Message:
        """The response headers, as urllib exposes them."""
        return self.headers

    def getheader(self, name: str, default: str | None = None) -> str | None:
        """One response header by name."""
        return self.headers.get(name, default)

    def read(self, size: int = -1) -> bytes:
        """The whole body, whatever size was asked for."""
        del size
        return self._payload


def _headers(pairs: tuple[tuple[str, str], ...]) -> email.message.Message:
    """A header block that keeps repeated names as separate headers."""
    message = email.message.Message()
    for name, value in pairs:
        message[name] = value
    return message


def _bytes(body: str | bytes) -> bytes:
    """Encode a text body; pass bytes through untouched."""
    return body if isinstance(body, bytes) else body.encode("utf-8")


def serve(
    monkeypatch: pytest.MonkeyPatch,
    *,
    page: str | bytes,
    export: str | bytes | None,
    page_url: str = WATCHLIST_PAGE_URL,
    export_target: str | None = None,
    set_cookie: tuple[str, ...] = DEFAULT_SET_COOKIE,
    export_status: int = 200,
    export_content_type: str | None = EXPORT_CONTENT_TYPE,
    export_disposition: str | None = EXPORT_DISPOSITION,
    page_error: urllib.error.HTTPError | None = None,
    export_error: urllib.error.HTTPError | None = None,
) -> Transport:
    """Pin the opener to one page and one export, refusing every other request.

    The page answers a GET of ``page_url`` with ``set_cookie`` as separate
    ``Set-Cookie`` headers; the export answers a POST of ``export_target`` — by
    default the ``goto_sublist`` action for :data:`WATCHLIST_ID` — with the
    content headers given. ``export=None`` offers no export at all. Backoff
    sleeping is removed so a refused request does not cost real seconds.

    The transport reads the ``Cookie`` header off the request object itself,
    which is the only place it can be: a cookie jar attached to the opener would
    be bypassed here, exactly as it would be silenced in production by the
    manual header the transport already sets.
    """
    transport = Transport()
    target = export_url() if export_target is None else export_target

    class _Opener:
        def open(self, request: Any, timeout: float | None = None) -> _Response:
            del timeout
            headers = {name.lower(): value for name, value in request.header_items()}
            exchange = Exchange(
                method=request.get_method(),
                url=request.full_url,
                headers=headers,
                body=request.data,
            )
            transport.exchanges.append(exchange)
            if exchange.method == "GET" and exchange.url == page_url:
                if page_error is not None:
                    raise page_error
                pairs = (("Content-Type", "text/html; charset=utf-8"),) + tuple(
                    ("Set-Cookie", value) for value in set_cookie
                )
                return _Response(200, _bytes(page), _headers(pairs))
            if exchange.method == "POST" and exchange.url == target and export is not None:
                if export_error is not None:
                    raise export_error
                pairs = tuple(
                    (name, value)
                    for name, value in (
                        ("Content-Type", export_content_type),
                        ("Content-Disposition", export_disposition),
                    )
                    if value is not None
                )
                return _Response(export_status, _bytes(export), _headers(pairs))
            raise UnofferedRequestError(
                f"{exchange.method} {exchange.url} was requested but never offered"
            )

    monkeypatch.setenv(SESSION_ENV, SESSION_TOKEN)
    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: _Opener())
    monkeypatch.setattr("fundamentals.ingest.screener_session.time.sleep", lambda seconds: None)
    return transport


def refuse_dial_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any opener built from now on raise, without touching a socket."""

    class _Sentinel:
        def open(self, request: Any, timeout: float | None = None) -> _Response:
            del timeout
            raise DialOutError(f"an opener built before the seam was used for {request.full_url}")

    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: _Sentinel())


def http_error(url: str, status: int, reason: str = "error") -> urllib.error.HTTPError:
    """An ``HTTPError`` the way urllib raises one, with an empty header block."""
    return urllib.error.HTTPError(url, status, reason, email.message.Message(), None)


def cookies_of(exchange: Exchange) -> dict[str, str]:
    """The cookies one request carried, parsed from its single ``Cookie`` header."""
    jar: SimpleCookie = SimpleCookie()
    jar.load(exchange.headers.get("cookie", ""))
    return {name: morsel.value for name, morsel in jar.items()}


def form_of(exchange: Exchange) -> dict[str, list[str]]:
    """The urlencoded form fields one POST carried."""
    if exchange.body is None:
        return {}
    return parse_qs(exchange.body.decode("utf-8"), keep_blank_values=True)


def config() -> ScreenerSessionConfig:
    """A config carrying a fixture cookie and no request spacing."""
    return ScreenerSessionConfig(
        credentials=ScreenerCredentials(session_cookie=SecretStr(SESSION_TOKEN)),
        min_request_spacing_seconds=0,
        rate_limit_backoff_seconds=0,
    )


def source() -> ScreenerSessionSource:
    """One subscriber source, shared by the GET and the POST of a run."""
    return ScreenerSessionSource(config())


def acquire(
    monkeypatch: pytest.MonkeyPatch,
    *,
    page: str | bytes,
    export: str | bytes | None,
    watchlist_id: int | None = None,
    injected: ScreenerSessionSource | None = None,
    **options: Any,
) -> tuple[Any, Transport]:
    """Acquire one watchlist through the real code path against the pinned seam."""
    transport = serve(monkeypatch, page=page, export=export, **options)
    run = watchlist.acquire_watchlist(
        source=injected if injected is not None else source(), watchlist_id=watchlist_id
    )
    return run, transport


def acquire_roster(
    monkeypatch: pytest.MonkeyPatch,
    roster: tuple[Member, ...],
    *,
    columns: tuple[Column, ...] = DEFAULT_COLUMNS,
    **options: Any,
) -> tuple[Any, Transport]:
    """Acquire one roster rendered consistently on both sides."""
    return acquire(
        monkeypatch,
        page=watchlist_page(roster, columns=columns),
        export=export_csv(roster, columns=columns),
        **options,
    )


def read_table(body: str) -> Any:
    """Read one page body through the pure table reader."""
    return watchlist.read_watchlist_table(parse_document(body))


def read_export(
    body: str | bytes,
    *,
    http_status: int = 200,
    content_type: str | None = EXPORT_CONTENT_TYPE,
    content_disposition: str | None = EXPORT_DISPOSITION,
) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]:
    """Read one export response through the pure CSV reader."""
    header, records = watchlist.read_watchlist_export(
        _bytes(body),
        http_status=http_status,
        content_type=content_type,
        content_disposition=content_disposition,
    )
    return tuple(header), tuple(tuple(record) for record in records)
