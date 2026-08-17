# Inventory review — DISP-6-2 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-6-2` |
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
{"approval_records":[],"human_review_id":["HR-0001","HR-0004"],"required_approvals":[{"actor":null,"approval_id":"APR-DISP-6-2-01","approval_type":"DELEGATED_ARTIFACT_APPROVAL","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Delegated fresh Sol xhigh specification reviewer","scope":"6.2 under S06","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (recorder recomputes after
Phase A, recording design r2 §3.4):

- `reviewed_input_sha256` (pre-record): `0e2fd7e9c2cf4105c75c87f377dba0054f947578effd9bd3a1db44c5c063b057`
- `reviewed_inventory_sha256` (pre-record): `b8c6562d54679caba24e9c8dcfb0bc983dd753bc8ddaf5aca877b25333141aa0`

## Scope of this decision

Completeness of the typed approval obligation list (goal L188) — not whether any
approval has been obtained.

## The source clause, re-read this round

Disposition report L359-361:

> ### 6.2 Materiality is not only a financial-statement threshold
>
> The proposed percentage rule is one component. Governance, guidance, thesis
> relevance, and source conflict must also be represented.

## Reasoning

**The one enumerated requirement.** `APR-DISP-6-2-01`,
`DELEGATED_ARTIFACT_APPROVAL`, "Delegated fresh Sol xhigh specification
reviewer", scope `"6.2 under S06"`. The row's `applicable_spec_ids` are
`["S06", "S13"]`, so the scope string picks one of two; it picks the one whose
draft bytes this row actually carries as evidence
(`EV-DISP-6-2-SPEC-DRAFT` → `docs/specs/equity-os-s06-output-materiality-falsifiers.md`).
That is the correct owner: §6.2 constrains the materiality contract, which lives
in S06; S13 is applicable because `C-04`'s validation surface must enforce it,
not because S13 carries the clause's text. One delegated approval per row, on the
artifact that carries the obligation, is the ledger-wide pattern for all 123 such
requirements.

**The near-miss that must be checked here: `DOMAIN_EXPERT_ACCEPTANCE`.** Of all
11 components in this batch, §6.2 is the one whose subject matter — what counts
as material in equity research — most plainly involves domain judgment, and the
vocabulary does contain `DOMAIN_EXPERT_ACCEPTANCE` / "Equity-research domain
expert". It is nevertheless **not** an omission here, and the reason is
locatable rather than argumentative: that exact authority is enumerated exactly
once in the entire ledger, on **`REG-A-10`** — the "Define claim materiality
policy" register row that this very clause names as its related register scope.
`REG-A-10` carries `('DELEGATED_ARTIFACT_APPROVAL', …)` plus
`('DOMAIN_EXPERT_ACCEPTANCE', 'Equity-research domain expert')`, paired with its
own `TYPED_APPROVAL` evidence item. §6.2 tells the policy what it must contain;
the domain sign-off on that policy's content is `A-10`'s obligation and is
already inventoried there. Duplicating it on the disposition item would create a
second obligation for one real-world decision — precisely what goal L607-609
forbids ("Where one real-world decision covers two approval types or scopes,
record two explicit human resolutions … rather than infer coverage" — and here
there is only one decision, on `A-10`). Consistently, **zero** of the 32
`disposition_item` rows carry `DOMAIN_EXPERT_ACCEPTANCE`; all six sit on
`REG-A-10`, `REG-B-03`, `REG-B-07`, `REG-B-12`, `REG-C-17`, `PG-05-05`.

**Sweep of the rest of the closed vocabulary.**

| Type | Why not demanded here |
|---|---|
| `ANALYST_ACCEPTANCE` | No approved thesis, narrative, or rework artifact appears in the clause. The three `disposition_item` rows that carry one (`DISP-G-1`, `DISP-M-1`, `DISP-M-5`) each name an explicitly approved object; §6.2 names none. |
| `MEMORY_PROMOTION` | Nothing is promoted to canonical memory. |
| `PRODUCT_OWNER_DECISION` | Activates no deferred scope; `A-10` and `C-04` are both `Open`/`REQUIRED_NOW`. Zero `disposition_item` rows carry this type. |
| `BUDGET_APPROVAL`, `CAPACITY_COMMITMENT`, `NAMED_OWNER_COMMITMENT` | No spend, capacity, or named owner. |
| `DATA_RIGHTS_APPROVAL`, `LEGAL_REVIEW`, `REGULATORY_REVIEW` | "Governance" here means governance *events as a materiality category*, not corporate-governance sign-off; no data licence, trademark, or regulated activity is involved. |
| `DISTRIBUTION_APPROVAL`, `EXECUTION_TRUST_DOMAIN_APPROVAL` | Nothing distributed; no execution boundary. |

**`human_review_id: ["HR-0001", "HR-0004"]` — and the authority that is
deliberately *not* in this list.** This row carries an `OPEN_BLOCKING` finding
`S06-I7` whose `required_authority` block reads
`{"approval_type": "GOAL_OR_PROCESS_AUTHORIZATION", "authority": "Explicit rank-1
current-user authority", "ordinary_r5_permitted": false}`. That is a real,
unmet authority requirement — and it is correctly **absent** from
`required_approvals`, for a mechanical reason: `GOAL_OR_PROCESS_AUTHORIZATION`
does not appear in the closed required-authority table (goal L562-576), and goal
L583-584 states that "An approval type absent from the table above has no
obligation in this inventory and gains one only through a reconciled, reviewed,
approved change"; `validate_ledger_structural.py:2629` would reject such an entry
outright. Process authority in this contract lives at the human-review layer, and
it is in fact recorded there: `docs/goals/equity-os-blueprint-human-review-needed.md`
entry `HR-0001` carries
`decision_authority.approval_type == "GOAL_OR_PROCESS_AUTHORIZATION"` with
authority "Explicit rank-1 current-user authority over the active goal process"
and `competent_roles: ["CURRENT_USER"]`, `blocking: true`, and this row links
`HR-0001`. So the authority is inventoried, in the only place the contract can
represent it. The `HR-0004` link is the reconciliation entry carried by every
post-HR-0004 canonical row.

**Remaining projection fields.** `approval_records: []` — no decision has been
recorded, consistent with the single `UNRESOLVED` requirement and with `HR-0001`
remaining open. `security_exception_ids: []` — no trust boundary is crossed and
no security exception exists on any of the 213 rows.

**Residuals.** None. The `S06-I7` block remains open and this review neither
resolves nor narrows it.

---

**verdict: CLEAN**

`required_approvals` for `DISP-6-2` is complete: one delegated artifact approval
under S06, with the domain sign-off correctly located on `REG-A-10` and the
process authority correctly located on `HR-0001`. This review grants no authority
(goal L624-626).
