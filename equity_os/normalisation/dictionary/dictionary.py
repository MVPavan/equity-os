"""Canonical dictionary: versioned row definitions, declarative formulas and the validating loader.

The dictionary lives in ``config/normalisation/dictionary/<version>/``: one YAML file per statement
family, ``templates.yaml`` (dimension templates), ``applicability.yaml`` and
``metadata.yaml``. ``derived.yaml`` is the formula set; its version and SHA-256 are
pinned separately from the rest (plan design decision 7).

Formulas are operator trees over declared operands and decimal literals; formula
strings are never parsed or evaluated. The loader validates in a fixed order —
schema, dangling ids, dimension fit, temporal-role fit, unit algebra, cycles,
member-of-member, duplicate selectors — and raises on the first defect class with every
offending id.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable, Mapping, Sequence
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from equity_os.contracts.measurement.canonical import (
    Basis,
    PeriodNature,
    StatementFamily,
    TemporalRole,
    ValueKind,
)
from equity_os.contracts.measurement.evidence_tier import EvidenceTier
from equity_os.contracts.measurement.qualification import QualificationScope
from equity_os.normalisation.dictionary.applicability import (
    ApplicabilityRule,
    parse_applicability_rules,
)

METADATA_FILE = "metadata.yaml"
TEMPLATES_FILE = "templates.yaml"
APPLICABILITY_FILE = "applicability.yaml"
FORMULA_SET_FILE = "derived.yaml"
FAMILY_FILES: Mapping[str, StatementFamily] = {
    "pl.yaml": StatementFamily.PL,
    "balance_sheet.yaml": StatementFamily.BALANCE_SHEET,
    "cash_flow.yaml": StatementFamily.CASH_FLOW,
    "segment.yaml": StatementFamily.SEGMENT,
    "shareholding.yaml": StatementFamily.SHAREHOLDING,
    FORMULA_SET_FILE: StatementFamily.DERIVED,
}
KNOWN_FILES = frozenset({METADATA_FILE, TEMPLATES_FILE, APPLICABILITY_FILE, *FAMILY_FILES})
YAML_GLOB = "*.yaml"

_LOAD_FAILED = "dictionary load failed: {defect} for {ids}{detail}"
_ARITY = "{op} needs {expected} arguments, got {got}"
_LEAF = "{op} takes no arguments and needs exactly its own field"
_DECLARED_NEEDS_MEMBERS = "a DECLARED aggregation lists at least one input member"
_NOT_BINDABLE = "only an unbound ENTITY_EVIDENCE aggregation takes members at evaluation"
_BAD_BINDING = "bound members must be non-empty, distinct and exclude the output member"
_UNEXPECTED_FILES = "unexpected file set"
_FAMILY_MISMATCH = "family mismatch"
_VERSION_MISMATCH = "version mismatch"
_ROW_ID_KEY = "canonical_id"
_ROW_NOT_MAPPING = "row is not a mapping"


class DictionaryDefect(StrEnum):
    """Why a dictionary failed to load."""

    DANGLING_ID = "DANGLING_ID"
    UNIT_ALGEBRA = "UNIT_ALGEBRA"
    CYCLE = "CYCLE"
    MEMBER_OF_MEMBER = "MEMBER_OF_MEMBER"
    DUPLICATE_SELECTOR = "DUPLICATE_SELECTOR"
    TEMPORAL_ROLE_MISFIT = "TEMPORAL_ROLE_MISFIT"
    DIMENSION_MISFIT = "DIMENSION_MISFIT"
    SCHEMA = "SCHEMA"


class DictionaryLoadError(ValueError):
    """The dictionary is invalid; ``ids`` names every offender of the first failing defect class."""

    def __init__(self, defect: DictionaryDefect, ids: Iterable[str], detail: str = "") -> None:
        self.defect = defect
        self.ids = tuple(sorted(set(ids)))
        suffix = f": {detail}" if detail else ""
        super().__init__(_LOAD_FAILED.format(defect=defect, ids=list(self.ids), detail=suffix))


class FormulaOp(StrEnum):
    """Operator of one formula node."""

    ADD = "ADD"
    SUB = "SUB"
    MUL = "MUL"
    DIV = "DIV"
    OPERAND = "OPERAND"
    LITERAL = "LITERAL"


class PeriodAggregationKind(StrEnum):
    """Whether a row's values may be derived across periods (Q4 = FY − 9M, H2, TTM)."""

    ADDITIVE_DURATION = "ADDITIVE_DURATION"
    NONE = "NONE"


class DayCount(StrEnum):
    """Day-count convention of a days-valued formula."""

    ACTUAL_DAYS_IN_OUTPUT_INTERVAL = "ACTUAL_DAYS_IN_OUTPUT_INTERVAL"


