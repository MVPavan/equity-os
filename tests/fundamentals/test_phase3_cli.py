"""Acceptance tests for the ``three-source-crosscheck`` command (Phase 3, S6).

The seam is ``fundamentals.api.three_source_cli``: the composition root that
resolves one watchlist stock, reads the three offline sides (the XBRL spine out
of gold, the retained Screener sections, the retained Tijori capture), hands
them to the S5 comparator and turns the result into one JSON report, one
tab-separated summary and one exit code.

What these tests protect is the boundary between a measurement and a claim. The
output is evidence somebody will quote, so an amount must not leave the process
unless it was asked for (``--include-values``), a report must never overwrite an
earlier one, an input this repo could not read must outrank any number of
disagreements, and an absent Tijori side must read as MISSING rather than as a
failure — otherwise the first partial measurement, which runs with no Tijori
bodies at all, would look like a broken command.

Nothing here fetches: the Tijori page is retained through a real
``SnapshotStore`` with the transport patched at the committed envelope seam, the
Screener sections are round-tripped through their own validator before they are
written, and the watchlist is loaded through the real config loader. Every
figure, symbol and date is synthetic. The command module is imported at call
time, after each test's fixtures are built, so collection stays green and a red
test is the missing seam rather than a broken fixture.
"""

from __future__ import annotations

import ast
import hashlib
import json
import urllib.request
from collections.abc import Iterator, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr

from fundamentals.api.cli import _configure_logging, main
from fundamentals.api.cli_parser import build_parser
from fundamentals.api.watchlist_config import load_watchlist_config
from fundamentals.contracts.acquisition_outcome import OutcomeCode
from fundamentals.contracts.observation import AccountingFramework, PeriodType, Scope
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.ingest.screener_financials_models import (
    Cell,
    FinancialsMetadata,
    Period,
    PeriodKind,
    RowStatus,
    Section,
    SectionOutcome,
    SectionTable,
    TableRow,
    Unit,
)
from fundamentals.ingest.screener_session_models import Basis
from fundamentals.ingest.tijori_capture import PageEnvelope
from fundamentals.ingest.tijori_source import TijoriCredentials, TijoriSource, TijoriSourceConfig
from fundamentals.reconcile.agreement import AgreementStatus, SourceValue
from fundamentals.reconcile.gold_file import (
    GOLD_SCHEMA_VERSION,
    GoldFact,
    GoldFile,
    canonical_json,
    gold_file_path,
)
from fundamentals.store.snapshot_store import SnapshotStore
from fundamentals.verify.comparison_key import ComparisonKey
from fundamentals.verify.three_source_map import (
    BASIC_EPS_CONTINUING_AND_DISCONTINUED,
    MAP_VERSION,
    PROFIT_ATTRIBUTABLE_TO_OWNERS,
    PROFIT_BEFORE_TAX,
    PROFIT_LOSS_FOR_PERIOD,
    REVENUE_FROM_OPERATIONS,
)

COMMAND = "three-source-crosscheck"
SYMBOL, SLUG, COMPANY_ID = "TITAN", "titan-company-limited", 81
SESSION_VALUE, MEDIA_TYPE = "fixture-session-token", "text/html; charset=utf-8"
SCREENER_SOURCE_ID, XBRL_SOURCE_ID = "screener-subscriber", "nse-indas-xbrl-consolidated"
CRORE_UNIT, PER_SHARE_UNIT, CRORE_SCALE = "INR crore", "INR per share", 10**7
QUARTER = "FY27Q4"

# The quarter every side is asked for, the quarter before it, and a year end
# only the annual profit-loss table carries.
QUARTER_END, PRIOR_END, ANNUAL_END = date(2027, 3, 31), date(2026, 12, 31), date(2026, 3, 31)
FETCHED_AT = datetime(2027, 4, 20, 9, 30, tzinfo=UTC)

# The Tijori fixture publishes its latest quarter as "Mar 2025"; every test
# restates it in the synthetic quarter the other two sides are stated in.
FIXTURE_LABEL, SYNTHETIC_LABEL = b"Mar 2025", b"Mar 2027"
SECOND_CAPTURE_MARK = b"<!-- second synthetic capture of the same page -->"

