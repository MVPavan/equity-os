# Inventory review — REG-A-07 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-A-07` |
| `review_type` | `APPROVAL` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `90676a15-0b66-4e7c-9fd2-f1b300d6e780` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-16T13:44:34Z` |

Role binding: `CONTEXT.md` "Agent roles (harness-wide)" L137-139 and L147 bind
`REVIEWER` to Claude Opus 5 at high effort, in an agent and context independent
of any `IMPLEMENTER` that produced the reviewed content. The digest above is the
`CONTEXT.md` bytes at review time and is an immutable historical capture.

## Input hashes read for this review

| Input | SHA-256 |
|---|---|
| `docs/goals/equity-os-blueprint-completion.md` (active goal contract) | `f15f7ab5a4e425dec3877ab7f1f7594687979060e4dbcd49390a8a8d5fedb85f` |
| `docs/goals/equity-os-blueprint-component-ledger.jsonl` (canonical ledger) | `de236d7e8dcf02e307ec58797f5722ae2f85d1d8cdba57d4ecc07df5383c9c97` |
| `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` (pinned v2 decision register) | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| `docs/blueprint/funda-third-order-review-disposition-report.md` (pinned third-order disposition report) | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| `scripts/equity_os_blueprint/validate_ledger_structural.py` (structural validator) | `731d0d8b208b577967c92e3992e7ec1a4333cdecbf89f6951c32d2ec469436f9` |
| `scripts/equity_os_blueprint/validate_ledger_preimplementation.py` (preimplementation validator) | `f7a225a1f99cb85c92cde3094505a92a746552280eb45dae0253a71ab9048013` |
| `scripts/equity_os_blueprint/extract_goal_validators.py` (extractor) | `5d20d796666d1154fb3c84ba4fa7407ee82819510a5ac06254f7f4a3126c6f2a` |
| `docs/goals/equity-os-blueprint-human-review-needed.md` (canonical human-review artifact) | `094fcdfab74a3f4c6fdb82b1520fc4d13b636ac0e9ed10194e5d607aed2ce9af` |
| `CONTEXT.md` (role binding) | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r2.md` (artifact format, design r2 §2.2) | `adf908ac8cec01a55a53438624c6a8913f673f5b7cecd3e955fc4919f73803fb` |

Fresh structural validation at these exact bytes:
`python3 scripts/equity_os_blueprint/validate_ledger_structural.py --repo-root .`
→ exit `0` (run at review time). Every `evidence_refs` entry on this row was
additionally re-hashed by hand against its current target bytes this round —
`FILE_BYTES` objects over whole-file bytes, `UTF8_LINE_SPAN` objects over the
`\n`-joined, whitespace-trimmed span — and all matched.

## Register-row review applicability, verified on this row

`REG-A-07` has `kind == "register_row"`. Its `scope_derivation` reads exactly

```json
{
 "authority_effect": null,
 "derived_program_disposition": "REQUIRED_NOW",
 "related_register_ids": [],
 "rule": "REGISTER_STATUS",
 "semantic_review": null
}
```

so `scope_derivation.semantic_review` **is `null`**, checked on the live row
rather than assumed. Two independent mechanisms make that the applicable-review
rule: `validate_ledger_preimplementation.py:200-204` builds the per-row check
list as `APPROVAL` + `EVIDENCE` always and appends `SCOPE` only
`if row["kind"] != "register_row"`; and the goal fixes the null slot for this
kind at L208-211, mechanized at goal L2886
(`assert derivation["semantic_review"] is None`). This row therefore carries
**two** applicable reviews, `EVIDENCE` and `APPROVAL`, and no `SCOPE` review
exists to record. No `SCOPE` artifact was written for `REG-A-07`.

One consequence is worth stating rather than leaving implicit: the `SCOPE`
inventory projection (`validate_ledger_structural.py:293-305`) is the only
projection that covers `disposition_refs`, `gate_refs`, `activation_predicate`,
and `related_register_ids`. On a register row those fields are covered by the
**input** projection — so any mutation to them stales both reviews below — but
they are not the subject of a per-component semantic review, by contract. The
scope of a register row comes from the pinned v2 register itself.

## Reviewed inventory, exactly as read

`review_inventory_projection(row, "APPROVAL")` — canonical JSON:

```json
{"approval_records":[],"human_review_id":["HR-0004"],"required_approvals":[{"actor":null,"approval_id":"APR-REG-A-07-01","approval_type":"DELEGATED_ARTIFACT_APPROVAL","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Delegated fresh Sol xhigh specification reviewer","scope":"A-07 under S08: Define initial per-workflow budgets","status":"UNRESOLVED","timestamp":null},{"actor":null,"approval_id":"APR-REG-A-07-02","approval_type":"BUDGET_APPROVAL","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Budget owner","scope":"A-07 budget authorization","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `36c24551a0e8355e46332a32c570380f2f2db6096a2c6ceb9555430bae019ed5`
- `reviewed_inventory_sha256` (pre-record): `1f455b353763dbb37f6fc9b9ba2f50ba7af0249ceefcfd6ab48d43043d933109`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line
37, register ID `A-07`, title "Define initial per-workflow budgets":

```text
| A-07 | High | Define initial per-workflow budgets | Ceilings or measurement rules for model cost, tool calls, latency, document volume, retries, and analyst minutes | A-13 | Open |
```

- `source_hash` recomputed over the whole pinned v2 register →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L37 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `0ca41b6dee0a54da6dbf1010859095e997a53b41886ce0736d125c0d05c33923`, matching the row and
  matching `EV-REG-A-07-SOURCE.content_sha256`.
- `required_acceptance_text` equals the source row's acceptance cell byte for
  byte, and `register_id`/`source_title` equal its ID and decision cells
  (checked by comparison, not by eye).
- Register `Status` cell: `Open`; `Priority`: `High`; `Dependencies`:
  `A-13`. Row `program_disposition`: `REQUIRED_NOW`; `delivery_status`:
  `SPEC_DRAFT`; `gate_result`: `NOT_EVALUATED`.

## Reasoning

**What this review decides.** Whether `required_approvals` on `REG-A-07`
enumerates every authority the A-07 clause and its derivation sources demand.
Both requirements are `UNRESOLVED` with null actor/timestamp/record.

**Source acceptance text.** A-07 sets spending and consumption ceilings. The
authority that follows is budget authority, and it is enumerated:
`APR-REG-A-07-02` is `BUDGET_APPROVAL` with authority `Budget owner`, the
single permitted string for that type (`:2588`, goal L565). `APR-REG-A-07-01`
is the standard delegated specification-review approval.

**Dependencies.** The register cell is `A-13`. `REG-A-13` carries
`PRODUCT_OWNER_DECISION`; that does not propagate here. A-07's budgets are
expressed in terms A-13's success-metric contract defines, which is a
definitional dependency, not an authority one.

**Phase gates.** `gate_refs` is exactly `["PG-1-10"]`. I read that row:
`required_approvals` is empty; the clause is "cost, latency, failures, and
retries are visible". No authority propagates from it.

**Dispositions re-read.** `disposition_refs` are `M-8`, `T-1`, `T-2`.
`DISP-T-1` ("Operating budget and calendar disappeared") is the disposition
that demanded a *separate* row for weekly capacity, phase dates, monthly
ceilings and maintenance burden; its `related_register_ids` is `["A-12"]`, not
A-07 — which is the point of the disposition: it split standing budget away
from per-run ceilings. `DISP-T-2` relates `A-13`, `DISP-M-8` relates `A-13` and
`C-18`. All three carry only the delegated approval. None introduces an
authority A-07 lacks.

**The candidate I tested hardest: `CAPACITY_COMMITMENT`.** A-07's sixth
dimension is "analyst minutes", and capacity commitment is a real authority in
this ledger's vocabulary. I rejected it here for a reason grounded in
`DISP-T-1` above: the disposition deliberately separates per-workflow ceilings
(A-07) from the standing capacity commitment (A-12), and `REG-A-12` carries
`CAPACITY_COMMITMENT` / `Capacity owner`. Requiring the capacity owner to sign
A-07 as well would restate an obligation the source explicitly relocated.

**Other candidates rejected.** `PURCHASE_AUTHORIZATION` — the vocabulary
contains it, but no `required_authority` value is defined for it in the closed
map (`:2586-2613`), so no row can carry it without a reconciled vocabulary
change; and A-07 authorizes no purchase, it sets ceilings. `PROVIDER_AUTHORIZATION` — "model cost" implies a provider, but A-07 caps
spend rather than authorizing anyone to serve it; and like
`PURCHASE_AUTHORIZATION`, that type has no `required_authority` value in the
closed map, so no row in the ledger carries it (I counted: zero requirements of
either type across all 213 rows).

**Transitions, fail-closed boundaries, security exceptions.** `approval_records`
`[]`; `security_exception_ids` `[]`; `blocked_scope` `[]`; no prohibition or
deviation in the clause.

**Other `APPROVAL` inventory fields.** `human_review_id` `HR-0004`, projected
`["HR-0004"]` — inside the digest-pinned 134-component HR-0004 scope.

**Conclusion.** `required_approvals` is complete for the A-07 clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `REG-A-07`'s `required_approvals` inventory is correct at the input bytes pinned
above.
