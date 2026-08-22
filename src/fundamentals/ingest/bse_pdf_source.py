"""Fetch the issuer's quarterly results PDF from BSE corporate announcements.

This is the *second first-party* source for the same issuer results already
ingested from the NSE Ind AS XBRL: the BSE-hosted results PDF the company itself
filed. Parsed deterministically (see
:mod:`fundamentals.extract.pdf_number_parser`) it gives the reconciliation two
independent first-party readings of the same consolidated quarter.

Flow (all bounded, all fail-closed):

1. **Locate** the results filing via the installed ``bse`` library's
   ``announcements(scripcode, from_date, to_date, category="Result")`` — a
   first-party BSE endpoint. The single "Financial Results" PDF row is chosen by
   largest attachment then earliest post-quarter filing; genuine ambiguity fails
   closed listing the candidates rather than guessing.
2. **Download** the attachment from BSE's static filing host
   (``/xml-data/corpfiling/AttachHis/<name>``, falling back to ``AttachLive`` on
   404), with an explicit timeout and bounded retries.
3. **Verify** the bytes before trusting them: the magic must be ``%PDF-`` and the
   size must equal the announcement's declared ``Fld_Attachsize`` — a mismatch
   fails closed (never a truncated or wrong file).

Rights posture: owner-authorized private, non-commercial use
(``A05-DECISION-004`` + bd memory ``preapproval-goal-multistock-validation-2026-08-21``)
— polite, low-volume, one attachment per quarter, no anti-bot evasion, no
redistribution, no external upload. The static filing host serves attachments to
browsers, so the request carries a browser ``User-Agent`` and BSE ``Referer``
(the same headers the ``bse`` library's own session sends); these are honest
browser headers for a first-party CDN, not an evasion of any challenge, and are
injectable so the posture stays explicit. Bytes are held under a caller-supplied
(gitignored) folder and never committed.

A terminal provider block (403/auth/CAPTCHA) is classified and surfaced
immediately as :class:`BsePdfHardBlockError` and never retried (the M10 pattern
shared with :mod:`fundamentals.ingest.xbrl_source` and
:mod:`fundamentals.ingest.bse_source`; the small classifier is repeated per
adapter as those modules do — a shared ``ingest`` HTTP helper could later dedupe
all three).
"""

from __future__ import annotations

import hashlib
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, TypeVar

import structlog
from pydantic import BaseModel, ConfigDict

_LOGGER = structlog.get_logger(__name__)

_T = TypeVar("_T")

# --- Source identity ----------------------------------------------------------

SOURCE_ID = "bse-results-pdf"

# BSE serves filed attachments from a static host; AttachHis holds historical
# filings, AttachLive the most recent. Both are first-party BSE.
ATTACH_HIS_URL_TEMPLATE = "https://www.bseindia.com/xml-data/corpfiling/AttachHis/{name}"
ATTACH_LIVE_URL_TEMPLATE = "https://www.bseindia.com/xml-data/corpfiling/AttachLive/{name}"

# Browser headers for the static filing CDN (see module docstring; not evasion).
DEFAULT_USER_AGENT = "Mozilla/5.0"
DEFAULT_REFERER = "https://www.bseindia.com/"
USER_AGENT_HEADER = "User-Agent"
REFERER_HEADER = "Referer"

# announcements() filter + the row shape we consume.
RESULT_CATEGORY = "Result"
FINANCIAL_RESULTS_SUBCATEGORY = "Financial Results"
_TABLE_KEY = "Table"
_ATTACHMENT_NAME_KEY = "ATTACHMENTNAME"
_ATTACHMENT_SIZE_KEY = "Fld_Attachsize"
_SUBCATEGORY_KEY = "SUBCATNAME"
_HEADLINE_KEY = "HEADLINE"
_NEWS_DT_KEY = "NEWS_DT"
_PDF_SUFFIX = ".pdf"
_PDF_MAGIC = b"%PDF-"

# --- Fetch tunables -----------------------------------------------------------

DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 2.0

# --- Terminal-block classification (M10 pattern; see xbrl_source/bse_source) ---

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


class BsePdfFetchError(Exception):
    """Typed, resumable failure: the fetch produced no trustworthy results PDF."""


class BsePdfHardBlockError(BsePdfFetchError):
    """A terminal provider block (403/auth/CAPTCHA): stop immediately, do not retry."""


def _is_terminal_error(exc: Exception) -> bool:
    """Classify whether an exception represents a terminal hard block."""
    code = getattr(exc, "code", None) or getattr(exc, "status", None)
    if isinstance(code, int) and code in _TERMINAL_HTTP_CODES:
        return True
    message = str(exc).lower()
    return any(marker in message for marker in _TERMINAL_MARKERS)


