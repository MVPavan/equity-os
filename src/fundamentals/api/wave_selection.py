"""Shared ``--wave`` resolution for the watchlist-scoped CLI commands.

Extracted verbatim from :mod:`fundamentals.api.cli` so ``validate``, ``report``
and ``thesis`` keep resolving the wave filter through one seam once each owns
its own module.
"""

from __future__ import annotations

import argparse

from fundamentals.api.watchlist_config import StockConfig, Wave


def _selected_wave(args: argparse.Namespace) -> Wave | None:
    """Resolve the ``--wave`` filter to a :class:`Wave`, or ``None`` when unset."""
    return Wave(args.wave) if args.wave else None


def _require_symbol_in_wave(stock: StockConfig, wave: Wave | None) -> None:
    """Fail closed when an explicit ``--wave`` contradicts the ``--symbol``'s own wave."""
    if wave is not None and stock.wave is not wave:
        raise SystemExit(f"symbol {stock.symbol} is in {stock.wave.value}, not {wave.value}")
