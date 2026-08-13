# S18 — MVP universe, analyst-review economics, and results-season throughput

Status: DRAFT — AWAITING FRESH SOL XHIGH REVIEW

## 1. Contract identity and authority

This specification is the sole primary specification for S18. It defines measurement and decision contracts for the Phase 0.5 review-economics evidence, Phase 1 universe selection, the Phase 1 economics gate, and peak results-season throughput. It does not select companies, set thresholds, commit capacity, or accept results.

| Program field | Exact value |
|---|---|
| Spec ID | S18 |
| Exact title | MVP universe, analyst-review economics, and results-season throughput |
| Exact path | docs/specs/equity-os-s18-universe-review-economics-throughput.md |
| Primary register IDs | B-04, C-01, C-12, C-18 |
| Disposition references | G-2, G-3, G-4, M-8, 6.1 |
| Activation classification | Active-only |
| Initial program disposition | REQUIRED_NOW |
| Amendment ownership | None |

Authority is applied in this order:

1. The v2 register controls live decision wording, dependencies, Status, and acceptance.
2. The Exact 25-spec program assigns B-04, C-01, C-12, and C-18 only to S18.
3. Dispositions G-2, G-3, G-4, M-8, and correction 6.1 constrain valid measurement claims.
4. A missing A-13 metric definition/threshold, A-12 capacity commitment, baseline, or competent human decision yields BLOCKED, never an inferred pass.

### Exact register ownership

The following cells reproduce the controlling register text exactly.

| Register ID | Blueprint phase | Priority | Decision or action | Required evidence / acceptance | Dependencies | Activation source status | Primary owner |
|---|---|---:|---|---|---|---|---|
| B-04 | Phase 0.5 | Critical | Measure analyst review economics without invalid percentiles | Record each report's total review time; claim count; per-claim disposition and time; source-locate and calculation-check time; accepted/edited/rejected/deferred counts; correction categories; no report-level P90 is used at n=3 | A-03, A-13, B-13 | Open | S18 — MVP universe, analyst-review economics, and results-season throughput |
| C-01 | Phase 1 | Critical | Expand to two or three core non-financial companies | Companies selected for disclosure quality, history, differing but manageable structures, and feasible peak-season review capacity | A-12 | Open | S18 — MVP universe, analyst-review economics, and results-season throughput |
| C-12 | Phase 1 | High | Set Phase 1 analyst-economics gate | Pre-agreed improvement is evaluated against per-company or matched-quarter baselines; workload-normalized metrics and total report time are reported; remaining confounds are disclosed | A-13, B-04 | Open | S18 — MVP universe, analyst-review economics, and results-season throughput |
| C-18 | Phase 1 | Medium | Validate results-season throughput | Peak-week reviews per analyst, claim/document volume, backlog age, and completion capacity for the Phase 1 universe are measured and accepted or mitigated | A-12, A-13, C-01 | Open | S18 — MVP universe, analyst-review economics, and results-season throughput |

### Disposition obligations

- G-2: report the three Phase 0.5 observed totals directly; record total analyst minutes for each report and descriptive claim-level disposition/time summaries; do not manufacture report-level P90 or statistical-significance claims at n=3.
- G-3: Phase 1 uses a manual baseline for each company or a matched historical quarter, workload-normalized measures, explicit complexity descriptors, and total report time without treating that total as a portable causal measure.
- G-4: Quarter 0 is the manual baseline/bootstrap and Quarters 1–3 are later assisted updates; do not reuse the same quarter for the primary manual-versus-assisted comparison. Counterbalance order where possible across companies; when it is infeasible, evidence the specific constraint and preserve the practice/order confound in the experiment log.
- M-8: track reports reviewable per analyst per week, peak-week document and claim volume, backlog age, percentage completed before the next material event, and capacity at the selected Phase 1 company count.
- Correction 6.1: claims are clustered within reports and companies. Claim-level telemetry supports operations and error analysis, not unsupported significance claims.

