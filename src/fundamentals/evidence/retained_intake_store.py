"""Atomic normalized storage and complete by-evidence-ID witness reload."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, LiteralString

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from fundamentals.contracts.canonical import Representation
from fundamentals.contracts.evidence import AcquisitionAttempt, CaptureReference, FilingPackage
from fundamentals.evidence import repository_rows as sql_rows
from fundamentals.evidence.repository import EvidenceRepository, SettingsRecord
from fundamentals.evidence.retained_intake_models import (
    PreparedRetainedIntakeWitness,
    RetainedIntakeRequest,
    RetainedIntakeVersionPin,
    RetainedIntakeWitness,
    RetainedIntakeWitnessError,
    RetainedIntakeWitnessPayload,
)
from fundamentals.evidence.retained_intake_proof import (
    _associations,
    generation_document,
    generation_pin_projection,
    request_matches_attempt,
    require_member_generation_rows,
    require_payload_association,
    require_prepared_material,
)
from fundamentals.pg.identity_seed import EvidenceInputKind

if TYPE_CHECKING:
    from fundamentals.evidence.first_party_generation import FirstPartyGenerationHandoff
    from fundamentals.evidence.first_party_ingest import IngestReport
    from fundamentals.evidence.repository import EvidenceInputRecord

_HEADERS: LiteralString = (
    "SELECT w.*, e.kind, e.label, e.content_sha256 AS evidence_content_sha256, e.recorded_at, "
    "s.closure_sha256, s.binding_count, s.attempt_count, s.capture_count, s.pin_count, s.sealed_at "
    "FROM eqos.retained_intake_witnesses w "
    "JOIN eqos.evidence_inputs e ON e.id=w.evidence_input_id "
    "LEFT JOIN eqos.retained_intake_witness_seals s ON s.witness_id=w.id "
    "WHERE w.evidence_input_id=ANY(%s) ORDER BY w.evidence_input_id"
)
_PINS: LiteralString = (
    "SELECT id,artifact,version,content_sha256,pinned_at FROM eqos.version_pins "
    "WHERE artifact=ANY(%s) ORDER BY artifact"
)
_INSERT_HEADER: LiteralString = (
    "INSERT INTO eqos.retained_intake_witnesses (evidence_input_id,schema_version,issuer,quarter,"
    "manifest_body,manifest_sha256,manifest_size,manifest_label,issuer_config_body,"
    "issuer_config_sha256,issuer_config_size,issuer_config_label,selection_json,entity_id,family,"
    "period_end,basis,framework,package_id,package_evidence_sha256,settings_record_id,"
    "qualification_context_sha256,publication_version,publication_sha256,publication_state,"
    "canonical_payload,content_sha256) VALUES ("
    "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
    "RETURNING id"
)
_INSERT_BINDING: LiteralString = (
    "INSERT INTO eqos.retained_intake_witness_bindings (witness_id,representation,source_id,"
    "surface,relative_path,expected_input_sha256,request_key,filed_at_raw,knowledge_time,"
    "extractor_version,extractor_sha256,extraction_context_sha256,context_material) "
    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id"
)


class RetainedIntakeWitnessStore:
    """Use the repository's existing transaction seam; never take a nested pool connection."""

    def __init__(self, repository: EvidenceRepository) -> None:
        self.repository = repository

    def seal(
        self,
        prepared: PreparedRetainedIntakeWitness,
        *,
        handoff: FirstPartyGenerationHandoff,
        report: IngestReport,
    ) -> RetainedIntakeWitness:
        """Reload complete generation associations, then atomically write or reprove exact reuse."""
        require_prepared_material(prepared)
        payload = self._payload(prepared, handoff, report)
        with self.repository._transaction() as conn:
            _require_read_committed(conn)
            # Serialize content reuse before any witness DML. Header/child/seal SQL
            # independently locks the common evidence identity and refuses stale isolation.
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"retained-intake-content:{payload.content_sha256}",),
            )
            evidence = _rows(
                conn,
                "SELECT id,label,recorded_at FROM eqos.evidence_inputs "
                "WHERE kind='RETAINED_INTAKE' AND content_sha256=%s",
                (payload.content_sha256,),
            )
            if evidence:
                witness = _one(self._load(conn, [int(evidence[0]["id"])]), "existing witness")
                if witness.payload != payload:
                    raise RetainedIntakeWitnessError(
                        "same witness hash has a different full payload"
                    )
                return witness
            evidence_id = int(
                _one(
                    _rows(
                        conn,
                        "INSERT INTO eqos.evidence_inputs (kind,label,content_sha256) "
                        "VALUES ('RETAINED_INTAKE',%s,%s) RETURNING id",
                        (payload.label, payload.content_sha256),
                    ),
                    "new evidence input",
                )["id"]
            )
            witness_id = int(
                _one(
                    _rows(
                        conn,
                        _INSERT_HEADER,
                        (evidence_id, *_header_values(payload)),
                    ),
                    "new witness header",
                )["id"]
            )
            binding_ids: dict[Representation, int] = {}
            for request in prepared.requests:
                binding_ids[request.representation] = int(
                    _one(
                        _rows(
                            conn,
                            _INSERT_BINDING,
                            (witness_id, *_binding_values(request)),
                        ),
                        "new witness binding",
                    )["id"]
                )
            for association in payload.associations:
                binding_id = binding_ids[association.representation]
                for attempt_id in association.attempt_ids:
                    conn.execute(
                        "INSERT INTO eqos.retained_intake_witness_attempts "
                        "(witness_id,binding_id,attempt_id) VALUES (%s,%s,%s)",
                        (witness_id, binding_id, attempt_id),
                    )
                for disposition, ids in (
                    ("PACKAGE_MEMBER", association.package_capture_ids),
                    ("FAILED_PEER", association.failed_capture_ids),
                ):
                    for capture_id in ids:
                        conn.execute(
                            "INSERT INTO eqos.retained_intake_witness_captures "
                            "(witness_id,binding_id,capture_ref_id,disposition) "
                            "VALUES (%s,%s,%s,%s)",
                            (witness_id, binding_id, capture_id, disposition),
                        )
            for pin in payload.pins:
                conn.execute(
                    "INSERT INTO eqos.retained_intake_witness_pins "
                    "(witness_id,artifact,version_pin_id) VALUES (%s,%s,%s)",
                    (witness_id, pin.artifact, pin.id),
                )
            conn.execute(
                "INSERT INTO eqos.retained_intake_witness_seals "
                "(witness_id,closure_sha256,binding_count,attempt_count,capture_count,pin_count) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (
                    witness_id,
                    payload.closure_sha256,
                    len(prepared.requests),
                    len(payload.attempts),
                    len(payload.captures),
                    len(payload.pins),
                ),
            )
            witness = _one(self._load(conn, [evidence_id]), "new sealed witness")
            if witness.payload != payload:
                raise RetainedIntakeWitnessError(
                    "sealed witness differs from exact prepared payload"
                )
            return witness

    def get_by_evidence_ids(self, ids: Sequence[int]) -> tuple[RetainedIntakeWitness, ...]:
        """Reload exact evidence IDs; unsealed or malformed closure fails closed."""
        if not ids:
            return ()
        if any(type(item) is not int or item <= 0 for item in ids) or len(ids) != len(set(ids)):
            raise RetainedIntakeWitnessError(
                "witness evidence IDs must be positive and duplicate-free"
            )
        with self.repository._transaction() as conn:
            return self._load(conn, ids)

    def _get_for_transport(self, ids: Sequence[int]) -> tuple[RetainedIntakeWitness, ...]:
        """Load sealed material/normalized identities only; manifest guards own domain reproof."""
        if any(type(item) is not int or item <= 0 for item in ids) or len(ids) != len(set(ids)):
            raise RetainedIntakeWitnessError("transport evidence IDs must be exact and unique")
        with self.repository._transaction() as conn:
            return self._load(conn, ids, reprove_domain=False)

    def _payload(
        self,
        prepared: PreparedRetainedIntakeWitness,
        handoff: FirstPartyGenerationHandoff,
        report: IngestReport,
    ) -> RetainedIntakeWitnessPayload:
        if report.package_id != handoff.package_id or report.generation_context is None:
            raise RetainedIntakeWitnessError(
                "valid returned ingest generation is required for sealing"
            )
        attempts = self.repository.get_attempts(handoff.attempt_ids)
        if tuple(sorted(report.attempts, key=lambda row: _positive(row.attempt_id))) != attempts:
            raise RetainedIntakeWitnessError(
                "ingest report attempts do not match exact stored generation"
            )
        captures = self.repository.get_capture_refs(
            sorted(
                {
                    _positive(row.capture.capture_ref_id)
                    for row in attempts
                    if row.capture is not None
                }
            )
        )
        package = _one(self.repository.get_packages([handoff.package_id]), "stored package")
        settings = _one(
            self.repository.get_settings_records([handoff.fiscal_year_end_setting_id]),
            "stored settings",
        )
        from fundamentals.evidence.first_party_context import FirstPartyGenerationContext

        if report.generation_context != FirstPartyGenerationContext.from_record(settings):
            raise RetainedIntakeWitnessError("ingest context differs from handed settings identity")
        reported = {row.representation: row for row in report.members}
        if len(reported) != len(report.members) or set(reported) != {
            row.representation for row in handoff.members
        }:
            raise RetainedIntakeWitnessError("ingest report successful member projection differs")
        for member in handoff.members:
            item = reported[member.representation]
            if (
                item.capture_ref_id,
                item.source_id,
                item.surface,
                item.extractor_version,
                item.occurrence_ids,
                item.interpretation_ids,
            ) != (
                member.capture_ref_id,
                member.source_id,
                member.surface,
                member.extractor_pin.version,
                member.occurrence_ids,
                member.interpretation_ids,
            ):
                raise RetainedIntakeWitnessError("ingest report generation IDs differ from handoff")
        requests: dict[Representation, RetainedIntakeRequest] = {
            row.representation: row for row in prepared.requests
        }
        complete = tuple(
            row
            for row in self.repository.list_attempts(
                prepared.entity_id, prepared.reporting_period_end
            )
            if row.representation in requests
            and request_matches_attempt(requests[row.representation], prepared, row)
        )
        if {row.attempt_id for row in complete} != {row.attempt_id for row in attempts}:
            raise RetainedIntakeWitnessError(
                "complete original request attempt set differs from report"
            )
        expected_pins = generation_pin_projection(handoff)
        pins = tuple(
            RetainedIntakeVersionPin.model_validate(row)
            for row in self.repository._fetch(_PINS, (list(expected_pins),))
            if row["version"] == expected_pins[row["artifact"]].version
        )
        payload = RetainedIntakeWitnessPayload(
            prepared=prepared,
            package_id=handoff.package_id,
            package_evidence_sha256=handoff.package_evidence_sha256,
            settings_record_id=settings.id,
            qualification_context_sha256=handoff.qualification_context_sha256,
            publication_version=handoff.publication_version,
            publication_sha256=handoff.publication_sha256,
            publication_state=handoff.publication_state.value,
            generation_json=generation_document(handoff),
            attempts=attempts,
            captures=captures,
            pins=pins,
            associations=_associations(
                attempts,
                captures,
                {row.capture_ref_id: row.representation for row in handoff.members},
                requests,
            ),
        )
        require_payload_association(
            payload,
            package=package,
            settings=settings,
            captures=captures,
            attempts=attempts,
            pins=pins,
        )
        require_member_generation_rows(
            payload,
            occurrences=self.repository.get_occurrences(
                sorted({item for member in handoff.members for item in member.occurrence_ids})
            ),
            interpretations=self.repository.get_interpretations(
                sorted({item for member in handoff.members for item in member.interpretation_ids})
            ),
            context=report.generation_context,
        )
        return payload

    def _load(
        self, conn: psycopg.Connection[Any], ids: Sequence[int], *, reprove_domain: bool = True
    ) -> tuple[RetainedIntakeWitness, ...]:
        headers = _rows(conn, _HEADERS, (list(ids),))
        if tuple(row["evidence_input_id"] for row in headers) != tuple(sorted(ids)):
            raise RetainedIntakeWitnessError("witness evidence IDs do not reload exactly")
        result: list[RetainedIntakeWitness] = []
        for row in headers:
            try:
                payload = RetainedIntakeWitnessPayload.model_validate(row["canonical_payload"])
                if (
                    row["kind"] != EvidenceInputKind.RETAINED_INTAKE.value
                    or row["sealed_at"] is None
                ):
                    raise ValueError("evidence kind is wrong or witness is unsealed")
                if _header_values(payload, json_values=False) != tuple(
                    row[name] for name in _HEADER_FIELDS
                ):
                    raise ValueError(
                        "normalized witness header/material differs from canonical payload"
                    )
                require_prepared_material(payload.prepared)
                attempts, captures, pins = _reload_children(
                    conn, row["id"], payload, reprove_domain=reprove_domain
                )
                if pins != payload.pins:
                    raise ValueError("transported pin payload differs from normalized stored pins")
                settings = None
                if reprove_domain:
                    settings = SettingsRecord.model_validate(
                        _one(
                            _rows(
                                conn,
                                "SELECT * FROM eqos.settings_records WHERE id=%s",
                                (payload.settings_record_id,),
                            ),
                            "witness settings",
                        )
                    )
                    package = _package(conn, payload.package_id)
                    require_payload_association(
                        payload,
                        package=package,
                        settings=settings,
                        captures=captures,
                        attempts=attempts,
                        pins=pins,
                    )
                    from fundamentals.evidence.first_party_context import (
                        FirstPartyGenerationContext,
                    )
                    from fundamentals.evidence.first_party_generation import (
                        FirstPartyGenerationHandoff,
                    )

                    generation = FirstPartyGenerationHandoff.model_validate_json(
                        payload.generation_json
                    )
                    require_member_generation_rows(
                        payload,
                        occurrences=tuple(
                            sql_rows.occurrence_of(item)
                            for item in _rows(
                                conn,
                                sql_rows.OCCURRENCES_BY_ID,
                                (
                                    [
                                        item
                                        for member in generation.members
                                        for item in member.occurrence_ids
                                    ],
                                ),
                            )
                        ),
                        interpretations=tuple(
                            sql_rows.interpretation_of(item)
                            for item in _rows(
                                conn,
                                sql_rows.INTERPRETATIONS_BY_ID,
                                (
                                    [
                                        item
                                        for member in generation.members
                                        for item in member.interpretation_ids
                                    ],
                                ),
                            )
                        ),
                        context=FirstPartyGenerationContext.from_record(settings),
                    )
                expected_counts = (
                    len(payload.prepared.requests),
                    len(attempts),
                    len(captures),
                    len(pins),
                )
                if expected_counts != tuple(
                    row[name]
                    for name in ("binding_count", "attempt_count", "capture_count", "pin_count")
                ):
                    raise ValueError("sealed witness counts differ from normalized closure")
                witness = RetainedIntakeWitness(
                    evidence_input_id=row["evidence_input_id"],
                    label=row["label"],
                    content_sha256=row["evidence_content_sha256"],
                    recorded_at=row["recorded_at"],
                    sealed_at=row["sealed_at"],
                    closure_sha256=row["closure_sha256"],
                    payload=payload,
                )
                clocks = [pin.pinned_at for pin in pins]
                if settings is not None:
                    clocks.append(settings.recorded_at)
                clocks.extend(row.attempted_at for row in attempts if row.attempted_at is not None)
                clocks.extend(capture.registered_at for capture in captures)
                clocks.extend(capture.first_seen_at for capture in captures)
                store_clock = _one(
                    _rows(conn, "SELECT eqos.store_now() AS clock", ()), "store clock"
                )["clock"]
                if (
                    any(clock > witness.recorded_at for clock in clocks)
                    or witness.sealed_at > store_clock
                ):
                    raise ValueError("witness or associated database clocks contradict store time")
                result.append(witness)
            except (ValueError, TypeError, KeyError) as exc:
                raise RetainedIntakeWitnessError(f"witness by-ID reload refused: {exc}") from exc
        return tuple(result)


