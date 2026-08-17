# Inventory review — PG-1-07 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `PG-1-07` |
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
{"activation_predicate":null,"disposition_refs":[],"gate_refs":[],"related_register_ids":["C-10"],"scope_derivation":{"authority_effect":null,"derived_program_disposition":"REQUIRED_NOW","related_register_ids":["C-10"],"rule":"RELATED_REGISTER_SCOPE"}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 —
appending review evidence mutates `evidence_refs` and therefore the input
projection):

- `reviewed_input_sha256` (pre-record): `8824d3dd61a8ff7e0ca58bf82c041b72376d6fb4940a8335ed66d16663210637`
- `reviewed_inventory_sha256` (pre-record): `2370580b74f06143f94249e09e0fd69cd5f11c9c7612968b81b85bf2306daf23`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md`
L156, the seventh bullet under `### Phase 1 may exit only when`
(L148), inside `## F. Phase-gate scorecard` (L122):

> - corrections, invalidation, supersession, and promotion are auditable;

- `source_hash` recomputed over the whole register file → `26d51b31…`, matches
  the stored value.
- `text_digest` recomputed over the normalized L156 span →
  `5594b2db9e4a19d1c50e6fe366cfded442d8f7ed0509cbb04b9d19b4079cc824`, equal to
  the stored `text_digest` and to `EV-PG-1-07-SOURCE.content_sha256`.
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
right only by elimination. `PG-1-07` states a positive obligation — four operations must
exist and be auditable — which is the opposite of what `ACTIVE_NEGATIVE_CONTROL`
is for ("it proves that named capabilities stay dormant or rejected", goal
L263-264).

**Related register IDs — `["C-10"]`.** `C-10` (register v2 L81) is "Establish
correction, supersession, and promotion workflow", whose acceptance reads:
"Corrections create new versions; invalidated items remain auditable; canonical
promotion is separately approved; split-brain writes are prevented." The gate
bullet names four operations — corrections, invalidation, supersession,
promotion — and asserts one property over them. `C-10` is the only register
entry that names all four together, and it is the only one that carries the
auditability word itself ("invalidated items remain auditable"). One ID, exact,
unpadded.

**Candidates examined and rejected.** Goal L233-235 forbids padding
`related_register_ids` or inferring it from spec applicability, so each near
neighbour was checked against the clause's actual subject rather than its
vocabulary:

- `C-03`, "Implement append-only observation and revision model" (L74):
  "Restatements and conflicting observations are preserved; no silent
  overwrite." That is storage semantics beneath the correction workflow, not the
  workflow itself, and `C-03` is already claimed elsewhere — its stored
  `gate_refs` is `['PG-1-03']`.
- `B-14`, "Demonstrate human-feedback rework path" (L64), which does name an
  invalidation cascade. It is a Phase 0.5 demonstration obligation and is
  claimed by `PG-05-08` (`gate_refs == ['PG-05-08']`); its subject is that a
  rejected claim triggers the cascade, not that the four operations are
  auditable.
- `C-09`, "Implement complete run manifest" (L80), which registers approvals and
  the exact published-artifact hash and is therefore audit-adjacent. Its
  acceptance enumerates run inputs and outputs, never correction, supersession,
  or promotion. `C-09` carries no gate at all — it is one of 21 register rows
  the §F scorecard does not reach — which is a property of the source document,
  not a gap this row should fill.
- `D-03`, "Define canonical memory promotion transaction". Wrong phase and wrong
  promotion: `D-03` is Phase 2 memory promotion, is `Deferred`, and is claimed by
  `PG-2-03` and `PG-2-04`. Adding it would also drag a dormant row into a Phase 1
  gate and change this row's derived disposition.

**Derived disposition — recomputed, not read.** `REG-C-10` has
`activation_source_status` `Open` and current `source_status` `Open`, which is
`REQUIRED_NOW` by goal L213-214. Aggregation over `{C-10}` therefore takes the
first branch of goal L248-250 ("`REQUIRED_NOW` if any related row is
`REQUIRED_NOW`"). Stored `derived_program_disposition` and `program_disposition`
are both `REQUIRED_NOW`, as `validate_ledger_structural.py:1564-1565` requires.

**`authority_effect` — `null`, and not a choice.**
`validate_ledger_structural.py:1551` asserts `authority_effect is None` for
every `RELATED_REGISTER_SCOPE` row, and goal L252-254 confines the three
`authority_effect` values to `AUTHORITATIVE_OCCURRENCE`. There is no open
judgment here, unlike a `disposition_item`.

**`activation_predicate: null` — load-bearing.** Goal L288-290: a component
whose derived disposition is `REQUIRED_NOW`, "including one that became
`REQUIRED_NOW` by related-register aggregation", has a null predicate. A
predicate here would be a contract violation, not a nicety.

**`gate_refs: []` and `disposition_refs: []`, with the reverse link closed.**
The gate map runs the other way: `validate_ledger_structural.py:2659-2666`
builds it from every phase-gate clause's `related_register_ids` and asserts each
register row's `gate_refs` equals its image. `REG-C-10`'s stored `gate_refs` is
exactly `['PG-1-07']` — this row is the sole clause claiming `C-10`, and the
link closes in both directions. `disposition_refs` is empty because no
third-order finding is attached to this clause; the disposition ordinals live on
`disposition_item` and `SCALE-*` rows.

**`primary_spec: null`.** Goal L184 permits null "only when `scope_derivation`
explicitly supplies program-wide or related-register ownership". This row
supplies related-register ownership, and null "never means inactive". The
artifact ownership sits on `REG-C-10` under S15.

**Applicable review slot.** This is a non-register canonical row, so
`validate_ledger_preimplementation.py:199-204` appends `SCOPE` to its checks and
`scope_derivation.semantic_review` is the slot this review fills. It is present,
non-`null`, `PENDING`, and carries exactly the 10-key `PENDING` set with no
role-binding keys.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `PG-1-07`'s scope derivation is correct at the input bytes pinned
above.
