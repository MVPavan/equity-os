# Inventory review — DISP-M-4 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-M-4` |
| `review_type` | `APPROVAL` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `a88da077-0dfc-49ab-bb1a-df4e8266291b` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-15T13:16:03Z` |

Role binding: `CONTEXT.md` "Agent roles (harness-wide)" binds `REVIEWER` to
Claude Opus 5 at high effort, in an agent and context independent of any
`IMPLEMENTER` that produced the reviewed content. The digest above is the
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

`review_inventory_projection(row, "APPROVAL")` — canonical JSON:

```json
{"approval_records":[],"human_review_id":["HR-0004"],"required_approvals":[{"actor":null,"approval_id":"APR-DISP-M-4-01","approval_type":"DELEGATED_ARTIFACT_APPROVAL","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Delegated fresh Sol xhigh specification reviewer","scope":"M-4 under S11","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (the recorder must recompute both
after its Phase A evidence append, per recording design r2 §3.4 — appending review
evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `7756b975f26284b62fb73ea268c8c6c3d987bc84323c5f72b05a63947bc39329`
- `reviewed_inventory_sha256` (pre-record): `0ea9a827fb5864901153ffe375970fa8aafef9a54a0aaed823e465bb4cf18e70`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` lines 182-195, anchor
`M-4`, `source_title` "Knowledge-time enforcement and leakage":

> ### M-4 — Knowledge-time enforcement and leakage
>
> **Disposition: Accept, split into two policies.**
>
> **Current and historical data access controls** are implementation requirements:
>
> - every run has a cutoff;
> - SQL, document, memory, and fact retrieval enforce `knowledge_time <= cutoff`;
> - canonical fact and relationship selection is evaluated **as of that cutoff**, so later corrections or restatements do not retroactively rewrite a historical package;
> - tool calls declare whether they are cutoff-aware;
> - historical replay permits only approved archived or time-bounded sources;
> - tests deliberately insert post-cutoff records and verify that retrieval excludes them.
>
> **Model-weight leakage** is different. It cannot be eliminated and must be disclosed for historical LLM evaluation. It does not invalidate current-period earnings review, where the run date is current and the model is not being evaluated as if it were historically ignorant.


Recomputed this round against current bytes:

- `source_hash` over the whole file → `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`, equal to the stored value.
- `text_digest` over the normalized L182-195 span
  (CRLF-to-LF normalized, surrounding ASCII whitespace trimmed) →
  `b75537aa2059b3740ee345a515b8ae6022098917e9b5d78541fbaf9ea02ef131`, equal to the stored value.
- `required_acceptance_text` equals that normalized span byte for byte.
- Every `evidence_refs` object on this row was re-hashed against current bytes and
  matches its stored `content_sha256`.

## Reasoning

**Enumerated.** One requirement:

| `approval_id` | `approval_type` | `required_authority` | `scope` | `status` |
|---|---|---|---|---|
| `APR-DISP-M-4-01` | `DELEGATED_ARTIFACT_APPROVAL` | `Delegated fresh Sol xhigh specification reviewer` | `M-4 under S11` | `UNRESOLVED` |

Type in the closed vocabulary (goal L~538-548); authority literal is the shared
value enforced at `validate_ledger_structural.py:2620-2631`.

**Source-clause scan for omitted authorities.** Remit per goal L188; derivation
basis per goal L535-537.

Report L182-195 splits into two policies and neither names an authorizing actor.
The access-control half is a list of enforcement requirements and tests; the
leakage half states that model-weight leakage "cannot be eliminated and **must be
disclosed** for historical LLM evaluation". Two candidates were examined:

1. *"historical replay permits only **approved** archived or time-bounded
   sources"*. This is the only appearance of "approved" in the clause, and it is
   adjectival: it constrains which sources a replay may read, describing a property
   those sources must already have, rather than requiring a sign-off on this
   component. The register control `C-15` states the same enforcement without any
   approval requirement of its own — `REG-C-15` carries the delegated artifact
   approval and nothing else.
2. *`PRODUCT_OWNER_DECISION` / `Product owner authorized to activate deferred
   blueprint scope`*, which the related register `REG-E-10` does carry. Rejected:
   that requirement exists on `REG-E-10` because `E-10` is captured `Deferred` and
   the approval is what would activate it. This clause does not activate `E-10` —
   as this component's `SCOPE` review establishes, `ACTIVE_CONTROL` derives
   `REQUIRED_NOW` without aggregating related-row state
   (`validate_ledger_structural.py:1558-1559`), and `REG-E-10` retains its own
   `CONDITIONAL_UNACTIVATED` disposition and its own activation approval. Importing
   that approval here would misrepresent a disclosure obligation as an activation.

No dependency, phase gate, transition, or fail-closed boundary in the clause
introduces a further authority.

**`human_review_id`.** `"HR-0004"`, a single `HR-####` string (goal L~192-196),
normalized to `["HR-0004"]` in this projection.

**`approval_records`.** `[]`. Correct and required: no approval decision has been
made on this component, and goal L~588-592 says a requirement missing actor,
timestamp, evidence, authorization proof, or matching record stays `UNRESOLVED`.
Each requirement here carries `actor: null`, `timestamp: null`,
`evidence_ref_ids: []`, `matched_record_id: null`, `status: "UNRESOLVED"` —
internally consistent, and consistent with `approval_records` being empty. An
`APPROVED` record with no requirement, or a `SATISFIED` requirement with no record,
would each have been a defect; neither is present.

**`security_exception_ids`.** `[]`. The clause raises no fail-closed security
boundary and no security exception has been approved, so an empty list is the
correct completed determination rather than an unknown.

**Conclusion.** `required_approvals` is complete: the clause demands no authority
beyond the delegated approval of the owning specification artifact.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition, and grants no
authority of any kind (goal L~624-626). It records only that `DISP-M-4`'s
`required_approvals` inventory is complete at the input bytes pinned above.
