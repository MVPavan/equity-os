"""Fetch and hold the NSE Ind AS XBRL for a requested issuer quarter.

Rights posture: NSE access is owner-authorized private use (A05-DECISION-004) —
polite, low-volume, no evasion. This adapter fetches at most one filing per
call, verifies issuer, period and consolidation scope *before* returning, and
fails closed: on any network failure, ambiguity, or staleness it raises a typed
:class:`XbrlFetchError` and produces no retrieval record, so no fact can ever be
built from an unverified download.

The downloaded bytes are held under a caller-supplied (gitignored) folder and
sha256-stamped; the source bytes are never committed or redistributed.
"""

from __future__ import annotations

import hashlib
import time
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from lxml import etree  # type: ignore[import-untyped]
from nse import NSE  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.provenance import Provenance, SourceAnchorType

NS_XBRLI = "http://www.xbrl.org/2003/instance"
FIN_NAMESPACE = "http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin"
SCOPE_CONCEPT = "NatureOfReportStandaloneConsolidated"
CONSOLIDATED_TEXT = "Consolidated"

_XBRLI = f"{{{NS_XBRLI}}}"

DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 2.0
ROW_DATE_FORMAT = "%d-%b-%Y"
BROADCAST_DATE_FORMAT = "%d-%b-%Y %H:%M:%S"
INDAS_MARKER = "Ind-AS"
CONSOLIDATED_ROW_VALUE = "Consolidated"
CONSOLIDATED_SOURCE_ID = "nse-indas-xbrl-consolidated"

# Rename-stable issuer-identity registry. A company's ISIN never changes across a
# symbol/name rename, but a filing made *before* the rename still carries the OLD
# NSE symbol in its XBRL context entity, while ``financial_results`` now keys the
# row (and its ``isin``) under the NEW symbol. This maps the stable ISIN to the
# as-filed entity identifiers that legitimately belong to that issuer, so a
# pre-rename filing verifies without weakening the guard against a genuinely
# different company. Curated + auditable; keyed by ISIN so it survives future
# renames. (Zomato Limited -> Eternal Limited; symbol ZOMATO -> ETERNAL, effective
# 2025-04-09; ISIN INE758T01015 unchanged.)
_ACCEPTED_ENTITY_IDS_BY_ISIN: dict[str, frozenset[str]] = {
    "INE758T01015": frozenset({"ZOMATO"}),
}

# Markers that classify a provider response as a TERMINAL hard block — never
# retried, surfaced immediately. Only timeouts and transient statuses are retried.
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


class XbrlFetchError(Exception):
    """Typed, resumable failure: the fetch produced no trustworthy filing."""


class XbrlHardBlockError(XbrlFetchError):
    """A terminal provider block (403/auth/CAPTCHA): stop immediately, do not retry."""


def _is_terminal_error(exc: Exception) -> bool:
    """Classify whether an exception represents a terminal hard block."""
    code = getattr(exc, "code", None) or getattr(exc, "status", None)
    if isinstance(code, int) and code in _TERMINAL_HTTP_CODES:
        return True
    message = str(exc).lower()
    return any(marker in message for marker in _TERMINAL_MARKERS)


