"""Citation resolution: what a claim's cited record says, if it has authority (plan D8, D9).

``resolve_citation`` returns ``None`` (row 1, ``UNRESOLVED``) unless the cited record exists
and has authority: ``FIGURE`` and ``CALCULATION`` only first-party values (every capture
behind them; an interpretation ``FIGURE`` with no run its own mapped value), a quote only a
non-vendor capture, a ``COMPARISON`` its own run and key, a
``POLICY`` an owner ``SET_POLICY`` decision on a report of the same entity, and a declared
``source_sha256`` only the cited fact's file or capture's blob. A capture's
first-seen time is the earlier of its registration and its blob's legacy acquisitions (D8).
A drafted quote's guidance contract is the one a sealed import binds to the same quote
(``bound_contract``, plan D4 M9).
Run-store values (cells, pair differences, traces) are base units, stated in the claim's
scale (``scale`` 10^7 for crore); display never rescales.
"""

from __future__ import annotations

import json
import re
import tempfile
from collections.abc import Iterable, Mapping
from datetime import datetime
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import Any, LiteralString

import pymupdf
from psycopg import Cursor
from psycopg.rows import dict_row
from pydantic import BaseModel, ConfigDict

from fundamentals.canon.role_translation import translate
from fundamentals.compare.queue import overlay_at
from fundamentals.compare.trust import trusted
from fundamentals.contracts.canonical import Basis, ValueKind
from fundamentals.contracts.comparison import CorroborationStatus, ExtractionStatus, SourceState
from fundamentals.contracts.fact import Fact
from fundamentals.contracts.ledger import (
    Citation,
    CitationKind,
    GuidanceContract,
    InputTime,
    NumericClaim,
    ResolvedCitation,
)
from fundamentals.contracts.measurement_key import DimensionSet, MeasurementKey
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.contracts.source_catalog import SourceCatalog, SourceClass, UnknownSourceError
from fundamentals.entity.identity_layers import issuer_values
from fundamentals.evidence.capture_retention import retained_capture
from fundamentals.evidence.repository_rows import capture_of, period_of
from fundamentals.ingest.pdf_source import PdfIntegrityError, load_pdf
from fundamentals.ledger.import_mapping import UPDATE_FILES, ledger_contracts
from fundamentals.reconcile.fact_view import CANONICAL_ENTITY_SCHEME
from fundamentals.store.pg_fact_store import NATIVE_ORIGIN
from fundamentals.store.snapshot_store import SnapshotStore
from fundamentals.verify.quote_anchor import (
    SourceDocument,
    source_document,
    verify_quote_anchor,
)

ANCHOR = re.compile(r"p(\d+)\.b(\d+)\.(\d+:\d+)")
PDF_MAGIC = b"%PDF-"
_FIRST_SEEN: LiteralString = """least(c.first_seen_at, (SELECT min(a.retrieved_at)
    FROM eqos.legacy_acquisitions a WHERE a.blob_sha256 = c.blob_sha256))"""
_CAPTURE: LiteralString = (
    "SELECT c.*, " + _FIRST_SEEN + " AS first_seen FROM eqos.capture_refs c WHERE c.id = %s"
)
_FACT: LiteralString = """SELECT f.knowledge_time, f.fact_json, f.file_sha256 AS fact_file,
    f.created_at, t.*, b.capture_ref_id, s.selected_at, s.recorded_at AS selection_recorded_at
FROM eqos.fact_rows f
LEFT JOIN LATERAL (SELECT min(selected_at) AS selected_at, min(recorded_at) AS recorded_at
    FROM eqos.fact_selections WHERE target_store = f.target_store AND row_handle = f.handle) s
    ON true
LEFT JOIN eqos.legacy_fact_translations t
    ON t.target_store = f.target_store AND t.row_handle = f.handle
LEFT JOIN eqos.legacy_evidence_bindings b
    ON b.target_store = f.target_store AND b.row_handle = f.handle
WHERE f.origin = %s AND f.origin_id = %s"""
# A native fact's captures: every capture of its file, earliest first-seen first.
_FILE_CAPTURES: LiteralString = (
    "SELECT c.*, " + _FIRST_SEEN + " AS first_seen FROM eqos.capture_refs c "
    "WHERE c.blob_sha256 = %s ORDER BY first_seen, c.id"
)
_RUN_CELL: LiteralString = """SELECT r.key_digest, r.value_kind, r.currency, run.created_at,
    r.extraction_status, r.corroboration_status, EXISTS (SELECT 1 FROM eqos.result_source_values f
    WHERE f.result_id = r.id AND f.source_role = 'FIRST_PARTY' AND f.source_state = 'VALUE')
    AS first_party_value, """
