# Inventory review — `REG-C-09` — `EVIDENCE` — `r0`

**verdict: CLEAN**

## 1. Review identity and role binding

| Field | Value |
|---|---|
| Component ID | `REG-C-09` |
| Component kind | `register_row` |
| Review type | `EVIDENCE` |
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

`REG-C-09` is a `register_row`. `validate_ledger_preimplementation.py:199-204`
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

The `EVIDENCE` slot as read, `PENDING` with the exact 10-key `PENDING` key
set and no role-binding keys (`validate_ledger_structural.py:238-243`,
`:320-356`):

```json
{
  "effort": null,
  "evidence_ref_ids": [],
  "model": null,
  "review_type": "EVIDENCE",
  "reviewed_input_sha256": null,
  "reviewed_inventory_sha256": null,
  "reviewer": null,
  "status": "PENDING",
  "timestamp": null,
  "verdict": null
}
```

## 4. Source clause, as read in the pinned authority

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line 80
(file SHA-256 `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`), read verbatim:

```
| C-09 | High | Implement complete run manifest | Inputs, cutoff, source/evidence-package versions, tools, models, prompts, code versions, costs, calculations, QA, approvals, and exact published-artifact hash are registered | C-16 | Open |
```

| Binding | Ledger value | Recomputed from the pinned bytes | Match |
|---|---|---|---|
| `text_digest` | `0443a0a26b52985de0490d6c048dc951c8fffac0849a1a40b6606840b911d246` | `0443a0a26b52985de0490d6c048dc951c8fffac0849a1a40b6606840b911d246` | yes |
| `source_title` | `Implement complete run manifest` | cell 3 of the row | yes |
| `required_acceptance_text` | (cell 4, reproduced below) | cell 4 of the row | yes |
| `source_status` | `Open` | cell 6 of the row | yes |
| `priority` | `High` | cell 2 of the row | yes |

Acceptance text bound by the ledger:

> Inputs, cutoff, source/evidence-package versions, tools, models, prompts, code versions, costs, calculations, QA, approvals, and exact published-artifact hash are registered

Owning spec: `S11` — Run manifest, knowledge cutoff, and layered reproducibility
(`docs/specs/equity-os-s11-run-manifest-cutoff-reproducibility.md`). Blueprint phase `1`,
program disposition `REQUIRED_NOW`, delivery status
`SPEC_DRAFT`. `disposition_refs` = `["G-1", "M-4", "6.9"]`,
`gate_refs` = `[]`,
`dependencies` = `["C-16"]`.

## 5. Reviewed inventory, exactly as read

The `EVIDENCE` inventory is defined by goal L433-434: the `EVIDENCE` reviewed inventory is the complete `required_evidence`, `evidence_refs`, and `verification_command` collections.
Transcribed here directly from the canonical ledger bytes whose SHA-256 is
recorded in §2:

