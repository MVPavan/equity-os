# Inventory review — REG-A-13 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-A-13` |
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

`REG-A-13` has `kind == "register_row"`. Its `scope_derivation` reads exactly

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
exists to record. No `SCOPE` artifact was written for `REG-A-13`.

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
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"2eabf45af26be8a946814f7d14194bf79955f1fd53dd91d9dad12e41a7441bf3","digest_mode":"UTF8_LINE_SPAN","end_line":43,"evidence_ref_id":"EV-REG-A-13-SOURCE","path":"docs/blueprint/funda-blueprint-implementation-decision-register-v2.md","scope":"Exact authoritative source occurrence for REG-A-13","start_line":43},{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"96add3840a6ff8c6280a70a75242b20a1615e50e9a49236d1bd3636f7e22d9ba","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-REG-A-13-SPEC-DRAFT","path":"docs/specs/equity-os-s08-success-metrics-budgets-capacity.md","scope":"Current draft specification bytes for REG-A-13","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: Versioned definitions and measurement methods for factual accuracy, citation correctness, numerical traceability, unsupported claims, analyst minutes, per-claim verification time, coverage capacity, latency, cost, failure/retry rate, and phase applicability","evidence_id":"REQ-REG-A-13-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"REG-A-13 acceptance and delivery scope","status":"UNRESOLVED"},{"approval_ids":[],"description":"Persisted clean fresh Sol xhigh review of the current specification bytes","evidence_id":"REQ-REG-A-13-SPEC-REVIEW","evidence_ref_ids":[],"evidence_type":"REVIEW","proof_mode":"CONTENT_HASH","scope":"A-13 under S08: Freeze success-metric contract","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `be4eb463a1ef3c3da33c16211c3ffcd8b3695c5c2b466ebeed2c2b8890cc34f9`
- `reviewed_inventory_sha256` (pre-record): `2cfe263d078f2c1859d402b2169272a6a250f09f35d563f05b64f913e1e538f5`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line
43, register ID `A-13`, title "Freeze success-metric contract":

```text
| A-13 | Critical | Freeze success-metric contract | Versioned definitions and measurement methods for factual accuracy, citation correctness, numerical traceability, unsupported claims, analyst minutes, per-claim verification time, coverage capacity, latency, cost, failure/retry rate, and phase applicability | A-01 | Open |
```

- `source_hash` recomputed over the whole pinned v2 register →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L43 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `2eabf45af26be8a946814f7d14194bf79955f1fd53dd91d9dad12e41a7441bf3`, matching the row and
  matching `EV-REG-A-13-SOURCE.content_sha256`.
- `required_acceptance_text` equals the source row's acceptance cell byte for
  byte, and `register_id`/`source_title` equal its ID and decision cells
  (checked by comparison, not by eye).
- Register `Status` cell: `Open`; `Priority`: `Critical`; `Dependencies`:
  `A-01`. Row `program_disposition`: `REQUIRED_NOW`; `delivery_status`:
  `SPEC_DRAFT`; `gate_result`: `NOT_EVALUATED`.

## Reasoning

**What this review decides.** Whether `required_evidence` on `REG-A-13`
enumerates every proof obligation the A-13 clause demands. Both items are
`UNRESOLVED` with empty `evidence_ref_ids`.

**The clause, restated from the bytes.** A-13 demands versioned definitions and
measurement methods for eleven metrics: factual accuracy, citation correctness,
numerical traceability, unsupported claims, analyst minutes, per-claim
verification time, coverage capacity, latency, cost, failure/retry rate, and
phase applicability. `required_acceptance_text`, the `ACCEPTANCE` description
less its prefix, and register line 43 agree byte for byte.

**Enumerated: two items only — the smallest inventory in this batch alongside
B-08 and B-13.** `REQ-REG-A-13-ACCEPTANCE` (`ARTIFACT` / `CONTENT_HASH`) and
`REQ-REG-A-13-SPEC-REVIEW` (`REVIEW` / `CONTENT_HASH`). Eleven metrics, two
obligations — so this row deserved the sharpest completeness test in the batch,
and I ran two.

**Test one: does "measurement methods" demand executable proof?** No, and the
distinction is the whole point of the clause. A-13 demands that each metric be
*defined* — units, procedure, phase applicability — not that any measurement be
taken. `DISP-T-2` ("Success metrics are scattered"), which relates exactly
`["A-13"]`, says so directly: "Create one versioned success-metric contract
covering definitions, units, measurement procedures, and phase applicability",
and closes "All phase gates should reference this contract." The measuring
happens at the gates and on the rows that consume the contract; the contract
itself is a document. Mechanically, `REG-A-13` is absent from the pinned
`EXPECTED_COMMAND_PROOF_COMPONENTS` manifest (`:2635-2649`), which is asserted
equal to the actual `COMMAND_RESULT`-bearing set, so a `COMMAND` item here
would fail structural validation.

**Test two: does any of the eleven metrics drag in a typed human authority?**
Three look like candidates — "analyst minutes" (analyst), "cost" (budget),
"coverage capacity" (capacity) — but each names a *quantity to be defined*, not
a commitment to be signed. The commitments themselves live where the register
puts them and carry the matching typed evidence items: A-07 for per-workflow
ceilings including analyst minutes, A-12 for standing budget and capacity.
A-13's own `required_approvals` accordingly names only the delegated reviewer
and a `PRODUCT_OWNER_DECISION`, and the latter has no representable evidence
type — `evidence_types` (`:2095-2100`) contains no product-owner member, and
`PRODUCT_OWNER_DECISION` is a `decision_approval_type` (`:1599-1601`) proven
through a `HUMAN_RESOLUTION`-sourced approval record. So the two-item inventory
is what a complete enumeration looks like on this row.

**`evidence_refs` as read.** `EV-REG-A-13-SOURCE` (`UTF8_LINE_SPAN` L43-43,
digest equal to `text_digest`) and `EV-REG-A-13-SPEC-DRAFT` (`FILE_BYTES` over
the S08 spec, `captured_at` 2026-08-13T02:49:11Z). Both re-hashed this round
against current bytes; both resolve. Note this row shares its spec draft object
path and digest with `REG-A-07` and `REG-A-12` — three register rows under S08
— which is expected, since `evidence_ref_id` uniqueness is global but paths and
digests may repeat.

**`verification_command`.** `mode` `UNRESOLVED`, no commands. Worth one remark:
because `DISP-T-2` says every phase gate should reference this contract, A-13's
downstream gates (`PG-0A-05`, `PG-1-10`) are where commands eventually attach —
not here.

**Conclusion.** `required_evidence` is complete for the A-13 clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `REG-A-13`'s `required_evidence` inventory is correct at the input bytes pinned
above.
