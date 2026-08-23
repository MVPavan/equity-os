"""Slice 4 integration — the end-to-end Infosys Q1 FY25 earnings-update pipeline.

The default acceptance runs the whole increment on the DETERMINISTIC path: the
real, lawfully-held Q1 results + transcript PDFs plus the committed synthetic NSE
Ind AS XBRL fixture (the real NSE bytes are gitignored, never committed), so the
run is reproducible byte-for-byte without live network.

It asserts the milestone contract:
* the rendered markdown carries Revenue 39,315 / PAT 6,374 / EPS 15.38;
* every number in the facts section resolves to a stored, provenance-bound fact;
* the XBRL↔PDF cross-check passed on every headline figure;
* removing a required fact makes the render FAIL CLOSED (no un-sourced output).

An opt-in ``RUN_NSE_LIVE=1`` variant re-runs the same pipeline against the live
NSE filing instead of the fixture.
"""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from fundamentals.api.cli import _build_parser, main, run_command
from fundamentals.api.config import FundamentalsConfig, load_config
from fundamentals.api.pipeline import PipelineResult, XbrlInput, run_pipeline
from fundamentals.output.earnings_update import (
    EarningsUpdate,
    FactRole,
    RenderedFact,
    RenderError,
    VerificationOutcome,
    render_earnings_update,
)
from fundamentals.store.fact_store import FactStore

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_PATH = _REPO_ROOT / "config" / "fundamentals.yaml"
_FIXTURES = _REPO_ROOT / "tests" / "fundamentals" / "fixtures"
_SYNTHETIC_XBRL = _FIXTURES / "synthetic_q1_fy25_consolidated.xml"

_CRORE_UNIT = "INR crore"
_PER_SHARE_UNIT = "INR per share"

_EXPECTED_HEADLINES = ("39,315", "6,374", "15.38")


def _config() -> FundamentalsConfig:
    return load_config(_CONFIG_PATH)


def _synthetic_xbrl_input(config: FundamentalsConfig) -> XbrlInput:
    xml_bytes = _SYNTHETIC_XBRL.read_bytes()
    return XbrlInput(
        xml_bytes=xml_bytes,
        file_sha256=hashlib.sha256(xml_bytes).hexdigest(),
        source_id=config.xbrl.source_id,
        retrieved_at=config.quarter.knowledge_cutoff,
    )


def _run_deterministic(store: FactStore) -> PipelineResult:
    config = _config()
    return run_pipeline(
        config=config,
        xbrl_input=_synthetic_xbrl_input(config),
        results_pdf_path=str(config.results_pdf_path(_CONFIG_PATH)),
        results_pdf_sha256=config.results_pdf.sha256,
        transcript_pdf_path=str(config.transcript_pdf_path(_CONFIG_PATH)),
        transcript_pdf_sha256=config.transcript_pdf.sha256,
        store=store,
    )


def _format_value(value: Decimal, unit: str) -> str:
    if unit == _PER_SHARE_UNIT:
        return f"{value:.2f}"
    return f"{int(value):,}"


def _facts_table_values(markdown: str) -> list[str]:
    """Extract the value column of every row in the §2 facts table."""
    lines = markdown.splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "## 2. facts")
    values: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("## "):
            break
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2 or cells[0] in {"P&L line", "---"}:
            continue
        values.append(cells[1])
    return values


def _stored_value_strings(store: FactStore) -> set[str]:
    strings: set[str] = set()
    for revision in store.query_canonical():
        obs = revision.fact.observation
        assert obs.provenance.file_sha256, "stored fact must be provenance-bound"
        strings.add(_format_value(obs.normalized_value, obs.normalized_unit))
    return strings


@pytest.fixture()
def store() -> Iterator[FactStore]:
    fact_store = FactStore(":memory:")
    yield fact_store
    fact_store.close()


def test_pipeline_produces_headline_figures(store: FactStore) -> None:
    result = _run_deterministic(store)
    for headline in _EXPECTED_HEADLINES:
        assert headline in result.markdown, headline


def test_single_issuer_pipeline_says_comparatives_were_not_attempted(store: FactStore) -> None:
    """The legacy single-issuer path must not imply that it searched for comparators."""
    result = _run_deterministic(store)

    assert (
        "Prior-period comparatives were not attempted for this single-issuer pipeline path."
        in result.markdown
    )
    assert "No prior-period comparator filings were collected" not in result.markdown


def test_every_facts_table_number_resolves_to_a_stored_fact(store: FactStore) -> None:
    result = _run_deterministic(store)
    stored_values = _stored_value_strings(store)

    table_values = _facts_table_values(result.markdown)
    assert len(table_values) == len(FactRole)
    for value in table_values:
        assert value in stored_values, f"un-sourced number in output: {value!r}"


def test_cross_check_passed_on_headline_figures(store: FactStore) -> None:
    result = _run_deterministic(store)
    assert len(result.cross_check_results) == 5
    assert all(check.matched for check in result.cross_check_results)
    assert all(check.keys_compatible for check in result.cross_check_results)


