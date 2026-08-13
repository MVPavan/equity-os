# S10 — Source-of-truth matrix, evidence packages, and record-retention policy

**Status: DRAFT — AWAITING FRESH SOL XHIGH REVIEW**

## Contract purpose

This specification defines which store is authoritative for each Equity-OS
record class, how a frozen evidence package is assembled and versioned, and
which records may or may not be retained. It is an implementation contract for
B-03 and C-11. It does not approve those register rows, select a future storage
engine, or grant any human approval.

## Authority, ownership, and activation

Authority order is: the v2 decision register for live implementation gates;
the activated goal for exact spec ownership, path, lifecycle, and amendment
rules; and the disposition report for the stated audit treatment. Narrative
material cannot override the register.

| Field | Exact source text |
|---|---|
| Spec program row | `S10` — `Source-of-truth matrix, evidence packages, and record-retention policy` |
| Exact path | `docs/specs/equity-os-s10-source-of-truth-evidence-retention.md` |
| Primary register ownership | `B-03, C-11` |
| Disposition references | `T-3, R-5` |
| Activation classification | `active-only` |

| ID | Blueprint phase | Priority | Decision or action — exact register text | Required evidence / acceptance — exact register text | Dependencies — exact register text | Activation status | Primary owner |
|---|---|---:|---|---|---|---|---|
| B-03 | 0.5 | Critical | Establish source-of-truth matrix | Approved authority table for raw documents, SQL facts, claims, calculations, narrative memory, derivative indices, evidence packages, and reports | — | Open | S10 |
| C-11 | 1 | High | Prohibit product dependence on raw model scratchpads | Stored records are evidence, tool traces, structured decisions, QA results, and concise rationales | — | Open | S10 |

Disposition T-3 is accepted: the implementation register owns live gate
wording; the consolidated review remains rationale, not an operational
checklist. Disposition R-5 is retained only as an operational note: SQLite is
appropriate for the vertical slice and small pilot, and storage migration is
reconsidered on measured triggers rather than treated as a new critical
decision.

## Scope

This contract owns:

- the authority matrix for raw documents, observations/facts, claims, events,
  calculations, evidence packages, run manifests, approvals, approved
  narratives/reports, and derivative retrieval indices;
- immutable, content-addressed evidence-package manifests and versioning;
- retention and deletion behavior for authoritative, derived, operational,
  and prohibited records;
- prevention of split-brain authority and reconstruction from non-authoritative
  stores; and
- the storage scale-up decision record and its objective trigger inputs.

## Non-goals

This contract does not define the final observation/fact schema (S12), claim
schema (S13), document ingestion mechanics (S09), calculation semantics (S16),
run-manifest/cutoff rules (S11), promotion workflow (S15), workflow state
machine (S14), or a specific replacement for SQLite. It does not make a vector
index, cache, model output, prompt transcript, or raw scratchpad authoritative.

## Source-of-truth matrix

| Record class | Authoritative representation | Permitted derivative | Write authority and conflict rule | Retention rule |
|---|---|---|---|---|
| Original source document | Immutable object bytes plus document registry identity, hash, origin, capture/first-seen times, and parser metadata | Text/OCR chunks and search index entries keyed to document hash | S09 ingestion registers once; a changed source is a new version, never an overwrite | Retain original bytes and registry history; deletion requires an explicit rights/retention decision and leaves a tombstone and audit record |
| Observation and fact | Append-only SQL records using S12 identity, valid time, knowledge time, revision family, and canonical-selection history | Read models, caches, aggregates, and embeddings | Only reconciliation creates or changes canonical selection; conflicting observations coexist | Retain every revision, correction reason, and supersession edge; never hard-delete history as a correction |
| Claim | Append-only SQL claim records using the registered vocabulary and evidence links defined by S13 | Search/document projections | Claim review/promotion workflows create new status or superseding records; display text cannot replace structured identity | Retain all reviewed versions, dispositions, evidence directions, and supersession history |
| Event or corporate action | Versioned SQL event records | Timelines and alerts | Event authority follows S17; conflicts remain explicit until reconciled | Retain event versions, identifier mappings, and reconciliation history |
| Calculation | Registered calculation trace containing inputs, assumptions, operator/code/runtime version, replay class, and output | Rendered tables and cached results | Only S16 registered compute is authoritative; an LLM-produced number is never a calculation record | Retain every trace referenced by a fact, claim, evidence package, or report |
| Evidence package | Immutable manifest plus content-addressed references to exact source, fact, claim, and calculation versions | Materialized bundle/cache regenerated from the manifest | One package version is frozen per run attempt; any input change creates v(N+1) | Retain every referenced manifest and its dependency closure; a superseding package never mutates a prior package |
| Run manifest | Append-only SQL record satisfying S11 | Human-readable run summary | The workflow registrar appends; downstream stages cannot rewrite earlier inputs or cutoff | Retain every run, attempt, failure, cost, QA, approval, and published-artifact binding |
| Approval and review decision | Append-only SQL decision metadata bound to canonical human-review or delegated-review evidence | UI views and reports | Only the authority defined by the typed approval contract may decide; copied labels have no authority | Retain grants, denials, revocations, expiry, evidence, actor, scope, and timestamp |
| Approved thesis/narrative/report | Immutable approved bytes in versioned artifact storage, bound by hash from SQL | Rendered HTML/PDF and retrieval chunks | Analyst approval/promotion is separate from drafting; changing bytes requires a new version and approval | Retain every approved version and exact published-artifact hash; drafts follow explicit draft retention |
| Derivative retrieval index | Rebuildable index keyed only to authoritative IDs, versions, hashes, cutoff fields, and epistemic class | Cache only | Never accepts canonical writes; disagreement with an authoritative store invalidates and rebuilds the index | May be dropped and rebuilt; it cannot be sole evidence or sole copy |
| Tool/model trace | Structured invocation, inputs by reference, outputs, versions, timing, and errors needed for audit | Diagnostic views | Registered by the run workflow; cannot directly promote facts or claims | Retain when referenced by QA, evidence, an approval, a failure, or policy; otherwise apply the approved operational retention schedule |
| Raw model scratchpad or hidden reasoning | None; prohibited as a product dependency | None | No product component may read it as state, evidence, approval, or rationale | Do not persist as a product record; if platform diagnostics incidentally retain it, isolate it from product stores and apply platform/security retention controls |

