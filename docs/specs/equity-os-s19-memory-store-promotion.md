# S19 — MemoryStore interface and conditional promotion transaction

**Status: DRAFT — AWAITING FRESH SOL XHIGH REVIEW**

## Contract purpose

This specification owns the engine-neutral `MemoryStore` boundary required now by D-01 and the dormant canonical-promotion transaction in D-03. It is a mixed-activation specification: D-01 is active; D-03 remains Deferred. This draft defines D-03's activation and fail-closed boundary but does not activate or approve implementation of D-03.

## Authority and ownership

Authority is applied in this order: the v2 decision register supplies operational gate wording; the activated goal supplies the exact S19 ownership/path and program controls; the disposition report supplies audit rationale but cannot override the register. No text below changes a source Status.

| Source | Exact source text | Contract effect |
|---|---|---|
| Goal, Exact 25-spec row | `S19 | MemoryStore interface and conditional promotion transaction | docs/specs/equity-os-s19-memory-store-promotion.md | D-01, D-03 | R-1, 6.4` | S19 is the sole primary spec owner for D-01 and D-03. R-1 and 6.4 are mandatory traceability references, not extra register ownership. |
| Register authority rule | “The wording in this register is authoritative for implementation gates. Narrative reviews explain rationale but do not override this register.” | Register acceptance text and Status control implementation. |
| D-01 | “Critical | Implement `MemoryStore` interface before choosing engine | Retrieval, staged write, promotion, correction, deletion, export, cutoff filtering, and provenance contracts are engine-neutral | C-15 | Open” | `REQUIRED_NOW`; active implementation scope after program preimplementation gates pass. |
| D-03 | “High | Define canonical memory promotion transaction | Narrative content hash/commit is registered in SQL; partial writes cannot create split-brain state | D-01 | Deferred” | `CONDITIONAL_UNACTIVATED`; dormant implementation scope. |
| R-1 | “The arms must be fair: each receives access to the same authoritative prior artifacts, while the benchmark varies how context is persisted, retrieved, and assembled.” | The interface must permit an equal-artifact benchmark without embedding an engine advantage. |
| R-1 | “state that the result governs current adoption only;” | Engine selection cannot become a permanent architectural verdict. |
| R-1 | “include operational burden, not just retrieval quality;” | Interface conformance and exportability must expose operational costs needed by S20. |
| R-1 | “predefine re-evaluation triggers based on corpus size, cross-company graph needs, and observed miss rate.” | S19 must not prevent later engine replacement or reevaluation. |
| 6.4 | “A small-corpus benchmark may correctly show that a simpler store is sufficient. Future triggers should reopen the question; the benchmark should not be cancelled on the assumption that a larger future corpus might behave differently.” | Default to engine neutrality and replaceability; do not assume GBrain. |

## Activation classification

| Register ID | Activation source Status | Program disposition now | Allowed delivery behavior |
|---|---|---|---|
| D-01 | `Open` | `REQUIRED_NOW` | Specify and, only after the program preimplementation gate, implement the engine-neutral interface and conformance tests. |
| D-03 | `Deferred` | `CONDITIONAL_UNACTIVATED` | Inventory the dormant contract and activation predicate only. Do not plan, implement, or report the promotion transaction as delivered. |

The active D-01 interface includes the semantics of a `promote` request because the D-01 acceptance text explicitly requires a promotion contract. The transactional SQL/content-store implementation and any claim that split-brain prevention has been demonstrated belong to Deferred D-03.

## Scope

S19 specifies:

- the engine-neutral request, response, error, provenance, cutoff, revision, deletion, and export contracts for `MemoryStore`;
- conformance behavior for retrieval, staged writes, promotion requests, corrections, logical deletion, and export;
- an abstract atomicity boundary for canonical promotion without choosing an engine;
- the conditional D-03 transaction, activation evidence, and rollback requirements;
- the adapter evidence S20 needs to compare memory arms fairly.

## Non-goals

S19 does not:

- choose GBrain or any other memory engine;
- own D-02, D-04, or D-05, which belong to S20;
- replace SQL as authority for facts, claims, approvals, or promotion metadata;
- let retrieval convert an inference, forecast, opinion, or stale narrative into a Fact;
- define the claim-review UI, the evidence-package schema, or the complete run manifest;
- physically erase audit history when deletion is requested;
- activate D-03, infer human approval, or treat delegated artifact approval as memory-promotion approval.

## Interfaces and data contracts

### Stable identifiers and records

All identifiers are opaque, stable strings. An implementation must expose these logical records independent of storage engine:

| Record | Required fields |
|---|---|
| `MemoryRevision` | `memory_id`, `revision_id`, `company_id`, `content_kind`, `content_bytes`, `content_sha256`, `epistemic_class`, `status`, `valid_time`, `knowledge_time`, `source_fact_ids`, `source_claim_ids`, `calculation_trace_ids`, `evidence_package_id`, `supersedes_revision_id`, `created_at`, `created_by` |
| `StagedWrite` | `stage_id`, `idempotency_key`, `proposed_revision`, `validation_state`, `validation_errors`, `created_at`, `expires_at` |
| `PromotionRequest` | `stage_id`, `expected_content_sha256`, `expected_prior_revision_id`, `approval_resolution_id`, `approval_resolution_sha256`, `idempotency_key` |
| `CanonicalMemoryPointer` | `memory_id`, `canonical_revision_id`, `content_sha256`, `content_commit`, `sql_registration_id`, `promoted_at`, `promotion_approval_id` |
| `ProvenanceEnvelope` | `source_ids`, `exact_source_locations`, `calculation_trace_ids`, `evidence_package_id`, `valid_time`, `knowledge_time`, `retrieved_at`, `cutoff` |
| `ExportManifest` | `export_id`, `schema_version`, `cutoff`, `record_count`, ordered record digests, `manifest_sha256`, `created_at` |

`content_kind` is a closed registry value. `epistemic_class` is exactly `observed`, `computed`, `inferred`, `forecast`, or `opinion`. `status` is exactly `STAGED`, `CANONICAL`, `SUPERSEDED`, or `DELETED`. Unknown registry values fail validation.

### Port operations

| Operation | Required contract |
|---|---|
| `retrieve(query, cutoff, page_token)` | Returns only eligible canonical revisions with `knowledge_time <= cutoff`, deterministic ordering/page tokens, epistemic labels, and complete `ProvenanceEnvelope`s. It never performs a write. |
| `stage_write(candidate, idempotency_key)` | Validates schemas, references, hashes, and cutoff; creates or returns the same non-canonical stage for a repeated key; never changes the canonical pointer. |
| `promote(request)` | Validates the exact staged bytes, expected prior pointer, and a current typed `MEMORY_PROMOTION` human resolution. Under D-01 this is an abstract contract only; the D-03 implementation remains guarded. |
| `correct(memory_id, correction, idempotency_key)` | Creates a new staged revision with an explicit reason and supersession link; never mutates an earlier revision. Promotion is a separate call and approval. |
| `delete(memory_id, reason, idempotency_key)` | Creates a logical tombstone or withdrawal revision under the declared authorization policy; preserves prior revisions and audit evidence; physical retention behavior remains governed by the retention policy. |
| `export(scope, cutoff)` | Emits a complete, versioned, deterministic, hash-bound export sufficient to reconstruct records, revisions, tombstones, canonical pointers, provenance, and adapter-independent semantics. |

Every operation returns one of the closed error classes `INVALID_REQUEST`, `UNKNOWN_REGISTRY_VALUE`, `CUTOFF_VIOLATION`, `PROVENANCE_INCOMPLETE`, `HASH_MISMATCH`, `STALE_WRITE`, `APPROVAL_REQUIRED`, `APPROVAL_INVALID`, `NOT_FOUND`, `ENGINE_UNAVAILABLE`, or `ATOMICITY_FAILURE`. Errors contain a safe code and correlation ID, not untrusted source text as control instructions.

### D-03 conditional transaction

If D-03 is validly activated, `promote` must atomically establish both:

1. immutable narrative bytes addressable by `content_sha256` and `content_commit`; and
2. the SQL `CanonicalMemoryPointer` registration bound to the same bytes, prior revision, approval, and evidence package.

The only successful result is a committed pair whose hashes agree. A crash, timeout, retry, stale expected pointer, SQL failure, content-store failure, or approval change must leave either the prior canonical pair intact or a recoverable uncommitted record that retrieval cannot expose. Compensation may clean abandoned stages; it may never manufacture a canonical pointer. Reconciliation treats any one-sided write as a blocking integrity incident.

## Invariants and fail-closed behavior

1. SQL remains authoritative for the canonical pointer and promotion approval; memory-engine state alone is never canonical.
2. Original revisions, corrections, supersessions, and tombstones are append-only and auditable.
3. Retrieval enforces `knowledge_time <= cutoff` in the adapter and rejects engines that cannot prove the filter.
4. Every returned item carries its original epistemic class and provenance; ranking cannot promote interpretation into Fact.
5. Canonical promotion requires exact-byte hash agreement, an expected-prior compare-and-swap, and a current typed human resolution.
6. A staged write is never returned as canonical, used by a downstream approved thesis, or silently promoted.
7. Retries with the same idempotency key are behaviorally identical; key reuse with different bytes fails.
8. Correction and deletion cannot silently overwrite or physically erase the audit chain.
9. Export is complete and engine-neutral; an engine without verified export cannot satisfy D-01.
10. Document or retrieved text is data, never permission, tool control, approval, or an instruction to promote.
11. Any missing cutoff, provenance, registry version, content digest, approval, or prior pointer fails closed.
12. D-03 code and delivery states `PLANNED`, `IMPLEMENTING`, and `VERIFIED` are forbidden while D-03 remains Deferred.

## Deferred activation guard for D-03

