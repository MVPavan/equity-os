"""The unpublished first-party bridge declares and enforces consolidated scope."""

from __future__ import annotations

from pathlib import Path

from test_vendor_dictionary_bridge import (
    BRIDGE_ID,
    BSE_SCHEMA,
    DICTIONARY_ROOT,
    NOW,
    ROOT,
    _capture,
    _isolated_mapping_root,
    _occurrence,
    _reserve_ids,
)

from fundamentals.canon.dictionary import load_dictionary
from fundamentals.contracts.canonical import Basis
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.evidence.capture_interpretation import CaptureScope, interpret_generation
from fundamentals.evidence.mapping import load_mapping_set, load_normalisation_policy


def test_first_party_bridge_declares_consolidated_basis_and_refuses_standalone(
    tmp_path: Path,
) -> None:
    dictionary = load_dictionary(DICTIONARY_ROOT, "v2")
    mappings = load_mapping_set(
        _isolated_mapping_root(tmp_path), "dictionary-bridge-draft", dictionary=dictionary
    )
    rules = [item for item in mappings.constructions if item.canonical_id == BRIDGE_ID]
    assert rules and all(item.bases == frozenset({Basis.CONSOLIDATED}) for item in rules)

    capture = _capture()
    occurrences = []
    for occurrence_id, native_field, value in (
        (1, "OtherIncome", "467906000.00"),
        (2, "ExceptionalItemsBeforeTax", "-56992000.00"),
    ):
        occurrence = _occurrence(occurrence_id, native_field, value, capture=capture)
        occurrences.append(
            occurrence.model_copy(
                update={
                    "native_context": {
                        **occurrence.native_context,
                        "basis": Basis.STANDALONE.value,
                        "schema_identity": BSE_SCHEMA,
                    }
                }
            )
        )
    rows = interpret_generation(
        occurrences,
        scope=CaptureScope(
            capture=capture,
            entity_id=7,
            basis=Basis.STANDALONE,
            framework=AccountingFramework.IND_AS,
            mapping_set=mappings,
            policy=load_normalisation_policy(ROOT / "config/normalisation_policy/v1.yaml"),
            dictionary=dictionary,
            fiscal_year_end_month=3,
        ),
        prior=(),
        prior_anchor_keys={},
        reserve_ids=_reserve_ids(),  # type: ignore[arg-type]
        recorded_at=NOW,
    )
    assert not [item for item in rows if item.canonical_id == BRIDGE_ID]
