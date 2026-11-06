"""Mapping set and normalisation policy: models and validating loaders (D1a Task 5).

A mapping set is ``<root>/<version>.yaml`` naming its member files: XBRL entry files (one
per schema identity), PDF layout files, source-scoped constructions and structural
statement anchors. Its pin is the SHA-256 over the index and every member file (design
decision 7). The loader refuses dangling ids, schema defects and overlapping selectors
(design decision 9) with every offender named.

An entry or construction naming a ``source`` applies to that source only; one with no source
applies to every source of its surface. Runtime matching takes the source, the XBRL fact's
own namespace URI and the selector; two entries matching one native field fail closed.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from enum import StrEnum
from itertools import combinations
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from equity_os.contracts.measurement.canonical import (
    PeriodKind,
    PeriodNature,
    Representation,
)
from equity_os.contracts.measurement.evidence import Occurrence
from equity_os.contracts.measurement.qualification import QualificationScope
from equity_os.extraction.results_pdf.pdf_header_text import normalize_text_tokens
from equity_os.normalisation.dictionary.dictionary import (
    CanonicalDictionary,
)
from equity_os.normalisation.mapping.mapping_models import (
    AnchorPeriodShape,
    ConstructionOperand,
    ConstructionRule,
    DashRule,
    MappingEntry,
    MemberSource,
    NormalisationPolicy,
    PdfPeriodRule,
    PeriodShape,
    PrecisionRule,
    Selector,
    StatementAnchor,
    UnitRule,
    UnitTransform,
    UnmappedLabel,
    selector_matches,
)

__all__ = [
    "AnchorPeriodShape",
    "AmbiguousMappingError",
    "ConstructionOperand",
    "ConstructionRule",
    "DashRule",
    "MappingDefect",
    "MappingEntry",
    "MappingLoadError",
    "MappingSet",
    "MemberSource",
    "NormalisationPolicy",
    "PdfPeriodRule",
    "PeriodShape",
    "PrecisionRule",
    "Selector",
    "StatementAnchor",
    "UnitRule",
    "UnitTransform",
    "UnsupportedSchemaError",
    "applies_to_source",
    "load_mapping_set",
    "load_normalisation_policy",
    "selects",
]

# Keys every adapter writes into ``Occurrence.native_context`` for matching.
CONTEXT_SCHEMA_IDENTITY = "schema_identity"
CONTEXT_NAMESPACE = "namespace_uri"
CONTEXT_BASIS = "basis"
CONTEXT_LOCAL_NAME = "local_name"
CONTEXT_DIMENSION_AXES = "dimension_axes"
CONTEXT_STATEMENT_FAMILY = "statement_family"
CONTEXT_LABEL = "label"
CONTEXT_SECTION = "section"
CONTEXT_LABEL_ORDINAL = "label_ordinal"
CONTEXT_COLUMN_HEADER = "column_header"

_LOAD_FAILED = "mapping set load failed: {defect} for {ids}{detail}"
_UNSUPPORTED = "schema {schema!r} is not supported by mapping set {version}"
_AMBIGUOUS = "entries {entry_ids} all match native field {native_field!r}"


class MappingDefect(StrEnum):
    """Why a mapping set failed to load."""

    DANGLING_CANONICAL_ID = "DANGLING_CANONICAL_ID"
    DANGLING_ENTRY_ID = "DANGLING_ENTRY_ID"
    DUPLICATE_SELECTOR = "DUPLICATE_SELECTOR"
    SCHEMA = "SCHEMA"


class MappingLoadError(ValueError):
    """The mapping set or normalisation policy is invalid; ``ids`` names every offender."""

    def __init__(self, defect: MappingDefect, ids: Iterable[str], detail: str = "") -> None:
        self.defect = defect
        self.ids = tuple(sorted(set(ids)))
        suffix = f": {detail}" if detail else ""
        super().__init__(_LOAD_FAILED.format(defect=defect, ids=list(self.ids), detail=suffix))


class UnsupportedSchemaError(ValueError):
    """A member's schema identity is outside the mapping set's supported schemas."""

    def __init__(self, schema: str, version: str) -> None:
        self.schema = schema
        super().__init__(_UNSUPPORTED.format(schema=schema, version=version))


class AmbiguousMappingError(LookupError):
    """More than one entry matches one occurrence; no entry may be chosen by file order."""

    def __init__(self, native_field: str, entry_ids: Sequence[str]) -> None:
        self.entry_ids = tuple(entry_ids)
        super().__init__(_AMBIGUOUS.format(entry_ids=list(entry_ids), native_field=native_field))


class MappingSet(BaseModel):
    """A loaded, validated mapping set version with its content pin."""

    model_config = ConfigDict(frozen=True)

    version: str
    content_sha256: str
    normalisation_policy_version: str
    entries: tuple[MappingEntry, ...]
    constructions: tuple[ConstructionRule, ...]
    statement_anchors: tuple[StatementAnchor, ...]
    supported_schemas: frozenset[str]
    unmapped: Mapping[str, tuple[UnmappedLabel, ...]] = Field(default_factory=dict)
    """Reviewed unmapped vendor labels, by surface."""

    def entry(self, entry_id: str) -> MappingEntry:
        """The entry with this id; an unknown id raises ``KeyError``."""
        for candidate in self.entries:
            if candidate.entry_id == entry_id:
                return candidate
        raise KeyError(entry_id)

    def require_schema(self, schema_identity: str) -> None:
        """Raise :class:`UnsupportedSchemaError` for a schema this set does not map."""
        if schema_identity not in self.supported_schemas:
            raise UnsupportedSchemaError(schema_identity, self.version)

    def matches(
        self, occurrence: Occurrence, *, period_kind: PeriodKind | None = None
    ) -> tuple[MappingEntry, ...]:
        """Every entry whose source, scope and selector match the occurrence."""
        context = occurrence.native_context
        schema = context.get(CONTEXT_SCHEMA_IDENTITY)
        basis = context.get(CONTEXT_BASIS)
        candidates = tuple(
            entry
            for entry in self.entries
            if applies_to_source(entry.source, occurrence.capture.source_id)
            and entry.surface == occurrence.capture.surface
            and entry.schema_identity == schema
            and basis in {member.value for member in entry.basis}
            and (period_kind is None or period_kind in entry.period_kinds)
        )
        selected = tuple(entry for entry in candidates if selects(entry, occurrence))
        if selected or occurrence.representation is Representation.XBRL:
            return selected
        # A repeated label with explicit but unestablished section identities is
        # ambiguous evidence, not absence. Interpretation retains all candidates
        # and fails INVALID rather than assigning another section's value.
        labelled = tuple(
            entry
            for entry in candidates
            if entry.selector.unestablished_section_ambiguous
            and entry.selector.section_equals is not None
            and context.get(CONTEXT_STATEMENT_FAMILY) == entry.selector.statement_family
            and tuple(normalize_text_tokens(str(context.get(CONTEXT_LABEL, ""))))
            in {tuple(normalize_text_tokens(label)) for label in entry.selector.labels}
        )
        return labelled if len(labelled) > 1 else selected

    def match(
        self, occurrence: Occurrence, *, period_kind: PeriodKind | None = None
    ) -> MappingEntry | None:
        """The one matching entry, or ``None``; several raise :class:`AmbiguousMappingError`."""
        found = self.matches(occurrence, period_kind=period_kind)
        if len(found) > 1:
            raise AmbiguousMappingError(
                occurrence.native_field, [entry.entry_id for entry in found]
            )
        return found[0] if found else None


def applies_to_source(source: str | None, source_id: str) -> bool:
    """A source-generic entry or rule applies to every source; a named one to itself only."""
    return source is None or source == source_id


def in_namespace(context: Mapping[str, object], schema_identity: str) -> bool:
    """Whether an XBRL occurrence's element is declared in this schema's namespace."""
    return context.get(CONTEXT_NAMESPACE) == schema_identity


def matches_dimensions(
    context: Mapping[str, object],
    schema_identity: str,
    axis: str | None,
    member: str | None = None,
) -> bool:
    """Dimension identities must name this schema's explicit axis and member namespaces,
    and the selector's member when it names one."""
    native = context.get("dimensions")
    axes = context.get(CONTEXT_DIMENSION_AXES)
    found = tuple(axes) if isinstance(axes, list | tuple) else ()
    if axis is None:
        return not found and not native
    wanted = f"{{{schema_identity}}}{axis}"
    qualified = context.get("dimension_qnames")
    if found != (wanted,) or not isinstance(qualified, list | tuple) or len(qualified) != 1:
        return False
    pair = qualified[0]
    return (
        isinstance(pair, list | tuple)
        and len(pair) == 2
        and pair[0] == wanted
        and isinstance(pair[1], str)
        and pair[1].startswith(f"{{{schema_identity}}}")
        and (member is None or pair[1] == f"{{{schema_identity}}}{member}")
    )


