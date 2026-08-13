# S15 — Human claim review, correction, supersession, and promotion

**Status: DRAFT — AWAITING FRESH SOL XHIGH REVIEW**

This document is an implementation contract, not evidence of delegated approval. It does not grant analyst, memory-promotion, product, production, or other human authority.

## 1. Authority and ownership

The v2 decision register states exactly: “The wording in this register is authoritative for implementation gates. Narrative reviews explain rationale but do not override this register.” If this contract conflicts with the register, the register wins and implementation stops pending amendment and fresh review.

| Ownership field | Exact source text |
|---|---|
| Spec ID | `S15` |
| Spec title | `Human claim review, correction, supersession, and promotion` |
| Exact path | `docs/specs/equity-os-s15-human-review-correction-promotion.md` |
| Primary register IDs | `C-05, C-10` |
| Disposition references | `M-5, M-6, 6.6` |
| Activation classification | `active-only` |

The owned register rows are reproduced without semantic rewriting:

| ID | Priority | Decision or action | Required evidence / acceptance | Dependencies | Status |
|---|---:|---|---|---|---|
| C-05 | Critical | Build claim-level review UI/workflow | Accept, reject, edit, defer, source jump, calculation inspection, diff-only review, provenance display for memory drafts, and safe shadow-test mode are supported | B-13, B-14 | Open |
| C-10 | High | Establish correction, supersession, and promotion workflow | Corrections create new versions; invalidated items remain auditable; canonical promotion is separately approved; split-brain writes are prevented | B-03, B-14 | Open |

Disposition authority is limited to these exact findings:

- `M-5 — Human-feedback rework transitions`: review correction must reach source correction, re-extraction, recalculation, redrafting, partial revalidation, and reapproval through immutable versions and dependency-aware invalidation.
- `M-6 — Reviewer and builder are the same person`: accepted-unchanged is not sufficient; measure false accepts/rejects, use materiality/epistemic stratification, isolate seeded errors in shadow/test artifacts, and use external spot review where practical.
- `6.6 Seeded errors require isolation`: seeded errors are reviewer-QA tests, not production data; no promotion path may touch them.

## 2. Scope

This contract owns:

1. Claim-level human review operations: accept, reject, edit, defer, exact-source jump, calculation inspection, diff-only review, memory-draft provenance, and safe shadow mode.
2. Immutable correction versions and explicit supersession/invalidation links, including corrections discovered after acceptance or publication.
3. Separate, content-bound human authority for claim/report acceptance and canonical memory promotion.
4. A promotion boundary that prevents split-brain writes and rejects all shadow/golden artifacts.
5. Reviewer-bias safeguards at the review surface and decision-record boundary.

### Non-goals

- Owning the S13 claim schema or validator, S14 workflow engine/rework orchestration, S10 source-of-truth matrix, or S19 engine-neutral MemoryStore/promotion transaction.
- Letting UI state, model output, accepted-unchanged rate, or coordinator action substitute for human authority.
- Injecting known falsehoods into any artifact that can be promoted or published.
- Deleting or rewriting a corrected, rejected, invalidated, or superseded historical item.
- Defining public distribution or production authorization.

## 3. Interfaces and data contracts

### 3.1 `ReviewTask`

The immutable canonical record contains exactly `task_id`, `task_purpose` (`INITIAL_REVIEW`, `REWORK_REVIEW`, or `POST_APPROVAL_CORRECTION`), `run_id`, `evidence_package_id`, `evidence_package_version`, `evidence_package_content_sha256`, `claim_artifact_refs`, `report_artifact_id`, `report_artifact_version`, `report_content_sha256`, `current_approved_thesis_id`, `current_approved_thesis_content_sha256`, `materiality_policy_version`, `materiality_policy_content_sha256`, `validator_result_id`, `validator_result_content_sha256`, `source_location_targets`, `calculation_trace_targets`, `diff_base_id`, `diff_base_content_sha256`, `diff_head_id`, `diff_head_content_sha256`, `artifact_mode`, `provenance_refs`, `assigned_human_reviewer`, `exact_scope`, `created_at`, and `task_content_digest`. Every reference collection is duplicate-free and sorted by identifier. Its digest contract is defined in §3.8.

