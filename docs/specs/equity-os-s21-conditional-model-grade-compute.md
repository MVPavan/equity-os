# S21 — Conditional model-grade financial compute

**Status: DRAFT — AWAITING FRESH SOL XHIGH REVIEW**

## Contract purpose

This specification solely owns E-01, the Deferred addition of model-grade financial compute after the minimum deterministic calculation layer. S21 is dormant-only. It defines the activation, interface, reproducibility, evidence, approval, and fail-closed contracts for a future capability; it does not activate E-01 or authorize product-code implementation.

## Authority and ownership

The v2 decision register supplies the controlling implementation gate. The activated goal supplies exact S21 ownership/path and dormant-only program control. S21 has no direct disposition reference.

| Source | Exact source text | Contract effect |
|---|---|---|
| Goal, Exact 25-spec row | `S21 | Conditional model-grade financial compute | docs/specs/equity-os-s21-conditional-model-grade-compute.md | E-01 | None directly; v2 controls` | S21 is the sole primary spec owner for E-01; no disposition item is assigned. |
| Register authority rule | “The wording in this register is authoritative for implementation gates. Narrative reviews explain rationale but do not override this register.” | E-01 acceptance and Status are controlling. |
| E-01 | “High | Add model-grade financial compute | Statement tie-outs, DCF/SOTP/WACC, sensitivities, and sector definitions are reproducible and fail closed | C-08 | Deferred” | Entire capability is `CONDITIONAL_UNACTIVATED`. |
| Phase 1 gate | “missing inputs fail closed;” | Model-grade compute cannot fill gaps through model inference or hidden defaults. |
| Phase 1 gate | “deterministic calculations satisfy their declared exact/tolerance/seeded replay class and the approved narrative is bound to an artifact hash;” | Every operator declares and proves a replay class; narrative output is not the calculator. |
| Phase 1 gate | “GBrain, debate, backtesting, and execution remain outside the release unless separately approved.” | E-01 does not activate any unrelated conditional capability. |

## Activation classification

| Register ID | Activation source Status | Program disposition now | Allowed delivery behavior |
|---|---|---|---|
| E-01 | `Deferred` | `CONDITIONAL_UNACTIVATED` | Specify dormancy, activation evidence, and prospective acceptance behavior only; no planning, implementation, or verified-delivery claim. |

E-01 stays dormant after C-08 becomes Accepted unless its own typed predicate and separate human activation resolution pass. A dependency becoming ready is necessary, not sufficient, authority.

## Scope

If E-01 is validly activated, S21 governs:

- deterministic statement tie-outs and valuation/model operators for DCF, SOTP, WACC, sensitivities, and versioned sector definitions;
- typed inputs, assumptions, operator registries, calculation traces, replay classes, validation, and output schemas;
- explicit handling of missing, stale, contradictory, incomparable, dimensionally invalid, or cutoff-ineligible inputs;
- reviewable analyst/domain approvals for assumption sets and sector definitions used in approved research;
- conformance with the minimum deterministic compute layer rather than replacement of it.

## Non-goals

S21 does not:

- implement any model-grade calculator while E-01 is Deferred;
- own B-07 or C-08 minimum deterministic compute, which belong to S16;
- let an LLM calculate, repair, interpolate, or silently choose authoritative values;
- define one universal valuation methodology for every sector;
- create forecasts, assumptions, or sector definitions without versioned provenance and competent approval;
- provide portfolio construction, quant validation, historical alpha claims, personalized advice, distribution, or execution;
- activate E-02 through E-10 or weaken their independent gates;
- claim that DCF, SOTP, or WACC output is a Fact, recommendation, or approved thesis.

## Interfaces and data contracts

### Registered operator

Every executable calculation is declared before use:

