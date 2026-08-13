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

- the authority matrix for raw documents, SourceOccurrences,
  ExtractionResults, Observations, Fact revisions/canonical selections, claims,
  events, calculations, evidence packages, run manifests, approvals, approved
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
| Source occurrence (`SourceOccurrence`) | Append-only SQL occurrence record satisfying S12 and bound to one exact S09 document ID/version/byte hash, source location, raw-value payload, schema version, and record digest; the S09 bytes remain authoritative for the document itself | Source-jump/read models keyed to `source_occurrence_id` and digest | Only S12's `append_source_occurrence` interface, invoked by the registered S09 ingestion/extraction stage, may append after the location and raw payload verify against the immutable source version. Source correction creates a new document version and occurrence; no writer updates or reuses an occurrence ID | Retain every occurrence referenced by a retained ExtractionResult, Observation, Fact, package, review, correction, or approval. An unreferenced occurrence follows the approved source-rights schedule; deletion is a distinct tombstoned rights action and never mutation or correction |
| Extraction result (`ExtractionResult`) | Append-only SQL extraction metadata plus immutable inline output or content-addressed output reference satisfying S12, including exact occurrence ID/digest, extractor/config identity, output digest, schema version, and record digest | Parser diagnostics and candidate views keyed to `extraction_result_id` and digest | Only S12's `append_extraction_result` interface, invoked by a registered extractor or actor-bound manual-extraction path, may append. Parser, model, prompt/config, or manual re-extraction changes create a new result; an extraction result cannot write Observation, Fact, or canonical status | Retain every result referenced by a retained Observation, Fact, package, QA record, failure, correction, review, or approval. An unreferenced result may expire only under the approved operational schedule after an inbound-reference check; required removal leaves a tombstone and invalidates affected reconstruction claims |
| Observation | Append-only SQL Observation records satisfying S12, each bound by ID and digest to exactly one ExtractionResult and its SourceOccurrence | Read models, caches, aggregates, and embeddings | Only S12's `append_observation` normalization/validation interface may append a typed pre-reconciliation Observation. New extraction or normalization meaning creates a new Observation; conflicts coexist and no Observation writer can select a Fact | Retain every Observation, validation state, conflict, and lineage edge referenced by a revision family, Fact, package, calculation, claim, review, or approval; never hard-delete history as correction |
| Fact revision and canonical selection | Append-only SQL Fact revisions, reconciliation decisions, revision-family history, and canonical-selection chain satisfying S12 | As-of fact views and aggregates keyed to immutable IDs/digests | Only S12's reconciliation append interfaces may write a family version, decision, or Fact revision, and only its atomic `compare_and_append_canonical_selection` interface may append selection. Conflicting candidates coexist; no mutable latest pointer or direct Fact update is authoritative | Retain every revision, reconciliation decision, correction reason, supersession/predecessor edge, and prior selection plus its complete retained S12 lineage; never hard-delete history as correction |
| Claim | Append-only SQL claim records using the registered vocabulary and evidence links defined by S13 | Search/document projections | Claim review/promotion workflows create new status or superseding records; display text cannot replace structured identity | Retain all reviewed versions, dispositions, evidence directions, and supersession history |
| Event or corporate action | Versioned SQL event records | Timelines and alerts | Event authority follows S17; conflicts remain explicit until reconciled | Retain event versions, identifier mappings, and reconciliation history |
| Calculation | Registered calculation trace containing inputs, assumptions, operator/code/runtime version, replay class, and output | Rendered tables and cached results | Only S16 registered compute is authoritative; an LLM-produced number is never a calculation record | Retain every trace referenced by a fact, claim, evidence package, or report |
| Evidence package | Immutable manifest plus content-addressed references to exact source, S12 lineage, claim, and calculation versions | Materialized bundle/cache regenerated from the manifest | One package version is frozen per run attempt; any input change creates v(N+1) | Retain every referenced manifest and its verified dependency closure; a superseding package never mutates a prior package |
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
| `manifest_schema_version`, `canonicalization_profile` | Exact manifest schema version and `eos-manifest-json-v1` byte profile |
| `evidence_package_id`, `version` | Stable package identity and monotonically increasing immutable version |
| `run_id`, `attempt_id` | Owning run and attempt from S11 |
| `knowledge_cutoff` | UTC cutoff enforced by S11; never inferred from package creation time |
| `created_at` | UTC package-freeze time |
| `document_refs` | Ordered document IDs, exact versions, byte hashes, source locations where scoped, and knowledge times |
| `observation_refs` | Exact S12 `observation_id`, record-schema version, `observation_sha256`, and intended package role for every Observation included directly rather than only through a Fact root |
| `fact_refs` | Exact `fact_id`, `fact_revision_id`, record-schema version, `fact_revision_sha256`, definition version, and selected-revision role |
| `canonical_selection_refs` | Exact `canonical_selection_id`, record-schema version, `canonical_selection_sha256`, measurement-key ID/digest, selected Fact-revision ID/digest, and selection-as-of-cutoff proof |
| `s12_lineage_closure` | Complete deterministic `S12LineageClosure` defined below; every Observation, Fact revision, and canonical-selection root resolves through it to exact SourceOccurrence and ExtractionResult IDs/digests |
| `claim_refs` | Exact claim IDs and versions included as prior approved analytical state; drafted claims are separately marked |
| `calculation_refs` | Exact trace IDs and code/runtime versions |
| `policy_refs` | Materiality, metric/predicate registry, retention, source-authority, reconciliation, and S12 schema/canonicalization policy IDs, versions, and content digests |
| `reconciliation_evidence_refs`, `approval_refs` | Exact non-document evidence IDs/versions/content hashes and typed approval requirement/record/human-resolution IDs/content digests referenced by the S12 lineage |
| `parent_package_ref` | Exact immediate predecessor `{evidence_package_id, version, manifest_sha256}`; null if and only if `version=1`; for `version=N>1`, it resolves to the same package ID at `version=N-1` and its stored manifest hash |
| `change_set` | Typed added/removed/superseded references and invalidation reasons |
| `manifest_sha256` | Lowercase hexadecimal SHA-256 of the domain-separated canonical preimage defined below |

