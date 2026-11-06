"""Citation resolution: what a claim's cited record says, if it has authority (plan D8, D9).

``resolve_citation`` returns ``None`` (row 1, ``UNRESOLVED``) unless the cited record exists
and has authority: ``FIGURE`` and ``CALCULATION`` only first-party values (every capture
behind them; an interpretation ``FIGURE`` with no run its own mapped value) or vendor values
admitted under the pinned runs and still held (VENDOR-1 §6.9: both witnesses retained or
restored, no licence end, an unchecked class not contradicted by the cutoff), a quote only a
non-vendor capture, a ``COMPARISON`` its own run and key, a
``POLICY`` an owner ``SET_POLICY`` decision on a report of the same entity, a ``THESIS_CLAIM``
a falsifier threshold of the entity's bootstrap thesis whose version an approval recorded at the
pinned sealed digest (its earliest such approval's time is the input time), an admitted fact
only its admissions under the citing version's pinned runs, and a declared
``source_sha256`` only the cited fact's file or capture's blob. An admitted fact carries its
authorising admission's label (``citation_admission``), a trace over admitted operands the
weakest of theirs (§6.10). A capture's
first-seen time is the earlier of its registration and its blob's legacy acquisitions (D8).
A claim is labelled ``FILED`` exactly when it is an interpretation ``FIGURE`` with no run, and
only a comparator prior (``cmp.*.prior``), the filed tax total (``calc.2``) or a risk probe's
own operand (``FILED_KEYS``) may be one (invariant 7). A drafted quote's guidance contract is
the one a sealed import binds to the same quote (``bound_contract``, plan D4 M9).
Run-store values (cells, pair differences, traces) are base units, stated in the claim's
scale (``scale`` 10^7 for crore); display never rescales.
"""

from __future__ import annotations

import json
import re
import tempfile
from collections.abc import Iterable, Mapping, Sequence, Set
from datetime import datetime
from decimal import Decimal
from fractions import Fraction
from pathlib import Path, PurePosixPath
from typing import Any, LiteralString

import pymupdf
from psycopg import Cursor
from psycopg.rows import dict_row
from pydantic import BaseModel, ConfigDict

from equity_os.analysis.lenses.risk.probe_operands import FILED_KEYS
from equity_os.companies.identity.identity_layers import issuer_values
from equity_os.contracts.measurement.canonical import Basis, ValueKind
from equity_os.contracts.measurement.fact import Fact
from equity_os.contracts.measurement.measurement_key import DimensionSet, MeasurementKey
from equity_os.contracts.measurement.observation import AccountingFramework
from equity_os.contracts.measurement.provenance import Provenance, SourceAnchorType
from equity_os.contracts.publication.ledger import (
    Citation,
    CitationKind,
    GuidanceContract,
    InputTime,
    NumericClaim,
    ResolvedCitation,
)
from equity_os.contracts.sourcing.source_catalog import (
    SourceCatalog,
    SourceClass,
    UnknownSourceError,
)
from equity_os.contracts.verification.comparison import (
    CorroborationStatus,
    ExtractionStatus,
    SourceState,
)
from equity_os.contracts.verification.vendor_first import weakest
from equity_os.extraction.results_pdf.pdf_source import PdfIntegrityError, load_pdf
from equity_os.normalisation.derivation.interval import truncate_value
from equity_os.normalisation.dictionary.role_translation import translate
from equity_os.publication.checking.citation_admission import latest, standing
from equity_os.publication.checking.citation_admission import witnesses as witnesses
from equity_os.publication.checking.quote_anchor import (
    SourceDocument,
    source_document,
    verify_quote_anchor,
)
from equity_os.publication.checking.vendor_text import VT_ANCHOR, vendor_location
from equity_os.publication.drafting.display import EXACT_DIGITS, FILED
from equity_os.publication.revision.import_mapping import UPDATE_FILES, ledger_contracts
from equity_os.storage.facts.pg_fact_store import NATIVE_ORIGIN
from equity_os.storage.raw_files.capture_retention import retained_capture
from equity_os.storage.raw_files.snapshot_store import SnapshotStore
from equity_os.storage.records.repository_rows import capture_of, period_of
from equity_os.verification.admission.admission import ADMITTED_CONCEPT_PREFIX
from equity_os.verification.comparison.fact_view import CANONICAL_ENTITY_SCHEME
from equity_os.verification.review_queue.queue import overlay_at
from equity_os.verification.review_queue.trust import trusted

