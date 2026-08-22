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

## Outcome per stock (with the deterministic + local-OCR recovery lanes)

| Stock | Domain | AGREE (2 first-party) | Outcome | Note |
|---|---|---|---|---|
| **MTARTECH** | Precision Eng. | **5 / 5** | **DONE** | full cross-source agreement |
| **LAURUSLABS** | CDMO / Pharma | **5 / 5** | **DONE** | PFP recovered via a conditional post-associate label |
| **TITAN** | Jewellery / Retail | **5 / 5** | **DONE** | Revenue recovered via arithmetic-validated sub-component sum; EPS (`ll.80`) recovered via local OCR |
| **THERMAX** | Power Infra | **5 / 5** | **DONE** | garbled consolidated P&L recovered via local OCR (Income/PBT/PFP/EPS); Revenue derived from the statement's own identity (Total income − Other income = 2507.76) when its label was OCR-corrupt |
| **SONACOMS** | Auto Ancillary | **5 / 5** | needs_adjudication | all facts AGREE; held only by a pre-existing NSE cross-foot residual (associate/exceptional items), not the PDF |

**25 / 25 material concepts** reached two-first-party AGREE (up from 17/25 before the recovery
lanes). Every value is cross-verified across two independent first-party hosts — no fabricated
or silently-dropped number. **Four stocks are fully DONE**; SONACOMS is AGREE on all five facts
and needs adjudication only for a pre-existing NSE cross-foot residual.

## Per-concept matrix (NSE-XBRL vs BSE-PDF vs Screener)

| Stock | Concept | Status | NSE | BSE-PDF | Screener |
|---|---|---|---:|---:|---:|
| LAURUSLABS | RevenueFromOperations | AGREE | 1415.05 | 1415.05 | 1415 |
| LAURUSLABS | Income | AGREE | 1424.47 | 1424.47 | — |
| LAURUSLABS | ProfitBeforeTax | AGREE | 130.68 | 130.68 | — |
| LAURUSLABS | ProfitLossForPeriod | AGREE | 92.94 | 92.94 | 93 |
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
| THERMAX | RevenueFromOperations | AGREE (derived) | 2507.76 | 2507.76 | 2529 |
| THERMAX | Income | AGREE (OCR) | 2539.27 | 2539.27 | — |
| THERMAX | ProfitBeforeTax | AGREE (OCR) | 156.77 | 156.77 | — |
| THERMAX | ProfitLossForPeriod | AGREE (OCR) | 113.73 | 113.73 | 114 |
| THERMAX | BasicEPS | AGREE (OCR) | 10.29 | 10.29 | 9.73 |
| TITAN | RevenueFromOperations | AGREE | 17740.00 | 17740 | 17740 |
| TITAN | Income | AGREE | 17868.00 | 17868 | — |
| TITAN | ProfitBeforeTax | AGREE | 1396.00 | 1396 | — |
| TITAN | ProfitLossForPeriod | AGREE | 1047.28 | 1047 | 1047 |
| TITAN | BasicEPS | AGREE (OCR) | 11.80 | 11.80 | 11.79 |

`AGREE (OCR)` = the BSE-PDF value was recovered from a corrupt text layer via the local OCR
lane (rapidocr, on-CPU, deterministic), then reconciled normally against NSE. Income and
ProfitBeforeTax carry no Screener column because Screener does not publish those lines; where
two first-party sources (NSE + PDF) agree, the fact is AGREE regardless.

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

## Recovery lanes (added after the first pass)

- **LAURUS PFP** — recovered deterministically: a conditional label binds the post-associate
  "Net profit after … associates" line (92.94), never the pre-associate line.
- **TITAN Revenue** — recovered deterministically: sum of dash-led sub-components, accepted only
  when the statement's own arithmetic validates (sum + other income == total income).
- **TITAN EPS, THERMAX Income/PBT/PFP/EPS** — recovered via the local OCR lane (per-cell 0.80
  confidence floor + page-level self-cross-foot gate; never gated on the NSE value).
- **THERMAX Revenue** — its label OCR'd as `Revenuc` (unmatchable), so the value is DERIVED from
  the statement's own identity: Total income − Other income = 2539.27 − 31.51 = 2507.76, carrying
  a computed trace and both contributing anchors. Fires only when the revenue label is entirely
  unreadable; a present-but-non-reconciling split still fails closed.

## Residual (still open, correctly fail-closed)

- **SONACOMS** cross-foot residual (−5.70 cr) is a pre-existing NSE identity limitation
  (associate/exceptional items), independent of the PDF lane; all 5 SONACOMS facts AGREE.
- Screener values for a few lines genuinely differ (line-item restatement, diluted-vs-basic
  EPS) and correctly do **not** corroborate — fail-closed working as intended.
