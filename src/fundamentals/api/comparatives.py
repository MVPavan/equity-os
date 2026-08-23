"""Fetch prior NSE filings and calculate sourced QoQ/YoY material-fact changes."""

from __future__ import annotations

import hashlib
from datetime import date, timedelta
from decimal import Context, Decimal, DecimalException, localcontext
from pathlib import Path

from pydantic import ValidationError

from fundamentals.api.watchlist_config import StockConfig
from fundamentals.contracts.comparative import (
    PERCENT_CONTEXT_PRECISION,
    ComparativeChange,
    ComparatorKind,
    ConceptComparative,
)
from fundamentals.contracts.observation import Observation, PeriodType, Scope
from fundamentals.extract.xbrl_parser import (
    FactSelectionError,
    XbrlParseError,
    parse_observations,
    select_observation,
)
from fundamentals.extract.xbrl_taxonomies import _ALL_TAXONOMIES
from fundamentals.ingest.comparator_cache import (
    comparator_period_dir,
    quarantine_rejected_comparator,
)
from fundamentals.ingest.xbrl_identity import validate_nse_entity_identities
from fundamentals.ingest.xbrl_source import (
    CONSOLIDATED_SOURCE_ID,
    NseXbrlSource,
    XbrlFetchError,
    XbrlHardBlockError,
)
from fundamentals.reconcile.agreement import AgreementResult
from fundamentals.reconcile.fact_view import (
    canonicalise,
    derived_concept_map,
    material_concepts,
    role_agreement,
    winning_anchors,
)
from fundamentals.reconcile.report import CollectedSource, SourceStatus, StockReport
from fundamentals.verify.comparison_key import ComparisonKey

REASON_NSE_NOT_SELECTED = "NSE comparator source was not selected"
REASON_NSE_CURRENT_UNAVAILABLE = "current NSE source is {status}: {reason}"
REASON_NO_CURRENT = "no retained source-verified current value"
REASON_PRIOR_ZERO = "prior value is zero"
REASON_PERCENT_RANGE = "percent calculation exceeded safe range"
REASON_NO_FIXTURE = "no {kind} NSE comparator fixture configured"
REASON_SELECTION_FAILED = "comparator selection failed: {error}"
REASON_INCOMPATIBLE = "comparator key incompatible: {reasons}"


def _validate_entities(observations: tuple[Observation, ...], stock: StockConfig) -> None:
    """Reject observations outside the shared NSE scheme and issuer-id policy."""
    accepted = {
        stock.identifiers.nse_symbol.strip().upper(),
        *(alias.strip().upper() for alias in stock.identifiers.accepted_entity_ids),
    }
    validate_nse_entity_identities(
        {(item.entity_scheme, item.entity_id) for item in observations}, accepted
    )


def _same_day_previous_year(value: date) -> date:
    """Shift a date back one year, clamping leap day to February 28."""
    try:
        return value.replace(year=value.year - 1)
    except ValueError:
        return value.replace(year=value.year - 1, day=28)


