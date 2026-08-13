# Success metrics, workflow budgets, and operating capacity

**Spec ID:** S08
**Status:** DRAFT — AWAITING FRESH SOL XHIGH REVIEW
**Activation classification:** Active-only
**Exact path:** `docs/specs/equity-os-s08-success-metrics-budgets-capacity.md`

## Contract status and authority

This document defines the implementation contract for S08; it does not freeze
the metrics, commit money or capacity, or accept any register row. The
implementation decision register v2 owns live decision and gate wording. The
disposition report supplies the referenced audit decisions. The activated
goal supplies exact spec ownership. A fresh clean Sol xhigh review can grant
only delegated artifact approval. This draft claims neither that review nor
any human budget, capacity, analyst, or product-owner decision.

### Exact ownership and source text

| Register ID | Blueprint phase | Priority | Decision or action — exact register text | Required evidence / acceptance — exact register text | Dependencies — exact register text | Activation status | Current source status |
|---|---|---:|---|---|---|---|---|
| A-07 | 0A | High | Define initial per-workflow budgets | Ceilings or measurement rules for model cost, tool calls, latency, document volume, retries, and analyst minutes | A-13 | Open | Open |
| A-12 | 0A | High | Define operating calendar, standing budget, and capacity | Weekly builder/analyst capacity, target phase dates, monthly provider/model/infrastructure ceilings, maintenance allowance, and expected company coverage documented | A-01, A-02 | Open | Open |
| A-13 | 0A | Critical | Freeze success-metric contract | Versioned definitions and measurement methods for factual accuracy, citation correctness, numerical traceability, unsupported claims, analyst minutes, per-claim verification time, coverage capacity, latency, cost, failure/retry rate, and phase applicability | A-01 | Open | Open |

The exact program assignment is: **S08 — Success metrics, workflow budgets,
and operating capacity**, with primary register IDs **A-07, A-12, A-13** and
disposition references **M-8, T-1, T-2**. All owned rows were `Open` at the
pinned activation snapshot, so S08 is active-only. It owns no Deferred row.

| Disposition ref | Exact heading | Exact disposition | Binding effect in this contract |
|---|---|---|---|
| M-8 | Results-season throughput | Accept and fold into the success-metric contract. | Track reports per analyst per week, peak-week document/claim volume, backlog age, completion before the next material event, and capacity at the Phase 1 company count. |
| T-1 | Operating budget and calendar disappeared | Accept. | Preserve weekly builder capacity, target phase dates, monthly provider/model/infrastructure ceilings, analyst-review capacity, and maintenance burden separately from per-run ceilings. |
| T-2 | Success metrics are scattered | Accept. | Maintain one versioned contract for definitions, units, measurement procedures, and phase applicability; all phase gates reference it. |

## Scope

S08 defines one versioned metric catalog, per-workflow budget envelopes, and
an operating calendar/capacity plan. It provides a single measurement
vocabulary to the manual baseline, assisted updates, analyst-economics gate,
results-season throughput evaluation, and phase-gate scorecard.

The contract must make every metric reproducible from identified events or
human time records, define missing-data behavior, separate measurement from
threshold approval, and preserve report/company clustering. Numeric targets
are evidence-derived and authority-approved values; this draft does not invent
them.

### Non-goals

- This spec does not select the discovery company, estimate unapproved spend,
  reserve staff time, purchase services, or promise delivery dates.
- It does not define claim materiality, the failure taxonomy, or Phase 1
  company-selection criteria, though it consumes their typed outputs.
- It does not treat three reports as enough for a report-level percentile or
  make causal/statistical-significance claims from clustered claim telemetry.
- It does not let passing cost or latency compensate for factual, citation,
  traceability, unsupported-claim, or human-approval failures.
- It does not convert a documented ceiling into budget or capacity approval.

## Interfaces and data contracts

### `MetricDefinition`

Each catalog entry contains:

