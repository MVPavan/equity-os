"""Selections, proofs and derived evaluation over one ingested Apar package (D1a Task 7).

A ``PackageView`` selects every key of one stored package under the given pins at a
boundary read from the store clock (never written). Tests evaluate derived rows through
``fundamentals.evidence.derived`` exactly as a run would, with the output measurement's
own qualification context.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from evidence_support import CAPMKT, CONFIG, PDF_LAYOUT, XBRL_ONLY, Ingest, marked_xbrl
from retained_support import MarkedEdit

from fundamentals.canon.dictionary import CanonicalDictionary, load_dictionary
from fundamentals.canon.formula import TraceOperand
from fundamentals.canon.interval import RoundingPolicy, load_rounding_policy
from fundamentals.contracts.canonical import Basis, Representation, TemporalRole, ValueKind
from fundamentals.contracts.comparison import SelectionSource
from fundamentals.contracts.evidence import (
    EligibilityBoundary,
    FilingFamily,
    FilingPackage,
    Interpretation,
    InterpretationTriple,
    KeySelection,
    Occurrence,
    RunMode,
)
from fundamentals.contracts.measurement_key import DimensionSet, MeasurementKey, PeriodInterval
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.qualification import qualification_context
from fundamentals.evidence.alignment import AlignmentProof, load_alignment_rules, prove_alignment
from fundamentals.evidence.derived import DerivedSide, evaluate_derived
from fundamentals.evidence.first_party_ingest import IngestReport
from fundamentals.evidence.interpret import SEGMENT_AXIS, prove_conditions
from fundamentals.evidence.pdf_adapter import PDF_EXTRACTOR_VERSION
from fundamentals.evidence.repository_calc import StoredTrace
from fundamentals.evidence.selection import select_key, select_opening_operand, select_package
from fundamentals.evidence.xbrl_adapter import XBRL_EXTRACTOR_VERSION

ALIGNMENT_V1 = CONFIG / "mappings" / "alignment" / "v1.yaml"
FISCAL_YEAR_END_MONTH = 3
INR = "INR"
SURFACES = {Representation.XBRL: "NSE_XBRL_INSTANCE", Representation.PDF: "NSE_RESULTS_PDF"}
SCHEMAS = {Representation.XBRL: CAPMKT, Representation.PDF: PDF_LAYOUT}
_MONETARY = {ValueKind.CURRENCY_AMOUNT, ValueKind.PER_SHARE_AMOUNT}
FY25_Q4_END = date(2025, 3, 31)
OPENING_CASH = PeriodInterval.at(FY25_Q4_END)
# Keys with a v1 alignment rule that must hold in the Q2 FY26 filing, quarter and H1 alike.
PROVEN = (
    "revenue_from_operations",
    "total_income",
    "total_expenses",
    "profit_for_period",
    "eps_basic",
)
SEGMENTS = ("conductors", "others", "power_telecom_cables", "transformer_and_speciality_oils")
SEGMENT_TOTAL = {"elimination_basis": "PRE_ELIMINATION", "segment": "reportable_segments_total"}
BSE_FIN = "http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin"
# Marked copies of the Q2 FY26 XBRL, each withholding one filed fact (test edits only).
WITHHELD_REVENUE = MarkedEdit(
    label="withheld-revenue",
    find=b'<in-capmkt:RevenueFromOperations contextRef="OneD" decimals="-5" unitRef="INR">'
    b"57154200000</in-capmkt:RevenueFromOperations>",
    replace=b"",
)
WITHHELD_OTHERS = MarkedEdit(
    label="withheld-others-segment-revenue",
    find=b'<in-capmkt:SegmentRevenue contextRef="OneReportable4D" decimals="-5" unitRef="INR">'
    b"334300000</in-capmkt:SegmentRevenue>",
    replace=b"",
)
WITHHELD_OPENING_CASH = MarkedEdit(
    label="withheld-opening-cash",
    find=b'<in-capmkt:CashAndCashEquivalentsCashFlowStatement contextRef="PY_I" decimals="-5" '
    b'unitRef="INR">6864200000</in-capmkt:CashAndCashEquivalentsCashFlowStatement>',
    replace=b"",
)


def triple(mapping_set: str = "v1") -> InterpretationTriple:
    """The interpretation versions a view selects under."""
    return InterpretationTriple(
        mapping_set=mapping_set,
        normalisation_policy="v1",
        extractor_xbrl=XBRL_EXTRACTOR_VERSION,
        extractor_pdf=PDF_EXTRACTOR_VERSION,
    )


def rounding() -> RoundingPolicy:
    """Rounding policy v1."""
    return load_rounding_policy(CONFIG / "rounding_policy" / "v1.yaml")


class PackageView:
    """Every selection of one stored package at the store's current clock."""

    def __init__(
        self, ingest: Ingest, report: IngestReport, *, pins: InterpretationTriple | None = None
    ) -> None:
        self.ingest = ingest
        self.package: FilingPackage = ingest.package(report)
        self.pins = pins or triple()
        self.boundary = EligibilityBoundary.at(ingest.repository.store_clock())
        self.rows: dict[Representation, tuple[tuple[Occurrence, ...], tuple[Interpretation, ...]]]
        self.rows = {}
        for representation, member in self.package.members.items():
            capture_ref_id = member.capture.capture_ref_id
            assert capture_ref_id is not None
            self.rows[representation] = (
                ingest.repository.list_capture_occurrences(capture_ref_id),
                ingest.repository.list_capture_interpretations(capture_ref_id),
            )

    def select(self, key: MeasurementKey, representation: Representation) -> KeySelection:
        """One key's selection in one representation."""
        occurrences, interpretations = self.rows.get(representation, ((), ()))
        return select_key(
            key,
            representation,
            package=self.package,
            occurrences=occurrences,
            interpretations=interpretations,
            boundary=self.boundary,
            mode=RunMode.AS_KNOWN,
            pinned=self.pins,
        )

    def opening(
        self,
        key: MeasurementKey,
        representation: Representation,
        fallback: Callable[[], KeySelection],
    ) -> KeySelection:
        """An opening instant: the package's own disclosure, else ``fallback``."""
        occurrences, interpretations = self.rows.get(representation, ((), ()))
        return select_opening_operand(
            key,
            representation,
            output_package=self.package,
            package_occurrences=occurrences,
            package_interpretations=interpretations,
            boundary=self.boundary,
            mode=RunMode.AS_KNOWN,
            pinned=self.pins,
            fallback=fallback,
        )

    def selections(self) -> dict[tuple[str, Representation], KeySelection]:
        """Every keyed line of every member, selected, by (key digest, representation)."""
        found = {}
        for representation, (_, interpretations) in self.rows.items():
            for key in {item.key for item in interpretations if item.key is not None}:
                found[(key.digest(), representation)] = self.select(key, representation)
        return found

    def stored_proofs(self, rules_path: Path = ALIGNMENT_V1) -> tuple[AlignmentProof, ...]:
        """Prove alignment for every selected key and store the proofs."""
        proofs = prove_alignment(self.package, self.selections(), load_alignment_rules(rules_path))
        return self.ingest.repository.put_alignment_proofs(proofs)

    def key(
        self,
        canonical_id: str,
        period: PeriodInterval,
        dictionary: CanonicalDictionary,
        dimensions: dict[str, str] | None = None,
    ) -> MeasurementKey:
        """A consolidated Ind AS key of this entity at the row's value kind."""
        kind = dictionary.row(canonical_id).value_kind
        return MeasurementKey(
            entity_id=self.package.entity_id,
            canonical_id=canonical_id,
            period=period,
            basis=Basis.CONSOLIDATED,
            framework=AccountingFramework.IND_AS,
            currency=INR if kind in _MONETARY else None,
            value_kind=kind,
            dimensions=DimensionSet.of(dimensions or {}),
        )

    def evaluate(
        self,
        canonical_id: str,
        period: PeriodInterval,
        representation: Representation,
        *,
        dictionary: CanonicalDictionary,
        proofs: tuple[AlignmentProof, ...] = (),
        dimensions: dict[str, str] | None = None,
    ) -> DerivedSide:
        """Evaluate one derived row for this package in one representation."""
        row = dictionary.row(canonical_id)
        output = self.key(canonical_id, period, dictionary, dimensions)
        scope = row.formula.qualification if row.formula is not None else None
        conditions = () if scope is None else (*scope.conditions, *scope.exclusions)
        _, interpretations = self.rows.get(representation, ((), ()))
        proven = prove_conditions(
            conditions, interpretations=interpretations, period=period, basis=Basis.CONSOLIDATED
        )
        repository = self.ingest.repository
        return evaluate_derived(
            row,
            output,
            representation=representation,
            resolve=lambda key, role: self._resolve(key, role, representation),
            proofs=proofs,
            qualification=qualification_context(
                output,
                schema_identity=SCHEMAS[representation],
                surface=SURFACES[representation],
                fiscal_year_end_month=FISCAL_YEAR_END_MONTH,
                proven=proven,
            ),
            policy=rounding(),
            repository=repository,
            dictionary=dictionary,
            reporting_currency=INR,
            segment_members=repository.segment_members_as_of(
                self.package.entity_id, SEGMENT_AXIS, self.boundary.first_seen_cutoff
            ),
        )

    def _resolve(
        self, key: MeasurementKey, role: TemporalRole, representation: Representation
    ) -> KeySelection:
        """Duration and closing operands from this package (no v1 formula reads an opening)."""
        assert role is not TemporalRole.OPENING, "opening operands are tested via select_opening"
        return self.select(key, representation)


