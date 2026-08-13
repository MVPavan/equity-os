# S11 — Run manifest, knowledge cutoff, and layered reproducibility

**Status: DRAFT — AWAITING FRESH SOL XHIGH REVIEW**

## Contract purpose

This specification defines the complete run manifest, mandatory knowledge-time
cutoff enforcement, and layered reproducibility classes for Equity-OS. It is an
implementation contract for C-09, C-15, and C-16. It does not accept those
register rows, approve a published narrative, or claim that stochastic or
LLM-generated text is bit-identically regenerable.

## Authority, ownership, and activation

The v2 decision register is authoritative for live gates. The activated goal
is authoritative for this exact title, path, ownership, lifecycle, and
activation classification. The disposition report supplies the accepted
clarifications below and does not override register wording.

| Field | Exact source text |
|---|---|
| Spec program row | `S11` — `Run manifest, knowledge cutoff, and layered reproducibility` |
| Exact path | `docs/specs/equity-os-s11-run-manifest-cutoff-reproducibility.md` |
| Primary register ownership | `C-09, C-15, C-16` |
| Disposition references | `G-1, M-4, 6.9` |
| Activation classification | `active-only` |

| ID | Blueprint phase | Priority | Decision or action — exact register text | Required evidence / acceptance — exact register text | Dependencies — exact register text | Activation status | Primary owner |
|---|---|---:|---|---|---|---|---|
| C-09 | 1 | High | Implement complete run manifest | Inputs, cutoff, source/evidence-package versions, tools, models, prompts, code versions, costs, calculations, QA, approvals, and exact published-artifact hash are registered | C-16 | Open | S11 |
| C-15 | 1 | Critical | Enforce run knowledge cutoff across stores and tools | SQL/document/memory retrieval applies `knowledge_time <= cutoff`; canonical selections are resolved as of the cutoff so later restatements/corrections do not rewrite history; tool gateway records cutoff capability; tests insert and reject post-cutoff records | B-03, C-02, C-03 | Open | S11 |
| C-16 | 1 | Critical | Implement layered reproducibility and artifact approval | Exact-class operators replay exactly; floating-point/optimization outputs meet declared tolerances; stochastic operators store seeds and test distributions; evidence package reconstructs exactly; approved narrative bytes are immutable and bound to content hash | B-03, B-07, C-08 | Open | S11 |

G-1 is accepted with modification: deterministic calculations, evidence-package
reconstruction, and narrative immutability are three different guarantees.
M-4 is accepted as two policies: controllable store/tool cutoff enforcement is
an implementation requirement; model-weight leakage is an unavoidable
disclosure for historical LLM evaluation and is owned by S25. Correction 6.9
requires exact replay only for exact-class operators, declared tolerances for
floating-point/optimization operators, and stored seeds plus distribution
checks for stochastic operators.

## Scope

This contract owns:

- registration of every run and attempt before evidence access;
- one immutable UTC knowledge cutoff propagated through every store and tool;
- complete input, version, cost, QA, approval, calculation, and artifact
  traceability;
- exact evidence-package reconstruction;
- exact, tolerance-based, and seeded/distributional calculation replay; and
- immutability and content-hash binding of the approved narrative bytes.

## Non-goals

This contract does not define source retention (S10), final observation schema
(S12), calculation formulas (S16), historical model-weight leakage policy
(S25), approval UI (S15), or provider rights (S02). It does not promise clean
historical ignorance from model weights, text-identical regeneration of an LLM
narrative, or permission to retrieve unregistered sources during a run.

## Run and attempt lifecycle

The fixed lifecycle is:

1. allocate `run_id`, declare workflow purpose/version and UTC
   `knowledge_cutoff`, and seal `RunManifest` version 1;
2. allocate `attempt_id`, seal `AttemptManifest` version 1, and seal a new run
   manifest version referencing it before any tool or store access;
3. assemble and seal one S10 evidence package under the same cutoff, then seal
   new attempt and run manifest versions that bind its exact ID/version/hash;