For each record class, the authoritative representation is singular by role,
not necessarily by physical database. Cross-store references use stable IDs and
content hashes. No two stores may both accept canonical writes for the same
field or lifecycle transition.

## Evidence-package contract

An `EvidencePackageManifest` contains at minimum:

| Field | Contract |
|---|---|
| `evidence_package_id`, `version` | Stable package identity and monotonically increasing immutable version |
| `run_id`, `attempt_id` | Owning run and attempt from S11 |
| `knowledge_cutoff` | UTC cutoff enforced by S11; never inferred from package creation time |
| `created_at` | UTC package-freeze time |
| `document_refs` | Ordered document IDs, exact versions, byte hashes, source locations where scoped, and knowledge times |
| `fact_refs` | Exact fact/observation IDs, selected revisions, definition versions, and selection-as-of-cutoff proof |
| `claim_refs` | Exact claim IDs and versions included as prior approved analytical state; drafted claims are separately marked |
| `calculation_refs` | Exact trace IDs and code/runtime versions |
| `policy_refs` | Materiality, metric/predicate registry, retention, and source-authority policy versions |
| `parent_package_id` | Prior immutable package when this version is rework; null only for the first package |
| `change_set` | Typed added/removed/superseded references and invalidation reasons |
| `manifest_sha256` | Hash of canonical manifest bytes excluding this field |

Package assembly is a transaction: resolve all authoritative references as of
the cutoff, validate hashes and policy versions, persist the manifest, then
seal it. Partial assembly is not a package. A downstream step consumes one
sealed manifest hash and performs no new evidence retrieval. Changed evidence,
human rejection, source correction, or recalculation creates a new manifest;
the prior package remains reproducible and auditable.

## Retention, correction, and deletion

1. Corrections append new records and explicit supersession or canonical-
   selection edges; they do not overwrite evidence.
2. Records in an approved package, calculation trace, review, approval, or
   published artifact are retention-pinned with their dependency closure.
3. A legal/data-rights deletion request is a typed human gate. Fulfilment
   records the authority, scope, affected hashes/IDs, tombstone, time, and the
   packages or artifacts that can no longer be reconstructed. The system must
   not claim reproducibility after required bytes are removed.
4. Derivative indices and caches may be deleted without approval only when
   they are demonstrably rebuildable from retained authoritative records.
5. Draft narrative retention is policy-versioned and cannot silently promote a
   draft or erase an approval trail.
6. Secrets, credentials, raw scratchpads, and document-originated instructions
   are never stored in an evidence package.

## Invariants and fail-closed behavior

- An authoritative record is addressable by stable ID and immutable version or
  content hash; a mutable "latest" pointer is never sufficient evidence.
- A fact, claim, calculation, or report cannot cite an index row, cache entry,
  prose summary, or scratchpad as its sole authority.
- Every package reference resolves, matches its digest, is permitted by the
  retention/rights policy, and satisfies `knowledge_time <= cutoff`; otherwise
  sealing and downstream execution fail.
- A package cannot be edited after sealing. Hash mismatch, missing dependency,
  partial write, unregistered policy version, or cross-store disagreement
  invalidates it and blocks publication.
- Deletion never masquerades as correction; correction never destroys prior
  history; supersession never implies physical erasure.
