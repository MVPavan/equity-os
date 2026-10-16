"""Temporal identity layers over the D1a securities and listings (plan D6 D3.2, D3.3).

A security holds an ISIN and a listing its venue code over half-open intervals
``[valid_from, end)``; ``end`` is the effective date of the event whose ``ENDS`` edge names
the relationship. A target with no relationship rows in a namespace still holds its D1a base
value, unbounded; the base value becomes a relationship (citing its seed input, ``valid_from``
null) only when an event must end it. With no relationships or events every read returns
exactly the seeded values.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from enum import StrEnum
from typing import Any, LiteralString

import psycopg
from psycopg.rows import dict_row
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.entity_identity import JOIN_NAMESPACES, IdentifierNamespace
from fundamentals.ingest.xbrl_identity import ACCEPTED_ENTITY_IDS_BY_ISIN

ISIN = IdentifierNamespace.ISIN
_NAMESPACE_VENUE = {IdentifierNamespace.NSE_SYMBOL: "NSE", IdentifierNamespace.BSE_SCRIP: "BSE"}
_VENUE_NAMESPACE = {venue: namespace for namespace, venue in _NAMESPACE_VENUE.items()}

_NO_IDENTIFIERS = "entity {entity_id} has no security holding an ISIN, NSE and BSE listing"
_AMBIGUOUS_IDENTIFIERS = "entity {entity_id} has {count} complete securities; identity is ambiguous"
_NO_TARGET = "{namespace} target {target} does not exist"
_NOT_HELD = "{namespace} target {target} holds no open value at {at}"
_DIFFERENT = "{namespace} target {target} holds {held!r}; {value!r} needs an identity event"
_OVERLAP = "{namespace} {value!r} is held by another target over an overlapping interval"
_ONCE_HELD = "{namespace} {value!r} was held by another listing; only SYMBOL_REUSE may take it"
_STILL_HELD = "{namespace} {value!r} is still held by another listing at {at}"
_SHAPE = "{kind} needs {shape}"
_EARLY = "{kind} effective {at} precedes the start {start} of the value it ends"
_OWNER_HELD = "ISIN {isin}, symbol {symbol} or scrip {scrip} is held by another issuer"
_OWNER_ONCE_HELD = (
    "symbol {symbol} was held by another listing and no SYMBOL_REUSE gave it this one"
)
_ALIAS = "{kind} refused: ISIN {isin} is a registry alias (ACCEPTED_ENTITY_IDS_BY_ISIN)"


class IdentityConflictError(ValueError):
    """An identity write contradicts what the layers already hold."""


class IdentityEventKind(StrEnum):
    """What an ``identity_events`` row records."""

    ISIN_CHANGE = "ISIN_CHANGE"
    SYMBOL_CHANGE = "SYMBOL_CHANGE"
    SYMBOL_REUSE = "SYMBOL_REUSE"
    MERGER = "MERGER"
    DEMERGER = "DEMERGER"
    DELISTING = "DELISTING"


class EdgeRole(StrEnum):
    """How an event touches a relationship or an entity."""

    ENDS = "ENDS"
    STARTS = "STARTS"
    PREDECESSOR = "PREDECESSOR"
    SUCCESSOR = "SUCCESSOR"


class IdentifierRef(BaseModel):
    """One target's namespace: ``ISIN`` names a security, a venue code a listing."""

    model_config = ConfigDict(frozen=True)

    namespace: IdentifierNamespace
    target_id: int


class SliceValue(BaseModel):
    """One identifier a target holds at the slice date."""

    model_config = ConfigDict(frozen=True)

    entity_id: int
    security_id: int
    listing_id: int | None
    namespace: IdentifierNamespace
    value: str
    evidence_input_id: int


class _Holding(BaseModel):
    """One interval over which a target holds a value (``relationship_id`` None = base)."""

    model_config = ConfigDict(frozen=True)

    ref: IdentifierRef
    entity_id: int
    security_id: int
    value: str
    start: date | None
    end: date | None
    relationship_id: int | None
    evidence_input_id: int

    def active(self, at: date) -> bool:
        """Started on/before ``at`` and not ended on/before it."""
        return (self.start is None or self.start <= at) and (self.end is None or at < self.end)


