"""FIVE-1 Task 2: replayable entity-bound fetches and the two generation modes.

SYNTHETIC throughout: the ZZFAKE symbol, its URLs, bodies and checkout are made here; no socket
is opened and no real protected data exists. An entity generation (``compare fallback``) has no
NSE master and ``as_of: null``; onboarding's keeps exactly one master and its retrieval date.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from equity_os.companies.onboarding.discovery import (
    MANIFEST_NAME,
    Capture,
    Request,
    Response,
    replay_fetch,
    write_generation,
)
from equity_os.contracts.companies.onboarding import VerificationUnit
from equity_os.contracts.sourcing.source_catalog import NSE_MASTER
from equity_os.interface.commands.companies import acquisition_authority
from equity_os.interface.commands.companies.acquisition_authority import entity_fetch
from equity_os.interface.commands.extraction import evidence_cli
from equity_os.interface.commands.verification import compare_cli
from equity_os.interface.entry.cli import main

BASE = "https://www.nseindia.com/api/zzfake"
LISTINGS = [
    Request(unit=VerificationUnit.EXCHANGE, source_id="nse", surface="LISTING", url=f"{BASE}?a=1"),
    Request(unit=VerificationUnit.EXCHANGE, source_id="nse", surface="LISTING", url=f"{BASE}?b=2"),
]
MASTER = Request(
    unit=VerificationUnit.EXCHANGE, source_id=NSE_MASTER[0], surface=NSE_MASTER[1], url=BASE
)
SERVED = {LISTINGS[0].url: (200, b"ZZFAKE listing"), LISTINGS[1].url: (404, b"")}
WHEN = datetime(2026, 11, 6, 4, 0, tzinfo=UTC)  # 2026-11-06 in Asia/Kolkata


def _send(request: Request) -> tuple[int, bytes]:
    """The SYNTHETIC server."""
    return SERVED[request.url]


@pytest.fixture(autouse=True)
def committed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The running checkout's implementation paths read as committed (no git repo is needed)."""
    monkeypatch.setattr(acquisition_authority, "uncommitted", lambda: "")


def _no_socket() -> Callable[[Request], tuple[int, bytes]]:
    """A transport that must never be built on replay."""
    raise AssertionError("replay opened a transport")


def _acquire(root: Path) -> list[Response]:
    """One acquisition of both listings through ``entity_fetch``, written afterwards."""
    fetch, write = entity_fetch(root, None, "1", "SYNTHETIC fallback", lambda: _send)
    responses = [fetch(request, True) for request in LISTINGS]
    write()
    return responses


def _generation(folder: Path, *requests: Request, entity: bool = False) -> dict[str, object]:
    """Write a generation of ``requests`` answered OK; its manifest as JSON."""
    log = [
        Capture(request=r, response=Response(outcome="OK", body=b"x", retrieved_at=WHEN))
        for r in requests
    ]
    write_generation(folder, "ZZFAKE", "SYNTHETIC", 1, log, entity=entity)
    manifest: dict[str, object] = json.loads((folder / MANIFEST_NAME).read_text())
    return manifest


def test_entity_generation_replays_what_was_acquired(tmp_path: Path) -> None:
    """Acquire writes the next generation (no master, ``as_of: null``); replay of it serves the
    same responses without a transport, a later acquire takes the next number, and an altered
    body refuses the replay."""
    acquired = _acquire(tmp_path)
    manifest = json.loads((tmp_path / "gen-1" / MANIFEST_NAME).read_text())
    assert (manifest["generation"], manifest["as_of"]) == (1, None)
    fetch, write = entity_fetch(tmp_path, 1, "1", "SYNTHETIC fallback", _no_socket)
    assert [fetch(request, True) for request in LISTINGS] == acquired
    write()
    assert sorted(path.name for path in tmp_path.iterdir()) == ["gen-1"]
    _acquire(tmp_path)
    assert sorted(path.name for path in tmp_path.iterdir()) == ["gen-1", "gen-2"]
    (tmp_path / "gen-1" / "00.bin").write_bytes(b"ZZFAKE listing, edited")
    with pytest.raises(ValueError, match="00.bin altered"):
        entity_fetch(tmp_path, 1, "1", "SYNTHETIC fallback", _no_socket)


