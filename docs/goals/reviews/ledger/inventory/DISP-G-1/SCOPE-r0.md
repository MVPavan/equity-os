# Inventory review — DISP-G-1 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-G-1` |
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
{"activation_predicate":null,"disposition_refs":["G-1"],"gate_refs":[],"related_register_ids":["A-04","C-08","C-09","C-16"],"scope_derivation":{"applicable_spec_ids":["S06","S11","S16"],"authority_effect":"ACTIVE_CONTROL","derived_program_disposition":"REQUIRED_NOW","related_register_ids":["A-04","C-08","C-09","C-16"],"rule":"AUTHORITATIVE_OCCURRENCE"}}
```

Digests observed at review time, **pre-record** (recorder recomputes after
Phase A, recording design r2 §3.4):

- `reviewed_input_sha256` (pre-record): `de150af438f6f0bd491f0a622f5a20f14ebc87528a67adc2ca0674b97332f16e`
- `reviewed_inventory_sha256` (pre-record): `3abb2245b7948014ceef6de14d6e50ed01be7068df46f486c89d4b09f269c364`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` L47-59, under
`## 2. Gate-spec audit` (L44):

> ### G-1 — Narrative reproducibility
>
> **Disposition: Accept with modification.**
>
> The sentence "the report is reproducible from frozen inputs and registered
> versions" is ambiguous. It may be read as bit-identical regeneration, which is
> not a safe guarantee for an LLM-generated narrative. However, the gate is not
> permanently unpassable because the exact approved artifact can be stored and
> retrieved by hash.
>
> Use three separate guarantees:
>
> 1. **Deterministic calculations:** replay under frozen inputs, code, runtime,
>    and operator policy. …
> 2. **Evidence package:** exactly reconstructable from registered source, fact,
>    claim, and cutoff identifiers.
> 3. **Narrative:** the approved published bytes are immutable and bound to a
>    content hash; a later regeneration must be audited against the same
>    approved claim set but need not be text-identical.
>
> This correction belongs in the output contract, run manifest, and Phase 1
> gate.

- `source_hash` recomputed → `a9021c15…`, matches.
- `text_digest` recomputed over the normalized L47-59 span →
  `ea24b6386565704043e6a7fc2ff923d2c514d23384dd07a684420bc1fa0c4572`, equal to
  the stored value.
- `required_acceptance_text` equals that span byte for byte, including the
  numbered guarantees and the closing sentence.

## Reasoning

**Kind — and why a "gate-spec audit" finding is not a `phase_gate_clause`.**
`G-1` sits under the report's gate-spec audit heading, which invites the reading
that it should be inventoried as a `phase_gate_clause`. It should not, and the
distinguishing rule is structural rather than thematic: every `phase_gate_clause`
row in the ledger has `source_path` equal to the pinned register
(`funda-blueprint-implementation-decision-register-v2.md`) and a single-line span
inside the §F scorecard — `PG-1-06`, for instance, is register L155. `G-1` is a
finding *about* gate wording, occurring at L47-59 of the report, and the contract
inventories exact occurrences. `disposition_item` with
`disposition_refs == ["G-1"]` is therefore correct, and the register-side gate
clause it corrects (`PG-1-06`) is separately inventoried at its own path and span.

**Derivation rule.** `AUTHORITATIVE_OCCURRENCE`, fixed by kind (goal L241;
`validate_ledger_structural.py:1511`). Stored value matches.

**`authority_effect == "ACTIVE_CONTROL"`.** The disposition is "Accept with
modification" and the clause prescribes three named guarantees plus their
destination. All four related register rows are `Open` / `REQUIRED_NOW`, so
`FOLLOW_RELATED_SCOPE` would coincidentally derive the same value; the choice is
therefore not observationally decisive here, and `ACTIVE_CONTROL` is nonetheless
correct because "Use three separate guarantees" is an unconditional instruction
that stands independently of any register row's status. Not `REJECTED_PROPOSAL`:
the modification is an acceptance, and the clause is explicit that the gate "is
not permanently unpassable". `derived_program_disposition == "REQUIRED_NOW"`
follows and equals the stored `program_disposition`.

**Related register IDs — `["A-04", "C-08", "C-09", "C-16"]`, the largest set in
the batch, checked one by one against the clause's own three guarantees and its
closing sentence.** The closing sentence is the key: "This correction belongs in
the output contract, run manifest, and Phase 1 gate."

