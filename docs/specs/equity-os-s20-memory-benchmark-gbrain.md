# S20 — Memory benchmark, GBrain due diligence, and adoption decision

**Status: DRAFT — AWAITING FRESH SOL XHIGH REVIEW**

## Contract purpose

This specification owns D-02, D-04, and D-05: a fair current-scale three-arm memory benchmark, GBrain repository/dependency due diligence, and the resulting present adoption decision. S20 is dormant-only. It defines activation predicates, evidence, evaluation, and fail-closed behavior; it does not activate any row, install GBrain, run a benchmark, or approve adoption.

## Authority and ownership

The v2 decision register is authoritative for operational gates. The activated goal supplies the exact S20 mapping and dormant-only program control. The disposition report explains R-1 and 6.4 without overriding the register.

| Source | Exact source text | Contract effect |
|---|---|---|
| Goal, Exact 25-spec row | `S20 | Memory benchmark, GBrain due diligence, and adoption decision | docs/specs/equity-os-s20-memory-benchmark-gbrain.md | D-02, D-04, D-05 | R-1, 6.4` | S20 is the sole primary spec owner for D-02, D-04, and D-05. |
| Register authority rule | “The wording in this register is authoritative for implementation gates. Narrative reviews explain rationale but do not override this register.” | Status, dependencies, and acceptance text below are controlling. |
| D-02 | “Critical | Run current-scale three-arm memory benchmark | All arms receive the same authoritative prior artifacts; compare no persistent memory/manual context assembly, Git/Markdown/SQL retrieval, and GBrain on longitudinal tasks, retrieval misses, contradiction/staleness detection, analyst time, unsupported claims, latency, cost, and operations; result governs current adoption only; re-evaluation triggers are precommitted | C-05, D-01, D-04 | Deferred” | Dormant benchmark contract. |
| D-04 | “High | Verify GBrain repository and dependency posture | Repository, license, maintainers, activity, tests, security, export path, and pinned version recorded | — | Deferred” | Dormant due-diligence contract. |
| D-05 | “High | Decide GBrain adoption | Adopt only if current-scale benchmark benefit exceeds operational and upgrade burden; a non-adoption result does not prevent later trigger-based reevaluation | D-02, D-04 | Deferred” | Dormant, evidence-bound adoption decision. |
| R-1 disposition | “Disposition: Reject.” | The proposal to cancel D-02 is rejected; S20 retains it. |
| R-1 | “A result showing no advantage at that scale is not a false negative; it is a valid reason not to adopt the dependency yet.” | Non-adoption is a valid present decision. |
| R-1 | “The arms must be fair: each receives access to the same authoritative prior artifacts, while the benchmark varies how context is persisted, retrieved, and assembled.” | Artifact parity and intervention isolation are mandatory. |
| R-1 | “state that the result governs current adoption only;” | Decision scope is current scale/workload only. |
| R-1 | “define minimum query/task coverage and avoid a ceiling-only test set;” | Coverage must be precommitted and discriminating. |
| R-1 | “include operational burden, not just retrieval quality;” | Adoption utility includes operations and upgrade burden. |
| R-1 | “instrument retrieval misses and contradictions caught later by humans;” | Human-discovered miss telemetry is mandatory. |
| R-1 | “predefine re-evaluation triggers based on corpus size, cross-company graph needs, and observed miss rate.” | Future reconsideration is threshold-driven. |
| 6.4 | “D-02 answers a present adoption question” | Historical result cannot claim permanent engine superiority. |
| 6.4 | “A small-corpus benchmark may correctly show that a simpler store is sufficient. Future triggers should reopen the question; the benchmark should not be cancelled on the assumption that a larger future corpus might behave differently.” | Simpler-store selection and future reopening are both valid. |

## Activation classification

| Register ID | Activation source Status | Program disposition now | Allowed delivery behavior |
|---|---|---|---|
| D-02 | `Deferred` | `CONDITIONAL_UNACTIVATED` | Preserve benchmark design and activation evidence; do not run or claim results. |
| D-04 | `Deferred` | `CONDITIONAL_UNACTIVATED` | Preserve due-diligence checklist and activation evidence; do not install, inspect through credentials, or approve a dependency. |
| D-05 | `Deferred` | `CONDITIONAL_UNACTIVATED` | Preserve decision rule; do not adopt or reject GBrain. |

