# Inventory review — REG-C-08 — EVIDENCE — r0

**Verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| Component ID | `REG-C-08` |
| Review type | `EVIDENCE` |
| Round | `r0` |
| Reviewer | Reviewer role (CONTEXT.md "Agent roles (harness-wide)"), Claude Code session `8958a695-f635-4f4e-8747-5433095fbc1a` |
| Role | `REVIEWER` |
| Role binding path | `CONTEXT.md` |
| Role binding SHA-256 at review time | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| Model actually invoked | `claude-opus-5` |
| Effort actually invoked | `high` |
| Review UTC | `2026-08-16T13:45:24Z` |
| Batch | 17 (`register_row`, owning specs S15–S18) per recording design r2 §5.2 |

## Input hashes read at review time

| Input | Path | SHA-256 |
|---|---|---|
| Active goal | `docs/goals/equity-os-blueprint-completion.md` | `f15f7ab5a4e425dec3877ab7f1f7594687979060e4dbcd49390a8a8d5fedb85f` |
| Canonical ledger | `docs/goals/equity-os-blueprint-component-ledger.jsonl` | `de236d7e8dcf02e307ec58797f5722ae2f85d1d8cdba57d4ecc07df5383c9c97` |
| Pinned decision register v2 | `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| Third-order disposition report | `docs/blueprint/funda-third-order-review-disposition-report.md` | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| Structural validator | `scripts/equity_os_blueprint/validate_ledger_structural.py` | `731d0d8b208b577967c92e3992e7ec1a4333cdecbf89f6951c32d2ec469436f9` |
| Preimplementation validator | `scripts/equity_os_blueprint/validate_ledger_preimplementation.py` | `f7a225a1f99cb85c92cde3094505a92a746552280eb45dae0253a71ab9048013` |
| Human-review artifact | `docs/goals/equity-os-blueprint-human-review-needed.md` | `094fcdfab74a3f4c6fdb82b1520fc4d13b636ac0e9ed10194e5d607aed2ce9af` |
| Role binding | `CONTEXT.md` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |

Fresh at these bytes: `extract_goal_validators.py --check` exit `0`;
`validate_ledger_structural.py --repo-root .` exit `0`.

## Applicability

`REG-C-08.kind == "register_row"`; `scope_derivation.semantic_review` is `null`
(verified on the row; goal L208-211). `EVIDENCE` and `APPROVAL` only; no
`SCOPE` artifact.

## Live source occurrence (pinned authority)

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md:79`,
section **C. Phase 1 — Evidence-grounded MVP**, register ID `C-08`, status
`Open`, priority `High`:

> | C-08 | High | Implement minimum deterministic calculations | Growth, margins, cash conversion, leverage, dilution/share count, guidance comparison, and reconciliation traces pass tests and fail closed | B-07 | Open |

Recomputed `UTF8_LINE_SPAN` digest of line 79:
`324fbfa23a198557beb9dbd588a086b9de5e6c6db03e10bfeb944eb360af17ea` — equals
`text_digest` and `EV-REG-C-08-SOURCE.content_sha256`. `required_acceptance_text`
is byte-identical to the acceptance cell.

## Reviewed inventory, exactly as read

`required_evidence` (3 items):

| `evidence_id` | `evidence_type` | `proof_mode` | `status` | `approval_ids` |
|---|---|---|---|---|
| `REQ-REG-C-08-ACCEPTANCE` | `ARTIFACT` | `CONTENT_HASH` | `UNRESOLVED` | `[]` |
| `REQ-REG-C-08-SPEC-REVIEW` | `REVIEW` | `CONTENT_HASH` | `UNRESOLVED` | `[]` |
| `REQ-REG-C-08-COMMAND-PROOF` | `COMMAND_RESULT` | `COMMAND` | `UNRESOLVED` | `[]` |

- `…-ACCEPTANCE.description` = "Current proof satisfying: Growth, margins, cash
  conversion, leverage, dilution/share count, guidance comparison, and
  reconciliation traces pass tests and fail closed".
- `…-SPEC-REVIEW` scope = "C-08 under S16: Implement minimum deterministic
  calculations".
- `…-COMMAND-PROOF.description` = "Reproducible command result proving the
  current REG-C-08 acceptance obligation", scope "REG-C-08 command proof".

`evidence_refs` (2): `EV-REG-C-08-SOURCE` (`UTF8_LINE_SPAN`, register v2:79,
`2026-08-13T02:49:11Z`) and `EV-REG-C-08-SPEC-DRAFT` (`FILE_BYTES`,
`docs/specs/equity-os-s16-minimum-deterministic-compute.md`,
`b3d436e95b874445cb9000a7ee89c69c5a9bcdee03433865b83280e09842b3d6`,
`2026-08-15T07:13:28Z`). Both recomputed: current.

