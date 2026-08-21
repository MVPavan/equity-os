"""Fundamentals api layer — composition root, config, and orchestration."""

from fundamentals.api.config import (
    FundamentalsConfig,
    XbrlMode,
    load_config,
)
from fundamentals.api.pipeline import (
    PipelineError,
    PipelineResult,
    XbrlInput,
    run_pipeline,
)

__all__ = [
    "FundamentalsConfig",
    "PipelineError",
    "PipelineResult",
    "XbrlInput",
    "XbrlMode",
    "load_config",
    "run_pipeline",
]
