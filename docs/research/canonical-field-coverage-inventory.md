# Canonical field coverage inventory — Indian listed non-financial companies (research evidence)

Status: research draft, 2026-10-11. Scope: non-financial issuers under Ind AS; banks, NBFCs and
insurers are out of scope. Evidence is what the repo holds, plus a handful of measurements I ran
on retained artifacts (scripts in `scratchpad/canonical-spec/*.py`, all read-only, offline).

## 1. Method

### Evidence base

The sample is small and the conclusions are only as wide as the sample:

- **XBRL**: one issuer under the new `in-capmkt` taxonomy (APARINDS, 8 filings, all
  consolidated) and nine Q3FY25 filings under the older `in-bse-fin` taxonomy (CGPOWER,
  ETERNAL, HFCL, LAURUSLABS, MTARTECH, POLYCAB, SONACOMS, THERMAX, TITAN).
- **PDF**: one results PDF (APARINDS FY26 Q2), text read with `pypdf`.
- **Screener and Tijori**: ten retained captures each, for the same watchlist.
- **Upstox**: no raw bodies were read. Everything in that column comes from the research docs.
- **SHP**: no artifacts at all.

### How I measured the vendors

Vendor rows were measured against the XBRL `OneD` context (Oct–Dec 2024) of the nine Q3FY25
filings:

- Screener: the `Dec 2024` column of `section_quarters.json`.
- Tijori: the `Dec 2024` column of the `qt_c` table in the retained `fin_tables_data` island.

A row counts as "agrees" when the difference is within vendor rounding. That is ±0.5 crore for
Screener's integer crore, and 2 dp for Tijori.

### Cell vocabulary

The vocabulary follows the brief, with two qualifiers:

- `NATIVE [M]` — a vendor row was measured against a filing.
- `NATIVE [U]` — a vendor row exists, but its equivalence to the filing is unproven.
- XBRL and PDF `NATIVE` cells are first-party by definition.

### Coverage count

The coverage column reads `n (m)`:

- `n` = sources with NATIVE (any) or a MEASURED FORMULA.
- `m` = the measured subset, i.e. XBRL/PDF NATIVE + vendor `[M]` + MEASURED FORMULA.
- SHP never counts. Its cells are general knowledge only.

### Evidence keys (used in cells)

| Key | File(s) |
|---|---|
| X-Q2 | `data/raw/watchlist/aparinds/nse/INTEGRATED_FILING_INDAS_1560713_29102025085858_WEB.xml` (in-capmkt 2025-01-31; Q2FY26; contexts `OneD` quarter, `FourD` H1, `OneI` 30-Sep-25, `PY_I` 31-Mar-25; 227 element names) |
| X-Q1 | `…/INTEGRATED_FILING_INDAS_1496866_29072025062446_WEB.xml` (Q1FY26; 93 element names — **no balance sheet, no cash flow**) |
| X-Q4 | `…/INTEGRATED_FILING_INDAS_1439170_14052025093124_WEB.xml` (Q4FY25; `FourD` = FY; 245 names; adds e.g. `ReserveExcludingRevaluationReserves`, `NonControllingInterest`, `DeferredTaxAssetsNet`) |
| X-BSE | `…/INDAS_113920_1293440_30102024104705.xml` (in-bse-fin 2020-03-31; 229 names) |
| X9 | `data/raw/watchlist/<sym>/nse/INDAS_*.xml`, nine Q3FY25 in-bse-fin consolidated filings |
| PDF | `data/raw/watchlist/aparinds/nse_pdf/APARINDS-FY26_Q2-results.pdf`: p3 P&L (consolidated and standalone side by side), p4 segments (consolidated only, Note 3), p6 BS, p7 CF |
| S | `data/raw/watchlist/screener-financials/<SYM>/consolidated/section_*.json` (union over the 10 stocks; NETWEB is standalone only) |
| S-sch | `…/schedules/*.raw.json` (expander sub-rows; union over 10 stocks) |
| S-page | `…/TITAN/consolidated/screener_financials_page.raw.html` (shareholding row labels, top ratios) |
| T | `data/raw/snapshots/v1/tijori/financials/<slug>/*/body.bin` → island `fin_tables_data` (keys `qt_c qt_s pl_c_s pl_c_d pl_s_* bs_c_s bs_c_d bs_s_* cf_c cf_s fr_c fr_s growth`; every row carries a vendor `formula` string) |
| U-doc | `docs/research/upstox-api-schemas/fundamentals.md` (§"LANE B LIVE VERIFICATION — 2026-09-04", share-holdings section) |
| LB | `docs/research/upstox-lane-b-first-measurement.md` |
| 3S | `docs/research/three-source-first-measurement.md` |
| MEAS | my replays: `scratchpad/canonical-spec/measure_screener.py`, `measure_tijori.py` (X9 vs S/T, Dec 2024), plus ad-hoc checks noted inline |
| RL / SM / INV | `docs/research/screener/ratio-library.md` / `docs/research/screener/surface-map.md` / `docs/research/screener-tijori-endpoint-inventory.md` |
| MAP / XC | `src/fundamentals/verify/three_source_map.py` / `src/fundamentals/ingest/screener_crosscheck.py` |

### Files read

**Code:**

- `src/fundamentals/verify/three_source_map.py`
- `src/fundamentals/extract/xbrl_taxonomies.py`
- `src/fundamentals/extract/xbrl_parser.py` (header and namespace sections)
- `src/fundamentals/contracts/role.py`
- `src/fundamentals/reconcile/fact_view.py` (header)
- `src/fundamentals/ingest/tijori_pl.py` (header)
- `src/fundamentals/ingest/tijori_tables.py` (table keys)
- `src/fundamentals/ingest/tijori_shareholding_breakup.py` (header)
- `src/fundamentals/ingest/tijori_shareholding.py` (string grep)
- `src/fundamentals/ingest/screener_shareholding.py` (header)
- `src/fundamentals/ingest/screener_segments.py` (header)
- `src/fundamentals/ingest/screener_company_models.py` (bucket constants)
- `src/fundamentals/ingest/screener_crosscheck.py` (line map)
- `src/fundamentals/ingest/upstox_statements.py` (grep)
- `src/fundamentals/extract/pdf_column_geometry.py` (grep)
- `tests/fundamentals/fixtures/synthetic_tijori_shareholding.html` (labels only; synthetic)

**Docs:**

- `docs/research/screener/ratio-library.md`
- `docs/research/screener/surface-map.md` (§3, §10)
- `docs/research/screener-tijori-endpoint-inventory.md`
- `docs/research/upstox-api-schemas/fundamentals.md` (head, share-holdings, Lane B block)
- `docs/research/upstox-api-schemas/VERIFICATION.md` (grep)
- `docs/research/three-source-first-measurement.md`
- `docs/research/upstox-lane-b-first-measurement.md` (Parts 1–2)

**Artifacts:** all the files under X-Q2, X-Q1, X-Q4, X-BSE, X9, PDF, S, S-sch, S-page, T, and
`data/gold/THERMAX-Q3FY25.json`.

**Not read:**

- `three_source.py`, beyond its role as consumer of the map.
- Most of the `screener_*` and `tijori_*` modules beyond their headers.
- `tijori_overview_*` (Revenue Mix), beyond one grep.
- Any Upstox raw capture.

### Per-source periodicity and basis limits (applies to every table below)

| Source | Periodicity actually observed | Basis |
|---|---|---|
| XBRL | P&L every filing: `OneD` = quarter, `FourD` = YTD (H1 at Q2, 9M at Q3, FY at Q4). BS: `OneI` only, and **only in Q2 and Q4 filings** (X-Q1 has none). The BS carries no comparative March column, apart from `CashAndCashEquivalentsCashFlowStatement` at `PY_I`. CF: `FourD` only, Q2 (H1) and Q4 (FY) filings. | `NatureOfReportStandaloneConsolidated`. All retained files are Consolidated. Standalone XBRL is not retained (UNKNOWN in repo). |
| PDF | Quarter, previous quarter, YoY quarter, H1, previous H1, previous FY (Apar p3). BS: half-year end plus previous March. CF: H1 plus previous H1. | Both bases on the same page (Apar). Segments consolidated only (Apar Note 3). |
| Screener | `quarters`: 13 quarters. `profit-loss`: annual + TTM. `balance-sheet` and `cash-flow`: annual, **Mar year-ends only** (no half-year BS observed). | `/consolidated/` vs bare URL; schedules select basis by key presence (SM §10). |
| Tijori | `qt_*`: 10 quarters. `pl_*`: annual, with the last column labelled `Jun 2026`, which equals TTM (THERMAX Sales 10,839.35 = Screener TTM 10,839; one stock). `bs_*`, `cf_*`, `fr_*`: annual. | `_c` / `_s` table keys. The repo parser assumes scope (`SCOPE_ASSUMED_NOTE`, `tijori_pl.py`). |
| Upstox | Four periods per surface. `income-statement` summary is quarterly or yearly; **`full_statement` is annual-only, even on a quarterly request**. BS and CF ignore `time_period` (U-doc §2). Surfaces are not period-aligned per company (LB). | `?type=`. key-ratios does not echo basis (U-doc §4). |
| SHP | Quarterly filing (general knowledge). | Not applicable. |

## 2. Matrix

### 2a. P&L — SEBI results format (periodicity: Q, H, 9M, FY; basis C and S unless noted)

