"""The ``upstox-crosscheck`` command: Lane B's log-only differential check.

    upstox-crosscheck --isin-file <path> --screener-root <dir> --out-dir <dir>
                      [--basis standalone|consolidated|both] [--upstox-root <dir>]

**Nothing this command produces is a fact.** Upstox and Screener share upstream
lineage, which disqualifies Upstox from corroborating Screener and is exactly
what makes it useful for detecting *extraction drift*. A disagreement gives a
triage direction, never a diagnosis, so the exit code ignores every mismatch it
finds. Only a parse failure — a response this repo could not read — is non-zero.

**Two guards decide whether to call at all, and both exist because of one live
finding.** An unknown ISIN answers ``{"status":"success","data":[]}`` with HTTP
200, byte-identical to a real company with nothing to report. No envelope check
can separate them, so the separation has to happen before the request:

1. the ISIN must carry a valid ISO 6166 check digit, and
2. the ``--screener-root`` must already hold that company's sections.

A company failing either is recorded as skipped and never requested. The second
guard also happens to be the honest one: there is nothing to compare against.

**``--isin-file`` is a two-column TSV**, ``<isin>\\t<symbol>``. Screener knows
companies by NSE symbol and Upstox by ISIN, and neither artifact carries the
other's key, so the join is stated explicitly in a file a human can audit rather
than inferred at run time.

**Screener layout** follows ``screener-financials``' own default:
``<screener-root>/<symbol>/<basis>/section_<name>.json``. Three sections are
read — ``profit-loss``, ``balance-sheet``, ``cash-flow`` — and a row label
appearing in more than one of them is refused rather than resolved, because
which section a value came from would then depend on file order.

Only annual figures are compared. ``balance-sheet`` and ``cash-flow`` discard
``time_period`` outright, and under a quarterly ``income-statement`` request the
two blocks of one payload carry different periodicities under the same period
labels — so a quarterly comparison would need a different alignment than this
one and is deliberately not offered.

**Every fetched body is retained before it is interpreted**, under
``<out-dir>/upstox/<symbol>/<basis>/<surface>.raw.json`` beside a
``.meta.json`` recording the URL, hash, size, retrieval time and route key it
came with. A sweep costs authenticated requests against a rate-limited vendor,
so the bytes are kept whatever the reader made of them: a response that drifted
past the parser is the one most worth re-reading.

``--upstox-root <dir>`` replays such a tree instead of fetching. No request is
made and no credential is asked for, each body is checked against the hash
recorded beside it before it is parsed, and a company with nothing retained is
skipped rather than fetched behind the operator's back.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import structlog
from pydantic import BaseModel, ConfigDict, ValidationError

from fundamentals.api.artifact_writer import (
    preflight_out_paths,
    safe_subdirectory,
    write_bytes_no_clobber,
    write_json_no_clobber,
)
from fundamentals.api.screener_cli_dispatch import EXIT_REFUSED
from fundamentals.api.upstox_cli import SourceLike
from fundamentals.ingest.upstox_crosscheck import (
    AMBIGUOUS_ROW_MESSAGE,
    COMPARED_SECTIONS,
    EXIT_UNREADABLE,
    CompanyCrosscheck,
    CompanyStatus,
    CrosscheckRunReport,
    ScreenerSection,
    compare_company,
)

# The command's exit code and summary header are the comparison's, re-exported
# unaliased so a caller of this command reads them from the command.
from fundamentals.ingest.upstox_crosscheck import EXIT_OK as EXIT_OK
from fundamentals.ingest.upstox_crosscheck import SUMMARY_HEADER as SUMMARY_HEADER
from fundamentals.ingest.upstox_source import (
    AcquisitionOutcome,
    UpstoxCapture,
    UpstoxConfig,
    UpstoxCredentials,
    UpstoxError,
    UpstoxFetch,
    UpstoxSource,
    UpstoxSurface,
    route_for,
)
from fundamentals.ingest.upstox_statements import (
    StatementBasis,
    read_balance_sheet,
    read_cash_flow,
    read_income_statement,
)

_LOGGER = structlog.get_logger(__name__)

UPSTOX_CROSSCHECK_COMMAND = "upstox-crosscheck"
REPORT_FILENAME = "upstox_crosscheck_report.json"

BOTH_BASES = "both"
BASIS_QUERY_KEY = "type"
FULL_STATEMENT_QUERY_KEY = "fs"
FULL_STATEMENT_QUERY_VALUE = "true"

SECTION_FILENAME_TEMPLATE = "section_{section}.json"

# The three statement surfaces one company is asked for, in the order they are
# fetched, retained and replayed.
STATEMENT_SURFACES: tuple[UpstoxSurface, ...] = (
    UpstoxSurface.INCOME_STATEMENT,
    UpstoxSurface.BALANCE_SHEET,
    UpstoxSurface.CASH_FLOW,
)

RETENTION_DIRNAME = "upstox"
RAW_FILENAME_TEMPLATE = "{surface}.raw.json"
META_FILENAME_TEMPLATE = "{surface}.meta.json"
# What a retained body was when it was retained: every kept response was a
# readable 200 of JSON, and the parsers read neither field.
_RETAINED_HTTP_STATUS = 200
_RETAINED_MEDIA_TYPE = "application/json"

# A symbol names a directory under both --screener-root and --upstox-root, so it
# has to be one path segment and not a relative one.
_PATH_SEPARATORS = ("/", "\\")
_UNSAFE_SEGMENTS = frozenset({".", ".."})

_ISIN_LENGTH = 12
_ISIN_COUNTRY_LENGTH = 2
_ALPHABET_OFFSET = 55  # ord("A") - 10, so "A" expands to 10 and "Z" to 35.

_REFUSED_EVENT = "upstox_crosscheck_refused"

_HELP = "compare Upstox statement values against Screener's, log-only"
_ISIN_FILE_HELP = "two-column TSV: <isin>\\t<nse symbol>, one company per line"
_SCREENER_ROOT_HELP = "root of screener-financials output: <root>/<symbol>/<basis>/"
_OUT_DIR_HELP = "directory the disagreement report is written to"
_BASIS_HELP = "which set of books to compare (default: consolidated)"
_UPSTOX_ROOT_HELP = "replay bodies retained by an earlier run instead of fetching"

_BAD_LINE = "{path} line {number}: expected <isin>\\t<symbol>, got {line!r}"
_REPEATED = "{path} line {number}: isin {isin} is repeated"
_EMPTY_FILE = "{path} holds no isin/symbol lines"
_REPEATED_SYMBOL = (
    "{path} line {number}: symbol {symbol} is repeated; two companies cannot retain "
    "into one directory"
)
_UNSAFE_SYMBOL = "{path} line {number}: symbol {symbol!r} is not a plain directory name"
_UNREADABLE_SECTION = "{path} is not readable as a screener section: {reason}"
_TAMPERED_BODY = "{path}: bytes hash to {found}, but the record beside them says {recorded}"
_UNREADABLE_META = "{path} is not readable as a retention record: {reason}"
_TORN_RETENTION = "{directory} holds {held} of {expected} surfaces; a torn capture is not a replay"


class RetainedBodyError(UpstoxError):
    """A retained body no longer matches the record written beside it.

    A replayed body is evidence only while the hash recorded with it still
    covers the bytes on disk. Reported as a response this repo could not read,
    because that is what an unverifiable body is.
    """


class RetainedBody(BaseModel):
    """The record written beside one retained body.

    Exactly the capture-bound fields ``_DocumentHeader`` carries, so a replayed
    document is indistinguishable from the one the live run read.
    """

    model_config = ConfigDict(frozen=True)

    source_url: str
    content_sha256: str
    byte_count: int
    retrieved_at: datetime
    route_key: str


def add_upstox_crosscheck_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register ``upstox-crosscheck`` and its five flags."""
    parser = subparsers.add_parser(UPSTOX_CROSSCHECK_COMMAND, help=_HELP)
    parser.add_argument("--isin-file", required=True, help=_ISIN_FILE_HELP)
    parser.add_argument("--screener-root", required=True, help=_SCREENER_ROOT_HELP)
    parser.add_argument("--out-dir", required=True, help=_OUT_DIR_HELP)
    parser.add_argument(
        "--basis",
        choices=(StatementBasis.STANDALONE.value, StatementBasis.CONSOLIDATED.value, BOTH_BASES),
        default=StatementBasis.CONSOLIDATED.value,
        help=_BASIS_HELP,
    )
    parser.add_argument("--upstox-root", default=None, help=_UPSTOX_ROOT_HELP)


