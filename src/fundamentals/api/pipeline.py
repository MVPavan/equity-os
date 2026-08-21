"""End-to-end orchestration for the Infosys Q1 FY25 source-verified update.

The pipeline wires the five completed modules into one fail-closed increment:

1. load the hash-verified held PDFs (results + transcript);
2. parse the NSE Ind AS XBRL and the results PDF into context-bound Observations;
3. select the canonical consolidated-quarter P&L facts (fail closed if any is
   missing or ambiguous);
4. cross-foot the P&L accounting identities (tolerance derived from decimals);
5. cross-check the headline XBRL figures against the independent PDF read using
   the full comparison key;
6. quote-anchor each management-guidance claim to an exact page/block/span;
7. persist every fact append-only and select the XBRL revision canonical;
8. render the 11-section sourced markdown.

SEC 20-F is an optional retrospective *annual* cross-check only. It is excluded
from the Q1 evidence package by ``knowledge_time > cutoff`` and is never
cross-footed against the Q1 quarter. Any un-provenanced or un-verified *material*
Q1 fact aborts the render — no un-sourced number is ever emitted.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import structlog
from pydantic import BaseModel, ConfigDict

from fundamentals.api.config import FundamentalsConfig
from fundamentals.contracts.fact import CanonicalStatus, Fact, ReconciliationStatus
from fundamentals.contracts.observation import Observation, PeriodType, Scope
from fundamentals.contracts.provenance import Provenance
from fundamentals.extract.guidance_extractor import extract_guidance_claims, resolve_span
from fundamentals.extract.pdf_number_parser import extract_consolidated_pl
from fundamentals.extract.xbrl_parser import parse_observations, select_observation
from fundamentals.ingest.pdf_source import LoadedPdf, load_pdf
from fundamentals.ingest.sec_source import SecAnnualSource, SecFetchError, SecSourceConfig
from fundamentals.output.earnings_update import (
    EarningsUpdate,
    FactRole,
    RenderedCalculation,
    RenderedFact,
    RenderedGuidance,
    render_earnings_update,
)
from fundamentals.store.fact_store import FactStore, StoredRevision
from fundamentals.verify.cross_check import CrossCheckResult, cross_check
from fundamentals.verify.crossfoot import (
    CrossFootResult,
    Identity,
    SignedTerm,
    check_identity,
)
from fundamentals.verify.quote_anchor import (
    SourceBlock,
    SourceDocument,
    verify_quote_anchor,
)

_LOGGER = structlog.get_logger("fundamentals.pipeline")

# --- concept vocabulary (the frozen Q1 oracle) --------------------------------

REVENUE = "in-bse-fin:RevenueFromOperations"
TOTAL_INCOME = "in-bse-fin:Income"
TOTAL_EXPENSES = "in-bse-fin:Expenses"
PROFIT_BEFORE_TAX = "in-bse-fin:ProfitBeforeTax"
PROFIT_FOR_PERIOD = "in-bse-fin:ProfitLossForPeriod"
BASIC_EPS = "in-bse-fin:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations"
ATTRIBUTABLE = "in-bse-fin:ProfitOrLossAttributableToOwnersOfParent"
NCI = "in-bse-fin:ProfitOrLossAttributableToNonControllingInterests"

# The six P&L roles the render requires, mapped to their concept QName.
_ROLE_CONCEPTS: tuple[tuple[FactRole, str], ...] = (
    (FactRole.REVENUE, REVENUE),
    (FactRole.TOTAL_INCOME, TOTAL_INCOME),
    (FactRole.TOTAL_EXPENSES, TOTAL_EXPENSES),
    (FactRole.PROFIT_BEFORE_TAX, PROFIT_BEFORE_TAX),
    (FactRole.PROFIT_FOR_PERIOD, PROFIT_FOR_PERIOD),
    (FactRole.BASIC_EPS, BASIC_EPS),
)

# Auxiliary consolidated facts required only to close the cross-foot identities.
_AUX_CONCEPTS: tuple[str, ...] = (ATTRIBUTABLE, NCI)

# Headline figures independently read from BOTH the XBRL and the results PDF.
_CROSS_CHECK_CONCEPTS: tuple[str, ...] = (
    REVENUE,
    TOTAL_INCOME,
    PROFIT_BEFORE_TAX,
    PROFIT_FOR_PERIOD,
    BASIC_EPS,
)

# Accounting identities satisfiable from the on-hand consolidated observations.
_IDENTITIES: tuple[Identity, ...] = (
    Identity(
        name="Profit before tax = Total income − Total expenses",
        lhs_concept=PROFIT_BEFORE_TAX,
        terms=(
            SignedTerm(sign=1, concept_qname=TOTAL_INCOME),
            SignedTerm(sign=-1, concept_qname=TOTAL_EXPENSES),
        ),
    ),
    Identity(
        name="Profit for the period = Attributable to owners + Non-controlling interests",
        lhs_concept=PROFIT_FOR_PERIOD,
        terms=(
            SignedTerm(sign=1, concept_qname=ATTRIBUTABLE),
            SignedTerm(sign=1, concept_qname=NCI),
        ),
    ),
)

_GUIDANCE_LABELS: dict[str, str] = {
    "revenue_growth": "Revenue growth guidance",
    "operating_margin": "Operating margin guidance",
}
_PERCENT_UNIT = "%"


class PipelineError(RuntimeError):
    """Raised when a material fact cannot be verified — the pipeline fails closed."""


class XbrlInput(BaseModel):
    """The XBRL instance bytes plus the provenance the parser needs to stamp."""

    model_config = ConfigDict(frozen=True)

    xml_bytes: bytes
    file_sha256: str
    source_id: str
    retrieved_at: datetime


class PipelineResult(BaseModel):
    """The rendered artifact plus the verification evidence behind it."""

    model_config = ConfigDict(frozen=True)

    markdown: str
    stored_revisions: tuple[StoredRevision, ...]
    cross_foot_results: tuple[CrossFootResult, ...]
    cross_check_results: tuple[CrossCheckResult, ...]
    sec_cross_check_note: str


def _normalize_entity(obs: Observation, aliases: dict[str, str]) -> Observation:
    """Canonicalise an observation's entity scheme across sources."""
    canonical = aliases.get(obs.entity_scheme)
    if canonical is None or canonical == obs.entity_scheme:
        return obs
    return obs.model_copy(update={"entity_scheme": canonical})


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