| canonical_id | description | periodicity | XBRL | PDF | Screener | Tijori | Upstox | SHP | cov |
|---|---|---|---|---|---|---|---|---|---|
| `sales` | Sales of products/services (before other operating income) | Q/H/FY | ABSENT — no element in X-Q2/X-Q4/X-BSE | NATIVE: "1 Sales" (p3) | ABSENT — Screener "Sales" is `revenue_from_operations` (below) | UNKNOWN — `pl_c_d` "Gross Sales" (annual; THERMAX Mar-26 = its Net Sales) | UNKNOWN | — | 1 (1) |
| `other_operating_income` | Other operating revenue | Q/H/FY | ABSENT (no element in instances) | NATIVE: "2 Other operating incomes" | ABSENT (no separate row) | UNKNOWN | UNKNOWN | — | 1 (1) |
| `revenue_from_operations` | Revenue from operations | Q/H/FY | NATIVE: `RevenueFromOperations` | NATIVE: "3 Revenue from operations (1+2)" | NATIVE [M]: "Sales" (quarters, profit-loss); 8/9 agree, THERMAX +0.84 % (3S) | NATIVE [M]: `qt_c` "Net Sales" 8/9, THERMAX +0.83 % (3S); `pl_*` "Sales"/"Net Sales" annual [U] | NATIVE [U]: `full_statement` "Revenue" (annual only) | — | 5 (4) |
| `excise_duty` | Excise duty (legacy, pre-GST) | FY | ABSENT in observed instances | ABSENT (Apar) | ABSENT | NATIVE [U]: `pl_c_d` "Less: Excise Duty" (null for THERMAX) | ABSENT | — | 1 (0) |
| `other_income` | Other income | Q/H/FY | NATIVE: `OtherIncome` | NATIVE: "4 Other incomes" | Page row "Other Income" = FORMULA `other_income + exceptional_items_before_tax`, MEASURED (SONACOMS 46.79 − 5.70 = 41.09 vs 41; other 8 have exceptional 0); S-sch sub-row "Other income normal" NATIVE [M] (5/6 checked; HFCL 20.69 = OI 20.04 + associates 0.65) | NATIVE [M]: "Other Income" 9/9 (excludes exceptional) | NATIVE [U]: `full_statement` "Other Income" | — | 5 (4) |
| `total_income` | Total income | Q/H/FY | NATIVE: `Income` | NATIVE: "5 Total income (3+4)" | FORMULA UNPROVEN: Sales + Other Income (OI carries exceptional, so not the filing identity) | ABSENT (no row in qt/pl) | NATIVE [U]: `full_statement` "Total Revenue" and summary `revenue` (equal to each other in 48/51 identity checks, U-doc §3); vs Screener Sales+OI RELATED_NOT_EQUIVALENT, 19/40 anomalies (LB) | — | 3 (2) |
| `cost_of_materials_consumed` | (a) Cost of materials consumed | Q/H/FY | NATIVE: `CostOfMaterialsConsumed` | NATIVE: "(a) Costs of materials consumed" | ABSENT as value (only inside "Material Cost %", §2f) | NATIVE [M]: `qt_*` "Operating Expenses/Raw Material" 8/9, THERMAX +20.96; `pl_*` "Raw Material" annual [U] | ABSENT (not among the 9 particulars) | — | 3 (3) |
| `purchases_of_stock_in_trade` | (b) Purchases of stock-in-trade | Q/H/FY | NATIVE: `PurchasesOfStockInTrade` | NATIVE: "(b) Purchases of stock-in-trade" | ABSENT (only inside Material Cost %) | ABSENT — no row; e.g. TITAN 1,895 sits in an unlabelled residual of "Operating Expenses" | ABSENT | — | 2 (2) |
| `changes_in_inventories` | (c) Changes in inventories of FG, WIP, stock-in-trade | Q/H/FY | NATIVE: `ChangesInInventoriesOfFinishedGoodsWorkInProgressAndStockInTrade` | NATIVE: "(c) Changes in inventories…" | ABSENT (only inside Material Cost %) | NATIVE [M]: "Increase/Decrease in Stock" 8/9 (HFCL 86.79 vs 84.63) | ABSENT | — | 3 (3) |
| `employee_benefits_expense` | (d) Employee benefits expense | Q/H/FY | NATIVE: `EmployeeBenefitExpense` | NATIVE: "(d) Employee benefits expense" | ABSENT as value on page (only "Employee Cost %", §2f); RL screen field "Employee cost last year" UNKNOWN | NATIVE [M]: "Employee Cost" 9/9 | ABSENT | — | 3 (3) |
| `finance_costs` | (e) Finance costs | Q/H/FY | NATIVE: `FinanceCosts` | NATIVE: "(e) Finance costs" | NATIVE [M]: "Interest" 9/9 | NATIVE [M]: "Interest" 9/9 | ABSENT | — | 4 (4) |
| `depreciation_amortisation` | (f) Depreciation and amortisation | Q/H/FY | NATIVE: `DepreciationDepletionAndAmortisationExpense` | NATIVE: "(f) Depreciation and amortisation expense" | NATIVE [M]: "Depreciation" 9/9 | NATIVE [M]: "Depreciation and Amortization" 9/9 | ABSENT | — | 4 (4) |
| `other_expenses` | (g) Other expenses | Q/H/FY | NATIVE: `OtherExpenses` | NATIVE: "(g) Other expenses" | ABSENT | ABSENT — "Miscellaneous Expenses" = 0.0 on 9/9 while filed OtherExpenses is 22–3,054 cr; vendor carve-outs ("Selling and Distribution Expenses", "Electricity, Power & Fuel Cost", "Gen_AdminExpenses") are partial and of unknown origin | ABSENT | — | 2 (2) |
| `other_expenses_detail[n]` | Itemised other-expense lines | Q/H/FY | NATIVE: `OtherExpenses` + `DescriptionOfOtherExpenses` on `DetailsOfOtherExpensesAxis` (`OtherExpenses1Member`, X-Q2) | UNKNOWN (issuer-dependent; Apar prints none) | Annual S-sch "Manufacturing Cost %", "Other Cost %" — FORMULA UNPROVEN | UNKNOWN (see carve-outs above) | ABSENT | — | 1 (1) |
| `total_expenses` | Total expenses | Q/H/FY | NATIVE: `Expenses` | NATIVE: "6 Total expenses" | FORMULA MEASURED: "Expenses" + "Interest" + "Depreciation", 8/9 (THERMAX +21) | FORMULA MEASURED: "Operating Expenses" + "Interest" + "Depreciation and Amortization", 8/9 (THERMAX +20.96) | NATIVE [U]: `full_statement` "Total Expenses" | — | 5 (4) |
| `profit_before_exceptional_items_and_tax` | Profit before exceptional items and tax | Q/H/FY | NATIVE: `ProfitBeforeExceptionalItemsAndTax` | UNKNOWN (Apar has no exceptional line) | ABSENT | NATIVE [U]: `pl_c_d` "Profit Before Taxation & Exceptional Items" (annual); no quarterly row | ABSENT | — | 2 (1) |
| `exceptional_items_before_tax` | Exceptional items | Q/H/FY | NATIVE: `ExceptionalItemsBeforeTax` | UNKNOWN (issuer-dependent; Apar: none) | NATIVE [M]: S-sch "Other Income/Exceptional items" (SONACOMS −5.70 = filed; the only non-zero case) | NATIVE [M]: `qt_c` "Exceptional Items" (SONACOMS −5.699); `pl_c_d` "Exceptional Income / Expenses" [U] | ABSENT | — | 3 (3) |
| `exceptional_items_after_tax` | Exceptional items net of tax (vendor concept) | Q/FY | ABSENT | ABSENT (Apar) | NATIVE [U]: S-sch "Net Profit/Exceptional items AT" (SONACOMS −4) | UNKNOWN | ABSENT | — | 1 (0) |
| `profit_before_tax` | Profit before tax, **before** share of associates/JV (XBRL position) | Q/H/FY | NATIVE: `ProfitBeforeTax`. MEASURED as pre-associates: = `Income − Expenses + Exceptional` on X9; Apar X-Q2 340.56 = PDF line 7, not line 9 (340.53) | NATIVE: Apar "7 Profit before tax & share in net profit/(loss) of associates" | NATIVE [M]: "Profit before tax" 9/9 | NATIVE [M]: "Profit Before Tax" 9/9 | NATIVE [U]: `full_statement` "Profit Before Tax" and summary `operating_profit` (mislabel, U-doc); vs Screener tier-1 with CGPOWER exclusion (LB) | — | 5 (4) |
| `share_of_profit_associates_jv` | Share of profit/(loss) of associates and JVs (equity method) | Q/H/FY | NATIVE: `ShareOfProfitLossOfAssociatesAndJointVenturesAccountedForUsingEquityMethod` (sits **after tax** in the XBRL arithmetic); also `ShareOfProfitAndLossFromPartnershipFirmOrAssociationOfPersonsOrLimitedLiabilityPartnerships` (X-Q2, FourD) | NATIVE: Apar "8 Share in net profit/(loss) of associates" (**pre-tax** position) | NATIVE [M]: S-sch "Net Profit/Profit from Associates" (LAURUSLABS 2 vs 2.33; present in 1/10 quarters, 4/10 annual); HFCL folds it into Other income (inference, one stock) | ABSENT in `qt_*`; `pl_c_d` "Share of Associate" annual [U] | ABSENT | — | 4 (3) |
| `profit_before_tax_incl_associates` | PBT after share of associates (PDF position) | Q/H/FY | FORMULA MEASURED (1 filing): `profit_before_tax + share_of_profit_associates_jv` (340.56 − 0.03 = 340.53); `SegmentProfitBeforeTax` carries this value (segment section) | NATIVE: Apar "9 Profit before tax (7+8)" | ABSENT | ABSENT | UNKNOWN | — | 2 (2) |
| `current_tax` | Current tax | Q/H/FY | NATIVE: `CurrentTax`, **includes earlier-years tax** (X-Q4 FY25 284.65 = PDF 280.00 + 4.66; one filing) | NATIVE: "(a) Current tax" | ABSENT on page; RL screen field "Current Tax" UNKNOWN | NATIVE [U]: `pl_c_d` "Current Income Tax" (annual) | ABSENT | — | 3 (2) |
| `deferred_tax` | Deferred tax | Q/H/FY | NATIVE: `DeferredTax` | NATIVE: "(b) Deferred tax" | ABSENT | NATIVE [U]: `pl_c_d` "Deferred Tax" (annual) | ABSENT | — | 3 (2) |
| `tax_earlier_years` | Tax relating to earlier years | Q/H/FY | ABSENT (no element in any Apar instance; folded into `CurrentTax`) | NATIVE: "(c) Current tax in respect of earlier years" | ABSENT | ABSENT (`pl_c_d` "Other taxes" = fringe + wealth tax, not this) | ABSENT | — | 1 (1) |
| `tax_expense` | Total tax expense (continuing) | Q/H/FY | NATIVE: `TaxExpense` | FORMULA MEASURED: (a)+(b)+(c) (Apar Q2 89.13 − 0.30 = 88.83 = XBRL; no printed total) | ABSENT as value on page (see "Tax %", §2f); RL screen field "Tax" UNKNOWN | NATIVE [M]: `qt_*` "Tax" 9/9; `pl_c_s` "Tax" (formula `Profit_before_tax − Profit_after_tax`) / `pl_c_d` "Provision for Taxs" [U] | NATIVE [U]: `full_statement` "Tax" | — | 4 (3) |
| `profit_continuing_after_tax` | Net profit from continuing operations (before associates in XBRL layout) | Q/H/FY | NATIVE: `ProfitLossForPeriodFromContinuingOperations` | ABSENT (Apar line 11 is after associates) | ABSENT | NATIVE [M]: `qt_c` "Profit After Tax" **and "Net Profit"** = this, 9/9 to 0.01 cr. Equivalently PBT − Tax, because discontinued = 0 in the sample. | UNKNOWN (whether "Profit After Tax" is this or `profit_for_period`) | — | 2 (2) |
| `profit_discontinued_before_tax` | Profit from discontinued operations before tax | Q/H/FY | NATIVE: `ProfitLossFromDiscontinuedOperationsBeforeTax` | UNKNOWN (Apar none) | UNKNOWN | UNKNOWN | UNKNOWN | — | 1 (1) |
| `tax_discontinued` | Tax on discontinued operations | Q/H/FY | NATIVE: `TaxExpenseOfDiscontinuedOperations` | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | — | 1 (1) |
| `profit_discontinued_after_tax` | Profit from discontinued operations after tax | Q/H/FY | NATIVE: `ProfitLossFromDiscontinuedOperationsAfterTax` | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | — | 1 (1) |
| `regulatory_deferral_net_movement` | Net movement in regulatory deferral balances | Q/H/FY | NATIVE: `NetMovementInRegulatoryDeferralAccountBalancesRelatedToProfitOrLossAndTheRelatedDeferredTaxMovement` | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | — | 1 (1) |
| `profit_for_period` | Profit for the period (incl. associates and NCI) | Q/H/FY | NATIVE: `ProfitLossForPeriod` | NATIVE: Apar "11 Profit after tax (9-10)" (251.70 = XBRL) | NATIVE [M]: "Net Profit" 9/9; discriminates against owners on 4 stocks (3S) | `qt_c` "Net Profit" is **not** this (it is `profit_continuing_after_tax`; HFCL/LAURUSLABS/THERMAX/TITAN differ by associates). `pl_c_d` "Net Profit" (`Consolidated_NetProfit`) annual [U] | NATIVE [U]: summary `net_profit` / `full_statement` "Profit After Tax" (internally inconsistent on NETWEB and POLYCAB; LAURUSLABS exclusion vs Screener, LB) | — | 4 (3) |
| `profit_attributable_owners` | Profit attributable to owners of parent | Q/H/FY | NATIVE: `ProfitOrLossAttributableToOwnersOfParent` (quirks: CGPOWER −20.54 vs PL 237.85; MTARTECH 0/absent) | NATIVE: "(a) Owners of the Company" | NATIVE [M]: S-sch "Net Profit/Profit for EPS" 6/6 checked (HFCL 74/73.65, LAURUSLABS 92/92.30, POLYCAB 458/457.56, THERMAX 116/115.90, TITAN, SONACOMS 151/151.19) | UNKNOWN | ABSENT | — | 3 (3) |
| `profit_attributable_nci` | Profit attributable to non-controlling interests | Q/H/FY | NATIVE: `ProfitOrLossAttributableToNonControllingInterests` (X9, X-BSE, X-Q4; absent from X-Q2 where NCI is nil) | NATIVE: "(b) Non-controlling interest" | FORMULA MEASURED: S-sch "Minority share" = −NCI (sign-flipped), 4/4 non-zero cases | NATIVE [U]: `pl_c_d` "Minority Interest" (annual) | ABSENT | — | 4 (3) |
| `oci_not_reclassified_items` | OCI A(i): items not reclassified to P&L | Q/H/FY | NATIVE: `AmountOfItemThatWillNotBeReclassifiedToProfitAndLoss` (+ `DescriptionOf…` on `ItemsThatWillNotBeReclassifiedToProfitAndLossAxis`) | NATIVE: "(A)(i)" | ABSENT (no OCI row in any section, 10 stocks) | ABSENT (no OCI row) | ABSENT | — | 2 (2) |
| `oci_not_reclassified_tax` | OCI A(ii): tax on the above | Q/H/FY | NATIVE: `IncomeTaxRelatingToItemsThatWillNotBeReclassifiedToProfitOrLoss` (in-bse-fin spelling `…Itmes…`) | NATIVE: "(A)(ii)" | ABSENT | ABSENT | ABSENT | — | 2 (2) |
| `oci_reclassified_items` | OCI B(i): items reclassified to P&L | Q/H/FY | NATIVE: `AmountOfItemThatWillBeReclassifiedToProfitAndLoss` | NATIVE: "(B)(i)" | ABSENT | ABSENT | ABSENT | — | 2 (2) |
| `oci_reclassified_tax` | OCI B(ii): tax on the above | Q/H/FY | NATIVE: `IncomeTaxRelatingToItemsThatWillBeReclassifiedToProfitOrLoss` (in-bse-fin `…Itmes…`) | NATIVE: "(B)(ii)" | ABSENT | ABSENT | ABSENT | — | 2 (2) |
| `oci_net` | Other comprehensive income, net | Q/H/FY | NATIVE: `OtherComprehensiveIncomeNetOfTaxes` (and `OtherComprehensiveIncome`, same value in X-Q2) | NATIVE: "12 Other comprehensive incomes" | ABSENT | ABSENT | ABSENT | — | 2 (2) |
| `total_comprehensive_income` | Total comprehensive income | Q/H/FY | NATIVE: `ComprehensiveIncomeForThePeriod` | NATIVE: "13 Total comprehensive income" | ABSENT | ABSENT | ABSENT | — | 2 (2) |
| `tci_attributable_owners` | TCI attributable to owners | Q/H/FY | NATIVE (suspect): `ComprehensiveIncomeForThePeriodAttributableToOwnersOfParent`. X-Q2 shows 22.95 (Q) and 30.80 (H1), which is the PDF **OCI**-owners figure, not TCI-owners (274.65) | NATIVE: "Total comprehensive incomes attributable to (a) Owners" | ABSENT | ABSENT | ABSENT | — | 2 (1) |
| `tci_attributable_nci` | TCI attributable to NCI | Q/H/FY | NATIVE: `ComprehensiveIncomeForThePeriodAttributableToOwnersOfParentNonControllingInterests` (X-BSE, X-Q4) | NATIVE | ABSENT | ABSENT | ABSENT | — | 2 (2) |
| `oci_attributable_owners` | OCI attributable to owners | Q/H/FY | ABSENT as a distinct element (but see the misuse above) | NATIVE | ABSENT | ABSENT | ABSENT | — | 1 (1) |
| `oci_attributable_nci` | OCI attributable to NCI | Q/H/FY | ABSENT | NATIVE | ABSENT | ABSENT | ABSENT | — | 1 (1) |
| `paid_up_equity_capital` | Paid-up equity share capital | Q/H/FY | NATIVE: `PaidUpValueOfEquityShareCapital` (every filing); `EquityShareCapital` (BS) | NATIVE: "14 Paid up share Capital" | NATIVE [U]: BS "Equity Capital" (annual); RL "Equity Capital latest quarter" (screen field) | NATIVE [U]: BS "Share Capital" (annual) | NATIVE [U]: BS `full_statement` "Equity Capital" (annual) | — | 5 (2) |
| `face_value_per_share` | Face value per share | Q/H/FY | NATIVE: `FaceValueOfEquityShareCapital` (X-Q2 `OneD` = 10, `FourD` = 0, a quirk) | NATIVE: inside the line-14 label "(Face value of ₹10 each)" | NATIVE [U]: top-ratios "Face Value" (current snapshot only, S-page) | UNKNOWN | UNKNOWN | — | 3 (2) |
| `reserves_excl_revaluation` | Reserves excluding revaluation reserve | FY | NATIVE: `ReserveExcludingRevaluationReserves` (X-Q4 only) | NATIVE: "15 Reserves excluding revaluation reserve" (FY column only) | NATIVE [U]: BS "Reserves" (equivalence unproven) | NATIVE [U]: BS "Reserves" | ABSENT | — | 4 (2) |
| `eps_basic` | Basic EPS (continuing + discontinued) | Q/H/FY | NATIVE: `BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations` | NATIVE: "16 EPS — Basic" | FORMULA UNPROVEN: row "EPS in Rs" agrees with filed basic 6/9 (ETERNAL 14.3 %, THERMAX 5.4 %, TITAN 0.08 % off, 3S); S-sch "Profit for EPS" suggests owners profit ÷ a vendor share count | FORMULA UNPROVEN: `qt_*` "Quarterly Ratios/EPS" (`adj_eps_abs`) agrees to 2 dp 8/9 (TITAN 11.764 vs 11.80); `fr_c` "Adjusted EPS" annual. MAP says "No Tijori EPS row is parsed today", yet the row exists in T. | NATIVE [U]: `full_statement` "EPS - Basic" (annual) | — | 3 (2) |
| `eps_basic_continuing` | Basic EPS, continuing operations | Q/H/FY | NATIVE: `BasicEarningsLossPerShareFromContinuingOperations` | UNKNOWN (Apar prints one Basic) | ABSENT | ABSENT | ABSENT | — | 1 (1) |
| `eps_basic_discontinued` | Basic EPS, discontinued operations | Q/H/FY | NATIVE: `BasicEarningsLossPerShareFromDiscontinuedOperations` | UNKNOWN | ABSENT | ABSENT | ABSENT | — | 1 (1) |
| `eps_diluted` | Diluted EPS (continuing + discontinued) | Q/H/FY | NATIVE: `DilutedEarningsLossPerShareFromContinuingAndDiscontinuedOperations` | NATIVE: "Diluted" | ABSENT | ABSENT | NATIVE [U]: `full_statement` "EPS - Diluted" | — | 3 (2) |
| `eps_diluted_continuing` | Diluted EPS, continuing | Q/H/FY | NATIVE: `DilutedEarningsLossPerShareFromContinuingOperations` | UNKNOWN | ABSENT | ABSENT | ABSENT | — | 1 (1) |
| `eps_diluted_discontinued` | Diluted EPS, discontinued | Q/H/FY | NATIVE: `DilutedEarningsLossPerShareFromDiscontinuedOperations` | UNKNOWN | ABSENT | ABSENT | ABSENT | — | 1 (1) |
| `shares_outstanding` | Number of equity shares | Q/FY | ABSENT (no count element in instances); FORMULA UNPROVEN `paid_up_equity_capital ÷ face_value_per_share` | FORMULA UNPROVEN (same) | UNKNOWN: RL screen field "Number of equity shares" | NATIVE [U]: `pl_c_*` "Number of shares(Crs)" (annual) | UNKNOWN | UNVERIFIED-general-knowledge: SHP states total shares | 1 (0) |