def derive_comparator_periods(
    period_start: date, period_end: date
) -> dict[ComparatorKind, tuple[date, date]]:
    """Derive the previous calendar quarter and same quarter one year earlier."""
    previous_end = period_start - timedelta(days=1)
    previous_start_month = ((previous_end.month - 1) // 3) * 3 + 1
    previous_start = date(previous_end.year, previous_start_month, 1)
    return {
        ComparatorKind.QOQ: (previous_start, previous_end),
        ComparatorKind.YOY: (
            _same_day_previous_year(period_start),
            _same_day_previous_year(period_end),
        ),
    }


def _fixture_path(stock: StockConfig, kind: ComparatorKind) -> str | None:
    """Return the configured prior-filing fixture for one comparator kind."""
    if kind is ComparatorKind.QOQ:
        return stock.fixtures.nse_qoq
    return stock.fixtures.nse_yoy


def _fixture_unavailable_reason(stock: StockConfig, kind: ComparatorKind) -> str | None:
    """Return a cached-selection failure reason for one comparator kind."""
    if kind is ComparatorKind.QOQ:
        return stock.fixtures.nse_qoq_unavailable_reason
    return stock.fixtures.nse_yoy_unavailable_reason


def _load_fixture(
    stock: StockConfig,
    kind: ComparatorKind,
    repo_root: Path,
) -> tuple[tuple[Observation, ...] | None, str | None]:
    """Parse one committed comparator fixture, returning an explicit failure reason."""
    fixture = _fixture_path(stock, kind)
    if fixture is None:
        return None, _fixture_unavailable_reason(stock, kind) or REASON_NO_FIXTURE.format(
            kind=kind.value
        )
    fixture_path = repo_root / fixture
    xml: bytes | None = None
    try:
        xml = fixture_path.read_bytes()
        observations = parse_observations(
            xml,
            source_id=CONSOLIDATED_SOURCE_ID,
            file_sha256=hashlib.sha256(xml).hexdigest(),
            retrieved_at=stock.quarter.knowledge_cutoff,
            taxonomies=_ALL_TAXONOMIES,
        )
        _validate_entities(observations, stock)
        return observations, None
    except (OSError, XbrlParseError, ValidationError, ValueError, DecimalException) as error:
        if xml is not None:
            quarantine_rejected_comparator(
                fixture_path,
                repo_root=repo_root,
                symbol=stock.symbol,
                xml=xml,
                reason=str(error),
            )
        return None, str(error)


def _load_live(
    stock: StockConfig,
    kind: ComparatorKind,
    period_start: date,
    period_end: date,
    repo_root: Path,
) -> tuple[tuple[Observation, ...] | None, str | None]:
    """Fetch and parse one prior NSE filing, returning an explicit failure reason."""
    download_folder = comparator_period_dir(
        repo_root,
        stock.symbol,
        kind,
        period_start,
        period_end,
    )
    source = NseXbrlSource(
        download_folder,
        symbol=stock.identifiers.nse_symbol,
        accepted_entity_ids=stock.identifiers.accepted_entity_ids,
    )
    retrieval_path: Path | None = None
    xml: bytes | None = None
    try:
        retrieval = source.fetch_consolidated_quarter(
            from_date=period_start,
            to_date=period_end,
        )
        retrieval_path = retrieval.local_path
        xml = retrieval_path.read_bytes()
        observations = parse_observations(
            xml,
            source_id=retrieval.source_id,
            file_sha256=retrieval.file_sha256,
            retrieved_at=retrieval.retrieved_at,
            taxonomies=_ALL_TAXONOMIES,
        )
        _validate_entities(observations, stock)
        return observations, None
    except XbrlHardBlockError:
        raise
    except (
        OSError,
        XbrlFetchError,
        XbrlParseError,
        ValidationError,
        ValueError,
        DecimalException,
    ) as error:
        if retrieval_path is not None and xml is not None:
            quarantine_rejected_comparator(
                retrieval_path,
                repo_root=repo_root,
                symbol=stock.symbol,
                xml=xml,
                reason=str(error),
            )
        return None, str(error)


def _unavailable(
    kind: ComparatorKind,
    period_start: date,
    period_end: date,
    reason: str,
) -> ComparativeChange:
    """Build an explicitly unavailable comparator result."""
    return ComparativeChange(
        kind=kind,
        period_start=period_start,
        period_end=period_end,
        unavailable_reason=reason,
    )


def _calculate(
    *,
    kind: ComparatorKind,
    period_start: date,
    period_end: date,
    current_value: Decimal,
    prior: Observation,
) -> ComparativeChange:
    """Calculate Decimal absolute and percent changes over two sourced endpoints."""
    delta = current_value - prior.normalized_value
    absolute_trace = f"{current_value} - {prior.normalized_value}"
    if prior.normalized_value == 0:
        return ComparativeChange(
            kind=kind,
            period_start=period_start,
            period_end=period_end,
            prior_value=prior.normalized_value,
            absolute_change=delta,
            absolute_trace=absolute_trace,
            prior_source=prior.provenance,
            percent_unavailable_reason=REASON_PRIOR_ZERO,
        )
    try:
        with localcontext(Context(prec=PERCENT_CONTEXT_PRECISION)):
            percent = delta / prior.normalized_value * Decimal(100)
    except DecimalException:
        return ComparativeChange(
            kind=kind,
            period_start=period_start,
            period_end=period_end,
            prior_value=prior.normalized_value,
            absolute_change=delta,
            absolute_trace=absolute_trace,
            prior_source=prior.provenance,
            percent_unavailable_reason=REASON_PERCENT_RANGE,
        )
    return ComparativeChange(
        kind=kind,
        period_start=period_start,
        period_end=period_end,
        prior_value=prior.normalized_value,
        absolute_change=delta,
        percent_change=percent,
        absolute_trace=absolute_trace,
        percent_trace=(
            f"({current_value} - {prior.normalized_value}) / {prior.normalized_value} * 100"
        ),
        prior_source=prior.provenance,
    )


def _one_change(
    *,
    kind: ComparatorKind,
    period_start: date,
    period_end: date,
    current: AgreementResult,
    observations: tuple[Observation, ...] | None,
    filing_reason: str | None,
    stock: StockConfig,
) -> ComparativeChange:
    """Select, key-check, and calculate one concept's prior-filing change."""
    if observations is None:
        return _unavailable(kind, period_start, period_end, filing_reason or "filing unavailable")
    try:
        prior = select_observation(
            observations,
            concept_qname=current.comparison_key.concept_qname,
            scope=Scope.CONSOLIDATED,
            period_type=PeriodType.DURATION,
            period_start=period_start,
            period_end=period_end,
        )
    except FactSelectionError as error:
        return _unavailable(
            kind,
            period_start,
            period_end,
            REASON_SELECTION_FAILED.format(error=error),
        )

    canonical_prior = canonicalise(prior, stock.symbol)
    compatibility = current.comparison_key.comparative_compatibility(
        ComparisonKey.from_observation(canonical_prior)
    )
    if not compatibility.comparable:
        return _unavailable(
            kind,
            period_start,
            period_end,
            REASON_INCOMPATIBLE.format(reasons="; ".join(compatibility.reasons)),
        )
    assert current.agreed_value is not None
    return _calculate(
        kind=kind,
        period_start=period_start,
        period_end=period_end,
        current_value=current.agreed_value,
        prior=canonical_prior,
    )


def collect_comparatives(
    report: StockReport,
    stock: StockConfig,
    *,
    live: bool,
    nse_source: CollectedSource | None,
    repo_root: Path,
) -> tuple[ConceptComparative, ...]:
    """Collect prior filings once and calculate every configured material concept."""
    periods = derive_comparator_periods(stock.quarter.period_start, stock.quarter.period_end)
    derived_map = derived_concept_map(stock.concepts.roles)
    filings: dict[ComparatorKind, tuple[tuple[Observation, ...] | None, str | None]] = {}
    hard_block_reason: str | None = None
    for kind, (period_start, period_end) in periods.items():
        if hard_block_reason is not None:
            filings[kind] = (None, hard_block_reason)
        elif nse_source is None:
            filings[kind] = (None, REASON_NSE_NOT_SELECTED)
        elif live and nse_source.status is not SourceStatus.OK:
            filings[kind] = (
                None,
                REASON_NSE_CURRENT_UNAVAILABLE.format(
                    status=nse_source.status.value,
                    reason=nse_source.note or "no usable current filing",
                ),
            )
        elif live:
            try:
                filings[kind] = _load_live(stock, kind, period_start, period_end, repo_root)
            except XbrlHardBlockError as error:
                hard_block_reason = str(error)
                filings[kind] = (None, hard_block_reason)
        else:
            filings[kind] = _load_fixture(stock, kind, repo_root)

    comparatives: list[ConceptComparative] = []
    for concept in material_concepts(stock.concepts.roles, stock.concepts.cross_check):
        current = role_agreement(
            concept,
            report.sources,
            symbol=stock.symbol,
            period_start=stock.quarter.period_start,
            period_end=stock.quarter.period_end,
            derived_map=derived_map,
        )
        if current is None or current.agreed_value is None:
            qoq_start, qoq_end = periods[ComparatorKind.QOQ]
            yoy_start, yoy_end = periods[ComparatorKind.YOY]
            qoq_reason = filings[ComparatorKind.QOQ][1] or REASON_NO_CURRENT
            yoy_reason = filings[ComparatorKind.YOY][1] or REASON_NO_CURRENT
            comparatives.append(
                ConceptComparative(
                    concept_qname=concept,
                    current_unavailable_reason=REASON_NO_CURRENT,
                    qoq=_unavailable(ComparatorKind.QOQ, qoq_start, qoq_end, qoq_reason),
                    yoy=_unavailable(ComparatorKind.YOY, yoy_start, yoy_end, yoy_reason),
                )
            )
            continue

        current_sources = winning_anchors(current)
        changes: dict[ComparatorKind, ComparativeChange] = {}
        for kind, (period_start, period_end) in periods.items():
            observations, reason = filings[kind]
            changes[kind] = _one_change(
                kind=kind,
                period_start=period_start,
                period_end=period_end,
                current=current,
                observations=observations,
                filing_reason=reason,
                stock=stock,
            )
        comparatives.append(
            ConceptComparative(
                concept_qname=concept,
                current_value=current.agreed_value,
                unit=current.normalized_unit,
                current_sources=current_sources,
                qoq=changes[ComparatorKind.QOQ],
                yoy=changes[ComparatorKind.YOY],
            )
        )
    return tuple(comparatives)
