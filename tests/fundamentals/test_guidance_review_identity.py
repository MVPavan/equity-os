"""Canonical guidance identity survives presentation and JSON changes."""

import hashlib
from decimal import Decimal
from pathlib import Path

import pymupdf
import pytest
from tests.fundamentals.test_phase05_review_session import _synthetic_update
from tests.fundamentals.test_pipeline_temporal_admission import inputs, run_synthetic_pipeline

from fundamentals.output.earnings_update import (
    EarningsUpdate,
    RenderedGuidance,
    render_earnings_update,
)
from fundamentals.output.review_session import ClaimKind, enumerate_claims
from fundamentals.store.fact_store import FactStore


def test_canonical_guidance_identity_survives_label_rename_and_json() -> None:
    update = _synthetic_update()
    payload = update.guidance[0].model_dump()
    payload.update(metric="operating_margin", metric_label="Operating margin outlook")
    guidance = RenderedGuidance.model_validate(payload)
    update = update.model_copy(update={"guidance": (guidance,)})
    restored = EarningsUpdate.model_validate_json(update.model_dump_json())
    claim = next(c for c in enumerate_claims(restored) if c.kind is ClaimKind.GUIDANCE)
    assert claim.claim_id == "guidance:operating_margin:fy2028"
    assert "Operating margin outlook" in claim.text
    assert restored.guidance[0].lower_bound == Decimal("18.0")
    renamed = restored.model_copy(
        update={"guidance": (guidance.model_copy(update={"metric_label": "Margin"}),)}
    )
    renamed_claim = next(c for c in enumerate_claims(renamed) if c.kind is ClaimKind.GUIDANCE)
    assert renamed_claim.claim_id == claim.claim_id
    assert renamed_claim.text != claim.text


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
        claim = next(c for c in enumerate_claims(update) if c.kind is ClaimKind.GUIDANCE)
        ids.append(claim.claim_id)
    assert ids == ["guidance:revenue_growth:FY25", "guidance:revenue_growth:FY25"]


@pytest.mark.parametrize("metric", [None, "operating_margin", " operating_margin "])
def test_metric_is_verbatim_and_does_not_change_rendered_content(metric: str | None) -> None:
    update = _synthetic_update()
    guidance = RenderedGuidance.model_validate(
        {**update.guidance[0].model_dump(), "metric": metric}
    )
    changed = update.model_copy(update={"guidance": (guidance,)})
    assert render_earnings_update(changed) == render_earnings_update(update)
    assert changed.guidance[0].metric == metric
    claim = next(c for c in enumerate_claims(changed) if c.kind is ClaimKind.GUIDANCE)
    expected = "Operating margin" if metric is None else metric
    assert claim.claim_id == f"guidance:{expected}:fy2028"


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
    assert [c.claim_id for c in enumerate_claims(update) if c.kind is ClaimKind.GUIDANCE] == [
        "guidance:operating_margin:fy2028",
        "guidance:revenue_growth:fy2028",
        "guidance:operating_margin:fy2029",
    ]