Filing metadata rows. These are needed as comparison keys, and only XBRL carries them as data.
XBRL-native elements:

- `DateOfStartOfReportingPeriod` / `DateOfEndOfReportingPeriod`
- `NatureOfReportStandaloneConsolidated`
- `WhetherResultsAreAuditedOrUnaudited`
- `LevelOfRounding` (in-bse-fin: `LevelOfRoundingUsedInFinancialStatements`)
- `DescriptionOfPresentationCurrency`
- `ReportingQuarter`
- `TypeOfReportingPeriod`
- `IsCompanyReportingMultisegmentOrSingleSegment`
- `TypeOfCashFlowStatement`
- `DateOfBoardMeetingWhenFinancialResultsWereApproved`
- `Symbol` / `ISIN` / `ScripCode`

The PDF prints the same facts as headings. The vendors carry none of them per period, except basis
via URL or table key.

### 2b. Balance sheet (point-in-time; filings: half-year end and FY end; vendors: FY end only)

The XBRL column is Apar X-Q2 `OneI` (30-Sep-25) unless noted. The PDF column is Apar p6. No vendor
BS row has been measured against a filing; the only BS measurements in the repo are vendor↔vendor
(LB, TITAN etc.).

| canonical_id | description | periodicity | XBRL | PDF | Screener | Tijori | Upstox | SHP | cov |
|---|---|---|---|---|---|---|---|---|---|
| `ppe` | Property, plant and equipment | H/FY | NATIVE: `PropertyPlantAndEquipment` (1,441.55 = PDF) | NATIVE: "Property, plant and equipments" | FORMULA UNPROVEN: "Fixed Assets" (net block incl. intangibles; S-sch has "Gross Block", "Accumulated Depreciation", "Intangible Assets", asset classes) | FORMULA UNPROVEN: `bs_c_*` "Net Block" (= "Gross Block" − "Less: Accumulated Depreciation" − "Less: Impairment") | ABSENT | — | 2 (2) |
| `right_of_use_assets` | Right-of-use assets | H/FY | ABSENT — folded by filer into `OtherIntangibleAssets` (108.46 = PDF ROU 106.73 + intangibles 1.73) | NATIVE: "Right to use assets" | ABSENT | ABSENT | ABSENT | — | 1 (1) |
| `cwip` | Capital work-in-progress | H/FY | NATIVE: `CapitalWorkInProgress` | NATIVE | NATIVE [U]: "CWIP" | NATIVE [U]: "Capital Work in Progress" | ABSENT | — | 4 (2) |
| `goodwill` | Goodwill | H/FY | NATIVE: `Goodwill` | UNKNOWN (Apar prints none) | ABSENT (not a separate row) | ABSENT | ABSENT | — | 1 (1) |
| `other_intangible_assets` | Other intangible assets | H/FY | NATIVE: `OtherIntangibleAssets` (see ROU folding) | NATIVE | NATIVE [U]: S-sch "Fixed Assets/Intangible Assets" | ABSENT | ABSENT | — | 3 (2) |
| `intangibles_under_development` | Intangible assets under development | H/FY | NATIVE: `IntangibleAssetsUnderDevelopment` | NATIVE | ABSENT | NATIVE [U]: `bs_c_s` "Intangible Assets Under Development" | ABSENT | — | 3 (2) |
| `investment_property` | Investment property | H/FY | NATIVE: `InvestmentProperty` (X-Q4, X-BSE) | UNKNOWN | ABSENT | ABSENT | ABSENT | — | 1 (1) |
| `biological_assets` | Biological assets other than bearer plants | H/FY | NATIVE: `BiologicalAssetsOtherThanBearerPlants` (X-Q4) | UNKNOWN | ABSENT | ABSENT | ABSENT | — | 1 (1) |
| `investments_equity_method` | Investments accounted for using equity method | H/FY | NATIVE: `InvestmentsAccountedForUsingEquityMethod` (X-Q4) | UNKNOWN (Apar prints "Investments in subsidiaries & associates") | ABSENT | ABSENT | ABSENT | — | 1 (1) |
| `noncurrent_investments` | Non-current investments | H/FY | NATIVE: `NoncurrentInvestments` | NATIVE: "Investments in subsidiaries & associates" (Apar) | FORMULA UNPROVEN: "Investments" (current + non-current?) | NATIVE [U]: "Long Term Investments" | ABSENT | — | 3 (2) |
| `trade_receivables_noncurrent` | Trade receivables, non-current | H/FY | NATIVE: `TradeReceivablesNoncurrent` | NATIVE | ABSENT | ABSENT | ABSENT | — | 2 (2) |
| `loans_noncurrent` | Loans, non-current | H/FY | NATIVE: `LoansNoncurrent` | NATIVE | FORMULA UNPROVEN: S-sch "Other Assets/Loans n Advances" | NATIVE [U]: `bs_c_d` "Long Term Loans & Advances" | ABSENT | — | 3 (2) |
| `other_noncurrent_financial_assets` | Other non-current financial assets | H/FY | NATIVE: `OtherNoncurrentFinancialAssets` (15.04 = PDF derivative 2.49 + other 12.55, folded) | NATIVE: "Other financial assets" (+ "Derivative financial assets") | ABSENT | ABSENT | ABSENT | — | 2 (2) |
| `noncurrent_financial_assets` | Non-current financial assets (subtotal) | H/FY | NATIVE: `NoncurrentFinancialAssets` | ABSENT (no printed subtotal, Apar) | ABSENT | ABSENT | ABSENT | — | 1 (1) |
| `deferred_tax_assets_net` | Deferred tax assets (net) | H/FY | NATIVE: `DeferredTaxAssetsNet` (X-Q4, X-BSE) | UNKNOWN (Apar none at H1) | ABSENT | NATIVE [U]: `bs_c_d` "Deferred Tax Assets/Liabilities" (net, single signed row) | ABSENT | — | 2 (1) |
| `noncurrent_tax_assets` | Non-current tax assets (net) | H/FY | ABSENT — folded into `OtherNoncurrentAssets` (235.21 = 191.99 + 43.22) | NATIVE: "Noncurrent tax assets (net)" | ABSENT | ABSENT | ABSENT | — | 1 (1) |
| `other_noncurrent_assets` | Other non-current assets | H/FY | NATIVE: `OtherNoncurrentAssets` | NATIVE | ABSENT | NATIVE [U]: `bs_c_d` "Other Non Current Assets" | ABSENT | — | 3 (2) |
| `noncurrent_assets_total` | Total non-current assets | H/FY | NATIVE: `NoncurrentAssets` (2,265.23 = PDF) | NATIVE | ABSENT | NATIVE [U]: "Non Current Assets" (formula `Total_Nonassets − Net_Def_Tax_Nf`) | NATIVE [U]: `full_statement` "Non-Current Assets" | — | 4 (2) |
| `inventories` | Inventories | H/FY | NATIVE: `Inventories` | NATIVE | NATIVE [U]: S-sch "Other Assets/Inventories" | NATIVE [U]: "Inventory" | ABSENT | — | 4 (2) |
| `current_investments` | Current investments | H/FY | NATIVE: `CurrentInvestments` | NATIVE | ABSENT (inside "Investments"?) | NATIVE [U]: "Short Term Investments" | ABSENT | — | 3 (2) |
| `trade_receivables_current` | Trade receivables, current | H/FY | NATIVE: `TradeReceivablesCurrent` | NATIVE | NATIVE [U]: S-sch "Other Assets/Trade receivables" | NATIVE [U]: "Accounts Receivable" | ABSENT | — | 4 (2) |
| `cash_and_cash_equivalents` | Cash and cash equivalents | H/FY | NATIVE: `CashAndCashEquivalents` | NATIVE | FORMULA UNPROVEN: S-sch "Other Assets/Cash Equivalents" (may include bank balances) | FORMULA UNPROVEN: "Cash & Bank Balances" (cash + other bank balances?) | ABSENT | — | 2 (2) |
| `other_bank_balances` | Bank balances other than cash equivalents | H/FY | NATIVE: `BankBalanceOtherThanCashAndCashEquivalents` | NATIVE: "Bank balances other than above" | UNKNOWN | UNKNOWN (see above) | ABSENT | — | 2 (2) |
| `loans_current` | Loans, current | H/FY | NATIVE: `LoansCurrent` | NATIVE | UNKNOWN (inside "Loans n Advances"?) | NATIVE [U]: `bs_c_d` "Short Term Loans and Advances" | ABSENT | — | 3 (2) |
| `other_current_financial_assets` | Other current financial assets | H/FY | NATIVE: `OtherCurrentFinancialAssets` (154.78 = derivatives 79.69 + other 75.09, folded) | NATIVE (+ derivatives line) | ABSENT | ABSENT | ABSENT | — | 2 (2) |
| `current_financial_assets` | Current financial assets (subtotal) | H/FY | NATIVE: `CurrentFinancialAssets` | ABSENT (no printed subtotal) | ABSENT | ABSENT | ABSENT | — | 1 (1) |
| `current_tax_assets` | Current tax assets | H/FY | NATIVE: `CurrentTaxAssets` (X-Q4, X-BSE) | UNKNOWN | ABSENT | ABSENT | ABSENT | — | 1 (1) |
| `other_current_assets` | Other current assets | H/FY | NATIVE: `OtherCurrentAssets` | NATIVE | FORMULA UNPROVEN: S-sch "Other Assets/Other asset items" | NATIVE [U]: `bs_c_d` "Other Current Assets" | ABSENT | — | 3 (2) |
| `assets_held_for_sale` | Non-current assets held for sale | H/FY | NATIVE: `NoncurrentAssetsClassifiedAsHeldForSale` (X-Q4) | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | — | 1 (1) |
| `regulatory_deferral_debit` | Regulatory deferral debit balances | H/FY | NATIVE: `RegulatoryDeferralAccountDebitBalancesAndRelatedDeferredTaxAssets` (X-Q4) | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | — | 1 (1) |
| `current_assets_total` | Total current assets | H/FY | NATIVE: `CurrentAssets` | NATIVE | ABSENT | NATIVE [U]: "Current Assets" | NATIVE [U]: `full_statement` "Current Assets" | — | 4 (2) |
| `total_assets` | Total assets | H/FY | NATIVE: `Assets` (11,312.53 = PDF) | NATIVE: "TOTAL ASSETS" | NATIVE [U]: "Total Assets"; vs Upstox `total_asset` tier-2, 17/40 anomalies, median 0.055 % (LB) | NATIVE [U]: "Assets" (`Total_Applications_Nf`) | NATIVE [U]: summary `total_asset`; `full_statement` "Total Assets" | — | 5 (2) |
| `equity_share_capital` | Equity share capital | H/FY | NATIVE: `EquityShareCapital` | NATIVE | NATIVE [U]: "Equity Capital" | NATIVE [U]: "Share Capital" | NATIVE [U]: `full_statement` "Equity Capital" | — | 5 (2) |
| `other_equity` | Other equity | H/FY | NATIVE: `OtherEquity` | NATIVE | NATIVE [U]: "Reserves" | NATIVE [U]: "Reserves" | ABSENT | — | 4 (2) |
| `equity_attributable_owners` | Equity attributable to owners | H/FY | NATIVE: `EquityAttributableToOwnersOfParent` | NATIVE: "Total equity" (Apar, no NCI) | FORMULA UNPROVEN: "Equity Capital" + "Reserves" | NATIVE [U]: "Shareholders Funds" | ABSENT | — | 3 (2) |
| `non_controlling_interest_bs` | Non-controlling interest (BS) | H/FY | NATIVE: `NonControllingInterest` (X-Q4, X-BSE) | UNKNOWN (Apar nil) | NATIVE [U]: S-sch "Other Liabilities/Non controlling int" (carried **inside liabilities**, 8/10 stocks) | UNKNOWN | ABSENT | — | 2 (1) |
| `total_equity` | Total equity | H/FY | NATIVE: `Equity` | NATIVE: "Total equity" | ABSENT (NCI sits under Other Liabilities) | ABSENT | ABSENT | — | 2 (2) |
| `borrowings_noncurrent` | Non-current borrowings | H/FY | NATIVE: `BorrowingsNoncurrent` | NATIVE | NATIVE [U]: S-sch "Borrowings/Long term Borrowings" | FORMULA UNPROVEN: "Secured Loans" + "Unsecured Loans" (non-current block) | ABSENT | — | 3 (2) |
| `lease_liabilities_noncurrent` | Lease liabilities, non-current | H/FY | ABSENT — folded into `OtherNoncurrentFinancialLiabilities` (111.15 = lease 108.08 + other 3.07) | NATIVE | FORMULA UNPROVEN: S-sch "Borrowings/Lease Liabilities" (current + non-current?) | ABSENT | ABSENT | — | 1 (1) |
| `other_noncurrent_financial_liabilities` | Other non-current financial liabilities | H/FY | NATIVE: `OtherNoncurrentFinancialLiabilities` (lease folded in) | NATIVE (+ derivatives line) | ABSENT | NATIVE [U]: `bs_c_d` "Other Long Term Liabilities" | ABSENT | — | 3 (2) |
| `noncurrent_financial_liabilities` | Non-current financial liabilities (subtotal) | H/FY | NATIVE: `NoncurrentFinancialLiabilities` | ABSENT | ABSENT | ABSENT | ABSENT | — | 1 (1) |
| `provisions_noncurrent` | Non-current provisions | H/FY | NATIVE: `ProvisionsNoncurrent` | NATIVE | ABSENT | NATIVE [U]: "Long Term Provisions" | ABSENT | — | 3 (2) |
| `deferred_tax_liabilities_net` | Deferred tax liabilities (net) | H/FY | NATIVE: `DeferredTaxLiabilitiesNet` | NATIVE | ABSENT | see `deferred_tax_assets_net` (single signed row) | ABSENT | — | 2 (2) |
| `other_noncurrent_liabilities` | Other non-current liabilities | H/FY | NATIVE: `OtherNoncurrentLiabilities` (X-Q4) | UNKNOWN | ABSENT | ABSENT | ABSENT | — | 1 (1) |
| `deferred_government_grants` | Deferred government grants (current / non-current) | H/FY | NATIVE: `DeferredGovernmentGrantsCurrent` / `…Noncurrent` (X-Q4) | UNKNOWN | ABSENT | ABSENT | ABSENT | — | 1 (1) |
| `noncurrent_liabilities_total` | Total non-current liabilities | H/FY | NATIVE: `NoncurrentLiabilities` | NATIVE | ABSENT | NATIVE [U]: "Non Current Liabilities" | NATIVE [U]: `full_statement` "Non-Current Liabilities" | — | 4 (2) |
| `borrowings_current` | Current borrowings | H/FY | NATIVE: `BorrowingsCurrent` | NATIVE | NATIVE [U]: S-sch "Borrowings/Short term Borrowings" | NATIVE [U]: "Short Term Loans" | ABSENT | — | 4 (2) |
| `borrowings_total` | Total borrowings (vendor aggregate) | H/FY | FORMULA UNPROVEN: `borrowings_noncurrent + borrowings_current` (± lease) | FORMULA UNPROVEN | NATIVE [U]: "Borrowings" (S-sch sums reconcile to the page row: Long term + Short term + Lease Liabilities + Other Borrowings + Preference Capital [3/10]) | NATIVE [U]: `fr_c` "Total Debt (Crs)" | ABSENT | — | 2 (0) |
| `lease_liabilities_current` | Lease liabilities, current | H/FY | ABSENT — folded into `OtherCurrentFinancialLiabilities` | NATIVE | see `lease_liabilities_noncurrent` | ABSENT | ABSENT | — | 1 (1) |
| `trade_payables_msme` | Trade payables — micro and small enterprises | H/FY | NATIVE: `TotalOutstandingDuesOfMicroEnterpriseAndSmallEnterpriseCurrent` (+ `…Noncurrent`, X-Q4) | NATIVE: "a) …micro and small enterprises" | ABSENT | ABSENT | ABSENT | — | 2 (2) |
| `trade_payables_others` | Trade payables — other than MSE | H/FY | NATIVE: `TotalOutstandingDuesOfCreditorsOtherThanMicroEnterpriseAndSmallEnterpriseCurrent` | NATIVE: "b) …" | ABSENT | ABSENT | ABSENT | — | 2 (2) |
| `trade_payables_current` | Trade payables, current (total) | H/FY | NATIVE: `TradePayablesCurrent` (5,293.82 = a + b) | FORMULA MEASURED: a + b (no printed total) | NATIVE [U]: S-sch "Other Liabilities/Trade Payables" | NATIVE [U]: "Accounts Payable" | ABSENT | — | 4 (2) |
| `trade_payables_noncurrent` | Trade payables, non-current | H/FY | NATIVE: `TradePayablesNoncurrent` (X-Q4, X-BSE) | UNKNOWN | ABSENT | ABSENT | ABSENT | — | 1 (1) |
| `other_current_financial_liabilities` | Other current financial liabilities | H/FY | NATIVE: `OtherCurrentFinancialLiabilities` (137.77 = lease 4.56 + derivatives 25.08 + other 108.13) | NATIVE (3 lines) | ABSENT | ABSENT | ABSENT | — | 2 (2) |
| `current_financial_liabilities` | Current financial liabilities (subtotal) | H/FY | NATIVE: `CurrentFinancialLiabilities` | ABSENT | ABSENT | ABSENT | ABSENT | — | 1 (1) |
| `other_current_liabilities` | Other current liabilities | H/FY | NATIVE: `OtherCurrentLiabilities` | NATIVE | FORMULA UNPROVEN: S-sch "Advance from Customers" + "Other liability items" | NATIVE [U]: `bs_c_d` "Other Current Liabilities" | ABSENT | — | 3 (2) |
| `provisions_current` | Current provisions | H/FY | NATIVE: `ProvisionsCurrent` | NATIVE | ABSENT | NATIVE [U]: "Short Term Provisions" | ABSENT | — | 3 (2) |
| `current_tax_liabilities` | Current tax liabilities (net) | H/FY | NATIVE: `CurrentTaxLiabilities` | NATIVE | ABSENT | ABSENT | ABSENT | — | 2 (2) |
| `liabilities_held_for_sale` | Liabilities of disposal groups held for sale | H/FY | NATIVE: `LiabilitiesDirectlyAssociatedWithAssetsInDisposalGroupClassifiedAsHeldForSale` (X-Q4) | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | — | 1 (1) |
| `regulatory_deferral_credit` | Regulatory deferral credit balances | H/FY | NATIVE: `RegulatoryDeferralAccountCreditBalancesAndRelatedDeferredTaxLiability` (X-Q4) | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | — | 1 (1) |
| `current_liabilities_total` | Total current liabilities | H/FY | NATIVE: `CurrentLiabilities` | NATIVE | ABSENT | NATIVE [U]: "Current Liabilities" | NATIVE [U]: `full_statement` "Current Liabilities" | — | 4 (2) |
| `total_liabilities` | Total liabilities (excluding equity) | H/FY | NATIVE: `Liabilities` (6,460.02 = PDF) | NATIVE: "Total liabilities" | FORMULA MEASURED (vs Upstox, not filing): "Borrowings" + "Other Liabilities", TITAN 4 periods within 0–3 cr bar Mar-23 (LB). **Not** Screener "Total Liabilities". | UNKNOWN (no row) | NATIVE [U]: summary `total_liability` (no `full_statement` particular, U-doc §4) | — | 3 (2) |
| `total_equity_and_liabilities` | Total equity and liabilities | H/FY | NATIVE: `EquityAndLiabilities` | NATIVE | NATIVE [M-internal]: "Total Liabilities" = "Total Assets" on every period checked (LB) | NATIVE [U]: "Liabilities" (`Total_Sounces_Funds_Nf`) | NATIVE [U]: `full_statement` "Total Equity & Liabilities" | — | 5 (2) |
| `net_current_assets` | Net current assets (vendor) | FY | FORMULA: `current_assets_total − current_liabilities_total` | FORMULA | ABSENT (RL "Working capital" screen field, UNKNOWN definition) | ABSENT | NATIVE [U]: `full_statement` "Net Current Asset" | — | 1 (0) |
| `gross_block` / `accumulated_depreciation` | Gross block, accumulated depreciation | FY | ABSENT (not in results XBRL) | ABSENT (Apar) | NATIVE [U]: S-sch "Fixed Assets/Gross Block", "…/Accumulated Depreciation" | NATIVE [U]: `bs_c_d` "Gross Block", "Less: Accumulated Depreciation" | ABSENT | — | 2 (0) |

