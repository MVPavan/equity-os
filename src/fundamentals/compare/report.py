"""Render a stored run as plain text (D1a Task 9).

One header block from the run record (with its operational failures), then one block per
result row keyed by ``row_id``: each source value (a vendor's as ``source/surface``) with its
unit, state and epistemic class (an interpretation is ``OBSERVED``, a calculation
``COMPUTED``), its provenance (the interpretation id and source anchor, the calculation trace,
or the attempt that decided a failed side), extraction and corroboration, pair outcomes with
reason, difference, gap, definition record and adjustments, the headline marker and
surfaced restatements, then the row's open queue items and its trust at the overlay time the
header states (items without a measurement key, i.e. ``UNMAPPED`` occurrences, list in the
header). Currency amounts also print in crore, two decimals. ``NOT_APPLICABLE`` rows list
their rule id only. The dictionary must be the one the run pinned, by content.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Protocol

from fundamentals.canon.dictionary import CanonicalDictionary
from fundamentals.compare.run_models import (
    PairRecord,
    ResultRow,
    RunRecord,
    SourceValue,
    period_text,
)
from fundamentals.compare.tables import TaggingAdjustment
from fundamentals.compare.trust import trusted
from fundamentals.contracts.canonical import ApplicabilityStatus, ValueKind
from fundamentals.contracts.comparison import EpistemicClass, SourceRef, SourceRole, SourceState
from fundamentals.contracts.evidence import Interpretation, Occurrence
from fundamentals.contracts.review_queue import QueueItem, QueueOverlay
from fundamentals.contracts.versioning import VersionContentDriftError

CRORE = Decimal(10) ** 7
CRORE_PLACES = Decimal("0.01")
HEADLINE_MARKER = "*"
NONE_TEXT = "-"
DICTIONARY_ARTIFACT = "dictionary"
_HEADER = (
    "run\t{run_id}",
    "cutoff\t{cutoff}",
    "mode\t{mode}",
    "status\t{status}",
    "code\t{code}",
    "overlay\t{as_of}",
)
_FAILURE = "failure\t{failure}"
_ROW = "row\t{row_id}{headline}"
_NOT_APPLICABLE = "  NOT_APPLICABLE\t{rule}"
_STATUSES = "  extraction\t{extraction}\t{extraction_reason}\n  corroboration\t{corroboration}"
_VALUE = "  {role}\t{representation}\t{state}\t{value}\t{unit}{crore}\tclass={label}{provenance}"
_CRORE = "\t{amount} crore"
_REASON = "\treason={reason}"
_TRACE = "\ttrace={trace}"
_INTERPRETATION = "\tinterpretation={interpretation}\tanchor={anchor}"
_ATTEMPT = "\tattempt={attempt}"
_PAIR = (
    "  pair\t{kind}\t{left}~{right}\t{outcome}\treason={reason}\tdifference={difference}"
    "\tgap={gap}{triage}{definition}{adjustments}"
)
_TRIAGE = "\ttriage={triage}"
_DEFINITION = "\tdefinition={record}"
_ADJUSTMENT = "\tadjust={operand}:{representation}:{direction}{amount}:{record}"
_SURFACED = "  surfaced\t{ids}"
_QUEUE = "queue\t{item}\t{severity}\t{outcome}\t{route}\treason={reason}\tkey={key}"
_TRUST = "  trusted\t{trusted}"
_CAPTURE_ANCHOR = "capture:{capture}:{anchor}"
_CONSTRUCTION_ANCHOR = "construction:{rule}"


class AnchorReader(Protocol):
    """By-id reads that resolve an interpretation to its source anchor."""

    def get_interpretations(self, ids: Sequence[int]) -> tuple[Interpretation, ...]:
        """Interpretations by id."""
        ...

    def get_occurrences(self, ids: Sequence[int]) -> tuple[Occurrence, ...]:
        """Occurrences by id."""
        ...


def source_anchors(reader: AnchorReader, results: Sequence[ResultRow]) -> dict[int, str]:
    """Every reported interpretation's anchor: its capture and anchor key, or its rule."""
    ids = sorted(
        {
            value.interpretation_id
            for row in results
            for value in row.source_values
            if value.interpretation_id is not None
        }
    )
    interpretations = reader.get_interpretations(ids) if ids else ()
    occurrence_ids = sorted(
        {item.occurrence_id for item in interpretations if item.occurrence_id is not None}
    )
    occurrences = {
        occurrence.occurrence_id: occurrence
        for occurrence in (reader.get_occurrences(occurrence_ids) if occurrence_ids else ())
    }
    anchors: dict[int, str] = {}
    for item in interpretations:
        assert item.interpretation_id is not None
        occurrence = occurrences.get(item.occurrence_id)
        if occurrence is not None:
            anchors[item.interpretation_id] = _CAPTURE_ANCHOR.format(
                capture=occurrence.capture.capture_ref_id, anchor=occurrence.anchor_key
            )
        elif item.construction_rule_id is not None:
            anchors[item.interpretation_id] = _CONSTRUCTION_ANCHOR.format(
                rule=item.construction_rule_id
            )
    return anchors


