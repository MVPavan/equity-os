"""Slice phase05-sD — metric registry, predicate registry, falsifier evaluator, CLI.

Acceptance tests for four modules that do not exist yet:
``fundamentals.verify.metric_registry``, ``fundamentals.verify.thesis_predicates``,
``fundamentals.verify.thesis_impact`` and ``fundamentals.api.thesis_impact_cli``. Every
import of those four happens *inside* a test (or a helper a test calls), so each node id
fails on its own ``ModuleNotFoundError`` instead of one module-level import collapsing
the file into a single collection error.

All data is synthetic: symbol ``SYNTH``, a 2027 quarter, invented rupee values, and a
made-up thesis file written under ``tmp_path``. No held filing bytes, no network.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from fundamentals.contracts.comparative import ComparativeChange, ComparatorKind, ConceptComparative
from fundamentals.contracts.fact import ReconciliationStatus
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.contracts.role import FactRole
from fundamentals.output.earnings_update import (
    EarningsUpdate,
    RenderedFact,
    VerificationOutcome,
    anchor_label,
)

_SYMBOL = "SYNTH"
_OTHER_SYMBOL = "OTHERSYN"
_ISSUER_NAME = "Synthetic Test Corp"
_QUARTER_LABEL = "Q1FY28"
_PERIOD_START = "2027-04-01"
_PERIOD_END = "2027-06-30"
_KNOWLEDGE_CUTOFF = "2027-07-25"
_RETRIEVED_AT = datetime(2027, 7, 25, tzinfo=UTC)

_CRORE = "INR crore"
_PER_SHARE = "INR per share"
_XBRL_SOURCE_ID = "synthetic-nse-xbrl"
_PDF_SOURCE_ID = "synthetic-issuer-pdf"

_ROLE_QNAMES: dict[FactRole, str] = {
    FactRole.REVENUE: "in-bse-fin:RevenueFromOperations",
    FactRole.TOTAL_INCOME: "in-bse-fin:Income",
    FactRole.TOTAL_EXPENSES: "in-bse-fin:Expenses",
    FactRole.PROFIT_BEFORE_TAX: "in-bse-fin:ProfitBeforeTax",
    FactRole.PROFIT_FOR_PERIOD: "in-bse-fin:ProfitLossForPeriod",
    FactRole.BASIC_EPS: "in-bse-fin:BasicEarningsLossPerShare",
}

# Synthetic P&L: PBT margin 20%, PAT margin 15%, effective tax rate 25%.
_FACT_VALUES: dict[FactRole, Decimal] = {
    FactRole.REVENUE: Decimal("1000"),
    FactRole.TOTAL_INCOME: Decimal("1020"),
    FactRole.TOTAL_EXPENSES: Decimal("820"),
    FactRole.PROFIT_BEFORE_TAX: Decimal("200"),
    FactRole.PROFIT_FOR_PERIOD: Decimal("150"),
    FactRole.BASIC_EPS: Decimal("12.50"),
}

_QOQ_START = date(2027, 1, 1)
_QOQ_END = date(2027, 3, 31)
_YOY_START = date(2026, 4, 1)
_YOY_END = date(2026, 6, 30)
_QOQ_PERCENT_TRACE = "QoQ % trace: (1000 − 800) / 800 × 100"
_YOY_PERCENT_TRACE = "YoY % trace: (1000 − 500) / 500 × 100"
_NO_PRIOR_FILING = "no prior filing was retained for the comparator period"

_FACT_METRIC_IDS: tuple[str, ...] = (
    "revenue_crore",
    "total_income_crore",
    "total_expenses_crore",
    "pbt_crore",
    "pat_crore",
    "eps_basic_inr",
)
_COMPARATIVE_METRIC_IDS: tuple[str, ...] = (
    "revenue_qoq_pct",
    "revenue_yoy_pct",
    "pbt_qoq_pct",
    "pbt_yoy_pct",
    "pat_qoq_pct",
    "pat_yoy_pct",
    "eps_yoy_pct",
)
_DERIVED_METRIC_IDS: tuple[str, ...] = (
    "pbt_margin_pct",
    "pat_margin_pct",
    "effective_tax_rate_pct",
)
_UNREGISTERED_METRIC_ID = "synthetic_free_cash_flow_pct"


# --- synthetic builders (existing contracts only, so they may import at module level) ---


def _provenance(source_id: str, context_ref: str) -> Provenance:
    """One synthetic XBRL-context anchor."""
    return Provenance(
        source_id=source_id,
        file_sha256="ab" * 32,
        anchor_type=SourceAnchorType.XBRL_CONTEXT,
        context_ref=context_ref,
        retrieved_at=_RETRIEVED_AT,
    )


def _fact(role: FactRole, value: Decimal | None = None) -> RenderedFact:
    """One rendered P&L fact for ``role``, anchored to one synthetic source."""
    unit = _PER_SHARE if role is FactRole.BASIC_EPS else _CRORE
    return RenderedFact(
        role=role,
        concept_qname=_ROLE_QNAMES[role],
        value=_FACT_VALUES[role] if value is None else value,
        unit=unit,
        reconciliation_status=ReconciliationStatus.CROSS_SOURCE_CONFIRMED,
        sources=(_provenance(_XBRL_SOURCE_ID, f"ctx-{role.value}"),),
    )


def _all_facts(**overrides: Decimal) -> tuple[RenderedFact, ...]:
    """The six P&L facts, with any role's value overridden by keyword."""
    return tuple(_fact(role, overrides.get(role.value)) for role in _ROLE_QNAMES)