ANCHOR = re.compile(r"p(\d+)\.b(\d+)\.(\d+:\d+)")
PDF_MAGIC = b"%PDF-"
_FIRST_SEEN: LiteralString = """least(c.first_seen_at, (SELECT min(a.retrieved_at)
    FROM eqos.legacy_acquisitions a WHERE a.blob_sha256 = c.blob_sha256))"""
_CAPTURE: LiteralString = (
    "SELECT c.*, " + _FIRST_SEEN + " AS first_seen FROM eqos.capture_refs c WHERE c.id = %s"
)
# Issuer bindings known and recorded no later than the citing version's cutoff.
_LOCATION_ISSUER: LiteralString = """SELECT 1 FROM eqos.interpretations i
LEFT JOIN eqos.occurrences o ON o.id = i.occurrence_id
WHERE i.capture_ref_id = %(capture)s AND i.entity_id = %(entity)s
    AND i.recorded_at <= %(cutoff)s
    AND coalesce(o.knowledge_time, i.recorded_at) <= %(cutoff)s
UNION ALL SELECT 1 FROM eqos.numeric_claims q
JOIN eqos.report_versions v ON v.id = q.version_id
JOIN eqos.reports r ON r.id = v.report_id
JOIN eqos.capture_refs c ON c.id = %(capture)s
WHERE r.entity_id = %(entity)s AND q.citation_kind = 'SOURCE_QUOTE'
    AND q.source_sha256 = c.blob_sha256 AND v.knowledge_cutoff <= %(cutoff)s
    AND EXISTS (SELECT 1 FROM eqos.import_sources s WHERE s.version_id = v.id)
    AND EXISTS (SELECT 1 FROM eqos.decisions d
        WHERE d.subject_kind = 'REPORT_VERSION' AND d.subject_id = v.id
            AND d.kind = 'IMPORT_SEAL' AND d.decider = 'PANEL'
            AND d.recorded_at <= %(cutoff)s
            AND d.sealed_digest = eqos.version_sealed_digest(v.id))
UNION ALL SELECT 1 FROM eqos.legacy_evidence_bindings b
JOIN eqos.legacy_fact_translations t USING (target_store, row_handle)
JOIN eqos.fact_rows f ON f.target_store = b.target_store AND f.handle = b.row_handle
WHERE b.capture_ref_id = %(capture)s AND t.entity_id = %(entity)s
    AND CASE WHEN b.capture_ref_id = %(capture)s AND t.entity_id = %(entity)s
        THEN greatest(f.knowledge_time::timestamptz, f.created_at::timestamptz) END <= %(cutoff)s
LIMIT 1"""
# A fact's first selection time: a legacy-imported selection's own time, any other selection's
# no earlier than its store-clock recording (0037), whatever the cited fact's origin.
_FACT: LiteralString = """SELECT f.knowledge_time, f.fact_json, f.file_sha256 AS fact_file,
    f.created_at, t.*, b.capture_ref_id, s.selected_at
FROM eqos.fact_rows f
LEFT JOIN LATERAL (SELECT min(CASE WHEN eqos.legacy_time_exempt(target_store, origin)
        THEN selected_at::timestamptz ELSE greatest(selected_at::timestamptz, recorded_at) END)
        AS selected_at
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
# An admitted fact's admissions of the report's issuer under the pinned runs, with their keys,
# earliest first.
_ADMITTED: LiteralString = """SELECT r.key_digest, r.value_kind, r.currency, a.overlay_position,
    o.capture_ref_id, a.id, a.interpretation_id, a.witness_interpretation_id, a.label,
    a.class_digest
FROM eqos.fact_admissions a JOIN eqos.results r ON r.id = a.result_id
JOIN eqos.occurrences o ON o.id = a.occurrence_id
WHERE a.fact_origin = %s AND a.fact_origin_id = %s AND r.entity_id = %s
    AND a.run_id = ANY(%s)
