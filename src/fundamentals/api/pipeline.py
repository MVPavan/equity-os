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

import re
import uuid
from collections.abc import Callable, Sequence
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import structlog
from pydantic import BaseModel, ConfigDict

from fundamentals.api.config import FundamentalsConfig
from fundamentals.api.source_admission import (
    AdmittedPipelineInputs,
    AdmittedSource,
    PipelineSourceRefs,
    SourceAdmissionError,
    SourceEvidenceResolver,
    actual_clock,
    admitted_provenance,
    bind_observation,
    build_derived_fact,
    monotonic_clock,
    prepare_pipeline_sources,
    utc_time,
    validate_prepared,
)
from fundamentals.contracts.comparative import ConceptComparative
from fundamentals.contracts.fact import Fact, ReconciliationStatus
from fundamentals.contracts.guidance_claim import GuidanceClaim
from fundamentals.contracts.observation import (
    AccountingFramework,
    Observation,
    PeriodType,
    Scope,
)
from fundamentals.contracts.provenance import Provenance
from fundamentals.extract.guidance_extractor import (
    PERCENT_UNIT,
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
from fundamentals.extract.xbrl_taxonomies import _ALL_TAXONOMIES
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
from fundamentals.output.management_ledger import (
    ManagementLedger,
    load_ledger,
    reconcile_ledger,
    save_ledger,
)
from fundamentals.store.fact_store import CanonicalSelectionError, FactStore, StoredRevision
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


class FactTemporalAudit(BaseModel):
    """Persisted producer history is unproved, even after fresh source admission."""

    model_config = ConfigDict(frozen=True)
    row_id: int
    persisted_knowledge_time: datetime
    persisted_first_seen_time: datetime
    derivation_completed_at: datetime
    selection_action: str
    persisted_basis: str = "unproved_producer"
    historical_certification: bool = False


class PipelineTemporalEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)
    run_started_at: datetime
    cutoff: datetime
    sources: tuple[AdmittedSource, ...]
    xbrl_extracted_at: datetime
    results_extracted_at: datetime
    transcript_extracted_at: datetime
    reconciled_at: datetime
    facts: tuple[FactTemporalAudit, ...]


class PipelineResult(BaseModel):
    """The rendered artifact plus the verification evidence behind it."""

    model_config = ConfigDict(frozen=True)

    update: EarningsUpdate
    markdown: str
    stored_revisions: tuple[StoredRevision, ...]
    cross_foot_results: tuple[CrossFootResult, ...]
    cross_check_results: tuple[CrossCheckResult, ...]
    sec_cross_check_note: str
    temporal_evidence: PipelineTemporalEvidence


