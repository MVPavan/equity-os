"""The risk probe's operands per check: one table below both the probe and citation resolution,
which admits exactly these filed amounts (invariant 7, OD-2)."""

from __future__ import annotations

from collections.abc import Mapping

RECEIVABLES, INVENTORIES, PAYABLES = (
    "trade_receivables_current",
    "inventories",
    "trade_payables_current",
)
BORROWINGS = ("borrowings_current", "borrowings_noncurrent")
EQUITY, REVENUE, CFO, PROFIT, CAPEX = (
    "total_equity",
    "revenue_from_operations",
    "cfo",
    "profit_for_period",
    "cf_capex_ppe",
)
M = ("cost_of_materials_consumed", "purchases_of_stock_in_trade", "changes_in_inventories")
# Each check's numerator and denominator ids; the denominator's are summed.
OPERANDS: Mapping[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "R1": ((RECEIVABLES,), (REVENUE,)),
    "R2": ((INVENTORIES,), M),
    "R3": ((PAYABLES,), M),
    "R4": ((CFO,), (PROFIT,)),
    "R5": ((CAPEX,), (REVENUE,)),
    "R6": (BORROWINGS, (EQUITY,)),
}


def key(check_id: str) -> str:
    """A check's claim key."""
    return f"probe.{check_id}"


FILED_KEYS = {
    f"{key(check_id)}.{operand}": operand
    for check_id, (numerator, denominator) in OPERANDS.items()
    for operand in numerator + denominator
}
