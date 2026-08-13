# S22 — Conditional stress-test-company expansion

Status: DRAFT — AWAITING FRESH SOL XHIGH REVIEW

## Contract posture

This document is the implementation contract for S22. Normative terms MUST,
MUST NOT, SHOULD, and MAY are binding. S22 specifies a dormant capability and
its activation, isolation, evidence, and approval gates; it does not activate
E-02 or authorize implementation merely by existing.

## Authority and ownership

| Authority | Exact source text | Effect in this contract |
|---|---|---|
| Exact 25-spec table | `S22` | Stable spec identifier. |
| Exact 25-spec table | `Conditional stress-test-company expansion` | Exact title. |
| Exact 25-spec table | `docs/specs/equity-os-s22-conditional-stress-test-companies.md` | Exact owned path. |
| Exact 25-spec table | `E-02` | Sole primary register owner. |
| Exact 25-spec table | `None directly; v2 controls` | No direct disposition item is assigned; v2 remains controlling. |
| Activation classification | `the dormant-only specs are exactly S03, S04, and S20–S25` | S22 is dormant-only at the pinned draft snapshot. |
| E-02 register priority | `High` | Exact source priority; this draft does not change it. |
| E-02 register decision or action | `Add stress-test companies` | Exact owned action. |
| E-02 required evidence / acceptance | `One bank/NBFC, one conglomerate, and one difficult disclosure/corporate-action case` | All three exact archetypes are mandatory. |
| E-02 dependencies | `C-01` | Exact register dependency edge. |
| E-02 source status | `Deferred` | E-02 remains dormant until the governed transition completes. |

The v2 decision register is operational authority for E-02 Status and its
gates. This draft neither changes that Status nor supplies an activation
decision. If this document conflicts with the register, the register wins and
the conflict blocks work.

## Scope

After valid activation, S22 governs a bounded evaluation of whether the
vertical-slice contracts generalize to deliberately selected additional
companies. It covers:

- selection of stress dimensions and candidate companies;
- reuse of the approved ingestion, observation/fact, claim, workflow, compute,
  review, and evidence-package interfaces without silent company-specific
  exceptions;
- isolated execution, comparison with the discovery-company baseline, and
  explicit classification of every discovered contract delta; and
- evidence needed to accept, reject, revise, or defer broader-company support.

## Non-goals

S22 does not define a production universe, authorize bulk onboarding, promise
cross-sector generality, procure data, alter the source-of-truth hierarchy,
change an approved schema implicitly, distribute research, or permit automated
memory promotion. It does not treat a successful run as permission to activate
another Deferred component.

## Interfaces and data contracts

All records are immutable, schema-versioned, content-addressed, and refer to
repository-relative or canonical store identifiers. Unknown evidence remains
unknown; it is never represented by a guessed value.

### `StressTestExpansionProtocol`

