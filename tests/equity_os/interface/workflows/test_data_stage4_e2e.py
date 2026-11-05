"""D6 Task 6 (T6): the held-out Stage 4 company end to end against its frozen manifest.

The identifier is the current attempt's, read from the record at runtime; this file holds no
company value. Onboarding replays the attempt's retained root (no socket) into a fresh
``eqos_test_*`` database and the manifest's ``cli`` runs through ``main``; the D6 step 4 freeze
assertions follow. Every failure is an opaque ``pytest.fail`` naming the check (D1.7); a
mutation's differences are counted, never printed.
"""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
from collections.abc import Callable
from datetime import date
from functools import partial
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
from stage1_provenance import provenance
from stage4_support import (
    CLOSURE,
    DISCOVERY,
    FREEZE,
    IMPL,
    commits,
    current,
    git,
    is_ancestor,
    need,
    opaque,
    refused,
    sha256,
)
from test_frozen_manifests import REPO, load

from equity_os.companies.identity.identity_seed import SettingKey
from equity_os.companies.onboarding.discovery import MANIFEST_NAME
from equity_os.contracts.measurement.canonical import Basis
from equity_os.contracts.measurement.evidence import RunMode
from equity_os.contracts.measurement.evidence_tier import EvidenceTier
from equity_os.contracts.verification.comparison import CalculationState, SourceRole
from equity_os.contracts.verification.config_versions import ConfigVersions
from equity_os.interface.commands.companies import onboard_cli
from equity_os.interface.entry.cli import main
from equity_os.storage.records.repository import EvidenceRepository
from equity_os.verification.comparison.run import load_results
from equity_os.verification.comparison.run_config import LoadedConfig, load_run_config
from equity_os.verification.comparison.run_models import (
    FIRST_PARTY_SOURCES,
    ResultRow,
    RunExitStatus,
    RunManifest,
    RunScope,
)
from equity_os.verification.comparison.run_store import RunStore
from equity_os.verification.review_queue.queue import overlay_boundary, read_overlay

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
RETRIEVAL = "retrieval_manifest"
FROZEN = ("implementation_commit", "descriptor_commit", "acquisition_head")
RECORDED = (*FROZEN, "freeze_descriptor_sha256", "generation", "attempt")
# onboard's exit per predicted outcome (D4: an admitted PARTIAL is an incomplete success)
ONBOARD_EXIT = {"ONBOARDED": RunExitStatus.SUCCESS, "PARTIAL": RunExitStatus.INCOMPLETE}


class StoppedError(Exception):
    """Raised by a replay seam to stop onboarding once its generation is chosen."""


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


def replayed(folders: list[Path], root: Path, header: dict[str, Any], n: int) -> None:
    """Replay read exactly the manifest's generation (D2: none named, so the highest complete
    one), whose acquisition record names this attempt and the header's freeze fields and hashes
    the discovery and retrieval manifests the replay consumed."""
    paths = {s["kind"]: Path(s["path"]) for s in header["sources"]}
    names = {ACQUISITION: onboard_cli.ACQUISITION_NAME, DISCOVERY_KIND: MANIFEST_NAME}
    names[RETRIEVAL] = onboard_cli.RETRIEVAL_NAME
    pinned = paths[ACQUISITION].parent
    need(pinned.name == f"{onboard_cli.GENERATION_PREFIX}{header['generation']}", "generation")
    need(all(paths[kind] == pinned / name for kind, name in names.items()), "generation sources")
    need(folders == [root / pinned.name], "replayed generation")
    acquisition = json.loads((folders[0] / onboard_cli.ACQUISITION_NAME).read_bytes())
    need(all(acquisition[f] == header[f] for f in RECORDED), "acquisition record")
    need(acquisition["attempt"] == n, "acquisition attempt")
    consumed = {
        f"{kind}_sha256": sha256((folders[0] / names[kind]).read_bytes())
        for kind in (DISCOVERY_KIND, RETRIEVAL)
    }
    need(all(acquisition[f] == sha for f, sha in consumed.items()), "acquisition hashes")


