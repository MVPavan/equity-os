"""FIVE-1 Task 1: the sanctioned acquisition route — a committed, Sol-approved symbol listing in
the checkout's sanctions directory authorises ``onboard --acquire`` in place of a freeze.

Only transports are faked; sanction repos are ``tmp_path`` git repos made the running checkout,
with a SYNTHETIC sentinel at the held-out record's path.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from onboarding_support import (
    APAR,
    FAILURE,
    INCOMPLETE,
    REVIEW,
    cli,
    count,
    fresh_db,
    git,
    recorded,
    serving_transport,
    world,
    yaml_sha,
)
from pg_support import PgTestDatabase
from retained_support import REPO_ROOT
from test_onboarding_acquisition import CLOCK, _raising

from equity_os.companies.onboarding.discovery import MANIFEST_NAME
from equity_os.interface.commands.companies import acquisition_authority, onboard_cli
from equity_os.interface.entry.cli import main

__all__ = ["cli"]

SANCTIONED = "ZZSANCT"
SANCTION = "zz.yaml"


def _sanction_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    symbols: tuple[str, ...] = (SANCTIONED,),
    verdict: str = "APPROVE",
    folder: Path = acquisition_authority.SANCTIONS,
    commit: bool = True,
) -> tuple[Path, Path]:
    """A git repo, made the running checkout, whose ``config`` links each of the repository's
    own config folders and holds a sanction stamped over its payload; a SYNTHETIC sentinel stands
    at the held-out record's path. Returns the repo and the sanction."""
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    for child in (REPO_ROOT / "config").iterdir():
        if child.name != "acquisition":
            (repo / "config" / child.name).symlink_to(child)
    holdout = repo / acquisition_authority.HOLDOUT_RECORD
    holdout.parent.mkdir(parents=True)
    holdout.write_text("SYNTHETIC sentinel: the sanction route never opens this\n")
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "t@example.invalid")
    git(repo, "config", "user.name", "t")
    git(repo, "add", "config", acquisition_authority.HOLDOUT_RECORD)
    git(repo, "commit", "-qm", "plan")
    plan = git(repo, "rev-parse", "HEAD")
    payload = {"symbols": list(symbols), "purpose": "zz", "plan": "zz.md", "plan_commit": plan}
    review = {**REVIEW, "verdict": verdict, "review_commit": plan}
    path = repo / folder / SANCTION
    path.parent.mkdir(parents=True)
    path.write_text(
        yaml.safe_dump({**payload, "review": {**review, "payload_sha256": yaml_sha(payload)}})
    )
    if commit:
        git(repo, "add", str(path))
        git(repo, "commit", "-qm", "sanction")
    monkeypatch.setattr(acquisition_authority, "SOURCE_CHECKOUT", repo)
    return repo, path


def _copied_stamp(repo: Path, path: Path) -> Path:
    sanction = yaml.safe_load(path.read_text())
    sanction["symbols"].append("ZZMORE")
    path.write_text(yaml.safe_dump(sanction))
    git(repo, "commit", "-qam", "more symbols, old stamp")
    return path


def _linked_out(repo: Path, path: Path) -> Path:
    link = repo / acquisition_authority.SANCTIONS / SANCTION
    link.parent.mkdir(parents=True)
    link.symlink_to(path)
    git(repo, "add", str(link))
    git(repo, "commit", "-qm", "link")
    return link


def _restamped(symbols: Any) -> Callable[[Path, Path], Path]:
    """A committed sanction whose ``symbols`` is ``symbols``, stamped over its own payload."""

    def damage(repo: Path, path: Path) -> Path:
        sanction = yaml.safe_load(path.read_text())
        payload = {**sanction, "symbols": symbols}
        del payload["review"]
        review = {**sanction["review"], "payload_sha256": yaml_sha(payload)}
        path.write_text(yaml.safe_dump({**payload, "review": review}))
        git(repo, "commit", "-qam", "malformed symbols, own stamp")
        return path

    return damage