### Manifest canonical-byte profile

`eos-manifest-json-v1` is the self-contained canonical byte contract for S10
and for manifests that explicitly import it:

1. The manifest is encoded as UTF-8 JSON with no BOM or insignificant
   whitespace. Object names are unique after Unicode NFC normalization and are
   ordered by unsigned lexicographic order of their normalized UTF-8 bytes.
2. String names and values are NFC-normalized. `"`, `\`, and U+0000 through
   U+001F are escaped as `\"`, `\\`, and lowercase `\u00xx`, respectively;
   every other character is emitted as unescaped UTF-8, and invalid Unicode or
   lone surrogates fail canonicalization.
3. Arrays are ordered. In this profile every manifest collection is set-like:
   its elements are sorted by their complete canonical JSON bytes before the
   array is persisted and hashed. A future semantically ordered collection
   requires a new schema/profile version that declares its ordering rule.
4. UTC timestamps use exactly `YYYY-MM-DDTHH:mm:ss.ffffffZ`. Values not exactly
   representable at microsecond precision are rejected rather than rounded.
   Integers use base-10 JSON numbers with no leading plus, leading zero, or
   negative zero. Non-integral quantities use decimal strings matching
   `-?(0|[1-9][0-9]*)\.[0-9]*[1-9]`; exponent form, redundant leading or
   trailing zeros, plus signs, negative zero, and non-finite values are
   forbidden.
5. Every field declared by `manifest_schema_version` is present. A nullable
   field is encoded as JSON `null`; absent and null are not interchangeable.
   Unknown fields, duplicate names, and omitted required or nullable fields
   fail canonicalization.

The hash input is the ASCII domain separator
`EquityOS:EvidencePackageManifest:v1\n` followed by the canonical JSON object
with `manifest_sha256` removed entirely, not set to null. The stored
`manifest_sha256` equals the lowercase hexadecimal SHA-256 of exactly those
bytes; `\n` denotes one LF byte (`0x0A`), not a backslash and `n`. A producer
and verifier must reject a manifest whose stored collection
order, profile/version, preimage, or digest does not match this contract.

### Deterministic content-addressed S12 lineage closure

`S12LineageClosure` is one manifest field, not a separately mutable index. It
contains `closure_schema_version=S12-LINEAGE-1`,
`canonicalization_profile=eos-manifest-json-v1`, `root_refs`, `nodes`, and
`lineage_closure_sha256`. A root is each exact Observation, Fact revision, or
canonical-selection record named by the three corresponding manifest
collections. Each root must occur exactly once in `nodes` with the same ID,
schema version, and record digest.

Each node contains `record_type`, `record_id`, `record_schema_version`,
`record_sha256`, and `dependency_refs`. `record_type` is exactly one of
`SOURCE_OCCURRENCE`, `EXTRACTION_RESULT`, `OBSERVATION`, `MEASUREMENT_KEY`,
`REVISION_FAMILY`, `RECONCILIATION_DECISION`, `FACT_REVISION`, or
`CANONICAL_SELECTION`. Each dependency ref contains the dependent record's
type, ID, schema version, and record digest. The verifier derives, rather than
trusts, the complete dependency set from the authoritative S12 record:

