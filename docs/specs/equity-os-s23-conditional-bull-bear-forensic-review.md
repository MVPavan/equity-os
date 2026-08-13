# S23 — Conditional bull/bear and forensic-review evaluation

Status: DRAFT — AWAITING FRESH SOL XHIGH REVIEW

## Contract posture

This document is the implementation contract for S23. Normative terms MUST,
MUST NOT, SHOULD, and MAY are binding. It specifies dormant evaluation scope
and gates for E-03; it does not activate E-03, approve a debate conclusion, or
authorize implementation.

## Authority and ownership

| Authority | Exact source text | Effect in this contract |
|---|---|---|
| Exact 25-spec table | `S23` | Stable spec identifier. |
| Exact 25-spec table | `Conditional bull/bear and forensic-review evaluation` | Exact title. |
| Exact 25-spec table | `docs/specs/equity-os-s23-conditional-bull-bear-forensic-review.md` | Exact owned path. |
| Exact 25-spec table | `E-03` | Sole primary register owner. |
| Exact 25-spec table | `None directly; v2 controls` | No direct disposition item is assigned; v2 remains controlling. |
| Activation classification | `the dormant-only specs are exactly S03, S04, and S20–S25` | S23 is dormant-only at the pinned draft snapshot. |
| E-03 register priority | `High` | Exact source priority; this draft does not change it. |
| E-03 register decision or action | `Evaluate bull/bear and forensic review` | Exact owned action. |
| E-03 required evidence / acceptance | `Compare with single senior-reviewer baseline; retain only if incremental valid issue detection justifies cost` | Exact comparison and retention rule. |
| E-03 dependencies | `C-04, C-05` | Exact register dependency edges. |
| E-03 source status | `Deferred` | E-03 remains dormant until the governed transition completes. |

The v2 decision register is operational authority for E-03 Status and gates.
This draft cannot change the register or supply an activation decision. A
conflict with the register blocks work and is resolved in favor of the
register.

## Scope

After valid activation, S23 governs controlled evaluation of bull, bear, and
forensic challenge methods against the existing earnings-review workflow. It
covers frozen shared evidence, symmetric role instructions, traceable
challenges and rebuttals, forensic red-flag handling, comparison with a
non-debate baseline, human adjudication, and measured usefulness.

## Non-goals

S23 does not create autonomous investment personas, fetch evidence during a
debate, convert hypotheses into facts, manufacture consensus, issue a rating
or recommendation, accuse a person or company of misconduct, distribute
research, alter source records, or promote conclusions without analyst review.
It does not activate any other Deferred capability.

## Interfaces and data contracts

### `ChallengeEvaluationProtocol`

| Field | Type | Contract |
|---|---|---|
| `protocol_id` | stable identifier | Immutable and unique. |
| `spec_id` / `register_id` | enums | Exactly `S23` / `E-03`. |
| `activation_binding` | content-bound activation envelope | Contains `activation_record_id`, `activation_predicate_id`, `activation_predicate_sha256`, `approval_record_id`, `human_resolution_decision_id`, and `human_resolution_sha256`; every value MUST match the same current E-03 activation record. It is attached after the body digest is computed and is outside that digest's preimage. |
| `senior_reviewer_baseline` | typed object | Exactly one stable senior-reviewer ID and one frozen baseline-method version, plus an exact `case_id -> baseline_run_id` map; every baseline run is that reviewer acting without the challenged method. |
| `case_ids` | nonempty identifier array | Preselected, versioned evaluation cases. |
| `evidence_package_id_by_case` | nonempty identifier map | Key set equals `case_ids` exactly; each case resolves to one frozen package shared byte-identically by its baseline reviewer and all challenge roles. Missing and extra keys fail validation. |
| `role_contract_versions` | object | Exact bull, bear, forensic, rebuttal, and adjudication instruction versions. |
| `retention_rule` | typed object | Fixed before outputs are viewed; defines valid-issue adjudication, minimum positive incremental valid-issue detection, the cost measure, and the maximum approved cost per incremental valid issue. |
| `budgets` / `stop_rules` | objects | Turns, tokens, elapsed time, analyst minutes, safety, and evidence limits. |
| `required_approval_ids` | nonempty typed reference array | Exact one-to-one pre-run requirements from `S23-G02` through `S23-G04`; boundary-conditioned requirements are resolved before protocol freeze. `S23-G01` is a separate spec-artifact gate, while `S23-G05` through `S23-G07` are instantiated after their result or downstream content exists. This pre-run approval envelope is outside the body digest's preimage. |
| `protocol_body_sha256` | lowercase SHA-256 | Pre-activation body digest defined below. |

