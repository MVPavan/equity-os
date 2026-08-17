# Inventory review — PG-2-06 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `PG-2-06` |
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
{"activation_predicate":{"evaluated_at":null,"evaluation_sha256":null,"expression":{"args":[{"comparator":"NE","expected":"","metric_id":"MTR-PG-2-06-TRIGGER-POLICY-ID","op":"COMPARE"},{"comparator":"GT","expected":0,"metric_id":"MTR-PG-2-06-CORPUS-SIZE-THRESHOLD","op":"COMPARE"},{"comparator":"GT","expected":0,"metric_id":"MTR-PG-2-06-CROSS-COMPANY-GRAPH-QUERY-THRESHOLD","op":"COMPARE"},{"comparator":"GT","expected":0,"metric_id":"MTR-PG-2-06-RETRIEVAL-MISS-RATE-THRESHOLD","op":"COMPARE"},{"comparator":"LTE","expected":1,"metric_id":"MTR-PG-2-06-RETRIEVAL-MISS-RATE-THRESHOLD","op":"COMPARE"},{"comparator":"EQ","left_metric_id":"MTR-PG-2-06-CURRENT-ENGINE-DECISION-ID","op":"COMPARE_METRICS","right_metric_id":"MTR-PG-2-06-TRIGGER-POLICY-ENGINE-DECISION-ID"}],"op":"ALL"},"metrics":[{"evidence_ref_id":null,"json_pointer":"/phase_gates/pg_2_06/corpus_size_threshold","metric_id":"MTR-PG-2-06-CORPUS-SIZE-THRESHOLD","register_ids":[],"source_kind":"EVIDENCE_JSON","valid_until":null,"value_type":"NUMBER"},{"evidence_ref_id":null,"json_pointer":"/phase_gates/pg_2_06/cross_company_graph_query_threshold","metric_id":"MTR-PG-2-06-CROSS-COMPANY-GRAPH-QUERY-THRESHOLD","register_ids":[],"source_kind":"EVIDENCE_JSON","valid_until":null,"value_type":"NUMBER"},{"evidence_ref_id":null,"json_pointer":"/phase_gates/pg_2_06/current_engine_decision_id","metric_id":"MTR-PG-2-06-CURRENT-ENGINE-DECISION-ID","register_ids":[],"source_kind":"EVIDENCE_JSON","valid_until":null,"value_type":"STRING"},{"evidence_ref_id":null,"json_pointer":"/phase_gates/pg_2_06/retrieval_miss_rate_threshold","metric_id":"MTR-PG-2-06-RETRIEVAL-MISS-RATE-THRESHOLD","register_ids":[],"source_kind":"EVIDENCE_JSON","valid_until":null,"value_type":"NUMBER"},{"evidence_ref_id":null,"json_pointer":"/phase_gates/pg_2_06/trigger_policy_engine_decision_id","metric_id":"MTR-PG-2-06-TRIGGER-POLICY-ENGINE-DECISION-ID","register_ids":[],"source_kind":"EVIDENCE_JSON","valid_until":null,"value_type":"STRING"},{"evidence_ref_id":null,"json_pointer":"/phase_gates/pg_2_06/trigger_policy_id","metric_id":"MTR-PG-2-06-TRIGGER-POLICY-ID","register_ids":[],"source_kind":"EVIDENCE_JSON","valid_until":null,"value_type":"STRING"}],"predicate_id":"AP-PG-2-06","result":"UNKNOWN"},"disposition_refs":[],"gate_refs":[],"related_register_ids":["D-02","D-05"],"scope_derivation":{"authority_effect":null,"derived_program_disposition":"CONDITIONAL_UNACTIVATED","related_register_ids":["D-02","D-05"],"rule":"RELATED_REGISTER_SCOPE"}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 —
appending review evidence mutates `evidence_refs` and therefore the input
projection):

- `reviewed_input_sha256` (pre-record): `53b36aca0f1fd5e29523d5691ac09cb1d1d5b9b7df3d81a5f0ed4279e74c4409`
- `reviewed_inventory_sha256` (pre-record): `2d6bbf10ec40dbde4f52a52b8858e2086371e4cf5df122b9ad43694ac0d25fa7`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md`
L169, the sixth bullet under `### Phase 2 may exit only when`
(L162), inside `## F. Phase-gate scorecard` (L122):

> - future re-evaluation triggers are recorded regardless of the current engine decision.

- `source_hash` recomputed over the whole register file → `26d51b31…`, matches
  the stored value.
- `text_digest` recomputed over the normalized L169 span →
  `243ad3e9e2c456ad75135c0caa0feef82c9fa152fcbe33888e217a58353ad99a`, equal to
  the stored `text_digest` and to `EV-PG-2-06-SOURCE.content_sha256`.
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

**Related register IDs — `["D-02", "D-05"]`.** The clause has two halves and
each half is one register row:

- "future re-evaluation triggers are recorded" → `D-02` (register v2 L98), whose
  acceptance ends "…result governs current adoption only; **re-evaluation
  triggers are precommitted**".
- "regardless of the current engine decision" → `D-05` (L101), "Decide GBrain
  adoption", whose acceptance ends "**a non-adoption result does not prevent
  later trigger-based reevaluation**".