def selects(entry: MappingEntry, occurrence: Occurrence) -> bool:
    """Whether one entry's selector matches one occurrence's native field and context."""
    selector = entry.selector
    context = occurrence.native_context
    if selector.native_field is not None:
        if (
            context.get(CONTEXT_LOCAL_NAME) != selector.native_field
            or not in_namespace(context, entry.schema_identity)
            or occurrence.period is None
        ):
            return False
        is_instant = occurrence.period.instant is not None
        if is_instant != (selector.period_shape is PeriodShape.INSTANT):
            return False
        return matches_dimensions(
            context, entry.schema_identity, selector.dimension_axis, selector.dimension_member
        )
    return selector_matches(selector, context)


# --- loading -------------------------------------------------------------------


class _Index(BaseModel):
    """``<version>.yaml``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str = Field(min_length=1)
    normalisation_policy_version: str = Field(min_length=1)
    entry_files: tuple[str, ...] = Field(min_length=1)
    construction_files: tuple[str, ...] = ()
    statement_anchor_files: tuple[str, ...] = ()


class _EntryFile(BaseModel):
    """One entry file: scope shared by its entries, defaults, and the entries."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str | None = None
    surface: str
    schema_identity: str
    defaults: Mapping[str, Any] = Field(default_factory=dict)
    entries: tuple[Mapping[str, Any], ...]
    unmapped: tuple[UnmappedLabel, ...] = ()


