# Ledger authority and remediation design r5

Next action: obtain one clean independent exact-byte **Reviewer** review of this
file at the predetermined path
`docs/goals/reviews/ledger/equity-os-blueprint-ledger-remediation-design-r5-review-r0.md`.
The review must declare role `REVIEWER`, its actual invoked model and effort,
the role-binding capture defined in §3.8, verdict `CLEAN`, and a reviewed-input
SHA-256 equal to this file's freshly computed SHA-256. If and only if all
bindings validate, the orchestrator may ask the exact decision question in
[§5.2](#52-exact-decision-question). No canonical mutation, HR-0004 entry,
resolution, migration code, Beads change, staging, commit, or push is
authorized before the current user answers that completed question
affirmatively.

**The prior approval is void.** The user approval recorded in
`scratchpad/hr0004/approval-evidence.md` is bound to r4 SHA-256
`c1ab125880ec1895a344b57f7aaef8d372836fa0ded9c900a1aae9284b295e00` and to the
r4 review. r5 changes the ledger content, the validator contract, and the goal
amendment set that approval covered. That approval is therefore void for every
purpose, must not be reused, quoted as current authority, or embedded in any
candidate goal record, and `scratchpad/hr0004/approval-evidence.md` becomes
historical context only. A fresh §5.2 answer bound to r5 is required.

## 1. Status, defects corrected, and authority boundary

This document starts from the exact r4 design whose SHA-256 is
`c1ab125880ec1895a344b57f7aaef8d372836fa0ded9c900a1aae9284b295e00` and
supersedes its operational design. It preserves every mechanically verified r4
non-finding and corrects exactly the defects in the independent candidate
review at `scratchpad/hr0004/review/review-r0.md`
(`Verdict: BLOCKED — 1 Critical, 7 Important`), plus the two user-instructed
terminology requirements. It does not approve any earlier revision, amend the
active goal, or authorize a migration.

1. **Approval binds the exact independent review.** The literal question binds
   this r5 path and SHA-256, the predetermined review path and SHA-256, the
   review's `CLEAN` verdict, its reviewed-input SHA equal to the r5 SHA, and the
   reviewer **role** binding of §3.8 together with the actual model and effort
   the review records. The completed question and response bytes are recorded
   after approval, and structural reconciliation verifies every bound review
   field against the immutable review artifact before any write.
2. **Stale rejection evidence is not current proof.** `DISP-R-1` retains its
   accounted rejection authority and historical rejection-record references,
   but its no-implementation requirement resets to exact `UNRESOLVED`. Current
   proof exists only after satisfied requirement coverage and a fresh
   content-bound clean `REVIEWER`-role evidence review over the current bytes.
3. **One required repository-root contract.** Candidate and post-replacement
   structural, preimplementation, and terminal invocations all pass the required
   `--repo-root .`; the post-replacement terminal invocation is explicit.
4. **The canonical structural invariant is not relaxed for convenience.** r5
   resolves the r4 §3.5/§3.6 `PG-2-04` contradiction without weakening the rule
   that a non-conditional component carrying an activation predicate must be
   `REJECTED_ACCOUNTED`. That rule survives r5 unchanged in meaning
   (§3.5, §3.9).

The protections carried forward into r5 remain binding: the canonical goal,
ledger, and human-review artifact stay byte-identical through independent
review and the user's decision; HR-0004 is created and resolved only inside the
later transaction; and its exact structured scope remains 144 IDs, comprising
141 affected existing IDs plus the three new IDs (freshly recomputed in §4). No
later scope expansion is permitted.

Current-user approval is necessary but not sufficient. It authorizes one
bounded transaction only after a clean independent review; the migrator must
still satisfy every precondition and every temporary-artifact validator. A
reviewer, orchestrator, implementer, migrator, or validator cannot substitute
for the user's authority.

### 1.1 Disposition of every candidate-review finding and deviation

Every finding in `scratchpad/hr0004/review/review-r0.md` and every deviation in
`scratchpad/hr0004/staging/run-report.md` §7 is disposed of here. "Contract" means
r5 states the requirement and the migrator must satisfy it; "design" means r5
changes what the migrator must build.

| ID | Disposition | r5 location |
|---|---|---|
| C-1 | **Design change.** `PG-2-04` keeps its grounded `["D-01","D-03"]` source semantics, derives `REQUIRED_NOW`, and carries `activation_predicate=null`. Neither validator relaxation in the reviewed candidate is authorized. One narrow transition-legality addition is authorized. | §3.5, §3.9, §7.2 |
| I-1 | **Design change.** The goal-prose amendment list is extended to every closed-schema change, and an extractor-owned marker check makes prose/validator drift fail loudly. | §7.3, §8.1 |
| I-2 | **Design change.** Closed `approval_type -> required_authority` vocabulary table; every new obligation reuses or extends it explicitly. | §3.7 |
| I-3 | **Contract.** Canonical file mode preserved on replace and on rollback; mode recorded in the preimage and proven in the rollback result. | §6.2, §8.3 |
| I-4 | **Contract.** Every temporary candidate is deleted on any non-`COMMITTED` exit. | §6.2 |
| I-5 | **Contract.** Interrupt-safe rollback: `BaseException`-level guard or signal handlers routing into the same rollback path. | §6.2 |
| I-6 | **Contract.** Dirty-baseline and Git-index equality are enforced before writing and re-derived and compared after replacement. | §6.2, §8.3 |
| I-7 | **Contract.** The evidence bundle must contain the complete §8.4 content, enumerated exactly. | §8.4 |
| M-1 | **Contract.** Overlay is torn down after validation; the literal-root invocation must fail closed with exit 2, not a traceback. | §6.3, §8.1 |
| M-2 | **Design closure.** `controlled_state.scope_definition` stays the exact three-key projection permanently; the kind-specific keys are digest-bound through the review projections, which r5 makes a required validator rule. | §3.2, §3.10 |
| M-3 | Accepted as-is: the blocker reason list is a required-subset, not a fixed length. | §8.1 |
| M-4 | Accepted as-is: either transition type is allowed for HR-link growth, with the resolution binding required whenever `AUTHORITY_RECONCILIATION` is used. | §3.2 |
| M-5 | Accepted as-is: `gate_refs` compared as a set with uniqueness. | §3.6 |
| M-6 | **Design change.** Fresh §5.2 question, byte-verbatim rendering rule, prior approval declared void. | Header, §5.1, §5.2 |
| M-7 | **Contract.** Runtime metadata is parsed from the approval-evidence capture, never hard-coded. | §5.3, §6.1 |
| M-8 | **Contract.** The atomic-replacement probe runs inside the transaction's private staging directory and renames over a second probe. | §6.2 |
| M-9 | **Contract.** The startup recovery check runs in both `--prepare` and `--execute`; `RECOVERY_REQUIRED` is signalled by the journal, and the design no longer claims an inter-process lock survives exit. | §6.2 |
| M-10 | **Contract.** External-tool availability is a precondition checked before replacement, not a rollback trigger. | §6.2 |
| M-11 | Accepted as-is: the bootstrap generator stays out of scope. | §9 |
| M-12 | **Design change.** Role terminology reconciliation. | §3.8, §7.3 |
| D-1 | Closed deliberately by M-2's disposition. | §3.10 |
| D-2 | Conforms; retained. | §3.2 |
| D-3 | Superseded by the C-1 resolution. | §3.5 |
| D-4 | Conforms; retained. | §3.6 |
| D-5 | Conforms; retained. | §8.1 |
| D-6 | Conforms with the added teardown and fail-closed requirements. | §6.3 |
| D-7 | Closed by the §3.7 vocabulary table and the §3.7 obligation-ID rules. | §3.7 |
| D-8 | Closed by the §7.3 amendment list. | §7.3 |
| D-9 | Rollback remains unexercised; §6.2 adds the required rehearsal before `--execute`. | §6.2 |
| D-10 | Conforms; retained. | §9 |

## 2. Verified immutable pre-transaction baseline

These hashes are the transaction preconditions, not hashes the resulting files
must retain. Every value below was freshly recomputed while authoring r5 and
equals the r4 §2 value; the goal, ledger, and human-review artifacts are
therefore still byte-identical to the r4 baseline and no baseline moved:

| Input | Required SHA-256 |
|---|---|
| Active goal | `dabad7bfe3d2765a5ac9687376029d8587b4b2ac95bc03494155a974e5ddc67f` |
| Canonical component ledger | `51091042dae87d2f41fbbf02d77ab1619c6a1008a022baec4233c44a0e295e13` |
| Canonical human review | `54c1e183def8e0b1b91504effbf20c233b3d1352fd65d4910e89c2b913ee5702` |
| v2 register authority | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| Disposition-report authority | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |

The three validator/extractor scripts are allowed transaction targets and are
not pinned preconditions in the question, but their pre-state bytes are
preimage inputs and were freshly recomputed as
`f880f507d82ac20145ac73d422a01bae38abf88a23e1ed0f240c62ebdd9554e9`
(structural), `ed73ffe1bd0388ed55e6d2d368058599aaa5b346f6c583fb76086a636cd5b39c`
(preimplementation), and
`7d9e130c94bcdbc3f272c883fd9f52b4bcae27e5934d9731c62b2d715ac8934d`
(extractor). §6.2 requires them to be recaptured and compared under the lock.

The canonical ledger pre-state is exactly, all values freshly recomputed:

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
  human-review payload has no resolutions;
- every content-bound inventory review is `PENDING`: 107 `semantic_review`
  objects and 167 `evidence_inventory_review` objects, with none `COMPLETE`;
  every one of the 210 `verification_command` policies is `UNRESOLVED`, so no
  `NOT_APPLICABLE` verification review exists; and
- 192 `FILE_BYTES` evidence objects, of which 106 are stale. The 106 stale
  objects sit on 106 distinct rows and point to 21 spec files whose current
  bytes are newer than the recorded r0 bytes. They are a known
  structural-validation blocker, not permission to invent approval or delivery
  evidence.

The ledger and human-review hashes above equal their `HEAD` bytes. Any dirty
path outside this transaction belongs to another owner and must remain
untouched; at r5 authoring time the only dirty paths are `CONTEXT.md` and
`.beads/issues.jsonl`, neither of which is a transaction target.

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

The goal and all three embedded validators must adopt these closed changes.
Bullets 1–8 are carried from r4 unchanged in substance; bullets 9–13 are new in
r5.

1. `canonical_component_id` is exactly one of: `null` for a canonical row; a
   canonical component-ID string for a simple alias; or a sorted unique array
   of at least two direct canonical component IDs for a compound alias. Every
   target must exist in the same post-state, must not be an alias, and must not
   be the source alias.
2. `human_review_id` is exactly one of: `null`; one `HR-####` string; or a sorted
   unique array of at least two IDs. All validators normalize it to a set before
   forward and reverse-link checks. Transition replay permits only append-only
   link growth: `null -> string`, `null -> sorted array`, or an existing string
   or array -> a sorted array whose exact prefix-normalized set is the old set
   plus new IDs. Removing or replacing a prior HR ID fails. A link-growth
   transition may be `REFERENCE_APPEND` or `AUTHORITY_RECONCILIATION`; the
   latter additionally requires an active `RECONCILE_AUTHORITY` resolution whose
   structured scope contains the row.
3. Human-review `scope.component_ids` may name canonical or alias IDs. Scope
   validation first checks direct IDs against the complete post-state ledger ID
   set. Canonical IDs participate in bidirectional component-local HR linking;
   aliases remain direct resolution-bound scope members but keep
   `human_review_id=null` under the alias schema. Register/spec/Bead projections
   still yield canonical IDs only.
4. `scope_derivation` has exact kind-specific key sets. A `disposition_item`
   adds `applicable_spec_ids`; a `sequence_clause` adds
   `source_register_ids` and `applicable_spec_ids`; every other kind rejects
   those keys. All such arrays are sorted and unique. `primary_spec`,
   applicability, and semantic register relations are independently validated.
5. `ACTIVE_NEGATIVE_CONTROL` is allowed only for `phase_gate_clause`. It
   requires nonempty exact `related_register_ids`, `authority_effect=null`,
   `derived_program_disposition=REQUIRED_NOW`, and
   `activation_predicate=null`. Its gate proof is invalidated by any related
   register state, activation, rejection, approval, or no-implementation-proof
   change.
6. `rejection_record.no_implementation_evidence_ref_ids` is an immutable
   historical record of which references supported the rejection when it was
   recorded; membership never establishes current proof by itself. Structural
   validation owns the exact current no-implementation requirement map, which is
   `DISP-R-1 -> REQ-DISP-R-1-NO-IMPLEMENTATION` for this inventory. A rejected
   component has current no-implementation proof only when every historical ref
   is covered by the union of `evidence_ref_ids` on its mapped requirements,
   every mapped requirement is currently `SATISFIED`, every referenced evidence
   object validates against current bytes, and `evidence_inventory_review` is a
   current content-bound `COMPLETE`/`CLEAN` review performed under role
   `REVIEWER` per §3.8, whose evidence refs include every historical ref and
   whose timestamp is no earlier than their current captures. Its
   reviewed-input and reviewed-inventory digests must equal the validator's
   current projections. False is a valid structural state, but it is an explicit
   preimplementation and terminal blocker. No description/scope substring or
   refreshed content digest may substitute for this closed predicate.
7. Predicate expressions add the exact leaf
   `{"op":"COMPARE_METRICS","left_metric_id":...,"comparator":...,"right_metric_id":...}`.
   Both referenced metrics must exist and share one value type. Boolean/string
   operands allow `EQ` and `NE`; numeric operands additionally allow `GT`,
   `GTE`, `LT`, and `LTE`. An unresolved operand yields `UNKNOWN` under the
   existing three-valued rules.
8. A genuinely omitted post-activation component may begin at sequence zero
   only with `transition_type=AUTHORITY_RECONCILIATION`,
   `field=CONTROLLED_STATE`, `old_value=null`, and its full controlled-state
   `new_value`, bound to the active HR-0004 `RECONCILE_AUTHORITY` resolution.
   It uses the transaction timestamp and current evidence. A synthetic or
   backdated `ACTIVATION_SNAPSHOT` is forbidden.
9. **Program-disposition transition legality (new).** The legal
   `program_disposition` transition set gains exactly one pair,
   `("CONDITIONAL_UNACTIVATED","REQUIRED_NOW")`, admissible only when all of the
   following hold: the row's `kind` is not `register_row`; the transition type is
   `AUTHORITY_RECONCILIATION` bound to an active `RECONCILE_AUTHORITY`
   resolution whose structured scope contains the row; the post-state
   `program_disposition` equals the value freshly derived from the post-state
   `scope_derivation` by the existing derivation rules; the post-state
   `activation_predicate` is `null`; and the row has no `activation_record`.
   The existing four pairs are unchanged. No other disposition pair is added.
10. **The predicate invariant is not relaxed (new, restated as a closed rule).**
    A component whose derived disposition is `REQUIRED_NOW` — including one that
    became `REQUIRED_NOW` by related-register aggregation — must have
    `activation_predicate=null`. Only components currently derived
    `CONDITIONAL_UNACTIVATED` or `CONDITIONAL_ACTIVATED`, registers captured
    `Deferred`, and `REJECTED_ACCOUNTED` components may carry a predicate. No
    component-ID allowlist, phase-gate exemption, or kind exemption to this rule
    is authorized in this or any later transaction without its own reviewed
    design and approval.
11. **Closed required-authority vocabulary (new).** Structural validation owns
    the closed `approval_type -> allowed required_authority` map in §3.7 and
    rejects any `required_approvals` entry outside it. In reconciliation mode it
    additionally requires every post-state `(approval_type, required_authority)`
    pair to be either present in the baseline ledger or listed in §3.7 as an
    r5-authorized addition.
12. **Role-bound inventory reviews (new).** The content-bound inventory-review
    schema and the `NOT_APPLICABLE` verification-review schema replace their
    pinned vendor model/effort constants with the closed role vocabulary and
    binding capture in §3.8. A `PENDING` review keeps exactly its existing key
    set; a `COMPLETE` review carries exactly that key set plus `role`,
    `role_binding_path`, and `role_binding_sha256`.
13. **Review projections must bind the whole derivation (new).**
    `reviewed_input_sha256` covers `scope_derivation` with only
    `semantic_review` removed, and the `SCOPE` inventory projection covers
    `scope_derivation` with only `semantic_review` removed. Both are exact
    whole-object projections, so every kind-specific key added by bullet 4 is
    digest-bound and any change to it invalidates a `COMPLETE` review. A
    key-subset projection is forbidden.

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

#### 3.5.1 `PG-2-04` — resolution of the r4 §3.5/§3.6 contradiction (C-1)

**The contradiction.** r4 §3.6 fixed `PG-2-04.related_register_ids=["D-01","D-03"]`
while r4 §3.5 required `PG-2-04` to carry an observable Phase-2 conjunction in
`activation_predicate`. `REG-D-01` is `Open`, so `aggregate_related` derives
`REQUIRED_NOW`, and the canonical structural validator forbids a non-conditional
component from carrying a predicate unless it is `REJECTED_ACCOUNTED`. Both r4
clauses cannot hold at once.

**Grounding in the register source.** v2 §F "Phase 2 may exit only when" bullet
four is "correction, deletion, backup, and export have been tested"; `PG-2-04`
is exactly that bullet. `D-01` ("Implement `MemoryStore` interface before
choosing engine") is the only register row whose required evidence names those
operations: "Retrieval, staged write, promotion, correction, deletion, export,
cutoff filtering, and provenance contracts are engine-neutral". Its Status is
`Open` and its Priority is `Critical` — it is not deferred capability. `D-03`
("Define canonical memory promotion transaction") is `Deferred` and governs the
promotion transaction whose partial-write failure mode the deletion/backup/export
tests must exclude; it is the pre-state related row and is retained. Dropping
`D-01` would omit a true source relation, which §3.4's rule against padding or
inferring source semantics forbids in both directions. **`D-01` stays.**

**The resolution.** Because the source makes `PG-2-04` a now-required
obligation, `PG-2-04` has no dormant capability for an activation predicate to
gate. r5 therefore adopts resolution (b), forced by the (a)-side grounding:

- `PG-2-04.related_register_ids=["D-01","D-03"]`, `rule=RELATED_REGISTER_SCOPE`,
  `authority_effect=null`, `primary_spec=null`;
- `derived_program_disposition` and `program_disposition` are `REQUIRED_NOW`,
  matching the unmodified derivation;
- `PG-2-04.activation_predicate=null`. The pre-state predicate is removed, not
  rewritten. It was a copied verdict field (`MTR-PG-2-04-READY`), which §3.5
  already declares invalid, so nothing valid is lost;
- the observable conjunction r4 §3.5 specified for `PG-2-04` becomes the exact
  scope text of its command-proof obligation
  `REQ-PG-2-04-COMMAND-PROOF` (§3.6 already places `PG-2-04` in the
  command-proof component set): for each of `correction`, `deletion`, `backup`,
  and `export`, `{op}_test_result_id != ""`, `{op}_cases_executed > 0`, and
  `{op}_failure_count == 0`. This is a now-required, currently `UNRESOLVED`
  proof obligation, not an activation gate, and it advances no gate or delivery
  state;
- `REG-D-01.gate_refs` gains `PG-2-04` by the ordinary recomputation in §3.6.
  `REG-D-01` is inside the semantic scope, so this is an allowed change.

**Why this is fail-closed.** The movement is from a conditional obligation to a
required obligation: strictly more is demanded, nothing is activated, no
`activation_record` is created, no register Status changes, and `gate_result`
stays `NOT_EVALUATED`. The canonical rule that a required component cannot carry
an activation predicate is preserved exactly (§3.2 bullet 10), so the permanent
relaxation the candidate review identified never enters the canonical validator.
The only permanent validator addition is the narrowly conditioned
`CONDITIONAL_UNACTIVATED -> REQUIRED_NOW` transition pair of §3.2 bullet 9,
which cannot be used on a register row, cannot be used without a matching fresh
derivation, cannot coexist with a predicate, and cannot accompany an activation
record.

#### 3.5.2 The other five Phase-2 gates

`PG-2-01`, `PG-2-02`, `PG-2-03`, `PG-2-05`, and `PG-2-06` keep their pre-state
`related_register_ids` (`["D-02","D-05"]`, `["D-02"]`, `["D-03"]`, `["D-05"]`,
`["D-02","D-05"]` respectively). Every one of those related rows is `Deferred`,
so each gate stays `CONDITIONAL_UNACTIVATED` and legitimately carries an
activation predicate. Their predicates use `MTR-{component}-{FIELD-IN-UPPER-KEBAB}`
metric IDs and exact `/phase_gates/pg_2_XX/<field>` JSON pointers:

| Gate | Exact observable conjunction |
|---|---|
| PG-2-01 | `benchmark_result_id != ""`; `primary_metric_definition_id != ""`; `precommitted_minimum_improvement > 0`; `observed_primary_improvement >= precommitted_minimum_improvement` |
| PG-2-02 | `test_result_id != ""`; `stale_fixture_count > 0`; `stale_surfaced_count == stale_fixture_count`; `contradiction_fixture_count > 0`; `contradiction_surfaced_count == contradiction_fixture_count` |
| PG-2-03 | `test_result_id != ""`; `promotion_cases_executed > 0`; `sql_metadata_divergence_count == 0`; `partial_write_escape_count == 0` |
| PG-2-05 | `burden_measurement_id != ""`; each observed `operator_minutes_per_month`, `incidents_per_100_runs`, and `p95_recovery_minutes` is `<=` its independent `precommitted_max_*` metric |
| PG-2-06 | `trigger_policy_id != ""`; `current_engine_decision_id == trigger_policy_engine_decision_id`; `corpus_size_threshold > 0`; `cross_company_graph_query_threshold > 0`; `0 < retrieval_miss_rate_threshold <= 1` |

Missing evidence or thresholds yields `UNKNOWN`. Copied verdict fields such as
`*_ready`, `*_improved`, or `*_acceptable` are invalid. `PG-2-04` is deliberately
absent from this table; see §3.5.1.

### 3.6 Proof-inventory corrections retained from r2

Retain the r2 non-delegated approvals exactly: registers A-07 budget; B-14
analyst; C-14 data rights; C-16 analyst; E-01 budget/capacity/named owner; E-02
capacity; E-03 budget plus a distinct retention product decision; E-04 data
rights/budget/named owner; E-05 budget; and separate D-05
`ACTIVATE_DEFERRED` and `ADOPT_MEMORY_APPROACH` scopes. Retain phase-gate
approvals PG-05-01 analyst, PG-05-02 analyst, PG-05-05 domain, PG-1-06 analyst,
PG-1-09 capacity, and PG-2-05 product owner; and disposition approvals G-1,
M-1, and M-5 analyst. The six gates use ordinary component `REVIEW` evidence,
not invented delegated artifact approval. Every one of these obligations takes
its `required_authority` from the closed §3.7 vocabulary.

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
retain `R-5`. `PG-2-04.related_register_ids=["D-01","D-03"]` under §3.5.1.
Derived `gate_refs` are recomputed from the exact gate map and compared as a
set with uniqueness, not as an ordered list, so evidence-only rows whose set is
already correct are not rewritten for ordering.

`DISP-R-1` is deliberately not counted as having current no-implementation
proof after this transaction. Its sole mapped requirement is reset to this
exact canonical JSON value; the identity, description, scope, type, and mode
are retained, while `status` and `evidence_ref_ids` take the exact unresolved
form required by the live schema:

```json
{"approval_ids":[],"description":"Current S20 draft preserves D-02 as dormant and contains no implementation claim","evidence_id":"REQ-DISP-R-1-NO-IMPLEMENTATION","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"R-1 current no-implementation proof","status":"UNRESOLVED"}
```

Its `evidence_inventory_review` remains the exact `PENDING` form. The unchanged
rejection record continues to account for the pinned rejection authority, but
its historical `no_implementation_evidence_ref_ids=["EV-DISP-R-1-SPEC-DRAFT"]`
does not satisfy the requirement. A later substantive review may establish
current proof only by changing the requirement and review through the ordinary
evidenced process; this reconciliation does not perform or imply that review.

### 3.7 Closed required-authority vocabulary

`validate_ledger_structural.py` asserts that a satisfying approval record's
`authority` equals its requirement's `required_authority` byte-for-byte.
Introducing a second string for an authority that already has one therefore
creates a permanent trap. r5 closes the vocabulary. The post-state ledger must
satisfy this exact map, which structural validation owns:

| `approval_type` | Exact allowed `required_authority` values |
|---|---|
| `ANALYST_ACCEPTANCE` | `Responsible analyst` |
| `BUDGET_APPROVAL` | `Budget owner` |
| `CAPACITY_COMMITMENT` | `Capacity owner` |
| `DATA_RIGHTS_APPROVAL` | `Data-rights authority` |
| `DISTRIBUTION_APPROVAL` | `Distribution owner` |
| `DOMAIN_EXPERT_ACCEPTANCE` | `Calculation-domain authority`, `Data-domain authority`, `Entity-data authority`, `Equity-research domain expert`, `Vocabulary authority` |
| `EXECUTION_TRUST_DOMAIN_APPROVAL` | `Execution-boundary owner` |
| `LEGAL_REVIEW` | `Competent dependency-license reviewer`, `Competent legal reviewer`, `Competent trademark or legal reviewer` |
| `MEMORY_PROMOTION` | `Responsible analyst` |
| `NAMED_OWNER_COMMITMENT` | `Golden-set owner`, `Model-grade compute owner`, `Event-monitoring owner` |
| `PRODUCT_OWNER_DECISION` | `Product owner`, `Product owner authorized to activate deferred blueprint scope`, `Product owner for memory adoption` |
| `REGULATORY_REVIEW` | `Competent regulatory reviewer` |
| `DELEGATED_ARTIFACT_APPROVAL` | exactly one distinct value across the whole ledger; the literal is deliberately not pinned (see below) |

Every value except the two `NAMED_OWNER_COMMITMENT` additions is the exact
pre-state string, freshly enumerated from the pre-state ledger. The two
additions are r5-authorized because the pre-state `NAMED_OWNER_COMMITMENT`
string `Golden-set owner` names the A-08 golden-set owner specifically and
would be false if reused for E-01 or E-04; the pre-state convention for this
approval type is one scoped owner name per accountable owner, matching
`Distribution owner` and `Execution-boundary owner`.

`DELEGATED_ARTIFACT_APPROVAL` is the only approval type whose authority is a
process role rather than a named business authority, and its single pre-state
string is exactly the vendor-lane string that §3.8 defers. Structural validation
therefore asserts that all `DELEGATED_ARTIFACT_APPROVAL` requirements share one
identical nonempty `required_authority` value without pinning the literal, so
the deferred terminology transaction can swap it atomically with no further
schema change and the one-string-per-authority invariant holds before and after.

The exact authority for each obligation §3.6 requires:

| Component | `approval_type` | Exact `required_authority` |
|---|---|---|
| `REG-A-07` | `BUDGET_APPROVAL` | `Budget owner` |
| `REG-B-14` | `ANALYST_ACCEPTANCE` | `Responsible analyst` |
| `REG-C-14` | `DATA_RIGHTS_APPROVAL` | `Data-rights authority` |
| `REG-C-16` | `ANALYST_ACCEPTANCE` | `Responsible analyst` |
| `REG-E-01` | `BUDGET_APPROVAL` | `Budget owner` |
| `REG-E-01` | `CAPACITY_COMMITMENT` | `Capacity owner` |
| `REG-E-01` | `NAMED_OWNER_COMMITMENT` | `Model-grade compute owner` |
| `REG-E-02` | `CAPACITY_COMMITMENT` | `Capacity owner` |
| `REG-E-03` | `BUDGET_APPROVAL` | `Budget owner` |
| `REG-E-03` | `PRODUCT_OWNER_DECISION` | `Product owner` |
| `REG-E-04` | `DATA_RIGHTS_APPROVAL` | `Data-rights authority` |
| `REG-E-04` | `BUDGET_APPROVAL` | `Budget owner` |
| `REG-E-04` | `NAMED_OWNER_COMMITMENT` | `Event-monitoring owner` |
| `REG-E-05` | `BUDGET_APPROVAL` | `Budget owner` |
| `PG-05-01` | `ANALYST_ACCEPTANCE` | `Responsible analyst` |
| `PG-05-02` | `ANALYST_ACCEPTANCE` | `Responsible analyst` |
| `PG-05-05` | `DOMAIN_EXPERT_ACCEPTANCE` | `Data-domain authority` |
| `PG-1-06` | `ANALYST_ACCEPTANCE` | `Responsible analyst` |
| `PG-1-09` | `CAPACITY_COMMITMENT` | `Capacity owner` |
| `PG-2-05` | `PRODUCT_OWNER_DECISION` | `Product owner` |
| `DISP-G-1` | `ANALYST_ACCEPTANCE` | `Responsible analyst` |
| `DISP-M-1` | `ANALYST_ACCEPTANCE` | `Responsible analyst` |
| `DISP-M-5` | `ANALYST_ACCEPTANCE` | `Responsible analyst` |

`PG-05-05` is the "the source-of-truth matrix is approved" clause; the
source-of-truth matrix is register `B-03`, whose pre-state domain approval is
`Data-domain authority`, so that exact string is reused rather than invented.
`REG-D-05` already carries both `PRODUCT_OWNER_DECISION` approvals; §3.6's
"separate scopes" requirement is satisfied by making their `scope` strings
distinct, not by adding an approval.

Obligation identities are closed and deterministic:

- new approval requirement IDs are `APR-<component_id>-<NN>`, `NN` zero-padded
  to two digits, continuing that row's existing maximum ordinal in ascending
  order of `approval_type` then `required_authority`;
- new evidence requirement IDs are `REQ-<component_id>-COMMAND-PROOF`,
  `REQ-<component_id>-NO-IMPLEMENTATION`,
  `REQ-<component_id>-REEVALUATION-CONTROL`, and, for each typed approval,
  `REQ-<component_id>-<APPROVAL_TYPE-IN-UPPER-KEBAB>`;
- every new requirement and approval is `UNRESOLVED` with empty
  `evidence_ref_ids`, and every new `description` and `scope` string is nonempty
  and contains no vendor model, lane, or tool name (§3.8);
- structural validation owns the exact resulting manifest of new requirement and
  approval IDs per component derived from §3.6's sets, and the evidence bundle
  reports the exact counts actually produced.

### 3.8 Role terminology reconciliation

Per the current user's standing instruction and candidate-review finding M-12,
the contract stops hard-coding vendor model lanes. `CONTEXT.md` section
"Agent roles (harness-wide)" is the single binding table; the goal points at it
and never restates a model binding.

**Closed role vocabulary.** `role` is exactly one of `ORCHESTRATOR`,
`IMPLEMENTER`, `REVIEWER`.

**Review schema (replaces the pinned `gpt-5.6-sol`/`xhigh` constants).** The
shared content-bound inventory-review schema and the `NOT_APPLICABLE`
verification-review schema become:

- a `PENDING` review has exactly its existing key set with every scalar null and
  empty evidence — unchanged from the pre-state, so no existing row changes;
- a `COMPLETE` review has exactly that key set plus `role`,
  `role_binding_path`, and `role_binding_sha256`, and must satisfy
  `role == "REVIEWER"`; `model` and `effort` are nonempty strings recording the
  model and effort actually invoked, checked for shape only and never compared
  against a vendor constant; `role_binding_path == "CONTEXT.md"`; and
  `role_binding_sha256` is a lowercase 64-hex digest of that file's bytes as
  captured at review time;
- `role_binding_sha256` is deliberately **not** a declared evidence object and
  is never re-verified against current bytes. It is an immutable historical
  capture that makes the binding auditable; making it a live `FILE_BYTES`
  reference would let an unrelated `CONTEXT.md` edit invalidate completed
  reviews, which is exactly the stale-evidence failure this transaction repairs.

Because every pre-state inventory review is `PENDING` and every pre-state
`verification_command` policy is `UNRESOLVED` (§2), this schema change requires
**zero ledger row mutations**. Rows adopt the new keys only when a review is
actually completed.

**Reason codes.** `CURRENT_SOL_XHIGH_EVIDENCE_REVIEW_MISSING` is replaced
program-wide by `CURRENT_REVIEWER_ROLE_EVIDENCE_REVIEW_MISSING`.
`REQUIREMENT_UNRESOLVED` and `HISTORICAL_REFS_UNCOVERED` are unchanged. No
reason code may contain a vendor model, lane, or tool name.

**What is preserved as historical fact and never rewritten.** These record which
model actually ran and are evidence, not policy:

- all 454 `transition_history[].invoked_model` values (freshly counted; all 454
  are `gpt-5.6-sol`);
- the 23 `open_findings[].review.model` and 23
  `open_findings[].adjudication.model` values;
- the three HR-0001..3 `question` strings in the canonical human-review
  artifact;
- the goal's `Activation record` section, including the `U1` post-activation
  routing correction dated 2026-08-13 and the activation-table rows bound to
  approved contract hash `0e63f684d43ef2afcea998135c6d77f83c023a76c4075f42a2f2c6aba3f0028f`.

`invoked_model` keeps its meaning — the model identifier actually invoked — so
new transitions record the model that actually ran. No vendor constant is
asserted anywhere in the validators.

**What is deferred to a separate transaction (`TERM-0001`).** Three
forward-looking ledger text fields still contain lane strings, freshly
enumerated from the pre-state:

| Field | Rows |
|---|---:|
| `required_approvals[].required_authority` | 123 |
| `required_evidence[].description` | 91 |
| `open_findings[].required_authority.required_for` | 23 |

Their union is exactly 123 rows: 82 inside the 107-row semantic set, 34 inside
the 34-row evidence-maintenance set where §7.2 forbids every semantic change,
and 7 outside the 144-ID scope entirely (`REG-A-12`, `REG-A-13`, `REG-B-06`,
`REG-B-12`, `REG-C-04`, `REG-C-09`, `REG-D-03`). Migrating them inside HR-0004
would require widening §7.2 for 34 rows and expanding the approved scope by 7
rows, which §1 forbids. r5 therefore chooses **schema-level redefinition now,
per-row obligation-text migration later**: the mechanical contract becomes
lane-free in this transaction at zero row cost, and `TERM-0001` migrates the
123 rows' obligation text under its own reviewed design and fresh approval, as a
single-string-to-single-string swap that the §3.7 uniformity rule already
permits without a schema change. Until then, no new obligation string may
contain a lane name; HR-0004 adds none.

**Goal prose.** The forward-looking routing, effort, dispatch, review-cap, and
review-schema paragraphs are rewritten into role vocabulary (exact list in
§7.3). The historical passages listed above are preserved verbatim.

### 3.9 What r5 explicitly refuses to authorize

For the avoidance of doubt, none of the following is authorized by this design
or by any approval of it:

- any component-ID allowlist, phase-gate exemption, or other relaxation of the
  rule that a non-conditional component carrying an activation predicate must be
  `REJECTED_ACCOUNTED` (§3.2 bullet 10);
- any `program_disposition` transition pair beyond the four pre-state pairs plus
  the single narrowly conditioned pair in §3.2 bullet 9;
- any change to `program_disposition` on a `register_row`;
- any rewriting of a historical `invoked_model`, finding-review model,
  adjudication model, HR question, or activation-record value;
- any migration of the 123 rows' lane-bearing obligation text.

### 3.10 Deliberate closure of the `scope_definition` projection question (M-2)

`controlled_state.scope_definition` is permanently the exact three-key
projection `{rule, related_register_ids, authority_effect}`. It is **not**
widened to the kind-specific keys added by §3.2 bullet 4. The reasons are
closed and stated so no later agent re-opens the question by accident:

1. every sequence-zero snapshot stores the exact controlled-field key set, and
   §8.3 requires all 454 pre-state transition objects to stay byte-for-byte
   equivalent, so widening the projection would falsify existing history;
2. the new keys are already digest-bound through the review projections, which
   §3.2 bullet 13 now makes a required whole-object rule rather than an
   incidental implementation detail — a change to `applicable_spec_ids` or
   `source_register_ids` alone invalidates any `COMPLETE` semantic review;
3. the accepted consequence is explicit: a future change to `applicable_spec_ids`
   or `source_register_ids` alone emits no `scope_definition` transition. In this
   transaction the consequence is moot but not vacuous — of the 45 rows whose
   `scope_derivation` changes, only 8 also change the three-key projection
   (`DISP-6-6`, `DISP-6-9`, `DISP-G-1`, `DISP-G-4`, `DISP-M-6`, `DISP-R-5`,
   `PG-1-11`, `PG-2-04`), while the other 37 change only the new keys. Every one
   of the 141 changed existing rows nevertheless carries at least one appended
   `AUTHORITY_RECONCILIATION` transition bound to the HR-0004 decision, because
   every scoped canonical row also changes `human_review_id` and every scoped
   alias also changes `canonical_component_id`.

If a later design wants kind-specific keys inside the replayed controlled state,
it must also define how the 454 historical snapshots are reconciled; that is out
of scope here and is not authorized by silence.

## 4. Exact HR-0004 resolution-bound scope

The r2 authority-reconciliation set of 110 IDs is correct for semantic/schema
repair, but it is not the full atomic transaction target. Fresh enumeration
finds 106 stale `FILE_BYTES` references, including 34 register rows outside
that 110-ID set. The active structural validator checks every declared
evidence object against current bytes, so a candidate cannot pass without
repairing those 34 rows too.

The r5 changes were checked against the affected-row set and do not move it.
The C-1 resolution touches `PG-2-04` and `REG-D-01`, both already in scope; the
§3.7 vocabulary touches only rows §3.6 already placed in scope; and the §3.8
terminology reconciliation changes zero ledger rows. The scope is therefore
unchanged from r4 and was re-derived from source rather than copied.

HR-0004's `scope` has sorted unique `component_ids` equal to the following full
set; `register_ids`, `spec_ids`, `bead_ids`, and `blocked_component_ids` are all
empty. The entry may not use an anchor ID or a projection shortcut:

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
immutable pre-state and three (`ALIAS-044`, `AUTH-REG-002`, `AUTH-REG-003`) are
new. Its canonical-JSON sorted-array digest, freshly recomputed while authoring
r5, is `bf6fee00d0f4510316b42b50ec13f74148df9ed44e472f2ad8be114ee3add894`.
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

1. the exact r5 path and its freshly computed full SHA-256, substituted
   externally for every `<R5_SHA256>` in the literal question without editing
   this file;
2. the five immutable pre-state hashes in §2 and the reviewed authority hashes;
3. the predetermined independent review path
   `docs/goals/reviews/ledger/equity-os-blueprint-ledger-remediation-design-r5-review-r0.md`,
   its freshly computed full SHA-256 substituted externally for
   `<R5_REVIEW_SHA256>`, reviewer/session identity, UTC timestamp, and its exact
   binding values: reviewed r5 path, reviewed-input SHA equal to `<R5_SHA256>`,
   reviewer role `REVIEWER`, the actual reviewer model and effort strings, the
   review's `role_binding_path` and `role_binding_sha256`, and verdict `CLEAN`;
4. the exact 144-ID scope, count, and canonical-JSON digest
   `bf6fee00d0f4510316b42b50ec13f74148df9ed44e472f2ad8be114ee3add894`;
   and
5. the §5.2 question with both placeholders filled only in the externally
   presented copy after the review exists.

**Byte-verbatim rendering is mandatory.** The orchestrator must render §5.2 with
exactly two substitutions — `<R5_SHA256>` and `<R5_REVIEW_SHA256>` — and **zero
insertions, deletions, reorderings, or reflowings of any other byte**, including
conjunctions, punctuation, and whitespace. The r4 attempt inserted one word
("and") and thereby failed r4 §10 step 2; that class of deviation is not
acceptable here. If the presented bytes differ from the template in any way
other than the two substitutions, the answer does not authorize the transaction
and the question must be re-asked verbatim.

The immutable review artifact must contain exactly one unambiguous binding for
the reviewed design path, reviewed-input SHA-256, reviewer role, reviewer model,
reviewer effort, role-binding path and digest, and verdict, with the values in
item 3 and no conflicting duplicate. Its own SHA-256 is computed only after
those review bytes are final. This r5 file retains placeholders, so neither the
design nor the review hashes itself.

The user must answer affirmatively in the current conversation after seeing
that completed package. Silence, the void r4-bound approval, the rejected r2
recording, an agent recommendation, or a paraphrase that omits a bound hash is
not approval.

### 5.2 Exact decision question

> Do you approve one `RECONCILE_AUTHORITY` transaction bound to independently reviewed `docs/goals/reviews/ledger/equity-os-blueprint-ledger-remediation-design-r5.md` SHA-256 `<R5_SHA256>` and predetermined independent review `docs/goals/reviews/ledger/equity-os-blueprint-ledger-remediation-design-r5-review-r0.md` SHA-256 `<R5_REVIEW_SHA256>`, whose explicit verdict is `CLEAN`, whose explicit reviewed-input SHA-256 is `<R5_SHA256>` equal to that r5 design SHA-256, and whose reviewer role is `REVIEWER` under the `CONTEXT.md` "Agent roles" binding with its actual invoked model and effort recorded in the review, superseding and voiding the earlier approval bound to r4 SHA-256 `c1ab125880ec1895a344b57f7aaef8d372836fa0ded9c900a1aae9284b295e00`; active-goal pre-state SHA-256 `dabad7bfe3d2765a5ac9687376029d8587b4b2ac95bc03494155a974e5ddc67f`, ledger pre-state SHA-256 `51091042dae87d2f41fbbf02d77ab1619c6a1008a022baec4233c44a0e295e13`, human-review pre-state SHA-256 `54c1e183def8e0b1b91504effbf20c233b3d1352fd65d4910e89c2b913ee5702`, v2-register SHA-256 `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, disposition-report SHA-256 `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`, and exact 144-ID scope digest `bf6fee00d0f4510316b42b50ec13f74148df9ed44e472f2ad8be114ee3add894`, authorizing only one atomic change to the goal, its three validator surfaces plus extractor interface, the canonical ledger, and canonical human-review artifact that records and resolves HR-0004 over that exact full structured scope, including current-digest repair for every freshly enumerated stale declared evidence object while resetting `REQ-DISP-R-1-NO-IMPLEMENTATION` to `UNRESOLVED` with empty evidence refs and treating its unchanged rejection-record refs as historical rather than current proof; sets `PG-2-04.related_register_ids` to `["D-01","D-03"]` so that exactly one row moves `CONDITIONAL_UNACTIVATED` to `REQUIRED_NOW` with its activation predicate removed and no activation record created, without relaxing the rule that a required component may not carry an activation predicate; closes the required-authority vocabulary and replaces every vendor model lane in the validator-checked review schema and reason codes with the `ORCHESTRATOR`/`IMPLEMENTER`/`REVIEWER` role vocabulary bound to `CONTEXT.md`, changing no ledger row for that purpose and rewriting no historical model record; produces exactly 213 ledger rows = 169 canonical + 44 aliases; preserves all 454 existing transition objects as exact prefixes and preserves HR-0001..3 open and unresolved; changes no pinned blueprint bytes or register Status cells; activates no Deferred component; advances no delivery or gate state; and aborts without canonical change on any design hash, review path/hash/verdict/reviewed-input/role binding, scope, validation, or replacement failure?

Recommendation: approve only that exact package. Safe default: do not create
HR-0004 and leave every canonical byte unchanged; product implementation stays
blocked.

### 5.3 Approval evidence without invented citation

The transaction records the actual user message, not a reconstructed quote or
fabricated URI. The candidate goal adds one authority-reconciliation record
containing the exact completed §5.2 question bytes as presented to the user,
the exact user response bytes, actual runtime-supplied UTC timestamp and
conversation/goal-tool identifier, the r5 path/SHA, review
path/SHA/verdict/reviewed-input SHA/role/model/effort/binding digest, scope
digest, and all five pre-state hashes. The completed question bytes themselves
contain those same immutable review bindings, so the stored question/response
pair proves which exact review the user approved. The HR-0004 entry and
resolution use a `UTF8_LINE_SPAN` evidence object that points to that exact
post-transaction goal span and hashes it under the existing evidence rules.
This creates no digest cycle: the goal span contains no HR entry, resolution, or
ledger digest.

The runtime metadata — recorded UTC timestamp, conversation/session identifier,
and authenticated current-user designation — is **parsed from the approval
capture file the orchestrator writes at approval time**, never hard-coded in
migrator source. A mismatch between the parsed values and the capture file, or a
missing value, aborts before any write. If the runtime cannot supply the exact
response bytes, authenticated-current-user designation, timestamp, and a stable
conversation/goal-tool identifier, the transaction must not start.

Before any canonical write, structural reconciliation reads the fixed r5 and
review paths, hashes their exact bytes, parses the review's unique binding, and
compares the actual design SHA, review SHA, verdict, reviewed-input SHA, role,
model, effort, and role-binding digest with both the completed question and the
candidate goal record. It also requires the reviewed-input SHA to equal the
actual r5 SHA. A missing, ambiguous, changed, substituted, non-`CLEAN`,
wrong-input, or wrong-role review fails before replacement; matching
agent-authored fields in the candidate do not suffice.

The evidence scope says only what is mechanically true. It does not invent a
legal name, URL, message ID, transcript, or citation. Conversation memory or
an agent-authored paraphrase is inadmissible. The HR-0004 resolution actor is
`actor_type=HUMAN`, role `CURRENT_USER`, with the stable identity/display values
actually supplied by the runtime; the existing goal's truthful
`Current authenticated chat user` designation may be used as the display value
but never as a legal name. `authority_basis` exactly matches the entry's
`GOAL_OR_PROCESS_AUTHORIZATION` and cites the real goal-span approval evidence.

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
is created. `CONTEXT.md` is the role-binding authority and is **not** a
transaction target: it is read for its digest capture only, and the transaction
must abort if it would write to it. The one-shot migrator executes from a
private temporary directory after approval and is removed after the evidence
bundle is complete; it never becomes a repository mutation.

Forbidden changes include both pinned blueprint authorities, all specs and
review artifacts including this r5 file and its predetermined independent
review, every other goal/review/workstream file, `CONTEXT.md`, the bootstrap
generator, Beads/Dolt state, `.beads/issues.jsonl`, Git index, Git history,
commits, pushes, product code, and every unrelated dirty path. No register
Status cell may change.

### 6.2 Transaction boundary and rollback

The transaction is a manifest-controlled compare-and-swap over exactly the six
canonical paths:

1. Acquire an exclusive repository-local transaction lock. Run the startup
   recovery check **in both `--prepare` and `--execute`**: any nonterminal
   journal stops the run with an explicit recovery notice naming the journal
   path, its state, and its unproven paths — never a generic hash-mismatch
   message. Reject a symlinked target, duplicate target, non-regular pre-state
   target, or filesystem that cannot support same-directory atomic replacement
   for every target. The atomic-replacement probe runs **inside the
   transaction's private staging directory, never inside `docs/goals/` or
   `scripts/equity_os_blueprint/`**, and must rename one probe file over a
   second existing probe file; a self-rename does not demonstrate replacement.
2. Verify external-tool preconditions that the post-replacement validation
   depends on, including the read-only Beads lookup the structural validator
   performs. A missing or failing external dependency aborts **before** any
   write, so it can never trigger the rollback path for an unrelated reason.
3. Read and retain every preimage byte string in memory and in a private
   same-filesystem staging directory, together with each target's exact
   filesystem mode. Verify the five immutable hashes, the three script
   pre-state hashes, the full r5 digest, predetermined clean-review
   path/digest/verdict/reviewed-input SHA/role/model/effort/binding digest,
   exact completed question and response bytes parsed from the approval
   capture, exact 144-ID manifest/digest, authority hashes, expected Git-index
   bytes, and the allowed-path dirty-tree baseline. **The dirty-tree baseline is
   enforced, not merely captured**: the set of dirty paths outside the six
   targets must equal the recorded baseline exactly, and a dirty allowed-path
   target must be explicitly acknowledged in the baseline or abort. The
   r5/review bindings must also pass the independent structural reconciliation
   comparison in §5.3. Any mismatch exits before writing.
4. Build every candidate byte string in memory. Write candidates with exclusive
   creation to same-directory temporary files, set each temporary file's mode to
   its target's recorded pre-state mode, `fsync` each file, validate only the
   temporary candidates, and `fsync` their directories. Temporary names are
   never canonical. **Every temporary path is registered in a cleanup set and
   unlinked on any exit that is not `COMMITTED`**, using a `try`/`finally` that
   covers creation, validation, and replacement.
5. Write and `fsync` a transaction journal containing transaction ID,
   pre/post hashes, pre-state modes, exact target order, temp paths,
   backup/preimage paths, approval and review digests, 144-ID scope digest,
   validator results, and state `PREPARED`.
6. Replace targets in deterministic order: goal, structural validator,
   preimplementation validator, extractor, ledger, and human review. Before
   each replacement compare the live target to its recorded prehash. Use
   same-directory atomic rename. After each rename, verify the replaced file's
   mode equals the recorded pre-state mode, then update and `fsync` the journal.
7. Rerun canonical-path validation, compare every canonical posthash to the
   prepared candidate hash, re-derive the dirty-path set and Git-index bytes and
   compare them to the recorded baseline allowing only the six targets to
   differ. Only then mark and `fsync` `COMMITTED`, `fsync` directories, release
   the lock, and retain the evidence bundle.

Filesystem rename is atomic per path, not across paths. Therefore the journal
and rollback protocol are part of the transaction boundary. On any failure
after the first replacement, restore every replaced path from its exact
preimage in reverse order using same-directory atomic rename, **restore each
file's exact pre-state mode**, `fsync` restored files/directories, verify all
original hashes **and modes**, mark `ROLLED_BACK`, and exit nonzero. A rollback
may be reported as proven only when both bytes and mode match the preimage for
every replaced path.

**Interrupt safety.** The replacement and post-replacement blocks must be
guarded at `BaseException` level, or by `SIGINT`/`SIGTERM` handlers that route
into the same rollback path, so that `KeyboardInterrupt` and `SystemExit` cannot
leave a mixed authority state. The guard re-raises after rollback completes.

If automatic rollback cannot prove every prehash and mode, write
`RECOVERY_REQUIRED` with the exact unproven path/hash/mode list, stop all goal
mutations, and report it. The durable guard against re-mutation is the
nonterminal journal checked in step 1 of both modes; the design does not claim a
process-held file lock survives process exit.

**Rollback rehearsal is mandatory before the first `--execute`.** Because the
rollback path has never been executed, the operator must first run it end-to-end
in an isolated full-tree replica committed at the pre-state, forcing a failure
after at least one and before the last replacement, and prove that every target
is restored to its exact pre-state bytes and mode, that no temporary file
survives, that the journal reaches `ROLLED_BACK`, and that an interrupt during
replacement reaches the same outcome. The rehearsal transcript is part of the
evidence bundle.

No staging, commit, push, or Beads mutation is inside or implied by this
transaction.

### 6.3 Candidate-validation root

Candidate validation runs from a private, same-filesystem staging root that
hardlinks the `docs/` tree and substitutes the candidate goal at its canonical
relative path, invoked with `cwd` at that root and literal `--repo-root .`. This
is the only reading under which §5.3's post-transaction `UTF8_LINE_SPAN`
evidence and §8.2's `--repo-root .` are simultaneously satisfiable before any
canonical byte changes; §8.1's rule that alternate artifact arguments may be
absolute while stored paths resolve under `--repo-root` supports it.

Two requirements close the caveats the candidate review raised:

1. **Teardown is mandatory.** The staging root is removed immediately after
   candidate validation completes, and the evidence bundle records its removal.
   While it exists, canonical `docs/` files share inodes with it, so any
   in-place write through an overlay path would corrupt a canonical file; no
   process other than the validators may run against that root, and the
   migrator must verify the canonical hashes again after teardown.
2. **The literal-root invocation must fail closed.** Running the candidate
   structural validator with `cwd` at the repository root must exit 2 with an
   explicit message naming the unresolvable evidence span, not raise an
   uncaught `AssertionError` with a traceback. The candidate structural
   validator therefore converts an out-of-range `UTF8_LINE_SPAN` target into a
   fail-closed exit-2 diagnostic.

## 7. Deterministic migration algorithm

1. **Recheck authority.** Verify every §2 prehash, the three script pre-state
   hashes, the exact r5 and predetermined review bindings, completed approval
   question/response bytes parsed from the approval capture, exact allowed path
   set, unchanged Git index, and unchanged unrelated dirty baseline under the
   exclusive lock.
2. **Amend the contract in memory.** Apply only §§3–6, §7.3, and §8 to the
   active goal; update its three embedded validators together. Extract the first
   two into candidate scripts and require byte identity with the candidates.
3. **Build the HR candidate.** Preserve HR-0001..3 as exact JSON values. Add one
   HR-0004 entry with the exact 144-ID scope and evidence described above, plus
   exactly one sequence-next `RECONCILE_AUTHORITY` decision bound to the
   immutable entry authority projection. Do not reuse the rejected r2 HR-0004
   draft or its partial scope.
4. **Migrate schema and semantics.** Apply the exact aliases, crosswalks,
   negative control, sequences, predicates, the §3.5.1 `PG-2-04` resolution, the
   §3.7 vocabulary and obligation identities, proof inventories, gate refs,
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
   For `DISP-R-1`, updating `EV-DISP-R-1-SPEC-DRAFT` to the current digest must
   be followed by the exact §3.6 requirement reset; its evidence inventory
   review stays `PENDING`, and its unchanged rejection-record ref cannot be
   consumed as current proof.
6. **Append histories.** Never edit, reorder, delete, or insert within any of
   the 454 existing transition arrays. For each changed existing row, append
   one transition per changed controlled field in a validator-owned fixed field
   order. Use truthful current UTC times, unique IDs, the previous terminal
   hash, current evidence, the actual invoked model in `invoked_model`, and the
   HR-0004 decision ID/digest for every authority reconciliation. New IDs begin
   with the authorized sequence-zero reconciliation defined in §3.2 bullet 8.
7. **Validate candidates.** Run §8 against only the candidate paths, then tear
   down the staging root per §6.3. On any failure, delete every temporary
   candidate, preserve canonical bytes, and exit nonzero. There is no partial
   acceptance or automatic scope widening.
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

**One additional field is allowed on exactly one row.** `program_disposition`
may change on `PG-2-04` only, only from `CONDITIONAL_UNACTIVATED` to
`REQUIRED_NOW`, only as the derived consequence of the §3.5.1
`related_register_ids` correction, and only together with
`activation_predicate` becoming `null`. No other row may change
`program_disposition`, and no register row may change it at all. The validator
owns this single-row exception as an exact manifest, not a kind-level or
gate-level allowance.

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

The proof-specific mutable delta for `DISP-R-1` is closed: within
`evidence_refs`, only `EV-DISP-R-1-SPEC-DRAFT.content_sha256` and
`.captured_at` change to the freshly observed current values; within
`required_evidence`, only
`REQ-DISP-R-1-NO-IMPLEMENTATION.status` changes from `SATISFIED` to
`UNRESOLVED` and its `evidence_ref_ids` changes from
`["EV-DISP-R-1-SPEC-DRAFT"]` to `[]`. Its already-`PENDING`
`evidence_inventory_review` stays unchanged. Its `rejection_record`, including
`no_implementation_evidence_ref_ids=["EV-DISP-R-1-SPEC-DRAFT"]`, is retained
exactly as historical authority-accounting metadata; it is not cleared and is
not current proof.

All 454 existing transition objects remain exact prefixes. In particular,
`DISP-R-1`'s existing sequence-zero controlled-state preimage retains the exact
unchanged rejection record and its historical ref ID. `evidence_refs` and
`required_evidence` are not fields in the existing controlled-state replay, so
this design does not falsely claim that transition history stores their old
objects: their exact pretransaction JSON is preserved in the protected ledger
preimage and stale-evidence mapping in the evidence bundle. The appended
HR-0004 link transition and resulting history digest follow the ordinary fixed
field order; no existing history object is edited to manufacture proof.

### 7.3 Exact goal-prose amendment list

The goal is the authoritative narrative contract. After this transaction no
prose claim in it may be falsified by its own embedded validators or by the
ledger. Every item below is an exact-match, fail-loud patch; pre-state line
numbers refer to the goal at SHA-256
`dabad7bfe3d2765a5ac9687376029d8587b4b2ac95bc03494155a974e5ddc67f`.

**A. Closed-schema statements (candidate-review finding I-1).**

| # | Pre-state anchor | Required amendment |
|---|---|---|
| A1 | lines 223–225, "Every non-register canonical component has a `scope_derivation` object with…" | state the kind-specific key sets of §3.2 bullet 4: `disposition_item` adds `applicable_spec_ids`; `sequence_clause` adds `source_register_ids` and `applicable_spec_ids`; every other kind rejects both; arrays sorted and unique |
| A2 | lines 227–237, rule-by-kind table | `phase_gate_clause` maps to `RELATED_REGISTER_SCOPE` **or** `ACTIVE_NEGATIVE_CONTROL` |
| A3 | lines 239–249, rule-semantics paragraph | add the closed `ACTIVE_NEGATIVE_CONTROL` semantics of §3.2 bullet 5, including its `REQUIRED_NOW` derivation, `activation_predicate=null`, and gate-proof invalidation conditions |
| A4 | lines 259–262, predicate applicability | restate as §3.2 bullet 10: a component derived `REQUIRED_NOW`, including by related-register aggregation, has `activation_predicate=null`; conditional components, registers captured `Deferred`, and `REJECTED_ACCOUNTED` components may carry one |
| A5 | lines 270–274, `COMPARE` leaf definition | add the `COMPARE_METRICS` leaf, operand typing, and comparator sets of §3.2 bullet 7 |
| A6 | §"Typed evidence and verification proof" (from line 395) | add the closed current no-implementation-proof predicate of §3.2 bullet 6, and state that historical rejection refs are not current proof |
| A7 | §"State transitions" (from line 559) | add the sequence-zero `AUTHORITY_RECONCILIATION` rule of §3.2 bullet 8, the §3.2 bullet 2 link-growth rule, and the §3.2 bullet 9 disposition pair with all five of its conditions |
| A8 | §"Disposition derivation and authority records" (from line 198) | state the §3.5.1 `PG-2-04` outcome as contract: an aggregated `REQUIRED_NOW` phase-gate clause carries no activation predicate, and its observable conjunction lives in its command-proof obligation |
| A9 | §"Typed approval proof" (from line 461) | embed the §3.7 vocabulary table and the `DELEGATED_ARTIFACT_APPROVAL` uniformity rule |
| A10 | §"Canonical blueprint component ledger" inventory prose (from line 129) | the exact 213/169/44 inventory, the four authority clauses, the compound-alias schema of §3.2 bullet 1, and the multi-ID `human_review_id` schema of §3.2 bullet 2 |
| A11 | §"Content-bound inventory reviews" (from line 350) | state the whole-object review projection rule of §3.2 bullet 13 |

**B. Role terminology (user instruction and finding M-12).** Rewrite these
forward-looking passages into `ORCHESTRATOR`/`IMPLEMENTER`/`REVIEWER` vocabulary
with a single pointer to `CONTEXT.md` "Agent roles (harness-wide)" as the
binding table, restating no model binding in the goal: lines 26–43; line 116;
line 251; line 386; lines 423 and 439; line 516; line 654; lines 752–786; lines
792–824 including the role table and the CLI invocation block; line 829; line
858; lines 1158–1173; and line 4089. The two embedded validator literals at
lines 1486 and 3246 are replaced by the §3.8 role rule.

**C. Preserved verbatim.** Lines 4114–4116 and the activation-record table rows
at lines 4132 and 4135, and every other line in §"Activation record", are
historical approval evidence bound to contract hash
`0e63f684d43ef2afcea998135c6d77f83c023a76c4075f42a2f2c6aba3f0028f` and are not
rewritten.

**D. Mechanical anti-drift check.** `extract_goal_validators.py` already reads
the goal. It gains a closed list of exact required marker substrings — one per
item A1–A11 — and asserts that each appears at least once in the goal outside
the three embedded program spans, exiting nonzero otherwise. This makes a future
prose/validator divergence fail loudly instead of silently, which is the defect
class I-1 identified.

## 8. Mechanical validator and evidence contract

### 8.1 Required validator interfaces

- Structural: required `--repo-root`, plus paired `--ledger-path` and
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
  and checks the resulting prefix projection against that digest. An
  unresolvable `UTF8_LINE_SPAN` evidence target exits 2 with an explicit
  diagnostic, never an uncaught traceback (§6.3).
- Preimplementation: required `--repo-root`, optional `--ledger-path`, and
  `--report-blockers`. The reporting flag performs the same digest checks on
  every `COMPLETE` review, emits exact `PENDING`/stale review IDs as JSON, and
  exits 2 when the gate is not ready; it never converts or waives a review. It
  also evaluates the closed current no-implementation-proof predicate for every
  rejected component.
- Terminal: required `--repo-root`, the same paired candidate paths as
  structural, plus `--report-blockers`. The ordinary path remains SUCCESS-only.
  Reporting mode derives current active/dormant/rejected state and emits unmet
  SUCCESS conditions as JSON with exit 2; it never grants a terminal state.
  Rejected state is accounted only after the record-authority checks; it does
  not waive the separate current no-implementation-proof predicate.
- Extractor: optional `--goal-path`, `--structural-output`,
  `--preimplementation-output`, and `--terminal-output`. Default `--check`
  retains byte-exact checking of the two checked-in scripts; explicit outputs
  allow all three programs from a candidate goal to be compared and syntax
  checked without a canonical write. It also runs the §7.3 D marker check.
- Alternate artifact arguments may be absolute. Every path stored inside the
  ledger remains repo-relative and resolves under `--repo-root`. Evidence may
  target neither selected ledger nor selected human-review artifact.

Structural validation independently owns exact occurrence manifests for every
phase gate, deferral, scale trigger, disposition, authority, sequence,
document-strategy clause, and alias; exact target/crosswalk/gate/sequence maps;
exact schema keys; the 213/169/44 inventory; the exact 144-ID HR-0004 scope;
multi-HR reverse links; eligible delegated-approval evidence; new-history form;
the 454-history prefix invariant; the §3.7 approval-authority vocabulary; the
§3.8 role vocabulary; and the single-row `PG-2-04` `program_disposition`
exception of §7.2. In reconciliation mode it also owns the exact r5/review
binding comparison from §5.3, the exact
`DISP-R-1 -> REQ-DISP-R-1-NO-IMPLEMENTATION` proof map, the rule that false
current proof is structurally valid, and the rule that every post-state
`(approval_type, required_authority)` pair exists in the baseline or in §3.7's
authorized additions. It requires the §3.6 unresolved object and false
current-proof result in this post-state. It never imports generator constants.

Both reporting validators must include this exact unresolved proof in their
not-ready JSON under `unmet_no_implementation_proof`: component ID
`DISP-R-1`, requirement ID `REQ-DISP-R-1-NO-IMPLEMENTATION`, historical ref ID
`EV-DISP-R-1-SPEC-DRAFT`, and reason codes `REQUIREMENT_UNRESOLVED` and
`CURRENT_REVIEWER_ROLE_EVIDENCE_REVIEW_MISSING`. The list is a required subset,
not a fixed length: `HISTORICAL_REFS_UNCOVERED` is a true conjunct of the closed
predicate under the emptied `evidence_ref_ids` and must also be emitted. Digest
refresh alone may not remove any of them.

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
failure. Current baseline reviews are `PENDING`, delivery is incomplete,
`DISP-R-1` current no-implementation proof is unmet, and HR-0001..3 remain open,
so this transaction is not allowed to make either gate pass. Product work
resumes only after later fresh inventory reviews and proof satisfy the ordinary
structural-plus-preimplementation sequence.

Retain the candidate-extracted terminal program in protected transaction
staging as `<protected-postreplacement-terminal>` through post-replacement
validation. Because the canonical goal posthash must equal the prepared
candidate goal hash, those bytes are the exact terminal program embedded in the
canonical replacement. After canonical replacement run these explicit
commands; structural, preimplementation, and terminal use the same required
repository root and explicit artifact-path resolution as their candidate
invocations:

```bash
python3 scripts/equity_os_blueprint/extract_goal_validators.py --check
python3 scripts/equity_os_blueprint/validate_ledger_structural.py --repo-root . \
  --ledger-path docs/goals/equity-os-blueprint-component-ledger.jsonl \
  --human-review-path docs/goals/equity-os-blueprint-human-review-needed.md \
  --reconciliation-check \
  --reconciliation-baseline-ledger-path <protected-preimage-ledger> \
  --reconciliation-baseline-human-review-path <protected-preimage-human-review>
python3 scripts/equity_os_blueprint/validate_ledger_preimplementation.py --repo-root . \
  --ledger-path docs/goals/equity-os-blueprint-component-ledger.jsonl \
  --report-blockers
python3 <protected-postreplacement-terminal> --repo-root . \
  --ledger-path docs/goals/equity-os-blueprint-component-ledger.jsonl \
  --human-review-path docs/goals/equity-os-blueprint-human-review-needed.md \
  --report-blockers
git diff --check -- docs/goals/equity-os-blueprint-completion.md \
  scripts/equity_os_blueprint/validate_ledger_structural.py \
  scripts/equity_os_blueprint/validate_ledger_preimplementation.py \
  scripts/equity_os_blueprint/extract_goal_validators.py \
  docs/goals/equity-os-blueprint-component-ledger.jsonl \
  docs/goals/equity-os-blueprint-human-review-needed.md
git status --porcelain
git status --short --branch
```

The post-replacement structural result must exit 0. The explicit
preimplementation and terminal invocations must reproduce the candidate's
exit-2 not-ready result and required `DISP-R-1` blocker object. `git status
--porcelain` output is compared against the recorded dirty baseline, allowing
only the six targets to differ; `git diff --check` and `git status --short
--branch` are recorded. Because Git does not track non-executable mode bits,
these commands cannot detect a permission change, so the explicit mode
comparison in §6.2 is the only guard for it and is mandatory.

### 8.3 Mandatory postconditions

Every postcondition is evaluated against the resulting bytes, never by asking
mutable files to retain pre-state hashes:

- canonical posthashes equal the prepared candidate hashes and differ from a
  prehash only for allowed paths; **every target's filesystem mode equals its
  recorded pre-state mode**; both pinned blueprint hashes remain exact;
  `CONTEXT.md` is byte-unchanged; the actual r5/review paths, byte hashes,
  `CLEAN` verdict, reviewed-input SHA, role, model, effort, and role-binding
  digest equal every value bound in the completed question, response record, and
  structural reconciliation result;
- 213 unique rows = 169 canonical + 44 aliases, with exact kind counts
  `60/35/13/8/32/4/11/6/44` and all source occurrences/crosswalks exact;
- every one of the 454 pre-state transition objects remains byte-for-byte
  equivalent as canonical JSON at the same per-row index; every existing
  history is an exact prefix; all appended/new chains and history digests
  recompute;
- HR-0004 has exactly one active `RECONCILE_AUTHORITY` resolution, exact
  144-ID structured scope, exact approval/review/r5/prehash evidence, and valid
  entry/resolution/hash-chain digests; HR-0001..3 remain open, blocking,
  unresolved, and otherwise unchanged;
- all 23 preexisting finding-bearing and blocked rows retain their findings and
  blockers; all 23 prior HR links remain, with overlaps represented by arrays;
- register state remains exactly 45 `Open` and 15 `Deferred`; all
  `activation_record` values remain null; no `source_status` or
  `activation_source_status` changes; all originally Deferred rows remain
  `CONDITIONAL_UNACTIVATED` and no new implementation reference exists;
- exactly one row changes `program_disposition`: `PG-2-04`, from
  `CONDITIONAL_UNACTIVATED` to `REQUIRED_NOW`, with `activation_predicate=null`,
  no `activation_record`, `gate_result` still `NOT_EVALUATED`, and a derivation
  that recomputes from `["D-01","D-03"]`; no other row and no register row
  changes it; no component derived `REQUIRED_NOW` carries a predicate;
- every `required_approvals` entry satisfies the §3.7 vocabulary, and every
  `(approval_type, required_authority)` pair exists in the baseline ledger or in
  §3.7's authorized additions;
- every inventory review remains `PENDING` and every `verification_command`
  policy remains `UNRESOLVED`, so no review gains the §3.8 `COMPLETE`-only keys;
  no validator asserts a vendor model or effort constant; no reason code
  contains a lane name; all 454 historical `invoked_model` values and all 23
  finding-review and 23 adjudication model values are unchanged;
- no delivery state advances: every row's post-state delivery ordinal is less
  than or equal to its pre-state ordinal, with only the authorized `DEF-12`
  reset allowed; every gate remains `NOT_EVALUATED`; no new satisfied evidence,
  approval, approval record, verification result, or `verified_at` exists;
- `DISP-R-1.rejection_record` is unchanged and retains its historical ref;
  `REQ-DISP-R-1-NO-IMPLEMENTATION` equals the exact §3.6 `UNRESOLVED` object;
  the current no-implementation-proof predicate is false; and both reporting
  validators emit its exact unmet-proof blocker and exit 2;
- every evidence object validates against current bytes; the evidence bundle
  contains the exact stale preimage-to-current mapping without claiming the
  refresh as delivery, approval, or no-implementation proof; and
- the Git index bytes are unchanged; the re-derived dirty-path set differs from
  the recorded baseline only by the six targets; the staging root is removed;
  no temporary candidate file survives; and no Beads, commit, push, blueprint,
  spec, review, generator, or unrelated dirty path changed.

### 8.4 Evidence bundle

The retained bundle contains canonical JSON plus referenced raw command output.
Every item below is mandatory; an absent item is a bundle defect, because §6.1
forbids committing anything in this transaction and the bundle is therefore the
only durable record of what changed:

- transaction ID, timestamps, lock identity, **the complete final journal
  document**, final state, target manifest, pre/post hashes, **pre-state and
  post-state filesystem modes**, candidate hashes, replacement order,
  **rollback result including per-path byte and mode proof**, the rollback
  rehearsal transcript required by §6.2, staging-root creation and teardown
  records, and unrelated-dirty/index baselines with their post-replacement
  re-derivations;
- r5 path/SHA, predetermined review path/SHA, parsed `CLEAN` verdict, reviewed-
  input SHA, reviewer role/model/effort and role-binding path/digest, exact
  completed question and response bytes/digests together with the parsed
  runtime metadata and its source file, HR entry/resolution digests, and
  expanded 144-ID list/digest;
- exact pre-state ledger row-ID list, **all 454 transition objects in full**
  and their manifest digest, HR-0001..3 projections, counts, statuses,
  findings, blockers, links, delivery/gate state, and pinned authority hashes;
- **exact field-level ledger and human-review semantic diff**, per row and per
  field, with old and new canonical JSON values; new-component manifests;
  old-history prefix comparison per row; HR reverse-link comparison; the exact
  `PG-2-04` before/after projection; and the exact new
  requirement/approval manifest with its counts;
- fresh stale-evidence inventory with every old/current digest, the exact
  `DISP-R-1` requirement reset, unchanged historical rejection refs, false
  current-proof result, and proof-reset disposition; and
- every candidate and canonical validator argv, exit code, stdout/stderr
  digest, extractor byte-equality result, marker-check result, external-tool
  precondition result, `git diff --check`, `git status --porcelain`, and final
  `git status --short --branch`.

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
must use a separate one-shot migrator. `scripts/equity_os_blueprint/generate_initial_ledger.py`
is not one of the six allowed paths and must not be read for constants or
modified. Its emitted schema will diverge further once this transaction
executes; tracking that divergence is separate work.

Generator work remains independent from HR-0004 migration authority: it is
neither a prerequisite nor an authorization for the transaction. Only the
fresh, hash-bound user approval in §5 can authorize creation and resolution of
HR-0004 and execution of the bounded migration.

## 10. Executor handoff

1. Commission one clean, independent, exact-byte `REVIEWER`-role review of this
   r5 file at the predetermined r5-review-r0 path. The reviewer must not be the
   agent or context that authored r5. Any finding or binding mismatch stops the
   lane and requires a new reviewed design revision.
2. After `CLEAN`, compute the r5, review, and scope digests; externally fill only
   the two §5.2 placeholders; and ask that completed question byte-verbatim with
   zero other insertions. Preserve all canonical pre-state bytes while waiting.
3. After a fresh affirmative user answer, capture real approval evidence in the
   approval-capture file and implement one one-shot migrator plus the
   contract/validator candidates.
4. Rehearse the rollback and interrupt paths per §6.2 in an isolated replica.
5. Run the complete temporary-artifact proof, then the journaled compare-and-
   swap transaction; stop after the evidence bundle and hand off for separate
   review. Do not stage, commit, push, modify Beads, or resume product work.
6. Track the deferred `TERM-0001` obligation-text migration (§3.8) as separate
   work with its own design, independent review, and fresh user approval.

**Hard prohibition:** no migration, HR-0004 entry or resolution, canonical
goal/validator/ledger/human-review mutation, or approval record may be
created before both a clean independent review at the predetermined path of the
exact r5 SHA and a fresh current-user approval explicitly bound to that review
and the completed §5 question. The approval recorded against r4 is void and
cannot be substituted. A failed precondition, changed r5 or review byte,
non-clean/wrong-input/wrong-role review, incomplete answer, non-verbatim
question, missing exact-message evidence, validator failure, or rollback
uncertainty ends the attempt fail-closed with canonical pre-state restored.
