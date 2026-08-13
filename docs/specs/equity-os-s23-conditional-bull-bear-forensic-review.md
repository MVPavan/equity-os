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
| `activation_record_id` | identifier | Resolves to the active E-03 activation record. |
| `baseline_run_ids` | nonempty identifier array | Runs reviewed without the challenged method. |
| `case_ids` | nonempty identifier array | Preselected, versioned evaluation cases. |
| `evidence_package_id` | identifier per case | Frozen once and shared identically by all roles. |
| `role_contract_versions` | object | Exact bull, bear, forensic, rebuttal, and adjudication instruction versions. |
| `success_rules` | nonempty array | Fixed before outputs are viewed. |
| `budgets` / `stop_rules` | objects | Turns, tokens, elapsed time, analyst minutes, safety, and evidence limits. |
| `required_approval_ids` | typed reference array | Resolves without inference. |

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

The result binds the protocol, all role outputs, deterministic validators,
human adjudications, corrections, analyst minutes, accepted-unchanged rate,
incremental material findings, false-positive categories, missed-baseline
findings, and terminal `PASS`, `FAIL`, or `BLOCKED`. Missing or blocked cases
remain in the denominator.

## Invariants and fail-closed behavior

1. E-03 remains dormant unless its typed predicate recomputes `TRUE` and a
   distinct active canonical human resolution authorizes `ACTIVATE_DEFERRED`
   for E-03.
2. Every role receives byte-identical frozen evidence and the same knowledge
   cutoff. No role or adjudicator may browse or retrieve additional evidence
   during the run.
3. Bull and bear outputs are candidate claims, not votes. Repetition,
   confidence, eloquence, or majority does not increase authority.
4. Material outputs resolve to a fact ID, calculation trace, or exact source
   location and preserve epistemic class, scope, horizon, and falsifier.
5. Contradictory evidence and unresolved challenges MUST remain visible to the
   analyst; summarization cannot delete them.
6. The adjudicator cannot promote memory, approve its own artifact, or replace
   analyst, legal, regulatory, or distribution authority.
7. Missing evidence, evidence-package divergence, source-hash mismatch,
   unsupported allegation, prompt/version drift, stale activation proof, or
   missing approval yields `BLOCKED` for the affected case.
8. Dormant mode creates no runtime resources, credentials, model calls,
   schedules, provider calls, or implementation dependency.

## Evidence and typed human-approval gates

| Gate ID | Required evidence | Required authority | Fail-closed result |
|---|---|---|---|
| `S23-G01-DELEGATED-ARTIFACT` | Fresh clean Sol xhigh review with source hashes, review round, timestamp, and persisted evidence path | `DELEGATED_ARTIFACT_APPROVAL` under the activated goal | Draft remains unapproved. This document records no approval. |
| `S23-G02-ACTIVATION` | Current TRUE predicate digest, evidence, E-03 activation record, and matching canonical human-resolution digest | Competent human authorized for exact E-03 `ACTIVATE_DEFERRED` scope | Capability remains dormant. |
| `S23-G03-PROTOCOL` | Frozen cases, baseline, role contracts, metrics, denominator, budgets, and stop rules | Analyst/domain owner | Evaluation does not start. |
| `S23-G04-FORENSIC` | Flag taxonomy, allegation-safe language controls, escalation path, and test fixtures | Analyst/domain owner; legal or regulatory authority where the proposed use crosses that boundary | Forensic mode remains disabled. |
| `S23-G05-ADJUDICATION` | Complete role transcript/artifacts, evidence links, validator results, and correction record | Analyst | Output remains candidate evaluation evidence. |
| `S23-G06-PROMOTION` | Exact approved claims and thesis diff | Analyst through the separate memory-promotion transaction | Canonical thesis is unchanged. |
| `S23-G07-DISTRIBUTION` | Approved audience, purpose, legal/regulatory decision, and content version | Competent distribution/legal/regulatory authority | Output remains private/internal and undistributed. |

Each record satisfies at most one requirement. Delegated artifact approval does
not satisfy activation, analyst, domain, legal, regulatory, distribution, or
promotion authority.

## Acceptance tests and verification

Before activation:

1. Structural tests prove no debate/forensic executable, model route,
   credential, schedule, or runtime dependency is enabled.
2. False, unknown, expired, stale, or unevaluated predicates; missing or
   mismatched resolutions; and delegated approval alone are rejected.

After activation:

3. Identical case fixtures give all roles byte-identical evidence packages and
   cutoffs; an attempted evidence fetch or package mutation fails closed.
4. Unsupported, unlocated, or epistemically unlabeled material outputs are
   blocked and cannot enter adjudication or promotion.
5. Contradictory fixtures retain both sides and unresolved state; a majority or
   high-confidence unsupported output cannot become `SUPPORTED`.
6. Forensic fixtures distinguish testable discrepancies from allegations and
   route boundary-crossing language to the typed human gate.
7. Baseline-versus-challenge reports account for every case, failure,
   correction, false positive, analyst minute, and blocked result.
8. Replaying frozen deterministic validators yields the same result and binds
   exact role-contract and source hashes.

Verification evidence records the exact command, exit status, hashes,
validator output, execution time, and reviewer identity. Conversation text and
agent summaries are not proof.

## Dependencies

- Register authority and valid E-03 activation.
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