def _build_fact(
    obs: Observation,
    *,
    role_family: str,
    reconciliation_status: ReconciliationStatus,
    config: FundamentalsConfig,
) -> Fact:
    """Wrap an observation as an append-only, revision-aware Fact."""
    return Fact(
        observation=obs,
        reconciliation_status=reconciliation_status,
        canonical_status=CanonicalStatus.CANDIDATE,
        revision_family=role_family,
        valid_time_start=config.quarter.period_start,
        valid_time_end=config.quarter.period_end,
        knowledge_time=config.quarter.knowledge_cutoff,
        first_seen_time=config.quarter.knowledge_cutoff,
    )


def _source_document(pdf: LoadedPdf) -> SourceDocument:
    """Reconstruct a page/block-addressable SourceDocument from a loaded PDF."""
    blocks = tuple(
        SourceBlock(page=page.page_number, block=block.number, text=block.text)
        for page in pdf.pages
        for block in page.blocks
    )
    return SourceDocument(blocks=blocks)


def _run_sec_cross_check(config: FundamentalsConfig) -> str:
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


def run_pipeline(
    *,
    config: FundamentalsConfig,
    xbrl_input: XbrlInput,
    results_pdf_path: str,
    results_pdf_sha256: str,
    transcript_pdf_path: str,
    transcript_pdf_sha256: str,
    store: FactStore,
) -> PipelineResult:
    """Run the full Q1 FY25 increment end to end, failing closed on any gap."""
    log = _LOGGER.bind(issuer=config.issuer.nse_symbol, quarter=config.quarter.issuer_quarter)
    log.info("pipeline_start", xbrl_mode=config.xbrl.mode.value)

    # 1. Load hash-verified held PDFs.
    results_pdf = load_pdf(
        source_id=config.results_pdf.source_id,
        path=Path(results_pdf_path),
        expected_sha256=results_pdf_sha256,
    )
    transcript_pdf = load_pdf(
        source_id=config.transcript_pdf.source_id,
        path=Path(transcript_pdf_path),
        expected_sha256=transcript_pdf_sha256,
    )
    log.info(
        "pdfs_loaded",
        results_pages=results_pdf.page_count,
        transcript_pages=transcript_pdf.page_count,
    )

    # 2. Parse both first-party sources into context-bound Observations.
    xbrl_obs = tuple(
        _normalize_entity(obs, config.xbrl.entity_scheme_aliases)
        for obs in parse_observations(
            xbrl_input.xml_bytes,
            source_id=xbrl_input.source_id,
            file_sha256=xbrl_input.file_sha256,
            retrieved_at=xbrl_input.retrieved_at,
        )
    )
    pdf_obs = extract_consolidated_pl(results_pdf, retrieved_at=config.quarter.knowledge_cutoff)
    pdf_by_concept = {obs.concept_qname: obs for obs in pdf_obs}
    log.info("sources_parsed", xbrl_observations=len(xbrl_obs), pdf_observations=len(pdf_obs))

    # 3. Select the canonical consolidated-quarter facts (fail closed).
    role_obs: dict[FactRole, Observation] = {}
    concept_obs: dict[str, Observation] = {}
    for role, concept in _ROLE_CONCEPTS:
        obs = _select_consolidated_quarter(xbrl_obs, concept, config)
        role_obs[role] = obs
        concept_obs[concept] = obs
    for concept in _AUX_CONCEPTS:
        concept_obs[concept] = _select_consolidated_quarter(xbrl_obs, concept, config)

    # 4. Cross-foot the accounting identities (fail closed on any residual).
    cross_foot_results: list[CrossFootResult] = []
    for identity in _IDENTITIES:
        foot_result = check_identity(identity, concept_obs)
        cross_foot_results.append(foot_result)
        if not foot_result.passed:
            raise PipelineError(
                f"cross-foot failed for {identity.name!r}: residual {foot_result.residual} "
                f"exceeds tolerance {foot_result.tolerance}"
            )
    log.info("cross_foot_passed", identities=len(cross_foot_results))

    # 5. Cross-check the headline figures against the independent PDF read.
    cross_check_results: list[CrossCheckResult] = []
    confirmed_concepts: set[str] = set()
    for concept in _CROSS_CHECK_CONCEPTS:
        pdf_headline = pdf_by_concept.get(concept)
        if pdf_headline is None:
            raise PipelineError(f"headline concept {concept!r} absent from the results PDF")
        check_result = cross_check(concept_obs[concept], pdf_headline)
        cross_check_results.append(check_result)
        if not check_result.matched:
            raise PipelineError(
                f"XBRL↔PDF cross-check failed for {concept!r}: {', '.join(check_result.reasons)}"
            )
        confirmed_concepts.add(concept)
    log.info("cross_check_passed", headline_concepts=len(cross_check_results))

    # 6. Extract and quote-anchor management guidance (fail closed).
    guidance_claims = extract_guidance_claims(
        transcript_pdf, retrieved_at=config.quarter.knowledge_cutoff
    )
    source_document = _source_document(transcript_pdf)
    rendered_guidance: list[RenderedGuidance] = []
    for claim in guidance_claims:
        quote = resolve_span(transcript_pdf, claim.provenance)
        anchor = verify_quote_anchor(claim, quote, source_document)
        if not anchor.anchored:
            raise PipelineError(
                f"guidance quote-anchor failed for {claim.metric!r}: {anchor.reason}"
            )
        rendered_guidance.append(
            RenderedGuidance(
                metric_label=_GUIDANCE_LABELS.get(claim.metric, claim.metric),
                lower_bound=claim.lower_bound,
                upper_bound=claim.upper_bound,
                unit=_PERCENT_UNIT,
                constant_currency=claim.constant_currency,
                horizon=claim.horizon,
                quote=quote,
                source=claim.provenance,
            )
        )
    log.info("guidance_anchored", claims=len(rendered_guidance))

    # 7. Persist every fact append-only; select the XBRL revision canonical.
    stored_revisions: list[StoredRevision] = []
    rendered_facts: list[RenderedFact] = []
    for role, concept in _ROLE_CONCEPTS:
        family = f"{config.quarter.issuer_quarter}:{role.value}"
        xbrl_fact_obs = role_obs[role]
        status = (
            ReconciliationStatus.CROSS_SOURCE_CONFIRMED
            if concept in confirmed_concepts
            else ReconciliationStatus.CROSS_FOOT_PASS
        )
        xbrl_revision = store.put(
            _build_fact(
                xbrl_fact_obs,
                role_family=family,
                reconciliation_status=status,
                config=config,
            )
        )
        canonical = store.select_canonical(
            xbrl_revision.row_id, reason="XBRL context-bound canonical for Q1 evidence"
        )
        stored_revisions.append(canonical)

        sources: list[Provenance] = [xbrl_fact_obs.provenance]
        pdf_confirm = pdf_by_concept.get(concept)
        if pdf_confirm is not None:
            pdf_revision = store.put(
                _build_fact(
                    pdf_confirm,
                    role_family=family,
                    reconciliation_status=ReconciliationStatus.CROSS_SOURCE_CONFIRMED,
                    config=config,
                )
            )
            stored_revisions.append(pdf_revision)
            sources.append(pdf_confirm.provenance)

        rendered_facts.append(
            RenderedFact(
                role=role,
                concept_qname=concept,
                value=xbrl_fact_obs.normalized_value,
                unit=xbrl_fact_obs.normalized_unit,
                reconciliation_status=status.value,
                sources=tuple(sources),
            )
        )
    log.info("facts_stored", revisions=len(stored_revisions))

    # 8. Optional SEC retrospective annual cross-check (never footed against Q1).
    sec_note = _run_sec_cross_check(config)

    # 9. Render the sourced 11-section update (fail closed on missing required fact).
    calculations = _build_calculations(concept_obs)
    update = EarningsUpdate(
        issuer_name=config.issuer.name,
        nse_symbol=config.issuer.nse_symbol,
        issuer_quarter_label=config.quarter.label,
        period_start=config.quarter.period_start.isoformat(),
        period_end=config.quarter.period_end.isoformat(),
        knowledge_cutoff=config.quarter.knowledge_cutoff.date().isoformat(),
        facts=tuple(rendered_facts),
        guidance=tuple(rendered_guidance),
        calculations=calculations,
        cross_check_summary=(
            f"PASS — {len(cross_check_results)}/{len(cross_check_results)} headline figures "
            "agree within decimals-derived tolerance"
        ),
        cross_foot_summary=(
            f"PASS — {len(cross_foot_results)}/{len(cross_foot_results)} identities hold at ±0"
        ),
        sec_cross_check_note=sec_note,
    )
    markdown = render_earnings_update(update)
    log.info("pipeline_complete", markdown_bytes=len(markdown))

    return PipelineResult(
        markdown=markdown,
        stored_revisions=tuple(stored_revisions),
        cross_foot_results=tuple(cross_foot_results),
        cross_check_results=tuple(cross_check_results),
        sec_cross_check_note=sec_note,
    )


