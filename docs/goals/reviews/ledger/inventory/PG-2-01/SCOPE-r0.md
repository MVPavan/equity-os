# Inventory review — PG-2-01 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `PG-2-01` |
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
{"activation_predicate":{"evaluated_at":null,"evaluation_sha256":null,"expression":{"args":[{"comparator":"NE","expected":"","metric_id":"MTR-PG-2-01-BENCHMARK-RESULT-ID","op":"COMPARE"},{"comparator":"NE","expected":"","metric_id":"MTR-PG-2-01-PRIMARY-METRIC-DEFINITION-ID","op":"COMPARE"},{"comparator":"GT","expected":0,"metric_id":"MTR-PG-2-01-PRECOMMITTED-MINIMUM-IMPROVEMENT","op":"COMPARE"},{"comparator":"GTE","left_metric_id":"MTR-PG-2-01-OBSERVED-PRIMARY-IMPROVEMENT","op":"COMPARE_METRICS","right_metric_id":"MTR-PG-2-01-PRECOMMITTED-MINIMUM-IMPROVEMENT"}],"op":"ALL"},"metrics":[{"evidence_ref_id":null,"json_pointer":"/phase_gates/pg_2_01/benchmark_result_id","metric_id":"MTR-PG-2-01-BENCHMARK-RESULT-ID","register_ids":[],"source_kind":"EVIDENCE_JSON","valid_until":null,"value_type":"STRING"},{"evidence_ref_id":null,"json_pointer":"/phase_gates/pg_2_01/observed_primary_improvement","metric_id":"MTR-PG-2-01-OBSERVED-PRIMARY-IMPROVEMENT","register_ids":[],"source_kind":"EVIDENCE_JSON","valid_until":null,"value_type":"NUMBER"},{"evidence_ref_id":null,"json_pointer":"/phase_gates/pg_2_01/precommitted_minimum_improvement","metric_id":"MTR-PG-2-01-PRECOMMITTED-MINIMUM-IMPROVEMENT","register_ids":[],"source_kind":"EVIDENCE_JSON","valid_until":null,"value_type":"NUMBER"},{"evidence_ref_id":null,"json_pointer":"/phase_gates/pg_2_01/primary_metric_definition_id","metric_id":"MTR-PG-2-01-PRIMARY-METRIC-DEFINITION-ID","register_ids":[],"source_kind":"EVIDENCE_JSON","valid_until":null,"value_type":"STRING"}],"predicate_id":"AP-PG-2-01","result":"UNKNOWN"},"disposition_refs":[],"gate_refs":[],"related_register_ids":["D-02","D-05"],"scope_derivation":{"authority_effect":null,"derived_program_disposition":"CONDITIONAL_UNACTIVATED","related_register_ids":["D-02","D-05"],"rule":"RELATED_REGISTER_SCOPE"}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 —
appending review evidence mutates `evidence_refs` and therefore the input
projection):

- `reviewed_input_sha256` (pre-record): `523ee731b034adbcd11f5dc75133d054afdba5e4e982761fe1618cc8cd480c93`
- `reviewed_inventory_sha256` (pre-record): `39ca9d8e3793d0e6257286a5af2b2debd40819b1ced9e25844a2cd76dd18fb4b`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md`
L164, the first bullet under `### Phase 2 may exit only when`
(L162), inside `## F. Phase-gate scorecard` (L122):

> - the selected memory approach improves measurable current-scale workflow outcomes;

- `source_hash` recomputed over the whole register file → `26d51b31…`, matches
  the stored value.
- `text_digest` recomputed over the normalized L164 span →
  `49518e1c2f8439fbc01285087b7e5efbb6bf9e25cdedf0d7dc631dcb000086f4`, equal to
  the stored `text_digest` and to `EV-PG-2-01-SOURCE.content_sha256`.
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
right only by elimination. `PG-2-01` states a positive obligation over Phase 2 memory scope,
not a proof that named capabilities stay dormant, so `ACTIVE_NEGATIVE_CONTROL`
would be wrong on the merits as well as unavailable.

**Related register IDs — `["D-02", "D-05"]`, and the exclusion of `D-01` is the
load-bearing part.** The clause has two elements: "the **selected** memory
approach" and "**improves measurable** current-scale workflow outcomes".

- `D-05` (register v2 L101), "Decide GBrain adoption" — "Adopt only if
  current-scale benchmark benefit exceeds operational and upgrade burden" — is
  where the approach is *selected*.
- `D-02` (L98), "Run current-scale three-arm memory benchmark", is the
  measurement: it compares no-persistent-memory, Git/Markdown/SQL retrieval, and
  GBrain on "longitudinal tasks, retrieval misses, contradiction/staleness
  detection, analyst time, unsupported claims, latency, cost, and operations",
  and states that its "result governs current adoption only". "Measurable
  current-scale workflow outcomes" is `D-02`'s comparison set, phrase for
  phrase.