## 2. Scope

S18 specifies:

- the exact review-time and claim-disposition events needed for B-04;
- the Phase 1 company-selection record and evidence;
- baseline matching, workload normalization, complexity descriptors, and confound disclosure;
- an attempted cross-company counterbalancing plan, or evidence that counterbalancing is infeasible;
- a mechanically evaluated C-12 economics gate whose metric IDs and thresholds come from A-13;
- peak-week workload, backlog, timeliness, and mitigation evidence for C-18;
- typed human approvals, fail-closed rules, and verification fixtures.

### Non-goals

S18 does not:

- choose the discovery company or its four quarters, owned by S05;
- define the success-metric vocabulary or set thresholds, owned by S08/A-13;
- fabricate report-level percentiles, statistical independence, significance, causal effects, or generalized ROI from a small sample;
- select Phase 1 companies or commit analyst capacity without human authority;
- use accepted-unchanged rate as a standalone quality measure;
- evaluate financial-sector companies in the initial C-01 universe;
- activate any Deferred capability.

## 3. Data contracts

Every event is append-only, timestamped in UTC, attributed to one actor and workflow attempt, and bound to the report/evidence-package version. Corrections create new events; they do not overwrite elapsed time or dispositions.

### 3.1 UniverseCandidate

Contains candidate_id, company_id, non_financial classification and evidence, disclosure-quality rubric/version and score/evidence, history coverage, structural descriptors, source availability/rights, expected peak-week dates, expected document/claim volume, estimated analyst load, known conflicts, and decision status.

### 3.2 UniverseSelection

Contains selection_id/version, exactly two or three selected company_ids, rejected candidates with reasons, comparison of disclosure quality/history/structural diversity/manageability, peak-capacity scenario, A-12 capacity reference, human decision record, evidence references, and digest.

The selection must not include the discovery company merely to improve measured economics. If it does include that company for a justified product reason, familiarity is an explicit confound and cannot serve as the only Phase 1 comparison.

### 3.3 ReviewSession

Contains review_session_id, report_id/version, company_id, quarter, workflow_mode MANUAL or ASSISTED, analyst_id, started_at, ended_at, pause intervals with reasons, instrumentation overhead, evidence-package ID/version, source-set digest, claim count, complexity descriptor ID, prior-familiarity declaration, nullable counterbalance-plan ID/version, and nullable planned/actual order position. The counterbalance fields may be null for Phase 0.5 and are required for every Phase 1 session.

Total review minutes equal active review duration excluding declared pauses but including source location, calculation checking, correction, and approval work. Both manual and assisted modes use the same timer rules. Instrumentation overhead is separately measured and also reported.

### 3.4 ReviewActivityEvent

Each event contains event_id, review_session_id, activity_type, claim_id when applicable, started_at, ended_at, duration, disposition, correction category, materiality class, epistemic class, source-locate time, calculation-check time, edit/reject reason, and provenance.

Allowed claim dispositions are ACCEPTED, EDITED, REJECTED, and DEFERRED. Activity types include READING, SOURCE_LOCATE, CALCULATION_CHECK, CLAIM_REVIEW, CORRECTION, DRAFT_REVIEW, and APPROVAL. Overlapping events require an explicit overlap group and cannot be double-counted in total time.

### 3.5 ComplexityDescriptor

Contains descriptor_id/version, report_id, document count, page count where meaningful, source count, claim count, material-claim count, calculation count, reconciliation-exception count, corporate-action count, and missing/conflicting-source count. Unknown values remain null and block normalizations that require them.

### 3.6 BaselineMatch

Contains match_id, assisted session, baseline session, method PER_COMPANY_MANUAL or MATCHED_HISTORICAL_QUARTER, match variables, material differences, practice/familiarity flags, source/evidence hashes, approved rationale, and status.

