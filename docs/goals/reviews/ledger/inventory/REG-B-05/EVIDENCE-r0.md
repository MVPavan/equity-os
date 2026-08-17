# Inventory review — REG-B-05 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-B-05` |
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

`REG-B-05` has `kind == "register_row"`. Its `scope_derivation.semantic_review` is `null`,
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
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"cd82dea6900753366fd175f9c48ef2309a22744538509a7bb48e721da9fc5714","digest_mode":"UTF8_LINE_SPAN","end_line":55,"evidence_ref_id":"EV-REG-B-05-SOURCE","path":"docs/blueprint/funda-blueprint-implementation-decision-register-v2.md","scope":"Exact authoritative source occurrence for REG-B-05","start_line":55},{"captured_at":"2026-08-15T07:13:28Z","content_sha256":"61094a92688a7393eeedf99cd1a8759be874b5f9fd775374984d748c73d3376d","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-REG-B-05-SPEC-DRAFT","path":"docs/specs/equity-os-s12-observation-fact-identity-schema.md","scope":"Current draft specification bytes for REG-B-05","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: Schema supports raw/normalized values, dimensions, scope, source location, valid time, knowledge time, revisions, definition version, and quality/reconciliation status","evidence_id":"REQ-REG-B-05-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"REG-B-05 acceptance and delivery scope","status":"UNRESOLVED"},{"approval_ids":[],"description":"Persisted clean fresh Sol xhigh review of the current specification bytes","evidence_id":"REQ-REG-B-05-SPEC-REVIEW","evidence_ref_ids":[],"evidence_type":"REVIEW","proof_mode":"CONTENT_HASH","scope":"B-05 under S12: Derive minimum source and fact schemas from actual use","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (the recorder must recompute both after
its Phase A evidence append, per recording design r2 §3.4 — appending review evidence
mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `b1b09bb02b11042f3a7926744efaa858444f72509bc983f1e9568d1c23cd4f74`
- `reviewed_inventory_sha256` (pre-record): `56d7d4600bf7a32a68c9df02c8bc31b658f9ca77fb9cf8715220c1acc45aaf62`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line 55, anchor
`B-05`, a row of the decision table whose header is at line 49,
inside `## B. Phase 0.5 — One company, four quarters: one baseline plus three assisted updates` (line 47):

> | B-05 | Critical | Derive minimum source and fact schemas from actual use | Schema supports raw/normalized values, dimensions, scope, source location, valid time, knowledge time, revisions, definition version, and quality/reconciliation status | A-06, B-11, B-12 | Open |

- `source_hash` recomputed over the whole register file →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L55 span (CRLF→LF, surrounding ASCII
  whitespace trimmed) → `cd82dea6900753366fd175f9c48ef2309a22744538509a7bb48e721da9fc5714`, matching the row.
- `required_acceptance_text` is the 4th table cell ("Required evidence / acceptance") of
  that line; I compared it programmatically against the row's stored value, not by eye.
- The `Status` cell reads `Open`, matching the row's `source_status` and
  `activation_source_status`; `program_disposition` is `REQUIRED_NOW`.
- `EV-REG-B-05-SOURCE` is a `UTF8_LINE_SPAN` reference over exactly that one line
  (`start_line == end_line == 55`) and its `content_sha256` recomputes to the same
  digest; `EV-REG-B-05-SPEC-DRAFT` is a `FILE_BYTES` reference whose digest I recomputed
  against the current spec file. Both of the row's evidence objects resolve against
  current bytes.

## Reasoning

**What the clause demands.** One thing, ten times over: that a
schema *supports* raw/normalized values, dimensions, scope, source location, valid time,
knowledge time, revisions, definition version, and quality/reconciliation status. Every
conjunct is a structural capability of a schema document. Nothing in the clause is an
event, an execution, or a decision.

**What is enumerated.** Two obligations, which is the minimum a spec-owned register row
can carry: `REQ-REG-B-05-ACCEPTANCE` (`ARTIFACT`/`CONTENT_HASH`), byte-equal to
`"Current proof satisfying: " + required_acceptance_text` so all ten capabilities are
carried, and `REQ-REG-B-05-SPEC-REVIEW` (`REVIEW`/`CONTENT_HASH`) over the S12
specification bytes.

**Is a third obligation missing? The typed-approval candidate.** This is the question
that matters on a two-item row. `B-05` is a *data* schema, and its S12 sibling `B-03`
("Establish source-of-truth matrix") does carry a `DOMAIN`/`TYPED_APPROVAL` item backed by
`DOMAIN_EXPERT_ACCEPTANCE` / "Data-domain authority". If a data-domain sign-off were
implicit in schema work generally, it would be missing here. It is not implicit: the
discriminator is in the source text. `B-03`'s acceptance column begins "**Approved**
authority table"; `B-05`'s says "Schema **supports**". No approval word appears in `B-05`,
and the goal makes inventing one expensive rather than merely wrong — L556-558 warns that
a second string for an authority that already has one is "a permanent trap", and L551-554
forbids collapsing an unrepresented authority into a nearby type. An obligation must be
recovered from the clause, not supplied by analogy to a neighbour.

**No command obligation is missing.** "supports" is a state predicate over a document,
not a test verb. I checked this against the register rather than against the manifest
alone: every one of the ten register rows in `EXPECTED_COMMAND_PROOF_COMPONENTS` contains
explicit test, replay, or execution language — "tested" (`B-01`, `B-11`, `C-17`, `E-10`),
"tests insert and reject" (`C-15`), "test cases approved" (`A-10`), "pass tests" (`C-08`),
"replay exactly" / "reconstructs exactly" (`C-16`), "reproducible" (`E-01`), "succeed"
(`B-14`). Rows whose acceptance reads "are represented" (`B-06`, `C-07`), "are preserved"
(`C-02`), or "are registered" (`C-09`) carry none. `B-05` is
squarely in the second class, and the manifest agrees. The independent verb test and the
contract manifest give the same answer.

**On "from actual use" and the phase gates.** The decision column says "Derive minimum
source and fact schemas from **actual use**", and gate `PG-05-07` says the schemas must be
"based on actual workflow evidence". Both constrain the *provenance* of the schema, not
the number of proofs it needs — a provenance claim is established by the artifact and its
review. I read both declared gate rows, `PG-05-07` and `PG-1-03`; neither adds an
evidence obligation of its own kind that this row would have to mirror.

**State.** Both items `UNRESOLVED`, empty refs; `verification_command` `UNRESOLVED`.
The L55 source span and S12 draft bytes both re-hash to their recorded digests.

**Residuals.** None. The obligation list is complete against the clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition, and it satisfies no
evidence item. It records only that the component's `required_evidence` obligation list is
complete against its source clause at the input bytes pinned above; every item in it
remains `UNRESOLVED`.
