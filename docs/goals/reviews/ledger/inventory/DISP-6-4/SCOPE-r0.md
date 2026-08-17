# Inventory review — DISP-6-4 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-6-4` |
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
{"activation_predicate":null,"disposition_refs":["6.4"],"gate_refs":[],"related_register_ids":["D-02","D-05"],"scope_derivation":{"applicable_spec_ids":["S19","S20"],"authority_effect":"ACTIVE_CONTROL","derived_program_disposition":"REQUIRED_NOW","related_register_ids":["D-02","D-05"],"rule":"AUTHORITATIVE_OCCURRENCE"}}
```

Digests observed at review time, **pre-record** (recorder recomputes after
Phase A, recording design r2 §3.4):

- `reviewed_input_sha256` (pre-record): `9bff37a60e123d84e5b0fc7acfc34c60c1c4b1e2b514b0f8b1747346162b9b48`
- `reviewed_inventory_sha256` (pre-record): `0c499fbff7b9cbbd47d2c566e3cfb31c00b29032d6fbfcbfc9761a80a10e4df6`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` L367-369:

> ### 6.4 D-02 answers a present adoption question
>
> A small-corpus benchmark may correctly show that a simpler store is
> sufficient. Future triggers should reopen the question; the benchmark should
> not be cancelled on the assumption that a larger future corpus might behave
> differently.

- `source_hash` recomputed → `a9021c15…`, matches.
- `text_digest` recomputed over the normalized L367-369 span →
  `25f209688a463141578b299c3781bb9fc36837b5e0e8acc331ae9a1a6fb33afc`, equal to
  the stored value.
- `required_acceptance_text` equals that span byte for byte.

## Reasoning

**Kind.** A numbered correction item, `disposition_refs == ["6.4"]` matching the
heading ordinal → `disposition_item`. The heading names a register decision
(`D-02`) but the row is not a `register_row`: it inventories the *report's
correction about* `D-02`, at the report's own span, not `D-02` itself, which is
separately inventoried as `REG-D-02` at register v2 L98.

**Derivation rule.** `AUTHORITATIVE_OCCURRENCE`, fixed by kind (goal L241;
`validate_ledger_structural.py:1511`). Stored value matches.

**`authority_effect == "ACTIVE_CONTROL"` — the load-bearing decision on this
row, and the reason this component is not like the others in the batch.** Both
related register rows are `Deferred`: `REG-D-02` and `REG-D-05` are
`CONDITIONAL_UNACTIVATED`. So the choice between `ACTIVE_CONTROL` and
`FOLLOW_RELATED_SCOPE` is **observationally decisive here**, unlike on
`DISP-6-1`/`DISP-6-2`/`DISP-6-3` where both would derive `REQUIRED_NOW` anyway:
under `FOLLOW_RELATED_SCOPE` the related-row aggregation (goal L249-253) would
find no `REQUIRED_NOW` and no activation, and would derive
`CONDITIONAL_UNACTIVATED`, which would in turn require a non-null
`activation_predicate` (goal L282-286). I therefore treated this as the question
this review exists to answer, and `ACTIVE_CONTROL` is correct:

- The clause's obligation is not the benchmark. It is a **constraint on how the
  deferred decision is written and retained** — "the benchmark should not be
  cancelled on the assumption that a larger future corpus might behave
  differently" and "future triggers should reopen the question". Those bind the
  program *now*, while `D-02` is dormant; indeed they only have work to do while
  it is dormant, since a cancelled-in-advance benchmark is exactly the failure
  they forbid.
- The register already reflects that the obligation is live: `D-02`'s current
  acceptance text (register L98) ends "result governs current adoption only;
  re-evaluation triggers are precommitted", and `D-05`'s (L101) ends "a
  non-adoption result does not prevent later trigger-based reevaluation". Those
  sentences are the discharge of §6.4 into the register, and they are present at
  the pinned v2 bytes while `D-02` is `Deferred`.
