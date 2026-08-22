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
7. render the 11-section sourced markdown;
8. only after every gate AND the render succeed, persist every fact append-only
   and select the XBRL revision canonical — so a failed run leaves no partial
   canonical state.

SEC 20-F is an optional retrospective *annual* cross-check only. It is excluded
from the Q1 evidence package by ``knowledge_time > cutoff`` and is never
cross-footed against the Q1 quarter. Any un-provenanced or un-verified *material*
Q1 fact aborts the render — no un-sourced number is ever emitted.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import structlog
from pydantic import BaseModel, ConfigDict

from fundamentals.api.config import FundamentalsConfig
from fundamentals.contracts.fact import CanonicalStatus, Fact, ReconciliationStatus
from fundamentals.contracts.guidance_claim import GuidanceClaim
from fundamentals.contracts.observation import (
    AccountingFramework,
    Observation,
    PeriodType,
    Scope,
)
from fundamentals.contracts.provenance import Provenance
from fundamentals.extract.guidance_extractor import (
    GuidanceExtractionError,
    GuidanceRule,
    extract_guidance_claims,
    resolve_span,
)
from fundamentals.extract.pdf_number_parser import PdfParseSpec, extract_consolidated_pl
from fundamentals.extract.xbrl_parser import (
    FactSelectionError,
    parse_observations,
    select_observation,
)
from fundamentals.ingest.pdf_source import LoadedPdf, load_pdf
from fundamentals.ingest.sec_source import SecAnnualSource, SecFetchError, SecSourceConfig
from fundamentals.output.earnings_update import (
    EarningsUpdate,
    FactRole,
    RenderedCalculation,
    RenderedFact,
    RenderedGuidance,
    VerificationOutcome,
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

_PERCENT_UNIT = "%"

# Render roles whose sourced value the calculations section derives from.
_REVENUE_ROLE = FactRole.REVENUE
_TOTAL_INCOME_ROLE = FactRole.TOTAL_INCOME
_PBT_ROLE = FactRole.PROFIT_BEFORE_TAX
_PAT_ROLE = FactRole.PROFIT_FOR_PERIOD


class PipelineError(RuntimeError):
    """Raised when a material fact cannot be verified — the pipeline fails closed."""


class _PlannedWrite(BaseModel):
    """A store write deferred until all gates and the render succeed."""

    model_config = ConfigDict(frozen=True)

    fact: Fact
    make_canonical: bool


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


def _select_optional(
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


def _pdf_parse_spec(config: FundamentalsConfig) -> PdfParseSpec:
    """Assemble the PDF-parse spec from per-issuer config + run identity."""
    return PdfParseSpec(
        statement_markers=config.pdf_parse.statement_markers,
        anchor_label=config.pdf_parse.anchor_label,
        target_lines=config.pdf_parse.target_lines,
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
    )


def _claim_range_quote(claim: GuidanceClaim) -> str:
    """Independent expected quote: the claim's own asserted percentage range.

    Used to actually test the quote anchor — the recorded span must contain the
    claim's asserted range, so a mis-anchored span fails rather than tautologically
    re-reading itself.
    """
    return f"{claim.lower_bound}% to {claim.upper_bound}%"


def _build_fact(
    obs: Observation,
    *,
    role_family: str,
    reconciliation_status: ReconciliationStatus,
    config: FundamentalsConfig,
    run_id: str,
) -> Fact:
    """Wrap an observation as an append-only, revision-aware Fact."""
    return Fact(
        observation=obs,
        reconciliation_status=reconciliation_status,
        canonical_status=CanonicalStatus.CANDIDATE,
        revision_family=role_family,
        run_id=run_id,
        valid_time_start=config.quarter.period_start,
        valid_time_end=config.quarter.period_end,
        knowledge_time=config.quarter.knowledge_cutoff,
        first_seen_time=config.quarter.knowledge_cutoff,
    )


def _required_concepts(config: FundamentalsConfig) -> frozenset[str]:
    """The concept set the XBRL parse must prove present (per-statement completeness)."""
    required: set[str] = {role.concept_qname for role in config.concepts.roles if role.required}
    required.update(aux.concept_qname for aux in config.concepts.aux if aux.required)
    required.update(config.concepts.cross_check)
    return frozenset(required)


def _guidance_quote_holds(claim: GuidanceClaim, resolved_span_text: str) -> bool:
    """Verify the anchored span still carries the claim captured at extraction.

    The resolved span must equal the ``source_quote`` stored at extraction (so a
    re-pointed provenance fails), and the claim's numeric bounds must be
    represented in that quote (so mutating 3–4% to 8–10% while keeping the old
    provenance fails).
    """
    if claim.source_quote is None:
        return False
    if resolved_span_text != claim.source_quote:
        return False
    return (
        f"{claim.lower_bound}%" in claim.source_quote
        and f"{claim.upper_bound}%" in claim.source_quote
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
    run_id = uuid.uuid4().hex
    log = _LOGGER.bind(
        issuer=config.issuer.nse_symbol, quarter=config.quarter.issuer_quarter, run_id=run_id
    )
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
            required_concepts=_required_concepts(config),
        )
    )
    pdf_obs = extract_consolidated_pl(
        results_pdf, spec=_pdf_parse_spec(config), retrieved_at=config.quarter.knowledge_cutoff
    )
    pdf_by_concept = {obs.concept_qname: obs for obs in pdf_obs}
    log.info("sources_parsed", xbrl_observations=len(xbrl_obs), pdf_observations=len(pdf_obs))

    # 3. Select the consolidated-quarter facts. Required concepts fail closed;
    #    optional concepts (e.g. non-controlling interest) may be absent.
    role_obs: dict[FactRole, Observation] = {}
    concept_obs: dict[str, Observation] = {}
    for role_concept in config.concepts.roles:
        obs = _select_optional(
            xbrl_obs, role_concept.concept_qname, config, required=role_concept.required
        )
        if obs is None:
            continue
        role_obs[role_concept.role] = obs
        concept_obs[role_concept.concept_qname] = obs
    for aux in config.concepts.aux:
        obs = _select_optional(xbrl_obs, aux.concept_qname, config, required=aux.required)
        if obs is not None:
            concept_obs[aux.concept_qname] = obs

    # 4. Cross-foot the accounting identities. An identity that references an
    #    optional concept the filing omits is skipped, not failed.
    cross_foot_results: list[CrossFootResult] = []
    for identity_cfg in config.concepts.identities:
        referenced = {identity_cfg.lhs_concept, *(t.concept_qname for t in identity_cfg.terms)}
        if not referenced <= concept_obs.keys():
            log.info("identity_skipped_optional_absent", identity=identity_cfg.name)
            continue
        identity = Identity(
            name=identity_cfg.name,
            lhs_concept=identity_cfg.lhs_concept,
            terms=tuple(
                SignedTerm(sign=term.sign, concept_qname=term.concept_qname)
                for term in identity_cfg.terms
            ),
        )
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
    for concept in config.concepts.cross_check:
        xbrl_headline = concept_obs.get(concept)
        if xbrl_headline is None:
            continue
        pdf_headline = pdf_by_concept.get(concept)
        if pdf_headline is None:
            raise PipelineError(f"headline concept {concept!r} absent from the results PDF")
        check_result = cross_check(xbrl_headline, pdf_headline)
        cross_check_results.append(check_result)
        if not check_result.matched:
            raise PipelineError(
                f"XBRL↔PDF cross-check failed for {concept!r}: {', '.join(check_result.reasons)}"
            )
        confirmed_concepts.add(concept)
    log.info("cross_check_passed", headline_concepts=len(cross_check_results))

    # 6. Extract and quote-anchor management guidance. Extraction is non-fatal
    #    (no guidance -> empty), but any extracted claim must anchor or fail closed.
    guidance_rules = tuple(
        GuidanceRule(metric=rule.metric, pattern=rule.pattern, horizon=rule.horizon)
        for rule in config.guidance.rules
    )
    guidance_labels = {rule.metric: rule.label for rule in config.guidance.rules}
    guidance_claims = extract_guidance_claims(
        transcript_pdf, rules=guidance_rules, retrieved_at=config.quarter.knowledge_cutoff
    )
    source_document = _source_document(transcript_pdf)
    rendered_guidance: list[RenderedGuidance] = []
    for claim in guidance_claims:
        try:
            quote = resolve_span(transcript_pdf, claim.provenance)
        except GuidanceExtractionError as error:
            raise PipelineError(
                f"guidance span for {claim.metric!r} no longer resolves: {error}"
            ) from error
        # The resolved span must still equal the quote captured at extraction and
        # represent the claim's numeric bounds, so re-pointing provenance or
        # mutating the range (e.g. 3–4% to 8–10%) fails closed.
        if not _guidance_quote_holds(claim, quote):
            raise PipelineError(
                f"guidance quote-anchor failed for {claim.metric!r}: the anchored span no "
                "longer carries the claim captured at extraction"
            )
        # Verify against the claim's OWN asserted range (not a re-read of the same
        # span), so a span that does not actually contain the claim fails closed.
        anchor = verify_quote_anchor(claim, _claim_range_quote(claim), source_document)
        if not anchor.anchored:
            raise PipelineError(
                f"guidance quote-anchor failed for {claim.metric!r}: {anchor.reason}"
            )
        rendered_guidance.append(
            RenderedGuidance(
                metric_label=guidance_labels.get(claim.metric, claim.metric),
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

    # 7. Assemble the render inputs and the planned store writes WITHOUT touching
    #    the store yet: canonical promotion happens only after every gate AND the
    #    render succeed, so a later failure never leaves partial canonical facts.
    planned_writes: list[_PlannedWrite] = []
    rendered_facts: list[RenderedFact] = []
    for role_concept in config.concepts.roles:
        role = role_concept.role
        concept = role_concept.concept_qname
        if role not in role_obs:
            continue
        family = f"{config.quarter.issuer_quarter}:{role.value}"
        xbrl_fact_obs = role_obs[role]
        status = (
            ReconciliationStatus.CROSS_SOURCE_CONFIRMED
            if concept in confirmed_concepts
            else ReconciliationStatus.CROSS_FOOT_PASS
        )
        planned_writes.append(
            _PlannedWrite(
                fact=_build_fact(
                    xbrl_fact_obs,
                    role_family=family,
                    reconciliation_status=status,
                    config=config,
                    run_id=run_id,
                ),
                make_canonical=True,
            )
        )

        sources: list[Provenance] = [xbrl_fact_obs.provenance]
        pdf_confirm = pdf_by_concept.get(concept)
        if pdf_confirm is not None:
            planned_writes.append(
                _PlannedWrite(
                    fact=_build_fact(
                        pdf_confirm,
                        role_family=family,
                        reconciliation_status=ReconciliationStatus.CROSS_SOURCE_CONFIRMED,
                        config=config,
                        run_id=run_id,
                    ),
                    make_canonical=False,
                )
            )
            sources.append(pdf_confirm.provenance)

        rendered_facts.append(
            RenderedFact(
                role=role,
                concept_qname=concept,
                value=xbrl_fact_obs.normalized_value,
                unit=xbrl_fact_obs.normalized_unit,
                reconciliation_status=status,
                sources=tuple(sources),
            )
        )

    # 8. Optional SEC retrospective annual cross-check (never footed against Q1).
    sec_note = _run_sec_cross_check(config)

    # 9. Build the derived calculations and render the sourced 11-section update.
    #    Both must succeed before anything is committed (fail-closed transaction).
    calculations = _build_calculations(role_obs)
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
        cross_check=VerificationOutcome(
            passed_count=sum(1 for check in cross_check_results if check.matched),
            total_count=len(cross_check_results),
        ),
        cross_foot=VerificationOutcome(
            passed_count=sum(1 for identity in cross_foot_results if identity.passed),
            total_count=len(cross_foot_results),
        ),
        sec_cross_check_note=sec_note,
    )
    markdown = render_earnings_update(update)

    # 10. All gates and the render passed — now commit. Canonical promotion is a
    #     separate auditable step; nothing was persisted on a failed run.
    stored_revisions: list[StoredRevision] = []
    for planned in planned_writes:
        revision = store.put(planned.fact)
        if planned.make_canonical:
            revision = store.select_canonical(
                revision.row_id, reason="XBRL context-bound canonical for Q1 evidence"
            )
        stored_revisions.append(revision)
    log.info("facts_stored", revisions=len(stored_revisions))
    log.info("pipeline_complete", markdown_bytes=len(markdown))

    return PipelineResult(
        markdown=markdown,
        stored_revisions=tuple(stored_revisions),
        cross_foot_results=tuple(cross_foot_results),
        cross_check_results=tuple(cross_check_results),
        sec_cross_check_note=sec_note,
    )


def _build_calculations(
    role_obs: dict[FactRole, Observation],
) -> tuple[RenderedCalculation, ...]:
    """Derive sourced calculations, each traced over stored consolidated facts."""
    total_income = role_obs[_TOTAL_INCOME_ROLE].normalized_value
    revenue = role_obs[_REVENUE_ROLE].normalized_value
    pbt = role_obs[_PBT_ROLE].normalized_value
    pat = role_obs[_PAT_ROLE].normalized_value

    if pbt == 0:
        raise PipelineError(
            "cannot derive the effective tax rate: profit before tax is zero (division guard)"
        )

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
