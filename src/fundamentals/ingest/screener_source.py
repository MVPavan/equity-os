"""Screener.in adapter — DERIVED quarterly P&L cross-check source.

Screener.in is a **derived aggregator**: it publishes its own *normalized
restatement* of an issuer's filings, mapped into Screener's line-item schema —
not the issuer's PDFs and not exchange Ind AS XBRL. Every value this adapter
emits is therefore flagged as derived and is fit for **private cross-check
ONLY**, never as a source of record. The reconciler must weight these
observations as a convenience check, not first-party evidence.

Rights posture: A05-DECISION-004 + bd memory
``preapproval-goal-multistock-validation-2026-08-21``. Screener is a derived
aggregator carrying its own (unreviewed) ToS: this adapter uses only the
credential-free public company page (no login, no credentials, no anti-bot
evasion), a declared User-Agent, an explicit timeout, bounded retries, and
terminal classification of 403/429/451 blocks (fail closed, stop — never work
around a block).

How derived-ness is marked (belt and braces so no downstream consumer can
mistake a Screener number for first-party evidence):

* ``provenance.source_id`` is exactly :data:`SOURCE_ID` (``"screener"``);
* every ``concept_qname`` is Screener-namespaced (``"screener:*"``), never an
  ``ifrs-full:``/``ind-as:`` taxonomy qname;
* ``accounting_basis`` is :data:`AccountingFramework.UNKNOWN` — Screener
  restates across standalone/consolidated and its own schema, so the true basis
  is unknown;
* ``provenance.context_ref`` carries the fetched public URL (there is no exact
  page/block/span — the number is aggregated, so no first-party anchor exists);
* the batch wrapper :class:`ScreenerResult` restates ``derived=True`` and
  ``cross_check_only=True`` at the batch level, and :func:`is_derived` restates
  it per observation.
"""

from __future__ import annotations

import calendar
import hashlib
import time
import urllib.error
import urllib.request
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

import structlog
from lxml import html as lxml_html  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.observation import (
    AccountingFramework,
    Observation,
    PeriodType,
    Scope,
)
from fundamentals.contracts.provenance import Provenance, SourceAnchorType

_LOGGER = structlog.get_logger(__name__)

# The single, stable marker that binds every observation to the Screener source.
SOURCE_ID = "screener"

ENTITY_SCHEME = "screener-slug"
USER_AGENT_HEADER = "User-Agent"
DEFAULT_USER_AGENT = "EquityOS Research (mvpavan42@gmail.com)"

# Credential-free public company page. ``consolidated`` appends the /consolidated/
# path variant Screener exposes without a login.
_BASE_URL_TEMPLATE = "https://www.screener.in/company/{slug}/"
_CONSOLIDATED_URL_TEMPLATE = "https://www.screener.in/company/{slug}/consolidated/"

# HTTP statuses that mean "stop": a block or rate-limit, never retried around.
_BLOCK_STATUSES = frozenset({403, 429, 451})

INR = "INR"
INR_CRORE = "INR crore"
INR_PER_SHARE = "INR per share"

# One crore = 1e7 base units; values are reported to whole-crore precision.
_CRORE_SCALE = 10_000_000
_CRORE_DECIMALS = -7
_EPS_SCALE = 1
_EPS_DECIMALS = 2

_MONTH_ABBR_TO_NUMBER: dict[str, int] = {
    abbr: number for number, abbr in enumerate(calendar.month_abbr) if abbr
}


class ScreenerConcept(StrEnum):
    """The headline quarterly P&L line-items this adapter cross-checks.

    All are Screener-namespaced so they can never be footed against a
    first-party XBRL taxonomy concept without an explicit, intentional mapping.
    """

    SALES = "screener:Sales"
    OPERATING_PROFIT = "screener:OperatingProfit"
    NET_PROFIT = "screener:NetProfit"
    EPS = "screener:EPS"


# Screener's row labels (as rendered in the quarterly table) → tracked concept.
_LABEL_TO_CONCEPT: dict[str, ScreenerConcept] = {
    "Sales": ScreenerConcept.SALES,
    "Operating Profit": ScreenerConcept.OPERATING_PROFIT,
    "Net Profit": ScreenerConcept.NET_PROFIT,
    "EPS in Rs": ScreenerConcept.EPS,
}

_PER_SHARE_CONCEPTS = frozenset({ScreenerConcept.EPS})


class ScreenerFetchError(Exception):
    """Typed, resumable failure — raised instead of returning partial data."""


class ScreenerBlockError(ScreenerFetchError):
    """Terminal block/rate-limit (403/429/451) — stop; do not retry or evade."""


