"""Tests for the fail-closed Tijori JSON-island adapter."""

from __future__ import annotations

import urllib.error
import urllib.request
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from fundamentals.api.watchlist_config import load_watchlist_config
from fundamentals.contracts.observation import AccountingFramework, Scope
from fundamentals.contracts.provenance import SourceAnchorType
from fundamentals.ingest.tijori_source import (
    SOURCE_ID,
    TijoriCredentials,
    TijoriCredentialsError,
    TijoriFetchError,
    TijoriParseError,
    TijoriSource,
    TijoriSourceConfig,
    is_tijori_derived,
)

_FIXTURES = Path(__file__).parent / "fixtures"
_HTML_FIXTURE = _FIXTURES / "synthetic_tijori_financials.html"
_WRONG_IDENTITY_FIXTURE = _FIXTURES / "synthetic_tijori_wrong_identity.html"
_REPO_ROOT = Path(__file__).resolve().parents[2]
_TITAN_SLUG = "titan-company-limited"
_TITAN_SYMBOL = "TITAN"
_TITAN_PERIOD_END = date(2024, 12, 31)
_TITAN_URL = "https://www.tijorifinance.com/company/titan-company-limited/financials/"


def _parse_titan(raw: bytes) -> tuple:
    """Parse one raw fixture through the adapter's public identity seam."""
    return TijoriSource.parse_pl_bytes(
        raw,
        slug=_TITAN_SLUG,
        expected_symbol=_TITAN_SYMBOL,
        period_end=_TITAN_PERIOD_END,
        source_url=_TITAN_URL,
    )


class _Response(BytesIO):
    """Controllable HTTP response that records the bounded read requested."""

    def __init__(
        self, payload: bytes, *, status: int = 200, content_length: str | None = None
    ) -> None:
        super().__init__(payload)
        self._status = status
        self.headers: dict[str, str] = {}
        if content_length is not None:
            self.headers["Content-Length"] = content_length
        self.read_sizes: list[int] = []

    def getcode(self) -> int:
        """Return the configured HTTP status code."""
        return self._status

    def read(self, size: int = -1) -> bytes:
        """Record and perform one bounded body read."""
        self.read_sizes.append(size)
        return super().read(size)


class _Opener:
    """Injectable urllib opener that records outbound requests."""

    def __init__(self, outcome: _Response | Exception) -> None:
        self._outcome = outcome
        self.calls: list[tuple[urllib.request.Request, float]] = []

    def open(self, request: urllib.request.Request, timeout: float) -> _Response:
        """Record the one outbound request and return or raise the configured outcome."""
        self.calls.append((request, timeout))
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


def _source(**config: Any) -> TijoriSource:
    """Build a live source with a synthetic, redacted session cookie."""
    return TijoriSource(
        TijoriSourceConfig(
            credentials=TijoriCredentials(session_cookie="session-token"),
            **config,
        )
    )


def _install_opener(
    monkeypatch: pytest.MonkeyPatch, opener: _Opener
) -> list[urllib.request.HTTPRedirectHandler]:
    """Patch opener construction and capture the supplied redirect policy."""
    handlers: list[urllib.request.HTTPRedirectHandler] = []

    def build_opener(handler: urllib.request.HTTPRedirectHandler) -> _Opener:
        handlers.append(handler)
        return opener

    monkeypatch.setattr(urllib.request, "build_opener", build_opener)
    return handlers


def test_json_islands_emit_only_three_consolidated_pnl_observations() -> None:
    """The live DOM's exact quarter maps Net Sales, PBT, and Net Profit only."""
    observations = _parse_titan(_HTML_FIXTURE.read_bytes())
    by_concept = {observation.concept_qname: observation for observation in observations}

    assert set(by_concept) == {
        "tijori:sales",
        "tijori:pbt",
        "tijori:net_profit",
    }
    assert by_concept["tijori:sales"].normalized_value == Decimal("17740.0")
    assert by_concept["tijori:pbt"].normalized_value == Decimal("1396.0")
    assert by_concept["tijori:net_profit"].normalized_value == Decimal("1047.0")
    assert all(observation.raw_value.endswith(".0") for observation in observations)
    assert all(observation.normalized_unit == "INR crore" for observation in observations)
    assert all(observation.scope is Scope.CONSOLIDATED for observation in observations)
    assert {observation.accounting_basis for observation in observations} == {
        AccountingFramework.UNKNOWN
    }
    assert all(is_tijori_derived(observation) for observation in observations)


