"""PostgreSQL publication and reads of runs, versions, inputs, results and pairs (D1a Task 9).

Publication is one transaction: the ``runs`` row is inserted on conflict of its identity
hash doing nothing, so a concurrent identical run waits on the first and then reads it back
(``created=False``); otherwise every child table follows and the transaction commits. A
failure anywhere before commit leaves no row of the run visible. Serialisation failures
retry at most three times, then fail loudly. Kept apart from ``EvidenceRepository`` because
run rows are the compare layer's contract and the repository is at its size limit.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Sequence
from datetime import date
from typing import Any, LiteralString

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from fundamentals.compare.definitions import definition_record_ids
from fundamentals.compare.run_models import (
    PairRecord,
    ResultRow,
    RunInput,
    RunInputDisposition,
    RunInputKind,
    RunManifest,
    SourceRef,
    SourceRole,
    SourceValue,
    row_id,
    sorted_inputs,
)
from fundamentals.compare.tables import TaggingAdjustment
from fundamentals.contracts.canonical import (
    ApplicabilityStatus,
    Basis,
    Representation,
    ValueIdentity,
    ValueKind,
)
from fundamentals.contracts.comparison import (
    CalculationState,
    CorroborationStatus,
    ExtractionStatus,
    PairKind,
    PairOutcome,
    ReasonCode,
    SourceState,
    Triage,
)
from fundamentals.contracts.evidence import (
    Interpretation,
    PinnedVersions,
    VendorExtractorPin,
    VersionPin,
)
from fundamentals.contracts.measurement_key import DimensionSet, MeasurementKey
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.evidence import repository_rows as rows_sql

MAX_PUBLISH_ATTEMPTS = 3
PublishHook = Callable[[str], None]

# Publication stages, in insert order; ``publish_hook`` is called with each after its insert.
STAGE_RUNS = "runs"
STAGE_VERSIONS = "run_versions"
STAGE_INPUTS = "run_inputs"
STAGE_RESULTS = "results"
STAGE_SOURCE_VALUES = "result_source_values"
STAGE_SURFACED = "result_surfaced_restatements"
STAGE_PAIRS = "pair_outcomes"
STAGE_ADJUSTMENTS = "pair_adjustments"

_INPUT_COLUMNS: tuple[RunInputKind, ...] = (
    RunInputKind.CAPTURE_REF,
    RunInputKind.PACKAGE,
    RunInputKind.OCCURRENCE,
    RunInputKind.INTERPRETATION,
    RunInputKind.ATTEMPT,
    RunInputKind.ALIGNMENT_PROOF,
    RunInputKind.CALCULATION_TRACE,
    RunInputKind.EVIDENCE_INPUT,
    RunInputKind.SETTINGS_RECORD,
    RunInputKind.BASIS_STATUS,
    RunInputKind.SEGMENT_MEMBER,
    RunInputKind.PACKAGE_STATEMENT,
    RunInputKind.DEFINITION_SET,
)
_PIN_NAMES = tuple(
    name
    for name in PinnedVersions.model_fields
    if name not in {"vendor_extractors", "source_authority"}
)
_UNREADABLE = "run {run_id} {detail}"
_NO_RECORD = "definition record {record_id!r} is not in the run's published set"
_EXHAUSTED = "run publication hit {count} serialisation failures"

_INSERT_RUN: LiteralString = (
    "INSERT INTO eqos.runs (identity_hash, cutoff, mode, status, code_version, manifest, "
    "manifest_sha256) VALUES (%s, %s, %s, %s, %s, %s, %s) "
    "ON CONFLICT (identity_hash) DO NOTHING RETURNING id"
)
_RUN_BY_HASH: LiteralString = "SELECT id FROM eqos.runs WHERE identity_hash = %s"
_RUN_BY_ID: LiteralString = (
    "SELECT id, identity_hash, manifest, manifest_sha256 FROM eqos.runs WHERE id = %s"
)
_LATEST_RUN: LiteralString = (
    "SELECT id FROM eqos.runs WHERE manifest @> %s ORDER BY created_at DESC, id DESC LIMIT 1"
)
_INSERT_VERSION: LiteralString = (
    "INSERT INTO eqos.run_versions (run_id, pin, version, content_sha256, source_id, surface) "
    "VALUES (%s, %s, %s, %s, %s, %s)"
)
_VERSIONS: LiteralString = (
    "SELECT pin, version, content_sha256, source_id, surface "
    "FROM eqos.run_versions WHERE run_id = %s"
)
_INSERT_INPUT: LiteralString = (
    "INSERT INTO eqos.run_inputs (run_id, input_kind, disposition, capture_ref_id, package_id, "
    "occurrence_id, interpretation_id, attempt_id, alignment_proof_id, calculation_trace_id, "
    "evidence_input_id, settings_record_id, basis_status_id, segment_member_id, "
    "package_statement_id, definition_set_id) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)
_INPUTS: LiteralString = (
    "SELECT input_kind, disposition, COALESCE(capture_ref_id, package_id, occurrence_id, "
    "interpretation_id, attempt_id, alignment_proof_id, calculation_trace_id, evidence_input_id, "
    "settings_record_id, basis_status_id, segment_member_id, package_statement_id, "
    "definition_set_id) AS ref_id FROM eqos.run_inputs WHERE run_id = %s"
)
_INSERT_RESULT: LiteralString = (
    "INSERT INTO eqos.results (run_id, entity_id, canonical_id, dictionary_version, "
    "period_start, period_end, period_instant, basis, framework, currency, value_kind, "
    "dimension_set, dimension_hash, key_digest, value_identity, applicability, "
    "applicability_rule_id, extraction_status, extraction_reason, corroboration_status, "
    "corroboration_reason) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
    "%s, %s, %s, %s, %s, %s, %s) RETURNING id"
)
_RESULTS: LiteralString = "SELECT * FROM eqos.results WHERE run_id = %s ORDER BY id"
_INSERT_VALUE: LiteralString = (
    "INSERT INTO eqos.result_source_values (result_id, source_role, representation, "
    "source_state, reason, value, lower, upper, interpretation_id, calculation_trace_id, "
    "attempt_id, calculation_state, source_id, surface) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
    "RETURNING id"
)
_VALUES: LiteralString = (
    "SELECT v.* FROM eqos.result_source_values v JOIN eqos.results r ON r.id = v.result_id "
    "WHERE r.run_id = %s ORDER BY v.id"
)
_INSERT_SURFACED: LiteralString = (
    "INSERT INTO eqos.result_surfaced_restatements (result_id, interpretation_id) VALUES (%s, %s)"
)
_SURFACED: LiteralString = (
    "SELECT s.result_id, s.interpretation_id FROM eqos.result_surfaced_restatements s "
    "JOIN eqos.results r ON r.id = s.result_id WHERE r.run_id = %s ORDER BY s.id"
)
_INSERT_PAIR: LiteralString = (
    "INSERT INTO eqos.pair_outcomes (result_id, pair_kind, left_value_id, right_value_id, "
    "outcome, reason, triage, difference, interval_gap, definition_record_id) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id"
)
_PAIRS: LiteralString = (
    "SELECT p.*, d.record_id FROM eqos.pair_outcomes p JOIN eqos.results r ON r.id = p.result_id "
    "LEFT JOIN eqos.definition_records d ON d.id = p.definition_record_id "
    "WHERE r.run_id = %s ORDER BY p.id"
)
_INSERT_ADJUSTMENT: LiteralString = (
    "INSERT INTO eqos.pair_adjustments (pair_outcome_id, definition_record_id, operand_name, "
    "representation, direction, amount) VALUES (%s, %s, %s, %s, %s, %s)"
)
_ADJUSTMENTS: LiteralString = (
    "SELECT a.pair_outcome_id, a.operand_name, a.representation, a.direction, a.amount, "
    "d.record_id, d.unit FROM eqos.pair_adjustments a "
    "JOIN eqos.definition_records d ON d.id = a.definition_record_id "
    "JOIN eqos.pair_outcomes p ON p.id = a.pair_outcome_id "
    "JOIN eqos.results r ON r.id = p.result_id WHERE r.run_id = %s ORDER BY a.id"
)
_BY_KEY_DIGESTS: LiteralString = (
    rows_sql.INTERPRETATION_COLUMNS + "WHERE i.key_digest = ANY(%s) ORDER BY i.id"
)
_PACKAGES_OF_CAPTURES: LiteralString = (
    "SELECT DISTINCT package_id FROM eqos.package_members WHERE capture_ref_id = ANY(%s) "
    "ORDER BY package_id"
)


class RunReadError(RuntimeError):
    """A stored run does not read back consistently (manifest, versions or inputs)."""


class PublishRetriesExhaustedError(RuntimeError):
    """Publication kept failing on serialisation; nothing of the run is visible."""


class RunStore:
    """Run-table publication and reads, plus the two current reads resolution needs."""

    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    # --- current reads (fresh resolution only; never reached from replay) -----------

    def interpretations_by_key_digests(self, digests: Sequence[str]) -> tuple[Interpretation, ...]:
        """Every interpretation keyed to one of the digests (comparative candidates)."""
        rows = self._fetch(_BY_KEY_DIGESTS, (list(digests),))
        return tuple(rows_sql.interpretation_of(row) for row in rows)

    def package_ids_of_captures(self, capture_ids: Sequence[int]) -> tuple[int, ...]:
        """Packages having any of the captures as a member."""
        return tuple(
            row["package_id"] for row in self._fetch(_PACKAGES_OF_CAPTURES, (list(capture_ids),))
        )

    # --- publication ----------------------------------------------------------------

    def publish(
        self,
        manifest: RunManifest,
        rows: Sequence[ResultRow],
        *,
        definition_set_id: int,
        publish_hook: PublishHook | None = None,
    ) -> tuple[int, bool]:
        """Publish a run atomically, or return the stored run of the same identity."""
        _validate_vendor_manifest(manifest, rows)
        for _ in range(MAX_PUBLISH_ATTEMPTS):
            try:
                return self._publish_once(manifest, rows, definition_set_id, publish_hook)
            except (psycopg.errors.SerializationFailure, psycopg.errors.DeadlockDetected):
                continue
        raise PublishRetriesExhaustedError(_EXHAUSTED.format(count=MAX_PUBLISH_ATTEMPTS))

    def _publish_once(
        self,
        manifest: RunManifest,
        rows: Sequence[ResultRow],
        definition_set_id: int,
        hook: PublishHook | None,
    ) -> tuple[int, bool]:
        """One publication transaction (see module docstring)."""
        identity = manifest.identity_hash()
        stage = hook or _no_hook
        with self._pool.connection() as conn, conn.transaction(), conn.cursor() as cursor:
            inserted = cursor.execute(
                _INSERT_RUN,
                (
                    identity,
                    manifest.cutoff,
                    manifest.mode.value,
                    manifest.status.value,
                    manifest.code_version,
                    Jsonb(manifest.stored_document()),
                    manifest.content_sha256(),
                ),
            ).fetchone()
            if inserted is None:
                existing = cursor.execute(_RUN_BY_HASH, (identity,)).fetchone()
                assert existing is not None
                return int(existing[0]), False
            run_id = int(inserted[0])
            stage(STAGE_RUNS)
            cursor.executemany(
                _INSERT_VERSION,
                _version_params(run_id, manifest.pinned),
            )
            stage(STAGE_VERSIONS)
            cursor.executemany(
                _INSERT_INPUT, [_input_params(run_id, item) for item in manifest.inputs]
            )
            stage(STAGE_INPUTS)
            result_ids = _returning(
                cursor, _INSERT_RESULT, [_result_params(run_id, r) for r in rows]
            )
            stage(STAGE_RESULTS)
            value_rows = [
                (result_id, value)
                for result_id, row in zip(result_ids, rows, strict=True)
                for value in row.source_values
            ]
            value_ids = _returning(
                cursor, _INSERT_VALUE, [_value_params(rid, value) for rid, value in value_rows]
            )
            stage(STAGE_SOURCE_VALUES)
            ids_of: dict[tuple[int, SourceRole, Representation, str | None, str | None], int] = {
                (
                    rid,
                    value.source_role,
                    value.representation,
                    value.source_id,
                    value.surface,
                ): value_id
                for (rid, value), value_id in zip(value_rows, value_ids, strict=True)
            }
            cursor.executemany(
                _INSERT_SURFACED,
                [
                    (result_id, interpretation_id)
                    for result_id, row in zip(result_ids, rows, strict=True)
                    for interpretation_id in row.surfaced_restatements
                ],
            )
            stage(STAGE_SURFACED)
            records = definition_record_ids(conn, definition_set_id)
            pair_rows = [
                (result_id, pair)
                for result_id, row in zip(result_ids, rows, strict=True)
                for pair in row.pairs
            ]
            pair_ids = _returning(
                cursor,
                _INSERT_PAIR,
                [_pair_params(rid, pair, ids_of, records) for rid, pair in pair_rows],
            )
            stage(STAGE_PAIRS)
            cursor.executemany(
                _INSERT_ADJUSTMENT,
                [
                    (
                        pair_id,
                        _record_id(records, adjustment.definition_record_id),
                        adjustment.operand_name,
                        adjustment.representation.value,
                        adjustment.direction,
                        adjustment.amount,
                    )
                    for pair_id, (_, pair) in zip(pair_ids, pair_rows, strict=True)
                    for adjustment in pair.adjustments
                ],
            )
            stage(STAGE_ADJUSTMENTS)
            return run_id, True

    # --- reads ----------------------------------------------------------------------

    def latest_run(self, entity_id: int, period_end: date, basis: Basis) -> int | None:
        """The latest stored run whose scope covers this entity, period end and basis."""
        scope = {
            "scope": {
                "entity_ids": [entity_id],
                "period_ends": [period_end.isoformat()],
                "bases": [basis.value],
            }
        }
        found = self._fetch(_LATEST_RUN, (Jsonb(scope),))
        return int(found[0]["id"]) if found else None

    def read_manifest(self, run_id: int) -> RunManifest:
        """A stored run's manifest with its inputs; integrity-checked against the run row."""
        found = self._fetch(_RUN_BY_ID, (run_id,))
        if not found:
            raise LookupError(_UNREADABLE.format(run_id=run_id, detail="is not stored"))
        stored = found[0]
        inputs = [
            RunInput(
                kind=RunInputKind(row["input_kind"]),
                ref_id=row["ref_id"],
                disposition=RunInputDisposition(row["disposition"]),
            )
            for row in self._fetch(_INPUTS, (run_id,))
        ]
        manifest = RunManifest.model_validate(
            {**stored["manifest"], "inputs": sorted_inputs(inputs)}
        )
        if manifest.content_sha256() != stored["manifest_sha256"]:
            raise RunReadError(_UNREADABLE.format(run_id=run_id, detail="manifest hash differs"))
        if manifest.identity_hash() != stored["identity_hash"]:
            raise RunReadError(_UNREADABLE.format(run_id=run_id, detail="identity hash differs"))
        if self.read_versions(run_id) != manifest.pinned:
            raise RunReadError(_UNREADABLE.format(run_id=run_id, detail="run_versions differ"))
        return manifest

    def read_versions(self, run_id: int) -> PinnedVersions:
        """A stored run's pinned versions from ``run_versions``."""
        records = self._fetch(_VERSIONS, (run_id,))
        pins: dict[str, Any] = {
            row["pin"]: VersionPin(version=row["version"], content_sha256=row["content_sha256"])
            for row in records
            if row["pin"] != "vendor_extractor"
        }
        pins["vendor_extractors"] = tuple(
            VendorExtractorPin(
                source_id=row["source_id"],
                surface=row["surface"],
                version=row["version"],
                content_sha256=row["content_sha256"],
            )
            for row in records
            if row["pin"] == "vendor_extractor"
        )
        return PinnedVersions.model_validate(pins)

    def read_results(self, run_id: int) -> tuple[ResultRow, ...]:
        """A stored run's result rows with source values, surfaced restatements and pairs."""
        manifest = self.read_manifest(run_id)
        legacy_sources = (
            not manifest.scope.vendor_sources
            and not manifest.pinned.vendor_extractors
            and manifest.pinned.source_authority is None
        )
        values: dict[int, list[tuple[int, SourceValue]]] = defaultdict(list)
        for row in self._fetch(_VALUES, (run_id,)):
            values[row["result_id"]].append((row["id"], _value_of(row, legacy=legacy_sources)))
        surfaced: dict[int, list[int]] = defaultdict(list)
        for row in self._fetch(_SURFACED, (run_id,)):
            surfaced[row["result_id"]].append(row["interpretation_id"])
        adjustments: dict[int, list[TaggingAdjustment]] = defaultdict(list)
        for row in self._fetch(_ADJUSTMENTS, (run_id,)):
            adjustments[row["pair_outcome_id"]].append(
                TaggingAdjustment(
                    operand_name=row["operand_name"],
                    representation=Representation(row["representation"]),
                    direction=row["direction"],
                    amount=row["amount"],
                    unit=ValueKind(row["unit"]),
                    definition_record_id=row["record_id"],
                )
            )
        refs = {
            value_id: SourceRef(
                source_role=value.source_role,
                representation=value.representation,
                source_id=value.source_id,
                surface=value.surface,
            )
            for items in values.values()
            for value_id, value in items
        }
        pairs: dict[int, list[PairRecord]] = defaultdict(list)
        for row in self._fetch(_PAIRS, (run_id,)):
            pairs[row["result_id"]].append(
                _pair_of(row, refs, tuple(adjustments.get(row["id"], ())))
            )
        results = [
            _result_of(
                row,
                values=tuple(value for _, value in values.get(row["id"], ())),
                pairs=tuple(pairs.get(row["id"], ())),
                surfaced=tuple(sorted(surfaced.get(row["id"], ()))),
            )
            for row in self._fetch(_RESULTS, (run_id,))
        ]
        return tuple(sorted(results, key=lambda item: item.row_id))

    def _fetch(self, query: LiteralString, params: tuple[object, ...]) -> list[dict[str, Any]]:
        """One parameterised read as column dicts."""
        with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()


