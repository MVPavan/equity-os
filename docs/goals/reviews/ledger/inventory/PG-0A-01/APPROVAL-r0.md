# Inventory review — PG-0A-01 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `PG-0A-01` |
| `review_type` | `APPROVAL` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `3c844df3-fdab-4e89-929b-89fcbc8223d4` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-16T03:50:06Z` |

Role binding: `CONTEXT.md` "Agent roles (harness-wide)" L137-139 binds `REVIEWER` to
Claude Opus 5 at high effort, in an agent and context independent of any `IMPLEMENTER`
that produced the reviewed content. The digest above is the `CONTEXT.md` bytes at review
time and is an immutable historical capture, never re-verified against later bytes
(`validate_ledger_structural.py:250-262`).

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
{"approval_records":[],"human_review_id":[],"required_approvals":[],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (the recorder must recompute both after
its Phase A evidence append, per recording design r2 §3.4 — appending review evidence
mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `cacb03f5b389f32d8da34bec18a8bbc3fe94faf0f64a56fd52b1571a65a48952`
- `reviewed_inventory_sha256` (pre-record): `3d8490f952ad11fc316d91ecf8ad98db82eea8653909b7236c8c66569c3d904f`

Note on that inventory digest, recorded so it is not mistaken for a copy-paste error: the
`APPROVAL` inventory projection (`validate_ledger_structural.py:312-318`) contains no
component identifier — only `required_approvals`, `approval_records`, the normalized
`human_review_id`, and `security_exception_ids`. Eight rows in this batch have all four
empty or `[]`, so they legitimately share the single digest
`3d8490f952ad11fc316d91ecf8ad98db82eea8653909b7236c8c66569c3d904f`. The per-row
`reviewed_input_sha256` above is distinct, because the input projection does carry
`component_id`, so the two digests together still bind this review to this row.

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line 126,
anchor `F-0A-01`, the 1st bullet under the
`### Phase 0A may exit only when` heading at line 124, inside
`## F. Phase-gate scorecard` (line 122):

> - the initial product boundary is documented;

- `source_hash` recomputed over the whole register file →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L126 span (CRLF→LF, surrounding ASCII
  whitespace trimmed) → `e7cfb37e6dc22ae00997af7c8feed2d3601b7d190560456e67a2d9ad311fd2d5`, matching the row.
- `required_acceptance_text` is that span with the `- ` list marker and the trailing
  `;` removed — compared programmatically, not by eye.
- `EV-PG-0A-01-SOURCE` is a `UTF8_LINE_SPAN` reference over exactly that one line
  (`start_line == end_line == 126`); its `content_sha256` recomputes to the same digest,
  so the row's only evidence object resolves against current bytes.

## Reasoning

**What authority the clause demands.** On its face, none: "the initial product boundary
is documented" asserts that a document exists.

**What is enumerated.** `required_approvals == []`. Per goal L188 this is a positive
determination, and I affirm it — but this row and `PG-0A-02` are the two in this batch
where the related register carries a non-delegated authority that the gate does not, so
the reasoning is set out in full.

**The argument for a missing `PRODUCT_OWNER_DECISION`.** `REG-A-01` carries
`APR-REG-A-01-02`, `PRODUCT_OWNER_DECISION` / `Product owner`. A-01's title is
"**Freeze** initial user and distribution boundary" (register L31), and freezing a
product's user and distribution boundary is a product-owner decision if anything is. If
the gate is really about the boundary being settled, the owner's decision is the gate
condition and its absence would be an omission.

**Why I concluded it is not missing.**

1. **The clause says "documented", not "frozen" or "approved".** A-01's *title* names the
   freeze; A-01's *acceptance text* — which is what obligations derive from — is "Written
   statement covering …", a documentation requirement. This clause takes the acceptance
   text's demand, not the title's framing.
2. **The consistently applied gate rule.** Across all 35 phase-gate rows in the ledger,
   exactly six carry a non-delegated approval requirement, and each of those six asserts
   an approval or acceptance state in its own words: "is approved" (`PG-05-01`,
   `PG-05-05`), "reviewed" (`PG-05-02`), "the approved narrative" (`PG-1-06`), "is
   accepted" (`PG-1-09`), "is acceptable" (`PG-2-05`). `PG-0A-07`, the sibling clause
   "operating capacity and standing budget are **documented**", carries none — even though
   its register A-12 concerns capacity and budget, both of which have named authorities in
   the closed vocabulary. "Documented" does not carry an authority in this program, and
   that treatment is uniform, not special-cased here.
3. **The authority is enumerated where it binds.** `REG-A-01` holds the product-owner
   decision and lists `PG-0A-01` in its `gate_refs`, so the gate cannot be evaluated
   against a register row whose owner decision is unmet. Duplicating it at gate level
   would create a second obligation for one real-world decision, and the goal's matching
   rules forbid one record satisfying two requirements — so the duplicate would have to be
   discharged by a second, separately recorded product-owner resolution over the same
   fact.

I record the counter-argument because it is genuine. On these bytes and this clause text,
the empty list is correct.

**Check against the rest of the closed vocabulary.** `LEGAL_REVIEW` is the other type
worth naming, since a user-and-distribution boundary sounds legal. A-01 forecloses it in
its own acceptance text: "document does not claim legal sufficiency". The pinned
disposition report says the same thing directly, at line 303: "A-01 can define the
intended product boundary without completing legal analysis. It should avoid claiming that
the chosen boundary is legally sufficient. Current regulatory verification becomes
mandatory before external, paid, personalized, or execution-connected use, **not
necessarily before documenting the initial private-use intent**." Both authoritative
sources place legal and regulatory review after this gate, not on it. Nothing reaches
analyst, domain, budget, capacity, named-owner, rights, regulatory, production,
distribution, security, or execution authority.

**Why no delegated artifact approval.** No `phase_gate_clause` row carries one;
`primary_spec` is `null` — the S01 specification that covers this boundary is owned by
`REG-A-01`, which is where the delegated spec approval correctly sits.

**Rest of the projection.** `approval_records == []`; `security_exception_ids == []`;
`human_review_id` normalizes to `[]`, and `PG-0A-01` has zero occurrences in the canonical
human-review artifact.

**Residuals.** None. The empty approval list is complete against the clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition, and grants no
non-delegated authority (goal L624-626). It records only that the component's
`required_approvals` obligation list is complete against its source clause at the input
bytes pinned above.