def temp_dictionary(tmp_path: Path, edit: Callable[[dict[str, Any]], None]) -> CanonicalDictionary:
    """Dictionary v1 with ``derived.yaml`` edited, loaded from a copy under ``tmp_path``."""
    root = tmp_path / f"dictionary-{len(list(tmp_path.glob('dictionary-*')))}"
    shutil.copytree(CONFIG / "dictionary", root)
    path = root / "v1" / "derived.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    edit(data)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return load_dictionary(root, "v1")


def scope_formula(canonical_id: str, scope: dict[str, Any]) -> Callable[[dict[str, Any]], None]:
    """Edit: one formula demonstrated inside ``scope``."""

    def edit(data: dict[str, Any]) -> None:
        (row,) = [item for item in data["rows"] if item["canonical_id"] == canonical_id]
        row["formula"]["tier"] = "EQUIVALENCE_DEMONSTRATED"
        row["formula"]["qualification"] = scope

    return edit


def operands_by_name(stored: StoredTrace) -> dict[str, TraceOperand]:
    """A stored trace's operand rows by name."""
    return {operand.name: operand for operand in stored.trace.operands}


def marked_xbrl_package(ingest: Ingest, edit: MarkedEdit) -> PackageView:
    """A one-member package of a marked Q2 FY26 XBRL copy."""
    marked = marked_xbrl(ingest.tmp_path, edit)
    report = ingest.run(ingest.intake(XBRL_ONLY, marked={Representation.XBRL: marked}))
    return PackageView(ingest, report)


