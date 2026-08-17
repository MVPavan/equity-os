# Inventory review — REG-D-01 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-D-01` |
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
`{"authority_effect": null, "derived_program_disposition": "REQUIRED_NOW",
"related_register_ids": [], "rule": "REGISTER_STATUS", "semantic_review": null}`.
No `SCOPE` artifact exists or may exist for this component.

## Row facts, re-read this round

| Field | Value as read |
|---|---|
| `kind` | `register_row` |
| `register_id` / `source_anchor` | `D-01` / `D-01` |
| `source_path` L97-97 | `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` |
| `source_status` / `activation_source_status` | `Open` / `Open` |
| `program_disposition` / `delivery_status` | `REQUIRED_NOW` / `SPEC_DRAFT` |
| `priority` / `blueprint_phase` | `Critical` / `2` |
| `primary_spec` | `S19` — docs/specs/equity-os-s19-memory-store-promotion.md |
| `dependencies` / `gate_refs` | `["C-15"]` / `["PG-2-04"]` |
| `disposition_refs` / `human_review_id` | `["R-1", "6.4"]` / `"HR-0004"` |
| `text_digest` (recomputed this round) | `b2d194e4f6098521d7186eb6795bd5c0e89da9ea735f1140c244f089bab3da3d` |

## Reviewed inventory, exactly as read

`review_inventory_projection(row, "APPROVAL")` — canonical JSON:

```json
{"approval_records":[],"human_review_id":["HR-0004"],"required_approvals":[{"actor":null,"approval_id":"APR-REG-D-01-01","approval_type":"DELEGATED_ARTIFACT_APPROVAL","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Delegated fresh Sol xhigh specification reviewer","scope":"D-01 under S19: Implement `MemoryStore` interface before choosing engine","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record**:

- `reviewed_input_sha256` (pre-record): `19b32bb73f5c90f7921b3f57a8d473a076137e3bf7f134087a641b309af8afbb`
- `reviewed_inventory_sha256` (pre-record): `546bcb921099951d10114f5b10f9351894fad7836aa57208048f76c977497a1a`

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

Register L97, table `## D. Phase 2 — Memory evaluation` (header L95-96), the single table row for `D-01`:

> | D-01 | Critical | Implement `MemoryStore` interface before choosing engine | Retrieval, staged write, promotion, correction, deletion, export, cutoff filtering, and provenance contracts are engine-neutral | C-15 | Open |

Column 4 ("Required evidence / acceptance") is the acceptance text:

> Retrieval, staged write, promotion, correction, deletion, export, cutoff filtering, and provenance contracts are engine-neutral

`text_digest` and `EV-REG-D-01-SOURCE.content_sha256` were both recomputed
this round over the normalized L97-97 span → `b2d194e4f6098521d7186eb6795bd5c0e89da9ea735f1140c244f089bab3da3d`,
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

**Why this row carries exactly one approval, and why that is the complete
answer.** `REG-D-01` is the only component in this batch with
`program_disposition: REQUIRED_NOW` (`source_status: Open`,
`activation_source_status: Open`, so goal L213-215's mechanical derivation gives
`REQUIRED_NOW`). Its single obligation `APR-REG-D-01-01` is the
`DELEGATED_ARTIFACT_APPROVAL` over `S19`, with the one pinned delegated
authority literal.

**The absent activate-deferred approval is required to be absent.** Every one of
the other ten components in this batch carries a `PRODUCT_OWNER_DECISION` with
authority `Product owner authorized to activate deferred blueprint scope`.
`REG-D-01` must not: recomputed over all 60 register rows this round, that
requirement is present on exactly the `CONDITIONAL_UNACTIVATED` rows and absent
from every other row, with zero exceptions. There is no deferred scope here to
activate, so the requirement would be an obligation with no referent.

**`MEMORY_PROMOTION` — the trap this particular clause sets.** The clause
literally contains the word "promotion", and `MEMORY_PROMOTION` (authority
`Responsible analyst`) is in the closed table. It is not demanded here. That
authority authorizes an **actual** promotion of a memory item by the responsible
analyst; `D-01` obliges only that the promotion *contract* be engine-neutral.
Recomputed this round, the ledger's sole `MEMORY_PROMOTION` requirement sits on
`REG-C-10` ("Establish correction, supersession, and promotion workflow", S15) —
the workflow row where a promotion is actually performed. Mirroring it here would
inventory one authority against two requirements, which goal L613-615 forbids.

**Sweep of the remaining closed vocabulary.**

| Type | Why it is not demanded by this clause |
|---|---|
| `ANALYST_ACCEPTANCE` | No analyst output is produced or accepted; an interface shape is not an analyst deliverable. |
| `DOMAIN_EXPERT_ACCEPTANCE` | Engine neutrality is an architectural property of Funda's own code. Calculation, vocabulary, data, entity, and equity-research domain acceptance live on `REG-B-07`, `REG-B-12`, `REG-B-03`, `REG-C-17` and `REG-A-10` respectively — none of which this clause touches. |
| `PRODUCT_OWNER_DECISION` | Nothing deferred is activated and no memory approach is adopted; the adoption decision is `D-05`'s (`Product owner for memory adoption`). |
| `BUDGET_APPROVAL`, `CAPACITY_COMMITMENT`, `NAMED_OWNER_COMMITMENT` | The clause commits no spend, no analyst capacity, and appoints no owner. |
| `DATA_RIGHTS_APPROVAL`, `LEGAL_REVIEW`, `REGULATORY_REVIEW` | No external data, no third-party dependency, no licence, and no regulated activity — `D-04` is the row that examines a dependency's licence. |
| `DISTRIBUTION_APPROVAL`, `EXECUTION_TRUST_DOMAIN_APPROVAL` | Nothing is distributed; no execution boundary is crossed (`REG-E-08` and `REG-E-09` hold those). |

**Gate and dependency sweep.** `gate_refs` is `["PG-2-04"]` and `dependencies` is
`["C-15"]`. `PG-2-04` carries zero `required_approvals` (verified on its live
bytes), so no gate-local authority exists to mirror; and gate obligations are in
any case inventoried component-locally on the gate row — six of the 35
`phase_gate_clause` rows do carry their own approvals, none of which is `PG-2-04`.
`REG-C-15` carries only its own delegated approval.

**Remaining projection fields.** `approval_records: []` matches zero
requirements — correct, since no decision has been recorded. `human_review_id`
normalizes to `["HR-0004"]`, a link to the canonical human-review artifact
recording the authority-reconciliation transaction; a link is not an approval
obligation and creates none. `security_exception_ids: []`, and no row in the
ledger carries one.

**Residuals.** None.

---

**verdict: CLEAN**

`required_approvals` for `REG-D-01` is complete at the input bytes pinned above.
This review grants no authority (goal L624-626) and authorizes no delivery,
gate, or transition.
