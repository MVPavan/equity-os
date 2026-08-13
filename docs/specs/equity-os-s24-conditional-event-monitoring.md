# S24 — Conditional event monitoring

Status: DRAFT — AWAITING FRESH SOL XHIGH REVIEW

## Contract posture

This document is the implementation contract for S24. Normative terms MUST,
MUST NOT, SHOULD, and MAY are binding. It defines dormant event-monitoring
boundaries for E-04 and does not activate E-04, authorize background execution,
or approve external delivery.

## Authority and ownership

| Authority | Exact source text | Effect in this contract |
|---|---|---|
| Exact 25-spec table | `S24` | Stable spec identifier. |
| Exact 25-spec table | `Conditional event monitoring` | Exact title. |
| Exact 25-spec table | `docs/specs/equity-os-s24-conditional-event-monitoring.md` | Exact owned path. |
| Exact 25-spec table | `E-04` | Sole primary register owner. |
| Exact 25-spec table | `None directly; v2 controls` | No direct disposition item is assigned; v2 remains controlling. |
| Activation classification | `the dormant-only specs are exactly S03, S04, and S20–S25` | S24 is dormant-only at the pinned draft snapshot. |
| E-04 register priority | `High` | Exact source priority; this draft does not change it. |
| E-04 register decision or action | `Add event monitoring` | Exact owned action. |
| E-04 required evidence / acceptance | `Alerts identify which fact, assumption, catalyst, promise, falsifier, or thesis breaker changed; immaterial events do not rewrite thesis` | Exact alert and immaterial-event semantics. |
| E-04 dependencies | `C-04` | Exact register dependency edge. |
| E-04 source status | `Deferred` | E-04 remains dormant until the governed transition completes. |

The v2 decision register controls E-04 Status and gates. This draft does not
change that Status or constitute an activation record. Any conflict blocks
work and is resolved in favor of the register.

## Scope

After valid activation, S24 governs bounded detection, normalization,
deduplication, routing, and human review of covered company events. Monitoring
consumes authorized point-in-time captures and produces candidate alerts and
workflow triggers with exact evidence, valid time, knowledge time, and replay
provenance.

## Non-goals

S24 does not create a trading system, promise real-time or complete coverage,
scrape unapproved sources, infer facts from price movement alone, silently
modify a thesis, auto-publish research, send personalized recommendations,
operate an execution system, or recreate point-in-time history that was never
captured.

## Interfaces and data contracts

### `MonitoringActivationConfig`

| Field | Type | Contract |
|---|---|---|
| `config_id` | stable identifier | Unique, immutable version. |
| `supersedes_config_id` | nullable stable identifier | Names the immediately prior configuration version when this body replaces one; null for the first version. Prior bodies remain immutable. |
| `spec_id` / `register_id` | enums | Exactly `S24` / `E-04`. |
| `deferred_activation_envelope` | content-addressed one-time component envelope | Contains `envelope_id`, `spec_id=S24`, `component_id`, `register_id=E-04`, `activation_record_id`, `activation_record_sha256`, `activation_predicate_id`, `activation_predicate_sha256`, `activation_approval_record_id`, `human_resolution_decision_id`, `human_resolution_sha256`, and `content_sha256`. It identifies the single retained E-04 Deferred-transition record and MUST NOT contain `config_id`, `config_body_sha256`, or another runtime-body field. It is attached after the body digest is computed and is outside that digest's preimage. |
| `covered_entity_ids` | nonempty identifier array | Explicit, approved scope; no wildcard universe. |
| `source_ids` | nonempty identifier array | Each resolves to rights and retention evidence. |
| `event_type_versions` | nonempty map | Closed event vocabulary and schema versions. |
| `capture_cadence` | object | Per-source poll/event cadence and expected latency. |
| `ruleset_version` | identifier | Immutable detection and materiality rules. |
| `budgets` | object | Requests, documents, storage, compute, analyst review, and delivery limits. |
| `destinations` | array | Empty by default; each item fixes destination ID, boundary class, audience, purpose, content schema/version, and independent configuration-approval requirements. |
| `kill_switch_owner` | human authority reference | Named competent operator, not an agent. |
| `approval_bindings` | content-addressed closed replaceable configuration envelope | Contains `envelope_id`, nullable `supersedes_envelope_id`, `config_id`, `config_body_sha256`, `spec_id=S24`, `register_id=E-04`, the exact typed reference maps below, and `content_sha256`. It contains `S24-G02B` and concrete configuration-level requirements instantiated from `S24-G03` through `S24-G05`; per-alert `S24-G06` through `S24-G08` requirements bind later to the alert body digest. This envelope is outside the configuration-body digest's preimage. |
| `config_body_sha256` | lowercase SHA-256 | Envelope-excluded body digest defined below. |

