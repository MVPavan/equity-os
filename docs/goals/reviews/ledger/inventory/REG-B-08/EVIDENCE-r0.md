# Inventory review — REG-B-08 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-B-08` |
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

`REG-B-08` has `kind == "register_row"`. Its `scope_derivation` reads exactly

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
exists to record. No `SCOPE` artifact was written for `REG-B-08`.

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
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"b220948438547a2bffb087722bdd82a848d1b9569122882ad41cbe26e808ac88","digest_mode":"UTF8_LINE_SPAN","end_line":58,"evidence_ref_id":"EV-REG-B-08-SOURCE","path":"docs/blueprint/funda-blueprint-implementation-decision-register-v2.md","scope":"Exact authoritative source occurrence for REG-B-08","start_line":58},{"captured_at":"2026-08-15T07:13:28Z","content_sha256":"5da8bf5f31e29833885d7e0bf74ecfc2a550fb9c24415ef5123fa47c938e2957","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-REG-B-08-SPEC-DRAFT","path":"docs/specs/equity-os-s07-golden-set-failure-reviewer-controls.md","scope":"Current draft specification bytes for REG-B-08","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: Extraction, reconciliation, source, unit, period, calculation, citation, inference, review, cutoff leakage, source-confusion, and document-as-instruction failures categorized","evidence_id":"REQ-REG-B-08-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"REG-B-08 acceptance and delivery scope","status":"UNRESOLVED"},{"approval_ids":[],"description":"Persisted clean fresh Sol xhigh review of the current specification bytes","evidence_id":"REQ-REG-B-08-SPEC-REVIEW","evidence_ref_ids":[],"evidence_type":"REVIEW","proof_mode":"CONTENT_HASH","scope":"B-08 under S07: Record failure taxonomy","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `b7b1dbc93b1905700e7673c44913f12ba0c7ec1c2c39d0cdf182c1c09f956ac7`
- `reviewed_inventory_sha256` (pre-record): `3511407ae0bbdf2e77b647475d1c6eafaa5841b98346568beaa1af714bd51dae`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line
58, register ID `B-08`, title "Record failure taxonomy":

```text
| B-08 | High | Record failure taxonomy | Extraction, reconciliation, source, unit, period, calculation, citation, inference, review, cutoff leakage, source-confusion, and document-as-instruction failures categorized | A-08 | Open |
```

- `source_hash` recomputed over the whole pinned v2 register →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L58 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `b220948438547a2bffb087722bdd82a848d1b9569122882ad41cbe26e808ac88`, matching the row and
  matching `EV-REG-B-08-SOURCE.content_sha256`.
- `required_acceptance_text` equals the source row's acceptance cell byte for
  byte, and `register_id`/`source_title` equal its ID and decision cells
  (checked by comparison, not by eye).
- Register `Status` cell: `Open`; `Priority`: `High`; `Dependencies`:
  `A-08`. Row `program_disposition`: `REQUIRED_NOW`; `delivery_status`:
  `SPEC_DRAFT`; `gate_result`: `NOT_EVALUATED`.

## Reasoning

**What this review decides.** Whether `required_evidence` on `REG-B-08`
enumerates every proof obligation the B-08 clause demands. Both items are
`UNRESOLVED` with empty `evidence_ref_ids`.

**The clause, restated from the bytes.** B-08 demands that twelve failure
classes be *categorized*: extraction, reconciliation, source, unit, period,
calculation, citation, inference, review, cutoff leakage, source-confusion, and
document-as-instruction. `required_acceptance_text`, the `ACCEPTANCE`
description less its prefix, and register line 58 agree byte for byte. This is
a Phase 0.5 row (`blueprint_phase` `0.5`), unlike the nine Phase 0A rows in
this batch.

**Enumerated: two items.** `REQ-REG-B-08-ACCEPTANCE` (`ARTIFACT` /
`CONTENT_HASH`) and `REQ-REG-B-08-SPEC-REVIEW` (`REVIEW` / `CONTENT_HASH`,
scope "B-08 under S07: Record failure taxonomy"). No typed-approval item, and
that is correct rather than an omission: `required_approvals` on this row
contains exactly one entry, the `DELEGATED_ARTIFACT_APPROVAL`, and
`:2135-2137` forbids `approval_ids` on a non-`TYPED_APPROVAL` item — so a
delegated approval structurally cannot have a paired evidence item. All 123
delegated requirements in the ledger are unpaired for the same reason.

**Does the clause demand executable proof?** The operative verb is
"categorized" — the deliverable is a taxonomy document. `REG-B-08` is absent
from the pinned `EXPECTED_COMMAND_PROOF_COMPONENTS` set (`:2635-2649`). Its
gate `PG-05-10` ("the first golden cases are automated or consistently
reviewable") does carry the automation question, but that gate is its own row
and its clause is about the golden cases, which are A-08's material, not about
the taxonomy. The two rows are related through `gate_refs`, and the executable
obligation is placed on `DISP-M-9`, which *is* in the pinned command-proof
manifest.

**The two most security-flavoured categories, checked.** "source-confusion" and
"document-as-instruction" are the tail of the twelve, and they come straight
from `DISP-M-9` ("Untrusted-document surface"), whose `related_register_ids`
includes `B-08`. I tested whether a `SECURITY`-typed evidence item is missing
and it is not: `SECURITY` evidence attaches to an approved security exception,
and this clause defines failure categories rather than waiving a control.
`security_exception_ids` is `[]`.

**Cross-row completeness, checked in the direction that could hide a gap.**
`REG-A-08` demands the first twenty labeled cases *including* prompt-injection
and source-confusion cases; `REG-B-08` demands those failure modes be
categorized; `REG-B-13` demands false-accept/false-reject stratification. Three
rows, three distinct obligations from three distinct clauses — no demand of
B-08's own clause is parked on a neighbour. *(Noted, outside this inventory:
`REG-B-08` lists `M-6` and `6.6` in `disposition_refs`, but `DISP-M-6`'s
`related_register_ids` is `["A-08", "B-13", "C-10"]` and `DISP-6-6`'s is
`["B-13", "C-10"]` — neither names `B-08`. `disposition_refs` lives in the
`SCOPE` inventory projection (`:293-305`), which a register row does not have,
so this is outside both inventories I am auditing and I take no finding on it.)*

**`evidence_refs` as read.** `EV-REG-B-08-SOURCE` (`UTF8_LINE_SPAN` L58-58,
digest equal to `text_digest`) and `EV-REG-B-08-SPEC-DRAFT` (`FILE_BYTES` over
the S07 spec, `captured_at` 2026-08-15T07:13:28Z, refreshed by HR-0004). Both
re-hashed; both resolve.

**`verification_command`.** `mode` `UNRESOLVED`, no commands — consistent.

**Conclusion.** `required_evidence` is complete for the B-08 clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `REG-B-08`'s `required_evidence` inventory is correct at the input bytes pinned
above.
