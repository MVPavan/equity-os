# S14 — Fixed earnings-review workflow and feedback rework

**Status: DRAFT — AWAITING FRESH SOL XHIGH REVIEW**

This document is an implementation contract, not evidence of delegated approval. It does not grant analyst, product, production, or other human authority.

## 1. Authority and ownership

The v2 decision register states exactly: “The wording in this register is authoritative for implementation gates. Narrative reviews explain rationale but do not override this register.” If this contract conflicts with the register, the register wins and implementation stops pending amendment and fresh review.

| Ownership field | Exact source text |
|---|---|
| Spec ID | `S14` |
| Spec title | `Fixed earnings-review workflow and feedback rework` |
| Exact path | `docs/specs/equity-os-s14-earnings-review-workflow-rework.md` |
| Primary register IDs | `B-01, B-02, B-14` |
| Disposition references | `M-5, R-5` |
| Activation classification | `active-only` |

The owned register rows are reproduced without semantic rewriting:

| ID | Priority | Decision or action | Required evidence / acceptance | Dependencies | Status |
|---|---:|---|---|---|---|
| B-01 | Critical | Implement fixed, resumable earnings-review workflow | State definitions, allowed transitions, failure states, immutable step outputs, idempotent retries, and resume behavior documented and tested | A-04, A-10, A-11 | Open |
| B-02 | Critical | Produce three real incremental earnings updates | Quarters 1–3 each consume the approved preceding thesis and include sources, facts, changes, management ledger, thesis impact, falsifiers, calculations, open questions, and approval record | B-01, B-03–B-07, B-11–B-14 | Open |
| B-14 | Critical | Demonstrate human-feedback rework path | A rejected claim triggers the correct invalidation cascade; evidence package v(N+1) is created; only affected calculations/claims are rerun; prior package remains immutable; partial revalidation and reapproval succeed | B-01, B-11 | Open |

Disposition authority is limited to these exact findings:

- `M-5 — Human-feedback rework transitions`: immutable step outputs, idempotent re-entry, evidence-package versioning, dependency-aware invalidation, partial revalidation, and a path from rejected claim through correction/re-extraction/recalculation/redrafting/reapproval are required.
- `R-5 — Predefine the SQLite migration trigger`: SQLite remains appropriate for the vertical slice and small pilot; migration triggers are operational notes rather than a new critical decision.

## 2. Scope

This contract owns:

1. The fixed, resumable earnings-review state machine from run registration through publication.
2. Immutable step attempts and outputs, idempotent retry/re-entry, failure handling, and deterministic resume.
3. Three real assisted incremental updates for Quarters 1–3 using each approved preceding thesis.
4. Rejected-claim correction, evidence-package versioning, dependency-aware invalidation, minimal rerun, partial revalidation, and reapproval.
5. Observable migration triggers for the Phase 0.5 SQLite/simple-state implementation.

### Non-goals

- Autonomous planning or arbitrary agent-selected workflow transitions.
- Defining claim validation, human review semantics, deterministic calculations, source-of-truth roles, or thesis content owned by S13, S15, S16, S10, and S05/S06.
- Selecting a distributed workflow engine before observed need.
- Treating a successful retry as permission to overwrite an earlier attempt or output.
- Publishing any run without its required human approval record.

## 3. Fixed state machine

The successful path is fixed:

`REGISTERED → INGESTED → EXTRACTED → RECONCILED → CALCULATED → DRAFTED → HUMAN_REVIEW → APPROVED → PUBLISHED`

The complete base-edge set is:

| Transition kind | Allowed edge | Predicate |
|---|---|---|
| Forward | Each adjacent edge in the successful path through `HUMAN_REVIEW` | The predecessor's immutable output exists and every input hash required by the successor matches. |
| Approval | `HUMAN_REVIEW → APPROVED` | A current `ACCEPT` resolution binds the exact reviewed artifact/claim bytes and declared scope. |
| Publication | `APPROVED → PUBLISHED` | The exact `PublicationEligibilityResult` defined in §4.8 is `TRUE`. |
| Rework | `HUMAN_REVIEW → INGESTED` | `REJECT` identifies source selection or source correction as the earliest affected step. |
| Rework | `HUMAN_REVIEW → EXTRACTED` | `REJECT` identifies extraction as the earliest affected step. |
| Rework | `HUMAN_REVIEW → RECONCILED` | `REJECT` identifies reconciliation as the earliest affected step. |
| Rework | `HUMAN_REVIEW → CALCULATED` | `REJECT` identifies calculation as the earliest affected step. |
| Rework | `HUMAN_REVIEW → DRAFTED` | `REJECT` identifies claim construction or drafting as the earliest affected step, or `EDIT` creates new draft bytes. |

