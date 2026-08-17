# Inventory review — DEF-10 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DEF-10` |
| `review_type` | `SCOPE` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `b6d5971a-5871-45c7-aa6f-85ddec86becd` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-15T13:10:53Z` |

Role binding: `CONTEXT.md` "Agent roles (harness-wide)" (L127) binds `REVIEWER`
to an independent subagent and context, and the binding table at L147 records
the current model and effort as Claude Opus 5 at high effort. The digest above
is the `CONTEXT.md` bytes at review time and is an immutable historical capture,
never re-verified against later bytes.

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
→ exit `0` (run at review time). That run re-resolves and re-digests every
`evidence_refs[].path` in the ledger
(`validate_ledger_structural.py:210-233`), so this component's declared
evidence is current against live bytes.

## Reviewed inventory, exactly as read

`review_inventory_projection(row, "SCOPE")` — canonical JSON:

```json
{"activation_predicate":null,"disposition_refs":[],"gate_refs":[],"related_register_ids":[],"scope_derivation":{"authority_effect":null,"derived_program_disposition":"REQUIRED_NOW","related_register_ids":[],"rule":"PROGRAM_WIDE_ACTIVE_CONTROL"}}
```

Digests observed at review time, **pre-record** (the recorder must
recompute both after its Phase A evidence append, per recording design
r2 §3.4 — appending review evidence mutates `evidence_refs` and therefore
the input projection):

- `reviewed_input_sha256` (pre-record): `5a12eef290f5484c1c8f11e35f2865c8d618ba2574369944b5454b3a74955a46`
- `reviewed_inventory_sha256` (pre-record): `a9dd60c5b7d09531f54342a3bd757624a0d25211784829a28dfcf3f214f76d10`

The `SCOPE` inventory projection is byte-identical across all thirteen
`first_release_deferral` rows — and, as it happens, identical to the four
`authority_clause` rows too — because every field it covers
(`activation_predicate`, `disposition_refs`, `gate_refs`,
`related_register_ids`, and the whole `scope_derivation` object minus its
review slot) is fixed by kind rather than by occurrence. That is a property of
the projection, not of the review. What differs per component, and what this
review actually decided, is whether *this* occurrence justifies that fixed
derivation. Recorded here so a later reader does not mistake a shared digest for
a copied review.

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line
184, inside `## G. Explicitly deferred from the first release` (L173):

> - paper trading;

- `source_hash` `26d51b31…` recomputed over the whole register file → matches
  the stored value.
- `text_digest` recomputed over the normalized L184-184 span
  (`\n`-joined, surrounding ASCII whitespace trimmed) →
  `5443de7378c16c2ba4572ecee3068a6003b6e61c9bd6e44f6bcfb7bf78576643`,
  equal to the stored `text_digest`.
- `required_acceptance_text` is `"paper trading"`, which is
  that span with the list marker and terminal punctuation removed — the exact
  clause content.

## Reasoning

**Kind.** Bullet 10 of register §G (L184), excluding paper trading.
`first_release_deferral` by the §G rule. The kind check that mattered here is
that this is *not* a phase-gate clause: `REG-E-09`'s exclusion is enforced
through a `Deferred` register decision and, separately, through §F gate wording,
whereas this bullet is a release-scope exclusion. It carries no phase name and no
exit condition.

**Derivation rule.** For `first_release_deferral` the rule is not a free choice:
goal L240 fixes the kind→rule mapping to `PROGRAM_WIDE_ACTIVE_CONTROL`,
mechanized at `validate_ledger_structural.py:1508` (`required_rule_by_kind`),
and `:1547-1549` then forces `related_register_ids == []`,
`authority_effect is None`, and `derived == "REQUIRED_NOW"`. Goal L247-248
states the same rule in prose. The stored `derived_program_disposition` is
`REQUIRED_NOW` and `program_disposition` agrees.

