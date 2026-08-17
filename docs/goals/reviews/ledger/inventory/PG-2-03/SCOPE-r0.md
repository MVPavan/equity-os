# Inventory review — PG-2-03 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `PG-2-03` |
| `review_type` | `SCOPE` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `c43733f6-8986-4487-8aa6-2f7b5b723107` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-16T03:52:19Z` |

Role binding: `CONTEXT.md` "Agent roles (harness-wide)" L137-139 and L147 bind
`REVIEWER` to Claude Opus 5 at high effort, in an agent and context independent
of any `IMPLEMENTER` that produced the reviewed content. The digest above is the
`CONTEXT.md` bytes at review time and is an immutable historical capture.

## Input hashes read for this review

| Input | SHA-256 |
|---|---|
| `docs/goals/equity-os-blueprint-completion.md` (active goal) | `f15f7ab5a4e425dec3877ab7f1f7594687979060e4dbcd49390a8a8d5fedb85f` |
| `docs/goals/equity-os-blueprint-component-ledger.jsonl` (canonical ledger) | `de236d7e8dcf02e307ec58797f5722ae2f85d1d8cdba57d4ecc07df5383c9c97` |
| `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` (pinned v2 register) | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| `docs/blueprint/funda-third-order-review-disposition-report.md` (pinned disposition report) | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| `scripts/equity_os_blueprint/validate_ledger_structural.py` (structural validator) | `731d0d8b208b577967c92e3992e7ec1a4333cdecbf89f6951c32d2ec469436f9` |
| `scripts/equity_os_blueprint/validate_ledger_preimplementation.py` | `f7a225a1f99cb85c92cde3094505a92a746552280eb45dae0253a71ab9048013` |
| `scripts/equity_os_blueprint/extract_goal_validators.py` | `5d20d796666d1154fb3c84ba4fa7407ee82819510a5ac06254f7f4a3126c6f2a` |
| `docs/goals/equity-os-blueprint-human-review-needed.md` | `094fcdfab74a3f4c6fdb82b1520fc4d13b636ac0e9ed10194e5d607aed2ce9af` |
| `CONTEXT.md` (role binding) | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r2.md` (artifact format) | `adf908ac8cec01a55a53438624c6a8913f673f5b7cecd3e955fc4919f73803fb` |

Fresh structural validation at these exact bytes:
`python3 scripts/equity_os_blueprint/validate_ledger_structural.py --repo-root .`
→ exit `0` (run at review time).

## Reviewed inventory, exactly as read

`review_inventory_projection(row, "SCOPE")` — canonical JSON:

```json
{"activation_predicate":{"evaluated_at":null,"evaluation_sha256":null,"expression":{"args":[{"comparator":"NE","expected":"","metric_id":"MTR-PG-2-03-TEST-RESULT-ID","op":"COMPARE"},{"comparator":"GT","expected":0,"metric_id":"MTR-PG-2-03-PROMOTION-CASES-EXECUTED","op":"COMPARE"},{"comparator":"EQ","expected":0,"metric_id":"MTR-PG-2-03-SQL-METADATA-DIVERGENCE-COUNT","op":"COMPARE"},{"comparator":"EQ","expected":0,"metric_id":"MTR-PG-2-03-PARTIAL-WRITE-ESCAPE-COUNT","op":"COMPARE"}],"op":"ALL"},"metrics":[{"evidence_ref_id":null,"json_pointer":"/phase_gates/pg_2_03/partial_write_escape_count","metric_id":"MTR-PG-2-03-PARTIAL-WRITE-ESCAPE-COUNT","register_ids":[],"source_kind":"EVIDENCE_JSON","valid_until":null,"value_type":"INTEGER"},{"evidence_ref_id":null,"json_pointer":"/phase_gates/pg_2_03/promotion_cases_executed","metric_id":"MTR-PG-2-03-PROMOTION-CASES-EXECUTED","register_ids":[],"source_kind":"EVIDENCE_JSON","valid_until":null,"value_type":"INTEGER"},{"evidence_ref_id":null,"json_pointer":"/phase_gates/pg_2_03/sql_metadata_divergence_count","metric_id":"MTR-PG-2-03-SQL-METADATA-DIVERGENCE-COUNT","register_ids":[],"source_kind":"EVIDENCE_JSON","valid_until":null,"value_type":"INTEGER"},{"evidence_ref_id":null,"json_pointer":"/phase_gates/pg_2_03/test_result_id","metric_id":"MTR-PG-2-03-TEST-RESULT-ID","register_ids":[],"source_kind":"EVIDENCE_JSON","valid_until":null,"value_type":"STRING"}],"predicate_id":"AP-PG-2-03","result":"UNKNOWN"},"disposition_refs":[],"gate_refs":[],"related_register_ids":["D-03"],"scope_derivation":{"authority_effect":null,"derived_program_disposition":"CONDITIONAL_UNACTIVATED","related_register_ids":["D-03"],"rule":"RELATED_REGISTER_SCOPE"}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 —
appending review evidence mutates `evidence_refs` and therefore the input
projection):

- `reviewed_input_sha256` (pre-record): `243008294a0c9ecf90d27c75e7180f0a39ddd2a1817c1613deb3963c5f7c917a`
- `reviewed_inventory_sha256` (pre-record): `15be0688cb1e65e15b5422f702d6ab45a58f122755442707a3141275a6f96970`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md`
L166, the third bullet under `### Phase 2 may exit only when`
(L162), inside `## F. Phase-gate scorecard` (L122):