A rework target names the logical step that must execute next; it does not assert that the target step has already produced a valid replacement output. Its transition record must preserve `rework_resume_target=target`. After that new attempt commits, the run follows the declared forward edges. `DEFER` records a review outcome without changing `HUMAN_REVIEW`.

For any otherwise allowed base edge `from → target`, an attempt may record `from → FAILED` instead of committing `target`; its transition record must preserve `resume_target=target`. `FAILED` may transition only to that exact `resume_target` through a new idempotent attempt, or to `BLOCKED` with the same target. If required input, evidence, or authority is unavailable before an allowed edge, `from → BLOCKED` is legal only with `blocked_resume_target=target`; after the recorded blocker is resolved, `BLOCKED` may transition only to that target. Thus failure and blocking edges are derived mechanically from the closed base-edge set rather than selected freely.

Human outcomes are:

- `ACCEPT`: advance a content-bound reviewed version toward `APPROVED`.
- `REJECT`: create a correction request and enter the rework algorithm below.
- `EDIT`: create a new drafted version, invalidate affected downstream review, and require review of the new bytes.
- `DEFER`: remain unapproved and unpublished until a later explicit decision.

No other transition is legal. A state label alone is not proof: each transition requires a valid `WorkflowTransitionRecord`, its declared immutable input/output references, and actor/authority where applicable.

## 4. Interfaces and data contracts

### 4.1 `RunRecord`

Contains stable `run_id`, discovery company, quarter, run cutoff, source/evidence-package version, preceding approved thesis ID and content hash, workflow-definition version, created time, and ordered transition references. The current logical state is derived from the last valid chained transition record, never asserted independently. Quarters 1–3 must name the immediately preceding approved thesis; absence or hash mismatch blocks registration.

### 4.2 `WorkflowTransitionRecord`

Contains stable transition ID, run ID, prior-transition digest, `from_state`, `to_state`, transition kind, workflow-definition version, triggering attempt/output references, exact input and output digests, review-outcome/approval resolution ID and digest when applicable, correction and invalidation references, evidence-package ID/version/digest, `resume_target`, `blocked_resume_target`, or `rework_resume_target` when applicable, blocker and resolution evidence, actor/authority reference when applicable, transition time, and `transition_digest`. Fields that do not apply are explicit `null`, not omitted.

The digest preimage is the UTF-8 domain separator `equity-os.s14.workflow-transition.v1`, one LF byte, and RFC 8785 canonical JSON of every field above except `transition_digest`, including explicit nulls and the prior-transition digest. `transition_digest` is the lowercase SHA-256 hex digest of that exact preimage. Missing canonical bytes, a broken prior-digest chain, a digest mismatch, or disagreement between the record's target and the closed graph blocks the transition.

An approval edge must bind the exact S15 decision ID, immutable resolution digest, reviewed artifact/claim hashes, and scope; a rework edge must bind the exact `REJECT` or `EDIT` decision plus correction, invalidation, and new evidence-package records, with `rework_resume_target=to_state`. `FAILED` and `BLOCKED` records must bind the exact target they preserve. A copied outcome string, an unbound resolution, or an inferred resume target is invalid.

### 4.3 `StepAttempt`

Contains stable attempt ID, run ID, step, attempt number, idempotency key, immutable input-reference set and digest, executor/tool version, start/end times, outcome, output references, failure classification, and retry-of reference. The idempotency key is derived from the logical step, workflow version, and exact input digest. Repeating the same key returns the same committed output or safely completes the same atomic commit; it never creates duplicate side effects.

### 4.4 `StepOutput`

Contains stable output ID, run/step/attempt identity, content hash, immutable artifact location, schema version, creation time, and dependency edges. Outputs are append-only. Correction creates a successor; no operation mutates prior bytes.

### 4.5 `EvidencePackageVersion`

Contains stable package ID, monotonically increasing version within a run, parent package ID, exact added/retained/invalidated evidence references, cutoff, content digest, creation reason, and creator. `v(N+1)` never changes `vN`.

