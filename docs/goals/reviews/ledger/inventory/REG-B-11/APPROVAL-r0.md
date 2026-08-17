# Inventory review — REG-B-11 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-B-11` |
| `review_type` | `APPROVAL` |
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

`review_inventory_projection(row, "APPROVAL")` — canonical JSON
(`validate_ledger_structural.py:292-318`, extracted by `ast` and executed in an isolated
namespace this round rather than transcribed):

```json
{"approval_records":[],"human_review_id":["HR-0004"],"required_approvals":[{"actor":null,"approval_id":"APR-REG-B-11-01","approval_type":"DELEGATED_ARTIFACT_APPROVAL","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Delegated fresh Sol xhigh specification reviewer","scope":"B-11 under S12: Specify fact identity, revision-family, and correction semantics","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (the recorder must recompute both after
its Phase A evidence append, per recording design r2 §3.4 — appending review evidence
mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `617ac3e10464b0904e5d93ed0d7364add2163ad326d106b0b683eaf59bb7de61`
- `reviewed_inventory_sha256` (pre-record): `ae0f2441c333a76d3b7a91b8eed2fa9f307c5ef78033dabc6f6077788c618a57`

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

**What authority the clause demands.** None. Five identity
concepts must be distinguished, five revision causes must have separate reasons, and
prior-period comparative handling must be tested. Every conjunct is a property of a model
or a test outcome; none is a decision reserved to a person or external body.

**What is enumerated.** One requirement, `APR-REG-B-11-01`,
`DELEGATED_ARTIFACT_APPROVAL`, scope "B-11 under S12: Specify fact identity,
revision-family, and correction semantics", `UNRESOLVED` with null actor, timestamp, and
`matched_record_id`. It is present because `primary_spec` is S12 and goal L957-968 records
the delegated spec approval as exactly this requirement.

**The candidate I took seriously.** One of the five revision causes this row must
distinguish is "**manual correction**" — a human act named in the source text. It creates
no approval obligation, and the distinction matters: the clause requires the system to be
able to *record* a manual correction as a distinct revision reason, not to obtain
anyone's sign-off before this row can be accepted. There is no type in the closed
vocabulary (goal L535-549) for "an operator performed a correction", and goal L551-554 is
explicit that where a register row does require an unrepresented authority, the vocabulary
"must be reconciled and explicitly approved... it may not be collapsed into a nearby
type." Mapping "manual correction" onto, say, `ANALYST_ACCEPTANCE` would be exactly that
prohibited collapse — and it would be unnecessary, because no authority is demanded here
at all.

**Gate cross-check.** `gate_refs` is `["PG-05-06"]` — "fact identity/revision rules and
metric/predicate registries are in use". I read that ledger row: `required_approvals` is
`[]`. This is worth stating precisely, because `PG-05-06` is shared with `B-12`, which
*does* carry a Vocabulary authority. The gate itself supplies no authority to either row;
`B-12`'s comes from its own clause ("addition approval"), and `B-11`'s clause contains no
such phrase. So `B-11` is not missing an authority by association with its gate-mate.

**Disposition cross-check.** `disposition_refs` is `["M-2"]`. I read `M-2` in the pinned
third-order disposition report: it prescribes a richer identity model — measurement key,
observation ID, revision family, revision reason — and names no approver anywhere. It
therefore adds no approval obligation, and under the register's own Authority rule
(register L23) it could not override the register wording if it did.

**Rest of the projection.** `approval_records` `[]`, `security_exception_ids` `[]`,
`human_review_id` `["HR-0004"]` — a `RECONCILE_AUTHORITY` reconciliation resolution whose
scope text states it advances no delivery or gate state, so it neither supplies nor
demands an approval on this row's content (goal L615-617).

**Residuals.** None. The approval list is complete against the clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition, and grants no
non-delegated authority (goal L615-617). It records only that the component's
`required_approvals` obligation list is complete against its source clause at the input
bytes pinned above; every requirement in it remains `UNRESOLVED`.
