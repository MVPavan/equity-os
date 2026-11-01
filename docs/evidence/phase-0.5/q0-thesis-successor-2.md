# Q0 Bootstrap Investment Thesis — Apar Industries Ltd (APARINDS), Q2 FY26

| Field | Value |
| --- | --- |
| Record type | `INVESTMENT_THESIS` |
| Record version | 1.2.0 |
| Record status | `ANALYST-APPROVED` |
| Program quarter | Q0 |
| Issuer quarter | Q2 FY26 (quarter ended 2025-09-30) |
| Basis | Consolidated, Ind AS, ₹ crore |
| Knowledge cutoff | 2025-11-06 |
| Approved by | gpt-6.1-sol |
| Approval date | 2026-11-01 |
| Machine twin | `q0-thesis-successor-2.yaml` |
| Machine twin SHA-256 | `ee1a13ac282b3873e15ec4938d7954283c7c687745ebf7a48a41c2afee8b7cfb` |

## Purpose and boundary

Fixes version 1.2.0 of the Q0 bootstrap thesis for Apar Industries. It is the frozen prior
against which the three assisted quarters — Q3 FY26, Q4 FY26 and Q1 FY27 — are mechanically
evaluated in each run draft's falsifier status sections. It rests on the Q2 FY26 facts recorded in
`q0-fact-confirmation.md`; it confirms no figure itself and grants no source-use rights.

**The value of this thesis is that it can be proved wrong, not that it is right.**

## Method and provenance

### Version 1.2.0

Version 1.2.0 keeps the 1.1.0 thesis content and F1–F5 unchanged and adds F6–F11, one falsifier per
risk-probe metric. The reason is that the risk probe's rule L tests a probe metric against the
approved thesis, and a probe limit is a typed thesis falsifier
(`docs/specs/2026-10-27-research-3-thesis-analysis.md` §2 L;
`docs/plans/RESEARCH-3-S1-risk-probe.md` Task 5). Without such a falsifier rule L has nothing to
evaluate. Each new falsifier is an opinion: the choice of metric, direction and recipe. Each
threshold is a calculation from that recipe over the observed values of the three statements below,
written by `thresholds.py`; no chosen constant enters any limit. Version 1.2.0 was approved by a
fresh gpt-6.1-sol review of this pair, the recipes and the script output (autonomous-approval
directive). The 1.0.0 council did not review 1.2.0.

The calculation's inputs and result are retained beside this pair:
`q0-thesis-successor-2-observations.json` (the observed values),
`q0-thesis-successor-2-recipes.yaml` (each recipe and its rationale) and
`q0-thesis-successor-2-thresholds.json` (each limit). The order is fixed: read the observations at
claim precision, evaluate the recipe in `Decimal`, then quantise half-even at the metric kind's
precision in `config/rounding_policy/v1.yaml`.

This is a retrospective record, as 1.1.0 was. The calculation reads only the statements below, each
published at or before the 2025-11-06 cutoff, and no input after Q2 FY26. The store first saw each
of them after that cutoff, and later quarters had already been processed under earlier versions
before this version. The recipes were written from the observed values of these statements alone.
That describes the input; it does not prove the absence of later knowledge, and the known limitation
below applies.

| Statement | Balance date | Flow window | Published at | First seen at |
| --- | --- | --- | --- | --- |
| FY26_Q2_H1 | 2025-09-30 | 2025-04-01 to 2025-09-30 | 2025-10-29T15:28:58+00:00 | 2026-10-20T12:27:04.942313+00:00 |
| FY25_Q2_H1 | 2024-09-30 | 2024-04-01 to 2024-09-30 | 2024-10-30T05:17:06+00:00 | 2026-10-29T06:31:59.975419+00:00 |
| FY25_FY | 2025-03-31 | 2024-04-01 to 2025-03-31 | 2025-05-14T16:01:25+00:00 | 2026-10-29T06:32:09.787165+00:00 |

### Version 1.1.0

