# Inventory review — DISP-6-8 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-6-8` |
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
{"activation_predicate":null,"disposition_refs":["6.8"],"gate_refs":[],"related_register_ids":["A-02","B-02"],"scope_derivation":{"applicable_spec_ids":["S05"],"authority_effect":"ACTIVE_CONTROL","derived_program_disposition":"REQUIRED_NOW","related_register_ids":["A-02","B-02"],"rule":"AUTHORITATIVE_OCCURRENCE"}}
```

Digests observed at review time, **pre-record** (recorder recomputes after
Phase A, recording design r2 §3.4):

- `reviewed_input_sha256` (pre-record): `4ac020791efc6d89879a53bf4e62669ee70417c044f87dcdf4f99572125221d9`
- `reviewed_inventory_sha256` (pre-record): `83801ec669d496a97604d51ea38c54ffeaeb4b49e0ca9b20c611ee54c21dce49`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` L383-394 — the
longest span in this batch, twelve lines including a fenced `text` block:

> ### 6.8 The repaired measurement design no longer fits three quarters
>
> The review retains a one-company, three-quarter slice while also requiring a
> manual baseline on quarters not reused for assisted runs. Because B-02
> requires three assisted incremental updates, these conditions cannot all hold
> simultaneously. The minimum internally consistent slice is:
>
> ```text
> Quarter 0: manual baseline + approved bootstrap thesis
> Quarter 1: assisted incremental update 1
> Quarter 2: assisted incremental update 2
> Quarter 3: assisted incremental update 3
> ```
>
> The revised register therefore uses four consecutive quarters. This adds one
> quarter of source material but removes a fundamental experiment-design
> contradiction.

- `source_hash` recomputed → `a9021c15…`, matches.
- `text_digest` recomputed over the normalized L383-394 span, `\n`-joined with
  surrounding ASCII whitespace trimmed →
  `a89f9e82f82755171c1c7daaa8977390c37aa800f0ce8e085f9506d0f86d2323`, equal to
  the stored value. I checked this span specifically because it contains a code
  fence: the fence lines are inside the span, so the digest covers the quarter
  table, and `source_end_line == 394` is the closing fence's line, not the
  paragraph after it.
- `required_acceptance_text` equals that normalized span byte for byte,
  including the fenced block.

## Reasoning

**Kind.** A numbered correction item, `disposition_refs == ["6.8"]` matching the
heading ordinal → `disposition_item`. Note this clause does more than qualify a
statement — it *resolves a contradiction* and prescribes a replacement design.
That is still a disposition of a reviewer statement, at an exact occurrence in
the report; the register change it prescribes is inventoried separately as the
register rows' own current bytes.

**Derivation rule.** `AUTHORITATIVE_OCCURRENCE`, fixed by kind (goal L241;
`validate_ledger_structural.py:1511`). Stored value matches.

**`authority_effect == "ACTIVE_CONTROL"`.** The clause prescribes the slice the
program must run — "The minimum internally consistent slice is: …" and "The
revised register therefore uses four consecutive quarters." Both related register
rows are `Open` / `REQUIRED_NOW`, so `FOLLOW_RELATED_SCOPE` would derive the same
value; I record that the choice is not observationally decisive here, and that
`ACTIVE_CONTROL` is nonetheless correct because the clause is constitutive of the
current design rather than derivative of the registers' status. Not
`REJECTED_PROPOSAL`: the three-quarter slice is superseded, not rejected as
accounted-for scope — and the ledger's only `REJECTED_ACCOUNTED` row is
`DISP-R-1`, which carries a `rejection_record`; this row's is `null`.
`derived_program_disposition == "REQUIRED_NOW"` follows and equals the stored
`program_disposition`.

**Related register IDs — `["A-02", "B-02"]`, verified against the register's
current bytes.** This is the one row in the batch where the discharge is directly
observable in the pinned authority, so I checked it rather than reasoning by
analogy:

- `A-02` (register v2 L32) now reads "Select one discovery company and **four
  consecutive quarters**", with acceptance "Quarter 0 is reserved for the manual
  baseline and bootstrap thesis; Quarters 1–3 are reserved for three assisted
  incremental updates; source package exists for all quarters". That is §6.8's
  fenced table transcribed into the register — the correction's discharge, in the
  authority the ledger mirrors.
- `B-02` (L52) is "Produce three real incremental earnings updates … Quarters 1–3
  each consume the approved preceding thesis". §6.8 names `B-02` explicitly in
  its own text as the constraint that made three quarters impossible, and the
  resolution preserves it unchanged.

Naming both is exactly right: `A-02` is what changed and `B-02` is what was
preserved, and the contradiction lived between them. I checked `B-13` as a third
candidate — §6.8's premise sentence invokes "a manual baseline on quarters not
reused for assisted runs", which is `B-13`'s control ("Quarter 0 is not reused
for assisted work") — and rejected it: `B-13` appears in the clause as an
*unchanged premise*, not as scope the clause governs. The resolution satisfies
`B-13` by adding a quarter rather than by modifying it, and `A-02`'s current
acceptance already encodes the non-reuse. Listing `B-13` would assert that this
correction governs the reviewer-bias controls, which it does not.

**Applicable spec IDs — `["S05"]`.** S05 is "Discovery-company vertical slice,
manual baseline, and bootstrap thesis" — the artifact that must carry the
four-quarter design. Exactly one spec applies, so
`validate_ledger_structural.py:2473-2475` requires a non-null `primary_spec`; the
row carries `spec_id "S05"` with matching title and path
`docs/specs/equity-os-s05-discovery-company-vertical-slice.md`, which is also its
`SPEC-DRAFT` evidence target. Consistent.

**Disposition and gate refs.** `disposition_refs == ["6.8"]`; `gate_refs == []`,
the uniform value for all 109 non-register canonical rows. The gate reach is
carried by the register rows: `REG-A-02`'s `gate_refs` are `['PG-0A-03']` and
`REG-B-02`'s are `['PG-05-02']` — the Phase 0A and Phase 0.5 gates where the
slice design is actually tested.

**Activation predicate.** `null`, required for `REQUIRED_NOW` (goal L288-290).

**Applicable review slot.** Non-register canonical row →
`scope_derivation.semantic_review` is the applicable `SCOPE` slot
(`validate_ledger_preimplementation.py:200-204`). Present, `PENDING`, 10-key set,
no role-binding keys.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `DISP-6-8`'s scope derivation is correct at the input bytes pinned
above.