Because every owned row was Deferred at activation, S20 may not enter `PLANNED`, `IMPLEMENTING`, or `VERIFIED` until the exact row being advanced is validly activated. One row's activation does not activate the others.

## Scope

S20 specifies:

- three-arm benchmark parity, workload, metrics, instrumentation, analysis, and result scope;
- GBrain identity, version, repository, licensing, maintenance, test, security, portability, and export due diligence;
- a precommitted, evidence-bound current adoption decision rule;
- a non-adoption path and measurable future reevaluation triggers;
- typed human gates for activation, external service/credentials/purchase, exceptions, and adoption.

## Non-goals

S20 does not:

- implement the S19 `MemoryStore` interface or canonical promotion transaction;
- assume GBrain exists at a particular repository, version, deployment model, or license before due diligence;
- grant repository, service, credential, purchase, legal, rights, security-exception, or adoption approval;
- vary source artifacts, cutoff, task definitions, or evaluator rules between benchmark arms;
- treat more retrieved text as better retrieval, or treat claim count as independent samples;
- turn a current-scale result into a permanent rejection or adoption;
- make GBrain mandatory, weaken SQL/evidence authority, or bypass human memory promotion.

## Benchmark interface and data contracts

### Benchmark manifest

Each run is registered before execution with:

| Field group | Required fields |
|---|---|
| Identity | `benchmark_id`, `protocol_version`, `created_at`, `owner`, `decision_scope=CURRENT_SCALE_ONLY` |
| Frozen workload | ordered `task_ids`, longitudinal period coverage, task class, company, cutoff, expected evidence package, difficulty label, ceiling-risk label |
| Artifact parity | one `authoritative_artifact_manifest_sha256`, artifact IDs/hashes, cutoff, and allowed transforms shared by all arms |
| Arms | exactly `MANUAL_CONTEXT`, `GIT_MARKDOWN_SQL`, and `GBRAIN`; adapter version/config; identical task and artifact references |
| Models/tools | exact model, prompt, tool, code, runtime, seed/replay class, and cutoff-capability declarations |
| Metrics | metric definitions, units, aggregation level, missing-data rule, correction rule, and precommitted decision threshold |
| Operations | setup, ingestion, index/rebuild, backup, restore, upgrade, export, incident, latency, and cost collection rules |
| Human review | blinded/randomized presentation where feasible, analyst timing protocol, claim dispositions, later-miss capture window, and correction categories |
| Triggers | corpus-size, cross-company-graph-need, observed-miss-rate, contradiction/staleness, and operational-burden thresholds with evaluation cadence |

The manifest and every output are content-hashed. Any post-registration protocol change creates a new version and cannot be backfilled into an earlier result.

### Arms and controlled intervention

1. `MANUAL_CONTEXT`: no persistent memory; the analyst or workflow assembles context from the same frozen authoritative artifacts.
2. `GIT_MARKDOWN_SQL`: retrieval/assembly uses the repository, Markdown, and SQL approach behind the S19 contract.
3. `GBRAIN`: a pinned, due-diligenced candidate version is used only through an S19-compatible adapter.

The independent variable is how context is persisted, retrieved, and assembled. Source artifacts, knowledge cutoff, questions, task order allocation, models, tool permissions, scoring rubric, analyst role, and downstream approval policy are held constant or explicitly counterbalanced. Arm-specific preprocessing that changes accessible evidence fails parity.

### Minimum workload coverage

The activated benchmark must contain pre-labeled, longitudinal tasks spanning at least:

- direct retrieval of an earlier observed Fact;
- management-commitment creation, modification, due status, and outcome;
- later issuer restatement or correction;
- contradicted or superseded thesis content;
- cutoff-sensitive retrieval where a later record must be excluded;
- cross-period synthesis requiring more than one prior artifact;
- missing evidence where abstention is correct;
- provenance/source-jump recovery;
- deletion/export/restore behavior relevant to engine portability;
- non-ceiling cases established by pilot evidence before scored execution.

