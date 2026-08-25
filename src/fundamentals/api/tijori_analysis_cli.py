"""CLI composition helpers for Tijori's ancillary analysis-API acquisition."""

from __future__ import annotations

import argparse
from pathlib import Path

import structlog
from pydantic import BaseModel, ConfigDict

from fundamentals.api.artifact_writer import preflight_out_paths, write_json_no_clobber
from fundamentals.api.watchlist_config import load_watchlist_config
from fundamentals.ingest.tijori_analysis_models import (
    METRIC_ID_REQUIRED,
    METRIC_SECTIONS,
    SECTION_DOCUMENT_IDS,
    TijoriAnalysisFetch,
    TijoriAnalysisSection,
)
from fundamentals.ingest.tijori_source import (
    TijoriCredentials,
    TijoriSource,
    TijoriSourceConfig,
)

TIJORI_ANALYSIS_COMMAND = "tijori-analysis"

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_WATCHLIST_PATH = _REPO_ROOT / "config" / "watchlist.yaml"
_DEFAULT_OUT_ROOT = _REPO_ROOT / "data" / "raw" / "watchlist" / "tijori-analysis"
_SUMMARY_HEADER = "section\tdocument\toutcome\telements\tmetric_id\traw\tnote"
_RAW_SUFFIX = ".raw.json"
_SKIPPED_OUTCOME = "skipped"
_ABSENT = "-"

# Sections a breadth run can acquire knowing only the company id.
_BREADTH_SECTIONS = tuple(
    section for section in TijoriAnalysisSection if section not in METRIC_SECTIONS
)


class SkippedSection(BaseModel):
    """One section a run did not attempt, and why.

    A skipped section is reported, never omitted: a caller who cannot see that
    ``op_metrics`` was skipped would read its absence as the API having nothing.
    """

    model_config = ConfigDict(frozen=True)

    section: TijoriAnalysisSection
    reason: str


class AnalysisRun(BaseModel):
    """Everything one ``tijori-analysis`` invocation acquired and declined."""

    model_config = ConfigDict(frozen=True)

    fetched: tuple[TijoriAnalysisFetch, ...]
    skipped: tuple[SkippedSection, ...]


