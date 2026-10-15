"""Private pipeline helpers: selection, anchoring, SEC cross-check and ledger reuse."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

import structlog

from fundamentals.api.config import (
    ASSOCIATES_SHARE_CONCEPT,
    TAX_EXPENSE_CONCEPT,
    FundamentalsConfig,
)
from fundamentals.api.source_admission import SourceAdmissionError, utc_time
from fundamentals.contracts.guidance_claim import GuidanceClaim
from fundamentals.contracts.observation import AccountingFramework, Observation, PeriodType, Scope
from fundamentals.extract.guidance_extractor import PERCENT_UNIT
from fundamentals.extract.pdf_number_parser import PdfParseSpec
from fundamentals.extract.xbrl_parser import FactSelectionError, select_observation
from fundamentals.ingest.sec_source import SecAnnualSource, SecFetchError, SecSourceConfig
from fundamentals.output.earnings_update import FactRole, RenderedCalculation, anchor_label
from fundamentals.output.management_ledger import ManagementLedger, reconcile_ledger
from fundamentals.output.pnl_lines import headline_line, tax_lines

_LOGGER = structlog.get_logger("fundamentals.pipeline")


class PipelineError(RuntimeError):
    """Raised when a material fact cannot be verified — the pipeline fails closed."""


def normalize_entity(
    obs: Observation,
    scheme_aliases: dict[str, str],
    id_aliases: dict[str, str],
    issuer_scheme: str,
) -> Observation:
    """Canonicalise an observation's entity scheme, then its id, across sources.

    The id alias applies only once the canonical scheme is the issuer scheme the
    run stamps on PDF facts, so an as-filed identifier (e.g. a scrip code) collapses
    onto the issuer's symbol while an id under any other scheme, or one with no
    declared alias, is left untouched and still fails the cross-check.
    """
    canonical_scheme = scheme_aliases.get(obs.entity_scheme, obs.entity_scheme)
    entity_id = obs.entity_id
    if canonical_scheme == issuer_scheme:
        entity_id = id_aliases.get(entity_id, entity_id)
    if canonical_scheme == obs.entity_scheme and entity_id == obs.entity_id:
        return obs
    return obs.model_copy(update={"entity_scheme": canonical_scheme, "entity_id": entity_id})


def _select_consolidated_quarter(
    observations: tuple[Observation, ...],
    concept: str,
    config: FundamentalsConfig,
) -> Observation:
    """Select the segment-free consolidated-quarter observation, fail closed."""
    return select_observation(
        observations,
        concept_qname=concept,
        scope=Scope.CONSOLIDATED,
        period_type=PeriodType.DURATION,
        period_start=config.quarter.period_start,
        period_end=config.quarter.period_end,
    )


def select_optional(
    observations: tuple[Observation, ...],
    concept: str,
    config: FundamentalsConfig,
    *,
    required: bool,
) -> Observation | None:
    """Select a consolidated-quarter observation, or ``None`` if optional/absent.

    Required concepts still fail closed on a zero/ambiguous match; only optional
    concepts (e.g. non-controlling interest for a filer without minority
    interest) may be missing without aborting the run.
    """
    try:
        return _select_consolidated_quarter(observations, concept, config)
    except FactSelectionError:
        if required:
            raise
        return None


def pdf_parse_spec(config: FundamentalsConfig) -> PdfParseSpec:
    """Assemble the PDF-parse spec from per-issuer config + run identity."""
    return PdfParseSpec(
        scope_marker=config.pdf_parse.scope_marker,
        statement_confirmations=config.pdf_parse.statement_confirmations,
        anchor_label=config.pdf_parse.anchor_label,
        target_lines=config.pdf_parse.effective_target_lines,
        entity_scheme=config.issuer.entity_scheme,
        entity_id=config.issuer.nse_symbol,
        currency=config.pdf_parse.currency,
        scope=Scope.CONSOLIDATED,
        accounting_basis=AccountingFramework.IND_AS,
        period_start=config.quarter.period_start,
        period_end=config.quarter.period_end,
        row_band_tolerance_pt=config.pdf_parse.row_band_tolerance_pt,
        column_x_tolerance_pt=config.pdf_parse.column_x_tolerance_pt,
        month_names=config.pdf_parse.month_names,
        printed_unit=config.pdf_parse.printed_unit,
    )


def claim_range_quote(claim: GuidanceClaim) -> str:
    """Independent expected quote: the claim's own asserted range or bound.

    Used to actually test the quote anchor — the resolved span must carry the
    claim's asserted numbers, so a mis-anchored span fails rather than
    tautologically re-reading the stored quote. A percentage range is expected in
    its ``x% to y%`` form when the transcript phrased it that way; otherwise the
    lower bound as printed (plain or with thousands separators). A bound that
    appears in neither form fails closed at the anchor.
    """
    quote = claim.source_quote or ""
    if claim.unit == PERCENT_UNIT and claim.lower_bound != claim.upper_bound:
        range_text = f"{claim.lower_bound}% to {claim.upper_bound}%"
        if not quote or range_text in quote:
            return range_text
    plain = str(claim.lower_bound)
    grouped = f"{claim.lower_bound:,}"
    return grouped if grouped in quote and plain not in quote else plain


def required_concepts(config: FundamentalsConfig) -> frozenset[str]:
    """The concept set the XBRL parse must prove present (per-statement completeness)."""
    required: set[str] = {role.concept_qname for role in config.concepts.roles if role.required}
    required.update(aux.concept_qname for aux in config.concepts.aux if aux.required)
    required.update(config.concepts.cross_check)
    return frozenset(required)


def run_sec_cross_check(config: FundamentalsConfig) -> str:
    """Run the optional SEC 20-F annual cross-check; never foot it against Q1."""
    if not config.sec.enabled:
        return "not run (disabled; retrospective annual adapter only)"
    try:
        source = SecAnnualSource(
            SecSourceConfig(
                user_agent=config.sec.user_agent,
                cik=config.sec.cik,
                request_timeout_seconds=config.sec.request_timeout_seconds,
                max_retries=config.sec.max_retries,
            )
        )
        result = source.fetch()
    except SecFetchError as error:
        _LOGGER.warning("sec_cross_check_unavailable", error=str(error))
        return f"unavailable ({error})"
    if not result.excluded_from_q1:
        raise PipelineError(
            "SEC annual facts are not excluded from the Q1 cutoff — refusing to leak them"
        )
    return (
        f"{len(result.observations)} FY25 annual IFRS/USD facts loaded and correctly "
        "EXCLUDED from the Q1 evidence package (knowledge_time > cutoff); not cross-footed"
    )


def reconcile_current_guidance(
    prior: ManagementLedger | None,
    *,
    symbol: str,
    issuer_quarter: str,
    claims: Sequence[GuidanceClaim],
    cutoff: datetime,
    derivation_completed_at: datetime,
) -> ManagementLedger:
    """Reuse complete identical anchored output, retaining the original artifact."""
    if (
        prior is not None
        and prior.updated_quarter == issuer_quarter
        and prior.quarter_claims is not None
    ):
        excluded = {"provenance": {"retrieved_at", "first_seen_at"}}
        old = {
            (claim.metric, claim.horizon, claim.scope): claim.model_dump(exclude=excluded)
            for claim in prior.quarter_claims
        }
        current = {
            (claim.metric, claim.horizon, claim.scope): claim.model_dump(exclude=excluded)
            for claim in claims
        }
        if len(old) == len(prior.quarter_claims) and len(current) == len(claims) and old == current:
            for claim in prior.quarter_claims:
                for clock in (claim.provenance.retrieved_at, claim.provenance.first_seen_at):
                    if clock is None:
                        raise SourceAdmissionError(
                            "retained guidance clocks require present UTC time"
                        )
                    retained_at = utc_time(clock)
                    if retained_at > cutoff or retained_at > derivation_completed_at:
                        raise SourceAdmissionError(
                            "retained guidance clocks exceed cutoff or "
                            "current derivation completion"
                        )
            # Strict ledger reconciliation checks the retained artifact itself;
            # fresh report claims above keep their actual acquisition clocks.
            return reconcile_ledger(
                prior, symbol=symbol, issuer_quarter=issuer_quarter, claims=prior.quarter_claims
            )
    return reconcile_ledger(prior, symbol=symbol, issuer_quarter=issuer_quarter, claims=claims)


# Render roles whose sourced value the calculations section derives from.
_REVENUE_ROLE = FactRole.REVENUE
_TOTAL_INCOME_ROLE = FactRole.TOTAL_INCOME
_PBT_ROLE = FactRole.PROFIT_BEFORE_TAX
_XBRL_PARSE = "the filed XBRL parse"


def build_calculations(
    role_obs: dict[FactRole, Observation],
    concept_obs: dict[str, Observation],
    config: FundamentalsConfig,
) -> tuple[RenderedCalculation, ...]:
    """Derive sourced calculations over stored facts and the filed XBRL report operands."""
    total_income = role_obs[_TOTAL_INCOME_ROLE].normalized_value
    revenue = role_obs[_REVENUE_ROLE].normalized_value
    pbt = role_obs[_PBT_ROLE].normalized_value
    if pbt == 0:
        raise PipelineError(
            "cannot derive the effective tax rate: profit before tax is zero (division guard)"
        )
    tax, share = (
        concept_obs.get(config.report_operand(name))
        for name in (TAX_EXPENSE_CONCEPT, ASSOCIATES_SHARE_CONCEPT)
    )
    other_income = total_income - revenue
    return (
        RenderedCalculation(
            label="Non-operating / other income gap (₹ crore)",
            result=f"{int(other_income):,}",
            trace=f"Total income {int(total_income):,} − Revenue {int(revenue):,}",
        ),
        *tax_lines(pbt=pbt, tax=_operand(tax), sources=_operand_source(tax)),
        headline_line(pbt=pbt, share_of_associates=_operand(share), sources=_operand_source(share)),
    )


def _operand(obs: Observation | None) -> Decimal | None:
    """A filed report operand's value, if the parse carried it."""
    return None if obs is None else obs.normalized_value


def _operand_source(obs: Observation | None) -> str:
    """Where a report operand was read: its XBRL anchor, else the parse that lacked it."""
    return _XBRL_PARSE if obs is None else anchor_label(obs.provenance)
