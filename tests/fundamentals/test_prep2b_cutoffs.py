"""PREP-2b Task 1: each non-frozen Apar config's cutoff is its transcript's NSE filing instant.

NSE wall time is Asia/Kolkata; the old cutoffs read it as UTC and fell 5h30 late. The frozen
Stage 5 config keeps its old pin.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from retained_support import REPO_ROOT, manifest_entry

from fundamentals.api.config import load_config
from fundamentals.evidence.capture_intake import parse_filed_at

pytestmark = pytest.mark.retained

CONFIGS = {
    "FY26_Q2": "aparinds-fy26-q2.yaml",
    "FY26_Q3": "aparinds-fy26-q3.yaml",
    "FY26_Q4": "aparinds-fy26-q4-pg.yaml",
    "FY27_Q1": "aparinds-fy27-q1.yaml",
}


@pytest.mark.parametrize(("quarter", "name"), CONFIGS.items())
def test_cutoff_is_transcript_filing_instant(quarter: str, name: str) -> None:
    """The cutoff equals the IST-parsed filing time of the quarter's transcript."""
    quarter_config = load_config(REPO_ROOT / "config" / name).quarter
    filed = parse_filed_at(manifest_entry(quarter, "transcript")["filed_at_nse"])
    assert quarter_config.issuer_quarter == quarter
    assert quarter_config.knowledge_cutoff == filed


def test_old_window_is_after_the_cutoff() -> None:
    """An instant inside the old 5h30 window is past FY26_Q2's corrected cutoff."""
    cutoff = load_config(REPO_ROOT / "config" / CONFIGS["FY26_Q2"]).quarter.knowledge_cutoff
    assert cutoff == datetime(2025, 11, 6, 6, 35, 34, tzinfo=UTC)
    assert datetime(2025, 11, 6, 9, 0, tzinfo=UTC) > cutoff