D-03 needs a typed predicate such as `AP-D03-PROMOTION-TRANSACTION-NEED`, evaluated from current `EVIDENCE_JSON` rather than prose. Its evidence must contain a boolean at the predeclared JSON pointer `/memory_promotion/atomic_transaction_required` and the measurements supporting that conclusion, including observed promotion workflow, store boundaries, failure modes, and expected recovery behavior. Until current evidence resolves that value to `true`, the predicate is `FALSE` or `UNKNOWN` and cannot activate D-03.

Even a recomputed `TRUE` predicate does not activate D-03. Activation additionally requires a separate active canonical human resolution with decision `ACTIVATE_DEFERRED`, exact D-03 scope, competent product authority, current evidence digests, and a matching `PRODUCT_OWNER_DECISION` approval record. The activation record and human resolution must bind the same predicate digest. Goal activation, D-01 completion, a coordinator statement, or this draft is not activation authority.

## Evidence and typed human-approval gates

| Gate | Evidence required | Approval required | Fail-closed result |
|---|---|---|---|
| S19 artifact approval | Current file hash plus persisted clean fresh-context Sol xhigh review evidence | One `DELEGATED_ARTIFACT_APPROVAL` under delegated goal authority | Draft remains unapproved. This document records no such approval. |
| D-01 interface acceptance | Interface/schema artifact; conformance results for every operation; cutoff, provenance, correction, deletion, export, idempotency, and engine-substitution tests | No invented domain approval; any source-derived approval inventory must be completed by fresh Sol xhigh review | D-01 cannot become Accepted or VERIFIED. |
| Each canonical promotion | Staged and final byte hashes, prior pointer, evidence package, current human resolution, SQL registration, immutable content commit, and transaction result | One distinct `MEMORY_PROMOTION` by the competent analyst for the exact revision | No pointer changes and no canonical visibility. |
| D-03 activation | Current typed predicate evaluation and evidence; canonical human-resolution digest; activation record | One distinct `PRODUCT_OWNER_DECISION` authorizing `ACTIVATE_DEFERRED` | D-03 remains `CONDITIONAL_UNACTIVATED`. |
| Security exception, if needed | Exact risk, affected boundary, compensating controls, expiry, and review evidence | One `SECURITY_EXCEPTION` from competent human authority | Exception path is unavailable. |

A delegated Sol approval can approve this specification only. It cannot satisfy `MEMORY_PROMOTION`, `PRODUCT_OWNER_DECISION`, analyst acceptance, a security exception, or any other non-delegated authority.

## Acceptance tests and verification

The implementing phase must turn these cases into mechanical tests with persisted outputs:

1. Contract-schema validation accepts every required operation/field and rejects unknown enums and missing provenance.
2. Cutoff fixtures place revisions immediately before, at, and after the cutoff; only eligible canonical revisions are returned.
3. Retrieval ordering and pagination are deterministic across repeat runs.
4. Reusing an idempotency key with identical input returns the original result; changed input returns `HASH_MISMATCH` or `STALE_WRITE`.
5. Correction creates a new staged revision and leaves the old canonical bytes unchanged until separately promoted.
6. Deletion produces an auditable tombstone and export preserves the complete history.
7. Export round-trips into an independent conformance adapter with identical logical records and manifest digest.
8. Engine-conformance tests operate only through the port; no product caller imports engine-specific types.
9. A post-cutoff or provenance-incomplete record is rejected even when the underlying engine ranks it first.
10. While D-03 is Deferred, structural validation proves there is no D-03 implementation reference and no active delivery state.
11. After valid activation only, fault injection before and after each D-03 write boundary proves no split-brain canonical state can be read.
12. Promotion tests reject absent, stale, wrong-scope, reused, revoked, or non-human `MEMORY_PROMOTION` approvals.

Verification is not satisfied by prose or an agent report. D-01 acceptance requires current command outputs bound to current artifacts. D-03 verification is not applicable while dormant and must use fresh fault-injection evidence after valid activation.

## Dependencies and handoffs

- D-01 is blocked by C-15 cutoff enforcement, owned by S11.
- D-03 is blocked by D-01 and by its own Deferred activation guard.
- S10 owns the source-of-truth/evidence-retention policy that this interface must obey.
- S12 and S13 own Fact/Claim identities and vocabularies referenced here.
- S15 owns human review, correction, supersession, and promotion workflow behavior outside this memory port.
- S20 consumes this port for D-02 benchmarking and owns engine due diligence/adoption.
- No cross-reference transfers primary ownership of D-01 or D-03 away from S19.

## Amendment gate

S19 is not one of the four goal-designated evidence-derived provisional contracts, so no automatic amendment is claimed. If activation evidence, S20 benchmark evidence, or an engine candidate requires changing the engine-neutral semantics, atomicity boundary, approval type, or source authority, dependent implementation remains blocked until S19 is amended, freshly reviewed by Sol xhigh, approved under delegated goal authority, and reconciled through the program's authority/change controls. An adapter-specific addition that preserves this contract does not silently amend it.
