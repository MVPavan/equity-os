"""The ``onboard`` command: discover, verify and record one NSE symbol (plan D6 D4).

    onboard <SYMBOL> --raw-root <dir> --snapshot-root <dir> [--config-root config]
        [--acquire --freeze-descriptor <path>]

Replay (the default) reads the latest ``gen-<n>`` discovery generation under ``--raw-root`` and
never opens a socket. ``--acquire`` writes the next generation through the live transport, and
only on a checkout that satisfies the freeze protocol (C5): the descriptor's current entry
committed at ``HEAD``, its implementation commit an ancestor of the first commit holding the
entry, and no implementation path changed since or uncommitted. Exit: ``ONBOARDED`` 0,
``PARTIAL`` 4, anything else (including an abort) 5. Failures never echo a transport message,
so a credential a server reflects lands nowhere.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
import structlog
import yaml

from fundamentals.api.env_credentials import (
    _screener_credentials_from_env,
    _tijori_credentials_from_env,
    _upstox_credentials_from_env,
)
from fundamentals.canon.dictionary import load_dictionary
from fundamentals.compare.run_config import DICTIONARY_DIR, MAPPINGS_DIR
from fundamentals.compare.run_models import RunExitStatus
from fundamentals.contracts.onboarding import ONBOARDING_VERSIONS, OnboardingOutcome
from fundamentals.contracts.snapshot import SnapshotError
from fundamentals.contracts.source_catalog import UPSTOX_STATEMENT, VENDOR_SURFACES
from fundamentals.entity import discovery
from fundamentals.entity.discovery import (
    OnboardingAbortError,
    Request,
    Send,
    acquiring_fetch,
    discover,
    record,
    store_captures,
    write_generation,
)
from fundamentals.evidence.mapping import load_mapping_set
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.ingest.http_session import NoRedirectHandler, read_bounded
from fundamentals.ingest.nse_filings import NSE_API
from fundamentals.pg.pool import DatabaseUnavailableError, open_pool
from fundamentals.pg.settings import PgRole, PgSettings
from fundamentals.store.snapshot_store import MAX_BODY_BYTES, SnapshotStore

ONBOARD_COMMAND = "onboard"
DEFAULT_CONFIG_ROOT = "config"
ACQUISITION_NAME = "acquisition.json"
GENERATION_PREFIX = "gen-"
IMPLEMENTATION_PATHS = ("src", "config", "migrations", "scripts", "pyproject.toml", "uv.lock")
TIMEOUT_SECONDS = 30
_FREEZES = "freezes"
_IMPLEMENTATION = "implementation_commit"
_AGENT = "Mozilla/5.0 (equity-os onboarding)"
_SESSION_COOKIE = "sessionid={value}"
_HELP = "discover, verify and record one NSE symbol (D6)"
_NEEDS_DESCRIPTOR = "--acquire needs --freeze-descriptor"
_UNFROZEN = "the checkout does not satisfy the freeze protocol: {why}"
_SEVERITY_HIGH = "HIGH"
_EXIT = {
    OnboardingOutcome.ONBOARDED: RunExitStatus.SUCCESS,
    OnboardingOutcome.PARTIAL: RunExitStatus.INCOMPLETE,
}
_FAILURES = (
    OnboardingAbortError,
    OSError,
    LookupError,
    ValueError,
    subprocess.SubprocessError,
    psycopg.Error,
    DatabaseUnavailableError,
    SnapshotError,
)

# Seams the tests replace: the authority table, the live transport, the clock, the replay.
SURFACES = VENDOR_SURFACES
replay_fetch = discovery.replay_fetch


def now() -> datetime:
    """The acquisition clock."""
    return datetime.now(UTC)


def live_transport() -> Send:
    """``send(request) -> (status, body)`` over HTTPS with each source's own credential;
    redirects are refused (a login bounce is a failure, not a page)."""
    screener, tijori, upstox = (
        _screener_credentials_from_env(),
        _tijori_credentials_from_env(),
        _upstox_credentials_from_env(),
    )
    cookies = {
        "screener-subscriber": screener and screener.session_cookie,
        "tijori": tijori and tijori.session_cookie,
    }
    opener = urllib.request.build_opener(NoRedirectHandler())

    def send(request: Request) -> tuple[int, bytes]:
        if request.url.startswith(NSE_API):  # the NSE API needs the client's primed session
            from nse import NSE  # type: ignore[import-untyped]

            with (
                tempfile.TemporaryDirectory() as folder,
                NSE(folder, timeout=TIMEOUT_SECONDS) as client,
            ):
                response = client._req(request.url)
                return int(response.status_code), bytes(response.content)
        headers = {"User-Agent": _AGENT}
        cookie = cookies.get(request.source_id)
        if cookie:
            headers["Cookie"] = _SESSION_COOKIE.format(value=cookie.get_secret_value())
        if (request.source_id, request.surface) == UPSTOX_STATEMENT and upstox:
            headers["Authorization"] = f"Bearer {upstox.access_token.get_secret_value()}"
        try:
            with opener.open(
                urllib.request.Request(request.url, headers=headers), timeout=TIMEOUT_SECONDS
            ) as response:
                return int(response.status), read_bounded(response, MAX_BODY_BYTES)
        except urllib.error.HTTPError as error:
            return int(error.code), b""

    return send


def add_onboard_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register ``onboard``."""
    parser = subparsers.add_parser(ONBOARD_COMMAND, help=_HELP)
    parser.add_argument("symbol")
    parser.add_argument("--raw-root", required=True, type=Path)
    parser.add_argument("--snapshot-root", required=True, type=Path)
    parser.add_argument("--config-root", type=Path, default=Path(DEFAULT_CONFIG_ROOT))
    parser.add_argument("--acquire", action="store_true")
    parser.add_argument("--freeze-descriptor", type=Path)