_HEADER_FIELDS = (
    "schema_version",
    "issuer",
    "quarter",
    "manifest_body",
    "manifest_sha256",
    "manifest_size",
    "manifest_label",
    "issuer_config_body",
    "issuer_config_sha256",
    "issuer_config_size",
    "issuer_config_label",
    "selection_json",
    "entity_id",
    "family",
    "period_end",
    "basis",
    "framework",
    "package_id",
    "package_evidence_sha256",
    "settings_record_id",
    "qualification_context_sha256",
    "publication_version",
    "publication_sha256",
    "publication_state",
    "canonical_payload",
    "content_sha256",
)


def _header_values(
    payload: RetainedIntakeWitnessPayload, *, json_values: bool = True
) -> tuple[object, ...]:
    prepared = payload.prepared
    selection = [row.model_dump(mode="json") for row in prepared.selection]
    document = payload.model_dump(mode="json")
    return (
        prepared.schema_version,
        prepared.issuer,
        prepared.quarter,
        prepared.manifest.body,
        prepared.manifest.sha256,
        prepared.manifest.size,
        prepared.manifest.label,
        prepared.issuer_config.body,
        prepared.issuer_config.sha256,
        prepared.issuer_config.size,
        prepared.issuer_config.label,
        Jsonb(selection) if json_values else selection,
        prepared.entity_id,
        prepared.family.value,
        prepared.reporting_period_end,
        prepared.basis.value,
        prepared.framework.value,
        payload.package_id,
        payload.package_evidence_sha256,
        payload.settings_record_id,
        payload.qualification_context_sha256,
        payload.publication_version,
        payload.publication_sha256,
        payload.publication_state,
        Jsonb(document) if json_values else document,
        payload.content_sha256,
    )


