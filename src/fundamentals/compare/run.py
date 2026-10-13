"""Execute, publish and replay one comparison run (D1a Task 9).

``execute_run`` loads and content-pins every versioned artifact, resolves the request's
evidence (``resolve``), and publishes the run in one transaction (``RunStore.publish``):
identical requests, even concurrent ones, yield one run. ``replay_run`` reads only the
manifest (``run_versions`` and ``run_inputs``), reloads every input by id through a
``ReplayReader`` and recomputes, so later evidence never changes a stored run. A run's
operational failures are a function of its rows, so a replay reproduces them too.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from pathlib import Path

from psycopg_pool import ConnectionPool

from fundamentals.compare.resolve import load_inputs, recompute, resolve
from fundamentals.compare.resolve_models import ReplayReader
from fundamentals.compare.run_config import (
    ConfigVersions,
    LoadedConfig,
    load_run_config,
    pin_config,
    require_pins,
)
from fundamentals.compare.run_models import (
    FIRST_PARTY_SOURCES,
    DatabaseIdentity,
    ResultRow,
    RunExitStatus,
    RunInput,
    RunInputDisposition,
    RunInputKind,
    RunManifest,
    RunRecord,
    RunRequest,
    RunScope,
    RunStatus,
    SourceRole,
    SourceValue,
)
from fundamentals.compare.run_store import PublishHook, RunStore
from fundamentals.contracts.canonical import Basis, Representation
from fundamentals.contracts.comparison import SourceState
from fundamentals.contracts.evidence import RunMode, VersionPin
from fundamentals.contracts.versioning import VersionContentDriftError
from fundamentals.evidence.repository import EvidenceRepository

__all__ = [
    "DatabaseIdentity",
    "ResultRow",
    "RunExitStatus",
    "RunInput",
    "RunInputDisposition",
    "RunInputKind",
    "RunManifest",
    "RunRecord",
    "RunRequest",
    "RunScope",
    "RunStatus",
    "SourceValue",
    "VersionContentDriftError",
    "execute_run",
    "exit_status",
    "load_results",
    "operational_failures",
    "replay_run",
    "request_for",
]

DEFINITION_SET_ARTIFACT = "definition_set"
NO_ATTEMPT = "-"
_FAILURE = "{representation}\t{reason}\tattempt={attempt}"


def request_for(
    entity_id: int,
    period_end: date,
    basis: Basis,
    *,
    cutoff: datetime,
    config_root: Path,
    code_version: str,
    database_identity: DatabaseIdentity,
    mode: RunMode = RunMode.AS_KNOWN,
    sources: tuple[str, ...] = FIRST_PARTY_SOURCES,
    versions: ConfigVersions | None = None,
    extractor_pins: Mapping[Representation, VersionPin] | None = None,
) -> RunRequest:
    """A one-entity, one-period request pinned to the config root's artifacts at ``versions``."""
    config = load_run_config(config_root, versions, extractor_pins=extractor_pins)
    return RunRequest(
        scope=RunScope(
            entity_ids=(entity_id,), period_ends=(period_end,), bases=(basis,), sources=sources
        ),
        cutoff=cutoff,
        mode=mode,
        pinned=config.pinned,
        code_version=code_version,
        database_identity=database_identity,
    )


def execute_run(
    request: RunRequest,
    *,
    pool: ConnectionPool,
    config_root: Path,
    extractor_pins: Mapping[Representation, VersionPin] | None = None,
    publish_hook: PublishHook | None = None,
) -> RunRecord:
    """Resolve and publish one run, or return the stored run of the same identity."""
    config = _config(config_root, request, extractor_pins)
    repository = EvidenceRepository(pool)
    definition_set_id = pin_config(
        config, repository=repository, pool=pool, config_root=config_root
    )
    store = RunStore(pool)
    inputs, rows = resolve(
        request,
        repository=repository,
        store=store,
        config=config,
        definition_set_id=definition_set_id,
    )
    manifest = RunManifest(
        scope=request.scope,
        cutoff=request.cutoff,
        mode=request.mode,
        pinned=request.pinned,
        code_version=request.code_version,
        database_identity=request.database_identity,
        inputs=inputs.inputs,
        status=run_status(rows),
        operational_failures=operational_failures(rows),
    )
    run_id, created = store.publish(
        manifest, rows, definition_set_id=definition_set_id, publish_hook=publish_hook
    )
    stored = manifest if created else store.read_manifest(run_id)
    return RunRecord(run_id=run_id, manifest=stored, created=created)