class SignConvention(StrEnum):
    """Which direction is positive for a row's canonical value."""

    POSITIVE_AS_LABELLED = "POSITIVE_AS_LABELLED"
    SIGNED_PROFIT_POSITIVE = "SIGNED_PROFIT_POSITIVE"
    SIGNED_INFLOW_POSITIVE = "SIGNED_INFLOW_POSITIVE"
    AS_COMPUTED = "AS_COMPUTED"


class AggregationBehaviour(StrEnum):
    """Whether values of different dimension members may be summed."""

    SUMMABLE_ACROSS_MEMBERS = "SUMMABLE_ACROSS_MEMBERS"
    NOT_SUMMABLE = "NOT_SUMMABLE"


class MemberSource(StrEnum):
    """Where a template axis gets its members."""

    CLOSED_LIST = "CLOSED_LIST"
    ENTITY_EVIDENCE = "ENTITY_EVIDENCE"


class MemberBinding(StrEnum):
    """Where a dimensional aggregation's closed input-member list comes from."""

    DECLARED = "DECLARED"
    ENTITY_EVIDENCE = "ENTITY_EVIDENCE"


class MissingMemberRule(StrEnum):
    """What a listed input member without a value does to the aggregate (data spec §1)."""

    OPERAND_MISSING = "OPERAND_MISSING"


class FormulaNode(BaseModel):
    """One node of a declarative formula tree.

    ``ADD`` takes two or more arguments; ``SUB``, ``MUL`` and ``DIV`` exactly two.
    ``OPERAND`` names a declared operand; ``LITERAL`` holds an exact decimal.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    op: FormulaOp
    args: tuple[FormulaNode, ...] = ()
    operand: str | None = None
    value: Decimal | None = None

    @model_validator(mode="after")
    def _shape(self) -> FormulaNode:
        """Refuse nodes whose arity or leaf fields do not match their operator."""
        if self.op in (FormulaOp.OPERAND, FormulaOp.LITERAL):
            wants_operand = self.op is FormulaOp.OPERAND
            if (
                self.args
                or (self.operand is None) == wants_operand
                or ((self.value is None) != wants_operand)
            ):
                raise ValueError(_LEAF.format(op=self.op))
            return self
        if self.operand is not None or self.value is not None:
            raise ValueError(_LEAF.format(op=self.op))
        expected = "2+" if self.op is FormulaOp.ADD else "2"
        if len(self.args) < 2 or (self.op is not FormulaOp.ADD and len(self.args) != 2):
            raise ValueError(_ARITY.format(op=self.op, expected=expected, got=len(self.args)))
        return self

    def operand_names(self) -> frozenset[str]:
        """Every operand name the tree references."""
        if self.op is FormulaOp.OPERAND:
            assert self.operand is not None
            return frozenset({self.operand})
        return frozenset().union(*(arg.operand_names() for arg in self.args))


class DimensionalAggregation(BaseModel):
    """Sum a closed list of members of one axis into a declared output member.

    ``DECLARED`` lists the members here (closed-list axes). ``ENTITY_EVIDENCE`` lists none:
    the closed list is the entity's evidenced members for the period, bound at evaluation
    with :meth:`bind_members` and pinned as an input there. Either way every listed
    member needs a value (``missing_member``).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    axis: str = Field(min_length=1)
    input_members: tuple[str, ...] = ()
    output_member: str = Field(min_length=1)
    member_binding: MemberBinding = MemberBinding.DECLARED
    missing_member: MissingMemberRule = MissingMemberRule.OPERAND_MISSING

    @model_validator(mode="after")
    def _declared_lists_members(self) -> DimensionalAggregation:
        """A declared closed list cannot be empty."""
        if self.member_binding is MemberBinding.DECLARED and not self.input_members:
            raise ValueError(_DECLARED_NEEDS_MEMBERS)
        return self

    def bind_members(self, members: Sequence[str]) -> DimensionalAggregation:
        """Return this entity-bound aggregation with its evaluated closed member list."""
        if self.member_binding is not MemberBinding.ENTITY_EVIDENCE or self.input_members:
            raise ValueError(_NOT_BINDABLE)
        if not members or len(set(members)) != len(members) or self.output_member in members:
            raise ValueError(_BAD_BINDING)
        return self.model_copy(update={"input_members": tuple(members)})


class FormulaOperand(BaseModel):
    """A named formula input: a canonical id at a temporal role, optionally aggregated."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    canonical_id: str = Field(min_length=1)
    temporal_role: TemporalRole
    aggregation: DimensionalAggregation | None = None


class Formula(BaseModel):
    """A registered formula with its own tier and qualification scope (plan design decision 8)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    formula_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    operands: tuple[FormulaOperand, ...] = Field(min_length=1)
    expression: FormulaNode
    output_kind: ValueKind
    day_count: DayCount | None = None
    pbt_id: str | None = None
    tier: EvidenceTier = EvidenceTier.EQUIVALENCE_UNPROVEN
    qualification: QualificationScope | None = None
    evidence: str = Field(min_length=1)


