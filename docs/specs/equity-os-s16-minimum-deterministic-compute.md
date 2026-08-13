# S16 — Minimum deterministic compute

Status: DRAFT — AWAITING FRESH SOL XHIGH REVIEW

## 1. Contract identity and authority

This specification is the sole primary specification for S16. It is an implementation contract for the minimum deterministic-compute capability; it is not evidence that B-07 or C-08 has been accepted.

| Program field | Exact value |
|---|---|
| Spec ID | S16 |
| Exact title | Minimum deterministic compute |
| Exact path | docs/specs/equity-os-s16-minimum-deterministic-compute.md |
| Primary register IDs | B-07, C-08 |
| Disposition references | G-1, 6.9 |
| Activation classification | Active-only |
| Initial program disposition | REQUIRED_NOW |
| Amendment ownership | None |

Authority is applied in this order:

1. The live wording and Status cells in docs/blueprint/funda-blueprint-implementation-decision-register-v2.md control implementation gates.
2. The Exact 25-spec program assigns B-07 and C-08 only to S16.
3. The disposition report supplies the accepted qualifications at G-1 and 6.9; it does not override the register.
4. This draft makes those controls implementable. A conflict fails closed and requires authority reconciliation before work continues.

### Exact register ownership

The following cells reproduce the controlling register text exactly.

| Register ID | Blueprint phase | Priority | Decision or action | Required evidence / acceptance | Dependencies | Activation source status | Primary owner |
|---|---|---:|---|---|---|---|---|
| B-07 | Phase 0.5 | High | Define minimum deterministic compute | Approved MVP list with input, trace, code-version, missing-input, and reproducibility contracts | A-04 | Open | S16 — Minimum deterministic compute |
| C-08 | Phase 1 | High | Implement minimum deterministic calculations | Growth, margins, cash conversion, leverage, dilution/share count, guidance comparison, and reconciliation traces pass tests and fail closed | B-07 | Open | S16 — Minimum deterministic compute |

### Disposition obligations

G-1 requires three separate guarantees:

1. Deterministic calculations replay under frozen inputs, code, runtime, and operator policy. Exact-class accounting operators match exactly; floating-point or optimization operators remain within declared tolerances; stochastic operators require a stored seed and distribution checks.
2. An evidence package is exactly reconstructable from registered source, fact, claim, and cutoff identifiers.
3. Approved narrative bytes are immutable and content-addressed; narrative regeneration is not required to be text-identical.

Disposition 6.9 qualifies bit-exact computation: exact replay applies only to operators designed for it. Floating-point, optimization, and stochastic calculations require declared tolerances, pinned environments, and stored seeds as applicable.

## 2. Scope

S16 specifies:

- the minimum approved operator registry required by B-07;
- typed calculation requests and immutable calculation traces;
- deterministic handling of units, currency, period, statement scope, definitions, missing inputs, rounding, and tolerances;
- the Phase 1 operators required by C-08: growth, margins, cash conversion, leverage, dilution/share count, guidance comparison, and reconciliation;
- replay classification and evidence binding;
- fail-closed behavior and verification fixtures.

### Non-goals

S16 does not:

- define model-grade DCF, SOTP, WACC, optimization, or sector-pack calculations;
- permit an LLM to be an authoritative calculator;
- define final observation, fact, or claim schemas owned by S12 and S13;
- define the run manifest or evidence-package storage owned by S11 and S10;
- approve financial definitions, tolerances, or operator activation;
- make narrative generation deterministic;
- activate any Deferred capability.

## 3. Required interfaces and data contracts

All persisted records are append-only or revisioned. IDs are opaque and stable. Decimal financial values are persisted as decimal strings plus an explicit scale; binary floating-point values may not silently enter an exact-class operator.

### 3.1 OperatorDefinition

Each executable operator version contains:

| Field | Contract |
|---|---|
| operator_id | Stable semantic identifier; a changed formula or meaning requires a new version |
| operator_version | Immutable version |
| display_name | Human-readable name |
| family | GROWTH, MARGIN, CASH_CONVERSION, LEVERAGE, DILUTION_SHARE_COUNT, GUIDANCE_COMPARISON, or RECONCILIATION |
| formula | Machine-readable operation tree plus a human-readable rendering |
| input_roles | Ordered required/optional roles, accepted fact definitions, units, dimensions, scope, and period relation |
| output_contract | Output type, unit/dimension, currency behavior, scale, and sign convention |
| replay_class | EXACT, TOLERANCE, or STOCHASTIC |
| tolerance_policy | Null for EXACT; absolute/relative tolerances and comparison method for TOLERANCE |
| seed_policy | Null unless STOCHASTIC |
| rounding_policy | Mode, precision, and whether rounding occurs only at display or within the operator |
| missing_input_policy | Always FAIL_CLOSED for this MVP |
| zero_denominator_policy | Always FAIL_CLOSED unless the operator version explicitly returns a typed NOT_MEANINGFUL result |
| applicability_rules | Required accounting basis, consolidation scope, period type, and exclusions |
| approval_state | DRAFT or APPROVED with a resolvable approval record |
| code_artifact | Repository-relative implementation identity and content hash |