class BseAnnouncement(BaseModel):
    """One selected BSE results-filing announcement row (the fields we consume)."""

    model_config = ConfigDict(frozen=True)

    attachment_name: str
    attachment_size: int
    subcategory: str
    headline: str
    filed_at: datetime | None


class BsePdfRetrieval(BaseModel):
    """Immutable record of one verified BSE results-PDF download and its provenance."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    local_path: Path
    file_sha256: str
    attachment_name: str
    attachment_size: int
    results_url: str
    scrip_code: str
    from_date: date
    to_date: date
    headline: str
    retrieved_at: datetime
    filed_at: datetime | None = None


def _parse_filed_at(raw: object) -> datetime | None:
    """Parse a BSE ISO-ish ``NEWS_DT`` (``2025-02-04T17:31:44.287``); ``None`` if bad."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return datetime.fromisoformat(raw.strip()).replace(tzinfo=UTC)
    except ValueError:
        return None


def _to_announcement(row: dict[str, Any]) -> BseAnnouncement | None:
    """Project a raw announcements row into a typed record, or ``None`` if not a PDF."""
    name = str(row.get(_ATTACHMENT_NAME_KEY, "")).strip()
    if not name.lower().endswith(_PDF_SUFFIX):
        return None
    try:
        size = int(row.get(_ATTACHMENT_SIZE_KEY) or 0)
    except (TypeError, ValueError):
        size = 0
    return BseAnnouncement(
        attachment_name=name,
        attachment_size=size,
        subcategory=str(row.get(_SUBCATEGORY_KEY, "")).strip(),
        headline=str(row.get(_HEADLINE_KEY, "")).strip(),
        filed_at=_parse_filed_at(row.get(_NEWS_DT_KEY)),
    )


def _select_results_row(rows: list[dict[str, Any]], scrip_code: str) -> BseAnnouncement:
    """Choose the single Financial-Results PDF row, failing closed on ambiguity.

    Candidates are the PDF attachments whose subcategory is exactly ``Financial
    Results``. They are ordered by largest attachment (the full results package),
    then earliest filing (the primary broadcast rather than a later corrigendum),
    then attachment name for a stable tie-break — so selection is deterministic and
    never a silent guess.
    """
    candidates = [
        announcement
        for announcement in (_to_announcement(row) for row in rows)
        if announcement is not None and announcement.subcategory == FINANCIAL_RESULTS_SUBCATEGORY
    ]
    if not candidates:
        raise BsePdfFetchError(
            f"no '{FINANCIAL_RESULTS_SUBCATEGORY}' results PDF found for scrip {scrip_code!r}"
        )
    candidates.sort(
        key=lambda a: (
            -a.attachment_size,
            a.filed_at or datetime.max.replace(tzinfo=UTC),
            a.attachment_name,
        )
    )
    if len(candidates) > 1:
        _LOGGER.info(
            "bse_pdf_multiple_result_rows",
            scrip_code=scrip_code,
            chosen=candidates[0].attachment_name,
            candidate_count=len(candidates),
            candidate_sizes=[a.attachment_size for a in candidates],
        )
    return candidates[0]


