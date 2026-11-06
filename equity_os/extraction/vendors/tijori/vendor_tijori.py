"""Tijori financials page to lossless occurrences for one basis (spec §2–§4).

Only tables whose own key scope is the requested basis are read; a page with none for that
basis is rejected and yields no values (standalone is never stored as consolidated). The
island's numerals declare neither unit nor precision; only the rows an evidenced display rule
of their own (section, basis) scopes (``config/normalisation/mappings/tijori/v5/display.yaml``)
take its unit, and their value is the number the page renders at its displayed precision (the
island number stays as raw evidence). A section without a rule stays ``UNKNOWN_UNIT``.
Periods come from column labels: ``qt_*`` quarters, ``pl_*``/``cf_*`` years, ``bs_*``
instants. The final ``pl_*`` column is TTM, evidenced by the table footer, never a fiscal
period.
"""

from __future__ import annotations

import json
from decimal import ROUND_HALF_DOWN, ROUND_HALF_UP, Decimal
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from equity_os.contracts.measurement.canonical import Basis, PeriodKind, StatementFamily
from equity_os.contracts.measurement.evidence import CaptureReference, Occurrence
from equity_os.contracts.measurement.measurement_key import PeriodInterval
from equity_os.contracts.sourcing.acquisition_outcome import ExtractionOutcome
from equity_os.contracts.sourcing.snapshot import CaptureRecord
from equity_os.extraction.surfaces.vendor_ingest import (
    VendorExtraction,
    VendorExtractionError,
    json_occurrence,
    month_period,
)
from equity_os.extraction.vendors.tijori.tijori_tables import (
    TijoriError,
    TijoriTable,
    TijoriTableScope,
)
from equity_os.normalisation.mapping.interpret import input_digest
from equity_os.sourcing.vendors.tijori.tijori_source import TijoriSource

SOURCE_ID = "tijori"
SURFACE = "financials"
SCHEMA_IDENTITY = "tijori-financials-island-v1"
EXTRACTOR_VERSION = "tijori-v5"  # v5: a display rule per (section, basis)
UNKNOWN_UNIT = "unknown"
_TTM_FOOTER = "TTM Values as of {label}"
_FAMILY = {
    "bs": StatementFamily.BALANCE_SHEET,
    "pl": StatementFamily.PL,
    "qt": StatementFamily.PL,
    "cf": StatementFamily.CASH_FLOW,
    "fr": StatementFamily.DERIVED,
}
_SCOPE = {
    Basis.CONSOLIDATED: TijoriTableScope.CONSOLIDATED,
    Basis.STANDALONE: TijoriTableScope.STANDALONE,
}
_NO_BASIS = "page carries no {basis} financial table; a degenerate response yields no values"


class TijoriBinding(BaseModel):
    """Composition-root issuer identity for one Tijori slug (``config/watchlist.yaml``)."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    slug: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    company_id: int = Field(gt=0)


class TijoriDisplayRule(BaseModel):
    """One island table's evidenced unit and displayed precision (spec §5, VENDOR-1 §6.1)."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    section: str
    basis: Basis
    excluded_labels: tuple[str, ...] = ()  # rows, and subtrees under them, not in the unit
    raw_unit: str
    raw_scale: int
    unit_evidence_ref: str = Field(min_length=1)
    rounding_threshold: Decimal
    decimals_above: int
    decimals_within: int
    precision_evidence_ref: str = Field(min_length=1)

    def decimals(self, value: Decimal) -> int:
        """Decimals Tijori's page displays for ``value``."""
        above = abs(_double(value)) > self.rounding_threshold
        return self.decimals_above if above else self.decimals_within

    def render(self, value: Decimal) -> str:
        """The number Tijori's page displays for ``value``, without digit grouping.

        The script rounds the parsed JavaScript double: ``toFixed`` rounds its exact binary
        value half away from zero (96.005 shows 96.00); ``Math.round`` rounds half toward
        +infinity (-100.5 shows -100).
        """
        double = _double(value)
        above = abs(double) > self.rounding_threshold
        rounding = ROUND_HALF_DOWN if above and double < 0 else ROUND_HALF_UP
        return str(double.quantize(Decimal(1).scaleb(-self.decimals(value)), rounding))


