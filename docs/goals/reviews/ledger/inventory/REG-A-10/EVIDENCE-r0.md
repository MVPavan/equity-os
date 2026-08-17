# Inventory review — REG-A-10 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-A-10` |
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

`REG-A-10` has `kind == "register_row"`. Its `scope_derivation` reads exactly

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
exists to record. No `SCOPE` artifact was written for `REG-A-10`.

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
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"7ecbf2a586fe16f9fdf54abe1ace2e106a0d8907534b416fff417fe72952afb3","digest_mode":"UTF8_LINE_SPAN","end_line":40,"evidence_ref_id":"EV-REG-A-10-SOURCE","path":"docs/blueprint/funda-blueprint-implementation-decision-register-v2.md","scope":"Exact authoritative source occurrence for REG-A-10","start_line":40},{"captured_at":"2026-08-15T07:13:28Z","content_sha256":"9b14f5f327a9ff623cb41c823ab3eeec2d14f2f3ee05b8506313fbb28e83f458","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-REG-A-10-SPEC-DRAFT","path":"docs/specs/equity-os-s06-output-materiality-falsifiers.md","scope":"Current draft specification bytes for REG-A-10","start_line":null},{"captured_at":"2026-08-13T04:19:57Z","content_sha256":"9b14f5f327a9ff623cb41c823ab3eeec2d14f2f3ee05b8506313fbb28e83f458","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-REG-A-10-S06-I7-CURRENT-S06","path":"docs/specs/equity-os-s06-output-materiality-falsifiers.md","scope":"Exact current S06 bytes adjudicated for S06-I7 on REG-A-10","start_line":null},{"captured_at":"2026-08-13T04:19:57Z","content_sha256":"61d74f4b8b9248a75ff48e4508b1b58fb79b884acbbc859328111bb3814f2113","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-REG-A-10-S06-I7-R4","path":"docs/goals/reviews/specs/equity-os-s04-s06-r4.md","scope":"Final ordinary r4 review report finding S06-I7 for REG-A-10","start_line":null},{"captured_at":"2026-08-13T04:19:57Z","content_sha256":"da3ef87f32646fdb3e0f576086aba5070eee0aee3b115f53cb6b40579999e26a","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-REG-A-10-S06-I7-ADJUDICATION","path":"docs/goals/reviews/specs/equity-os-s04-s06-adjudication.md","scope":"Post-cap adjudication upholding S06-I7 and its exact cone for REG-A-10","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: Versioned policy combining quantitative magnitude, always-material categories, thesis relevance, source conflict/uncertainty, and coverage-specific overrides; validator test cases approved","evidence_id":"REQ-REG-A-10-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"REG-A-10 acceptance and delivery scope","status":"UNRESOLVED"},{"approval_ids":[],"description":"Persisted clean fresh Sol xhigh review of the current specification bytes","evidence_id":"REQ-REG-A-10-SPEC-REVIEW","evidence_ref_ids":[],"evidence_type":"REVIEW","proof_mode":"CONTENT_HASH","scope":"A-10 under S06: Define claim materiality policy","status":"UNRESOLVED"},{"approval_ids":["APR-REG-A-10-02"],"description":"Current DOMAIN_EXPERT_ACCEPTANCE evidence from Equity-research domain expert","evidence_id":"REQ-REG-A-10-DOMAIN_EXPERT_ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"DOMAIN","proof_mode":"TYPED_APPROVAL","scope":"A-10 under S06: Define claim materiality policy","status":"UNRESOLVED"},{"approval_ids":[],"description":"Reproducible command result proving the current REG-A-10 acceptance obligation","evidence_id":"REQ-REG-A-10-COMMAND-PROOF","evidence_ref_ids":[],"evidence_type":"COMMAND_RESULT","proof_mode":"COMMAND","scope":"REG-A-10 command proof","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `d1135bb52f42d52483cd00671492a5687ea247c52a4c106febe888d3956bbcbb`
- `reviewed_inventory_sha256` (pre-record): `1864ca9bbf2d8c93dc5636851e1518339d6ec3aa275a2050b940941440f8349f`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line
40, register ID `A-10`, title "Define claim materiality policy":

```text
| A-10 | Critical | Define claim materiality policy | Versioned policy combining quantitative magnitude, always-material categories, thesis relevance, source conflict/uncertainty, and coverage-specific overrides; validator test cases approved | A-01, A-02 | Open |
```

- `source_hash` recomputed over the whole pinned v2 register →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L40 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `7ecbf2a586fe16f9fdf54abe1ace2e106a0d8907534b416fff417fe72952afb3`, matching the row and
  matching `EV-REG-A-10-SOURCE.content_sha256`.
- `required_acceptance_text` equals the source row's acceptance cell byte for
  byte, and `register_id`/`source_title` equal its ID and decision cells
  (checked by comparison, not by eye).
- Register `Status` cell: `Open`; `Priority`: `Critical`; `Dependencies`:
  `A-01, A-02`. Row `program_disposition`: `REQUIRED_NOW`; `delivery_status`:
  `REVIEW_BLOCKED`; `gate_result`: `NOT_EVALUATED`.

## Reasoning

**What this review decides.** Whether `required_evidence` on `REG-A-10`
enumerates every proof obligation the A-10 clause demands. All four items are
`UNRESOLVED` with empty `evidence_ref_ids`.

**The clause, restated from the bytes.** A-10 demands a versioned materiality
policy combining five inputs — quantitative magnitude, always-material
categories, thesis relevance, source conflict/uncertainty, and
coverage-specific overrides — and, separately, that "validator test cases
[be] approved". `required_acceptance_text`, the `ACCEPTANCE` description less
its prefix, and register line 40 agree byte for byte.

**Enumerated: four items — tied with `REG-A-12` for the largest inventory in
this batch.**
`REQ-REG-A-10-ACCEPTANCE` (`ARTIFACT` / `CONTENT_HASH`),
`REQ-REG-A-10-SPEC-REVIEW` (`REVIEW` / `CONTENT_HASH`),
`REQ-REG-A-10-DOMAIN_EXPERT_ACCEPTANCE` (`DOMAIN` / `TYPED_APPROVAL`, paired to
`APR-REG-A-10-02`), and `REQ-REG-A-10-COMMAND-PROOF` (`COMMAND_RESULT` /
`COMMAND`, scope "REG-A-10 command proof").

**The clause's two-part tail is exactly matched, and that is the point.**
"validator test cases approved" makes two demands at once — something
executable, and someone approving it — and the inventory carries one item for
each. The executable half is the `COMMAND_RESULT` item, and its presence is not
discretionary: `REG-A-10` is the first entry in the validator's pinned
`EXPECTED_COMMAND_PROOF_COMPONENTS` manifest (`:2635-2649`), which is asserted
equal to the actual set of `COMMAND_RESULT`-bearing rows, so this row must carry
it. `COMMAND_RESULT` forces `proof_mode == COMMAND` (`:2130-2131`), which the
item satisfies. The approving half is the `DOMAIN` item, whose `scope` is the
whole row scope, "A-10 under S06: Define claim materiality policy" — so it
covers the test cases as well as the policy, and no separate approval-of-test-
cases obligation is missing.

**Five `evidence_refs`, three of them finding evidence.**
`EV-REG-A-10-SOURCE`, `EV-REG-A-10-SPEC-DRAFT`, and the S06-I7 trio
`-CURRENT-S06`, `-R4`, `-ADJUDICATION`. All five re-hashed against current
bytes this round; all five resolve. As on `REG-A-04`, the trio is referenced
from `open_findings[0].evidence_ref_ids` and deliberately not from any
`required_evidence` item: it proves an open blocking finding, not an acceptance
obligation, and linking it into an item would force that item off `UNRESOLVED`
(`:2138-2143`).

**The open finding.** `REG-A-10` is `REVIEW_BLOCKED`, `review_round: 4`, with
the same `OPEN_BLOCKING` S06-I7 finding as `REG-A-04` (UPHELD, fix
`NOT_AUTHORIZED`, rank-1 authority required under HR-0001). It blocks
advancement, not the completeness of this enumeration; if remediation later
changes A-10's obligations, the input digest changes and this review stales by
design.

**`verification_command` — the one place this row has real forward work.**
`mode` is `UNRESOLVED` with an empty `commands` list. That matters more here
than on the other ten rows in this batch, because `REQ-REG-A-10-COMMAND-PROOF`
cannot ever reach `SATISFIED` without a registered command object and
`mode == COMMANDS`. That is a forward obligation on a pre-implementation row
(`gate_result` `NOT_EVALUATED`), and the goal admits `UNRESOLVED` during
initial ledger construction. The *obligation* is enumerated, which is what this
review audits.

**Dispositions re-read.** `G-1`, `G-5`, `R-4`, `6.2`. `DISP-G-5` ("Undefined
materiality") and `DISP-6-2` ("Materiality is not only a financial-statement
threshold") both list `A-10` and are the source of the five-input policy shape;
re-reading them I found no proof demand A-10's own clause does not already
carry.

**Conclusion.** `required_evidence` is complete for the A-10 clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `REG-A-10`'s `required_evidence` inventory is correct at the input bytes pinned
above.