def _no_hook(_: str) -> None:
    """The default publication hook: nothing."""


def _validate_vendor_manifest(manifest: RunManifest, rows: Sequence[ResultRow]) -> None:
    """Reject vendor values under a legacy request or unpinned vendor/authority identity."""
    requested = {(item.source_id, item.surface) for item in manifest.scope.vendor_sources}
    pinned = {(pin.source_id, pin.surface) for pin in manifest.pinned.vendor_extractors}
    if requested and (not requested <= pinned or manifest.pinned.source_authority is None):
        raise ValueError("requested vendor surfaces require extractor and source-authority pins")
    for row in rows:
        for value in row.source_values:
            if value.source_role in (SourceRole.INDEPENDENT_VENDOR, SourceRole.DIAGNOSTIC):
                if (value.source_id, value.surface) not in requested:
                    raise ValueError(
                        "vendor result side is outside the manifest's requested sources"
                    )


def _returning(
    cursor: psycopg.Cursor[Any], query: LiteralString, params: list[tuple[object, ...]]
) -> list[int]:
    """Insert many rows and return their ids in order."""
    if not params:
        return []
    cursor.executemany(query, params, returning=True)
    ids = []
    while True:
        found = cursor.fetchone()
        assert found is not None
        ids.append(int(found[0]))
        if not cursor.nextset():
            break
    return ids


