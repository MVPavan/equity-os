"""Which vendor text spans a report may use: bound to its issuer, known by its two cutoffs,
present in the retained bytes and numeral-free (VENDOR-1 §7, readings 3, 4, 5 and 7).

Vendor text is guidance, never a number source; a span is cited as
``{{s:<capture_ref_id>|vt:<start>-<end>:<blob_sha256>}}``.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from itertools import groupby
from typing import Any, LiteralString
from urllib.parse import urlsplit

from psycopg import Cursor
from psycopg.rows import dict_row
from pydantic import BaseModel, ConfigDict

from equity_os.contracts.companies.entity_identity import IdentifierNamespace
from equity_os.contracts.sourcing.snapshot import IntegrityError
from equity_os.extraction.surfaces.vendor_text_readers import READERS, CompanyRef, read_text
from equity_os.publication.checking.numeral_scan import has_numeral
from equity_os.sourcing.surfaces.vendor_surface_fetch import Site
from equity_os.storage.raw_files.capture_retention import retained_capture
from equity_os.storage.raw_files.snapshot_store import SnapshotStore
from equity_os.storage.records.repository_rows import capture_of

VT_ANCHOR = re.compile(r"vt:([0-9]+)-([0-9]+):([0-9a-f]{64})")
_COMPANY_PATH = re.compile(r"/company/([^/]+)/(?:consolidated/)?")
_BODY_MISMATCH = "capture {capture_ref_id} body does not match its blob hash"
_IDS: LiteralString = """SELECT b.screener_company_id, a.url FROM eqos.vendor_basis_bindings b
LEFT JOIN eqos.capture_addresses a ON a.capture_ref_id = b.capture_ref_id
WHERE b.entity_id = %s AND b.recorded_at <= %s"""
# Reading 7: the latest capture per request registered by S, its latest completed extraction
# recorded by K, and that extraction's CLAIM rows recorded by K; earlier ones never revive.
_SPANS: LiteralString = """WITH latest AS (
    SELECT DISTINCT ON (c.source_id, c.surface, c.request_key) c.*
    FROM eqos.capture_refs c
    WHERE (c.source_id, c.surface) IN
        (SELECT * FROM unnest(%(sites)s::text[], %(surfaces)s::text[]))
        AND c.registered_at <= %(source_cutoff)s
    ORDER BY c.source_id, c.surface, c.request_key, c.registered_at DESC, c.id DESC
), extraction AS (
    SELECT DISTINCT ON (o.capture_ref_id) o.capture_ref_id, o.surface, o.parser_version
    FROM eqos.vendor_outcomes o JOIN latest l ON l.id = o.capture_ref_id
    WHERE o.surface = substring(l.surface from 4) AND starts_with(o.parser_version, 'claims:')
        AND o.status IN ('OK', 'PARTIAL', 'EMPTY') AND o.recorded_at <= %(knowledge_cutoff)s
    ORDER BY o.capture_ref_id, o.recorded_at DESC, o.id DESC
)
SELECT l.*, a.url, t.span_start, t.span_end, t.text FROM latest l
JOIN extraction e ON e.capture_ref_id = l.id
JOIN eqos.vendor_text_claims t ON t.capture_ref_id = l.id AND t.surface = e.surface
    AND e.parser_version = 'claims:' || t.model_id || ':' || t.prompt_version
JOIN eqos.capture_addresses a ON a.capture_ref_id = l.id
WHERE t.kind = 'CLAIM' AND t.text IS NOT NULL AND t.recorded_at <= %(knowledge_cutoff)s
    AND eqos.capture_state(l.id) IN ('RETAINED', 'RESTORED')
    AND NOT EXISTS (SELECT 1 FROM eqos.licence_ends x WHERE x.source_id = l.source_id)
ORDER BY l.id, t.span_start, t.span_end"""


class VendorIds(BaseModel):
    """The issuer's Screener company id and slug, from its vendor basis bindings."""

    model_config = ConfigDict(frozen=True)
    company_id: int
    slug: str


class IssuerSpan(BaseModel):
    """One eligible vendor span; offsets index the reader's text, end exclusive."""

    model_config = ConfigDict(frozen=True)
    capture_ref_id: int
    site: Site
    surface: str
    registered_at: datetime
    start: int
    end: int
    sha256: str
    text: str