def _facts_without(dropped: FactRole) -> tuple[RenderedFact, ...]:
    """The P&L facts with one role absent, so its metric cannot resolve."""
    return tuple(fact for fact in _all_facts() if fact.role is not dropped)


def _available_change(
    kind: ComparatorKind,
    prior: Decimal,
    percent: Decimal,
    percent_trace: str,
) -> ComparativeChange:
    """A sourced prior value with its absolute and percent traces."""
    start, end = (_QOQ_START, _QOQ_END) if kind is ComparatorKind.QOQ else (_YOY_START, _YOY_END)
    current = _FACT_VALUES[FactRole.REVENUE]
    return ComparativeChange(
        kind=kind,
        period_start=start,
        period_end=end,
        prior_value=prior,
        absolute_change=current - prior,
        percent_change=percent,
        absolute_trace=f"{current} − {prior}",
        percent_trace=percent_trace,
        prior_source=_provenance(_PDF_SOURCE_ID, f"ctx-prior-{kind.value}"),
    )


def _unavailable_change(kind: ComparatorKind) -> ComparativeChange:
    """A comparator that was never sourced, carrying only its explicit reason."""
    start, end = (_QOQ_START, _QOQ_END) if kind is ComparatorKind.QOQ else (_YOY_START, _YOY_END)
    return ComparativeChange(
        kind=kind,
        period_start=start,
        period_end=end,
        unavailable_reason=_NO_PRIOR_FILING,
    )


def _revenue_comparative(*, qoq_available: bool = True) -> ConceptComparative:
    """Revenue's QoQ/YoY comparative, optionally with an unavailable QoQ leg."""
    qoq = (
        _available_change(ComparatorKind.QOQ, Decimal("800"), Decimal("25"), _QOQ_PERCENT_TRACE)
        if qoq_available
        else _unavailable_change(ComparatorKind.QOQ)
    )
    return ConceptComparative(
        concept_qname=_ROLE_QNAMES[FactRole.REVENUE],
        current_value=_FACT_VALUES[FactRole.REVENUE],
        unit=_CRORE,
        current_sources=(_provenance(_XBRL_SOURCE_ID, "ctx-revenue"),),
        qoq=qoq,
        yoy=_available_change(
            ComparatorKind.YOY, Decimal("500"), Decimal("100"), _YOY_PERCENT_TRACE
        ),
    )


