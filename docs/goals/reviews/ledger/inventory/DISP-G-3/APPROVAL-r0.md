# Inventory review — DISP-G-3 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-G-3` |
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
{"approval_records":[],"human_review_id":["HR-0004"],"required_approvals":[{"actor":null,"approval_id":"APR-DISP-G-3-01","approval_type":"DELEGATED_ARTIFACT_APPROVAL","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Delegated fresh Sol xhigh specification reviewer","scope":"G-3 under S18","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (the recorder must recompute both
after its Phase A evidence append, per recording design r2 §3.4 — appending review
evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `597d6b69a174ea324effbc8f864f9fffa80a9aa35c23049fede97050fa5d99ef`
- `reviewed_inventory_sha256` (pre-record): `f27b8adb244d3dc1a999945010e89bddd4e41ea1d6a22885f8c5d282097542ea`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` lines 75-86, anchor
`G-3`, `source_title` "Cross-company economics comparison":

> ### G-3 — Cross-company economics comparison
>
> **Disposition: Accept.**
>
> Comparing assisted work on unfamiliar Phase 1 companies with a manual baseline from the now-familiar discovery company confounds company complexity, analyst familiarity, and tooling effect.
>
> The gate should use:
>
> - a manual baseline for each Phase 1 company or a matched historical quarter;
> - normalized operational measures such as verification time per material claim, source-locate time, and correction time;
> - explicit complexity descriptors such as document count, page count, claim count, and number of reconciliation exceptions;
> - total report time retained as a business metric, but not treated as a portable causal measure by itself.


Recomputed this round against current bytes:

- `source_hash` over the whole file → `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`, equal to the stored value.
- `text_digest` over the normalized L75-86 span
  (CRLF-to-LF normalized, surrounding ASCII whitespace trimmed) →
  `ae5b642d33d770cb932dc756db0b063455ba57c1e449022c40be7290acaa1ea4`, equal to the stored value.
- `required_acceptance_text` equals that normalized span byte for byte.
- Every `evidence_refs` object on this row was re-hashed against current bytes and
  matches its stored `content_sha256`.

## Reasoning

**Enumerated.** One requirement:

| `approval_id` | `approval_type` | `required_authority` | `scope` | `status` |
|---|---|---|---|---|
| `APR-DISP-G-3-01` | `DELEGATED_ARTIFACT_APPROVAL` | `Delegated fresh Sol xhigh specification reviewer` | `G-3 under S18` | `UNRESOLVED` |

The type is in the closed vocabulary (goal L~538-548). Its authority literal is not
pinned in the goal's authority table by design; instead
`validate_ledger_structural.py:2620-2631` requires every
`DELEGATED_ARTIFACT_APPROVAL` requirement in the ledger to share one identical
nonempty `required_authority`, and this row's value is that shared literal.

**Source-clause scan for omitted authorities.** Goal L188 defines this review's
remit precisely: `approval_inventory_review` "records whether a fresh
`REVIEWER`-role review has checked the component's source clauses for omitted
approval types", and goal L535-537 gives the derivation basis — "its exact source
acceptance text, dependencies, phase gates, transitions, fail-closed boundaries,
and any approved security exception".

Read against the exact text of report L75-86: the clause is written entirely in the
prescriptive voice of gate design — "The gate **should use**: a manual baseline …;
normalized operational measures …; explicit complexity descriptors …; total report
time retained as a business metric". It contains no verb of authorization: no
approve, accept, sign off, authorize, commit, or owner. There is no dependency,
phase gate, transition, or fail-closed boundary named in the clause that would
introduce one.

Near-miss examined and rejected. `REG-C-12`, this component's related register,
does carry `ANALYST_ACCEPTANCE` / `Responsible analyst`, and its register text
opens "**Pre-agreed** improvement is evaluated …". That word could suggest an
agreement obligation reaching this occurrence. It does not: "pre-agreed" belongs to
`C-12`'s own acceptance criteria in the pinned v2 register, not to this clause, and
this review's basis is the component's exact source acceptance text. The register
decision carries its approval where it belongs, on `REG-C-12`.

Contrast within this batch, which shows the enumeration is discriminating rather
than uniform: `DISP-M-1` and `DISP-M-5`, whose clauses do use approval verbs
("Approve and version it"; "… and reapproval"), each carry a second requirement of
type `ANALYST_ACCEPTANCE` / `Responsible analyst`. `DISP-G-3`'s clause uses none
and carries none.

**`human_review_id`.** `"HR-0004"` — a single `HR-####` string, one of the three
shapes goal L~192-196 permits, normalized to `["HR-0004"]` by
`normalized_human_review_id` inside this projection. It resolves into the one
canonical human-review artifact.

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

**Conclusion.** `required_approvals` is complete for this component: exactly one
authority is demanded by the clause and by the contract — delegated approval of the
owning specification artifact — and exactly that one is enumerated.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition, and grants no
authority of any kind (goal L~624-626). It records only that `DISP-G-3`'s
`required_approvals` inventory is complete at the input bytes pinned above.
