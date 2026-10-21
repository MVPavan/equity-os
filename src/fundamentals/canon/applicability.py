"""Applicability: whether a dictionary row applies to a filing context, decided from context alone.

Decided before any value is examined (data spec §1). The context carries no value
fields by construction, so a decision can never depend on what a source printed.
Only an applicable row can later be ``NO_SOURCE``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from fundamentals.contracts.basis_status import BasisStatus
from fundamentals.contracts.canonical import (
    ApplicabilityStatus,
    Basis,
    DocumentType,
    PeriodKind,
    ReportingRegime,
    StatementFamily,
)

if TYPE_CHECKING:
    from fundamentals.canon.dictionary import DictionaryRow

# Rule ids for the basis refusals, which apply to every row before its own rule.
STANDALONE_ONLY_RULE_ID = "basis.standalone_only_entity"
ROW_BASIS_RULE_ID = "basis.row_basis_applicability"
# A package reporting kind (Task 5 ``reporting_kind``) is one of these.
REPORTING_KINDS: frozenset[PeriodKind] = frozenset(
    {PeriodKind.QUARTER, PeriodKind.HALF_YEAR, PeriodKind.NINE_MONTH, PeriodKind.YEAR}
)
RULES_KEY = "rules"
# A shareholding pattern is filed at an instant, its own reporting kind (plan D8 R4).
_INSTANT_KINDS = REPORTING_KINDS | {PeriodKind.INSTANT}
_NOT_REPORTING_KIND = "applicability needs a package reporting kind, got {kind}"


def reporting_kinds(document_type: DocumentType | None) -> frozenset[PeriodKind]:
    """The package reporting kinds a document type is filed under."""
    if document_type is DocumentType.SHAREHOLDING_PATTERN:
        return _INSTANT_KINDS
    return REPORTING_KINDS


class ApplicabilityRule(BaseModel):
    """When a row applies: its regime and document type, and the period kinds that require it.

    Outside ``required_in`` the row applies only when the package contains
    ``when_statement_present``, or, with ``when_disclosed``, the row's own disclosure
    (preserved, never fabricated). With ``requires_evidenced_segments`` the row is required
    only for a basis on which the entity's reportable segments are evidenced; otherwise it is
    genuinely inapplicable unless the package contains the statement.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str = Field(min_length=1)
    regime: ReportingRegime
    document_type: DocumentType
    required_in: frozenset[PeriodKind]
    when_statement_present: StatementFamily | None = None
    when_disclosed: bool = False
    requires_evidenced_segments: bool = False
    evidence: str = Field(min_length=1)


class ApplicabilityContext(BaseModel):
    """What is known about a filing before any value is read.

    ``period_kind`` is the package reporting kind. ``entity_basis_status`` and
    ``evidenced_segment_bases`` (bases on which the entity's reportable segments are
    recorded with their evidencing segment-note occurrences) come from evidenced identity
    input, never from the filing being decided. ``disclosed_rows`` names the canonical ids
    whose line or element the package contains, as structure only, never its value.
    """

    model_config = ConfigDict(frozen=True)

    regime: ReportingRegime
    document_type: DocumentType
    statements_present: frozenset[StatementFamily]
    period_kind: PeriodKind
    requested_basis: Basis
    entity_basis_status: BasisStatus
    evidenced_segment_bases: frozenset[Basis]
    disclosed_rows: frozenset[str]

    @field_validator("period_kind")
    @classmethod
    def _reporting_kind(cls, kind: PeriodKind, info: ValidationInfo) -> PeriodKind:
        """Refuse kinds no package of the document type reports under, such as TTM, or an
        instant outside a shareholding pattern."""
        if kind not in reporting_kinds(info.data.get("document_type")):
            raise ValueError(_NOT_REPORTING_KIND.format(kind=kind))
        return kind


class ApplicabilityDecision(BaseModel):
    """The applicability of one row in one context, and the rule that decided it."""

    model_config = ConfigDict(frozen=True)

    status: ApplicabilityStatus
    rule_id: str


def load_applicability_rules(path: Path) -> tuple[ApplicabilityRule, ...]:
    """Read the applicability rules file; schema errors propagate to the dictionary loader."""
    return parse_applicability_rules(path.read_bytes())


def parse_applicability_rules(body: bytes) -> tuple[ApplicabilityRule, ...]:
    """Parse an already captured buffer so a dictionary's content pin covers its rules."""
    data = yaml.safe_load(body)
    return tuple(ApplicabilityRule.model_validate(item) for item in data[RULES_KEY])


def decide_applicability(
    row: DictionaryRow, context: ApplicabilityContext
) -> ApplicabilityDecision:
    """Decide whether ``row`` applies in ``context``, without looking at any value.

    Order: a consolidated request against a standalone-only entity, then the
    row's own basis applicability, then the row's rule (regime and document
    type, then period kind where the rule requires the row, then statement or
    disclosure presence).
    """
    if (
        context.requested_basis is Basis.CONSOLIDATED
        and context.entity_basis_status is BasisStatus.STANDALONE_ONLY
    ):
        return _not_applicable(STANDALONE_ONLY_RULE_ID)
    if context.requested_basis not in row.basis_applicability:
        return _not_applicable(ROW_BASIS_RULE_ID)
    rule = row.applicability_rule
    if rule.regime is not context.regime or rule.document_type is not context.document_type:
        return _not_applicable(rule.rule_id)
    required = context.period_kind in rule.required_in and (
        not rule.requires_evidenced_segments
        or context.requested_basis in context.evidenced_segment_bases
    )
    present = (
        rule.when_statement_present is not None
        and rule.when_statement_present in context.statements_present
    ) or (rule.when_disclosed and row.canonical_id in context.disclosed_rows)
    if required or present:
        return ApplicabilityDecision(status=ApplicabilityStatus.APPLICABLE, rule_id=rule.rule_id)
    return _not_applicable(rule.rule_id)


def _not_applicable(rule_id: str) -> ApplicabilityDecision:
    """Build a ``NOT_APPLICABLE`` decision naming its rule."""
    return ApplicabilityDecision(status=ApplicabilityStatus.NOT_APPLICABLE, rule_id=rule_id)
