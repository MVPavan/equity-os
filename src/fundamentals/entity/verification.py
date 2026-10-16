"""Pure verification predicates of onboarding discovery (plan D6 D4.3).

Each predicate reads evidence bytes already fetched and returns a :data:`Verdict`. A
contradiction is ``CONFLICT`` (with its detail); missing or unproven evidence is never a
positive. Expected identity per filing is supplied by the caller (D4.3 C8).
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime

from lxml import etree  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.acquisition_outcome import OutcomeCode
from fundamentals.contracts.observation import Scope
from fundamentals.contracts.onboarding import (
    ANCHOR_UNITS,
    OnboardingOutcome,
    OnboardingReason,
    Verdict,
    VerificationState,
    VerificationUnit,
)
from fundamentals.entity.entity_map import isin_check_digit
from fundamentals.evidence.member_identity import verify_xbrl_period
from fundamentals.extract.xbrl_parser import RawXbrlInstance
from fundamentals.ingest.screener_session_models import (
    AnonymousPageError,
    Basis,
    BasisTopology,
    ScreenerSessionError,
)
from fundamentals.ingest.screener_session_page import (
    assert_logged_in,
    parse_document,
    read_identity,
    read_page_evidence,
)
from fundamentals.ingest.tijori_capture import classify_financials_body
from fundamentals.ingest.upstox_source import (
    AcquisitionOutcome,
    UpstoxCapture,
    UpstoxFetch,
    UpstoxSurface,
)
from fundamentals.ingest.upstox_statements import (
    StatementBasis,
    StatementPeriodicity,
    read_income_statement,
)
from fundamentals.ingest.xbrl_identity import (
    BSE_SCRIP_ENTITY_SCHEME,
    NSE_ENTITY_SCHEME,
    SEBI_SCRIP_ENTITY_SCHEME,
)

VERIFIED: Verdict = (VerificationState.VERIFIED, None)
# Task 0b pin (docs/workstreams/data-foundation/d6-capability.md §2, §3): the in-capmkt-ent
# entry point under IntegratedFinance_IndAS. Bank, NBFC and insurer filings use the same xsd
# file name under IntegratedFinance_Banking/_NBFC/_LI, so the namespace is what separates them.
IND_AS_ENTRY_POINT = re.compile(
    rb"^http://www\.sebi\.gov\.in/xbrl/IntegratedFinance_IndAS/\d{4}-\d{2}-\d{2}"
    rb"/in-capmkt/in-capmkt-ent$"
)
ENTRY_POINT_PREFIX = "in-capmkt-ent-"
_SCHEMA_REF = "{http://www.xbrl.org/2003/linkbase}schemaRef"
_HREF = "{http://www.w3.org/1999/xlink}href"
_MASTER_SYMBOL, _MASTER_SERIES, _MASTER_NAME, _MASTER_ISIN = (
    "SYMBOL",
    "SERIES",
    "NAME OF COMPANY",
    "ISIN NUMBER",
)
_EQ = "EQ"
_LI = re.compile(r"<li\b.*?</li>", re.S)
_LI_SCRIP = re.compile(r"</strong>(?:&nbsp;|\s)*(\d+)")
_SCREENER_CODE = re.compile(r"\b(BSE|NSE):\s*(\S+)")
_TOP_SPANS = "//*[@id='top']//span"
_SCREENER_URLS = ("/company/{symbol}/", "/company/{symbol}/consolidated/")
_TIJORI_COMPANY = "companies"
_NSE_EQ, _BSE_EQ = "NSE_EQ", "BSE_EQ"
_SCRIP_SCHEMES = (SEBI_SCRIP_ENTITY_SCHEME, BSE_SCRIP_ENTITY_SCHEME)
_DIFFERS = "{what} {found!r} differs from the expected {expected!r}"
_COUNT = "{what}: {count} candidates"


class Expected(BaseModel):
    """The identity a filing must carry at its filed date (``scrip`` None: not yet known)."""

    model_config = ConfigDict(frozen=True)

    isin: str
    symbol: str
    scrip: str | None


class FilingIdentity(BaseModel):
    """The identity facts and context pairs one instance declares."""

    model_config = ConfigDict(frozen=True)

    isin: frozenset[str]
    symbol: frozenset[str]
    scrip: frozenset[str]
    names: frozenset[str]
    pairs: frozenset[tuple[str, str]]


def conflict(detail: str) -> Verdict:
    """A contradiction, with what contradicted what."""
    return VerificationState.CONFLICT, detail


def differs(what: str, found: object, expected: object) -> Verdict:
    """A value that contradicts the expected one."""
    return conflict(_DIFFERS.format(what=what, found=found, expected=expected))


def normalise_name(name: str) -> str:
    """D4.3 pinned normalisation: casefold, drop ``.`` and ``,``, collapse whitespace,
    trailing ``ltd`` → ``limited``."""
    folded = " ".join(name.casefold().replace(".", "").replace(",", "").split())
    return re.sub(r"\bltd$", "limited", folded)


def master_rows(master: bytes, symbol: str) -> list[tuple[str, str]]:
    """``(name, ISIN)`` of each ``EQ`` row the NSE master lists for the symbol."""
    reader = csv.DictReader(io.StringIO(master.decode("utf-8-sig")))
    found = []
    for raw in reader:
        row = {key.strip(): (value or "").strip() for key, value in raw.items() if key}
        if row.get(_MASTER_SYMBOL) == symbol and row.get(_MASTER_SERIES) == _EQ:
            found.append((row[_MASTER_NAME], row[_MASTER_ISIN]))
    return found


def financial_rule(instance: bytes) -> bool:
    """Supported only on the positive non-financial signal: the ``in-capmkt-ent-`` schemaRef
    and the ``IntegratedFinance_IndAS`` entry-point namespace; anything else fails closed."""
    try:
        root = etree.fromstring(instance)
    except etree.XMLSyntaxError:
        return False
    refs = [ref.get(_HREF) or "" for ref in root.iter(_SCHEMA_REF)]
    namespaces = {uri.encode() for uri in root.nsmap.values() if uri}
    return (
        bool(refs)
        and all(ref.rsplit("/", 1)[-1].startswith(ENTRY_POINT_PREFIX) for ref in refs)
        and any(IND_AS_ENTRY_POINT.match(uri) for uri in namespaces)
    )


def filing_identity(instance: RawXbrlInstance) -> FilingIdentity:
    """The registered taxonomy's identity facts and every context ``(scheme, id)`` pair."""
    facts: dict[str, set[str]] = {"ISIN": set(), "Symbol": set(), "ScripCode": set()}
    names: set[str] = set()
    for fact in instance.facts:
        if fact.namespace_uri != instance.taxonomy.namespace:
            continue
        local = fact.concept_qname.rsplit(":", 1)[-1]
        text = (fact.raw_text or "").strip()
        if local in facts and text:
            facts[local].add(text)
        if local == "NameOfTheCompany" and text:
            names.add(normalise_name(text))
    return FilingIdentity(
        isin=frozenset(facts["ISIN"]),
        symbol=frozenset(facts["Symbol"]),
        scrip=frozenset(facts["ScripCode"]),
        names=frozenset(names),
        pairs=frozenset((f.entity_scheme, f.entity_id.strip()) for f in instance.facts),
    )


