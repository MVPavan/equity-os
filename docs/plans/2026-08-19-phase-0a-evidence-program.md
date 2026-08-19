# Phase 0A Evidence Program Implementation Plan

**Origin:** `docs/specs/2026-08-19-phase-0a-evidence-program.md`; pre-approval SHA-256 `5e8bfb585fcb0891e9b04f0a9088b9f2374c7390523316f2fcbc3a080f3b7040`, preserved in its approval metadata; current approved-artifact SHA-256 `3ffcb445b8f4743034453a0ea4b2548a5e1325777eabcb3d8495c3fb2a775965` at approval commit `3437550`.
**Goal:** Produce the authority-backed, digest-bound A-01 through A-13 evidence and one mechanically validated Phase 0A exit package needed before any Phase 0.5 product implementation can begin.
**Out of scope:** A workstream or roadmap; product code; assisted program Quarters 1-3; Phase 0.5 execution; provider, feed, parser, library, model, purchase, credential, or ingestion selection; public, paid, personalized, or execution-linked distribution; historical ledger closure; copied register statuses or gate prose.
**Constraints:** The v2 decision register is the sole operational authority; this plan follows its A rows and section F, not historical ledger artifacts.
**Constraints:** The binding 2026-08-19 current-user decision is preserved in the versioned notes/history of `eqos-3ps`: after the exact five-stage structure and recommended A-01/A-02 values were shown, the current user replied `continue`, and the Orchestrator accepted that response as approval of the stated structure and values. Execution must cite that durable event rather than infer approval from the spec or shortlist.
**Constraints:** A-01 is private/internal-only: public, paid, personalized, and execution-linked modes remain prohibited. This is the recorded product-owner boundary decision, not a legal-sufficiency finding and not activation of E-08.
**Constraints:** A-02 selects Infosys issuer Q1-Q4 FY25 as program Q0-Q3. The separate identifiable analyst suitability attestation remains required and fail-closed.
**Constraints:** Every source/use rights decision remains separate, current, attributable, and fail-closed. Public access, research evidence, or another approval never establishes a right.
**Constraints:** Preparatory evidence work may proceed within an already authorized scope; missing, stale, conflicting, mismatched, or wrong-authority decisions produce `BLOCKED` or `UNKNOWN` and are never synthesized by an agent.
**Constraints:** Only non-product validation automation may be written in Phase 0A. Product code, product tests, and Phase 0.5 work remain blocked until the complete v2 Phase 0A exit gate, approved relevant build contracts, and continuing Architecture v2 approval.
**Constraints:** One integrated independent review is performed on the exact exit-package bytes after mechanical checks. Earlier tasks receive author self-check and competent-human decisions; they do not each create an independent review round.
**Tracking:** Single-phase epic `eqos-3ps`; five flat stages `eqos-3ps.1` through `eqos-3ps.5`; no workstream, roadmap, nested Beads, or extra issue.

## Approved stage graph and ownership

| Stage | Bead | Primary A-row ownership | Classification |
|---|---|---|---|
| S1 Boundary and discovery slice | `eqos-3ps.1` | A-01, A-02 | Substantive evidence and human-decision capture |
| S2 Source rights and filing coverage | `eqos-3ps.2` | A-05, A-06 | Substantive rights evidence plus evidence/docs spike |
| S3 Measured baseline and bootstrap thesis | `eqos-3ps.3` | A-03, A-04, A-10, A-11, A-13 | Substantive analyst and measurement evidence |
| S4 Golden set and product identity evidence | `eqos-3ps.4` | A-08, A-09 | Substantive evaluation evidence and independent human decisions |
| S5 Operating envelope and integrated exit package | `eqos-3ps.5` | A-07, A-12; exact A-01..A-13 acceptance | Substantive operating decisions plus non-product validation automation |

The graph contains exactly five `parent-child` edges from `eqos-3ps.1` through `eqos-3ps.5` to epic `eqos-3ps`, plus exactly four `blocks` edges: `eqos-3ps.2 -> eqos-3ps.1`, `eqos-3ps.3 -> eqos-3ps.2`, `eqos-3ps.5 -> eqos-3ps.3`, and `eqos-3ps.5 -> eqos-3ps.4`, where the left side depends on the right side. S4 may run in parallel with S1-S3 where it does not assume an unsettled boundary, source right, measurement definition, company fact, or human decision.

