"""Tijori adapter — transport and per-surface entry points for one company.

Tijori is a private authenticated convenience source, never a source of record.
This adapter owns the authenticated fetch, the page-level authentication and
identity gates, and the entry point for each acquisition surface; it accepts only
the verified Django ``json_script`` page shape and rejects identity,
authentication, schema, and transport ambiguity before it can produce a value.

Surface-specific parsing lives beside it: the derived quarterly P&L in
:mod:`fundamentals.ingest.tijori_pl`, the raw financial tables in
:mod:`fundamentals.ingest.tijori_tables`, shareholding in
:mod:`fundamentals.ingest.tijori_shareholding`, and the overview sections in
:mod:`fundamentals.ingest.tijori_overview`.
"""

from __future__ import annotations

import hashlib
import time
import urllib.error
import urllib.request
from datetime import UTC, date, datetime
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from fundamentals.contracts.observation import Observation
from fundamentals.ingest.tijori_analysis import build_tijori_analysis
from fundamentals.ingest.tijori_analysis_models import (
    METRIC_ID_REQUIRED,
    METRIC_SECTIONS,
    SECTION_PATHS,
    TijoriAnalysisFetch,
    TijoriAnalysisMetricIdError,
    TijoriAnalysisSection,
)
from fundamentals.ingest.tijori_overview import build_tijori_overview
from fundamentals.ingest.tijori_overview_models import (
    TijoriOverviewSection,
    TijoriOverviewSectionBase,
)
from fundamentals.ingest.tijori_page import (
    JsonScriptCollector,
    as_object,
    decode_document,
    load_islands,
)
from fundamentals.ingest.tijori_pl import (
    ENTITY_SCHEME as ENTITY_SCHEME,
)
from fundamentals.ingest.tijori_pl import (
    SCOPE_ASSUMED_NOTE as SCOPE_ASSUMED_NOTE,
)
from fundamentals.ingest.tijori_pl import (
    TijoriConcept as TijoriConcept,
)
from fundamentals.ingest.tijori_pl import (
    TijoriPlPayload,
    build_pl_payload,
    pl_observations,
)
from fundamentals.ingest.tijori_pl import (
    TijoriRow as TijoriRow,
)
from fundamentals.ingest.tijori_pl import (
    is_tijori_derived as is_tijori_derived,
)
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
DEFAULT_BASE_URL = "https://www.tijorifinance.com"
DEFAULT_PL_URL_TEMPLATE = "{base}/company/{slug}/financials/"
DEFAULT_SHAREHOLDING_URL_TEMPLATE = "{base}/company/{slug}/shareholding/"
DEFAULT_OVERVIEW_URL_TEMPLATE = "{base}/company/{slug}/"
DEFAULT_USER_AGENT = "EquityOS Research"
DEFAULT_MAX_RESPONSE_BYTES = 4 * 1024 * 1024

