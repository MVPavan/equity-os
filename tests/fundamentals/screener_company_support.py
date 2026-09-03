"""Shared fixtures and seams for the ``screener-company`` test modules.

No test opens a socket: the transport seam defined here is replaced with
committed synthetic bodies, and every helper below exists so the two test
modules exercise the same one.

The routing table in :func:`_fixture_for` is deliberately keyed on the URL the
production code builds, not on a name the test passes in. That makes every test
that asserts a *value* also an assertion that the URL was built correctly — the
segments basis rule in particular, where the difference between a right and a
wrong request is one query value.
"""

from __future__ import annotations

import email.message
import json
import urllib.request
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest
from pydantic import SecretStr

from fundamentals.ingest.screener_company import CompanyRun, read_company
from fundamentals.ingest.screener_company_models import ALL_PARTS, CompanyPart
from fundamentals.ingest.screener_session import ScreenerSessionSource
from fundamentals.ingest.screener_session_models import (
    Basis,
    BasisTopology,
    ScreenerCredentials,
    ScreenerRateLimitedError,
    ScreenerRedirectError,
    ScreenerSessionConfig,
)
from fundamentals.ingest.screener_session_page import parse_document

FIXTURES = Path(__file__).parent / "fixtures"
DOCUMENTS = FIXTURES / "screener_company"
PAGE = FIXTURES / "synthetic_screener_company.html"
SHELL_PAGE = FIXTURES / "synthetic_screener_session_basis_unavailable.html"

SESSION_ENV = "SCREENER_SESSION_COOKIE"
SESSION_TOKEN = "fixture-session-token"
COMPANY_ID = 991001
CONSOLIDATED_WAREHOUSE_ID = 992001
STANDALONE_WAREHOUSE_ID = 992002
SYMBOL = "FIXTURECO"
RETRIEVED_AT = datetime(2026, 8, 26, tzinfo=UTC)
SOURCE_ID = "screener-subscriber"
ZERO_SHA = "0" * 64

# Every sub-document one full consolidated run of the fixture page requests, in
# the order the page offers them. Held as a constant so a test can assert the
# request budget rather than a bare count.
EXPECTED_DOCUMENT_PATHS = (
    "/api/3/991001/investors/promoters/quarterly/",
    "/api/3/991001/investors/foreign_institutions/quarterly/",
    "/api/3/991001/investors/government/quarterly/",
    "/api/3/991001/investors/public/quarterly/",
    "/api/3/991001/investors/promoters/yearly/",
    "/api/3/991001/investors/foreign_institutions/yearly/",
    "/api/3/991001/investors/government/yearly/",
    "/api/3/991001/investors/public/yearly/",
    "/api/segments/991001/quarters/1/?consolidated=true",
    "/api/segments/991001/profit-loss/1/?consolidated=true",
    "/results/rpt/991001/consolidated/",
    "/company/actions/991001/",
    "/api/company/992001/peers/",
    "/api/company/992001/quick_ratios/",
)

WATCHLIST_YAML = """
raw_dir: "data/raw/watchlist"
stocks:
  - name: "Fixture Consolidated Ltd"
    domain: "Fixture"
    identifiers:
      nse_symbol: "FIXTURECO"
      bse_scrip: "500999"
      screener_slug: "FIXTURECO"
      screener_company_id: 991001
      screener_warehouse_id_consolidated: 992001
      screener_warehouse_id_standalone: 992002
      tijori_slug: "fixture-consolidated-ltd"
      tijori_company_id: 81
      needs_verification: [{flagged}]
    quarter:
      label: "Q3FY25"
      period_start: "2024-10-01"
      period_end: "2024-12-31"
      knowledge_cutoff: "2025-02-15T00:00:00Z"
  - name: "Fixture Standalone Only Ltd"
    domain: "Fixture"
    identifiers:
      nse_symbol: "SOLOCO"
      bse_scrip: "500998"
      screener_slug: "SOLOCO"
      screener_company_id: 991002
      screener_warehouse_id_standalone: 992003
      tijori_slug: "fixture-standalone-only-ltd"
      tijori_company_id: 82
    quarter:
      label: "Q3FY25"
      period_start: "2024-10-01"
      period_end: "2024-12-31"
      knowledge_cutoff: "2025-02-15T00:00:00Z"
"""


def watchlist(tmp_path: Path, *, flagged: str = "") -> Path:
    """Write the fixture watchlist, optionally flagging one identifier unverified."""
    path = tmp_path / "watchlist.yaml"
    path.write_text(WATCHLIST_YAML.format(flagged=flagged), encoding="utf-8")
    return path