def is_valid_isin(isin: str) -> bool:
    """Whether a string is a well-formed ISIN with a correct ISO 6166 check digit.

    The only guard that can precede the request. An unknown ISIN answers with a
    successful empty payload, so a malformed one must never reach the wire —
    the response would look exactly like a real company with nothing to report.
    """
    if len(isin) != _ISIN_LENGTH or not isin.isalnum() or not isin.isupper():
        return False
    if not isin[:_ISIN_COUNTRY_LENGTH].isalpha() or not isin[-1].isdigit():
        return False
    digits = "".join(
        character if character.isdigit() else str(ord(character) - _ALPHABET_OFFSET)
        for character in isin[:-1]
    )
    total = 0
    for position, digit in enumerate(reversed(digits)):
        value = int(digit)
        if position % 2 == 0:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return (10 - total % 10) % 10 == int(isin[-1])


def read_isin_file(path: Path) -> tuple[tuple[str, str], ...]:
    """Read the ``<isin>\\t<symbol>`` join, refusing anything it cannot read exactly.

    A repeated ISIN is refused rather than de-duplicated: the same company under
    two symbols is a mistake in the join, and comparing it twice would double
    its weight in every count the report carries. A repeated symbol is refused
    for a second reason — both companies would retain their bodies into one
    directory, so the collision would only surface mid-run with requests already
    spent. A symbol that is not a plain directory name is refused outright: it
    is used to address two trees, and neither may be climbed out of.
    """
    pairs: list[tuple[str, str]] = []
    seen: dict[str, int] = {}
    symbols: dict[str, int] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
            raise SystemExit(_BAD_LINE.format(path=path, number=number, line=line))
        isin, symbol = parts[0].strip(), parts[1].strip()
        if isin in seen:
            raise SystemExit(_REPEATED.format(path=path, number=number, isin=isin))
        if symbol in _UNSAFE_SEGMENTS or any(part in symbol for part in _PATH_SEPARATORS):
            raise SystemExit(_UNSAFE_SYMBOL.format(path=path, number=number, symbol=symbol))
        if symbol in symbols:
            raise SystemExit(_REPEATED_SYMBOL.format(path=path, number=number, symbol=symbol))
        seen[isin] = number
        symbols[symbol] = number
        pairs.append((isin, symbol))
    if not pairs:
        raise SystemExit(_EMPTY_FILE.format(path=path))
    return tuple(pairs)


