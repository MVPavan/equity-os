"""Composition-root configuration for the Fundamentals pipeline.

Non-secret settings load from ``config/fundamentals.yaml`` into frozen pydantic
models here, at the composition root only. No business-logic module reads the
environment or the filesystem for configuration — everything is injected at
construction time (repo rule ``python/safety.md``). Repo-relative paths are
resolved against the repository root (the parent of the ``config`` directory).
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from fundamentals.contracts.comparative import ComparatorKind
from fundamentals.contracts.role import FactRole
from fundamentals.contracts.source_catalog import SourceClass
from fundamentals.extract.guidance_extractor import DEFAULT_GUIDANCE_RULES
from fundamentals.extract.pdf_number_parser import (
    DEFAULT_COLUMN_X_TOLERANCE_PT,
    DEFAULT_MONTH_NAMES,
    DEFAULT_ROW_BAND_TOLERANCE_PT,
    ConditionalLabel,
    PdfLineUnit,
    PdfPrintedUnit,
    PdfTargetLine,
    SubcomponentSummation,
)

_DEFAULT_XBRL_ALIASES: dict[str, str] = {
    "http://www.nseindia.com/NSESymbol": "nse-symbol",
}

# The taxonomy the built-in concept defaults below are written against. An issuer
# filing under another taxonomy (e.g. a SEBI Integrated Filing, ``in-capmkt``) uses
# the same local names, so declaring the prefix is enough to retarget them.
_DEFAULT_TAXONOMY_PREFIX = "in-bse-fin"
_UNKNOWN_OVERRIDE_ERROR = (
    "pdf_parse.label_overrides key {key!r} matches no configured target-line concept"
)


class XbrlMode(StrEnum):
    """How the pipeline obtains the NSE Ind AS XBRL instance."""

    LOCAL = "local"
    LIVE = "live"


class IssuerConfig(BaseModel):
    """Issuer identity and its canonical comparison-key entity scheme."""

    model_config = ConfigDict(frozen=True)

    name: str
    nse_symbol: str
    entity_scheme: str


class QuarterConfig(BaseModel):
    """The issuer quarter under review and its bitemporal anchors."""

    model_config = ConfigDict(frozen=True)

    issuer_quarter: str
    program_quarter: str
    label: str
    period_start: date
    period_end: date
    knowledge_cutoff: datetime


class SourceFileConfig(BaseModel):
    """A held source file: its id, filename under ``raw_dir``, and pinned sha256.

    ``source_class`` is required: a source declares the authority it carries.
    Reconciliation refuses any source whose class it cannot resolve, so a config
    block that names a source must also say what kind of source it is.
    """

    model_config = ConfigDict(frozen=True)

    source_id: str
    source_class: SourceClass
    filename: str
    sha256: str


class XbrlConfig(BaseModel):
    """NSE Ind AS XBRL settings for local (held) or live (polite) retrieval."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    mode: XbrlMode = XbrlMode.LOCAL
    local_path: str
    symbol: str
    timeout_seconds: int = 15
    max_retries: int = 3
    retry_backoff_seconds: float = 2.0
    # As-filed context entity identifiers accepted as this issuer (a pre-rename NSE
    # symbol, or the BSE scrip an Integrated Filing identifies the entity by).
    accepted_entity_ids: tuple[str, ...] = ()
    entity_scheme_aliases: dict[str, str] = Field(
        default_factory=lambda: dict(_DEFAULT_XBRL_ALIASES)
    )
    # As-filed entity ids (keyed by id) accepted as the issuer's canonical id, applied
    # only under the issuer's own entity scheme so a wrong company's file still fails.
    entity_id_aliases: dict[str, str] = Field(default_factory=dict)


class ComparatorInstanceConfig(BaseModel):
    """One hash-pinned prior-quarter XBRL instance for a comparative."""

    model_config = ConfigDict(frozen=True)

    local_path: str
    sha256: str
    period_start: date
    period_end: date
    accept_taxonomy_drift: bool = False


class ComparatorsConfig(BaseModel):
    """Optional QoQ and YoY prior-quarter XBRL comparator instances."""

    model_config = ConfigDict(frozen=True)

    qoq: ComparatorInstanceConfig | None = None
    yoy: ComparatorInstanceConfig | None = None


