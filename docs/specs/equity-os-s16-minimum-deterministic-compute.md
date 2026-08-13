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
| seed_policy | Required and non-null for STOCHASTIC; null otherwise |
| distribution_check_policy | Required and non-null for STOCHASTIC, including distributional assertions, sample count, confidence/error bounds, and pass rule; null otherwise |
| rounding_policy | Mode, precision, and whether rounding occurs only at display or within the operator |
| missing_input_policy | Always FAIL_CLOSED for this MVP |
| zero_denominator_policy | Always FAIL_CLOSED unless the operator version explicitly returns a typed NOT_MEANINGFUL result |
| applicability_rules | Required accounting basis, consolidation scope, period type, and exclusions |
| code_artifact | Repository-relative implementation identity and content hash |
| operator_definition_sha256 | SHA-256 of the canonical definition preimage specified below |
| approval_bindings | One exact reference to the registry-level S16-G02 requirement and one operator-version-specific S16-G03 requirement binding; each names its approval_id and, when satisfied, its unique matched approval_record_id, human_review_id, resolution_decision_id, and resolution_content_sha256 |
| approval_state | Derived DRAFT or APPROVED; never caller supplied |

The `operator_definition_sha256` preimage is the program's canonical JSON of every immutable field in this table from `operator_id` through `code_artifact`, excluding `operator_definition_sha256`, `approval_bindings`, and derived `approval_state`. Referenced policies and the code artifact appear as stable IDs, versions, and content digests, not unresolved labels.

Every definition references both approval requirements even while unresolved. S16-G02 is one registry-inventory requirement satisfied by one product-owner record for the exact inventory digest; definitions in that inventory reference the same requirement rather than minting duplicate requirements for the same decision. S16-G03 is a separate requirement for each exact operator ID, version, and digest. `approval_state=APPROVED` if and only if the referenced S16-G02 `PRODUCT_OWNER_DECISION` requirement and the operator-specific S16-G03 `DOMAIN_EXPERT_ACCEPTANCE` requirement are each `SATISFIED` one-to-one by distinct, current `APPROVED` records. Each binding must match type, authority, exact scope, actor, timestamp, evidence, authority source, active human-resolution decision ID, and resolution content digest. A missing, stale, denied, revoked, expired, mismatched, reused, or delegated-review record makes the derived state DRAFT. One record may not satisfy both requirements or any second requirement.

Only a definition whose conjunction above recomputes to APPROVED may execute in an approvable run. This specification proposes the minimum families but does not mark any definition approved.

### 3.2 CalculationInput

Each input contains input_id, input_role, fact_id, observation lineage, raw decimal value, normalized decimal value, unit, currency, scale, period start/end, instant-or-duration classification, statement and consolidation scope, dimensions, definition/version, valid time, knowledge time, source location, and evidence reference.

An input without a resolvable fact/evidence identity is invalid. A request may not substitute a prose value, an LLM-produced number, or a later-than-cutoff fact.

### 3.3 CalculationRequest

A request contains calculation_id, run_id, an `evidence_package_ref` containing the exact S10 evidence_package_id, version, and manifest_sha256, a `pre_calculation_attempt_manifest_ref` containing the exact S11 attempt_id, attempt_manifest_version, and attempt_manifest_sha256, requested_at, operator_id/version, ordered inputs, explicit assumptions, requested output role, caller identity, and request_digest. The package reference is the reconstruction key: it must resolve the exact sealed S10 manifest bytes, whose complete declared field set binds schema/profile, owning run/attempt, cutoff, creation time, document/fact/claim/calculation/policy references, parent-package reference, and change set. The registered source, fact, claim, and cutoff identifiers used by this calculation must match that resolved manifest; they are validation inputs, not a partial substitute from which omitted manifest fields are guessed.

`pre_calculation_attempt_manifest_ref` is not an arbitrary package-bearing S11 version. It must resolve the unique immutable AttemptManifest version sealed at S11 lifecycle step 3 for this attempt: the post-package, pre-calculation version whose evidence_package_ref exactly equals the request's package reference, whose `calculation_trace_refs` is empty because step 4 has not begun, and which is referenced by the companion RunManifest version sealed at that same lifecycle step. Its immediate predecessor chain must validate through the step-2 pre-access version. The reference is selected and sealed before `requested_at` and before any calculation executes; a later manifest cannot be substituted merely because it still names the same package.

The content-dependency order is strictly acyclic:

