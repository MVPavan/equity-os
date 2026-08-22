"""Multi-stock validation goal runner.

Executes ``docs/goals/fundamentals-multistock-validation-goal.md``: for each
watchlist stock it resolves the source identifiers, pulls every source that
carries the stock, reconciles each material P&L fact across those sources with
the frozen agreement classifier, writes the per-stock gold reference file, and
evaluates the goal's Definition of Done — producing a per-stock report and a
Wave-1 roll-up.

Design invariants:

* **Reuse, never re-implement.** Fetch/parse is delegated to the ingest adapters
  and :mod:`fundamentals.extract.xbrl_parser`; per-fact agreement to
  :func:`fundamentals.reconcile.agreement.classify_agreement`; the gold file to
  :mod:`fundamentals.reconcile.gold_file`; cross-footing to
  :mod:`fundamentals.verify.crossfoot`. This module is orchestration only.
* **Fail closed, never loop forever.** A stock with no reachable first-party
  source, a missing credential, or a parse defect is recorded ``BLOCKED`` and
  surfaced once — the loop never retries indefinitely and no un-sourced number
  enters a report.
* **Derived aggregators cross-check only.** Screener and Tijori observations are
  re-expressed onto the first-party comparison column so they can *corroborate*
  an agreed value, but the classifier (by ``source_id``) never counts them toward
  the two independent first-party sources a value needs to be confirmed.
* **Cross-host entity canonicalisation.** NSE (symbol), BSE (scrip) and derived
  (slug) name the same issuer under different entity schemes; every observation
  is canonicalised to ``(nse-symbol, <symbol>)`` before comparison so the same
  issuer's values land in one comparison column.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict

from fundamentals.api.config import (
    ConceptsConfig,
    IdentityConfig,
    PdfParseConfig,
)
from fundamentals.api.watchlist_config import StockConfig, StockQuarter, WatchlistConfig
from fundamentals.contracts.observation import (
    AccountingFramework,
    Observation,
    PeriodType,
    Scope,
)
from fundamentals.extract.pdf_number_parser import (
    PdfParseSpec,
    extract_consolidated_pl,
)
from fundamentals.extract.xbrl_parser import (
    FactSelectionError,
    XbrlParseError,
    parse_observations,
    select_observation,
)
from fundamentals.ingest.bse_source import (
    BSE_RESULTS_URL_TEMPLATE,
    BSE_TAXONOMIES,
    SUMMARY_SOURCE_ID,
    BseFetchError,
    BseSource,
    _period_bounds,
)
from fundamentals.ingest.bse_source import (
    SOURCE_ID as BSE_XBRL_SOURCE_ID,
)
from fundamentals.ingest.pdf_source import PdfIntegrityError, load_pdf
from fundamentals.ingest.screener_source import (
    ScreenerFetchError,
    ScreenerSource,
    ScreenerSourceConfig,
    parse_quarterly_pnl,
)
from fundamentals.ingest.tijori_source import (
    TijoriCredentials,
    TijoriError,
    TijoriSource,
    TijoriSourceConfig,
)
from fundamentals.ingest.xbrl_source import (
    CONSOLIDATED_SOURCE_ID,
    NseXbrlSource,
    XbrlFetchError,
)
from fundamentals.output.earnings_update import FactRole
from fundamentals.reconcile.agreement import (
    AgreementResult,
    AgreementStatus,
    SourceClass,
    classify_agreement,
)
from fundamentals.reconcile.gold_file import DEFAULT_GOLD_DIR, write_gold_file
from fundamentals.verify.crossfoot import (
    CrossFootResult,
    Identity,
    SignedTerm,
    check_identity,
)

_LOGGER = structlog.get_logger("fundamentals.goal_runner")

CANONICAL_ENTITY_SCHEME = "nse-symbol"

# Parse both first-party XBRL hosts with the superset of supported taxonomies
# (in-bse-fin + in-capmkt); the parser fails closed if an instance matches none.
_ALL_TAXONOMIES = BSE_TAXONOMIES

# Screener / Tijori derived concepts that map onto a first-party render role, so a
# derived value can corroborate the role's canonical concept.
_DERIVED_ROLE_ALIASES: dict[FactRole, tuple[str, ...]] = {
    FactRole.REVENUE: ("screener:Sales", "tijori:sales"),
    FactRole.PROFIT_FOR_PERIOD: ("screener:NetProfit", "tijori:net_profit"),
    FactRole.BASIC_EPS: ("screener:EPS", "tijori:eps"),
}


class RunMode(StrEnum):
    """Whether sources are fetched live (polite) or read from local fixtures."""

    LIVE = "live"
    FIXTURE = "fixture"


class QuarterMode(StrEnum):
    """How the reviewed quarter is chosen for a run.

    ``PINNED`` uses each stock's configured quarter unchanged. ``LATEST`` asks BSE
    which quarters it currently publishes and retargets every source onto the most
    recent completed quarter they can share — so the first-party summary source
    (which only carries the latest quarters) can reach cross-source AGREE.
    """

    PINNED = "pinned"
    LATEST = "latest"


# resultsSnapshot exposes only the latest quarters BSE publishes; a placeholder
# label is passed purely to read back the available period columns before the
# target quarter is known (LATEST mode). It is never matched as a real column.
_LATEST_PROBE_LABEL = "__latest__"

# A "Mon-YY" BSE column is a quarter (not the fiscal-year column) when its resolved
# span is under this many days; fiscal-year columns span ~365 days.
_MAX_QUARTER_SPAN_DAYS = 100

# BSE column labels are "Mon-YY"; %b-%y yields exactly that in the default C locale.
_BSE_PERIOD_LABEL_FORMAT = "%b-%y"


class SourceKind(StrEnum):
    """The sources the runner can cross-check per stock."""

    NSE = "nse"
    BSE = "bse"
    SCREENER = "screener"
    TIJORI = "tijori"
    PDF = "pdf"
    SEC = "sec"


ALL_SOURCE_KINDS: frozenset[SourceKind] = frozenset(SourceKind)
_FIRST_PARTY_KINDS: frozenset[SourceKind] = frozenset(
    {SourceKind.NSE, SourceKind.BSE, SourceKind.PDF}
)
_XBRL_SELECT_KINDS: frozenset[SourceKind] = frozenset({SourceKind.NSE, SourceKind.BSE})


class SourceStatus(StrEnum):
    """Outcome of pulling one source for one stock."""

    OK = "ok"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class StockOutcome(StrEnum):
    """The per-stock verdict against the goal's Definition of Done."""

    DONE = "done"
    NEEDS_ADJUDICATION = "needs_adjudication"
    BLOCKED = "blocked"


