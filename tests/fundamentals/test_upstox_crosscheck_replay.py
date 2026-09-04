"""``upstox-crosscheck`` keeps the bodies it fetched, and can be re-run from them.

Lane B's sweep is a live measurement: every re-run costs authenticated requests
against a rate-limited vendor, and until the bodies are kept nobody can ask a
second question of the same responses. Retention plus replay is what turns one
sweep into a re-readable artifact, and what lets an offline harness reproduce a
run's counts without touching the wire.

These tests are RED at HEAD by design. The contracts they pin, in the shape the
command already uses (paths as keyword arguments, ``args`` carrying only the
basis):

* ``fundamentals.ingest.upstox_crosscheck`` exists and exports the pure seam —
  ``compare_company``, ``ScreenerSection``, ``CompanyCrosscheck``,
  ``CompanyStatus``, ``CrosscheckRunReport`` and ``COMPARED_SECTIONS``;
* a live run writes ``<out-dir>/upstox/<symbol>/<basis>/<surface>.raw.json``
  and ``<surface>.meta.json``, before the body is interpreted;
* ``run_upstox_crosscheck_command`` takes a keyword-only
  ``upstox_root: Path | None = None`` that ``dispatch_upstox_crosscheck_command``
  fills from a new ``--upstox-root`` flag.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, NoReturn

import pytest
from tests.fundamentals.upstox_fixtures import (
    SCREENER_PERIODS,
    SCREENER_SECTION_ROWS,
    STATEMENT_SURFACES,
    StubSource,
    screener_root,
    statement_bodies,
    statement_fetch,
)

from fundamentals.api.cli import _configure_logging
from fundamentals.api.upstox_crosscheck_cli import (
    EXIT_OK,
    EXIT_UNREADABLE,
    REPORT_FILENAME,
    SUMMARY_HEADER,
    UPSTOX_CROSSCHECK_COMMAND,
    add_upstox_crosscheck_parser,
    dispatch_upstox_crosscheck_command,
    read_retained_bodies,
    run_upstox_crosscheck_command,
)
from fundamentals.ingest.upstox_source import (
    DEFAULT_ROUTE_KEY,
    UpstoxFetch,
    UpstoxRoute,
    UpstoxSurface,
)
from fundamentals.ingest.upstox_statements import (
    BalanceSheetDocument,
    CashFlowDocument,
    IncomeStatementDocument,
    StatementBasis,
    read_balance_sheet,
    read_cash_flow,
    read_income_statement,
)

# Real check digits: TITAN and NETWEB, both listed. Used as identifiers only.
TITAN_ISIN = "INE280A01028"
NETWEB_ISIN = "INE0NT901020"

RETENTION_DIRNAME = "upstox"
BASIS = StatementBasis.STANDALONE
# The config a run reads when no ``--triage-config`` is given, which is what
# ``_live_run`` drives the command with.
DEFAULT_TRIAGE_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "laneb_triage.yaml"

# A body that no reader can interpret: the envelope itself is wrong, so the
# document comes back SCHEMA_DRIFT and the company is UPSTOX_UNREADABLE.
UNREADABLE_BODY: dict[str, Any] = {"status": "error", "data": {}}


class RaisingSource:
    """A transport that must never be asked anything once a replay root is given."""

    def fetch(
        self,
        route: UpstoxRoute,
        query: Mapping[str, str] | None = None,
        **params: str,
    ) -> UpstoxFetch:
        raise AssertionError(f"replay fetched {route.surface.value}")

    def redact(self, text: str) -> str:
        return text


def _refusing_credentials() -> NoReturn:
    """A credentials factory that fails the test if a replay ever calls it."""
    raise AssertionError("replay asked for upstox credentials")


def _isin_file(tmp_path: Path, *pairs: tuple[str, str], name: str = "isins.tsv") -> Path:
    path = tmp_path / name
    path.write_text("".join(f"{isin}\t{symbol}\n" for isin, symbol in pairs), encoding="utf-8")
    return path


def _args(**kwargs: object) -> argparse.Namespace:
    defaults: dict[str, object] = {"basis": BASIS.value}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def _replay_args(*, isin_file: Path, screener: Path, out_dir: Path, upstox_root: Path) -> Any:
    """Parse a replay invocation through the command's own parser."""
    parser = argparse.ArgumentParser()
    add_upstox_crosscheck_parser(parser.add_subparsers(dest="command"))
    return parser.parse_args(
        [
            UPSTOX_CROSSCHECK_COMMAND,
            "--isin-file",
            str(isin_file),
            "--screener-root",
            str(screener),
            "--out-dir",
            str(out_dir),
            "--basis",
            BASIS.value,
            "--upstox-root",
            str(upstox_root),
        ]
    )