### 2c. Cash flow (filings: H1 and FY, indirect method; vendors: FY)

The XBRL column is Apar X-Q2 `FourD` (H1). The PDF column is Apar p7, an issuer-condensed
presentation. Vendor cash-flow rows have **never** been measured against a filing. Screener↔Upstox
CF is `NOT_COMPARABLE` (LB), and NETWEB CFO differs 4.6× between the two.

| canonical_id | description | periodicity | XBRL | PDF | Screener | Tijori | Upstox | SHP | cov |
|---|---|---|---|---|---|---|---|---|---|
| `cf_profit_before_tax` | Starting profit (PBT) | H/FY | ABSENT as a CF element (the start is `AdjustmentsForReconcileProfitLoss` relative to P&L) | NATIVE: "Profit before tax & share in net profit/(loss) of associates" | ABSENT | NATIVE [U]: `cf_c` "Profit Before Tax" | NATIVE [U]: `full_statement` "Profit before tax" | — | 3 (1) |
| `cf_adj_depreciation` | Adjustment: D&A | H/FY | NATIVE: `AdjustmentsForDepreciationAndAmortisationExpense` | NATIVE | ABSENT | ABSENT (only "Adjustments" total) | ABSENT | — | 2 (2) |
| `cf_adj_finance_costs` | Adjustment: finance costs | H/FY | NATIVE: `AdjustmentsForFinanceCosts` | NATIVE: "Interest costs" | ABSENT | ABSENT | ABSENT | — | 2 (2) |
| `cf_adj_interest_income` | Adjustment: interest income | H/FY | NATIVE: `AdjustmentsForInterestIncome` (sign stored positive) | NATIVE | ABSENT | ABSENT | ABSENT | — | 2 (2) |
| `cf_adj_dividend_income` | Adjustment: dividend income | H/FY | NATIVE: `AdjustmentsForDividendIncome` | UNKNOWN | ABSENT | ABSENT | ABSENT | — | 1 (1) |
| `cf_adj_unrealised_fx` | Adjustment: unrealised FX | H/FY | NATIVE: `AdjustmentsForUnrealisedForeignExchangeLossesGains` | NATIVE | ABSENT | ABSENT | ABSENT | — | 2 (2) |
| `cf_adj_share_based_payments` | Adjustment: share-based payments | H/FY | NATIVE: `AdjustmentsForSharebasedPayments` | NATIVE | ABSENT | ABSENT | ABSENT | — | 2 (2) |
| `cf_adj_impairment` | Adjustment: impairment | H/FY | NATIVE: `AdjustmentsForImpairmentLossReversalOfImpairmentLossRecognisedInProfitOrLoss` | UNKNOWN | ABSENT | ABSENT | ABSENT | — | 1 (1) |
| `cf_adj_fair_value` | Adjustment: fair-value gains/losses | H/FY | NATIVE: `AdjustmentsForFairValueGainsLosses` | UNKNOWN ("Profit on sale of investments" is similar, not proven) | ABSENT | ABSENT | ABSENT | — | 1 (1) |
| `cf_adj_provisions` | Adjustment: provisions (current/non-current) | H/FY | NATIVE: `AdjustmentsForProvisionsCurrent` / `…Noncurrent` (20.09 = PDF "Provision for doubtful debts") | NATIVE | ABSENT | ABSENT | ABSENT | — | 2 (2) |
| `cf_adj_associates_undistributed` | Adjustment: undistributed profits of associates | H/FY | NATIVE: `AdjustmentsForUndistributedProfitsOfAssociates` | UNKNOWN | ABSENT | ABSENT | ABSENT | — | 1 (1) |
| `cf_adj_other_noncash` | Other non-cash adjustments (3 residual elements) | H/FY | NATIVE: `OtherAdjustmentsForNoncashItems`, `OtherAdjustmentsForWhichCashEffectsAreInvestingOrFinancingCashFlow`, `OtherAdjustmentsToReconcileProfitLoss` | issuer-specific lines | ABSENT | ABSENT | ABSENT | — | 2 (2) |
| `cf_wc_trade_receivables` | WC change: trade receivables (current/non-current) | H/FY | NATIVE: `AdjustmentsForDecreaseIncreaseInTradeReceivablesCurrent` / `…Noncurrent` | NATIVE: "trade and other receivables" | NATIVE [U]: S-sch "Cash from Operating Activity/Receivables" | ABSENT (only "Working Capital Changes") | ABSENT | — | 3 (2) |
| `cf_wc_inventories` | WC change: inventories | H/FY | NATIVE: `AdjustmentsForDecreaseIncreaseInInventories` | NATIVE | NATIVE [U]: S-sch "…/Inventory" | ABSENT | ABSENT | — | 3 (2) |
| `cf_wc_trade_payables` | WC change: trade payables | H/FY | NATIVE: `AdjustmentsForIncreaseDecreaseInTradePayablesCurrent` / `…Noncurrent` | NATIVE | NATIVE [U]: S-sch "…/Payables" | ABSENT | ABSENT | — | 3 (2) |
| `cf_wc_other_assets_liabilities` | WC change: other assets, liabilities, financial assets/liabilities, bank balances (≈10 elements) | H/FY | NATIVE: `AdjustmentsForDecreaseIncreaseInOther{Current,Noncurrent}Assets`, `AdjustmentsForIncreaseDecreaseInOther{Current,Noncurrent}Liabilities`, `AdjustmentsForOtherFinancial{Assets,Liabilities}{Current,Noncurrent}`, `AdjustmentsForOtherBankBalances` | partially (issuer-condensed) | NATIVE [U]: S-sch "Loans Advances", "Other WC items" | ABSENT | ABSENT | — | 3 (2) |
| `cf_wc_total` | Total working-capital change | H/FY | FORMULA UNPROVEN (sum of the `cf_wc_*` elements; no total element) | FORMULA | NATIVE [U]: S-sch "Working capital changes" | NATIVE [U]: "Working Capital Changes" | NATIVE [U]: `full_statement` "Change in WC" (and "Change in Assets", "Change in Liabilities") | — | 3 (0) |
| `cf_adjustments_total` | Total adjustments to reconcile profit | H/FY | NATIVE: `AdjustmentsForReconcileProfitLoss` (−344.41, includes WC) | ABSENT | ABSENT | NATIVE [U]: "Adjustments" (definition may exclude WC) | ABSENT | — | 2 (1) |
| `cf_cash_generated_from_operations` | Cash generated from operations (before tax) | H/FY | NATIVE: `CashFlowsFromUsedInOperations` | ABSENT (Apar prints no subtotal) | NATIVE [U]: S-sch "Profit from operations" (meaning unproven) | NATIVE [U]: "OCF Before Working Capital" (meaning differs: pre-WC) | NATIVE [U]: `full_statement` "Income before WC changes" (pre-WC) | — | 4 (1) |
| `cf_interest_dividend_operating` | Interest paid/received and dividends received classified as operating | H/FY | NATIVE: `InterestPaidClassifiedAsOperatingActivities`, `InterestReceivedClassifiedAsOperatingActivities`, `DividendsReceivedClassifiedAsOperatingActivities` | UNKNOWN | ABSENT | ABSENT | ABSENT | — | 1 (1) |
| `cf_income_taxes_paid` | Income taxes paid (operating) | H/FY | NATIVE: `IncomeTaxesPaidRefundClassifiedAsOperatingActivities` (positive = outflow); also the `…Investing` / `…Financing` variants | NATIVE: "Tax paid" | NATIVE [U]: S-sch "Direct taxes" | NATIVE [U]: "Taxes Paid" | ABSENT | — | 4 (2) |
| `cf_other_operating` | Other operating inflows/outflows | H/FY | NATIVE: `OtherInflowsOutflowsOfCashClassifiedAsOperatingActivities` | UNKNOWN | NATIVE [U]: S-sch "Exceptional CF items", "Other operating items", "Operating borrowings" (2/10, 2/10, 1/10) | ABSENT | ABSENT | — | 2 (1) |
| `cfo` | Net cash from operating activities | H/FY | NATIVE: `CashFlowsFromUsedInOperatingActivities` (168.84 vs PDF 168.86) | NATIVE | NATIVE [U]: "Cash from Operating Activity" | NATIVE [U]: "Cash from Operating Activity" | NATIVE [U]: summary `operating`; `full_statement` "Cash flow from Operations" | — | 5 (2) |
| `cf_capex_ppe` | Purchase of PPE | H/FY | NATIVE: `PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities` (positive = outflow) | NATIVE: "Acquisition of property, plant and equipment" | NATIVE [U]: S-sch "Fixed assets purchased" | NATIVE [U]: "Fixed Assets Purchased" | ABSENT | — | 4 (2) |
| `cf_sale_ppe` | Proceeds from sale of PPE | H/FY | NATIVE: `ProceedsFromSalesOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities` | NATIVE | NATIVE [U]: "Fixed assets sold" | NATIVE [U]: "Fixed Assets Sold" | ABSENT | — | 4 (2) |
| `cf_intangibles_other_lt_assets` | Purchase/sale of intangibles, IAUD, goodwill, investment property, biological, other LT assets (≈14 elements) | H/FY | NATIVE: `PurchaseOf…`/`ProceedsFromSalesOf…` for IntangibleAssets, IntangibleAssetsUnderDevelopment, Goodwill, InvestmentProperty, BiologicalAssets…, OtherLongTermAssets | UNKNOWN | ABSENT | ABSENT | ABSENT | — | 1 (1) |
| `cf_investments_purchase_sale` | Purchase/sale of investments (equity/debt instruments, JVs) | H/FY | NATIVE: `OtherCashPaymentsToAcquireEquityOrDebtInstruments…`, `OtherCashReceiptsFromSalesOfEquityOrDebtInstruments…`, `…InterestsInJointVentures…` (Apar mis-tags net investments sale 198.26 as `ProceedsFromSalesOfInvestmentPropertyClassifiedAsInvestingActivities`) | NATIVE: "Sale/(purchase) of investments – net" | NATIVE [U]: S-sch "Investments purchased", "Investments sold" | NATIVE [U]: "Investment Purchased", "Investment Sold" | ABSENT | — | 4 (2) |
| `cf_subsidiaries_acquisition_disposal` | Obtaining/losing control of subsidiaries | H/FY | NATIVE: `CashFlowsUsedInObtainingControlOfSubsidiaries…`, `CashFlowsFromLosingControlOfSubsidiaries…` | UNKNOWN | NATIVE [U]: S-sch "Acquisition of companies", "Invest in subsidiaries", "Investment in group cos" | NATIVE [U]: "Subsidiary Investments" | ABSENT | — | 3 (1) |
| `cf_loans_advances_investing` | Loans and advances made/repaid (investing) | H/FY | NATIVE: `CashAdvancesAndLoansMadeToOtherParties…`, `CashReceiptsFromRepaymentOfAdvancesAndLoans…` | UNKNOWN | NATIVE [U]: S-sch "Inter corporate deposits" (1/10) | ABSENT | ABSENT | — | 2 (1) |
| `cf_derivative_contracts_investing` | Futures/forwards/options/swaps (investing) | H/FY | NATIVE: `CashPaymentsForFuture…`, `CashReceiptsFromFuture…` | UNKNOWN | ABSENT | ABSENT | ABSENT | — | 1 (1) |
| `cf_interest_received_investing` | Interest received (investing) | H/FY | NATIVE: `InterestReceivedClassifiedAsInvestingActivities` (0.49 vs PDF 0.53) | NATIVE | NATIVE [U]: S-sch "Interest received" | NATIVE [U]: "Interest Recieved" | ABSENT | — | 4 (2) |
| `cf_dividends_received_investing` | Dividends received (investing) | H/FY | NATIVE: `DividendsReceivedClassifiedAsInvestingActivities` | UNKNOWN | NATIVE [U]: S-sch "Dividends received" (2/10); "Investment income" (2/10) | NATIVE [U]: "Dividends Recieved" | ABSENT | — | 3 (1) |
| `cf_partnership_firms` | Partnership/AOP/LLP investments and profit share | H/FY | NATIVE: `CashPaymentForInvestmentInPartnershipFirm…`, `CashReceiptsFromShareOfProfitsOfPartnershipFirm…` | UNKNOWN | ABSENT | ABSENT | ABSENT | — | 1 (1) |
| `cf_government_grants` | Government grants received | H/FY | NATIVE: `ProceedsFromGovernmentGrantsClassifiedAsInvestingActivities` | UNKNOWN | ABSENT | ABSENT | ABSENT | — | 1 (1) |
| `cf_other_investing` | Other investing flows | H/FY | NATIVE: `OtherInflowsOutflowsOfCashClassifiedAsInvestingActivities` | UNKNOWN | NATIVE [U]: S-sch "Other investing items", "Redemp n Canc of Shares" | ABSENT | ABSENT | — | 2 (1) |
| `cfi` | Net cash from investing activities | H/FY | NATIVE: `CashFlowsFromUsedInInvestingActivities` | NATIVE | NATIVE [U]: "Cash from Investing Activity" | NATIVE [U]: "Cash from Investing Activity" | NATIVE [U]: summary `investing`; `full_statement` "Cash flow from Investing" | — | 5 (2) |
| `cf_proceeds_shares` | Proceeds from issuing shares / other equity / ESOP | H/FY | NATIVE: `ProceedsFromIssuingSharesClassifiedAsFinancingActivities`, `ProceedsFromIssuingOtherEquityInstruments`, `ProceedsFromExerciseOfStockOptions` | UNKNOWN | NATIVE [U]: S-sch "Proceeds from shares" | NATIVE [U]: "Proceeds From Shares" | ABSENT | — | 3 (1) |
| `cf_buyback_equity_payments` | Buyback / payments of other equity | H/FY | NATIVE: `PaymentsToAcquireOrRedeemEntitysShares`, `PaymentsOfOtherEquityInstruments` | UNKNOWN | UNKNOWN | ABSENT | ABSENT | — | 1 (1) |
| `cf_ownership_changes_subsidiaries` | Changes in ownership in subsidiaries (no loss of control) | H/FY | NATIVE: `ProceedsFromChangesInOwnershipInterestsInSubsidiaries`, `PaymentsFromChangesIn…` | UNKNOWN | ABSENT | ABSENT | ABSENT | — | 1 (1) |
| `cf_proceeds_borrowings` | Proceeds from borrowings (incl. debentures) | H/FY | NATIVE: `ProceedsFromBorrowingsClassifiedAsFinancingActivities`, `ProceedsFromIssuingDebenturesNotesBondsEtc` | NATIVE (short-term net + long-term lines) | NATIVE [U]: S-sch "Proceeds from borrowings" | NATIVE [U]: "Proceeds From Borrowings" (long-term) | ABSENT | — | 4 (2) |
| `cf_repayment_borrowings` | Repayments of borrowings | H/FY | NATIVE: `RepaymentsOfBorrowingsClassifiedAsFinancingActivities` | NATIVE | NATIVE [U]: S-sch "Repayment of borrowings" | NATIVE [U]: "Repayment From Borrowings" | ABSENT | — | 4 (2) |
| `cf_lease_payments` | Payments of lease liabilities | H/FY | NATIVE: `PaymentsOfLeaseLiabilitiesClassifiedAsFinancingActivities` (in-bse-fin: `PaymentsOfFinanceLeaseLiabilities…`) | NATIVE | NATIVE [U]: S-sch "Financial liabilities" (meaning unproven) | ABSENT | ABSENT | — | 3 (2) |
| `cf_dividends_paid` | Dividends paid | H/FY | NATIVE: `DividendsPaidClassifiedAsFinancingActivities` | NATIVE: "Dividend Payment" | NATIVE [U]: S-sch "Dividends paid" | NATIVE [U]: "Dividend Paid" | ABSENT | — | 4 (2) |
| `cf_interest_paid_financing` | Interest paid (financing) | H/FY | NATIVE: `InterestPaidClassifiedAsFinancingActivities` | NATIVE | NATIVE [U]: S-sch "Interest paid fin" | NATIVE [U]: "Interest Paid" | ABSENT | — | 4 (2) |
| `cf_other_financing` | Other financing flows | H/FY | NATIVE: `OtherInflowsOutflowsOfCashClassifiedAsFinancingActivities` | UNKNOWN | NATIVE [U]: S-sch "Other financing items" | ABSENT | ABSENT | — | 2 (1) |
| `cff` | Net cash from financing activities | H/FY | NATIVE: `CashFlowsFromUsedInFinancingActivities` | NATIVE | NATIVE [U]: "Cash from Financing Activity" | NATIVE [U]: "Cash from Financing Activity" | NATIVE [U]: summary `financing`; `full_statement` "Cash flow from Financing" | — | 5 (2) |
| `cf_net_change_before_fx` | Net change in cash before FX | H/FY | NATIVE: `IncreaseDecreaseInCashAndCashEquivalentsBeforeEffectOfExchangeRateChanges` | NATIVE: "Net increase/(decrease)" | NATIVE [U]: "Net Cash Flow" (before or after FX unproven) | NATIVE [U]: "Net Cash Flow" | NATIVE [U]: `full_statement` "Total Cash Flow" | — | 5 (2) |
| `cf_fx_effect` | Effect of FX on cash | H/FY | NATIVE: `EffectOfExchangeRateChangesOnCashAndCashEquivalents` | NATIVE | ABSENT | NATIVE [U]: "Effect of FX" | ABSENT | — | 3 (2) |
| `cf_net_change` | Net change in cash after FX | H/FY | NATIVE: `IncreaseDecreaseInCashAndCashEquivalents` | FORMULA | UNKNOWN | ABSENT | UNKNOWN | — | 1 (1) |
| `cf_cash_opening` | Opening cash and cash equivalents | H/FY | NATIVE: `CashAndCashEquivalentsCashFlowStatement` @ `PY_I` | NATIVE | ABSENT (RL screen field "Cash beginning of last year") | NATIVE [U]: "Opening Cash & Cash Equivalents" | NATIVE [U]: `full_statement` "Cash (Start of the year)" | — | 4 (2) |
| `cf_cash_closing` | Closing cash and cash equivalents | H/FY | NATIVE: `CashAndCashEquivalentsCashFlowStatement` @ `OneI` | NATIVE | ABSENT (RL "Cash end of last year") | NATIVE [U]: "Closing Cash & Cash Equivalents" | NATIVE [U]: `full_statement` "Cash (End of the year)" | — | 4 (2) |

