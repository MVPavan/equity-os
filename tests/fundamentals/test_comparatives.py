"""QoQ/YoY comparatives through the public stock-runner and report seams."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from fundamentals.api.cli import _cached_stock
from fundamentals.api.comparatives import (
    _load_fixture,
    _one_change,
    derive_comparator_periods,
)
from fundamentals.api.goal_runner import (
    RunMode,
    SourceKind,
    StockOutcome,
    StockReport,
    run_stock,
)
from fundamentals.api.report_builder import render_report
from fundamentals.api.watchlist_config import (
    FixturePaths,
    SourceIdentifiers,
    StockConfig,
    StockQuarter,
)
from fundamentals.contracts.comparative import ComparatorKind
from fundamentals.contracts.observation import AccountingFramework, PeriodType, Scope
from fundamentals.extract.xbrl_parser import select_observation
from fundamentals.ingest.xbrl_source import (
    CONSOLIDATED_SOURCE_ID,
    XbrlHardBlockError,
    XbrlRetrieval,
)
from fundamentals.reconcile.fact_view import derived_concept_map, role_agreement

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CURRENT = "tests/fundamentals/fixtures/synthetic_wave1_nse_q3fy25_consolidated.xml"
_CURRENT_BSE = "tests/fundamentals/fixtures/synthetic_wave1_bse_q3fy25_consolidated.xml"
_QOQ = "tests/fundamentals/fixtures/synthetic_wave1_nse_q2fy25_consolidated.xml"
_QOQ_YTD_DEFECT = (
    "tests/fundamentals/fixtures/synthetic_wave1_nse_q2fy25_ytd_defect_consolidated.xml"
)
_YOY = "tests/fundamentals/fixtures/synthetic_wave1_nse_q3fy24_consolidated.xml"

REVENUE = "in-bse-fin:RevenueFromOperations"
PAT = "in-bse-fin:ProfitLossForPeriod"


def _stock(*, qoq_fixture: str | None = _QOQ) -> StockConfig:
    """Build a synthetic Q3FY25 stock with separate prior filing fixtures."""
    return StockConfig(
        name="Synthetic Test Corp",
        domain="Test",
        identifiers=SourceIdentifiers(
            nse_symbol="SYNTH",
            bse_scrip="999999",
            screener_slug="SYNTH",
            screener_company_id=991001,
            screener_warehouse_id_consolidated=992001,
            tijori_slug="synthetic-test-corp",
            tijori_company_id=81,
        ),
        quarter=StockQuarter(
            label="Q3FY25",
            period_start=date(2024, 10, 1),
            period_end=date(2024, 12, 31),
            knowledge_cutoff=datetime(2025, 2, 15, tzinfo=UTC),
        ),
        fixtures=FixturePaths(
            nse=_CURRENT,
            bse=_CURRENT_BSE,
            nse_qoq=qoq_fixture,
            nse_yoy=_YOY,
        ),
    )


def _run(stock: StockConfig, tmp_path: Path, *, repo_root: Path = _REPO_ROOT) -> StockReport:
    """Run the deterministic current and prior filing fixtures."""
    return run_stock(
        stock,
        mode=RunMode.FIXTURE,
        repo_root=repo_root,
        kinds=frozenset({SourceKind.NSE, SourceKind.BSE}),
        out_dir=tmp_path,
    )


def test_derived_concept_map_canonicalises_tijori_pbt() -> None:
    """Tijori's derived PBT participates in the configured canonical cross-check."""
    derived = derived_concept_map(_stock().concepts.roles)

    assert derived["tijori:pbt"] == "in-bse-fin:ProfitBeforeTax"


def _cached_qoq_stock(tmp_path: Path, xml: str) -> tuple[StockConfig, Path]:
    """Place one comparator in the real cache layout and point other fixtures at held files."""
    cache_dir = tmp_path / "data/raw/watchlist/synth/nse/comparatives/qoq/2024-07-01_2024-09-30"
    cache_dir.mkdir(parents=True)
    comparator_path = cache_dir / "cached.xml"
    comparator_path.write_text(xml, encoding="utf-8")
    stock = _stock(qoq_fixture=str(comparator_path.relative_to(tmp_path)))
    fixtures = stock.fixtures.model_copy(
        update={
            "nse": str(_REPO_ROOT / _CURRENT),
            "bse": str(_REPO_ROOT / _CURRENT_BSE),
            "nse_yoy": str(_REPO_ROOT / _YOY),
        }
    )
    return stock.model_copy(update={"fixtures": fixtures}), comparator_path


