# A-13 Success Metric Contract (Final, With Targets)

**Record version:** 1.0.0-final
**Status:** ACCEPTED — the accepted A-13 v0 measurement method is preserved verbatim and product-owner targets are added; every target is an approved value or a defined MEASUREMENT_RULE, none is unlimited
**Prepared at:** 2026-08-21
**Author:** bounded implementer (recording agent, not the decision maker)

## Purpose and boundary

This is the `SuccessMetricContractFinal` required by decision-register v2 A-13
and Task 5. It **preserves the accepted A-13 v0 method** (unit, scope, collection
method, phase applicability, correction rules, instrumentation overhead) verbatim
and **adds only the product-owner targets**. It preserves:

- Path: `docs/evidence/phase-0a/a-13-success-metric-contract-v0.md`
- Version: `1.0.0-approved-method-only`
- Method digest: `sha256:3d5932842a80ece20890d9a6f721f337faf54b863e421d92d1398c1d60f38dc6`

## Basis (recorded honestly)

These targets are **FORWARD PRODUCT-OWNER TARGETS** for a personal project. Q0
was executed via the multi-model method (`bd memory
methodology-q0-thesis-multimodel-2026-08-21`), **not** a timed manual pass, so
the targets are honest forward product-owner ambitions and are **NOT derived from
observed manual Q0 minutes**. Every target is either an approved value or a
defined `MEASUREMENT_RULE` (never "unlimited").

## Global method rules (preserved from v0)

- **Instrumentation overhead** is recorded separately via the
  `instrumentation_overhead` event and excluded from analytic-work metrics. If a
  metric's instrumentation overhead is not measurable, the affected comparison is
  invalid.
- **Correction rules:** a correction emits a new event/measurement referencing
  the corrected one via visible lineage; earlier measurements are never
  rewritten. Re-derived values are versioned, not overwritten.
- **Small samples** are reported as observations; no percentile claim is made
  where sample size does not support it.
- **Phase applicability** states where the metric is collected; Q0 is the manual
  baseline, Q1–Q3 are assisted updates.

## Metric method definitions and product-owner targets

The Unit, Scope, Collection method, Phase applicability, Correction rules, and
Instrumentation overhead columns are preserved verbatim from A-13 v0. The
**Target** column is the product-owner decision added here.

| Metric | Unit | Scope | Collection method | Phase applicability | Correction rules | Instrumentation overhead | Target |
|---|---|---|---|---|---|---|---|
| `factual_accuracy` | ratio (correct / evaluated) | Per report, over material observed facts | `verification` event outcomes against exact source locations, stratified by materiality and epistemic class | Q0 manual; Q1–Q3 assisted | Corrected verifications supersede via lineage; ratio re-derived and versioned | Excluded via `instrumentation_overhead` | **≥ 0.99** |
| `citation_correctness` | ratio (correct citations / citations) | Per report, over cited facts | Compare each citation to its `source_location_capture`; count exact-location matches | Q0 manual; Q1–Q3 assisted | Citation corrections tracked with lineage; ratio re-derived | Excluded | **≥ 0.99** |
| `numerical_traceability` | ratio (traced / material computed) | Per report, over material computed results | Each computed result must resolve to a `calculation` trace; LLM is never the authoritative calculator | Q0 manual; Q1–Q3 assisted | Trace corrections superseded with lineage | Excluded | **= 1.0 (hard rule, 100%)** |
| `unsupported_claims` | count | Per report | Count accepted claims lacking required source location or calculation trace | Q0 manual; Q1–Q3 assisted | Reclassification recorded with lineage | Excluded | **= 0 (hard rule, fail-closed)** |
| `analyst_minutes` | minutes | Per report (total analyst time) | Sum of analytic-work event durations; excludes `instrumentation_overhead` | Q0 manual; Q1–Q3 assisted | Timing corrections superseded with lineage | Recorded and excluded | **≤ 20 (CEILING)** |
| `per_claim_verification_time` | seconds/claim | Per claim | `verification` (+ `source_location_capture`/`calculation`) duration per claim | Q0 manual; Q1–Q3 assisted | Per-claim corrections superseded with lineage | Excluded | **MEASUREMENT_RULE** (observe; no target yet) |
| `coverage_capacity` | reports (or companies) per analyst per period | Per analyst per period | Count reviewed reports normalized to analyst capacity; reported as observation, no invalid percentile | Q0 manual; Q1–Q3 assisted | Re-counts versioned, not overwritten | Excluded | **≥ 5 companies/week** |
| `latency` | seconds (wall-clock) | Per report end-to-end | Elapsed time from first `reading` to `approval`/PENDING for the report | Q0 manual; Q1–Q3 assisted | Re-measurements versioned | Recorded and excluded | **≤ 15 min (CEILING)** |
| `cost` | currency units (model + tool) | Per report | Sum of recorded model and tool-call cost measurements; no provider is selected here | Q0 manual (may be 0); Q1–Q3 assisted | Cost corrections superseded with lineage | Excluded | **≤ ₹50/report (CEILING)** |
| `failure_retry_rate` | ratio (failed-or-retried / attempts) | Per report | Count workflow-step failures and retries over attempts | Q0 manual; Q1–Q3 assisted | Reclassified outcomes superseded with lineage | Excluded | **MEASUREMENT_RULE** (observe; flag if > 20%) |

