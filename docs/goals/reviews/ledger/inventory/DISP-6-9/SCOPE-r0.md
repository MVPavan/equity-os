# Inventory review — DISP-6-9 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-6-9` |
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
{"activation_predicate":null,"disposition_refs":["6.9"],"gate_refs":[],"related_register_ids":["C-08","C-16"],"scope_derivation":{"applicable_spec_ids":["S11","S16"],"authority_effect":"ACTIVE_CONTROL","derived_program_disposition":"REQUIRED_NOW","related_register_ids":["C-08","C-16"],"rule":"AUTHORITATIVE_OCCURRENCE"}}
```

Digests observed at review time, **pre-record** (recorder recomputes after
Phase A, recording design r2 §3.4):

- `reviewed_input_sha256` (pre-record): `db44dad35c6af1da83fa0a3219476e046fcbe6e0690babcb30dbb94f18745941`
- `reviewed_inventory_sha256` (pre-record): `69e3ec6ce8dfdd8d07d0b8c77c75081a21e78dfe16260931e980a49b376a5773`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` L396-398 — the
last item of the corrections section:

> ### 6.9 Bit-exact computation is not universal
>
> The review correctly separates computation from narrative, but "bit-exact"
> should apply only to operators designed for exact replay. Floating-point,
> optimization, and stochastic calculations require declared tolerances, pinned
> environments, and stored seeds as applicable.

- `source_hash` recomputed → `a9021c15…`, matches.
- `text_digest` recomputed over the normalized L396-398 span →
  `bd66104f1f5d50f20c3d0e191ea675db1e6cbc4dc93c5469635b8f66ff054354`, equal to
  the stored value.
- `required_acceptance_text` equals that span byte for byte.

## Reasoning

**Kind.** A numbered correction item, `disposition_refs == ["6.9"]` matching the
heading ordinal → `disposition_item`.

**Derivation rule.** `AUTHORITATIVE_OCCURRENCE`, fixed by kind (goal L241;
`validate_ledger_structural.py:1511`). Stored value matches.

**`authority_effect == "ACTIVE_CONTROL"`.** "require declared tolerances, pinned
environments, and stored seeds" is a mandatory present-tense requirement on the
compute layer, and "'bit-exact' should apply only to operators designed for exact
replay" narrows an existing guarantee that would otherwise be unsatisfiable. Both
related register rows are `Open` / `REQUIRED_NOW`, so `FOLLOW_RELATED_SCOPE`
would coincidentally derive the same value; I record that the choice is not
observationally decisive on this row, and that `ACTIVE_CONTROL` is nonetheless
right because the requirement is unconditional. Not `REJECTED_PROPOSAL`: the
clause opens by endorsing the review ("The review correctly separates computation
from narrative") and narrows rather than rejects.
`derived_program_disposition == "REQUIRED_NOW"` follows and equals the stored
`program_disposition`.

**Related register IDs — `["C-08", "C-16"]`.** `C-16` (register v2 L87),
"Implement layered reproducibility and artifact approval", carries §6.9's
resolution near-verbatim in its acceptance: "Exact-class operators replay exactly;
floating-point/optimization outputs meet declared tolerances; stochastic
operators store seeds and test distributions". `C-08` (L79), "Implement minimum
deterministic calculations", is where the operators being classified live — the
clause's distinction between exact-replay operators and the rest has to be made
about a concrete operator set, and `C-08` is that set. Naming one without the
other would leave either the classification unlocated or the reproducibility
policy unattached to any operator. Two IDs, exact, unpadded.

**Distinguished from `DISP-G-1`, which shares both of these IDs.** `DISP-G-1`
maps to `(["S06","S11","S16"], ["A-04","C-08","C-09","C-16"])` — a superset of
this row's pair. The two are not duplicates and the difference is the right one:
`G-1` (report L47-59) is the *gate-spec audit* finding about **narrative**
reproducibility, and its three guarantees span deterministic calculations, the
evidence package, and the approved narrative bytes — hence it additionally names
`A-04` (the output contract) and `C-09` (the run manifest), and adds S06.
`DISP-6-9` is the *corrections* finding about the **computation** half only, and
its own first sentence explicitly defers the narrative side ("The review
correctly separates computation from narrative"). Its narrower register set is
therefore a faithful reading, not an omission — a `DISP-6-9` that named `A-04`
and `C-09` would claim scope its text disclaims.

**Applicable spec IDs — `["S11", "S16"]`.** S16 is "Minimum deterministic
compute" (the operator classes) and S11 is "Run manifest, knowledge cutoff, and
layered reproducibility" (where declared tolerances, pinned environments, and
stored seeds are recorded per run). Both are needed: a tolerance that is declared
but not recorded per run cannot be replayed against. Two specs apply, so
`validate_ledger_structural.py:2476-2477` requires `primary_spec is None`, and the
row carries `null`; goal L184-186 confirms this "never means inactive". The spec
pair mirrors the register pair (`C-08`→S16, `C-16`→S11).

**Disposition and gate refs.** `disposition_refs == ["6.9"]`; `gate_refs == []`,
the uniform value for all 109 non-register canonical rows. The gate reach is
carried by the register rows: `REG-C-08`'s `gate_refs` are
`['PG-1-04', 'PG-1-06']` and `REG-C-16`'s are `['PG-1-06']`. `PG-1-06` reads
"deterministic calculations satisfy their declared exact/tolerance/seeded replay
class and the approved narrative is bound to an artifact hash" — the Phase 1 gate
that tests exactly this clause's first half. Nothing is lost by the empty array.

**Activation predicate.** `null`, required for `REQUIRED_NOW` (goal L288-290).

**Applicable review slot.** Non-register canonical row →
`scope_derivation.semantic_review` is the applicable `SCOPE` slot
(`validate_ledger_preimplementation.py:200-204`). Present, `PENDING`, 10-key set,
no role-binding keys.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `DISP-6-9`'s scope derivation is correct at the input bytes pinned
above.
