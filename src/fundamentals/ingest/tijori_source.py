"""Tijori adapter — derived quarterly P&L headline numbers for cross-check only.

Tijori is a private authenticated convenience source, never a source of record.
This adapter accepts only the verified Django ``json_script`` page shape and
rejects identity, authentication, schema, and transport ambiguity before it can
produce an observation.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from html.parser import HTMLParser
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from fundamentals.contracts.observation import (
    AccountingFramework,
    Observation,
    PeriodType,
    Scope,
)
from fundamentals.contracts.provenance import Provenance, SourceAnchorType

_LOGGER = structlog.get_logger(__name__)

SOURCE_ID = "tijori"
ENTITY_SCHEME = "tijori-slug"
DEFAULT_BASE_URL = "https://www.tijorifinance.com"
DEFAULT_PL_URL_TEMPLATE = "{base}/company/{slug}/financials/"
DEFAULT_USER_AGENT = "EquityOS Research"
DEFAULT_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
SCOPE_ASSUMED_NOTE = "scope_assumed=True; Tijori does not disclose statement scope"

_CURRENCY_INR = "INR"
_INR_CRORE_UNIT = "INR crore"
_CRORE_SCALE = 10_000_000
_CRORE_DECIMALS = -7
_FINANCIALS_ISLAND = "fin_tables_data"
_REQUIRED_ISLANDS = (_FINANCIALS_ISLAND, "company_details", "is_auth")
_QUARTERLY_CONSOLIDATED_TABLE = "qt_c"
_MONTH_LABELS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)
_QUARTER_BOUNDS: dict[int, tuple[int, int]] = {
    3: (1, 31),
    6: (4, 30),
    9: (7, 30),
    12: (10, 31),
}


class TijoriError(Exception):
    """Base class for Tijori adapter failures."""


class TijoriCredentialsError(TijoriError):
    """No credentials injected — skippable so the pipeline never hard-fails."""


class TijoriFetchError(TijoriError):
    """Terminal fetch/transport failure (never a partial result)."""


class TijoriParseError(TijoriError):
    """The Tijori page was malformed or internally inconsistent."""


class TijoriConcept(StrEnum):
    """The derived P&L concepts supported by the verified Tijori DOM."""

    SALES = "tijori:sales"
    PBT = "tijori:pbt"
    NET_PROFIT = "tijori:net_profit"


_ROW_TO_CONCEPT: dict[str, TijoriConcept] = {
    "Net Sales": TijoriConcept.SALES,
    "Profit Before Tax": TijoriConcept.PBT,
    "Net Profit": TijoriConcept.NET_PROFIT,
}


class TijoriCredentials(BaseModel):
    """Owner-account auth material, injected at the composition root only."""

    model_config = ConfigDict(frozen=True)

    email: SecretStr | None = None
    password: SecretStr | None = None
    session_cookie: SecretStr | None = None


class TijoriSourceConfig(BaseModel):
    """Injected settings for the Tijori adapter (no environment reads here)."""

    model_config = ConfigDict(frozen=True)

    credentials: TijoriCredentials | None = None
    base_url: str = DEFAULT_BASE_URL
    pl_url_template: str = DEFAULT_PL_URL_TEMPLATE
    user_agent: str = DEFAULT_USER_AGENT
    request_timeout_seconds: float = 30.0
    max_retries: int = 3
    retry_backoff_seconds: float = 1.0
    max_response_bytes: int = Field(default=DEFAULT_MAX_RESPONSE_BYTES, gt=0)
    expected_company_id: int | None = Field(default=None, gt=0)


class TijoriRow(BaseModel):
    """One selected P&L value in the requested quarterly consolidated table."""

    model_config = ConfigDict(frozen=True)

    label: str
    value: Decimal | int


class TijoriPlPayload(BaseModel):
    """Validated selected quarterly P&L data from the JSON islands."""

    model_config = ConfigDict(frozen=True)

    slug: str
    company_id: int
    symbol: str
    url: str
    period_label: str
    period_start: date
    period_end: date
    rows: tuple[TijoriRow, ...]


class _JsonScriptCollector(HTMLParser):
    """Collect required Django JSON islands without interpreting their payloads."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.islands: dict[str, str] = {}
        self.duplicates: set[str] = set()
        self._active_island: str | None = None
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Start collecting a required application/json script body."""
        if tag != "script":
            return
        attributes = dict(attrs)
        island_id = attributes.get("id")
        content_type = attributes.get("type")
        if island_id not in _REQUIRED_ISLANDS or content_type is None:
            return
        if content_type.strip().lower() != "application/json":
            return
        if island_id in self.islands:
            self.duplicates.add(island_id)
            return
        self._active_island = island_id
        self._chunks = []

    def handle_data(self, data: str) -> None:
        """Append a script body fragment for the active JSON island."""
        if self._active_island is not None:
            self._chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        """Finish collecting the active JSON island."""
        if tag == "script" and self._active_island is not None:
            self.islands[self._active_island] = "".join(self._chunks)
            self._active_island = None
            self._chunks = []


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Turn every HTTP redirect into a terminal response error."""

    def redirect_request(
        self,
        request: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        """Refuse redirects so an unknown slug cannot become the home page."""
        del request, fp, code, msg, headers, newurl
        return None


def is_tijori_derived(observation: Observation) -> bool:
    """True when the observation is a Tijori-derived cross-check value."""
    return (
        observation.provenance.source_id == SOURCE_ID
        and observation.accounting_basis is AccountingFramework.UNKNOWN
    )


def _expected_label(period_end: date) -> str:
    """Return the verified ``Mon YYYY`` DOM label for a configured quarter end."""
    quarter = _QUARTER_BOUNDS.get(period_end.month)
    if quarter is None or period_end.day != quarter[1]:
        raise TijoriParseError(f"configured period end is not a fiscal quarter end: {period_end}")
    return f"{_MONTH_LABELS[period_end.month - 1]} {period_end.year}"


def _quarter_start(period_end: date) -> date:
    """Return the start date of the configured Indian fiscal quarter."""
    start_month, _ = _QUARTER_BOUNDS[period_end.month]
    start_year = period_end.year if start_month <= period_end.month else period_end.year - 1
    return date(start_year, start_month, 1)


def _as_object(value: Any, label: str) -> dict[str, Any]:
    """Require an untrusted JSON object with a named failure reason."""
    if not isinstance(value, dict):
        raise TijoriParseError(f"tijori JSON island {label!r} must contain an object")
    return value


def _as_string_list(value: Any, label: str) -> tuple[str, ...]:
    """Require non-empty source labels without normalizing their exact text."""
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise TijoriParseError(f"tijori {label} must be a list of non-empty strings")
    return tuple(value)


class TijoriSource:
    """Fetches verified Tijori JSON-island P&L values as derived observations."""

    def __init__(self, config: TijoriSourceConfig | None = None) -> None:
        self._config = config or TijoriSourceConfig()

    def fetch_pl(
        self, slug: str, *, expected_symbol: str, period_end: date
    ) -> tuple[Observation, ...]:
        """Fetch one stock's configured quarter as derived P&L observations."""
        credentials = self._config.credentials
        if credentials is None:
            raise TijoriCredentialsError(
                "tijori credentials not provided; skipping Tijori cross-check"
            )
        raw = self._fetch_pl_bytes(slug, credentials)
        source_url = self._config.pl_url_template.format(base=self._config.base_url, slug=slug)
        return self.parse_pl_bytes(
            raw,
            slug=slug,
            source_url=source_url,
            expected_symbol=expected_symbol,
            expected_company_id=self._config.expected_company_id,
            period_end=period_end,
        )

    def _fetch_pl_bytes(self, slug: str, credentials: TijoriCredentials) -> bytes:
        """Fetch one complete authenticated financials page without redirects."""
        session_cookie = credentials.session_cookie
        if session_cookie is None:
            raise TijoriFetchError(
                "tijori session cookie required for HTTP fetch; mint one via an "
                "authenticated login and inject it as credentials.session_cookie"
            )
        url = self._config.pl_url_template.format(base=self._config.base_url, slug=slug)
        request = urllib.request.Request(
            url,
            headers={
                "Cookie": f"sessionid={session_cookie.get_secret_value()}",
                "User-Agent": self._config.user_agent,
            },
            method="GET",
        )
        opener = urllib.request.build_opener(_NoRedirectHandler())
        last_error: Exception | None = None
        for attempt in range(1, self._config.max_retries + 1):
            try:
                with opener.open(request, timeout=self._config.request_timeout_seconds) as response:
                    status = response.getcode()
                    if status is not None and 300 <= status < 400:
                        raise TijoriFetchError("tijori slug not found: redirect response")
                    payload = response.read(self._config.max_response_bytes + 1)
                    if not isinstance(payload, bytes):
                        raise TijoriFetchError("tijori response body is not bytes")
                if len(payload) > self._config.max_response_bytes:
                    raise TijoriFetchError(
                        f"tijori response exceeded maximum {self._config.max_response_bytes} bytes"
                    )
                self._verify_complete_response(response, payload)
                return payload
            except TijoriFetchError:
                raise
            except urllib.error.HTTPError as error:
                if 300 <= error.code < 400:
                    raise TijoriFetchError("tijori slug not found: redirect response") from error
                if 400 <= error.code < 500:
                    raise TijoriFetchError(
                        f"tijori returned HTTP {error.code} for {slug!r}"
                    ) from error
                last_error = error
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                last_error = error
            if last_error is not None:
                _LOGGER.warning(
                    "tijori_pl_fetch_failed",
                    attempt=attempt,
                    slug=slug,
                    error_type=type(last_error).__name__,
                    status_code=getattr(last_error, "code", None),
                )
            if attempt < self._config.max_retries:
                time.sleep(self._config.retry_backoff_seconds * attempt)
        raise TijoriFetchError(
            f"tijori pl fetch failed after {self._config.max_retries} attempts"
        ) from last_error

    @staticmethod
    def _verify_complete_response(response: Any, payload: bytes) -> None:
        """Reject an HTTP response whose declared body was not fully read."""
        headers = getattr(response, "headers", None)
        content_length = None if headers is None else headers.get("Content-Length")
        if content_length is None:
            return
        try:
            expected_length = int(content_length)
        except (TypeError, ValueError) as error:
            raise TijoriFetchError("tijori response has invalid Content-Length") from error
        if expected_length != len(payload):
            raise TijoriFetchError("tijori response body was truncated")

    @classmethod
    def parse_pl_bytes(
        cls,
        raw: bytes,
        *,
        slug: str,
        expected_symbol: str,
        expected_company_id: int | None = None,
        period_end: date,
        source_url: str | None = None,
    ) -> tuple[Observation, ...]:
        """Parse the verified JSON-island DOM for one configured issuer and quarter."""
        if not slug.strip():
            raise TijoriParseError("tijori requested slug is empty")
        if not expected_symbol.strip():
            raise TijoriParseError("tijori expected symbol is empty")
        content_sha256 = hashlib.sha256(raw).hexdigest()
        payload = cls._parse_pl_html(
            raw,
            slug=slug,
            expected_symbol=expected_symbol,
            expected_company_id=expected_company_id,
            period_end=period_end,
            source_url=source_url,
        )
        return cls.parse_pl(payload, content_sha256=content_sha256)

    @classmethod
    def _parse_pl_html(
        cls,
        raw: bytes,
        *,
        slug: str,
        expected_symbol: str,
        expected_company_id: int | None,
        period_end: date,
        source_url: str | None,
    ) -> TijoriPlPayload:
        """Extract, validate, and select the verified Tijori JSON-island shape."""
        try:
            document = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise TijoriParseError("tijori financials page is not UTF-8 HTML") from error
        collector = _JsonScriptCollector()
        collector.feed(document)
        collector.close()
        islands = cls._load_required_islands(collector)
        financials = _as_object(islands[_FINANCIALS_ISLAND], _FINANCIALS_ISLAND)
        company_details = _as_object(islands["company_details"], "company_details")
        if islands["is_auth"] is not True:
            raise TijoriParseError("tijori response is not authenticated")

        response_symbol = company_details.get("symbol")
        if not isinstance(response_symbol, str) or not response_symbol.strip():
            raise TijoriParseError("tijori company_details symbol is missing or invalid")
        if response_symbol.strip() != expected_symbol.strip():
            raise TijoriParseError(
                "tijori response identity mismatch: "
                f"requested symbol {expected_symbol.strip()!r}, "
                f"response symbol {response_symbol.strip()!r}"
            )
        company_id = company_details.get("company_id")
        if not isinstance(company_id, int) or isinstance(company_id, bool):
            raise TijoriParseError("tijori company_details company_id is missing or invalid")
        if expected_company_id is not None and company_id != expected_company_id:
            raise TijoriParseError(
                "tijori response identity mismatch: "
                f"requested company ID {expected_company_id}, response company ID {company_id}"
            )

        table = _as_object(financials.get(_QUARTERLY_CONSOLIDATED_TABLE), "qt_c")
        report_dates = _as_string_list(table.get("report_dates"), "qt_c.report_dates")
        expected_label = _expected_label(period_end)
        matching_columns = tuple(
            index for index, label in enumerate(report_dates) if label == expected_label
        )
        if not matching_columns:
            available = ", ".join(report_dates)
            raise TijoriParseError(
                f"tijori requested quarter {expected_label!r} is absent; "
                f"available labels: {available}"
            )
        if len(matching_columns) > 1:
            available = ", ".join(report_dates)
            raise TijoriParseError(
                f"tijori requested quarter {expected_label!r} is ambiguous; "
                f"available labels: {available}"
            )
        column = matching_columns[0]

        rows = cls._selected_rows(table, report_dates, column)
        resolved_url = source_url or DEFAULT_PL_URL_TEMPLATE.format(
            base=DEFAULT_BASE_URL, slug=slug
        )
        return TijoriPlPayload(
            slug=slug,
            company_id=company_id,
            symbol=response_symbol.strip(),
            url=resolved_url,
            period_label=expected_label,
            period_start=_quarter_start(period_end),
            period_end=period_end,
            rows=rows,
        )

    @staticmethod
    def _load_required_islands(collector: _JsonScriptCollector) -> dict[str, Any]:
        """Deserialize every required JSON island with isolated failure reasons."""
        decoded: dict[str, Any] = {}
        for island_id in _REQUIRED_ISLANDS:
            if island_id in collector.duplicates:
                raise TijoriParseError(f"tijori JSON island {island_id!r} appears multiple times")
            raw_island = collector.islands.get(island_id)
            if raw_island is None:
                raise TijoriParseError(f"tijori JSON island {island_id!r} is missing")
            try:
                decoded[island_id] = json.loads(raw_island, parse_float=Decimal)
            except json.JSONDecodeError as error:
                raise TijoriParseError(
                    f"tijori JSON island {island_id!r} is unparseable"
                ) from error
        return decoded

    @staticmethod
    def _selected_rows(
        table: dict[str, Any], report_dates: tuple[str, ...], column: int
    ) -> tuple[TijoriRow, ...]:
        """Select and validate the three required P&L rows at one exact column."""
        raw_rows = table.get("data")
        if not isinstance(raw_rows, list):
            raise TijoriParseError("tijori qt_c.data must be a list")
        selected: dict[str, TijoriRow] = {}
        for raw_row in raw_rows:
            if not isinstance(raw_row, dict):
                raise TijoriParseError("tijori qt_c.data contains a non-object row")
            label = raw_row.get("name")
            if not isinstance(label, str):
                raise TijoriParseError("tijori qt_c.data row name must be a string")
            if label not in _ROW_TO_CONCEPT:
                continue
            if label in selected:
                raise TijoriParseError(f"tijori qt_c.data contains duplicate row {label!r}")
            values = raw_row.get("value")
            if not isinstance(values, list) or len(values) != len(report_dates):
                raise TijoriParseError(
                    f"tijori row {label!r} has invalid values for {len(report_dates)} columns"
                )
            raw_value = values[column]
            if (
                isinstance(raw_value, bool)
                or not isinstance(raw_value, (Decimal, int))
                or isinstance(raw_value, Decimal)
                and not raw_value.is_finite()
            ):
                raise TijoriParseError(
                    f"tijori row {label!r} has a non-numeric value for the requested quarter"
                )
            selected[label] = TijoriRow(label=label, value=raw_value)
        missing = tuple(label for label in _ROW_TO_CONCEPT if label not in selected)
        if missing:
            raise TijoriParseError(
                f"tijori qt_c.data is missing required rows: {', '.join(missing)}"
            )
        return tuple(selected[label] for label in _ROW_TO_CONCEPT)

    @classmethod
    def parse_pl(cls, payload: TijoriPlPayload, *, content_sha256: str) -> tuple[Observation, ...]:
        """Map the selected consolidated P&L rows to derived observations."""
        retrieved_at = datetime.now(tz=UTC)
        observations = tuple(
            cls._to_observation(
                payload=payload,
                concept=_ROW_TO_CONCEPT[row.label],
                row_label=row.label,
                raw_value=row.value,
                content_sha256=content_sha256,
                retrieved_at=retrieved_at,
            )
            for row in payload.rows
        )
        _LOGGER.info(
            "tijori_quarterly_observations_parsed",
            count=len(observations),
            slug=payload.slug,
        )
        return observations

    @staticmethod
    def _to_observation(
        *,
        payload: TijoriPlPayload,
        concept: TijoriConcept,
        row_label: str,
        raw_value: Decimal | int,
        content_sha256: str,
        retrieved_at: datetime,
    ) -> Observation:
        """Build one derived observation from a verified JSON numeric value."""
        # Tijori's only EPS is adjusted EPS (adj_eps_abs), so it is deliberately unmapped.
        normalized_value = raw_value if isinstance(raw_value, Decimal) else Decimal(raw_value)
        context_ref = (
            f"{payload.url}#{_FINANCIALS_ISLAND}/{_QUARTERLY_CONSOLIDATED_TABLE}/"
            f"{payload.period_label}/{concept.value}"
        )
        provenance = Provenance(
            source_id=SOURCE_ID,
            file_sha256=content_sha256,
            anchor_type=SourceAnchorType.JSON_ISLAND,
            context_ref=context_ref,
            island_id=_FINANCIALS_ISLAND,
            table_key=_QUARTERLY_CONSOLIDATED_TABLE,
            row_label=row_label,
            column_label=payload.period_label,
            retrieved_at=retrieved_at,
            first_seen_at=retrieved_at,
        )
        return Observation(
            concept_qname=concept.value,
            raw_value=str(raw_value),
            normalized_value=normalized_value,
            normalized_unit=_INR_CRORE_UNIT,
            context_ref=context_ref,
            entity_scheme=ENTITY_SCHEME,
            entity_id=payload.slug,
            scope=Scope.CONSOLIDATED,
            accounting_basis=AccountingFramework.UNKNOWN,
            period_type=PeriodType.DURATION,
            period_start=payload.period_start,
            period_end=payload.period_end,
            currency=_CURRENCY_INR,
            scale=_CRORE_SCALE,
            decimals=_CRORE_DECIMALS,
            provenance=provenance,
        )