# The fixture's own consolidated quarterly figures, in crore, and its EPS.
SALES, PBT, NET_PROFIT, EPS = Decimal("17000"), Decimal("1300"), Decimal("950"), Decimal("11.80")
SALES_TEXT, NET_PROFIT_TEXT, EPS_TEXT = "17000", "950", "11.80"
PRIOR_SALES_TEXT, PRIOR_PROFIT_TEXT, PRIOR_EPS_TEXT = "16000", "880", "9.90"
SIGN_FLIPPED_SALES_TEXT = "-17000"

XBRL_DECIMALS, EPS_DECIMALS = -5, 2
REPORT_FILENAME = "three_source_report.json"
REDACTED_LABEL = "<redacted>"
SUMMARY_COLUMNS = ("concept", "xbrl_screener", "xbrl_tijori", "screener_tijori", "triage")

EXIT_OK, EXIT_WARN, EXIT_REFUSED, EXIT_UNREADABLE = 0, 1, 2, 3

CRORE_CONCEPTS: tuple[tuple[str, Decimal], ...] = (
    (REVENUE_FROM_OPERATIONS, SALES),
    (PROFIT_BEFORE_TAX, PBT),
    (PROFIT_LOSS_FOR_PERIOD, NET_PROFIT),
    (PROFIT_ATTRIBUTABLE_TO_OWNERS, NET_PROFIT),
)

WATCHLIST_YAML = f"""
raw_dir: "synthetic-raw"
stocks:
  - name: "Synthetic Fixture Company Ltd"
    domain: "Fixture"
    identifiers:
      nse_symbol: "{SYMBOL}"
      bse_scrip: "500999"
      screener_slug: "{SYMBOL}"
      screener_company_id: 991001
      screener_warehouse_id_consolidated: 992001
      screener_warehouse_id_standalone: 992002
      tijori_slug: "{SLUG}"
      tijori_company_id: {COMPANY_ID}
    quarter:
      label: "{QUARTER}"
      period_start: "2027-01-01"
      period_end: "{QUARTER_END.isoformat()}"
      knowledge_cutoff: "2027-04-20T00:00:00Z"
"""

_RowSpec = tuple[str, Unit, tuple[str, ...]]


@pytest.fixture(autouse=True)
def _stderr_logging() -> None:
    """Route structlog to stderr before any store publish, exactly as ``main`` does.

    A capture is retained before ``main`` runs, and structlog's default logger
    writes to stdout; without this the stdout assertions depend on test order.
    """
    _configure_logging()


def _repo_root() -> Path:
    """The checkout root, found by its marker file rather than a fixed depth."""
    here = Path(__file__).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise AssertionError("no pyproject.toml above this test file")


def _command_module() -> Any:
    """The S6 command seam, imported at call time so collection stays green."""
    return import_module("fundamentals.api.three_source_cli")


def _fixture_page() -> bytes:
    """The committed synthetic Tijori page, restated in the synthetic quarter."""
    fixtures = _repo_root() / "tests" / "fundamentals" / "fixtures"
    page = (fixtures / "synthetic_tijori_financials.html").read_bytes()
    assert page.count(FIXTURE_LABEL) == 1, "the fixture's latest quarter moved"
    return page.replace(FIXTURE_LABEL, SYNTHETIC_LABEL)


def _section_table(
    section: Section, ends: Sequence[date], rows: Sequence[_RowSpec]
) -> SectionTable:
    """One synthetic Screener section, built through the real section models."""
    table_id = f"{section.value}-data-table"
    digest = hashlib.sha256(section.value.encode("utf-8")).hexdigest()
    periods = tuple(
        Period(
            index=index,
            label=end.strftime("%b %Y"),
            kind=PeriodKind.DATE,
            date_key=end.isoformat(),
            period_end=end,
        )
        for index, end in enumerate(ends)
    )
    table_rows = tuple(
        TableRow(
            position=position,
            label=label,
            status=RowStatus.MODELED,
            unit=unit,
            cells=tuple(
                Cell(
                    period_index=index,
                    value=Decimal(raw_text),
                    raw_text=raw_text,
                    published=True,
                    provenance=Provenance(
                        source_id=SCREENER_SOURCE_ID,
                        file_sha256=digest,
                        retrieved_at=FETCHED_AT,
                        anchor_type=SourceAnchorType.HTML_TABLE,
                        table_id=table_id,
                        row_path=label,
                        column_label=periods[index].label,
                        column_index=index,
                    ),
                )
                for index, raw_text in enumerate(raw_texts)
            ),
        )
        for position, (label, unit, raw_texts) in enumerate(rows)
    )
    return SectionTable(
        section=section,
        table_id=table_id,
        outcome=SectionOutcome.OK,
        unit_statement="Consolidated Figures in Rs. Crores",
        periods=periods,
        rows=table_rows,
    )