`protocol_body_sha256` is SHA-256 of canonical JSON of every protocol field
except `activation_binding`, `required_approval_ids`, and
`protocol_body_sha256`. Canonical JSON is UTF-8 with sorted keys, no
insignificant whitespace, direct Unicode, JSON booleans/null, and arrays in
declared order. The body is frozen and hashed before the activation and
operational-approval envelopes are attached. Every operational approval
requirement scope MUST name `protocol_id`, `protocol_body_sha256`, `S23`, and
`E-03`; a requirement bound to another digest cannot pass. The validator
recomputes the body projection exactly, validates each envelope independently,
and rejects a missing field, an extra field in the digest preimage, or any body
mutation not accompanied by a new digest and new scoped envelopes.

`S23-G01-DELEGATED-ARTIFACT` is independent of every runtime protocol. Its
scope MUST name `S23`, this repository-relative path, and the SHA-256 of the
exact spec file bytes reviewed. Its record carries the clean review round,
reviewer identity/session, source hashes, timestamp, and persisted evidence
path. It MUST NOT depend on or name a future `protocol_id`,
`protocol_body_sha256`, activation record, or E-03 runtime approval. Any edit
to the spec bytes requires a new artifact review and record; a later protocol
change neither supplies nor invalidates the artifact approval for unchanged
spec bytes.

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
content-mismatched values leave E-03 dormant.

Each referenced operational approval requirement contains `approval_id`,
`approval_type`, `required_authority`, `scope`, `status`, `actor`, `timestamp`,
`evidence_ref_ids`, and `matched_record_id`. Each record contains
`approval_record_id`, `approval_type`, `authority`, `scope`, `decision`,
`actor`, `timestamp`, `evidence_ref_ids`, `authority_source`, `human_review_id`,
`resolution_decision_id`, and `resolution_content_sha256`. Every operational
record MUST use `HUMAN_RESOLUTION` and copy type, authority, scope, actor,
timestamp, evidence, canonical decision ID, and digest from one active immutable
resolution. That resolution digest is SHA-256 of canonical JSON of the complete
resolution object except `content_sha256`; its `entry_authority_sha256` is the
same digest over the referenced human-review entry excluding `state`,
`resolution_decision_ids`, and `content_sha256`. The separate `S23-G01`
artifact record uses `DELEGATED_AUTOMATED` with null human-resolution fields.
Any absent field or mismatch leaves the requirement `UNRESOLVED`; only
`SATISFIED` passes.

### `ChallengeItem`

Each item contains a stable ID, case and run IDs, role, subject, typed
proposition, epistemic class, scope and horizon, confidence, supporting and
contradicting evidence references, exact source locations or calculation
traces, assumptions, observable falsifier, materiality, and status. Allowed
statuses are `PROPOSED`, `SUPPORTED`, `REBUTTED`, `UNRESOLVED`, `REJECTED`, and
`BLOCKED`. A role label never changes epistemic class or evidence quality.

### `ForensicFlag`

A forensic flag contains `flag_type`, exact observation/fact/claim references,
expected relationship, observed discrepancy, alternative explanations,
materiality, knowledge cutoff, and `review_state`. It MUST be worded as a
testable discrepancy or hypothesis unless supported by approved evidence. It
MUST NOT label misconduct, intent, or fraud without the distinct competent
human and legal process required for such a claim.

### `ChallengeEvaluationResult`

The result has a stable `result_id` and binds the protocol, all role outputs,
deterministic validators, human adjudications, corrections, analyst minutes,
accepted-unchanged rate, incremental material findings, false-positive
categories, missed-baseline findings, `incremental_valid_issue_count`, the cost
numerator and denominator, the mechanically recomputed
cost-per-incremental-valid-issue, `retention_decision` (`RETAIN`,
`DO_NOT_RETAIN`, or `BLOCKED`), and `result_body_sha256`. The digest is SHA-256
of canonical JSON of every result field except `result_body_sha256`. Terminal
`PASS` requires `RETAIN`; `RETAIN` is valid only when incremental valid-issue
detection is positive and every pre-frozen `retention_rule` threshold passes.
Missing or blocked cases remain in the denominator.

## Invariants and fail-closed behavior

1. Sequencing is fail closed: the separately scoped spec-artifact gate controls
   whether this contract may be implemented but is not a runtime protocol
   requirement. At runtime, `protocol_body_sha256` validates before the
   activation and approval envelopes; `S23-G02`, both `S23-G03` requirements,
   and every applicable `S23-G04` requirement are `SATISFIED` before an
   evaluation starts;
   `S23-G05` may be satisfied only from complete results; and promotion or
   distribution requires its own later `S23-G06` or `S23-G07` records.
   `S23-G05` through `S23-G07` are absent from the frozen pre-run inventory and
   are instantiated in separate result/downstream envelopes only after the
   content they bind exists.
