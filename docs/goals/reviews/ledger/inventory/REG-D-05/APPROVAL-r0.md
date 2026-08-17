# Inventory review — REG-D-05 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-D-05` |
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
| `register_id` / `source_anchor` | `D-05` / `D-05` |
| `source_path` L101-101 | `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` |
| `source_status` / `activation_source_status` | `Deferred` / `Deferred` |
| `program_disposition` / `delivery_status` | `CONDITIONAL_UNACTIVATED` / `SPEC_DRAFT` |
| `priority` / `blueprint_phase` | `High` / `2` |
| `primary_spec` | `S20` — docs/specs/equity-os-s20-memory-benchmark-gbrain.md |
| `dependencies` / `gate_refs` | `["D-02", "D-04"]` / `["PG-1-11", "PG-2-01", "PG-2-05", "PG-2-06"]` |
| `disposition_refs` / `human_review_id` | `["R-1", "6.4"]` / `"HR-0004"` |
| `text_digest` (recomputed this round) | `e3dc39a33b03f1a58eea915ea03f7884ef24e19a7c099be1d6d54d355e90514f` |

## Reviewed inventory, exactly as read

`review_inventory_projection(row, "APPROVAL")` — canonical JSON:

```json
{"approval_records":[],"human_review_id":["HR-0004"],"required_approvals":[{"actor":null,"approval_id":"APR-REG-D-05-01","approval_type":"DELEGATED_ARTIFACT_APPROVAL","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Delegated fresh Sol xhigh specification reviewer","scope":"D-05 under S20: Decide GBrain adoption","status":"UNRESOLVED","timestamp":null},{"actor":null,"approval_id":"APR-REG-D-05-02","approval_type":"PRODUCT_OWNER_DECISION","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Product owner authorized to activate deferred blueprint scope","scope":"D-05 ACTIVATE_DEFERRED scope","status":"UNRESOLVED","timestamp":null},{"actor":null,"approval_id":"APR-REG-D-05-03","approval_type":"PRODUCT_OWNER_DECISION","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Product owner for memory adoption","scope":"D-05 ADOPT_MEMORY_APPROACH scope","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record**:

- `reviewed_input_sha256` (pre-record): `9c28337df3f29c7144f3bf502123933d81fbfbf93679ea453da4ee8bbc46a5ae`
- `reviewed_inventory_sha256` (pre-record): `dca6796c213ba94e2b66ca1773b6a5ec7935553b7bb15aeec350526e94830777`

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

Register L101, table `## D. Phase 2 — Memory evaluation` (header L95-96), the single table row for `D-05`:

> | D-05 | High | Decide GBrain adoption | Adopt only if current-scale benchmark benefit exceeds operational and upgrade burden; a non-adoption result does not prevent later trigger-based reevaluation | D-02, D-04 | Deferred |

Column 4 ("Required evidence / acceptance") is the acceptance text:

> Adopt only if current-scale benchmark benefit exceeds operational and upgrade burden; a non-adoption result does not prevent later trigger-based reevaluation

`text_digest` and `EV-REG-D-05-SOURCE.content_sha256` were both recomputed
this round over the normalized L101-101 span → `e3dc39a33b03f1a58eea915ea03f7884ef24e19a7c099be1d6d54d355e90514f`,
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

**Three obligations, and the reason there are three rather than two — the
distinguishing feature of this row.** `REG-D-05` is the only component in this
batch carrying **two** `PRODUCT_OWNER_DECISION` requirements:

- `APR-REG-D-05-02`, authority `Product owner authorized to activate deferred
  blueprint scope`, scope `D-05 ACTIVATE_DEFERRED scope`;
- `APR-REG-D-05-03`, authority `Product owner for memory adoption`, scope
  `D-05 ADOPT_MEMORY_APPROACH scope`.

