"""Typed mapping configuration models shared by the validating loader."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from fundamentals.canon.dictionary import FormulaNode, FormulaOp
from fundamentals.contracts.canonical import (
    Basis,
    PeriodKind,
    StatementFamily,
    ValueKind,
)
from fundamentals.contracts.evidence_tier import EvidenceTier
from fundamentals.contracts.qualification import QualificationScope
from fundamentals.extract.pdf_header_text import normalize_text_tokens

ALL_BASES = frozenset(Basis)
ALL_PERIOD_KINDS = frozenset(PeriodKind)


class PeriodShape(StrEnum):
    """Whether an XBRL selector takes duration or instant contexts."""

    DURATION = "DURATION"
    INSTANT = "INSTANT"


class PdfPeriodRule(StrEnum):
    """How a PDF row's key period follows from its column header."""

    COLUMN_DURATION = "COLUMN_DURATION"
    COLUMN_OPENING_INSTANT = "COLUMN_OPENING_INSTANT"
    COLUMN_CLOSING_INSTANT = "COLUMN_CLOSING_INSTANT"
    COLUMN_INSTANT = "COLUMN_INSTANT"


class MemberSource(StrEnum):
    """Where a templated entry's entity-evidence member comes from."""

    XBRL_DESCRIPTION = "XBRL_DESCRIPTION"


class UnitTransform(StrEnum):
    """How a raw value becomes base units."""

    SCALE_TO_BASE_UNIT = "SCALE_TO_BASE_UNIT"


class PrecisionRule(StrEnum):
    """Where the uncertainty interval comes from."""

    DECLARED = "DECLARED"


class AnchorPeriodShape(StrEnum):
    """The period a statement anchor must have relative to the package period end."""

    INSTANT_AT_PERIOD_END = "INSTANT_AT_PERIOD_END"
    DURATION_ENDING_AT_PERIOD_END = "DURATION_ENDING_AT_PERIOD_END"


class Selector(BaseModel):
    """A native field and context predicate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    native_field: str | None = None
    period_shape: PeriodShape | None = None
    dimension_axis: str | None = None
    statement_family: StatementFamily | None = None
    labels: tuple[str, ...] = ()
    section: str | None = None
    section_equals: str | None = None
    unestablished_section_ambiguous: bool = False
    section_parent_equals: str | None = None
    label_ordinal: int | None = Field(default=None, ge=1)
    column_header: str | None = None

    @model_validator(mode="after")
    def _one_kind(self) -> Selector:
        xbrl = self.native_field is not None
        pdf = self.statement_family is not None
        if xbrl == pdf or (xbrl and self.period_shape is None) or (pdf and not self.labels):
            raise ValueError("a selector is either XBRL (element, period shape) or PDF (labels)")
        if xbrl:
            assert self.native_field is not None
            if not self.native_field.strip():
                raise ValueError("an XBRL selector requires a nonblank native field")
        if pdf and any(not normalize_text_tokens(label) for label in self.labels):
            raise ValueError("a PDF selector requires nonblank label evidence")
        predicates = (
            self.dimension_axis,
            self.section,
            self.section_equals,
            self.section_parent_equals,
            self.column_header,
        )
        if any(value is not None and not normalize_text_tokens(value) for value in predicates):
            raise ValueError("selector evidence predicates cannot be blank")
        return self

    def overlaps(self, other: Selector) -> bool:
        """Whether some native field and context could satisfy both selectors."""
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
            and _compatible_sections(self, other)
            and (
                self.section_parent_equals is None
                or other.section_parent_equals is None
                or normalize_text_tokens(self.section_parent_equals)
                == normalize_text_tokens(other.section_parent_equals)
            )
            and _compatible(self.column_header, other.column_header)
        )


class MappingEntry(BaseModel):
    """One evidenced native-to-canonical mapping."""

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
        if self.sign not in (1, -1):
            raise ValueError("sign must be 1 or -1")
        if (self.period_rule is None) != (self.selector.native_field is not None):
            raise ValueError("PDF entries carry a period_rule; XBRL entries carry none")
        return self

    def emitted_measurement(self) -> tuple[object, ...]:
        return (
            self.canonical_id,
            tuple(sorted(self.dimension_members.items())),
            self.member_source,
        )


class ConstructionOperand(BaseModel):
    """One construction operand: a mapping entry or a selector over the capture's own rows."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    mapping_entry_id: str | None = Field(
        default=None, min_length=1, exclude_if=lambda value: value is None
    )
    dash_rule_id: str | None = None
    selector: Selector | None = Field(default=None, exclude_if=lambda value: value is None)

    @model_validator(mode="after")
    def _one_branch(self) -> ConstructionOperand:
        if (self.mapping_entry_id is None) == (self.selector is None):
            raise ValueError("exactly one of mapping_entry_id or selector is required")
        if self.selector is not None and self.dash_rule_id is not None:
            raise ValueError("selector operands do not use dash-to-zero rules")
        return self


