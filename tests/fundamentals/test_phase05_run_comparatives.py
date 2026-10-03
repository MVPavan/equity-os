"""Slice phase05-sB acceptance — `run` comparatives from declared prior-quarter instances.

Red proof for the ``comparators`` config block, the collector
``fundamentals.api.run_comparatives.collect_run_comparatives``, the accepted
taxonomy-drift note on a ``ComparativeChange``, and the pipeline wiring that puts
QoQ/YoY into §3 of the rendered update.

Everything compared is synthetic: hand-built current ``Observation``s for symbol
SYNTH over 2027 quarters, plus prior XBRL instances written byte-for-byte into
``tmp_path`` and pinned by the sha256 of exactly those bytes. The two pipeline tests
reuse the committed synthetic Q1 FY25 fixtures ``test_pipeline_e2e`` runs on, because
``run`` only renders a full six-role report. Drift is staged between two taxonomies
the parser registry knows — an unregistered one fails closed in ``parse_instance``.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import BaseModel, ConfigDict
from temporal_fixture_support import FIXTURE_ACQUIRED_AT, run_trusted_fixture_pipeline

from fundamentals.api.comparatives import REASON_SELECTION_FAILED
from fundamentals.api.config import FundamentalsConfig, load_config
from fundamentals.api.pipeline import PipelineResult, XbrlInput
from fundamentals.contracts.comparative import ComparatorKind
from fundamentals.contracts.observation import (
    AccountingFramework,
    Observation,
    PeriodType,
    Scope,
)
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.contracts.role import FactRole
from fundamentals.contracts.source_catalog import SourceClass
from fundamentals.extract.xbrl_parser import FIN_NAMESPACE, FIN_PREFIX, SCOPE_CONCEPT
from fundamentals.extract.xbrl_taxonomies import (
    IN_CAPMKT_2026_NAMESPACE,
    IN_CAPMKT_2026_REGISTRY_VERSION,
    IN_CAPMKT_PREFIX,
)
from fundamentals.output.earnings_update import _Footnotes, _render_change
from fundamentals.store.fact_store import FactStore
from fundamentals.verify.comparison_key import FIELD_SCALE, FIELD_UNIT

_SYMBOL = "SYNTH"
_SCHEME = "nse-symbol"
_FIRST_PARTY = SourceClass.FIRST_PARTY.value
_NSE_SCHEME_URI = "http://www.nseindia.com/NSESymbol"

_CURRENT_PERIOD = (date(2027, 7, 1), date(2027, 9, 30))
_QOQ_PERIOD = (date(2027, 4, 1), date(2027, 6, 30))
_YOY_PERIOD = (date(2026, 7, 1), date(2026, 9, 30))
_UNRELATED_PERIOD = (date(2027, 1, 1), date(2027, 3, 31))
# (prefix, namespace) of the two registered taxonomies the drift tests span.
_CAPMKT = (IN_CAPMKT_PREFIX, IN_CAPMKT_2026_NAMESPACE)
_BSE_FIN = (FIN_PREFIX, FIN_NAMESPACE)
_REVENUE_LOCAL = "RevenueFromOperations"
_PAT_LOCAL = "ProfitLossForPeriod"
_REVENUE_QNAME = f"{IN_CAPMKT_PREFIX}:{_REVENUE_LOCAL}"
_PAT_QNAME = f"{IN_CAPMKT_PREFIX}:{_PAT_LOCAL}"

_CURRENT_REVENUE = Decimal("1000")
_CURRENT_PAT = Decimal("120")
_PRIOR_REVENUE = "800"
_PRIOR_PAT = "100"
_EXPECTED_DELTA = Decimal("200")
_EXPECTED_PERCENT = Decimal("25")
_CRORE_SCALE = 10_000_000
_CRORE_UNIT = "INR crore"
_CURRENCY = "INR"
_CRORE_DECIMALS = -7
_INR_UNIT_REF = "INR"
_PER_SHARE_UNIT_REF = "INRPerShare"
_PER_SHARE_DECIMALS = 2
_CONTEXT_ID = "OneD"
_SOURCE_ID = "synth-xbrl-consolidated"
_LOCAL_PATH = "priors/current.xml"
_CURRENT_SHA = hashlib.sha256(b"synthetic-current-SYNTH-Q2-FY28-instance").hexdigest()
_WRONG_SHA = hashlib.sha256(b"a different file entirely").hexdigest()
_RETRIEVED_AT = datetime(2027, 10, 15, tzinfo=UTC)

_DRIFT_MARKER = "taxonomy"
_RENDERED_DRIFT_MARKER = "taxonomy drift accepted"
_UNDECLARED_YOY_REASON = f"no {ComparatorKind.YOY.value} comparator declared"
_SELECTION_REASON_PREFIX = REASON_SELECTION_FAILED.split("{error}")[0]

# Located by walking up, so the module works from its staged path and its final home.
_REPO_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "config" / "fundamentals.yaml").is_file()
)
_E2E_CONFIG_PATH = _REPO_ROOT / "config" / "fundamentals.yaml"
_FIXTURES = _REPO_ROOT / "tests" / "fundamentals" / "fixtures"
_SYNTHETIC_XBRL = _FIXTURES / "synthetic_q1_fy25_consolidated.xml"
_NOT_ATTEMPTED = (
    "Prior-period comparatives were not attempted for this single-issuer pipeline path."
)
_COMPARATIVES_HEADER = "| P&L line | Current | QoQ prior / change | YoY prior / change |"
_E2E_SYMBOL = "INFY"
_E2E_QOQ_PERIOD = (date(2024, 1, 1), date(2024, 3, 31))
_E2E_PRIOR_YEAR = _E2E_QOQ_PERIOD[0].year - 1
_E2E_YOY_PERIOD = (date(_E2E_PRIOR_YEAR, 4, 1), date(_E2E_PRIOR_YEAR, 6, 30))
_E2E_ROLE_LOCALS = (_REVENUE_LOCAL, "Income", "Expenses", "ProfitBeforeTax", _PAT_LOCAL)
_E2E_EPS_LOCAL = "BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations"
_E2E_QOQ_VALUES = ("38000", "39000", "30000", "9000", "6000")
_E2E_YOY_VALUES = ("36000", "37000", "29000", "8000", "5500")
_E2E_RENDERED_PRIORS = ("38,000", "36,000")

_INSTANCE_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl
    xmlns:xbrli="http://www.xbrl.org/2003/instance"
    xmlns:iso4217="http://www.xbrl.org/2003/iso4217"
    xmlns:{prefix}="{namespace}">
  <xbrli:context id="{context}"><xbrli:entity>
    <xbrli:identifier scheme="{scheme}">{entity_id}</xbrli:identifier>
  </xbrli:entity><xbrli:period>
    <xbrli:startDate>{start}</xbrli:startDate><xbrli:endDate>{end}</xbrli:endDate>
  </xbrli:period></xbrli:context>
  <xbrli:unit id="INR"><xbrli:measure>iso4217:INR</xbrli:measure></xbrli:unit>
  <xbrli:unit id="INRPerShare"><xbrli:divide>
    <xbrli:unitNumerator><xbrli:measure>iso4217:INR</xbrli:measure></xbrli:unitNumerator>
    <xbrli:unitDenominator><xbrli:measure>xbrli:shares</xbrli:measure></xbrli:unitDenominator>
  </xbrli:divide></xbrli:unit>
{scope_line}
{facts}
</xbrli:xbrl>
"""
_SCOPE_LINE = '  <{prefix}:{scope} contextRef="{context}">Consolidated</{prefix}:{scope}>'
_FACT_LINE = (
    '  <{prefix}:{name} contextRef="{context}" unitRef="{unit}" '
    'decimals="{decimals}">{value}</{prefix}:{name}>'
)