class TemplateMember(BaseModel):
    """A closed-list member, with the member that aggregates it when one does."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    member: str = Field(min_length=1)
    parent: str | None = None


class TemplateAxis(BaseModel):
    """One axis of a dimension template and how its members are instantiated."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    axis: str = Field(min_length=1)
    member_source: MemberSource
    members: tuple[TemplateMember, ...] = ()
    aggregate_members: tuple[str, ...] = ()
    instantiation: str = Field(min_length=1)


class DimensionTemplate(BaseModel):
    """The axes a templated row's keys carry."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    template_id: str = Field(min_length=1)
    axes: tuple[TemplateAxis, ...] = Field(min_length=1)

    def axis(self, name: str) -> TemplateAxis | None:
        """Return the named axis, or ``None``."""
        return next((axis for axis in self.axes if axis.axis == name), None)


class _RowSpec(BaseModel):
    """One row as written in a family file, before rules are resolved."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    canonical_id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    meaning: str = Field(min_length=1)
    value_kind: ValueKind
    period_nature: PeriodNature
    sign_convention: SignConvention
    aggregation_behaviour: AggregationBehaviour
    period_aggregation: PeriodAggregationKind = PeriodAggregationKind.NONE
    applicability_rule_id: str = Field(min_length=1)
    basis_applicability: frozenset[Basis] = Field(min_length=1)
    dimension_template: str | None = None
    formula: Formula | None = None
    headline: bool = False
    deprecated_by: str | None = None


class DictionaryRow(BaseModel):
    """One canonical row. ``applicability_rule`` is resolved from ``applicability_rule_id``."""

    model_config = ConfigDict(frozen=True)

    canonical_id: str
    family: StatementFamily
    meaning: str
    value_kind: ValueKind
    period_nature: PeriodNature
    sign_convention: SignConvention
    aggregation_behaviour: AggregationBehaviour
    period_aggregation: PeriodAggregationKind | None
    applicability_rule_id: str
    applicability_rule: ApplicabilityRule
    basis_applicability: frozenset[Basis]
    dimension_template: str | None
    formula: Formula | None
    headline: bool
    deprecated_by: str | None


class CanonicalDictionary(BaseModel):
    """A loaded, validated dictionary version with its content pins."""

    model_config = ConfigDict(frozen=True)

    version: str
    content_sha256: str
    formula_set_version: str
    formula_set_sha256: str
    rows: tuple[DictionaryRow, ...]
    templates: tuple[DimensionTemplate, ...]

    def row(self, canonical_id: str) -> DictionaryRow:
        """Return the row with this id; an unknown id raises ``KeyError``."""
        for candidate in self.rows:
            if candidate.canonical_id == canonical_id:
                return candidate
        raise KeyError(canonical_id)

    def template(self, template_id: str) -> DimensionTemplate:
        """Return the template with this id; an unknown id raises ``KeyError``."""
        for candidate in self.templates:
            if candidate.template_id == template_id:
                return candidate
        raise KeyError(template_id)

    def family_counts(self) -> Mapping[StatementFamily, int]:
        """Count rows per family; every family appears, zero included."""
        return {
            family: sum(1 for row in self.rows if row.family is family)
            for family in StatementFamily
        }


class _Metadata(BaseModel):
    """``metadata.yaml``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str = Field(min_length=1)
    formula_set_version: str = Field(min_length=1)
    scope: str = Field(min_length=1)


class _FamilyFile(BaseModel):
    """One family file: its family, defaults merged into every row, and the rows.

    Rows stay untyped here so each is validated, and named, on its own.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    family: StatementFamily
    defaults: Mapping[str, Any] = Field(default_factory=dict)
    rows: tuple[Any, ...]