def _section_table_labels(markdown: str, section: str) -> tuple[str, ...]:
    """Return the first-column labels from one rendered Markdown section table."""
    body = markdown.split(f"## {section}", maxsplit=1)[1].split("\n## ", maxsplit=1)[0]
    return tuple(
        line.split("|")[1].strip()
        for line in body.splitlines()
        if line.startswith("| ") and not line.startswith("| ---") and "P&L line" not in line
    )


def test_fixture_run_computes_qoq_and_yoy_deltas_with_traces(tmp_path: Path) -> None:
    """Separate prior filings yield literal QoQ/YoY changes with arithmetic traces."""
    report = _run(_stock(), tmp_path)

    revenue = next(item for item in report.comparatives if item.concept_qname == REVENUE)
    assert revenue.current_value == Decimal("1000")
    assert revenue.qoq.prior_value == Decimal("800")
    assert revenue.qoq.absolute_change == Decimal("200")
    assert revenue.qoq.percent_change == Decimal("25")
    assert revenue.qoq.absolute_trace == "1000.00 - 800"
    assert revenue.yoy.prior_value == Decimal("500")
    assert revenue.yoy.absolute_change == Decimal("500")
    assert revenue.yoy.percent_change == Decimal("100")
    assert revenue.yoy.absolute_trace == "1000.00 - 500"


def test_comparator_selects_quarter_not_defective_ytd_context(tmp_path: Path) -> None:
    """Declared reporting periods disambiguate a production-shaped YTD comparator."""
    report = _run(_stock(qoq_fixture=_QOQ_YTD_DEFECT), tmp_path)

    revenue = next(item for item in report.comparatives if item.concept_qname == REVENUE)
    assert revenue.qoq.prior_value == Decimal("800")
    assert revenue.qoq.absolute_change == Decimal("200")
    assert all(item.qoq.available for item in report.comparatives)


def test_comparator_periods_cross_the_indian_fiscal_year_boundary() -> None:
    """Q1 FY25 compares QoQ with Q4 FY24 and YoY with Q1 FY24."""
    periods = derive_comparator_periods(date(2024, 4, 1), date(2024, 6, 30))

    assert periods[ComparatorKind.QOQ] == (date(2024, 1, 1), date(2024, 3, 31))
    assert periods[ComparatorKind.YOY] == (date(2023, 4, 1), date(2023, 6, 30))


def test_cached_comparators_are_selected_by_derived_period_not_glob_order(
    tmp_path: Path,
) -> None:
    """An exact period directory wins even when an older lexicographic cache exists."""
    qoq_root = tmp_path / "data/raw/watchlist/synth/nse/comparatives/qoq"
    wanted_qoq = qoq_root / "2024-07-01_2024-09-30" / "wanted.xml"
    stale_qoq = qoq_root / "2024-04-01_2024-06-30" / "stale.xml"
    wanted_yoy = (
        tmp_path / "data/raw/watchlist/synth/nse/comparatives/yoy/2023-10-01_2023-12-31/wanted.xml"
    )
    for path in (wanted_qoq, stale_qoq, wanted_yoy):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture", encoding="utf-8")

    cached = _cached_stock(_stock(), tmp_path)

    assert cached.fixtures.nse_qoq == str(wanted_qoq.relative_to(tmp_path))
    assert cached.fixtures.nse_yoy == str(wanted_yoy.relative_to(tmp_path))


