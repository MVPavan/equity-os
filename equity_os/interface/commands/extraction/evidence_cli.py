"""The ``evidence`` command: ingest one first-party results package (D1a Task 5).

    evidence ingest --retrieval-manifest <json> --issuer <symbol> --quarter <FYyy_Qn>
        --period-end <YYYY-MM-DD> --basis consolidated --raw-root <dir> --snapshot-root <dir>
        [--member xbrl=<kind>] [--member pdf=<kind>] [--issuer-config <yaml>]
        [--config-root config]
    evidence acquire --entity <key> --basis consolidated --period-end <YYYY-MM-DD>
        --mapping-set <m> --dictionary <d> --snapshot-root <dir> --raw-root <dir>
        [--issuer-config <yaml>] [--config-root config] [--generation <n>]
    evidence transcript --retrieval-manifest <json> --issuer <symbol> --quarter <FYyy_Qn>
        --raw-root <dir> --snapshot-root <dir> --issuer-config <yaml>
    evidence stage --generation <root>/gen-<n> --stage <new dir>

The composition root: ``PgSettings``, the runtime pool, the retained intake and the
source catalog (design decision 12) are built here and nowhere else. ``--issuer-config``
supplies the PDF ``pdf_parse`` block and the results-PDF declaration and is required when a
PDF member is named. Exit 0 only when a package with occurrences is stored and no extraction
attempt failed (``EXIT_INCOMPLETE`` otherwise; ``NOT_PUBLISHED`` is not a failure).

``acquire`` (FIVE-1 Task 3) fetches and ingests one named period's results filing exactly as
``compare fallback`` does, writing no run, admission or outcome; its fetches are kept as the next
entity generation under ``--raw-root``, and ``--generation`` replays one with no socket. It prints
the stored package id, ``FILING_UNAVAILABLE`` or ``FILING_UNRESOLVED`` and exits
``EXIT_INCOMPLETE`` unless the filing was ingested.

``stage`` copies an onboarding generation's retrieval-manifest members (XBRL only) from their
numbered bodies into intake's layout under a directory it creates, each body confined to the
generation and matching both manifests' SHA-256, so ``ingest`` can re-interpret them.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import sys
from collections.abc import Mapping
from datetime import date
from pathlib import Path

import psycopg
import structlog
from pydantic import ValidationError

from equity_os.companies.identity.identity_seed import SettingKey
from equity_os.companies.onboarding.discovery import MANIFEST_NAME, DiscoveryManifest
from equity_os.contracts.measurement.canonical import Basis, Representation
from equity_os.contracts.measurement.evidence import FilingFamily
from equity_os.contracts.measurement.observation import AccountingFramework
from equity_os.contracts.sourcing.acquisition_outcome import outcome_source_state
from equity_os.contracts.sourcing.snapshot import INTAKE_RIGHTS
from equity_os.contracts.sourcing.source_catalog import BUILTIN_SOURCES
from equity_os.contracts.verification.comparison import SourceState
from equity_os.contracts.verification.config_versions import ConfigVersions
from equity_os.contracts.verification.vendor_first import FallbackOutcome
from equity_os.extraction.packages.capture_intake import (
    XBRL_INPUT_DIR,
    IntakeError,
    retained_intake_from_manifest,
)
from equity_os.extraction.packages.first_party_ingest import (
    IngestError,
    admit_transcript,
    ingest_first_party,
)
from equity_os.extraction.results_pdf.pdf_statement_pages import specs_from_config
from equity_os.interface.commands.companies.acquisition_authority import (
    entity_fetch,
    inside,
    ordinary_roots,
)
from equity_os.interface.commands.companies.onboard_cli import RETRIEVAL_NAME, live_transport
from equity_os.interface.commands.sourcing.screener_cli_dispatch import EXIT_OK, EXIT_REFUSED
from equity_os.interface.entry.config import load_config
from equity_os.interface.entry.watchlist_config import with_issuer_pdfs
from equity_os.normalisation.dictionary.dictionary import load_dictionary
from equity_os.normalisation.mapping.mapping import (
    MappingLoadError,
    load_mapping_set,
    load_normalisation_policy,
)
from equity_os.storage.database.pool import DatabaseUnavailableError, open_pool
from equity_os.storage.database.settings import PgRole, PgSettings
from equity_os.storage.raw_files.snapshot_store import SnapshotStore
from equity_os.storage.records.repository import EvidenceRepository
from equity_os.verification.admission.fallback import (
    acquire_group,
    ingest_group,
    ingested,
    pdf_issuer_config,
)
from equity_os.verification.comparison.run_config import extractor_pin, load_run_config

EVIDENCE_COMMAND = "evidence"
INGEST_ACTION = "ingest"
ACQUIRE_ACTION = "acquire"
NAMED_PERIOD = "named-period acquisition of {key} {period_end}"
TRANSCRIPT_ACTION = "transcript"
STAGE_ACTION = "stage"
TRANSCRIPT_KIND = "transcript"
TRANSCRIPT_DECLARATION = "transcript_pdf"
DEFAULT_CONFIG_ROOT = "config"
# Default pins, as ``compare run``'s; a new normalisation version is a reviewed code change.
DICTIONARY_VERSION = "v1"
MAPPING_SET_VERSION = "v1"
NORMALISATION_POLICY_VERSION = "v1"
DICTIONARY_DIR = "normalisation/dictionary"
MAPPINGS_DIR = "normalisation/mappings"
NORMALISATION_POLICY_DIR = "normalisation/normalisation_policy"
# The NSE surfaces this command reads are the Ind AS filings (``nse-indas-*``).
FRAMEWORK = AccountingFramework.IND_AS
MEMBER_SEPARATOR = "="
FISCAL_MONTH = SettingKey.FISCAL_YEAR_END_MONTH
# As ``compare run``'s INCOMPLETE: the ingest ran but stored no usable package, or an
# extraction attempt failed.
EXIT_INCOMPLETE = 4

_ACTION_DEST = "evidence_action"
_HELP = "ingest first-party filings into the evidence store"
_INGEST_HELP = "stage, extract and interpret one results package from retained originals"
_ACQUIRE_HELP = "fetch and ingest one named period's results filing, as the fallback does"
_TRANSCRIPT_HELP = "register one quarter's transcript PDF as a diagnostic first-party capture"
_STAGE_HELP = "stage an onboarding generation's package members for ingest"
_STAGED = "staged\t{count}\n"
_ALTERED = "{path} does not match its manifest SHA-256"
_MEMBER_HELP = "a package member as <representation>=<manifest kind>, e.g. xbrl=xbrl-consolidated"
_BAD_MEMBER = "--member {value!r} is not xbrl=<kind> or pdf=<kind>"
_NO_MEMBER = "name at least one --member"
_PDF_NEEDS_CONFIG = "a pdf member needs --issuer-config"
_OUTSIDE_SETTINGS = "no fiscal-year-end month governs {period_end}; onboarding's window"
_UNKNOWN_ISSUER = "issuer {issuer!r} is not seeded"
_REFUSED_EVENT = "evidence_command_refused"
_CAPTURE_REF = "capture_ref\t{capture_ref_id}\n"
_ACQUIRED = "{period_end}\tpackage\t{package_id}\n"
_NOT_ACQUIRED = "{period_end}\t{outcome}\n"
_SUMMARY = "package\t{package_id}\noccurrences\t{occurrences}"
_COUNT_LINE = "interpretations\t{status}\t{count}"
_ATTEMPT_LINE = "attempt\t{stage}\t{representation}\t{family}\t{outcome}"
_BASES = {basis.value.lower(): basis for basis in Basis}


class EvidenceCommandError(ValueError):
    """The command line cannot form an ingest request."""


def add_evidence_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register ``evidence`` and its ``ingest``, ``acquire`` and ``transcript`` actions."""
    parser = subparsers.add_parser(EVIDENCE_COMMAND, help=_HELP)
    actions = parser.add_subparsers(dest=_ACTION_DEST, required=True)
    ingest = actions.add_parser(INGEST_ACTION, help=_INGEST_HELP)
    ingest.add_argument("--retrieval-manifest", required=True, type=Path)
    ingest.add_argument("--issuer", required=True)
    ingest.add_argument("--quarter", required=True)
    ingest.add_argument("--period-end", required=True, type=date.fromisoformat)
    ingest.add_argument("--basis", required=True, choices=sorted(_BASES))
    ingest.add_argument("--raw-root", required=True, type=Path)
    ingest.add_argument("--snapshot-root", required=True, type=Path)
    ingest.add_argument("--member", action="append", default=[], help=_MEMBER_HELP)
    ingest.add_argument("--issuer-config", type=Path)
    ingest.add_argument("--config-root", type=Path, default=Path(DEFAULT_CONFIG_ROOT))
    ingest.add_argument("--dictionary", default=DICTIONARY_VERSION)
    ingest.add_argument("--mapping-set", default=MAPPING_SET_VERSION)
    acquire = actions.add_parser(ACQUIRE_ACTION, help=_ACQUIRE_HELP)
    acquire.add_argument("--entity", required=True)
    acquire.add_argument("--basis", required=True, choices=sorted(_BASES))
    acquire.add_argument("--period-end", required=True, type=date.fromisoformat)
    acquire.add_argument("--mapping-set", required=True)
    acquire.add_argument("--dictionary", required=True)
    acquire.add_argument("--snapshot-root", required=True, type=Path)
    acquire.add_argument("--raw-root", required=True, type=Path)
    acquire.add_argument("--issuer-config", type=Path)
    acquire.add_argument("--config-root", type=Path, default=Path(DEFAULT_CONFIG_ROOT))
    acquire.add_argument("--generation", type=int)
    transcript = actions.add_parser(TRANSCRIPT_ACTION, help=_TRANSCRIPT_HELP)
    for flag in ("--retrieval-manifest", "--raw-root", "--snapshot-root", "--issuer-config"):
        transcript.add_argument(flag, required=True, type=Path)
    transcript.add_argument("--issuer", required=True)
    transcript.add_argument("--quarter", required=True)
    stage = actions.add_parser(STAGE_ACTION, help=_STAGE_HELP)
    stage.add_argument("--generation", required=True, type=Path)
    stage.add_argument("--stage", required=True, type=Path)


