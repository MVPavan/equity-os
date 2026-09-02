"""CLI composition for ``fundamentals screener-company``.

Slice 2 of the Screener build. It mirrors ``screener-financials`` deliberately —
identical refusal-before-the-network, identical no-clobber pre-flight, identical
evidence-before-metadata publishing order — because the three Screener commands
write into the same tree and a caller should not have to learn three contracts.

What it adds is the evidence *class* per document. Most of what this command
acquires cannot be proven at all (see
:class:`~fundamentals.ingest.screener_company_models.EvidenceClass`), so the
summary names each part's class and its key check result, and the metadata lists
every document under the class it earned. A ``BOUNDED`` or ``URL_ONLY`` document
is reported and does not fail the run; anything that *could* be checked and
failed is a refusal with its body retained.
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
    safe_subdirectory,
    write_bytes_no_clobber,
    write_json_no_clobber,
)
from fundamentals.api.screener_page_cli import basis_topology
from fundamentals.api.watchlist_config import load_watchlist_config
from fundamentals.ingest.screener_company import CompanyRun, read_company
from fundamentals.ingest.screener_company_artifacts import (
    CompanyArtifact,
)
from fundamentals.ingest.screener_company_models import ALL_PARTS, CompanyPart
from fundamentals.ingest.screener_company_sweep import CompanyDocument
from fundamentals.ingest.screener_session import ScreenerSessionSource
from fundamentals.ingest.screener_session_models import (
    Basis,
    PageOutcome,
    ScreenerCredentials,
    ScreenerPageFetch,
    ScreenerSessionConfig,
)

SCREENER_COMPANY_COMMAND = "screener-company"

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_WATCHLIST_PATH = _REPO_ROOT / "config" / "watchlist.yaml"
_DEFAULT_OUT_ROOT = _REPO_ROOT / "data" / "raw" / "watchlist" / "screener-company"

META_FILENAME = "screener_company_meta.json"
PAGE_RAW_FILENAME = "screener_company_page.raw.html"
FAILURES_FILENAME = "screener_company_failures.json"
DOCUMENTS_DIRNAME = "documents"
PART_FILENAME_TEMPLATE = "part_{part}.json"
DOCUMENT_FILENAME_TEMPLATE = "{part}__{name}.raw.{extension}"

_PART_HEADER = "part\toffered\tdocuments\tdetail"
_EVIDENCE_HEADER = "document\tbinding\tvalidation\tstatus"
_CHECK_HEADER = "document\tcheck\tresult"
_FAILURE_HEADER = "refused_document\trefusal\tdetail"
_WEAK_HEADER = "weak_document\tbinding\tvalidation"
_UNSAFE_DOCUMENTS_DIR = (
    "refusing to write retained bodies into {path}: it is not a plain directory this run "
    "created inside the output directory"
)
_INCOMPLETE_LINE = "INCOMPLETE\t{reason}"
_UNVERIFIED = "Screener identifiers for {symbol} are not verified: {fields}"
_HASH_MISMATCH = "retained bytes for {path} do not match their recorded sha256; refusing to publish"
_BASIS_UNAVAILABLE = (
    "screener served no {basis} basis for {symbol}: nothing was parsed and no artifact was written"
)
_ABSENT = "-"
_SLUG_SEPARATOR = "-"
_UNSAFE_CHARACTERS = re.compile(r"[^a-z0-9]+")


class ScreenerCompanyRun(BaseModel):
    """One acquisition: what was read, and where its evidence was written."""

    model_config = ConfigDict(frozen=True)

    run: CompanyRun
    meta_path: Path
    page_path: Path
    part_paths: tuple[Path, ...]
    document_paths: tuple[Path, ...]


class ScreenerCompanyRefused(BaseModel):
    """The page proved the requested basis is not published; nothing was parsed."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    basis: Basis


