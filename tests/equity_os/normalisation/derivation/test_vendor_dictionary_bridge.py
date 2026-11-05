"""D1b dictionary v2 first-party Other Income bridge proof."""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

from canon_formula_support import evaluate_inr, key, leaf, load_v1_policy

from equity_os.contracts.measurement.canonical import StatementFamily
from equity_os.contracts.measurement.evidence_tier import EvidenceTier
from equity_os.contracts.measurement.measurement_key import PeriodInterval
from equity_os.contracts.verification.comparison import CalculationState, SourceState
from equity_os.normalisation.derivation.interval import Interval
from equity_os.normalisation.dictionary.dictionary import load_dictionary

ROOT = Path(__file__).resolve().parents[4]
DICTIONARY_ROOT = ROOT / "config/normalisation/dictionary"
SOURCE_XML = ROOT / "data/raw/watchlist/sonacoms/nse/INDAS_117581_1359784_23012025083325.xml"
SCREENER_HTML = (
    ROOT / "data/raw/watchlist/screener-financials/SONACOMS/consolidated/"
    "screener_financials_page.raw.html"
)
SOURCE_XML_SHA256 = "c2e5b2bde74f631b47ff203a721e1a995bc135692e6b6c23d64bc1a0a75831fc"
SCREENER_HTML_SHA256 = "44347bbbd29a191760059564cd21bed2a7ce53f9091762d5b86125178b68b0a2"
BRIDGE_ID = "other_income_incl_exceptional"
PERIOD = PeriodInterval.duration(date(2024, 10, 1), date(2024, 12, 31))
V1_FILE_SHA256 = {
    "applicability.yaml": "e769a2ec049d1fa503641da9fbba0d6618baec333907e61b9d3536ca04061ae1",
    "balance_sheet.yaml": "f30dfa8c9ac84eefe22f15109e467e2cf89ae9c4081b9e75e8ad960995708b76",
    "cash_flow.yaml": "312b1a5d76a43945b39290059ef38c1c4f089990be88452fdefc48b5af21f347",
    "derived.yaml": "d557fd1329d8ab7aefaae17b331f29d04494dbeece91f71f928c0f5fcaab76b8",
    "metadata.yaml": "2543e236fa0a50e5d4e6a3ea757b5337960aa997343461152e4e7d7cb2943669",
    "pl.yaml": "132a595f867570c939a442e7093409f216951a8a13b68319fbf0d875e96516ff",
    "segment.yaml": "28368da5ac8cbcc00e365adc5e864b13c5070406564b7eee7e1fa2a3d7665ba0",
    "shareholding.yaml": "96f6b0741b556c371d9da2851ffbf12230f6312797ce634288e9abcf98e8c711",
    "templates.yaml": "182fe5b367284c79065a0b363ead46030e88abee1f4461a00002e3df1d91b205",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_oracle() -> tuple[Decimal, Decimal]:
    """Read the signed OneD literals and period/basis directly from retained XML."""
    root = ET.parse(SOURCE_XML).getroot()
    contexts = {
        node.attrib["id"]: node for node in root if node.tag.rsplit("}", 1)[-1] == "context"
    }
    one_d = contexts["OneD"]
    dates = {
        node.tag.rsplit("}", 1)[-1]: node.text
        for node in one_d.iter()
        if node.tag.rsplit("}", 1)[-1] in {"startDate", "endDate"}
    }
    facts = {
        node.tag.rsplit("}", 1)[-1]: Decimal(str(node.text))
        for node in root
        if node.attrib.get("contextRef") == "OneD"
        and node.tag.rsplit("}", 1)[-1] in {"OtherIncome", "ExceptionalItemsBeforeTax"}
    }
    basis = next(
        node.text
        for node in root
        if node.attrib.get("contextRef") == "OneD"
        and node.tag.rsplit("}", 1)[-1] == "NatureOfReportStandaloneConsolidated"
    )
    assert dates == {"startDate": "2024-10-01", "endDate": "2024-12-31"}
    assert basis == "Consolidated"
    return facts["OtherIncome"], facts["ExceptionalItemsBeforeTax"]


def test_v2_is_v1_plus_one_derived_bridge_and_v1_bytes_are_unchanged() -> None:
    v1 = load_dictionary(DICTIONARY_ROOT, "v1")
    v2 = load_dictionary(DICTIONARY_ROOT, "v2")

    assert {name: _sha256(DICTIONARY_ROOT / "v1" / name) for name in V1_FILE_SHA256} == (
        V1_FILE_SHA256
    )
    assert v1.version == "v1" and v1.formula_set_version == "v1"
    assert v2.version == "v2" and v2.formula_set_version == "v2"
    assert sum(v1.family_counts().values()) == 259
    assert sum(v2.family_counts().values()) == 260
    assert v2.templates == v1.templates
    assert [row.model_dump() for row in v2.rows if row.canonical_id != BRIDGE_ID] == [
        row.model_dump() for row in v1.rows
    ]

    bridge = v2.row(BRIDGE_ID)
    assert bridge.family is StatementFamily.DERIVED
    assert bridge.formula is not None
    assert bridge.formula.tier is EvidenceTier.EQUIVALENCE_UNPROVEN
    assert bridge.formula.qualification is None
    assert [(item.name, item.canonical_id) for item in bridge.formula.operands] == [
        ("other_income", "other_income"),
        ("exceptional_items", "exceptional_items_before_tax"),
    ]


def test_retained_signed_xml_bridge_matches_screener_interval_not_plain_other_income() -> None:
    assert _sha256(SOURCE_XML) == SOURCE_XML_SHA256
    assert _sha256(SCREENER_HTML) == SCREENER_HTML_SHA256
    other_income, exceptional_items = _source_oracle()
    assert (other_income, exceptional_items) == (Decimal("467906000.00"), Decimal("-56992000.00"))

    dictionary = load_dictionary(DICTIONARY_ROOT, "v2")
    result = evaluate_inr(
        dictionary,
        load_v1_policy(),
        BRIDGE_ID,
        key(BRIDGE_ID, PERIOD),
        {
            "other_income": leaf(key("other_income", PERIOD), str(other_income), decimals=-6),
            "exceptional_items": leaf(
                key("exceptional_items_before_tax", PERIOD), str(exceptional_items), decimals=-6
            ),
        },
    )
    assert result.state is CalculationState.COMPUTED
    assert result.exact == Fraction(410_914_000)
    assert result.interval == Interval(lower=Fraction(409_914_000), upper=Fraction(411_914_000))
    screener_interval = Interval.from_precision(Decimal("410000000"), -7)
    assert screener_interval.contains(result.exact)
    assert result.interval is not None and screener_interval.intersects(result.interval)
    assert not screener_interval.contains(Fraction(other_income))


def test_bridge_formula_fails_closed_for_missing_and_invalid_operands() -> None:
    dictionary = load_dictionary(DICTIONARY_ROOT, "v2")
    policy = load_v1_policy()
    output = key(BRIDGE_ID, PERIOD)
    missing = evaluate_inr(
        dictionary,
        policy,
        BRIDGE_ID,
        output,
        {
            "other_income": leaf(key("other_income", PERIOD), None, state=SourceState.NO_VALUE),
            "exceptional_items": leaf(
                key("exceptional_items_before_tax", PERIOD), "-56992000", decimals=-6
            ),
        },
    )
    invalid = evaluate_inr(
        dictionary,
        policy,
        BRIDGE_ID,
        output,
        {
            "other_income": leaf(key("other_income", PERIOD), None, state=SourceState.NO_VALUE),
            "exceptional_items": leaf(
                key("exceptional_items_before_tax", PERIOD),
                None,
                state=SourceState.INVALID,
                reasons=("source-invalid",),
            ),
        },
    )
    assert missing.state is CalculationState.OPERAND_MISSING
    assert invalid.state is CalculationState.OPERAND_INVALID
    assert missing.exact is None and missing.interval is None
    assert invalid.exact is None and invalid.interval is None
