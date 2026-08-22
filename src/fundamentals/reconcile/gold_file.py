"""Per-stock gold reference file: retained cross-source values and drift regression.

A gold file (``data/gold/<symbol>-<quarter>.json``; ``data/`` is gitignored) is
the durable, human-reviewed record of what every source said about each material
fact for one stock-quarter and how they reconciled. It carries, per fact, the
retained cross-source value, the full comparison key, every source's value with
provenance, the agreement status, and the count of independent first-party
sources — enough to re-audit the reconciliation without re-running extraction.

The file is written as deterministic canonical JSON (sorted keys, facts ordered
by comparison key, Decimals serialized as strings) so that re-writing an
unchanged reconciliation produces byte-identical output. On re-runs, ``regress``
compares a fresh extraction against the stored gold file and reports any drift —
a changed value, a changed status, or a fact that appeared or disappeared.
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path

import structlog
from pydantic import BaseModel, ConfigDict

from fundamentals.reconcile.agreement import AgreementResult, AgreementStatus, SourceValue
from fundamentals.verify.comparison_key import ComparisonKey

_LOGGER = structlog.get_logger("fundamentals.reconcile.gold_file")

# Bump when the on-disk schema changes in a backward-incompatible way.
GOLD_SCHEMA_VERSION = 1

DEFAULT_GOLD_DIR = Path("data/gold")


class GoldFact(BaseModel):
    """One material fact as retained in a gold file."""

    model_config = ConfigDict(frozen=True)

    concept_qname: str
    comparison_key: ComparisonKey
    value: str | None
    normalized_unit: str
    agreement_status: AgreementStatus
    agreed_sources: tuple[str, ...]
    corroborating_sources: tuple[str, ...]
    incompatible_sources: tuple[str, ...]
    first_party_source_count: int
    needs_human_review: bool
    source_values: tuple[SourceValue, ...]


class GoldFile(BaseModel):
    """A per-stock-quarter reference of reconciled cross-source facts."""

    model_config = ConfigDict(frozen=True)

    schema_version: int
    symbol: str
    quarter: str
    facts: tuple[GoldFact, ...]


class DriftKind(StrEnum):
    """The kind of drift detected between a stored gold file and a fresh extraction."""

    VALUE_DRIFT = "value_drift"
    STATUS_CHANGE = "status_change"
    MISSING_IN_FRESH = "missing_in_fresh"
    NEW_IN_FRESH = "new_in_fresh"


class Drift(BaseModel):
    """One detected divergence between the gold file and a fresh extraction."""

    model_config = ConfigDict(frozen=True)

    kind: DriftKind
    concept_qname: str
    gold_value: str | None = None
    fresh_value: str | None = None
    gold_status: AgreementStatus | None = None
    fresh_status: AgreementStatus | None = None
    detail: str


class RegressReport(BaseModel):
    """Outcome of regressing a fresh extraction against a stored gold file."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    quarter: str
    drifts: tuple[Drift, ...]

    @property
    def has_drift(self) -> bool:
        """Whether any divergence was detected."""
        return bool(self.drifts)


def _value_to_str(value: object) -> str | None:
    """Render an agreed Decimal value as a canonical string (or ``None``)."""
    return None if value is None else str(value)


def _gold_fact(result: AgreementResult) -> GoldFact:
    """Project an agreement result into its retained gold-fact record."""
    return GoldFact(
        concept_qname=result.comparison_key.concept_qname,
        comparison_key=result.comparison_key,
        value=_value_to_str(result.agreed_value),
        normalized_unit=result.normalized_unit,
        agreement_status=result.status,
        agreed_sources=result.agreed_sources,
        corroborating_sources=result.corroborating_sources,
        incompatible_sources=result.incompatible_sources,
        first_party_source_count=result.first_party_source_count,
        needs_human_review=result.needs_human_review,
        source_values=result.source_values,
    )


def _sort_key(fact: GoldFact) -> tuple[str, str, str]:
    """Deterministic ordering key for gold facts within a file."""
    key = fact.comparison_key
    period = "|".join(
        "" if part is None else part.isoformat()
        for part in (key.period_start, key.period_end, key.period_instant)
    )
    return (fact.concept_qname, str(key.scope), period)


