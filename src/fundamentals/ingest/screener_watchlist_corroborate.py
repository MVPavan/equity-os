"""The third source for a watchlist member's identity: the Upstox instrument master.

The watchlist cross-check corroborates the page's slug against the export's
exchange code and nothing else, so the ISIN is published on the export's word
alone. One witness cannot corroborate itself: swap the ISIN between two
slug-routed export records and every cross-render rule still passes, while each
row merges under the other company's identity.

This reads two artifacts that are already on disk — a published
:class:`~fundamentals.ingest.screener_watchlist_models.WatchlistArtifact` and a
retained :class:`~fundamentals.ingest.upstox_instruments.UpstoxInstrumentCatalog`
— and asks the catalog which ISIN each exported exchange code belongs to. It
opens no socket and writes to neither input, so anyone holding the same two
files re-runs it and gets the same answer.

Both directions are checked in one pass, because neither alone is enough. Code →
ISIN catches an ISIN that belongs to another company; ISIN → code catches an
exchange code the vendor states differently for the very security the export
named. The results are per field rather than one verdict per row: a wrong BSE
scrip beside a right NSE symbol is a real finding that a single verdict would
either hide or overstate.

Silence is never read as disagreement. The retained catalog is an ISIN-filtered
view of a current-state file, so a code it holds no row for may be our filter, a
delisting or a security type we never retain — :data:`CorroborationOutcome.NOT_COVERED`
says "nobody corroborated this", never "the vendor says otherwise". This is the
same absence rule the Upstox entity adapter already holds, and for the same
reason.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from fundamentals.ingest.screener_watchlist_models import (
    WatchlistArtifact,
    WatchlistCompany,
    WatchlistOutcome,
)
from fundamentals.ingest.upstox_instruments import (
    BSE_EQUITY_SEGMENT,
    NSE_EQUITY_SEGMENT,
    UpstoxInstrument,
    UpstoxInstrumentCatalog,
)
from fundamentals.ingest.upstox_source import AcquisitionOutcome, UpstoxSurface

# What a clean run does NOT close, said in the report rather than in a bead.
# Upstox publishes no industry field of any kind, so a report that named only
# what it checked would read as a full identity corroboration.
INDUSTRY_NOT_CORROBORATED = (
    "industry and industry group are not corroborated here: the Upstox instrument "
    "catalog publishes no industry field of any kind, so both remain the Screener "
    "export's word alone"
)

_INCOMPLETE_ARTIFACT = (
    "watchlist artifact {path} published outcome {outcome!r}, not {expected!r}: a run "
    "that stopped short records no membership, and corroborating its empty rows would "
    "report nothing conflicted and call a failed acquisition clean"
)
_INCOMPLETE_CATALOG = (
    "upstox instrument catalog {path} published outcome {outcome!r}, not {expected!r}: a "
    "run that drifted retains no equity rows, and every company would be published as "
    "uncovered when in truth the evidence never loaded"
)
_NOT_A_LISTED_CATALOG = (
    "{path} is not a listed-instrument catalog with rows; a suspended catalog states no "
    "current identity and corroborates nothing"
)
_AMBIGUOUS_CODE = (
    "the catalog states {field} {code!r} on two different securities ({first} and "
    "{second}): an ambiguous code is not evidence, and resolving it to whichever row "
    "was read last would make the answer depend on the vendor's file order"
)
# A different fault with the same consequence, and worth telling apart: the code
# is not ambiguous, the file states one security twice. Nothing here can say
# which duplicate is authoritative, and a catalog that repeats a row may be
# repeating others, so it is refused rather than de-duplicated.
_DUPLICATED_ROW = (
    "the catalog states {field} {code!r} twice for one security ({isin}): a repeated row "
    "is drift in the file itself, and silently collapsing it would hide that"
)
_WATCHLIST_KIND = "watchlist artifact"
_CATALOG_KIND = "upstox instrument catalog"
_UNOPENABLE_INPUT = (
    "{kind} {path} could not be opened ({reason}): this command corroborates two retained "
    "files and has nothing to say about a path that is not one of them"
)
_UNREADABLE_INPUT = (
    "{kind} {path} did not parse as one ({reason}): a file this command cannot read is a "
    "caller defect, and publishing it as an uncovered watchlist would blame the sources"
)
_COUNTS_DISAGREE = "corroboration counts do not match the rows they claim to count"
_INDUSTRY_NOTE_REWRITTEN = (
    "a corroboration report may not restate what it did not corroborate: industry_note "
    "carries one fixed sentence or the report is not one"
)


class CorroborationOutcome(StrEnum):
    """What the catalog had to say about one exported field.

    ``NOT_COVERED`` is a statement about our own coverage, never about the
    company: it is what an empty export field, a filtered-out security or a
    delisting all look like from here.
    """

    CONFIRMED = "CONFIRMED"
    CONFLICTED = "CONFLICTED"
    NOT_COVERED = "NOT_COVERED"


class ExportCodeField(StrEnum):
    """The two export fields a resolution can come from.

    Named exactly as the export names them, so a report row says which code
    carried the join in the reader's own vocabulary.
    """

    NSE = "nse_code"
    BSE = "bse_code"


class WatchlistCorroborationError(ValueError):
    """The inputs cannot corroborate anything, so nothing is published."""


class CodeResolution(BaseModel):
    """One exported exchange code and the ISIN the catalog binds it to."""

    model_config = ConfigDict(frozen=True)

    via: ExportCodeField
    code: str
    isin: str


class CorroborationRow(BaseModel):
    """One watchlist member, as the catalog does or does not corroborate it.

    ``name`` is the export's display name. It is not a symbol and is not called
    one: the exchange codes have their own fields below, and this bead exists
    because a display name is exactly the wrong thing to bind an identity to.

    Every resolution is kept rather than only the first: one code agreeing does
    not make the row corroborated, and reporting only the first would publish a
    row as confirmed while discarding the disagreement that was found.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    isin: str
    isin_outcome: CorroborationOutcome
    resolved_isin: str | None
    resolved_via: ExportCodeField | None
    nse_code: str | None
    bse_code: str | None
    nse_code_corroborated: CorroborationOutcome
    bse_code_corroborated: CorroborationOutcome
    resolutions: tuple[CodeResolution, ...] = ()


