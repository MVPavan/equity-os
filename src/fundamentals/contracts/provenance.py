"""Provenance: where a measured value came from and how to find it again.

Every observation and guidance claim must carry non-null provenance binding it
to a source file (by sha256) and a typed anchor — a PDF page/block/span, an XBRL
context reference, a JSON island location, a location inside a standalone JSON
API document, a server-rendered HTML table cell, or a field of one record of a
delimited export — plus the bitemporal timestamps needed to reason about when
the value could have been known.

The anchor type is the retrieval procedure, not a formatting detail: a
``JSON_ISLAND`` value is re-found by fetching a page and reading the named
``json_script`` block inside it, while an ``API_DOCUMENT`` value is re-found by
issuing the documented GET. The two also differ in what the source can assert:
a page island sits beside the identity islands its adapter verifies, whereas an
API response may carry no identity field at all, leaving the request URL as the
only binding. Collapsing them onto one anchor type would erase that difference
at exactly the layer built to preserve it.

``CSV_RECORD`` exists for the same reason. A downloaded export and the page it
was exported from order their rows differently, so an anchor that names the
export file while addressing the page's row position points at another
issuer's figure. The type states which file the position is a position *in*.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator


class SourceAnchorType(StrEnum):
    """Discriminant for the kind of typed source anchor a Provenance carries."""

    PDF_SPAN = "PDF_SPAN"
    XBRL_CONTEXT = "XBRL_CONTEXT"
    JSON_ISLAND = "JSON_ISLAND"
    API_DOCUMENT = "API_DOCUMENT"
    HTML_TABLE = "HTML_TABLE"
    CSV_RECORD = "CSV_RECORD"


# Location fields each anchor kind must NOT set, verified against every
# committed producer in this repo. ``context_ref`` and ``row_label``/
# ``column_label`` are genuinely shared and so appear in no row. PDF_SPAN and
# XBRL_CONTEXT are deliberately absent: their producers predate this rule and
# tightening them is a separate, non-Tijori change.
_FOREIGN_ANCHOR_FIELDS: dict[SourceAnchorType, tuple[str, ...]] = {
    SourceAnchorType.JSON_ISLAND: ("document_id", "table_id", "row_path", "column_index"),
    SourceAnchorType.API_DOCUMENT: ("island_id", "table_id", "row_path", "column_index"),
    SourceAnchorType.HTML_TABLE: ("document_id", "island_id", "table_key"),
    SourceAnchorType.CSV_RECORD: ("document_id", "island_id", "table_key"),
}

# The anchor kinds addressed by ``table_id``/``row_path``/``column_index``.
_POSITIONAL_ANCHOR_TYPES = (SourceAnchorType.HTML_TABLE, SourceAnchorType.CSV_RECORD)


class Provenance(BaseModel):
    """Immutable binding of a value to its source location and known-times.

    A PDF anchor uses ``page``/``block``/``span``; an XBRL anchor uses
    ``context_ref``; a JSON island anchor uses ``island_id``/``table_key``/
    ``row_label``/``column_label``; an API document anchor uses the same
    location triple below ``document_id`` instead of ``island_id``; an HTML
    table anchor and a CSV record anchor both use ``table_id``/``row_path``/
    ``column_index``/``column_label``, differing in which file the position
    addresses. Typed fields not relevant to ``anchor_type`` are left ``None``.
    """

    model_config = ConfigDict(frozen=True)

    source_id: str
    file_sha256: str
    anchor_type: SourceAnchorType

    page: int | None = None
    block: int | None = None
    span: str | None = None
    context_ref: str | None = None
    island_id: str | None = None
    document_id: str | None = None
    table_key: str | None = None
    row_label: str | None = None
    column_label: str | None = None
    table_id: str | None = None
    row_path: str | None = None
    column_index: int | None = None

    retrieved_at: datetime
    filed_at: datetime | None = None
    published_at: datetime | None = None
    first_seen_at: datetime | None = None

    @model_validator(mode="after")
    def _check_anchor_consistency(self) -> Provenance:
        """Require the typed anchor fields the declared ``anchor_type`` needs."""
        if self.anchor_type is SourceAnchorType.PDF_SPAN:
            if self.page is None or self.block is None or self.span is None:
                raise ValueError("PDF_SPAN anchor requires page, block, and span to be set")
        elif self.anchor_type is SourceAnchorType.XBRL_CONTEXT:
            if self.context_ref is None:
                raise ValueError("XBRL_CONTEXT anchor requires context_ref to be set")
        elif self.anchor_type is SourceAnchorType.JSON_ISLAND:
            location_fields = (
                self.island_id,
                self.table_key,
                self.row_label,
                self.column_label,
            )
            if any(value is None or not value.strip() for value in location_fields):
                raise ValueError(
                    "JSON_ISLAND anchor requires island_id, table_key, row_label, "
                    "and column_label to be set"
                )
        elif self.anchor_type is SourceAnchorType.API_DOCUMENT:
            api_fields: tuple[str | None, ...] = (
                self.document_id,
                self.context_ref,
                self.table_key,
                self.row_label,
                self.column_label,
            )
            if any(value is None or not value.strip() for value in api_fields):
                raise ValueError(
                    "API_DOCUMENT anchor requires document_id, context_ref, table_key, "
                    "row_label, and column_label to be set"
                )
        elif self.anchor_type in _POSITIONAL_ANCHOR_TYPES:
            kind = self.anchor_type.value
            positional_fields = (self.table_id, self.row_path, self.column_label)
            if any(value is None or not value.strip() for value in positional_fields):
                raise ValueError(
                    f"{kind} anchor requires table_id, row_path, and column_label to be set"
                )
            if self.column_index is None or self.column_index < 0:
                raise ValueError(f"{kind} anchor requires a non-negative column_index")
        self._reject_foreign_fields()
        return self

    def _reject_foreign_fields(self) -> None:
        """Refuse a location field that belongs to a different anchor kind.

        Requiring the right fields is not enough: an anchor that ALSO carries a
        foreign one is ambiguous about which retrieval procedure applies, and an
        API document addressed by ``island_id`` would read as a page island to
        anything that switches on the typed fields rather than the discriminant.
        """
        foreign = _FOREIGN_ANCHOR_FIELDS.get(self.anchor_type)
        if foreign is None:
            return
        populated = sorted(field for field in foreign if getattr(self, field) is not None)
        if populated:
            raise ValueError(
                f"{self.anchor_type.value} anchor must not set {', '.join(populated)}: "
                "those fields belong to a different anchor kind"
            )