> - canonical promotion cannot diverge from SQL metadata;

- `source_hash` recomputed over the whole register file → `26d51b31…`, matches
  the stored value.
- `text_digest` recomputed over the normalized L166 span →
  `09818df2446031daa36f27d021f18ce227574eb8a49dc5f452e1b64594352ed7`, equal to
  the stored `text_digest` and to `EV-PG-2-03-SOURCE.content_sha256`.
- `required_acceptance_text` equals that bullet with the list marker and the
  terminal punctuation stripped, byte for byte.

## Reasoning

**Kind.** The occurrence is one bullet of the register's own §F phase-gate
scorecard. `phase_gate_clause` is the kind that inventories exactly those
bullets: all 35 `PG-*` rows carry `source_path` = the pinned v2 register,
`register_id: null`, and a `source_anchor` of the form `F-<phase>-<ordinal>`.
It is not a `register_row` (those are the §A–§E decision table rows and carry a
`register_id`), not a `disposition_item` (those inventory the third-order
disposition report's numbered findings), and not a `first_release_deferral`
(those are §G).

**Derivation rule.** Goal L239 admits exactly two rules for this kind,
`RELATED_REGISTER_SCOPE` or `ACTIVE_NEGATIVE_CONTROL`, and
`validate_ledger_structural.py:1535-1538` enforces that pair. The choice is
further closed from the other side: `:2520-2523` asserts that the set of
canonical rows using `ACTIVE_NEGATIVE_CONTROL` is exactly `{"PG-1-11"}`. So for
this row `RELATED_REGISTER_SCOPE` is the only representable rule, and the
stored value matches. It is also right on the merits — see below — rather than
right only by elimination. The clause is a safety property that the Phase 2 promotion
transaction must exhibit — a positive obligation on a capability being built,
not a proof that a capability stays out.

**Related register IDs — `["D-03"]`.** `D-03` (register v2 L99) is "Define
canonical memory promotion transaction", acceptance: "Narrative content
hash/commit is registered in SQL; **partial writes cannot create split-brain
state**." The gate bullet is that acceptance restated as an exit condition, with
"cannot diverge from SQL metadata" naming the same divergence the "registered in
SQL" plus "no split-brain" pair rules out. One ID, exact.

**Candidates examined and rejected — and `C-10` is the sharp one.** `C-10`
(register L81, "Establish correction, supersession, and promotion workflow")
ends "canonical promotion is separately approved; **split-brain writes are
prevented**" — a near-verbatim collision with this clause's subject. I rejected
it on three independent grounds:

1. **Phase.** `PG-2-03` is a Phase 2 bullet (`blueprint_phase: "2"`, under
   "### Phase 2 may exit only when"), and the register partitions its own
   sections by phase: §C is Phase 1, §D is Phase 2. `C-10`'s promotion is the
   Phase 1 evidence/claim correction workflow; `D-03`'s is the Phase 2 canonical
   *memory* promotion transaction. Same word, different transactions.
2. **Ownership already assigned.** `REG-C-10.gate_refs == ['PG-1-07']` — `C-10`
   is claimed by the Phase 1 auditability clause, also in this batch, and the
   two clauses read the row for different properties. Adding `C-10` here would
   break that reverse-link map at `validate_ledger_structural.py:2659-2666`
   unless `REG-C-10.gate_refs` were also rewritten.
3. **Disposition.** `REG-C-10` is `Open`/`Open` and therefore `REQUIRED_NOW`;
   including it would flip this clause's aggregation to `REQUIRED_NOW` and, by
   goal L288-290, force `activation_predicate` to `null`, destroying the
   `AP-PG-2-03` predicate pinned at `:2525-2545` and removing `PG-2-03` from
   `PHASE2_CONDITIONAL_GATE_IDS` (`:411-413`).

`D-01` was likewise rejected: its promotion contract is engine-neutral interface
shape, not SQL registration, and it is `Open` — including it would produce the
same disposition flip. The contrast with `PG-2-04`, which *does* include
`D-01` and is `REQUIRED_NOW` without a predicate, shows the boundary is drawn
deliberately.

**Derived disposition — recomputed.** `REG-D-03`: activation `Deferred`, current
`Deferred` → `CONDITIONAL_UNACTIVATED`. Single related row, so aggregation
returns that (goal L250-252). Stored fields match; `:2534` pins it.

**`authority_effect` — `null`, and not a choice.**
`validate_ledger_structural.py:1551` asserts `authority_effect is None` for
every `RELATED_REGISTER_SCOPE` row, and goal L252-254 confines the three
`authority_effect` values to `AUTHORITATIVE_OCCURRENCE`. There is no open
judgment here, unlike a `disposition_item`.

**`activation_predicate` — present, and mechanically constrained.** Goal
L284-286 requires a non-null predicate on every non-register component derived
`CONDITIONAL_UNACTIVATED`, and `validate_ledger_structural.py:2525-2545` pins
the shape for the five Phase 2 conditional gates
(`PHASE2_CONDITIONAL_GATE_IDS`, `:411-413`): `predicate_id == "AP-" + gate_id`,
top-level `op == "ALL"`, every metric's `json_pointer` under
`/phase_gates/pg_2_03/` with no nested segment, and every `metric_id` derived
mechanically from its field name. All of that holds as read.

The part worth reviewing rather than re-asserting is
`FORBIDDEN_PHASE2_FIELD_SUFFIXES = ("_ready", "_improved", "_acceptable")`
(`:2529`, `:2542`): the contract forbids a Phase 2 gate from resolving to a
self-attesting boolean named after its own conclusion. `AP-PG-2-03` declares four
metrics under `/phase_gates/pg_2_03/`: `test_result_id` nonempty,
`promotion_cases_executed > 0`, `sql_metadata_divergence_count == 0`, and
`partial_write_escape_count == 0`. The `> 0` guard is again what prevents a
vacuous pass — two zero-counts prove nothing if nothing was attempted. This row
is also the **explicit exemption** from the "at least one `COMPARE_METRICS`
leaf" requirement: `:2546-2549` reads `... or gate_id == "PG-2-03"`. The
exemption is principled rather than a carve-out of convenience — an impossibility
claim is proved by absolute zeros against a nonzero attempt count, not by
comparing two observed quantities — and the row's expression is consistent with
it, using only `COMPARE` leaves.

Every metric is `source_kind: EVIDENCE_JSON` with `evidence_ref_id: null`. Goal
L320-324 permits exactly that before the evidence exists — "the pointer and
value type must already be exact" — so the predicate evaluates `UNKNOWN` and
`result: UNKNOWN`, `evaluated_at: null`, `evaluation_sha256: null` is the
correct unevaluated state (goal L333-334).

**`gate_refs: []`, reverse link closed.** `REG-D-03.gate_refs ==
['PG-2-03', 'PG-2-04']`; both Phase 2 clauses that read `D-03` are listed, and
`:2659-2666` closes the map. `disposition_refs: []`.

**`primary_spec: null`.** Related-register ownership supplied; `D-03` is
S19-owned.

**Applicable review slot.** This is a non-register canonical row, so
`validate_ledger_preimplementation.py:199-204` appends `SCOPE` to its checks and
`scope_derivation.semantic_review` is the slot this review fills. It is present,
non-`null`, `PENDING`, and carries exactly the 10-key `PENDING` set with no
role-binding keys.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `PG-2-03`'s scope derivation is correct at the input bytes pinned
above.