def _input_params(run_id: int, item: RunInput) -> tuple[object, ...]:
    """One ``run_inputs`` row: the id in its kind's column, every other column null."""
    columns: list[object] = [None] * len(_INPUT_COLUMNS)
    columns[_INPUT_COLUMNS.index(item.kind)] = item.ref_id
    return (run_id, item.kind.value, item.disposition.value, *columns)


def _version_params(run_id: int, pinned: PinnedVersions) -> list[tuple[object, ...]]:
    """Persist first-party and source-qualified vendor pins without changing v1 documents."""
    rows: list[tuple[object, ...]] = [
        (run_id, name, pin.version, pin.content_sha256, None, None)
        for name in _PIN_NAMES
        for pin in (getattr(pinned, name),)
    ]
    rows.extend(
        (run_id, "vendor_extractor", pin.version, pin.content_sha256, pin.source_id, pin.surface)
        for pin in pinned.vendor_extractors
    )
    if pinned.source_authority is not None:
        pin = pinned.source_authority
        rows.append((run_id, "source_authority", pin.version, pin.content_sha256, None, None))
    return rows


def _result_params(run_id: int, row: ResultRow) -> tuple[object, ...]:
    """One ``results`` row."""
    key = row.key
    return (
        run_id,
        key.entity_id,
        key.canonical_id,
        row.dictionary_version,
        *rows_sql.period_params(key.period),
        key.basis.value,
        key.framework.value,
        key.currency,
        key.value_kind.value,
        Jsonb([list(pair) for pair in key.dimensions.pairs]),
        key.dimensions.digest(),
        key.digest(),
        row.value_identity.value,
        row.applicability.value,
        row.applicability_rule_id,
        row.extraction_status.value,
        _value(row.extraction_reason),
        row.corroboration_status.value,
        _value(row.corroboration_reason),
    )


