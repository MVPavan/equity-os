"""The in-progress record of one company sub-document sweep.

Split out of :mod:`fundamentals.ingest.screener_company` so the orchestrator
reads as the order of the work rather than as bookkeeping. This is the one place
in Slice 2 that is deliberately mutable: everything it produces is frozen, but
while a sweep is running the request count, the retained bodies, the refusals
and the per-part outcomes are all still accumulating.

It also owns the rule about which transport refusal ends what. A rate limit ends
the whole sweep: Screener returned HTTP 429 after ~40 authenticated GETs, so once
one request has been refused the remaining parts must not each discover that for
themselves — that would keep requesting from a source that has just asked us to
stop. **Every other transport refusal ends only its own part.** A redirect, a
terminal status or an unreadable body is a fact about one document, and letting
it escape discards every body the run has already paid for: the first live smoke
lost twelve to eighteen fetched sub-documents and wrote an empty output directory
because one modal answered 302.
"""

from __future__ import annotations

from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict

from fundamentals.ingest.screener_company_artifacts import (
    CompanyFailure,
    DocumentEvidence,
    PartOutcome,
)
from fundamentals.ingest.screener_company_models import (
    CompanyPart,
    Validation,
    ValidationStatus,
)
from fundamentals.ingest.screener_session import ScreenerSessionSource
from fundamentals.ingest.screener_session_models import (
    ScreenerRateLimitedError,
    ScreenerSessionError,
)

_LOGGER = structlog.get_logger(__name__)

_REFUSED_EVENT = "screener_company_document_refused"
_ABORTED_EVENT = "screener_company_sweep_aborted"

RATE_LIMITED = (
    "rate-limited after {done} of {planned} planned sub-documents; the sweep stopped and "
    "everything already read is retained"
)
NOT_OFFERED = (
    "the page renders the section but not the control for this part, which is positive "
    "proof the company does not publish it"
)
NO_WAREHOUSE_ID = (
    "the page carries no data-warehouse-id, which this endpoint is scoped by; nothing was requested"
)
MISSING_SECTION = (
    "the page carries no {sections} section, which is where this part's control lives. An "
    "absent control is a fact about the company; an absent section is the page changing "
    "shape under us, and recording that as 'not offered' would file a layout change as an "
    "issuer property"
)
OVER_BUDGET = (
    "the page offers {planned} sub-documents, above the {cap}-request ceiling for one run "
    "against a source observed to rate-limit at ~40 GETs; nothing beyond the page was "
    "fetched, because discovering this one 429 at a time would spend the budget to learn it"
)
OVER_BUDGET_INCOMPLETE = (
    "refused before the first sub-request: {planned} planned against a ceiling of {cap}. No "
    "planned request was attempted, so this run is not complete in any sense — reporting it "
    "as complete would say every planned request was made when none was"
)


class CompanyDocument(BaseModel):
    """One retained sub-document response, kept beside the artifact it fed.

    The bytes are retained for the same reason the page's are: an artifact whose
    source document is gone cannot be re-derived or audited, and for the
    ``URL_ONLY`` parts the ``document_id`` is the whole of its identity.
    """

    model_config = ConfigDict(frozen=True)

    part: CompanyPart
    name: str
    document_id: str
    url: str
    content_sha256: str
    raw_body: bytes
    is_json: bool


class Sweep:
    """Mutable accumulator for one run, so each part reads as a small function.

    Deliberately not a frozen model: it is the one place in this slice that is
    an in-progress record rather than a published fact, and every artifact it
    produces at the end is frozen.
    """

    def __init__(self, *, source: ScreenerSessionSource, planned: int = 0) -> None:
        self.source = source
        # The plan is held here so a rate limit can report what was left. "after
        # 2 of 3" measured the abort against the requests already made, which
        # reads as a nearly finished run when fourteen were planned.
        self.planned = planned
        self.documents: list[CompanyDocument] = []
        self.failures: list[CompanyFailure] = []
        self.outcomes: list[PartOutcome] = []
        # Starts at one for the company page, which has already been fetched by
        # the time a sweep exists.
        self.request_count = 1
        self.incomplete_reason: str | None = None

    @property
    def rate_limited(self) -> bool:
        """True once a 429 has ended the sweep; no further part is attempted."""
        return self.incomplete_reason is not None

    def fetch(self, *, part: CompanyPart, name: str, url: str, is_json: bool) -> Any:
        """Fetch and retain one sub-document, or return ``None`` if it did not arrive.

        Two failure shapes, deliberately handled differently. A rate limit ends
        the sweep, because the source has asked us to stop and every remaining
        part would only rediscover that. Any other transport refusal — a
        redirect, a terminal status, a body this transport will not interpret —
        is recorded against *this* document and the sweep continues, because it
        says nothing about the next document and abandoning the run would throw
        away everything already fetched.
        """
        if self.rate_limited:
            return None
        # Counted before the attempt, not after it succeeds: this is the ledger
        # of what the run actually asked the source for, and the request that
        # earned the 429 is the one that matters most in it.
        self.request_count += 1
        try:
            fetched = self.source.fetch_document(url=url)
        except ScreenerRateLimitedError:
            self.incomplete_reason = RATE_LIMITED.format(
                done=len(self.documents), planned=self.planned
            )
            _LOGGER.warning(
                _ABORTED_EVENT,
                fetched=len(self.documents),
                planned=self.planned,
                part=part.value,
            )
            return None
        except ScreenerSessionError as error:
            self.refuse(part=part, name=name, url=url, document_id=url, sha=None, error=error)
            return None
        self.documents.append(
            CompanyDocument(
                part=part,
                name=name,
                document_id=url,
                url=url,
                content_sha256=fetched.content_sha256,
                raw_body=fetched.raw_body,
                is_json=is_json,
            )
        )
        return fetched

    def refuse(
        self,
        *,
        part: CompanyPart,
        name: str,
        url: str | None = None,
        document_id: str | None = None,
        sha: str | None = None,
        error: Exception,
        validation: Validation = Validation.NONE,
    ) -> None:
        """Record one refused sub-document, beside its bytes where there are any.

        ``sha`` is ``None`` for the two refusals that have no body: a transport
        failure, where the response never became bytes this adapter would keep,
        and a page-shape failure, where the section that names the document is
        missing so no request was built.
        """
        self.failures.append(
            CompanyFailure(
                part=part,
                name=name,
                url=url,
                document_id=document_id,
                body_sha256=sha,
                refusal=type(error).__name__,
                detail=str(error),
                validation=validation,
                validation_status=ValidationStatus.FAILED,
            )
        )
        _LOGGER.warning(_REFUSED_EVENT, part=part.value, name=name, refusal=type(error).__name__)

    def record(
        self,
        part: CompanyPart,
        *,
        offered: bool,
        documents: tuple[DocumentEvidence, ...] = (),
        note: str = "",
    ) -> None:
        """Record what one requested part produced."""
        self.outcomes.append(
            PartOutcome(part=part, offered=offered, documents=documents, note=note)
        )