def _normalize_entity(
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


def _claim_range_quote(claim: GuidanceClaim) -> str:
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
    numbers = {
        Decimal(value.replace(",", ""))
        for value in re.findall(r"\d[\d,]*(?:\.\d+)?", claim.source_quote)
    }
    return claim.lower_bound in numbers and claim.upper_bound in numbers


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


def _reconcile_current_guidance(
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


def run_pipeline(
    *,
    config: FundamentalsConfig,
    config_path: Path | None = None,
    xbrl_input: XbrlInput,
    results_pdf_path: str,
    results_pdf_sha256: str,
    transcript_pdf_path: str,
    transcript_pdf_sha256: str,
    store: FactStore,
    source_refs: PipelineSourceRefs | None = None,
    evidence_resolver: SourceEvidenceResolver | None = None,
    clock: Callable[[], datetime] | None = None,
    admitted_inputs: AdmittedPipelineInputs | None = None,
) -> PipelineResult:
    """Run the full Q1 FY25 increment end to end, failing closed on any gap."""
    if (
        xbrl_input.source_id != config.xbrl.source_id
        or results_pdf_sha256 != config.results_pdf.sha256
        or transcript_pdf_sha256 != config.transcript_pdf.sha256
    ):
        raise SourceAdmissionError("source identity/config digest mismatch")
    if admitted_inputs is not None:
        if source_refs is not None or evidence_resolver is not None or clock is not None:
            raise SourceAdmissionError("prepared inputs cannot be combined with references/clock")
        validate_prepared(
            admitted_inputs,
            cutoff=config.quarter.knowledge_cutoff,
            source_ids=(
                xbrl_input.source_id,
                config.results_pdf.source_id,
                config.transcript_pdf.source_id,
            ),
            hashes=(xbrl_input.file_sha256, results_pdf_sha256, transcript_pdf_sha256),
            xbrl_bytes=xbrl_input.xml_bytes,
        )
        return _run_admitted(
            config=config, config_path=config_path, store=store, prepared=admitted_inputs
        )
    tick = clock or actual_clock
    with prepare_pipeline_sources(
        xbrl_bytes=xbrl_input.xml_bytes,
        xbrl_source_id=xbrl_input.source_id,
        xbrl_sha256=xbrl_input.file_sha256,
        results_pdf_path=results_pdf_path,
        results_pdf_sha256=results_pdf_sha256,
        results_source_id=config.results_pdf.source_id,
        transcript_pdf_path=transcript_pdf_path,
        transcript_pdf_sha256=transcript_pdf_sha256,
        transcript_source_id=config.transcript_pdf.source_id,
        cutoff=config.quarter.knowledge_cutoff,
        run_started_at=utc_time(tick()),
        source_refs=source_refs,
        evidence_resolver=evidence_resolver,
        clock=tick,
    ) as prepared:
        return _run_admitted(config=config, config_path=config_path, store=store, prepared=prepared)


def _run_admitted(
    *,
    config: FundamentalsConfig,
    config_path: Path | None,
    store: FactStore,
    prepared: AdmittedPipelineInputs,
) -> PipelineResult:
    completed = monotonic_clock(prepared)

    run_id = uuid.uuid4().hex
    log = _LOGGER.bind(
        issuer=config.issuer.nse_symbol, quarter=config.quarter.issuer_quarter, run_id=run_id
    )
    log.info("pipeline_start", xbrl_mode=config.xbrl.mode.value)

    # 1. Load hash-verified held PDFs.
    results_pdf = load_pdf(
        source_id=config.results_pdf.source_id,
        path=prepared._results_path,
        expected_sha256=prepared.results_pdf.source_sha256,
    )
    transcript_pdf = load_pdf(
        source_id=config.transcript_pdf.source_id,
        path=prepared._transcript_path,
        expected_sha256=prepared.transcript_pdf.source_sha256,
    )
    log.info(
        "pdfs_loaded",
        results_pages=results_pdf.page_count,
        transcript_pages=transcript_pdf.page_count,
    )

    # 2. Parse both first-party sources into context-bound Observations.
    xbrl_obs = tuple(
        _normalize_entity(
            obs,
            config.xbrl.entity_scheme_aliases,
            config.xbrl.entity_id_aliases,
            config.issuer.entity_scheme,
        )
        for obs in parse_observations(
            prepared.xbrl_bytes,
            source_id=prepared.xbrl.source_id,
            file_sha256=prepared.xbrl.source_sha256,
            retrieved_at=prepared.xbrl.acquired_at,
            taxonomies=_ALL_TAXONOMIES,
            required_concepts=_required_concepts(config),
        )
    )
    xbrl_extracted_at = completed()
    pdf_obs = extract_consolidated_pl(
        results_pdf, spec=_pdf_parse_spec(config), retrieved_at=prepared.results_pdf.acquired_at
    )
    results_extracted_at = completed()
    xbrl_obs = tuple(bind_observation(obs, prepared.xbrl) for obs in xbrl_obs)
    pdf_obs = [bind_observation(obs, prepared.results_pdf) for obs in pdf_obs]
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
        GuidanceRule(metric=rule.metric, pattern=rule.pattern, horizon=rule.horizon, unit=rule.unit)
        for rule in config.guidance.rules
    )
    guidance_labels = {rule.metric: rule.label for rule in config.guidance.rules}
    guidance_claims = extract_guidance_claims(
        transcript_pdf, rules=guidance_rules, retrieved_at=prepared.transcript_pdf.acquired_at
    )
    transcript_extracted_at = completed()
    guidance_claims = [
        claim.model_copy(
            update={
                "provenance": admitted_provenance(claim.provenance, prepared.transcript_pdf),
            }
        )
        for claim in guidance_claims
    ]
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
                metric=claim.metric,
                metric_label=guidance_labels.get(claim.metric, claim.metric),
                lower_bound=claim.lower_bound,
                upper_bound=claim.upper_bound,
                unit=claim.unit,
                constant_currency=claim.constant_currency,
                horizon=claim.horizon,
                quote=quote,
                source=claim.provenance,
            )
        )
    log.info("guidance_anchored", claims=len(rendered_guidance))

    ledger_path = (
        config.ledger_path_resolved(config_path)
        if config_path is not None
        else Path(config.ledger_path)
        if config.ledger_path is not None
        else None
    )
    ledger = (
        _reconcile_current_guidance(
            load_ledger(
                ledger_path,
                issuer_quarter=config.quarter.issuer_quarter,
                symbol=config.issuer.nse_symbol,
            ),
            symbol=config.issuer.nse_symbol,
            issuer_quarter=config.quarter.issuer_quarter,
            claims=guidance_claims,
            cutoff=prepared.cutoff,
            derivation_completed_at=transcript_extracted_at,
        )
        if ledger_path is not None
        else None
    )

    # 7. Assemble the render inputs and the planned store writes WITHOUT touching
    #    the store yet: canonical promotion happens only after every gate AND the
    #    render succeed, so a later failure never leaves partial canonical facts.
    reconciled_at = completed()
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
                fact=build_derived_fact(
                    xbrl_fact_obs,
                    role_family=family,
                    reconciliation_status=status,
                    config=config,
                    run_id=run_id,
                    completed_at=reconciled_at,
                ),
                make_canonical=True,
            )
        )

        sources: list[Provenance] = [xbrl_fact_obs.provenance]
        pdf_confirm = pdf_by_concept.get(concept)
        if concept in config.concepts.cross_check and pdf_confirm is not None:
            planned_writes.append(
                _PlannedWrite(
                    fact=build_derived_fact(
                        pdf_confirm,
                        role_family=family,
                        reconciliation_status=ReconciliationStatus.CROSS_SOURCE_CONFIRMED,
                        config=config,
                        run_id=run_id,
                        completed_at=reconciled_at,
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

    comparatives: tuple[ConceptComparative, ...] = ()
    if config.comparators is not None:
        if config_path is None:
            raise PipelineError("comparator config requires the run config path")
        from fundamentals.api.run_comparatives import collect_run_comparatives

        comparatives = collect_run_comparatives(
            config,
            config_path=config_path,
            current={fact.concept_qname: role_obs[fact.role] for fact in rendered_facts},
            current_sources={fact.concept_qname: fact.sources for fact in rendered_facts},
        )

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
        comparatives=comparatives,
        comparatives_attempted=config.comparators is not None,
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
        ledger=ledger,
    )
    markdown = render_earnings_update(update)

    # 10. All gates and the render passed — now commit. Canonical promotion is a
    #     separate auditable step; nothing was persisted on a failed run.
    audits: list[FactTemporalAudit] = []
    stored_revisions: list[StoredRevision] = []
    decision_times = [completed() if planned.make_canonical else None for planned in planned_writes]
    for planned, decision_time in zip(planned_writes, decision_times, strict=True):
        revision = store.put(planned.fact)
        action = "not_selected"
        if planned.make_canonical:
            assert decision_time is not None
            history = store.get_selection_history(revision.content_identity)
            if history and decision_time <= history[-1].selected_at:
                raise CanonicalSelectionError("selection time must strictly follow predecessor")
            current = store.get_canonical(revision.content_identity, cutoff=decision_time)
            if current is not None and current.row_id == revision.row_id:
                revision = current
                action = "unchanged"
            else:
                revision = store.select_canonical(
                    revision.row_id,
                    reason="XBRL context-bound canonical for Q1 evidence",
                    selected_at=decision_time,
                    expected_selection_id=history[-1].selection_id if history else 0,
                )
                action = "selected"
        audits.append(
            FactTemporalAudit(
                row_id=revision.row_id,
                persisted_knowledge_time=revision.fact.knowledge_time,
                persisted_first_seen_time=revision.fact.first_seen_time,
                derivation_completed_at=reconciled_at,
                selection_action=action,
            )
        )
        stored_revisions.append(revision)
    if ledger_path is not None and ledger is not None:
        save_ledger(ledger, ledger_path)
    log.info("facts_stored", revisions=len(stored_revisions))
    log.info("pipeline_complete", markdown_bytes=len(markdown))

    return PipelineResult(
        update=update,
        markdown=markdown,
        stored_revisions=tuple(stored_revisions),
        cross_foot_results=tuple(cross_foot_results),
        cross_check_results=tuple(cross_check_results),
        sec_cross_check_note=sec_note,
        temporal_evidence=PipelineTemporalEvidence(
            run_started_at=prepared.run_started_at,
            cutoff=prepared.cutoff,
            sources=(prepared.xbrl, prepared.results_pdf, prepared.transcript_pdf),
            xbrl_extracted_at=xbrl_extracted_at,
            results_extracted_at=results_extracted_at,
            transcript_extracted_at=transcript_extracted_at,
            reconciled_at=reconciled_at,
            facts=tuple(audits),
        ),
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
