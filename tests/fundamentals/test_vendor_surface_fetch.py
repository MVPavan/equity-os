"""The only outbound boundary refuses actions and durably keeps failures."""

import http.client
import io
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import OpenerDirector

import pytest
from pydantic import SecretStr

from fundamentals.contracts.snapshot import BodyCompleteness


class Opener(OpenerDirector):
    """A bounded in-memory HTTP boundary, with a call log."""

    def __init__(self, status=200, location=None, partial=False):
        super().__init__()
        self.status, self.partial, self.calls = status, partial, []
        self.headers = Message()
        self.headers["Content-Type"] = "text/plain"
        if location:
            self.headers["Location"] = location

    def open(self, request, timeout):
        self.calls.append(request)
        body = io.BytesIO(b"fixture")
        if self.partial:
            body = Partial()
        response = HTTPError(request.full_url, self.status, "fixture", self.headers, body)
        if self.status != 200:
            raise response
        return response


class Partial(io.BytesIO):
    def read(self, amount=-1):
        raise http.client.IncompleteRead(b"prefix")


class Lock:
    def __init__(self, held=False):
        self.held = held

    def acquire(self, site):
        return not self.held


def fetcher(tmp_path, opener, lock=None, budget=350):
    from fundamentals.ingest.vendor_surface_fetch import Site, SiteSession, VendorFetcher
    from fundamentals.store.snapshot_store import SnapshotStore

    site = Site.SCREENER
    store = SnapshotStore(tmp_path / "store")
    session = SiteSession(site=site, session_cookie=SecretStr("synthetic"), cookie_name="sessionid")
    return VendorFetcher(
        store,
        {site: session},
        opener,
        tmp_path,
        lock or Lock(),
        spacing_seconds=0,
        site_budget=budget,
    ), store


WORDS = (
    "logout delete remove add create rename save edit follow unfollow subscribe toggle upgrade "
    "payment alert connect sync reset refresh ai flag ask mark share-by-email"
).split()
KEYS = "ack acked mark mark_read mark_as_seen seen read dismiss".split()


@pytest.mark.parametrize(
    "path",
    [f"/{word}/" for word in WORDS]
    + [f"/x/{word}-x/" for word in WORDS]
    + [f"/x/x_{word}/" for word in WORDS]
    + [f"/ok/?{key}=true" for key in WORDS + KEYS]
    + [
        "/in/watchlist/company/1",
        "/user/account/",
        "/portfolio/",
        "/in/alerts/",
        "/in/edit-columns/",
        "/capsules/1/stock-alerts/",
        "/alerts/",
        "/api/portfolio/family_summary/",
        "/settings/",
        "/profile/",
        "/api/portfolio/task-status/",
        "/annual-reports/1/summary/",
        "/concalls/summary/1/",
        "/results/concall-summaries/",
        "/%2e%2e/watchlist/../delete/",
        "//in//watchlist/company/1",
        "/capsules/1/delete/stock-alerts/",
        "/capsules/delete/stock-alerts/",
    ],
)
def test_deny_list(path):
    from fundamentals.ingest.vendor_surface_fetch import is_denied, normalise

    assert is_denied(normalise("https://www.screener.in" + path))


@pytest.mark.parametrize(
    "path",
    [
        "/company/ask-automotive-ltd/",
        "/filter/saved-queries/",
    ],
)
def test_read_only_exceptions(path):
    from fundamentals.ingest.vendor_surface_fetch import is_denied, normalise

    assert not is_denied(normalise("https://www.screener.in" + path))


@pytest.mark.parametrize(
    "url",
    [
        "http://www.screener.in/",
        "https://screener.in/",
        "https://www.screener.in:8443/",
        "https://user@www.screener.in/",
        "https://www.screener.in/%2e%2e/delete/",
        "https://www.screener.in//in//watchlist/company/1",
        "https://www.screener.in/%2e%2e/watchlist/",
        "https://www.screener.in//in//watchlist",
    ],
)
def test_refused_before_open(tmp_path, url):
    from fundamentals.ingest.vendor_surface_fetch import Site

    opener = Opener()
    client, _ = fetcher(tmp_path, opener)
    with pytest.raises(ValueError):
        client.get(Site.SCREENER, "chart-api", url)
    assert opener.calls == []


