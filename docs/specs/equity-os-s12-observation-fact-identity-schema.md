# S12 — Observation/fact identity, revision, and schema evolution

**Status: DRAFT — AWAITING FRESH SOL XHIGH REVIEW**

## Contract purpose and provisional posture

This specification defines the invariant identity model, evidence-driven schema
derivation procedure, revision/correction semantics, safe evolution rules, and
schema-delta format for B-05, B-10, B-11, and C-03. It intentionally does not
invent or freeze the final minimum source/fact schema. B-05 and B-10 remain
provisional until their separate mandatory amendment gates have passed.

## Authority, ownership, and activation

The v2 decision register is authoritative for live gates. The activated goal
is authoritative for this exact title, path, ownership, active-only
classification, and mandatory amendments. The disposition report clarifies
M-2 but cannot weaken the register.

| Field | Exact source text |
|---|---|
| Spec program row | `S12` — `Observation/fact identity, revision, and schema evolution` |
| Exact path | `docs/specs/equity-os-s12-observation-fact-identity-schema.md` |
| Primary register ownership | `B-05, B-10, B-11, C-03` |
| Disposition references | `M-2` |
| Activation classification | `active-only` |

| ID | Blueprint phase | Priority | Decision or action — exact register text | Required evidence / acceptance — exact register text | Dependencies — exact register text | Activation status | Primary owner |
|---|---|---:|---|---|---|---|---|
| B-05 | 0.5 | Critical | Derive minimum source and fact schemas from actual use | Schema supports raw/normalized values, dimensions, scope, source location, valid time, knowledge time, revisions, definition version, and quality/reconciliation status | A-06, B-11, B-12 | Open | S12 |
| B-10 | 0.5 | High | Decide which speculative blueprint fields to remove or defer | Schema-delta document showing retained, deleted, added, and deferred fields with reasons | B-02, B-05, B-06 | Open | S12 |
| B-11 | 0.5 | Critical | Specify fact identity, revision-family, and correction semantics | Source occurrence, extraction result, measurement key, revision family, and canonical selection are distinguished; issuer restatement, source correction, parser re-extraction, manual correction, and normalization-policy change have separate reasons; prior-period comparative handling is tested | A-06, B-12 | Open | S12 |
| C-03 | 1 | Critical | Implement append-only observation and revision model | Restatements and conflicting observations are preserved; no silent overwrite; model follows B-11 identity semantics | B-11 | Open | S12 |

M-2 is accepted with a model richer than a single key. It requires four
distinct concepts: source occurrence, extraction result, economic measurement
slot, and approved canonical selection. Parser upgrades normally create new
extraction results; restatements, reclassifications, and segment-definition
changes require explicit reconciliation rather than key-based overwrite.

## Scope

This contract owns:

- identity and separation of raw source occurrence (`SourceOccurrence`),
  extraction result, typed pre-reconciliation Observation, measurement slot,
  revision family, reconciled Fact, and canonical selection;
- raw/normalized value, unit/currency, dimensions, statement/scope, exact
  source location, valid time, knowledge time, definition version, quality,
  and reconciliation invariants;
- distinct revision reasons and prior-period comparative treatment;
- append-only corrections and safe schema/version migrations;
- the evidence-driven derivation procedure and fixtures for the final minimum
  source/fact schema; and
- the retained/deleted/added/deferred schema-delta decision format.

## Non-goals

This contract does not define the final field inventory before vertical-slice
evidence, the metric/predicate registries (S13), materiality policy (S06),
document registry (S09), authoritative-store matrix (S10), calculations (S16),
entity/security identity (S17), or claim schema (S13). It does not collapse
valid time into knowledge time, treat a parser result as a fact, or silently
select the newest value.

## Identity model

The following concepts are distinct even if an implementation co-locates them:

| Concept | Stable identity and required meaning | Mutability rule |
|---|---|---|
| Source occurrence (`SourceOccurrence`) | `source_occurrence_id` identifies one immutable raw value occurrence at an exact location in one immutable source version; it preserves raw text/value and source coordinates | Never overwritten; corrected source bytes create a new source version and occurrence |
| Extraction result | `extraction_result_id` identifies parser/model or actor-recorded manual extraction output for one `source_occurrence_id`, extractor identity/version, prompt/config where applicable, and extraction time | A parser/config upgrade or manual re-extraction appends a new result; it does not rewrite the occurrence or an earlier result |
| Observation | `observation_id` identifies one typed, extracted, normalized, pre-reconciliation value derived from one extraction result and bound to its raw source occurrence; it retains raw and normalized value, units, currency, scope, dimensions, exact source location, and temporal fields | Append-only; a new extraction or normalization interpretation creates a new Observation and never rewrites the source occurrence, extraction result, or earlier Observation |
| Measurement key | `measurement_key_id` identifies the economic slot composed from entity, metric definition/version, period, statement/consolidation scope, dimension set, and accounting/adjustment basis | Definition or dimensional meaning changes create a new key/version; aliases cannot merge incompatible slots |
| Revision family | `revision_family_id` groups Observations believed, through explicit reconciliation, to represent the same measurement slot | Membership is append-only and reasoned; equality of a key alone does not auto-supersede |
| Reconciled Fact revision | `fact_revision_id` records one reconciled use of a selected `observation_id` for a measurement key, its complete source/extraction lineage, quality/reconciliation state, temporal bounds, and reason | Append-only; a correction or restatement creates another revision and edge |
| Canonical selection | `canonical_selection_id` records which fact revision is approved for a measurement key from one knowledge time, its exact predecessor, event class, policy, evidence, and approval bindings | Never updated in place; an atomic compare-and-append creates one successor, and the successor's start derives the predecessor's end |

Repository glossary vocabulary controls these object names. `Observation` and
`observation_id` are reserved exclusively for the typed, extracted, normalized,
pre-reconciliation value. The raw immutable lifecycle object is
`SourceOccurrence`, identified only by `source_occurrence_id`. M-2's
illustrative `observation_id = immutable source occurrence` spelling is
implemented as `source_occurrence_id = immutable source occurrence`; its
lifecycle distinctions and all B-11 behaviors remain intact. A source
occurrence or extraction result is not an Observation, and an Observation is
not a reconciled Fact.

The logical measurement key is:

```text
entity
+ metric definition/version
+ period
+ statement/consolidation scope
+ dimension set
+ accounting/adjustment basis
```

The system must not derive identity solely from display label, numeric value,
document order, filing date, ISIN, or the latest ingestion timestamp.

## Provisional data-contract envelopes

These envelopes state mandatory invariants, not the final minimum physical
schema. The B-05 amendment may add, split, rename, or reject provisional fields
only with evidence, compatibility analysis, fixtures, migration rules, and a
fresh Sol xhigh review.

### `SourceOccurrence`

- `source_occurrence_id`, immutable `document_id` and `document_version`;
- exact `source_location` capable of deterministic source jump and line/page/
  table/cell or equivalent locator;
- `raw_value` and raw unit/currency/scope tokens without normalization loss;
- source valid-period signals and recorded `knowledge_time`/first-seen time;
- content/location digest and creation audit metadata.

### `ExtractionResult`

- `extraction_result_id`, `source_occurrence_id`, extractor
  kind/version/config hash, prompt/config where applicable, extraction time,
  and recorded `knowledge_time`;
- immutable parser/model or actor-recorded manual output or output reference,
  candidate count, warnings, confidence, validation results, and output digest;
  and
- zero or more Observations may immutably reference the result; extraction
  success alone implies no Observation, canonical, or Fact status.

### `Observation`

- `observation_id`, `extraction_result_id`, and `source_occurrence_id`, with
  exactly one bound extraction result and its exact raw source occurrence;
- losslessly bound `raw_value` plus typed normalized value, unit, currency,
  period, dimensions, scope, metric candidate, and exact `source_location`;