`sealed S10 package -> S11 step-3 post-package/pre-calculation AttemptManifest -> CalculationRequest -> CalculationTrace -> S11 step-5 successor AttemptManifest`.

The validator rejects a manifest closure that refers back to the request or trace (self-reference), any descendant of the exact step-3 version, any later version, any version whose calculation_trace_refs contain the current calculation/attempt/request or resulting trace, any unsealed or not-yet-registered future version, and any version registered after `requested_at` or calculation start. It also rejects a sibling/fork, stale predecessor, mismatched run/attempt/package, or companion RunManifest disagreement. `request_digest` is SHA-256 of the program's canonical JSON of all preceding request fields plus the current operator-definition digest and the fact/evidence content digests for every ordered input; it excludes only `request_digest` itself. A missing or unresolved package/attempt reference, non-step-3 reference, incomplete manifest closure, field/order mismatch, or referenced digest mismatch makes the request invalid.

### 3.4 CalculationTrace

A completed attempt contains:

- calculation_id and immutable attempt_id;
- request digest and evidence-package identity;
- operator definition and code-artifact hashes;
- replay class, runtime identity, dependency lock identity, locale, timezone, and decimal context;
- resolved inputs and assumptions;
- normalized operation tree and intermediate steps;
- closed outcome plus output value/unit when numeric, or typed non-numeric result/failure metadata;
- tolerance, seed, distribution-check, and rounding records as applicable;
- warnings that do not change pass/fail;
- created-at time and trace digest.

The trace digest is SHA-256 of the program's canonical JSON of every trace field above except the digest itself. It therefore binds the request digest, definition/code digests, runtime, ordered resolved inputs, operation tree, intermediates, outcome, and applicable tolerance, seed, distribution-check, and rounding records.

Allowed outcomes are SUCCEEDED, NOT_MEANINGFUL, BLOCKED_MISSING_INPUT, BLOCKED_INVALID_INPUT, BLOCKED_AMBIGUOUS_DEFINITION, BLOCKED_SCOPE_MISMATCH, BLOCKED_UNIT_MISMATCH, BLOCKED_ZERO_DENOMINATOR, and REPLAY_MISMATCH. SUCCEEDED carries the typed numeric output. NOT_MEANINGFUL is a completed, non-numeric result permitted only when the approved operator version's explicit zero-denominator policy selects it; it carries the zero denominator, applicable input facts, and reason, and cannot support a numerical computed claim. BLOCKED_ZERO_DENOMINATOR applies when no approved NOT_MEANINGFUL policy exists. Every blocked outcome has no authoritative numeric output.

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

MVP implementations should use EXACT where decimal arithmetic and operator semantics support exact replay. TOLERANCE is permitted only with an approved, operator-specific tolerance. STOCHASTIC is outside the minimum list unless this specification is amended and separately approved; registry validation rejects a STOCHASTIC definition, including one carrying otherwise valid S16-G02/S16-G03 records, while that amendment is absent. After such an amendment, both seed and distribution-check policies are mandatory; a seed alone does not make a stochastic result exact.

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
13. S16 verification cannot satisfy its assigned G-1 obligations unless the exact package ID/version/digest resolves to the sealed S10 manifest, the request binds the exact acyclic S11 lifecycle-step-3 post-package/pre-calculation AttemptManifest version, the applicable S10/S11 proof validates every declared manifest field and referenced dependency in that package's complete closure, and the registered source, fact, claim, and cutoff identifiers used by the calculation match that manifest. A partial identifier list, arbitrary later package-bearing manifest, or calculation replay alone cannot satisfy that proof.

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
- current S10/S11 evidence-package reconstruction proof bound to the same package ID/version/digest and exact lifecycle-step-3 post-package/pre-calculation attempt-manifest ID/version/digest used by the S16 fixtures, validating the acyclic version order, companion run-manifest reference, complete S10 manifest field set and dependency closure, plus the calculation's registered source/fact/claim/cutoff identifiers;
- current typed approval records for S16-G02 through S16-G04;
- fresh delegated review evidence for S16-G01;
- verification command output bound to the tested artifact hashes.

## 7. Acceptance tests and verification

