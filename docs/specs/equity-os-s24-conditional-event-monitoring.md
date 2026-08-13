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
| `activation_record_id` | identifier | Resolves to the active E-04 activation record. |
| `covered_entity_ids` | nonempty identifier array | Explicit, approved scope; no wildcard universe. |
| `source_ids` | nonempty identifier array | Each resolves to rights and retention evidence. |
| `event_type_versions` | nonempty map | Closed event vocabulary and schema versions. |
| `capture_cadence` | object | Per-source poll/event cadence and expected latency. |
| `ruleset_version` | identifier | Immutable detection and materiality rules. |
| `budgets` | object | Requests, documents, storage, compute, analyst review, and delivery limits. |
| `destinations` | array | Empty by default; every nonempty destination requires an independent approval. |
| `kill_switch_owner` | human authority reference | Named competent operator, not an agent. |

### `CapturedEvent`

Each event contains stable event and entity/security IDs, event type/version,
source document ID and hash, exact source location, raw and normalized payload,
valid time, knowledge time, first-seen time, capture time, supersession link,
deduplication key, rights-policy version, and ingestion-run ID. Corrections
append and supersede; they never overwrite the prior occurrence.

### `AlertCandidate`

An alert contains the event ID, materiality rule and version, matched evidence,
epistemic class, confidence, affected thesis/claim IDs if any, observable
falsifier, knowledge cutoff, routing class, review state, and suppression or
supersession links. Allowed review states are `PENDING`, `APPROVED_INTERNAL`,
`REJECTED`, `SUPERSEDED`, and `BLOCKED`. Detection does not equal approval.

### `MonitoringRunManifest`

The manifest binds configuration, source snapshots, cutoff, code/ruleset
versions, requests, retries, deduplication decisions, emitted and suppressed
candidates, failures, approvals, and terminal `COMPLETE`, `PARTIAL`, or
`BLOCKED`. `PARTIAL` is visible and cannot satisfy a completeness claim.

## Invariants and fail-closed behavior

1. E-04 remains dormant unless its typed predicate recomputes `TRUE` and a
   distinct active canonical human resolution authorizes `ACTIVATE_DEFERRED`
   for the exact E-04 scope.
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
7. A candidate alert is not a fact, approved thesis change, recommendation, or
   delivery authorization.
8. Rights uncertainty, identity ambiguity, missing source hash/location,
   unsupported event type, stale activation, expired approval, budget breach,
   queue poison item, or material clock anomaly fails closed and is surfaced.
9. Failure of one source or entity does not silently mark the run complete and
   does not erase independent successfully captured evidence.

## Evidence and typed human-approval gates

| Gate ID | Required evidence | Required authority | Fail-closed result |
|---|---|---|---|
| `S24-G01-DELEGATED-ARTIFACT` | Fresh clean Sol xhigh review, source hashes, review round, timestamp, and persisted evidence path | `DELEGATED_ARTIFACT_APPROVAL` under the activated goal | Draft remains unapproved. No approval is recorded here. |
| `S24-G02-ACTIVATION` | Current TRUE predicate digest, evidence, E-04 activation record, and matching canonical human-resolution digest | Competent human authorized for exact E-04 `ACTIVATE_DEFERRED` scope | Monitoring remains dormant. |
| `S24-G03-SOURCES` | Per-source rights, permitted use, retention, cadence, and credential-owner decisions | Rights/legal/provider authority and credential owner as applicable | Source is disabled. |
| `S24-G04-OPERATIONS` | Capacity budget, SLO wording, escalation path, kill switch, recovery and replay evidence | Human operations/capacity owner | Background execution remains disabled. |
| `S24-G05-RULESET` | Event vocabulary, materiality fixtures, false-positive results, and covered-entity list | Analyst/domain owner | Detection/routing remains disabled. |
| `S24-G06-INTERNAL-ALERT` | Exact alert, evidence, recipient/purpose, and freshness | Analyst | Candidate is not delivered. |
| `S24-G07-DISTRIBUTION` | Exact content/version, audience, purpose, and legal/regulatory decision | Competent legal/regulatory/distribution authority | External or personalized delivery is prohibited. |
| `S24-G08-PROMOTION` | Approved thesis diff and reviewed supporting claims | Analyst through separate memory promotion | Canonical thesis is unchanged. |

One approval record satisfies one requirement only. Delegated artifact approval
does not satisfy activation, rights, legal, provider, credential, operations,
capacity, analyst, regulatory, distribution, production, or promotion gates.

## Acceptance tests and verification

Before activation:

1. Structural tests prove all schedules, webhooks, consumers, credentials,
   destinations, and provider routes are absent or disabled by default.
2. Missing, false, unknown, expired, stale, or mismatched activation evidence
   is rejected before any external or background operation.

After activation:

3. Authorized fixtures normalize covered events with exact source hash/location
   and distinct valid, knowledge, first-seen, and capture timestamps.
4. Duplicate, retry, correction, restatement, out-of-order, late, and replayed
   fixtures produce deterministic idempotent and revision-aware results.
5. Unknown entities/types, ambiguous identity, rights denial, clock anomalies,
   budget exhaustion, poison items, and unavailable destinations fail closed
   with visible `PARTIAL` or `BLOCKED` state.
6. No candidate reaches an internal destination without `S24-G06`; no item
   crosses the distribution boundary without `S24-G07`; neither action promotes
   a thesis without `S24-G08`.
7. Kill-switch and recovery tests stop new work, preserve immutable evidence,
   resume idempotently, and do not relabel replayed evidence as newly known.
8. Coverage reports reconcile every configured entity/source/event type and do
   not call partial coverage complete.

Verification evidence records exact commands, exit statuses, hashes, fixture
IDs, validator outputs, timestamps, and reviewer identity. Conversation text
and agent summaries are not proof.

## Dependencies

- Register authority and valid E-04 activation.
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