`config_body_sha256` is SHA-256 of canonical JSON of every configuration field
except `deferred_activation_envelope`, `approval_bindings`, and
`config_body_sha256`. Canonical JSON is UTF-8 with sorted keys, no insignificant
whitespace, direct Unicode, JSON booleans/null, and arrays in declared order.
The body is frozen and hashed before the component-activation and
configuration-approval envelopes are attached. Every configuration approval
requirement scope MUST name `config_id`,
`config_body_sha256`, `S24`, and `E-04`; `S24-G02B` additionally states that it
authorizes only operation of that exact body and uses an active
`SATISFY_APPROVAL` resolution, never the `ACTIVATE_DEFERRED` resolution. A
requirement bound to another digest cannot pass. The validator recomputes the
body projection exactly, validates each envelope independently, and rejects a
missing field, an extra field in the digest preimage, or any body mutation not
accompanied by a new digest and new scoped envelopes.

`S24-G01-DELEGATED-ARTIFACT` is independent of every runtime configuration. Its
scope MUST name `S24`, this repository-relative path, and the SHA-256 of the
exact spec file bytes reviewed. Its record carries the clean review round,
reviewer identity/session, source hashes, timestamp, and persisted evidence
path. It MUST NOT depend on or name a future `config_id`,
`config_body_sha256`, activation record, or E-04 runtime approval. Any edit to
the spec bytes requires a new artifact review and record; a later configuration
change neither supplies nor invalidates the artifact approval for unchanged
spec bytes.

`approval_bindings` contains exactly one `S24-G02B` body-authorization ID; an
exact source-ID map to separate
`DATA_RIGHTS_APPROVAL` and, when applicable, `PROVIDER_AUTHORIZATION`,
`LEGAL_REVIEW`, and `CREDENTIAL_ACCESS_APPROVAL` requirement IDs; operations
IDs for `BUDGET_APPROVAL`, `CAPACITY_COMMITMENT`, and
`NAMED_OWNER_COMMITMENT`; ruleset IDs for `ANALYST_ACCEPTANCE` and
`DOMAIN_EXPERT_ACCEPTANCE`; and an exact destination-ID map to separate
internal `ANALYST_ACCEPTANCE` and, for every distribution boundary,
`DISTRIBUTION_APPROVAL`, `LEGAL_REVIEW`, and `REGULATORY_REVIEW` requirement
IDs. The destination requirements are instantiated from `S24-G05C` through
`S24-G05F`; `S24-G06` through `S24-G08` are never configuration bindings. Map
key sets MUST equal the configured source and destination sets. Applicability
is derived from current typed policy evidence before the configuration is
frozen; `UNKNOWN`, a missing key, or a reference bound to a different
configuration blocks the affected source or destination. Each concrete
requirement ID appears exactly once, while one gate template may produce
multiple separately scoped source or destination requirements. These
configuration approvals authorize only the configured route. They never
satisfy the later per-alert delivery or promotion requirements.

