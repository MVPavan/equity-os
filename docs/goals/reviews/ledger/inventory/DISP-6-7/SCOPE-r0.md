# Inventory review — DISP-6-7 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-6-7` |
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
{"activation_predicate":null,"disposition_refs":["6.7"],"gate_refs":[],"related_register_ids":["E-06","E-07","E-09"],"scope_derivation":{"applicable_spec_ids":["S03","S04"],"authority_effect":"ACTIVE_CONTROL","derived_program_disposition":"REQUIRED_NOW","related_register_ids":["E-06","E-07","E-09"],"rule":"AUTHORITATIVE_OCCURRENCE"}}
```

Digests observed at review time, **pre-record** (recorder recomputes after
Phase A, recording design r2 §3.4):

- `reviewed_input_sha256` (pre-record): `23003399c09174f2f9e342db20b784e4609538c5931ea1c82d666d236b57089e`
- `reviewed_inventory_sha256` (pre-record): `a5a25c6de8fed9edabb440714195ba9585c8d325374b6415a24fff43056ebf24`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` L379-381:

> ### 6.7 Infrastructure assumptions are unsupported by the reviewed files
>
> The report's references to Temporal, Partner, Bodha, an existing homelab, or
> an existing PostgreSQL deployment may come from context outside the two
> documents. They should remain outside the architecture record until explicitly
> confirmed. The underlying general recommendation—do not build a bespoke
> workflow engine and migrate storage only when earned—remains sound.

- `source_hash` recomputed → `a9021c15…`, matches.
- `text_digest` recomputed over the normalized L379-381 span →
  `c6ce2d26a315ea6fdd47aa46db0e3417b77a7ff6ac423003e2e5c9b4ba4d5503`, equal to
  the stored value.
- `required_acceptance_text` equals that span byte for byte.

## Reasoning

**Kind.** A numbered correction item, `disposition_refs == ["6.7"]` matching the
heading ordinal → `disposition_item`.

**Derivation rule.** `AUTHORITATIVE_OCCURRENCE`, fixed by kind (goal L241;
`validate_ledger_structural.py:1511`). Stored value matches.

**`authority_effect == "ACTIVE_CONTROL"` — load-bearing on this row.** All three
related register rows (`E-06`, `E-07`, `E-09`) are `Deferred` /
`CONDITIONAL_UNACTIVATED`, so `FOLLOW_RELATED_SCOPE` would aggregate to
`CONDITIONAL_UNACTIVATED` and force a non-null `activation_predicate` (goal
L282-286). `ACTIVE_CONTROL` is right: the clause's operative sentence — "They
should remain outside the architecture record until explicitly confirmed" — is a
constraint on the architecture record *as it is written today*, and it is
strictest precisely while the E-series rows are dormant. A control that excluded
unconfirmed infrastructure only once that infrastructure had been activated would
have no content. The third sentence ("do not build a bespoke workflow engine and
migrate storage only when earned … remains sound") is likewise a present-tense
standing recommendation. Not `REJECTED_PROPOSAL`: nothing is rejected — the named
assumptions are held outside the record pending confirmation, and the underlying
recommendation is explicitly retained; the ledger's only `REJECTED_ACCOUNTED` row
is `DISP-R-1`. `derived_program_disposition == "REQUIRED_NOW"` follows and equals
the stored `program_disposition`.

**Related register IDs — `["E-06", "E-07", "E-09"]`.** The clause names five
concrete assumptions and one general recommendation. Mapping them:

- *OpenBB-class external tooling* → `E-06` (register v2 L114, "Evaluate OpenBB
  deployment … license and replacement path approved").
- *FinanceHarness / Vibe-Trading-class reuse, and the named third-party
  repositories generally* → `E-07` (L115, "Verify FinanceHarness and Vibe-Trading
  before reuse — Exact repositories, licenses, test quality, provider
  assumptions, and pinned versions recorded"). This is the register row that most
  directly encodes "do not admit an assumed dependency until it is recorded".
- *An execution partner* → `E-09` (L117, "Keep execution in a separate trust
  domain"), which owns the boundary any partner assumption would sit behind.

Each of the three is an unconfirmed-external-dependency decision, which is
exactly the class §6.7 is about. I checked two further candidates and rejected
both:

- The **workflow-engine** half of the third sentence ("do not build a bespoke
  workflow engine") is already inventoried as its own finding, `M-5`, with four
  dedicated `scale_trigger` rows `SCALE-WORKFLOW-01..04` whose
  `disposition_refs` are pinned to `["M-5"]`
  (`validate_ledger_structural.py:2651-2652`).
- The **storage-migration** half ("migrate storage only when earned") is
  likewise inventoried as `R-5`, with `SCALE-SQLITE-01..04` pinned to `["R-5"]`.

So the general recommendation's two limbs are not unrepresented in the program —
they are represented by their own components, and duplicating their register
scope onto this row would double-inventory them. What is unique to §6.7, and what
its related IDs correctly capture, is the *unconfirmed-assumption exclusion*.

**Applicable spec IDs — `["S03", "S04"]`.** S03 is "Optional external-tool
dependency due diligence" — the artifact that must record which external tools
are confirmed, and the one this row's `SPEC-DRAFT` evidence points at. S04 is
"Execution trust-domain boundary", matching `E-09`. Two specs apply, so
`validate_ledger_structural.py:2476-2477` requires `primary_spec is None`, and
the row carries `null`; goal L184-186 is explicit that this "never means
inactive". The spec pair mirrors the register set (`E-06`,`E-07`→S03;
`E-09`→S04), which holds.

**Disposition and gate refs.** `disposition_refs == ["6.7"]`; `gate_refs == []`,
the uniform value for all 109 non-register canonical rows. `REG-E-06` and
`REG-E-07` carry `gate_refs == []`; `REG-E-09` carries `['PG-1-11']`, the
`ACTIVE_NEGATIVE_CONTROL` row that proves the dormant E-series stays dormant.
That is the correct and only gate reach for this clause, and it is reached
through the register rows rather than authored here.

**Activation predicate.** `null`, required for `REQUIRED_NOW` (goal L288-290),
and consistent with the `ACTIVE_CONTROL` derivation recorded above. Note the
clause contains the word "until", which reads like a condition — but the
condition governs when an assumption may *enter* the architecture record, not
when this control activates. The control is unconditional and immediate, so a
typed `activation_predicate` would be wrong here.

**Applicable review slot.** Non-register canonical row →
`scope_derivation.semantic_review` is the applicable `SCOPE` slot
(`validate_ledger_preimplementation.py:200-204`). Present, `PENDING`, 10-key set,
no role-binding keys.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition, and activates
nothing: `E-06`, `E-07`, and `E-09` remain `Deferred` and
`CONDITIONAL_UNACTIVATED`. It records only that `DISP-6-7`'s scope derivation is
correct at the input bytes pinned above.