class _ConstructionFile(BaseModel):
    """A constructions file."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    constructions: tuple[ConstructionRule, ...]


class _AnchorFile(BaseModel):
    """A statement-anchors file."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    statement_anchors: tuple[StatementAnchor, ...]


class _PolicyFile(BaseModel):
    """The normalisation policy file as written."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str = Field(min_length=1)
    units: tuple[UnitRule, ...]
    dash_rules: tuple[DashRule, ...] = ()


def load_normalisation_policy(path: Path) -> NormalisationPolicy:
    """Load a normalisation policy, pinned by the SHA-256 of its bytes."""
    body = path.read_bytes()
    try:
        parsed = _PolicyFile.model_validate(yaml.safe_load(body))
    except (ValidationError, yaml.YAMLError) as error:
        raise MappingLoadError(MappingDefect.SCHEMA, [path.name], _flat(error)) from error
    units = [rule.raw_unit for rule in parsed.units]
    rules = [rule.rule_id for rule in parsed.dash_rules]
    repeated = {u for u in units if units.count(u) > 1} | {r for r in rules if rules.count(r) > 1}
    if repeated:
        raise MappingLoadError(MappingDefect.DUPLICATE_SELECTOR, repeated)
    return NormalisationPolicy(
        version=parsed.version,
        content_sha256=hashlib.sha256(body).hexdigest(),
        units={rule.raw_unit: rule for rule in parsed.units},
        dash_rules={rule.rule_id: rule for rule in parsed.dash_rules},
    )


def load_mapping_set(root: Path, version: str, *, dictionary: CanonicalDictionary) -> MappingSet:
    """Load and validate mapping set ``version`` from ``root/<version>.yaml``.

    Raises :class:`MappingLoadError` with the first failing defect class (schema,
    dangling canonical id, dangling entry id, overlapping selector) and every offender.
    """
    index_path = root / f"{version}.yaml"
    bodies: dict[Path, bytes] = {}
    index = _parse(_Index, index_path, version, bodies=bodies)
    if index.version != version:
        raise MappingLoadError(MappingDefect.SCHEMA, [index.version], "version mismatch")
    entries: list[MappingEntry] = []
    unmapped: dict[str, tuple[UnmappedLabel, ...]] = {}
    failures: dict[str, str] = {}
    for name in index.entry_files:
        path = root / name
        entry_file = _parse(_EntryFile, path, name, bodies=bodies)
        scope = {
            "source": entry_file.source,
            "surface": entry_file.surface,
            "schema_identity": entry_file.schema_identity,
        }
        if entry_file.unmapped:
            known = unmapped.get(entry_file.surface, ())
            unmapped[entry_file.surface] = known + entry_file.unmapped
        for position, raw in enumerate(entry_file.entries):
            label = str(raw.get("entry_id", f"{name}[{position}]"))
            try:
                entries.append(MappingEntry.model_validate({**entry_file.defaults, **scope, **raw}))
            except ValidationError as error:
                failures[label] = _flat(error)
    if failures:
        detail = " | ".join(f"{key}: {reason}" for key, reason in failures.items())
        raise MappingLoadError(MappingDefect.SCHEMA, failures, detail)
    constructions: list[ConstructionRule] = []
    for name in index.construction_files:
        constructions.extend(
            _parse(_ConstructionFile, root / name, name, bodies=bodies).constructions
        )
    anchors: list[StatementAnchor] = []
    for name in index.statement_anchor_files:
        anchors.extend(_parse(_AnchorFile, root / name, name, bodies=bodies).statement_anchors)
    _check_schema(entries, constructions, dictionary)
    _check_dangling_canonical(entries, constructions, dictionary)
    _check_dangling_entries(entries, constructions)
    _check_duplicates(entries, constructions)
    return MappingSet(
        version=index.version,
        content_sha256=_content_sha256(bodies),
        normalisation_policy_version=index.normalisation_policy_version,
        entries=tuple(entries),
        constructions=tuple(constructions),
        statement_anchors=tuple(anchors),
        unmapped=unmapped,
        supported_schemas=frozenset(
            [
                *(entry.schema_identity for entry in entries),
                *(rule.schema_identity for rule in constructions),
            ]
        ),
    )


def _parse[M: BaseModel](model: type[M], path: Path, label: str, *, bodies: dict[Path, bytes]) -> M:
    """Parse one YAML file into ``model``; any failure is a ``SCHEMA`` defect."""
    try:
        if path not in bodies:
            bodies[path] = path.read_bytes()
        return model.model_validate(yaml.safe_load(bodies[path]))
    except (ValidationError, yaml.YAMLError, OSError) as error:
        raise MappingLoadError(MappingDefect.SCHEMA, [label], _flat(error)) from error


def _flat(error: Exception) -> str:
    """An error message on one line."""
    return " ".join(str(error).split())


def _check_schema(
    entries: Sequence[MappingEntry],
    constructions: Sequence[ConstructionRule],
    dictionary: CanonicalDictionary,
) -> None:
    """Entry ids are unique, and each entry's period shape fits its row's period nature."""
    offenders: set[str] = set()
    ids = [entry.entry_id for entry in entries] + [rule.rule_id for rule in constructions]
    offenders.update(entry_id for entry_id in ids if ids.count(entry_id) > 1)
    known = {row.canonical_id: row for row in dictionary.rows}
    for entry in entries:
        row = known.get(entry.canonical_id)
        if row is None:
            continue
        instant = row.period_nature is PeriodNature.INSTANT
        if entry.selector.period_shape is not None:
            fits = (entry.selector.period_shape is PeriodShape.INSTANT) == instant
        else:
            fits = (entry.period_rule is PdfPeriodRule.COLUMN_DURATION) != instant
        templated = row.dimension_template is not None
        dimensioned = bool(entry.dimension_members) or entry.member_source is not None
        if not fits or templated != dimensioned:
            offenders.add(entry.entry_id)
    for rule in constructions:
        names = [operand.name for operand in rule.operands]
        if len(set(names)) != len(names) or rule.expression.operand_names() != set(names):
            offenders.add(rule.rule_id)
        row = known.get(rule.canonical_id)
        selector = any(operand.selector for operand in rule.operands)
        if selector and row is not None and row.dimension_template is not None:
            offenders.add(rule.rule_id)
    if offenders:
        raise MappingLoadError(MappingDefect.SCHEMA, offenders)


def _check_dangling_canonical(
    entries: Sequence[MappingEntry],
    constructions: Sequence[ConstructionRule],
    dictionary: CanonicalDictionary,
) -> None:
    """Every canonical id, including qualification conditions, is a dictionary row."""
    known = {row.canonical_id for row in dictionary.rows}
    offenders: set[str] = set()
    scoped: list[tuple[str, QualificationScope | None]] = [
        (entry.canonical_id, entry.qualification) for entry in entries
    ] + [(rule.canonical_id, rule.qualification) for rule in constructions]
    for canonical_id, scope in scoped:
        if canonical_id not in known:
            offenders.add(canonical_id)
        if scope is not None:
            offenders.update(
                condition.canonical_id
                for condition in scope.conditions + scope.exclusions
                if condition.canonical_id not in known
            )
    if offenders:
        raise MappingLoadError(MappingDefect.DANGLING_CANONICAL_ID, offenders)


def _check_dangling_entries(
    entries: Sequence[MappingEntry], constructions: Sequence[ConstructionRule]
) -> None:
    """Every construction operand names an entry of the construction's own scope.

    A source-generic rule takes source-generic operands; a source-named rule takes its own
    source's or source-generic ones.
    """
    by_id = {entry.entry_id: entry for entry in entries}
    offenders: set[str] = set()
    for rule in constructions:
        for operand in rule.operands:
            if operand.mapping_entry_id is None:
                continue
            entry = by_id.get(operand.mapping_entry_id)
            if (
                entry is None
                or (entry.surface, entry.schema_identity) != (rule.surface, rule.schema_identity)
                or entry.source not in (None, rule.source)
            ):
                offenders.add(operand.mapping_entry_id)
    if offenders:
        raise MappingLoadError(MappingDefect.DANGLING_ENTRY_ID, offenders)


def _check_duplicates(
    entries: Sequence[MappingEntry], constructions: Sequence[ConstructionRule]
) -> None:
    """Refuse two entries (or constructions) of one scope that overlap or emit one measurement.

    Scope is (surface, schema identity) with overlapping sources (equal, or either one
    source-generic), bases and period kinds; the same native name under another schema is
    legitimate. Nothing is decided by file order: an overlap is a defect.
    """
    offenders: set[str] = set()
    for left, right in combinations(entries, 2):
        if not _same_scope(left, right):
            continue
        if (
            left.selector.overlaps(right.selector)
            or left.emitted_measurement() == right.emitted_measurement()
        ):
            offenders.update((left.entry_id, right.entry_id))
    for left_rule, right_rule in combinations(constructions, 2):
        if (left_rule.surface, left_rule.schema_identity, left_rule.canonical_id) == (
            right_rule.surface,
            right_rule.schema_identity,
            right_rule.canonical_id,
        ) and _sources_overlap(left_rule.source, right_rule.source):
            offenders.update((left_rule.rule_id, right_rule.rule_id))
    for rule in constructions:
        offenders.update(
            entry.entry_id
            for entry in entries
            if (entry.surface, entry.schema_identity, entry.canonical_id)
            == (rule.surface, rule.schema_identity, rule.canonical_id)
            and _sources_overlap(entry.source, rule.source)
            and not entry.dimension_members
        )
    if offenders:
        raise MappingLoadError(MappingDefect.DUPLICATE_SELECTOR, offenders)


def _same_scope(left: MappingEntry, right: MappingEntry) -> bool:
    """Same surface and schema with overlapping sources, bases and period kinds."""
    return (
        (left.surface, left.schema_identity) == (right.surface, right.schema_identity)
        and _sources_overlap(left.source, right.source)
        and bool(left.basis & right.basis)
        and bool(left.period_kinds & right.period_kinds)
    )


def _sources_overlap(left: str | None, right: str | None) -> bool:
    """Whether some source both apply to: equal, or either one source-generic."""
    return left is None or right is None or left == right


def _content_sha256(bodies: Mapping[Path, bytes]) -> str:
    """SHA-256 over the index and every member file, in load order."""
    digest = hashlib.sha256()
    for path, body in bodies.items():
        digest.update(path.name.encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(body).hexdigest().encode("ascii") + b"\n")
    return digest.hexdigest()