def test_nothing_fetched_writes_no_generation(tmp_path: Path) -> None:
    """A fallback that fetches nothing leaves the raw root as it was."""
    _, write = entity_fetch(tmp_path, None, "1", "SYNTHETIC fallback", lambda: _send)
    write()
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    ("edit", "entity"),
    [
        (lambda m: m.update(as_of=None), False),  # onboarding: null as_of beside a master
        (lambda m: m.update(entries=[]), False),  # onboarding: no master
        (lambda m: m.update(as_of="2026-11-07"), False),  # onboarding: not the master's date
        (lambda m: None, True),  # onboarding's generation read in entity mode
    ],
    ids=["null-as-of", "no-master", "wrong-date", "master-in-entity-mode"],
)
def test_onboarding_replay_keeps_its_master_rule(
    tmp_path: Path, edit: Callable[[dict[str, object]], None], entity: bool
) -> None:
    """Onboarding's replay needs one master and its retrieval date; entity mode refuses one."""
    manifest = _generation(tmp_path / "gen", MASTER)
    assert manifest["as_of"] == "2026-11-06"
    replay_fetch(tmp_path / "gen")
    edit(manifest)
    (tmp_path / "gen" / MANIFEST_NAME).write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="as_of"):
        replay_fetch(tmp_path / "gen", entity=entity)


@pytest.mark.parametrize(
    ("requests", "entity"),
    [((), False), ((MASTER, MASTER), False), ((MASTER,), True)],
    ids=["no-master", "two-masters", "master-in-entity-mode"],
)
def test_a_generation_breaking_its_master_rule_is_never_written(
    tmp_path: Path, requests: tuple[Request, ...], entity: bool
) -> None:
    """The replay rule binds the write: onboarding's generation holds exactly one master, an
    entity one none; any other log refuses before the folder exists."""
    with pytest.raises(ValueError, match="NSE master captures"):
        _generation(tmp_path / "gen", *LISTINGS, *requests, entity=entity)
    assert not (tmp_path / "gen").exists()


def test_entity_generation_replays_only_in_entity_mode(tmp_path: Path) -> None:
    """An entity generation (no master, ``as_of: null``) is not an onboarding generation."""
    _generation(tmp_path / "gen", *LISTINGS, entity=True)
    replay_fetch(tmp_path / "gen", entity=True)
    with pytest.raises(ValueError, match="as_of"):
        replay_fetch(tmp_path / "gen")


