# Inventory review — `REG-B-03` — `APPROVAL` — `r0`

**verdict: CLEAN**

## 1. Review identity and role binding

| Field | Value |
|---|---|
| Component ID | `REG-B-03` |
| Component kind | `register_row` |
| Review type | `APPROVAL` |
| Review round | `r0` |
| Reviewer identity / session | Reviewer-role dispatch (independent agent and context), Claude Code session dac10266-7ecd-43c9-8e3d-203459a7c509 |
| Role | `REVIEWER` |
| Role binding path | `CONTEXT.md` |
| Role binding SHA-256 (CONTEXT.md bytes at review time) | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| Model actually invoked | `claude-opus-5` |
| Effort actually invoked | `high` |
| Review UTC timestamp | `2026-08-16T13:46:18Z` |

This dispatch is an independent `REVIEWER`-role agent and context, separate from
any `IMPLEMENTER` that produced the reviewed ledger content (goal L947-949;
`CONTEXT.md` "Agent roles (harness-wide)", whose current `REVIEWER` binding is
Claude Opus 5 at high effort — the model and effort recorded above are what was
actually invoked, not a copy of that table).

## 2. Input hashes read at review time

Recomputed by `sha256sum` from repo root `/data/codes/equity-os` during this
review; every file below was read, not assumed.

