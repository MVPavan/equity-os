"""Capture bytes to lossless XBRL occurrences (D1a Task 5).

One occurrence per distinct numeric or text fact (nil facts as ``NIL``). Keeping text
facts independently of mappings permits capture-only reuse. Values stay as filed: raw text, raw
unit, raw scale 0 (XBRL values are base-unit INR already), the declared ``decimals``,
the raw period and the declared-period repair evidence.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from fundamentals.contracts.canonical import Representation
from fundamentals.contracts.evidence import (
    CaptureReference,
    MissingValueState,
    Occurrence,
    PackageMember,
    PrecisionKind,
    RevisionCause,
)
from fundamentals.contracts.observation import Scope
from fundamentals.evidence.mapping import (
    CONTEXT_BASIS,
    CONTEXT_DIMENSION_AXES,
    CONTEXT_LOCAL_NAME,
    CONTEXT_NAMESPACE,
    CONTEXT_SCHEMA_IDENTITY,
    MappingSet,
    UnsupportedSchemaError,
)
from fundamentals.extract.xbrl_parser import (
    RawXbrlFact,
    RawXbrlInstance,
    UnsupportedTaxonomyError,
    XbrlParseError,
    iter_raw_facts,
)
from fundamentals.extract.xbrl_taxonomies import _ALL_TAXONOMIES

XBRL_EXTRACTOR_VERSION = "xbrl-occurrences/3"
SEGMENT_DESCRIPTION_CONCEPT = "DescriptionOfReportableSegment"
DECIMALS_INFINITE = "INF"
CONTEXT_MEMBER_DESCRIPTIONS = "member_descriptions"
CONTEXT_PERIOD_AMBIGUOUS = "period_ambiguous"
_SIGNED_NUMBER = re.compile(r"[+-]?\d+(\.\d+)?")
_ZERO = re.compile(r"[+-]?0+(\.0+)?")
_UNREGISTERED = "an unregistered taxonomy"
_BASIS_OF_SCOPE: Mapping[Scope, str] = {
    Scope.CONSOLIDATED: "CONSOLIDATED",
    Scope.STANDALONE: "STANDALONE",
}


def parse_instance(body: bytes, *, mapping_set: MappingSet) -> RawXbrlInstance:
    """Parse an instance, refusing a schema the mapping set does not support."""
    try:
        instance = iter_raw_facts(body, taxonomies=_ALL_TAXONOMIES)
    except UnsupportedTaxonomyError as error:
        raise UnsupportedSchemaError(_UNREGISTERED, mapping_set.version) from error
    mapping_set.require_schema(instance.schema_identity)
    return instance


def read_xbrl_occurrences(
    body: bytes, *, capture: CaptureReference, member: PackageMember, mapping_set: MappingSet
) -> tuple[Occurrence, ...]:
    """Every numeric fact and every named text fact of one instance, as occurrences.

    Raises :class:`UnsupportedSchemaError` when the instance's namespace is not in the
    mapping set's supported schemas (or matches no registered taxonomy).
    """
    return occurrences_from_instance(
        parse_instance(body, mapping_set=mapping_set),
        capture=capture,
        member=member,
        mapping_set=mapping_set,
    )


def occurrences_from_instance(
    instance: RawXbrlInstance,
    *,
    capture: CaptureReference,
    member: PackageMember,
    mapping_set: MappingSet,
) -> tuple[Occurrence, ...]:
    """Occurrences of an already parsed instance (see :func:`read_xbrl_occurrences`)."""
    # Document order distinguishes unanchored facts, but is not payload identity
    # when two facts explicitly claim the same native id.
    unique: dict[str, RawXbrlFact] = {}
    for fact in instance.facts:
        anchor = anchor_key_of(fact)
        previous = unique.get(anchor)
        if previous is not None:
            if previous.model_dump(exclude={"document_order"}) != fact.model_dump(
                exclude={"document_order"}
            ):
                raise XbrlParseError(f"duplicate XBRL anchor {anchor!r} has differing payloads")
            continue
        unique[anchor] = fact
    facts = tuple(unique.values())
    ambiguous = _ambiguous_raw_periods(facts)
    descriptions = _member_descriptions(facts, instance.schema_identity)
    basis = _BASIS_OF_SCOPE[instance.scope]
    return tuple(
        _occurrence(
            fact,
            instance=instance,
            capture=capture,
            member=member,
            basis=basis,
            period_ambiguous=_is_ambiguous(fact, ambiguous),
            descriptions=descriptions,
        )
        for fact in facts
    )


def anchor_key_of(fact: RawXbrlFact) -> str:
    """The fact id, or the context ref plus document order."""
    if fact.fact_id:
        return f"xbrl:{fact.fact_id}"
    return f"xbrl:{fact.context_ref}:{fact.document_order}"


def member_slug(description: str) -> str:
    """Member id from a filed description (dictionary template ``segment`` rule)."""
    return re.sub(r"[^a-z0-9]+", "_", description.lower()).strip("_")


def _occurrence(
    fact: RawXbrlFact,
    *,
    instance: RawXbrlInstance,
    capture: CaptureReference,
    member: PackageMember,
    basis: str,
    period_ambiguous: bool,
    descriptions: Mapping[tuple[tuple[str, str], ...], tuple[str, str]],
) -> Occurrence:
    """One fact as an occurrence."""
    text = fact.raw_text
    precision, declared = _precision(fact)
    member_descriptions = {}
    if fact.dimension_qnames and fact.dimension_qnames in descriptions:
        description, anchor_key = descriptions[fact.dimension_qnames]
        member_descriptions = {
            axis: {"text": description, "anchor_key": anchor_key}
            for axis, _ in fact.dimension_qnames
        }
    return Occurrence(
        occurrence_id=None,
        capture=capture,
        representation=Representation.XBRL,
        extractor_version=XBRL_EXTRACTOR_VERSION,
        native_field=fact.concept_qname,
        raw_value_text=text,
        raw_unit=fact.unit_measure or "",
        raw_scale=0,
        raw_sign=-1 if text is not None and text.strip().startswith("-") else 1,
        precision_kind=precision,
        declared_precision=declared,
        native_context={
            CONTEXT_SCHEMA_IDENTITY: instance.schema_identity,
            CONTEXT_BASIS: basis,
            CONTEXT_LOCAL_NAME: _local(fact.concept_qname),
            CONTEXT_NAMESPACE: fact.namespace_uri,
            CONTEXT_DIMENSION_AXES: [
                axis for axis, _ in (fact.dimension_qnames or fact.dimensions)
            ],
            "concept_qname": fact.concept_qname,
            "context_ref": fact.context_ref,
            "dimensions": [list(pair) for pair in fact.dimensions],
            "dimension_qnames": [list(pair) for pair in fact.dimension_qnames],
            "entity": {"scheme": fact.entity_scheme, "identifier": fact.entity_id},
            "raw_period": fact.raw_period.model_dump(mode="json"),
            "period_declaration": (
                list(fact.period_declaration) if fact.period_declaration is not None else None
            ),
            CONTEXT_PERIOD_AMBIGUOUS: period_ambiguous,
            "decimals": fact.decimals_raw,
            "is_nil": fact.is_nil,
            CONTEXT_MEMBER_DESCRIPTIONS: member_descriptions,
        },
        period=fact.period,
        missing_state=_missing_state(fact),
        disclosure={
            "taxonomy_registry_version": instance.taxonomy.registry_version,
            "schema_identity": instance.schema_identity,
        },
        anchor={
            "fact_id": fact.fact_id,
            "context_ref": fact.context_ref,
            "document_order": fact.document_order,
        },
        anchor_key=anchor_key_of(fact),
        knowledge_time=member.knowledge_time,
        knowledge_time_status=member.knowledge_time_status,
        first_seen_at=capture.first_seen_at,
        revision_cause=RevisionCause.ORIGINAL,
    )


def _local(qname: str) -> str:
    """The local name of a prefixed name."""
    return qname.rsplit(":", 1)[-1]


def _missing_state(fact: RawXbrlFact) -> MissingValueState:
    """``NIL`` for a nil fact, ``ZERO_PRINTED`` for a filed zero, else ``VALUE``."""
    if fact.is_nil:
        return MissingValueState.NIL
    if fact.is_numeric and fact.raw_text is not None and _ZERO.fullmatch(fact.raw_text.strip()):
        return MissingValueState.ZERO_PRINTED
    return MissingValueState.VALUE


def _precision(fact: RawXbrlFact) -> tuple[PrecisionKind, int | None]:
    """``INF`` is exact, an integer is finite, anything else unsupported."""
    decimals = (fact.decimals_raw or "").strip()
    if decimals == DECIMALS_INFINITE:
        return PrecisionKind.EXACT, None
    if _SIGNED_NUMBER.fullmatch(decimals) and "." not in decimals:
        return PrecisionKind.FINITE, int(decimals)
    return PrecisionKind.UNSUPPORTED, None


def _ambiguous_raw_periods(facts: Sequence[RawXbrlFact]) -> frozenset[tuple[object, ...]]:
    """Raw duration periods that two declared contexts repaired to different periods.

    Such a raw period cannot tell an undeclared context sharing it which period it means
    (Apar FY25 Q2: ``OneD`` and ``FourD`` both carry 2024-07-01..2024-09-30).
    """
    repaired: dict[tuple[object, ...], set[tuple[object, ...]]] = {}
    for fact in facts:
        if fact.period_declaration is None:
            continue
        raw = (fact.raw_period.start, fact.raw_period.end, fact.raw_period.instant)
        repaired.setdefault(raw, set()).add((fact.period.start, fact.period.end))
    return frozenset(raw for raw, periods in repaired.items() if len(periods) > 1)


def _is_ambiguous(fact: RawXbrlFact, ambiguous: frozenset[tuple[object, ...]]) -> bool:
    """An undeclared context whose raw period two declared contexts read differently."""
    raw = (fact.raw_period.start, fact.raw_period.end, fact.raw_period.instant)
    return fact.period_declaration is None and raw in ambiguous


def _member_descriptions(
    facts: Sequence[RawXbrlFact], schema_identity: str
) -> Mapping[tuple[tuple[str, str], ...], tuple[str, str]]:
    """The one filed description per dimension set, with its anchor key.

    Only the schema's own ``DescriptionOfReportableSegment`` counts; a dimension set whose
    descriptions disagree resolves to no member.
    """
    found: dict[tuple[tuple[str, str], ...], set[str]] = {}
    anchors: dict[tuple[tuple[str, str], ...], str] = {}
    for fact in facts:
        if (
            fact.namespace_uri != schema_identity
            or _local(fact.concept_qname) != SEGMENT_DESCRIPTION_CONCEPT
            or not fact.dimension_qnames
        ):
            continue
        text = (fact.raw_text or "").strip()
        found.setdefault(fact.dimension_qnames, set()).add(text)
        anchors.setdefault(fact.dimension_qnames, anchor_key_of(fact))
    return {
        dimensions: (next(iter(texts)), anchors[dimensions])
        for dimensions, texts in found.items()
        if len(texts) == 1 and next(iter(texts))
    }
