"""Tijori adapter — derived quarterly P&L headline numbers for cross-check only.

Tijori is a private authenticated convenience source, never a source of record.
This adapter accepts only the verified Django ``json_script`` page shape and
rejects identity, authentication, schema, and transport ambiguity before it can
produce an observation.
"""

from __future__ import annotations

import hashlib
import time
import urllib.error
import urllib.request
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
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
from fundamentals.ingest.tijori_page import JsonScriptCollector, decode_document, load_islands
from fundamentals.ingest.tijori_shareholding import (
    TijoriShareholding,
    build_tijori_shareholding,
)
from fundamentals.ingest.tijori_tables import (
    FINANCIALS_ISLAND_ID,
    FINANCIALS_LOCKS_ISLAND_ID,
    PLAN_DETAILS_ISLAND_ID,
    TIJORI_SOURCE_ID,
    TijoriTable,
    build_all_tijori_tables,
    build_tijori_table,
    parse_table_key,
)
from fundamentals.ingest.tijori_tables import (
    TijoriCredentialsError as TijoriCredentialsError,
)
from fundamentals.ingest.tijori_tables import (
    TijoriError as TijoriError,
)
from fundamentals.ingest.tijori_tables import (
    TijoriFetchError as TijoriFetchError,
)
from fundamentals.ingest.tijori_tables import (
    TijoriParseError as TijoriParseError,
)

_LOGGER = structlog.get_logger(__name__)

SOURCE_ID = TIJORI_SOURCE_ID
ENTITY_SCHEME = "tijori-slug"
DEFAULT_BASE_URL = "https://www.tijorifinance.com"
DEFAULT_PL_URL_TEMPLATE = "{base}/company/{slug}/financials/"
DEFAULT_SHAREHOLDING_URL_TEMPLATE = "{base}/company/{slug}/shareholding/"
DEFAULT_USER_AGENT = "EquityOS Research"
DEFAULT_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
SCOPE_ASSUMED_NOTE = "scope_assumed=True; Tijori does not disclose statement scope"

