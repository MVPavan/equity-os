# Inventory review — AUTH-REG-001 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `AUTH-REG-001` |
| `review_type` | `SCOPE` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `47c148f8-1c4c-4ed7-88b5-49996aea69bf` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-15T12:53:38Z` |

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
{"activation_predicate":null,"disposition_refs":[],"gate_refs":[],"related_register_ids":[],"scope_derivation":{"authority_effect":null,"derived_program_disposition":"REQUIRED_NOW","related_register_ids":[],"rule":"PROGRAM_WIDE_ACTIVE_CONTROL"}}
```

Digests observed at review time, **pre-record** (recorder recomputes after
Phase A, recording design r2 §3.4):

- `reviewed_input_sha256` (pre-record): `a816a1bcf46b73ff9ede78f7d840a5e1ed123381d4274cb750c34a38d6855843`
- `reviewed_inventory_sha256` (pre-record): `a9dd60c5b7d09531f54342a3bd757624a0d25211784829a28dfcf3f214f76d10`

The inventory digest is shared with the other three `authority_clause` rows
because every field the `SCOPE` projection covers is fixed by kind. What this
review decided is whether the live occurrence justifies that fixed derivation;
that is component-specific and is set out below.

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line 23,
the sole body line of `## Authority rule` (L21):

> The wording in this register is authoritative for implementation gates.
> Narrative reviews explain rationale but do not override this register.

- `source_hash` `26d51b31…` recomputed over the whole register → matches.
- `text_digest` recomputed over the normalized L23-23 span →
  `93a7b66070a38c6750129151fa4612c80a263babcf04c98ae17c90e65402eaf9`,
  equal to the stored value; `required_acceptance_text` equals that span byte for
  byte.
- `expected_authority_clause_lines` (`validate_ledger_structural.py:377-406`)
  pins `AUTH-REG-001` to this path at `source_start_line == source_end_line == 23`;
  the row matches.

## Reasoning

**Kind.** This is the register's own precedence rule — it governs the whole
document and every gate the register defines. It is not a `register_row`: it has
no register ID, no Status cell, no priority, and no "Required evidence /
acceptance" column entry (`register_id: null`, `priority: null`,
`source_status: null`), whereas all 60 register rows are table rows in sections
A-F with those fields populated. It is not a `phase_gate_clause`: it defines no
exit condition. `authority_clause` with `source_title` "Register authority rule"
is correct.

**Derivation rule.** Fixed by kind: goal L243 and
`validate_ledger_structural.py:1511` require `PROGRAM_WIDE_ACTIVE_CONTROL` for
`authority_clause`; `:1547-1549` then forces `related_register_ids == []`,
`authority_effect is None`, and `derived == "REQUIRED_NOW"`. The stored values
match, and the substantive check the rule leaves open passes: a rule stating that
*this register* outranks narrative reviews for *all* implementation gates is
program-wide by construction, not scoped to any one decision.

**Related register IDs.** `[]` is right on the merits as well as by rule. The
clause's subject is the register as a whole; naming any subset of the 60 register
IDs would falsely narrow a document-level precedence rule, and naming all 60
would be padding, which goal L232-235 forbids ("neither may be padded or inferred
from the other").

**Provenance cross-check.** `authority_rank` is 2, the value carried by every
register-sourced row (60 register rows, 35 phase gates, 13 deferrals, 8 scale
triggers, 3 `AUTH-REG-*`), against 3 for every disposition-report-sourced row
including `AUTH-DISP-001`. The rank is document provenance, and it is consistent
with — not evidence for — the precedence this clause asserts.

**Source anchor.** `AUTHORITY-RULE-001`, a clause ordinal. Verified unique within
the register path: zero duplicate `source_anchor` values and zero duplicate
`(source_start_line, source_end_line)` spans among all rows sourced from that
file. The same literal is used by `AUTH-DISP-001` in the disposition-report path;
goal L182 requires uniqueness within a path only, so this is compliant.

**Disposition and gate refs.** Both `[]`. `gate_refs` is a register-row-only
field — nonempty on 39 of 60 register rows and pinned by the `gate_map` equality
at `validate_ledger_structural.py:2660-2664`; all 109 non-register canonical rows
carry `[]`. For `disposition_refs` I examined the strongest candidate
specifically: disposition finding **T-3** ("Gate wording lives in multiple
places", L293) disposes that "the implementation register should own the live gate
wording", which is the finding this register clause implements. T-3 is
nonetheless represented where the ledger's convention puts it — as `DISP-T-3`
(`disposition_refs: ["T-3"]`) and on the register rows `REG-B-03` and `REG-C-11`
(`["T-3","R-5"]`). `disposition_refs` is populated on exactly three closed
populations (56 register rows via the curated crosswalk, 32 `DISP-*`
self-identifications, and the 8 `SCALE-*` rows pinned at `:2652-2653`); all 73
other canonical rows carry `[]`. `[]` here is the uniform treatment, and no goal
or validator rule requires the ref.

**Activation predicate.** `null`, required for a `REQUIRED_NOW` component (goal
L288-290).

**Applicable review slot.** Non-register canonical row, so
`validate_ledger_preimplementation.py:200-204` appends `SCOPE`;
`scope_derivation.semantic_review` is present, non-`null`, `PENDING`, with exactly
the 10-key `PENDING` set and no role-binding keys. This is the applicable slot.

**Input-side observation (covered by `reviewed_input_sha256`, not by this
projection).** `AUTH-REG-001` is the **only** row in the ledger carrying a
`SPEC_EPIC` `tracked_work` entry (`WORK-SPEC-EPIC` → bead `eqos-0xb`), and the
only `authority_clause` with a non-empty `bead_ids`. That is coherent: the clause
that makes the register authoritative for implementation gates is the natural
anchor for the program's spec epic. It is checked and consistent —
`work_type: BEAD` forces `spec_id: null` and `content_sha256: null`
(`validate_ledger_structural.py:697-712`), and `legacy_sources <= typed_sources`
holds (`:744`) since `bead_ids == ["eqos-0xb"]`. It does not affect the `SCOPE`
inventory, which does not cover `tracked_work`.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `AUTH-REG-001`'s scope derivation is correct at the input bytes pinned
above.