def run_upstox_crosscheck_command(
    args: argparse.Namespace,
    *,
    isin_file: Path,
    screener_root: Path,
    out_dir: Path,
    source: SourceLike,
    upstox_root: Path | None = None,
) -> CrosscheckRunReport:
    """Compare every listed company on every requested basis and write one report.

    With ``upstox_root`` the bodies come from an earlier run's retention tree and
    ``source`` is never asked for anything; without it every fetched body is
    retained under ``out_dir`` before it is read.

    Every path the run intends to write is preflighted before the first request.
    A no-clobber refusal is correct but arrives mid-loop, and by then a live run
    has spent authenticated calls it cannot get back and has written no report
    to show for them.
    """
    bases = _requested_bases(str(args.basis))
    pairs = read_isin_file(isin_file)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / REPORT_FILENAME
    retained = () if upstox_root is not None else _retention_paths(out_dir, pairs, bases)
    preflight_out_paths((report_path, *retained))

    companies: list[CompanyCrosscheck] = []
    for isin, symbol in pairs:
        for basis in bases:
            companies.append(
                _crosscheck_company(
                    isin=isin,
                    symbol=symbol,
                    basis=basis,
                    screener_root=screener_root,
                    source=source,
                    out_dir=out_dir,
                    upstox_root=upstox_root,
                )
            )
    run = CrosscheckRunReport(
        companies=tuple(companies),
        upstox_root=str(upstox_root) if upstox_root is not None else None,
        retained_under=None if upstox_root is not None else str(out_dir / RETENTION_DIRNAME),
    )
    write_json_no_clobber(report_path, run.model_dump_json(indent=2) + "\n")
    _LOGGER.info(
        "upstox_crosscheck_written",
        companies=len(run.companies),
        mismatches=run.mismatch_count,
        anomalies=run.anomaly_count,
        unmet_tier3=run.unmet_tier3_count,
        unreadable=run.unreadable_count,
    )
    return run