_FINANCIALS_ISLAND = FINANCIALS_ISLAND_ID
_REQUIRED_ISLANDS = (_FINANCIALS_ISLAND, "company_details", "is_auth")
_TABLE_ISLANDS = _REQUIRED_ISLANDS
# Plan and capability islands are metadata: their absence must never block a
# table whose raw data is present on the page.
_TABLE_OPTIONAL_ISLANDS = (FINANCIALS_LOCKS_ISLAND_ID, PLAN_DETAILS_ISLAND_ID)
_FINANCIALS_PAGE_LABEL = "financials"
_PL_FETCH_FAILED_EVENT = "tijori_pl_fetch_failed"
_SHAREHOLDING_FETCH_FAILED_EVENT = "tijori_shareholding_fetch_failed"
_OVERVIEW_FETCH_FAILED_EVENT = "tijori_overview_fetch_failed"
_ANALYSIS_FETCH_FAILED_EVENT = "tijori_analysis_fetch_failed"


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
    overview_url_template: str = DEFAULT_OVERVIEW_URL_TEMPLATE
    user_agent: str = DEFAULT_USER_AGENT
    request_timeout_seconds: float = 30.0
    max_retries: int = 3
    retry_backoff_seconds: float = 1.0
    max_response_bytes: int = Field(default=DEFAULT_MAX_RESPONSE_BYTES, gt=0)
    expected_company_id: int | None = Field(default=None, gt=0)


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

    def fetch_overview(
        self,
        *,
        slug: str,
        expected_symbol: str,
        expected_company_id: int,
        section: TijoriOverviewSection | None = None,
    ) -> tuple[TijoriOverviewSectionBase, ...]:
        """Fetch the overview sections, binding the response to the caller's identity."""
        credentials = self._config.credentials
        if credentials is None:
            raise TijoriCredentialsError(
                "tijori credentials not provided; skipping Tijori overview acquisition"
            )
        return self.parse_overview_bytes(
            self._fetch_overview_bytes(slug, credentials),
            slug=slug,
            expected_symbol=expected_symbol,
            expected_company_id=expected_company_id,
            source_url=self._config.overview_url_template.format(
                base=self._config.base_url, slug=slug
            ),
            section=section,
        )

    def fetch_analysis(
        self,
        *,
        slug: str,
        symbol: str,
        company_id: int,
        section: TijoriAnalysisSection,
        metric_id: int | None = None,
    ) -> TijoriAnalysisFetch:
        """Fetch and build one analysis API document for one configured issuer.

        ``symbol`` is carried into the artifact as the CONFIGURED identity: these
        responses assert no identity of their own, so the only binding is the
        ``company_id`` this method puts in the URL. The response bytes are
        returned beside the artifact so the caller can retain the exact body the
        recorded ``file_sha256`` was taken over.
        """
        credentials = self._config.credentials
        if credentials is None:
            raise TijoriCredentialsError(
                "tijori credentials not provided; skipping Tijori analysis acquisition"
            )
        if section in METRIC_SECTIONS and metric_id is None:
            raise TijoriAnalysisMetricIdError(METRIC_ID_REQUIRED)
        url = self.analysis_url(section, company_id=company_id, metric_id=metric_id)
        raw = self._fetch_page_bytes(
            url, slug=slug, credentials=credentials, fetch_event=_ANALYSIS_FETCH_FAILED_EVENT
        )
        return TijoriAnalysisFetch(
            document=build_tijori_analysis(
                raw,
                section=section,
                slug=slug,
                symbol=symbol,
                company_id=company_id,
                source_url=url,
                content_sha256=hashlib.sha256(raw).hexdigest(),
                retrieved_at=datetime.now(tz=UTC),
                metric_id=metric_id,
            ),
            raw_body=raw,
        )

    def analysis_url(
        self, section: TijoriAnalysisSection, *, company_id: int, metric_id: int | None = None
    ) -> str:
        """Build one analysis API URL, keeping the trailing slash the API requires."""
        path = SECTION_PATHS[section]
        if section in METRIC_SECTIONS:
            if metric_id is None:
                raise TijoriAnalysisMetricIdError(METRIC_ID_REQUIRED)
            path = path.format(company_id=company_id, metric_id=metric_id)
        else:
            path = path.format(company_id=company_id)
        return f"{self._config.base_url}{path}"

    @staticmethod
    def parse_overview_bytes(
        raw: bytes,
        *,
        slug: str,
        expected_symbol: str,
        expected_company_id: int,
        source_url: str | None = None,
        section: TijoriOverviewSection | None = None,
    ) -> tuple[TijoriOverviewSectionBase, ...]:
        """Parse the typed data sections from a verified overview page."""
        return build_tijori_overview(
            raw,
            slug=slug,
            expected_symbol=expected_symbol,
            expected_company_id=expected_company_id,
            source_url=source_url
            or DEFAULT_OVERVIEW_URL_TEMPLATE.format(base=DEFAULT_BASE_URL, slug=slug),
            retrieved_at=datetime.now(tz=UTC),
            section=section,
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

    def _fetch_overview_bytes(self, slug: str, credentials: TijoriCredentials) -> bytes:
        """Fetch one complete authenticated overview page without redirects."""
        url = self._config.overview_url_template.format(base=self._config.base_url, slug=slug)
        return self._fetch_page_bytes(
            url, slug=slug, credentials=credentials, fetch_event=_OVERVIEW_FETCH_FAILED_EVENT
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
        islands, company_id, response_symbol = cls._verified_page_islands(
            raw,
            expected_symbol=expected_symbol,
            expected_company_id=expected_company_id,
            required_islands=_REQUIRED_ISLANDS,
        )
        payload = build_pl_payload(
            islands,
            slug=slug,
            company_id=company_id,
            symbol=response_symbol,
            period_end=period_end,
            source_url=source_url
            or DEFAULT_PL_URL_TEMPLATE.format(base=DEFAULT_BASE_URL, slug=slug),
        )
        return cls.parse_pl(payload, content_sha256=hashlib.sha256(raw).hexdigest())

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
        company_details = as_object(islands["company_details"], "company_details")
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

    @classmethod
    def parse_pl(cls, payload: TijoriPlPayload, *, content_sha256: str) -> tuple[Observation, ...]:
        """Map the selected consolidated P&L rows to derived observations."""
        return pl_observations(payload, content_sha256=content_sha256)
