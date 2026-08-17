# Inventory review — REG-B-13 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-B-13` |
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

`review_inventory_projection(row, "EVIDENCE")` — canonical JSON:

```json
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"0f3c2de68cb37e48e56b3ebbec631268dd366e9e3ae85fb1dc387a1da94a2617","digest_mode":"UTF8_LINE_SPAN","end_line":63,"evidence_ref_id":"EV-REG-B-13-SOURCE","path":"docs/blueprint/funda-blueprint-implementation-decision-register-v2.md","scope":"Exact authoritative source occurrence for REG-B-13","start_line":63},{"captured_at":"2026-08-15T07:13:28Z","content_sha256":"5da8bf5f31e29833885d7e0bf74ecfc2a550fb9c24415ef5123fa47c938e2957","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-REG-B-13-SPEC-DRAFT","path":"docs/specs/equity-os-s07-golden-set-failure-reviewer-controls.md","scope":"Current draft specification bytes for REG-B-13","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: Quarter 0 is not reused for assisted work; instrumentation is symmetric and overhead measured; shadow-mode seeded-error drills cannot be promoted; false-accept/false-reject results are stratified by materiality and epistemic class; optional external spot review procedure defined","evidence_id":"REQ-REG-B-13-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"REG-B-13 acceptance and delivery scope","status":"UNRESOLVED"},{"approval_ids":[],"description":"Persisted clean fresh Sol xhigh review of the current specification bytes","evidence_id":"REQ-REG-B-13-SPEC-REVIEW","evidence_ref_ids":[],"evidence_type":"REVIEW","proof_mode":"CONTENT_HASH","scope":"B-13 under S07: Add reviewer-bias and measurement controls","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `e8c7a025e658d20589a135674e8268e8bdc3843c5678abb9a5a33b911b784bb7`
- `reviewed_inventory_sha256` (pre-record): `5cc7bac38b155f925405cc71c07f2aa62ce9d9122e362b879be32e9f022c0005`

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

**What this review decides.** Whether `required_evidence` on `REG-B-13`
enumerates every proof obligation the B-13 clause demands. Both items are
`UNRESOLVED` with empty `evidence_ref_ids`.

**The clause, restated from the bytes.** B-13 demands five controls: Quarter 0
is not reused for assisted work; instrumentation is symmetric and overhead
measured; shadow-mode seeded-error drills cannot be promoted;
false-accept/false-reject results are stratified by materiality and epistemic
class; and an optional external spot review procedure is defined.
`required_acceptance_text`, the `ACCEPTANCE` description less its prefix, and
register line 63 agree byte for byte. Phase 0.5 row.

**Enumerated: two items.** `REQ-REG-B-13-ACCEPTANCE` (`ARTIFACT` /
`CONTENT_HASH`) and `REQ-REG-B-13-SPEC-REVIEW` (`REVIEW` / `CONTENT_HASH`).
Five controls, two obligations — so I tested each control for a proof mode the
enumeration cannot carry.

**Control by control.** (1) "Quarter 0 is not reused for assisted work" is a
design constraint on the slice, provable by inspecting the specification.
(2) "instrumentation is symmetric and overhead measured" is the one that sounds
executable; I return to it below. (3) "shadow-mode seeded-error drills cannot
be promoted" is a fail-closed prohibition — a property of the promotion path's
design, provable by inspection, and `DISP-6-6` states it in exactly those terms
("prevent all promotion paths from touching them"). (4) "false-accept/
false-reject results are stratified by materiality and epistemic class" is a
reporting-shape requirement on the metrics definition. (5) "optional external
spot review procedure defined" demands that a procedure *be defined*, and the
word "optional" is in the source — the deliverable is the procedure document,
not an executed review.

**The executable question, resolved.** Control (2) demands measurement, so a
missing `COMMAND_RESULT` item was a live hypothesis. `REG-B-13` is absent from
the pinned `EXPECTED_COMMAND_PROOF_COMPONENTS` manifest (`:2635-2649`), which
is asserted equal to the actual `COMMAND_RESULT`-bearing set, so an item here
would fail structural validation. That pin is consistent with the source: the
symmetric-instrumentation demand originates in `DISP-G-4`, which asks for
"time-and-motion components" recorded during a manually performed baseline, and
the measurement it pairs with is A-03's manual Quarter 0 — a human record, not
a reproducible command. B-13's own demand is that the *control regime* be
specified.

**Where the controls come from, re-read.** `disposition_refs` are `M-6`, `M-9`,
`6.6`. `DISP-M-6` ("Reviewer and builder are the same person") lists `B-13` and
supplies controls (2)–(5), including "occasional external spot review where
practical". `DISP-6-6` ("Seeded errors require isolation") lists `B-13` and
supplies control (3). Both carry their own `required_evidence` on their own
rows; neither makes a demand of B-13 that B-13's clause omits.
*(Noted, outside this inventory: `DISP-M-9`'s `related_register_ids` is
`["A-08", "B-08"]` and does not include `B-13`, although `B-13` lists `M-9` in
`disposition_refs`. `disposition_refs` is covered by the `SCOPE` inventory
projection (`:293-305`), which a register row does not have, so it is outside
both inventories I am auditing and I take no finding on it.)*

**Security shape, checked.** Seeded-error drills and promotion prohibitions are
control language, so I tested for a missing `SECURITY` item. `SECURITY`
evidence attaches to an approved security *exception*; B-13 grants none and
`security_exception_ids` is `[]`.

**`evidence_refs` as read.** `EV-REG-B-13-SOURCE` (`UTF8_LINE_SPAN` L63-63,
digest equal to `text_digest`) and `EV-REG-B-13-SPEC-DRAFT` (`FILE_BYTES` over
the S07 spec, refreshed by HR-0004). Both re-hashed this round; both resolve.

**`verification_command`.** `mode` `UNRESOLVED`, no commands — consistent with
a row enumerating no `COMMAND` obligation.

**Conclusion.** `required_evidence` is complete for the B-13 clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `REG-B-13`'s `required_evidence` inventory is correct at the input bytes pinned
above.