def test_distinct_cached_filings_for_one_period_require_manual_adjudication(
    tmp_path: Path,
) -> None:
    """Two different filings for one exact period fail closed instead of sorting."""
    period_dir = tmp_path / "data/raw/watchlist/synth/nse/comparatives/qoq/2024-07-01_2024-09-30"
    period_dir.mkdir(parents=True)
    original = (_REPO_ROOT / _QOQ).read_bytes()
    changed = original.replace(b">8000000000<", b">8100000000<")
    (period_dir / "a.xml").write_bytes(original)
    (period_dir / "b.xml").write_bytes(changed)
    cached = _cached_stock(_stock(), tmp_path)
    fixtures = cached.fixtures.model_copy(
        update={
            "nse": str(_REPO_ROOT / _CURRENT),
            "bse": str(_REPO_ROOT / _CURRENT_BSE),
            "nse_yoy": str(_REPO_ROOT / _YOY),
        }
    )

    report = _run(
        cached.model_copy(update={"fixtures": fixtures}),
        tmp_path / "gold",
        repo_root=tmp_path,
    )

    revenue = next(item for item in report.comparatives if item.concept_qname == REVENUE)
    assert not revenue.qoq.available
    assert revenue.qoq.unavailable_reason == (
        "multiple distinct cached filings for this period; adjudicate manually"
    )


def test_byte_identical_cached_filings_for_one_period_are_usable(tmp_path: Path) -> None:
    """Duplicate filenames do not create ambiguity when their held bytes match."""
    period_dir = tmp_path / "data/raw/watchlist/synth/nse/comparatives/qoq/2024-07-01_2024-09-30"
    period_dir.mkdir(parents=True)
    xml = (_REPO_ROOT / _QOQ).read_bytes()
    (period_dir / "a.xml").write_bytes(xml)
    (period_dir / "b.xml").write_bytes(xml)
    cached = _cached_stock(_stock(), tmp_path)
    fixtures = cached.fixtures.model_copy(
        update={
            "nse": str(_REPO_ROOT / _CURRENT),
            "bse": str(_REPO_ROOT / _CURRENT_BSE),
            "nse_yoy": str(_REPO_ROOT / _YOY),
        }
    )

    report = _run(
        cached.model_copy(update={"fixtures": fixtures}),
        tmp_path / "gold",
        repo_root=tmp_path,
    )

    revenue = next(item for item in report.comparatives if item.concept_qname == REVENUE)
    assert revenue.qoq.prior_value == Decimal("800")
    assert revenue.qoq.absolute_change == Decimal("200")


def test_zero_prior_value_keeps_absolute_change_and_marks_percent_na(tmp_path: Path) -> None:
    """A zero comparator never divides; its percent result records why it is unavailable."""
    report = _run(_stock(), tmp_path)

    pat = next(item for item in report.comparatives if item.concept_qname == PAT)
    assert pat.qoq.prior_value == Decimal(0)
    assert pat.qoq.absolute_change == Decimal("150")
    assert pat.qoq.absolute_trace == "150.00 - 0"
    assert pat.qoq.percent_change is None
    assert pat.qoq.percent_trace is None
    assert pat.qoq.percent_unavailable_reason == "prior value is zero"


def test_missing_comparator_is_explicit_and_does_not_block_current_report(
    tmp_path: Path,
) -> None:
    """A missing prior filing degrades every QoQ cell without changing current DoD."""
    report = _run(_stock(qoq_fixture=None), tmp_path)

    assert report.outcome is StockOutcome.DONE
    assert report.dod.met is True
    assert report.facts
    assert all(not item.qoq.available for item in report.comparatives)
    assert all(
        "no QoQ NSE comparator fixture" in item.qoq.unavailable_reason
        for item in report.comparatives
        if item.qoq.unavailable_reason is not None
    )
    assert all(item.yoy.available for item in report.comparatives)
    assert "no QoQ NSE comparator fixture configured" in render_report(
        report, _stock(qoq_fixture=None)
    )