```json
{
  "evidence_refs": [
    {
      "captured_at": "2026-08-13T02:49:11Z",
      "content_sha256": "0443a0a26b52985de0490d6c048dc951c8fffac0849a1a40b6606840b911d246",
      "digest_mode": "UTF8_LINE_SPAN",
      "end_line": 80,
      "evidence_ref_id": "EV-REG-C-09-SOURCE",
      "path": "docs/blueprint/funda-blueprint-implementation-decision-register-v2.md",
      "scope": "Exact authoritative source occurrence for REG-C-09",
      "start_line": 80
    },
    {
      "captured_at": "2026-08-13T02:49:11Z",
      "content_sha256": "f6158ce7d04109cbb954a4113bd43046428028abd30c34f0652ca3aae52ccf8e",
      "digest_mode": "FILE_BYTES",
      "end_line": null,
      "evidence_ref_id": "EV-REG-C-09-SPEC-DRAFT",
      "path": "docs/specs/equity-os-s11-run-manifest-cutoff-reproducibility.md",
      "scope": "Current draft specification bytes for REG-C-09",
      "start_line": null
    }
  ],
  "required_evidence": [
    {
      "approval_ids": [],
      "description": "Current proof satisfying: Inputs, cutoff, source/evidence-package versions, tools, models, prompts, code versions, costs, calculations, QA, approvals, and exact published-artifact hash are registered",
      "evidence_id": "REQ-REG-C-09-ACCEPTANCE",
      "evidence_ref_ids": [],
      "evidence_type": "ARTIFACT",
      "proof_mode": "CONTENT_HASH",
      "scope": "REG-C-09 acceptance and delivery scope",
      "status": "UNRESOLVED"
    },
    {
      "approval_ids": [],
      "description": "Persisted clean fresh Sol xhigh review of the current specification bytes",
      "evidence_id": "REQ-REG-C-09-SPEC-REVIEW",
      "evidence_ref_ids": [],
      "evidence_type": "REVIEW",
      "proof_mode": "CONTENT_HASH",
      "scope": "C-09 under S11: Implement complete run manifest",
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

## 6. The question this review decides

Is `required_evidence` **complete** — does the source clause demand any proof that is not enumerated? This audits the completeness of the obligation list, not whether any proof has been obtained.

## 7. Reasoning

**What the source clause demands.** `C-09` (v2 line 80) is "Implement complete
run manifest", accepted when "Inputs, cutoff, source/evidence-package versions,
tools, models, prompts, code versions, costs, calculations, QA, approvals, and
exact published-artifact hash **are registered**". Twelve registration classes.
The demanded proof is the manifest itself — its schema and a populated
instance — whose bytes are hashable.

**Against the enumerated inventory.** Two items are declared.
`REQ-REG-C-09-ACCEPTANCE` (`ARTIFACT` / `CONTENT_HASH`) carries the acceptance
cell verbatim (recomputed and matched), so all twelve classes ride inside a
single hashed obligation. `REQ-REG-C-09-SPEC-REVIEW` (`REVIEW` /
`CONTENT_HASH`) is the persisted-review proof for the row's single
`DELEGATED_ARTIFACT_APPROVAL`.

**Is a command proof missing? This is the closest call in the batch.** A
"complete run manifest" is the kind of thing one would naturally test for field
completeness, and `C-09`'s dependency `C-16` *does* carry a `COMMAND_RESULT`
item. But the criterion the contract actually applies is what the clause
demands, and "are registered" is a registration predicate with no verification
verb — no "tested", "pass tests", "replay", "reconstructs", "reproducible",
"fail closed". Every one of the twenty-five components in the pinned
`EXPECTED_COMMAND_PROOF_COMPONENTS` set has such a verb in its own clause; I
checked the ten register members against their cells and the criterion
discriminates cleanly, including within this very batch (`C-15`: "tests insert
and reject"; `C-16`: "replay exactly … reconstructs exactly" — both carry
command proofs; `C-09`: no verb — does not). `REG-C-09` is absent from that
pinned set, so declaring a command item here would fail
`validate_ledger_structural.py:2649`.

**Does "approvals … are registered" demand a typed-approval evidence item?**
No, and this is the second thing worth stating plainly. The manifest *records a
reference to* approvals obtained elsewhere; recording an approval is not
obtaining one. The approvals being registered are the ones already required on
the components that produce them — `C-16`'s `ANALYST_ACCEPTANCE` for the
approved narrative being the direct example. A `TYPED_APPROVAL` item on `C-09`
would assert that the manifest itself needs a sign-off, which the clause does
not say. The same reading applies to "QA": the closed `evidence_type`
vocabulary has no QA type, and the goal states that an approval type absent
from the pinned table "has no obligation in this inventory".

**Dispositions.** `G-1`, `M-4` and `6.9` are spec-level S11 tags. `G-1` does
name the run manifest — "This correction belongs in the output contract, run
manifest, and Phase 1 gate" — but that is an instruction about *where the
three-guarantee wording is placed*, and the wording it places is already the
subject of `C-15`'s and `C-16`'s acceptance cells. It introduces no proof kind
that `C-09`'s own cell fails to enumerate.

`required_evidence` is complete for the clause as written.

## 8. Verdict

No omission found. The obligation list is complete against the source clause as
written, against the phase-gate and disposition authorities that reach this row,
and against the contract's closed vocabularies.

verdict: CLEAN