SANCTION_BREACHES: dict[str, tuple[dict[str, Any], Callable[[Path, Path], Path]]] = {
    "unlisted": ({"symbols": ("ZZOTHER",)}, lambda repo, path: path),
    "not_approve": ({"verdict": "REJECT"}, lambda repo, path: path),
    "copied_stamp": ({}, _copied_stamp),
    "uncommitted": ({"commit": False}, lambda repo, path: path),
    "edited": ({}, lambda repo, path: path.write_text(path.read_text() + "#\n") and path),
    "outside_sanctions": ({"folder": Path("config/elsewhere")}, lambda repo, path: path),
    "linked_outside": ({"folder": Path("config/elsewhere")}, _linked_out),
    "other_config_root": ({}, lambda repo, path: path),
    "scalar_symbols": ({}, _restamped(SANCTIONED + "X")),  # substring membership would pass
    "mapping_symbols": ({}, _restamped({SANCTIONED: "x"})),  # key membership would pass
    "empty_symbol": ({}, _restamped([SANCTIONED, ""])),
}


@pytest.mark.parametrize("breach", SANCTION_BREACHES)
def test_sanctioned_refuses_anything_but_a_committed_approved_listing(
    breach: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The sanction must sit committed and unchanged in the checkout's sanctions directory (a
    symlink out of it counts as outside), stamped APPROVE over its own payload, and list the
    symbol exactly in a list of nonempty strings; a stamp copied over a changed symbol list fails
    its digest, and a correctly stamped scalar or mapping ``symbols`` is malformed."""
    options, damage = SANCTION_BREACHES[breach]
    repo, path = _sanction_repo(tmp_path, monkeypatch, **options)
    path = damage(repo, path)
    config = tmp_path / "config" if breach == "other_config_root" else repo / "config"
    with pytest.raises(ValueError, match="does not authorise"):
        acquisition_authority.sanctioned(path, config, SANCTIONED)


@pytest.mark.parametrize("breach", ["both_flags", "no_flag", "raw_protected", "snapshot_linked"])
def test_sanctioned_acquire_refuses_a_second_authority_or_a_protected_root(
    breach: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--acquire`` takes exactly one of ``--sanction`` and ``--freeze-descriptor``, and a
    sanctioned acquisition refuses a root under, or linked into, a protected root (SYNTHETIC
    checkout, no real protected data); each refuses (exit 5) before any request or write."""
    repo, path = _sanction_repo(tmp_path, monkeypatch)
    raw, snapshots = tmp_path / "raw", tmp_path / "s"
    if breach == "raw_protected":
        raw = repo / "data" / "holdout" / "raw"
    elif breach == "snapshot_linked":
        (repo / "data" / "raw" / "onboarding").mkdir(parents=True)
        (tmp_path / "link").symlink_to(repo / "data" / "raw" / "onboarding")
        snapshots = tmp_path / "link" / "s"
    flags = {
        "both_flags": ("--sanction", str(path), "--freeze-descriptor", str(path)),
        "no_flag": (),
    }.get(breach, ("--sanction", str(path)))
    monkeypatch.setattr(onboard_cli, "live_transport", lambda: _raising)
    args = ["onboard", SANCTIONED, "--raw-root", str(raw), "--snapshot-root", str(snapshots)]
    assert main([*args, "--config-root", str(repo / "config"), "--acquire", *flags]) == FAILURE
    assert not raw.exists() and not snapshots.exists()