All ten register-named metrics now carry a target: eight approved values (two of
them hard rules) and two defined `MEASUREMENT_RULE`s. None is unlimited.

## Target acceptance

| Acceptance | Authority | State |
|---|---|---|
| Collection method (definitions/units/scopes) | Analyst | **APPROVED** (preserved from v0; re-confirmed) |
| Collection method (evaluation seam) | Evaluation authority | **APPROVED** (preserved from v0; re-confirmed) |
| Metric targets | Product owner | **APPROVED** |

- **Decider:** PavanMV (mvpavan42@gmail.com), product owner. For this
  single-principal private project the analyst and evaluation-authority method
  re-confirmations rest on the same basis already used for `A02-ATTEST-001` and
  the A-08 approval (`A08-APPROVAL-001`); the method itself is unchanged from the
  accepted v0.
- **Decision date:** 2026-08-21.
- **Verbatim instruction (2026-08-21):** "Accept all the defaults."
- **Scope of this approval:** the ten metric targets above only. The measurement
  method is preserved from the accepted v0 and is not re-opened. No provider or
  model is selected.

## Record digest convention and payload

Non-self-referential SHA-256 per the A-01 convention (UTF-8 canonical JSON,
recursively sorted keys, preserved array order, no whitespace/BOM, every
`record_digest` field excluded). No source content is digested.

```json
{"approval":{"analyst_method_reconfirmation":"APPROVED","authority_role":"product_owner","evaluation_authority_method_reconfirmation":"APPROVED","product_owner_targets":"APPROVED"},"artifact_id":"A-13","basis":"FORWARD PRODUCT-OWNER TARGETS for a personal project. Q0 was executed via the multi-model method (bd memory methodology-q0-thesis-multimodel-2026-08-21), not a timed manual pass; these targets are honest forward product-owner ambitions, NOT derived from observed manual Q0 minutes. Every target is either an approved value or a MEASUREMENT_RULE; none is unlimited.","contract_kind":"SUCCESS_METRIC_CONTRACT_FINAL","decider":"PavanMV (mvpavan42@gmail.com), product owner","decision_date":"2026-08-21","document_version":"1.0.0-final","instrumentation_vocabulary_ref":"docs/evidence/phase-0a/instrumentation-vocabulary.json","method_fields":["unit","scope","collection_method","phase_applicability","correction_rules","instrumentation_overhead"],"method_preserved":true,"metrics":["factual_accuracy","citation_correctness","numerical_traceability","unsupported_claims","analyst_minutes","per_claim_verification_time","coverage_capacity","latency","cost","failure_retry_rate"],"prepared_at":"2026-08-21","preserves_method_of":{"digest":"sha256:3d5932842a80ece20890d9a6f721f337faf54b863e421d92d1398c1d60f38dc6","path":"docs/evidence/phase-0a/a-13-success-metric-contract-v0.md","version":"1.0.0-approved-method-only"},"scope":"Post-method final success-metric contract: preserves the accepted A-13 v0 measurement method (units, scopes, collection methods, phase applicability, correction rules, instrumentation overhead) verbatim and adds product-owner targets.","targets":{"analyst_minutes":{"kind":"CEILING","operator":"<=","unit":"minutes","value":20},"citation_correctness":{"kind":"TARGET","operator":">=","unit":"ratio","value":0.99},"cost":{"kind":"CEILING","operator":"<=","unit":"INR/report","value":50},"coverage_capacity":{"kind":"TARGET","operator":">=","unit":"companies/week","value":5},"factual_accuracy":{"kind":"TARGET","operator":">=","unit":"ratio","value":0.99},"failure_retry_rate":{"flag_threshold":0.2,"kind":"MEASUREMENT_RULE","unit":"ratio","value":"observe; flag if > 20%"},"latency":{"kind":"CEILING","operator":"<=","unit":"minutes","value":15},"numerical_traceability":{"kind":"HARD_RULE","operator":"==","unit":"ratio","value":1.0},"per_claim_verification_time":{"kind":"MEASUREMENT_RULE","unit":"seconds/claim","value":"observe; no target yet"},"unsupported_claims":{"kind":"HARD_RULE","operator":"==","unit":"count","value":0}},"verbatim_instruction":"Accept all the defaults. (2026-08-21)"}
```

**Record digest:** `sha256:9f02bed95afcd8a0a5fd1c2d1497543ecd0f531cfcd074ab03c302a49129fbc1`

## Authorities

- `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` — A-13 metric clause.
- `docs/evidence/phase-0a/a-13-success-metric-contract-v0.md` (`1.0.0-approved-method-only`, method digest `sha256:3d5932842a80ece20890d9a6f721f337faf54b863e421d92d1398c1d60f38dc6`) — the accepted measurement method preserved here.
- `docs/evidence/phase-0a/instrumentation-vocabulary.json` — shared collection method.
- Product owner: targets APPROVED 2026-08-21 by PavanMV (see target acceptance above).
