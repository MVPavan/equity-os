"""Only the registered taxonomy can supply the filing's identity declarations."""

from datetime import date

import pytest
from evidence_support import dictionary, mapping_set
from retained_support import apar_original
from vendor_retained_support import RAW_ROOT

from fundamentals.contracts.canonical import Basis
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.evidence.mapping import MappingSet
from fundamentals.evidence.member_identity import (
    IssuerIdentifiers,
    verify_xbrl_framework,
    verify_xbrl_identity,
    verify_xbrl_period,
)
from fundamentals.evidence.xbrl_adapter import parse_instance

__all__ = ["dictionary", "mapping_set"]
pytestmark = pytest.mark.retained
IDENTIFIERS = IssuerIdentifiers(
    entity_id=1, isin="INE372A01015", nse_symbol="APARINDS", bse_scrip="532259", evidence_input_id=1
)
FOREIGN = "https://example.invalid/foreign"


def test_foreign_report_nature_cannot_replace_genuine_context_evidence(
    mapping_set: MappingSet,
) -> None:
    instance = parse_instance(
        apar_original("FY26_Q2", "xbrl-consolidated").read_bytes(), mapping_set=mapping_set
    )
    declarations = [
        fact
        for fact in instance.facts
        if fact.concept_qname.endswith(":NatureOfReportStandaloneConsolidated")
    ]
    assert declarations
    foreign = declarations[0].model_copy(
        update={
            "namespace_uri": FOREIGN,
            "concept_qname": "foreign:NatureOfReportStandaloneConsolidated",
        }
    )
    stripped = instance.model_copy(
        update={
            "facts": tuple(fact for fact in instance.facts if fact not in declarations) + (foreign,)
        }
    )
    verdict = verify_xbrl_identity(stripped, IDENTIFIERS, basis=Basis.CONSOLIDATED)
    assert not verdict.verified
    assert "no context-bound" in (verdict.reason or "")


def test_foreign_identity_lookalike_cannot_override_genuine_identity(
    mapping_set: MappingSet,
) -> None:
    instance = parse_instance(
        apar_original("FY26_Q2", "xbrl-consolidated").read_bytes(), mapping_set=mapping_set
    )
    isin = next(fact for fact in instance.facts if fact.concept_qname.endswith(":ISIN"))
    foreign = isin.model_copy(
        update={
            "namespace_uri": FOREIGN,
            "concept_qname": "foreign:ISIN",
            "raw_text": "INE000000000",
        }
    )
    supplemented = instance.model_copy(update={"facts": (*instance.facts, foreign)})
    verdict = verify_xbrl_identity(supplemented, IDENTIFIERS, basis=Basis.CONSOLIDATED)
    assert verdict.verified
    assert not any("foreign:ISIN" in item for item in verdict.evidence)


def test_foreign_framework_text_cannot_replace_genuine_declaration(mapping_set: MappingSet) -> None:
    instance = parse_instance(
        apar_original("FY26_Q2", "xbrl-consolidated").read_bytes(), mapping_set=mapping_set
    )
    declarations = [
        fact
        for fact in instance.facts
        if "prepared in accordance with Indian Accounting Standard" in (fact.raw_text or "")
    ]
    assert declarations
    foreign = declarations[0].model_copy(
        update={"namespace_uri": FOREIGN, "concept_qname": "foreign:NotesTextBlock"}
    )
    stripped = instance.model_copy(
        update={
            "facts": tuple(fact for fact in instance.facts if fact not in declarations) + (foreign,)
        }
    )
    verdict = verify_xbrl_framework(stripped, AccountingFramework.IND_AS)
    assert not verdict.verified
    assert verdict.reason == "the capture declares no accounting framework"


def test_ind_as_entry_point_declares_the_framework(mapping_set: MappingSet) -> None:
    # POLYCAB Q3 FY25 has no notes sentence naming Ind AS; its schemaRef is the declaration.
    xbrl = RAW_ROOT / "polycab/nse/INDAS_117488_1357164_22012025051528.xml"
    instance = parse_instance(xbrl.read_bytes(), mapping_set=mapping_set)
    verdict = verify_xbrl_framework(instance, AccountingFramework.IND_AS)
    assert verdict.verified
    assert verdict.evidence == ("IND_AS declared at schemaRef Ind-AS_entry_point_2020-03-31.xsd",)


def test_foreign_period_end_cannot_replace_genuine_declaration(mapping_set: MappingSet) -> None:
    instance = parse_instance(
        apar_original("FY26_Q2", "xbrl-consolidated").read_bytes(), mapping_set=mapping_set
    )
    declarations = [
        fact
        for fact in instance.facts
        if fact.concept_qname.endswith(":" + instance.taxonomy.reporting_period_end_concept)
    ]
    assert declarations
    foreign = declarations[0].model_copy(update={"namespace_uri": FOREIGN})
    stripped = instance.model_copy(
        update={
            "facts": tuple(fact for fact in instance.facts if fact not in declarations) + (foreign,)
        }
    )
    verdict = verify_xbrl_period(stripped, date(2025, 9, 30))
    assert not verdict.verified