class SecConfig(BaseModel):
    """SEC 20-F retrospective annual cross-check settings (opt-in, network)."""

    model_config = ConfigDict(frozen=True)

    enabled: bool = False
    user_agent: str = "EquityOS Research"
    cik: int = 1067491
    request_timeout_seconds: float = 30.0
    max_retries: int = 3


# --- general Ind-AS (in-bse-fin) defaults; a different filer overrides in YAML --


def _local_name(concept_qname: str) -> str:
    """The concept's local name, i.e. its qname without the taxonomy prefix."""
    return concept_qname.split(":", 1)[-1]


_INR_CRORE_UNIT = "INR crore"
_INR_UNIT_REF = "INR"
_CRORE_SCALE = 10_000_000
_CRORE_DECIMALS = -7

# The consolidated-vs-standalone discriminator plus the P&L structural markers.
# Matched case-insensitively as substrings by the parser; together with the anchor
# they identify the consolidated P&L (not a standalone / balance-sheet / cash-flow
# / segment page) across the varied SEBI Reg-33 title wordings seen in the wild.
_DEFAULT_SCOPE_MARKER = "Consolidated"
_DEFAULT_STATEMENT_CONFIRMATIONS: tuple[str, ...] = ("Total income",)

# Accepted printed label variants per concept. Matching is contiguous-subsequence
# on normalized tokens, so a leading enumerator ("III. Total income (I+II)") and
# trailing wording are tolerated; only the SEBI-standard variants that differ in
# wording (not enumerator/suffix) need listing here.
_DEFAULT_PDF_TARGET_LINES: tuple[PdfTargetLine, ...] = (
    PdfTargetLine(
        labels=("Total revenue from operations", "Revenue from operations"),
        concept_qname="in-bse-fin:RevenueFromOperations",
        normalized_unit=_INR_CRORE_UNIT,
        unit_ref=_INR_UNIT_REF,
        scale=_CRORE_SCALE,
        decimals=_CRORE_DECIMALS,
        # A filer may print no single revenue total, only sub-components under a
        # value-less header (e.g. TITAN). Reconstruct by summation, accepted only
        # when sub-components + other income == total income (the Income line below,
        # marked is_reconciliation_total). Intra-statement check; never NSE-gated.
        subcomponent_summation=SubcomponentSummation(other_labels=("Other income",)),
    ),
    PdfTargetLine(
        labels=("Total income",),
        concept_qname="in-bse-fin:Income",
        normalized_unit=_INR_CRORE_UNIT,
        unit_ref=_INR_UNIT_REF,
        scale=_CRORE_SCALE,
        decimals=_CRORE_DECIMALS,
        is_reconciliation_total=True,
    ),
    PdfTargetLine(
        labels=("Profit before tax", "Profit/(loss) before tax", "Profit before taxation"),
        concept_qname="in-bse-fin:ProfitBeforeTax",
        normalized_unit=_INR_CRORE_UNIT,
        unit_ref=_INR_UNIT_REF,
        scale=_CRORE_SCALE,
        decimals=_CRORE_DECIMALS,
    ),
    PdfTargetLine(
        labels=(
            "Net profit for the period",
            "Profit for the period",
            "Profit/(loss) for the period",
        ),
        concept_qname="in-bse-fin:ProfitLossForPeriod",
        normalized_unit=_INR_CRORE_UNIT,
        unit_ref=_INR_UNIT_REF,
        scale=_CRORE_SCALE,
        decimals=_CRORE_DECIMALS,
        # A consolidated filer with associates below tax (e.g. LAURUSLABS) prints the
        # profit for the period as "Net profit after tax(es) and share of ...
        # associates". Requiring both the "Net profit after" head AND "associates"
        # binds that line while never matching the pre-associate "Net Profit after
        # tax" (which lacks "associates"); it takes precedence over the plain labels.
        conditional_labels=(
            ConditionalLabel(heads=("Net profit after",), also_contains=("associates",)),
        ),
    ),
    PdfTargetLine(
        labels=("Basic earnings per share", "Basic (in", "Basic"),
        concept_qname="in-bse-fin:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
        normalized_unit="INR per share",
        unit_ref="INR_per_share",
        scale=1,
        decimals=2,
        line_unit=PdfLineUnit.PER_SHARE,
    ),
)


