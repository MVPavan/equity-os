"""Coverage for the ``upstox`` command: what it writes, and what it refuses to write.

The command is an acquisition front end, so the properties worth pinning are
about bytes and paths rather than about analysis. The retained body on disk must
be byte-identical to the one its recorded sha256 covers; no capture may clobber
another; and no token may reach a filename, a log line or a summary.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

import pytest
from upstox_fixtures import (
    NSE_ISIN,
    bse_equity_row,
    gzip_body,
    instruments_fetch,
    nse_equity_row,
    suspended_fetch,
    suspended_row,
)

from fundamentals.api.cli_parser import build_parser
from fundamentals.api.upstox_cli import (
    INSTRUMENTS_SURFACE,
    UPSTOX_COMMAND,
    dispatch_upstox_command,
    run_instruments_command,
)
from fundamentals.ingest.upstox_source import (
    UpstoxFetch,
    UpstoxRoute,
    UpstoxSurface,
)

_TOKEN = "fixture-analytics-token"


class _StubSource:
    """An Upstox source that replays prepared fetches and opens no socket."""

    def __init__(self, *fetches: UpstoxFetch) -> None:
        self._fetches = list(fetches)
        self.routes: list[UpstoxRoute] = []

    def fetch(
        self,
        route: UpstoxRoute,
        query: Mapping[str, str] | None = None,
        **params: str,
    ) -> UpstoxFetch:
        """Record the route and return the next prepared fetch."""
        del query, params
        self.routes.append(route)
        return self._fetches.pop(0)

    def redact(self, text: str) -> str:
        """Strip the synthetic token, as the real source does."""
        return text.replace(_TOKEN, "[redacted-secret]")


def _listed() -> UpstoxFetch:
    """A complete-instruments fetch over two synthetic equity rows."""
    return instruments_fetch([nse_equity_row(), bse_equity_row()])


def _capture_dir(out_dir: Path) -> Path:
    """The one capture directory the run wrote under ``out_dir``."""
    captures = sorted(path for path in out_dir.rglob("*_meta.json"))
    assert len(captures) == 1
    return captures[0].parent


def test_the_run_writes_the_four_artifacts_of_one_capture(tmp_path: Path) -> None:
    """Raw bytes, the capture record, the parsed catalog, and the review section."""
    run_instruments_command(tmp_path, source=_StubSource(_listed()))
    written = {path.name for path in _capture_dir(tmp_path).iterdir()}
    assert written == {
        "upstox_instruments.raw.json.gz",
        "upstox_instruments_meta.json",
        "upstox_instruments.parsed.json",
        "review.json",
    }


def test_the_retained_body_is_byte_identical_to_its_recorded_hash(tmp_path: Path) -> None:
    """The bytes on disk are the bytes the sha256 covers, with nothing in between.

    Written through the no-clobber byte writer rather than a decode-and-re-encode,
    because our own hash over the raw bytes is the only restatement detector this
    vendor's responses allow.
    """
    fetch = _listed()
    run_instruments_command(tmp_path, source=_StubSource(fetch))
    directory = _capture_dir(tmp_path)
    on_disk = (directory / "upstox_instruments.raw.json.gz").read_bytes()
    meta = json.loads((directory / "upstox_instruments_meta.json").read_text(encoding="utf-8"))
    assert on_disk == fetch.raw_body
    assert meta["content_sha256"] == hashlib.sha256(on_disk).hexdigest()


def test_the_parsed_catalog_round_trips_into_the_entity_adapter(tmp_path: Path) -> None:
    """The artifact this slice exists to produce is the one the entity map reads."""
    from fundamentals.entity.upstox_entity_source import load_upstox_records

    run_instruments_command(tmp_path, source=_StubSource(_listed()))
    parsed = _capture_dir(tmp_path) / "upstox_instruments.parsed.json"
    records = load_upstox_records(parsed)
    assert {record.assertions[0].value for record in records} >= {NSE_ISIN}


def test_the_review_artifact_carries_the_unknown_key_census(tmp_path: Path) -> None:
    """Vendor drift is written where a human will find it, not into a log line."""
    fetch = instruments_fetch([nse_equity_row(new_vendor_field="x")])
    run_instruments_command(tmp_path, source=_StubSource(fetch))
    review = json.loads((_capture_dir(tmp_path) / "review.json").read_text(encoding="utf-8"))
    assert review["unknown_keys"] == [["new_vendor_field", 1]]
    assert review["outcome"] == "OK"


def test_a_second_capture_of_identical_bytes_never_clobbers_the_first(
    tmp_path: Path,
) -> None:
    """Append-only holds as a filesystem property: the capture id carries the hash."""
    from datetime import UTC, datetime

    from upstox_fixtures import fetch_of

    rows = [nse_equity_row()]
    run_instruments_command(tmp_path, source=_StubSource(instruments_fetch(rows)))
    later = fetch_of(gzip_body(rows), retrieved_at=datetime(2027, 1, 1, tzinfo=UTC))
    run_instruments_command(tmp_path, source=_StubSource(later))
    assert len(sorted(tmp_path.rglob("*_meta.json"))) == 2


def test_no_pipe_reaches_a_filename(tmp_path: Path) -> None:
    """``instrument_key`` holds a pipe; a path component built from one would not."""
    run_instruments_command(tmp_path, source=_StubSource(_listed()))
    assert all("|" not in str(path) for path in tmp_path.rglob("*"))


def test_a_drifted_catalog_is_still_written_and_reported_as_refused(tmp_path: Path) -> None:
    """Unreadable bytes are retained, because a reviewed parser can re-read them."""
    corrupt = instruments_fetch([nse_equity_row()])
    broken = UpstoxFetch(raw_body=b"\x1f\x8b\x08\x00 not a gzip", capture=corrupt.capture)
    result = run_instruments_command(tmp_path, source=_StubSource(broken))
    assert result.outcome_value == "SCHEMA_DRIFT"
    directory = _capture_dir(tmp_path)
    assert (directory / "upstox_instruments.raw.json.gz").read_bytes() == broken.raw_body
    review = json.loads((directory / "review.json").read_text(encoding="utf-8"))
    assert review["anomalies"]


def test_the_suspended_file_is_fetched_only_when_asked(tmp_path: Path) -> None:
    """It has no code consumer, so acquiring it is an explicit decision each run."""
    source = _StubSource(_listed())
    run_instruments_command(tmp_path, source=source)
    assert [route.route_key for route in source.routes] == ["complete"]


def test_the_suspended_file_is_written_as_its_own_capture(tmp_path: Path) -> None:
    """Retained evidence of suspension, kept beside the listed catalog, not merged."""
    source = _StubSource(_listed(), suspended_fetch([suspended_row()]))
    run_instruments_command(tmp_path, source=source, include_suspended=True)
    assert [route.route_key for route in source.routes] == ["complete", "suspended"]
    assert len(sorted(tmp_path.rglob("upstox_suspended*_meta.json"))) == 1


def test_the_summary_names_the_counts_and_never_the_token(tmp_path: Path) -> None:
    """A run summary is read by a human and pasted into issues; it carries no secret."""
    result = run_instruments_command(tmp_path, source=_StubSource(_listed()))
    summary = result.render()
    assert _TOKEN not in summary
    assert "2" in summary


# --- argument wiring --------------------------------------------------------


def test_the_command_is_registered_on_the_parser() -> None:
    """The command exists on the shared parser, not only in its own module."""
    args = build_parser().parse_args(
        [UPSTOX_COMMAND, "--surface", INSTRUMENTS_SURFACE, "--out", "/tmp/x"]
    )
    assert args.command == UPSTOX_COMMAND
    assert args.surface == INSTRUMENTS_SURFACE


def test_an_unimplemented_surface_is_refused_by_the_parser() -> None:
    """A surface with no reader yet is not offered, so no run half-executes one."""
    with pytest.raises(SystemExit):
        build_parser().parse_args([UPSTOX_COMMAND, "--surface", "candles", "--out", "/tmp/x"])


def test_the_dispatcher_ignores_every_other_command() -> None:
    """Dispatch returns ``None`` for a command it does not own, as its siblings do."""
    namespace = argparse.Namespace(command="entity-map")
    assert dispatch_upstox_command(namespace, credentials_factory=lambda: None) is None


def test_every_surface_the_parser_offers_has_a_reader() -> None:
    """A choice the parser accepts and the runner cannot serve would be a dead flag."""
    assert INSTRUMENTS_SURFACE == UpstoxSurface.INSTRUMENTS.value


def test_the_entity_map_build_takes_the_catalog_only_when_asked() -> None:
    """D8: the map's inputs change when someone asks, and not before.

    A default-on flag would silently alter every existing build's inputs, and a
    published identity map is the wrong place to discover a new source.
    """
    args = build_parser().parse_args(
        ["entity-map", "build", "--artifact", "a.json", "--config", "c.yaml", "--out", "o"]
    )
    assert args.upstox_catalog is None
    wired = build_parser().parse_args(
        [
            "entity-map",
            "build",
            "--artifact",
            "a.json",
            "--config",
            "c.yaml",
            "--out",
            "o",
            "--upstox-catalog",
            "cat.json",
        ]
    )
    assert wired.upstox_catalog == "cat.json"


def test_the_gzip_fixture_really_is_gzip() -> None:
    """Guard the fixture itself: a plain-JSON fixture would make the decode vacuous."""
    assert gzip.decompress(gzip_body([nse_equity_row()])).startswith(b"[")