`approval_bindings.content_sha256` is SHA-256 of canonical JSON of the complete
configuration-approval envelope except `content_sha256`. Its configuration
identifiers and digest MUST equal the recomputed immutable configuration body,
and every typed ID MUST resolve one-to-one to a complete current requirement and
approval record for that body. The envelope and every referenced
requirement/record are new for each configuration version; mutation creates a
new envelope digest and never changes the Deferred activation envelope.
`supersedes_envelope_id` is null only for V1 and otherwise names the immediately
prior E-04 envelope; forks, cycles, cross-register links, and skipped lineage
fail. Only the unreplaced leaf is current for new background work. Supersession
makes the prior envelope historical but does not alter its configuration,
records, or completed-delivery evidence.

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

It accepts exactly one envelope for E-04 only when
`activation_source_status=Deferred`, live source status is `Open`, `In
progress`, or `Accepted`, every projection equality and digest rule above
passes, and the record is the single activation record created on the legal
`Deferred -> Open|In progress` transition. The activation record, its approved
`GOAL_OR_PROCESS_AUTHORIZATION` record, and its active `ACTIVATE_DEFERRED`
canonical human resolution MUST carry the same component, register, activation
scope, predicate ID/digest, decision ID, and resolution digest. The activation
scope is component-local and MUST NOT name or authorize a runtime configuration.

For activation currentness, the validator recomputes the governed predicate
using three-valued logic and hashes canonical JSON with exactly these keys and
values: `predicate_id`, `expression`, `metrics`, deterministically
`resolved_values`, `digest_sources`, `result`, and `evaluated_at`. The stored
activation predicate digest MUST equal that current digest, the result MUST be
`TRUE`, and all metrics MUST be resolved and unexpired. The referenced
activation resolution and approval MUST remain active, purpose-matching,
unsuperseded, and unrevoked. A later configuration reuses the same envelope ID
and `content_sha256`; it obtains a new body digest and wholly new body-scoped
configuration approvals. A second activation envelope, activation record, or
`Deferred` transition for E-04 is invalid. Missing, copied, stale, superseded,
revoked, extra, or content-mismatched activation values leave E-04 dormant.

Each referenced operational approval requirement contains `approval_id`,
`approval_type`, `required_authority`, `scope`, `status`, `actor`, `timestamp`,
`evidence_ref_ids`, and `matched_record_id`. Each record contains
`approval_record_id`, `approval_type`, `authority`, `scope`, `decision`,
`actor`, `timestamp`, `evidence_ref_ids`, `authority_source`, `human_review_id`,
`resolution_decision_id`, and `resolution_content_sha256`. Every operational
record MUST use `HUMAN_RESOLUTION` and copy type, authority, scope, actor,
timestamp, evidence, canonical decision ID, and digest from one active immutable
`SATISFY_APPROVAL` resolution. It MUST remain current, unexpired,
unsuperseded, and unrevoked and MUST bind the exact current configuration body.
It MUST NOT use the component's `ACTIVATE_DEFERRED` decision or activation
approval record. That resolution digest is SHA-256 of canonical JSON of the
complete resolution object except `content_sha256`; its
`entry_authority_sha256` is the
same digest over the referenced human-review entry excluding `state`,
`resolution_decision_ids`, and `content_sha256`. The separate `S24-G01`
artifact record uses `DELEGATED_AUTOMATED` with null human-resolution fields.
Any absent field or mismatch leaves the requirement `UNRESOLVED`; only
`SATISFIED` passes.

### `CapturedEvent`

Each event contains stable event and entity/security IDs, event type/version,
source document ID and hash, exact source location, raw and normalized payload,
valid time, knowledge time, first-seen time, capture time, supersession link,
deduplication key, rights-policy version, and ingestion-run ID. Corrections
append and supersede; they never overwrite the prior occurrence.

### `AlertCandidate`