@pytest.fixture
def checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A SYNTHETIC checkout whose protected roots hold nothing."""
    repo = tmp_path / "checkout"
    for held in acquisition_authority.PROTECTED_ROOTS:
        (repo / held).mkdir(parents=True)
    monkeypatch.setattr(acquisition_authority, "SOURCE_CHECKOUT", repo)
    return repo


@pytest.mark.parametrize("generation", [None, 1])
@pytest.mark.parametrize("linked", [False, True])
def test_a_protected_raw_root_refuses_before_any_access(
    checkout: Path, tmp_path: Path, generation: int | None, linked: bool
) -> None:
    """A raw root under, or linked into, a protected root refuses on acquire and replay before
    the transport is built or the root is read or written."""
    root = checkout / "data/raw/onboarding/ZZFAKE"
    if linked:
        root = tmp_path / "link"
        root.symlink_to(checkout / "data/holdout", target_is_directory=True)
    with pytest.raises(ValueError, match="protected root"):
        entity_fetch(root, generation, "1", "SYNTHETIC fallback", _no_socket)
    assert not any((checkout / "data").rglob("*.*"))


@pytest.mark.parametrize("generation", [[], ["--generation", "1"]])
def test_compare_fallback_refuses_a_protected_snapshot_root(
    checkout: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, generation: list[str]
) -> None:
    """``compare fallback`` refuses a protected snapshot root, on acquire and replay, before it
    opens the database."""
    monkeypatch.setattr(compare_cli, "open_pool", _no_socket)
    argv = [
        *("compare", "fallback", "--run", "1", "--store-id", "zz"),
        *("--snapshot-root", str(checkout / "data/holdout/snapshots")),
        *("--raw-root", str(tmp_path / "raw"), *generation),
    ]
    assert main(argv) == 5
    assert not (tmp_path / "raw").exists()


@pytest.mark.parametrize("protected", ["snapshot", "raw"])
def test_evidence_acquire_refuses_a_protected_root(
    checkout: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, protected: str
) -> None:
    """FIVE-1 Task 3: ``evidence acquire`` refuses a protected snapshot or raw root before it
    opens the database or builds a transport."""
    monkeypatch.setattr(evidence_cli, "open_pool", _no_socket)
    monkeypatch.setattr(evidence_cli, "live_transport", _no_socket)
    roots = {"snapshot": tmp_path / "snapshots", "raw": tmp_path / "raw"}
    roots[protected] = checkout / "data/holdout" / protected
    argv = [
        *("evidence", "acquire", "--entity", "ZZFAKE", "--basis", "consolidated"),
        *("--period-end", "2025-09-30", "--mapping-set", "v9", "--dictionary", "v2"),
        *("--snapshot-root", str(roots["snapshot"]), "--raw-root", str(roots["raw"])),
    ]
    assert main(argv) == 2
    assert not any((checkout / "data").rglob("*.*"))


@pytest.mark.parametrize("generation", [None, 1])
def test_an_uncommitted_implementation_refuses_acquire_and_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, generation: int | None
) -> None:
    """FIVE-1 closing review 7: entity acquisition and replay run only on a committed
    implementation, as the sanctioned acquisition does."""
    monkeypatch.setattr(acquisition_authority, "uncommitted", lambda: " M equity_os/zz.py")
    with pytest.raises(ValueError, match="uncommitted"):
        entity_fetch(tmp_path, generation, "1", "SYNTHETIC fallback", _no_socket)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    ("generation", "issuer", "authorization"),
    [(7, "1", "SYNTHETIC fallback"), (1, "2", "SYNTHETIC fallback"), (1, "1", "SYNTHETIC other")],
    ids=["generation", "issuer", "authorization"],
)
def test_replay_needs_the_requested_binding(
    tmp_path: Path, generation: int, issuer: str, authorization: str
) -> None:
    """FIVE-1 closing review 6: a replayed manifest must declare the requested generation,
    issuer and authorization; here gen-7 holds a manifest declaring generation 1."""
    _acquire(tmp_path)
    (tmp_path / "gen-1").rename(tmp_path / f"gen-{generation}")
    with pytest.raises(ValueError, match="does not bind"):
        entity_fetch(tmp_path, generation, issuer, authorization, _no_socket)


def _linked_generation(checkout: Path, root: Path) -> None:
    """``gen-1`` under ``root`` links to a SYNTHETIC generation under a protected root."""
    _acquire(root)
    held = checkout / "data/holdout/gen-1"
    (root / "gen-1").rename(held)
    (root / "gen-1").symlink_to(held, target_is_directory=True)


def _escaping_name(checkout: Path, root: Path) -> None:
    """A manifest naming a body outside its generation, with the right hash."""
    del checkout
    _acquire(root)
    path = root / "gen-1" / MANIFEST_NAME
    manifest = json.loads(path.read_text())
    (root / "out.bin").write_bytes((root / "gen-1" / "00.bin").read_bytes())
    manifest["entries"][0]["filename"] = "../out.bin"
    path.write_text(json.dumps(manifest))


def _linked_body(checkout: Path, root: Path) -> None:
    """A body linked to a file under a protected root, with the right hash."""
    _acquire(root)
    held = checkout / "data/holdout/00.bin"
    held.write_bytes((root / "gen-1" / "00.bin").read_bytes())
    (root / "gen-1" / "00.bin").unlink()
    (root / "gen-1" / "00.bin").symlink_to(held)


@pytest.mark.parametrize("breach", [_linked_generation, _escaping_name, _linked_body])
def test_replay_stays_inside_an_ordinary_generation(
    checkout: Path, tmp_path: Path, breach: Callable[[Path, Path], None]
) -> None:
    """FIVE-1 closing review 2: an ordinary raw root whose ``gen-N`` links into a protected
    root, or whose manifest names a body outside the generation or linked out of it, refuses
    before the manifest or that body is read."""
    root = tmp_path / "raw"
    breach(checkout, root)
    with pytest.raises(ValueError, match="protected root|outside"):
        entity_fetch(root, 1, "1", "SYNTHETIC fallback", _no_socket)