The exact count is evidence-derived and frozen in the activated manifest. A tiny all-easy set, an all-ceiling set, or tasks selected after seeing arm results is invalid.

### Metric contract

| Dimension | Required measurement |
|---|---|
| Task outcome | rubric-bound correctness, unsupported claims, correct abstention, and source/citation correctness |
| Retrieval | eligible target retrieved, rank, retrieval miss, irrelevant retrieval, cutoff violation, and provenance completeness |
| Memory quality | stale conclusion surfaced, contradiction surfaced, supersession respected, and human-discovered miss/contradiction during the capture window |
| Analyst economics | total minutes per task/report, context assembly, source location, correction, and approval; clustered results reported by task/report/company without false independence claims |
| Runtime | end-to-end and retrieval latency, failures, retries, rebuild time, and availability incidents |
| Cost | model/tool/provider/infrastructure cost under one declared accounting method |
| Operations | setup, maintenance, upgrade, backup/restore, export, debugging, dependency/security response, and adapter burden |

Missing results remain missing and are disclosed; they are never silently assigned neutral or winning values. The report includes per-task results and aggregation, task/arm failures, protocol deviations, uncertainty, and workload limits.

## GBrain due-diligence contract

Before D-04 can be accepted, the evidence package must record:

1. exact canonical repository URL and immutable revision/tag;
2. license files and the competent interpretation needed for intended use;
3. maintainers, release/activity history, issue/patch posture, and abandonment risk;
4. install/runtime dependencies, supported platforms, transitive dependency inventory, and reproducible build or pinning evidence;
5. first-party tests, independently rerun results, coverage limitations, and upgrade/migration tests;
6. trust boundaries, data egress, telemetry, secrets, authentication, authorization, dependency vulnerabilities, and unresolved security findings;
7. backup, deletion, full-fidelity export, restore into an independent representation, and exit/migration path;
8. deployment topology, operational ownership, capacity, costs, external services, credentials, and purchase needs;
9. S19 adapter mapping, semantic gaps, and any engine-specific feature that would contaminate arm parity.

Unknown or unsupported facts are recorded as unresolved. No assumed Temporal, Partner, Bodha, homelab, PostgreSQL, repository, or deployment posture may enter the decision as verified evidence.

## Adoption decision contract

D-05 may decide only `ADOPT_CURRENT_SCALE`, `DO_NOT_ADOPT_CURRENT_SCALE`, or `NO_DECISION_INSUFFICIENT_EVIDENCE`.

`ADOPT_CURRENT_SCALE` is allowed only when:

- D-02 and D-04 have current accepted evidence;
- the precommitted benchmark threshold shows material workflow benefit over the simpler eligible arm on the declared primary outcomes;
- unsupported claims, cutoff violations, provenance loss, or promotion-authority violations do not worsen beyond precommitted safety bounds;
- operational and upgrade burden, exportability, security posture, cost, capacity, and ownership are acceptable under separately evidenced gates;
- every required non-delegated approval is current and exact-scope.

`DO_NOT_ADOPT_CURRENT_SCALE` is valid when a simpler eligible arm is sufficient or GBrain's measured benefit does not exceed operational and upgrade burden. It is not `Rejected` forever and does not disable triggers. `NO_DECISION_INSUFFICIENT_EVIDENCE` is mandatory for parity failure, incomplete due diligence, missing primary outcomes, post-hoc thresholds, unresolved load-bearing findings, or stale evidence.

The decision record contains exactly `outcome`, `manifest_sha256`, `benchmark_result_sha256`, `due_diligence_sha256`, `decision_rule_version`, `decision_rule_evaluation_sha256`, `actor`, `authority`, `decision_scope`, `candidate_revision`, `deployment_operating_scope`, `timestamp`, `rationale`, `dissent`, `limitations`, `reevaluation_triggers`, `approval_record_id`, `resolution_decision_id`, and `resolution_content_sha256`. The last three fields are null for `NO_DECISION_INSUFFICIENT_EVIDENCE` and required for a conclusive outcome. `decision_record_sha256` is lowercase SHA-256 of the goal-defined canonical JSON object containing exactly those fields and excluding `decision_record_sha256` itself. `decision_rule_evaluation_sha256` is computed before human decision from canonical JSON containing exactly `protocol_version`, `decision_rule_version`, `decision_scope`, `candidate_revision`, `manifest_sha256`, `benchmark_result_sha256`, `due_diligence_sha256`, `primary_outcomes`, `precommitted_thresholds`, `safety_bounds`, `measured_operations_upgrade_burden`, `unresolved_limitations`, and `candidate_outcome`.