Version 1.1.0 keeps the 1.0.0 thesis content unchanged except F5 and the F2 label. F5's threshold
was recalculated by a deterministic script from the two pinned filings, Q2 FY26 and Q1 FY26
(`q0-thesis-successor-1-f5-threshold.txt`), using reading A (rates rounded to 2 places first).
That computation reads no input after Q2 FY26. Later quarters had already been processed under
1.0.0 before this version; the change redefines the measure, not the recipe. Version 1.1.0 was
approved by a fresh gpt-6.1-sol review of this pair and the script output (autonomous-approval
directive). The 1.0.0 council below did not review 1.1.0.

### Version 1.0.0 history

Version 1.0.0 was produced under the product-owner methodology decision of 2026-08-21 (bd memory
`methodology-q0-thesis-multimodel-2026-08-21`), which supersedes a timed manual pass: independent
generation by a blind model council, orchestrator cross-verification, and product-owner
adjudication of divergent, material and low-confidence points only.

Council composition chosen by the product owner on 2026-09-07 — members as per the Infosys Q0,
judge newly named:

| Role | Model |
| --- | --- |
| Member (blind) | Claude Opus 5, effort medium |
| Member (blind) | GPT-5.6 Sol, effort high |
| Judge (consolidates only) | GPT-6 Astra, effort medium |

Source generations retained verbatim under `q0-council/`, together with the identical brief both
members received. Members ran in parallel and neither saw the other's work.

The orchestrator recomputed every derived figure in both member reports from the confirmed source
numbers; all agreed exactly. Every proposed metric identifier exists in the metric registry. The
approved falsifier set was executed against the Q0 artifact alone and all five metrics resolved.
No later quarter was evaluated before approval, so no post-cutoff outcome informed this thesis.

#### Adjudication

Two thresholds were adopted without owner involvement because both members chose them
independently: `revenue_yoy_pct LT 11.55` and `pbt_margin_pct LT 5.53`.

Six points diverged and were put to the product owner with the judge's recommendation on each:
whether profit-growth deceleration is measured after tax or before tax; whether a single
sequential profit fall should fire; whether unusually high margins should count as weakening;
whether the tax test should cover a falling rate; whether earnings per share needs its own test;
and whether an absolute revenue floor should be added.

Product-owner ruling, 2026-09-07, verbatim: **"accept all"** — every judge recommendation
accepted. The resulting set is five falsifiers. Each rejected alternative would have added a
predicate capable of firing on a good quarter.

#### Known limitation

All three models were trained past the 2025-11-06 cutoff and may hold recollections of Apar's
later results. Each was instructed to exclude such knowledge; Claude Opus 5 medium explicitly
declared holding it and excluding it. The judge found no identifiable post-cutoff outcome in
either member report. This is an instruction and a textual finding, not proof, and is recorded
as a limitation of the method rather than resolved.

## Approved thesis

**Stance.** Constructive but conditional on continued company-level revenue and earnings growth,
retention of the prior-year margin improvement, and positive per-share growth. The sequential
profit decline in Q2 FY26 makes temporary margin pressure a hypothesis to test rather than an
established fact.

**Assumptions and open questions** are carried verbatim in the machine twin and are not restated
here; the twin is the authority.

**Falsifiers.** Each is a deterministic predicate over one registered metric. A predicate
evaluating TRUE against an observed quarter is reported as `WEAKENED`.

| ID | Falsifier | Predicate | Threshold basis |
| --- | --- | --- | --- |
| F1 | Revenue YoY growth falls below half its Q0 rate | `revenue_yoy_pct LT 11.55` | Half the Q0 rate of 23.1% |
| F2 | PBT margin, PBT before associates over revenue, falls below the approximate prior-year floor | `pbt_margin_pct LT 5.53` | Q2 FY25 margin, 256.70 ÷ 4,644.51 |
| F3 | PAT YoY growth falls below half its Q0 rate | `pat_yoy_pct LT 14.90` | Half the Q0 rate of 29.8% |
| F4 | Basic EPS fails to grow year on year | `eps_yoy_pct LTE 0` | The boundary between growth and contraction |
| F5 | Effective tax rate, filed total tax over PBT before associates, exceeds its upper tolerance | `filed_effective_tax_rate_pct GT 26.74` | Q2 FY26 rate plus the observed quarter-on-quarter spread |

