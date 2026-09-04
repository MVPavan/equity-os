"""CLI composition for ``fundamentals screener-financials``.

Slice 1 of the Screener build. It mirrors ``screener-page`` deliberately —
identical refusal-before-the-network, identical no-clobber pre-flight, identical
evidence-before-metadata publishing order — because the two commands write into
the same tree and a caller should not have to learn two contracts.

What it adds is that the evidence is now plural: the page's bytes *and* every
schedule response that fed a number. Each is written and hash-verified before
the metadata that claims it exists, so a run that dies mid-sweep leaves readable
evidence and no durable claim about it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import structlog
from pydantic import BaseModel, ConfigDict

from fundamentals.api.artifact_writer import (
    preflight_out_paths,
    write_bytes_no_clobber,
    write_json_no_clobber,
)
from fundamentals.api.screener_page_cli import basis_topology
from fundamentals.api.watchlist_config import load_watchlist_config
from fundamentals.ingest.screener_financials import (
    ALL_SECTIONS,
    FinancialsRun,
    ScheduleDocument,
    read_financials,
)
from fundamentals.ingest.screener_financials_models import (
    ScheduleFamily,
    Section,
    family_key,
    reconciliation_is_proven,
)
from fundamentals.ingest.screener_session import ScreenerSessionSource
from fundamentals.ingest.screener_session_models import (
    Basis,
    PageOutcome,
    ScreenerCredentials,
    ScreenerPageFetch,
    ScreenerSessionConfig,
)

SCREENER_FINANCIALS_COMMAND = "screener-financials"

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_WATCHLIST_PATH = _REPO_ROOT / "config" / "watchlist.yaml"
_DEFAULT_OUT_ROOT = _REPO_ROOT / "data" / "raw" / "watchlist" / "screener-financials"

META_FILENAME = "screener_financials_meta.json"
PAGE_RAW_FILENAME = "screener_financials_page.raw.html"
SCHEDULES_DIRNAME = "schedules"
SECTION_FILENAME_TEMPLATE = "section_{section}.json"
FAILURES_FILENAME = "screener_financials_failures.json"
SCHEDULE_FILENAME_TEMPLATE = "{section}__{parent}.raw.json"
# A nested body named by section and parent alone would collide with its own
# parent's file, and the no-clobber write would then refuse the level-3 one —
# losing exactly the evidence the artifact's deepest claim rests on.
NESTED_SCHEDULE_FILENAME_TEMPLATE = "{section}__{parent}__{sub}.raw.json"

# ``blocks`` is period columns for a data-table section and ranges-tables for
# the growth section, which is what each of them is actually divided into.
_SECTION_HEADER = (
    "section\toutcome\tblocks\trows\tmodeled\tunmodeled\tinvalid\tquarantined\tschedules"
)
_SCHEDULE_HEADER = "schedule\tstrategy\treconciliation\tsub_rows\tperiods_checked\tnote"
_FAILURE_HEADER = "refused_schedule\trefusal\tdetail"
_INCOMPLETE_LINE = "INCOMPLETE\t{reason}"
_UNVERIFIED = "Screener identifiers for {symbol} are not verified: {fields}"
_HASH_MISMATCH = "retained bytes for {path} do not match their recorded sha256; refusing to publish"
_BASIS_UNAVAILABLE = (
    "screener served no {basis} basis for {symbol}: nothing was parsed and no artifact was written"
)
_SLUG_SEPARATOR = "-"
_UNSAFE_CHARACTERS = re.compile(r"[^a-z0-9]+")


class ScreenerFinancialsRun(BaseModel):
    """One acquisition: what was read, and where its evidence was written."""

    model_config = ConfigDict(frozen=True)

    run: FinancialsRun
    meta_path: Path
    page_path: Path
    section_paths: tuple[Path, ...]
    schedule_paths: tuple[Path, ...]


class ScreenerFinancialsRefused(BaseModel):
    """The page proved the requested basis is not published; nothing was parsed."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    basis: Basis


