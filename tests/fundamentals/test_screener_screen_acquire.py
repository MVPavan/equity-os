"""Slice 3 acquisition contract: the walk, its refusals and the frozen model seam.

Companion to :mod:`test_screener_screen`, which pins how one returned page is
read. This file pins what a multi-page walk produces: the terminality of a block
or an exhausted rate limit, the evidence retained when a walk stops short, and
the published models, enum and error hierarchy every assertion in both files
reads through.

Each test states the requirement id it pins and why that behaviour matters. The
transport seam and the builders live in :mod:`screener_screen_support`.
"""

from __future__ import annotations

import hashlib
import urllib.error
from enum import StrEnum
from pathlib import Path

import pytest
import screener_screen_support as support
from pydantic import ValidationError

from fundamentals.api.cli import main
from fundamentals.api.screener_cli_dispatch import EXIT_REFUSED
from fundamentals.ingest.screener_session_models import (
    SOURCE_ID,
    ScreenerBlockedError,
    ScreenerRateLimitedError,
    ScreenerSessionError,
)

# --------------------------------------------------------------------------
# The frozen models, enum and errors every other test reads through
# --------------------------------------------------------------------------


def test_an_artifact_whose_fields_contradict_its_outcome_cannot_be_built(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL3-12: the outcome and the evidence beside it are one fact, not two.

    Every consumer branches on ``outcome`` and then reads the fields it implies.
    An artifact calling itself ``results`` with no rows, ``zero_results`` while
    carrying them, or ``incomplete`` with nothing naming what is missing is
    readable by that consumer and wrong in a way no field-level bound catches —
    each is a real result silently retitled as a different kind of answer.
    """
    run, _ = support.acquire(monkeypatch, support.walk(1))
    artifact = run.artifact

    outcomes = support.models.ScreenOutcome
    contradictions: tuple[dict[str, object], ...] = (
        {"outcome": outcomes.RESULTS, "columns": (), "rows": ()},
        {"outcome": outcomes.ZERO_RESULTS, "columns": artifact.columns, "rows": artifact.rows},
        {"outcome": outcomes.INCOMPLETE, "incomplete_reason": None, "failure": None},
    )
    for override in contradictions:
        with pytest.raises(ValidationError, match="do not match its outcome"):
            support.rebuilt(artifact, **override)


def test_the_published_models_carry_exactly_the_frozen_fields_bounds_and_refusal_types(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """SL3-11, SL3-12 and SL3-13 all read these models, so the models are pinned here.

    Every other test in this file asserts through them, which means a model that
    silently gained a field, lost a bound, or stopped being frozen would leave
    all of them green. The bounds are the ones that make a wrong value
    impossible to publish rather than merely unlikely: a zero row id, a serial
    below one, a cell claiming a column the header cannot name, a negative byte
    count. And the refusal types have to sit under the session error the CLI
    already catches, or a screen refusal becomes a traceback instead of an exit
    code.
    """
    for name, fields in support.MODEL_FIELDS.items():
        assert set(getattr(support.models, name).model_fields) == fields, name

    outcomes = support.models.ScreenOutcome
    assert issubclass(outcomes, StrEnum)
    assert {member.name: member.value for member in outcomes} == {
        "RESULTS": "results",
        "ZERO_RESULTS": "zero_results",
        "INCOMPLETE": "incomplete",
    }

    base = support.models.ScreenerScreenError
    assert issubclass(base, ScreenerSessionError)
    for name in ("ScreenQueryError", "ScreenStructureError", "ScreenPaginationError"):
        assert issubclass(getattr(support.models, name), base)

    assert support.models.MAX_SCREEN_PAGES == 25
    assert support.models.ScreenAcquisitionConfig().max_pages == 25
    for bound in (0, 26):
        with pytest.raises(ValidationError):
            support.models.ScreenAcquisitionConfig(max_pages=bound)

    body = support.walk(1)[1]
    run, _ = support.acquire(monkeypatch, {1: body})
    artifact = run.artifact
    row = artifact.rows[0]
    cell = row.cells[0]
    metadata = artifact.pages[0]

    assert artifact.source_id == SOURCE_ID == support.SOURCE_ID
    assert metadata.page_number == 1
    assert metadata.source_url == support.models.screen_url(support.QUERY, 1)
    assert metadata.http_status == 200
    assert metadata.byte_count == len(body.encode("utf-8"))
    assert metadata.content_sha256 == support.fetch(body).content_sha256
    assert metadata.fetched_at.tzinfo is not None
    assert metadata.offered_pages == (1,)

    for model, override in (
        (artifact.columns[0], {"index": -1}),
        (cell, {"column_index": 1}),
        (row.company, {"data_row_company_id": 0}),
        (row, {"page_number": 0}),
        (row, {"serial_number": 0}),
        (metadata, {"byte_count": -1}),
    ):
        with pytest.raises(ValidationError):
            support.rebuilt(model, **override)

    for frozen, field, value in (
        (artifact, "query", "another query"),
        (row, "serial_number", 2),
        (cell, "raw_text", "rewritten"),
        (metadata, "http_status", 500),
    ):
        with pytest.raises(ValidationError):
            setattr(frozen, field, value)

    later_empty = support.walk(2)
    later_empty[2] = support.zero_result_page()
    refused, _ = support.acquire(monkeypatch, later_empty)
    failure = refused.artifact.failure
    assert failure is not None
    assert failure.source_url == support.models.screen_url(support.QUERY, 2)
    assert failure.refusal == "ScreenPaginationError"
    assert failure.detail

    artifact_path = tmp_path / support.ARTIFACT_FILENAME
    assert (
        support.models.ScreenerScreenCliRun(run=run, artifact_path=artifact_path).page_paths == ()
    )
    published = support.models.ScreenerScreenCliRun(
        run=run,
        artifact_path=artifact_path,
        page_paths=[support.page_file(tmp_path, 1)],
    )
    assert published.page_paths == (support.page_file(tmp_path, 1),)
    assert published.artifact_path == artifact_path


# --------------------------------------------------------------------------
# Terminal refusals and retained partial evidence
# --------------------------------------------------------------------------


@pytest.mark.parametrize("refusal", [ScreenerRateLimitedError, ScreenerBlockedError])
def test_a_block_or_an_exhausted_rate_limit_stops_the_run_where_it_stands(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    refusal: type[ScreenerSessionError],
) -> None:
    """SL3-11: a refusal is the host's answer, and there is no way around it.

    No later request, no alternate host, no cookie refresh, no delay escalation.
    The two positions differ only in what evidence exists: a refusal on the first
    request leaves nothing to publish and propagates, while one mid-walk leaves
    real pages that stay true and are published as incomplete.
    """
    with monkeypatch.context() as patcher:
        run, recorder = support.acquire(
            patcher, support.walk(3), refusals={2: refusal("screener refused")}
        )
        assert [support.requested_page(url) for url in recorder.urls] == [1, 2]
        assert run.artifact.outcome is support.models.ScreenOutcome.INCOMPLETE
        assert run.artifact.failure is not None
        assert run.artifact.failure.page_number == 2
        assert run.artifact.failure.refusal == refusal.__name__
        # No body came back for that attempt, so there is no hash to record.
        assert run.artifact.failure.content_sha256 is None
        assert len(run.artifact.pages) == 1

    with monkeypatch.context() as patcher:
        recorder = support.serve(
            patcher, support.walk(3), refusals={1: refusal("screener refused")}
        )
        with pytest.raises(refusal):
            support.screen.acquire_screen(
                support.QUERY,
                source=support.source(),
                config=support.models.ScreenAcquisitionConfig(),
            )
        assert len(recorder.urls) == 1

    exit_code, _, _ = support.run_cli(
        monkeypatch, tmp_path, support.walk(3), refusals={2: refusal("screener refused")}
    )
    assert exit_code == EXIT_REFUSED


def test_evidence_already_fetched_is_kept_and_published_as_incomplete(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """SL3-12: a partial result must never read as a smaller result.

    Everything fetched before the stop is retained and still true; what is
    missing is named. The two ways a walk stops short are different facts: a page
    that would not parse leaves a refusal carrying the hash of the body that
    caused it, while the configured page cap is this run's own bound and leaves
    no failure at all — publishing one as the other sends someone looking for a
    site change that never happened. Both are published rather than discarded:
    the artifact records what was admitted, every retained body sits beside it
    including the one that would not parse, and neither the page metadata nor the
    counted output line is inflated by a body no page was admitted for.
    """
    broken_body = support.page(
        support.table_of(
            support.header_row(support.NARROW_LABELS)
            + support.data_row(support.one_row(serial=9, values=("110.25", "12.50")))
        ),
        support.pagination((1, 2), active=2, previous=True),
    )
    malformed = support.walk(2)
    malformed[2] = broken_body

    with monkeypatch.context() as patcher:
        run, _ = support.acquire(patcher, malformed)
        assert run.artifact.outcome is support.models.ScreenOutcome.INCOMPLETE
        assert run.artifact.failure is not None
        assert run.artifact.failure.page_number == 2
        assert run.artifact.failure.refusal == "ScreenStructureError"
        assert run.artifact.failure.content_sha256 == support.fetch(broken_body).content_sha256
        assert len(run.artifact.pages) == 1
        assert len(run.documents) == 2
        assert support.screen_cli.is_incomplete(
            support.models.ScreenerScreenCliRun(
                run=run, artifact_path=tmp_path / support.ARTIFACT_FILENAME
            )
        )

    with monkeypatch.context() as patcher:
        capped, recorder = support.acquire(patcher, support.walk(5), max_pages=3)
        assert [support.requested_page(url) for url in recorder.urls] == [1, 2, 3]
        assert capped.artifact.outcome is support.models.ScreenOutcome.INCOMPLETE
        assert capped.artifact.failure is None
        assert capped.artifact.incomplete_reason is not None
        assert "3" in capped.artifact.incomplete_reason
        assert "4" in capped.artifact.incomplete_reason
        assert len(capped.artifact.pages) == 3

    with monkeypatch.context() as patcher:
        complete, _ = support.acquire(patcher, support.walk(2))
        assert not support.screen_cli.is_incomplete(
            support.models.ScreenerScreenCliRun(
                run=complete, artifact_path=tmp_path / support.ARTIFACT_FILENAME
            )
        )

    exit_code, out_dir, _ = support.run_cli(
        monkeypatch, tmp_path, malformed, out_dir=tmp_path / "malformed"
    )
    assert exit_code == EXIT_REFUSED
    assert capsys.readouterr().out.splitlines() == [
        support.TSV_HEADER,
        f"incomplete\t1\t8\t6\t{support.artifact_of(out_dir).resolve()}",
    ]
    published = support.artifact_body(support.payload_of(out_dir))
    assert published["outcome"] == support.models.ScreenOutcome.INCOMPLETE.value
    assert len(published["rows"]) == 8
    assert published["failure"]["page_number"] == 2
    assert published["failure"]["refusal"] == "ScreenStructureError"
    assert published["failure"]["content_sha256"] == support.fetch(broken_body).content_sha256
    pages = support.artifact_pages(support.payload_of(out_dir))
    assert [metadata["page_number"] for metadata in pages] == [1]
    # Both retained bodies reach disk — the one that would not parse is the
    # evidence the refusal points at — while only the admitted page is described
    # by page metadata, and the counts above never include the other.
    for position in (1, 2):
        body_bytes = support.page_file(out_dir, position).read_bytes()
        assert body_bytes == malformed[position].encode("utf-8")
    assert (
        hashlib.sha256(support.page_file(out_dir, 1).read_bytes()).hexdigest()
        == (pages[0]["content_sha256"])
    )
    assert not support.page_file(out_dir, 3).exists()

    capped_code, capped_dir, _ = support.run_cli(
        monkeypatch, tmp_path, support.walk(5), "--max-pages", "3", out_dir=tmp_path / "capped"
    )
    assert capped_code == EXIT_REFUSED
    assert capsys.readouterr().out.splitlines() == [
        support.TSV_HEADER,
        f"incomplete\t3\t24\t6\t{support.artifact_of(capped_dir).resolve()}",
    ]
    capped_published = support.artifact_body(support.payload_of(capped_dir))
    assert capped_published["failure"] is None
    assert capped_published["incomplete_reason"]
    capped_pages = support.artifact_pages(support.payload_of(capped_dir))
    assert [metadata["page_number"] for metadata in capped_pages] == [1, 2, 3]
    for position, metadata in enumerate(capped_pages, start=1):
        retained = support.page_file(capped_dir, position).read_bytes()
        assert hashlib.sha256(retained).hexdigest() == metadata["content_sha256"]
    assert not support.page_file(capped_dir, 4).exists()


@pytest.mark.parametrize(
    "second_page",
    [
        support.page(
            support.results_table(support.NARROW_LABELS, support.rows_for(2)),
            support.nested_options_pagination(),
        ),
        support.results_page(2, offered=(1, 2)),
    ],
    ids=["successor-replaced-by-page-size-only", "successor-dropped-from-the-offer"],
)
def test_a_page_offered_earlier_in_the_walk_may_not_simply_stop_being_offered(
    monkeypatch: pytest.MonkeyPatch, second_page: str
) -> None:
    """SL3-10b rule 2: the walk must remember what it was promised.

    Page 1 offers ``(1, 2, 3)``. Whatever page 2 then says, page 3 was offered
    and was never fetched, so the run is missing evidence it was told exists.
    The termination check only ever looks at the *current* page's offered set,
    which is why an emptied or shrunken one ends the walk cleanly: verified
    against the implementation, both bodies below publish ``RESULTS`` complete
    after two requests, with nothing recording the third page. The request list
    is asserted beside the outcome because "never fetched page 3" is the defect
    — an implementation that merely probed page 3 and then refused would satisfy
    the outcome and violate the no-probing rule.
    """
    run, recorder = support.acquire(
        monkeypatch, {1: support.results_page(1, offered=(1, 2, 3)), 2: second_page}
    )

    assert [support.requested_page(url) for url in recorder.urls] == [1, 2]
    assert run.artifact.outcome is support.models.ScreenOutcome.INCOMPLETE
    assert run.artifact.failure is not None
    assert run.artifact.failure.refusal == "ScreenPaginationError"


def test_a_body_that_does_not_parse_is_evidence_and_not_a_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL3-16: an unparseable body is the one thing the retention rule exists for.

    A 2xx with an empty body is a real answer from the host — a truncated
    response, a proxy interposing — and it is the answer most worth keeping,
    because nothing else records that it happened. ``parse_document`` raises
    ``lxml.etree.ParserError`` on it, which is not a ``ScreenerSessionError``,
    so it walks straight past the handler that publishes ``INCOMPLETE`` and
    retains the fetch. Verified against the implementation: the walk dies with
    that traceback. It must instead become a typed structure refusal raised
    after the fetch is recorded, like every other body this reader cannot read.
    """
    empty_body = ""
    run, _ = support.acquire(
        monkeypatch, {1: support.results_page(1, offered=(1, 2)), 2: empty_body}
    )

    assert run.artifact.outcome is support.models.ScreenOutcome.INCOMPLETE
    assert run.artifact.failure is not None
    assert run.artifact.failure.page_number == 2
    assert run.artifact.failure.refusal == "ScreenStructureError"
    assert run.artifact.failure.content_sha256 == hashlib.sha256(b"").hexdigest()
    assert len(run.artifact.pages) == 1
    assert len(run.documents) == 2


def test_the_unparseable_body_survives_on_disk_instead_of_being_rolled_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """SL3-16 through the command: the rollback is what destroys the evidence.

    The refusal escaping as an untyped exception is only half the defect. The
    CLI wraps publication in a rollback that unlinks everything the invocation
    wrote and re-raises, so the run ends in a traceback with the one body that
    explains it deleted — the exact outcome the retention rule exists to
    prevent. A refusal the walk itself published is not a publication failure,
    so the artifact and every retained page must still be there afterwards.
    """
    empty_body = ""
    bodies = {1: support.results_page(1, offered=(1, 2)), 2: empty_body}

    exit_code, out_dir, _ = support.run_cli(monkeypatch, tmp_path, bodies)

    assert exit_code == EXIT_REFUSED
    published = support.artifact_body(support.payload_of(out_dir))
    assert published["outcome"] == support.models.ScreenOutcome.INCOMPLETE.value
    assert published["failure"]["page_number"] == 2
    assert support.page_file(out_dir, 2).read_bytes() == b""


def test_the_private_query_never_reaches_a_transport_log_line_or_an_error_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """SL3-17: the screen URL carries the owner's own research, percent-encoded.

    Every other Screener URL this transport fetches is a public route. The screen
    URL is not: its ``query`` parameter is the screen itself, and the CLI already
    keeps it out of the invocation log for that reason. The transport below that
    then puts the whole URL into a 429 warning and interpolates it into the fetch
    refusal that reaches stderr, which hands it to any shell that redirects the
    command's diagnostics. The rest of the URL may stay; the query may not.
    """
    url = support.models.screen_url(support.QUERY, 1)
    arguments = [support.COMMAND, "--query", support.QUERY, "--out", str(tmp_path / "private")]

    with monkeypatch.context() as patcher:
        support.serve_transport_failure(
            patcher, urllib.error.HTTPError(url, 429, "Too Many Requests", None, None)
        )
        assert main(arguments) == EXIT_REFUSED
        logged = capsys.readouterr().err
        assert "screener_session_rate_limited" in logged
        assert support.SELECTOR_QUERY not in logged

    with monkeypatch.context() as patcher:
        support.serve_transport_failure(patcher, urllib.error.URLError("connection reset"))
        assert main(arguments) == EXIT_REFUSED
        logged = capsys.readouterr().err
        assert "ScreenerSessionFetchError" in logged
        assert support.SELECTOR_QUERY not in logged