def dispatch_onboard_command(args: argparse.Namespace) -> int | None:
    """Run ``onboard``, or return ``None`` for any other command."""
    if args.command != ONBOARD_COMMAND:
        return None
    try:
        return _onboard(args)
    except _FAILURES as error:
        structlog.get_logger().error("onboard_failed", error=type(error).__name__)
        return RunExitStatus.FAILURE


def _onboard(args: argparse.Namespace) -> int:
    """Acquire or replay, discover, store the captures and write the record."""
    acquisition = _frozen(args.freeze_descriptor) if args.acquire else None
    dictionary = load_dictionary(args.config_root / DICTIONARY_DIR, ONBOARDING_VERSIONS.dictionary)
    mapping_set = load_mapping_set(
        args.config_root / MAPPINGS_DIR, ONBOARDING_VERSIONS.mapping_set, dictionary=dictionary
    )
    root: Path = args.raw_root
    taken = sorted(
        int(path.name.removeprefix(GENERATION_PREFIX))
        for path in root.glob(f"{GENERATION_PREFIX}*")
    )
    log: list[discovery.Capture] = []
    if acquisition is None:
        fetch = replay_fetch(root / f"{GENERATION_PREFIX}{taken[-1]}")
    else:
        generation = (taken[-1] if taken else 0) + 1
        fetch = acquiring_fetch(live_transport(), now, log)
    with open_pool(PgSettings(), PgRole.RUNTIME) as pool:
        try:
            with pool.connection() as conn:
                found = discover(args.symbol, fetch, conn, SURFACES, mapping_set)
        finally:
            if acquisition is not None and log:
                folder = root / f"{GENERATION_PREFIX}{generation}"
                authorization = f"freeze {acquisition['descriptor_commit']}"
                write_generation(folder, args.symbol, authorization, generation, log)
                (folder / ACQUISITION_NAME).write_text(json.dumps(acquisition, indent=1))
        store = SnapshotStore(args.snapshot_root)
        with store.prepare_ordinary_output():
            captures = store_captures(store, EvidenceRepository(pool), found.captures)
        with pool.connection() as conn:
            result, reason = record(conn, found, captures)
    sys.stdout.write(f"onboard {args.symbol}: {result.value}")
    if result is OnboardingOutcome.IDENTITY_CONFLICT:
        sys.stdout.write(f" severity {_SEVERITY_HIGH}")
    sys.stdout.write(f" {reason or ''}\n")
    for unit, (state, why) in found.states.items():
        sys.stdout.write(f"  {unit.value}: {state.value} {why or ''}\n")
    return _EXIT.get(result, RunExitStatus.FAILURE)


def _frozen(descriptor: Path | None) -> dict[str, str]:
    """C5: the freeze protocol's checks, and what the acquisition records of them."""
    if descriptor is None:
        raise ValueError(_NEEDS_DESCRIPTOR)
    repo = Path(_git(descriptor.resolve().parent, "rev-parse", "--show-toplevel"))
    path = str(descriptor.resolve().relative_to(repo.resolve()))
    if _git(repo, "status", "--porcelain", "--", *IMPLEMENTATION_PATHS, path):
        raise ValueError(_UNFROZEN.format(why="uncommitted changes"))
    entry = yaml.safe_load(descriptor.read_text())[_FREEZES][-1]
    head = _git(repo, "rev-parse", "HEAD")
    commits = _git(repo, "log", "--reverse", "--format=%H", "--", path).split()
    holding = [commit for commit in commits if entry in _freezes(repo, commit, path)]
    if not holding or entry not in _freezes(repo, head, path):
        raise ValueError(_UNFROZEN.format(why="entry not committed at HEAD"))
    implementation = str(entry[_IMPLEMENTATION])
    _git(repo, "merge-base", "--is-ancestor", implementation, holding[0])
    _git(repo, "diff", "--quiet", implementation, head, "--", *IMPLEMENTATION_PATHS)
    return {
        "acquisition_head": head,
        "descriptor_commit": holding[0],
        "implementation_commit": implementation,
        "freeze_descriptor": path,
    }


def _freezes(repo: Path, commit: str, path: str) -> list[Any]:
    """The descriptor's entries at ``commit``."""
    return list(yaml.safe_load(_git(repo, "show", f"{commit}:{path}"))[_FREEZES])


def _git(repo: Path, *args: str) -> str:
    """One git command's stdout; a non-zero exit raises."""
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()
