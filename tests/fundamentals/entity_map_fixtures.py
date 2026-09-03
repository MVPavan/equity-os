"""Synthetic fixtures for the entity identity map acceptance tests (``eqos-kx4.4``).

Nothing here is captured. Every company name, slug, NSE symbol, BSE scrip and
numeric id below is invented, and no identifier of a real listed company appears
in this file. ISINs are valid **by construction**: :func:`isin` computes the ISO
6166 check digit for a synthetic 11-character body, so a fixture is never
accidentally valid nor accidentally invalid, and the deliberately-broken ISINs
are broken in exactly one way each.

The entity-map modules are reached through :class:`_Module` rather than imported
at the top. These tests are written before the implementation exists, and a
top-level import would collapse every independently red test into a single
collection error — the opposite of a per-rule red proof.

Fixtures are self-checking: the check-digit helper proves at import time that it
discriminates (a one-character mutation of a body changes the digit), because a
helper that silently returned a constant would make every EM-01 test vacuous.
"""

from __future__ import annotations

import hashlib
import importlib
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.ingest.screener_watchlist_models import (
    WatchlistArtifact,
    WatchlistColumn,
    WatchlistCompany,
    WatchlistCrossCheck,
    WatchlistOutcome,
    WatchlistRow,
)


class _Module:
    """Deferred attribute access into an entity-map module.

    Every lookup happens at call time, so a module that does not exist yet fails
    the one test that asked for it instead of the whole file.
    """

    def __init__(self, name: str) -> None:
        self._name = name

    def __getattr__(self, attribute: str) -> Any:
        """Resolve one public name out of the named module."""
        return getattr(importlib.import_module(self._name), attribute)


contracts = _Module("fundamentals.contracts.entity_identity")
entity_map = _Module("fundamentals.entity.entity_map")
sources = _Module("fundamentals.entity.entity_map_sources")

# ---------------------------------------------------------------------------
# ISO 6166 check digits
# ---------------------------------------------------------------------------

ISIN_SHAPE = r"IN[EF9][A-Z0-9]{8}[0-9]"
_ISIN_BODY_LENGTH = 11
# ord("A") - 10: the base-36 expansion EM-01 names.
_ALPHABET_OFFSET = 55
_LUHN_MODULUS = 10


def _luhn_check_digit(digits: str) -> int:
    """The Luhn check digit for a payload of decimal digits."""
    total = 0
    for position, character in enumerate(reversed(digits)):
        value = int(character)
        if position % 2 == 0:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return (_LUHN_MODULUS - total % _LUHN_MODULUS) % _LUHN_MODULUS


def isin_check_digit(body: str) -> str:
    """The ISO 6166 check digit for an 11-character ISIN body."""
    if len(body) != _ISIN_BODY_LENGTH:
        raise ValueError(f"an ISIN body is {_ISIN_BODY_LENGTH} characters, got {body!r}")
    expanded = "".join(
        character if character.isdigit() else str(ord(character) - _ALPHABET_OFFSET)
        for character in body
    )
    return str(_luhn_check_digit(expanded))


def isin(body: str) -> str:
    """A synthetic ISIN: the given body followed by its computed check digit."""
    return f"{body}{isin_check_digit(body)}"


def isin_with_wrong_check_digit(body: str) -> str:
    """A correctly shaped synthetic ISIN whose final digit is deliberately wrong."""
    wrong = (int(isin_check_digit(body)) + 1) % _LUHN_MODULUS
    return f"{body}{wrong}"


def _self_check_the_check_digit() -> None:
    """Prove the helper discriminates before any test relies on it."""
    body = "INE100A0101"
    mutated = f"{body[:-1]}2"
    if isin_check_digit(body) == isin_check_digit(mutated):
        raise AssertionError("the ISIN check digit helper does not react to a mutated body")
    if isin(body)[:-1] != body or len(isin(body)) != _ISIN_BODY_LENGTH + 1:
        raise AssertionError("the ISIN helper does not append exactly one check digit")
    if isin_with_wrong_check_digit(body) == isin(body):
        raise AssertionError("the wrong-check-digit helper produced a valid ISIN")


_self_check_the_check_digit()

# ---------------------------------------------------------------------------
# The synthetic corpus
# ---------------------------------------------------------------------------

