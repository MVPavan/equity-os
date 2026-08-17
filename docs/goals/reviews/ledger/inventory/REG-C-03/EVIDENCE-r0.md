# Inventory review — REG-C-03 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-C-03` |
| `review_type` | `EVIDENCE` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `4fc94e50-8bc8-416d-b8e5-e7ce4ad128d0` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-16T13:54:44Z` |

Role binding: `CONTEXT.md` "Agent roles (harness-wide)" L137-139 binds `REVIEWER` to
Claude Opus 5 at high effort, in an agent and context independent of any `IMPLEMENTER`
that produced the reviewed content. The digest above is the `CONTEXT.md` bytes at review
time and is an immutable historical capture, never re-verified against later bytes
(`validate_ledger_structural.py:250-262`).

## Review types applicable to this component

`REG-C-03` has `kind == "register_row"`. Its `scope_derivation.semantic_review` is `null`,
which I verified on the row itself before writing: the contract fixes that null for a
register row (goal L208-211, mechanized at goal L2886
`assert derivation["semantic_review"] is None`), because a register row's scope comes from
the pinned v2 register itself. `validate_ledger_preimplementation.py:200-204` builds the
applicable check set as `APPROVAL` + `EVIDENCE` always and appends `SCOPE` only
`if row["kind"] != "register_row"`. This component therefore has exactly **two**
applicable reviews — `EVIDENCE` and `APPROVAL` — and no `SCOPE` artifact exists or should
exist for it.

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

Fresh validation at these exact bytes, run this round:
`python3 scripts/equity_os_blueprint/validate_ledger_structural.py --repo-root .` → exit `0`;
`python3 scripts/equity_os_blueprint/extract_goal_validators.py --check` → exit `0`, so the
structural validator's pinned manifests are the goal's own bytes, not a downstream
paraphrase of them.

## Reviewed inventory, exactly as read

`review_inventory_projection(row, "EVIDENCE")` — canonical JSON
(`validate_ledger_structural.py:292-318`, extracted by `ast` and executed in an isolated
namespace this round rather than transcribed):

```json
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"1b48f58b4525be293e1ae18d2e885e18c7b89f79859b7eb5c74e64bfb454916b","digest_mode":"UTF8_LINE_SPAN","end_line":74,"evidence_ref_id":"EV-REG-C-03-SOURCE","path":"docs/blueprint/funda-blueprint-implementation-decision-register-v2.md","scope":"Exact authoritative source occurrence for REG-C-03","start_line":74},{"captured_at":"2026-08-15T07:13:28Z","content_sha256":"61094a92688a7393eeedf99cd1a8759be874b5f9fd775374984d748c73d3376d","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-REG-C-03-SPEC-DRAFT","path":"docs/specs/equity-os-s12-observation-fact-identity-schema.md","scope":"Current draft specification bytes for REG-C-03","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: Restatements and conflicting observations are preserved; no silent overwrite; model follows B-11 identity semantics","evidence_id":"REQ-REG-C-03-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"REG-C-03 acceptance and delivery scope","status":"UNRESOLVED"},{"approval_ids":[],"description":"Persisted clean fresh Sol xhigh review of the current specification bytes","evidence_id":"REQ-REG-C-03-SPEC-REVIEW","evidence_ref_ids":[],"evidence_type":"REVIEW","proof_mode":"CONTENT_HASH","scope":"C-03 under S12: Implement append-only observation and revision model","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (the recorder must recompute both after
its Phase A evidence append, per recording design r2 §3.4 — appending review evidence
mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `90386f2504b54d30ee44a2c39bfbb1aa048f1143874e4bcbf2ebc050ed746410`
- `reviewed_inventory_sha256` (pre-record): `c42ad635093816b3d12e24e554ac0ba00e03e4428c0ac44b4405ed756a34a9a9`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line 74, anchor
`C-03`, a row of the decision table whose header is at line 70,
inside `## C. Phase 1 — Evidence-grounded MVP` (line 68):

> | C-03 | Critical | Implement append-only observation and revision model | Restatements and conflicting observations are preserved; no silent overwrite; model follows B-11 identity semantics | B-11 | Open |

- `source_hash` recomputed over the whole register file →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L74 span (CRLF→LF, surrounding ASCII
  whitespace trimmed) → `1b48f58b4525be293e1ae18d2e885e18c7b89f79859b7eb5c74e64bfb454916b`, matching the row.
- `required_acceptance_text` is the 4th table cell ("Required evidence / acceptance") of
  that line; I compared it programmatically against the row's stored value, not by eye.
- The `Status` cell reads `Open`, matching the row's `source_status` and
  `activation_source_status`; `program_disposition` is `REQUIRED_NOW`.
- `EV-REG-C-03-SOURCE` is a `UTF8_LINE_SPAN` reference over exactly that one line
  (`start_line == end_line == 74`) and its `content_sha256` recomputes to the same
  digest; `EV-REG-C-03-SPEC-DRAFT` is a `FILE_BYTES` reference whose digest I recomputed
  against the current spec file. Both of the row's evidence objects resolve against
  current bytes.

## Reasoning

**What the clause demands.** Three things, one of which is
negative and one of which is a cross-reference: restatements and conflicting observations
"are **preserved**"; "**no silent overwrite**"; and "model follows **B-11** identity
semantics".

**What is enumerated.** Two obligations: `REQ-REG-C-03-ACCEPTANCE`
(`ARTIFACT`/`CONTENT_HASH`), verified byte-equal to
`"Current proof satisfying: " + required_acceptance_text`, and
`REQ-REG-C-03-SPEC-REVIEW` (`REVIEW`/`CONTENT_HASH`) over the S12 specification bytes.

**The negative conjunct is the one that had to survive, and it did.** "no silent
overwrite" is a prohibition: proof against it must establish an absence, not a presence.
This is precisely the failure mode the program-level evidence-inventory review r0 found
elsewhere in this ledger (Critical finding 3, the thirteen `DEF-*` rows given positively
framed obligations that inverted a no-implementation boundary). Here the phrase is carried
verbatim into `REQ-REG-C-03-ACCEPTANCE`, so a proof offered against that item must also
establish that no silent overwrite occurs. Had the description read "Restatements and
conflicting observations are preserved" alone, I would have raised a completeness finding
rather than recorded `CLEAN`.

**The cross-reference imports no second obligation.** "model follows B-11 identity
semantics" is a conformance demand on this row and nothing more. `B-11`'s own identity
obligations — including its `COMMAND_RESULT` item for "prior-period comparative handling
is tested" — are enumerated on `REG-B-11`, and `B-11` is this row's sole declared
dependency. Re-deriving a command obligation here on the strength of the reference would
put one obligation on two rows.

**No command obligation is missing — and this is the closest call on the row.** "are
preserved" and "no silent overwrite" describe a store's behaviour, and a reviewer could
argue that an append-only guarantee is exactly the kind of thing a test proves. I record
the tension rather than hide it, and resolve it on the source: the clause contains no
test, replay, or demonstration verb, and its nearest structural sibling `C-02`
("Original files, URLs, timestamps, hashes, parser versions, extraction warnings, and
first-seen times **are preserved**") carries no command item either. `REG-C-03` is absent
from `EXPECTED_COMMAND_PROOF_COMPONENTS` (`validate_ledger_structural.py:2635-2649`), and
`extract_goal_validators.py --check` exits `0`, so that absence is the goal's own bytes.
Under the register's Authority rule (register L23) the register wording is what gates
implementation, and this wording asks for a preserved model, not a passing test.

**Gate cross-check.** `gate_refs` is `["PG-1-03"]` — "units, period, currency, statement
scope, and definition are explicit". I read that row; it carries no obligation of a kind
this list would have to mirror, and its subject (explicitness of measurement attributes)
is `B-05`/`B-11` schema territory rather than an extra proof duty on `C-03`.

**State.** Both items `UNRESOLVED`, empty refs; `verification_command` `UNRESOLVED`. The
L74 span and the S12 draft bytes both re-hash to their recorded digests.

**Residuals.** None. The obligation list is complete against the clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition, and it satisfies no
evidence item. It records only that the component's `required_evidence` obligation list is
complete against its source clause at the input bytes pinned above; every item in it
remains `UNRESOLVED`.
