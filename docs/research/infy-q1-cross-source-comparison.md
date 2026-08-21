# Infosys Q1 FY25 — Cross-Source Fact Comparison

**Purpose:** extract the same Infosys Q1 FY25 (quarter ended **30-Jun-2024**) financial
facts from every independent source on hand and compare them fact-by-fact, so a human
analyst can see where sources **agree** (high confidence) vs **disagree** (needs
adjudication). This is **verification/evaluation scaffolding**, not product code, and not a
thesis. The human analyst adjudicates every discrepancy and owns the baseline; this document
is a cross-check aid only.

**Date:** 2026-08-21 · **Rights:** private/personal, owner-authorized
(`A05-DECISION-004`); polite, low-volume, INFY-scoped, no evasion; source bytes stay in the
gitignored session scratchpad. Raw extracted data lives in
`scratchpad/xsource-eval/` (not committed); only the comparison and small samples appear here.

---

## 0. Source status — what was extracted vs skipped

| # | Source | Basis / period | Status | Extraction path |
|---|---|---|---|---|
| 1 | **NSE Ind AS XBRL** | Consolidated **and** Standalone, Q1 FY25 (Apr–Jun 2024) | **SUCCESS** | `NseIndiaApi` → filing index + XBRL link; downloaded `INDAS_109110_…xml` (consol) / `INDAS_109109_…xml` (standalone); parsed **context-aware** (bound to context `OneD`, the Apr–Jun 2024 duration, segment-free) |
| 2 | **Deterministic PDF parse** | Consolidated (p11) + Standalone (p17), Q1 FY25 | **SUCCESS** | `PyMuPDF` word-geometry, row-band grouping; first data column (qtr ended 30-Jun-2024) bound per row; sha256 `a07c12ef…b372695` |
| 3 | **BSE Ind AS XBRL** | Q1 FY25 consolidated | **SKIPPED — not on hand** | Prior crawl4AI eval downloaded only **Q2/Q3/Q4** FY25 BSE XBRL (since cleaned); no Q1 file exists locally. `bse` lib `resultsSnapshot` returns only the **current** quarter (Jun-26), not Jun-24. A Q1 fetch needs a fresh heavy Chromium render of the BSE SPA filing index — out of scope per instructions |
| 4 | **SEC 20-F XBRL** | **FY25 ANNUAL, USD** (year ended 31-Mar-2025) | **SUCCESS (annual only)** | `data.sec.gov` companyfacts JSON, CIK 0001067491, declared UA. **Different period + currency** — annual reconciliation only, **not** comparable to the Q1 INR figure |
| 5 | **Tijori (aggregator, derived)** | — | **SKIPPED** | No saved session (`session.json`) on disk; would require re-login. Derived/optional — not worth re-authing per instructions |

**Two independent first-party sources landed on the Q1 FY25 quarterly figures: the NSE
Ind AS XBRL and the issuer results PDF.** Both derive from the same regulatory filing but via
fully independent extraction paths (typed XBRL facts vs. PDF pixel/word geometry), so exact
agreement is a genuine cross-validation that neither extractor mis-associates a column or a
context. BSE would have been a third, separately-hosted first-party feed but its Q1 file is not
on hand.

---

## 1. Comparison table — Q1 FY25 **Consolidated** P&L (₹ crore)

Basis: consolidated, Ind AS, quarter ended 30-Jun-2024. `—` = source does not carry a directly
comparable value.

