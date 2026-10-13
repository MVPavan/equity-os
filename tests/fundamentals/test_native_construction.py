"""Source-native construction contracts and v1 compatibility."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import yaml
from evidence_support import dictionary, mapping_set, policy
from selection_support import interpretation, key, member

from fundamentals.canon.dictionary import CanonicalDictionary
from fundamentals.contracts.canonical import Basis, PeriodKind, Representation, StatementFamily
from fundamentals.contracts.evidence import (
    CaptureReference,
    InterpretationStatus,
    KnowledgeTimeStatus,
    MissingValueState,
    Occurrence,
    PrecisionKind,
    RevisionCause,
    VendorExtractorPin,
)
from fundamentals.contracts.evidence_tier import EvidenceTier
from fundamentals.contracts.interval import Interval
from fundamentals.contracts.measurement_key import PeriodInterval
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.qualification import QualificationContext
from fundamentals.evidence.capture_interpretation import CaptureScope, interpret_generation
from fundamentals.evidence.interpret import construct
from fundamentals.evidence.mapping import MappingSet, NormalisationPolicy, load_mapping_set

__all__ = ["dictionary", "mapping_set", "policy"]

NOW = datetime(2026, 10, 13, tzinfo=UTC)
LEGACY_MAPPING_SHA256 = "9a1389b4bc2ddc76c3a846f7cbd0a6ab59aa880b6c03961e55f0b1b130c08b24"
LEGACY_RULE_ID = "capmkt.profit_before_tax_incl_associates"
SOURCE = "screener-subscriber"
SURFACE = "SCREENER_FINANCIALS"
SCHEMA = "screener-financials-html-v1"
CAPTURE = CaptureReference(
    capture_ref_id=17,
    source_id=SOURCE,
    surface=SURFACE,
    request_key="native-construction-request",
    capture_id="native-construction-capture",
    blob_sha256="1" * 64,
    record_sha256="2" * 64,
    registered_at=NOW,
    first_seen_at=NOW,
)


def _native_mapping(root: Path, dictionary: CanonicalDictionary) -> MappingSet:
    """A private valid mapping bundle whose only construction uses native selectors."""
    root.mkdir()
    (root / "native-v2.yaml").write_text(
        yaml.safe_dump(
            {
                "version": "native-v2",
                "normalisation_policy_version": "v1",
                "entry_files": ["entries.yaml"],
                "construction_files": ["constructions.yaml"],
            },
            sort_keys=False,
        )
    )
    (root / "entries.yaml").write_text(
        yaml.safe_dump(
            {
                "source": SOURCE,
                "surface": SURFACE,
                "schema_identity": SCHEMA,
                "entries": [
                    {
                        "entry_id": "test.unused_assets",
                        "selector": {
                            "statement_family": "BALANCE_SHEET",
                            "labels": ["Unused assets"],
                            "section_equals": "balance-sheet",
                        },
                        "canonical_id": "total_assets",
                        "period_rule": "COLUMN_INSTANT",
                        "basis": ["CONSOLIDATED"],
                        "period_kinds": ["INSTANT"],
                        "evidence_ref": "synthetic loader sentinel",
                    }
                ],
            },
            sort_keys=False,
        )
    )
    operand_common: Mapping[str, object] = {
        "sign": 1,
        "unit_transform": "SCALE_TO_BASE_UNIT",
        "precision_rule": "DECLARED",
        "value_kind": "CURRENCY_AMOUNT",
        "currency": "INR",
        "period_nature": "INSTANT",
        "dimension_members": {},
        "bases": ["CONSOLIDATED"],
        "period_kinds": ["INSTANT"],
    }
    (root / "constructions.yaml").write_text(
        yaml.safe_dump(
            {
                "constructions": [
                    {
                        "rule_id": "screener.liabilities_incl_nci",
                        "source": SOURCE,
                        "surface": SURFACE,
                        "schema_identity": SCHEMA,
                        "canonical_id": "liabilities_incl_nci",
                        "operands": [
                            {
                                "name": "borrowings",
                                "native": {
                                    **operand_common,
                                    "selector": {
                                        "statement_family": "BALANCE_SHEET",
                                        "labels": ["Borrowings"],
                                        "section_equals": "balance-sheet",
                                    },
                                    "evidence_ref": "synthetic Borrowings cell",
                                },
                            },
                            {
                                "name": "other_liabilities",
                                "native": {
                                    **operand_common,
                                    "selector": {
                                        "statement_family": "BALANCE_SHEET",
                                        "labels": ["Other Liabilities"],
                                        "section_equals": "balance-sheet",
                                    },
                                    "evidence_ref": "synthetic Other Liabilities cell",
                                },
                            },
                        ],
                        "expression": {
                            "op": "ADD",
                            "args": [
                                {"op": "OPERAND", "operand": "borrowings"},
                                {"op": "OPERAND", "operand": "other_liabilities"},
                            ],
                        },
                        "evidence_ref": "synthetic native construction",
                    }
                ]
            },
            sort_keys=False,
        )
    )
    return load_mapping_set(root, "native-v2", dictionary=dictionary)


def _occurrence(occurrence_id: int, label: str, value: str) -> Occurrence:
    return Occurrence(
        occurrence_id=occurrence_id,
        capture=CAPTURE,
        representation=Representation.HTML,
        extractor_version="screener-extractor-v2",
        native_field=label,
        raw_value_text=value,
        raw_unit="INR",
        raw_scale=7,
        raw_sign=1,
        precision_kind=PrecisionKind.FINITE,
        declared_precision=2,
        native_context={
            "schema_identity": SCHEMA,
            "basis": Basis.CONSOLIDATED.value,
            "statement_family": StatementFamily.BALANCE_SHEET.value,
            "label": label,
            "section": "balance-sheet",
        },
        period=PeriodInterval.at(date(2026, 3, 31)),
        missing_state=MissingValueState.VALUE,
        disclosure={},
        anchor={"label": label},
        anchor_key=f"balance-sheet:{label}",
        knowledge_time=NOW,
        knowledge_time_status=KnowledgeTimeStatus.KNOWN,
        first_seen_at=NOW,
        revision_cause=RevisionCause.ORIGINAL,
    )


def _reserve() -> object:
    next_id = 100

    def reserve(count: int) -> tuple[int, ...]:
        nonlocal next_id
        found = tuple(range(next_id, next_id + count))
        next_id += count
        return found

    return reserve


def test_v1_construction_contract_is_unchanged(
    dictionary: CanonicalDictionary,
    mapping_set: MappingSet,
    policy: NormalisationPolicy,
) -> None:
    """Adding native operands must not change the published v1 pin, dump, or result."""
    del dictionary
    rule = next(item for item in mapping_set.constructions if item.rule_id == LEGACY_RULE_ID)

    assert mapping_set.content_sha256 == LEGACY_MAPPING_SHA256
    assert rule.model_dump(mode="json", exclude_defaults=True) == {
        "rule_id": LEGACY_RULE_ID,
        "surface": "NSE_XBRL_INSTANCE",
        "schema_identity": "http://www.sebi.gov.in/xbrl/2025-01-31/in-capmkt",
        "canonical_id": "profit_before_tax_incl_associates",
        "operands": [
            {"name": "pbt", "mapping_entry_id": "capmkt.profit_before_tax"},
            {
                "name": "associates",
                "mapping_entry_id": "capmkt.share_of_profit_associates_jv",
            },
        ],
        "expression": {
            "op": "ADD",
            "args": [
                {"op": "OPERAND", "operand": "pbt"},
                {"op": "OPERAND", "operand": "associates"},
            ],
        },
        "evidence_ref": (
            "X-Q2 (sha256 90baae0b) OneD: ProfitBeforeTax 3,405,600,000 + "
            "ShareOfProfitLossOfAssociates... -300,000 = 3,405,300,000 = "
            'SegmentProfitBeforeTax and PDF p3 line 9 "Profit before tax (7+8)" 340.53 '
            "crore; the instance files no separate after-associates PBT element."
        ),
    }

    owner = member(Representation.XBRL, 1, NOW, NOW)
    pbt = interpretation(
        1,
        owner,
        measurement=key("profit_before_tax"),
        crore="340.56",
        recorded_at=NOW,
    )
    associates = interpretation(
        2,
        owner,
        measurement=key("share_of_profit_associates_jv"),
        crore="-0.03",
        recorded_at=NOW,
    )
    result = construct(
        rule,
        {"pbt": pbt, "associates": associates},
        dash_rules=policy,
        qualification=QualificationContext(
            schema_identity=rule.schema_identity,
            surface=rule.surface,
            basis=Basis.CONSOLIDATED,
            period_kind=PeriodKind.QUARTER,
            proven={},
        ),
        recorded_at=NOW,
    )

    assert result.status is InterpretationStatus.MAPPED
    assert result.value == Decimal("3405300000.00")
    assert result.interval == Interval(lower=Fraction(3_405_200_000), upper=Fraction(3_405_400_000))
    assert result.tier is EvidenceTier.EQUIVALENCE_UNPROVEN
    assert result.operand_interpretation_ids == (1, 2)
    assert result.input_digest == "a369938f084991d464dd73717cac068ac7b1c9164adc9605e8f9ba70c781ba17"
    assert result.transform_trace == {
        "rule_id": LEGACY_RULE_ID,
        "operands": {
            "pbt": {"interpretation_id": 1, "status": "MAPPED", "missing_state": None},
            "associates": {
                "interpretation_id": 2,
                "status": "MAPPED",
                "missing_state": None,
            },
        },
    }
    assert result.key is not None
    assert result.key.entity_id == 1
    assert result.key.canonical_id == "profit_before_tax_incl_associates"
    assert result.key.basis is Basis.CONSOLIDATED
    assert result.key.framework is AccountingFramework.IND_AS


def test_native_operands_construct_only_the_evidenced_aggregate(
    tmp_path: Path,
    dictionary: CanonicalDictionary,
    policy: NormalisationPolicy,
) -> None:
    """Two UNMAPPED native rows yield one exact linked aggregate, never pretend operands."""
    mappings = _native_mapping(tmp_path / "mappings", dictionary)
    rows = interpret_generation(
        [
            _occurrence(1, "Borrowings", "10.25"),
            _occurrence(2, "Other Liabilities", "2.50"),
        ],
        scope=CaptureScope(
            capture=CAPTURE,
            entity_id=7,
            basis=Basis.CONSOLIDATED,
            framework=AccountingFramework.IND_AS,
            mapping_set=mappings,
            policy=policy,
            dictionary=dictionary,
            fiscal_year_end_month=3,
            expected_extractor_pin=VendorExtractorPin(
                source_id=SOURCE,
                surface=SURFACE,
                version="screener-extractor-v2",
                content_sha256="3" * 64,
            ),
        ),
        prior=(),
        prior_anchor_keys={},
        reserve_ids=_reserve(),  # type: ignore[arg-type]
        recorded_at=NOW,
    )

    direct = rows[:2]
    assert [item.status for item in direct] == [
        InterpretationStatus.UNMAPPED,
        InterpretationStatus.UNMAPPED,
    ]
    assert all(
        item.canonical_id is None and item.key is None and item.value is None for item in direct
    )
    (constructed,) = rows[2:]
    assert constructed.status is InterpretationStatus.MAPPED
    assert constructed.canonical_id == "liabilities_incl_nci"
    assert constructed.value == Decimal("127500000")
    assert constructed.interval == Interval(
        lower=Fraction(127_400_000), upper=Fraction(127_600_000)
    )
    assert constructed.operand_interpretation_ids == (100, 101)
    assert constructed.key is not None
    assert constructed.key.period == PeriodInterval.at(date(2026, 3, 31))
    assert constructed.key.currency == "INR"
    assert constructed.tier is EvidenceTier.EQUIVALENCE_UNPROVEN
