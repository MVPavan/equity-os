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
tier, so the choice was to demote both lines to `RELATED_NOT_EQUIVALENT` — which
empties tier 1 and makes `MISMATCH` unreachable — or to keep tier 1 and state
the exclusion explicitly.

**Owner decision, 2026-09-04 (PavanMV): keep tier 1, state the exclusion.** The
reasoning that decides it is what demotion would cost: with tier 1 empty, the
POLYCAB Mar-2023 finding — a real Upstox summary-block defect, the one class
where Lane B gives a clean answer — would arrive as one `ANOMALY` among 62,
indistinguishable from the rounding noise that dominates tier 2.

The cost of keeping it is that the enum member alone over-claims. Two things
carry the correction instead:

* each mapping's `means` now names its exclusion, the company it failed on and
  the size of the failure — and `means` travels into every report row, which is
  where a reader actually looks;
* `EvidenceTier`'s own docstring says a tier is not self-sufficient and that
  `EQUIVALENCE_DEMONSTRATED` may carry a stated exclusion.

`test_screener_crosscheck.py::TestTierOneCarriesItsMeasuredExclusion` fails if
an edit ever drops an exclusion while leaving the tier at 1, so the over-claim
cannot silently return.

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
answers that. Part 3 below is that measurement.

---

## Part 3 — sensitivity (9 seeded mutation classes, offline replay)

Step 5(b) of the graduation procedure. `upstox-crosscheck-sensitivity` seeds a
parser-defect-shaped mutation into one row of one retained Screener section,
re-runs the real comparator against the retained Upstox bodies of the same
sweep, and records whether the verdict changed. **Zero live requests**: the
27 bodies retained by the Part 2 sweep replay through `--upstox-root`, and that
replay reproduces the sweep's counts exactly (111 AGREE / 7 MISMATCH / 62
ANOMALY / 108 NOT_COMPARABLE / 16 MISSING_UPSTOX) before any mutation is applied.

Nine companies, consolidated basis (NETWEB publishes no consolidated statements
and is skipped, not silently absent). Every row of every compared section is
mutated — 25,416 cells classified — and each cell is one of:

| Class | Meaning |
|---|---|
| `DETECTED` | baseline `AGREE`, mutated verdict `MISMATCH`, `ANOMALY` or `MISSING_SCREENER` |
| `UNDETECTED` | baseline `AGREE`, still `AGREE` after the mutation |
| `MASKED` | baseline already disagreed, so the mutation changes nothing observable |
| `BLIND_TIER3` / `BLIND_UNMAPPED` | tier-3 row (always `NOT_COMPARABLE`) / row Lane B never reads |
| `BLIND_NO_UPSTOX` | Screener period Upstox carries no report for |
| `NOT_APPLICABLE` | the class cannot alter this cell (see below) |

`sensitivity = DETECTED / (DETECTED + UNDETECTED)`. Everything else is reported
beside the ratio and kept out of the denominator.

### Result

| Mutation | Tier 1 (demonstrated) | Tier 2 (related) |
|---|---:|---:|
| `DROP_ROW` | 65 / 0 → **1.000** | 72 / 0 → **1.000** |
| `COLUMN_SHIFT` | 65 / 0 → **1.000** | 70 / 2 → 0.972 |
| `SIGN_FLIP` | 65 / 0 → **1.000** | 72 / 0 → **1.000** |
| `SCALE_10` | 65 / 0 → **1.000** | 72 / 0 → **1.000** |
| `SCALE_100` | 65 / 0 → **1.000** | 72 / 0 → **1.000** |
| `THOUSANDS_TRUNCATED` | 65 / 0 → **1.000** | 72 / 0 → **1.000** |
| `ROW_SWAP` | 65 / 0 → **1.000** | 43 / 9 → 0.827 |
| `UNIT_DRIFT` (+1 crore) | 65 / 0 → **1.000** | 36 / 36 → **0.500** |
| `STALE_PERIOD` | 17 / 0 → **1.000** | 13 / 0 → **1.000** |
| **All** | | **1059 / 47 → 0.9575** |

Cells are detected / undetected. Tier 1 also carries 7 `MASKED` cells per class
— exactly the seven hand-labelled mismatches of Part 2 (LAURUSLABS ×3, POLYCAB,
CGPOWER ×3): a defect seeded on a line that already disagrees is invisible,
which is a property of the base rate, not of the harness. Tier 3 is blind by
construction (291 cells per class) and stays so.

**Every one of the 47 undetected cells is on tier 2, and all 47 have one cause:
the tolerance of a reconstruction mapping.**

### Coverage — the number that matters more than the ratio