ORDER BY a.overlay_position, a.id"""
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
_FILED_TAX = "calc.2"
_INTERPRETATION: LiteralString = """SELECT value, key_digest, value_kind, currency
FROM eqos.interpretations WHERE id = %s AND status = 'MAPPED' AND entity_id = %s"""
_TRACE: LiteralString = (
    "SELECT value, exact_value, key_digest FROM eqos.calculation_traces "
    "WHERE id = %s AND state = 'COMPUTED'"
)
_POLICY: LiteralString = """SELECT d.policy_value, d.policy_unit, d.recorded_at
FROM eqos.decisions d JOIN eqos.reports r ON r.id = d.subject_id
WHERE d.id = %s AND d.subject_kind = 'REPORT' AND d.kind = 'SET_POLICY'
    AND d.decider = 'OWNER' AND r.entity_id = %s"""
_THESIS_CLAIM: LiteralString = """SELECT c.value, c.unit, c.value_kind, d.recorded_at
FROM eqos.numeric_claims c JOIN eqos.report_versions v ON v.id = c.version_id
JOIN eqos.reports r ON r.id = v.report_id
JOIN eqos.decisions d ON d.subject_kind = 'REPORT_VERSION' AND d.subject_id = c.version_id
WHERE c.id = %s AND r.entity_id = %s AND r.kind = 'BOOTSTRAP_THESIS'
    AND starts_with(c.claim_key, 'falsifier.') AND d.kind IN ('APPROVE', 'IMPORTED_APPROVAL')
    AND d.sealed_digest = %s AND d.sealed_digest = eqos.version_sealed_digest(c.version_id)
ORDER BY d.recorded_at, d.id LIMIT 1"""
# The given traces and every trace they reach through operand traces (``WITH RECURSIVE``).
TRACES: LiteralString = """traces(id) AS (
    SELECT unnest(%(traces)s::bigint[])
    UNION SELECT o.operand_trace_id FROM eqos.calculation_trace_operands o
        JOIN traces t ON o.calculation_trace_id = t.id WHERE o.operand_trace_id IS NOT NULL
)"""
# The admissions under the pinned runs whose interpretation a trace reaches.
_TRACE_ADMISSIONS: LiteralString = (
    "WITH RECURSIVE "
    + TRACES
    + """ SELECT DISTINCT a.id, a.overlay_position, a.interpretation_id,
    a.witness_interpretation_id, a.label, a.class_digest FROM traces t
JOIN eqos.calculation_trace_operands o ON o.calculation_trace_id = t.id
JOIN eqos.fact_admissions a ON a.interpretation_id = o.interpretation_id
WHERE a.run_id = ANY(%(runs)s)"""
)
# Every interpretation behind the cited traces and interpretations, through trace operands,
# nested traces and constructed interpretations' operands, in id order so the pinned input
# fingerprint does not depend on the query plan.
_INPUTS: LiteralString = (
    "WITH RECURSIVE "
    + TRACES
    + """, interps(id) AS (
    SELECT unnest(%(interpretations)s::bigint[])
    UNION SELECT o.interpretation_id FROM eqos.calculation_trace_operands o
        JOIN traces t ON o.calculation_trace_id = t.id WHERE o.interpretation_id IS NOT NULL
    UNION SELECT o.operand_interpretation_id FROM eqos.interpretation_operands o
        JOIN interps i ON o.interpretation_id = i.id
)
SELECT i.id, c.source_id, i.recorded_at, i.occurrence_id, oc.knowledge_time,
    oc.first_seen_at AS occurrence_first_seen, """
    + _FIRST_SEEN
    + """ AS first_seen
