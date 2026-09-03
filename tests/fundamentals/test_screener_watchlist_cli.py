"""The ``screener-watchlist`` publication contract and its refusals.

Everything here is about what reaches disk, what reaches stdout and stderr, and
what exit code the caller sees. The transport seam and the synthetic bodies
live in :mod:`screener_watchlist_fixtures`; nothing in this file opens a socket
or reads a captured page.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import screener_screen_support as screen_support
import screener_watchlist_fixtures as fx
from pydantic import SecretStr

from fundamentals.api.cli import main
from fundamentals.api.cli_parser import build_parser
from fundamentals.api.screener_cli_dispatch import EXIT_BASIS_UNAVAILABLE, EXIT_OK, EXIT_REFUSED
from fundamentals.ingest.screener_session_models import ScreenerCredentials

_ROSTER = fx.members()
ARTIFACT_FILENAME = "screener_watchlist.json"
PAGE_FILENAME = "watchlist.raw.html"
EXPORT_FILENAME = "watchlist.raw.csv"
TSV_HEADER = "outcome\trows\tcolumns\tartifact"
_DEFAULT_ROOT = ("data", "raw", "screener-watchlist")

# Flags this command does not have. Each names something the slice deliberately
# does not control, and argparse must refuse it rather than let it be ignored.
_FORBIDDEN_FLAGS = ("--query", "--stock", "--basis", "--max-pages", "--config")


def _run_cli(
    monkeypatch: pytest.MonkeyPatch,
    out_dir: Path,
    *extra: str,
    page: str | None = None,
    export: str | bytes | None = None,
    **options: Any,
) -> tuple[int, fx.Transport]:
    """Run ``fundamentals screener-watchlist`` end to end against the pinned seam."""
    transport = fx.serve(
        monkeypatch,
        page=fx.watchlist_page(_ROSTER) if page is None else page,
        export=fx.export_csv(_ROSTER) if export is None and page is None else export,
        **options,
    )
    exit_code = main([fx.COMMAND, "--out", str(out_dir), *extra])
    return exit_code, transport


def _payload(out_dir: Path) -> dict[str, Any]:
    """The published artifact record of one output directory, parsed."""
    loaded: dict[str, Any] = json.loads((out_dir / ARTIFACT_FILENAME).read_text(encoding="utf-8"))
    return screen_support.artifact_body(loaded)


def test_the_command_bounds_its_flags_and_refuses_before_the_first_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL4-13 / SL4-17: an unaddressable invocation must not spend a request.

    ``--watchlist-id`` is a positive integer or nothing; a zero, a negative or
    a word is a caller defect. The flags of the other Screener commands are
    refused rather than ignored, because a caller passing ``--query`` to this
    command has been told nothing if it silently acquires the default list.
    The accepting shapes are asserted first: without them an unregistered
    command refuses everything and this test proves nothing.
    """
    parser = build_parser()
    assert parser.parse_args([fx.COMMAND]).watchlist_id is None
    assert parser.parse_args([fx.COMMAND, "--watchlist-id", str(fx.WATCHLIST_ID)]).watchlist_id == (
        fx.WATCHLIST_ID
    )

    for bad in ("0", "-1", "abc"):
        with monkeypatch.context() as patcher:
            transport = fx.serve(patcher, page=fx.watchlist_page(_ROSTER), export=None)
            with pytest.raises(SystemExit) as excinfo:
                main([fx.COMMAND, "--watchlist-id", bad])
            assert excinfo.value.code == EXIT_REFUSED
            assert transport.exchanges == []

    for flag in _FORBIDDEN_FLAGS:
        with monkeypatch.context() as patcher:
            transport = fx.serve(patcher, page=fx.watchlist_page(_ROSTER), export=None)
            with pytest.raises(SystemExit) as excinfo:
                main([fx.COMMAND, flag, "anything"])
            assert excinfo.value.code == EXIT_REFUSED
            assert transport.exchanges == []