def onboarded(code: int, out: list[str], cli: str, outcome: str) -> None:
    """onboard exits as its outcome does and prints exactly the manifest's command."""
    need(code == ONBOARD_EXIT[outcome], "onboard exit")
    commands = [
        line.removeprefix(onboard_cli.COMPARE_PREFIX)
        for line in out
        if line.startswith(onboard_cli.COMPARE_PREFIX)
    ]
    need(commands == ["eqos" + cli.removeprefix("fundamentals")], "printed command")


def ran(
    record: RunManifest, cli: str, onboarding: dict[str, Any], entity_id: int, frozen: Any
) -> LoadedConfig:
    """The stored run is the manifest's ``cli``: its entity, period, basis and vendor scope,
    its mode, and every pin of the configuration at the freeze's ``onboarding_versions``."""
    args = shlex.split(cli)
    need(args[:3] == ["fundamentals", "compare", "run"] and len(args) % 2 == 1, "cli")
    opts: dict[str, list[str]] = {}
    for flag, value in zip(args[3::2], args[4::2], strict=True):
        opts.setdefault(flag, []).append(value)
    versions = ConfigVersions.model_validate(frozen)
    need(opts["--entity"] == [onboarding["entity_key"]], "cli entity")
    need(opts["--period-end"] == [str(onboarding["period_end"])], "cli period")
    pins = [versions.dictionary], [versions.mapping_set]
    need((opts["--dictionary"], opts["--mapping-set"]) == pins, "cli versions")
    scope = RunScope(
        entity_ids=(entity_id,),
        period_ends=(date.fromisoformat(str(onboarding["period_end"])),),
        bases=(Basis(opts["--basis"][0].upper()),),
        sources=FIRST_PARTY_SOURCES,
        vendors=tuple((v.split("/", 1)[0], v.split("/", 1)[1]) for v in opts["--vendor"]),
    )
    need(record.scope == scope, "run scope")
    need(record.mode == RunMode(opts["--mode"][0].upper()), "run mode")
    config = load_run_config(REPO / "config", versions, vendors=scope.vendors)
    need(record.pinned == config.pinned, "run pins")
    return config


def selected(rows: tuple[ResultRow, ...]) -> list[int]:
    """The first-party interpretation ids the rows selected."""
    return [
        v.interpretation_id
        for row in rows
        for v in row.source_values
        if v.source_role is SourceRole.FIRST_PARTY and v.interpretation_id
    ]


def relabelled(rows: tuple[ResultRow, ...]) -> tuple[ResultRow, ...]:
    """The rows with their first-party selections rotated, numbers untouched."""
    ids = selected(rows)
    need(len(set(ids)) > 1, "selections to relabel")
    rotate = dict(zip(ids, ids[1:] + ids[:1], strict=True))
    return tuple(
        row.model_copy(
            update={
                "source_values": tuple(
                    v.model_copy(update={"interpretation_id": rotate[v.interpretation_id]})
                    if v.source_role is SourceRole.FIRST_PARTY and v.interpretation_id
                    else v
                    for v in row.source_values
                )
            }
        )
        for row in rows
    )


def deleted(rows: tuple[ResultRow, ...], target: int) -> tuple[ResultRow, ...]:
    """The rows with one first-party selection's interpretation id dropped, numbers untouched."""
    return tuple(
        row.model_copy(
            update={
                "source_values": tuple(
                    v.model_copy(update={"interpretation_id": None})
                    if v.source_role is SourceRole.FIRST_PARTY and v.interpretation_id == target
                    else v
                    for v in row.source_values
                )
            }
        )
        for row in rows
    )


