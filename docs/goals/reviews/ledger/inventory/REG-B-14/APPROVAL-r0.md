# Inventory review — REG-B-14 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-B-14` |
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

`REG-B-14` has `kind == "register_row"`. Its `scope_derivation.semantic_review` is `null`,
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
{"approval_records":[],"human_review_id":["HR-0004"],"required_approvals":[{"actor":null,"approval_id":"APR-REG-B-14-01","approval_type":"DELEGATED_ARTIFACT_APPROVAL","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Delegated fresh Sol xhigh specification reviewer","scope":"B-14 under S14: Demonstrate human-feedback rework path","status":"UNRESOLVED","timestamp":null},{"actor":null,"approval_id":"APR-REG-B-14-02","approval_type":"ANALYST_ACCEPTANCE","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Responsible analyst","scope":"B-14 analyst acceptance","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (the recorder must recompute both after
its Phase A evidence append, per recording design r2 §3.4 — appending review evidence
mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `672f5b499492a0d4d3c3892614041c729f0a6fa153f6d0106781aea9cc4e7a41`
- `reviewed_inventory_sha256` (pre-record): `6fe2ab5819dfde7fcfe4d8e16ec3a557e7f81024e369f94bbd31274dd23a3d19`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line 64, anchor
`B-14`, a row of the decision table whose header is at line 49,
inside `## B. Phase 0.5 — One company, four quarters: one baseline plus three assisted updates` (line 47):

> | B-14 | Critical | Demonstrate human-feedback rework path | A rejected claim triggers the correct invalidation cascade; evidence package v(N+1) is created; only affected calculations/claims are rerun; prior package remains immutable; partial revalidation and reapproval succeed | B-01, B-11 | Open |

- `source_hash` recomputed over the whole register file →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L64 span (CRLF→LF, surrounding ASCII
  whitespace trimmed) → `a7cb881cbe7663596fd59dac8c546cb9a7abdcbfe62688078a375eeb4ef54aa1`, matching the row.
- `required_acceptance_text` is the 4th table cell ("Required evidence / acceptance") of
  that line; I compared it programmatically against the row's stored value, not by eye.
- The `Status` cell reads `Open`, matching the row's `source_status` and
  `activation_source_status`; `program_disposition` is `REQUIRED_NOW`.
- `EV-REG-B-14-SOURCE` is a `UTF8_LINE_SPAN` reference over exactly that one line
  (`start_line == end_line == 64`) and its `content_sha256` recomputes to the same
  digest; `EV-REG-B-14-SPEC-DRAFT` is a `FILE_BYTES` reference whose digest I recomputed
  against the current spec file. Both of the row's evidence objects resolve against
  current bytes.

## Reasoning

**What authority the clause demands.** One, at the end of the
acceptance text: "partial revalidation and **reapproval** succeed". The whole row is about
what happens after a human rejects a claim, so the authority that reapproves at the end of
the cascade is intrinsic to the clause rather than incidental to it.

**What is enumerated.** Two requirements. `APR-REG-B-14-01`,
`DELEGATED_ARTIFACT_APPROVAL`, scope "B-14 under S14: Demonstrate human-feedback rework
path". And `APR-REG-B-14-02`, `ANALYST_ACCEPTANCE`, required authority "Responsible
analyst", scope "**B-14 analyst acceptance**", both `UNRESOLVED`.

**Who reapproves, and why the type and authority are forced.** The rejection this row
exercises is a claim-level review rejection — analyst work — so the reapproval is analyst
acceptance. `ANALYST_ACCEPTANCE` admits exactly one authority string, "Responsible
analyst" (goal L564), so the type determines the authority with no discretion left. Goal
L970-975 independently forbids the delegated reviewer from covering analyst acceptance, so
the delegated requirement alone would have been an omission.

**The scope-string difference is deliberate and load-bearing.** Unlike every other
multi-requirement row in this batch, `B-14`'s two requirements carry *different* scope
strings — "B-14 under S14: Demonstrate human-feedback rework path" for the delegated one,
"B-14 analyst acceptance" for the analyst one. I checked that this is correct rather than
inconsistent: goal L610-613 requires a `SATISFIED` requirement to match one record with
identical type, authority, **scope**, actor, timestamp, evidence, and authority source,
and forbids one record from satisfying two requirements. Two distinct scope strings keep
the spec approval and the analyst reapproval separately matchable and make accidental
cross-satisfaction impossible. The matching evidence item
`REQ-REG-B-14-ANALYST_ACCEPTANCE-02` carries the same scope and names `APR-REG-B-14-02` in
its `approval_ids`, so the evidence and approval sides of the one real decision are bound
together.

**The candidate I rejected.** "A rejected claim triggers the correct invalidation cascade"
names a rejection, which is a decision. It generates no requirement here: the rejection is
the *input condition being demonstrated*, not an authorization this row must obtain before
it can be accepted. The authorization this row must obtain is the reapproval, and it is
enumerated.

**Gate cross-check.** `gate_refs` is `["PG-05-08"]` — "the rejected-claim rework path and
evidence-package versioning are demonstrated". I read that ledger row: `required_approvals`
is `[]`, so the gate demands no authority beyond what this row already declares.

**Rest of the projection.** `approval_records` `[]`, `security_exception_ids` `[]`,
`human_review_id` `["HR-0004"]` — reconciliation scope, advancing no delivery or gate
state. No duplicate `(component, type, authority, scope)` pair exists across the two
requirements.

**Residuals.** None. The approval list is complete against the clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition, and grants no
non-delegated authority (goal L615-617). It records only that the component's
`required_approvals` obligation list is complete against its source clause at the input
bytes pinned above; every requirement in it remains `UNRESOLVED`.