_CHANGES = (
    IdentityEventKind.ISIN_CHANGE,
    IdentityEventKind.SYMBOL_CHANGE,
    IdentityEventKind.SYMBOL_REUSE,
)
_SHAPES = {
    IdentityEventKind.ISIN_CHANGE: "one ISIN ended and one started on the same security",
    IdentityEventKind.SYMBOL_CHANGE: "one venue code ended and one started on the same listing",
    IdentityEventKind.SYMBOL_REUSE: "one venue code ended and one started on the same listing",
    IdentityEventKind.DELISTING: "venue codes of one listing ended and none started",
    IdentityEventKind.MERGER: "disjoint entities: at least one predecessor, one successor",
    IdentityEventKind.DEMERGER: "disjoint entities: one predecessor, at least one successor",
}


def latest_slice(
    conn: psycopg.Connection[Any], as_of: date | None = None
) -> tuple[SliceValue, ...]:
    """Every identifier every target holds at ``as_of`` (``None``: the store's current date)."""
    at = as_of if as_of is not None else _store_date(conn)
    return tuple(
        SliceValue(
            entity_id=held.entity_id,
            security_id=held.security_id,
            listing_id=None if held.ref.namespace is ISIN else held.ref.target_id,
            namespace=held.ref.namespace,
            value=held.value,
            evidence_input_id=held.evidence_input_id,
        )
        for held in _holdings(conn)
        if held.active(at)
    )


def issuer_values(
    conn: psycopg.Connection[Any], entity_id: int, as_of: date | None = None
) -> tuple[SliceValue, SliceValue, SliceValue]:
    """The one security's ISIN, NSE symbol and BSE scrip the entity holds at ``as_of``."""
    held = [item for item in latest_slice(conn, as_of) if item.entity_id == entity_id]
    complete = [
        values
        for values in (
            [
                [item for item in held if item.security_id == security and item.namespace is ns]
                for ns in JOIN_NAMESPACES
            ]
            for security in sorted({item.security_id for item in held})
        )
        if all(values)
    ]
    if not complete:
        raise LookupError(_NO_IDENTIFIERS.format(entity_id=entity_id))
    if len(complete) > 1 or any(len(values) > 1 for values in complete[0]):
        raise LookupError(_AMBIGUOUS_IDENTIFIERS.format(entity_id=entity_id, count=len(complete)))
    (isin,), (nse,), (bse,) = complete[0]
    return isin, nse, bse


def resolve_owner(
    conn: psycopg.Connection[Any], symbol: str, isin: str, scrip: str | None
) -> tuple[int | None, str | None, set[IdentifierRef]]:
    """The entity whose current ISIN, NSE symbol and (once known) BSE scrip all sit on one
    security, ``None`` when none is held, with the targets hit. A partial or split hit, or a
    symbol once held by another listing that no ``SYMBOL_REUSE`` gave this one, is a conflict
    detail."""
    wanted = {(IdentifierNamespace.ISIN, isin), (IdentifierNamespace.NSE_SYMBOL, symbol)}
    if scrip is not None:
        wanted.add((IdentifierNamespace.BSE_SCRIP, scrip))
    hits = [v for v in latest_slice(conn) if (v.namespace, v.value) in wanted]
    targets = {
        IdentifierRef(namespace=v.namespace, target_id=v.listing_id or v.security_id) for v in hits
    }
    split = sorted(v.namespace for v in hits) != sorted(ns for ns, _ in wanted)
    if hits and (split or len({v.security_id for v in hits}) > 1):
        return None, _OWNER_HELD.format(isin=isin, symbol=symbol, scrip=scrip), targets
    nse = next((v.listing_id for v in hits if v.namespace is IdentifierNamespace.NSE_SYMBOL), None)
    others = {row[0] for row in conn.execute(_OWNER_ONCE_HELD_SQL, (symbol, symbol))} - {nse}
    if others and not conn.execute(_OWNER_REUSED_SQL, (nse, symbol)).fetchall():
        return None, _OWNER_ONCE_HELD.format(symbol=symbol), targets
    return (hits[0].entity_id if hits else None), None, targets