def vendor_ids(cursor: Cursor[Any], *, entity_id: int, known_by: datetime) -> VendorIds | None:
    """The unique company id and slug over the bindings recorded by ``known_by``, else ``None``."""
    rows = cursor.execute(_IDS, (entity_id, known_by)).fetchall()
    companies = {company for company, _ in rows}
    paths = (_COMPANY_PATH.fullmatch(urlsplit(url or "").path) for _, url in rows)
    slugs = {path[1] if path else None for path in paths}
    if len(companies) != 1 or len(slugs) != 1 or None in slugs:
        return None
    return VendorIds(company_id=companies.pop(), slug=str(slugs.pop()))


def eligible_spans(
    cursor: Cursor[Any],
    *,
    entity_id: int,
    source_cutoff: datetime,
    knowledge_cutoff: datetime,
    snapshots: SnapshotStore,
    capture_ref_id: int | None = None,
) -> tuple[IssuerSpan, ...]:
    """The issuer's usable spans, equal texts once at their lowest (capture, start); then, with
    ``capture_ref_id``, those of that capture, so a discarded duplicate never resolves.

    A retained body whose bytes do not match its blob hash raises ``IntegrityError``.
    """
    ids = vendor_ids(cursor, entity_id=entity_id, known_by=knowledge_cutoff)
    if ids is None:
        return ()
    issuer = {
        CompanyRef(namespace=IdentifierNamespace.SCREENER_COMPANY_ID, value=str(ids.company_id)),
        CompanyRef(namespace=IdentifierNamespace.SCREENER_SLUG, value=ids.slug),
    }
    params = {
        "sites": [site for site, _ in READERS],
        "surfaces": ["vs." + surface for _, surface in READERS],
        "source_cutoff": source_cutoff,
        "knowledge_cutoff": knowledge_cutoff,
    }
    with cursor.connection.cursor(row_factory=dict_row) as own:
        rows = own.execute(_SPANS, params).fetchall()
    kept: list[IssuerSpan] = []
    seen: set[str] = set()
    for _, group in groupby(rows, key=lambda row: row["id"]):
        claims = list(group)
        capture = claims[0]
        _, body = retained_capture(cursor.connection, snapshots, capture_of(capture))
        if hashlib.sha256(body).hexdigest() != capture["blob_sha256"]:
            raise IntegrityError(_BODY_MISMATCH.format(capture_ref_id=capture["id"]))
        site, surface = Site(capture["source_id"]), capture["surface"].removeprefix("vs.")
        read = read_text(site, surface, body, capture["url"])
        for claim in claims:
            start, end, text = claim["span_start"], claim["span_end"], claim["text"]
            if (
                not 0 <= start < end <= len(read.text)
                or read.text[start:end] != text
                or not any(
                    i.start <= start and end <= i.end and i.company in issuer for i in read.items
                )
                or has_numeral(text)
                or "{{" in text
                or "}}" in text
                or text in seen
            ):
                continue
            seen.add(text)
            kept.append(
                IssuerSpan(
                    capture_ref_id=capture["id"],
                    site=site,
                    surface=surface,
                    registered_at=capture["registered_at"],
                    start=start,
                    end=end,
                    sha256=capture["blob_sha256"],
                    text=text,
                )
            )
    return tuple(span for span in kept if capture_ref_id in (None, span.capture_ref_id))


def vendor_location(
    cursor: Cursor[Any],
    capture_ref_id: int,
    anchor: str,
    entity_id: int,
    source_cutoff: datetime | None,
    knowledge_cutoff: datetime,
    snapshots: SnapshotStore,
) -> bool:
    """Whether a ``VT_ANCHOR`` names an eligible span of that capture; no source cutoff: no."""
    parsed = VT_ANCHOR.fullmatch(anchor)
    if parsed is None or source_cutoff is None:
        return False
    spans = eligible_spans(
        cursor,
        entity_id=entity_id,
        source_cutoff=source_cutoff,
        knowledge_cutoff=knowledge_cutoff,
        snapshots=snapshots,
        capture_ref_id=capture_ref_id,
    )
    named = (int(parsed[1]), int(parsed[2]), parsed[3])
    return named in {(span.start, span.end, span.sha256) for span in spans}