A discovery-company Quarter 0 manual baseline may measure Phase 0.5 workflow economics but is not by itself a valid causal baseline for unfamiliar Phase 1 companies.

### 3.7 CounterbalancePlan

Contains plan_id/version, selected company IDs, analyst IDs, comparison groups, planned company/workflow order assignments, assignment method, status PLANNED/EXECUTED/PARTIAL/INFEASIBLE, actual assignments when run, deviations, residual order/practice confounds, evidence references/content digests, and plan_digest. `plan_digest` is SHA-256 of the program's canonical JSON of every preceding field except `plan_digest`; a status, assignment, deviation, or evidence change creates a new immutable plan version.

The plan must attempt to vary comparison order across companies when the available companies, analysts, and reporting calendar permit it. PARTIAL or INFEASIBLE requires a specific evidenced constraint and preserves the residual confound; a bare choice not to counterbalance is invalid. A Phase 1 economics result may proceed only with EXECUTED, or with PARTIAL/INFEASIBLE plus that evidence and disclosure.

### 3.8 EconomicsEvaluation

Contains evaluation_id, A-13 metric-contract ID/version/digest, evaluated sessions/matches and their digests, CounterbalancePlan ID/version/digest, metric IDs, pre-agreed thresholds, observed raw values, workload-normalized values, total report times, confounds, aggregation method, result PASS/FAIL/BLOCKED, evaluator, evidence IDs/content digests, and digest. The digest is SHA-256 of the program's canonical JSON of every preceding field except the digest itself.

The evaluator reads thresholds from the approved A-13 contract. It cannot accept a threshold supplied after observing results. Missing pre-agreement, invalid matches, incomplete timings, or unsupported normalization yields BLOCKED.

### 3.9 CapacityWindow

Contains capacity_window_id/version, selected universe ID/version/digest, A-12 capacity-policy ID/version/digest and approval binding, A-13 metric-contract ID/version/digest and approval binding, pre-agreed limit-set ID/version/digest, evaluation-method ID/version/digest, week start/end, analyst roster and committed minutes, report arrivals, document volume, claim volume, completed reviews, backlog items and age, next material event per update, completion-before-next-event result, retry/failure load, maintenance load, mitigation actions already in force, evidence IDs/content digests, and window_digest.

Derived measures include reports per analyst-week, peak-week documents and claims, maximum/median backlog age, percentage of updates completed before the next material event, required versus committed analyst minutes, and residual capacity. Every denominator and zero-denominator policy is explicit.

`window_digest` is SHA-256 of the program's canonical JSON of every CapacityWindow field except `window_digest`. The A-12/A-13 policies, limit set, evaluation method, and their approval timestamps must predate the first observed result in the window. Missing, stale, post-agreed, or digest-mismatched references make the window unusable.

### 3.10 CapacityEvaluation

Contains evaluation_id/version, CapacityWindow ID/version/digest, selected universe ID/version/digest, A-12 policy ID/version/digest and approval binding, A-13 contract ID/version/digest and approval binding, evaluation-method ID/version/digest, the complete pre-agreed limit set, observed measures, per-limit outcomes, aggregate result PASS/FAIL/BLOCKED, mitigation ID/version/digest when applicable, evidence IDs/content digests, approval_bindings, acceptance_state UNACCEPTED/ACCEPTED, capacity_result_sha256, and capacity_decision_sha256.

Each pre-agreed limit contains limit_id, A-13 metric ID/version, A-12 capacity dimension where applicable, comparison operator, threshold decimal string/scale, unit, denominator and zero-denominator policy, applicability interval, approval timestamp, and source-policy digests. Each per-limit outcome binds the limit ID/digest, observed value, predicate result TRUE/FALSE/UNKNOWN, and evidence digests.

The mechanical result is PASS if every applicable limit predicate is TRUE. It is FAIL if all required inputs are valid and at least one predicate is FALSE. It is BLOCKED if any required policy, limit, universe, method, input, denominator, prerequisite A-12/A-13 policy approval binding, evidence item, or digest is missing, stale, ambiguous, post-agreed, or UNKNOWN. A human decision cannot alter this result.

