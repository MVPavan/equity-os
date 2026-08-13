# S25 — Controlled quant validation and historical-replay leakage

Status: DRAFT — AWAITING FRESH SOL XHIGH REVIEW

## Contract posture

This document is the implementation contract for S25. Normative terms MUST,
MUST NOT, SHOULD, and MAY are binding. S25 owns two separately gated Deferred
components. It defines how future quant validation and historical replay must
remain controlled and leakage-aware; it activates neither component and makes
no performance claim.

## Authority and ownership

| Authority | Exact source text | Effect in this contract |
|---|---|---|
| Exact 25-spec table | `S25` | Stable spec identifier. |
| Exact 25-spec table | `Controlled quant validation and historical-replay leakage` | Exact title. |
| Exact 25-spec table | `docs/specs/equity-os-s25-quant-validation-historical-leakage.md` | Exact owned path. |
| Exact 25-spec table | `E-05, E-10` | Exact primary register owners; each retains independent status and activation. |
| Exact 25-spec table | `M-4, 6.5` | Exact disposition references assigned to S25. |
| Activation classification | `the dormant-only specs are exactly S03, S04, and S20–S25` | S25 is dormant-only at the pinned draft snapshot. |
| E-05 register priority | `High` | Exact source priority; this draft does not change it. |
| E-05 register decision or action | `Begin controlled quant validation` | Exact owned action. |
| E-05 required evidence / acceptance | `Uses collected point-in-time data; leakage, revisions, universe history, fees, liquidity, and benchmark are disclosed` | Every named disclosure is mandatory. |
| E-05 dependencies | `B-09, E-10` | Exact register dependency edges. |
| E-05 source status | `Deferred` | E-05 remains dormant until the governed transition completes. |
| E-10 register priority | `High` | Exact source priority; this draft does not change it. |
| E-10 register decision or action | `Publish historical-replay leakage policy` | Exact owned action. |
| E-10 required evidence / acceptance | `Store/tool leakage controls are tested; model-weight leakage is disclosed as an uncontrollable limitation; historical LLM results are not represented as clean alpha evidence` | The two leakage classes and clean-alpha prohibition are distinct and mandatory. |
| E-10 dependencies | `C-15` | Exact register dependency edge. |
| E-10 source status | `Deferred` | E-10 remains dormant until the governed transition completes. |
| M-4 disposition | `Accept, split into two policies.` | Current/store/tool controls and model-weight disclosure remain separate. |
| M-4 model-weight rule | `Model-weight leakage is different. It cannot be eliminated and must be disclosed for historical LLM evaluation.` | It is an uncontrollable historical limitation, not a controllable store/tool test result. |
| 6.5 scope | `It is a standing caveat for historical LLM replay and agent-alpha claims.` | Historical LLM output cannot be promoted as clean alpha evidence. |

The v2 decision register is operational authority for E-05 and E-10 Status and
gates. The complete third-order disposition report is authoritative for the
owned M-4 and 6.5 occurrences without turning them into new register rows.
This draft changes neither source and supplies no activation decision. A
conflict blocks work and is resolved by the governing authority.

## Scope

After each component's independent valid activation, S25 governs:

- pre-registered, bounded quantitative validation of explicitly named research
  hypotheses (E-05 scope);
- construction and validation of point-in-time datasets and replay manifests;
- deterministic leakage, survivorship, revision, corporate-action, and
  availability checks;
- historical replay only over evidence whose knowledge-time availability is
  provable for the simulated decision time (E-10 scope); and
- reporting that separates research validation from production, trading, and
  distribution claims.

## Non-goals

S25 does not authorize live trading, portfolio construction, execution-system
operation, automated stock selection, investment recommendations, production
signals, procurement, external distribution, or claims that unavailable
point-in-time history has been recreated. It does not optimize a model on the
holdout, treat a backtest as causal proof, or activate E-05 and E-10 together
by convenience.

## Interfaces and data contracts

### `QuantValidationProtocol`

