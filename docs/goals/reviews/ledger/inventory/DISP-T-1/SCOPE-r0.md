# Inventory review — DISP-T-1 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-T-1` |
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
{"activation_predicate":null,"disposition_refs":["T-1"],"gate_refs":[],"related_register_ids":["A-12"],"scope_derivation":{"applicable_spec_ids":["S08"],"authority_effect":"ACTIVE_CONTROL","derived_program_disposition":"REQUIRED_NOW","related_register_ids":["A-12"],"rule":"AUTHORITATIVE_OCCURRENCE"}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `c5e347b68ed2b264388984a672f0be1ceadd1e0ac0e170c3a6bfa464fa5dea73`
- `reviewed_inventory_sha256` (pre-record): `9ac29b0f3ae361ed256e0855a9528e6ba16d6ed62297722c2b80feaea21af018`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` lines 268-272, anchor `T-1`, title "Operating budget and calendar disappeared":

> ### T-1 — Operating budget and calendar disappeared
>
> **Disposition: Accept.**
>
> Per-run ceilings do not replace a team/calendar/provider budget. Add a separate row for weekly builder capacity, target phase dates, monthly provider/model/infrastructure ceilings, analyst-review capacity, and maintenance burden.

- `source_hash` recomputed over the whole file → `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`, matching the row.
- `text_digest` recomputed over the normalized L268-272 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `31d86ca11632b3b8424099990a16f9f760110465f1dfcf7ce4ce0d8fe0afeaa5`, matching the row.
- `required_acceptance_text` equals that normalized span byte for byte
  (checked by comparison, not by eye).
- The crosswalk for this row is pinned by the structural validator at
  `validate_ledger_structural.py:2427-2479` (`EXPECTED_DISPOSITION_CROSSWALK`),
  which fixes `applicable_spec_ids` and `related_register_ids` and derives the
  `primary_spec` shape from the spec count.

## Reasoning

**Kind.** The occurrence is the first numbered finding of §4
"Register-to-review traceability audit" (heading at L266), ordinal `T-1`, with an
explicit `**Disposition: Accept.**` line. Section membership does not change the
inventory kind — the shape of the occurrence does, and this is a numbered,
separately dispositioned finding. `disposition_item` is correct; the §4 heading
itself is not inventoried as a component.

**Derivation rule.** `AUTHORITATIVE_OCCURRENCE` (goal L237-245;
`validate_ledger_structural.py:1510`), `applicable_spec_ids` present as the only
kind-specific key (`:1502`).

**Authority effect.** `ACTIVE_CONTROL`, deriving `REQUIRED_NOW` directly; both
stored disposition fields agree.

**Related register IDs.** `["A-12"]`. The clause's operative demand is "Add a
separate row for weekly builder capacity, target phase dates, monthly
provider/model/infrastructure ceilings, analyst-review capacity, and maintenance
burden" — a demand for exactly one new register row, which the pinned v2 register
now carries as A-12 ("Define operating calendar, standing budget, and capacity",
register L42), whose acceptance text mirrors the list: "Weekly builder/analyst
capacity, target phase dates, monthly provider/model/infrastructure ceilings,
maintenance allowance, and expected company coverage documented". One demanded
row, one related ID. The clause's opening sentence mentions per-run ceilings only
to say they are *not* a substitute, which creates no obligation on the workflow
budget rows and correctly yields no additional related ID.

**Applicable spec IDs and `primary_spec`.** `["S08"]`, matching REG-A-12's owning
spec (success metrics, workflow budgets, and operating capacity). One spec, so
`primary_spec` is the object form (`:2474-2476`), pointing at
`docs/specs/equity-os-s08-success-metrics-budgets-capacity.md`; HR-0004 left it
in place, touching only `human_review_id` on this row.

**Distinctness from its section-mate.** `DISP-T-2` (L274-291) also lands on S08
and also concerns measurement. They are separate occurrences with disjoint
targets: T-1 is the *budget and calendar* row (A-12), T-2 is the *success-metric
contract* (A-13). Neither related list overlaps the other, which is what I would
expect if both derivations were done from the source rather than from the spec.

**Refs, predicate, slot.** `disposition_refs == ["T-1"]`; `gate_refs == []`
(register-only field, `:2660-2664`); `activation_predicate == null` for a
`REQUIRED_NOW` row (goal L288-290); `scope_derivation.semantic_review` is the
applicable slot, `PENDING`, with the exact 10-key set.

**Restatement check.** `ALIAS-013` (L36) and `ALIAS-019` (L410) resolve to
`DISP-T-1` as derivative restatements; the authoritative occurrence stays
L268-272.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `DISP-T-1`'s scope derivation is correct at the input bytes pinned above.
