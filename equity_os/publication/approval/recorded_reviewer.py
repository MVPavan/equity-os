"""A reviewer whose verdict was obtained out of band (LIVE-RUN-1 Task 4; OD-3, OD-4).

The verdict is read only from the reviewer's own preserved response, which must carry exactly
one binding line naming the subject, its sealed digest, the SHA-256 of the narrative under review
and the verdict; the responder record says only who answered. No model is called here.
"""

from __future__ import annotations

import hashlib
import re

from pydantic import BaseModel, ConfigDict

from equity_os.contracts.publication.ledger import ReviewOutput, Verdict
from equity_os.publication.approval.lifecycle import DecisionRefusedError

REHEARSAL_PROVIDER = "rehearsal"
TEST_DATABASE_PREFIX = "eqos_test_"
BINDING_PREFIX = "EQOS-BINDING"
_BINDING = re.compile(
    BINDING_PREFIX + r" subject=(?P<subject>\S+) sealed_digest=(?P<sealed_digest>[0-9a-f]{64})"
    r" narrative_sha256=(?P<narrative_sha256>[0-9a-f]{64})"
    r" verdict=(?P<verdict>APPROVE|REQUEST_CHANGES|REJECT)"
)
_ONE_LINE = "the response needs exactly one EQOS-BINDING line, well formed"
_DIGEST = "the response does not bind the sealed digest under review"
_NARRATIVE = "the response does not bind the reviewed narrative"


class Responder(BaseModel):
    """Who answered: recorded as data, never a verdict, digest or rationale."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str
    model: str
    effort: str
    brief_version: str


class Binding(BaseModel):
    """The response's binding line."""

    model_config = ConfigDict(frozen=True)

    subject: str
    sealed_digest: str
    narrative_sha256: str
    verdict: Verdict


def binding(response: str) -> Binding:
    """The response's single well-formed binding line, or refuse."""
    lines = [line for line in response.splitlines() if line.startswith(BINDING_PREFIX)]
    found = _BINDING.fullmatch(lines[0]) if len(lines) == 1 else None
    if found is None:
        raise DecisionRefusedError(_ONE_LINE)
    return Binding.model_validate(found.groupdict())


def rehearsal_allowed(provider: str, database: str) -> bool:
    """Whether a verdict from ``provider`` may decide on ``database`` (rehearsal: test only)."""
    return provider != REHEARSAL_PROVIDER or database.startswith(TEST_DATABASE_PREFIX)


class RecordedReviewer:
    """Returns the response's bound verdict, with the whole response as its rationale."""

    def __init__(self, responder: Responder, response: str) -> None:
        """Parse the binding now so a malformed response refuses before any connection."""
        self.provider, self.model = responder.provider, responder.model
        self.effort, self.brief_version = responder.effort, responder.brief_version
        self.response, self.binding = response, binding(response)

    def review(self, subject_text: str, sealed_digest: str) -> ReviewOutput:
        """The bound verdict if the binding names this digest and this exact narrative."""
        if self.binding.sealed_digest != sealed_digest:
            raise DecisionRefusedError(_DIGEST)
        if self.binding.narrative_sha256 != hashlib.sha256(subject_text.encode()).hexdigest():
            raise DecisionRefusedError(_NARRATIVE)
        return ReviewOutput(verdict=self.binding.verdict, rationale=self.response)
