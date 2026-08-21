"""SEC annual adapter — INFY FY25 20-F IFRS facts for retrospective cross-check.

This adapter fetches the Infosys FY25 20-F annual IFRS facts from SEC EDGAR via
``edgartools`` and maps them onto the frozen :class:`Observation` contract. It
exists ONLY to validate the FY25 *annual* figures against an independent source
(the Q4 IFRS press release); it is deliberately excluded from the Q1 FY25
evidence package.

The exclusion is not a comment — it is enforced by the data. Every observation
carries the 20-F filing date (2025-07-01) as its provenance ``filed_at``, which
is the value a downstream filter compares against the Q1 knowledge cutoff
(:data:`Q1_UPDATE_CUTOFF`, 2024-07-18). Because the 20-F was filed nearly a year
after the Q1 cutoff, :func:`is_excluded_from_q1` returns ``True`` for every fact,
so a cutoff-aware consumer never mistakes annual USD data for the Q1 ₹-crore
update. :class:`SecAnnualResult` restates the same guarantee at the batch level
via ``cross_check_only`` and ``excluded_from_q1``.

Rights posture: SEC EDGAR automated access is authorised under A05-DECISION-001
within fair-access limits — a declared User-Agent, low request volume, explicit
timeouts, and bounded retries. See ``docs/research/pdf-extraction-bakeoff.md``
§3b/§3c for the tooling decision and the confirmed FY25 values.

Known ``edgartools`` trap guarded here: its *rendered* statement table shows
per-share values as ``0.00`` (the millions scale is misapplied). This adapter
reads the underlying fact value (the DataFrame path), never the rendered table,
so EPS loads as its true ``0.76``.
"""

from __future__ import annotations

import hashlib
import logging
import time
import urllib.error
import urllib.request
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from edgar import Company, set_identity
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.observation import (
    AccountingFramework,
    Observation,
    PeriodType,
    Scope,
)
from fundamentals.contracts.provenance import Provenance, SourceAnchorType

_LOGGER = logging.getLogger(__name__)

INFY_CIK = 1067491
FORM_20F = "20-F"
FY25_PERIOD_START = date(2024, 4, 1)
FY25_PERIOD_END = date(2025, 3, 31)

# Q1 FY25 knowledge cutoff (matches the Slice 0 manifest retrieval time). A fact
# is excluded from the Q1 evidence package when its knowledge time is after this.
Q1_UPDATE_CUTOFF = datetime(2024, 7, 18, tzinfo=UTC)

DEFAULT_USER_AGENT = "EquityOS Research (mvpavan42@gmail.com)"
USER_AGENT_HEADER = "User-Agent"
COMPANYFACTS_URL_TEMPLATE = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

ENTITY_SCHEME = "sec-cik"
IFRS_REGISTRY = "ifrs-full"

USD = "USD"
USD_MILLION = "USD million"
_MILLION = Decimal(1_000_000)
_MONETARY_SCALE = 1_000_000
_MONETARY_DECIMALS = -6
_EPS_SCALE = 1
_EPS_DECIMALS = 2

# A full April–March fiscal year is 364/365 days; a quarter is ~90. The guard
# only needs to separate the two, so a generous lower bound is correct.
_FULL_YEAR_MIN_DAYS = 360


class SecConcept(StrEnum):
    """The four IFRS annual concepts this adapter cross-checks (per §3c)."""

    REVENUE = "ifrs-full:RevenueFromContractsWithCustomers"
    OPERATING_PROFIT = "ifrs-full:ProfitLossFromOperatingActivities"
    PROFIT_FOR_PERIOD = "ifrs-full:ProfitLoss"
    BASIC_EPS = "ifrs-full:BasicEarningsLossPerShare"


_PER_SHARE_CONCEPTS = frozenset({SecConcept.BASIC_EPS})


class SecFetchError(Exception):
    """Typed, resumable failure — raised instead of storing partial facts."""