### 2d. Segment results (templated per reportable segment `k`; quarter, YTD; consolidated)

XBRL places segment `k` in `ReportableSegmentsAxis = ReportableSegments{k}Member`. Results use
`ReportableSegmentsFinanceCostsAxis`, assets use `ReportableSegmentAssetsAxis`, and liabilities use
`ReportableSegmentLiabilitiesAxis`. The name comes from `DescriptionOfReportableSegment`. Apar has
4 segments.

| canonical_id | description | periodicity | XBRL | PDF | Screener | Tijori | Upstox | SHP | cov |
|---|---|---|---|---|---|---|---|---|---|
| `segment_name[k]` | Segment description | Q/H/FY | NATIVE: `DescriptionOfReportableSegment` | NATIVE (row label) | NATIVE [U]: segment row labels in `/api/segments/…` fragment (SM §3a) | UNKNOWN: Overview "Revenue Mix" product/location break-ups (INV; `tijori_overview_revenue_mix.py`); not a segment report | ABSENT | — | 3 (2) |
| `segment_revenue[k]` | Segment revenue (gross of inter-segment) | Q/H/FY | NATIVE: `SegmentRevenue` @ segment member | NATIVE | NATIVE [U]: segment line "Sales" (TITAN exceeds page Sales; ETERNAL has a "Less: Intersegment" row; screener_segments.py) | UNKNOWN (Revenue Mix % shares only?) | ABSENT | — | 3 (2) |
| `segment_revenue_total` | Total segment revenue | Q/H/FY | NATIVE: `SegmentRevenue` (no dimension) | NATIVE | FORMULA UNPROVEN (sum of segment Sales; does not reliably equal page Sales) | ABSENT | ABSENT | — | 2 (2) |
| `inter_segment_revenue` | Inter-segment revenue | Q/H/FY | NATIVE: `InterSegmentRevenue` | NATIVE: "Less: Inter-segment revenue" | NATIVE [U]: "Less: Intersegment" (ETERNAL only) | ABSENT | ABSENT | — | 3 (2) |
| `segment_revenue_from_operations` | External revenue (= P&L revenue) | Q/H/FY | NATIVE: `SegmentRevenueFromOperations` (= `RevenueFromOperations`, Apar) | NATIVE | ABSENT | ABSENT | ABSENT | — | 2 (2) |
| `segment_result[k]` | Segment result (profit before finance cost and tax) | Q/H/FY | NATIVE: `SegmentProfitLossBeforeTaxAndFinanceCosts` @ segment member | NATIVE | NATIVE [U]: segment line "Profit" (definition unproven) | ABSENT | ABSENT | — | 3 (2) |
| `segment_result_total` | Total segment results | Q/H/FY | NATIVE: `SegmentProfitLossBeforeTaxAndFinanceCosts` (no dimension) | NATIVE | ABSENT | ABSENT | ABSENT | — | 2 (2) |
| `segment_finance_costs` | Finance cost (reconciling) | Q/H/FY | NATIVE: `SegmentFinanceCosts` | NATIVE | ABSENT | ABSENT | ABSENT | — | 2 (2) |
| `segment_unallocable_net` | Unallocable expenditure net of income (+ other eliminations) | Q/H/FY | NATIVE: `OtherUnallocableExpenditureNetOffUnAllocableIncome`. Apar 36.72 = PDF unallocable 32.58 + "other elimination" 4.11 (two PDF lines in one element) | NATIVE: 2 lines (Apar) | ABSENT | ABSENT | ABSENT | — | 2 (2) |
| `segment_profit_before_tax` | PBT per the segment reconciliation (after associates, Apar) | Q/H/FY | NATIVE: `SegmentProfitBeforeTax` (340.53 = PDF line 9) | NATIVE | ABSENT | ABSENT | ABSENT | — | 2 (2) |
| `segment_assets[k]` | Segment assets | H/FY | NATIVE: `SegmentAssets` @ member. **Post-elimination** in Apar (Conductors 5,333.37 vs PDF 5,989.96) | NATIVE (pre-elimination) | NATIVE [U]? segment line "Capital Employed" is a different measure | ABSENT | ABSENT | — | 2 (2) |
| `segment_assets_total` | Total segment assets / unallocable / net | H/FY | NATIVE: `SegmentAssets`, `UnAllocableAssets`, `NetSegmentAssets` (= `Assets`) | NATIVE (+ "Less: Inter-segment assets") | ABSENT | ABSENT | ABSENT | — | 2 (2) |
| `inter_segment_assets` | Inter-segment asset elimination | H/FY | ABSENT (no element; eliminations pushed into members) | NATIVE | ABSENT | ABSENT | ABSENT | — | 1 (1) |
| `segment_liabilities[k]` | Segment liabilities | H/FY | NATIVE: `SegmentLiabilities` @ member (Apar allocation differs from PDF: Power/Telecom 928.57 vs 1,585.16) | NATIVE | ABSENT | ABSENT | ABSENT | — | 2 (2) |
| `segment_liabilities_total` | Total / unallocable / net segment liabilities | H/FY | NATIVE: `SegmentLiabilities`, `UnAllocableLiabilities`, `NetSegmentLiabilities` | NATIVE | ABSENT | ABSENT | ABSENT | — | 2 (2) |
| `segment_capital_employed[k]` | Capital employed per segment (vendor) | Q/FY | FORMULA UNPROVEN: assets − liabilities | FORMULA | NATIVE [U]: segment line "Capital Employed"; also "ROCE %", "Profit %", growth % lines | ABSENT | ABSENT | — | 1 (0) |