4. execute only registered steps against that package;
5. register calculation traces, QA, human/delegated decisions, costs, and
   failures by sealing new immutable attempt and run manifest versions;
6. after the required approval resolves, bind approved artifact bytes, source
   attempt/package, approval record, and resolution digest in new versions; and
7. seal terminal attempt and run versions as succeeded, failed, cancelled, or
   superseded without deleting any prior version or attempt.

A retry creates a new attempt unless the registered step is explicitly
idempotent and its immutable output is reused by hash. A run cutoff never
changes. A different cutoff creates a different run. Version numbers increase
by exactly one within each manifest family. Version `N>1` names and verifies
the exact ID, version `N-1`, and hash of its immediate predecessor. Null fields
in an early version are resolved only by sealing a successor version; stored
bytes and hashes are never populated or changed in place.

## Run manifest data contract

A `RunManifest` contains at minimum:

| Field | Contract |
|---|---|
| `manifest_schema_version`, `canonicalization_profile` | Exact run-manifest schema version and the `eos-manifest-json-v1` profile imported from S10 |
| `run_id` | Globally unique stable identifier |
| `manifest_version`, `parent_manifest_ref` | Monotonic immutable version and exact immediate predecessor `{run_id, manifest_version, manifest_sha256}`; parent is null if and only if version 1 |
| `workflow_name`, `workflow_version` | Registered fixed workflow and exact version |
| `purpose`, `company_id`, `event_id` | Typed research scope; nullable only where the workflow contract says not applicable |
| `knowledge_cutoff` | Required UTC timestamp fixed before retrieval |
| `registered_at`, `closed_at`, `run_status` | Append-only lifecycle times and closed enum state |
| `input_refs` | Exact initial thesis, policies, registries, company/security mapping, and other input versions |
| `attempt_refs` | Complete collection of exact `{attempt_id, attempt_manifest_version, attempt_manifest_sha256}` refs; each run-manifest version contains exactly one referenced version for every allocated attempt |
| `failure_retry_summary` | Attempts, retry reasons, invalidations, reused outputs, and terminal state |
| `published_artifact_binding` | Run-level `{published_artifact_ref, published_artifact_sha256, attempt_manifest_ref}` projection; valid only when the referenced attempt manifest carries the same artifact ref/hash and the exact package, approval requirement/record, and resolution bindings; null until separately approved in a successor version |
| `manifest_sha256` | Lowercase hexadecimal SHA-256 of the run-manifest preimage defined below |

An `AttemptManifest` contains at minimum:

| Field | Contract |
|---|---|
| `attempt_id`, `run_id`, `parent_attempt_id` | Stable attempt and owning-run identity; exact prior attempt when this is a retry |
| `manifest_schema_version`, `canonicalization_profile` | Exact attempt-manifest schema version and imported `eos-manifest-json-v1` profile |
| `attempt_manifest_version`, `parent_attempt_manifest_ref` | Monotonic immutable version and exact immediate predecessor `{attempt_id, attempt_manifest_version, attempt_manifest_sha256}`; parent is null if and only if version 1 |
| `registered_at`, `closed_at`, `attempt_status` | Immutable-version lifecycle state; version 1 is sealed before access |
| `evidence_package_ref` | Exact `{evidence_package_id, version, manifest_sha256}` for this attempt; null only before successful package sealing or on a terminal pre-package failure |
| `source_versions` | Exact document IDs, versions, byte hashes, capture times, and knowledge times represented by the package |
| `tool_invocations` | Tool identity/version, cutoff capability, request digest, response/evidence ref or quarantine ref, start/end times, status, and error category |
| `model_invocations` | Provider/model identity, effective version where available, prompt/template ID and hash, parameters, tool policy, input/output refs, token/cost/latency, and status |
| `code_versions` | Repository commit/tree hash, dirty-state digest where permitted, dependency lock hash, runtime/container identity, and schema/migration version |
| `calculation_trace_refs` | Registered S16 trace IDs, operator versions, replay classes, inputs, assumptions, and outputs |
| `qa_refs` | Validator, golden-fixture, contradiction, citation, calculation, and review-result evidence |
| `approval_refs` | Exact typed requirement and matched approval-record data. Human decisions include `human_review_id`, `resolution_decision_id`, and `resolution_content_sha256`; only `DELEGATED_ARTIFACT_APPROVAL` uses delegated review evidence and null human-resolution fields |
| `cost_summary` | Model, tool, provider, and infrastructure units/currency under S08 definitions |
| `step_outputs`, `failure_state`, `reused_output_proof` | Exact output hashes, invalidation/failure state, and proof for any idempotent reuse |
| `published_artifact_binding` | Artifact ref/hash, exact package ref, approval requirement and record IDs, and human resolution ID/content hash when human approval is required; null until all required one-to-one approvals are `SATISFIED` |
| `attempt_manifest_sha256` | Lowercase hexadecimal SHA-256 of the attempt-manifest preimage defined below |

