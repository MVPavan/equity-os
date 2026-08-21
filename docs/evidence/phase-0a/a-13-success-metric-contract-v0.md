# A-13 Success Metric Contract v0 (Method Only)

**Record version:** 1.0.0-approved-method-only
**Status:** APPROVED (METHOD ONLY) — pre-baseline metric method definitions accepted; NO targets set; analyst method acceptance and evaluation-authority method acceptance RECORDED; product-owner targets remain PENDING_BASELINE
**Prepared at:** 2026-08-21
**Author:** bounded implementer (drafting agent, not a decision maker)

## Purpose and boundary

This is the pre-baseline success-metric method required by decision-register v2
A-13. It defines, for every metric, the **unit, scope, collection method, phase
applicability, correction rules, and instrumentation overhead** — and nothing
else. It sets **no product-owner targets**: targets are evidence-derived
decisions that require the measured Q0 baseline and are recorded later in
`a-13-success-metric-contract-final.md`. Every `target` field below is
`PENDING_BASELINE`.

Collection is defined against the shared
`docs/evidence/phase-0a/instrumentation-vocabulary.json`, used symmetrically in
the manual and assisted lanes. Changing a definition creates a successor version
and does not rewrite earlier results. Analyst and evaluation-authority
acceptance of the **method** are now **RECORDED** (see method acceptance below);
product-owner **targets** remain **PENDING_BASELINE** and are not set here.

## Global method rules

- **Instrumentation overhead** is recorded separately via the
  `instrumentation_overhead` event and excluded from analytic-work metrics. If a
  metric's instrumentation overhead is not measurable, the affected comparison
  is invalid and cannot support a target, budget, or capacity decision.
- **Correction rules:** a correction emits a new event/measurement referencing
  the corrected one via visible lineage; earlier measurements are never
  rewritten. Re-derived metric values are versioned, not overwritten.
- **Small samples** are reported as observations; no percentile claim is made
  where sample size does not support it (e.g. no report-level P90 at n=3).
- **Phase applicability** states where the metric is collected; Q0 is the manual
  baseline, Q1–Q3 are assisted updates.

## Metric method definitions

| Metric | Unit | Scope | Collection method | Phase applicability | Correction rules | Instrumentation overhead | Target |
|---|---|---|---|---|---|---|---|
| `factual_accuracy` | ratio (correct / evaluated) | Per report, over material observed facts | `verification` event outcomes against exact source locations, stratified by materiality and epistemic class | Q0 manual; Q1–Q3 assisted | Corrected verifications supersede via lineage; ratio re-derived and versioned | Excluded via `instrumentation_overhead` | **PENDING_BASELINE** |
| `citation_correctness` | ratio (correct citations / citations) | Per report, over cited facts | Compare each citation to its `source_location_capture`; count exact-location matches | Q0 manual; Q1–Q3 assisted | Citation corrections tracked with lineage; ratio re-derived | Excluded | **PENDING_BASELINE** |
| `numerical_traceability` | ratio (traced / material computed) | Per report, over material computed results | Each computed result must resolve to a `calculation` trace; LLM is never the authoritative calculator | Q0 manual; Q1–Q3 assisted | Trace corrections superseded with lineage | Excluded | **PENDING_BASELINE** |
| `unsupported_claims` | count | Per report | Count accepted claims lacking required source location or calculation trace | Q0 manual; Q1–Q3 assisted | Reclassification recorded with lineage | Excluded | **PENDING_BASELINE** |
| `analyst_minutes` | minutes | Per report (total analyst time) | Sum of analytic-work event durations; excludes `instrumentation_overhead` | Q0 manual; Q1–Q3 assisted | Timing corrections superseded with lineage | Recorded and excluded | **PENDING_BASELINE** |
| `per_claim_verification_time` | seconds/claim | Per claim | `verification` (+ `source_location_capture`/`calculation`) duration per claim | Q0 manual; Q1–Q3 assisted | Per-claim corrections superseded with lineage | Excluded | **PENDING_BASELINE** |
| `coverage_capacity` | reports (or companies) per analyst per period | Per analyst per period | Count reviewed reports normalized to analyst capacity; reported as observation, no invalid percentile | Q0 manual; Q1–Q3 assisted | Re-counts versioned, not overwritten | Excluded | **PENDING_BASELINE** |
| `latency` | seconds (wall-clock) | Per report end-to-end | Elapsed time from first `reading` to `approval`/PENDING for the report | Q0 manual; Q1–Q3 assisted | Re-measurements versioned | Recorded and excluded | **PENDING_BASELINE** |
| `cost` | currency units (model + tool) | Per report | Sum of recorded model and tool-call cost measurements; no provider is selected here | Q0 manual (may be 0); Q1–Q3 assisted | Cost corrections superseded with lineage | Excluded | **PENDING_BASELINE** |
| `failure_retry_rate` | ratio (failed-or-retried / attempts) | Per report | Count workflow-step failures and retries over attempts | Q0 manual; Q1–Q3 assisted | Reclassified outcomes superseded with lineage | Excluded | **PENDING_BASELINE** |

