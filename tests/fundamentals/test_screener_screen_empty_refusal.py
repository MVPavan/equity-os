"""Typed refusals retain screen evidence even without a displayable message."""

from __future__ import annotations

import hashlib
from typing import Any

import pytest
import screener_screen_support as support

from fundamentals.ingest import screener_screen
from fundamentals.ingest.screener_screen_models import ScreenOutcome, ScreenStructureError
from fundamentals.ingest.screener_session_models import (
    ScreenerBlockedError,
    ScreenerDocumentFetch,
    ScreenerSessionError,
)


@pytest.mark.parametrize("detail", ["", " \t\n", "  host refused  "])
@pytest.mark.parametrize("refusal", [ScreenerSessionError, ScreenerBlockedError])
def test_typed_fetch_refusal_retains_admitted_evidence_and_original_detail(
    monkeypatch: pytest.MonkeyPatch, detail: str, refusal: type[ScreenerSessionError]
) -> None:
    """A missing summary cannot discard a captured page or rewrite native provenance."""
    bodies = support.walk(2)
    run, recorder = support.acquire(monkeypatch, bodies, refusals={2: refusal(detail)})
    artifact = run.artifact
    assert artifact.outcome is ScreenOutcome.INCOMPLETE
    assert artifact.incomplete_reason and artifact.incomplete_reason.strip()
    if detail.strip():
        assert artifact.incomplete_reason == detail
    else:
        assert refusal.__name__ in artifact.incomplete_reason
    assert [support.requested_page(url) for url in recorder.urls] == [1, 2]
    assert len(artifact.columns) == 6
    assert [row.serial_number for row in artifact.rows] == list(range(1, 9))
    assert artifact.rows[0].company.data_row_company_id == 770001
    assert artifact.rows[0].cells[0].raw_text == "10.25"
    assert len(artifact.pages) == len(run.documents) == 1
    raw = bodies[1].encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    assert run.documents[0].raw_body == raw
    assert run.documents[0].content_sha256 == digest
    assert artifact.pages[0].page_number == 1
    assert artifact.pages[0].content_sha256 == digest
    assert artifact.pages[0].byte_count == len(raw)
    assert artifact.pages[0].offered_pages == (1, 2)
    assert (artifact.pages[0].stated_total, artifact.pages[0].stated_pages) == (16, 2)
    assert artifact.failure is not None
    assert artifact.failure.refusal == refusal.__name__
    assert artifact.failure.detail == detail
    assert artifact.failure.page_number == 2
    assert artifact.failure.source_url == recorder.urls[1]
    assert artifact.failure.content_sha256 is None
    assert (artifact.failure.stated_total, artifact.failure.stated_pages) == (None, None)


@pytest.mark.parametrize("detail", ["", " \t\n"])
def test_typed_read_refusal_retains_unadmitted_body_and_admitted_rows(
    monkeypatch: pytest.MonkeyPatch, detail: str
) -> None:
    """A read refusal keeps the failing response alongside earlier admitted evidence."""
    read_table = screener_screen.read_screen_table

    def refuse_second_page(root: Any, *, fetch: ScreenerDocumentFetch, page_number: int) -> Any:
        """Inject a typed read refusal only after the second response is retained."""
        if page_number == 2:
            raise ScreenStructureError(detail)
        return read_table(root, fetch=fetch, page_number=page_number)

    monkeypatch.setattr(screener_screen, "read_screen_table", refuse_second_page)
    bodies = support.walk(2)
    run, _ = support.acquire(monkeypatch, bodies)
    artifact = run.artifact
    assert artifact.outcome is ScreenOutcome.INCOMPLETE
    assert artifact.incomplete_reason and artifact.incomplete_reason.strip()
    assert "ScreenStructureError" in artifact.incomplete_reason
    assert [row.serial_number for row in artifact.rows] == list(range(1, 9))
    assert [page.page_number for page in artifact.pages] == [1]
    assert [document.raw_body for document in run.documents] == [
        bodies[1].encode("utf-8"),
        bodies[2].encode("utf-8"),
    ]
    assert artifact.failure is not None
    assert artifact.failure.refusal == "ScreenStructureError"
    assert artifact.failure.detail == detail
    assert artifact.failure.page_number == 2
    assert artifact.failure.content_sha256 == hashlib.sha256(bodies[2].encode("utf-8")).hexdigest()
    assert (artifact.failure.stated_total, artifact.failure.stated_pages) == (16, 2)


@pytest.mark.parametrize("detail", ["", " \t\n", "host refused"])
def test_refusal_before_any_response_raises_the_original_exception(
    monkeypatch: pytest.MonkeyPatch, detail: str
) -> None:
    """Without retained bytes there is no evidence from which to build an artifact."""
    error = ScreenerBlockedError(detail)
    recorder = support.serve(monkeypatch, {}, refusals={1: error})
    with pytest.raises(ScreenerBlockedError) as caught:
        screener_screen.acquire_screen(
            support.QUERY,
            source=support.source(),
            config=support.models.ScreenAcquisitionConfig(),
        )
    assert caught.value is error
    assert str(caught.value) == detail
    assert [support.requested_page(url) for url in recorder.urls] == [1]
