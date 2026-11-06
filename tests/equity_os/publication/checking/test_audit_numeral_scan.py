"""Audit F01: analytical prose must not impersonate structural identifiers."""

import pytest

from equity_os.contracts.publication.ledger import VersionState
from equity_os.publication.checking.numeral_scan import has_numeral, scan_section


@pytest.mark.parametrize(
    "prose",
    [
        "Expected revenue:500 crore.",
        "Expected revenue-500 crore.",
        "Expected revenue#500 crore.",
        "Expected return is × 100 percent.",
    ],
)
def test_analytical_numerals_are_not_structural(prose: str) -> None:
    assert scan_section("{{e:opinion}} " + prose, resolves=lambda capture, anchor: False) == (
        VersionState.UNREGISTERED_NUMBER,
    )


@pytest.mark.parametrize(
    "text,numeral",
    [
        ("Three plants opened", True),  # a number word
        ("Capacity doubled", True),
        ("Margins held 12", True),  # a digit
        ("Margins held ١٢", True),  # a non-ASCII numeral
        ("Orders ½ done", True),
        ("Booked on 2025-09-30", True),  # no date exemption
        ("Strong Q2 demand", True),  # no period exemption
        ("Margins held steady on export demand", False),
    ],
)
def test_vendor_span_numeral_rule_has_no_exemption(text: str, numeral: bool) -> None:
    """VENDOR-1 reading 5: any Unicode numeric character or number word makes a span a numeral."""
    assert has_numeral(text) is numeral
