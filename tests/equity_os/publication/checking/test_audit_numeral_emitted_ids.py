"""F01 compatibility ruling: a closed set of emitted IDs, never arbitrary prose."""

import pytest

from equity_os.contracts.publication.ledger import VersionState
from equity_os.publication.checking.numeral_scan import scan_section


@pytest.mark.parametrize(
    ("prefix", "expected"),
    [
        pytest.param("version", (), id="version"),
        pytest.param("memory", (), id="memory"),
        pytest.param("claim", (), id="claim"),
        pytest.param("definition_record", (), id="definition_record"),
        pytest.param("disposition", (), id="disposition"),
        pytest.param("capture_ref", (), id="capture_ref"),
        pytest.param("revenue", (VersionState.UNREGISTERED_NUMBER,), id="analytical-revenue"),
    ],
)
def test_only_emitted_id_prefixes_are_structural(
    prefix: str, expected: tuple[VersionState, ...]
) -> None:
    assert (
        scan_section(
            "{{e:computed}} Reference " + prefix + ":500.", resolves=lambda capture, anchor: False
        )
        == expected
    )
