"""CLI surface for deterministic approved-thesis impact evaluation."""

from __future__ import annotations

import argparse
from pathlib import Path

import structlog
from pydantic import ValidationError

from fundamentals.api.artifact_writer import preflight_out_paths, write_bytes_no_clobber
from fundamentals.output.earnings_update import EarningsUpdate
from fundamentals.verify.thesis_impact import Disposition, evaluate_thesis, render_thesis_impact
from fundamentals.verify.thesis_predicates import load_thesis

THESIS_IMPACT_COMMAND = "thesis-impact"
_CLI_LOGGER = structlog.get_logger("fundamentals.thesis_impact")


def add_thesis_impact_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``thesis-impact`` artifact command."""
    thesis_impact = subparsers.add_parser(
        THESIS_IMPACT_COMMAND,
        help="evaluate approved thesis falsifiers against an earnings-update JSON artifact",
    )
    thesis_impact.add_argument("--report-json", required=True, help="EarningsUpdate JSON artifact")
    thesis_impact.add_argument("--thesis", required=True, help="approved thesis YAML file")
    thesis_impact.add_argument("--out", required=True, help="new markdown output path")
    thesis_impact.add_argument("--out-json", default=None, help="optional new JSON output path")


def dispatch_thesis_impact_command(args: argparse.Namespace) -> int | None:
    """Run ``thesis-impact`` or return ``None`` for another command."""
    if args.command != THESIS_IMPACT_COMMAND:
        return None
    report_path = Path(args.report_json)
    thesis_path = Path(args.thesis)
    out_path = Path(args.out)
    out_json_path = Path(args.out_json) if args.out_json else None
    try:
        update = EarningsUpdate.model_validate_json(report_path.read_bytes())
        thesis = load_thesis(thesis_path)
        impact = evaluate_thesis(update, thesis)
        markdown = render_thesis_impact(impact)
        out_paths = (out_path,) if out_json_path is None else (out_path, out_json_path)
        preflight_out_paths(out_paths)
        write_bytes_no_clobber(out_path, markdown.encode("utf-8"))
        if out_json_path is not None:
            write_bytes_no_clobber(out_json_path, impact.model_dump_json(indent=2).encode("utf-8"))
    except (OSError, ValidationError, ValueError, SystemExit) as error:
        _CLI_LOGGER.warning("thesis_impact_refused", error=str(error))
        return 2
    return 1 if impact.counts.get(Disposition.WEAKENED, 0) else 0