Each plan task is a bounded Implementer dispatch. Closing a child Bead requires every plan task mapped to it to be complete and the child acceptance criteria to hold. Review is integrated at S5 rather than repeated per file.

## File map

| Path | Responsibility |
|---|---|
| `docs/evidence/phase-0a/a-01-initial-boundary-decision.md` | Exact A-01 product-owner boundary decision and authority envelope. |
| `docs/evidence/phase-0a/a-02-discovery-slice-selection.md` | Exact A-02 product-owner selection plus separate analyst suitability attestation. |
| `docs/evidence/phase-0a/source-package-inventory.json` | Versioned metadata-only Infosys Q1-Q4 FY25 source-package inventory, operations sought, cutoff/provenance fields, record digest, and `UNKNOWN`/`BLOCKED` source-content digest until exact acquisition/retention rights permit it. |
| `docs/evidence/phase-0a/a-05-source-rights-package.json` | Per-source and per-operation rights decisions, unknown/denied behavior, account limits, point-in-time availability, and replacement paths. |
| `docs/evidence/phase-0a/a-06-filing-coverage-matrix.csv` | Company-quarter coverage observations across every A-06 dimension with distinct unknown, absent, and not-applicable states. |
| `docs/evidence/phase-0a/a-06-filing-coverage-spike.md` | Spike method, source references, reconciliation observations, gaps, and bounded conclusions. |
| `docs/evidence/phase-0a/a-04-output-contract-v0.md` | Provisional output contract frozen before the first measured Q0 action. |
| `docs/evidence/phase-0a/a-10-materiality-policy.md` | Versioned concrete materiality policy and analyst decision. |
| `docs/evidence/phase-0a/a-10-validator-cases.jsonl` | Authority-owned materiality validator cases and expected outcomes. |
| `docs/evidence/phase-0a/a-13-success-metric-contract-v0.md` | Pre-baseline metric definitions, units, scopes, collection methods, correction rules, phase applicability, and method acceptances; no evidence-derived targets. |
| `docs/evidence/phase-0a/instrumentation-vocabulary.json` | Shared manual/assisted-shaped event definitions, actor/timing semantics, exclusions, correction lineage, and overhead treatment. |
| `docs/evidence/phase-0a/a-03-manual-baseline-package.md` | Reconstructable, approved Q0 manual workflow evidence. |
| `docs/evidence/phase-0a/instrumentation-events.jsonl` | Q0 event stream using the frozen instrumentation vocabulary. |
| `docs/evidence/phase-0a/a-04-output-contract-final.md` | Evidence-derived final output contract and required analyst/product-owner acceptances. |
| `docs/evidence/phase-0a/a-11-bootstrap-thesis.md` | Exact versioned, analyst-authored and analyst-approved Q0 bootstrap thesis. |
| `docs/evidence/phase-0a/a-13-success-metric-contract-final.md` | Post-baseline A-13 contract retaining the accepted method and adding evidence-derived product-owner target decisions. |
| `docs/evidence/phase-0a/a-08-golden-set-charter.md` | Accountable owner/individual, repository location, cadence, label authority, and fixture governance. |
| `docs/evidence/phase-0a/a-08-golden-set.jsonl` | At least twenty non-duplicate expert-labeled initial cases across every required failure category. |
| `docs/evidence/phase-0a/a-09-trademark-legal-assessment.md` | Trademark/legal search record and risk assessment for the exact candidate identity. |
| `docs/evidence/phase-0a/a-09-product-owner-decision.md` | Separate product-owner selection or rejection of that same exact identity. |
| `docs/evidence/phase-0a/a-07-workflow-budget-contract.md` | Approved ceilings or measurement rules for every required workflow-budget dimension. |
| `docs/evidence/phase-0a/a-12-operating-capacity-contract.md` | Product-owner-approved calendar, personnel capacity, ceilings, maintenance allowance, and expected coverage. |
| `docs/evidence/phase-0a/manifest.json` | Exact A-01..A-13 primary-ownership index, artifact paths, versions, decisions, source references, and SHA-256 digests; not a status mirror. |
| `docs/evidence/phase-0a/phase-0a-exit-record.md` | Small reviewed decision record mapping each applicable v2 section F clause to exact current evidence and human decisions. |
| `scripts/validate_phase_0a_evidence.py` | Python-stdlib, non-product validator for structural, digest, typed Beads graph, authority, whitespace, and evidence-contract checks. |
| `tests/phase_0a/test_validate_phase_0a_evidence.py` | Validator tests for happy paths and every spec-required fail-closed branch. |

