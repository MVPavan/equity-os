# Inventory review — REG-A-13 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-A-13` |
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

`REG-A-13` has `kind == "register_row"`. Its `scope_derivation` reads exactly

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
exists to record. No `SCOPE` artifact was written for `REG-A-13`.

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
{"approval_records":[],"human_review_id":[],"required_approvals":[{"actor":null,"approval_id":"APR-REG-A-13-01","approval_type":"DELEGATED_ARTIFACT_APPROVAL","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Delegated fresh Sol xhigh specification reviewer","scope":"A-13 under S08: Freeze success-metric contract","status":"UNRESOLVED","timestamp":null},{"actor":null,"approval_id":"APR-REG-A-13-02","approval_type":"PRODUCT_OWNER_DECISION","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Product owner","scope":"A-13 under S08: Freeze success-metric contract","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `be4eb463a1ef3c3da33c16211c3ffcd8b3695c5c2b466ebeed2c2b8890cc34f9`
- `reviewed_inventory_sha256` (pre-record): `751059cc1402cb615dbc7b9e683ce338bd7b2cf135acacebf7e931ed3b9e5a1b`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line
43, register ID `A-13`, title "Freeze success-metric contract":

```text
| A-13 | Critical | Freeze success-metric contract | Versioned definitions and measurement methods for factual accuracy, citation correctness, numerical traceability, unsupported claims, analyst minutes, per-claim verification time, coverage capacity, latency, cost, failure/retry rate, and phase applicability | A-01 | Open |
```

- `source_hash` recomputed over the whole pinned v2 register →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L43 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `2eabf45af26be8a946814f7d14194bf79955f1fd53dd91d9dad12e41a7441bf3`, matching the row and
  matching `EV-REG-A-13-SOURCE.content_sha256`.
- `required_acceptance_text` equals the source row's acceptance cell byte for
  byte, and `register_id`/`source_title` equal its ID and decision cells
  (checked by comparison, not by eye).
- Register `Status` cell: `Open`; `Priority`: `Critical`; `Dependencies`:
  `A-01`. Row `program_disposition`: `REQUIRED_NOW`; `delivery_status`:
  `SPEC_DRAFT`; `gate_result`: `NOT_EVALUATED`.

## Reasoning

**What this review decides.** Whether `required_approvals` on `REG-A-13`
enumerates every authority the A-13 clause and its derivation sources demand.
Both requirements are `UNRESOLVED` with null actor/timestamp/record.

**Source acceptance text.** A-13's verb is "Freeze" — it fixes the programme's
success-metric contract, which is a product-level commitment about what
"working" means. `APR-REG-A-13-02` is `PRODUCT_OWNER_DECISION` with authority
`Product owner`, one of the three permitted strings for that type
(`:2607-2611`). `APR-REG-A-13-01` is the standard delegated
specification-review approval. Two requirements, matching the two-item evidence
inventory.

**Dependencies.** The register cell is `A-01`. `REG-A-01` is not in this batch;
its authority does not propagate here, and A-13's dependence on the
user/distribution boundary is definitional (which metrics are in scope), not
delegated.

**Phase gates.** `gate_refs` is `["PG-0A-05", "PG-1-10"]`. I read both rows:
PG-0A-05 ("materiality and success-metric contracts are versioned") and
PG-1-10 ("cost, latency, failures, and retries are visible") each carry an
empty `required_approvals`. Neither propagates an authority.

**Dispositions re-read.** `M-8`, `T-1`, `T-2`. `DISP-T-2` relates exactly
`["A-13"]` and carries only the delegated approval. `DISP-M-8` ("Results-season
throughput") relates `A-13` and `C-18` and likewise carries only the delegated
approval; its five tracked quantities — reports per analyst per week, peak-week
volume, backlog age, percent completed before the next material event, capacity
at the Phase 1 company count — are folded into this contract by disposition,
and I checked specifically whether folding capacity language in should have
dragged `CAPACITY_COMMITMENT` onto this row. It should not: `DISP-M-8`'s own
words are that "the register should **track**" those quantities, i.e. define and
measure them, and the capacity that is actually *committed* is A-12's, which
carries `CAPACITY_COMMITMENT` / `Capacity owner`.

**Other candidates tested and rejected.** `BUDGET_APPROVAL` — "cost" is one of
the eleven metrics to be defined; authorizing spend is A-07's and A-12's.
`ANALYST_ACCEPTANCE` — "analyst minutes" and "verification time per claim" are
measured *about* the analyst, not accepted *by* them; the ledger attaches
analyst acceptance to analyst work product (A-03, A-04, A-11).
`DOMAIN_EXPERT_ACCEPTANCE` — "factual accuracy" and "citation correctness" are
measurement definitions; the domain judgment about what is material is A-10's.

**Transitions, fail-closed boundaries, security exceptions.** `approval_records`
`[]`; `security_exception_ids` `[]`; `blocked_scope` `[]`. No prohibition and no
claimed deviation in the clause.

**Other `APPROVAL` inventory fields.** `human_review_id` is **`null`**,
projected `[]`. As on `REG-A-12`, I verified this rather than assumed it:
`REG-A-13` is not among the 134 canonical IDs in HR-0004's digest-pinned
structured scope, and `:2806-2811` asserts the correspondence in both
directions, so a link here would fail structural validation. It is one of
exactly seven register rows with no human-review link.

**Conclusion.** `required_approvals` is complete for the A-13 clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `REG-A-13`'s `required_approvals` inventory is correct at the input bytes pinned
above.