def _fixture_name(url: str) -> str:
    """The committed fixture one requested URL maps to, from the URL alone."""
    parts = urlsplit(url)
    path = parts.path
    segments = path.strip("/").split("/")
    if path.startswith("/api/3/"):
        _, _, _, _, bucket, periodicity = segments
        return f"investors__{bucket}_{periodicity}"
    if path.startswith("/api/segments/"):
        _, _, _, section, segment_type = segments
        # The basis is asserted here rather than ignored: this endpoint selects
        # basis by the query VALUE, so a body served for a query the production
        # code did not build would hide exactly the bug the rule exists for.
        assert parts.query in ("", "consolidated=true"), parts.query
        return f"segments__{section}_{segment_type}"
    if path.startswith("/results/rpt/"):
        return "related_party"
    if path.startswith("/company/actions/"):
        return "corporate_actions"
    if path.endswith("/peers/"):
        return "peers" if str(CONSOLIDATED_WAREHOUSE_ID) in path else "peers.standalone"
    if path.endswith("/quick_ratios/"):
        return "quick_ratios"
    raise AssertionError(f"no fixture routed for {url}")


def _fixture_for(url: str, *, swap: tuple[str, str] | None) -> bytes:
    """Serve the committed body for one requested URL, honouring one swap.

    ``swap`` replaces exactly one document's body with a named variant, which is
    how a single wrong or malformed response is injected into an otherwise
    correct run.
    """
    name = _fixture_name(url)
    variant = swap[1] if swap is not None and swap[0] == name else ""
    suffix = "json" if name.startswith("investors__") else "html"
    return (DOCUMENTS / f"{name}{variant}.{suffix}").read_bytes()


def serve(
    monkeypatch: pytest.MonkeyPatch,
    *,
    swap: tuple[str, str] | None = None,
    rate_limit_after: int | None = None,
    redirect_at: int | None = None,
    body: tuple[str, bytes] | None = None,
    page: Path | None = None,
) -> list[str]:
    """Pin the transport seam to committed bodies and record every URL requested.

    ``redirect_at`` makes the n-th sub-document answer with the transport
    refusal Screener actually returns for a modal fetched without the XHR
    header: a 302 to the company page, which this adapter refuses rather than
    follows. ``body`` substitutes one named document's bytes outright, for the
    generated bodies that are too large to commit.
    """
    requested: list[str] = []

    def fetch_bytes(
        source: ScreenerSessionSource,
        url: str,
        credentials: ScreenerCredentials,
        *,
        xhr: bool = False,
    ) -> tuple[int, bytes]:
        del source, credentials, xhr
        requested.append(url)
        if "/company/" in url and url.endswith(("/consolidated/", f"/{SYMBOL}/", "/SOLOCO/")):
            if "SOLOCO" in url:
                return 200, SHELL_PAGE.read_bytes()
            source = page or PAGE
            if url.endswith(f"/{SYMBOL}/"):
                return 200, standalone_page(source)
            return 200, source.read_bytes()
        documents_so_far = len(requested) - 1
        if rate_limit_after is not None and documents_so_far > rate_limit_after:
            raise ScreenerRateLimitedError(f"screener rate-limited {url}")
        if redirect_at is not None and documents_so_far == redirect_at:
            raise ScreenerRedirectError(
                f"screener redirected {url} to '/company/FIXTURECO/'; refusing to follow"
            )
        if body is not None and _fixture_name(url) == body[0]:
            return 200, body[1]
        return 200, _fixture_for(url, swap=swap)

    monkeypatch.setenv(SESSION_ENV, SESSION_TOKEN)
    monkeypatch.setattr(ScreenerSessionSource, "_fetch_bytes", fetch_bytes)
    return requested


# What the same company page differs by on the standalone basis, verified against
# the live captures for all ten watchlist companies: the basis marker and its
# toggle link invert, the warehouse id changes (the company id does not), and
# the Related Party modal drops its ``consolidated/`` suffix. Applied as a
# transformation rather than committed as a second 200-line fixture so the two
# pages cannot drift apart, and stated here because these four differences ARE
# the standalone contract.
_STANDALONE_SUBSTITUTIONS = (
    ("Consolidated Figures", "Standalone Figures"),
    ("View Standalone", "View Consolidated"),
    (
        f'data-warehouse-id="{CONSOLIDATED_WAREHOUSE_ID}"',
        f'data-warehouse-id="{STANDALONE_WAREHOUSE_ID}"',
    ),
    ("/results/rpt/991001/consolidated/", "/results/rpt/991001/"),
    (f'href="/company/{SYMBOL}/"', f'href="/company/{SYMBOL}/consolidated/"'),
)


def standalone_page(source: Path) -> bytes:
    """The same fixture page as the site renders it on the standalone basis."""
    html = source.read_text(encoding="utf-8")
    for old, new in _STANDALONE_SUBSTITUTIONS:
        html = html.replace(old, new)
    return html.encode("utf-8")


def config() -> ScreenerSessionConfig:
    """A config carrying a fixture cookie; the seam never reads its value."""
    return ScreenerSessionConfig(
        credentials=ScreenerCredentials(session_cookie=SecretStr(SESSION_TOKEN)),
        min_request_spacing_seconds=0,
    )