def xbrl_scope(
    scope_id: str, bases: list[str], period_kinds: list[str], schema: str = CAPMKT
) -> dict[str, Any]:
    """A raw XBRL-instance qualification scope."""
    return {
        "scope_id": scope_id,
        "schema_identities": [schema],
        "surfaces": [SURFACES[Representation.XBRL]],
        "bases": bases,
        "period_kinds": period_kinds,
    }


def scope_entry(entry_id: str, scope: dict[str, Any]) -> Callable[[dict[str, Any]], None]:
    """Edit: one mapping entry demonstrated inside ``scope``."""

    def edit(data: dict[str, Any]) -> None:
        data["entries"] = [
            {**item, "tier": "EQUIVALENCE_DEMONSTRATED", "qualification": scope}
            if item["entry_id"] == entry_id
            else item
            for item in data["entries"]
        ]

    return edit


def historical_fallback(
    ingest: Ingest, historical: PackageView, key: MeasurementKey, boundary: EligibilityBoundary
) -> KeySelection:
    """The opening instant from the package ending on it, selected as a run would."""
    period_end = key.period.instant
    assert period_end is not None
    package = select_package(
        ingest.repository.list_packages(
            ingest.entity_id, FilingFamily.FINANCIAL_RESULTS, period_end
        ),
        entity_id=ingest.entity_id,
        family=FilingFamily.FINANCIAL_RESULTS,
        statement_family=ingest.dictionary.row(key.canonical_id).family,
        basis=Basis.CONSOLIDATED,
        framework=AccountingFramework.IND_AS,
        period_end=period_end,
        boundary=boundary,
    )
    assert package == historical.package
    return historical.select(key, Representation.XBRL).model_copy(
        update={"source": SelectionSource.HISTORICAL_PACKAGE}
    )