- valid-time signals, recorded `knowledge_time`, normalization policy/version,
  validation/quality state, and immutable content digest; and
- explicit pre-reconciliation status. One extraction result may emit zero or
  more candidate Observations, but ambiguity remains explicit and no candidate
  is silently selected as a Fact.

### `MeasurementKey`

- `measurement_key_id`, stable entity ID, registered metric definition and
  definition version;
- period type/bounds, statement and consolidation scope, ordered canonical
  dimension set, and accounting/adjustment basis; and
- canonical serialization/digest so ordering or formatting cannot create a
  second identity for the same declared slot.

### `RevisionFamily` and `ReconciliationDecision`

- `revision_family_id`, `measurement_key_id`, typed member `observation_id`
  refs with their `source_occurrence_id` and `extraction_result_id` lineage;
- reconciliation status, conflict set, selected/rejected/deferred candidates,
  rationale/evidence refs, actor and timestamp; and
- distinct `revision_reason`: `ISSUER_RESTATEMENT`, `SOURCE_CORRECTION`,
  `PARSER_RE_EXTRACTION`, `MANUAL_CORRECTION`, or
  `NORMALIZATION_POLICY_CHANGE`.

### `FactRevision` and `CanonicalSelection`

- stable `fact_id` plus immutable `fact_revision_id`, selected `observation_id`,
  and its exact source-occurrence/extraction lineage;
- raw and normalized value, unit, currency, dimensions, scope, metric
  definition version, source location, valid-time interval, knowledge-time
  evidence, quality status, and reconciliation status;
- supersession/revision edge with typed reason and prior revision; and
- append-only canonical selection with `measurement_key_id`, selected
  `fact_revision_id`, `effective_from_knowledge_time`, transition sequence,
  exact predecessor ID, selection-event type, reconciliation-policy
  version and policy-approval binding, selector evidence, typed event-approval
  requirement/record refs, and exact human-resolution bindings where a human
  approval is required.

No field may be silently null-filled or defaulted when its absence could alter
identity, period, units, currency, scope, definition, cutoff eligibility, or
canonical selection. Such a candidate remains unresolved.

A Fact revision and canonical selection resolve immutably to the complete
`source_occurrence_id` → `extraction_result_id` → `observation_id` lineage.
Neither may become knowledge-eligible before every bound source occurrence,
extraction result, Observation, reconciliation decision, policy, evidence item,
and required approval is knowledge-eligible. At cutoff `t`, both the canonical-
selection predicate and every record in that selected Fact's lineage must
satisfy their recorded knowledge-time constraint; any missing or post-cutoff
lineage fails closed.

### Atomic append-only canonical-selection transition

Canonical-selection applicability uses successor-derived bounds; no stored
selection row is closed or mutated. For one `measurement_key_id`, the immutable
chain has exactly one root, each selection has at most one successor, and each
`(measurement_key_id, transition_sequence)` and
`(measurement_key_id, effective_from_knowledge_time)` pair is unique. A
successor has sequence `predecessor.sequence + 1`, starts strictly after its
predecessor, and binds the predecessor's exact immutable ID.

The only write interface is an atomic compare-and-append operation receiving
the measurement key, expected predecessor ID (null only for the root),
selected fact revision, event type, effective-from time, reconciliation policy,
evidence, and approval bindings. In one transaction it:

1. verifies the fact belongs to the measurement key, the expected predecessor
   is the unique current head, the start time is monotonic, the selected Fact's
   complete lineage is knowledge-eligible at that start time, and every
   required approval binding is satisfied;
2. enforces the root, successor, sequence, and start-time uniqueness
   constraints; and
3. appends the new selection and commits without updating the predecessor.

A stale predecessor, concurrent winner, fork, duplicate start/sequence, missing
approval, or partial write aborts the entire append and leaves the prior chain
unchanged. At cutoff `t`, the selected row must be the unique chain member with
`effective_from_knowledge_time <= t` and either no valid successor or a
successor whose `effective_from_knowledge_time > t`. Zero or multiple matches,
a broken link, or an incomplete transition is unresolved and fails closed.