class CollectedSource(BaseModel):
    """One source's pulled observations plus its status and any note."""

    model_config = ConfigDict(frozen=True)

    kind: SourceKind
    source_id: str
    status: SourceStatus
    observations: tuple[Observation, ...] = ()
    note: str = ""


class SourceReading(BaseModel):
    """One source's reported value for a reconciled fact."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    source_class: SourceClass
    value: str
    normalized_unit: str


class FactOutcome(BaseModel):
    """The cross-source reconciliation of one material fact."""

    model_config = ConfigDict(frozen=True)

    concept_qname: str
    status: AgreementStatus
    agreed_value: str | None
    agreed_sources: tuple[str, ...]
    corroborating_sources: tuple[str, ...]
    incompatible_sources: tuple[str, ...]
    first_party_source_count: int
    needs_human_review: bool
    readings: tuple[SourceReading, ...]


class CrossFootOutcome(BaseModel):
    """One evaluated accounting identity's result, projected for the report."""

    model_config = ConfigDict(frozen=True)

    identity: str
    passed: bool
    residual: str
    tolerance: str
    flagged_for_review: bool


class DodEvaluation(BaseModel):
    """The goal's Definition of Done, evaluated per stock."""

    model_config = ConfigDict(frozen=True)

    material_facts_agreed: bool
    cross_foot_holds: bool
    gold_file_written: bool
    no_unsourced_number: bool
    no_missing_material_concepts: bool

    @property
    def met(self) -> bool:
        """Whether every Definition-of-Done clause holds for this stock."""
        return (
            self.material_facts_agreed
            and self.cross_foot_holds
            and self.gold_file_written
            and self.no_unsourced_number
            and self.no_missing_material_concepts
        )


