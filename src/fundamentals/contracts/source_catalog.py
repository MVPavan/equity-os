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
