"""Declared source classification: what authority a ``source_id`` carries.

Every observation binds to a ``source_id``, and reconciliation must know whether
that id names an authoritative first-party filing or a derived aggregator. This
module is the single place that answers that, and it answers it only from an
explicit declaration.

**Why this exists.** Classification used to be inferred: a source was derived if
its id contained ``screener`` or ``tijori``, and first-party otherwise. That
default is open — an id nobody had ever declared was granted the highest
authority the system has, purely because it did not spell a marker word. This
module inverts that: an undeclared source raises :class:`UnknownSourceError`.

**Why the class is not a field on** :class:`~fundamentals.contracts.provenance.Provenance`.
Some source ids are not known at import time. Three are declared in
``config/fundamentals.yaml`` (a per-issuer, per-quarter results PDF, its
transcript, and the XBRL instance) and one is built per filing
(``sec-edgar-20f-<accession>``). A closed registry cannot enumerate those, which
is exactly the pressure that produced the substring rule. So the classification
travels with the *declaration* of a source — a constant here, or a config block
that must state it — and the composition root resolves both into one catalog.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.canonical import Representation
from fundamentals.contracts.comparison import SourceRole


class SourceClass(StrEnum):
    """Whether a source is an authoritative first-party filing or a derived aggregator."""

    FIRST_PARTY = "first_party"
    DERIVED = "derived"


class EvidenceRole(StrEnum):
    """Whether a source's values may participate in reconciliation at all."""

    RECONCILABLE = "reconcilable"
    DIAGNOSTIC_ONLY = "diagnostic_only"


class UnknownSourceError(LookupError):
    """Raised when a ``source_id`` has not been declared in any catalog.

    Failing here is the point: an unrecognised source must be refused, never
    promoted to first-party by default.
    """


class SourceDescriptor(BaseModel):
    """One source's declared classification.

    ``is_namespace`` marks a declaration that covers every id beginning with
    ``source_id`` — used by the four families whose ids carry a per-item suffix
    (exchange announcements and SEC filings).
    """

    model_config = ConfigDict(frozen=True)

    source_id: str
    source_class: SourceClass
    evidence_role: EvidenceRole
    is_namespace: bool = False

    @property
    def may_reconcile(self) -> bool:
        """Whether values from this source may enter reconciliation."""
        return self.evidence_role is EvidenceRole.RECONCILABLE


