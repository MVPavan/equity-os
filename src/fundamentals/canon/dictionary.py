"""Canonical dictionary: versioned row definitions, declarative formulas and the validating loader.

The dictionary lives in ``config/dictionary/<version>/``: one YAML file per statement
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

from fundamentals.canon.applicability import ApplicabilityRule, load_applicability_rules
from fundamentals.contracts.canonical import (
    Basis,
    PeriodNature,
    StatementFamily,
    TemporalRole,
    ValueKind,
)
from fundamentals.contracts.evidence_tier import EvidenceTier
from fundamentals.contracts.qualification import QualificationScope

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
PBT_IDS = frozenset({"profit_before_tax", "profit_before_tax_incl_associates"})
# ``ratio × 100 → percentage`` is the one literal with unit meaning (data spec §1).
PERCENT_SCALE = Decimal(100)

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
    metadata, rows, templates, rules = _read(directory, version)
    by_id = {row.canonical_id: row for row, _ in rows}
    _check_schema(rows, rules)
    _check_dangling(rows, by_id, templates, rules)
    resolved = tuple(_resolve(row, family, rules) for row, family in rows)
    _check_dimensions(rows, by_id, templates)
    _check_temporal_roles(rows, by_id)
    _check_unit_algebra(rows, by_id)
    _check_cycles(rows)
    _check_member_of_member(rows, templates)
    _check_duplicates(rows, templates)
    return CanonicalDictionary(
        version=metadata.version,
        content_sha256=_content_sha256(directory),
        formula_set_version=metadata.formula_set_version,
        formula_set_sha256=hashlib.sha256((directory / FORMULA_SET_FILE).read_bytes()).hexdigest(),
        rows=resolved,
        templates=templates,
    )


# Each row carries its family alongside, so checks can stay on the written spec.
_FamilyRow = tuple[_RowSpec, StatementFamily]


def _read(
    directory: Path, version: str
) -> tuple[
    _Metadata, list[_FamilyRow], tuple[DimensionTemplate, ...], tuple[ApplicabilityRule, ...]
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
    failures: dict[str, str] = {}
    metadata = _parsed(
        failures, METADATA_FILE, lambda: _Metadata.model_validate(_yaml(directory / METADATA_FILE))
    )
    templates = _parsed(
        failures,
        TEMPLATES_FILE,
        lambda: _TemplatesFile.model_validate(_yaml(directory / TEMPLATES_FILE)).templates,
    )
    rules = _parsed(
        failures,
        APPLICABILITY_FILE,
        lambda: load_applicability_rules(directory / APPLICABILITY_FILE),
    )
    rows: list[_FamilyRow] = []
    for name, family in FAMILY_FILES.items():
        family_file = _parsed(failures, name, _load_model, _FamilyFile, directory / name)
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
    return metadata, rows, templates, rules


def _parsed[T](
    failures: dict[str, str], offender: str, build: Callable[..., T], *args: Any
) -> T | None:
    """Run one parse step; record its failure under ``offender`` instead of raising."""
    try:
        return build(*args)
    except (ValidationError, yaml.YAMLError, KeyError, TypeError) as error:
        failures[offender] = " ".join(str(error).split())
        return None


def _load_model[M: BaseModel](model: type[M], path: Path) -> M:
    """Parse one YAML file into ``model``."""
    return model.model_validate(_yaml(path))


def _row_label(file_name: str, index: int, raw: Any) -> str:
    """Name a raw row by its canonical id, or by file and position when it has none."""
    canonical_id = raw.get(_ROW_ID_KEY) if isinstance(raw, Mapping) else None
    return canonical_id if isinstance(canonical_id, str) else f"{file_name}[{index}]"


def _yaml(path: Path) -> Any:
    """Parse one YAML file."""
    return yaml.safe_load(path.read_bytes())


def _resolve(
    row: _RowSpec, family: StatementFamily, rules: Sequence[ApplicabilityRule]
) -> DictionaryRow:
    """Build the public row, attaching its applicability rule."""
    rule = next(rule for rule in rules if rule.rule_id == row.applicability_rule_id)
    return DictionaryRow(family=family, applicability_rule=rule, **row.model_dump())


def _raise_if(defect: DictionaryDefect, offenders: Iterable[str]) -> None:
    """Raise ``defect`` naming every offender, if there are any."""
    found = set(offenders)
    if found:
        raise DictionaryLoadError(defect, found)


def _formula_rows(rows: Sequence[_FamilyRow]) -> Iterable[tuple[_RowSpec, Formula]]:
    """Yield each row that carries a formula, with its formula."""
    for row, _ in rows:
        if row.formula is not None:
            yield row, row.formula


def _check_schema(rows: Sequence[_FamilyRow], rules: Sequence[ApplicabilityRule]) -> None:
    """Structural rules the models alone cannot express."""
    offenders: set[str] = set()
    rule_ids = [rule.rule_id for rule in rules]
    offenders.update(rule_id for rule_id in rule_ids if rule_ids.count(rule_id) > 1)
    for row, family in rows:
        derived = family is StatementFamily.DERIVED
        if derived != (row.formula is not None):
            offenders.add(row.canonical_id)
        if row.period_aggregation is PeriodAggregationKind.ADDITIVE_DURATION and (
            row.value_kind is not ValueKind.CURRENCY_AMOUNT
            or row.period_nature is not PeriodNature.DURATION
        ):
            offenders.add(row.canonical_id)
        if row.formula is not None and not _formula_well_formed(row, row.formula):
            offenders.add(row.canonical_id)
    _raise_if(DictionaryDefect.SCHEMA, offenders)


def _formula_well_formed(row: _RowSpec, formula: Formula) -> bool:
    """Output kind matches the row, operands are unique and used, and the PBT id is named."""
    names = [operand.name for operand in formula.operands]
    pbt_operands = {op.canonical_id for op in formula.operands} & PBT_IDS
    pbt_named = formula.pbt_id is None if not pbt_operands else pbt_operands == {formula.pbt_id}
    return (
        formula.output_kind is row.value_kind
        and len(set(names)) == len(names)
        and formula.expression.operand_names() == set(names)
        and pbt_named
    )


def _check_dangling(
    rows: Sequence[_FamilyRow],
    by_id: Mapping[str, _RowSpec],
    templates: Sequence[DimensionTemplate],
    rules: Sequence[ApplicabilityRule],
) -> None:
    """Every referenced id — row, template, rule, axis, member, parent — must exist."""
    template_by_id = {template.template_id: template for template in templates}
    rule_ids = {rule.rule_id for rule in rules}
    offenders: set[str] = set()
    for template in templates:
        for axis in template.axes:
            declared = {member.member for member in axis.members}
            offenders.update(
                f"{template.template_id}.{axis.axis}.{member.parent}"
                for member in axis.members
                if member.parent is not None and member.parent not in declared
            )
    for row, _ in rows:
        if row.applicability_rule_id not in rule_ids:
            offenders.add(row.applicability_rule_id)
        if row.deprecated_by is not None and row.deprecated_by not in by_id:
            offenders.add(row.deprecated_by)
        if row.dimension_template is not None and row.dimension_template not in template_by_id:
            offenders.add(row.dimension_template)
    for _, formula in _formula_rows(rows):
        conditions = (
            formula.qualification.conditions + formula.qualification.exclusions
            if (formula.qualification is not None)
            else ()
        )
        offenders.update(c.canonical_id for c in conditions if c.canonical_id not in by_id)
        if formula.pbt_id is not None and formula.pbt_id not in by_id:
            offenders.add(formula.pbt_id)
        for operand in formula.operands:
            target = by_id.get(operand.canonical_id)
            if target is None:
                offenders.add(operand.canonical_id)
            elif operand.aggregation is not None:
                offenders.update(_dangling_members(operand, target, template_by_id))
    _raise_if(DictionaryDefect.DANGLING_ID, offenders)


def _dangling_members(
    operand: FormulaOperand, target: _RowSpec, templates: Mapping[str, DimensionTemplate]
) -> set[str]:
    """Aggregation axis and members must be declared by the operand row's template."""
    assert operand.aggregation is not None
    aggregation = operand.aggregation
    template = templates.get(target.dimension_template or "")
    axis = template.axis(aggregation.axis) if template is not None else None
    if axis is None:
        return {f"{operand.canonical_id}.{aggregation.axis}"}
    if aggregation.output_member not in _declared(axis):
        return {f"{aggregation.axis}.{aggregation.output_member}"}
    if axis.member_source is MemberSource.ENTITY_EVIDENCE:
        return set()
    return {
        f"{aggregation.axis}.{member}"
        for member in aggregation.input_members
        if member not in _declared(axis)
    }


