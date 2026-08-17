# Inventory review — PG-1-09 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `PG-1-09` |
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
{"activation_predicate":null,"disposition_refs":[],"gate_refs":[],"related_register_ids":["C-01","C-18"],"scope_derivation":{"authority_effect":null,"derived_program_disposition":"REQUIRED_NOW","related_register_ids":["C-01","C-18"],"rule":"RELATED_REGISTER_SCOPE"}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 —
appending review evidence mutates `evidence_refs` and therefore the input
projection):

- `reviewed_input_sha256` (pre-record): `33a43a14079d9af52ae63a68080e6cbedf638941191dafd3708b2619be2507c8`
- `reviewed_inventory_sha256` (pre-record): `bf9c8ec3f524cbc957383b7339d20114b05171ebde143f6d0c972284dee43b59`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md`
L158, the ninth bullet under `### Phase 1 may exit only when`
(L148), inside `## F. Phase-gate scorecard` (L122):

> - peak results-season capacity is accepted for the selected universe;

- `source_hash` recomputed over the whole register file → `26d51b31…`, matches
  the stored value.
- `text_digest` recomputed over the normalized L158 span →
  `c4248b18af2a75ebef45d3ea65a2ed079caa78ab89eed64d90004a4c7e649064`, equal to
  the stored `text_digest` and to `EV-PG-1-09-SOURCE.content_sha256`.
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
right only by elimination. The clause requires an acceptance to have been obtained — a
positive obligation.

**Related register IDs — `["C-01", "C-18"]`.** The bullet has two nouns and each
maps to exactly one register row:

- "the selected universe" → `C-01` (register v2 L72), "Expand to two or three
  core non-financial companies", whose acceptance ends "…and **feasible peak-
  season review capacity**". `C-01` is where the universe is selected, and its
  acceptance already conditions that selection on peak-season feasibility.
- "peak results-season capacity is accepted" → `C-18` (L89), "Validate
  results-season throughput": "Peak-week reviews per analyst, claim/document
  volume, backlog age, and completion capacity for the Phase 1 universe are
  measured and **accepted or mitigated**." The gate bullet is `C-18`'s
  acceptance branch.

The pair is the clause, not padding: neither row alone carries both the universe
and the acceptance.

**Candidates examined and rejected.**

- `A-12`, "Define operating calendar, standing budget, and capacity" (L42),
  which literally contains the word capacity and carries both `BUDGET_APPROVAL`
  and `CAPACITY_COMMITMENT`. It defines *standing* operating capacity at Phase
  0A and is claimed by `PG-0A-07` ("operating capacity and standing budget are
  documented"). `PG-1-09` is about peak results-season throughput for the Phase
  1 universe — `C-18`'s subject, and `C-18` declares `A-12` as its own
  dependency. Adding `A-12` would import a dependency transitively, which goal
  L233-235 forbids.
- `A-13`, the success-metric contract, which defines "coverage capacity" as a
  metric. Definition, not acceptance; already claimed by `PG-0A-05` and
  `PG-1-10`.
- `C-05` (claim-level review UI/workflow), which drives review throughput in
  practice. It is a capability row, not a capacity acceptance, and carries no
  gate at all.

**Derived disposition — recomputed.** `REG-C-01`: `Open`/`Open` →
`REQUIRED_NOW`. `REG-C-18`: `Open`/`Open` → `REQUIRED_NOW`. Aggregate
`REQUIRED_NOW` (goal L248-250). Matches both stored fields.

**`authority_effect` — `null`, and not a choice.**
`validate_ledger_structural.py:1551` asserts `authority_effect is None` for
every `RELATED_REGISTER_SCOPE` row, and goal L252-254 confines the three
`authority_effect` values to `AUTHORITATIVE_OCCURRENCE`. There is no open
judgment here, unlike a `disposition_item`.

**`activation_predicate: null`.** Required by goal L288-290. Correct.

**`gate_refs: []`, reverse link closed.** `REG-C-01.gate_refs == ['PG-1-09']`
and `REG-C-18.gate_refs == ['PG-1-09']` — this clause is the sole gate for both
rows, and `validate_ledger_structural.py:2659-2666` closes the map.
`disposition_refs: []`.

**`primary_spec: null`.** Related-register ownership supplied; both `C-01` and
`C-18` are S18-owned.

**Applicable review slot.** This is a non-register canonical row, so
`validate_ledger_preimplementation.py:199-204` appends `SCOPE` to its checks and
`scope_derivation.semantic_review` is the slot this review fills. It is present,
non-`null`, `PENDING`, and carries exactly the 10-key `PENDING` set with no
role-binding keys.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `PG-1-09`'s scope derivation is correct at the input bytes pinned
above.
