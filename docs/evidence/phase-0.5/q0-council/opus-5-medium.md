# Q0 bootstrap investment thesis — Apar Industries Limited (NSE `APARINDS`, BSE 532259)

As of 2025-11-06. Basis quarter: Q2 FY26, ended 2025-09-30. Consolidated, Ind AS, INR crore.

## Stance

Constructive on Apar's demand trajectory, deliberately unconvinced on its earnings trajectory:
Q2 FY26 is a volume print (revenue +23.1% YoY) whose profit did not follow sequentially
(PBT -3.4% QoQ, PAT -4.3% QoQ) because expenses outgrew revenue (+13.1% vs +12.0%). I claim this
is input-cost/mix noise inside a structurally thin-margin converter, not the start of margin
decay — topline keeps compounding at better than half the observed YoY rate while PBT margin
holds inside the 5.53%-6.91% corridor the three known quarters trace. The thesis is wrong in the
way that matters if margin breaks that floor while revenue keeps growing.

## Assumptions

- `[FACT]` Q2 FY26: revenue 5,715.42; total income 5,742.85; total expenses 5,402.29; PBT 340.56;
  PAT 251.70; EPS 62.66. Every YoY line is strongly positive (revenue +23.1%, PBT +32.7%,
  PAT +29.8%) while both profit lines fell QoQ on a +12.0% QoQ revenue increase.
- `[FACT]` Expense-to-revenue worsened sequentially but improved year on year:
  5,402.29/5,715.42 = 94.52% (Q2 FY26); 4,776.44/5,104.16 = 93.58% (Q1 FY26);
  4,420.59/4,644.51 = 95.18% (Q2 FY25).
- `[FACT]` PBT margin: 5.96% / 352.51 ÷ 5,104.16 = 6.906% / 256.70 ÷ 4,644.51 = 5.527%.
  PAT margin: 4.40% / 262.91 ÷ 5,104.16 = 5.151% / 193.88 ÷ 4,644.51 = 4.174%
  (Q2 FY26 / Q1 FY26 / Q2 FY25).
- `[FACT]` Effective tax rate drifts up across the three computable quarters:
  62.82/256.70 = 24.47% (Q2 FY25); 89.60/352.51 = 25.42% (Q1 FY26); 88.86/340.56 = 26.09%
  (Q2 FY26).
- `[FACT]` Non-operating income is immaterial to the margin story: 27.43/5,715.42 = 0.48% of
  revenue, vs 24.79/5,104.16 = 0.49% and 32.78/4,644.51 = 0.71%. So PBT margin on revenue is a
  near-clean read on operating cost discipline.
- `[INFERENCE]` No meaningful equity dilution over the past year: EPS YoY (+29.8%) equals PAT YoY
  (+29.8%) and EPS QoQ (-4.3%) equals PAT QoQ (-4.3%) to the stated precision.
- `[INFERENCE]` The QoQ compression is cost/mix, not tax: ETR moved 25.42% -> 26.09% (+0.67pp)
  while PBT margin fell 6.906% -> 5.96% (-0.95pp).
- `[SPECULATION]` As a commodity-input converter, pass-through lags produce roughly ±1pp PBT
  margin swings per quarter that mean-revert; the right run-rate anchor is H1 FY26,
  5,104.16 + 5,715.42 = 10,819.58, not either quarter alone.
- `[SPECULATION]` Two priors per line item cannot identify seasonality, so a purely sequential
  percentage falsifier would confuse seasonality with deterioration.

## Falsifiers

Each predicate is over exactly one registered metric for the observed quarter; TRUE = thesis
weakened.

**F1 — Growth stalls.** Revenue YoY growth halves from the observed rate, breaking the
durable-demand leg.
`revenue_yoy_pct` / `LT` / `11.55` — half of the observed 23.1% (23.1 / 2 = 11.55).

**F2 — Absolute topline regression.** Revenue falls back below the level of two quarters
earlier, erasing the sequential progress the thesis rests on.
`revenue_crore` / `LT` / `5104.16` — Q1 FY26 revenue exactly; set a quarter back rather than at
5,715.42 so one seasonal dip does not fire it.

**F3 — Margin breaks the floor.** PBT margin falls below the worst margin in evidence, i.e. the
YoY margin recovery reverses outright.
`pbt_margin_pct` / `LT` / `5.53` — Q2 FY25 PBT margin, 256.70/4,644.51 = 5.527%, rounded up so
the predicate is strictly harder to fire than the historical low.