_CELL: LiteralString = (
    _RUN_CELL
    + """v.value FROM eqos.result_source_values v
JOIN eqos.results r ON r.id = v.result_id JOIN eqos.runs run ON run.id = r.run_id
WHERE v.interpretation_id = %s AND v.source_state = 'VALUE' AND r.run_id = %s
    AND r.key_digest = %s"""
)
_COMPARISON: LiteralString = (
    _RUN_CELL
    + """p.difference AS value FROM eqos.pair_outcomes p
JOIN eqos.results r ON r.id = p.result_id JOIN eqos.runs run ON run.id = r.run_id
WHERE p.id = %s AND r.run_id = %s AND r.key_digest = %s"""
)
# The cited fact's file, or the cited interpretation's or quote's capture blob.
_SOURCE: LiteralString = """SELECT coalesce(
    (SELECT file_sha256 FROM eqos.fact_rows WHERE origin = %s AND origin_id = %s),
    (SELECT c.blob_sha256 FROM eqos.interpretations i
     JOIN eqos.capture_refs c ON c.id = i.capture_ref_id WHERE i.id = %s),
    (SELECT blob_sha256 FROM eqos.capture_refs WHERE id = %s)) AS sha256"""
_INTERPRETATION: LiteralString = """SELECT value, key_digest, value_kind, currency
FROM eqos.interpretations WHERE id = %s AND status = 'MAPPED' AND entity_id = %s"""
_TRACE: LiteralString = (
    "SELECT value, key_digest FROM eqos.calculation_traces WHERE id = %s AND state = 'COMPUTED'"
)
_POLICY: LiteralString = """SELECT d.policy_value, d.policy_unit, d.recorded_at
FROM eqos.decisions d JOIN eqos.reports r ON r.id = d.subject_id
WHERE d.id = %s AND d.subject_kind = 'REPORT' AND d.kind = 'SET_POLICY'
    AND d.decider = 'OWNER' AND r.entity_id = %s"""
# Every interpretation behind the cited traces and interpretations, through trace operands,
# nested traces and constructed interpretations' operands.
_INPUTS: LiteralString = (
    """WITH RECURSIVE traces(id) AS (
    SELECT unnest(%(traces)s::bigint[])
    UNION SELECT o.operand_trace_id FROM eqos.calculation_trace_operands o
        JOIN traces t ON o.calculation_trace_id = t.id WHERE o.operand_trace_id IS NOT NULL
), interps(id) AS (
    SELECT unnest(%(interpretations)s::bigint[])
    UNION SELECT o.interpretation_id FROM eqos.calculation_trace_operands o
        JOIN traces t ON o.calculation_trace_id = t.id WHERE o.interpretation_id IS NOT NULL
    UNION SELECT o.operand_interpretation_id FROM eqos.interpretation_operands o
        JOIN interps i ON o.interpretation_id = i.id
)
SELECT c.source_id, i.recorded_at, i.occurrence_id, oc.knowledge_time,
    oc.first_seen_at AS occurrence_first_seen, """
    + _FIRST_SEEN
    + """ AS first_seen
FROM interps x JOIN eqos.interpretations i ON i.id = x.id
JOIN eqos.capture_refs c ON c.id = i.capture_ref_id
LEFT JOIN eqos.occurrences oc ON oc.id = i.occurrence_id"""
)
# M9: the imported quote claims of the entity at the drafted quote's location, with every import
# source of their versions; only a version its panel IMPORT_SEAL sealed as it stands counts.
_IMPORTED_QUOTES: LiteralString = """SELECT c.id, c.claim_key, i.source_path, i.sha256, i.body
FROM eqos.numeric_claims c
JOIN eqos.report_versions v ON v.id = c.version_id
JOIN eqos.reports r ON r.id = v.report_id
JOIN eqos.import_sources i ON i.version_id = v.id
WHERE r.entity_id = %(entity)s AND c.citation_kind = 'SOURCE_QUOTE' AND c.quote = %(quote)s
    AND eqos.quote_location(c.source_sha256, c.anchor)
        = eqos.quote_location(%(capture)s::bigint, %(anchor)s)
    AND EXISTS (SELECT 1 FROM eqos.decisions d
                WHERE d.subject_kind = 'REPORT_VERSION' AND d.subject_id = v.id
                  AND d.kind = 'IMPORT_SEAL' AND d.decider = 'PANEL'
                  AND d.sealed_digest = eqos.version_sealed_digest(v.id))
ORDER BY c.id, i.id"""