Only APPROVED definitions may execute in an approvable run. This specification proposes the minimum families but does not mark any definition approved.

### 3.2 CalculationInput

Each input contains input_id, input_role, fact_id, observation lineage, raw decimal value, normalized decimal value, unit, currency, scale, period start/end, instant-or-duration classification, statement and consolidation scope, dimensions, definition/version, valid time, knowledge time, source location, and evidence reference.

An input without a resolvable fact/evidence identity is invalid. A request may not substitute a prose value, an LLM-produced number, or a later-than-cutoff fact.

### 3.3 CalculationRequest

A request contains calculation_id, run_id, evidence_package_id/version, knowledge_cutoff, operator_id/version, ordered inputs, explicit assumptions, requested output role, and caller identity. The request digest binds all fields and referenced evidence digests.

### 3.4 CalculationTrace

A completed attempt contains:

- calculation_id and immutable attempt_id;
- request digest and evidence-package identity;
- operator definition and code-artifact hashes;
- replay class, runtime identity, dependency lock identity, locale, timezone, and decimal context;
- resolved inputs and assumptions;
- normalized operation tree and intermediate steps;
- output value/unit or a typed failure;
- tolerance, seed, and rounding records as applicable;
- warnings that do not change pass/fail;
- created-at time and trace digest.

Allowed outcomes are SUCCEEDED, BLOCKED_MISSING_INPUT, BLOCKED_INVALID_INPUT, BLOCKED_AMBIGUOUS_DEFINITION, BLOCKED_SCOPE_MISMATCH, BLOCKED_UNIT_MISMATCH, BLOCKED_ZERO_DENOMINATOR, and REPLAY_MISMATCH. A blocked outcome has no authoritative numeric output.

## 4. Minimum operator contract

The approved B-07 list must include at least one explicitly named, versioned operator in every family below. Generic labels without defined numerator, denominator, sign, scope, period, and unit semantics are invalid.

| Family | Minimum semantic contract |
|---|---|
| Growth | Compare current and prior values using a registered formula. A relative-growth operator declares its denominator and behavior for zero or sign-changing comparisons; it may not silently choose absolute prior value or a percentage-point presentation. |
| Margin | Divide a registered numerator by a registered denominator from compatible period, scope, currency, and dimensions; preserve both source facts in the trace. |
| Cash conversion | Name the exact cash-flow numerator and earnings/profit denominator. “Cash conversion” alone is not an executable definition. |
| Leverage | Name debt composition, cash/netting policy, and denominator. Gross debt, net debt, EBITDA, equity, and capital variants are separate operator definitions. |
| Dilution/share count | Reconcile opening shares, typed issuance/conversion/buyback/corporate-action movements, closing shares, and any weighted-average measure without treating them as interchangeable. An unexplained residual fails. |
| Guidance comparison | Bind actual and guidance to the same metric definition, unit, currency, scope, period, and guidance version; classify below, within, or above only after range normalization. |
| Reconciliation | Express opening value plus typed movements equals closing value; retain every movement and residual. A residual outside the declared exact/tolerance rule fails. |

MVP implementations should use EXACT where decimal arithmetic and operator semantics support exact replay. TOLERANCE is permitted only with an approved, operator-specific tolerance. STOCHASTIC is outside the minimum list unless this specification is amended and separately approved; a seed alone does not make a stochastic result exact.

## 5. Invariants and fail-closed behavior

1. The LLM may select or explain an operator but never supplies the authoritative result.
2. Every successful output resolves to an approved operator version, immutable code hash, complete input facts, and an immutable trace.
3. Inputs must match the run cutoff, evidence package, definition, unit, currency, scope, dimensions, and period rules.
4. Missing, ambiguous, stale, post-cutoff, dimensionally incompatible, or conflicting inputs block calculation.
5. No implicit unit conversion, currency conversion, annualization, sign flip, denominator choice, scope coercion, or restatement selection is allowed.
6. Every conversion is a separate registered operator or a trace-visible approved preprocessing step.
7. Exact-class replay must be byte-equivalent in normalized inputs, operation tree, intermediates, and output.
8. Tolerance-class replay passes only under the stored comparison method and approved absolute/relative bounds.
9. A replay mismatch invalidates dependent computed claims and blocks approval until re-computation and re-review.
10. Display rounding never mutates the stored authoritative value.
11. The approved narrative hash is outside the calculation result; narrative regeneration cannot establish calculation replay.
12. Unknown operator versions, absent code hashes, missing traces, or unapproved definitions fail closed.