def add_tijori_analysis_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``fundamentals tijori-analysis`` command."""
    parser = subparsers.add_parser(
        TIJORI_ANALYSIS_COMMAND,
        help="acquire the typed Tijori analysis JSON APIs for one watchlist stock",
    )
    parser.add_argument("--stock", required=True, help="watchlist NSE symbol, e.g. TITAN")
    parser.add_argument(
        "--section",
        choices=tuple(section.value for section in TijoriAnalysisSection),
        default=None,
        help="one analysis API (default: every API that needs only the company id)",
    )
    parser.add_argument(
        "--metric-id",
        action="append",
        type=int,
        default=None,
        dest="metric_ids",
        help=(
            "operational-metric id to fetch (repeatable); required for op_metrics, "
            "which is otherwise skipped because no acquired artifact publishes these ids"
        ),
    )
    parser.add_argument(
        "--out",
        default=None,
        help="output directory (default: data/raw/watchlist/tijori-analysis/<stock>)",
    )
    parser.add_argument(
        "--config",
        default=str(_DEFAULT_WATCHLIST_PATH),
        help="path to watchlist.yaml",
    )


def _plan(
    args: argparse.Namespace, metric_ids: tuple[int, ...]
) -> tuple[tuple[tuple[TijoriAnalysisSection, int | None], ...], tuple[SkippedSection, ...]]:
    """Resolve what this invocation fetches and what it declines, with reasons."""
    if args.section is not None:
        section = TijoriAnalysisSection(args.section)
        if section in METRIC_SECTIONS and not metric_ids:
            raise SystemExit(METRIC_ID_REQUIRED)
        if section in METRIC_SECTIONS:
            return tuple((section, metric_id) for metric_id in metric_ids), ()
        return ((section, None),), ()

    requests: list[tuple[TijoriAnalysisSection, int | None]] = [
        (section, None) for section in _BREADTH_SECTIONS
    ]
    skipped: list[SkippedSection] = []
    for section in TijoriAnalysisSection:
        if section not in METRIC_SECTIONS:
            continue
        if metric_ids:
            requests.extend((section, metric_id) for metric_id in metric_ids)
        else:
            skipped.append(SkippedSection(section=section, reason=METRIC_ID_REQUIRED))
    return tuple(requests), tuple(skipped)


def _artifact_name(section: TijoriAnalysisSection, metric_id: int | None) -> str:
    """Name one artifact so two metrics of one section never collide on disk."""
    if metric_id is None:
        return f"{section.value}.json"
    return f"{section.value}-{metric_id}.json"


def _raw_name(artifact_name: str) -> str:
    """Name the retained response body beside its artifact."""
    return f"{artifact_name.removesuffix('.json')}{_RAW_SUFFIX}"


def run_tijori_analysis_command(
    args: argparse.Namespace,
    *,
    credentials: TijoriCredentials,
) -> AnalysisRun:
    """Resolve one stock, fetch the requested analysis APIs, and write their JSON."""
    config_path = Path(args.config).resolve()
    watchlist = load_watchlist_config(config_path)
    try:
        stock = watchlist.stock(args.stock)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    unverified = stock.identifiers.unverified_tijori_fields()
    if unverified:
        raise SystemExit(
            f"Tijori identifiers for {stock.symbol} are not verified: {', '.join(unverified)}"
        )

    metric_ids: tuple[int, ...] = tuple(args.metric_ids or ())
    requests, skipped = _plan(args, metric_ids)
    source = TijoriSource(TijoriSourceConfig(credentials=credentials))
    fetched = tuple(
        source.fetch_analysis(
            slug=stock.identifiers.tijori_slug,
            symbol=stock.symbol,
            company_id=stock.identifiers.tijori_company_id,
            section=section,
            metric_id=metric_id,
        )
        for section, metric_id in requests
    )

    out_dir = Path(args.out).resolve() if args.out else _DEFAULT_OUT_ROOT / stock.symbol
    out_dir.mkdir(parents=True, exist_ok=True)
    names = tuple(_artifact_name(section, metric_id) for section, metric_id in requests)
    # The artifact and its source bytes are pre-flighted together: retaining one
    # without the other would leave a recorded body hash with nothing to check.
    out_paths = tuple(out_dir / name for name in names) + tuple(
        out_dir / _raw_name(name) for name in names
    )
    preflight_out_paths(out_paths)
    logger = structlog.get_logger("fundamentals.tijori_analysis")
    for fetch, name in zip(fetched, names, strict=True):
        artifact = fetch.document
        write_json_no_clobber(out_dir / name, artifact.model_dump_json(indent=2) + "\n")
        write_json_no_clobber(out_dir / _raw_name(name), fetch.raw_body.decode("utf-8"))
        logger.info(
            "tijori_analysis_document_written",
            stock=stock.symbol,
            section=artifact.section.value,
            document=artifact.document_id,
            outcome=artifact.outcome.value,
            elements=artifact.element_count,
            metric_id=artifact.metadata.metric_id,
            path=str(out_dir / name),
            raw_path=str(out_dir / _raw_name(name)),
        )
    for skip in skipped:
        logger.info(
            "tijori_analysis_section_skipped",
            stock=stock.symbol,
            section=skip.section.value,
            reason=skip.reason,
        )
    return AnalysisRun(fetched=fetched, skipped=skipped)


def render_tijori_analysis_summary(run: AnalysisRun) -> str:
    """Render one deterministic line per acquired document and per skipped section."""
    lines = [_SUMMARY_HEADER]
    for fetch in run.fetched:
        artifact = fetch.document
        name = _artifact_name(artifact.section, artifact.metadata.metric_id)
        lines.append(
            "\t".join(
                (
                    artifact.section.value,
                    artifact.document_id,
                    artifact.outcome.value,
                    str(artifact.element_count),
                    (
                        _ABSENT
                        if artifact.metadata.metric_id is None
                        else str(artifact.metadata.metric_id)
                    ),
                    _raw_name(name),
                    artifact.note or _ABSENT,
                )
            )
        )
    lines.extend(
        "\t".join(
            (
                skip.section.value,
                SECTION_DOCUMENT_IDS[skip.section],
                _SKIPPED_OUTCOME,
                _ABSENT,
                _ABSENT,
                _ABSENT,
                skip.reason,
            )
        )
        for skip in run.skipped
    )
    return "\n".join(lines)
