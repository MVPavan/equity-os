"""The verified shapes of the Screener schedule families that are not sums.

Separated from the vocabulary because this module is *evidence*, not design: it
records what three live companies actually returned on 2026-08-26 (TITAN
consolidated, NETWEB standalone, HFCL consolidated), and it is the file to
re-derive when new captures land. The rules for reading it live beside the
types in :mod:`fundamentals.ingest.screener_financials_models`.

Every family here expands into something a sum does not describe — alternative
measures of one figure, or a nested hierarchy with its own subtotals — so each
is exempt from the flat-sum reconciliation gate. That exemption is the most
dangerous thing in this adapter, which is why qualifying for it takes two
independent checks rather than one.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from fundamentals.ingest.screener_financials_models import Section, SubRowKind


class HierarchyRule(BaseModel):
    """A page row that is one sub-row minus another, rather than a sum of them.

    ``Fixed Assets`` is net of depreciation: the page value is ``Gross Block``
    less ``Accumulated Depreciation``. Where the relation is arithmetic and
    verified it is checked, so the family is proven against its page row rather
    than merely exempted from proof.
    """

    model_config = ConfigDict(frozen=True)

    minuend: str
    subtrahend: str


class MixedFamilyShape(BaseModel):
    """The verified shape of one family whose sub-rows are not plain addends.

    Two sets, because a single one is an escape hatch in whichever direction it
    is missing:

    * ``allowed`` — every ``(label, kind)`` seen across the live captures. A row
      outside it means the family may have changed what it decomposes into.
    * ``required`` — the rows that make this family *this* family: its subtotal
      and percent rows, plus any row a registered hierarchy needs. Without it,
      a body of one innocuous row (``{"Land": 999}``) would satisfy "subset of
      allowed" and inherit the exemption, skipping every check with a number
      that is not the page's. Membership of ``allowed`` says a row is familiar;
      ``required`` is what says the *shape* is.

    Both are drawn from TITAN (consolidated), NETWEB (standalone) and HFCL
    (consolidated), 2026-08-26: ``allowed`` is their union, ``required`` is
    verified present in all three.
    """

    model_config = ConfigDict(frozen=True)

    allowed: frozenset[tuple[str, SubRowKind]]
    required: frozenset[tuple[str, SubRowKind]]
    hierarchy: HierarchyRule | None = None


# The four families whose sub-rows are neither all amounts nor all percentages.
# None may be summed: each expands into alternative measures of the same figure
# (``Profit for PE``, ``Profit for EPS``) or into a nested hierarchy with its own
# subtotals (``Gross Block``; ``Working capital changes``), so a flat sum
# restates or double-counts rather than decomposes.
#
# ``required`` is deliberately narrower than the intersection of the three
# captures for the two families whose component rows genuinely vary by company
# (a company with no vehicles has no ``Vehicles`` row): it holds the
# discriminating rows and the hierarchy operands, each verified present on all
# three. For the Net Profit families the restatement rows are present on every
# company, so required is the full intersection.
MIXED_FAMILY_SHAPES: dict[tuple[Section, str], MixedFamilyShape] = {
    (Section.QUARTERS, "Net Profit"): MixedFamilyShape(
        allowed=frozenset(
            {
                ("Minority share", SubRowKind.AMOUNT),
                ("Exceptional items AT", SubRowKind.AMOUNT),
                ("Profit excl Excep", SubRowKind.AMOUNT),
                ("Profit for PE", SubRowKind.AMOUNT),
                ("Profit for EPS", SubRowKind.AMOUNT),
                ("YOY Profit Growth %", SubRowKind.PERCENT),
            }
        ),
        required=frozenset(
            {
                ("Profit excl Excep", SubRowKind.AMOUNT),
                ("Profit for PE", SubRowKind.AMOUNT),
                ("Profit for EPS", SubRowKind.AMOUNT),
                ("YOY Profit Growth %", SubRowKind.PERCENT),
            }
        ),
    ),
    (Section.PROFIT_LOSS, "Net Profit"): MixedFamilyShape(
        allowed=frozenset(
            {
                ("Profit from Associates", SubRowKind.AMOUNT),
                ("Minority share", SubRowKind.AMOUNT),
                ("Exceptional items AT", SubRowKind.AMOUNT),
                ("Profit excl Excep", SubRowKind.AMOUNT),
                ("Profit for PE", SubRowKind.AMOUNT),
                ("Profit for EPS", SubRowKind.AMOUNT),
                ("Profit Growth %", SubRowKind.PERCENT),
            }
        ),
        required=frozenset(
            {
                ("Exceptional items AT", SubRowKind.AMOUNT),
                ("Profit excl Excep", SubRowKind.AMOUNT),
                ("Profit for PE", SubRowKind.AMOUNT),
                ("Profit for EPS", SubRowKind.AMOUNT),
                ("Profit Growth %", SubRowKind.PERCENT),
            }
        ),
    ),
    (Section.BALANCE_SHEET, "Fixed Assets"): MixedFamilyShape(
        allowed=frozenset(
            {
                ("Land", SubRowKind.AMOUNT),
                ("Building", SubRowKind.AMOUNT),
                ("Plant Machinery", SubRowKind.AMOUNT),
                ("Equipments", SubRowKind.AMOUNT),
                ("Computers", SubRowKind.AMOUNT),
                ("Furniture n fittings", SubRowKind.AMOUNT),
                ("Vehicles", SubRowKind.AMOUNT),
                ("Intangible Assets", SubRowKind.AMOUNT),
                ("Other fixed assets", SubRowKind.AMOUNT),
                ("Gross Block", SubRowKind.SUBTOTAL),
                ("Accumulated Depreciation", SubRowKind.AMOUNT),
            }
        ),
        required=frozenset(
            {
                ("Gross Block", SubRowKind.SUBTOTAL),
                ("Accumulated Depreciation", SubRowKind.AMOUNT),
            }
        ),
        hierarchy=HierarchyRule(minuend="Gross Block", subtrahend="Accumulated Depreciation"),
    ),
    (Section.CASH_FLOW, "Cash from Operating Activity"): MixedFamilyShape(
        allowed=frozenset(
            {
                ("Profit from operations", SubRowKind.SUBTOTAL),
                ("Receivables", SubRowKind.AMOUNT),
                ("Inventory", SubRowKind.AMOUNT),
                ("Payables", SubRowKind.AMOUNT),
                ("Loans Advances", SubRowKind.AMOUNT),
                ("Operating borrowings", SubRowKind.AMOUNT),
                ("Other WC items", SubRowKind.AMOUNT),
                ("Working capital changes", SubRowKind.SUBTOTAL),
                ("Direct taxes", SubRowKind.AMOUNT),
                ("Other operating items", SubRowKind.AMOUNT),
            }
        ),
        required=frozenset(
            {
                ("Profit from operations", SubRowKind.SUBTOTAL),
                ("Working capital changes", SubRowKind.SUBTOTAL),
            }
        ),
    ),
}
