# Inventory review — PG-1-08 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `PG-1-08` |
| `review_type` | `SCOPE` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `c43733f6-8986-4487-8aa6-2f7b5b723107` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-16T03:52:19Z` |

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
{"activation_predicate":null,"disposition_refs":[],"gate_refs":[],"related_register_ids":["B-04","C-12"],"scope_derivation":{"authority_effect":null,"derived_program_disposition":"REQUIRED_NOW","related_register_ids":["B-04","C-12"],"rule":"RELATED_REGISTER_SCOPE"}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 —
appending review evidence mutates `evidence_refs` and therefore the input
projection):

- `reviewed_input_sha256` (pre-record): `30a21cc7444012e779bf57b938faba0ec48366bed6c8c2ddc7355e0e5b48ca02`
- `reviewed_inventory_sha256` (pre-record): `b1e0835cf791a9821a3aa64f47242c2b5d7f9af08ec2872f7d111fbeb68f721d`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md`
L157, the eighth bullet under `### Phase 1 may exit only when`
(L148), inside `## F. Phase-gate scorecard` (L122):

> - analyst effort improves against matched or per-company baselines by the agreed threshold, with confounds disclosed;

- `source_hash` recomputed over the whole register file → `26d51b31…`, matches
  the stored value.
- `text_digest` recomputed over the normalized L157 span →
  `a30cba48f316e0439924b15b38e4971c3febbb97d99243f69a739ca219c4e2dd`, equal to
  the stored `text_digest` and to `EV-PG-1-08-SOURCE.content_sha256`.
- `required_acceptance_text` equals that bullet with the list marker and the
  terminal punctuation stripped, byte for byte.

## Reasoning

**Kind.** The occurrence is one bullet of the register's own §F phase-gate
scorecard. `phase_gate_clause` is the kind that inventories exactly those
bullets: all 35 `PG-*` rows carry `source_path` = the pinned v2 register,
`register_id: null`, and a `source_anchor` of the form `F-<phase>-<ordinal>`.
It is not a `register_row` (those are the §A–§E decision table rows and carry a
`register_id`), not a `disposition_item` (those inventory the third-order
disposition report's numbered findings), and not a `first_release_deferral`
(those are §G).

**Derivation rule.** Goal L239 admits exactly two rules for this kind,
`RELATED_REGISTER_SCOPE` or `ACTIVE_NEGATIVE_CONTROL`, and
`validate_ledger_structural.py:1535-1538` enforces that pair. The choice is
further closed from the other side: `:2520-2523` asserts that the set of
canonical rows using `ACTIVE_NEGATIVE_CONTROL` is exactly `{"PG-1-11"}`. So for
this row `RELATED_REGISTER_SCOPE` is the only representable rule, and the
stored value matches. It is also right on the merits — see below — rather than
right only by elimination. `PG-1-08` requires a measured improvement to have occurred — a
positive obligation — not that a named capability stay dormant.

**Related register IDs — `["B-04", "C-12"]`.** Two IDs, and the pair is
load-bearing rather than duplicative:

- `C-12` (register v2 L83) is "Set Phase 1 analyst-economics gate", acceptance
  "Pre-agreed improvement is evaluated against per-company or matched-quarter
  baselines; workload-normalized metrics and total report time are reported;
  remaining confounds are disclosed." Every element of the gate bullet appears
  here: the baseline choice ("matched or per-company"), the pre-agreed
  threshold, and the confound disclosure. `C-12` is the clause's decision row.
- `B-04` (L54) is "Measure analyst review economics without invalid
  percentiles", which is where the *inputs* to that evaluation are defined —
  total review time, claim counts, per-claim disposition and time, correction
  categories. Without `B-04` there is nothing to evaluate `C-12`'s threshold
  against. The bullet's subject, "analyst effort", is `B-04`'s measurement
  series.

Sorted and unique, as goal L232-233 requires.

**Candidates examined and rejected.**

- `A-13`, "Freeze success-metric contract" (L43), which defines "analyst
  minutes" and "per-claim verification time" as versioned metrics and is a
  declared dependency of both `B-04` and `C-12`. It is upstream *definition*,
  not the Phase 1 evaluation, and it is already claimed by `PG-0A-05` and
  `PG-1-10` (`REG-A-13.gate_refs == ['PG-0A-05', 'PG-1-10']`). Including it here
  would pad the set with a transitively-implied row, which goal L233-235
  forbids.
- `B-13`, "Add reviewer-bias and measurement controls" (L63), which names
  instrumentation symmetry and overhead — arguably a confound. But the bullet's
  "with confounds disclosed" is `C-12`'s own final phrase, word for word, and
  `B-13` speaks to *controlling* bias rather than *disclosing* residual
  confounds in the Phase 1 result. `B-13` is claimed by `PG-05-04`.
- `A-03`, the manual baseline workflow. It supplies the Quarter 0 baseline but
  is a Phase 0A/0.5 execution row already claimed by `PG-05-02` and `PG-05-03`.

**Derived disposition — recomputed.** `REG-B-04`: activation `Open`, current
`Open` → `REQUIRED_NOW`. `REG-C-12`: activation `Open`, current `Open` →
`REQUIRED_NOW`. Goal L248-250's first branch fires on either one alone; the
aggregate is `REQUIRED_NOW`, matching both stored fields.

**`authority_effect` — `null`, and not a choice.**
`validate_ledger_structural.py:1551` asserts `authority_effect is None` for
every `RELATED_REGISTER_SCOPE` row, and goal L252-254 confines the three
`authority_effect` values to `AUTHORITATIVE_OCCURRENCE`. There is no open
judgment here, unlike a `disposition_item`.

**`activation_predicate: null`.** Required by goal L288-290 for a
`REQUIRED_NOW` component. Correct.

**`gate_refs: []`, reverse link closed.** `REG-B-04`'s stored `gate_refs` is
`['PG-05-03', 'PG-05-04', 'PG-1-08']` and `REG-C-12`'s is `['PG-1-08']`; both
contain this row and `validate_ledger_structural.py:2659-2666` asserts the map
is exactly the image of the clauses' `related_register_ids`. That `B-04` carries
three gates is expected — it is measured at Phase 0.5 (`PG-05-03`, `PG-05-04`)
and evaluated at Phase 1 (`PG-1-08`) — and confirms this row is not
double-claiming a register another clause owns exclusively.
`disposition_refs: []`, as for every phase-gate row.

**`primary_spec: null`.** Related-register ownership is supplied (goal L184).
Both `B-04` and `C-12` are owned by S18, so a single owning spec exists in
practice — but `primary_spec` on a phase-gate row is `null` on all 35 rows and
"never determines whether a component is active" (goal L185).

**Applicable review slot.** This is a non-register canonical row, so
`validate_ledger_preimplementation.py:199-204` appends `SCOPE` to its checks and
`scope_derivation.semantic_review` is the slot this review fills. It is present,
non-`null`, `PENDING`, and carries exactly the 10-key `PENDING` set with no
role-binding keys.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `PG-1-08`'s scope derivation is correct at the input bytes pinned
above.