FROM interps x JOIN eqos.interpretations i ON i.id = x.id
JOIN eqos.capture_refs c ON c.id = i.capture_ref_id
LEFT JOIN eqos.occurrences oc ON oc.id = i.occurrence_id
ORDER BY i.id"""
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
    run_ids: Sequence[int] = (),
    cutoff: datetime | None = None,
) -> ResolvedCitation | None:
    """What the claim's citation resolves to at ``overlay_position``, or ``None``.

    ``entity_id`` is the stock of the claim's report, which every keyed record and a ``POLICY``
    decision must share; ``run_ids`` are the citing version's pinned comparison runs, the only
    runs whose admissions an admitted fact resolves through; ``cutoff`` is the citing version's
    (default the overlay position), by which an unchecked vendor value's class must stand
    uncontradicted.
    """
    cutoff = overlay_position if cutoff is None else cutoff
    citation = claim.citation
    filed = (
        citation.kind is CitationKind.FIGURE
        and citation.fact_origin_id is None
        and citation.interpretation_id is not None
        and citation.run_id is None
    )
    if (FILED in claim.qualifiers) != filed or (filed and not _filed_key(claim)):
        return None
    with cursor.connection.cursor(row_factory=dict_row) as own:
        if citation.source_sha256 is not None and citation.source_sha256 != _source(own, citation):
            return None
        if citation.kind is CitationKind.FIGURE and citation.fact_origin_id is not None:
            return _fact(
                own,
                citation.fact_origin,
                citation.fact_origin_id,
                entity_id,
                catalog,
                claim,
                run_ids,
                cutoff,
            )
        if citation.kind is CitationKind.FIGURE and citation.interpretation_id is not None:
            times = _input_times(own, (), (citation.interpretation_id,), catalog)
            if times is None:
                return None
            if citation.run_id is None:
                return _interpretation(own, citation.interpretation_id, claim, entity_id, times)
            return _run_cell(
                own, _CELL, citation.interpretation_id, claim, entity_id, overlay_position, times
            )
        if citation.kind is CitationKind.CALCULATION and citation.calculation_trace_id is not None:
            trace = citation.calculation_trace_id
            return _trace(own, trace, claim, entity_id, catalog, run_ids, cutoff)
        if citation.kind is CitationKind.SOURCE_QUOTE and citation.capture_ref_id is not None:
            capture = _first_party_capture(own, citation.capture_ref_id, catalog)
            if capture is None:
                return None
            return ResolvedCitation(
                times=((InputTime.FIRST_SEEN, capture["first_seen"]),),
                quote_text=_span(own, capture, citation.anchor or "", snapshots),
            )
        if citation.kind is CitationKind.COMPARISON:
            return _run_cell(
                own, _COMPARISON, citation.pair_outcome_id, claim, entity_id, overlay_position
            )
        if citation.kind is CitationKind.POLICY:
            return _policy(own, claim, entity_id)
        if citation.kind is CitationKind.THESIS_CLAIM:
            params = (citation.cited_claim_id, entity_id, citation.cited_sealed_digest)
            row = own.execute(_THESIS_CLAIM, params).fetchone()
            if row is None:
                return None
            return ResolvedCitation(
                value=row["value"],
                unit=row["unit"],
                value_kind=ValueKind(row["value_kind"]),
                times=((InputTime.POLICY, row["recorded_at"]),),
            )
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
    entity_id: int,
    cutoff: datetime,
    catalog: SourceCatalog,
    snapshots: SnapshotStore,
    source_cutoff: datetime | None = None,
) -> bool:
    """Whether a prose location names a non-empty first-party span of this issuer, known and
    first seen by the citing version's cutoff, or a ``VT_ANCHOR`` eligible vendor span."""
    if not capture_id.isdigit():
        return False
    if VT_ANCHOR.fullmatch(anchor):
        return vendor_location(
            cursor, int(capture_id), anchor, entity_id, source_cutoff, cutoff, snapshots
        )
    with cursor.connection.cursor(row_factory=dict_row) as own:
        capture = _first_party_capture(own, int(capture_id), catalog)
        if capture is None or capture["first_seen"] > cutoff:
            return False
        params = {"capture": int(capture_id), "entity": entity_id, "cutoff": cutoff}
        if own.execute(_LOCATION_ISSUER, params).fetchone() is None:
            return False
        span = _span(own, capture, anchor, snapshots)
    return span is not None and span.strip() != ""


