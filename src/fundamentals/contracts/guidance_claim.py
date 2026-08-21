"""GuidanceClaim: management guidance modelled as an epistemically-typed claim.

Guidance is a forecast, not an observed fact, so it is a distinct contract. Each
claim carries its numeric range, unit, whether it is stated on a
constant-currency basis, its horizon and scope, free-text qualifiers, and a
mandatory :class:`EpistemicClass` label (guidance is ``FORECAST``). Provenance
binds the claim to an exact page/block/span in the held source.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.observation import Scope
from fundamentals.contracts.provenance import Provenance


class EpistemicClass(StrEnum):
    """Mandatory output label preventing interpretation from becoming fact."""

    OBSERVED = "observed"
    COMPUTED = "computed"
    INFERRED = "inferred"
    FORECAST = "forecast"
    OPINION = "opinion"


class GuidanceClaim(BaseModel):
    """A single management-guidance range bound to its source and epistemic class."""

    model_config = ConfigDict(frozen=True)

    metric: str
    lower_bound: Decimal
    upper_bound: Decimal
    unit: str
    constant_currency: bool
    horizon: str
    scope: Scope
    qualifiers: tuple[str, ...] = ()
    epistemic_class: EpistemicClass = EpistemicClass.FORECAST

    provenance: Provenance