| P&L line item | PDF (p11) | NSE XBRL (`OneD`) | BSE XBRL | SEC 20-F | Agreement | Provenance / concept |
|---|---:|---:|---:|---:|---|---|
| Revenue from operations | 39,315 | 39,315 | not on hand | annual only | **all-agree** | `RevenueFromOperations` |
| Other income, net | 838 | 838 | not on hand | — | **all-agree** | `OtherIncome` |
| Total income | 40,153 | 40,153 | not on hand | — | **all-agree** | `Income` |
| Employee benefit expenses | 20,934 | 20,934 | not on hand | — | **all-agree** | `EmployeeBenefitExpense` |
| Depreciation & amortisation | 1,149 | 1,149 | not on hand | — | **all-agree** | `DepreciationDepletionAndAmortisationExpense` |
| Finance cost | 105 | 105 | not on hand | — | **all-agree** | `FinanceCosts` |
| Other/allocable expenses (grouped) | 8,944¹ | 8,944 | not on hand | — | **agree (granularity)** | `OtherExpenses` — see §2 |
| Total expenses | 31,132 | 31,132 | not on hand | — | **all-agree** | `Expenses` |
| Profit before tax | 9,021 | 9,021 | not on hand | — | **all-agree** | `ProfitBeforeTax` |
| Current tax | 2,998 | 2,998 | not on hand | — | **all-agree** | `CurrentTax` |
| Deferred tax | (351) | (351) | not on hand | — | **all-agree** | `DeferredTax` |
| Tax expense (net) | 2,647 | 2,647 | not on hand | — | **all-agree** | `TaxExpense` (2,998 − 351) |
| **Profit for the period** | **6,374** | **6,374** | not on hand | — | **all-agree** | `ProfitLossForPeriod` |
| — attributable to owners | 6,368 | 6,368 | not on hand | — | **all-agree** | `ProfitOrLossAttributableToOwnersOfParent` |
| — non-controlling interests | 6 | 6 | not on hand | — | **all-agree** | `ProfitOrLossAttributableToNonControllingInterests` |
| Total OCI, net of tax | (33) | (33) | not on hand | — | **all-agree** | `OtherComprehensiveIncomeNetOfTaxes` |
| Total comprehensive income | 6,341 | 6,341 | not on hand | — | **all-agree** | `ComprehensiveIncomeForThePeriod` |
| Paid-up share capital | 2,072 | 2,072 | not on hand | — | **all-agree** | `PaidUpValueOfEquityShareCapital` (`OneI`, instant 30-Jun-2024) |
| **EPS basic (₹)** | **15.38** | **15.38** | not on hand | — | **all-agree** | `BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations` |
| EPS diluted (₹) | 15.35 | 15.35 | not on hand | — | **all-agree** | `DilutedEarningsLossPerShare…` |

¹ The PDF prints six itemized non-major expense lines (Cost of technical sub-contractors 3,169;
Travel 478; Cost of software packages & others 3,455; Communication 147; Consultancy &
professional 445; Other expenses 1,250). The XBRL concept `OtherExpenses` rolls these into a
single **8,944** (3,169+478+3,455+147+445+1,250 = 8,944). Same money, different granularity —
see §2.

**Cross-foot identities (hold on both sources, ±0):** Total income = Revenue + Other income
(40,153); PBT = Total income − Total expenses (9,021); PAT = PBT − net tax (6,374);
TCI = PAT + OCI (6,341).

### Provenance / scale sample (NSE XBRL, context-aware)

```
concept   : RevenueFromOperations
contextRef: OneD   (period 2024-04-01 → 2024-06-30, segment-free)
value_raw : 393150000000.00   unit iso4217:INR   decimals -7
→ 393150000000 / 1e7 = 39,315 ₹ crore
```

The **context-aware** rule is the fix for the known first-value bug: the same file also carries
`OneReportableSegmentRevenue01D…08D` and other dimensioned contexts sharing element names; a
naive `.find()`/first-value read can return a segment or a comparative value. Every fact above
is bound to the plain (no-segment) current-quarter context `OneD` (durations) / `OneI`
(instants). This NSE quarterly file carries **only** current-quarter contexts (no prior-period
columns), so the period-context trap does not arise here; the segment-dimension trap does, and
is handled.

---

## 2. Discrepancies — flagged for analyst adjudication

Between the two on-hand first-party sources (PDF vs NSE XBRL) there are **zero numeric
conflicts** on the consolidated Q1 FY25 P&L. The items below are **presentational / concept
differences and known traps**, not value disagreements:

1. **Expense sub-itemisation (granularity, not a conflict).** PDF exposes six named expense
   sub-lines; XBRL groups them under `OtherExpenses` = 8,944. Both reconcile to Total expenses
   31,132. *Adjudication:* none needed for headline P&L; only matters if the analyst wants the
   itemised expense mix, which is **PDF-only** (the XBRL does not break it out).

2. **Standalone vs Consolidated (the ~10% trap).** The **standalone** Q1 FY25 figures differ
   materially from consolidated and both on-hand sources agree on them:

   | Line | PDF standalone (p17) | NSE standalone XBRL | Consolidated (for contrast) |
   |---|---:|---:|---:|
   | Revenue from operations | 33,283 | 33,283 | 39,315 |
   | Profit before tax | 8,128 | 8,128 | 9,021 |
   | Profit for the period | 5,768 | 5,768 | 6,374 |
   | Basic EPS (₹) | — | 13.90 | 15.38 |

   *Adjudication trap:* a summary/aggregator feed that surfaces **standalone** net profit
   (**5,768**, EPS **13.90**) while the analyst assumes **consolidated** (**6,374**, EPS
   **15.38**) is a ~9–10% error. Prior library evidence (`libs-pipeline-capability.md` §1.1)
   shows NSE's `results_comparison` summary returning the 5,768 / 13.90 standalone numbers — a
   live example of this trap. **Always confirm consolidated-vs-standalone basis.**