### 2e. Shareholding pattern (quarterly)

No SHP filing is ingested. Vendor equivalence to the SHP is unmeasured everywhere.

| canonical_id | description | periodicity | XBRL | PDF | Screener | Tijori | Upstox | SHP | cov |
|---|---|---|---|---|---|---|---|---|---|
| `shp_promoter_pct` | Promoter and promoter group % | Q | ABSENT (not in results XBRL) | ABSENT | NATIVE [U]: "Promoters" (quarterly and yearly tables; drill-down holders sum to the row, e.g. TITAN 52.90; screener_shareholding.py) | UNKNOWN: real labels not captured (only a synthetic fixture; breakup docstring example `['Promoter', 52.9]`) | NATIVE [U]: `promoters` | UNVERIFIED-general-knowledge: Table II | 2 (0) |
| `shp_promoter_pledged_pct` | Promoter shares pledged/encumbered | Q | ABSENT | ABSENT | UNKNOWN on company page; RL screen fields "Pledged percentage", "Unpledged promoter holding" | UNKNOWN: `company_details.quick_look` has a pledge flag (INV), values unverified | ABSENT (5 categories only) | UNVERIFIED-general-knowledge: encumbrance columns | 0 (0) |
| `shp_fpi_pct` | Foreign portfolio investors (FII/FPI) % | Q | ABSENT | ABSENT | NATIVE [U]: "FIIs" | UNKNOWN | NATIVE [U]: `fii` | UNVERIFIED-general-knowledge | 2 (0) |
| `shp_dii_pct` | Domestic institutions % (total) | Q | ABSENT | ABSENT | NATIVE [U]: "DIIs" | UNKNOWN | FORMULA UNPROVEN: `mutual_funds + other_dii` | UNVERIFIED-general-knowledge | 1 (0) |
| `shp_mutual_funds_pct` | Mutual funds % | Q | ABSENT | ABSENT | ABSENT (only via drill-down holders ≥1 %, BOUNDED) | UNKNOWN (docstring example "Mutual Funds") | NATIVE [U]: `mutual_funds` | UNVERIFIED-general-knowledge | 1 (0) |
| `shp_other_dii_pct` | DII excl. mutual funds (insurance, banks, …) | Q | ABSENT | ABSENT | ABSENT | UNKNOWN | NATIVE [U]: `other_dii` | — | 1 (0) |
| `shp_insurance_pct` | Insurance companies % | Q | ABSENT | ABSENT | ABSENT | UNKNOWN | ABSENT (inside `other_dii`?) | UNVERIFIED-general-knowledge | 0 (0) |
| `shp_government_pct` | Central/state government % | Q | ABSENT | ABSENT | NATIVE [U]: "Government" | UNKNOWN | ABSENT (folded somewhere; unproven) | UNVERIFIED-general-knowledge | 1 (0) |
| `shp_public_pct` | Public / retail % | Q | ABSENT | ABSENT | NATIVE [U]: "Public" | UNKNOWN | FORMULA UNPROVEN: `retail_and_other` (mixes "Public" and "Others"?) | UNVERIFIED-general-knowledge | 1 (0) |
| `shp_others_pct` | Others % | Q | ABSENT | ABSENT | NATIVE [U]: "Others" | UNKNOWN | see above | — | 1 (0) |
| `shp_custodian_dr_pct` | Shares held by custodians (DRs) | Q | ABSENT | ABSENT | ABSENT | UNKNOWN (label in synthetic fixture only) | ABSENT | UNVERIFIED-general-knowledge: Table IV | 0 (0) |
| `shp_num_shareholders` | Number of shareholders | Q | ABSENT | ABSENT | NATIVE [U]: "No. of Shareholders" | UNKNOWN | ABSENT | UNVERIFIED-general-knowledge | 1 (0) |
| `shp_holder_detail[h]` | Named holder % (≥1 %) | Q | ABSENT | ABSENT | NATIVE [U]: investors drill-down `{holder: {period: pct}}` (promoters complete; others ≥1 % only) | UNKNOWN (Detailed tab) | ABSENT | UNVERIFIED-general-knowledge | 1 (0) |