| Field | Type | Contract |
|---|---|---|
| `protocol_id` | stable identifier | Immutable and unique. |
| `spec_id` | enum | Exactly `S25`. |
| `register_scope` | nonempty enum set | One or both of `E-05`, `E-10`; it selects operations, not dependency satisfaction. |
| `activation_binding_by_register` | typed activation-envelope map | Key set equals `register_scope` exactly. Each value contains that register's `activation_record_id`, `activation_predicate_id`, `activation_predicate_sha256`, `approval_record_id`, `human_resolution_decision_id`, and `human_resolution_sha256`. The map is attached after the body digest is computed and is outside that digest's preimage. |
| `dependency_binding_by_register` | typed map | For E-05, exact keys are `B-09` and `E-10`; for E-10, exact key is `C-15`. Each value content-binds the live register row, source digest, required `Accepted` status, and retained activation record when the dependency was originally Deferred. Dependency bindings do not add an operation to `register_scope`. |
| `hypothesis` | typed object | Subject, metric, direction, horizon, universe, materiality, and observable falsifier fixed in advance. |
| `universe_snapshot_id` | identifier | Point-in-time membership with inclusion/exclusion rationale. |
| `feature_set_version` | identifier | Closed feature definitions and allowed availability lags. |
| `target_version` | identifier | Closed outcome definition and horizon. |
| `split_plan` | object | Chronological train/validation/holdout periods and embargo/purge rules. |
| `metrics` | nonempty array | Primary and secondary metrics, uncertainty method, and failure threshold. |
| `fee_assumptions` | typed object | Required for E-05: complete fee schedule, effective dates, calculation method, and evidence; zero-fee treatment requires explicit evidence and rationale. E-10-only scope uses evidenced `NOT_APPLICABLE` only when it makes no performance claim. |
| `liquidity_assumptions` | typed object | Required for E-05: point-in-time volume/depth inputs, participation and capacity limits, missing-data treatment, and evidence. E-10-only scope uses evidenced `NOT_APPLICABLE` only when it makes no performance claim. |
| `benchmark_definition` | typed object | Required for E-05: stable benchmark ID, point-in-time membership/version, return convention, rebalance rule, currency, and comparison method. E-10-only scope uses evidenced `NOT_APPLICABLE` only when it makes no performance claim. |
| `budgets` | object | Maximum data, compute, trials, elapsed time, and analyst review. |
| `stop_rules` | nonempty array | Leakage, rights, evidence, multiple-testing, budget, and safety stops. |
| `required_approval_ids` | nonempty typed reference array | Exact one-to-one pre-run requirements from `S25-G02` through `S25-G06`, each bound to its named register scope; boundary-conditioned requirements are resolved before protocol freeze. `S25-G01` is a separate spec-artifact gate, while `S25-G07` through `S25-G09` are instantiated after their report or downstream content exists. This pre-run approval envelope is outside the body digest's preimage. |
| `protocol_body_sha256` | lowercase SHA-256 | Pre-activation body digest defined below. |

`protocol_body_sha256` is SHA-256 of canonical JSON of every protocol field
except `activation_binding_by_register`, `required_approval_ids`, and
`protocol_body_sha256`. Canonical JSON is UTF-8 with sorted keys, no
insignificant whitespace, direct Unicode, JSON booleans/null, and arrays in
declared order. The body is frozen and hashed before the activation and
operational-approval envelopes are attached. Every operational approval
requirement scope MUST name `protocol_id`, `protocol_body_sha256`, `S25`, and
exactly one of `E-05` or `E-10`; a requirement bound to another digest or a
compound register scope cannot pass. The validator recomputes the body
projection exactly, validates each envelope independently, and rejects a
missing field, an extra field in the digest preimage, or any body mutation not
accompanied by a new digest and new scoped envelopes. The protocol body is
frozen before holdout access. Changes create a new body and cannot overwrite
the prior one.