def add_screener_company_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``fundamentals screener-company`` command."""
    parser = subparsers.add_parser(
        SCREENER_COMPANY_COMMAND,
        help="acquire the shareholding, segments, modal, peers and ratio documents of one stock",
    )
    parser.add_argument("--stock", required=True, help="watchlist NSE symbol, e.g. TITAN")
    parser.add_argument(
        "--basis",
        choices=tuple(basis.value for basis in Basis),
        default=Basis.CONSOLIDATED.value,
        help="which figures to request (default: consolidated)",
    )
    parser.add_argument(
        "--part",
        choices=tuple(part.value for part in ALL_PARTS),
        default=None,
        help="acquire one part only (default: every part)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="output directory (default: data/raw/watchlist/screener-company/<stock>/<basis>)",
    )
    parser.add_argument("--config", default=str(_DEFAULT_WATCHLIST_PATH), help="watchlist.yaml")


def run_screener_company_command(
    args: argparse.Namespace,
    *,
    credentials: ScreenerCredentials,
) -> ScreenerCompanyRun | ScreenerCompanyRefused:
    """Acquire one company's sub-documents on one basis and publish them."""
    watchlist = load_watchlist_config(Path(args.config).resolve())
    try:
        stock = watchlist.stock(args.stock)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    unverified = stock.identifiers.unverified_screener_fields()
    if unverified:
        raise SystemExit(_UNVERIFIED.format(symbol=stock.symbol, fields=", ".join(unverified)))

    basis = Basis(args.basis)
    parts = (CompanyPart(args.part),) if args.part else ALL_PARTS
    out_dir = (
        Path(args.out).resolve() if args.out else _DEFAULT_OUT_ROOT / stock.symbol / basis.value
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    meta_path = out_dir / META_FILENAME
    failures_path = out_dir / FAILURES_FILENAME
    page_path = out_dir / PAGE_RAW_FILENAME
    part_paths = tuple(out_dir / PART_FILENAME_TEMPLATE.format(part=part.value) for part in parts)
    # Pre-flighted before the request, exactly as the other two Screener
    # commands do: refusing an existing artifact after the sweep would spend
    # nineteen rate-limited requests to discard their result. Sub-document
    # bodies are named only by what the page turns out to offer, so they cannot
    # be pre-flighted here; each is written no-clobber in its own right.
    preflight_out_paths((page_path, meta_path, failures_path, *part_paths))

    source = ScreenerSessionSource(ScreenerSessionConfig(credentials=credentials))
    page_fetch = source.fetch_company_page(
        symbol=stock.symbol,
        slug=stock.identifiers.screener_slug,
        basis=basis,
        expected_company_id=stock.identifiers.screener_company_id,
        topology=basis_topology(stock),
    )
    if page_fetch.metadata.outcome is not PageOutcome.OK:
        return ScreenerCompanyRefused(symbol=stock.symbol, basis=basis)

    run = read_company(
        page_fetch,
        company_id=stock.identifiers.screener_company_id,
        parts=parts,
        source=source,
    )
    document_paths = _publish(
        run,
        page_fetch=page_fetch,
        out_dir=out_dir,
        page_path=page_path,
        meta_path=meta_path,
        failures_path=failures_path,
        part_paths=part_paths,
        parts=parts,
    )
    structlog.get_logger("fundamentals.screener_company").info(
        "screener_company_written",
        stock=stock.symbol,
        basis=basis.value,
        parts=len(parts),
        documents=len(document_paths),
        requests=run.artifact.metadata.request_count,
        complete=run.artifact.metadata.complete,
        path=str(meta_path),
    )
    return ScreenerCompanyRun(
        run=run,
        meta_path=meta_path,
        page_path=page_path,
        part_paths=part_paths,
        document_paths=document_paths,
    )


def _publish(
    run: CompanyRun,
    *,
    page_fetch: ScreenerPageFetch,
    out_dir: Path,
    page_path: Path,
    meta_path: Path,
    failures_path: Path,
    part_paths: tuple[Path, ...],
    parts: tuple[CompanyPart, ...],
) -> tuple[Path, ...]:
    """Write every piece of evidence, then the parts, then the metadata last.

    The metadata is the completion marker. It is published only once the bytes
    and the parsed parts it describes are on disk, so a failure part-way never
    leaves a durable claim pointing at evidence that does not exist — and,
    because writes are no-clobber, never blocks the retry that would fix it.

    Rollback removes only the paths *this* invocation created, and a path is
    recorded only once its write returned: pre-flight ran before the fetch, so
    another process may have published into this directory meanwhile, and
    unlinking by name would turn a no-clobber refusal into that process's
    evidence loss.
    """
    created: list[Path] = []
    document_paths: list[Path] = []
    try:
        _write_verified(page_path, page_fetch.raw_body, page_fetch.metadata.content_sha256)
        created.append(page_path)
        if run.documents:
            _safe_documents_dir(out_dir)
        for document in run.documents:
            path = out_dir / DOCUMENTS_DIRNAME / _document_filename(document)
            _write_verified(path, document.raw_body, document.content_sha256)
            created.append(path)
            document_paths.append(path)
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
        for part, path in zip(parts, part_paths, strict=True):
            write_json_no_clobber(path, _part_payload(run.artifact, part))
            created.append(path)
        write_json_no_clobber(meta_path, run.artifact.metadata.model_dump_json(indent=2) + "\n")
        created.append(meta_path)
    except BaseException:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return tuple(document_paths)


def _part_payload(artifact: CompanyArtifact, part: CompanyPart) -> str:
    """Serialise everything one part produced, outcome included.

    A part file always carries its outcome, even when the part was not offered:
    a reader that finds an empty ``investors`` file must be able to tell "this
    company publishes no drill-downs" from "the run never got there".
    """
    outcome = next(
        (found for found in artifact.outcomes if found.part is part),
        None,
    )
    payload: dict[str, object] = {
        "part": part.value,
        "outcome": None if outcome is None else outcome.model_dump(mode="json"),
    }
    if part is CompanyPart.INVESTORS:
        payload["shareholding"] = [table.model_dump(mode="json") for table in artifact.shareholding]
        payload["buckets"] = [bucket.model_dump(mode="json") for bucket in artifact.investors]
    elif part is CompanyPart.SEGMENTS:
        payload["tables"] = [table.model_dump(mode="json") for table in artifact.segments]
    elif part is CompanyPart.RELATED_PARTY:
        payload["related_party"] = (
            None
            if artifact.related_party is None
            else artifact.related_party.model_dump(mode="json")
        )
    elif part is CompanyPart.CORPORATE_ACTIONS:
        payload["corporate_actions"] = (
            None
            if artifact.corporate_actions is None
            else artifact.corporate_actions.model_dump(mode="json")
        )
    elif part is CompanyPart.PEERS:
        payload["peers"] = (
            None if artifact.peers is None else artifact.peers.model_dump(mode="json")
        )
    else:
        payload["quick_ratios"] = [entry.model_dump(mode="json") for entry in artifact.quick_ratios]
    return json.dumps(payload, indent=2) + "\n"


def _safe_documents_dir(out_dir: Path) -> Path:
    """Create, or accept, the directory retained bodies are written into.

    No-clobber protects a file that already exists; it does nothing about the
    directory holding it. A ``documents`` symlink planted beforehand would send
    every retained response somewhere the caller never named, and each write
    would succeed because the files inside are new. So the path must be one this
    run created, or a plain directory already sitting inside the output
    directory — never a link, and never a link's target.
    """
    try:
        return safe_subdirectory(out_dir, DOCUMENTS_DIRNAME)
    except SystemExit as error:
        raise SystemExit(_UNSAFE_DOCUMENTS_DIR.format(path=out_dir / DOCUMENTS_DIRNAME)) from error


def _write_verified(path: Path, payload: bytes, expected_sha256: str) -> None:
    """Write retained bytes and prove on disk that they are the bytes we hashed."""
    write_bytes_no_clobber(path, payload)
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha256:
        raise SystemExit(_HASH_MISMATCH.format(path=path))


def _document_filename(document: CompanyDocument) -> str:
    """A filesystem-safe name for one retained sub-document body.

    The name comes off the page (a bucket key, a section id), so it is reduced
    to a known-safe alphabet rather than trusted as a path component; the
    ``document_id`` inside the artifact remains the authoritative address.
    """
    return DOCUMENT_FILENAME_TEMPLATE.format(
        part=_slug(document.part.value),
        name=_slug(document.name),
        extension="json" if document.is_json else "html",
    )


def _slug(text: str) -> str:
    """Reduce one label to lowercase alphanumerics joined by hyphens."""
    return _UNSAFE_CHARACTERS.sub(_SLUG_SEPARATOR, text.lower()).strip(_SLUG_SEPARATOR)


def basis_unavailable_message(refused: ScreenerCompanyRefused) -> str:
    """The refusal text for a basis the company does not publish."""
    return _BASIS_UNAVAILABLE.format(basis=refused.basis.value, symbol=refused.symbol)


def render_screener_company_summary(published: ScreenerCompanyRun) -> str:
    """Render one deterministic block stating what was read and how strongly."""
    artifact = published.run.artifact
    lines = [_PART_HEADER]
    for outcome in artifact.outcomes:
        lines.append(
            "\t".join(
                (
                    outcome.part.value,
                    str(outcome.offered).lower(),
                    str(len(outcome.document_ids)),
                    outcome.note or _ABSENT,
                )
            )
        )
    documents = [document for outcome in artifact.outcomes for document in outcome.documents]
    if documents:
        lines.append(_EVIDENCE_HEADER)
        for document in documents:
            lines.append(
                "\t".join(
                    (
                        document.document_id,
                        document.binding.value,
                        document.validation.value,
                        document.validation_status.value,
                    )
                )
            )
    checks = _check_lines(artifact)
    if checks:
        lines.append(_CHECK_HEADER)
        lines.extend(checks)
    if artifact.metadata.weak_documents:
        lines.append(_WEAK_HEADER)
        by_document = {document.document_id: document for document in documents}
        for document_id in artifact.metadata.weak_documents:
            found = by_document.get(document_id)
            lines.append(
                "\t".join(
                    (
                        document_id,
                        _ABSENT if found is None else found.binding.value,
                        _ABSENT if found is None else found.validation.value,
                    )
                )
            )
    if artifact.failures:
        lines.append(_FAILURE_HEADER)
        for failure in artifact.failures:
            lines.append(
                "\t".join((f"{failure.part.value}/{failure.name}", failure.refusal, failure.detail))
            )
    if not artifact.metadata.complete:
        lines.append(_INCOMPLETE_LINE.format(reason=artifact.metadata.incomplete_reason))
    return "\n".join(lines)


def _check_lines(artifact: CompanyArtifact) -> list[str]:
    """One line per document that had a check to run, with what the check said."""
    lines: list[str] = []
    for table in artifact.shareholding:
        lines.append(
            "\t".join(
                (
                    table.table_id,
                    "page_table",
                    f"{len(table.rows)} row(s) over {len(table.periods)} period(s)",
                )
            )
        )
    for bucket in artifact.investors:
        lines.append(
            "\t".join(
                (
                    f"investors {bucket.bucket} {bucket.periodicity.value}",
                    bucket.strategy.value,
                    f"{bucket.outcome.value} n={len(bucket.holders)}",
                )
            )
        )
    for segment in artifact.segments:
        largest = max(
            (comparison.difference for comparison in segment.comparisons),
            key=abs,
            default=None,
        )
        # The relation is printed verbatim from the artifact, and the result is
        # phrased as what actually held: the NEWEST period did not fall below
        # the page row. "flat_sum reconciled" read as "the whole table
        # reconciled and the basis is confirmed", which is a claim no segments
        # fragment can support — TITAN's correct consolidated table exceeds its
        # page row in every period, and the body names no company at all.
        lines.append(
            "\t".join(
                (
                    f"segments {segment.section} Sales",
                    segment.validation.value,
                    f"newest_period_not_below {segment.outcome.value} "
                    f"{_ABSENT if largest is None else f'{largest:+}'}",
                )
            )
        )
    if artifact.peers is not None:
        lines.append(
            "\t".join(
                (
                    "peers",
                    "self_row_basis",
                    f"self_row={artifact.peers.self_row_position} basis ok",
                )
            )
        )
    for entry in artifact.quick_ratios:
        lines.append(
            "\t".join(
                (
                    entry.document_id,
                    "configured_by_account" if entry.configured_by_account else "page_block",
                    f"{len(entry.ratios)} ratio(s)",
                )
            )
        )
    return lines


def is_incomplete(published: ScreenerCompanyRun) -> bool:
    """True when the sweep did not finish, so the artifact is partial."""
    return not published.run.artifact.metadata.complete


def refused_documents(published: ScreenerCompanyRun) -> tuple[str, ...]:
    """Documents whose response was retained but refused outright."""
    return tuple(
        f"{failure.part.value}/{failure.name}" for failure in published.run.artifact.failures
    )


def weak_evidence(published: ScreenerCompanyRun) -> tuple[str, ...]:
    """Documents whose own contents this run did not establish.

    Reported, never fatal. A configured-URL-only document did not skip a gate —
    there was no gate to run, because the source publishes nothing that could
    close one — and a passing one-sided bound is still not a proof. Exiting
    non-zero for them would make ``ok`` unreachable for every company and train
    a caller to ignore the exit code.
    """
    return published.run.artifact.metadata.weak_documents


def not_offered_parts(published: ScreenerCompanyRun) -> tuple[str, ...]:
    """Parts whose owning section rendered without the control that names them."""
    return tuple(
        outcome.part.value for outcome in published.run.artifact.outcomes if not outcome.offered
    )
