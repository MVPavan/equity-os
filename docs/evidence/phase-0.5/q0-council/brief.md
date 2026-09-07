# Council brief — Apar Industries Q0 bootstrap investment thesis

You are one member of a blind council. Other models are answering this same brief
independently and will not see your work, nor you theirs. A judge model consolidates
afterwards. Write your best independent answer.

## Task

Write the **Q0 bootstrap investment thesis** for **Apar Industries Limited** (NSE `APARINDS`,
BSE scrip 532259), as an analyst would have written it on **2025-11-06**, working only from
the quarter ended **30 September 2025** (Q2 FY26) and what was public before that date.

This thesis is the fixed prior against which three later quarters will be mechanically
evaluated. Its value lies in being **falsifiable**, not in being right.

## HARD RULE — knowledge cutoff 2025-11-06

Write as of 2025-11-06. Do **not** use any knowledge of Apar Industries, its results, its
share price, its guidance, or Indian market conditions after that date, even if you have it.
If you find yourself recalling a later outcome, exclude it and say so in your open questions.
Using post-cutoff knowledge silently invalidates the entire exercise.

## Confirmed facts — Q2 FY26, quarter ended 2025-09-30

Consolidated, Ind AS, INR crore. Each figure below was independently extracted from the NSE
Ind AS XBRL consolidated instance and from the issuer's results PDF, and the two agree.

| P&L line | Value | Reconciliation |
| --- | ---: | --- |
| Revenue from operations | 5,715.42 | cross_source_confirmed |
| Total income | 5,742.85 | cross_source_confirmed |
| Total expenses | 5,402.29 | cross_foot_pass |
| Profit before tax | 340.56 | cross_source_confirmed |
| Profit for the period (PAT) | 251.70 | cross_source_confirmed |
| EPS basic (INR) | 62.66 | cross_source_confirmed |

## Comparatives (both priors are hash-pinned filings, both pre-cutoff)

| P&L line | Q2 FY26 | Q1 FY26 (Jun-2025) | QoQ | Q2 FY25 (Sep-2024) | YoY |
| --- | ---: | ---: | ---: | ---: | ---: |
| Revenue from operations | 5,715.42 | 5,104.16 | +12.0% | 4,644.51 | +23.1% |
| Total income | 5,742.85 | 5,128.95 | +12.0% | 4,677.29 | +22.8% |
| Total expenses | 5,402.29 | 4,776.44 | +13.1% | 4,420.59 | +22.2% |
| Profit before tax | 340.56 | 352.51 | -3.4% | 256.70 | +32.7% |
| Profit for the period (PAT) | 251.70 | 262.91 | -4.3% | 193.88 | +29.8% |
| EPS basic (INR) | 62.66 | 65.45 | -4.3% | 48.27 | +29.8% |

## Derived, from the figures above

- Non-operating / other income gap = 27 (Total income 5,742 minus Revenue 5,715)
- Net tax expense = 88 (PBT 340 minus PAT 251)
- Effective tax rate = 26.1% ((PBT 340 minus PAT 251) / PBT 340)
- PBT margin on revenue = 5.96%; PAT margin on revenue = 4.40%

## Management commitments stated on the Q2 FY26 earnings call

Both are quote-anchored to the held transcript at a known page, block and character span.

1. **Conductor EBITDA per metric ton: 30,000 INR/MT**, medium-term horizon.
   Management's words: "we will continue our guidance of 30,000 per metric ton".
2. **Cables revenue growth: 25% year on year**, annual horizon.
   Management's words: "we have been guiding a growth of 25% year on year".

## Falsifiers must be machine-checkable

Each falsifier you propose must be a deterministic predicate over exactly one **registered
metric**. The complete registry is below; nothing else exists, and you may not invent a metric.

Facts (INR crore, or INR per share for EPS): `revenue_crore`, `total_income_crore`,
`total_expenses_crore`, `pbt_crore`, `pat_crore`, `eps_basic_inr`.

Change percentages: `revenue_qoq_pct`, `revenue_yoy_pct`, `pbt_qoq_pct`, `pbt_yoy_pct`,
`pat_qoq_pct`, `pat_yoy_pct`, `eps_yoy_pct`.

Derived percentages: `pbt_margin_pct`, `pat_margin_pct`, `effective_tax_rate_pct`.

Operators: `LT`, `LTE`, `GT`, `GTE` each take one `threshold`; `OUTSIDE_BAND` takes a
`band: [low, high]`. A falsifier fires (the thesis is WEAKENED) when its predicate is TRUE of
the observed quarter.

**Important limitation, state it rather than working around it.** Every registered metric is
company-level consolidated P&L. There is no segment-level metric, and no EBITDA or per-metric-ton
metric. So neither management commitment above can be expressed directly as a predicate. Do not
force a segment or per-ton commitment onto a company-level metric and pretend it is equivalent.
Where a commitment matters but cannot be machine-checked, put it under open questions and say
what metric would be needed.

## Deliverable

A single self-contained report, in markdown, with these sections:

1. **Stance** — one or two sentences. Your actual view, conditional if it should be.
2. **Assumptions** — the load-bearing ones, each tagged `[FACT]`, `[INFERENCE]` or
   `[SPECULATION]`. A `[FACT]` must be traceable to a figure in this brief.
3. **Falsifiers** — 4 to 8 of them. For each: an id (`F1`, `F2`, ...), a plain-English
   statement of what would break the thesis, and the predicate as
   `metric_id` / `op` / `threshold` or `band`. Justify each threshold from the figures in this
   brief; an unjustified round number is worse than an awkward exact one.
4. **Reasoning** — why this thesis and these thresholds, including what you considered and
   rejected.
5. **Open questions** — what you could not settle from this brief, what you would want next
   quarter, and any commitment you could not turn into a predicate.

## Rules

- Work only from this brief. Do **not** open any file in the repository, do **not** search the
  web, do **not** run any command that reads `data/` or `scratchpad/`.
- Never state a figure that is not in this brief or arithmetic derived from one. Show the
  arithmetic when you derive.
- Do not hedge into uselessness. A thesis that cannot be wrong is worthless here.
- Length: aim for 700 to 1200 words. Depth over breadth.
