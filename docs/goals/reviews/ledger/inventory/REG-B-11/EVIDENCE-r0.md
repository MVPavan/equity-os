# Inventory review — REG-B-11 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-B-11` |
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

`REG-B-11` has `kind == "register_row"`. Its `scope_derivation.semantic_review` is `null`,
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
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"2aef8528474171ab4baf42fde79bcab72a6d2db05e5b2a23fd709742bfb83254","digest_mode":"UTF8_LINE_SPAN","end_line":61,"evidence_ref_id":"EV-REG-B-11-SOURCE","path":"docs/blueprint/funda-blueprint-implementation-decision-register-v2.md","scope":"Exact authoritative source occurrence for REG-B-11","start_line":61},{"captured_at":"2026-08-15T07:13:28Z","content_sha256":"61094a92688a7393eeedf99cd1a8759be874b5f9fd775374984d748c73d3376d","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-REG-B-11-SPEC-DRAFT","path":"docs/specs/equity-os-s12-observation-fact-identity-schema.md","scope":"Current draft specification bytes for REG-B-11","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: Source occurrence, extraction result, measurement key, revision family, and canonical selection are distinguished; issuer restatement, source correction, parser re-extraction, manual correction, and normalization-policy change have separate reasons; prior-period comparative handling is tested","evidence_id":"REQ-REG-B-11-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"REG-B-11 acceptance and delivery scope","status":"UNRESOLVED"},{"approval_ids":[],"description":"Persisted clean fresh Sol xhigh review of the current specification bytes","evidence_id":"REQ-REG-B-11-SPEC-REVIEW","evidence_ref_ids":[],"evidence_type":"REVIEW","proof_mode":"CONTENT_HASH","scope":"B-11 under S12: Specify fact identity, revision-family, and correction semantics","status":"UNRESOLVED"},{"approval_ids":[],"description":"Reproducible command result proving the current REG-B-11 acceptance obligation","evidence_id":"REQ-REG-B-11-COMMAND-PROOF","evidence_ref_ids":[],"evidence_type":"COMMAND_RESULT","proof_mode":"COMMAND","scope":"REG-B-11 command proof","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (the recorder must recompute both after
its Phase A evidence append, per recording design r2 §3.4 — appending review evidence
mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `617ac3e10464b0904e5d93ed0d7364add2163ad326d106b0b683eaf59bb7de61`
- `reviewed_inventory_sha256` (pre-record): `dd467d849cf3ca5763502106c666aded8811a2c92d909ec48b9915d8ea5b0360`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line 61, anchor
`B-11`, a row of the decision table whose header is at line 49,
inside `## B. Phase 0.5 — One company, four quarters: one baseline plus three assisted updates` (line 47):

> | B-11 | Critical | Specify fact identity, revision-family, and correction semantics | Source occurrence, extraction result, measurement key, revision family, and canonical selection are distinguished; issuer restatement, source correction, parser re-extraction, manual correction, and normalization-policy change have separate reasons; prior-period comparative handling is tested | A-06, B-12 | Open |

- `source_hash` recomputed over the whole register file →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L61 span (CRLF→LF, surrounding ASCII
  whitespace trimmed) → `2aef8528474171ab4baf42fde79bcab72a6d2db05e5b2a23fd709742bfb83254`, matching the row.
- `required_acceptance_text` is the 4th table cell ("Required evidence / acceptance") of
  that line; I compared it programmatically against the row's stored value, not by eye.
- The `Status` cell reads `Open`, matching the row's `source_status` and
  `activation_source_status`; `program_disposition` is `REQUIRED_NOW`.
- `EV-REG-B-11-SOURCE` is a `UTF8_LINE_SPAN` reference over exactly that one line
  (`start_line == end_line == 61`) and its `content_sha256` recomputes to the same
  digest; `EV-REG-B-11-SPEC-DRAFT` is a `FILE_BYTES` reference whose digest I recomputed
  against the current spec file. Both of the row's evidence objects resolve against
  current bytes.

## Reasoning

**What the clause demands.** Three groups, and they are not the
same kind of demand. (a) Five concepts "are **distinguished**" — source occurrence,
extraction result, measurement key, revision family, canonical selection. (b) Five
revision causes "have **separate reasons**" — issuer restatement, source correction,
parser re-extraction, manual correction, normalization-policy change. (c) "prior-period
comparative handling **is tested**". Group (c) is executable; (a) and (b) are structural.

**What is enumerated.** Three obligations: `REQ-REG-B-11-ACCEPTANCE`
(`ARTIFACT`/`CONTENT_HASH`), `REQ-REG-B-11-SPEC-REVIEW` (`REVIEW`/`CONTENT_HASH`), and
`REQ-REG-B-11-COMMAND-PROOF` (`COMMAND_RESULT`/`COMMAND`).

**The enumeration inside group (b) is the thing worth checking.** Both (a) and (b) are
lists whose value is their exact membership: a model that distinguishes four of the five
identity concepts, or that collapses "parser re-extraction" into "source correction",
would defeat the clause while still answering to a loosely worded obligation. I compared
`REQ-REG-B-11-ACCEPTANCE`'s description byte-for-byte against
`"Current proof satisfying: " + required_acceptance_text` and it is equal, so all five
identity concepts and all five revision reasons are carried by name. That list is also, by
construction, the `M-2` disposition's own model, which makes the verbatim carry
load-bearing rather than cosmetic.

**Why the command obligation is present and belongs.** Group (c) is the only explicit test
verb on the row, and it is enough on its own: `REG-B-11` is a member of the goal-owned
`EXPECTED_COMMAND_PROOF_COMPONENTS` manifest at
`validate_ledger_structural.py:2635-2649`, and `extract_goal_validators.py --check` exits
`0` at these bytes, so that membership is contract text. `REG-B-11` is one of the three
rows in this batch named in the program-level evidence review r0's Critical finding 2 as
lacking command evidence at the pre-HR-0004 bytes; the item now exists, so that finding is
closed here. As on `REG-B-01`, the command obligation is component-scoped rather than
attached to conjunct (c) alone, and `verification_command` remains `UNRESOLVED` — the
obligation is declared without yet declaring an argv, which goal L501-502 permits at this
stage.

**On the disposition reference.** `disposition_refs` is `["M-2"]`, and `M-2` ("Fact
identity and revision semantics") does prescribe a richer model. It adds no obligation
here for two reasons: the register's own Authority rule (register L23) states that "the
wording in this register is authoritative for implementation gates" and that "narrative
reviews explain rationale but do not override this register"; and, in fact, L61 already
carries `M-2`'s five revision reasons verbatim, so there is no gap between the narrative
and the gate to reconcile.

**No typed approval is missing.** "manual correction" names a human act, but as a
*revision reason the system must be able to record*, not as a sign-off gating this row's
acceptance. The closed evidence vocabulary has no type for "an operator performed a
correction", and inventing the nearest one would be the substitution the goal forbids.
Gate `PG-05-06` ("fact identity/revision rules and metric/predicate registries are in
use") carries no approval or typed-evidence obligation on its own row — read, not assumed.

**State.** Three items `UNRESOLVED`, empty refs. The L61 span and S12 draft bytes both
re-hash to their recorded digests.

**Residuals.** None. The obligation list is complete against the clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition, and it satisfies no
evidence item. It records only that the component's `required_evidence` obligation list is
complete against its source clause at the input bytes pinned above; every item in it
remains `UNRESOLVED`.