The pair is not redundant: `D-02` supplies the obligation to record triggers,
`D-05` supplies the independence-from-outcome clause. Dropping either would drop
half the bullet.

**Candidates examined and rejected.**

- `D-04` ("Verify GBrain repository and dependency posture"), which records
  activity and pinned versions — the sort of facts a re-evaluation trigger might
  watch. It records repository *state*, not trigger *policy*, and carries no
  gate anywhere.
- The eight `scale_trigger` rows (`SCALE-SQLITE-01`…`04`,
  `SCALE-WORKFLOW-01`…`04`), which inventory the register's §H "Storage and
  workflow scale-up triggers". These are the ledger's other re-evaluation
  controls, and the resemblance is close enough to check: §H's own preamble says
  "These are operating notes, not Phase 0.5 blockers", and the rows are
  `first_release`-independent `scale_trigger` components with
  `PROGRAM_WIDE_ACTIVE_CONTROL` derivation and no register IDs at all. They are
  a different source section and a different kind, not registers this clause
  could relate to.
- `D-03`, the promotion transaction, which is engine-implementation detail
  rather than trigger policy; claimed by `PG-2-03` and `PG-2-04`.

**Derived disposition — recomputed.** `REG-D-02`: `Deferred`/`Deferred` →
`CONDITIONAL_UNACTIVATED`. `REG-D-05`: same. No related row is `REQUIRED_NOW` or
activated, so aggregation reaches goal L250-252's dormant branch. Stored fields
are `CONDITIONAL_UNACTIVATED`; `:2534` pins it.

I note the reading tension and resolve it explicitly, because it is the
substantive question on this row: the clause says triggers are recorded
"**regardless of** the current engine decision", which sounds like an obligation
that should be live now, independent of Phase 2 dormancy — i.e. like `PG-1-11`'s
negative control. It is not the same shape. `PG-1-11` asserts something about
the *present* release (four capabilities are outside it), which is why
`ACTIVE_NEGATIVE_CONTROL` fixes it to `REQUIRED_NOW`. `PG-2-06` asserts
something about the *Phase 2 exit*: at the point Phase 2 exits, triggers must be
on record whichever way the engine decision went. "Regardless" quantifies over
the outcome of `D-05`, not over the activation state of Phase 2. And the rule is
not available anyway — `:2520-2523` pins `ACTIVE_NEGATIVE_CONTROL` to exactly
`{"PG-1-11"}`, and this clause activates a recording obligation rather than
proving a capability stays dormant, so goal L263-264 would not fit it.

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
`/phase_gates/pg_2_06/` with no nested segment, and every `metric_id` derived
mechanically from its field name. All of that holds as read.

The part worth reviewing rather than re-asserting is
`FORBIDDEN_PHASE2_FIELD_SUFFIXES = ("_ready", "_improved", "_acceptable")`
(`:2529`, `:2542`): the contract forbids a Phase 2 gate from resolving to a
self-attesting boolean named after its own conclusion. `AP-PG-2-06` declares six
metrics under `/phase_gates/pg_2_06/`. A nonempty `trigger_policy_id`; three
threshold metrics that must each be `> 0` — `corpus_size_threshold`,
`cross_company_graph_query_threshold`, `retrieval_miss_rate_threshold` — with
the miss-rate additionally bounded `<= 1` by a second `COMPARE` leaf on the same
metric, which is a genuine type-sanity guard on a rate rather than filler; and a
`COMPARE_METRICS` equality requiring `current_engine_decision_id ==
trigger_policy_engine_decision_id`. That last leaf is the mechanization of
"regardless of the current engine decision": the recorded policy must be bound
to the engine decision actually in force, so a trigger policy written against a
superseded decision cannot satisfy the gate. It also satisfies the
`COMPARE_METRICS` requirement at `:2546-2549`. Note the decomposition avoids a
`..._ready` flag (`:2529`, `:2542`) by naming the three thresholds
individually — the triggers `D-02` calls "precommitted" are enumerated as
values, not asserted as a boolean.

Every metric is `source_kind: EVIDENCE_JSON` with `evidence_ref_id: null`. Goal
L320-324 permits exactly that before the evidence exists — "the pointer and
value type must already be exact" — so the predicate evaluates `UNKNOWN` and
`result: UNKNOWN`, `evaluated_at: null`, `evaluation_sha256: null` is the
correct unevaluated state (goal L333-334).

**`gate_refs: []`, reverse link closed.** `REG-D-02.gate_refs ==
['PG-1-11','PG-2-01','PG-2-02','PG-2-06']` and `REG-D-05.gate_refs ==
['PG-1-11','PG-2-01','PG-2-05','PG-2-06']`; both contain this row.
`disposition_refs: []` — the §H scale triggers carry disposition ordinals
(`M-5`, `R-5` at `:2651-2653`), this Phase 2 gate clause does not.

**`primary_spec: null`.** Related-register ownership supplied; both `D-02` and
`D-05` are S20-owned.

**Applicable review slot.** This is a non-register canonical row, so
`validate_ledger_preimplementation.py:199-204` appends `SCOPE` to its checks and
`scope_derivation.semantic_review` is the slot this review fills. It is present,
non-`null`, `PENDING`, and carries exactly the 10-key `PENDING` set with no
role-binding keys.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `PG-2-06`'s scope derivation is correct at the input bytes pinned
above.
