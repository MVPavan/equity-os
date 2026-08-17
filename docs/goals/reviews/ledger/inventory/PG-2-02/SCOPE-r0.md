# Inventory review — PG-2-02 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `PG-2-02` |
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
{"activation_predicate":{"evaluated_at":null,"evaluation_sha256":null,"expression":{"args":[{"comparator":"NE","expected":"","metric_id":"MTR-PG-2-02-TEST-RESULT-ID","op":"COMPARE"},{"comparator":"GT","expected":0,"metric_id":"MTR-PG-2-02-STALE-FIXTURE-COUNT","op":"COMPARE"},{"comparator":"GT","expected":0,"metric_id":"MTR-PG-2-02-CONTRADICTION-FIXTURE-COUNT","op":"COMPARE"},{"comparator":"EQ","left_metric_id":"MTR-PG-2-02-STALE-SURFACED-COUNT","op":"COMPARE_METRICS","right_metric_id":"MTR-PG-2-02-STALE-FIXTURE-COUNT"},{"comparator":"EQ","left_metric_id":"MTR-PG-2-02-CONTRADICTION-SURFACED-COUNT","op":"COMPARE_METRICS","right_metric_id":"MTR-PG-2-02-CONTRADICTION-FIXTURE-COUNT"}],"op":"ALL"},"metrics":[{"evidence_ref_id":null,"json_pointer":"/phase_gates/pg_2_02/contradiction_fixture_count","metric_id":"MTR-PG-2-02-CONTRADICTION-FIXTURE-COUNT","register_ids":[],"source_kind":"EVIDENCE_JSON","valid_until":null,"value_type":"INTEGER"},{"evidence_ref_id":null,"json_pointer":"/phase_gates/pg_2_02/contradiction_surfaced_count","metric_id":"MTR-PG-2-02-CONTRADICTION-SURFACED-COUNT","register_ids":[],"source_kind":"EVIDENCE_JSON","valid_until":null,"value_type":"INTEGER"},{"evidence_ref_id":null,"json_pointer":"/phase_gates/pg_2_02/stale_fixture_count","metric_id":"MTR-PG-2-02-STALE-FIXTURE-COUNT","register_ids":[],"source_kind":"EVIDENCE_JSON","valid_until":null,"value_type":"INTEGER"},{"evidence_ref_id":null,"json_pointer":"/phase_gates/pg_2_02/stale_surfaced_count","metric_id":"MTR-PG-2-02-STALE-SURFACED-COUNT","register_ids":[],"source_kind":"EVIDENCE_JSON","valid_until":null,"value_type":"INTEGER"},{"evidence_ref_id":null,"json_pointer":"/phase_gates/pg_2_02/test_result_id","metric_id":"MTR-PG-2-02-TEST-RESULT-ID","register_ids":[],"source_kind":"EVIDENCE_JSON","valid_until":null,"value_type":"STRING"}],"predicate_id":"AP-PG-2-02","result":"UNKNOWN"},"disposition_refs":[],"gate_refs":[],"related_register_ids":["D-02"],"scope_derivation":{"authority_effect":null,"derived_program_disposition":"CONDITIONAL_UNACTIVATED","related_register_ids":["D-02"],"rule":"RELATED_REGISTER_SCOPE"}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 —
appending review evidence mutates `evidence_refs` and therefore the input
projection):

- `reviewed_input_sha256` (pre-record): `d1c935a8b905e1fb28f0f66ba10795760d671fd7f4b4e8972abea6c065ac879d`
- `reviewed_inventory_sha256` (pre-record): `63a9ebfdc9cb008772822ea9bb7cc0f493c43d23a76896f6123605bcd7069017`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md`
L165, the second bullet under `### Phase 2 may exit only when`
(L162), inside `## F. Phase-gate scorecard` (L122):

> - stale and contradicted conclusions are surfaced;

- `source_hash` recomputed over the whole register file → `26d51b31…`, matches
  the stored value.
- `text_digest` recomputed over the normalized L165 span →
  `28e6abf5a629ee2d726d3d1707e590e967f5d1f1a763531f8598f30e45ed780e`, equal to
  the stored `text_digest` and to `EV-PG-2-02-SOURCE.content_sha256`.
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
right only by elimination.