def _filed_key(claim: NumericClaim) -> bool:
    """Whether a claim may cite a filed value: a comparator prior, the filed tax total, or a
    risk probe's own operand under a currency-amount key naming that operand."""
    name, key = claim.claim_key, claim.measurement_key
    if name == _FILED_TAX or (name.startswith("cmp.") and name.endswith(".prior")):
        return True
    return (
        key is not None
        and key.canonical_id == FILED_KEYS.get(name)
        and key.value_kind is ValueKind.CURRENCY_AMOUNT
    )


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
    own: Cursor[Any],
    origin: str | None,
    origin_id: int,
    entity_id: int,
    catalog: SourceCatalog,
    claim: NumericClaim,
    run_ids: Sequence[int],
    cutoff: datetime,
) -> ResolvedCitation | None:
    """A legacy fact of the report's issuer, through its translation and its bound capture; a
    native admitted fact, through its pinned admissions (``_admitted``); or a native
    (run-written) fact of that issuer, through ``translate`` and its file's first-party
    capture, also held to its row's store-clock recording time."""
    row = own.execute(_FACT, (origin, origin_id)).fetchone()
    if row is None:
        return None
    observation = json.loads(row["fact_json"], parse_float=Decimal)["observation"]
    if origin == NATIVE_ORIGIN and observation["concept_qname"].startswith(ADMITTED_CONCEPT_PREFIX):
        return _admitted(own, row, origin_id, entity_id, catalog, claim, run_ids, cutoff)
    recorded: _Times = ()
    if origin == NATIVE_ORIGIN:
        key, capture = _native_key(own, row, entity_id), _file_capture(own, row, catalog)
        recorded = ((InputTime.RECORDED, _instant(row["created_at"])),)
    else:
        key, capture = _legacy_key(row), _first_party_capture(own, row["capture_ref_id"], catalog)
    if capture is None or key is None or key.entity_id != entity_id:
        return None
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
            (InputTime.SELECTED, row["selected_at"]),
            *recorded,
        ),
    )


def _admitted(
    own: Cursor[Any],
    row: _Row,
    origin_id: int,
    entity_id: int,
    catalog: SourceCatalog,
    claim: NumericClaim,
    run_ids: Sequence[int],
    cutoff: datetime,
) -> ResolvedCitation | None:
    """An admitted fact of the report's issuer, through its admissions under the pinned runs:
    their one key, value kind and currency, its base-unit value in the claim's scale, the
    earliest valid admission with its own capture as the witness of when it was known, and the
    authorising admission's label and times (``standing``); a valid filed admission's capture is
    first-party, a vendor one's two witnesses held."""
    admissions = own.execute(
        _ADMITTED, (NATIVE_ORIGIN, origin_id, entity_id, list(run_ids))
    ).fetchall()
    cells = {(a["key_digest"], a["value_kind"], a["currency"]) for a in admissions}
    valid = {a["id"]: seen for a in admissions if (seen := _seen(own, a, catalog)) is not None}
    authority = latest(admissions, cutoff)
    if len(cells) != 1 or authority is None or authority["id"] not in valid:
        return None
    held = standing(own, authority, cutoff)
    if held is None:
        return None
    ((digest, value_kind, currency),) = cells
    witness = next(a for a in admissions if a["id"] in valid)
    observation = Fact.model_validate_json(row["fact_json"]).observation
    return ResolvedCitation(
        value=_claim_scaled(observation.normalized_value, claim),
        key_digest=digest,
        value_kind=ValueKind(value_kind),
        currency=currency,
        times=(
            (InputTime.KNOWLEDGE, _instant(row["knowledge_time"])),
            (InputTime.FIRST_SEEN, valid[witness["id"]]),
            (InputTime.SELECTED, row["selected_at"]),
            (InputTime.RECORDED, _instant(row["created_at"])),
            (InputTime.RECORDED, witness["overlay_position"]),
            *held,
        ),
        admission_label=authority["label"],
    )


