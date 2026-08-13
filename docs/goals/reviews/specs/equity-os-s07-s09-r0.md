# S07–S09 independent review — r0

**Batch verdict: ISSUES_FOUND — delegated goal approval withheld.**

- **Reviewer:** `gpt-5.6-sol/xhigh`
- **UTC time:** `2026-08-13T02:35:26Z`
- **Committed spec baseline:** `fa4cd53`
- **Review round:** `r0`
- **Approval semantics:** `CLEAN` would grant delegated goal approval only, never personal user approval.

## Content binding

| Role | Artifact | Current on-disk SHA-256 |
|---|---|---|
| Authority, reviewed lines 129–870 | `docs/goals/equity-os-blueprint-completion.md` | `dabad7bfe3d2765a5ac9687376029d8587b4b2ac95bc03494155a974e5ddc67f` |
| Authority | `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| Authority | `docs/blueprint/funda-third-order-review-disposition-report.md` | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| Target S07 | `docs/specs/equity-os-s07-golden-set-failure-reviewer-controls.md` | `184f7f449205be932a855e95b39d8900b222a185afdc683d615b7989601e807c` |
| Target S08 | `docs/specs/equity-os-s08-success-metrics-budgets-capacity.md` | `42ecf1bc96542c5b242baf5912942d0df49d4a4f721dfe9160dc03e2055a5ef5` |
| Target S09 | `docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md` | `d560f81b4752faf61fb02bb0565c92c6a7432c7331e77be7873643c3420f1714` |

## S07 — ISSUES_FOUND

Exact title, path, ownership, source text, dependencies, statuses, activation classification, and disposition references match the authorities.

### Critical

None.

### Important

1. **S07-I1 — Known-case outcome schema cannot represent the required edit/defer cases.**
   **Load-bearing:** Yes.
   `decision`, expected decision, and observed decision admit `ACCEPT`, `EDIT`, `REJECT`, and `DEFER`, but `outcome` admits only accept/reject outcomes. A correct `EDIT` or `DEFER` therefore has no defined outcome without coercion. The acceptance tests likewise require only false-accept/false-reject aggregation, omitting M-6’s explicit edit/reject accuracy requirement.
   Locations: [S07:114](docs/specs/equity-os-s07-golden-set-failure-reviewer-controls.md:114), [S07:121](docs/specs/equity-os-s07-golden-set-failure-reviewer-controls.md:121), [S07:197](docs/specs/equity-os-s07-golden-set-failure-reviewer-controls.md:197), [disposition:216](docs/blueprint/funda-third-order-review-disposition-report.md:216).

2. **S07-I2 — Promotion policy conflicts for real-source golden fixtures.**
   **Load-bearing:** Yes.
   `promotion_eligible=false` is mandatory only for synthetic or seeded cases, while the required interface says promotion and publication reject all golden/shadow fixtures. The invariant and tests then narrow enforcement back to synthetic/seeded artifacts. The contract consequently has no deterministic rule for a `REAL_SOURCE` golden fixture or its test-run artifacts.
   Locations: [S07:75](docs/specs/equity-os-s07-golden-set-failure-reviewer-controls.md:75), [S07:87](docs/specs/equity-os-s07-golden-set-failure-reviewer-controls.md:87), [S07:143](docs/specs/equity-os-s07-golden-set-failure-reviewer-controls.md:143), [S07:161](docs/specs/equity-os-s07-golden-set-failure-reviewer-controls.md:161).

3. **S07-I3 — A-08’s owner/location/cadence contract lacks a machine-readable interface and explicit acceptance assertion.**
   **Load-bearing:** Yes.
   The exact authority requires a named owner, repository location, review cadence, and initial cases. The draft declares a human gate but defines no golden-set manifest or equivalent record carrying those fields, and the acceptance-test inventory does not assert owner, location, or cadence. Typed evidence alone does not define the implementation interface.
   Locations: [S07:23](docs/specs/equity-os-s07-golden-set-failure-reviewer-controls.md:23), [S07:69](docs/specs/equity-os-s07-golden-set-failure-reviewer-controls.md:69), [S07:175](docs/specs/equity-os-s07-golden-set-failure-reviewer-controls.md:175), [S07:186](docs/specs/equity-os-s07-golden-set-failure-reviewer-controls.md:186).

### Minor

None.

## S08 — ISSUES_FOUND

Exact title, path, ownership, source text, dependencies, statuses, activation classification, and disposition references match the authorities.

### Critical

None.

### Important

1. **S08-I1 — `MetricObservation` cannot implement its declared append-only supersession semantics.**
   **Load-bearing:** Yes.
   The record has neither a stable observation ID nor a `supersedes_observation_id`, yet corrections must append a superseding observation. Consumers therefore cannot unambiguously replay corrections, select the current observation, or prove that historical results were not silently replaced.
   Location: [S08:134](docs/specs/equity-os-s08-success-metrics-budgets-capacity.md:134).

2. **S08-I2 — A-07’s permitted measurement-rule path is incorrectly forced through `BUDGET_APPROVAL`.**
   **Load-bearing:** Yes.
   A-07 explicitly permits either ceilings **or measurement rules**. The draft nevertheless requires a budget-approval record on every `WorkflowBudget` and applies `BUDGET_APPROVAL` jointly to A-07 and A-12. That invents financial authority for a measurement-only contract and can block an authority-compliant A-07 resolution. Applicability needs a typed split between measurement-rule authorization and actual budget commitment.
   Locations: [S08:22](docs/specs/equity-os-s08-success-metrics-budgets-capacity.md:22), [S08:116](docs/specs/equity-os-s08-success-metrics-budgets-capacity.md:116), [S08:186](docs/specs/equity-os-s08-success-metrics-budgets-capacity.md:186).

3. **S08-I3 — Phase-gate threshold applicability is overbroad and mechanically undefined.**
   **Load-bearing:** Yes.
   Thresholds are nullable until approved, but the interface says phase gates reference metric versions “plus approved thresholds.” Many authoritative phase gates are qualitative and require no threshold. The contract must distinguish metric references from threshold-bearing predicates and state that only gates whose predicates use thresholds require approved threshold records.
   Locations: [S08:79](docs/specs/equity-os-s08-success-metrics-budgets-capacity.md:79), [S08:150](docs/specs/equity-os-s08-success-metrics-budgets-capacity.md:150), [register-v2:124](docs/blueprint/funda-blueprint-implementation-decision-register-v2.md:124).

### Minor

None.

## S09 — ISSUES_FOUND

Exact title, path, ownership, source text, dependencies, statuses, mixed activation classification, and disposition references match the authorities. C-14 is correctly retained as Deferred, but its activation mechanics are not yet approvable.

### Critical

None.

### Important

1. **S09-I1 — C-14 invokes the wrong reconciliation class for a status-only activation.**
   **Load-bearing:** Yes.
   The draft requires “authority reconciliation” before C-14 planning. The goal reserves `AUTHORITY_RECONCILIATION` for source, ownership, or contract changes; a legal Deferred-status transition instead uses `STATUS_SOURCE_RECONCILIATION` with activation authority. Requiring the wrong transition class makes the activation record inconsistent with the governing state machine.
   Locations: [S09:197](docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:197), [S09:206](docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:206), [goal:622](docs/goals/equity-os-blueprint-completion.md:622), [goal:629](docs/goals/equity-os-blueprint-completion.md:629).

2. **S09-I2 — The typed C-14 predicate cannot mechanically enforce rights validity or official-source status.**
   **Load-bearing:** Yes.
   The predicate expression has one Boolean leaf reading `/official_audio_transcription_required`. The surrounding prose additionally says expired rights and non-official sources force `FALSE` or `UNKNOWN`, but neither condition appears as a metric/expression operand and no `valid_until` binding to the underlying rights expiry is specified. A still-current hashed JSON Boolean could therefore remain `TRUE` after rights expiry.
   Locations: [S09:182](docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:182), [S09:190](docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:190), [goal:270](docs/goals/equity-os-blueprint-completion.md:270), [goal:299](docs/goals/equity-os-blueprint-completion.md:299).

3. **S09-I3 — Provider authorization uses an untyped “where applicable” escape.**
   **Load-bearing:** Yes.
   The acquisition gate conditionally requires `PROVIDER_AUTHORIZATION` without defining the mechanically evaluated applicability source or fail-closed default. The data contracts expose a rights-policy reference but no provider-authorization-required field. A missing provider record can therefore be interpreted either as inapplicable or unresolved.
   Locations: [S09:95](docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:95), [S09:218](docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:218), [S09:225](docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:225).

4. **S09-I4 — B-09 requires S17-owned identities despite declaring only A-05 as its dependency.**
   **Load-bearing:** Yes.
   `CaptureEvent` requires internal entity/security references, and the interface says S17 supplies those identities. S17 is later Phase-1 scope, while B-09 depends exactly on A-05 and must start during Phase 0.5. Although prose says unresolved mappings are retained, the event schema provides no nullable/raw-identity representation. B-09 therefore cannot produce a conforming record before S17 without adding an undeclared dependency.
   Locations: [S09:113](docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:113), [S09:152](docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:152), [S09:274](docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:274).

### Minor

None.

## Batch consistency verdict

**ISSUES_FOUND.**

The batch correctly preserves:

- disjoint primary ownership and exact register text;
- current `Open`/`Deferred` statuses;
- S07/S08 active-only and S09 mixed classification;
- declared disposition coverage;
- absence of mandatory evidence-derived amendment gates for S07–S09.

It fails batch approval because S07’s telemetry contract is incomplete for S08 consumption, S09 introduces an undeclared S17 prerequisite into active B-09 scope, and C-14’s reconciliation and predicate mechanics conflict with the governing goal.

## Overall verdict

**ISSUES_FOUND — S07, S08, and S09 all require correction and a fresh review round before any can receive delegated goal approval. No personal user approval is claimed or implied.**