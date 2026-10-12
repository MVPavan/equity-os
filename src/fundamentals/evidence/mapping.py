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
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from fundamentals.canon.dictionary import CanonicalDictionary, FormulaNode
from fundamentals.contracts.canonical import (
    Basis,
    PeriodKind,
    PeriodNature,
    StatementFamily,
    ValueKind,
)
from fundamentals.contracts.evidence import Occurrence
from fundamentals.contracts.evidence_tier import EvidenceTier
from fundamentals.contracts.qualification import QualificationScope
from fundamentals.extract.pdf_header_text import normalize_text_tokens

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

ALL_BASES = frozenset(Basis)
ALL_PERIOD_KINDS = frozenset(PeriodKind)
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


class PeriodShape(StrEnum):
    """Whether an XBRL selector takes duration or instant contexts."""

    DURATION = "DURATION"
    INSTANT = "INSTANT"


class PdfPeriodRule(StrEnum):
    """How a PDF row's key period follows from its column header (row-aware, R5)."""

    COLUMN_DURATION = "COLUMN_DURATION"
    COLUMN_OPENING_INSTANT = "COLUMN_OPENING_INSTANT"
    COLUMN_CLOSING_INSTANT = "COLUMN_CLOSING_INSTANT"
    COLUMN_INSTANT = "COLUMN_INSTANT"


class MemberSource(StrEnum):
    """Where a templated entry's entity-evidence member comes from."""

    XBRL_DESCRIPTION = "XBRL_DESCRIPTION"


class UnitTransform(StrEnum):
    """How a raw value becomes base units: ``value × 10^raw_scale``."""

    SCALE_TO_BASE_UNIT = "SCALE_TO_BASE_UNIT"


class PrecisionRule(StrEnum):
    """Where the uncertainty interval comes from: the occurrence's declared precision."""

    DECLARED = "DECLARED"


class AnchorPeriodShape(StrEnum):
    """The period a statement anchor must be filed for, relative to the package period end."""

    INSTANT_AT_PERIOD_END = "INSTANT_AT_PERIOD_END"
    DURATION_ENDING_AT_PERIOD_END = "DURATION_ENDING_AT_PERIOD_END"


