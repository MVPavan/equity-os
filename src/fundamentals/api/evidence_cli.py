"""The ``evidence`` command: ingest one first-party results package (D1a Task 5).

    evidence ingest --retrieval-manifest <json> --issuer <symbol> --quarter <FYyy_Qn>
        --period-end <YYYY-MM-DD> --basis consolidated --raw-root <dir> --snapshot-root <dir>
        [--member xbrl=<kind>] [--member pdf=<kind>] [--issuer-config <yaml>]
        [--config-root config]

The composition root: ``PgSettings``, the runtime pool, the retained intake and the
source catalog (design decision 12) are built here and nowhere else. ``--issuer-config``
supplies the PDF ``pdf_parse`` block and the results-PDF declaration and is required when a
PDF member is named. Exit 0 only when a package with occurrences is stored and no extraction
attempt failed (``EXIT_INCOMPLETE`` otherwise; ``NOT_PUBLISHED`` is not a failure).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping
from datetime import date
from pathlib import Path

import psycopg
import structlog
from pydantic import ValidationError

from fundamentals.api.config import load_config
from fundamentals.api.screener_cli_dispatch import EXIT_OK, EXIT_REFUSED
from fundamentals.api.watchlist_config import with_issuer_pdfs
from fundamentals.canon.dictionary import load_dictionary
from fundamentals.contracts.acquisition_outcome import outcome_source_state
from fundamentals.contracts.canonical import Basis, Representation
from fundamentals.contracts.comparison import SourceState
from fundamentals.contracts.evidence import FilingFamily
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.source_catalog import BUILTIN_SOURCES
from fundamentals.evidence.capture_intake import IntakeError, retained_intake_from_manifest
from fundamentals.evidence.first_party_ingest import IngestError, ingest_first_party
from fundamentals.evidence.mapping import (
    MappingLoadError,
    load_mapping_set,
    load_normalisation_policy,
)
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.extract.pdf_statement_pages import specs_from_config
from fundamentals.pg.pool import DatabaseUnavailableError, open_pool
from fundamentals.pg.settings import PgRole, PgSettings
from fundamentals.store.snapshot_store import SnapshotStore

EVIDENCE_COMMAND = "evidence"
INGEST_ACTION = "ingest"
DEFAULT_CONFIG_ROOT = "config"
# Default pins, as ``compare run``'s; a new normalisation version is a reviewed code change.
DICTIONARY_VERSION = "v1"
MAPPING_SET_VERSION = "v1"
NORMALISATION_POLICY_VERSION = "v1"
DICTIONARY_DIR = "dictionary"
MAPPINGS_DIR = "mappings"
NORMALISATION_POLICY_DIR = "normalisation_policy"
# The NSE surfaces this command reads are the Ind AS filings (``nse-indas-*``).
FRAMEWORK = AccountingFramework.IND_AS
MEMBER_SEPARATOR = "="
# As ``compare run``'s INCOMPLETE: the ingest ran but stored no usable package, or an
# extraction attempt failed.
EXIT_INCOMPLETE = 4

_ACTION_DEST = "evidence_action"
_HELP = "ingest first-party filings into the evidence store"
_INGEST_HELP = "stage, extract and interpret one results package from retained originals"
_MEMBER_HELP = "a package member as <representation>=<manifest kind>, e.g. xbrl=xbrl-consolidated"
_BAD_MEMBER = "--member {value!r} is not xbrl=<kind> or pdf=<kind>"
_NO_MEMBER = "name at least one --member"
_PDF_NEEDS_CONFIG = "a pdf member needs --issuer-config"
_UNKNOWN_ISSUER = "issuer {issuer!r} is not seeded"
_REFUSED_EVENT = "evidence_command_refused"
_SUMMARY = "package\t{package_id}\noccurrences\t{occurrences}"
_COUNT_LINE = "interpretations\t{status}\t{count}"
_ATTEMPT_LINE = "attempt\t{stage}\t{representation}\t{family}\t{outcome}"
_BASES = {basis.value.lower(): basis for basis in Basis}


class EvidenceCommandError(ValueError):
    """The command line cannot form an ingest request."""


def add_evidence_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register ``evidence`` and its ``ingest`` action."""
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


def dispatch_evidence_command(args: argparse.Namespace) -> int | None:
    """Run ``evidence ingest``, or return ``None`` for any other command."""
    if args.command != EVIDENCE_COMMAND:
        return None
    try:
        return _ingest(args)
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
