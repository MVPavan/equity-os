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

- identity and separation of source occurrence, extraction result, observation,
  measurement slot, revision family, reconciled fact, and canonical selection;
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
| Source occurrence / observation | `observation_id` identifies one immutable value occurrence at an exact location in one immutable source version; it preserves raw text/value and source coordinates | Never overwritten; corrected source bytes create a new source version and occurrence |
| Extraction result | `extraction_result_id` identifies parser/model output for one `observation_id`, extractor identity/version, prompt/config where applicable, and extraction time | A parser/config upgrade appends a new result; it does not rewrite the occurrence or an earlier result |
| Measurement key | `measurement_key_id` identifies the economic slot composed from entity, metric definition/version, period, statement/consolidation scope, dimension set, and accounting/adjustment basis | Definition or dimensional meaning changes create a new key/version; aliases cannot merge incompatible slots |
| Revision family | `revision_family_id` groups occurrences believed, through explicit reconciliation, to represent the same measurement slot | Membership is append-only and reasoned; equality of a key alone does not auto-supersede |
| Reconciled fact revision | `fact_revision_id` records one reconciled use of a selected observation/extraction for a measurement key, its quality/reconciliation state, temporal bounds, and reason | Append-only; a correction or restatement creates another revision and edge |
| Canonical selection | `canonical_selection_id` records which fact revision is approved for a measurement key over a knowledge-time interval and why | Never update in place; close the prior knowledge interval and append a new selection |

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

### `ObservationOccurrence`

- `observation_id`, immutable `document_id` and `document_version`;
- exact `source_location` capable of deterministic source jump and line/page/
  table/cell or equivalent locator;
- `raw_value` and raw unit/currency/scope tokens without normalization loss;
- source valid-period signals and recorded `knowledge_time`/first-seen time;
- content/location digest and creation audit metadata.

### `ExtractionResult`

- `extraction_result_id`, `observation_id`, extractor kind/version/config hash;
- typed proposed normalized value, unit, currency, period, dimensions, scope,
  and metric candidate;
- warnings, confidence, validation results, extraction time, and immutable
  output digest; and
- no canonical/fact status implied by extraction success.

### `MeasurementKey`

- `measurement_key_id`, stable entity ID, registered metric definition and
  definition version;
- period type/bounds, statement and consolidation scope, ordered canonical
  dimension set, and accounting/adjustment basis; and
- canonical serialization/digest so ordering or formatting cannot create a
  second identity for the same declared slot.

### `RevisionFamily` and `ReconciliationDecision`

- `revision_family_id`, `measurement_key_id`, typed member observation and
  extraction refs;
- reconciliation status, conflict set, selected/rejected/deferred candidates,
  rationale/evidence refs, actor and timestamp; and
- distinct `revision_reason`: `ISSUER_RESTATEMENT`, `SOURCE_CORRECTION`,
  `PARSER_RE_EXTRACTION`, `MANUAL_CORRECTION`, or
  `NORMALIZATION_POLICY_CHANGE`.

### `FactRevision` and `CanonicalSelection`

- stable `fact_id` plus immutable `fact_revision_id` and selected
  observation/extraction refs;
- raw and normalized value, unit, currency, dimensions, scope, metric
  definition version, source location, valid-time interval, knowledge-time
  interval, quality status, and reconciliation status;
- supersession/revision edge with typed reason and prior revision; and
- append-only canonical selection with selector authority/evidence and exact
  knowledge-time applicability.

No field may be silently null-filled or defaulted when its absence could alter
identity, period, units, currency, scope, definition, cutoff eligibility, or
canonical selection. Such a candidate remains unresolved.

## Revision and correction semantics

