# Inventory review — DISP-G-5 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-G-5` |
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
{"activation_predicate":null,"disposition_refs":["G-5"],"gate_refs":[],"related_register_ids":["A-10","C-04"],"scope_derivation":{"applicable_spec_ids":["S06","S13"],"authority_effect":"ACTIVE_CONTROL","derived_program_disposition":"REQUIRED_NOW","related_register_ids":["A-10","C-04"],"rule":"AUTHORITATIVE_OCCURRENCE"}}
```

Digests observed at review time, **pre-record** (the recorder must recompute both
after its Phase A evidence append, per recording design r2 §3.4 — appending review
evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `3784cc2355215c3b43b79bb6c4e70ca20371fbe0348224b6fb1a40df180140c7`
- `reviewed_inventory_sha256` (pre-record): `c7f178972685f9681646bd3c5ef640969c48551cce0337886fa44b1fb247ccbb`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` lines 102-116, anchor
`G-5`, `source_title` "Undefined materiality":

> ### G-5 — Undefined materiality
>
> **Disposition: Accept, but broaden the remedy.**
>
> The validator cannot enforce “all material claims” until materiality is operationally defined. A single quantitative percentage is insufficient because a small number may still be thesis-critical, governance-critical, or legally significant.
>
> The minimum materiality policy should combine:
>
> - **quantitative magnitude:** relative to the relevant statement line, segment, guidance range, equity, enterprise value, or prior assumption;
> - **always-material categories:** guidance, restatements, auditor qualifications, going-concern language, promoter pledges, related-party transactions, capital raises, material dilution, major corporate actions, management changes, and regulatory actions;
> - **thesis relevance:** whether the item changes an assumption, catalyst, risk, valuation input, management-credibility assessment, or thesis breaker;
> - **uncertainty and source conflict:** unresolved contradictions or low-confidence extraction of an otherwise important item;
> - **coverage-level overrides:** company- or mandate-specific thresholds stored with a policy version.
>
> The materiality decision itself should be reviewable and versioned.


Recomputed this round against current bytes:

- `source_hash` over the whole file → `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`, equal to the stored value.
- `text_digest` over the normalized L102-116 span
  (CRLF-to-LF normalized, surrounding ASCII whitespace trimmed) →
  `299faaca255a6bf92cf524c3251a5e269f1e46ad112799f732005b09432542c0`, equal to the stored value.
- `required_acceptance_text` equals that normalized span byte for byte.
- Every `evidence_refs` object on this row was re-hashed against current bytes and
  matches its stored `content_sha256`.

## Reasoning

**Kind.** `### G-5 — Undefined materiality`, a numbered gap finding opening
`**Disposition: Accept, but broaden the remedy.**`, ordinal `G-5`. The qualified
verdict ("broaden the remedy") does not change the kind: the clause still
disposes of one numbered finding and prescribes the remedy's content, which is
`disposition_item`.

**Derivation rule.** `AUTHORITATIVE_OCCURRENCE` forced by kind (goal L242,
`validate_ledger_structural.py:1510`). `authority_effect` is `ACTIVE_CONTROL`.
This is the one field worth stating explicitly for a *qualified* acceptance:
"Accept, but broaden the remedy" is an acceptance that widens the obligation, not
a rejection, so `ACTIVE_CONTROL` — not `REJECTED_PROPOSAL` — is correct, and
`REJECTED_PROPOSAL` is reserved in this ledger for the single `REJECTED_ACCOUNTED`
row `DISP-R-1`. `ACTIVE_CONTROL` derives `REQUIRED_NOW` (`:1558-1559`), matching
the stored value, and `activation_predicate` is `null` (goal L288-290).

**Applicable spec IDs.** `["S06", "S13"]`. The goal's 25-spec table lists `G-5` in
S06's disposition references (`G-1, G-5, R-4, 6.2`) and in S13's
(`G-5, M-3, 6.2`). The split is real: the materiality *policy* is S06's
output/materiality contract, the *claim-validation* consequence is S13's. Two
specs, so `primary_spec` must be `null` (`:2477-2478`), and it is.

**Related register IDs.** `["A-10", "C-04"]`:

- `A-10` — "Define claim materiality policy — Versioned policy combining
  quantitative magnitude, always-material categories, thesis relevance, source
  conflict/uncertainty, and coverage-specific overrides". This is a five-for-five
  match with the clause's five bullets, in the same order. It is the tightest
  register mapping in this batch.
- `C-04` — "Implement materiality- and epistemic-class-aware claim validation …
  contradiction and materiality reasoning are visible" ← the clause's opening
  sentence, "The validator cannot enforce 'all material claims' until materiality
  is operationally defined."

Candidate examined and rejected: `B-06` (minimum typed claim schema), whose
acceptance text carries "materiality result/policy version" and so answers the
clause's closing sentence, "The materiality decision itself should be reviewable
and versioned." Rejected because that sentence is already discharged inside
`A-10` ("**Versioned** policy"), and `B-06` is the related register of
`DISP-M-3`, whose subject is vocabulary and claim-schema governance. Relating it
here would double-inventory one semantic across two disposition items.

Sibling check: `DISP-6-2` carries the identical `(["S06","S13"], ["A-10","C-04"])`
derivation. That is correct rather than duplicative — the contract inventories
exact occurrences, and 6.2 is a separate occurrence at a separate span in the
report's section 6.

**Disposition and gate refs.** `disposition_refs == ["G-5"]`; `gate_refs == []`.

**Blocked state is outside this projection — stated so it is not misread.** This
row is the only one in the batch that is not quiescent: `delivery_status` is
`REVIEW_BLOCKED`, `review_round` is `4`, `human_review_id` is the sorted pair
`["HR-0001","HR-0004"]`, and `open_findings` carries `S06-I7` ("Cross-record
digest cycle", severity Important, `load_bearing: true`, status `OPEN_BLOCKING`)
with a populated `blocked_scope`. None of `open_findings`, `blocked_scope`,
`delivery_status`, or `review_round` is inside the `SCOPE` inventory projection
(goal L430-431), so none of them bears on this verdict; and substantively `S06-I7`
is a digest-cycle defect in the S06 specification artifact, not a defect in this
row's scope derivation. **This CLEAN verdict clears nothing about `S06-I7`.** It
is also correct that the finding sits inside `review_input_projection`: any change
to it stales this review, which is the behaviour the contract wants.

**Applicable review slot.** Non-register canonical row; `SCOPE` applies and
`scope_derivation.semantic_review` is present, `PENDING`, 10 keys, no role-binding
keys.

**Residuals.** None within the `SCOPE` inventory.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records only
that `DISP-G-5`'s scope derivation is correct at the input bytes pinned above.
