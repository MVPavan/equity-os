# Inventory review — PG-0A-08 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `PG-0A-08` |
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
{"approval_records":[],"human_review_id":[],"required_approvals":[],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (the recorder recomputes
`reviewed_input_sha256` after its Phase A evidence append, recording design r2
§3.4 — appending review evidence mutates `evidence_refs` and therefore the input
projection):

- `reviewed_input_sha256` (pre-record): `514f0c6ad5b8b5d059ebafde20d5622cc340a33745ad984b08574c072f1e9287`
- `reviewed_inventory_sha256` (pre-record): `3d8490f952ad11fc316d91ecf8ad98db82eea8653909b7236c8c66569c3d904f`

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

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line 133,
under `### Phase 0A may exit only when` (register v2 L124), inside `## F. Phase-gate scorecard` (L122); `source_title` "Phase 0A gate clause 8",
`source_anchor` `F-0A-08`:

> - the golden-set owner and initial cases exist.

Recomputed this round against current bytes:

- `source_hash` over the whole register file → `26d51b31…`, equal to the stored value.
- `text_digest` over the normalized L133-133 span (`"\n".join(lines[132:133]).strip(" \t\n\r\f\v")`,
  the exact rule at `validate_ledger_structural.py:174-176`) → `47924ca3115e35ab64986b0b6e0fdeb55bed240956f0e67214835860670321f3`,
  equal to the stored value.
- `EV-PG-0A-08-SOURCE.content_sha256` recomputed over the same span → `47924ca3115e35ab64986b0b6e0fdeb55bed240956f0e67214835860670321f3`,
  equal to the stored value.
- `required_acceptance_text` equals that span with the `- ` list marker and the
  terminal `.` removed, byte for byte.
- Anchor uniqueness holds ledger-wide: `(funda-blueprint-implementation-decision-register-v2.md, F-0A-08)` occurs once
  across all 213 rows, and so does the span `(133, 133)` — both recomputed this round
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
"exist", which asserts a state of an artifact, not a sign-off. §F draws that
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

**The authority in this neighbourhood is unusual, so I checked it closely.**
`REG-A-08` carries `APR-REG-A-08-02`, a `NAMED_OWNER_COMMITMENT` held by the
"Golden-set owner" — one of only three `NAMED_OWNER_COMMITMENT` requirements in
the entire ledger — with a paired `REQ-REG-A-08-NAMED_OWNER_COMMITMENT`
`TYPED_APPROVAL` item. The register decision is "**Appoint** golden-test-set
owner", and an appointment is precisely where a named person's commitment is
taken. This clause instead says the owner "exists", which is what a reader of the
appointment record observes.

**Why the related register's authority is not also owed here — the decisive
point, and it is mechanical, not stylistic.** `REG-A-08`'s `NAMED_OWNER_COMMITMENT` is the golden-set owner's own commitment to the role the appointment creates. A reader could
argue that this gate cannot pass without that decision and should therefore
enumerate it too. Duplicating it would be positively harmful under the contract.
Goal L610-613: "A `SATISFIED` requirement matches one `APPROVED` record … Record
IDs and resolution decision IDs are globally unique for matching purposes and
**may not satisfy two requirements**", and goal L188 repeats it: "One record
satisfies at most one requirement; one approval never implies another." So a
duplicate requirement on this gate could not be satisfied by the same named-owner commitment recorded for A-08
— it would demand a second, separately recorded real-world decision covering the
same ground, which goal L613-615 permits only "Where one real-world decision
covers two approval types or scopes". Here there is one decision and one scope.
The obligation is inventoried exactly once, on the component whose source text
demands it.

**The reading that would produce a finding, stated and answered.** One could
argue that an owner cannot "exist" unless someone has committed, so the
commitment is implicit in the clause and should be enumerated. I do not adopt it,
for two reasons. First, goal L188 says "one approval never implies another" —
the contract deliberately refuses to derive one requirement from another's
implication, which is exactly the inference this reading needs. Second, A-08's
acceptance column tells us what the gate reads: "**Named owner**, repository
location, review cadence, and first twenty labeled cases". A name in a record is
an artifact fact. The commitment behind the name is a separate typed obligation,
and it is inventoried.

**Second gate over the same register, checked for a split obligation.** A-08 is
also claimed by `PG-05-10` ("the first golden cases are automated or consistently
reviewable"), which likewise carries no approval requirement. Neither gate
absorbs A-08's commitment obligation, and neither should; it stays on the
register row exactly once.

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
`PG-0A-08` regardless of kind, and it is the slot this review is written against.

**`human_review_id` = `null`.** In the `APPROVAL` inventory projection (goal
L435-436) and therefore in this review's remit. It is correct: this row was not
inside the affected-component set of `HR-0004`
(`docs/goals/equity-os-blueprint-human-review-needed.md`), the only human
resolution in the ledger, and no other human resolution names it. I checked the
affected set directly rather than inferring it from the field.

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

**Corroboration, treated as corroboration only.** `PG-0A-08` is absent from
Important finding 2 of the program-level approval-inventory review. Independent
reading and prior review agree.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition, and it
grants no non-delegated authority (goal L624-626). It records only that this
component's `required_approvals` inventory is complete at the input bytes
pinned above.