An alert contains the event ID, materiality rule and version, matched evidence,
epistemic class, confidence, a nonempty `affected_targets` array, materiality
(`MATERIAL` or `IMMATERIAL`), observable falsifier, knowledge cutoff, routing
class, nullable `proposed_thesis_diff_id`, derived review state, and suppression
or supersession links, plus `alert_body_sha256`. Every affected target contains
exactly one `target_type` from `FACT`, `ASSUMPTION`, `CATALYST`, `PROMISE`, `FALSIFIER`, and
`THESIS_BREAKER`, its stable target ID, and the evidence-backed changed value or
state. Allowed review states are `PENDING`, `APPROVED_INTERNAL`, `REJECTED`,
`SUPERSEDED`, and `BLOCKED`. Detection does not equal approval.

`alert_body_sha256` is SHA-256 of canonical JSON of every alert field except
`review_state` and `alert_body_sha256`. `review_state` is a projection derived
only from the immutable candidate body, active per-alert approval envelope, and
supersession state; it is never an authority input and cannot change the body
digest. Every per-alert `S24-G06`, `S24-G07`, or `S24-G08` requirement scope
binds the exact alert ID and body digest plus `config_id` and
`config_body_sha256`. Those requirements form a separate per-alert approval
envelope created only after the candidate exists. They are not stored in
`approval_bindings` and cannot be copied from a configuration-level destination
approval.

For each alert, the per-alert envelope contains one concrete `S24-G06`
requirement per proposed internal delivery, one concrete requirement for each
of `S24-G07A` through `S24-G07C` per proposed distribution-boundary delivery,
and one `S24-G08` only when a material alert proposes a thesis diff. A gate
template may therefore produce multiple destination-scoped requirement IDs;
each concrete ID and matched record remains one-to-one.

Every `S24-G06` and `S24-G07` scope also binds the exact destination, audience,
purpose, and delivered-content digest. `S24-G08` additionally binds the non-null
`proposed_thesis_diff_id`, promotion-transaction ID, and exact thesis-diff
content digest. Changed alert, delivered, or thesis-diff bytes require a new
scoped requirement and record.

### `MonitoringRunManifest`

The manifest binds configuration, source snapshots, cutoff, code/ruleset
versions, requests, retries, deduplication decisions, emitted and suppressed
candidates, failures, approvals, and terminal `COMPLETE`, `PARTIAL`, or
`BLOCKED`. `PARTIAL` is visible and cannot satisfy a completeness claim.

## Invariants and fail-closed behavior

1. Sequencing is fail closed: the separately scoped spec-artifact gate controls
   whether this contract may be implemented but is not a runtime configuration
   requirement. At runtime, `config_body_sha256` validates before the
   one-time activation and replaceable configuration-approval envelopes. The
   immutable `S24-G02A` component envelope MUST validate; `S24-G02B`, every
   applicable `S24-G03`, all `S24-G04`, `S24-G05A` and `S24-G05B`, and each
   applicable concrete destination requirement instantiated from `S24-G05C`
   through `S24-G05F` MUST be `SATISFIED` before the corresponding
   scheduler, source, rule, credential, or route is enabled. A candidate then
   requires its own content-bound
   `S24-G06` before internal delivery, all `S24-G07` requirements before crossing
   a distribution boundary, and `S24-G08` before promotion.
2. Dormant mode has no active scheduler, webhook, queue consumer, credential,
   provider call, destination, or runtime resource.
3. Only explicitly covered entities, event types, sources, and cadences may be
   processed. Wildcards and implicit expansion fail validation.
4. Originals are immutable. Corrections and restatements append with
   supersession; no record is silently overwritten.
5. Valid time, knowledge time, first-seen time, and capture time remain
   distinct and precisely defined.
6. Duplicate delivery is prevented by a deterministic event/rule/destination
   idempotency key; replay never masquerades as a newly known event.
7. Every candidate identifies at least one exact changed fact, assumption,
   catalyst, promise, falsifier, or thesis breaker. A missing, empty, unknown,
   or unresolvable affected-target classification is `BLOCKED`.
8. An `IMMATERIAL` event MUST have `proposed_thesis_diff_id=null` and MUST NOT
   invoke or satisfy the promotion path. A candidate alert is not itself a fact,
   approved thesis change, recommendation, or delivery authorization.