S1_SOURCE_ID = "screener-watchlist"
S2_SOURCE_ID = "watchlist-config"

ALPHA_BODY = "INE100A0101"
BRAVO_BODY = "INE200B0101"
CHARLIE_BODY = "INE300C0101"
DELTA_BODY = "INE400D0101"

ALPHA_ISIN = isin(ALPHA_BODY)
BRAVO_ISIN = isin(BRAVO_BODY)
CHARLIE_ISIN = isin(CHARLIE_BODY)
DELTA_ISIN = isin(DELTA_BODY)

# Shape-invalid (third character is not E/F/9) but carrying a correctly computed
# check digit, so only the shape half of EM-01 can refuse it.
WRONG_SHAPE_BODY = "INA100A0101"
WRONG_SHAPE_ISIN = isin(WRONG_SHAPE_BODY)

# Shape-valid but the twelfth character is wrong, so only the check-digit half
# of EM-01 can refuse it.
WRONG_DIGIT_BODY = "INE900Z0101"
WRONG_DIGIT_ISIN = isin_with_wrong_check_digit(WRONG_DIGIT_BODY)

ALPHA_NSE = "ALPHAFX"
BRAVO_NSE = "BRAVOFX"
CHARLIE_NSE = "CHARLIEFX"
DELTA_NSE = "DELTAFX"
ZULU_NSE = "ZULUFX"

ALPHA_BSE = "590001"
BRAVO_BSE = "590002"
CHARLIE_BSE = "590003"
DELTA_BSE = "590004"
ORPHAN_BSE = "590007"
SHARED_NSE = "SHAREDFX"
SHARED_BSE = "590009"

ALPHA_NAME = "Fixture Alpha Industries Limited"
BRAVO_NAME = "Fixture Bravo Chemicals Limited"
SHARED_NAME = "Fixture Shared Name Limited"

FIXTURE_SHA256 = hashlib.sha256(b"entity-map-fixture-bytes").hexdigest()
RETRIEVED_AT = datetime(2026, 9, 3, 6, 0, tzinfo=UTC)
_TABLE_ID = "entity-map-fixture"


def sha256_of(path: Path) -> str:
    """The sha256 of a file on disk, as the provenance field records it."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def provenance(
    source_id: str,
    *,
    file_sha256: str = FIXTURE_SHA256,
    row_path: str = "0",
    column_label: str = "identifier",
    column_index: int = 0,
) -> Provenance:
    """A valid synthetic :class:`Provenance` naming a record and a field."""
    return Provenance(
        source_id=source_id,
        file_sha256=file_sha256,
        anchor_type=SourceAnchorType.CSV_RECORD,
        table_id=_TABLE_ID,
        row_path=row_path,
        column_label=column_label,
        column_index=column_index,
        retrieved_at=RETRIEVED_AT,
    )


def namespace(name: str) -> Any:
    """One :class:`IdentifierNamespace` member, resolved at call time."""
    return getattr(contracts.IdentifierNamespace, name)


ISIN_NS = "ISIN"
NSE_NS = "NSE_SYMBOL"
BSE_NS = "BSE_SCRIP"
SCREENER_SLUG_NS = "SCREENER_SLUG"
SCREENER_COMPANY_ID_NS = "SCREENER_COMPANY_ID"
TIJORI_SLUG_NS = "TIJORI_SLUG"
TIJORI_COMPANY_ID_NS = "TIJORI_COMPANY_ID"


def record(
    *,
    source_id: str = S1_SOURCE_ID,
    display_name: str | None = None,
    isin_code: str | None = None,
    nse: str | None = None,
    bse: str | None = None,
    screener_slug: str | None = None,
    screener_company_id: int | None = None,
    tijori_slug: str | None = None,
    tijori_company_id: int | None = None,
    unverified: tuple[str, ...] = (),
    reported_absent: tuple[str, ...] = (),
    row: str = "0",
) -> Any:
    """One source's assertions about one security, as the map ingests them.

    ``unverified`` names the namespaces this source flags as not yet confirmed
    (EM-07); every other supplied value is asserted as verified.

    ``reported_absent`` names the namespaces this source *carried* and published
    as null — the S1 export's empty ``NSE Code`` cell, say. It is what separates
    ``SOURCE_REPORTED_ABSENT`` from ``NOT_SUPPLIED`` under A6, and a namespace
    named here must not also be given a value.
    """
    supplied: tuple[tuple[str, str | None], ...] = (
        (ISIN_NS, isin_code),
        (NSE_NS, nse),
        (BSE_NS, bse),
        (SCREENER_SLUG_NS, screener_slug),
        (SCREENER_COMPANY_ID_NS, None if screener_company_id is None else str(screener_company_id)),
        (TIJORI_SLUG_NS, tijori_slug),
        (TIJORI_COMPANY_ID_NS, None if tijori_company_id is None else str(tijori_company_id)),
    )
    assertions = tuple(
        contracts.SourceAssertion(
            namespace=namespace(name),
            value=value,
            provenance=provenance(
                source_id,
                row_path=row,
                column_label=name.lower(),
                column_index=index,
            ),
            verified=name not in unverified,
        )
        for index, (name, value) in enumerate(supplied)
        if value is not None
    )
    supplied_names = {name for name, value in supplied if value is not None}
    if supplied_names & set(reported_absent):
        raise ValueError("a namespace cannot be both supplied and reported absent")
    return contracts.SourceRecord(
        source_id=source_id,
        display_name=display_name,
        assertions=assertions,
        reported_absent=tuple(namespace(name) for name in reported_absent),
    )


def build(*records: Any) -> Any:
    """Build the entity map from the given source records."""
    return entity_map.build_entity_map(records)


def by_key(built: Any) -> dict[str, Any]:
    """The built map's entities, indexed by their published key."""
    return {entity.key: entity for entity in built.entities}


