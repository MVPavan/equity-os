# Inventory review — SCALE-WORKFLOW-02 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `SCALE-WORKFLOW-02` |
| `review_type` | `APPROVAL` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `ada0fb8a-424a-40b8-aa85-79326ee8641e` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-15T13:10:30Z` |

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

`review_inventory_projection(row, "APPROVAL")` — canonical JSON:

```json
{"approval_records":[],"human_review_id":["HR-0004"],"required_approvals":[{"actor":null,"approval_id":"APR-SCALE-WORKFLOW-02-01","approval_type":"DELEGATED_ARTIFACT_APPROVAL","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Delegated fresh Sol xhigh specification reviewer","scope":"SCALE-WORKFLOW-02 under S14","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

The stored row value of `human_review_id` is the single string `"HR-0004"`;
the projection normalizes it to the sorted one-element list above
(`validate_ledger_structural.py:316`). Both forms were checked.

Digests observed at review time, **pre-record**:

- `reviewed_input_sha256` (pre-record): `1000ed68b4c09da928d8a6ac3d0c6093b7541667674e92867fcaa96240398a3b`
- `reviewed_inventory_sha256` (pre-record): `fa5a910e25dd264c89bf32d0f1db95f39a292fbe7c3b3aa14496740eba5fe19e`

## What this review decided

Whether `required_approvals` is **complete** — whether the source clause
demands any authority whose sign-off is not enumerated. Not whether the one
enumerated approval has been obtained; it is `UNRESOLVED` with null actor,
timestamp, and `matched_record_id`, the contract-correct unresolved shape
(goal L592-596).

## Source clause, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` L205:

> - human rework and invalidation paths cannot be maintained clearly;

under `### Reconsider the simple state table when` (L202) in section H,
lead-in L193, closing clause L209.

## Reasoning

**This is the hardest `ANALYST_ACCEPTANCE` call of the four workflow rows, and
I want the reasoning on the record.** The clause is explicitly about the
*human* rework loop, and its governing disposition `DISP-M-5` carries an
`ANALYST_ACCEPTANCE` requirement with authority "Responsible analyst" and scope
"M-5 analyst acceptance", paired with a `TYPED_APPROVAL` evidence item. If any
of the eight scale triggers should carry an analyst authority, it would be this
one. It should not, for three reasons that I checked rather than assumed:

- *What the analyst accepts is M-5's design, not this trigger.* The
  requirement's own `scope` string binds it to M-5 — the six-capability rework
  design (immutable step outputs, idempotent re-entry, evidence-package
  versioning, dependency-aware invalidation, partial revalidation, and the
  rejected-claim-to-reapproval path). Those are claims about earnings-review
  correctness. This clause states the condition under which the *platform
  choice* is revisited. An analyst accepting that the rework design is right is
  a different act from observing that its paths have become unmaintainable.
- *Nothing in the clause asks for acceptance.* Compare `PG-2-05` (L168,
  "operational burden is acceptable"), which does carry a
  `PRODUCT_OWNER_DECISION` precisely because "acceptable" is authority-relative.
  This clause says paths "cannot be maintained clearly" — a statement about the
  system, true or false independently of who signs it.
- *Duplication would be a permanent trap.* Goal L188: "One record satisfies at
  most one requirement; one approval never implies another." Mirroring M-5's
  analyst requirement onto the four `SCALE-WORKFLOW-*` rows would create four
  requirements no single analyst acceptance of M-5 could ever satisfy.

The comparison case confirms the pattern is disposition-specific rather than a
blanket omission: `DISP-R-5`, governing the four `SCALE-SQLITE-*` rows, carries
no analyst approval, and those rows carry none either.

**The rest of the derivation basis.** Goal L535-538 derives
`required_approvals` from "exact source acceptance text, dependencies, phase
gates, transitions, fail-closed boundaries, and any approved security
exception."

- *Source acceptance text.* Names no business authority. "human rework" invokes
  people, but as *users of the workflow*, not as approvers of anything this
  clause states.
- *Dependencies.* `dependencies` is `[]`.
- *Phase gates.* `gate_refs` is `[]`, and `PG-2-06` (L169), the gate about
  recorded reevaluation triggers, carries **no** `required_approvals` at all.
  No gate authority to inherit.
- *Transitions.* Inventory-review recording is transition-free by design
  (recording design r2 §3.5).
- *Fail-closed boundaries.* None created; L193 makes the clause a non-blocker.
- *Approved security exception.* `security_exception_ids` is `[]`, correctly.

**The one enumerated approval is the right one.**
`APR-SCALE-WORKFLOW-02-01`, `DELEGATED_ARTIFACT_APPROVAL`, authority "Delegated
fresh Sol xhigh specification reviewer", scope "SCALE-WORKFLOW-02 under S14".
It exists because the row has `primary_spec` S14 and a paired
`REQ-SCALE-WORKFLOW-02-SPEC-REVIEW` obligation, and its scope names S14 rather
than S10 — correct for a workflow trigger. Goal L577-583 makes this the only
approval type whose authority is a process role; the validator (`:2618-2632`)
asserts every such requirement shares one identical authority string, and I
verified this literal matches the single ledger-wide value.

**Human-review linkage is correct.** `human_review_id` is `HR-0004` alone —
correctly *not* `HR-0003`, whose scope covers the S10 R3-F-01 cone (including
the four `SCALE-SQLITE-*` rows) but no `SCALE-WORKFLOW-*` row; I read
`HR-0003`'s `scope.component_ids` directly and confirmed the absence, and
`validate_ledger_structural.py:2784-2785` pins that exact reverse set.
`HR-0004`'s 144-ID scope does contain this row.

**Should `GOAL_OR_PROCESS_AUTHORIZATION` appear here?** No. `HR-0004`'s
`decision_authority` is that type with authority "Explicit rank-1 current-user
authority over the active goal process", but I checked every row in the ledger:
**zero** `required_approvals` entries carry it. Rank-1 process authority routes
through the human-review artifact and its resolution decisions;
`human_review_id`, itself part of this reviewed inventory, is the field that
carries it.

**`approval_records` is `[]`.** Correct: no approval decision has been made.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition, and grants
no authority. It records only that `SCALE-WORKFLOW-02`'s `required_approvals`
inventory is complete at the input bytes pinned above.