9. Rights uncertainty, identity ambiguity, missing source hash/location,
   unsupported event type, stale activation, expired approval, budget breach,
   queue poison item, or material clock anomaly fails closed and is surfaced.
10. Failure of one source or entity does not silently mark the run complete and
   does not erase independent successfully captured evidence.

## Evidence and typed human-approval gates

| Gate ID | Required evidence | Exact `approval_type` | Required authority | Fail-closed result |
|---|---|---|---|---|
| `S24-G01-DELEGATED-ARTIFACT` | Exact current spec-file SHA-256, fresh clean Sol xhigh review, source hashes, review round, timestamp, and persisted evidence path | `DELEGATED_ARTIFACT_APPROVAL` | Delegated authority under the activated goal | Draft remains unapproved. No approval is recorded here. |
| `S24-G02A-COMPONENT-ACTIVATION` | Current TRUE predicate digest, component-local evidence, the single retained E-04 activation record and record digest, and matching canonical human-resolution digest; scope excludes every configuration/body identifier | `GOAL_OR_PROCESS_AUTHORIZATION` | Competent human authorized for exact E-04 `ACTIVATE_DEFERRED` component scope | Monitoring remains dormant. |
| `S24-G02B-CONFIGURATION-AUTHORIZATION` | Exact `config_id`, `config_body_sha256`, `S24`, `E-04`, configured purpose, budgets, stops, and current supporting evidence | `GOAL_OR_PROCESS_AUTHORIZATION` | Competent human authorized to operate that exact configuration body through a distinct active `SATISFY_APPROVAL` resolution | That configuration remains disabled. |
| `S24-G03A-DATA-RIGHTS` | Per-source permitted use and retention | `DATA_RIGHTS_APPROVAL` | Competent data-rights authority | Source is disabled. |
| `S24-G03B-PROVIDER` | Provider authorization is required for the exact source/use; included when the policy predicate is `TRUE` | `PROVIDER_AUTHORIZATION` | Competent provider authority | Source is disabled. |
| `S24-G03C-LEGAL` | Legal adjudication is required for the exact source/use; included when the policy predicate is `TRUE` | `LEGAL_REVIEW` | Competent legal authority | Source is disabled. |
| `S24-G03D-CREDENTIAL` | Exact credential, source, purpose, storage path, and permitted operations; included for every credentialed source | `CREDENTIAL_ACCESS_APPROVAL` | Competent credential owner | Credentialed source is disabled. |
| `S24-G04A-BUDGET` | Request, storage, compute, analyst-review, and delivery limits | `BUDGET_APPROVAL` | Competent budget authority | Background execution remains disabled. |
| `S24-G04B-CAPACITY` | Capacity, SLO wording, recovery, and replay commitments | `CAPACITY_COMMITMENT` | Competent capacity owner | Background execution remains disabled. |
| `S24-G04C-OWNER` | Escalation path and named kill-switch/recovery owner | `NAMED_OWNER_COMMITMENT` | Competent named operator | Background execution remains disabled. |
| `S24-G05A-RULESET-ANALYST` | Event vocabulary, materiality fixtures, false-positive results, and covered entities | `ANALYST_ACCEPTANCE` | Competent analyst | Detection/routing remains disabled. |
| `S24-G05B-RULESET-DOMAIN` | Domain validity of event types, changed-target mappings, and materiality rules | `DOMAIN_EXPERT_ACCEPTANCE` | Competent domain expert | Detection/routing remains disabled. |
| `S24-G05C-INTERNAL-ROUTE-CONFIG` | Per-destination internal route, audience, purpose, and content schema/version | `ANALYST_ACCEPTANCE` | Competent analyst | Internal route remains disabled. |
| `S24-G05D-DISTRIBUTION-ROUTE-CONFIG` | Per-destination distribution boundary, audience, purpose, and content schema/version | `DISTRIBUTION_APPROVAL` | Competent distribution authority | Distribution route remains disabled. |
| `S24-G05E-DISTRIBUTION-LEGAL-CONFIG` | Legal decision for the configured distribution route and audience | `LEGAL_REVIEW` | Competent legal authority | Distribution route remains disabled. |
| `S24-G05F-DISTRIBUTION-REGULATORY-CONFIG` | Regulatory decision for the configured distribution route and audience | `REGULATORY_REVIEW` | Competent regulatory authority | Distribution route remains disabled. |
| `S24-G06-INTERNAL-ALERT` | Exact alert, evidence, recipient/purpose, and freshness | `ANALYST_ACCEPTANCE` | Competent analyst | Candidate is not delivered. |
| `S24-G07A-DISTRIBUTION` | Exact content/version, audience, and purpose | `DISTRIBUTION_APPROVAL` | Competent distribution authority | External or personalized delivery is prohibited. |
| `S24-G07B-DISTRIBUTION-LEGAL` | Legal decision for exact content/version and audience | `LEGAL_REVIEW` | Competent legal authority | External or personalized delivery is prohibited. |
| `S24-G07C-DISTRIBUTION-REGULATORY` | Regulatory decision for exact content/version and audience | `REGULATORY_REVIEW` | Competent regulatory authority | External or personalized delivery is prohibited. |
| `S24-G08-PROMOTION` | Approved thesis diff and reviewed supporting claims | `MEMORY_PROMOTION` | Competent memory-promotion authority | Canonical thesis is unchanged. |