def test_a_consistent_pair_exits_zero_with_a_two_line_summary_and_an_invocation_log(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The two TSV lines are what a shell loop reads; the exit code is what it branches on.

    The counts are the fixture's, never a literal: the column set is the user's
    configuration. The dispatch log must branch on the command rather than
    dereference ``stock`` and ``basis``, or every invocation dies with an
    ``AttributeError`` before the first request. And nothing this command can
    produce is a basis question, so exit 3 must never be borrowed.
    """
    out_dir = tmp_path / "out"

    exit_code, _ = _run_cli(monkeypatch, out_dir)

    assert exit_code == EXIT_OK
    assert exit_code != EXIT_BASIS_UNAVAILABLE
    captured = capsys.readouterr()
    artifact_path = (out_dir / ARTIFACT_FILENAME).resolve()
    assert captured.out.splitlines() == [
        TSV_HEADER,
        f"results\t{len(_ROSTER)}\t{len(fx.DEFAULT_COLUMNS)}\t{artifact_path}",
    ]
    assert "screener_command_invoked" in captured.err
    assert f"command={fx.COMMAND}" in captured.err
    assert "stock=" not in captured.err
    assert "basis=" not in captured.err


def test_both_bodies_are_retained_verified_and_written_before_the_artifact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """SL4-16: the artifact is the completion marker, so it is written last.

    A reader that finds the artifact must find both bodies already on disk,
    hashing to what the artifact records; a truncated write is a failure, not
    silent evidence. The order is asserted from the writer's own calls because
    the finished directory cannot tell "artifact last" from "artifact first".
    """
    out_dir = tmp_path / "out"
    with monkeypatch.context() as patcher:
        created = screen_support.record_publications(patcher)
        exit_code, _ = _run_cli(patcher, out_dir)

    assert exit_code == EXIT_OK
    assert created == [
        out_dir / PAGE_FILENAME,
        out_dir / EXPORT_FILENAME,
        out_dir / ARTIFACT_FILENAME,
    ]
    record = _payload(out_dir)["cross_check"]
    assert (
        hashlib.sha256((out_dir / PAGE_FILENAME).read_bytes()).hexdigest() == record["html_sha256"]
    )
    assert (
        hashlib.sha256((out_dir / EXPORT_FILENAME).read_bytes()).hexdigest()
        == record["export_sha256"]
    )


def test_a_refused_cross_check_exits_non_zero_and_keeps_both_bodies_beside_the_artifact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """SL4-15 through the command: a refusal the run published is not a publication failure.

    The rollback exists for a write that failed part-way. Applying it to an
    ``INCOMPLETE`` run would delete the one pair of bodies that explains the
    disagreement, which is the outcome the retention rule exists to prevent.
    """
    out_dir = tmp_path / "out"
    member = _ROSTER[0]
    changed = fx.with_member(_ROSTER, member.serial, values=("999.99", *member.values[1:]))

    exit_code, _ = _run_cli(
        monkeypatch, out_dir, page=fx.watchlist_page(_ROSTER), export=fx.export_csv(changed)
    )

    assert exit_code == EXIT_REFUSED
    published = _payload(out_dir)
    assert published["outcome"] == fx.models.WatchlistOutcome.INCOMPLETE.value
    assert published["rows"] == []
    assert (out_dir / PAGE_FILENAME).exists()
    assert (out_dir / EXPORT_FILENAME).exists()
    assert capsys.readouterr().out.splitlines()[0] == TSV_HEADER


def test_a_refusal_on_the_first_request_leaves_nothing_and_exits_by_code(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """SL4-11: a block on the page is the host's answer, reported as one line and exit 2.

    Nothing was retained, so there is nothing to publish — and the operator must
    still see a refusal line rather than a traceback, because a traceback reads
    as a bug in the command rather than a decision by the host.

    "Nothing" includes the output directory. It is created before the first
    request so the caller can learn the default destination without spending
    one, but an empty directory left behind by a run that fetched nothing is
    evidence of a run that produced none — and the next invocation's no-clobber
    preflight would find it and pass.
    """
    out_dir = tmp_path / "refused"

    exit_code, transport = _run_cli(
        monkeypatch,
        out_dir,
        page_error=fx.http_error(fx.WATCHLIST_PAGE_URL, 403, "Forbidden"),
    )

    assert exit_code == EXIT_REFUSED
    assert len(transport.exchanges) == 1
    assert not (out_dir / ARTIFACT_FILENAME).exists()
    assert not out_dir.exists()
    assert "ScreenerBlockedError" in capsys.readouterr().err


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"export_error": fx.http_error(fx.export_url(), 403, "Forbidden")},
        {
            "export_error": ValueError(
                f"Invalid header value b'{fx.SESSION_COOKIE_NAME}={fx.SESSION_TOKEN}; "
                f"{fx.CSRF_COOKIE_NAME}={fx.CSRF_COOKIE_VALUE}'"
            )
        },
    ],
    ids=["published", "export-403", "untyped-error-quoting-the-cookie-header"],
)
def test_no_token_or_cookie_value_reaches_stdout_stderr_or_the_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    options: dict[str, Any],
) -> None:
    """SL4-19 / A20 / SL4-28: the retained page embeds a live CSRF token; nothing else may.

    ``data/raw`` is gitignored, so the raw body is the one sanctioned place for
    the token. A log line, a summary line, a failure detail or an artifact field
    carrying it — or the ``Set-Cookie`` value, or any request header — hands
    owner auth material to whatever the shell redirects diagnostics into.

    The published and blocked paths only prove that this code never *writes* a
    secret. The third case is the one that matters: a message this code did not
    write, quoting the outbound ``Cookie`` header, on the exact path SL4-15
    routes into ``failure.detail`` and stderr.
    """
    out_dir = tmp_path / "out"

    _run_cli(monkeypatch, out_dir, **options)

    captured = capsys.readouterr()
    artifact_text = (out_dir / ARTIFACT_FILENAME).read_text(encoding="utf-8")
    for secret in (fx.CSRF_FORM_TOKEN, fx.CSRF_COOKIE_VALUE, fx.SESSION_TOKEN):
        assert secret not in captured.out
        assert secret not in captured.err
        assert secret not in artifact_text


def test_a_requested_id_that_the_page_does_not_confirm_exits_non_zero_without_posting(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """SL4-17: ``--watchlist-id`` binds both artifacts to one list, or the run refuses.

    A page for another list is a 200 with a form; posting it would export the
    wrong list under the requested id and the two renderings would agree.
    """
    out_dir = tmp_path / "out"

    exit_code, transport = _run_cli(
        monkeypatch,
        out_dir,
        "--watchlist-id",
        str(fx.WATCHLIST_ID),
        page=fx.watchlist_page(_ROSTER, watchlist_id=fx.OTHER_WATCHLIST_ID),
        export=fx.export_csv(_ROSTER),
        page_url=f"{fx.WATCHLIST_PAGE_URL}{fx.WATCHLIST_ID}/",
        export_target=fx.export_url(fx.OTHER_WATCHLIST_ID),
    )

    assert exit_code == EXIT_REFUSED
    assert transport.posts == []
    assert _payload(out_dir)["outcome"] == fx.models.WatchlistOutcome.INCOMPLETE.value


def test_other_offered_watchlists_are_named_on_stderr_and_not_acquired(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """SL4-17 / A18: one invocation, one artifact; the rest of the dropdown is advisory.

    Multi-list acquisition is unobserved and out of scope. An operator who sees
    only the selected list acquired needs to be told the others exist, on stderr,
    where the summary line is not.
    """
    out_dir = tmp_path / "out"

    exit_code, transport = _run_cli(
        monkeypatch,
        out_dir,
        page=fx.watchlist_page(_ROSTER, names=(fx.WATCHLIST_NAME, fx.OTHER_WATCHLIST_NAME)),
        export=fx.export_csv(_ROSTER),
    )

    assert exit_code == EXIT_OK
    assert len(transport.exchanges) == 2
    assert fx.OTHER_WATCHLIST_NAME in capsys.readouterr().err
    assert _payload(out_dir)["watchlist_name"] == fx.WATCHLIST_NAME


def test_a_missing_session_cookie_is_a_configuration_fault_and_not_a_refusal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """No cookie is a local fault: it names the variable and exits 1, spending no request.

    A caller must not confuse it with the host refusing, so it is neither exit
    0 nor exit 2.
    """
    with monkeypatch.context() as patcher:
        transport = fx.serve(patcher, page=fx.watchlist_page(_ROSTER), export=None)
        patcher.delenv(fx.SESSION_ENV, raising=False)
        with pytest.raises(SystemExit) as excinfo:
            main([fx.COMMAND, "--out", str(tmp_path / "nocookie")])

    assert excinfo.value.code not in (EXIT_OK, EXIT_REFUSED, EXIT_BASIS_UNAVAILABLE)
    assert fx.SESSION_ENV in str(excinfo.value.code)
    assert transport.exchanges == []


def test_the_default_output_directory_is_under_the_raw_data_root_and_costs_no_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The default path must be derivable by the caller and resolved before any request.

    Refusing a destination after the fetch spends a scarce request budget to
    discard the result. Under ``data/raw`` it is gitignored, which is what keeps
    the retained page's CSRF token out of any commit.
    """
    with monkeypatch.context() as patcher:
        transport = fx.serve(patcher, page=fx.watchlist_page(_ROSTER), export=None)
        screen_support.intercept_first_creation(patcher)
        with pytest.raises(screen_support.FirstCreationError) as excinfo:
            main([fx.COMMAND])

    created = excinfo.value.path
    assert created.is_absolute()
    parts = created.parts
    assert any(parts[index : index + 3] == _DEFAULT_ROOT for index in range(len(parts)))
    assert not created.exists()
    assert transport.exchanges == []


def test_an_occupied_artifact_path_is_refused_before_the_first_request(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """No-clobber is checked in preflight: a run that would overwrite must not fetch first."""
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / ARTIFACT_FILENAME).write_text("{}", encoding="utf-8")

    with monkeypatch.context() as patcher:
        transport = fx.serve(patcher, page=fx.watchlist_page(_ROSTER), export=None)
        with pytest.raises(SystemExit) as excinfo:
            main([fx.COMMAND, "--out", str(occupied)])

    assert "refusing to overwrite" in str(excinfo.value)
    assert transport.exchanges == []


def test_the_command_module_exposes_the_run_the_summary_and_the_exit_decision(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The dispatcher composes three names; each must mean what the dispatcher assumes.

    ``run_screener_watchlist_command`` returns the published run and its paths;
    the summary is the two TSV lines; ``is_incomplete`` is what turns the
    outcome into exit 2. A summary that said ``complete`` anywhere would name a
    guarantee the slice does not make.
    """
    credentials = ScreenerCredentials(session_cookie=SecretStr(fx.SESSION_TOKEN))
    assert fx.watchlist_cli.SCREENER_WATCHLIST_COMMAND == fx.COMMAND

    fx.serve(monkeypatch, page=fx.watchlist_page(_ROSTER), export=fx.export_csv(_ROSTER))
    published = fx.watchlist_cli.run_screener_watchlist_command(
        argparse.Namespace(watchlist_id=None, out=str(tmp_path / "direct")),
        credentials=credentials,
    )
    summary = fx.watchlist_cli.render_screener_watchlist_summary(published)

    assert published.run.artifact.outcome is fx.models.WatchlistOutcome.RESULTS
    assert published.artifact_path == (tmp_path / "direct" / ARTIFACT_FILENAME).resolve()
    assert summary.splitlines()[0] == TSV_HEADER
    assert summary.splitlines()[1].startswith("results\t")
    assert "complete" not in summary.lower()
    assert fx.watchlist_cli.is_incomplete(published) is False

    member = _ROSTER[0]
    changed = fx.with_member(_ROSTER, member.serial, values=("999.99", *member.values[1:]))
    fx.serve(monkeypatch, page=fx.watchlist_page(_ROSTER), export=fx.export_csv(changed))
    refused = fx.watchlist_cli.run_screener_watchlist_command(
        argparse.Namespace(watchlist_id=None, out=str(tmp_path / "refused")),
        credentials=credentials,
    )

    assert fx.watchlist_cli.is_incomplete(refused) is True
