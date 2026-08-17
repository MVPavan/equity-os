# Inventory review — REG-A-02 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-A-02` |
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

`review_inventory_projection(row, "EVIDENCE")` — canonical JSON:

```json
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"7b498369713bdb18afd5bdd1a006949c382234dd04af65a7fe0e5f024bdb713a","digest_mode":"UTF8_LINE_SPAN","end_line":32,"evidence_ref_id":"EV-REG-A-02-SOURCE","path":"docs/blueprint/funda-blueprint-implementation-decision-register-v2.md","scope":"Exact authoritative source occurrence for REG-A-02","start_line":32},{"captured_at":"2026-08-15T07:13:28Z","content_sha256":"3f3e371f7a71683c3befed5e6f0d6daff4bd2a5f630ad4aa9b62c31b1070885e","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-REG-A-02-SPEC-DRAFT","path":"docs/specs/equity-os-s05-discovery-company-vertical-slice.md","scope":"Current draft specification bytes for REG-A-02","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: Quarter 0 is reserved for the manual baseline and bootstrap thesis; Quarters 1–3 are reserved for three assisted incremental updates; source package exists for all quarters and at least one management commitment can be tracked across periods","evidence_id":"REQ-REG-A-02-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"REG-A-02 acceptance and delivery scope","status":"UNRESOLVED"},{"approval_ids":[],"description":"Persisted clean fresh Sol xhigh review of the current specification bytes","evidence_id":"REQ-REG-A-02-SPEC-REVIEW","evidence_ref_ids":[],"evidence_type":"REVIEW","proof_mode":"CONTENT_HASH","scope":"A-02 under S05: Select one discovery company and four consecutive quarters","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `210dc8d0e73a77a0e50e2ad2a3fc008c78acd6992efbff84c763c2986f68a117`
- `reviewed_inventory_sha256` (pre-record): `3a95401df9b17b6bef13b88174395f4846cbf99a685d7bc2deec04b70181043f`

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

**What this review decides.** Whether `required_evidence` on `REG-A-02`
enumerates every proof obligation the A-02 register clause demands. It is not a
judgment that any proof exists: both items are `UNRESOLVED` with empty
`evidence_ref_ids`, which the validator requires of an unresolved item
(`validate_ledger_structural.py:2138-2139`), and this review changes neither.

**The clause, restated from the bytes.** A-02 demands a *slice selection*: one
discovery company, four consecutive quarters, with Quarter 0 reserved for the
manual baseline and bootstrap thesis, Quarters 1–3 reserved for three assisted
incremental updates, a source package existing for all four quarters, and at
least one management commitment trackable across periods. I compared
`required_acceptance_text` and the `ACCEPTANCE` item's `description` (less its
`Current proof satisfying: ` prefix) against register line 32 byte for byte;
all three agree, so nothing in the clause falls outside the enumerated
obligation's stated scope.

**Enumerated: two items.** `REQ-REG-A-02-ACCEPTANCE` (`ARTIFACT` /
`CONTENT_HASH`) carries the clause verbatim; `REQ-REG-A-02-SPEC-REVIEW`
(`REVIEW` / `CONTENT_HASH`, scope "A-02 under S05: Select one discovery company
and four consecutive quarters") carries the specification-review obligation
against S05.

**The one apparent gap, resolved.** `required_approvals` on this row carries
`APR-REG-A-02-02`, a `PRODUCT_OWNER_DECISION`, and no `required_evidence` item
is paired to it — unlike, say, `REG-A-03`'s `ANALYST` item. I checked whether
that is an omission and it is not, for two mechanical reasons. First, the
closed `evidence_types` vocabulary (`validate_ledger_structural.py:2095-2100`)
contains no product-owner type at all, so such an item is unrepresentable; the
13 `human_evidence_types` at `:2101-2105` that do force `TYPED_APPROVAL` are
the analyst/domain/provider/data-rights/legal/regulatory/budget/capacity/
named-owner/production/distribution/security/external-coordination set.
Second, `PRODUCT_OWNER_DECISION` is one of the two `decision_approval_types`
(`:1599-1601`), whose proof travels on the approval requirement's own
`evidence_ref_ids` and `matched_record_id` and on a `HUMAN_RESOLUTION`-sourced
`approval_records` entry (`:1247-1257`, `:1603-1615`) — the `APPROVAL`
inventory's business, not this one. I confirmed this is uniform rather than a
local accident: all 23 `PRODUCT_OWNER_DECISION` requirements across the 213-row
ledger are unpaired, as are all 123 `DELEGATED_ARTIFACT_APPROVAL` requirements
(the latter necessarily, since `:2135-2137` forbids `approval_ids` on a
non-`TYPED_APPROVAL` item, which is what the `CONTENT_HASH` spec-review item
is).

**Is executable proof demanded?** "source package exists for all quarters" and
"at least one management commitment can be tracked across periods" are
existence-and-traceability facts about a selected slice, provable by inspecting
the assembled package; neither states a reproducible measurement. `REG-A-02` is
absent from the validator's pinned `EXPECTED_COMMAND_PROOF_COMPONENTS` manifest
(`:2635-2649`), and its single phase gate `PG-0A-03` demands only that the
selection be made ("one discovery company and four consecutive quarters — one
baseline/bootstrap plus three assisted — are selected"), adding no measurement
obligation. So the absent `COMMAND_RESULT` item is consistent with both the
clause and the pinned manifest.

**Where the four-quarter shape comes from, and why it adds nothing here.** The
row's `disposition_refs` are `G-4`, `M-1`, `6.8`. `DISP-6-8` is the disposition
that replaced a three-quarter slice with four; `DISP-G-4` is the practice-effect
control. Both are separate ledger rows carrying their own `required_evidence`,
and re-reading their source text I found no proof demand that A-02's own clause
also makes and this row omits.

**`evidence_refs` as read.** Two objects, both re-hashed this round against
current bytes: `EV-REG-A-02-SOURCE` (`UTF8_LINE_SPAN` L32-32 of the pinned v2
register, `content_sha256` equal to the row's `text_digest`) and
`EV-REG-A-02-SPEC-DRAFT` (`FILE_BYTES` over the S05 spec, `captured_at`
2026-08-15T07:13:28Z, refreshed by the HR-0004 transaction). Both resolve.

**`verification_command`.** `mode` `UNRESOLVED`, no commands, no
`not_applicable_review`. Coherent with a row that enumerates no `COMMAND`
obligation and whose `gate_result` is `NOT_EVALUATED`.

**Conclusion.** `required_evidence` is complete for the A-02 clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `REG-A-02`'s `required_evidence` inventory is correct at the input bytes pinned
above.