| Test ID | Required proof |
|---|---|
| S16-T01 | Registry validation rejects a definition missing formula, input roles, replay class, code hash, either approval requirement binding, or a replay-class-required tolerance, seed, or distribution-check policy. |
| S16-T02 | Every minimum family has at least one version whose APPROVED state recomputes from distinct current one-to-one S16-G02 and S16-G03 records before B-07 can be accepted; one generic, reused, stale, or mismatched record never passes. |
| S16-T03 | Exact-class fixture replays with identical normalized inputs, steps, and output. |
| S16-T04 | Tolerance-class fixture passes at the boundary and fails immediately outside it. |
| S16-T05 | Missing, post-cutoff, ambiguous, wrong-period, wrong-unit, wrong-currency, and wrong-scope inputs each yield a typed blocked outcome and no numeric output. |
| S16-T06 | Growth handles zero and sign-changing comparison values only according to its declared policy. An approved NOT_MEANINGFUL policy returns that closed non-numeric outcome with denominator facts and reason; without it, zero yields BLOCKED_ZERO_DENOMINATOR. |
| S16-T07 | Margin, cash-conversion, and leverage requests cannot substitute an unregistered numerator or denominator. |
| S16-T08 | Dilution/share-count and reconciliation fixtures preserve every movement and fail on an unexplained residual. |
| S16-T09 | Guidance comparison rejects mismatched versions, periods, units, or scopes. |
| S16-T10 | Changing an input, reconstruction identifier, operator definition, code artifact, runtime, rounding rule, tolerance, seed, or distribution-check policy invalidates the prior trace digest and dependent verification. |
| S16-T11 | Narrative byte differences do not alter a valid calculation trace, while a changed approved narrative produces a different narrative artifact hash. |
| S16-T12 | A generated numerical computed claim resolves to a SUCCEEDED calculation trace; a NOT_MEANINGFUL or blocked calculation cannot support a numerical material computed claim. |
| S16-T13 | Starting from the request's exact evidence-package ID/version/digest and exact S11 lifecycle-step-3 post-package/pre-calculation attempt-manifest ID/version/digest, the applicable S10/S11 proof reconstructs the exact canonical manifest bytes, validates every declared manifest field, companion run-manifest reference, predecessor chain, and full referenced dependency closure, and confirms the calculation's registered source/fact/claim/cutoff identifiers are included. A missing manifest field/reference, substituted version, partial identifier-only reconstruction, parent/change-set mismatch, or digest mismatch blocks S16 verification. |
| S16-T14 | Before an approved stochastic amendment exists, registry validation rejects every STOCHASTIC definition even if its approval bindings are otherwise satisfied; after such an amendment, a missing seed policy or distribution-check policy is rejected. |
| S16-T15 | For otherwise identical zero-denominator fixtures, an operator with an approved NOT_MEANINGFUL policy emits that exact non-numeric outcome, while an operator without it emits BLOCKED_ZERO_DENOMINATOR; neither trace exposes a numeric output or satisfies a numerical computed claim. |
| S16-T16 | Manifest-order negative fixtures reject a self-referential manifest closure, a descendant or later version of the exact step-3 snapshot, a version containing the current calculation/request/resulting trace, a sibling/fork or stale predecessor, and an unsealed, future, or post-request version. The exact step-3 snapshot passes and the later step-5 manifest may register the completed trace only after the trace digest exists. |

Verification is successful only when all tests pass against the current registry/code hashes, the same-package S10/S11 reconstruction proof passes, and all required evidence and one-to-one approvals are current. Test output alone cannot satisfy human gates.

## 8. Dependencies, activation, and amendment guards

- B-07 is blocked on A-04. Because A-04 has a provisional-to-final amendment gate owned by S06, B-07 and dependent C-08 work remain blocked while the mandatory post-baseline A-04 amendment is due or A-04 is not validly accepted.
- C-08 is blocked on accepted B-07 definitions.
- S10/S11 supply the sealed evidence-package manifest, complete dependency closure, and run/attempt/reproducibility identities; their applicable exact-reconstruction acceptance proof for the same package ID/version/digest and exact S11 lifecycle-step-3 post-package/pre-calculation attempt-manifest version is a prerequisite to satisfying S16's assigned G-1 coverage. The later S11 step-5 version consumes completed S16 trace references and can never be the request's ancestor reference. S12 supplies fact identity; S13 supplies computed-claim validation. S16 consumes those interfaces and proof without taking their ownership.
- Deferred activation guard: not applicable to owned rows. B-07 and C-08 were Open at activation, so S16 is active-only and may not be marked dormant or require an ACTIVATE_DEFERRED resolution.
- Amendment gate: S16 owns none of the four evidence-derived provisional contracts. Any semantic change to an approved operator creates a new version and repeats the relevant review and human gates; it is not an in-place amendment disguised as implementation.