class WatchlistCorroborationReport(BaseModel):
    """The published result: one row per member, bound to both inputs by digest.

    The digests are the producers' own — the catalog's ``content_sha256`` and
    the watchlist's two cross-check digests — so a disagreement can be re-read
    against exactly the bytes that produced it. ``watchlist_retrieved_at`` is the
    EARLIEST retrieval time the artifact's own value cells record, and ``None``
    when it carries no cells and so records no time at all; a filesystem mtime
    would be restamped by any checkout and is never read here.

    ``industry_note`` is fixed by a validator rather than by convention: it is
    the one sentence saying what a clean run did NOT corroborate, and a report
    that could quietly carry a different one could quietly carry none.
    """

    model_config = ConfigDict(frozen=True)

    catalog_sha256: str
    catalog_retrieved_at: datetime
    watchlist_html_sha256: str
    watchlist_export_sha256: str
    watchlist_retrieved_at: datetime | None
    confirmed_count: int = Field(ge=0)
    conflicted_count: int = Field(ge=0)
    not_covered_count: int = Field(ge=0)
    rows: tuple[CorroborationRow, ...] = ()
    industry_note: str = INDUSTRY_NOT_CORROBORATED

    @model_validator(mode="after")
    def _check_published_claims(self) -> WatchlistCorroborationReport:
        """Refuse a report whose counts contradict its rows, or whose note was rewritten."""
        stated = (self.confirmed_count, self.conflicted_count, self.not_covered_count)
        if stated != _counts(self.rows):
            raise ValueError(_COUNTS_DISAGREE)
        if self.industry_note != INDUSTRY_NOT_CORROBORATED:
            raise ValueError(_INDUSTRY_NOTE_REWRITTEN)
        return self

    def has_conflict(self) -> bool:
        """Whether any company or any single code field came back disagreeing.

        A code conflict counts. It is a real identity disagreement about the
        security the export named, not a gap in our coverage.
        """
        return any(
            CorroborationOutcome.CONFLICTED
            in (row.isin_outcome, row.nse_code_corroborated, row.bse_code_corroborated)
            for row in self.rows
        )