def _binding_values(
    request: RetainedIntakeRequest, *, json_values: bool = True
) -> tuple[object, ...]:
    context = json.loads(request.context_material_json)
    return (
        request.representation.value,
        request.source_id,
        request.surface,
        request.relative_path,
        request.expected_input_sha256,
        request.request_key,
        request.filed_at_raw,
        request.knowledge_time,
        request.extractor_pin.version,
        request.extractor_pin.content_sha256,
        request.extraction_context_sha256,
        Jsonb(context) if json_values else context,
    )


def _reload_children(
    conn: psycopg.Connection[Any],
    witness_id: int,
    payload: RetainedIntakeWitnessPayload,
    *,
    reprove_domain: bool,
) -> tuple[
    tuple[AcquisitionAttempt, ...],
    tuple[CaptureReference, ...],
    tuple[RetainedIntakeVersionPin, ...],
]:
    bindings = _rows(
        conn,
        "SELECT * FROM eqos.retained_intake_witness_bindings "
        "WHERE witness_id=%s ORDER BY representation",
        (witness_id,),
    )
    columns = (
        "representation",
        "source_id",
        "surface",
        "relative_path",
        "expected_input_sha256",
        "request_key",
        "filed_at_raw",
        "knowledge_time",
        "extractor_version",
        "extractor_sha256",
        "extraction_context_sha256",
        "context_material",
    )
    if tuple(tuple(row[name] for name in columns) for row in bindings) != tuple(
        _binding_values(request, json_values=False) for request in payload.prepared.requests
    ):
        raise ValueError("normalized bindings differ from source-derived exact requests")
    representations = {row["id"]: row["representation"] for row in bindings}
    attempt_links = _rows(
        conn,
        "SELECT * FROM eqos.retained_intake_witness_attempts "
        "WHERE witness_id=%s ORDER BY attempt_id",
        (witness_id,),
    )
    capture_links = _rows(
        conn,
        "SELECT * FROM eqos.retained_intake_witness_captures "
        "WHERE witness_id=%s ORDER BY capture_ref_id",
        (witness_id,),
    )
    pin_links = _rows(
        conn,
        "SELECT p.artifact,p.version_pin_id,v.id,v.version,v.content_sha256,v.pinned_at, "
        "v.artifact AS stored_artifact "
        "FROM eqos.retained_intake_witness_pins p "
        "JOIN eqos.version_pins v ON v.id=p.version_pin_id "
        "WHERE p.witness_id=%s ORDER BY p.artifact",
        (witness_id,),
    )
    expected_attempts = sorted(
        (item, association.representation.value)
        for association in payload.associations
        for item in association.attempt_ids
    )
    expected_captures = sorted(
        (item, association.representation.value, disposition)
        for association in payload.associations
        for disposition, ids in (
            ("PACKAGE_MEMBER", association.package_capture_ids),
            ("FAILED_PEER", association.failed_capture_ids),
        )
        for item in ids
    )
    if [
        (row["attempt_id"], representations.get(row["binding_id"])) for row in attempt_links
    ] != expected_attempts:
        raise ValueError("normalized attempt/request closure differs")
    if [
        (row["capture_ref_id"], representations.get(row["binding_id"]), row["disposition"])
        for row in capture_links
    ] != expected_captures:
        raise ValueError("normalized capture/request/disposition closure differs")
    if [(row["artifact"], row["version_pin_id"]) for row in pin_links] != [
        (pin.artifact, pin.id) for pin in payload.pins
    ]:
        raise ValueError("normalized pin association differs")
    if any(row["artifact"] != row["stored_artifact"] for row in pin_links):
        raise ValueError("normalized pin artifact differs from exact stored pin row")
    attempts = (
        tuple(
            sql_rows.attempt_of(row)
            for row in _rows(
                conn,
                sql_rows.ATTEMPTS_BY_ID,
                ([row["attempt_id"] for row in attempt_links],),
            )
        )
        if reprove_domain
        else payload.attempts
    )
    captures = (
        tuple(
            sql_rows.capture_of(row)
            for row in _rows(
                conn,
                sql_rows.CAPTURE_REFS_BY_ID,
                ([row["capture_ref_id"] for row in capture_links],),
            )
        )
        if reprove_domain
        else payload.captures
    )
    pins = tuple(
        RetainedIntakeVersionPin.model_validate(
            {
                name: row[name]
                for name in ("id", "artifact", "version", "content_sha256", "pinned_at")
            }
        )
        for row in pin_links
    )
    return attempts, captures, pins