class _Fact(BaseModel):
    """One numeric fact to emit into a synthetic instance."""

    model_config = ConfigDict(frozen=True)

    local_name: str
    value: str
    unit_ref: str = _INR_UNIT_REF
    decimals: int = _CRORE_DECIMALS


def _rupees(crore: str) -> str:
    """Render a crore amount as the full-rupee lexical value a filing carries."""
    return f"{Decimal(crore) * _CRORE_SCALE:.2f}"


def _crore_fact(local_name: str, crore: str) -> _Fact:
    """A monetary fact stated in full rupees, normalising to crore."""
    return _Fact(local_name=local_name, value=_rupees(crore))


def _default_prior_facts() -> tuple[_Fact, ...]:
    """The two role concepts a comparable prior quarter states."""
    return (_crore_fact(_REVENUE_LOCAL, _PRIOR_REVENUE), _crore_fact(_PAT_LOCAL, _PRIOR_PAT))


def _write_prior(
    repo_root: Path,
    name: str,
    *,
    period: tuple[date, date],
    facts: tuple[_Fact, ...],
    taxonomy: tuple[str, str] = _CAPMKT,
    entity_id: str = _SYMBOL,
) -> tuple[str, str]:
    """Write one prior instance under ``repo_root``; return its relative path and sha256."""
    prefix, namespace = taxonomy
    body = "\n".join(
        _FACT_LINE.format(
            prefix=prefix,
            name=fact.local_name,
            context=_CONTEXT_ID,
            unit=fact.unit_ref,
            decimals=fact.decimals,
            value=fact.value,
        )
        for fact in facts
    )
    payload = _INSTANCE_TEMPLATE.format(
        prefix=prefix,
        namespace=namespace,
        scheme=_NSE_SCHEME_URI,
        entity_id=entity_id,
        context=_CONTEXT_ID,
        start=period[0].isoformat(),
        end=period[1].isoformat(),
        scope_line=_SCOPE_LINE.format(prefix=prefix, scope=SCOPE_CONCEPT, context=_CONTEXT_ID),
        facts=body,
    ).encode("utf-8")
    relative = f"priors/{name}.xml"
    path = repo_root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return relative, hashlib.sha256(payload).hexdigest()