def _update(
    *,
    facts: tuple[RenderedFact, ...] | None = None,
    comparatives: tuple[ConceptComparative, ...] = (),
    symbol: str = _SYMBOL,
) -> EarningsUpdate:
    """A synthetic SYNTH Q1FY28 earnings update — the evaluator's only fact input."""
    return EarningsUpdate(
        issuer_name=_ISSUER_NAME,
        nse_symbol=symbol,
        issuer_quarter_label=_QUARTER_LABEL,
        period_start=_PERIOD_START,
        period_end=_PERIOD_END,
        knowledge_cutoff=_KNOWLEDGE_CUTOFF,
        facts=_all_facts() if facts is None else facts,
        comparatives=comparatives,
        comparatives_attempted=bool(comparatives),
        guidance=(),
        calculations=(),
        cross_check=VerificationOutcome(passed_count=6, total_count=6),
        cross_foot=VerificationOutcome(passed_count=2, total_count=2),
        sec_cross_check_note="not applicable for this synthetic issuer",
    )


# --- helpers that import the not-yet-existing modules (kept out of module scope) ---


def _resolve(update: EarningsUpdate, metric_id: str) -> Any:
    """Resolve one metric against an update via the not-yet-written registry."""
    from fundamentals.verify.metric_registry import resolve_metric

    return resolve_metric(update, metric_id)


def _predicate(
    metric_id: str,
    op_name: str,
    *,
    threshold: str | None = None,
    band: tuple[str, str] | None = None,
) -> Any:
    """Build one falsifier predicate, naming the op by its registry member name."""
    from fundamentals.verify.thesis_predicates import FalsifierPredicate, PredicateOp

    return FalsifierPredicate(
        metric_id=metric_id,
        op=PredicateOp[op_name],
        threshold=None if threshold is None else Decimal(threshold),
        band=None if band is None else (Decimal(band[0]), Decimal(band[1])),
    )


def _falsifier(falsifier_id: str, statement: str, predicate: Any) -> Any:
    """Bind one analyst statement to one registered predicate."""
    from fundamentals.verify.thesis_predicates import ThesisFalsifier

    return ThesisFalsifier(falsifier_id=falsifier_id, statement=statement, predicate=predicate)


def _thesis(falsifiers: tuple[Any, ...], *, symbol: str = _SYMBOL) -> Any:
    """An approved thesis built in-process (the loader is exercised separately)."""
    from fundamentals.verify.thesis_predicates import ApprovedThesis

    return ApprovedThesis(
        symbol=symbol,
        version="2027.1",
        approved_by="synthetic-analyst",
        approved_at=date(2027, 7, 25),
        stance="constructive on synthetic order book",
        assumptions=("synthetic assumption: PBT margin stays above 12%",),
        falsifiers=falsifiers,
        open_questions=("synthetic open question: does the order book convert?",),
        content_sha256="cd" * 32,
    )


def _single(statement: str, predicate: Any, *, falsifier_id: str, symbol: str = _SYMBOL) -> Any:
    """An approved thesis carrying exactly one falsifier."""
    return _thesis((_falsifier(falsifier_id, statement, predicate),), symbol=symbol)


def _evaluate(update: EarningsUpdate, thesis: Any) -> Any:
    """Run the falsifier evaluator."""
    from fundamentals.verify.thesis_impact import evaluate_thesis

    return evaluate_thesis(update, thesis)


def _by_id(impact: Any) -> dict[str, Any]:
    """Index an impact's evaluations by falsifier id."""
    return {evaluation.falsifier_id: evaluation for evaluation in impact.evaluations}


def _count(impact: Any, disposition: Any) -> int:
    """Read one disposition count, tolerating enum-keyed or string-keyed counts."""
    for key, value in dict(impact.counts).items():
        if str(key) == str(disposition):
            return int(value)
    return 0


# --- thesis YAML written under tmp_path (loader + CLI) ---

