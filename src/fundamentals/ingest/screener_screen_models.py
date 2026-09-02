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
    model_config = ConfigDict(frozen=True)

    max_pages: int = Field(default=MAX_SCREEN_PAGES, ge=1, le=MAX_SCREEN_PAGES)


class ScreenColumn(BaseModel):
    model_config = ConfigDict(frozen=True)

    index: int = Field(ge=0)
    label: str


class ScreenCell(BaseModel):
    model_config = ConfigDict(frozen=True)

    column_index: int = Field(ge=2)
    value: Decimal | None
    raw_text: str
    provenance: Provenance


class ScreenCompany(BaseModel):
    model_config = ConfigDict(frozen=True)

    slug: str | None
    display_name: str
    data_row_company_id: int = Field(gt=0)
    consolidated: bool


class ScreenRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    page_number: int = Field(gt=0)
    serial_number: int = Field(gt=0)
    company: ScreenCompany
    cells: tuple[ScreenCell, ...] = ()


class ScreenPageMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    page_number: int = Field(gt=0)
    source_url: str
    http_status: int
    offered_pages: tuple[int, ...] = ()
    content_sha256: str
    byte_count: int = Field(ge=0)
    fetched_at: datetime


class ScreenFailure(BaseModel):
    model_config = ConfigDict(frozen=True)

    page_number: int = Field(gt=0)
    source_url: str
    refusal: str
    detail: str
    content_sha256: str | None = None


class ScreenArtifact(BaseModel):
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
    model_config = ConfigDict(frozen=True)

    artifact: ScreenArtifact
    documents: tuple[ScreenerDocumentFetch, ...] = ()


class ScreenerScreenCliRun(BaseModel):
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