def _comparator_entry(
    *,
    local_path: str,
    sha256: str,
    period: tuple[date, date],
    accept_taxonomy_drift: bool = False,
) -> dict[str, Any]:
    """One ``comparators.<kind>`` YAML block."""
    return {
        "local_path": local_path,
        "sha256": sha256,
        "period_start": period[0],
        "period_end": period[1],
        "accept_taxonomy_drift": accept_taxonomy_drift,
    }


def _source_file(source_id: str, filename: str) -> dict[str, Any]:
    """A held-source block; the collector tests never open these files."""
    block = {"source_id": source_id, "source_class": _FIRST_PARTY, "filename": filename}
    return {**block, "sha256": hashlib.sha256(filename.encode("utf-8")).hexdigest()}


def _write_yaml(repo_root: Path, data: dict[str, Any]) -> Path:
    """Write a config whose ``repo_root`` (its grandparent) is ``repo_root``."""
    config_dir = repo_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "fundamentals.yaml"
    config_file.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return config_file


def _write_config(repo_root: Path, *, comparators: dict[str, Any] | None = None) -> Path:
    """Write the minimal two-role SYNTH config, optionally declaring comparators."""
    data: dict[str, Any] = {
        "issuer": {"name": "Synth Industries Ltd", "nse_symbol": _SYMBOL, "entity_scheme": _SCHEME},
        "quarter": {
            "issuer_quarter": "FY28_Q2",
            "program_quarter": "QUARTER_2",
            "label": "Q2 FY28 (quarter ended 2027-09-30)",
            "period_start": _CURRENT_PERIOD[0],
            "period_end": _CURRENT_PERIOD[1],
            "knowledge_cutoff": _RETRIEVED_AT,
        },
        "raw_dir": "data/raw/synth",
        "store_db": ":memory:",
        "results_pdf": _source_file("synth-results-pdf", "SYNTH-FY28-Q2-results.pdf"),
        "transcript_pdf": _source_file("synth-transcript-pdf", "SYNTH-FY28-Q2-transcript.pdf"),
        "xbrl": {"source_id": _SOURCE_ID, "local_path": _LOCAL_PATH, "symbol": _SYMBOL},
        "concepts": {
            "roles": [
                {"role": FactRole.REVENUE.value, "concept_qname": _REVENUE_QNAME},
                {"role": FactRole.PROFIT_FOR_PERIOD.value, "concept_qname": _PAT_QNAME},
            ]
        },
    }
    if comparators is not None:
        data["comparators"] = comparators
    return _write_yaml(repo_root, data)