def _value_params(result_id: int, value: SourceValue) -> tuple[object, ...]:
    """One ``result_source_values`` row."""
    return (
        result_id,
        value.source_role.value,
        value.representation.value,
        value.state.value,
        value.reason,
        value.value,
        value.lower,
        value.upper,
        value.interpretation_id,
        value.calculation_trace_id,
        value.attempt_id,
        _value(value.calculation_state),
        value.source_id,
        value.surface,
    )


def _pair_params(
    result_id: int,
    pair: PairRecord,
    ids_of: dict[tuple[int, SourceRole, Representation, str | None, str | None], int],
    records: dict[str, int],
) -> tuple[object, ...]:
    """One ``pair_outcomes`` row naming two source values of the same result."""
    left = ids_of[
        (
            result_id,
            pair.left.source_role,
            pair.left.representation,
            pair.left.source_id,
            pair.left.surface,
        )
    ]
    right = ids_of[
        (
            result_id,
            pair.right.source_role,
            pair.right.representation,
            pair.right.source_id,
            pair.right.surface,
        )
    ]
    record = (
        None
        if pair.definition_record_id is None
        else _record_id(records, pair.definition_record_id)
    )
    return (
        result_id,
        pair.pair_kind.value,
        left,
        right,
        pair.outcome.value,
        _value(pair.reason),
        _value(pair.triage),
        pair.difference,
        pair.interval_gap,
        record,
    )


