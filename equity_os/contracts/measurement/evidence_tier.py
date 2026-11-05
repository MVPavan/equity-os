"""Evidence tiers: how much a mapping or computed value is entitled to conclude."""

from __future__ import annotations

from enum import StrEnum


class EvidenceTier(StrEnum):
    """How much a comparison on this line is entitled to conclude.

    **A tier is not self-sufficient — read the mapping's ``means`` with it.**
    ``EQUIVALENCE_DEMONSTRATED`` may carry a stated exclusion there, because an
    identity can hold across most of a population and fail on a named part of
    it. Both tier-1 lines currently do: the 2026-09-04 sweep held on 73 of 80
    live lines and failed on companies with material exceptional items or
    associates. Grading those lines down would have emptied tier 1 and made
    ``MISMATCH`` unreachable, hiding a real Upstox-side defect among 62 tier-2
    anomalies, so the owner kept the tier and required the exclusion to travel
    in ``means`` — which reaches every report row, as the enum member does not.
    """

    EQUIVALENCE_DEMONSTRATED = "EQUIVALENCE_DEMONSTRATED"
    RELATED_NOT_EQUIVALENT = "RELATED_NOT_EQUIVALENT"
    EQUIVALENCE_UNPROVEN = "EQUIVALENCE_UNPROVEN"


# Strongest first.
TIER_ORDER: tuple[EvidenceTier, ...] = (
    EvidenceTier.EQUIVALENCE_DEMONSTRATED,
    EvidenceTier.RELATED_NOT_EQUIVALENT,
    EvidenceTier.EQUIVALENCE_UNPROVEN,
)

_NO_TIERS = "weakest() needs at least one tier"


def weakest(*tiers: EvidenceTier) -> EvidenceTier:
    """Return the weakest of the given tiers; a value is only as strong as its weakest input."""
    if not tiers:
        raise ValueError(_NO_TIERS)
    return max(tiers, key=TIER_ORDER.index)