**F4 — Growth stops reaching the bottom line.** PAT YoY growth halves from the observed rate.
`pat_yoy_pct` / `LT` / `14.90` — half of the observed 29.8%. Same halving rule as F1; together
they separate "no growth" from "growth without profit".

**F5 — Margin regime change, either direction.** PAT margin leaves the corridor the three known
quarters trace. Below is deterioration; above means the thin, range-bound cost structure I
assumed is simply wrong and the model needs rebuilding.
`pat_margin_pct` / `OUTSIDE_BAND` / `[4.17, 5.15]` — low 193.88/4,644.51 = 4.174%, high
262.91/5,104.16 = 5.151%.

**F6 — Tax bridge breaks.** The PBT-to-PAT translation I treat as stable turns out to be driven
by structure, jurisdiction or one-offs.
`effective_tax_rate_pct` / `OUTSIDE_BAND` / `[24.47, 26.09]` — observed min (Q2 FY25) and max
(Q2 FY26) of the three computable quarters.

## Reasoning

The most informative fact in the brief is the sign disagreement between the YoY and QoQ columns:
every YoY line strongly positive, every profit line negative sequentially. That rules out the two
lazy readings. Not a demand problem — revenue rose 12.0% QoQ. Not a tax problem — ETR moved only
+0.67pp QoQ against a 0.95pp fall in PBT margin. It is cost or mix, visible directly as
93.58% -> 94.52% on the expense ratio. The thesis therefore has to take a position on whether
that 0.94pp of slippage persists. I say it does not, because the same ratio is 0.66pp *better*
than a year ago (95.18% -> 94.52%) — the signature of a converter absorbing an input-cost step,
not one structurally losing pricing power. F3 and F5 settle that bet.

Thresholds are anchored to printed values, not intuition. Deceleration tests halve the observed
growth rate (F1, F4) — an explicit reproducible rule rather than a defensible-sounding 10% or
15%. Level tests use a figure verbatim (F2 = Q1 FY26 revenue; F3 = the Q2 FY25 margin). Regime
tests use the observed min and max of the three computable quarters (F5, F6).

Considered and rejected:

- **QoQ profit falsifiers** (`pbt_qoq_pct`, `pat_qoq_pct`): with two priors I cannot separate
  seasonality from deterioration, so any threshold would encode ignorance rather than a claim.
- **`total_expenses_crore` thresholds**: any absolute ceiling fires trivially as revenue grows,
  since expenses run at 94.52% of revenue. The signal I want is the ratio; the registry has no
  expense-ratio metric, and with other income at ~0.48% of revenue, `pbt_margin_pct` is a good
  proxy.
- **A second PBT-margin band alongside F3**: F3 (floor) plus F5 (PAT-margin band) already cover
  downside and regime break without double-counting one movement twice.
- **`eps_yoy_pct` predicates**: under the no-dilution inference EPS YoY adds nothing to PAT YoY,
  and the interesting test — whether the two *diverge* — is a two-metric comparison the operator
  set cannot express.

## Open questions

1. **Neither management commitment is machine-checkable here, and I will not fake it.** The
   30,000 INR/MT conductor EBITDA guidance needs a metric like `conductor_ebitda_per_mt_inr`
   (segment EBITDA plus conductor volume in MT); the 25% YoY cables guidance needs
   `cables_segment_revenue_yoy_pct`. Neither exists, and mapping either onto `revenue_yoy_pct` or
   `pbt_margin_pct` would silently convert a segment claim into a company claim. Both stay
   unfalsified in Q0.
2. **Segment mix is the whole mechanism and I cannot see it.** A 0.95pp company-level margin move
   could be conductors, cables, oils, export mix or one project's timing. I want segment revenue
   and segment results next quarter.
3. **Q3 seasonality is unknown** — hence F2 is set a full quarter back rather than at Q2's level.
4. **Composition of the 27.43 other income, and whether any of the QoQ move is a one-off.** The
   brief shows no exceptional-item line; I have assumed there is none.
5. **Share count is inferred, not given.** A QIP or buyback would break the reading of F4/F5
   without breaking the business case.
6. **Cutoff hygiene.** I hold training-data recollection of Apar Industries covering periods after
   2025-11-06. I excluded it from every figure, threshold and judgement above; nothing here is
   derived from a post-cutoff outcome. The halving rule in F1/F4 is a mechanical transform of the
   Q2 FY26 print, not hindsight.
