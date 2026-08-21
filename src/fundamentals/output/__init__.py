"""Fundamentals output layer — sourced earnings-update rendering."""

from fundamentals.output.earnings_update import (
    EarningsUpdate,
    FactRole,
    RenderedCalculation,
    RenderedFact,
    RenderedGuidance,
    RenderError,
    anchor_label,
    render_earnings_update,
)

__all__ = [
    "EarningsUpdate",
    "FactRole",
    "RenderError",
    "RenderedCalculation",
    "RenderedFact",
    "RenderedGuidance",
    "anchor_label",
    "render_earnings_update",
]
