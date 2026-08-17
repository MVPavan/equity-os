# Inventory review — DEF-12 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DEF-12` |
| `review_type` | `APPROVAL` |
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

`review_inventory_projection(row, "APPROVAL")` — canonical JSON:

```json
{"approval_records":[],"human_review_id":["HR-0004"],"required_approvals":[{"actor":null,"approval_id":"APR-DEF-12-01","approval_type":"DELEGATED_ARTIFACT_APPROVAL","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Delegated fresh Sol xhigh specification reviewer","scope":"DEF-12 under S20","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (the recorder must
recompute both after its Phase A evidence append, per recording design
r2 §3.4 — appending review evidence mutates `evidence_refs` and therefore
the input projection):

- `reviewed_input_sha256` (pre-record): `e15f00e9c21f332c37b444675e3213f22e828729a2374d5ac7e68053cd826922`
- `reviewed_inventory_sha256` (pre-record): `1468984ddd2522e5dfac75526749f3d6c45427bc9c9c129114594b87c44f7bd2`

## Scope of this decision

Goal L188: `required_approvals` "exhaustively declares the component's typed
approval obligations", and goal L619-623 requires a `COMPLETE` approval-inventory
review to check "the exact source acceptance text, dependencies, gates, and
fail-closed boundaries" and return `CLEAN`. This review therefore decides
**completeness of the obligation list only** — whether the source clause demands
an authority whose sign-off is not enumerated. It does not decide whether any
approval has been obtained; the single enumerated requirement here is
legitimately `UNRESOLVED` with a null actor, null timestamp, empty evidence, and
no matched record (goal L588-591). Per goal L624-626, neither this completeness
review nor a `REVIEWER`-role approval grants any non-delegated authority.

## The source clause, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line
186, inside `## G. Explicitly deferred from the first release` (L173):

> - local-model optimization without a Funda-specific benchmark;

`text_digest` recomputed over the normalized L186-186 span →
`a7595dd8e141fbe63dfda149d579a5915d8c7a2552fb98cacb57be49363d7503`, matching the stored value.

**Authority language in the clause.** It contains no "approve", "approved",
"accept", "sign-off", "authorize", or named role. Its grammatical form is a bare
noun phrase in a list governed by the heading "Explicitly deferred from the first
release" — an exclusion, not a commitment. Nothing in it commits a resource,
acquires a right, binds an external party, or crosses a trust boundary.

## Reasoning

**The conditional form, tested for an omitted authority.** "Without a
Funda-specific benchmark" means the exclusion lapses once a benchmark exists —
so who authorises the finding that it does? Not this row. Producing the benchmark
is `REG-D-02`'s obligation, and adopting anything on its result is `REG-D-05`'s,
which is the only row in the ledger carrying `PRODUCT_OWNER_DECISION` with
authority `Product owner for memory adoption`. Both are `Deferred` and both carry
the activate-deferred authority as well. The lapse condition is therefore fully
owned, and owned elsewhere.

**The `primary_spec: null` seam, checked against the approval scope string.**
`APR-DEF-12-01`'s scope reads "DEF-12 under S20" while `primary_spec` is `null`
— a null the goal-derived validator pins directly
(`validate_ledger_structural.py:2654`). I checked whether the delegated approval
is thereby unbound to any artifact and it is not: the scope string names S20
explicitly and `EV-DEF-12-SPEC-DRAFT` resolves to
`docs/specs/equity-os-s20-memory-benchmark-gbrain.md`, whose bytes the structural
run re-digested. Goal L184 permits a null `primary_spec` where `scope_derivation`
supplies program-wide ownership, and L185 adds that `primary_spec` "never
determines whether a component is active". So the delegated obligation has a
named artifact and the inventory is complete. Recorded as a structural
observation.

**The enumerated obligation.** One requirement, `APR-DEF-12-01`, type
`DELEGATED_ARTIFACT_APPROVAL`, authority "Delegated fresh Sol xhigh
specification reviewer", scope "DEF-12 under S20", `UNRESOLVED`. It is the delegated
review of the specification artifact that states this exclusion — the same
obligation every spec-bound row in this ledger carries, present on 123 of 213
rows. Its authority literal is deliberately unpinned by the contract (goal
L577-582) but must be one identical nonempty string across the whole ledger,
which `validate_ledger_structural.py:2633` asserts
(`len(delegated_artifact_authorities) == 1`). I verified all 123 share it.

**Sweep of the closed non-delegated vocabulary.** Goal L562-575 and
`validate_ledger_structural.py:2586-2613` close
the set of 12 approval types that may carry a `required_approvals` entry, each
with an exact allowed authority string. Checked one by one against this clause's
exact text:

