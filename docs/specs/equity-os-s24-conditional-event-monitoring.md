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
| `spec_id` / `register_id` | enums | Exactly `S24` / `E-04`. |
| `activation_binding` | content-bound reference object | Contains `activation_record_id`, `activation_predicate_id`, `activation_predicate_sha256`, `approval_record_id`, `human_resolution_decision_id`, and `human_resolution_sha256`; every value MUST match the same current E-04 activation record. |
| `covered_entity_ids` | nonempty identifier array | Explicit, approved scope; no wildcard universe. |
| `source_ids` | nonempty identifier array | Each resolves to rights and retention evidence. |
| `event_type_versions` | nonempty map | Closed event vocabulary and schema versions. |
| `capture_cadence` | object | Per-source poll/event cadence and expected latency. |
| `ruleset_version` | identifier | Immutable detection and materiality rules. |
| `budgets` | object | Requests, documents, storage, compute, analyst review, and delivery limits. |
| `destinations` | array | Empty by default; each item fixes destination ID, boundary class, audience, purpose, content schema/version, and independent configuration-approval requirements. |
| `kill_switch_owner` | human authority reference | Named competent operator, not an agent. |
| `approval_bindings` | closed typed object | Exact content-bound references defined below for every source, credential, operations gate, ruleset, destination, and distribution boundary in this configuration. Per-alert delivery and promotion requirements bind later to the alert digest. |
| `config_sha256` | lowercase SHA-256 | Digest defined below; it content-binds the complete configuration. |

`config_sha256` is SHA-256 of canonical JSON of every configuration field
except `config_sha256`. Canonical JSON is UTF-8 with sorted keys, no
insignificant whitespace, direct Unicode, JSON booleans/null, and arrays in
declared order. Every approval requirement scope MUST name `config_id`,
`config_sha256`, `S24`, and `E-04`; a requirement bound to another digest
cannot pass.

`approval_bindings` contains: an exact source-ID map to separate
`DATA_RIGHTS_APPROVAL` and, when applicable, `PROVIDER_AUTHORIZATION`,
`LEGAL_REVIEW`, and `CREDENTIAL_ACCESS_APPROVAL` requirement IDs; operations
IDs for `BUDGET_APPROVAL`, `CAPACITY_COMMITMENT`, and
`NAMED_OWNER_COMMITMENT`; ruleset IDs for `ANALYST_ACCEPTANCE` and
`DOMAIN_EXPERT_ACCEPTANCE`; and an exact destination-ID map to separate
internal `ANALYST_ACCEPTANCE` and, for every distribution boundary,
`DISTRIBUTION_APPROVAL`, `LEGAL_REVIEW`, and `REGULATORY_REVIEW` requirement
IDs. Map key sets MUST equal the configured source and destination sets.
Applicability is derived from current typed policy evidence before the
configuration is frozen; `UNKNOWN`, a missing key, or a reference bound to a
different configuration blocks the affected source or destination. These
configuration approvals authorize only the configured route. They never
satisfy the later per-alert delivery or promotion requirements.

The validator dereferences `activation_binding` rather than trusting copied
values. It recomputes the governed activation predicate using three-valued
logic and hashes canonical JSON with exactly these keys and values:
`predicate_id`, `expression`, `metrics`, deterministically
`resolved_values`, `digest_sources`, `result`, and `evaluated_at`. The binding
passes only when that digest is current, the result is `TRUE`, all metrics are
resolved and unexpired, and the activation record, approved
`GOAL_OR_PROCESS_AUTHORIZATION` record, and active `ACTIVATE_DEFERRED` canonical human
resolution carry the same predicate ID/digest, exact scope, decision ID, and
resolution digest. Missing, copied, stale, superseded, revoked, or
content-mismatched values leave E-04 dormant.

