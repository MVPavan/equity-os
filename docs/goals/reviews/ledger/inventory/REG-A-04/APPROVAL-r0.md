# Inventory review — REG-A-04 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-A-04` |
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

`REG-A-04` has `kind == "register_row"`. Its `scope_derivation` reads exactly

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
exists to record. No `SCOPE` artifact was written for `REG-A-04`.

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
{"approval_records":[],"human_review_id":["HR-0001","HR-0004"],"required_approvals":[{"actor":null,"approval_id":"APR-REG-A-04-01","approval_type":"DELEGATED_ARTIFACT_APPROVAL","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Delegated fresh Sol xhigh specification reviewer","scope":"A-04 under S06: Freeze the first output contract","status":"UNRESOLVED","timestamp":null},{"actor":null,"approval_id":"APR-REG-A-04-02","approval_type":"PRODUCT_OWNER_DECISION","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Product owner","scope":"A-04 under S06: Freeze the first output contract","status":"UNRESOLVED","timestamp":null},{"actor":null,"approval_id":"APR-REG-A-04-03","approval_type":"ANALYST_ACCEPTANCE","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Responsible analyst","scope":"A-04 under S06: Freeze the first output contract","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `4e145cff7e03a4f9c99120a5b1c91ff7ebaae305aa31619ca1a71e21c2b0b7a1`
- `reviewed_inventory_sha256` (pre-record): `6341901473778ef204932487e8cb2ca1259094d7501f5d51beb26c3b438adc02`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line
34, register ID `A-04`, title "Freeze the first output contract":

```text
| A-04 | Critical | Freeze the first output contract | A provisional v0 exists before baseline; final contract after baseline includes event/cutoff, facts, changes, driver analysis, management ledger, thesis impact, observable falsifiers, open questions, calculations, memory draft, and approval record | A-03 for final freeze | Open |
```

- `source_hash` recomputed over the whole pinned v2 register →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L34 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `e57f810850b4e4d969ddd00b06fc5855a724cec1e982d0eb1d83c4617f76949c`, matching the row and
  matching `EV-REG-A-04-SOURCE.content_sha256`.
- `required_acceptance_text` equals the source row's acceptance cell byte for
  byte, and `register_id`/`source_title` equal its ID and decision cells
  (checked by comparison, not by eye).
- Register `Status` cell: `Open`; `Priority`: `Critical`; `Dependencies`:
  `A-03 for final freeze`. Row `program_disposition`: `REQUIRED_NOW`; `delivery_status`:
  `REVIEW_BLOCKED`; `gate_result`: `NOT_EVALUATED`.

## Reasoning

**What this review decides.** Whether `required_approvals` on `REG-A-04`
enumerates every authority the A-04 clause and its derivation sources demand.
All three requirements are `UNRESOLVED` with null actor/timestamp/record.

**Source acceptance text.** A-04 freezes the first output contract. Two
distinct authorities follow from the text, and both are enumerated.
`APR-REG-A-04-02` (`PRODUCT_OWNER_DECISION` / `Product owner`) carries the
freeze itself — deciding what the product's output contract *is* is a product
decision. `APR-REG-A-04-03` (`ANALYST_ACCEPTANCE` / `Responsible analyst`)
carries acceptance of the eleven-element content, which is analyst work
product derived from the baseline; the clause's own "approval record" element
and its "A-03 for final freeze" dependency both point at the analyst who
performed Quarter 0. `APR-REG-A-04-01` is the standard delegated
specification-review approval.

**Dependencies.** The register cell is `A-03 for final freeze`. `REG-A-03`
carries `ANALYST_ACCEPTANCE`, and A-04 independently carries its own — which is
right: the dependency sequences the freeze, it does not delegate the freeze's
authority.

**Phase gates.** `gate_refs` is exactly `["PG-0A-06"]`. I read that row: its
`required_approvals` is empty and its clause is "the provisional output
contract exists". No gate-side authority to propagate.

**Dispositions re-read — the strongest cross-check on this row.**
`disposition_refs` are `G-1`, `G-5`, `R-4`, `6.2`. `DISP-G-1` (narrative
reproducibility) has `related_register_ids` including `A-04` and itself carries
`ANALYST_ACCEPTANCE` / `Responsible analyst` — the same type A-04 enumerates,
which is the confirmation I wanted rather than a new obligation. `DISP-R-4`
(add observable falsifiers) relates `A-04` and carries only the delegated
approval. `DISP-G-5` and `DISP-6-2` are materiality dispositions relating
`A-10` and `C-04`, not `A-04`.

**Fail-closed boundaries, security exceptions, and the blocking finding.**
`security_exception_ids` is `[]`; the clause claims no deviation.
`blocked_scope` carries one entry for finding S06-I7 under HR-0001, whose
`required_authority` is `GOAL_OR_PROCESS_AUTHORIZATION` with authority
"Explicit rank-1 current-user authority". I considered carefully whether that
should appear as a `required_approvals` entry on this row and concluded it must
not: that authority is required for *a post-cap S06 remediation mechanism*, not
for satisfying A-04's acceptance criteria. It is recorded where the contract
puts it — as an open human-review entry (HR-0001, `OPEN_BLOCKING`,
`resolution_decision_ids: []`) with this component inside its scope, and
mirrored in `open_findings[0].required_authority`. Adding it to
`required_approvals` would assert that A-04's own clause demands it, which the
register bytes do not say.

**Candidate authorities I tested and rejected.** `DOMAIN_EXPERT_ACCEPTANCE` —
"observable falsifiers" and "thesis impact" are domain-flavoured, but the
domain authority in this cone attaches to the materiality *policy*, which is
A-10's row and does carry that type. `MEMORY_PROMOTION` — the clause requires
the contract to contain a "memory draft"; a draft is precisely what has not yet
been promoted, and the ledger's single `MEMORY_PROMOTION` requirement sits on
`REG-C-10`, not here.

**Other `APPROVAL` inventory fields.** `approval_records` `[]`;
`security_exception_ids` `[]`; `human_review_id` `["HR-0001", "HR-0004"]`,
projected sorted as `["HR-0001", "HR-0004"]`. `REG-A-04` is one of the nine
components the validator pins to exactly this pair
(`EXPECTED_PRIOR_HR_LINKS["HR-0001"]`, `:2776-2781`, asserted at `:2812-2816`),
so the double link is mechanically forced.

**Conclusion.** `required_approvals` is complete for the A-04 clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `REG-A-04`'s `required_approvals` inventory is correct at the input bytes pinned
above.