def corroborate_watchlist(watchlist_path: Path, catalog_path: Path) -> WatchlistCorroborationReport:
    """Corroborate one published watchlist against one retained instrument catalog.

    Reads both files, refuses either input that did not publish a complete
    result, and reports every member both directions at once.
    """
    artifact, cross_check_digests, watchlist_stamp = _load_watchlist(watchlist_path)
    catalog = _load_catalog(catalog_path)
    nse_index, bse_index = _code_indexes(catalog)
    grouped = catalog.by_isin()
    rows = tuple(
        _row(
            row.company,
            nse_index=nse_index,
            bse_index=bse_index,
            catalog_rows=grouped.get(row.company.isin_code, ()),
        )
        for row in artifact.rows
    )
    confirmed, conflicted, not_covered = _counts(rows)
    html_sha256, export_sha256 = cross_check_digests
    return WatchlistCorroborationReport(
        catalog_sha256=catalog.content_sha256,
        catalog_retrieved_at=catalog.retrieved_at,
        watchlist_html_sha256=html_sha256,
        watchlist_export_sha256=export_sha256,
        watchlist_retrieved_at=watchlist_stamp,
        confirmed_count=confirmed,
        conflicted_count=conflicted,
        not_covered_count=not_covered,
        rows=rows,
    )


def _read[ModelT: BaseModel](path: Path, model: type[ModelT], kind: str) -> ModelT:
    """Parse one retained artifact, naming the path in any refusal it raises.

    A mistyped path and a file that is not the artifact it was named as are both
    caller defects, and both reach the operator as this command's own typed
    refusal rather than as a traceback that reads like a crash.
    """
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise WatchlistCorroborationError(
            _UNOPENABLE_INPUT.format(kind=kind, path=path, reason=type(error).__name__)
        ) from error
    try:
        return model.model_validate_json(payload)
    except ValidationError as error:
        raise WatchlistCorroborationError(
            _UNREADABLE_INPUT.format(kind=kind, path=path, reason=error.errors()[0]["msg"])
        ) from error


def _load_watchlist(path: Path) -> tuple[WatchlistArtifact, tuple[str, str], datetime | None]:
    """Read one watchlist artifact, refusing any run that stopped short.

    The same rule the entity map's S1 adapter holds: an artifact that did not
    publish a complete result records no membership, and reading it for its
    empty rows would print a clean total for a failed acquisition.

    Returns the artifact, its two cross-check digests and the earliest retrieval
    time its own value cells record — ``None`` when it carries no cells.
    """
    artifact = _read(path, WatchlistArtifact, _WATCHLIST_KIND)
    cross_check = artifact.cross_check
    if artifact.outcome is not WatchlistOutcome.RESULTS or cross_check is None:
        raise WatchlistCorroborationError(
            _INCOMPLETE_ARTIFACT.format(
                path=path,
                outcome=artifact.outcome.value,
                expected=WatchlistOutcome.RESULTS.value,
            )
        )
    stamps = [cell.provenance.retrieved_at for row in artifact.rows for cell in row.cells]
    return artifact, (cross_check.html_sha256, cross_check.export_sha256), min(stamps, default=None)


def _load_catalog(path: Path) -> UpstoxInstrumentCatalog:
    """Read one retained instrument catalog, refusing a drifted or suspended one.

    The same rule the Upstox entity adapter holds. A catalog that is not ``OK``
    retains no equity rows, so every company would resolve to nothing and the
    report would say the watchlist is simply uncovered.
    """
    catalog = _read(path, UpstoxInstrumentCatalog, _CATALOG_KIND)
    if catalog.surface is not UpstoxSurface.INSTRUMENTS or not catalog.instruments:
        raise WatchlistCorroborationError(_NOT_A_LISTED_CATALOG.format(path=path))
    if catalog.outcome is not AcquisitionOutcome.OK:
        raise WatchlistCorroborationError(
            _INCOMPLETE_CATALOG.format(
                path=path,
                outcome=catalog.outcome.value,
                expected=AcquisitionOutcome.OK.value,
            )
        )
    return catalog


def _code_indexes(catalog: UpstoxInstrumentCatalog) -> tuple[dict[str, str], dict[str, str]]:
    """Build the two code → ISIN indexes, from the fields each exchange states them in.

    The same two extractions the Upstox entity adapter reads: the NSE symbol
    from ``trading_symbol`` on ``NSE_EQ`` rows, the BSE scrip from
    ``exchange_token`` on ``BSE_EQ`` rows.
    """
    nse_index: dict[str, str] = {}
    bse_index: dict[str, str] = {}
    for row in catalog.instruments:
        if row.segment == NSE_EQUITY_SEGMENT:
            _index(nse_index, row.trading_symbol, row.isin, ExportCodeField.NSE)
        elif row.segment == BSE_EQUITY_SEGMENT:
            _index(bse_index, row.exchange_token, row.isin, ExportCodeField.BSE)
    return nse_index, bse_index