_CURRENCY_INR = "INR"
_INR_CRORE_UNIT = "INR crore"
_CRORE_SCALE = 10_000_000
_CRORE_DECIMALS = -7
_FINANCIALS_ISLAND = FINANCIALS_ISLAND_ID
_REQUIRED_ISLANDS = (_FINANCIALS_ISLAND, "company_details", "is_auth")
_TABLE_ISLANDS = _REQUIRED_ISLANDS
# Plan and capability islands are metadata: their absence must never block a
# table whose raw data is present on the page.
_TABLE_OPTIONAL_ISLANDS = (FINANCIALS_LOCKS_ISLAND_ID, PLAN_DETAILS_ISLAND_ID)
_FINANCIALS_PAGE_LABEL = "financials"
_PL_FETCH_FAILED_EVENT = "tijori_pl_fetch_failed"
_SHAREHOLDING_FETCH_FAILED_EVENT = "tijori_shareholding_fetch_failed"
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
    shareholding_url_template: str = DEFAULT_SHAREHOLDING_URL_TEMPLATE
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

    def fetch_table(self, key: str, *, slug: str, expected_symbol: str) -> TijoriTable:
        """Fetch one typed raw financial table from an authenticated page."""
        parse_table_key(key)
        credentials = self._config.credentials
        if credentials is None:
            raise TijoriCredentialsError(
                "tijori credentials not provided; skipping Tijori table acquisition"
            )
        raw = self._fetch_pl_bytes(slug, credentials)
        source_url = self._config.pl_url_template.format(base=self._config.base_url, slug=slug)
        return self.parse_table_bytes(
            raw,
            key=key,
            slug=slug,
            expected_symbol=expected_symbol,
            expected_company_id=self._config.expected_company_id,
            source_url=source_url,
        )

    def fetch_all_tables(self, *, slug: str, expected_symbol: str) -> tuple[TijoriTable, ...]:
        """Fetch every supported raw financial table with one authenticated GET."""
        credentials = self._config.credentials
        if credentials is None:
            raise TijoriCredentialsError(
                "tijori credentials not provided; skipping Tijori table acquisition"
            )
        raw = self._fetch_pl_bytes(slug, credentials)
        source_url = self._config.pl_url_template.format(base=self._config.base_url, slug=slug)
        return self.parse_all_tables_bytes(
            raw,
            slug=slug,
            expected_symbol=expected_symbol,
            expected_company_id=self._config.expected_company_id,
            source_url=source_url,
        )

    def fetch_shareholding(
        self, *, slug: str, expected_symbol: str, expected_company_id: int
    ) -> TijoriShareholding:
        """Fetch the detailed shareholding table from an authenticated page.

        ``expected_company_id`` is required, not read from config: the page's only
        identity marker is its heading ``comp_id``, which proves nothing without a
        configured id to match it against.
        """
        credentials = self._config.credentials
        if credentials is None:
            raise TijoriCredentialsError(
                "tijori credentials not provided; skipping Tijori shareholding acquisition"
            )
        raw = self._fetch_shareholding_bytes(slug, credentials)
        source_url = self._config.shareholding_url_template.format(
            base=self._config.base_url, slug=slug
        )
        return self.parse_shareholding_bytes(
            raw,
            slug=slug,
            expected_symbol=expected_symbol,
            expected_company_id=expected_company_id,
            source_url=source_url,
        )

    @staticmethod
    def parse_shareholding_bytes(
        raw: bytes,
        *,
        slug: str,
        expected_symbol: str,
        expected_company_id: int,
        source_url: str | None = None,
    ) -> TijoriShareholding:
        """Parse the detailed shareholding table from a verified shareholding page."""
        if not slug.strip():
            raise TijoriParseError("tijori requested slug is empty")
        if not expected_symbol.strip():
            raise TijoriParseError("tijori expected symbol is empty")
        resolved_url = source_url or DEFAULT_SHAREHOLDING_URL_TEMPLATE.format(
            base=DEFAULT_BASE_URL, slug=slug
        )
        return build_tijori_shareholding(
            raw,
            slug=slug,
            expected_symbol=expected_symbol,
            expected_company_id=expected_company_id,
            source_url=resolved_url,
            retrieved_at=datetime.now(tz=UTC),
        )

    def _fetch_pl_bytes(self, slug: str, credentials: TijoriCredentials) -> bytes:
        """Fetch one complete authenticated financials page without redirects."""
        url = self._config.pl_url_template.format(base=self._config.base_url, slug=slug)
        return self._fetch_page_bytes(
            url, slug=slug, credentials=credentials, fetch_event=_PL_FETCH_FAILED_EVENT
        )

    def _fetch_shareholding_bytes(self, slug: str, credentials: TijoriCredentials) -> bytes:
        """Fetch one complete authenticated shareholding page without redirects."""
        url = self._config.shareholding_url_template.format(base=self._config.base_url, slug=slug)
        return self._fetch_page_bytes(
            url, slug=slug, credentials=credentials, fetch_event=_SHAREHOLDING_FETCH_FAILED_EVENT
        )

    def _fetch_page_bytes(
        self, url: str, *, slug: str, credentials: TijoriCredentials, fetch_event: str
    ) -> bytes:
        """Fetch one complete authenticated Tijori page without following redirects."""
        session_cookie = credentials.session_cookie
        if session_cookie is None:
            raise TijoriFetchError(
                "tijori session cookie required for HTTP fetch; mint one via an "
                "authenticated login and inject it as credentials.session_cookie"
            )
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
                    fetch_event,
                    attempt=attempt,
                    slug=slug,
                    error_type=type(last_error).__name__,
                    status_code=getattr(last_error, "code", None),
                )
            if attempt < self._config.max_retries:
                time.sleep(self._config.retry_backoff_seconds * attempt)
        raise TijoriFetchError(
            f"tijori page fetch failed after {self._config.max_retries} attempts"
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
    def parse_table_bytes(
        cls,
        raw: bytes,
        *,
        key: str,
        slug: str,
        expected_symbol: str,
        expected_company_id: int | None = None,
        source_url: str | None = None,
    ) -> TijoriTable:
        """Parse one typed raw table from a verified financials page."""
        if not slug.strip():
            raise TijoriParseError("tijori requested slug is empty")
        if not expected_symbol.strip():
            raise TijoriParseError("tijori expected symbol is empty")
        parse_table_key(key)
        islands, company_id, response_symbol = cls._verified_page_islands(
            raw,
            expected_symbol=expected_symbol,
            expected_company_id=expected_company_id,
            required_islands=_TABLE_ISLANDS,
            optional_islands=_TABLE_OPTIONAL_ISLANDS,
        )
        resolved_url = source_url or DEFAULT_PL_URL_TEMPLATE.format(
            base=DEFAULT_BASE_URL, slug=slug
        )
        return build_tijori_table(
            financials=islands[_FINANCIALS_ISLAND],
            financials_locks=islands.get(FINANCIALS_LOCKS_ISLAND_ID),
            plan_details=islands.get(PLAN_DETAILS_ISLAND_ID),
            key=key,
            content_sha256=hashlib.sha256(raw).hexdigest(),
            source_url=resolved_url,
            retrieved_at=datetime.now(tz=UTC),
            slug=slug,
            symbol=response_symbol,
            company_id=company_id,
        )

    @classmethod
    def parse_all_tables_bytes(
        cls,
        raw: bytes,
        *,
        slug: str,
        expected_symbol: str,
        expected_company_id: int | None = None,
        source_url: str | None = None,
    ) -> tuple[TijoriTable, ...]:
        """Parse every typed raw table from a verified financials page."""
        if not slug.strip():
            raise TijoriParseError("tijori requested slug is empty")
        if not expected_symbol.strip():
            raise TijoriParseError("tijori expected symbol is empty")
        islands, company_id, response_symbol = cls._verified_page_islands(
            raw,
            expected_symbol=expected_symbol,
            expected_company_id=expected_company_id,
            required_islands=_TABLE_ISLANDS,
            optional_islands=_TABLE_OPTIONAL_ISLANDS,
        )
        resolved_url = source_url or DEFAULT_PL_URL_TEMPLATE.format(
            base=DEFAULT_BASE_URL, slug=slug
        )
        return build_all_tijori_tables(
            financials=islands[_FINANCIALS_ISLAND],
            financials_locks=islands.get(FINANCIALS_LOCKS_ISLAND_ID),
            plan_details=islands.get(PLAN_DETAILS_ISLAND_ID),
            content_sha256=hashlib.sha256(raw).hexdigest(),
            source_url=resolved_url,
            retrieved_at=datetime.now(tz=UTC),
            slug=slug,
            symbol=response_symbol,
            company_id=company_id,
        )

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
        islands, company_id, response_symbol = cls._verified_page_islands(
            raw,
            expected_symbol=expected_symbol,
            expected_company_id=expected_company_id,
            required_islands=_REQUIRED_ISLANDS,
        )
        financials = _as_object(islands[_FINANCIALS_ISLAND], _FINANCIALS_ISLAND)

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
            symbol=response_symbol,
            url=resolved_url,
            period_label=expected_label,
            period_start=_quarter_start(period_end),
            period_end=period_end,
            rows=rows,
        )

    @classmethod
    def _verified_page_islands(
        cls,
        raw: bytes,
        *,
        expected_symbol: str,
        expected_company_id: int | None,
        required_islands: tuple[str, ...],
        optional_islands: tuple[str, ...] = (),
    ) -> tuple[dict[str, Any], int, str]:
        """Validate page encoding, authentication, identity, and named JSON islands."""
        document = decode_document(raw, page_label=_FINANCIALS_PAGE_LABEL)
        collector = JsonScriptCollector(required_islands + optional_islands)
        collector.feed(document)
        collector.close()
        islands = load_islands(collector, required_islands, optional_islands)
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
        return islands, company_id, response_symbol.strip()

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