_MARGIN_HOLDS_BLOCK = """  - falsifier_id: f_margin_collapse
    statement: "PBT margin prints below 12% in any FY28 quarter"
    predicate:
      metric_id: pbt_margin_pct
      op: LT
      threshold: "12"
"""
_MARGIN_FIRES_BLOCK = """  - falsifier_id: f_margin_collapse
    statement: "PBT margin prints below 25% in any FY28 quarter"
    predicate:
      metric_id: pbt_margin_pct
      op: LT
      threshold: "25"
"""
_TAX_BAND_BLOCK = """  - falsifier_id: f_tax_band
    statement: "Effective tax rate leaves the 20-30% band"
    predicate:
      metric_id: effective_tax_rate_pct
      op: OUTSIDE_BAND
      band: ["20", "30"]
"""
_UNKNOWN_OP_BLOCK = """  - falsifier_id: f_unknown_op
    statement: "PBT margin sits between two numbers"
    predicate:
      metric_id: pbt_margin_pct
      op: BETWEEN
      threshold: "12"
"""
_DUPLICATE_ID_BLOCK = (
    _MARGIN_HOLDS_BLOCK
    + """  - falsifier_id: f_margin_collapse
    statement: "PAT margin prints below 5% in any FY28 quarter"
    predicate:
      metric_id: pat_margin_pct
      op: LT
      threshold: "5"
"""
)


def _write_thesis(path: Path, falsifier_blocks: str, *, symbol: str = _SYMBOL) -> Path:
    """Write a made-up approved-thesis YAML file and return its path."""
    path.write_text(
        "symbol: " + symbol + "\n"
        'version: "2027.1"\n'
        "approved_by: synthetic-analyst\n"
        "approved_at: 2027-07-25\n"
        "stance: constructive on synthetic order book\n"
        "assumptions:\n"
        '  - "synthetic assumption: PBT margin stays above 12%"\n'
        "falsifiers:\n" + falsifier_blocks + "open_questions:\n"
        '  - "synthetic open question: does the order book convert?"\n',
        encoding="utf-8",
    )
    return path


def test_registry_versions_and_kinds_validate() -> None:
    """WHY: B-12 requires pinned registry versions and kind-complete definitions."""
    from fundamentals.verify.metric_registry import (
        METRIC_REGISTRY_VERSION,
        REGISTRY,
        MetricDefinition,
        MetricKind,
    )
    from fundamentals.verify.thesis_predicates import PREDICATE_REGISTRY_VERSION

    assert METRIC_REGISTRY_VERSION == "2026-09-07.1"
    assert PREDICATE_REGISTRY_VERSION == "2026-09-07.1"

    for metric_id in _FACT_METRIC_IDS:
        assert REGISTRY[metric_id].kind is MetricKind.FACT
    for metric_id in _COMPARATIVE_METRIC_IDS:
        assert REGISTRY[metric_id].kind is MetricKind.COMPARATIVE
    for metric_id in _DERIVED_METRIC_IDS:
        assert REGISTRY[metric_id].kind is MetricKind.DERIVED
    assert all(metric_id == definition.metric_id for metric_id, definition in REGISTRY.items())
    assert REGISTRY[_FACT_METRIC_IDS[0]].role is FactRole.REVENUE

    with pytest.raises(ValueError):
        MetricDefinition(
            metric_id="synthetic_bad_derived",
            label="Derived without its roles",
            unit="percent",
            kind=MetricKind.DERIVED,
        )


def test_fact_metric_resolves_with_sources() -> None:
    """WHY: a metric may only carry a number it can hand back the source anchors for."""
    from fundamentals.verify.metric_registry import REGISTRY, MetricValue

    resolved = _resolve(_update(), "revenue_crore")

    assert isinstance(resolved, MetricValue)
    assert resolved.metric_id == "revenue_crore"
    assert resolved.value == Decimal("1000")
    assert resolved.unit == REGISTRY["revenue_crore"].unit
    assert [source.source_id for source in resolved.sources] == [_XBRL_SOURCE_ID]
    assert "1000" in resolved.trace


def test_comparative_metric_uses_percent_trace() -> None:
    """WHY: a percent change must reuse the comparator's own audited trace, not a new one."""
    from fundamentals.verify.metric_registry import MetricValue

    update = _update(comparatives=(_revenue_comparative(),))

    qoq = _resolve(update, "revenue_qoq_pct")
    yoy = _resolve(update, "revenue_yoy_pct")

    assert isinstance(qoq, MetricValue)
    assert isinstance(yoy, MetricValue)
    assert qoq.value == Decimal("25")
    assert yoy.value == Decimal("100")
    assert _QOQ_PERCENT_TRACE in qoq.trace
    assert _YOY_PERCENT_TRACE in yoy.trace
    assert "percent" in qoq.unit


