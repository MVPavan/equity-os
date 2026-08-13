# S22–S25 Independent Review — r0

- **Reviewer:** `gpt-5.6-sol`
- **Effort:** `xhigh`
- **UTC time:** `2026-08-13T02:34:59Z`
- **Committed spec baseline:** `fa4cd53`
- **Review round:** `r0`
- **Approval semantics:** `CLEAN` would grant delegated goal approval only, never personal user approval. No target is CLEAN in this round.

## On-disk SHA-256 bindings

| Role | File | SHA-256 |
|---|---|---|
| Authority, reviewed lines 129–870 | `docs/goals/equity-os-blueprint-completion.md` | `dabad7bfe3d2765a5ac9687376029d8587b4b2ac95bc03494155a974e5ddc67f` |
| Authority | `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| Authority | `docs/blueprint/funda-third-order-review-disposition-report.md` | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| Target S22 | `docs/specs/equity-os-s22-conditional-stress-test-companies.md` | `d96a79de0a2ee3256e1440e025883b9fe987eeee4de618fccf55f539a3b02bf9` |
| Target S23 | `docs/specs/equity-os-s23-conditional-bull-bear-forensic-review.md` | `a951417ad6f284a51c4472d4df93fd01dbeb68c57da14cf8c12d3ce1a395d022` |
| Target S24 | `docs/specs/equity-os-s24-conditional-event-monitoring.md` | `74adf2f9de335ddb2c7390858aa2eb5395d93736446431fa13526dc13705c365` |
| Target S25 | `docs/specs/equity-os-s25-quant-validation-historical-leakage.md` | `5ea88c54bf4b93b3a96787a7b1533d5f20e453e3c753519f303b65586dac7c48` |

## Per-spec verdicts

| Spec | Verdict | Blocking findings |
|---|---|---|
| S22 | **ISSUES_FOUND** | C-01, I-01, I-02 |
| S23 | **ISSUES_FOUND** | C-02, I-01, I-02 |
| S24 | **ISSUES_FOUND** | C-03, I-01, I-02, I-03 |
| S25 | **ISSUES_FOUND** | C-04, C-05, C-06, I-01, I-02, I-04 |

## Critical findings

### C-01 — S22 can pass without the three mandatory stress-test archetypes

**Load-bearing:** YES

The E-02 authority requires exactly one bank/NBFC, one conglomerate, and one difficult disclosure/corporate-action case (`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md:110`). S22 instead permits any nonempty candidate set drawn from generic stress dimensions, and its tests require only coverage of whatever dimensions were declared. It therefore permits a passing evaluation that omits one or all source-mandated archetypes.

Evidence: `docs/specs/equity-os-s22-conditional-stress-test-companies.md:65-70`, `docs/specs/equity-os-s22-conditional-stress-test-companies.md:138-148`.

### C-02 — S23 does not enforce E-03’s authoritative comparison and retention rule

**Load-bearing:** YES

E-03 requires comparison against a **single senior-reviewer baseline** and permits retention only when incremental valid-issue detection justifies cost (`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md:111`). S23 defines only runs “without the challenged method,” leaves `success_rules` open-ended, and reports incremental findings and analyst minutes without making the source retention rule mandatory. A different baseline or success rule could therefore produce `PASS`.

Evidence: `docs/specs/equity-os-s23-conditional-bull-bear-forensic-review.md:46-59`, `docs/specs/equity-os-s23-conditional-bull-bear-forensic-review.md:79-85`, `docs/specs/equity-os-s23-conditional-bull-bear-forensic-review.md:144-147`.

### C-03 — S24 omits the defining E-04 alert and immaterial-event acceptance semantics

**Load-bearing:** YES

E-04 requires every alert to identify which fact, assumption, catalyst, promise, falsifier, or thesis breaker changed, and requires immaterial events not to rewrite the thesis (`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md:112`). `AlertCandidate` has only optional thesis/claim IDs and an observable falsifier. Neither its schema, invariants, nor tests require the complete affected-target classification or prohibit promotion of an immaterial event.

Evidence: `docs/specs/equity-os-s24-conditional-event-monitoring.md:69-75`, `docs/specs/equity-os-s24-conditional-event-monitoring.md:99-105`, `docs/specs/equity-os-s24-conditional-event-monitoring.md:135-148`.

### C-04 — S25 omits mandatory E-05 fees, liquidity, and benchmark disclosures

**Load-bearing:** YES

E-05 requires point-in-time data plus disclosure of leakage, revisions, universe history, fees, liquidity, and benchmark (`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md:113`). S25 covers the first four areas but does not require fees, liquidity assumptions, or a benchmark in the protocol, report, invariants, or acceptance tests. Its report could therefore pass while omitting three authoritative acceptance items.

Evidence: `docs/specs/equity-os-s25-quant-validation-historical-leakage.md:55-73`, `docs/specs/equity-os-s25-quant-validation-historical-leakage.md:103-110`, `docs/specs/equity-os-s25-quant-validation-historical-leakage.md:170-188`.

### C-05 — S25 does not implement E-10, M-4, and 6.5 model-weight-leakage controls

**Load-bearing:** YES

The authorities require:

- disclosure of model-weight leakage as an uncontrollable historical limitation;
- historical LLM results not being presented as clean alpha evidence;
- separation of that limitation from controllable store/tool leakage.

S25’s leakage taxonomy contains `analyst-memory` but not model-weight leakage. Its generic limitations field and narrow `PASS` disclaimer do not mandate the required disclosure or the clean-alpha prohibition.

Evidence: `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md:118`; `docs/blueprint/funda-third-order-review-disposition-report.md:182-195`, `docs/blueprint/funda-third-order-review-disposition-report.md:371-373`; `docs/specs/equity-os-s25-quant-validation-historical-leakage.md:93-110`, `docs/specs/equity-os-s25-quant-validation-historical-leakage.md:186-193`.

### C-06 — S25 permits E-05 operation while its mandatory E-10 dependency remains dormant

**Load-bearing:** YES

The register makes E-05 depend on both B-09 and E-10 (`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md:113`). S25 permits `register_scope` to contain E-05 alone and explicitly permits only one of E-05/E-10 to activate while the other remains fully dormant. Independent activation records are correct, but E-05 active work must still fail closed until E-10’s dependency state is satisfied.

Evidence: `docs/specs/equity-os-s25-quant-validation-historical-leakage.md:61-70`, `docs/specs/equity-os-s25-quant-validation-historical-leakage.md:114-118`, `docs/specs/equity-os-s25-quant-validation-historical-leakage.md:217-223`.

## Important findings

### I-01 — All four authority inventories omit exact register-row semantics

**Load-bearing:** YES

The authority tables correctly reproduce each spec ID, title, path, owner IDs, disposition assignments, and dormant-only classification. They do not reproduce the owned row’s exact priority, decision text, required evidence, dependencies, or `Deferred` source status. Their dependency sections also use broad spec references instead of declaring the exact register dependency edges.

Affected locations:

- S22: `docs/specs/equity-os-s22-conditional-stress-test-companies.md:14-26`, `docs/specs/equity-os-s22-conditional-stress-test-companies.md:154-165`
- S23: `docs/specs/equity-os-s23-conditional-bull-bear-forensic-review.md:14-26`, `docs/specs/equity-os-s23-conditional-bull-bear-forensic-review.md:153-165`
- S24: `docs/specs/equity-os-s24-conditional-event-monitoring.md:14-25`, `docs/specs/equity-os-s24-conditional-event-monitoring.md:154-168`
- S25: `docs/specs/equity-os-s25-quant-validation-historical-leakage.md:15-28`, `docs/specs/equity-os-s25-quant-validation-historical-leakage.md:195-213`

This omission contributed directly to C-01 through C-06.

### I-02 — Approval gates are not declared using the closed approval-type vocabulary

**Load-bearing:** YES

The goal requires explicit, one-to-one approval requirements using its closed `approval_type` vocabulary. The specs instead use compound or conditional prose such as “analyst/domain owner,” “rights/legal/provider authority as applicable,” and “operations/capacity owner.” These do not mechanically distinguish separate `ANALYST_ACCEPTANCE`, `DOMAIN_EXPERT_ACCEPTANCE`, `PROVIDER_AUTHORIZATION`, `DATA_RIGHTS_APPROVAL`, `LEGAL_REVIEW`, `CAPACITY_COMMITMENT`, and related requirements.

S25 additionally requires “model-risk” and “operational” authority without mapping them to an existing closed type or invoking the required vocabulary-reconciliation path.

Affected locations:

- S22: `docs/specs/equity-os-s22-conditional-stress-test-companies.md:111-124`
- S23: `docs/specs/equity-os-s23-conditional-bull-bear-forensic-review.md:109-123`
- S24: `docs/specs/equity-os-s24-conditional-event-monitoring.md:107-122`
- S25: `docs/specs/equity-os-s25-quant-validation-historical-leakage.md:141-158`

Governing contract: `docs/goals/equity-os-blueprint-completion.md:461-520`, `docs/goals/equity-os-blueprint-completion.md:826-843`.

### I-03 — S24’s activation configuration cannot bind its required approvals

**Load-bearing:** YES

`MonitoringActivationConfig` binds sources, destinations, budgets, and a kill-switch owner but contains no typed approval-reference collection. The runtime configuration therefore lacks a specified content-bound link to the source-rights, credential, operations, ruleset, destination, and distribution approvals that gate those fields.

Evidence: `docs/specs/equity-os-s24-conditional-event-monitoring.md:45-60`, `docs/specs/equity-os-s24-conditional-event-monitoring.md:107-122`.

### I-04 — S25 has no typed per-register activation-reference mapping

**Load-bearing:** YES

`register_scope` is typed as an enum set while its contract says each selected register has its own activation reference. An enum set cannot itself carry the referenced activation-record IDs, and no separate mapping field exists. This makes independent E-05/E-10 activation binding under-specified even apart from C-06.

Evidence: `docs/specs/equity-os-s25-quant-validation-historical-leakage.md:55-70`.

## Minor findings

### M-01 — S23’s evidence-package cardinality is ambiguous

**Load-bearing:** NO

The protocol has multiple `case_ids` but declares a singular `evidence_package_id` whose type is described as “identifier per case.” It should be an exact case-to-package mapping or a typed per-case record so completeness and byte-identity can be validated mechanically.

Evidence: `docs/specs/equity-os-s23-conditional-bull-bear-forensic-review.md:53-56`.

## Batch-consistency assessment

The batch is consistent in several important respects:

- exact spec IDs, titles, paths, owner IDs, and assigned disposition references match the 25-spec table;
- all four artifacts remain explicitly `DRAFT` and claim no delegated or personal approval;
- all four correctly classify themselves as dormant-only;
- delegated artifact approval alone cannot activate a component;
- the deferred guards prohibit product implementation and live external activity before valid activation;
- sibling Deferred components are not implicitly activated;
- pre-activation and post-activation negative tests are present;
- no evidence-derived provisional amendment gate is incorrectly assigned.

The batch nevertheless fails because the same authority-inventory and approval-typing defects recur across all four specs, while each spec has at least one source acceptance or dependency defect capable of producing false acceptance.

## Batch verdict

**ISSUES_FOUND — BLOCKED**

S22–S25 are not batch-consistent with the complete authoritative acceptance and dependency contracts. The load-bearing Critical and Important findings block delegated approval and every affected implementation cone.

## Overall verdict

**ISSUES_FOUND**

No target receives `CLEAN` or delegated goal approval at `r0`. No personal user approval is asserted or implied.