_Row = Mapping[str, Any]
_Times = tuple[tuple[InputTime, datetime | None], ...]


class ContractBinding(BaseModel):
    """One sealed import's guidance contract for a quote: its claim and management-ledger
    source; ``contract`` is ``None`` when that ledger has no entry at the claim's key."""

    model_config = ConfigDict(frozen=True)

    claim_id: int
    source_sha256: str
    contract: GuidanceContract | None


class _Located(BaseModel):
    """A capture span in the shape the quote-anchor verifier reads."""

    model_config = ConfigDict(frozen=True)

    provenance: Provenance


def resolve_citation(
    cursor: Cursor[Any],
    claim: NumericClaim,
    *,
    entity_id: int,
    overlay_position: datetime,
    catalog: SourceCatalog,
    snapshots: SnapshotStore,
) -> ResolvedCitation | None:
    """What the claim's citation resolves to at ``overlay_position``, or ``None``.

    ``entity_id`` is the stock of the claim's report, which a ``POLICY`` decision must share.
    """
    citation = claim.citation
    with cursor.connection.cursor(row_factory=dict_row) as own:
        if citation.source_sha256 is not None and citation.source_sha256 != _source(own, citation):
            return None
        if citation.kind is CitationKind.FIGURE and citation.fact_origin_id is not None:
            return _fact(own, citation.fact_origin, citation.fact_origin_id, entity_id, catalog)
        if citation.kind is CitationKind.FIGURE and citation.interpretation_id is not None:
            times = _input_times(own, (), (citation.interpretation_id,), catalog)
            if times is None:
                return None
            if citation.run_id is None:
                return _interpretation(own, citation.interpretation_id, claim, entity_id, times)
            return _run_cell(own, _CELL, citation.interpretation_id, claim, overlay_position, times)
        if citation.kind is CitationKind.CALCULATION and citation.calculation_trace_id is not None:
            return _trace(own, citation.calculation_trace_id, claim, entity_id, catalog)
        if citation.kind is CitationKind.SOURCE_QUOTE and citation.capture_ref_id is not None:
            capture = _first_party_capture(own, citation.capture_ref_id, catalog)
            if capture is None:
                return None
            return ResolvedCitation(
                times=((InputTime.FIRST_SEEN, capture["first_seen"]),),
                quote_text=_span(own, capture, citation.anchor or "", snapshots),
            )
        if citation.kind is CitationKind.COMPARISON:
            return _run_cell(own, _COMPARISON, citation.pair_outcome_id, claim, overlay_position)
        if citation.kind is CitationKind.POLICY:
            return _policy(own, claim, entity_id)
    return None


