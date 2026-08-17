# Inventory review — DISP-6-1 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-6-1` |
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
`REVIEWER` to Claude Opus 5 at high effort, in an agent and context independent
of any `IMPLEMENTER` that produced the reviewed content. The digest above is the
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
{"activation_predicate":null,"disposition_refs":["6.1"],"gate_refs":[],"related_register_ids":["B-04"],"scope_derivation":{"applicable_spec_ids":["S18"],"authority_effect":"ACTIVE_CONTROL","derived_program_disposition":"REQUIRED_NOW","related_register_ids":["B-04"],"rule":"AUTHORITATIVE_OCCURRENCE"}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `b96cb3c6b4816ccafd9f0674718ca07228705d66e2145223bff00da613abb1f2`
- `reviewed_inventory_sha256` (pre-record): `b1a10cefa32e5c47b2394a73361259bd5c19c1e220598e44c60f810fba5c941b`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` L355-357, under
`## 6. Corrections to the third-order review` (L350):

> ### 6.1 "Hundreds of claims" do not create hundreds of independent samples
>
> Claim-level telemetry is useful, but claims are clustered within reports and
> companies. Use it for operations and error analysis, not unsupported
> significance claims.

- `source_hash` recomputed over the whole file → `a9021c15…`, matches stored.
- `text_digest` recomputed over the normalized L355-357 span →
  `84e251b4ff1802024369742c4adfad81b14e21072419d331090308c4f2ca47dd`, equal to
  the stored `text_digest`.
- `required_acceptance_text` equals that normalized span byte for byte.

## Reasoning

**Kind.** The occurrence is one numbered item in the report's own corrections
section — a named reviewer statement being qualified by the report. That is
exactly what `disposition_item` inventories: the 32 `DISP-*` rows are the
report's 32 numbered findings (`G-1`…`G-5`, `M-1`…`M-9`, `T-1`…`T-4`,
`R-1`…`R-5`, `6.1`…`6.9`), each carrying its own ordinal in `disposition_refs`.
`disposition_refs == ["6.1"]` is that self-identification and matches the
heading ordinal. It is not an `authority_clause` (it allocates no document
authority) and not a `phase_gate_clause` (it lives in the report, not in the
register's §F scorecard).

**Derivation rule.** Fixed by kind, not chosen: goal L241 maps
`disposition_item` → `AUTHORITATIVE_OCCURRENCE`, mechanized at
`validate_ledger_structural.py:1511` (`required_rule_by_kind`). Stored rule
matches.

**`authority_effect` — the one genuinely open field.** `AUTHORITATIVE_OCCURRENCE`
admits `ACTIVE_CONTROL`, `REJECTED_PROPOSAL`, or `FOLLOW_RELATED_SCOPE` (goal
L253-258). `ACTIVE_CONTROL` is right: the clause's operative sentence is a
present-tense instruction — "Use it for operations and error analysis, not
unsupported significance claims" — that binds any current use of claim-level
telemetry. `REJECTED_PROPOSAL` would be wrong: nothing is rejected here, the
clause *qualifies* a reviewer statement rather than discarding it, and the
ledger's only `REJECTED_ACCOUNTED` row is `DISP-R-1`. `FOLLOW_RELATED_SCOPE`
would happen to derive the same `REQUIRED_NOW` today, because `B-04` is `Open`;
I record explicitly that the choice is therefore **not** observationally
load-bearing at these bytes, and that it is nonetheless the semantically correct
one, because the clause's force does not depend on `B-04`'s status — it
constrains how telemetry may be read whatever the register does.

**Related register IDs — `["B-04"]`.** `B-04` (register v2 L54) is "Measure
analyst review economics without invalid percentiles", whose acceptance already
demands "claim count; per-claim disposition and time … no report-level P90 is
used at n=3". §6.1 governs precisely the epistemic status of that per-claim
series. I checked `B-13` ("Add reviewer-bias and measurement controls",
register L63) as a candidate second ID and rejected it: §6.1 says nothing about
instrumentation symmetry, Quarter-0 reuse, seeded-error drills, or stratified
false-accept/false-reject results. Adding it would be inference from spec
applicability into source semantics, which goal L233-235 forbids ("neither may
be padded or inferred from the other"). One ID, exact, unpadded.

**Applicable spec IDs — `["S18"]`.** S18 is "MVP universe, analyst-review
economics, and results-season throughput"; claim-level review telemetry is its
subject matter. Because exactly one spec applies, `validate_ledger_structural.py`
:2473-2475 requires a non-null `primary_spec` equal to that spec, and the row
carries `primary_spec.spec_id == "S18"` with the matching title and path.

**Distinguished from `DISP-G-2`, which carries the identical pair.** `DISP-G-2`
maps to the same `(["S18"], ["B-04"])`, so a reader could suspect duplication. It
is not: `DISP-G-2` is the *gate-spec audit* finding at L61-73 about a
report-level P90 at n=3; `DISP-6-1` is the *corrections* finding at L355-357
about claim-level sample independence. Distinct occurrences, distinct spans,
distinct claims — and the contract inventories exact occurrences, so two rows is
correct. Verified: the disposition-report path has zero duplicate
`(source_start_line, source_end_line)` spans across all rows.

**Disposition and gate refs.** `gate_refs == []`. No rule populates `gate_refs`
for any non-register kind — it is derived for register rows only, from the
`phase_gate_clause` → `related_register_ids` map pinned at
`validate_ledger_structural.py:2660-2664` — and all 109 non-register canonical
rows carry `[]`. The gate reach of this clause is carried indirectly: `B-04`'s
own `gate_refs` are `['PG-05-03', 'PG-05-04', 'PG-1-08']`, and `PG-05-04` is
"claim-level review telemetry and correction categories are available without
invalid percentile claims" — the gate this correction lands in. Nothing is lost
by the empty array.

**Activation predicate.** `null`, required by goal L288-290 for a component
whose derived disposition is `REQUIRED_NOW`.

**Applicable review slot.** `DISP-6-1` is a non-register canonical row, so
`validate_ledger_preimplementation.py:200-204` appends `SCOPE` to its checks and
`scope_derivation.semantic_review` is the slot this review fills. It is present,
non-`null`, `PENDING`, and carries exactly the 10-key `PENDING` set with no
role-binding keys.

**Residuals.** None. The `authority_effect` reasoning above is recorded as a
verified choice, not an open doubt.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `DISP-6-1`'s scope derivation is correct at the input bytes pinned
above.