class SecSourceConfig(BaseModel):
    """Injected fair-access settings for the SEC adapter (no env reads)."""

    model_config = ConfigDict(frozen=True)

    user_agent: str = DEFAULT_USER_AGENT
    cik: int = INFY_CIK
    form: str = FORM_20F
    period_start: date = FY25_PERIOD_START
    period_end: date = FY25_PERIOD_END
    request_timeout_seconds: float = 30.0
    max_retries: int = 3
    retry_backoff_seconds: float = 1.0


class SecAnnualResult(BaseModel):
    """Batch of FY25 annual observations, flagged as cross-check-only.

    ``knowledge_time`` is the 20-F filing date shared by every observation;
    ``excluded_from_q1`` restates the per-fact guarantee at the batch level.
    """

    model_config = ConfigDict(frozen=True)

    observations: tuple[Observation, ...]
    knowledge_time: datetime
    update_cutoff: datetime = Q1_UPDATE_CUTOFF
    cross_check_only: bool = True

    @property
    def excluded_from_q1(self) -> bool:
        """True when the batch's knowledge time is after the Q1 cutoff."""
        return self.knowledge_time > self.update_cutoff


def knowledge_time_of(observation: Observation) -> datetime:
    """Return the observation's knowledge time (its 20-F filing date)."""
    filed_at = observation.provenance.filed_at
    if filed_at is None:
        raise ValueError("SEC observation is missing provenance.filed_at (knowledge time)")
    return filed_at


def is_annual(observation: Observation) -> bool:
    """True when the observation spans a full fiscal year, not a quarter."""
    if observation.period_type is not PeriodType.DURATION:
        return False
    if observation.period_start is None or observation.period_end is None:
        return False
    return (observation.period_end - observation.period_start).days >= _FULL_YEAR_MIN_DAYS


def is_excluded_from_q1(observation: Observation, cutoff: datetime = Q1_UPDATE_CUTOFF) -> bool:
    """True when the observation must be kept out of the Q1 evidence package."""
    return knowledge_time_of(observation) > cutoff