def _record_id(records: dict[str, int], record_id: str) -> int:
    """A definition record's stored id; a record outside the pinned set fails loudly."""
    if record_id not in records:
        raise LookupError(_NO_RECORD.format(record_id=record_id))
    return records[record_id]


def _value(member: Any) -> str | None:
    """An optional enum's stored text."""
    return None if member is None else str(member.value)


def _value_of(row: dict[str, Any], *, legacy: bool = False) -> SourceValue:
    """A stored source value."""
    state = row["calculation_state"]
    first_party_legacy = legacy and row["source_role"] in (
        SourceRole.FIRST_PARTY.value,
        SourceRole.REPORTED_COUNTERPART.value,
    )
    return SourceValue(
        source_role=SourceRole(row["source_role"]),
        source_id=None if first_party_legacy else row["source_id"],
        surface=None if first_party_legacy else row["surface"],
        representation=Representation(row["representation"]),
        state=SourceState(row["source_state"]),
        reason=row["reason"],
        value=row["value"],
        lower=row["lower"],
        upper=row["upper"],
        interpretation_id=row["interpretation_id"],
        calculation_trace_id=row["calculation_trace_id"],
        attempt_id=row["attempt_id"],
        calculation_state=None if state is None else CalculationState(state),
    )


def _pair_of(
    row: dict[str, Any], refs: dict[int, SourceRef], adjustments: tuple[TaggingAdjustment, ...]
) -> PairRecord:
    """A stored pair outcome."""
    reason, triage = row["reason"], row["triage"]
    return PairRecord(
        pair_kind=PairKind(row["pair_kind"]),
        left=refs[row["left_value_id"]],
        right=refs[row["right_value_id"]],
        outcome=PairOutcome(row["outcome"]),
        reason=None if reason is None else ReasonCode(reason),
        triage=None if triage is None else Triage(triage),
        difference=row["difference"],
        interval_gap=row["interval_gap"],
        definition_record_id=row["record_id"],
        adjustments=adjustments,
    )