def _declared(axis: TemplateAxis) -> set[str]:
    """Members an axis declares itself: its closed list and its aggregate members."""
    return {member.member for member in axis.members} | set(axis.aggregate_members)


def _check_dimensions(
    rows: Sequence[_FamilyRow],
    by_id: Mapping[str, _RowSpec],
    templates: Sequence[DimensionTemplate],
) -> None:
    """The output must carry exactly its operands' axes, and aggregations must fit their axis.

    Operands share the output's dimension set (data spec §1), so an operand's template
    axes equal the output's. An aggregation keeps its axis on the output with the output
    member declared there; a ``DECLARED`` list needs a closed-list axis and an
    ``ENTITY_EVIDENCE`` binding an entity-evidence axis with no members listed here.
    Each shared axis keeps its member source and closed members on the output.
    """
    template_by_id = {template.template_id: template for template in templates}
    offenders: set[str] = set()
    for row, formula in _formula_rows(rows):
        output = template_by_id.get(row.dimension_template or "")
        for operand in formula.operands:
            source = template_by_id.get(by_id[operand.canonical_id].dimension_template or "")
            if (
                _axis_names(source) != _axis_names(output)
                or not _members_carry_over(operand.aggregation, source, output)
                or (
                    operand.aggregation is not None
                    and not _aggregation_fits(operand.aggregation, source, output)
                )
            ):
                offenders.add(f"{row.canonical_id}.{operand.name}")
    _raise_if(DictionaryDefect.DIMENSION_MISFIT, offenders)


