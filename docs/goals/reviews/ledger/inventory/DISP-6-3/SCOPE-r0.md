# Inventory review — DISP-6-3 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-6-3` |
| `review_type` | `SCOPE` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `13edf3cc-a5b0-4217-8730-759de344e6db` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-15T13:10:41Z` |

Role binding: `CONTEXT.md` "Agent roles (harness-wide)" L137-139 and L147 bind
`REVIEWER` to Claude Opus 5 at high effort, independent of any `IMPLEMENTER`
that produced the reviewed content.

## Input hashes read for this review

| Input | SHA-256 |
|---|---|
| `docs/goals/equity-os-blueprint-completion.md` (active goal) | `f15f7ab5a4e425dec3877ab7f1f7594687979060e4dbcd49390a8a8d5fedb85f` |
| `docs/goals/equity-os-blueprint-component-ledger.jsonl` (canonical ledger) | `de236d7e8dcf02e307ec58797f5722ae2f85d1d8cdba57d4ecc07df5383c9c97` |
| `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` (pinned v2 register) | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| `docs/blueprint/funda-third-order-review-disposition-report.md` (pinned disposition report) | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| `scripts/equity_os_blueprint/validate_ledger_structural.py` (structural validator) | `731d0d8b208b577967c92e3992e7ec1a4333cdecbf89f6951c32d2ec469436f9` |
| `scripts/equity_os_blueprint/validate_ledger_preimplementation.py` | `f7a225a1f99cb85c92cde3094505a92a746552280eb45dae0253a71ab9048013` |
| `scripts/equity_os_blueprint/extract_goal_validators.py` | `5d20d796666d1154fb3c84ba4fa7407ee82819510a5ac06254f7f4a3126c6f2a` |
| `docs/goals/equity-os-blueprint-human-review-needed.md` | `094fcdfab74a3f4c6fdb82b1520fc4d13b636ac0e9ed10194e5d607aed2ce9af` |
| `CONTEXT.md` (role binding) | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r2.md` (artifact format) | `adf908ac8cec01a55a53438624c6a8913f673f5b7cecd3e955fc4919f73803fb` |

Fresh structural validation at these exact bytes → exit `0`.

## Reviewed inventory, exactly as read

`review_inventory_projection(row, "SCOPE")` — canonical JSON:

```json
{"activation_predicate":null,"disposition_refs":["6.3"],"gate_refs":[],"related_register_ids":["C-17"],"scope_derivation":{"applicable_spec_ids":["S17"],"authority_effect":"ACTIVE_CONTROL","derived_program_disposition":"REQUIRED_NOW","related_register_ids":["C-17"],"rule":"AUTHORITATIVE_OCCURRENCE"}}
```

Digests observed at review time, **pre-record** (recorder recomputes after
Phase A, recording design r2 §3.4):

- `reviewed_input_sha256` (pre-record): `bc29cafeff2b8f079afaf2465d3b9bef679825f492e722dc83ec7cef0b72ee6f`
- `reviewed_inventory_sha256` (pre-record): `11d5491311605aa6a4072d9e1aa7864d0bb5f8581e61d50e803d5346fea9ed80`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` L363-365:

> ### 6.3 ISIN is an external identifier
>
> Use an internal stable identifier as the primary key. ISIN is a high-value
> mapping, not the authority for Funda object identity.

- `source_hash` recomputed → `a9021c15…`, matches.
- `text_digest` recomputed over the normalized L363-365 span →
  `1229dceb7624a05b00ff7b56a390013260bbd87947fe74372ab21695f0514880`, equal to
  the stored value.
- `required_acceptance_text` equals that span byte for byte.

## Reasoning

**Kind.** A numbered correction item, self-identified by
`disposition_refs == ["6.3"]` matching the heading ordinal → `disposition_item`.

**Derivation rule.** `AUTHORITATIVE_OCCURRENCE`, fixed by kind (goal L241,
`validate_ledger_structural.py:1511`). Stored value matches.

**`authority_effect == "ACTIVE_CONTROL"`.** Two imperative sentences: "Use an
internal stable identifier as the primary key" is a design mandate, and "ISIN is
… not the authority for Funda object identity" is a standing prohibition on the
alternative. Both bind now, before any entity-master implementation exists. Not
`REJECTED_PROPOSAL` — ISIN is explicitly retained as "a high-value mapping",
i.e. demoted rather than rejected, and the ledger's only `REJECTED_ACCOUNTED`
row is `DISP-R-1`. Not `FOLLOW_RELATED_SCOPE` — the mandate is unconditional.
`derived_program_disposition == "REQUIRED_NOW"` follows and equals the stored
`program_disposition`.

**Related register IDs — `["C-17"]`.** `C-17` (register v2 L88) is "Decide
entity/security master authority", acceptance: "Stable internal company/security
IDs; versioned ISIN/symbol/CIN/LEI mappings; source hierarchy, conflicts,
valid/knowledge time, and one real identifier-change case tested". §6.3's two
sentences map onto its first two elements exactly — internal IDs as primary key,
ISIN as a versioned mapping. This is a one-to-one clause/decision match, so a
second ID would be padding. I checked `C-17`'s own declared dependencies `A-05`
(source rights and providers) and `A-06` as candidates and rejected both: §6.3
says nothing about where identifier data is sourced from or under what rights,
only about which identifier holds authority inside the system. Goal L233-235
forbids inferring related-register scope from spec applicability, and this is the
symmetric case — inferring it from a register row's dependency list would be the
same error.

**Applicable spec IDs — `["S17"]`.** S17 is "Entity/security master,
relationships, and corporate actions" — the artifact that defines object
identity. Exactly one spec applies, so `validate_ledger_structural.py:2473-2475`
requires a non-null `primary_spec`, and the row carries `spec_id "S17"` with the
matching title and path `docs/specs/equity-os-s17-entity-security-master-actions.md`
— the same path its `SPEC-DRAFT` evidence points at. Consistent.

**Disposition and gate refs.** `disposition_refs == ["6.3"]`; `gate_refs == []`,
the uniform value for all 109 non-register canonical rows. Here I note something
that differs from most rows in this batch and record it as verified rather than
as a gap: `REG-C-17`'s own `gate_refs` are also `[]` — no `phase_gate_clause`
names `C-17` in its `related_register_ids`, so this clause has **no** phase-gate
reach anywhere in the ledger. That is consistent, not missing: identifier
authority is a design decision that no §F scorecard gate currently tests, and
`gate_refs` is derived, never authored (`validate_ledger_structural.py:2660-2664`).

**Activation predicate.** `null`, required for `REQUIRED_NOW` (goal L288-290).

**Applicable review slot.** Non-register canonical row →
`scope_derivation.semantic_review` is the applicable `SCOPE` slot
(`validate_ledger_preimplementation.py:200-204`). Present, `PENDING`, 10-key set,
no role-binding keys.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `DISP-6-3`'s scope derivation is correct at the input bytes pinned
above.
