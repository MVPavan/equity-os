"""Orchestrate the multi-model, cross-verified thesis (bounded and fail-closed).

One deterministic prompt is built from the validated facts and sent to every
injected client concurrently (bounded — exactly the two models in practice). Each
client's answer is parsed into a draft; a failed or timed-out call becomes a
recorded gap, never a fabricated draft. The two drafts are cross-verified
deterministically, and the document's status reflects how many usable drafts came
back: two → OK, one → PARTIAL (with the gap recorded), none → BLOCKED.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed

import structlog

from fundamentals.thesis.client import (
    ThesisClientError,
    ThesisClientTimeoutError,
    ThesisModelClient,
)
from fundamentals.thesis.contracts import (
    DraftStatus,
    ThesisDocument,
    ThesisDocumentStatus,
    ThesisDraft,
    ValidatedFactSet,
)
from fundamentals.thesis.draft_parser import failed_draft, parse_draft
from fundamentals.thesis.prompt import build_prompt
from fundamentals.thesis.settings import DEFAULT_MAX_WORKERS
from fundamentals.thesis.verifier import cross_verify

_LOGGER = structlog.get_logger("fundamentals.thesis.pipeline")


def _invoke_client(client: ThesisModelClient, prompt: str) -> ThesisDraft:
    """Call one client, converting any failure into a recorded (never fabricated) draft."""
    start = time.monotonic()
    try:
        response = client.generate(prompt)
    except ThesisClientTimeoutError as error:
        return failed_draft(
            model_label=client.label,
            client_name=client.name,
            status=DraftStatus.TIMED_OUT,
            error=str(error),
            duration_seconds=time.monotonic() - start,
        )
    except ThesisClientError as error:
        return failed_draft(
            model_label=client.label,
            client_name=client.name,
            status=DraftStatus.FAILED,
            error=str(error),
            duration_seconds=time.monotonic() - start,
        )
    except Exception as error:  # fail-closed: a client bug must not crash the run
        return failed_draft(
            model_label=client.label,
            client_name=client.name,
            status=DraftStatus.FAILED,
            error=f"unexpected client error: {error}",
            duration_seconds=time.monotonic() - start,
        )
    return parse_draft(
        response.text,
        model_label=client.label,
        client_name=client.name,
        duration_seconds=response.duration_seconds,
    )


def _run_clients(
    clients: Sequence[ThesisModelClient], prompt: str, max_workers: int
) -> list[ThesisDraft]:
    """Run every client concurrently (bounded), preserving client order in the result."""
    if not clients:
        return []
    workers = max(1, min(max_workers, len(clients)))
    ordered: list[ThesisDraft | None] = [None] * len(clients)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures: dict[Future[ThesisDraft], int] = {
            executor.submit(_invoke_client, client, prompt): index
            for index, client in enumerate(clients)
        }
        for future in as_completed(futures):
            ordered[futures[future]] = future.result()
    return [draft for draft in ordered if draft is not None]


def _document_status(drafts: Sequence[ThesisDraft]) -> ThesisDocumentStatus:
    """Derive document status from the number of usable drafts."""
    usable = sum(1 for draft in drafts if draft.is_usable)
    if usable >= 2:
        return ThesisDocumentStatus.OK
    if usable == 1:
        return ThesisDocumentStatus.PARTIAL
    return ThesisDocumentStatus.BLOCKED


def build_thesis(
    fact_set: ValidatedFactSet,
    clients: Sequence[ThesisModelClient],
    *,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> ThesisDocument:
    """Generate two independent drafts, cross-verify them, and assemble the document."""
    prompt = build_prompt(fact_set)
    drafts = _run_clients(clients, prompt, max_workers)
    cross = cross_verify(fact_set, drafts)
    status = _document_status(drafts)
    _LOGGER.info(
        "thesis_built",
        symbol=fact_set.symbol,
        quarter=fact_set.quarter,
        status=status.value,
        usable_drafts=sum(1 for draft in drafts if draft.is_usable),
        unsourced_claims=len(cross.unsourced_claims),
        discrepancies=len(cross.discrepancies),
    )
    return ThesisDocument(
        fact_set=fact_set,
        drafts=tuple(drafts),
        cross_verification=cross,
        status=status,
    )