`capacity_result_sha256` is SHA-256 of the program's canonical JSON containing the evaluation/window/universe IDs, versions, and digests; the complete A-12/A-13 policy approval-binding objects with their resolution digests; evaluation-method digest; ordered complete limit definitions; observed measures; ordered per-limit outcomes; aggregate result; mitigation reference; and evidence IDs/content digests. It excludes both digest fields, the S18 post-result `approval_bindings`, and derived `acceptance_state`.

`approval_bindings` contains one explicit component-local requirement binding for each applicable S18 gate. Every accepted evaluation requires distinct current one-to-one `SATISFIED`/`APPROVED` bindings for S18-G03, S18-G04, and S18-G05; a mitigation also requires S18-G02. When satisfied, each binding carries approval_id, approval_record_id, approval type, exact scope, actor, timestamp, evidence, human_review_id, active resolution_decision_id, and resolution_content_sha256. Missing, reused, denied, revoked, expired, stale, scope-mismatched, or digest-mismatched records leave `acceptance_state=UNACCEPTED`.

The S18-G03 binding in this conjunction is the same prerequisite capacity-commitment requirement already bound through A-12, not a second approval requirement. Repeating its reference in the decision preimage binds terminal acceptance to the same current record without allowing that record to satisfy any different requirement.

`acceptance_state=ACCEPTED` if and only if the mechanical result is PASS and the applicable conjunction above validates. `capacity_decision_sha256` is SHA-256 of the program's canonical JSON containing `capacity_result_sha256`, the ordered complete approval bindings with their resolution digests, and derived acceptance_state. Any change to a result or binding requires a new immutable evaluation version and invalidates the prior decision digest.

## 4. Measurement and decision rules

### Phase 0.5

1. Record Quarter 0 manual baseline/bootstrap separately from Quarters 1–3 assisted updates.
2. Report all four observed report totals; for the three assisted updates, do not publish a report-level P90.
3. Present per-claim medians/distributions only as descriptive operational telemetry, stratified by claim type, materiality, epistemic class, disposition, and correction category where sample size permits disclosure.
4. Do not claim claim-level statistical independence or significance.
5. Measure identical time components and instrumentation overhead in manual and assisted modes.

### Phase 1 economics

1. Every selected company has a per-company manual baseline or a justified matched historical quarter.
2. Comparisons include raw total report time and the A-13-approved workload-normalized metrics.
3. Before Phase 1 measurement begins, create a CounterbalancePlan and attempt cross-company order counterbalancing where feasible. PARTIAL or INFEASIBLE is valid only with evidenced constraints and the residual order/practice confound in the experiment log.
4. Complexity, analyst familiarity, order/practice effects, source changes, model/tool changes, and unmatched differences are explicit confounds.
5. A pass is mechanical against pre-agreed A-13 thresholds, then subject to required human acceptance. Human acceptance cannot turn a mechanical threshold failure into PASS; mitigation and a new pre-agreed evaluation are required.
6. The result is evidence about the measured workflow and universe, not a portable causal estimate for all companies or analysts.

### Results-season throughput

1. Capacity is evaluated over an identified actual or evidence-backed peak week for the selected universe.
2. Before the window begins, bind the accepted C-01 universe, current approved A-12/A-13 policies, complete pre-agreed limits, and one versioned evaluation method.
3. Report arrivals, documents, claims, review minutes, retry/failure load, maintenance, backlog age, and next material events are measured into an immutable CapacityWindow using that method.
4. Evaluate every limit mechanically and persist the typed result plus capacity_result_sha256 before seeking the post-result S18-G04/S18-G05 human acceptances; the prerequisite capacity and policy approvals remain bound separately.
5. C-18 passes only when a PASS result has the applicable one-to-one human approval conjunction and a valid capacity_decision_sha256. A shortfall mitigation is approved before use, then produces a new window and evaluation; it cannot relabel the failed result.
6. Deferring work past the next material event, dropping material claims, or reducing review quality cannot be counted as capacity.

