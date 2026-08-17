# Inventory review verdict — REG-A-05 — APPROVAL — r0

**verdict: CLEAN**

Durable evidence for one content-bound `APPROVAL` inventory review of ledger
component `REG-A-05`. It is not an approval and grants no authority (goal
L615-617, L624-626).

## 1. Review identity

| Field | Value |
|---|---|
| Component ID | `REG-A-05` |
| Review type | `APPROVAL` |
| Round | `r0` |
| Role | `REVIEWER` |
| Reviewer | Independent `REVIEWER` subagent, Claude Code session `6b725e7a-eda6-42e9-be39-2f0d26984eee`, batch-13 dispatch |
| Role binding path | `CONTEXT.md` |
| Role binding SHA-256 (at review time) | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| Model actually invoked | `claude-opus-5` |
| Effort actually invoked | `high` |
| Review UTC | `2026-08-16T13:48:25Z` |
| Batch | 13 (`register_row`, specs S01–S04) per recording design r2 §5.2 |

## 2. Inputs read at review time

| Input | SHA-256 |
|---|---|
| `docs/goals/equity-os-blueprint-completion.md` | `f15f7ab5a4e425dec3877ab7f1f7594687979060e4dbcd49390a8a8d5fedb85f` |
| `docs/goals/equity-os-blueprint-component-ledger.jsonl` | `de236d7e8dcf02e307ec58797f5722ae2f85d1d8cdba57d4ecc07df5383c9c97` |
| `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| `docs/blueprint/funda-third-order-review-disposition-report.md` | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| `scripts/equity_os_blueprint/validate_ledger_structural.py` | `731d0d8b208b577967c92e3992e7ec1a4333cdecbf89f6951c32d2ec469436f9` |
| `CONTEXT.md` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `docs/specs/equity-os-s02-source-rights-providers-consensus-policy.md` (owning spec, corroboration only) | `284d496f4b173c2489b1214e5662af0d6d7454db2558f106bbb649878c57ac14` |

## 3. Applicable review slots — verified on this row, not assumed

`scope_derivation` on this row, verbatim from the pinned ledger bytes:

```json
{"authority_effect": null, "derived_program_disposition": "REQUIRED_NOW",
 "related_register_ids": [], "rule": "REGISTER_STATUS", "semantic_review": null}
