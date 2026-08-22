# Wave-1 Multi-Stock Validation — Roll-up

**Date:** 2026-08-22 · **Quarter:** Q3FY25 (2024-10-01 … 2024-12-31), consolidated, Ind AS ·
**Sources:** NSE Ind AS XBRL (first-party) · BSE issuer results PDF (first-party) ·
Screener (derived cross-check). Values in ₹ crore (EPS in ₹/share).

Machine reports (`*-Q3FY25.json`, full provenance) are gitignored (large, regeneratable);
regenerate with:

```
uv run fundamentals validate --watchlist --sources nse,pdf,screener --live \
  --report-dir docs/research/validation --gold-dir data/gold
```

## Why this quarter, why these sources

The two first-party **hosts** sit on different live-data frontiers: NSE's API serves through
**Q3FY25 (Dec-24)**; BSE `resultsSnapshot` exposes only the **latest ~2 quarters** (Mar/Jun-26).
They do not overlap, so same-quarter NSE+BSE-summary cross-check is impossible. The independent
second first-party source is therefore the **issuer results PDF** fetched from BSE announcements
(the Infosys-oracle design: structured XBRL cross-checked against the company's own signed
statement). Screener is a derived aggregator — cross-check only, never source-of-record.

## Outcome per stock

| Stock | Domain | AGREE (2 first-party) | Outcome | Note |
|---|---|---|---|---|
| **MTARTECH** | Precision Eng. | **5 / 5** | **DONE** | full cross-source agreement |
| **SONACOMS** | Auto Ancillary | **5 / 5** | needs_adjudication | all facts AGREE; held only by a pre-existing NSE cross-foot residual (associate/exceptional items), not the PDF |
| **LAURUSLABS** | CDMO / Pharma | 4 / 5 | needs_adjudication | PFP: PDF prints pre- and post-associate profit lines; no general label isolates the post-associate line → fail-closed |
| **TITAN** | Jewellery / Retail | 3 / 5 | needs_adjudication | Revenue printed as split header (no single total line); EPS current-quarter cell OCR-corrupted (`ll.80`) → both fail-closed |
| **THERMAX** | Power Infra | 0 / 5 | needs_adjudication | consolidated P&L text layer OCR-garbled (`Consolidut<-d`, `Rc,·cnue`) → PDF SKIPPED fail-closed; NSE facts intact |

**17 / 25 material concepts** reached two-first-party AGREE. Every non-AGREE is a *reported
fail-closed* (ambiguous or OCR-corrupt source), never a fabricated or silently-dropped number.

## Per-concept matrix (NSE-XBRL vs BSE-PDF vs Screener)

| Stock | Concept | Status | NSE | BSE-PDF | Screener |
|---|---|---|---:|---:|---:|
| LAURUSLABS | RevenueFromOperations | AGREE | 1415.05 | 1415.05 | 1415 |
| LAURUSLABS | Income | AGREE | 1424.47 | 1424.47 | — |
| LAURUSLABS | ProfitBeforeTax | AGREE | 130.68 | 130.68 | — |
| LAURUSLABS | ProfitLossForPeriod | single | 92.94 | — | 93 |
| LAURUSLABS | BasicEPS | AGREE | 1.71 | 1.71 | 1.71 |
| MTARTECH | RevenueFromOperations | AGREE | 174.455 | 174.455 | 174 |
| MTARTECH | Income | AGREE | 177.604 | 177.604 | — |
| MTARTECH | ProfitBeforeTax | AGREE | 21.432 | 21.432 | — |
| MTARTECH | ProfitLossForPeriod | AGREE | 15.964 | 15.964 | 16 |
| MTARTECH | BasicEPS | AGREE | 5.19 | 5.19 | 5.19 |
| SONACOMS | RevenueFromOperations | AGREE | 867.967 | 867.907 | 868 |
| SONACOMS | Income | AGREE | 914.758 | 914.758 | — |
| SONACOMS | ProfitBeforeTax | AGREE | 203.001 | 203.001 | — |
| SONACOMS | ProfitLossForPeriod | AGREE | 150.713 | 150.713 | 151 |
| SONACOMS | BasicEPS | AGREE | 2.43 | 2.43 | 2.43 |
| THERMAX | RevenueFromOperations | single | 2507.76 | — | 2529 |
| THERMAX | Income | single | 2539.27 | — | — |
| THERMAX | ProfitBeforeTax | single | 156.77 | — | — |
| THERMAX | ProfitLossForPeriod | single | 113.73 | — | 114 |
| THERMAX | BasicEPS | single | 10.29 | — | 9.73 |
| TITAN | RevenueFromOperations | single | 17740.00 | — | 17740 |
| TITAN | Income | AGREE | 17868.00 | 17868 | — |
| TITAN | ProfitBeforeTax | AGREE | 1396.00 | 1396 | — |
| TITAN | ProfitLossForPeriod | AGREE | 1047.28 | 1047 | 1047 |
| TITAN | BasicEPS | single | 11.80 | — | 11.79 |

Income and ProfitBeforeTax carry no Screener column because Screener does not publish those
lines; where two first-party sources (NSE + PDF) agree, the fact is AGREE regardless.

## Generalization gaps found by the multi-stock run (the point of the exercise)

Validating beyond Infosys surfaced and fixed real single-stock-bias defects:

1. **YTD-period defect** — filers stamp the year-to-date XBRL context's `xbrli:period` with the
   *quarter's* dates; quarter and YTD shared one comparison key and every NSE fact was dropped.
   Fixed by re-periodising from the taxonomy's authoritative `DateOf*OfReportingPeriod` facts.
   (commit `c65b24b`)
2. **Derived-source basis wildcard** — Screener's `accounting_basis=UNKNOWN` was treated as
   incompatible with `IND_AS`, blocking all corroboration. Now a wildcard (IFRS-vs-IndAS guard
   intact). (commit `c65b24b`)
3. **PDF extractor overfit to Infosys** — generalized to SEBI Reg-33 layouts: consolidated-scope
   page finder, current-quarter column by printed date (3-month vs 9-month), glyph-independent
   unit detection, serial-column-proof labels, per-concept partial extraction. (commit `235e971`)

## Residual (not defects in this lane)

- **THERMAX / TITAN-EPS / LAURUS-PFP** fail-closed on OCR-garbled or structurally-ambiguous PDF
  text layers. Closing these needs a scanned-page vision lane or a cleaner PDF source, not
  looser matching (which would risk asserting the wrong line).
- **SONACOMS** cross-foot residual (−5.70 cr) is a pre-existing NSE identity limitation
  (associate/exceptional items), independent of the PDF lane; all 5 SONACOMS facts AGREE.
- **THERMAX / TITAN-Revenue / TITAN-EPS** Screener values genuinely differ (line-item
  restatement, diluted-vs-basic EPS) and correctly do **not** corroborate — fail-closed working.
