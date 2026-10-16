"""Seed reporting entities, securities and listings from evidenced identity input.

Two inputs are accepted. An issuer identity file (``config/identity/<issuer>.yaml``)
cites every identity field to a retained capture and also seeds the entity's
basis status and fiscal-year-end setting. An entity map seeds only the
identifiers it holds verified and unconflicted; everything else is listed in
the report, never guessed.

Every write is insert-on-conflict returning the existing row, so internal ids
are stable across re-seeds and a repeat seed inserts nothing.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import LiteralString

import psycopg
import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from fundamentals.contracts.basis_status import BasisStatus
from fundamentals.contracts.entity_identity import (
    CoverageStatus,
    Entity,
    EntityMap,
    IdentifierNamespace,
)

MARKET_IN = "IN"
SHARE_CLASS_EQUITY = "EQUITY"
ENTITY_MAP_LABEL = "entity-map"
# Identity fields that must each carry a citation. ``entity_key`` is our own key
# and ``share_class`` our own label, so neither is a filed fact to cite.
CITED_FIELDS: frozenset[str] = frozenset(
    {"display_name", "isin", "nse_symbol", "bse_scrip", "basis_status", "fiscal_year_end_month"}
)
_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_UNCITED = "identity input {path} has fields without a citation: {fields}"
_UNKNOWN_CITATION = "identity input {path} cites unknown fields: {fields}"
_CITATION_WITHOUT_ANCHOR = "a citation needs a native field or pages: {field}"


class EvidenceInputKind(StrEnum):
    """What kind of file an ``evidence_inputs`` row records."""

    ENTITY_MAP = "ENTITY_MAP"
    ISSUER_IDENTITY = "ISSUER_IDENTITY"
    ISSUER_CONFIG = "ISSUER_CONFIG"
    DISCOVERY = "DISCOVERY"


class ListingVenue(StrEnum):
    """The exchange a listing row names."""

    NSE = "NSE"
    BSE = "BSE"


class SettingKey(StrEnum):
    """Which evidenced per-entity setting a ``settings_records`` row holds."""

    FISCAL_YEAR_END_MONTH = "FISCAL_YEAR_END_MONTH"
    PDF_PRINTED_UNIT = "PDF_PRINTED_UNIT"
    PDF_LAYOUT = "PDF_LAYOUT"
    DOCUMENT_LOCATION = "DOCUMENT_LOCATION"
    PRESENTATION_CURRENCY = "PRESENTATION_CURRENCY"
    REPORTING_FRAMEWORK = "REPORTING_FRAMEWORK"
    FILING_ROUNDING_LEVEL = "FILING_ROUNDING_LEVEL"


class IdentityInputError(ValueError):
    """An identity input file is uncited or cites something it does not hold."""


class IdentityCitation(BaseModel):
    """Where in a retained capture one identity field is printed."""

    model_config = ConfigDict(frozen=True)

    field: str
    capture_sha256: str = Field(pattern=_SHA256_PATTERN)
    native_field: str | None = None
    context_ref: str | None = None
    pages: tuple[int, ...] = ()

    @model_validator(mode="after")
    def _anchored(self) -> IdentityCitation:
        """A citation names an XBRL element or PDF pages; a bare hash points nowhere."""
        if self.native_field is None and not self.pages:
            raise ValueError(_CITATION_WITHOUT_ANCHOR.format(field=self.field))
        return self


class IssuerIdentityInput(BaseModel):
    """One issuer's evidenced identity, as loaded from its identity file."""

    model_config = ConfigDict(frozen=True)

    entity_key: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    isin: str = Field(min_length=1)
    share_class: str = Field(min_length=1)
    nse_symbol: str = Field(min_length=1)
    bse_scrip: str = Field(min_length=1)
    basis_status: BasisStatus
    fiscal_year_end_month: int = Field(ge=1, le=12)
    citations: tuple[IdentityCitation, ...]
    content_sha256: str = Field(pattern=_SHA256_PATTERN)


class IdentitySeedReport(BaseModel):
    """Ids the seed resolved and how many rows it inserted versus found."""

    model_config = ConfigDict(frozen=True)

    entity_ids: Mapping[str, int]
    evidence_input_id: int
    inserted: int
    existing: int
    skipped: tuple[str, ...] = ()


def load_issuer_identity(path: Path) -> IssuerIdentityInput:
    """Load an issuer identity file, refusing any identity field without a citation."""
    body = path.read_bytes()
    data = yaml.safe_load(body)
    identity = IssuerIdentityInput.model_validate(
        {**data, "content_sha256": hashlib.sha256(body).hexdigest()}
    )
    cited = {citation.field for citation in identity.citations}
    uncited = CITED_FIELDS - cited
    if uncited:
        raise IdentityInputError(_UNCITED.format(path=path, fields=", ".join(sorted(uncited))))
    unknown = cited - CITED_FIELDS
    if unknown:
        raise IdentityInputError(
            _UNKNOWN_CITATION.format(path=path, fields=", ".join(sorted(unknown)))
        )
    return identity