| Field | Contract |
|---|---|
| `metric_id`, `version`, `name` | Stable identity, monotonic version, and unambiguous display name. |
| `definition` | Operational meaning, including inclusions and exclusions. |
| `unit` | Exact unit; time identifies clock and pause rules, money identifies currency, and rates identify scale. |
| `numerator`, `denominator` | Required for rates; each resolves to named events or records. |
| `population`, `sampling_rule` | Eligible units, cutoff, exclusions, and missing-record treatment. |
| `aggregation` | Allowed summaries and minimum sample rule; report/company clustering retained. |
| `stratification` | Required dimensions such as workflow mode, company, report, materiality, epistemic class, claim/correction type, and phase. |
| `measurement_method` | Source event schema, deterministic transformation/version, and instrumentation overhead treatment. |
| `phase_applicability` | One or more exact blueprint phases plus gate use; `NOT_APPLICABLE` requires rationale. |
| `threshold` | Nullable until approved; includes direction, value/range, effective version, and authority record. |
| `owner`, `status` | Named measurement owner and `DRAFT`, `APPROVED`, `DEPRECATED`, or `SUPERSEDED`; status requires evidence. |

The initial catalog contains definitions for exactly the register-required
families: factual accuracy, citation correctness, numerical traceability,
unsupported-claim rate, analyst minutes, per-claim verification time, coverage
capacity, latency, cost, and failure/retry rate. Coverage capacity additionally
includes the M-8 throughput measures. Metrics may be more granular, but no
required family may be represented only by a vague proxy.

### Minimum metric semantics

- **Factual accuracy:** disposition against expert-labeled supported facts,
  stratified by materiality and failure/correction category; unresolved truth
  is excluded only under an explicit reviewed rule.
- **Citation correctness:** claim-to-source-location correctness and source
  identity, not merely the presence of a citation token.
- **Numerical traceability:** material numerical claims resolving to a fact or
  registered calculation trace with explicit unit, period, currency, scope,
  definition, and applicable reproducibility class.
- **Unsupported-claim rate:** unsupported claims divided by all eligible
  reviewed claims, with inference/forecast labeling evaluated separately.
- **Analyst minutes:** total report review time and named components such as
  source locating, calculation checking, correction, and approval; instrument
  overhead is separately captured.
- **Per-claim verification time:** review time per eligible claim, retaining
  report/company keys and correction type.
- **Coverage capacity:** reports reviewable per analyst per week, peak-week
  document and claim volume, backlog age, percent completed before the next
  material event, and accepted capacity at the selected Phase 1 company count.
- **Latency:** defined workflow boundary and clock; queue, tool, model, retry,
  and human-wait time are separable.
- **Cost:** model, tool/provider, and infrastructure cost in declared currency
  and allocation method; unknown cost remains unknown.
- **Failure/retry rate:** attempts, terminal failures, retried steps, retry
  cause, and successful recovery, using the S07 taxonomy.

### `WorkflowBudget`

Required fields are `budget_id`, `version`, `workflow_id`, applicable phase,
effective interval, model-cost ceiling or measurement rule, tool-call ceiling
or rule, latency ceiling/rule, document-volume ceiling/rule, retry ceiling/rule,
analyst-minute ceiling/rule, breach action, currency, allocation method,
evidence refs, and budget-approval record. `CEILING_NOT_APPROVED` is distinct
from `NO_LIMIT`; null never means unlimited.

### `OperatingCapacityPlan`

Required fields are `plan_id`, `version`, effective interval, weekly builder
capacity, weekly analyst capacity, target blueprint-phase dates, monthly
provider/model/infrastructure ceilings, maintenance allowance, expected
company coverage, peak-week assumptions, backlog policy, capacity owner,
evidence refs, and approval records. Per-workflow budgets and the standing
plan remain separate objects with explicit links.

### `MetricObservation`

Each observation contains metric/version, phase, run/report/company keys,
population and strata, raw event refs, calculation version, value/unit,
missingness state, instrumentation overhead, captured time, and knowledge
cutoff. Corrections append a superseding observation; no historical result is
silently overwritten.

### Required interfaces

- S07 supplies failure/retry and reviewer-decision telemetry.
- The manual baseline and assisted workflow emit the same timing schema.
- The run manifest supplies model/tool versions, cost, latency, retry, and
  artifact identities.
- The analyst-economics/throughput spec consumes catalog definitions and
  reports actual outcomes without changing them.
- Phase gates reference exact metric IDs and versions plus approved thresholds;
  they do not copy definitions into new prose.

## Invariants and fail-closed behavior

1. Every reported metric resolves to one current versioned definition and its
   raw evidence. An absent definition, unit, population, phase, or method makes
   the result invalid.
2. Unknown, missing, or stale observations are never coerced to zero, success,
   within-budget, or not applicable.
3. A threshold without the required human authority record is unresolved and
   cannot pass a gate.
