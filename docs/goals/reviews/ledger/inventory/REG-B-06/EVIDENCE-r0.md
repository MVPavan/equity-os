# Inventory review — REG-B-06 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-B-06` |
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

`REG-B-06` has `kind == "register_row"`. Its `scope_derivation.semantic_review` is `null`,
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
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"5110f0a367164462f071166fb4da6fc5636e783994a3d0a4a5482ea4376c54ad","digest_mode":"UTF8_LINE_SPAN","end_line":56,"evidence_ref_id":"EV-REG-B-06-SOURCE","path":"docs/blueprint/funda-blueprint-implementation-decision-register-v2.md","scope":"Exact authoritative source occurrence for REG-B-06","start_line":56},{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"f1a60a20e24a0d2a457aa71f8d9006316ea461d237ea1faa054fc24176ba3dc4","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-REG-B-06-SPEC-DRAFT","path":"docs/specs/equity-os-s13-claim-schema-vocabulary-evidence.md","scope":"Current draft specification bytes for REG-B-06","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: Subject, registered predicate, object, scope, horizon, epistemic class, confidence, materiality result/policy version, status, evidence direction, and supersession are represented","evidence_id":"REQ-REG-B-06-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"REG-B-06 acceptance and delivery scope","status":"UNRESOLVED"},{"approval_ids":[],"description":"Persisted clean fresh Sol xhigh review of the current specification bytes","evidence_id":"REQ-REG-B-06-SPEC-REVIEW","evidence_ref_ids":[],"evidence_type":"REVIEW","proof_mode":"CONTENT_HASH","scope":"B-06 under S13: Derive minimum typed claim schema","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (the recorder must recompute both after
its Phase A evidence append, per recording design r2 §3.4 — appending review evidence
mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `ad03edb5214d3d1525a2027773da11b8797a845e3dabe81b84ef300315e45428`
- `reviewed_inventory_sha256` (pre-record): `1d134f1caa3114003566ce9bcff94603abcfceaeb6202fe3c1b3915816b61f3c`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line 56, anchor
`B-06`, a row of the decision table whose header is at line 49,
inside `## B. Phase 0.5 — One company, four quarters: one baseline plus three assisted updates` (line 47):

> | B-06 | Critical | Derive minimum typed claim schema | Subject, registered predicate, object, scope, horizon, epistemic class, confidence, materiality result/policy version, status, evidence direction, and supersession are represented | A-10, B-12 | Open |

- `source_hash` recomputed over the whole register file →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L56 span (CRLF→LF, surrounding ASCII
  whitespace trimmed) → `5110f0a367164462f071166fb4da6fc5636e783994a3d0a4a5482ea4376c54ad`, matching the row.
- `required_acceptance_text` is the 4th table cell ("Required evidence / acceptance") of
  that line; I compared it programmatically against the row's stored value, not by eye.
- The `Status` cell reads `Open`, matching the row's `source_status` and
  `activation_source_status`; `program_disposition` is `REQUIRED_NOW`.
- `EV-REG-B-06-SOURCE` is a `UTF8_LINE_SPAN` reference over exactly that one line
  (`start_line == end_line == 56`) and its `content_sha256` recomputes to the same
  digest; `EV-REG-B-06-SPEC-DRAFT` is a `FILE_BYTES` reference whose digest I recomputed
  against the current spec file. Both of the row's evidence objects resolve against
  current bytes.

## Reasoning

**What the clause demands.** That eleven attributes — subject,
registered predicate, object, scope, horizon, epistemic class, confidence, materiality
result/policy version, status, evidence direction, and supersession — "are represented" in
a typed claim schema. Two of the eleven are not self-contained: "**registered** predicate"
presupposes a predicate registry, and "materiality result/**policy version**" presupposes a
versioned materiality policy.

**What is enumerated.** Two obligations: `REQ-REG-B-06-ACCEPTANCE`
(`ARTIFACT`/`CONTENT_HASH`), verified byte-equal to the prefixed
`required_acceptance_text` so all eleven attributes including both cross-referencing ones
survive, and `REQ-REG-B-06-SPEC-REVIEW` (`REVIEW`/`CONTENT_HASH`) over the S13
specification bytes.

**The candidate I took seriously.** Because "registered predicate" points at `B-12` and
"materiality result/policy version" points at `A-10`, and because `B-12` carries a
`DOMAIN`/`TYPED_APPROVAL` obligation (Vocabulary authority) while `A-10` carries a
`COMMAND_RESULT` obligation, one could argue `B-06` inherits proof duties from both. It
does not, and the distinction is precise: `B-06`'s clause demands that the schema *have a
field typed as a registered predicate* and *a field carrying a materiality policy
version*. It does not demand that the registry be approved or that the policy's test cases
pass — those are the acceptance obligations of `REG-B-12` and `REG-A-10`, where they are
in fact enumerated, and both are declared in this row's `dependencies` (`A-10`, `B-12`).
Re-deriving them here would make one real obligation appear twice in the inventory, which
the goal's approval side states as a rule — "One record satisfies at most one requirement;
one approval never implies another" (L188) — and which is no less wrong on the evidence
side.

**No command obligation is missing.** "are represented" is the same state-descriptive
construction as `C-07` ("are represented") and `C-09` ("are registered"), neither of which
carries a `COMMAND` item, and it contains no test, replay, or demonstration verb.
`REG-B-06` is absent from `EXPECTED_COMMAND_PROOF_COMPONENTS`
(`validate_ledger_structural.py:2635-2649`). Its declared gate `PG-05-07` ("minimum fact
and claim schemas are based on actual workflow evidence") carries no command obligation
either — I read that row rather than inferring it.

**A binding check specific to this row.** `human_review_id` is `null` here, unlike seven
of the ten rows in this batch. I searched the canonical human-review artifact and
`REG-B-06` occurs zero times in it, so the forward and reverse links agree and no
human-review-derived obligation is being concealed by a stale link. Both of the row's
evidence objects nonetheless resolve against current bytes: I recomputed the L56
`UTF8_LINE_SPAN` digest and the S13 `FILE_BYTES` digest and both match.

**Residuals.** None. The obligation list is complete against the clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition, and it satisfies no
evidence item. It records only that the component's `required_evidence` obligation list is
complete against its source clause at the input bytes pinned above; every item in it
remains `UNRESOLVED`.