| Field | Type | Contract |
|---|---|---|
| `protocol_id` | stable identifier | Unique and immutable. |
| `supersedes_protocol_id` | nullable stable identifier | Names the immediately prior protocol version when this body replaces one; null for the first version. Prior bodies remain immutable. |
| `spec_id` | enum | Exactly `S22`. |
| `register_id` | enum | Exactly `E-02`. |
| `deferred_activation_envelope` | content-addressed one-time component envelope | Contains `envelope_id`, `spec_id=S22`, `component_id`, `register_id=E-02`, `activation_record_id`, `activation_record_sha256`, `activation_predicate_id`, `activation_predicate_sha256`, `activation_approval_record_id`, `human_resolution_decision_id`, `human_resolution_sha256`, and `content_sha256`. It identifies the single retained E-02 Deferred-transition record and MUST NOT contain `protocol_id`, `protocol_body_sha256`, or another runtime-body field. It is attached after the body digest is computed and is outside that digest's preimage. |
| `baseline_run_ids` | nonempty identifier array | Approved discovery-company runs used as the comparison baseline. |
| `stress_dimensions` | nonempty enum array | Chosen from sector, size, reporting complexity, segment complexity, document variation, and source coverage. |
| `candidate_companies` | exactly three typed objects | Unique stable entity IDs; exactly one object has each `mandatory_archetype` value `BANK_OR_NBFC`, `CONGLOMERATE`, and `DIFFICULT_DISCLOSURE_OR_CORPORATE_ACTION`. Each also contains selection rationale, covered dimensions, source-rights result, and reviewer decision ID. Generic stress dimensions never substitute for an archetype. |
| `frozen_contract_versions` | nonempty map | Exact versions of every upstream interface under test. |
| `budgets` | object | Maximum companies, documents, analyst minutes, compute, and elapsed time. |
| `success_rules` | nonempty array | Mechanically evaluable thresholds fixed before execution. |
| `stop_rules` | nonempty array | Safety, rights, evidence, quality, and budget termination conditions. |
| `operational_approval_envelope` | content-addressed replaceable body envelope | Contains `envelope_id`, nullable `supersedes_envelope_id`, `protocol_id`, `protocol_body_sha256`, `spec_id=S22`, `register_id=E-02`, ordered nonempty `required_approval_ids`, and `content_sha256`. The ID list contains exact one-to-one body-scoped pre-run requirements `S22-G02B` through `S22-G05`; source-conditioned requirements are resolved before protocol freeze. `S22-G01` is a separate spec-artifact gate, `S22-G02A` is represented only by `deferred_activation_envelope`, and `S22-G06` and `S22-G07` are instantiated after their result or thesis diff exists. |
| `protocol_body_sha256` | lowercase SHA-256 | Envelope-excluded body digest defined below. |

`protocol_body_sha256` is SHA-256 of canonical JSON of every protocol field
except `deferred_activation_envelope`, `operational_approval_envelope`, and
`protocol_body_sha256`. Canonical JSON is UTF-8 with sorted keys, no
insignificant whitespace, direct Unicode, JSON booleans/null, and arrays in
declared order. The body is frozen and hashed before the component-activation
and operational-approval envelopes are attached. Every operational approval
requirement scope MUST name `protocol_id`, `protocol_body_sha256`, `S22`, and
`E-02`; `S22-G02B` additionally states that it authorizes only operation of
that exact body and uses an active `SATISFY_APPROVAL` resolution, never the
`ACTIVATE_DEFERRED` resolution. A requirement bound to another digest cannot
pass. The validator recomputes the body projection exactly, validates each
envelope independently,
and rejects a missing field, an extra field in the digest preimage, or any body
mutation not accompanied by a new digest and new scoped envelopes.

`operational_approval_envelope.content_sha256` is SHA-256 of canonical JSON of
the complete operational envelope except `content_sha256`. Its body identifiers
and digest MUST equal the recomputed immutable protocol body, and its ID list
MUST resolve one-to-one to the complete current requirements and approval
records for that body. The envelope and every referenced requirement/record are
new for each body version; mutation creates a new envelope digest and never
changes the Deferred activation envelope. `supersedes_envelope_id` is null only
for V1 and otherwise names the immediately prior same-register envelope; forks,
cycles, cross-register links, and skipped lineage fail. Only the unreplaced leaf
is current for a new run. Supersession makes the prior envelope historical but
does not alter its body, records, or completed-run evidence.

`S22-G01-DELEGATED-ARTIFACT` is independent of every runtime protocol. Its
scope MUST name `S22`, this repository-relative path, and the SHA-256 of the
exact spec file bytes reviewed. Its record carries the clean review round,
reviewer identity/session, source hashes, timestamp, and persisted evidence
path. It MUST NOT depend on or name a future `protocol_id`,
`protocol_body_sha256`, activation record, or E-02 runtime approval. Any edit
to the spec bytes requires a new artifact review and record; a later protocol
change neither supplies nor invalidates the artifact approval for unchanged
spec bytes.

