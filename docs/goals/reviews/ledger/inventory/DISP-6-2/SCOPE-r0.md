# Inventory review — DISP-6-2 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-6-2` |
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
{"activation_predicate":null,"disposition_refs":["6.2"],"gate_refs":[],"related_register_ids":["A-10","C-04"],"scope_derivation":{"applicable_spec_ids":["S06","S13"],"authority_effect":"ACTIVE_CONTROL","derived_program_disposition":"REQUIRED_NOW","related_register_ids":["A-10","C-04"],"rule":"AUTHORITATIVE_OCCURRENCE"}}
```

Digests observed at review time, **pre-record** (recorder recomputes after
Phase A, recording design r2 §3.4):

- `reviewed_input_sha256` (pre-record): `0e2fd7e9c2cf4105c75c87f377dba0054f947578effd9bd3a1db44c5c063b057`
- `reviewed_inventory_sha256` (pre-record): `a6ebbb31f0dc7dafa0018cc0bdbe51d37df37ce83cbfdddbd6ac7ac56bed7db4`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` L359-361:

> ### 6.2 Materiality is not only a financial-statement threshold
>
> The proposed percentage rule is one component. Governance, guidance, thesis
> relevance, and source conflict must also be represented.

- `source_hash` recomputed → `a9021c15…`, matches.
- `text_digest` recomputed over the normalized L359-361 span →
  `295d805b384dfd06599d314799fa46854da59b2a85f8bcff60219cbc74f66d05`, equal to
  the stored value.
- `required_acceptance_text` equals that span byte for byte.

## Reasoning

**Kind and self-identification.** One numbered item of the report's corrections
section, qualifying a named reviewer statement → `disposition_item`, with
`disposition_refs == ["6.2"]` matching the heading ordinal.

**Derivation rule.** Fixed by kind (goal L241; `required_rule_by_kind` at
`validate_ledger_structural.py:1511`): `AUTHORITATIVE_OCCURRENCE`. Stored value
matches.

**`authority_effect == "ACTIVE_CONTROL"`.** The clause's operative verb is "must
also be represented" — a mandatory, present-tense content requirement on the
materiality policy. Not `REJECTED_PROPOSAL`: the percentage rule is explicitly
retained ("is one component"), so nothing is rejected. Not
`FOLLOW_RELATED_SCOPE`: the requirement is unconditional, and — unlike some rows
in this batch where the two would coincide — it matters here that it does not
depend on `A-10`/`C-04` remaining active, since a "must" that lapses when a
related register row changes state would be a weaker obligation than the clause
states. `derived_program_disposition == "REQUIRED_NOW"` follows from
`ACTIVE_CONTROL` (goal L253-256) and equals the stored `program_disposition`.

**Related register IDs — `["A-10", "C-04"]`, and why both.** This is the tightest
register match in the batch. `A-10` (register v2 L40) is "Define claim
materiality policy", acceptance: "Versioned policy combining quantitative
magnitude, always-material categories, thesis relevance, source conflict/
uncertainty, and coverage-specific overrides". Map §6.2 onto it item by item:
"percentage rule" → quantitative magnitude; "governance, guidance" →
always-material categories; "thesis relevance" → thesis relevance verbatim;
"source conflict" → source conflict/uncertainty verbatim. `A-10` is the *policy*
obligation. `C-04` (L75) is "Implement materiality- and epistemic-class-aware
claim validation", acceptance: "contradiction and materiality reasoning are
visible" — the *enforcement* obligation, without which a policy listing those
components is unrepresented at runtime. §6.2 says the components "must be
represented", which is a claim about both the policy and what enforces it, so
naming exactly these two is correct and neither is padding. I checked `B-06`
(claim schema) as a third candidate and rejected it: §6.2 constrains the
materiality dimension, not the claim record's shape.

**Applicable spec IDs — `["S06", "S13"]`.** S06 is "Output, materiality, and
observable-falsifier contract" — the artifact that carries the materiality
contract, and the one this row's `SPEC-DRAFT` evidence points at. S13 is "Claim
schema, vocabulary registries, and evidence validation", which owns `C-04`'s
validation surface. Two specs apply, so `validate_ledger_structural.py:2476-2477`
requires `primary_spec is None`, and the row carries `null`. Goal L184 is
explicit that a null `primary_spec` "never means inactive" — and this row is
`REQUIRED_NOW`.

**Disposition and gate refs.** `disposition_refs == ["6.2"]`; `gate_refs == []`,
which is the uniform value for all 109 non-register canonical rows, since
`gate_refs` is derived only for register rows from the `phase_gate_clause` map
(`validate_ledger_structural.py:2660-2664`). The gate reach here is carried by
`A-10`'s own `gate_refs` — `['PG-0A-05', 'PG-1-01', 'PG-1-02']` — and `C-04`'s
`['PG-1-01', 'PG-1-02']`. Nothing is lost.

**Activation predicate.** `null`, required for `REQUIRED_NOW` (goal L288-290).

**The blocking finding does not touch this projection — checked deliberately.**
`DISP-6-2` is `delivery_status: REVIEW_BLOCKED` with `review_round: 4` and one
`OPEN_BLOCKING` finding `S06-I7` ("Cross-record digest cycle", severity
Important, load-bearing, `fix.status: NOT_AUTHORIZED`). None of
`delivery_status`, `open_findings`, `blocked_scope`, or `review_round` is inside
`review_inventory_projection(row, "SCOPE")`; they sit in the *input* projection,
which is why the `SCOPE` review still has a well-defined, current object to
decide on. That separation is correct on the contract's own terms: goal L200
makes `delivery_status` describe "artifact/evidence progress only", so a blocked
S06 spec says nothing about whether the clause's scope was derived correctly.
The block is real and is recorded on the row; it is simply not this review's
subject, and this review does not clear it.

**Applicable review slot.** Non-register canonical row →
`scope_derivation.semantic_review` is the applicable `SCOPE` slot
(`validate_ledger_preimplementation.py:200-204`). Present, `PENDING`, 10-key set,
no role-binding keys.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition, and does not
resolve or narrow the open `S06-I7` block. It records only that `DISP-6-2`'s
scope derivation is correct at the input bytes pinned above.