All ten register-named metrics are defined. No target value appears in any row.

## Method acceptance

| Acceptance | Authority | State |
|---|---|---|
| Collection method (definitions/units/scopes) | Analyst | **APPROVED** |
| Collection method (evaluation seam) | Evaluation authority | **APPROVED** |
| Metric targets | Product owner | **PENDING_BASELINE** — not set before baseline evidence exists |

- **Decider:** PavanMV (mvpavan42@gmail.com), acting as analyst and, for this
  single-principal private project, expressly self-assuming the
  evaluation-authority role on the same basis already used for `A02-ATTEST-001`
  and the A-08 approval (`A08-APPROVAL-001`).
- **Decision date:** 2026-08-21.
- **Verbatim instruction (2026-08-21):** "Approve all with defaults." — given in
  direct reply to a plain-language explanation of the four items and their
  recommended defaults.
- **Scope of this approval:** the measurement **method only** (units, scopes,
  collection methods, phase applicability, correction rules, instrumentation
  overhead). It sets **no targets**; product-owner targets follow the measured
  Q0 baseline and are recorded later.

## Record digest convention and payload

Non-self-referential SHA-256 per the A-01 convention (UTF-8 canonical JSON,
recursively sorted keys, preserved array order, no whitespace/BOM, every
`record_digest` field excluded). No source content is digested.

```json
{"approval":{"analyst_method_acceptance":"APPROVED","evaluation_authority_method_acceptance":"APPROVED","product_owner_targets":"PENDING_BASELINE"},"artifact_id":"A-13","contract_kind":"SUCCESS_METRIC_CONTRACT_V0_METHOD_ONLY","decider":"PavanMV (mvpavan42@gmail.com), product owner and analyst; for this single-principal private project the evaluation-authority role is expressly self-assumed on the same basis as A02-ATTEST-001 and A-08 (A08-APPROVAL-001)","decision_date":"2026-08-21","document_version":"1.0.0-approved-method-only","instrumentation_vocabulary_ref":"docs/evidence/phase-0a/instrumentation-vocabulary.json","method_fields":["unit","scope","collection_method","phase_applicability","correction_rules","instrumentation_overhead"],"metrics":["factual_accuracy","citation_correctness","numerical_traceability","unsupported_claims","analyst_minutes","per_claim_verification_time","coverage_capacity","latency","cost","failure_retry_rate"],"prepared_at":"2026-08-21","scope":"Pre-baseline metric method definitions only: unit, scope, collection method, phase applicability, correction rules, and instrumentation overhead. No evidence-derived product-owner targets are set in v0; targets remain PENDING_BASELINE.","target_decisions_present":false,"verbatim_instruction":"Approve all with defaults. (2026-08-21)"}
```

**Record digest:** `sha256:3d5932842a80ece20890d9a6f721f337faf54b863e421d92d1398c1d60f38dc6`

## Authorities

- `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` — A-13 clause (metric definitions and measurement methods).
- `docs/specs/2026-08-19-phase-0a-evidence-program.md` — A-13 primary-ownership boundary; targets are product-owner decisions after baseline.
- `docs/evidence/phase-0a/instrumentation-vocabulary.json` — shared collection method.
- Analyst and evaluation authority (method): decisions **APPROVED** 2026-08-21 by PavanMV (see method acceptance above). Product owner (targets): **PENDING_BASELINE**, not set here.