def _live_run(
    *,
    isin_file: Path,
    screener: Path,
    out_dir: Path,
    bodies: dict[UpstoxSurface, dict[str, Any]] | None = None,
) -> Any:
    """One live-style run over the stub transport, which is what retains bodies."""
    return run_upstox_crosscheck_command(
        _args(),
        isin_file=isin_file,
        screener_root=screener,
        out_dir=out_dir,
        source=StubSource(bodies if bodies is not None else statement_bodies(BASIS.value)),
    )


def _retained(out_dir: Path, symbol: str) -> Path:
    return out_dir / RETENTION_DIRNAME / symbol / BASIS.value


def _report(out_dir: Path) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads((out_dir / REPORT_FILENAME).read_text(encoding="utf-8"))
    return payload


def _documents() -> tuple[IncomeStatementDocument, BalanceSheetDocument, CashFlowDocument]:
    """The three parsed documents the same bodies produce, with no file involved."""
    bodies = statement_bodies(BASIS.value)
    return (
        read_income_statement(
            statement_fetch(
                bodies[UpstoxSurface.INCOME_STATEMENT], surface=UpstoxSurface.INCOME_STATEMENT
            ),
            requested_basis=BASIS,
        ),
        read_balance_sheet(
            statement_fetch(
                bodies[UpstoxSurface.BALANCE_SHEET], surface=UpstoxSurface.BALANCE_SHEET
            ),
            requested_basis=BASIS,
        ),
        read_cash_flow(
            statement_fetch(bodies[UpstoxSurface.CASH_FLOW], surface=UpstoxSurface.CASH_FLOW),
            requested_basis=BASIS,
        ),
    )


def _section_payload(section: str) -> dict[str, Any]:
    """One section as the narrow model reads it, built in memory rather than read."""
    return {
        "periods": [
            {"index": index, "label": label} for index, label in enumerate(SCREENER_PERIODS)
        ],
        "rows": [
            {
                "label": label,
                "cells": [
                    {"period_index": index, "value": text, "published": True}
                    for index, text in enumerate(texts)
                ],
            }
            for label, texts in SCREENER_SECTION_ROWS[section]
        ],
    }


def test_compare_company_is_the_comparison_the_command_performs(tmp_path: Path) -> None:
    """A-01: the pure seam, called on in-memory inputs, is what the CLI reports.

    The command annotates every compared row with its triage class and relative
    difference (step 5(c)) before writing the report, so the seam is compared
    after the same annotation pass. What A-01 pins is that the *comparison* is
    identical, not that the command reports it unannotated.
    """
    from fundamentals.ingest.upstox_crosscheck import (
        COMPARED_SECTIONS,
        CrosscheckRunReport,
        ScreenerSection,
        compare_company,
    )
    from fundamentals.verify.laneb_triage import load_triage_config, triage_run

    income, balance, cash = _documents()
    pure = compare_company(
        isin=TITAN_ISIN,
        symbol="TITAN",
        basis=BASIS,
        sections={
            section: ScreenerSection.model_validate(_section_payload(section))
            for section in COMPARED_SECTIONS
        },
        income=income,
        balance=balance,
        cash=cash,
    )
    run = _live_run(
        isin_file=_isin_file(tmp_path, (TITAN_ISIN, "TITAN")),
        screener=screener_root(tmp_path, "TITAN", BASIS.value),
        out_dir=tmp_path / "out",
    )
    annotated = triage_run(
        CrosscheckRunReport(companies=(pure,)), load_triage_config(DEFAULT_TRIAGE_CONFIG_PATH)
    )
    assert annotated.companies[0].model_dump() == run.companies[0].model_dump()


