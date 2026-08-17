# Inventory review — DISP-R-3 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-R-3` |
| `review_type` | `SCOPE` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `4e983789-a352-4ab6-9d42-4e7bdc2941f6` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-15T13:22:11Z` |

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
additionally re-hashed by hand against its current target bytes this round and
matched.

## Reviewed inventory, exactly as read

`review_inventory_projection(row, "SCOPE")` — canonical JSON:

```json
{"activation_predicate":null,"disposition_refs":["R-3"],"gate_refs":[],"related_register_ids":["A-05"],"scope_derivation":{"applicable_spec_ids":["S02"],"authority_effect":"ACTIVE_CONTROL","derived_program_disposition":"REQUIRED_NOW","related_register_ids":["A-05"],"rule":"AUTHORITATIVE_OCCURRENCE"}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `0f5750f72f79730a85bcaa5e0573cd4cf9d8b8b1869f45e119013f65fdd79627`
- `reviewed_inventory_sha256` (pre-record): `640d874f9904413cae2b3d2509318de5af8abcfbd82a1ba114242a29f5c33356`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` lines 331-335, anchor `R-3`, title "Make A-05 depend on A-01":

> ### R-3 — Make A-05 depend on A-01
>
> **Disposition: Accept.**
>
> The intended use boundary determines which rights are required. A-05 should be scoped to the initial boundary while retaining fields for future commercial/public modes. This prevents an open-ended legal exercise from blocking the private research slice.

- `source_hash` recomputed over the whole file → `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`, matching the row.
- `text_digest` recomputed over the normalized L331-335 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `d6cde4e05f3464b4c60f97c1047839d070c930b13059cb8ab83a166311eb8726`, matching the row.
- `required_acceptance_text` equals that normalized span byte for byte
  (checked by comparison, not by eye).
- The crosswalk for this row is pinned by the structural validator at
  `validate_ledger_structural.py:2427-2479` (`EXPECTED_DISPOSITION_CROSSWALK`),
  which fixes `applicable_spec_ids` and `related_register_ids` and derives the
  `primary_spec` shape from the spec count.

## Reasoning

**Kind.** Numbered §5 amendment finding, ordinal `R-3`, explicit
`**Disposition: Accept.**` — `disposition_item`.

**Derivation rule.** `AUTHORITATIVE_OCCURRENCE` forced by kind (goal L237-245;
`validate_ledger_structural.py:1510`); `applicable_spec_ids` is the only extra
key (`:1502`).

**Authority effect.** `ACTIVE_CONTROL`, deriving `REQUIRED_NOW` directly; both
stored disposition fields agree.

**Related register IDs — the one judgment this row actually turns on.** The
stored value is `["A-05"]`, while the clause's own title is "Make A-05 depend on
**A-01**". I treated the omission of A-01 as the live question and resolved it
against the contract's definition rather than against lexical mention.
`related_register_ids` is source semantics — the register rows whose obligation
this occurrence controls — and the goal forbids padding it. A-05 is the row the
disposition changes: it is rescoped to the initial boundary while retaining
fields for future commercial/public modes. A-01 is the *determinant* of that
scope, not a row this clause imposes anything on; A-01's own acceptance text is
untouched by R-3. The dependency itself is already recorded where it belongs — in
the pinned v2 register, A-05's Dependencies cell reads `A-01` (register L35) —
and the ordering relation is separately inventoried as `SEQ-01` (report L451,
`source_register_ids ["A-01"]`) and `SEQ-02` (L452, "A-05 and A-09: rights review
scoped to that boundary"). Adding A-01 here would restate that sequence semantics
inside a disposition item and would attach a register row that this occurrence
does not govern. `["A-05"]` is correct.

**Applicable spec IDs and `primary_spec`.** `["S02"]`, matching REG-A-05's owning
spec (source rights, providers, and consensus-data policy). One spec ID, so
`primary_spec` is the object form as `:2474-2476` requires, pointing at
`docs/specs/equity-os-s02-source-rights-providers-consensus-policy.md`. Note this
also confirms the A-01 reading: had A-01 been in scope, S01 would be the
applicable artifact for the boundary statement, and it is not claimed.

**Refs, predicate, slot.** `disposition_refs == ["R-3"]` self-identifies;
`gate_refs == []` (register-only, `:2660-2664`); `activation_predicate == null`
for a `REQUIRED_NOW` row (goal L288-290); `scope_derivation.semantic_review` is
the applicable slot and is `PENDING` with the exact 10-key set.

**Restatement check.** `ALIAS-021` (report L412) resolves to `DISP-R-3`; it is a
derivative restatement, and the authoritative occurrence remains L331-335.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `DISP-R-3`'s scope derivation is correct at the input bytes pinned above.