## 5. Invariants and fail-closed behavior

1. Manual and assisted sessions use the same event taxonomy, timer rules, and overhead disclosure.
2. Quarter 0 is not reused as an assisted primary comparator for Quarters 1–3.
3. Report totals are never replaced by claim-level pseudo-replication.
4. No report-level percentile is computed from the three assisted updates.
5. No significance or causal claim is emitted unless a separately approved design establishes its assumptions; S18 supplies none.
6. Thresholds and metric versions must predate the evaluated results.
7. Missing timestamps, overlapping unclassified time, missing claims, changed evidence packages, or stale metric versions block evaluation.
8. Accepted/edited/rejected/deferred counts reconcile exactly to the reviewed claim inventory.
9. Source-locate, calculation-check, correction, and approval time reconcile to total active time without double counting.
10. Universe selection is exactly two or three core non-financial companies and carries current capacity evidence.
11. Confounds are never silently normalized away.
12. A capacity shortfall remains FAIL or BLOCKED. C-18 remains unaccepted until an approved mitigation is applied and a fresh window/evaluation independently passes.
13. An analyst or product owner may accept evidence or mitigation only through a typed human resolution; delegated Sol review cannot supply that authority.
14. Capacity acceptance is derived only from the typed mechanical result and applicable one-to-one approval bindings; a free-form decision status is never authoritative.
15. A missing counterbalancing attempt, or a PARTIAL/INFEASIBLE status without evidenced constraints and confound disclosure, blocks the Phase 1 economics evaluation.

## 6. Evidence and typed approval gates

All entries begin unresolved. This draft, coordinator narration, and delegated review do not constitute human acceptance or capacity commitment.

| Gate | Type | Required authority | Required evidence | Blocks |
|---|---|---|---|---|
| S18-G01 | DELEGATED_ARTIFACT_APPROVAL | Fresh gpt-5.6-sol xhigh reviewer under delegated goal authority | Persisted clean review, exact source hashes, review round, reviewer/session identity, timestamp, and artifact hash | Spec approval and planning |
| S18-G02 | PRODUCT_OWNER_DECISION | Human product owner | Approved Phase 1 selection of exactly two or three core non-financial companies, candidate/rejection rationale, and mitigation decisions | C-01 and mitigated C-18 acceptance |
| S18-G03 | CAPACITY_COMMITMENT | Competent human capacity owner | A-12-backed weekly analyst/builder capacity, peak-week availability, maintenance allowance, and named scope | C-01 selection and C-18 acceptance |
| S18-G04 | ANALYST_ACCEPTANCE | Human analyst responsible for the measured workflow | Acceptance of timer protocol, baseline matches, recorded confounds, observed economics, and throughput usability | B-04, C-12, and C-18 acceptance |
| S18-G05 | NAMED_OWNER_COMMITMENT | Human owner of measurement operations | Named ownership for instrumentation integrity, backlog tracking, corrections, and evidence retention | Measurement collection and terminal acceptance |

Required evidence inventory:

- approved A-13 metric contract and pre-agreed thresholds;
- approved A-12 capacity/calendar record;
- symmetric manual/assisted instrumentation protocol and content hash;
- Quarter 0 plus Quarters 1–3 session/event exports with reconciliation results;
- Phase 1 candidate rubric, selection decision, baseline matches, complexity descriptors, and confound log;
- CounterbalancePlan, actual order assignments, and either execution evidence or the evidenced PARTIAL/INFEASIBLE constraint;
- peak-week CapacityWindow and CapacityEvaluation evidence, complete pre-agreed limit set, result/decision digests, and any mitigation/new-window/re-evaluation chain;
- typed approval records for S18-G02 through S18-G05;
- fresh delegated review and verification outputs bound to all current artifact hashes.

