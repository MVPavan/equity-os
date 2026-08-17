# Inventory review verdict — REG-A-01 — APPROVAL — r0

**verdict: CLEAN**

This artifact is the durable evidence for one content-bound `APPROVAL`
inventory review of ledger component `REG-A-01`. It is not an approval and
grants no authority: goal L615-617 fixes that ordinary `REVIEWER`-role
inventory review "is never an authority-bearing human resolution."

## 1. Review identity

| Field | Value |
|---|---|
| Component ID | `REG-A-01` |
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
| `docs/specs/equity-os-s01-…-boundary.md` (owning spec, corroboration only) | `1ad276cfa854b760a627b067be5aabe3b36019998a9ad5d1b52194c2dbd4af49` |

## 3. Applicable review slots — verified on this row, not assumed

The row's own `scope_derivation` reads, verbatim from the pinned ledger bytes:

```json
{"authority_effect": null, "derived_program_disposition": "REQUIRED_NOW",
 "related_register_ids": [], "rule": "REGISTER_STATUS", "semantic_review": null}
```

`semantic_review` is `null`, as goal L208-211 requires of every `register_row`
and as goal L2886 mechanizes (`assert derivation["semantic_review"] is None`).
`validate_ledger_preimplementation.py:200-204` appends the `SCOPE` check only
`if row["kind"] != "register_row"`. Applicable slots are therefore `EVIDENCE`
and `APPROVAL` only; **no `SCOPE` artifact is produced for this component**.

## 4. Reviewed inventory, exactly as seen

The `APPROVAL` reviewed inventory is `required_approvals`, `approval_records`,
`human_review_id`, and `security_exception_ids` (goal L435-436). Reproduced
verbatim from the pinned ledger bytes via the structural validator's own
`review_inventory_projection`, extracted read-only by `ast` per recording
design r2 §3.3:

```json
{
  "approval_records": [],
  "human_review_id": [
    "HR-0004"
  ],
  "required_approvals": [
    {
      "actor": null,
      "approval_id": "APR-REG-A-01-01",
      "approval_type": "DELEGATED_ARTIFACT_APPROVAL",
      "evidence_ref_ids": [],
      "matched_record_id": null,
      "required_authority": "Delegated fresh Sol xhigh specification reviewer",
      "scope": "A-01 under S01: Freeze initial user and distribution boundary",
      "status": "UNRESOLVED",
      "timestamp": null
    },
    {
      "actor": null,
      "approval_id": "APR-REG-A-01-02",
      "approval_type": "PRODUCT_OWNER_DECISION",
      "evidence_ref_ids": [],
      "matched_record_id": null,
      "required_authority": "Product owner",
      "scope": "A-01 under S01: Freeze initial user and distribution boundary",
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
| `reviewed_inventory_sha256` (`APPROVAL`) | `716e17b28b6ffd2622d8ee85f98048beafcdec3ebeb1c12165856d8b575ff125` |
| `reviewed_input_sha256` (shared by both review types on this row) | `4d3d7cceec9f641be74b057c4c4d2426729e69b79ed311c87888faac854eaf78` |

These are informational: the recorder recomputes both from the ledger at record
time and must not copy them from this artifact.

## 5. Source clause, read in the pinned authority

`EV-REG-A-01-SOURCE` binds register line 31 (`UTF8_LINE_SPAN` 31–31):

```
| A-01 | Critical | Freeze initial user and distribution boundary | Written statement covering private/internal use, public or paid distribution, personalization, execution linkage, and intended future boundary; document does not claim legal sufficiency | — | Open |
```

Dependencies cell: `—`. Status cell: `Open`. Also read: disposition report
§T-4 (this row's only `disposition_ref`).

## 6. Completeness reasoning

The question is narrow: **does the source clause demand any authority whose
sign-off `required_approvals` does not enumerate?** Whether an approval has
been obtained is not in scope — `approval_records` is correctly `[]` and every
requirement is `UNRESOLVED`.

Two bounds govern the answer. First, goal L535 derives `required_approvals`
from "its exact source acceptance text, dependencies, phase gates,
transitions, fail-closed boundaries, and any approved security exception."
Second, goal L583-584 closes the universe: "An approval type absent from the
table above has no obligation in this inventory and gains one only through a
reconciled, reviewed, approved change." The admissible types are the twelve in
the goal's required-authority table (L562-575, mechanized as
`REQUIRED_AUTHORITY_VOCABULARY` at `validate_ledger_structural.py:2586-2607`)
plus `DELEGATED_ARTIFACT_APPROVAL`.

**Enumerated and correct.**

- `APR-REG-A-01-02`, `PRODUCT_OWNER_DECISION`, `Product owner`. The clause's
  operative verb is **"Freeze"** — a binding determination of who the product
  is for and how it may be distributed. That is a product-scope decision, and
  `Product owner` is the exact vocabulary literal for it. Correct type and
  correct authority string.
- `APR-REG-A-01-01`, `DELEGATED_ARTIFACT_APPROVAL`, for the specification
  artifact review.

**Types considered and rejected, with reasons.**

- `LEGAL_REVIEW` / `REGULATORY_REVIEW`. Tempting, because the clause is about a
  distribution boundary. Rejected, and the clause itself is the reason: it ends
  "document does not claim legal sufficiency" — an explicit instruction that
  this row does *not* carry a legal conclusion. Disposition §T-4, this row's own
  `disposition_ref`, says the same in terms: "A-01 can define the intended
  product boundary without completing legal analysis… Current regulatory
  verification becomes mandatory before external, paid, personalized, or
  execution-connected use, not necessarily before documenting the initial
  private-use intent." That downstream obligation is enumerated on `REG-E-08`,
  which depends on A-01 and carries `LEGAL_REVIEW`, `REGULATORY_REVIEW`, and
  `DISTRIBUTION_APPROVAL`. Placing them here would contradict the disposition.
- `DISTRIBUTION_APPROVAL`. The clause requires the distribution boundary to be
  *documented*, including the intended future boundary; documenting an intent
  is not authorizing a mode. The authority to authorize a mode sits on E-08.

**Corroboration.** The owning spec S01 §7 lists exactly one typed authority for
its "A-01 boundary freeze" gate: `PRODUCT_OWNER_DECISION`. The ledger matches.
I treat the spec as corroboration only — register L23 makes the register
wording authoritative — but here authority and corroboration agree.

The inventory is exhaustive as goal L188 requires.

## 7. Verdict

verdict: CLEAN