class ScreenerSourceConfig(BaseModel):
    """Injected, credential-free settings for the Screener adapter (no env reads)."""

    model_config = ConfigDict(frozen=True)

    slug: str
    consolidated: bool = False
    user_agent: str = DEFAULT_USER_AGENT
    request_timeout_seconds: float = 30.0
    max_retries: int = 3
    retry_backoff_seconds: float = 1.0

    @property
    def url(self) -> str:
        """The credential-free public company-page URL for this slug/view."""
        template = _CONSOLIDATED_URL_TEMPLATE if self.consolidated else _BASE_URL_TEMPLATE
        return template.format(slug=self.slug)


class ScreenerResult(BaseModel):
    """Batch of Screener quarterly P&L observations, flagged derived / cross-check.

    ``derived`` and ``cross_check_only`` are always ``True``: Screener is an
    aggregator restatement, never a source of record.
    """

    model_config = ConfigDict(frozen=True)

    observations: tuple[Observation, ...]
    source_url: str
    file_sha256: str
    retrieved_at: datetime
    derived: bool = True
    cross_check_only: bool = True


def is_derived(observation: Observation) -> bool:
    """True when the observation is a Screener-derived cross-check value."""
    return observation.provenance.source_id == SOURCE_ID


def _clean_label(raw: str) -> str:
    """Normalize a Screener row label: drop the ``+`` expander and whitespace."""
    return raw.replace("+", " ").split("\xa0")[0].strip()


def _parse_quarter_period(label: str) -> tuple[date, date]:
    """Map a Screener quarter header (e.g. ``"Jun 2023"``) to (start, end) dates.

    A ``Mmm YYYY`` header names the month the fiscal quarter *ends*; the quarter
    spans the three months ending there.
    """
    parts = label.split()
    if len(parts) != 2:
        raise ScreenerFetchError(f"unrecognized quarter header: {label!r}")
    month = _MONTH_ABBR_TO_NUMBER.get(parts[0])
    if month is None:
        raise ScreenerFetchError(f"unrecognized quarter month: {label!r}")
    try:
        year = int(parts[1])
    except ValueError as error:
        raise ScreenerFetchError(f"unrecognized quarter year: {label!r}") from error
    start_month = month - 2
    if start_month < 1:
        raise ScreenerFetchError(f"quarter header is not a fiscal quarter-end: {label!r}")
    period_start = date(year, start_month, 1)
    period_end = date(year, month, calendar.monthrange(year, month)[1])
    return period_start, period_end


def _parse_decimal(raw: str) -> Decimal | None:
    """Parse a Screener numeric cell (Indian comma grouping) or ``None`` if empty."""
    text = raw.strip()
    if text in ("", "-"):
        return None
    try:
        return Decimal(text.replace(",", ""))
    except InvalidOperation:
        return None


def _cell_text(cell: Any) -> str:
    """Flatten a table cell's text content into a single stripped string."""
    return "".join(cell.itertext()).strip()


def parse_quarterly_pnl(
    html_text: str,
    *,
    source_url: str,
    file_sha256: str,
    entity_id: str,
    consolidated: bool,
    retrieved_at: datetime,
) -> tuple[Observation, ...]:
    """Parse Screener's quarterly P&L table into derived :class:`Observation`s.

    Pure and deterministic: takes the page HTML and the provenance context, and
    returns one observation per (tracked concept × quarter) cell that carries a
    value. Every observation is flagged derived (see module docstring). Raises
    :class:`ScreenerFetchError` when the quarterly table is absent or malformed.
    """
    root = lxml_html.fromstring(html_text)
    tables = root.xpath("//section[@id='quarters']//table")
    if not tables:
        raise ScreenerFetchError("quarterly results table not found on Screener page")
    table = tables[0]

    header_cells = table.xpath(".//thead//th")
    # The first header cell is the (empty) row-label column; the rest are quarters.
    quarter_labels = [_cell_text(cell) for cell in header_cells[1:]]
    if not quarter_labels:
        raise ScreenerFetchError("no quarter columns found in Screener quarterly table")
    quarter_periods = [_parse_quarter_period(label) for label in quarter_labels]

    scope = Scope.CONSOLIDATED if consolidated else Scope.STANDALONE
    observations: list[Observation] = []
    for row in table.xpath(".//tbody//tr"):
        cells = row.xpath("./td")
        if not cells:
            continue
        concept = _LABEL_TO_CONCEPT.get(_clean_label(_cell_text(cells[0])))
        if concept is None:
            continue
        for index, value_cell in enumerate(cells[1:]):
            if index >= len(quarter_periods):
                break
            observation = _build_observation(
                concept=concept,
                raw_value=_cell_text(value_cell),
                period=quarter_periods[index],
                scope=scope,
                entity_id=entity_id,
                source_url=source_url,
                file_sha256=file_sha256,
                retrieved_at=retrieved_at,
            )
            if observation is not None:
                observations.append(observation)

    if not observations:
        raise ScreenerFetchError("no headline P&L values parsed from Screener quarterly table")
    return tuple(observations)