@pytest.mark.parametrize(
    ("status", "location", "stop"),
    [
        (429, None, True),
        (429, "https://[", True),
        (302, "https://[", False),
        (403, None, True),
        (503, None, True),
        (302, "/login/", True),
        (302, "/%6cogin/", True),
        (302, "https://WWW.SCREENER.IN/login/", True),
        (302, "https://example.com/document", False),
        (302, "https://example.com/login/", False),
    ],
)
def test_response_retained_before_stop(tmp_path, status, location, stop):
    from fundamentals.ingest.vendor_surface_fetch import Site, SiteStopped

    opener = Opener(status, location)
    client, store = fetcher(tmp_path, opener)
    if stop:
        with pytest.raises(SiteStopped) as raised:
            client.get(Site.SCREENER, "chart-api", "https://www.screener.in/api/chart/")
        fetched = raised.value.fetched
        assert fetched is not None
        assert not (tmp_path / "STOP-screener-subscriber").exists()
    else:
        fetched = client.get(Site.SCREENER, "chart-api", "https://www.screener.in/api/chart/")
    assert fetched.location == location
    assert store.read_body(fetched.record) == b"fixture"
    assert len(opener.calls) == 1


def test_partial_busy_and_budget(tmp_path: Path):
    from fundamentals.ingest.vendor_surface_fetch import Site, SiteBusy

    opener = Opener(partial=True)
    client, store = fetcher(tmp_path, opener, budget=1)
    fetched = client.get(Site.SCREENER, "chart-api", "https://www.screener.in/api/chart/")
    assert fetched.record.effective_body_completeness is BodyCompleteness.PARTIAL
    assert store.read_evidence_body(fetched.record) == b"prefix"
    assert client.remaining(Site.SCREENER) == 0
    with pytest.raises(ValueError, match="budget"):
        client.get(Site.SCREENER, "chart-api", fetched.url)
    busy, _ = fetcher(tmp_path, opener, Lock(held=True))
    with pytest.raises(SiteBusy):
        busy.get(Site.SCREENER, "chart-api", fetched.url)
    assert len(opener.calls) == 1


def test_injected_standard_opener_cannot_follow_redirect(tmp_path):
    from urllib.request import HTTPSHandler, build_opener
    from urllib.response import addinfourl

    from fundamentals.ingest.vendor_surface_fetch import Site

    calls = []

    class Responses(HTTPSHandler):
        def https_open(self, request):
            calls.append(request.full_url)
            headers = Message()
            if len(calls) == 1:
                headers["Location"] = "https://example.com/document"
            response = addinfourl(
                io.BytesIO(b"fixture"), headers, request.full_url, 302 if len(calls) == 1 else 200
            )
            response.msg = "fixture"
            return response

    client, _ = fetcher(tmp_path, build_opener(Responses()))
    fetched = client.get(Site.SCREENER, "chart-api", "https://www.screener.in/chart/")
    assert fetched.record.http_status == 302
    assert fetched.location == "https://example.com/document"
    assert calls == ["https://www.screener.in/chart/"]


def test_stop_rechecked_after_site_lock(tmp_path):
    from fundamentals.ingest.vendor_surface_fetch import Site, SiteStopped

    class StoppingLock:
        def acquire(self, site):
            (tmp_path / f"STOP-{site}").write_text("another command stopped\n")
            return True

    opener = Opener()
    client, _ = fetcher(tmp_path, opener, StoppingLock())
    with pytest.raises(SiteStopped):
        client.get(Site.SCREENER, "chart-api", "https://www.screener.in/chart/")
    assert not opener.calls


def test_sessions_resolve_only_selected_site(monkeypatch):
    from fundamentals.api.vendor_surface_cli import sessions
    from fundamentals.ingest.vendor_surface_fetch import Site

    monkeypatch.setenv("SCREENER_SESSION_COOKIE", "synthetic")
    monkeypatch.setenv("TIJORI_EMAIL", "synthetic@example.com")
    monkeypatch.delenv("TIJORI_SESSION_COOKIE", raising=False)
    assert set(sessions({Site.SCREENER})) == {Site.SCREENER}


def test_missing_session_refused_before_fetch():
    from fundamentals.api.cli_parser import build_parser
    from fundamentals.api.vendor_surface_cli import dispatch_vendor_command

    args = build_parser().parse_args(
        ["vendor", "capture", "--symbol", "APARINDS", "--surface", "screener:chart-api"]
    )
    with pytest.raises(ValueError, match="missing vendor session: screener-subscriber"):
        dispatch_vendor_command(
            args,
            sessions_factory=lambda sites: {},
            pool_factory=lambda: pytest.fail("credentials must be checked before opening the pool"),
        )
