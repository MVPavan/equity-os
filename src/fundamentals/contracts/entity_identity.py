"""Frozen contracts for the entity identity map (``eqos-kx4.4``).

The map answers one question: for a listed security, what identifier does each
namespace we hold call it, and which source said so. Every value therefore
carries :class:`~fundamentals.contracts.provenance.Provenance`, and every
namespace publishes a coverage record even when nothing is known — the absence
of a field is never allowed to mean "unknown" (EM-12).

Two facts about an entity are deliberately separate. :class:`EntityState` is
about keying and listing and its members are mutually exclusive;
``Entity.conflicted`` is about two sources disagreeing, which can happen to an
entity in any state. Collapsing them would either hide a delisting from the
universe filter or hide a disagreement from the report.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from fundamentals.contracts.provenance import Provenance

NSE_KEY_PREFIX = "nse:"
BSE_KEY_PREFIX = "bse:"


class IdentifierNamespace(StrEnum):
    """One namespace an identifier value can be stated in.

    Numeric namespaces are held as strings: a Screener company id is an opaque
    handle, and arithmetic on it is always a mistake.
    """

    ISIN = "ISIN"
    NSE_SYMBOL = "NSE_SYMBOL"
    BSE_SCRIP = "BSE_SCRIP"
    SCREENER_SLUG = "SCREENER_SLUG"
    SCREENER_COMPANY_ID = "SCREENER_COMPANY_ID"
    TIJORI_SLUG = "TIJORI_SLUG"
    TIJORI_COMPANY_ID = "TIJORI_COMPANY_ID"


# The namespaces that key or join an entity, in the order EM-08's ladder tries
# them: ISIN first, then the NSE symbol, then the BSE scrip. Never a name.
JOIN_NAMESPACES: tuple[IdentifierNamespace, ...] = (
    IdentifierNamespace.ISIN,
    IdentifierNamespace.NSE_SYMBOL,
    IdentifierNamespace.BSE_SCRIP,
)


# The two namespaces EM-02 calls nullable unique alternate keys. They are lookup
# paths rather than identity, which is why a value neither source has confirmed
# is exempt from the uniqueness refusal — and why a duplicate among those
# unconfirmed values still has to be said out loud.
ALTERNATE_KEY_NAMESPACES: tuple[IdentifierNamespace, ...] = (
    IdentifierNamespace.NSE_SYMBOL,
    IdentifierNamespace.BSE_SCRIP,
)


class EntityState(StrEnum):
    """How an entity is keyed and whether it is listed. Mutually exclusive.

    ``ISIN_MISSING`` means no source supplied an ISIN, so the entity is keyed by
    a surrogate. ``NOT_LISTED`` means an ISIN keys it but neither exchange code
    is known — the delisting shape, which is kept rather than refused.
    """

    RESOLVED = "RESOLVED"
    NOT_LISTED = "NOT_LISTED"
    ISIN_MISSING = "ISIN_MISSING"


class CoverageStatus(StrEnum):
    """What the map holds for one namespace of one entity."""

    KNOWN = "KNOWN"
    UNVERIFIED = "UNVERIFIED"
    MISSING = "MISSING"
    CONFLICTED = "CONFLICTED"


class MissingReason(StrEnum):
    """Why a namespace holds no value.

    ``NOT_SUPPLIED`` is a statement about our coverage: no source carried the
    namespace at all. ``SOURCE_REPORTED_ABSENT`` is a statement about the
    company: a source carried the namespace and published nothing in it.
    """

    NOT_SUPPLIED = "NOT_SUPPLIED"
    SOURCE_REPORTED_ABSENT = "SOURCE_REPORTED_ABSENT"


class VerificationOutcome(StrEnum):
    """What comparing one hand-pinned stock against the watchlist evidence found."""

    CONFIRMED = "CONFIRMED"
    CONFLICTED = "CONFLICTED"
    NOT_COVERED = "NOT_COVERED"


class EntityMapError(ValueError):
    """Base refusal raised while building or verifying the entity identity map."""


class IsinFormatError(EntityMapError):
    """An ISIN failed the shape or the ISO 6166 check digit, so it is not stored."""


class UnkeyableRecordError(EntityMapError):
    """A source record carries no ISIN, NSE symbol or BSE scrip, so nothing keys it."""


class AlternateKeyCollisionError(EntityMapError):
    """Two securities claim one non-null value in an alternate-key namespace."""


class DuplicatePinnedSymbolError(AlternateKeyCollisionError):
    """Two hand-pinned stocks claim one NSE symbol, so the report has no key.

    Kept distinct from :class:`AlternateKeyCollisionError` because the fix lives
    somewhere else: this is a defect in a hand-edited config file, not a
    collision discovered in the entity graph.
    """


class DuplicateEntityKeyError(AlternateKeyCollisionError):
    """Two published entities would carry one key, so neither can be addressed.

    EM-01b promises one entity per key. Two surrogate-keyed securities whose
    symbols match — one of them flagged unconfirmed, so nothing joined them —
    would publish two rows under ``nse:<symbol>`` and make every advisory and
    every lookup naming that key ambiguous.
    """


class AmbiguousPinError(EntityMapError):
    """One pinned stock resolves to two different securities in the evidence.

    Picking a rung of the join ladder and calling it the answer would attribute
    a company's figures to whichever identifier happened to be tried first.
    """


class IncompleteEvidenceError(EntityMapError):
    """The watchlist artifact did not publish a complete result, so it is no evidence.

    A run that stopped short records its outcome rather than its rows. Reading
    such an artifact for its (empty) membership would report every pin as
    uncovered and exit zero — a failed acquisition reading as a clean map.
    """


class ShareClassCollisionError(EntityMapError):
    """Two distinct ISINs resolve to one Screener company id.

    Either a dual-class issuer, which needs a modelling decision, or a parse
    error. Both must stop the build rather than be merged silently.
    """


class SourceAssertion(BaseModel):
    """One source's claim that a security's identifier in a namespace is a value."""

    model_config = ConfigDict(frozen=True)

    namespace: IdentifierNamespace
    value: str = Field(min_length=1)
    provenance: Provenance
    verified: bool = True


class SourceRecord(BaseModel):
    """Everything one source asserts about one security, as the map ingests it.

    ``reported_absent`` names the namespaces this source carried and published
    nothing in. It is what separates "the source says there is no such value"
    from "no source looked", which :class:`MissingReason` keeps apart.
    """

    model_config = ConfigDict(frozen=True)

    source_id: str = Field(min_length=1)
    display_name: str | None = None
    assertions: tuple[SourceAssertion, ...] = ()
    reported_absent: tuple[IdentifierNamespace, ...] = ()


class IdentifierValue(BaseModel):
    """One identifier value the map holds, with every source that asserted it.

    ``provenances`` carries at least one mark, so a value with no recorded
    source cannot be stored. Two sources asserting the same value merge into one
    entry with two marks; two sources asserting different values stay two
    entries, which is what makes confirmation and conflict distinguishable.
    """

    model_config = ConfigDict(frozen=True)

    value: str = Field(min_length=1)
    provenances: tuple[Provenance, ...] = Field(min_length=1)
    verified: bool


class NamespaceCoverage(BaseModel):
    """What one entity holds in one namespace, stated rather than implied."""

    model_config = ConfigDict(frozen=True)

    namespace: IdentifierNamespace
    status: CoverageStatus
    values: tuple[IdentifierValue, ...] = ()
    missing_reason: MissingReason | None = None


class Entity(BaseModel):
    """One security: its published key, how it is keyed, and its coverage.

    ``display_names`` retains every name a source gave, because the S1 export
    truncates them and none of them is an identifier.
    """

    model_config = ConfigDict(frozen=True)

    key: str = Field(min_length=1)
    state: EntityState
    conflicted: bool
    display_names: tuple[str, ...] = ()
    namespaces: tuple[NamespaceCoverage, ...] = ()

    def coverage(self, namespace: IdentifierNamespace) -> NamespaceCoverage:
        """The coverage record this entity publishes for one namespace."""
        for covered in self.namespaces:
            if covered.namespace is namespace:
                return covered
        raise KeyError(namespace)


class DuplicateAlternateKey(BaseModel):
    """Two entities holding one alternate-key value that no source has confirmed.

    Not a conflict under EM-06 — nothing disagrees — and not a refusal under
    EM-02, because an unconfirmed value is no lookup path and so joins nothing.
    It is still worth saying: two hand-pinned scrips that are byte-identical is
    far more likely a copy-paste in a human-edited file than two securities that
    happen to share a code.
    """

    model_config = ConfigDict(frozen=True)

    namespace: IdentifierNamespace
    value: str = Field(min_length=1)
    entity_keys: tuple[str, ...] = Field(min_length=2)


class EntityMap(BaseModel):
    """The current-state map: every entity, and the keys excluded from lookup.

    There is deliberately no as-of, valid-from or version field. History belongs
    to the append-only snapshot store, and anticipating it here would fork
    bitemporal modelling across two deliverables.
    """

    model_config = ConfigDict(frozen=True)

    entities: tuple[Entity, ...] = ()
    conflicts: tuple[str, ...] = ()
    duplicate_alternate_keys: tuple[DuplicateAlternateKey, ...] = ()

    def lookup(self, namespace: IdentifierNamespace, value: str) -> Entity | None:
        """The one entity reachable by a verified value, or ``None``.

        A conflicted entity is unreachable however undisputed the namespace
        asked for: while two sources disagree about it, no lookup may hand it to
        a caller as if the disagreement were settled. An unverified value is
        also no lookup path — it is a pin nothing has confirmed.

        Known limitation (A29): uniqueness is enforced for the published key and
        for the three key namespaces, but not for slugs. Two entities holding
        one ``SCREENER_SLUG`` therefore resolve to whichever is published first.
        Widening uniqueness to the slug namespaces is a separate decision, not a
        silent one taken here.
        """
        for entity in self.entities:
            if entity.conflicted:
                continue
            for held in entity.coverage(namespace).values:
                if held.verified and held.value == value:
                    return entity
        return None

    def analysis_universe(self) -> tuple[Entity, ...]:
        """The entities admitted to analysis by default.

        A delisted entity is kept in the map — losing it would make the map
        blind to the very transition worth detecting — but it is not a
        candidate, and neither is one whose identity is under dispute.
        """
        return tuple(
            entity
            for entity in self.entities
            if entity.state is not EntityState.NOT_LISTED and not entity.conflicted
        )


class VerificationEntry(BaseModel):
    """One pinned stock's outcome against the watchlist evidence."""

    model_config = ConfigDict(frozen=True)

    symbol: str = Field(min_length=1)
    outcome: VerificationOutcome
    disagreements: tuple[IdentifierNamespace, ...] = ()


class VerificationReport(BaseModel):
    """The read-only result of comparing every pin against the watchlist."""

    model_config = ConfigDict(frozen=True)

    entries: tuple[VerificationEntry, ...] = ()

    def has_conflict(self) -> bool:
        """Whether any pin disagrees with the evidence, which alone fails a run."""
        return any(entry.outcome is VerificationOutcome.CONFLICTED for entry in self.entries)
