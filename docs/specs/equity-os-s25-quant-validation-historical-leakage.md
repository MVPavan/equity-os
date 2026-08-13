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
| `register_scope` | enum set | One or both of `E-05`, `E-10`, each with its own valid activation reference. |
| `hypothesis` | typed object | Subject, metric, direction, horizon, universe, materiality, and observable falsifier fixed in advance. |
| `universe_snapshot_id` | identifier | Point-in-time membership with inclusion/exclusion rationale. |
| `feature_set_version` | identifier | Closed feature definitions and allowed availability lags. |
| `target_version` | identifier | Closed outcome definition and horizon. |
| `split_plan` | object | Chronological train/validation/holdout periods and embargo/purge rules. |
| `metrics` | nonempty array | Primary and secondary metrics, uncertainty method, and failure threshold. |
| `budgets` | object | Maximum data, compute, trials, elapsed time, and analyst review. |
| `stop_rules` | nonempty array | Leakage, rights, evidence, multiple-testing, budget, and safety stops. |
| `approval_ids` | typed reference array | Component-scoped and independently resolvable. |

The protocol is content-addressed and frozen before seeing holdout results.
Changes create a new protocol and cannot overwrite the prior one.

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

A finding contains stable ID, protocol/dataset/frame IDs, category, severity,
affected rows and periods, exact evidence, detection rule/version, expected
temporal relation, observed relation, remediation state, reviewer, and
terminal disposition. The closed minimum categories are future-knowledge,
revision/restatement, survivorship, universe-selection, target, feature,
corporate-action, source-availability, label, split/embargo, analyst-memory,
and repeated-holdout leakage.

### `QuantValidationReport`

The report includes the frozen protocol, complete trial registry, dataset and
code hashes, all leakage findings, failed and blocked runs, denominators,
uncertainty, primary and secondary results, analyst review cost, limitations,
and terminal `PASS`, `FAIL`, or `BLOCKED`. `PASS` means only that the approved
validation gate passed; it is not production, causal, regulatory, distribution,
or investment approval.

## Invariants and fail-closed behavior

1. E-05 and E-10 are independently conditional. Each remains dormant unless
   its own typed predicate recomputes `TRUE` and its own active canonical human
   resolution authorizes `ACTIVATE_DEFERRED` for that exact register scope.
2. E-05 activation cannot authorize historical replay under E-10; E-10
   activation cannot authorize quant validation under E-05.
3. A datum may enter a decision frame only when its knowledge time and source
   availability are no later than the simulated decision time, including the
   configured operational lag.
4. Later revisions, restatements, index membership, classifications, and
   corporate-action knowledge MUST NOT replace the version knowable at the
   frame cutoff.
5. Train, validation, and holdout are chronological. Purge and embargo rules
   prevent overlapping labels or feature windows from crossing splits.
6. Hypothesis, universe, features, target, primary metric, thresholds, trial
   budget, and stop rules are frozen before holdout access.
7. Every attempted parameter/model variant is recorded. Failed, abandoned,
   blocked, and null-result trials remain in the denominator.
8. Missing point-in-time evidence yields missing data or `BLOCKED`; it MUST NOT
   be filled from hindsight or a present-day snapshot and described as replay.
9. Deterministic calculations use registered code and calculation traces; an
   LLM never serves as the authoritative calculator.
10. Source-rights uncertainty, hash/lineage failure, entity ambiguity, stale
    activation, budget breach, leakage Important/Critical finding, or missing
    approval blocks the affected run and every dependent conclusion.
11. Dormant mode creates no datasets, credentials, provider calls, compute
    jobs, product-code dependencies, schedules, or execution integration.

## Evidence and typed human-approval gates

