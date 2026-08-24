"""Project the pipeline's validated facts into a thesis :class:`ValidatedFactSet`.

Two entry points, one contract out:

* :func:`from_gold_file` reads a persisted gold file — the durable reconciliation
  record — which carries full provenance anchors (PDF page/block/span or XBRL
  context, plus a sha256), so the thesis can footnote every figure. This is the
  richest source and what the demo uses.
* :func:`from_stock_report` consumes an in-memory :class:`StockReport` straight
  from the goal runner. That structure is thinner (per-source readings carry no
  page/span anchor), so anchors degrade to the source id; the reconciliation and
  values are identical.

Only ``AGREE``/``MINOR_DIFF`` facts and single-first-party facts (value present)
are passed as citable facts; conflicts and missing concepts become ``unknowns``.
This module owns the seam to the pipeline, keeping that dependency out of the
thesis core (which depends only on :mod:`fundamentals.thesis.contracts`).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, assert_never

from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.reconcile.agreement import AgreementStatus
from fundamentals.reconcile.gold_file import GoldFact, read_gold_file
from fundamentals.thesis.contracts import (
    FactAnchor,
    Unknown,
    UnknownReason,
    ValidatedFact,
    ValidatedFactSet,
)

if TYPE_CHECKING:
    from fundamentals.api.goal_runner import StockReport

_SHA_PREFIX_LEN = 12
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")

# The goal runner canonicalises every retained fact onto the consolidated Ind AS
# comparison column (see goal_runner._canonicalise); a StockReport does not restate
# these per fact, so they are the honest basis to report for that path.
_CANONICAL_SCOPE = "consolidated"
_CANONICAL_BASIS = "IND_AS"

# Facts with a retained value the models may cite.
_RETAINED_STATUSES: frozenset[AgreementStatus] = frozenset(
    {AgreementStatus.AGREE, AgreementStatus.MINOR_DIFF, AgreementStatus.SINGLE_FIRST_PARTY}
)

_LABEL_OVERRIDES: dict[str, str] = {
    "in-bse-fin:RevenueFromOperations": "Revenue from operations",
    "in-bse-fin:Income": "Total income",
    "in-bse-fin:Expenses": "Total expenses",
    "in-bse-fin:ProfitBeforeTax": "Profit before tax",
    "in-bse-fin:ProfitLossForPeriod": "Profit for the period (PAT)",
    "in-bse-fin:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations": "Basic EPS",
}


def _concept_label(concept_qname: str) -> str:
    """Human label for a concept: a curated override, else a de-CamelCased local name."""
    override = _LABEL_OVERRIDES.get(concept_qname)
    if override is not None:
        return override
    local = concept_qname.split(":", 1)[-1]
    return _CAMEL_BOUNDARY.sub(" ", local)


def _anchor_description(provenance: Provenance) -> str:
    """One-line, document-text-free pointer to a source location plus a sha prefix."""
    sha = provenance.file_sha256[:_SHA_PREFIX_LEN]
    if provenance.anchor_type is SourceAnchorType.PDF_SPAN:
        location = f"page {provenance.page}, block {provenance.block}, span {provenance.span}"
    elif provenance.anchor_type is SourceAnchorType.XBRL_CONTEXT:
        location = f"context {provenance.context_ref}"
    elif provenance.anchor_type is SourceAnchorType.JSON_ISLAND:
        location = (
            f"JSON island {provenance.island_id}, table {provenance.table_key}, "
            f"row {provenance.row_label}, column {provenance.column_label}"
        )
    else:
        assert_never(provenance.anchor_type)
    return f"{location} (sha {sha}…)"


def _is_retained(status: AgreementStatus, value: str | None) -> bool:
    """Whether a fact carries a citable retained value."""
    return status in _RETAINED_STATUSES and value is not None


def _gold_fact_to_validated(fact: GoldFact) -> ValidatedFact:
    """Project a retained gold fact into a citable validated fact with anchors."""
    key = fact.comparison_key
    anchors = tuple(
        FactAnchor(
            source_id=value.source_id,
            source_class=value.source_class.value,
            value=str(value.normalized_value),
            description=_anchor_description(value.provenance),
        )
        for value in fact.source_values
    )
    return ValidatedFact(
        concept_qname=fact.concept_qname,
        label=_concept_label(fact.concept_qname),
        value=str(fact.value),
        unit=fact.normalized_unit,
        status=fact.agreement_status.value,
        agreed_sources=fact.agreed_sources,
        corroborating_sources=fact.corroborating_sources,
        first_party_source_count=fact.first_party_source_count,
        single_sourced=fact.agreement_status is AgreementStatus.SINGLE_FIRST_PARTY,
        period_start=key.period_start.isoformat() if key.period_start else None,
        period_end=key.period_end.isoformat() if key.period_end else None,
        scope=key.scope.value,
        currency=key.currency,
        anchors=anchors,
    )


def from_gold_file(path: Path, *, name: str = "", domain: str = "") -> ValidatedFactSet:
    """Build a validated fact set from a persisted gold file (richest anchors)."""
    gold = read_gold_file(path)
    facts: list[ValidatedFact] = []
    unknowns: list[Unknown] = []
    for fact in gold.facts:
        if _is_retained(fact.agreement_status, fact.value):
            facts.append(_gold_fact_to_validated(fact))
        else:
            unknowns.append(
                Unknown(
                    concept_qname=fact.concept_qname,
                    label=_concept_label(fact.concept_qname),
                    reason=UnknownReason.CONFLICT,
                    detail=f"agreement status {fact.agreement_status.value}; no retained value",
                )
            )

    reference = gold.facts[0].comparison_key if gold.facts else None
    return ValidatedFactSet(
        symbol=gold.symbol,
        name=name,
        domain=domain,
        quarter=gold.quarter,
        period_start=reference.period_start.isoformat()
        if reference and reference.period_start
        else None,
        period_end=reference.period_end.isoformat() if reference and reference.period_end else None,
        scope=reference.scope.value if reference else _CANONICAL_SCOPE,
        basis=reference.accounting_basis.value if reference else _CANONICAL_BASIS,
        currency=reference.currency if reference else None,
        facts=tuple(facts),
        unknowns=tuple(unknowns),
    )


def from_stock_report(report: StockReport) -> ValidatedFactSet:
    """Build a validated fact set from an in-memory goal-runner ``StockReport``.

    Anchors degrade to the source id (a ``StockReport`` reading carries no
    page/span); values, statuses, and source classes are preserved unchanged.
    """
    facts: list[ValidatedFact] = []
    unknowns: list[Unknown] = []
    currency: str | None = None
    for fact in report.facts:
        if not _is_retained(fact.status, fact.agreed_value):
            unknowns.append(
                Unknown(
                    concept_qname=fact.concept_qname,
                    label=_concept_label(fact.concept_qname),
                    reason=UnknownReason.CONFLICT,
                    detail=f"agreement status {fact.status.value}; no retained value",
                )
            )
            continue
        unit = fact.readings[0].normalized_unit if fact.readings else ""
        anchors = tuple(
            FactAnchor(
                source_id=reading.source_id,
                source_class=reading.source_class.value,
                value=reading.value,
                description=f"{reading.source_id} reading (no page/span anchor in StockReport)",
            )
            for reading in fact.readings
        )
        facts.append(
            ValidatedFact(
                concept_qname=fact.concept_qname,
                label=_concept_label(fact.concept_qname),
                value=str(fact.agreed_value),
                unit=unit,
                status=fact.status.value,
                agreed_sources=fact.agreed_sources,
                corroborating_sources=fact.corroborating_sources,
                first_party_source_count=fact.first_party_source_count,
                single_sourced=fact.status is AgreementStatus.SINGLE_FIRST_PARTY,
                period_start=None,
                period_end=None,
                scope=_CANONICAL_SCOPE,
                currency=None,
                anchors=anchors,
            )
        )

    unknowns.extend(
        Unknown(
            concept_qname=concept,
            label=_concept_label(concept),
            reason=UnknownReason.MISSING,
            detail="no source reported this concept for the quarter",
        )
        for concept in report.missing_material_concepts
    )

    return ValidatedFactSet(
        symbol=report.symbol,
        name=report.name,
        domain=report.domain,
        quarter=report.quarter,
        period_start=None,
        period_end=None,
        scope=_CANONICAL_SCOPE,
        basis=_CANONICAL_BASIS,
        currency=currency,
        facts=tuple(facts),
        unknowns=tuple(unknowns),
    )
