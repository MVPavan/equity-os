# Phase 0A — Approvals Needed From You

This is your decision sheet. Reply with your choices (approve-as-is, or edits) and
I record each as the formal authority entry in its artifact. Nothing here is
recorded until you decide — no approval is inferred.

Two parts: **Part A** you can do now (pre-baseline). **Part B** comes *after* your
Q0 baseline (its values must be grounded in the measured Q0 work) — listed so you
see what's coming, but do not decide it yet.

---

## PART A — approve now (you are the analyst / product owner)

### A-04 · Output-contract shape (analyst usability + product-owner scope)

**What it is:** the fixed list of sections every earnings-review output must have.
Not the content — just the shape. The 11 sections:

1. event_and_cutoff · 2. facts · 3. changes · 4. drivers · 5. management_ledger ·
6. thesis_impact · 7. observable_falsifiers · 8. open_questions · 9. calculations ·
10. non_canonical_memory_draft · 11. approval_record

**Approving means:** you accept these as the output structure for the pilot.

- [ ] **Approve as-is**  ·  [ ] Edit (add/remove/reorder sections): ______________

### A-10 · Materiality policy (analyst)

**What it is:** the rule that decides whether a claim is `MATERIAL` (needs full
source/calc support), `REVIEW` (you must eyeball it), or `NOT_MATERIAL`. It uses:
always-material categories (e.g. capital raise/dilution, guidance changes), a
quantitative magnitude band, thesis relevance, and source-conflict → REVIEW.

**One value needs you:** the **magnitude band** — the size at/above which a number
is automatically material. Currently a placeholder. Suggested starting point for a
large-cap like Infosys: **any P&L line ≥ 1% of revenue, or any change ≥ 5% quarter-on-quarter.**

- [ ] **Approve policy + use the suggested band (≥1% of revenue / ≥5% QoQ)**
- [ ] Approve policy, different band: ______________
- [ ] Edit policy: ______________

### A-13 · Metric method (analyst)

**What it is:** *how* each success metric is measured (units/scope/method) — NOT
the target numbers (those come after baseline). The 10 metrics:
factual_accuracy, citation_correctness, numerical_traceability, unsupported_claims,
analyst_minutes, per_claim_verification_time, coverage_capacity, latency, cost,
failure_retry_rate.

**Approving means:** you accept how these will be measured. No targets are set yet.

- [ ] **Approve the measurement method as-is**  ·  [ ] Edit: ______________

### A-09 · Product identity trademark basis (product owner)

**What it is:** you SELECTED "Fundamentals". The identity packet formally wants a
*competent trademark/legal assessment*, which honestly doesn't exist (no lawyer
reviewed it). The gate can't mechanically pass A-09 until you decide the basis.

**Recommended:** for this private/personal gate, the descriptive-name + non-legal
basis is sufficient; formal clearance deferred to any future public/commercial launch.

- [ ] **Accept non-legal basis for the private gate; defer formal clearance to public launch** (recommended)
- [ ] I want a real trademark clearance before the gate passes
- [ ] Other: ______________

---

## PART B — after your Q0 baseline (do NOT decide yet)

These must be grounded in the measured Q0 work (e.g. how many analyst-minutes Q0
actually took), so they come after the baseline. Listed for visibility only.

- **A-13 targets** — the target values for the 10 metrics (set from what Q0 showed).
- **A-07 workflow budget** — per-report ceilings or measurement rules for cost, tool
  calls, latency, document volume, retries, analyst minutes. (A missing ceiling is
  recorded as `CEILING_NOT_APPROVED`, never "unlimited".)
- **A-12 operating capacity** — weekly builder/analyst capacity, target dates, monthly
  provider/model/infra ceilings, maintenance allowance, expected company coverage.

I'll tee these up as a second short sheet once your Q0 baseline lands, pre-filled
with the measured numbers so they're mostly confirm/adjust.

---

**How to respond:** just tell me your choice per item (e.g. "A-04 approve, A-10 approve
with band ≥1%/≥5%, A-13 approve, A-09 accept non-legal basis"). I'll record each into
its artifact with your name, date, and the digest binding — and re-run the validator.