def instance_state(instance: RawXbrlInstance, period_end: date) -> Verdict:
    """The instance's own declarations against its listing row: the consolidated file scope
    and every declared reporting-period end (first-party ingest's own period predicate)."""
    if instance.scope is not Scope.CONSOLIDATED:
        return differs("instance scope", instance.scope.value, Scope.CONSOLIDATED.value)
    period = verify_xbrl_period(instance, period_end)
    return VERIFIED if period.verified else conflict(period.reason or "")


def xbrl_entity_state(filing: FilingIdentity, name: str, expected: Expected) -> Verdict:
    """ISIN and name as the master and expected identity; every context pair against the
    scheme → value map of the expected identity (NSE scheme ↔ symbol, scrip schemes ↔ scrip)."""
    if filing.isin != {expected.isin}:
        return differs("filing ISIN", sorted(filing.isin), expected.isin)
    if filing.names != {normalise_name(name)}:
        return differs("filing name", sorted(filing.names), name)
    scrip = expected.scrip if expected.scrip is not None else _one(filing.scrip)
    by_scheme = {NSE_ENTITY_SCHEME: expected.symbol, **dict.fromkeys(_SCRIP_SCHEMES, scrip)}
    for scheme, value in sorted(filing.pairs):
        if scheme not in by_scheme or value != by_scheme[scheme]:
            return differs(f"context {scheme}", value, by_scheme.get(scheme))
    return VERIFIED