The approved spec, v2 decision register, blueprint-completion goal, Architecture v2 brief, and discovery shortlist are read-only inputs. No task modifies them.

### Task 1: Record the boundary and discovery slice - substantive

Goal: A-01 and A-02 are durable exact decisions for the approved private/internal Infosys slice, while analyst suitability remains a separate attributable gate.

Stage: `eqos-3ps.1`

Files:
- Create: `docs/evidence/phase-0a/a-01-initial-boundary-decision.md`, `docs/evidence/phase-0a/a-02-discovery-slice-selection.md`, `docs/evidence/phase-0a/source-package-inventory.json`
- Modify: None
- Test: None; Task 9 validates the completed records and inventory.

Interfaces:
- Consumes: the exact 2026-08-19 approval event preserved in the versioned notes/history of `eqos-3ps`; the approved spec; the non-authoritative `DiscoveryCompanyShortlist`; v2 A-01/A-02; already available official-source references only.
- Produces: `InitialBoundaryDecision` Markdown; `DiscoverySliceSelection` Markdown; metadata-only `SourcePackageInventory` JSON keyed by program quarter, source identifier, intended operation, cutoff/provenance, record digest, and source-content-digest state.

Approach: Bind both product-owner records to the exact `eqos-3ps` approval-history event, including its principal, timestamp, decision text, presented scope, and event reference; do not treat the approved spec or shortlist as that decision. Record private/internal as the sole initially allowed mode and prohibit public, paid, personalized, and execution-linked modes separately, without claiming legal sufficiency. Record Infosys issuer Q1-Q4 FY25 as program Q0-Q3, with Q0 reserved for the manual baseline/bootstrap thesis and Q1-Q3 reserved for assisted updates. Preserve the source shortlist's facts, inferences, and data gaps as those epistemic classes. Inventory only metadata and already lawfully held bytes before Task 2. Set source-content digests to `UNKNOWN` or `BLOCKED` unless the exact acquisition and retention operations are already permitted; observed URLs never authorize fetching for hashing. Obtain and record an identifiable analyst suitability attestation against the exact selected slice; if it is absent, stale, or scope-mismatched, keep A-02 and the stage `BLOCKED`. Do not invent a decider identity not present in the approval evidence.

Verification: `python3 -m json.tool docs/evidence/phase-0a/source-package-inventory.json >/dev/null` exits 0; a focused inspection confirms four ordered entries map issuer Q1-Q4 FY25 to program Q0-Q3, every source entry carries intended operations, provenance/cutoff fields, a record digest, and either a permitted held-byte content digest or `UNKNOWN`/`BLOCKED`; both decisions cite the exact `eqos-3ps` approval-history event; and the A-02 record contains a separate current identifiable analyst attestation. If the attestation is absent, the task does not pass.

Dependencies: None

Risks: `HIGH` distribution and human-authority boundary. No code or test-first call applies; stage closure is blocked until the analyst attestation is real and attributable.

### Task 2: Resolve source and use rights - substantive

Goal: Every source and intended operation in the selected package has a current competent-authority disposition, with unknown or unapproved operations denied.

Stage: `eqos-3ps.2`

Files:
- Create: `docs/evidence/phase-0a/a-05-source-rights-package.json`
- Modify: None
- Test: None; Task 9 supplies rights set-equality and negative-path automation.

Interfaces:
- Consumes: the Task 1 `SourcePackageInventory`, A-01 boundary, exact intended operations, and decisions supplied by the source-rights authority with legal review where that authority requires it.
- Produces: `SourceRightsPackage` JSON keyed by source identifier and intended operation, with access method, automation, caching, retention, commercial use, transformation/derived output, redistribution, account limits, point-in-time availability, replacement path, authority envelope, and disposition.

Approach: Present each source/use pair to the competent source-rights authority; the Implementer may collect terms and facts but may not decide what they permit. Record independently scoped `ALLOWED`, `DENIED`, or `UNKNOWN` dispositions. Treat missing, ambiguous, stale, wrong-authority, or broader-than-evidence decisions as `UNKNOWN`; deny acquisition, transformation, and use except for operations independently marked `ALLOWED`. Keep public access and technical feasibility separate from permission. Select no provider, procurement route, account, credential, parser, or automation mechanism.