Neither management commitment made on the Q2 FY26 call — conductor EBITDA of 30,000 INR per
metric ton, and cables revenue growth of 25 percent — is expressible as a predicate over any
registered metric. Both were deliberately left unfalsified rather than mapped onto a
company-level metric, which would have converted a segment claim into a company claim. They
remain tracked as commitments in the management ledger.

### Version 1.2.0: probe limits

Each limit starts at the most adverse level the three statements show, under a strict operator.
F6–F8 stand above FY26_Q2's own level. F9–F11 start at FY26_Q2's own level, which does not fire. F10
and F11 add the move between the two half-years, so that drift alone does not fire them. F9 adds no
such move, because it is larger than the base and would carry the limit below zero, a different test.
High payable days and high capex intensity have no trend rule in the probe; their direction follows
the probe's own stated implication, and high capex can be deliberate, so a breach prompts examination.
R1–R3 scale by each window's own calendar days. Every limit compares half-year and full-year
statements without seasonal adjustment.

| ID | Falsifier | Predicate | Threshold basis |
| --- | --- | --- | --- |
| F6 | {{e:opinion}} Receivable days rise above the highest level the Q0-window statements show. | `probe_receivable_days GT 85.23` | The highest of R1 on the three statements below; calculated by `thresholds.py` |
| F7 | {{e:opinion}} Inventory days, materials-cost basis, rise above the highest level the Q0-window statements show. | `probe_inventory_materials_days GT 82.46` | The highest of R2 on the three statements below; calculated by `thresholds.py` |
| F8 | {{e:opinion}} Payable days, materials-cost basis, rise above the highest level the Q0-window statements show. | `probe_payable_materials_days GT 137.41` | The highest of R3 on the three statements below; calculated by `thresholds.py` |
| F9 | {{e:opinion}} Cash conversion, CFO over PAT, falls below the lowest level the Q0-window statements show. | `probe_cash_conversion_pct LT 32.81` | The lowest of R4 on the three statements below; calculated by `thresholds.py` |
| F10 | {{e:opinion}} Capex intensity, capex over revenue, rises above the highest level the Q0-window statements show by more than the move between the two half-years. | `probe_capex_intensity_pct GT 4.80` | The highest of R5 on the three statements below, plus the absolute difference between R5 on the FY26 and FY25 half-years; calculated by `thresholds.py` |
| F11 | {{e:opinion}} Borrowings to equity rises above the highest level the Q0-window statements show by more than the move between the two half-year balance dates. | `probe_borrowings_to_equity_ratio GT 0.128761` | The highest of R6 on the three statements below, plus the absolute difference between R6 on the FY26 and FY25 half-years; calculated by `thresholds.py` |

### Version 1.1.0: F5 redefined

Version 1.0.0 registered F5 on `effective_tax_rate_pct`, which derives tax as PBT − PAT. The
approved data spec (`docs/specs/2026-10-11-canonical-financial-data-and-cross-source-comparison.md`
§1) defines the rate as filed total tax ÷ PBT before the share of associates and forbids PBT − PAT,
which mixes in that share. Version 1.1.0 therefore re-registers F5 as
`filed_effective_tax_rate_pct` (`docs/plans/RESEARCH-1-falsifier-status.md`, D6 and Task 6). Its
threshold reapplies the 1.0.0 recipe to the filed Q2 FY26 and Q1 FY26 rates, each rounded to 2
places first; the computation, the source filings and their pinned sha256s are in
`q0-thesis-successor-1-f5-threshold.txt` (deterministic script output). 26.78 is not reproducible at 2 places: 1.0.0
used a 1-place Q2 FY26 rate, 26.10 (`q0-council/consolidation.md`).

## How this record is used

Each run draft binds the newest version of this thesis approved as of its cutoff and derives two
sections from it in code: `thesis_impact`, the status summary against that version's sealed
digest, and `observable_falsifiers`, each falsifier's traced value, operator, cited threshold and
status (`WEAKENED`, `HELD` or `UNRESOLVED`). F6–F11 also feed the risk probe's rule L; on a statement
that predates the run's period they show `NOT_ASSESSED`.
