"""The one declared registry of vendor lines the three-source comparison reads.

Each entry names a row on a vendor's page (Screener's company page, Tijori's
quarterly JSON island), says what that row *is* there, carries the evidence tier a
comparison on it may conclude under, and lists its candidate XBRL concepts in
preference order — for several lines, which concept the vendor means is undecided.

Nothing here reconciles: this is a declaration ``reconcile`` reads, so it imports
nothing from ``reconcile``, ``api`` or ``store``; an import back would close a
cycle. It is also the single home of the derived alias table ``fact_view`` held
as a literal before S4 — :func:`alias_roles` reproduces it exactly, keys and
tuples in order, so no consumer of ``derived_concept_map`` changed behaviour.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from fundamentals.contracts.role import FactRole
from fundamentals.ingest.screener_crosscheck import EvidenceTier

MAP_VERSION = "2026-09-05.1"

# Section identifiers: the Screener values are ``screener_financials_models.Section``
# members, the Tijori one is the consolidated-quarterly table key of its JSON island.
SCREENER_QUARTERS = "quarters"
SCREENER_PROFIT_LOSS = "profit-loss"
TIJORI_QT_C = "qt_c"

REVENUE_FROM_OPERATIONS = "in-bse-fin:RevenueFromOperations"
PROFIT_BEFORE_TAX = "in-bse-fin:ProfitBeforeTax"
PROFIT_LOSS_FOR_PERIOD = "in-bse-fin:ProfitLossForPeriod"
PROFIT_ATTRIBUTABLE_TO_OWNERS = "in-bse-fin:ProfitOrLossAttributableToOwnersOfParent"
BASIC_EPS_CONTINUING_AND_DISCONTINUED = (
    "in-bse-fin:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations"
)

# Both vendors' "Net Profit" is one of these two until the replay decides which.
_NET_PROFIT_CANDIDATES = (PROFIT_LOSS_FOR_PERIOD, PROFIT_ATTRIBUTABLE_TO_OWNERS)

_UNMAPPED_ROW_MESSAGE = (
    "{source} section {section!r} row {row_selector!r} has no declared mapping; "
    "refusing to guess one"
)
_UNMAPPED_ALIAS_MESSAGE = "alias {alias!r} has no declared mapping; refusing to guess one"
# Empty exclusions on a tier-1 line claim an identity no measurement supports.
_TIER_ONE_NEEDS_EXCLUSION = "EQUIVALENCE_DEMONSTRATED requires the exclusion it failed on"
_ALIAS_REQUIRES_ROLE = "alias_qname and role must be set together, or neither"
_ENTRY_BINDS_NOTHING = "an entry with no row_selector must bind an alias_qname"
_DUPLICATE_MAPPING_ID = "duplicate mapping_id {value!r}"
_DUPLICATE_SELECTOR = "duplicate row selector {value!r}"
_DUPLICATE_ALIAS = "duplicate alias_qname {value!r}"


class MappedSource(StrEnum):
    """The vendors whose rows this registry declares."""

    SCREENER = "screener"
    TIJORI = "tijori"


class UnmappedRowError(LookupError):
    """A vendor row or alias nobody declared was asked for."""


class SourceLineMapping(BaseModel):
    """One vendor row: what it is, what it becomes, and what it may conclude.

    ``row_selector`` is ``"<parent>/<label>"`` for a schedule sub-row, the bare
    label at top level, and ``None`` for an alias-only binding — an alias with no
    vendor row behind it, reachable by alias and never by row lookup.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    mapping_id: str = Field(min_length=1)
    source: MappedSource
    section: str = Field(min_length=1)
    row_selector: str | None
    alias_qname: str | None
    role: FactRole | None
    means: str = Field(min_length=1)
    exclusions: tuple[str, ...] = ()
    tier: EvidenceTier
    concept_qnames: tuple[str, ...] = Field(min_length=1)
    map_version: str = MAP_VERSION

    @model_validator(mode="after")
    def _check_tier_and_bindings(self) -> SourceLineMapping:
        """Refuse a tier-1 line without its exclusion, or a half-bound entry."""
        if self.tier is EvidenceTier.EQUIVALENCE_DEMONSTRATED and not self.exclusions:
            raise ValueError(_TIER_ONE_NEEDS_EXCLUSION)
        if (self.alias_qname is None) != (self.role is None):
            raise ValueError(_ALIAS_REQUIRES_ROLE)
        if self.row_selector is None and self.alias_qname is None:
            raise ValueError(_ENTRY_BINDS_NOTHING)
        return self