def test_unavailable_comparative_is_unresolved() -> None:
    """WHY: an unsourced comparator must surface its own reason, never a fabricated 0%."""
    from fundamentals.verify.metric_registry import MetricUnavailable

    update = _update(comparatives=(_revenue_comparative(qoq_available=False),))

    resolved = _resolve(update, "revenue_qoq_pct")

    assert isinstance(resolved, MetricUnavailable)
    assert resolved.metric_id == "revenue_qoq_pct"
    assert _NO_PRIOR_FILING in resolved.reason


def test_derived_metric_computes_ratio() -> None:
    """WHY: a ratio falsifier must be computed from the sourced facts, both anchors kept."""
    from fundamentals.verify.metric_registry import MetricValue

    update = _update()

    pbt_margin = _resolve(update, "pbt_margin_pct")
    pat_margin = _resolve(update, "pat_margin_pct")
    tax_rate = _resolve(update, "effective_tax_rate_pct")

    assert isinstance(pbt_margin, MetricValue)
    assert isinstance(pat_margin, MetricValue)
    assert isinstance(tax_rate, MetricValue)
    assert pbt_margin.value == Decimal("20")
    assert pat_margin.value == Decimal("15")
    assert tax_rate.value == Decimal("25")
    context_refs = {source.context_ref for source in pbt_margin.sources}
    assert {"ctx-revenue", "ctx-profit_before_tax"} <= context_refs


def test_derived_zero_denominator_unavailable() -> None:
    """WHY: a zero denominator must fail closed, not raise or emit an invented ratio."""
    from fundamentals.verify.metric_registry import MetricUnavailable

    update = _update(facts=_all_facts(revenue=Decimal("0")))

    resolved = _resolve(update, "pbt_margin_pct")

    assert isinstance(resolved, MetricUnavailable)
    assert resolved.metric_id == "pbt_margin_pct"
    assert any(word in resolved.reason.lower() for word in ("zero", "divis", "divid"))


def test_unregistered_metric_is_unavailable() -> None:
    """WHY: an unregistered metric id must fail closed instead of being improvised (B-12)."""
    from fundamentals.verify.metric_registry import MetricUnavailable

    resolved = _resolve(_update(), _UNREGISTERED_METRIC_ID)

    assert isinstance(resolved, MetricUnavailable)
    assert resolved.metric_id == _UNREGISTERED_METRIC_ID
    assert "unregistered metric" in resolved.reason


def test_thesis_loader_rejects_unknown_op_and_duplicate_ids(tmp_path: Path) -> None:
    """WHY: an unregistered op or an ambiguous falsifier id must never reach the evaluator."""
    from fundamentals.verify.thesis_predicates import PredicateOp, load_thesis

    good_path = _write_thesis(tmp_path / "thesis.yaml", _MARGIN_HOLDS_BLOCK + _TAX_BAND_BLOCK)
    thesis = load_thesis(good_path)

    assert thesis.symbol == _SYMBOL
    assert thesis.version == "2027.1"
    assert thesis.approved_at == date(2027, 7, 25)
    assert [falsifier.falsifier_id for falsifier in thesis.falsifiers] == [
        "f_margin_collapse",
        "f_tax_band",
    ]
    assert thesis.falsifiers[0].predicate.op is PredicateOp.LT
    assert thesis.falsifiers[0].predicate.threshold == Decimal("12")
    assert thesis.falsifiers[1].predicate.band == (Decimal("20"), Decimal("30"))
    assert thesis.content_sha256 == hashlib.sha256(good_path.read_bytes()).hexdigest()

    unknown_op_path = _write_thesis(tmp_path / "unknown_op.yaml", _UNKNOWN_OP_BLOCK)
    with pytest.raises(ValueError):
        load_thesis(unknown_op_path)

    duplicate_path = _write_thesis(tmp_path / "duplicate.yaml", _DUPLICATE_ID_BLOCK)
    with pytest.raises(ValueError):
        load_thesis(duplicate_path)


