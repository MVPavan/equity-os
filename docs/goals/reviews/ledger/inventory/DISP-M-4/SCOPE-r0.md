# Inventory review — DISP-M-4 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-M-4` |
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
{"activation_predicate":null,"disposition_refs":["M-4"],"gate_refs":[],"related_register_ids":["C-15","E-10"],"scope_derivation":{"applicable_spec_ids":["S11","S25"],"authority_effect":"ACTIVE_CONTROL","derived_program_disposition":"REQUIRED_NOW","related_register_ids":["C-15","E-10"],"rule":"AUTHORITATIVE_OCCURRENCE"}}
```

Digests observed at review time, **pre-record** (the recorder must recompute both
after its Phase A evidence append, per recording design r2 §3.4 — appending review
evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `7756b975f26284b62fb73ea268c8c6c3d987bc84323c5f72b05a63947bc39329`
- `reviewed_inventory_sha256` (pre-record): `70141e48ce1acb14136d68ee40ebe7113355573763aedc499bbfac85a132b41e`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` lines 182-195, anchor
`M-4`, `source_title` "Knowledge-time enforcement and leakage":

> ### M-4 — Knowledge-time enforcement and leakage
>
> **Disposition: Accept, split into two policies.**
>
> **Current and historical data access controls** are implementation requirements:
>
> - every run has a cutoff;
> - SQL, document, memory, and fact retrieval enforce `knowledge_time <= cutoff`;
> - canonical fact and relationship selection is evaluated **as of that cutoff**, so later corrections or restatements do not retroactively rewrite a historical package;
> - tool calls declare whether they are cutoff-aware;
> - historical replay permits only approved archived or time-bounded sources;
> - tests deliberately insert post-cutoff records and verify that retrieval excludes them.
>
> **Model-weight leakage** is different. It cannot be eliminated and must be disclosed for historical LLM evaluation. It does not invalidate current-period earnings review, where the run date is current and the model is not being evaluated as if it were historically ignorant.


Recomputed this round against current bytes:

- `source_hash` over the whole file → `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`, equal to the stored value.
- `text_digest` over the normalized L182-195 span
  (CRLF-to-LF normalized, surrounding ASCII whitespace trimmed) →
  `b75537aa2059b3740ee345a515b8ae6022098917e9b5d78541fbaf9ea02ef131`, equal to the stored value.
- `required_acceptance_text` equals that normalized span byte for byte.
- Every `evidence_refs` object on this row was re-hashed against current bytes and
  matches its stored `content_sha256`.

## Reasoning

**Kind.** `### M-4 — Knowledge-time enforcement and leakage`, ordinal `M-4`,
opening `**Disposition: Accept, split into two policies.**`. The clause is
explicitly two-part — "**Current and historical data access controls** are
implementation requirements" and "**Model-weight leakage** is different" — but it
is one span under one heading with one ordinal, so one `disposition_item` is
correct; splitting it into two components would invent occurrences the report does
not publish.

**Derivation rule.** `AUTHORITATIVE_OCCURRENCE` forced by kind (goal L242,
`validate_ledger_structural.py:1510`); `authority_effect` `ACTIVE_CONTROL`.

**This row is the batch's load-bearing test of the no-aggregation rule.** Its
related registers are one active (`C-15`, Status `Open`) and one dormant (`E-10`,
Status `Deferred`, `REG-E-10` deriving `CONDITIONAL_UNACTIVATED`). Under
`RELATED_REGISTER_SCOPE` or `FOLLOW_RELATED_SCOPE` the derived disposition would
be computed by aggregating those rows; under `ACTIVE_CONTROL` it is **not** —
`validate_ledger_structural.py:1558-1559` sets `derived = "REQUIRED_NOW"` outright,
and goal L252-256 says the same in prose ("This makes active program-wide controls
terminal obligations … while dormant feature scope remains dormant"). So
`derived_program_disposition == "REQUIRED_NOW"` and `activation_predicate is None`
are correct here **despite** relating a dormant register, and this component
activates nothing: `REG-E-10` keeps its own `CONDITIONAL_UNACTIVATED` disposition
and its own `PRODUCT_OWNER_DECISION` activation approval.

**Applicable spec IDs.** `["S11", "S25"]`. The goal's 25-spec table lists `M-4` in
S11's disposition references (`G-1, M-4, 6.9`) and in S25's (`M-4, 6.5`), matching
the clause's own two-policy split: cutoff enforcement is S11's run-manifest and
reproducibility scope, historical-replay leakage is S25's. Two specs, so
`primary_spec` is forced `null` (`:2477-2478`), and it is.

**Related register IDs.** `["C-15", "E-10"]` — one per policy half:

- `C-15` — "Enforce run knowledge cutoff across stores and tools — SQL/document/
  memory retrieval applies `knowledge_time <= cutoff`; canonical selections are
  resolved as of the cutoff so later restatements/corrections do not rewrite
  history; tool gateway records cutoff capability; tests insert and reject
  post-cutoff records". This matches the clause's access-control bullets almost
  line for line, including the as-of-cutoff canonical selection rule and the
  deliberate post-cutoff test.
- `E-10` — "Publish historical-replay leakage policy — … model-weight leakage is
  disclosed as an uncontrollable limitation; historical LLM results are not
  represented as clean alpha evidence" ← the clause's second policy verbatim.

Candidates examined and rejected. `C-09` (complete run manifest) — the clause's
first bullet, "every run has a cutoff", is satisfied by the manifest, but `C-09`
is `DISP-G-1`'s related register and its subject is manifest completeness, not
cutoff enforcement. `E-05` (controlled quant validation) — its acceptance mentions
leakage disclosure among six items, but the clause names the *policy*, which is
`E-10`; `E-05` is `DISP-6-5`'s neighbourhood, not this clause's control.

**Disposition and gate refs.** `disposition_refs == ["M-4"]`; `gate_refs == []`.

**Applicable review slot.** Non-register canonical row; `SCOPE` applies; the
`semantic_review` slot is present, `PENDING`, 10 keys, no role-binding keys.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records only
that `DISP-M-4`'s scope derivation is correct at the input bytes pinned above.
