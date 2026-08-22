"""Fetch and hold the BSE Ind AS XBRL for a requested issuer quarter.

BSE is the *second* first-party host for the same issuer Ind AS filing already
ingested from NSE (see :mod:`fundamentals.ingest.xbrl_source`): two independent
first-party sources of the identical ``in-bse-fin`` / ``in-capmkt`` XBRL give the
Fundamentals reconciliation a built-in cross-check.

Rights posture: BSE access here is owner-authorized private, non-commercial use
(``A05-DECISION-004`` + bd memory ``preapproval-goal-multistock-validation-2026-08-21``)
— polite, low-volume, no anti-bot evasion, no redistribution, no external upload.
Per ``docs/research/crawl4ai-nse-bse-evaluation.md`` the static ``/XBRLFILES/*.xml``
instances are NOT Akamai-gated and can be pulled with a plain HTTP client once the
link is known, so that is the primary path here; resolving the link from the filing
index via the ``bse`` library is an opt-in convenience used only on the live path.

This adapter reuses the context-aware parser in
:mod:`fundamentals.extract.xbrl_parser` (it does NOT re-implement XBRL parsing):
it fetches at most one filing per call, verifies scope, period and issuer *before*
returning, and fails closed — on any network failure, ambiguity, malformed
download, or scope/period mismatch it raises a typed :class:`BseFetchError` and
produces no retrieval record, so no observation can be built from an unverified
download. A terminal hard block (403/auth/CAPTCHA) is classified and never retried
(the M10 pattern from ``xbrl_source``).

The downloaded bytes are held under a caller-supplied (gitignored) folder and
sha256-stamped; the source bytes are never committed or redistributed.
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
from urllib.parse import urlsplit

import structlog
from lxml import etree  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.observation import Observation
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.extract.xbrl_parser import (
    DEFAULT_TAXONOMIES,
    TaxonomySpec,
    parse_observations,
)

_LOGGER = structlog.get_logger(__name__)

_T = TypeVar("_T")

# --- Source identity ----------------------------------------------------------

SOURCE_ID = "bse-xbrl"
ENTITY_SCHEME = "bse-scrip"
DEFAULT_USER_AGENT = "EquityOS Research (mvpavan42@gmail.com)"
USER_AGENT_HEADER = "User-Agent"

# BSE served the results XBRL under two taxonomies across FY25: ``in-bse-fin``
# through Q3 FY25 and ``in-capmkt`` (the "Integrated Filing" format) from Q4 FY25
# onward. The parser dispatches by scope concept through a taxonomy registry, so
# BSE support is additive: reuse the shipped ``in-bse-fin`` spec and add
# ``in-capmkt``. NOTE: the ``in-capmkt`` namespace URI below must be confirmed
# against a real Integrated Filing instance; the committed fixture declares the
# same value so the deterministic test is self-consistent, but live parsing of a
# real ``in-capmkt`` instance requires the confirmed production URI.
IN_CAPMKT_NAMESPACE = "http://www.sebi.gov.in/xbrl/2023-03-31/in-capmkt"
IN_CAPMKT_PREFIX = "in-capmkt"
IN_CAPMKT_REGISTRY_VERSION = "in-capmkt/2023-03-31"

BSE_TAXONOMIES: tuple[TaxonomySpec, ...] = (
    *DEFAULT_TAXONOMIES,
    TaxonomySpec(
        namespace=IN_CAPMKT_NAMESPACE,
        prefix=IN_CAPMKT_PREFIX,
        registry_version=IN_CAPMKT_REGISTRY_VERSION,
    ),
)

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

# Candidate result-listing method names on the ``bse`` client. The library is a
# sibling of ``nse`` (used in xbrl_source); its exact result API is unverified in
# this environment, so discovery probes these names and fails closed if none exist.
_BSE_RESULT_METHODS: tuple[str, ...] = ("financial_results", "results", "result")


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
    """Polite, fail-closed fetcher for BSE Ind AS quarterly XBRL filings.

    Parsing is delegated to :func:`fundamentals.extract.xbrl_parser.parse_observations`
    with :data:`BSE_TAXONOMIES` (``in-bse-fin`` + ``in-capmkt``); this class owns
    only fetch, verification, provenance stamping, and the parse hand-off.
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

    # -- Public parse hand-off (deterministic, no network) --------------------

    @staticmethod
    def parse(
        xml_bytes: bytes,
        *,
        file_sha256: str,
        retrieved_at: datetime,
    ) -> tuple[Observation, ...]:
        """Parse held BSE XBRL bytes into observations via the shared parser.

        Stamps every observation's provenance with ``source_id="bse-xbrl"`` and
        dispatches concept resolution through :data:`BSE_TAXONOMIES`, so a filing
        under either the ``in-bse-fin`` or ``in-capmkt`` taxonomy is handled and an
        instance under neither fails closed (never yields an empty result).
        """
        return parse_observations(
            xml_bytes,
            source_id=SOURCE_ID,
            file_sha256=file_sha256,
            retrieved_at=retrieved_at,
            taxonomies=BSE_TAXONOMIES,
        )

    # -- Fetch + verify + parse (live) ----------------------------------------

    def fetch_quarter(
        self,
        *,
        from_date: date,
        to_date: date,
        consolidated: bool = True,
        xbrl_url: str | None = None,
    ) -> BseRetrieval:
        """Fetch, verify and stamp the BSE Ind AS XBRL for one quarter.

        The static ``/XBRLFILES/*.xml`` instance is pulled with a plain HTTP client
        once ``xbrl_url`` is known; when it is omitted the link is resolved from the
        filing index via the ``bse`` library. Raises :class:`BseFetchError`
        (producing no record) on any network failure, ambiguous filing match,
        malformed download, or scope/period/issuer mismatch.
        """
        self._download_folder.mkdir(parents=True, exist_ok=True)
        retrieved_at = datetime.now(UTC)

        resolved_url = xbrl_url or self._resolve_xbrl_url(
            from_date=from_date, to_date=to_date, consolidated=consolidated
        )
        self._validate_xbrl_url(resolved_url)

        xml_bytes = self._download(resolved_url)
        self._verify(xml_bytes, from_date=from_date, to_date=to_date, consolidated=consolidated)
        local_path = self._persist(xml_bytes, resolved_url)
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
            xbrl_url=resolved_url,
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
        """Fetch one quarter and return its parsed, provenance-stamped observations."""
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
            for spec in BSE_TAXONOMIES
            if root.find(f"{{{spec.namespace}}}{spec.scope_concept}") is not None
        ]
        if len(matched) != 1:
            supported = ", ".join(spec.registry_version for spec in BSE_TAXONOMIES)
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

    def _resolve_xbrl_url(self, *, from_date: date, to_date: date, consolidated: bool) -> str:
        """Resolve the static XBRL link from the filing index via the ``bse`` library.

        Opt-in convenience for the live path only. The ``bse`` client is imported
        lazily (it is not a hard dependency of this package); its exact result API
        is probed defensively and any absence/mismatch fails closed.
        """
        bse_client_cls = self._load_bse_client_class()
        rows = self._retry(
            "BSE results listing",
            lambda: self._list_results(bse_client_cls),
        )
        return self._select_xbrl_link(
            rows, from_date=from_date, to_date=to_date, consolidated=consolidated
        )

    def _load_bse_client_class(self) -> Any:
        """Lazily import the ``bse`` client class, failing closed if unavailable."""
        try:
            from bse import BSE  # type: ignore[import-not-found]
        except ImportError as exc:
            raise BseFetchError(
                "the 'bse' library is required to resolve the filing index; "
                "install it or pass xbrl_url explicitly"
            ) from exc
        return BSE

    def _list_results(self, bse_client_cls: Any) -> list[dict[str, Any]]:
        """Fetch the raw results listing rows via the ``bse`` client."""
        with bse_client_cls(self._download_folder) as client:
            for method_name in _BSE_RESULT_METHODS:
                method = getattr(client, method_name, None)
                if callable(method):
                    rows: Any = method(scripcode=self._scrip_code)
                    return list(rows)
        raise BseFetchError(
            f"'bse' client exposes none of the expected result methods: {_BSE_RESULT_METHODS}"
        )

    def _select_xbrl_link(
        self,
        rows: list[dict[str, Any]],
        *,
        from_date: date,
        to_date: date,
        consolidated: bool,
    ) -> str:
        """Pick the single matching quarter's static XBRL link, failing closed."""
        wanted_end = to_date.isoformat()
        candidates: list[str] = []
        for row in rows:
            link = self._row_xbrl_link(row)
            if link is None:
                continue
            if self._row_matches(row, wanted_end=wanted_end, consolidated=consolidated):
                candidates.append(link)
        unique = sorted(set(candidates))
        if len(unique) != 1:
            raise BseFetchError(
                f"expected exactly 1 {'consolidated' if consolidated else 'standalone'} "
                f"XBRL link for scrip {self._scrip_code} {from_date}..{to_date}, "
                f"found {len(unique)}"
            )
        return unique[0]

    @staticmethod
    def _row_xbrl_link(row: dict[str, Any]) -> str | None:
        """Extract a static ``.xml`` XBRL link from a results-listing row, if any."""
        for value in row.values():
            if isinstance(value, str) and value.strip().lower().endswith(XBRL_LINK_SUFFIX):
                return value.strip()
        return None

    @staticmethod
    def _row_matches(row: dict[str, Any], *, wanted_end: str, consolidated: bool) -> bool:
        """True when a listing row is the requested quarter and consolidation scope."""
        blob = " ".join(str(value) for value in row.values()).lower()
        if wanted_end not in blob:
            return False
        return ("consolidated" in blob) == consolidated
