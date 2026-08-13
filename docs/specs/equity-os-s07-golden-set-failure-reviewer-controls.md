# Golden set, failure taxonomy, and reviewer-bias controls

**Spec ID:** S07
**Status:** DRAFT — AWAITING FRESH SOL XHIGH REVIEW
**Activation classification:** Active-only
**Exact path:** `docs/specs/equity-os-s07-golden-set-failure-reviewer-controls.md`

## Contract status and authority

This document is an implementation contract, not evidence that any owned
register row is accepted. The implementation decision register v2 is the
operational authority for decision wording and gates. The disposition report
is the audit trail for the referenced findings. The activated goal assigns
S07 its exact title, path, owners, and disposition references. A fresh Sol
xhigh review may later grant only delegated artifact approval; this draft does
not claim that review or approval, and delegated approval cannot substitute
for any typed human decision below.

### Exact ownership and source text

| Register ID | Blueprint phase | Priority | Decision or action — exact register text | Required evidence / acceptance — exact register text | Dependencies — exact register text | Activation status | Current source status |
|---|---|---:|---|---|---|---|---|
| A-08 | 0A | High | Appoint golden-test-set owner | Named owner, repository location, review cadence, and first twenty labeled cases, including prompt-injection/source-confusion cases | — | Open | Open |
| B-08 | 0.5 | High | Record failure taxonomy | Extraction, reconciliation, source, unit, period, calculation, citation, inference, review, cutoff leakage, source-confusion, and document-as-instruction failures categorized | A-08 | Open | Open |
| B-13 | 0.5 | High | Add reviewer-bias and measurement controls | Quarter 0 is not reused for assisted work; instrumentation is symmetric and overhead measured; shadow-mode seeded-error drills cannot be promoted; false-accept/false-reject results are stratified by materiality and epistemic class; optional external spot review procedure defined | A-03, A-08, A-13 | Open | Open |

The exact program assignment is: **S07 — Golden set, failure taxonomy, and
reviewer-bias controls**, with primary register IDs **A-08, B-08, B-13** and
disposition references **M-6, M-9, 6.6**. All owned rows were `Open` at the
pinned activation snapshot, so S07 is active-only. This spec neither owns nor
activates any Deferred row.

| Disposition ref | Exact heading | Exact disposition | Binding effect in this contract |
|---|---|---|---|
| M-6 | Reviewer and builder are the same person | Accept with safeguards. | Add golden-case edit/reject checks, stratified false-accept/false-reject measures, isolated seeded-error drills, and an optional external spot-review procedure. |
| M-9 | Untrusted-document surface | Accept. | Treat source content as data; cover prompt injection, source confusion, control-plane changes, execution/secrets, and promotion provenance in the golden set and taxonomy. |
| 6.6 | Seeded errors require isolation | Correction to the third-order review. | Seeded errors are reviewer-QA fixtures only and must have no path into a promotable or publishable artifact. |

## Scope

S07 defines the contracts needed to:

1. appoint and evidence one accountable golden-set owner;
2. maintain a versioned repository of at least twenty expert-labeled initial
   cases and a declared review cadence;
3. classify failures without collapsing distinct extraction, evidence,
   calculation, inference, cutoff, review, or adversarial-document failures;
4. measure reviewer behavior with symmetric manual/assisted instrumentation;
5. run seeded-error drills only in isolated golden fixtures or shadow reports;
6. measure false accepts and false rejects by materiality and epistemic class;
7. define, without pretending it has occurred, an optional external
   spot-review procedure; and
8. export stable case, run, decision, and failure records to the evaluation and
   analyst-economics consumers.

### Non-goals

- This spec does not select the discovery company, perform Quarter 0, define
  materiality, freeze success metrics, or build the claim-review UI.
- It does not approve any golden label, appoint an owner, conduct an external
  review, or supply analyst/domain authority.
- It does not permit source text to issue instructions or grant tool,
  credential, cutoff, publication, or promotion authority.
- It does not use accepted-unchanged rate as a standalone quality measure or
  treat claims clustered in one report as independent statistical samples.
- It does not place synthetic defects in a production evidence package,
  canonical thesis, approved narrative, or any artifact capable of promotion.

## Interfaces and data contracts

All records are versioned, machine-readable, and addressed by stable IDs.
Timestamps are UTC. Enumerations below are closed unless a later reviewed
amendment explicitly versions them.

### `GoldenSetManifest`

The A-08 repository root contains one current manifest with `manifest_id`,
`manifest_version`, `repository_path`, `owner_identity_id`,
`owner_commitment_record_id`, `review_rrule`, `review_timezone`,
`next_review_due_at`, exact ordered `case_refs` (`case_id` plus `case_version`),
category-coverage results, `effective_at`, and `supersedes_manifest_version`.
`repository_path` is repository-relative and must resolve to the manifest and
referenced case records. `review_rrule` is a machine-parseable RFC 5545
recurrence rule; `next_review_due_at` is its current computed UTC occurrence.
The current initial manifest must reference at least twenty distinct current
cases. Missing, duplicate, stale, unresolvable, or unparseable fields keep A-08
unresolved rather than falling back to prose or directory inference.