Verification: `python3 -m json.tool docs/evidence/phase-0a/a-05-source-rights-package.json >/dev/null` exits 0; a set comparison between source/use pairs in the inventory and rights package is exact; every required field is populated or explicitly unknown; and negative inspection confirms no source-level access decision widens independently denied or unknown operations.

Dependencies: Task 1

Risks: `HIGH` rights boundary. The source-rights authority supplies the conclusion; the Implementer only structures evidence and records it.

### Task 3: Run the filing-channel coverage spike - evidence/docs

Goal: A-06 reports rights-permitted Infosys Q0-Q3 filing coverage and reconciliation effort at every required dimension without hiding gaps in an aggregate score.

Stage: `eqos-3ps.2`

Files:
- Create: `docs/evidence/phase-0a/a-06-filing-coverage-matrix.csv`, `docs/evidence/phase-0a/a-06-filing-coverage-spike.md`
- Modify: None
- Test: None; Task 9 validates dimensions and state vocabulary.

Interfaces:
- Consumes: Task 1 `SourcePackageInventory`; Task 2 `SourceRightsPackage`; only source content and operations currently marked `ALLOWED`.
- Produces: `FilingCoverageMatrix` CSV with company-quarter/channel/dimension rows; `FilingCoverageSpike` Markdown with method, versioned sources, observed mapping stability, reconciliation effort, conflicts, and gaps.

Approach: Evaluate Tier 1 official structured/XBRL first for each required measurement. Use Tier 2 official unstructured content only for demonstrated coverage gaps and retain exact source locations. A Tier 3 item may appear only if it is separately licensed and rights-permitted, and then only as a reconciliation cross-check; it cannot become primary, fill a missing official-source gap, or win a conflict by origin. Cover filing channel, taxonomy/version, statement, segment, note, ownership/share count, restatement behavior, mapping stability, and reconciliation effort for each program quarter. Preserve `UNKNOWN`, `ABSENT`, and `NOT_APPLICABLE` distinctly. Keep source disagreements visible for analyst disposition and state unproven stable XBRL links or retention as data gaps.

Verification: `python3 -c 'import csv; p="docs/evidence/phase-0a/a-06-filing-coverage-matrix.csv"; r=list(csv.DictReader(open(p, newline=""))); assert r and {x["program_quarter"] for x in r}=={"Q0","Q1","Q2","Q3"}'` exits 0; focused inspection confirms every required dimension occurs for each quarter, only allowed operations were used, state values remain distinct, and the spike reports per-quarter gaps rather than one aggregate score.

Dependencies: Task 2

Risks: Rights and cutoff failures block affected observations. This task records evidence, not a source-rights, provider, parser, or coverage-acceptance decision.

### Task 4: Freeze pre-baseline contracts - substantive

Goal: A-04 v0, the concrete A-10 policy/validator set, and the A-13 measurement method are authority-approved and immutable before the first measured Q0 baseline action.

Stage: `eqos-3ps.3`

Files:
- Create: `docs/evidence/phase-0a/a-04-output-contract-v0.md`, `docs/evidence/phase-0a/a-10-materiality-policy.md`, `docs/evidence/phase-0a/a-10-validator-cases.jsonl`, `docs/evidence/phase-0a/a-13-success-metric-contract-v0.md`, `docs/evidence/phase-0a/instrumentation-vocabulary.json`
- Modify: None
- Test: None; Task 9 exercises validator cases and instrumentation equivalence.

Interfaces:
- Consumes: Task 3 coverage evidence; the rights-permitted source package; v2 A-03/A-04/A-10/A-13; competent analyst, product-owner, and expressly assigned domain/evaluation decisions.
- Produces: `OutputContractV0` Markdown; `MaterialityPolicy` Markdown; `MaterialityValidatorCases` JSONL; `SuccessMetricContractV0` Markdown containing definitions and collection methods but no evidence-derived target decisions; `InstrumentationVocabulary` JSON shared by manual and assisted-shaped events.