### Controlled source-status and reevaluation transitions

After its own valid activation, D-05 evaluates evidence while `Open` or `In progress`. `ADOPT_CURRENT_SCALE` and `DO_NOT_ADOPT_CURRENT_SCALE` are both conclusive completion of the register instruction to decide adoption; either may support `In progress → Accepted` and delivery `VERIFIED` only after complete proof and one current exact-scope `PRODUCT_OWNER_DECISION`. The matching approval record must use `authority_source=HUMAN_RESOLUTION` and copy one active canonical `SATISFY_APPROVAL` resolution binding D-05, the chosen outcome, `decision_scope=CURRENT_SCALE_ONLY`, the candidate revision, the manifest/result/due-diligence hashes, the decision-rule evaluation digest, and the exact deployment/operating scope. The decision record's actor, authority, timestamp, approval-record ID, resolution decision ID, and resolution content digest must equal that approval/resolution chain. A positive outcome grants no separate installation, purchase, production, credential, service, legal, rights, budget, capacity, owner, or security authority.

`NO_DECISION_INSUFFICIENT_EVIDENCE` is non-conclusive: it cannot support D-05 `Accepted`, delivery `VERIFIED`, or `gate_result=PASS`. D-05 retains its legal current active source/delivery state with an explicit blocker until new valid evidence is available; it does not skip or regress a source Status.

A later D-02 rerun, D-04 due-diligence refresh, or D-05 reconsideration after the affected row is `Accepted` is blocked until a separate active canonical `REOPEN_ACCEPTED` human resolution for that exact row/scope is followed by source reconciliation of `Accepted → Open`. A new GBrain revision or a replacement/refreshed due-diligence package advances D-04 and therefore requires this D-04 transition; it cannot replace accepted D-04 evidence in place. If a reevaluation advances more than one accepted row, each row requires its own resolution and reconciliation. The trigger crossing and original evidence are inputs to those human decisions; neither changes source Status, starts work, nor invalidates the preserved original result. New due-diligence or scored work then uses a new package or manifest/protocol version and follows the ordinary activation/dependency/approval sequence from each reopened state.

## Invariants and fail-closed behavior

1. Exactly three declared arms receive the identical authoritative artifact manifest and cutoff.
2. GBrain is accessed only through the engine-neutral S19 contract; product callers do not gain engine-specific dependencies from the benchmark.
3. D-04 evidence is completed before D-02 begins and both D-02 and D-04 precede D-05.
4. Protocol, thresholds, task coverage, and primary outcomes are frozen before scored results are visible.
5. Later human-discovered retrieval misses and contradictions remain attributable to the originating arm/run.
6. No retrieval output bypasses evidence validation, epistemic labels, cutoff enforcement, or human promotion.
7. A benchmark failure, due-diligence unknown, parity breach, stale hash, missing export, or unresolved safety finding produces `NO_DECISION_INSUFFICIENT_EVIDENCE`.
8. A non-adoption decision preserves all trigger definitions and their cadence.
9. A trigger crossing opens reevaluation consideration; it does not itself adopt, install, purchase, or activate GBrain.
10. Results apply only to the measured current scale, workload, versions, and operating boundary.
11. D-02, D-04, and D-05 implementation/delivery references remain absent while their individual Status is Deferred.
12. Both conclusive D-05 outcomes require an exact-scope current product-owner resolution and complete D-05 as `Accepted`; insufficient evidence completes neither source acceptance nor delivery verification.
13. Accepted D-02, D-04, or D-05 work cannot restart, and its accepted proof cannot be replaced, until that exact row has its own valid `REOPEN_ACCEPTED` resolution and reconciled `Accepted → Open` source transition.

## Deferred activation guards

