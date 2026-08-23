"""Tijori adapter — DERIVED quarterly P&L headline numbers for cross-check ONLY.

Tijori (``tijorifinance.com``) is an aggregator that *restates* company
financials behind the owner's authenticated login. Its numbers are therefore
**derived**, never source-of-record: first-party Ind AS XBRL / PDF remain the
spine, and Tijori is a private convenience/cross-check layer (see
``docs/research/tijori-mcp-evaluation.md``). Rights: bounded personal-account
use only (bd memory ``rights-tijori-eval-2026-08-21`` +
``preapproval-goal-multistock-validation-2026-08-21``) — no redistribution.

Every observation this adapter emits is flagged derived: its provenance
``source_id`` is :data:`SOURCE_ID` (``"tijori"``), its ``accounting_basis`` is
``UNKNOWN`` (Tijori discloses no framework and gives no filing-level anchor),
and its ``concept_qname`` carries a ``tijori:`` prefix so a reconciliation layer
never collapses a Tijori restatement onto a first-party fact by label alone —
the fact-identity-collapse the ``Observation`` contract guards against.

Credential handling (STRICT):
    * This module NEVER reads ``os.environ`` and NEVER hard-codes a credential.
      Credentials are injected via :class:`TijoriSourceConfig` at construction;
      the composition root is the only place allowed to read
      ``TIJORI_EMAIL`` / ``TIJORI_PASSWORD`` (and an optional session cookie)
      from the environment and pass them in.
    * If no credentials are injected, :meth:`TijoriSource.fetch_pl` fails closed
      with :class:`TijoriCredentialsError` — a *skippable* typed error the caller
      catches to skip Tijori without hard-failing the pipeline.
    * No credential or session token is ever written to a file by this module.

Provenance anchor limitation (surfaced, not hidden): the frozen ``Provenance``
contract offers only ``PDF_SPAN`` and ``XBRL_CONTEXT`` anchor types — neither
models a scraped web page. This adapter uses ``XBRL_CONTEXT`` with a synthetic
``context_ref`` that embeds the Tijori URL + period + concept locator. That is a
best-fit compromise, not a claim of XBRL provenance; a future ``WEB`` anchor
type would be the correct fix.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

import structlog
from lxml import etree  # type: ignore[import-untyped]
from lxml import html as lxml_html
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

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
DEFAULT_MAX_RESPONSE_BYTES = 5 * 1024 * 1024
_QUARTERLY_WRAPPER_ID = "quarterly_results_table_wrapper"
_QUARTERLY_CONTENT_ID = "company_table_innertab_quarterly_results_content"
_LIVE_DOM_UNVERIFIED_NOTE = "tijori parser unverified against live DOM"
_SCOPE_ASSUMED_NOTE = "scope_assumed=True; Tijori does not disclose statement scope"

_CURRENCY_INR = "INR"
# Tijori reports monetary lines in ₹ crore (1 crore = 10,000,000).
_INR_CRORE_UNIT = "INR crore"
_CRORE_SCALE = 10_000_000
_CRORE_DECIMALS = -7
_EPS_SCALE = 1
_EPS_DECIMALS = 2
_MISSING_MARKERS = frozenset({"", "-", "—", "na", "n/a", "null"})

# Indian fiscal quarter-end months -> (start month, end month, end day).
_QUARTER_BY_END_MONTH: dict[int, tuple[int, int, int]] = {
    3: (1, 3, 31),
    6: (4, 6, 30),
    9: (7, 9, 30),
    12: (10, 12, 31),
}
_MONTH_ABBREV: dict[str, int] = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


class TijoriError(Exception):
    """Base class for Tijori adapter failures."""


class TijoriCredentialsError(TijoriError):
    """No credentials injected — skippable so the pipeline never hard-fails."""


class TijoriFetchError(TijoriError):
    """Terminal fetch/transport failure (never a partial, unverified result)."""


class TijoriParseError(TijoriError):
    """The Tijori payload was malformed or internally inconsistent."""


class TijoriPeriodType(StrEnum):
    """Whether a Tijori column is a full fiscal year or a single quarter."""

    ANNUAL = "annual"
    QUARTER = "quarter"


class TijoriConcept(StrEnum):
    """The P&L headline lines this adapter maps, keyed by canonical qname.

    The ``tijori:`` prefix marks these as Tijori's *derived* restatement so a
    reconciliation layer must explicitly map them onto first-party concepts
    rather than matching on a shared label.
    """

    SALES = "tijori:sales"
    OPERATING_PROFIT = "tijori:operating_profit"
    NET_PROFIT = "tijori:net_profit"
    EPS = "tijori:eps"


# Tijori's scraped row labels -> canonical Tijori concept.
_LABEL_TO_CONCEPT: dict[str, TijoriConcept] = {
    "sales": TijoriConcept.SALES,
    "revenue": TijoriConcept.SALES,
    "operating profit": TijoriConcept.OPERATING_PROFIT,
    "net profit": TijoriConcept.NET_PROFIT,
    "eps": TijoriConcept.EPS,
}
_PER_SHARE_CONCEPTS = frozenset({TijoriConcept.EPS})


class TijoriCredentials(BaseModel):
    """Owner-account auth material, injected at the composition root only.

    ``session_cookie`` (a ``sessionid`` minted by a prior authenticated login)
    is the only credential used by this adapter. No automated login exists; all
    fields stay redacted outside the outbound HTTP request boundary.
    """

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
    live_dom_verified: bool = False


class TijoriPeriod(BaseModel):
    """One column header from a Tijori financials table."""

    model_config = ConfigDict(frozen=True)

    label: str
    type: TijoriPeriodType


class TijoriRow(BaseModel):
    """One line item; ``values`` align positionally with the payload periods."""

    model_config = ConfigDict(frozen=True)

    label: str
    values: tuple[str | None, ...]


class TijoriPlPayload(BaseModel):
    """Parsed shape of a Tijori P&L (`pl`) financials response."""

    model_config = ConfigDict(frozen=True)

    slug: str
    company_id: int
    symbol: str
    url: str
    currency: str
    unit: str
    periods: tuple[TijoriPeriod, ...]
    rows: tuple[TijoriRow, ...]


def is_tijori_derived(observation: Observation) -> bool:
    """True when the observation is a Tijori-derived cross-check value."""
    return (
        observation.provenance.source_id == SOURCE_ID
        and observation.accounting_basis is AccountingFramework.UNKNOWN
    )


def _parse_quarter_label(label: str) -> tuple[date, date]:
    """Map a ``Mon'YY`` quarter label to its (period_start, period_end) dates."""
    cleaned = label.strip().lower().replace("’", "'")
    parts = cleaned.split("'")
    if len(parts) != 2:
        raise TijoriParseError(f"unrecognized quarter label: {label!r}")
    month_key, year_key = parts[0][:3], parts[1]
    end_month = _MONTH_ABBREV.get(month_key)
    if end_month is None or end_month not in _QUARTER_BY_END_MONTH:
        raise TijoriParseError(f"label is not a fiscal quarter end: {label!r}")
    try:
        end_year = 2000 + int(year_key)
    except ValueError as error:
        raise TijoriParseError(f"unparseable year in label {label!r}") from error
    start_month, _, end_day = _QUARTER_BY_END_MONTH[end_month]
    start_year = end_year if start_month <= end_month else end_year - 1
    return date(start_year, start_month, 1), date(end_year, end_month, end_day)