def test_a_live_run_retains_every_body_verbatim_beside_its_meta(tmp_path: Path) -> None:
    """A-02: the bytes on disk are the bytes served, and the meta covers them."""
    out_dir = tmp_path / "out"
    _live_run(
        isin_file=_isin_file(tmp_path, (TITAN_ISIN, "TITAN")),
        screener=screener_root(tmp_path, "TITAN", BASIS.value),
        out_dir=out_dir,
    )
    bodies = statement_bodies(BASIS.value)
    for surface in STATEMENT_SURFACES:
        capture = statement_fetch(bodies[surface], surface=surface).capture
        raw = (_retained(out_dir, "TITAN") / f"{surface.value}.raw.json").read_bytes()
        assert raw == statement_fetch(bodies[surface], surface=surface).raw_body
        meta = json.loads(
            (_retained(out_dir, "TITAN") / f"{surface.value}.meta.json").read_text(encoding="utf-8")
        )
        assert meta["content_sha256"] == hashlib.sha256(raw).hexdigest()
        assert meta["byte_count"] == len(raw)
        assert meta["source_url"] == capture.request_url
        assert meta["route_key"] == DEFAULT_ROUTE_KEY
        assert datetime.fromisoformat(meta["retrieved_at"]) == capture.retrieved_at


def test_a_body_the_reader_refuses_is_retained_all_the_same(tmp_path: Path) -> None:
    """A-02: retention happens before interpretation, or drift is unstudiable."""
    out_dir = tmp_path / "out"
    bodies = statement_bodies(BASIS.value)
    bodies[UpstoxSurface.BALANCE_SHEET] = UNREADABLE_BODY
    run = _live_run(
        isin_file=_isin_file(tmp_path, (TITAN_ISIN, "TITAN")),
        screener=screener_root(tmp_path, "TITAN", BASIS.value),
        out_dir=out_dir,
        bodies=bodies,
    )
    assert run.companies[0].status.value == "UPSTOX_UNREADABLE"
    raw = _retained(out_dir, "TITAN") / f"{UpstoxSurface.BALANCE_SHEET.value}.raw.json"
    assert raw.read_bytes() == json.dumps(UNREADABLE_BODY).encode("utf-8")


def test_a_replay_reproduces_the_live_comparison_without_fetching(tmp_path: Path) -> None:
    """A-03: same companies, same outcomes, and the transport is never asked."""
    isin_file = _isin_file(tmp_path, (TITAN_ISIN, "TITAN"))
    screener = screener_root(tmp_path, "TITAN", BASIS.value)
    live_out = tmp_path / "live"
    live = _live_run(isin_file=isin_file, screener=screener, out_dir=live_out)
    replay = run_upstox_crosscheck_command(
        _args(),
        isin_file=isin_file,
        screener_root=screener,
        out_dir=tmp_path / "replay",
        source=RaisingSource(),
        upstox_root=live_out / RETENTION_DIRNAME,
    )
    assert [company.model_dump() for company in replay.companies] == [
        company.model_dump() for company in live.companies
    ]


