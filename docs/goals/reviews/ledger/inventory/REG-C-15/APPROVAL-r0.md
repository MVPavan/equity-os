# Inventory review — `REG-C-15` — `APPROVAL` — `r0`

**verdict: CLEAN**

## 1. Review identity and role binding

| Field | Value |
|---|---|
| Component ID | `REG-C-15` |
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

`REG-C-15` is a `register_row`. `validate_ledger_preimplementation.py:199-204`
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

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line 86
(file SHA-256 `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`), read verbatim:

```
| C-15 | Critical | Enforce run knowledge cutoff across stores and tools | SQL/document/memory retrieval applies `knowledge_time <= cutoff`; canonical selections are resolved as of the cutoff so later restatements/corrections do not rewrite history; tool gateway records cutoff capability; tests insert and reject post-cutoff records | B-03, C-02, C-03 | Open |
```

| Binding | Ledger value | Recomputed from the pinned bytes | Match |
|---|---|---|---|
| `text_digest` | `ba0cfc2d154d387a2ab553f1fe2df1ac0f5e7c2bf82ef56c803b3edfb84df206` | `ba0cfc2d154d387a2ab553f1fe2df1ac0f5e7c2bf82ef56c803b3edfb84df206` | yes |
| `source_title` | `Enforce run knowledge cutoff across stores and tools` | cell 3 of the row | yes |
| `required_acceptance_text` | (cell 4, reproduced below) | cell 4 of the row | yes |
| `source_status` | `Open` | cell 6 of the row | yes |
| `priority` | `Critical` | cell 2 of the row | yes |

Acceptance text bound by the ledger:

> SQL/document/memory retrieval applies `knowledge_time <= cutoff`; canonical selections are resolved as of the cutoff so later restatements/corrections do not rewrite history; tool gateway records cutoff capability; tests insert and reject post-cutoff records

Owning spec: `S11` — Run manifest, knowledge cutoff, and layered reproducibility
(`docs/specs/equity-os-s11-run-manifest-cutoff-reproducibility.md`). Blueprint phase `1`,
program disposition `REQUIRED_NOW`, delivery status
`SPEC_DRAFT`. `disposition_refs` = `["G-1", "M-4", "6.9"]`,
`gate_refs` = `["PG-1-05"]`,
`dependencies` = `["B-03", "C-02", "C-03"]`.

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
      "approval_id": "APR-REG-C-15-01",
      "approval_type": "DELEGATED_ARTIFACT_APPROVAL",
      "evidence_ref_ids": [],
      "matched_record_id": null,
      "required_authority": "Delegated fresh Sol xhigh specification reviewer",
      "scope": "C-15 under S11: Enforce run knowledge cutoff across stores and tools",
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

**What the source clause demands.** "SQL/document/memory retrieval applies
`knowledge_time <= cutoff`; canonical selections are resolved as of the cutoff
so later restatements/corrections do not rewrite history; tool gateway records
cutoff capability; tests insert and reject post-cutoff records". Four technical
conjuncts. No approval verb, no acceptance verb, no named authority — the
clause is entirely about enforced mechanism.

**Against the enumerated inventory.** One requirement is declared:
`APR-REG-C-15-01`, `DELEGATED_ARTIFACT_APPROVAL`, the universal
specification-review obligation, scope "C-15 under S11: Enforce run knowledge
cutoff across stores and tools".

**Derivation sources checked one by one.**

- *Acceptance text*: "tool gateway **records** cutoff capability" is the one
  phrase worth pausing on. It is a capability *record*, not a sign-off; nothing
  is being approved by anyone.
- *Phase gates*: `gate_refs` is `["PG-1-05"]`, confirmed by reverse scan to be
  the only gate clause relating to `C-15`. `PG-1-05` carries
  `required_approvals == []`. This is a genuinely discriminating observation
  rather than a formality: its immediate sibling `PG-1-06` — the very next gate
  clause, related to `C-08`/`C-16` — *does* carry `ANALYST_ACCEPTANCE` /
  "Responsible analyst", and that obligation is correspondingly present on
  `C-16` in this same batch. So the gate axis is demonstrably capable of
  producing an approval obligation, and here it produces none.
- *Dependencies*: `B-03`, `C-02`, `C-03`. `B-03` holds
  `DOMAIN_EXPERT_ACCEPTANCE` / "Data-domain authority" for the source-of-truth
  table. That determination — which store is authoritative for each data class —
  is exercised on `B-03`, and `C-15` depends on it; enforcing a time predicate
  over those stores raises no second data-domain question, and a duplicate
  requirement would need a second, distinct record (goal L188).
- *Dispositions*: `G-1`, `M-4`, `6.9` are S11 spec-level tags. `M-4`, whose
  register scope actually contains `C-15`, is explicitly dispositioned as
  "implementation requirements" and `DISP-M-4` itself carries only the delegated
  approval — so the disposition that most directly governs this row is itself
  free of a business authority. `G-1`'s analyst acceptance attaches to the
  approved narrative (`C-16`), not to cutoff enforcement.
- *Fail-closed boundaries / security exceptions*: `security_exception_ids` is
  empty; `approval_records` is empty.

**Human-review links.** `"HR-0004"` (a single string, which the schema permits
alongside `null` and a sorted array of two or more). It resolves to a `DECISION`
entry whose scope contains this component, and its authority type is
`GOAL_OR_PROCESS_AUTHORIZATION` — a human-resolution decision type that is
never a component inventory obligation.

`required_approvals` is complete for the clause as written.

## 8. Verdict

No omission found. The obligation list is complete against the source clause as
written, against the phase-gate and disposition authorities that reach this row,
and against the contract's closed vocabularies.

verdict: CLEAN