def replay_run(
    run_id: int,
    *,
    pool: ConnectionPool,
    config_root: Path,
    reader: ReplayReader | None = None,
) -> tuple[ResultRow, ...]:
    """Recompute a stored run from its manifest and by-id evidence reads alone.

    Extractors are not re-run: the manifest's extractor pins stand. Every other artifact is
    reloaded at its pinned version and refused if its content drifted.
    """
    manifest = RunStore(pool).read_manifest(run_id)
    pinned = manifest.pinned
    extractors = {
        Representation.XBRL: pinned.extractor_xbrl,
        Representation.PDF: pinned.extractor_pdf,
    }
    request = RunRequest(
        scope=manifest.scope,
        cutoff=manifest.cutoff,
        mode=manifest.mode,
        pinned=pinned,
        code_version=manifest.code_version,
        database_identity=manifest.database_identity,
    )
    config = _config(config_root, request, extractors)
    by_id = reader if reader is not None else EvidenceRepository(pool)
    inputs = load_inputs(by_id, manifest.inputs)
    stored_set = by_id.get_definition_set(inputs.definition_set_id)
    if stored_set.content_sha256 != pinned.definition_set.content_sha256:
        raise VersionContentDriftError(
            artifact=DEFINITION_SET_ARTIFACT,
            version=pinned.definition_set.version,
            pinned_sha256=pinned.definition_set.content_sha256,
            actual_sha256=stored_set.content_sha256,
        )
    return recompute(inputs, request, config=config)


def load_results(run_id: int, *, pool: ConnectionPool) -> tuple[ResultRow, ...]:
    """A stored run's result rows, as published."""
    return RunStore(pool).read_results(run_id)


def run_status(rows: tuple[ResultRow, ...]) -> RunStatus:
    """``INCOMPLETE`` when any first-party source state is ``UNAVAILABLE``."""
    unavailable = any(
        value.state is SourceState.UNAVAILABLE
        for row in rows
        for value in row.source_values
        if value.source_role is SourceRole.FIRST_PARTY
    )
    return RunStatus.INCOMPLETE if unavailable else RunStatus.COMPLETE


def operational_failures(rows: tuple[ResultRow, ...]) -> tuple[str, ...]:
    """Each distinct failure behind a first-party ``UNAVAILABLE`` state, in sorted order.

    A failure is the representation, the reason that decided the state and the attempt that
    recorded it (``-`` when the state comes from the pins, e.g. nothing extracted under the
    pinned extractor). Non-empty exactly when the run is ``INCOMPLETE``.
    """
    return tuple(
        sorted(
            {
                _FAILURE.format(
                    representation=value.representation.value,
                    reason=value.reason or NO_ATTEMPT,
                    attempt=NO_ATTEMPT if value.attempt_id is None else value.attempt_id,
                )
                for row in rows
                for value in row.source_values
                if value.source_role is SourceRole.FIRST_PARTY
                and value.state is SourceState.UNAVAILABLE
            }
        )
    )


def exit_status(record: RunRecord) -> RunExitStatus:
    """The CLI exit status of a published run (open-high is first emitted by D1b.3)."""
    if record.manifest.status is RunStatus.INCOMPLETE:
        return RunExitStatus.INCOMPLETE
    return RunExitStatus.SUCCESS


def _config(
    config_root: Path,
    request: RunRequest,
    extractor_pins: Mapping[Representation, VersionPin] | None,
) -> LoadedConfig:
    """The request's pinned artifacts, refused if any resolved content differs."""
    config = load_run_config(
        config_root, ConfigVersions.of(request.pinned), extractor_pins=extractor_pins
    )
    require_pins(config, request.pinned)
    return config
