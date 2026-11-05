"""Audit F01: analytical prose must not impersonate structural identifiers."""

import pytest

from equity_os.contracts.publication.ledger import VersionState
from equity_os.publication.checking.numeral_scan import scan_section


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