def dispatch_evidence_command(args: argparse.Namespace) -> int | None:
    """Run an ``evidence`` action, or return ``None`` for any other command."""
    if args.command != EVIDENCE_COMMAND:
        return None
    try:
        if args.evidence_action == ACQUIRE_ACTION:
            return _acquire(args)
        if args.evidence_action == STAGE_ACTION:
            return _stage(args.generation, args.stage)
        return _transcript(args) if args.evidence_action == TRANSCRIPT_ACTION else _ingest(args)
    except (
        EvidenceCommandError,
        IntakeError,
        IngestError,
        MappingLoadError,
        DatabaseUnavailableError,
        psycopg.Error,
        ValidationError,
        OSError,
        LookupError,
        ValueError,
    ) as refusal:
        structlog.get_logger("fundamentals.evidence").warning(
            _REFUSED_EVENT, refusal=type(refusal).__name__, detail=str(refusal)
        )
        return EXIT_REFUSED


def _ingest(args: argparse.Namespace) -> int:
    """Compose the pins, intake, catalog and repository, then ingest one package."""
    members = _members(args.member)
    if Representation.PDF in members and args.issuer_config is None:
        raise EvidenceCommandError(_PDF_NEEDS_CONFIG)
    config_root: Path = args.config_root
    dictionary = load_dictionary(config_root / DICTIONARY_DIR, args.dictionary)
    mapping_set = load_mapping_set(
        config_root / MAPPINGS_DIR, args.mapping_set, dictionary=dictionary
    )
    policy = load_normalisation_policy(
        config_root / NORMALISATION_POLICY_DIR / f"{NORMALISATION_POLICY_VERSION}.yaml"
    )
    intake = retained_intake_from_manifest(
        args.retrieval_manifest,
        issuer=args.issuer,
        quarter=args.quarter,
        kinds=members,
        store_root=args.snapshot_root.absolute(),
        input_root=args.raw_root.absolute(),
        issuer_config=args.issuer_config,
        rights=INTAKE_RIGHTS,
        basis=_BASES[args.basis],
    )
    catalog = BUILTIN_SOURCES
    pdf_specs = None
    if args.issuer_config is not None:
        issuer_config = load_config(args.issuer_config)
        catalog = with_issuer_pdfs(catalog, issuer_config)
        pdf_specs = specs_from_config(issuer_config.pdf_parse)
    settings = PgSettings()
    with open_pool(settings, PgRole.RUNTIME) as pool:
        repository = EvidenceRepository(pool)
        entity_id = repository.entity_id(args.issuer)
        if entity_id is None:
            raise EvidenceCommandError(_UNKNOWN_ISSUER.format(issuer=args.issuer))
        report = ingest_first_party(
            intake=intake,
            catalog=catalog,
            snapshot_store=SnapshotStore(args.snapshot_root),
            repository=repository,
            dictionary=dictionary,
            mapping_set=mapping_set,
            policy=policy,
            entity_id=entity_id,
            basis=_BASES[args.basis],
            framework=FRAMEWORK,
            family=FilingFamily.FINANCIAL_RESULTS,
            reporting_period_end=args.period_end,
            pdf_specs=pdf_specs,
        )
    lines = [_SUMMARY.format(package_id=report.package_id, occurrences=report.occurrence_count)]
    lines += [
        _COUNT_LINE.format(status=status.value, count=count)
        for status, count in sorted(report.interpretation_counts.items())
    ]
    lines += [
        _ATTEMPT_LINE.format(
            stage=attempt.stage.value,
            representation=attempt.representation.value,
            family=attempt.statement_family.value if attempt.statement_family else "-",
            outcome=attempt.outcome.value,
        )
        for attempt in report.attempts
    ]
    sys.stdout.write("\n".join(lines) + "\n")
    failed = any(
        outcome_source_state(attempt.outcome) is SourceState.UNAVAILABLE
        for attempt in report.attempts
    )
    usable = report.package_id is not None and report.occurrence_count > 0
    return EXIT_OK if usable and not failed else EXIT_INCOMPLETE


