Next action: obtain the single HR-0004 authorization in §7. Until then, only the generator-only changes in A are lawful; the goal, validators, human-review artifact, and live ledger remain untouched.

# Ledger r1 remediation design

## Verified baseline

- Active goal SHA-256: `dabad7bfe3d2765a5ac9687376029d8587b4b2ac95bc03494155a974e5ddc67f`.
- Both pinned authorities match:
  - v2 register: `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`.
  - disposition report: `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`.
- Live ledger: `51091042…`; 210 rows = 167 canonical + 43 aliases; 454 existing history entries; 23 finding-linked, human-linked, blocked rows.
- Human-review artifact: `54c1e183…`; HR-0001..3 remain `OPEN_BLOCKING`, with no resolutions.
- Reviewed generator diff remains 193 insertions/59 deletions, base blob `c4b5a5a…`, worktree blob `bbe7e0e…`, reviewed patch SHA-256 `6e20977e…`.
- That diff must not be accepted as-is.

## A. Lawful generator-only fixes now

Only [generate_initial_ledger.py](../../../../scripts/equity_os_blueprint/generate_initial_ledger.py) may change in this lane. It must never mutate activated artifacts.

1. Convert it into a fresh-bootstrap-only writer:

   - Require both `--ledger-path` and `--human-review-path`.
   - Remove canonical defaults and environment-variable fallbacks.
   - Reject either canonical live path, identical targets, or any existing target.
   - Open outputs exclusively; never truncate or overwrite.
   - Build both outputs in memory before writing; remove only files created by the failed invocation on partial failure.
   - Capture one truthful current UTC snapshot timestamp; remove the backdated `SNAPSHOT_AT`.
   - Continue verifying both pinned authority hashes before output.

2. Remove the activated-state rewriter:

   - No live-ledger mode.
   - No live human-review replacement.
   - No history regeneration, blocker clearing, finding clearing, or HR clearing.
   - Any future migration is a separate program requiring HR-0004.

3. Retain the representable r0 corrections:

   - Negative proof wording for `DEF-01..13`.
   - Operating-trigger proof wording for all eight `SCALE-*` rows.
   - Add `AUTH-REG-002` for v2 line 193, `AUTH-REG-003` for line 209, and `ALIAS-044` for line 9.
   - Restore `SCALE-WORKFLOW-01..04.disposition_refs=["M-5"]`.
   - Add the exact non-delegated approvals and command requirements listed below.
   - Fix `PG-2-04.related_register_ids` to `["D-01","D-03"]`.
   - Set `DEF-12.primary_spec=null`.

4. Remove the invalid r1 mechanisms:

   - Remove the owner-set equality assertion.
   - Do not alter semantic register links to manufacture spec-owner equality.
   - Keep `SEQ-01..11` as `PROGRAM_WIDE_ACTIVE_CONTROL`; never use `related_register_ids` for sequence ownership.
   - Do not convert the nine aliases into authority clauses.
   - Do not add delegated artifact approvals to null-owned phase gates.
   - Fail closed with “approved schema reconciliation required” for compound aliases, `PG-1-11`, multi-spec applicability, and threshold-to-measurement predicates until B is authorized.

## B. Goal/schema amendments requiring HR-0004

### 1. Minimal closed schema

Amend the active goal and all three embedded validators as one indivisible contract change.

- `canonical_component_id` becomes a closed union:
  - canonical row: `null`;
  - simple alias: one canonical component-ID string;
  - compound alias: sorted unique array of at least two direct canonical IDs.
  - Alias targets may never be aliases; each target must exist and differ from the alias.

- `human_review_id` becomes a closed union:
  - `null`, one `HR-####` string, or a sorted unique array of at least two IDs.
  - Validators normalize it to a set.
  - This is necessary to add HR-0004 without overwriting HR-0001..3.