def build_gold_file(symbol: str, quarter: str, results: list[AgreementResult]) -> GoldFile:
    """Assemble a :class:`GoldFile` from per-fact agreement results, deterministically ordered."""
    facts = tuple(sorted((_gold_fact(result) for result in results), key=_sort_key))
    return GoldFile(
        schema_version=GOLD_SCHEMA_VERSION,
        symbol=symbol,
        quarter=quarter,
        facts=facts,
    )


def canonical_json(gold: GoldFile) -> str:
    """Serialize a gold file as deterministic canonical JSON with a trailing newline."""
    payload = gold.model_dump(mode="json")
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"


def gold_file_path(symbol: str, quarter: str, out_dir: Path = DEFAULT_GOLD_DIR) -> Path:
    """Return the gold-file path for a stock-quarter under ``out_dir``."""
    return out_dir / f"{symbol}-{quarter}.json"


def write_gold_file(
    symbol: str,
    quarter: str,
    results: list[AgreementResult],
    out_dir: Path = DEFAULT_GOLD_DIR,
) -> Path:
    """Write the per-stock gold reference and return its path.

    ``out_dir`` (default ``data/gold``, gitignored) is created if absent. Output
    is deterministic canonical JSON.
    """
    gold = build_gold_file(symbol, quarter, results)
    path = gold_file_path(symbol, quarter, out_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(gold), encoding="utf-8")
    _LOGGER.info(
        "wrote_gold_file",
        symbol=symbol,
        quarter=quarter,
        path=str(path),
        fact_count=len(gold.facts),
    )
    return path


def read_gold_file(path: Path) -> GoldFile:
    """Read and validate a gold file from disk."""
    return GoldFile.model_validate_json(path.read_text(encoding="utf-8"))


def regress(gold: GoldFile, fresh: list[AgreementResult]) -> RegressReport:
    """Compare a fresh extraction against a stored gold file and report drift.

    Facts are matched by full comparison key. A changed retained value or changed
    agreement status is drift; so is a gold fact missing from the fresh run, or a
    fresh fact absent from the gold file.
    """
    fresh_by_key: dict[ComparisonKey, AgreementResult] = {
        result.comparison_key: result for result in fresh
    }
    drifts: list[Drift] = []
    seen: set[ComparisonKey] = set()

    for fact in gold.facts:
        key = fact.comparison_key
        seen.add(key)
        fresh_result = fresh_by_key.get(key)
        if fresh_result is None:
            drifts.append(
                Drift(
                    kind=DriftKind.MISSING_IN_FRESH,
                    concept_qname=fact.concept_qname,
                    gold_value=fact.value,
                    gold_status=fact.agreement_status,
                    detail=f"{fact.concept_qname} present in gold file but absent from fresh run",
                )
            )
            continue

        fresh_value = _value_to_str(fresh_result.agreed_value)
        if fresh_value != fact.value:
            drifts.append(
                Drift(
                    kind=DriftKind.VALUE_DRIFT,
                    concept_qname=fact.concept_qname,
                    gold_value=fact.value,
                    fresh_value=fresh_value,
                    detail=(
                        f"{fact.concept_qname} value drifted: "
                        f"gold {fact.value} -> fresh {fresh_value}"
                    ),
                )
            )
        if fresh_result.status != fact.agreement_status:
            drifts.append(
                Drift(
                    kind=DriftKind.STATUS_CHANGE,
                    concept_qname=fact.concept_qname,
                    gold_status=fact.agreement_status,
                    fresh_status=fresh_result.status,
                    detail=(
                        f"{fact.concept_qname} status changed: "
                        f"gold {fact.agreement_status} -> fresh {fresh_result.status}"
                    ),
                )
            )

    for key, result in fresh_by_key.items():
        if key not in seen:
            drifts.append(
                Drift(
                    kind=DriftKind.NEW_IN_FRESH,
                    concept_qname=key.concept_qname,
                    fresh_value=_value_to_str(result.agreed_value),
                    fresh_status=result.status,
                    detail=f"{key.concept_qname} present in fresh run but absent from gold file",
                )
            )

    return RegressReport(symbol=gold.symbol, quarter=gold.quarter, drifts=tuple(drifts))
