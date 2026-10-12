"""Verify a package member's document identity against the seeded issuer (data spec l.384).

Bounded to the issuer already seeded for the package: no discovery, no temporal identity.
A member whose identity is not evidenced as the seeded issuer's is ``IDENTITY_REJECTED``
and nothing from it is written. The same holds for the request's accounting framework and
period end: each is read from the capture's own declaration and must equal the request
(a requested framework or period is verified, never trusted).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date

from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.canonical import Basis
from fundamentals.contracts.evidence import Occurrence
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.extract.pdf_header_text import normalize_text_tokens
from fundamentals.extract.xbrl_parser import RawXbrlInstance
from fundamentals.ingest.pdf_source import LoadedPdf
from fundamentals.ingest.xbrl_identity import (
    BSE_SCRIP_ENTITY_SCHEME,
    NSE_ENTITY_SCHEME,
    SEBI_SCRIP_ENTITY_SCHEME,
)

PDF_SYMBOL_MARKER = "Scrip Symbol :"
PDF_IDENTITY_PAGE = 1
ISIN_CONCEPT = "ISIN"
SCRIP_CODE_CONCEPT = "ScripCode"
SYMBOL_CONCEPT = "Symbol"
TEXT_BLOCK_SUFFIX = "TextBlock"
# Framework declarations, each evidenced on the retained Apar captures: the XBRL notes text
# block DisclosureOfNotesOnFinancialResultsExplanatoryTextBlock@OneD (Q2 FY26 sha256 90baae0b,
# Q3 FY26, FY25 Q2 sha256 c44ac376) and the results PDF page 5 note 1 (sha256 8be1b8de):
# "... financial statements have been prepared in accordance with Indian Accounting Standard
# notified under Section 133 of the Companies Act, 2013".
FRAMEWORK_DECLARATIONS: Mapping[AccountingFramework, tuple[str, ...]] = {
    AccountingFramework.IND_AS: ("prepared in accordance with Indian Accounting Standard",),
}
_NO_FRAMEWORK = "the capture declares no accounting framework"
_FRAMEWORKS_DISAGREE = "the capture declares several accounting frameworks {found}"
_FRAMEWORK_CONFLICT = "the capture declares {found} at {where}, not the requested {requested}"
_NO_PERIOD_DECLARATION = "the capture declares no reporting period end ({concept})"
_PERIOD_CONFLICT = (
    "the capture declares reporting period end {found}, not the requested {requested}"
)
_NO_PDF_PERIOD = "no PDF column header prints a period"
_PDF_PERIOD_CONFLICT = (
    "the latest PDF column header period ends {found}, not the requested {requested}"
)
_UNKNOWN_SCHEME = "context entity scheme {scheme!r} is not a seeded identifier scheme"
_CONFLICT = "{what} {found!r} differs from the seeded {expected!r}"
_NO_MARKER = "page 1 prints no {marker!r} line"
_BASIS_CONFLICT = "report nature {found!r} is not the package basis {basis}"


class IssuerIdentifiers(BaseModel):
    """The seeded identifiers of one reporting entity."""

    model_config = ConfigDict(frozen=True)

    entity_id: int
    isin: str
    nse_symbol: str
    bse_scrip: str
    evidence_input_id: int


class IdentityVerdict(BaseModel):
    """Whether a member names the seeded issuer, with what was checked."""

    model_config = ConfigDict(frozen=True)

    verified: bool
    reason: str | None
    evidence: tuple[str, ...]


def verify_xbrl_identity(
    instance: RawXbrlInstance, identifiers: IssuerIdentifiers, *, basis: Basis
) -> IdentityVerdict:
    """Every context entity, identity fact and report-nature fact must match the seed."""
    expected_by_scheme: Mapping[str, str] = {
        NSE_ENTITY_SCHEME: identifiers.nse_symbol,
        SEBI_SCRIP_ENTITY_SCHEME: identifiers.bse_scrip,
        BSE_SCRIP_ENTITY_SCHEME: identifiers.bse_scrip,
    }
    expected_by_concept: Mapping[str, str] = {
        ISIN_CONCEPT: identifiers.isin,
        SCRIP_CODE_CONCEPT: identifiers.bse_scrip,
        SYMBOL_CONCEPT: identifiers.nse_symbol,
    }
    spec = instance.taxonomy
    nature_text = spec.consolidated_text if basis is Basis.CONSOLIDATED else spec.standalone_text
    evidence: list[str] = []
    for fact in instance.facts:
        expected_entity = expected_by_scheme.get(fact.entity_scheme)
        if expected_entity is None:
            return _rejected(_UNKNOWN_SCHEME.format(scheme=fact.entity_scheme), evidence)
        if fact.entity_id != expected_entity:
            return _rejected(
                _CONFLICT.format(
                    what=fact.entity_scheme, found=fact.entity_id, expected=expected_entity
                ),
                evidence,
            )
        local = fact.concept_qname.rsplit(":", 1)[-1]
        found = (fact.raw_text or "").strip()
        if local in expected_by_concept and found != expected_by_concept[local]:
            return _rejected(
                _CONFLICT.format(what=local, found=found, expected=expected_by_concept[local]),
                evidence,
            )
        if local == spec.scope_concept and found != nature_text:
            return _rejected(_BASIS_CONFLICT.format(found=found, basis=basis), evidence)
        if local in expected_by_concept or local == spec.scope_concept:
            evidence.append(f"{fact.concept_qname}@{fact.context_ref}={found}")
    schemes = sorted({fact.entity_scheme for fact in instance.facts})
    evidence.extend(f"scheme {scheme}" for scheme in schemes)
    return IdentityVerdict(verified=True, reason=None, evidence=tuple(evidence))


def verify_pdf_identity(pdf: LoadedPdf, identifiers: IssuerIdentifiers) -> IdentityVerdict:
    """Page 1's ``Scrip Symbol :`` line must name the seeded NSE symbol."""
    for line in pdf.page(PDF_IDENTITY_PAGE).text.splitlines():
        if PDF_SYMBOL_MARKER not in line:
            continue
        found = line.split(PDF_SYMBOL_MARKER, 1)[1].strip()
        if found != identifiers.nse_symbol:
            return _rejected(
                _CONFLICT.format(
                    what=PDF_SYMBOL_MARKER, found=found, expected=identifiers.nse_symbol
                ),
                [],
            )
        return IdentityVerdict(
            verified=True, reason=None, evidence=(f"page {PDF_IDENTITY_PAGE}: {line.strip()}",)
        )
    return _rejected(_NO_MARKER.format(marker=PDF_SYMBOL_MARKER), [])