def _result_of(
    row: dict[str, Any],
    *,
    values: tuple[SourceValue, ...],
    pairs: tuple[PairRecord, ...],
    surfaced: tuple[int, ...],
) -> ResultRow:
    """A stored result row with its children."""
    period = rows_sql.period_of(row)
    assert period is not None
    key = MeasurementKey(
        entity_id=row["entity_id"],
        canonical_id=row["canonical_id"],
        period=period,
        basis=Basis(row["basis"]),
        framework=AccountingFramework(row["framework"]),
        currency=row["currency"],
        value_kind=ValueKind(row["value_kind"]),
        dimensions=DimensionSet(pairs=tuple(tuple(pair) for pair in row["dimension_set"])),
    )
    identity = ValueIdentity(row["value_identity"])
    extraction_reason, corroboration_reason = row["extraction_reason"], row["corroboration_reason"]
    return ResultRow(
        row_id=row_id(key, identity),
        key=key,
        dictionary_version=row["dictionary_version"],
        value_identity=identity,
        applicability=ApplicabilityStatus(row["applicability"]),
        applicability_rule_id=row["applicability_rule_id"],
        extraction_status=ExtractionStatus(row["extraction_status"]),
        extraction_reason=None if extraction_reason is None else ReasonCode(extraction_reason),
        corroboration_status=CorroborationStatus(row["corroboration_status"]),
        corroboration_reason=(
            None if corroboration_reason is None else ReasonCode(corroboration_reason)
        ),
        source_values=tuple(
            sorted(
                values,
                key=lambda item: (
                    item.source_role.value,
                    item.representation.value,
                    item.source_id or "",
                    item.surface or "",
                ),
            )
        ),
        pairs=pairs,
        surfaced_restatements=surfaced,
    )