| Event | Required behavior | Forbidden behavior |
|---|---|---|
| Issuer restatement | Preserve original occurrence/fact; ingest new occurrence; reconcile into the family; append selection effective at its knowledge time with `ISSUER_RESTATEMENT` | Rewrite the earlier fact or make the restatement visible before it was known |
| Source correction | Preserve old source version and occurrence when retention permits; append corrected version/result and `SOURCE_CORRECTION` fact revision | Replace source bytes under the old document hash |
| Parser re-extraction | Append extraction result for the same immutable occurrence and extractor version/config; revalidation decides whether a new fact revision is required | Treat parser upgrade as issuer restatement or overwrite prior result |
| Manual correction | Append reasoned correction with human decision evidence and affected dependency invalidation | Edit normalized value in place or omit actor/rationale |
| Normalization-policy change | Version the policy/definition; append result/revision; use a new measurement key when semantic meaning changes | Retroactively rewrite all historical normalized values without versioned provenance |
| Conflicting sources | Preserve every occurrence and explicit conflict; apply source hierarchy/reconciliation; allow unresolved status | Select the latest or largest value silently |
| Reclassification/segment change | Preserve both definitions/dimensions and reconcile comparability explicitly | Group under one key solely because labels resemble each other |

## Prior-period comparative contract

When Quarter N repeats a comparative value for Quarter N-1, each printed value
is a separate source occurrence. If the meaning and measurement key match, the
occurrences may join one revision family after reconciliation. If the newer
filing restates or reclassifies the comparative, it creates a new fact revision
known only from the newer source's knowledge time. Historical runs before that
time continue to select the earlier revision. Fixtures must cover unchanged
comparative repetition, numeric restatement, statement-scope change,
segment-definition change, unit/currency change, and parser-only re-extraction.

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

- Source occurrence, extraction result, measurement key, revision family, fact
  revision, and canonical selection have distinct IDs and lifecycles.
- All occurrences, conflicts, revisions, reasons, and prior selections are
  append-only and auditable; there is no silent overwrite.
- Raw values and exact source location survive normalization. Normalized output
  never replaces raw evidence.
- Unit, currency, period, statement/consolidation scope, dimensions, metric
  definition/version, valid time, and knowledge time are explicit when they can
  change meaning. Ambiguity blocks canonical selection.
- Canonical selection is always `(measurement key, knowledge cutoff)` aware.
  "Newest" is not a valid selection policy.
- A parser result cannot become a fact or canonical selection without
  reconciliation and required approval evidence.
- Unknown revision reason, incompatible dimension/definition, broken source
  digest, unsafe migration, or missing comparative handling fails closed.
- Provisional envelopes cannot be represented as final B-05 or B-10 acceptance.

## Evidence and typed approval gates

| Gate | Required evidence | Approval type and authority | Fail-closed result |
|---|---|---|---|
| Initial S12 delegated artifact approval | Fresh clean Sol xhigh review bound to current bytes, exact ownership, M-2, provisional posture, and both amendment gates | `DELEGATED_ARTIFACT_APPROVAL`; fresh Sol xhigh under delegated goal authority | Spec remains draft; no personal user approval is inferred |
| Reconciliation/canonical-selection policy | Source hierarchy, fixtures, conflict outcomes, comparative tests, and audit fields | `DOMAIN_EXPERT_ACCEPTANCE` by a competent human for financial meaning and reconciliation policy | Conflicted candidate remains unresolved and cannot become canonical fact |
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

Before initial delegated S12 approval, structural fixtures must prove:

1. each identity layer is distinct and all records retain source/version links;
2. a parser re-extraction appends a result without rewriting the occurrence or
   masquerading as issuer restatement;
3. restatement, source correction, manual correction, and normalization-policy
   change produce distinct typed revisions;
4. conflicting observations coexist and cannot auto-select by latest timestamp;
5. as-of selection before a later restatement returns the earlier fact;
6. prior-period comparatives cover unchanged, restated, reclassified,
   dimension-changed, unit/currency-changed, and parser-only cases;
7. unsafe destructive migration, missing raw/source proof, or semantic nulls
   fail before canonical switch;
8. the provisional schema and delta cannot report B-05 or B-10 final acceptance;
9. both amendment gates block their exact dependency cones until fresh review;
   and
10. a source-to-spec audit finds B-05, B-10, B-11, C-03, and M-2 exactly once
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
- S10 consumes fact/revision records as the authoritative SQL contract and
  includes them in evidence packages.
- S11 applies knowledge cutoffs to canonical selection and historical replay.
- S15 supplies correction and human review transitions.
- S16 consumes canonical facts and must reject unresolved/ambiguous inputs.
- S17 supplies stable internal entity/security IDs used by measurement keys.

No implementation may treat the provisional envelopes in this draft as the
final minimum schema.
