# Inventory review — REG-A-03 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-A-03` |
| `review_type` | `APPROVAL` |
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

`REG-A-03` has `kind == "register_row"`. Its `scope_derivation` reads exactly

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
exists to record. No `SCOPE` artifact was written for `REG-A-03`.

One consequence is worth stating rather than leaving implicit: the `SCOPE`
inventory projection (`validate_ledger_structural.py:293-305`) is the only
projection that covers `disposition_refs`, `gate_refs`, `activation_predicate`,
and `related_register_ids`. On a register row those fields are covered by the
**input** projection — so any mutation to them stales both reviews below — but
they are not the subject of a per-component semantic review, by contract. The
scope of a register row comes from the pinned v2 register itself.

## Reviewed inventory, exactly as read

`review_inventory_projection(row, "APPROVAL")` — canonical JSON:

```json
{"approval_records":[],"human_review_id":["HR-0004"],"required_approvals":[{"actor":null,"approval_id":"APR-REG-A-03-01","approval_type":"DELEGATED_ARTIFACT_APPROVAL","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Delegated fresh Sol xhigh specification reviewer","scope":"A-03 under S05: Define and perform the manual baseline workflow","status":"UNRESOLVED","timestamp":null},{"actor":null,"approval_id":"APR-REG-A-03-02","approval_type":"ANALYST_ACCEPTANCE","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Responsible analyst","scope":"A-03 under S05: Define and perform the manual baseline workflow","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `6bcd0de47a66ccd258134a5b6261a74d34ae41f29c8307c8b25c226d00e76493`
- `reviewed_inventory_sha256` (pre-record): `d935fc4052c89bf81afb527003bff40b87c77eb7ca66e951ac4996fd3c6f773d`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line
33, register ID `A-03`, title "Define and perform the manual baseline workflow":

```text
| A-03 | Critical | Define and perform the manual baseline workflow | Quarter 0 is completed manually with time-stamped reading, source location, verification, calculation, drafting, and approval; the same lightweight instrumentation is used in manual and assisted workflows and its overhead is recorded | A-02, A-04 v0, A-10, A-13 | Open |
```

- `source_hash` recomputed over the whole pinned v2 register →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L33 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `04cb3973d777cf5475b28b28ce15a8433bdb66564419b2a1b960659644bf7c0e`, matching the row and
  matching `EV-REG-A-03-SOURCE.content_sha256`.
- `required_acceptance_text` equals the source row's acceptance cell byte for
  byte, and `register_id`/`source_title` equal its ID and decision cells
  (checked by comparison, not by eye).
- Register `Status` cell: `Open`; `Priority`: `Critical`; `Dependencies`:
  `A-02, A-04 v0, A-10, A-13`. Row `program_disposition`: `REQUIRED_NOW`; `delivery_status`:
  `SPEC_DRAFT`; `gate_result`: `NOT_EVALUATED`.

## Reasoning

**What this review decides.** Whether `required_approvals` on `REG-A-03`
enumerates every authority the A-03 clause and its derivation sources demand.
Both requirements are `UNRESOLVED` with null actor/timestamp/record and empty
evidence refs.

**Source acceptance text.** A-03 is the strongest case in this batch for a
named authority, because the clause enumerates "approval" as one of the six
steps of the manual Quarter 0. The enumeration answers it: `APR-REG-A-03-02` is
`ANALYST_ACCEPTANCE` with authority `Responsible analyst`, the single string
the closed vocabulary permits for that type (`:2587`, goal L564). Its `scope`
string, "A-03 under S05: Define and perform the manual baseline workflow",
matches the row's spec binding.

**Dependencies.** The register cell reads `A-02, A-04 v0, A-10, A-13`. I
checked each for authority that ought to propagate. A-02 carries a
`PRODUCT_OWNER_DECISION`; A-04 carries `PRODUCT_OWNER_DECISION` and
`ANALYST_ACCEPTANCE`; A-10 carries `DOMAIN_EXPERT_ACCEPTANCE`; A-13 carries
`PRODUCT_OWNER_DECISION`. None of those propagates onto A-03: the contract
treats each row's approvals as that row's own obligation, and the goal is
explicit that "one record satisfies at most one requirement; one approval never
implies another" (L188). A-03 consuming a frozen output contract does not make
A-03 the row that authorizes the freeze.

**Phase gates.** `gate_refs` is `["PG-05-02", "PG-05-03"]`. This is the
sharpest cross-check available on this row, and it holds: PG-05-02
("Quarter 0 manual baseline/bootstrap and three real assisted updates for
Quarters 1–3 have been produced **and reviewed**") itself carries an
`ANALYST_ACCEPTANCE` / `Responsible analyst` requirement — the same type and
authority A-03 enumerates. PG-05-03 ("the manual baseline and all three
report-level review times are recorded") carries no approval requirement. So
the gate side introduces no authority this row lacks.

**Transitions, fail-closed boundaries, security exceptions.**
`transition_history_sha256` is a read-only input covered by the input
projection; `approval_records` is `[]`; `security_exception_ids` is `[]`;
`blocked_scope` is `[]`. The clause states no prohibition and claims no
deviation.

**Dispositions re-read.** `disposition_refs` are `G-4`, `M-1`, `6.8`.
`DISP-G-4` (practice effect) relates A-02, A-03, B-02, B-04, B-13 and carries
only the delegated approval. `DISP-M-1` carries `ANALYST_ACCEPTANCE`, but its
`related_register_ids` is `["A-11"]` — the bootstrap thesis, not the baseline
workflow — and `REG-A-11` carries that type. So `DISP-M-1`'s analyst authority
is accounted for on the row it points at.

**Candidate authorities I tested and rejected.** `MEMORY_PROMOTION` — the
clause produces a manual baseline, not a promoted memory; the ledger's single
`MEMORY_PROMOTION` requirement sits on `REG-C-10`. `CAPACITY_COMMITMENT`
— "analyst minutes" appear in A-07's and A-12's clauses, not A-03's; A-03
records overhead rather than committing capacity. `PRODUCT_OWNER_DECISION` —
A-03 performs a workflow the product owner already scoped in A-02; nothing in
its text is a product-scope decision.

**Other `APPROVAL` inventory fields.** `approval_records` `[]`;
`security_exception_ids` `[]`; `human_review_id` `HR-0004`, projected
`["HR-0004"]`, inside the digest-pinned 134-component HR-0004 scope.

**Conclusion.** `required_approvals` is complete for the A-03 clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `REG-A-03`'s `required_approvals` inventory is correct at the input bytes pinned
above.