### 4.6 `DependencyEdge` and `InvalidationRecord`

Every derived fact, calculation, claim, section, draft, review, and approval declares exact upstream references. An invalidation record binds the rejected/corrected input, reason, affected edge closure, invalidated outputs, unaffected outputs retained, package transition, actor, timestamp, and digest. Dependency closure is computed from stored edges, not prose or filename conventions.

### 4.7 `ReviewOutcome`

S14 consumes the content-bound human decision contract supplied by S15: decision ID and type, exact reviewed artifact/claim version and hash, actor and human actor type, authority basis, exact scope, timestamp, rationale where required, evidence, and immutable resolution digest. S14 must verify the complete canonical decision record against that digest before using it in a transition. Unavailable canonical bytes, a digest mismatch, stale/revoked authority, changed scope, or a copied decision string blocks the transition.

### 4.8 `PublicationTarget` and `PublicationEligibilityResult`

`PublicationTarget` contains stable target ID and version, exact audience, channel/destination, access controls, public-distribution, paid-distribution, personalization, and execution-linkage classifications, and a content digest. Unknown or omitted classifications are invalid.

`PublicationEligibilityResult` contains a stable result ID and binds the approved artifact ID/hash, current `ANALYST_ACCEPTANCE` decision ID and resolution digest, target ID/version/digest, S01 `OperatingBoundary` ID/version/digest, its exact current `PRODUCT_OWNER_DECISION` ID and resolution digest, evaluator version, evaluated time, reasons, a three-valued result (`TRUE`, `FALSE`, or `UNKNOWN`), and `result_digest`.

The eligibility predicate is `TRUE` only when all of the following hold for the exact bound bytes:

1. The run's chained state is `APPROVED`, the analyst acceptance is current and exact-scope, and no invalidation, review, failure, or blocker remains unresolved.
2. The target resolves unambiguously to private/internal use, its audience is within the current boundary's intended users, and its channel/access controls preserve that restriction.
3. The current content-bound S01 boundary resolution is valid, has `private_internal_use=true`, and classifies public distribution, paid distribution, personalization, and execution linkage as `PROHIBITED`.
4. Every bound ID, version, scope, authority record, and digest recomputes and matches.

A known out-of-boundary target yields `FALSE`; missing, stale, ambiguous, conflicting, or unverifiable inputs yield `UNKNOWN`. Every result other than `TRUE` blocks publication. In particular, analyst acceptance does not authorize a publication target. While E-08 remains deferred, public, paid, personalized, and execution-linked targets fail closed even if a nearby or purported approval is supplied; S14 neither activates nor evaluates the dormant distribution gate.

For both records, the content-digest preimage is the record-type domain separator (`equity-os.s14.publication-target.v1` or `equity-os.s14.publication-eligibility.v1`), one LF byte, and RFC 8785 canonical JSON of every field except `content_digest` or `result_digest`, with explicit nulls. The digest is lowercase SHA-256 hex.

### 4.9 `PublicationReceipt`

Contains stable receipt ID, approved artifact ID/hash, current analyst-acceptance decision ID/resolution digest, run/evidence-package/thesis versions, publication-target ID/version/digest, `PublicationEligibilityResult` ID/digest, operating-boundary ID/version/digest, publication idempotency key, commit timestamp, atomic publication result, and `receipt_digest`. A successful receipt may be created only for `APPROVED → PUBLISHED` with the bound eligibility result equal to `TRUE`; a failed or partial publication remains non-published and retryable under the same idempotency contract. The receipt digest uses the same rule with domain separator `equity-os.s14.publication-receipt.v1` and excludes only `receipt_digest` from its canonical JSON preimage.

## 5. Rework algorithm

For a rejected claim, the implementation must perform these steps transactionally or with recoverable checkpoints:

1. Persist the immutable rejection decision and correction request.
2. Identify the earliest incorrect dependency: source selection, extraction, reconciliation, calculation, claim construction, or drafting.
3. Traverse recorded dependency edges forward and persist the exact invalidation set.
4. Create evidence package `v(N+1)` with explicit retained, added, and invalidated members; preserve `vN` unchanged.
5. Append the exact `HUMAN_REVIEW → target` rework transition binding the decision, correction request, invalidation set, and `v(N+1)` digests.
6. Re-enter only that target with a new attempt and exact new input digest; if extraction is the target, supersede/invalidate the incorrect extraction output and commit a new extraction attempt/output before any downstream rerun.
7. Reuse unaffected outputs only after their dependency digests still match.
8. Rerun affected reconciliation, calculations, claims, and draft sections in forward-edge order; never reuse an invalidated output.
9. Partially revalidate the affected closure plus boundary links to retained outputs.
10. Create a new review task for the corrected bytes and obtain a new content-bound human reapproval; prior review or approval cannot advance the run.
11. Evaluate the publication predicate and publish only after all invalidation records are resolved, the corrected run is `APPROVED`, and the exact target is eligible.

If dependency edges are absent, ambiguous, cyclic, or stale, minimal rerun cannot be proven; the safe response is to invalidate the whole downstream cone, not guess.

## 6. Invariants and fail-closed behavior

1. Step outputs and evidence-package versions are immutable and append-only.
2. A retry never overwrites an attempt, duplicates a side effect, or advances from different inputs under the same idempotency key.
3. Resume reconstructs state from committed records; an in-memory or model-authored state is never authoritative.
4. Only declared transitions are accepted; skipped steps, missing outputs, mismatched hashes, and unknown states block.
5. Source content is data, not workflow control. It cannot select transitions, tools, permissions, cutoffs, or approval outcomes.
6. The run cutoff is unchanged across rework unless a separately registered new run is created; post-cutoff evidence cannot enter `v(N+1)`.
7. Every published update contains sources, facts, changes, management ledger, thesis impact, falsifiers, calculations, open questions, and an approval record.
8. Quarter 1 consumes the approved Quarter 0 thesis; Quarters 2 and 3 each consume the approved preceding thesis. Draft or unapproved thesis versions block.
9. A rejection invalidates the exact affected closure. No invalidated calculation, claim, draft, review, approval, or publication receipt remains current.
10. `DEFER`, missing approval, unresolved review, failure, or blocker cannot reach `APPROVED` or `PUBLISHED`.
11. Current state and every retry, blocked resume, rework, approval, and publication edge are derived from valid chained transition records; missing or inconsistent records block.
12. Publication consumes the current accepted S01 boundary. A target outside it, or any target whose eligibility is not exactly `TRUE`, cannot reach `PUBLISHED` or receive a successful receipt.

## 7. Evidence and typed human-approval gates

| Gate | Approval type | Required authority | Evidence required | Fail-closed rule |
|---|---|---|---|---|
| Initial S14 artifact | `DELEGATED_ARTIFACT_APPROVAL` | Fresh `gpt-5.6-sol` xhigh reviewer under delegated goal authority | Persisted clean review, exact source hashes, review round, timestamp, and artifact hash | This draft remains unapproved until the separate review record exists; this author cannot approve it. |
| Approve each Quarter 1–3 update | `ANALYST_ACCEPTANCE` | Competent human analyst | Exact report/thesis/evidence-package hashes, reviewed claim set, actor authority basis, decision, timestamp, and evidence | No approval record means no `APPROVED` or `PUBLISHED` transition. |
| Reapprove after rework | `ANALYST_ACCEPTANCE` | Competent human analyst | Corrected bytes, resolved invalidation closure, partial/full validation evidence, superseded prior decision, actor authority basis, decision, timestamp, and digest | Prior approval never carries across changed bytes or package versions. |
| Resolve the current private/internal boundary | S01 `PRODUCT_OWNER_DECISION` (consumed, not owned) | Competent human product owner under S01/A-01 | Exact `OperatingBoundary` ID/version/digest, intended users, all mode classifications, actor authority basis, decision, timestamp, and resolution digest | Missing, stale, mismatched, or non-private boundary evidence blocks target eligibility and publication; analyst acceptance cannot substitute. |

Every human approval is a distinct canonical resolution binding actor, human actor type, authority basis, exact scope, decision, timestamp, evidence, and immutable content digest. A model, coordinator, inferred condition, nearby approval, or matching text cannot supply or widen it. One approval satisfies at most one declared requirement.

## 8. SQLite and simple-state-table guard

SQLite and explicit state/attempt tables are the Phase 0.5 default. R-5 does not authorize migration. Record and measure the register's exact scale-up triggers:

- SQLite: persistent writer-lock contention affects ingestion/review; multiple remote users require concurrent writes; availability/backup/failover exceeds embedded deployment; or operational workarounds become more complex than migration.
- Simple state table: durable timers/signals are required across services; human rework/invalidation cannot be maintained clearly; concurrency/retries create duplicate side effects despite idempotency; or observability becomes a material burden.

A trigger observation is evidence for a separate decision, not automatic permission to migrate. Until that decision and its applicable human/provider/security approvals exist, the current implementation remains in place or blocks if unsafe.

## 9. Activation and amendment guards

S14 is `active-only` at the pinned draft snapshot because B-01, B-02, and B-14 are all `Open`; it owns no `Deferred` register row. This contract activates no deferred capability. Consuming S01's current A-01 boundary does not transfer ownership or activate S01/E-08. If an owned row becomes deferred, ownership expands to deferred scope, or a future S14 version is proposed to permit a public, paid, personalized, or execution-linked target, work stops pending the separate canonical authority/activation process, S14 amendment, and fresh review.

No evidence-derived mandatory amendment gate is assigned to S14. Any material change to state definitions, allowed transitions, acceptance semantics, or owned authority still changes this contract and requires fresh Sol xhigh review; prior approval evidence does not apply to changed bytes.

## 10. Dependencies

Authoritative dependencies are exact:

- B-01 depends on A-04, A-10, and A-11.
- B-02 depends on B-01, B-03 through B-07, and B-11 through B-14.
- B-14 depends on B-01 and B-11.

Interface dependencies are S01 for the current operating/distribution boundary, S05/S06 for the approved preceding thesis and output contract, S10 for source-of-truth/evidence-package authority, S12 for fact identity, S13 for claim validation, S15 for human decisions/correction/promotion, and S16 for calculation traces. These references do not transfer primary ownership.

## 11. Acceptance tests and verification

| Test | Fixture/action | Required result |
|---|---|---|
| S14-T01 Legal transitions | Enumerate every base edge, derived `FAILED`/`BLOCKED` edge, all five `HUMAN_REVIEW` rework targets, skips, regressions, target substitutions, digest-chain tampering, and unknown states. | Only the closed graph with complete content-bound transition records passes; failure/block records resume only their bound target and all other cases fail closed. |
| S14-T02 Crash resume | Crash before output commit, during commit, and after commit/ack. | Resume produces one committed output and no duplicate side effect. |
| S14-T03 Idempotent retry | Repeat identical and changed-input attempts. | Identical key returns the committed result; changed input requires a new key/output. |
| S14-T04 Rejected extraction | Reject a claim caused by extraction error and attempt rework once with the old extraction output and once with a corrected extraction attempt/output. | `v(N+1)` and `HUMAN_REVIEW → EXTRACTED` are recorded; the incorrect extraction output is invalidated/superseded but remains immutable; a new corrected extraction output is required; affected reconciliation/calculation/claim/draft/review outputs rerun in order; unrelated outputs remain only with matching dependencies. |
| S14-T05 Rejected calculation | Reject a calculated claim. | The calculation and downstream closure rerun; source/extraction outputs remain immutable and reusable when hashes match. |
| S14-T06 Missing dependency graph | Remove or corrupt an edge. | Whole uncertain downstream cone invalidates; workflow never guesses minimal scope. |
| S14-T07 Reapproval | Correct previously approved bytes. | Old approval becomes non-current; publication blocks until new analyst acceptance binds corrected bytes. |
| S14-T08 Three real updates | Execute Quarter 1, 2, and 3 runs. | Each consumes the approved preceding thesis and produces every B-02 required section plus approval record. |
| S14-T09 Cutoff/source injection | Add post-cutoff evidence and instruction-like source text during rework. | Evidence is excluded; source text cannot alter workflow control. |
| S14-T10 Migration trigger | Cross and do not cross each recorded trigger. | Telemetry records the result; neither case silently changes the engine. |
| S14-T11 Publication boundary | Attempt publication with a current exact private/internal target, each external mode, an out-of-audience target, and missing/stale/ambiguous boundary or resolution evidence. | Only the exact private/internal target can yield eligibility `TRUE`; every other case blocks `PUBLISHED` and emits no successful receipt, without activating E-08. |

Verification is complete only when these tests run against the implementation, all three real updates and the B-14 rework demonstration have current content-bound evidence, every required human approval is valid, and a fresh independent Sol xhigh review is clean. Structural presence of this file is not product verification.
