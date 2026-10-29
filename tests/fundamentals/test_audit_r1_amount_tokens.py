"""F02 amount syntax, metadata boundaries and existing plural spellings."""

from decimal import Decimal

import pytest
from test_thesis import _draft, _fact_set

from fundamentals.thesis import JudgmentSection, cross_verify, extract_numbers


def _claims(text: str) -> tuple:
    return cross_verify(
        _fact_set(), [_draft("audit", sections={JudgmentSection.DRIVERS: [text]}, raw_text=text)]
    ).unsourced_claims


@pytest.mark.parametrize("sign", ["+-", "+−", "-+"])
def test_malformed_signs_fail_closed(sign: str) -> None:
    assert len(_claims(f"Revenue is {sign}999 crore.")) == 1


@pytest.mark.parametrize(
    "unit", ["crore per share", "crore/share", "crore USD", "crore per employee", "crore/employee"]
)
def test_full_unsupported_unit_is_refused(unit: str) -> None:
    assert len(_claims(f"Revenue is 174.455 {unit}.")) == 1


def test_accounting_negative_is_negative() -> None:
    hits = extract_numbers("Revenue is (174.455 crore).")
    assert len(hits) == 1
    assert hits[0].value == Decimal("-174.455")


@pytest.mark.parametrize("text", ["2024-10-01 to 2024-12-31", "In Q3FY25, demand held."])
def test_exact_prompt_metadata_is_allowed(text: str) -> None:
    assert _claims(text) == ()


@pytest.mark.parametrize(
    "text", ["Revenue is 2024 crore.", "Margin is 25%.", "In Q4FY25.", "On 2025-01-01."]
)
def test_metadata_components_and_unsupplied_tokens_are_unsourced(text: str) -> None:
    assert _claims(text)


@pytest.mark.parametrize(
    ("plural", "singular"),
    [("crores", "CRORE"), ("lakhs", "LAKH"), ("millions", "MILLION"), ("billions", "BILLION")],
)
def test_supported_plural_units_normalize(plural: str, singular: str) -> None:
    hits = extract_numbers(f"Revenue is 174.455 {plural}.")
    assert len(hits) == 1
    assert hits[0].unit == singular


@pytest.mark.parametrize("text", ["174.455 million", "USD 174.455 crore", "174.455 crores"])
def test_plural_normalization_does_not_source_judgment_amounts(text: str) -> None:
    assert _claims(text)