class SurfaceAuthority(BaseModel):
    """One allowed vendor ``(source, surface)``: its role and retention authority (spec §3)."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    surface: str
    representation: Representation
    role: SourceRole
    retention_authority: str


class SurfaceNotAuthorisedError(LookupError):
    """The ``(source, surface)`` is not registered; capture and interpretation are refused."""


def surface_authority(
    source_id: str, surface: str, table: tuple[SurfaceAuthority, ...] | None = None
) -> SurfaceAuthority:
    """The registered authority of one surface in ``table`` (default ``VENDOR_SURFACES``)."""
    for authority in VENDOR_SURFACES if table is None else table:
        if (authority.source_id, authority.surface) == (source_id, surface):
            return authority
    raise SurfaceNotAuthorisedError(f"{source_id}/{surface} is not a registered vendor surface")


class SourceCatalog(BaseModel):
    """An explicit, closed set of source declarations.

    Resolution prefers an exact declaration, then the longest matching
    namespace. An id matching neither is refused.
    """

    model_config = ConfigDict(frozen=True)

    entries: tuple[SourceDescriptor, ...]

    @classmethod
    def of(cls, *descriptors: SourceDescriptor) -> SourceCatalog:
        """Build a catalog from descriptors."""
        return cls(entries=descriptors)

    def extend(self, *descriptors: SourceDescriptor) -> SourceCatalog:
        """Return a new catalog with additional declarations appended.

        Later declarations win on exact-id collision, so a config block may
        override a builtin without mutating it.
        """
        return SourceCatalog(entries=self.entries + descriptors)

    def describe(self, source_id: str) -> SourceDescriptor:
        """Resolve a ``source_id`` to its declaration, or refuse it."""
        exact = [entry for entry in self.entries if not entry.is_namespace]
        for entry in reversed(exact):
            if entry.source_id == source_id:
                return entry

        namespaces = [
            entry
            for entry in self.entries
            if entry.is_namespace and source_id.startswith(entry.source_id)
        ]
        if namespaces:
            return max(namespaces, key=lambda entry: len(entry.source_id))

        raise UnknownSourceError(
            f"source_id {source_id!r} is not declared in this catalog; "
            "declare it in BUILTIN_SOURCES or in the config block that names it. "
            "An undeclared source is refused, never treated as first-party."
        )

    def classify(self, source_id: str) -> SourceClass:
        """Resolve a ``source_id`` to its declared class, or refuse it."""
        return self.describe(source_id).source_class


def _first_party(source_id: str, *, is_namespace: bool = False) -> SourceDescriptor:
    """Declare an authoritative filing or issuer document."""
    return SourceDescriptor(
        source_id=source_id,
        source_class=SourceClass.FIRST_PARTY,
        evidence_role=EvidenceRole.RECONCILABLE,
        is_namespace=is_namespace,
    )


def _derived(source_id: str, *, is_namespace: bool = False) -> SourceDescriptor:
    """Declare an aggregator, media feed, or internal artifact."""
    return SourceDescriptor(
        source_id=source_id,
        source_class=SourceClass.DERIVED,
        evidence_role=EvidenceRole.RECONCILABLE,
        is_namespace=is_namespace,
    )


# Sources declared in code. Config-declared sources (the results PDF, the
# transcript, the XBRL instance) are added at the composition root and are not
# listed here — see the module docstring.
#
# Upstox is deliberately absent. It is the one source proven non-independent of
# Screener, its diagnostic lane is unbuilt, and while it is undeclared any leak
# into reconciliation raises instead of voting.
BUILTIN_SOURCES: SourceCatalog = SourceCatalog.of(
    _first_party("bse-xbrl"),
    _first_party("bse-summary"),
    _first_party("bse-results-pdf"),
    _first_party("nse-indas-xbrl-consolidated"),
    _first_party("nse-shareholding-xbrl"),
    _first_party("bse-announcements", is_namespace=True),
    _first_party("nse-announcements", is_namespace=True),
    _first_party("sec-edgar-", is_namespace=True),
    _derived("screener"),
    _derived("screener-subscriber"),
    _derived("tijori"),
    _derived("et-markets-rss", is_namespace=True),
    # Owner configuration and internal stores are not evidence. They are declared
    # derived so they can never satisfy the two-first-party requirement.
    _derived("watchlist-config"),
    _derived("news-store"),
)

_EXCHANGE_RIGHTS = "docs/evidence/phase-0a/a-05-rights-decision-004-private-use.md"
_SUBSCRIBER_RIGHTS = "docs/evidence/phase-0a/a-05-rights-decision-005-subscriber-scraping.md"
_UPSTOX_RIGHTS = "docs/research/upstox-rights-record.md"
# Owner decision 2026-09-03 (data spec §3): Upstox statements are a diagnostic parse-check only.
_UPSTOX_DIAGNOSTIC = "docs/specs/2026-10-11-canonical-financial-data-and-cross-source-comparison.md"
# No rights record covers SEBI; the D8 plan (Task 2b) records this bounded reference capture.
_REGULATOR_REFERENCE = "docs/workstreams/data-foundation/plans/D8.md"


def _surface(
    source_id: str, surface: str, representation: Representation, role: SourceRole, authority: str
) -> SurfaceAuthority:
    """Declare one allowed vendor surface."""
    return SurfaceAuthority(
        source_id=source_id,
        surface=surface,
        representation=representation,
        role=role,
        retention_authority=authority,
    )


# Onboarding discovery surfaces (plan D6 D4.4), as (source_id, surface).
NSE_MASTER = ("nse", "EQUITY_L")
NSE_RESULTS_LISTING = ("nse", "FINANCIAL_RESULTS_LISTING")
NSE_INTEGRATED_LISTING = ("nse", "INTEGRATED_FILING_LISTING")
NSE_XBRL_INSTANCE = ("nse-indas-xbrl-consolidated", "NSE_XBRL_INSTANCE")
BSE_PEER_SEARCH = ("bse", "PEER_SMART_SEARCH")
SCREENER_SEARCH = ("screener-subscriber", "SCREENER_SEARCH")
SCREENER_PAGE = ("screener-subscriber", "SCREENER_FINANCIALS")
TIJORI_SEARCH = ("tijori", "company_search")
TIJORI_PAGE = ("tijori", "financials")
UPSTOX_INSTRUMENTS = ("upstox", "instruments")
UPSTOX_STATEMENT = ("upstox", "income-statement")
# Shareholding-pattern surfaces (plan D8 R2, R8).
SHP_LISTING = ("nse", "SHAREHOLDING_LISTING")
SHP_XBRL = ("nse-shareholding-xbrl", "NSE_SHP_XBRL")
SCREENER_SHAREHOLDING = ("screener-subscriber", "SCREENER_SHAREHOLDING")
TIJORI_SHAREHOLDING = ("tijori", "shareholding")
# The Screener drill-down behind a shareholding-table hook (plan D8 Task 1b).
SCREENER_INVESTORS = ("screener-subscriber", "SCREENER_INVESTORS")
# The Tijori overview page a screen review reads (plan D7-screen-export S5).
TIJORI_OVERVIEW = ("tijori", "overview")
UPSTOX_SHAREHOLDING = ("upstox", "share-holdings")
# Definitional references for the SHP probe (plan D8 Task 2b): never interpreted.
SHP_TAXONOMY = ("nse", "SHP_TAXONOMY")
SEBI_REGULATION = ("sebi", "REGULATION_TEXT")
SCREENER_DOCS = ("screener", "SCREENER_DOCS")
# The Upstox surfaces that go to the API origin with the bearer token.
UPSTOX_ROUTED = (UPSTOX_STATEMENT, UPSTOX_SHAREHOLDING)
# A screen formula run at each vendor on an owner command (amendment 2026-10-18-screen-export): the
# Screener CSV export, the Screener raw-query page echoing the formula, Tijori's results JSON.
SCREEN_EXPORT = ("screener-subscriber", "SCREEN_EXPORT")
SCREENER_SCREEN_PAGE = ("screener-subscriber", "SCREEN_DEFINITION")
TIJORI_SCREEN = ("tijori", "screen_results")
_IDENTITY_SURFACES = (
    (NSE_MASTER, Representation.HTML, _EXCHANGE_RIGHTS),
    (NSE_RESULTS_LISTING, Representation.JSON, _EXCHANGE_RIGHTS),
    (NSE_INTEGRATED_LISTING, Representation.JSON, _EXCHANGE_RIGHTS),
    (BSE_PEER_SEARCH, Representation.HTML, _EXCHANGE_RIGHTS),
    (SCREENER_SEARCH, Representation.JSON, _SUBSCRIBER_RIGHTS),
    (TIJORI_SEARCH, Representation.JSON, _SUBSCRIBER_RIGHTS),
    (UPSTOX_INSTRUMENTS, Representation.JSON, _UPSTOX_RIGHTS),
    (SCREEN_EXPORT, Representation.CSV, _SUBSCRIBER_RIGHTS),
    (SCREENER_SCREEN_PAGE, Representation.HTML, _SUBSCRIBER_RIGHTS),
    (TIJORI_SCREEN, Representation.JSON, _SUBSCRIBER_RIGHTS),
    (SHP_LISTING, Representation.JSON, _EXCHANGE_RIGHTS),
    (SHP_TAXONOMY, Representation.XBRL, _EXCHANGE_RIGHTS),
    (SEBI_REGULATION, Representation.PDF, _REGULATOR_REFERENCE),
    (SCREENER_DOCS, Representation.HTML, _SUBSCRIBER_RIGHTS),
)

VENDOR_SURFACES: tuple[SurfaceAuthority, ...] = (
    _surface(
        "screener-subscriber",
        "SCREENER_FINANCIALS",
        Representation.HTML,
        SourceRole.INDEPENDENT_VENDOR,
        _SUBSCRIBER_RIGHTS,
    ),
    _surface(
        "screener-subscriber",
        "SCREENER_SCHEDULE",
        Representation.JSON,
        SourceRole.INDEPENDENT_VENDOR,
        _SUBSCRIBER_RIGHTS,
    ),
    _surface(
        "tijori",
        "financials",
        Representation.HTML,
        SourceRole.INDEPENDENT_VENDOR,
        _SUBSCRIBER_RIGHTS,
    ),
    *(
        _surface("upstox", surface, Representation.JSON, SourceRole.DIAGNOSTIC, _UPSTOX_DIAGNOSTIC)
        for surface in ("income-statement", "balance-sheet", "cash-flow", "key-ratios")
    ),
    *(
        _surface(*pair, representation, SourceRole.IDENTITY, authority)
        for pair, representation, authority in _IDENTITY_SURFACES
    ),
    _surface(*NSE_XBRL_INSTANCE, Representation.XBRL, SourceRole.FIRST_PARTY, _EXCHANGE_RIGHTS),
    _surface(*SHP_XBRL, Representation.XBRL, SourceRole.FIRST_PARTY, _EXCHANGE_RIGHTS),
    *(
        _surface(*pair, Representation.HTML, SourceRole.INDEPENDENT_VENDOR, _SUBSCRIBER_RIGHTS)
        for pair in (SCREENER_SHAREHOLDING, TIJORI_SHAREHOLDING, TIJORI_OVERVIEW)
    ),
    _surface(
        *SCREENER_INVESTORS, Representation.JSON, SourceRole.INDEPENDENT_VENDOR, _SUBSCRIBER_RIGHTS
    ),
    _surface(*UPSTOX_SHAREHOLDING, Representation.JSON, SourceRole.DIAGNOSTIC, _UPSTOX_DIAGNOSTIC),
)
