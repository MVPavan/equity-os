"""Slice phase05-sC — the management ledger carried across quarters (+ addendum A2).

Acceptance tests for ``fundamentals.output.management_ledger`` (which does not exist
yet), its wiring into ``FundamentalsConfig``/``run_pipeline``/``EarningsUpdate``, the §5
renderer, and the addendum-A2 guidance rules (a per-rule ``unit`` and one- or two-group
patterns). Every reference to a not-yet-existing name happens *inside* a test or a helper
a test calls, so each node id fails on its own error instead of one module-level import
collapsing the file into a collection error.

All ledger data is synthetic: symbol ``SYNTH``, quarters ``FY27_Q1``/``FY27_Q2``/
``FY27_Q3``, invented metrics and quotes, 2027 dates. The one pipeline test reuses the
committed deterministic end-to-end path (see ``tests/fundamentals/test_pipeline_e2e.py``)
because the ledger write is a property of that pipeline, not of a hand-built fixture.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml

from fundamentals.api.config import FundamentalsConfig, GuidanceRuleConfig, load_config
from fundamentals.api.pipeline import XbrlInput, run_pipeline
from fundamentals.contracts.fact import ReconciliationStatus
from fundamentals.contracts.guidance_claim import EpistemicClass, GuidanceClaim
from fundamentals.contracts.observation import Scope
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.contracts.role import FactRole
from fundamentals.ingest.pdf_source import LoadedPdf, PdfBlock, PdfIntegrityError, PdfPage
from fundamentals.output.earnings_update import (
    EarningsUpdate,
    RenderedFact,
    VerificationOutcome,
    render_earnings_update,
)
from fundamentals.store.fact_store import FactStore


def _find_repo_root() -> Path:
    """Walk up from this file to the directory holding ``config/fundamentals.yaml``."""
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "config" / "fundamentals.yaml").is_file():
            return candidate
    raise RuntimeError("repository root (config/fundamentals.yaml) not found above this test")


_REPO_ROOT = _find_repo_root()
_CONFIG_PATH = _REPO_ROOT / "config" / "fundamentals.yaml"
_FIXTURES = _REPO_ROOT / "tests" / "fundamentals" / "fixtures"
_SYNTHETIC_XBRL = _FIXTURES / "synthetic_q1_fy25_consolidated.xml"

_SYMBOL = "SYNTH"
_ISSUER_NAME = "Synthetic Test Corp"
_Q1 = "FY27_Q1"
_Q2 = "FY27_Q2"
_Q3 = "FY27_Q3"
_HORIZON = "FY27"
_MARGIN = "synth_margin"
_GROWTH = "synth_growth"
_PERCENT = "%"
_RETRIEVED_AT = datetime(2027, 7, 25, tzinfo=UTC)
_LEDGER_RELATIVE = "data/ledger/synth-management-ledger.json"

_CRORE = "INR crore"
_PER_SHARE = "INR per share"
_ROLE_QNAMES: dict[FactRole, str] = {
    FactRole.REVENUE: "in-bse-fin:RevenueFromOperations",
    FactRole.TOTAL_INCOME: "in-bse-fin:Income",
    FactRole.TOTAL_EXPENSES: "in-bse-fin:Expenses",
    FactRole.PROFIT_BEFORE_TAX: "in-bse-fin:ProfitBeforeTax",
    FactRole.PROFIT_FOR_PERIOD: "in-bse-fin:ProfitLossForPeriod",
    FactRole.BASIC_EPS: "in-bse-fin:BasicEarningsLossPerShare",
}
_FACT_VALUES: dict[FactRole, Decimal] = {
    FactRole.REVENUE: Decimal("1000"),
    FactRole.TOTAL_INCOME: Decimal("1020"),
    FactRole.TOTAL_EXPENSES: Decimal("820"),
    FactRole.PROFIT_BEFORE_TAX: Decimal("200"),
    FactRole.PROFIT_FOR_PERIOD: Decimal("150"),
    FactRole.BASIC_EPS: Decimal("12.50"),
}

_Q1_MARGIN_QUOTE = "we expect a synthetic margin of 10% to 12% for FY27"
_Q2_MARGIN_QUOTE = "we reiterate a synthetic margin of 10% to 12% for FY27"
_Q1_GROWTH_QUOTE = "synthetic growth guidance of 5% to 7% for FY27"


# --- synthetic builders over contracts that already exist (safe at module scope) ---


def _provenance(quarter: str, *, page: int = 4, block: int = 2) -> Provenance:
    """One synthetic transcript span anchor, distinct per quarter."""
    return Provenance(
        source_id=f"synth-transcript-{quarter.lower()}",
        file_sha256=hashlib.sha256(quarter.encode()).hexdigest(),
        anchor_type=SourceAnchorType.PDF_SPAN,
        page=page,
        block=block,
        span="0:48",
        retrieved_at=_RETRIEVED_AT,
    )


def _claim(
    metric: str,
    lower: str,
    upper: str,
    quarter: str,
    *,
    quote: str,
    unit: str = _PERCENT,
) -> GuidanceClaim:
    """One synthetic quote-anchored guidance claim for ``quarter``."""
    return GuidanceClaim(
        metric=metric,
        lower_bound=Decimal(lower),
        upper_bound=Decimal(upper),
        unit=unit,
        constant_currency=False,
        horizon=_HORIZON,
        scope=Scope.CONSOLIDATED,
        epistemic_class=EpistemicClass.FORECAST,
        source_quote=quote,
        provenance=_provenance(quarter),
    )


def _margin_claim(lower: str, upper: str, quarter: str, quote: str) -> GuidanceClaim:
    """The tracked margin commitment as restated in ``quarter``."""
    return _claim(_MARGIN, lower, upper, quarter, quote=quote)


def _fact(role: FactRole) -> RenderedFact:
    """One rendered P&L fact so the §5 render is reachable through a valid update."""
    return RenderedFact(
        role=role,
        concept_qname=_ROLE_QNAMES[role],
        value=_FACT_VALUES[role],
        unit=_PER_SHARE if role is FactRole.BASIC_EPS else _CRORE,
        reconciliation_status=ReconciliationStatus.CROSS_SOURCE_CONFIRMED,
        sources=(_provenance(_Q3, page=1, block=int(role is FactRole.BASIC_EPS)),),
    )


def _guidance_pdf(sentence: str) -> LoadedPdf:
    """A one-block synthetic transcript page carrying ``sentence``."""
    block = PdfBlock(number=3, text=sentence)
    page = PdfPage(page_number=2, text=sentence, words=(), blocks=(block,))
    return LoadedPdf(
        source_id="synth-transcript-fy27_q1",
        file_sha256="ab" * 32,
        page_count=1,
        pages=(page,),
    )


def _section_five(markdown: str) -> list[str]:
    """Return the body lines of the rendered §5 management_ledger section."""
    lines = markdown.splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "## 5. management_ledger")
    body: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("## "):
            break
        body.append(line)
    return body


def _line_with(lines: list[str], token: str) -> str:
    """The single §5 bullet carrying ``token`` — one entry per status by construction."""
    matches = [line for line in lines if token in line]
    assert len(matches) == 1, f"expected exactly one §5 line containing {token!r}: {matches}"
    return matches[0]


# --- helpers touching names that do not exist yet (never imported at module scope) ---


def _reconcile(prior: Any, quarter: str, claims: list[GuidanceClaim]) -> Any:
    """Reconcile ``claims`` for ``quarter`` against ``prior`` via the new module."""
    from fundamentals.output.management_ledger import reconcile_ledger

    return reconcile_ledger(prior, symbol=_SYMBOL, issuer_quarter=quarter, claims=claims)


def _entry_by_metric(ledger: Any, metric: str) -> Any:
    """The single ledger entry tracking ``metric``."""
    matches = [entry for entry in ledger.entries if entry.metric == metric]
    assert len(matches) == 1, f"expected one entry for {metric!r}, got {len(matches)}"
    return matches[0]


def _rule_from_config(rule_config: GuidanceRuleConfig) -> Any:
    """Build the extractor rule from config the way the pipeline must, unit included."""
    from fundamentals.extract.guidance_extractor import GuidanceRule

    return GuidanceRule(
        metric=rule_config.metric,
        pattern=rule_config.pattern,
        horizon=rule_config.horizon,
        unit=rule_config.unit,
    )


def _extract_one(rule_config: GuidanceRuleConfig, sentence: str) -> GuidanceClaim:
    """Extract the single claim ``rule_config`` yields from ``sentence``."""
    from fundamentals.extract.guidance_extractor import extract_guidance_claims

    claims = extract_guidance_claims(
        _guidance_pdf(sentence),
        rules=(_rule_from_config(rule_config),),
        retrieved_at=_RETRIEVED_AT,
    )
    assert len(claims) == 1, f"rule {rule_config.metric!r} did not match once: {claims}"
    return claims[0]


def _ledger_for_render() -> Any:
    """A four-entry ledger, one per status, as of FY27_Q3."""
    from fundamentals.output.management_ledger import (
        LedgerAnchor,
        LedgerEntry,
        LedgerRevision,
        LedgerStatus,
        ManagementLedger,
    )

    def anchor(quarter: str, quote: str) -> Any:
        return LedgerAnchor(issuer_quarter=quarter, quote=quote, source=_provenance(quarter))

    def entry(
        metric: str,
        lower: str,
        upper: str,
        status: Any,
        first: Any,
        latest: Any,
        history: tuple[Any, ...] = (),
    ) -> Any:
        return LedgerEntry(
            claim_key=f"{metric}|{_HORIZON}|{Scope.CONSOLIDATED}",
            metric=metric,
            lower_bound=Decimal(lower),
            upper_bound=Decimal(upper),
            unit=_PERCENT,
            constant_currency=False,
            horizon=_HORIZON,
            scope=Scope.CONSOLIDATED,
            first=first,
            latest=latest,
            status=status,
            history=history,
        )

    q1_margin = anchor(_Q1, _Q1_MARGIN_QUOTE)
    q3_margin = anchor(_Q3, "we now see a synthetic margin of 13% to 15% for FY27")
    q1_growth = anchor(_Q1, _Q1_GROWTH_QUOTE)
    q3_growth = anchor(_Q3, "synthetic growth guidance stays at 5% to 7% for FY27")
    q1_capex = anchor(_Q1, "synthetic capex intensity of 3% to 4% of revenue")
    q3_new = anchor(_Q3, "a new synthetic utilisation target of 8% to 9%")
    return ManagementLedger(
        symbol=_SYMBOL,
        version=3,
        updated_quarter=_Q3,
        entries=(
            entry("synth_utilisation", "8", "9", LedgerStatus.NEW, q3_new, q3_new),
            entry(_GROWTH, "5", "7", LedgerStatus.REAFFIRMED, q1_growth, q3_growth),
            entry(
                _MARGIN,
                "13",
                "15",
                LedgerStatus.MODIFIED,
                q1_margin,
                q3_margin,
                (
                    LedgerRevision(
                        issuer_quarter=_Q1,
                        lower_bound=Decimal("10"),
                        upper_bound=Decimal("12"),
                        status=LedgerStatus.NEW,
                    ),
                ),
            ),
            entry("synth_capex", "3", "4", LedgerStatus.CARRIED, q1_capex, q1_capex),
        ),
    )


def _update_with_ledger(ledger: Any) -> EarningsUpdate:
    """A synthetic earnings update whose §5 must render from ``ledger``."""
    return EarningsUpdate(
        issuer_name=_ISSUER_NAME,
        nse_symbol=_SYMBOL,
        issuer_quarter_label="Q3 FY27",
        period_start="2026-10-01",
        period_end="2026-12-31",
        knowledge_cutoff="2027-01-20",
        facts=tuple(_fact(role) for role in _ROLE_QNAMES),
        guidance=(),
        calculations=(),
        cross_check=VerificationOutcome(passed_count=6, total_count=6),
        cross_foot=VerificationOutcome(passed_count=2, total_count=2),
        sec_cross_check_note="not applicable for this synthetic issuer",
        ledger=ledger,
    )


def _deterministic_xbrl_input(config: FundamentalsConfig) -> XbrlInput:
    """The committed synthetic XBRL instance, as the end-to-end fixture uses it."""
    xml_bytes = _SYNTHETIC_XBRL.read_bytes()
    return XbrlInput(
        xml_bytes=xml_bytes,
        file_sha256=hashlib.sha256(xml_bytes).hexdigest(),
        source_id=config.xbrl.source_id,
        retrieved_at=config.quarter.knowledge_cutoff,
    )


def _run(config: FundamentalsConfig) -> None:
    """Run the deterministic pipeline once against an in-memory store."""
    store = FactStore(":memory:")
    try:
        run_pipeline(
            config=config,
            xbrl_input=_deterministic_xbrl_input(config),
            results_pdf_path=str(config.results_pdf_path(_CONFIG_PATH)),
            results_pdf_sha256=config.results_pdf.sha256,
            transcript_pdf_path=str(config.transcript_pdf_path(_CONFIG_PATH)),
            transcript_pdf_sha256=config.transcript_pdf.sha256,
            store=store,
        )
    finally:
        store.close()


def _config_with_ledger(ledger_path: Path) -> FundamentalsConfig:
    """The committed deterministic config, pointed at ``ledger_path``."""
    return load_config(_CONFIG_PATH).model_copy(update={"ledger_path": str(ledger_path)})


# --- tests ---


def test_first_quarter_entries_are_new() -> None:
    # A commitment nobody has tracked before must enter the ledger as NEW with this
    # quarter's transcript anchor on both ends — that anchor is what sD later judges.
    ledger = _reconcile(None, _Q1, [_margin_claim("10", "12", _Q1, _Q1_MARGIN_QUOTE)])

    from fundamentals.output.management_ledger import LedgerStatus

    assert ledger.symbol == _SYMBOL
    assert ledger.version == 1
    assert ledger.updated_quarter == _Q1
    entry = _entry_by_metric(ledger, _MARGIN)
    assert entry.status is LedgerStatus.NEW
    assert entry.claim_key == f"{_MARGIN}|{_HORIZON}|{Scope.CONSOLIDATED}"
    assert (entry.lower_bound, entry.upper_bound) == (Decimal("10"), Decimal("12"))
    assert entry.first.issuer_quarter == _Q1
    assert entry.latest.issuer_quarter == _Q1
    assert entry.first.quote == _Q1_MARGIN_QUOTE
    assert entry.first.source == _provenance(_Q1)


def test_identical_restatement_is_reaffirmed_with_latest_anchor() -> None:
    # Re-stating the same range must keep the ORIGINAL quarter's anchor as ``first``
    # (that is when the commitment was made) while recording the fresh restatement.
    prior = _reconcile(None, _Q1, [_margin_claim("10", "12", _Q1, _Q1_MARGIN_QUOTE)])
    ledger = _reconcile(prior, _Q2, [_margin_claim("10", "12", _Q2, _Q2_MARGIN_QUOTE)])

    from fundamentals.output.management_ledger import LedgerStatus

    assert ledger.version == 2
    assert ledger.updated_quarter == _Q2
    assert len(ledger.entries) == 1
    entry = _entry_by_metric(ledger, _MARGIN)
    assert entry.status is LedgerStatus.REAFFIRMED
    assert (entry.lower_bound, entry.upper_bound) == (Decimal("10"), Decimal("12"))
    assert entry.first.issuer_quarter == _Q1
    assert entry.first.quote == _Q1_MARGIN_QUOTE
    assert entry.latest.issuer_quarter == _Q2
    assert entry.latest.quote == _Q2_MARGIN_QUOTE
    assert entry.latest.source == _provenance(_Q2)


def test_changed_bounds_are_modified_with_history() -> None:
    # A moved goalpost must not silently replace the old one: the superseded bounds
    # stay in history, so a later reader can see the commitment was changed.
    prior = _reconcile(None, _Q1, [_margin_claim("10", "12", _Q1, _Q1_MARGIN_QUOTE)])
    new_quote = "we now see a synthetic margin of 13% to 15% for FY27"
    ledger = _reconcile(prior, _Q2, [_margin_claim("13", "15", _Q2, new_quote)])

    from fundamentals.output.management_ledger import LedgerStatus

    entry = _entry_by_metric(ledger, _MARGIN)
    assert entry.status is LedgerStatus.MODIFIED
    assert (entry.lower_bound, entry.upper_bound) == (Decimal("13"), Decimal("15"))
    assert entry.first.issuer_quarter == _Q1
    assert entry.latest.issuer_quarter == _Q2
    assert entry.latest.quote == new_quote
    superseded = [
        revision
        for revision in entry.history
        if (revision.lower_bound, revision.upper_bound) == (Decimal("10"), Decimal("12"))
    ]
    assert len(superseded) == 1, f"old bounds must survive in history: {entry.history}"
    assert superseded[0].issuer_quarter == _Q1


def test_unrestated_entry_is_carried_and_never_deleted() -> None:
    # Silence is evidence too: a commitment management stopped repeating must stay in
    # the ledger, marked CARRIED, with the quarter it was not restated in recorded.
    prior = _reconcile(
        None,
        _Q1,
        [
            _margin_claim("10", "12", _Q1, _Q1_MARGIN_QUOTE),
            _claim(_GROWTH, "5", "7", _Q1, quote=_Q1_GROWTH_QUOTE),
        ],
    )
    ledger = _reconcile(prior, _Q2, [_margin_claim("10", "12", _Q2, _Q2_MARGIN_QUOTE)])

    from fundamentals.output.management_ledger import LedgerStatus

    assert len(ledger.entries) == 2, "nothing is ever deleted from the ledger"
    carried = _entry_by_metric(ledger, _GROWTH)
    assert carried.status is LedgerStatus.CARRIED
    assert (carried.lower_bound, carried.upper_bound) == (Decimal("5"), Decimal("7"))
    assert carried.first.issuer_quarter == _Q1
    assert carried.latest.issuer_quarter == _Q1, "an unrestated claim gains no new anchor"
    assert carried.latest.quote == _Q1_GROWTH_QUOTE
    assert any(
        revision.issuer_quarter == _Q2 and revision.status is LedgerStatus.CARRIED
        for revision in carried.history
    ), f"history must note the quarter it was not restated in: {carried.history}"


def test_duplicate_claim_keys_rejected() -> None:
    # Two ranges for the same metric/horizon/scope make "was it met?" unanswerable, so
    # reconciliation fails closed instead of picking one silently.
    with pytest.raises(ValueError):
        _reconcile(
            None,
            _Q1,
            [
                _margin_claim("10", "12", _Q1, _Q1_MARGIN_QUOTE),
                _margin_claim("13", "15", _Q1, "a second synthetic margin sentence"),
            ],
        )


def test_earlier_quarter_cannot_overwrite_later_ledger() -> None:
    # Re-running an old quarter must never rewind the ledger to a stale state.
    prior = _reconcile(None, _Q2, [_margin_claim("10", "12", _Q2, _Q2_MARGIN_QUOTE)])

    with pytest.raises(ValueError):
        _reconcile(prior, _Q1, [_margin_claim("10", "12", _Q1, _Q1_MARGIN_QUOTE)])
    with pytest.raises(ValueError):
        _reconcile(prior, _Q2, [_margin_claim("10", "12", _Q2, _Q2_MARGIN_QUOTE)])


def test_ledger_round_trips_through_json(tmp_path: Path) -> None:
    # The ledger is the only carrier of cross-quarter memory: it must survive the disk
    # round trip exactly, and a failed write must never leave a truncated ledger.
    from fundamentals.output.management_ledger import load_ledger, save_ledger

    ledger = _reconcile(None, _Q1, [_margin_claim("10", "12", _Q1, _Q1_MARGIN_QUOTE)])
    path = tmp_path / "synth-ledger.json"

    assert load_ledger(path) is None, "an absent ledger is a first quarter, not an error"
    save_ledger(ledger, path)
    assert load_ledger(path) == ledger

    blocker = tmp_path / "blocker.json"
    blocker.write_text("not a directory", encoding="utf-8")
    unwritable = blocker / "synth-ledger.json"
    with pytest.raises(OSError):
        save_ledger(ledger, unwritable)
    assert not unwritable.exists(), "a failed write must leave no partial ledger"
    assert blocker.read_text(encoding="utf-8") == "not a directory"


def test_renderer_section_five_shows_status_and_both_anchors() -> None:
    # §5 is the reader-facing contract: every carried commitment shows its status and
    # both ends of its evidence, so no status claim is made without an anchor.
    markdown = render_earnings_update(_update_with_ledger(_ledger_for_render()))
    section = _section_five(markdown)

    new_line = _line_with(section, "NEW")
    assert "8–9%" in new_line
    assert f"first quoted {_Q3}" in new_line

    reaffirmed = _line_with(section, "REAFFIRMED")
    assert f"first quoted {_Q1}" in reaffirmed
    assert f"restated {_Q3}" in reaffirmed
    markers = re.findall(r"\[\^\d+\]", reaffirmed)
    assert len(markers) == 2, f"both anchors must be footnoted: {reaffirmed}"
    assert markers[0] != markers[1], "first and latest anchors are distinct sources"

    modified = _line_with(section, "MODIFIED")
    assert "13–15%" in modified
    assert "(was 10–12)" in modified

    carried = _line_with(section, "CARRIED")
    assert f"not restated in {_Q3}" in carried


def test_pipeline_writes_ledger_only_after_gates_pass(tmp_path: Path) -> None:
    # The ledger is committed state: a run that fails an integrity gate must not leave
    # a ledger claiming the quarter was processed.
    passed_path = tmp_path / "passed-ledger.json"
    _run(_config_with_ledger(passed_path))
    assert passed_path.is_file(), "a fully-gated run commits the ledger"
    payload = json.loads(passed_path.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert payload["entries"], "a run with anchored guidance records at least one entry"

    failed_path = tmp_path / "failed-ledger.json"
    config = _config_with_ledger(failed_path)
    corrupted = config.model_copy(
        update={"transcript_pdf": config.transcript_pdf.model_copy(update={"sha256": "00" * 32})}
    )
    with pytest.raises(PdfIntegrityError):
        _run(corrupted)
    assert not failed_path.exists(), "a failed gate must leave no ledger on disk"


def test_config_ledger_path_optional(tmp_path: Path) -> None:
    # Issuers without a tracked ledger must keep working unchanged; those with one get a
    # repo-relative path resolved the same way every other held path is.
    raw: dict[str, Any] = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8"))
    raw.pop("ledger_path", None)
    without = tmp_path / "without-ledger.yaml"
    without.write_text(yaml.safe_dump(raw), encoding="utf-8")
    config_without = load_config(without)
    assert config_without.ledger_path is None
    assert config_without.ledger_path_resolved(without) is None

    raw["ledger_path"] = _LEDGER_RELATIVE
    with_ledger = tmp_path / "with-ledger.yaml"
    with_ledger.write_text(yaml.safe_dump(raw), encoding="utf-8")
    config_with = load_config(with_ledger)
    assert config_with.ledger_path == _LEDGER_RELATIVE
    assert config_with.ledger_path_resolved(with_ledger) == (
        config_with.repo_root(with_ledger) / _LEDGER_RELATIVE
    )


def test_point_guidance_rule_yields_equal_bounds_with_unit() -> None:
    # Real filers commit to a point ("about 30,000 per MT"), not always a range: one
    # capture group must yield lower == upper, thousands separators stripped, unit kept.
    rule_config = GuidanceRuleConfig(
        metric="synth_realisation",
        label="Synthetic realisation guidance",
        pattern=r"realisation guidance of about ([\d,]+) per MT",
        horizon=_HORIZON,
        unit="INR per MT",
    )
    sentence = "Management sees a realisation guidance of about 30,000 per MT through FY27."

    claim = _extract_one(rule_config, sentence)

    assert claim.lower_bound == Decimal("30000")
    assert claim.upper_bound == Decimal("30000")
    assert claim.unit == "INR per MT"


def test_two_group_rule_keeps_percent_default() -> None:
    # Adding the unit must not change the existing two-group behaviour: a rule that
    # omits ``unit`` still reports both bounds as a percentage range.
    rule_config = GuidanceRuleConfig(
        metric=_MARGIN,
        label="Synthetic margin guidance",
        pattern=r"synthetic margin guidance.*?(\d+)% to (\d+)%",
        horizon=_HORIZON,
    )
    sentence = "Our synthetic margin guidance stays at 10% to 12% for the year."

    claim = _extract_one(rule_config, sentence)

    assert claim.lower_bound == Decimal("10")
    assert claim.upper_bound == Decimal("12")
    assert claim.unit == _PERCENT