Each row has its own exact typed predicate and its own component-local `FILE_BYTES` activation-evidence object.

The D-04 predicate ID is exactly `AP-D04-GBRAIN-DUE-DILIGENCE-NEED`. Its expression is exactly:

```json
{"op":"COMPARE","metric_id":"MTR-D04-GBRAIN-DUE-DILIGENCE-REQUIRED","comparator":"EQ","expected":true}
```

The D-02 predicate ID is exactly `AP-D02-CURRENT-SCALE-BENCHMARK-READY`. Its expression is exactly:

```json
{"op":"ALL","args":[{"op":"COMPARE","metric_id":"MTR-D02-C05-SOURCE-STATUS","comparator":"EQ","expected":"Accepted"},{"op":"COMPARE","metric_id":"MTR-D02-D01-SOURCE-STATUS","comparator":"EQ","expected":"Accepted"},{"op":"COMPARE","metric_id":"MTR-D02-D04-SOURCE-STATUS","comparator":"EQ","expected":"Accepted"},{"op":"COMPARE","metric_id":"MTR-D02-BENCHMARK-READY","comparator":"EQ","expected":true}]}
```

The D-05 predicate ID is exactly `AP-D05-GBRAIN-ADOPTION-DECISION-READY`. Its expression is exactly:

```json
{"op":"ALL","args":[{"op":"COMPARE","metric_id":"MTR-D05-D02-SOURCE-STATUS","comparator":"EQ","expected":"Accepted"},{"op":"COMPARE","metric_id":"MTR-D05-D04-SOURCE-STATUS","comparator":"EQ","expected":"Accepted"},{"op":"COMPARE","metric_id":"MTR-D05-ADOPTION-DECISION-READY","comparator":"EQ","expected":true}]}
```

Every metric uses `source_kind=EVIDENCE_JSON` and `register_ids=[]`. Metrics for one predicate name the same current row-local evidence object and retain the declared order shown in that predicate's expression.

| Metric ID | Type | Stable JSON pointer and binding |
|---|---|---|
| `MTR-D04-GBRAIN-DUE-DILIGENCE-REQUIRED` | `BOOLEAN` | `/memory/gbrain_due_diligence_required`; the D-04 evidence names the candidate revision, intended use/deployment scope, due-diligence owner/capacity, and current evidence hashes. D-04 has no D-01 or other register dependency. |
| `MTR-D02-C05-SOURCE-STATUS` | `STRING` | `/memory/c05_source_status`; the D-02 evidence binds `register_id="C-05"`, the live register file SHA-256, the exact C-05 row-span digest, and current acceptance-proof references. |
| `MTR-D02-D01-SOURCE-STATUS` | `STRING` | `/memory/d01_source_status`; the D-02 evidence binds `register_id="D-01"`, the live register file SHA-256, the exact D-01 row-span digest, and current acceptance-proof references. |
| `MTR-D02-D04-SOURCE-STATUS` | `STRING` | `/memory/d04_source_status`; the D-02 evidence binds `register_id="D-04"`, the live register file SHA-256, the exact D-04 row-span digest, and current acceptance-proof references. |
| `MTR-D02-BENCHMARK-READY` | `BOOLEAN` | `/memory/benchmark_ready`; the D-02 evidence binds the frozen workload candidate, parity-feasible artifact set, benchmark budget/capacity, metric/threshold draft, and D-04 evidence. |
| `MTR-D05-D02-SOURCE-STATUS` | `STRING` | `/memory/d02_source_status`; the D-05 evidence binds `register_id="D-02"`, the live register file SHA-256, the exact D-02 row-span digest, and current acceptance-proof references. |
| `MTR-D05-D04-SOURCE-STATUS` | `STRING` | `/memory/d04_source_status`; the D-05 evidence binds `register_id="D-04"`, the live register file SHA-256, the exact D-04 row-span digest, and current acceptance-proof references. |
| `MTR-D05-ADOPTION-DECISION-READY` | `BOOLEAN` | `/memory/adoption_decision_ready`; the D-05 evidence binds the current benchmark and due-diligence packages, decision-rule evaluation, limitations, proposed deployment scope, and approval inventory. |