def mutations_caught(outcome: Any, manifest: dict[str, Any], check: Callable[..., Any]) -> None:
    """Each mutation that leaves every number unchanged is caught: a relabelled selection or
    rule, each selection's id or direct occurrence deleted, a moved locator, a promoted tier, a
    broken construction operand, a vendor trace operand replaced by another of its operands, a
    first-party computed side's trace id deleted or unknown, or its trace operand broken
    (provenance), a wrong recorded mode or pin (``check``, the run-identity check)."""
    repository, rows, record = outcome.stage.repository, outcome.rows, outcome.record
    read, cells = repository.get_interpretations, repository.get_occurrences
    traces = repository.get_calculation_traces
    chosen = read(selected(rows))
    direct = [i.interpretation_id for i in chosen if i.occurrence_id]
    need(len(direct) > 1 and any(i.operand_interpretation_ids for i in chosen), "targets")
    vendor = [
        v.calculation_trace_id
        for row in rows
        for v in row.source_values
        if v.source_role is not SourceRole.FIRST_PARTY and v.calculation_trace_id
    ]
    need(
        any(len({o.interpretation_id for o in t.trace.operands}) > 1 for t in traces(vendor)),
        "vendor trace targets",
    )
    computed = [
        v.calculation_trace_id
        for row in rows
        for v in row.source_values
        if v.source_role is SourceRole.FIRST_PARTY
        and v.calculation_trace_id
        and v.calculation_state is CalculationState.COMPUTED
    ]
    need(
        any(o.interpretation_id for t in traces(computed) for o in t.trace.operands),
        "computed trace targets",
    )

    def moved(ids: list[int]) -> tuple[Any, ...]:
        found = cells(ids)
        return tuple(
            cell.model_copy(update={"anchor": o.anchor, "native_context": o.native_context})
            for cell, o in zip(found, found[1:] + found[:1], strict=True)
        )

    def promoted(ids: list[int]) -> tuple[Any, ...]:
        unproven = EvidenceTier.EQUIVALENCE_UNPROVEN
        tier = {"tier": EvidenceTier.EQUIVALENCE_DEMONSTRATED}
        return tuple(i.model_copy(update=tier) if i.tier is unproven else i for i in read(ids))

    def broken(ids: list[int]) -> tuple[Any, ...]:
        found = read(ids)
        operands = {o for i in found for o in i.operand_interpretation_ids}
        other = next(i for i in direct if i not in operands)
        return tuple(
            i.model_copy(
                update={"operand_interpretation_ids": (other, *i.operand_interpretation_ids[1:])}
            )
            if i.operand_interpretation_ids
            else i
            for i in found
        )

    def unresolved(ids: list[int]) -> tuple[Any, ...]:
        mutated = []
        for stored in traces(ids):
            operands = [
                o.model_copy(update={"interpretation_id": 10**9})
                if o.interpretation_id and stored.trace_id in computed
                else o
                for o in stored.trace.operands
            ]
            trace = stored.trace.model_copy(update={"operands": tuple(operands)})
            mutated.append(stored.model_copy(update={"trace": trace}))
        return tuple(mutated)

    def duplicated(ids: list[int]) -> tuple[Any, ...]:
        mutated = []
        for stored in traces(ids):
            operands = list(stored.trace.operands)
            a = operands[0].interpretation_id if operands else None
            b = next((n for n, o in enumerate(operands) if o.interpretation_id != a), None)
            if b is not None:
                operands[b] = operands[b].model_copy(update={"interpretation_id": a})
            trace = stored.trace.model_copy(update={"operands": tuple(operands)})
            mutated.append(stored.model_copy(update={"trace": trace}))
        return tuple(mutated)

    ruled = tuple(row.model_copy(update={"applicability_rule_id": "relabelled"}) for row in rows)
    missed = [
        name
        for name, mutated in (
            ("relabelled selection", relabelled(rows)),
            ("relabelled rule", ruled),
        )
        if not provenance(outcome, mutated, manifest)
    ]
    missed += [
        f"deleted id {n}"
        for n, target in enumerate(sorted(set(selected(rows))))
        if not provenance(outcome, deleted(rows, target), manifest)
    ]
    for n, occurrence in enumerate(sorted({i.occurrence_id for i in chosen if i.occurrence_id})):
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(
                repository,
                "get_occurrences",
                lambda ids, gone=occurrence: tuple(
                    c for c in cells(ids) if c.occurrence_id != gone
                ),
            )
            if not provenance(outcome, None, manifest):
                missed.append(f"deleted occurrence {n}")
    for name, method, seam in (
        ("moved locator", "get_occurrences", moved),
        ("promoted tier", "get_interpretations", promoted),
        ("broken operand", "get_interpretations", broken),
        ("duplicated vendor operand", "get_calculation_traces", duplicated),
        ("unresolved computed operand", "get_calculation_traces", unresolved),
    ):
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(repository, method, seam)
            if not provenance(outcome, None, manifest):
                missed.append(name)
    for n, target in enumerate(sorted(set(computed))):
        for name, trace_id in (("deleted", None), ("unknown", 10**9)):
            retraced = tuple(
                row.model_copy(
                    update={
                        "source_values": tuple(
                            v.model_copy(update={"calculation_trace_id": trace_id})
                            if v.source_role is SourceRole.FIRST_PARTY
                            and v.calculation_trace_id == target
                            else v
                            for v in row.source_values
                        )
                    }
                )
                for row in rows
            )
            if not provenance(outcome, retraced, manifest):
                missed.append(f"{name} computed trace {n}")
    wrong_pin = record.pinned.model_copy(update={"mapping_set": record.pinned.dictionary})
    wrong: dict[str, dict[str, Any]] = {
        "wrong mode": {"mode": RunMode.RETROSPECTIVE},
        "wrong pin": {"pinned": wrong_pin},
    }
    for name, update in wrong.items():
        if not refused(partial(check, record.model_copy(update=update))):
            missed.append(name)
    need(not missed, f"mutations uncaught: {', '.join(missed)}")