Task lifecycle is an append-only `ReviewTaskStateEvent` stream outside the canonical task bytes. Each canonical event contains exactly `event_id`, `task_id`, `task_content_digest`, `prior_event_digest`, `from_state`, `to_state`, `actor_identity`, `timestamp`, and `event_digest`; its digest contract is defined in §3.8. Task state, assignment display, or a copied task ID never alters the immutable task or supplies authority.

### 3.2 `ReviewDecision`

The canonical record contains exactly `decision_id`, `task_id`, `review_task_content_digest`, `approval_type`, `reviewed_artifact_id`, `reviewed_version`, `reviewed_content_sha256`, `artifact_mode`, `provenance_refs`, `decision` (`ACCEPT`, `REJECT`, `EDIT`, or `DEFER`), `actor_identity`, `human_actor_type`, `authority_basis`, `exact_scope`, `rationale`, `edit_or_correction_ref`, `timestamp`, `evidence_refs`, and `resolution_content_digest`. `approval_type` is exactly `ANALYST_ACCEPTANCE` only for a production `ACCEPT` eligible to satisfy that typed gate; it is explicit `null` for `REJECT`, `EDIT`, `DEFER`, and any shadow/golden `ACCEPT`. `rationale` and `edit_or_correction_ref` are explicit `null` when inapplicable, never omitted. Its digest contract is defined in §3.8.

- `ACCEPT` applies only to the exact reviewed bytes and declared scope. It supplies typed `ANALYST_ACCEPTANCE` only when the complete task recomputes, task and decision fields match, `artifact_mode=PRODUCTION`, provenance is current and eligible, and the scope is the exact analytical artifact scope being accepted; claim-only, shadow, golden, stale-provenance, or copied-task acceptance cannot authorize publication or promotion.
- `REJECT` requires a reason and correction target sufficient for S14 to determine or conservatively expand the invalidation cone.
- `EDIT` creates a new version; it never mutates the reviewed version and never inherits its acceptance.
- `DEFER` remains unapproved and cannot be promoted or published.

### 3.3 `CorrectionVersion`

Contains stable version ID, predecessor ID/hash, correction reason and category, changed fields/artifacts, author, creation time, source/evidence/calculation changes, affected dependency references, and content digest. The predecessor remains readable and immutable. A correction after acceptance or publication always creates this immutable successor (or first creates an immutable correction request that the eventual successor must bind); it never reopens bytes in place.

### 3.4 `SupersessionRecord`

Contains stable record ID, old and new version identities/hashes, relation (`CORRECTS`, `SUPERSEDES`, or `INVALIDATES`), reason, effective time, knowledge time, correction-decision reference, invalidated analyst-acceptance decision ID/digest when applicable, invalidated publication-receipt IDs/digests when applicable, and evidence. It never deletes the old version and cannot point a version to itself or create a cycle. Currentness is derived from the immutable decision/supersession/invalidation chain: an old acceptance or receipt named by a later valid record remains auditable but cannot authorize its predecessor or successor.

### 3.5 `PromotionRequest`

The canonical request contains exactly `request_id`, `accepted_artifact_id`, `accepted_artifact_type`, `accepted_artifact_version`, `accepted_content_sha256`, `accepted_exact_scope`, `analyst_acceptance_approval_type` (exactly `ANALYST_ACCEPTANCE`), `analyst_acceptance_decision_id`, `analyst_acceptance_resolution_content_digest`, `review_task_id`, `review_task_content_digest`, `evidence_package_id`, `evidence_package_version`, `run_id`, `run_cutoff`, `provenance_refs`, `artifact_mode`, `requested_canonical_target`, `required_promotion_approval_id`, `idempotency_key`, and `request_content_digest`. The request is an intent, not evidence that acceptance exists and not a successful promotion. Its digest contract is defined in §3.8.

