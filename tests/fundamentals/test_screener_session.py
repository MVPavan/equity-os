"""Fixture-only coverage for the subscriber Screener transport and its gates.

No test opens a socket: ``urllib``'s opener is replaced with a recording double
that serves committed synthetic bodies whose structure mirrors real captured
subscriber pages (private captures, never committed).

The gates under test all exist because this source fails *quietly*: an expired
cookie is answered with a valid anonymous page, a standalone-only company
answers its consolidated URL with HTTP 200, and peer widgets carry other
companies' identifiers. Every test below states which of those it pins.
"""

from __future__ import annotations

import email.message
import hashlib
import io
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from structlog.testing import capture_logs

from fundamentals.ingest.screener_session import ScreenerSessionSource
from fundamentals.ingest.screener_session_models import (
    AnonymousPageError,
    Basis,
    BasisEvidenceMissingError,
    BasisMismatchError,
    BasisTopology,
    IdentityAmbiguousError,
    IdentityMismatchError,
    PageOutcome,
    ScreenerBlockedError,
    ScreenerCredentials,
    ScreenerCredentialsError,
    ScreenerOriginError,
    ScreenerPageFetch,
    ScreenerRateLimitedError,
    ScreenerRedirectError,
    ScreenerSessionConfig,
    assert_pinned_origin,
)

_FIXTURES = Path(__file__).parent / "fixtures"
_SESSION_TOKEN = "fixture-session-token"
_SYMBOL = "FIXTURECO"
_SLUG = "FIXTURECO"
_COMPANY_ID = 991001
_WAREHOUSE_CONSOLIDATED = 992001
_WAREHOUSE_STANDALONE = 992002
_SOLO_SYMBOL = "SOLOCO"
_SOLO_COMPANY_ID = 991002
_SOLO_WAREHOUSE_STANDALONE = 992003

# Topology is configuration, so the tests state it explicitly: a dual-basis
# company publishes both bases, a standalone-only one publishes exactly one.
_DUAL_BASIS = BasisTopology(
    consolidated_warehouse_id=_WAREHOUSE_CONSOLIDATED,
    standalone_warehouse_id=_WAREHOUSE_STANDALONE,
)
_SINGLE_BASIS = BasisTopology(standalone_warehouse_id=_SOLO_WAREHOUSE_STANDALONE)


def _body(name: str) -> bytes:
    """Read one committed synthetic company-page body."""
    return (_FIXTURES / f"synthetic_screener_session_{name}.html").read_bytes()


class _Response(io.BytesIO):
    """Minimal urllib response double carrying a status."""

    def __init__(self, payload: bytes, *, status: int = 200) -> None:
        super().__init__(payload)
        self._status = status
        self.headers: dict[str, str] = {}

    def getcode(self) -> int:
        """Return the configured HTTP status code."""
        return self._status

    def __enter__(self) -> _Response:
        """Support the ``with opener.open(...)`` form the adapter uses."""
        return self

    def __exit__(self, *exc: object) -> None:
        """Close the response body."""
        self.close()


class _Opener:
    """Injectable urllib opener that replays a scripted sequence of outcomes."""

    def __init__(self, *outcomes: _Response | urllib.error.HTTPError) -> None:
        self._outcomes = list(outcomes)
        self.calls: list[urllib.request.Request] = []

    def open(self, request: urllib.request.Request, timeout: float) -> _Response:
        """Record the outbound request and return (or raise) the next outcome."""
        del timeout
        self.calls.append(request)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, urllib.error.HTTPError):
            raise outcome
        return outcome


def _http_error(status: int, *, location: str | None = None) -> urllib.error.HTTPError:
    """Build an HTTPError the way urllib raises one, with real headers."""
    headers = email.message.Message()
    if location is not None:
        headers["Location"] = location
    return urllib.error.HTTPError("https://www.screener.in/", status, "error", headers, None)


