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

from equity_os.contracts.measurement.canonical import Basis, Representation
from equity_os.contracts.measurement.evidence import (
    FilingFamily,
    RunMode,
    VendorExtractorPin,
    VersionPin,
)
from equity_os.contracts.storage.retention import OriginalExpiredError
from equity_os.contracts.verification.comparison import SourceState
from equity_os.contracts.verification.review_queue import QueueOverlay, QueueSeverity
from equity_os.contracts.verification.versioning import VersionContentDriftError
from equity_os.storage.records.repository import EvidenceRepository
from equity_os.verification.comparison.resolve import load_inputs, recompute, resolve
from equity_os.verification.comparison.resolve_models import ReplayReader, ResolvedInputs
from equity_os.verification.comparison.run_config import (
    ConfigVersions,
    LoadedConfig,
    extractor_pin,
    load_run_config,
    pin_config,
    require_pins,
)
from equity_os.verification.comparison.run_family import RUN_FAMILIES
from equity_os.verification.comparison.run_models import (
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
from equity_os.verification.comparison.run_store import PublishHook, RunStore
from equity_os.verification.comparison.vendor_sides import NO_ATTEMPT as NO_CAPTURE
from equity_os.verification.review_queue.routing import route_run

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
    "replay_inputs",
    "replay_run",
    "request_for",
]

