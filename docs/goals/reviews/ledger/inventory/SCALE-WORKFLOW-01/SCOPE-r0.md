# Inventory review — SCALE-WORKFLOW-01 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `SCALE-WORKFLOW-01` |
| `review_type` | `SCOPE` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `ada0fb8a-424a-40b8-aa85-79326ee8641e` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-15T13:10:28Z` |

Inputs were read and independently recomputed in this session between
`2026-08-15T13:05Z` and the timestamp above.

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

Fresh structural validation at these exact bytes → exit `0`.

## Reviewed inventory, exactly as read

`review_inventory_projection(row, "SCOPE")` — canonical JSON:

```json
{"activation_predicate":null,"disposition_refs":["M-5"],"gate_refs":[],"related_register_ids":[],"scope_derivation":{"authority_effect":null,"derived_program_disposition":"REQUIRED_NOW","related_register_ids":[],"rule":"PROGRAM_WIDE_ACTIVE_CONTROL"}}
```

Digests observed at review time, **pre-record**:

- `reviewed_input_sha256` (pre-record): `50d98e203abea27c8c7853fcd23f58abf1c694751db0e29deae983d56fa82d2b`
- `reviewed_inventory_sha256` (pre-record): `353989a577eed37b666999a6e5a8bcecd0a7d66415ab82efa181cb59936cf68d`

The inventory digest is shared with the other three `SCALE-WORKFLOW-*` rows —
and differs from the four `SCALE-SQLITE-*` rows only in `disposition_refs`
(`["M-5"]` here versus `["R-5"]` there), which is the sole field of this
projection that is not identical across all eight scale triggers. The input
digest is unique to this row.

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line 204,
the first bullet under `### Reconsider the simple state table when` (L202),
inside `## H. Storage and workflow scale-up triggers` (L191):

> - long-running workflows require durable timers/signals across services;

- `source_hash` `26d51b31…` recomputed over the whole register → matches.
- `text_digest` recomputed over the normalized L204-204 span →
  `e25e6bcb29a79eb9ff4ee75a8252c11f04fda91515cdea47bbcf693955a6e344`, equal to
  the stored value.
- `required_acceptance_text` is that span with the list marker and trailing `;`
  removed: "long-running workflows require durable timers/signals across
  services". Character-exact.
- Span `(204, 204)` and anchor `SCALE-WORKFLOW-01` are both unique within this
  path.

## Reasoning

**Kind.** `scale_trigger` is correct, and the subject is the *workflow engine*,
not the storage engine — a different second-level heading (L202) under the same
section H. The row is not a `register_row` (section H narrative, not a
sections A–F table row; `register_id`, `priority`, `source_status` all null),
not a `phase_gate_clause` (it states no phase exit condition; the gate that
concerns recorded reevaluation triggers is `PG-2-06` at L169), and not a
`first_release_deferral` (`DEF-13` at L187 defers "migration to a distributed
workflow engine or PostgreSQL before observed need" — the deferral that this
trigger, if it fired, would put back on the table).

**Distinguishing it from its siblings.** This is the only one of the four
workflow triggers whose subject is *time and topology*: durable timers and
signals that must survive across service boundaries. `SCALE-WORKFLOW-02` is
about maintainability of rework paths, `-03` about correctness under
concurrency and retry, `-04` about the cost of observing the system. A
long-running workflow can demand durable timers while rework paths are still
clear, retries still idempotent, and observability still cheap — so the trigger
is disjoint from the other three and its own row is justified.

**Derivation rule.** Fixed by kind: goal L235-245 requires
`PROGRAM_WIDE_ACTIVE_CONTROL` for `scale_trigger`, and L247-248 forces
`related_register_ids == []` and `derived_program_disposition ==
REQUIRED_NOW`. Stored values match. The substantive check passes: durable
timers and cross-service signalling are properties of the execution substrate,
which every workflow step shares, so program-wide is the right scope rather
than a narrowing to any register decision.

**`REQUIRED_NOW` is not a claim that the condition holds.** Nothing in the
reviewed bytes asserts that long-running workflows currently require durable
cross-service timers; indeed M-5 records the opposite conclusion for Phase 0.5.
What is current is the control:
`REQ-SCALE-WORKFLOW-01-REEVALUATION-CONTROL` is worded "recorded and enforced
without requiring its condition to occur". Derivation and proof obligation
agree.

**Related register IDs.** `[]`, correct by rule and on the merits. The clause
names no register decision. Unlike the `SCALE-SQLITE-*` rows, this row carries
no `blocked_scope` cone at all, so there is not even an adjacent register set to
be tempted by; goal L232-235's no-padding rule is satisfied trivially.

**Disposition refs.** `["M-5"]`, and correct on the merits as well as
validator-pinned (`validate_ledger_structural.py:2652`). Disposition finding
**M-5** ("Human-feedback rework transitions", report L197-210) is dispositioned
"Accept" and closes with: "SQLite plus explicit state and attempt tables is
sufficient for Phase 0.5. **A durable workflow platform should be adopted only
after observed rework/concurrency complexity justifies it.**" That sentence is
the decision these four register bullets are the triggers for — it is what
makes M-5, rather than any storage finding, the governing disposition. For this
row specifically, the link is to M-5's platform-adoption holding rather than to
one of its six capability bullets; I state that plainly rather than claim a
bullet-level match, and it is sufficient because `disposition_refs` names the
disposition that governs the clause, not a bullet.

**Gate refs.** `[]`. Verified all 109 non-register canonical rows carry `[]`;
the validator's `gate_map` equality (`:2660-2664`) is asserted over register
rows only.

**Activation predicate.** `null`, required by goal L288-290 for a
`REQUIRED_NOW` component. The clause reads like a predicate, but predicates
belong to dormant scope awaiting activation; this row is not dormant, and
`PROGRAM_WIDE_ACTIVE_CONTROL` cannot derive a conditional disposition.

**Applicable review slot.** Non-register canonical row, so
`validate_ledger_preimplementation.py:200-204` appends `SCOPE`;
`scope_derivation.semantic_review` is present, non-`null`, `PENDING`, with
exactly the 10-key `PENDING` set and no role-binding keys. This is the
applicable slot.

**Input-side observations (covered by `reviewed_input_sha256`, not by this
projection).** `delivery_status` is `SPEC_DRAFT` with `review_round` 0, no open
findings, and no `blocked_scope` — the clean counterpart to the
`SCALE-SQLITE-*` rows' `REVIEW_BLOCKED` state. `primary_spec` is S14
(`docs/specs/equity-os-s14-earnings-review-workflow-rework.md`), the workflow
spec, correctly distinct from the SQLITE rows' S10. None of these fields is in
the `SCOPE` inventory.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `SCALE-WORKFLOW-01`'s scope derivation is correct at the input bytes
pinned above.