def _retention_paths(
    out_dir: Path,
    pairs: tuple[tuple[str, str], ...],
    bases: tuple[StatementBasis, ...],
) -> tuple[Path, ...]:
    """Every file a live run would retain, listed before the first one is fetched.

    Companies this run will skip are included: their paths do not exist, so they
    cost the preflight nothing, and leaving them out would make the guard depend
    on which guard fires later.
    """
    return tuple(
        directory / template.format(surface=surface.value)
        for _, symbol in pairs
        for basis in bases
        for directory in (out_dir / RETENTION_DIRNAME / symbol / basis.value,)
        for surface in STATEMENT_SURFACES
        for template in (RAW_FILENAME_TEMPLATE, META_FILENAME_TEMPLATE)
    )


def _requested_bases(requested: str) -> tuple[StatementBasis, ...]:
    """Expand ``--basis``, keeping a stable order so the report is comparable."""
    if requested == BOTH_BASES:
        return (StatementBasis.STANDALONE, StatementBasis.CONSOLIDATED)
    return (StatementBasis(requested),)


def _crosscheck_company(
    *,
    isin: str,
    symbol: str,
    basis: StatementBasis,
    screener_root: Path,
    source: SourceLike,
    out_dir: Path,
    upstox_root: Path | None,
) -> CompanyCrosscheck:
    """Run both pre-call guards, obtain the three bodies, then compare them."""
    if not is_valid_isin(isin):
        return CompanyCrosscheck(
            isin=isin,
            symbol=symbol,
            basis=basis.value,
            status=CompanyStatus.SKIPPED_INVALID_ISIN,
            detail="check digit does not verify; an unknown ISIN answers 200 with an "
            "empty payload, so it is never requested",
        )
    directory = screener_root / symbol / basis.value
    sections = _load_screener_sections(directory)
    if sections is None:
        return CompanyCrosscheck(
            isin=isin,
            symbol=symbol,
            basis=basis.value,
            status=CompanyStatus.SKIPPED_NO_SCREENER_DATA,
            detail=f"no screener sections under {directory}",
        )

    if upstox_root is None:
        bodies = _fetch_and_retain(
            isin=isin, symbol=symbol, basis=basis, source=source, out_dir=out_dir
        )
    else:
        retained = upstox_root / symbol / basis.value
        replayed = read_retained_bodies(retained)
        if replayed is None:
            return CompanyCrosscheck(
                isin=isin,
                symbol=symbol,
                basis=basis.value,
                status=CompanyStatus.SKIPPED_NO_UPSTOX_DATA,
                detail=f"no retained bodies under {retained}",
            )
        bodies = replayed

    return compare_company(
        isin=isin,
        symbol=symbol,
        basis=basis,
        sections=sections,
        income=read_income_statement(bodies[UpstoxSurface.INCOME_STATEMENT], requested_basis=basis),
        balance=read_balance_sheet(bodies[UpstoxSurface.BALANCE_SHEET], requested_basis=basis),
        cash=read_cash_flow(bodies[UpstoxSurface.CASH_FLOW], requested_basis=basis),
    )


