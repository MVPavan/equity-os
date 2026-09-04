# Lane B measurement — 2026-09-04

Two runs, in order: a **replay** over two retained pairs that found two comparator
defects, then a **10-pair sweep** over fresh same-day captures from both vendors
that produced the first base rate — and falsified a tier-1 claim.

## Part 1 — replay (2 pairs, zero live requests)

The first end-to-end `upstox-crosscheck` run over real data from both vendors.
**Zero live requests**: the 2026-09-04 Upstox verification bodies and previously
retained Screener financial sections were replayed through the real command.

Two company/basis pairs had both sides available — TITAN consolidated and NETWEB
standalone. That is a small sample and it is stated as one; nothing here is a
graduation threshold. What it did do is find two defects in the comparator that
no synthetic fixture would have.

## Result

```
isin          symbol  basis         status    agree mismatch anomaly not_comparable unmet_tier3
INE280A01028  TITAN   standalone    SKIPPED_NO_SCREENER_DATA
INE280A01028  TITAN   consolidated  COMPARED     12        0       8             12           2
INE0NT901020  NETWEB  standalone    COMPARED     19        1       0             12           1
INE0NT901020  NETWEB  consolidated  SKIPPED_NO_SCREENER_DATA
```

Exit code 0, as decision A requires. 64 lines compared across 9 periods.

## The one MISMATCH localizes to Upstox, and two independent checks say so

NETWEB standalone, Mar 2025, `operating_profit`:

| Source | Value |
|---|---|
| Upstox summary block | 153.0 |
| Upstox `full_statement` → `Profit Before Tax` | 153.97 |
| Screener → `Profit before tax` | 154 |

The parse-time internal-consistency check had already flagged this line: the
summary block and the `full_statement` block **of the same HTTP response**
disagree by 0.97. The cross-vendor comparison then fires on the same line and
period — and Screener agrees with Upstox's *own* `full_statement`, not with its
summary.

**Earned diagnostic rule.** When a summary↔`full_statement` anomaly and a
Screener `MISMATCH` fire on the same category and period, the disagreement is
Upstox-side and the Screener parse is exonerated. Two checks with different
inputs converging is worth more than either alone, and this is the shape the
graduation procedure should look for when hand-labelling.

The same NETWEB response carries a second internal disagreement, `net_profit`
113.75 vs `Profit After Tax` 114.48 — but there Screener says 114, inside
tolerance of the summary's 113.75, so that line reads `AGREE`. One response, one
period, two contradictions, two different cross-vendor verdicts.

## Defect found: `total_liability` was mapped to a row that is not liabilities

**Screener's `Total Liabilities` row is the balancing total.** It equals
Screener's own `Total Assets` on every period of every company checked:

| Period | Screener Total Liabilities | Screener Total Assets |
|---|---|---|
| Mar 2026 | 60,561 | 60,561 |
| Mar 2025 | 40,645 | 40,645 |

Upstox's `total_liability` is liabilities **excluding** equity. Mapping it onto
the same-sounding Screener row produced a five-figure false `ANOMALY` on all
four TITAN periods — 15,703, 11,622, 9,390 and 11,901 crore — while the
underlying numbers agreed to the crore.

The correct mapping is `Borrowings + Other Liabilities`:

| Period | Upstox `total_liability` | Borrowings + Other Liabilities | Diff | (`total_asset` diff) |
|---|---|---|---|---|
| Mar 2026 | 44,858.0 | 44,858 | **0** | 0 |
| Mar 2025 | 29,023.0 | 29,021 | 2 | 2 |
| Mar 2024 | 22,157.0 | 22,154 | 3 | 3 |
| Mar 2023 | 15,119.0 | 15,169 | **−50** | 3 |

Mar-2025 and Mar-2024 are off by exactly the same amount as `total_asset`, so
that is a shared restatement offset rather than a mapping error. Mar-2023's −50
is a genuine difference, and tier 2 now reports it as an `ANOMALY` instead of
burying it among four fabricated ones. Anomalies across the run fell from 13 to
8.

This is the failure `screener_crosscheck`'s own docstring warns about —
*"a comparator built on matching names would report a false mismatch on every
company"* — reproduced by the module that warns about it. **Name similarity
between two vendors is not evidence of a mapping.** Every entry in the map now
has to be demonstrated on live data from both sides.

## Defect found: the comparator depended on parts of the Screener artifact it never reads