def _qoq_only_config(
    tmp_path: Path,
    *,
    facts: tuple[_Fact, ...] | None = None,
    period: tuple[date, date] = _QOQ_PERIOD,
    taxonomy: tuple[str, str] = _CAPMKT,
    accept_taxonomy_drift: bool = False,
) -> Path:
    """Declare exactly one QoQ comparator instance and return the config path."""
    local_path, sha256 = _write_prior(
        tmp_path, "qoq", period=period, facts=facts or _default_prior_facts(), taxonomy=taxonomy
    )
    entry = _comparator_entry(
        local_path=local_path,
        sha256=sha256,
        period=_QOQ_PERIOD,
        accept_taxonomy_drift=accept_taxonomy_drift,
    )
    return _write_config(tmp_path, comparators={"qoq": entry})


def _current_observation(concept_qname: str, value: Decimal) -> Observation:
    """One selected consolidated-quarter XBRL observation for the current quarter."""
    return Observation(
        concept_qname=concept_qname,
        taxonomy_namespace=IN_CAPMKT_2026_NAMESPACE,
        registry_version=IN_CAPMKT_2026_REGISTRY_VERSION,
        raw_value=_rupees(str(value)),
        normalized_value=value,
        normalized_unit=_CRORE_UNIT,
        context_ref=_CONTEXT_ID,
        entity_scheme=_SCHEME,
        entity_id=_SYMBOL,
        scope=Scope.CONSOLIDATED,
        accounting_basis=AccountingFramework.IND_AS,
        period_type=PeriodType.DURATION,
        period_start=_CURRENT_PERIOD[0],
        period_end=_CURRENT_PERIOD[1],
        currency=_CURRENCY,
        scale=_CRORE_SCALE,
        decimals=_CRORE_DECIMALS,
        provenance=Provenance(
            source_id=_SOURCE_ID,
            file_sha256=_CURRENT_SHA,
            anchor_type=SourceAnchorType.XBRL_CONTEXT,
            context_ref=_CONTEXT_ID,
            retrieved_at=_RETRIEVED_AT,
        ),
    )


def _collect(config_path: Path) -> Any:
    """Run the collector over the two hand-built current endpoints."""
    from fundamentals.api.run_comparatives import collect_run_comparatives

    current = {
        _REVENUE_QNAME: _current_observation(_REVENUE_QNAME, _CURRENT_REVENUE),
        _PAT_QNAME: _current_observation(_PAT_QNAME, _CURRENT_PAT),
    }
    return collect_run_comparatives(
        load_config(config_path),
        config_path=config_path,
        current=current,
        current_sources={qname: (obs.provenance,) for qname, obs in current.items()},
    )


