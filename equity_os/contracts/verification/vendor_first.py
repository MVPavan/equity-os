"""Vendor-first admission vocabulary: labels, T1 outcomes, filing states and failures, fallback
outcomes (VENDOR-1 spec §6.5, §6.8)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from enum import StrEnum
from types import MappingProxyType


class AdmissionLabel(StrEnum):
    """The owner's two labels on an admitted value (stored in ``fact_admissions.label``)."""

    CHECKED_AGAINST_FILING = "CHECKED_AGAINST_FILING"
    VENDORS_AGREE_NOT_CHECKED = "VENDORS_AGREE_NOT_CHECKED"


LABEL_TEXT: Mapping[AdmissionLabel, str] = MappingProxyType(
    {
        AdmissionLabel.CHECKED_AGAINST_FILING: "checked against filing",
        AdmissionLabel.VENDORS_AGREE_NOT_CHECKED: "vendors agree, not checked against filing",
    }
)


def weakest(labels: Iterable[str]) -> AdmissionLabel:
    """The weakest of the labels: not checked against a filing is weaker than checked."""
    checked = AdmissionLabel.CHECKED_AGAINST_FILING
    return min(map(AdmissionLabel, labels), key=lambda label: label is checked)


class VendorOutcome(StrEnum):
    """T1: how the two vendor values for a cell relate."""

    VENDOR_UNMAPPED = "VENDOR_UNMAPPED"
    VENDORS_DISAGREE = "VENDORS_DISAGREE"
    VENDORS_IMPRECISE = "VENDORS_IMPRECISE"
    VENDORS_AGREE = "VENDORS_AGREE"


class FilingState(StrEnum):
    """The filed side of a cell, against the vendor value."""

    FILING_ABSENT = "FILING_ABSENT"
    FILING_FAILED = "FILING_FAILED"
    FILING_DIFFERS = "FILING_DIFFERS"
    FILING_AGREES = "FILING_AGREES"


class FilingFailure(StrEnum):
    """Why a present filing fails the first-party admission rule: the detail of a
    ``FILING_UNRESOLVED`` refusal."""

    EXTRACTION_NOT_AGREE = "EXTRACTION_NOT_AGREE"
    NOT_SINGLE_REPRESENTATION = "NOT_SINGLE_REPRESENTATION"
    NO_DIRECT_OCCURRENCE = "NO_DIRECT_OCCURRENCE"
    KNOWLEDGE_TIME_UNKNOWN = "KNOWLEDGE_TIME_UNKNOWN"


class FallbackOutcome(StrEnum):
    """Terminal outcome of the fallback workflow for one company-period."""

    ADMITTED = "ADMITTED"
    FILING_UNAVAILABLE = "FILING_UNAVAILABLE"
    FILING_UNRESOLVED = "FILING_UNRESOLVED"
    STILL_REFUSED = "STILL_REFUSED"


class FallbackDisposition(StrEnum):
    """A fallback-only disposition of an original trigger cell (§6.8 step 5); a cell the rerun
    still refuses carries its ``AdmissionRefusal`` instead. None of them creates a fact."""

    ADMITTED = "ADMITTED"
    NOT_DISCLOSED = "NOT_DISCLOSED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    RERUN_ROW_MISSING = "RERUN_ROW_MISSING"


class FallbackFailure(StrEnum):
    """Why a fallback stage failed before a rerun: the detail of its ``FILING_UNRESOLVED``."""

    PDF_UNACQUIRED = "PDF_UNACQUIRED"
    INTAKE_REFUSED = "INTAKE_REFUSED"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    LISTING_UNPARSED = "LISTING_UNPARSED"
    RERUN_UNRESOLVED = "RERUN_UNRESOLVED"