The first replay refused outright. `_load_screener_values` validated the whole
`SectionTable`, so a retained capture written before `ScheduleStrategy` and
`SubRowKind` became required fields made a log-only lane refuse rows it could
read perfectly well — 16 validation errors, none of them in a field any
comparison touches.

Lane B reads periods, row labels and cell values. It now validates exactly that
and nothing else, strictly. What is not read is not a dependency.

## Findings that are about the vendor, not the comparator

**The four Lane B surfaces are not period-aligned for the same company.** NETWEB
standalone: `income-statement` and `cash-flow` both carry Mar 2026;
`balance-sheet` stops at Mar 2025 and reaches back to Mar 2022 instead. Nine
comparison rows across two periods came back `MISSING_UPSTOX` for that reason
alone. Never assume one surface's period coverage from another's.

**Tier 3 hides the largest number in the run.** NETWEB Mar-2026 operating cash
flow reads 789.92 on Upstox against Screener's 171 — a 4.6× gap, while investing
(−216 both) and financing (240 both) agree exactly. Upstox is internally
consistent here: its `full_statement` "Cash flow from Operations" also says
789.92. Cash-flow equivalence was never demonstrated, so `NOT_COMPARABLE` is the
honest verdict and does not change — but counting only mismatches and anomalies
would have left the biggest disagreement in the run invisible in every summary.
`unmet_tier3` now counts tier-3 lines whose values differ beyond tolerance. It
claims nothing about them; it says which ones are worth a reviewer's time.

---

## Part 2 — the sweep (10 pairs, live)

Screener financials acquired the same day for all ten watchlist companies —
nine consolidated, NETWEB standalone (it publishes no consolidated statements) —
then compared against 60 live Upstox GETs, all HTTP 200, none rate-limited.
**344 lines compared across 10 company/basis pairs and 4 periods each.**

Screener captures are same-day on purpose. Comparing a fresh Upstox response
against a weeks-old Screener capture would fold refresh timing into every
difference, and refresh timing is one of the causes Lane B cannot distinguish.

### Outcome by mapped line

| Category | Tier | AGREE | MISMATCH | ANOMALY | NOT_COMPARABLE | MISSING_UPSTOX |
|---|---|---:|---:|---:|---:|---:|
| `revenue` | related | 21 | – | 19 | – | 3 |
| `operating_profit` | **demonstrated** | 37 | **3** | – | – | 3 |
| `net_profit` | **demonstrated** | 36 | **4** | – | – | 3 |
| `total_asset` | related | 23 | – | 17 | – | 3 |
| `total_liability` | related | 13 | – | 27 | – | 3 |
| `operating` | unproven | – | – | – | 40 | 3 |
| `investing` | unproven | – | – | – | 40 | 3 |
| `financing` | unproven | – | – | – | 40 | 3 |

**Tier-1 base rate: 7 mismatches in 80 compared lines — 8.75%.** That is the
number `eqos-0j6` was opened to obtain, and it is the number every warn/block
threshold has to be argued against.

### Every tier-1 mismatch, hand-labelled

Labelled by opening both vendors' own figures for that company and period, which
is step 5(a) of the graduation procedure.

| Company | Period | Line | Upstox | Screener | Diff | Class |
|---|---|---|---:|---:|---:|---|
| POLYCAB | Mar 2023 | `net_profit` | 1283.09 | 1282 | 1.09 | **U** |
| LAURUSLABS | Mar 2025 | `net_profit` | 354.41 | 358 | 3.59 | **D** |
| LAURUSLABS | Mar 2024 | `net_profit` | 168.21 | 162 | 6.21 | **D** |
| LAURUSLABS | Mar 2023 | `net_profit` | 796.64 | 793 | 3.64 | **D** |
| CGPOWER | Mar 2026 | `operating_profit` | 1626.23 | 1628 | 1.77 | **D** |
| CGPOWER | Mar 2024 | `operating_profit` | 1158.38 | 1715 | **556.62** | **D** |
| CGPOWER | Mar 2023 | `operating_profit` | 1002.14 | 1169 | 166.86 | **D** |

- **U — Upstox summary-block defect.** POLYCAB Mar-2023: Upstox's summary says
  1283.09, its own `full_statement` `Profit After Tax` says 1282.25, Screener
  says 1282. The internal-consistency check flagged it at parse time and the
  Screener comparison flagged it independently. The convergence rule fires.
- **D — definitional divergence, both vendors internally consistent.** See below.
- **P — our Screener parse read the page wrong: zero of seven.**

