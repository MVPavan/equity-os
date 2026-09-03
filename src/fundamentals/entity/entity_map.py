"""Build the entity identity map, and verify hand-pinned identifiers against it.

The build joins source records into entities, merges what agrees, records what
disagrees, and refuses the three shapes that cannot be resolved by looking
harder: a malformed ISIN, two securities claiming one alternate key, and two
ISINs resolving to one Screener company.

Nothing here opens a socket. The inputs are source records the adapters in
:mod:`fundamentals.entity.entity_map_sources` read from files already on disk,
and the output is a deterministic artifact: two builds over equal inputs, in any
order, serialise to the same bytes so a diff between two runs is meaningful.

Joining is by ISIN, then NSE symbol, then BSE scrip, and never by name — the
watchlist export truncates display names, and a wrong join silently attributes
one company's financials to another. Only a *verified* value joins: a value a
source flagged as unconfirmed is no lookup path, so it is neither a join key nor
subject to the alternate-key uniqueness rule.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Sequence
from itertools import combinations
from pathlib import Path

from fundamentals.contracts.entity_identity import (
    ALTERNATE_KEY_NAMESPACES,
    BSE_KEY_PREFIX,
    JOIN_NAMESPACES,
    NSE_KEY_PREFIX,
    AlternateKeyCollisionError,
    AmbiguousPinError,
    CoverageStatus,
    DuplicateAlternateKey,
    DuplicateEntityKeyError,
    DuplicatePinnedSymbolError,
    Entity,
    EntityMap,
    EntityState,
    IdentifierNamespace,
    IdentifierValue,
    IsinFormatError,
    MissingReason,
    NamespaceCoverage,
    ShareClassCollisionError,
    SourceRecord,
    UnkeyableRecordError,
    VerificationEntry,
    VerificationOutcome,
    VerificationReport,
)
from fundamentals.contracts.provenance import Provenance
from fundamentals.entity.entity_map_sources import load_s1_records, load_s2_records

# EM-01. ``IN`` is the country prefix, ``E``/``F``/``9`` the issue-type family
# the Indian numbering agency uses for equity, and the last character is the
# ISO 6166 check digit over the eleven before it.
_ISIN_PATTERN = re.compile(r"^IN[EF9][A-Z0-9]{8}[0-9]$")
_ISIN_BODY_LENGTH = 11
# ord("A") - 10, so a letter expands to its base-36 ordinal in decimal digits.
_ALPHABET_OFFSET = 55
_LUHN_MODULUS = 10

_BAD_ISIN = "{value!r} is not a valid ISIN: it fails the {half}"
_SHAPE_HALF = "shape rule"
_CHECK_DIGIT_HALF = "ISO 6166 check digit"
_UNKEYABLE = (
    "source {source!r} asserted a record with no ISIN, NSE symbol or BSE scrip: "
    "nothing identifies it, and a display name is not an identifier"
)
_ALTERNATE_KEY_COLLISION = (
    "two securities claim one alternate key: ISINs {isins} were joined through "
    "{namespace} {values}, so one of the two assertions is wrong"
)
_KEY_DISAGREEMENT = (
    "two records joined through an alternate key disagree on {namespace}: "
    "{mine} versus {theirs}. Neither carries an ISIN they share, so these are "
    "two securities and merging them would delete one of them from the map"
)
_DUPLICATE_ENTITY_KEY = (
    "two entities would be published under one key {keys}: EM-01b promises one "
    "entity per key, and nothing addressed by that key could be resolved"
)
_AMBIGUOUS_PIN = (
    "pinned stock {symbol} resolves to more than one security in the evidence: "
    "{keys}. The join ladder must not pick one of them by position"
)
_SHARE_CLASS_COLLISION = (
    "entities {keys} resolve to one screener company id {company_id}: either a "
    "dual-class issuer, which needs a modelling decision, or a parse error"
)
_DUPLICATE_PINNED_SYMBOL = "two pinned stocks claim NSE symbol {symbols}"
_PIN_WITHOUT_SYMBOL = "pinned stock from {source!r} carries no NSE symbol to report under"


def build_entity_map(records: Sequence[SourceRecord]) -> EntityMap:
    """Join source records into the current-state identity map, or refuse.

    Refuses a malformed ISIN, a record with no key of any kind, two securities
    sharing an alternate key, and two ISINs sharing a Screener company id. A
    disagreement between two sources is not a refusal: both values are kept and
    the entity is marked conflicted for a human to settle.
    """
    for record in records:
        _check_ingestible(record)
    entities = tuple(
        sorted(
            (_entity(group) for group in _group(records)),
            key=_publication_order,
        )
    )
    _refuse_duplicate_entity_keys(entities)
    _refuse_share_class_collisions(entities)
    return EntityMap(
        entities=entities,
        conflicts=tuple(entity.key for entity in entities if entity.conflicted),
        duplicate_alternate_keys=_duplicate_alternate_keys(entities),
    )


def verify_pins(artifact_path: Path, config_path: Path) -> VerificationReport:
    """Compare every hand-pinned stock against the watchlist evidence, read-only.

    Neither file is written, renamed or repaired. Correcting a pin is a human
    edit informed by this report; a ``verify`` that helpfully rewrote the config
    would destroy the hand-pinned assertion the next run needs to check.
    """
    evidence = load_s1_records(artifact_path)
    pins = load_s2_records(config_path)
    for pin in pins:
        _check_ingestible(pin)
    symbols = tuple(_pinned_symbol(pin) for pin in pins)
    _refuse_duplicate_pinned_symbols(symbols)
    resolved = build_entity_map(evidence)
    return VerificationReport(
        entries=tuple(
            _verify_pin(symbol, pin, resolved) for symbol, pin in zip(symbols, pins, strict=True)
        )
    )


def isin_check_digit(body: str) -> str:
    """The ISO 6166 check digit for an eleven-character ISIN body."""
    expanded = "".join(
        character if character.isdigit() else str(ord(character) - _ALPHABET_OFFSET)
        for character in body
    )
    total = 0
    for position, character in enumerate(reversed(expanded)):
        value = int(character)
        if position % 2 == 0:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return str((_LUHN_MODULUS - total % _LUHN_MODULUS) % _LUHN_MODULUS)


def _check_isin(value: str) -> None:
    """Refuse an ISIN that fails either half of EM-01, storing nothing."""
    if _ISIN_PATTERN.fullmatch(value) is None:
        raise IsinFormatError(_BAD_ISIN.format(value=value, half=_SHAPE_HALF))
    if isin_check_digit(value[:_ISIN_BODY_LENGTH]) != value[_ISIN_BODY_LENGTH:]:
        raise IsinFormatError(_BAD_ISIN.format(value=value, half=_CHECK_DIGIT_HALF))


def _check_ingestible(record: SourceRecord) -> None:
    """Refuse a record the map could not identify or could not trust."""
    for value in _values(record, IdentifierNamespace.ISIN):
        _check_isin(value)
    if not any(_values(record, namespace) for namespace in JOIN_NAMESPACES):
        raise UnkeyableRecordError(_UNKEYABLE.format(source=record.source_id))


def _values(record: SourceRecord, namespace: IdentifierNamespace) -> tuple[str, ...]:
    """Every value one record asserts in one namespace, in assertion order."""
    return tuple(
        assertion.value for assertion in record.assertions if assertion.namespace is namespace
    )


def _verified_values(record: SourceRecord, namespace: IdentifierNamespace) -> tuple[str, ...]:
    """The values of one namespace this record vouches for, so they may join."""
    return tuple(
        assertion.value
        for assertion in record.assertions
        if assertion.namespace is namespace and assertion.verified
    )


def _group(records: Sequence[SourceRecord]) -> tuple[tuple[SourceRecord, ...], ...]:
    """Partition records into one member per security, following EM-08's ladder."""
    parent = list(range(len(records)))

    def root(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for namespace in JOIN_NAMESPACES:
        first_seen: dict[str, int] = {}
        for index, record in enumerate(records):
            for value in _verified_values(record, namespace):
                held = first_seen.setdefault(value, index)
                parent[root(index)] = root(held)

    members: dict[int, list[SourceRecord]] = defaultdict(list)
    for index, record in enumerate(records):
        members[root(index)].append(record)
    groups = tuple(tuple(group) for group in members.values())
    for group in groups:
        _refuse_alternate_key_collision(group)
        _refuse_key_disagreement(group)
    return groups


def _refuse_alternate_key_collision(group: Sequence[SourceRecord]) -> None:
    """Refuse a joined group that turns out to hold two distinct ISINs.

    Two ISINs are two securities. If they were pulled together by a shared NSE
    symbol or BSE scrip, one of those claims is wrong, and merging them would
    attribute two companies' financials to one entity.
    """
    isins = _distinct(group, IdentifierNamespace.ISIN)
    if len(isins) < 2:
        return
    for namespace in ALTERNATE_KEY_NAMESPACES:
        shared = _shared_values(group, namespace)
        if shared:
            raise AlternateKeyCollisionError(
                _ALTERNATE_KEY_COLLISION.format(
                    isins=", ".join(isins),
                    namespace=namespace.value,
                    values=", ".join(shared),
                )
            )


def _refuse_key_disagreement(group: Sequence[SourceRecord]) -> None:
    """Refuse two records pulled together by an alternate key that contradict each other.

    The ISIN is the primary key: two records that share one are one security,
    and a disagreement between them is an EM-06 conflict to be recorded, not a
    refusal. Two records that share NO ISIN were pulled together by an alternate
    key alone, and if they then hold *different* confirmed values in another key
    namespace they are not one security at all — merging them would delete the
    second company's key from the published map without saying so.

    Only confirmed values count on both sides. EM-07 is explicit that an
    unverified value a second source contradicts is an ordinary conflict, so a
    mistyped hand-pinned scrip must never take a build down.
    """
    for first, second in combinations(group, 2):
        if _shares_a_confirmed_value(first, second, IdentifierNamespace.ISIN):
            continue
        for namespace in JOIN_NAMESPACES:
            mine = set(_verified_values(first, namespace))
            theirs = set(_verified_values(second, namespace))
            if mine and theirs and mine != theirs:
                raise AlternateKeyCollisionError(
                    _KEY_DISAGREEMENT.format(
                        namespace=namespace.value,
                        mine=", ".join(sorted(mine)),
                        theirs=", ".join(sorted(theirs)),
                    )
                )


def _shares_a_confirmed_value(
    first: SourceRecord, second: SourceRecord, namespace: IdentifierNamespace
) -> bool:
    """Whether two records vouch for one common value in a namespace."""
    return bool(set(_verified_values(first, namespace)) & set(_verified_values(second, namespace)))


def _distinct(group: Sequence[SourceRecord], namespace: IdentifierNamespace) -> tuple[str, ...]:
    """The distinct values a group of records holds in one namespace, sorted."""
    return tuple(sorted({value for record in group for value in _values(record, namespace)}))


def _shared_values(
    group: Sequence[SourceRecord], namespace: IdentifierNamespace
) -> tuple[str, ...]:
    """The verified values of one namespace that more than one record asserts."""
    counts: dict[str, int] = defaultdict(int)
    for record in group:
        for value in set(_verified_values(record, namespace)):
            counts[value] += 1
    return tuple(sorted(value for value, count in counts.items() if count > 1))


def _entity(group: Sequence[SourceRecord]) -> Entity:
    """Publish one security: its key, its keying state, and its full coverage."""
    namespaces = tuple(_coverage(group, namespace) for namespace in IdentifierNamespace)
    held = {covered.namespace: covered for covered in namespaces}
    isins = _distinct(group, IdentifierNamespace.ISIN)
    return Entity(
        key=_key(group, isins),
        state=_state(group, isins),
        conflicted=any(covered.status is CoverageStatus.CONFLICTED for covered in held.values()),
        display_names=tuple(
            sorted({record.display_name for record in group if record.display_name})
        ),
        namespaces=namespaces,
    )


def _coverage(group: Sequence[SourceRecord], namespace: IdentifierNamespace) -> NamespaceCoverage:
    """State what the map holds in one namespace, including why it holds nothing.

    "The source carried this column and published nothing in it" is an assertion
    about the company, not a gap in our coverage. So when another source does
    assert a value there, the two disagree, and the namespace is conflicted
    exactly as it would be for two different non-null values. Letting the
    asserted value win would turn a hand-typed pin into a confirmed lookup path
    contradicting the evidence, and would erase EM-03's delisting signal — the
    one transition the map exists to make visible.
    """
    values = _merge(group, namespace)
    reported_absent = any(namespace in record.reported_absent for record in group)
    if not values:
        return NamespaceCoverage(
            namespace=namespace,
            status=CoverageStatus.MISSING,
            missing_reason=(
                MissingReason.SOURCE_REPORTED_ABSENT
                if reported_absent
                else MissingReason.NOT_SUPPLIED
            ),
        )
    if len(values) > 1 or reported_absent:
        status = CoverageStatus.CONFLICTED
    else:
        status = CoverageStatus.KNOWN if values[0].verified else CoverageStatus.UNVERIFIED
    return NamespaceCoverage(namespace=namespace, status=status, values=values)


def _merge(
    group: Sequence[SourceRecord], namespace: IdentifierNamespace
) -> tuple[IdentifierValue, ...]:
    """Fold every assertion in one namespace into one entry per distinct value.

    Two sources asserting the same value produce one entry carrying both marks,
    which is how a second source promotes an unverified pin to verified. Two
    sources asserting different values produce two entries, which is what marks
    the namespace conflicted rather than letting one silently win.
    """
    marks: dict[str, list[Provenance]] = defaultdict(list)
    verified: dict[str, bool] = defaultdict(bool)
    for record in group:
        for assertion in record.assertions:
            if assertion.namespace is not namespace:
                continue
            marks[assertion.value].append(assertion.provenance)
            verified[assertion.value] = verified[assertion.value] or assertion.verified
    return tuple(
        IdentifierValue(
            value=value,
            provenances=tuple(sorted(marks[value], key=_provenance_order)),
            verified=verified[value],
        )
        for value in sorted(marks)
    )


def _provenance_order(mark: Provenance) -> str:
    """A total, content-derived order, so a rebuild serialises the same bytes."""
    return mark.model_dump_json()


def _key(group: Sequence[SourceRecord], isins: tuple[str, ...]) -> str:
    """The published key: the ISIN, else a namespaced surrogate.

    A surrogate is prefixed so it can never be read as an ISIN, and it survives
    only until a source supplies one — at which point the two records join and
    the entity is republished under the ISIN.
    """
    if isins:
        return isins[0]
    symbols = _distinct(group, IdentifierNamespace.NSE_SYMBOL)
    if symbols:
        return f"{NSE_KEY_PREFIX}{symbols[0]}"
    return f"{BSE_KEY_PREFIX}{_distinct(group, IdentifierNamespace.BSE_SCRIP)[0]}"


def _state(group: Sequence[SourceRecord], isins: tuple[str, ...]) -> EntityState:
    """How this entity is keyed and whether either exchange still lists it."""
    if not isins:
        return EntityState.ISIN_MISSING
    listed = _distinct(group, IdentifierNamespace.NSE_SYMBOL) or _distinct(
        group, IdentifierNamespace.BSE_SCRIP
    )
    return EntityState.RESOLVED if listed else EntityState.NOT_LISTED


def _publication_order(entity: Entity) -> tuple[int, str]:
    """ISIN-keyed entities first, each group lexicographic by key."""
    return (1 if entity.state is EntityState.ISIN_MISSING else 0, entity.key)


def _refuse_duplicate_entity_keys(entities: Sequence[Entity]) -> None:
    """Refuse two entities that would be published under one key.

    Reachable without any ISIN in play: two pins claiming one NSE symbol, one of
    them flagged unconfirmed so nothing joined them, are two surrogate-keyed
    entities under ``nse:<symbol>``. Publishing both would make every reference
    to that key ambiguous, the A17 advisory included.
    """
    seen: set[str] = set()
    for entity in entities:
        if entity.key in seen:
            raise DuplicateEntityKeyError(_DUPLICATE_ENTITY_KEY.format(keys=entity.key))
        seen.add(entity.key)


def _refuse_share_class_collisions(entities: Sequence[Entity]) -> None:
    """Refuse two DISTINCT ISINs that resolve to one Screener company id.

    EM-04 words the tripwire as two ISINs, and the scoping is load-bearing: a
    watchlist row and a config pin for one company that no rung of the ladder
    joined also share a company id, and EM-08 calls that missed join recoverable.
    Firing on it would kill the build over the live ICICI Securities shape —
    an ISIN with neither exchange code beside a pin carrying both.
    """
    claimants: dict[str, dict[str, set[str]]] = defaultdict(dict)
    for entity in entities:
        for held in entity.coverage(IdentifierNamespace.SCREENER_COMPANY_ID).values:
            claimants[held.value][entity.key] = {
                isin.value for isin in entity.coverage(IdentifierNamespace.ISIN).values
            }
    for company_id, by_key in sorted(claimants.items()):
        isins = {isin for held in by_key.values() for isin in held}
        if len(by_key) > 1 and len(isins) > 1:
            raise ShareClassCollisionError(
                _SHARE_CLASS_COLLISION.format(keys=", ".join(sorted(by_key)), company_id=company_id)
            )


def _duplicate_alternate_keys(
    entities: Sequence[Entity],
) -> tuple[DuplicateAlternateKey, ...]:
    """Report one alternate-key value that two published entities both hold.

    Only an unconfirmed value can reach this state: a value both sources vouch
    for joins its records into one entity, and two ISINs pulled together that
    way are refused outright. So a duplicate surviving to publication means at
    least one side is a pin nothing has checked — an advisory, not a refusal,
    because refusing would fail a build over a value the map never trusted.
    """
    advisories: list[DuplicateAlternateKey] = []
    for namespace in ALTERNATE_KEY_NAMESPACES:
        claimants: dict[str, list[str]] = defaultdict(list)
        for entity in entities:
            for held in entity.coverage(namespace).values:
                claimants[held.value].append(entity.key)
        advisories.extend(
            DuplicateAlternateKey(namespace=namespace, value=value, entity_keys=tuple(sorted(keys)))
            for value, keys in sorted(claimants.items())
            if len(keys) > 1
        )
    return tuple(advisories)


def _pinned_symbol(pin: SourceRecord) -> str:
    """The NSE symbol the verification report keys this pinned stock by."""
    symbols = _values(pin, IdentifierNamespace.NSE_SYMBOL)
    if not symbols:
        raise UnkeyableRecordError(_PIN_WITHOUT_SYMBOL.format(source=pin.source_id))
    return symbols[0]


def _refuse_duplicate_pinned_symbols(symbols: Iterable[str]) -> None:
    """Refuse a config whose pins do not have one report row each.

    The watchlist config constrains its Screener and Tijori ids for uniqueness
    but not its symbols, so nothing upstream catches this, and two pins under
    one symbol would silently collapse into one report row.
    """
    counts: dict[str, int] = defaultdict(int)
    for symbol in symbols:
        counts[symbol] += 1
    repeated = sorted(symbol for symbol, count in counts.items() if count > 1)
    if repeated:
        raise DuplicatePinnedSymbolError(
            _DUPLICATE_PINNED_SYMBOL.format(symbols=", ".join(repeated))
        )


def _verify_pin(symbol: str, pin: SourceRecord, resolved: EntityMap) -> VerificationEntry:
    """Compare one pin against the security the built evidence map resolves it to."""
    matched = _match(symbol, pin, resolved)
    if matched is None:
        return VerificationEntry(symbol=symbol, outcome=VerificationOutcome.NOT_COVERED)
    disagreements = tuple(
        namespace for namespace in IdentifierNamespace if _disagrees(pin, matched, namespace)
    )
    return VerificationEntry(
        symbol=symbol,
        outcome=(
            VerificationOutcome.CONFLICTED if disagreements else VerificationOutcome.CONFIRMED
        ),
        disagreements=disagreements,
    )


def _match(symbol: str, pin: SourceRecord, resolved: EntityMap) -> Entity | None:
    """The security this pin resolves to in the built evidence map, if exactly one.

    Resolution goes through the map rather than through raw records, so the
    refusals that catch ambiguous evidence — EM-02's uniqueness, EM-04's
    share-class tripwire, one-entity-per-key — have already run, and no answer
    can depend on the order rows happened to appear in the export.

    ``lookup`` matches only confirmed values, which is the join rule the build
    already follows: an unconfirmed pin is not a lookup path, so it must not drag
    a pin onto another company's row and manufacture disagreements there. Every
    rung of the ladder is tried, and two rungs pointing at two different
    securities is refused rather than settled by precedence.
    """
    found: dict[str, Entity] = {}
    for namespace in JOIN_NAMESPACES:
        for value in _verified_values(pin, namespace):
            entity = resolved.lookup(namespace, value)
            if entity is not None:
                found[entity.key] = entity
    if len(found) > 1:
        raise AmbiguousPinError(_AMBIGUOUS_PIN.format(symbol=symbol, keys=", ".join(sorted(found))))
    return next(iter(found.values()), None)


def _disagrees(pin: SourceRecord, matched: Entity, namespace: IdentifierNamespace) -> bool:
    """Whether the pin and the resolved security both state a namespace, differently.

    Every value the pin asserts is compared, confirmed or not: EM-07 says an
    unconfirmed value a second source contradicts is a disagreement like any
    other. Only *joining* is restricted to confirmed values.
    """
    pinned = set(_values(pin, namespace))
    observed = {held.value for held in matched.coverage(namespace).values}
    return bool(pinned) and bool(observed) and pinned != observed
