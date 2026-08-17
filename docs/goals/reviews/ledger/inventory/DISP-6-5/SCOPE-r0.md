# Inventory review — DISP-6-5 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-6-5` |
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
{"activation_predicate":null,"disposition_refs":["6.5"],"gate_refs":[],"related_register_ids":["E-10"],"scope_derivation":{"applicable_spec_ids":["S25"],"authority_effect":"ACTIVE_CONTROL","derived_program_disposition":"REQUIRED_NOW","related_register_ids":["E-10"],"rule":"AUTHORITATIVE_OCCURRENCE"}}
```

Digests observed at review time, **pre-record** (recorder recomputes after
Phase A, recording design r2 §3.4):

- `reviewed_input_sha256` (pre-record): `916bbb948f34a0792518fa5c39efdc874dbee5f6bf88052c8c2b12a2e59ddf5a`
- `reviewed_inventory_sha256` (pre-record): `250501cbfa5abc69d03c43e410d01e3881bbaaf879c20470282f386f3a321164`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` L371-373:

> ### 6.5 Model-weight leakage is scoped to historical claims
>
> It is a standing caveat for historical LLM replay and agent-alpha claims. It
> is not a reason to weaken current-period evidence controls or block the
> current earnings-review MVP.

- `source_hash` recomputed → `a9021c15…`, matches.
- `text_digest` recomputed over the normalized L371-373 span →
  `82f00975f69fda912663f80143996c5fe812213cfb7a8288cc72dbc9a3bee314`, equal to
  the stored value.
- `required_acceptance_text` equals that span byte for byte.

## Reasoning

**Kind.** A numbered correction item, `disposition_refs == ["6.5"]` matching the
heading ordinal → `disposition_item`.

**Derivation rule.** `AUTHORITATIVE_OCCURRENCE`, fixed by kind (goal L241;
`validate_ledger_structural.py:1511`). Stored value matches.

**`authority_effect == "ACTIVE_CONTROL"` — load-bearing here, with its own
argument.** The single related register row `E-10` is `Deferred` /
`CONDITIONAL_UNACTIVATED`, so `FOLLOW_RELATED_SCOPE` would aggregate to
`CONDITIONAL_UNACTIVATED` and force a non-null `activation_predicate` (goal
L282-286). `ACTIVE_CONTROL` is right, and the reason is sharper than on
`DISP-6-4`: this clause's **second sentence protects currently active scope** —
"It is not a reason to weaken current-period evidence controls or block the
current earnings-review MVP." A control that prevents a dormant concern from
being used to relax live controls has work to do *now*, on `REQUIRED_NOW` scope,
and would be inert precisely when it is needed if its own disposition tracked
`E-10`'s dormancy. Not `REJECTED_PROPOSAL` — the leakage concern is retained in
full as "a standing caveat", merely bounded, and the ledger's only
`REJECTED_ACCOUNTED` row is `DISP-R-1`. `derived_program_disposition ==
"REQUIRED_NOW"` follows and equals the stored `program_disposition`.

**Related register IDs — `["E-10"]`, and why the second sentence adds none.**
`E-10` (register v2 L118) is "Publish historical-replay leakage policy",
acceptance: "Store/tool leakage controls are tested; model-weight leakage is
disclosed as an uncontrollable limitation; historical LLM results are not
represented as clean alpha evidence". The clause's first sentence maps onto that
verbatim. The second sentence names two things it does *not* reach: current-period
evidence controls (whose register home is `C-15`, "Enforce run knowledge cutoff
across stores and tools" — also `E-10`'s declared dependency) and the current
earnings-review MVP (`B-01`/`B-02`). I considered adding `C-15` and rejected it
on the clause's own terms: `related_register_ids` records the register semantics a
clause **governs**, and §6.5 governs `C-15` only by *excluding* it. Listing `C-15`
would assert the opposite of what the sentence says and would drag an `Open`,
`REQUIRED_NOW` row into the scope of a caveat that explicitly spares it. One ID,
exact, unpadded — and the exclusion is preserved in the acceptance text rather
than in the ID array, which is the right place for it.

**Applicable spec IDs — `["S25"]`.** S25 is "Controlled quant validation and
historical-replay leakage" — the artifact that must carry the caveat and its
bound. Exactly one spec applies, so `validate_ledger_structural.py:2473-2475`
requires a non-null `primary_spec`; the row carries `spec_id "S25"` with matching
title and path `docs/specs/equity-os-s25-quant-validation-historical-leakage.md`,
which is also what its `SPEC-DRAFT` evidence points at. Consistent. Note that
`primary_spec` being non-null here does not make the row active — goal L184-186
— and that its activity comes from the `ACTIVE_CONTROL` derivation above.

**Disposition and gate refs.** `disposition_refs == ["6.5"]`; `gate_refs == []`,
the uniform value for all 109 non-register canonical rows. `REG-E-10`'s own
`gate_refs` are also `[]` — no `phase_gate_clause` names `E-10` — so this clause
has no phase-gate reach, which is consistent with a deferred E-series policy row
rather than a gap.

**Activation predicate.** `null`, required for `REQUIRED_NOW` (goal L288-290) and
consistent with the `ACTIVE_CONTROL` derivation recorded above.

**Applicable review slot.** Non-register canonical row →
`scope_derivation.semantic_review` is the applicable `SCOPE` slot
(`validate_ledger_preimplementation.py:200-204`). Present, `PENDING`, 10-key set,
no role-binding keys.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition, and activates
nothing: `E-10` remains `Deferred` and `CONDITIONAL_UNACTIVATED`. It records only
that `DISP-6-5`'s scope derivation is correct at the input bytes pinned above.
