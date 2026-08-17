# Inventory review verdict — REG-C-13 — APPROVAL — r0

**verdict: CLEAN**

Durable evidence for one content-bound `APPROVAL` inventory review of ledger
component `REG-C-13`. It is not an approval and grants no authority (goal
L615-617, L624-626).

## 1. Review identity

| Field | Value |
|---|---|
| Component ID | `REG-C-13` |
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
      "approval_id": "APR-REG-C-13-01",
      "approval_type": "DELEGATED_ARTIFACT_APPROVAL",
      "evidence_ref_ids": [],
      "matched_record_id": null,
      "required_authority": "Delegated fresh Sol xhigh specification reviewer",
      "scope": "C-13 under S02: Decide treatment of consensus estimates",
      "status": "UNRESOLVED",
      "timestamp": null
    },
    {
      "actor": null,
      "approval_id": "APR-REG-C-13-02",
      "approval_type": "DATA_RIGHTS_APPROVAL",
      "evidence_ref_ids": [],
      "matched_record_id": null,
      "required_authority": "Data-rights authority",
      "scope": "C-13 under S02: Decide treatment of consensus estimates",
      "status": "UNRESOLVED",
      "timestamp": null
    },
    {
      "actor": null,
      "approval_id": "APR-REG-C-13-03",
      "approval_type": "PRODUCT_OWNER_DECISION",
      "evidence_ref_ids": [],
      "matched_record_id": null,
      "required_authority": "Product owner",
      "scope": "C-13 under S02: Decide treatment of consensus estimates",
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
| `reviewed_inventory_sha256` (`APPROVAL`) | `b98974dd8920ba4cc3e4942cf6a321fdabc8df41496c38da06ce4d173e315936` |
| `reviewed_input_sha256` (shared by both review types on this row) | `c4c589fc55595449ee7374b7e68d24edbbe1537f3c035e136aac7c214876dac9` |

These are informational: the recorder recomputes both from the ledger at record
time and must not copy them from this artifact.

## 5. Source clause, read in the pinned authority

`EV-REG-C-13-SOURCE` binds register line 84 (`UTF8_LINE_SPAN` 84–84):

```
| C-13 | Medium | Decide treatment of consensus estimates | Licensed and necessary, or explicitly excluded from the MVP | A-05 | Open |
```

Dependencies cell: `A-05`. Status cell: `Open`. Disposition refs: `T-4`, `R-3`.

## 6. Completeness reasoning

Bounds: goal L535 (derivation from exact acceptance text, dependencies, phase
gates, transitions, fail-closed boundaries) and goal L583-584 (types absent
from the required-authority table carry no obligation). Admissible set: the
twelve types at goal L562-575, mechanized as `REQUIRED_AUTHORITY_VOCABULARY` at
`validate_ledger_structural.py:2586-2607`, plus `DELEGATED_ARTIFACT_APPROVAL`.

This row is the batch's cleanest illustration of a two-authority clause, and
both authorities are enumerated.

**Enumerated and correct.**

- `APR-REG-C-13-03`, `PRODUCT_OWNER_DECISION`, `Product owner`. The clause's
  operative verb is "**Decide** treatment", and its second branch is "explicitly
  **excluded from the MVP**". Whether a data class is in or out of the MVP is a
  product-scope decision; `Product owner` is the exact vocabulary literal.
- `APR-REG-C-13-02`, `DATA_RIGHTS_APPROVAL`, `Data-rights authority`. The
  inclusion branch requires consensus estimates to be "Licensed" — a rights
  determination over third-party data, reinforced by the `A-05` dependency and
  disposition §R-3. `Data-rights authority` is the single allowed literal.
- `APR-REG-C-13-01`, `DELEGATED_ARTIFACT_APPROVAL`, for the specification
  artifact review.

**Types considered and rejected, with reasons.**

- `LEGAL_REVIEW`. Considered because the clause says "Licensed". Rejected: the
  subject is third-party *data*, and its permitted use is the data-rights
  authority's determination. The `LEGAL_REVIEW` authorities in the closed table
  are "Competent dependency-license reviewer", "Competent legal reviewer", and
  "Competent trademark or legal reviewer" — the first fits software
  dependencies (as on `REG-E-06`/`REG-E-07`), the others fit legal posture and
  trademark. None is the natural authority for a data licence, and S02 §7 lists
  `LEGAL_REVIEW` for the consensus-inclusion gate only "as applicable", i.e.
  conditionally, alongside the two unconditional types the ledger does
  enumerate.
- `PROVIDER_AUTHORIZATION`. Named by S02 §7 for this gate, but absent from the
  closed required-authority table; goal L583-584 gives it no obligation here and
  the structural validator would reject it.

**Corroboration.** S02 §7 states the consensus gates directly: inclusion
requires "Distinct records for `PRODUCT_OWNER_DECISION`, `DATA_RIGHTS_APPROVAL`,
and each applicable `PROVIDER_AUTHORIZATION`/`LEGAL_REVIEW`"; exclusion requires
`PRODUCT_OWNER_DECISION`. Both unconditional types are enumerated on the row,
and both branches of the disjunction are covered.

**Cross-reference.** I relied on this row as the structural analogue in my
`REG-A-09` `APPROVAL` finding: A-09 has the same
external-authority-plus-product-decision shape but enumerates only the external
half. C-13 shows the ledger modelling that shape correctly, which is why the
A-09 gap reads as an omission rather than a program-wide convention.

The inventory is exhaustive as goal L188 requires.

## 7. Verdict

verdict: CLEAN