Approach: Freeze the provisional output sections required by A-04 without inventing generalized schemas. Define A-10 quantitative magnitude, thesis relevance, source conflict/uncertainty, coverage-specific overrides, and every always-material category from the spec; require material for always-material cases and review for important unresolved conflict, missing input, or low confidence. Obtain analyst approval of the concrete policy and validator set; a domain/evaluation authority may prepare or validate only its expressly assigned fixtures or metrics. Define every A-13 metric's unit, scope, collection method, phase applicability, correction rules, and instrumentation overhead in v0, and obtain analyst/evaluation acceptance of that method. Do not set product-owner targets before the baseline evidence exists. Write the shared event vocabulary before Q0 data collection and preserve successor-version semantics for future changes.

Verification: `python3 -m json.tool docs/evidence/phase-0a/instrumentation-vocabulary.json >/dev/null` exits 0; every line of `a-10-validator-cases.jsonl` parses as one JSON object; cold inspection confirms all A-04 v0 sections, A-10 always-material categories/outcomes, A-13 v0 metrics/method fields, symmetric event semantics, correction lineage, overhead treatment, and exact method/policy authorities; A-13 v0 contains no unsupported target decision.

Dependencies: Task 3

Risks: `HIGH` analytical and measurement authority. Any absent policy/method approval or unusable instrumentation method blocks Task 5; targets remain pending baseline evidence and are not supplied by the Implementer.

### Task 5: Execute Q0 and approve the bootstrap thesis - substantive

Goal: The rights-permitted Infosys Q0 manual baseline is reconstructable under the frozen contracts, and its final output contract and exact bootstrap thesis carry all required approvals.

Stage: `eqos-3ps.3`

Files:
- Create: `docs/evidence/phase-0a/a-03-manual-baseline-package.md`, `docs/evidence/phase-0a/instrumentation-events.jsonl`, `docs/evidence/phase-0a/a-04-output-contract-final.md`, `docs/evidence/phase-0a/a-11-bootstrap-thesis.md`, `docs/evidence/phase-0a/a-13-success-metric-contract-final.md`
- Modify: None
- Test: None; Task 9 reconstructs the baseline and checks material support.

Interfaces:
- Consumes: Task 4 frozen contracts and vocabulary; Task 2 rights dispositions; Task 3 coverage evidence; exact rights-permitted Q0 content; analyst work and decisions.
- Produces: `ManualBaselinePackage` Markdown; `InstrumentationEventStream` JSONL; `OutputContractFinal` Markdown; exact `BootstrapThesis` Markdown; post-baseline `SuccessMetricContractFinal` Markdown.

Approach: Run Q0 manually and record time-stamped reading, exact source location, verification, deterministic or manual calculation trace, drafting, review, correction lineage, approval, and instrumentation overhead. The LLM is never an authoritative calculator. Fail material observed results without exact source locations and material computed results without calculation traces. Use the accepted baseline to finalize A-04, preserving event/cutoff, facts, changes, drivers, management ledger, thesis impact, observable falsifiers, open questions, calculations, non-canonical memory draft, and approval record; obtain analyst usability acceptance and product-owner scope approval. Preserve the accepted A-13 v0 method and use the measured baseline to obtain product-owner target decisions in A-13 final; the analyst and evaluation authority re-confirm the collection method against observed use. The analyst then authors and approves the concise versioned A-11 thesis, assumptions, commitments, risks, open questions, and falsifiers. It is not full initiation. Program Q1 stays blocked until the exact thesis version and digest are approved.

Verification: every line of `instrumentation-events.jsonl` parses as one JSON object; a cold replay from Q0 package through baseline, final output, A-13 final, and thesis resolves each accepted material observation to an exact source location, each accepted material computation to a trace, and each correction to visible lineage; A-13 final preserves the accepted v0 method and adds only evidence-derived product-owner targets; authority records and content digests match the exact reviewed versions.

Dependencies: Task 4

Risks: `HIGH` analyst authority and Phase 0.5 entry evidence. Failed instrumentation invalidates affected comparisons and blocks metric, budget, and capacity decisions.

### Task 6: Establish the golden set - substantive evidence/fixtures

Goal: A-08 has an accountable owner, competent labels, and at least twenty non-duplicate initial cases covering every required failure class.

Stage: `eqos-3ps.4`

Files:
- Create: `docs/evidence/phase-0a/a-08-golden-set-charter.md`, `docs/evidence/phase-0a/a-08-golden-set.jsonl`
- Modify: None
- Test: None; Task 9 validates cardinality, uniqueness, ownership, and category coverage.

