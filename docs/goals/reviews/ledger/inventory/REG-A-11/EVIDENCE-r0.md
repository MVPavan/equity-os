# Inventory review — REG-A-11 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-A-11` |
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

`REG-A-11` has `kind == "register_row"`. Its `scope_derivation` reads exactly

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
exists to record. No `SCOPE` artifact was written for `REG-A-11`.

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
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"9af11ddc3b29bd8392d49888e9071c80e0f97f5ca9e75fad595a849af4ad797b","digest_mode":"UTF8_LINE_SPAN","end_line":41,"evidence_ref_id":"EV-REG-A-11-SOURCE","path":"docs/blueprint/funda-blueprint-implementation-decision-register-v2.md","scope":"Exact authoritative source occurrence for REG-A-11","start_line":41},{"captured_at":"2026-08-15T07:13:28Z","content_sha256":"3f3e371f7a71683c3befed5e6f0d6daff4bd2a5f630ad4aa9b62c31b1070885e","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-REG-A-11-SPEC-DRAFT","path":"docs/specs/equity-os-s05-discovery-company-vertical-slice.md","scope":"Current draft specification bytes for REG-A-11","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: Using Quarter 0, a concise initial thesis, assumptions, management commitments, risks, open questions, and observable falsifiers are manually written, approved, versioned, and available before Quarter 1; full initiation remains deferred","evidence_id":"REQ-REG-A-11-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"REG-A-11 acceptance and delivery scope","status":"UNRESOLVED"},{"approval_ids":[],"description":"Persisted clean fresh Sol xhigh review of the current specification bytes","evidence_id":"REQ-REG-A-11-SPEC-REVIEW","evidence_ref_ids":[],"evidence_type":"REVIEW","proof_mode":"CONTENT_HASH","scope":"A-11 under S05: Author and approve bootstrap thesis for the discovery company","status":"UNRESOLVED"},{"approval_ids":["APR-REG-A-11-02"],"description":"Current ANALYST_ACCEPTANCE evidence from Responsible analyst","evidence_id":"REQ-REG-A-11-ANALYST_ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ANALYST","proof_mode":"TYPED_APPROVAL","scope":"A-11 under S05: Author and approve bootstrap thesis for the discovery company","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `e9b0763723416d0642ab5b650b0b7a038552234bfe89818d01fc9a7308b855fa`
- `reviewed_inventory_sha256` (pre-record): `f9d98d469a95f96004c331e7ba7f4171e0ad9041f640f221bc50b9bb34f95265`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line
41, register ID `A-11`, title "Author and approve bootstrap thesis for the discovery company":

```text
| A-11 | Critical | Author and approve bootstrap thesis for the discovery company | Using Quarter 0, a concise initial thesis, assumptions, management commitments, risks, open questions, and observable falsifiers are manually written, approved, versioned, and available before Quarter 1; full initiation remains deferred | A-03 | Open |
```

- `source_hash` recomputed over the whole pinned v2 register →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L41 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `9af11ddc3b29bd8392d49888e9071c80e0f97f5ca9e75fad595a849af4ad797b`, matching the row and
  matching `EV-REG-A-11-SOURCE.content_sha256`.
- `required_acceptance_text` equals the source row's acceptance cell byte for
  byte, and `register_id`/`source_title` equal its ID and decision cells
  (checked by comparison, not by eye).
- Register `Status` cell: `Open`; `Priority`: `Critical`; `Dependencies`:
  `A-03`. Row `program_disposition`: `REQUIRED_NOW`; `delivery_status`:
  `SPEC_DRAFT`; `gate_result`: `NOT_EVALUATED`.

## Reasoning

**What this review decides.** Whether `required_evidence` on `REG-A-11`
enumerates every proof obligation the A-11 clause demands. All three items are
`UNRESOLVED` with empty `evidence_ref_ids`.

**The clause, restated from the bytes.** Using Quarter 0, a concise initial
thesis with assumptions, management commitments, risks, open questions, and
observable falsifiers must be manually written, approved, versioned, and
available before Quarter 1; full initiation remains deferred.
`required_acceptance_text`, the `ACCEPTANCE` description less its prefix, and
register line 41 agree byte for byte.

**Enumerated: three items.** `REQ-REG-A-11-ACCEPTANCE` (`ARTIFACT` /
`CONTENT_HASH`), `REQ-REG-A-11-SPEC-REVIEW` (`REVIEW` / `CONTENT_HASH`), and
`REQ-REG-A-11-ANALYST_ACCEPTANCE` (`ANALYST` / `TYPED_APPROVAL`, paired to
`APR-REG-A-11-02`). The clause contains an explicit "approved", and the typed
item is its enumerated proof.

**Four verbs, checked one at a time.** "manually written" and "versioned" are
artifact properties of the thesis document, covered by the `ARTIFACT` /
`CONTENT_HASH` acceptance item, which embeds the clause verbatim. "approved" is
the `ANALYST` typed item. "available before Quarter 1" is the one that needed
thought: it is a temporal ordering condition, and I checked whether a separate
sequencing proof obligation is missing. It is not — the condition is inside the
acceptance text the `ACCEPTANCE` item carries whole, and the ledger's
`sequence_clause` rows (all 11 of them) carry empty `related_register_ids`, so
sequencing is not modelled as a per-register-row cross-link that could have
been dropped here.

**"full initiation remains deferred" — a negative demand.** I tested whether
this creates an obligation to *prove absence*, the way `DISP-R-1` carries a
`REQ-...-NO-IMPLEMENTATION` item. It does not. The ledger's no-implementation-
proof mechanism is a closed map with exactly one entry,
`NO_IMPLEMENTATION_REQUIREMENT_MAP = {"DISP-R-1": [...]}` (`:2671-2673`), and
`REG-A-11` is `REQUIRED_NOW` with `source_status` `Open` — it is not a deferred
or rejected row. The deferral clause bounds A-11's scope; it does not add a
proof obligation to it. The ledger's 13 `first_release_deferral` rows are where
deferral itself is tracked.

**Executable proof.** `REG-A-11` is absent from
`EXPECTED_COMMAND_PROOF_COMPONENTS` (`:2635-2649`), and correctly so: authoring
and approving a thesis document is not a reproducible command. Its gate
`PG-05-01` demands only "the bootstrap thesis is approved".

**Disposition source re-read.** `disposition_refs` are `G-4`, `M-1`, `6.8`.
`DISP-M-1` ("Thesis cold start") is the disposition that created this row —
"create a concise analyst-authored bootstrap coverage thesis… Approve and
version it before the three later assisted updates" — and its
`related_register_ids` is exactly `["A-11"]`. Its demands map one-for-one onto
A-11's acceptance text, and it introduces no proof this inventory lacks.

**`evidence_refs` as read.** `EV-REG-A-11-SOURCE` (`UTF8_LINE_SPAN` L41-41,
digest equal to `text_digest`) and `EV-REG-A-11-SPEC-DRAFT` (`FILE_BYTES` over
the S05 spec, refreshed by HR-0004). Both re-hashed; both resolve.

**`verification_command`.** `mode` `UNRESOLVED`, no commands — consistent.

**Conclusion.** `required_evidence` is complete for the A-11 clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `REG-A-11`'s `required_evidence` inventory is correct at the input bytes pinned
above.