### 3.6 `PromotionDecision` and `PromotionReceipt`

The decision is a distinct canonical `MEMORY_PROMOTION` human resolution containing exactly `decision_id`, `approval_type` (exactly `MEMORY_PROMOTION`), `request_id`, `request_content_digest`, `analyst_acceptance_decision_id`, `analyst_acceptance_resolution_content_digest`, `review_task_id`, `review_task_content_digest`, `requested_canonical_target`, `decision` (`APPROVED`, `DENIED`, `REVOKED`, or `EXPIRED`), `actor_identity`, `human_actor_type`, `authority_basis`, `exact_scope`, `timestamp`, `evidence_refs`, and `resolution_content_digest`. Its digest contract is defined in §3.8. Its analyst-acceptance and review-task bindings must exactly match the request; its decision ID must differ from the bound analyst-acceptance decision ID, and neither decision may satisfy the other's typed gate.

The canonical receipt contains exactly `receipt_id`, `request_id`, `request_content_digest`, `memory_promotion_decision_id`, `memory_promotion_resolution_content_digest`, `analyst_acceptance_approval_type` (exactly `ANALYST_ACCEPTANCE`), `analyst_acceptance_decision_id`, `analyst_acceptance_resolution_content_digest`, `review_task_id`, `review_task_content_digest`, `accepted_artifact_id`, `accepted_artifact_type`, `accepted_artifact_version`, `accepted_content_sha256`, `accepted_exact_scope`, `artifact_mode`, `provenance_refs`, `canonical_content_id`, `canonical_content_sha256`, `metadata_record_id`, `metadata_content_sha256`, `transaction_id`, `idempotency_key`, `committed_at`, `result` (exactly `SUCCEEDED` for a success receipt), and `receipt_digest`. It is returned only by the authoritative promotion transaction after the commit-time predicate below passes; its digest contract is defined in §3.8.

At transaction commit and again before returning a success receipt, the authoritative adapter must resolve the complete immutable `ReviewTask` and `ReviewDecision` by the request's bound IDs, independently recompute both digests, resolve current evidence/provenance, and prove all of the following: the decision is a distinct active, unreplaced, unrevoked, unexpired `ACCEPT` with `approval_type=ANALYST_ACCEPTANCE`; task, decision, request, and source bind the same exact artifact ID/type/version/hash and exact scope; mode is `PRODUCTION`; provenance is eligible; and no later correction, supersession, or invalidation makes the acceptance non-current. It must separately resolve and verify the current `MEMORY_PROMOTION` decision against the exact request and target. Absent records or bytes, stale/revoked/expired decisions, reused decision IDs, wrong scope, non-production mode, ineligible provenance, evidence/provenance failure, hash mismatch, or any cross-record disagreement aborts without promotion or a success receipt.

S15 invokes but does not reimplement the authoritative promotion adapter. Until S10 freezes the source-of-truth roles and the applicable S19 transaction is available, promotion is blocked rather than performed as independent best-effort writes.

### 3.7 `ArtifactMode`

Every reviewable artifact is exactly one of `PRODUCTION`, `SHADOW_TEST`, or `GOLDEN_FIXTURE`. Mode is immutable for a version. Only `PRODUCTION` is eligible for acceptance that can lead to publication or promotion. Copying content from another mode creates a new production version with explicit provenance and ordinary validation/review; it does not change the source artifact's mode.

`provenance_refs` resolve to content-addressed immutable lineage records and must agree across artifact, task, decision, request, and receipt. Provenance is eligible only when every reference resolves, the current version's production origin/mode is unambiguous, and no seeded error or test-only content remains. A copy from test mode must expose the copy boundary, create new production bytes, remove test-only content, and pass fresh production validation and review; the source task or acceptance never carries across. Missing, stale, conflicting, or test-contaminated provenance fails closed.

### 3.8 Canonical authority-record bytes

The shared byte contracts are:

| Record | UTF-8 domain separator | Digest member excluded from its own preimage |
|---|---|---|
| `ReviewTask` | `equity-os.s15.review-task.v1` | `task_content_digest` |
| `ReviewTaskStateEvent` | `equity-os.s15.review-task-state.v1` | `event_digest` |
| `ReviewDecision` | `equity-os.s15.review-decision.v1` | `resolution_content_digest` |
| `PromotionRequest` | `equity-os.s15.promotion-request.v1` | `request_content_digest` |
| `PromotionDecision` | `equity-os.s15.promotion-decision.v1` | `resolution_content_digest` |
| `PromotionReceipt` | `equity-os.s15.promotion-receipt.v1` | `receipt_digest` |

For each record, the digest preimage is its domain separator, one LF byte, and RFC 8785 canonical JSON of every canonical member declared in its subsection except the excluded digest member. No declared member may be omitted and no additional member is accepted; every inapplicable value is explicit `null`. Identifier-reference collections, including `evidence_refs` and `provenance_refs`, are duplicate-free arrays sorted by identifier before canonicalization. Each digest is the lowercase SHA-256 hex digest of that exact preimage.

The producer must retain and supply the complete canonical record bytes. Every S14 workflow consumer and authoritative promotion adapter must recognize the exact domain version, independently canonicalize and recompute the digest, and compare every bound task, decision, acceptance, artifact, mode, provenance, target, scope, authority, evidence reference, and content hash before acting. Unavailable bytes, an unknown domain version, noncanonical or incomplete membership, duplicate/unsorted reference collections, stale/revoked/expired authority, or any mismatch blocks approval, rework, publication, or promotion. A digest string, task ID, request assertion, or receipt string by itself is not authority.

## 4. Review behavior

The review surface must provide, for the exact version under review:

1. Accept, reject, edit, and defer actions whose consequences are explicit before confirmation.
2. One-hop jump to the exact source location for evidence-backed claims.
3. Calculation inspection showing registered inputs, assumptions, outputs, and code version.
4. Diff-only review against the last approved version, with an option to inspect unchanged context.
5. Materiality result/policy version, epistemic class, confidence, evidence direction, contradictions, uncertainty, and validator result.
6. Content-addressed mode/provenance for every reviewed artifact at decision time and again for every memory draft at promotion time.
7. A conspicuous immutable mode indicator for shadow and golden artifacts, with promotion/publication actions absent and server-side rejection if called directly.

## 5. Correction, supersession, and promotion flow

1. Persist the human review decision against exact reviewed bytes.
2. For `REJECT` or `EDIT`, create an immutable correction version or request and send it to S14's dependency-aware rework interface. If the source is already accepted or published, bind and invalidate the prior acceptance and every affected receipt without editing them, then use S14's declared `APPROVED`/`PUBLISHED` correction edge.
3. Preserve the reviewed version, decision, and every invalidated derivative.
4. Receive the corrected artifact plus invalidation/revalidation evidence as a new task.
5. Require a new analyst decision; no prior acceptance carries forward.
6. On exact-byte typed production acceptance, a separate promotion request may be created; it must bind the acceptance decision/digest, immutable task/digest, exact accepted scope, mode, and provenance.
7. Require a distinct active `MEMORY_PROMOTION` human decision for that request.
8. Invoke one idempotent authoritative promotion transaction; the adapter freshly resolves and verifies both distinct current decisions and accepts success only with a content-bound receipt covering the analyst acceptance, review task, request, promotion decision, canonical content, and metadata.
9. On timeout, partial failure, or ambiguous commit, query by idempotency key and reconcile; never issue an uncorrelated second write.

## 6. Invariants and fail-closed behavior

