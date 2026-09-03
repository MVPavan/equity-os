"""The two source adapters of the entity identity map, both reading disk only.

S1 is a published ``screener-watchlist`` artifact: fetched, cross-checked
between the page and its export, and provenance-bound cell by cell. S2 is
``config/watchlist.yaml``: ten stocks a human pinned by hand. The difference is
not cosmetic — S1 is evidence and S2 is an assertion — so S2's values are
anchored ``CONFIG_PIN``, which the fact store bars outright.

Each adapter binds every value it emits to the file it read, by sha256. The
retrieval time comes from the file's CONTENT — the artifact's own recorded
retrieval time — or from a stamp the caller supplies, and never from filesystem
metadata. An mtime is restamped by any clone or checkout, so deriving from it
would mean CI could never byte-match a developer's build over identical bytes,
which is exactly the diff EM-11 exists to make meaningful. A source that records
no retrieval time of its own gets :data:`UNRECORDED_RETRIEVAL`, a sentinel that
says so rather than inventing a plausible-looking timestamp.

Neither adapter opens a socket, and neither writes to what it read.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from fundamentals.api.watchlist_config import StockConfig, load_watchlist_config
from fundamentals.contracts.entity_identity import (
    IdentifierNamespace,
    IncompleteEvidenceError,
    SourceAssertion,
    SourceRecord,
    UnkeyableRecordError,
)
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.ingest.screener_watchlist_models import (
    WatchlistArtifact,
    WatchlistOutcome,
    WatchlistRow,
)

S2_SOURCE_ID = "watchlist-config"

# The stamp used when a source records no retrieval time of its own. A config
# file records none by nature, and an artifact published without value cells
# carries none either. Saying "unrecorded" in one recognisable way beats either
# inventing a time or reading one off the filesystem.
UNRECORDED_RETRIEVAL = datetime(1970, 1, 1, tzinfo=UTC)

# The artifact JSON has no columns and no delimited records, so its values are
# addressed as a location inside a published JSON document: the member list is
# the island, the serial number is the row and the artifact's own field name is
# the column. This anchor kind also BARS ``column_index``, so no ordinal can be
# fabricated for a position the file does not have.
_S1_ISLAND_ID = "screener-watchlist-artifact"
_S1_TABLE_KEY = "rows"

_INCOMPLETE_ARTIFACT = (
    "watchlist artifact {path} published outcome {outcome!r}, not {expected!r}: a run "
    "that stopped short records no membership, and reading it as evidence would "
    "report every pin uncovered and call the map clean"
)
_PIN_WITHOUT_SYMBOL = (
    "pinned stock {name!r} carries no nse_symbol: the config addresses every stock "
    "by symbol, so nothing identifies this row or anchors its pins"
)

_ISIN_FIELD = "isin_code"
_NSE_FIELD = "nse_code"
_BSE_FIELD = "bse_code"
_SLUG_FIELD = "slug"
_COMPANY_ID_FIELD = "data_row_company_id"

# The five namespaces the watchlist artifact carries, in the order their columns
# are addressed. It carries no Tijori namespace whatsoever, which is a statement
# about our coverage rather than about the company.
_S1_COLUMNS: tuple[tuple[IdentifierNamespace, str], ...] = (
    (IdentifierNamespace.ISIN, _ISIN_FIELD),
    (IdentifierNamespace.NSE_SYMBOL, _NSE_FIELD),
    (IdentifierNamespace.BSE_SCRIP, _BSE_FIELD),
    (IdentifierNamespace.SCREENER_SLUG, _SLUG_FIELD),
    (IdentifierNamespace.SCREENER_COMPANY_ID, _COMPANY_ID_FIELD),
)

_PIN_ISIN_FIELD = "isin"
_PIN_NSE_FIELD = "nse_symbol"
_PIN_BSE_FIELD = "bse_scrip"
_PIN_SCREENER_SLUG_FIELD = "screener_slug"
_PIN_SCREENER_COMPANY_ID_FIELD = "screener_company_id"
_PIN_TIJORI_SLUG_FIELD = "tijori_slug"
_PIN_TIJORI_COMPANY_ID_FIELD = "tijori_company_id"

# The namespaces every pinned stock carries a field for. ``isin`` is absent by
# design: the field defaults to null and no stock populates it, so an unpinned
# ISIN is "no source looked", never "the config says there is none".
_S2_FIELDS: tuple[tuple[IdentifierNamespace, str], ...] = (
    (IdentifierNamespace.NSE_SYMBOL, _PIN_NSE_FIELD),
    (IdentifierNamespace.BSE_SCRIP, _PIN_BSE_FIELD),
    (IdentifierNamespace.SCREENER_SLUG, _PIN_SCREENER_SLUG_FIELD),
    (IdentifierNamespace.SCREENER_COMPANY_ID, _PIN_SCREENER_COMPANY_ID_FIELD),
    (IdentifierNamespace.TIJORI_SLUG, _PIN_TIJORI_SLUG_FIELD),
    (IdentifierNamespace.TIJORI_COMPANY_ID, _PIN_TIJORI_COMPANY_ID_FIELD),
)


def load_s1_records(
    path: Path, *, retrieved_at: datetime | None = None
) -> tuple[SourceRecord, ...]:
    """Read one ``screener-watchlist`` artifact into one source record per member.

    An artifact that did not publish a complete result is refused rather than
    read for its rows. ``INCOMPLETE`` is a first-class outcome precisely so a
    capped or stale fetch cannot pass as complete, and a consumer that iterated
    its empty membership would turn a failed acquisition into a clean map.
    """
    payload = path.read_bytes()
    artifact = WatchlistArtifact.model_validate_json(payload)
    if artifact.outcome is not WatchlistOutcome.RESULTS:
        raise IncompleteEvidenceError(
            _INCOMPLETE_ARTIFACT.format(
                path=path,
                outcome=artifact.outcome.value,
                expected=WatchlistOutcome.RESULTS.value,
            )
        )
    stamp = retrieved_at if retrieved_at is not None else _recorded_retrieval(artifact)
    digest = hashlib.sha256(payload).hexdigest()
    return tuple(
        _s1_record(row, source_id=artifact.source_id, digest=digest, retrieved_at=stamp)
        for row in artifact.rows
    )


def load_s2_records(
    path: Path, *, retrieved_at: datetime | None = None
) -> tuple[SourceRecord, ...]:
    """Read ``watchlist.yaml`` into one source record per hand-pinned stock.

    A YAML config records no retrieval time of its own, so without a caller's
    stamp every pin is marked :data:`UNRECORDED_RETRIEVAL`.
    """
    config = load_watchlist_config(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    stamp = retrieved_at if retrieved_at is not None else UNRECORDED_RETRIEVAL
    return tuple(_s2_record(stock, digest=digest, retrieved_at=stamp) for stock in config.stocks)


def _recorded_retrieval(artifact: WatchlistArtifact) -> datetime:
    """The earliest retrieval time the artifact records against its own cells.

    Derived from content, so two builds over identical bytes agree however the
    file got onto the disk. An artifact carrying no value cells records no time
    at all, and says so rather than borrowing the filesystem's.
    """
    stamps = [cell.provenance.retrieved_at for row in artifact.rows for cell in row.cells]
    return min(stamps) if stamps else UNRECORDED_RETRIEVAL


def _s1_record(
    row: WatchlistRow, *, source_id: str, digest: str, retrieved_at: datetime
) -> SourceRecord:
    """One watchlist member's identity, every field bound to the artifact record."""
    company = row.company
    stated: dict[str, str | None] = {
        _ISIN_FIELD: company.isin_code,
        _NSE_FIELD: company.nse_code,
        _BSE_FIELD: company.bse_code,
        _SLUG_FIELD: company.slug,
        _COMPANY_ID_FIELD: str(company.data_row_company_id),
    }
    assertions: list[SourceAssertion] = []
    absent: list[IdentifierNamespace] = []
    for namespace, field in _S1_COLUMNS:
        value = (stated[field] or "").strip()
        if not value:
            absent.append(namespace)
            continue
        assertions.append(
            SourceAssertion(
                namespace=namespace,
                value=value,
                provenance=Provenance(
                    source_id=source_id,
                    file_sha256=digest,
                    anchor_type=SourceAnchorType.JSON_ISLAND,
                    island_id=_S1_ISLAND_ID,
                    table_key=_S1_TABLE_KEY,
                    row_label=str(row.serial_number),
                    column_label=field,
                    retrieved_at=retrieved_at,
                ),
                verified=True,
            )
        )
    return SourceRecord(
        source_id=source_id,
        display_name=company.display_name,
        assertions=tuple(assertions),
        reported_absent=tuple(absent),
    )


