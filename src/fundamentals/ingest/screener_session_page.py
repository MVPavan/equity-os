"""Positive-evidence assertions over a Screener subscriber company page.

Pure and deterministic: every function here takes page HTML and returns what the
page *proves*, or raises a typed refusal. Nothing in this module fetches, and
nothing infers a fact from a URL, an HTTP status, or the absence of a bad
marker — the three ways this source is known to mislead:

* an expired cookie is served a **valid anonymous page**, so authentication is
  proven only by the Account menu (Profile link *and* the logout form);
* a standalone-only company answers its ``/consolidated/`` URL with HTTP 200 and
  a fully-sectioned page whose financial tables are empty, so basis is proven
  only by a basis marker plus a ``data-warehouse-id``;
* peer widgets carry other companies' identifiers, so identity is read from the
  page's own ``#company-info`` element, never from a body-wide search.

Structure verified 2026-08-26 against captured pages for all ten watchlist
companies (private captures, not committed).
"""

from __future__ import annotations

from typing import Any

from lxml import html as lxml_html  # type: ignore[import-untyped]

from fundamentals.ingest.screener_session_models import (
    AnonymousPageError,
    Basis,
    BasisEvidenceMissingError,
    BasisMismatchError,
    BasisTopology,
    IdentityAmbiguousError,
    IdentityMismatchError,
    PageEvidence,
    PageOutcome,
)

# The Account menu, rendered only for a live session. Both are required: the
# Profile link alone also appears in logged-out marketing markup on some pages.
ACCOUNT_LINK_XPATH = "//a[@href='/user/account/']"
LOGOUT_FORM_XPATH = "//form[@action='/logout/']"

COMPANY_INFO_XPATH = "//*[@id='company-info']"
COMPANY_ID_ATTRIBUTE = "data-company-id"
WAREHOUSE_ID_ATTRIBUTE = "data-warehouse-id"

CONSOLIDATED_FIGURES_MARKER = "Consolidated Figures"
STANDALONE_FIGURES_MARKER = "Standalone Figures"
VIEW_STANDALONE_MARKER = "View Standalone"
VIEW_CONSOLIDATED_MARKER = "View Consolidated"

# Recorded verbatim in metadata, in this order, so a drift in the site's own
# wording is visible in the artifact rather than only in a boolean.
RECORDED_MARKERS = (
    CONSOLIDATED_FIGURES_MARKER,
    STANDALONE_FIGURES_MARKER,
    VIEW_STANDALONE_MARKER,
    VIEW_CONSOLIDATED_MARKER,
)

# Only these markers *declare* a basis. The "View …" links name the OTHER basis
# (they are the toggle), so treating them as declarations would invert the read.
_DECLARING_MARKERS: dict[str, Basis] = {
    CONSOLIDATED_FIGURES_MARKER: Basis.CONSOLIDATED,
    STANDALONE_FIGURES_MARKER: Basis.STANDALONE,
}

# The sections whose tables are basis-scoped. ``insights`` is deliberately absent:
# it carries company-level KPI rows with their own period headers even on a page
# whose financial tables are empty, so counting it would hide the emptiness.
BASIS_SCOPED_SECTION_IDS = (
    "quarters",
    "profit-loss",
    "balance-sheet",
    "cash-flow",
    "ratios",
)
_PERIOD_HEADER_XPATH = ".//*[@data-result-table]//th[@data-date-key]"

_NO_ACCOUNT_MENU = (
    "screener served a page with no Account menu: the session cookie is not "
    "logged in (an expired cookie yields a valid anonymous page)"
)
_NO_IDENTITY = "screener page carries no #company-info identity element"
_AMBIGUOUS_IDENTITY = (
    "screener page carries {count} #company-info identity elements; exactly one is "
    "required so a decoy cannot answer for the real company"
)


def parse_document(html_text: str) -> Any:
    """Parse page HTML into an element tree for the assertions below."""
    return lxml_html.fromstring(html_text)


def assert_logged_in(root: Any) -> None:
    """Refuse a page that does not positively prove an authenticated session."""
    if not (root.xpath(ACCOUNT_LINK_XPATH) and root.xpath(LOGOUT_FORM_XPATH)):
        raise AnonymousPageError(_NO_ACCOUNT_MENU)


def read_identity(root: Any) -> tuple[int, int | None]:
    """Return the page's own ``(company_id, warehouse_id)`` from its one identity element.

    The warehouse id is optional: a standalone-only company's consolidated URL
    renders ``#company-info`` without one. The identity *element* is not: more
    than one makes identity depend on document order, which a planted decoy
    carrying the expected ids would exploit.
    """
    elements = root.xpath(COMPANY_INFO_XPATH)
    if len(elements) != 1:
        if not elements:
            raise IdentityAmbiguousError(_NO_IDENTITY)
        raise IdentityAmbiguousError(_AMBIGUOUS_IDENTITY.format(count=len(elements)))
    company_id = _numeric_attribute(elements[0], COMPANY_ID_ATTRIBUTE)
    if company_id is None:
        raise IdentityAmbiguousError(_NO_IDENTITY)
    return company_id, _numeric_attribute(elements[0], WAREHOUSE_ID_ATTRIBUTE)


def read_markers(root: Any) -> tuple[str, ...]:
    """Return the basis-related markers the page renders, in canonical order."""
    text = root.text_content()
    return tuple(marker for marker in RECORDED_MARKERS if marker in text)