def _acquire(args: argparse.Namespace) -> int:
    """Fetch and ingest one named period's filing as the fallback does; print the outcome."""
    ordinary_roots(args.snapshot_root, args.raw_root)
    pdf_config = pdf_issuer_config(args.issuer_config)
    versions = ConfigVersions(dictionary=args.dictionary, mapping_set=args.mapping_set)
    config = load_run_config(args.config_root, versions)
    extractors = {r: extractor_pin(r) for r in (Representation.XBRL, Representation.PDF)}
    roots = (args.snapshot_root, args.raw_root)
    authorization = NAMED_PERIOD.format(key=args.entity, period_end=args.period_end)
    with open_pool(PgSettings(), PgRole.RUNTIME) as pool:
        repository = EvidenceRepository(pool)
        entity_id = repository.entity_id(args.entity)
        if entity_id is None:
            raise EvidenceCommandError(_UNKNOWN_ISSUER.format(issuer=args.entity))
        clock = repository.store_clock()
        if repository.settings_as_of(entity_id, FISCAL_MONTH, clock, args.period_end) is None:
            raise EvidenceCommandError(_OUTSIDE_SETTINGS.format(period_end=args.period_end))
        group = (entity_id, args.period_end, _BASES[args.basis])
        fetch, write = entity_fetch(
            args.raw_root, args.generation, args.entity, authorization, live_transport
        )
        try:
            filing, symbol = acquire_group(
                pool, SnapshotStore(args.snapshot_root), fetch, group, pdf_config
            )
        finally:
            write()
        report = None
        if filing is not None and (filing.pdf is not None or pdf_config is None):
            with contextlib.suppress(IntakeError, IngestError):
                report = ingest_group(
                    pool,
                    filing,
                    group,
                    symbol,
                    authorization,
                    roots,
                    config,
                    pdf_config,
                    extractors,
                )
    if report is not None and ingested(report):
        sys.stdout.write(_ACQUIRED.format(period_end=args.period_end, package_id=report.package_id))
        return EXIT_OK
    outcome = (
        FallbackOutcome.FILING_UNAVAILABLE if filing is None else FallbackOutcome.FILING_UNRESOLVED
    )
    sys.stdout.write(_NOT_ACQUIRED.format(period_end=args.period_end, outcome=outcome.value))
    return EXIT_INCOMPLETE