def _fetch_and_retain(
    *,
    isin: str,
    symbol: str,
    basis: StatementBasis,
    source: SourceLike,
    out_dir: Path,
) -> dict[UpstoxSurface, UpstoxFetch]:
    """Fetch each statement surface, writing every body down before anything reads it.

    Retention precedes interpretation on purpose. A response the parser refuses
    is the one worth re-reading, and re-fetching it costs an authenticated call
    against a rate-limited vendor — which is exactly what is unavailable once
    the vendor has restated the figure.
    """
    query = {BASIS_QUERY_KEY: basis.value, FULL_STATEMENT_QUERY_KEY: FULL_STATEMENT_QUERY_VALUE}
    directory = _retention_directory(out_dir, symbol, basis)
    fetched: dict[UpstoxSurface, UpstoxFetch] = {}
    for surface in STATEMENT_SURFACES:
        fetch = source.fetch(route_for(surface), query, isin=isin)
        _retain(directory, fetch)
        fetched[surface] = fetch
    return fetched


def _retention_directory(out_dir: Path, symbol: str, basis: StatementBasis) -> Path:
    """Create ``<out-dir>/upstox/<symbol>/<basis>/`` one plain child at a time.

    The symbol comes from the operator's join file, so each level is created
    through the writer's own guard rather than by one ``mkdir`` of a path that
    could carry a symlink or climb out of the output directory.
    """
    retained = safe_subdirectory(out_dir, RETENTION_DIRNAME)
    return safe_subdirectory(safe_subdirectory(retained, symbol), basis.value)


def _retain(directory: Path, fetch: UpstoxFetch) -> None:
    """Write one body verbatim, beside the record that binds the bytes to their fetch."""
    capture = fetch.capture
    surface = capture.surface.value
    write_bytes_no_clobber(
        directory / RAW_FILENAME_TEMPLATE.format(surface=surface), fetch.raw_body
    )
    record = RetainedBody(
        source_url=capture.request_url,
        content_sha256=capture.content_sha256,
        byte_count=capture.byte_count,
        retrieved_at=capture.retrieved_at,
        route_key=capture.route_key,
    )
    write_json_no_clobber(
        directory / META_FILENAME_TEMPLATE.format(surface=surface),
        record.model_dump_json(indent=2) + "\n",
    )


def read_retained_bodies(directory: Path) -> dict[UpstoxSurface, UpstoxFetch] | None:
    """Read one company's retained bodies, or ``None`` when the tree holds none.

    An absent company is a skip rather than a failure: a retention tree
    assembled from several runs will not cover every company in a later join
    file, and refusing the whole run for that would make replay useless. A
    company holding some surfaces but not all is a different thing — a torn
    capture, where the missing third is exactly what a comparison would need —
    and is refused, as is a body that no longer hashes to what was recorded
    beside it.
    """
    held = tuple(surface for surface in STATEMENT_SURFACES if _is_retained(directory, surface))
    if not held:
        return None
    if len(held) != len(STATEMENT_SURFACES):
        raise RetainedBodyError(
            _TORN_RETENTION.format(
                directory=directory, held=len(held), expected=len(STATEMENT_SURFACES)
            )
        )

    bodies: dict[UpstoxSurface, UpstoxFetch] = {}
    for surface in STATEMENT_SURFACES:
        raw_path = directory / RAW_FILENAME_TEMPLATE.format(surface=surface.value)
        raw = raw_path.read_bytes()
        record = _read_retained_record(
            directory / META_FILENAME_TEMPLATE.format(surface=surface.value)
        )
        digest = hashlib.sha256(raw).hexdigest()
        if digest != record.content_sha256 or len(raw) != record.byte_count:
            raise RetainedBodyError(
                _TAMPERED_BODY.format(path=raw_path, found=digest, recorded=record.content_sha256)
            )
        bodies[surface] = UpstoxFetch(
            raw_body=raw,
            capture=UpstoxCapture(
                surface=surface,
                route_key=record.route_key,
                request_url=record.source_url,
                http_status=_RETAINED_HTTP_STATUS,
                media_type=_RETAINED_MEDIA_TYPE,
                byte_count=record.byte_count,
                content_sha256=record.content_sha256,
                outcome=AcquisitionOutcome.OK,
                retrieved_at=record.retrieved_at,
            ),
        )
    return bodies