def test_falsifier_fires_weakened() -> None:
    """WHY: a fired falsifier is the whole deterministic signal the analyst layer needs."""
    from fundamentals.verify.thesis_impact import Disposition

    thesis = _single(
        "PBT margin prints below 25% in any FY28 quarter",
        _predicate("pbt_margin_pct", "LT", threshold="25"),
        falsifier_id="f_margin_collapse",
    )

    impact = _evaluate(_update(), thesis)
    evaluation = impact.evaluations[0]

    assert evaluation.disposition == Disposition.WEAKENED
    assert evaluation.metric_id == "pbt_margin_pct"
    assert evaluation.observed is not None
    assert evaluation.observed.value == Decimal("20")
    assert _count(impact, Disposition.WEAKENED) == 1
    assert impact.symbol == _SYMBOL
    assert impact.issuer_quarter == _QUARTER_LABEL
    assert impact.thesis_version == "2027.1"
    assert impact.thesis_sha256 == "cd" * 32


def test_falsifier_holds() -> None:
    """WHY: a predicate that is false must read HELD, never 'strengthened' (no such claim)."""
    from fundamentals.verify.thesis_impact import Disposition

    thesis = _single(
        "PBT margin prints below 12% in any FY28 quarter",
        _predicate("pbt_margin_pct", "LT", threshold="12"),
        falsifier_id="f_margin_collapse",
    )

    impact = _evaluate(_update(), thesis)

    assert impact.evaluations[0].disposition == Disposition.HELD
    assert _count(impact, Disposition.HELD) == 1
    assert _count(impact, Disposition.WEAKENED) == 0
    assert not any(str(key) == "STRENGTHENED" for key in dict(impact.counts))


def test_outside_band() -> None:
    """WHY: a band falsifier fires on either side, and a band op may not carry a threshold."""
    from fundamentals.verify.thesis_impact import Disposition

    inside = _single(
        "Effective tax rate leaves the 20-30% band",
        _predicate("effective_tax_rate_pct", "OUTSIDE_BAND", band=("20", "30")),
        falsifier_id="f_tax_band",
    )
    outside = _single(
        "Effective tax rate leaves the 20-24% band",
        _predicate("effective_tax_rate_pct", "OUTSIDE_BAND", band=("20", "24")),
        falsifier_id="f_tax_band",
    )

    assert _evaluate(_update(), inside).evaluations[0].disposition == Disposition.HELD
    assert _evaluate(_update(), outside).evaluations[0].disposition == Disposition.WEAKENED

    with pytest.raises(ValueError):
        _predicate("effective_tax_rate_pct", "OUTSIDE_BAND", threshold="20")
    with pytest.raises(ValueError):
        _predicate("pbt_margin_pct", "LT", band=("20", "30"))


def test_missing_metric_is_unresolved_never_dropped() -> None:
    """WHY: a falsifier that cannot be evaluated must be reported UNRESOLVED, not silently lost."""
    from fundamentals.verify.thesis_impact import Disposition

    thesis = _thesis(
        (
            _falsifier(
                "f_eps_slump",
                "Basic EPS falls below 10 in any FY28 quarter",
                _predicate("eps_basic_inr", "LT", threshold="10"),
            ),
            _falsifier(
                "f_unregistered",
                "Free cash flow conversion drops below 60%",
                _predicate(_UNREGISTERED_METRIC_ID, "LT", threshold="60"),
            ),
            _falsifier(
                "f_margin_collapse",
                "PBT margin prints below 25% in any FY28 quarter",
                _predicate("pbt_margin_pct", "LT", threshold="25"),
            ),
        )
    )

    impact = _evaluate(_update(facts=_facts_without(FactRole.BASIC_EPS)), thesis)
    evaluations = _by_id(impact)

    assert len(impact.evaluations) == 3
    assert set(evaluations) == {"f_eps_slump", "f_unregistered", "f_margin_collapse"}
    for falsifier_id in ("f_eps_slump", "f_unregistered"):
        assert evaluations[falsifier_id].disposition == Disposition.UNRESOLVED
        assert evaluations[falsifier_id].observed is None
        assert evaluations[falsifier_id].reason
    assert "unregistered metric" in evaluations["f_unregistered"].reason
    assert evaluations["f_margin_collapse"].disposition == Disposition.WEAKENED
    assert _count(impact, Disposition.UNRESOLVED) == 2
    assert sum(int(value) for value in dict(impact.counts).values()) == 3