def _install(monkeypatch: pytest.MonkeyPatch, opener: _Opener) -> list[float]:
    """Pin opener construction and capture every sleep instead of serving it."""
    slept: list[float] = []

    def build_opener(handler: Any) -> _Opener:
        del handler
        return opener

    monkeypatch.setattr(urllib.request, "build_opener", build_opener)
    monkeypatch.setattr(
        "fundamentals.ingest.screener_session.time.sleep", lambda seconds: slept.append(seconds)
    )
    return slept


def _source(**overrides: Any) -> ScreenerSessionSource:
    """A subscriber source with a synthetic cookie and no real pacing delay."""
    settings: dict[str, Any] = {
        "credentials": ScreenerCredentials(session_cookie=_SESSION_TOKEN),
        "min_request_spacing_seconds": 0.0,
        "rate_limit_backoff_seconds": 0.0,
    }
    settings.update(overrides)
    return ScreenerSessionSource(ScreenerSessionConfig(**settings))


def _fetch(
    source: ScreenerSessionSource,
    *,
    basis: Basis = Basis.CONSOLIDATED,
    symbol: str = _SYMBOL,
    company_id: int = _COMPANY_ID,
    topology: BasisTopology = _DUAL_BASIS,
) -> ScreenerPageFetch:
    """Fetch one page against the configured identity and topology under test."""
    return source.fetch_company_page(
        symbol=symbol,
        slug=_SLUG,
        basis=basis,
        expected_company_id=company_id,
        topology=topology,
    )


def test_a_consolidated_page_is_proven_by_its_own_marker_and_warehouse_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Basis is a fact read off the page, never inferred from the URL requested."""
    opener = _Opener(_Response(_body("consolidated")))
    _install(monkeypatch, opener)

    fetch = _fetch(_source())

    metadata = fetch.metadata
    assert metadata.outcome is PageOutcome.OK
    assert metadata.basis_requested is Basis.CONSOLIDATED
    assert metadata.basis_observed is Basis.CONSOLIDATED
    assert metadata.single_basis is False
    assert metadata.markers == ("Consolidated Figures", "View Standalone")
    assert metadata.warehouse_id_seen == _WAREHOUSE_CONSOLIDATED
    assert metadata.company_id_seen == _COMPANY_ID
    assert metadata.tables_empty is False
    assert metadata.http_status == 200
    assert opener.calls[0].full_url == "https://www.screener.in/company/FIXTURECO/consolidated/"


def test_the_standalone_url_is_the_bare_company_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """The two bases are two URLs; a standalone request must not append /consolidated/."""
    opener = _Opener(_Response(_body("standalone")))
    _install(monkeypatch, opener)

    fetch = _fetch(_source(), basis=Basis.STANDALONE)

    assert opener.calls[0].full_url == "https://www.screener.in/company/FIXTURECO/"
    assert fetch.metadata.basis_observed is Basis.STANDALONE
    assert fetch.metadata.warehouse_id_seen == _WAREHOUSE_STANDALONE


def test_the_session_cookie_is_sent_as_a_sessionid_header_and_never_logged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The cookie is owner auth material: it may reach the wire, never a log or artifact."""
    opener = _Opener(_Response(_body("consolidated")))
    _install(monkeypatch, opener)

    with capture_logs() as logs:
        fetch = _fetch(_source())

    assert opener.calls[0].get_header("Cookie") == f"sessionid={_SESSION_TOKEN}"
    assert opener.calls[0].get_header("User-agent") == "EquityOS Research"
    assert _SESSION_TOKEN not in json.dumps(logs)
    assert _SESSION_TOKEN not in fetch.metadata.model_dump_json()


def test_an_anonymous_page_must_never_parse_as_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """An expired cookie yields a VALID page: only the Account menu proves the session.

    Without this gate the run would record a logged-out page as subscriber
    evidence — the failure mode that is wrong-but-plausible rather than loud.
    """
    _install(monkeypatch, _Opener(_Response(_body("anonymous"))))

    with pytest.raises(AnonymousPageError, match="no Account menu"):
        _fetch(_source())