def _stage(generation: Path, stage: Path) -> int:
    """Stage the generation's retrieval-manifest members as ``<stage>/nse/<filename>`` beside a
    copy of that manifest under a new ``stage``, every path checked ordinary before it is touched
    and every hash checked before anything is written; print how many."""
    ordinary_roots(generation, stage)
    package = _ordinary(generation, RETRIEVAL_NAME).read_bytes()
    found = DiscoveryManifest.model_validate_json(_ordinary(generation, MANIFEST_NAME).read_bytes())
    bodies = {entry.url: (str(entry.filename), entry.sha256) for entry in found.entries}
    entries = json.loads(package)["entries"]
    staged = []
    for entry in entries:
        name, digest = bodies[entry["url"]]
        body = _ordinary(generation, name).read_bytes()
        if not hashlib.sha256(body).hexdigest() == digest == entry["sha256"]:
            raise EvidenceCommandError(_ALTERED.format(path=generation / name))
        staged.append((entry["filename"], body))
    stage.mkdir(parents=True)
    (stage / XBRL_INPUT_DIR).mkdir()
    for filename, body in staged:
        _ordinary(stage / XBRL_INPUT_DIR, filename).write_bytes(body)
    _ordinary(stage, RETRIEVAL_NAME).write_bytes(package)
    sys.stdout.write(_STAGED.format(count=len(entries)))
    return EXIT_OK