Each referenced approval requirement contains `approval_id`,
`approval_type`, `required_authority`, `scope`, `status`, `actor`, `timestamp`,
`evidence_ref_ids`, and `matched_record_id`. Each record contains
`approval_record_id`, `approval_type`, `authority`, `scope`, `decision`,
`actor`, `timestamp`, `evidence_ref_ids`, `authority_source`, `human_review_id`,
`resolution_decision_id`, and `resolution_content_sha256`. A non-delegated
record MUST use `HUMAN_RESOLUTION` and copy type, authority, scope, actor,
timestamp, evidence, canonical decision ID, and digest from one active immutable
resolution. That resolution digest is SHA-256 of canonical JSON of the complete
resolution object except `content_sha256`; its `entry_authority_sha256` is the
same digest over the referenced human-review entry excluding `state`,
`resolution_decision_ids`, and `content_sha256`. Only
`DELEGATED_ARTIFACT_APPROVAL` may use `DELEGATED_AUTOMATED`, with null human
resolution fields. Any absent field or mismatch leaves the requirement
`UNRESOLVED`; only `SATISFIED` passes.

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
class, nullable `proposed_thesis_diff_id`, review state, and suppression or
supersession links, plus `alert_sha256`. Every affected target contains exactly one `target_type`
from `FACT`, `ASSUMPTION`, `CATALYST`, `PROMISE`, `FALSIFIER`, and
`THESIS_BREAKER`, its stable target ID, and the evidence-backed changed value or
state. Allowed review states are `PENDING`, `APPROVED_INTERNAL`, `REJECTED`,
`SUPERSEDED`, and `BLOCKED`. Detection does not equal approval.

`alert_sha256` is SHA-256 of canonical JSON of every alert field except itself.
Every per-alert `S24-G06`, `S24-G07`, or `S24-G08` requirement scope binds the
exact alert ID and digest plus `config_id` and `config_sha256`. Those
requirements are created only after the candidate exists and cannot be copied
from a configuration-level destination approval.

### `MonitoringRunManifest`

The manifest binds configuration, source snapshots, cutoff, code/ruleset
versions, requests, retries, deduplication decisions, emitted and suppressed
candidates, failures, approvals, and terminal `COMPLETE`, `PARTIAL`, or
`BLOCKED`. `PARTIAL` is visible and cannot satisfy a completeness claim.

## Invariants and fail-closed behavior

1. Sequencing is fail closed: the activation binding and `config_sha256`
   validate first; `S24-G01`, `S24-G02`, every applicable `S24-G03`, all
   `S24-G04`, both `S24-G05`, and each configured-destination approval binding
   are `SATISFIED` before the corresponding scheduler, source, rule, credential,
   or route is enabled. A candidate then requires its own content-bound
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
| `S24-G01-DELEGATED-ARTIFACT` | Fresh clean Sol xhigh review, source hashes, review round, timestamp, and persisted evidence path | `DELEGATED_ARTIFACT_APPROVAL` | Delegated authority under the activated goal | Draft remains unapproved. No approval is recorded here. |
| `S24-G02-ACTIVATION` | Current TRUE predicate digest, evidence, E-04 activation record, and matching canonical human-resolution digest | `GOAL_OR_PROCESS_AUTHORIZATION` | Competent human authorized for exact E-04 `ACTIVATE_DEFERRED` scope | Monitoring remains dormant. |
| `S24-G03A-DATA-RIGHTS` | Per-source permitted use and retention | `DATA_RIGHTS_APPROVAL` | Competent data-rights authority | Source is disabled. |
| `S24-G03B-PROVIDER` | Provider authorization is required for the exact source/use; included when the policy predicate is `TRUE` | `PROVIDER_AUTHORIZATION` | Competent provider authority | Source is disabled. |
| `S24-G03C-LEGAL` | Legal adjudication is required for the exact source/use; included when the policy predicate is `TRUE` | `LEGAL_REVIEW` | Competent legal authority | Source is disabled. |
| `S24-G03D-CREDENTIAL` | Exact credential, source, purpose, storage path, and permitted operations; included for every credentialed source | `CREDENTIAL_ACCESS_APPROVAL` | Competent credential owner | Credentialed source is disabled. |
| `S24-G04A-BUDGET` | Request, storage, compute, analyst-review, and delivery limits | `BUDGET_APPROVAL` | Competent budget authority | Background execution remains disabled. |
| `S24-G04B-CAPACITY` | Capacity, SLO wording, recovery, and replay commitments | `CAPACITY_COMMITMENT` | Competent capacity owner | Background execution remains disabled. |
| `S24-G04C-OWNER` | Escalation path and named kill-switch/recovery owner | `NAMED_OWNER_COMMITMENT` | Competent named operator | Background execution remains disabled. |
| `S24-G05A-RULESET-ANALYST` | Event vocabulary, materiality fixtures, false-positive results, and covered entities | `ANALYST_ACCEPTANCE` | Competent analyst | Detection/routing remains disabled. |
| `S24-G05B-RULESET-DOMAIN` | Domain validity of event types, changed-target mappings, and materiality rules | `DOMAIN_EXPERT_ACCEPTANCE` | Competent domain expert | Detection/routing remains disabled. |
| `S24-G06-INTERNAL-ALERT` | Exact alert, evidence, recipient/purpose, and freshness | `ANALYST_ACCEPTANCE` | Competent analyst | Candidate is not delivered. |
| `S24-G07A-DISTRIBUTION` | Exact content/version, audience, and purpose | `DISTRIBUTION_APPROVAL` | Competent distribution authority | External or personalized delivery is prohibited. |
| `S24-G07B-DISTRIBUTION-LEGAL` | Legal decision for exact content/version and audience | `LEGAL_REVIEW` | Competent legal authority | External or personalized delivery is prohibited. |
| `S24-G07C-DISTRIBUTION-REGULATORY` | Regulatory decision for exact content/version and audience | `REGULATORY_REVIEW` | Competent regulatory authority | External or personalized delivery is prohibited. |
| `S24-G08-PROMOTION` | Approved thesis diff and reviewed supporting claims | `MEMORY_PROMOTION` | Competent memory-promotion authority | Canonical thesis is unchanged. |