def exchange_state(
    peer_search: bytes, isin: str, filings: Sequence[tuple[FilingIdentity, Expected]]
) -> tuple[Verdict, str | None]:
    """The ISIN check digit; exactly one exact-ISIN ``PeerSmartSearch`` candidate whose scrip
    equals each filing's ``ScripCode`` as expected at its date; each filing's ``Symbol`` the
    expected symbol. Returns the verdict and the verified scrip."""
    if isin_check_digit(isin[:11]) != isin[11:]:
        return conflict(f"ISIN {isin} fails its check digit"), None
    exact = f"<strong>{isin}</strong>"
    candidates = [li for li in _LI.findall(json.loads(peer_search)) if exact in li]
    if not candidates:
        return (VerificationState.UNVERIFIED, OnboardingReason.NO_CANDIDATE.value), None
    if len(candidates) > 1:
        return conflict(
            _COUNT.format(what="PeerSmartSearch exact ISIN", count=len(candidates))
        ), None
    found = _LI_SCRIP.search(candidates[0])
    scrip = found.group(1) if found else ""
    for filing, expected in filings:
        want = expected.scrip or scrip
        if filing.scrip != {scrip} or want != scrip:
            return differs("scrip", sorted(filing.scrip | {scrip}), want), None
        if filing.symbol != {expected.symbol}:
            return differs("filing symbol", sorted(filing.symbol), expected.symbol), None
    return VERIFIED, scrip


def screener_candidate(search: bytes, symbol: str) -> Verdict | int:
    """The one search result with an id at the symbol's company URL (none: UNAVAILABLE)."""
    urls = {template.format(symbol=symbol) for template in _SCREENER_URLS}
    found = json.loads(search)
    ids = [item["id"] for item in found if item.get("id") is not None and item.get("url") in urls]
    if not ids:
        return VerificationState.UNAVAILABLE, OnboardingReason.NO_CANDIDATE.value
    if len(ids) > 1:
        return conflict(_COUNT.format(what="Screener exact symbol", count=len(ids)))
    return int(ids[0])


def screener_page_state(page: bytes, company_id: int, symbol: str, scrip: str) -> Verdict:
    """The page's own company id and BSE/NSE codes equal the anchors; its consolidated basis
    proven by the adapter's gate (marker plus warehouse id)."""
    html = page.decode("utf-8", errors="replace")
    root = parse_document(html)
    try:
        assert_logged_in(root)
    except AnonymousPageError:
        return VerificationState.UNAVAILABLE, OnboardingReason.ACCESS_FAILED.value
    try:
        found_id, warehouse_id = read_identity(root)
    except ScreenerSessionError as error:
        return conflict(str(error))
    if found_id != company_id:
        return differs("Screener company id", found_id, company_id)
    spans = root.xpath(_TOP_SPANS)
    codes = {pair for span in spans for pair in _SCREENER_CODE.findall(span.text_content())}
    if codes != {("BSE", scrip), ("NSE", symbol)}:
        return differs("Screener codes", sorted(codes), [scrip, symbol])
    if warehouse_id is None:
        return VerificationState.UNVERIFIED, OnboardingReason.BASIS_UNVERIFIED.value
    try:
        topology = BasisTopology(consolidated_warehouse_id=warehouse_id)
        read_page_evidence(html, basis_requested=Basis.CONSOLIDATED, topology=topology)
    except ScreenerSessionError:
        return VerificationState.UNVERIFIED, OnboardingReason.BASIS_UNVERIFIED.value
    return VERIFIED


def tijori_candidate(search: bytes) -> Verdict | str:
    """The slug of the one ``companies`` result for the ISIN (none: UNAVAILABLE)."""
    slugs = [item["slug"] for item in json.loads(search) if item.get("type") == _TIJORI_COMPANY]
    if not slugs:
        return VerificationState.UNAVAILABLE, OnboardingReason.NO_CANDIDATE.value
    if len(slugs) > 1:
        return conflict(_COUNT.format(what="Tijori companies", count=len(slugs)))
    return str(slugs[0])


