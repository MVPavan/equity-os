# Inventory review — REG-D-02 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-D-02` |
| `review_type` | `APPROVAL` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `c625bbd5-cbd8-40b2-823c-20422d619435` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-16T13:58:44Z` |

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

Fresh structural validation at these exact bytes → exit `0`
(`python3 scripts/equity_os_blueprint/validate_ledger_structural.py --repo-root .`).

## Applicable review slots for this component

This component is a `register_row`, so it has exactly **two** applicable review
slots. `scope_derivation.semantic_review` is contractually `null` (goal
L208-211, mechanized at `validate_ledger_structural.py:1532`), and
`validate_ledger_preimplementation.py:199-204` builds `checks` as `APPROVAL` +
`EVIDENCE` and appends `SCOPE` only when `row["kind"] != "register_row"`. I
confirmed on this row's live bytes that `scope_derivation` is
`{"authority_effect": null, "derived_program_disposition": "CONDITIONAL_UNACTIVATED",
"related_register_ids": [], "rule": "REGISTER_STATUS", "semantic_review": null}`.
No `SCOPE` artifact exists or may exist for this component.

## Row facts, re-read this round

| Field | Value as read |
|---|---|
| `kind` | `register_row` |
| `register_id` / `source_anchor` | `D-02` / `D-02` |
| `source_path` L98-98 | `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` |
| `source_status` / `activation_source_status` | `Deferred` / `Deferred` |
| `program_disposition` / `delivery_status` | `CONDITIONAL_UNACTIVATED` / `SPEC_DRAFT` |
| `priority` / `blueprint_phase` | `Critical` / `2` |
| `primary_spec` | `S20` — docs/specs/equity-os-s20-memory-benchmark-gbrain.md |
| `dependencies` / `gate_refs` | `["C-05", "D-01", "D-04"]` / `["PG-1-11", "PG-2-01", "PG-2-02", "PG-2-06"]` |
| `disposition_refs` / `human_review_id` | `["R-1", "6.4"]` / `"HR-0004"` |
| `text_digest` (recomputed this round) | `f6fcaf28d67d26fe22a49525fb9e268e883377555cf30bdf423f7b62a077f0f5` |

## Reviewed inventory, exactly as read

`review_inventory_projection(row, "APPROVAL")` — canonical JSON:

```json
{"approval_records":[],"human_review_id":["HR-0004"],"required_approvals":[{"actor":null,"approval_id":"APR-REG-D-02-01","approval_type":"DELEGATED_ARTIFACT_APPROVAL","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Delegated fresh Sol xhigh specification reviewer","scope":"D-02 under S20: Run current-scale three-arm memory benchmark","status":"UNRESOLVED","timestamp":null},{"actor":null,"approval_id":"APR-REG-D-02-02","approval_type":"PRODUCT_OWNER_DECISION","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Product owner authorized to activate deferred blueprint scope","scope":"D-02 under S20: Run current-scale three-arm memory benchmark","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record**:

- `reviewed_input_sha256` (pre-record): `bc7b99611c754550cbabcd76317b671cb00418aeb194d61ccf79868b035983ab`
- `reviewed_inventory_sha256` (pre-record): `87793c82e0135db2d863a1ef4defe745eee6ceaf2b949f1c7f5a5b56e913aa26`

Both were recomputed this round with `canonical_sha256` /
`review_input_projection` / `review_inventory_projection` extracted from the
checked-in structural validator by `ast` (never imported), per design r2 §3.3.

## Scope of this decision

Completeness of `required_approvals` only: does this row's source clause,
dependencies, gates, transitions, or fail-closed boundaries (goal L535-537)
demand an authority whose sign-off is not enumerated? Whether any approval has
been obtained is out of scope. Goal L188 makes an approval inventory a
completed, evidenced determination, so each enumerated obligation is affirmed
and each absent one is affirmed as absent, not skipped.

## The source clause, re-read this round

Register L98, table `## D. Phase 2 — Memory evaluation` (header L95-96), the single table row for `D-02`:

> | D-02 | Critical | Run current-scale three-arm memory benchmark | All arms receive the same authoritative prior artifacts; compare no persistent memory/manual context assembly, Git/Markdown/SQL retrieval, and GBrain on longitudinal tasks, retrieval misses, contradiction/staleness detection, analyst time, unsupported claims, latency, cost, and operations; result governs current adoption only; re-evaluation triggers are precommitted | C-05, D-01, D-04 | Deferred |

Column 4 ("Required evidence / acceptance") is the acceptance text:

> All arms receive the same authoritative prior artifacts; compare no persistent memory/manual context assembly, Git/Markdown/SQL retrieval, and GBrain on longitudinal tasks, retrieval misses, contradiction/staleness detection, analyst time, unsupported claims, latency, cost, and operations; result governs current adoption only; re-evaluation triggers are precommitted

`text_digest` and `EV-REG-D-02-SOURCE.content_sha256` were both recomputed
this round over the normalized L98-98 span → `f6fcaf28d67d26fe22a49525fb9e268e883377555cf30bdf423f7b62a077f0f5`,
matching the stored values. The register's ID, priority, title, acceptance text,
dependencies, and status cells were each byte-compared against the corresponding
ledger fields; all six match.

## Reasoning

**Program-wide facts recomputed this round** (not transcribed from any peer
artifact), used in the sweeps below:

- The required-authority map is closed at 12 approval types with pinned literal
  authorities (`REQUIRED_AUTHORITY_VOCABULARY`,
  `validate_ledger_structural.py:2586-2612`; goal L555-576), and every
  `required_approvals` entry outside it is rejected (`:2629-2631`).
  `DELEGATED_ARTIFACT_APPROVAL` is exempt from the literal pin but must use one
  identical nonempty authority string everywhere (`:2623-2628`, `:2633`).
- `GOAL_OR_PROCESS_AUTHORIZATION`, `PROVIDER_AUTHORIZATION`,
  `PRODUCTION_APPROVAL`, `EXTERNAL_SERVICE_APPROVAL`, `SECURITY_EXCEPTION`,
  `CREDENTIAL_ACCESS_APPROVAL`, `PURCHASE_AUTHORIZATION` and
  `EXTERNAL_COORDINATION_APPROVAL` appear in the goal's approval-type list
  (L539-549) but **not** in the required-authority table, and goal L583-584
  states such a type "has no obligation in this inventory". None is
  representable in `required_approvals` today.
- Where each remaining authority actually lives, recomputed over all 213 rows:
  `MEMORY_PROMOTION`/`Responsible analyst` → `REG-C-10` only;
  `DOMAIN_EXPERT_ACCEPTANCE` → `REG-B-07` (`Calculation-domain authority`),
  `REG-B-12` (`Vocabulary authority`), `REG-B-03` + `PG-05-05`
  (`Data-domain authority`), `REG-C-17` (`Entity-data authority`), `REG-A-10`
  (`Equity-research domain expert`); `DATA_RIGHTS_APPROVAL` → `REG-A-05`,
  `REG-C-13`, `REG-C-14`, `REG-E-04`, `REG-E-06`; `REGULATORY_REVIEW` and
  `DISTRIBUTION_APPROVAL` → `REG-E-08` only;
  `EXECUTION_TRUST_DOMAIN_APPROVAL` → `REG-E-09` only;
  `NAMED_OWNER_COMMITMENT` → `REG-A-08`, `REG-E-01`, `REG-E-04`.
- The activate-deferred obligation is exactly disposition-keyed: across all 60
  `register_row` components, a `PRODUCT_OWNER_DECISION` with authority
  `Product owner authorized to activate deferred blueprint scope` is present on
  every `CONDITIONAL_UNACTIVATED` row and absent from every other row — zero
  exceptions.
- `approval_records` and `security_exception_ids` are empty on all 213 rows, so
  the remaining projection fields carry no unenumerated obligation.

**The two enumerated obligations, affirmed.** `APR-REG-D-02-01` is the
`DELEGATED_ARTIFACT_APPROVAL` over `S20`; `APR-REG-D-02-02` is the
`PRODUCT_OWNER_DECISION` with the exact pinned literal `Product owner authorized
to activate deferred blueprint scope`. The second is required and correctly
present: this row is `CONDITIONAL_UNACTIVATED` (`activation_source_status:
Deferred`, `source_status: Deferred`), and recomputed this round the
activate-deferred requirement holds on every `CONDITIONAL_UNACTIVATED` register
row and no other, with zero exceptions.

**`BUDGET_APPROVAL` and `CAPACITY_COMMITMENT` — the sharpest challenge on this
row, and the one I spent the most on.** The clause names "analyst time",
"latency", "cost", and "operations", and a three-arm benchmark plainly consumes
analyst hours and compute spend. The determination is that neither is demanded,
on three independent grounds:

1. *Grammatical role.* Every one of those words appears as a **dimension of
   comparison** — the things the benchmark measures — not as a resource the
   clause commits. Measuring cost is not authorizing spend. Contrast `REG-E-03`,
   whose clause says "retain only if incremental valid issue detection justifies
   **cost**" — an authorization-shaped test — and which does carry
   `BUDGET_APPROVAL`.
2. *The row's own mechanical statement of readiness.* `activation_predicate`
   `AP-D02-CURRENT-SCALE-BENCHMARK-READY` is an `ALL` over four metrics:
   `c05_accepted`, `d01_accepted`, `d04_activated`, `benchmark_ready`. It names
   **no** budget or capacity metric — unlike `REG-E-01`
   (`capacity_and_budget_ready`) and `REG-E-02` (`capacity_ready`), both of which
   do carry the matching commitment. The predicate is the row's own testable
   statement of what must hold, and it is silent on resources.
3. *Where the program does inventory Phase-2 capacity and budget.* Recomputed
   ledger-wide, `Budget owner` sits on `REG-A-07`, `REG-A-12`, `REG-E-01`,
   `REG-E-03`, `REG-E-04`, `REG-E-05`; `Capacity owner` on `PG-1-09`, `REG-A-12`,
   `REG-C-01`, `REG-C-18`, `REG-E-01`, `REG-E-02`. `REG-A-12` ("Define operating
   calendar, standing budget, and capacity") is where the standing commitment
   lives; a benchmark drawing on that standing capacity does not re-inventory it.

**The adoption authority is `D-05`'s, not this row's.** "result governs current
adoption only" reads as an obligation on how the benchmark's output may be used,
and it is tempting to attach the adoption approval here. `D-05` ("Decide GBrain
adoption") carries `Product owner for memory adoption` — verified on its live
bytes — and this row produces the input to that decision, not the decision.
Attaching it here would satisfy two requirements from one real-world decision,
which goal L613-615 forbids explicitly.

**Sweep of the remaining closed vocabulary.**

| Type | Why it is not demanded by this clause |
|---|---|
| `ANALYST_ACCEPTANCE` | Analyst time is measured, not accepted; no analyst signs off on a benchmark's fairness. `Responsible analyst` sits on `REG-A-03`, `A-04`, `A-11`, `B-02`, `B-14`, `C-12`, `C-16` and three disposition rows. |
| `MEMORY_PROMOTION` | No memory item is promoted; the promotion workflow authority is `REG-C-10`'s. |
| `DOMAIN_EXPERT_ACCEPTANCE` | Benchmark design is a measurement-methodology question, not a data, calculation, entity, vocabulary, or equity-research determination. |
| `DATA_RIGHTS_APPROVAL` | The arms consume "the same authoritative prior artifacts" — Funda's own existing artifacts. No external source is acquired. |
| `LEGAL_REVIEW` | GBrain's licence is `D-04`'s obligation (`Competent dependency-license reviewer`), not this row's; the benchmark is an evaluation, not an adoption. |
| `REGULATORY_REVIEW`, `DISTRIBUTION_APPROVAL` | Nothing is published or distributed; both live on `REG-E-08` alone. |
| `EXECUTION_TRUST_DOMAIN_APPROVAL` | No execution boundary (`REG-E-09` alone). |

**Gate sweep.** `gate_refs` is `["PG-1-11", "PG-2-01", "PG-2-02", "PG-2-06"]`. All
four carry zero `required_approvals` (verified on their live bytes), so no
gate-local authority exists to consider mirroring. `PG-2-05`, the one Phase-2
gate that does carry a `PRODUCT_OWNER_DECISION`, is scoped to `D-05` and is not
one of this row's gates.

**Remaining projection fields.** `approval_records: []`; `human_review_id`
normalizes to `["HR-0004"]` (a link, not an obligation);
`security_exception_ids: []`.

**Residuals.** None.

---

**verdict: CLEAN**

`required_approvals` for `REG-D-02` is complete at the input bytes pinned above.
This review grants no authority (goal L624-626) and authorizes no delivery,
gate, or transition.