def contract_bindings(
    cursor: Cursor[Any], claim: NumericClaim, entity_id: int
) -> tuple[ContractBinding, ...]:
    """What each sealed import of ``entity_id`` quoting the claim's capture location and quote
    binds, from its management-ledger source (plan D4, M9)."""
    citation = claim.citation
    if citation.kind is not CitationKind.SOURCE_QUOTE or citation.capture_ref_id is None:
        return ()
    params = {
        "entity": entity_id,
        "quote": citation.quote,
        "capture": citation.capture_ref_id,
        "anchor": citation.anchor,
    }
    with cursor.connection.cursor(row_factory=dict_row) as own:
        rows = own.execute(_IMPORTED_QUOTES, params).fetchall()
    return tuple(
        ContractBinding(
            claim_id=row["id"],
            source_sha256=row["sha256"],
            contract=ledger_contracts(bytes(row["body"])).get(row["claim_key"]),
        )
        for row in rows
        if PurePosixPath(row["source_path"]).name not in UPDATE_FILES
    )


def bound_contract(
    cursor: Cursor[Any], claim: NumericClaim, entity_id: int
) -> GuidanceContract | None:
    """The one guidance contract the sealed imports bind to the quote claim; none or several
    distinct bind nothing (fail closed)."""
    contracts = {binding.contract for binding in contract_bindings(cursor, claim, entity_id)}
    return contracts.pop() if len(contracts) == 1 else None


def resolve_location(
    cursor: Cursor[Any],
    capture_id: str,
    anchor: str,
    *,
    catalog: SourceCatalog,
    snapshots: SnapshotStore,
) -> bool:
    """Whether ``{{s:<capture id>|<anchor>}}`` names a non-empty span of a non-vendor capture."""
    if not capture_id.isdigit():
        return False
    with cursor.connection.cursor(row_factory=dict_row) as own:
        capture = _first_party_capture(own, int(capture_id), catalog)
        span = None if capture is None else _span(own, capture, anchor, snapshots)
    return span is not None and span.strip() != ""


def _first_party(source_id: str, catalog: SourceCatalog) -> bool:
    """Whether the catalog declares ``source_id`` first-party (undeclared: no)."""
    try:
        return catalog.classify(source_id) is SourceClass.FIRST_PARTY
    except UnknownSourceError:
        return False


def _first_party_capture(
    own: Cursor[Any], capture_ref_id: int, catalog: SourceCatalog
) -> _Row | None:
    """The capture row with its D8 first-seen time, if it exists and is first-party."""
    row = own.execute(_CAPTURE, (capture_ref_id,)).fetchone()
    return row if row is not None and _first_party(row["source_id"], catalog) else None


def _source(own: Cursor[Any], citation: Citation) -> str | None:
    """The SHA-256 of the file or capture the citation names, if it names one."""
    fields = ("fact_origin", "fact_origin_id", "interpretation_id", "capture_ref_id")
    row = own.execute(_SOURCE, tuple(getattr(citation, name) for name in fields)).fetchone()
    assert row is not None
    sha256: str | None = row["sha256"]
    return sha256


def _fact(
    own: Cursor[Any], origin: str | None, origin_id: int, entity_id: int, catalog: SourceCatalog
) -> ResolvedCitation | None:
    """A legacy fact, through its translation and its bound capture; or a native (run-written)
    fact of the report's issuer, through ``translate`` and its file's first-party capture, also
    held to its row's and first selection's store-clock recording times."""
    row = own.execute(_FACT, (origin, origin_id)).fetchone()
    if row is None:
        return None
    recorded: _Times = ()
    if origin == NATIVE_ORIGIN:
        key, capture = _native_key(own, row, entity_id), _file_capture(own, row, catalog)
        recorded = (
            (InputTime.RECORDED, _instant(row["created_at"])),
            (InputTime.RECORDED, row["selection_recorded_at"]),
        )
    else:
        key, capture = _legacy_key(row), _first_party_capture(own, row["capture_ref_id"], catalog)
    if capture is None or key is None:
        return None
    observation = json.loads(row["fact_json"], parse_float=Decimal)["observation"]
    return ResolvedCitation(
        value=Decimal(str(observation["normalized_value"])),
        key_digest=key.digest(),
        value_kind=key.value_kind,
        unit=observation["normalized_unit"],
        currency=observation["currency"],
        scale=observation["scale"],
        times=(
            (InputTime.KNOWLEDGE, _instant(row["knowledge_time"])),
            (InputTime.FIRST_SEEN, capture["first_seen"]),
            (InputTime.SELECTED, _instant(row["selected_at"])),
            *recorded,
        ),
    )