class _TemplatesFile(BaseModel):
    """``templates.yaml``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    templates: tuple[DimensionTemplate, ...]


def load_dictionary(root: Path, version: str) -> CanonicalDictionary:
    """Load and validate dictionary ``version`` from ``root/<version>/``.

    Raises :class:`DictionaryLoadError` with the first failing defect class and
    every offending id.
    """
    directory = root / version
    metadata, rows, templates, rules, bodies = _read(directory, version)
    from equity_os.normalisation.dictionary.dictionary_validation import validate_dictionary

    validate_dictionary(rows, templates, rules)
    resolved = tuple(_resolve(row, family, rules) for row, family in rows)
    return CanonicalDictionary(
        version=metadata.version,
        content_sha256=_content_sha256(bodies),
        formula_set_version=metadata.formula_set_version,
        formula_set_sha256=hashlib.sha256(bodies[FORMULA_SET_FILE]).hexdigest(),
        rows=resolved,
        templates=templates,
    )


# Each row carries its family alongside, so checks can stay on the written spec.
_FamilyRow = tuple[_RowSpec, StatementFamily]


def _read(
    directory: Path, version: str
) -> tuple[
    _Metadata,
    list[_FamilyRow],
    tuple[DimensionTemplate, ...],
    tuple[ApplicabilityRule, ...],
    Mapping[str, bytes],
]:
    """Read every file, mapping parse and model errors to ``SCHEMA``.

    Every failing file and row is collected before raising, each named by its canonical
    id (or ``file[index]`` when the row has none).
    """
    present = {path.name for path in directory.glob(YAML_GLOB)}
    unknown = present - KNOWN_FILES
    missing = KNOWN_FILES - present
    if unknown or missing:
        raise DictionaryLoadError(DictionaryDefect.SCHEMA, unknown | missing, _UNEXPECTED_FILES)
    try:
        bodies = {name: (directory / name).read_bytes() for name in sorted(present)}
    except OSError as error:
        raise DictionaryLoadError(DictionaryDefect.SCHEMA, present, str(error)) from error
    failures: dict[str, str] = {}
    metadata = _parsed(
        failures,
        METADATA_FILE,
        lambda: _Metadata.model_validate(yaml.safe_load(bodies[METADATA_FILE])),
    )
    templates = _parsed(
        failures,
        TEMPLATES_FILE,
        lambda: _TemplatesFile.model_validate(yaml.safe_load(bodies[TEMPLATES_FILE])).templates,
    )
    rules = _parsed(
        failures,
        APPLICABILITY_FILE,
        lambda: parse_applicability_rules(bodies[APPLICABILITY_FILE]),
    )
    rows: list[_FamilyRow] = []
    for name, family in FAMILY_FILES.items():
        family_file = _parsed(failures, name, _load_model, _FamilyFile, bodies[name])
        if family_file is None:
            continue
        if family_file.family is not family:
            failures[name] = _FAMILY_MISMATCH
        for index, raw in enumerate(family_file.rows):
            if not isinstance(raw, Mapping):
                failures[_row_label(name, index, raw)] = _ROW_NOT_MAPPING
                continue
            spec = _parsed(
                failures,
                _row_label(name, index, raw),
                _RowSpec.model_validate,
                {**family_file.defaults, **raw},
            )
            if spec is not None:
                rows.append((spec, family))
    if failures or metadata is None or templates is None or rules is None:
        detail = " | ".join(f"{offender}: {reason}" for offender, reason in failures.items())
        raise DictionaryLoadError(DictionaryDefect.SCHEMA, failures, detail)
    if metadata.version != version:
        raise DictionaryLoadError(DictionaryDefect.SCHEMA, [metadata.version], _VERSION_MISMATCH)
    return metadata, rows, templates, rules, bodies


def _parsed[T](
    failures: dict[str, str], offender: str, build: Callable[..., T], *args: Any
) -> T | None:
    """Run one parse step; record its failure under ``offender`` instead of raising."""
    try:
        return build(*args)
    except (ValidationError, yaml.YAMLError, KeyError, TypeError) as error:
        failures[offender] = " ".join(str(error).split())
        return None


def _load_model[M: BaseModel](model: type[M], body: bytes) -> M:
    """Parse one YAML file into ``model``."""
    return model.model_validate(yaml.safe_load(body))


def _row_label(file_name: str, index: int, raw: Any) -> str:
    """Name a raw row by its canonical id, or by file and position when it has none."""
    canonical_id = raw.get(_ROW_ID_KEY) if isinstance(raw, Mapping) else None
    return canonical_id if isinstance(canonical_id, str) else f"{file_name}[{index}]"


def _resolve(
    row: _RowSpec, family: StatementFamily, rules: Sequence[ApplicabilityRule]
) -> DictionaryRow:
    """Build the public row, attaching its applicability rule."""
    rule = next(rule for rule in rules if rule.rule_id == row.applicability_rule_id)
    return DictionaryRow(family=family, applicability_rule=rule, **row.model_dump())


def _content_sha256(bodies: Mapping[str, bytes]) -> str:
    """SHA-256 over every dictionary file except the separately pinned formula set."""
    digest = hashlib.sha256()
    for name, body in sorted(bodies.items()):
        if name == FORMULA_SET_FILE:
            continue
        digest.update(name.encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(body).hexdigest().encode("ascii") + b"\n")
    return digest.hexdigest()