| ID | Register v2 | What in `G-1` puts it here |
|---|---|---|
| `A-04` | L34, "Freeze the first output contract" | the **output contract**, named verbatim in the closing sentence; guarantee 3's "approved published bytes" is an output-contract commitment, and `A-04`'s acceptance already lists "approval record" among the contract's contents |
| `C-09` | L80, "Implement complete run manifest" | the **run manifest**, named verbatim; its acceptance ends "and exact published-artifact hash are registered" — guarantee 3's content-hash binding |
| `C-08` | L79, "Implement minimum deterministic calculations" | guarantee 1, the operator set whose replay is being classified |
| `C-16` | L87, "Implement layered reproducibility and artifact approval" | guarantees 1 and 3 together: "Exact-class operators replay exactly; … evidence package reconstructs exactly; approved narrative bytes are immutable and bound to content hash" — and guarantee 2 as well |

Every element of the clause maps to at least one ID, and every ID is demanded by
at least one element. Nothing is padded: I checked `B-03` (source-of-truth
matrix, for guarantee 2's "evidence package") and rejected it — `C-16`'s
acceptance carries "evidence package reconstructs exactly" explicitly, so
guarantee 2 already has an exact home and `B-03` would be a second, looser one.

**"Phase 1 gate" and `gate_refs == []` — deliberately checked.** The clause names
a gate destination, and this row's `gate_refs` is empty, which looks like a gap
until the derivation rule is applied. `gate_refs` is not authored on non-register
rows: it is derived for register rows from the `phase_gate_clause` →
`related_register_ids` map and asserted by equality at
`validate_ledger_structural.py:2660-2664`, and all 109 non-register canonical rows
carry `[]`. The Phase 1 destination is reached through this row's register IDs:
`REG-C-08`'s `gate_refs` are `['PG-1-04', 'PG-1-06']` and `REG-C-16`'s are
`['PG-1-06']`, and `PG-1-06` reads "deterministic calculations satisfy their
declared exact/tolerance/seeded replay class and the approved narrative is bound
to an artifact hash" — which is `G-1`'s guarantees 1 and 3 as gate wording. The
correction has in fact landed in the Phase 1 gate; the linkage simply lives on
the register side, where the contract puts it. (`REG-A-04`'s `gate_refs` are
`['PG-0A-06']` and `REG-C-09`'s are `[]`, which is consistent — the output
contract is frozen at a Phase 0A gate, and the run manifest is tested through
`C-16`'s gate rather than one of its own.)

**Applicable spec IDs — `["S06", "S11", "S16"]`.** S06 "Output, materiality, and
observable-falsifier contract" carries the output contract (`A-04`), S11 "Run
manifest, knowledge cutoff, and layered reproducibility" carries the run manifest
and the layered guarantees (`C-09`, `C-16`), and S16 "Minimum deterministic
compute" carries the operator set (`C-08`). Three specs apply, so
`validate_ledger_structural.py:2476-2477` requires `primary_spec is None`, and the
row carries `null`; goal L184-186 confirms this "never means inactive".

**Activation predicate.** `null`, required for `REQUIRED_NOW` (goal L288-290).

**The blocking finding does not touch this projection.** `DISP-G-1` is
`delivery_status: REVIEW_BLOCKED` with `review_round: 4` and one `OPEN_BLOCKING`
finding `S06-I7` ("Cross-record digest cycle", Important, load-bearing,
`fix.status: NOT_AUTHORIZED`), shared with `DISP-6-2` and seven other components.
None of `delivery_status`, `open_findings`, `blocked_scope`, or `review_round` is
inside `review_inventory_projection(row, "SCOPE")` — they sit in the input
projection — so this review has a well-defined current object to decide on, and
goal L200 makes `delivery_status` describe "artifact/evidence progress only". The
block is real, is recorded on the row, and is neither resolved nor narrowed here.

**Applicable review slot.** Non-register canonical row →
`scope_derivation.semantic_review` is the applicable `SCOPE` slot
(`validate_ledger_preimplementation.py:200-204`). Present, `PENDING`, 10-key set,
no role-binding keys.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition, and does not
clear the open `S06-I7` block. It records only that `DISP-G-1`'s scope derivation
is correct at the input bytes pinned above.