| Node type | Required S12 dependencies |
|---|---|
| `SOURCE_OCCURRENCE` | None; its exact S09 document ID/version/byte hash must resolve in `document_refs` |
| `EXTRACTION_RESULT` | Its one `SOURCE_OCCURRENCE` |
| `OBSERVATION` | Its one `EXTRACTION_RESULT` and that result's one `SOURCE_OCCURRENCE` |
| `MEASUREMENT_KEY` | None; its exact metric-definition/policy leaves must resolve in `policy_refs` |
| `REVISION_FAMILY` | Its `MEASUREMENT_KEY` and every member `OBSERVATION` in the referenced immutable family version |
| `RECONCILIATION_DECISION` | Its `REVISION_FAMILY`, `MEASUREMENT_KEY`, and every selected, rejected, or deferred candidate `OBSERVATION` |
| `FACT_REVISION` | Its `MEASUREMENT_KEY`, selected `OBSERVATION`, `RECONCILIATION_DECISION`, and prior Fact revision when non-root |
| `CANONICAL_SELECTION` | Its `MEASUREMENT_KEY`, selected `FACT_REVISION`, and exact predecessor selection when non-root |

Every S12 record reference above is an ID-plus-digest reference under S12's
record-digest contract. Every non-S12 document, policy, evidence, approval, or
human-resolution leaf named by a node must resolve exactly once with its
content digest in the matching manifest collection. The manifest's top-level
hash therefore binds both the closed S12 graph and every external leaf needed
to interpret, reconcile, approve, or source it.

Closure construction and verification use this exact algorithm:

1. Form the unique root set from `observation_refs`, `fact_refs`, and
   `canonical_selection_refs`; duplicate identities with different digests
   fail.
2. Fetch each root by exact ID/schema version/digest, recompute its S12 record
   digest, derive its required dependencies from the table, and recurse by
   exact ID/schema version/digest until every path reaches a SourceOccurrence
   or MeasurementKey leaf.
3. Recompute every visited record digest and every derived dependency set;
   reject a missing, extra, unreachable, duplicated, cyclic, type-confused, or
   digest-conflicting node and any missing, mismatched, or multiply resolved
   external leaf.
4. Require every knowledge-time-bearing node and external leaf to be eligible
   at `knowledge_cutoff`; missing or post-cutoff proof fails the closure.
5. Sort `root_refs`, every `dependency_refs` collection, and `nodes` by their
   complete canonical JSON bytes. Hash the ASCII domain separator
   `EquityOS:S12LineageClosure:v1\n` followed by canonical JSON of the closure
   with `lineage_closure_sha256` removed entirely.
6. Require the stored lowercase digest to equal that hash, require the closure
   object to be embedded unchanged in the canonical manifest preimage, and
   then verify `manifest_sha256`.

Reconstruction repeats every step from retained authoritative records; merely
matching a stored node list or closure digest is insufficient. Any source,
result, Observation, reconciliation, Fact, selection, policy, evidence, or
approval mutation must produce a new immutable record where permitted and a
new package version. It can never preserve the prior closure or manifest hash.

Package assembly is a transaction: resolve all authoritative references as of
the cutoff, validate hashes and policy versions, persist the manifest, then
seal it. Partial assembly is not a package. A downstream step consumes one
sealed manifest hash and performs no new evidence retrieval. Changed evidence,
human rejection, source correction, or recalculation creates a new manifest;
the prior package remains reproducible and auditable. Version `N>1` cannot seal
until its exact `parent_package_ref` resolves and its predecessor hash verifies.

## Retention, correction, and deletion

1. Corrections append new records and explicit supersession or canonical-
   selection edges; they do not overwrite evidence.
2. Records in an approved package, calculation trace, review, approval, or
   published artifact are retention-pinned with their dependency closure. For
   an evidence package this includes every node and external leaf in its
   verified `S12LineageClosure`, including SourceOccurrences and
   ExtractionResults that are not top-level manifest roots.
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
- Every Observation, Fact revision, and canonical-selection root has one exact,
  complete, reachable, acyclic S12 lineage closure. An omitted or extra
  SourceOccurrence/ExtractionResult, ID/digest substitution, edge mismatch,
  unreachable node, or external-leaf mismatch blocks sealing and
  reconstruction even when all top-level references match.