def test_a_replayed_document_carries_the_capture_the_live_run_recorded(tmp_path: Path) -> None:
    """A-03: the document is bound to the fetch that produced it, not to the replay.

    Every Lane B document carries the hash, URL and retrieval time of the
    response it was read from, and a replayed one must carry the live ones. A
    replay that restamped them would silently re-date the evidence, and the
    retained bytes would no longer be traceable to the request that got them.
    """
    live_out = tmp_path / "live"
    _live_run(
        isin_file=_isin_file(tmp_path, (TITAN_ISIN, "TITAN")),
        screener=screener_root(tmp_path, "TITAN", BASIS.value),
        out_dir=live_out,
    )
    bodies = read_retained_bodies(_retained(live_out, "TITAN"))
    assert bodies is not None
    replayed = read_cash_flow(bodies[UpstoxSurface.CASH_FLOW], requested_basis=BASIS)
    live = read_cash_flow(
        statement_fetch(
            statement_bodies(BASIS.value)[UpstoxSurface.CASH_FLOW],
            surface=UpstoxSurface.CASH_FLOW,
        ),
        requested_basis=BASIS,
    )
    assert (replayed.retrieved_at, replayed.source_url, replayed.content_sha256) == (
        live.retrieved_at,
        live.source_url,
        live.content_sha256,
    )


def test_a_replay_never_asks_for_upstox_credentials(tmp_path: Path) -> None:
    """A-03: ``--upstox-root`` and live fetching are exclusive, before the token."""
    isin_file = _isin_file(tmp_path, (TITAN_ISIN, "TITAN"))
    screener = screener_root(tmp_path, "TITAN", BASIS.value)
    live_out = tmp_path / "live"
    _live_run(isin_file=isin_file, screener=screener, out_dir=live_out)
    replay_out = tmp_path / "replay"
    code = dispatch_upstox_crosscheck_command(
        _replay_args(
            isin_file=isin_file,
            screener=screener,
            out_dir=replay_out,
            upstox_root=live_out / RETENTION_DIRNAME,
        ),
        credentials_factory=_refusing_credentials,
    )
    assert code == EXIT_OK
    assert _report(replay_out)["companies"][0]["status"] == "COMPARED"


def test_a_retained_body_that_contradicts_its_hash_is_refused(tmp_path: Path) -> None:
    """A-03: a replayed body is only evidence while its recorded hash still holds.

    The tampering here is a restated number in an otherwise untouched body: it
    parses, it compares, and every outcome it produces looks ordinary. Nothing
    but the recorded hash separates it from the bytes the vendor served, so a
    run that dropped the check would publish a clean report over evidence that
    is no longer the evidence. The refusal must also leave no report behind —
    an artifact written from bodies this run could not vouch for is the outcome
    the check exists to prevent.
    """
    isin_file = _isin_file(tmp_path, (TITAN_ISIN, "TITAN"))
    screener = screener_root(tmp_path, "TITAN", BASIS.value)
    live_out = tmp_path / "live"
    _live_run(isin_file=isin_file, screener=screener, out_dir=live_out)
    tampered = _retained(live_out, "TITAN") / f"{UpstoxSurface.CASH_FLOW.value}.raw.json"
    body = json.loads(tampered.read_text(encoding="utf-8"))
    body["data"]["cash_flow"][0]["history"][0]["value"] = 56.0
    tampered.write_bytes(json.dumps(body).encode("utf-8"))
    replay_out = tmp_path / "replay"
    code = dispatch_upstox_crosscheck_command(
        _replay_args(
            isin_file=isin_file,
            screener=screener,
            out_dir=replay_out,
            upstox_root=live_out / RETENTION_DIRNAME,
        ),
        credentials_factory=_refusing_credentials,
    )
    assert code == EXIT_UNREADABLE
    assert not (replay_out / REPORT_FILENAME).exists()