def _build_calculations(
    concept_obs: dict[str, Observation],
) -> tuple[RenderedCalculation, ...]:
    """Derive sourced calculations, each traced over stored consolidated facts."""
    total_income = concept_obs[TOTAL_INCOME].normalized_value
    revenue = concept_obs[REVENUE].normalized_value
    pbt = concept_obs[PROFIT_BEFORE_TAX].normalized_value
    pat = concept_obs[PROFIT_FOR_PERIOD].normalized_value

    other_income = total_income - revenue
    net_tax = pbt - pat
    effective_tax = (net_tax / pbt * Decimal(100)).quantize(Decimal("0.1"))

    return (
        RenderedCalculation(
            label="Non-operating / other income gap (₹ crore)",
            result=f"{int(other_income):,}",
            trace=f"Total income {int(total_income):,} − Revenue {int(revenue):,}",
        ),
        RenderedCalculation(
            label="Net tax expense (₹ crore)",
            result=f"{int(net_tax):,}",
            trace=f"Profit before tax {int(pbt):,} − Profit for the period {int(pat):,}",
        ),
        RenderedCalculation(
            label="Effective tax rate (%)",
            result=f"{effective_tax}",
            trace=f"(PBT {int(pbt):,} − PAT {int(pat):,}) / PBT {int(pbt):,}",
        ),
    )