- A package cannot be edited after sealing. Hash mismatch, missing dependency,
  partial write, unregistered policy version, or cross-store disagreement
  invalidates it and blocks publication.
- Non-canonical encoding, an invalid digest preimage, or a missing, mismatched,
  or non-immediate parent reference blocks sealing; package-family parentage is
  reconstructed only from exact ID/version/hash links.
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
| S10 delegated artifact approval | Fresh clean Sol xhigh review bound to this file's current bytes, exact source rows, T-3/R-5 treatment, declared interfaces and canonical preimage, parent-reference contract, S12 lineage-closure contract, content-bound S08 storage-trigger prerequisite, fixture catalogue, and test specifications; no product execution result is required | `DELEGATED_ARTIFACT_APPROVAL`; fresh Sol xhigh under delegated goal authority | Spec remains draft; no personal user approval is inferred |
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

A storage reconsideration or migration recommendation is authoritative only as
an immutable `StorageScaleDecision`. S08 does not define authoritative record
digests for the four record types consumed here. S10 therefore binds exact
S08-owned values through the versioned import projections below. An import
digest is an S10 content binding for this decision path; it does not become an
S08 record digest, duplicate S08 ownership, or replace an S08 approval.

### S08 import canonicalization and common nested types

Every import projection uses `canonicalization_profile=eos-manifest-json-v1`.
Every field listed for its schema is present; nullable fields are explicit
JSON `null`. All projection arrays are set-like and are stored sorted by each
element's complete canonical JSON bytes. Object-key order, strings, timestamps,
integers, decimal strings, nulls, and rejection of unknown or omitted fields
follow the profile exactly. These common nested objects are closed:

- `effective_interval` is
  `{starts_at, ends_at}`, where `starts_at` is a canonical UTC timestamp and
  `ends_at` is a later canonical UTC timestamp or null;
- `typed_scalar` is `{value_type, value}`, where `value_type` is exactly
  `BOOLEAN`, `INTEGER`, `DECIMAL`, or `STRING`; `value` has the corresponding
  JSON boolean, integer, canonical decimal string, or NFC string type;
- `typed_quantity` is `{value, unit}`, where `value` is an integer or canonical
  decimal string and `unit` is a nonempty NFC string;
- `content_ref` is `{record_type, record_id, record_version, content_sha256}`;
  `record_version` is an integer or null only when the source type has no
  version, and the digest is lowercase SHA-256 of the referenced immutable
  content under that record's owning contract;
- `approval_binding` is
  `{approval_type, requirement_ref, record_ref, human_resolution_ref}`.
  `requirement_ref` is
  `{approval_id, required_authority, scope, status, evidence_refs}`;
  when present, `record_ref` is
  `{approval_record_id, decision, authority, scope, actor, timestamp,
  evidence_refs}`; each evidence ref is `{evidence_ref_id, content_sha256}`;
  and, when present, `human_resolution_ref` is
  `{human_review_id, resolution_decision_id, resolution_content_sha256}`.
  S08 imports permit only `PRODUCT_OWNER_DECISION`, `BUDGET_APPROVAL`, and
  `CAPACITY_COMMITMENT`. Requirement status is exactly `UNRESOLVED`,
  `SATISFIED`, `DENIED`, `REVOKED`, or `EXPIRED`. `UNRESOLVED` requires null
  record and human-resolution refs; every other status requires both refs, the
  correspondingly named record decision (`SATISFIED` maps to `APPROVED`), and
  matching scopes under the activated goal's typed-approval contract. Only a
  `SATISFIED`/`APPROVED` binding supports `TRUE`, `FALSE`, or `CURRENT`.

An imported source field described below as a string is its complete S08
semantic value, not a display abbreviation. A source value that cannot be
represented by the declared type or nesting requires a new S10 import-schema
version. Producers may not stringify an object, flatten a collection, infer a
null, omit an unrecognized S08 field, or silently project a changed source
schema through an old import version.

### Versioned S08 import projections

Each projection is one JSON object with the exact top-level nesting shown:
`{import_schema_version, canonicalization_profile, source_spec_id, record,
<own digest field>}`. `source_spec_id` is exactly `S08`; `record` has exactly
the fields in the table. The own digest field is removed entirely for its own
preimage and is present everywhere else, including inside a
`StorageScaleDecision` preimage.