class ConstructionRule(BaseModel):
    """A reported value assembled from one capture's own lines."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str = Field(min_length=1)
    source: str | None = Field(default=None, min_length=1)
    surface: str = Field(min_length=1)
    schema_identity: str = Field(min_length=1)
    canonical_id: str = Field(min_length=1)
    bases: frozenset[Basis] | None = Field(
        default=None, min_length=1, exclude_if=lambda value: value is None
    )
    operands: tuple[ConstructionOperand, ...] = Field(min_length=1)
    expression: FormulaNode
    tier: EvidenceTier = EvidenceTier.EQUIVALENCE_UNPROVEN
    qualification: QualificationScope | None = None
    evidence_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def _operands_cover_expression(self) -> ConstructionRule:
        names = [operand.name for operand in self.operands]
        if len(set(names)) != len(names) or self.expression.operand_names() != set(names):
            raise ValueError("operand names are distinct and exactly cover the expression")
        selectors = [operand.selector for operand in self.operands if operand.selector]
        if selectors:
            if self.source is None:
                raise ValueError("selector constructions require a named source")
            if not _additive(self.expression):
                raise ValueError("selector constructions only add or subtract their operands")
            if self.tier is EvidenceTier.RELATED_NOT_EQUIVALENT:
                raise ValueError("selector constructions cannot claim a related tier")
            if self.tier is EvidenceTier.EQUIVALENCE_DEMONSTRATED and self.qualification is None:
                raise ValueError("demonstrated selector constructions require qualification")
            for index, left in enumerate(selectors):
                if any(left.overlaps(right) for right in selectors[index + 1 :]):
                    raise ValueError("selector operands cannot overlap")
        return self

    def operand_entry_id(self, operand: ConstructionOperand) -> str:
        """The operand's mapping entry id, or its rule-scoped id for a selector operand."""
        return operand.mapping_entry_id or f"{self.rule_id}#{operand.name}"


def _additive(node: FormulaNode) -> bool:
    """Whether a formula only adds and subtracts operands."""
    if node.op is FormulaOp.OPERAND:
        return True
    return node.op in (FormulaOp.ADD, FormulaOp.SUB) and all(_additive(arg) for arg in node.args)


class StatementAnchor(BaseModel):
    """Native fields proving that a statement is present."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_identity: str = Field(min_length=1)
    statement_family: StatementFamily
    native_fields: frozenset[str] = Field(min_length=1)
    period_shape: AnchorPeriodShape


class DashRule(BaseModel):
    """Reads a printed dash as zero for one mapped construction operand."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str = Field(min_length=1)
    construction_rule_id: str = Field(min_length=1)
    operand_name: str = Field(min_length=1)
    evidence_ref: str = Field(min_length=1)


class UnitRule(BaseModel):
    """What one raw unit means."""

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


def selector_matches(selector: Selector, context: Mapping[str, object]) -> bool:
    """Match the PDF/HTML half of a selector against native context."""
    if context.get("statement_family") != selector.statement_family:
        return False
    label = normalize_text_tokens(str(context.get("label", "")))
    if all(normalize_text_tokens(variant) != label for variant in selector.labels):
        return False
    if selector.section is not None and not _contains(
        normalize_text_tokens(str(context.get("section", ""))),
        normalize_text_tokens(selector.section),
    ):
        return False
    if selector.section_equals is not None and normalize_text_tokens(
        str(context.get("section", ""))
    ) != normalize_text_tokens(selector.section_equals):
        return False
    if selector.section_parent_equals is not None and normalize_text_tokens(
        str(context.get("section_parent", ""))
    ) != normalize_text_tokens(selector.section_parent_equals):
        return False
    if (
        selector.label_ordinal is not None
        and context.get("label_ordinal") != selector.label_ordinal
    ):
        return False
    return selector.column_header is None or _contains(
        normalize_text_tokens(str(context.get("column_header", ""))),
        normalize_text_tokens(selector.column_header),
    )


def _contains(haystack: Sequence[str], needle: Sequence[str]) -> bool:
    width = len(needle)
    return width > 0 and any(
        list(haystack[index : index + width]) == list(needle)
        for index in range(len(haystack) - width + 1)
    )


def _compatible(left: str | None, right: str | None) -> bool:
    del left, right
    return True


def _compatible_sections(left: Selector, right: Selector) -> bool:
    for exact, other in ((left.section_equals, right), (right.section_equals, left)):
        if exact is None:
            continue
        tokens = normalize_text_tokens(exact)
        if other.section_equals is not None and tokens != normalize_text_tokens(
            other.section_equals
        ):
            return False
        if other.section is not None and not _contains(
            tokens, normalize_text_tokens(other.section)
        ):
            return False
    return True