def test_identity_substitution_fails_closed_naming_both_symbols() -> None:
    """A valid JSON page for another issuer must not become a TITAN observation."""
    with pytest.raises(TijoriParseError, match="requested symbol 'TITAN', response symbol 'OTHER'"):
        _parse_titan(_WRONG_IDENTITY_FIXTURE.read_bytes())


def test_missing_financials_island_fails_closed() -> None:
    """A page missing its financials island cannot be treated as an empty statement."""
    raw = _HTML_FIXTURE.read_bytes().replace(b'id="fin_tables_data"', b'id="other_data"')

    with pytest.raises(TijoriParseError, match="'fin_tables_data' is missing"):
        _parse_titan(raw)


def test_unparseable_required_island_fails_closed_with_its_name() -> None:
    """A broken JSON island has a reason distinct from a missing island."""
    raw = _HTML_FIXTURE.read_bytes().replace(
        b'<script id="is_auth" type="application/json">true</script>',
        b'<script id="is_auth" type="application/json">{</script>',
    )

    with pytest.raises(TijoriParseError, match="'is_auth' is unparseable"):
        _parse_titan(raw)


def test_unauthenticated_page_fails_closed() -> None:
    """Anonymous page rendering does not satisfy the authenticated data contract."""
    raw = _HTML_FIXTURE.read_bytes().replace(
        b'<script id="is_auth" type="application/json">true</script>',
        b'<script id="is_auth" type="application/json">false</script>',
    )

    with pytest.raises(TijoriParseError, match="not authenticated"):
        _parse_titan(raw)


def test_missing_requested_quarter_lists_available_labels() -> None:
    """The adapter selects the configured label, never a positional neighbour."""
    raw = _HTML_FIXTURE.read_bytes().replace(b'"Dec 2024"', b'"Dec 2025"', 1)

    with pytest.raises(TijoriParseError, match="available labels: Sep 2024, Dec 2025, Mar 2025"):
        _parse_titan(raw)


def test_non_numeric_requested_value_fails_closed() -> None:
    """Stringly JSON values cannot bypass the numeric boundary."""
    raw = _HTML_FIXTURE.read_bytes().replace(b"[1200.0,1396.0,1300.0]", b'[1200.0,"1396",1300.0]')

    with pytest.raises(TijoriParseError, match="Profit Before Tax.*non-numeric"):
        _parse_titan(raw)


def test_unhashable_row_name_fails_closed() -> None:
    """A malformed row name must not escape as a dictionary-key TypeError."""
    raw = _HTML_FIXTURE.read_bytes().replace(b'"name":"Net Sales"', b'"name":[]', 1)

    with pytest.raises(TijoriParseError, match="row name must be a string"):
        _parse_titan(raw)


def test_json_fraction_preserves_its_exact_wire_lexeme() -> None:
    """A long JSON fraction must never round-trip through binary float."""
    raw = _HTML_FIXTURE.read_bytes().replace(
        b"[1200.0,1396.0,1300.0]",
        b"[1200.0,0.1000000000000000000000001,1300.0]",
    )

    observations = _parse_titan(raw)

    pbt = next(
        observation for observation in observations if observation.concept_qname == "tijori:pbt"
    )
    assert pbt.normalized_value == Decimal("0.1000000000000000000000001")


def test_json_integer_is_accepted_without_float_conversion() -> None:
    """An integer beyond binary-float precision remains exact."""
    raw = _HTML_FIXTURE.read_bytes().replace(
        b"[1200.0,1396.0,1300.0]",
        b"[1200.0,9007199254740993,1300.0]",
    )

    observations = _parse_titan(raw)

    pbt = next(
        observation for observation in observations if observation.concept_qname == "tijori:pbt"
    )
    assert pbt.normalized_value == Decimal("9007199254740993")


def test_duplicate_requested_quarter_label_fails_closed() -> None:
    """Two requested-quarter columns must not silently select the first value."""
    raw = _HTML_FIXTURE.read_bytes().replace(
        b'["Sep 2024", "Dec 2024", "Mar 2025"]',
        b'["Sep 2024", "Dec 2024", "Dec 2024", "Mar 2025"]',
    )
    raw = raw.replace(b"[16000.0,17740.0,17000.0]", b"[16000.0,17740.0,1.0,17000.0]")
    raw = raw.replace(b"[1200.0,1396.0,1300.0]", b"[1200.0,1396.0,1.0,1300.0]")
    raw = raw.replace(b"[900.0,1047.0,950.0]", b"[900.0,1047.0,1.0,950.0]")

    with pytest.raises(TijoriParseError, match="requested quarter 'Dec 2024' is ambiguous"):
        _parse_titan(raw)


