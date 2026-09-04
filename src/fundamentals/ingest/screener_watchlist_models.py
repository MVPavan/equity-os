"""Frozen models, URL construction and typed refusals for core-watchlist acquisition.

The watchlist page states no total of its own — no ``data-page-info``, no
"results found" line, no pagination block — so nothing here models a stated
completeness claim. What the two renderings of one list *do* offer is agreement
with each other, and every model below exists to record that agreement or the
exact disagreement that refused it.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from fundamentals.contracts.provenance import Provenance
from fundamentals.ingest.screener_session_models import (
    SCREENER_ORIGIN,
    SOURCE_ID,
    ScreenerDocumentFetch,
    ScreenerSessionError,
)

WATCHLIST_PATH = "/watchlist/"
EXPORT_PATH = "/api/export/screen/"
STOCKS_EDITOR_PATH = "/user/stocks/"
CREATE_WATCHLIST_PATH = "/watchlist/add/"
SUBLIST_ID_PARAMETER = "sublist_id"
NEXT_PARAMETER = "next"

CSRF_FORM_FIELD = "csrfmiddlewaretoken"
CSRF_COOKIE_NAME = "csrftoken"

EXPORT_MEDIA_TYPE = "text/csv"
EXPORT_ENCODING = "utf-8-sig"

# The CSV identity labels. A27: the six-field prefix is observed, never
# contractual, so these are matched by label and never by field position.
CSV_NAME = "Name"
CSV_BSE_CODE = "BSE Code"
CSV_NSE_CODE = "NSE Code"
CSV_ISIN_CODE = "ISIN Code"
CSV_INDUSTRY_GROUP = "Industry Group"
CSV_INDUSTRY = "Industry"
CSV_IDENTITY_LABELS = (
    CSV_NAME,
    CSV_BSE_CODE,
    CSV_NSE_CODE,
    CSV_ISIN_CODE,
    CSV_INDUSTRY_GROUP,
    CSV_INDUSTRY,
)

# The provenance anchor names the export, because SL4-20 makes the CSV the
# authoritative side. It therefore addresses a position *in the export*: the CSV
# record and the CSV field, under the CSV anchor type. The page's row order is
# not the export's, so an anchor naming this file and addressing a page row
# would resolve to another company's figure on almost every row.
WATCHLIST_TABLE_ID = "watchlist-export"

_NON_POSITIVE_ID = "watchlist id must be positive"


class WatchlistOutcome(StrEnum):
    """What one run of the seam produced.

    There is deliberately no ``EMPTY`` member. Nothing in the evidence tells a
    genuinely empty watchlist apart from an anonymous shell or a degraded page
    rendering no rows, and an outcome that cannot be distinguished from a
    failure must never be published as a successful answer.
    """

    RESULTS = "results"
    INCOMPLETE = "incomplete"


class ScreenerWatchlistError(ScreenerSessionError):
    """Base refusal for the core-watchlist seam."""


class WatchlistQueryError(ScreenerWatchlistError):
    """The caller named a watchlist this seam cannot address."""


class WatchlistStructureError(ScreenerWatchlistError):
    """The rendered watchlist table does not have an admitted shape."""


class WatchlistPageError(ScreenerWatchlistError):
    """The page cannot authorise or bind the export it is supposed to carry."""


class WatchlistExportError(ScreenerWatchlistError):
    """The export response did not prove it is the export, or is not readable as one."""


class WatchlistCrossCheckError(ScreenerWatchlistError):
    """The page and the export disagree, so neither may be published as a row."""


class WatchlistTableRow(BaseModel):
    """One admitted member row as the page renders it, before the export is joined."""

    model_config = ConfigDict(frozen=True)

    serial_number: int = Field(gt=0)
    data_row_company_id: int = Field(gt=0)
    slug: str | None
    consolidated: bool
    display_name: str
    values: tuple[str, ...] = ()


class WatchlistTable(BaseModel):
    """The rendered table: its stated column names and its member rows.

    ``value_labels`` are the ``data-tooltip`` full metric names the header
    declares; ``visible_labels`` are the abbreviations beside them, retained as
    a secondary label and never as the identity of a column.
    """

    model_config = ConfigDict(frozen=True)

    value_labels: tuple[str, ...]
    visible_labels: tuple[str, ...]
    rows: tuple[WatchlistTableRow, ...] = ()


class WatchlistPageEvidence(BaseModel):
    """What the fetched page itself supplies about the list and its export.

    ``export_action`` is read verbatim from the one export form the page
    renders; no export URL is ever constructed. The form token is a
    :class:`~pydantic.SecretStr` so it cannot reach a log line, a summary or an
    artifact field by accident — the retained body under ``data/raw`` is the
    only sanctioned place it exists.
    """

    model_config = ConfigDict(frozen=True)

    export_action: str
    csrf_form_token: SecretStr
    watchlist_id: int | None
    watchlist_name: str | None
    other_watchlist_names: tuple[str, ...] = ()


class WatchlistColumn(BaseModel):
    """One value column, named by the CSV header the page's tooltip declares."""

    model_config = ConfigDict(frozen=True)

    csv_field_index: int = Field(ge=0)
    label: str
    html_label: str


