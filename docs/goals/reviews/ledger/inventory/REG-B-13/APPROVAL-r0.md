# Inventory review — REG-B-13 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-B-13` |
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

`REG-B-13` has `kind == "register_row"`. Its `scope_derivation` reads exactly

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
exists to record. No `SCOPE` artifact was written for `REG-B-13`.

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
{"approval_records":[],"human_review_id":["HR-0004"],"required_approvals":[{"actor":null,"approval_id":"APR-REG-B-13-01","approval_type":"DELEGATED_ARTIFACT_APPROVAL","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Delegated fresh Sol xhigh specification reviewer","scope":"B-13 under S07: Add reviewer-bias and measurement controls","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `e8c7a025e658d20589a135674e8268e8bdc3843c5678abb9a5a33b911b784bb7`
- `reviewed_inventory_sha256` (pre-record): `3e2c08952e4cfa3d7916dd3dfb893cf3650e0de5fca3e3427a70e5bde62fb685`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line
63, register ID `B-13`, title "Add reviewer-bias and measurement controls":

```text
| B-13 | High | Add reviewer-bias and measurement controls | Quarter 0 is not reused for assisted work; instrumentation is symmetric and overhead measured; shadow-mode seeded-error drills cannot be promoted; false-accept/false-reject results are stratified by materiality and epistemic class; optional external spot review procedure defined | A-03, A-08, A-13 | Open |
```

- `source_hash` recomputed over the whole pinned v2 register →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L63 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `0f3c2de68cb37e48e56b3ebbec631268dd366e9e3ae85fb1dc387a1da94a2617`, matching the row and
  matching `EV-REG-B-13-SOURCE.content_sha256`.
- `required_acceptance_text` equals the source row's acceptance cell byte for
  byte, and `register_id`/`source_title` equal its ID and decision cells
  (checked by comparison, not by eye).
- Register `Status` cell: `Open`; `Priority`: `High`; `Dependencies`:
  `A-03, A-08, A-13`. Row `program_disposition`: `REQUIRED_NOW`; `delivery_status`:
  `SPEC_DRAFT`; `gate_result`: `NOT_EVALUATED`.

## Reasoning

**What this review decides.** Whether `required_approvals` on `REG-B-13`
enumerates every authority the B-13 clause and its derivation sources demand.
The single requirement is `UNRESOLVED` with null actor/timestamp/record.

**The shape of this row makes the question sharp.** Like `REG-B-08`,
`required_approvals` holds exactly one entry — `APR-REG-B-13-01`
(`DELEGATED_ARTIFACT_APPROVAL` / `Delegated fresh Sol xhigh specification
reviewer`). So the real question is whether a named business authority is
missing, and the goal requires that to be an affirmative determination rather
than a skip (goal L188).

**The candidate the clause hands you: "optional external spot review procedure
defined".** This is the only phrase in the batch naming an *external* party, and
`EXTERNAL_COORDINATION_APPROVAL` is a real type in the closed vocabulary
(goal L548-549). I rejected it, on three grounds. First, the demand is that a
procedure be **defined**, not performed — defining a procedure needs no external
party's consent. Second, the source qualifier is "optional", and `DISP-M-6`,
the disposition this control comes from, is weaker still: "occasional external
spot review **where practical**". An obligation the source marks optional and
practicality-contingent cannot be a mandatory sign-off. Third, the closed
required-authority map (`:2586-2613`) defines no `required_authority` value for
`EXTERNAL_COORDINATION_APPROVAL` at all, so no row could carry it without a
reconciled vocabulary change — and goal L551-554 is explicit that an authority
not represented "must be reconciled and explicitly approved before that row can
advance; it may not be collapsed into a nearby type." Collapsing this into, say,
`LEGAL_REVIEW` is precisely what the contract forbids.

**The second candidate: "cannot be promoted".** Control (3) forbids promoting
shadow-mode seeded-error drills, and `MEMORY_PROMOTION` is an approval type. I
rejected it because the direction is wrong: the clause *removes* a promotion
path rather than creating one that someone must authorize. A prohibition
forecloses; it does not require sign-off. `DISP-6-6` states it the same way —
"prevent all promotion paths from touching them" — and `DISP-M-6` adds "Never
inject a known falsehood into the artifact that can be promoted or published."

**Dependencies.** The register cell is `A-03, A-08, A-13` — three upstream
rows, each carrying a different authority type. `REG-A-03` carries `ANALYST_ACCEPTANCE`,
`REG-A-08` carries `NAMED_OWNER_COMMITMENT`, `REG-A-13` carries
`PRODUCT_OWNER_DECISION`. None propagates: each is the authority for its own
row's act (performing the baseline, owning the golden set, freezing the metric
contract), and "one approval never implies another" (goal L188). B-13 consumes
all three outputs without authorizing any of them.

**Phase gates.** `gate_refs` is exactly `["PG-05-04"]`, whose clause is
"claim-level review telemetry and correction categories are available without
invalid percentile claims" and whose own `required_approvals` is empty. No
gate-side authority.

**Dispositions re-read.** `M-6`, `M-9`, `6.6`. `DISP-M-6` and `DISP-6-6` both
list `B-13` in `related_register_ids`, and both carry only the delegated
specification-review approval — so even the dispositions that supply B-13's
controls name no business authority.

**Fail-closed boundaries and security exceptions.** `security_exception_ids` is
`[]`, `approval_records` is `[]`, `blocked_scope` is `[]`. The clause's
prohibitions grant no exception and claim no deviation, so no
`SECURITY_EXCEPTION` requirement arises.

**Other `APPROVAL` inventory fields.** `human_review_id` `HR-0004`, projected
`["HR-0004"]`, inside the digest-pinned 134-component HR-0004 scope.

**Conclusion.** `required_approvals` is complete for the B-13 clause: the
delegated specification-review approval, and affirmatively no named business
authority.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `REG-B-13`'s `required_approvals` inventory is correct at the input bytes pinned
above.