## 6. Evidence and typed approval gates

All entries begin unresolved. Conversation text and this draft are not approval evidence.

| Gate | Type | Required authority | Required evidence | Blocks |
|---|---|---|---|---|
| S16-G01 | DELEGATED_ARTIFACT_APPROVAL | Fresh gpt-5.6-sol xhigh reviewer under delegated goal authority | Persisted clean review, exact source hashes, review round, reviewer/session identity, timestamp, and artifact hash | Spec approval and planning |
| S16-G02 | PRODUCT_OWNER_DECISION | Human product owner | Approved minimum family/operator inventory and explicit exclusions | B-07 acceptance |
| S16-G03 | DOMAIN_EXPERT_ACCEPTANCE | Competent human financial/accounting domain expert | Approval of formulas, definitions, sign conventions, scope rules, rounding, tolerances, and missing-input behavior for every executable operator version | Operator APPROVED state and C-08 implementation |
| S16-G04 | ANALYST_ACCEPTANCE | Human analyst responsible for the workflow | Fixture review showing outputs and trace explanations are usable for earnings review | C-08 acceptance |

Required evidence inventory:

- versioned operator-registry artifact and content hash;
- code and dependency-lock hashes for every implemented operator;
- exact, tolerance, missing-input, zero-denominator, unit/scope mismatch, and replay-mismatch fixtures;
- source-linked calculation traces for all minimum families;
- current typed approval records for S16-G02 through S16-G04;
- fresh delegated review evidence for S16-G01;
- verification command output bound to the tested artifact hashes.

## 7. Acceptance tests and verification

| Test ID | Required proof |
|---|---|
| S16-T01 | Registry validation rejects a definition missing formula, input roles, replay class, code hash, or approval state. |
| S16-T02 | Every minimum family has at least one approved version before B-07 can be accepted. |
| S16-T03 | Exact-class fixture replays with identical normalized inputs, steps, and output. |
| S16-T04 | Tolerance-class fixture passes at the boundary and fails immediately outside it. |
| S16-T05 | Missing, post-cutoff, ambiguous, wrong-period, wrong-unit, wrong-currency, and wrong-scope inputs each yield a typed blocked outcome and no numeric output. |
| S16-T06 | Growth handles zero and sign-changing comparison values only according to its declared policy. |
| S16-T07 | Margin, cash-conversion, and leverage requests cannot substitute an unregistered numerator or denominator. |
| S16-T08 | Dilution/share-count and reconciliation fixtures preserve every movement and fail on an unexplained residual. |
| S16-T09 | Guidance comparison rejects mismatched versions, periods, units, or scopes. |
| S16-T10 | Changing an input, operator definition, code artifact, runtime, rounding rule, or tolerance invalidates the prior trace digest and dependent verification. |
| S16-T11 | Narrative byte differences do not alter a valid calculation trace, while a changed approved narrative produces a different narrative artifact hash. |
| S16-T12 | A generated computed claim resolves to the successful calculation trace; a blocked calculation cannot support a material computed claim. |

Verification is successful only when all tests pass against the current registry/code hashes and all required evidence and approvals are current. Test output alone cannot satisfy human gates.

## 8. Dependencies, activation, and amendment guards

- B-07 is blocked on A-04. Because A-04 has a provisional-to-final amendment gate owned by S06, B-07 and dependent C-08 work remain blocked while the mandatory post-baseline A-04 amendment is due or A-04 is not validly accepted.
- C-08 is blocked on accepted B-07 definitions.
- S10/S11 supply evidence-package and run/reproducibility identities; S12 supplies fact identity; S13 supplies computed-claim validation. S16 consumes those interfaces without taking their ownership.
- Deferred activation guard: not applicable to owned rows. B-07 and C-08 were Open at activation, so S16 is active-only and may not be marked dormant or require an ACTIVATE_DEFERRED resolution.
- Amendment gate: S16 owns none of the four evidence-derived provisional contracts. Any semantic change to an approved operator creates a new version and repeats the relevant review and human gates; it is not an in-place amendment disguised as implementation.