| Gate ID | Register scope | Required evidence | Required authority | Fail-closed result |
|---|---|---|---|---|
| `S25-G01-DELEGATED-ARTIFACT` | S25 | Fresh clean Sol xhigh review, source hashes, review round, timestamp, and persisted evidence path | `DELEGATED_ARTIFACT_APPROVAL` under the activated goal | Draft remains unapproved. No approval is recorded here. |
| `S25-G02-E05-ACTIVATION` | E-05 | Current TRUE E-05 predicate digest, evidence, activation record, and matching canonical human-resolution digest | Competent human authorized for exact E-05 `ACTIVATE_DEFERRED` scope | Quant validation remains dormant. |
| `S25-G03-E10-ACTIVATION` | E-10 | Current TRUE E-10 predicate digest, evidence, activation record, and matching canonical human-resolution digest | Competent human authorized for exact E-10 `ACTIVATE_DEFERRED` scope | Historical replay remains dormant. |
| `S25-G04-PROTOCOL` | Activated scope only | Frozen hypothesis, universe, features, target, splits, metrics, trial budget, and stop rules | Analyst/domain owner | Run does not start. |
| `S25-G05-RIGHTS` | Activated scope only | Dataset-specific permitted use, retention, transformation, and derived-output decision | Rights/legal/provider authority as applicable | Dataset is excluded and affected run is blocked. |
| `S25-G06-BUDGET` | Activated scope only | Data, compute, trial, elapsed-time, and analyst-review limits | Human budget/capacity owner | Resource-consuming work does not start. |
| `S25-G07-RESULT` | Activated scope only | Full trial registry, leakage report, uncertainty, failed/blocked runs, and limitations | Analyst/domain owner | Result remains unaccepted evidence. |
| `S25-G08-PRODUCTION` | Activated scope only | Separate security, operational, regulatory, model-risk, and production evidence | Competent human authorities for each declared type | No production use. |
| `S25-G09-DISTRIBUTION` | Activated scope only | Exact content/version, audience, purpose, and legal/regulatory resolution | Competent distribution/legal/regulatory authority | No external or personalized distribution. |

One approval record satisfies one requirement only and is scoped to the named
component. Delegated artifact approval does not satisfy E-05/E-10 activation,
analyst, domain, rights, legal, provider, budget, capacity, security,
operations, model-risk, regulatory, production, or distribution authority.

## Acceptance tests and verification

Before activation:

1. Structural tests prove there is no S25 dataset build, provider route,
   credential, compute job, schedule, runtime dependency, or execution hook.
2. E-05-only approval fails an E-10 operation and E-10-only approval fails an
   E-05 operation; false, unknown, stale, expired, or mismatched proof fails
   both.

After the applicable activation:

3. Synthetic temporal fixtures catch every minimum `LeakageFinding` category,
   including revised filings, post-cutoff index membership, late source
   availability, future corporate actions, overlapping horizons, and repeated
   holdout access.
4. Advancing a source's availability past the frame cutoff removes it from the
   decision frame; substituting a present-day snapshot is rejected.
5. Dataset and replay rebuilds from identical immutable inputs and code produce
   identical hashes; revisions create new versions and preserve old results.
6. Split tests enforce chronology, purge, embargo, and outcome isolation; no
   target-derived transformation enters features.
7. Trial-registry tests account for every attempted run, including failures,
   manual interruptions, budget stops, and null results.
8. Missing rights, lineage, temporal proof, identity, corporate-action version,
   or activation evidence yields `BLOCKED`, not imputation or silent exclusion.
9. Reports state denominators, uncertainty, limitations, all leakage findings,
   and the exact narrow meaning of `PASS`; they make no production, causal,
   trading, or recommendation claim.

Verification evidence MUST contain exact commands, exit statuses, immutable
input/output hashes, protocol and code versions, validator output, timestamps,
and reviewer identity. Conversation text, agent summaries, and matching
ledger-authored labels are not proof.

## Dependencies

- Register authority and a valid activation for each used component, E-05
  and/or E-10.
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

Until the corresponding component is validly activated, permitted work is
limited to authoring, reviewing, and structural verification of this dormant
contract and non-executable synthetic fixtures. No source acquisition, dataset
construction, historical replay, provider call, compute experiment, product
code, runtime configuration, or execution integration is allowed. If only one
of E-05 or E-10 activates, the other remains fully dormant. Neither activation
activates E-02, E-03, or E-04.

## Amendment gate

No evidence-derived provisional amendment gate is assigned to S25 in the
goal's amendment table. Any change to this contract still requires source
reconciliation, disposition reconciliation for M-4 and 6.5, the capped
review/fix policy, a fresh clean Sol xhigh review, and delegated artifact
approval. Activation alone is neither amendment nor approval.