def _ordinary(folder: Path, name: str) -> Path:
    """``folder / name``, confined to ``folder`` and outside every protected root."""
    path = inside(folder, name)
    ordinary_roots(path)
    return path


def _transcript(args: argparse.Namespace) -> int:
    """Register the quarter's transcript PDF under its issuer config's pin; print its id."""
    intake = retained_intake_from_manifest(
        args.retrieval_manifest,
        issuer=args.issuer,
        quarter=args.quarter,
        kinds={Representation.PDF: TRANSCRIPT_KIND},
        store_root=args.snapshot_root.absolute(),
        input_root=args.raw_root.absolute(),
        issuer_config=args.issuer_config,
        pdf_declaration=TRANSCRIPT_DECLARATION,
        rights=INTAKE_RIGHTS,
    )
    catalog = with_issuer_pdfs(BUILTIN_SOURCES, load_config(args.issuer_config))
    with open_pool(PgSettings(), PgRole.RUNTIME) as pool:
        ref = admit_transcript(
            EvidenceRepository(pool), SnapshotStore(args.snapshot_root), intake, catalog=catalog
        )
    sys.stdout.write(_CAPTURE_REF.format(capture_ref_id=ref.capture_ref_id))
    return EXIT_OK


def _members(values: list[str]) -> Mapping[Representation, str]:
    """Parse ``--member`` values into one manifest kind per representation."""
    if not values:
        raise EvidenceCommandError(_NO_MEMBER)
    members: dict[Representation, str] = {}
    for value in values:
        name, separator, kind = value.partition(MEMBER_SEPARATOR)
        try:
            representation = Representation(name.upper())
        except ValueError as error:
            raise EvidenceCommandError(_BAD_MEMBER.format(value=value)) from error
        if not separator or not kind or representation in members:
            raise EvidenceCommandError(_BAD_MEMBER.format(value=value))
        members[representation] = kind
    return members
