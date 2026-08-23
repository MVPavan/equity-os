"""Fetch BSE first-party quarterly results for cross-checking the NSE Ind AS filing.

BSE is the *second* first-party host for the same issuer results already ingested
from NSE (see :mod:`fundamentals.ingest.xbrl_source`): a second independent
first-party source gives the Fundamentals reconciliation a built-in cross-check.

There are two ways in, in priority order:

* **``resultsSnapshot`` (default).** The installed ``bse`` library (v3.3.1) exposes
  a real ``resultsSnapshot(scripcode)`` endpoint that returns BSE's own results
  summary — Revenue, Net Profit, EPS, Cash EPS, OPM %, NPM % — for the *latest*
  ~2 quarters plus the current fiscal year. This is a first-party (BSE-hosted),
  *summary-level* source (not the full XBRL line items). It cannot serve arbitrary
  historical quarters: it only exposes whatever columns BSE currently publishes.
* **Static ``/XBRLFILES/*.xml`` (secondary).** If an explicit ``xbrl_url`` is
  passed, the full Ind AS XBRL instance is pulled with a plain HTTP client and
  parsed by the shared context-aware parser. There is no filing-index resolver:
  the ``bse`` library has no XBRL-index API, so the URL must be supplied.

Rights posture: BSE access here is owner-authorized private, non-commercial use
(``A05-DECISION-004`` + bd memory ``preapproval-goal-multistock-validation-2026-08-21``)
— polite, low-volume, no anti-bot evasion, no redistribution, no external upload.

Both paths fail closed. The summary path is *skippable* fail-closed: a request for
a quarter BSE no longer publishes returns zero observations plus a structured note
rather than raising or fabricating. The XBRL path is *hard* fail-closed: any
network failure, malformed download, or scope/period/issuer mismatch raises a
typed :class:`BseFetchError` and produces no record. A terminal hard block
(403/auth/CAPTCHA) is classified and never retried (the M10 pattern).
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from pathlib import Path
from typing import Any, TypeVar
from urllib.parse import urlsplit

import structlog
from lxml import etree  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.observation import (
    AccountingFramework,
    Observation,
    PeriodType,
    Scope,
)
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.extract.xbrl_parser import TaxonomySpec, parse_observations
from fundamentals.extract.xbrl_taxonomies import _ALL_TAXONOMIES

_LOGGER = structlog.get_logger(__name__)

_T = TypeVar("_T")

# --- Source identity ----------------------------------------------------------

SOURCE_ID = "bse-xbrl"
SUMMARY_SOURCE_ID = "bse-summary"
ENTITY_SCHEME = "bse-scrip"
DEFAULT_USER_AGENT = "EquityOS Research (mvpavan42@gmail.com)"
USER_AGENT_HEADER = "User-Agent"

# The results summary is read from BSE's own results endpoint (the same host the
# ``bse`` library queries); this is recorded as the retrieval URL for provenance.
BSE_RESULTS_URL_TEMPLATE = (
    "https://api.bseindia.com/BseIndiaAPI/api/TabResults_PAR/w?scripcode={scrip}&tabtype=RESULTS"
)

# BSE served the results XBRL under two taxonomies across FY25: ``in-bse-fin``
# through Q3 FY25 and ``in-capmkt`` (the "Integrated Filing" format) from Q4 FY25
# onward. The parser dispatches by scope concept through a taxonomy registry, so
# BSE support is additive: reuse the shipped ``in-bse-fin`` spec and add
# ``in-capmkt``. NOTE: the ``in-capmkt`` namespace URI below must be confirmed
# against a real Integrated Filing instance; the committed fixture declares the
# same value so the deterministic test is self-consistent, but live parsing of a
# real ``in-capmkt`` instance requires the confirmed production URI.
# --- Summary concept mapping (BSE row title -> canonical concept) --------------
# The three cross-checkable rows use the *exact* concept QNames the NSE parser and
# reconciler config use (see fundamentals.api.config), so the reconciler compares
# them column-for-column. The remaining rows are BSE-only summary extras carried
# under descriptive QNames; they have no NSE counterpart and simply add coverage.

CONCEPT_REVENUE = "in-bse-fin:RevenueFromOperations"
CONCEPT_NET_PROFIT = "in-bse-fin:ProfitLossForPeriod"
CONCEPT_EPS = "in-bse-fin:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations"
CONCEPT_CASH_EPS = "in-bse-fin:CashEarningsLossPerShare"
CONCEPT_OPM = "in-bse-fin:OperatingProfitMarginPercent"
CONCEPT_NPM = "in-bse-fin:NetProfitMarginPercent"


class SummaryUnit(StrEnum):
    """The unit family a summary row carries, driving its normalization."""

    MONETARY_CRORE = "monetary_crore"
    PER_SHARE = "per_share"
    PERCENT = "percent"


class SummaryConcept(BaseModel):
    """A canonical concept plus the unit family for one BSE summary row."""

    model_config = ConfigDict(frozen=True)

    concept_qname: str
    unit: SummaryUnit


# Keyed by the normalized (lower-cased, stripped) BSE row title.
_BSE_ROW_CONCEPTS: dict[str, SummaryConcept] = {
    "revenue": SummaryConcept(concept_qname=CONCEPT_REVENUE, unit=SummaryUnit.MONETARY_CRORE),
    "net profit": SummaryConcept(concept_qname=CONCEPT_NET_PROFIT, unit=SummaryUnit.MONETARY_CRORE),
    "eps": SummaryConcept(concept_qname=CONCEPT_EPS, unit=SummaryUnit.PER_SHARE),
    "cash eps": SummaryConcept(concept_qname=CONCEPT_CASH_EPS, unit=SummaryUnit.PER_SHARE),
    "opm %": SummaryConcept(concept_qname=CONCEPT_OPM, unit=SummaryUnit.PERCENT),
    "npm %": SummaryConcept(concept_qname=CONCEPT_NPM, unit=SummaryUnit.PERCENT),
}

_CURRENCY_INR = "INR"
_CRORE_UNIT = "INR crore"
_CRORE_SCALE = 10_000_000
_CRORE_DECIMALS = -7
_PER_SHARE_UNIT = "INR per share"
_PER_SHARE_SCALE = 1
_PER_SHARE_DECIMALS = 2
_PERCENT_UNIT = "percent"
_PERCENT_SCALE = 1
_PERCENT_DECIMALS = 2

# (currency, normalized_unit, scale, decimals) per unit family. Monetary rows keep
# scale 10**7 / decimals -7 so an "INR crore" value cross-checks against the NSE
# XBRL crore value under the same comparison key (see verify.comparison_key).
_SUMMARY_UNIT_SPEC: dict[SummaryUnit, tuple[str | None, str, int, int]] = {
    SummaryUnit.MONETARY_CRORE: (_CURRENCY_INR, _CRORE_UNIT, _CRORE_SCALE, _CRORE_DECIMALS),
    SummaryUnit.PER_SHARE: (_CURRENCY_INR, _PER_SHARE_UNIT, _PER_SHARE_SCALE, _PER_SHARE_DECIMALS),
    SummaryUnit.PERCENT: (None, _PERCENT_UNIT, _PERCENT_SCALE, _PERCENT_DECIMALS),
}

_RESULTS_IN_CRORES_KEY = "results_in_crores"
_FIELDS_KEY = "fields"
_DATA_KEY = "data"
_PERIODS_KEY = "periods"
_CURRENCY_UNIT_KEY = "currency_unit"

_MISSING_MARKERS = frozenset({"", "-", "—", "na", "n/a", "null", "nil"})

# --- Period-label parsing -----------------------------------------------------
# BSE columns are "Mon-YY" quarter labels (e.g. "Jun-26" = the quarter ending
# June 2026) or "FYaa-bb" fiscal-year labels (e.g. "FY25-26" = Apr 2025..Mar 2026).

_QUARTER_LABEL_RE = re.compile(r"^([A-Za-z]{3})-(\d{2})$")
_FY_LABEL_RE = re.compile(r"^FY(\d{2})-(\d{2})$")
_CENTURY = 2000

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
# Quarter-end month -> (start month, start day, end month, end day) within one year.
_QUARTER_BOUNDS: dict[int, tuple[int, int, int, int]] = {
    3: (1, 1, 3, 31),
    6: (4, 1, 6, 30),
    9: (7, 1, 9, 30),
    12: (10, 1, 12, 31),
}

# --- Fetch tunables -----------------------------------------------------------

DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 2.0

# --- URL / host safety --------------------------------------------------------

HTTPS_SCHEME = "https"
BSE_HOST_SUFFIX = "bseindia.com"
XBRLFILES_PATH_MARKER = "/xbrlfiles/"
XBRL_LINK_SUFFIX = ".xml"

# --- XBRL namespaces / scope --------------------------------------------------

NS_XBRLI = "http://www.xbrl.org/2003/instance"
_XBRLI = f"{{{NS_XBRLI}}}"

# --- Terminal-block classification (M10 pattern; see xbrl_source) --------------

_TERMINAL_HTTP_CODES = frozenset({401, 403, 407, 451})
_TERMINAL_MARKERS: tuple[str, ...] = (
    "403",
    "401",
    "forbidden",
    "unauthorized",
    "unauthorised",
    "captcha",
    "access denied",
    "blocked",
    "authentication",
)


class BseFetchError(Exception):
    """Typed, resumable failure: the fetch produced no trustworthy filing."""


class BseHardBlockError(BseFetchError):
    """A terminal provider block (403/auth/CAPTCHA): stop immediately, do not retry."""


def _is_terminal_error(exc: Exception) -> bool:
    """Classify whether an exception represents a terminal hard block."""
    code = getattr(exc, "code", None) or getattr(exc, "status", None)
    if isinstance(code, int) and code in _TERMINAL_HTTP_CODES:
        return True
    message = str(exc).lower()
    return any(marker in message for marker in _TERMINAL_MARKERS)


def _snapshot_sha256(snapshot: dict[str, Any]) -> str:
    """Stable content hash of a resultsSnapshot dict for provenance."""
    canonical = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _parse_indian_decimal(raw: str) -> Decimal | None:
    """Parse an Indian-grouped numeric cell to Decimal; ``None`` if it is empty.

    Commas and spaces are stripped and a parenthesised value (BSE's negative
    notation) is negated. A missing marker returns ``None`` so the row is skipped
    rather than fabricated.
    """
    text = raw.strip()
    if text.lower() in _MISSING_MARKERS:
        return None
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    text = text.replace(",", "").replace(" ", "")
    if not text or text.lower() in _MISSING_MARKERS:
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    return -value if negative else value


def _period_bounds(label: str) -> tuple[date, date]:
    """Resolve a BSE column label to its ``(period_start, period_end)`` dates.

    Handles a "Mon-YY" quarter label and a "FYaa-bb" fiscal-year label; raises
    :class:`ValueError` for any other shape so an unrecognised column fails closed.
    """
    quarter = _QUARTER_LABEL_RE.match(label)
    if quarter is not None:
        month = _MONTH_ABBREV.get(quarter.group(1).lower())
        if month is None or month not in _QUARTER_BOUNDS:
            raise ValueError(f"not a quarter-end month: {label!r}")
        year = _CENTURY + int(quarter.group(2))
        start_month, start_day, end_month, end_day = _QUARTER_BOUNDS[month]
        return date(year, start_month, start_day), date(year, end_month, end_day)
    fiscal = _FY_LABEL_RE.match(label)
    if fiscal is not None:
        start_year = _CENTURY + int(fiscal.group(1))
        end_year = _CENTURY + int(fiscal.group(2))
        return date(start_year, 4, 1), date(end_year, 3, 31)
    raise ValueError(f"unrecognised BSE period label: {label!r}")


class BseSummaryResult(BaseModel):
    """Outcome of one ``resultsSnapshot`` read for a requested period column.

    ``observations`` is empty and ``note`` is set (never both raising and
    fabricating) when the requested period is not among the exposed columns or the
    label cannot be resolved — the skippable fail-closed contract for the summary
    source.
    """

    model_config = ConfigDict(frozen=True)

    source_id: str
    scrip_code: str
    results_url: str
    snapshot_sha256: str
    currency_unit: str
    requested_period: str
    available_periods: tuple[str, ...]
    observations: tuple[Observation, ...]
    retrieved_at: datetime
    note: str | None = None


class BseRetrieval(BaseModel):
    """Immutable record of one verified BSE XBRL download and its provenance."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    local_path: Path
    file_sha256: str
    xbrl_url: str
    scrip_code: str
    from_date: date
    to_date: date
    consolidated: bool
    retrieved_at: datetime
    filed_at: datetime | None = None

    def provenance(self, *, context_ref: str = "OneD") -> Provenance:
        """Build the file-level XBRL provenance for the held instance."""
        return Provenance(
            source_id=self.source_id,
            file_sha256=self.file_sha256,
            anchor_type=SourceAnchorType.XBRL_CONTEXT,
            context_ref=context_ref,
            retrieved_at=self.retrieved_at,
            filed_at=self.filed_at,
        )