`S25-G01-DELEGATED-ARTIFACT` is independent of every runtime protocol. Its
scope MUST name `S25`, this repository-relative path, and the SHA-256 of the
exact spec file bytes reviewed. Its record carries the clean review round,
reviewer identity/session, source hashes, timestamp, and persisted evidence
path. It MUST NOT depend on or name a future `protocol_id`,
`protocol_body_sha256`, activation record, `register_scope`, or E-05/E-10
runtime approval. Any edit to the spec bytes requires a new artifact review and
record; a later protocol change neither supplies nor invalidates the artifact
approval for unchanged spec bytes.

For each selected register, the validator dereferences its activation binding
rather than trusting copied values. It recomputes the governed activation
predicate using three-valued logic and hashes canonical JSON with exactly these
keys and values: `predicate_id`, `expression`, `metrics`, deterministically
`resolved_values`, `digest_sources`, `result`, and `evaluated_at`. A binding
passes only when that digest is current, the result is `TRUE`, all metrics are
resolved and unexpired, and the activation record, approved
`GOAL_OR_PROCESS_AUTHORIZATION` record, and active `ACTIVATE_DEFERRED` canonical human
resolution carry the same register, predicate ID/digest, exact scope, decision
ID, and resolution digest. Missing, copied, stale, superseded, revoked, or
content-mismatched values leave that register dormant.

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
`resolution_decision_ids`, and `content_sha256`. The separate `S25-G01`
artifact record uses `DELEGATED_AUTOMATED` with null human-resolution fields.
Any absent field or mismatch leaves the requirement `UNRESOLVED`; only
`SATISFIED` passes.

### `PointInTimeDatasetManifest`

Each manifest contains dataset/version ID, source IDs and rights versions,
byte hashes, entity/security identifiers, membership snapshots, field-level
valid-time and knowledge-time rules, actual first-seen or availability times,
revision/supersession links, corporate-action adjustments and versions,
missingness, exclusions, transformations, feature lineage, target lineage,
cutoff, and build-code version. An estimated availability time is explicitly
typed and cannot satisfy a proof requiring observed availability.

### `ReplayDecisionFrame`

Each frame binds simulated decision time, knowledge cutoff, eligible universe,
the exact evidence package available at that time, feature values and lineage,
calculation traces, missing/blocked inputs, produced candidate output, and
subsequent outcome kept outside the input boundary. Replays append results and
never overwrite source facts or approved theses.

### `LeakageFinding`

A finding contains stable ID, protocol/dataset/frame IDs, category,
`control_class`, severity, affected rows and periods, exact evidence, detection
rule/version, expected temporal relation, observed relation, remediation state,
reviewer, and terminal disposition. The closed minimum categories are
future-knowledge, revision/restatement, survivorship, universe-selection,
target, feature, corporate-action, source-availability, label, split/embargo,
analyst-memory, repeated-holdout, and model-weight leakage. `control_class` is
`CONTROLLABLE_STORE_OR_TOOL` for testable data/retrieval/tool boundaries and
`UNCONTROLLABLE_MODEL_WEIGHT` only for the standing historical LLM limitation;
the classes MUST NOT be merged or substituted for one another.

### `ModelWeightLeakageDisclosure`

Every report carries this typed object separately from controllable leakage
test results. It records whether an LLM contributed to historical outputs, the
model/version evidence available, replay periods, the uncontrollable
model-weight limitation, affected claims, and
`clean_alpha_representation_prohibited=true`. When no LLM contributed, an
evidenced `NOT_APPLICABLE` value is required; omission or generic limitations
text is not equivalent to this disclosure.

### `QuantValidationReport`

The report has a stable `report_id` and includes the frozen protocol, complete
trial registry, dataset and code hashes, all leakage findings, failed and
blocked runs, denominators, uncertainty, primary and secondary results, analyst
review cost, limitations, E-05 fee and liquidity results and benchmark-relative
results (or evidenced `NOT_APPLICABLE` in a non-performance E-10-only report),
tested controllable store/tool leakage controls, the separate
`ModelWeightLeakageDisclosure`, terminal technical outcome `PASS`, `FAIL`, or
`BLOCKED`, and `report_body_sha256`. The digest is SHA-256 of canonical JSON of
every report field except `report_body_sha256`. `PASS` means only that the
frozen validation rule passed; it does not encode `S25-G07` approval and is not
clean alpha evidence or production, causal, regulatory, distribution, or
investment approval.