def _tables(sales_text: str) -> tuple[SectionTable, SectionTable]:
    """The quarterly table, and an annual one carrying the same quarter-end column."""
    quarterly: tuple[_RowSpec, ...] = (
        ("Sales", Unit.RS_CRORE, (PRIOR_SALES_TEXT, sales_text)),
        ("Net Profit", Unit.RS_CRORE, (PRIOR_PROFIT_TEXT, NET_PROFIT_TEXT)),
        ("EPS in Rs", Unit.RUPEES, (PRIOR_EPS_TEXT, EPS_TEXT)),
    )
    annual: tuple[_RowSpec, ...] = (("Net Profit", Unit.RS_CRORE, ("3400", "3600")),)
    return (
        _section_table(Section.QUARTERS, (PRIOR_END, QUARTER_END), quarterly),
        _section_table(Section.PROFIT_LOSS, (ANNUAL_END, QUARTER_END), annual),
    )


def _metadata(symbol: str = SYMBOL) -> FinancialsMetadata:
    """The provenance record written beside one acquisition's sections."""
    return FinancialsMetadata(
        source_id=SCREENER_SOURCE_ID,
        symbol=symbol,
        slug=SLUG,
        basis=Basis.CONSOLIDATED,
        company_id=COMPANY_ID,
        page_url=f"https://example.invalid/company/{symbol}/consolidated/",
        page_sha256=hashlib.sha256(symbol.encode("utf-8")).hexdigest(),
        sections_requested=(Section.QUARTERS, Section.PROFIT_LOSS),
        schedule_families_requested=(),
        schedule_families_fetched=(),
        schedule_families_refused=(),
        schedule_families_unverified=(),
        complete=True,
        verified=True,
        incomplete_reason=None,
        fetched_at=FETCHED_AT,
    )


def _write_screener(root: Path, *, symbol: str = SYMBOL, sales_text: str = SALES_TEXT) -> Path:
    """Write one acquisition's sections and metadata in the Phase 2 layout."""
    directory = root / SYMBOL / Basis.CONSOLIDATED.value
    directory.mkdir(parents=True, exist_ok=True)
    for table in _tables(sales_text):
        payload = table.model_dump(mode="json")
        assert SectionTable.model_validate(payload) == table, "section dump does not round-trip"
        name = f"section_{table.section.value}.json"
        (directory / name).write_text(json.dumps(payload), encoding="utf-8")
    metadata = _metadata(symbol)
    document = json.dumps(metadata.model_dump(mode="json"))
    (directory / "screener_financials_meta.json").write_text(document, encoding="utf-8")
    return root


def _gold_fact(
    concept: str, amount: Decimal, *, decimals: int | None, unit: str, scale: int
) -> GoldFact:
    """One gold fact whose XBRL source value is the spine the command reads."""
    provenance = Provenance(
        source_id=XBRL_SOURCE_ID,
        file_sha256="b" * 64,
        anchor_type=SourceAnchorType.XBRL_CONTEXT,
        context_ref="SyntheticQuarter",
        retrieved_at=FETCHED_AT,
    )
    source_value = SourceValue.model_validate(
        {
            "source_id": XBRL_SOURCE_ID,
            "source_class": "first_party",
            "normalized_value": str(amount),
            "normalized_unit": unit,
            "decimals": decimals,
            "provenance": provenance.model_dump(mode="json"),
        }
    )
    key = ComparisonKey(
        entity_scheme="nse-symbol",
        entity_id=SYMBOL,
        concept_qname=concept,
        period_type=PeriodType.DURATION,
        period_start=date(QUARTER_END.year, 1, 1),
        period_end=QUARTER_END,
        scope=Scope.CONSOLIDATED,
        accounting_basis=AccountingFramework.IND_AS,
        currency="INR",
        unit=unit,
        scale=scale,
    )
    return GoldFact(
        concept_qname=concept,
        comparison_key=key,
        value=str(amount),
        normalized_unit=unit,
        agreement_status=AgreementStatus.SINGLE_FIRST_PARTY,
        agreed_sources=(XBRL_SOURCE_ID,),
        corroborating_sources=(),
        incompatible_sources=(),
        first_party_source_count=1,
        needs_human_review=False,
        source_values=(source_value,),
    )


