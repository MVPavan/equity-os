"""Fundamentals — source-backed earnings-review product (Phase 0.5 pilot).

Public entry points for the end-to-end increment. Lower layers stay importable
from their own packages (``fundamentals.ingest``, ``.extract``, ``.verify``,
``.store``, ``.output``); the top level re-exports only the composition-root
orchestration and the sourced-render entry.
"""

from fundamentals.api.config import FundamentalsConfig, load_config
from fundamentals.api.pipeline import PipelineError, PipelineResult, XbrlInput, run_pipeline
from fundamentals.output.earnings_update import render_earnings_update
from fundamentals.store.fact_store import FactStore

__all__ = [
    "FactStore",
    "FundamentalsConfig",
    "PipelineError",
    "PipelineResult",
    "XbrlInput",
    "load_config",
    "render_earnings_update",
    "run_pipeline",
]