def test_a_page_for_another_company_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Identity binds to the page's own data-company-id, so a swapped page cannot pass."""
    _install(monkeypatch, _Opener(_Response(_body("wrong_identity"))))

    with pytest.raises(IdentityMismatchError, match="company id 991999"):
        _fetch(_source())


def test_a_warehouse_id_from_the_other_basis_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """The warehouse id is per basis and scopes peers/quick_ratios: it must match that basis."""
    _install(monkeypatch, _Opener(_Response(_body("consolidated"))))
    swapped = BasisTopology(
        consolidated_warehouse_id=_WAREHOUSE_STANDALONE,
        standalone_warehouse_id=_WAREHOUSE_CONSOLIDATED,
    )

    with pytest.raises(IdentityMismatchError, match="warehouse id 992001"):
        _fetch(_source(), topology=swapped)


def test_a_login_redirect_is_refused_rather_than_followed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Following the login bounce would turn a dead session into a plausible page."""
    opener = _Opener(_http_error(302, location="/login/"))
    _install(monkeypatch, opener)

    with pytest.raises(ScreenerRedirectError, match="/login/"):
        _fetch(_source())

    assert len(opener.calls) == 1


def test_a_rate_limited_fetch_backs_off_within_its_bound_and_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """429 is a typed outcome with bounded backoff, not a reason to hammer the host."""
    opener = _Opener(_http_error(429), _Response(_body("consolidated")))
    slept = _install(monkeypatch, opener)

    fetch = _fetch(_source(rate_limit_backoff_seconds=2.0))

    assert fetch.metadata.outcome is PageOutcome.OK
    assert len(opener.calls) == 2
    assert slept == [2.0]


def test_an_exhausted_rate_limit_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """After the configured retries the run stops; it never works around the limit."""
    opener = _Opener(*(_http_error(429) for _ in range(3)))
    slept = _install(monkeypatch, opener)

    with pytest.raises(ScreenerRateLimitedError, match="rate-limited"):
        _fetch(_source(max_rate_limit_retries=2, rate_limit_backoff_seconds=1.0))

    assert len(opener.calls) == 3
    # Exponential, and bounded to the two configured retries.
    assert slept == [1.0, 2.0]


@pytest.mark.parametrize("status", [403, 451])
def test_a_terminal_block_is_never_retried(monkeypatch: pytest.MonkeyPatch, status: int) -> None:
    """A block is the host's answer; retrying it would be working around a refusal."""
    opener = _Opener(_http_error(status))
    _install(monkeypatch, opener)

    with pytest.raises(ScreenerBlockedError, match=str(status)):
        _fetch(_source())

    assert len(opener.calls) == 1


def test_a_standalone_only_company_reports_single_basis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A company with no basis toggle publishes no marker; its one page is standalone.

    Recorded as ``single_basis`` rather than treated as missing evidence, so a
    later slice can tell "no consolidated figures exist" from "the marker moved".
    """
    _install(monkeypatch, _Opener(_Response(_body("single_basis"))))

    fetch = _fetch(
        _source(),
        basis=Basis.STANDALONE,
        symbol=_SOLO_SYMBOL,
        company_id=_SOLO_COMPANY_ID,
        topology=_SINGLE_BASIS,
    )

    metadata = fetch.metadata
    assert metadata.outcome is PageOutcome.OK
    assert metadata.basis_observed is Basis.STANDALONE
    assert metadata.single_basis is True
    assert metadata.markers == ()
    assert metadata.tables_empty is False


def test_the_degenerate_consolidated_page_is_never_reported_as_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A standalone-only company answers /consolidated/ with HTTP 200 and an empty shell.

    Status 200 plus eleven present sections is exactly what a valid page looks
    like, so the outcome must come from the failed positive rule (no marker, no
    warehouse id) — with table emptiness recorded as corroborating fact only.
    """
    _install(monkeypatch, _Opener(_Response(_body("basis_unavailable"))))

    fetch = _fetch(
        _source(),
        symbol=_SOLO_SYMBOL,
        company_id=_SOLO_COMPANY_ID,
        topology=_SINGLE_BASIS,
    )

    metadata = fetch.metadata
    assert metadata.outcome is PageOutcome.BASIS_UNAVAILABLE
    assert metadata.basis_requested is Basis.CONSOLIDATED
    assert metadata.basis_observed is None
    assert metadata.single_basis is True
    assert metadata.warehouse_id_seen is None
    assert metadata.tables_empty is True
    assert metadata.http_status == 200