Tool and model records are structured audit records, not raw scratchpads. Each
new attempt-manifest version must be referenced by a new run-manifest version;
failure to persist either side atomically leaves the new version unusable.

### Canonical digest preimages

Both manifest types import `eos-manifest-json-v1` exactly from S10, including
its key and collection ordering, timestamp, Unicode, number, null/absence, and
unknown-field rules. The `RunManifest` hash input is ASCII
`EquityOS:RunManifest:v1\n` followed by the canonical JSON object with
`manifest_sha256` removed entirely. The `AttemptManifest` hash input is ASCII
`EquityOS:AttemptManifest:v1\n` followed by the canonical JSON object with
`attempt_manifest_sha256` removed entirely. Each stored digest is the lowercase
hexadecimal SHA-256 of exactly its respective input. Profile/version mismatch,
non-canonical bytes, omitted nullable fields, or a predecessor/ref digest
mismatch fails before the manifest version can be registered or consumed.

## Knowledge-cutoff contract

- `knowledge_cutoff` means the latest knowledge time a run may observe. It is
  independent of valid time, capture time, publication date, event date, and
  run registration time.
- Every SQL query includes `knowledge_time <= :cutoff`. Canonical observation,
  fact, relationship, event, claim, and policy selection is evaluated as of
  that cutoff rather than from a mutable current pointer.
- Document retrieval admits only versions whose recorded first-seen/knowledge
  time is at or before the cutoff. Search indices must filter authoritative
  metadata before returning content.
- Memory retrieval applies the same cutoff to every returned artifact and
  derived chunk. A current thesis version created after the cutoff is excluded
  even if it describes an earlier valid period.
- The tool gateway declares each tool invocation `CUTOFF_NATIVE`,
  `ARCHIVED_SOURCE_ONLY`, or `NOT_CUTOFF_CAPABLE`. The first two require exact
  enforcement evidence. `NOT_CUTOFF_CAPABLE` is denied for historical replay
  and for authoritative evidence retrieval. A current-period workflow may
  invoke it only when workflow policy and source rights explicitly permit a
  non-authoritative exploratory lane;
  its response is quarantined and cannot enter an evidence package, fact,
  claim, calculation, QA proof, approval evidence, or published artifact unless
  every admitted record independently carries authoritative knowledge-time
  proof satisfying `knowledge_time <= cutoff`. Invocation observation time is
  audit metadata, not cutoff proof.
- Downstream stages use the sealed evidence package and cannot fetch new
  evidence. A missing source creates an unresolved question or failure, not an
  unregistered retrieval.

Canonical selection queries must take `(measurement_key, cutoff)` and return
exactly one selection from S12's immutable linear transition chain satisfying
`effective_from_knowledge_time <= cutoff` and either having no valid successor
or a successor with `cutoff < successor.effective_from_knowledge_time`. Zero
matches, multiple matches, a fork, a stale predecessor, or an incomplete
transition fails closed. A later restatement, correction, parser result, or
policy change never rewrites a historical run.

## Layered reproducibility contract