- `scope_derivation` gains kind-specific exact fields:
  - `disposition_item`: `applicable_spec_ids`.
  - `sequence_clause`: `source_register_ids` and `applicable_spec_ids`.
  - Other kinds must not contain those keys.
  - `primary_spec`, `applicable_spec_ids`, and `related_register_ids` are independently validated and never derived from one another.

- Add phase-gate rule `ACTIVE_NEGATIVE_CONTROL`:
  - nonempty `related_register_ids`;
  - `authority_effect=null`;
  - `derived_program_disposition=REQUIRED_NOW`;
  - `activation_predicate=null`;
  - applicable only to an authority clause that actively enforces exclusion or separate approval.

- Add predicate expression leaf:
  - `{"op":"COMPARE_METRICS","left_metric_id":…,"comparator":…,"right_metric_id":…}`.
  - Both metrics must have the same type; allowed comparators follow the existing type rules.
  - This permits an observed measurement to be compared with an independently recorded threshold.

- Permit a post-activation omitted component to begin at sequence zero with `AUTHORITY_RECONCILIATION`, `old_value=null`, a full controlled-state `new_value`, and the active HR-0004 resolution. Backdated synthetic activation snapshots remain forbidden.

### 2. Compound-alias targets

Ranges below are inclusive.

| Alias | Exact canonical target set |
|---|---|
| `ALIAS-001` | `DISP-G-1..5`, `DISP-M-1..9` |
| `ALIAS-011` | `DISP-G-1..5` |
| `ALIAS-012` | `DISP-M-1..9` |
| `ALIAS-013` | `DISP-T-1..4` |
| `ALIAS-014` | `DISP-R-1..5` |
| `ALIAS-015` | `DISP-G-1..5`, `DISP-M-1..9`, `DISP-T-1..4`, `DISP-R-1..5` |
| `ALIAS-023` | `REG-A-04` |
| `ALIAS-041` | `DISP-G-5`, `DISP-M-1`, `DISP-M-2`, `DISP-M-4`, `DISP-M-5`, `DISP-M-6`, `DISP-T-2` |
| `ALIAS-043` | `DOC-02`, `DOC-03`, `DISP-G-4`, `DISP-M-1`, `DISP-M-2`, `DISP-M-4`, `DISP-M-5`, `DISP-R-1`, `DISP-6-4`, `DISP-T-2` |

Correct inventory becomes exactly 213 rows: 169 canonical and 44 aliases. Canonical kinds include exactly four authority clauses, not thirteen.

### 3. Exact disposition crosswalks

`applicable_spec_ids` is the user-approved disposition-to-spec crosswalk. `related_register_ids` records source semantics. Neither set may be inferred from the other.

| Item | Exact specs | Exact semantic `related_register_ids` |
|---|---|---|
| G-1 | S06, S11, S16 | A-04, C-08, C-09, C-16 |
| G-2 | S18 | B-04 |
| G-3 | S18 | B-04, C-12 |
| G-4 | S05, S18 | A-02, A-03, B-02, B-04, B-13 |
| G-5 | S06, S13 | A-10, C-04 |
| M-1 | S05 | A-11 |
| M-2 | S12 | B-05, B-11, C-03 |
| M-3 | S13 | B-06, B-12 |
| M-4 | S11, S25 | C-15, E-10 |
| M-5 | S14, S15 | B-01, B-14, C-10 |
| M-6 | S07, S15 | A-08, B-13, C-10 |
| M-7 | S17 | C-17 |
| M-8 | S08, S18 | A-13, C-18 |
| M-9 | S07, S09 | A-08, B-08 |
| T-1 | S08 | A-12 |
| T-2 | S08 | A-13 |
| T-3 | S10 | B-03 |
| T-4 | S01, S02, S04 | A-01, E-08, E-09 |
| R-1 | S19, S20 | D-02 |
| R-2 | S09 | A-06 |
| R-3 | S02 | A-05 |
| R-4 | S06 | A-04 |
| R-5 | S10, S14 | B-03, B-01 |
| 6.1 | S18 | B-04 |
| 6.2 | S06, S13 | A-10, C-04 |
| 6.3 | S17 | C-17 |
| 6.4 | S19, S20 | D-02, D-05 |
| 6.5 | S25 | E-10 |
| 6.6 | S07, S15 | B-13, C-10 |
| 6.7 | S03, S04 | E-06, E-07, E-09 |
| 6.8 | S05 | A-02, B-02 |
| 6.9 | S11, S16 | C-08, C-16 |