def financial_tables_empty(root: Any) -> bool:
    """True when no basis-scoped section renders a single period column.

    Recorded as a fact, never used as the basis test: an empty table is what a
    degenerate consolidated page looks like, but emptiness alone could also mean
    a genuinely new listing.
    """
    for section_id in BASIS_SCOPED_SECTION_IDS:
        for section in root.xpath(f"//*[@id={section_id!r}]"):
            if section.xpath(_PERIOD_HEADER_XPATH):
                return False
    return True


def read_page_evidence(
    html_text: str, *, basis_requested: Basis, topology: BasisTopology
) -> tuple[PageEvidence, PageOutcome]:
    """Assert authentication, identity, and the basis the config says to expect.

    ``topology`` is the configured, live-verified answer to "which bases does
    this company publish"; it is never read off the page, because a page that
    has merely lost its marker is byte-indistinguishable from a standalone-only
    company's page. Given the topology there are exactly two legal shapes:

    * config publishes the requested basis → the page must prove it: a matching
      warehouse id, plus its basis marker — required everywhere except the one
      shape Screener renders unmarked, a standalone-only company's standalone
      page. Anything else raises :class:`BasisEvidenceMissingError`;
    * config does not publish the requested basis → the page must carry neither
      a marker nor a warehouse id, which is the degenerate consolidated shell
      and the only route to :attr:`PageOutcome.BASIS_UNAVAILABLE`.
    """
    root = parse_document(html_text)
    assert_logged_in(root)
    company_id, warehouse_id = read_identity(root)
    markers = read_markers(root)
    declared = _declared_basis(markers, basis_requested)
    tables_empty = financial_tables_empty(root)
    configured = topology.warehouse_id_for(basis_requested)

    if warehouse_id is not None and configured is not None and warehouse_id != configured:
        raise IdentityMismatchError(
            f"screener {basis_requested.value} page carries warehouse id {warehouse_id}, "
            f"expected {configured}"
        )
    if configured is None:
        _refuse_unexpected_basis(basis_requested, declared, warehouse_id)
        outcome = PageOutcome.BASIS_UNAVAILABLE
        basis_observed = None
    else:
        _require_basis_evidence(
            basis_requested,
            declared=declared,
            warehouse_id=warehouse_id,
            marker_optional=topology.standalone_only and basis_requested is Basis.STANDALONE,
        )
        outcome = PageOutcome.OK
        basis_observed = basis_requested

    return (
        PageEvidence(
            logged_in=True,
            company_id=company_id,
            warehouse_id=warehouse_id,
            markers=markers,
            basis_observed=basis_observed,
            single_basis=topology.single_basis,
            tables_empty=tables_empty,
        ),
        outcome,
    )


def _require_basis_evidence(
    basis_requested: Basis,
    *,
    declared: Basis | None,
    warehouse_id: int | None,
    marker_optional: bool,
) -> None:
    """Refuse a page that does not prove the basis the config says it publishes.

    ``marker_optional`` is true only for the one shape the site is known to
    render unmarked: the standalone page of a standalone-only company, which is
    offered no basis toggle. Every other page — a consolidated one above all,
    whatever the topology — must carry its own marker, because an unmarked page
    is precisely what a page that lost its marker looks like.
    """
    if warehouse_id is None:
        raise BasisEvidenceMissingError(
            f"screener {basis_requested.value} page carries no {WAREHOUSE_ID_ATTRIBUTE}, "
            "which config says it publishes; re-verify the identity map before trusting it"
        )
    if marker_optional:
        if declared is not None:
            raise BasisEvidenceMissingError(
                f"config records only a standalone basis for this company but the page now "
                f"declares {declared.value} figures; a basis toggle appeared, re-verify config"
            )
        return
    if declared is None:
        raise BasisEvidenceMissingError(
            f"screener {basis_requested.value} page carries no basis marker, which config says "
            "it publishes; an unmarked page is not proof of a basis"
        )


def _refuse_unexpected_basis(
    basis_requested: Basis, declared: Basis | None, warehouse_id: int | None
) -> None:
    """Refuse a page that shows a basis the config records as not published.

    Config says this company has no such basis, so a marker or a warehouse id on
    that URL means the company gained one: a fact to re-verify, never a silent
    acquisition and never the degenerate-page outcome.
    """
    if declared is None and warehouse_id is None:
        return
    seen = declared.value if declared is not None else f"{WAREHOUSE_ID_ATTRIBUTE}={warehouse_id}"
    raise BasisEvidenceMissingError(
        f"config records no {basis_requested.value} basis for this company but the page "
        f"carries {seen}; re-verify the identity map instead of acquiring it"
    )


def _declared_basis(markers: tuple[str, ...], basis_requested: Basis) -> Basis | None:
    """The basis the page declares, refusing any declaration that is not the one asked for."""
    declared = {basis for marker, basis in _DECLARING_MARKERS.items() if marker in markers}
    if not declared:
        return None
    if declared != {basis_requested}:
        named = ", ".join(sorted(basis.value for basis in declared))
        raise BasisMismatchError(
            f"screener page declares basis {named} but {basis_requested.value} was requested"
        )
    return basis_requested


def _numeric_attribute(element: Any, attribute: str) -> int | None:
    """Read one numeric identity attribute, or ``None`` when it is absent."""
    raw = element.get(attribute)
    if raw is None or not raw.strip():
        return None
    try:
        return int(raw.strip())
    except ValueError as error:
        raise IdentityMismatchError(
            f"screener page attribute {attribute} is not numeric: {raw!r}"
        ) from error