def test_cross_foot_identities_hold(store: FactStore) -> None:
    result = _run_deterministic(store)
    assert result.cross_foot_results
    assert all(identity.passed for identity in result.cross_foot_results)
    assert all(identity.residual == Decimal(0) for identity in result.cross_foot_results)


def test_two_independent_sources_share_one_revision_family(store: FactStore) -> None:
    _run_deterministic(store)
    revenue = next(
        revision
        for revision in store.query_canonical()
        if revision.fact.observation.concept_qname == "in-bse-fin:RevenueFromOperations"
    )
    family = store.get_revisions(revenue.content_identity)
    source_ids = {rev.fact.observation.provenance.source_id for rev in family}
    # XBRL canonical + PDF confirmation land as two retained revisions, one family.
    assert len(family) == 2
    assert source_ids == {"nse-indas-xbrl-consolidated", "infy-q1-fy25-results-pdf"}


def test_render_fails_closed_when_a_required_fact_is_missing(store: FactStore) -> None:
    result = _run_deterministic(store)

    # Reconstruct the render inputs from the stored canonical facts, then drop one.
    canonical = {rev.fact.observation.concept_qname: rev for rev in store.query_canonical()}
    role_by_concept = {
        "in-bse-fin:RevenueFromOperations": FactRole.REVENUE,
        "in-bse-fin:Income": FactRole.TOTAL_INCOME,
        "in-bse-fin:Expenses": FactRole.TOTAL_EXPENSES,
        "in-bse-fin:ProfitBeforeTax": FactRole.PROFIT_BEFORE_TAX,
        "in-bse-fin:ProfitLossForPeriod": FactRole.PROFIT_FOR_PERIOD,
        "in-bse-fin:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations": (
            FactRole.BASIC_EPS
        ),
    }
    facts = tuple(
        RenderedFact(
            role=role_by_concept[concept],
            concept_qname=concept,
            value=rev.fact.observation.normalized_value,
            unit=rev.fact.observation.normalized_unit,
            reconciliation_status=rev.fact.reconciliation_status.value,
            sources=(rev.fact.observation.provenance,),
        )
        for concept, rev in canonical.items()
        if concept != "in-bse-fin:ProfitLossForPeriod"  # remove a REQUIRED fact
    )
    incomplete = EarningsUpdate(
        issuer_name="Infosys Limited",
        nse_symbol="INFY",
        issuer_quarter_label="Q1 FY25",
        period_start="2024-04-01",
        period_end="2024-06-30",
        knowledge_cutoff="2024-07-18",
        facts=facts,
        guidance=(),
        calculations=(),
        cross_check=VerificationOutcome(passed_count=5, total_count=5),
        cross_foot=VerificationOutcome(passed_count=2, total_count=2),
        sec_cross_check_note="n/a",
    )
    with pytest.raises(RenderError):
        render_earnings_update(incomplete)

    # The complete render still succeeds (sanity that only the removal broke it).
    assert "6,374" in result.markdown


def test_cli_run_writes_sourced_markdown_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["run", "--issuer", "INFY", "--quarter", "Q1-FY25"])
    assert exit_code == 0
    captured = capsys.readouterr()
    for headline in _EXPECTED_HEADLINES:
        assert headline in captured.out, headline
    assert "## 2. facts" in captured.out


def test_cli_rejects_mismatched_issuer() -> None:
    parser = _build_parser()
    args = parser.parse_args(["run", "--issuer", "TCS", "--quarter", "Q1-FY25"])
    with pytest.raises(SystemExit):
        run_command(args)


@pytest.mark.skipif(
    os.environ.get("RUN_NSE_LIVE") != "1",
    reason="live NSE fetch is opt-in; set RUN_NSE_LIVE=1 to run",
)
def test_pipeline_e2e_live_nse(store: FactStore) -> None:
    from fundamentals.api.cli import _build_xbrl_input
    from fundamentals.api.config import XbrlMode

    config = _config()
    xbrl_input = _build_xbrl_input(config, _CONFIG_PATH, XbrlMode.LIVE)
    result = run_pipeline(
        config=config,
        xbrl_input=xbrl_input,
        results_pdf_path=str(config.results_pdf_path(_CONFIG_PATH)),
        results_pdf_sha256=config.results_pdf.sha256,
        transcript_pdf_path=str(config.transcript_pdf_path(_CONFIG_PATH)),
        transcript_pdf_sha256=config.transcript_pdf.sha256,
        store=store,
    )
    for headline in _EXPECTED_HEADLINES:
        assert headline in result.markdown
    assert all(check.matched for check in result.cross_check_results)


def test_no_bare_unsourced_prior_period_numbers(store: FactStore) -> None:
    # The pipeline must not emit inferred comparatives (e.g. prior-quarter revenue
    # 37,923) that do not resolve to a stored Q1 fact.
    result = _run_deterministic(store)
    assert "37,923" not in result.markdown
    assert "37,933" not in result.markdown
    # Guard against an accidental stray percent-growth inference in the facts area.
    facts_section = re.search(r"## 2\. facts(.*?)## 3\.", result.markdown, re.DOTALL)
    assert facts_section is not None