def _write_e2e_prior(
    tmp_path: Path, name: str, period: tuple[date, date], values: tuple[str, ...], eps: str
) -> tuple[str, str]:
    """Write one six-role synthetic INFY prior quarter and pin its bytes."""
    unit, decimals = _PER_SHARE_UNIT_REF, _PER_SHARE_DECIMALS
    facts = (
        *(_crore_fact(local, value) for local, value in zip(_E2E_ROLE_LOCALS, values, strict=True)),
        _Fact(local_name=_E2E_EPS_LOCAL, value=eps, unit_ref=unit, decimals=decimals),
    )
    return _write_prior(
        tmp_path, name, period=period, facts=facts, taxonomy=_BSE_FIN, entity_id=_E2E_SYMBOL
    )


def _e2e_config(tmp_path: Path, comparators: dict[str, Any] | None) -> Path:
    """Copy the committed e2e config to a temp repo root, optionally adding comparators."""
    data: dict[str, Any] = yaml.safe_load(_E2E_CONFIG_PATH.read_text(encoding="utf-8"))
    data["raw_dir"] = str(_REPO_ROOT / str(data["raw_dir"]))
    data["xbrl"]["local_path"] = str(_REPO_ROOT / str(data["xbrl"]["local_path"]))
    if comparators is not None:
        data["comparators"] = comparators
    return _write_yaml(tmp_path, data)


def _run_e2e(config: FundamentalsConfig, config_path: Path, store: FactStore) -> PipelineResult:
    """Run the deterministic INFY pipeline over the committed synthetic fixtures."""
    xml_bytes = _SYNTHETIC_XBRL.read_bytes()
    return run_trusted_fixture_pipeline(
        config=config,
        config_path=config_path,
        xbrl_input=XbrlInput(
            xml_bytes=xml_bytes,
            file_sha256=hashlib.sha256(xml_bytes).hexdigest(),
            source_id=config.xbrl.source_id,
            retrieved_at=FIXTURE_ACQUIRED_AT,
        ),
        results_pdf_path=str(config.results_pdf_path(config_path)),
        results_pdf_sha256=config.results_pdf.sha256,
        transcript_pdf_path=str(config.transcript_pdf_path(config_path)),
        transcript_pdf_sha256=config.transcript_pdf.sha256,
        store=store,
    )


def test_config_loads_comparators_and_resolves_paths(tmp_path: Path) -> None:
    # A comparator is auditable only if config pins the file, its hash, and its period.
    from fundamentals.api.config import ComparatorInstanceConfig, ComparatorsConfig

    declared = {
        "qoq": _comparator_entry(
            local_path="priors/qoq.xml", sha256=_WRONG_SHA, period=_QOQ_PERIOD
        ),
        "yoy": _comparator_entry(
            local_path="priors/yoy.xml",
            sha256=_CURRENT_SHA,
            period=_YOY_PERIOD,
            accept_taxonomy_drift=True,
        ),
    }
    config_path = _write_config(tmp_path, comparators=declared)

    config = load_config(config_path)

    assert isinstance(config.comparators, ComparatorsConfig)
    qoq, yoy = config.comparators.qoq, config.comparators.yoy
    assert isinstance(qoq, ComparatorInstanceConfig)
    assert isinstance(yoy, ComparatorInstanceConfig)
    assert qoq.sha256 == _WRONG_SHA
    assert (qoq.period_start, qoq.period_end) == _QOQ_PERIOD
    assert (yoy.period_start, yoy.period_end) == _YOY_PERIOD
    assert qoq.accept_taxonomy_drift is False
    assert yoy.accept_taxonomy_drift is True
    assert config.comparator_path(config_path, ComparatorKind.QOQ) == tmp_path / "priors/qoq.xml"
    assert config.comparator_path(config_path, ComparatorKind.YOY) == tmp_path / "priors/yoy.xml"


def test_absent_comparators_leave_report_not_attempted() -> None:
    # With no comparator declared the report must keep claiming nothing, not claim a search.
    config = load_config(_E2E_CONFIG_PATH)
    assert config.comparators is None

    store = FactStore(":memory:")
    try:
        result = _run_e2e(config, _E2E_CONFIG_PATH, store)
    finally:
        store.close()

    assert _NOT_ATTEMPTED in result.markdown
    assert _COMPARATIVES_HEADER not in result.markdown