def _write_gold(gold_dir: Path, *, eps_decimals: int | None = EPS_DECIMALS) -> Path:
    """Write the synthetic spine every registry concept is covered by.

    ``eps_decimals=None`` is the pre-S4 gold this repo already holds: a source
    value that states no precision at all.
    """
    facts = [
        _gold_fact(concept, amount, decimals=XBRL_DECIMALS, unit=CRORE_UNIT, scale=CRORE_SCALE)
        for concept, amount in CRORE_CONCEPTS
    ]
    facts.append(
        _gold_fact(
            BASIC_EPS_CONTINUING_AND_DISCONTINUED,
            EPS,
            decimals=eps_decimals,
            unit=PER_SHARE_UNIT,
            scale=1,
        )
    )
    gold = GoldFile(
        schema_version=GOLD_SCHEMA_VERSION, symbol=SYMBOL, quarter=QUARTER, facts=tuple(facts)
    )
    document = canonical_json(gold)
    assert GoldFile.model_validate_json(document) == gold, "gold dump does not round-trip"
    path = gold_file_path(SYMBOL, QUARTER, gold_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document, encoding="utf-8")
    return gold_dir


def _write_watchlist(tmp_path: Path) -> Path:
    """Write the one-stock synthetic watchlist, proving the loader accepts it."""
    path = tmp_path / "watchlist.yaml"
    path.write_text(WATCHLIST_YAML, encoding="utf-8")
    stock = load_watchlist_config(path).stock(SYMBOL)
    assert stock.quarter.period_end == QUARTER_END
    assert stock.identifiers.tijori_slug == SLUG
    return path


def _retain(monkeypatch: pytest.MonkeyPatch, snapshot_root: Path, page: bytes) -> str:
    """Retain one scripted 200 response and return the capture id it sealed."""

    def envelope(source: TijoriSource, slug: str, credentials: TijoriCredentials) -> PageEnvelope:
        del source, credentials
        assert slug == SLUG
        return PageEnvelope(payload=page, status=200, media_type=MEDIA_TYPE)

    monkeypatch.setattr(TijoriSource, "_fetch_pl_envelope", envelope)
    source = TijoriSource(
        TijoriSourceConfig(
            credentials=TijoriCredentials(session_cookie=SecretStr(SESSION_VALUE)),
            expected_company_id=COMPANY_ID,
            max_retries=1,
        )
    )
    retention = import_module("fundamentals.ingest.tijori_retention").retain_tijori_tables(
        source, SnapshotStore(snapshot_root), slug=SLUG, expected_symbol=SYMBOL
    )
    assert retention.record.outcome.code is OutcomeCode.OK, "the fixture no longer retains OK"
    return str(retention.record.capture_id)


class _Tree:
    """The four input roots and the config path of one synthetic run."""

    def __init__(self, base: Path) -> None:
        """Build the roots without touching the network or the repo's own data."""
        self.config = _write_watchlist(base)
        self.screener_root = base / "screener"
        self.gold_dir = base / "gold"
        self.snapshot_root = base / "snapshots"


def _tree(
    tmp_path: Path,
    *,
    sales_text: str = SALES_TEXT,
    screener_symbol: str = SYMBOL,
    eps_decimals: int | None = EPS_DECIMALS,
) -> _Tree:
    """One complete synthetic input tree, with no Tijori capture retained yet."""
    tree = _Tree(tmp_path)
    _write_screener(tree.screener_root, symbol=screener_symbol, sales_text=sales_text)
    _write_gold(tree.gold_dir, eps_decimals=eps_decimals)
    return tree