Interfaces:
- Consumes: v2 A-08; spec failure categories; decisions and labels from the named evaluation/domain authority; source-derived fixtures only where their use is rights-permitted.
- Produces: `GoldenSetCharter` Markdown; `GoldenCaseSet` JSONL with stable case IDs, category, input/reference, expected disposition, label authority, version, provenance, and digest.

Approach: Name the accountable owner and individual, repository location, review cadence, label authority, and promotion/change method. Prepare at least twenty expert-labeled cases spanning prompt injection, source confusion, source, period, unit, citation, numerical trace, unsupported claim, and materiality failures. Keep shadow or prepared outcomes separate from authority-approved labels; do not pad the minimum with duplicates, unlabeled examples, or multiple encodings of one case. Where the selected source package is not yet rights-permitted, use bounded synthetic structure without fabricating a source fact and mark it as such.

Verification: every JSONL line parses; a count of unique `case_id` values is at least twenty; the required category set is a subset of recorded categories; each case names an identifiable label authority, expected result, provenance class, version, and digest; the charter names the accountable individual and cadence.

Dependencies: None; may run in parallel with Tasks 1-5, subject to rights and unsettled-fact constraints.

Risks: `HIGH` evaluation authority. A prepared fixture is not an approved label, and fixture results are never production approval.

### Task 7: Complete the product identity decision pair - substantive

Goal: A-09 contains two separately attributable decisions for the same exact candidate identity, with neither decision reused as the other.

Stage: `eqos-3ps.4`

Files:
- Create: `docs/evidence/phase-0a/a-09-trademark-legal-assessment.md`, `docs/evidence/phase-0a/a-09-product-owner-decision.md`
- Modify: None
- Test: None; Task 9 validates decision-type and candidate-identity equality.

Interfaces:
- Consumes: the exact candidate identity; trademark/legal authority search record and risk assessment; separate product-owner selection or rejection.
- Produces: `TrademarkLegalAssessment` Markdown with its authority envelope; separate `ProductOwnerIdentityDecision` Markdown for the identical normalized candidate identity.

Approach: Present the exact candidate identity, including continued use of Funda where applicable, to the competent trademark/legal authority and record its search facts, unknowns, and risk assessment without selecting the product identity. Present that exact evidence version to the product owner and record a separate typed selection or rejection. Keep decision types, deciders, times, rationale, evidence version, and digests distinct. If either is absent, stale, mismatched, or outside authority, identity remains undecided.

Verification: focused comparison shows identical normalized candidate identity and reviewed evidence version across both files, distinct required decision types and competent deciders, and each recorded content digest matching its own file bytes; neither file claims that architecture, governance, rights, or the other A-09 record supplies its authority.

Dependencies: None; may run in parallel with Tasks 1-6.

Risks: `HIGH` legal/trademark and product-owner authority. The Implementer records evidence and decisions but supplies neither conclusion.

### Task 8: Freeze workflow budgets and operating capacity - substantive

Goal: A-07 and A-12 are evidence-derived product-owner decisions grounded in the accepted Infosys Q0 measurement rather than assumed capacity or unlimited spending.

Stage: `eqos-3ps.5`

Files:
- Create: `docs/evidence/phase-0a/a-07-workflow-budget-contract.md`, `docs/evidence/phase-0a/a-12-operating-capacity-contract.md`
- Modify: None
- Test: None; Task 9 validates required dimensions, grounding, and approval state.

Interfaces:
- Consumes: Task 5 accepted measurement evidence; Task 4 metric definitions; selected-company scope; available-personnel facts; product-owner decisions.
- Produces: `WorkflowBudgetContract` Markdown; `OperatingCapacityContract` Markdown.

Approach: For model cost, tool calls, latency, document volume, retries, and analyst minutes, record either an approved `CEILING` or a defined `MEASUREMENT_RULE`; represent a missing ceiling decision as `CEILING_NOT_APPROVED`, never unlimited. Record weekly builder and analyst capacity, target dates, monthly provider/model/infrastructure ceilings, maintenance allowance, and expected company coverage. Make every A-12 value traceable to selected-company evidence, observed Q0 manual work, available personnel, and explicit product-owner approval. Do not procure or select a provider, model, or infrastructure product.