def _package(conn: psycopg.Connection[Any], package_id: int) -> FilingPackage:
    row = _one(_rows(conn, sql_rows.PACKAGES_BY_ID, ([package_id],)), "witness package")
    members = _rows(conn, sql_rows.MEMBERS_OF_PACKAGES, ([package_id],))
    statements = [
        sql_rows.PackageStatementRecord.model_validate(item)
        for item in _rows(
            conn,
            sql_rows.STATEMENTS_OF_PACKAGES,
            ([package_id],),
        )
    ]
    return sql_rows.package_of(row, members, statements)


def _require_read_committed(conn: psycopg.Connection[Any]) -> None:
    if (
        _rows(conn, "SHOW transaction_isolation", ())[0]["transaction_isolation"]
        != "read committed"
    ):
        raise RetainedIntakeWitnessError("retained witness writes require READ COMMITTED")


def _rows(
    conn: psycopg.Connection[Any], query: LiteralString, params: tuple[object, ...]
) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query, params)
        return cursor.fetchall()


def _one[T](rows: Sequence[T], label: str) -> T:
    if len(rows) != 1:
        raise RetainedIntakeWitnessError(f"expected exactly one {label}")
    return rows[0]


def _positive(value: int | None) -> int:
    if type(value) is not int or value <= 0:
        raise RetainedIntakeWitnessError("witness requires exact positive stored IDs")
    return value


def enrich_retained_intake_evidence_inputs(
    repository: EvidenceRepository, records: tuple[EvidenceInputRecord, ...]
) -> tuple[EvidenceInputRecord, ...]:
    """Existing kinds take no witness query; only exactly returned new-kind IDs are enriched."""
    ids = [row.id for row in records if row.kind is EvidenceInputKind.RETAINED_INTAKE]
    if not ids:
        return records
    witnesses = {
        row.evidence_input_id: row
        for row in RetainedIntakeWitnessStore(repository)._get_for_transport(ids)
    }
    return tuple(
        row.model_copy(update={"retained_intake_witness": witnesses[row.id]})
        if row.kind is EvidenceInputKind.RETAINED_INTAKE
        else row
        for row in records
    )
