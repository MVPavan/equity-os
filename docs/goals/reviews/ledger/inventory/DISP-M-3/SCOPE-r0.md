# Inventory review — DISP-M-3 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-M-3` |
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
{"activation_predicate":null,"disposition_refs":["M-3"],"gate_refs":[],"related_register_ids":["B-06","B-12"],"scope_derivation":{"applicable_spec_ids":["S13"],"authority_effect":"ACTIVE_CONTROL","derived_program_disposition":"REQUIRED_NOW","related_register_ids":["B-06","B-12"],"rule":"AUTHORITATIVE_OCCURRENCE"}}
```

Digests observed at review time, **pre-record** (the recorder must recompute both
after its Phase A evidence append, per recording design r2 §3.4 — appending review
evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `2b97105430ea5512995d0895fe860a01a77f56860b0f38676410e6d1a777ebe2`
- `reviewed_inventory_sha256` (pre-record): `ee25a2af6115ffede22427377fcdbdee9326e60bcad04ecb921830c6a9427708`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` lines 168-180, anchor
`M-3`, `source_title` "Predicate and metric vocabulary governance":

> ### M-3 — Predicate and metric vocabulary governance
>
> **Disposition: Accept with a simpler Phase 0.5 implementation.**
>
> Typed claims are ineffective without controlled predicates and metric definitions. The first version needs:
>
> - a small versioned metric registry;
> - a small versioned claim-predicate registry;
> - aliases and deprecated terms;
> - definition, expected object type, units/dimensions, and scope rules;
> - a human approval rule for additions.
>
> Embedding-assisted duplicate suggestions are optional later. They should not be a Phase 0.5 dependency for a registry containing only dozens of entries.


Recomputed this round against current bytes:

- `source_hash` over the whole file → `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`, equal to the stored value.
- `text_digest` over the normalized L168-180 span
  (CRLF-to-LF normalized, surrounding ASCII whitespace trimmed) →
  `a7d8a6209c47dcce38693046ce19563c89e4dde47e0d9310d3bc949693c5017e`, equal to the stored value.
- `required_acceptance_text` equals that normalized span byte for byte.
- Every `evidence_refs` object on this row was re-hashed against current bytes and
  matches its stored `content_sha256`.

## Reasoning

**Kind.** `### M-3 — Predicate and metric vocabulary governance`, ordinal `M-3`,
opening `**Disposition: Accept with a simpler Phase 0.5 implementation.**`. The
qualifier scopes down the remedy (a small registry now, embedding-assisted dedup
later) but still accepts the finding, so `disposition_item` with an accepting
disposition is the correct inventory.

**Derivation rule.** `AUTHORITATIVE_OCCURRENCE` forced by kind (goal L242,
`validate_ledger_structural.py:1510`); `authority_effect` `ACTIVE_CONTROL` derives
`REQUIRED_NOW` (`:1558-1559`); `activation_predicate` `null` (goal L288-290). Note
that "Accept with a simpler … implementation" is still `ACTIVE_CONTROL`: the
clause narrows *how much* is built now, not *whether* the obligation is live, and
the deferrable part ("Embedding-assisted duplicate suggestions are optional later.
They should not be a Phase 0.5 dependency") is expressed as an explicit
non-dependency rather than as a conditional activation. A predicate here would
have been wrong.

**Applicable spec IDs.** `["S13"]`. The goal's 25-spec table lists S13's
disposition references as `G-5, M-3, 6.2`; no other spec lists `M-3`. Single spec,
so `primary_spec` is forced non-null (`:2473-2476`) and carries S13 ("Claim
schema, vocabulary registries, and evidence validation").

**Related register IDs.** `["B-06", "B-12"]`:

- `B-12` — "Establish versioned metric and predicate registries — Registry
  definitions, aliases, object/unit/dimension rules, addition approval,
  deprecation, and versioning exist; every structured fact/claim resolves to a
  registered entry; embedding-assisted dedup is optional". Every one of the
  clause's five "first version needs" bullets appears here, and so does the
  clause's optionality carve-out for embedding-assisted suggestions.
- `B-06` — "Derive minimum typed claim schema — Subject, registered predicate,
  object, scope, horizon, epistemic class …" ← the clause's opening premise,
  "Typed claims are ineffective without controlled predicates and metric
  definitions."

Candidates examined and rejected. `C-04` (materiality- and epistemic-class-aware
claim validation) — owned by the same spec S13 and topically adjacent, but claim
*validation* is `DISP-G-5`'s control; this clause governs the vocabulary
registries that validation resolves against. `B-05` (minimum source and fact
schemas) — the clause mentions "metric definitions", but fact-schema derivation is
`DISP-M-2`'s control. Both rejections turn on the same rule: goal L233-235 bars
inferring `related_register_ids` from spec ownership.

**Disposition and gate refs.** `disposition_refs == ["M-3"]`; `gate_refs == []`.

**Applicable review slot.** Non-register canonical row; `SCOPE` applies; the
`semantic_review` slot is present, `PENDING`, 10 keys, no role-binding keys.

**Scope of this verdict.** This artifact reviews the `SCOPE` inventory only. The
`APPROVAL` inventory of this same component did **not** come back clean — see
`docs/goals/reviews/ledger/inventory/DISP-M-3/APPROVAL-r0.md`. Because a row's
applicable reviews are recorded all-at-once or not at all (recording design r2
§3.4), this CLEAN `SCOPE` verdict is not recordable while that finding stands.

**Residuals.** None within the `SCOPE` inventory.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records only
that `DISP-M-3`'s scope derivation is correct at the input bytes pinned above.