def test_wrong_entity_cached_comparator_is_unavailable_and_quarantined(tmp_path: Path) -> None:
    """A cached filing for another issuer cannot be canonicalised into the requested issuer."""
    wrong_entity_xml = (_REPO_ROOT / _QOQ).read_text(encoding="utf-8").replace(">SYNTH<", ">OTHER<")
    stock, comparator_path = _cached_qoq_stock(tmp_path, wrong_entity_xml)

    report = _run(stock, tmp_path / "gold", repo_root=tmp_path)

    revenue = next(item for item in report.comparatives if item.concept_qname == REVENUE)
    assert not revenue.qoq.available
    assert revenue.qoq.unavailable_reason is not None
    assert "entity" in revenue.qoq.unavailable_reason.lower()
    assert report.outcome is StockOutcome.DONE
    assert "not available" in render_report(report, stock)
    assert not comparator_path.exists()
    assert list((comparator_path.parent / "rejected").glob("cached-*.xml"))


def test_wrong_entity_scheme_cached_comparator_is_rejected(tmp_path: Path) -> None:
    """The right symbol under an attacker-controlled scheme is not NSE identity."""
    wrong_scheme_xml = (
        (_REPO_ROOT / _QOQ)
        .read_text(encoding="utf-8")
        .replace(
            'scheme="http://www.nseindia.com/NSESymbol"',
            'scheme="https://attacker.example/NSESymbol"',
        )
    )
    stock, comparator_path = _cached_qoq_stock(tmp_path, wrong_scheme_xml)

    report = _run(stock, tmp_path / "gold", repo_root=tmp_path)

    revenue = next(item for item in report.comparatives if item.concept_qname == REVENUE)
    assert not revenue.qoq.available
    assert revenue.qoq.unavailable_reason is not None
    assert "scheme" in revenue.qoq.unavailable_reason.lower()
    assert not comparator_path.exists()


def test_configured_entity_alias_is_accepted_before_canonicalisation(tmp_path: Path) -> None:
    """A reviewed as-filed alias remains a valid comparator issuer identity."""
    alias_xml = (_REPO_ROOT / _QOQ).read_text(encoding="utf-8").replace(">SYNTH<", ">SYNTH-OLD<")
    stock, comparator_path = _cached_qoq_stock(tmp_path, alias_xml)
    identifiers = stock.identifiers.model_copy(update={"accepted_entity_ids": ("synth-old",)})

    report = _run(
        stock.model_copy(update={"identifiers": identifiers}),
        tmp_path / "gold",
        repo_root=tmp_path,
    )

    revenue = next(item for item in report.comparatives if item.concept_qname == REVENUE)
    assert revenue.qoq.available
    assert comparator_path.exists()


def test_invalid_date_comparator_is_unavailable_and_current_report_renders(
    tmp_path: Path,
) -> None:
    """A typed parser failure degrades the comparator without aborting current facts."""
    malformed_xml = (
        (_REPO_ROOT / _QOQ).read_text(encoding="utf-8").replace(">2024-07-01<", ">not-a-date<")
    )
    stock, comparator_path = _cached_qoq_stock(tmp_path, malformed_xml)

    report = _run(stock, tmp_path / "gold", repo_root=tmp_path)

    revenue = next(item for item in report.comparatives if item.concept_qname == REVENUE)
    assert not revenue.qoq.available
    assert revenue.qoq.unavailable_reason is not None
    assert "invalid isoformat" in revenue.qoq.unavailable_reason.lower()
    assert report.outcome is StockOutcome.DONE
    assert report.facts
    assert "not available" in render_report(report, stock)
    assert not comparator_path.exists()


def test_quarantine_move_failure_keeps_evidence_and_still_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A quarantine filesystem failure never deletes or accepts poisoned evidence."""
    wrong_entity_xml = (_REPO_ROOT / _QOQ).read_text(encoding="utf-8").replace(">SYNTH<", ">OTHER<")
    stock, comparator_path = _cached_qoq_stock(tmp_path, wrong_entity_xml)
    original_rename = Path.rename

    def fail_comparator_rename(self: Path, target: str | Path) -> Path:
        if self.resolve() == comparator_path.resolve():
            raise OSError("simulated quarantine failure")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", fail_comparator_rename)

    report = _run(stock, tmp_path / "gold", repo_root=tmp_path)

    revenue = next(item for item in report.comparatives if item.concept_qname == REVENUE)
    assert report.outcome is StockOutcome.DONE
    assert not revenue.qoq.available
    assert comparator_path.exists()
    assert "not available" in render_report(report, stock)


def test_unexpected_comparator_failure_cannot_abort_current_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The runner's last-resort seam contains an unclassified comparator failure."""

    def fail_comparators(*_args: object, **_kwargs: object) -> tuple[()]:
        raise RuntimeError("unexpected comparator defect")

    monkeypatch.setattr("fundamentals.api.goal_runner.collect_comparatives", fail_comparators)

    report = _run(_stock(), tmp_path)

    assert report.outcome is StockOutcome.DONE
    assert report.facts
    assert report.comparatives == ()