For multi-spec dispositions, set `primary_spec=null`; for single-spec dispositions it may remain that single spec. Each applicable spec must have its own exact artifact evidence and delegated approval requirement. The semantic register set must never be padded to reach a spec.

### 4. `PG-1-11`, sequences, and Phase 2 predicates

`PG-1-11`:

- `rule=ACTIVE_NEGATIVE_CONTROL`.
- `related_register_ids=["D-02","D-05","E-03","E-05","E-09"]`.
- `program_disposition=REQUIRED_NOW`.
- `primary_spec=null`.
- No activation predicate and no unrelated `C-11`.
- `PASS` requires each related capability either:
  - still dormant/rejected with current no-implementation proof; or
  - separately activated through its valid register activation record and every source-required approval.
- Any related-scope change invalidates its gate proof.

Sequence crosswalk:

| Clause | `source_register_ids` | `applicable_spec_ids` |
|---|---|---|
| SEQ-01 | A-01 | S01 |
| SEQ-02 | A-05, A-09 | S01, S02 |
| SEQ-03 | A-02, A-06 | S05, S09 |
| SEQ-04 | A-10, A-13 | S06, S08 |
| SEQ-05 | A-04 | S06 |
| SEQ-06 | A-03, A-11 | S05 |
| SEQ-07 | A-04 | S06 |
| SEQ-08 | B-11, B-12 | S12, S13 |
| SEQ-09 | B-01, B-14 | S14 |
| SEQ-10 | B-02 | S14 |
| SEQ-11 | empty | empty |

All eleven retain `PROGRAM_WIDE_ACTIVE_CONTROL`, `related_register_ids=[]`, and `primary_spec=null`. Source-register references do not derive dormancy. Do not auto-create delegated approvals merely from applicability; add one only when an exact eligible spec, roadmap, or JIT-plan artifact is named.

Phase 2 predicate metrics use `MTR-{component}-{FIELD-IN-UPPER-KEBAB}` and the listed JSON fields:

| Gate | Required observable expression |
|---|---|
| PG-2-01 | `benchmark_result_id != ""`; `primary_metric_definition_id != ""`; `precommitted_minimum_improvement > 0`; `observed_primary_improvement >= precommitted_minimum_improvement` |
| PG-2-02 | `test_result_id != ""`; `stale_fixture_count > 0`; `stale_surfaced_count == stale_fixture_count`; `contradiction_fixture_count > 0`; `contradiction_surfaced_count == contradiction_fixture_count` |
| PG-2-03 | `test_result_id != ""`; `promotion_cases_executed > 0`; `sql_metadata_divergence_count == 0`; `partial_write_escape_count == 0` |
| PG-2-04 | For each of `correction`, `deletion`, `backup`, `export`: `{op}_test_result_id != ""`, `{op}_cases_executed > 0`, `{op}_failure_count == 0` |
| PG-2-05 | `burden_measurement_id != ""`; observed `operator_minutes_per_month`, `incidents_per_100_runs`, and `p95_recovery_minutes` are each `<=` their independently stored `precommitted_max_*` metric |
| PG-2-06 | `trigger_policy_id != ""`; `current_engine_decision_id == trigger_policy_engine_decision_id`; `corpus_size_threshold > 0`; `cross_company_graph_query_threshold > 0`; `retrieval_miss_rate_threshold > 0` and `<= 1` |

