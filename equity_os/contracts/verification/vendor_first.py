"""Vendor-first admission vocabulary: labels, T1 outcomes, filing states, fallback outcomes
(VENDOR-1 spec §6.5, §6.8)."""

from __future__ import annotations

from collections.abc import Mapping
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


class FallbackOutcome(StrEnum):
    """Terminal outcome of the fallback workflow for one company-period."""

    ADMITTED = "ADMITTED"
    FILING_UNAVAILABLE = "FILING_UNAVAILABLE"
    FILING_UNRESOLVED = "FILING_UNRESOLVED"
    STILL_REFUSED = "STILL_REFUSED"
