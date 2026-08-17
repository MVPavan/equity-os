# Inventory review — `REG-C-16` — `EVIDENCE` — `r0`

**verdict: CLEAN**

## 1. Review identity and role binding

| Field | Value |
|---|---|
| Component ID | `REG-C-16` |
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

The `EVIDENCE` inventory is defined by goal L433-434: the `EVIDENCE` reviewed inventory is the complete `required_evidence`, `evidence_refs`, and `verification_command` collections.
Transcribed here directly from the canonical ledger bytes whose SHA-256 is
recorded in §2:

```json
{
  "evidence_refs": [
    {
      "captured_at": "2026-08-13T02:49:11Z",
      "content_sha256": "5937ceac7c918ea305d1f4bdffbacd0ab6a04be781f00f7c8a408c8e9ef0d711",
      "digest_mode": "UTF8_LINE_SPAN",
      "end_line": 87,
      "evidence_ref_id": "EV-REG-C-16-SOURCE",
      "path": "docs/blueprint/funda-blueprint-implementation-decision-register-v2.md",
      "scope": "Exact authoritative source occurrence for REG-C-16",
      "start_line": 87
    },
    {
      "captured_at": "2026-08-13T02:49:11Z",
      "content_sha256": "f6158ce7d04109cbb954a4113bd43046428028abd30c34f0652ca3aae52ccf8e",
      "digest_mode": "FILE_BYTES",
      "end_line": null,
      "evidence_ref_id": "EV-REG-C-16-SPEC-DRAFT",
      "path": "docs/specs/equity-os-s11-run-manifest-cutoff-reproducibility.md",
      "scope": "Current draft specification bytes for REG-C-16",
      "start_line": null
    }
  ],
  "required_evidence": [
    {
      "approval_ids": [],
      "description": "Current proof satisfying: Exact-class operators replay exactly; floating-point/optimization outputs meet declared tolerances; stochastic operators store seeds and test distributions; evidence package reconstructs exactly; approved narrative bytes are immutable and bound to content hash",
      "evidence_id": "REQ-REG-C-16-ACCEPTANCE",
      "evidence_ref_ids": [],
      "evidence_type": "ARTIFACT",
      "proof_mode": "CONTENT_HASH",
      "scope": "REG-C-16 acceptance and delivery scope",
      "status": "UNRESOLVED"
    },
    {
      "approval_ids": [],
      "description": "Persisted clean fresh Sol xhigh review of the current specification bytes",
      "evidence_id": "REQ-REG-C-16-SPEC-REVIEW",
      "evidence_ref_ids": [],
      "evidence_type": "REVIEW",
      "proof_mode": "CONTENT_HASH",
      "scope": "C-16 under S11: Implement layered reproducibility and artifact approval",
      "status": "UNRESOLVED"
    },
    {
      "approval_ids": [
        "APR-REG-C-16-02"
      ],
      "description": "Typed ANALYST_ACCEPTANCE proof for C-16 analyst acceptance",
      "evidence_id": "REQ-REG-C-16-ANALYST_ACCEPTANCE-02",
      "evidence_ref_ids": [],
      "evidence_type": "ANALYST",
      "proof_mode": "TYPED_APPROVAL",
      "scope": "C-16 analyst acceptance",
      "status": "UNRESOLVED"
    },
    {
      "approval_ids": [],
      "description": "Reproducible command result proving the current REG-C-16 acceptance obligation",
      "evidence_id": "REQ-REG-C-16-COMMAND-PROOF",
      "evidence_ref_ids": [],
      "evidence_type": "COMMAND_RESULT",
      "proof_mode": "COMMAND",
      "scope": "REG-C-16 command proof",
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

**What the source clause demands.** `C-16` (v2 line 87) is "Implement layered
reproducibility and artifact approval", and its acceptance cell carries five
separable conjuncts: (i) "Exact-class operators replay exactly"; (ii)
"floating-point/optimization outputs meet declared tolerances"; (iii)
"stochastic operators store seeds and test distributions"; (iv) "evidence
package reconstructs exactly"; and (v) "**approved** narrative bytes are
immutable and bound to content hash". This clause demands three different kinds
of proof at once — executed replay, a hashed artifact, and an act of approval —
so it is the strongest completeness test in the batch.

**Against the enumerated inventory.** Four items are declared, and each of the
three proof kinds is present.

1. `REQ-REG-C-16-ACCEPTANCE` (`ARTIFACT` / `CONTENT_HASH`) carries the whole
   acceptance cell verbatim (recomputed and matched), so conjuncts (ii) and (v)'s
   immutability-and-hash-binding property are inside a hashed obligation.
2. `REQ-REG-C-16-COMMAND-PROOF` (`COMMAND_RESULT` / `COMMAND`) discharges the
   executed-verification conjuncts (i), (iii) and (iv) — "replay exactly",
   "test distributions", "reconstructs exactly". `REG-C-16` is one of the
   twenty-five components in the pinned `EXPECTED_COMMAND_PROOF_COMPONENTS`
   set (`validate_ledger_structural.py:2635-2649`), so this item is
   contract-required rather than optional.
3. `REQ-REG-C-16-ANALYST_ACCEPTANCE-02` (`ANALYST` / `TYPED_APPROVAL`,
   `approval_ids == ["APR-REG-C-16-02"]`, scope "C-16 analyst acceptance")
   discharges conjunct (v)'s word "**approved**". `ANALYST` is inside
   `human_evidence_types` (`:2101-2105`), forcing `TYPED_APPROVAL` and closing
   off the fabricated-shell-command path for a human acceptance.
4. `REQ-REG-C-16-SPEC-REVIEW` (`REVIEW` / `CONTENT_HASH`) is the
   persisted-review proof for the `DELEGATED_ARTIFACT_APPROVAL`.

I checked the requirement-to-evidence mapping directly: both non-delegated
approval requirements on this row have a `TYPED_APPROVAL` item bound to them,
and the delegated one is proven by the `REVIEW` item (which cannot carry
`approval_ids`, since `:2134-2137` forbids them on a non-`TYPED_APPROVAL` item).

**Independent corroboration.** Gate `PG-1-06` — "deterministic calculations
satisfy their declared exact/tolerance/seeded replay class and the approved
narrative is bound to an artifact hash", the gate clause relating `C-08` and
`C-16` — carries an `ARTIFACT` acceptance, an `ANALYST`/`TYPED_APPROVAL` item,
*and* a `COMMAND_RESULT` item. That is the same three-kind shape derived from a
second authority, and `C-16` matches it.

**Disposition `6.9`.** "'bit-exact' should apply only to operators designed for
exact replay. Floating-point, optimization, and stochastic calculations require
declared tolerances, pinned environments, and stored seeds as applicable." Every
element — exact-replay class, tolerances, seeds — is already in the acceptance
cell I hashed. "Pinned environments" is the one element phrased only in the
disposition; it is a property of how the replay command is run, and is
discharged through the same `COMMAND_RESULT` obligation rather than by a
separate proof kind. `DISP-6-9` itself carries `ARTIFACT` and `COMMAND_RESULT`
requirements, matching that reading.

`required_evidence` is complete for the clause as written.

## 8. Verdict

No omission found. The obligation list is complete against the source clause as
written, against the phase-gate and disposition authorities that reach this row,
and against the contract's closed vocabularies.

verdict: CLEAN
