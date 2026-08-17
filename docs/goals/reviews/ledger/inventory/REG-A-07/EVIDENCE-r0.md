# Inventory review — REG-A-07 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-A-07` |
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

`REG-A-07` has `kind == "register_row"`. Its `scope_derivation` reads exactly

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
exists to record. No `SCOPE` artifact was written for `REG-A-07`.

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
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"0ca41b6dee0a54da6dbf1010859095e997a53b41886ce0736d125c0d05c33923","digest_mode":"UTF8_LINE_SPAN","end_line":37,"evidence_ref_id":"EV-REG-A-07-SOURCE","path":"docs/blueprint/funda-blueprint-implementation-decision-register-v2.md","scope":"Exact authoritative source occurrence for REG-A-07","start_line":37},{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"96add3840a6ff8c6280a70a75242b20a1615e50e9a49236d1bd3636f7e22d9ba","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-REG-A-07-SPEC-DRAFT","path":"docs/specs/equity-os-s08-success-metrics-budgets-capacity.md","scope":"Current draft specification bytes for REG-A-07","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: Ceilings or measurement rules for model cost, tool calls, latency, document volume, retries, and analyst minutes","evidence_id":"REQ-REG-A-07-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"REG-A-07 acceptance and delivery scope","status":"UNRESOLVED"},{"approval_ids":[],"description":"Persisted clean fresh Sol xhigh review of the current specification bytes","evidence_id":"REQ-REG-A-07-SPEC-REVIEW","evidence_ref_ids":[],"evidence_type":"REVIEW","proof_mode":"CONTENT_HASH","scope":"A-07 under S08: Define initial per-workflow budgets","status":"UNRESOLVED"},{"approval_ids":["APR-REG-A-07-02"],"description":"Typed BUDGET_APPROVAL proof for A-07 budget authorization","evidence_id":"REQ-REG-A-07-BUDGET_APPROVAL-02","evidence_ref_ids":[],"evidence_type":"BUDGET","proof_mode":"TYPED_APPROVAL","scope":"A-07 budget authorization","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `36c24551a0e8355e46332a32c570380f2f2db6096a2c6ceb9555430bae019ed5`
- `reviewed_inventory_sha256` (pre-record): `dfd996a024632d35559def409747075c3a6473a37abf67303e0b74ad6198db43`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line
37, register ID `A-07`, title "Define initial per-workflow budgets":

```text
| A-07 | High | Define initial per-workflow budgets | Ceilings or measurement rules for model cost, tool calls, latency, document volume, retries, and analyst minutes | A-13 | Open |
```

- `source_hash` recomputed over the whole pinned v2 register →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L37 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `0ca41b6dee0a54da6dbf1010859095e997a53b41886ce0736d125c0d05c33923`, matching the row and
  matching `EV-REG-A-07-SOURCE.content_sha256`.
- `required_acceptance_text` equals the source row's acceptance cell byte for
  byte, and `register_id`/`source_title` equal its ID and decision cells
  (checked by comparison, not by eye).
- Register `Status` cell: `Open`; `Priority`: `High`; `Dependencies`:
  `A-13`. Row `program_disposition`: `REQUIRED_NOW`; `delivery_status`:
  `SPEC_DRAFT`; `gate_result`: `NOT_EVALUATED`.

## Reasoning

**What this review decides.** Whether `required_evidence` on `REG-A-07`
enumerates every proof obligation the A-07 clause demands. All three items are
`UNRESOLVED` with empty `evidence_ref_ids`.

**The clause, restated from the bytes.** A-07 demands "Ceilings **or**
measurement rules" for six named dimensions: model cost, tool calls, latency,
document volume, retries, and analyst minutes. The disjunction is in the source
and matters — the clause is satisfied by defining rules, not by executing
measurements. `required_acceptance_text`, the `ACCEPTANCE` description less its
prefix, and register line 37 agree byte for byte.

**Enumerated: three items.** `REQ-REG-A-07-ACCEPTANCE` (`ARTIFACT` /
`CONTENT_HASH`), `REQ-REG-A-07-SPEC-REVIEW` (`REVIEW` / `CONTENT_HASH`), and
`REQ-REG-A-07-BUDGET_APPROVAL-02` (`BUDGET` / `TYPED_APPROVAL`, paired to
`APR-REG-A-07-02`). Six dimensions, three obligations — I checked that the
dimensions are covered collectively by the verbatim acceptance text rather than
needing one item each; the contract's unit of obligation is the clause, and the
`ACCEPTANCE` item embeds it whole.

**A naming irregularity, reported and dismissed as non-substantive.** This
row's typed item is `REQ-REG-A-07-BUDGET_APPROVAL-02`, carrying the approval's
`-02` suffix, whereas the structurally identical item on `REG-A-12` is
`REQ-REG-A-12-BUDGET_APPROVAL` without it. The validator constrains
`evidence_id` only to be a nonempty, ledger-unique string (`:2116-2119`), so
this is cosmetic. It is not a completeness defect and I am not recording it as
a finding, but a later reader comparing the two budget rows should not read the
difference as meaning anything.

**Is executable proof demanded?** This is the row where I pressed hardest,
because "measurement rules" for latency and retries sounds executable.
`REG-A-07` is absent from the pinned `EXPECTED_COMMAND_PROOF_COMPONENTS` set
(`:2635-2649`), which is asserted equal to the actual set of `COMMAND_RESULT`-
bearing rows — so a `COMMAND` item here would fail structural validation. That
pin is consistent with the clause: A-07 *defines* ceilings or rules; the phase
gate that demands the numbers actually be observable, `PG-1-10` ("cost,
latency, failures, and retries are visible"), is a Phase-1 gate carried on its
own ledger row, and A-07's `gate_result` is `NOT_EVALUATED`. Definition now,
observation at the gate.

**Capacity, checked and correctly absent.** "analyst minutes" is one of the six
dimensions, and analyst capacity is a `CAPACITY_COMMITMENT` matter — but on
`REG-A-12`, whose clause demands "Weekly builder/analyst capacity" and which
carries both `CAPACITY` and `BUDGET` typed items. A-07 sets a per-workflow
ceiling on analyst minutes; A-12 commits the standing capacity. Different
obligations, correctly separated, neither missing.

**`evidence_refs` as read.** `EV-REG-A-07-SOURCE` (`UTF8_LINE_SPAN` L37-37,
digest equal to `text_digest`) and `EV-REG-A-07-SPEC-DRAFT` (`FILE_BYTES` over
the S08 spec, `captured_at` 2026-08-13T02:49:11Z — note this row's spec draft
was *not* re-captured by the HR-0004 transaction, unlike the S05/S06/S07 rows
in this batch; the digest nonetheless verifies against current bytes, which is
what the validator requires). Both resolve.

**`verification_command`.** `mode` `UNRESOLVED`, no commands — consistent with
a row enumerating no `COMMAND` obligation.

**Conclusion.** `required_evidence` is complete for the A-07 clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `REG-A-07`'s `required_evidence` inventory is correct at the input bytes pinned
above.
