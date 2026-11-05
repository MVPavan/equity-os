"""``eqos-operator``: the installed composition root for historical source admission.

Its trust anchor is this checkout, never the caller's paths: the repository root, the retrieval
manifest's SHA-256 and each accepted quarter config's bytes. Bindings take the anchored
manifest's pins and A05-DECISION-004 rights; argv selects only the quarter and the store.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections.abc import Mapping
from functools import partial
from pathlib import Path

from equity_os.contracts.measurement.canonical import Representation
from equity_os.contracts.sourcing.snapshot import INTAKE_RIGHTS
from equity_os.contracts.sourcing.source_registration import SourceRegistrationError, SourceRole
from equity_os.extraction.packages.capture_intake import retained_intake_from_manifest
from equity_os.interface.commands.sourcing.artifact_writer import write_bytes_no_clobber
from equity_os.interface.commands.sourcing.source_admission import (
    PipelineSourceRefs,
    RetainedSourceRef,
)
from equity_os.interface.commands.sourcing.source_intake import (
    ApprovedIntakeBinding,
    ApprovedIntakeContext,
    stage_local_source,
)
from equity_os.interface.entry import cli
from equity_os.interface.entry.cli_parser import RUN_COMMAND, build_parser
from equity_os.interface.entry.config import load_config
from equity_os.storage.raw_files.snapshot_store import SnapshotStore

INSTALLED_ROOT = Path(__file__).resolve().parents[3]
RETRIEVAL_MANIFEST = "data/raw/watchlist/aparinds/retrieval-manifest-v2.json"
RETRIEVAL_MANIFEST_SHA256 = "c47866ce13f719521bbcc7826fc23590acc73f9904cfc1749a1ad911bb399a1b"
# Each accepted quarter config's committed bytes; FY26_Q4 runs from its -pg copy.
ACCEPTED_CONFIGS: Mapping[str, str] = {
    "config/runs/aparinds-fy26-q2.yaml": (
        "2e179d03dcc6dcfb0feeb6d0e909ccc018624ea8df04f816c4799b96cf40156d"
    ),
    "config/runs/aparinds-fy26-q3.yaml": (
        "83c7d7b2fbe0634e06680855ee95fad4e6ecff43c012f3dd9815d0f76824bf3c"
    ),
    "config/runs/aparinds-fy26-q4-pg.yaml": (
        "91cc4641de6350f4b023d2f56372e22281241e3362fbaab52ea4bada8c25e8fd"
    ),
    "config/runs/aparinds-fy27-q1.yaml": (
        "38c6417cd7c89c775613d7a7ec48bf897e95286cf66a284f0e5462a18a74dd09"
    ),
}
STAGE_COMMAND = "stage"
UNSUPPORTED_ROOT = "unsupported root"
CONFIG_NOT_ACCEPTED = "config not accepted"
MANIFEST_NOT_ACCEPTED = "manifest not accepted"
XBRL_SOURCE_DIFFERS = "XBRL source differs from the configuration"
RETROSPECTIVE_REQUIRED = "retrospective manifest required"
SOURCE_ADMISSION_REQUIRED = "source admission manifest and store required"
USAGE = "usage: eqos-operator {stage|run} ..."


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _approved(
    config_path: Path, store_root: Path, root: Path
) -> tuple[ApprovedIntakeContext, Mapping[SourceRole, Path]]:
    """The context of one accepted quarter config and each role's manifest-relative path."""
    root, config_path = root.resolve(), config_path.resolve()
    accepted = config_path.relative_to(root).as_posix() if config_path.is_relative_to(root) else ""
    if accepted not in ACCEPTED_CONFIGS:
        raise SourceRegistrationError(UNSUPPORTED_ROOT)
    if _sha256(config_path) != ACCEPTED_CONFIGS[accepted]:
        raise SourceRegistrationError(CONFIG_NOT_ACCEPTED)
    if _sha256(root / RETRIEVAL_MANIFEST) != RETRIEVAL_MANIFEST_SHA256:
        raise SourceRegistrationError(MANIFEST_NOT_ACCEPTED)
    config = load_config(config_path)
    bind = partial(
        retained_intake_from_manifest,
        root / RETRIEVAL_MANIFEST,
        issuer=config.issuer.nse_symbol,
        quarter=config.quarter.issuer_quarter,
        store_root=store_root.absolute(),
        input_root=root / config.raw_dir,
        issuer_config=config_path,
        rights=INTAKE_RIGHTS,
    )
    results = bind(kinds={Representation.XBRL: "xbrl-consolidated", Representation.PDF: "results"})
    transcript = bind(kinds={Representation.PDF: "transcript"}, pdf_declaration="transcript_pdf")
    if results.binding(Representation.XBRL).source_id != config.xbrl.source_id:
        raise SourceRegistrationError(XBRL_SOURCE_DIFFERS)
    bound = {
        SourceRole.XBRL: (results, results.binding(Representation.XBRL)),
        SourceRole.RESULTS_PDF: (results, results.binding(Representation.PDF)),
        SourceRole.TRANSCRIPT_PDF: (transcript, transcript.binding(Representation.PDF)),
    }
    context = ApprovedIntakeContext(
        tuple(
            ApprovedIntakeBinding(role, member.source_id, member.expected_sha256, intake.rights)
            for role, (intake, member) in bound.items()
        ),
        ACCEPTED_CONFIGS[accepted],
        results.store_anchor,
        results.input_anchor,
    )
    return context, {role: member.relative_path for role, (_, member) in bound.items()}


def approved_intake(
    config_path: Path, store_root: Path, *, root: Path = INSTALLED_ROOT
) -> ApprovedIntakeContext:
    """The approved intake context of one accepted quarter config (``root`` is a test seam)."""
    return _approved(config_path, store_root, root)[0]


def _stage(argv: list[str]) -> int:
    """Capture and register the quarter's three pinned originals, then write their locator."""
    parser = argparse.ArgumentParser(prog="eqos-operator stage")
    for flag in ("--config", "--source-admission-store", "--out-manifest"):
        parser.add_argument(flag, type=Path, required=True)
    args = parser.parse_args(argv)
    context, paths = _approved(args.config, args.source_admission_store, INSTALLED_ROOT)
    store = SnapshotStore(args.source_admission_store)
    receipts = {
        role: stage_local_source(store, approved_intake=context, role=role, path=paths[role])
        for role in SourceRole
    }
    fields = set(RetainedSourceRef.model_fields)
    refs = PipelineSourceRefs(
        **{
            role.value: RetainedSourceRef(**receipt.model_dump(include=fields))
            for role, receipt in receipts.items()
        }
    )
    write_bytes_no_clobber(args.out_manifest, refs.model_dump_json(indent=2).encode())
    for role, receipt in receipts.items():
        sys.stdout.write(f"{role.value}\t{receipt.source_id}\t{receipt.capture_id}\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    """``stage`` a quarter's originals, or ``run`` it retrospectively under the anchored context."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == [STAGE_COMMAND]:
        return _stage(argv[1:])
    if argv[:1] != [RUN_COMMAND]:
        raise SystemExit(USAGE)
    args = build_parser().parse_args(argv)
    if args.retrospective is None or (
        args.retrospective.resolve() != INSTALLED_ROOT / RETRIEVAL_MANIFEST
    ):
        raise SourceRegistrationError(RETROSPECTIVE_REQUIRED)
    if args.source_admission_manifest is None or args.source_admission_store is None:
        raise SourceRegistrationError(SOURCE_ADMISSION_REQUIRED)
    context = approved_intake(Path(args.config), Path(args.source_admission_store))
    return cli.main(argv, intake_context=context)