def _s2_record(stock: StockConfig, *, digest: str, retrieved_at: datetime) -> SourceRecord:
    """One pinned stock's identifiers, each anchored to the config line that holds it."""
    identifiers = stock.identifiers
    if not identifiers.nse_symbol.strip():
        raise UnkeyableRecordError(_PIN_WITHOUT_SYMBOL.format(name=stock.name))
    stated: dict[str, str | None] = {
        _PIN_NSE_FIELD: identifiers.nse_symbol,
        _PIN_BSE_FIELD: identifiers.bse_scrip,
        _PIN_SCREENER_SLUG_FIELD: identifiers.screener_slug,
        _PIN_SCREENER_COMPANY_ID_FIELD: str(identifiers.screener_company_id),
        _PIN_TIJORI_SLUG_FIELD: identifiers.tijori_slug,
        _PIN_TIJORI_COMPANY_ID_FIELD: str(identifiers.tijori_company_id),
    }
    unconfirmed = set(identifiers.needs_verification)
    assertions: list[SourceAssertion] = []
    absent: list[IdentifierNamespace] = []
    for namespace, field in _S2_FIELDS:
        value = (stated[field] or "").strip()
        if not value:
            absent.append(namespace)
            continue
        assertions.append(
            _pin_assertion(
                namespace=namespace,
                field=field,
                value=value,
                symbol=identifiers.nse_symbol,
                digest=digest,
                retrieved_at=retrieved_at,
                verified=field not in unconfirmed,
            )
        )
    pinned_isin = (identifiers.isin or "").strip()
    if pinned_isin:
        assertions.append(
            _pin_assertion(
                namespace=IdentifierNamespace.ISIN,
                field=_PIN_ISIN_FIELD,
                value=pinned_isin,
                symbol=identifiers.nse_symbol,
                digest=digest,
                retrieved_at=retrieved_at,
                verified=_PIN_ISIN_FIELD not in unconfirmed,
            )
        )
    return SourceRecord(
        source_id=S2_SOURCE_ID,
        display_name=stock.name,
        assertions=tuple(assertions),
        reported_absent=tuple(absent),
    )


def _pin_assertion(
    *,
    namespace: IdentifierNamespace,
    field: str,
    value: str,
    symbol: str,
    digest: str,
    retrieved_at: datetime,
    verified: bool,
) -> SourceAssertion:
    """One hand-pinned identifier, addressed by the symbol and the field name.

    The anchor is ``CONFIG_PIN`` because no other kind describes a value a human
    typed into a YAML file, and an anchor that named a page or an export would
    make the retrieval procedure a lie.
    """
    return SourceAssertion(
        namespace=namespace,
        value=value,
        provenance=Provenance(
            source_id=S2_SOURCE_ID,
            file_sha256=digest,
            anchor_type=SourceAnchorType.CONFIG_PIN,
            row_label=symbol,
            column_label=field,
            retrieved_at=retrieved_at,
        ),
        verified=verified,
    )