def _selector_key(entry: SourceLineMapping) -> tuple[str, str, str] | None:
    """The row-lookup identity of an entry, or ``None`` for an alias-only one."""
    if entry.row_selector is None:
        return None
    return (entry.source.value, entry.section, entry.row_selector)


def build_registry(entries: Sequence[SourceLineMapping]) -> tuple[SourceLineMapping, ...]:
    """Return the entries as a registry, refusing any duplicated identity.

    A duplicate id, selector triple or alias makes a lookup return whichever entry
    happens to be first — a mapping chosen by list position, not by declaration.
    """
    seen_ids: set[str] = set()
    seen_selectors: set[tuple[str, str, str]] = set()
    seen_aliases: set[str] = set()
    for entry in entries:
        if entry.mapping_id in seen_ids:
            raise ValueError(_DUPLICATE_MAPPING_ID.format(value=entry.mapping_id))
        seen_ids.add(entry.mapping_id)
        selector = _selector_key(entry)
        if selector is not None:
            if selector in seen_selectors:
                raise ValueError(_DUPLICATE_SELECTOR.format(value=selector))
            seen_selectors.add(selector)
        if entry.alias_qname is not None:
            if entry.alias_qname in seen_aliases:
                raise ValueError(_DUPLICATE_ALIAS.format(value=entry.alias_qname))
            seen_aliases.add(entry.alias_qname)
    return tuple(entries)


# Registry order is load-bearing: ``alias_roles()`` derives the alias table from it,
# and that table's role and alias order must reproduce the pre-S4 literal in
# ``reconcile/fact_view.py`` exactly. Every tier below is EQUIVALENCE_UNPROVEN — no
# XBRL-to-vendor measurement exists yet (the 2026-09-04 sweep measured Upstox against
# Screener, neither against a filing).
REGISTRY: tuple[SourceLineMapping, ...] = build_registry(
    (
        SourceLineMapping(
            mapping_id="screener.quarters.sales",
            source=MappedSource.SCREENER,
            section=SCREENER_QUARTERS,
            row_selector="Sales",
            alias_qname="screener:Sales",
            role=FactRole.REVENUE,
            means="The top line of Screener's quarterly results table, labelled Sales.",
            tier=EvidenceTier.EQUIVALENCE_UNPROVEN,
            concept_qnames=(REVENUE_FROM_OPERATIONS,),
        ),
        SourceLineMapping(
            mapping_id="tijori.qt_c.net_sales",
            source=MappedSource.TIJORI,
            section=TIJORI_QT_C,
            row_selector="Net Sales",
            alias_qname="tijori:sales",
            role=FactRole.REVENUE,
            means="The Net Sales row of Tijori's consolidated quarterly table.",
            tier=EvidenceTier.EQUIVALENCE_UNPROVEN,
            concept_qnames=(REVENUE_FROM_OPERATIONS,),
        ),
        SourceLineMapping(
            mapping_id="tijori.qt_c.pbt",
            source=MappedSource.TIJORI,
            section=TIJORI_QT_C,
            row_selector="Profit Before Tax",
            alias_qname="tijori:pbt",
            role=FactRole.PROFIT_BEFORE_TAX,
            means="The Profit Before Tax row of Tijori's consolidated quarterly table.",
            tier=EvidenceTier.EQUIVALENCE_UNPROVEN,
            concept_qnames=(PROFIT_BEFORE_TAX,),
        ),
        SourceLineMapping(
            mapping_id="screener.quarters.net_profit",
            source=MappedSource.SCREENER,
            section=SCREENER_QUARTERS,
            row_selector="Net Profit",
            alias_qname="screener:NetProfit",
            role=FactRole.PROFIT_FOR_PERIOD,
            means="The Net Profit row of Screener's quarterly results table, post-tax.",
            tier=EvidenceTier.EQUIVALENCE_UNPROVEN,
            concept_qnames=_NET_PROFIT_CANDIDATES,
        ),
        SourceLineMapping(
            mapping_id="tijori.qt_c.net_profit",
            source=MappedSource.TIJORI,
            section=TIJORI_QT_C,
            row_selector="Net Profit",
            alias_qname="tijori:net_profit",
            role=FactRole.PROFIT_FOR_PERIOD,
            means="The Net Profit row of Tijori's consolidated quarterly table, post-tax.",
            tier=EvidenceTier.EQUIVALENCE_UNPROVEN,
            concept_qnames=_NET_PROFIT_CANDIDATES,
        ),
        SourceLineMapping(
            mapping_id="screener.quarters.eps",
            source=MappedSource.SCREENER,
            section=SCREENER_QUARTERS,
            row_selector="EPS in Rs",
            alias_qname="screener:EPS",
            role=FactRole.BASIC_EPS,
            means="The EPS in Rs row of Screener's quarterly table, a per-share rupee amount.",
            tier=EvidenceTier.EQUIVALENCE_UNPROVEN,
            concept_qnames=(BASIC_EPS_CONTINUING_AND_DISCONTINUED,),
        ),
        SourceLineMapping(
            mapping_id="tijori.eps.alias_only",
            source=MappedSource.TIJORI,
            section=TIJORI_QT_C,
            row_selector=None,
            alias_qname="tijori:eps",
            role=FactRole.BASIC_EPS,
            means=(
                "No Tijori EPS row is parsed today: the alias tijori:eps has no vendor row "
                "behind it, and this entry exists only so the role table is unchanged."
            ),
            tier=EvidenceTier.EQUIVALENCE_UNPROVEN,
            concept_qnames=(BASIC_EPS_CONTINUING_AND_DISCONTINUED,),
        ),
        SourceLineMapping(
            mapping_id="screener.quarters.pbt",
            source=MappedSource.SCREENER,
            section=SCREENER_QUARTERS,
            row_selector="Profit before tax",
            alias_qname=None,
            role=None,
            means=(
                "The Profit before tax row of Screener's quarterly results table; no "
                "observation producer emits it today, so it is a comparator line only."
            ),
            tier=EvidenceTier.EQUIVALENCE_UNPROVEN,
            concept_qnames=(PROFIT_BEFORE_TAX,),
        ),
        SourceLineMapping(
            mapping_id="screener.profit_loss.net_profit",
            source=MappedSource.SCREENER,
            section=SCREENER_PROFIT_LOSS,
            row_selector="Net Profit",
            alias_qname=None,
            role=None,
            means=(
                "The Net Profit row of Screener's profit-loss table, which is annual: it "
                "covers a full financial year and can never satisfy a quarterly comparison."
            ),
            tier=EvidenceTier.EQUIVALENCE_UNPROVEN,
            concept_qnames=_NET_PROFIT_CANDIDATES,
        ),
    )
)