def tijori_page_state(page: bytes, symbol: str) -> Verdict:
    """The page's ``company_details.symbol`` equals the NSE symbol (its own gate classifies)."""
    record = classify_financials_body(page, expected_symbol=symbol, expected_company_id=None)
    if record.code is OutcomeCode.IDENTITY_MISMATCH:
        return conflict(f"Tijori page symbol is not {symbol}")
    if record.code is OutcomeCode.AUTH_EXPIRED:
        return VerificationState.UNAVAILABLE, OnboardingReason.ACCESS_FAILED.value
    if record.code is not OutcomeCode.OK:
        return VerificationState.UNVERIFIED, record.native_value
    return VERIFIED


def upstox_rows_state(instruments: bytes, isin: str, symbol: str, scrip: str) -> Verdict:
    """Exactly one ``NSE_EQ`` row with the symbol and one ``BSE_EQ`` row with the scrip for the
    ISIN; two in a venue conflict."""
    rows = [row for row in json.loads(gzip.decompress(instruments)) if row.get("isin") == isin]
    venues = ((_NSE_EQ, "trading_symbol", symbol), (_BSE_EQ, "exchange_token", scrip))
    for segment, field, value in venues:
        venue = [row for row in rows if row.get("segment") == segment]
        if len(venue) > 1:
            return conflict(_COUNT.format(what=f"Upstox {segment}", count=len(venue)))
        if not venue:
            return VerificationState.UNAVAILABLE, OnboardingReason.NO_CANDIDATE.value
        if venue[0].get(field) != value:
            return differs(f"Upstox {segment} {field}", venue[0].get(field), value)
    return VERIFIED


def upstox_statement_state(statement: bytes, url: str) -> Verdict:
    """The existing consolidated response gate: ``OK`` only (``OK_EMPTY`` → EMPTY_STATEMENT)."""
    document = read_income_statement(
        UpstoxFetch(
            raw_body=statement,
            capture=UpstoxCapture(
                surface=UpstoxSurface.INCOME_STATEMENT,
                route_key="default",
                request_url=url,
                http_status=200,
                media_type=None,
                byte_count=len(statement),
                content_sha256="0" * 64,
                outcome=AcquisitionOutcome.OK,
                retrieved_at=datetime.now(UTC),
            ),
        ),
        requested_basis=StatementBasis.CONSOLIDATED,
        requested_periodicity=StatementPeriodicity.QUARTERLY,
    )
    if document.outcome is AcquisitionOutcome.OK:
        return VERIFIED
    if document.outcome is AcquisitionOutcome.OK_EMPTY:
        return VerificationState.UNVERIFIED, OnboardingReason.EMPTY_STATEMENT.value
    return VerificationState.UNVERIFIED, OnboardingReason.BASIS_UNVERIFIED.value


def outcome(states: Mapping[VerificationUnit, Verdict]) -> tuple[OnboardingOutcome, str | None]:
    """Any conflict → IDENTITY_CONFLICT; an anchor not verified → UNSUPPORTED; another unit not
    verified → PARTIAL; else ONBOARDED. The reason is the deciding unit's."""
    for unit, (state, reason) in states.items():
        if state is VerificationState.CONFLICT:
            return OnboardingOutcome.IDENTITY_CONFLICT, f"{unit.value}: {reason}"
    unverified = [
        reason
        for state, reason in (
            states.get(unit, (VerificationState.UNVERIFIED, None)) for unit in ANCHOR_UNITS
        )
        if state is not VerificationState.VERIFIED
    ]
    if unverified:  # the refusing anchor's reason, not the one stopped by it
        stopped = OnboardingReason.STOPPED_ON_REFUSAL.value
        return OnboardingOutcome.UNSUPPORTED, next(
            (r for r in unverified if r != stopped), unverified[0]
        )
    if any(state is not VerificationState.VERIFIED for state, _ in states.values()):
        return OnboardingOutcome.PARTIAL, None
    return OnboardingOutcome.ONBOARDED, None


def _one(values: frozenset[str]) -> str | None:
    """The single value, if exactly one."""
    return next(iter(values)) if len(values) == 1 else None
