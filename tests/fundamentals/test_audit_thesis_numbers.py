"""Audit F02: only signed, unit-compatible validated facts source draft amounts."""

import pytest
from test_thesis import _draft, _fact_set

from fundamentals.thesis import JudgmentSection, cross_verify


@pytest.mark.parametrize(
    ("text", "facts"),
    [
        ("ROCE is 31%.", False),
        ("Leverage is 1%.", False),
        ("There are 2024 stores.", False),
        ("Profit is -31 crore.", False),
        ("Revenue is 2 crore.", True),
        ("Revenue is 174 crore.", True),
        ("Revenue is -174.455 crore.", True),
        ("Revenue is −174.455 crore.", True),
        ("Margin is 174.455%.", True),
        ("Revenue is 174.455 million.", True),
        ("Revenue is USD 174.455 crore.", True),
        ("EPS is 5.19 crore.", True),
    ],
)
def test_metadata_sign_and_unit_do_not_source_amounts(text: str, facts: bool) -> None:
    fact_set = _fact_set()
    if not facts:
        fact_set = fact_set.model_copy(update={"facts": ()})
    draft = _draft("audit", sections={JudgmentSection.DRIVERS: [text]}, raw_text=text)
    assert len(cross_verify(fact_set, [draft]).unsourced_claims) == 1


@pytest.mark.parametrize(
    "text",
    [
        "Revenue is +174.455 crore.",
        "Revenue is INR 174.455 crore.",
        "Revenue is ₹174.455 crore.",
        "EPS of 5.19 held up.",
        "EPS is 5.19 INR per share.",
    ],
)
def test_signed_unit_compatible_fact_echoes_remain_sourced(text: str) -> None:
    draft = _draft("audit", sections={JudgmentSection.DRIVERS: [text]}, raw_text=text)
    assert cross_verify(_fact_set(), [draft]).unsourced_claims == ()
