"""D6 Task 3 (T3): acquisition and replay — the freeze protocol (C5), provenance, generations,
recorded denials and the live transport's boundaries (C13).

Only transports are faked: a fixture-serving ``send``, a fake ``requests`` session at the NSE
boundary and a fake final HTTPS handler under urllib. No socket is opened; freeze repos are
``tmp_path`` git repos with a synthetic (``ZZ``) held-out record.
"""

from __future__ import annotations

import email.message
import hashlib
import io
import json
import shlex
import shutil
import urllib.error
import urllib.request
import urllib.response
from collections.abc import Callable
from contextlib import nullcontext
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
import urllib3
import yaml
from onboarding_support import (
    APAR,
    AS_OF,
    FAILURE,
    INCOMPLETE,
    JUN,
    SENTINEL,
    R,
    S,
    U,
    cli,
    count,
    edit,
    freeze,
    freeze_repo,
    fresh_db,
    git,
    recorded,
    serving_transport,
    world,
    write_root,
    yaml_sha,
)
from pg_support import PgTestDatabase
from retained_support import REPO_ROOT

from equity_os.companies.onboarding.discovery import (
    MANIFEST_NAME,
    Capture,
    Request,
    acquiring_fetch,
    authorised,
    replay_fetch,
    screener_search_url,
)
from equity_os.contracts.companies.onboarding import VerificationUnit
from equity_os.contracts.measurement.canonical import Basis
from equity_os.contracts.sourcing.source_catalog import VENDOR_SURFACES
from equity_os.interface.commands.companies import acquisition_authority, onboard_cli
from equity_os.interface.commands.companies.onboard_cli import RETRIEVAL_NAME
from equity_os.interface.entry.cli import main
from equity_os.sourcing.exchange.nse_filings import NSE_API, listing_url
from equity_os.sourcing.transport.http_session import ResponseTooLargeError

__all__ = ["cli"]

CLOCK = datetime(2026, 10, 16, 2, 20, 24, tzinfo=UTC)


def _raising(request: Any) -> tuple[int, bytes]:
    raise AssertionError("replay must not open a transport")


def _manifest_entries(folder: Path) -> list[dict[str, Any]]:
    return list(json.loads((folder / MANIFEST_NAME).read_text())["entries"])


# --- acquisition, replay and the freeze protocol ----------------------------------------------