`D-01` ("Implement `MemoryStore` interface before choosing engine") is
deliberately **not** in the set, and the choice is observationally decisive
rather than stylistic: `REG-D-01` is `Open`/`Open` and therefore `REQUIRED_NOW`,
so including it would flip this clause's aggregation to `REQUIRED_NOW` (goal
L248-250) and, by goal L288-290, force `activation_predicate` to `null` —
destroying the `AP-PG-2-01` predicate the contract pins for this gate at
`validate_ledger_structural.py:2525-2545`. The semantic reason and the
mechanical reason agree: `D-01` is an engine-neutral interface obligation that
must be met *before* an engine is chosen; it neither selects an approach nor
measures an outcome. The contrast with `PG-2-04` in this same batch, which does
include `D-01` and is consequently `REQUIRED_NOW` without a predicate, shows the
distinction is being drawn deliberately across the Phase 2 clauses.

**Other candidates examined and rejected.** `D-04` ("Verify GBrain repository
and dependency posture") records licence and version facts, measuring no
workflow outcome, and carries no gate. `D-03` (canonical promotion transaction)
is a correctness property of promotion, claimed by `PG-2-03` and `PG-2-04`.
`B-04`/`C-12`, which own analyst-time measurement, are Phase 0.5/1 rows already
claimed by `PG-05-03`, `PG-05-04`, and `PG-1-08`; importing them would also flip
the disposition. Goal L233-235's no-padding rule applies.

**Derived disposition — recomputed.** `REG-D-02`: activation `Deferred`, current
`Deferred` → `CONDITIONAL_UNACTIVATED` (goal L215-216). `REG-D-05`: same.
Aggregation therefore falls past goal L248-250's first two branches — no related
row is `REQUIRED_NOW`, none is activated — to "`CONDITIONAL_UNACTIVATED` if any
remains dormant". Stored `derived_program_disposition` and `program_disposition`
are both `CONDITIONAL_UNACTIVATED`, and `validate_ledger_structural.py:2534`
pins it for this gate independently.

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
`/phase_gates/pg_2_01/` with no nested segment, and every `metric_id` derived
mechanically from its field name. All of that holds as read.

The part worth reviewing rather than re-asserting is
`FORBIDDEN_PHASE2_FIELD_SUFFIXES = ("_ready", "_improved", "_acceptable")`
(`:2529`, `:2542`): the contract forbids a Phase 2 gate from resolving to a
self-attesting boolean named after its own conclusion. "Improves" is exactly the
word that would have invited a `..._improved` flag; instead `AP-PG-2-01`
decomposes it into four metrics under `/phase_gates/pg_2_01/` —
`benchmark_result_id` and `primary_metric_definition_id` must each be a nonempty
string, `precommitted_minimum_improvement` must be `> 0`, and
`observed_primary_improvement` must be `>= precommitted_minimum_improvement` via
a `COMPARE_METRICS` leaf. That last leaf is what makes the gate falsifiable: the
bar is fixed in the same evidence document as the observation, and the
`COMPARE_METRICS` requirement at `:2546-2549` is satisfied. The predicate is a
faithful mechanization of "improves … by a pre-committed amount", which is also
what `D-02`\'s "result governs current adoption only" demands.

Every metric is `source_kind: EVIDENCE_JSON` with `evidence_ref_id: null`. Goal
L320-324 permits exactly that before the evidence exists — "the pointer and
value type must already be exact" — so the predicate evaluates `UNKNOWN` and
`result: UNKNOWN`, `evaluated_at: null`, `evaluation_sha256: null` is the
correct unevaluated state (goal L333-334).

**`gate_refs: []`, reverse link closed.** `REG-D-02.gate_refs ==
['PG-1-11','PG-2-01','PG-2-02','PG-2-06']` and `REG-D-05.gate_refs ==
['PG-1-11','PG-2-01','PG-2-05','PG-2-06']`; both contain this row, and
`validate_ledger_structural.py:2659-2666` asserts each register's `gate_refs` is
exactly the image of the clauses' `related_register_ids`.
`disposition_refs: []`.

**`primary_spec: null`.** Related-register ownership supplied (goal L184); both
`D-02` and `D-05` are S20-owned.

**Applicable review slot.** This is a non-register canonical row, so
`validate_ledger_preimplementation.py:199-204` appends `SCOPE` to its checks and
`scope_derivation.semantic_review` is the slot this review fills. It is present,
non-`null`, `PENDING`, and carries exactly the 10-key `PENDING` set with no
role-binding keys.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `PG-2-01`'s scope derivation is correct at the input bytes pinned
above.
