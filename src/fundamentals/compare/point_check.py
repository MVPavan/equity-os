"""The R12 point check: a vendor shareholding value against the filing's point value (D8).

Pure over a run's frozen evidence and rows, so a stored run and ``replay_run``'s rows give the
same checks; it never enters a status, tier, row or fact. Candidates are the vendor sides
``VendorSides`` selects holding a printed number (its exact lexeme is the vendor value) at a key
resolving to a first-party category or basket, with or without a row. A member with no stored
first-party value counts as zero only when the selected package was extracted and no
occurrence's context bears it or a descendant.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import ROUND_HALF_EVEN, Decimal
from enum import StrEnum
from typing import cast

from pydantic import BaseModel, ConfigDict

from fundamentals.compare.resolve import ReplayTraces
from fundamentals.compare.resolve_models import ResolvedInputs
from fundamentals.compare.run_config import LoadedConfig
from fundamentals.compare.run_models import (
    ResultRow,
    RunInputDisposition,
    RunInputKind,
    RunRequest,
)
from fundamentals.compare.vendor_sides import VendorSides
from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.canonical import Representation
from fundamentals.contracts.comparison import PairOutcome, SourceRole, SourceState
from fundamentals.contracts.evidence import (
    Interpretation,
    InterpretationReason,
    MissingValueState,
    Occurrence,
)
from fundamentals.contracts.measurement_key import MeasurementKey
from fundamentals.evidence.interpret import TRACE_ASSUMPTIONS
from fundamentals.evidence.mapping_models import MappingAssumption

CATEGORY_AXIS = "shareholding_category"
ZERO = Decimal(0)
_ANY_MONTH = 3  # an instant's period kind ignores the fiscal calendar
_SELECTED = (RunInputKind.PACKAGE, RunInputDisposition.SELECTED)
# A printed vendor number: selected, or refused only for its undeclared precision (Upstox).
_NUMBERS = (MissingValueState.VALUE, MissingValueState.ZERO_PRINTED)
_PRINTED = {
    (SourceState.VALUE, None),
    (SourceState.INVALID, InterpretationReason.PRECISION_UNSUPPORTED.value),
}
NO_PACKAGE = "no selected, successfully extracted shareholding package"
_FILED = "category {member} is filed in the package with no stored value at this key"
_UNRESOLVED = "category {member} has no first-party selector, so its absence is unknown"


class PointVerdict(StrEnum):
    """Equal at the vendor's printed places, a check (not an error), or refused."""

    POINT_EQUAL = "POINT_EQUAL"
    POINT_CHECK = "POINT_CHECK"
    POINT_REFUSED = "POINT_REFUSED"


_VERDICTS = {
    None: PointVerdict.POINT_REFUSED,
    True: PointVerdict.POINT_EQUAL,
    False: PointVerdict.POINT_CHECK,
}


class PointCheck(BaseModel):
    """One vendor value's point check; ``outcome`` is its row's formal pair outcome, if any."""

    model_config = ConfigDict(frozen=True)

    key: MeasurementKey
    source: str
    vendor_value: Decimal
    members: tuple[tuple[str, Decimal | None], ...]
    zero_members: tuple[str, ...]
    point_value: Decimal | None
    package_id: int | None
    outcome: PairOutcome | None
    assumptions: tuple[MappingAssumption, ...]
    verdict: PointVerdict
    reason: str | None