def _index(index: dict[str, str], code: str, isin: str, field: ExportCodeField) -> None:
    """Bind one code to one ISIN, refusing the whole catalog on a repeated code.

    Both repeats are refused and both are named, because they are different
    faults: two securities under one code is an ambiguous code, and one security
    under it twice is a duplicated row. Reporting them in the same words would
    send an operator looking for the wrong thing in a 117,000-row file.
    """
    held = index.get(code)
    if held == isin:
        raise WatchlistCorroborationError(
            _DUPLICATED_ROW.format(field=field.value, code=code, isin=isin)
        )
    if held is not None:
        raise WatchlistCorroborationError(
            _AMBIGUOUS_CODE.format(field=field.value, code=code, first=held, second=isin)
        )
    index[code] = isin


def _row(
    company: WatchlistCompany,
    *,
    nse_index: dict[str, str],
    bse_index: dict[str, str],
    catalog_rows: Sequence[UpstoxInstrument],
) -> CorroborationRow:
    """Corroborate one member both directions and record what each one found."""
    resolutions: list[CodeResolution] = []
    for field, code, index in (
        (ExportCodeField.NSE, company.nse_code, nse_index),
        (ExportCodeField.BSE, company.bse_code, bse_index),
    ):
        if not code:
            continue
        resolved = index.get(code)
        if resolved is not None:
            resolutions.append(CodeResolution(via=field, code=code, isin=resolved))
    outcome, headline = _headline(company.isin_code, tuple(resolutions))
    stated_nse, stated_bse = _stated_codes(catalog_rows)
    return CorroborationRow(
        name=company.display_name,
        isin=company.isin_code,
        isin_outcome=outcome,
        resolved_isin=None if headline is None else headline.isin,
        resolved_via=None if headline is None else headline.via,
        nse_code=company.nse_code,
        bse_code=company.bse_code,
        nse_code_corroborated=_field_outcome(company.nse_code, stated_nse),
        bse_code_corroborated=_field_outcome(company.bse_code, stated_bse),
        resolutions=tuple(resolutions),
    )


def _stated_codes(rows: Sequence[UpstoxInstrument]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """What the catalog itself states for one ISIN: its NSE symbols and BSE scrips.

    Every row is kept rather than the first of each segment: an issuer listed in
    more than one series states more than one code, and the export naming any of
    them is the export agreeing with the vendor.
    """
    return (
        tuple(row.trading_symbol for row in rows if row.segment == NSE_EQUITY_SEGMENT),
        tuple(row.exchange_token for row in rows if row.segment == BSE_EQUITY_SEGMENT),
    )


def _headline(
    isin: str, resolutions: tuple[CodeResolution, ...]
) -> tuple[CorroborationOutcome, CodeResolution | None]:
    """The row's verdict and the resolution that carries it.

    A disagreeing resolution is preferred as the headline: on a conflicted row
    the published ``resolved_isin`` must name the ISIN that disagrees, not the
    one that happens to be listed first.
    """
    if not resolutions:
        return CorroborationOutcome.NOT_COVERED, None
    disagreeing = [resolution for resolution in resolutions if resolution.isin != isin]
    if disagreeing:
        return CorroborationOutcome.CONFLICTED, disagreeing[0]
    return CorroborationOutcome.CONFIRMED, resolutions[0]


def _field_outcome(code: str | None, stated: tuple[str, ...]) -> CorroborationOutcome:
    """Compare one exported code against what the catalog states for that ISIN.

    A code the export left empty is nothing to compare, and so is an ISIN the
    catalog holds no row for. Calling either a conflict would fail a run over a
    company nobody has a complaint about.
    """
    if not code or not stated:
        return CorroborationOutcome.NOT_COVERED
    return CorroborationOutcome.CONFIRMED if code in stated else CorroborationOutcome.CONFLICTED


def _counts(rows: Sequence[CorroborationRow]) -> tuple[int, int, int]:
    """Confirmed, conflicted and not-covered ISIN outcomes, in that order."""
    outcomes = [row.isin_outcome for row in rows]
    return (
        outcomes.count(CorroborationOutcome.CONFIRMED),
        outcomes.count(CorroborationOutcome.CONFLICTED),
        outcomes.count(CorroborationOutcome.NOT_COVERED),
    )