`S24-G01` is not a runtime binding, `S24-G02A` is represented only by
`deferred_activation_envelope`, and `S24-G06` through `S24-G08` are instantiated
in the separate per-alert envelope. None may appear in `approval_bindings`;
`S24-G02B` MUST appear exactly once and is newly instantiated for every
configuration body. One approval record satisfies one concrete requirement
only. Every applicable
concrete requirement instantiated from `S24-G03` through `S24-G05` appears
exactly once in `approval_bindings`; a template may appear many times through
distinct per-source or per-destination requirement IDs. An applicability
predicate that is `UNKNOWN` blocks the source or destination. Delegated
artifact approval does not satisfy activation, rights, legal, provider,
credential, operations, capacity, analyst, domain, regulatory, distribution,
production, or promotion gates.

## Acceptance tests and verification

Before activation:

1. Structural tests prove all schedules, webhooks, consumers, credentials,
   destinations, and provider routes are absent or disabled by default.
2. Missing, false, unknown, expired, stale, or mismatched activation evidence;
   changed predicate preimages; unresolved metrics; mismatched configuration-body
   or resolution digests; superseded/revoked resolutions; reused approval records;
   and incomplete approval-binding maps are rejected before any external or
   background operation.
3. Negative binding fixtures mutate a configuration-body field without
   replacing `config_body_sha256`, bind a configuration approval to a different
   body digest, put a configuration/body field in the component activation
   envelope, and include either envelope in the canonical body preimage; every
   fixture is rejected. Changing only an envelope leaves the body digest stable
   but still fails unless the immutable activation envelope is current and the
   replacement configuration envelope is current, complete, and matches the
   frozen body scope exactly. Component-envelope fixtures independently mutate
   each of the nine projected fields listed above while recomputing envelope-only
   hashes, and independently mutate `activation_record_sha256` with both
   envelope hashes recomputed, `envelope_id` with `content_sha256` recomputed,
   and `content_sha256` alone; every fixture is rejected by the rule whose
   preimage or equality it violates.
4. Negative scope fixtures omit or alter the reviewed spec-file SHA-256, bind
   `S24-G01` to a runtime configuration, place `S24-G01`, `S24-G02A`, or any
   `S24-G06` through `S24-G08` requirement in `approval_bindings`, reuse a
   configuration approval for an alert, or collapse multiple per-source or
   per-destination requirements into one template ID; every fixture is rejected
   without affecting E-04's dormant state.
