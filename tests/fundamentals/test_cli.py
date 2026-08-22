"""CLI acceptance tests for ``fundamentals validate`` wave selection.

These exercise the composition root offline against the real ``config/watchlist.yaml``:
a ``--wave`` filter restricts a ``--watchlist`` run to one wave, and a plain
``--watchlist`` run rolls each wave up under its own filename so a cross-wave run
never clobbers another wave's roll-up. The real Wave-1/Wave-2 stocks carry no
committed fixtures, so every source skips (each stock BLOCKED) and no network is
touched — these tests assert *which* stocks are selected and *where* the roll-ups
land, not the per-stock outcome. A ``--wave`` that contradicts ``--symbol`` fails
closed. Thesis wave filtering is exercised end-to-end with faked model clients.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from fundamentals.api.cli import (
    _build_parser,
    main,
    thesis_command,
    validate_command,
)
from fundamentals.api.watchlist_config import Wave
from fundamentals.contracts.observation import AccountingFramework, PeriodType, Scope
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.reconcile.agreement import AgreementStatus, SourceClass, SourceValue
from fundamentals.reconcile.gold_file import GoldFact, GoldFile
from fundamentals.thesis import ModelResponse, ThesisDocumentStatus
from fundamentals.verify.comparison_key import ComparisonKey

_WAVE1_SYMBOLS = {"LAURUSLABS", "MTARTECH", "SONACOMS", "THERMAX", "TITAN"}
_WAVE2_SYMBOLS = {"NETWEB", "HFCL", "POLYCAB", "CGPOWER", "ETERNAL"}
_QUARTER = "Q3FY25"


def _validate_args(
    tmp_path: Path,
    *,
    watchlist: bool = False,
    symbol: str | None = None,
    wave: str | None = None,
    report_dir: Path | None = None,
) -> object:
    """Parse an offline ``validate`` argv through the real CLI parser."""
    argv = ["validate", "--fixture", "--gold-dir", str(tmp_path / "gold")]
    if watchlist:
        argv.append("--watchlist")
    if symbol is not None:
        argv += ["--symbol", symbol]
    if wave is not None:
        argv += ["--wave", wave]
    if report_dir is not None:
        argv += ["--report-dir", str(report_dir)]
    return _build_parser().parse_args(argv)


def test_validate_wave1_selects_only_wave1_stocks(tmp_path: Path) -> None:
    waves = validate_command(_validate_args(tmp_path, watchlist=True, wave="Wave-1"))
    assert len(waves) == 1
    report = waves[0]
    assert report.wave is Wave.WAVE_1
    assert {stock.symbol for stock in report.stocks} == _WAVE1_SYMBOLS


def test_validate_wave2_selects_only_wave2_stocks(tmp_path: Path) -> None:
    waves = validate_command(_validate_args(tmp_path, watchlist=True, wave="Wave-2"))
    assert len(waves) == 1
    report = waves[0]
    assert report.wave is Wave.WAVE_2
    assert {stock.symbol for stock in report.stocks} == _WAVE2_SYMBOLS


def test_validate_wave_alone_scopes_to_that_wave(tmp_path: Path) -> None:
    # `--wave` on its own (no --watchlist) scopes the run to that wave.
    waves = validate_command(_validate_args(tmp_path, wave="Wave-2"))
    assert len(waves) == 1
    assert waves[0].wave is Wave.WAVE_2
    assert {stock.symbol for stock in waves[0].stocks} == _WAVE2_SYMBOLS


def test_validate_watchlist_writes_per_wave_rollups_without_collision(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports"
    waves = validate_command(_validate_args(tmp_path, watchlist=True, report_dir=report_dir))

    # One roll-up per wave (in canonical order), each labelled by its own wave.
    assert tuple(report.wave for report in waves) == (Wave.WAVE_1, Wave.WAVE_2)

    wave1_path = report_dir / "Wave-1-rollup.json"
    wave2_path = report_dir / "Wave-2-rollup.json"
    assert wave1_path.is_file()
    assert wave2_path.is_file()

    wave1 = json.loads(wave1_path.read_text(encoding="utf-8"))
    wave2 = json.loads(wave2_path.read_text(encoding="utf-8"))
    assert wave1["wave"] == "Wave-1"
    assert wave2["wave"] == "Wave-2"
    # Each roll-up carries only its own wave's stocks -> no cross-wave clobber.
    assert {stock["symbol"] for stock in wave1["stocks"]} == _WAVE1_SYMBOLS
    assert {stock["symbol"] for stock in wave2["stocks"]} == _WAVE2_SYMBOLS


def test_validate_symbol_labels_rollup_by_the_symbols_own_wave(tmp_path: Path) -> None:
    # A single Wave-2 symbol rolls up under Wave-2 (not a mislabelled Wave-1 file).
    report_dir = tmp_path / "reports"
    waves = validate_command(_validate_args(tmp_path, symbol="NETWEB", report_dir=report_dir))
    assert len(waves) == 1
    assert waves[0].wave is Wave.WAVE_2
    assert (report_dir / "Wave-2-rollup.json").is_file()
    assert not (report_dir / "Wave-1-rollup.json").exists()


def test_validate_symbol_wave_mismatch_fails_closed(tmp_path: Path) -> None:
    # NETWEB is Wave-2; asserting --wave Wave-1 is contradictory -> fail closed.
    with pytest.raises(SystemExit, match="Wave-2"):
        validate_command(_validate_args(tmp_path, symbol="NETWEB", wave="Wave-1"))


def test_validate_main_emits_json_array_of_wave_rollups(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        [
            "validate",
            "--watchlist",
            "--wave",
            "Wave-1",
            "--fixture",
            "--gold-dir",
            str(tmp_path / "gold"),
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list)
    assert len(payload) == 1
    assert payload[0]["wave"] == "Wave-1"
    assert {stock["symbol"] for stock in payload[0]["stocks"]} == _WAVE1_SYMBOLS


@pytest.mark.parametrize("command", ["report", "thesis"])
def test_report_and_thesis_accept_wave_option(command: str) -> None:
    argv = [command, "--watchlist", "--wave", "Wave-1"]
    if command == "thesis":
        argv += ["--quarter", _QUARTER]
    args = _build_parser().parse_args(argv)
    assert args.wave == "Wave-1"


# --- thesis --wave filtering (functional, faked model clients) ------------------


class _FakeClient:
    """A ThesisModelClient returning canned JSON (no process, no network)."""

    def __init__(self, label: str, name: str) -> None:
        self._label = label
        self._name = name

    @property
    def label(self) -> str:
        return self._label

    @property
    def name(self) -> str:
        return self._name

    def generate(self, prompt: str) -> ModelResponse:  # noqa: ARG002 - fixed response
        text = (
            '{"stance":"constructive",'
            '"drivers":["order book expansion"],'
            '"key_risks":["customer concentration"]}'
        )
        return ModelResponse(text=text, duration_seconds=0.01)


def _write_gold(gold_dir: Path, symbol: str) -> None:
    """Write a minimal one-AGREE-fact gold file for ``symbol``-Q3FY25."""
    revenue = "in-bse-fin:RevenueFromOperations"
    key = ComparisonKey(
        entity_scheme="nse-symbol",
        entity_id=symbol,
        concept_qname=revenue,
        period_type=PeriodType.DURATION,
        period_start=date(2024, 10, 1),
        period_end=date(2024, 12, 31),
        scope=Scope.CONSOLIDATED,
        accounting_basis=AccountingFramework.IND_AS,
        currency="INR",
        unit="INR crore",
        scale=10_000_000,
    )
    provenance = Provenance(
        source_id="nse-indas-xbrl-consolidated",
        file_sha256="0" * 64,
        anchor_type=SourceAnchorType.XBRL_CONTEXT,
        context_ref="OneD",
        retrieved_at=datetime(2026, 8, 22, tzinfo=UTC),
    )
    fact = GoldFact(
        concept_qname=revenue,
        comparison_key=key,
        value="1000.00",
        normalized_unit="INR crore",
        agreement_status=AgreementStatus.AGREE,
        agreed_sources=("bse-results-pdf", "nse-indas-xbrl-consolidated"),
        corroborating_sources=(),
        incompatible_sources=(),
        first_party_source_count=2,
        needs_human_review=False,
        source_values=(
            SourceValue(
                source_id="nse-indas-xbrl-consolidated",
                source_class=SourceClass.FIRST_PARTY,
                normalized_value=Decimal("1000.00"),
                normalized_unit="INR crore",
                provenance=provenance,
            ),
        ),
    )
    gold = GoldFile(schema_version=1, symbol=symbol, quarter=_QUARTER, facts=(fact,))
    gold_dir.mkdir(parents=True, exist_ok=True)
    (gold_dir / f"{symbol}-{_QUARTER}.json").write_text(gold.model_dump_json(), encoding="utf-8")


def _thesis_args(gold_dir: Path, out_dir: Path, wave: str) -> object:
    """Parse a ``thesis --watchlist --wave`` argv through the real CLI parser."""
    return _build_parser().parse_args(
        [
            "thesis",
            "--watchlist",
            "--wave",
            wave,
            "--quarter",
            _QUARTER,
            "--gold-dir",
            str(gold_dir),
            "--out-dir",
            str(out_dir),
        ]
    )


def test_thesis_wave_filter_selects_only_that_waves_symbols(tmp_path: Path) -> None:
    # Only TITAN (Wave-1) has a gold file. A Wave-2 run must ignore it (TITAN is not
    # in Wave-2); a Wave-1 run must process it. This proves --wave filters the set.
    gold_dir, out_dir = tmp_path / "gold", tmp_path / "thesis"
    _write_gold(gold_dir, "TITAN")
    clients = (
        _FakeClient("gpt-5.6-sol", "codex-sol"),
        _FakeClient("claude-opus", "claude-opus"),
    )

    wave2_docs = thesis_command(_thesis_args(gold_dir, out_dir, "Wave-2"), clients=clients)
    assert wave2_docs == []

    wave1_docs = thesis_command(_thesis_args(gold_dir, out_dir, "Wave-1"), clients=clients)
    assert len(wave1_docs) == 1
    assert wave1_docs[0].fact_set.symbol == "TITAN"
    assert wave1_docs[0].status is ThesisDocumentStatus.OK