def _argv(
    tree: _Tree,
    out_dir: Path,
    *,
    include_values: bool = False,
    warn_exit: bool = False,
    capture_id: str | None = None,
    snapshot_root: Path | None = None,
) -> list[str]:
    """The full argument vector for one ``three-source-crosscheck`` run."""
    argv = [
        COMMAND,
        "--stock",
        SYMBOL,
        "--config",
        str(tree.config),
        "--screener-root",
        str(tree.screener_root),
        "--gold-dir",
        str(tree.gold_dir),
        "--snapshot-root",
        str(snapshot_root if snapshot_root is not None else tree.snapshot_root),
        "--out-dir",
        str(out_dir),
    ]
    if include_values:
        argv.append("--include-values")
    if warn_exit:
        argv.append("--warn-exit")
    if capture_id is not None:
        argv.extend(["--capture-id", capture_id])
    return argv


def _report(out_dir: Path) -> dict[str, Any]:
    """The report one run wrote, parsed."""
    payload: dict[str, Any] = json.loads((out_dir / REPORT_FILENAME).read_text("utf-8"))
    return payload


def _sides(payload: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Every side value the report carries, on the rows and inside the pairs."""
    for row in payload["rows"]:
        for key in ("xbrl", "screener", "tijori"):
            if row[key] is not None:
                yield row[key]
        for pair in row["pairs"]:
            for key in ("left", "right"):
                if pair[key] is not None:
                    yield pair[key]


def _pairs(payload: dict[str, Any], left: str, right: str) -> list[dict[str, Any]]:
    """Every pair in the report joining the two named sides."""
    return [
        pair
        for row in payload["rows"]
        for pair in row["pairs"]
        if (pair["left_side"], pair["right_side"]) == (left, right)
    ]


def _forbid_fetching(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any outbound attempt an error, so 'never fetches' is provable."""

    def refuse(*args: object, **kwargs: object) -> Any:
        raise AssertionError("the command attempted a fetch while reading retained inputs")

    monkeypatch.setattr(urllib.request, "build_opener", refuse)
    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr(urllib.request.AbstractHTTPHandler, "do_open", refuse)


def test_full_triple_runs_and_writes_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A complete triple exits 0, reports counts, and states no amount on stdout.

    This is the shape the first measurement is read out of, so two things have
    to hold at once. The report has to name which retained capture the Tijori
    side came from — a measurement quoting a vendor without saying which
    retained bytes it read cannot be re-derived by anyone. And the default run
    must publish no figure: the vendor bodies are private-use only, so counts
    and outcomes travel, raw amounts do not until ``--include-values`` asks.
    """
    tree = _tree(tmp_path)
    capture_id = _retain(monkeypatch, tree.snapshot_root, _fixture_page())
    module = _command_module()
    _forbid_fetching(monkeypatch)
    out_dir = tmp_path / "out"

    assert main(_argv(tree, out_dir)) == EXIT_OK

    captured = capsys.readouterr()
    payload = _report(out_dir)
    assert payload["symbol"] == SYMBOL
    assert payload["period_end"] == QUARTER_END.isoformat()
    assert payload["map_version"] == MAP_VERSION
    assert payload["capture_ids"] == [capture_id]
    assert payload["warn"] is False
    assert sum(payload["counts"].values()) == 3 * len(payload["rows"])
    assert [row["concept_qname"] for row in payload["rows"]] == sorted(
        row["concept_qname"] for row in payload["rows"]
    )

    for side in _sides(payload):
        assert side["amount"] is None
        assert side["raw_label"] == REDACTED_LABEL

    lines = captured.out.splitlines()
    assert lines[0].split("\t") == list(SUMMARY_COLUMNS)
    assert len(lines) == len(payload["rows"]) + 2
    assert [line.split("\t")[0] for line in lines[1:-1]] == [
        row["concept_qname"] for row in payload["rows"]
    ]
    assert "warn" in lines[-1]
    assert SALES_TEXT not in captured.out

    run = module.run_three_source_command(
        build_parser().parse_args(_argv(tree, tmp_path / "second-out")),
        config_path=tree.config,
        screener_root=tree.screener_root,
        gold_dir=tree.gold_dir,
        snapshot_root=tree.snapshot_root,
        out_dir=tmp_path / "second-out",
    )
    assert run.tijori_capture_id == capture_id
    assert run.warn_count == 0
    assert run.report_path == tmp_path / "second-out" / REPORT_FILENAME
    assert run.report_path.is_file()
    assert module.render_three_source_summary(run).strip() == captured.out.strip()


def test_include_values_puts_amounts_in_report_and_stdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--include-values`` is the only way a raw amount leaves the process.

    The flag has to actually carry the figures through, or the operator
    investigating a listed row reaches for the vendor page again. Redaction is
    therefore a projection of the report, not a second comparison: the same run,
    asked for values, states the figures its sides were built from.
    """
    tree = _tree(tmp_path)
    _retain(monkeypatch, tree.snapshot_root, _fixture_page())
    _command_module()
    out_dir = tmp_path / "out"

    assert main(_argv(tree, out_dir, include_values=True)) == EXIT_OK

    captured = capsys.readouterr()
    payload = _report(out_dir)
    amounts = {Decimal(side["amount"]) for side in _sides(payload)}
    labels = {side["raw_label"] for side in _sides(payload)}
    assert SALES in amounts
    assert NET_PROFIT in amounts
    assert REDACTED_LABEL not in labels
    assert {"Sales", "Net Sales", "Net Profit"} <= labels
    assert SALES_TEXT in captured.out


def test_no_tijori_capture_is_missing_not_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An absent Tijori side is reported as MISSING, never as a failed run.

    The approved first measurement runs before any Tijori body has been
    acquired, so this is the normal case, not a degraded one. A command that
    failed here would either be worked around with a flag or read as though the
    XBRL-to-Screener comparison had not happened — and that comparison is the
    entire content of Part 1 of the measurement.
    """
    tree = _tree(tmp_path)
    _command_module()
    out_dir = tmp_path / "out"

    assert main(_argv(tree, out_dir, snapshot_root=tmp_path / "empty-snapshots")) == EXIT_OK

    payload = _report(out_dir)
    assert payload["capture_ids"] == []
    tijori_pairs = _pairs(payload, "xbrl", "tijori")
    assert tijori_pairs != []
    assert {pair["outcome"] for pair in tijori_pairs} == {"MISSING_RIGHT"}
    assert all(row["tijori"] is None for row in payload["rows"])
    assert len(capsys.readouterr().out.splitlines()) == len(payload["rows"]) + 2


def test_warn_exit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A disagreement is non-zero only when the operator opts in, exactly as in Lane B.

    The measured base rate for this comparison is zero runs old: nothing yet
    says how often a real filing and a vendor page differ. A command that failed
    by default on an unmeasured rate would be switched off within a week, taking
    the telemetry with it. ``--warn-exit`` exists for the operator's own manual
    runs, where a non-zero exit is the point.
    """
    tree = _tree(tmp_path, sales_text=SIGN_FLIPPED_SALES_TEXT)
    _retain(monkeypatch, tree.snapshot_root, _fixture_page())
    _command_module()

    silent_dir = tmp_path / "silent"
    assert main(_argv(tree, silent_dir)) == EXIT_OK
    payload = _report(silent_dir)
    assert payload["warn"] is True

    assert main(_argv(tree, tmp_path / "flagged", warn_exit=True)) == EXIT_WARN


def test_unreadable_outranks_warn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An input this repo could not read wins over any number of disagreements.

    A gold source value with no ``decimals`` states no precision, so every
    tolerance derived from it would be invented — and an invented tolerance
    manufactures agreement. That is a stronger statement than a warn: the
    comparison did not happen. Exiting 1 here would let the run be read as a
    completed measurement that merely found something.
    """
    tree = _tree(tmp_path, sales_text=SIGN_FLIPPED_SALES_TEXT, eps_decimals=None)
    _retain(monkeypatch, tree.snapshot_root, _fixture_page())
    _command_module()
    out_dir = tmp_path / "out"

    assert main(_argv(tree, out_dir, warn_exit=True)) == EXIT_UNREADABLE
    assert not (out_dir / REPORT_FILENAME).exists()


def test_identity_mismatch_is_unreadable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sections whose own metadata names another company stop the run.

    A directory name is a filing convention, not evidence. Reading one issuer's
    figures against another's XBRL spine and publishing the result as a
    measurement is the worst outcome this command has, so it is refused with the
    same code as any other unreadable input rather than compared and warned on.
    """
    tree = _tree(tmp_path, screener_symbol="OTHERCO")
    _retain(monkeypatch, tree.snapshot_root, _fixture_page())
    _command_module()
    out_dir = tmp_path / "out"

    assert main(_argv(tree, out_dir)) == EXIT_UNREADABLE
    assert not (out_dir / REPORT_FILENAME).exists()


def test_report_path_refuses_overwrite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A second run into the same directory refuses rather than replacing evidence.

    Every other acquisition command in this repo writes no-clobber, and a
    measurement report is exactly the artifact that must not be silently
    rewritten: the numbers quoted in the research doc must still be readable
    beside it. This is a store refusal, not an unreadable input, so it carries
    the store's own exit code.
    """
    tree = _tree(tmp_path)
    _retain(monkeypatch, tree.snapshot_root, _fixture_page())
    _command_module()
    out_dir = tmp_path / "out"

    assert main(_argv(tree, out_dir)) == EXIT_OK
    first = (out_dir / REPORT_FILENAME).read_bytes()

    assert main(_argv(tree, out_dir)) == EXIT_REFUSED
    assert (out_dir / REPORT_FILENAME).read_bytes() == first


def test_capture_id_selects_named_capture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The Tijori side is pinnable, and unpinned it is the newest OK capture.

    Two captures of one page are the normal state after a re-acquisition, and
    which one a published number came from must be the operator's decision, not
    directory order. Defaulting to the newest makes an unpinned re-run reproduce
    the vendor's current page; ``--capture-id`` makes an older measurement
    re-derivable from the bytes it actually read.
    """
    tree = _tree(tmp_path)
    older = _retain(monkeypatch, tree.snapshot_root, _fixture_page())
    newer = _retain(monkeypatch, tree.snapshot_root, _fixture_page() + SECOND_CAPTURE_MARK)
    assert older != newer
    assert older < newer, "capture ids must sort oldest first"
    _command_module()

    pinned_dir = tmp_path / "pinned"
    assert main(_argv(tree, pinned_dir, capture_id=older)) == EXIT_OK
    assert _report(pinned_dir)["capture_ids"] == [older]

    default_dir = tmp_path / "default"
    assert main(_argv(tree, default_dir)) == EXIT_OK
    assert _report(default_dir)["capture_ids"] == [newer]


def test_exit_codes_match_lane_b() -> None:
    """The four exit codes are the ones every sibling command already means.

    An operator loops this command over ten stocks and branches on its status;
    a 2 that meant "unreadable" here and "refused" everywhere else would make
    that loop wrong in the one case it exists to catch. The constants are
    declared locally rather than imported so a Tijori/Screener command does not
    depend on an Upstox module — which is exactly why their equality needs a
    test rather than an import to hold.
    """
    module = _command_module()
    upstox = import_module("fundamentals.ingest.upstox_crosscheck")
    screener = import_module("fundamentals.api.screener_cli_dispatch")

    assert (module.EXIT_OK, upstox.EXIT_OK) == (EXIT_OK, EXIT_OK)
    assert (module.EXIT_WARN, upstox.EXIT_WARN) == (EXIT_WARN, EXIT_WARN)
    assert (module.EXIT_UNREADABLE, upstox.EXIT_UNREADABLE) == (EXIT_UNREADABLE,) * 2
    assert (module.EXIT_REFUSED, screener.EXIT_REFUSED) == (EXIT_REFUSED, EXIT_REFUSED)

    source = _repo_root() / "src" / "fundamentals" / "api" / "three_source_cli.py"
    parsed = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    imported: set[str] = set()
    for node in ast.walk(parsed):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    assert not any(name.startswith("fundamentals.ingest.upstox") for name in imported)


def test_command_is_wired() -> None:
    """The command is reachable from the composition root, not only importable.

    A dispatcher nobody registered is dead code that every test can still
    exercise directly, so the wiring is what this pins: the shared parser offers
    the subcommand, and ``main`` serves its help through argparse's own exit
    rather than falling through to another command's branch.
    """
    module = _command_module()
    assert module.THREE_SOURCE_COMMAND == COMMAND

    parsed = build_parser().parse_args(
        [COMMAND, "--stock", SYMBOL, "--out-dir", "out", "--include-values", "--warn-exit"]
    )
    assert parsed.command == COMMAND
    assert parsed.stock == SYMBOL
    assert (parsed.include_values, parsed.warn_exit) == (True, True)
    assert parsed.capture_id is None
    assert parsed.basis == "consolidated"

    with pytest.raises(SystemExit) as exit_info:
        main([COMMAND, "--help"])
    assert exit_info.value.code == 0