1. Human decisions bind the immutable review-task digest, typed approval when applicable, exact artifact bytes, version, mode, provenance, scope, authority, and evidence through the canonical-byte contract in §3.8; changing any of them makes the decision non-current.
2. Review task state, UI display, model recommendation, or accepted-unchanged telemetry cannot create approval.
3. Corrections append versions. Rejected, invalidated, and superseded items remain auditable.
4. A prior acceptance never authorizes corrected bytes, a new evidence-package version, a wider scope, or an immutable successor. Post-approval/post-publication correction makes the bound old acceptance and receipt non-current without deleting either.
5. Claim/report acceptance and memory promotion are separate typed human decisions. Neither implies the other.
6. Promotion is all-or-nothing across canonical content and authoritative metadata. The request and receipt bind a distinct current exact-byte `ANALYST_ACCEPTANCE` plus the separate `MEMORY_PROMOTION`; absent/stale/revoked/expired/wrong-scope/hash-mismatched acceptance, missing/ambiguous receipt, or partial write is failure requiring reconciliation.
7. `SHADOW_TEST` and `GOLDEN_FIXTURE` artifacts, their seeded errors, and any derivative retaining test-mode provenance cannot be promoted or published.
8. A source document cannot issue instructions, change mode, invoke promotion, select tools, request secrets, or provide authority.
9. Diff-only review never hides changed dependency, materiality, evidence, assumption, uncertainty, calculation, or provenance metadata.
10. Missing source, unavailable calculation trace, failed S13 validation, unresolved contradiction, unknown actor authority, absent task bytes, expired/revoked/superseded decision, stale task/decision/evidence/provenance digest, or cross-record mismatch blocks acceptance/publication/promotion.

## 7. Evidence and typed human-approval gates

| Gate | Approval type | Required authority | Evidence required | Fail-closed rule |
|---|---|---|---|---|
| Initial S15 artifact | `DELEGATED_ARTIFACT_APPROVAL` | Fresh `gpt-5.6-sol` xhigh reviewer under delegated goal authority | Persisted clean review, exact source hashes, review round, timestamp, and artifact hash | This draft remains unapproved until the separate review record exists; this author cannot approve it. |
| Accept a corrected or publishable analytical artifact | `ANALYST_ACCEPTANCE` | Competent human analyst | Immutable task ID/digest, exact production bytes/version/mode/provenance/scope, validation and review evidence, actor authority basis, decision, timestamp, and resolution digest | No active exact-match typed production resolution means the artifact remains unapproved and cannot publish or promote. |
| Promote to canonical thesis/memory | `MEMORY_PROMOTION` | Competent human analyst explicitly authorized to promote | Exact accepted source/scope and target, distinct current analyst-acceptance decision/digest, immutable task/digest, provenance closure, promotion request hash, actor authority basis, decision, timestamp, evidence, and resolution digest | Must be separate from analyst acceptance; the adapter must resolve both at commit, and no valid pair or exact receipt means no promotion. |

Every human approval is a distinct canonical resolution binding actor, human actor type, authority basis, exact scope, decision, timestamp, evidence, and immutable content digest. A model, coordinator, inferred condition, nearby approval, matching text, or successful validation cannot supply or widen it. One approval satisfies at most one declared requirement.

## 8. Reviewer-bias and seeded-error controls

- Capture accepted, edited, rejected, and deferred decisions and correction categories; accepted unchanged is not a standalone quality conclusion.
- Measure false accepts and false rejects on known golden cases, stratified by materiality and epistemic class.
- Seed wrong-period, wrong-unit, wrong-source, unsupported-claim, and fabricated-citation errors only in `SHADOW_TEST` or `GOLDEN_FIXTURE` artifacts.
- Enforce isolation in storage and at the server-side promotion/publication boundary, not only in the UI.
- Record optional external spot review separately; absence is visible and never fabricated.

## 9. Activation and amendment guards

S15 is `active-only` at the pinned draft snapshot because C-05 and C-10 are both `Open`; it owns no `Deferred` register row. This contract activates no deferred capability. Its reference to S19 is an interface boundary, not activation of deferred D-03. Until the relevant promotion transaction is separately activated and available, promotion fails closed.

No evidence-derived mandatory amendment gate is assigned to S15. Any material change to review decisions, authority, correction/supersession semantics, artifact modes, or promotion atomicity still requires amendment and fresh Sol xhigh review; prior approval evidence does not apply to changed bytes.

## 10. Dependencies

Authoritative dependencies are exact:

