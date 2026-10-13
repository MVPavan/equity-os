"""Native operands coexist with ordinary mapped rows in one generation."""

from fractions import Fraction
from pathlib import Path

import pytest
from evidence_support import dictionary, policy
from test_native_construction import _native_mapping, _occurrence
from test_native_construction_store import _run, _scope

from fundamentals.canon.dictionary import CanonicalDictionary
from fundamentals.contracts.evidence import InterpretationStatus
from fundamentals.evidence.mapping import NormalisationPolicy
from fundamentals.evidence.native_construction import (
    NativeConstructionDefect,
    NativeConstructionError,
)

__all__ = ["dictionary", "policy"]


def test_mapped_native_nonoperand_does_not_abort_the_aggregate(
    tmp_path: Path, dictionary: CanonicalDictionary, policy: NormalisationPolicy
) -> None:
    mappings = _native_mapping(tmp_path / "mappings", dictionary)
    rows = _run(
        [
            _occurrence(1, "Borrowings", "10.25"),
            _occurrence(2, "Other Liabilities", "20.50"),
            _occurrence(3, "Unused assets", "99.75"),
        ],
        scope=_scope(mappings, dictionary, policy),
    )
    assert rows[2].status is InterpretationStatus.MAPPED
    assert rows[2].canonical_id == "total_assets"
    assert rows[3].canonical_id == "liabilities_incl_nci"
    assert rows[3].status is InterpretationStatus.MAPPED
    assert rows[3].value == Fraction(307_500_000)
    assert rows[3].operand_interpretation_ids == (100, 101)


def test_mapped_nonoperand_still_requires_actual_generation_provenance(
    tmp_path: Path, dictionary: CanonicalDictionary, policy: NormalisationPolicy
) -> None:
    mappings = _native_mapping(tmp_path / "mappings", dictionary)
    outsider = _occurrence(3, "Unused assets", "99.75")
    outsider = outsider.model_copy(
        update={"capture": outsider.capture.model_copy(update={"capture_ref_id": 18})}
    )
    with pytest.raises(NativeConstructionError) as caught:
        _run(
            [
                _occurrence(1, "Borrowings", "10.25"),
                _occurrence(2, "Other Liabilities", "20.50"),
                outsider,
            ],
            scope=_scope(mappings, dictionary, policy),
        )
    assert caught.value.defect is NativeConstructionDefect.PROVENANCE_MISMATCH