## Invariants and fail-closed behavior

1. E-05 and E-10 are independently conditional. The separately scoped
   spec-artifact gate controls whether this contract may be implemented but is
   not a runtime protocol requirement. For each selected operation,
   `protocol_body_sha256` validates before the activation and approval
   envelopes; then the selected register's activation binding and dependency
   bindings validate. The matching activation gate, both
   `S25-G04`, every applicable `S25-G05`, and both `S25-G06` requirements are
   `SATISFIED` before that operation starts. `S25-G07` may be satisfied only from
   completed results; production and distribution remain separately sequenced
   behind `S25-G08` and `S25-G09`. `S25-G07` through `S25-G09` are absent from
   the frozen pre-run inventory and are instantiated in separate
   report/downstream envelopes only after the content they bind exists.
2. E-05 activation and operation fail closed unless live register authority
   shows both exact dependencies `B-09` and `E-10` as `Accepted`, with current
   content-bound dependency proof. E-10 being `Deferred`, `Open`, `In progress`,
   `Rejected`, missing, or digest-stale cannot satisfy E-05.
3. E-05 activation cannot authorize a historical-replay operation under E-10;
   accepted E-10 dependency proof does not place E-10 in `register_scope`.
   E-10 activation cannot authorize quant validation under E-05.
4. An E-10 operation fails closed unless exact dependency `C-15` is `Accepted`
   with current content-bound proof.
5. A datum may enter a decision frame only when its knowledge time and source
   availability are no later than the simulated decision time, including the
   configured operational lag.
6. Later revisions, restatements, index membership, classifications, and
   corporate-action knowledge MUST NOT replace the version knowable at the
   frame cutoff.
7. Train, validation, and holdout are chronological. Purge and embargo rules
   prevent overlapping labels or feature windows from crossing splits.
8. Hypothesis, universe, features, target, primary metric, thresholds, trial
   budget, and stop rules are frozen before holdout access. E-05 also freezes
   fees, liquidity assumptions, and benchmark before holdout access.
9. Every attempted parameter/model variant is recorded. Failed, abandoned,
   blocked, and null-result trials remain in the denominator.
10. Missing point-in-time evidence yields missing data or `BLOCKED`; it MUST NOT
   be filled from hindsight or a present-day snapshot and described as replay.
11. Deterministic calculations use registered code and calculation traces; an
   LLM never serves as the authoritative calculator.
12. E-05 always discloses fees, liquidity, and benchmark. Missing, unevidenced,
    or silently zero/default assumptions produce `BLOCKED`, not `PASS`; an
    E-10-only non-performance report records evidenced `NOT_APPLICABLE` rather
    than omitting those fields.
13. Historical LLM results always carry the separate uncontrollable
    model-weight disclosure and MUST NOT be represented as clean alpha evidence;
    this caveat never weakens controllable store/tool leakage tests.
14. Source-rights uncertainty, hash/lineage failure, entity ambiguity, stale
    activation, budget breach, a controllable store/tool Important/Critical
    finding, or missing approval blocks the affected run and every dependent
    conclusion. A disclosed `UNCONTROLLABLE_MODEL_WEIGHT` limitation blocks any
    clean-alpha representation; omission of its required disclosure blocks the
    run, while the disclosed limitation alone never weakens or substitutes for
    controllable leakage tests.
15. Dormant mode creates no datasets, credentials, provider calls, compute
    jobs, product-code dependencies, schedules, or execution integration.

## Evidence and typed human-approval gates