def test_a_substituted_basis_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serving standalone figures for a consolidated request must never pass silently."""
    _install(monkeypatch, _Opener(_Response(_body("standalone"))))

    with pytest.raises(BasisMismatchError, match="declares basis standalone"):
        _fetch(_source())


def test_requests_are_spaced_by_the_configured_minimum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sequential authenticated GETs at ~0.6 s were rate-limited after ~40 requests."""
    opener = _Opener(_Response(_body("consolidated")), _Response(_body("consolidated")))
    slept = _install(monkeypatch, opener)
    source = _source(min_request_spacing_seconds=1.5)

    _fetch(source)
    _fetch(source)

    assert len(slept) == 1
    assert 0 < slept[0] <= 1.5


def test_the_retained_bytes_are_the_bytes_that_were_hashed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A recorded hash is worthless unless it covers the body kept beside it."""
    payload = _body("consolidated")
    _install(monkeypatch, _Opener(_Response(payload)))

    fetch = _fetch(_source())

    assert fetch.raw_body == payload
    assert fetch.metadata.content_sha256 == hashlib.sha256(payload).hexdigest()
    assert fetch.metadata.byte_count == len(payload)


def test_a_fetch_without_credentials_is_refused_before_any_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No cookie means an anonymous page would be served: refuse instead of asking."""
    opener = _Opener()
    _install(monkeypatch, opener)
    source = ScreenerSessionSource(ScreenerSessionConfig())

    with pytest.raises(ScreenerCredentialsError, match="session cookie required"):
        _fetch(source)

    assert opener.calls == []