```

`semantic_review` is `null` (goal L208-211; asserted at goal L2886), so
`validate_ledger_preimplementation.py:200-204` yields `APPROVAL` + `EVIDENCE`
only. **No `SCOPE` artifact for this component.**

## 4. Reviewed inventory, exactly as seen

`required_approvals`, `approval_records`, `human_review_id`,
`security_exception_ids` (goal L435-436), reproduced verbatim via the
structural validator's own `review_inventory_projection`, extracted read-only by
`ast` (design r2 §3.3):

```json
{
  "approval_records": [],
  "human_review_id": [
    "HR-0004"
  ],
  "required_approvals": [
    {
      "actor": null,
      "approval_id": "APR-REG-A-05-01",
      "approval_type": "DELEGATED_ARTIFACT_APPROVAL",
      "evidence_ref_ids": [],
      "matched_record_id": null,
      "required_authority": "Delegated fresh Sol xhigh specification reviewer",
      "scope": "A-05 under S02: Create provider and data-rights register scoped to the declared boundary",
      "status": "UNRESOLVED",
      "timestamp": null
    },
    {
      "actor": null,
      "approval_id": "APR-REG-A-05-02",
      "approval_type": "DATA_RIGHTS_APPROVAL",
      "evidence_ref_ids": [],
      "matched_record_id": null,
      "required_authority": "Data-rights authority",
      "scope": "A-05 under S02: Create provider and data-rights register scoped to the declared boundary",
      "status": "UNRESOLVED",
      "timestamp": null
    }
  ],
  "security_exception_ids": []
}
```

Digests recomputed by me over these exact bytes, using the validator's own
`canonical_sha256`:

| Digest | Value |
|---|---|
| `reviewed_inventory_sha256` (`APPROVAL`) | `aea0867d29b29b8d8a0ad39695b709888124b1c3a092700f5f0eeef53e2d6546` |
| `reviewed_input_sha256` (shared by both review types on this row) | `67c24fc3137611892ef97fbdfe0f325fe388431eddaefe408ab85bb918fdd427` |

These are informational: the recorder recomputes both from the ledger at record
time and must not copy them from this artifact.

## 5. Source clause, read in the pinned authority

`EV-REG-A-05-SOURCE` binds register line 35 (`UTF8_LINE_SPAN` 35–35):

```
| A-05 | Critical | Create provider and data-rights register scoped to the declared boundary | For every source: access method, automation, caching, retention, commercial use, derived outputs, redistribution, account limits, point-in-time availability, and replacement path | A-01 | Open |
```

Dependencies cell: `A-01`. Status cell: `Open`. Disposition refs: `T-4`, `R-3`
(§R-3 "Make A-05 depend on A-01" — **Accept**).

## 6. Completeness reasoning

Bounds, as for every row in this batch: goal L535 derives `required_approvals`
from the exact source acceptance text, dependencies, phase gates, transitions,
fail-closed boundaries, and approved security exceptions; goal L583-584 closes
the universe — "An approval type absent from the table above has no obligation
in this inventory." The admissible set is the twelve types in the goal's
required-authority table (L562-575, mechanized as
`REQUIRED_AUTHORITY_VOCABULARY` at `validate_ledger_structural.py:2586-2607`)
plus `DELEGATED_ARTIFACT_APPROVAL`.

**Enumerated and correct.**

- `APR-REG-A-05-02`, `DATA_RIGHTS_APPROVAL`, `Data-rights authority`. The
  clause's substance is rights determination: commercial use, derived outputs,
  redistribution, retention, and account limits are all questions of what the
  program is permitted to do with third-party source data. `Data-rights
  authority` is the single allowed literal for this type and is used exactly.
- `APR-REG-A-05-01`, `DELEGATED_ARTIFACT_APPROVAL`, for the specification
  artifact review.

**Types considered and rejected, with reasons.**

- `LEGAL_REVIEW`. This is the closest call on this row, because S02 §7's
  register-completeness gate does name it — but conditionally: "`LEGAL_REVIEW`
  **when legal interpretation is required**." The authoritative register clause
  contains no licence or legal term at all. The contrast within this very batch
  is the discriminator: `REG-E-06` and `REG-E-07`, whose clauses say "license"
  and "licenses", both enumerate `LEGAL_REVIEW`; A-05's clause does not, and
  does not. A conditional-on-circumstance authority is not an enumerable
  obligation at these bytes under goal L535's "exact source acceptance text"; if
  the condition later materialises it enters through a reconciled, reviewed
  change, which is exactly the path goal L583-584 prescribes.
- `PROVIDER_AUTHORIZATION`, `PURCHASE_AUTHORIZATION`,
  `CREDENTIAL_ACCESS_APPROVAL`, `EXTERNAL_SERVICE_APPROVAL`,
  `EXTERNAL_COORDINATION_APPROVAL`. All five are named by S02 §7's "Provider
  access" gate, and all five are **absent from the goal's closed
  required-authority table**. Goal L583-584 is explicit that such a type "has no
  obligation in this inventory," and the structural validator would reject any
  `required_approvals` entry using one. Their absence is contract-mandated, not
  an omission. I note the tension honestly: the owning spec describes real
  obligations the ledger cannot represent today; resolving that is a vocabulary
  reconciliation, not a defect in this row's inventory.
- `PRODUCT_OWNER_DECISION`. Rejected. A-05's clause builds an inventory
  *against a boundary already frozen elsewhere* — "scoped to the declared
  boundary", with the A-01 dependency and §R-3 confirming that direction. It
  makes no product-scope decision of its own. The contrast is `REG-C-13` in this
  same batch, whose clause requires an include-or-exclude-from-MVP decision and
  which does carry `PRODUCT_OWNER_DECISION`.

**Corroboration.** S02 §7's register-completeness and operational-mode gates
name `DATA_RIGHTS_APPROVAL` unconditionally and everything else either
conditionally or outside the admissible vocabulary. The ledger enumerates
exactly the unconditional admissible authority.

The inventory is exhaustive as goal L188 requires.

## 7. Verdict

verdict: CLEAN