def test_a_company_with_no_retained_body_is_skipped_and_the_run_continues(
    tmp_path: Path,
) -> None:
    """A-03: a gap in the retention tree is recorded, not fatal to the run."""
    screener = screener_root(tmp_path, "TITAN", BASIS.value)
    screener_root(tmp_path, "NETWEB", BASIS.value)
    live_out = tmp_path / "live"
    _live_run(
        isin_file=_isin_file(tmp_path, (TITAN_ISIN, "TITAN"), name="one.tsv"),
        screener=screener,
        out_dir=live_out,
    )
    replay = run_upstox_crosscheck_command(
        _args(),
        isin_file=_isin_file(tmp_path, (TITAN_ISIN, "TITAN"), (NETWEB_ISIN, "NETWEB")),
        screener_root=screener,
        out_dir=tmp_path / "replay",
        source=RaisingSource(),
        upstox_root=live_out / RETENTION_DIRNAME,
    )
    assert [company.status.value for company in replay.companies] == [
        "COMPARED",
        "SKIPPED_NO_UPSTOX_DATA",
    ]


def test_the_report_says_whether_it_was_replayed_or_retained(tmp_path: Path) -> None:
    """A-04: a reader of the artifact can tell a replay from a live run."""
    isin_file = _isin_file(tmp_path, (TITAN_ISIN, "TITAN"))
    screener = screener_root(tmp_path, "TITAN", BASIS.value)
    live_out = tmp_path / "live"
    _live_run(isin_file=isin_file, screener=screener, out_dir=live_out)
    assert _report(live_out)["upstox_root"] is None
    assert _report(live_out)["retained_under"] == str(live_out / RETENTION_DIRNAME)

    replay_out = tmp_path / "replay"
    dispatch_upstox_crosscheck_command(
        _replay_args(
            isin_file=isin_file,
            screener=screener,
            out_dir=replay_out,
            upstox_root=live_out / RETENTION_DIRNAME,
        ),
        credentials_factory=_refusing_credentials,
    )
    assert _report(replay_out)["upstox_root"] == str(live_out / RETENTION_DIRNAME)
    assert _report(replay_out)["retained_under"] is None


def test_the_summary_and_exit_code_are_unchanged_on_both_paths(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A-05: retention and replay add columns to nothing and change no code.

    ``main`` routes structlog to stderr before it dispatches anything, so the
    command's diagnostics never share stdout with the artifact. This test enters
    at the dispatcher instead, and so has to do the same — otherwise it would be
    asserting against a logging configuration the product never runs under.
    """
    _configure_logging()
    isin_file = _isin_file(tmp_path, (TITAN_ISIN, "TITAN"))
    screener = screener_root(tmp_path, "TITAN", BASIS.value)
    live_out = tmp_path / "live"
    live = _live_run(isin_file=isin_file, screener=screener, out_dir=live_out)
    assert live.exit_code == EXIT_OK
    assert live.render().splitlines()[0] == SUMMARY_HEADER

    code = dispatch_upstox_crosscheck_command(
        _replay_args(
            isin_file=isin_file,
            screener=screener,
            out_dir=tmp_path / "replay",
            upstox_root=live_out / RETENTION_DIRNAME,
        ),
        credentials_factory=_refusing_credentials,
    )
    assert code == EXIT_OK
    assert capsys.readouterr().out.splitlines()[0] == SUMMARY_HEADER


def test_an_unreadable_body_exits_three_on_both_paths(tmp_path: Path) -> None:
    """A-05: replaying a drifted body reaches the same verdict the live run did."""
    isin_file = _isin_file(tmp_path, (TITAN_ISIN, "TITAN"))
    screener = screener_root(tmp_path, "TITAN", BASIS.value)
    bodies = statement_bodies(BASIS.value)
    bodies[UpstoxSurface.INCOME_STATEMENT] = UNREADABLE_BODY
    live_out = tmp_path / "live"
    live = _live_run(isin_file=isin_file, screener=screener, out_dir=live_out, bodies=bodies)
    assert live.exit_code == EXIT_UNREADABLE

    code = dispatch_upstox_crosscheck_command(
        _replay_args(
            isin_file=isin_file,
            screener=screener,
            out_dir=tmp_path / "replay",
            upstox_root=live_out / RETENTION_DIRNAME,
        ),
        credentials_factory=_refusing_credentials,
    )
    assert code == EXIT_UNREADABLE