def _seen(own: Cursor[Any], admission: _Row, catalog: SourceCatalog) -> datetime | None:
    """A valid admission's capture's first-seen time: a filed one's capture first-party, a
    vendor one's two witnesses held; else ``None``."""
    capture = own.execute(_CAPTURE, (admission["capture_ref_id"],)).fetchone()
    witness = admission["witness_interpretation_id"]
    if capture is None or not (
        _first_party(capture["source_id"], catalog)
        if witness is None
        else witnesses(own, admission["interpretation_id"], witness) is not None
    ):
        return None
    first_seen: datetime = capture["first_seen"]
    return first_seen


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
    if _issuer_key(claim, entity_id) is None:
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
    own: Cursor[Any],
    trace_id: int,
    claim: NumericClaim,
    entity_id: int,
    catalog: SourceCatalog,
    run_ids: Sequence[int],
    cutoff: datetime,
) -> ResolvedCitation | None:
    """A computed trace whose every operand is first-party or authorised by a standing vendor
    admission under the pinned runs (``standing``, whose times it adds), under a claim key of the
    report's issuer (the caller matches the trace's key digest to the claim's); it carries the
    weakest label of its admitted operands' authorising admissions."""
    if _issuer_key(claim, entity_id) is None:
        return None
    row = own.execute(_TRACE, (trace_id,)).fetchone()
    params = {"traces": [trace_id], "runs": list(run_ids)}
    by_operand: dict[int, list[_Row]] = {}
    for found in own.execute(_TRACE_ADMISSIONS, params).fetchall():
        by_operand.setdefault(found["interpretation_id"], []).append(found)
    authorities = [latest(group, cutoff) for group in by_operand.values()]
    admissions = [a for a in authorities if a is not None]
    held: dict[int, _Times] = {}
    for a in admissions:
        if a["witness_interpretation_id"] is not None and (t := standing(own, a, cutoff)):
            held[a["interpretation_id"]] = t
    times = _input_times(own, (trace_id,), (), catalog, held.keys())
    if row is None or row["value"] is None or times is None:
        return None
    times += tuple(time for operand in held.values() for time in operand)
    value = (
        truncate_value(Fraction(row["exact_value"]) / (claim.scale or 1), claim.precision)
        if EXACT_DIGITS in claim.qualifiers
        else _claim_scaled(row["value"], claim)
    )
    label = weakest(a["label"] for a in admissions) if admissions else None
    return ResolvedCitation(
        value=value, key_digest=row["key_digest"], times=times, admission_label=label
    )


def _issuer_key(claim: NumericClaim, entity_id: int) -> MeasurementKey | None:
    """The claim's key, only when it is a key of the report's issuer."""
    key = claim.measurement_key
    return key if key is not None and key.entity_id == entity_id else None


def _run_cell(
    own: Cursor[Any],
    query: LiteralString,
    record_id: int | None,
    claim: NumericClaim,
    entity_id: int,
    overlay_position: datetime,
    times: _Times | None = None,
) -> ResolvedCitation | None:
    """A value of a result of the named run under the claim's key of the report's issuer: an
    interpretation's ``VALUE`` source value (D9), or a pair difference whose input time is the
    run's."""
    run_id, key = claim.citation.run_id, _issuer_key(claim, entity_id)
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
    """A run-store or admitted-fact value, held in base units (INR, not crore), in the claim's
    scale, so row 5 compares it at the claim's display precision. Legacy facts carry their own
    scale."""
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
    vendor: Set[int] = frozenset(),
) -> _Times | None:
    """Every input time behind the traces and interpretations, or ``None`` when any capture
    behind them is not first-party, other than the ``vendor`` interpretations'."""
    rows = own.execute(
        _INPUTS, {"traces": list(traces), "interpretations": list(interpretations)}
    ).fetchall()
    if not rows or not all(
        row["id"] in vendor or _first_party(row["source_id"], catalog) for row in rows
    ):
        return None
    times: list[tuple[InputTime, datetime | None]] = []
    for row in rows:
        times.append((InputTime.FIRST_SEEN, row["first_seen"]))
        times.append((InputTime.RECORDED, row["recorded_at"]))
        if row["occurrence_id"] is not None:
            if row["id"] not in vendor:  # a vendor value is known by its capture's first sight
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