| Section | Mapped rows / all rows | Periods with an Upstox report / periods on the page |
|---|---:|---:|
| profit-loss | 36 / 108 = 0.333 | 38 / 106 = 0.358 |
| balance-sheet | 27 / 90 = 0.300 | 38 / 97 = 0.392 |
| cash-flow | 27 / 54 = 0.500 (all tier 3) | 38 / 97 = 0.392 |

Lane B reads 10 of the rows Screener publishes and about four of its twelve or
thirteen columns. A sensitivity of 0.96 is a statement about those cells only:
**a parser defect confined to an unmapped row, an older year or the TTM column
is invisible to this lane, and no threshold chosen in step 5(c) can change
that.** `BLIND_UNMAPPED` (1,818 cells per class) and `BLIND_NO_UPSTOX` are the
two largest buckets in the run.

### The undetected cases, each with its cause

**`UNIT_DRIFT` +1 crore, 36 tier-2 misses (M3).** `revenue` and
`total_liability` are two-addend reconstructions (`Sales + Other Income`,
`Borrowings + Other Liabilities`). Screener publishes integer crore, so the
tolerance is the sum of both addends' half-ULPs plus Upstox's: ≈1.005. A
+1 shift on one addend sits inside it whenever the baseline gap is under 0.005.
The 36 detections on the same class are the cells whose baseline already sat
near the edge. `Total Assets` is a single-row mapping (tolerance ≈0.505) and
catches +1 on all 20 cells. **A two-addend tolerance is one crore wide, and
one crore is exactly the drift a mis-read thousands separator or a stale cell
produces.** This is the tolerance finding step 5(c) has to price.

**`COLUMN_SHIFT`, 2 tier-2 misses — the same finding.** MTARTECH `Other Income`
Mar-2025 took Mar-2024's value: 6 for 5. CGPOWER `Borrowings` Mar-2024 took
Mar-2023's: 16 for 17. Both shifts are ±1 on an addend of a two-addend sum.

**`ROW_SWAP`, 9 tier-2 misses (M5).** All nine are `Borrowings`, and
`Borrowings` is *never* detected under this class — 0 detected, 9 undetected,
27 masked. Its next row on every Screener balance sheet is `Other Liabilities`,
the other addend of the same `total_liability` reconstruction. **A sum is
blind to a swap of its own addends.** Swapping `Other Liabilities` with the row
below it (the balancing total) is caught 9 of 9 times.

### Two false lows the harness itself produced before it measured anything

The first run reported overall sensitivity **0.19** and tier-1 **0.28**; the
final number is 0.96. Nothing in the comparator changed between them. Both
gaps were the harness charging the comparator for cells nobody could detect:

1. **Periods Upstox does not carry (M1).** Screener pages carry 12–13 columns;
   Upstox answers for 4–5. The first run classified a mutation on Mar-2016 as
   `UNDETECTED`. 136 of the 140 tier-1 "misses" had no Upstox report for the
   period at all; the other 4 were `MISSING_UPSTOX`. Now `BLIND_NO_UPSTOX`,
   reported as period coverage.
2. **Cells a row-scoped mutation never touched (M4).** `STALE_PERIOD` re-keys
   one cell per row, but the run classified every period of the row — three
   untouched cells per detection, read as 17 / 48 → 0.26. Applicability is now
   per cell (`touched()`), and the class reads 17 / 0.

`STALE_PERIOD` also read **0 of 600** in the first run for a third reason (M2):
it targeted the oldest column (index 0 on a real page) and, for profit-loss,
the TTM column Upstox never carries. It now targets the newest period *this
mapping* was actually scored in. Three separate ways for a mutation class to
report a zero that means "the harness never fired" rather than "the comparator
is blind" — each one indistinguishable from a real result in the summary line.

### What this establishes, and what it does not

- **Established:** on the cells Lane B reads, the comparator notices every
  seeded value defect on tier 1 and every non-tolerance defect on tier 2. A
  quiet tier-1 report is not a blind one.
- **Established:** the two-addend tolerance is the only detection floor found,
  and it is ≈1 crore. `unmet_tier3` and the row-level JSON are where
  `MISSING_SCREENER` detections appear; the summary line does not count them.
- **Not established:** anything about the 67–70% of rows and 61–64% of columns
  Lane B never reads. Coverage, not sensitivity, is the bound on what this
  lane can promise.
- **Not established:** sensitivity on standalone statements (NETWEB and any
  standalone-only issuer) — this run is consolidated only.

Artifacts: `scratchpad/laneb-5b/sensitivity-2/laneb_sensitivity_report.json`
(local, not committed — it embeds retained subscriber values); the harness is
`fundamentals upstox-crosscheck-sensitivity`.

---

## Part 4 — triage: what warns, what is listed, what stays quiet