5. Negative alert-binding fixtures include derived `review_state` in the alert
   body preimage, change alert bytes after a per-alert approval, reuse one
   alert's approval for another alert, or change delivered or thesis-diff bytes
   without new approvals; every fixture is rejected.

After activation:

6. Re-version fixtures approve configuration V1, then freeze a distinct
   configuration ID and body V2 with explicit configuration/envelope
   supersession links. V2 reuses the exact V1 `deferred_activation_envelope` ID
   and digest and supplies a wholly new `approval_bindings` envelope—including
   new `S24-G02B` and every applicable G03-G05 requirement—bound to V2; V2
   passes without another E-04 Status transition. Reusing a V1 configuration
   approval for V2, issuing a second activation record/envelope, or attempting a
   second `Deferred -> Open|In progress` transition is rejected. Revocation or
   staleness blocks the authority it actually governs: activation-envelope
   invalidity blocks every configuration, while one configuration's approval
   invalidity blocks only that configuration.
7. Authorized fixtures normalize covered events with exact source hash/location
   and distinct valid, knowledge, first-seen, and capture timestamps. Fixtures
   exercise all six affected-target types; an empty, unknown, or unresolvable
   affected target is `BLOCKED`.
8. Duplicate, retry, correction, restatement, out-of-order, late, and replayed
   fixtures produce deterministic idempotent and revision-aware results.
9. Unknown entities/types, ambiguous identity, rights denial, clock anomalies,
   budget exhaustion, poison items, and unavailable destinations fail closed
   with visible `PARTIAL` or `BLOCKED` state.
10. No candidate reaches an internal destination without `S24-G06`; no item
   crosses the distribution boundary without all of `S24-G07A` through
   `S24-G07C`; neither action promotes a thesis without `S24-G08`. An
   `IMMATERIAL` fixture cannot carry a thesis diff or reach `S24-G08`, and the
   canonical thesis remains byte-identical.
11. Kill-switch and recovery tests stop new work, preserve immutable evidence,
   resume idempotently, and do not relabel replayed evidence as newly known.
12. Coverage reports reconcile every configured entity/source/event type and do
   not call partial coverage complete. Binding key sets equal the configured
   source/destination sets, requirement and record IDs are one-to-one, and every
   configuration scope matches the frozen `config_body_sha256`; per-alert
   scopes also match the exact `alert_body_sha256` and cannot reuse configuration
   approvals.

Verification evidence records exact commands, exit statuses, hashes, fixture
IDs, validator outputs, timestamps, and reviewer identity. Conversation text
and agent summaries are not proof.

## Dependencies

- Exact register dependency `E-04 -> C-04`, register authority, and valid E-04
  activation.
- Authorized filing ingestion, immutable documents, point-in-time capture, and
  conditional-source controls (S09).
- Source-of-truth, evidence-package, retention, manifest, cutoff, and
  reproducibility contracts (S10–S11).
- Claim/evidence validation, workflow, and human review/promotion contracts
  (S13–S15).
- Entity/security identity, relationships, and corporate actions (S17).
- Product/distribution boundary, source-rights policy, success budgets, and
  operating capacity (S01–S02 and S08).

An unavailable dependency disables only the affected scope and is exposed as
blocked; it cannot be converted into a silent coverage reduction.

## Deferred activation guard

Until E-04 is validly activated, only authoring, reviewing, and structural
verification of this dormant contract and non-executable fixtures are allowed.
No scheduler, webhook, polling, credentials, provider calls, queue, delivery,
or product implementation may be created or enabled. Activation is bounded to
the exact approved sources, entities, event types, cadences, budgets, and
destinations and does not activate E-02, E-03, E-05, or E-10.

## Amendment gate

No evidence-derived provisional amendment gate is assigned to S24 in the
goal's amendment table. Any contract change still requires source
reconciliation, the capped review/fix policy, a fresh clean Sol xhigh review,
and delegated artifact approval. Activation alone does not amend or approve
this spec.