def test_whitespace_altered_requested_label_fails_exact_match() -> None:
    """Whitespace in an untrusted source label must not alter quarter identity."""
    raw = _HTML_FIXTURE.read_bytes().replace(b'"Dec 2024"', b'" Dec 2024 "', 1)

    with pytest.raises(TijoriParseError) as error:
        _parse_titan(raw)

    assert str(error.value) == (
        "tijori requested quarter 'Dec 2024' is absent; "
        "available labels: Sep 2024,  Dec 2024 , Mar 2025"
    )


def test_fetch_uses_one_get_with_a_complete_bounded_read_and_identity_constraints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The live seam makes one secret-safe GET and forwards all parse constraints."""
    response = _Response(_HTML_FIXTURE.read_bytes())
    opener = _Opener(response)
    handlers = _install_opener(monkeypatch, opener)

    observations = _source(max_response_bytes=4 * 1024 * 1024).fetch_pl(
        _TITAN_SLUG,
        expected_symbol=_TITAN_SYMBOL,
        period_end=_TITAN_PERIOD_END,
    )

    assert len(observations) == 3
    assert len(opener.calls) == 1
    request, timeout = opener.calls[0]
    assert request.full_url == _TITAN_URL
    assert request.get_method() == "GET"
    assert request.get_header("Cookie") == "sessionid=session-token"
    assert request.get_header("User-agent") == "EquityOS Research"
    assert timeout == 30.0
    assert response.read_sizes == [4 * 1024 * 1024 + 1]
    assert len(handlers) == 1
    assert handlers[0].redirect_request(request, None, 302, "Found", {}, "/") is None


def test_fetch_rejects_a_configured_company_id_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An optional stable Tijori company ID adds a second identity constraint."""
    opener = _Opener(_Response(_HTML_FIXTURE.read_bytes()))
    _install_opener(monkeypatch, opener)

    with pytest.raises(
        TijoriParseError,
        match="requested company ID 82, response company ID 81",
    ):
        _source(expected_company_id=82).fetch_pl(
            _TITAN_SLUG,
            expected_symbol=_TITAN_SYMBOL,
            period_end=_TITAN_PERIOD_END,
        )

    assert len(opener.calls) == 1


def test_redirect_response_is_a_slug_not_found_skip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown-slug redirects are rejected before the home page can be parsed."""
    redirect = _Response(b"", status=302)
    redirect.headers["Location"] = "/"
    opener = _Opener(redirect)
    _install_opener(monkeypatch, opener)

    with pytest.raises(TijoriFetchError, match="slug not found: redirect"):
        _source().fetch_pl(
            _TITAN_SLUG,
            expected_symbol=_TITAN_SYMBOL,
            period_end=_TITAN_PERIOD_END,
        )

    assert len(opener.calls) == 1


def test_oversized_response_fails_closed_before_parsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The byte cap reads one sentinel byte beyond its limit and rejects it."""
    response = _Response(b"12345")
    opener = _Opener(response)
    _install_opener(monkeypatch, opener)

    with pytest.raises(TijoriFetchError, match="exceeded maximum 4 bytes"):
        _source(max_response_bytes=4).fetch_pl(
            _TITAN_SLUG,
            expected_symbol=_TITAN_SYMBOL,
            period_end=_TITAN_PERIOD_END,
        )

    assert response.read_sizes == [5]


def test_truncated_response_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A response shorter than its advertised body is not parsed as complete."""
    opener = _Opener(_Response(b"1234", content_length="5"))
    _install_opener(monkeypatch, opener)

    with pytest.raises(TijoriFetchError, match="body was truncated"):
        _source().fetch_pl(
            _TITAN_SLUG,
            expected_symbol=_TITAN_SYMBOL,
            period_end=_TITAN_PERIOD_END,
        )


def test_fetch_retries_network_failure_without_sleeping_after_the_last_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Transient transport failures retain bounded retries and no terminal backoff."""
    opener = _Opener(urllib.error.URLError("offline"))
    _install_opener(monkeypatch, opener)
    sleeps: list[float] = []
    monkeypatch.setattr("fundamentals.ingest.tijori_source.time.sleep", sleeps.append)

    with pytest.raises(TijoriFetchError, match="fetch failed after 2 attempts"):
        _source(max_retries=2).fetch_pl(
            _TITAN_SLUG,
            expected_symbol=_TITAN_SYMBOL,
            period_end=_TITAN_PERIOD_END,
        )

    assert len(opener.calls) == 2
    assert sleeps == [1.0]