| Type | Why it is not demanded by this clause |
|---|---|
| `ANALYST_ACCEPTANCE`, `MEMORY_PROMOTION` (`Responsible analyst`) | The clause asks an analyst to accept nothing and promotes no memory; it removes work from the release rather than producing an analyst-judged output. |
| `DOMAIN_EXPERT_ACCEPTANCE` (calculation, data, entity-data, equity-research, vocabulary) | No calculation, dataset, entity mapping, or vocabulary term is defined or changed by an exclusion. |
| `PRODUCT_OWNER_DECISION` (incl. `Product owner authorized to activate deferred blueprint scope`) | `REG-D-02` ('Run current-scale three-arm memory benchmark', `Deferred`) carries the activate-deferred authority and owns the benchmark whose absence this clause conditions on. `REG-D-05` ('Decide GBrain adoption') additionally carries the ledger's only `Product owner for memory adoption` authority. |
| `BUDGET_APPROVAL`, `CAPACITY_COMMITMENT`, `NAMED_OWNER_COMMITMENT` | The clause commits no spend, no capacity, and no named owner. Not building a capability consumes none of the three. |
| `DATA_RIGHTS_APPROVAL`, `LEGAL_REVIEW`, `REGULATORY_REVIEW` | No data is acquired, no licence taken, no trademark used, and no regulated activity performed. An exclusion creates no legal or rights surface. |
| `DISTRIBUTION_APPROVAL`, `EXECUTION_TRUST_DOMAIN_APPROVAL` | Nothing is distributed and no execution boundary is crossed. Both types exist in this ledger on exactly one row each (`REG-E-08` and `REG-E-09`), both `Deferred` register rows that would *perform* the activity. |

**The activation authority exists — and it is deliberately not on this row.**
This is the check that matters most for a deferral, so I did it by enumeration
rather than by argument. `PRODUCT_OWNER_DECISION` with authority "Product owner
authorized to activate deferred blueprint scope" appears on exactly **15** rows
in this ledger: `REG-C-14`, `REG-D-02`…`REG-D-05`, and `REG-E-01`…`REG-E-10`.
Every one is a `register_row` captured `Deferred`. **Zero** non-register rows
carry it, and no `first_release_deferral`, `scale_trigger`, `phase_gate_clause`,
`authority_clause`, `sequence_clause`, or `document_strategy_clause` does.

That distribution is the contract working as designed, not an oversight. The
authority to activate dormant scope attaches to the register decision that
*holds* the scope, whose own derivation is `CONDITIONAL_UNACTIVATED` and whose
`activation_predicate` records the condition (goal L285-286). A
`first_release_deferral` is `REQUIRED_NOW` with `activation_predicate: null`: it
is the active control asserting the capability is out, not a dormant capability
awaiting a signature. Putting an activation approval here would assert that the
*exclusion* awaits approval, which inverts it.

**`GOAL_OR_PROCESS_AUTHORIZATION` is unrepresentable, by design.** If any
authority fitted a release-scope boundary decision it would be this one. It is in
the approval-type vocabulary at goal L540 but deliberately **absent** from the
closed required-authority table at L562-575, and goal L583-584 is explicit: "An
approval type absent from the table above has no obligation in this inventory and
gains one only through a reconciled, reviewed, approved change."
`validate_ledger_structural.py:2629` would reject such an entry outright
(`assert approval_type in REQUIRED_AUTHORITY_VOCABULARY`). Process and
goal authority in this contract lives at the human-review layer —
`decision_authority.approval_type` on an `HR-####` entry — not in
`required_approvals`. `DEF-12` is linked to `HR-0004` only.

**Remaining projection fields.** `approval_records: []` is consistent with a
single `UNRESOLVED` requirement and with the ledger-wide state — zero of 213 rows
carry an approval record, since none has been obtained (goal L188: one record
satisfies at most one requirement). `security_exception_ids: []`: the clause
crosses no trust boundary, and no security exception exists anywhere in the
ledger (0 of 213 rows), so there is no `SECURITY_EXCEPTION` obligation to
enumerate. `human_review_id` is `HR-0004`, normalized to a sorted set by `normalized_human_review_id` before the projection is digested.

**Residual, recorded not waived.** `required_authority` reads "Delegated fresh
Sol xhigh specification reviewer" — a vendor model lane, where `CONTEXT.md` binds
process roles. HR-0004 replaced vendor lanes in the validator-checked review
schema and reason codes while "changing no ledger row for that purpose", and the
literal cannot be changed on this row alone in any case: the validator asserts
all 123 delegated requirements share one identical string, so a per-row edit
would fail structural validation. This is a program-level cleanup bound to a
future atomic migration, not an omission from this row's obligation list, and it
is outside this review's decided question. Recorded so the inventory of surviving
literals is not lost.

**Residuals beyond the one recorded above.** None.

---

**verdict: CLEAN**

`required_approvals` for `DEF-12` is complete at the input bytes pinned above: the
source clause demands exactly one typed approval — the delegated artifact
approval already enumerated as `APR-DEF-12-01` — and no authority whose
sign-off is unenumerated. This review grants no authority (goal L624-626) and
authorizes no delivery, gate, or transition.
