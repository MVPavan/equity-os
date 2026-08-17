# Inventory review — REG-A-12 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-A-12` |
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

`REG-A-12` has `kind == "register_row"`. Its `scope_derivation` reads exactly

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
exists to record. No `SCOPE` artifact was written for `REG-A-12`.

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
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"4e9cb7daed4ca172ca22eb094d166ac559ab22d834bd645e0f4374fd7c4a81e1","digest_mode":"UTF8_LINE_SPAN","end_line":42,"evidence_ref_id":"EV-REG-A-12-SOURCE","path":"docs/blueprint/funda-blueprint-implementation-decision-register-v2.md","scope":"Exact authoritative source occurrence for REG-A-12","start_line":42},{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"96add3840a6ff8c6280a70a75242b20a1615e50e9a49236d1bd3636f7e22d9ba","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-REG-A-12-SPEC-DRAFT","path":"docs/specs/equity-os-s08-success-metrics-budgets-capacity.md","scope":"Current draft specification bytes for REG-A-12","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: Weekly builder/analyst capacity, target phase dates, monthly provider/model/infrastructure ceilings, maintenance allowance, and expected company coverage documented","evidence_id":"REQ-REG-A-12-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"REG-A-12 acceptance and delivery scope","status":"UNRESOLVED"},{"approval_ids":[],"description":"Persisted clean fresh Sol xhigh review of the current specification bytes","evidence_id":"REQ-REG-A-12-SPEC-REVIEW","evidence_ref_ids":[],"evidence_type":"REVIEW","proof_mode":"CONTENT_HASH","scope":"A-12 under S08: Define operating calendar, standing budget, and capacity","status":"UNRESOLVED"},{"approval_ids":["APR-REG-A-12-02"],"description":"Current BUDGET_APPROVAL evidence from Budget owner","evidence_id":"REQ-REG-A-12-BUDGET_APPROVAL","evidence_ref_ids":[],"evidence_type":"BUDGET","proof_mode":"TYPED_APPROVAL","scope":"A-12 under S08: Define operating calendar, standing budget, and capacity","status":"UNRESOLVED"},{"approval_ids":["APR-REG-A-12-03"],"description":"Current CAPACITY_COMMITMENT evidence from Capacity owner","evidence_id":"REQ-REG-A-12-CAPACITY_COMMITMENT","evidence_ref_ids":[],"evidence_type":"CAPACITY","proof_mode":"TYPED_APPROVAL","scope":"A-12 under S08: Define operating calendar, standing budget, and capacity","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `98cc1327091579efdc4f842a5ad7f15d6539bdf55417f23cb30df4259085637d`
- `reviewed_inventory_sha256` (pre-record): `bee96301d9f3914f47c3a31731f2f0c151bd444d5e15d7675b24c4ae4a24442b`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line
42, register ID `A-12`, title "Define operating calendar, standing budget, and capacity":

```text
| A-12 | High | Define operating calendar, standing budget, and capacity | Weekly builder/analyst capacity, target phase dates, monthly provider/model/infrastructure ceilings, maintenance allowance, and expected company coverage documented | A-01, A-02 | Open |
```

- `source_hash` recomputed over the whole pinned v2 register →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L42 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `4e9cb7daed4ca172ca22eb094d166ac559ab22d834bd645e0f4374fd7c4a81e1`, matching the row and
  matching `EV-REG-A-12-SOURCE.content_sha256`.
- `required_acceptance_text` equals the source row's acceptance cell byte for
  byte, and `register_id`/`source_title` equal its ID and decision cells
  (checked by comparison, not by eye).
- Register `Status` cell: `Open`; `Priority`: `High`; `Dependencies`:
  `A-01, A-02`. Row `program_disposition`: `REQUIRED_NOW`; `delivery_status`:
  `SPEC_DRAFT`; `gate_result`: `NOT_EVALUATED`.

## Reasoning

**What this review decides.** Whether `required_evidence` on `REG-A-12`
enumerates every proof obligation the A-12 clause demands. All four items are
`UNRESOLVED` with empty `evidence_ref_ids`.

**The clause, restated from the bytes.** A-12 demands five documented
quantities: weekly builder/analyst capacity, target phase dates, monthly
provider/model/infrastructure ceilings, maintenance allowance, and expected
company coverage. `required_acceptance_text`, the `ACCEPTANCE` description less
its prefix, and register line 42 agree byte for byte.

**Enumerated: four items — and this row is the only one in the batch carrying
two distinct typed-approval evidence items.** `REQ-REG-A-12-ACCEPTANCE`
(`ARTIFACT` / `CONTENT_HASH`), `REQ-REG-A-12-SPEC-REVIEW` (`REVIEW` /
`CONTENT_HASH`), `REQ-REG-A-12-BUDGET_APPROVAL` (`BUDGET` / `TYPED_APPROVAL`,
paired to `APR-REG-A-12-02`), and `REQ-REG-A-12-CAPACITY_COMMITMENT`
(`CAPACITY` / `TYPED_APPROVAL`, paired to `APR-REG-A-12-03`). The clause fuses
two different authorities' subject matter — money ("monthly
provider/model/infrastructure ceilings", "maintenance allowance") and people
("weekly builder/analyst capacity", "expected company coverage") — and the
inventory carries a typed item for each rather than collapsing them. Both are
in `human_evidence_types`, so `:2132-2133` forces `TYPED_APPROVAL` on both and
`:2134-2135` forces their nonempty `approval_ids`; both hold, and each points at
its own distinct approval.

**The fifth quantity, checked separately.** "target phase dates" belongs to
neither budget nor capacity cleanly — it is calendar. I tested whether a third
authority's evidence item is missing and concluded it is not: the calendar is
documented output, covered by the `ARTIFACT` / `CONTENT_HASH` acceptance item
that embeds the clause whole, and the closed `evidence_types` vocabulary
(`:2095-2100`) has no schedule or calendar member for a typed item to use.

**Executable proof.** `REG-A-12` is absent from
`EXPECTED_COMMAND_PROOF_COMPONENTS` (`:2635-2649`). The clause's operative verb
is "documented" — five quantities written down, not measured — so no reproducible
command is demanded. Its gate `PG-0A-07` ("operating capacity and standing
budget are documented") says the same thing and carries no approval of its own.

**Disposition source re-read.** `disposition_refs` are `M-8`, `T-1`, `T-2`.
`DISP-T-1` ("Operating budget and calendar disappeared") is the disposition
that created this row — "Add a separate row for weekly builder capacity, target
phase dates, monthly provider/model/infrastructure ceilings, analyst-review
capacity, and maintenance burden" — and its `related_register_ids` is exactly
`["A-12"]`. Its demands are carried by A-12's five acceptance quantities, and it adds no
proof obligation this inventory lacks.

**`evidence_refs` as read.** `EV-REG-A-12-SOURCE` (`UTF8_LINE_SPAN` L42-42,
digest equal to `text_digest`) and `EV-REG-A-12-SPEC-DRAFT` (`FILE_BYTES` over
the S08 spec, `captured_at` 2026-08-13T02:49:11Z — not re-captured by HR-0004,
and verifying against current bytes). Both re-hashed; both resolve.

**`verification_command`.** `mode` `UNRESOLVED`, no commands — consistent.

**Conclusion.** `required_evidence` is complete for the A-12 clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `REG-A-12`'s `required_evidence` inventory is correct at the input bytes pinned
above.