def coverage(entity: Any, name: str) -> Any:
    """One namespace's coverage record on an entity, by namespace name.

    Raises ``KeyError`` when the entity publishes no record for the namespace,
    which is itself the EM-12 failure (absence never means "unknown").
    """
    published = {covered.namespace: covered for covered in entity.namespaces}
    return published[namespace(name)]


def values_of(entity: Any, name: str) -> tuple[str, ...]:
    """The identifier values an entity holds in one namespace, in stored order."""
    return tuple(held.value for held in coverage(entity, name).values)


def source_ids_of(entity: Any, name: str) -> tuple[frozenset[str], ...]:
    """The provenance source ids behind each value an entity holds in a namespace."""
    return tuple(
        frozenset(mark.source_id for mark in held.provenances)
        for held in coverage(entity, name).values
    )


# ---------------------------------------------------------------------------
# S1 — a ``screener-watchlist`` artifact on disk
# ---------------------------------------------------------------------------


class Listing(BaseModel):
    """One synthetic member of a synthetic watchlist artifact."""

    model_config = ConfigDict(frozen=True)

    company_id: int
    slug: str | None
    display_name: str
    isin_code: str
    nse_code: str | None
    bse_code: str | None


ALPHA_LISTING = Listing(
    company_id=9100001,
    slug=ALPHA_NSE,
    display_name=ALPHA_NAME,
    isin_code=ALPHA_ISIN,
    nse_code=ALPHA_NSE,
    bse_code=ALPHA_BSE,
)
BRAVO_LISTING = Listing(
    company_id=9100002,
    slug=BRAVO_NSE,
    display_name=BRAVO_NAME,
    isin_code=BRAVO_ISIN,
    nse_code=BRAVO_NSE,
    bse_code=BRAVO_BSE,
)

_COLUMN = WatchlistColumn(csv_field_index=0, label="Sales", html_label="Sales")


def _cross_check(listings: Sequence[Listing]) -> WatchlistCrossCheck:
    """A minimal passing cross-check record for a synthetic artifact."""
    return WatchlistCrossCheck(
        html_source_url="https://fixture.invalid/watchlist/",
        export_source_url="https://fixture.invalid/api/export/screen/",
        html_http_status=200,
        export_http_status=200,
        html_sha256=FIXTURE_SHA256,
        export_sha256=FIXTURE_SHA256,
        html_byte_count=1,
        export_byte_count=1,
        export_content_type="text/csv",
        export_content_disposition=None,
        html_row_count=len(listings),
        csv_row_count=len(listings),
        compared_cell_count=0,
    )


