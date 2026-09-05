"""The shared capture-level outcome of one acquisition attempt.

Capture-level only: these codes say what happened when a source was *asked* for
a document — whether bytes arrived, and if not, why the vendor said no. Each
adapter keeps its own native enum as its wire vocabulary (the Upstox lane's
``AcquisitionOutcome``, the subscriber session's ``PageOutcome``) and translates
into this code through a ``to_outcome_record`` function that lives beside it, so
the native value survives the translation verbatim inside the record.

``NOT_OFFERED`` means the vendor has no such surface for this entity at all —
a standalone-only company has no consolidated basis to serve — which is a fact
about the entity, not a failure and never a success.

Parse- and run-level states (sections, islands, screens, watchlists, events)
are deliberately **not** represented here: they describe what was inside a
response that did arrive, and folding them in would make one code mean both
"the vendor changed the payload" and "our parser missed a table". ``eqos-kx4.5``
owns that mapping.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints


class OutcomeCode(StrEnum):
    """What one acquisition attempt established, in shared vocabulary."""

    OK = "ok"
    OK_EMPTY = "ok_empty"
    NOT_OFFERED = "not_offered"
    PLAN_LOCKED = "plan_locked"
    AUTH_EXPIRED = "auth_expired"
    IDENTITY_MISMATCH = "identity_mismatch"
    SCHEMA_DRIFT = "schema_drift"
    RATE_LIMITED = "rate_limited"
    TRANSPORT_ERROR = "transport_error"
    CLIENT_BLOCKED = "client_blocked"
    REQUEST_REJECTED = "request_rejected"


# The only two codes a bounded retry can clear. Every other failure is
# terminal: a block never clears on backoff, and a dead token is renewed by a
# human. Mirrors each adapter's own retry set, which its translator must agree
# with member for member.
RETRYABLE_CODES: frozenset[OutcomeCode] = frozenset(
    {OutcomeCode.RATE_LIMITED, OutcomeCode.TRANSPORT_ERROR}
)


class OutcomeRecord(BaseModel):
    """One capture outcome, carrying the source's own words for it.

    A record is evidence, so it cannot be restated in place and cannot lose its
    origin: ``native_kind`` names the enum that classified the attempt and
    ``native_value`` is that member's wire value verbatim, which is the only
    way to re-check a stored outcome against the source that produced it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: OutcomeCode
    native_kind: Annotated[str, StringConstraints(min_length=1)]
    native_value: Annotated[str, StringConstraints(min_length=1)]

    @property
    def retryable(self) -> bool:
        """Whether a bounded retry could clear this outcome."""
        return self.code in RETRYABLE_CODES
