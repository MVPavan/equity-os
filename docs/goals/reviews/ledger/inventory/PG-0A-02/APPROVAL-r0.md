# Inventory review — PG-0A-02 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `PG-0A-02` |
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

- `reviewed_input_sha256` (pre-record): `6bfc6737876df8fe546952ac5774bade7071a260f656987e2f95dc8537ec2d3d`
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

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line 127,
anchor `F-0A-02`, the 2nd bullet under the
`### Phase 0A may exit only when` heading at line 124, inside
`## F. Phase-gate scorecard` (line 122):

> - source rights are scoped to that boundary;

- `source_hash` recomputed over the whole register file →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L127 span (CRLF→LF, surrounding ASCII
  whitespace trimmed) → `b13b104b6d04b56a955bf4eb3b8daa6855f571d7e255ed44b4e6ac2ebbe14fb1`, matching the row.
- `required_acceptance_text` is that span with the `- ` list marker and the trailing
  `;` removed — compared programmatically, not by eye.
- `EV-PG-0A-02-SOURCE` is a `UTF8_LINE_SPAN` reference over exactly that one line
  (`start_line == end_line == 127`); its `content_sha256` recomputes to the same digest,
  so the row's only evidence object resolves against current bytes.

## Reasoning

**What authority the clause demands.** On its face, none: "source rights are scoped to
that boundary" asserts a consistency relation between the rights register and the declared
product boundary, checkable by reading both.

**What is enumerated.** `required_approvals == []`. Per goal L188 this is a positive
determination and I affirm it — but with `PG-0A-01` this is one of the two rows in the
batch where the related register carries an authority the gate does not, so the reasoning
is set out in full.

**The argument for a missing `DATA_RIGHTS_APPROVAL`.** `REG-A-05` carries
`APR-REG-A-05-02`, `DATA_RIGHTS_APPROVAL` / `Data-rights authority`, plus the matching
`REQ-REG-A-05-DATA_RIGHTS_APPROVAL` typed-approval evidence item. "Source rights" is
precisely the subject that authority governs, and the goal is emphatic that rights
evidence "always uses `TYPED_APPROVAL` and the typed approval/human-review path, never a
fabricated shell command". If this gate asserts anything about what rights permit, an
agent must not be the one establishing it.

**Why I concluded it is not missing.**

1. **The clause asserts a scoping relation, not a rights determination.** It says the
   rights are *scoped to that boundary* — that the register's coverage matches A-01's
   declared user and distribution boundary. Whether a given provider's terms actually
   permit commercial use or redistribution is A-05's question, and A-05 enumerates the
   competent authority for it.
2. **The authority is enumerated where it binds, and is coupled to this gate.**
   `REG-A-05.gate_refs == ["PG-0A-02"]` — a singleton pointing here — so this gate cannot
   be evaluated against a register row whose data-rights approval is unmet. The authority
   is present in the program and directly upstream of this clause; it is not absent.
   Duplicating it would create two obligations for one real-world rights decision, and the
   goal's matching rules ("Record IDs … may not satisfy two requirements" (goal L612-613)) mean the
   duplicate would need its own separately recorded human resolution over the same fact.
3. **The gate rule is applied uniformly.** Exactly six of the ledger's 35 phase-gate rows
   carry a non-delegated approval, and each of those six asserts an approval or acceptance
   state in its own words. This clause asserts a scoping fact. `PG-0A-01`, the clause this
   one refers back to, is treated identically with respect to A-01's
   `PRODUCT_OWNER_DECISION`.

I record the counter-argument because it is the strongest available against this row, and
a later reader with new information should be able to re-open it. On these bytes and this
clause text, the empty list is correct.

**Check against the rest of the closed vocabulary.** `PROVIDER_AUTHORIZATION` appears in
the goal's prose list of approval types but has no entry in the pinned
`REQUIRED_AUTHORITY_VOCABULARY` map (`validate_ledger_structural.py:2586-2613`), and the
goal states that "An approval type absent from the table above has no obligation in this
inventory and gains one only through a reconciled, reviewed, approved change"
(goal L583-585) — so it
cannot be the missing authority here, and `REG-A-05` does not carry it either.
`LEGAL_REVIEW` is not reached: the clause is about scope matching, and A-01's own text
disclaims legal sufficiency for the boundary document.

**Why no delegated artifact approval.** No `phase_gate_clause` row carries one;
`primary_spec` is `null` — the S02 specification covering source rights is owned by
`REG-A-05`.

**Rest of the projection.** `approval_records == []`; `security_exception_ids == []` — the
clause creates no fail-closed exception; `human_review_id` normalizes to `[]`, and
`PG-0A-02` has zero occurrences in the canonical human-review artifact.

**Residuals.** None. The empty approval list is complete against the clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition, and grants no
non-delegated authority (goal L624-626). It records only that the component's
`required_approvals` obligation list is complete against its source clause at the input
bytes pinned above.