### Event-level approval mapping and resolution binding

S15 owns the closed event-to-approval-requirement mapping for
`INITIAL_SELECTION`, `ISSUER_RESTATEMENT`, `SOURCE_CORRECTION`,
`PARSER_INDUCED_FACT_REVISION`, `MANUAL_CORRECTION`, and
`NORMALIZATION_POLICY_CHANGE`. The mapping is versioned and returns exact typed
requirements from the goal's closed approval vocabulary; it has no default or
generic escape. It cannot remove S12's policy-level
`DOMAIN_EXPERT_ACCEPTANCE` gate, and `MANUAL_CORRECTION` retains its distinct
`ANALYST_ACCEPTANCE` requirement.

Each selection binds the approved reconciliation-policy version and that
policy's distinct satisfied requirement, approval record, and resolution, then
binds the event-mapping version and every resulting `approval_id` and matched
`approval_record_id`. Every required event-level record uses
`HUMAN_RESOLUTION` and also binds its canonical
`human_review_id`, `resolution_decision_id`, and
`resolution_content_sha256`; `DELEGATED_ARTIFACT_APPROVAL` never satisfies an
event-level selection requirement. Requirement and record must match
type, authority, exact scope, actor, timestamp, evidence, and authority source
one-to-one. Until S15 declares the event mapping and every returned requirement
is `SATISFIED`, the candidate remains unresolved and no selection is appended.

## Revision and correction semantics

| Event | Required behavior | Forbidden behavior |
|---|---|---|
| Issuer restatement | Preserve original source occurrence, extraction result, Observation, and Fact; ingest the new occurrence; append its extraction result and Observation; reconcile into the family; if selected, use the atomic transition with `ISSUER_RESTATEMENT`, its knowledge time, and S15-mapped approvals | Rewrite an earlier lifecycle record or make the restatement visible before it was known |
| Source correction | Preserve the old lifecycle identities and records; retain old source bytes when policy permits; append the corrected version, occurrence, result, and Observation; reconcile and append a `SOURCE_CORRECTION` Fact revision; if selected, use the mapped atomic transition | Replace source bytes under the old document hash or reuse its lifecycle IDs |
| Parser re-extraction | Append an extraction result for the same immutable `source_occurrence_id`; append every emitted typed candidate as a new Observation; revalidation decides whether a new Fact revision is required; any induced selection uses `PARSER_INDUCED_FACT_REVISION` and its mapped approvals | Treat parser upgrade as issuer restatement, overwrite the occurrence/result/Observation, or promote its result or Observation directly |
| Manual correction | Preserve the source occurrence and prior extraction/Observation; append an actor-bound manual extraction result, a reasoned corrected Observation, and, after reconciliation, a Fact revision with distinct `ANALYST_ACCEPTANCE`, affected dependency invalidation, and the mapped atomic transition if selected | Edit a normalized value in place or omit actor/rationale/approval binding |
| Normalization-policy change | Version the policy/definition; append a policy-bound Observation and, after reconciliation, a Fact revision; use a new measurement key when semantic meaning changes; any selection uses its mapped atomic transition | Retroactively rewrite historical Observations or Facts without versioned provenance |
| Conflicting sources | Preserve every source occurrence, extraction result, and Observation plus the explicit conflict; apply source hierarchy/reconciliation; allow unresolved status | Select the latest or largest value silently |
| Reclassification/segment change | Preserve both definitions/dimensions and reconcile comparability explicitly | Group under one key solely because labels resemble each other |

## Prior-period comparative contract

