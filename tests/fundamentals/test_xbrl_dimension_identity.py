"""Dimension prefixes are aliases, and foreign semantics cannot become canonical segments."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from evidence_support import dictionary, mapping_set, policy
from lxml import etree
from retained_support import apar_original
from selection_support import at, member

from fundamentals.canon.dictionary import CanonicalDictionary
from fundamentals.contracts.canonical import Basis, PeriodKind, Representation
from fundamentals.contracts.evidence import InterpretationStatus
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.qualification import QualificationContext
from fundamentals.evidence.interpret import interpret
from fundamentals.evidence.mapping import MappingSet, NormalisationPolicy
from fundamentals.evidence.member_identity import (
    IssuerIdentifiers,
    verify_xbrl_framework,
    verify_xbrl_identity,
)
from fundamentals.evidence.xbrl_adapter import occurrences_from_instance, parse_instance
from fundamentals.extract.xbrl_parser import XbrlParseError

__all__ = ["dictionary", "mapping_set", "policy"]
pytestmark = pytest.mark.retained
XBRLDI = "http://xbrl.org/2006/xbrldi"
FOREIGN = "urn:foreign-dimensional-semantics"


@pytest.mark.parametrize("variant", ["foreign_axis", "foreign_member", "genuine_alias"])
def test_dimension_namespace_controls_canonical_mapping(
    dictionary: CanonicalDictionary,
    mapping_set: MappingSet,
    policy: NormalisationPolicy,
    variant: str,
) -> None:
    original = apar_original("FY26_Q2", "xbrl-consolidated").read_bytes()
    genuine = parse_instance(original, mapping_set=mapping_set)
    root = etree.fromstring(original)
    if variant == "genuine_alias":
        aliased = etree.Element(root.tag, nsmap={**root.nsmap, "alias": genuine.schema_identity})
        aliased.attrib.update(root.attrib)
        aliased.extend(root)
        root = aliased
    for node in root.findall(f".//{{{XBRLDI}}}explicitMember"):
        if not node.get("dimension", "").endswith(":ReportableSegmentsAxis"):
            continue
        namespace = genuine.schema_identity if variant == "genuine_alias" else FOREIGN
        changed = etree.Element(node.tag, nsmap={"alias": namespace})
        changed.attrib.update(node.attrib)
        changed.text = node.text
        if variant == "foreign_member":
            changed.text = "alias:" + (node.text or "").rsplit(":", 1)[-1]
        else:
            changed.set("dimension", "alias:ReportableSegmentsAxis")
        node.getparent().replace(node, changed)
    instance = parse_instance(etree.tostring(root), mapping_set=mapping_set)
    identifiers = IssuerIdentifiers(
        entity_id=1,
        isin="INE372A01015",
        nse_symbol="APARINDS",
        bse_scrip="532259",
        evidence_input_id=1,
    )
    assert verify_xbrl_identity(instance, identifiers, basis=Basis.CONSOLIDATED).verified
    assert verify_xbrl_framework(instance, AccountingFramework.IND_AS).verified
    owner = member(Representation.XBRL, 1, at(29), at(30))
    read = occurrences_from_instance(
        instance, capture=owner.capture, member=owner, mapping_set=mapping_set
    )
    filed = next(
        item
        for item in read
        if item.native_context["context_ref"] == "OneReportable1D"
        and item.native_context["local_name"] == "SegmentRevenue"
    )
    row = interpret(
        filed.model_copy(update={"occurrence_id": 1}),
        entity_id=1,
        basis=Basis.CONSOLIDATED,
        framework=AccountingFramework.IND_AS,
        mapping_set=mapping_set,
        policy=policy,
        dictionary=dictionary,
        fiscal_year_end_month=3,
        qualification=QualificationContext(
            schema_identity=instance.schema_identity,
            surface="NSE_XBRL_INSTANCE",
            basis=Basis.CONSOLIDATED,
            period_kind=PeriodKind.QUARTER,
            proven={},
        ),
        recorded_at=datetime.now(UTC),
    )
    if variant.startswith("foreign"):
        assert row.status is InterpretationStatus.UNMAPPED
        assert row.key is None and row.value is None and row.dimensions is None
        assert any(
            FOREIGN in name for pair in filed.native_context["dimension_qnames"] for name in pair
        )
        assert filed.native_context["dimensions"]
        forced = interpret(
            filed.model_copy(update={"occurrence_id": 1}),
            entity_id=1,
            basis=Basis.CONSOLIDATED,
            framework=AccountingFramework.IND_AS,
            mapping_set=mapping_set,
            policy=policy,
            dictionary=dictionary,
            fiscal_year_end_month=3,
            qualification=QualificationContext(
                schema_identity=instance.schema_identity,
                surface="NSE_XBRL_INSTANCE",
                basis=Basis.CONSOLIDATED,
                period_kind=PeriodKind.QUARTER,
                proven={},
            ),
            recorded_at=datetime.now(UTC),
            as_entry=mapping_set.entry("capmkt.segment_revenue"),
        )
        assert forced.status is InterpretationStatus.UNMAPPED and forced.value is None
    else:
        assert row.status is InterpretationStatus.MAPPED
        assert row.value == Decimal("31001900000")
        assert row.key is not None and dict(row.key.dimensions.pairs) == {
            "elimination_basis": "PRE_ELIMINATION",
            "segment": "conductors",
        }
    # A dimensional fact cannot become an undimensioned total by losing local identity.
    total = filed.model_copy(
        update={
            "native_field": "in-capmkt:RevenueFromOperations",
            "native_context": {**filed.native_context, "local_name": "RevenueFromOperations"},
        }
    )
    assert mapping_set.match(total) is None


def test_missing_dimension_axis_is_not_silently_undimensioned(mapping_set: MappingSet) -> None:
    root = etree.fromstring(apar_original("FY26_Q2", "xbrl-consolidated").read_bytes())
    node = root.find(f".//{{{XBRLDI}}}explicitMember")
    assert node is not None
    del node.attrib["dimension"]
    with pytest.raises(XbrlParseError, match="no axis"):
        parse_instance(etree.tostring(root), mapping_set=mapping_set)
