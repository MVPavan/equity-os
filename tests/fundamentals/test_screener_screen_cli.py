"""The ``screener-screen`` publication contract and its refusals.

Everything here is about what reaches disk, what reaches stdout, and what exit
code the caller sees. The transport seam and the synthetic bodies live in
:mod:`screener_screen_support`; nothing in this file opens a socket or reads a
captured page.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import screener_screen_support as support
from structlog.testing import capture_logs

from fundamentals.api.cli import main
from fundamentals.api.screener_cli_dispatch import (
    EXIT_BASIS_UNAVAILABLE,
    EXIT_OK,
    EXIT_REFUSED,
)
from fundamentals.ingest.screener_session_models import ScreenerRateLimitedError

# Three queries chosen for what the frozen default-path algorithm does to them:
# one it leaves whole, one longer than the 48-character excerpt whose separators
# are single spaces (so truncating before or after the substitution gives the
# same answer, and the test pins the rule rather than an ordering the plan does
# not fix), and one with no ``[a-z0-9]`` at all, which must fall back.
_PLAIN_QUERY = support.QUERY
_PLAIN_EXCERPT = "alpha-ratio-11-and-beta-score-3"
_LONG_QUERY = "alphabetical ratio measured over the beta score threshold gamma"
_LONG_EXCERPT = "alphabetical-ratio-measured-over-the-beta-score"
_UNNAMEABLE_QUERY = ">= < > =="
_FALLBACK_EXCERPT = "query"

_DEFAULT_ROOT = ("data", "raw", "screener-screen")

# Flags this command does not have. Each names something the slice deliberately
# does not control, and argparse must refuse it rather than let it be ignored:
# a caller who passes --limit and is silently served 50 rows a page has been
# told nothing, and a caller who passes --stock is on the wrong command.
_FORBIDDEN_FLAGS = ("--stock", "--basis", "--config", "--sort", "--order", "--source", "--limit")


def _default_directory_name(excerpt: str, query: str) -> str:
    """The directory name the default output path is contracted to derive."""
    return f"{excerpt}-{hashlib.sha256(query.encode('utf-8')).hexdigest()[:12]}"


def _created_directory(monkeypatch: pytest.MonkeyPatch, query: str) -> tuple[Path, list[str]]:
    """Run without ``--out`` and return the first directory the run tried to create."""
    with monkeypatch.context() as patcher:
        requested = support.serve(patcher, support.walk(2))
        support.intercept_first_creation(patcher)
        with pytest.raises(support.FirstCreationError) as excinfo:
            main([support.COMMAND, "--query", query])
    created = excinfo.value.path
    directory = created.parent if created.name == support.PAGES_DIRNAME else created
    return directory, requested.urls


def test_the_command_bounds_its_flags_prints_two_tsv_lines_and_exits_by_outcome(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """SL3-13: the flags, the default path, the two output lines and the exits are the contract.

    ``--max-pages`` is bounded at both ends by argparse, before Pydantic sees it,
    because 25 sits below the ~40-request boundary this account was rate-limited
    at and a caller must not be able to talk the run past it — nor accidentally
    fall below it, which is why the default is asserted by walking to it rather
    than by reading it back. The two TSV lines are what a shell loop reads, so
    they carry admitted pages — not every body retained — beside the absolute
    artifact path. The default output path has to be derivable by the caller
    without opening the artifact, and it must never be the query itself: the
    excerpt makes the directory findable, the digest keeps two similar or
    identically truncated queries apart, and the exact query stays in the
    artifact and out of the logs. And this command has no stock and no basis: the
    shared dispatch log must branch on the command rather than dereference
    namespace attributes that do not exist, or every invocation dies with an
    ``AttributeError`` before the first request.
    """
    for bad in ("0", "26", "abc"):
        with monkeypatch.context() as patcher:
            requested = support.serve(patcher, support.walk(2))
            with pytest.raises(SystemExit) as excinfo:
                main([support.COMMAND, "--query", support.QUERY, "--max-pages", bad])
            assert excinfo.value.code == EXIT_REFUSED
            assert requested.urls == []

    for flag in _FORBIDDEN_FLAGS:
        with monkeypatch.context() as patcher:
            requested = support.serve(patcher, support.walk(2))
            with pytest.raises(SystemExit) as excinfo:
                main([support.COMMAND, "--query", support.QUERY, flag, "anything"])
            assert excinfo.value.code == EXIT_REFUSED
            assert requested.urls == []

    with monkeypatch.context() as patcher:
        with capture_logs() as logs:
            exit_code, out_dir, _ = support.run_cli(
                patcher, tmp_path, support.walk(2), "--max-pages", "25"
            )
        assert exit_code == EXIT_OK
        assert capsys.readouterr().out.splitlines() == [
            support.TSV_HEADER,
            f"results\t2\t16\t6\t{support.artifact_of(out_dir).resolve()}",
        ]
        invoked = next(entry for entry in logs if entry["event"] == "screener_command_invoked")
        # The whole record, not a probe for two absent keys: a log line that
        # dereferences ``args.stock`` on this namespace does not log a wrong
        # value, it raises before the first request.
        assert set(invoked) == {"event", "log_level", "command", "started_at"}
        assert invoked["command"] == support.COMMAND
        assert all(support.QUERY not in str(value) for entry in logs for value in entry.values())

    # No --max-pages at all, against a query offering one more page than the
    # bound: the walk must stop at 25 of its own accord.
    with monkeypatch.context() as patcher:
        default_code, default_dir, recorder = support.run_cli(
            patcher, tmp_path, support.walk(26), out_dir=tmp_path / "default-bound"
        )
        assert default_code == EXIT_REFUSED
        assert [support.requested_page(url) for url in recorder.urls] == list(range(1, 26))
        assert capsys.readouterr().out.splitlines() == [
            support.TSV_HEADER,
            f"incomplete\t25\t200\t6\t{support.artifact_of(default_dir).resolve()}",
        ]

    for query, excerpt in (
        (_PLAIN_QUERY, _PLAIN_EXCERPT),
        (_LONG_QUERY, _LONG_EXCERPT),
        (_UNNAMEABLE_QUERY, _FALLBACK_EXCERPT),
    ):
        directory, urls = _created_directory(monkeypatch, query)
        assert directory.is_absolute()
        assert directory.parts[-4:] == (*_DEFAULT_ROOT, _default_directory_name(excerpt, query))
        assert not directory.exists()
        assert urls == []

    with monkeypatch.context() as patcher:
        capped, _, _ = support.run_cli(
            patcher, tmp_path / "capped", support.walk(2), "--max-pages", "1"
        )
        assert capped == EXIT_REFUSED

    # A refusal on the very first request leaves nothing to publish, so it
    # propagates — and still exits by outcome rather than as a traceback.
    with monkeypatch.context() as patcher:
        first_page_refused, _, requested = support.run_cli(
            patcher,
            tmp_path,
            support.walk(2),
            refusals={1: ScreenerRateLimitedError("screener refused")},
            out_dir=tmp_path / "refused",
        )
        assert first_page_refused == EXIT_REFUSED
        assert len(requested.urls) == 1
        assert not support.artifact_of(tmp_path / "refused").exists()

    with monkeypatch.context() as patcher:
        requested = support.serve(patcher, support.walk(2))
        refused = main(
            [
                support.COMMAND,
                "--query",
                "   ",
                "--out",
                str(tmp_path / "blank"),
            ]
        )
        assert refused == EXIT_REFUSED
        assert requested.urls == []
        assert "ScreenQueryError" in capsys.readouterr().err

    # No cookie is a local configuration fault, not an answer from the host: it
    # names the variable and exits 1 (a string ``SystemExit`` is exit 1), which
    # is the code a caller must not confuse with a refusal.
    with monkeypatch.context() as patcher:
        requested = support.serve(patcher, support.walk(2))
        patcher.delenv(support.SESSION_ENV, raising=False)
        with pytest.raises(SystemExit) as excinfo:
            main([support.COMMAND, "--query", support.QUERY, "--out", str(tmp_path / "nocookie")])
        assert excinfo.value.code not in (EXIT_OK, EXIT_REFUSED, EXIT_BASIS_UNAVAILABLE)
        assert support.SESSION_ENV in str(excinfo.value.code)
        assert requested.urls == []

    # Nothing this command can produce is a basis question, so exit 3 is
    # unreachable and must never be borrowed for another meaning.
    assert EXIT_BASIS_UNAVAILABLE not in {exit_code, default_code, capped, refused}


def test_pages_are_written_into_a_safe_directory_and_verified_before_the_artifact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """SL3-15: the artifact is the completion marker, so it is written last.

    No-clobber protects a file that already exists; it does nothing about the
    directory holding it, so a planted ``pages`` symlink would send every
    retained body somewhere the caller never named while each write succeeded.
    Every knowable target is refused before the first request, because refusing
    afterwards spends a scarce request budget to discard the result. And when a
    write does fail part-way, rollback removes only what this invocation created
    — unlinking by name would turn a no-clobber refusal into another process's
    evidence loss.

    The publication *order* is asserted from the writer's own calls rather than
    from the directory afterwards, because the finished directory cannot tell
    "the artifact came last" from "the artifact came first and was rolled back",
    and those two differ exactly when it matters: a reader that finds the
    artifact finds a run whose evidence is already on disk.
    """
    unsafe = tmp_path / "unsafe"
    unsafe.mkdir()
    (tmp_path / "elsewhere").mkdir()
    (unsafe / support.PAGES_DIRNAME).symlink_to(tmp_path / "elsewhere")
    with monkeypatch.context() as patcher:
        requested = support.serve(patcher, support.walk(2))
        with pytest.raises(SystemExit):
            main([support.COMMAND, "--query", support.QUERY, "--out", str(unsafe)])
        assert requested.urls == []

    occupied = tmp_path / "occupied"
    occupied.mkdir()
    support.artifact_of(occupied).write_text("{}", encoding="utf-8")
    with monkeypatch.context() as patcher:
        requested = support.serve(patcher, support.walk(2))
        with pytest.raises(SystemExit) as excinfo:
            main([support.COMMAND, "--query", support.QUERY, "--out", str(occupied)])
        assert "refusing to overwrite" in str(excinfo.value)
        assert requested.urls == []

    with monkeypatch.context() as patcher:
        created = support.record_publications(patcher)
        exit_code, out_dir, _ = support.run_cli(patcher, tmp_path, support.walk(2))
        assert exit_code == EXIT_OK
        assert created == [
            support.page_file(out_dir, 1),
            support.page_file(out_dir, 2),
            support.artifact_of(out_dir),
        ]
        payload = support.payload_of(out_dir)
        pages = support.artifact_pages(payload)
        assert len(pages) == 2
        for position, metadata in enumerate(pages, start=1):
            body = support.page_file(out_dir, position).read_bytes()
            assert hashlib.sha256(body).hexdigest() == metadata["content_sha256"]
            assert metadata["page_number"] == position
        assert support.QUERY in json.dumps(payload)

    # A body this invocation did not write, sitting on the name page two would
    # claim: the write is refused, and rollback must leave it exactly as it is
    # while removing the page this invocation did create.
    contested = tmp_path / "contested"
    (contested / support.PAGES_DIRNAME).mkdir(parents=True)
    foreign = support.page_file(contested, 2)
    foreign.write_bytes(b"<html>another process wrote this</html>")
    with monkeypatch.context() as patcher:
        created = support.record_publications(patcher)
        support.serve(patcher, support.walk(2))
        with pytest.raises(SystemExit):
            main([support.COMMAND, "--query", support.QUERY, "--out", str(contested)])
    assert created == [support.page_file(contested, 1), foreign]
    assert support.artifact_of(contested) not in created
    assert not support.artifact_of(contested).exists()
    assert foreign.read_bytes() == b"<html>another process wrote this</html>"
    assert not support.page_file(contested, 1).exists()
    assert (contested / support.PAGES_DIRNAME).is_dir()
