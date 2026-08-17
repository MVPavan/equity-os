# Inventory review — PG-1-06 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `PG-1-06` |
| `review_type` | `APPROVAL` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `9e80cd5e-6230-475f-937f-f1db62fa5746` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-16T04:05:18Z` |

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

`review_inventory_projection(row, "APPROVAL")` — canonical JSON, produced by the
validator's own projection function, `ast`-extracted from
`validate_ledger_structural.py` per recording design r2 §3.3:

```json
{"approval_records":[],"human_review_id":["HR-0004"],"required_approvals":[{"actor":null,"approval_id":"APR-PG-1-06-01","approval_type":"ANALYST_ACCEPTANCE","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Responsible analyst","scope":"PG-1-06 analyst acceptance","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (the recorder recomputes
`reviewed_input_sha256` after its Phase A evidence append, recording design r2
§3.4 — appending review evidence mutates `evidence_refs` and therefore the input
projection):

- `reviewed_input_sha256` (pre-record): `bda61bb7df981152da9f49b527886b88b38869046efdb54d692a2a2ef204d7f1`
- `reviewed_inventory_sha256` (pre-record): `8d81b7fbe4e92950c5848555310be91bbb0450c1d5e036bceed4e6edea5a6a17`

## Scope of this decision

Per recording design r2 §2.2, this review decides one question: is
`required_approvals` **complete** — does the source clause demand any authority
whose sign-off is not enumerated? Goal L188 fixes the standard:
`required_approvals` "exhaustively declares the component's typed approval
obligations", and "Empty `required_approvals` means a completed, evidenced
determination that no approval is required, not an unknown inventory." Goal
L619-622 scopes the check to "the exact source acceptance text, dependencies,
gates, and fail-closed boundaries". This is an audit of the obligation list, not
of whether any approval has been obtained. The `APPROVAL` inventory projection
(goal L435-436) covers `required_approvals`, `approval_records`,
`human_review_id`, and `security_exception_ids`.

## The source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line 155,
under `### Phase 1 may exit only when` (register v2 L148), inside `## F. Phase-gate scorecard` (L122); `source_title` "Phase 1 gate clause 6",
`source_anchor` `F-1-06`:

> - deterministic calculations satisfy their declared exact/tolerance/seeded replay class and the approved narrative is bound to an artifact hash;

Recomputed this round against current bytes:

- `source_hash` over the whole register file → `26d51b31…`, equal to the stored value.
- `text_digest` over the normalized L155-155 span (`"\n".join(lines[154:155]).strip(" \t\n\r\f\v")`,
  the exact rule at `validate_ledger_structural.py:174-176`) → `a4f0460fcfea62f2417261f9f13c5504dcb79e2b63c7ccdd7fd272b014ec5138`,
  equal to the stored value.
- `EV-PG-1-06-SOURCE.content_sha256` recomputed over the same span → `a4f0460fcfea62f2417261f9f13c5504dcb79e2b63c7ccdd7fd272b014ec5138`,
  equal to the stored value.
- `required_acceptance_text` equals that span with the `- ` list marker and the
  terminal `;` removed, byte for byte.
- Anchor uniqueness holds ledger-wide: `(funda-blueprint-implementation-decision-register-v2.md, F-1-06)` occurs once
  across all 213 rows, and so does the span `(155, 155)` — both recomputed this round
  (`validate_ledger_structural.py:179-180`).

## Reasoning

**`required_approvals` is not empty on this row — it carries exactly one
requirement, and this is the only such row in this batch:**

| Field | Value |
|---|---|
| `approval_id` | `APR-PG-1-06-01` |
| `approval_type` | `ANALYST_ACCEPTANCE` |
| `required_authority` | `Responsible analyst` |
| `scope` | `PG-1-06 analyst acceptance` |
| `status` | `UNRESOLVED` |
| `actor` / `timestamp` / `matched_record_id` | `null` / `null` / `null` |
| `evidence_ref_ids` | `[]` |

That is the correct unresolved shape: goal L610-611 makes a `SATISFIED`
requirement one that "matches one `APPROVED` record with identical type,
authority, scope, actor, timestamp, evidence, and authority source", so an
unresolved requirement must carry none of those. It is paired with
`REQ-PG-1-06-ANALYST_ACCEPTANCE-01` (`ANALYST`/`TYPED_APPROVAL`), whose
`approval_ids` names `APR-PG-1-06-01` — exactly the linkage goal L485-487
prescribes, where a `TYPED_APPROVAL` item "names one or more component-local
requirements that are `SATISFIED` by unique approval records".

**The clause does name an approval, and the enumerated one matches it.** The
second conjunct is "the **approved** narrative is bound to an artifact hash".
`PG-1-06` is therefore on the approval-bearing side of §F's own partition: of the
35 gate clauses, exactly six contain approval or acceptance language and exactly
those six carry an approval requirement (`PG-05-01`, `PG-05-02`, `PG-05-05`,
`PG-1-06`, `PG-1-09`, `PG-2-05`). I re-derived that partition from the 35 clause
texts this round.

**Is `ANALYST_ACCEPTANCE` / "Responsible analyst" the right authority?** Yes, and
I checked it against the source rather than against the ledger's own habit. The
artifact being approved is the **narrative** — the analyst-authored research
output. Register C-16, which supplies this conjunct, reads "**approved narrative
bytes** are immutable and bound to content hash", and `REG-C-16` itself carries
`APR-REG-C-16-02`, `ANALYST_ACCEPTANCE`, "Responsible analyst" — the same type
and the same authority. The approval vocabulary in this ledger offers thirteen
types; the alternatives that could plausibly own a narrative are
`DOMAIN_EXPERT_ACCEPTANCE` (used where a subject-matter judgment is required, as
on A-10's materiality policy) and `PRODUCT_OWNER_DECISION` (used for
product-scope decisions). Neither fits: approving one's own research narrative
for release is the responsible analyst's act, and C-16 says so.

**Is one requirement enough — does the clause demand a second authority?** I
tested the first conjunct separately. "Deterministic calculations satisfy their
declared exact/tolerance/seeded replay class" is mechanical, and it is proved by
`REQ-PG-1-06-COMMAND-PROOF`, not by anyone's signature; goal L487-490 keeps the
two paths distinct and this row uses both correctly. I also tested the word
"**declared**": a declaration of replay class is a property of the specification
artifact, and neither the clause nor C-16 requires the declaration itself to be
separately approved. And I tested "bound to an artifact hash": the binding is
mechanical, and C-16 places it alongside the approval rather than as a second
approval. So exactly one authority is demanded and exactly one is enumerated.

**No `DELEGATED_ARTIFACT_APPROVAL` is owed** — for the same structural reason as
the other eleven components in this batch: a `phase_gate_clause` has
`primary_spec=null` and cannot carry `applicable_spec_ids` (goal L230-232,
enforced at `validate_ledger_structural.py:1519-1520`), so it owns no
specification artifact for a delegated approval to be scoped to. All 35 gate
clauses are alike in this, including the six that carry a non-delegated
authority.

**No second, register-mirrored authority is owed.** `REG-C-16` carries
`APR-REG-C-16-02` (`ANALYST_ACCEPTANCE`) and `REG-C-08` carries only its
delegated approval. This gate's `APR-PG-1-06-01` is a *distinct* obligation from
`APR-REG-C-16-02`, not a duplicate of it: goal L610-613 makes records "globally
unique for matching purposes" and says they "may not satisfy two requirements",
so the two requirements will need two recorded decisions — which is correct,
because they have different scopes ("PG-1-06 analyst acceptance" versus C-16's
own scope) and goal L613-615 requires exactly that where one real-world decision
would otherwise be stretched across two scopes.

**Applicable review slot.** `approval_inventory_review` is present, non-`null`,
`status=PENDING`, carrying exactly the 10-key `PENDING` set with no role-binding
keys — verified this round. `validate_ledger_preimplementation.py:200-204` makes
`APPROVAL` an unconditional check on every canonical row, so this slot applies to
`PG-1-06` regardless of kind, and it is the slot this review is written against.

**`human_review_id` = `"HR-0004"`.** In the `APPROVAL` inventory projection
(goal L435-436) and therefore in this review's remit, so I verified the link
rather than passing over it: `PG-1-06` does appear in the affected-component set of
`HR-0004` in `docs/goals/equity-os-blueprint-human-review-needed.md`, which is
the `RECONCILE_AUTHORITY` resolution under which this row received its
`COMMAND`-classified requirement. The link is a record of that reconciliation,
not an approval obligation — goal L615-617 is explicit that ordinary
`REVIEWER`-role evidence/inventory review "is never an authority-bearing human
resolution", and a human-review link does not create or discharge a
`required_approvals` entry.

**`approval_records` = `[]`.** Correct and currently universal: the whole
ledger contains **zero** approval records, which I counted this round across all
213 rows. Goal L188 makes `approval_records` "append-only evidence of actual
approval decisions"; no decision has been recorded anywhere in this programme
yet, so an entry here would be a fabrication.

**`security_exception_ids` = `[]`.** Also currently universal — zero security
exceptions exist across all 213 rows. This clause raises no trust-boundary
carve-out, so nothing is missing.

**Fail-closed boundary, as goal L619-622 requires this review to check.** The
question is whether this component could reach terminal proof while an authority
its source demands has been bypassed. It cannot: the one authority the clause names is enumerated, is `UNRESOLVED`,
and is bound to a `TYPED_APPROVAL` evidence item that is also `UNRESOLVED`.
Terminal proof therefore cannot be reached without a recorded analyst acceptance
matching `APR-PG-1-06-01` on type, authority, scope, actor, timestamp, and
evidence (goal L610-611). The gate fails closed on both the evidence and the
authority side.

**Corroboration, treated as corroboration only.** Important finding 2 of
`docs/goals/reviews/ledger/equity-os-blueprint-approval-inventory-r0.md` named
`PG-1-06 — ANALYST_ACCEPTANCE` as a §F clause with "explicit approval or
acceptance authority" and no corresponding non-delegated requirement. That
requirement now exists, with exactly the type that finding specified. I verified
its presence, type, authority, scope, status, and evidence pairing directly
against the clause and against C-16, not by reading them off the finding.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition, and it
grants no non-delegated authority (goal L624-626). It records only that this
component's `required_approvals` inventory is complete at the input bytes
pinned above.