def add_screener_financials_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``fundamentals screener-financials`` command."""
    parser = subparsers.add_parser(
        SCREENER_FINANCIALS_COMMAND,
        help="acquire the financial sections and schedules of one watchlist stock",
    )
    parser.add_argument("--stock", required=True, help="watchlist NSE symbol, e.g. TITAN")
    parser.add_argument(
        "--basis",
        choices=tuple(basis.value for basis in Basis),
        default=Basis.CONSOLIDATED.value,
        help="which figures to request (default: consolidated)",
    )
    parser.add_argument(
        "--section",
        choices=tuple(section.value for section in ALL_SECTIONS),
        default=None,
        help="acquire one section only (default: every section)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="output directory (default: data/raw/watchlist/screener-financials/<stock>/<basis>)",
    )
    parser.add_argument("--config", default=str(_DEFAULT_WATCHLIST_PATH), help="watchlist.yaml")


def run_screener_financials_command(
    args: argparse.Namespace,
    *,
    credentials: ScreenerCredentials,
) -> ScreenerFinancialsRun | ScreenerFinancialsRefused:
    """Acquire one company's financial sections on one basis and publish them."""
    watchlist = load_watchlist_config(Path(args.config).resolve())
    try:
        stock = watchlist.stock(args.stock)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    unverified = stock.identifiers.unverified_screener_fields()
    if unverified:
        raise SystemExit(_UNVERIFIED.format(symbol=stock.symbol, fields=", ".join(unverified)))

    basis = Basis(args.basis)
    sections = (Section(args.section),) if args.section else ALL_SECTIONS
    out_dir = (
        Path(args.out).resolve() if args.out else _DEFAULT_OUT_ROOT / stock.symbol / basis.value
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    meta_path = out_dir / META_FILENAME
    failures_path = out_dir / FAILURES_FILENAME
    page_path = out_dir / PAGE_RAW_FILENAME
    section_paths = tuple(
        out_dir / SECTION_FILENAME_TEMPLATE.format(section=section.value) for section in sections
    )
    # Pre-flighted before the request, exactly as ``screener-page`` does:
    # refusing an existing artifact after the sweep would spend sixteen
    # rate-limited requests to discard their result. Schedule bodies are named
    # only by what the page turns out to offer, so they cannot be pre-flighted
    # here; each is written no-clobber in its own right.
    preflight_out_paths((page_path, meta_path, failures_path, *section_paths))

    source = ScreenerSessionSource(ScreenerSessionConfig(credentials=credentials))
    page_fetch = source.fetch_company_page(
        symbol=stock.symbol,
        slug=stock.identifiers.screener_slug,
        basis=basis,
        expected_company_id=stock.identifiers.screener_company_id,
        topology=basis_topology(stock),
    )
    if page_fetch.metadata.outcome is not PageOutcome.OK:
        return ScreenerFinancialsRefused(symbol=stock.symbol, basis=basis)

    run = read_financials(
        page_fetch,
        company_id=stock.identifiers.screener_company_id,
        sections=sections,
        source=source,
    )
    schedule_paths = _publish(
        run,
        page_fetch=page_fetch,
        out_dir=out_dir,
        page_path=page_path,
        meta_path=meta_path,
        failures_path=failures_path,
        section_paths=section_paths,
        sections=sections,
    )
    structlog.get_logger("fundamentals.screener_financials").info(
        "screener_financials_written",
        stock=stock.symbol,
        basis=basis.value,
        sections=len(sections),
        schedules=len(schedule_paths),
        complete=run.artifact.metadata.complete,
        path=str(meta_path),
    )
    return ScreenerFinancialsRun(
        run=run,
        meta_path=meta_path,
        page_path=page_path,
        section_paths=section_paths,
        schedule_paths=schedule_paths,
    )


def _publish(
    run: FinancialsRun,
    *,
    page_fetch: ScreenerPageFetch,
    out_dir: Path,
    page_path: Path,
    meta_path: Path,
    failures_path: Path,
    section_paths: tuple[Path, ...],
    sections: tuple[Section, ...],
) -> tuple[Path, ...]:
    """Write every piece of evidence, then the sections, then the metadata last.

    The metadata is the completion marker. It is published only once the bytes
    and the parsed sections it describes are on disk, so a failure part-way
    never leaves a durable claim pointing at evidence that does not exist — and,
    because writes are no-clobber, never blocks the retry that would fix it.

    Rollback removes only the paths *this* invocation created, and a path is
    recorded only once its write returned: pre-flight ran before the fetch, so
    another process may have published into this directory meanwhile, and
    unlinking by name would turn a no-clobber refusal into that process's
    evidence loss.
    """
    created: list[Path] = []
    schedule_paths: list[Path] = []
    try:
        _write_verified(page_path, page_fetch.raw_body, page_fetch.metadata.content_sha256)
        created.append(page_path)
        if run.schedule_documents:
            (out_dir / SCHEDULES_DIRNAME).mkdir(parents=True, exist_ok=True)
        for document in run.schedule_documents:
            path = out_dir / SCHEDULES_DIRNAME / _schedule_filename(document)
            _write_verified(path, document.raw_body, document.content_sha256)
            created.append(path)
            schedule_paths.append(path)
        if run.artifact.failures:
            write_json_no_clobber(
                failures_path,
                json.dumps(
                    [failure.model_dump(mode="json") for failure in run.artifact.failures],
                    indent=2,
                )
                + "\n",
            )
            created.append(failures_path)
        by_section = {table.section: table for table in run.artifact.sections}
        for section, path in zip(sections, section_paths, strict=True):
            write_json_no_clobber(path, by_section[section].model_dump_json(indent=2) + "\n")
            created.append(path)
        write_json_no_clobber(meta_path, run.artifact.metadata.model_dump_json(indent=2) + "\n")
        created.append(meta_path)
    except BaseException:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return tuple(schedule_paths)


def _write_verified(path: Path, payload: bytes, expected_sha256: str) -> None:
    """Write retained bytes and prove on disk that they are the bytes we hashed."""
    write_bytes_no_clobber(path, payload)
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha256:
        raise SystemExit(_HASH_MISMATCH.format(path=path))


def _schedule_filename(document: ScheduleDocument) -> str:
    """A filesystem-safe name for one retained schedule body.

    The parent label comes off the page, so it is reduced to a known-safe
    alphabet rather than trusted as a path component; the ``document_id`` inside
    the artifact remains the authoritative, verbatim address.
    """
    if document.expands is None:
        return SCHEDULE_FILENAME_TEMPLATE.format(
            section=document.section.value, parent=_slug(document.parent)
        )
    return NESTED_SCHEDULE_FILENAME_TEMPLATE.format(
        section=document.section.value,
        parent=_slug(document.expands),
        sub=_slug(document.parent),
    )


def _slug(text: str) -> str:
    """Reduce one label to lowercase alphanumerics joined by hyphens."""
    return _UNSAFE_CHARACTERS.sub(_SLUG_SEPARATOR, text.lower()).strip(_SLUG_SEPARATOR)


def basis_unavailable_message(refused: ScreenerFinancialsRefused) -> str:
    """The refusal text for a basis the company does not publish."""
    return _BASIS_UNAVAILABLE.format(basis=refused.basis.value, symbol=refused.symbol)


def render_screener_financials_summary(published: ScreenerFinancialsRun) -> str:
    """Render one deterministic block stating what was read and what reconciled."""
    artifact = published.run.artifact
    lines = [_SECTION_HEADER]
    for table in artifact.sections:
        statuses = [row.status.value for row in table.rows]
        # The growth section holds ranges-tables, not period rows. Counting its
        # (always empty) ``rows`` printed a line of zeros that read as "this
        # section came back empty", which is the opposite of what it means.
        blocks = len(table.growth_tables) or len(table.periods)
        rows = sum(len(block.rows) for block in table.growth_tables) or len(table.rows)
        lines.append(
            "\t".join(
                (
                    table.section.value,
                    table.outcome.value,
                    str(blocks),
                    str(rows),
                    str(statuses.count("modeled")),
                    str(statuses.count("unmodeled")),
                    str(statuses.count("invalid")),
                    str(len(table.quarantined)),
                    str(len(table.schedules)),
                )
            )
        )
    lines.append(_SCHEDULE_HEADER)
    for table in artifact.sections:
        for family in table.schedules:
            lines.append(_schedule_line(family))
            lines.extend(_schedule_line(child) for child in family.nested)
    if artifact.failures:
        lines.append(_FAILURE_HEADER)
        for failure in artifact.failures:
            lines.append(
                "\t".join(
                    (
                        family_key(failure.section, failure.parent, failure.expands),
                        failure.refusal,
                        failure.detail,
                    )
                )
            )
    if not artifact.metadata.complete:
        lines.append(_INCOMPLETE_LINE.format(reason=artifact.metadata.incomplete_reason))
    return "\n".join(lines)


def _schedule_line(family: ScheduleFamily) -> str:
    """One summary row for a family, keyed the same three ways its body is named."""
    return "\t".join(
        (
            family_key(family.section, family.parent, family.expands),
            family.strategy.value,
            family.reconciliation.value,
            str(len(family.sub_rows)),
            str(len(family.comparisons)),
            family.reconciliation_note,
        )
    )


def is_incomplete(published: ScreenerFinancialsRun) -> bool:
    """True when the schedule sweep did not finish, so the artifact is partial."""
    return not published.run.artifact.metadata.complete


def unreconciled_families(published: ScreenerFinancialsRun) -> tuple[str, ...]:
    """Families the reconciliation gate did not actually clear.

    ``NOT_APPLICABLE`` is excluded because it is a positive result: a registered
    shape, carrying all of its required rows, that a sum would not describe.
    Everything else here is a gate that did not run — an unrecognised shape,
    sub-rows that aligned to no page column, an empty response, or a page row
    with nothing readable to compare against — and naming them keeps ``ok`` from
    covering any of it.

    This shares :func:`reconciliation_is_proven` with the artifact's ``verified``
    flag on purpose, so the file on disk can never disagree with the exit code
    the caller saw.
    """
    return tuple(
        family_key(family.section, family.parent, family.expands)
        for table in published.run.artifact.sections
        for parent_family in table.schedules
        for family in (parent_family, *parent_family.nested)
        if not reconciliation_is_proven(family.reconciliation)
    )


def refused_families(published: ScreenerFinancialsRun) -> tuple[str, ...]:
    """Families whose response was retained but refused outright."""
    return tuple(
        family_key(failure.section, failure.parent, failure.expands)
        for failure in published.run.artifact.failures
    )