def _axis_names(template: DimensionTemplate | None) -> frozenset[str]:
    """The axes a template's keys carry; none without a template."""
    return frozenset() if template is None else frozenset(axis.axis for axis in template.axes)


def _members_carry_over(
    aggregation: DimensionalAggregation | None,
    source: DimensionTemplate | None,
    output: DimensionTemplate | None,
) -> bool:
    """Every axis keeps its member source and closed members from operand to output.

    A retained axis also keeps its aggregate members; only the aggregated axis may differ
    there, since the output declares the aggregate member it produces.
    """
    if source is None or output is None:
        return source is output
    for source_axis in source.axes:
        output_axis = output.axis(source_axis.axis)
        if (
            output_axis is None
            or output_axis.member_source is not source_axis.member_source
            or output_axis.members != source_axis.members
        ):
            return False
        aggregated = aggregation is not None and aggregation.axis == source_axis.axis
        if not aggregated and output_axis.aggregate_members != source_axis.aggregate_members:
            return False
    return True


def _aggregation_fits(
    aggregation: DimensionalAggregation,
    source: DimensionTemplate | None,
    output: DimensionTemplate | None,
) -> bool:
    """The output declares the aggregate member, and the binding matches the axis's source."""
    source_axis = source.axis(aggregation.axis) if source is not None else None
    output_axis = output.axis(aggregation.axis) if output is not None else None
    if source_axis is None or output_axis is None:
        return False
    if aggregation.member_binding is MemberBinding.DECLARED:
        binding_fits = source_axis.member_source is MemberSource.CLOSED_LIST
    else:
        binding_fits = (
            source_axis.member_source is MemberSource.ENTITY_EVIDENCE
            and not aggregation.input_members
        )
    if output_axis.member_source is MemberSource.ENTITY_EVIDENCE:
        output_declared = aggregation.output_member in output_axis.aggregate_members
    else:
        output_declared = aggregation.output_member in _declared(output_axis)
    return binding_fits and output_declared


def _check_temporal_roles(rows: Sequence[_FamilyRow], by_id: Mapping[str, _RowSpec]) -> None:
    """Each operand role must fit the operand's and the output's period nature."""
    offenders: set[str] = set()
    for row, formula in _formula_rows(rows):
        for operand in formula.operands:
            nature = by_id[operand.canonical_id].period_nature
            if not _role_fits(operand.temporal_role, nature, row.period_nature):
                offenders.add(f"{row.canonical_id}.{operand.name}")
    _raise_if(DictionaryDefect.TEMPORAL_ROLE_MISFIT, offenders)


