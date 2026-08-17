# Inventory review — REG-A-08 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-A-08` |
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

`REG-A-08` has `kind == "register_row"`. Its `scope_derivation` reads exactly

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
exists to record. No `SCOPE` artifact was written for `REG-A-08`.

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
{"approval_records":[],"human_review_id":["HR-0004"],"required_approvals":[{"actor":null,"approval_id":"APR-REG-A-08-01","approval_type":"DELEGATED_ARTIFACT_APPROVAL","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Delegated fresh Sol xhigh specification reviewer","scope":"A-08 under S07: Appoint golden-test-set owner","status":"UNRESOLVED","timestamp":null},{"actor":null,"approval_id":"APR-REG-A-08-02","approval_type":"NAMED_OWNER_COMMITMENT","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Golden-set owner","scope":"A-08 under S07: Appoint golden-test-set owner","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `eea64b6b4b1fd7ec32b407f37bab4ff10c09d3c413cb778b270ea763ec595988`
- `reviewed_inventory_sha256` (pre-record): `55f5028e9a9e0c1439e1c3c2b1f7e56bb744f35a8ba05a2b15c943fc03fff176`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line
38, register ID `A-08`, title "Appoint golden-test-set owner":

```text
| A-08 | High | Appoint golden-test-set owner | Named owner, repository location, review cadence, and first twenty labeled cases, including prompt-injection/source-confusion cases | — | Open |
```

- `source_hash` recomputed over the whole pinned v2 register →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L38 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `f3242a22721b00ddd070a09c6bf8d98b4eae059c140fe6145903337854421389`, matching the row and
  matching `EV-REG-A-08-SOURCE.content_sha256`.
- `required_acceptance_text` equals the source row's acceptance cell byte for
  byte, and `register_id`/`source_title` equal its ID and decision cells
  (checked by comparison, not by eye).
- Register `Status` cell: `Open`; `Priority`: `High`; `Dependencies`:
  `—`. Row `program_disposition`: `REQUIRED_NOW`; `delivery_status`:
  `SPEC_DRAFT`; `gate_result`: `NOT_EVALUATED`.

## Reasoning

**What this review decides.** Whether `required_approvals` on `REG-A-08`
enumerates every authority the A-08 clause and its derivation sources demand.
Both requirements are `UNRESOLVED` with null actor/timestamp/record.

**Source acceptance text.** A-08's title is "Appoint golden-test-set owner" and
its first acceptance demand is "Named owner". The authority that follows is a
named-owner commitment, and it is enumerated: `APR-REG-A-08-02` is
`NAMED_OWNER_COMMITMENT` with authority `Golden-set owner`. That string is one
of exactly three the closed vocabulary permits for this type — the other two
being `Event-monitoring owner` and `Model-grade compute owner` (`:2603-2606`,
goal L573) — and I confirmed `Golden-set owner` is the one that matches this
clause rather than a near-miss. Note that the other two are the ledger's two
`AUTHORIZED_AUTHORITY_ADDITIONS` (`:2614-2617`); `Golden-set owner` is not an
addition, it is baseline.

**Dependencies.** The register Dependencies cell for A-08 is `—`. Nothing
upstream to propagate.

**Phase gates.** `gate_refs` is `["PG-0A-08", "PG-05-10"]`. I read both rows.
PG-0A-08 ("the golden-set owner and initial cases exist") and PG-05-10 ("the
first golden cases are automated or consistently reviewable") each carry an
empty `required_approvals`. The Phase-0A gate names the owner but demands no
separate sign-off beyond the one A-08 already carries.

**Dispositions re-read.** `M-6`, `M-9`, `6.6`. `DISP-M-6` and `DISP-M-9` both
list `A-08` in `related_register_ids`, and both carry only the delegated
specification-review approval — no human authority to propagate. `DISP-6-6`
("Seeded errors require isolation") relates `B-13` and `C-10` and likewise
carries only the delegated approval.

**Candidates I tested and rejected.** `PRODUCT_OWNER_DECISION` — "Appoint"
sounds like an appointing authority, and appointing a person is arguably a
management act. I rejected it because the contract's mechanism for
"this named person commits to owning this" is exactly `NAMED_OWNER_COMMITMENT`,
which the row carries; requiring a product-owner decision in addition would
double-count the same act, and no comparable row in the ledger pairs the two.
`SECURITY_EXCEPTION` — the clause mandates prompt-injection coverage rather
than waiving a control; `security_exception_ids` is `[]`. `EXTERNAL_
COORDINATION_APPROVAL` — "repository location" is internal; no external party
is named.

**Transitions and fail-closed boundaries.** `approval_records` `[]`;
`blocked_scope` `[]`; no prohibition in the clause.

**Other `APPROVAL` inventory fields.** `human_review_id` `HR-0004`, projected
`["HR-0004"]`, inside the digest-pinned HR-0004 scope; HR-0004 is resolved, not
blocking.

**Conclusion.** `required_approvals` is complete for the A-08 clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `REG-A-08`'s `required_approvals` inventory is correct at the input bytes pinned
above.