| Imported record | `import_schema_version` | Exact fields nested directly under `record` | Own digest field | ASCII domain separator |
|---|---|---|---|---|
| `MetricDefinition` | `S10-S08-METRIC-DEFINITION-IMPORT-1` | `metric_id`, `version`, `name`, `definition`, `unit`, `numerator`, `denominator`, `population`, `sampling_rule`, `aggregation`, `stratification`, `measurement_method`, `phase_applicability`, `threshold`, `owner`, `status`, `metric_contract_approval_binding` | `metric_definition_import_sha256` | `EquityOS:S10:S08MetricDefinitionImport:v1\n` |
| `MetricObservation` | `S10-S08-METRIC-OBSERVATION-IMPORT-1` | `observation_id`, `metric_definition_ref`, `phase`, `scope`, `raw_event_refs`, `calculation_version`, `observed_value`, `unit`, `missingness_state`, `instrumentation_overhead`, `captured_at`, `knowledge_cutoff`, `supersedes_observation_ref`, `correction_reason` | `metric_observation_import_sha256` | `EquityOS:S10:S08MetricObservationImport:v1\n` |
| `WorkflowBudget` | `S10-S08-WORKFLOW-BUDGET-IMPORT-1` | `budget_id`, `version`, `workflow_id`, `applicable_phase`, `effective_interval`, `controls`, `breach_action`, `currency`, `allocation_method`, `evidence_refs`, `authorization_class`, `product_owner_approval_bindings`, `budget_approval_binding` | `workflow_budget_import_sha256` | `EquityOS:S10:S08WorkflowBudgetImport:v1\n` |
| `OperatingCapacityPlan` | `S10-S08-OPERATING-CAPACITY-PLAN-IMPORT-1` | `plan_id`, `version`, `effective_interval`, `weekly_builder_capacity`, `weekly_analyst_capacity`, `target_blueprint_phase_dates`, `monthly_ceilings`, `maintenance_allowance`, `expected_company_coverage`, `peak_week_assumptions`, `backlog_policy`, `capacity_owner`, `workflow_budget_refs`, `evidence_refs`, `product_owner_approval_binding`, `budget_approval_binding`, `capacity_approval_binding` | `operating_capacity_plan_import_sha256` | `EquityOS:S10:S08OperatingCapacityPlanImport:v1\n` |

The record-specific compound fields have these exact shapes:

- `MetricDefinition.metric_id`, `name`, `definition`, `unit`, `population`,
  `sampling_rule`, `measurement_method`, and `owner` are nonempty NFC strings;
  `version` is a positive integer. `aggregation` and `stratification` are
  arrays of nonempty NFC strings. `phase_applicability` contains
  `{blueprint_phase, gate_use, not_applicable_rationale}` objects; the first two
  fields are nonempty NFC strings and the rationale is null unless that entry
  is not applicable. `numerator` and `denominator` are null or nonempty NFC
  strings that name the S08 event/record expression.
  `threshold` is null or
  `{threshold_id, threshold_version, comparator, direction, threshold_value,
  unit, effective_interval, authority_binding}`. `threshold_value` is
  `{value, range}` with exactly one non-null: `value` is a `typed_scalar`, while
  `range` is `{lower, upper, lower_inclusive, upper_inclusive}` with typed-scalar
  bounds and JSON-boolean inclusivity fields. Threshold IDs, comparator,
  direction, and unit are nonempty NFC strings, and the threshold version is a
  positive integer. `status` is exactly `DRAFT`, `APPROVED`, `DEPRECATED`, or
  `SUPERSEDED`. `metric_contract_approval_binding` is the S08 A-13
  `PRODUCT_OWNER_DECISION` requirement and may retain unresolved or adverse
  state; it must be `SATISFIED` when status is `APPROVED`.
- `MetricObservation.observation_id`, `phase`, `calculation_version`, and
  `unit` are nonempty NFC strings. `metric_definition_ref` is
  `{metric_id, version, metric_definition_import_sha256}` and must resolve to
  exactly one imported definition in the same decision. `scope` is
  `{run_id, report_id, company_id, population, strata}`; the three IDs are
  nullable only when S08's metric definition excludes that key, `population`
  is a nonempty NFC string, and `strata` is an array of
  `{dimension, value}`. `raw_event_refs` are `content_ref` objects.
  `observed_value` is a `typed_scalar` or null; it is non-null exactly when
  `missingness_state=PRESENT`, and null when that state is `MISSING` or
  `UNKNOWN`. `unit` is a nonempty NFC string, `instrumentation_overhead` is a
  `typed_quantity`, and `supersedes_observation_ref` is null or
  `{observation_id, metric_observation_import_sha256}` for the immediate
  predecessor in S08's same-scope correction chain. `captured_at` and
  `knowledge_cutoff` are canonical UTC timestamps; `correction_reason` is null
  or a nonempty NFC string.