## 7. Acceptance tests and verification

| Test ID | Required proof |
|---|---|
| S18-T01 | Review-event counts reconcile exactly to accepted/edited/rejected/deferred totals and the claim inventory. |
| S18-T02 | Active time reconciles to component events without double-counted overlaps; instrumentation overhead is reported separately. |
| S18-T03 | A request for report-level P90 from the three assisted reports is rejected. |
| S18-T04 | Claim-level summaries are labeled descriptive/clustered and cannot produce a significance claim. |
| S18-T05 | Quarter 0 reused as an assisted primary comparator is rejected. |
| S18-T06 | Phase 1 evaluation without a per-company or approved matched-quarter baseline returns BLOCKED. |
| S18-T07 | A threshold created after the evaluated result, a stale A-13 version, or an incomplete complexity descriptor returns BLOCKED. |
| S18-T08 | Raw total time, workload-normalized results, and every declared confound appear together in the economics result. |
| S18-T09 | Universe selection rejects fewer than two, more than three, financial-sector, unsupported, or capacity-infeasible selections. |
| S18-T10 | From the bound CapacityWindow, A-12/A-13 policies, limit set, and evaluation method, capacity metrics and every limit predicate reproduce reports per analyst-week, peak documents/claims, backlog age, completion before next event, required-versus-committed minutes, the aggregate PASS/FAIL/BLOCKED result, and capacity_result_sha256 exactly. |
| S18-T11 | Dropped material work, overdue updates, or quality-gate bypass cannot improve a capacity result. |
| S18-T12 | A shortfall without approved mitigation yields FAIL/BLOCKED; an approved mitigation cannot rewrite that result and must produce a fresh CapacityWindow and CapacityEvaluation. |
| S18-T13 | With prerequisite A-12/A-13 bindings current, mechanical PASS without distinct current S18-G04/G05 records remains UNACCEPTED; terminal acceptance also binds S18-G03, and a mitigated case additionally requires S18-G02. Reused, stale, revoked, or scope/digest-mismatched records fail and cannot reproduce capacity_decision_sha256. |
| S18-T14 | Mutation of a session, claim inventory, match, metric/policy version, threshold, selected universe, evaluation method, CapacityWindow, result, mitigation, or approval binding changes the applicable digest and invalidates prior evaluation/acceptance evidence. |
| S18-T15 | Each Phase 1 run has an EXECUTED counterbalance plan, or a PARTIAL/INFEASIBLE plan with a specific evidenced constraint and residual confound; a missing attempt or bare decline returns BLOCKED. |

Verification succeeds only when current data reconcile, negative tests fail closed, evidence hashes and both capacity digests recompute, and the applicable one-to-one typed approvals are satisfied. Human acceptance cannot be inferred from a passing script.

## 8. Dependencies, activation, and amendment guards

- B-04 depends on completed A-03 baseline instrumentation, the approved A-13 metric contract, and B-13 reviewer-bias controls.
- C-01 depends on A-12 capacity/calendar evidence and a current human capacity commitment.
- C-12 depends on A-13 and valid B-04 evidence.
- C-18 depends on A-12, A-13, and the accepted C-01 universe.
- S05 owns discovery-company/quarter selection; S07 owns reviewer-bias controls; S08 owns metric definitions, budgets, and capacity policy. S18 consumes those decisions and owns the measurements and gates above.
- Deferred activation guard: not applicable to owned rows. B-04, C-01, C-12, and C-18 were Open at activation, so S18 is active-only and no ACTIVATE_DEFERRED resolution applies.
- Amendment gate: no evidence-derived provisional amendment gate is assigned to S18. Changes to an approved timer protocol, match method, normalization, universe, threshold, or capacity method require versioning, impact evidence, fresh Sol review, and repetition of affected human approvals; observed results may not be used to retroactively choose a favorable method.
