"""Filed tax, effective tax rate and headline PBT lines for both report paths (data spec §1).

Tax is the filed tax expense, never PBT − PAT. XBRL does not tag the headline PBT incl.
associates separately, so it is PBT plus the filed share of associates/JV. A missing operand
renders ``OPERAND_MISSING``; nothing is inferred.
"""

from __future__ import annotations

from decimal import Decimal

from fundamentals.output.earnings_update import RenderedCalculation

OPERAND_MISSING = "OPERAND_MISSING"
GAP_LABEL = "Non-operating / other income gap (₹ crore)"
TAX_LABEL = "Tax expense (filed, ₹ crore)"
ETR_LABEL = "Effective tax rate (%)"
HEADLINE_LABEL = "Headline PBT incl. associates (₹ crore)"
_PERCENT_QUANTUM = Decimal("0.01")


def format_crore(value: Decimal) -> str:
    """A crore value with thousands grouping, keeping real decimals."""
    if value == value.to_integral_value():
        return f"{value.to_integral_value():,}"
    return f"{value.normalize():,}"


def tax_lines(
    *, pbt: Decimal | None, tax: Decimal | None, sources: str
) -> tuple[RenderedCalculation, RenderedCalculation]:
    """The filed tax line and ETR = filed tax ÷ PBT × 100, both traced to ``sources``."""
    if tax is None or pbt is None:
        trace = f"{OPERAND_MISSING}: no filed tax expense and PBT in {sources}"
        return (
            RenderedCalculation(label=TAX_LABEL, result=OPERAND_MISSING, trace=trace),
            RenderedCalculation(label=ETR_LABEL, result=OPERAND_MISSING, trace=trace),
        )
    rate = (tax / pbt * Decimal(100)).quantize(_PERCENT_QUANTUM)
    return (
        RenderedCalculation(
            label=TAX_LABEL, result=format_crore(tax), trace=f"filed tax expense [{sources}]"
        ),
        RenderedCalculation(
            label=ETR_LABEL,
            result=f"{rate}",
            trace=f"filed tax {format_crore(tax)} ÷ PBT {format_crore(pbt)} × 100 [{sources}]",
        ),
    )


def headline_line(
    *, pbt: Decimal | None, share_of_associates: Decimal | None, sources: str
) -> RenderedCalculation:
    """Headline PBT = PBT + the filed share of associates/JV, traced to ``sources``."""
    if pbt is None or share_of_associates is None:
        trace = f"{OPERAND_MISSING}: no filed share of associates/JV and PBT in {sources}"
        return RenderedCalculation(label=HEADLINE_LABEL, result=OPERAND_MISSING, trace=trace)
    return RenderedCalculation(
        label=HEADLINE_LABEL,
        result=format_crore(pbt + share_of_associates),
        trace=(
            f"PBT {format_crore(pbt)} + share of associates/JV "
            f"{format_crore(share_of_associates)} [{sources}]"
        ),
    )
