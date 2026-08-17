# Inventory review — DISP-G-3 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-G-3` |
| `review_type` | `SCOPE` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `a88da077-0dfc-49ab-bb1a-df4e8266291b` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-15T13:16:03Z` |

Role binding: `CONTEXT.md` "Agent roles (harness-wide)" binds `REVIEWER` to
Claude Opus 5 at high effort, in an agent and context independent of any
`IMPLEMENTER` that produced the reviewed content. The digest above is the
`CONTEXT.md` bytes at review time and is an immutable historical capture.

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

Fresh structural validation at these exact bytes:
`python3 scripts/equity_os_blueprint/validate_ledger_structural.py --repo-root .`
→ exit `0` (run at review time).

## Reviewed inventory, exactly as read

`review_inventory_projection(row, "SCOPE")` — canonical JSON:

```json
{"activation_predicate":null,"disposition_refs":["G-3"],"gate_refs":[],"related_register_ids":["B-04","C-12"],"scope_derivation":{"applicable_spec_ids":["S18"],"authority_effect":"ACTIVE_CONTROL","derived_program_disposition":"REQUIRED_NOW","related_register_ids":["B-04","C-12"],"rule":"AUTHORITATIVE_OCCURRENCE"}}
```

Digests observed at review time, **pre-record** (the recorder must recompute both
after its Phase A evidence append, per recording design r2 §3.4 — appending review
evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `597d6b69a174ea324effbc8f864f9fffa80a9aa35c23049fede97050fa5d99ef`
- `reviewed_inventory_sha256` (pre-record): `b878c561b9e49c4c2c01f42c14cb105262e2a8b372d0358a3fa94cf9ca6ca7e1`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` lines 75-86, anchor
`G-3`, `source_title` "Cross-company economics comparison":

> ### G-3 — Cross-company economics comparison
>
> **Disposition: Accept.**
>
> Comparing assisted work on unfamiliar Phase 1 companies with a manual baseline from the now-familiar discovery company confounds company complexity, analyst familiarity, and tooling effect.
>
> The gate should use:
>
> - a manual baseline for each Phase 1 company or a matched historical quarter;
> - normalized operational measures such as verification time per material claim, source-locate time, and correction time;
> - explicit complexity descriptors such as document count, page count, claim count, and number of reconciliation exceptions;
> - total report time retained as a business metric, but not treated as a portable causal measure by itself.


Recomputed this round against current bytes:

- `source_hash` over the whole file → `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`, equal to the stored value.
- `text_digest` over the normalized L75-86 span
  (CRLF-to-LF normalized, surrounding ASCII whitespace trimmed) →
  `ae5b642d33d770cb932dc756db0b063455ba57c1e449022c40be7290acaa1ea4`, equal to the stored value.
- `required_acceptance_text` equals that normalized span byte for byte.
- Every `evidence_refs` object on this row was re-hashed against current bytes and
  matches its stored `content_sha256`.

## Reasoning

**Kind.** The occurrence is `### G-3 — Cross-company economics comparison`, one
of the disposition report's numbered gap findings, opening `**Disposition:
Accept.**`. It carries the ordinal `G-3`, which the row self-identifies in
`disposition_refs`. A numbered finding with its own disposition verdict is
exactly what `disposition_item` inventories; `authority_clause` (used for the
report's two unnumbered program-wide authority statements) would be wrong
because this clause disposes of one review finding rather than allocating
authority across documents.

**Derivation rule.** Not a free choice: goal L242 fixes `disposition_item` →
`AUTHORITATIVE_OCCURRENCE`, mechanized at `validate_ledger_structural.py:1510`
(`required_rule_by_kind`) and asserted at `:1538`. The stored rule matches.
`authority_effect` is `ACTIVE_CONTROL`, which is correct for an `Accept`
disposition and is one of the three closed values at goal L253-254 and
`:1554-1557`. `ACTIVE_CONTROL` derives `REQUIRED_NOW` directly, with **no**
aggregation over related rows (`:1558-1559`); the stored
`derived_program_disposition` is `REQUIRED_NOW` and `program_disposition`
agrees. `activation_predicate` is `null`, which goal L288-290 requires of every
`REQUIRED_NOW` component.

**Applicable spec IDs.** `["S18"]`. The goal's 25-spec table lists S18's
disposition references as `G-2, G-3, G-4, M-8, 6.1`; no other spec row lists
`G-3` (all 25 rows re-read this round). Because exactly one spec applies,
`validate_ledger_structural.py:2473-2476` forces `primary_spec` non-null and
equal to that spec: the row carries S18 with the exact title and path from the
goal table.

**Related register IDs.** `["B-04", "C-12"]`, and both are the clause's own
semantics rather than topic matches:

- `C-12` — "Set Phase 1 analyst-economics gate … Pre-agreed improvement is
  evaluated against per-company or matched-quarter baselines; workload-normalized
  metrics and total report time are reported; remaining confounds are disclosed."
  The clause's three prescriptions map onto this one-for-one: the manual
  baseline "for each Phase 1 company or a matched historical quarter", the
  normalized operational measures, and total report time "retained as a business
  metric, but not treated as a portable causal measure by itself".
- `B-04` — "Measure analyst review economics without invalid percentiles …
  per-claim disposition and time; source-locate and calculation-check time". This
  is the source of the operational measures the clause requires the gate to use
  (verification time per material claim, source-locate time, correction time).

Candidates examined and rejected. `A-13` (freeze success-metric contract) defines
"per-claim verification time" and is the natural associative pull, but the clause
neither names nor controls the metric contract; `A-13` is listed in the
*Dependencies* column of both `B-04` and `C-12`, so it is reached transitively.
Goal L233-235 forbids padding `related_register_ids` by inference, so adding it
would be wrong. `C-01` (expand to two or three core companies) was rejected for
the same reason: "each Phase 1 company" is a descriptive reference to the
universe, not a control over how it is chosen — that scope belongs to `DISP-M-8`
via `C-18`.

Sibling check: `DISP-G-2`, the other economics disposition under S18, relates
only `B-04`. `G-3` additionally relates `C-12` because it is the only one of the
two that speaks about the Phase 1 gate itself. The asymmetry is right.

**Disposition and gate refs.** `disposition_refs == ["G-3"]` is the row's own
ordinal, matching the source anchor. `gate_refs == []` is correct: `gate_refs` is
populated only on `register_row` rows, by the `by_register` inversion of the 35
`phase_gate_clause` rows, and every non-register canonical row carries `[]`.

**Applicable review slot.** `DISP-G-3` is a non-register canonical row, so
`validate_ledger_preimplementation.py:198-204` appends `SCOPE` to its checks and
`scope_derivation.semantic_review` is the slot this review fills. It is present,
non-`null`, `PENDING`, and carries exactly the 10-key `PENDING` set with no
role-binding keys. Goal L274-280 is the governing rule for that slot.

**Residuals.** None. Every field in the reviewed inventory was checked against
either a mechanized rule or the live source occurrence and the pinned v2 register.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records only
that `DISP-G-3`'s scope derivation is correct at the input bytes pinned above.
