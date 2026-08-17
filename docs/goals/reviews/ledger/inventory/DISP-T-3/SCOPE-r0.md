# Inventory review — DISP-T-3 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-T-3` |
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
{"activation_predicate":null,"disposition_refs":["T-3"],"gate_refs":[],"related_register_ids":["B-03"],"scope_derivation":{"applicable_spec_ids":["S10"],"authority_effect":"ACTIVE_CONTROL","derived_program_disposition":"REQUIRED_NOW","related_register_ids":["B-03"],"rule":"AUTHORITATIVE_OCCURRENCE"}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `b317abef887b3dce2b093934411c7c382c9189eee07233cb14873b8be68b5663`
- `reviewed_inventory_sha256` (pre-record): `53514c23d2a802eece423203f96283e37f97d008f76878568ce6750be1fc1583`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` lines 293-297, anchor `T-3`, title "Gate wording lives in multiple places":

> ### T-3 — Gate wording lives in multiple places
>
> **Disposition: Accept.**
>
> The implementation register should own the live gate wording. The consolidated review should state principles and rationale but should no longer be edited as the operational checklist.

- `source_hash` recomputed over the whole file → `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`, matching the row.
- `text_digest` recomputed over the normalized L293-297 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `8006f6c866c3cfb55c0592355c7b2657e5e97b6c727d1789ca30a77263564845`, matching the row.
- `required_acceptance_text` equals that normalized span byte for byte
  (checked by comparison, not by eye).
- The crosswalk for this row is pinned by the structural validator at
  `validate_ledger_structural.py:2427-2479` (`EXPECTED_DISPOSITION_CROSSWALK`),
  which fixes `applicable_spec_ids` and `related_register_ids` and derives the
  `primary_spec` shape from the spec count.

## Reasoning

**Kind.** Numbered §4 traceability finding, ordinal `T-3`, explicit
`**Disposition: Accept.**` — `disposition_item`.

**Derivation rule.** `AUTHORITATIVE_OCCURRENCE` (goal L237-245;
`validate_ledger_structural.py:1510`), with `applicable_spec_ids` as the only
kind-specific key (`:1502`).

**Authority effect.** `ACTIVE_CONTROL`, deriving `REQUIRED_NOW`; both stored
disposition fields agree.

**Kind boundary — the judgment this row turns on.** This clause allocates
authority between two blueprint documents, which is exactly what an
`authority_clause` does, and the report *does* carry such a clause: `AUTH-DISP-001`
anchors report L41, the executive-verdict statement that the register "should now
be the single operational source of truth for gates and open decisions". The two
are distinct occurrences, and both are correctly inventoried. L41 is an unnumbered
authority statement in §1's final disposition, carrying no finding ordinal, and is
inventoried as `authority_clause` with `PROGRAM_WIDE_ACTIVE_CONTROL` and empty
`related_register_ids`. L293-297 is a numbered §4 finding with its own ordinal and
its own disposition line, and it is register-scoped. Inventorying exact
occurrences means two rows here, not one; `AUTH-DISP-001`'s own scope-derivation
artifact records the reciprocal check.

**Distinctness from the document-strategy rows.** §9 "Document strategy"
(L466-476) is inventoried as `DOC-01`…`DOC-06` at L468, L470-473 and L475. Those
say which documents exist and what each is for; T-3 says which document owns the
live gate wording. The spans are disjoint from L293-297 and the kinds differ
correctly.

**Related register IDs.** `["B-03"]`. B-03 ("Establish source-of-truth matrix …
Approved authority table for raw documents, SQL facts, claims, calculations,
narrative memory, derivative indices, evidence packages, and reports", register
L53) is the register row that owns document authority, which is what this clause
constrains. No other register row governs which document is authoritative. An
independent corroboration: the `R3-F-01` blocking analysis placed `DISP-T-3` and
`REG-B-03` in the same direct-component cone, which is only coherent if this row
is B-03-scoped.

**Applicable spec IDs and `primary_spec`.** `["S10"]`, matching REG-B-03's owning
spec. One spec, so `primary_spec` is the object form (`:2474-2476`) pointing at
`docs/specs/equity-os-s10-source-of-truth-evidence-retention.md`; HR-0004 touched
only `human_review_id` here.

**Blocked state.** `REVIEW_BLOCKED` at `review_round` 4 with `R3-F-01` open.
Those fields are outside the `SCOPE` projection; blocking is delivery state, and
`activation_predicate` correctly stays `null` for a `REQUIRED_NOW` row.

**Refs and slot.** `disposition_refs == ["T-3"]`; `gate_refs == []`
(register-only, `:2660-2664`) — worth stating explicitly on a row *about* gate
wording: the clause governs where gate wording lives, which is not the same as
this component owning a gate; `scope_derivation.semantic_review` is the applicable
slot and is `PENDING`.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `DISP-T-3`'s scope derivation is correct at the input bytes pinned above.