**The convergence rule is now mechanically applicable from the report alone.**
`CompanyCrosscheck.upstox_anomalies` carries the parse-time findings, so
matching a mismatch's category and period against them classifies POLYCAB
automatically and leaves six for a human. Before this the rule was earned but
unusable from the artifact.

### The important result: tier 1 is falsified

`operating_profit == Screener "Profit before tax"` was graded
`EQUIVALENCE_DEMONSTRATED` on the strength of an independence probe that held
12/12 across TITAN, HFCL and NETWEB. **CGPOWER breaks it on three of four
periods, by up to 556.62 crore.** And both vendors are internally consistent
while doing so:

| Mar 2024 | Screener | Upstox |
|---|---:|---:|
| Operating Profit | 1142 | – |
| Other Income | 684 | – |
| Interest / Depreciation | 17 / 95 | – |
| **Profit before tax** | **1715** | **1158.38** |
| Profit after tax | 1428 | 871.12 (`full_statement`) |
| Net profit (summary) | – | 1427.61 |

Screener's chain closes: 1142 + 684 − 17 − 95 = 1714 ≈ 1715, and 1715 taxed at
its stated 17% gives 1428. Upstox's `full_statement` chain also closes: 1158.38
→ 871.12. The two are internally coherent and land on different pre-tax
figures — a company with large exceptional items, where "profit before tax"
means two different things. Note that Upstox's *summary* `net_profit` (1427.61)
matches Screener's Net Profit (1428) while its own `full_statement` PAT does
not: a third inconsistency inside one response.

LAURUSLABS is the same class on the other line. Screener's `Profit before tax`
matches Upstox's to the crore in all four periods (1109/1108.94, 236/236.36,
484/484.29, 1182/1181.88) while `net_profit` differs in **both directions**
across years — the signature of associates or minority interest being placed
differently, not of a parse error.

**A demonstrated-equivalence claim built on three companies does not survive
ten.** The identity holds exactly for 73 of 80 lines and fails on companies with
exceptional items or material associates. The tier vocabulary has no conditional
tier, so the honest options are to demote both lines to
`RELATED_NOT_EQUIVALENT` — which empties tier 1 and makes `MISMATCH`
unreachable — or to keep tier 1 and state the exclusion explicitly. **This is an
owner decision and is recorded on `eqos-0j6` rather than taken here**, because
the plan's step 5(c) reserves per-field warn/block calls to the owner.

### Tier-2 magnitudes

Absolute differences are not comparable across companies, so these are stated
relative to the Upstox value.

| Line | Anomalies | Median | Max |
|---|---:|---:|---:|
| `total_asset` | 17 / 40 | 0.055% | 5.45% (THERMAX Mar-2025) |
| `revenue` | 19 / 40 | 0.146% | 7.09% (CGPOWER Mar-2024) |
| `total_liability` | 27 / 40 | 1.168% | 16.77% (SONACOMS Mar-2025) |

The medians are rounding-chain noise: Screener publishes integer crore, so a
tolerance of ~0.505 flags any true difference above half a crore, and on a
10,000-crore balance sheet that is 0.005%. **The absolute tolerance is correct
arithmetic and a poor triage signal at these magnitudes** — a relative figure
alongside it would separate the noise from CGPOWER's 7%.

**SONACOMS `total_liability` is off by a near-constant 149.3 crore across all
three periods** (149.64 / 149.19 / 149.30). A constant offset across periods of
very different size is the signature of a whole item sitting on one side and
not the other — most likely a fixed instrument that Screener carries in
`Other Liabilities` and Upstox counts as equity. It is a genuine reconstruction
gap, correctly reported at tier 2, and it should not be tuned away.

CGPOWER's `revenue` gap (577.76 on Mar-2024) is the same exceptional-items story
as its `operating_profit` mismatch, arriving on a different line.

### Coverage gaps

`MISSING_UPSTOX` on 8 lines each for HFCL, MTARTECH and NETWEB — in every case
because the Upstox `balance-sheet` surface covers different years than that same
company's `income-statement` and `cash-flow`. Confirms the Part 1 finding at
scale: **the four Lane B surfaces are not period-aligned per company.**

### What the sweep still does not establish

A base rate is not sensitivity. Seven mismatches in eighty says how often the
two vendors disagree; it says nothing about whether Lane B would *notice* a real
Screener parser defect, and zero of the seven were parser defects. Step 5(b) —
seeding known parser mutations and measuring detection — is the only thing that
answers that, and it is not done. Until it is, a quiet report and a blind report
look the same.