class TijoriDisplayRules(BaseModel):
    """The display rules, at most one per (section, basis)."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    rules: tuple[TijoriDisplayRule, ...]

    @model_validator(mode="after")
    def _one_per_section(self) -> TijoriDisplayRules:
        keys = [(rule.section, rule.basis) for rule in self.rules]
        if len(set(keys)) != len(keys):
            raise ValueError("more than one display rule for a (section, basis)")
        return self

    def rule_for(
        self, section: str, basis: Basis, labels: tuple[str, ...]
    ) -> TijoriDisplayRule | None:
        """The rule scoping a row with these own and parent ``labels``, if any."""
        rule = next((r for r in self.rules if (r.section, r.basis) == (section, basis)), None)
        return None if rule is None or set(rule.excluded_labels) & set(labels) else rule


def _double(value: Decimal) -> Decimal:
    """The exact value of the IEEE double JavaScript parses ``value`` to (-0 as 0)."""
    return Decimal(float(value)) or Decimal(0)


def load_tijori_display(path: Path) -> TijoriDisplayRules:
    """Load the display rule file."""
    return TijoriDisplayRules.model_validate(yaml.safe_load(path.read_bytes()))


def extract_tijori(
    body: bytes,
    *,
    capture: CaptureReference,
    record: CaptureRecord,
    extractor_version: str,
    binding: TijoriBinding,
    display: TijoriDisplayRules,
    basis: Basis,
) -> VendorExtraction:
    """Read every cell of the requested basis's tables from one registered page."""
    try:
        tables = TijoriSource.parse_all_tables_bytes(
            body,
            slug=binding.slug,
            expected_symbol=binding.symbol,
            expected_company_id=binding.company_id,
            retrieved_at=record.retrieved_at,
        )
    except TijoriError as error:
        raise VendorExtractionError(ExtractionOutcome.PARSE_FAILED, str(error)) from error
    scoped = [
        table for table in tables if table.scope is _SCOPE[basis] and table.key.value[:2] in _FAMILY
    ]
    if not scoped:
        raise VendorExtractionError(
            ExtractionOutcome.IDENTITY_REJECTED, _NO_BASIS.format(basis=basis.value)
        )
    occurrences: list[Occurrence] = []
    for table in scoped:
        labels = table.column_period_labels
        for row in table.rows:
            rule = display.rule_for(table.key.value, basis, (row.label, *row.parent_labels))
            lexemes = [(cell.raw_text, cell.value) for cell in row.cells] or [
                (raw, None) for raw in row.unaligned_raw_values
            ]
            for index, (lexeme, value) in enumerate(lexemes):
                column = labels[index] if row.cells else None
                ttm = bool(row.cells) and _is_ttm(table, index)
                occurrences.append(
                    json_occurrence(
                        capture,
                        extractor_version=extractor_version,
                        label=row.label,
                        lexeme=lexeme if rule is None or value is None else rule.render(value),
                        value=value,
                        raw_unit=rule.raw_unit if rule else UNKNOWN_UNIT,
                        raw_scale=rule.raw_scale if rule else 0,
                        declared_precision=None
                        if rule is None or value is None
                        else rule.decimals(value),
                        period=_period(table, index) if row.cells else None,
                        native_context={
                            "schema_identity": SCHEMA_IDENTITY,
                            "basis": basis.value,
                            "statement_family": _FAMILY[table.key.value[:2]].value,
                            "label": row.label,
                            "section": table.key.value,
                            "section_parent": "/".join(row.parent_labels),
                            "field_id": row.field_id,
                            "island_value": lexeme,
                            "header_months": 3 if table.key.value[:2] == "qt" else 12,
                            "header_kind": PeriodKind.TTM.value if ttm else None,
                        },
                        anchor={
                            "anchor_type": "JSON_ISLAND",
                            "table_key": table.key.value,
                            "row_key": row.row_key,
                            "column_index": index,
                            "column_label": column,
                        },
                        disclosure={
                            "alignment": row.alignment.value,
                            "quarantined": not row.cells,
                            "skipped_column": column in table.skipped_period_labels,
                        },
                    )
                )
    reasons = tuple(
        f"{table.key.value}: {row_key} could not be aligned"
        for table in scoped
        for row_key in table.cardinality_mismatch_rows
    )
    return VendorExtraction(
        occurrences=tuple(occurrences),
        outcome=ExtractionOutcome.PARTIAL if reasons else ExtractionOutcome.COMPLETE,
        reasons=reasons,
        issuer=binding.symbol,
        basis=basis,
        extraction_context_sha256=input_digest(
            {
                "surface": capture.surface,
                "capture_sha256": capture.blob_sha256,
                "basis": basis.value,
                "binding": binding.model_dump(mode="json"),
                "display": display.model_dump(mode="json"),
            }
        ),
    )


def _period(table: TijoriTable, index: int) -> PeriodInterval | None:
    """The column's interval from its label; the final ``pl_*`` column only as evidenced TTM.

    A TTM column ending at the fiscal year end keeps its interval and its TTM header kind;
    interpretation refuses that pair as period-ambiguous rather than reading a fiscal year.
    """
    label = table.column_period_labels[index]
    family = table.key.value[:2]
    if family == "fr":
        return None  # A ratio label does not settle its operands' temporal roles.
    year = month_period(label, 12)
    if family == "bs":
        return PeriodInterval.at(year.end) if year is not None and year.end else None
    if family == "qt":
        return month_period(label, 3)
    if family == "pl" and index == len(table.column_period_labels) - 1:
        return year if _is_ttm(table, index) else None
    return year


def _is_ttm(table: TijoriTable, index: int) -> bool:
    """The final ``pl_*`` column whose footer evidences it as TTM, whatever month it ends."""
    label = table.column_period_labels[index]
    footer = json.loads(table.table_footer_json) if table.table_footer_json else None
    return (
        table.key.value[:2] == "pl"
        and index == len(table.column_period_labels) - 1
        and footer == _TTM_FOOTER.format(label=label)
        and month_period(label, 12) is not None
    )
