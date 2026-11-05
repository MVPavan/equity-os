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
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path

import structlog
from pydantic import BaseModel, ConfigDict

from equity_os.contracts.measurement.fact import Fact, ReconciliationStatus
from equity_os.contracts.measurement.guidance_claim import GuidanceClaim
from equity_os.contracts.measurement.observation import (
    Observation,
)
from equity_os.contracts.measurement.provenance import Provenance
from equity_os.contracts.verification.comparative import RUN_PERCENT_PLACES, ConceptComparative
from equity_os.extraction.guidance.guidance_extractor import (
    GuidanceExtractionError,
    GuidanceRule,
    extract_guidance_claims,
    resolve_span,
)
from equity_os.extraction.results_pdf.pdf_number_parser import extract_consolidated_pl
from equity_os.extraction.results_pdf.pdf_source import load_pdf
from equity_os.extraction.xbrl.xbrl_parser import (
    parse_observations,
)
from equity_os.extraction.xbrl.xbrl_taxonomies import _ALL_TAXONOMIES
from equity_os.interface.commands.sourcing.source_admission import (
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
from equity_os.interface.entry.config import FundamentalsConfig
from equity_os.interface.workflows.pipeline_steps import (
    PipelineError as PipelineError,
)
from equity_os.interface.workflows.pipeline_steps import (
    build_calculations,
    claim_range_quote,
    normalize_entity,
    pdf_parse_spec,
    required_concepts,
    run_sec_cross_check,
    select_optional,
)
from equity_os.publication.checking.quote_anchor import (
    guidance_quote_holds,
    source_document,
    verify_quote_anchor,
)
from equity_os.publication.drafting.earnings_update import (
    EarningsUpdate,
    FactRole,
    RenderedFact,
    RenderedGuidance,
    VerificationOutcome,
    render_earnings_update,
)
from equity_os.storage.facts.fact_store import (
    CanonicalSelectionError,
    FactStoreLike,
    StoredRevision,
)
from equity_os.verification.comparison.cross_check import CrossCheckResult, cross_check
from equity_os.verification.comparison.crossfoot import (
    CrossFootResult,
    Identity,
    SignedTerm,
    check_identity,
)

_LOGGER = structlog.get_logger("fundamentals.pipeline")
BeforeCommit = Callable[[EarningsUpdate, tuple[GuidanceClaim, ...]], object]


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
    guidance_claims: tuple[GuidanceClaim, ...] = ()
    draft_version_id: int | None = None


def run_pipeline(
    *,
    config: FundamentalsConfig,
    config_path: Path | None = None,
    xbrl_input: XbrlInput,
    results_pdf_path: str,
    results_pdf_sha256: str,
    transcript_pdf_path: str,
    transcript_pdf_sha256: str,
    store: FactStoreLike,
    source_refs: PipelineSourceRefs | None = None,
    evidence_resolver: SourceEvidenceResolver | None = None,
    clock: Callable[[], datetime] | None = None,
    admitted_inputs: AdmittedPipelineInputs | None = None,
    comparators_acquired_at: Mapping[str, datetime] | None = None,
    before_commit: BeforeCommit | None = None,
    skip_roles: frozenset[FactRole] = frozenset(),
) -> PipelineResult:
    """Run the full Q1 FY25 increment end to end, failing closed on any gap;
    ``comparators_acquired_at`` is each registered comparator XBRL's acquisition time;
    ``before_commit`` sees the rendered update and guidance claims before any fact is stored
    and may refuse; ``skip_roles`` are rendered but not stored or selected."""
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
            config=config,
            config_path=config_path,
            store=store,
            prepared=admitted_inputs,
            comparators_acquired_at=comparators_acquired_at,
            before_commit=before_commit,
            skip_roles=skip_roles,
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
        return _run_admitted(
            config=config,
            config_path=config_path,
            store=store,
            prepared=prepared,
            comparators_acquired_at=comparators_acquired_at,
            before_commit=before_commit,
            skip_roles=skip_roles,
        )


def _run_admitted(
    *,
    config: FundamentalsConfig,
    config_path: Path | None,
    store: FactStoreLike,
    prepared: AdmittedPipelineInputs,
    comparators_acquired_at: Mapping[str, datetime] | None,
    before_commit: BeforeCommit | None,
    skip_roles: frozenset[FactRole],
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
        normalize_entity(
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
            required_concepts=required_concepts(config),
        )
    )
    xbrl_extracted_at = completed()
    pdf_obs = extract_consolidated_pl(
        results_pdf, spec=pdf_parse_spec(config), retrieved_at=prepared.results_pdf.acquired_at
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
        obs = select_optional(
            xbrl_obs, role_concept.concept_qname, config, required=role_concept.required
        )
        if obs is None:
            continue
        role_obs[role_concept.role] = obs
        concept_obs[role_concept.concept_qname] = obs
    for aux in config.report_aux():
        obs = select_optional(xbrl_obs, aux.concept_qname, config, required=aux.required)
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
    transcript_document = source_document(transcript_pdf)
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
        if not guidance_quote_holds(claim, quote):
            raise PipelineError(
                f"guidance quote-anchor failed for {claim.metric!r}: the anchored span no "
                "longer carries the claim captured at extraction"
            )
        # Verify against the claim's OWN asserted range (not a re-read of the same
        # span), so a span that does not actually contain the claim fails closed.
        anchor = verify_quote_anchor(claim, claim_range_quote(claim), transcript_document)
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
        # A skipped role (carried by a rework) is rendered, never stored.
        writes = planned_writes if role not in skip_roles else []
        writes.append(
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
            writes.append(
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
    sec_note = run_sec_cross_check(config)

    comparatives: tuple[ConceptComparative, ...] = ()
    if config.comparators is not None:
        if config_path is None:
            raise PipelineError("comparator config requires the run config path")
        from equity_os.interface.workflows.run_comparatives import collect_run_comparatives

        comparatives = collect_run_comparatives(
            config,
            config_path=config_path,
            current={fact.concept_qname: role_obs[fact.role] for fact in rendered_facts},
            current_sources={fact.concept_qname: fact.sources for fact in rendered_facts},
            acquired_at=comparators_acquired_at or {},
        )

    # 9. Build the derived calculations and render the sourced 11-section update.
    #    Both must succeed before anything is committed (fail-closed transaction).
    calculations = build_calculations(role_obs, concept_obs, config)
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
        retrospective=prepared.retrospective,
        source_cutoff=prepared.cutoff,
        percent_places=RUN_PERCENT_PLACES,
    )
    markdown = render_earnings_update(update)
    if before_commit is not None:
        before_commit(update, tuple(guidance_claims))

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
    update = update.model_copy(update={"derivation_cutoff": completed()})
    markdown = render_earnings_update(update)
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
        guidance_claims=tuple(guidance_claims),
    )
