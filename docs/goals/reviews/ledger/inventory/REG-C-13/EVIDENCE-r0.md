# Inventory review verdict — REG-C-13 — EVIDENCE — r0

**verdict: CLEAN**

Durable evidence for one content-bound `EVIDENCE` inventory review of ledger
component `REG-C-13`. It records no approval and does not satisfy any evidence
item (goal L493-495).

## 1. Review identity

| Field | Value |
|---|---|
| Component ID | `REG-C-13` |
| Review type | `EVIDENCE` |
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

`REG-C-13.kind` is `register_row`; its `scope_derivation.semantic_review` is
`null` in the pinned ledger bytes (goal L208-211, asserted at goal L2886).
`validate_ledger_preimplementation.py:200-204` appends `SCOPE` only for
non-register kinds. Applicable slots: `EVIDENCE` and `APPROVAL` only. **No
`SCOPE` artifact for this component.** Both were `PENDING`.

## 4. Reviewed inventory, exactly as seen

`required_evidence`, `evidence_refs`, `verification_command` (goal L433-434),
reproduced verbatim via the structural validator's own
`review_inventory_projection`, extracted read-only by `ast` (design r2 §3.3):

```json
{
  "evidence_refs": [
    {
      "captured_at": "2026-08-13T02:49:11Z",
      "content_sha256": "47f401dc7676210a2ad776af94ca931667de93f989965c056e2e8f8dddf63d5e",
      "digest_mode": "UTF8_LINE_SPAN",
      "end_line": 84,
      "evidence_ref_id": "EV-REG-C-13-SOURCE",
      "path": "docs/blueprint/funda-blueprint-implementation-decision-register-v2.md",
      "scope": "Exact authoritative source occurrence for REG-C-13",
      "start_line": 84
    },
    {
      "captured_at": "2026-08-15T07:13:28Z",
      "content_sha256": "284d496f4b173c2489b1214e5662af0d6d7454db2558f106bbb649878c57ac14",
      "digest_mode": "FILE_BYTES",
      "end_line": null,
      "evidence_ref_id": "EV-REG-C-13-SPEC-DRAFT",
      "path": "docs/specs/equity-os-s02-source-rights-providers-consensus-policy.md",
      "scope": "Current draft specification bytes for REG-C-13",
      "start_line": null
    }
  ],
  "required_evidence": [
    {
      "approval_ids": [],
      "description": "Current proof satisfying: Licensed and necessary, or explicitly excluded from the MVP",
      "evidence_id": "REQ-REG-C-13-ACCEPTANCE",
      "evidence_ref_ids": [],
      "evidence_type": "ARTIFACT",
      "proof_mode": "CONTENT_HASH",
      "scope": "REG-C-13 acceptance and delivery scope",
      "status": "UNRESOLVED"
    },
    {
      "approval_ids": [],
      "description": "Persisted clean fresh Sol xhigh review of the current specification bytes",
      "evidence_id": "REQ-REG-C-13-SPEC-REVIEW",
      "evidence_ref_ids": [],
      "evidence_type": "REVIEW",
      "proof_mode": "CONTENT_HASH",
      "scope": "C-13 under S02: Decide treatment of consensus estimates",
      "status": "UNRESOLVED"
    },
    {
      "approval_ids": [
        "APR-REG-C-13-02"
      ],
      "description": "Current DATA_RIGHTS_APPROVAL evidence from Data-rights authority",
      "evidence_id": "REQ-REG-C-13-DATA_RIGHTS_APPROVAL",
      "evidence_ref_ids": [],
      "evidence_type": "DATA_RIGHTS",
      "proof_mode": "TYPED_APPROVAL",
      "scope": "C-13 under S02: Decide treatment of consensus estimates",
      "status": "UNRESOLVED"
    }
  ],
  "verification_command": {
    "commands": [],
    "mode": "UNRESOLVED",
    "not_applicable_review": null
  }
}
```

Digests recomputed by me over these exact bytes, using the validator's own
`canonical_sha256`:

| Digest | Value |
|---|---|
| `reviewed_inventory_sha256` (`EVIDENCE`) | `c660a9328d675f59c8ca6e03eca6c3079e0226c891532c442ea58b02fb4d10dd` |
| `reviewed_input_sha256` (shared by both review types on this row) | `c4c589fc55595449ee7374b7e68d24edbbe1537f3c035e136aac7c214876dac9` |

These are informational: the recorder recomputes both from the ledger at record
time and must not copy them from this artifact.

## 5. Source clause, read in the pinned authority

`EV-REG-C-13-SOURCE` binds register line 84 (`UTF8_LINE_SPAN` 84–84):

```
| C-13 | Medium | Decide treatment of consensus estimates | Licensed and necessary, or explicitly excluded from the MVP | A-05 | Open |
```

Dependencies cell: `A-05`. Status cell: `Open`. Disposition refs: `T-4`, `R-3`.
`gate_refs` is empty. `blueprint_phase` is `1`.

## 6. Completeness reasoning

**1. The acceptance obligation is a disjunction, and that is what makes this
row interesting.** The clause is not a list — it is a choice of branches:
either consensus estimates are **licensed and necessary**, or they are
**explicitly excluded from the MVP**. Each branch demands different proof: the
inclusion branch demands licence evidence and a necessity analysis, the
exclusion branch demands an explicit exclusion record.
`REQ-REG-C-13-ACCEPTANCE` (`ARTIFACT` / `CONTENT_HASH`) carries the whole
disjunction verbatim — compared byte-for-byte, minus the `Current proof
satisfying: ` prefix, against register L84 column 4; it matches exactly. That
verbatim carriage is what preserves both branches. A decomposed inventory that
enumerated only the inclusion branch would silently make exclusion
unrepresentable, which is the failure mode worth guarding against on a
disjunctive clause; it has not happened here.

**2. The delegated review obligation.** `REQ-REG-C-13-SPEC-REVIEW`
(`REVIEW` / `CONTENT_HASH`), consumed by `APR-REG-C-13-01`. Present.

**3. Typed-approval evidence.** The row has three approvals. Checking each:
`APR-REG-C-13-01` (`DELEGATED_ARTIFACT_APPROVAL`) is discharged by the
`SPEC-REVIEW` item above. `APR-REG-C-13-02` (`DATA_RIGHTS_APPROVAL`) is paired
by `REQ-REG-C-13-DATA_RIGHTS_APPROVAL`, `evidence_type` `DATA_RIGHTS`,
`proof_mode` `TYPED_APPROVAL`, `approval_ids` `["APR-REG-C-13-02"]` — exact
type correspondence per goal L486-489. `APR-REG-C-13-03`
(`PRODUCT_OWNER_DECISION`) has no paired item, and correctly so: the closed
`evidence_type` vocabulary (goal L479-483) has no product-owner member, and all
23 `PRODUCT_OWNER_DECISION` requirements ledger-wide are likewise unpaired.

**4. Does "Licensed" demand a separate `LEGAL` evidence item?** I weighed this,
because `REG-E-06` and `REG-E-07` in this same batch do carry `LEGAL` evidence
items off the word "license". The distinction is what is being licensed.
E-06/E-07 concern **software dependency** licences, and their approvals name a
"Competent dependency-license reviewer". C-13 concerns third-party **data** —
consensus estimates — whose permitted use is a rights question under the
`Data-rights authority`, which is enumerated. S02 §7's consensus-inclusion gate
confirms the split: it requires records for `PRODUCT_OWNER_DECISION` and
`DATA_RIGHTS_APPROVAL` unconditionally, and `PROVIDER_AUTHORIZATION`/
`LEGAL_REVIEW` only "as applicable". A conditional authority carries no
enumerable evidence item at these bytes, so no omission.

**5. No `COMMAND` obligation.** "Decide treatment" and "explicitly excluded"
are decision-record obligations, not executable checks.
`verification_command.mode` `UNRESOLVED` is the valid initial state (goal L187).

**6. `R-3` and the A-05 dependency** scope this row to the declared boundary
and order it after A-05; neither is an additional proof obligation, and both
live outside the `EVIDENCE` projection.

Nothing the clause demands is unenumerated.

## 7. Verdict

verdict: CLEAN
