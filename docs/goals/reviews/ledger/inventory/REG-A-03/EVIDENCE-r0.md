# Inventory review — REG-A-03 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-A-03` |
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

`REG-A-03` has `kind == "register_row"`. Its `scope_derivation` reads exactly

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
exists to record. No `SCOPE` artifact was written for `REG-A-03`.

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
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"04cb3973d777cf5475b28b28ce15a8433bdb66564419b2a1b960659644bf7c0e","digest_mode":"UTF8_LINE_SPAN","end_line":33,"evidence_ref_id":"EV-REG-A-03-SOURCE","path":"docs/blueprint/funda-blueprint-implementation-decision-register-v2.md","scope":"Exact authoritative source occurrence for REG-A-03","start_line":33},{"captured_at":"2026-08-15T07:13:28Z","content_sha256":"3f3e371f7a71683c3befed5e6f0d6daff4bd2a5f630ad4aa9b62c31b1070885e","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-REG-A-03-SPEC-DRAFT","path":"docs/specs/equity-os-s05-discovery-company-vertical-slice.md","scope":"Current draft specification bytes for REG-A-03","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: Quarter 0 is completed manually with time-stamped reading, source location, verification, calculation, drafting, and approval; the same lightweight instrumentation is used in manual and assisted workflows and its overhead is recorded","evidence_id":"REQ-REG-A-03-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"REG-A-03 acceptance and delivery scope","status":"UNRESOLVED"},{"approval_ids":[],"description":"Persisted clean fresh Sol xhigh review of the current specification bytes","evidence_id":"REQ-REG-A-03-SPEC-REVIEW","evidence_ref_ids":[],"evidence_type":"REVIEW","proof_mode":"CONTENT_HASH","scope":"A-03 under S05: Define and perform the manual baseline workflow","status":"UNRESOLVED"},{"approval_ids":["APR-REG-A-03-02"],"description":"Current ANALYST_ACCEPTANCE evidence from Responsible analyst","evidence_id":"REQ-REG-A-03-ANALYST_ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ANALYST","proof_mode":"TYPED_APPROVAL","scope":"A-03 under S05: Define and perform the manual baseline workflow","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `6bcd0de47a66ccd258134a5b6261a74d34ae41f29c8307c8b25c226d00e76493`
- `reviewed_inventory_sha256` (pre-record): `28c8c9a57463b0b892a83d0dfe5d7c6107deb45e7aa5e88ae517f7f33ee68573`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line
33, register ID `A-03`, title "Define and perform the manual baseline workflow":

```text
| A-03 | Critical | Define and perform the manual baseline workflow | Quarter 0 is completed manually with time-stamped reading, source location, verification, calculation, drafting, and approval; the same lightweight instrumentation is used in manual and assisted workflows and its overhead is recorded | A-02, A-04 v0, A-10, A-13 | Open |
```

- `source_hash` recomputed over the whole pinned v2 register →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L33 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `04cb3973d777cf5475b28b28ce15a8433bdb66564419b2a1b960659644bf7c0e`, matching the row and
  matching `EV-REG-A-03-SOURCE.content_sha256`.
- `required_acceptance_text` equals the source row's acceptance cell byte for
  byte, and `register_id`/`source_title` equal its ID and decision cells
  (checked by comparison, not by eye).
- Register `Status` cell: `Open`; `Priority`: `Critical`; `Dependencies`:
  `A-02, A-04 v0, A-10, A-13`. Row `program_disposition`: `REQUIRED_NOW`; `delivery_status`:
  `SPEC_DRAFT`; `gate_result`: `NOT_EVALUATED`.

## Reasoning

**What this review decides.** Whether `required_evidence` on `REG-A-03`
enumerates every proof obligation the A-03 clause demands. All three items are
`UNRESOLVED` with empty `evidence_ref_ids`; this review does not change that.

**The clause, restated from the bytes.** A-03 demands that Quarter 0 be
*completed manually* with six named steps — time-stamped reading, source
location, verification, calculation, drafting, and approval — and that the same
lightweight instrumentation be used in manual and assisted workflows with its
overhead recorded. `required_acceptance_text`, the `ACCEPTANCE` description
(less its prefix), and register line 33 agree byte for byte.

**Enumerated: three items, and the third is the load-bearing one.**
`REQ-REG-A-03-ACCEPTANCE` (`ARTIFACT` / `CONTENT_HASH`);
`REQ-REG-A-03-SPEC-REVIEW` (`REVIEW` / `CONTENT_HASH`); and
`REQ-REG-A-03-ANALYST_ACCEPTANCE` (`ANALYST` / `TYPED_APPROVAL`,
`approval_ids: ["APR-REG-A-03-02"]`). The clause's sixth step is literally
"approval", and this row is one of only 13 in the ledger pairing an `ANALYST`
evidence item to an `ANALYST_ACCEPTANCE` requirement. `ANALYST` is in
`human_evidence_types`, so `:2132-2133` forces its `proof_mode` to
`TYPED_APPROVAL`, and `:2134-2135` forces the nonempty `approval_ids` — both
hold.

**The demand I probed hardest: "its overhead is recorded".** This is the one
clause in the batch that names a measurement, so I tested whether a
`COMMAND_RESULT` obligation is missing. It is not. The demand is that the
overhead of a *manually performed* Quarter 0 be recorded — a time-and-motion
record produced by a human performing the workflow, not a reproducible command;
`DISP-G-4`, one of this row's dispositions, says exactly that, "rely on
time-and-motion components, not only whole-report elapsed time". `REG-A-03` is
absent from the pinned `EXPECTED_COMMAND_PROOF_COMPONENTS` manifest
(`:2635-2649`), and the manifest is asserted to equal the actual set of rows
carrying a `COMMAND_RESULT` item, so adding one here would fail structural
validation outright. The recording obligation is inside the `ACCEPTANCE`
item's verbatim clause text, which is where the contract puts artifact-shaped
proof.

**Instrumentation symmetry, checked for double-counting.** "the same
lightweight instrumentation is used in manual and assisted workflows" also
appears as a control on `REG-B-13` ("instrumentation is symmetric and overhead
measured"). That is not a reason to drop it here: A-03's clause demands it of
the manual baseline it defines, B-13's demands it of the bias-control regime.
Each row carries the demand its own source makes; neither omits anything.

**Typed-approval demands beyond the analyst, checked.** The clause names one
approval step and one actor class. It does not name a budget owner, a domain
expert, or a named owner, and none of those types appears in the enumeration —
correctly.

**`evidence_refs` as read.** `EV-REG-A-03-SOURCE` (`UTF8_LINE_SPAN` L33-33,
digest equal to `text_digest`) and `EV-REG-A-03-SPEC-DRAFT` (`FILE_BYTES` over
the S05 spec). Both re-hashed this round and both resolve.

**`verification_command`.** `mode` `UNRESOLVED`, no commands. Consistent with a
row enumerating no `COMMAND` obligation.

**Conclusion.** `required_evidence` is complete for the A-03 clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `REG-A-03`'s `required_evidence` inventory is correct at the input bytes pinned
above.