class BseSource:
    """Polite, fail-closed BSE results reader (summary default, XBRL secondary).

    ``fetch_summary`` reads BSE's own ``resultsSnapshot`` summary and is the
    default path. ``fetch_quarter`` / ``fetch_observations`` pull and verify a full
    Ind AS XBRL instance from an explicit ``/XBRLFILES/*.xml`` link, delegating the
    parse to :func:`fundamentals.extract.xbrl_parser.parse_observations`.
    """

    def __init__(
        self,
        download_folder: Path,
        *,
        scrip_code: str,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
    ) -> None:
        self._download_folder = download_folder
        self._scrip_code = scrip_code.strip()
        self._user_agent = user_agent
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds

    # -- Summary path (resultsSnapshot; default) ------------------------------

    def fetch_summary(self, *, period_label: str) -> BseSummaryResult:
        """Read BSE's results summary and map the requested period column.

        Calls the ``bse`` library's ``resultsSnapshot`` (bounded retries, terminal
        block classified and not retried, session always closed), then maps the
        ``results_in_crores`` rows for ``period_label`` to observations. If BSE no
        longer exposes that quarter the result carries zero observations and a
        structured note — skippable fail-closed, never fabricated.
        """
        self._download_folder.mkdir(parents=True, exist_ok=True)
        retrieved_at = datetime.now(UTC)
        snapshot = self._retry("BSE resultsSnapshot", self._fetch_snapshot)
        return self.parse_summary(
            snapshot,
            period_label=period_label,
            scrip_code=self._scrip_code,
            results_url=self._results_url(),
            retrieved_at=retrieved_at,
        )

    def _fetch_snapshot(self) -> dict[str, Any]:
        """Call ``resultsSnapshot`` on a fresh ``bse`` client, closing it always."""
        bse_client_cls = self._load_bse_client_class()
        client = bse_client_cls(download_folder=self._download_folder)
        try:
            snapshot = client.resultsSnapshot(self._scrip_code)
        finally:
            client.exit()
        if not isinstance(snapshot, dict):
            kind = type(snapshot).__name__
            raise BseFetchError(f"resultsSnapshot returned {kind}, expected dict")
        return dict(snapshot)

    def _results_url(self) -> str:
        """The BSE results endpoint URL recorded in provenance for this scrip."""
        return BSE_RESULTS_URL_TEMPLATE.format(scrip=self._scrip_code)

    @staticmethod
    def parse_summary(
        snapshot: dict[str, Any],
        *,
        period_label: str,
        scrip_code: str,
        results_url: str,
        retrieved_at: datetime,
    ) -> BseSummaryResult:
        """Map a ``resultsSnapshot`` dict's requested column to observations.

        Deterministic and network-free: selects the ``period_label`` column of
        ``results_in_crores`` and builds one observation per mapped row. Returns a
        zero-observation result with a structured note when the period is not
        exposed or its label cannot be resolved.
        """
        periods = tuple(str(period) for period in snapshot.get(_PERIODS_KEY, []))
        currency_unit = str(snapshot.get(_CURRENCY_UNIT_KEY, ""))
        snapshot_sha256 = _snapshot_sha256(snapshot)

        def _empty(note: str) -> BseSummaryResult:
            return BseSummaryResult(
                source_id=SUMMARY_SOURCE_ID,
                scrip_code=scrip_code,
                results_url=results_url,
                snapshot_sha256=snapshot_sha256,
                currency_unit=currency_unit,
                requested_period=period_label,
                available_periods=periods,
                observations=(),
                retrieved_at=retrieved_at,
                note=note,
            )

        table = snapshot.get(_RESULTS_IN_CRORES_KEY, {})
        fields = [str(field) for field in table.get(_FIELDS_KEY, [])]
        if period_label not in periods or period_label not in fields:
            return _empty(
                "bse resultsSnapshot only exposes latest quarters; "
                f"{period_label} not available (available: {list(periods)})"
            )
        try:
            period_start, period_end = _period_bounds(period_label)
        except ValueError as error:
            return _empty(f"bse resultsSnapshot period column unresolved: {error}")

        column = fields.index(period_label)
        context_prefix = f"{results_url}#results/{period_label}"
        observations = _map_rows(
            table.get(_DATA_KEY, []),
            column=column,
            scrip_code=scrip_code,
            period_start=period_start,
            period_end=period_end,
            snapshot_sha256=snapshot_sha256,
            context_prefix=context_prefix,
            retrieved_at=retrieved_at,
        )
        note = None if observations else "bse resultsSnapshot exposed no mapped summary rows"
        return BseSummaryResult(
            source_id=SUMMARY_SOURCE_ID,
            scrip_code=scrip_code,
            results_url=results_url,
            snapshot_sha256=snapshot_sha256,
            currency_unit=currency_unit,
            requested_period=period_label,
            available_periods=periods,
            observations=observations,
            retrieved_at=retrieved_at,
            note=note,
        )

    # -- Public XBRL parse hand-off (deterministic, no network) ---------------

    @staticmethod
    def parse(
        xml_bytes: bytes,
        *,
        file_sha256: str,
        retrieved_at: datetime,
    ) -> tuple[Observation, ...]:
        """Parse held BSE XBRL bytes into observations via the shared parser.

        Stamps every observation's provenance with ``source_id="bse-xbrl"`` and
        dispatches concept resolution through :data:`_ALL_TAXONOMIES`, so a filing
        under either the ``in-bse-fin`` or ``in-capmkt`` taxonomy is handled and an
        instance under neither fails closed (never yields an empty result).
        """
        return parse_observations(
            xml_bytes,
            source_id=SOURCE_ID,
            file_sha256=file_sha256,
            retrieved_at=retrieved_at,
            taxonomies=_ALL_TAXONOMIES,
        )

    # -- XBRL fetch + verify + parse (secondary; explicit url) ----------------

    def fetch_quarter(
        self,
        *,
        from_date: date,
        to_date: date,
        consolidated: bool = True,
        xbrl_url: str | None = None,
    ) -> BseRetrieval:
        """Fetch, verify and stamp the BSE Ind AS XBRL for one quarter.

        ``xbrl_url`` (a static ``/XBRLFILES/*.xml`` link) is required: the ``bse``
        library exposes no XBRL filing index, so there is nothing to resolve from.
        Raises :class:`BseFetchError` (producing no record) when the URL is absent
        or on any network failure, malformed download, or scope/period/issuer
        mismatch. Use :meth:`fetch_summary` for the default resultsSnapshot path.
        """
        if xbrl_url is None:
            raise BseFetchError(
                "fetch_quarter requires an explicit xbrl_url (a static /XBRLFILES/*.xml "
                "link); the bse library has no XBRL index — use fetch_summary() for the "
                "resultsSnapshot path"
            )
        self._download_folder.mkdir(parents=True, exist_ok=True)
        retrieved_at = datetime.now(UTC)

        self._validate_xbrl_url(xbrl_url)
        xml_bytes = self._download(xbrl_url)
        self._verify(xml_bytes, from_date=from_date, to_date=to_date, consolidated=consolidated)
        local_path = self._persist(xml_bytes, xbrl_url)
        file_sha256 = hashlib.sha256(xml_bytes).hexdigest()

        _LOGGER.info(
            "bse_xbrl_fetched",
            scrip_code=self._scrip_code,
            from_date=from_date.isoformat(),
            to_date=to_date.isoformat(),
            consolidated=consolidated,
            file_sha256=file_sha256,
        )
        return BseRetrieval(
            source_id=SOURCE_ID,
            local_path=local_path,
            file_sha256=file_sha256,
            xbrl_url=xbrl_url,
            scrip_code=self._scrip_code,
            from_date=from_date,
            to_date=to_date,
            consolidated=consolidated,
            retrieved_at=retrieved_at,
        )

    def fetch_observations(
        self,
        *,
        from_date: date,
        to_date: date,
        consolidated: bool = True,
        xbrl_url: str | None = None,
    ) -> tuple[Observation, ...]:
        """Fetch one quarter's XBRL (explicit ``xbrl_url``) and return observations."""
        retrieval = self.fetch_quarter(
            from_date=from_date,
            to_date=to_date,
            consolidated=consolidated,
            xbrl_url=xbrl_url,
        )
        return self.parse(
            retrieval.local_path.read_bytes(),
            file_sha256=retrieval.file_sha256,
            retrieved_at=retrieval.retrieved_at,
        )

    # -- Internals ------------------------------------------------------------

    def _retry(self, description: str, action: Callable[[], _T]) -> _T:
        """Run ``action`` with bounded retries and linear backoff, failing closed.

        A terminal hard block (403/auth/CAPTCHA/explicit block) stops immediately
        and is surfaced as :class:`BseHardBlockError`; only timeouts and other
        transient failures are retried.
        """
        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                return action()
            except Exception as exc:  # noqa: BLE001 - re-raised as typed failure below
                if _is_terminal_error(exc):
                    raise BseHardBlockError(
                        f"{description} hit a terminal block; not retrying: {exc}"
                    ) from exc
                last_error = exc
                _LOGGER.warning(
                    "bse_fetch_retry", action=description, attempt=attempt + 1, error=str(exc)
                )
                if attempt + 1 < self._max_retries:
                    time.sleep(self._retry_backoff_seconds * (attempt + 1))
        raise BseFetchError(
            f"{description} failed after {self._max_retries} attempts: {last_error}"
        ) from last_error

    def _load_bse_client_class(self) -> Any:
        """Lazily import the ``bse`` client class, failing closed if unavailable."""
        try:
            from bse import BSE  # type: ignore[import-untyped]
        except ImportError as exc:
            raise BseFetchError(
                "the 'bse' library is required for the resultsSnapshot path; install it"
            ) from exc
        return BSE

    def _download(self, xbrl_url: str) -> bytes:
        """Download the static XBRL instance over plain HTTP, failing closed."""
        request = urllib.request.Request(xbrl_url, headers={USER_AGENT_HEADER: self._user_agent})
        return self._retry("BSE XBRL download", lambda: self._http_get(request))

    def _http_get(self, request: urllib.request.Request) -> bytes:
        """Perform one bounded-timeout GET, returning the body bytes."""
        with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
            payload: bytes = response.read()
        if not payload:
            raise BseFetchError("BSE XBRL download returned an empty body")
        return payload

    def _persist(self, xml_bytes: bytes, xbrl_url: str) -> Path:
        """Write verified bytes into the held folder, named from the URL."""
        name = Path(urlsplit(xbrl_url).path).name or f"{self._scrip_code}.xml"
        local_path = self._download_folder / name
        local_path.write_bytes(xml_bytes)
        return local_path

    def _validate_xbrl_url(self, xbrl_url: str) -> None:
        """Reject any URL that is not a first-party static BSE ``/XBRLFILES/*.xml``.

        This is a rights/safety guard, not evasion: it confines fetches to the
        static XBRL asset host and refuses arbitrary or non-BSE targets.
        """
        parts = urlsplit(xbrl_url)
        host = parts.hostname or ""
        path = parts.path.lower()
        if parts.scheme != HTTPS_SCHEME:
            raise BseFetchError(f"XBRL url must be https, got {xbrl_url!r}")
        if not (host == BSE_HOST_SUFFIX or host.endswith(f".{BSE_HOST_SUFFIX}")):
            raise BseFetchError(f"XBRL url host {host!r} is not a BSE first-party host")
        if XBRLFILES_PATH_MARKER not in path or not path.endswith(XBRL_LINK_SUFFIX):
            raise BseFetchError(f"XBRL url is not a static /XBRLFILES/*.xml asset: {xbrl_url!r}")

    def _verify(
        self, xml_bytes: bytes, *, from_date: date, to_date: date, consolidated: bool
    ) -> None:
        """Reject a download whose scope, period, or issuer does not match the request."""
        try:
            root = etree.fromstring(xml_bytes)
        except etree.XMLSyntaxError as exc:
            raise BseFetchError(f"downloaded XBRL is not well-formed: {exc}") from exc

        spec = self._detect_spec(root)
        self._verify_scope(root, spec, consolidated=consolidated)
        self._verify_issuer(root)
        self._verify_period(root, from_date=from_date, to_date=to_date)

    def _detect_spec(self, root: Any) -> TaxonomySpec:
        """Return the single BSE taxonomy whose scope concept the instance declares."""
        matched = [
            spec
            for spec in _ALL_TAXONOMIES
            if root.find(f"{{{spec.namespace}}}{spec.scope_concept}") is not None
        ]
        if len(matched) != 1:
            supported = ", ".join(spec.registry_version for spec in _ALL_TAXONOMIES)
            raise BseFetchError(
                f"downloaded XBRL matches {len(matched)} supported taxonomies "
                f"(expected 1 of: {supported})"
            )
        return matched[0]

    def _verify_scope(self, root: Any, spec: TaxonomySpec, *, consolidated: bool) -> None:
        """Reject a download whose file-level scope is not the requested one."""
        element = root.find(f"{{{spec.namespace}}}{spec.scope_concept}")
        text = (element.text or "").strip() if element is not None else ""
        wanted = spec.consolidated_text if consolidated else spec.standalone_text
        if text != wanted:
            raise BseFetchError(
                f"downloaded XBRL scope {text!r} does not match requested {wanted!r}"
            )

    def _verify_issuer(self, root: Any) -> None:
        """Reject a download whose context entity is not the requested scrip."""
        identifiers = {
            (identifier.text or "").strip()
            for identifier in root.findall(f"{_XBRLI}context/{_XBRLI}entity/{_XBRLI}identifier")
        }
        if self._scrip_code not in identifiers:
            raise BseFetchError(
                f"downloaded XBRL entity {sorted(identifiers)} does not match requested "
                f"scrip {self._scrip_code!r}"
            )

    def _verify_period(self, root: Any, *, from_date: date, to_date: date) -> None:
        """Reject a download that carries no context for the requested quarter."""
        wanted = (from_date.isoformat(), to_date.isoformat())
        for context in root.findall(f"{_XBRLI}context"):
            start = context.find(f"{_XBRLI}period/{_XBRLI}startDate")
            end = context.find(f"{_XBRLI}period/{_XBRLI}endDate")
            if start is None or end is None:
                continue
            if ((start.text or "").strip(), (end.text or "").strip()) == wanted:
                return
        raise BseFetchError(f"downloaded XBRL carries no {from_date}..{to_date} duration context")


