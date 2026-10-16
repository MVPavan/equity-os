"""D6 Task 6 (T6): the held-out Stage 4 company end to end against its frozen manifest.

The identifier is the current attempt's, read from the record at runtime; this file holds no
company value. Onboarding replays the attempt's retained root (no socket) into a fresh
``eqos_test_*`` database and the manifest's ``cli`` runs through ``main``; the D6 step 4 freeze
assertions follow. Every failure is an opaque ``pytest.fail`` naming the check (D1.7).
"""

from __future__ import annotations

import json
import shlex
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml
from manifest_support import DISCOVERY as DISCOVERY_KIND
from manifest_support import SETTINGS, check_stage4, failure_surface
from onboarding_support import recorded, rows
from pg_support import PgTestDatabase
from stage1_e2e_support import actual, manifest_lines
from stage4_support import (
    DISCOVERY,
    FREEZE,
    IMPL,
    RefusedError,
    commits,
    current,
    git,
    is_ancestor,
    need,
    sha256,
)
from test_frozen_manifests import REPO, load

from fundamentals.api import onboard_cli
from fundamentals.api.cli import main
from fundamentals.compare.queue import overlay_boundary, read_overlay
from fundamentals.compare.run import load_results
from fundamentals.compare.run_store import RunStore
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.pg.identity_seed import SettingKey

MANIFEST = REPO / "tests/fundamentals/fixtures/data_foundation/stage4_manifest.yaml"
ACQUISITION = "acquisition"  # header source kind of the generation's acquisition.json
SETTING_KEYS = dict(
    zip(
        SETTINGS,
        (
            SettingKey.FISCAL_YEAR_END_MONTH,
            SettingKey.PRESENTATION_CURRENCY,
            SettingKey.FILING_ROUNDING_LEVEL,
            SettingKey.REPORTING_FRAMEWORK,
        ),
        strict=True,
    )
)
FROZEN = ("implementation_commit", "descriptor_commit", "acquisition_head")
RECORDED = (*FROZEN, "freeze_descriptor_sha256", "generation")


@contextmanager
def opaque(check: str) -> Iterator[None]:
    """Fail the check by name and step only, never a value or traceback (D1.7)."""
    try:
        yield
        return
    except RefusedError as refused:
        step = str(refused)
    except Exception as error:  # opaque: the type only, a message may carry a value
        step = type(error).__name__
    pytest.fail(f"stage4_e2e {check}: {step}", pytrace=False)


def inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """The current attempt, its freeze entry and the Stage 4 manifest, checked by
    ``check_stage4`` against each other."""
    attempt, freeze = current(REPO)
    manifest = load(MANIFEST)
    check_stage4(REPO, manifest, attempt, freeze)
    return attempt, freeze, manifest


def printed(capsys: pytest.CaptureFixture[str], argv: list[str]) -> tuple[int, list[str]]:
    """``main(argv)``'s exit and stdout lines; the capture is drained even on a raise, so no
    printed value reaches a failure report."""
    try:
        code = main(argv)
        return code, capsys.readouterr().out.splitlines()
    finally:
        capsys.readouterr()


def source(manifest: dict[str, Any], kind: str) -> Any:
    """The JSON of the manifest's one source of ``kind``."""
    (path,) = [s["path"] for s in manifest["header"]["sources"] if s["kind"] == kind]
    return json.loads((REPO / path).read_bytes())


