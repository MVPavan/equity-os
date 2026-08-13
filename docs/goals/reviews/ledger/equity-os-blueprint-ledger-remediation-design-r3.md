# Ledger authority and remediation design r3

Next action: obtain a clean independent Sol xhigh review of this exact file. If
and only if the verdict is `CLEAN`, the orchestrator may compute its SHA-256 and
ask the exact decision question in [Pre-approval package](#pre-approval-package).
No canonical mutation, HR-0004 entry, resolution, migration code, Beads change,
staging, commit, or push is authorized before the current user answers that
question affirmatively.

## 1. Status, failure corrected, and authority boundary

This document supersedes the operational design in r2; it does not approve r2,
amend the active goal, or authorize a migration. It corrects two independent
review findings:

1. **No self-invalidating preapproval write.** The canonical goal, ledger, and
   human-review artifact stay byte-identical through independent review and the
   user's decision. Approval is recorded externally in conversation first and
   is bound to this r3 file's reviewed SHA-256 plus every immutable pre-state
   hash. Only one later atomic authority transaction may change canonical
   files.
2. **No partial HR-0004 scope.** HR-0004 is created and resolved inside that
   transaction. Its structured `component_ids` is the exact full 144-ID
   transaction target: 141 affected existing IDs plus the three new IDs.
   The user approves that immutable set before it exists in the canonical
   artifact; the post-transaction validator evaluates it against the complete
   post-transaction inventory. No later scope expansion is permitted.

Current-user approval is necessary but not sufficient. It authorizes one
bounded transaction only after a clean independent review; the migrator must
still satisfy every precondition and every temporary-artifact validator. A
reviewer, coordinator, generator, migrator, or validator cannot substitute for
the user's authority.

## 2. Verified immutable pre-transaction baseline

These hashes are the transaction preconditions, not hashes the resulting files
must retain:

| Input | Required SHA-256 |
|---|---|
| Active goal | `dabad7bfe3d2765a5ac9687376029d8587b4b2ac95bc03494155a974e5ddc67f` |
| Canonical component ledger | `51091042dae87d2f41fbbf02d77ab1619c6a1008a022baec4233c44a0e295e13` |
| Canonical human review | `54c1e183def8e0b1b91504effbf20c233b3d1352fd65d4910e89c2b913ee5702` |
| v2 register authority | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| Disposition-report authority | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |

The canonical ledger pre-state is exactly:

- 210 rows: 167 canonical and 43 aliases;
- kind counts `60/35/13/8/32/2/11/6/43` in this order:
  `register_row`, `phase_gate_clause`, `first_release_deferral`,
  `scale_trigger`, `disposition_item`, `authority_clause`,
  `sequence_clause`, `document_strategy_clause`, `derivative_alias`;
- 454 transition objects; the canonical-JSON digest of the map from sorted
  component ID to its ordered transition array is
  `d4ce9646438d388bf26c8faa82d689209296726af2c29d1e56942218c613d9b1`;
- 45 `Open` and 15 `Deferred` register rows; zero activation records;
- dispositions: 145 `REQUIRED_NOW`, 21 `CONDITIONAL_UNACTIVATED`, one
  `REJECTED_ACCOUNTED`, and 43 `DERIVATIVE_ALIAS`;
- delivery: 100 `SPEC_DRAFT`, 23 `REVIEW_BLOCKED`, and 87 `INVENTORIED`;
  every `gate_result` is `NOT_EVALUATED`;
- 23 rows with findings, blockers, and human-review links; HR-0001, HR-0002,
  and HR-0003 are all `OPEN_BLOCKING`, have empty resolution lists, and the
  human-review payload has no resolutions; and
- 106 stale `FILE_BYTES` evidence references. They all point to 21 spec files
  whose current bytes are newer than the recorded r0 bytes. They are a known
  structural-validation blocker, not permission to invent approval or delivery
  evidence.

The ledger and human-review hashes above equal their `HEAD` bytes. Any dirty
path outside this transaction belongs to another owner and must remain
untouched.

## 3. Corrected target model

### 3.1 Exact inventory

The post-transaction inventory is exactly 213 rows: 169 canonical and 44
aliases, with exact kind counts `60/35/13/8/32/4/11/6/44` in the order used
above. The three new IDs are `AUTH-REG-002`, `AUTH-REG-003`, and `ALIAS-044`.
The canonical authority clauses are exactly:

- `AUTH-REG-001`: register line 23;
- `AUTH-DISP-001`: disposition line 41;
- `AUTH-REG-002`: register line 193, the operating-note rule; and
- `AUTH-REG-003`: register line 209, the technology-neutrality rule.

The nine summary passages r2 incorrectly risked promoting remain aliases, not
new authority clauses. This is supported by the disposition report's repeated
executive/final-summary structure and the active goal's rule that repeated
summaries are aliases. `ALIAS-044` accounts for the register-purpose
restatement at line 9.

### 3.2 Minimal closed schema amendments

The goal and all three embedded validators must adopt these closed changes:

- `canonical_component_id` is exactly one of: `null` for a canonical row; a
  canonical component-ID string for a simple alias; or a sorted unique array
  of at least two direct canonical component IDs for a compound alias. Every
  target must exist in the same post-state, must not be an alias, and must not
  be the source alias.
- `human_review_id` is exactly one of: `null`; one `HR-####` string; or a sorted
  unique array of at least two IDs. All validators normalize it to a set before
  forward and reverse-link checks. Transition replay permits only append-only
  link growth: `null -> string`, `null -> sorted array`, or an existing string
  or array -> a sorted array whose exact prefix-normalized set is the old set
  plus new IDs. Removing or replacing a prior HR ID fails.
- Human-review `scope.component_ids` may name canonical or alias IDs. Scope
  validation first checks direct IDs against the complete post-state ledger ID
  set. Canonical IDs participate in bidirectional component-local HR linking;
  aliases remain direct resolution-bound scope members but keep
  `human_review_id=null` under the alias schema. Register/spec/Bead projections
  still yield canonical IDs only. This is the closed representation needed for
  one decision to authorize compound-alias repair without pretending an alias
  is deliverable scope.
- `scope_derivation` has exact kind-specific key sets. A `disposition_item`
  adds `applicable_spec_ids`; a `sequence_clause` adds
  `source_register_ids` and `applicable_spec_ids`; every other kind rejects
  those keys. All such arrays are sorted and unique. `primary_spec`,
  applicability, and semantic register relations are independently validated.
- `ACTIVE_NEGATIVE_CONTROL` is allowed only for `phase_gate_clause`. It
  requires nonempty exact `related_register_ids`, `authority_effect=null`,
  `derived_program_disposition=REQUIRED_NOW`, and
  `activation_predicate=null`. Its gate proof is invalidated by any related
  register state, activation, rejection, approval, or no-implementation-proof
  change.
- Predicate expressions add the exact leaf
  `{"op":"COMPARE_METRICS","left_metric_id":...,"comparator":...,"right_metric_id":...}`.
  Both referenced metrics must exist and share one value type. Boolean/string
  operands allow `EQ` and `NE`; numeric operands additionally allow `GT`,
  `GTE`, `LT`, and `LTE`. An unresolved operand yields `UNKNOWN` under the
  existing three-valued rules.
- A genuinely omitted post-activation component may begin at sequence zero
  only with `transition_type=AUTHORITY_RECONCILIATION`,
  `field=CONTROLLED_STATE`, `old_value=null`, and its full controlled-state
  `new_value`, bound to the active HR-0004 `RECONCILE_AUTHORITY` resolution.
  It uses the transaction timestamp and current evidence. A synthetic or
  backdated `ACTIVATION_SNAPSHOT` is forbidden.

Every digest projection in the structural, preimplementation, and terminal
validators must include the new kind-specific fields and normalized HR-link
representation. Exact top-level and nested key equality is mandatory; a
superset check is insufficient.

### 3.3 Exact alias targets

All aliases retain their current simple target except these exact repairs:

| Alias | Exact target or sorted target set |
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
| `ALIAS-044` | `AUTH-REG-001` |

Ranges are inclusive and expand in lexical numeric order. The validator owns
the full 44-alias occurrence-and-target manifest; it does not import generator
constants.

### 3.4 Exact disposition crosswalk

`applicable_spec_ids` is artifact applicability. `related_register_ids` is
source semantics. Neither may be padded or inferred from the other.

| Item | Exact `applicable_spec_ids` | Exact `related_register_ids` |
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
| R-5 | S10, S14 | B-01, B-03 |
| 6.1 | S18 | B-04 |
| 6.2 | S06, S13 | A-10, C-04 |
| 6.3 | S17 | C-17 |
| 6.4 | S19, S20 | D-02, D-05 |
| 6.5 | S25 | E-10 |
| 6.6 | S07, S15 | B-13, C-10 |
| 6.7 | S03, S04 | E-06, E-07, E-09 |
| 6.8 | S05 | A-02, B-02 |
| 6.9 | S11, S16 | C-08, C-16 |

For multi-spec dispositions, `primary_spec=null`. For a single-spec
disposition it equals that spec. Every applicable spec requires its own exact
current artifact evidence and one delegated artifact-approval obligation.

### 3.5 Exact negative-control, sequence, and Phase-2 mappings

`PG-1-11` is the active Phase-1 exclusion at register line 160:

- `rule=ACTIVE_NEGATIVE_CONTROL`;
- `related_register_ids=["D-02","D-05","E-03","E-05","E-09"]`;
- `program_disposition=REQUIRED_NOW`, `primary_spec=null`, and no activation
  predicate or unrelated `C-11`;
- `PASS` requires every named capability either to remain dormant/rejected with
  current no-implementation proof, or to have its own valid activation and all
  source-required approvals. This does not activate any capability.

All sequence rows remain `PROGRAM_WIDE_ACTIVE_CONTROL`,
`related_register_ids=[]`, `primary_spec=null`, and `REQUIRED_NOW`:

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

Applicability alone never creates delegated approval; an exact eligible spec,
roadmap, or JIT-plan artifact and current evidence are required.

Phase-2 predicates use `MTR-{component}-{FIELD-IN-UPPER-KEBAB}` and exact
`/phase_gates/pg_2_XX/<field>` JSON pointers:

| Gate | Exact observable conjunction |
|---|---|
| PG-2-01 | `benchmark_result_id != ""`; `primary_metric_definition_id != ""`; `precommitted_minimum_improvement > 0`; `observed_primary_improvement >= precommitted_minimum_improvement` |
| PG-2-02 | `test_result_id != ""`; `stale_fixture_count > 0`; `stale_surfaced_count == stale_fixture_count`; `contradiction_fixture_count > 0`; `contradiction_surfaced_count == contradiction_fixture_count` |
| PG-2-03 | `test_result_id != ""`; `promotion_cases_executed > 0`; `sql_metadata_divergence_count == 0`; `partial_write_escape_count == 0` |
| PG-2-04 | For each `correction`, `deletion`, `backup`, and `export`: `{op}_test_result_id != ""`; `{op}_cases_executed > 0`; `{op}_failure_count == 0` |
| PG-2-05 | `burden_measurement_id != ""`; each observed `operator_minutes_per_month`, `incidents_per_100_runs`, and `p95_recovery_minutes` is `<=` its independent `precommitted_max_*` metric |
| PG-2-06 | `trigger_policy_id != ""`; `current_engine_decision_id == trigger_policy_engine_decision_id`; `corpus_size_threshold > 0`; `cross_company_graph_query_threshold > 0`; `0 < retrieval_miss_rate_threshold <= 1` |

Missing evidence or thresholds yields `UNKNOWN`. Copied verdict fields such as
`*_ready`, `*_improved`, or `*_acceptable` are invalid.

### 3.6 Proof-inventory corrections retained from r2

Retain the r2 non-delegated approvals exactly: registers A-07 budget; B-14
analyst; C-14 data rights; C-16 analyst; E-01 budget/capacity/named owner; E-02
capacity; E-03 budget plus a distinct retention product decision; E-04 data
rights/budget/named owner; E-05 budget; and separate D-05
`ACTIVATE_DEFERRED` and `ADOPT_MEMORY_APPROACH` scopes. Retain phase-gate
approvals PG-05-01 analyst, PG-05-02 analyst, PG-05-05 domain, PG-1-06 analyst,
PG-1-09 capacity, and PG-2-05 product owner; and disposition approvals G-1,
M-1, and M-5 analyst. The six gates use ordinary component `REVIEW` evidence,
not invented delegated artifact approval.

The exact command-proof component set is:

- `REG-A-10`, `REG-B-01`, `REG-B-11`, `REG-B-14`, `REG-C-08`,
  `REG-C-15`, `REG-C-16`, `REG-C-17`, `REG-E-01`, `REG-E-10`;
- `PG-05-08`, `PG-1-04`, `PG-1-05`, `PG-1-06`, `PG-2-03`, `PG-2-04`;
- `DISP-G-1`, `DISP-M-4`, `DISP-M-5`, `DISP-M-6`, `DISP-M-7`,
  `DISP-M-9`, `DISP-6-6`, `DISP-6-9`, and `SEQ-09`.

`DEF-01..13` use current negative no-implementation proof. All eight scale
triggers use proof that the operating reevaluation control is recorded and
enforced without requiring its condition to occur. `DEF-12.primary_spec=null`.
`SCALE-WORKFLOW-01..04.disposition_refs=["M-5"]`; the four SQLite triggers
retain `R-5`. `PG-2-04.related_register_ids=["D-01","D-03"]`. Derived
`gate_refs` are recomputed from the exact gate map.

## 4. Exact HR-0004 resolution-bound scope

The r2 authority-reconciliation set of 110 IDs is correct for semantic/schema
repair, but it is not the full atomic transaction target. Fresh enumeration
finds 106 stale `FILE_BYTES` references, including 34 register rows outside
that 110-ID set. The active structural validator checks every declared
evidence object against current bytes, so a candidate cannot pass without
repairing those 34 rows too. This is source-grounded correction of r2's
migration scope, not a change to its 213/169/44 inventory or semantic
crosswalks.

HR-0004's `scope` therefore has sorted unique `component_ids` equal to the
following full set; `register_ids`, `spec_ids`, `bead_ids`, and
`blocked_component_ids` are all empty. The entry may not use an anchor ID or a
projection shortcut:

```text
ALIAS-001, ALIAS-011, ALIAS-012, ALIAS-013, ALIAS-014, ALIAS-015,
ALIAS-023, ALIAS-041, ALIAS-043, ALIAS-044,
AUTH-REG-002, AUTH-REG-003,
DEF-01..DEF-13,
DISP-G-1..DISP-G-5, DISP-M-1..DISP-M-9, DISP-T-1..DISP-T-4,
DISP-R-1..DISP-R-5, DISP-6-1..DISP-6-9,
PG-05-01, PG-05-02, PG-05-05, PG-05-08,
PG-1-04, PG-1-05, PG-1-06, PG-1-09, PG-1-11,
PG-2-01..PG-2-06,
REG-A-07, REG-A-10,
REG-B-01, REG-B-11, REG-B-14,
REG-C-08, REG-C-11, REG-C-14, REG-C-15, REG-C-16, REG-C-17,
REG-D-01, REG-D-05,
REG-E-01, REG-E-02, REG-E-03, REG-E-04, REG-E-05, REG-E-10,
SCALE-SQLITE-01..SCALE-SQLITE-04,
SCALE-WORKFLOW-01..SCALE-WORKFLOW-04,
SEQ-01..SEQ-11

plus these 34 evidence-maintenance targets outside the semantic set:

REG-A-01, REG-A-02, REG-A-03, REG-A-04, REG-A-05, REG-A-06,
REG-A-08, REG-A-09, REG-A-11,
REG-B-02, REG-B-03, REG-B-04, REG-B-05, REG-B-07, REG-B-08,
REG-B-09, REG-B-10, REG-B-13,
REG-C-01, REG-C-02, REG-C-03, REG-C-05, REG-C-06, REG-C-07,
REG-C-10, REG-C-12, REG-C-13, REG-C-18,
REG-D-02, REG-D-04,
REG-E-06, REG-E-07, REG-E-08, REG-E-09
```

After range expansion and union this is exactly 144 IDs: 141 exist in the
immutable pre-state and three are new. Its canonical-JSON sorted-array digest
is `bf6fee00d0f4510316b42b50ec13f74148df9ed44e472f2ad8be114ee3add894`.
The entry's nonempty `scope_text` states that it is the exact 144-ID
goal/schema/validator, evidence-maintenance, and append-only
ledger-reconciliation scope, with no blueprint-authority-byte or
register-Status change, no Deferred activation, no delivery advance,
preservation of all 454 histories as exact prefixes, and preservation of
HR-0001..3.

Post-transaction validation is deliberately two-pass:

1. Parse all 213 candidate ledger rows and establish the canonical ID set,
   including the three new IDs.
2. Parse HR-0004 and require its `component_ids` to equal the validator-owned
   144-ID manifest exactly. Normalize the scope against that post-state, then
   require `HR-0004` in all 132 existing canonical rows in scope and both new
   canonical rows. `ALIAS-*` rows remain outside component-local
   HR reverse-linking because aliases require `human_review_id=null`; their
   authority is still covered by HR-0004's structured scope and their own
   resolution-bound reconciliation histories. No non-target row may gain
   HR-0004.

For the 23 target rows already linked to HR-0001, HR-0002, or HR-0003, the
post-state is the sorted two-ID array containing the prior ID and `HR-0004`.
All other target canonical rows use `HR-0004`. Existing HR entry objects,
scope, evidence, state, and resolution arrays remain byte-for-byte equivalent
as JSON values. HR-0001..3 stay `OPEN_BLOCKING` and unresolved.

## 5. Pre-approval package

### 5.1 Package assembled without canonical mutation

After a clean independent review, the orchestrator assembles this read-only
package in conversation:

1. the repo-relative path of this r3 file and its freshly computed full
   SHA-256, inserted externally as `<R3_SHA256>`;
2. the five immutable pre-state hashes in §2 and the reviewed authority hashes;
3. the independent review artifact path, SHA-256, reviewer/session identity,
   `gpt-5.6-sol`, `xhigh`, UTC timestamp, and exact `CLEAN` verdict;
4. the exact 144-ID scope, count, and canonical-JSON digest
   `bf6fee00d0f4510316b42b50ec13f74148df9ed44e472f2ad8be114ee3add894`;
   and
5. the following exact user-facing question with only `<R3_SHA256>` and the
   independently reviewed review-evidence fields filled. There is no digest in
   this file that attempts to hash itself.

The user must answer affirmatively in the current conversation after seeing
that completed package. Silence, earlier approval, the rejected r2 recording,
an agent recommendation, or a paraphrase that omits a bound hash is not
approval.

### 5.2 Exact decision question

> Do you approve one `RECONCILE_AUTHORITY` transaction bound to independently reviewed `docs/goals/reviews/ledger/equity-os-blueprint-ledger-remediation-design-r3.md` SHA-256 `<R3_SHA256>`, active-goal pre-state SHA-256 `dabad7bfe3d2765a5ac9687376029d8587b4b2ac95bc03494155a974e5ddc67f`, ledger pre-state SHA-256 `51091042dae87d2f41fbbf02d77ab1619c6a1008a022baec4233c44a0e295e13`, human-review pre-state SHA-256 `54c1e183def8e0b1b91504effbf20c233b3d1352fd65d4910e89c2b913ee5702`, v2-register SHA-256 `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, disposition-report SHA-256 `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`, and exact 144-ID scope digest `bf6fee00d0f4510316b42b50ec13f74148df9ed44e472f2ad8be114ee3add894`, authorizing only one atomic change to the goal, its three validator surfaces plus extractor interface, the canonical ledger, and canonical human-review artifact that records and resolves HR-0004 over that exact full structured scope, including current-digest repair for every freshly enumerated stale declared evidence object without treating that maintenance as satisfied proof; produces exactly 213 ledger rows = 169 canonical + 44 aliases; preserves all 454 existing transition objects as exact prefixes and preserves HR-0001..3 open and unresolved; changes no pinned blueprint bytes or register Status cells; activates no Deferred component; advances no delivery or gate state; and aborts without canonical change on any hash, review, scope, validation, or replacement failure?

Recommendation: approve only that exact package. Safe default: do not create
HR-0004 and leave every canonical byte unchanged; product implementation stays
blocked.

### 5.3 Approval evidence without invented citation

The transaction records the actual user message, not a reconstructed quote or
fabricated URI. The candidate goal adds one authority-reconciliation record
containing the exact completed §5.2 question bytes as presented to the user,
the exact user response bytes, actual runtime-supplied UTC timestamp and
conversation/goal-tool identifier, the r3/review/scope digests, and all five
pre-state hashes. The HR-0004 entry and resolution use a
`UTF8_LINE_SPAN` evidence object that points to that exact post-transaction goal
span and hashes it under the existing evidence rules. This creates no digest
cycle: the goal span contains no HR entry, resolution, or ledger digest.

The evidence scope says only what is mechanically true. It does not invent a
legal name, URL, message ID, transcript, or citation. Conversation memory or
an agent-authored paraphrase is inadmissible. If the runtime cannot supply the
exact response bytes, authenticated-current-user designation, timestamp, and a
stable conversation/goal-tool identifier, the transaction must not start.
The HR-0004 resolution actor is `actor_type=HUMAN`, role `CURRENT_USER`, with
the stable identity/display values actually supplied by the runtime; the
existing goal's truthful `Current authenticated chat user` designation may be
used as the display value but never as a legal name. `authority_basis` exactly
matches the entry's `GOAL_OR_PROCESS_AUTHORIZATION` and cites the real goal-span
approval evidence.

## 6. Atomic authority transaction

### 6.1 Allowed and forbidden canonical paths

The only canonical paths allowed to change are:

1. `docs/goals/equity-os-blueprint-completion.md`;
2. `scripts/equity_os_blueprint/validate_ledger_structural.py`;
3. `scripts/equity_os_blueprint/validate_ledger_preimplementation.py`;
4. `scripts/equity_os_blueprint/extract_goal_validators.py`;
5. `docs/goals/equity-os-blueprint-component-ledger.jsonl`; and
6. `docs/goals/equity-os-blueprint-human-review-needed.md`.

The third embedded terminal validator changes only inside the goal; there is
no checked-in terminal-validator script today. Approval evidence is recorded
in the amended goal as §5.3 specifies, so no seventh canonical evidence file
is created. The one-shot migrator executes from a private temporary directory
after approval and is removed after the evidence bundle is complete; it never
becomes a repository mutation.

Forbidden changes include both pinned blueprint authorities, all specs and
review artifacts including this r3 file and its independent review, every
other goal/review/workstream file, the bootstrap generator, Beads/Dolt state,
`.beads/issues.jsonl`, Git index, Git history, commits, pushes, product code,
and every unrelated dirty path. No register Status cell may change.

### 6.2 Transaction boundary and rollback

The transaction is a manifest-controlled compare-and-swap over exactly the six
canonical paths:

1. Acquire an exclusive repository-local transaction lock. Reject a symlinked
   target, duplicate target, non-regular pre-state target, or filesystem that
   cannot support same-directory atomic replacement for every target.
2. Read and retain every preimage byte string in memory and in a private
   same-filesystem staging directory. Verify the five immutable hashes, the
   full r3 digest, clean-review digest/verdict, exact user-message bytes, exact
   144-ID manifest/digest, authority hashes, expected Git-index bytes, and the
   allowed-path dirty-tree baseline. Any mismatch exits before writing.
3. Build every candidate byte string in memory. Write candidates with exclusive
   creation to same-directory temporary files, `fsync` each file, validate only
   the temporary candidates, and `fsync` their directories. Temporary names are
   never canonical and are deleted on precommit failure.
4. Write and `fsync` a transaction journal containing transaction ID,
   pre/post hashes, exact target order, temp paths, backup/preimage paths,
   approval and review digests, 144-ID scope digest, validator results, and
   state `PREPARED`.
5. Replace targets in deterministic order: goal, structural validator,
   preimplementation validator, extractor, ledger, and human review. Before
   each replacement compare the live target to its recorded
   prehash. Use same-directory atomic rename. After each rename, update and
   `fsync` the journal.
6. Rerun canonical-path validation and compare every canonical posthash to the
   prepared candidate hash. Only then mark and `fsync` `COMMITTED`, `fsync`
   directories, release the lock, and retain the evidence bundle.

Filesystem rename is atomic per path, not across paths. Therefore the journal
and rollback protocol are part of the transaction boundary. On any failure
after the first replacement, restore every replaced path from its exact
preimage in reverse order using same-directory atomic rename, `fsync` restored
files/directories, verify all original hashes, mark `ROLLED_BACK`, and exit
nonzero. If automatic rollback cannot prove every prehash, keep the lock,
write `RECOVERY_REQUIRED`, stop all goal mutations, and report the exact
path/hash mismatch; never continue from a mixed authority state. A startup
recovery check must resolve any nonterminal journal before another mutation.

No staging, commit, push, or Beads operation is inside or implied by this
transaction.

## 7. Deterministic migration algorithm

1. **Recheck authority.** Verify every §2 prehash, r3/review/approval package,
   exact allowed path set, unchanged Git index, and unchanged unrelated dirty
   baseline under the exclusive lock.
2. **Amend the contract in memory.** Apply only §§3–6 and §8 to the active goal;
   update its three embedded validators together. Extract the first two into
   candidate scripts and require byte identity with the candidates.
3. **Build the HR candidate.** Preserve HR-0001..3 as exact JSON values. Add one
   HR-0004 entry with the exact 144-ID scope and evidence described above, plus
   exactly one sequence-next `RECONCILE_AUTHORITY` decision bound to the
   immutable entry authority projection. Do not reuse the rejected r2 HR-0004
   draft or its partial scope.
4. **Migrate schema and semantics.** Apply the exact aliases, crosswalks,
   negative control, sequences, predicates, proof inventories, gate refs,
   `DEF-12`, and scale-trigger corrections in §3. Existing components may
   change only the fields named in §7.2. Add the three new components with
   current source proof.
5. **Repair stale artifact evidence.** Recompute the stale set from the
   pre-state. For each stale `FILE_BYTES` object, preserve the old evidence
   object's full canonical JSON in the transaction evidence bundle and append
   a manifest entry binding old ref/digest to current path/digest. Then update
   that declared evidence object's `content_sha256` and `captured_at` to the
   actual current bytes; the active structural validator checks every declared
   object, so retaining a stale object inside `evidence_refs` and merely adding
   a replacement would still fail. Append an `AUTHORITY_RECONCILIATION`
   transition for any controlled projection affected by the evidence-driven
   remediation, reset covered complete reviews/proof if any are stale, and do
   not mark any unresolved evidence, approval, verification, delivery, or gate
   obligation satisfied. The 106 known refs are a preflight expectation, not a
   hard-coded authority: execution must record and use the freshly derived set.
6. **Append histories.** Never edit, reorder, delete, or insert within any of
   the 454 existing transition arrays. For each changed existing row, append
   one transition per changed controlled field in a validator-owned fixed field
   order. Use truthful current UTC times, unique IDs, the previous terminal
   hash, current evidence, and the HR-0004 decision ID/digest for every
   authority reconciliation. New IDs begin with the authorized sequence-zero
   reconciliation defined in §3.2.
7. **Validate candidates.** Run §8 against only the candidate paths. On any
   failure, delete temporary candidates, preserve canonical bytes, and exit
   nonzero. There is no partial acceptance or automatic scope widening.
8. **Commit or roll back the file transaction.** Execute §6.2. Revalidate the
   canonical paths after replacement. A failed post-replacement check invokes
   rollback; a successful check produces the evidence bundle and stops. It
   does not resume product implementation or perform Git/Beads operations.

### 7.1 Exact HR linking rule

The expanded 144-ID HR scope contains ten aliases: nine repaired aliases plus
new `ALIAS-044`. Aliases keep `human_review_id=null` under the alias schema.
Every scoped canonical row carries HR-0004. Exactly 23 of those canonical rows
also retain an earlier HR ID:

- HR-0001: `DISP-6-2`, `DISP-G-1`, `DISP-G-5`, `DISP-R-4`, `REG-A-04`,
  `REG-A-10`, `SEQ-04`, `SEQ-05`, `SEQ-07`;
- HR-0002: `DISP-R-2`, `REG-A-06`, `REG-B-09`, `REG-C-02`, `REG-C-14`;
  and
- HR-0003: `DEF-13`, `DISP-R-5`, `DISP-T-3`, `REG-B-03`, `REG-C-11`,
  `SCALE-SQLITE-01..04`.

The validator rejects any loss of those prior links and rejects HR-0004 on any
canonical component outside its exact scope.

### 7.2 Exact mutable ledger fields

For the 107 existing semantic targets, the allowed semantic fields are limited to
`canonical_component_id`, `primary_spec`, `scope_derivation`,
`activation_predicate`, `disposition_refs`, derived `gate_refs`,
`required_approvals`, `required_evidence`, `evidence_refs`,
`human_review_id`, and the safe `DEF-12` delivery reset. Affected stale review
objects may move only from `COMPLETE` to their exact `PENDING` form; affected
verification results/`verified_at` may only be cleared. Append-only transition
objects and `transition_history_sha256` necessarily change.

For the other 34 existing targets, only stale `evidence_refs`, derived stale
review/proof resets, `human_review_id`, appended transition objects, and
`transition_history_sha256` may change. No semantic source, scope, ownership,
predicate, proof-obligation, delivery, gate, work, finding, blocker, approval,
or security field may change on those rows.

Source coordinates/text, authority rank, register ID/title/acceptance/phase/
priority/dependencies, `activation_source_status`, `source_status`, register
`primary_spec`, Bead/work/roadmap/plan/implementation references, activation or
rejection records, open findings, blocked scope, security links, approval
records, satisfied approval state, and unrelated proof remain unchanged. No
row may move forward in delivery; `DEF-12` may only reset from `SPEC_DRAFT` to
`INVENTORIED`. No gate result changes.

## 8. Mechanical validator and evidence contract

### 8.1 Required validator interfaces

- Structural: `--repo-root`, plus paired `--ledger-path` and
  `--human-review-path`; neither path means canonical defaults and supplying
  only one fails. `--reconciliation-check` is transaction-only and requires
  paired `--reconciliation-baseline-ledger-path` and
  `--reconciliation-baseline-human-review-path`; supplying either baseline
  outside that mode, or only one, fails. Both baseline inputs must match the
  §2 hashes; reconciliation mode uses them for exact field, history-prefix,
  prior-HR, state, and no-advance comparison. Ordinary future validation does
  not depend on retained preimage files: the validator permanently owns the
  baseline per-row transition-prefix-length manifest and its canonical-JSON
  digest `d4ce9646438d388bf26c8faa82d689209296726af2c29d1e56942218c613d9b1`,
  and checks the resulting prefix projection against that digest.
- Preimplementation: `--repo-root`, optional `--ledger-path`, and
  `--report-blockers`. The reporting flag performs the same digest checks on
  every `COMPLETE` review, emits exact `PENDING`/stale review IDs as JSON, and
  exits 2 when the gate is not ready; it never converts or waives a review.
- Terminal: the same paired candidate paths as structural plus
  `--report-blockers`. The ordinary path remains SUCCESS-only. Reporting mode
  derives current active/dormant/rejected state and emits unmet SUCCESS
  conditions as JSON with exit 2; it never grants a terminal state.
- Extractor: optional `--goal-path`, `--structural-output`,
  `--preimplementation-output`, and `--terminal-output`. Default `--check`
  retains byte-exact checking of the two checked-in scripts; explicit outputs
  allow all three programs from a candidate goal to be compared and syntax
  checked without a canonical write.
- Alternate artifact arguments may be absolute. Every path stored inside the
  ledger remains repo-relative and resolves under `--repo-root`. Evidence may
  target neither selected ledger nor selected human-review artifact.

Structural validation independently owns exact occurrence manifests for every
phase gate, deferral, scale trigger, disposition, authority, sequence,
document-strategy clause, and alias; exact target/crosswalk/gate/sequence maps;
exact schema keys; the 213/169/44 inventory; the exact 144-ID HR-0004 scope;
multi-HR reverse links; eligible delegated-approval evidence; new-history form;
and the 454-history prefix invariant. It never imports generator constants.

### 8.2 Candidate commands

Use actual temporary paths in these commands:

```bash
python3 <candidate-extractor> --goal-path <candidate-goal> \
  --structural-output <candidate-structural> \
  --preimplementation-output <candidate-preimplementation> \
  --terminal-output <candidate-terminal> --check
python3 <candidate-structural> --repo-root . \
  --ledger-path <candidate-ledger> --human-review-path <candidate-human-review> \
  --reconciliation-check \
  --reconciliation-baseline-ledger-path \
  docs/goals/equity-os-blueprint-component-ledger.jsonl \
  --reconciliation-baseline-human-review-path \
  docs/goals/equity-os-blueprint-human-review-needed.md
python3 <candidate-preimplementation> --repo-root . \
  --ledger-path <candidate-ledger> --report-blockers
python3 <candidate-terminal> --repo-root . \
  --ledger-path <candidate-ledger> --human-review-path <candidate-human-review> \
  --report-blockers
```

The structural command must exit 0. The preimplementation and terminal
reporting commands must each exit 2 with their explicit not-ready JSON; exit 0
would falsely claim readiness/SUCCESS and any other exit is an implementation
failure. Current baseline reviews are `PENDING`, delivery is incomplete, and
HR-0001..3 remain open, so this transaction is not allowed to make either gate
pass. Product work resumes only after later fresh inventory reviews make the
ordinary structural-plus-preimplementation sequence exit 0.

After canonical replacement run:

```bash
python3 scripts/equity_os_blueprint/extract_goal_validators.py --check
python3 scripts/equity_os_blueprint/validate_ledger_structural.py \
  --reconciliation-check \
  --reconciliation-baseline-ledger-path <protected-preimage-ledger> \
  --reconciliation-baseline-human-review-path <protected-preimage-human-review>
python3 scripts/equity_os_blueprint/validate_ledger_preimplementation.py \
  --report-blockers
git diff --check -- docs/goals/equity-os-blueprint-completion.md \
  scripts/equity_os_blueprint/validate_ledger_structural.py \
  scripts/equity_os_blueprint/validate_ledger_preimplementation.py \
  scripts/equity_os_blueprint/extract_goal_validators.py \
  docs/goals/equity-os-blueprint-component-ledger.jsonl \
  docs/goals/equity-os-blueprint-human-review-needed.md
git status --short --branch
```

The post-replacement transaction also invokes the extracted terminal program
with `--report-blockers` and the canonical pair. It requires the same exit-2
not-ready result seen on the candidate.

### 8.3 Mandatory postconditions

Every postcondition is evaluated against the resulting bytes, never by asking
mutable files to retain pre-state hashes:

- canonical posthashes equal the prepared candidate hashes and differ from a
  prehash only for allowed paths; both pinned blueprint hashes remain exact;
- 213 unique rows = 169 canonical + 44 aliases, with exact kind counts
  `60/35/13/8/32/4/11/6/44` and all source occurrences/crosswalks exact;
- every one of the 454 pre-state transition objects remains byte-for-byte
  equivalent as canonical JSON at the same per-row index; every existing
  history is an exact prefix; all appended/new chains and history digests
  recompute;
- HR-0004 has exactly one active `RECONCILE_AUTHORITY` resolution, exact
  144-ID structured scope, exact approval/review/r3/prehash evidence, and valid
  entry/resolution/hash-chain digests; HR-0001..3 remain open, blocking,
  unresolved, and otherwise unchanged;
- all 23 preexisting finding-bearing and blocked rows retain their findings and
  blockers; all 23 prior HR links remain, with overlaps represented by arrays;
- register state remains exactly 45 `Open` and 15 `Deferred`; all
  `activation_record` values remain null; no `source_status` or
  `activation_source_status` changes; all originally Deferred rows remain
  `CONDITIONAL_UNACTIVATED` and no new implementation reference exists;
- no delivery state advances: every row's post-state delivery ordinal is less
  than or equal to its pre-state ordinal, with only the authorized `DEF-12`
  reset allowed; every gate remains `NOT_EVALUATED`; no new satisfied evidence,
  approval, approval record, verification result, or `verified_at` exists;
- every evidence object validates against current bytes; the evidence bundle
  contains the exact stale preimage-to-current mapping without claiming the
  refresh as delivery or approval proof; and
- the Git index bytes are unchanged; no Beads, commit, push, blueprint, spec,
  review, generator, or unrelated dirty path changed.

### 8.4 Evidence bundle

The retained bundle contains canonical JSON plus referenced raw command output:

- transaction ID, timestamps, lock identity, journal, final state, target
  manifest, pre/post hashes, candidate hashes, replacement order, rollback
  result, and unrelated-dirty/index baselines;
- r3 SHA, independent-review evidence and verdict, actual approval-message
  bytes/digest, HR entry/resolution digests, and expanded 144-ID list/digest;
- exact pre-state ledger row-ID list, all 454 transition objects and their
  manifest digest, HR-0001..3 projections, counts, statuses, findings,
  blockers, links, delivery/gate state, and pinned authority hashes;
- exact field-level ledger and human-review semantic diff; new-component
  manifests; old-history prefix comparison; HR reverse-link comparison;
- fresh stale-evidence inventory with every old/current digest and proof-reset
  disposition; and
- every candidate and canonical validator argv, exit code, stdout/stderr
  digest, extractor byte-equality result, `git diff --check`, and final
  `git status`.

The bundle is evidence, not authority. Its repository destination must be
approved before the transaction if it is to be committed later; otherwise it
remains in the transaction's protected staging/recovery area for handoff.

## 9. Generator relationship

The current generator is a safe bootstrap-only candidate generator. Its r4
review is `CLEAN` for the findings raised in the generator r3 review. It uses
one fresh per-invocation UTC timestamp for generated evidence and transitions;
the fixed authority-activation cutoff on the R-1 rejection record is not a
generated snapshot timestamp.

That bounded review verdict does not make the generator a live reconciler. Its
emitted bootstrap inventory and schema still differ from the live
reconciliation target specified by this design, so the canonical migration
must use a separate one-shot migrator. Neither generator constants nor current
or future generator output is an input to validator-owned manifests. The
generator must not touch existing or canonical activated artifacts or
reconstruct history.

Generator work remains independent from HR-0004 migration authority: it is
neither a prerequisite nor an authorization for the transaction. Only the
fresh, hash-bound user approval in §5 can authorize creation and resolution of
HR-0004 and execution of the bounded migration.

## 10. Executor handoff

1. Commission one clean, independent, exact-byte Sol xhigh review of this r3
   file; any finding stops the lane and requires a new reviewed revision.
2. After `CLEAN`, compute the r3/review/scope digests and ask the exact §5.2
   question. Preserve all canonical pre-state bytes while waiting.
3. After a fresh affirmative user answer, capture real approval evidence and
   implement one one-shot migrator plus the contract/validator candidates.
4. Run the complete temporary-artifact proof, then the journaled compare-and-
   swap transaction; stop after the evidence bundle and hand off for separate
   review. Do not stage, commit, push, modify Beads, or resume product work.

**Hard prohibition:** no migration, HR-0004 entry or resolution, canonical
goal/validator/ledger/human-review mutation, or approval record may be
created before both a clean independent review of the exact r3 SHA and a fresh
current-user approval explicitly bound to the completed §5 package. A failed
precondition, changed r3 byte, non-clean review, incomplete answer, missing
exact-message evidence, validator failure, or rollback uncertainty ends the
attempt fail-closed with canonical pre-state restored.