When Quarter N repeats a comparative value for Quarter N-1, each printed value
is a separate SourceOccurrence and each typed extraction is a separate
Observation. If the meaning and measurement key match, the Observations may
join one revision family after reconciliation while retaining their distinct
raw occurrence and extraction lineage. If the newer filing restates or
reclassifies the comparative, it creates a new Fact revision known only from
the newer source's knowledge time. Historical runs before that time continue
to select the earlier revision. Fixtures must cover unchanged comparative
repetition, numeric restatement, statement-scope change, segment-definition
change, unit/currency change, and parser-only re-extraction.

## Evidence-driven schema derivation

The final minimum schema is derived, not guessed:

1. Collect A-06 channel/taxonomy spike artifacts and actual B-11/B-12 workflow
   evidence from the discovery-company sources.
2. Inventory every observed source shape, field need, ambiguity, conflict,
   restatement, prior-period comparative, definition change, and failed
   reconciliation without inventing placeholder evidence.
3. Trace each candidate field to a required invariant, query, cutoff rule,
   source-jump need, failure, or accepted downstream contract.
4. Create representative and adversarial fixtures with exact source evidence.
5. Propose the minimum schema and field-level required/nullable rules; reject
   fields with no evidenced purpose and defer fields whose need is plausible
   but unobserved.
6. Test identity stability, lossless raw preservation, as-of selection,
   append-only correction, package reconstruction, and safe migration.
7. Produce the B-05 amendment, obtain fresh clean Sol xhigh review and distinct
   delegated approval, then unblock dependent implementation.

## Schema evolution and migration contract

- Every physical/logical schema and metric definition has an immutable version.
- Readers declare supported versions; writers emit one current approved version.
- Additive changes default to nullable only when absence is semantically safe;
  otherwise they require a backfill/reconciliation plan with source proof.
- Renames preserve stable semantic identity and compatibility mapping. A meaning
  change is a new field/definition, not a rename.
- Destructive removal requires the B-10 delta decision, usage/dependency proof,
  export or tombstone policy, migration fixture, rollback/recovery plan, and
  the required human decision.
- Migrations are restartable, idempotent, content-audited, and fail before
  canonical switch on count/hash/invariant mismatch.
- Old fact revisions and historical package reconstruction remain readable
  under their recorded schema/definition versions.

## Schema-delta decision format

Each candidate field has one row containing:

`field_id`, prior path/version, proposed path/version, disposition
(`RETAINED`, `DELETED`, `ADDED`, or `DEFERRED`), exact evidence refs, observed
workflow/query need, identity/temporal/source implications, downstream owners,
migration action, compatibility window, rollback/recovery proof, required
human approvals, reviewer evidence, and rationale.

`DEFERRED` means not implemented and not silently emitted as an unvalidated
nullable field. `DELETED` means removed only after dependency and reconstruction
proof. The delta document cannot be finalized until B-02, B-05, and B-06
evidence exists.

## Invariants and fail-closed behavior

- Source occurrence, extraction result, Observation, measurement key, revision
  family, Fact revision, and canonical selection have distinct IDs and
  lifecycles. `source_occurrence_id` and `observation_id` are never aliases.
- Every Observation binds exactly one extraction result and its exact source
  occurrence; every Fact revision binds a reconciled Observation and preserves
  that complete lineage.
- All occurrences, extraction results, Observations, conflicts, revisions,
  reasons, and prior selections are append-only and auditable. Selection
  changes append one atomic successor; predecessor applicability ends only by
  that successor-derived bound.
- Raw values and exact source location survive into each Observation and Fact
  lineage. Normalized output never replaces raw evidence.
- Unit, currency, period, statement/consolidation scope, dimensions, metric
  definition/version, valid time, and knowledge time are explicit when they can
  change meaning. Ambiguity blocks canonical selection.
- Canonical selection is always `(measurement key, knowledge cutoff)` aware and
  uses the unique successor-derived predicate above. "Newest" is not a valid
  selection policy; a fork, overlap, gap, or ambiguous match fails closed.
- A source occurrence or extraction result cannot masquerade as an Observation.
  An extraction result or Observation cannot become a Fact or canonical
  selection without reconciliation, the S15 event mapping, and one-to-one
  required approval and resolution evidence.