@pytest.mark.pg
@pytest.mark.retained
def test_stage4_onboards_and_compares_as_its_manifest(
    pg_db: PgTestDatabase,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Replay onboarding records the manifest's (and prediction's) outcome, unit states,
    captures, settings, entity key and period; the printed ``compare run`` is the manifest's
    ``cli`` and, through ``main``, yields its rows, status and projected failures."""
    with opaque("inputs"):
        attempt, _, manifest = inputs()
        header, onboarding, (run,) = manifest["header"], manifest["onboarding"], manifest["runs"]
        prediction = attempt["prediction"]
        root = REPO / f"data/raw/onboarding/attempt-{attempt['n']}"
        need(root.is_dir(), "attempt root")
    monkeypatch.chdir(REPO)  # the manifest's ``cli`` names the checkout's ``config``
    for name, value in pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    opened = "stage4_e2e onboard: replay opened a transport"
    monkeypatch.setattr(onboard_cli, "live_transport", lambda: pytest.fail(opened, pytrace=False))

    with opaque("onboard"):
        snapshots = str(tmp_path / "snapshots")
        argv = ["onboard", attempt["identifier"], "--raw-root", str(root)]
        _, out = printed(capsys, [*argv, "--snapshot-root", snapshots])
        commands = [
            line.removeprefix(onboard_cli.COMPARE_PREFIX)
            for line in out
            if line.startswith(onboard_cli.COMPARE_PREFIX)
        ]
        need(commands == [header["cli"]], "printed command")

    with opaque("onboarding"):
        (_, outcome, _, _, entity_id), states = recorded(pg_db)
        need(outcome == onboarding["outcome"] == prediction["outcome"], "outcome")
        units = {u: (unit["state"], unit.get("reason")) for u, unit in onboarding["units"].items()}
        need(states == units, "unit states")
        excluded = sorted(u for u, (state, _) in states.items() if state != "VERIFIED")
        need(excluded == sorted(prediction["excluded_units"]), "excluded units")
        key = rows(pg_db, "SELECT entity_key FROM eqos.reporting_entities WHERE id = %s", entity_id)
        need(key == [(onboarding["entity_key"],)], "entity key")
        period = rows(
            pg_db,
            "SELECT reporting_period_end FROM eqos.filing_packages WHERE entity_id = %s",
            entity_id,
        )
        need(period == [(date.fromisoformat(str(onboarding["period_end"])),)], "period")

    with opaque("evidence"):
        need(
            all(sha256((REPO / s["path"]).read_bytes()) == s["sha256"] for s in header["sources"]),
            "source hashes",
        )
        acquisition = source(manifest, ACQUISITION)
        need(all(acquisition[f] == header[f] for f in RECORDED), "acquisition record")
        captured = {
            e["sha256"] for e in source(manifest, DISCOVERY_KIND)["entries"] if e["outcome"] == "OK"
        }
        stored = {sha for (sha,) in rows(pg_db, "SELECT blob_sha256 FROM eqos.capture_refs")}
        need(stored == captured, "capture hashes")

    with opaque("settings"):
        values = {node["name"]: node for node in onboarding["values"]}
        location = {"url": values["DOCUMENT_URL"]["v"], "sha256": values["DOCUMENT_SHA256"]["v"]}
        want = {
            (SETTING_KEYS[n["name"]].value, str(n["v"]), date.fromisoformat(str(n["valid_from"])))
            for n in onboarding["values"]
            if n["name"] in SETTINGS
        } | {
            (
                SettingKey.DOCUMENT_LOCATION.value,
                json.dumps(location, sort_keys=True),
                date.fromisoformat(str(onboarding["period_end"])),
            )
        }
        got = rows(
            pg_db,
            "SELECT setting_key, value_text, valid_from FROM eqos.settings_records "
            "WHERE entity_id = %s",
            entity_id,
        )
        need(set(got) == want and len(got) == len(want), "settings")
        basis = rows(
            pg_db,
            "SELECT basis_status FROM eqos.entity_basis_status WHERE entity_id = %s",
            entity_id,
        )
        need(basis == [(values["BASIS_STATUS"]["v"],)], "basis status")

    with opaque("compare"):
        code, out = printed(capsys, shlex.split(header["cli"])[1:])
        (run_id,) = [int(line.split("\t", 1)[1]) for line in out if line.startswith("run\t")]
        with pg_db.runtime_pool() as pool:
            results = load_results(run_id, pool=pool)
            items = list(read_overlay(pool, run_id=run_id, as_of=overlay_boundary(pool)).open_items)
            record = RunStore(pool).read_manifest(run_id)
            stage = SimpleNamespace(
                run=run, entity_id=entity_id, pool=pool, repository=EvidenceRepository(pool)
            )
            got_run = SimpleNamespace(
                stage=stage,
                got=actual(run, results, items),
                items=items,
                status=record.status.value,
                exit=code,
            )
            lines = manifest_lines(got_run, manifest)  # type: ignore[arg-type]
        need(not lines, f"{len(lines)} run differences")
        need(record.status.value == prediction["run_status"], "run status")
        projected = {failure_surface(f) for f in record.operational_failures}
        need(projected == {failure_surface(f) for f in run["operational_failures"]}, "failures")


def test_stage4_freeze_holds_at_head() -> None:
    """D6 step 4: implementation ⊑ descriptor ⊑ acquisition head ⊑ HEAD; the acquisition
    head's descriptor holds the recorded entry; no implementation change since the freeze,
    committed or not; ``discovery.py`` exists at the freeze."""
    with opaque("freeze"):
        _, freeze, manifest = inputs()
        implementation, descriptor, head = (manifest["header"][f] for f in FROZEN)
        need(freeze["implementation_commit"] == implementation, "freeze entry")
        ancestry = [(implementation, descriptor), (descriptor, head), (head, "HEAD")]
        need(all(is_ancestor(REPO, old, new) for old, new in ancestry), "ancestry")
        entries = yaml.safe_load(git(REPO, "show", f"{head}:{FREEZE}"))["freezes"]
        hashes = {sha256(yaml.safe_dump(e, sort_keys=True).encode()) for e in entries}
        need(manifest["header"]["freeze_descriptor_sha256"] in hashes, "descriptor entry")
        need(not commits(REPO, f"{implementation}..HEAD", "--", *IMPL), "implementation commits")
        diff = subprocess.run(
            ["git", "diff", "--quiet", implementation, "--", "src", "config"], cwd=REPO
        )
        need(diff.returncode == 0, "src/config diff")
        need(not git(REPO, "status", "--porcelain", "--", *IMPL), "uncommitted implementation")
        found = subprocess.run(["git", "cat-file", "-e", f"{implementation}:{DISCOVERY}"], cwd=REPO)
        need(found.returncode == 0, "discovery at the freeze")