`deferred_activation_envelope` is immutable and has exactly the twelve fields
declared above. After dereferencing `activation_record_id`, the validator
resolves the unique registered component named by
`activation_record.component_id`. The envelope projection over the nine keys
below MUST equal this canonical projection exactly:

```text
{
  spec_id: registered_component.primary_spec.spec_id,
  component_id: activation_record.component_id,
  register_id: activation_record.register_id,
  activation_record_id: activation_record.activation_record_id,
  activation_predicate_id: activation_record.activation_predicate_id,
  activation_predicate_sha256: activation_record.activation_predicate_sha256,
  activation_approval_record_id: activation_record.approval_record_id,
  human_resolution_decision_id: activation_record.human_resolution_decision_id,
  human_resolution_sha256: activation_record.human_resolution_sha256
}
```

Thus `spec_id` is derived from the registered component owner, not from an
activation-record field. Component, register, activation-record, predicate,
and resolution IDs/digests compare directly; only the approval reference uses
the explicit name mapping above. The three envelope-only values have separate,
acyclic rules: `activation_record_sha256` equals SHA-256 of canonical JSON of
the complete dereferenced activation record; `envelope_id` equals lowercase
SHA-256 of canonical JSON of the complete envelope excluding `envelope_id` and
`content_sha256`; and `content_sha256` equals lowercase SHA-256 of canonical
JSON of the complete envelope excluding only `content_sha256`, including the
validated `envelope_id`. The validator recomputes each preimage independently.

It accepts exactly one envelope for E-02 only when
`activation_source_status=Deferred`, live source status is `Open`, `In
progress`, or `Accepted`, every projection equality and digest rule above
passes, and the record is the single activation record created on the legal
`Deferred -> Open|In progress` transition. The activation record, its approved
`GOAL_OR_PROCESS_AUTHORIZATION` record, and its active `ACTIVATE_DEFERRED`
canonical human resolution MUST carry the same component, register, activation
scope, predicate ID/digest, decision ID, and resolution digest. The activation
scope is component-local and MUST NOT name or authorize a runtime protocol.

For activation currentness, the validator recomputes the governed predicate
using three-valued logic and hashes canonical JSON with exactly these keys and
values: `predicate_id`, `expression`, `metrics`, deterministically
`resolved_values`, `digest_sources`, `result`, and `evaluated_at`. The stored
activation predicate digest MUST equal that current digest, the result MUST be
`TRUE`, and all metrics MUST be resolved and unexpired. The referenced
activation resolution and approval MUST remain active, purpose-matching,
unsuperseded, and unrevoked. A later protocol reuses the same envelope ID and
`content_sha256`; it obtains a new body digest and wholly new body-scoped
operational approvals. A second activation envelope, activation record, or
`Deferred` transition for E-02 is invalid. Missing, copied, stale, superseded,
revoked, extra, or content-mismatched activation values leave E-02 dormant.

Each referenced operational approval requirement contains `approval_id`,
`approval_type`, `required_authority`, `scope`, `status`, `actor`, `timestamp`,
`evidence_ref_ids`, and `matched_record_id`. Each record contains
`approval_record_id`, `approval_type`, `authority`, `scope`, `decision`,
`actor`, `timestamp`, `evidence_ref_ids`, `authority_source`, `human_review_id`,
`resolution_decision_id`, and `resolution_content_sha256`. Every operational
record MUST use `HUMAN_RESOLUTION` and copy type, authority, scope, actor,
timestamp, evidence, canonical decision ID, and digest from one active immutable
`SATISFY_APPROVAL` resolution. It MUST remain current, unexpired,
unsuperseded, and unrevoked and MUST bind the exact current protocol body. It
MUST NOT use the component's `ACTIVATE_DEFERRED` decision or activation approval
record. That resolution digest is SHA-256 of canonical JSON of the complete
resolution object except `content_sha256`; its `entry_authority_sha256` is the
same digest over the referenced human-review entry excluding `state`,
`resolution_decision_ids`, and `content_sha256`. The separate `S22-G01`
artifact record uses `DELEGATED_AUTOMATED` with null human-resolution fields.
Any absent field or mismatch leaves the requirement `UNRESOLVED`; only
`SATISFIED` passes.