### `GoldenCase`

| Field | Contract |
|---|---|
| `case_id`, `case_version` | Stable identity plus monotonic version; a changed label creates a new version. |
| `fixture_kind` | `REAL_SOURCE`, `SYNTHETIC`, or `SHADOW_SEEDED_ERROR`. |
| `source_refs` | Immutable source/evidence references with exact locations and hashes; synthetic sources are visibly marked. |
| `input_contract_version` | Exact workflow/input contract used by the case. |
| `expected_claims` | Typed expected observations/claims, epistemic class, materiality class/policy version, disposition, and exact evidence support. |
| `expected_failures` | Zero or more `FailureCode` values and expected fail-closed boundary. |
| `adversarial_tags` | Includes `PROMPT_INJECTION` and/or `SOURCE_CONFUSION` where applicable. |
| `label_authority` | Human/domain label record ID; unresolved until valid typed evidence exists. |
| `promotion_eligible`, `publication_eligible` | Both are fixed to `false` for every golden case, including `REAL_SOURCE`; fixture status never authorizes promotion or publication. |
| `created_at`, `supersedes_case_version` | Audit history; old versions remain retrievable. |

The initial inventory passes only with at least twenty distinct, currently
reviewable cases. It must include prompt-injection and source-confusion cases
and seeded examples for wrong period, wrong unit, wrong source, unsupported
claim, and fabricated citation. One case may cover multiple categories, but
the inventory must report category coverage explicitly rather than infer it
from prose.

### `FailureEvent`

Required fields are `failure_id`, `run_id`, `case_id` when applicable,
`workflow_step`, `failure_code`, `materiality_result`, `materiality_policy_version`,
`epistemic_class`, `source_ref_ids`, `affected_artifact_ids`, `detected_by`,
`detected_at`, `disposition`, and `supersedes_failure_id`.

`failure_code` is one of:

`EXTRACTION`, `RECONCILIATION`, `SOURCE`, `UNIT`, `PERIOD`, `CALCULATION`,
`CITATION`, `INFERENCE`, `REVIEW`, `CUTOFF_LEAKAGE`, `SOURCE_CONFUSION`, or
`DOCUMENT_AS_INSTRUCTION`.

Subcodes may add detail but may not replace the required top-level code.
Multiple causal categories require multiple linked events or an explicit
primary/secondary relation; silently choosing one category is forbidden.

### `ReviewDecisionTelemetry`

Each claim review records `review_decision_id`, `run_id`, `report_id`,
`claim_id`, `case_id` if any, reviewer identity/role, `decision` (`ACCEPT`,
`EDIT`, `REJECT`, or `DEFER`), materiality result and policy version,
epistemic class, source-locate time, calculation-check time, total decision
time, correction category, instrumentation overhead, and UTC timestamps.
Known-case evaluation additionally records expected decision, observed
decision, and a mechanically derived outcome: `CORRECT_ACCEPT`,
`CORRECT_EDIT`, `CORRECT_REJECT`, or `CORRECT_DEFER` when they match, otherwise
`FALSE_ACCEPT`, `FALSE_EDIT`, `FALSE_REJECT`, or `FALSE_DEFER` according to the
observed decision. The expected/observed pair and derived outcome must agree;
coercion between decision classes fails validation. Edit accuracy is the share
of known cases whose expected decision is `EDIT` and observed decision is
`EDIT`; reject accuracy is defined analogously. False-accept and false-reject
categories are the mismatches whose observed decision is respectively
`ACCEPT` or `REJECT`. All known-case aggregations remain stratified by
materiality and epistemic class and retain report/company clustering keys.

### `SeededDrillIsolationRecord`

Every drill records the source golden case, shadow artifact ID, production
artifact ID if a corresponding clean run exists, isolation mechanism,
promotion eligibility fixed to `false`, publication eligibility fixed to
`false`, attempted boundary crossings, deletion/retention outcome, and a
verification result. The promotion and publication services must reject the
shadow artifact ID independently of document labels. Every fixture-execution
artifact carries its originating `case_id`, `case_version`, and run mode;
golden or shadow lineage fixes both eligibility values to `false` through all
derived test artifacts.

### Required interfaces

- The earnings-review workflow emits failure and review-decision records.
- The materiality contract supplies the materiality result and policy version.
- The claim contract supplies epistemic class and evidence direction.
- The success-metric contract consumes stratified telemetry without treating
  accepted-unchanged rate as standalone quality or clustered claims as
  independent samples.
- The claim-review workflow can open golden/shadow fixtures, but promotion and
  publication interfaces must reject every fixture and every artifact with
  golden/shadow lineage, including `REAL_SOURCE` cases.

## Invariants and fail-closed behavior

