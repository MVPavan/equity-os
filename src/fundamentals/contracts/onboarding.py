"""Onboarding vocabulary (plan D6 D4.1): the one definition the CLI, discovery, gate and the
``0022`` CHECK text share.

An onboarding attempt verifies an NSE symbol per verification unit and ends in one of four
outcomes. ``UNIT_SURFACES`` names the base run representation each excludable unit supplies;
``ONBOARDING_VERSIONS`` is the configuration pin every onboarded company is compared under.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from enum import StrEnum
from zoneinfo import ZoneInfo

from fundamentals.contracts.canonical import Representation
from fundamentals.contracts.config_versions import ConfigVersions

INDIA = ZoneInfo("Asia/Kolkata")


def as_of_for(retrieved_at: datetime) -> date:
    """C13: the Asia/Kolkata date of the master's retrieval."""
    return retrieved_at.astimezone(INDIA).date()


class VerificationUnit(StrEnum):
    """A namespace onboarding verifies on its own evidence."""

    EXCHANGE = "EXCHANGE"
    XBRL_ENTITY = "XBRL_ENTITY"
    SCREENER = "SCREENER"
    TIJORI = "TIJORI"
    UPSTOX = "UPSTOX"
    RESULTS_PDF = "RESULTS_PDF"


ANCHOR_UNITS = (VerificationUnit.EXCHANGE, VerificationUnit.XBRL_ENTITY)


class OnboardingOutcome(StrEnum):
    """The data spec §8 outcomes of one attempt."""

    ONBOARDED = "ONBOARDED"
    PARTIAL = "PARTIAL"
    UNSUPPORTED = "UNSUPPORTED"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"


class VerificationState(StrEnum):
    """What one unit's evidence established."""

    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    CONFLICT = "CONFLICT"
    NOT_AUTHORISED = "NOT_AUTHORISED"
    UNAVAILABLE = "UNAVAILABLE"


class OnboardingReason(StrEnum):
    """Why a unit is not verified or an attempt stopped (a conflict carries its own detail)."""

    NOT_LISTED = "NOT_LISTED"
    FOREIGN_ISIN = "FOREIGN_ISIN"
    STANDALONE_BASIS = "STANDALONE_BASIS"
    NO_IND_AS_FILING = "NO_IND_AS_FILING"
    INSUFFICIENT_FILINGS = "INSUFFICIENT_FILINGS"
    FINANCIAL_OR_UNKNOWN_SECTOR = "FINANCIAL_OR_UNKNOWN_SECTOR"
    UNSUPPORTED_SCHEMA = "UNSUPPORTED_SCHEMA"
    NO_FRAMEWORK_DECLARATION = "NO_FRAMEWORK_DECLARATION"
    NO_CANDIDATE = "NO_CANDIDATE"
    BASIS_UNVERIFIED = "BASIS_UNVERIFIED"
    EMPTY_STATEMENT = "EMPTY_STATEMENT"
    ACCESS_FAILED = "ACCESS_FAILED"
    NOT_AUTHORISED = "NOT_AUTHORISED"
    EXCLUDED_BY_RULE = "EXCLUDED_BY_RULE"
    STOPPED_ON_CONFLICT = "STOPPED_ON_CONFLICT"
    STOPPED_ON_REFUSAL = "STOPPED_ON_REFUSAL"
    ACQUISITION_FAILED = "ACQUISITION_FAILED"


UNIT_SURFACES: Mapping[VerificationUnit, str] = {
    VerificationUnit.RESULTS_PDF: Representation.PDF.value,
    VerificationUnit.SCREENER: "screener-subscriber/SCREENER_FINANCIALS",
    VerificationUnit.TIJORI: "tijori/financials",
    VerificationUnit.UPSTOX: "upstox/income-statement",
}

ONBOARDING_VERSIONS = ConfigVersions(dictionary="v2", mapping_set="v5")

# A unit's state and, unless verified, why.
Verdict = tuple[VerificationState, str | None]
