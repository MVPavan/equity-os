# Canonical dictionary v1 — resolved manifest

Status: hand-authored for D1a Task 3 (stage `eqos-3f9.2`), 2026-10-12; revised the same day for
the stage 2 review findings. Source of the rows:
[canonical field coverage inventory](../../research/canonical-field-coverage-inventory.md) §2
(2a–2f, 224 draft rows), resolved under the rules of the
[data spec](../2026-10-11-canonical-financial-data-and-cross-source-comparison.md) §1. Artifact:
`config/dictionary/v1/` (`derived.yaml` is the formula set, pinned separately).

The counts below were counted by hand from the inventory dispositions in this file, not copied
from the loader. `tests/fundamentals/test_canon_dictionary_load.py` compares this table with
`CanonicalDictionary.family_counts()`. A mismatch means one of the two is wrong; never fix it by
copying the loader's output.

## Resolution rules

1. **Every filed line item plus the vendor formula rows** (spec §1, plan Task 3). A vendor formula
   row whose construction is unresolved is deferred with a cited reason (below), never silently
   dropped. Rows that are not numeric dictionary rows at all (names, period kinds, price-dependent
   ratios, mappings) are excluded with their reason.
2. **Numeric only.** Segment, item, holder and share-class names are dimension members, not rows.
3. **Grouped entries become one id per measure.** A row is grouped when its id joins several ids
   (`a / b`), ends in "etc.", or its description lists distinct measures; current and non-current
   balance-sheet items are always distinct measures. Each filed XBRL element is its own measure:
   purchases and sales, payments and receipts, acquisitions and disposals, advances and
   repayments, and current and non-current flows are never netted into one row. An issuer's
   condensed or net PDF line (Apar FY26 Q2 results p7 "trade and other receivables", "trade and
   other payables", "Sale / (purchase) of investments- net", "short-term borrowings. net") is a
   distinct filed measure with its own row, not a netting rule over the element rows; it is
   declared as an aggregate construction only when a source evidences its composition (none does
   in v1).
4. **Templated rows** (`[n]`, `[k]`, `[h]`) are one row each with a dimension template; shareholding
   categories are members of one row (spec §1).
5. **Formula rows live in `derived.yaml`** (family `DERIVED`), whatever inventory section listed
   them. Every v1 formula is `EQUIVALENCE_UNPROVEN` with no qualification scope. A vendor formula
   string is a hint (inventory §4 conflict 12): it is declared only once each operand resolves to
   an evidenced dictionary row.
6. **Closing stocks are instants.** Paid-up capital, face value and reserves are balances. XBRL
   files them in the results column's duration context; they are normalised to the instant at
   that context's end date, and formulas read them with the `CLOSING` role. EPS stays a duration.

## Counts per family

| Family | Rows |
|---|---|
| PL | 53 |
| BALANCE_SHEET | 68 |
| CASH_FLOW | 96 |
| SEGMENT | 20 |
| SHAREHOLDING | 4 |
| DERIVED | 18 |
| **Total** | **259** |

## Reconciliation with the inventory (224 rows)

| Section | Inventory rows | Kept as one row | Moved to `DERIVED` | Excluded | Deferred to D1b | Split or collapsed | v1 rows in family |
|---|---|---|---|---|---|---|---|
| 2a P&L | 53 | 51 | 1 (`shares_outstanding`) | 1 | 0 | +2 OCI detail template rows | 53 |
| 2b Balance sheet | 65 | 62 | 1 (`net_current_assets`) | 1 | 1 (`borrowings_total`) | +1 (`deferred_government_grants` → 2), +1 (`trade_payables_msme_noncurrent`), +4 separately filed derivative measures | 68 |
| 2c Cash flow | 51 | 33 | 1 (`cf_wc_total`) | 0 | 0 | 17 grouped rows → 61 rows (+44; table below), +2 added filed lines | 96 |
| 2d Segment | 16 | 14 | 1 (`segment_capital_employed`) | 1 | 0 | +2 (`segment_assets_total` → 3), +2 (`segment_liabilities_total` → 3), +2 separately filed reconciliation measures | 20 |
| 2e Shareholding | 13 | 3 | 0 | 0 | 0 | 10 category rows → 1 templated row | 4 |
| 2f Derived | 26 | 11 | — | 4 | 10 | `working_capital_days etc.` → `receivable_days` (its other 4 ids deferred) | 12 |

2c: 51 − 1 moved = 50; 33 kept as one row + 61 rows from the 17 split rows + 2 added rows = 96.
The 61 are 57 filed XBRL elements plus 4 filed PDF lines with no element of their own (rule 3).
The 2 added rows are filed lines with no inventory row (below). 2f: 26 = 11 kept
(9 as before plus `net_profit_margin_pct` and `gross_margin_pct`, restored) + 1 split
(`working_capital_days etc.`) + 10 deferred + 4 excluded; v1 rows = 11 + 1 (`receivable_days`) = 12.

`DERIVED` = 12 (2f) + 4 moved from 2a–2d + 2 spec-mandated rows (`liabilities_incl_nci`, spec §2;
`segment_revenue_members_total`, spec §1 dimensional aggregation and plan Task 3) = **18**.

### Renamed, split, added and collapsed rows

| Inventory row | v1 row(s) | Reason |
|---|---|---|
| `operating_expenses_ex_fin_da` | `opex_excl_finance_and_da` | Spec §1 name |
| `operating_profit_vendor` | `ebitda_excl_other_income` | Spec §1 "EBITDA excluding other income" |
| `working_capital_days etc.` | `receivable_days`; deferred `inventory_days`, `payable_days`, `cash_conversion_cycle_days`, `working_capital_days` | Grouped. Receivable days has a stated construction (spec Stage 1 fixture) and is defined on current trade receivables only; the inventory gives only vendor labels for the other four |
| `deferred_government_grants` | `deferred_government_grants_current`, `deferred_government_grants_noncurrent` | Grouped current / non-current |
| `trade_payables_msme` | `trade_payables_msme` (current), `trade_payables_msme_noncurrent` | The inventory cites both XBRL elements |
| Derivatives folded into other financial assets/liabilities | `derivative_financial_assets_noncurrent`, `derivative_financial_assets_current`, `derivative_financial_liabilities_noncurrent`, `derivative_financial_liabilities_current` | Rule 3: retained Apar FY26 Q2 results PDF p6 prints four distinct lines: 2.49, 79.69, dash (comparative 3.75), and 25.08 crore, respectively. A folded XBRL measure does not replace separately filed PDF measures |
| Additional segment reconciliation lines | `segment_other_elimination`, `inter_segment_liabilities` | Rule 3: the same PDF p4 prints other elimination (4.11 crore deducted in Q2) and inter-segment liabilities (656.59 crore deducted at 30 September 2025) separately |
| `cf_adj_provisions` | `cf_adj_provisions_current`, `cf_adj_provisions_noncurrent` | Current / non-current elements |
| `cf_adj_other_noncash` | `cf_adj_other_noncash`, `cf_adj_other_investing_financing`, `cf_adj_other_reconcile` | Three residual elements |
| `cf_wc_trade_receivables` | `cf_wc_trade_receivables_current`, `cf_wc_trade_receivables_noncurrent`, `cf_wc_trade_and_other_receivables` | Current / non-current elements; the inventory's PDF column is the condensed "trade and other receivables" line (H1 FY26 consolidated −232.97, standalone −206.80 crore) |
| `cf_wc_trade_payables` | `cf_wc_trade_payables_current`, `cf_wc_trade_payables_noncurrent`, `cf_wc_trade_and_other_payables` | Current / non-current elements; the PDF line is "trade and other payables" (H1 FY26 consolidated −300.48, standalone −368.82 crore) |
| `cf_wc_other_assets_liabilities` | `cf_wc_other_current_assets`, `cf_wc_other_noncurrent_assets`, `cf_wc_other_current_liabilities`, `cf_wc_other_noncurrent_liabilities`, `cf_wc_other_financial_assets_current`, `cf_wc_other_financial_assets_noncurrent`, `cf_wc_other_financial_liabilities_current`, `cf_wc_other_financial_liabilities_noncurrent`, `cf_wc_other_bank_balances` | Nine elements |
| `cf_interest_dividend_operating` | `cf_interest_paid_operating`, `cf_interest_received_operating`, `cf_dividends_received_operating` | Three elements |
| `cf_income_taxes_paid` | `cf_income_taxes_paid`, `cf_income_taxes_paid_investing`, `cf_income_taxes_paid_financing` | The inventory cites the operating, investing and financing elements |
| `cf_intangibles_other_lt_assets` | `cf_purchase_*` and `cf_sale_*` for `intangible_assets`, `intangibles_under_development`, `goodwill`, `investment_property`, `biological_assets`, `other_long_term_assets` | Twelve elements: purchase vs sale, per asset class |
| `cf_investments_purchase_sale` | `cf_purchase_equity_debt_instruments`, `cf_sale_equity_debt_instruments`, `cf_purchase_jv_interests`, `cf_sale_jv_interests`, `cf_investments_net` | Purchases vs sales; instruments vs JV interests; the PDF column is the net "Sale / (purchase) of investments- net" line (H1 FY26 consolidated 198.26, standalone 198.76 crore) |
| `cf_subsidiaries_acquisition_disposal` | `cf_obtaining_control_subsidiaries`, `cf_losing_control_subsidiaries` | Acquisitions vs disposals |
| `cf_loans_advances_investing` | `cf_loans_advances_made`, `cf_loans_advances_repaid` | Advances vs repayments |
| `cf_derivative_contracts_investing` | `cf_derivative_payments_investing`, `cf_derivative_receipts_investing` | Payments vs receipts |
| `cf_partnership_firms` | `cf_partnership_investment`, `cf_partnership_profit_share` | Investment vs profit share |
| `cf_proceeds_shares` | `cf_proceeds_shares`, `cf_proceeds_other_equity_instruments`, `cf_proceeds_stock_options` | Three elements |
| `cf_buyback_equity_payments` | `cf_payments_redeem_own_shares`, `cf_payments_other_equity_instruments` | Two elements |
| `cf_ownership_changes_subsidiaries` | `cf_proceeds_ownership_changes_subsidiaries`, `cf_payments_ownership_changes_subsidiaries` | Proceeds vs payments |
| `cf_proceeds_borrowings` | `cf_proceeds_borrowings`, `cf_proceeds_debentures`, `cf_short_term_borrowings_net` | Two elements; the inventory's PDF column names a short-term net line ("Proceeds/(repayments) from short-term borrowings. net", 41.45 crore) besides the gross long-term proceeds line |
| `segment_assets_total` | `segment_assets_total`, `segment_unallocable_assets`, `segment_assets_net` | Grouped total / unallocable / net |
| `segment_liabilities_total` | `segment_liabilities_total`, `segment_unallocable_liabilities`, `segment_liabilities_net` | Grouped total / unallocable / net |
| `oci_not_reclassified_items`, `oci_reclassified_items` | + `oci_not_reclassified_items_detail`, `oci_reclassified_items_detail` | Spec §1 OCI detail template; the XBRL axes are cited in the inventory and present in every retained Apar instance |
| `segment_revenue[k]`, `segment_result[k]`, `segment_assets[k]`, `segment_liabilities[k]` | `segment_revenue`, `segment_result`, `segment_assets`, `segment_liabilities` | Templated (`segment`) |
| `other_expenses_detail[n]` | `other_expenses_detail` | Templated (`other_expense_detail`) |
| `shp_promoter_pct`, `shp_fpi_pct`, `shp_dii_pct`, `shp_mutual_funds_pct`, `shp_other_dii_pct`, `shp_insurance_pct`, `shp_government_pct`, `shp_public_pct`, `shp_others_pct`, `shp_custodian_dr_pct` | `shp_holding_pct` | Categories are dimension members (spec §1) |
| `shp_holder_detail[h]` | `shp_holder_pct` | Templated (`shareholding_holder`) |

Every cash-flow element named in a split is present in the retained Apar X-Q2 and FY26 annual
XBRL instances. The four PDF-line rows are on p7 of the retained Apar FY26 Q2 results PDF.

### Added filed lines (beyond the 224-row inventory)

Two adjustment lines on p7 of the retained Apar FY26 Q2 results PDF have no inventory row; rule 1
("every filed line item") adds them. Neither has an XBRL element with its meaning: Apar X-Q2
carries the H1 FY26 consolidated values only under working-capital elements
(`AdjustmentsForDecreaseIncreaseInOtherNoncurrentAssets` 9.58,
`AdjustmentsForOtherFinancialAssetsCurrent` −7.21 crore), so no element is claimed.

| v1 row | PDF line | Printed values (₹ crore; H1 FY26 cons / std, H1 FY25 cons / std) | Kept distinct from |
|---|---|---|---|
| `cf_adj_gain_loss_sale_ppe` | "(Gain)/loss on sale of property, plant and equipment" | 9.58 / 9.58, 0.09 / 0.09 | `cf_sale_ppe` (disposal proceeds) |
| `cf_adj_profit_sale_investments` | "Profit on sale of investments" | −7.21 / −6.94, −3.07 / −2.90 | `cf_adj_fair_value` (equivalence unproven, inventory §2c); `cf_sale_equity_debt_instruments`, `cf_investments_net` |

`tests/fundamentals/test_canon_dictionary_load.py` names all 30 printed p7 lines by their v1 ids
and checks each id exists.

### Restored vendor formula rows

| Inventory row | v1 row | Construction |
|---|---|---|
| `net_profit_margin_pct` | `net_profit_margin_pct` | Tijori qt_c "Net Profit Margin" = Net Profit / Net Sales × 100, measured on one row (THERMAX Jun-26); Net Profit = `profit_continuing_after_tax` (§4 conflict 2), Net Sales = `revenue_from_operations` (2a) |
| `gross_margin_pct` | `gross_margin_pct` | Tijori fr_c "Gross Margin (%)" = 100 − Tijori "Material Cost (%)", whose operands resolve to `cost_of_materials_consumed`, `changes_in_inventories` and `revenue_from_operations`; declared as (r − m − c) / r × 100 |

Both are `EQUIVALENCE_UNPROVEN`.

### Deferred to D1b (bead under epic eqos-u0u: 'Resolve deferred vendor formula rows before D1b vendor comparisons')

| Inventory row | Deferred id(s) | Reason |
|---|---|---|
| `borrowings_total` | `borrowings_total` | Construction unresolved: `borrowings_noncurrent + borrowings_current` "± lease" (2b); Screener "Borrowings" also adds other borrowings and preference capital |
| `ebit_vendor` | `ebit_vendor` | Only a Tijori formula string, `Operating_profit − Depreciation`, whose `Operating_profit` "appears to include other income" (one THERMAX row); not executable truth (§4 conflict 12) |
| `profit_excl_exceptional` | `profit_excl_exceptional` | Screener S-sch formula unproven; depends on `exceptional_items_after_tax`, a vendor-only concept with no first-party construction |
| `profit_for_pe` | `profit_for_pe` | "≈ owners profit excl. exceptional"; no stated construction |
| `free_cash_flow` | `free_cash_flow` | "CFO − capex": gross vs net capex undecided (vendors use a net capex of unstated composition) |
| `roce_pct` | `roce_pct` | Tijori fr_c string (OP − D&A) / (total assets − current liabilities): its OP operand does not resolve to an evidenced row (the fr_c `Operating_profit` appears to include other income) and the balance-sheet role (closing or average) is unstated; Screener and Upstox undefined |
| `roe_roa_pct` | `roe_pct`, `roa_pct` | No stated construction (Tijori fr_c names only) |
| `debt_to_equity` | `debt_to_equity` | No stated construction; its debt operand is the deferred `borrowings_total` |
| `interest_coverage` | `interest_coverage` | "EBIT ÷ interest" with EBIT unresolved (`ebit_vendor` deferred) |
| `current_quick_ratio` | `current_ratio`, `quick_ratio` | No construction stated in the sources (vendor labels only) |
| `dividend_payout_pct` | `dividend_payout_pct` | No construction stated in the sources (vendor labels only) |
| `working_capital_days etc.` | `inventory_days`, `payable_days`, `cash_conversion_cycle_days`, `working_capital_days` | Vendor labels only (Screener ratios, Tijori fr_c); no construction |

D1b disposition, 2026-10-13 (Codex session, handoff run): all 17 deferred ids above are
`EXCLUDED_UNPROVEN` within the presently authorized retained inputs. The
[complete source-cited ledger](stage1-source-inventory.md#deferred-construction-dispositions)
records every id, exact native source locator and unresolved construction; the
[independent review](../../workstreams/data-foundation/reviews/D1b-source-inventory-review.md)
approves each exclusion. Native rows remain evidence and are not zero-filled or silently
remapped. These exclusions do not reduce the Stage 1 oracle or waive missing vendor measurements.
No v1 dictionary row was added by this disposition. The separately spec-defined Screener
Other Income construction belongs in a reviewed next-version release, preserving v1 replay.

### Excluded inventory rows

| Inventory row | Reason |
|---|---|
| `exceptional_items_after_tax` | Vendor-only concept (Screener S-sch); not a filed line, and no restored construction needs it |
| `gross_block / accumulated_depreciation` | Vendor rows; not in results filings (XBRL and PDF absent) |
| `segment_name[k]` | A name, so a dimension member (`segment` template), not a numeric row |
| `ebitda` | "Canonical definition to be chosen" (inventory open question 10); `ebitda_excl_other_income` is the evidenced construction |
| `ttm_revenue / ttm_net_profit` | TTM is a period kind derived by period aggregation (`ADDITIVE_DURATION`), not a row |
| `valuation_ratios` | Price-dependent; prices and market data are out of scope (spec Decisions) |
| `upstox_total_liability` | A mapping to `total_liabilities`, not a new row |

Filing metadata (period dates, nature of report, rounding level, currency, symbol and so on) is not
a §2 table row; it is occurrence metadata and settings, not dictionary rows.

## Template instantiation rules

Templates are declared in `config/dictionary/v1/templates.yaml`.

| Template | Axes | Instantiation |
|---|---|---|
| `segment` | `segment` (entity evidence), `elimination_basis` (`PRE_ELIMINATION`, `POST_ELIMINATION`) | One `segment` member per reportable segment, recorded per entity with its `DescriptionOfReportableSegment` occurrence. Member id = the description lower-cased, every run of non-alphanumeric characters replaced by one underscore, leading and trailing underscores removed. Aligned by description, never by context ordinal. `reportable_segments_total` is the declared aggregate member. Pre- and post-elimination figures are distinct keys. |
| `other_expense_detail` | `other_expense_item` (entity evidence) | One member per `DescriptionOfOtherExpenses` on `DetailsOfOtherExpensesAxis`; id from the description as for segments |
| `oci_not_reclassified_detail` | `oci_item` (entity evidence) | One member per `DescriptionOfItemThatWillNotBeReclassifiedToProfitAndLoss` on `ItemsThatWillNotBeReclassifiedToProfitAndLossAxis` |
| `oci_reclassified_detail` | `oci_item` (entity evidence) | One member per `DescriptionOfItemThatWillBeReclassifiedToProfitAndLoss` on `ItemsThatWillBeReclassifiedToProfitAndLossAxis` |
| `shareholding_category` | `shareholding_category` (closed list), `share_class` (entity evidence), `denominator` (`TOTAL_SHARES`, `VOTING_RIGHTS`, `PROMOTER_HOLDING`) | Categories: `promoter_group`, `fpi`, `dii` (aggregates `mutual_funds` and `other_dii`), `mutual_funds`, `other_dii` (aggregates `insurance`), `insurance`, `government`, `public`, `others`, `custodian_dr`. A list never sums a member with one it contains |
| `shareholding_holder` | `holder` (entity evidence), `share_class`, `denominator` (`TOTAL_SHARES`, `VOTING_RIGHTS`) | One member per named holder disclosed; the disclosure threshold is occurrence metadata |
| `shareholding_pledge` | `share_class` (entity evidence), `denominator` (`TOTAL_SHARES`, `VOTING_RIGHTS`, `PROMOTER_HOLDING`) | The pledged percentage per share class and stated denominator; which denominators an SHP prints is unevidenced, so none is assumed |

The one v1 dimensional aggregation, `segment_revenue_members_total`, sums `segment_revenue` into
`reportable_segments_total`. It lists no members: `member_binding: ENTITY_EVIDENCE` binds the
closed list at evaluation to the entity's recorded `segment_members` valid for the period (Task 2
repository read `segment_members_as_of`), pinned as an input; `missing_member: OPERAND_MISSING`
makes any bound member without a value fail the aggregate. A `DECLARED` list is allowed only over
a closed-list axis. The loader checks that every formula output carries its operands' axes and
declares the aggregate member, and that every shared axis keeps its member source and closed
members (a retained axis also its aggregate members) from operand to output (`DIMENSION_MISFIT`).

## Applicability rules

`config/dictionary/v1/applicability.yaml`. Basis refusals run first for every row: a
`CONSOLIDATED` request for a `STANDALONE_ONLY` entity (`basis.standalone_only_entity`), then a
basis outside the row's `basis_applicability` (`basis.row_basis_applicability`).

| Rule | Rows | Applicable when |
|---|---|---|
| `results.every_period` | P&L except the two below; derived rows over P&L operands (incl. `shares_outstanding`) | Financial results, any reporting kind |
| `results.annual_disclosure` | `reserves_excl_revaluation`, `excise_duty` (inventory periodicity FY) | Year; any other reporting kind only when the package contains the row's line (`disclosed_rows`) |
| `results.segment` | Segment; `segment_capital_employed`, `segment_revenue_members_total` | Any reporting kind for a requested basis among the entity's evidenced segment bases (required, so a missing value is later `NO_SOURCE`); otherwise only when the package contains a segment statement, else genuinely `NOT_APPLICABLE`. Apar: consolidated only |
| `results.balance_sheet` | Balance sheet; `receivable_days`, `liabilities_incl_nci`, `net_current_assets` | Half-year or year; quarter or nine-month only with a balance sheet in the package |
| `results.cash_flow` | Cash flow; `cfo_to_op_pct`, `cf_wc_total` | Half-year or year; quarter or nine-month only with a cash flow in the package |
| `shareholding.every_period` | Shareholding | Shareholding-pattern filings, any reporting kind |

## Tier scoping note

`scoped_tier` returns `RELATED_NOT_EQUIVALENT` (and any tier below demonstrated) unchanged. This
is the reading of the plan's "anything else … is `EQUIVALENCE_UNPROVEN`" wording: the clause
governs a demonstrated tier whose scope does not hold; scope can withhold strength, never add it
or rewrite a weaker classification.