def test_a_dual_basis_page_that_lost_its_marker_is_drift_not_a_single_basis_company(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unmarked page must never be read as "this company has only one basis".

    Config records both bases for this company, so its standalone page carrying
    a warehouse id but no marker is the site changing under us. Inferring
    topology from the page would turn that drift into a false structural claim
    about the issuer, recorded as a clean success.
    """
    _install(monkeypatch, _Opener(_Response(_body("marker_stripped"))))

    with pytest.raises(BasisEvidenceMissingError, match="no basis marker"):
        _fetch(_source(), basis=Basis.STANDALONE)


def test_a_page_missing_marker_and_warehouse_id_is_refused_not_called_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BASIS_UNAVAILABLE is a claim about the company; only config may license it.

    Config publishes this company's consolidated basis, so a consolidated page
    with neither marker nor warehouse id is drift — recording it as
    BASIS_UNAVAILABLE would assert, on the strength of a broken page, that the
    company files no consolidated accounts.
    """
    _install(monkeypatch, _Opener(_Response(_body("evidence_missing"))))

    with pytest.raises(BasisEvidenceMissingError, match="carries no data-warehouse-id"):
        _fetch(_source())


def test_a_basis_config_says_is_unpublished_may_not_be_acquired_from_the_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If a company gains a basis, that is a fact to re-verify, not to acquire silently."""
    _install(monkeypatch, _Opener(_Response(_body("consolidated"))))

    with pytest.raises(BasisEvidenceMissingError, match="config records no consolidated basis"):
        _fetch(
            _source(),
            symbol=_SOLO_SYMBOL,
            company_id=_SOLO_COMPANY_ID,
            topology=_SINGLE_BASIS,
        )


def test_single_basis_is_reported_from_config_not_from_the_absence_of_a_marker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The flag states what config records; the page only has to corroborate it."""
    _install(monkeypatch, _Opener(_Response(_body("consolidated"))))

    fetch = _fetch(_source())

    assert fetch.metadata.single_basis is False
    assert fetch.metadata.markers == ("Consolidated Figures", "View Standalone")


def test_a_decoy_identity_element_cannot_answer_for_the_real_company(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two identity elements make identity a matter of document order.

    The fixture puts the EXPECTED ids in a decoy ahead of the real element,
    which names another company: trusting the first match would pass it.
    """
    _install(monkeypatch, _Opener(_Response(_body("decoy_identity"))))

    with pytest.raises(IdentityAmbiguousError, match="2 #company-info"):
        _fetch(_source())


def test_an_off_origin_url_never_reaches_the_opener(monkeypatch: pytest.MonkeyPatch) -> None:
    """The session cookie is owner auth material: it may only ever leave for Screener."""
    opener = _Opener(_Response(_body("consolidated")))
    _install(monkeypatch, opener)
    monkeypatch.setattr(
        "fundamentals.ingest.screener_session.company_page_url",
        lambda slug, basis: "https://evil.example.com/company/FIXTURECO/consolidated/",
    )

    with pytest.raises(ScreenerOriginError, match="off-origin"):
        _fetch(_source())

    assert opener.calls == []


@pytest.mark.parametrize(
    "url",
    [
        "http://www.screener.in/company/TITAN/",
        "https://screener.in.evil.example/company/TITAN/",
        "https://www.screener.in:8443/company/TITAN/",
        "https://user:pass@www.screener.in/company/TITAN/",
        "https://evil.example/company/TITAN/",
    ],
)
def test_only_the_pinned_origin_is_accepted(url: str) -> None:
    """Scheme, exact host, port, and credentials are all part of "the same origin"."""
    with pytest.raises(ScreenerOriginError):
        assert_pinned_origin(url)


@pytest.mark.parametrize(
    "settings",
    [
        {"request_timeout_seconds": 600.0},
        {"request_timeout_seconds": float("inf")},
        {"request_timeout_seconds": 0.0},
        {"min_request_spacing_seconds": float("nan")},
        {"max_rate_limit_retries": 5},
        {"rate_limit_backoff_seconds": 90.0},
        # Within the per-attempt bound, but the doubling blows the total budget.
        {"rate_limit_backoff_seconds": 50.0, "max_rate_limit_retries": 2},
    ],
)
def test_unbounded_timing_settings_are_rejected(settings: dict[str, Any]) -> None:
    """Injected timing must not be able to turn a polite fetcher into a hang or a hammer."""
    with pytest.raises(ValidationError):
        ScreenerSessionConfig(**settings)


def test_a_consolidated_only_topology_still_requires_the_consolidated_marker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Marker absence is excused for exactly one shape, and this is not it.

    Screener renders an unmarked page only where no basis toggle exists, which
    §10 evidences solely for a standalone-only company. A consolidated page
    always carries "Consolidated Figures", so excusing the marker for any
    single-basis topology would accept a marker-stripped page as consolidated.
    """
    _install(monkeypatch, _Opener(_Response(_body("marker_stripped"))))
    consolidated_only = BasisTopology(consolidated_warehouse_id=_WAREHOUSE_STANDALONE)

    with pytest.raises(BasisEvidenceMissingError, match="no basis marker"):
        _fetch(_source(), topology=consolidated_only)


def test_a_marked_page_under_a_standalone_only_topology_is_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A marker where config says no toggle exists means the company gained a basis."""
    _install(monkeypatch, _Opener(_Response(_body("standalone"))))
    standalone_only = BasisTopology(standalone_warehouse_id=_WAREHOUSE_STANDALONE)

    with pytest.raises(BasisEvidenceMissingError, match="basis toggle appeared"):
        _fetch(_source(), basis=Basis.STANDALONE, topology=standalone_only)
