# Lane B first measurement — 2026-09-04

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

## What this does not establish

A two-pair sample cannot give a base rate, and a low disagreement count does not
demonstrate sensitivity to real parser failures — the seeded-mutation step of
the graduation procedure is what would. Both remain open on `eqos-0j6`.