The question the rule leaves genuinely open — and the one this review had to
decide — is whether a *deferral* is coherently `REQUIRED_NOW`. It is, and the
distinction is load-bearing: the inventoried component is **the control that
keeps the capability out of the first release**, not the capability. The control
is required now; the capability is not scheduled at all. Goal L255-257 states
exactly this ("This makes active program-wide controls terminal obligations even
when `primary_spec=null`, while dormant feature scope remains dormant"). A
deferral row derived `CONDITIONAL_UNACTIVATED` would invert it, making the
exclusion itself dormant.

**Related register IDs.** `[]`, contract-forced. The register's execution
territory is `REG-E-09` ("Keep execution in a separate trust domain", Priority
Critical, Status `Deferred`, dependencies `E-08`), whose acceptance names a
separate service, credentials, database, deterministic limits, approvals, kill
switch, and reconciliation. Paper trading is the non-live rung of that same
ladder, and the §G bullet excludes even that rung from the first release. `E-09`
is where the dormancy and the `EXECUTION_TRUST_DOMAIN_APPROVAL` live; this row
carries the active exclusion.

**Distinct from `DEF-11`.** Both rows own spec S04 ("execution trust domain").
`DEF-10` excludes *simulated* order flow, `DEF-11` excludes *real* order flow.
They are separate bullets at separate lines (L184 and L185) with distinct
`text_digest` values, and the register treats them as separable — paper trading
is reachable without the legal and regulatory gate that `E-08` imposes on live
execution. Two rows is correct.

**Source anchor and span.** `source_anchor` is `DEF-10`, a clause ordinal.
Goal L182 requires the anchor to be unique *within that path*, and the span
`(source_start_line, source_end_line)` likewise. Verified across all **120**
ledger rows that carry `source_path =
docs/blueprint/funda-blueprint-implementation-decision-register-v2.md`: zero
duplicate `source_anchor` values and zero duplicate spans. Verified separately
that the thirteen §G bullets at register L175-187 map one-to-one onto
`DEF-01`…`DEF-13` in line order with no gap, no overlap, and no second row
claiming any line in L173-188 — including the `## G.` heading at L173, which
goal L142's normalization rule ("One object per bullet in v2 §G", exact minimum
13) deliberately does not inventory.

**Disposition and gate refs.** `disposition_refs == []` and `gate_refs == []`.
Recomputed across the ledger this round: `gate_refs` is nonempty on exactly 39
rows, all `register_row`, and is pinned by the `gate_map` set equality at
`validate_ledger_structural.py:2660-2664`; no rule populates it for any
non-register kind. `disposition_refs` is nonempty on exactly three closed
populations — 56 register rows, the 32 `DISP-*` self-identifications, and the 8
`SCALE-*` rows pinned at `:2652-2653`. No `first_release_deferral` is in any of
them, and `[]` is the contract's uniform treatment of a program-wide control
whose scope is supplied by the derivation rule rather than by ref arrays.

**Activation predicate.** `null`, and required to be: goal L288-290 states that
a component whose derived disposition is `REQUIRED_NOW` has
`activation_predicate=null`, and L292-294 forbids any component-ID allowlist,
phase-gate exemption, or kind exemption to that rule. Mechanized at
`validate_ledger_structural.py:1577-1581`: a row that is neither a
was-conditional register nor currently derived conditional may hold a non-null
predicate only if it derives `REJECTED_ACCOUNTED` (`:1581`). This row derives
`REQUIRED_NOW`, so a predicate here would fail that assertion.

**Applicable review slot.** `DEF-10` is a non-register canonical row, so
`validate_ledger_preimplementation.py:200-204` appends `SCOPE` to its checks and
`scope_derivation.semantic_review` is the slot this review fills. It is present,
non-`null`, `PENDING`, and carries exactly the 10-key `PENDING` set with no
role-binding keys. Contrast the 60 `register_row` rows, where the contract fixes
`semantic_review = null` (goal L208-211) and no `SCOPE` review exists at all.

**Residuals.** None. Every field in the reviewed inventory was checked against
either a mechanized rule or the live source occurrence, and every mechanized
rule cited above was read in the checked-in validator at the pinned bytes.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `DEF-10`'s scope derivation is correct at the input bytes pinned above.