DEFINITION_SET_ARTIFACT = "definition_set"
NO_ATTEMPT = "-"
_FAILURE = "{representation}\t{reason}\tattempt={attempt}"
_NON_DIAGNOSTIC = (SourceRole.FIRST_PARTY, SourceRole.INDEPENDENT_VENDOR)
_EXPIRED = "ORIGINAL_EXPIRED: {what} reads expired vendor captures {captures}"


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
    sources: tuple[str, ...] | None = None,
    vendors: tuple[tuple[str, str], ...] = (),
    versions: ConfigVersions | None = None,
    extractor_pins: Mapping[Representation, VersionPin] | None = None,
    family: FilingFamily = FilingFamily.FINANCIAL_RESULTS,
) -> RunRequest:
    """A one-entity, one-period request pinned to the config root's artifacts at ``versions``.

    Sources default to the family's first-party surfaces, and a shareholding request pins
    the family's XBRL extractor (plan D8 R6).
    """
    scope = RunScope(
        entity_ids=(entity_id,),
        period_ends=(period_end,),
        bases=(basis,),
        sources=RUN_FAMILIES[family].sources if sources is None else sources,
        vendors=vendors,
        family=family,
    )
    config = load_run_config(
        config_root,
        versions,
        extractor_pins=_extractors(family, extractor_pins),
        vendors=scope.vendors,
    )
    return RunRequest(
        scope=scope,
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
    """Resolve and publish one run with its routed queue items, or return the stored run of
    the same identity."""
    config = _config(config_root, request, extractor_pins)
    repository = EvidenceRepository(pool)
    definition_set_id = pin_config(config, repository=repository, pool=pool)
    store = RunStore(pool)
    inputs, rows = resolve(
        request,
        repository=repository,
        store=store,
        config=config,
        definition_set_id=definition_set_id,
    )
    inputs = _retained(inputs, request, pool)
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
        manifest,
        rows,
        definition_set_id=definition_set_id,
        publish_hook=publish_hook,
        queue_drafts=route_run(inputs, rows, request.pinned),
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
    inputs, request, config = replay_inputs(
        run_id, pool=pool, config_root=config_root, reader=reader
    )
    return recompute(inputs, request, config=config)


def replay_inputs(
    run_id: int,
    *,
    pool: ConnectionPool,
    config_root: Path,
    reader: ReplayReader | None = None,
) -> tuple[ResolvedInputs, RunRequest, LoadedConfig]:
    """A stored run's frozen evidence (by id), request and pinned config, as replay reads them."""
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
    config = _config(config_root, request, extractors, vendor_pins=pinned.vendor_extractors)
    if expired := sorted(_expired(pool, manifest.inputs)):
        raise OriginalExpiredError(_EXPIRED.format(what=f"run {run_id}", captures=expired))
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
    return inputs, request, config


def load_results(run_id: int, *, pool: ConnectionPool) -> tuple[ResultRow, ...]:
    """A stored run's result rows, as published."""
    return RunStore(pool).read_results(run_id)


def run_status(rows: tuple[ResultRow, ...]) -> RunStatus:
    """``INCOMPLETE`` when the rows hold any ``operational_failures``."""
    return RunStatus.INCOMPLETE if operational_failures(rows) else RunStatus.COMPLETE


def operational_failures(rows: tuple[ResultRow, ...]) -> tuple[str, ...]:
    """Each distinct failure behind a non-diagnostic ``UNAVAILABLE`` state, in sorted order.

    A failure is the representation (a vendor's ``source/surface``), the reason that decided
    the state and the attempt that recorded it (``-`` when the state comes from the pins,
    e.g. nothing extracted under the pinned extractor). A vendor surface with no capture for
    the period (``NO_ATTEMPT``) is absence, not failure (spec §6.3). Non-empty exactly when
    the run is ``INCOMPLETE``.
    """
    return tuple(
        sorted(
            {
                _FAILURE.format(
                    representation=value.representation.value
                    if value.source_id is None
                    else f"{value.source_id}/{value.surface}",
                    reason=value.reason or NO_ATTEMPT,
                    attempt=NO_ATTEMPT if value.attempt_id is None else value.attempt_id,
                )
                for row in rows
                for value in row.source_values
                if value.source_role in _NON_DIAGNOSTIC
                and value.state is SourceState.UNAVAILABLE
                and not (value.source_id is not None and value.reason == NO_CAPTURE)
            }
        )
    )


def exit_status(record: RunRecord, overlay: QueueOverlay) -> RunExitStatus:
    """The CLI exit status of a published run: ``INCOMPLETE`` first, then whether the
    overlay holds an open ``HIGH`` item."""
    if record.manifest.status is RunStatus.INCOMPLETE:
        return RunExitStatus.INCOMPLETE
    if any(item.severity is QueueSeverity.HIGH for item in overlay.open_items):
        return RunExitStatus.SUCCESS_WITH_OPEN_HIGH
    return RunExitStatus.SUCCESS


def _expired(pool: ConnectionPool, inputs: tuple[RunInput, ...]) -> set[int]:
    """The input vendor captures that are not retained (R13)."""
    captures = [item.ref_id for item in inputs if item.kind is RunInputKind.CAPTURE_REF]
    with pool.connection() as conn:
        found = conn.execute("SELECT eqos.expired_vendor_captures(%s)", (captures,)).fetchone()
    return set(found[0] if found else ())


def _retained(inputs: ResolvedInputs, request: RunRequest, pool: ConnectionPool) -> ResolvedInputs:
    """Inputs without the vendor attempts and captures whose originals expired, refused when
    the latest applicable attempt of a key (as ``vendor_sides`` picks it) may read one (R13).
    An expired capture's occurrences are withheld, so it counts at every scope end."""
    if not (expired := _expired(pool, inputs.inputs)):
        return inputs
    ends = request.scope.period_ends
    evidenced = {(item.capture.capture_ref_id, item.valid_time) for item in inputs.occurrences}
    latest = {}
    drop: set[tuple[RunInputKind, int | None]] = {(RunInputKind.CAPTURE_REF, c) for c in expired}
    for attempt in sorted(inputs.attempts, key=lambda item: (item.attempted_at, item.attempt_id)):
        capture = attempt.capture and attempt.capture.capture_ref_id
        if capture in expired:
            drop.add((RunInputKind.ATTEMPT, attempt.attempt_id))
        if attempt.capture is None or attempt.capture.registered_at <= request.cutoff:
            served = (
                ends
                if capture in expired
                else (attempt.period_end, *(end for end in ends if (capture, end) in evidenced))
            )
            for end in served:
                key = (attempt.source_id, attempt.surface, attempt.entity_id, end, attempt.basis)
                latest[key] = capture
    if read := sorted(expired.intersection(latest.values())):
        raise OriginalExpiredError(_EXPIRED.format(what="the latest attempt", captures=read))
    kept = tuple(item for item in inputs.inputs if (item.kind, item.ref_id) not in drop)
    return inputs.model_copy(update={"inputs": kept})


def _config(
    config_root: Path,
    request: RunRequest,
    extractor_pins: Mapping[Representation, VersionPin] | None,
    *,
    vendor_pins: tuple[VendorExtractorPin, ...] | None = None,
) -> LoadedConfig:
    """The request's pinned artifacts, refused if any resolved content differs."""
    config = load_run_config(
        config_root,
        ConfigVersions.of(request.pinned),
        extractor_pins=_extractors(request.scope.family, extractor_pins),
        vendors=request.scope.vendors,
        vendor_pins=vendor_pins,
    )
    require_pins(config, request.pinned)
    return config


def _extractors(
    family: FilingFamily, pins: Mapping[Representation, VersionPin] | None
) -> Mapping[Representation, VersionPin] | None:
    """Explicit pins, else the shareholding family's own XBRL extractor (plan D8 R6)."""
    if pins is None and family is FilingFamily.SHAREHOLDING:
        return {Representation.XBRL: extractor_pin(Representation.XBRL, family=family)}
    return pins