- C-05 depends on B-13 and B-14.
- C-10 depends on B-03 and B-14.

Interface dependencies are S07 for reviewer-bias/golden-set controls, S10 for source-of-truth authority, S13 for claim validation, S14 for rework/invalidation, S16 for calculation inspection, and S19 for the separately controlled engine-neutral promotion transaction. These references do not transfer primary ownership or activate deferred scope.

## 11. Acceptance tests and verification

| Test | Fixture/action | Required result |
|---|---|---|
| S15-T01 Exact-task/exact-byte decision | Accept version A, then alter one task, artifact, mode, provenance, scope, evidence, or dependency byte. | Acceptance applies only to the complete bound production task and A bytes; every altered or stale binding is unapproved. |
| S15-T02 Review operations | Exercise accept, reject, edit, and defer. | Each creates the specified immutable decision/effect; only an exact-task typed production `ACCEPT` can proceed toward publication. |
| S15-T03 Post-acceptance correction audit | Reject and correct once after acceptance and once after publication. | A new immutable successor and supersession/invalidation records exist; old versions, decisions, and receipts remain readable but non-current; S14 uses the legal origin-specific correction edge; reapproval and a new receipt for republished bytes are required. |
| S15-T04 Source/calculation access | Review source-backed and computed claims. | Exact source jump and calculation trace are available; absent targets block acceptance. |
| S15-T05 Diff completeness | Change claim text, evidence, materiality, assumption, calculation, and provenance independently. | Every change is visible in diff review or mandatory metadata; nothing material is hidden as unchanged. |
| S15-T06 Approval separation and closure | Accept an artifact without promotion approval, then approve promotion separately; attempt to reuse either decision ID for both gates. | First step cannot promote; only distinct current exact-byte `ANALYST_ACCEPTANCE` and `MEMORY_PROMOTION` decisions plus their exact transaction receipt succeed, and reused IDs fail. |
| S15-T07 Split-brain failure | Fail content write, metadata write, response delivery, and retry at each boundary. | No divergent canonical state; ambiguous outcomes reconcile by idempotency key before retry. |
| S15-T08 Seed isolation | Attempt UI and direct-API promotion/publication of shadow/golden artifacts and derivatives. | Every path rejects server-side; production records remain untouched. |
| S15-T09 Authority spoofing | Submit model-, coordinator-, document-, absent-task, stale-, revoked-, expired-, superseded-, wrong-mode-, wrong-provenance-, or wrong-scope approvals. | All fail; only a current competent-human typed production exact-task/exact-scope resolution is accepted. |
| S15-T10 Bias telemetry | Run known seeded-error cases across materiality and epistemic classes. | False accepts/rejects and disposition categories are recorded without treating claims as independent samples. |
| S15-T11 Canonical authority bytes | Verify review-task, review-decision, promotion-request, promotion-decision, and promotion-receipt records with exact bytes; reordered object keys; omitted explicit nulls; added members; duplicate/unsorted references; wrong domain versions; unavailable bytes; bare copied IDs; and one changed bound field without a matching digest. | RFC 8785 key reordering preserves the digest; only complete mutually matching records under recognized domains with canonical reference collections and recomputed digests pass, and every other case fails closed before workflow, publication, or promotion effects. |
| S15-T12 Promotion analyst-acceptance closure | For one valid promotion request, independently substitute absent, stale, revoked, expired, superseded, wrong-scope, wrong-mode, wrong-provenance, artifact-hash-mismatched, task-digest-mismatched, evidence-absent, evidence-stale, evidence-hash-mismatched, and non-distinct analyst acceptance at request, commit, and receipt-return time. | Every substitution aborts without canonical mutation or success receipt; only the separately resolved current exact-byte production `ANALYST_ACCEPTANCE` bound through request and receipt can close promotion. |

Verification is complete only when these tests run against the implementation, correction/supersession and promotion receipts are content-bound, every required human approval is valid, shadow isolation is proven on every route, and a fresh independent Sol xhigh review is clean. Structural presence of this file is not product verification.
