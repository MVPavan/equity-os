# Inventory review — PG-2-05 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `PG-2-05` |
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
{"activation_predicate":{"evaluated_at":null,"evaluation_sha256":null,"expression":{"args":[{"comparator":"NE","expected":"","metric_id":"MTR-PG-2-05-BURDEN-MEASUREMENT-ID","op":"COMPARE"},{"comparator":"LTE","left_metric_id":"MTR-PG-2-05-OPERATOR-MINUTES-PER-MONTH","op":"COMPARE_METRICS","right_metric_id":"MTR-PG-2-05-PRECOMMITTED-MAX-OPERATOR-MINUTES-PER-MONTH"},{"comparator":"LTE","left_metric_id":"MTR-PG-2-05-INCIDENTS-PER-100-RUNS","op":"COMPARE_METRICS","right_metric_id":"MTR-PG-2-05-PRECOMMITTED-MAX-INCIDENTS-PER-100-RUNS"},{"comparator":"LTE","left_metric_id":"MTR-PG-2-05-P95-RECOVERY-MINUTES","op":"COMPARE_METRICS","right_metric_id":"MTR-PG-2-05-PRECOMMITTED-MAX-P95-RECOVERY-MINUTES"}],"op":"ALL"},"metrics":[{"evidence_ref_id":null,"json_pointer":"/phase_gates/pg_2_05/burden_measurement_id","metric_id":"MTR-PG-2-05-BURDEN-MEASUREMENT-ID","register_ids":[],"source_kind":"EVIDENCE_JSON","valid_until":null,"value_type":"STRING"},{"evidence_ref_id":null,"json_pointer":"/phase_gates/pg_2_05/incidents_per_100_runs","metric_id":"MTR-PG-2-05-INCIDENTS-PER-100-RUNS","register_ids":[],"source_kind":"EVIDENCE_JSON","valid_until":null,"value_type":"NUMBER"},{"evidence_ref_id":null,"json_pointer":"/phase_gates/pg_2_05/operator_minutes_per_month","metric_id":"MTR-PG-2-05-OPERATOR-MINUTES-PER-MONTH","register_ids":[],"source_kind":"EVIDENCE_JSON","valid_until":null,"value_type":"NUMBER"},{"evidence_ref_id":null,"json_pointer":"/phase_gates/pg_2_05/p95_recovery_minutes","metric_id":"MTR-PG-2-05-P95-RECOVERY-MINUTES","register_ids":[],"source_kind":"EVIDENCE_JSON","valid_until":null,"value_type":"NUMBER"},{"evidence_ref_id":null,"json_pointer":"/phase_gates/pg_2_05/precommitted_max_incidents_per_100_runs","metric_id":"MTR-PG-2-05-PRECOMMITTED-MAX-INCIDENTS-PER-100-RUNS","register_ids":[],"source_kind":"EVIDENCE_JSON","valid_until":null,"value_type":"NUMBER"},{"evidence_ref_id":null,"json_pointer":"/phase_gates/pg_2_05/precommitted_max_operator_minutes_per_month","metric_id":"MTR-PG-2-05-PRECOMMITTED-MAX-OPERATOR-MINUTES-PER-MONTH","register_ids":[],"source_kind":"EVIDENCE_JSON","valid_until":null,"value_type":"NUMBER"},{"evidence_ref_id":null,"json_pointer":"/phase_gates/pg_2_05/precommitted_max_p95_recovery_minutes","metric_id":"MTR-PG-2-05-PRECOMMITTED-MAX-P95-RECOVERY-MINUTES","register_ids":[],"source_kind":"EVIDENCE_JSON","valid_until":null,"value_type":"NUMBER"}],"predicate_id":"AP-PG-2-05","result":"UNKNOWN"},"disposition_refs":[],"gate_refs":[],"related_register_ids":["D-05"],"scope_derivation":{"authority_effect":null,"derived_program_disposition":"CONDITIONAL_UNACTIVATED","related_register_ids":["D-05"],"rule":"RELATED_REGISTER_SCOPE"}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 —
appending review evidence mutates `evidence_refs` and therefore the input
projection):

- `reviewed_input_sha256` (pre-record): `eee65156ecda03a7811170104512d4b81fff8484c710df23101b9c69413785dc`
- `reviewed_inventory_sha256` (pre-record): `720d54c405573c563123fc586973ad8c908eb8b1b2912c9bf980e9d8d061d626`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md`
L168, the fifth bullet under `### Phase 2 may exit only when`
(L162), inside `## F. Phase-gate scorecard` (L122):