| Field | Contract |
|---|---|
| `operator_id` / `operator_version` | Stable registry identity; behavior changes require a new version. |
| `operator_kind` | Closed values `STATEMENT_TIE_OUT`, `DCF`, `SOTP`, `WACC`, `SENSITIVITY`, or `SECTOR_METRIC`. |
| `input_schema_ref` / `output_schema_ref` | Immutable, versioned schemas with units, currency, period, scope, dimensions, epistemic class, and nullable rules. |
| `definition_ref` | Exact `definition_id`, `definition_version`, and `definition_sha256` for a versioned formula/method and, for sector metrics, a separate versioned sector-definition record. |
| `definition_approval_record_id` | Current `DOMAIN_EXPERT_ACCEPTANCE` record for the exact method definition/version/hash, operator kind, and use scope. It never substitutes for sector-definition or assumption approval. |
| `replay_class` | Exactly `EXACT`, `TOLERANCE`, or `SEEDED_STOCHASTIC`. |
| `tolerance_policy` | Required for `TOLERANCE`; metric, absolute/relative bound, rounding, and comparison order. Null otherwise. |
| `seed_policy` | Required for `SEEDED_STOCHASTIC`; seed source and distribution test. Null otherwise. |
| `missing_input_policy` | Must be `FAIL`; optional scenarios use explicitly modeled nullable branches, never hidden imputation. |
| `code_artifact_sha256` / `runtime_manifest_sha256` | Bind code and execution environment. |

A `CalculationMethodDefinition` contains exactly `definition_id`, `definition_version`, `operator_kind`, `method_graph`, `input_schema_refs`, `output_schema_refs`, `unit_rules`, `currency_rules`, `period_rules`, `scope_rules`, `rounding_policy`, `replay_policy`, `validation_rules`, `tie_out_rules`, `effective_from`, `effective_until`, `owner_id`, `source_ref_ids`, and `evidence_ref_ids`. Its `definition_sha256` is lowercase SHA-256 of the goal-defined canonical JSON object containing exactly those fields. A behavior change creates a new version and digest; a mutable pointer or same-version digest change fails closed.

A known tie-out adjustment is a `TieOutAdjustment` containing exactly `adjustment_id`, `adjustment_version`, `company_id`, `statement_scope`, `period_scope`, `value`, `units`, `currency`, `sign`, `reason`, `source_fact_revision_ids`, `evidence_package_id`, `knowledge_cutoff`, `definition_id`, `definition_version`, `effective_from`, `effective_until`, and `owner_id`. Its `adjustment_sha256` hashes the goal-defined canonical JSON object containing exactly those fields. Transport IDs, approval fields, and execution timestamps are not part of either semantic preimage. Use additionally requires a separate current approval record whose canonical resolution binds the exact record ID/version/digest and use scope.

An `AssumptionSet` contains exactly `assumption_set_id`, `assumption_set_version`, `assumption_schema_ref`, `scenario_scope`, ordered `assumptions`, `currency_fx_policy`, `knowledge_cutoff`, `sensitivity_coverage`, `rationale`, `effective_from`, `effective_until`, `owner_id`, `source_ref_ids`, and `evidence_ref_ids`. Its `assumption_set_sha256` is lowercase SHA-256 of the goal-defined canonical JSON object containing exactly those fields. A changed assumption, order, scope, cutoff, rationale, source, or sensitivity declaration creates a new version and digest; same-version content substitution fails closed.

A `SectorDefinition` contains exactly `sector_definition_id`, `sector_definition_version`, `sector_id`, `metric_semantics`, `inclusion_rules`, `exclusion_rules`, `units`, `scope_rules`, `period_rules`, `source_hierarchy`, `test_fixture_ref_ids`, `effective_from`, `effective_until`, `owner_id`, `source_ref_ids`, and `evidence_ref_ids`. Its `sector_definition_sha256` is lowercase SHA-256 of the goal-defined canonical JSON object containing exactly those fields. A changed semantic, rule, source hierarchy, fixture, owner, or effective interval creates a new version and digest; same-version content substitution fails closed. Approval records and execution metadata are excluded from both semantic preimages and remain separately bound.

### Calculation request

A request contains `calculation_id`, operator identity/version, method-definition ID/version/digest, method-approval-record ID, run/evidence-package ID, knowledge cutoff, ordered input Fact IDs and revisions, input values and units, assumption-set ID/version/digest, assumption-set approval-record ID, exact nonempty assumption use scope, sector-definition ID/version/digest, sector-definition approval-record ID, and exact nonempty sector-definition use scope where applicable, ordered tie-out-adjustment IDs/versions/digests and approval-record IDs where applicable, scenario ID, currency/FX policy, requested outputs, and idempotency key.