2. The comparison baseline has exactly one senior reviewer, the exact case set,
   and the frozen no-challenge method; missing, mixed-reviewer, or alternative
   baselines are `BLOCKED`.
3. Every role receives byte-identical frozen evidence and the same knowledge
   cutoff. No role or adjudicator may browse or retrieve additional evidence
   during the run.
4. Bull and bear outputs are candidate claims, not votes. Repetition,
   confidence, eloquence, or majority does not increase authority.
5. Material outputs resolve to a fact ID, calculation trace, or exact source
   location and preserve epistemic class, scope, horizon, and falsifier.
6. Contradictory evidence and unresolved challenges MUST remain visible to the
   analyst; summarization cannot delete them.
7. Only human-adjudicated valid issues count as incremental detection. The
   challenged method MUST NOT be retained and the result MUST NOT be `PASS`
   unless its positive increment justifies cost under the frozen rule.
8. The adjudicator cannot promote memory, approve its own artifact, or replace
   analyst, legal, regulatory, or distribution authority.
9. Missing evidence, evidence-package divergence, source-hash mismatch,
   unsupported allegation, prompt/version drift, stale activation proof, or
   missing approval yields `BLOCKED` for the affected case.
10. Dormant mode creates no runtime resources, credentials, model calls,
   schedules, provider calls, or implementation dependency.

## Evidence and typed human-approval gates

| Gate ID | Required evidence | Exact `approval_type` | Required authority | Fail-closed result |
|---|---|---|---|---|
| `S23-G01-DELEGATED-ARTIFACT` | Exact current spec-file SHA-256 and fresh clean Sol xhigh review with source hashes, review round, timestamp, and persisted evidence path | `DELEGATED_ARTIFACT_APPROVAL` | Delegated authority under the activated goal | Draft remains unapproved. This document records no approval. |
| `S23-G02-ACTIVATION` | Current TRUE predicate digest, evidence, E-03 activation record, and matching canonical human-resolution digest | `GOAL_OR_PROCESS_AUTHORIZATION` | Competent human authorized for exact E-03 `ACTIVATE_DEFERRED` scope | Capability remains dormant. |
| `S23-G03A-PROTOCOL-ANALYST` | Frozen cases, single-reviewer baseline, role contracts, metrics, denominator, retention rule, budgets, and stops | `ANALYST_ACCEPTANCE` | Competent analyst | Evaluation does not start. |
| `S23-G03B-PROTOCOL-DOMAIN` | Valid-issue definition and case/forensic representativeness | `DOMAIN_EXPERT_ACCEPTANCE` | Competent domain expert | Evaluation does not start. |
| `S23-G04A-FORENSIC-LEGAL` | Exact use crosses the legal/allegation boundary; requirement is included when that boundary predicate is `TRUE` | `LEGAL_REVIEW` | Competent legal authority | Forensic mode remains disabled. |
| `S23-G04B-FORENSIC-REGULATORY` | Exact use crosses a regulatory boundary; requirement is included when that boundary predicate is `TRUE` | `REGULATORY_REVIEW` | Competent regulatory authority | Forensic mode remains disabled. |
| `S23-G05-ADJUDICATION` | Complete role artifacts, evidence links, validator results, valid-issue decisions, and corrections | `ANALYST_ACCEPTANCE` | Competent analyst | Output remains candidate evaluation evidence. |
| `S23-G06-PROMOTION` | Exact approved claims and thesis diff through the separate promotion transaction | `MEMORY_PROMOTION` | Competent memory-promotion authority | Canonical thesis is unchanged. |
| `S23-G07A-DISTRIBUTION` | Exact content/version, approved audience, and purpose | `DISTRIBUTION_APPROVAL` | Competent distribution authority | Output remains private/internal and undistributed. |
| `S23-G07B-DISTRIBUTION-LEGAL` | Legal decision for the exact distributed content and audience | `LEGAL_REVIEW` | Competent legal authority | Output remains private/internal and undistributed. |
| `S23-G07C-DISTRIBUTION-REGULATORY` | Regulatory decision for the exact distributed content and audience | `REGULATORY_REVIEW` | Competent regulatory authority | Output remains private/internal and undistributed. |