`verification_command` = `{"mode": "UNRESOLVED", "commands": [],
"not_applicable_review": null}`.

## Reasoning

1. **Clause decomposition.** Seven calculation families — growth, margins, cash
   conversion, leverage, dilution/share count, guidance comparison,
   reconciliation traces — must satisfy two predicates: they "**pass tests**"
   and they "**fail closed**". All seven families and both predicates are
   carried verbatim in `REQ-REG-C-08-ACCEPTANCE.description`.

2. **The executable obligation is enumerated, and this is the decisive check on
   this row.** "Pass tests" is an explicit demand for a reproducible execution
   result, which cannot be discharged by a content-hashed document.
   `REQ-REG-C-08-COMMAND-PROOF` is present with `evidence_type =
   COMMAND_RESULT` and `proof_mode = COMMAND`, which is the only classification
   the goal's typed-evidence schema offers for that demand (goal L476-484;
   validator asserts `evidence_type == "COMMAND_RESULT"` implies
   `proof_mode == "COMMAND"` at goal L3484-3486). Independently, the goal pins
   `REG-C-08` as a member of the closed
   `EXPECTED_COMMAND_PROOF_COMPONENTS` set (goal L3989-3996; checked-in
   validator `:2635`, asserted `:2649`) — my reading of the clause and the pin
   agree.

   This is worth stating explicitly: the r0 program-level evidence-inventory
   review (`equity-os-blueprint-evidence-inventory-r0.md`, Critical finding 2)
   recorded that **no** ledger requirement used `COMMAND`, and named `REG-C-08`
   as one of the ten register rows whose test/replay obligation was
   unrepresented. At the bytes I read, that finding is remediated on this row:
   the `COMMAND_RESULT` item exists.

3. **"Fail closed" is covered by the same two items.** The negative behaviour —
   a missing input must not silently produce a number — is a runtime property
   provable by the same test harness, and it is stated verbatim inside the
   `ACCEPTANCE` description. The corresponding gate, `PG-1-04` ("missing inputs
   fail closed", `related_register_ids = ["C-08"]`), also carries a
   `COMMAND_RESULT` item (`REQ-PG-1-04-COMMAND-PROOF`, verified), so the
   fail-closed obligation is proven on both the register row and its gate.

4. **Gate cross-check.** `gate_refs` = `["PG-1-04", "PG-1-06"]`. I read both.
   `PG-1-06` ("deterministic calculations satisfy their declared
   exact/tolerance/seeded replay class and the approved narrative is bound to an
   artifact hash", `related_register_ids = ["C-08","C-16"]`) carries
   `ACCEPTANCE` + `ANALYST_ACCEPTANCE` + `COMMAND-PROOF`. Its analyst-acceptance
   arm attaches to the "approved narrative" half of the clause, which is
   `C-16`'s scope — and `REG-C-16` does carry its own `ANALYST_ACCEPTANCE` and
   `COMMAND-PROOF` items (verified). Nothing the gates demand of C-08's half is
   missing from C-08's inventory.

5. **Disposition cross-check.** `disposition_refs` are `G-1` and `6.9`. G-1
   (report L47-59) splits reproducibility into calculation replay, evidence-
   package reconstruction, and immutable narrative; §6.9 (L396-398) confines
   bit-exactness to operators designed for exact replay and requires declared
   tolerances, pinned environments, and stored seeds elsewhere. Both are
   separately ledgered with their own `COMMAND_RESULT` items — `DISP-G-1`
   (`ACCEPTANCE` + `ANALYST_ACCEPTANCE` + `COMMAND-PROOF`) and `DISP-6-9`
   (`ACCEPTANCE` + `COMMAND-PROOF`), verified. Under register v2's Authority
   rule (L23) they refine how the tests are specified rather than adding a
   distinct obligation to this row.

6. **Dependency.** `B-07` defines the approved MVP operator list and carries the
   `DOMAIN_EXPERT_ACCEPTANCE` for it; C-08 implements that list. The definition
   approval stays on `B-07` (goal L188).

7. **`verification_command` = `UNRESOLVED`.** Valid during initial ledger
   construction (goal L500-502). Note the distinction that matters here: the
   `COMMAND_RESULT` *requirement* is the enumerated obligation this review
   audits; populating `verification_command.mode = COMMANDS` with an argv and
   digest is the later delivery step. Their both being unresolved now is
   consistent, and the requirement's presence is what keeps the obligation from
   being lost.

No omission found; all three items are correctly typed and jointly cover both
clause predicates.

## Verdict

verdict: CLEAN
