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


class XbrlFetchError(Exception):
    """Typed, resumable failure: the fetch produced no trustworthy filing."""


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
    ) -> None:
        self._download_folder = download_folder
        self._symbol = symbol.upper()
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds

    def _retry(self, description: str, action: Any) -> Any:
        """Run ``action`` with bounded retries and linear backoff, failing closed."""
        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                return action()
            except Exception as exc:  # noqa: BLE001 - re-raised as typed failure below
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
            and (row.get("consolidated") or "") == CONSOLIDATED_ROW_VALUE
            and INDAS_MARKER in (row.get("indAs") or "")
            and (row.get("xbrl") or "").strip()
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

    def _verify(self, xml_bytes: bytes, *, from_date: date, to_date: date) -> None:
        """Reject a download whose scope or period does not match the request."""
        try:
            root = etree.fromstring(xml_bytes)
        except etree.XMLSyntaxError as exc:
            raise XbrlFetchError(f"downloaded XBRL is not well-formed: {exc}") from exc

        nature = root.find(f"{{{FIN_NAMESPACE}}}{SCOPE_CONCEPT}")
        if nature is None or (nature.text or "").strip() != CONSOLIDATED_TEXT:
            raise XbrlFetchError("downloaded XBRL is not a consolidated filing")

        wanted = (from_date.isoformat(), to_date.isoformat())
        for context in root.findall(f"{_XBRLI}context"):
            start = context.find(f"{_XBRLI}period/{_XBRLI}startDate")
            end = context.find(f"{_XBRLI}period/{_XBRLI}endDate")
            if start is None or end is None:
                continue
            if ((start.text or "").strip(), (end.text or "").strip()) == wanted:
                return
        raise XbrlFetchError(f"downloaded XBRL carries no {from_date}..{to_date} duration context")

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
                local_path = self._download(client, xbrl_url)
        except XbrlFetchError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalise to a typed failure
            raise XbrlFetchError(f"NSE fetch failed: {exc}") from exc

        xml_bytes = local_path.read_bytes()
        self._verify(xml_bytes, from_date=from_date, to_date=to_date)
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


def _row_date(raw: str | None) -> date | None:
    """Parse an NSE filing-row date (``01-Apr-2024``); ``None`` if unparseable."""
    if not raw:
        return None
    try:
        return datetime.strptime(raw.strip(), ROW_DATE_FORMAT).date()
    except ValueError:
        return None