def test_live_comparators_are_skipped_after_current_nse_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One current-source hard block prevents both additional comparator requests."""
    calls: list[tuple[date, date]] = []

    def blocked_fetch(_source: object, *, from_date: date, to_date: date) -> None:
        calls.append((from_date, to_date))
        raise XbrlHardBlockError("NSE returned 403 Forbidden")

    monkeypatch.setattr(
        "fundamentals.ingest.xbrl_source.NseXbrlSource.fetch_consolidated_quarter",
        blocked_fetch,
    )

    report = run_stock(
        _stock(),
        mode=RunMode.LIVE,
        repo_root=tmp_path,
        kinds=frozenset({SourceKind.NSE}),
        out_dir=tmp_path / "gold",
    )

    assert calls == [(date(2024, 10, 1), date(2024, 12, 31))]
    assert report.comparatives
    assert all(not item.qoq.available and not item.yoy.available for item in report.comparatives)
    assert all(
        "403 Forbidden" in (item.qoq.unavailable_reason or "") for item in report.comparatives
    )


def test_comparator_hard_block_aborts_remaining_fetches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A QoQ hard block prevents the subsequent YoY request for that stock."""
    calls: list[tuple[date, date]] = []
    current_path = _REPO_ROOT / _CURRENT
    current_xml = current_path.read_bytes()

    def fetch_then_block(_source: object, *, from_date: date, to_date: date) -> XbrlRetrieval:
        calls.append((from_date, to_date))
        if len(calls) == 1:
            return XbrlRetrieval(
                source_id=CONSOLIDATED_SOURCE_ID,
                local_path=current_path,
                file_sha256=hashlib.sha256(current_xml).hexdigest(),
                xbrl_url="https://nsearchives.example/current.xml",
                symbol="SYNTH",
                from_date=from_date,
                to_date=to_date,
                relating_to="Third Quarter",
                consolidated=True,
                retrieved_at=datetime(2025, 2, 15, tzinfo=UTC),
            )
        raise XbrlHardBlockError("NSE comparator returned 403 Forbidden")

    monkeypatch.setattr(
        "fundamentals.ingest.xbrl_source.NseXbrlSource.fetch_consolidated_quarter",
        fetch_then_block,
    )

    report = run_stock(
        _stock(),
        mode=RunMode.LIVE,
        repo_root=tmp_path,
        kinds=frozenset({SourceKind.NSE}),
        out_dir=tmp_path / "gold",
    )

    assert calls == [
        (date(2024, 10, 1), date(2024, 12, 31)),
        (date(2024, 7, 1), date(2024, 9, 30)),
    ]
    assert all(
        "403 Forbidden" in (item.qoq.unavailable_reason or "")
        and "403 Forbidden" in (item.yoy.unavailable_reason or "")
        for item in report.comparatives
    )


def test_extreme_percent_is_rendered_as_unavailable_without_aborting_report(
    tmp_path: Path,
) -> None:
    """An unrepresentable percent degrades only that percent presentation."""
    stock = _stock()
    report = _run(stock, tmp_path)
    comparatives = tuple(
        item.model_copy(
            update={"qoq": item.qoq.model_copy(update={"percent_change": Decimal("1E+999999999")})}
        )
        if item.concept_qname == REVENUE
        else item
        for item in report.comparatives
    )

    markdown = render_report(report.model_copy(update={"comparatives": comparatives}), stock)

    revenue_row = next(
        line
        for line in markdown.splitlines()
        if line.startswith("| Revenue from operations |") and "Δ" in line
    )
    assert "n/a (percent cannot be represented safely)" in revenue_row
    assert "Δ +200" in revenue_row