def _legacy_key(row: _Row) -> MeasurementKey | None:
    """A legacy fact's stored translation, if it has one."""
    period = None if row["canonical_id"] is None else period_of(row)
    if period is None:
        return None
    return MeasurementKey(
        entity_id=row["entity_id"],
        canonical_id=row["canonical_id"],
        period=period,
        basis=Basis(row["basis"]),
        framework=AccountingFramework(row["framework"]),
        currency=row["currency"],
        value_kind=ValueKind(row["value_kind"]),
        dimensions=DimensionSet(pairs=tuple(tuple(pair) for pair in row["dimension_set"])),
    )


def _native_key(own: Cursor[Any], row: _Row, entity_id: int) -> MeasurementKey | None:
    """A native fact's key, only when its observation names the entity's NSE symbol."""
    fact = Fact.model_validate_json(row["fact_json"])
    _, symbol, _ = issuer_values(own.connection, entity_id)
    issuer = (fact.observation.entity_scheme, fact.observation.entity_id)
    if issuer != (CANONICAL_ENTITY_SCHEME, symbol.value):
        return None
    return translate(fact, entity_id=entity_id)


def _file_capture(own: Cursor[Any], row: _Row, catalog: SourceCatalog) -> _Row | None:
    """The earliest-seen first-party capture of a native fact's file, if any."""
    captures = own.execute(_FILE_CAPTURES, (row["fact_file"],)).fetchall()
    return next((c for c in captures if _first_party(c["source_id"], catalog)), None)


def _interpretation(
    own: Cursor[Any], interpretation_id: int, claim: NumericClaim, entity_id: int, times: _Times
) -> ResolvedCitation | None:
    """A mapped first-party interpretation of the report's issuer, under a claim key of that
    issuer: its own value and key, with no run (a comparator figure or a filed operand of a
    run's computed value)."""
    key = claim.measurement_key
    if key is None or key.entity_id != entity_id:
        return None
    row = own.execute(_INTERPRETATION, (interpretation_id, entity_id)).fetchone()
    if row is None or row["value"] is None:
        return None
    return ResolvedCitation(
        value=_claim_scaled(row["value"], claim),
        key_digest=row["key_digest"],
        value_kind=ValueKind(row["value_kind"]),
        currency=row["currency"],
        times=times,
    )


def _trace(
    own: Cursor[Any], trace_id: int, claim: NumericClaim, entity_id: int, catalog: SourceCatalog
) -> ResolvedCitation | None:
    """A computed trace whose every operand is first-party, under a claim key of the report's
    issuer (the caller matches the trace's key digest to the claim's)."""
    key = claim.measurement_key
    if key is None or key.entity_id != entity_id:
        return None
    row = own.execute(_TRACE, (trace_id,)).fetchone()
    times = _input_times(own, (trace_id,), (), catalog)
    if row is None or row["value"] is None or times is None:
        return None
    return ResolvedCitation(
        value=_claim_scaled(row["value"], claim), key_digest=row["key_digest"], times=times
    )


def _run_cell(
    own: Cursor[Any],
    query: LiteralString,
    record_id: int | None,
    claim: NumericClaim,
    overlay_position: datetime,
    times: _Times | None = None,
) -> ResolvedCitation | None:
    """A value of a result of the named run under the claim's key: an interpretation's
    ``VALUE`` source value (D9), or a pair difference whose input time is the run's."""
    run_id, key = claim.citation.run_id, claim.measurement_key
    if record_id is None or run_id is None or key is None:
        return None
    row = own.execute(query, (record_id, run_id, key.digest())).fetchone()
    if row is None or row["value"] is None:
        return None
    first_party = SourceState.VALUE if row["first_party_value"] else SourceState.NO_VALUE
    trust = trusted(
        run_id=run_id,
        key=key,
        extraction=ExtractionStatus(row["extraction_status"]),
        corroboration=CorroborationStatus(row["corroboration_status"]),
        first_party_state=first_party,
        overlay=overlay_at(own, run_id=run_id, as_of=overlay_position),
    )
    return ResolvedCitation(
        value=_claim_scaled(row["value"], claim),
        key_digest=row["key_digest"],
        value_kind=ValueKind(row["value_kind"]),
        currency=row["currency"],
        times=((InputTime.RUN, row["created_at"]),) if times is None else times,
        trusted=trust.trusted,
    )