def read(
    monkeypatch: pytest.MonkeyPatch,
    *,
    parts: tuple[CompanyPart, ...] = ALL_PARTS,
    basis: Basis = Basis.CONSOLIDATED,
    **kwargs: Any,
) -> tuple[CompanyRun, list[str]]:
    """Read the fixture page and its sub-documents through the real code path."""
    requested = serve(monkeypatch, **kwargs)
    source = ScreenerSessionSource(config())
    page_fetch = source.fetch_company_page(
        symbol=SYMBOL,
        slug=SYMBOL,
        basis=basis,
        expected_company_id=COMPANY_ID,
        topology=BasisTopology(
            consolidated_warehouse_id=CONSOLIDATED_WAREHOUSE_ID,
            standalone_warehouse_id=STANDALONE_WAREHOUSE_ID,
        ),
    )
    run = read_company(page_fetch, company_id=COMPANY_ID, parts=parts, source=source)
    return run, requested


def run_only(monkeypatch: pytest.MonkeyPatch, **kwargs: Any) -> CompanyRun:
    """The run alone, for the tests that do not inspect the request log."""
    return read(monkeypatch, **kwargs)[0]


def page_root(source: Path | None = None) -> Any:
    """The parsed fixture company page."""
    return parse_document((source or PAGE).read_text(encoding="utf-8"))


def document(name: str) -> bytes:
    """One committed sub-document fixture by file name."""
    return (DOCUMENTS / name).read_bytes()


def bucket(run: CompanyRun, key: str, periodicity: str) -> Any:
    """One investor bucket of a run, by API key and periodicity."""
    return next(
        found
        for found in run.artifact.investors
        if found.bucket == key and found.periodicity.value == periodicity
    )


def segments_table(run: CompanyRun, section: str) -> Any:
    """One segments table of a run, by the page section it expands."""
    return next(found for found in run.artifact.segments if found.section == section)


def outcome(run: CompanyRun, part: CompanyPart) -> Any:
    """One part outcome of a run."""
    return next(found for found in run.artifact.outcomes if found.part is part)


class _FakeResponse:
    """The minimum of a urllib response the transport reads.

    ``headers`` is part of that minimum: a real ``http.client.HTTPResponse``
    always exposes one, and the transport reads it to hand response headers
    back to callers. Omitting it here would push a defensive ``getattr`` into
    production code to accommodate a shortcoming of this double.
    """

    def __init__(self, status: int, payload: bytes) -> None:
        self._status = status
        self._payload = payload
        self.headers = email.message.Message()

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def getcode(self) -> int:
        return self._status

    def read(self, _size: int) -> bytes:
        return self._payload


def capture_requests(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Intercept the real ``urllib`` request objects the transport builds.

    The other helpers pin the seam one level higher, at ``_fetch_bytes``, which
    is where the fixture bodies come from. That seam cannot see headers, so a
    test about what actually goes on the wire has to reach the request object
    itself.
    """
    built: list[Any] = []

    class _Opener:
        def open(self, request: Any, timeout: float | None = None) -> _FakeResponse:
            del timeout
            built.append(request)
            body = PAGE.read_bytes() if "/company/FIXTURECO/" in request.full_url else b"{}"
            return _FakeResponse(200, body)

    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: _Opener())
    return built


def promoters_body(
    *, holders: int = 410, drop: str | None = None, duplicate: str | None = None
) -> bytes:
    """A synthetic promoters body of ``holders`` names summing to the page row.

    Generated rather than committed: 410 holders is what TITAN actually
    publishes, and a fixture that large would be unreadable in review while its
    only interesting property — that it sums to 60.00 / 60.00 / 59.50 exactly —
    is one line of arithmetic here.

    ``drop`` removes one named holder, which is what a response missing a real
    shareholder looks like. ``duplicate`` emits one holder key twice, which JSON
    permits and ``json.loads`` silently resolves last-one-wins.
    """
    rest = holders - 2
    values = [("Fixture Anchor Holding", ("1.50", "1.50", "1.50"))]
    values.extend(
        (f"Fixture Nominee {index:03d}", ("0.14", "0.14", "0.14")) for index in range(rest)
    )
    tail = [
        Decimal("60.00") - Decimal("1.50") - Decimal("0.14") * rest,
        Decimal("60.00") - Decimal("1.50") - Decimal("0.14") * rest,
        Decimal("59.50") - Decimal("1.50") - Decimal("0.14") * rest,
    ]
    values.append(("Fixture Residual Trust", tuple(f"{value:.2f}" for value in tail)))

    periods = ("Sep 2025", "Dec 2025", "Mar 2026")
    entries = []
    for position, (name, cells) in enumerate(values):
        if name == drop:
            continue
        holder = {period: cell for period, cell in zip(periods, cells, strict=True)}
        holder["setAttributes"] = {"data-person-url": f"/people/{9000 + position}/fixture/"}
        entries.append((name, holder))
        if name == duplicate:
            entries.append((name, holder))
    body = ",".join(f"{json.dumps(name)}: {json.dumps(holder)}" for name, holder in entries)
    return ("{" + body + "}").encode("utf-8")