def _normalize_decimal(raw_value: str) -> Decimal:
    """Parse an Indian-formatted numeric string (commas stripped) to Decimal."""
    stripped = raw_value.replace(",", "").strip()
    try:
        return Decimal(stripped)
    except InvalidOperation as error:
        raise TijoriParseError(f"non-numeric Tijori value: {raw_value!r}") from error


def _is_missing(cell: str | None) -> bool:
    """True when a cell carries no reportable value."""
    return cell is None or cell.strip().lower() in _MISSING_MARKERS


def _cell_text(cell: Any) -> str:
    """Flatten one rendered table cell to normalized visible text."""
    return " ".join("".join(cell.itertext()).split())


def _html_cell_value(cell: Any) -> str | None:
    """Return a rendered numeric cell, normalizing Tijori's missing markers."""
    text = _cell_text(cell)
    return None if _is_missing(text) else text


class TijoriSource:
    """Fetches Tijori quarterly P&L headline numbers as derived observations."""

    def __init__(self, config: TijoriSourceConfig | None = None) -> None:
        self._config = config or TijoriSourceConfig()

    def fetch_pl(self, slug: str, *, expected_symbol: str | None = None) -> tuple[Observation, ...]:
        """Fetch and parse a company's quarterly P&L into derived observations.

        Fails closed with :class:`TijoriCredentialsError` (skippable) when no
        credentials are injected, so a caller can drop Tijori without failing
        the pipeline. Transport problems raise :class:`TijoriFetchError`.
        """
        credentials = self._config.credentials
        if credentials is None:
            raise TijoriCredentialsError(
                "tijori credentials not provided; skipping Tijori cross-check"
            )
        if not self._config.live_dom_verified:
            raise TijoriFetchError(_LIVE_DOM_UNVERIFIED_NOTE)
        raw = self._fetch_pl_bytes(slug, credentials)
        source_url = self._config.pl_url_template.format(base=self._config.base_url, slug=slug)
        return self.parse_pl_bytes(
            raw,
            slug=slug,
            source_url=source_url,
            expected_symbol=expected_symbol,
        )

    def _fetch_pl_bytes(self, slug: str, credentials: TijoriCredentials) -> bytes:
        """Fetch the rendered financials page over an authenticated HTTP session."""
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
        )
        last_error: Exception | None = None
        for attempt in range(1, self._config.max_retries + 1):
            try:
                with urllib.request.urlopen(
                    request, timeout=self._config.request_timeout_seconds
                ) as response:
                    payload = bytes(response.read(self._config.max_response_bytes + 1))
                if len(payload) > self._config.max_response_bytes:
                    raise TijoriFetchError(
                        f"tijori response exceeded maximum {self._config.max_response_bytes} bytes"
                    )
                return payload
            except urllib.error.HTTPError as error:
                # 4xx is terminal (auth/slug problem); do not retry blindly.
                if error.code == 404:
                    raise TijoriFetchError(
                        f"tijori slug unverified: {slug!r} returned HTTP 404"
                    ) from error
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

    @classmethod
    def parse_pl_bytes(
        cls,
        raw: bytes,
        *,
        slug: str | None = None,
        source_url: str | None = None,
        expected_symbol: str | None = None,
    ) -> tuple[Observation, ...]:
        """Hash + validate JSON or rendered HTML, then parse derived observations."""
        content_sha256 = hashlib.sha256(raw).hexdigest()
        if raw.lstrip().startswith(b"<"):
            try:
                payload = cls._parse_pl_html(raw, slug=slug, source_url=source_url)
            except ValidationError as error:
                raise TijoriParseError("tijori HTML payload has an invalid schema") from error
            cls._verify_response_identity(payload, slug=slug, expected_symbol=expected_symbol)
            return cls.parse_pl(payload, content_sha256=content_sha256)
        try:
            document = json.loads(raw)
        except json.JSONDecodeError as error:
            raise TijoriParseError("tijori payload is not valid JSON") from error
        try:
            payload = TijoriPlPayload.model_validate(document)
        except ValidationError as error:
            raise TijoriParseError("tijori JSON payload has an invalid schema") from error
        cls._verify_response_identity(payload, slug=slug, expected_symbol=expected_symbol)
        return cls.parse_pl(payload, content_sha256=content_sha256)

    @staticmethod
    def _verify_response_identity(
        payload: TijoriPlPayload, *, slug: str | None, expected_symbol: str | None
    ) -> None:
        """Reject a response whose own identity differs from the requested stock."""
        if slug is not None and payload.slug.casefold() != slug.casefold():
            raise TijoriParseError("tijori response identity mismatch: slug differs from request")
        if expected_symbol is not None and payload.symbol.casefold() != expected_symbol.casefold():
            raise TijoriParseError("tijori response identity mismatch: symbol differs from request")

    @staticmethod
    def _parse_pl_html(raw: bytes, *, slug: str | None, source_url: str | None) -> TijoriPlPayload:
        """Parse Tijori's rendered quarterly-results DataTable into a payload."""
        try:
            root = lxml_html.fromstring(raw)
        except (etree.ParserError, UnicodeDecodeError, ValueError) as error:
            raise TijoriParseError("tijori financials page is not valid HTML") from error
        wrappers = root.xpath(f"//*[@id='{_QUARTERLY_WRAPPER_ID}']")
        if not wrappers:
            wrappers = root.xpath(f"//*[@id='{_QUARTERLY_CONTENT_ID}']")
        if not wrappers:
            raise TijoriParseError(
                "tijori quarterly table not present in returned HTML; page may require rendering"
            )
        wrapper: Any = wrappers[0]
        tables = wrapper.xpath(".//table")
        heads = wrapper.xpath(".//thead")
        if len(tables) != 1 or len(heads) != 1:
            raise TijoriParseError(
                "tijori quarterly wrapper must contain exactly one table and thead"
            )
        table: Any = tables[0]
        header_cells = table.xpath(
            ".//thead//th[contains(concat(' ', normalize-space(@class), ' '), ' headerItem ')]"
        )
        periods = tuple(
            TijoriPeriod(label=_cell_text(cell), type=TijoriPeriodType.QUARTER)
            for cell in header_cells
            if _cell_text(cell)
        )
        if not periods:
            raise TijoriParseError("tijori quarterly table has no period columns")
        rows: list[TijoriRow] = []
        for table_row in table.xpath(".//tbody//tr"):
            label = str(table_row.get("data-id") or "").strip()
            if not label:
                first_cells = table_row.xpath(
                    "./td[contains(concat(' ', normalize-space(@class), ' '), ' firstcol ')]"
                )
                label = _cell_text(first_cells[0]) if first_cells else ""
            if not label:
                continue
            value_cells = table_row.xpath(
                "./td[contains(concat(' ', normalize-space(@class), ' '), ' knowledge ') "
                "and contains(concat(' ', normalize-space(@class), ' '), ' numericvalue ')]"
            )
            values = tuple(_html_cell_value(cell) for cell in value_cells)
            if len(values) != len(periods):
                raise TijoriParseError(
                    f"tijori row {label!r} has {len(values)} values for {len(periods)} periods"
                )
            rows.append(TijoriRow(label=label, values=values))
        resolved_slug = str(wrapper.get("data-slug") or "").strip()
        resolved_url = str(wrapper.get("data-url") or source_url or "").strip()
        if not resolved_slug or not resolved_url:
            raise TijoriParseError("tijori HTML payload is missing slug or source URL context")
        raw_company_id = str(wrapper.get("data-company-id") or "0")
        try:
            company_id = int(raw_company_id)
        except ValueError as error:
            raise TijoriParseError("tijori HTML payload has an invalid company id") from error
        return TijoriPlPayload(
            slug=resolved_slug,
            company_id=company_id,
            symbol=str(wrapper.get("data-symbol") or "").strip(),
            url=resolved_url,
            currency=str(wrapper.get("data-currency") or _CURRENCY_INR).strip(),
            unit=str(wrapper.get("data-unit") or "cr").strip(),
            periods=periods,
            rows=tuple(rows),
        )

    @classmethod
    def parse_pl(cls, payload: TijoriPlPayload, *, content_sha256: str) -> tuple[Observation, ...]:
        """Map quarterly rows of a validated P&L payload to observations.

        Annual columns are skipped: Tijori uses the same ``Mon'YY`` label for a
        fiscal-year and a quarter, and conflating them is exactly the
        fact-identity collapse the contract forbids.
        """
        retrieved_at = datetime.now(tz=UTC)
        observations: list[Observation] = []
        emitted: set[tuple[TijoriConcept, date]] = set()
        for column, period in enumerate(payload.periods):
            if period.type is not TijoriPeriodType.QUARTER:
                continue
            period_start, period_end = _parse_quarter_label(period.label)
            for row in payload.rows:
                concept = _LABEL_TO_CONCEPT.get(row.label.strip().lower())
                if concept is None:
                    continue
                fact_key = (concept, period_end)
                if fact_key in emitted:
                    continue
                cell = cls._cell(row, column, payload.slug)
                if _is_missing(cell):
                    continue
                assert cell is not None  # narrowed by _is_missing
                observations.append(
                    cls._to_observation(
                        payload=payload,
                        concept=concept,
                        period=period,
                        period_start=period_start,
                        period_end=period_end,
                        raw_value=cell,
                        content_sha256=content_sha256,
                        retrieved_at=retrieved_at,
                    )
                )
                emitted.add(fact_key)
        _LOGGER.info(
            "tijori_quarterly_observations_parsed",
            count=len(observations),
            slug=payload.slug,
        )
        return tuple(observations)

    @staticmethod
    def _cell(row: TijoriRow, column: int, slug: str) -> str | None:
        """Return the row's value in ``column``, failing loud on misalignment."""
        if column >= len(row.values):
            raise TijoriParseError(
                f"tijori row {row.label!r} for {slug!r} has fewer values than periods"
            )
        return row.values[column]

    @staticmethod
    def _to_observation(
        *,
        payload: TijoriPlPayload,
        concept: TijoriConcept,
        period: TijoriPeriod,
        period_start: date,
        period_end: date,
        raw_value: str,
        content_sha256: str,
        retrieved_at: datetime,
    ) -> Observation:
        """Build one DERIVED observation from a single Tijori quarterly cell."""
        normalized_value = _normalize_decimal(raw_value)
        if concept in _PER_SHARE_CONCEPTS:
            normalized_unit = payload.currency
            scale = _EPS_SCALE
            decimals = _EPS_DECIMALS
        else:
            normalized_unit = _INR_CRORE_UNIT
            scale = _CRORE_SCALE
            decimals = _CRORE_DECIMALS
        context_ref = f"{payload.url}#pl/{period.label}/{concept.value}"
        provenance = Provenance(
            source_id=SOURCE_ID,
            file_sha256=content_sha256,
            anchor_type=SourceAnchorType.XBRL_CONTEXT,
            context_ref=context_ref,
            retrieved_at=retrieved_at,
            first_seen_at=retrieved_at,
        )
        return Observation(
            concept_qname=concept.value,
            raw_value=raw_value,
            normalized_value=normalized_value,
            normalized_unit=normalized_unit,
            context_ref=context_ref,
            entity_scheme=ENTITY_SCHEME,
            entity_id=payload.slug,
            scope=Scope.CONSOLIDATED,
            accounting_basis=AccountingFramework.UNKNOWN,
            period_type=PeriodType.DURATION,
            period_start=period_start,
            period_end=period_end,
            currency=payload.currency,
            scale=scale,
            decimals=decimals,
            provenance=provenance,
        )