### `StressTestCompanyResult`

Each result contains stable `result_id`, `protocol_id`, `entity_id`, `run_ids`,
frozen evidence package IDs, source hashes, knowledge cutoff, interface
versions, validator results, analyst-review minutes, corrections, unresolved
failures, a terminal state of `PASS`, `FAIL`, or `BLOCKED`, and
`result_body_sha256`. The digest is SHA-256 of canonical JSON of every result
field except `result_body_sha256`. `BLOCKED` is not counted as a pass and
missing companies remain in the denominator.

### `ContractDeltaDecision`

Every observed difference is recorded as `RETAIN`, `ADD`, `CHANGE`, `DEFER`,
or `REJECT`, with the affected contract, exact evidence, compatibility impact,
owner, and required approval types. A delta is only a proposal until the owned
upstream spec is amended, freshly reviewed, and approved. S22 MUST NOT mutate
another spec or schema by implication.

## Invariants and fail-closed behavior

1. Sequencing is fail closed: the separately scoped spec-artifact gate controls
   whether this contract may be implemented but is not a runtime protocol
   requirement. At runtime, `protocol_body_sha256` validates before the
   one-time activation and replaceable approval envelopes. The immutable
   `S22-G02A` component envelope MUST validate; `S22-G02B`, both `S22-G03`
   requirements, every applicable `S22-G04` requirement, and both `S22-G05`
   requirements MUST be `SATISFIED` before a candidate run starts. `S22-G06`
   may be satisfied only from completed results; `S22-G07` may be satisfied only
   after `S22-G06`.
   `S22-G06` and `S22-G07` are absent from the frozen pre-run inventory and are
   instantiated in a separate result-level envelope only after the content they
   bind exists.
2. A copied ledger label, coordinator statement, this draft, or delegated
   artifact approval cannot activate E-02.
3. The protocol contains exactly the three mandatory E-02 archetypes, with one
   distinct company per archetype; omission, duplication, or substitution with
   a generic stress dimension is `BLOCKED`.
4. The protocol and success rules are frozen before the first candidate run.
5. Every run uses one frozen evidence package and one explicit knowledge
   cutoff; downstream steps MUST NOT fetch new evidence invisibly.
6. Company results remain isolated. Data, claims, and corrections MUST carry
   stable entity identity and MUST NOT leak between companies.
7. Material claims resolve to a fact ID, calculation trace, or exact source
   location and retain epistemic class.
8. A rights failure, missing source hash, unresolved identity, stale activation
   proof, budget breach, validator failure, or missing approval produces
   `BLOCKED` and stops the affected run.
9. No stress result is promoted to the canonical thesis without the separate
   analyst-controlled review and memory-promotion transaction.
10. Dormant mode creates no runtime resources, schedules, credentials, provider
   calls, purchases, or product-code dependency.

## Evidence and typed human-approval gates

