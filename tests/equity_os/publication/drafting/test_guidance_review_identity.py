"""Canonical guidance identity survives presentation and JSON changes."""

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pymupdf
import pytest

from equity_os.contracts.measurement.fact import ReconciliationStatus
from equity_os.contracts.measurement.provenance import Provenance, SourceAnchorType
from equity_os.contracts.measurement.role import FactRole
from equity_os.publication.drafting.earnings_update import (
    EarningsUpdate,
    RenderedFact,
    RenderedGuidance,
    VerificationOutcome,
    render_earnings_update,
)
from equity_os.storage.facts.fact_store import FactStore
from tests.equity_os.interface.commands.sourcing.test_pipeline_temporal_admission import (
    inputs,
    run_synthetic_pipeline,
)

SOURCE = Provenance(
    source_id="synthetic-xbrl",
    file_sha256="0" * 63 + "1",
    anchor_type=SourceAnchorType.XBRL_CONTEXT,
    context_ref="synthetic-current",
    retrieved_at=datetime(2027, 10, 20, 6, tzinfo=UTC),
)


def _synthetic_update() -> EarningsUpdate:
    """A renderable synthetic report with one operating-margin guidance range."""
    facts = tuple(
        RenderedFact(
            role=role,
            concept_qname=f"syn-fin:{role.value}",
            value=Decimal("100"),
            unit="INR crore",
            reconciliation_status=ReconciliationStatus.CROSS_SOURCE_CONFIRMED,
            sources=(SOURCE,),
        )
        for role in (
            FactRole.REVENUE,
            FactRole.TOTAL_INCOME,
            FactRole.TOTAL_EXPENSES,
            FactRole.PROFIT_BEFORE_TAX,
            FactRole.PROFIT_FOR_PERIOD,
            FactRole.BASIC_EPS,
        )
    )
    guidance = RenderedGuidance(
        metric="margin",
        metric_label="Operating margin",
        lower_bound=Decimal("18.0"),
        upper_bound=Decimal("19.5"),
        unit="percent",
        constant_currency=False,
        horizon="fy2028",
        quote="We expect margin of 18 to 19.5 percent for fy2028.",
        source=SOURCE,
    )
    outcome = VerificationOutcome(passed_count=1, total_count=1)
    return EarningsUpdate(
        issuer_name="Synthetic Industries Limited",
        nse_symbol="SYNTH",
        issuer_quarter_label="Q2FY28",
        period_start="2027-07-01",
        period_end="2027-09-30",
        knowledge_cutoff="2027-10-20",
        facts=facts,
        guidance=(guidance,),
        calculations=(),
        cross_check=outcome,
        cross_foot=outcome,
        sec_cross_check_note="not applicable to this synthetic issuer",
    )


def test_canonical_guidance_identity_survives_label_rename_and_json() -> None:
    update = _synthetic_update()
    payload = update.guidance[0].model_dump()
    payload.update(metric="operating_margin", metric_label="Operating margin outlook")
    guidance = RenderedGuidance.model_validate(payload)
    update = update.model_copy(update={"guidance": (guidance,)})
    restored = EarningsUpdate.model_validate_json(update.model_dump_json())
    assert restored.guidance[0] == guidance
    assert (restored.guidance[0].metric, restored.guidance[0].horizon) == (
        "operating_margin",
        "fy2028",
    )
    renamed = RenderedGuidance.model_validate_json(
        guidance.model_copy(update={"metric_label": "Margin"}).model_dump_json()
    )
    assert renamed.metric == guidance.metric and renamed.metric_label != guidance.metric_label


@pytest.mark.parametrize("metric", ["", " ", "\t\n"])
def test_present_blank_metric_is_rejected(metric: str) -> None:
    payload = _synthetic_update().guidance[0].model_dump()
    payload["metric"] = metric
    with pytest.raises(ValueError):
        RenderedGuidance.model_validate(payload)


def test_generated_pipeline_guidance_keeps_metric_through_json_and_label_rename(
    tmp_path: Path,
) -> None:
    args = inputs(tmp_path)
    transcript = tmp_path / "new-guidance.pdf"
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((60, 90), "Revenue growth guidance of 3% to 4% constant currency.")
        document.save(str(transcript))
    args["transcript_pdf_path"] = str(transcript)
    args["transcript_pdf_sha256"] = hashlib.sha256(transcript.read_bytes()).hexdigest()
    config = args["config"]
    ids = []
    for label in ("Growth forecast", "Revenue outlook"):
        rules = tuple(r.model_copy(update={"label": label}) for r in config.guidance.rules)
        args["config"] = config.model_copy(
            update={"guidance": config.guidance.model_copy(update={"rules": rules})}
        )
        store = FactStore(":memory:")
        try:
            result = run_synthetic_pipeline(**args, store=store)
        finally:
            store.close()
        update = EarningsUpdate.model_validate_json(result.update.model_dump_json())
        assert update.guidance[0].metric == "revenue_growth"
        assert update.guidance[0].metric_label == label
        assert label in result.markdown
        ids.append((update.guidance[0].metric, update.guidance[0].horizon))
    assert ids == [("revenue_growth", "FY25"), ("revenue_growth", "FY25")]


@pytest.mark.parametrize("metric", [None, "operating_margin", " operating_margin "])
def test_metric_is_verbatim_and_does_not_change_rendered_content(metric: str | None) -> None:
    update = _synthetic_update()
    guidance = RenderedGuidance.model_validate(
        {**update.guidance[0].model_dump(), "metric": metric}
    )
    changed = update.model_copy(update={"guidance": (guidance,)})
    assert render_earnings_update(changed) == render_earnings_update(update)
    assert changed.guidance[0].metric == metric


def test_shared_label_distinguishes_metrics_and_horizons() -> None:
    update = _synthetic_update()
    payload = update.guidance[0].model_dump()
    guidance = tuple(
        RenderedGuidance.model_validate({**payload, "metric": metric, "horizon": horizon})
        for metric, horizon in (
            ("operating_margin", "fy2028"),
            ("revenue_growth", "fy2028"),
            ("operating_margin", "fy2029"),
        )
    )
    update = update.model_copy(update={"guidance": guidance})
    restored = EarningsUpdate.model_validate_json(update.model_dump_json())
    assert [(g.metric, g.horizon) for g in restored.guidance] == [
        ("operating_margin", "fy2028"),
        ("revenue_growth", "fy2028"),
        ("operating_margin", "fy2029"),
    ]