@pytest.mark.pg
@pytest.mark.retained
def test_acquire_then_replay_is_identical_and_leaks_nothing(
    cli: Callable[..., int],
    pg_db: PgTestDatabase,
    pg_template: PgTestDatabase,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``onboard --acquire`` with only transports faked writes gen-1; replay in a fresh database
    with credentials unset, transports raising and the clock three years on gives the same
    outcome and window; altered retained entries refuse; a second acquisition writes gen-2 and
    leaves gen-1 byte-identical, and an echoed credential lands nowhere. ``acquisition.json``
    carries every D2 field, bound to the committed descriptor entry."""
    repo, implementation, entry = freeze_repo(tmp_path, monkeypatch)
    descriptor = freeze(repo, entry)
    raw = tmp_path / "raw"
    clock = datetime(2026, 10, 16, 2, 20, 24, tzinfo=UTC)
    monkeypatch.setattr(onboard_cli, "live_transport", lambda: serving_transport(world(APAR)))
    monkeypatch.setattr(onboard_cli, "now", lambda: clock)
    acquire = ("--acquire", "--freeze-descriptor", str(descriptor))
    assert cli(APAR, raw, *acquire) == INCOMPLETE
    acquisition = json.loads((raw / "gen-1" / "acquisition.json").read_text())
    head = git(repo, "rev-parse", "HEAD")
    discovery_sha = hashlib.sha256((raw / "gen-1" / MANIFEST_NAME).read_bytes()).hexdigest()
    retrieval_sha = hashlib.sha256((raw / "gen-1" / RETRIEVAL_NAME).read_bytes()).hexdigest()
    assert acquisition == {
        "generation": 1,
        "attempt": 1,
        "freeze_descriptor_sha256": yaml_sha(entry),
        "descriptor_commit": head,
        "acquisition_head": head,
        "implementation_commit": implementation,
        "argv": [
            *("onboard", APAR, "--raw-root", str(raw), "--snapshot-root"),
            *(str(tmp_path / "snapshots"), "--config-root", "config", *acquire),
        ],
        "discovery_manifest_sha256": discovery_sha,
        "retrieval_manifest_sha256": retrieval_sha,
    }
    first = recorded(pg_db)[1]
    gen1 = {p.name: p.read_bytes() for p in (raw / "gen-1").iterdir()}

    for name in ("SCREENER_SESSION_COOKIE", "TIJORI_SESSION_COOKIE", "UPSTOX_ANALYTICS_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(onboard_cli, "live_transport", lambda: _raising)
    monkeypatch.setattr(onboard_cli, "now", lambda: clock + timedelta(days=3 * 365))
    with fresh_db(pg_template) as db:
        for name, value in db.cli_env().items():
            monkeypatch.setenv(name, value)
        out = tmp_path / "replay-snapshots"
        assert (
            main(["onboard", APAR, "--raw-root", str(raw), "--snapshot-root", str(out)])
            == INCOMPLETE
        )
        assert recorded(db)[1] == first
        manifest = json.loads((raw / "gen-1" / MANIFEST_NAME).read_text())
        assert manifest["as_of"] == AS_OF.isoformat()
        for damage in ("delete", "alter"):
            copy = tmp_path / damage
            shutil.copytree(raw, copy)
            victim = (
                copy
                / "gen-1"
                / next(
                    e["filename"]
                    for e in manifest["entries"]
                    if e["surface"] == "NSE_XBRL_INSTANCE"
                )
            )
            if damage == "delete":
                victim.unlink()
            else:
                victim.write_bytes(victim.read_bytes() + b" ")
            assert (
                main(["onboard", APAR, "--raw-root", str(copy), "--snapshot-root", str(out)])
                == FAILURE
            )
        assert count(db, "onboarding_records") == 1

    for name, value in pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("TIJORI_SESSION_COOKIE", SENTINEL)
    monkeypatch.setattr(
        onboard_cli, "live_transport", lambda: serving_transport(world(APAR), echo=True)
    )
    monkeypatch.setattr(onboard_cli, "now", lambda: clock)
    capsys.readouterr()
    assert cli(APAR, raw, *acquire) == INCOMPLETE
    assert {p.name: p.read_bytes() for p in (raw / "gen-1").iterdir()} == gen1
    assert (raw / "gen-2" / MANIFEST_NAME).is_file()
    logs = capsys.readouterr()
    assert SENTINEL not in logs.out + logs.err
    assert not any(SENTINEL.encode() in p.read_bytes() for p in raw.rglob("*") if p.is_file())
    assert not any(
        SENTINEL.encode() in p.read_bytes()
        for p in (tmp_path / "snapshots").rglob("*")
        if p.is_file()
    )


ENTRY_BREACHES: dict[str, Callable[[dict[str, Any]], object]] = {
    "field_missing": lambda entry: entry.pop("tree"),
    "review_not_approve": lambda entry: entry["review"].update(verdict="REJECT"),
    "other_tree": lambda entry: entry.update(tree={"src": "0" * 40}),
    "other_versions": lambda entry: entry.update(onboarding_versions={"mapping_set": "v4"}),
    "not_current_attempt": lambda entry: entry.update(attempt=2),
    "other_payload": lambda entry: entry.update(holdout_payload_sha256="0" * 64),
}
BREACHES = [
    *("dirty_impl", "entry_uncommitted", "impl_after_freeze", "head_at_implementation"),
    *("impl_changed_then_reverted", "other_checkout", "other_config_root"),
    *("attempt_burned", *ENTRY_BREACHES),
]


@pytest.mark.parametrize("breach", BREACHES)
def test_acquire_refuses_outside_the_freeze_protocol(
    breach: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C5 and D6 step 2: acquisition only on the descriptor commit or a descendant with no IMPL
    change, the entry committed, complete, APPROVEd, pinning the implementation's inputs, tree
    and configuration, and bound to the current unburned attempt and its payload hash; each
    breach refuses (exit 5) before any request, as does an implementation commit since the
    freeze even if reverted, a descriptor outside the running checkout and another config root."""
    repo, implementation, entry = freeze_repo(
        tmp_path, monkeypatch, burned=breach == "attempt_burned"
    )
    if breach in ENTRY_BREACHES:
        ENTRY_BREACHES[breach](entry)
    descriptor = freeze(repo, entry)
    if breach == "dirty_impl":
        (repo / "src" / "impl.py").write_text("x = 2\n")
    elif breach == "entry_uncommitted":
        descriptor.write_text(yaml.safe_dump({"freezes": [entry, {**entry, "attempt": 2}]}))
    elif breach == "impl_after_freeze":
        (repo / "src" / "impl.py").write_text("x = 3\n")
        git(repo, "commit", "-qam", "late")
    elif breach == "impl_changed_then_reverted":
        (repo / "src" / "impl.py").write_text("x = 3\n")
        git(repo, "commit", "-qam", "late")
        git(repo, "revert", "--no-edit", "HEAD")
    elif breach == "head_at_implementation":
        git(repo, "checkout", "-q", implementation)
    elif breach == "other_checkout":
        monkeypatch.setattr(acquisition_authority, "SOURCE_CHECKOUT", REPO_ROOT)
    elif breach == "other_config_root":
        shutil.copytree(REPO_ROOT / "config", tmp_path / "config")
    monkeypatch.setattr(onboard_cli, "live_transport", lambda: _raising)
    args = [
        "onboard",
        APAR,
        "--raw-root",
        str(tmp_path / "raw"),
        "--snapshot-root",
        str(tmp_path / "s"),
        "--acquire",
        "--freeze-descriptor",
        str(descriptor),
        *(("--config-root", str(tmp_path / "config")) if breach == "other_config_root" else ()),
    ]
    assert main(args) == FAILURE
    assert not (tmp_path / "raw").exists()


def _without(surface: str) -> tuple[Any, ...]:
    return tuple(item for item in VENDOR_SURFACES if item.surface != surface)


@pytest.mark.pg
@pytest.mark.retained
def test_a_denied_request_is_recorded_and_replayed_from_the_record(
    cli: Callable[..., int],
    pg_db: PgTestDatabase,
    pg_template: PgTestDatabase,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D4.4: an unregistered vendor surface is a capture-less NOT_AUTHORISED manifest entry with
    no transport call (PARTIAL); replay after the table gains it still serves the recorded
    denial. An unregistered anchor surface aborts the same way: entry kept, no record."""
    repo, _, entry = freeze_repo(tmp_path, monkeypatch)
    acquire = ("--acquire", "--freeze-descriptor", str(freeze(repo, entry)))
    raw, sent = tmp_path / "raw", []
    monkeypatch.setattr(
        onboard_cli, "live_transport", lambda: serving_transport(world(APAR), sent=sent)
    )
    monkeypatch.setattr(onboard_cli, "now", lambda: CLOCK)
    monkeypatch.setattr(onboard_cli, "SURFACES", _without("company_search"))
    assert cli(APAR, raw, *acquire) == INCOMPLETE
    denied = [e for e in _manifest_entries(raw / "gen-1") if e["surface"] == "company_search"]
    assert [(e["outcome"], e["filename"], e["sha256"]) for e in denied] == [
        ("NOT_AUTHORISED", None, None)
    ]
    assert not any("company_search" in url or "/financials/" in url for url in sent)
    tijori = (S.NOT_AUTHORISED.value, R.NOT_AUTHORISED.value)
    assert recorded(pg_db)[1][U.TIJORI] == tijori

    monkeypatch.setattr(onboard_cli, "SURFACES", VENDOR_SURFACES)
    monkeypatch.setattr(onboard_cli, "live_transport", lambda: _raising)
    with fresh_db(pg_template) as db:
        for name, value in db.cli_env().items():
            monkeypatch.setenv(name, value)
        replay = ["onboard", APAR, "--raw-root", str(raw), "--snapshot-root", str(tmp_path / "r")]
        assert main(replay) == INCOMPLETE
        assert recorded(db)[1][U.TIJORI] == tijori

    for name, value in pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    sent.clear()
    monkeypatch.setattr(
        onboard_cli, "live_transport", lambda: serving_transport(world(APAR), sent=sent)
    )
    monkeypatch.setattr(onboard_cli, "SURFACES", _without("NSE_XBRL_INSTANCE"))
    assert cli(APAR, raw, *acquire) == FAILURE
    entries = _manifest_entries(raw / "gen-2")
    assert entries[-1]["surface"] == "NSE_XBRL_INSTANCE"
    assert entries[-1]["outcome"] == "NOT_AUTHORISED"
    assert not any("corporate/xbrl" in url for url in sent)
    assert count(pg_db, "onboarding_records") == 1


@pytest.mark.pg
@pytest.mark.retained
def test_an_off_origin_xbrl_link_is_never_requested(
    cli: Callable[..., int], pg_db: PgTestDatabase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A substituted listing pointing the latest instance at an internal http host: the request
    is refused before the transport (NOT_AUTHORISED entry), the anchor aborts, no record."""
    repo, _, entry = freeze_repo(tmp_path, monkeypatch)
    served, sent = world(APAR), []
    old = b"https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_INDAS_" + JUN.encode()
    edit(served, "integrated-filing", old, b"http://127.0.0.1/synthetic/" + JUN.encode())
    monkeypatch.setattr(onboard_cli, "live_transport", lambda: serving_transport(served, sent=sent))
    monkeypatch.setattr(onboard_cli, "now", lambda: CLOCK)
    raw = tmp_path / "raw"
    assert cli(APAR, raw, "--acquire", "--freeze-descriptor", str(freeze(repo, entry))) == FAILURE
    assert not any("127.0.0.1" in url for url in sent)
    last = _manifest_entries(raw / "gen-1")[-1]
    assert last["url"].startswith("http://127.0.0.1/") and last["outcome"] == "NOT_AUTHORISED"
    assert count(pg_db, "onboarding_records") == 0


XBRL = ("nse-indas-xbrl-consolidated", "NSE_XBRL_INSTANCE")


@pytest.mark.parametrize(
    ("pair", "url", "allowed"),
    [
        (XBRL, "https://nsearchives.nseindia.com/corporate/xbrl/x.xml", True),
        (XBRL, "http://nsearchives.nseindia.com/corporate/xbrl/x.xml", False),
        (XBRL, "https://127.0.0.1/corporate/xbrl/x.xml", False),
        (XBRL, "https://nsearchives.nseindia.com.zz.invalid/x.xml", False),
        (XBRL, "https://zz@nsearchives.nseindia.com/x.xml", False),
        (XBRL, "https://nsearchives.nseindia.com:8443/x.xml", False),
        (XBRL, "https://www.nseindia.com/api/x", False),  # another surface's origin
        (("zz", "UNREGISTERED"), "https://nsearchives.nseindia.com/x.xml", False),
    ],
)
def test_authority_binds_each_surface_to_its_https_origin(
    pair: tuple[str, str], url: str, allowed: bool
) -> None:
    """A surface authorises requests only on its approved https host: no other scheme, host,
    port or userinfo."""
    request = Request(unit=U.XBRL_ENTITY, source_id=pair[0], surface=pair[1], url=url)
    assert authorised(request, VENDOR_SURFACES) is allowed


def test_a_reserved_character_symbol_stays_one_value_in_request_and_printed_command() -> None:
    """SYNTHETIC ``ZZ&A`` (NSE symbols may carry ``&``, e.g. ``M&M``): Screener's search query
    carries it as one ``q`` value, and the printed ``compare run`` command, split as a shell
    does, keeps the entity and an alternate config root as single arguments."""
    query = parse_qs(urlsplit(screener_search_url("ZZ&A")).query)
    assert query == {"q": ["ZZ&A"], "v": ["3"], "fts": ["1"]}
    command = onboard_cli.compare_command(
        "ZZ&A", date(2026, 6, 30), Path("/zz alt/config"), Basis.CONSOLIDATED
    )
    argv = list(shlex.shlex(command, posix=True, punctuation_chars=True))  # ``&`` is a token
    assert argv[argv.index("--entity") + 1] == "ZZ&A"
    assert argv[argv.index("--config-root") + 1] == "/zz alt/config"


@pytest.mark.pg
@pytest.mark.retained
def test_replay_selects_a_generation_or_the_highest_complete_one(
    cli: Callable[..., int], pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """D2: an interrupted gen-2 (no manifest) and a gen-3 whose manifest names another
    generation are not complete, so the default replays gen-1; ``--generation 1`` selects it;
    an explicitly selected incomplete generation fails closed rather than falling back."""
    root = write_root(tmp_path / "raw", world(APAR), APAR)
    (root / "gen-2").mkdir()
    (root / "gen-2" / "00.bin").write_bytes(b"interrupted")
    shutil.copytree(root / "gen-1", root / "gen-3")
    assert cli(APAR, root) == INCOMPLETE
    assert cli(APAR, root, "--generation", "1") == INCOMPLETE
    assert cli(APAR, root, "--generation", "2") == FAILURE
    assert cli(APAR, root, "--generation", "3") == FAILURE
    assert count(pg_db, "onboarding_records") == 2


RELABELS: dict[str, Callable[[dict[str, Any]], object]] = {
    "other_source": lambda entry: entry.update(source_id="tijori"),
    "other_unit": lambda entry: entry.update(unit="EXCHANGE"),
    "unapproved_url": lambda entry: entry.update(  # same path and query, so the same key
        url=entry["url"].replace("https://www.screener.in", "https://zz.invalid")
    ),
    "underived_key": lambda entry: entry.update(request_key=entry["request_key"] + "&zz=1"),
}


@pytest.mark.retained
@pytest.mark.parametrize("relabel", [None, *RELABELS])
def test_replay_serves_an_entry_only_to_the_request_it_records(
    relabel: str | None, tmp_path: Path
) -> None:
    """SYNTHETIC: the Screener page's body and hash intact, but its entry relabelled as another
    source or unit, recorded from an unapproved URL or under a key its URL does not derive: replay
    refuses the approved request instead of publishing the body as its evidence."""
    folder = write_root(tmp_path / "raw", world(APAR), APAR) / "gen-1"
    manifest = json.loads((folder / MANIFEST_NAME).read_text())
    (entry,) = [e for e in manifest["entries"] if e["surface"] == "SCREENER_FINANCIALS"]
    request = Request.model_validate(entry)
    if relabel is not None:
        RELABELS[relabel](entry)
    (folder / MANIFEST_NAME).write_text(json.dumps(manifest))
    with pytest.raises(KeyError) if relabel else nullcontext():
        assert replay_fetch(folder)(request, True).outcome == "OK"


# --- the live transport's boundaries (fakes only) ---------------------------------------------


def _no_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("_screener", "_tijori", "_upstox"):
        monkeypatch.setattr(onboard_cli, f"{name}_credentials_from_env", lambda: None)


class _NseResponse:
    """A fake streamed ``requests`` response."""

    def __init__(self, status: int, body: bytes | Exception = b"") -> None:
        self.status_code = status
        self.raw = self
        self.body = body

    def read(self, amount: int, decode_content: bool) -> bytes:
        assert decode_content
        if isinstance(self.body, Exception):
            raise self.body  # the streamed body read fails after the 200
        return self.body[:amount]

    def __enter__(self) -> _NseResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class _NseSession:
    """A fake primed NSE session: records each GET's options and answers ``reply``."""

    def __init__(self, reply: _NseResponse | Exception) -> None:
        self.reply, self.options = reply, list[dict[str, Any]]()

    def get(self, url: str, **options: Any) -> _NseResponse:
        self.options.append(options)
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


BODY_TIMEOUT = urllib3.exceptions.ReadTimeoutError(None, "/", "read timed out")  # type: ignore[arg-type]
_STALLED = _NseResponse(200, BODY_TIMEOUT)
NSE_LISTING = Request(
    unit=U.EXCHANGE,
    source_id="nse",
    surface="FINANCIAL_RESULTS_LISTING",
    url=listing_url("corporates-financial-results", APAR, "quarterly"),
)


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        (_NseResponse(200, b"[]"), "OK"),
        (_NseResponse(403), "HTTP_403"),
        (_NseResponse(302), "HTTP_302"),
        (requests.ReadTimeout(), "TIMEOUT"),
        (_NseResponse(200, BODY_TIMEOUT), "TIMEOUT"),
        (
            _NseResponse(200, urllib3.exceptions.ProtocolError("connection broken")),
            "TRANSPORT_ERROR",
        ),
    ],
)
def test_the_nse_boundary_keeps_the_http_status_and_follows_no_redirect(
    reply: _NseResponse | Exception, expected: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The installed client's session is called without redirects and streamed: a 403 is
    HTTP_403 (not a transport error), a redirect is its own status, a timeout TIMEOUT — also
    when the streamed body read fails after the 200 — and each failure is a logged entry."""
    session, log = _NseSession(reply), list[Capture]()
    monkeypatch.setattr(onboard_cli, "nse_session", lambda: nullcontext(session))
    _no_credentials(monkeypatch)
    fetch = acquiring_fetch(onboard_cli.live_transport(), lambda: CLOCK, log)
    assert fetch(NSE_LISTING, True).outcome == expected
    assert [item.response.outcome for item in log] == [expected]
    options = {"timeout": onboard_cli.TIMEOUT_SECONDS, "allow_redirects": False, "stream": True}
    assert session.options == [options]


def test_an_nse_session_priming_timeout_is_a_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """The installed client primes its cookies on entry; a connect timeout there is TIMEOUT,
    the same as one during the request, not a transport error."""

    def stalled(*_: object, **__: object) -> None:
        raise requests.ConnectTimeout

    monkeypatch.setattr(requests.Session, "get", stalled)
    _no_credentials(monkeypatch)
    log = list[Capture]()
    fetch = acquiring_fetch(onboard_cli.live_transport(), lambda: CLOCK, log)
    assert fetch(NSE_LISTING, True).outcome == "TIMEOUT"
    assert [item.response.outcome for item in log] == ["TIMEOUT"]


@pytest.mark.pg
@pytest.mark.retained
def test_a_listing_body_timing_out_is_retained_and_exits_cleanly(
    cli: Callable[..., int], pg_db: PgTestDatabase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The NSE listing answers 200 and its streamed body read times out: the acquisition keeps
    the request as a TIMEOUT entry and the command fails with exit 5, no record."""
    repo, _, entry = freeze_repo(tmp_path, monkeypatch)
    monkeypatch.setattr(onboard_cli, "nse_session", lambda: nullcontext(_NseSession(_STALLED)))
    _no_credentials(monkeypatch)
    nse, served = onboard_cli.live_transport(), serving_transport(world(APAR))
    monkeypatch.setattr(
        onboard_cli,
        "live_transport",
        lambda: lambda request: (nse if request.url.startswith(NSE_API) else served)(request),
    )
    monkeypatch.setattr(onboard_cli, "now", lambda: CLOCK)
    raw = tmp_path / "raw"
    assert cli(APAR, raw, "--acquire", "--freeze-descriptor", str(freeze(repo, entry))) == FAILURE
    last = _manifest_entries(raw / "gen-1")[-1]
    assert last["url"].startswith(NSE_API) and last["outcome"] == "TIMEOUT"
    assert count(pg_db, "onboarding_records") == 0


def test_the_nse_boundary_refuses_an_oversized_body(monkeypatch: pytest.MonkeyPatch) -> None:
    """A body over the cap is refused, never truncated."""
    monkeypatch.setattr(onboard_cli, "MAX_BODY_BYTES", 4)
    session = _NseSession(_NseResponse(200, b"12345"))
    monkeypatch.setattr(onboard_cli, "nse_session", lambda: nullcontext(session))
    _no_credentials(monkeypatch)
    with pytest.raises(ResponseTooLargeError):
        onboard_cli.live_transport()(NSE_LISTING)


class _Https(urllib.request.HTTPSHandler):
    """A fake final HTTPS boundary: records each request and answers ``status``."""

    def __init__(self, status: int, location: str | None) -> None:
        super().__init__()
        self.status, self.location, self.seen = status, location, list[urllib.request.Request]()

    def https_open(self, req: urllib.request.Request) -> urllib.response.addinfourl:
        self.seen.append(req)
        headers = email.message.Message()
        if self.location:
            headers["Location"] = self.location
        response = urllib.response.addinfourl(
            io.BytesIO(b'"<li></li>"'), headers, req.full_url, self.status
        )
        response.msg = "synthetic"
        return response


BSE_SEARCH = Request(
    unit=U.EXCHANGE,
    source_id="bse",
    surface="PEER_SMART_SEARCH",
    url="https://api.bseindia.com/BseIndiaAPI/api/PeerSmartSearch/w?Type=SS&text=INE372A01015",
)


@pytest.mark.parametrize(("status", "location"), [(200, None), (302, "http://127.0.0.1/synthetic")])
def test_bse_peer_search_sends_the_probed_headers_and_follows_no_redirect(
    status: int, location: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Task 0b §7: PeerSmartSearch carries the browser Referer, Origin and Accept headers and
    no cookie; a redirect (here to an internal http host) is returned, not followed."""
    fake = _Https(status, location)
    real = urllib.request.build_opener
    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: real(*handlers, fake))
    _no_credentials(monkeypatch)
    assert onboard_cli.live_transport()(BSE_SEARCH)[0] == status
    (sent,) = fake.seen
    headers = {name: sent.get_header(name) for name in ("Referer", "Origin", "Accept", "Cookie")}
    assert headers == {
        "Referer": "https://www.bseindia.com/",
        "Origin": "https://www.bseindia.com",
        "Accept": "application/json, text/plain, */*",
        "Cookie": None,
    }


def test_live_transport_names_the_project_to_vendor_sites(monkeypatch):
    """Tijori blocks a default client and the site rules forbid a browser UA: vendors get ours."""
    sent: list[urllib.request.Request] = []

    class Opener:
        def open(self, request: urllib.request.Request, timeout: float) -> Any:
            sent.append(request)
            raise urllib.error.HTTPError(request.full_url, 404, "", email.message.Message(), None)

    monkeypatch.setattr(onboard_cli.urllib.request, "build_opener", lambda *_: Opener())
    send = onboard_cli.live_transport()
    for source in ("tijori", "screener-subscriber"):
        send(
            Request(unit=VerificationUnit.EXCHANGE, source_id=source, surface="s", url="https://x/")
        )
    assert [r.get_header("User-agent") for r in sent] == ["EquityOS Research"] * 2
