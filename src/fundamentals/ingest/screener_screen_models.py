"""Frozen models and URL construction for subscriber raw-screen acquisition."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from urllib.parse import urlencode

from pydantic import BaseModel, ConfigDict, Field, model_validator

from fundamentals.contracts.provenance import Provenance
from fundamentals.ingest.screener_session_models import (
    SOURCE_ID,
    ScreenerDocumentFetch,
    ScreenerSessionError,
)

# The measured subscriber boundary is about forty requests; leave headroom.
MAX_SCREEN_PAGES = 25


class ScreenOutcome(StrEnum):
    """What the screen actually returned, kept distinct from whether it failed.

    ``ZERO_RESULTS`` is a successful answer, not a degraded one: a query that
    matches nothing is data. Only ``INCOMPLETE`` means the walk stopped short of
    what the source offered.
    """

    RESULTS = "results"
    ZERO_RESULTS = "zero_results"
    INCOMPLETE = "incomplete"


class ScreenerScreenError(ScreenerSessionError):
    """Base refusal for the raw screen query seam."""


class ScreenQueryError(ScreenerScreenError):
    """The caller supplied a query or page this seam cannot address."""


class ScreenStructureError(ScreenerScreenError):
    """The returned result table does not have an admitted shape."""


class ScreenPaginationError(ScreenerScreenError):
    """The returned pagination cannot prove a complete, ordered walk."""


class ScreenAcquisitionConfig(BaseModel):
    """Caller-set bounds on one walk, validated against the request budget."""

    model_config = ConfigDict(frozen=True)

    max_pages: int = Field(default=MAX_SCREEN_PAGES, ge=1, le=MAX_SCREEN_PAGES)


class ScreenColumn(BaseModel):
    """One header cell. The column set is query-dependent, so it is never assumed."""

    model_config = ConfigDict(frozen=True)

    index: int = Field(ge=0)
    label: str


class ScreenCell(BaseModel):
    """One numeric cell, retaining the source text beside the parsed value.

    ``column_index`` starts at 2 because columns 0 and 1 are the serial number
    and the company link, which are modelled by :class:`ScreenRow` and
    :class:`ScreenCompany` rather than as cells. ``value`` is ``None`` when the
    source published nothing parseable — a missing input fails closed rather
    than becoming a zero.
    """

    model_config = ConfigDict(frozen=True)

    column_index: int = Field(ge=2)
    value: Decimal | None
    raw_text: str
    provenance: Provenance


class ScreenCompany(BaseModel):
    """The identity behind a row, keyed by the id rather than by the link.

    ``slug`` is ``None`` for an id-routed link, and is not a ticker even when
    present — captured slugs include BSE scrip codes. ``data_row_company_id`` is
    carried by every row shape and is the only identifier that survives all
    three of them, so it, not the slug, is what rows are de-duplicated on.
    """

    model_config = ConfigDict(frozen=True)

    slug: str | None
    display_name: str
    data_row_company_id: int = Field(gt=0)
    consolidated: bool


class ScreenRow(BaseModel):
    """One admitted result row, with the page it came from retained."""

    model_config = ConfigDict(frozen=True)

    page_number: int = Field(gt=0)
    serial_number: int = Field(gt=0)
    company: ScreenCompany
    cells: tuple[ScreenCell, ...] = ()


class ScreenPageMetadata(BaseModel):
    """Per-page provenance for one fetch in the walk.

    ``offered_pages`` is what that page's own pagination advertised, and is
    empty both for a zero-result page and for a populated result that fits on
    one page — the live surface renders no pagination controls in either case.
    """

    model_config = ConfigDict(frozen=True)

    page_number: int = Field(gt=0)
    source_url: str
    http_status: int
    offered_pages: tuple[int, ...] = ()
    content_sha256: str
    byte_count: int = Field(ge=0)
    fetched_at: datetime


class ScreenFailure(BaseModel):
    """The refusal that ended a walk, naming the page it happened on.

    ``content_sha256`` is present whenever a body was received, so a refused
    page's retained evidence can still be tied back to what was judged.
    """

    model_config = ConfigDict(frozen=True)

    page_number: int = Field(gt=0)
    source_url: str
    refusal: str
    detail: str
    content_sha256: str | None = None


class ScreenArtifact(BaseModel):
    """The published record of one screen query and everything it proved.

    Field validity is bound to :class:`ScreenOutcome` by a validator rather
    than by convention, so an artifact claiming results without rows, or
    claiming completeness while carrying a failure, cannot be constructed at
    all — a caller reading ``outcome`` never has to re-derive it from the
    other fields.
    """

    model_config = ConfigDict(frozen=True)

    source_id: str = SOURCE_ID
    query: str
    outcome: ScreenOutcome
    columns: tuple[ScreenColumn, ...] = ()
    rows: tuple[ScreenRow, ...] = ()
    pages: tuple[ScreenPageMetadata, ...] = ()
    incomplete_reason: str | None = None
    failure: ScreenFailure | None = None

    @model_validator(mode="after")
    def _check_outcome(self) -> ScreenArtifact:
        """Refuse any artifact whose fields contradict its own outcome."""
        if self.outcome is ScreenOutcome.RESULTS:
            valid = bool(self.columns and self.rows and self.pages) and not (
                self.incomplete_reason or self.failure
            )
        elif self.outcome is ScreenOutcome.ZERO_RESULTS:
            valid = (
                not self.columns
                and not self.rows
                and len(self.pages) == 1
                and not (self.incomplete_reason or self.failure)
            )
        else:
            valid = bool(self.incomplete_reason)
        if not valid:
            raise ValueError("screen artifact fields do not match its outcome")
        return self


class ScreenRun(BaseModel):
    """The artifact beside the raw bodies it was derived from.

    The documents are retained even for a refused walk: the response that was
    rejected is usually the most useful thing the run produced.
    """

    model_config = ConfigDict(frozen=True)

    artifact: ScreenArtifact
    documents: tuple[ScreenerDocumentFetch, ...] = ()


class ScreenerScreenCliRun(BaseModel):
    """A completed CLI invocation and the paths it wrote."""

    model_config = ConfigDict(frozen=True)

    run: ScreenRun
    artifact_path: Path
    page_paths: tuple[Path, ...] = ()


def screen_url(query: str, page: int) -> str:
    """Build the one raw-screen navigation URL this source admits."""
    if not query.strip():
        raise ScreenQueryError("screen query must not be blank")
    if page <= 0:
        raise ScreenQueryError("screen page must be positive")
    parameters = (
        ("sort", ""),
        ("order", ""),
        ("source", ""),
        ("query", query),
        ("page", str(page)),
    )
    return f"https://www.screener.in/screen/raw/?{urlencode(parameters)}"
