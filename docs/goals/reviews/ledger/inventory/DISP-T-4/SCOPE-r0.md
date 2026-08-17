# Inventory review — DISP-T-4 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-T-4` |
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
{"activation_predicate":null,"disposition_refs":["T-4"],"gate_refs":[],"related_register_ids":["A-01","E-08","E-09"],"scope_derivation":{"applicable_spec_ids":["S01","S02","S04"],"authority_effect":"ACTIVE_CONTROL","derived_program_disposition":"REQUIRED_NOW","related_register_ids":["A-01","E-08","E-09"],"rule":"AUTHORITATIVE_OCCURRENCE"}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `63e98eacc5dec431c3ea59db92441b78603612ccbffb63a75a6ceb94318d4aa3`
- `reviewed_inventory_sha256` (pre-record): `e2960feeeef277c5549348d6154d93d08c02e35cdeed8f4e1539fc479c6d6271`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` lines 299-303, anchor `T-4`, title "Regulatory verification before boundary statement":

> ### T-4 — Regulatory verification before boundary statement
>
> **Disposition: Partially accept.**
>
> A-01 can define the intended product boundary without completing legal analysis. It should avoid claiming that the chosen boundary is legally sufficient. Current regulatory verification becomes mandatory before external, paid, personalized, or execution-connected use, not necessarily before documenting the initial private-use intent.

- `source_hash` recomputed over the whole file → `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`, matching the row.
- `text_digest` recomputed over the normalized L299-303 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `862a0792e4271b735f2ec8646f1dbc2334a587944592a518434c6beb9dae20d7`, matching the row.
- `required_acceptance_text` equals that normalized span byte for byte
  (checked by comparison, not by eye).
- The crosswalk for this row is pinned by the structural validator at
  `validate_ledger_structural.py:2427-2479` (`EXPECTED_DISPOSITION_CROSSWALK`),
  which fixes `applicable_spec_ids` and `related_register_ids` and derives the
  `primary_spec` shape from the spec count.

## Reasoning

**Kind.** Numbered §4 traceability finding, ordinal `T-4`, with an explicit
`**Disposition: Partially accept.**` line — `disposition_item`.

**Derivation rule.** `AUTHORITATIVE_OCCURRENCE` (goal L237-245;
`validate_ledger_structural.py:1510`), `applicable_spec_ids` present as the only
kind-specific key (`:1502`).

**Authority effect — the judgment this row turns on.** "Partially accept" has no
representation in the closed `authority_effect` set, so the derivation must
decide what the *accepted part* is. It is an active control: A-01 must avoid
claiming the chosen boundary is legally sufficient, and current regulatory
verification becomes mandatory before external, paid, personalized, or
execution-connected use. What is declined — that verification must precede
documenting the initial private-use intent — imposes no obligation at all, so it
produces nothing to record. `ACTIVE_CONTROL` is therefore right, and
`REJECTED_PROPOSAL` would be wrong: that value is for a finding rejected outright
and carries a `rejection_record`, which this row correctly lacks.

**Related register IDs.** `["A-01","E-08","E-09"]`, and each of the clause's
targets maps to exactly one of them. A-01 is named literally, and the pinned
register's A-01 acceptance text now ends "document does not claim legal
sufficiency" (register L31) — this clause folded in. "External, paid,
personalized" is E-08 ("Gate paid/public/personalized research on current legal
review", L116). "Execution-connected" is E-09 ("Keep execution in a separate
trust domain", L117). No fourth row is implied.

**`REQUIRED_NOW` with two dormant related rows — checked deliberately.** E-08 and
E-09 are both `Deferred` in the register and `CONDITIONAL_UNACTIVATED` in the
ledger, yet this row derives `REQUIRED_NOW` and carries
`activation_predicate == null`. That is correct, not an inconsistency:
`ACTIVE_CONTROL` derives `REQUIRED_NOW` directly and does **not** aggregate
related-row state — the aggregating branch is `FOLLOW_RELATED_SCOPE`, which is
not used here (goal L~255-260). The substance agrees: the "do not claim legal
sufficiency" obligation binds now, while the gate it states binds later modes.
`activation_predicate == null` then follows from goal L288-290, which forbids a
predicate on a `REQUIRED_NOW` component.

**Applicable spec IDs and `primary_spec`.** `["S01","S02","S04"]`. REG-A-01 and
REG-E-08 are both owned by S01 and REG-E-09 by S04, so S02 cannot have been
inferred from the related rows: it is artifact applicability — source rights and
provider policy is where paid and personalized use changes what rights are
required. Three spec IDs means `primary_spec` must be `null`
(`:2474-2479`), and `TR-DISP-T-4-002` cleared the earlier S01 object under
`HRD-0004-001`.

**Refs and slot.** `disposition_refs == ["T-4"]`; `gate_refs == []` (register-only
field, `:2660-2664`) — again worth stating on a row that *describes* a gate: the
gate wording is the clause's content, not a `gate_refs` entry;
`scope_derivation.semantic_review` is the applicable slot, present and `PENDING`.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `DISP-T-4`'s scope derivation is correct at the input bytes pinned above.
