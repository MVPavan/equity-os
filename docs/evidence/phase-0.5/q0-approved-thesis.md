# Q0 Bootstrap Investment Thesis — Apar Industries Ltd (APARINDS), Q2 FY26

| Field | Value |
| --- | --- |
| Record type | `INVESTMENT_THESIS` |
| Record version | 1.0.0 |
| Record status | `ANALYST-APPROVED` |
| Program quarter | Q0 |
| Issuer quarter | Q2 FY26 (quarter ended 2025-09-30) |
| Basis | Consolidated, Ind AS, ₹ crore |
| Knowledge cutoff | 2025-11-06 |
| Approving analyst | PavanMV, product owner |
| Approval date | 2026-09-07 |
| Machine twin | `q0-approved-thesis.yaml` |
| Machine twin SHA-256 | `2ed9fd0f804da991249b9720f1c65909d5c66e22287a33ce80a0e962aa57c188` |

## Purpose and boundary

Fixes version 1.0.0 of the Q0 bootstrap thesis for Apar Industries. It is the frozen prior
against which the three assisted quarters — Q3 FY26, Q4 FY26 and Q1 FY27 — are mechanically
evaluated by `fundamentals thesis-impact`. It rests on the Q2 FY26 facts recorded in
`q0-fact-confirmation.md`; it confirms no figure itself and grants no source-use rights.

**The value of this thesis is that it can be proved wrong, not that it is right.**

## Method and provenance

Produced under the product-owner methodology decision of 2026-08-21 (bd memory
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

### Adjudication

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

### Known limitation

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
| F2 | PBT margin falls below the approximate prior-year floor | `pbt_margin_pct LT 5.53` | Q2 FY25 margin, 256.70 ÷ 4,644.51 |
| F3 | PAT YoY growth falls below half its Q0 rate | `pat_yoy_pct LT 14.90` | Half the Q0 rate of 29.8% |
| F4 | Basic EPS fails to grow year on year | `eps_yoy_pct LTE 0` | The boundary between growth and contraction |
| F5 | Effective tax rate exceeds its upper tolerance | `effective_tax_rate_pct GT 26.78` | Q2 FY26 rate plus the observed quarter-on-quarter spread |

Neither management commitment made on the Q2 FY26 call — conductor EBITDA of 30,000 INR per
metric ton, and cables revenue growth of 25 percent — is expressible as a predicate over any
registered metric. Both were deliberately left unfalsified rather than mapped onto a
company-level metric, which would have converted a segment claim into a company claim. They
remain tracked as commitments in the management ledger.

## How this record is used

```
fundamentals thesis-impact \
  --report-json <the quarter's run --out-json artifact> \
  --thesis docs/evidence/phase-0.5/q0-approved-thesis.yaml \
  --out <thesis-impact markdown>
```

Exit status 1 means at least one falsifier fired. Every evaluation report carries this file's
SHA-256, so an evaluation can always be tied back to the exact thesis text that produced it.