def _role_fits(role: TemporalRole, operand: PeriodNature, output: PeriodNature) -> bool:
    """``DURATION`` joins durations; ``CLOSING`` reads an instant at the output's end;
    ``OPENING`` and ``AVERAGE`` need a duration output with a start."""
    if role is TemporalRole.DURATION:
        return operand is PeriodNature.DURATION and output is PeriodNature.DURATION
    if role is TemporalRole.CLOSING:
        return operand is PeriodNature.INSTANT
    return operand is PeriodNature.INSTANT and output is PeriodNature.DURATION


# Unit algebra over value kinds; ``None`` is a dimensionless literal.
_Kind = ValueKind | None
_AMOUNT_DIVISIONS: Mapping[tuple[ValueKind, ValueKind], ValueKind] = {
    (ValueKind.CURRENCY_AMOUNT, ValueKind.PER_SHARE_AMOUNT): ValueKind.COUNT,
    (ValueKind.CURRENCY_AMOUNT, ValueKind.COUNT): ValueKind.PER_SHARE_AMOUNT,
}


class _UnitAlgebraError(ValueError):
    """An expression combines kinds the algebra does not allow."""


def _check_unit_algebra(rows: Sequence[_FamilyRow], by_id: Mapping[str, _RowSpec]) -> None:
    """Every expression must reduce to the declared output kind (days via the day count)."""
    offenders: set[str] = set()
    for row, formula in _formula_rows(rows):
        operand_kinds: dict[str, ValueKind] = {}
        for operand in formula.operands:
            target = by_id[operand.canonical_id]
            if (
                operand.aggregation is not None
                and target.aggregation_behaviour is not AggregationBehaviour.SUMMABLE_ACROSS_MEMBERS
            ):
                offenders.add(f"{row.canonical_id}.{operand.name}")
            operand_kinds[operand.name] = target.value_kind
        try:
            kind = _kind_of(formula.expression, operand_kinds.__getitem__)
        except _UnitAlgebraError:
            offenders.add(row.canonical_id)
            continue
        if formula.day_count is not None:
            fits = (
                kind is ValueKind.RATIO
                and formula.output_kind is ValueKind.DAYS
                and row.period_nature is PeriodNature.DURATION
            )
        else:
            fits = kind is formula.output_kind
        if not fits:
            offenders.add(row.canonical_id)
    _raise_if(DictionaryDefect.UNIT_ALGEBRA, offenders)


def _kind_of(node: FormulaNode, operand_kind: Callable[[str], ValueKind]) -> _Kind:
    """Reduce an expression to its value kind, or raise ``_UnitAlgebraError``."""
    if node.op is FormulaOp.OPERAND:
        assert node.operand is not None
        return operand_kind(node.operand)
    if node.op is FormulaOp.LITERAL:
        return None
    kinds = [_kind_of(arg, operand_kind) for arg in node.args]
    if node.op in (FormulaOp.ADD, FormulaOp.SUB):
        if len(set(kinds)) != 1:
            raise _UnitAlgebraError(node.op)
        return kinds[0]
    left, right = kinds
    if node.op is FormulaOp.MUL:
        return _multiply(node, left, right)
    if right is None or left == right:
        return left if right is None else ValueKind.RATIO
    if left is not None and (left, right) in _AMOUNT_DIVISIONS:
        return _AMOUNT_DIVISIONS[(left, right)]
    raise _UnitAlgebraError(node.op)


def _multiply(node: FormulaNode, left: _Kind, right: _Kind) -> _Kind:
    """Scale by a literal keeps the kind, except ``ratio × 100`` which is a percentage."""
    literal = next((arg.value for arg in node.args if arg.op is FormulaOp.LITERAL), None)
    kinds = {left, right}
    if kinds == {ValueKind.RATIO, None} and literal == PERCENT_SCALE:
        return ValueKind.PERCENTAGE
    if None in kinds:
        return left if right is None else right
    if kinds == {ValueKind.RATIO}:
        return ValueKind.RATIO
    raise _UnitAlgebraError(node.op)