def seed_issuer_identity(
    conn: psycopg.Connection, identity: IssuerIdentityInput
) -> IdentitySeedReport:
    """Seed one issuer's entity, security, listings, basis status and fiscal-year end."""
    tally = _Tally()
    with conn.transaction():
        input_id = _evidence_input(
            conn,
            tally,
            EvidenceInputKind.ISSUER_IDENTITY,
            identity.entity_key,
            identity.content_sha256,
        )
        entity_id = _entity(conn, tally, identity.entity_key, identity.display_name, input_id)
        security_id = _security(
            conn, tally, entity_id, identity.share_class, identity.isin, input_id
        )
        _listing(conn, tally, security_id, ListingVenue.NSE, identity.nse_symbol, input_id)
        _listing(conn, tally, security_id, ListingVenue.BSE, identity.bse_scrip, input_id)
        tally.record(
            conn,
            _INSERT_BASIS_STATUS,
            (entity_id, identity.basis_status.value, input_id),
            _SELECT_BASIS_STATUS,
            (entity_id, identity.basis_status.value, input_id),
        )
        month = str(identity.fiscal_year_end_month)
        tally.record(
            conn,
            _INSERT_SETTING,
            (entity_id, SettingKey.FISCAL_YEAR_END_MONTH.value, month, input_id),
            _SELECT_SETTING,
            (entity_id, SettingKey.FISCAL_YEAR_END_MONTH.value, month, input_id),
        )
    return IdentitySeedReport(
        entity_ids={identity.entity_key: entity_id},
        evidence_input_id=input_id,
        inserted=tally.inserted,
        existing=tally.existing,
    )


def seed_identity(
    conn: psycopg.Connection, entity_map: EntityMap, *, source_sha256: str
) -> IdentitySeedReport:
    """Seed every unconflicted entity and its verified identifiers from an entity map.

    A conflicted entity is skipped whole; an identifier that is unverified or
    conflicted is skipped alone. Both are named in ``skipped`` as ``key`` or
    ``key:NAMESPACE``.
    """
    tally = _Tally()
    skipped: list[str] = []
    entity_ids: dict[str, int] = {}
    with conn.transaction():
        input_id = _evidence_input(
            conn, tally, EvidenceInputKind.ENTITY_MAP, ENTITY_MAP_LABEL, source_sha256
        )
        for entity in entity_map.entities:
            if entity.conflicted:
                skipped.append(entity.key)
                continue
            isin = _verified(entity, IdentifierNamespace.ISIN, skipped)
            nse = _verified(entity, IdentifierNamespace.NSE_SYMBOL, skipped)
            bse = _verified(entity, IdentifierNamespace.BSE_SCRIP, skipped)
            display_name = entity.display_names[0] if entity.display_names else entity.key
            entity_id = _entity(conn, tally, entity.key, display_name, input_id)
            security_id = _security(conn, tally, entity_id, SHARE_CLASS_EQUITY, isin, input_id)
            if nse is not None:
                _listing(conn, tally, security_id, ListingVenue.NSE, nse, input_id)
            if bse is not None:
                _listing(conn, tally, security_id, ListingVenue.BSE, bse, input_id)
            entity_ids[entity.key] = entity_id
    return IdentitySeedReport(
        entity_ids=entity_ids,
        evidence_input_id=input_id,
        inserted=tally.inserted,
        existing=tally.existing,
        skipped=tuple(skipped),
    )


def _verified(entity: Entity, namespace: IdentifierNamespace, skipped: list[str]) -> str | None:
    """The namespace's one verified value, or ``None`` (listing anything held but unusable)."""
    coverage = entity.coverage(namespace)
    if coverage.status is CoverageStatus.KNOWN:
        verified = [held.value for held in coverage.values if held.verified]
        if len(verified) == 1:
            return verified[0]
    if coverage.values:
        skipped.append(f"{entity.key}:{namespace.value}")
    return None


class _Tally:
    """Counts rows a seed inserted versus rows it found already stored."""

    def __init__(self) -> None:
        self.inserted = 0
        self.existing = 0

    def record(
        self,
        conn: psycopg.Connection,
        insert: LiteralString,
        insert_params: tuple[object, ...],
        select: LiteralString,
        select_params: tuple[object, ...],
    ) -> int:
        """Insert-on-conflict, falling back to the stored row's id."""
        row = conn.execute(insert, insert_params).fetchone()
        if row is not None:
            self.inserted += 1
            return int(row[0])
        stored = conn.execute(select, select_params).fetchone()
        if stored is None:
            raise LookupError(select)
        self.existing += 1
        return int(stored[0])