For every source-status metric, the producer and validator independently parse the live register and copy its exact Status; a ledger label or unbound status string is invalid. `REGISTER_STATUS` is not used because its boolean cannot distinguish `Open`, `In progress`, and `Accepted`. `gbrain_due_diligence_required`, `benchmark_ready`, and `adoption_decision_ready` are the stable predicate pointers for this contract and cannot be silently renamed.

Each metric names its current evidence reference, or `null` only before evidence exists, and its predeclared UTC expiry. Each predicate's `evaluation_sha256` is lowercase SHA-256 of the goal-defined canonical JSON object containing exactly `predicate_id`, `expression`, `metrics`, `resolved_values`, `digest_sources`, `result`, and `evaluated_at`; `expression` is the exact tree above, `metrics` retain their declared order, and the resolved-value and digest-source objects are keyed by metric ID. A missing or wrong-typed value, `FALSE`, `UNKNOWN`, any dependency Status other than exact `Accepted`, expired evidence, or a stale source/evidence digest prevents activation.

A recomputed `TRUE` still requires a distinct active canonical human resolution with decision `ACTIVATE_DEFERRED`, exact row scope, competent product authority, evidence hashes, and one matching `PRODUCT_OWNER_DECISION`. The activation record and approval record must copy the same canonical resolution decision ID/content digest and bind that row's fixed predicate ID plus current `evaluation_sha256`. Neither this draft, a coordinator, another row's activation, a trigger crossing, nor a mismatched resolution supplies that authority.

## Evidence and typed human-approval gates

| Gate | Evidence required | Approval required | Fail-closed result |
|---|---|---|---|
| S20 artifact approval | Current spec hash and persisted clean fresh-context Sol xhigh review | One `DELEGATED_ARTIFACT_APPROVAL` under delegated goal authority | Status remains draft. This file claims no approval. |
| Each Deferred activation | Current typed predicate/evidence and matching canonical resolution digest | A distinct `PRODUCT_OWNER_DECISION` for `ACTIVATE_DEFERRED` and exact row scope | That row remains dormant. |
| D-04 acceptance | Complete due-diligence package, rerun tests, license/security/export evidence, and resolved load-bearing findings | `LEGAL_REVIEW`, `DATA_RIGHTS_APPROVAL`, `EXTERNAL_SERVICE_APPROVAL`, or `CREDENTIAL_ACCESS_APPROVAL` only when the evaluated posture crosses that boundary; any exception requires `SECURITY_EXCEPTION` | D-04 cannot be Accepted. |
| D-02 execution | Frozen manifest and task/artifact parity; budget/capacity evidence; D-04 accepted | `BUDGET_APPROVAL`, `CAPACITY_COMMITMENT`, `PURCHASE_AUTHORIZATION`, `EXTERNAL_SERVICE_APPROVAL`, or `CREDENTIAL_ACCESS_APPROVAL` when the actual benchmark requires them | Benchmark cannot start or affected arm is invalid. |
| D-05 conclusive decision | Current D-02/D-04 evidence, precommitted rule evaluation, exact outcome, and exact deployment/operations/exit scope | One `PRODUCT_OWNER_DECISION` for the exact `ADOPT_CURRENT_SCALE` or `DO_NOT_ADOPT_CURRENT_SCALE` outcome plus all boundary-triggered approvals applicable to that outcome | Decision is `NO_DECISION_INSUFFICIENT_EVIDENCE`; D-05 cannot become Accepted or VERIFIED. |
| Accepted-row reevaluation | Crossed-trigger evidence, original result/decision or due-diligence hashes, proposed new scope/candidate revision, and current source proof | One separate active `REOPEN_ACCEPTED` human resolution and source reconciliation for each accepted D-02, D-04, or D-05 row to be advanced | Consideration may be recorded, but due-diligence refresh, rerun, or reconsideration cannot start. |

Conditional approval types are not presumed satisfied. The approval inventory must explicitly prove whether each boundary applies. Automated Sol review may approve the artifact under delegated authority and may provide technical/security-review evidence; it cannot grant product adoption, legal/rights sufficiency, budget, capacity, credentials, purchase, external-service operation, production use, or a security exception.

## Acceptance tests and verification