Inputs are authoritative only when they resolve to cutoff-eligible Facts or separately labeled, approved assumptions. An inferred/forecast assumption never becomes an observed Fact. Every request validates dimensional compatibility, period alignment, consolidation/statement scope, currency basis, sign convention, and definition version before execution.

Before invoking calculation code, admission resolves each assumption-set and applicable sector-definition ID/version to its immutable record, recomputes the declared digest, and resolves the approval record selected by the request. That record must be current `APPROVED` evidence with `authority_source=HUMAN_RESOLUTION`; its active canonical resolution must match the approval type, exact record ID/version/digest, and the request's exact use-scope string. The request scope and approval/resolution scope must be byte-identical; wildcard, prefix, substring, inferred, or nearby-scope matching is forbidden. Missing records or fields, digest mismatch, wrong approval selection/type/scope, stale/expired/revoked/superseded approval, or resolution ID/content-digest mismatch produces `FAILED_CLOSED` before operator invocation and no consumable numeric result. Recording a corrected digest or approval only after execution cannot repair admission.

### Calculation trace and output

The immutable trace contains:

- request hash and all input Fact/revision/evidence references;
- method-definition, assumption, sector-definition, and tie-out-adjustment versions/digests plus their distinct typed approvals and canonical resolution IDs/digests;
- operator/code/runtime versions and replay policy;
- normalized inputs, conversions, intermediate nodes, formulas, outputs, rounding, tolerances, warnings, and validation checks;
- tie-out residuals and materiality thresholds;
- status `SUCCEEDED` or `FAILED_CLOSED` with a closed error code;
- output artifact hash, execution timestamp, and exact cutoff.

Outputs label each result `computed`; scenario and valuation outputs additionally retain assumption provenance and must never be presented as observed. A failed trace is preserved but supplies no consumable numeric result.

### Statement tie-out contract

A statement/model can proceed only when declared equations reconcile within their registered exact or tolerance policy. At minimum, applicable models explicitly check balance-sheet balance, subtotal/total bridges, cash-flow movement, share-count/dilution consistency, segment-to-group reconciliation, and opening-to-closing period continuity. A waived residual is prohibited; a known accepted adjustment must be the exact versioned, hash-bound explicit input above with provenance and its own current exact-scope `DOMAIN_EXPERT_ACCEPTANCE`.

### DCF, SOTP, WACC, sensitivity, and sector definitions

- DCF declares forecast horizon, cash-flow definition, terminal-value method, discount timing, currency, share count, net debt bridge, and every approved assumption.
- SOTP declares component boundaries, ownership percentages, intercompany eliminations, valuation method per component, net debt/allocation rules, and reconciliation to group scope.
- WACC declares capital structure, risk-free rate, risk premium, beta method, borrowing cost, tax rate, weighting convention, source/cutoff, and applicable country/currency basis.
- Sensitivities declare axes, ordered values, base case, recomputation graph, invalid combinations, and output units; they recompute rather than algebraically relabel stored outputs.
- Sector definitions declare metric semantics, inclusion/exclusion, units, scope, period treatment, source hierarchy, version, competent owner, approval, and effective interval.

## Invariants and fail-closed behavior

