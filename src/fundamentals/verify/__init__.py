"""Fundamentals verify layer — comparison-key, cross-foot, cross-check, anchor."""

from fundamentals.verify.comparison_key import (
    ComparabilityResult,
    ComparisonKey,
    explain_comparability,
)
from fundamentals.verify.cross_check import CrossCheckResult, cross_check
from fundamentals.verify.crossfoot import (
    CrossFootResult,
    FootingContextError,
    Identity,
    MissingRequiredFactError,
    SignedTerm,
    check_identity,
    half_ulp,
    observation_half_ulp,
)
from fundamentals.verify.quote_anchor import (
    QuoteAnchorResult,
    SourceBlock,
    SourceDocument,
    verify_quote_anchor,
)

__all__ = [
    "ComparabilityResult",
    "ComparisonKey",
    "CrossCheckResult",
    "CrossFootResult",
    "FootingContextError",
    "Identity",
    "MissingRequiredFactError",
    "QuoteAnchorResult",
    "SignedTerm",
    "SourceBlock",
    "SourceDocument",
    "check_identity",
    "cross_check",
    "explain_comparability",
    "half_ulp",
    "observation_half_ulp",
    "verify_quote_anchor",
]
