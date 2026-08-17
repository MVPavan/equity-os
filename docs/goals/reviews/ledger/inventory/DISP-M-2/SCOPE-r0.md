# Inventory review — DISP-M-2 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-M-2` |
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
{"activation_predicate":null,"disposition_refs":["M-2"],"gate_refs":[],"related_register_ids":["B-05","B-11","C-03"],"scope_derivation":{"applicable_spec_ids":["S12"],"authority_effect":"ACTIVE_CONTROL","derived_program_disposition":"REQUIRED_NOW","related_register_ids":["B-05","B-11","C-03"],"rule":"AUTHORITATIVE_OCCURRENCE"}}
```

Digests observed at review time, **pre-record** (the recorder must recompute both
after its Phase A evidence append, per recording design r2 §3.4 — appending review
evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `ce4c0fd031780e4c18e68be9b8818ab48dc62b5febf55d248a507b360163c03e`
- `reviewed_inventory_sha256` (pre-record): `99d66421e14a6368e53ee1d49c90408a3d26e2f7fac048600ac852d48536642a`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` lines 130-166, anchor
`M-2`, `source_title` "Fact identity and revision semantics":

> ### M-2 — Fact identity and revision semantics
>
> **Disposition: Accept; the required model is richer than a single key.**
>
> The system needs to distinguish four concepts:
>
> 1. **source occurrence:** the value as it appears in a specific source location;
> 2. **extraction result:** parser/model output for that occurrence and parser version;
> 3. **economic measurement slot:** the intended metric, entity, period, scope, dimensions, and definition;
> 4. **approved canonical selection:** the observation Funda currently uses for a specified knowledge cutoff.
>
> A robust design should include:
>
> ```text
> measurement_key
>   = entity
>   + metric definition/version
>   + period
>   + statement/consolidation scope
>   + dimension set
>   + accounting/adjustment basis
>
> observation_id
>   = immutable source occurrence
>
> revision_family_id
>   = observations believed to represent the same measurement slot
>
> revision_reason
>   = issuer restatement
>   | source correction
>   | parser re-extraction
>   | manual correction
>   | normalization-policy change
> ```
>
> A parser upgrade should normally create a new extraction result, not silently rewrite the economic observation. Restatements, reclassifications, and segment-definition changes require explicit reconciliation rather than automatic supersession by key.


Recomputed this round against current bytes:

- `source_hash` over the whole file → `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`, equal to the stored value.
- `text_digest` over the normalized L130-166 span
  (CRLF-to-LF normalized, surrounding ASCII whitespace trimmed) →
  `96f0c2eb2f7b560d54ec98d18c6515a90048f6093ebe3942ba5d4396103ba24f`, equal to the stored value.
- `required_acceptance_text` equals that normalized span byte for byte.
- Every `evidence_refs` object on this row was re-hashed against current bytes and
  matches its stored `content_sha256`.

## Reasoning

**Kind.** `### M-2 — Fact identity and revision semantics`, ordinal `M-2`,
opening `**Disposition: Accept; the required model is richer than a single
key.**`. At 37 lines (report L130-166) it is the longest occurrence in this batch
and the only one containing a fenced pseudo-schema block; that does not change the
kind, since the fenced block is part of the exact span the report publishes under
the `M-2` heading, and the span is inventoried whole.

**Derivation rule.** `AUTHORITATIVE_OCCURRENCE` forced by kind (goal L242,
`validate_ledger_structural.py:1510`); `authority_effect` `ACTIVE_CONTROL` derives
`REQUIRED_NOW` (`:1558-1559`); `activation_predicate` `null` (goal L288-290).

**Applicable spec IDs.** `["S12"]`. The goal's 25-spec table lists S12's
disposition references as exactly `M-2` — S12 is one of the few specs owning a
single disposition. Single spec, so `primary_spec` is forced non-null
(`:2473-2476`) and carries S12 ("Observation/fact identity, revision, and schema
evolution") with the exact title and path.

**Related register IDs.** `["B-05", "B-11", "C-03"]`:

- `B-11` — "Specify fact identity, revision-family, and correction semantics —
  Source occurrence, extraction result, measurement key, revision family, and
  canonical selection are distinguished; issuer restatement, source correction,
  parser re-extraction, manual correction, and normalization-policy change have
  separate reasons". This is the clause's four concepts and its five
  `revision_reason` values, restated in the register. It is the primary mapping.
- `B-05` — "Derive minimum source and fact schemas from actual use — Schema
  supports raw/normalized values, dimensions, scope, source location, valid time,
  knowledge time, revisions, definition version" ← the clause's `measurement_key`
  components (entity, metric definition/version, period, statement/consolidation
  scope, dimension set, accounting/adjustment basis).
- `C-03` — "Implement append-only observation and revision model — Restatements
  and conflicting observations are preserved; no silent overwrite; model follows
  B-11 identity semantics" ← "A parser upgrade should normally create a new
  extraction result, not silently rewrite the economic observation."

Candidates examined and rejected. `B-10` (decide which speculative blueprint fields
to remove or defer) — owned by the same spec S12, which is exactly the pull the
contract warns about: goal L233-235 separates artifact applicability from source
semantics and forbids inferring one from the other. The clause prescribes identity
semantics, not field-retention decisions. `B-12` (versioned metric and predicate
registries) — the clause's `measurement_key` includes "metric definition/version",
but M-2 *consumes* a definition version whereas registry governance is
`DISP-M-3`'s control, which relates `B-06` and `B-12`.

**Disposition and gate refs.** `disposition_refs == ["M-2"]`; `gate_refs == []`.

**Applicable review slot.** Non-register canonical row; `SCOPE` applies; the
`semantic_review` slot is present, `PENDING`, 10 keys, no role-binding keys.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records only
that `DISP-M-2`'s scope derivation is correct at the input bytes pinned above.