| Gate ID | Approval scope | Required evidence | Exact `approval_type` | Required authority | Fail-closed result |
|---|---|---|---|---|---|
| `S25-G01-DELEGATED-ARTIFACT` | S25 spec artifact | Exact current spec-file SHA-256, fresh clean Sol xhigh review, source hashes, review round, timestamp, and persisted evidence path | `DELEGATED_ARTIFACT_APPROVAL` | Delegated authority under the activated goal | Draft remains unapproved. No approval is recorded here. |
| `S25-G02-E05-ACTIVATION` | E-05 | Current TRUE E-05 predicate digest, evidence, activation record, and matching canonical human-resolution digest | `GOAL_OR_PROCESS_AUTHORIZATION` | Competent human authorized for exact E-05 `ACTIVATE_DEFERRED` scope | Quant validation remains dormant. |
| `S25-G03-E10-ACTIVATION` | E-10 | Current TRUE E-10 predicate digest, evidence, activation record, and matching canonical human-resolution digest | `GOAL_OR_PROCESS_AUTHORIZATION` | Competent human authorized for exact E-10 `ACTIVATE_DEFERRED` scope | Historical replay remains dormant. |
| `S25-G04A-PROTOCOL-ANALYST` | One activated register | Frozen hypothesis, universe, features, target, splits, metrics, trial budget, and stops; E-05 also requires fees, liquidity, and benchmark, while non-performance E-10-only scope requires evidenced `NOT_APPLICABLE` | `ANALYST_ACCEPTANCE` | Competent analyst | Run does not start. |
| `S25-G04B-PROTOCOL-DOMAIN` | One activated register | Domain validity of hypothesis, universe, features, target, and benchmark | `DOMAIN_EXPERT_ACCEPTANCE` | Competent domain expert | Run does not start. |
| `S25-G05A-DATA-RIGHTS` | One activated register | Dataset-specific permitted use, retention, transformation, and derived-output decision | `DATA_RIGHTS_APPROVAL` | Competent data-rights authority | Dataset is excluded and affected run is blocked. |
| `S25-G05B-PROVIDER` | One activated register | Provider authorization is required for the exact dataset/use; included when the policy predicate is `TRUE` | `PROVIDER_AUTHORIZATION` | Competent provider authority | Dataset is excluded and affected run is blocked. |
| `S25-G05C-LEGAL` | One activated register | Legal adjudication is required for the exact dataset/use; included when the policy predicate is `TRUE` | `LEGAL_REVIEW` | Competent legal authority | Dataset is excluded and affected run is blocked. |
| `S25-G06A-BUDGET` | One activated register | Data, compute, trial, elapsed-time, and analyst-review spend | `BUDGET_APPROVAL` | Competent budget authority | Resource-consuming work does not start. |
| `S25-G06B-CAPACITY` | One activated register | Data, compute, and analyst-review capacity | `CAPACITY_COMMITMENT` | Competent capacity owner | Resource-consuming work does not start. |
| `S25-G07A-RESULT-ANALYST` | One activated register | Full trial registry, leakage reports, disclosures, uncertainty, failed/blocked runs, and limitations | `ANALYST_ACCEPTANCE` | Competent analyst | Result remains unaccepted evidence. |
| `S25-G07B-RESULT-DOMAIN` | One activated register | Domain interpretation of results and limitations | `DOMAIN_EXPERT_ACCEPTANCE` | Competent domain expert | Result remains unaccepted evidence. |
| `S25-G08A-PRODUCTION` | One activated register | Exact proposed production scope and complete supporting evidence | `PRODUCTION_APPROVAL` | Competent production authority | No production use. |
| `S25-G08B-PRODUCTION-REGULATORY` | One activated register | Regulatory decision for the exact proposed production scope | `REGULATORY_REVIEW` | Competent regulatory authority | No production use. |
| `S25-G08C-PRODUCTION-CAPACITY` | One activated register | Operational capacity and recovery commitment | `CAPACITY_COMMITMENT` | Competent capacity owner | No production use. |
| `S25-G08D-PRODUCTION-OWNER` | One activated register | Named operational owner and escalation commitment | `NAMED_OWNER_COMMITMENT` | Competent named owner | No production use. |
| `S25-G08E-SECURITY-EXCEPTION` | One activated register | Exact exception evidence; included only when production requires a security exception | `SECURITY_EXCEPTION` | Competent security authority | No production use. |
| `S25-G09A-DISTRIBUTION` | One activated register | Exact content/version, audience, and purpose | `DISTRIBUTION_APPROVAL` | Competent distribution authority | No external or personalized distribution. |
| `S25-G09B-DISTRIBUTION-LEGAL` | One activated register | Legal decision for exact content/version and audience | `LEGAL_REVIEW` | Competent legal authority | No external or personalized distribution. |
| `S25-G09C-DISTRIBUTION-REGULATORY` | One activated register | Regulatory decision for exact content/version and audience | `REGULATORY_REVIEW` | Competent regulatory authority | No external or personalized distribution. |

