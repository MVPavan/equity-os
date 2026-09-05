# Three-source first measurement (Phase 3, eqos-kx4.4)

Status: **Parts 1 and 2 measured 2026-09-05 — nine stocks, one quarter, one run each.** Every
registry tier is `EQUIVALENCE_UNPROVEN`, so no line below is a MISMATCH claim — a residual outside tolerance is reported as ANOMALY, which is what tier 3 is
entitled to say. Nine stocks and one quarter are a first look, not a base rate.

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

## Part 2 — Tijori side (retained `financials` captures)

Acquisition: the owner-approved manual `tijori-tables` run, 2026-09-05 11:30–11:33 UTC, ten
stocks sequential with 20 s spacing; every request answered 200 and was classified OK
(authenticated, identity verified) before parsing; 0 rate limits, 0 blocks, 0 retries. Ten
captures retained under `data/raw/snapshots/v1/tijori/financials/<slug>/` (gitignored, private,
A05-DECISION-005). The measurement replays the retained bodies — no fetch.

| Pair | Concept | AGREE | ANOMALY | MISSING | Note |
|---|---|---|---|---|---|
| XBRL ↔ Tijori | RevenueFromOperations / Net Sales | 8 | 1 | 0 | THERMAX 0.83 % — same direction and size as Screener |
| XBRL ↔ Tijori | ProfitBeforeTax / Profit Before Tax | 9 | 0 | 0 | |
| XBRL ↔ Tijori | ProfitLossForPeriod / Net Profit | 8 | 1 | 0 | LAURUSLABS 2.5 % |
| XBRL ↔ Tijori | EPS | 0 | 0 | 9 (MISSING_RIGHT) | Tijori parses no EPS row (alias-only registry entry) |
| Screener ↔ Tijori | Sales / Net Sales | 9 | 0 | 0 | |
| Screener ↔ Tijori | Profit before tax / Profit Before Tax | 9 | 0 | 0 | |
| Screener ↔ Tijori | Net Profit / Net Profit | 7 | 2 | 0 | HFCL 1.5 %, LAURUSLABS 2.6 % |

Tijori half-ULP is 0.5 crore by declaration (`decimals=-7`, scale 10^7) even though its values
carry two decimals; the tolerance on a Tijori pair is therefore 1 crore (vendor) or 0.5 crore +
the XBRL half-ULP. That is the declared precision, not a measured one, and it is generous: a
tighter declaration would turn some of the AGREEs above into sub-crore anomalies.

### Hand reading

- **THERMAX revenue.** Tijori and Screener agree with each other (within 0.3 crore) and both
  exceed filed `RevenueFromOperations` by about 21 crore. Two independent vendors landing on the
  same number says the difference is a definition (which filed line the vendors call revenue),
  not a vendor transcription defect. Unresolved; the registry `means` for both revenue entries
  should say "may include a line the filing reports separately" once the line is identified.
- **LAURUSLABS net profit.** Tijori shows a value about 2.3 crore below filed
  `ProfitLossForPeriod` and about 1.7 crore below owners-of-parent — it matches neither
  candidate. Unexplained; one stock.
- **HFCL net profit (Screener ↔ Tijori only).** Tijori is within the XBRL tolerance of
  `ProfitLossForPeriod` but Screener's integer crore rounds the other way, so the vendor pair
  reports 1.5 % while each vendor agrees with the filing. This is the integer-crore rounding
  floor of a vendor↔vendor pair, not a disagreement about the figure.

### Tijori net-profit candidate (OWNER 3, Tijori half)

Where the two XBRL candidates differ by more than the tolerance (HFCL, POLYCAB, THERMAX — and
LAURUSLABS, which matches neither), Tijori's `Net Profit` agrees with `ProfitLossForPeriod` on
HFCL, POLYCAB and THERMAX and with owners-of-parent on none. Same answer as Screener: both
vendors publish consolidated profit for the period including non-controlling interest. The
registry freeze (both vendor net-profit entries to the single candidate
`in-bse-fin:ProfitLossForPeriod`, `MAP_VERSION` bump) is bead **eqos-al0**.

### Summary across the three sources

Over the nine stocks, the 36 XBRL↔Screener pairs, 27 XBRL↔Tijori pairs and 27 Screener↔Tijori
pairs with both sides present: 32 + 25 + 25 = 82 AGREE, 4 + 2 + 2 = 8 ANOMALY, 0 MISMATCH (tier
3 cannot claim one), 0 STRUCTURAL triage. Every anomaly is under 15 % and six of eight are under
3 %. The two vendors never disagree with each other on revenue or PBT.