def _claim_scaled(value: Decimal, claim: NumericClaim) -> Decimal:
    """A run-store value, held in base units (INR, not crore), in the claim's scale, so row 5
    compares it at the claim's display precision. Legacy facts carry their own scale."""
    return value / (claim.scale or 1)


def _policy(own: Cursor[Any], claim: NumericClaim, entity_id: int) -> ResolvedCitation | None:
    """An owner ``SET_POLICY`` value; a self-citation is its own imported record, whose value
    the importer's lossless mapping binds to the parsed source field (D7)."""
    decision_id = claim.citation.policy_decision_id
    if decision_id is None:
        return ResolvedCitation(value=claim.value)
    row = own.execute(_POLICY, (decision_id, entity_id)).fetchone()
    if row is None:
        return None
    return ResolvedCitation(
        value=row["policy_value"],
        unit=row["policy_unit"],
        times=((InputTime.POLICY, row["recorded_at"]),),
    )


def _input_times(
    own: Cursor[Any],
    traces: Iterable[int],
    interpretations: Iterable[int],
    catalog: SourceCatalog,
) -> _Times | None:
    """Every input time behind the traces and interpretations, or ``None`` when any capture
    behind them is not first-party."""
    rows = own.execute(
        _INPUTS, {"traces": list(traces), "interpretations": list(interpretations)}
    ).fetchall()
    if not rows or not all(_first_party(row["source_id"], catalog) for row in rows):
        return None
    times: list[tuple[InputTime, datetime | None]] = []
    for row in rows:
        times.append((InputTime.FIRST_SEEN, row["first_seen"]))
        times.append((InputTime.RECORDED, row["recorded_at"]))
        if row["occurrence_id"] is not None:
            times.append((InputTime.KNOWLEDGE, row["knowledge_time"]))
            times.append((InputTime.FIRST_SEEN, row["occurrence_first_seen"]))
    return tuple(times)


def _span(own: Cursor[Any], capture: _Row, anchor: str, snapshots: SnapshotStore) -> str | None:
    """The text at a ``p<page>.b<block>.<start>:<end>`` anchor of a PDF capture, or ``None``."""
    parsed = ANCHOR.fullmatch(anchor)
    document = _document(own, capture, snapshots)
    if parsed is None or document is None:
        return None
    provenance = Provenance(
        source_id=capture["source_id"],
        file_sha256=capture["blob_sha256"],
        anchor_type=SourceAnchorType.PDF_SPAN,
        page=int(parsed.group(1)),
        block=int(parsed.group(2)),
        span=parsed.group(3),
        retrieved_at=capture["first_seen"],
    )
    result = verify_quote_anchor(_Located(provenance=provenance), "", document)
    return result.resolved_text if result.anchored else None


def _document(own: Cursor[Any], capture: _Row, snapshots: SnapshotStore) -> SourceDocument | None:
    """The capture's retained PDF as addressable blocks, or ``None`` if it is not a PDF. An
    expired original raises ``OriginalExpiredError``, a lost one ``IntegrityError`` (RP7)."""
    _, body = retained_capture(own.connection, snapshots, capture_of(capture))
    if not body.startswith(PDF_MAGIC):
        return None
    try:
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / "capture.pdf"
            path.write_bytes(body)
            pdf = load_pdf(
                source_id=capture["source_id"], path=path, expected_sha256=capture["blob_sha256"]
            )
    except (PdfIntegrityError, pymupdf.FileDataError):
        return None
    return source_document(pdf)


def _instant(text: str | None) -> datetime | None:
    """A stored legacy ISO time, or ``None``."""
    return None if text is None else datetime.fromisoformat(text)