class BseResultsPdfSource:
    """Polite, fail-closed fetcher for a BSE-hosted quarterly results PDF."""

    def __init__(
        self,
        download_folder: Path,
        *,
        scrip_code: str,
        user_agent: str = DEFAULT_USER_AGENT,
        referer: str = DEFAULT_REFERER,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
    ) -> None:
        self._download_folder = download_folder
        self._scrip_code = scrip_code.strip()
        self._user_agent = user_agent
        self._referer = referer
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds

    def fetch_results_pdf(self, *, from_date: date, to_date: date) -> BsePdfRetrieval:
        """Locate, download and verify the results PDF for one reviewed quarter.

        ``from_date``/``to_date`` bound the announcement search window (the quarter
        end through ~60 days after, when results are broadcast). Raises
        :class:`BsePdfFetchError` (producing no record) on any location, download,
        size, or magic-byte failure so no fact is built from an unverified file.
        """
        self._download_folder.mkdir(parents=True, exist_ok=True)
        retrieved_at = datetime.now(UTC)

        rows = self._retry(
            "BSE announcements", lambda: self._fetch_announcements(from_date, to_date)
        )
        announcement = _select_results_row(rows, self._scrip_code)
        payload, results_url = self._download_attachment(announcement.attachment_name)
        self._verify(payload, announcement)

        local_path = self._download_folder / announcement.attachment_name
        local_path.write_bytes(payload)
        file_sha256 = hashlib.sha256(payload).hexdigest()

        _LOGGER.info(
            "bse_results_pdf_fetched",
            scrip_code=self._scrip_code,
            attachment=announcement.attachment_name,
            bytes=len(payload),
            file_sha256=file_sha256,
            results_url=results_url,
        )
        return BsePdfRetrieval(
            source_id=SOURCE_ID,
            local_path=local_path,
            file_sha256=file_sha256,
            attachment_name=announcement.attachment_name,
            attachment_size=announcement.attachment_size,
            results_url=results_url,
            scrip_code=self._scrip_code,
            from_date=from_date,
            to_date=to_date,
            headline=announcement.headline,
            retrieved_at=retrieved_at,
            filed_at=announcement.filed_at,
        )

    # -- Internals ------------------------------------------------------------

    def _fetch_announcements(self, from_date: date, to_date: date) -> list[dict[str, Any]]:
        """Call ``announcements`` on a fresh ``bse`` client, closing it always."""
        bse_client_cls = self._load_bse_client_class()
        client = bse_client_cls(download_folder=self._download_folder)
        try:
            response = client.announcements(
                scripcode=self._scrip_code,
                from_date=datetime(from_date.year, from_date.month, from_date.day, tzinfo=UTC),
                to_date=datetime(to_date.year, to_date.month, to_date.day, tzinfo=UTC),
                category=RESULT_CATEGORY,
            )
        finally:
            client.exit()
        if not isinstance(response, dict):
            kind = type(response).__name__
            raise BsePdfFetchError(f"announcements returned {kind}, expected dict")
        table = response.get(_TABLE_KEY, [])
        if not isinstance(table, list):
            raise BsePdfFetchError("announcements response has no 'Table' list")
        return [row for row in table if isinstance(row, dict)]

    def _load_bse_client_class(self) -> Any:
        """Lazily import the ``bse`` client class, failing closed if unavailable."""
        try:
            from bse import BSE  # type: ignore[import-untyped]
        except ImportError as exc:
            raise BsePdfFetchError(
                "the 'bse' library is required to locate the results PDF; install it"
            ) from exc
        return BSE

    def _download_attachment(self, name: str) -> tuple[bytes, str]:
        """Download the attachment, trying AttachHis then AttachLive on 404."""
        his_url = ATTACH_HIS_URL_TEMPLATE.format(name=name)
        try:
            return self._retry("BSE attachment download", lambda: self._http_get(his_url)), his_url
        except BsePdfFetchError as his_error:
            live_url = ATTACH_LIVE_URL_TEMPLATE.format(name=name)
            if "404" not in str(his_error):
                raise
            _LOGGER.info("bse_pdf_attachhis_404_fallback_live", attachment=name)
            return self._retry(
                "BSE attachment download (live)", lambda: self._http_get(live_url)
            ), live_url

    def _http_get(self, url: str) -> bytes:
        """Perform one bounded-timeout GET with browser headers, returning the body."""
        request = urllib.request.Request(
            url,
            headers={USER_AGENT_HEADER: self._user_agent, REFERER_HEADER: self._referer},
        )
        with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
            payload: bytes = response.read()
        if not payload:
            raise BsePdfFetchError(f"attachment download returned an empty body: {url}")
        return payload

    def _verify(self, payload: bytes, announcement: BseAnnouncement) -> None:
        """Reject a download whose magic bytes or size do not match the announcement."""
        if payload[: len(_PDF_MAGIC)] != _PDF_MAGIC:
            raise BsePdfFetchError(
                f"downloaded attachment {announcement.attachment_name!r} is not a PDF "
                f"(magic {payload[:5]!r})"
            )
        if announcement.attachment_size and len(payload) != announcement.attachment_size:
            raise BsePdfFetchError(
                f"downloaded {announcement.attachment_name!r} size {len(payload)} does not match "
                f"announced size {announcement.attachment_size}"
            )

    def _retry(self, description: str, action: Callable[[], _T]) -> _T:
        """Run ``action`` with bounded retries and linear backoff, failing closed.

        A terminal hard block (403/auth/CAPTCHA/explicit block) stops immediately
        as :class:`BsePdfHardBlockError`; a 404 is surfaced (so the caller can fall
        back to the live host); only timeouts and other transient failures retry.
        """
        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                return action()
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    raise BsePdfFetchError(f"{description} returned 404") from exc
                if _is_terminal_error(exc):
                    raise BsePdfHardBlockError(
                        f"{description} hit a terminal block; not retrying: {exc}"
                    ) from exc
                last_error = exc
            except BsePdfHardBlockError:
                raise
            except Exception as exc:  # noqa: BLE001 - re-raised as typed failure below
                if _is_terminal_error(exc):
                    raise BsePdfHardBlockError(
                        f"{description} hit a terminal block; not retrying: {exc}"
                    ) from exc
                last_error = exc
            _LOGGER.warning("bse_pdf_fetch_retry", action=description, attempt=attempt + 1)
            if attempt + 1 < self._max_retries:
                time.sleep(self._retry_backoff_seconds * (attempt + 1))
        raise BsePdfFetchError(
            f"{description} failed after {self._max_retries} attempts: {last_error}"
        )
