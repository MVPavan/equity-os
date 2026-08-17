# Inventory review — DISP-M-1 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-M-1` |
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
{"activation_predicate":null,"disposition_refs":["M-1"],"gate_refs":[],"related_register_ids":["A-11"],"scope_derivation":{"applicable_spec_ids":["S05"],"authority_effect":"ACTIVE_CONTROL","derived_program_disposition":"REQUIRED_NOW","related_register_ids":["A-11"],"rule":"AUTHORITATIVE_OCCURRENCE"}}
```

Digests observed at review time, **pre-record** (the recorder must recompute both
after its Phase A evidence append, per recording design r2 §3.4 — appending review
evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `a0847b1fb1ad50cdd367db2fcad14860cb90cb8494395e0ff27227154cd062d1`
- `reviewed_inventory_sha256` (pre-record): `7d6166b9bce430236d6f10567fe4be7cb831b55845102438e17405216da8dcab`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` lines 122-128, anchor
`M-1`, `source_title` "Thesis cold start":

> ### M-1 — Thesis cold start
>
> **Disposition: Accept.**
>
> The first incremental workflow requires a prior approved thesis, but no bootstrap path exists. Do not expand Phase 0.5 into a full initiation product. Use the first of four consecutive quarters as the manual baseline/bootstrap quarter and create a concise analyst-authored **bootstrap coverage thesis** containing current thesis, key assumptions, management commitments, risks, open questions, and observable falsifiers. Approve and version it before the three later assisted updates.
>
> Full company initiation remains deferred.


Recomputed this round against current bytes:

- `source_hash` over the whole file → `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`, equal to the stored value.
- `text_digest` over the normalized L122-128 span
  (CRLF-to-LF normalized, surrounding ASCII whitespace trimmed) →
  `4168736535342515f6b3b6ddfdf92a4874550aa677fe558d1c719b6e807bbba2`, equal to the stored value.
- `required_acceptance_text` equals that normalized span byte for byte.
- Every `evidence_refs` object on this row was re-hashed against current bytes and
  matches its stored `content_sha256`.

## Reasoning

**Kind.** `### M-1 — Thesis cold start`, a numbered missing-decision finding
opening `**Disposition: Accept.**`, ordinal `M-1`. `disposition_item`.

**Derivation rule.** `AUTHORITATIVE_OCCURRENCE` forced by kind (goal L242,
`validate_ledger_structural.py:1510`); `authority_effect` `ACTIVE_CONTROL` derives
`REQUIRED_NOW` (`:1558-1559`); `activation_predicate` `null` (goal L288-290). The
clause's closing sentence, "Full company initiation remains deferred", is worth
testing against this: it does **not** make the component conditional. What is
deferred is a capability the clause declines to build; the clause's own obligation
(author a bootstrap coverage thesis now) is unconditional, so `REQUIRED_NOW` with
a null predicate is right, and a predicate here would have been a contract
violation under goal L288-290.

**Applicable spec IDs.** `["S05"]`. The goal's 25-spec table lists S05's
disposition references as `G-4, M-1, 6.8`; no other spec lists `M-1`. Single spec,
so `primary_spec` is forced non-null (`:2473-2476`) and carries S05 with the exact
title and path from that table.

**Related register IDs.** `["A-11"]` — a singleton, and exactly right. `A-11` is
"Author and approve bootstrap thesis for the discovery company — Using Quarter 0,
a concise initial thesis, assumptions, management commitments, risks, open
questions, and observable falsifiers are manually written, approved, versioned,
and available before Quarter 1; full initiation remains deferred." Every element
of the clause lands inside it, including the six thesis contents enumerated
identically and the deferral tail.

Candidates examined and rejected. `A-02` (select one company and four consecutive
quarters) — the clause's "Use the first of four consecutive quarters" is a
descriptive reference to the slice `A-02` selects; the slice itself is `DISP-G-4`'s
control, and `DISP-G-4` does relate `A-02`. `A-03` (perform the manual baseline
workflow) — the baseline workflow is `A-03`'s own decision, and the register
already names `A-03` in `A-11`'s Dependencies column, so relating it here would be
inference, which goal L233-235 forbids. A first-release deferral row for "full
company initiation" — not expressible: `related_register_ids` admits only v2
register IDs, and the deferral is inventoried as a `first_release_deferral`
component.

A singleton related list under a singleton spec is the tightest derivation shape
available, and it is warranted here because the clause and `A-11` are near
restatements of one another.

**Disposition and gate refs.** `disposition_refs == ["M-1"]`; `gate_refs == []`.

**Applicable review slot.** Non-register canonical row; `SCOPE` applies and the
`semantic_review` slot is present, `PENDING`, 10 keys, no role-binding keys.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records only
that `DISP-M-1`'s scope derivation is correct at the input bytes pinned above.