- `WorkflowBudget.budget_id`, `workflow_id`, `applicable_phase`,
  `breach_action`, `currency`, and `allocation_method` are nonempty NFC
  strings; `version` is a positive integer; `evidence_refs` is an array of
  `{evidence_ref_id, content_sha256}`. `controls` contains exactly one object for each of
  `MODEL_COST`, `TOOL_CALLS`, `LATENCY`, `DOCUMENT_VOLUME`, `RETRIES`, and
  `ANALYST_MINUTES`. Each is
  `{control_kind, control_mode, metric_definition_ref, measurement_rule,
  ceiling}`. `control_mode` is `MEASUREMENT_RULE` or `CEILING`.
  `metric_definition_ref` is
  `{metric_id, version, metric_definition_import_sha256}` and resolves to one
  imported definition in the same decision.
  `MEASUREMENT_RULE` requires a nonempty NFC `measurement_rule` and null
  `ceiling`; `CEILING` requires null `measurement_rule` and
  `ceiling={limit, unit, effective_interval, breach_action}`, where `limit` is
  a `typed_scalar`. `authorization_class` is `MEASUREMENT_RULE_ONLY` or
  `BUDGET_COMMITMENT`; `product_owner_approval_bindings` contains exactly one
  distinct S08 `PRODUCT_OWNER_DECISION` for each `MEASUREMENT_RULE` control and
  no others. `budget_approval_binding` is null exactly for
  `MEASUREMENT_RULE_ONLY` and otherwise is the exact S08 `BUDGET_APPROVAL`.
- `OperatingCapacityPlan.plan_id`, `capacity_owner`, and `backlog_policy` are
  nonempty NFC strings; `version` is a positive integer; `evidence_refs` has
  the WorkflowBudget evidence-ref shape. `weekly_builder_capacity`,
  `weekly_analyst_capacity`, `maintenance_allowance`, and
  `expected_company_coverage` are `typed_quantity` objects.
  `target_blueprint_phase_dates` contains `{blueprint_phase, target_date}`
  objects with a nonempty NFC phase and `target_date` encoded as `YYYY-MM-DD`.
  `monthly_ceilings` is
  `{provider, model, infrastructure}` and each member is
  `{limit, currency, allocation_method, breach_action}` with a typed-scalar
  `limit` whose value type is `INTEGER` or `DECIMAL`; its other fields are
  nonempty NFC strings. `peak_week_assumptions` is an array of nonempty NFC strings.
  `workflow_budget_refs` contains
  `{budget_id, version, workflow_budget_import_sha256}` objects. The three
  approval-binding fields bind the S08 product-owner, standing-budget, and
  capacity requirements respectively. The product-owner binding is null unless
  S08 requires it for that exact plan; the budget and capacity requirement
  bindings are always present and must be `SATISFIED` for a plan used as
  current authority. Every S08-required binding, and no invented substitute,
  is required for current use.

For every projection, its stored digest is lowercase SHA-256 of its tabled
ASCII domain separator followed by canonical JSON of the complete projection
with only its own digest field removed entirely. The literal `\n` is one LF
byte. Wrong type or nesting, unknown or omitted field, duplicate identity,
non-canonical collection order, invalid profile/schema version, source
ID/version mismatch, unresolved nested reference, or digest mismatch rejects
the import and the containing decision. There is no ID-only, whole-S08-file-
hash, or copied-digest fallback.

### `StorageScaleDecision` result and current-validity model

`StorageScaleDecision` has exactly these fields:
`storage_scale_decision_schema_version=S10-STORAGE-SCALE-DECISION-1`,
`canonicalization_profile=eos-manifest-json-v1`, `decision_id`, `version`,
nullable `supersedes_decision_ref`, `trigger_kind`, `result`,
`measurement_window`, `evaluation_method`, `metric_definition_imports`,
`metric_observation_imports`, `workflow_budget_imports`,
`operating_capacity_plan_imports`, `created_at`, and
`storage_scale_decision_sha256`. `supersedes_decision_ref` is null for version
1 and otherwise is `{decision_id, version, storage_scale_decision_sha256}` for
the immediate same-family predecessor. `trigger_kind` is exactly one of
`WRITER_LOCK_CONTENTION`, `REMOTE_MULTI_WRITER_REQUIREMENT`,
`EMBEDDED_AVAILABILITY_BACKUP_FAILOVER_EXCEEDED`, or
`OPERATIONAL_WORKAROUND_COMPLEXITY_EXCEEDED`. `measurement_window` is
`{starts_at, ends_at}` with a non-null end. `evaluation_method` is
`{method_id, method_version, expression, observed_values}`; each observed value
is `{metric_observation_id, metric_observation_import_sha256, value}` with a
`typed_scalar` value and resolves exactly once to the imported observation.
Decision IDs, method IDs, and expressions are nonempty NFC strings; decision
and method versions are positive integers; `created_at` is a canonical UTC
timestamp. The registered method version owns the deterministic expression
language and rejects an unparseable expression, an undeclared observation, or
a value unequal to the referenced observation projection.

