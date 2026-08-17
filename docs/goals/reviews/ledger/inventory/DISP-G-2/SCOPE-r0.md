# Inventory review — DISP-G-2 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-G-2` |
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
{"activation_predicate":null,"disposition_refs":["G-2"],"gate_refs":[],"related_register_ids":["B-04"],"scope_derivation":{"applicable_spec_ids":["S18"],"authority_effect":"ACTIVE_CONTROL","derived_program_disposition":"REQUIRED_NOW","related_register_ids":["B-04"],"rule":"AUTHORITATIVE_OCCURRENCE"}}
```

Digests observed at review time, **pre-record** (recorder recomputes after
Phase A, recording design r2 §3.4):

- `reviewed_input_sha256` (pre-record): `8ace6288b1724a3700b9e5b18ddb844eafe2feb9e7cd74e42eaf41da0d8d2083`
- `reviewed_inventory_sha256` (pre-record): `1b5936dc6e6631d24b59bac1819b091508f072c1342bf5617fe9f2026b2bf15d`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` L61-73, under
`## 2. Gate-spec audit` (L44):

> ### G-2 — P90 from three reports
>
> **Disposition: Accept.**
>
> A report-level 90th percentile from three updates is not useful. Phase 0.5
> should report the three observed totals directly rather than manufacture a
> percentile.
>
> Claim-level timing is useful, but it is operational telemetry rather than a
> statistically independent sample. Claims within one report share the same
> company, sources, model run, and reviewer. Therefore:
>
> - record total analyst minutes for each report;
> - record median and distribution summaries for claim dispositions;
> - stratify by claim type and correction category;
> - do not make statistical-significance claims from the three-report pilot;
> - introduce report-level percentiles only after a materially larger run
>   history exists.

- `source_hash` recomputed → `a9021c15…`, matches.
- `text_digest` recomputed over the normalized L61-73 span →
  `d5035c658cea9b446ca8e42e590d955b0627a3a900a49ce261b37c2677da676f`, equal to
  the stored value.
- `required_acceptance_text` equals that span byte for byte, five bullets
  included.

## Reasoning

**Kind — a gate-spec audit finding, still a `disposition_item`.** As with
`DISP-G-1`, the heading sits under the report's gate-spec audit section, but the
occurrence is in the report, not in the register's §F scorecard. Every
`phase_gate_clause` row has `source_path` equal to the pinned register with a
single-line span; this row is at report L61-73. `disposition_item` with
`disposition_refs == ["G-2"]` is correct, and the register-side gate clause it
concerns (`PG-05-04`, "claim-level review telemetry and correction categories are
available without invalid percentile claims") is separately inventoried at its own
path and line.

**Derivation rule.** `AUTHORITATIVE_OCCURRENCE`, fixed by kind (goal L241;
`validate_ledger_structural.py:1511`). Stored value matches.

**`authority_effect == "ACTIVE_CONTROL"`.** Disposition "Accept", followed by five
imperative bullets — three affirmative recording requirements and two
prohibitions. The related register row `B-04` is `Open` / `REQUIRED_NOW`, so
`FOLLOW_RELATED_SCOPE` would coincidentally derive the same value; the choice is
therefore not observationally decisive on this row, and `ACTIVE_CONTROL` is
nonetheless correct because the bullets bind unconditionally — "do not make
statistical-significance claims from the three-report pilot" is a rule about the
pilot, which is Phase 0.5 work, not a rule contingent on `B-04`'s status. Not
`REJECTED_PROPOSAL`: the disposition accepts the finding, and what is discarded
is a *metric* (report-level P90 at n=3), not a component of program scope — the
ledger's only `REJECTED_ACCOUNTED` row is `DISP-R-1`, which carries a
`rejection_record`; this row's is `null`.
`derived_program_disposition == "REQUIRED_NOW"` follows and equals the stored
`program_disposition`.

**Related register IDs — `["B-04"]`.** `B-04` (register v2 L54) is "Measure
analyst review economics without invalid percentiles" — the register title itself
is `G-2`'s disposition, and its acceptance enumerates the clause's bullets almost
one for one: "Record each report's total review time; claim count; per-claim
disposition and time; source-locate and calculation-check time;
accepted/edited/rejected/deferred counts; correction categories; **no
report-level P90 is used at n=3**". This is the tightest single-row match in the
batch; a second ID would be padding.

**Distinguished from the two rows that share or nearly share this pair.**

- `DISP-6-1` maps to the identical `(["S18"], ["B-04"])`. It is a distinct
  occurrence at L355-357 in the corrections section, about *claim-level* sample
  independence; `G-2` is about the *report-level* percentile and the Phase 0.5
  reporting design. Two occurrences, two rows, no duplicate spans — verified
  across all rows on the disposition-report path.
- `DISP-G-3` ("Cross-company economics comparison") maps to
  `(["S18"], ["B-04", "C-12"])` — the same spec and register plus `C-12` ("Set
  Phase 1 analyst-economics gate"). That `G-2` does **not** carry `C-12` is
  correct and checkable: `G-2` is confined to the three-report Phase 0.5 pilot and
  says percentiles come "only after a materially larger run history exists";
  `G-3` is about comparing Phase 1 companies against a baseline, which is exactly
  `C-12`'s subject. Importing `C-12` here would extend `G-2`'s scope into the
  Phase 1 gate it explicitly defers to a later run history.

**Applicable spec IDs — `["S18"]`.** S18 is "MVP universe, analyst-review
economics, and results-season throughput". Exactly one spec applies, so
`validate_ledger_structural.py:2473-2475` requires a non-null `primary_spec`; the
row carries `spec_id "S18"` with matching title and path
`docs/specs/equity-os-s18-universe-review-economics-throughput.md`, which is also
its `SPEC-DRAFT` evidence target.

**Disposition and gate refs.** `disposition_refs == ["G-2"]`; `gate_refs == []`,
the uniform value for all 109 non-register canonical rows. The gate reach is
carried by `B-04`, whose `gate_refs` are `['PG-05-03', 'PG-05-04', 'PG-1-08']` —
including `PG-05-04`, the gate whose wording this finding corrects. The
correction has landed; the linkage lives on the register side, where the contract
derives it.

**Activation predicate.** `null`, required for `REQUIRED_NOW` (goal L288-290).
Note the last bullet reads like a condition ("only after a materially larger run
history exists"), but it conditions when a *metric may be introduced*, not when
this control activates; the control binds now. A typed `activation_predicate`
would be wrong, and would also be forbidden for a `REQUIRED_NOW` row.

**Applicable review slot.** Non-register canonical row →
`scope_derivation.semantic_review` is the applicable `SCOPE` slot
(`validate_ledger_preimplementation.py:200-204`). Present, `PENDING`, 10-key set,
no role-binding keys.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `DISP-G-2`'s scope derivation is correct at the input bytes pinned
above.