Step 5(c). With a base rate (Part 2) and a sensitivity (Part 3) in hand, the
per-field decision was made on 2026-09-04 by the owner (PavanMV) and is carried
in `config/laneb_triage.yaml`, each entry with its reason and the measurement
it came from. `upstox-crosscheck` now classifies every compared line and writes
a `warnings.tsv` beside its report. **Decision A stands: the exit code is 0
whatever is found.** `--warn-exit` is opt-in for an operator's manual run.

### The evidence the thresholds rest on

| | Vendor disagreements (Part 2, 69 lines) | Seeded parser defects (Part 3) |
|---|---|---|
| ≤ 5 % relative | 59 | `UNIT_DRIFT` only |
| ≤ 20 % relative | 68 | about half of `COLUMN_SHIFT` (it equals year-on-year growth, median 21 %) |
| > 20 % relative | 1 (CGPOWER Mar-2024, acknowledged) | `SCALE_10` 90 %, `SCALE_100` 99 %, `SIGN_FLIP` 200 %, `THOUSANDS_TRUNCATED` ≈ 100 %, the other half of `COLUMN_SHIFT` |
| line missing from Screener | 0 | `DROP_ROW`, `STALE_PERIOD` |

Persistence across periods does *not* separate the two: definitional gaps
persist (9 company-lines at 4 of 4 periods, 7 at 3 of 4) exactly as a parser
defect would. Whole-table breadth does, but only with a magnitude floor — both
balance-sheet categories disagree in 13 of 36 periods from rounding noise alone.

### The classes

| Class | Rule | Action |
|---|---|---|
| `STRUCTURAL` | a mapped line is missing from Screener | **warn** |
| `MAGNITUDE` | relative difference ≥ 0.20 on a tier-1 or tier-2 line | **warn** |
| `WHOLE_TABLE` | every mapped category of a section disagrees in one period and at least one is `MAGNITUDE` or `STRUCTURAL` | **warn** |
| `UPSTOX_SIDE` | an Upstox summary-vs-`full_statement` contradiction on the same line and period, **and** Screener within tolerance of the `full_statement` figure | listed, never warns |
| `ACKNOWLEDGED` | a (company, line) pair the owner has labelled definitional, with a reason | listed, never warns, **never suppressed** |
| `NOISE` | any other disagreement | logged only |

No class blocks. Zero parser defects were observed in 344 live lines, and Lane
B reads 30–50 % of rows and about 36–39 % of periods; a gate that fires only on
synthetic evidence is switched off the first time it fires for real.

### Result on the sweep

Replayed over the same nine consolidated pairs and retained bodies:

```
warn 0   listed 7   noise 62   none 235
```

| Company | Period | Line | Upstox | Screener | Rel. | Class |
|---|---|---|---:|---:|---:|---|
| POLYCAB | Mar 2023 | `net_profit` | 1283.09 | 1282 | 0.08 % | `UPSTOX_SIDE` |
| CGPOWER | Mar 2023 / 2024 / 2026 | `operating_profit` | | | 14.3 / 32.5 / 0.1 % | `ACKNOWLEDGED` |
| LAURUSLABS | Mar 2023 / 2024 / 2025 | `net_profit` | | | 0.5 / 3.7 / 1.0 % | `ACKNOWLEDGED` |

The queue is exactly the seven hand-labelled mismatches of Part 2, each carrying
the label Part 2 gave it, with nothing added and nothing hidden. A parser
defect of the shapes Part 3 seeded would appear above them as `STRUCTURAL` or
`MAGNITUDE`.

### The convergence rule needed its second half

The first replay listed THERMAX `revenue` Mar-2025 and Mar-2026 as
`UPSTOX_SIDE`: Upstox's summary (10,961.63) contradicts its own
`full_statement` (11,041.49) on that line. But Screener says 11,091 — about 50
crore from *both* Upstox figures. The contradiction is real and it exonerates
nothing, because the rule Part 1 earned has two halves: an internal Upstox
contradiction **and Screener agreeing with Upstox's own `full_statement`**. As
first built, the rule fired on the first half alone. It now requires
`|Screener − full_statement| ≤ tolerance`; POLYCAB (0.25 crore) keeps its
alibi and THERMAX falls to `NOISE`.

### Known limits

- **Bank-format pages.** Screener's bank statements carry `Revenue` and
  `Deposits` where the name map expects `Sales` and `Borrowings`, so every bank
  period would read `STRUCTURAL`. No bank is in the sweep; adding one needs a
  mapping first, not an acknowledgement.
- **A typo'd config refuses, it does not degrade.** `acknowledgements:` for
  `acknowledged:` is rejected outright; the alternative was CGPOWER's 32 %
  silently becoming a warn nobody expected.
- **Review owner:** PavanMV, on each manual run. Automation stays restricted.