def render_report(
    record: RunRecord,
    results: Sequence[ResultRow],
    *,
    dictionary: CanonicalDictionary,
    anchors: Mapping[int, str],
    overlay: QueueOverlay,
) -> str:
    """The run header and one block per result row, in ``row_id`` order, at ``overlay``.

    Raises ``VersionContentDriftError`` when ``dictionary`` is not the run's pinned one.
    """
    manifest = record.manifest
    pinned = manifest.pinned.dictionary
    if (dictionary.version, dictionary.content_sha256) != (pinned.version, pinned.content_sha256):
        raise VersionContentDriftError(
            artifact=DICTIONARY_ARTIFACT,
            version=pinned.version,
            pinned_sha256=pinned.content_sha256,
            actual_sha256=dictionary.content_sha256,
        )
    lines = [
        template.format(
            run_id=record.run_id,
            cutoff=manifest.cutoff.isoformat(),
            mode=manifest.mode.value,
            status=manifest.status.value,
            code=manifest.code_version,
            as_of=overlay.as_of.isoformat(),
        )
        for template in _HEADER
    ]
    lines.extend(_FAILURE.format(failure=failure) for failure in manifest.operational_failures)
    lines.extend(queue_line(item) for item in overlay.open_items if item.key is None)
    headlines = {row.canonical_id for row in dictionary.rows if row.headline}
    for result in sorted(results, key=lambda item: item.row_id):
        lines.extend(
            _row_lines(
                result,
                headline=result.key.canonical_id in headlines,
                anchors=anchors,
                run_id=record.run_id,
                overlay=overlay,
            )
        )
    return "\n".join(lines) + "\n"


def _row_lines(
    result: ResultRow,
    *,
    headline: bool,
    anchors: Mapping[int, str],
    run_id: int,
    overlay: QueueOverlay,
) -> list[str]:
    """One row's block."""
    lines = [_ROW.format(row_id=result.row_id, headline=HEADLINE_MARKER if headline else "")]
    if result.applicability is ApplicabilityStatus.NOT_APPLICABLE:
        lines.append(_NOT_APPLICABLE.format(rule=result.applicability_rule_id))
        return lines
    lines.append(
        _STATUSES.format(
            extraction=result.extraction_status.value,
            extraction_reason=result.extraction_reason or NONE_TEXT,
            corroboration=result.corroboration_status.value,
        )
    )
    unit = _unit(result)
    amount = result.key.value_kind is ValueKind.CURRENCY_AMOUNT
    lines.extend(
        _value_line(value, unit, in_crore=amount, anchors=anchors) for value in result.source_values
    )
    lines.extend(_pair_line(pair) for pair in result.pairs)
    if result.surfaced_restatements:
        ids = ",".join(str(item) for item in result.surfaced_restatements)
        lines.append(_SURFACED.format(ids=ids))
    digest = result.key.digest()
    lines.extend(
        "  " + queue_line(item)
        for item in overlay.open_items
        if item.key is not None and item.key.digest() == digest
    )
    first_party_value = any(
        value.source_role is SourceRole.FIRST_PARTY and value.state is SourceState.VALUE
        for value in result.source_values
    )
    trust = trusted(
        run_id=run_id,
        key=result.key,
        extraction=result.extraction_status,
        corroboration=result.corroboration_status,
        first_party_state=SourceState.VALUE if first_party_value else SourceState.NO_VALUE,
        overlay=overlay,
    )
    lines.append(_TRUST.format(trusted=str(trust.trusted).lower()))
    return lines