After valid activation of the applicable rows, verification must mechanically prove:

1. Manifest validation rejects any run without exactly three arms, a shared artifact hash/cutoff, frozen thresholds, or complete task coverage.
2. A parity canary exposed to one arm only invalidates the run.
3. Post-cutoff fixtures are excluded identically in all arms and any leakage is a safety failure.
4. Known retrieval, staleness, contradiction, supersession, provenance, and abstention fixtures exercise every required task class.
5. A pilot ceiling set cannot be promoted to the scored set without pre-scored replacement and a new manifest version.
6. Arm assignment/evaluation is randomized or counterbalanced as declared and reruns reproduce deterministic parts under the registered replay class.
7. Human-discovered misses entered during the capture window update the correct arm/run metrics without rewriting raw results.
8. Cost and operational measurements include setup, maintenance, rebuild, backup/restore, export, upgrade, and incident effort.
9. GBrain identity, license, revision, dependency, test, security, and export evidence hashes match the evaluated candidate.
10. Export/restore reconstructs the required S19 logical records without a hidden GBrain-only dependency.
11. The decision evaluator returns each of the three closed outcomes for positive, insufficient, and simpler-store-sufficient fixtures.
12. Positive- and simpler-store-sufficient fixtures produce their respective conclusive outcome but cannot advance D-05 without a current exact-outcome `PRODUCT_OWNER_DECISION`; with the matching resolution/record and complete proof, each advances D-05 through `In progress → Accepted` and delivery `VERIFIED`.
13. An insufficient-evidence fixture cannot produce D-05 `Accepted`, `VERIFIED`, or `PASS`, with or without a nearby, wrong-outcome, stale, expired, revoked, or digest-mismatched approval.
14. A crossed-trigger fixture records consideration without changing adoption or source state; when D-02, D-04, or D-05 is already Accepted, any affected refresh/rerun/reconsideration remains blocked until that exact row has a current `REOPEN_ACCEPTED` resolution and reconciled `Accepted → Open` transition. A new candidate revision or replacement due-diligence package specifically proves the D-04 block and preserves its prior accepted evidence.
15. Decision-record validation recomputes the evaluation and record digest preimages and rejects any outcome, scope, evidence-hash, approval-record, resolution-ID, or resolution-digest mismatch.
16. Structural checks prove no owned Deferred row has implementation references or an active delivery state before its own valid activation.
17. Predicate fixtures recompute all three exact trees and prove that missing or wrong-typed values, `FALSE`, `UNKNOWN`, expired evidence, stale source/evidence digests, or any dependency Status of `Open`, `In progress`, `Deferred`, or `Rejected` cannot produce `TRUE`; only D-04's current required leaf or D-02/D-05's exact `Accepted` dependencies plus current readiness leaf can produce `TRUE` for that row.
18. A `TRUE` predicate still cannot activate its row when the activation resolution or approval is absent, stale, revoked, wrong-row, wrong-scope, or mismatched on predicate ID, evaluation digest, resolution decision ID, or resolution content digest.

Conversation summaries and agent reports are not proof. Each acceptance or decision must bind current command outputs, source/artifact hashes, typed approvals, and fresh content-bound reviews.

## Dependencies and handoffs

- D-04 has no register dependency but remains independently Deferred.
- D-02 depends on C-05 (S15), D-01 (S19), and D-04 (S20).
- D-05 depends on D-02 and D-04.
- S10 governs source-of-truth and retention boundaries; S11 governs cutoff/reproducibility; S19 owns the port and promotion semantics.
- Benchmark findings may inform S19 adapters but do not transfer D-01/D-03 ownership.
- No cross-reference transfers D-02, D-04, or D-05 primary ownership away from S20.

## Amendment gate

S20 is not one of the four goal-designated provisional contracts, so benchmark evidence does not silently rewrite this specification. A protocol, primary outcome, parity rule, due-diligence scope, adoption threshold, or trigger changed after registration requires a versioned amendment and fresh Sol xhigh review before new scored work; prior results retain their original contract. A current adoption or non-adoption decision is recorded as evidence under the existing contract, not treated as a permanent spec amendment. Any source-authority change requires the program's authority reconciliation before dependent work resumes.
