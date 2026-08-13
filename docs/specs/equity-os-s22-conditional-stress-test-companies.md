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
| `spec_id` | enum | Exactly `S22`. |
| `register_id` | enum | Exactly `E-02`. |
| `activation_record_id` | identifier | Resolves to the active E-02 activation record. |
| `baseline_run_ids` | nonempty identifier array | Approved discovery-company runs used as the comparison baseline. |
| `stress_dimensions` | nonempty enum array | Chosen from sector, size, reporting complexity, segment complexity, document variation, and source coverage. |
| `candidate_companies` | nonempty object array | Each item contains stable entity ID, selection rationale, covered dimensions, source-rights result, and reviewer decision ID. |
| `frozen_contract_versions` | nonempty map | Exact versions of every upstream interface under test. |
| `budgets` | object | Maximum companies, documents, analyst minutes, compute, and elapsed time. |
| `success_rules` | nonempty array | Mechanically evaluable thresholds fixed before execution. |
| `stop_rules` | nonempty array | Safety, rights, evidence, quality, and budget termination conditions. |
| `approved_by` | typed approval references | No approval may be inferred from an actor name. |

### `StressTestCompanyResult`

Each result contains `protocol_id`, `entity_id`, `run_ids`, frozen evidence
package IDs, source hashes, knowledge cutoff, interface versions, validator
results, analyst-review minutes, corrections, unresolved failures, and a
terminal state of `PASS`, `FAIL`, or `BLOCKED`. `BLOCKED` is not counted as a
pass and missing companies remain in the denominator.

### `ContractDeltaDecision`

Every observed difference is recorded as `RETAIN`, `ADD`, `CHANGE`, `DEFER`,
or `REJECT`, with the affected contract, exact evidence, compatibility impact,
owner, and required approval types. A delta is only a proposal until the owned
upstream spec is amended, freshly reviewed, and approved. S22 MUST NOT mutate
another spec or schema by implication.

## Invariants and fail-closed behavior

1. E-02 remains dormant unless its typed activation predicate recomputes
   `TRUE` and a distinct active canonical human resolution authorizes
   `ACTIVATE_DEFERRED` for E-02.
2. A copied ledger label, coordinator statement, this draft, or delegated
   artifact approval cannot activate E-02.
3. The protocol and success rules are frozen before the first candidate run.
4. Every run uses one frozen evidence package and one explicit knowledge
   cutoff; downstream steps MUST NOT fetch new evidence invisibly.
5. Company results remain isolated. Data, claims, and corrections MUST carry
   stable entity identity and MUST NOT leak between companies.
6. Material claims resolve to a fact ID, calculation trace, or exact source
   location and retain epistemic class.
7. A rights failure, missing source hash, unresolved identity, stale activation
   proof, budget breach, validator failure, or missing approval produces
   `BLOCKED` and stops the affected run.
8. No stress result is promoted to the canonical thesis without the separate
   analyst-controlled review and memory-promotion transaction.
9. Dormant mode creates no runtime resources, schedules, credentials, provider
   calls, purchases, or product-code dependency.

## Evidence and typed human-approval gates

| Gate ID | Required evidence | Required authority | Fail-closed result |
|---|---|---|---|
| `S22-G01-DELEGATED-ARTIFACT` | Clean fresh-context Sol xhigh review, source hashes, review round, timestamp, and persisted evidence path | `DELEGATED_ARTIFACT_APPROVAL` under the activated goal | Draft remains unapproved. This document records no such approval. |
| `S22-G02-ACTIVATION` | Current TRUE predicate digest, component-local evidence, E-02 activation record, and matching canonical human-resolution digest | Competent human with authority to `ACTIVATE_DEFERRED` for the exact E-02 scope | E-02 remains dormant. |
| `S22-G03-SELECTION` | Candidate matrix, source coverage, conflicts, selection rationale, and fixed denominator | Analyst/domain owner | No candidate run starts. |
| `S22-G04-RIGHTS` | Source-by-source permitted-use and retention determination | Rights/legal or provider authority where required | Affected source and company are blocked. |
| `S22-G05-BUDGET` | Bounded company/document/compute/review budget | Human budget or capacity owner | No resource-consuming run starts. |
| `S22-G06-PROMOTION` | Reviewed result, correction record, and explicit promotion decision | Analyst | Result remains evaluation evidence only. |

One approval record satisfies one declared requirement only. Delegated artifact
approval never satisfies activation, analyst, domain, legal, rights, budget,
capacity, regulatory, production, distribution, or promotion authority.

## Acceptance tests and verification

Before activation:

1. A structural test proves no S22 executable entry point, schedule, provider
   call, credential, or runtime dependency is enabled.
2. Attempts using no activation record, a false/unknown/stale predicate, a
   mismatched resolution digest, or delegated artifact approval alone are
   rejected.

After activation:

3. Fixture companies covering every declared stress dimension run against the
   same frozen contract versions and produce isolated content-addressed results.
4. Missing evidence, source-rights denial, identity ambiguity, schema mismatch,
   budget exhaustion, and validator failure each deterministically produce
   `BLOCKED` without partial promotion.
5. Replaying identical inputs produces identical deterministic outputs or a
   documented nondeterministic boundary; no later-known evidence enters a run.
6. Every discovered delta has exactly one `ContractDeltaDecision`, and no
   `ADD` or `CHANGE` becomes operative without an amendment to its owning spec.
7. The final report preserves all failures and blocked cases in its denominator
   and reconciles every run, approval, and evidence reference.

Verification evidence MUST record the exact command, exit status, artifact
hashes, validator output, execution time, and reviewer identity. Conversation
text and agent summaries are not proof.

## Dependencies

- Register authority and valid E-02 activation are hard prerequisites for any
  active implementation.
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