class Selector(BaseModel):
    """The native field and context predicate an entry matches.

    XBRL: ``native_field`` (element local name), ``period_shape`` and the one
    ``dimension_axis`` the context carries (``None``: no dimensions). PDF:
    ``statement_family``, label variants, and optionally the nearest section heading,
    the label's ordinal within the block and a column-header marker.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    native_field: str | None = None
    period_shape: PeriodShape | None = None
    dimension_axis: str | None = None
    statement_family: StatementFamily | None = None
    labels: tuple[str, ...] = ()
    section: str | None = None
    label_ordinal: int | None = Field(default=None, ge=1)
    column_header: str | None = None

    @model_validator(mode="after")
    def _one_kind(self) -> Selector:
        """An XBRL selector names an element; a PDF selector names a family and labels."""
        xbrl = self.native_field is not None
        pdf = self.statement_family is not None
        if xbrl == pdf or (xbrl and self.period_shape is None) or (pdf and not self.labels):
            raise ValueError("a selector is either XBRL (element, period shape) or PDF (labels)")
        return self

    def overlaps(self, other: Selector) -> bool:
        """Whether some native field and context could satisfy both selectors.

        XBRL: same element, period shape and axis. PDF: same family and a shared label
        variant, with each optional predicate unrestricted on one side, equal, or (section,
        column header) one token run containing the other.
        """
        if (self.native_field is None) != (other.native_field is None):
            return False
        if self.native_field is not None:
            return (self.native_field, self.period_shape, self.dimension_axis) == (
                other.native_field,
                other.period_shape,
                other.dimension_axis,
            )
        labels = {tuple(normalize_text_tokens(label)) for label in self.labels}
        return (
            self.statement_family == other.statement_family
            and bool(labels & {tuple(normalize_text_tokens(label)) for label in other.labels})
            and (
                self.label_ordinal is None
                or other.label_ordinal is None
                or self.label_ordinal == other.label_ordinal
            )
            and _compatible(self.section, other.section)
            and _compatible(self.column_header, other.column_header)
        )


class MappingEntry(BaseModel):
    """One evidenced native-to-canonical mapping with its tier and qualification scope."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entry_id: str = Field(min_length=1)
    source: str | None = Field(default=None, min_length=1)
    surface: str = Field(min_length=1)
    schema_identity: str = Field(min_length=1)
    selector: Selector
    canonical_id: str = Field(min_length=1)
    dimension_members: Mapping[str, str] = Field(default_factory=dict)
    member_source: MemberSource | None = None
    sign: int = Field(default=1)
    unit_transform: UnitTransform = UnitTransform.SCALE_TO_BASE_UNIT
    precision_rule: PrecisionRule = PrecisionRule.DECLARED
    period_rule: PdfPeriodRule | None = None
    tier: EvidenceTier = EvidenceTier.EQUIVALENCE_UNPROVEN
    qualification: QualificationScope | None = None
    basis: frozenset[Basis] = ALL_BASES
    period_kinds: frozenset[PeriodKind] = ALL_PERIOD_KINDS
    evidence_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def _well_formed(self) -> MappingEntry:
        """Signs are ±1; a PDF entry carries a period rule and an XBRL entry none."""
        if self.sign not in (1, -1):
            raise ValueError("sign must be 1 or -1")
        if (self.period_rule is None) != (self.selector.native_field is not None):
            raise ValueError("PDF entries carry a period_rule; XBRL entries carry none")
        return self

    def emitted_measurement(self) -> tuple[object, ...]:
        """Canonical id and dimension selector this entry emits (duplicate check)."""
        return (
            self.canonical_id,
            tuple(sorted(self.dimension_members.items())),
            self.member_source,
        )


class ConstructionOperand(BaseModel):
    """One named operand of a construction: a mapping entry, optionally dash-ruled."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    mapping_entry_id: str = Field(min_length=1)
    dash_rule_id: str | None = None


class ConstructionRule(BaseModel):
    """A reported value assembled from one capture's own lines (``origin=CONSTRUCTED``)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str = Field(min_length=1)
    source: str | None = Field(default=None, min_length=1)
    surface: str = Field(min_length=1)
    schema_identity: str = Field(min_length=1)
    canonical_id: str = Field(min_length=1)
    operands: tuple[ConstructionOperand, ...] = Field(min_length=1)
    expression: FormulaNode
    tier: EvidenceTier = EvidenceTier.EQUIVALENCE_UNPROVEN
    qualification: QualificationScope | None = None
    evidence_ref: str = Field(min_length=1)


class StatementAnchor(BaseModel):
    """Native fields whose filing at the package period end shows a statement is present."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_identity: str = Field(min_length=1)
    statement_family: StatementFamily
    native_fields: frozenset[str] = Field(min_length=1)
    period_shape: AnchorPeriodShape


class DashRule(BaseModel):
    """Reads a printed dash as exact zero for one operand of one construction only."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str = Field(min_length=1)
    construction_rule_id: str = Field(min_length=1)
    operand_name: str = Field(min_length=1)
    evidence_ref: str = Field(min_length=1)