- A derivative index cannot perform promotion, correction, approval, or
  canonical selection. Any attempted authoritative write through it is denied.
- Model output remains a proposal until a typed record, evidence link, QA path,
  and required approval exist. Raw model scratchpads are never required to
  resume or audit a workflow.

## Evidence and typed approval gates

| Gate | Required evidence | Approval type and authority | Fail-closed result |
|---|---|---|---|
| S10 delegated artifact approval | Fresh clean Sol xhigh review bound to this file's current bytes, exact source rows, T-3/R-5 treatment, and review evidence | `DELEGATED_ARTIFACT_APPROVAL`; fresh Sol xhigh under delegated goal authority | Spec remains draft; no personal user approval is inferred |
| B-03 matrix approval | Completed authority table, conflict tests, package fixture, and cross-spec interface evidence | `PRODUCT_OWNER_DECISION` by a competent human product/process owner for the exact matrix scope | B-03 cannot become Accepted; dependent authoritative stores remain blocked |
| Retention/deletion policy | Versioned retention schedule plus dependency-impact and reconstruction analysis | `DATA_RIGHTS_APPROVAL` for source-rights constraints and `LEGAL_REVIEW` only where the intended retention/deletion mode requires it; distinct human resolutions | Affected data cannot be ingested, deleted, or represented as reconstructable |
| Approved narrative/report retention | Exact bytes, content hash, package/run bindings, and review disposition | `ANALYST_ACCEPTANCE` by the responsible analyst; promotion, if requested, is a separate `MEMORY_PROMOTION` decision | Artifact remains a draft and cannot be published or canonical memory |
| Storage migration | Trigger measurements, migration/recovery plan, consistency proof, and rollback evidence | `PRODUCT_OWNER_DECISION`; add `BUDGET_APPROVAL`, `PRODUCTION_APPROVAL`, or `EXTERNAL_SERVICE_APPROVAL` only when the chosen migration actually requires them | Continue within the supported current deployment or block capacity; no implicit engine switch |

Every human approval uses the canonical human-resolution path with actor,
authority basis, exact scope, decision, timestamp, and content-bound evidence.
One record satisfies one requirement. A Sol review is automated evidence only
except for the distinct delegated artifact approval; it grants no analyst,
product, legal, rights, budget, production, or promotion authority.

## SQLite and workflow scale-up guard

SQLite is the allowed Phase 0.5 default, not a permanent commitment. Reconsider
it only when measured evidence shows: persistent writer-lock contention affects
ingestion or review; multiple remote users require concurrent writes;
availability, backup, or failover requirements exceed the embedded deployment;
or operational workarounds become more complex than migration. These are
operating triggers, not automatic authorization and not a new critical
decision. This spec selects no replacement technology. Workflow-engine triggers
belong to S14; S10 retains only the storage authority and migration record.

## Activation and Deferred guard

S10 is active-only because both owned rows were `Open` at activation. It has no
Deferred row, activation predicate, or authority to activate any conditional
capability. A future attempt to mark either activation-owned row Deferred, or
to treat an operational scale trigger as activation approval, fails pending
formal authority reconciliation and re-review. R-5 cannot authorize a database
migration by itself.

## Acceptance tests and verification

Before delegated S10 approval, fixtures or structural tests must prove:

1. every matrix record class has exactly one authoritative write path and a
   declared retention rule;
2. a sealed package reconstructs the exact manifest and all referenced hashes;
3. missing, changed, post-cutoff, or unauthorized references block sealing;
4. rework creates v(N+1), preserves v(N), and records a typed change set;
5. a derivative-index-only citation and an attempted index canonical write are
   rejected;
6. correction appends while deletion uses a distinct approved/tombstoned path;
7. raw scratchpad absence does not prevent resume, audit, or reconstruction;
8. the storage-trigger record can recommend reconsideration but cannot perform
   or approve migration; and
9. a source-to-spec audit finds B-03, C-11, T-3, and R-5 exactly once under S10
   and no register row owned by another spec.

Mechanical verification is necessary but not sufficient. B-03 acceptance also
requires its typed human decision and current evidence; C-11 acceptance requires
tests demonstrating no product dependency on raw scratchpads.

## Dependencies and handoffs

- S09 supplies immutable document identities, bytes, hashes, and capture times.
- S11 supplies run/attempt manifests, cutoff enforcement, package binding, and
  reproducibility proof.
- S12 supplies observation/fact identity, revision, and schema-evolution rules.
- S13 supplies claim identity and evidence semantics.
- S14 consumes sealed evidence packages and creates new versions during rework.
- S15 supplies correction, approval, supersession, and promotion transitions.
- S16 supplies registered calculation traces and replay classes.
- S17 supplies authoritative event/entity relationships.

No dependent implementation may treat this draft as an approved B-03 matrix.