> - operational burden is acceptable;

- `source_hash` recomputed over the whole register file → `26d51b31…`, matches
  the stored value.
- `text_digest` recomputed over the normalized L168 span →
  `29dbd4151b7e3b554d28eaab54625e2ecfdb0b6b774bf730a23aef5950444764`, equal to
  the stored `text_digest` and to `EV-PG-2-05-SOURCE.content_sha256`.
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

**Related register IDs — `["D-05"]`.** `D-05` (register v2 L101), "Decide GBrain
adoption", acceptance: "Adopt only if current-scale benchmark benefit exceeds
**operational and upgrade burden**; a non-adoption result does not prevent later
trigger-based reevaluation." The gate bullet lifts the burden half of that
condition into an exit criterion. `D-05` is the only register row that uses the
word burden. One ID, exact.

**Candidates examined and rejected.**

- `D-02`, the benchmark, whose comparison dimensions end with "latency, cost,
  and **operations**". This is the closest rejected candidate: operations are
  measured there. But `D-02` measures operations as one dimension of a
  three-arm comparison, while `D-05` is where operational burden is weighed
  against benefit and judged acceptable — which is what this clause asserts.
  Including `D-02` would not change the derived disposition (it is also
  `Deferred`), so the exclusion rests on subject matter alone, and goal
  L233-235 forbids padding on that basis. It is also corroborated from the
  ledger: `REG-D-05.gate_refs` includes `PG-2-05` and `REG-D-02.gate_refs` does
  not.
- `D-04` ("Repository, license, maintainers, activity, tests, security, export
  path, and pinned version recorded"), which speaks to *upgrade* burden — the
  other half of `D-05`'s phrase. The §F bullet says "operational burden", not
  upgrade burden, and `D-04` carries no gate anywhere.
- `A-12` (operating calendar, standing budget, capacity), a Phase 0A row already
  claimed by `PG-0A-07`, and `Open` — including it would flip the aggregation
  to `REQUIRED_NOW` and destroy the `AP-PG-2-05` predicate pinned at
  `validate_ledger_structural.py:2525-2545`.

**Derived disposition — recomputed.** `REG-D-05`: activation `Deferred`, current
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
`/phase_gates/pg_2_05/` with no nested segment, and every `metric_id` derived
mechanically from its field name. All of that holds as read.

The part worth reviewing rather than re-asserting is
`FORBIDDEN_PHASE2_FIELD_SUFFIXES = ("_ready", "_improved", "_acceptable")`
(`:2529`, `:2542`): the contract forbids a Phase 2 gate from resolving to a
self-attesting boolean named after its own conclusion. This is the row the
forbidden-suffix rule was written for: `_acceptable` is one of the three banned
endings, and this clause's own text is "operational burden **is acceptable**".
A `/phase_gates/pg_2_05/operational_burden_acceptable` boolean would have been
the natural lazy mechanization and is precisely what `:2529` and `:2542`
prohibit. `AP-PG-2-05` instead declares seven metrics: a nonempty
`burden_measurement_id`, and three observed-versus-precommitted pairs compared
by `COMPARE_METRICS` with `LTE` — operator minutes per month, incidents per 100
runs, and P95 recovery minutes, each against its own
`precommitted_max_*` counterpart. Acceptability is thereby reduced to three
pre-committed ceilings fixed before the measurement, which is what makes a
subjective-sounding gate falsifiable. The `COMPARE_METRICS` requirement at
`:2546-2549` is satisfied three times over.

Every metric is `source_kind: EVIDENCE_JSON` with `evidence_ref_id: null`. Goal
L320-324 permits exactly that before the evidence exists — "the pointer and
value type must already be exact" — so the predicate evaluates `UNKNOWN` and
`result: UNKNOWN`, `evaluated_at: null`, `evaluation_sha256: null` is the
correct unevaluated state (goal L333-334).

**`gate_refs: []`, reverse link closed.** `REG-D-05.gate_refs ==
['PG-1-11','PG-2-01','PG-2-05','PG-2-06']` contains this row; `:2659-2666`
closes the map. `disposition_refs: []`.

**`primary_spec: null`.** Related-register ownership supplied; `D-05` is
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
only that `PG-2-05`'s scope derivation is correct at the input bytes pinned
above.