- Canonical cutoff selection verifies the complete selected Fact lineage; a
  post-cutoff or missing occurrence, result, Observation, reconciliation,
  policy, evidence, or approval binding fails closed even if the selection row
  alone satisfies the successor-derived time predicate.
- Unknown revision reason, incompatible dimension/definition, broken source
  digest, unsafe migration, or missing comparative handling fails closed.
- Provisional envelopes cannot be represented as final B-05 or B-10 acceptance.

## Evidence and typed approval gates

| Gate | Required evidence | Approval type and authority | Fail-closed result |
|---|---|---|---|
| Initial S12 delegated artifact approval | Fresh clean Sol xhigh review bound to current bytes, exact ownership, M-2, provisional posture, both amendment gates, declared identity/transition interfaces, S15 mapping delegation, fixture catalogue, and test specifications; no product execution result is required | `DELEGATED_ARTIFACT_APPROVAL`; fresh Sol xhigh under delegated goal authority | Spec remains draft; no personal user approval is inferred |
| Reconciliation/canonical-selection policy | Source hierarchy, fixtures, conflict outcomes, comparative tests, and audit fields | `DOMAIN_EXPERT_ACCEPTANCE` by a competent human for financial meaning and reconciliation policy | Conflicted candidate remains unresolved and cannot become canonical fact |
| Canonical-selection event | Versioned closed S15 event mapping, exact event/scope evidence, and all resulting requirement, record, and resolution bindings | Each distinct typed approval returned by S15's mapping; one record satisfies one requirement and no nearby approval is inferred | Selection append is denied and the candidate remains unresolved |
| Manual correction | Exact source/error evidence, affected dependency closure, reason, and new revision | `ANALYST_ACCEPTANCE` by the responsible analyst for the correction scope | Original remains; proposed correction is not canonical |
| B-05 final schema amendment | A-06 and actual B-11/B-12 evidence, field traceability, fixtures, migration/compatibility proof, and fresh review | distinct `DELEGATED_ARTIFACT_APPROVAL`; plus `DOMAIN_EXPERT_ACCEPTANCE` for semantic field/definition decisions that require human judgment | B-05 cannot be Accepted and dependent schema implementation remains blocked |
| B-10 schema-delta amendment | B-02/B-05/B-06 evidence, complete retained/deleted/added/deferred table, dependency/reconstruction proof, and fresh review | distinct `DELEGATED_ARTIFACT_APPROVAL`; `PRODUCT_OWNER_DECISION` for the exact removal/deferral scope, plus domain approval where meaning changes | B-10 cannot be Accepted; destructive or speculative schema changes remain blocked |

All non-delegated decisions use the canonical human-resolution artifact with
actor, authority basis, exact scope, decision, timestamp, and evidence. One
record satisfies one requirement. Sol review and delegated artifact approval
never substitute for analyst, domain, or product-owner authority.

## Mandatory amendment gates

### AMEND-S12-B05 — final minimum source/fact schema

This initial spec supplies invariants, derivation procedure, fixtures, and safe
migration rules only. After A-06 plus actual B-11/B-12 workflow evidence exists,
S12 must be amended and freshly reviewed before dependent schema implementation
continues or B-05 is accepted. The amendment must bind the evidence-derived
final minimum field set and migration contract. Until then the gate is due and
the provisional envelopes are not final acceptance evidence.

### AMEND-S12-B10 — speculative-field disposition

This initial spec supplies the schema-delta method and required decision format,
not the final delta. After B-02, B-05, and B-06 evidence exists, S12 must be
amended and freshly reviewed before B-10 acceptance or destructive/deferred
schema decisions proceed. Dependent work remains blocked while this amendment
is due.

Each amendment is a new content version with its own fresh Sol xhigh review,
review evidence, and delegated artifact approval. Neither amendment may claim
the non-delegated human decisions listed above.

## Activation and Deferred guard