### 2f. Vendor summary and derived rows (FORMULA rows over base rows)

Periodicity follows the vendor table. A "MEASURED" verdict here means measured on the nine
Q3FY25 stocks (MEAS) unless noted.

| canonical_id | description | periodicity | XBRL | PDF | Screener | Tijori | Upstox | SHP | cov |
|---|---|---|---|---|---|---|---|---|---|
| `operating_expenses_ex_fin_da` | Total expenses − finance costs − D&A | Q/FY | FORMULA (derivable) | FORMULA | FORMULA MEASURED: "Expenses" = `total_expenses − finance_costs − depreciation_amortisation`, 8/9 (THERMAX +21.2) | FORMULA MEASURED: `qt_*` "Operating Expenses" (`EXPENDITURE`), same, 8/9 (THERMAX +20.96); `pl_*` (`Total_expendiure`) [U] | ABSENT | — | 2 (2) |
| `operating_profit_vendor` | Revenue from operations − operating expenses (excl. other income); "EBITDA ex-OI" | Q/FY | FORMULA | FORMULA | FORMULA MEASURED: "Operating Profit" = `revenue_from_operations − operating_expenses_ex_fin_da`, 9/9 (THERMAX agrees too: the +21 cancels) | FORMULA MEASURED: "Operating Profit" (formula string `Operating_profit − Other_income`), 9/9 | ABSENT (summary `operating_profit` is PBT, U-doc) | — | 2 (2) |
| `opm_pct` | Operating profit ÷ revenue × 100 | Q/FY | — | — | FORMULA MEASURED: "OPM %" 9/9 (integer rounding) | FORMULA MEASURED (THERMAX one row): "Operating Profit Margin" = OP/Sales×100. The vendor formula string says ×1000, so formula strings are not literal. `pl_*` "OPM (%)" | ABSENT | — | 2 (2) |
| `pbdt_vendor` | Profit before depreciation and tax | Q/FY | — | — | ABSENT | FORMULA MEASURED: "PBDT" = OP + other_income − finance_costs + exceptional_items (CGPOWER, ETERNAL, TITAN exact; SONACOMS shows exceptional is inside) | ABSENT | — | 1 (1) |
| `ebitda` | EBITDA (canonical definition to be chosen) | Q/FY | — | — | UNKNOWN: RL "EBIDT latest quarter" etc. (screen fields, undefined) | UNKNOWN: `fr_c` "EV/EBITDA" uses `EV_Core_EBITDA` | UNKNOWN: key-ratio "EV/EBITDA" (definition unstated) | — | 0 (0) |
| `ebit_vendor` | EBIT | FY | — | — | UNKNOWN: RL "EBIT" | FORMULA UNPROVEN: `fr_c` "EBIT (Crs)" = `Operating_profit − Depreciation` (vendor string; here `Operating_profit` appears to include other income — THERMAX Mar-26 1,293.74 = 1,026.26 + 267.48) | ABSENT | — | 0 (0) |
| `pbt_margin_pct` | PBT ÷ revenue × 100 | Q/FY | — | — | ABSENT | ABSENT | ABSENT | — | 0 (0) |
| `effective_tax_rate_pct` | Tax expense ÷ PBT × 100 | Q/FY | — | — | FORMULA MEASURED: "Tax %" = `tax_expense / profit_before_tax × 100`, 9/9 (integer) | ABSENT (no row; `fr_c` uses `tax_rate` internally) | ABSENT | — | 1 (1) |
| `net_profit_margin_pct` | Net profit ÷ revenue × 100 | Q/FY | — | — | UNKNOWN: RL "NPM latest quarter" | FORMULA MEASURED (THERMAX Jun-26 one row): `qt_c` "Net Profit Margin" = Net Profit/Net Sales×100 (0.95); `fr_c` "Net Profit Margin (%)" [U] | ABSENT | — | 1 (1) |
| `material_cost_pct` | Materials ÷ revenue | Q/FY | — | — | FORMULA MEASURED: S-sch "Material Cost %" = `(cost_of_materials_consumed + purchases_of_stock_in_trade + changes_in_inventories) / Sales × 100`, 9/9 | FORMULA (vendor-internal, THERMAX): `pl_*` "Material Cost (%)" = `(Inc/Dec in Stock + Raw Material) / Net Sales × 100`. **Excludes stock-in-trade** | ABSENT | — | 2 (1) |
| `employee_cost_pct` | Employee cost ÷ revenue | Q/FY | — | — | FORMULA MEASURED: S-sch "Employee Cost %", 9/9 | ABSENT | ABSENT | — | 1 (1) |
| `gross_margin_pct` | 100 − material cost % | FY | — | — | ABSENT | FORMULA UNPROVEN: `fr_c` "Gross Margin (%)" = 100 − Material Cost (%) | ABSENT | — | 0 (0) |
| `profit_excl_exceptional` | Net profit excluding exceptional items (after tax) | Q/FY | — | — | FORMULA UNPROVEN: S-sch "Profit excl Excep" (SONACOMS 155 = 151 + 4) | ABSENT | ABSENT | — | 0 (0) |
| `profit_for_pe` | Profit used for P/E | Q/FY | — | — | FORMULA UNPROVEN: S-sch "Profit for PE" (≈ owners profit excl. exceptional) | ABSENT | ABSENT | — | 0 (0) |
| `ttm_revenue` / `ttm_net_profit` | Trailing twelve months | TTM | FORMULA: sum of 4 quarters | FORMULA | NATIVE [U]: profit-loss "TTM" column | NATIVE [U]: `pl_*` last column labelled `Jun 2026` (= TTM, THERMAX one stock) | ABSENT | — | 2 (0) |
| `free_cash_flow` | CFO − capex | FY | FORMULA | FORMULA | NATIVE [U]: "Free Cash Flow" (THERMAX −401 ≈ CFO 541.55 − net capex 942.45) | FORMULA (vendor-internal, THERMAX): "Free Cash Flow (est)" = CFO − "Net Capex (est)" (−400.9) | ABSENT | — | 1 (0) |
| `cfo_to_op_pct` | CFO ÷ operating profit | FY | — | — | NATIVE [U]: "CFO/OP" | ABSENT | ABSENT | — | 1 (0) |
| `working_capital_days` etc. | Debtor days, inventory days, payable days, CCC, WC days | FY | — | — | NATIVE [U]: ratios "Debtor Days", "Inventory Days", "Days Payable", "Cash Conversion Cycle", "Working Capital Days" | NATIVE [U]: `fr_c` "Days Receivable", "Inventory Days", "Days Payable", "Cash Conversion Cycle" | ABSENT | — | 2 (0) |
| `roce_pct` | ROCE | FY | — | — | NATIVE [U]: ratios "ROCE %" | FORMULA UNPROVEN: `fr_c` "ROCE (%)" = (OP − D&A)/(Total assets − Current liabilities) | NATIVE [U]: key-ratio "ROCE" (string with %) | — | 2 (0) |
| `roe_roa_pct` | ROE, ROA | FY | — | — | UNKNOWN (top ratio "ROE"; RL fields) | FORMULA UNPROVEN: `fr_c` "ROE (%)", "Return on Assets (%)" | NATIVE [U]: key-ratios "ROE", "ROA" | — | 1 (0) |
| `debt_to_equity` | Debt ÷ equity | FY | — | — | UNKNOWN: RL "Debt to equity" | FORMULA UNPROVEN: `fr_c` "Debt to Equity Ratio" | ABSENT | — | 0 (0) |
| `interest_coverage` | EBIT ÷ interest | FY | — | — | UNKNOWN: RL "Interest Coverage Ratio" | FORMULA UNPROVEN: `fr_c` "Interest Coverage Ratio" | ABSENT | — | 0 (0) |
| `current_quick_ratio` | Current / quick ratio | FY | — | — | UNKNOWN: RL fields | NATIVE [U]: `fr_c` "Current Ratio", "Quick Ratio" | NATIVE [U]: key-ratio "Quick Ratio" (absent for HFCL) | — | 2 (0) |
| `dividend_payout_pct` | Dividend payout | FY | — | — | NATIVE [U]: "Dividend Payout %" | NATIVE [U]: "Dividend Payout Ratio(%)" | ABSENT | — | 2 (0) |
| `valuation_ratios` | P/E, P/B, EV/EBITDA, dividend yield (price-dependent) | daily | — | — | NATIVE [U]: top ratios "Stock P/E", "Book Value", "Dividend Yield" | NATIVE [U]: `fr_c` "P/E", "Price to Book", "EV/EBITDA", "Dividend Yield (%)" | NATIVE [U]: key-ratios "P/E", "P/B", "EV/EBITDA" | — | 3 (0) |
| `upstox_total_liability` | Upstox liabilities excl. equity | FY | FORMULA = `total_liabilities` | FORMULA | FORMULA MEASURED (vs Upstox): "Borrowings" + "Other Liabilities" (LB) | — | NATIVE [U]: summary `total_liability` | — | — |

