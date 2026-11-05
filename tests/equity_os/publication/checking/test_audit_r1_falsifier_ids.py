"""F01 preserves the falsifier identifiers accepted by the thesis contract."""

import pytest

from equity_os.contracts.publication.ledger import VersionState
from equity_os.publication.checking.numeral_scan import scan_section


@pytest.mark.parametrize("identifier", ["A1", "B12", "Z9"])
def test_supported_falsifier_identifiers_are_structural(identifier: str) -> None:
    assert (
        scan_section("{{e:computed}} " + identifier + ": INDETERMINATE.", resolves=lambda *_: False)
        == ()
    )


@pytest.mark.parametrize("text", ["revenue:500 crore", "A123 crore", "word:42"])
def test_arbitrary_numeric_prose_remains_unregistered(text: str) -> None:
    assert scan_section("{{e:opinion}} " + text, resolves=lambda *_: False) == (
        VersionState.UNREGISTERED_NUMBER,
    )