**Related register IDs — `["D-02"]`, a single ID, and the narrowness is
correct.** `D-02` (register v2 L98) is the only register row that names this
capability: its comparison dimensions include "retrieval misses,
**contradiction/staleness detection**, analyst time, unsupported claims…". The
gate bullet — "stale and contradicted conclusions are surfaced" — is that one
dimension promoted to an exit condition. One ID, exact, unpadded.

**Candidates examined and rejected.** This clause attracts more plausible
neighbours than its one-ID derivation suggests, so each was checked:

- `D-05` ("Decide GBrain adoption"), which sits on three of the other four
  Phase 2 clauses. Detection of stale and contradicted conclusions is a property
  the benchmark measures across *all* arms, not a property of the adoption
  decision; including `D-05` would say this gate depends on which engine was
  chosen, when the clause says the capability must exist regardless.
- `C-03` ("Implement append-only observation and revision model": "Restatements
  and conflicting observations are preserved"), which is the Phase 1 storage
  substrate that makes contradiction visible at the *observation* level. This
  clause is about *conclusions*, i.e. narrative memory, and `C-03` is `Open` —
  including it would flip the aggregation to `REQUIRED_NOW` and destroy the
  `AP-PG-2-02` predicate the contract pins at
  `validate_ledger_structural.py:2525-2545`. `C-03` is claimed by `PG-1-03`.
- `C-04` ("…contradiction and materiality reasoning are visible"), which is
  claim-level contradiction inside Phase 1 validation, claimed by `PG-1-01` and
  `PG-1-02`. Again a different object — claims, not conclusions — and again an
  `Open` row whose inclusion would change the disposition.
- `B-11` (fact identity, revision families, supersession semantics), the
  fact-level analogue, Phase 0.5, claimed by `PG-05-06`.

**Derived disposition — recomputed.** `REG-D-02`: activation `Deferred`, current
`Deferred` → `CONDITIONAL_UNACTIVATED` (goal L215-216). With a single related
row, aggregation returns that value directly (goal L250-252). Stored fields
match, and `:2534` pins it.

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
`/phase_gates/pg_2_02/` with no nested segment, and every `metric_id` derived
mechanically from its field name. All of that holds as read.

The part worth reviewing rather than re-asserting is
`FORBIDDEN_PHASE2_FIELD_SUFFIXES = ("_ready", "_improved", "_acceptable")`
(`:2529`, `:2542`): the contract forbids a Phase 2 gate from resolving to a
self-attesting boolean named after its own conclusion. "Surfaced" could have been
mechanized as a boolean claim that detection works. `AP-PG-2-02` instead
declares five metrics under `/phase_gates/pg_2_02/` and requires a **recall
identity**: `test_result_id` nonempty, `stale_fixture_count > 0`,
`contradiction_fixture_count > 0`, and then two `COMPARE_METRICS` leaves
requiring `stale_surfaced_count == stale_fixture_count` and
`contradiction_surfaced_count == contradiction_fixture_count`. The two
`> 0` guards are what stop a vacuous pass on an empty fixture set — a real
falsifiability property, not boilerplate — and the two equalities satisfy the
`COMPARE_METRICS` requirement at `:2546-2549`. This is a faithful mechanization
of "are surfaced": every planted stale and contradicted conclusion must be
found, not merely some.

Every metric is `source_kind: EVIDENCE_JSON` with `evidence_ref_id: null`. Goal
L320-324 permits exactly that before the evidence exists — "the pointer and
value type must already be exact" — so the predicate evaluates `UNKNOWN` and
`result: UNKNOWN`, `evaluated_at: null`, `evaluation_sha256: null` is the
correct unevaluated state (goal L333-334).

**`gate_refs: []`, reverse link closed.** `REG-D-02.gate_refs ==
['PG-1-11','PG-2-01','PG-2-02','PG-2-06']` contains this row, and
`validate_ledger_structural.py:2659-2666` asserts the map is exactly the image
of the clauses' related-register sets. `disposition_refs: []`.

**`primary_spec: null`.** Related-register ownership supplied; `D-02` is
S20-owned.

**Applicable review slot.** This is a non-register canonical row, so
`validate_ledger_preimplementation.py:199-204` appends `SCOPE` to its checks and
`scope_derivation.semantic_review` is the slot this review fills. It is present,
non-`null`, `PENDING`, and carries exactly the 10-key `PENDING` set with no
role-binding keys.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `PG-2-02`'s scope derivation is correct at the input bytes pinned
above.