def queue_line(item: QueueItem) -> str:
    """One open queue item: id, severity, outcome, route, reason code and key."""
    key = item.key
    return _QUEUE.format(
        item=item.item_id,
        severity=item.severity.value,
        outcome=item.outcome,
        route=item.routing_reason,
        reason=NONE_TEXT if item.reason_code is None else item.reason_code.value,
        key=NONE_TEXT if key is None else f"{key.canonical_id}:{period_text(key.period)}",
    )


def _unit(result: ResultRow) -> str:
    """The row's unit: its currency for amounts, else its value kind."""
    key = result.key
    if key.currency is not None and key.value_kind is ValueKind.PER_SHARE_AMOUNT:
        return f"{key.currency}/share"
    return key.currency if key.currency is not None else key.value_kind.value


def _value_line(
    value: SourceValue, unit: str, *, in_crore: bool, anchors: Mapping[int, str]
) -> str:
    """One source value with state, unit, crore amount, class, provenance and reason."""
    crore = ""
    if in_crore and value.value is not None:
        crore = _CRORE.format(amount=_crore(value.value))
    computed = value.calculation_trace_id is not None
    return _VALUE.format(
        role=value.source_role.value,
        representation=_source(value),
        state=value.state.value,
        value=NONE_TEXT if value.value is None else str(value.value),
        unit=unit,
        crore=crore,
        label=(EpistemicClass.COMPUTED if computed else EpistemicClass.OBSERVED).value,
        provenance=_provenance(value, anchors),
    )


def _provenance(value: SourceValue, anchors: Mapping[int, str]) -> str:
    """Where a value comes from: interpretation and anchor, trace, attempt; then the reason."""
    text = ""
    if value.interpretation_id is not None:
        text += _INTERPRETATION.format(
            interpretation=value.interpretation_id,
            anchor=anchors.get(value.interpretation_id, NONE_TEXT),
        )
    if value.calculation_trace_id is not None:
        text += _TRACE.format(trace=value.calculation_trace_id)
    if value.attempt_id is not None:
        text += _ATTEMPT.format(attempt=value.attempt_id)
    if value.reason is not None:
        text += _REASON.format(reason=value.reason)
    return text


def _pair_line(pair: PairRecord) -> str:
    """One pair outcome with reason, difference, gap, triage, record and adjustments."""
    return _PAIR.format(
        kind=pair.pair_kind.value,
        left=f"{pair.left.source_role.value}:{_source(pair.left)}",
        right=f"{pair.right.source_role.value}:{_source(pair.right)}",
        outcome=pair.outcome.value,
        reason=NONE_TEXT if pair.reason is None else pair.reason.value,
        difference=NONE_TEXT if pair.difference is None else str(pair.difference),
        gap=NONE_TEXT if pair.interval_gap is None else str(pair.interval_gap),
        triage="" if pair.triage is None else _TRIAGE.format(triage=pair.triage.value),
        definition=(
            ""
            if pair.definition_record_id is None
            else _DEFINITION.format(record=pair.definition_record_id)
        ),
        adjustments="".join(_adjustment(item) for item in pair.adjustments),
    )


def _source(ref: SourceRef) -> str:
    """A first-party side's representation, or a vendor side's ``source/surface``."""
    return ref.representation.value if ref.source_id is None else f"{ref.source_id}/{ref.surface}"


def _adjustment(adjustment: TaggingAdjustment) -> str:
    """One applied tagging adjustment: operand, representation, signed amount, record."""
    return _ADJUSTMENT.format(
        operand=adjustment.operand_name,
        representation=adjustment.representation.value,
        direction="+" if adjustment.direction > 0 else "-",
        amount=adjustment.amount,
        record=adjustment.definition_record_id,
    )


def _crore(amount: Decimal) -> str:
    """An amount in crore, two decimals (half-even)."""
    return str((amount / CRORE).quantize(CRORE_PLACES, rounding=ROUND_HALF_EVEN))