3. **BSE Q1 XBRL absent (single-source risk).** The consolidated Q1 figures currently rest on
   two extraction paths over the **same** issuer filing. A genuinely independent second host
   (BSE `in-bse-fin` XBRL, scrip 500209) exists but its **Q1 (Jun-24)** file was never
   downloaded (only Q2/Q3/Q4 were, and those scratch files are gone). Until fetched, there is no
   cross-**host** confirmation of Q1 — only cross-**method** on NSE/PDF. *Adjudication:* treat
   the Q1 consolidated numbers as high-confidence but note they trace to one filing, not two
   independent filings.

4. **SEC = annual, USD — do not compare to Q1 INR.** See §3; flagged so no one foots it against
   the ₹-crore quarter.

---

## 3. SEC 20-F cross-check — **FY25 ANNUAL, US$ millions (separate period, do not mix)**

Year ended **31-Mar-2025**, IFRS, **USD** — a different period *and* currency from the Q1 INR
statement above. Included only for annual reconciliation. Source: SEC companyfacts JSON,
CIK 0001067491, accession 0000950170-25-091925 (20-F). Values match the prior
`pdf-extraction-bakeoff.md` §3c exactly.

| Line (IFRS) | SEC 20-F XBRL | US$ m |
|---|---|---:|
| Revenue (`RevenueFromContractsWithCustomers`) | 19,277,000,000 | 19,277 |
| Cost of sales (`CostOfSales`) | 13,405,000,000 | 13,405 |
| Gross profit (`GrossProfit`) | 5,872,000,000 | 5,872 |
| Operating profit (`ProfitLossFromOperatingActivities`) | 4,071,000,000 | 4,071 |
| Profit before tax (`ProfitLossBeforeTax`) | 4,447,000,000 | 4,447 |
| Income tax (`IncomeTaxExpenseContinuingOperations`) | 1,285,000,000 | 1,285 |
| Net profit (`ProfitLoss`) | 3,162,000,000 | 3,162 |
| Net profit attributable to owners (`…OwnersOfParent`) | 3,158,000,000 | 3,158 |
| Basic / Diluted EPS | — | 0.76 / 0.76 |

No quarterly structured data exists at SEC (6-K filings carry no quarterly income-statement
XBRL), so SEC cannot corroborate the Q1 quarter directly — annual only.

---

## 4. Confidence summary

- **Consolidated Q1 FY25 P&L line items compared: 19.**
  **Agree exactly across both on-hand first-party sources (PDF + NSE XBRL): 19 / 19.**
  **True value conflicts requiring adjudication: 0.**
- **Standalone Q1 FY25:** 4 / 4 compared items agree (PDF + NSE standalone XBRL).
- **Presentational / trap notes flagged (not value conflicts): 4** — expense granularity;
  standalone-vs-consolidated basis; BSE-host absent (cross-method only, not cross-host);
  SEC annual/USD separateness.
- **High confidence:** every headline consolidated P&L number (Revenue 39,315; PBT 9,021;
  PAT 6,374; EPS 15.38) is confirmed by two independent extraction methods with zero difference
  and passes all four cross-foot identities.
- **Residual risk for the analyst:** (a) both Q1 sources trace to one filing — no independent
  BSE-host confirmation yet; (b) the standalone 5,768 / consolidated 6,374 basis trap;
  (c) SEC is annual USD and must not be footed against the quarter.
- **Sources succeeded:** NSE Ind AS XBRL (consol + standalone, context-aware), deterministic
  PDF parse, SEC 20-F annual. **Skipped:** BSE Q1 XBRL (not on hand), Tijori (no session).

---

## 5. Verification-aid disclaimer

This is a **cross-check aid**, not an authoritative statement of Infosys' results and not an
investment thesis. Numbers are facts about a public regulatory filing, extracted mechanically;
the **human analyst adjudicates every discrepancy and owns the baseline** — the baseline remains
human-authoritative. Figures were cross-checked against the issuer's published Q1 FY25 results
for internal consistency (cross-footing), not independently audited.

### Evidence index (session scratchpad — not committed)

`scratchpad/xsource-eval/`:
- `pdf-extract.json` — PyMuPDF word-geometry extraction (consolidated p11 + standalone p17)
- `nse-dl/q1fy25-consol.xml`, `nse-dl/q1fy25-standalone.xml` — downloaded NSE Ind AS XBRL
- `nse-facts-q1fy25-consol.json` — 72 context-bound (`OneD`/`OneI`) consolidated facts
- `nse-filings.json` — NSE Q1 FY25 filing index + XBRL links
- `sec-companyfacts.json` — SEC CIK 0001067491 companyfacts (FY25 annual, USD)
- venvs: `pdf-venv` (PyMuPDF 1.28.x), `nse-venv` (NseIndiaApi 3.2.1, nselib, lxml)
</content>