def verify_xbrl_framework(
    instance: RawXbrlInstance, framework: AccountingFramework
) -> IdentityVerdict:
    """The instance's own text blocks must declare exactly the requested framework."""
    found: dict[AccountingFramework, list[str]] = {}
    for fact in instance.facts:
        if fact.is_numeric or not fact.concept_qname.endswith(TEXT_BLOCK_SUFFIX):
            continue
        for declared in _declared_frameworks(fact.raw_text or ""):
            found.setdefault(declared, []).append(f"{fact.concept_qname}@{fact.context_ref}")
    return _framework_verdict(found, framework)


def verify_pdf_framework(pdf: LoadedPdf, framework: AccountingFramework) -> IdentityVerdict:
    """The PDF's own text must declare exactly the requested framework."""
    found: dict[AccountingFramework, list[str]] = {}
    for page in pdf.pages:
        for declared in _declared_frameworks(page.text):
            found.setdefault(declared, []).append(f"page {page.page_number}")
    return _framework_verdict(found, framework)


def verify_xbrl_period(instance: RawXbrlInstance, period_end: date) -> IdentityVerdict:
    """Every declared reporting-period end of the instance must be the requested period end."""
    spec = instance.taxonomy
    concept = spec.reporting_period_end_concept
    declared = [
        fact
        for fact in instance.facts
        if fact.namespace_uri == spec.namespace and fact.concept_qname.endswith(f":{concept}")
    ]
    if not declared:
        return _rejected(_NO_PERIOD_DECLARATION.format(concept=concept), [])
    evidence: list[str] = []
    for fact in declared:
        found = (fact.raw_text or "").strip()
        if found != period_end.isoformat():
            return _rejected(
                _PERIOD_CONFLICT.format(found=found, requested=period_end.isoformat()), evidence
            )
        evidence.append(f"{fact.concept_qname}@{fact.context_ref}={found}")
    return IdentityVerdict(verified=True, reason=None, evidence=tuple(evidence))


def verify_pdf_period(occurrences: Sequence[Occurrence], period_end: date) -> IdentityVerdict:
    """The latest period any PDF column header prints must end at the requested period end."""
    ends = [
        occurrence.valid_time for occurrence in occurrences if occurrence.valid_time is not None
    ]
    if not ends:
        return _rejected(_NO_PDF_PERIOD, [])
    latest = max(ends)
    if latest != period_end:
        return _rejected(
            _PDF_PERIOD_CONFLICT.format(found=latest, requested=period_end.isoformat()), []
        )
    return IdentityVerdict(verified=True, reason=None, evidence=(f"latest header {latest}",))


def _declared_frameworks(text: str) -> set[AccountingFramework]:
    """Every framework whose declaration phrase the text contains as a token run."""
    tokens = normalize_text_tokens(text)
    return {
        framework
        for framework, phrases in FRAMEWORK_DECLARATIONS.items()
        if any(_contains(tokens, normalize_text_tokens(phrase)) for phrase in phrases)
    }


def _framework_verdict(
    found: Mapping[AccountingFramework, list[str]], requested: AccountingFramework
) -> IdentityVerdict:
    """Exactly one declared framework, equal to the requested one."""
    if not found:
        return _rejected(_NO_FRAMEWORK, [])
    if len(found) > 1:
        return _rejected(_FRAMEWORKS_DISAGREE.format(found=sorted(found)), [])
    ((declared, where),) = found.items()
    if declared is not requested:
        return _rejected(
            _FRAMEWORK_CONFLICT.format(found=declared, where=where[0], requested=requested), []
        )
    return IdentityVerdict(
        verified=True,
        reason=None,
        evidence=tuple(f"{declared.value} declared at {location}" for location in where),
    )


def _contains(haystack: Sequence[str], needle: Sequence[str]) -> bool:
    """Whether ``needle`` occurs as a contiguous token run in ``haystack``."""
    width = len(needle)
    return width > 0 and any(
        list(haystack[i : i + width]) == list(needle) for i in range(len(haystack) - width + 1)
    )


def _rejected(reason: str, evidence: list[str]) -> IdentityVerdict:
    """A rejection with what had been checked before it."""
    return IdentityVerdict(verified=False, reason=reason, evidence=tuple(evidence))