1. E-01 has no implementation or active delivery state while Deferred.
2. Every number is produced by registered code; LLM output is never an authoritative calculator or hidden input.
3. Every input is a cutoff-eligible Fact or an explicitly labeled, versioned, approved assumption.
4. Missing, stale, contradictory, dimensionally incompatible, or unresolved inputs produce `FAILED_CLOSED`, never zero, carry-forward, interpolation, or model guess.
5. Statement tie-outs pass their registered exact/tolerance policy before dependent valuation outputs are consumable.
6. Operators, formulas, sector definitions, assumptions, conversions, and runtime are versioned and content-bound in the trace.
7. An operator's replay class is declared before results; it cannot be chosen after observing drift.
8. `EXACT` must reproduce exactly; `TOLERANCE` must remain within its predeclared bound; `SEEDED_STOCHASTIC` must use the stored seed and pass declared distribution checks.
9. Corrections or restatements create new traces and invalidate dependent outputs without overwriting old traces.
10. Sensitivity results bind every axis value and assumption; no unlabeled base-case substitution is allowed.
11. Computed valuation output remains `computed` and does not become a Fact, approved thesis, or distribution approval.
12. A human approval cannot override a failed tie-out, missing evidence, cutoff violation, or stale trace.
13. Every executed method definition and accepted tie-out adjustment has its own current exact-version `DOMAIN_EXPERT_ACCEPTANCE`; one approval cannot satisfy both or cover another version, hash, operator kind, company/period, or use scope.
14. Every calculation admits only the exact content-bound assumption set and applicable sector definition selected in its request, each with its own current exact-ID/version/digest/use-scope approval and active canonical resolution; one record cannot satisfy both obligations or repair an already failed admission.

## Deferred activation guard

The E-01 predicate ID is exactly `AP-E01-MODEL-GRADE-COMPUTE-NEED`; it is not an example or renamable label. Its expression is exactly:

```json
{"op":"ALL","args":[{"op":"COMPARE","metric_id":"MTR-E01-C08-SOURCE-STATUS","comparator":"EQ","expected":"Accepted"},{"op":"COMPARE","metric_id":"MTR-E01-ACTIVATION-RECOMMENDED","comparator":"EQ","expected":true},{"op":"COMPARE","metric_id":"MTR-E01-INPUTS-AND-OWNERS-READY","comparator":"EQ","expected":true},{"op":"COMPARE","metric_id":"MTR-E01-CAPACITY-AND-BUDGET-READY","comparator":"EQ","expected":true}]}
```

All four metrics use `EVIDENCE_JSON`, `register_ids=[]`, one current component-local `FILE_BYTES` activation-evidence object, and these stable pointers/types:

| Metric ID | Type | JSON pointer and binding |
|---|---|---|
| `MTR-E01-C08-SOURCE-STATUS` | `STRING` | `/model_grade_compute/c08_source_status`; the evidence also contains `register_id="C-08"`, live register file SHA-256, exact C-08 row-span digest, and current acceptance-proof refs. The producer and validator independently parse the live register and copy its exact Status; a ledger label is invalid. |
| `MTR-E01-ACTIVATION-RECOMMENDED` | `BOOLEAN` | `/model_grade_compute/activation_recommended` |
| `MTR-E01-INPUTS-AND-OWNERS-READY` | `BOOLEAN` | `/model_grade_compute/inputs_and_owners_ready` |
| `MTR-E01-CAPACITY-AND-BUDGET-READY` | `BOOLEAN` | `/model_grade_compute/capacity_and_budget_ready` |

Each metric names that current evidence reference (or `null` only before evidence exists) and its predeclared UTC expiry. Exact C-08 acceptance is therefore content-bound through a supported string metric; the goal's `REGISTER_STATUS` boolean is not used because it cannot distinguish `Open`, `In progress`, and `Accepted`. `FALSE`, `UNKNOWN`, any non-`Accepted` C-08 value, expired evidence, or stale digests prevents activation. The predicate `evaluation_sha256` is lowercase SHA-256 of the goal-defined canonical JSON object containing exactly `predicate_id`, `expression`, `metrics`, `resolved_values`, `digest_sources`, `result`, and `evaluated_at`; `expression` is the tree above, `metrics` retain their declared order, and the resolved/digest-source objects are keyed by metric ID.

The evidence package must quantify the active workflow need that minimum compute cannot meet, name candidate calculations/sectors, demonstrate sufficient authoritative inputs and golden fixtures, identify competent method-definition, adjustment, sector-definition, and assumption owners, estimate analyst value and operating burden, and declare capacity/budget.