class StockReport(BaseModel):
    """Per-stock validation report: coverage, facts, discrepancies, and verdict."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    name: str
    domain: str
    quarter: str
    outcome: StockOutcome
    sources: tuple[CollectedSource, ...]
    facts: tuple[FactOutcome, ...]
    discrepancies: tuple[FactOutcome, ...]
    missing_material_concepts: tuple[str, ...]
    cross_foot: tuple[CrossFootOutcome, ...]
    gold_file_path: str | None
    dod: DodEvaluation
    blockers: tuple[str, ...]
    identifiers_to_verify: tuple[str, ...]

    @property
    def available_sources(self) -> tuple[str, ...]:
        """Source ids that returned observations for this stock."""
        return tuple(src.source_id for src in self.sources if src.status is SourceStatus.OK)


class WaveReport(BaseModel):
    """Roll-up across a wave: per-stock verdicts and coverage."""

    model_config = ConfigDict(frozen=True)

    wave: str
    quarter_labels: tuple[str, ...]
    stocks: tuple[StockReport, ...]

    @property
    def all_done(self) -> bool:
        """Whether every stock reached DONE (the goal's completion condition)."""
        return bool(self.stocks) and all(s.outcome is StockOutcome.DONE for s in self.stocks)

    @property
    def done_count(self) -> int:
        """Number of stocks that reached DONE."""
        return sum(1 for s in self.stocks if s.outcome is StockOutcome.DONE)

    @property
    def blocked_count(self) -> int:
        """Number of stocks recorded BLOCKED."""
        return sum(1 for s in self.stocks if s.outcome is StockOutcome.BLOCKED)


# --- entity / concept canonicalisation ----------------------------------------


def _role_concept_map(concepts: ConceptsConfig) -> dict[FactRole, str]:
    """Map each configured render role to its canonical concept QName."""
    return {role.role: role.concept_qname for role in concepts.roles}


def _derived_concept_map(concepts: ConceptsConfig) -> dict[str, str]:
    """Build the derived-concept -> canonical-concept map from the role map."""
    role_map = _role_concept_map(concepts)
    mapping: dict[str, str] = {}
    for role, aliases in _DERIVED_ROLE_ALIASES.items():
        canonical = role_map.get(role)
        if canonical is None:
            continue
        for alias in aliases:
            mapping[alias] = canonical
    return mapping


def _canonicalise(
    obs: Observation, symbol: str, *, canonical_concept: str | None = None
) -> Observation:
    """Project an observation onto the canonical cross-host comparison column.

    Every source is re-homed to ``(nse-symbol, <symbol>)`` so the same issuer's
    values compare, and its taxonomy identity is dropped so the column is
    taxonomy-agnostic: the NSE XBRL (which carries a taxonomy) and the BSE
    resultsSnapshot summary (which carries none) then land in one comparison
    column. Semantic drift is still caught by ``concept_qname``, which encodes the
    taxonomy prefix. For a derived observation ``canonical_concept`` also rewrites
    the concept, scope and accounting basis onto the first-party column it
    corroborates; the ``source_id`` is untouched, so the classifier still marks it
    derived and never counts it as first-party.
    """
    updates: dict[str, object] = {
        "entity_scheme": CANONICAL_ENTITY_SCHEME,
        "entity_id": symbol,
        "taxonomy_namespace": None,
        "registry_version": None,
    }
    if canonical_concept is not None:
        updates.update(
            concept_qname=canonical_concept,
            scope=Scope.CONSOLIDATED,
            accounting_basis=AccountingFramework.IND_AS,
        )
    return obs.model_copy(update=updates)


def _select_first_party(
    observations: Sequence[Observation],
    concept: str,
    stock: StockConfig,
) -> Observation | None:
    """Select the segment-free consolidated-quarter observation, or ``None``.

    Reuses :func:`select_observation`; a zero-or-ambiguous match means this source
    does not cleanly carry the concept, so it is skipped for that fact (fail
    closed — never guessed).
    """
    try:
        return select_observation(
            tuple(observations),
            concept_qname=concept,
            scope=Scope.CONSOLIDATED,
            period_type=PeriodType.DURATION,
            period_start=stock.quarter.period_start,
            period_end=stock.quarter.period_end,
        )
    except FactSelectionError:
        return None


def _gather_fact_observations(
    concept: str,
    sources: Sequence[CollectedSource],
    stock: StockConfig,
    derived_map: dict[str, str],
) -> list[Observation]:
    """Collect every source's observation for one canonical concept, canonicalised."""
    gathered: list[Observation] = []
    for src in sources:
        if src.status is not SourceStatus.OK:
            continue
        if src.kind in _XBRL_SELECT_KINDS:
            picked = _select_first_party(src.observations, concept, stock)
            if picked is not None:
                gathered.append(_canonicalise(picked, stock.symbol))
        elif src.kind in _FIRST_PARTY_KINDS:  # PDF: already quarter-bound
            gathered.extend(
                _canonicalise(obs, stock.symbol)
                for obs in src.observations
                if obs.concept_qname == concept
            )
        else:  # derived aggregator (Screener / Tijori)
            gathered.extend(_derived_for_concept(concept, src, stock, derived_map))
    return gathered


def _derived_for_concept(
    concept: str,
    src: CollectedSource,
    stock: StockConfig,
    derived_map: dict[str, str],
) -> list[Observation]:
    """Re-express a derived source's target-quarter observations onto ``concept``."""
    result: list[Observation] = []
    for obs in src.observations:
        if derived_map.get(obs.concept_qname) != concept:
            continue
        if obs.period_type is not PeriodType.DURATION:
            continue
        if obs.period_end != stock.quarter.period_end:
            continue
        result.append(_canonicalise(obs, stock.symbol, canonical_concept=concept))
    return result


# --- reconciliation -----------------------------------------------------------


def _fact_outcome(result: AgreementResult) -> FactOutcome:
    """Project an agreement result into the per-fact report record."""
    return FactOutcome(
        concept_qname=result.comparison_key.concept_qname,
        status=result.status,
        agreed_value=None if result.agreed_value is None else str(result.agreed_value),
        agreed_sources=result.agreed_sources,
        corroborating_sources=result.corroborating_sources,
        incompatible_sources=result.incompatible_sources,
        first_party_source_count=result.first_party_source_count,
        needs_human_review=result.needs_human_review,
        readings=tuple(
            SourceReading(
                source_id=value.source_id,
                source_class=value.source_class,
                value=str(value.normalized_value),
                normalized_unit=value.normalized_unit,
            )
            for value in result.source_values
        ),
    )


def _first_party_concept_obs(
    src: CollectedSource, stock: StockConfig, needed: frozenset[str]
) -> dict[str, Observation]:
    """Select every needed concept from one first-party XBRL source, canonicalised."""
    resolved: dict[str, Observation] = {}
    for concept in needed:
        picked = _select_first_party(src.observations, concept, stock)
        if picked is not None:
            resolved[concept] = _canonicalise(picked, stock.symbol)
    return resolved


def _cross_foot(
    sources: Sequence[CollectedSource], stock: StockConfig, concepts: ConceptsConfig
) -> list[CrossFootResult]:
    """Cross-foot each identity on the first-party source that fully covers it."""
    needed: set[str] = set()
    for identity in concepts.identities:
        needed.add(identity.lhs_concept)
        needed.update(term.concept_qname for term in identity.terms)
    per_source = [
        _first_party_concept_obs(src, stock, frozenset(needed))
        for src in sources
        if src.kind in _XBRL_SELECT_KINDS and src.status is SourceStatus.OK
    ]
    results: list[CrossFootResult] = []
    for identity_cfg in concepts.identities:
        referenced = {identity_cfg.lhs_concept, *(t.concept_qname for t in identity_cfg.terms)}
        covering = next((obs for obs in per_source if referenced <= obs.keys()), None)
        if covering is None:
            continue
        results.append(check_identity(_to_identity(identity_cfg), covering))
    return results


def _to_identity(identity_cfg: IdentityConfig) -> Identity:
    """Adapt a configured identity into the verify-layer identity type."""
    return Identity(
        name=identity_cfg.name,
        lhs_concept=identity_cfg.lhs_concept,
        terms=tuple(
            SignedTerm(sign=term.sign, concept_qname=term.concept_qname)
            for term in identity_cfg.terms
        ),
    )


def reconcile_stock(
    stock: StockConfig,
    sources: Sequence[CollectedSource],
    *,
    out_dir: Path = DEFAULT_GOLD_DIR,
) -> StockReport:
    """Reconcile every material fact across the collected sources and score the DoD.

    Pure of network I/O: it consumes already-pulled observations, so it is the
    deterministic core the tests drive directly. Writes the per-stock gold file
    only when at least one first-party source produced a fact (never an empty
    reference), and evaluates the goal's Definition of Done.
    """
    concepts = stock.concepts
    derived_map = _derived_concept_map(concepts)

    results: list[AgreementResult] = []
    facts: list[FactOutcome] = []
    missing: list[str] = []
    for concept in concepts.cross_check:
        gathered = _gather_fact_observations(concept, sources, stock, derived_map)
        if not gathered:
            missing.append(concept)
            continue
        result = classify_agreement(gathered)
        results.append(result)
        facts.append(_fact_outcome(result))

    cross_foot_results = _cross_foot(sources, stock, concepts)
    cross_foot = tuple(
        CrossFootOutcome(
            identity=r.identity,
            passed=r.passed,
            residual=str(r.residual),
            tolerance=str(r.tolerance),
            flagged_for_review=r.flagged_for_review,
        )
        for r in cross_foot_results
    )

    first_party_reachable = any(
        src.kind in _FIRST_PARTY_KINDS and src.status is SourceStatus.OK and src.observations
        for src in sources
    )
    blockers = tuple(
        f"{src.kind.value}: {src.note}"
        for src in sources
        if src.status is SourceStatus.BLOCKED and src.note
    )

    gold_path: str | None = None
    if results:
        written = write_gold_file(stock.symbol, stock.quarter.label, results, out_dir=out_dir)
        gold_path = str(written)

    dod = _evaluate_dod(facts, cross_foot_results, missing, gold_written=gold_path is not None)
    outcome = _stock_outcome(first_party_reachable, dod, results)
    discrepancies = tuple(fact for fact in facts if fact.needs_human_review)

    _LOGGER.info(
        "stock_reconciled",
        symbol=stock.symbol,
        outcome=outcome.value,
        facts=len(facts),
        discrepancies=len(discrepancies),
        missing=len(missing),
        available_sources=[src.source_id for src in sources if src.status is SourceStatus.OK],
    )
    return StockReport(
        symbol=stock.symbol,
        name=stock.name,
        domain=stock.domain,
        quarter=stock.quarter.label,
        outcome=outcome,
        sources=tuple(sources),
        facts=tuple(facts),
        discrepancies=discrepancies,
        missing_material_concepts=tuple(missing),
        cross_foot=cross_foot,
        gold_file_path=gold_path,
        dod=dod,
        blockers=blockers,
        identifiers_to_verify=stock.identifiers.needs_verification,
    )


def _evaluate_dod(
    facts: Sequence[FactOutcome],
    cross_foot_results: Sequence[CrossFootResult],
    missing: Sequence[str],
    *,
    gold_written: bool,
) -> DodEvaluation:
    """Evaluate every clause of the goal's Definition of Done."""
    material_facts_agreed = bool(facts) and all(
        fact.status is AgreementStatus.AGREE for fact in facts
    )
    cross_foot_holds = all(r.passed and not r.flagged_for_review for r in cross_foot_results)
    # Fail-closed guarantee: a retained value exists only with >=1 first-party source.
    no_unsourced_number = all(
        fact.agreed_value is None or fact.first_party_source_count >= 1 for fact in facts
    )
    return DodEvaluation(
        material_facts_agreed=material_facts_agreed,
        cross_foot_holds=cross_foot_holds,
        gold_file_written=gold_written,
        no_unsourced_number=no_unsourced_number,
        no_missing_material_concepts=not missing,
    )


def _stock_outcome(
    first_party_reachable: bool,
    dod: DodEvaluation,
    results: Sequence[AgreementResult],
) -> StockOutcome:
    """Decide the per-stock verdict, failing closed to BLOCKED / adjudication."""
    if not first_party_reachable or not results:
        return StockOutcome.BLOCKED
    if dod.met:
        return StockOutcome.DONE
    return StockOutcome.NEEDS_ADJUDICATION


# --- source collection (I/O) --------------------------------------------------


def collect_sources(
    stock: StockConfig,
    *,
    mode: RunMode,
    repo_root: Path,
    kinds: frozenset[SourceKind] = ALL_SOURCE_KINDS,
    tijori_credentials: TijoriCredentials | None = None,
) -> list[CollectedSource]:
    """Pull every requested source for one stock, recording status per source.

    Each source is isolated: a derived-source failure or a missing optional
    source is recorded (SKIPPED/BLOCKED) and never aborts the stock. NSE is always
    attempted; SEC is skipped unless the stock is US-listed; Tijori is skipped
    without injected credentials; PDF is skipped without a configured document.
    """
    retrieved_at = stock.quarter.knowledge_cutoff
    collected: list[CollectedSource] = []
    if SourceKind.NSE in kinds:
        collected.append(_collect_nse(stock, mode, repo_root, retrieved_at))
    if SourceKind.BSE in kinds:
        collected.append(_collect_bse(stock, mode, repo_root, retrieved_at))
    if SourceKind.SCREENER in kinds:
        collected.append(_collect_screener(stock, mode, repo_root, retrieved_at))
    if SourceKind.TIJORI in kinds:
        collected.append(_collect_tijori(stock, mode, repo_root, tijori_credentials))
    if SourceKind.PDF in kinds:
        collected.append(_collect_pdf(stock, repo_root, retrieved_at))
    if SourceKind.SEC in kinds:
        collected.append(_collect_sec(stock))
    return collected


def _skip(kind: SourceKind, source_id: str, note: str) -> CollectedSource:
    """Build a SKIPPED source record."""
    return CollectedSource(kind=kind, source_id=source_id, status=SourceStatus.SKIPPED, note=note)


def _blocked(kind: SourceKind, source_id: str, note: str) -> CollectedSource:
    """Build a BLOCKED source record (surfaced once, never retried)."""
    return CollectedSource(kind=kind, source_id=source_id, status=SourceStatus.BLOCKED, note=note)


def _ok(kind: SourceKind, source_id: str, observations: Sequence[Observation]) -> CollectedSource:
    """Build an OK source record from pulled observations."""
    return CollectedSource(
        kind=kind, source_id=source_id, status=SourceStatus.OK, observations=tuple(observations)
    )


def _collect_nse(
    stock: StockConfig, mode: RunMode, repo_root: Path, retrieved_at: datetime
) -> CollectedSource:
    """Pull the NSE Ind AS XBRL (always attempted; first-party primary)."""
    source_id = CONSOLIDATED_SOURCE_ID
    try:
        if mode is RunMode.FIXTURE:
            if stock.fixtures.nse is None:
                return _skip(SourceKind.NSE, source_id, "no NSE fixture configured")
            xml = (repo_root / stock.fixtures.nse).read_bytes()
            observations = parse_observations(
                xml,
                source_id=source_id,
                file_sha256=_sha256(xml),
                retrieved_at=retrieved_at,
                taxonomies=_ALL_TAXONOMIES,
            )
        else:
            observations = _fetch_nse_live(stock, repo_root)
    except (XbrlFetchError, XbrlParseError, OSError) as error:
        return _blocked(SourceKind.NSE, source_id, str(error))
    return _ok(SourceKind.NSE, source_id, observations)


def _fetch_nse_live(stock: StockConfig, repo_root: Path) -> tuple[Observation, ...]:
    """Fetch and parse the live NSE Ind AS XBRL for the reviewed quarter."""
    download_folder = repo_root / "data" / "raw" / "watchlist" / stock.symbol.lower() / "nse"
    source = NseXbrlSource(download_folder, symbol=stock.identifiers.nse_symbol)
    retrieval = source.fetch_consolidated_quarter(
        from_date=stock.quarter.period_start, to_date=stock.quarter.period_end
    )
    return parse_observations(
        retrieval.local_path.read_bytes(),
        source_id=retrieval.source_id,
        file_sha256=retrieval.file_sha256,
        retrieved_at=retrieval.retrieved_at,
        taxonomies=_ALL_TAXONOMIES,
    )


def _bse_period_label(stock: StockConfig) -> str:
    """The BSE "Mon-YY" column label for the stock's reviewed quarter end."""
    return stock.quarter.period_end.strftime(_BSE_PERIOD_LABEL_FORMAT)


def _collect_bse(
    stock: StockConfig, mode: RunMode, repo_root: Path, retrieved_at: datetime
) -> CollectedSource:
    """Pull the BSE resultsSnapshot summary for the reviewed quarter (second host).

    BSE's ``resultsSnapshot`` is a first-party (BSE-hosted) *summary* source that
    exposes only the latest quarters it publishes. A quarter it no longer carries
    is recorded ``SKIPPED`` with the structured note (skippable fail-closed), not a
    hard block. A committed ``.xml`` fixture is still parsed as a full XBRL instance
    for the deterministic two-host test; a ``.json`` fixture is a resultsSnapshot.
    """
    source_id = SUMMARY_SOURCE_ID
    period_label = _bse_period_label(stock)
    try:
        if mode is RunMode.FIXTURE:
            return _collect_bse_fixture(stock, repo_root, retrieved_at, period_label)
        download_folder = repo_root / "data" / "raw" / "watchlist" / stock.symbol.lower() / "bse"
        source = BseSource(download_folder, scrip_code=stock.identifiers.bse_scrip)
        result = source.fetch_summary(period_label=period_label)
    except (BseFetchError, XbrlParseError, OSError) as error:
        return _blocked(SourceKind.BSE, source_id, str(error))
    if not result.observations:
        return _skip(SourceKind.BSE, source_id, result.note or "no BSE summary observations")
    return _ok(SourceKind.BSE, source_id, result.observations)


def _collect_bse_fixture(
    stock: StockConfig, repo_root: Path, retrieved_at: datetime, period_label: str
) -> CollectedSource:
    """Read a committed BSE fixture: a resultsSnapshot ``.json`` or an XBRL ``.xml``."""
    if stock.fixtures.bse is None:
        return _skip(SourceKind.BSE, SUMMARY_SOURCE_ID, "no BSE fixture configured")
    path = repo_root / stock.fixtures.bse
    if path.suffix == ".json":
        snapshot = _load_bse_snapshot(path)
        result = BseSource.parse_summary(
            snapshot,
            period_label=period_label,
            scrip_code=stock.identifiers.bse_scrip,
            results_url=BSE_RESULTS_URL_TEMPLATE.format(scrip=stock.identifiers.bse_scrip),
            retrieved_at=retrieved_at,
        )
        if not result.observations:
            return _skip(
                SourceKind.BSE, SUMMARY_SOURCE_ID, result.note or "no BSE summary observations"
            )
        return _ok(SourceKind.BSE, SUMMARY_SOURCE_ID, result.observations)
    xml = path.read_bytes()
    observations = BseSource.parse(xml, file_sha256=_sha256(xml), retrieved_at=retrieved_at)
    return _ok(SourceKind.BSE, BSE_XBRL_SOURCE_ID, observations)


def _load_bse_snapshot(path: Path) -> dict[str, Any]:
    """Load a committed BSE resultsSnapshot JSON fixture, failing closed if malformed."""
    parsed: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise BseFetchError(f"BSE snapshot fixture {path} is not a JSON object")
    return parsed


def _collect_screener(
    stock: StockConfig, mode: RunMode, repo_root: Path, retrieved_at: datetime
) -> CollectedSource:
    """Pull the Screener derived quarterly P&L (cross-check only; non-fatal)."""
    source_id = "screener"
    try:
        if mode is RunMode.FIXTURE:
            if stock.fixtures.screener is None:
                return _skip(SourceKind.SCREENER, source_id, "no Screener fixture configured")
            html = (repo_root / stock.fixtures.screener).read_text(encoding="utf-8")
            observations = parse_quarterly_pnl(
                html,
                source_url=f"fixture://{stock.identifiers.screener_slug}",
                file_sha256=_sha256(html.encode("utf-8")),
                entity_id=stock.identifiers.screener_slug,
                consolidated=True,
                retrieved_at=retrieved_at,
            )
        else:
            source = ScreenerSource(
                ScreenerSourceConfig(slug=stock.identifiers.screener_slug, consolidated=True)
            )
            observations = source.fetch().observations
    except (ScreenerFetchError, OSError) as error:
        return _skip(SourceKind.SCREENER, source_id, f"unavailable: {error}")
    return _ok(SourceKind.SCREENER, source_id, observations)


def _collect_tijori(
    stock: StockConfig,
    mode: RunMode,
    repo_root: Path,
    credentials: TijoriCredentials | None,
) -> CollectedSource:
    """Pull the Tijori derived P&L; skip cleanly without credentials/fixture."""
    source_id = "tijori"
    try:
        if mode is RunMode.FIXTURE:
            if stock.fixtures.tijori is None:
                return _skip(SourceKind.TIJORI, source_id, "no Tijori fixture configured")
            raw = (repo_root / stock.fixtures.tijori).read_bytes()
            observations = TijoriSource.parse_pl_bytes(raw)
        else:
            if credentials is None:
                return _skip(SourceKind.TIJORI, source_id, "no Tijori credentials injected")
            source = TijoriSource(TijoriSourceConfig(credentials=credentials))
            observations = source.fetch_pl(stock.identifiers.tijori_slug)
    except (TijoriError, OSError) as error:
        return _skip(SourceKind.TIJORI, source_id, f"unavailable: {error}")
    return _ok(SourceKind.TIJORI, source_id, observations)


def _collect_pdf(stock: StockConfig, repo_root: Path, retrieved_at: datetime) -> CollectedSource:
    """Parse the issuer results PDF when configured, else skip with a note."""
    if stock.results_pdf is None or stock.fixtures.results_pdf is None:
        return _skip(SourceKind.PDF, "results-pdf", "no results-PDF configured")
    source_id = stock.results_pdf.source_id
    try:
        path = repo_root / stock.fixtures.results_pdf
        loaded = load_pdf(source_id=source_id, path=path, expected_sha256=stock.results_pdf.sha256)
        observations = extract_consolidated_pl(
            loaded, spec=_pdf_spec(stock), retrieved_at=retrieved_at
        )
    except (PdfIntegrityError, OSError) as error:
        return _blocked(SourceKind.PDF, source_id, str(error))
    return _ok(SourceKind.PDF, source_id, observations)


def _pdf_spec(stock: StockConfig) -> PdfParseSpec:
    """Assemble a PDF-parse spec from the shared defaults and the stock identity."""
    defaults = PdfParseConfig()
    return PdfParseSpec(
        statement_markers=defaults.statement_markers,
        anchor_label=defaults.anchor_label,
        target_lines=defaults.target_lines,
        entity_scheme=stock.entity_scheme,
        entity_id=stock.identifiers.nse_symbol,
        currency=defaults.currency,
        scope=Scope.CONSOLIDATED,
        accounting_basis=AccountingFramework.IND_AS,
        period_start=stock.quarter.period_start,
        period_end=stock.quarter.period_end,
        row_band_tolerance_pt=defaults.row_band_tolerance_pt,
        column_x_tolerance_pt=defaults.column_x_tolerance_pt,
        month_names=defaults.month_names,
    )


def _collect_sec(stock: StockConfig) -> CollectedSource:
    """SEC is a US-listing-only retrospective annual source; skip otherwise."""
    if not stock.identifiers.us_listed:
        return _skip(SourceKind.SEC, "sec", "not US-listed; SEC has no filing for this issuer")
    return _skip(
        SourceKind.SEC,
        "sec",
        "SEC is a retrospective annual source, not cross-footed against the quarter",
    )


def _sha256(payload: bytes) -> str:
    """Return the hex sha256 of raw bytes (fixture provenance stamping)."""
    return hashlib.sha256(payload).hexdigest()


# --- latest-quarter resolution ------------------------------------------------


def _bse_available_periods(
    stock: StockConfig, mode: RunMode, repo_root: Path, kinds: frozenset[SourceKind]
) -> tuple[str, ...] | None:
    """The period columns BSE currently publishes, or ``None`` if unresolvable.

    ``None`` (not an empty tuple) signals that BSE could not be consulted at all —
    not selected, no fixture, an XBRL-only fixture, or a live failure — so the
    caller fails closed rather than fabricating a quarter.
    """
    if SourceKind.BSE not in kinds:
        return None
    if mode is RunMode.FIXTURE:
        if stock.fixtures.bse is None or not stock.fixtures.bse.endswith(".json"):
            return None
        snapshot = _load_bse_snapshot(repo_root / stock.fixtures.bse)
        return tuple(str(period) for period in snapshot.get("periods", []))
    download_folder = repo_root / "data" / "raw" / "watchlist" / stock.symbol.lower() / "bse"
    source = BseSource(download_folder, scrip_code=stock.identifiers.bse_scrip)
    try:
        return source.fetch_summary(period_label=_LATEST_PROBE_LABEL).available_periods
    except (BseFetchError, OSError):
        return None


def _latest_completed_quarter(periods: Sequence[str], stock: StockConfig) -> StockQuarter | None:
    """Pick the most recent completed quarter column, or ``None`` if there is none.

    Fiscal-year columns are ignored; only "Mon-YY" quarter columns are eligible,
    and the one with the latest period end wins. Reuses the BSE period resolver so
    the bounds match what the summary source stamps on its observations.
    """
    best: StockQuarter | None = None
    for label in periods:
        try:
            start, end = _period_bounds(label)
        except ValueError:
            continue
        if (end - start).days >= _MAX_QUARTER_SPAN_DAYS:
            continue
        if best is None or end > best.period_end:
            best = StockQuarter(
                label=label,
                period_start=start,
                period_end=end,
                knowledge_cutoff=stock.quarter.knowledge_cutoff,
                filing_taxonomy=stock.quarter.filing_taxonomy,
            )
    return best


def _resolve_latest_stock(
    stock: StockConfig, mode: RunMode, repo_root: Path, kinds: frozenset[SourceKind]
) -> tuple[StockConfig | None, str]:
    """Retarget a stock onto the latest quarter its sources can share, or explain why not."""
    periods = _bse_available_periods(stock, mode, repo_root, kinds)
    if periods is None:
        return None, "cannot align latest quarter: BSE resultsSnapshot unavailable"
    quarter = _latest_completed_quarter(periods, stock)
    if quarter is None:
        return None, f"cannot align latest quarter: no completed quarter column in {list(periods)}"
    return stock.model_copy(update={"quarter": quarter}), ""


# --- orchestration ------------------------------------------------------------


def run_stock(
    stock: StockConfig,
    *,
    mode: RunMode,
    repo_root: Path,
    kinds: frozenset[SourceKind] = ALL_SOURCE_KINDS,
    tijori_credentials: TijoriCredentials | None = None,
    out_dir: Path = DEFAULT_GOLD_DIR,
    quarter_mode: QuarterMode = QuarterMode.PINNED,
) -> StockReport:
    """Collect every source for one stock, then reconcile and score it.

    In ``LATEST`` quarter mode the stock is first retargeted onto the newest
    quarter its first-party sources can share; if they cannot be aligned the stock
    is reported ``BLOCKED`` with the reason rather than run on a fabricated period.
    """
    if quarter_mode is QuarterMode.LATEST:
        resolved, reason = _resolve_latest_stock(stock, mode, repo_root, kinds)
        if resolved is None:
            return reconcile_stock(
                stock, [_blocked(SourceKind.BSE, SUMMARY_SOURCE_ID, reason)], out_dir=out_dir
            )
        stock = resolved
    sources = collect_sources(
        stock,
        mode=mode,
        repo_root=repo_root,
        kinds=kinds,
        tijori_credentials=tijori_credentials,
    )
    return reconcile_stock(stock, sources, out_dir=out_dir)


def run_wave(
    config: WatchlistConfig,
    *,
    mode: RunMode,
    repo_root: Path,
    kinds: frozenset[SourceKind] = ALL_SOURCE_KINDS,
    tijori_credentials: TijoriCredentials | None = None,
    out_dir: Path = DEFAULT_GOLD_DIR,
    quarter_mode: QuarterMode = QuarterMode.PINNED,
) -> WaveReport:
    """Run every watchlist stock and assemble the wave roll-up."""
    reports = [
        run_stock(
            stock,
            mode=mode,
            repo_root=repo_root,
            kinds=kinds,
            tijori_credentials=tijori_credentials,
            out_dir=out_dir,
            quarter_mode=quarter_mode,
        )
        for stock in config.stocks
    ]
    quarter_labels = tuple(sorted({report.quarter for report in reports}))
    _LOGGER.info(
        "wave_complete",
        wave=config.wave,
        stocks=len(reports),
        done=sum(1 for r in reports if r.outcome is StockOutcome.DONE),
        blocked=sum(1 for r in reports if r.outcome is StockOutcome.BLOCKED),
    )
    return WaveReport(wave=config.wave, quarter_labels=quarter_labels, stocks=tuple(reports))
