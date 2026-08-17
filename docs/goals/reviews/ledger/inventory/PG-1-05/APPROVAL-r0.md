# Inventory review — PG-1-05 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `PG-1-05` |
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
{"approval_records":[],"human_review_id":["HR-0004"],"required_approvals":[],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (the recorder recomputes
`reviewed_input_sha256` after its Phase A evidence append, recording design r2
§3.4 — appending review evidence mutates `evidence_refs` and therefore the input
projection):

- `reviewed_input_sha256` (pre-record): `66696e7877c345c9b8ed0ba54174c83c5c1860bed7023157e297942c1f3da8ba`
- `reviewed_inventory_sha256` (pre-record): `97690c6bdaa272b10410d8e6282fe908df7a46302da6a6197299f8bb98ef8958`

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

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line 154,
under `### Phase 1 may exit only when` (register v2 L148), inside `## F. Phase-gate scorecard` (L122); `source_title` "Phase 1 gate clause 5",
`source_anchor` `F-1-05`:

> - post-cutoff data are excluded by tested store/tool controls;

Recomputed this round against current bytes:

- `source_hash` over the whole register file → `26d51b31…`, equal to the stored value.
- `text_digest` over the normalized L154-154 span (`"\n".join(lines[153:154]).strip(" \t\n\r\f\v")`,
  the exact rule at `validate_ledger_structural.py:174-176`) → `66611d4eb86eb74858bd72109eeaa8dce34fcf4b7d7f7bf6431d292c4c4c8a3a`,
  equal to the stored value.
- `EV-PG-1-05-SOURCE.content_sha256` recomputed over the same span → `66611d4eb86eb74858bd72109eeaa8dce34fcf4b7d7f7bf6431d292c4c4c8a3a`,
  equal to the stored value.
- `required_acceptance_text` equals that span with the `- ` list marker and the
  terminal `;` removed, byte for byte.
- Anchor uniqueness holds ledger-wide: `(funda-blueprint-implementation-decision-register-v2.md, F-1-05)` occurs once
  across all 213 rows, and so does the span `(154, 154)` — both recomputed this round
  (`validate_ledger_structural.py:179-180`).

## Reasoning

`required_approvals` is `[]`. Goal L188 is explicit that this is a claim, not a
blank: "Empty `required_approvals` means a completed, evidenced determination
that no approval is required, not an unknown inventory." So this review must
affirm the emptiness on the merits, not skip the row. Across the 169 canonical
rows, 40 carry an empty approval inventory — 29 `phase_gate_clause`, 6
`document_strategy_clause`, 4 `authority_clause`, and `SEQ-11` — and this row is
one of them.

**The clause names no approving authority.** Its operative verb is
"are excluded by tested … controls", which asserts a state of an artifact, not a sign-off. §F draws that
distinction inside its own text, and the ledger follows it exactly: of the 35
gate clauses, the six that carry an approval requirement are precisely the six
whose own wording names an approval or acceptance — `PG-05-01` ("is
**approved**") → `ANALYST_ACCEPTANCE`; `PG-05-02` ("produced and **reviewed**")
→ `ANALYST_ACCEPTANCE`; `PG-05-05` ("is **approved**") →
`DOMAIN_EXPERT_ACCEPTANCE`; `PG-1-06` ("the **approved** narrative") →
`ANALYST_ACCEPTANCE`; `PG-1-09` ("is **accepted**") → `CAPACITY_COMMITMENT`;
`PG-2-05` ("is **acceptable**") → `PRODUCT_OWNER_DECISION`. I re-derived that
partition from the 35 clause texts this round; the correspondence is exact in
both directions, and this clause falls on the no-approval side of it.

**"Tested" is the clause's only qualifier, and it points at a command, not at an
authority.** The clause is the one in this batch whose own text names a test, and
the row carries `REQ-PG-1-05-COMMAND-PROOF` accordingly. C-15's acceptance makes
the shape concrete — "tests insert and reject post-cutoff records" — a
negative-path test with a determinate outcome. Nothing in the clause or in C-15
requires a person to attest that the exclusion holds; the test attests it. Goal
L487-490's typed-approval routing applies to determinations of competence, and
none is engaged.

**No authority in the neighbourhood.** `REG-C-15`, the sole related register,
carries only its `DELEGATED_ARTIFACT_APPROVAL`.

**One adjacent authority checked and excluded.** Knowledge-cutoff leakage is also
the subject of `E-10` ("Publish historical-replay leakage policy"), which is a
`Deferred` Phase 3 register row and could plausibly attract a publication or
disclosure authority. `E-10` is not related to this clause — this component's
`related_register_ids` is exactly `["C-15"]`, affirmed by its `SCOPE` review — so
no authority of E-10's is owed here.

**No `DELEGATED_ARTIFACT_APPROVAL` is owed, for a structural reason.** 123 of
the 169 canonical rows carry one; the 46 that do not are all 35
`phase_gate_clause` rows, all 6 `document_strategy_clause` rows, all 4
`authority_clause` rows, and `SEQ-11`. The dividing line is spec ownership: a
delegated artifact approval approves a specification artifact and is scoped
`"<X> under <Sxx>: …"`. A `phase_gate_clause` has `primary_spec=null` and cannot
carry `applicable_spec_ids` at all — goal L230-232 makes that key *rejected* for
this kind, enforced by the exact key-set assertion at
`validate_ledger_structural.py:1519-1520`. With no owned spec artifact there is
no artifact for a delegated approval to be scoped to. `SEQ-11`, the one
sequence clause without a delegated approval, confirms the rule from the other
side: it is the only sequence clause whose `applicable_spec_ids` is `[]`.

**Applicable review slot.** `approval_inventory_review` is present, non-`null`,
`status=PENDING`, carrying exactly the 10-key `PENDING` set with no role-binding
keys — verified this round. `validate_ledger_preimplementation.py:200-204` makes
`APPROVAL` an unconditional check on every canonical row, so this slot applies to
`PG-1-05` regardless of kind, and it is the slot this review is written against.

**`human_review_id` = `"HR-0004"`.** In the `APPROVAL` inventory projection
(goal L435-436) and therefore in this review's remit, so I verified the link
rather than passing over it: `PG-1-05` does appear in the affected-component set of
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
its source demands has been bypassed. It cannot: with an empty approval inventory the only paths to terminal state run
through `required_evidence`, whose items are all `UNRESOLVED`, and this review
has confirmed that the clause names no authority that a typed requirement would
have carried. The gate fails closed on the evidence side, and there is no
authority-side hole for it to fail open through.

**Corroboration, treated as corroboration only.** `PG-1-05` is absent from
Important finding 2 of the program-level approval-inventory review. Independent
reading and prior review agree.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition, and it
grants no non-delegated authority (goal L624-626). It records only that this
component's `required_approvals` inventory is complete at the input bytes
pinned above.