def point_checks(
    rows: Sequence[ResultRow], inputs: ResolvedInputs, request: RunRequest, config: LoadedConfig
) -> tuple[PointCheck, ...]:
    """Every candidate's point check, in key order."""
    vendors = VendorSides(inputs, request, config=config, traces=ReplayTraces(inputs.traces))
    sources = {ref.capture_ref_id: (ref.source_id, ref.surface) for ref in inputs.capture_refs}
    keys = {
        item.key
        for item in inputs.interpretations
        if sources.get(item.capture_ref_id) in request.scope.vendors
        and item.key is not None
        and _basket(config, item.key)[1]
    }
    stored = {
        _identity(row.key, row.key.canonical_id): value.value
        for row in rows
        for value in row.source_values
        if value.source_role is SourceRole.FIRST_PARTY and value.value is not None
    }
    chosen = {item.ref_id for item in inputs.inputs if (item.kind, item.disposition) == _SELECTED}
    package = next((item for item in inputs.packages if item.package_id in chosen), None)
    capture = package.members[Representation.XBRL].capture.capture_ref_id if package else None
    filed = [item for item in inputs.occurrences if item.capture.capture_ref_id == capture]
    outcomes = {
        item.outcome
        for item in inputs.attempts
        if item.capture is not None and item.capture.capture_ref_id == capture
    }
    by_id = {item.interpretation_id: item for item in inputs.interpretations}
    checks = []
    for key in sorted(keys, key=lambda item: item.digest()):
        canonical_id, basket = _basket(config, key)
        reason = None if outcomes == {ExtractionOutcome.COMPLETE} else NO_PACKAGE
        values = {member: stored.get(_identity(key, canonical_id, member)) for member in basket}
        for member in [member for member, value in values.items() if value is None]:
            reason = reason or _absent(config, member, filed)
        zeros = () if reason else tuple(member for member, value in values.items() if value is None)
        point = None if reason else sum((value or ZERO for value in values.values()), ZERO)
        pairs = next((row.pairs for row in rows if row.key == key), ())
        for side in vendors.sides(key, _ANY_MONTH):
            stored_side, occurrence = side.stored, side.occurrence
            number = occurrence is not None and occurrence.missing_state in _NUMBERS
            if (stored_side.state, stored_side.reason) not in _PRINTED or not number:
                continue
            assert occurrence is not None
            lexeme = str(occurrence.raw_value_text).rstrip("% ")
            vendor_value = Decimal(lexeme).scaleb(occurrence.raw_scale)
            places = Decimal(1).scaleb(-len(lexeme.partition(".")[2]))
            rounded = None if point is None else point.quantize(places, ROUND_HALF_EVEN)
            vendor = (stored_side.source_id, stored_side.surface)
            formal = [p for p in pairs if p.left.source_role is SourceRole.FIRST_PARTY]
            outcome = (p.outcome for p in formal if (p.right.source_id, p.right.surface) == vendor)
            checks.append(
                PointCheck(
                    key=key,
                    source="/".join(str(part) for part in vendor),
                    vendor_value=vendor_value,
                    members=tuple((m, ZERO if m in zeros else v) for m, v in values.items()),
                    zero_members=zeros,
                    point_value=point,
                    package_id=package.package_id if package else None,
                    outcome=next(outcome, None),
                    assumptions=assumptions_of(by_id[stored_side.interpretation_id]),
                    verdict=_VERDICTS[None if rounded is None else rounded == vendor_value],
                    reason=reason,
                )
            )
    return tuple(checks)


def _basket(config: LoadedConfig, key: MeasurementKey) -> tuple[str, tuple[str, ...]]:
    """The first-party row and category members a vendor key stands for (none: no category)."""
    member = dict(key.dimensions.pairs).get(CATEGORY_AXIS)
    formula = config.dictionary.row(key.canonical_id).formula
    if member is None or formula is None:
        return key.canonical_id, () if member is None else (member,)
    aggregation = formula.operands[0].aggregation
    if len(formula.operands) != 1 or aggregation is None or aggregation.axis != CATEGORY_AXIS:
        return key.canonical_id, ()
    return formula.operands[0].canonical_id, aggregation.input_members


def _identity(key: MeasurementKey, canonical_id: str, member: str = "") -> tuple[object, ...]:
    """A key's identity under another row (and category member)."""
    pairs = dict(key.dimensions.pairs) | ({CATEGORY_AXIS: member} if member else {})
    return canonical_id, key.entity_id, key.period, key.basis, frozenset(pairs.items())


def _absent(config: LoadedConfig, member: str, filed: Sequence[Occurrence]) -> str | None:
    """Why a member without a stored value is not zero; ``None`` when the filing omits it and
    every category it contains (the mapping set's first-party selectors name the filed members)."""
    axis = config.dictionary.template(CATEGORY_AXIS).axis(CATEGORY_AXIS)
    family = {member}
    for _ in axis.members if axis else ():
        family |= {item.member for item in axis.members if item.parent in family} if axis else set()
    names = {
        entry.selector.dimension_member
        for entry in config.mapping_set.entries
        if entry.dimension_members.get(CATEGORY_AXIS) in family
    } - {None}
    if not names:
        return _UNRESOLVED.format(member=member)
    bearing = {
        str(value).rsplit(":", 1)[-1]
        for item in filed
        for _, value in cast(list[list[str]], item.native_context.get("dimensions") or [])
    }
    return _FILED.format(member=member) if names & bearing else None


def assumptions_of(reading: Interpretation) -> tuple[MappingAssumption, ...]:
    """The mapping assumptions an interpretation's trace carries (R10, R12)."""
    listed = reading.transform_trace.get(TRACE_ASSUMPTIONS)
    return tuple(MappingAssumption(item) for item in listed) if isinstance(listed, list) else ()
