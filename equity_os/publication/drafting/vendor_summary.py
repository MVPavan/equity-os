"""The report's vendor summary block: every eligible vendor text span, grouped by vendor, surface
and capture date, marked as guidance and never a number source (VENDOR-1 §7 "Numerals").

The section is regenerated on every run, so a rework neither carries nor preserves it.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from psycopg import Cursor

from equity_os.publication.checking.vendor_text import IssuerSpan, eligible_spans
from equity_os.sourcing.surfaces.vendor_surface_fetch import Site
from equity_os.storage.raw_files.snapshot_store import SnapshotStore

VENDOR_SUMMARY = "vendor_summary"
_HEADING = "### {vendor} — {surface}, captured {day} — vendor summary — guidance, not evidence"
_PARAGRAPH = "{{{{e:inferred}}}} {text} {{{{s:{capture}|vt:{start}-{end}:{sha256}}}}}"


def vendor_summary_section(
    cursor: Cursor[Any],
    *,
    entity_id: int,
    source_cutoff: datetime,
    knowledge_cutoff: datetime,
    snapshots: SnapshotStore,
) -> tuple[str, str] | None:
    """The section key and body of the issuer's eligible spans, ``None`` when there are none."""
    spans = eligible_spans(
        cursor,
        entity_id=entity_id,
        source_cutoff=source_cutoff,
        knowledge_cutoff=knowledge_cutoff,
        snapshots=snapshots,
    )
    if not spans:
        return None
    groups: dict[tuple[Site, str, date], list[IssuerSpan]] = {}
    for span in spans:
        day = span.registered_at.astimezone(UTC).date()
        groups.setdefault((span.site, span.surface, day), []).append(span)
    body = f"## {VENDOR_SUMMARY}\n\n"
    for (site, surface, day), held in groups.items():
        body += _HEADING.format(vendor=site.name.title(), surface=surface, day=day) + "\n\n"
        body += "".join(
            _PARAGRAPH.format(
                text=" ".join(span.text.split()),  # one paragraph, whatever the span's breaks
                capture=span.capture_ref_id,
                start=span.start,
                end=span.end,
                sha256=span.sha256,
            )
            + "\n\n"
            for span in held
        )
    return VENDOR_SUMMARY, body
