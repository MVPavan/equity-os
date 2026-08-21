"""Provenance: where a measured value came from and how to find it again.

Every observation and guidance claim must carry non-null provenance binding it
to a source file (by sha256) and a typed anchor — either a PDF page/block/span
or an XBRL context reference — plus the bitemporal timestamps needed to reason
about when the value could have been known.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class SourceAnchorType(StrEnum):
    """Discriminant for the kind of typed source anchor a Provenance carries."""

    PDF_SPAN = "PDF_SPAN"
    XBRL_CONTEXT = "XBRL_CONTEXT"


class Provenance(BaseModel):
    """Immutable binding of a value to its source location and known-times.

    A PDF anchor uses ``page``/``block``/``span``; an XBRL anchor uses
    ``context_ref``. The typed anchor fields not relevant to ``anchor_type``
    are left ``None``.
    """

    model_config = ConfigDict(frozen=True)

    source_id: str
    file_sha256: str
    anchor_type: SourceAnchorType

    page: int | None = None
    block: int | None = None
    span: str | None = None
    context_ref: str | None = None

    retrieved_at: datetime
    filed_at: datetime | None = None
    published_at: datetime | None = None
    first_seen_at: datetime | None = None