`S25-G01` and `S25-G07` through `S25-G09` are not listed in
`required_approval_ids`. G01 has spec-artifact scope, not an E-05 or E-10
register scope; G07 through G09 are separate report/downstream requirements.
One approval record satisfies one runtime requirement only and is scoped to one
named register and the frozen protocol body digest. Applicability predicates that are
`UNKNOWN` block the affected dataset or production scope. Operational authority
is represented without a new type by the separate `CAPACITY_COMMITMENT` and
`NAMED_OWNER_COMMITMENT` requirements above. The closed vocabulary has no
model-risk approval type. S25 therefore MUST NOT map model-risk authority to a
nearby type: proposed production remains blocked until the goal vocabulary and
affected requirements are reconciled through a distinct active
`RECONCILE_AUTHORITY` canonical human resolution, this draft is amended, and a
fresh review confirms the new one-to-one requirement. Delegated artifact
approval does not satisfy E-05/E-10 activation, analyst, domain, rights, legal,
provider, budget, capacity, security, operations, model-risk, regulatory,
production, or distribution authority.

Every `S25-G07` scope additionally names the exact `report_id` and
`report_body_sha256` reviewed. Every `S25-G08` requirement additionally binds
that accepted report and the exact proposed-production artifact ID and content
digest. Every `S25-G09` requirement additionally binds the exact distributed
content digest, audience, and purpose. None of these approvals changes the
immutable report body; changed report, production, or distributed bytes require
a new scoped requirement and record.

## Acceptance tests and verification

Before activation:

1. Structural tests prove there is no S25 dataset build, provider route,
   credential, compute job, schedule, runtime dependency, or execution hook.
2. E-05-only approval fails an E-10 operation and E-10-only approval fails an
   E-05 operation. False, unknown, stale, expired, or mismatched predicates;
   changed predicate preimages; unresolved metrics; mismatched protocol-body or
   resolution digests; superseded/revoked resolutions; reused approval records;
   and a register-scope/activation-map key mismatch fail before any operation.
3. E-05 with E-10 `Deferred`, `Open`, `In progress`, `Rejected`, missing, or
   digest-stale is blocked. Only current `Accepted` bindings for both `B-09` and
   E-10 satisfy E-05 dependencies; selecting E-05 alone still cannot start an
   E-10 replay operation.
4. Negative binding fixtures mutate a protocol-body field without replacing
   `protocol_body_sha256`, bind an activation or operational approval to a
   different body digest, and include either envelope in the canonical body
   preimage; every fixture is rejected. Changing only an envelope leaves the
   body digest stable but still fails unless the replacement envelope is
   current and matches the frozen body and single-register scope exactly.
5. Negative artifact-scope fixtures omit or alter the reviewed spec-file
   SHA-256, bind `S25-G01` to a runtime protocol or to E-05/E-10, place G01 or
   any `S25-G07` through `S25-G09` requirement in `required_approval_ids`,
   pre-create a report/downstream requirement without its content digest, or use
   a runtime approval to satisfy G01; every fixture is rejected without
   affecting either register's dormant state.

After the applicable activation:

6. Synthetic temporal fixtures catch every minimum `LeakageFinding` category,
   including revised filings, post-cutoff index membership, late source
   availability, future corporate actions, overlapping horizons, and repeated
   holdout access. Model-weight limitation output is classified
   `UNCONTROLLABLE_MODEL_WEIGHT` and remains separate from controllable
   store/tool failures.
7. Advancing a source's availability past the frame cutoff removes it from the
   decision frame; substituting a present-day snapshot is rejected.
8. Dataset and replay rebuilds from identical immutable inputs and code produce
   identical hashes; revisions create new versions and preserve old results.
9. Split tests enforce chronology, purge, embargo, and outcome isolation; no
   target-derived transformation enters features.
10. Trial-registry tests account for every attempted run, including failures,
   manual interruptions, budget stops, and null results.
11. Missing rights, lineage, temporal proof, identity, corporate-action version,
   or activation evidence yields `BLOCKED`, not imputation or silent exclusion.
12. For E-05, missing or silently defaulted fees, liquidity assumptions, or
    benchmark yields `BLOCKED`. Valid E-05 reports disclose all three and
    reproduce their point-in-time calculations and benchmark-relative results;
    non-performance E-10-only reports prove `NOT_APPLICABLE` rather than omit
    them.
13. Historical LLM fixtures require the separate model-weight disclosure and
    reject every clean-alpha representation while retaining all controllable
    store/tool tests. A no-LLM fixture requires evidenced `NOT_APPLICABLE`.
14. Reports state denominators, uncertainty, limitations, all leakage findings,
    and the exact narrow meaning of `PASS`; they make no clean-alpha,
    production, causal, trading, or recommendation claim. Requirement and
    record IDs are one-to-one and every runtime scope matches
    `protocol_body_sha256` and exactly one selected register. Negative fixtures
    change report bytes after `S25-G07`, reuse one report approval for another
    report, and change proposed-production or distributed content after
    `S25-G08` or `S25-G09`; each invalidates the affected approval without
    altering prior immutable evidence.

Verification evidence MUST contain exact commands, exit statuses, immutable
input/output hashes, protocol and code versions, validator output, timestamps,
and reviewer identity. Conversation text, agent summaries, and matching
ledger-authored labels are not proof.

## Dependencies

- Exact register dependencies `E-05 -> B-09`, `E-05 -> E-10`, and
  `E-10 -> C-15`; register authority; and a valid activation for each selected
  operation, E-05 and/or E-10.
- Product/distribution and source-rights boundaries (S01–S02).
- Golden-set, failure-taxonomy, success-metric, budget, and capacity controls
  (S07–S08).
- Point-in-time capture and immutable documents (S09).
- Source-of-truth, evidence-package, retention, run-manifest, cutoff, and
  reproducibility contracts (S10–S11).
- Observation/fact identity, revision, schema, claim, and evidence-validation
  contracts (S12–S13).
- Registered deterministic compute and calculation traces (S16).
- Entity/security identity, universe snapshots, and corporate actions
  (S17–S18).

Lack of historical point-in-time evidence is a substantive blocker, not a data
engineering inconvenience. Independent scopes may continue only when their
dependency and activation cones do not intersect the blocker.

## Deferred activation guard

Until the corresponding component is validly activated and its exact register
dependencies are accepted, permitted work is limited to authoring, reviewing,
and structural verification of this dormant
contract and non-executable synthetic fixtures. No source acquisition, dataset
construction, historical replay, provider call, compute experiment, product
code, runtime configuration, or execution integration is allowed. E-10 may
activate and reach `Accepted` while E-05 remains dormant. E-05 cannot activate
while E-10 remains dormant; after E-10 is accepted as an E-05 dependency, an
E-05-only operation still does not authorize a new E-10 historical replay.
Neither activation activates E-02, E-03, or E-04.

## Amendment gate

No evidence-derived provisional amendment gate is assigned to S25 in the
goal's amendment table. Any change to this contract still requires source
reconciliation, disposition reconciliation for M-4 and 6.5, the capped
review/fix policy, a fresh clean Sol xhigh review, and delegated artifact
approval. Activation alone is neither amendment nor approval.