class UnitRule(BaseModel):
    """What one raw unit means: its value kind and currency."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    raw_unit: str = Field(min_length=1)
    value_kind: ValueKind
    currency: str | None
    evidence_ref: str = Field(min_length=1)


class NormalisationPolicy(BaseModel):
    """Raw-unit meanings and construction-scoped dash rules, pinned by content."""

    model_config = ConfigDict(frozen=True)

    version: str
    content_sha256: str
    units: Mapping[str, UnitRule]
    dash_rules: Mapping[str, DashRule]


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
        return tuple(
            entry
            for entry in self.entries
            if applies_to_source(entry.source, occurrence.capture.source_id)
            and entry.surface == occurrence.capture.surface
            and entry.schema_identity == schema
            and basis in {member.value for member in entry.basis}
            and (period_kind is None or period_kind in entry.period_kinds)
            and _selects(entry, occurrence)
        )

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


def _selects(entry: MappingEntry, occurrence: Occurrence) -> bool:
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
        axes = context.get(CONTEXT_DIMENSION_AXES)
        found = tuple(axes) if isinstance(axes, list | tuple) else ()
        wanted = () if selector.dimension_axis is None else (selector.dimension_axis,)
        return found == wanted
    if context.get(CONTEXT_STATEMENT_FAMILY) != selector.statement_family:
        return False
    label = normalize_text_tokens(str(context.get(CONTEXT_LABEL, "")))
    if all(normalize_text_tokens(variant) != label for variant in selector.labels):
        return False
    if selector.section is not None and not _contains(
        normalize_text_tokens(str(context.get(CONTEXT_SECTION, ""))),
        normalize_text_tokens(selector.section),
    ):
        return False
    if (
        selector.label_ordinal is not None
        and context.get(CONTEXT_LABEL_ORDINAL) != selector.label_ordinal
    ):
        return False
    return selector.column_header is None or _contains(
        normalize_text_tokens(str(context.get(CONTEXT_COLUMN_HEADER, ""))),
        normalize_text_tokens(selector.column_header),
    )


def _contains(haystack: Sequence[str], needle: Sequence[str]) -> bool:
    """Whether ``needle`` occurs as a contiguous token run in ``haystack``."""
    width = len(needle)
    return width > 0 and any(
        list(haystack[i : i + width]) == list(needle) for i in range(len(haystack) - width + 1)
    )


def _compatible(left: str | None, right: str | None) -> bool:
    """Two "contains" predicates one text could satisfy: either unset, or one inside the other."""
    if left is None or right is None:
        return True
    left_tokens, right_tokens = normalize_text_tokens(left), normalize_text_tokens(right)
    return _contains(left_tokens, right_tokens) or _contains(right_tokens, left_tokens)


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
    files: list[Path] = [index_path]
    index = _parse(_Index, index_path, version)
    if index.version != version:
        raise MappingLoadError(MappingDefect.SCHEMA, [index.version], "version mismatch")
    entries: list[MappingEntry] = []
    failures: dict[str, str] = {}
    for name in index.entry_files:
        path = root / name
        files.append(path)
        entry_file = _parse(_EntryFile, path, name)
        scope = {
            "source": entry_file.source,
            "surface": entry_file.surface,
            "schema_identity": entry_file.schema_identity,
        }
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
        files.append(root / name)
        constructions.extend(_parse(_ConstructionFile, root / name, name).constructions)
    anchors: list[StatementAnchor] = []
    for name in index.statement_anchor_files:
        files.append(root / name)
        anchors.extend(_parse(_AnchorFile, root / name, name).statement_anchors)
    _check_schema(entries, constructions, dictionary)
    _check_dangling_canonical(entries, constructions, dictionary)
    _check_dangling_entries(entries, constructions)
    _check_duplicates(entries, constructions)
    return MappingSet(
        version=index.version,
        content_sha256=_content_sha256(files),
        normalisation_policy_version=index.normalisation_policy_version,
        entries=tuple(entries),
        constructions=tuple(constructions),
        statement_anchors=tuple(anchors),
        supported_schemas=frozenset(entry.schema_identity for entry in entries),
    )


def _parse[M: BaseModel](model: type[M], path: Path, label: str) -> M:
    """Parse one YAML file into ``model``; any failure is a ``SCHEMA`` defect."""
    try:
        return model.model_validate(yaml.safe_load(path.read_bytes()))
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


def _content_sha256(paths: Sequence[Path]) -> str:
    """SHA-256 over the index and every member file, in load order."""
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii") + b"\n")
    return digest.hexdigest()
