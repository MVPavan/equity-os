# Inventory review — `REG-C-15` — `EVIDENCE` — `r0`

**verdict: CLEAN**

## 1. Review identity and role binding

| Field | Value |
|---|---|
| Component ID | `REG-C-15` |
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

The `EVIDENCE` inventory is defined by goal L433-434: the `EVIDENCE` reviewed inventory is the complete `required_evidence`, `evidence_refs`, and `verification_command` collections.
Transcribed here directly from the canonical ledger bytes whose SHA-256 is
recorded in §2:

```json
{
  "evidence_refs": [
    {
      "captured_at": "2026-08-13T02:49:11Z",
      "content_sha256": "ba0cfc2d154d387a2ab553f1fe2df1ac0f5e7c2bf82ef56c803b3edfb84df206",
      "digest_mode": "UTF8_LINE_SPAN",
      "end_line": 86,
      "evidence_ref_id": "EV-REG-C-15-SOURCE",
      "path": "docs/blueprint/funda-blueprint-implementation-decision-register-v2.md",
      "scope": "Exact authoritative source occurrence for REG-C-15",
      "start_line": 86
    },
    {
      "captured_at": "2026-08-13T02:49:11Z",
      "content_sha256": "f6158ce7d04109cbb954a4113bd43046428028abd30c34f0652ca3aae52ccf8e",
      "digest_mode": "FILE_BYTES",
      "end_line": null,
      "evidence_ref_id": "EV-REG-C-15-SPEC-DRAFT",
      "path": "docs/specs/equity-os-s11-run-manifest-cutoff-reproducibility.md",
      "scope": "Current draft specification bytes for REG-C-15",
      "start_line": null
    }
  ],
  "required_evidence": [
    {
      "approval_ids": [],
      "description": "Current proof satisfying: SQL/document/memory retrieval applies `knowledge_time <= cutoff`; canonical selections are resolved as of the cutoff so later restatements/corrections do not rewrite history; tool gateway records cutoff capability; tests insert and reject post-cutoff records",
      "evidence_id": "REQ-REG-C-15-ACCEPTANCE",
      "evidence_ref_ids": [],
      "evidence_type": "ARTIFACT",
      "proof_mode": "CONTENT_HASH",
      "scope": "REG-C-15 acceptance and delivery scope",
      "status": "UNRESOLVED"
    },
    {
      "approval_ids": [],
      "description": "Persisted clean fresh Sol xhigh review of the current specification bytes",
      "evidence_id": "REQ-REG-C-15-SPEC-REVIEW",
      "evidence_ref_ids": [],
      "evidence_type": "REVIEW",
      "proof_mode": "CONTENT_HASH",
      "scope": "C-15 under S11: Enforce run knowledge cutoff across stores and tools",
      "status": "UNRESOLVED"
    },
    {
      "approval_ids": [],
      "description": "Reproducible command result proving the current REG-C-15 acceptance obligation",
      "evidence_id": "REQ-REG-C-15-COMMAND-PROOF",
      "evidence_ref_ids": [],
      "evidence_type": "COMMAND_RESULT",
      "proof_mode": "COMMAND",
      "scope": "REG-C-15 command proof",
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

**What the source clause demands.** `C-15` (v2 line 86) is "Enforce run
knowledge cutoff across stores and tools". Its acceptance cell is unusually
dense and has four separable conjuncts: (i) "SQL/document/memory retrieval
applies `knowledge_time <= cutoff`"; (ii) "canonical selections are resolved as
of the cutoff so later restatements/corrections do not rewrite history";
(iii) "tool gateway records cutoff capability"; and (iv) "**tests insert and
reject post-cutoff records**". Conjunct (iv) is an explicit demand for an
executed check — the clause does not merely describe a property, it requires a
test to exist and to reject.

**Against the enumerated inventory.** Three items are declared, and the split
is the right one.

1. `REQ-REG-C-15-ACCEPTANCE` (`ARTIFACT` / `CONTENT_HASH`) carries the whole
   acceptance cell verbatim (recomputed and matched), so conjuncts (i)–(iii) —
   the retrieval predicate, the as-of canonical selection semantics, and the
   gateway capability record — are inside one hashed artifact obligation.
   Conjunct (ii) is the one most easily lost in a paraphrase, and the
   byte-identical description preserves it.
2. `REQ-REG-C-15-COMMAND-PROOF` (`COMMAND_RESULT` / `COMMAND`) discharges
   conjunct (iv). The pairing is contract-enforced: `COMMAND_RESULT` forces
   `proof_mode == "COMMAND"` (`validate_ledger_structural.py:2130-2131`), and
   `REG-C-15` is one of the twenty-five components in the pinned
   `EXPECTED_COMMAND_PROOF_COMPONENTS` set (`:2635-2649`), so the item is
   required to be here and could not be dropped.
3. `REQ-REG-C-15-SPEC-REVIEW` (`REVIEW` / `CONTENT_HASH`) is the
   persisted-review proof for the row's single `DELEGATED_ARTIFACT_APPROVAL`.

**Independent corroboration for the command item.** Gate `PG-1-05` —
"post-cutoff data are excluded by tested store/tool controls", the only gate
clause whose `related_register_ids` contains `C-15` — itself carries a
`COMMAND_RESULT` requirement. Two authorities (the register cell and the gate
clause) independently demand an executed control test, and both are enumerated.

**Is anything else demanded?** Conjunct (iii), "tool gateway records cutoff
capability", is a *record* obligation satisfied by the hashed gateway artifact,
not a separate approval or command. `verification_command.mode` is `UNRESOLVED`
and `verification_result` is empty; the goal permits `UNRESOLVED` during initial
ledger construction, and the standing obligation is carried by the
`COMMAND_RESULT` requirement rather than by a declared command, so no
enumerated proof is missing at this stage.

**Disposition `M-4`.** Its register scope is `C-15` and `E-10`, and it states
the cutoff controls as "implementation requirements" — every bullet it lists
(cutoff per run, retrieval enforcement, as-of canonical selection, cutoff-aware
tool declarations, approved archived sources for replay, deliberately inserted
post-cutoff records excluded by tests) is already inside the acceptance cell or
inside `DISP-M-4`'s own command proof. It adds no proof kind here.

`required_evidence` is complete for the clause as written.

## 8. Verdict

No omission found. The obligation list is complete against the source clause as
written, against the phase-gate and disposition authorities that reach this row,
and against the contract's closed vocabularies.

verdict: CLEAN