| Gate ID | Required evidence | Exact `approval_type` | Required authority | Fail-closed result |
|---|---|---|---|---|
| `S22-G01-DELEGATED-ARTIFACT` | Exact current spec-file SHA-256, clean fresh-context Sol xhigh review, source hashes, review round, timestamp, and persisted evidence path | `DELEGATED_ARTIFACT_APPROVAL` | Delegated authority under the activated goal | Draft remains unapproved. This document records no such approval. |
| `S22-G02A-COMPONENT-ACTIVATION` | Current TRUE predicate digest, component-local evidence, the single retained E-02 activation record and record digest, and matching canonical human-resolution digest; scope excludes every protocol/body identifier | `GOAL_OR_PROCESS_AUTHORIZATION` | Competent human authorized for exact E-02 `ACTIVATE_DEFERRED` component scope | E-02 remains dormant. |
| `S22-G02B-PROTOCOL-AUTHORIZATION` | Exact `protocol_id`, `protocol_body_sha256`, `S22`, `E-02`, purpose, budgets, stops, and current supporting evidence | `GOAL_OR_PROCESS_AUTHORIZATION` | Competent human authorized to operate that exact protocol body through a distinct active `SATISFY_APPROVAL` resolution | That protocol body does not run. |
| `S22-G03A-SELECTION-ANALYST` | Exact three-company matrix, source coverage, conflicts, rationales, and fixed denominator | `ANALYST_ACCEPTANCE` | Competent analyst | No candidate run starts. |
| `S22-G03B-SELECTION-DOMAIN` | Evidence that each selected company satisfies its named mandatory archetype | `DOMAIN_EXPERT_ACCEPTANCE` | Competent domain expert | No candidate run starts. |
| `S22-G04A-DATA-RIGHTS` | Source-by-source permitted-use and retention determination | `DATA_RIGHTS_APPROVAL` | Competent data-rights authority | Affected source and company are blocked. |
| `S22-G04B-PROVIDER` | Provider terms require authorization for the exact use; requirement is included when that current policy predicate is `TRUE` | `PROVIDER_AUTHORIZATION` | Competent provider authority | Affected source and company are blocked. |
| `S22-G04C-LEGAL` | Legal adjudication is required for the exact source/use; requirement is included when that current policy predicate is `TRUE` | `LEGAL_REVIEW` | Competent legal authority | Affected source and company are blocked. |
| `S22-G05A-BUDGET` | Bounded company, document, compute, and review spend | `BUDGET_APPROVAL` | Competent budget authority | No resource-consuming run starts. |
| `S22-G05B-CAPACITY` | Bounded analyst and compute capacity | `CAPACITY_COMMITMENT` | Competent capacity owner | No resource-consuming run starts. |
| `S22-G06-RESULT` | Reviewed result and correction record | `ANALYST_ACCEPTANCE` | Competent analyst | Result remains unaccepted evaluation evidence. |
| `S22-G07-PROMOTION` | Exact approved thesis diff through the separate promotion transaction | `MEMORY_PROMOTION` | Competent memory-promotion authority | Canonical thesis is unchanged. |

`S22-G01`, `S22-G02A`, `S22-G06`, and `S22-G07` are not listed in
`operational_approval_envelope.required_approval_ids`. G01 cannot satisfy a
runtime requirement; G02A is the one-time component envelope; G06 and G07 are
separate result-level
requirements. `S22-G02B` and every other operational requirement are newly
instantiated for each body digest. One approval record satisfies one declared
requirement only. A condition for `S22-G04B` or `S22-G04C` that is
`UNKNOWN` blocks the source; it is never treated as false. Delegated artifact
approval never satisfies activation, analyst, domain, provider, legal, rights,
budget, capacity, regulatory, production, distribution, or promotion authority.

Every `S22-G06` scope additionally names the exact `result_id` and
`result_body_sha256` reviewed. `S22-G07` additionally names that accepted result,
the separate promotion-transaction ID, and the exact thesis-diff content digest.
Neither approval changes the immutable result body; changed result or thesis-diff
bytes require a new scoped requirement and record.

## Acceptance tests and verification

Before activation:

1. A structural test proves no S22 executable entry point, schedule, provider
   call, credential, or runtime dependency is enabled.
2. Attempts using no activation record, a false/unknown/stale predicate, a
   changed predicate preimage, an unresolved metric, a mismatched protocol-body
   or resolution digest, a superseded/revoked resolution, a reused approval
   record, or delegated artifact approval alone are rejected before any run.
3. Negative binding fixtures mutate a protocol-body field without replacing
   `protocol_body_sha256`, bind an operational approval to a different body
   digest, put a protocol/body field in the component activation envelope, and
   include either envelope in the canonical body preimage; every fixture is
   rejected. Changing only an envelope leaves the body digest stable but still
   fails unless the immutable activation envelope is current and the replacement
   operational envelope is current and matches the frozen body scope exactly.
   Component-envelope fixtures independently mutate each of the nine projected
   fields listed above while recomputing envelope-only hashes, and independently
   mutate `activation_record_sha256` with both envelope hashes recomputed,
   `envelope_id` with `content_sha256` recomputed, and `content_sha256` alone;
   every fixture is rejected by the rule whose preimage or equality it violates.