_SELECTOR_INDEX: dict[tuple[str, str, str], SourceLineMapping] = {
    key: entry for entry in REGISTRY if (key := _selector_key(entry)) is not None
}

_ALIAS_INDEX: dict[str, SourceLineMapping] = {
    entry.alias_qname: entry for entry in REGISTRY if entry.alias_qname is not None
}


def mapping_for(source: MappedSource, section: str, row_selector: str) -> SourceLineMapping:
    """Resolve one declared row, refusing a row nobody has mapped.

    Guessing is how a false comparison is born: an undeclared row bound to the
    nearest-looking concept reports a mismatch on a line no one verified.
    """
    mapping = _SELECTOR_INDEX.get((source.value, section, row_selector))
    if mapping is None:
        raise UnmappedRowError(
            _UNMAPPED_ROW_MESSAGE.format(
                source=source.value, section=section, row_selector=row_selector
            )
        )
    return mapping


def mappings_for_alias(alias_qname: str) -> SourceLineMapping:
    """Resolve the entry an observation alias comes from, refusing an unknown alias."""
    mapping = _ALIAS_INDEX.get(alias_qname)
    if mapping is None:
        raise UnmappedRowError(_UNMAPPED_ALIAS_MESSAGE.format(alias=alias_qname))
    return mapping


def alias_roles() -> dict[FactRole, tuple[str, ...]]:
    """Group the registry's aliases by role, in registry order.

    Role order is first appearance, alias order is registry order — what keeps this
    identical to the pre-S4 table. Alias order decides which derived value is
    canonicalised first, so a reordered tuple is a behaviour change.
    """
    grouped: dict[FactRole, tuple[str, ...]] = {}
    for entry in REGISTRY:
        if entry.alias_qname is None or entry.role is None:
            continue
        grouped[entry.role] = (*grouped.get(entry.role, ()), entry.alias_qname)
    return grouped
