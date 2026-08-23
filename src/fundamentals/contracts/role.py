"""P&L roles shared by reconciliation, configuration, and report rendering."""

from __future__ import annotations

from enum import StrEnum


class FactRole(StrEnum):
    """The six consolidated P&L roles every earnings update carries."""

    REVENUE = "revenue"
    TOTAL_INCOME = "total_income"
    TOTAL_EXPENSES = "total_expenses"
    PROFIT_BEFORE_TAX = "profit_before_tax"
    PROFIT_FOR_PERIOD = "profit_for_period"
    BASIC_EPS = "basic_eps"