`S23-G01` and `S23-G05` through `S23-G07` are not listed in
`required_approval_ids`. G01 cannot satisfy a runtime requirement; G05 through
G07 are separate result/downstream requirements. Each record satisfies at most
one requirement. An applicability predicate for `S23-G04A` or `S23-G04B` that
is `UNKNOWN` disables forensic mode; it is never treated as false. Delegated
artifact approval does not satisfy activation, analyst, domain, legal,
regulatory, distribution, or promotion authority.

Every `S23-G05` scope additionally names the exact `result_id` and
`result_body_sha256` adjudicated. `S23-G06` additionally names that accepted
result, the separate promotion-transaction ID, and the exact promoted-content
digest. Every `S23-G07` requirement additionally names the exact distributed
content digest, audience, and purpose. None of these approvals changes the
immutable result body; changed result, promoted, or distributed bytes require a
new scoped requirement and record.

## Acceptance tests and verification

Before activation:

1. Structural tests prove no debate/forensic executable, model route,
   credential, schedule, or runtime dependency is enabled.
2. False, unknown, expired, stale, or unevaluated predicates; changed predicate
   preimages; unresolved metrics; mismatched protocol-body/resolution digests;
   superseded/revoked resolutions; reused approval records; and delegated
   approval alone are rejected before any run.
3. Negative binding fixtures mutate a protocol-body field without replacing
   `protocol_body_sha256`, bind an activation or operational approval to a
   different body digest, and include either envelope in the canonical body
   preimage; every fixture is rejected. Changing only an envelope leaves the
   body digest stable but still fails unless the replacement envelope is
   current and matches the frozen body scope exactly.
4. Negative artifact-scope fixtures omit or alter the reviewed spec-file
   SHA-256, bind `S23-G01` to a runtime protocol, place `S23-G01` or any
   `S23-G05` through `S23-G07` requirement in `required_approval_ids`, pre-create
   a result/downstream requirement without its content digest, or use a runtime
   approval to satisfy G01; every fixture is rejected without affecting E-03's
   dormant state.

After activation:

5. The case-to-package map has exactly one entry per case, and the single senior
   reviewer and all challenge roles receive each case's byte-identical package
   and cutoff; missing/extra mappings, a second reviewer, an alternative
   baseline, evidence fetches, and package mutation fail closed.
6. Unsupported, unlocated, or epistemically unlabeled material outputs are
   blocked and cannot enter adjudication or promotion.
7. Contradictory fixtures retain both sides and unresolved state; a majority or
   high-confidence unsupported output cannot become `SUPPORTED`.
8. Forensic fixtures distinguish testable discrepancies from allegations and
   route boundary-crossing language to the typed human gate.
9. Baseline-versus-challenge reports account for every case, failure,
   correction, false positive, analyst minute, blocked result, and adjudicated
   incremental valid issue. Zero valid increment or cost above the frozen limit
   forces `DO_NOT_RETAIN` and prevents `PASS`.
10. Replaying frozen deterministic validators yields the same result and binds
   exact role-contract, source, and `protocol_body_sha256` values; requirement
   and approval-record IDs remain one-to-one. Negative fixtures change result
   bytes after `S23-G05`, reuse one adjudication for another result, and change
   promoted or distributed content after `S23-G06` or `S23-G07`; each
   invalidates the affected approval without altering prior immutable evidence.

Verification evidence records the exact command, exit status, hashes,
validator output, execution time, and reviewer identity. Conversation text and
agent summaries are not proof.

## Dependencies

- Exact register dependencies `E-03 -> C-04` and `E-03 -> C-05`, register
  authority, and valid E-03 activation.
- Frozen evidence-package, record-retention, run-manifest, and cutoff contracts
  (S10–S11).
- Claim/vocabulary/evidence-validation and workflow contracts (S13–S14).
- Human correction, supersession, and promotion controls (S15).
- Golden-set, failure-taxonomy, success-metric, budget, and capacity controls
  (S07–S08).
- Deterministic compute traces when a challenge uses computed evidence (S16).

An unavailable dependency blocks only its affected cone. It cannot be hidden
by dropping a case or changing the denominator after results are known.

## Deferred activation guard

Until E-03 is validly activated, permitted work is limited to authoring,
reviewing, and verifying this dormant contract and non-executable fixtures.
Product code, model calls, live evaluations, prompt deployment, provider
access, and runtime configuration are prohibited. Activation is limited to the
approved scope, protocol, and budget and does not activate E-02, E-04, E-05,
or E-10.

## Amendment gate

No evidence-derived provisional amendment gate is assigned to S23 in the
goal's amendment table. Contract changes still require source reconciliation,
the capped review/fix policy, a fresh clean Sol xhigh review, and delegated
artifact approval. Activation is neither amendment nor approval.