Verification: cold inspection finds every A-07 and A-12 field with units, scope, evidence version, decision state, authority, and digest; every ceiling is approved or explicitly `CEILING_NOT_APPROVED`; no throughput or coverage value lacks a cited measurement or personnel basis.

Dependencies: Tasks 5, 6, and 7

Risks: `HIGH` product-owner authority and operating-envelope decisions. Missing measurements or authority block the contract rather than defaulting to a permissive value.

### Task 9: Build the evidence validator - validation automation

Goal: Non-product automation mechanically rejects malformed, incomplete, stale, unauthoritative, digest-mismatched, or graph-mismatched Phase 0A evidence.

Stage: `eqos-3ps.5`

Files:
- Create: `scripts/validate_phase_0a_evidence.py`, `tests/phase_0a/test_validate_phase_0a_evidence.py`
- Modify: None
- Test: `tests/phase_0a/test_validate_phase_0a_evidence.py`

Interfaces:
- Consumes: the approved spec's evidence-contract and negative-path semantics; all Task 1-8 typed artifacts; exactly five child-to-epic `parent-child` edges and four named inter-stage `blocks` edges from Beads export JSONL.
- Produces: Python-stdlib `Phase0AEvidenceValidator`; focused unittest fixtures; `Phase0AValidationReport` command output.

Approach: Write the smallest Python-stdlib validator needed to check record fields, enums, versions, SHA-256 digests, exact A-set equality when a manifest is present, source/use rights set equality, four-quarter continuity, twenty-case minimum, required authorities, cross-artifact references, and trailing-whitespace/final-newline rules. Parse Beads JSONL by dependency type: require exactly five named `parent-child` relations to `eqos-3ps` and exactly the four approved `blocks` relations, with no other `blocks` relation among the epic and children. Test structural happy paths; integrated baseline reconstruction; manual/assisted-shaped instrumentation equivalence; missing/stale/conflicting/wrong-role authority; unknown rights; absent cutoff; source conflict; incomplete coverage; unsupported material result; A-09 mismatch; golden-set defects; and A-10 fixture outcomes. Use minimal valid and invalid fixtures; do not embed real source content or human decisions in test data.

Verification: `python3 -m py_compile scripts/validate_phase_0a_evidence.py tests/phase_0a/test_validate_phase_0a_evidence.py` exits 0; `python3 -m unittest discover -s tests/phase_0a -p 'test_*.py'` exits 0; `bd export | python3 scripts/validate_phase_0a_evidence.py --root docs/evidence/phase-0a --beads-jsonl -` exits 0 and reports exactly five typed parent edges plus the four approved typed blocking edges; the validator reports no whitespace/final-newline defect in its owned files or evidence inputs.

Dependencies: Task 8

Risks: The automation itself is non-product but guards a `HIGH` phase gate. Use characterization-first fixtures; a failed check blocks Task 10 and Phase 0.5 product implementation.

### Task 10: Assemble the manifest and exit record - substantive gate evidence

Goal: The complete A-01 through A-13 artifact set is digest-bound exactly once and mapped to the applicable v2 Phase 0A exit clauses without copying register status or gate prose.

Stage: `eqos-3ps.5`

Files:
- Create: `docs/evidence/phase-0a/manifest.json`, `docs/evidence/phase-0a/phase-0a-exit-record.md`
- Modify: None
- Test: `scripts/validate_phase_0a_evidence.py`, `tests/phase_0a/test_validate_phase_0a_evidence.py`

Interfaces:
- Consumes: all Task 1-9 typed artifacts; v2 section F; exact competent-human decision records; continuing Architecture v2 approval.
- Produces: `Phase0AEvidenceManifest` JSON; exact-byte `Phase0AExitRecord` Markdown; passing `Phase0AValidationReport`.

Approach: Build a manifest whose primary-owner keys equal A-01 through A-13 exactly once and bind every artifact, decision, evidence version, source reference, and SHA-256 digest without becoming a status mirror. Write one small exit record mapping each applicable v2 section F clause to exact current evidence paths and human decisions without copying register statuses or gate prose and without inferring pass from dependencies. Run the Task 9 validator on the complete package. Missing, stale, conflicting, mismatched, wrong-authority, digest-mismatched, or unsupported evidence leaves the record non-accepting and keeps S5 open.