class WatchlistCell(BaseModel):
    """One value, parsed from the export and retained beside both raw texts.

    ``value`` is ``None`` whenever the source published nothing: an empty cell
    is "no such figure", and a zero is a figure.
    """

    model_config = ConfigDict(frozen=True)

    csv_field_index: int = Field(ge=0)
    value: Decimal | None
    csv_text: str
    html_text: str
    provenance: Provenance


class WatchlistCompany(BaseModel):
    """The identity of one member, as the union of what each rendering publishes.

    Neither artifact is a superset: the page alone carries the row id and the
    slug, the export alone carries the exchange codes, the ISIN and the
    industry. ``slug`` is ``None`` for an id-routed link, and the exchange codes
    are ``None`` when the export publishes none — several members legitimately
    have no NSE code and a delisted one has neither.
    """

    model_config = ConfigDict(frozen=True)

    data_row_company_id: int = Field(gt=0)
    slug: str | None
    display_name: str
    consolidated: bool
    bse_code: str | None
    nse_code: str | None
    isin_code: str
    industry_group: str | None
    industry: str | None


class WatchlistRow(BaseModel):
    """One published member: its identity and its values, both renderings agreed."""

    model_config = ConfigDict(frozen=True)

    serial_number: int = Field(gt=0)
    company: WatchlistCompany
    cells: tuple[WatchlistCell, ...] = ()


class WatchlistValueMismatch(BaseModel):
    """One cell the two renderings disagreed on, with both raw strings kept.

    A single row moving in one column reads nothing like a column shift or a
    membership gap, so this record is what lets an operator tell a price tick
    from a structural fault without spending a second pair of requests.
    """

    model_config = ConfigDict(frozen=True)

    display_name: str
    column_label: str
    html_text: str
    csv_text: str


class WatchlistCrossCheck(BaseModel):
    """What was compared between the two renderings, and what disagreed.

    A compared-cell count alone does not prove the right cells were compared,
    so both header sequences, both row counts and every disagreement are
    recorded here. On a published run the disagreement lists are empty; on a
    refused one they are the whole diagnosis.
    """

    model_config = ConfigDict(frozen=True)

    html_source_url: str
    export_source_url: str
    html_http_status: int
    export_http_status: int
    html_sha256: str
    export_sha256: str
    html_byte_count: int = Field(ge=0)
    export_byte_count: int = Field(ge=0)
    export_content_type: str | None
    export_content_disposition: str | None
    html_row_count: int = Field(ge=0)
    csv_row_count: int = Field(ge=0)
    compared_cell_count: int = Field(ge=0)
    html_value_labels: tuple[str, ...] = ()
    csv_value_labels: tuple[str, ...] = ()
    only_in_html: tuple[str, ...] = ()
    only_in_csv: tuple[str, ...] = ()
    duplicate_names_html: tuple[str, ...] = ()
    duplicate_names_csv: tuple[str, ...] = ()
    value_mismatches: tuple[WatchlistValueMismatch, ...] = ()


