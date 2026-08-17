# Inventory review — DISP-T-2 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-T-2` |
| `review_type` | `SCOPE` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `4e983789-a352-4ab6-9d42-4e7bdc2941f6` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-15T13:22:11Z` |

Role binding: `CONTEXT.md` "Agent roles (harness-wide)" L137-139 and L147 bind
`REVIEWER` to Claude Opus 5 at high effort, in an agent and context independent
of any `IMPLEMENTER` that produced the reviewed content. The digest above is the
`CONTEXT.md` bytes at review time and is an immutable historical capture.

## Input hashes read for this review

| Input | SHA-256 |
|---|---|
| `docs/goals/equity-os-blueprint-completion.md` (active goal contract) | `f15f7ab5a4e425dec3877ab7f1f7594687979060e4dbcd49390a8a8d5fedb85f` |
| `docs/goals/equity-os-blueprint-component-ledger.jsonl` (canonical ledger) | `de236d7e8dcf02e307ec58797f5722ae2f85d1d8cdba57d4ecc07df5383c9c97` |
| `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` (pinned v2 decision register) | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| `docs/blueprint/funda-third-order-review-disposition-report.md` (pinned third-order disposition report) | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| `scripts/equity_os_blueprint/validate_ledger_structural.py` (structural validator) | `731d0d8b208b577967c92e3992e7ec1a4333cdecbf89f6951c32d2ec469436f9` |
| `scripts/equity_os_blueprint/validate_ledger_preimplementation.py` (preimplementation validator) | `f7a225a1f99cb85c92cde3094505a92a746552280eb45dae0253a71ab9048013` |
| `scripts/equity_os_blueprint/extract_goal_validators.py` (extractor) | `5d20d796666d1154fb3c84ba4fa7407ee82819510a5ac06254f7f4a3126c6f2a` |
| `docs/goals/equity-os-blueprint-human-review-needed.md` (canonical human-review artifact) | `094fcdfab74a3f4c6fdb82b1520fc4d13b636ac0e9ed10194e5d607aed2ce9af` |
| `CONTEXT.md` (role binding) | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r2.md` (artifact format, design r2 §2.2) | `adf908ac8cec01a55a53438624c6a8913f673f5b7cecd3e955fc4919f73803fb` |

Fresh structural validation at these exact bytes:
`python3 scripts/equity_os_blueprint/validate_ledger_structural.py --repo-root .`
→ exit `0` (run at review time). Every `evidence_refs` entry on this row was
additionally re-hashed by hand against its current target bytes this round and
matched.

## Reviewed inventory, exactly as read

`review_inventory_projection(row, "SCOPE")` — canonical JSON:

```json
{"activation_predicate":null,"disposition_refs":["T-2"],"gate_refs":[],"related_register_ids":["A-13"],"scope_derivation":{"applicable_spec_ids":["S08"],"authority_effect":"ACTIVE_CONTROL","derived_program_disposition":"REQUIRED_NOW","related_register_ids":["A-13"],"rule":"AUTHORITATIVE_OCCURRENCE"}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `b3975a80328c84a4e3452fc0995aaa8fec7b7a2d2f31c43dfd0f182854384aba`
- `reviewed_inventory_sha256` (pre-record): `8d64997fade4b68b964fda85d4b2daece5bfd7e37fa5cd1007b5c9b7f35198fb`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` lines 274-291, anchor `T-2`, title "Success metrics are scattered":

> ### T-2 — Success metrics are scattered
>
> **Disposition: Accept.**
>
> Create one versioned success-metric contract covering definitions, units, measurement procedures, and phase applicability for:
>
> - factual accuracy;
> - citation correctness;
> - numerical traceability;
> - unsupported-claim rate;
> - analyst minutes;
> - verification time per claim;
> - coverage capacity;
> - latency;
> - model/tool cost;
> - failure and retry rates.
>
> All phase gates should reference this contract.

- `source_hash` recomputed over the whole file → `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`, matching the row.
- `text_digest` recomputed over the normalized L274-291 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `34af3a7c44b6c048ae93b3e489f9e1441f899f132586806c924b753e891905e2`, matching the row.
- `required_acceptance_text` equals that normalized span byte for byte
  (checked by comparison, not by eye).
- The crosswalk for this row is pinned by the structural validator at
  `validate_ledger_structural.py:2427-2479` (`EXPECTED_DISPOSITION_CROSSWALK`),
  which fixes `applicable_spec_ids` and `related_register_ids` and derives the
  `primary_spec` shape from the spec count.

## Reasoning

**Kind.** Numbered §4 traceability finding, ordinal `T-2`, explicit
`**Disposition: Accept.**` line, and the batch's longest span (L274-291) because
the clause enumerates ten metric families and closes with a cross-reference
sentence at L291. All eighteen lines are one occurrence with one disposition, so
one `disposition_item` row is right; splitting the bullet list into separate
components would invent occurrences the source does not have.

**Derivation rule.** `AUTHORITATIVE_OCCURRENCE` (goal L237-245;
`validate_ledger_structural.py:1510`), with `applicable_spec_ids` as the only
kind-specific key (`:1502`).

**Authority effect.** `ACTIVE_CONTROL`; derives `REQUIRED_NOW` directly, matching
both stored disposition fields.

**Related register IDs.** `["A-13"]`. The clause demands "Create one versioned
success-metric contract covering definitions, units, measurement procedures, and
phase applicability" for ten named metric families. A-13 ("Freeze success-metric
contract", register L43) is that contract, and its pinned acceptance text lists
the same families — "factual accuracy, citation correctness, numerical
traceability, unsupported claims, analyst minutes, per-claim verification time,
coverage capacity, latency, cost, failure/retry rate, and phase applicability".
I specifically tested whether C-18 belongs here as well, since "coverage
capacity" appears in both this clause and C-18, and since `DISP-M-8` relates to
both A-13 and C-18. It does not: T-2 demands that the *contract define* coverage
capacity as a metric, whereas C-18 is the validation row that measures throughput,
and `DISP-M-8` is the occurrence that controls C-18. Adding C-18 here would
attach a row whose obligation this clause does not change.

**Applicable spec IDs and `primary_spec`.** `["S08"]`, matching REG-A-13's owning
spec. One spec, so `primary_spec` is the object form (`:2474-2476`) pointing at
`docs/specs/equity-os-s08-success-metrics-budgets-capacity.md`; HR-0004 touched
only `human_review_id` here.

**The L291 sentence and `gate_refs`.** "All phase gates should reference this
contract" is inside the span and inside `required_acceptance_text`, so it is
inside this component's obligation. It is deliberately *not* expressed as
`gate_refs`: that field is populated only on register rows through the `gate_map`
equality (`:2660-2664`), and all 109 non-register canonical rows carry `[]`.
`gate_refs == []` here is the contract's uniform treatment, not a dropped
reference — the cross-reference obligation lives in the acceptance text.

**Predicate, refs, slot.** `activation_predicate == null` for `REQUIRED_NOW`
(goal L288-290); `disposition_refs == ["T-2"]` self-identifies;
`scope_derivation.semantic_review` is the applicable slot and is `PENDING`.

**Restatement check.** `ALIAS-013` (L36), `ALIAS-020` (L411), `ALIAS-041` (L481)
and `ALIAS-043` (L487) all resolve to `DISP-T-2`. Four derivative restatements is
unusual but consistent — T-2 is the most cross-referenced finding in the report —
and none displaces the authoritative occurrence at L274-291.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `DISP-T-2`'s scope derivation is correct at the input bytes pinned above.