def test_qoq_change_is_calculated_from_prior_instance(tmp_path: Path) -> None:
    # Both traces and the change must be computed from the declared prior file's own facts.
    config_path = _qoq_only_config(tmp_path)

    comparatives = _collect(config_path)

    assert [item.concept_qname for item in comparatives] == [_REVENUE_QNAME, _PAT_QNAME]
    revenue = comparatives[0]
    assert revenue.current_value == _CURRENT_REVENUE
    assert revenue.unit == _CRORE_UNIT
    assert [source.source_id for source in revenue.current_sources] == [_SOURCE_ID]

    change = revenue.qoq
    assert change.available
    assert (change.period_start, change.period_end) == _QOQ_PERIOD
    assert change.prior_value == Decimal(_PRIOR_REVENUE)
    assert change.absolute_change == _EXPECTED_DELTA
    assert change.percent_change == _EXPECTED_PERCENT
    assert change.absolute_trace == f"{_CURRENT_REVENUE} - {change.prior_value}"
    assert change.percent_trace == (
        f"({_CURRENT_REVENUE} - {change.prior_value}) / {change.prior_value} * 100"
    )

    # The prior endpoint is traced to the prior file's own XBRL context, not the current file.
    declared = load_config(config_path).comparators
    assert declared is not None and declared.qoq is not None
    assert change.prior_source is not None
    assert change.prior_source.context_ref == _CONTEXT_ID
    assert change.prior_source.file_sha256 == declared.qoq.sha256

    assert comparatives[1].qoq.prior_value == Decimal(_PRIOR_PAT)


def test_missing_prior_file_fails_closed(tmp_path: Path) -> None:
    # A declared prior that is not on disk is a config defect, never an "unavailable" cell.
    from fundamentals.api.run_comparatives import RunComparativesError

    missing = "priors/absent.xml"
    entry = _comparator_entry(local_path=missing, sha256=_WRONG_SHA, period=_QOQ_PERIOD)
    config_path = _write_config(tmp_path, comparators={"qoq": entry})

    with pytest.raises(RunComparativesError) as error:
        _collect(config_path)
    assert missing in str(error.value)


def test_prior_sha_mismatch_fails_closed(tmp_path: Path) -> None:
    # An unpinned prior could be any quarter's bytes, so a hash mismatch must abort the run.
    from fundamentals.api.run_comparatives import RunComparativesError

    local_path, _ = _write_prior(tmp_path, "qoq", period=_QOQ_PERIOD, facts=_default_prior_facts())
    entry = _comparator_entry(local_path=local_path, sha256=_WRONG_SHA, period=_QOQ_PERIOD)
    config_path = _write_config(tmp_path, comparators={"qoq": entry})

    with pytest.raises(RunComparativesError) as error:
        _collect(config_path)
    assert _WRONG_SHA in str(error.value)


def test_prior_selection_failure_is_unavailable_with_reason(tmp_path: Path) -> None:
    # A prior file stating another quarter must yield no value at all, and say why.
    config_path = _qoq_only_config(tmp_path, period=_UNRELATED_PERIOD)

    comparatives = _collect(config_path)

    for comparative in comparatives:
        assert not comparative.qoq.available
        assert comparative.qoq.prior_value is None
        reason = comparative.qoq.unavailable_reason
        assert reason is not None and reason.startswith(_SELECTION_REASON_PREFIX)


def test_taxonomy_drift_rejected_unless_accepted(tmp_path: Path) -> None:
    # Same local name under another taxonomy is a semantic claim only the analyst may accept.
    config_path = _qoq_only_config(tmp_path, taxonomy=_BSE_FIN, accept_taxonomy_drift=False)

    comparatives = _collect(config_path)

    change = comparatives[0].qoq
    assert not change.available
    reason = change.unavailable_reason
    assert reason is not None
    assert _DRIFT_MARKER in reason.lower()
    assert FIN_PREFIX in reason or FIN_NAMESPACE in reason