The immutable `result` vocabulary is closed: `TRUE`, `FALSE`, or `UNKNOWN`.
`TRUE` or `FALSE` may be recorded only when every required import and approval
binding verifies, is scope/window eligible, and is current at `created_at`, and
the declared method deterministically evaluates to that result. Missing or
ambiguous proof yields `UNKNOWN`; `UNRESOLVED` is invalid as a
`StorageScaleDecision.result` or `current_validity` value (its separate use as
an S08 approval-requirement status does not enter either vocabulary).
A byte/digest failure rejects the record before its result can be trusted and
must not be converted to `UNKNOWN`.

Current authority is evaluated separately from the immutable decision bytes.
It never rewrites `result` or any historical import. The closed derived
`current_validity` vocabulary is `CURRENT`, `NOT_CURRENT`, or `UNKNOWN`:

- `CURRENT` requires the decision and every import digest to reproduce, the
  decision to be the unsuperseded same-family leaf, every S08 observation and
  versioned prerequisite to remain the unique current same-scope value at the
  evaluation time, all effective intervals to include that time, and every
  approval binding to remain approved and unexpired. For versioned S08 records,
  current means the unique highest version for the same identity and scope
  whose S08 status, where defined, permits use and whose effective interval,
  where defined, contains the evaluation time; zero or multiple eligible
  versions is not current proof;
- `NOT_CURRENT` requires positive append-only proof of at least one of
  `DECISION_SUPERSEDED`, `INPUT_SUPERSEDED`, `APPROVAL_REVOKED`,
  `APPROVAL_EXPIRED`, `EFFECTIVE_INTERVAL_ENDED`, or
  `SCOPE_OR_WINDOW_MISMATCH`; and
- `UNKNOWN` requires `MISSING_CURRENT_PROOF` or
  `AMBIGUOUS_CURRENT_PROOF`. No missing or ambiguous state is coerced to
  `NOT_CURRENT` or `CURRENT`.

If persisted for audit, a use-time assessment is append-only and contains
`decision_id`, `version`, `storage_scale_decision_sha256`, `evaluated_at`,
`current_validity`, the exact closed reason codes above, and the current
successor/approval/effective-interval evidence refs. Reason codes are empty
exactly for `CURRENT` and otherwise contain only the codes assigned to the
derived state above. It is not part of the
historical decision preimage. A recommendation may be used only when the
decision digest and every import digest reproduce, `result=TRUE`, and a fresh
assessment returns `CURRENT`; `FALSE`, `UNKNOWN`, `NOT_CURRENT`, or an unknown
current validity cannot recommend or authorize migration.

`storage_scale_decision_sha256` is lowercase SHA-256 of the ASCII domain
separator `EquityOS:StorageScaleDecision:v1\n` followed by canonical JSON of
the complete decision with only `storage_scale_decision_sha256` removed. The
literal `\n` is one LF byte. All import objects, including their own digest
fields and original S08 approval bindings, remain in this preimage. An
append-only successor, approval revocation/expiry, observation correction, or
evaluation after an effective interval ends leaves the retained historical bytes and digest
reproducible but makes current use fail under the rules above.

This content-bound S08 prerequisite is required only for the storage-trigger
decision path; it does not add a new register dependency to B-03 or C-11. S10
neither duplicates S08 approvals nor lets one record satisfy a second
requirement. The separate S10 migration approval and recovery/consistency proof
remain mandatory.

## Activation and Deferred guard

S10 is active-only because both owned rows were `Open` at activation. It has no
Deferred row, activation predicate, or authority to activate any conditional
capability. A future attempt to mark either activation-owned row Deferred, or
to treat an operational scale trigger as activation approval, fails pending
formal authority reconciliation and re-review. R-5 cannot authorize a database
migration by itself.

## Acceptance tests and verification

Initial delegated S10 approval reviews this contract, its declared fixture
catalogue, and the test specifications below for completeness and internal
consistency. It does not require a store, package assembler, index, deletion
workflow, or resumable product workflow to exist or execute.

Before B-03 or C-11 acceptance, and at the corresponding implementation phase
gates, executable fixtures must prove:

1. every matrix record class, including SourceOccurrence and ExtractionResult,
   has exactly one authoritative write path plus explicit append, conflict,
   retention, and rights-deletion behavior;
2. independent producers serialize the same logical manifest to identical
   preimage bytes and digest across key-order, collection-order, timestamp,
   Unicode, integer/decimal, null, and absent-field cases, while malformed or
   non-canonical inputs fail;
3. a sealed package reconstructs the exact manifest, every S12 lineage node and
   external leaf, and all referenced hashes by recomputing the closure rather
   than trusting the stored node list;
4. missing, changed, post-cutoff, or unauthorized references block sealing;
5. rework creates v(N+1), preserves v(N), records a typed change set, and binds
   the exact same-family v(N) parent by ID, version, and verified hash;
6. a derivative-index-only citation and an attempted index canonical write are
   rejected;
7. correction appends while deletion uses a distinct approved/tombstoned path;
8. raw scratchpad absence does not prevent resume, audit, or reconstruction;
9. the storage-trigger record reproduces each versioned, domain-separated S08
   import projection and its decision preimage; distinguishes immutable
   `result` from derived `current_validity`; binds the exact applicable
   definition, observation, budget/capacity records, and original approval
   bindings; and can recommend reconsideration but cannot perform or approve
   migration; and
10. a source-to-spec audit finds B-03, C-11, T-3, and R-5 exactly once under S10
   and no register row owned by another spec.

Mechanical verification is necessary but not sufficient. B-03 acceptance also
requires its typed human decision and current evidence; C-11 acceptance requires
tests demonstrating no product dependency on raw scratchpads.

### Focused negative fixtures

| Fixture | Mutation | Required result |
|---|---|---|
| `S10-NL-01-OMITTED-RESULT` | Remove the ExtractionResult node between a valid Observation and SourceOccurrence while leaving every top-level ref unchanged | Closure traversal finds the missing derived dependency; package sealing and reconstruction fail |
| `S10-NL-02-SWAPPED-DIGEST` | Pair a valid `source_occurrence_id` or `extraction_result_id` with another record's digest | Record-digest recomputation fails; no ID-only fallback is allowed |
| `S10-NL-03-EDGE-OR-EXTRA` | Change a dependency edge, add an unreachable node, duplicate one identity with another digest, or introduce a cycle | Derived adjacency/uniqueness/reachability check fails before closure hashing |
| `S10-NL-04-CUTOFF-OR-RETENTION` | Supply a post-cutoff lineage node or remove a retention-pinned SourceOccurrence/ExtractionResult | Package cannot seal or reconstruct and the affected artifact cannot claim reproducibility |
| `S10-NS08-01-BYTE-TAMPER` | Change any retained import-projection or `StorageScaleDecision` byte under its existing identity/digest, including a nested payload, reference, scope, or approval-binding byte | The affected import or decision digest does not reproduce; the record is rejected before `result` or `current_validity` can be trusted, and no recommendation or approval follows |
| `S10-NS08-02-NOT-CURRENT` | Preserve all retained bytes, then append a decision/input successor or observation correction, append a matching approval revocation/expiry, or evaluate after an effective interval ends | Every historical import and decision digest still reproduces; a fresh assessment returns `NOT_CURRENT` with the exact reason code, and no current recommendation or approval follows |
| `S10-NS08-03-UNKNOWN-CURRENT-PROOF` | Preserve all retained bytes but omit or fork the evidence needed to prove the unique current successor, approval, or effective interval | Historical digests still reproduce; a fresh assessment returns `UNKNOWN` with `MISSING_CURRENT_PROOF` or `AMBIGUOUS_CURRENT_PROOF`, and no current recommendation or approval follows |

## Dependencies and handoffs

- S09 supplies immutable document identities, bytes, hashes, and capture times.
- S08 supplies the exact content-bound metric definitions/observations and,
  where applicable, budget/capacity records and original approval bindings used
  by `StorageScaleDecision`; S10 neither owns nor duplicates those approvals.
- S11 supplies run/attempt manifests, cutoff enforcement, package binding, and
  reproducibility proof.
- S12 supplies observation/fact identity, revision, and schema-evolution rules.
- S13 supplies claim identity and evidence semantics.
- S14 consumes sealed evidence packages and creates new versions during rework.
- S15 supplies correction, approval, supersession, and promotion transitions.
- S16 supplies registered calculation traces and replay classes.
- S17 supplies authoritative event/entity relationships.

No dependent implementation may treat this draft as an approved B-03 matrix.