def _build_observation(
    *,
    concept: ScreenerConcept,
    raw_value: str,
    period: tuple[date, date],
    scope: Scope,
    entity_id: str,
    source_url: str,
    file_sha256: str,
    retrieved_at: datetime,
) -> Observation | None:
    """Build one derived observation, or ``None`` when the cell has no value."""
    normalized_value = _parse_decimal(raw_value)
    if normalized_value is None:
        return None

    if concept in _PER_SHARE_CONCEPTS:
        normalized_unit = INR_PER_SHARE
        scale = _EPS_SCALE
        decimals = _EPS_DECIMALS
    else:
        normalized_unit = INR_CRORE
        scale = _CRORE_SCALE
        decimals = _CRORE_DECIMALS

    period_start, period_end = period
    # No exact page/span exists for an aggregated value: the URL (+concept+period)
    # is the only anchor Screener can provide, so it is the context_ref.
    context_ref = f"{source_url}#{concept.value}@{period_end.isoformat()}"
    provenance = Provenance(
        source_id=SOURCE_ID,
        file_sha256=file_sha256,
        anchor_type=SourceAnchorType.XBRL_CONTEXT,
        context_ref=context_ref,
        retrieved_at=retrieved_at,
    )
    return Observation(
        concept_qname=concept.value,
        raw_value=raw_value,
        normalized_value=normalized_value,
        normalized_unit=normalized_unit,
        context_ref=context_ref,
        entity_scheme=ENTITY_SCHEME,
        entity_id=entity_id,
        scope=scope,
        accounting_basis=AccountingFramework.UNKNOWN,
        period_type=PeriodType.DURATION,
        period_start=period_start,
        period_end=period_end,
        currency=INR,
        scale=scale,
        decimals=decimals,
        provenance=provenance,
    )


class ScreenerSource:
    """Fetches Screener's public quarterly P&L as derived cross-check observations."""

    def __init__(self, config: ScreenerSourceConfig) -> None:
        self._config = config

    def fetch(self) -> ScreenerResult:
        """Fetch and parse the public page, or raise a typed failure.

        Fails closed: on any fetch, block, or parse error no observations are
        returned. The fetched page bytes are hashed once for provenance.
        """
        url = self._config.url
        payload = self._fetch_page(url)
        file_sha256 = hashlib.sha256(payload).hexdigest()
        retrieved_at = datetime.now(tz=UTC)
        observations = parse_quarterly_pnl(
            payload.decode("utf-8", errors="replace"),
            source_url=url,
            file_sha256=file_sha256,
            entity_id=self._config.slug,
            consolidated=self._config.consolidated,
            retrieved_at=retrieved_at,
        )
        _LOGGER.info(
            "loaded screener derived observations",
            count=len(observations),
            slug=self._config.slug,
            consolidated=self._config.consolidated,
            derived=True,
            cross_check_only=True,
        )
        return ScreenerResult(
            observations=observations,
            source_url=url,
            file_sha256=file_sha256,
            retrieved_at=retrieved_at,
        )

    def _fetch_page(self, url: str) -> bytes:
        """GET the public page politely, classifying 403/429/451 as terminal blocks."""
        request = urllib.request.Request(
            url, headers={USER_AGENT_HEADER: self._config.user_agent}
        )
        last_error: Exception | None = None
        for attempt in range(1, self._config.max_retries + 1):
            try:
                with urllib.request.urlopen(
                    request, timeout=self._config.request_timeout_seconds
                ) as response:
                    payload: bytes = response.read()
                return payload
            except urllib.error.HTTPError as error:
                if error.code in _BLOCK_STATUSES:
                    # Terminal: a block or rate-limit. Stop — never retry around it.
                    raise ScreenerBlockError(
                        f"screener returned terminal status {error.code} for {url}"
                    ) from error
                last_error = error
                _LOGGER.warning(
                    "screener fetch http error", attempt=attempt, status=error.code, url=url
                )
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                last_error = error
                _LOGGER.warning("screener fetch failed", attempt=attempt, error=str(error))
            time.sleep(self._config.retry_backoff_seconds * attempt)
        raise ScreenerFetchError(
            f"screener fetch failed after {self._config.max_retries} attempts for {url}"
        ) from last_error
