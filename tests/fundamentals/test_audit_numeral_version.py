"""F01 compatibility ruling: preserve the renderer's version identifier."""

import pytest

from fundamentals.ledger.numeral_scan import scan_section


@pytest.mark.parametrize(
    "text",
    [
        "{{e:computed}} Prior: version:7 digest 3f9a2c1d7e.",
        "{{e:computed}} Full successor of version:1234 (full rework requested).",
    ],
)
def test_rendered_version_identifier_is_structural(text: str) -> None:
    assert scan_section(text, resolves=lambda capture, anchor: False) == ()
