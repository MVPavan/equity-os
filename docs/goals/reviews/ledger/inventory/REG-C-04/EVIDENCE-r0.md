# Inventory review — REG-C-04 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-C-04` |
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

`REG-C-04` has `kind == "register_row"`. Its `scope_derivation.semantic_review` is `null`,
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
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"9c2355db291c7858879cffa1f6da8599dfed812b013a69d049a869d2d9f9002f","digest_mode":"UTF8_LINE_SPAN","end_line":75,"evidence_ref_id":"EV-REG-C-04-SOURCE","path":"docs/blueprint/funda-blueprint-implementation-decision-register-v2.md","scope":"Exact authoritative source occurrence for REG-C-04","start_line":75},{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"f1a60a20e24a0d2a457aa71f8d9006316ea461d237ea1faa054fc24176ba3dc4","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-REG-C-04-SPEC-DRAFT","path":"docs/specs/equity-os-s13-claim-schema-vocabulary-evidence.md","scope":"Current draft specification bytes for REG-C-04","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: Material observed/computed claims require direct source or calculation support; material inferences/forecasts require linked evidence, explicit assumptions, uncertainty, and correct labeling; contradiction and materiality reasoning are visible","evidence_id":"REQ-REG-C-04-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"REG-C-04 acceptance and delivery scope","status":"UNRESOLVED"},{"approval_ids":[],"description":"Persisted clean fresh Sol xhigh review of the current specification bytes","evidence_id":"REQ-REG-C-04-SPEC-REVIEW","evidence_ref_ids":[],"evidence_type":"REVIEW","proof_mode":"CONTENT_HASH","scope":"C-04 under S13: Implement materiality- and epistemic-class-aware claim validation","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (the recorder must recompute both after
its Phase A evidence append, per recording design r2 §3.4 — appending review evidence
mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `d397ea0869e014fa7709991b16b5541a5672241c87f9b9bcc622278f9a32410d`
- `reviewed_inventory_sha256` (pre-record): `d70733255fae533d4bbbb5f3eeb53482e8123b2160eb4beecccc527acbb4c549`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line 75, anchor
`C-04`, a row of the decision table whose header is at line 70,
inside `## C. Phase 1 — Evidence-grounded MVP` (line 68):

> | C-04 | Critical | Implement materiality- and epistemic-class-aware claim validation | Material observed/computed claims require direct source or calculation support; material inferences/forecasts require linked evidence, explicit assumptions, uncertainty, and correct labeling; contradiction and materiality reasoning are visible | A-10, B-06 | Open |

- `source_hash` recomputed over the whole register file →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L75 span (CRLF→LF, surrounding ASCII
  whitespace trimmed) → `9c2355db291c7858879cffa1f6da8599dfed812b013a69d049a869d2d9f9002f`, matching the row.
- `required_acceptance_text` is the 4th table cell ("Required evidence / acceptance") of
  that line; I compared it programmatically against the row's stored value, not by eye.
- The `Status` cell reads `Open`, matching the row's `source_status` and
  `activation_source_status`; `program_disposition` is `REQUIRED_NOW`.
- `EV-REG-C-04-SOURCE` is a `UTF8_LINE_SPAN` reference over exactly that one line
  (`start_line == end_line == 75`) and its `content_sha256` recomputes to the same
  digest; `EV-REG-C-04-SPEC-DRAFT` is a `FILE_BYTES` reference whose digest I recomputed
  against the current spec file. Both of the row's evidence objects resolve against
  current bytes.

## Reasoning

**What the clause demands.** Three conjuncts, all conditioned on
materiality. (a) "**Material** observed/computed claims require direct source or
calculation support." (b) "**material** inferences/forecasts require linked evidence,
explicit assumptions, uncertainty, and correct labeling" — four sub-requirements, not one.
(c) "contradiction and materiality reasoning are **visible**."

**What is enumerated.** Two obligations: `REQ-REG-C-04-ACCEPTANCE`
(`ARTIFACT`/`CONTENT_HASH`), verified byte-equal to
`"Current proof satisfying: " + required_acceptance_text` — so all four of (b)'s
sub-requirements, including the easily-dropped "correct labeling", are carried by name —
and `REQ-REG-C-04-SPEC-REVIEW` (`REVIEW`/`CONTENT_HASH`) over the S13 specification bytes.

**The candidate I took most seriously.** Both (a) and (b) are gated on claims "classified
as material", and materiality is `A-10`'s versioned policy — a row whose own acceptance
ends "validator test cases **approved**" and which consequently carries a
`COMMAND_RESULT` obligation. If any obligation were to leak onto `C-04`, this is the path
it would take. It does not leak: `C-04`'s demand is that the validator *enforce* whatever
the current policy says, while the policy's existence, versioning, and approved test cases
are `REG-A-10`'s enumerated obligations, and `A-10` is declared in this row's
`dependencies`. Importing `A-10`'s proofs here would double-count one obligation across
two rows; the completeness question for `C-04` is whether *its own* clause demands
anything unlisted, and it does not.

**Second candidate: "correct labeling".** Correctly labelling epistemic class is a domain
judgement in operation, which could suggest a `DOMAIN`/`TYPED_APPROVAL` item. The clause
demands that the labelling *be correct*, not that a domain expert sign off on this
component. The contrast within this same specification is instructive and shows the
inventory is not uniformly stripped: `B-12`, also owned by S13, says "addition approval"
outright and does carry a `DOMAIN`/`TYPED_APPROVAL` item backed by Vocabulary authority.
The difference between the two rows tracks the words in the register.

**No command obligation is missing.** "require", "are visible" are state-descriptive; the
clause contains no test, replay, or demonstration verb. `REG-C-04` is absent from
`EXPECTED_COMMAND_PROOF_COMPONENTS` (`validate_ledger_structural.py:2635-2649`). Its two
declared gates, `PG-1-01` ("all numerical claims classified as material under A-10 resolve
to a fact or calculation trace") and `PG-1-02` ("all factual claims classified as material
under A-10 resolve to the correct source location"), read like checkable universals — so I
read both rows rather than assuming. Neither carries a command obligation of its own, so
the phase-gate side of the derivation contributes nothing this list lacks.

**State.** Both items `UNRESOLVED`, empty refs; `verification_command` `UNRESOLVED`.
`human_review_id` is `null` and `REG-C-04` occurs zero times in the canonical human-review
artifact — both link directions agree. The L75 span and the S13 draft bytes both re-hash
to their recorded digests.

**Residuals.** None. The obligation list is complete against the clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition, and it satisfies no
evidence item. It records only that the component's `required_evidence` obligation list is
complete against its source clause at the input bytes pinned above; every item in it
remains `UNRESOLVED`.
