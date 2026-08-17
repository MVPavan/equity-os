# Inventory review — `REG-C-16` — `APPROVAL` — `r0`

**verdict: CLEAN**

## 1. Review identity and role binding

| Field | Value |
|---|---|
| Component ID | `REG-C-16` |
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

`REG-C-16` is a `register_row`. `validate_ledger_preimplementation.py:199-204`
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

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line 87
(file SHA-256 `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`), read verbatim:

```
| C-16 | Critical | Implement layered reproducibility and artifact approval | Exact-class operators replay exactly; floating-point/optimization outputs meet declared tolerances; stochastic operators store seeds and test distributions; evidence package reconstructs exactly; approved narrative bytes are immutable and bound to content hash | B-03, B-07, C-08 | Open |
```

| Binding | Ledger value | Recomputed from the pinned bytes | Match |
|---|---|---|---|
| `text_digest` | `5937ceac7c918ea305d1f4bdffbacd0ab6a04be781f00f7c8a408c8e9ef0d711` | `5937ceac7c918ea305d1f4bdffbacd0ab6a04be781f00f7c8a408c8e9ef0d711` | yes |
| `source_title` | `Implement layered reproducibility and artifact approval` | cell 3 of the row | yes |
| `required_acceptance_text` | (cell 4, reproduced below) | cell 4 of the row | yes |
| `source_status` | `Open` | cell 6 of the row | yes |
| `priority` | `Critical` | cell 2 of the row | yes |

Acceptance text bound by the ledger:

> Exact-class operators replay exactly; floating-point/optimization outputs meet declared tolerances; stochastic operators store seeds and test distributions; evidence package reconstructs exactly; approved narrative bytes are immutable and bound to content hash

Owning spec: `S11` — Run manifest, knowledge cutoff, and layered reproducibility
(`docs/specs/equity-os-s11-run-manifest-cutoff-reproducibility.md`). Blueprint phase `1`,
program disposition `REQUIRED_NOW`, delivery status
`SPEC_DRAFT`. `disposition_refs` = `["G-1", "M-4", "6.9"]`,
`gate_refs` = `["PG-1-06"]`,
`dependencies` = `["B-03", "B-07", "C-08"]`.

## 5. Reviewed inventory, exactly as read

The `APPROVAL` inventory is defined by goal L435-436: the `APPROVAL` reviewed inventory is the complete `required_approvals`, `approval_records`, `human_review_id`, and `security_exception_ids` collections.
Transcribed here directly from the canonical ledger bytes whose SHA-256 is
recorded in §2:

```json
{
  "approval_records": [],
  "human_review_id": "HR-0004",
  "required_approvals": [
    {
      "actor": null,
      "approval_id": "APR-REG-C-16-01",
      "approval_type": "DELEGATED_ARTIFACT_APPROVAL",
      "evidence_ref_ids": [],
      "matched_record_id": null,
      "required_authority": "Delegated fresh Sol xhigh specification reviewer",
      "scope": "C-16 under S11: Implement layered reproducibility and artifact approval",
      "status": "UNRESOLVED",
      "timestamp": null
    },
    {
      "actor": null,
      "approval_id": "APR-REG-C-16-02",
      "approval_type": "ANALYST_ACCEPTANCE",
      "evidence_ref_ids": [],
      "matched_record_id": null,
      "required_authority": "Responsible analyst",
      "scope": "C-16 analyst acceptance",
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

**What the source clause demands.** "Exact-class operators replay exactly;
floating-point/optimization outputs meet declared tolerances; stochastic
operators store seeds and test distributions; evidence package reconstructs
exactly; **approved** narrative bytes are immutable and bound to content hash".
The final conjunct contains an approval verb applied to a specific object — the
published narrative — so this row genuinely requires a named authority, and the
review question is whether the enumerated one is the right one and whether it is
the only one.

**Against the enumerated inventory.** Two requirements are declared:
`APR-REG-C-16-01` (`DELEGATED_ARTIFACT_APPROVAL`, the universal
specification-review obligation) and `APR-REG-C-16-02` (`ANALYST_ACCEPTANCE`,
authority "Responsible analyst", scope "C-16 analyst acceptance").
"Responsible analyst" is the single literal the closed vocabulary permits for
`ANALYST_ACCEPTANCE` (`validate_ledger_structural.py:2586`), so the requirement
is on-vocabulary and cannot have silently invented an authority string.

**Corroboration from two independent authorities.** Gate `PG-1-06` — "…and the
approved narrative is bound to an artifact hash" — is the gate clause relating
`C-08` and `C-16`, and it carries exactly `ANALYST_ACCEPTANCE` / "Responsible
analyst". Disposition `G-1`, whose register scope contains `C-16`, states as its
third guarantee that "the approved published bytes are immutable and bound to a
content hash", and `DISP-G-1` likewise carries `ANALYST_ACCEPTANCE` /
"Responsible analyst". Three sources — register cell, phase gate, disposition —
converge on one authority, and that authority is enumerated.

**Is any further authority demanded?** I considered
`DOMAIN_EXPERT_ACCEPTANCE` / "Calculation-domain authority", since conjuncts
(i)–(iv) are about calculation replay classes and tolerances. It is not demanded
here: the register assigns the calculation-domain determination to `B-07`
(which carries exactly that requirement), and `C-16`'s conjuncts are engineering
*declarations* — a declared tolerance, a stored seed, a replay class — proved by
executed replay rather than approved by a domain authority. The clause's only
approval verb governs the narrative, and that is the requirement present.

**Other derivation sources.** `gate_refs` is `["PG-1-06"]`, confirmed by reverse
scan. Dependencies are `B-03`, `B-07`, `C-08`; `B-03`'s data-domain and `B-07`'s
calculation-domain determinations are exercised on those rows, and duplicating
them here would demand second, distinct records for the same decisions (goal
L188). `security_exception_ids` and `approval_records` are empty.

**Human-review links.** `"HR-0004"`, resolving to a `DECISION` entry whose scope
contains this component; its authority type `GOAL_OR_PROCESS_AUTHORIZATION` is a
human-resolution decision type, never a component inventory obligation (it
appears zero times in `required_approvals` anywhere in this ledger).

`required_approvals` is complete for the clause as written.

## 8. Verdict

No omission found. The obligation list is complete against the source clause as
written, against the phase-gate and disposition authorities that reach this row,
and against the contract's closed vocabularies.

verdict: CLEAN