Verification: `python3 -m json.tool docs/evidence/phase-0a/manifest.json >/dev/null` exits 0; `bd export | python3 scripts/validate_phase_0a_evidence.py --root docs/evidence/phase-0a --beads-jsonl -` exits 0 and reports exact A-01..A-13 ownership, current authority, matching digests, and the approved typed graph; `python3 -m unittest discover -s tests/phase_0a -p 'test_*.py'` exits 0; every exit-record mapping resolves to an existing manifest entry and current human decision.

Dependencies: Task 9

Risks: `HIGH` blueprint-phase gate. A passing validator is necessary but cannot supply product-owner, analyst, legal/trademark, source-rights, domain/evaluation, or review authority.

### Task 11: Review and Git-bind the exact exit package - substantive activation

Goal: One independent Reviewer accepts the exact staged Phase 0A package, one authorized normal commit binds those unchanged bytes, and only then are S5 and the epic closed.

Stage: `eqos-3ps.5`

Files:
- Create: None
- Modify: None
- Test: every Task 1-10 created path, the exact staged file set, the resulting commit, and live Beads state.

Interfaces:
- Consumes: Task 10 exact package and passing validation; an otherwise empty index; explicit authority to stage and create the normal evidence-binding commit; one independent Reviewer.
- Produces: one accepted exact-byte review verdict; one normal `Phase0AEvidenceCommit`; Beads closure evidence recording commit and review references.

Approach: Stop and obtain explicit git staging/commit authority if it is not already granted; this plan does not supply it. With authority, stage only the complete sorted Task 1-10 artifact set by explicit path, verify the staged set and whitespace, and dispatch one independent Reviewer against that exact staged set. Review evidence never supplies a human decision. Any load-bearing finding or byte change blocks activation and returns the affected stage to open work; no automatic review loop or broad cleanup is permitted. If accepted, commit the unchanged staged bytes normally, verify the commit contains exactly the reviewed set, record the commit and review reference in the existing S5/epic closure evidence, then close the completed children and epic with `--actor` attribution. Do not push or sync unless separately authorized.

Verification: `git diff --cached --name-only` equals the declared complete sorted Task 1-10 artifact set; `git diff --cached --check` exits 0; `bd export | python3 scripts/validate_phase_0a_evidence.py --root docs/evidence/phase-0a --beads-jsonl -` exits 0 immediately before review; the independent verdict names the same staged set and no load-bearing finding; after the authorized normal commit, `git show --name-only --format= HEAD` equals that set and `git diff HEAD^ HEAD --check` exits 0; `bd show eqos-3ps` and all five children report closed with the commit and review evidence; `git status --short` preserves unrelated work and shows no unintended staged path.

Dependencies: Task 10

Risks: `HIGH` authority activation. Missing commit authority, staged-path mismatch, review finding, post-review byte change, failed commit, or failed closure leaves S5 and the epic open and Phase 0.5 product implementation blocked.

## Inline self-review

- **Spec coverage:** S1-S5 own `{A-01..A-13}` exactly once at stage grain; Tasks 1-11 cover every happy path, edge case, testing decision, authority boundary, and out-of-scope constraint in the approved spec.
- **Placeholder scan:** The plan contains no deferred implementation marker, unnamed validation, invented provider/tool, or shorthand that requires another task's prose.
- **Name/type consistency:** `SourcePackageInventory -> SourceRightsPackage -> FilingCoverageMatrix -> frozen pre-baseline contracts -> ManualBaselinePackage/BootstrapThesis/SuccessMetricContractFinal -> operating contracts -> Phase0AEvidenceValidator -> Phase0AEvidenceManifest/Phase0AExitRecord -> Phase0AEvidenceCommit` is consistent across every producer and consumer.
- **Gap-naming pass:** Product-owner decision-event binding, analyst suitability, pre-rights digest state, per-source/use rights, post-baseline A-13 targets, A-09 dual authority, fixture authority, measurement failure, source conflicts, cutoff evidence, typed Beads edges, digests, Architecture v2 continuation, integrated review, commit authority, and product-code gating are explicit stop conditions.
- **Right-sizing:** Eleven independently rejectable plan tasks map onto exactly five durable stage Beads. S2, S3, S4, and S5 split at rights/spike, pre/post-baseline, golden-set/identity, operating/validator/manifest/activation boundaries so one Implementer dispatch remains bounded without creating extra Beads or per-file review rounds.