def _evidence_input(
    conn: psycopg.Connection, tally: _Tally, kind: EvidenceInputKind, label: str, sha256: str
) -> int:
    """The ``evidence_inputs`` row for one input file's content."""
    return tally.record(
        conn,
        _INSERT_EVIDENCE_INPUT,
        (kind.value, label, sha256),
        _SELECT_EVIDENCE_INPUT,
        (kind.value, sha256),
    )


def _entity(
    conn: psycopg.Connection, tally: _Tally, key: str, display_name: str, input_id: int
) -> int:
    """The ``reporting_entities`` row for one entity key."""
    return tally.record(
        conn,
        _INSERT_ENTITY,
        (key, MARKET_IN, display_name, input_id),
        _SELECT_ENTITY,
        (key,),
    )


def _security(
    conn: psycopg.Connection,
    tally: _Tally,
    entity_id: int,
    share_class: str,
    isin: str | None,
    input_id: int,
) -> int:
    """The ``securities`` row for one (entity, share class, ISIN)."""
    return tally.record(
        conn,
        _INSERT_SECURITY,
        (entity_id, isin, share_class, input_id),
        _SELECT_SECURITY,
        (entity_id, share_class, isin),
    )


def _listing(
    conn: psycopg.Connection,
    tally: _Tally,
    security_id: int,
    venue: ListingVenue,
    symbol: str,
    input_id: int,
) -> int:
    """The ``listings`` row for one venue code of a security."""
    return tally.record(
        conn,
        _INSERT_LISTING,
        (security_id, venue.value, symbol, input_id),
        _SELECT_LISTING,
        (venue.value, symbol, security_id),
    )


_INSERT_EVIDENCE_INPUT: LiteralString = (
    "INSERT INTO eqos.evidence_inputs (kind, label, content_sha256) VALUES (%s, %s, %s) "
    "ON CONFLICT (kind, content_sha256) DO NOTHING RETURNING id"
)
_SELECT_EVIDENCE_INPUT: LiteralString = (
    "SELECT id FROM eqos.evidence_inputs WHERE kind = %s AND content_sha256 = %s"
)
_INSERT_ENTITY: LiteralString = (
    "INSERT INTO eqos.reporting_entities (entity_key, market, display_name, evidence_input_id) "
    "VALUES (%s, %s, %s, %s) ON CONFLICT (entity_key) DO NOTHING RETURNING id"
)
_SELECT_ENTITY: LiteralString = "SELECT id FROM eqos.reporting_entities WHERE entity_key = %s"
_INSERT_SECURITY: LiteralString = (
    "INSERT INTO eqos.securities (entity_id, isin, share_class, evidence_input_id) "
    "VALUES (%s, %s, %s, %s) ON CONFLICT (entity_id, share_class, isin) DO NOTHING RETURNING id"
)
_SELECT_SECURITY: LiteralString = (
    "SELECT id FROM eqos.securities "
    "WHERE entity_id = %s AND share_class = %s AND isin IS NOT DISTINCT FROM %s"
)
_INSERT_LISTING: LiteralString = (
    "INSERT INTO eqos.listings (security_id, venue, symbol, evidence_input_id) "
    "VALUES (%s, %s, %s, %s) ON CONFLICT (venue, symbol, security_id) DO NOTHING RETURNING id"
)
_SELECT_LISTING: LiteralString = (
    "SELECT id FROM eqos.listings WHERE venue = %s AND symbol = %s AND security_id = %s"
)
_INSERT_BASIS_STATUS: LiteralString = (
    "INSERT INTO eqos.entity_basis_status (entity_id, basis_status, evidence_input_id) "
    "VALUES (%s, %s, %s) "
    "ON CONFLICT (entity_id, basis_status, evidence_input_id) DO NOTHING RETURNING id"
)
_SELECT_BASIS_STATUS: LiteralString = (
    "SELECT id FROM eqos.entity_basis_status "
    "WHERE entity_id = %s AND basis_status = %s AND evidence_input_id = %s"
)
_INSERT_SETTING: LiteralString = (
    "INSERT INTO eqos.settings_records (entity_id, setting_key, value_text, evidence_input_id) "
    "VALUES (%s, %s, %s, %s) "
    "ON CONFLICT (entity_id, setting_key, value_text, evidence_input_id) DO NOTHING RETURNING id"
)
_SELECT_SETTING: LiteralString = (
    "SELECT id FROM eqos.settings_records "
    "WHERE entity_id = %s AND setting_key = %s AND value_text = %s AND evidence_input_id = %s"
)
