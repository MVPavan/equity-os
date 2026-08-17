# Inventory review — DISP-6-9 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-6-9` |
| `review_type` | `APPROVAL` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `13edf3cc-a5b0-4217-8730-759de344e6db` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-15T13:10:41Z` |

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

`review_inventory_projection(row, "APPROVAL")` — canonical JSON:

```json
{"approval_records":[],"human_review_id":["HR-0004"],"required_approvals":[{"actor":null,"approval_id":"APR-DISP-6-9-01","approval_type":"DELEGATED_ARTIFACT_APPROVAL","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Delegated fresh Sol xhigh specification reviewer","scope":"6.9 under S11","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (recorder recomputes after
Phase A, recording design r2 §3.4):

- `reviewed_input_sha256` (pre-record): `db44dad35c6af1da83fa0a3219476e046fcbe6e0690babcb30dbb94f18745941`
- `reviewed_inventory_sha256` (pre-record): `f8de63b18debfe51df7730b61b3357eef009e636d97fdcc6f008e7d51f12dd64`

## Scope of this decision

Completeness of the typed approval obligation list (goal L188) — not whether any
approval has been obtained.

## The source clause, re-read this round

Disposition report L396-398:

> ### 6.9 Bit-exact computation is not universal
>
> The review correctly separates computation from narrative, but "bit-exact"
> should apply only to operators designed for exact replay. Floating-point,
> optimization, and stochastic calculations require declared tolerances, pinned
> environments, and stored seeds as applicable.

## Reasoning

**The one enumerated requirement.** `APR-DISP-6-9-01`,
`DELEGATED_ARTIFACT_APPROVAL`, "Delegated fresh Sol xhigh specification
reviewer", scope `"6.9 under S11"`. `applicable_spec_ids` is `["S11", "S16"]`,
and the scope names S11 — the spec whose draft bytes this row carries as evidence
(`EV-DISP-6-9-SPEC-DRAFT` → `docs/specs/equity-os-s11-run-manifest-cutoff-reproducibility.md`).
S16 is applicable through `C-08` but does not carry the clause.

**Near-miss 1: `DOMAIN_EXPERT_ACCEPTANCE` / "Calculation-domain authority".**
Deciding which operators are "designed for exact replay", and what tolerance is
acceptable for a floating-point or optimization operator, is a calculation-domain
judgment — and the vocabulary has a literal for exactly that. It is not omitted
here: that literal is enumerated exactly once in the whole ledger, on
**`REG-B-07`** ("Approved MVP list with input, trace, code-version,
missing-input, and reproducibility contracts", scoped "B-07 under S16: Define
minimum deterministic compute"), paired with its own `TYPED_APPROVAL` evidence
item. `B-07` is where the operator list itself is approved; §6.9 states a rule
about how that list must be classified, and the domain sign-off on the list is
`B-07`'s obligation. Recording it again here would create two obligations for one
decision, which goal L607-609 requires be avoided. Consistently, zero of the 32
`disposition_item` rows carry `DOMAIN_EXPERT_ACCEPTANCE`.

**Near-miss 2: `ANALYST_ACCEPTANCE`, and the `DISP-G-1` contrast.** `REG-C-16` —
one of this row's two related register rows — carries
`('ANALYST_ACCEPTANCE', 'Responsible analyst')`, and so does `DISP-G-1`, which
shares this row's `C-08`/`C-16` scope. So the question "why not here too?" is
live. The answer is in the clause's first sentence: "The review correctly
separates computation from narrative". `C-16`'s analyst acceptance and `G-1`'s
attach to the *narrative* limb — the approved published bytes bound to a content
hash, which is also what `PG-1-06` ("…and the approved narrative is bound to an
artifact hash") tests, and `PG-1-06` likewise carries the analyst acceptance.
§6.9 confines itself to the computation limb and explicitly defers the narrative
one. An `ANALYST_ACCEPTANCE` here would claim approval scope the clause disclaims.

**Sweep of the rest of the closed vocabulary** (goal L562-576):

| Type | Why not demanded here |
|---|---|
| `MEMORY_PROMOTION` | Nothing is promoted; the ledger's single instance is on `REG-C-10`. |
| `PRODUCT_OWNER_DECISION` | `C-08` and `C-16` are both `Open`/`REQUIRED_NOW`; nothing deferred is activated. Zero `disposition_item` rows carry this type. |
| `BUDGET_APPROVAL`, `CAPACITY_COMMITMENT` | "Pinned environments" implies infrastructure, but the clause commits no spend or capacity owner — it requires that whatever environment is used be *recorded*. The compute-cost obligations sit on the `REG-E-*` rows that carry them. |
| `NAMED_OWNER_COMMITMENT` / "Model-grade compute owner" | Checked because it is the compute-adjacent literal; it is enumerated on `REG-E-01`, whose subject is conditional model-grade compute. §6.9 is about the *minimum* deterministic set and names no owner. |
| `DATA_RIGHTS_APPROVAL`, `LEGAL_REVIEW`, `REGULATORY_REVIEW` | No data acquisition, licence, or regulated activity. |
| `DISTRIBUTION_APPROVAL`, `EXECUTION_TRUST_DOMAIN_APPROVAL` | Nothing distributed; no execution boundary. |

**Remaining projection fields.** `approval_records: []` — consistent with one
`UNRESOLVED` requirement and no decision. `human_review_id: ["HR-0004"]` — the
reconciliation entry; no open finding and `blocked_scope == []`, so no other HR
link is expected. `security_exception_ids: []` — no trust boundary crossed, and
no security exception exists on any of the 213 rows.

**Residuals.** None.

---

**verdict: CLEAN**

`required_approvals` for `DISP-6-9` is complete: one delegated artifact approval
under S11, with the calculation-domain sign-off correctly located on `REG-B-07`
and the narrative analyst acceptance on `REG-C-16` / `DISP-G-1` / `PG-1-06`. This
review grants no authority (goal L624-626) and authorizes no delivery, gate, or
transition.