All use `/phase_gates/pg_2_XX/<field>` in current content-addressed `EVIDENCE_JSON`. Missing evidence or thresholds evaluates `UNKNOWN`; copied booleans such as `*_ready`, `*_improved`, or `*_acceptable` are forbidden.

### 5. Exact validator changes

All three embedded validators and extracted scripts gain path injection:

- Structural: optional paired `--ledger-path` and `--human-review-path`.
- Preimplementation: optional `--ledger-path`.
- Terminal: optional paired `--ledger-path` and `--human-review-path`.
- Neither supplied means canonical live paths.
- Supplying only one of a required pair fails.
- Alternate artifact paths may be absolute; all ledger-contained source/evidence paths remain repo-relative and constrained beneath `--repo-root`.
- Evidence may not target either selected ledger or selected human-review artifact.

Structural invariants must independently enforce:

1. Exact totals: 213 rows, 169 canonical, 44 aliases; kind counts `60/35/13/8/32/4/11/6/44`.
2. Validator-owned exact occurrence manifests for every phase gate, deferral, trigger, disposition, authority, sequence, document-strategy clause, and alias—not generator constants or count-only checks.
3. Exact alias target sets, disposition spec sets, semantic register sets, phase-gate maps, and sequence maps above.
4. Exact top-level and kind-specific key sets; unknown fields fail.
5. No delegated approval without an identified eligible artifact and current artifact evidence.
6. Human-review reverse links normalize the new scalar-or-array representation and preserve multiple independent HR entries.
7. New-component reconciliation histories and existing-history prefix preservation.
8. `extract_goal_validators.py --check` remains byte-exact against the amended goal.

## Proof-inventory corrections

Retain source-required non-delegated approvals:

- Registers:
  - A-07 budget;
  - B-14 analyst;
  - C-14 data rights;
  - C-16 analyst;
  - E-01 budget, capacity, named owner;
  - E-02 capacity;
  - E-03 budget plus distinct post-evaluation-retention product decision;
  - E-04 data rights, budget, named owner;
  - E-05 budget;
  - D-05 distinct `ACTIVATE_DEFERRED` and `ADOPT_MEMORY_APPROACH` scopes.
- Phase gates:
  - PG-05-01 analyst;
  - PG-05-02 analyst;
  - PG-05-05 domain;
  - PG-1-06 analyst;
  - PG-1-09 capacity;
  - PG-2-05 product owner.
- Dispositions:
  - G-1 analyst;
  - M-1 analyst;
  - M-5 analyst.

The six phase gates above receive ordinary component `REVIEW` evidence, not automatic `DELEGATED_ARTIFACT_APPROVAL`.

The exact command-proof set remains:

- `REG-A-10`, `REG-B-01`, `REG-B-11`, `REG-B-14`, `REG-C-08`, `REG-C-15`, `REG-C-16`, `REG-C-17`, `REG-E-01`, `REG-E-10`;
- `PG-05-08`, `PG-1-04`, `PG-1-05`, `PG-1-06`, `PG-2-03`, `PG-2-04`;
- `DISP-G-1`, `DISP-M-4`, `DISP-M-5`, `DISP-M-6`, `DISP-M-7`, `DISP-M-9`, `DISP-6-6`, `DISP-6-9`, `SEQ-09`.

## C. Forbidden live-ledger migration until HR-0004

After authority only, use a separate migrator—not the bootstrap generator.

1. Bind the migration to:

   - current goal hash `dabad7bfe…`;
   - live ledger hash `51091042…`;
   - human-review hash `54c1e183…`;
   - both unchanged authority hashes;
   - the approved remediation-package digest and HR-0004 resolution digest.

   Any mismatch aborts and requires a new reconciliation decision.

