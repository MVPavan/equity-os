# Inventory review — REG-B-02 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-B-02` |
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

`REG-B-02` has `kind == "register_row"`. Its `scope_derivation.semantic_review` is `null`,
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
{"approval_records":[],"human_review_id":["HR-0004"],"required_approvals":[{"actor":null,"approval_id":"APR-REG-B-02-01","approval_type":"DELEGATED_ARTIFACT_APPROVAL","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Delegated fresh Sol xhigh specification reviewer","scope":"B-02 under S14: Produce three real incremental earnings updates","status":"UNRESOLVED","timestamp":null},{"actor":null,"approval_id":"APR-REG-B-02-02","approval_type":"ANALYST_ACCEPTANCE","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Responsible analyst","scope":"B-02 under S14: Produce three real incremental earnings updates","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (the recorder must recompute both after
its Phase A evidence append, per recording design r2 §3.4 — appending review evidence
mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `fb4f374e0f1bc365a419e07041ef219abc6b8c1b7954c2a96f00d15c77568188`
- `reviewed_inventory_sha256` (pre-record): `19a9b8f0b0566d115f0db0e49ae4690fea016e9a608a5b41db87787ffd1f7afa`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line 52, anchor
`B-02`, a row of the decision table whose header is at line 49,
inside `## B. Phase 0.5 — One company, four quarters: one baseline plus three assisted updates` (line 47):

> | B-02 | Critical | Produce three real incremental earnings updates | Quarters 1–3 each consume the approved preceding thesis and include sources, facts, changes, management ledger, thesis impact, falsifiers, calculations, open questions, and approval record | B-01, B-03–B-07, B-11–B-14 | Open |

- `source_hash` recomputed over the whole register file →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L52 span (CRLF→LF, surrounding ASCII
  whitespace trimmed) → `222ab622a106dce0c43496cdcc2ddf5caedd709407b50089c4593616338c7934`, matching the row.
- `required_acceptance_text` is the 4th table cell ("Required evidence / acceptance") of
  that line; I compared it programmatically against the row's stored value, not by eye.
- The `Status` cell reads `Open`, matching the row's `source_status` and
  `activation_source_status`; `program_disposition` is `REQUIRED_NOW`.
- `EV-REG-B-02-SOURCE` is a `UTF8_LINE_SPAN` reference over exactly that one line
  (`start_line == end_line == 52`) and its `content_sha256` recomputes to the same
  digest; `EV-REG-B-02-SPEC-DRAFT` is a `FILE_BYTES` reference whose digest I recomputed
  against the current spec file. Both of the row's evidence objects resolve against
  current bytes.

## Reasoning

**What authority the clause demands.** One, explicitly. The
acceptance text ends "...open questions, and **approval record**". An approval record is
the trace of a decision, and the decision here is a person's acceptance of an incremental
earnings update — the substance of the whole row.

**What is enumerated.** Two requirements. `APR-REG-B-02-01`,
`DELEGATED_ARTIFACT_APPROVAL`, for the S14 specification. And `APR-REG-B-02-02`,
`ANALYST_ACCEPTANCE`, required authority "Responsible analyst", same scope string, both
`UNRESOLVED` with null actor, timestamp, and record.

**Why `ANALYST_ACCEPTANCE` / "Responsible analyst" is the right and only reading.** The
goal's closed authority map (L564) allows `ANALYST_ACCEPTANCE` exactly one authority
string, "Responsible analyst", so once the type is right the authority is forced. The type
is right because the approval being recorded is acceptance of analytical output, and goal
L970-975 excludes analyst acceptance from what delegated approval can cover: "Delegation
does not include analyst acceptance... Only the competent real person or external
authority may supply those decisions." Had this row carried only the delegated
requirement, the delegated reviewer would have appeared to cover a decision the contract
reserves to a person.

**Independent cross-check against the gate.** `gate_refs` is `["PG-05-02"]` — "Quarter 0
manual baseline/bootstrap and three real assisted updates for Quarters 1–3 have been
produced and **reviewed**". I read that ledger row: it independently carries
`ANALYST_ACCEPTANCE` / "Responsible analyst" and nothing else. So the gate demands no
authority this row lacks, and the two levels of the program read the same authority out of
the same source text.

**The candidate I rejected.** "consume the approved preceding thesis" names an approval,
but not one `B-02` must obtain: for Quarter 1 the preceding thesis is approved under
`REG-A-11`; for Quarters 2–3 it is this row's own prior output, covered by the analyst
acceptance already enumerated. No third authority follows.

**Why no `PRODUCT_OWNER_DECISION`.** Twenty register rows carry one (22 requirements in
total), so I checked rather than assumed. The six carrying the plain "Product owner"
authority — `A-01`, `A-02`, `A-04`, `A-13`, `C-13`, `E-03` — each fix a product boundary, a
released contract, or whether a capability is in or out of the product; the fifteen
carrying "Product owner authorized to activate deferred blueprint scope" are all rows whose
register Status cell reads `Deferred`. `B-02`'s Status is `Open`, and it executes inside
the boundary `A-02` already set, using the contract `A-04` already froze; it decides
nothing about product scope.

**Rest of the projection.** `approval_records` `[]`, `security_exception_ids` `[]`,
`human_review_id` `["HR-0004"]` — a ledger-reconciliation resolution that by its own scope
text advances no delivery or gate state. The two requirements have distinct IDs and types,
so there is no duplicate `(component, type, authority, scope)` pair.

**Residuals.** None. The approval list is complete against the clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition, and grants no
non-delegated authority (goal L615-617). It records only that the component's
`required_approvals` obligation list is complete against its source clause at the input
bytes pinned above; every requirement in it remains `UNRESOLVED`.