| Layer | Required guarantee | Proof |
|---|---|---|
| Exact-class calculation | Same registered inputs, assumptions, operator, code, runtime, and policy produce exactly equal typed output | Byte/value equality plus trace-hash equality |
| Floating-point or optimization calculation | Output satisfies registered absolute/relative tolerance, convergence criteria, solver/runtime constraints, and invariant checks | Tolerance report bound to both traces |
| Stochastic calculation | Seed, generator/algorithm, environment, sample policy, and distribution assertions are stored | Seeded replay where supported plus predeclared distribution checks; no universal bit-exact claim |
| Evidence package | The exact manifest and every referenced authoritative version reconstruct by ID and hash | Full dependency-closure hash check |
| Approved narrative/report | The exact approved/published bytes are retrievable and immutable | Artifact byte hash equals the manifest's `published_artifact_sha256` |
| Narrative regeneration | Optional new draft from the same approved claim/evidence set is diffed and reviewed | New artifact/version and approval; text identity is not required or implied |

Reproducibility proof is invalid if an input is missing, a dependency/runtime
is unpinned beyond the declared replay policy, the tolerance was selected
after seeing the result, a seed/distribution check is absent, or approved bytes
cannot be retrieved by their recorded hash.

## Invariants and fail-closed behavior

- No store or tool access occurs before a persisted run and attempt with an
  immutable cutoff.
- Every retrieved record carries knowledge-time proof at or before the cutoff.
  Missing/ambiguous knowledge time is excluded, not treated as old enough.
- A tool that cannot prove the required cutoff behavior is denied for that
  authoritative lane. Quarantined output remains non-authoritative until each
  admitted record supplies independent cutoff proof; a copied
  `cutoff_aware=true` label or invocation time is not proof.
- Every calculation chooses exactly one registered replay class before
  execution. Missing class, tolerance, runtime, seed, or distribution policy
  blocks authoritative output.
- Every manifest and predecessor reference resolves and matches its recorded
  immutable hash. Partial, non-canonical, forked, stale-parent, or mismatched
  manifests cannot advance to review or publication.
- Package, invocation, QA, approval, and artifact state is attempt-owned. A run
  manifest only references or projects that state; any run/attempt/package or
  artifact-binding disagreement invalidates the graph rather than choosing one.
- Published bytes are immutable. Any edit creates a new artifact hash, review,
  and analyst approval. Late approval or artifact state creates successor
  attempt/run manifest versions; changing any prior manifest bytes or hash in
  place is forbidden.
- QA and approval omissions remain explicit. A successful workflow step cannot
  synthesize or imply an approval.
- Model-weight leakage is never represented as controllable store/tool leakage
  prevention. Historical LLM results cannot be called historically ignorant
  merely because cutoff controls passed.

## Evidence and typed approval gates

| Gate | Required evidence | Approval type and authority | Fail-closed result |
|---|---|---|---|
| S11 delegated artifact approval | Fresh clean Sol xhigh review bound to this file's current bytes; exact C-09/C-15/C-16 and G-1/M-4/6.9 coverage; declared run/attempt interfaces, digest preimages, cutoff predicates, fixture catalogue, and test specifications; no product execution result is required | `DELEGATED_ARTIFACT_APPROVAL`; fresh Sol xhigh under delegated goal authority | Spec remains draft; no personal user approval is inferred |
| Reproducibility policy | Operator inventory with predeclared replay class, tolerances/seeds/distribution checks, runtime policy, and test evidence | `DOMAIN_EXPERT_ACCEPTANCE` by a competent human for the covered calculation domain where judgment is required | Affected operator cannot produce authoritative computed facts |
| Approved narrative bytes | Sealed package, QA, exact artifact bytes/hash, diff, and review evidence | `ANALYST_ACCEPTANCE` by the responsible analyst for that artifact | `published_artifact_binding` remains null; no publication or promotion |
| Memory promotion, if requested | Approved narrative hash plus S15 transaction evidence | separate `MEMORY_PROMOTION` human decision | Artifact approval does not change canonical thesis memory |
| Production enablement | Cutoff-integration, recovery, monitoring, and replay evidence for the exact deployment | `PRODUCTION_APPROVAL` by competent human operations authority when production use is proposed | Deployment remains non-production |