4. Negative artifact-scope fixtures omit or alter the reviewed spec-file
   SHA-256, bind `S22-G01` to a runtime protocol, place `S22-G01`, `S22-G02A`,
   `S22-G06`, or `S22-G07` in
   `operational_approval_envelope.required_approval_ids`, pre-create a
   result-level requirement
   without its content digest, or use a runtime approval to satisfy G01; every
   fixture is rejected without affecting E-02's dormant state.

After activation:

5. Re-version fixtures approve body V1, then freeze a distinct protocol ID and
   body V2 with explicit protocol/envelope supersession links. V2
   reuses the exact V1 `deferred_activation_envelope` ID and digest and supplies
   wholly new `S22-G02B` through `S22-G05` requirements and records bound to V2;
   V2 passes without another E-02 Status transition. Reusing any V1 operational
   record for V2, issuing a second activation record/envelope, or attempting a
   second `Deferred -> Open|In progress` transition is rejected. Revocation or
   staleness blocks the authority it actually governs: activation-envelope
   invalidity blocks every body, while one body's approval invalidity blocks
   only that body.
6. The fixture matrix contains exactly one distinct bank/NBFC, one distinct
   conglomerate, and one distinct difficult disclosure/corporate-action case.
   Omitting, duplicating, or replacing any archetype deterministically yields
   `BLOCKED`; a valid matrix runs against the same frozen contract versions and
   produces isolated content-addressed results.
7. Missing evidence, source-rights denial, identity ambiguity, schema mismatch,
   budget exhaustion, and validator failure each deterministically produce
   `BLOCKED` without partial promotion.
8. Replaying identical inputs produces identical deterministic outputs or a
   documented nondeterministic boundary; no later-known evidence enters a run.
9. Every discovered delta has exactly one `ContractDeltaDecision`, and no
   `ADD` or `CHANGE` becomes operative without an amendment to its owning spec.
10. The final report preserves all failures and blocked cases in its denominator
   and reconciles every run, approval, and evidence reference; requirement and
   record IDs are one-to-one and every approval scope matches the frozen
   `protocol_body_sha256`. Negative fixtures change result bytes after
   `S22-G06`, reuse one result approval for another result, and change the thesis
   diff after `S22-G07`; each invalidates the affected approval without altering
   prior immutable evidence.

Verification evidence MUST record the exact command, exit status, artifact
hashes, validator output, execution time, and reviewer identity. Conversation
text and agent summaries are not proof.

## Dependencies

- Exact register dependency `E-02 -> C-01`, register authority, and valid E-02
  activation are hard prerequisites for any active implementation.
- Approved discovery-company baseline and bootstrap thesis (S05).
- Approved success metrics and operating budgets (S08).
- Approved source/evidence, reproducibility, observation/fact, claim, workflow,
  human-review, and deterministic-compute contracts (S10–S16 as applicable).
- Entity/security identity and corporate-action controls (S17).

An unavailable dependency blocks only the affected cone and cannot be waived
by reducing the acceptance threshold after seeing results.

## Deferred activation guard

Until E-02 is validly activated, permitted work is limited to authoring,
reviewing, and verifying this dormant contract and its non-executable fixtures.
Implementation planning, product code, live provider access, company
onboarding, runtime configuration, and evaluation execution are prohibited.
After activation, work is limited to the exact approved scope and budgets;
activation of E-02 does not activate E-03, E-04, E-05, or E-10.

## Amendment gate

No evidence-derived provisional amendment gate is assigned to S22 in the
goal's amendment table. Any change to this contract still requires source
reconciliation, the normal capped review/fix policy, a fresh clean Sol xhigh
review, and delegated artifact approval. Activation alone is not an amendment
or approval.
