# Inventory review — REG-A-10 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-A-10` |
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

`REG-A-10` has `kind == "register_row"`. Its `scope_derivation` reads exactly

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
exists to record. No `SCOPE` artifact was written for `REG-A-10`.

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
{"approval_records":[],"human_review_id":["HR-0001","HR-0004"],"required_approvals":[{"actor":null,"approval_id":"APR-REG-A-10-01","approval_type":"DELEGATED_ARTIFACT_APPROVAL","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Delegated fresh Sol xhigh specification reviewer","scope":"A-10 under S06: Define claim materiality policy","status":"UNRESOLVED","timestamp":null},{"actor":null,"approval_id":"APR-REG-A-10-02","approval_type":"DOMAIN_EXPERT_ACCEPTANCE","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Equity-research domain expert","scope":"A-10 under S06: Define claim materiality policy","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `d1135bb52f42d52483cd00671492a5687ea247c52a4c106febe888d3956bbcbb`
- `reviewed_inventory_sha256` (pre-record): `4473b4d935d8a3c30efa00f7593105d8fd47a9fa57014fe5fc80a64ca2c426a3`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line
40, register ID `A-10`, title "Define claim materiality policy":

```text
| A-10 | Critical | Define claim materiality policy | Versioned policy combining quantitative magnitude, always-material categories, thesis relevance, source conflict/uncertainty, and coverage-specific overrides; validator test cases approved | A-01, A-02 | Open |
```

- `source_hash` recomputed over the whole pinned v2 register →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L40 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `7ecbf2a586fe16f9fdf54abe1ace2e106a0d8907534b416fff417fe72952afb3`, matching the row and
  matching `EV-REG-A-10-SOURCE.content_sha256`.
- `required_acceptance_text` equals the source row's acceptance cell byte for
  byte, and `register_id`/`source_title` equal its ID and decision cells
  (checked by comparison, not by eye).
- Register `Status` cell: `Open`; `Priority`: `Critical`; `Dependencies`:
  `A-01, A-02`. Row `program_disposition`: `REQUIRED_NOW`; `delivery_status`:
  `REVIEW_BLOCKED`; `gate_result`: `NOT_EVALUATED`.

## Reasoning

**What this review decides.** Whether `required_approvals` on `REG-A-10`
enumerates every authority the A-10 clause and its derivation sources demand.
Both requirements are `UNRESOLVED` with null actor/timestamp/record.

**Source acceptance text.** The clause ends "validator test cases **approved**"
— an explicit, bare approval demand, and the only one of its kind in this
batch. Which authority? The subject matter is claim materiality: what counts as
material is an equity-research judgment, not a process or budget one. The
enumeration answers accordingly: `APR-REG-A-10-02` is
`DOMAIN_EXPERT_ACCEPTANCE` with authority `Equity-research domain expert`, one
of the five strings the closed vocabulary permits for that type — the others
being `Calculation-domain authority`, `Data-domain authority`, `Entity-data
authority`, and `Vocabulary authority` (`:2592-2596`, goal L569). Of those five
I checked that `Equity-research domain expert` is the right one for a
materiality policy spanning guidance, restatements, governance and thesis
relevance, and it is. Its `scope` covers the whole row, so the bare "approved"
in the clause has an enumerated authority.

**Dependencies.** The register cell is `A-01, A-02`. `REG-A-02` carries
`PRODUCT_OWNER_DECISION`; neither propagates. A-10's policy is *bounded by* the
distribution boundary (A-01) and the selected slice (A-02); those are
definitional inputs, not authority delegations.

**Phase gates.** `gate_refs` is `["PG-0A-05", "PG-1-01", "PG-1-02"]` — the
widest gate fan-out in this batch. I read all three rows. PG-0A-05
("materiality and success-metric contracts are versioned"), PG-1-01 ("all
numerical claims classified as material under A-10 resolve to a fact or
calculation trace") and PG-1-02 ("all factual claims classified as material
under A-10 resolve to the correct source location") each carry an empty
`required_approvals`. So the two Phase-1 gates that consume A-10's policy
demand evaluation, not additional sign-off.

**Dispositions re-read.** `G-1`, `G-5`, `R-4`, `6.2`. `DISP-G-5` and
`DISP-6-2` both list `A-10` in `related_register_ids` and both carry only the
delegated specification-review approval. `DISP-G-1` carries
`ANALYST_ACCEPTANCE`, but its related registers are `A-04`, `C-08`, `C-09`,
`C-16` — not `A-10` — and `REG-A-04` carries that type. So no analyst authority
is stranded.

**Candidates I tested and rejected.** `ANALYST_ACCEPTANCE` — the analyst
*applies* the materiality policy but does not own its definition; the ledger
attaches analyst acceptance to the rows that produce analyst work product
(A-03, A-04, A-11), and A-10 defines a policy. `PRODUCT_OWNER_DECISION` — a
materiality threshold has product consequences, but `DISP-G-5` frames the
remedy as a domain-completeness problem ("a single quantitative percentage is
insufficient"), not a product-scope decision. `REGULATORY_REVIEW` — the
always-material category list names "regulatory actions" and "auditor
qualifications"; that is subject matter to be *classified*, not a regulatory
filing to be reviewed, and the clause makes no compliance claim.

**Fail-closed boundaries and the blocking finding.** `security_exception_ids`
is `[]`; `blocked_scope` carries one S06-I7 entry under HR-0001 whose
`required_authority` is `GOAL_OR_PROCESS_AUTHORIZATION` / "Explicit rank-1
current-user authority". As on `REG-A-04`, that authority is required for a
post-cap S06 remediation mechanism, not for satisfying A-10's acceptance
criteria; the contract records it as an open human-review entry with this
component in scope, and putting it in `required_approvals` would misstate the
register bytes.

**Other `APPROVAL` inventory fields.** `approval_records` `[]`;
`human_review_id` `["HR-0001", "HR-0004"]`, projected sorted. `REG-A-10` is one
of the nine components the validator pins to exactly this pair
(`EXPECTED_PRIOR_HR_LINKS["HR-0001"]`, `:2776-2781`).

**Conclusion.** `required_approvals` is complete for the A-10 clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `REG-A-10`'s `required_approvals` inventory is correct at the input bytes pinned
above.