4. Per-workflow ceilings do not replace the operating calendar, standing
   monthly budget, maintenance allowance, or capacity commitment.
5. Manual and assisted instrumentation is symmetric and its overhead is
   measured. Changes to instrumentation version require a visible break or
   comparable remeasurement.
6. Report/company clustering keys are retained. Claim counts do not become
   independent samples; report-level P90 is forbidden at n=3.
7. Phase applicability is explicit. A metric required by a phase cannot be
   waived through an unreviewed `NOT_APPLICABLE` label.
8. Budget breach stops or blocks the affected workflow according to the
   approved breach action; it cannot be hidden by averaging with other runs.
9. Capacity acceptance uses measured peak-season volume and backlog, not only
   nominal weekly hours.
10. Quality controls do not trade off: favorable cost, latency, acceptance
    rate, or throughput cannot override unsupported claims, bad citations,
    missing traces, or required approvals.

## Evidence and typed approval gates

| Gate | Required proof | Typed authority | Fail-closed result |
|---|---|---|---|
| Delegated spec approval | Fresh clean Sol xhigh review bound to the exact S08 bytes and persisted review evidence | `DELEGATED_ARTIFACT_APPROVAL` | S08 remains draft and cannot authorize dependent implementation. |
| Metric-contract freeze | Versioned catalog, measurement fixtures, phase map, and explicit decision | `PRODUCT_OWNER_DECISION` | A-13 remains unresolved. |
| Analyst measurement fitness | Timed manual/assisted fixture evidence and explicit acceptance of clock/pause/overhead rules | `ANALYST_ACCEPTANCE` | Analyst-economics metrics cannot pass. |
| Per-workflow and standing budget | Exact ceilings/rules, currency, period, breach action, and authority evidence | `BUDGET_APPROVAL` | A-07/A-12 remain unresolved; null is not unlimited. |
| Builder/analyst capacity | Weekly commitments, maintenance allowance, coverage assumptions, effective period, and evidence | `CAPACITY_COMMITMENT` | Capacity and target dates remain planning assumptions, not commitments. |

Provider, purchase, or external-service approvals required by a chosen budget
are separate typed decisions and are not implied by `BUDGET_APPROVAL`.
Every non-delegated record must resolve through the canonical human-review
artifact. One record satisfies one requirement; Sol review supplies no human
budget, capacity, analyst, or product-owner authority.

## Acceptance tests and verification

Verification must prove:

- exact ownership of A-07, A-12, and A-13 and no other register row;
- one current versioned definition for every required metric family;
- deterministic recomputation from fixture events, including numerator,
  denominator, unit, sampling, stratification, and phase applicability;
- rejection of unknown units, missing definitions, missing evidence, stale
  versions, unapproved thresholds, and silent zero/default coercion;
- identical instrumentation schema for manual and assisted workflows and
  explicit overhead measurement;
- rejection of report-level P90 for the three-update pilot and preservation of
  report/company clustering;
- a distinct per-workflow budget and operating capacity plan;
- budget-breach behavior for cost, calls, latency, volume, retries, and analyst
  minutes;
- M-8 peak-week volume, backlog, next-material-event completion, and Phase 1
  company-count capacity measures; and
- current one-to-one typed evidence and approval records for every mandatory
  human gate.

The implementation plan must declare argv-style commands for schema/catalog
validation, fixture recomputation, missing-data and breach tests, and
phase-applicability coverage. Results persist exit code, output evidence,
scope/content hashes, and execution time. A dashboard screenshot or agent
summary is not proof.

## Dependencies and sequencing

- A-13 depends exactly on A-01 and must be versioned before baseline
  measurement is relied upon.
- A-07 depends exactly on A-13 so each workflow budget uses defined measures.
- A-12 depends exactly on A-01 and A-02 so boundary and discovery-slice scope
  constrain dates, spend, capacity, and company coverage.
- S08 consumes S07 telemetry and supplies A-13 definitions to B-13, B-04,
  C-12, and C-18 without taking ownership of those rows.
- Phase 0A cannot exit until the success-metric contract is versioned and
  operating capacity and standing budget are documented.

## Amendment gate

No mandatory evidence-derived amendment gate is assigned to S08 in the
Exact 25-spec program. Metric versions and approved thresholds may evolve
through their normal append-only versioning contract, but a change to source
semantics, ownership, activation classification, or required metric families
requires authority reconciliation and fresh Sol xhigh review.