def _map_rows(
    rows: list[Any],
    *,
    column: int,
    scrip_code: str,
    period_start: date,
    period_end: date,
    snapshot_sha256: str,
    context_prefix: str,
    retrieved_at: datetime,
) -> tuple[Observation, ...]:
    """Build one observation per mapped summary row for the selected column."""
    observations: list[Observation] = []
    for row in rows:
        cells = list(row)
        if not cells or column >= len(cells):
            continue
        concept = _BSE_ROW_CONCEPTS.get(str(cells[0]).strip().lower())
        if concept is None:
            continue
        raw_value = str(cells[column])
        value = _parse_indian_decimal(raw_value)
        if value is None:
            continue
        observations.append(
            _build_observation(
                concept=concept,
                raw_value=raw_value.strip(),
                value=value,
                scrip_code=scrip_code,
                period_start=period_start,
                period_end=period_end,
                snapshot_sha256=snapshot_sha256,
                context_prefix=context_prefix,
                retrieved_at=retrieved_at,
            )
        )
    return tuple(observations)


def _build_observation(
    *,
    concept: SummaryConcept,
    raw_value: str,
    value: Decimal,
    scrip_code: str,
    period_start: date,
    period_end: date,
    snapshot_sha256: str,
    context_prefix: str,
    retrieved_at: datetime,
) -> Observation:
    """Assemble one summary observation with BSE-summary provenance.

    ``taxonomy_namespace`` / ``registry_version`` are left ``None``: a summary
    figure is not read from a specific XBRL taxonomy, so it must not contradict the
    NSE taxonomy identity during reconciliation (see verify.comparison_key).
    """
    currency, normalized_unit, scale, decimals = _SUMMARY_UNIT_SPEC[concept.unit]
    context_ref = f"{context_prefix}/{concept.concept_qname}"
    provenance = Provenance(
        source_id=SUMMARY_SOURCE_ID,
        file_sha256=snapshot_sha256,
        anchor_type=SourceAnchorType.XBRL_CONTEXT,
        context_ref=context_ref,
        retrieved_at=retrieved_at,
        first_seen_at=retrieved_at,
    )
    return Observation(
        concept_qname=concept.concept_qname,
        raw_value=raw_value,
        normalized_value=value,
        normalized_unit=normalized_unit,
        context_ref=context_ref,
        entity_scheme=ENTITY_SCHEME,
        entity_id=scrip_code,
        scope=Scope.CONSOLIDATED,
        accounting_basis=AccountingFramework.IND_AS,
        period_type=PeriodType.DURATION,
        period_start=period_start,
        period_end=period_end,
        currency=currency,
        scale=scale,
        decimals=decimals,
        provenance=provenance,
    )