class XbrlRetrieval(BaseModel):
    """Immutable record of one verified XBRL download and its provenance."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    local_path: Path
    file_sha256: str
    xbrl_url: str
    symbol: str
    from_date: date
    to_date: date
    relating_to: str
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


def _parse_broadcast(raw: str | None) -> datetime | None:
    """Parse a broadcast/filing timestamp; return ``None`` if unrecognised."""
    if not raw:
        return None
    try:
        return datetime.strptime(raw.strip(), BROADCAST_DATE_FORMAT).replace(tzinfo=UTC)
    except ValueError:
        try:
            return datetime.strptime(raw.strip(), ROW_DATE_FORMAT).replace(tzinfo=UTC)
        except ValueError:
            return None


class NseXbrlSource:
    """Polite, fail-closed fetcher for NSE Ind AS quarterly XBRL filings."""

    def __init__(
        self,
        download_folder: Path,
        *,
        symbol: str,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
        accepted_entity_ids: tuple[str, ...] = (),
    ) -> None:
        self._download_folder = download_folder
        self._symbol = symbol.upper()
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds
        # Caller-injected as-filed entity identifiers accepted as this issuer
        # (e.g. a pre-rename NSE symbol), stored normalized for comparison.
        self._accepted_entity_ids = frozenset(
            alias.strip().upper() for alias in accepted_entity_ids if alias.strip()
        )

    def _retry(self, description: str, action: Any) -> Any:
        """Run ``action`` with bounded retries and linear backoff, failing closed.

        A terminal hard block (403/auth/CAPTCHA/explicit block) stops immediately
        and is surfaced as :class:`XbrlHardBlockError`; only timeouts and other
        transient failures are retried.
        """
        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                return action()
            except Exception as exc:  # noqa: BLE001 - re-raised as typed failure below
                if _is_terminal_error(exc):
                    raise XbrlHardBlockError(
                        f"{description} hit a terminal block; not retrying: {exc}"
                    ) from exc
                last_error = exc
                if attempt + 1 < self._max_retries:
                    time.sleep(self._retry_backoff_seconds * (attempt + 1))
        raise XbrlFetchError(
            f"{description} failed after {self._max_retries} attempts: {last_error}"
        ) from last_error

    def _find_filing(self, client: Any, *, from_date: date, to_date: date) -> dict[str, Any]:
        """Return the single consolidated Ind AS filing row for the quarter."""
        rows: list[dict[str, Any]] = self._retry(
            "financial_results listing",
            lambda: client.financial_results(
                segment="equities", period="quarterly", symbol=self._symbol
            ),
        )
        candidates = [
            row
            for row in rows
            if _row_date(row.get("fromDate")) == from_date
            and _row_date(row.get("toDate")) == to_date
            and _is_consolidated_indas_xbrl_row(row)
        ]
        if len(candidates) != 1:
            raise XbrlFetchError(
                f"expected exactly 1 consolidated Ind AS filing for {self._symbol} "
                f"{from_date}..{to_date}, found {len(candidates)}"
            )
        return candidates[0]

    def _download(self, client: Any, xbrl_url: str) -> Path:
        """Download the XBRL document into the held folder, failing closed."""
        path = self._retry(
            "XBRL download",
            lambda: client.download_document(xbrl_url, folder=self._download_folder),
        )
        local_path = Path(path)
        if not local_path.is_file():
            raise XbrlFetchError(f"download did not yield a file: {xbrl_url}")
        return local_path

    def _verify(
        self, xml_bytes: bytes, *, from_date: date, to_date: date, isin: str | None = None
    ) -> None:
        """Reject a download whose scope, issuer, or period does not match the request.

        ``isin`` is the filing row's rename-stable ISIN (when known); it widens the
        set of accepted context entity identifiers so a filing made before an issuer
        rename still verifies. It never relaxes the scope or period checks.
        """
        try:
            root = etree.fromstring(xml_bytes)
        except etree.XMLSyntaxError as exc:
            raise XbrlFetchError(f"downloaded XBRL is not well-formed: {exc}") from exc

        nature = root.find(f"{{{FIN_NAMESPACE}}}{SCOPE_CONCEPT}")
        if nature is None or (nature.text or "").strip() != CONSOLIDATED_TEXT:
            raise XbrlFetchError("downloaded XBRL is not a consolidated filing")

        self._verify_issuer(root, isin=isin)

        wanted = (from_date.isoformat(), to_date.isoformat())
        for context in root.findall(f"{_XBRLI}context"):
            start = context.find(f"{_XBRLI}period/{_XBRLI}startDate")
            end = context.find(f"{_XBRLI}period/{_XBRLI}endDate")
            if start is None or end is None:
                continue
            if ((start.text or "").strip(), (end.text or "").strip()) == wanted:
                return
        raise XbrlFetchError(f"downloaded XBRL carries no {from_date}..{to_date} duration context")

    def _accepted_entity_ids_for(self, isin: str | None) -> frozenset[str]:
        """Entity identifiers accepted as the requested issuer for this filing.

        The requested symbol always qualifies. A renamed issuer's *as-filed* XBRL
        still carries its OLD NSE symbol, so two rename-stable sources widen the
        set: caller-injected aliases, and the built-in registry keyed by the
        filing row's ISIN (which never changes across a symbol/name rename).
        """
        accepted = {self._symbol} | self._accepted_entity_ids
        if isin:
            accepted |= _ACCEPTED_ENTITY_IDS_BY_ISIN.get(isin.strip().upper(), frozenset())
        return frozenset(accepted)

    def _verify_issuer(self, root: Any, *, isin: str | None = None) -> None:
        """Reject a download whose context entity is not the requested issuer.

        A response pointing at another company's filing for the same dates must not
        pass ingestion verification: at least one context entity identifier must be
        the requested issuer — its current symbol, a rename-stable ISIN alias, or a
        configured alias. A filing for a genuinely different company is rejected.
        """
        identifiers = {
            (identifier.text or "").strip().upper()
            for identifier in root.findall(f"{_XBRLI}context/{_XBRLI}entity/{_XBRLI}identifier")
        }
        accepted = self._accepted_entity_ids_for(isin)
        if identifiers.isdisjoint(accepted):
            aliases = sorted(accepted - {self._symbol})
            raise XbrlFetchError(
                f"downloaded XBRL entity {sorted(identifiers)} does not match requested "
                f"issuer {self._symbol!r} (accepted aliases: {aliases or 'none'})"
            )

    def fetch_consolidated_quarter(self, *, from_date: date, to_date: date) -> XbrlRetrieval:
        """Fetch, verify and stamp the consolidated Ind AS XBRL for one quarter.

        Raises :class:`XbrlFetchError` (producing no record) on any network
        failure, ambiguous filing match, malformed download, or scope/period
        mismatch.
        """
        self._download_folder.mkdir(parents=True, exist_ok=True)
        retrieved_at = datetime.now(UTC)
        try:
            with NSE(self._download_folder, timeout=self._timeout_seconds) as client:
                row = self._find_filing(client, from_date=from_date, to_date=to_date)
                xbrl_url = row["xbrl"].strip()
                isin = (row.get("isin") or "").strip() or None
                local_path = self._download(client, xbrl_url)
        except XbrlFetchError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalise to a typed failure
            raise XbrlFetchError(f"NSE fetch failed: {exc}") from exc

        xml_bytes = local_path.read_bytes()
        self._verify(xml_bytes, from_date=from_date, to_date=to_date, isin=isin)
        file_sha256 = hashlib.sha256(xml_bytes).hexdigest()

        return XbrlRetrieval(
            source_id=CONSOLIDATED_SOURCE_ID,
            local_path=local_path,
            file_sha256=file_sha256,
            xbrl_url=xbrl_url,
            symbol=self._symbol,
            from_date=from_date,
            to_date=to_date,
            relating_to=(row.get("relatingTo") or "").strip(),
            consolidated=True,
            retrieved_at=retrieved_at,
            filed_at=_parse_broadcast(row.get("broadCastDate")),
        )

    def available_consolidated_quarters(self) -> frozenset[tuple[date, date]]:
        """Return the quarters NSE lists a consolidated Ind AS XBRL filing for.

        Reads the same quarterly ``financial_results`` listing as
        :meth:`fetch_consolidated_quarter` and returns the ``(from_date, to_date)``
        span of every row that qualifies as a consolidated Ind AS filing carrying
        an XBRL url; rows whose dates do not parse are skipped. Used to intersect
        with BSE's published quarters so latest-quarter resolution only targets a
        quarter both first-party hosts carry. Fails closed with
        :class:`XbrlFetchError` on any network failure.
        """
        self._download_folder.mkdir(parents=True, exist_ok=True)
        try:
            with NSE(self._download_folder, timeout=self._timeout_seconds) as client:
                rows: list[dict[str, Any]] = self._retry(
                    "financial_results listing",
                    lambda: client.financial_results(
                        segment="equities", period="quarterly", symbol=self._symbol
                    ),
                )
        except XbrlFetchError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalise to a typed failure
            raise XbrlFetchError(f"NSE listing failed: {exc}") from exc

        quarters: set[tuple[date, date]] = set()
        for row in rows:
            if not _is_consolidated_indas_xbrl_row(row):
                continue
            from_date = _row_date(row.get("fromDate"))
            to_date = _row_date(row.get("toDate"))
            if from_date is None or to_date is None:
                continue
            quarters.add((from_date, to_date))
        return frozenset(quarters)


def _is_consolidated_indas_xbrl_row(row: dict[str, Any]) -> bool:
    """Whether an NSE listing row is a consolidated Ind AS filing carrying an XBRL url."""
    return (
        (row.get("consolidated") or "") == CONSOLIDATED_ROW_VALUE
        and INDAS_MARKER in (row.get("indAs") or "")
        and bool((row.get("xbrl") or "").strip())
    )


def _row_date(raw: str | None) -> date | None:
    """Parse an NSE filing-row date (``01-Apr-2024``); ``None`` if unparseable."""
    if not raw:
        return None
    try:
        return datetime.strptime(raw.strip(), ROW_DATE_FORMAT).date()
    except ValueError:
        return None