- The contract explicitly contemplates active controls over dormant scope: goal
  L253-258 says `ACTIVE_CONTROL` "makes active program-wide controls terminal
  obligations even when `primary_spec=null`, while dormant feature scope remains
  dormant", and `PG-1-11` — the ledger's only `ACTIVE_NEGATIVE_CONTROL` — is a
  `REQUIRED_NOW` clause whose `related_register_ids` are exactly
  `["D-02", "D-05", "E-03", "E-05", "E-09"]`, i.e. it proves *these same two
  rows* stay dormant while being itself now-required. Controlling a dormant row
  is a present obligation in this contract, not a dormant one.

Not `REJECTED_PROPOSAL`: nothing is rejected; the reviewer's implied "cancel the
benchmark" move is what the clause refuses, which makes the clause a control, not
a rejection record — and the ledger's only `REJECTED_ACCOUNTED` row is
`DISP-R-1`. `derived_program_disposition == "REQUIRED_NOW"` follows and equals
the stored `program_disposition`.

**Related register IDs — `["D-02", "D-05"]`.** `D-02` is named in the clause's
own heading. `D-05` ("Decide GBrain adoption", L101) is the adoption decision the
benchmark feeds, and its acceptance carries the trigger-reopening sentence §6.4
demands; without it, "future triggers should reopen the question" would have no
inventoried home. I checked `D-01` and `D-04` (both are `D-02`'s declared
dependencies) and rejected them: §6.4 says nothing about the prior artifacts or
the due-diligence input, only about the benchmark's present validity and its
reopening. Two IDs, exact, unpadded.

**Applicable spec IDs — `["S19", "S20"]`.** S20 is "Memory benchmark, GBrain due
diligence, and adoption decision" — the artifact that must carry the benchmark's
non-cancellation and its precommitted triggers, and the one this row's
`SPEC-DRAFT` evidence points at. S19 is "MemoryStore interface and conditional
promotion transaction", which is applicable because the clause's premise — "a
simpler store is sufficient" — is a statement about which store sits behind that
interface; a benchmark result that a simpler store suffices is only actionable if
the interface admits one. Two specs apply, so
`validate_ledger_structural.py:2476-2477` requires `primary_spec is None`, and the
row carries `null`; goal L184 is explicit that this "never means inactive".

**Disposition and gate refs.** `disposition_refs == ["6.4"]`; `gate_refs == []`,
the uniform value for all 109 non-register canonical rows. The gate reach is
carried by the register rows: `REG-D-02`'s `gate_refs` are
`['PG-1-11', 'PG-2-01', 'PG-2-02', 'PG-2-06']` and `REG-D-05`'s are
`['PG-1-11', 'PG-2-01', 'PG-2-05', 'PG-2-06']` — including the `PG-1-11`
dormancy control cited above. Nothing is lost by the empty array.

**Activation predicate.** `null`. This follows from `REQUIRED_NOW` and is
required by goal L288-290 ("A component whose derived disposition is
`REQUIRED_NOW` … has `activation_predicate=null`"). It is the visible
consequence of the `ACTIVE_CONTROL` decision above: had the derivation been
`FOLLOW_RELATED_SCOPE`, this field would have had to be a typed predicate, and
its being `null` is consistent with the derivation actually recorded.

**Applicable review slot.** Non-register canonical row →
`scope_derivation.semantic_review` is the applicable `SCOPE` slot
(`validate_ledger_preimplementation.py:200-204`). Present, `PENDING`, 10-key set,
no role-binding keys.

**Residuals.** None. The `ACTIVE_CONTROL` decision is recorded above as verified
against three independent grounds, not as an open doubt.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition, and activates
nothing: `D-02` and `D-05` remain `Deferred` and `CONDITIONAL_UNACTIVATED`. It
records only that `DISP-6-4`'s scope derivation is correct at the input bytes
pinned above.
