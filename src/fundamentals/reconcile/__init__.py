"""Fundamentals reconcile layer — cross-source agreement and the gold file.

Exports the per-fact agreement classifier (AGREE / MINOR_DIFF / CONFLICT /
SINGLE_FIRST_PARTY) and the per-stock gold-file reader/writer + drift regression
the goal runner wires together.
"""

from fundamentals.reconcile.agreement import (
    DEFAULT_POLICY,
    AgreementPolicy,
    AgreementResult,
    AgreementStatus,
    SourceClass,
    SourceValue,
    classify_agreement,
    classify_source,
)
from fundamentals.reconcile.gold_file import (
    GOLD_SCHEMA_VERSION,
    Drift,
    DriftKind,
    GoldFact,
    GoldFile,
    RegressReport,
    build_gold_file,
    canonical_json,
    gold_file_path,
    read_gold_file,
    regress,
    write_gold_file,
)

__all__ = [
    "DEFAULT_POLICY",
    "GOLD_SCHEMA_VERSION",
    "AgreementPolicy",
    "AgreementResult",
    "AgreementStatus",
    "Drift",
    "DriftKind",
    "GoldFact",
    "GoldFile",
    "RegressReport",
    "SourceClass",
    "SourceValue",
    "build_gold_file",
    "canonical_json",
    "classify_agreement",
    "classify_source",
    "gold_file_path",
    "read_gold_file",
    "regress",
    "write_gold_file",
]