def record_relationship(
    conn: psycopg.Connection[Any],
    ref: IdentifierRef,
    value: str,
    evidence_input_id: int,
    *,
    valid_from: date | None = None,
) -> int | None:
    """Give a target a value it lacks; the value it already holds writes nothing (``None``).

    A different value for the target, or the value held by another target over an overlapping
    interval, raises :class:`IdentityConflictError`: a change needs an event.
    """
    with conn.transaction():
        lock_identifiers(conn, [ref], [(ref.namespace, value)])
        holdings = _holdings(conn)
        _target(holdings, conn, ref)
        own = [held for held in holdings if held.ref == ref and held.end is None]
        if any(held.value == value for held in own):
            return None
        if own:
            raise IdentityConflictError(
                _DIFFERENT.format(
                    namespace=ref.namespace, target=ref.target_id, held=own[0].value, value=value
                )
            )
        _refuse_overlap(holdings, ref, value, valid_from or date.min)
        return _insert_relationship(conn, ref, value, valid_from, evidence_input_id)


def record_event(
    conn: psycopg.Connection[Any],
    kind: IdentityEventKind,
    effective_date: date,
    evidence_input_id: int,
    *,
    ends: Sequence[IdentifierRef] = (),
    starts: Sequence[tuple[IdentifierRef, str]] = (),
    predecessors: Sequence[int] = (),
    successors: Sequence[int] = (),
) -> int:
    """Record one identity event with its edges and started relationships, atomically."""
    _refuse_shape(kind, ends, starts, predecessors, successors)
    with conn.transaction():
        lock_identifiers(
            conn, [*ends, *(ref for ref, _ in starts)], [(r.namespace, v) for r, v in starts]
        )
        holdings = _holdings(conn)
        ended = [_open(holdings, conn, ref, effective_date, kind) for ref in ends]
        for ref, value in starts:
            _target(holdings, conn, ref)
            _refuse_start(holdings, kind, ref, value, effective_date)
        if kind in _CHANGES:
            _refuse_alias(holdings, kind, ends[0])
        event_id = int(_one(conn, _INSERT_EVENT, (kind.value, effective_date, evidence_input_id)))
        for held in ended:
            relationship_id = held.relationship_id or _insert_relationship(
                conn, held.ref, held.value, None, held.evidence_input_id
            )
            conn.execute(_INSERT_EDGE, (event_id, EdgeRole.ENDS.value, relationship_id, None))
        for ref, value in starts:
            started = _insert_relationship(conn, ref, value, effective_date, evidence_input_id)
            conn.execute(_INSERT_EDGE, (event_id, EdgeRole.STARTS.value, started, None))
        for role, entities in (
            (EdgeRole.PREDECESSOR, predecessors),
            (EdgeRole.SUCCESSOR, successors),
        ):
            for entity_id in entities:
                conn.execute(_INSERT_EDGE, (event_id, role.value, None, entity_id))
    return event_id


def _refuse_shape(
    kind: IdentityEventKind,
    ends: Sequence[IdentifierRef],
    starts: Sequence[tuple[IdentifierRef, str]],
    predecessors: Sequence[int],
    successors: Sequence[int],
) -> None:
    """Each kind's edge shape (D3.2); predecessors and successors are disjoint."""
    renamed = len(ends) == len(starts) == 1 and starts[0][0] == ends[0]
    entities = bool(predecessors or successors)
    if kind is IdentityEventKind.ISIN_CHANGE:
        ok = renamed and ends[0].namespace is ISIN and not entities
    elif kind in _CHANGES:
        ok = renamed and ends[0].namespace is not ISIN and not entities
    elif kind is IdentityEventKind.DELISTING:
        ok = (
            bool(ends)
            and not starts
            and not entities
            and all(ref.namespace is not ISIN for ref in ends)
            and len({ref.target_id for ref in ends}) == 1
        )
    else:
        one, many = (successors, predecessors)
        if kind is IdentityEventKind.DEMERGER:
            one, many = predecessors, successors
        ok = (
            not ends
            and not starts
            and len(one) == 1
            and len(many) >= 1
            and not set(predecessors) & set(successors)
        )
    if not ok:
        raise IdentityConflictError(_SHAPE.format(kind=kind, shape=_SHAPES[kind]))


def _open(
    holdings: Sequence[_Holding],
    conn: psycopg.Connection[Any],
    ref: IdentifierRef,
    at: date,
    kind: IdentityEventKind,
) -> _Holding:
    """The target's open value that an event effective ``at`` ends."""
    _target(holdings, conn, ref)
    found = [held for held in holdings if held.ref == ref and held.end is None]
    if not found:
        raise IdentityConflictError(
            _NOT_HELD.format(namespace=ref.namespace, target=ref.target_id, at=at)
        )
    held = found[0]
    if held.start is not None and at < held.start:
        raise IdentityConflictError(_EARLY.format(kind=kind, at=at, start=held.start))
    return held


