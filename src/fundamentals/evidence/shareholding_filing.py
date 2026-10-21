"""SHP XBRL instance to lossless occurrences (plan D8 Task 4, extractor ``nse-shp-v2``).

Extraction only, so the version pin hashes what decides each occurrence. The instance is
read with the results parser's context and unit readers (``extract/xbrl_dimensions.py``
underneath, unedited). Before anything is kept: every fact is in the one supported
taxonomy (else ``UNSUPPORTED_SCHEMA``), the filed shareholding date
(``DateOfReport`` and its context instant) equals the listing row's date (else
``PARSE_FAILED``, R4), and every parsed context's entity (used by a fact or not) and every
ISIN, symbol and scrip fact names the issuer held at the instant (else ``IDENTITY_REJECTED``).
Every fact is then one occurrence; a ``pure`` percentage fraction carries raw scale 2 with
its lexeme, unit and ``decimals`` kept (R5), and its declared ``INF`` precision is
unsupported (R5 Precision). Each occurrence
records the validated filing ISIN and its list's completeness (R4 Completeness).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime
from typing import Any

from lxml import etree  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.canonical import Representation
from fundamentals.contracts.evidence import (
    CaptureReference,
    KnowledgeTimeStatus,
    Occurrence,
    PrecisionKind,
    RevisionCause,
)
from fundamentals.evidence.mapping import (
    CONTEXT_BASIS,
    CONTEXT_DIMENSION_AXES,
    CONTEXT_LOCAL_NAME,
    CONTEXT_NAMESPACE,
    CONTEXT_SCHEMA_IDENTITY,
)
from fundamentals.evidence.member_identity import (
    ISIN_CONCEPT,
    SCRIP_CODE_CONCEPT,
    SYMBOL_CONCEPT,
    IssuerIdentifiers,
)
from fundamentals.evidence.xbrl_adapter import _missing_state, _precision, anchor_key_of
from fundamentals.extract.xbrl_parser import (
    _NIL_TRUE,
    _XSI_NIL,
    PURE_MEASURE,
    RawXbrlFact,
    XbrlParseError,
    _parse_contexts,
    _parse_units,
    _period_interval,
    _raw_periods,
    _XbrlContext,
)
from fundamentals.ingest.xbrl_identity import (
    ACCEPTED_ENTITY_IDS_BY_ISIN,
    BSE_SCRIP_ENTITY_SCHEME,
    NSE_ENTITY_SCHEME,
    SEBI_SCRIP_ENTITY_SCHEME,
)

SHP_EXTRACTOR_VERSION = "nse-shp-v2"  # v2: the identity gate covers every context (D8 F8)
SHP_EXTRACTOR_VERSIONS = frozenset({"nse-shp-v1", SHP_EXTRACTOR_VERSION})
# d8-probe.md §3: the BSE SHP taxonomy every retained instance files under, and its scrip scheme.
SHP_NAMESPACE = "http://www.bseindia.com/xbrl/shp/2025-10-31/in-bse-shp"
SHP_FORMAT_VERSION = "in-bse-shp/2025-10-31"
SHP_SCRIP_ENTITY_SCHEME = "http://www.bseindia.com/in-bse-shp/ScripCode"
STANDALONE = "STANDALONE"  # R4: a SHAREHOLDING package is stored STANDALONE
CONTEXT_SECURITY_ISIN = "security_isin"
# §3: the shareholding date, context MainI (the category rows' instant; other instants are
# earlier quarters' foreign-ownership limits).
DATE_OF_REPORT_CONCEPT = "DateOfReport"
PERCENT_SCALE = 2  # R5: a pure fraction is x100 a percentage, exactly once
COMPLETE, THRESHOLDED, UNKNOWN = "COMPLETE", "THRESHOLDED", "UNKNOWN"
TOTAL_SHARES = "TOTAL_SHARES"
_TYPED = "typed:"
CATEGORY_AXIS_NATIVE = "CategoryOfShareholdersAxis"
SHP_TOTAL = "ShareholdingPatternMember"
# Each ``<Name>Member`` the retained instances file on the native axis, under its format parent by
# label correspondence (R/reference/gen-1/02.bin pp. 3-13; d8-probe.md §11.2), mapped or not.
_FORMAT_CHILDREN = {
    "ShareholdingPattern": "ShareholdingOfPromoterAndPromoterGroup PublicShareholding "
    "SharesHeldByNonPromoterNonPublicShareholders",
    "ShareholdingOfPromoterAndPromoterGroup": "Indian Foreign",
    "Indian": "IndividualsOrHinduUndividedFamily CentralGovernmentOrStateGovernmentS "
    "OtherIndianShareholders",
    "Foreign": "OtherForeignShareholders",
    "PublicShareholding": "InstitutionsDomestic InstitutionsForeign Governments NonInstitutions",
    "InstitutionsDomestic": "MutualFundsOrUTI AlternativeInvestmentFunds Banks InsuranceCompanies "
    "ProvidentFundsOrPensionFunds SovereignWealthFundsDomestic NBFCsRegisteredWithRBI "
    "OtherFinancialInstitutions",
    "InstitutionsForeign": "ForeignDirectInvestment "
    "InstitutionsForeignPortfolioInvestorCategoryOne "
    "InstitutionsForeignPortfolioInvestorCategoryTwo OtherInstitutionsForeign",
    "Governments": "CentralGovernmentOrPresidentOfIndia",
    "NonInstitutions": "DirectorsAndDirectorsRelatives KeyManagerialPersonnel "
    "InvestorEducationAndProtectionFund NonResidentIndians ForeignNationals ForeignCompanies "
    "ResidentIndividualShareholdersHoldingNominalShareCapitalUpToRsTwoLakh BodiesCorporate "
    "ResidentIndividualShareholdersHoldingNominalShareCapitalInExcessOfRsTwoLakh "
    "OtherNonInstitutions",
    "SharesHeldByNonPromoterNonPublicShareholders": "EmployeeBenefitsTrusts",
}
FORMAT_PARENT = {
    f"{child}Member": f"{parent}Member"
    for parent, children in _FORMAT_CHILDREN.items()
    for child in children.split()
}
# d8-probe.md §11.3: SEBI format notes (02.bin p. 11 Table III note 2; p. 13 Table IV note 2)
# "names of the shareholders holding 1% or more than 1% of shares of the listed entity".
_FORMAT_THRESHOLD = (
    "SEBI format note: holders of 1% or more of shares are named (inclusive; "
    "R/reference/gen-1/02.bin p. 11 Table III note 2, p. 13 Table IV note 2; d8-probe.md §11.3)"
)
_THRESHOLDED_LISTS = frozenset(
    f"DetailsOfSharesHeldBy{name}Axis"
    for name in (
        "MutualFundsOrUTI",
        "InsuranceCompanies",
        "ProvidentFundsOrPensionFunds",
        "InstitutionsForeignPortfolioInvestorOne",
        "ForeignDirectInvestment",
        "BodiesCorporate",
        "DirectorsAndDirectorsRelatives",
        "ResidentIndividualShareholdersHoldingNominalShareCapitalInExcessOfRsTwoLakh",
        "EmployeeBenefitsTrusts",
    )
)
_PROMOTER_REASON = (
    "promoter-group list: Reg. 31(4) requires disclosure but NIL holders are routed to a "
    "separate link and the consolidated LODR text is not retained (d8-probe.md §11.3; R4)"
)
_UNKNOWN_REASONS: Mapping[str, str] = {
    "DetailsSharesHeldByIndividualsOrHUFAxis": _PROMOTER_REASON,
    "DetailsOfSharesHeldByOthersIndianShareholdersAxis": _PROMOTER_REASON,
    "DetailsOfSharesHeldByOtherForeignShareholdersAxis": _PROMOTER_REASON,
    "DetailsOfSharesHeldByCentralGovernmentOrStateGovernmentsAxis": _PROMOTER_REASON,
    "DetailsOfTheShareholdersActingAsPersonsInConcertForPublicAxis": (
        "PAC list: the format prescribes it but states neither a threshold nor completeness "
        "(R/reference/gen-1/02.bin p. 11; d8-probe.md §11.3)"
    ),
}
_UNEVIDENCED = (
    "no retained evidence states this list's threshold or completeness (d8-probe.md §11.3)"
)
_FOREIGN_NAMESPACE = "facts outside {expected}: {found}"
_INSTANT_CONFLICT = (
    "DateOfReport (value, context instant) {found} is not the listing date {listing}"
)
_IDENTITY_CONFLICT = "{what} {found!r} is not the issuer's {expected}"


class ShareholdingListing(BaseModel):
    """The listing row a submission is filed under: its date and broadcast (knowledge) time."""

    model_config = ConfigDict(frozen=True)

    instant: date | None
    knowledge_time: datetime
    knowledge_time_raw: str


class ShareholdingExtraction(BaseModel):
    """One adapter invocation: its outcome, the refusal reason and the occurrences."""

    model_config = ConfigDict(frozen=True)

    outcome: ExtractionOutcome
    reason: str | None = None
    occurrences: tuple[Occurrence, ...] = ()


def extract_shareholding(
    body: bytes,
    *,
    capture: CaptureReference,
    identifiers: IssuerIdentifiers,
    listing: ShareholdingListing,
) -> ShareholdingExtraction:
    """Every fact of one SHP instance as an occurrence, or the refusal (see module docstring)."""
    try:
        root = etree.fromstring(body)
        contexts = _parse_contexts(root)
        facts = _facts(root, contexts)
    except (etree.XMLSyntaxError, XbrlParseError, ValueError) as error:
        return ShareholdingExtraction(outcome=ExtractionOutcome.PARSE_FAILED, reason=str(error))
    namespaces = {fact.namespace_uri for fact in facts}
    if namespaces != {SHP_NAMESPACE}:
        reason = _FOREIGN_NAMESPACE.format(
            expected=SHP_NAMESPACE, found=sorted(map(str, namespaces))
        )
        return ShareholdingExtraction(outcome=ExtractionOutcome.UNSUPPORTED_SCHEMA, reason=reason)
    instants = {
        ((fact.raw_text or "").strip(), str(fact.period.instant))
        for fact in facts
        if _local(fact) == DATE_OF_REPORT_CONCEPT
    }
    if instants != {(str(listing.instant), str(listing.instant))}:
        reason = _INSTANT_CONFLICT.format(found=sorted(map(str, instants)), listing=listing.instant)
        return ShareholdingExtraction(outcome=ExtractionOutcome.PARSE_FAILED, reason=reason)
    refusal = _identity_refusal(contexts.values(), facts, identifiers)
    if refusal is not None:
        return ShareholdingExtraction(outcome=ExtractionOutcome.IDENTITY_REJECTED, reason=refusal)
    isins = {(fact.raw_text or "").strip() for fact in facts if _local(fact) == ISIN_CONCEPT}
    isin = next(iter(isins)) if len(isins) == 1 else None
    return ShareholdingExtraction(
        outcome=ExtractionOutcome.COMPLETE,
        occurrences=tuple(_occurrence(fact, capture, listing, isin) for fact in facts),
    )


def _facts(root: Any, contexts: Mapping[str, _XbrlContext]) -> tuple[RawXbrlFact, ...]:
    """Every context-bound fact as filed (a fact on an unknown context is a parse failure)."""
    units, raw_periods = _parse_units(root), _raw_periods(root)
    facts = []
    for order, element in enumerate(root.iter()):
        context_ref = element.get("contextRef") if isinstance(element.tag, str) else None
        if context_ref is None:
            continue
        context = contexts.get(context_ref)
        if context is None:
            raise XbrlParseError(f"fact {element.tag} references unknown context {context_ref!r}")
        qname = etree.QName(element)
        is_nil = (element.get(_XSI_NIL) or "").strip().lower() in _NIL_TRUE
        unit_ref = element.get("unitRef")
        facts.append(
            RawXbrlFact(
                fact_id=element.get("id"),
                concept_qname=f"{element.prefix or qname.namespace}:{qname.localname}",
                namespace_uri=qname.namespace,
                context_ref=context_ref,
                raw_text=None if is_nil else (element.text or ""),
                is_nil=is_nil,
                is_numeric=unit_ref is not None,
                decimals_raw=element.get("decimals"),
                unit_measure=None if unit_ref is None else units.get(unit_ref),
                entity_scheme=context.entity_scheme,
                entity_id=context.entity_id,
                raw_period=raw_periods[context_ref],
                period=_period_interval(context),
                period_declaration=None,
                dimensions=context.dimensions,
                dimension_qnames=context.dimension_qnames,
                document_order=order,
            )
        )
    return tuple(facts)


def _identity_refusal(
    contexts: Iterable[_XbrlContext], facts: tuple[RawXbrlFact, ...], identifiers: IssuerIdentifiers
) -> str | None:
    """The first context entity or identity fact that names another issuer (R4 identity gate)."""
    symbols = {identifiers.nse_symbol, *ACCEPTED_ENTITY_IDS_BY_ISIN.get(identifiers.isin, ())}
    scrip = {identifiers.bse_scrip}
    by_scheme = {
        NSE_ENTITY_SCHEME: symbols,
        SEBI_SCRIP_ENTITY_SCHEME: scrip,
        BSE_SCRIP_ENTITY_SCHEME: scrip,
        SHP_SCRIP_ENTITY_SCHEME: scrip,
    }
    by_concept = {
        ISIN_CONCEPT: {identifiers.isin},
        SCRIP_CODE_CONCEPT: scrip,
        SYMBOL_CONCEPT: symbols,
    }
    for context in contexts:
        if context.entity_id not in by_scheme.get(context.entity_scheme, set()):
            what = f"context entity ({context.entity_scheme})"
            return _IDENTITY_CONFLICT.format(what=what, found=context.entity_id, expected=scrip)
    for fact in facts:
        expected = by_concept.get(_local(fact))
        found = (fact.raw_text or "").strip()
        if expected is not None and found not in expected:
            return _IDENTITY_CONFLICT.format(what=_local(fact), found=found, expected=expected)
    return None


def _occurrence(
    fact: RawXbrlFact, capture: CaptureReference, listing: ShareholdingListing, isin: str | None
) -> Occurrence:
    """One fact as an occurrence with its list's completeness and the validated ISIN."""
    pure = fact.unit_measure == PURE_MEASURE
    precision, declared = (PrecisionKind.UNSUPPORTED, None) if pure else _precision(fact)
    text = fact.raw_text
    return Occurrence(
        occurrence_id=None,
        capture=capture,
        representation=Representation.XBRL,
        extractor_version=SHP_EXTRACTOR_VERSION,
        native_field=fact.concept_qname,
        raw_value_text=text,
        raw_unit=fact.unit_measure or "",
        raw_scale=PERCENT_SCALE if pure else 0,
        raw_sign=-1 if text is not None and text.strip().startswith("-") else 1,
        precision_kind=precision,
        declared_precision=declared,
        native_context={
            CONTEXT_SCHEMA_IDENTITY: SHP_NAMESPACE,
            CONTEXT_BASIS: STANDALONE,
            CONTEXT_LOCAL_NAME: _local(fact),
            CONTEXT_NAMESPACE: fact.namespace_uri,
            CONTEXT_DIMENSION_AXES: [axis for axis, _ in fact.dimension_qnames],
            "concept_qname": fact.concept_qname,
            "context_ref": fact.context_ref,
            "dimensions": [list(pair) for pair in fact.dimensions],
            "dimension_qnames": [list(pair) for pair in fact.dimension_qnames],
            "entity": {"scheme": fact.entity_scheme, "identifier": fact.entity_id},
            "raw_period": fact.raw_period.model_dump(mode="json"),
            "decimals": fact.decimals_raw,
            "is_nil": fact.is_nil,
            CONTEXT_SECURITY_ISIN: isin,
        },
        period=fact.period,
        missing_state=_missing_state(fact),
        disclosure=_completeness(fact),
        anchor={
            "fact_id": fact.fact_id,
            "context_ref": fact.context_ref,
            "document_order": fact.document_order,
        },
        anchor_key=anchor_key_of(fact),
        knowledge_time=listing.knowledge_time,
        knowledge_time_status=KnowledgeTimeStatus.KNOWN,
        first_seen_at=capture.first_seen_at,
        revision_cause=RevisionCause.ORIGINAL,
    )


def _completeness(fact: RawXbrlFact) -> dict[str, object]:
    """R4 Completeness: a category fact is complete; a list is thresholded only on evidence."""
    lists = [axis.rsplit(":", 1)[-1] for axis, value in fact.dimensions if value.startswith(_TYPED)]
    disclosure: dict[str, object] = {
        "format_version": SHP_FORMAT_VERSION,
        "completeness": COMPLETE,
        "threshold_pct": None,
        "threshold_denominator": None,
        "completeness_reason": None,
    }
    if not lists:
        return disclosure
    if all(axis in _THRESHOLDED_LISTS for axis in lists):
        return {
            **disclosure,
            "completeness": THRESHOLDED,
            "threshold_pct": 1,
            "threshold_denominator": TOTAL_SHARES,
            "completeness_reason": _FORMAT_THRESHOLD,
        }
    reason = "; ".join(_UNKNOWN_REASONS.get(axis, _UNEVIDENCED) for axis in lists)
    return {**disclosure, "completeness": UNKNOWN, "completeness_reason": reason}


def _local(fact: RawXbrlFact) -> str:
    """The fact's local element name."""
    return fact.concept_qname.rsplit(":", 1)[-1]