def watchlist_artifact(listings: Sequence[Listing]) -> WatchlistArtifact:
    """A published-shape ``screener-watchlist`` artifact over synthetic members."""
    rows = tuple(
        WatchlistRow(
            serial_number=index + 1,
            company=WatchlistCompany(
                data_row_company_id=listing.company_id,
                slug=listing.slug,
                display_name=listing.display_name,
                consolidated=True,
                bse_code=listing.bse_code,
                nse_code=listing.nse_code,
                isin_code=listing.isin_code,
                industry_group=None,
                industry=None,
            ),
        )
        for index, listing in enumerate(listings)
    )
    return WatchlistArtifact(
        outcome=WatchlistOutcome.RESULTS,
        columns=(_COLUMN,),
        rows=rows,
        cross_check=_cross_check(listings),
    )


def write_s1_artifact(directory: Path, listings: Sequence[Listing]) -> Path:
    """Write a synthetic S1 artifact JSON and return its path."""
    path = directory / "screener_watchlist.json"
    path.write_text(watchlist_artifact(listings).model_dump_json(indent=2), encoding="utf-8")
    if not path.read_text(encoding="utf-8").strip():
        raise AssertionError("the S1 fixture wrote an empty artifact")
    return path


# ---------------------------------------------------------------------------
# S2 — a ``watchlist.yaml`` config on disk
# ---------------------------------------------------------------------------


class Pin(BaseModel):
    """One synthetic hand-pinned stock, as ``config/watchlist.yaml`` shapes it."""

    model_config = ConfigDict(frozen=True)

    name: str
    nse_symbol: str
    bse_scrip: str
    isin: str | None = None
    screener_slug: str
    screener_company_id: int
    screener_warehouse_id_standalone: int
    tijori_slug: str
    tijori_company_id: int
    needs_verification: tuple[str, ...] = ()


ALPHA_PIN = Pin(
    name=ALPHA_NAME,
    nse_symbol=ALPHA_NSE,
    bse_scrip=ALPHA_BSE,
    screener_slug=ALPHA_NSE,
    screener_company_id=9100001,
    screener_warehouse_id_standalone=9200001,
    tijori_slug="fixture-alpha-industries",
    tijori_company_id=9300001,
)
DELTA_PIN = Pin(
    name="Fixture Delta Precision Limited",
    nse_symbol=DELTA_NSE,
    bse_scrip=DELTA_BSE,
    screener_slug=DELTA_NSE,
    screener_company_id=9100004,
    screener_warehouse_id_standalone=9200004,
    tijori_slug="fixture-delta-precision",
    tijori_company_id=9300004,
    needs_verification=("bse_scrip",),
)

_QUARTER = {
    "label": "Q3FY25",
    "period_start": "2024-10-01",
    "period_end": "2024-12-31",
    "knowledge_cutoff": "2025-02-15T00:00:00Z",
    "filing_taxonomy": "in-bse-fin",
}


def _pin_document(pin: Pin) -> dict[str, Any]:
    """One stock entry of the synthetic watchlist YAML."""
    identifiers: dict[str, Any] = {
        "nse_symbol": pin.nse_symbol,
        "bse_scrip": pin.bse_scrip,
    }
    # Omitted entirely when unpinned, exactly as every stock in the committed
    # config omits it: the key is absent from the document, not present-and-null.
    if pin.isin is not None:
        identifiers["isin"] = pin.isin
    identifiers.update(
        {
            "screener_slug": pin.screener_slug,
            "screener_company_id": pin.screener_company_id,
            "screener_warehouse_id_consolidated": None,
            "screener_warehouse_id_standalone": pin.screener_warehouse_id_standalone,
            "tijori_slug": pin.tijori_slug,
            "tijori_company_id": pin.tijori_company_id,
            "us_listed": False,
            "needs_verification": list(pin.needs_verification),
        }
    )
    return {
        "name": pin.name,
        "domain": "Fixture Domain",
        "wave": "Wave-1",
        "identifiers": identifiers,
        "quarter": dict(_QUARTER),
    }


def write_s2_config(directory: Path, pins: Sequence[Pin]) -> Path:
    """Write a synthetic ``watchlist.yaml`` and return its path."""
    path = directory / "watchlist.yaml"
    document = {
        "raw_dir": "data/raw/fixture-watchlist",
        "stocks": [_pin_document(pin) for pin in pins],
    }
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    reloaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if len(reloaded["stocks"]) != len(pins):
        raise AssertionError("the S2 fixture did not round-trip every pinned stock")
    return path