## 3. Gaps (0 or 1 sources with coverage)

These counts use `n`, NATIVE of any tier.

**Only the filing carries it (XBRL and/or PDF only).** Every vendor is ABSENT or UNKNOWN on:

- All OCI lines: `oci_*`, `total_comprehensive_income`, `tci_*`.
- The discontinued-operations block and the regulatory-deferral rows.
- The diluted and continuing/discontinued EPS variants. Only Upstox has annual `eps_diluted`.
- `purchases_of_stock_in_trade` and `other_expenses`: XBRL and PDF only.
- `tax_earlier_years`: PDF only. XBRL folds it into `CurrentTax`.

**XBRL carries it but the PDF prints no separate line.** These are filer-dependent:

- `right_of_use_assets`, `noncurrent_tax_assets`, `lease_liabilities_*`, `inter_segment_assets`
  — these are the PDF-only side.
- XBRL subtotals `noncurrent_financial_assets`, `current_financial_assets`,
  `current_financial_liabilities`, `noncurrent_financial_liabilities`.

**Segment family.** Beyond segment name, revenue and result, only XBRL and PDF carry segment
data. Screener's segment lines are vendor-defined ("Profit", "Capital Employed").

**Shareholding.** No first-party source is ingested. Screener and Upstox are the only sources
observed, and both are unmeasured.

- Gaps with 0 or 1 sources: pledge %, insurance %, custodian/DR %, MF % (Upstox only), other-DII
  % (Upstox only), government % (Screener only), number of shareholders (Screener only), named
  holders (Screener only).
- **Pledge has zero observed sources** on the company-page surfaces.

**CF detail.** Roughly 30 XBRL elements have no vendor counterpart. These are the investing and
financing sub-flows and the dividend/interest operating classification.

**Derived rows with no MEASURED source.** EBITDA (three vendors, three undefined definitions),
EBIT, PBT margin, debt/equity, interest coverage, gross margin.

**`shares_outstanding`.** No first-party element exists in the results XBRL. Only Tijori carries
a vendor row, and it is unproven.

**Coverage that looks fine but is unmeasured.** Every vendor balance-sheet and cash-flow row is
`[U]`. The measured coverage `m` for BS and CF is 2 everywhere — XBRL plus PDF — and never
includes a vendor.

## 4. Definition conflicts (evidence-backed)

1. **XBRL `ProfitBeforeTax` excludes the share of associates; the PDF's "Profit before tax"
   includes it.**
   - In both taxonomies the associates' share is added after tax: `ProfitLossForPeriod =
     ProfitLossForPeriodFromContinuingOperations + ShareOfProfit…`, e.g. HFCL 71.93 + 0.65 =
     72.58 (X9).
   - In the Apar PDF, line 8 sits *before* tax. So Apar XBRL PBT 340.56 equals PDF line 7, not
     PDF "9 Profit before tax" (340.53).
   - The repo's PDF extractor already special-cases the pre-associate line
     (`pdf_column_geometry.py`, `conditional_labels`).
   - A canonical spec needs two PBT rows.
2. **Tijori `qt_c` "Net Profit" is PBT − Tax, before associates — not `ProfitLossForPeriod`.**
   - It equals `ProfitLossForPeriodFromContinuingOperations` to 0.01 cr on 9/9 stocks (MEAS):
     LAURUSLABS 90.61 vs PL 92.94; THERMAX 114.23 vs 113.73; HFCL 71.93 vs 72.58; TITAN 1,047
     vs 1,047.28.
   - 3S concluded "Tijori publishes consolidated profit … including non-controlling interest"
     and called LAURUSLABS "unexplained". Its 1-crore tolerance hid the associates term.
   - Bead eqos-al0's planned freeze of the Tijori net-profit mapping to `ProfitLossForPeriod`
     would therefore be wrong for associate-holding companies.
   - Screener "Net Profit" *does* equal `ProfitLossForPeriod`.
3. **Screener "Expenses" and "Operating Profit" are not filing lines.**
   - Expenses = total expenses − finance costs − D&A.
   - Operating Profit = revenue − that, i.e. EBITDA excluding other income.
   - Tijori "Operating Expenses" / "Operating Profit" use the same construction (MEAS 8/9 and
     9/9).
   - Upstox summary `operating_profit` is a third thing again: PBT (U-doc, LB).
4. **Screener "Other Income" includes exceptional items.** The S-sch expander shows
   "Exceptional items" + "Other income normal", and SONACOMS proves the sum.
   - Tijori "Other Income" excludes exceptional items; Tijori carries them in a separate
     "Exceptional Items" row inside PBT/PBDT.
   - CGPOWER FY24 (LB) is the large-magnitude instance: Screener PBT 1,715 vs Upstox 1,158.38.
5. **THERMAX revenue: both vendors are ~21 cr above filed `RevenueFromOperations` (3S).** The
   same +20.96 cr appears in:
   - Tijori "Raw Material" (1,363.25 vs `CostOfMaterialsConsumed` 1,342.29);
   - Tijori "Operating Expenses";
   - Screener "Expenses" (+21.2).

   Operating profit agrees. So the vendors gross up revenue and materials by the same item, a
   presentation difference such as netted scrap or recoveries. The filed line is not identified;
   the hypothesis is not proven.
6. **Screener "Total Liabilities" is the balance-sheet total (equity + liabilities).** It equals
   "Total Assets" on every period (LB). Real liabilities = "Borrowings" + "Other Liabilities"
   (vs Upstox `total_liability`, LB). NCI sits inside "Other Liabilities" (S-sch "Non
   controlling int"), so Screener's equity excludes NCI.
7. **Upstox `revenue` is Total Revenue (operations + other income),** not revenue from operations
   (U-doc). Upstox also contradicts itself inside one response:
   - NETWEB summary vs `full_statement`: 0.97 and 0.73 cr;
   - POLYCAB Mar-23: summary `net_profit` 1,283.09 vs PAT 1,282.25;
   - CGPOWER FY24: summary `net_profit` ≈ Screener while `full_statement` PAT differs (LB).
8. **EPS is vendor-derived, not transcribed.**
   - Screener "EPS in Rs" differs from filed basic EPS on 3/9 stocks (3S), with an S-sch "Profit
     for EPS" input.
   - Tijori EPS is `adj_eps_abs` ("adjusted"), TITAN 11.764 vs 11.80.
   - MAP's `tijori.eps.alias_only` says no Tijori EPS row exists. A row does exist in the capture
     (`qt_c` "Quarterly Ratios/EPS"); it is just not parsed.
9. **Material-cost ratios differ by vendor.** Screener "Material Cost %" includes stock-in-trade
   (MEAS 9/9). Tijori "Material Cost (%)" formula excludes it, and Tijori has no stock-in-trade
   row at all.
10. **XBRL filer folding and tagging quirks (Apar, one filing each).** These make XBRL a weaker
    line-level source than its NATIVE label suggests:
    - ROU assets folded into `OtherIntangibleAssets`.
    - Lease liabilities and derivatives folded into "other financial liabilities".
    - Non-current tax assets folded into `OtherNoncurrentAssets`.
    - Earlier-years tax folded into `CurrentTax`.
    - Two PDF segment lines combined in `OtherUnallocableExpenditureNetOffUnAllocableIncome`.
    - Segment assets/liabilities post-elimination with a different allocation than the PDF.
    - `ComprehensiveIncomeForThePeriodAttributableToOwnersOfParent` carrying OCI-owners rather
      than TCI-owners.
    - `ProceedsFromSalesOfInvestmentProperty…` used for sale of investments.
    - `FaceValueOfEquityShareCapital` = 0 at `FourD`.
    - Elsewhere: CGPOWER owners-of-parent −20.54 (3S); MTARTECH no owners figure.
11. **Screener HFCL "Other income normal" (20.69) = filed other income (20.04) + share of
    associates (0.65).** For LAURUSLABS the associates share is a separate "Profit from
    Associates" sub-row. So Screener's placement of associates varies by company. This is
    inferred from two stocks.
12. **Tijori formula strings are not executable truth.** Examples: OPM `…*1000` while the value
    is a percent; several `*10000000` scale artifacts in `fr_c`; "Short Term Loans and Advances"
    and "Other Current Assets" share the formula `Other_Current_Nf` but carry different values.
    Use them as hints only.
13. **Tijori `pl_*` last column is labelled `Jun 2026` but is TTM** (THERMAX matches Screener
    TTM). A label-keyed join would treat it as a fiscal period.
14. **Upstox `full_statement` is annual even on quarterly requests,** with matching `Mon YYYY`
    labels. The four Upstox surfaces are not period-aligned per company (U-doc §2, LB).

## 5. Open questions

1. Does the in-capmkt taxonomy itself define elements for Sales vs other operating income,
   earlier-years tax, ROU assets, lease liabilities, and OCI attributable to owners/NCI?
   - What I verified: these elements are absent from the *instances*. The taxonomy schema
     (`in-capmkt-ent-2025-01-31.xsd`) is not in the repo, so taxonomy-level presence is UNKNOWN.
   - Same question for a share-count element.
2. Standalone XBRL. Only consolidated files are retained. Do standalone filings use the same
   element set, and does NSE publish both for every issuer?
3. Is the PDF line set issuer-stable? One PDF was read (Apar). Two things vary by issuer:
   - whether the associates share sits before or after tax;
   - whether an exceptional line, a continuing/discontinued split, or a printed total-tax line
     exists.
4. Upstox vs filing. No Upstox field has ever been compared with XBRL or the PDF; every Upstox
   cell is `[U]`. Also: is `full_statement` "Profit After Tax" `profit_for_period` or
   continuing PAT? And what goes into "Revenue"?
5. What is the THERMAX ~21 cr line? It needs the THERMAX Q3FY25 PDF, or a non-dimensional
   element hunt.
6. Tijori standalone (`qt_s`), `pl_c_d` sub-rows (Other Manufacturing, S&D, Power, G&A, Misc):
   what is the source of these breakdowns, which no filing prints? Why does quarterly
   "Miscellaneous Expenses" read 0 when other expenses are large?
7. Tijori shareholding: real row labels (Overview/Trend/Detailed tables) were never captured.
   The fixture is synthetic, so every Tijori SHP cell is UNKNOWN. Does a pledge % exist on any
   vendor company page?
8. Do Screener's "Fixed Assets", "Investments", "Reserves" and "Cash Equivalents" correspond to
   specific filing lines? There is no BS measurement against any filing. The only BS data is
   annual Mar year-ends, and the filings' half-year BS has no vendor counterpart.
9. Does Screener's quarterly table ever carry half-year or 9M figures? Not observed. Is the
   half-year BS available on any vendor?
10. EBITDA canonical definition: with or without other income, and with or without exceptional
    items? Screener and Tijori "Operating Profit" exclude both. No vendor-labelled EBITDA has a
    known definition.
11. NETWEB is standalone-only. Its Screener `/consolidated/` page is degenerate (SM §10), and
    Upstox consolidated is empty. Basis fallback rules affect every row.
12. Measurement breadth. Every MEASURED claim rests on nine stocks, one quarter (Q3FY25,
    in-bse-fin), and a single Screener/Tijori capture each. None was measured on in-capmkt
    filings or on annual columns.