1. Source content is data, never control text. Retrieved text cannot change
   tools, permissions, cutoffs, promotion rules, or execution behavior and
   cannot request secrets.
2. A case without current source proof and competent label evidence is not an
   approved golden case and cannot count toward the initial twenty.
3. Missing or invalid manifest, owner commitment, resolvable repository
   location, machine-readable cadence, current case references, category
   coverage, or label version keeps A-08 unresolved.
4. An unknown failure code fails validation; it is not coerced to `REVIEW`.
5. Missing materiality, epistemic class, expected/observed decision, or a
   consistent derived outcome prevents known-case accuracy and
   false-accept/false-reject aggregation and blocks B-13 acceptance.
6. Manual and assisted measurements use the same instrumentation version;
   instrumentation overhead is separately recorded. Quarter 0 cannot be
   reused as an assisted quarter.
7. Every golden fixture and fixture-derived test artifact is non-promotable
   and non-publishable by lineage, enforced artifact type, and service checks;
   this includes real-source, synthetic, and seeded fixtures. A failed
   isolation check aborts the drill and blocks dependent acceptance.
8. Memory-draft provenance remains visible at promotion review; source text
   cannot authorize memory promotion.
9. External spot review is optional. Its procedure must be defined, but an
   absent external review may not be represented as performed.
10. No register status, delegated approval, analyst approval, or domain
    approval is inferred from document completion.

## Evidence and typed approval gates

| Gate | Required proof | Typed authority | Fail-closed result |
|---|---|---|---|
| Delegated spec approval | Fresh clean Sol xhigh review bound to this exact file hash and persisted review evidence | `DELEGATED_ARTIFACT_APPROVAL` | S07 remains draft; no implementation dependency may treat it as approved. |
| Golden-set ownership | Current manifest binding a named human and commitment record to a resolvable repository location, machine-readable cadence, scope, and initial cases | `NAMED_OWNER_COMMITMENT` | A-08 remains unresolved. |
| Golden labels | Current evidence for the expert-labeled initial inventory and label-change process | `DOMAIN_EXPERT_ACCEPTANCE` | Unapproved cases do not count toward twenty or terminal proof. |
| Analyst workflow fitness | Evidence that decision categories and timings match actual review work | `ANALYST_ACCEPTANCE` | B-13 remains unresolved. |
| Any external spot review | Scope, reviewer authority, evidence, and explicit decision, only if performed | `EXTERNAL_COORDINATION_APPROVAL` | Procedure may exist, but no external-review claim is allowed. |

Every non-delegated record must come from the canonical typed human-resolution
path with exact scope, actor, authority, timestamp, decision, and evidence.
One decision satisfies at most one declared requirement. A Sol review is not
human, analyst, domain, owner, or external authority.

## Acceptance tests and verification

Before owned rows can advance, verification must demonstrate:

- exact ownership of A-08, B-08, and B-13 and no other register row;
- one current machine-readable manifest whose named owner, commitment record,
  resolvable repository path, cadence, next due time, and at least twenty exact
  current case references validate;
- at least twenty current, uniquely identified, expert-labeled cases;
- explicit coverage for prompt injection, source confusion, wrong period,
  wrong unit, wrong source, unsupported claim, and fabricated citation;
- complete top-level failure-code coverage and rejection of unknown codes;
- symmetric manual/assisted instrumentation with separately measured overhead;
- Quarter 0 rejection when supplied as an assisted run;
- all four correct and all four false known-case outcomes, rejection of an
  outcome inconsistent with its expected/observed pair, edit and reject
  accuracy, and false-accept/false-reject aggregation by materiality and
  epistemic class;
- a document-as-instruction fixture that cannot alter tools, permissions,
  cutoff, secrets, execution, or promotion;
- real-source, synthetic, and seeded golden fixtures, plus every derived
  fixture-run artifact, rejected by both promotion and publication paths;
- no known falsehood in a promotable or publishable artifact; and
- current typed evidence and one-to-one approval records for each mandatory
  human gate.

The implementation plan must provide argv-style deterministic commands for
schema validation, category-coverage validation, fixture execution, isolation
tests, and telemetry aggregation. Command output, exit code, scope hash, and
artifact hashes are persisted; prose or agent reports are not verification.

## Dependencies and sequencing

- A-08 has no register dependency and establishes the owner/inventory needed
  by B-08 and B-13.
- B-08 depends on A-08.
- B-13 depends exactly on A-03, A-08, and A-13. S07 consumes the manual
  baseline and success-metric interfaces without taking ownership of them.
- S07 supplies adversarial-document fixtures to S09 and reviewer controls to
  the earnings-review and claim-review specs.

## Amendment gate

No mandatory evidence-derived amendment gate is assigned to S07 in the
Exact 25-spec program. Any later change to its ownership, source semantics,
activation classification, or closed contracts requires authority
reconciliation and a fresh Sol xhigh review; it may not be silently absorbed
as implementation detail.