class SecAnnualSource:
    """Fetches INFY FY25 20-F IFRS annual facts as cross-check observations."""

    def __init__(self, config: SecSourceConfig | None = None) -> None:
        self._config = config or SecSourceConfig()
        # edgartools requires a declared identity; this is config injection, not
        # an environment read, and keeps us inside SEC fair-access.
        set_identity(self._config.user_agent)

    def fetch(self) -> SecAnnualResult:
        """Load the FY25 annual observations or raise a typed failure.

        Fails closed: on any fetch or validation error no observations are
        returned. The company-facts document is hashed once for provenance.
        """
        file_sha256 = self._companyfacts_sha256()
        selected = self._select_annual_facts()

        observations = tuple(
            self._to_observation(concept, fact, file_sha256)
            for concept, fact in sorted(selected.items(), key=lambda item: item[0].value)
        )
        knowledge_time = knowledge_time_of(observations[0])
        _LOGGER.info(
            "loaded %d SEC FY25 annual observations knowledge_time=%s",
            len(observations),
            knowledge_time.date().isoformat(),
        )
        return SecAnnualResult(observations=observations, knowledge_time=knowledge_time)

    def _companyfacts_sha256(self) -> str:
        """Fetch the company-facts JSON politely and return its sha256 digest."""
        url = COMPANYFACTS_URL_TEMPLATE.format(cik=self._config.cik)
        request = urllib.request.Request(url, headers={USER_AGENT_HEADER: self._config.user_agent})
        last_error: Exception | None = None
        for attempt in range(1, self._config.max_retries + 1):
            try:
                with urllib.request.urlopen(
                    request, timeout=self._config.request_timeout_seconds
                ) as response:
                    payload: bytes = response.read()
                return hashlib.sha256(payload).hexdigest()
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                last_error = error
                _LOGGER.warning("companyfacts fetch attempt %d failed: %s", attempt, error)
                time.sleep(self._config.retry_backoff_seconds * attempt)
        raise SecFetchError(
            f"companyfacts fetch failed after {self._config.max_retries} attempts"
        ) from last_error

    def _select_annual_facts(self) -> dict[SecConcept, Any]:
        """Return exactly one FY25 annual fact per tracked concept."""
        facts = self._load_all_facts()
        concept_by_value = {concept.value: concept for concept in SecConcept}
        selected: dict[SecConcept, Any] = {}
        for fact in facts:
            concept = concept_by_value.get(fact.concept)
            if concept is None:
                continue
            if fact.form_type != self._config.form:
                continue
            if fact.period_start != self._config.period_start:
                continue
            if fact.period_end != self._config.period_end:
                continue
            existing = selected.get(concept)
            if existing is None or _filing_date_of(fact) > _filing_date_of(existing):
                selected[concept] = fact

        missing = [concept.value for concept in SecConcept if concept not in selected]
        if missing:
            raise SecFetchError(f"FY25 annual facts not found for concepts: {sorted(missing)}")
        return selected

    def _load_all_facts(self) -> list[Any]:
        """Load all entity facts via edgartools with bounded retries."""
        last_error: Exception | None = None
        for attempt in range(1, self._config.max_retries + 1):
            try:
                company = Company(self._config.cik)
                entity_facts = company.get_facts()
                if entity_facts is None:
                    raise SecFetchError(f"no XBRL facts for CIK {self._config.cik}")
                facts: list[Any] = list(entity_facts.get_all_facts())
                return facts
            except SecFetchError:
                raise
            except Exception as error:
                last_error = error
                _LOGGER.warning("edgar facts fetch attempt %d failed: %s", attempt, error)
                time.sleep(self._config.retry_backoff_seconds * attempt)
        raise SecFetchError(
            f"edgar facts fetch failed after {self._config.max_retries} attempts"
        ) from last_error

    def _to_observation(self, concept: SecConcept, fact: Any, file_sha256: str) -> Observation:
        """Map one FY25 IFRS annual fact onto the Observation contract."""
        raw_value = str(fact.value)
        unit = str(fact.unit)
        accession = str(fact.accession)
        filing_date = _filing_date_of(fact)

        if concept in _PER_SHARE_CONCEPTS:
            normalized_value = Decimal(raw_value)
            normalized_unit = unit
            scale = _EPS_SCALE
            decimals = _EPS_DECIMALS
        else:
            self._require_usd(concept, unit)
            normalized_value = Decimal(raw_value) / _MILLION
            normalized_unit = USD_MILLION
            scale = _MONETARY_SCALE
            decimals = _MONETARY_DECIMALS

        filed_at = datetime(filing_date.year, filing_date.month, filing_date.day, tzinfo=UTC)
        context_ref = f"{accession}:{concept.value}"
        provenance = Provenance(
            source_id=f"sec-edgar-20f-{accession}",
            file_sha256=file_sha256,
            anchor_type=SourceAnchorType.XBRL_CONTEXT,
            context_ref=context_ref,
            retrieved_at=datetime.now(tz=UTC),
            filed_at=filed_at,
            first_seen_at=filed_at,
        )
        return Observation(
            concept_qname=concept.value,
            registry_version=IFRS_REGISTRY,
            raw_value=raw_value,
            normalized_value=normalized_value,
            normalized_unit=normalized_unit,
            context_ref=context_ref,
            entity_scheme=ENTITY_SCHEME,
            entity_id=f"{self._config.cik:010d}",
            scope=Scope.CONSOLIDATED,
            accounting_basis=AccountingFramework.IFRS,
            period_type=PeriodType.DURATION,
            period_start=self._config.period_start,
            period_end=self._config.period_end,
            unit_ref=unit,
            currency=USD,
            scale=scale,
            decimals=decimals,
            provenance=provenance,
        )

    @staticmethod
    def _require_usd(concept: SecConcept, unit: str) -> None:
        """Fail closed if a monetary fact is not tagged USD (currency guard)."""
        if unit != USD:
            raise SecFetchError(f"expected USD for {concept.value}, got unit {unit!r}")


def _filing_date_of(fact: Any) -> date:
    """Extract a fact's filing date, raising if absent."""
    filing_date = fact.filing_date
    if not isinstance(filing_date, date):
        raise SecFetchError("SEC fact is missing a filing_date")
    return filing_date
