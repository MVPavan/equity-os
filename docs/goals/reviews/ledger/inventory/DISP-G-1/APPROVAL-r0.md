# Inventory review — DISP-G-1 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-G-1` |
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
{"approval_records":[],"human_review_id":["HR-0001","HR-0004"],"required_approvals":[{"actor":null,"approval_id":"APR-DISP-G-1-01","approval_type":"DELEGATED_ARTIFACT_APPROVAL","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Delegated fresh Sol xhigh specification reviewer","scope":"G-1 under S06","status":"UNRESOLVED","timestamp":null},{"actor":null,"approval_id":"APR-DISP-G-1-02","approval_type":"ANALYST_ACCEPTANCE","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Responsible analyst","scope":"G-1 analyst acceptance","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (recorder recomputes after
Phase A, recording design r2 §3.4):

- `reviewed_input_sha256` (pre-record): `de150af438f6f0bd491f0a622f5a20f14ebc87528a67adc2ca0674b97332f16e`
- `reviewed_inventory_sha256` (pre-record): `d90876e67468228f09516d73a98c68f9c5c49b588a12f69e2561359f1697d13e`

## Scope of this decision

Completeness of the typed approval obligation list (goal L188) — not whether any
approval has been obtained. Both requirements are legitimately `UNRESOLVED` with
null actor/timestamp and no matched record.

## The source clause, re-read this round

Disposition report L47-59, `### G-1 — Narrative reproducibility`, disposition
"Accept with modification", whose third guarantee reads:

> 3. **Narrative:** the approved published bytes are immutable and bound to a
>    content hash; a later regeneration must be audited against the same
>    approved claim set but need not be text-identical.

and which closes "This correction belongs in the output contract, run manifest,
and Phase 1 gate."

## Reasoning

**Two enumerated requirements — the only multi-approval row in this batch.**

- `APR-DISP-G-1-01`, `DELEGATED_ARTIFACT_APPROVAL`, "Delegated fresh Sol xhigh
  specification reviewer", scope `"G-1 under S06"`. `applicable_spec_ids` is
  `["S06", "S11", "S16"]` and the scope names S06 — the spec whose draft bytes
  this row carries as evidence (`EV-DISP-G-1-SPEC-DRAFT` →
  `docs/specs/equity-os-s06-output-materiality-falsifiers.md`), and the artifact
  the closing sentence calls "the output contract".
- `APR-DISP-G-1-02`, `ANALYST_ACCEPTANCE`, "Responsible analyst", scope
  `"G-1 analyst acceptance"`. This is the requirement guarantee 3 demands: bytes
  cannot be "the **approved** published bytes" unless someone approved them, and
  the approval competent to accept a research narrative is the responsible
  analyst. The authority literal is the only one the vocabulary permits for this
  type (goal L563). It is paired 1:1 with
  `REQ-DISP-G-1-ANALYST_ACCEPTANCE-02` (`ANALYST` / `TYPED_APPROVAL`), matching
  the ledger-wide convention for all 13 `ANALYST_ACCEPTANCE` requirements.

**Is the `ANALYST_ACCEPTANCE` correctly placed on this row rather than only on
the register?** Yes, and the check is worth recording because `REG-C-16` and
`REG-A-04` *also* carry one, which could look like triplication. They are three
distinct obligations, not one: `REG-A-04`'s attaches to freezing the output
contract, `REG-C-16`'s to the layered-reproducibility implementation, and
`APR-DISP-G-1-02` to accepting this specific correction's narrative guarantee.
Goal L607-609 requires exactly this treatment — "Where one real-world decision
covers two approval types or scopes, record two explicit human resolutions,
obligations, and records rather than infer coverage" — and record IDs are
globally unique for matching, so no single record can silently satisfy all three.
The corresponding gate clause `PG-1-06` ("deterministic calculations satisfy their
declared exact/tolerance/seeded replay class and the approved narrative is bound
to an artifact hash") likewise carries its own `ANALYST_ACCEPTANCE`, which is the
fourth instance of the same authority across this clause's cone and confirms the
pattern is deliberate.

**Is anything else demanded?** Sweep of the closed vocabulary (goal L562-576)
against `G-1`'s three guarantees:

| Type | Why not demanded here |
|---|---|
| `DOMAIN_EXPERT_ACCEPTANCE` / "Calculation-domain authority" | Guarantee 1 classifies operators, which is a calculation-domain judgment — but that authority is enumerated on `REG-B-07` ("Approved MVP list with … reproducibility contracts"), where the operator list itself is approved. Zero `disposition_item` rows carry this type. |
| `MEMORY_PROMOTION` | Guarantee 3 concerns publication immutability, not promotion into canonical memory; the ledger's single instance is on `REG-C-10`. |
| `PRODUCT_OWNER_DECISION` | All four related register rows are `Open`/`REQUIRED_NOW`; nothing deferred is activated. Zero `disposition_item` rows carry this type. |
| `BUDGET_APPROVAL`, `CAPACITY_COMMITMENT`, `NAMED_OWNER_COMMITMENT` | No spend, capacity, or named owner. |
| `DATA_RIGHTS_APPROVAL`, `LEGAL_REVIEW` | No acquisition or licence. |
| `REGULATORY_REVIEW`, `DISTRIBUTION_APPROVAL` | The nearest miss, since guarantee 3 speaks of "published bytes". Both of the ledger's instances sit on `REG-E-08`, which gates paid/public/personalized research. `G-1`'s "published" means published *inside* the private operating model — the distribution boundary is a separate, deferred decision, and importing its authorities here would attach a distribution obligation to an internal reproducibility guarantee. |
| `EXECUTION_TRUST_DOMAIN_APPROVAL` | No execution boundary; the ledger's single instance is on `REG-E-09`. |

**`human_review_id: ["HR-0001", "HR-0004"]` — and the authority deliberately not
in `required_approvals`.** This row carries the `OPEN_BLOCKING` finding `S06-I7`,
whose `required_authority` block reads
`{"approval_type": "GOAL_OR_PROCESS_AUTHORIZATION", "authority": "Explicit rank-1
current-user authority", "ordinary_r5_permitted": false}`. That authority is
unmet and real, and it is correctly absent from `required_approvals`:
`GOAL_OR_PROCESS_AUTHORIZATION` is not in the closed required-authority table
(goal L562-576), goal L583-584 states that a type absent from that table "has no
obligation in this inventory", and `validate_ledger_structural.py:2629` would
reject such an entry. It is instead inventoried where the contract can represent
it — `docs/goals/equity-os-blueprint-human-review-needed.md` entry `HR-0001`,
`decision_authority.approval_type == "GOAL_OR_PROCESS_AUTHORIZATION"`, authority
"Explicit rank-1 current-user authority over the active goal process",
`competent_roles: ["CURRENT_USER"]`, `blocking: true` — and this row links it.
The `HR-0004` link is the reconciliation entry.

**Remaining projection fields.** `approval_records: []` — no decision recorded,
consistent with two `UNRESOLVED` requirements and with `HR-0001` still open;
goal L188 also forbids one record satisfying two requirements, so two records
will eventually be needed here. `security_exception_ids: []` — no trust boundary
crossed, and no security exception exists on any of the 213 rows.

**Residuals.** None. The `S06-I7` block remains open and this review neither
resolves nor narrows it.

---

**verdict: CLEAN**

`required_approvals` for `DISP-G-1` is complete: one delegated artifact approval
under S06 and one analyst acceptance for guarantee 3's approved narrative bytes,
with the process authority correctly located on `HR-0001` and the
calculation-domain sign-off on `REG-B-07`. This review grants no authority (goal
L624-626) and authorizes no delivery, gate, or transition.