class PdfParseConfig(BaseModel):
    """Per-issuer PDF-parse settings; defaults suit an Ind-AS in-bse-fin filer."""

    model_config = ConfigDict(frozen=True)

    scope_marker: str = _DEFAULT_SCOPE_MARKER
    statement_confirmations: tuple[str, ...] = Field(
        default_factory=lambda: _DEFAULT_STATEMENT_CONFIRMATIONS
    )
    anchor_label: str = "Revenue from operations"
    target_lines: tuple[PdfTargetLine, ...] = Field(
        default_factory=lambda: _DEFAULT_PDF_TARGET_LINES
    )
    currency: str = "INR"
    row_band_tolerance_pt: float = DEFAULT_ROW_BAND_TOLERANCE_PT
    column_x_tolerance_pt: float = DEFAULT_COLUMN_X_TOLERANCE_PT
    month_names: tuple[str, ...] = Field(default_factory=lambda: DEFAULT_MONTH_NAMES)
    # Declared unit of the printed statement, used only when a scanned text layer
    # garbles the marker; a legible printed unit that disagrees still fails closed.
    printed_unit: PdfPrintedUnit | None = None
    # Extra printed labels per concept LOCAL name, appended to that concept's
    # default labels (the defaults keep precedence).
    label_overrides: dict[str, tuple[str, ...]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _reject_unknown_overrides(self) -> PdfParseConfig:
        """Fail closed on an override key naming no configured target line."""
        known = {_local_name(line.concept_qname) for line in self.target_lines}
        for key in self.label_overrides:
            if key not in known:
                raise ValueError(_UNKNOWN_OVERRIDE_ERROR.format(key=key))
        return self

    @property
    def effective_target_lines(self) -> tuple[PdfTargetLine, ...]:
        """Target lines with this issuer's extra labels appended to their concepts."""
        if not self.label_overrides:
            return self.target_lines
        lines: list[PdfTargetLine] = []
        for line in self.target_lines:
            extra = self.label_overrides.get(_local_name(line.concept_qname), ())
            lines.append(
                line.model_copy(update={"labels": (*line.labels, *extra)}) if extra else line
            )
        return tuple(lines)


class RoleConceptConfig(BaseModel):
    """Maps a render P&L role to its taxonomy concept QName; may be optional."""

    model_config = ConfigDict(frozen=True)

    role: FactRole
    concept_qname: str
    required: bool = True


class AuxConceptConfig(BaseModel):
    """An auxiliary concept needed only to close identities; may be optional.

    Non-controlling interest is the canonical optional case: a filer with no
    minority interest simply omits the tag, and the dependent identity is skipped
    rather than failing closed.
    """

    model_config = ConfigDict(frozen=True)

    concept_qname: str
    required: bool = True


class IdentityTermConfig(BaseModel):
    """One signed right-hand term of a configured accounting identity."""

    model_config = ConfigDict(frozen=True)

    sign: Literal[-1, 1]
    concept_qname: str


class IdentityConfig(BaseModel):
    """An accounting identity ``lhs_concept == sum(sign * term)``.

    An identity is skipped (not failed) when any referenced concept is an
    optional concept that the filing does not carry.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    lhs_concept: str
    terms: tuple[IdentityTermConfig, ...]


class GuidanceRuleConfig(BaseModel):
    """A guidance regex rule plus its render label."""

    model_config = ConfigDict(frozen=True)

    metric: str
    label: str
    pattern: str
    horizon: str


def _default_role_concepts() -> tuple[RoleConceptConfig, ...]:
    return (
        RoleConceptConfig(role=FactRole.REVENUE, concept_qname="in-bse-fin:RevenueFromOperations"),
        RoleConceptConfig(role=FactRole.TOTAL_INCOME, concept_qname="in-bse-fin:Income"),
        RoleConceptConfig(role=FactRole.TOTAL_EXPENSES, concept_qname="in-bse-fin:Expenses"),
        RoleConceptConfig(
            role=FactRole.PROFIT_BEFORE_TAX, concept_qname="in-bse-fin:ProfitBeforeTax"
        ),
        RoleConceptConfig(
            role=FactRole.PROFIT_FOR_PERIOD, concept_qname="in-bse-fin:ProfitLossForPeriod"
        ),
        RoleConceptConfig(
            role=FactRole.BASIC_EPS,
            concept_qname=(
                "in-bse-fin:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations"
            ),
        ),
    )


def _default_aux_concepts() -> tuple[AuxConceptConfig, ...]:
    return (
        AuxConceptConfig(concept_qname="in-bse-fin:ProfitOrLossAttributableToOwnersOfParent"),
        AuxConceptConfig(
            concept_qname="in-bse-fin:ProfitOrLossAttributableToNonControllingInterests",
            required=False,
        ),
    )


def _default_cross_check_concepts() -> tuple[str, ...]:
    return (
        "in-bse-fin:RevenueFromOperations",
        "in-bse-fin:Income",
        "in-bse-fin:ProfitBeforeTax",
        "in-bse-fin:ProfitLossForPeriod",
        "in-bse-fin:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
    )


def _default_identities() -> tuple[IdentityConfig, ...]:
    return (
        IdentityConfig(
            name="Profit before tax = Total income − Total expenses",
            lhs_concept="in-bse-fin:ProfitBeforeTax",
            terms=(
                IdentityTermConfig(sign=1, concept_qname="in-bse-fin:Income"),
                IdentityTermConfig(sign=-1, concept_qname="in-bse-fin:Expenses"),
            ),
        ),
        IdentityConfig(
            name="Profit for the period = Attributable to owners + Non-controlling interests",
            lhs_concept="in-bse-fin:ProfitLossForPeriod",
            terms=(
                IdentityTermConfig(
                    sign=1, concept_qname="in-bse-fin:ProfitOrLossAttributableToOwnersOfParent"
                ),
                IdentityTermConfig(
                    sign=1,
                    concept_qname="in-bse-fin:ProfitOrLossAttributableToNonControllingInterests",
                ),
            ),
        ),
    )


class ConceptsConfig(BaseModel):
    """Per-issuer concept map: roles, aux concepts, cross-checks, and identities."""

    model_config = ConfigDict(frozen=True)

    roles: tuple[RoleConceptConfig, ...] = Field(default_factory=_default_role_concepts)
    aux: tuple[AuxConceptConfig, ...] = Field(default_factory=_default_aux_concepts)
    cross_check: tuple[str, ...] = Field(default_factory=_default_cross_check_concepts)
    identities: tuple[IdentityConfig, ...] = Field(default_factory=_default_identities)


def _default_guidance_rules() -> tuple[GuidanceRuleConfig, ...]:
    labels = {
        "revenue_growth": "Revenue growth guidance",
        "operating_margin": "Operating margin guidance",
    }
    return tuple(
        GuidanceRuleConfig(
            metric=rule.metric,
            label=labels.get(rule.metric, rule.metric),
            pattern=rule.pattern,
            horizon=rule.horizon,
        )
        for rule in DEFAULT_GUIDANCE_RULES
    )


class GuidanceConfig(BaseModel):
    """Per-issuer guidance rules; empty is valid (no numeric guidance disclosed)."""

    model_config = ConfigDict(frozen=True)

    rules: tuple[GuidanceRuleConfig, ...] = Field(default_factory=_default_guidance_rules)


def _reprefixed(concept_qname: str, prefix: str) -> str:
    """Retarget a default-taxonomy qname onto ``prefix``; other qnames pass through.

    An explicit per-issuer override that already names another taxonomy is left
    alone — only the built-in ``in-bse-fin`` defaults are retargeted.
    """
    local = concept_qname.removeprefix(f"{_DEFAULT_TAXONOMY_PREFIX}:")
    if local == concept_qname:
        return concept_qname
    return f"{prefix}:{local}"


def _reprefixed_concepts(concepts: ConceptsConfig, prefix: str) -> ConceptsConfig:
    """Retarget every role, aux, cross-check, and identity qname onto ``prefix``."""
    return concepts.model_copy(
        update={
            "roles": tuple(
                role.model_copy(update={"concept_qname": _reprefixed(role.concept_qname, prefix)})
                for role in concepts.roles
            ),
            "aux": tuple(
                aux.model_copy(update={"concept_qname": _reprefixed(aux.concept_qname, prefix)})
                for aux in concepts.aux
            ),
            "cross_check": tuple(_reprefixed(concept, prefix) for concept in concepts.cross_check),
            "identities": tuple(
                identity.model_copy(
                    update={
                        "lhs_concept": _reprefixed(identity.lhs_concept, prefix),
                        "terms": tuple(
                            term.model_copy(
                                update={"concept_qname": _reprefixed(term.concept_qname, prefix)}
                            )
                            for term in identity.terms
                        ),
                    }
                )
                for identity in concepts.identities
            ),
        }
    )


def _reprefixed_pdf_parse(pdf_parse: PdfParseConfig, prefix: str) -> PdfParseConfig:
    """Retarget every PDF target-line qname onto ``prefix`` (local names are unchanged)."""
    return pdf_parse.model_copy(
        update={
            "target_lines": tuple(
                line.model_copy(update={"concept_qname": _reprefixed(line.concept_qname, prefix)})
                for line in pdf_parse.target_lines
            )
        }
    )


class FundamentalsConfig(BaseModel):
    """The full, resolved composition-root configuration."""

    model_config = ConfigDict(frozen=True)

    issuer: IssuerConfig
    quarter: QuarterConfig
    raw_dir: str
    store_db: str
    results_pdf: SourceFileConfig
    transcript_pdf: SourceFileConfig
    xbrl: XbrlConfig
    comparators: ComparatorsConfig | None = None
    sec: SecConfig = Field(default_factory=SecConfig)
    pdf_parse: PdfParseConfig = Field(default_factory=PdfParseConfig)
    concepts: ConceptsConfig = Field(default_factory=ConceptsConfig)
    guidance: GuidanceConfig = Field(default_factory=GuidanceConfig)
    # The taxonomy this issuer files under. Its local names are shared with the
    # default taxonomy, so declaring the prefix retargets the concept defaults.
    taxonomy_prefix: str = _DEFAULT_TAXONOMY_PREFIX

    @model_validator(mode="after")
    def _retarget_taxonomy(self) -> FundamentalsConfig:
        """Rewrite the default-taxonomy qnames onto this issuer's taxonomy prefix."""
        if self.taxonomy_prefix == _DEFAULT_TAXONOMY_PREFIX:
            return self
        return self.model_copy(
            update={
                "concepts": _reprefixed_concepts(self.concepts, self.taxonomy_prefix),
                "pdf_parse": _reprefixed_pdf_parse(self.pdf_parse, self.taxonomy_prefix),
            }
        )

    def repo_root(self, config_path: Path) -> Path:
        """Return the repository root given the loaded config file's path."""
        return config_path.resolve().parent.parent

    def results_pdf_path(self, config_path: Path) -> Path:
        """Absolute path to the held results PDF."""
        return self.repo_root(config_path) / self.raw_dir / self.results_pdf.filename

    def transcript_pdf_path(self, config_path: Path) -> Path:
        """Absolute path to the held transcript PDF."""
        return self.repo_root(config_path) / self.raw_dir / self.transcript_pdf.filename

    def xbrl_local_path(self, config_path: Path) -> Path:
        """Absolute path to the held/synthetic XBRL instance."""
        return self.repo_root(config_path) / self.xbrl.local_path

    def comparator_path(self, config_path: Path, kind: ComparatorKind) -> Path | None:
        """Resolve one declared comparator instance path against the repository root."""
        if self.comparators is None:
            return None
        instance = self.comparators.qoq if kind is ComparatorKind.QOQ else self.comparators.yoy
        if instance is None:
            return None
        return self.repo_root(config_path) / instance.local_path

    def store_db_path(self, config_path: Path) -> str:
        """Resolve the store DB path (``:memory:`` passes through)."""
        if self.store_db == ":memory:":
            return self.store_db
        return str(self.repo_root(config_path) / self.store_db)


def load_config(config_path: Path) -> FundamentalsConfig:
    """Load and validate the non-secret YAML configuration."""
    data: Any = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return FundamentalsConfig.model_validate(data)