def test_parsed_extreme_prior_degrades_percent_without_aborting_report(tmp_path: Path) -> None:
    """An extreme parsed prior keeps sourced endpoints while containing Decimal overflow."""
    extreme_xml = (
        (_REPO_ROOT / _QOQ).read_text(encoding="utf-8").replace(">8000000000<", ">1E-999990<")
    )
    stock, _comparator_path = _cached_qoq_stock(tmp_path, extreme_xml)

    report = _run(stock, tmp_path / "gold", repo_root=tmp_path)

    revenue = next(item for item in report.comparatives if item.concept_qname == REVENUE)
    assert revenue.qoq.available
    assert revenue.qoq.prior_value == Decimal("1E-999997")
    assert revenue.qoq.absolute_change == Decimal("1000.00")
    assert revenue.qoq.percent_change is None
    assert revenue.qoq.percent_unavailable_reason == "percent calculation exceeded safe range"
    assert report.outcome is StockOutcome.DONE
    assert "n/a (percent calculation exceeded safe range)" in render_report(report, stock)


def test_small_negative_percent_never_renders_with_both_signs(tmp_path: Path) -> None:
    """A decline rounded to negative zero keeps only its minus sign."""
    prior_xml = (
        (_REPO_ROOT / _QOQ).read_text(encoding="utf-8").replace(">8000000000<", ">10003000000<")
    )
    stock, _comparator_path = _cached_qoq_stock(tmp_path, prior_xml)

    markdown = render_report(_run(stock, tmp_path / "gold", repo_root=tmp_path), stock)

    revenue_row = next(
        line
        for line in markdown.splitlines()
        if line.startswith("| Revenue from operations |") and "Δ" in line
    )
    assert "-0.0%" in revenue_row
    assert "+-0.0%" not in revenue_row


@pytest.mark.parametrize(
    ("updates", "period_start", "period_end", "reason"),
    [
        ({"normalized_unit": "INR million"}, date(2024, 7, 1), date(2024, 9, 30), "unit mismatch"),
        ({"scale": 1_000_000}, date(2024, 7, 1), date(2024, 9, 30), "scale mismatch"),
        ({"currency": "USD"}, date(2024, 7, 1), date(2024, 9, 30), "currency mismatch"),
        (
            {"accounting_basis": AccountingFramework.IFRS},
            date(2024, 7, 1),
            date(2024, 9, 30),
            "accounting_basis mismatch",
        ),
        (
            {"scope": Scope.STANDALONE},
            date(2024, 7, 1),
            date(2024, 9, 30),
            "selection failed",
        ),
        (
            {"dimensions": (("SegmentAxis", "RetailMember"),)},
            date(2024, 7, 1),
            date(2024, 9, 30),
            "selection failed",
        ),
        (
            {"period_start": date(2024, 10, 1), "period_end": date(2024, 12, 31)},
            date(2024, 10, 1),
            date(2024, 12, 31),
            "period must differ",
        ),
    ],
    ids=("unit", "scale", "currency", "accounting-basis", "scope", "dimensions", "same-period"),
)
def test_incompatible_comparison_keys_are_rejected(
    tmp_path: Path,
    updates: dict[str, object],
    period_start: date,
    period_end: date,
    reason: str,
) -> None:
    """Every non-period comparator identity field and same-period key fail closed."""
    stock = _stock()
    report = _run(stock, tmp_path)
    current = role_agreement(
        REVENUE,
        report.sources,
        symbol=stock.symbol,
        period_start=stock.quarter.period_start,
        period_end=stock.quarter.period_end,
        derived_map=derived_concept_map(stock.concepts.roles),
    )
    observations, filing_reason = _load_fixture(stock, ComparatorKind.QOQ, _REPO_ROOT)
    assert current is not None
    assert observations is not None
    assert filing_reason is None
    prior = select_observation(
        observations,
        concept_qname=REVENUE,
        scope=Scope.CONSOLIDATED,
        period_type=PeriodType.DURATION,
        period_start=date(2024, 7, 1),
        period_end=date(2024, 9, 30),
    ).model_copy(update=updates)

    change = _one_change(
        kind=ComparatorKind.QOQ,
        period_start=period_start,
        period_end=period_end,
        current=current,
        observations=(prior,),
        filing_reason=None,
        stock=stock,
    )

    assert not change.available
    assert change.unavailable_reason is not None
    assert reason in change.unavailable_reason


