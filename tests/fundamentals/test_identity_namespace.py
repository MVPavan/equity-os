"""Only the registered taxonomy can supply the filing's identity declarations."""

import hashlib
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from evidence_support import dictionary, mapping_set
from retained_support import REPO_ROOT, apar_original
from stage4_filings import onboarding_mapping_set
from vendor_retained_support import RAW_ROOT

from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.canonical import Basis, Representation
from fundamentals.contracts.evidence import CaptureReference, KnowledgeTimeStatus, PackageMember
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.evidence.capture_intake import RetainedCaptureBinding
from fundamentals.evidence.first_party_extract import IngestRequest, _read_xbrl
from fundamentals.evidence.mapping import MappingSet
from fundamentals.evidence.member_identity import (
    IssuerIdentifiers,
    integrated_ind_as,
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
DEV = REPO_ROOT / "data" / "raw" / "onboarding-dev"
# One retained instance per IntegratedFinance form; THERMAX's notes carry no Ind AS phrase.
FORMS = {
    "IndAS": "dev-entry-points/THERMAX/nse/INTEGRATED_FILING_INDAS_1705307_30072026053358_WEB.xml",
    "Banking": "bank-HDFCBANK/nse/INTEGRATED_FILING_BANKING_1696123_18072026040126_WEB.xml",
    "NBFC": "nbfc-BAJFINANCE/nse/INTEGRATED_FILING_NBFC_INDAS_1705543_30072026070233_WEB.xml",
    "LI": "insurer-HDFCLIFE/nse/INTEGRATED_FILING_LI_1693455_15072026055112_WEB.xml",
}
IND_AS_ROOT_NAMESPACE = (
    b'xmlns:zz="http://www.sebi.gov.in/xbrl/IntegratedFinance_IndAS/2026-01-31/in-capmkt/'
    b'in-capmkt-ent" '
)
BANKING_ROOT_NAMESPACE = (
    b'xmlns:zb="http://www.sebi.gov.in/xbrl/IntegratedFinance_Banking/2025-01-31/in-capmkt/'
    b'in-capmkt-ent" '
)
UNKNOWN_CHILD_NAMESPACE = (
    b'xmlns:zz="http://www.sebi.gov.in/xbrl/IntegratedFinance_ZZ/2025-01-31/x" '
)


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
    body = apar_original("FY26_Q2", "xbrl-consolidated").read_bytes()
    instance = parse_instance(body, mapping_set=mapping_set)
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
    verdict = verify_xbrl_framework(stripped, AccountingFramework.IND_AS, body=body)
    assert verdict.verified  # only the form declaration remains
    assert verdict.evidence == ("IND_AS declared at IntegratedFinance_IndAS form declaration",)


def test_ind_as_entry_point_declares_the_framework(mapping_set: MappingSet) -> None:
    # POLYCAB Q3 FY25 has no notes sentence naming Ind AS; its schemaRef is the declaration.
    xbrl = RAW_ROOT / "polycab/nse/INDAS_117488_1357164_22012025051528.xml"
    body = xbrl.read_bytes()
    verdict = verify_xbrl_framework(
        parse_instance(body, mapping_set=mapping_set), AccountingFramework.IND_AS, body=body
    )
    assert verdict.verified
    assert verdict.evidence == ("IND_AS declared at schemaRef Ind-AS_entry_point_2020-03-31.xsd",)


@pytest.mark.parametrize("form", FORMS)
def test_only_the_ind_as_form_declares_the_framework(form: str) -> None:
    """The IntegratedFinance_IndAS form namespace is an explicit Ind AS form declaration; the
    Banking, NBFC and LI forms (same xsd name) declare no accounting framework."""
    body = (DEV / FORMS[form]).read_bytes()
    instance = parse_instance(body, mapping_set=onboarding_mapping_set())
    verdict = verify_xbrl_framework(instance, AccountingFramework.IND_AS, body=body)
    assert integrated_ind_as(body) is verdict.verified is (form == "IndAS")
    if verdict.verified:
        assert verdict.evidence == ("IND_AS declared at IntegratedFinance_IndAS form declaration",)
    else:
        assert verdict.reason == _competing(form)


def test_a_competing_form_contests_an_ind_as_namespace() -> None:
    """R1 (MARKED): an unused IndAS root namespace added to a bank filing, its Banking
    namespaces and content kept, does not make it an Ind AS form declaration."""
    body = (DEV / FORMS["Banking"]).read_bytes()
    marked = body.replace(b"<xbrli:xbrl ", b"<xbrli:xbrl " + IND_AS_ROOT_NAMESPACE, 1)
    assert marked != body
    instance = parse_instance(marked, mapping_set=onboarding_mapping_set())
    assert not integrated_ind_as(marked)
    verdict = verify_xbrl_framework(instance, AccountingFramework.IND_AS, body=marked)
    assert verdict.reason == _competing("Banking")
    assert not integrated_ind_as(b"<not xml")


@pytest.mark.parametrize(
    ("form", "edit"),
    [
        ("Banking", (b"<xbrli:xbrl ", b"<xbrli:xbrl " + BANKING_ROOT_NAMESPACE)),
        ("ZZ", (b"<xbrli:context ", b"<xbrli:context " + UNKNOWN_CHILD_NAMESPACE)),
        (None, (b"", b"")),
    ],
)
def test_a_competing_form_vetoes_a_phrase_bearing_ind_as_filing_at_ingest(
    mapping_set: MappingSet, tmp_path: Path, form: str | None, edit: tuple[bytes, bytes]
) -> None:
    """Critical review 2026-10-17 (P1): an unused Banking (root) or unknown (child-local)
    IntegratedFinance form added to Apar's IndAS filing, its IndAS namespace and Ind AS notes
    phrase kept, is refused by actual ingest (``_read_xbrl``) before the phrase can verify it;
    the unmutated filing extracts."""
    body = apar_original("FY26_Q2", "xbrl-consolidated").read_bytes()
    mutated = body.replace(*edit, 1) if form else body
    assert (mutated != body) is (form is not None)
    path = tmp_path / "instance.xml"
    path.write_bytes(mutated)
    sha = hashlib.sha256(mutated).hexdigest()
    at = datetime(2025, 11, 1, tzinfo=UTC)
    binding = RetainedCaptureBinding(
        representation=Representation.XBRL,
        source_id="apar",
        relative_path=Path("instance.xml"),
        expected_sha256=sha,
        filed_at_raw="",
    )
    capture = CaptureReference(
        capture_ref_id=1,
        source_id="apar",
        surface="nse",
        request_key="apar",
        capture_id="apar",
        blob_sha256=sha,
        record_sha256=sha,
        registered_at=at,
        first_seen_at=at,
    )
    member = PackageMember(
        representation=Representation.XBRL,
        capture=capture,
        knowledge_time=at,
        knowledge_time_raw="",
        knowledge_time_status=KnowledgeTimeStatus.KNOWN,
    )
    request = IngestRequest(
        entity_id=1,
        period_end=date(2025, 9, 30),
        basis=Basis.CONSOLIDATED,
        framework=AccountingFramework.IND_AS,
    )
    read = _read_xbrl(path, binding, member, IDENTIFIERS, request, mapping_set)
    if form is None:
        assert read.outcome is ExtractionOutcome.COMPLETE
        assert read.occurrences
    else:
        assert read.outcome is ExtractionOutcome.IDENTITY_REJECTED
        assert read.reason == _competing(form)
        assert not read.occurrences


def _competing(form: str) -> str:
    """The rejection naming one competing IntegratedFinance form."""
    return f"the capture declares the IntegratedFinance form(s) {[form]}, not Ind AS"


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