A recomputed `TRUE` does not activate E-01. Activation also requires a current canonical human resolution with decision `ACTIVATE_DEFERRED`, exact E-01 scope, competent product authority, evidence and predicate digests, and one matching `PRODUCT_OWNER_DECISION`. The activation record and approval record must copy the same canonical resolution decision ID/content digest and bind the fixed predicate ID plus current `evaluation_sha256`. This spec, goal activation, a coordinator statement, a valuation request, or C-08 acceptance cannot supply that authority.

## Evidence and typed human-approval gates

| Gate | Evidence required | Approval required | Fail-closed result |
|---|---|---|---|
| S21 artifact approval | Current spec hash and persisted clean fresh-context Sol xhigh review | One `DELEGATED_ARTIFACT_APPROVAL` under delegated goal authority | Status remains draft. This file records no approval. |
| E-01 activation | Current predicate evaluation, need/inputs/owner/capacity evidence, C-08 state, and canonical resolution digest | One `PRODUCT_OWNER_DECISION` authorizing `ACTIVATE_DEFERRED` for E-01 | E-01 stays dormant. |
| Calculation-method use | Exact method-definition ID/version/hash, formulas/method graph, schemas, fixtures, replay/tie-out policy, sources, effective interval, and competent review evidence | One `DOMAIN_EXPERT_ACCEPTANCE` by a competent financial-method owner for the exact definition/version/hash, operator kind, and use scope | The operator is unavailable and the calculation fails closed. |
| Accepted tie-out-adjustment use | Exact adjustment ID/version/hash, company/statement/period scope, value/units/currency/sign, provenance, cutoff, method version, effective interval, and competent review evidence | One separate `DOMAIN_EXPERT_ACCEPTANCE` by a competent financial-method owner for the exact adjustment/version/hash and use scope | The adjustment is unavailable; the unadjusted model must still tie out or fail closed. |
| Sector-definition use | Exact definition ID/version/hash, sources, test fixtures, effective interval, request-selected approval-record ID/use scope, and reviewer evidence | One `DOMAIN_EXPERT_ACCEPTANCE` by a competent owner for the exact definition ID/version/hash and identical use scope | Admission fails and the dependent calculation is not invoked. |
| Assumption-set use in approved research | Exact assumption-set ID/version/hash, sources/rationale, scenario scope, cutoff, sensitivity coverage, request-selected approval-record ID/use scope, and trace refs | One `ANALYST_ACCEPTANCE` for the exact assumption-set ID/version/hash and identical use scope | Admission fails and the dependent calculation is not invoked or admitted to an approved thesis/report. |
| Capacity/budget commitment | Measured cost/latency/review load and named operating scope | `BUDGET_APPROVAL`, `CAPACITY_COMMITMENT`, and `NAMED_OWNER_COMMITMENT` when implementation commits those resources | Implementation or production gate remains blocked. |
| Security exception, if any | Exact exception, affected trace/evidence boundary, compensating controls, and expiry | One `SECURITY_EXCEPTION` by competent human authority | Exception is unavailable. |

Delegated artifact approval applies only to the specification. It cannot grant activation, domain or analyst acceptance, budget/capacity/owner commitment, production approval, distribution approval, or an exception. Each method-definition, tie-out-adjustment, sector-definition, and assumption-set requirement is satisfied one-to-one by a distinct approval record with `authority_source=HUMAN_RESOLUTION`; method, adjustment, and sector records use the required `DOMAIN_EXPERT_ACCEPTANCE`, while assumption records use the required `ANALYST_ACCEPTANCE`. Each record must copy one active canonical `SATISFY_APPROVAL` resolution's human actor, competent authority basis, exact ID/version/hash/use scope, timestamp, evidence, decision ID, and content digest. Missing, expired, revoked, superseded, wrong-ID, wrong-version, wrong-hash, wrong-scope, wrong-type, or matching-string-only records fail closed. No nearby or reused approval passes.

## Acceptance tests and verification

After valid E-01 activation, mechanical verification must cover:

1. Structural validation rejects unknown operators, missing schema/definition/assumption/sector versions or required digests/approval-record IDs/use scopes, same-version digest changes, and invalid replay policies.
2. Golden statement fixtures pass exact tie-outs; injected imbalance, scope mismatch, and sign error fail closed.
3. Missing, null, post-cutoff, stale, contradictory, wrong-unit, wrong-currency, wrong-period, and wrong-consolidation inputs each fail closed.
4. DCF fixtures bind every assumption to the request-selected assumption-set digest and current exact-scope approval before execution and reproduce under the declared replay class; changed assumptions create distinct traces/hashes and require a new exact-version approval.
5. SOTP fixtures reconcile components, ownership, eliminations, and group scope; double counting is rejected.
6. WACC fixtures prove source/cutoff, units, currency/country basis, capital weighting, and tax handling.
7. Sensitivity fixtures recompute the model at every declared grid point and reject invalid/unlabeled combinations.
8. No operator runs with an unapproved, expired, revoked, wrong-kind, wrong-version, wrong-hash, or wrong-scope calculation-method definition; calculations using a sector definition independently reject an unapproved, expired, revoked, superseded, wrong-sector, wrong-version, wrong-hash, wrong-scope, or wrong-record selection.
9. Exact operators match byte-for-byte normalized numeric outputs; tolerance operators pass at the boundary and fail just outside it; seeded operators reproduce and pass distribution checks.
10. A corrected Fact invalidates dependent current outputs, creates a new trace, and preserves the prior trace.
11. Idempotent retry returns the same trace; changed input under the same key is rejected.
12. Output labels remain `computed`; no path writes a valuation result into the Fact store as observed evidence.
13. Human approvals cannot turn a `FAILED_CLOSED` trace into a successful one.
14. While E-01 remains Deferred, owned-file/program structural validation proves there are no E-01 implementation refs and no `PLANNED`, `IMPLEMENTING`, or `VERIFIED` delivery state.
15. Tie-out fixtures reject every unapproved, expired, revoked, wrong-company/period, wrong-version, wrong-hash, wrong-method, or wrong-scope adjustment and prove that approval cannot waive a residual or failed equation.
16. Predicate fixtures prove C-08 `Open` or `In progress`, copied/stale/mismatched status evidence, or any non-true readiness leaf cannot produce `TRUE`; exact live C-08 `Accepted` plus all current true readiness leaves can produce `TRUE` but still cannot activate E-01 without the matching resolution and approval record.
17. Admission fixtures for assumption sets and sector definitions each reject missing approval fields, same-version content substitution, wrong digest, wrong approval-record selection/type/ID/version/hash/use scope, expired/revoked/superseded approval, and resolution ID/content-digest mismatch; every case records `FAILED_CLOSED`, proves the operator was not invoked, and emits no consumable numeric result.

Fresh command outputs must bind the current code, schemas, definitions, fixtures, traces, approvals, and evidence. An agent statement, example calculation, spreadsheet screenshot, or clean spec review alone does not satisfy E-01.

## Dependencies and handoffs

- E-01 depends on C-08, owned with B-07 by S16.
- S12 supplies Fact identity/revision/schema semantics; S13 supplies Claim/vocabulary/evidence-validation semantics.
- S10 supplies source-of-truth and evidence-retention policy; S11 supplies cutoff/run reproducibility requirements.
- S15 supplies human review and promotion boundaries for claims/narrative outputs.
- S08 owns workflow budget/capacity definitions that activation evidence must use.
- E-01 does not activate or own stress-test companies, bull/bear review, event monitoring, quant validation, distribution, or execution.
- No cross-reference transfers primary E-01 ownership away from S21.

## Amendment gate

S21 is not one of the four goal-designated evidence-derived provisional contracts, so this draft does not invent a final sector library, valuation assumption set, or activation date. If E-01 is activated, the first implementation plan must bind the evidence-derived operator inventory, sector definitions, acceptance fixtures, owners, and resource approvals to this contract; any incompatible change to interfaces, replay policy, fail-closed rules, approval types, or register authority requires a versioned S21 amendment, fresh Sol xhigh review, delegated artifact approval, and authority reconciliation before dependent implementation resumes. Routine addition of a conforming versioned operator or definition follows the approved registry process and does not silently rewrite this contract.
