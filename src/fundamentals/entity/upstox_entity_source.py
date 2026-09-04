"""The Upstox entity adapter: a retained instrument catalog read as identity evidence.

Reads a **parsed catalog artifact from disk** and emits one
:class:`~fundamentals.contracts.entity_identity.SourceRecord` per ISIN. It opens
no socket, matching the invariant the two existing adapters hold, so an
entity-map build stays offline and reproducible.

Three namespaces, all read from the row that states them and never from a name:
``ISIN`` from ``isin``, ``NSE_SYMBOL`` from ``trading_symbol`` on ``NSE_EQ``
rows, and ``BSE_SCRIP`` from ``exchange_token`` on ``BSE_EQ`` rows.

Assertions are marked ``verified``, which is load-bearing —
:meth:`EntityMap.lookup` gates on it. The justification is what the file is: a
self-describing current-state bulk export that publishes the ISIN and the
exchange code side by side on one row is itself the confirmation, within the
snapshot it describes. It says nothing about any earlier state, which is why
nothing here reaches the fact store.

**Nothing is ever reported absent.** "The source carried this column and
published nothing in it" is an assertion about the company, and the map treats
it as one — it conflicts with any other source that does assert a value, and a
conflicted entity is unreachable by lookup. This adapter cannot honestly make
that assertion: the catalog it reads is a *filtered* view retaining only
``NSE_EQ``/``EQ`` and ``BSE_EQ``/``A`` rows, so a security listed in another BSE
group is missing from our rows because we dropped it, not because the vendor was
silent. Saying "reported absent" there would state our filter as the vendor's
claim and would make correctly-pinned entities unreachable.

The suspended file emits nothing. It is retained evidence of suspension with no
code consumer, and a candidate-match report whose matches nobody may act on
would be a deliverable in search of a user.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from fundamentals.contracts.entity_identity import (
    IdentifierNamespace,
    IncompleteEvidenceError,
    SourceAssertion,
    SourceRecord,
)
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.ingest.upstox_instruments import (
    BSE_EQUITY_SEGMENT,
    NSE_EQUITY_SEGMENT,
    UpstoxInstrument,
    UpstoxInstrumentCatalog,
)
from fundamentals.ingest.upstox_source import AcquisitionOutcome, UpstoxSurface

UPSTOX_SOURCE_ID = "upstox"

_ISIN_FIELD = "isin"
_TRADING_SYMBOL_FIELD = "trading_symbol"
_EXCHANGE_TOKEN_FIELD = "exchange_token"

_INCOMPLETE_CATALOG = (
    "upstox instrument catalog {path} published outcome {outcome!r}, not {expected!r}: a "
    "run that drifted records no membership, and reading it as evidence would report "
    "every pin uncovered and call the map clean"
)
_NOT_A_LISTED_CATALOG = (
    "{path} is a suspended-instrument catalog; suspended rows emit no entity "
    "assertions, because a suspension is not a statement of current identity"
)


def load_upstox_records(
    path: Path, *, retrieved_at: datetime | None = None
) -> tuple[SourceRecord, ...]:
    """Read one retained instrument catalog into one source record per ISIN.

    A catalog that did not publish a complete result is refused rather than read
    for its rows, for the same reason the watchlist adapter refuses an
    ``INCOMPLETE`` artifact: a consumer that iterated an empty membership would
    turn a failed acquisition into a clean map.
    """
    catalog = UpstoxInstrumentCatalog.model_validate_json(path.read_bytes())
    if catalog.surface is not UpstoxSurface.INSTRUMENTS or not catalog.instruments:
        _refuse_non_listed(path, catalog)
    if catalog.outcome is not AcquisitionOutcome.OK:
        raise IncompleteEvidenceError(
            _INCOMPLETE_CATALOG.format(
                path=path,
                outcome=catalog.outcome.value,
                expected=AcquisitionOutcome.OK.value,
            )
        )
    stamp = retrieved_at if retrieved_at is not None else catalog.retrieved_at
    grouped = catalog.by_isin()
    return tuple(
        _record(grouped[isin], catalog=catalog, retrieved_at=stamp) for isin in sorted(grouped)
    )


def _refuse_non_listed(path: Path, catalog: UpstoxInstrumentCatalog) -> None:
    """Refuse anything that is not a listed-instrument catalog with rows.

    A suspended catalog validates against this model — the two share every field
    the header declares — so the refusal is explicit rather than left to a
    validation error that would not say why.
    """
    if catalog.surface is UpstoxSurface.INSTRUMENTS and catalog.instruments:
        return
    raise IncompleteEvidenceError(_NOT_A_LISTED_CATALOG.format(path=path))


def _record(
    rows: Sequence[UpstoxInstrument], *, catalog: UpstoxInstrumentCatalog, retrieved_at: datetime
) -> SourceRecord:
    """One issuer's identity, every value bound to the row that stated it.

    A dual-listed issuer arrives as several rows under one ISIN. That is one
    security stated twice, so it becomes one record — the ISIN asserted once
    from the first row, and each exchange code from the row that carries it.
    """
    first = rows[0]
    assertions = [
        _assertion(
            namespace=IdentifierNamespace.ISIN,
            value=first.isin,
            field=_ISIN_FIELD,
            row=first,
            catalog=catalog,
            retrieved_at=retrieved_at,
        )
    ]
    for namespace, segment, field in (
        (IdentifierNamespace.NSE_SYMBOL, NSE_EQUITY_SEGMENT, _TRADING_SYMBOL_FIELD),
        (IdentifierNamespace.BSE_SCRIP, BSE_EQUITY_SEGMENT, _EXCHANGE_TOKEN_FIELD),
    ):
        # No ``else`` branch reporting absence: see the module docstring. A
        # namespace we hold no row for is a namespace our own filter may have
        # emptied, which is "nobody looked", never "the vendor said none".
        assertions.extend(
            _assertion(
                namespace=namespace,
                value=getattr(row, field),
                field=field,
                row=row,
                catalog=catalog,
                retrieved_at=retrieved_at,
            )
            for row in rows
            if row.segment == segment
        )
    return SourceRecord(
        source_id=UPSTOX_SOURCE_ID,
        display_name=first.name,
        assertions=tuple(assertions),
    )


def _assertion(
    *,
    namespace: IdentifierNamespace,
    value: str,
    field: str,
    row: UpstoxInstrument,
    catalog: UpstoxInstrumentCatalog,
    retrieved_at: datetime,
) -> SourceAssertion:
    """One identifier, anchored to the API document and the row it was read from.

    ``API_DOCUMENT`` rather than ``JSON_ISLAND`` because the retrieval procedure
    is the documented GET, not a named block inside a fetched page — and because
    an API response may carry no identity field at all, leaving the request URL
    as the only binding. The row is addressed by its ``instrument_key``, which
    is the file's own durable handle.
    """
    return SourceAssertion(
        namespace=namespace,
        value=value,
        provenance=Provenance(
            source_id=UPSTOX_SOURCE_ID,
            file_sha256=catalog.content_sha256,
            anchor_type=SourceAnchorType.API_DOCUMENT,
            document_id=f"{UPSTOX_SOURCE_ID}:{catalog.surface.value}:{catalog.content_sha256}",
            context_ref=catalog.source_url,
            table_key=catalog.surface.value,
            row_label=row.instrument_key,
            column_label=field,
            retrieved_at=retrieved_at,
        ),
        verified=True,
    )