def _is_retained(directory: Path, surface: UpstoxSurface) -> bool:
    """Whether both halves of one retained surface are present."""
    return (directory / RAW_FILENAME_TEMPLATE.format(surface=surface.value)).is_file() and (
        directory / META_FILENAME_TEMPLATE.format(surface=surface.value)
    ).is_file()


def _read_retained_record(path: Path) -> RetainedBody:
    """Read one ``.meta.json``, refusing a record this run cannot check a body against.

    Read as bytes: a record that is not valid UTF-8 is a record this run cannot
    verify a body against, which is the refusal it already has — not a decoding
    traceback out of a command.
    """
    try:
        return RetainedBody.model_validate_json(path.read_bytes())
    except ValidationError as error:
        raise RetainedBodyError(
            _UNREADABLE_META.format(path=path, reason=error.errors()[0]["msg"])
        ) from error


def _load_screener_sections(directory: Path) -> dict[str, ScreenerSection] | None:
    """Read one company's Screener sections, keyed by section name.

    ``None`` means no section was found at all, which is the second pre-call
    guard: there is nothing to compare against, so nothing is requested. A row
    label carried by two sections is refused rather than resolved, because which
    section a value came from would then depend on file order.
    """
    sections: dict[str, ScreenerSection] = {}
    origin: dict[str, str] = {}
    for section in COMPARED_SECTIONS:
        path = directory / SECTION_FILENAME_TEMPLATE.format(section=section)
        if not path.is_file():
            continue
        try:
            table = ScreenerSection.model_validate_json(path.read_text(encoding="utf-8"))
        except ValidationError as error:
            raise SystemExit(
                _UNREADABLE_SECTION.format(path=path, reason=error.errors()[0]["msg"])
            ) from error
        for row in table.rows:
            if origin.setdefault(row.label, section) != section:
                raise SystemExit(
                    AMBIGUOUS_ROW_MESSAGE.format(
                        label=row.label, first=origin[row.label], second=section
                    )
                )
        sections[section] = table
    return sections or None


def dispatch_upstox_crosscheck_command(
    args: argparse.Namespace,
    *,
    credentials_factory: Callable[[], UpstoxCredentials | None],
) -> int | None:
    """Run ``upstox-crosscheck`` and return its exit code, or ``None`` for another command.

    Every Lane B surface is authenticated, so a token-free run refuses here
    rather than issuing ten requests that will each come back 401. A replay
    reaches no surface at all, so it never asks for the token: ``--upstox-root``
    and live fetching are exclusive, and this is where that is enforced.
    """
    if getattr(args, "command", None) != UPSTOX_CROSSCHECK_COMMAND:
        return None
    upstox_root = Path(args.upstox_root) if args.upstox_root else None
    credentials = None if upstox_root is not None else credentials_factory()
    source = UpstoxSource(UpstoxConfig(credentials=credentials))
    try:
        run = run_upstox_crosscheck_command(
            args,
            isin_file=Path(args.isin_file),
            screener_root=Path(args.screener_root),
            out_dir=Path(args.out_dir),
            source=source,
            upstox_root=upstox_root,
        )
    except RetainedBodyError as refusal:
        _LOGGER.warning(
            _REFUSED_EVENT, refusal=type(refusal).__name__, detail=source.redact(str(refusal))
        )
        return EXIT_UNREADABLE
    except UpstoxError as refusal:
        _LOGGER.warning(
            _REFUSED_EVENT, refusal=type(refusal).__name__, detail=source.redact(str(refusal))
        )
        return EXIT_REFUSED
    sys.stdout.write(run.render() + "\n")
    return run.exit_code