| Input | Path | SHA-256 |
|---|---|---|
| Active goal contract | `docs/goals/equity-os-blueprint-completion.md` | `f15f7ab5a4e425dec3877ab7f1f7594687979060e4dbcd49390a8a8d5fedb85f` |
| Canonical component ledger | `docs/goals/equity-os-blueprint-component-ledger.jsonl` | `de236d7e8dcf02e307ec58797f5722ae2f85d1d8cdba57d4ecc07df5383c9c97` |
| Pinned decision register v2 (authority for this row) | `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| Third-order review disposition report | `docs/blueprint/funda-third-order-review-disposition-report.md` | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| Structural validator | `scripts/equity_os_blueprint/validate_ledger_structural.py` | `731d0d8b208b577967c92e3992e7ec1a4333cdecbf89f6951c32d2ec469436f9` |
| Preimplementation validator | `scripts/equity_os_blueprint/validate_ledger_preimplementation.py` | `f7a225a1f99cb85c92cde3094505a92a746552280eb45dae0253a71ab9048013` |
| Canonical human-review artifact | `docs/goals/equity-os-blueprint-human-review-needed.md` | `094fcdfab74a3f4c6fdb82b1520fc4d13b636ac0e9ed10194e5d607aed2ce9af` |
| Role binding table | `CONTEXT.md` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |

Baseline gate state observed at these bytes:
`python3 scripts/equity_os_blueprint/validate_ledger_structural.py --repo-root .`
exits `0`.

## 3. Applicable review slots for this row

`REG-B-03` is a `register_row`. `validate_ledger_preimplementation.py:199-204`
builds the applicable check list as `APPROVAL` + `EVIDENCE` always, and appends
`SCOPE` only when `row["kind"] != "register_row"`. I verified on this row
directly, from the canonical ledger bytes, that
`scope_derivation.semantic_review` is `null`:

```json
{
  "authority_effect": null,
  "derived_program_disposition": "REQUIRED_NOW",
  "related_register_ids": [],
  "rule": "REGISTER_STATUS",
  "semantic_review": null
}
```

So this row has exactly **two** applicable review slots, `EVIDENCE` and
`APPROVAL`, and no `SCOPE` review exists or may be created for it. Its scope
derivation comes from the pinned v2 register itself under rule `REGISTER_STATUS`
(goal L208-211).

The `APPROVAL` slot as read, `PENDING` with the exact 10-key `PENDING` key
set and no role-binding keys (`validate_ledger_structural.py:238-243`,
`:320-356`):

```json
{
  "effort": null,
  "evidence_ref_ids": [],
  "model": null,
  "review_type": "APPROVAL",
  "reviewed_input_sha256": null,
  "reviewed_inventory_sha256": null,
  "reviewer": null,
  "status": "PENDING",
  "timestamp": null,
  "verdict": null
}
```

## 4. Source clause, as read in the pinned authority

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line 53
(file SHA-256 `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`), read verbatim:

```
| B-03 | Critical | Establish source-of-truth matrix | Approved authority table for raw documents, SQL facts, claims, calculations, narrative memory, derivative indices, evidence packages, and reports | — | Open |
```

| Binding | Ledger value | Recomputed from the pinned bytes | Match |
|---|---|---|---|
| `text_digest` | `1d6aba44cfd0ea49ef92b8097525ce6db92eb32b2fa7dc0d36bed2c1e6e1c46a` | `1d6aba44cfd0ea49ef92b8097525ce6db92eb32b2fa7dc0d36bed2c1e6e1c46a` | yes |
| `source_title` | `Establish source-of-truth matrix` | cell 3 of the row | yes |
| `required_acceptance_text` | (cell 4, reproduced below) | cell 4 of the row | yes |
| `source_status` | `Open` | cell 6 of the row | yes |
| `priority` | `Critical` | cell 2 of the row | yes |

Acceptance text bound by the ledger:

> Approved authority table for raw documents, SQL facts, claims, calculations, narrative memory, derivative indices, evidence packages, and reports

Owning spec: `S10` — Source-of-truth matrix, evidence packages, and record-retention policy
(`docs/specs/equity-os-s10-source-of-truth-evidence-retention.md`). Blueprint phase `0.5`,
program disposition `REQUIRED_NOW`, delivery status
`REVIEW_BLOCKED`. `disposition_refs` = `["T-3", "R-5"]`,
`gate_refs` = `["PG-05-05"]`,
`dependencies` = `[]`.

## 5. Reviewed inventory, exactly as read

The `APPROVAL` inventory is defined by goal L435-436: the `APPROVAL` reviewed inventory is the complete `required_approvals`, `approval_records`, `human_review_id`, and `security_exception_ids` collections.
Transcribed here directly from the canonical ledger bytes whose SHA-256 is
recorded in §2:

```json
{
  "approval_records": [],
  "human_review_id": [
    "HR-0003",
    "HR-0004"
  ],
  "required_approvals": [
    {
      "actor": null,
      "approval_id": "APR-REG-B-03-01",
      "approval_type": "DELEGATED_ARTIFACT_APPROVAL",
      "evidence_ref_ids": [],
      "matched_record_id": null,
      "required_authority": "Delegated fresh Sol xhigh specification reviewer",
      "scope": "B-03 under S10: Establish source-of-truth matrix",
      "status": "UNRESOLVED",
      "timestamp": null
    },
    {
      "actor": null,
      "approval_id": "APR-REG-B-03-02",
      "approval_type": "DOMAIN_EXPERT_ACCEPTANCE",
      "evidence_ref_ids": [],
      "matched_record_id": null,
      "required_authority": "Data-domain authority",
      "scope": "B-03 under S10: Establish source-of-truth matrix",
      "status": "UNRESOLVED",
      "timestamp": null
    }
  ],
  "security_exception_ids": []
}
```

## 6. The question this review decides

Is `required_approvals` **complete** — does the source clause demand any authority whose sign-off is not enumerated? This audits the completeness of the obligation list, not whether any approval has been obtained.

## 7. Reasoning

**What the source clause demands.** The acceptance cell begins with the word
"**Approved**", so this row unambiguously requires a named authority's sign-off
on the source-of-truth authority table. The question is *which* authority, and
whether one is enough given the table spans eight data classes: raw documents,
SQL facts, claims, calculations, narrative memory, derivative indices, evidence
packages, and reports.

**Against the enumerated inventory.** Two requirements are declared:
`APR-REG-B-03-01` (`DELEGATED_ARTIFACT_APPROVAL`, the universal
specification-review obligation) and `APR-REG-B-03-02`
(`DOMAIN_EXPERT_ACCEPTANCE`, required authority "Data-domain authority", scope
"B-03 under S10: Establish source-of-truth matrix"). "Data-domain authority" is
one of the five literals the closed vocabulary permits for
`DOMAIN_EXPERT_ACCEPTANCE` (`validate_ledger_structural.py:2586`).

**The sharpest question on this row: do "calculations" and "narrative memory"
pull in further authorities?** The vocabulary does contain a
"Calculation-domain authority" and a `MEMORY_PROMOTION` / "Responsible analyst"
type, and both are in active use elsewhere in this ledger — on `B-07` and
`C-10` respectively. I checked whether their absence here is a gap and concluded
it is not. What `B-03` approves is *the authority table*: the single
determination of which store is authoritative for each data class. It is one
data-architecture decision, and the authority competent to make it is the
data-domain authority. It is not an approval of any calculation, nor a
promotion of any memory record; those are separate determinations that the
register assigns to their own rows, which carry their own requirements.
Duplicating them here would create parallel requirements for decisions the
register has already located elsewhere, and each would then need its own
distinct record (goal L188).

**Independent corroboration.** Gate `PG-05-05` — "the source-of-truth matrix is
approved" — is the only gate clause whose `related_register_ids` contains
`B-03`, and it carries exactly one approval:
`DOMAIN_EXPERT_ACCEPTANCE` / "Data-domain authority". Two authorities derived
independently (the register cell and the phase-gate clause) agree on precisely
one authority literal. `B-03` declares no dependencies, so no dependency-derived
obligation exists; `security_exception_ids` and `approval_records` are empty.

**Human-review links.** `["HR-0003","HR-0004"]`, both resolving to `DECISION`
entries whose scope contains this component. `HR-0003`'s decision authority is
`GOAL_OR_PROCESS_AUTHORIZATION`, a human-resolution decision type that is never
an inventory obligation.

`required_approvals` is complete for the clause as written.

## 8. Verdict

No omission found. The obligation list is complete against the source clause as
written, against the phase-gate and disposition authorities that reach this row,
and against the contract's closed vocabularies.

verdict: CLEAN