def _refuse_start(
    holdings: Sequence[_Holding],
    kind: IdentityEventKind,
    ref: IdentifierRef,
    value: str,
    at: date,
) -> None:
    """A started value must be free from ``at``; a venue code once held elsewhere only by reuse."""
    others = [
        held
        for held in holdings
        if held.ref.namespace is ref.namespace and held.value == value and held.ref != ref
    ]
    if kind is IdentityEventKind.SYMBOL_CHANGE and others:
        raise IdentityConflictError(_ONCE_HELD.format(namespace=ref.namespace, value=value))
    if kind is IdentityEventKind.SYMBOL_REUSE and any(
        held.end is None or held.end > at for held in others
    ):
        raise IdentityConflictError(_STILL_HELD.format(namespace=ref.namespace, value=value, at=at))
    _refuse_overlap(holdings, ref, value, at)


def _refuse_overlap(
    holdings: Sequence[_Holding], ref: IdentifierRef, value: str, start: date
) -> None:
    """No other target may hold the value over ``[start, ∞)``."""
    for held in holdings:
        if (
            held.ref != ref
            and held.ref.namespace is ref.namespace
            and held.value == value
            and (held.end is None or held.end > start)
        ):
            raise IdentityConflictError(_OVERLAP.format(namespace=ref.namespace, value=value))


def _refuse_alias(
    holdings: Sequence[_Holding], kind: IdentityEventKind, ref: IdentifierRef
) -> None:
    """A registry-alias ISIN's rename is encoded by the registry; an event would duplicate it."""
    security_id = next(held.security_id for held in holdings if held.ref == ref)
    for held in holdings:
        if (
            held.security_id == security_id
            and held.ref.namespace is ISIN
            and held.value in ACCEPTED_ENTITY_IDS_BY_ISIN
        ):
            raise IdentityConflictError(_ALIAS.format(kind=kind, isin=held.value))


def _target(
    holdings: Sequence[_Holding], conn: psycopg.Connection[Any], ref: IdentifierRef
) -> None:
    """Refuse a target that does not exist in its namespace (a listing of another venue)."""
    if any(held.ref == ref for held in holdings):
        return
    if ref.namespace is ISIN:
        found = conn.execute(_SECURITY_EXISTS, (ref.target_id,)).fetchall()
    else:
        venue = _NAMESPACE_VENUE[ref.namespace]
        found = conn.execute(_LISTING_EXISTS, (ref.target_id, venue)).fetchall()
    if not found:
        raise IdentityConflictError(
            _NO_TARGET.format(namespace=ref.namespace, target=ref.target_id)
        )


def _holdings(conn: psycopg.Connection[Any]) -> list[_Holding]:
    """Every interval every target holds: relationships where recorded, else the base value."""
    with conn.cursor(row_factory=dict_row) as cursor:
        bases = cursor.execute(_BASES).fetchall()
        relationships = cursor.execute(_RELATIONSHIPS).fetchall()
    found: list[_Holding] = []
    covered: set[IdentifierRef] = set()
    for row in relationships:
        is_isin = row["security_id"] is not None
        ref = IdentifierRef(
            namespace=IdentifierNamespace(row["namespace"]),
            target_id=row["security_id"] if is_isin else row["listing_id"],
        )
        covered.add(ref)
        found.append(
            _Holding(
                ref=ref,
                entity_id=row["entity_id"],
                security_id=row["owner_security_id"],
                value=row["value"],
                start=row["valid_from"],
                end=row["end_date"],
                relationship_id=row["id"],
                evidence_input_id=row["evidence_input_id"],
            )
        )
    for row in bases:
        namespace = ISIN if row["listing_id"] is None else _VENUE_NAMESPACE[row["venue"]]
        ref = IdentifierRef(
            namespace=namespace,
            target_id=row["security_id"] if namespace is ISIN else row["listing_id"],
        )
        if row["value"] is None or ref in covered:
            continue
        found.append(
            _Holding(
                ref=ref,
                entity_id=row["entity_id"],
                security_id=row["security_id"],
                value=row["value"],
                start=None,
                end=None,
                relationship_id=None,
                evidence_input_id=row["evidence_input_id"],
            )
        )
    return found