Both authorities are legal literals under `PRODUCT_OWNER_DECISION` in the closed
table (`:2607-2611`), and the pair is **required**, not duplicated. Goal L613-615:
"Where one real-world decision covers two approval types or scopes, record two
explicit human resolutions, obligations, and records rather than infer coverage."
Deciding that deferred Phase-2 scope becomes live and deciding which memory
approach Funda adopts are two decisions that happen to be taken at one moment; the
scope strings keep them separate, and `matched_record_id` is `null` on both so no
record can be shared. Collapsing them into one would be the omission — and it is
the omission the third requirement's distinct authority literal exists to prevent.

**`PG-2-05`'s gate-local `PRODUCT_OWNER_DECISION` is a *third* obligation that must
not be mirrored here.** `PG-2-05` is one of only six `phase_gate_clause` rows
carrying `required_approvals`, and its single entry is a `PRODUCT_OWNER_DECISION`
with the bare `Product owner` literal, scope `PG-2-05 product owner decision`; its
`related_register_ids` is exactly `["D-05"]` (all verified on its live bytes this
round). Because the gate names this register row, the natural error is to conclude
that `REG-D-05` is missing that approval. It is not: gate obligations are
inventoried component-locally on the gate row, and mirroring it here would satisfy
two requirements from one decision — the same rule that requires `-02` and `-03`
to stay separate forbids importing the gate's.

**`BUDGET_APPROVAL` / `CAPACITY_COMMITMENT` checked.** The clause names
"operational and upgrade burden", which is resource language. Not demanded: the
burden is an **input to the comparison**, not a commitment made by this clause.
`D-05` decides; if the decision is to adopt, the resulting operational commitment
belongs to the activated scope, and the standing capacity/budget commitment is
inventoried on `REG-A-12` ("Define operating calendar, standing budget, and
capacity"). The row's predicate `AP-D05-GBRAIN-ADOPTION-DECISION-READY` tests
`d02_complete`, `d04_complete`, `adoption_decision_ready` — three readiness
booleans, no resource metric.

**`LEGAL_REVIEW` checked.** Adopting a dependency is exactly when a licence
matters — but the licence obligation is enumerated on `D-04`
(`Competent dependency-license reviewer`), which is this row's dependency and the
row whose clause names "license". `D-05` consumes that determination; it does not
re-inventory it.

**`MEMORY_PROMOTION` checked.** This row decides the memory *approach*, not any
individual promotion. The ledger's sole `MEMORY_PROMOTION` requirement is
`REG-C-10`'s.

**Sweep of the remaining closed vocabulary.**

| Type | Why it is not demanded by this clause |
|---|---|
| `ANALYST_ACCEPTANCE` | The adoption decision is a product-owner decision, and the closed table separates the two roles. |
| `DOMAIN_EXPERT_ACCEPTANCE` | Choosing a memory engine is an engineering/product tradeoff, not a data, calculation, entity, vocabulary, or equity-research determination. |
| `NAMED_OWNER_COMMITMENT` | No owner is appointed; `Golden-set owner`, `Model-grade compute owner`, `Event-monitoring owner` sit on `REG-A-08`, `REG-E-01`, `REG-E-04`. |
| `DATA_RIGHTS_APPROVAL` | No external data acquired. |
| `REGULATORY_REVIEW`, `DISTRIBUTION_APPROVAL`, `EXECUTION_TRUST_DOMAIN_APPROVAL` | Nothing regulated, distributed, or executed (`REG-E-08`, `REG-E-09`). |

**Gate and dependency sweep.** `gate_refs` is `["PG-1-11", "PG-2-01", "PG-2-05",
"PG-2-06"]`; three of the four carry zero approvals and `PG-2-05`'s is handled
above. `dependencies` is `["D-02", "D-04"]`; `REG-D-02` carries delegated +
activate-deferred and `REG-D-04` adds the licence review — none of which
transfers, since each is component-local to its own scope string.

**Remaining projection fields.** `approval_records: []`; `human_review_id`
normalizes to `["HR-0004"]`; `security_exception_ids: []`.

**Residuals.** None.

---

**verdict: CLEAN**

`required_approvals` for `REG-D-05` is complete at the input bytes pinned above.
This review grants no authority (goal L624-626) and authorizes no delivery,
gate, or transition.
