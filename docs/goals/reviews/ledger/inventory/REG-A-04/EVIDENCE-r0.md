# Inventory review — REG-A-04 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-A-04` |
| `review_type` | `EVIDENCE` |
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

`REG-A-04` has `kind == "register_row"`. Its `scope_derivation` reads exactly

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
exists to record. No `SCOPE` artifact was written for `REG-A-04`.

One consequence is worth stating rather than leaving implicit: the `SCOPE`
inventory projection (`validate_ledger_structural.py:293-305`) is the only
projection that covers `disposition_refs`, `gate_refs`, `activation_predicate`,
and `related_register_ids`. On a register row those fields are covered by the
**input** projection — so any mutation to them stales both reviews below — but
they are not the subject of a per-component semantic review, by contract. The
scope of a register row comes from the pinned v2 register itself.

## Reviewed inventory, exactly as read

`review_inventory_projection(row, "EVIDENCE")` — canonical JSON:

```json
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"e57f810850b4e4d969ddd00b06fc5855a724cec1e982d0eb1d83c4617f76949c","digest_mode":"UTF8_LINE_SPAN","end_line":34,"evidence_ref_id":"EV-REG-A-04-SOURCE","path":"docs/blueprint/funda-blueprint-implementation-decision-register-v2.md","scope":"Exact authoritative source occurrence for REG-A-04","start_line":34},{"captured_at":"2026-08-15T07:13:28Z","content_sha256":"9b14f5f327a9ff623cb41c823ab3eeec2d14f2f3ee05b8506313fbb28e83f458","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-REG-A-04-SPEC-DRAFT","path":"docs/specs/equity-os-s06-output-materiality-falsifiers.md","scope":"Current draft specification bytes for REG-A-04","start_line":null},{"captured_at":"2026-08-13T04:19:57Z","content_sha256":"9b14f5f327a9ff623cb41c823ab3eeec2d14f2f3ee05b8506313fbb28e83f458","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-REG-A-04-S06-I7-CURRENT-S06","path":"docs/specs/equity-os-s06-output-materiality-falsifiers.md","scope":"Exact current S06 bytes adjudicated for S06-I7 on REG-A-04","start_line":null},{"captured_at":"2026-08-13T04:19:57Z","content_sha256":"61d74f4b8b9248a75ff48e4508b1b58fb79b884acbbc859328111bb3814f2113","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-REG-A-04-S06-I7-R4","path":"docs/goals/reviews/specs/equity-os-s04-s06-r4.md","scope":"Final ordinary r4 review report finding S06-I7 for REG-A-04","start_line":null},{"captured_at":"2026-08-13T04:19:57Z","content_sha256":"da3ef87f32646fdb3e0f576086aba5070eee0aee3b115f53cb6b40579999e26a","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-REG-A-04-S06-I7-ADJUDICATION","path":"docs/goals/reviews/specs/equity-os-s04-s06-adjudication.md","scope":"Post-cap adjudication upholding S06-I7 and its exact cone for REG-A-04","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: A provisional v0 exists before baseline; final contract after baseline includes event/cutoff, facts, changes, driver analysis, management ledger, thesis impact, observable falsifiers, open questions, calculations, memory draft, and approval record","evidence_id":"REQ-REG-A-04-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"REG-A-04 acceptance and delivery scope","status":"UNRESOLVED"},{"approval_ids":[],"description":"Persisted clean fresh Sol xhigh review of the current specification bytes","evidence_id":"REQ-REG-A-04-SPEC-REVIEW","evidence_ref_ids":[],"evidence_type":"REVIEW","proof_mode":"CONTENT_HASH","scope":"A-04 under S06: Freeze the first output contract","status":"UNRESOLVED"},{"approval_ids":["APR-REG-A-04-03"],"description":"Current ANALYST_ACCEPTANCE evidence from Responsible analyst","evidence_id":"REQ-REG-A-04-ANALYST_ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ANALYST","proof_mode":"TYPED_APPROVAL","scope":"A-04 under S06: Freeze the first output contract","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `4e145cff7e03a4f9c99120a5b1c91ff7ebaae305aa31619ca1a71e21c2b0b7a1`
- `reviewed_inventory_sha256` (pre-record): `398380d057f6e79e136505abccf78caba9b9d8a7e21eca844e54818026b029fa`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line
34, register ID `A-04`, title "Freeze the first output contract":

```text
| A-04 | Critical | Freeze the first output contract | A provisional v0 exists before baseline; final contract after baseline includes event/cutoff, facts, changes, driver analysis, management ledger, thesis impact, observable falsifiers, open questions, calculations, memory draft, and approval record | A-03 for final freeze | Open |
```

- `source_hash` recomputed over the whole pinned v2 register →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L34 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `e57f810850b4e4d969ddd00b06fc5855a724cec1e982d0eb1d83c4617f76949c`, matching the row and
  matching `EV-REG-A-04-SOURCE.content_sha256`.
- `required_acceptance_text` equals the source row's acceptance cell byte for
  byte, and `register_id`/`source_title` equal its ID and decision cells
  (checked by comparison, not by eye).
- Register `Status` cell: `Open`; `Priority`: `Critical`; `Dependencies`:
  `A-03 for final freeze`. Row `program_disposition`: `REQUIRED_NOW`; `delivery_status`:
  `REVIEW_BLOCKED`; `gate_result`: `NOT_EVALUATED`.

## Reasoning

**What this review decides.** Whether `required_evidence` on `REG-A-04`
enumerates every proof obligation the A-04 clause demands. All three items are
`UNRESOLVED` with empty `evidence_ref_ids`.

**The clause, restated from the bytes.** A-04 demands a provisional v0 output
contract before the baseline, and a final contract after the baseline
containing eleven named elements: event/cutoff, facts, changes, driver
analysis, management ledger, thesis impact, observable falsifiers, open
questions, calculations, memory draft, and approval record.
`required_acceptance_text`, the `ACCEPTANCE` description less its prefix, and
register line 34 agree byte for byte.

**Enumerated: three items.** `REQ-REG-A-04-ACCEPTANCE` (`ARTIFACT` /
`CONTENT_HASH`), `REQ-REG-A-04-SPEC-REVIEW` (`REVIEW` / `CONTENT_HASH`), and
`REQ-REG-A-04-ANALYST_ACCEPTANCE` (`ANALYST` / `TYPED_APPROVAL`, paired to
`APR-REG-A-04-03`).

**The eleventh element is the interesting one.** The clause requires the final
contract to *contain* an "approval record". I checked whether that creates a
proof obligation this list omits. It does not, and the distinction matters:
"contains an approval record" is a structural property of the contract
artifact, covered by the `ARTIFACT` / `CONTENT_HASH` acceptance item; the
*authorities* whose decisions populate such a record are enumerated in
`required_approvals` (three of them on this row) and their proof travels on
those requirements' own `evidence_ref_ids` and `approval_records` entries
(`:1247-1257`). No third mechanism is missing.

**Product-owner decision, unpaired — checked.** `APR-REG-A-04-02` is a
`PRODUCT_OWNER_DECISION` with no paired evidence item. As on every one of the
23 such requirements ledger-wide, this is structural: `evidence_types`
(`:2095-2100`) has no product-owner member, and `PRODUCT_OWNER_DECISION` is a
`decision_approval_type` (`:1599-1601`) proven through a `HUMAN_RESOLUTION`-
sourced approval record. Not an omission.

**Five `evidence_refs`, and why three of them are *not* in
`required_evidence`.** This row carries `EV-REG-A-04-SOURCE`,
`EV-REG-A-04-SPEC-DRAFT`, and three S06-I7 objects:
`EV-REG-A-04-S06-I7-CURRENT-S06`, `-R4`, and `-ADJUDICATION`. All five were
re-hashed against current bytes this round and all five resolve. The three
S06-I7 objects are referenced from `open_findings[0].evidence_ref_ids`, not
from any `required_evidence` item — correctly. `required_evidence` is the list
of *obligations the source clause demands*; those three objects are the
persisted proof of an open blocking finding, which is a different ledger
mechanism. Treating them as unenumerated acceptance obligations would be a
category error, and linking them into an item would have to change item status
away from `UNRESOLVED` (`:2138-2143`).

**The open finding, and why it does not change this verdict.** `REG-A-04` is
`REVIEW_BLOCKED` with `review_round: 4` and one `OPEN_BLOCKING` finding, S06-I7
("Cross-record digest cycle", severity Important, disposition UPHELD, fix
`NOT_AUTHORIZED`), whose remediation needs rank-1 authority under HR-0001. That
blocks *advancement* of this row. It does not make the evidence inventory
incomplete: the finding is about S06's digest architecture, and its remedy
would change the specification, not add a proof obligation to A-04's register
clause. If it later does, the input digest changes and this review goes stale
by design.

**Executable proof.** `REG-A-04` is absent from
`EXPECTED_COMMAND_PROOF_COMPONENTS` (`:2635-2649`). Its clause is a contract
definition; its gate `PG-0A-06` demands only that "the provisional output
contract exists". No `COMMAND` obligation is demanded and none is enumerated.

**`verification_command`.** `mode` `UNRESOLVED`, no commands — consistent.

**Conclusion.** `required_evidence` is complete for the A-04 clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `REG-A-04`'s `required_evidence` inventory is correct at the input bytes pinned
above.