@pytest.mark.pg
@pytest.mark.retained
def test_stage4_onboards_and_compares_as_its_manifest(
    pg_db: PgTestDatabase,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Replay onboarding of the manifest's generation exits as and records the manifest's (and
    prediction's) outcome, unit states, captures, settings, entity key and period; the printed
    ``compare run`` is the manifest's ``cli`` and, through ``main``, stores that run (scope,
    mode, pins) with its rows, provenance, status and projected failures."""
    with opaque("stage4_e2e inputs"):
        attempt, freeze, manifest = inputs()
        header, onboarding, (run,) = manifest["header"], manifest["onboarding"], manifest["runs"]
        prediction = attempt["prediction"]
        root = REPO / f"data/raw/onboarding/attempt-{attempt['n']}"
        need(root.is_dir(), "attempt root")
    monkeypatch.chdir(REPO)  # the manifest's ``cli`` names the checkout's ``config``
    for name, value in pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(onboard_cli, "live_transport", lambda: need(False, "transport opened"))
    folders: list[Path] = []
    replay = onboard_cli.replay_fetch

    def spy(folder: Path) -> Any:
        folders.append(folder)
        return replay(folder)

    monkeypatch.setattr(onboard_cli, "replay_fetch", spy)

    with opaque("stage4_e2e onboard"):
        snapshots = str(tmp_path / "snapshots")
        argv = ["onboard", attempt["identifier"], "--raw-root", str(root)]
        code, out = printed(capsys, [*argv, "--snapshot-root", snapshots])
        onboarded(code, out, header["cli"], onboarding["outcome"])
        need(
            refused(lambda: onboarded(RunExitStatus.FAILURE, out, header["cli"], "PARTIAL")),
            "wrong exit",
        )
        replayed(folders, root, header, attempt["n"])

    with opaque("stage4_e2e onboarding"):
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

    with opaque("stage4_e2e evidence"):
        need(
            all(sha256((REPO / s["path"]).read_bytes()) == s["sha256"] for s in header["sources"]),
            "source hashes",
        )
        captured = {
            e["sha256"] for e in source(manifest, DISCOVERY_KIND)["entries"] if e["outcome"] == "OK"
        }
        stored = {sha for (sha,) in rows(pg_db, "SELECT blob_sha256 FROM eqos.capture_refs")}
        need(stored == captured, "capture hashes")

    with opaque("stage4_e2e settings"):
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

    with opaque("stage4_e2e compare"):
        code, out = printed(capsys, shlex.split(header["cli"])[1:])
        (run_id,) = [int(line.split("\t", 1)[1]) for line in out if line.startswith("run\t")]
        with pg_db.runtime_pool() as pool:
            results = load_results(run_id, pool=pool)
            items = list(read_overlay(pool, run_id=run_id, as_of=overlay_boundary(pool)).open_items)
            record = RunStore(pool).read_manifest(run_id)

            def identity(stored: RunManifest) -> LoadedConfig:
                return ran(
                    stored, header["cli"], onboarding, entity_id, freeze["onboarding_versions"]
                )

            stage = SimpleNamespace(
                run=run,
                entity_id=entity_id,
                pool=pool,
                repository=EvidenceRepository(pool),
                config=identity(record),
            )
            got_run = SimpleNamespace(
                stage=stage,
                rows=results,
                record=record,
                got=actual(run, results, items),
                items=items,
                status=record.status.value,
                exit=code,
            )
            lines = manifest_lines(got_run, manifest)  # type: ignore[arg-type]
            need(not lines, f"{len(lines)} run differences")
            lines = provenance(got_run, None, manifest)  # type: ignore[arg-type]
            need(not lines, f"{len(lines)} provenance differences")
            mutations_caught(got_run, manifest, identity)
        need(record.status.value == prediction["run_status"], "run status")
        projected = {failure_surface(f) for f in record.operational_failures}
        need(projected == {failure_surface(f) for f in run["operational_failures"]}, "failures")


@pytest.mark.retained
def test_stage4_later_generation_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A later complete generation with identical bodies is what replay would choose; the
    generation binding refuses it and accepts the manifest's own (no database is reached)."""
    with opaque("stage4_e2e generation"):
        attempt, _, manifest = inputs()
        header, root = manifest["header"], tmp_path / "root"
        shutil.copytree(REPO / f"data/raw/onboarding/attempt-{attempt['n']}", root)
        pinned = root / f"{onboard_cli.GENERATION_PREFIX}{header['generation']}"
        later = root / f"{onboard_cli.GENERATION_PREFIX}{header['generation'] + 1}"
        shutil.copytree(pinned, later)
        document = json.loads((later / MANIFEST_NAME).read_bytes())
        (later / MANIFEST_NAME).write_text(
            json.dumps(document | {"generation": header["generation"] + 1})
        )
        folders: list[Path] = []

        def stop(folder: Path) -> None:
            folders.append(folder)
            raise StoppedError

        monkeypatch.setattr(onboard_cli, "replay_fetch", stop)
        argv = ["onboard", attempt["identifier"], "--raw-root", str(root)]
        try:
            main([*argv, "--snapshot-root", str(tmp_path / "snapshots")])
        except StoppedError:
            pass
        need(folders == [later], "later generation chosen")
        need(refused(lambda: replayed(folders, root, header, attempt["n"])), "later refused")
        replayed([pinned], root, header, attempt["n"])


def test_stage4_freeze_held_to_closure() -> None:
    """D6 step 4, pinned at the phase's closure (owner ruling 2026-10-16, D6.md Q2 amendment):
    implementation ⊑ descriptor ⊑ acquisition head ⊑ ``CLOSURE`` ⊑ HEAD; the acquisition head's
    descriptor holds the recorded entry; no implementation change from the freeze to ``CLOSURE``;
    ``discovery.py`` exists at the freeze. Later phases may change the implementation."""
    with opaque("stage4_e2e freeze"):
        _, freeze, manifest = inputs()
        implementation, descriptor, head = (manifest["header"][f] for f in FROZEN)
        need(freeze["implementation_commit"] == implementation, "freeze entry")
        chain = [
            (implementation, descriptor),
            (descriptor, head),
            (head, CLOSURE),
            (CLOSURE, "HEAD"),
        ]
        need(all(is_ancestor(REPO, old, new) for old, new in chain), "ancestry")
        entries = yaml.safe_load(git(REPO, "show", f"{head}:{FREEZE}"))["freezes"]
        hashes = {sha256(yaml.safe_dump(e, sort_keys=True).encode()) for e in entries}
        need(manifest["header"]["freeze_descriptor_sha256"] in hashes, "descriptor entry")
        span = f"{implementation}..{CLOSURE}"
        need(not commits(REPO, span, "--", *IMPL), "implementation commits")
        diff = subprocess.run(
            ["git", "diff", "--quiet", implementation, CLOSURE, "--", "src", "config"], cwd=REPO
        )
        need(diff.returncode == 0, "src/config diff")
        found = subprocess.run(["git", "cat-file", "-e", f"{implementation}:{DISCOVERY}"], cwd=REPO)
        need(found.returncode == 0, "discovery at the freeze")
