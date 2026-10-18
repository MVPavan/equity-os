"""PREP-2b Task 5: ``run --retrospective`` admits registered originals published by the cutoff.

The originals are registered (really) after the source cutoff. Without the flag that refuses as
before. With it, the manifest must be the one ``config/ledger_import.yaml`` pins and each
registered original one of the quarter's manifest originals published by the cutoff; its real
acquisition and registration times are kept. A local source is never retrospective.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from retained_support import REPO_ROOT
from tests.fundamentals.test_cli_temporal_admission import cli_fixture
from tests.fundamentals.test_source_intake_cli import INTAKE_TIME, intake_fixture

from fundamentals.api.cli import _build_parser, main, run_command
from fundamentals.api.config import load_config
from fundamentals.api.ledger_cli import DEFAULT_IMPORT_CONFIG
from fundamentals.api.pipeline import PipelineResult
from fundamentals.api.source_admission import RETROSPECTIVE, SourceAdmissionError

CUTOFF = INTAKE_TIME - timedelta(days=1)
PINNED = "c47866ce13f719521bbcc7826fc23590acc73f9904cfc1749a1ad911bb399a1b"
NSE_WALL = "%d-%b-%Y %H:%M:%S"
IST = timedelta(hours=5, minutes=30)


def _manifest(
    fixture: dict[str, Any], tmp_path: Path, published: datetime, *, drop: int = 3
) -> Path:
    """A retrieval manifest of the fixture's quarter: every original (but ``drop``) filed at
    ``published``, written as NSE wall time (IST)."""
    config = load_config(fixture["config"])
    entries = [
        {
            "quarter": config.quarter.issuer_quarter,
            "sha256": ref.source_sha256,
            "filed_at_nse": (published.replace(tzinfo=None) + IST).strftime(NSE_WALL),
        }
        for index, ref in enumerate(fixture["refs"].values())
        if index != drop
    ]
    path = tmp_path / "retrieval-manifest.json"
    path.write_text(json.dumps({"issuer": config.issuer.nse_symbol, "entries": entries}))
    _pin(config.repo_root(fixture["config"]), path)
    return path


def _pin(root: Path, manifest: Path) -> None:
    """Pin ``manifest`` in ``root``'s ledger import config, as the committed one pins its own."""
    body = (REPO_ROOT / DEFAULT_IMPORT_CONFIG).read_text()
    pinned = hashlib.sha256(manifest.read_bytes()).hexdigest()
    (root / DEFAULT_IMPORT_CONFIG).write_text(body.replace(PINNED, pinned))


def _run(fixture: dict[str, Any], *extra: str) -> PipelineResult:
    """The registered run of the fixture, through ``run_command``."""
    (fixture["config"].parent.parent / "output").mkdir(exist_ok=True)
    args = _build_parser().parse_args([*fixture["run"], *extra])
    return run_command(args, intake_context=fixture["context"])


@pytest.fixture
def registered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Originals registered at ``INTAKE_TIME``, a day after the source cutoff."""
    fixture = intake_fixture(tmp_path, monkeypatch, cutoff=CUTOFF)
    assert main(fixture["register"], intake_context=fixture["context"]) == 0
    return fixture


def test_registered_after_the_cutoff_refuses_without_the_flag(
    registered: dict[str, Any],
) -> None:
    """The ordinary rule stands: registration after the cutoff is not historical possession."""
    with pytest.raises(SourceAdmissionError, match="exceeds cutoff"):
        _run(registered)


def test_retrospective_admits_package_originals_with_real_times(
    registered: dict[str, Any], tmp_path: Path
) -> None:
    """Each original is admitted ``retrospective_registered`` at its real, later times."""
    manifest = _manifest(registered, tmp_path, CUTOFF - timedelta(hours=1))
    sources = _run(registered, "--retrospective", str(manifest)).temporal_evidence.sources
    assert [source.mode for source in sources] == [RETROSPECTIVE] * 3
    for source in sources:
        assert source.registration is not None
        assert source.registration.registered_at == INTAKE_TIME > CUTOFF
        assert source.acquired_at == source.registration.capture_completed_at


@pytest.mark.parametrize(
    ("published", "drop"),
    [
        (CUTOFF - timedelta(hours=1), 1),  # the results PDF is not a package original
        (CUTOFF + timedelta(seconds=1), 3),  # published after the source cutoff
        (CUTOFF + IST - timedelta(minutes=1), 3),  # inside the old 5h30 window
    ],
)
def test_retrospective_refuses_outside_the_published_package(
    registered: dict[str, Any], tmp_path: Path, published: datetime, drop: int
) -> None:
    """Not in the quarter's package, or published after the cutoff: refused."""
    manifest = _manifest(registered, tmp_path, published, drop=drop)
    with pytest.raises(SourceAdmissionError, match="not a package original"):
        _run(registered, "--retrospective", str(manifest))


def test_a_local_source_is_never_retrospective(registered: dict[str, Any], tmp_path: Path) -> None:
    """With no registered references the sources are new local captures: past the cutoff."""
    manifest = _manifest(registered, tmp_path, CUTOFF - timedelta(hours=1))
    (tmp_path / "local").mkdir()
    config, _, argv = cli_fixture(tmp_path / "local")
    _pin(load_config(config).repo_root(config), manifest)
    with pytest.raises(SourceAdmissionError, match="exceeds cutoff"):
        main([*argv, "--retrospective", str(manifest)])


def test_retrospective_refuses_an_unpinned_manifest(
    registered: dict[str, Any], tmp_path: Path
) -> None:
    """A manifest other than the pinned one cannot select the historical package."""
    manifest = _manifest(registered, tmp_path, CUTOFF - timedelta(hours=1))
    manifest.write_text(manifest.read_text() + "\n")
    with pytest.raises(SourceAdmissionError, match="is not the pinned"):
        _run(registered, "--retrospective", str(manifest))