def test_symbol_mismatch_refused() -> None:
    """WHY: evaluating one issuer's thesis against another's facts would be a silent lie."""
    thesis = _single(
        "PBT margin prints below 25% in any FY28 quarter",
        _predicate("pbt_margin_pct", "LT", threshold="25"),
        falsifier_id="f_margin_collapse",
        symbol=_OTHER_SYMBOL,
    )

    with pytest.raises(ValueError):
        _evaluate(_update(), thesis)


def test_render_lists_every_falsifier_with_sources() -> None:
    """WHY: §6/§7 must show every falsifier with its anchors and stay analyst-authored."""
    from fundamentals.verify.thesis_impact import Disposition, render_thesis_impact

    thesis = _thesis(
        (
            _falsifier(
                "f_margin_collapse",
                "PBT margin prints below 25% in any FY28 quarter",
                _predicate("pbt_margin_pct", "LT", threshold="25"),
            ),
            _falsifier(
                "f_eps_slump",
                "Basic EPS falls below 10 in any FY28 quarter",
                _predicate("eps_basic_inr", "LT", threshold="10"),
            ),
        )
    )
    impact = _evaluate(_update(facts=_facts_without(FactRole.BASIC_EPS)), thesis)

    markdown = render_thesis_impact(impact)

    assert "## 6. thesis_impact" in markdown
    assert "## 7. observable_falsifiers" in markdown
    assert "analyst" in markdown.lower()
    assert str(Disposition.WEAKENED) in markdown
    assert str(Disposition.UNRESOLVED) in markdown
    for falsifier in thesis.falsifiers:
        assert falsifier.falsifier_id in markdown
        assert falsifier.statement in markdown
    assert anchor_label(_provenance(_XBRL_SOURCE_ID, "ctx-revenue")) in markdown
    assert anchor_label(_provenance(_XBRL_SOURCE_ID, "ctx-profit_before_tax")) in markdown


def _run_cli(argv: list[str]) -> int:
    """Run the CLI, mapping a refusal raised as ``SystemExit`` back to an exit code."""
    from fundamentals.api.cli import main

    try:
        return main(argv)
    except SystemExit as error:
        code = error.code
        return code if isinstance(code, int) else 1


def test_cli_exit_codes_and_no_clobber(tmp_path: Path) -> None:
    """WHY: a script must read 'a falsifier fired' off the exit code, and never lose output."""
    import fundamentals.api.thesis_impact_cli  # noqa: F401  (module must exist)

    report_json = tmp_path / "update.json"
    report_json.write_text(_update().model_dump_json(), encoding="utf-8")
    holds_thesis = _write_thesis(tmp_path / "holds.yaml", _MARGIN_HOLDS_BLOCK)
    fires_thesis = _write_thesis(tmp_path / "fires.yaml", _MARGIN_FIRES_BLOCK)
    mismatch_thesis = _write_thesis(
        tmp_path / "mismatch.yaml", _MARGIN_HOLDS_BLOCK, symbol=_OTHER_SYMBOL
    )

    def argv(thesis: Path, out: Path) -> list[str]:
        """The ``thesis-impact`` argument vector for one thesis and one output path."""
        return [
            "thesis-impact",
            "--report-json",
            str(report_json),
            "--thesis",
            str(thesis),
            "--out",
            str(out),
        ]

    held_out = tmp_path / "held.md"
    assert _run_cli(argv(holds_thesis, held_out)) == 0
    assert "f_margin_collapse" in held_out.read_text(encoding="utf-8")

    fired_out = tmp_path / "fired.md"
    assert _run_cli(argv(fires_thesis, fired_out)) == 1
    fired_payload = fired_out.read_bytes()

    assert _run_cli(argv(holds_thesis, fired_out)) != 0
    assert fired_out.read_bytes() == fired_payload

    assert _run_cli(argv(mismatch_thesis, tmp_path / "mismatch.md")) == 2
    assert not (tmp_path / "mismatch.md").exists()
