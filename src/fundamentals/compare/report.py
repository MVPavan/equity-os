"""Render a stored run as plain text (D1a Task 9).

One header block from the run record, then one block per result row keyed by ``row_id``:
each source value with its unit and state (currency amounts also in crore, two decimals),
extraction and corroboration, pair outcomes with difference and gap, the headline marker,
surfaced restatements and, for derived rows, the calculation trace ids. ``NOT_APPLICABLE``
rows are listed with their rule id and nothing else.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import ROUND_HALF_EVEN, Decimal

from fundamentals.canon.dictionary import CanonicalDictionary
from fundamentals.compare.run_models import PairRecord, ResultRow, RunRecord, SourceValue
from fundamentals.contracts.canonical import ApplicabilityStatus, ValueKind

CRORE = Decimal(10) ** 7
CRORE_PLACES = Decimal("0.01")
HEADLINE_MARKER = "*"
NONE_TEXT = "-"
_HEADER = (
    "run\t{run_id}",
    "cutoff\t{cutoff}",
    "mode\t{mode}",
    "status\t{status}",
    "code\t{code}",
)
_ROW = "row\t{row_id}{headline}"
_NOT_APPLICABLE = "  NOT_APPLICABLE\t{rule}"
_STATUSES = "  extraction\t{extraction}\t{extraction_reason}\n  corroboration\t{corroboration}"
_VALUE = "  {role}\t{representation}\t{state}\t{value}\t{unit}{crore}{reason}{trace}"
_CRORE = "\t{amount} crore"
_REASON = "\treason={reason}"
_TRACE = "\ttrace={trace}"
_PAIR = "  pair\t{kind}\t{left}~{right}\t{outcome}\tdifference={difference}\tgap={gap}{triage}"
_TRIAGE = "\ttriage={triage}"
_SURFACED = "  surfaced\t{ids}"


def render_report(
    record: RunRecord, results: Sequence[ResultRow], *, dictionary: CanonicalDictionary
) -> str:
    """The run header and one block per result row, in ``row_id`` order."""
    manifest = record.manifest
    lines = [
        template.format(
            run_id=record.run_id,
            cutoff=manifest.cutoff.isoformat(),
            mode=manifest.mode.value,
            status=manifest.status.value,
            code=manifest.code_version,
        )
        for template in _HEADER
    ]
    headlines = {row.canonical_id for row in dictionary.rows if row.headline}
    for result in sorted(results, key=lambda item: item.row_id):
        lines.extend(_row_lines(result, headline=result.key.canonical_id in headlines))
    return "\n".join(lines) + "\n"


def _row_lines(result: ResultRow, *, headline: bool) -> list[str]:
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
    lines.extend(_value_line(value, unit, in_crore=amount) for value in result.source_values)
    lines.extend(_pair_line(pair) for pair in result.pairs)
    if result.surfaced_restatements:
        ids = ",".join(str(item) for item in result.surfaced_restatements)
        lines.append(_SURFACED.format(ids=ids))
    return lines


def _unit(result: ResultRow) -> str:
    """The row's unit: its currency for amounts, else its value kind."""
    key = result.key
    if key.currency is not None and key.value_kind is ValueKind.PER_SHARE_AMOUNT:
        return f"{key.currency}/share"
    return key.currency if key.currency is not None else key.value_kind.value


def _value_line(value: SourceValue, unit: str, *, in_crore: bool) -> str:
    """One source value with state, unit, crore amount, reason and trace."""
    crore = ""
    if in_crore and value.value is not None:
        crore = _CRORE.format(amount=_crore(value.value))
    return _VALUE.format(
        role=value.source_role.value,
        representation=value.representation.value,
        state=value.state.value,
        value=NONE_TEXT if value.value is None else str(value.value),
        unit=unit,
        crore=crore,
        reason="" if value.reason is None else _REASON.format(reason=value.reason),
        trace=(
            ""
            if value.calculation_trace_id is None
            else _TRACE.format(trace=value.calculation_trace_id)
        ),
    )


def _pair_line(pair: PairRecord) -> str:
    """One pair outcome with difference, gap and triage."""
    return _PAIR.format(
        kind=pair.pair_kind.value,
        left=f"{pair.left.source_role.value}:{pair.left.representation.value}",
        right=f"{pair.right.source_role.value}:{pair.right.representation.value}",
        outcome=pair.outcome.value,
        difference=NONE_TEXT if pair.difference is None else str(pair.difference),
        gap=NONE_TEXT if pair.interval_gap is None else str(pair.interval_gap),
        triage="" if pair.triage is None else _TRIAGE.format(triage=pair.triage.value),
    )


def _crore(amount: Decimal) -> str:
    """An amount in crore, two decimals (half-even)."""
    return str((amount / CRORE).quantize(CRORE_PLACES, rounding=ROUND_HALF_EVEN))
