# Inventory review — DISP-G-4 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-G-4` |
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
{"activation_predicate":null,"disposition_refs":["G-4"],"gate_refs":[],"related_register_ids":["A-02","A-03","B-02","B-04","B-13"],"scope_derivation":{"applicable_spec_ids":["S05","S18"],"authority_effect":"ACTIVE_CONTROL","derived_program_disposition":"REQUIRED_NOW","related_register_ids":["A-02","A-03","B-02","B-04","B-13"],"rule":"AUTHORITATIVE_OCCURRENCE"}}
```

Digests observed at review time, **pre-record** (the recorder must recompute both
after its Phase A evidence append, per recording design r2 §3.4 — appending review
evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `f32cbf67b2810b9f0df2e3363f47180e25ddf4b51eec47c3b2f1c494869ab9d3`
- `reviewed_inventory_sha256` (pre-record): `b2a2d9b313645d866676a6eaa1635e7b3e67967c2ab8a07103c9c383eb3cb135`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` lines 88-100, anchor
`G-4`, `source_title` "Practice effect":

> ### G-4 — Practice effect
>
> **Disposition: Accept.**
>
> The same analyst should not manually review a quarter and then use the tool on the same quarter as the primary economics comparison. Familiarity will make the second pass faster.
>
> A practical solo-builder design is:
>
> - use **one baseline/bootstrap quarter plus three later assisted quarters**, making the minimum coherent discovery slice four consecutive quarters;
> - use different quarters for manual and assisted runs;
> - counterbalance order where possible across companies;
> - preserve the confound in the experiment log when it cannot be removed;
> - rely on time-and-motion components, not only whole-report elapsed time.


Recomputed this round against current bytes:

- `source_hash` over the whole file → `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`, equal to the stored value.
- `text_digest` over the normalized L88-100 span
  (CRLF-to-LF normalized, surrounding ASCII whitespace trimmed) →
  `465e02d80bbbc9b68b7c3925848da7324766d637abe2a7b1855a55ddecfac170`, equal to the stored value.
- `required_acceptance_text` equals that normalized span byte for byte.
- Every `evidence_refs` object on this row was re-hashed against current bytes and
  matches its stored `content_sha256`.

## Reasoning

**Kind.** `### G-4 — Practice effect`, a numbered gap finding of the disposition
report opening `**Disposition: Accept.**`, ordinal `G-4`. `disposition_item` is
the right kind for the same reason as every other numbered finding: it disposes
of one review finding and carries its own ordinal.

**Derivation rule.** `AUTHORITATIVE_OCCURRENCE` is forced by kind (goal L242,
`validate_ledger_structural.py:1510`, asserted `:1538`). `authority_effect` is
`ACTIVE_CONTROL`, matching the `Accept` verdict and within the closed set at goal
L253-254 / `:1554-1557`; it derives `REQUIRED_NOW` with no related-row
aggregation (`:1558-1559`), which the stored value matches, and
`activation_predicate` is therefore `null` (goal L288-290).

**Applicable spec IDs.** `["S05", "S18"]`. The goal's 25-spec table lists `G-4`
in **both** S05's disposition references (`G-4, M-1, 6.8`) and S18's
(`G-2, G-3, G-4, M-8, 6.1`), and the clause genuinely straddles them: the
four-quarter discovery slice is S05's subject, the economics comparison is S18's.
Because two specs apply, `validate_ledger_structural.py:2477-2478` forces
`primary_spec` to be `null`, and it is. This is the contract's explicit case
where a null `primary_spec` does not mean inactive (goal L~181).

**Related register IDs.** Five, and each is named by a distinct sentence of the
clause rather than by association:

- `A-02` — "Select one discovery company and four consecutive quarters …
  Quarter 0 is reserved for the manual baseline and bootstrap thesis; Quarters 1–3
  are reserved for three assisted incremental updates" ← "one baseline/bootstrap
  quarter plus three later assisted quarters, making the minimum coherent
  discovery slice four consecutive quarters".
- `A-03` — "Define and perform the manual baseline workflow … the same lightweight
  instrumentation is used in manual and assisted workflows" ← the manual arm of the
  comparison.
- `B-02` — "Produce three real incremental earnings updates … Quarters 1–3" ← the
  assisted arm.
- `B-04` — "Record each report's total review time; claim count; per-claim
  disposition and time; source-locate and calculation-check time" ← "rely on
  time-and-motion components, not only whole-report elapsed time".
- `B-13` — "Quarter 0 is not reused for assisted work; instrumentation is
  symmetric and overhead measured" ← "use different quarters for manual and
  assisted runs", which is the practice-effect control itself.

Candidates examined and rejected. `C-01`/`C-12` were considered because the clause
says "counterbalance order where possible across companies" and mentions
confounds; both were rejected because that sentence is explicitly conditional
("where possible") and because the clause's control target is the Phase 0.5
discovery slice, while `C-12`'s confound disclosure is the Phase 1 gate, already
carried by `DISP-G-3`. Relating them here would pad source semantics with Phase 1
scope this clause does not govern.

Coverage check in the other direction: no sentence of the clause is left without
a related register. That matters because five related IDs is the second-largest
list of any `disposition_item`, and a long list is where padding would show.

**Disposition and gate refs.** `disposition_refs == ["G-4"]` matches the source
anchor; `gate_refs == []` is correct for a non-register row.

**Applicable review slot.** Non-register canonical row, so `SCOPE` applies
(`validate_ledger_preimplementation.py:198-204`) and
`scope_derivation.semantic_review` is this review's slot: present, `PENDING`,
exactly the 10 `PENDING` keys, no role-binding keys.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records only
that `DISP-G-4`'s scope derivation is correct at the input bytes pinned above.