def test_taxonomy_drift_accepted_records_note(tmp_path: Path) -> None:
    # An accepted drift must stay visible to the reader, not be silently absorbed.
    config_path = _qoq_only_config(tmp_path, taxonomy=_BSE_FIN, accept_taxonomy_drift=True)

    comparatives = _collect(config_path)

    revenue = comparatives[0]
    change = revenue.qoq
    assert change.available
    assert change.prior_value == Decimal(_PRIOR_REVENUE)
    assert change.absolute_change == _EXPECTED_DELTA
    assert change.percent_change == _EXPECTED_PERCENT
    assert change.taxonomy_drift is not None
    assert FIN_PREFIX in change.taxonomy_drift or FIN_NAMESPACE in change.taxonomy_drift

    _, trace = _render_change(revenue, change, _Footnotes())
    assert trace is not None
    assert _RENDERED_DRIFT_MARKER in trace


def test_other_key_fields_still_gate_under_drift(tmp_path: Path) -> None:
    # Accepting taxonomy drift must not relax the rest of the column identity.
    per_share_revenue = _Fact(
        local_name=_REVENUE_LOCAL,
        value="12.50",
        unit_ref=_PER_SHARE_UNIT_REF,
        decimals=_PER_SHARE_DECIMALS,
    )
    config_path = _qoq_only_config(
        tmp_path,
        taxonomy=_BSE_FIN,
        accept_taxonomy_drift=True,
        facts=(per_share_revenue, _crore_fact(_PAT_LOCAL, _PRIOR_PAT)),
    )

    comparatives = _collect(config_path)

    change = comparatives[0].qoq
    assert not change.available
    reason = change.unavailable_reason
    assert reason is not None
    assert FIELD_UNIT in reason
    assert FIELD_SCALE in reason

    # Positive control: the same-unit concept in the same drifting file still compares.
    assert comparatives[1].qoq.available


def test_undeclared_kind_is_unavailable_with_reason(tmp_path: Path) -> None:
    # An undeclared comparator must be reported as undeclared, not as a failed lookup.
    config_path = _qoq_only_config(tmp_path)

    comparatives = _collect(config_path)

    for comparative in comparatives:
        assert not comparative.yoy.available
        assert comparative.yoy.unavailable_reason == _UNDECLARED_YOY_REASON
        assert comparative.qoq.available


def test_pipeline_report_renders_qoq_and_yoy(tmp_path: Path) -> None:
    # §3 is the deliverable: a declared pair of priors must reach the rendered markdown.
    qoq = _write_e2e_prior(tmp_path, "e2e_qoq", _E2E_QOQ_PERIOD, _E2E_QOQ_VALUES, "14.50")
    yoy = _write_e2e_prior(tmp_path, "e2e_yoy", _E2E_YOY_PERIOD, _E2E_YOY_VALUES, "13.00")
    config_path = _e2e_config(
        tmp_path,
        {
            "qoq": _comparator_entry(local_path=qoq[0], sha256=qoq[1], period=_E2E_QOQ_PERIOD),
            "yoy": _comparator_entry(local_path=yoy[0], sha256=yoy[1], period=_E2E_YOY_PERIOD),
        },
    )
    config = load_config(config_path)

    store = FactStore(":memory:")
    try:
        result = _run_e2e(config, config_path, store)
    finally:
        store.close()

    assert _NOT_ATTEMPTED not in result.markdown
    assert _COMPARATIVES_HEADER in result.markdown
    for rendered_prior in _E2E_RENDERED_PRIORS:
        assert rendered_prior in result.markdown
    for period in (_E2E_QOQ_PERIOD, _E2E_YOY_PERIOD):
        assert f"{period[0].isoformat()}..{period[1].isoformat()}" in result.markdown
