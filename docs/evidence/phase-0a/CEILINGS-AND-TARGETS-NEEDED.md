# Phase 0A — Final Sheet: Ceilings & Targets (A-07 / A-12 / A-13)

The last thing between you and the closed gate. Everything is **pre-filled with
sensible defaults for a personal project** — reply "accept all defaults" or edit any line.

**Honest note on basis:** these were meant to be derived from *observed manual Q0 work*.
Because you (rightly) chose the multi-model method over a manual pass, Q0 wasn't manually
timed — so these are your **forward product-owner estimates**, not measured-manual values.
I'll record them truthfully as estimates. The governance rule: every item is either an
approved **CEILING** or a **MEASUREMENT_RULE** (observe & record) — never "unlimited."

---

## A-13 · Metric targets (the quality/cost/speed bars the product must hit)

| Metric | Proposed target | |
|---|---|---|
| factual_accuracy | ≥ 99% of material facts verified correct | [ ] |
| citation_correctness | ≥ 99% of citations resolve to exact source | [ ] |
| numerical_traceability | **100%** of material computed results traced (hard rule) | [ ] |
| unsupported_claims | **0** in final output (fail-closed) | [ ] |
| analyst_minutes | ≤ 20 min per stock-quarter (your review time) | [ ] |
| per_claim_verification_time | MEASUREMENT_RULE (observe; no target yet) | [ ] |
| coverage_capacity | 5 companies / week (target ambition) | [ ] |
| latency | ≤ 15 min per report end-to-end | [ ] |
| cost | ≤ ₹50 per report (model + tool) | [ ] |
| failure_retry_rate | MEASUREMENT_RULE (observe; flag if > 20%) | [ ] |

## A-07 · Workflow budget (per-report ceilings)

| Dimension | Proposed ceiling | |
|---|---|---|
| model cost | CEILING ₹50 / report | [ ] |
| tool calls | CEILING 60 / report | [ ] |
| latency | CEILING 15 min | [ ] |
| document volume | CEILING 10 docs / report | [ ] |
| retries | CEILING 3 | [ ] |
| analyst minutes | CEILING 20 min | [ ] |

## A-12 · Operating capacity

| Field | Proposed value | |
|---|---|---|
| weekly builder capacity | ~5 hrs / week (your dev time, flexible) | [ ] |
| weekly analyst capacity | ~2 hrs / week (your review time) | [ ] |
| pilot target date | Infosys Q1 output within the current build cycle | [ ] |
| monthly model/infra ceiling | CEILING ₹2,000 / month | [ ] |
| maintenance allowance | ~1 hr / week | [ ] |
| expected company coverage | start 1 (Infosys) → scale toward 5–10 | [ ] |

---

**How to respond:** reply **"accept all defaults"**, or name the lines you want to change
(e.g. "monthly ceiling ₹5,000, coverage start 1 scale to 20"). I record A-07 / A-12 / A-13-final
with your name + digests, re-run the validator → **it goes green → Phase 0A gate closes → the
build is authorized.**