def lock_identifiers(
    conn: psycopg.Connection[Any],
    refs: Sequence[IdentifierRef],
    values: Sequence[tuple[IdentifierNamespace, str]],
) -> None:
    """Transaction locks on each ``(target, namespace)`` and ``(namespace, value)``, sorted."""
    keys = {f"target:{ref.namespace}:{ref.target_id}" for ref in refs} | {
        f"value:{namespace}:{value}" for namespace, value in values
    }
    for key in sorted(keys):
        conn.execute(_LOCK, (key,))


def _insert_relationship(
    conn: psycopg.Connection[Any],
    ref: IdentifierRef,
    value: str,
    valid_from: date | None,
    evidence_input_id: int,
) -> int:
    """Insert one relationship row."""
    security_id = ref.target_id if ref.namespace is ISIN else None
    listing_id = None if ref.namespace is ISIN else ref.target_id
    params = (security_id, listing_id, ref.namespace.value, value, valid_from, evidence_input_id)
    return int(_one(conn, _INSERT_RELATIONSHIP, params))


def _store_date(conn: psycopg.Connection[Any]) -> date:
    """The store clock's Asia/Kolkata date."""
    return date.fromisoformat(str(_one(conn, _STORE_DATE, ())))


def _one(conn: psycopg.Connection[Any], query: LiteralString, params: tuple[object, ...]) -> Any:
    """The first column of the one row a statement returns."""
    row = conn.execute(query, params).fetchone()
    assert row is not None
    return row[0]


_STORE_DATE: LiteralString = "SELECT (eqos.store_now() AT TIME ZONE 'Asia/Kolkata')::date"
_LOCK: LiteralString = "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))"
_SECURITY_EXISTS: LiteralString = "SELECT 1 FROM eqos.securities WHERE id = %s"
_LISTING_EXISTS: LiteralString = "SELECT 1 FROM eqos.listings WHERE id = %s AND venue = %s"
_BASES: LiteralString = (
    "SELECT s.entity_id, s.id AS security_id, NULL::bigint AS listing_id, NULL AS venue, "
    "s.isin AS value, s.evidence_input_id FROM eqos.securities s "
    "UNION ALL SELECT s.entity_id, s.id, l.id, l.venue, l.symbol, l.evidence_input_id "
    "FROM eqos.listings l JOIN eqos.securities s ON s.id = l.security_id "
    "ORDER BY 2, 3 NULLS FIRST"
)
_RELATIONSHIPS: LiteralString = (
    "SELECT r.id, r.security_id, r.listing_id, r.namespace, r.value, r.valid_from, "
    "r.evidence_input_id, s.id AS owner_security_id, s.entity_id, e.effective_date AS end_date "
    "FROM eqos.identifier_relationships r "
    "LEFT JOIN eqos.listings l ON l.id = r.listing_id "
    "JOIN eqos.securities s ON s.id = COALESCE(r.security_id, l.security_id) "
    "LEFT JOIN eqos.identity_event_edges g ON g.relationship_id = r.id AND g.role = 'ENDS' "
    "LEFT JOIN eqos.identity_events e ON e.id = g.event_id ORDER BY r.id"
)
_INSERT_RELATIONSHIP: LiteralString = (
    "INSERT INTO eqos.identifier_relationships "
    "(security_id, listing_id, namespace, value, valid_from, evidence_input_id) "
    "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id"
)
_INSERT_EVENT: LiteralString = (
    "INSERT INTO eqos.identity_events (kind, effective_date, evidence_input_id) "
    "VALUES (%s, %s, %s) RETURNING id"
)
_INSERT_EDGE: LiteralString = (
    "INSERT INTO eqos.identity_event_edges (event_id, role, relationship_id, entity_id) "
    "VALUES (%s, %s, %s, %s)"
)
_OWNER_ONCE_HELD_SQL: LiteralString = (
    "SELECT id FROM eqos.listings WHERE venue = 'NSE' AND symbol = %s "
    "UNION SELECT listing_id FROM eqos.identifier_relationships "
    "WHERE namespace = 'NSE_SYMBOL' AND value = %s"
)
_OWNER_REUSED_SQL: LiteralString = (
    "SELECT 1 FROM eqos.identity_events e "
    "JOIN eqos.identity_event_edges g ON g.event_id = e.id AND g.role = 'STARTS' "
    "JOIN eqos.identifier_relationships r ON r.id = g.relationship_id "
    "WHERE e.kind = 'SYMBOL_REUSE' AND r.listing_id = %s AND r.value = %s"
)