def test_section_three_renders_comparatives_traces_and_both_endpoint_footnotes(
    tmp_path: Path,
) -> None:
    """The changes table sources current/prior values and their computed deltas."""
    stock = _stock()
    markdown = render_report(_run(stock, tmp_path), stock)
    revenue_row = next(
        line
        for line in markdown.splitlines()
        if line.startswith("| Revenue from operations |") and "Δ" in line
    )
    cells = [cell.strip() for cell in revenue_row.strip("|").split("|")]
    assert len(cells) == 4
    current_markers = set(re.findall(r"\[\^\d+\]", cells[1]))
    assert current_markers
    for change_cell in cells[2:]:
        prior, delta, percent, *_traces = change_cell.split("; ")
        prior_markers = set(re.findall(r"\[\^\d+\]", prior))
        assert prior_markers
        endpoint_markers = current_markers | prior_markers
        assert endpoint_markers <= set(re.findall(r"\[\^\d+\]", delta))
        assert endpoint_markers <= set(re.findall(r"\[\^\d+\]", percent))

    assert "## 3. changes" in markdown
    assert "| P&L line | Current | QoQ prior / change | YoY prior / change |" in markdown
    assert "Revenue from operations" in markdown
    assert "Δ +200" in markdown
    assert "+25.0%" in markdown
    assert "1000.00" in markdown and "800" in markdown and "500" in markdown
    assert "trace: 1000.00" in markdown
    assert "context OneD" in markdown
    assert "context QoQ" in markdown
    assert "context YoY" in markdown


def test_section_three_labels_periods_and_moves_traces_below_the_table(tmp_path: Path) -> None:
    """Comparator cells stay compact while the adjacent traces retain both endpoints."""
    stock = _stock()
    markdown = render_report(_run(stock, tmp_path), stock)
    revenue_row = next(
        line
        for line in markdown.splitlines()
        if line.startswith("| Revenue from operations |") and "Δ" in line
    )

    assert "Q2FY25 2024-07-01..2024-09-30" in revenue_row
    assert "Q3FY24 2023-10-01..2023-12-31" in revenue_row
    assert "trace:" not in revenue_row
    section = markdown.split("## 3. changes", maxsplit=1)[1].split("## 4.", maxsplit=1)[0]
    assert "Computed traces:" in section
    assert "Revenue from operations QoQ trace:" in section
    assert "Revenue from operations YoY trace:" in section


def test_section_three_escapes_dynamic_text_inside_markdown_cells(tmp_path: Path) -> None:
    """External reasons cannot add columns or rows to the comparative table."""
    stock = _stock(qoq_fixture=None)
    report = _run(stock, tmp_path)
    comparatives = tuple(
        item.model_copy(
            update={
                "qoq": item.qoq.model_copy(
                    update={"unavailable_reason": "missing | FORGED |\nsecond row"}
                )
            }
        )
        if item.concept_qname == REVENUE
        else item
        for item in report.comparatives
    )

    markdown = render_report(report.model_copy(update={"comparatives": comparatives}), stock)
    section = markdown.split("## 3. changes", maxsplit=1)[1].split("## 4.", maxsplit=1)[0]
    revenue_rows = [
        line for line in section.splitlines() if line.startswith("| Revenue from operations |")
    ]

    assert len(revenue_rows) == 1
    assert len(re.findall(r"(?<!\\)\|", revenue_rows[0])) == 5
    assert r"missing \| FORGED \| second row" in revenue_rows[0]


def test_section_three_renders_the_same_p_and_l_lines_as_section_two(tmp_path: Path) -> None:
    """Every sourced fact row has a corresponding comparative row in the same order."""
    stock = _stock()
    markdown = render_report(_run(stock, tmp_path), stock)

    assert _section_table_labels(markdown, "3. changes") == _section_table_labels(
        markdown, "2. facts"
    )