@pytest.mark.pg
def test_sanctioned_acquire_then_replay_is_identical(
    cli: Callable[..., int], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A sanctioned acquisition (every SYNTHETIC request answered 404, so discovery aborts)
    records the sanction, its digest and ``HEAD`` with no ``attempt``, and never opens the
    held-out record; replay opens no transport and gives the same exit over unchanged bytes."""
    repo, path = _sanction_repo(tmp_path, monkeypatch)
    raw, config = tmp_path / "raw", ("--config-root", str(repo / "config"))
    opened: list[str] = []
    real_run, real_open = acquisition_authority.subprocess.run, Path.open

    def run(argv: Any, **kwargs: Any) -> Any:
        opened.append(" ".join(map(str, argv)))
        return real_run(argv, **kwargs)

    def open_(self: Path, *args: Any, **kwargs: Any) -> Any:
        opened.append(str(self))
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(acquisition_authority.subprocess, "run", run)
    monkeypatch.setattr(Path, "open", open_)
    monkeypatch.setattr(onboard_cli, "live_transport", lambda: lambda request: (404, b""))
    monkeypatch.setattr(onboard_cli, "now", lambda: CLOCK)
    sanction = ("--acquire", "--sanction", str(path))
    assert cli(SANCTIONED, raw, *config, *sanction) == FAILURE
    assert opened and not any(acquisition_authority.HOLDOUT_RECORD in item for item in opened)
    head, relative = git(repo, "rev-parse", "HEAD"), str(path.relative_to(repo))
    acquisition = json.loads((raw / "gen-1" / "acquisition.json").read_text())
    assert acquisition == {
        "generation": 1,
        "sanction": relative,
        "sanction_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "acquisition_head": head,
        "argv": [
            *("onboard", SANCTIONED, "--raw-root", str(raw), "--snapshot-root"),
            *(str(tmp_path / "snapshots"), *config, *sanction),
        ],
        "discovery_manifest_sha256": hashlib.sha256(
            (raw / "gen-1" / MANIFEST_NAME).read_bytes()
        ).hexdigest(),
        "retrieval_manifest_sha256": None,
    }
    manifest = json.loads((raw / "gen-1" / MANIFEST_NAME).read_text())
    assert manifest["authorization"] == f"sanction {relative}@{head}"
    gen1 = {p.name: p.read_bytes() for p in (raw / "gen-1").iterdir()}
    monkeypatch.setattr(onboard_cli, "live_transport", lambda: _raising)
    assert cli(SANCTIONED, raw, *config) == FAILURE
    assert {p.name: p.read_bytes() for p in (raw / "gen-1").iterdir()} == gen1
    assert sorted(p.name for p in raw.iterdir()) == ["gen-1"]


@pytest.mark.pg
@pytest.mark.retained
def test_a_sanctioned_acquisition_onboards_and_replays_its_ingest(
    cli: Callable[..., int],
    pg_db: PgTestDatabase,
    pg_template: PgTestDatabase,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A sanctioned acquisition of a listed symbol whose fixture world answers (only transports
    faked) onboards and ingests its evidence; replaying that generation in a fresh database with
    transports raising records the same outcome, unit states and stored evidence."""
    repo, path = _sanction_repo(tmp_path, monkeypatch, symbols=(APAR,))
    raw, config = tmp_path / "raw", ("--config-root", str(repo / "config"))
    monkeypatch.setattr(onboard_cli, "live_transport", lambda: serving_transport(world(APAR)))
    monkeypatch.setattr(onboard_cli, "now", lambda: CLOCK)
    assert cli(APAR, raw, *config, "--acquire", "--sanction", str(path)) == INCOMPLETE
    tables = ("onboarding_records", "filing_packages", "occurrences", "interpretations")
    acquired, stored = recorded(pg_db), [count(pg_db, table) for table in tables]
    assert all(stored)
    monkeypatch.setattr(onboard_cli, "live_transport", lambda: _raising)
    with fresh_db(pg_template) as db:
        for name, value in db.cli_env().items():
            monkeypatch.setenv(name, value)
        out = ("--snapshot-root", str(tmp_path / "replay-snapshots"))
        assert main(["onboard", APAR, "--raw-root", str(raw), *out, *config]) == INCOMPLETE
        assert recorded(db)[0][1:4] == acquired[0][1:4] and recorded(db)[1] == acquired[1]
        assert [count(db, table) for table in tables] == stored