def _check_cycles(rows: Sequence[_FamilyRow]) -> None:
    """Depth-first search over formula operands; every row on a cycle is named."""
    edges = {
        row.canonical_id: [operand.canonical_id for operand in formula.operands]
        for row, formula in _formula_rows(rows)
    }
    offenders: set[str] = set()
    state: dict[str, int] = {}
    path: list[str] = []

    def visit(node: str) -> None:
        state[node] = 1
        path.append(node)
        for target in edges.get(node, []):
            if state.get(target) == 1:
                offenders.update(path[path.index(target) :])
            elif target not in state:
                visit(target)
        path.pop()
        state[node] = 2

    for node in edges:
        if node not in state:
            visit(node)
    _raise_if(DictionaryDefect.CYCLE, offenders)


def _check_member_of_member(
    rows: Sequence[_FamilyRow], templates: Sequence[DimensionTemplate]
) -> None:
    """Refuse aggregation lists that double count: a member with its own aggregate,
    a repeated member, or the output among the inputs."""
    aggregations = [
        (row.canonical_id, operand)
        for row, formula in _formula_rows(rows)
        for operand in formula.operands
        if operand.aggregation is not None
    ]
    children: dict[tuple[str, str], set[str]] = {}
    for template in templates:
        for axis in template.axes:
            for member in axis.members:
                if member.parent is not None:
                    children.setdefault((axis.axis, member.parent), set()).add(member.member)
    for _, operand in aggregations:
        assert operand.aggregation is not None
        key = (operand.aggregation.axis, operand.aggregation.output_member)
        children.setdefault(key, set()).update(operand.aggregation.input_members)
    offenders: set[str] = set()
    for row_id, operand in aggregations:
        assert operand.aggregation is not None
        aggregation = operand.aggregation
        inputs = aggregation.input_members
        double = len(set(inputs)) != len(inputs) or aggregation.output_member in inputs
        for name in inputs:
            below = _descendants(aggregation.axis, name, children)
            double = double or bool(below & set(inputs))
        if double:
            offenders.add(f"{row_id}.{operand.name}")
    _raise_if(DictionaryDefect.MEMBER_OF_MEMBER, offenders)


def _descendants(axis: str, member: str, children: Mapping[tuple[str, str], set[str]]) -> set[str]:
    """Every member that ``member`` aggregates, directly or through other aggregates."""
    found: set[str] = set()
    pending = [member]
    while pending:
        for child in children.get((axis, pending.pop()), set()):
            if child not in found and child != member:
                found.add(child)
                pending.append(child)
    return found


def _check_duplicates(rows: Sequence[_FamilyRow], templates: Sequence[DimensionTemplate]) -> None:
    """Two rows, templates, template instantiations or differing formula definitions must
    never share one selector; an identical formula may be reused."""
    offenders: set[str] = set()
    seen: set[str] = set()
    for row, _ in rows:
        if row.canonical_id in seen:
            offenders.add(row.canonical_id)
        seen.add(row.canonical_id)
    formulas: dict[tuple[str, str], Formula] = {}
    for _, formula in _formula_rows(rows):
        first = formulas.setdefault((formula.formula_id, formula.version), formula)
        if first != formula:
            offenders.add(f"{formula.formula_id}@{formula.version}")
    template_ids = [template.template_id for template in templates]
    offenders.update(t for t in template_ids if template_ids.count(t) > 1)
    for template in templates:
        axes = [axis.axis for axis in template.axes]
        offenders.update(f"{template.template_id}.{a}" for a in axes if axes.count(a) > 1)
        for axis in template.axes:
            members = [member.member for member in axis.members] + list(axis.aggregate_members)
            offenders.update(
                f"{template.template_id}.{axis.axis}.{m}" for m in members if members.count(m) > 1
            )
    _raise_if(DictionaryDefect.DUPLICATE_SELECTOR, offenders)


def _content_sha256(directory: Path) -> str:
    """SHA-256 over every dictionary file except the separately pinned formula set."""
    digest = hashlib.sha256()
    for path in sorted(directory.glob(YAML_GLOB)):
        if path.name == FORMULA_SET_FILE:
            continue
        digest.update(path.name.encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii") + b"\n")
    return digest.hexdigest()
