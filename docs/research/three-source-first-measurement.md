# Three-source first measurement (Phase 3, eqos-kx4.4)

Status: **Part 1 measured 2026-09-05 — XBRL ↔ Screener only, nine stocks.** Part 2 (Tijori side)
is appended once the owner-approved manual `tijori-tables` acquisition has run. This is an
explicitly partial measurement: it cannot substantiate a three-source base rate, every registry
tier is `EQUIVALENCE_UNPROVEN`, and therefore no line below is a MISMATCH claim — a residual
outside tolerance is reported as ANOMALY, which is what tier 3 is entitled to say.

Command: `fundamentals three-source-crosscheck --stock <SYM> --out-dir <dir>` (offline; gold
spine from `data/gold/<SYM>-Q3FY25.json`, Screener sections from
`data/raw/watchlist/screener-financials/<SYM>/consolidated/`, no Tijori capture present).
Stocks: CGPOWER, ETERNAL, HFCL, LAURUSLABS, MTARTECH, POLYCAB, SONACOMS, THERMAX, TITAN
(NETWEB has no gold file). Quarter: Q3FY25, period end 2024-12-31. Registry `MAP_VERSION
2026-09-05.1`. Tolerance per pair = XBRL half-ULP (from the fact's `decimals`/scale) + Screener
half-ULP (0.5 crore for integer-crore rows; 0.005 for two-decimal EPS).

## Part 1 — XBRL ↔ Screener (quarters table)

| Concept (in-bse-fin) | Screener row | AGREE | ANOMALY | MISSING | Note |
|---|---|---|---|---|---|
| RevenueFromOperations | Sales | 8 | 1 | 0 | THERMAX: relative difference 0.84 % |
| ProfitBeforeTax | Profit before tax | 9 | 0 | 0 | |
| ProfitLossForPeriod | Net Profit | 9 | 0 | 0 | see candidate decision below |
| ProfitOrLossAttributableToOwnersOfParent | Net Profit | 0 | 0 | 9 (MISSING_LEFT) | auxiliary concept, absent from gold by design |
| BasicEarningsLossPerShare… | EPS in Rs | 6 | 3 | 0 | ETERNAL 14.3 %, THERMAX 5.4 %, TITAN 0.08 % |
| Income | — | 0 | 0 | 9 (MISSING_RIGHT) | no Screener row is mapped to total income |

Totals over the 36 XBRL↔Screener pairs where both sides were present: 32 AGREE, 4 ANOMALY (all
triage NOISE, none STRUCTURAL: no sign flip, no ×10/×100/×1000 ratio). Every run exited 0;
`--warn-exit` would have exited 1 on ETERNAL, THERMAX and TITAN.

### What the anomalies are (hand read, not a claim)

- **EPS (3 of 9).** Screener's quarterly EPS is not the filed basic EPS on three stocks. TITAN
  differs by one paisa (11.80 filed vs 11.79 shown), THERMAX by 5.4 %, ETERNAL by one paisa on a
  seven-paise number. The pattern (Screener lower in all three) is consistent with Screener
  deriving EPS from net profit and a share count rather than reproducing the filed figure, but
  that is an inference from three cases, not a verified rule. The mapping stays tier 3.
- **Revenue (THERMAX, 0.84 %).** Screener's Sales exceeds filed RevenueFromOperations by about
  21 crore on a 2,508-crore line. Not investigated further in this pass; it is one stock, and
  the other eight agree within one crore. Tier stays 3.

### Net-profit candidate decision (OWNER 3 — decided by replay)

Registry entry `screener.quarters.net_profit` listed two XBRL candidates. The replay
discriminates: Screener's **Net Profit equals `ProfitLossForPeriod`** (consolidated profit
including non-controlling interest) on 9 of 9 stocks within the summed half-ULP. Reading the
retained XBRL for the auxiliary concept, four stocks separate the candidates by more than the
rounding tolerance — HFCL (owners 73.65 vs period 72.58 crore; Screener shows 73), LAURUSLABS
(92.30 vs 92.94; Screener 93), POLYCAB (457.56 vs 464.35; Screener 464) and THERMAX (115.90 vs
113.73; Screener 114) — and every one of them matches `ProfitLossForPeriod`, none matches
owners-of-parent. CGPOWER's owners-of-parent tag in the retained file carries a negative
20.5-crore value against a 237.9-crore period profit, which looks like a tagging quirk in the
filing rather than a candidate; it was not used.

Consequence: the Screener net-profit mapping can be frozen to the single candidate
`in-bse-fin:ProfitLossForPeriod`. The Tijori `Net Profit` row keeps both candidates until
Part 2 measures it. The registry freeze is deliberately NOT done in this commit so the
Screener and Tijori decisions land together (follow-up bead filed).

### Defect found by the replay

The first run reported `RevenueFromOperations` and `ProfitLossForPeriod` as MISSING on all
nine stocks. Cause: the Screener reader treated a row carrying `schedule_parent` as a schedule
sub-row and skipped it, but on the live page `schedule_parent` is the name a page row's own
expander requests — Sales, Net Profit and Expenses all carry one, and sub-rows live under
`schedules`, never in `rows`. The synthetic fixtures had no expanders, so the gate could not
see it. Fixed in `verify/three_source_inputs.py` with a regression test that gives the
fixture the live shape (`test_expander_rows_are_page_rows`). The second run produced the
table above.

## Part 2 — Tijori side

Pending the manual acquisition (sequential, spaced, stop on the first rate limit or block).