2. Exact authority-migration component scope:

   - New: `AUTH-REG-002`, `AUTH-REG-003`, `ALIAS-044`.
   - Alias repairs: `ALIAS-{001,011,012,013,014,015,023,041,043}`.
   - Gates: `PG-05-{01,02,05,08}`, `PG-1-{04,05,06,09,11}`, `PG-2-01..06`.
   - Register/projection rows: `REG-A-{07,10}`, `REG-B-{01,11,14}`, `REG-C-{08,11,14,15,16,17}`, `REG-D-{01,05}`, `REG-E-{01,02,03,04,05,10}`.
   - `DEF-01..13`.
   - `SCALE-SQLITE-01..04`, `SCALE-WORKFLOW-01..04`.
   - All 32 `DISP-*` rows.
   - `SEQ-01..11`.

3. Exact mutable fields are limited to:

   - `canonical_component_id`;
   - `primary_spec`;
   - `scope_derivation`;
   - `activation_predicate`;
   - `disposition_refs`;
   - derived `gate_refs` on `REG-C-11`, `REG-D-01`, `REG-D-05`;
   - `required_approvals`, `required_evidence`, and current evidence refs;
   - safe delivery reset for wrongly spec-owned `DEF-12`;
   - `human_review_id`;
   - appended transition entries and `transition_history_sha256`.

   Source statuses, activation statuses, source text, register ownership, Beads/work references, open findings, blockers, security links, and unrelated proof state remain unchanged.

4. Preserve history:

   - Every one of the existing 454 transition entries remains byte-identical and in the same order.
   - Existing histories are exact prefixes of migrated histories.
   - Existing rows receive only appended transitions with truthful current UTC timestamps, current old/new evidence, HR-0004 decision ID/digest, and the previous terminal hash.
   - New rows start with authorized sequence-zero `AUTHORITY_RECONCILIATION`; never backdate them.
   - HR-0001..3 JSON objects, scopes, evidence, states, empty resolution lists, component links, findings, and blocked histories remain intact.
   - Components overlapping HR-0004 use arrays such as `["HR-0001","HR-0004"]`; HR-0001 is never replaced.

5. Refresh stale artifact evidence separately and append-only:

   - Recompute the live stale set at execution time.
   - Append versioned evidence references; do not rewrite old evidence objects.
   - Reset affected completed reviews/proof to pending or unresolved if necessary.
   - Do not treat refreshed bytes as approval or delivery evidence.

6. Validate temporary artifacts first with injected paths. Required result:

   - Structural, preimplementation-applicable structural checks, and extraction synchronization pass.
   - Exact 213/169/44 inventory.
   - Every existing history is an exact prefix.
   - The existing 23 findings, blocked rows, and prior HR links remain.
   - HR-0001..3 remain open and unresolved.
   - No Deferred row activates; no product delivery advances.
   - Only then may the canonical ledger and human-review files be replaced as one rollback-capable migration transaction.

## HR-0004 authority decision

One HR-0004 can lawfully cover the whole amendment and migration because they form one indivisible authority-reconciliation package, not multiple product decisions. It is lawful only if the same package introduces multi-valued `human_review_id`; under the current singular-link schema alone, the answer is no because overlapping components would have to overwrite HR-0001..3.

Recommended exact question:

> Does the current user approve HR-0004 as one `RECONCILE_AUTHORITY` decision for the content-digested ledger-r1 remediation package, authorizing only: (1) the closed goal/schema and validator amendments specified in that package; and (2) one hash-bound, append-only migration of live ledger SHA-256 `51091042dae87d2f41fbbf02d77ab1619c6a1008a022baec4233c44a0e295e13` and human-review SHA-256 `54c1e183def8e0b1b91504effbf20c233b3d1352fd65d4910e89c2b913ee5702` to the exact 169-canonical/44-alias model, while preserving all 454 existing transition entries and HR-0001..3, changing no pinned blueprint bytes or register Status cells, activating no Deferred capability, advancing no delivery state, and aborting on any precondition-hash mismatch?

Recommendation: approve that exact package only. Safe default: harden the bootstrap generator under A, leave the goal, validators, human-review artifact, and live ledger unchanged, and keep product implementation blocked.