def test_credentials_and_config_repr_redact_all_secret_values() -> None:
    """Credentials never leak through Pydantic representations."""
    credentials = TijoriCredentials(
        email="owner@example.invalid",
        password="password-secret",
        session_cookie="cookie-secret",
    )
    config = TijoriSourceConfig(credentials=credentials)
    rendered = f"{credentials!r} {credentials} {config!r} {config}"

    for secret in ("owner@example.invalid", "password-secret", "cookie-secret"):
        assert secret not in rendered


def test_missing_credentials_is_a_skippable_error() -> None:
    """The optional derived source remains non-blocking without injected credentials."""
    with pytest.raises(TijoriCredentialsError, match="credentials not provided"):
        TijoriSource().fetch_pl(
            _TITAN_SLUG,
            expected_symbol=_TITAN_SYMBOL,
            period_end=_TITAN_PERIOD_END,
        )


def test_watchlist_carries_verified_tijori_slugs_for_every_stock() -> None:
    """Every live-verified legal-name slug exits only the Tijori configuration gate."""
    watchlist = load_watchlist_config(_REPO_ROOT / "config" / "watchlist.yaml")
    titan = watchlist.stock(_TITAN_SYMBOL)

    assert titan.identifiers.tijori_slug == _TITAN_SLUG
    assert all(stock.identifiers.tijori_slug for stock in watchlist.stocks)
    assert all(
        "tijori_slug" not in stock.identifiers.needs_verification for stock in watchlist.stocks
    )


def test_a_watchlist_reusing_one_tijori_company_id_is_rejected(tmp_path: Path) -> None:
    """A duplicate id would let one issuer's page satisfy another issuer's request."""
    config = tmp_path / "watchlist.yaml"
    config.write_text(
        """
raw_dir: "data/raw/watchlist"
stocks:
  - name: "Alpha Ltd"
    domain: "Test"
    identifiers:
      nse_symbol: "ALPHA"
      bse_scrip: "1"
      screener_slug: "ALPHA"
      screener_company_id: 991001
      screener_warehouse_id_consolidated: 992001
      tijori_slug: "alpha"
      tijori_company_id: 4242
    quarter:
      label: "Q3FY25"
      period_start: "2024-10-01"
      period_end: "2024-12-31"
      knowledge_cutoff: "2025-02-15T00:00:00Z"
  - name: "Beta Ltd"
    domain: "Test"
    identifiers:
      nse_symbol: "BETA"
      bse_scrip: "2"
      screener_slug: "BETA"
      screener_company_id: 991002
      screener_warehouse_id_consolidated: 992002
      tijori_slug: "beta"
      tijori_company_id: 4242
    quarter:
      label: "Q3FY25"
      period_start: "2024-10-01"
      period_end: "2024-12-31"
      knowledge_cutoff: "2025-02-15T00:00:00Z"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="reuses tijori_company_id across stocks: 4242"):
        load_watchlist_config(config)


def test_watchlist_carries_a_verified_tijori_company_id_for_every_stock() -> None:
    """The shareholding heading gate is inert without a configured id, so all ten carry one."""
    watchlist = load_watchlist_config(_REPO_ROOT / "config" / "watchlist.yaml")

    assert watchlist.stock(_TITAN_SYMBOL).identifiers.tijori_company_id == 81
    company_ids = [stock.identifiers.tijori_company_id for stock in watchlist.stocks]
    assert all(company_id > 0 for company_id in company_ids)
    # A duplicated id would silently bind two stocks to one Tijori company.
    assert len(set(company_ids)) == len(company_ids)
    assert all(
        "tijori_company_id" not in stock.identifiers.needs_verification
        for stock in watchlist.stocks
    )


def test_observation_provenance_binds_the_json_island_location() -> None:
    """Each result remains visibly derived and locatable in the source page."""
    observations = _parse_titan(_HTML_FIXTURE.read_bytes())
    expected_rows = {
        "tijori:sales": "Net Sales",
        "tijori:pbt": "Profit Before Tax",
        "tijori:net_profit": "Net Profit",
    }

    for observation in observations:
        assert observation.provenance.source_id == SOURCE_ID
        assert observation.provenance.anchor_type is SourceAnchorType.JSON_ISLAND
        assert observation.provenance.context_ref is not None
        assert observation.provenance.island_id == "fin_tables_data"
        assert observation.provenance.table_key == "qt_c"
        assert observation.provenance.row_label == expected_rows[observation.concept_qname]
        assert observation.provenance.column_label == "Dec 2024"
        assert "#fin_tables_data/qt_c/Dec 2024/" in observation.provenance.context_ref
        assert len(observation.provenance.file_sha256) == 64