Each non-delegated approval must resolve through the canonical human-review
artifact with exact actor, authority basis, scope, decision, timestamp, and
evidence. One approval record satisfies one requirement. Fresh Sol review is
not analyst, domain, production, or promotion authority.

## Activation and Deferred guard

S11 is active-only: C-09, C-15, and C-16 were all `Open` at activation. It has
no Deferred component or activation predicate. M-4 does not transfer ownership
of E-10 from S25 and does not activate controlled quant validation or any
historical-alpha claim. Store/tool cutoff implementation may proceed when its
dependencies and approvals pass; conditional historical-evaluation capability
may not be inferred from this spec.

## Acceptance tests and verification

Initial delegated S11 approval reviews this contract, its declared fixture
catalogue, and the test specifications below for completeness and internal
consistency. It does not require adapters, a gateway, manifest persistence,
replay operators, or artifact storage to exist or execute.

Before C-09, C-15, or C-16 acceptance, and at the corresponding implementation
phase gates, executable fixtures must prove:

1. no retrieval is possible without a persisted run, attempt, and cutoff;
2. SQL, document, memory, fact, event, relationship, policy, and index adapters
   exclude deliberately inserted post-cutoff records;
3. canonical selection at an earlier cutoff is unchanged after a later
   restatement, correction, or parser re-extraction;
4. the gateway rejects a non-cutoff-capable tool in historical and authoritative
   lanes; a permitted current-period exploratory response stays quarantined
   unless every admitted record independently proves cutoff eligibility, and
   every call records its effective capability and quarantine state;
5. independent producers serialize identical run and attempt manifests to the
   same preimage bytes/digests across ordering, timestamp, Unicode, number,
   null, and absent-field cases, and reject every non-canonical case;
6. multiple attempts bind their own exact package ID/version/hash; late QA,
   approval, artifact, failure, and terminal state produce immutable successor
   attempt/run versions with exact predecessor hashes and no in-place update;
7. a manifest graph captures every source/package/tool/model/prompt/code/cost/
   calculation/QA/approval/artifact field or an explicit valid null state;
8. exact-class, tolerance-class, and stochastic-class fixtures each pass their
   own predeclared policy and fail under missing policy inputs;
9. an evidence package reconstructs exactly, while missing or changed content
   blocks completion;
10. approved bytes round-trip by hash and bind their exact attempt, package,
    approval record, and resolution digest; regenerated prose is a new
    unapproved version even when its claims match;
11. changing the cutoff creates a new run rather than mutating the old one;
12. concurrent or partial canonical-selection transitions yield exactly one
    valid as-of result or fail closed, never an overlapping/forked selection;
    and
13. a source-to-spec audit finds C-09, C-15, C-16, G-1, M-4, and 6.9 exactly
    once under S11 and does not absorb E-10.

C-15 acceptance requires live adapter tests, not only manifest inspection.
C-16 acceptance requires replay evidence and the relevant typed approvals.
C-09 cannot be accepted until C-16 is satisfied and a complete real manifest
fixture binds an exact published-artifact hash.

## Dependencies and handoffs

- S10/B-03 defines authoritative stores and sealed evidence packages.
- S09/C-02 supplies immutable document versions, hashes, and first-seen times.
- S12/C-03 supplies append-only observations, revisions, and as-of selection.
- S13 supplies claim and vocabulary versions represented in manifests.
- S14 supplies run/attempt transitions and resumable failure handling.
- S15 supplies canonical approval, correction, and promotion evidence.
- S16/B-07/C-08 supplies operator semantics and calculation traces.
- S25/E-10 owns the disclosure and policy for model-weight leakage and claims
  made from historical LLM evaluation.

No consumer may use this draft as evidence that cutoff or reproducibility gates
have passed.
