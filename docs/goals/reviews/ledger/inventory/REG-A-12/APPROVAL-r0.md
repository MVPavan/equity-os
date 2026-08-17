# Inventory review — REG-A-12 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-A-12` |
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

`REG-A-12` has `kind == "register_row"`. Its `scope_derivation` reads exactly

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
exists to record. No `SCOPE` artifact was written for `REG-A-12`.

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
{"approval_records":[],"human_review_id":[],"required_approvals":[{"actor":null,"approval_id":"APR-REG-A-12-01","approval_type":"DELEGATED_ARTIFACT_APPROVAL","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Delegated fresh Sol xhigh specification reviewer","scope":"A-12 under S08: Define operating calendar, standing budget, and capacity","status":"UNRESOLVED","timestamp":null},{"actor":null,"approval_id":"APR-REG-A-12-02","approval_type":"BUDGET_APPROVAL","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Budget owner","scope":"A-12 under S08: Define operating calendar, standing budget, and capacity","status":"UNRESOLVED","timestamp":null},{"actor":null,"approval_id":"APR-REG-A-12-03","approval_type":"CAPACITY_COMMITMENT","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Capacity owner","scope":"A-12 under S08: Define operating calendar, standing budget, and capacity","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `98cc1327091579efdc4f842a5ad7f15d6539bdf55417f23cb30df4259085637d`
- `reviewed_inventory_sha256` (pre-record): `103c8045cd0b2c12217974042c9e627a0b2902add226bf98eb4b16b1479d3cde`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line
42, register ID `A-12`, title "Define operating calendar, standing budget, and capacity":

```text
| A-12 | High | Define operating calendar, standing budget, and capacity | Weekly builder/analyst capacity, target phase dates, monthly provider/model/infrastructure ceilings, maintenance allowance, and expected company coverage documented | A-01, A-02 | Open |
```

- `source_hash` recomputed over the whole pinned v2 register →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L42 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `4e9cb7daed4ca172ca22eb094d166ac559ab22d834bd645e0f4374fd7c4a81e1`, matching the row and
  matching `EV-REG-A-12-SOURCE.content_sha256`.
- `required_acceptance_text` equals the source row's acceptance cell byte for
  byte, and `register_id`/`source_title` equal its ID and decision cells
  (checked by comparison, not by eye).
- Register `Status` cell: `Open`; `Priority`: `High`; `Dependencies`:
  `A-01, A-02`. Row `program_disposition`: `REQUIRED_NOW`; `delivery_status`:
  `SPEC_DRAFT`; `gate_result`: `NOT_EVALUATED`.

## Reasoning

**What this review decides.** Whether `required_approvals` on `REG-A-12`
enumerates every authority the A-12 clause and its derivation sources demand.
All three requirements are `UNRESOLVED` with null actor/timestamp/record.

**Source acceptance text.** A-12 commits both money and people, and the
enumeration carries one authority for each: `APR-REG-A-12-02`
(`BUDGET_APPROVAL` / `Budget owner`) for the monthly
provider/model/infrastructure ceilings and maintenance allowance, and
`APR-REG-A-12-03` (`CAPACITY_COMMITMENT` / `Capacity owner`) for weekly
builder/analyst capacity and expected coverage. Both authority strings are the
single permitted value for their type (`:2588-2589`, goal L565-566).
`APR-REG-A-12-01` is the standard delegated specification-review approval. This
is one of two rows in the batch carrying three requirements, the other being
`REG-A-04`; it is the only one whose two named authorities are both typed
commitments rather than a decision.

**Dependencies.** The register cell is `A-01, A-02`. Neither propagates
authority: A-01 bounds the distribution boundary, A-02 fixes the slice, and
`REG-A-02`'s `PRODUCT_OWNER_DECISION` belongs to the selection act, not to
budgeting it.

**Phase gates.** `gate_refs` is exactly `["PG-0A-07"]`. I read that row: its
`required_approvals` is empty and its clause is "operating capacity and standing
budget are documented". No gate-side authority to propagate.

**Dispositions re-read.** `M-8`, `T-1`, `T-2`. `DISP-T-1` relates exactly
`["A-12"]` and carries only the delegated approval; `DISP-M-8` relates `A-13`
and `C-18`; `DISP-T-2` relates `A-13`. None introduces an authority A-12 lacks.

**The candidate I tested hardest: `PRODUCT_OWNER_DECISION`.** "target phase
dates" and "expected company coverage" are the most product-shaped phrases in
the clause, and A-02, A-04 and A-13 all carry a product-owner decision. I
rejected it here for a source-grounded reason: `DISP-T-1` frames this row as
the *operating* budget and calendar — an execution-resource commitment — and
assigns it to budget and capacity ownership, whereas the product-owner
decisions in this cone attach to freezing contracts and choosing scope. Adding
a product-owner requirement would extend the row past what `DISP-T-1` and the
register text say.

**Other candidates rejected.** `PROVIDER_AUTHORIZATION` and
`PURCHASE_AUTHORIZATION` — "monthly provider/model/infrastructure ceilings" caps
spend; it authorizes neither a provider nor a purchase. Both types are in the
goal's approval vocabulary but neither has a `required_authority` value in the
closed map (`:2586-2613`), so no row in the ledger can carry either without a
reconciled vocabulary change, and I confirmed zero requirements of either type
exist across all 213 rows.

**Other `APPROVAL` inventory fields — and the one that needed checking.**
`approval_records` `[]`; `security_exception_ids` `[]`; `blocked_scope` `[]`;
`human_review_id` is **`null`**, projected as `[]`. That is unusual — 53 of the
60 register rows carry `HR-0004` — so I verified rather than assumed it.
`REG-A-12` is simply not among the 134 canonical component IDs in HR-0004's
structured scope, a set whose digest is pinned at
`EXPECTED_HR0004_SCOPE_DIGEST` and asserted in **both** directions at
`:2806-2811` (every scoped canonical row links HR-0004, and every row linking
HR-0004 is scoped). A link here would fail structural validation. `REG-A-12` is
one of exactly seven register rows with a null link — the others being
`REG-A-13`, `REG-B-06`, `REG-B-12`, `REG-C-04`, `REG-C-09`, `REG-D-03`. A human-
review link is in any case not an approval; it records that a human-review entry
covers the row, and HR-0004 is a resolved `RECONCILE_AUTHORITY` decision, not a
pending sign-off.

**Conclusion.** `required_approvals` is complete for the A-12 clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `REG-A-12`'s `required_approvals` inventory is correct at the input bytes pinned
above.
