# Inventory review — REG-A-02 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-A-02` |
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

`REG-A-02` has `kind == "register_row"`. Its `scope_derivation` reads exactly

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
exists to record. No `SCOPE` artifact was written for `REG-A-02`.

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
{"approval_records":[],"human_review_id":["HR-0004"],"required_approvals":[{"actor":null,"approval_id":"APR-REG-A-02-01","approval_type":"DELEGATED_ARTIFACT_APPROVAL","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Delegated fresh Sol xhigh specification reviewer","scope":"A-02 under S05: Select one discovery company and four consecutive quarters","status":"UNRESOLVED","timestamp":null},{"actor":null,"approval_id":"APR-REG-A-02-02","approval_type":"PRODUCT_OWNER_DECISION","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Product owner","scope":"A-02 under S05: Select one discovery company and four consecutive quarters","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `210dc8d0e73a77a0e50e2ad2a3fc008c78acd6992efbff84c763c2986f68a117`
- `reviewed_inventory_sha256` (pre-record): `8cc35d69c0d336440a0514ac1b25261146fa33eb490c7294a338534f83db2f68`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line
32, register ID `A-02`, title "Select one discovery company and four consecutive quarters":

```text
| A-02 | Critical | Select one discovery company and four consecutive quarters | Quarter 0 is reserved for the manual baseline and bootstrap thesis; Quarters 1–3 are reserved for three assisted incremental updates; source package exists for all quarters and at least one management commitment can be tracked across periods | — | Open |
```

- `source_hash` recomputed over the whole pinned v2 register →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L32 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `7b498369713bdb18afd5bdd1a006949c382234dd04af65a7fe0e5f024bdb713a`, matching the row and
  matching `EV-REG-A-02-SOURCE.content_sha256`.
- `required_acceptance_text` equals the source row's acceptance cell byte for
  byte, and `register_id`/`source_title` equal its ID and decision cells
  (checked by comparison, not by eye).
- Register `Status` cell: `Open`; `Priority`: `Critical`; `Dependencies`:
  `—`. Row `program_disposition`: `REQUIRED_NOW`; `delivery_status`:
  `SPEC_DRAFT`; `gate_result`: `NOT_EVALUATED`.

## Reasoning

**What this review decides.** Whether `required_approvals` on `REG-A-02`
enumerates every authority whose sign-off the A-02 clause and its derivation
sources demand. It is not a judgment that any approval has been obtained: both
requirements are `UNRESOLVED` with null actor, null timestamp, empty
`evidence_ref_ids`, and null `matched_record_id`, which the validator requires
of an unresolved requirement (`validate_ledger_structural.py:1240-1245`).

**The derivation rule.** Goal L535-538: "Every component derives
`required_approvals` from its exact source acceptance text, dependencies, phase
gates, transitions, fail-closed boundaries, and any approved security
exception." I worked that list.

**Source acceptance text.** Register line 32 names no human role. Its demands
are a selection and two existence facts. What it *does* imply is a scope
decision — which company and which four quarters the programme commits to —
and that is a product decision, which is exactly what `APR-REG-A-02-02`
(`PRODUCT_OWNER_DECISION`, authority `Product owner`) carries. That authority
string is one of the three the closed vocabulary permits for this type
(`:2607-2611`, goal L574).

**Dependencies.** The register Dependencies cell for A-02 is `—`. There is no
upstream row whose authority could propagate here.

**Phase gates.** `gate_refs` is exactly `["PG-0A-03"]`. I read PG-0A-03's own
ledger row: its `required_approvals` is empty and its source clause is
"one discovery company and four consecutive quarters—one baseline/bootstrap
plus three assisted—are selected". A gate that demands no approval cannot
propagate one. (`gate_refs` is additionally validator-pinned to the inverse of
the gate rows' `related_register_ids` at `:2664-2666`, so this is not a
hand-maintained list.)

**Transitions.** `transition_history` is a read-only input to this review and
is covered by `transition_history_sha256` inside the input projection. Nothing
in this row's history introduces an approval obligation; `approval_records` is
`[]` and `matched_record_ids` is empty ledger-wide at this pre-state
(`:3046`).

**Fail-closed boundaries and security exceptions.** `security_exception_ids` is
`[]` and `blocked_scope` is `[]`. A-02 states no prohibition and claims no
deviation, so no `SECURITY_EXCEPTION` obligation arises.

**The delegated approval.** `APR-REG-A-02-01` (`DELEGATED_ARTIFACT_APPROVAL`,
authority `Delegated fresh Sol xhigh specification reviewer`) is the process-role
approval every canonical row carries for its specification artifact; the
validator asserts all 123 such requirements share one identical authority
literal (`:2618-2632`).

**Candidate authorities I tested and rejected.** `ANALYST_ACCEPTANCE` — A-02
selects the slice; the analyst work that would need acceptance (performing the
manual baseline, authoring the thesis) is A-03's and A-11's, and both of those
rows carry `ANALYST_ACCEPTANCE`. `DATA_RIGHTS_APPROVAL` — "source package
exists for all quarters" is about the package existing, not about the right to
use it; the data-rights obligations in this ledger sit on the five rows that
carry that type, none of which is A-02, and A-02's clause makes no licensing
claim. `BUDGET_APPROVAL` — adding a fourth quarter has a cost, but the clause
authorizes no spend; budget authority is A-07's and A-12's.

**Other fields in the `APPROVAL` inventory.** `approval_records` `[]`;
`security_exception_ids` `[]`; `human_review_id` `HR-0004`, projected as
`["HR-0004"]`. `REG-A-02` is one of the 134 canonical components inside
HR-0004's structured scope, a set digest-pinned at
`EXPECTED_HR0004_SCOPE_DIGEST` and asserted in both directions at `:2806-2811`,
so this link is mechanically forced, not editorial. HR-0004 is resolved
(`RECONCILE_AUTHORITY`), not blocking.

**Conclusion.** `required_approvals` is complete for the A-02 clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `REG-A-02`'s `required_approvals` inventory is correct at the input bytes pinned
above.