S12 is active-only: B-05, B-10, B-11, and C-03 were all `Open` at activation.
It owns no Deferred row and has no activation predicate. `DEFERRED` in the
schema-delta enum is a field-level design disposition, not activation of a
register component. It authorizes no implementation. Any attempt to treat a
plausible but unevidenced field as active scope, or to weaken an activation-
owned row to Deferred, fails pending authority reconciliation and re-review.

## Acceptance tests and verification

Initial delegated S12 approval reviews this contract, its declared fixture
catalogue, and the test specifications below for completeness and internal
consistency. It does not require identity persistence, reconciliation,
canonical-selection writes, migration machinery, or cutoff queries to exist or
execute.

Before B-11 or C-03 acceptance, at their corresponding implementation phase
gates, and at the B-05/B-10 amendment gates where applicable, executable
fixtures must prove:

1. each identity layer is distinct, `source_occurrence_id` never aliases
   `observation_id`, and every Observation and Fact retains its exact
   source/version/extraction lineage;
2. a parser re-extraction appends a result and every emitted typed candidate as
   a new Observation without rewriting the source occurrence, prior result, or
   prior Observation or masquerading as issuer restatement;
3. restatement, source correction, manual correction, and normalization-policy
   change produce distinct typed revisions;
4. conflicting Observations and their distinct raw occurrence/extraction
   lineages coexist and cannot auto-select by latest timestamp;
5. initial selection and every selection-producing revision event use the
   closed S15 mapping and exact one-to-one requirement, approval-record, and
   human-resolution bindings;
6. two concurrent transitions from the same predecessor permit one atomic
   successor and reject the other without mutation, while a partial write
   leaves the prior chain valid;
7. the successor-derived cutoff predicate returns exactly the earlier fact
   before a later restatement and the successor at/after its effective time;
   post-cutoff lineage is rejected even when the selection row alone matches;
   forked, duplicate, broken, zero-match, or multi-match chains fail closed;
8. prior-period comparatives preserve distinct source occurrences and
   Observations across unchanged, restated, reclassified, dimension-changed,
   unit/currency-changed, and parser-only cases;
9. unsafe destructive migration, missing raw/source proof, or semantic nulls
   fail before canonical switch;
10. the provisional schema and delta cannot report B-05 or B-10 final acceptance;
11. both amendment gates block their exact dependency cones until fresh review;
   and
12. a source-to-spec audit finds B-05, B-10, B-11, C-03, and M-2 exactly once
    under S12 and no register row owned by another spec.

For B-05 amendment acceptance, rerun fixtures against the evidence-derived
final schema and verify every final field has an evidence/contract trace. For
B-10 amendment acceptance, verify all field dispositions and migration paths
against actual B-02/B-05/B-06 evidence. C-03 acceptance additionally requires
append-only persistence tests, concurrent/conflict behavior, and historical
cutoff reconstruction through S11.

## Dependencies and handoffs

- A-06/S09 supplies filing-channel, taxonomy/version, source-location, and
  restatement evidence.
- B-12/S13 supplies registered metric definitions, dimensions, aliases, and
  vocabulary versions used in measurement keys.
- B-02/S14 supplies actual incremental-update evidence for the B-10 amendment.
- B-06/S13 supplies the evidence-derived claim schema needed before final delta.
- S10 consumes exact SourceOccurrence, Observation, and Fact-revision IDs and
  their extraction lineage as the authoritative SQL/package closure;
  `observation_id` never denotes a raw occurrence.
- S11 applies knowledge cutoffs to the complete source-occurrence, extraction,
  Observation, Fact-revision, and canonical-selection lineage, then uses the
  unchanged successor-derived selection predicate for historical replay.
- S15 supplies the closed canonical-selection event/approval mapping plus
  correction and human review transitions.
- S16 consumes canonical facts and must reject unresolved/ambiguous inputs.
- S17 supplies stable internal entity/security IDs used by measurement keys.

No implementation may treat the provisional envelopes in this draft as the
final minimum schema.
