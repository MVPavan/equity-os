# Inventory review — REG-A-11 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-A-11` |
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

`REG-A-11` has `kind == "register_row"`. Its `scope_derivation` reads exactly

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
exists to record. No `SCOPE` artifact was written for `REG-A-11`.

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
{"approval_records":[],"human_review_id":["HR-0004"],"required_approvals":[{"actor":null,"approval_id":"APR-REG-A-11-01","approval_type":"DELEGATED_ARTIFACT_APPROVAL","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Delegated fresh Sol xhigh specification reviewer","scope":"A-11 under S05: Author and approve bootstrap thesis for the discovery company","status":"UNRESOLVED","timestamp":null},{"actor":null,"approval_id":"APR-REG-A-11-02","approval_type":"ANALYST_ACCEPTANCE","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Responsible analyst","scope":"A-11 under S05: Author and approve bootstrap thesis for the discovery company","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `e9b0763723416d0642ab5b650b0b7a038552234bfe89818d01fc9a7308b855fa`
- `reviewed_inventory_sha256` (pre-record): `bf3ebc21c0615053728ce7fa5d26363816451898dc003c8fc4bac4afd31d594d`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line
41, register ID `A-11`, title "Author and approve bootstrap thesis for the discovery company":

```text
| A-11 | Critical | Author and approve bootstrap thesis for the discovery company | Using Quarter 0, a concise initial thesis, assumptions, management commitments, risks, open questions, and observable falsifiers are manually written, approved, versioned, and available before Quarter 1; full initiation remains deferred | A-03 | Open |
```

- `source_hash` recomputed over the whole pinned v2 register →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L41 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `9af11ddc3b29bd8392d49888e9071c80e0f97f5ca9e75fad595a849af4ad797b`, matching the row and
  matching `EV-REG-A-11-SOURCE.content_sha256`.
- `required_acceptance_text` equals the source row's acceptance cell byte for
  byte, and `register_id`/`source_title` equal its ID and decision cells
  (checked by comparison, not by eye).
- Register `Status` cell: `Open`; `Priority`: `Critical`; `Dependencies`:
  `A-03`. Row `program_disposition`: `REQUIRED_NOW`; `delivery_status`:
  `SPEC_DRAFT`; `gate_result`: `NOT_EVALUATED`.

## Reasoning

**What this review decides.** Whether `required_approvals` on `REG-A-11`
enumerates every authority the A-11 clause and its derivation sources demand.
Both requirements are `UNRESOLVED` with null actor/timestamp/record.

**Source acceptance text.** The clause's title is "Author **and approve**
bootstrap thesis for the discovery company" and its body repeats "approved".
Whose approval? `DISP-M-1`, the disposition that created this row, is explicit
that the artifact is an "analyst-authored bootstrap coverage thesis", and the
enumeration matches: `APR-REG-A-11-02` is `ANALYST_ACCEPTANCE` with authority
`Responsible analyst` — the single permitted string for that type (`:2587`).
`APR-REG-A-11-01` is the standard delegated specification-review approval.

**Dependencies.** The register cell is `A-03`. `REG-A-03` also carries
`ANALYST_ACCEPTANCE`, which is coherent — the same role signs both the manual
baseline and the thesis derived from it — but A-11 carries its own requirement
rather than relying on A-03's, which is what the contract demands ("one
approval never implies another", goal L188).

**Phase gates — the cleanest confirmation in this batch.** `gate_refs` is
exactly `["PG-05-01"]`, whose source clause is "the bootstrap thesis is
approved" and whose own `required_approvals` carries `ANALYST_ACCEPTANCE` /
`Responsible analyst`. The gate that gates on this row's approval names the same
type and authority the row enumerates. Had A-11 named a different authority, or
none, that mismatch would show here.

**Dispositions re-read.** `G-4`, `M-1`, `6.8`. `DISP-M-1` carries
`ANALYST_ACCEPTANCE` itself and relates exactly `["A-11"]` — a second
confirmation of the same type from the disposition side. `DISP-G-4` and
`DISP-6-8` relate the slice-shape registers and carry only the delegated
approval.

**Candidates I tested and rejected.** `PRODUCT_OWNER_DECISION` — the thesis is
an analytical position on one company, not a product-scope decision; the
product-scope act in this cone is A-02's selection, which does carry that type.
`DOMAIN_EXPERT_ACCEPTANCE` — a thesis is domain-flavoured, but the ledger
reserves domain acceptance for policy and vocabulary definitions (A-10 and its
peers), and `DISP-M-1` names the analyst, not a domain authority.
`MEMORY_PROMOTION` — the thesis is versioned and approved, not promoted into
memory; the ledger's single `MEMORY_PROMOTION` requirement sits on `REG-C-10`.

**Fail-closed boundaries.** "full initiation remains deferred" is a scope
prohibition, not an approval gate — it forecloses work rather than requiring
someone to authorize it. `security_exception_ids` `[]`; `blocked_scope` `[]`;
`approval_records` `[]`.

**Other `APPROVAL` inventory fields.** `human_review_id` `HR-0004`, projected
`["HR-0004"]`, inside the digest-pinned HR-0004 scope.

**Conclusion.** `required_approvals` is complete for the A-11 clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `REG-A-11`'s `required_approvals` inventory is correct at the input bytes pinned
above.