One approval record satisfies one requirement only. Every applicable gate ID
above appears exactly once in `approval_bindings`; an applicability predicate
that is `UNKNOWN` blocks the source or destination. Delegated artifact approval
does not satisfy activation, rights, legal, provider, credential, operations,
capacity, analyst, domain, regulatory, distribution, production, or promotion
gates.

## Acceptance tests and verification

Before activation:

1. Structural tests prove all schedules, webhooks, consumers, credentials,
   destinations, and provider routes are absent or disabled by default.
2. Missing, false, unknown, expired, stale, or mismatched activation evidence;
   changed predicate preimages; unresolved metrics; mismatched configuration or
   resolution digests; superseded/revoked resolutions; reused approval records;
   and incomplete approval-binding maps are rejected before any external or
   background operation.

After activation:

3. Authorized fixtures normalize covered events with exact source hash/location
   and distinct valid, knowledge, first-seen, and capture timestamps. Fixtures
   exercise all six affected-target types; an empty, unknown, or unresolvable
   affected target is `BLOCKED`.
4. Duplicate, retry, correction, restatement, out-of-order, late, and replayed
   fixtures produce deterministic idempotent and revision-aware results.
5. Unknown entities/types, ambiguous identity, rights denial, clock anomalies,
   budget exhaustion, poison items, and unavailable destinations fail closed
   with visible `PARTIAL` or `BLOCKED` state.
6. No candidate reaches an internal destination without `S24-G06`; no item
   crosses the distribution boundary without all of `S24-G07A` through
   `S24-G07C`; neither action promotes a thesis without `S24-G08`. An
   `IMMATERIAL` fixture cannot carry a thesis diff or reach `S24-G08`, and the
   canonical thesis remains byte-identical.
7. Kill-switch and recovery tests stop new work, preserve immutable evidence,
   resume idempotently, and do not relabel replayed evidence as newly known.
8. Coverage reports reconcile every configured entity/source/event type and do
   not call partial coverage complete. Binding key sets equal the configured
   source/destination sets, requirement and record IDs are one-to-one, and every
   configuration scope matches the frozen `config_sha256`; per-alert scopes also
   match the exact `alert_sha256` and cannot reuse configuration approvals.

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