class WatchlistFailure(BaseModel):
    """The refusal that stopped a run, naming what raised it and where."""

    model_config = ConfigDict(frozen=True)

    source_url: str
    refusal: str
    detail: str
    content_sha256: str | None = None


class WatchlistArtifact(BaseModel):
    """The published record of one watchlist acquisition and what it proved.

    The guarantee is **cross-render consistency at fetch time**: the page and
    the export agreed on membership, on the column correspondence the page
    itself states, and on every value cell, at the moment the two requests were
    made. It is not a claim that the watchlist contains nothing else — both
    renderings are served by one backend and could share one capped, filtered
    or stale snapshot, and whether the export is a live render or a cache is
    untested.

    On **identity** the claim is narrower than "the two agreed", and saying
    otherwise would overstate it. What is corroborated across the renderings is
    the exchange code, against the slug the page routes each row by; what is
    checked within one rendering is that the ISIN is present and unique and
    that no exchange code or slug repeats. The industry and the industry group
    are published on the export's word alone, bound to the row only by the
    display name that joined them — swap those fields between two slug-routed
    export records and every rule here still passes. Closing that needs a third
    source, and no source this repo holds publishes an industry at all. The ISIN
    and the exchange codes do have one, outside this seam:
    ``screener-watchlist-corroborate`` resolves them against a retained Upstox
    instrument catalog, which has never heard of this export.

    Field validity is bound to :class:`WatchlistOutcome` by a validator rather
    than by convention, so an artifact claiming rows it did not prove, or
    stopping short while recording neither a refusal nor the comparison it got
    to, cannot be constructed at all.
    """

    model_config = ConfigDict(frozen=True)

    source_id: str = SOURCE_ID
    watchlist_id: int | None = None
    watchlist_name: str | None = None
    other_watchlist_names: tuple[str, ...] = ()
    outcome: WatchlistOutcome
    columns: tuple[WatchlistColumn, ...] = ()
    rows: tuple[WatchlistRow, ...] = ()
    cross_check: WatchlistCrossCheck | None = None
    incomplete_reason: str | None = None
    failure: WatchlistFailure | None = None

    @model_validator(mode="after")
    def _check_outcome(self) -> WatchlistArtifact:
        """Refuse any artifact whose fields contradict its own outcome."""
        if self.outcome is WatchlistOutcome.RESULTS:
            valid = bool(self.columns and self.rows and self.cross_check) and not (
                self.incomplete_reason or self.failure
            )
        else:
            valid = bool(self.incomplete_reason) and bool(self.failure or self.cross_check)
        if not valid:
            raise ValueError("watchlist artifact fields do not match its outcome")
        return self


class WatchlistRun(BaseModel):
    """The artifact beside the raw bodies it was judged on.

    Both documents are retained even for a refused run: the pair of responses
    that disagreed is the only thing that explains the disagreement.
    """

    model_config = ConfigDict(frozen=True)

    artifact: WatchlistArtifact
    documents: tuple[ScreenerDocumentFetch, ...] = ()


class ScreenerWatchlistCliRun(BaseModel):
    """A completed CLI invocation and the paths it wrote."""

    model_config = ConfigDict(frozen=True)

    run: WatchlistRun
    artifact_path: Path
    document_paths: tuple[Path, ...] = ()


def watchlist_url(watchlist_id: int | None = None) -> str:
    """Build the default-list or one named-list watchlist URL, and nothing else.

    Both shapes were exercised live and render the same list; the id form is
    what binds a run to a named list. A watchlist id below one is a caller
    defect and is refused before it can spend a request.
    """
    if watchlist_id is None:
        return f"{SCREENER_ORIGIN}{WATCHLIST_PATH}"
    if watchlist_id <= 0:
        raise WatchlistQueryError(_NON_POSITIVE_ID)
    return f"{SCREENER_ORIGIN}{WATCHLIST_PATH}{watchlist_id}/"
