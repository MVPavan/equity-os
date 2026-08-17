# Inventory review — REG-C-06 — EVIDENCE — r0

**Verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| Component ID | `REG-C-06` |
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

`REG-C-06.kind == "register_row"`; `scope_derivation.semantic_review` is `null`
(verified on the row; goal L208-211). `EVIDENCE` and `APPROVAL` only; no
`SCOPE` artifact.

## Live source occurrence (pinned authority)

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md:77`,
section **C. Phase 1 — Evidence-grounded MVP**, register ID `C-06`, status
`Open`, priority `Critical`:

> | C-06 | Critical | Put authoritative corporate actions in SQL | Splits, bonuses, rights, demergers, dividends, ticker changes, and delistings are versioned events | C-17 | Open |

Recomputed `UTF8_LINE_SPAN` digest of line 77:
`5621fa8b8f2f5212dbfd2f00e648200f86683b61e33d6aa043c4b1bf5487d21b` — equals
`text_digest` and `EV-REG-C-06-SOURCE.content_sha256`. `required_acceptance_text`
is byte-identical to the acceptance cell.

## Reviewed inventory, exactly as read

`required_evidence` (2 items):

| `evidence_id` | `evidence_type` | `proof_mode` | `status` | `approval_ids` |
|---|---|---|---|---|
| `REQ-REG-C-06-ACCEPTANCE` | `ARTIFACT` | `CONTENT_HASH` | `UNRESOLVED` | `[]` |
| `REQ-REG-C-06-SPEC-REVIEW` | `REVIEW` | `CONTENT_HASH` | `UNRESOLVED` | `[]` |

- `…-ACCEPTANCE.description` = "Current proof satisfying: Splits, bonuses,
  rights, demergers, dividends, ticker changes, and delistings are versioned
  events".
- `…-SPEC-REVIEW` scope = "C-06 under S17: Put authoritative corporate actions
  in SQL".

`evidence_refs` (2): `EV-REG-C-06-SOURCE` (`UTF8_LINE_SPAN`, register v2:77,
`2026-08-13T02:49:11Z`) and `EV-REG-C-06-SPEC-DRAFT` (`FILE_BYTES`,
`docs/specs/equity-os-s17-entity-security-master-actions.md`,
`dbb6b8600de771e9ae668208a9893394321ce67fb366c706c2d9c98985ee85aa`,
`2026-08-15T07:13:28Z`). Both recomputed: current.

`verification_command` = `{"mode": "UNRESOLVED", "commands": [],
"not_applicable_review": null}`.

## Reasoning

1. **Clause decomposition.** Seven corporate-action classes — splits, bonuses,
   rights, demergers, dividends, ticker changes, delistings — must exist "as
   versioned events" in SQL. All seven, plus the versioning predicate, appear
   verbatim in `REQ-REG-C-06-ACCEPTANCE.description`. Nothing is elided.

2. **Proof mode.** The obligation is a *representation* obligation: the schema
   and populated store must model each class as a versioned event. The proof is
   the schema/data artifact bound by content hash, so
   `ARTIFACT`/`CONTENT_HASH` is the correct classification. Note the parallel
   with C-07 on the next register line, whose clause also ends "are
   represented" and which carries the identical two-item shape — the two rows
   are consistent with each other because their clause grammar is the same, not
   because they were copied.

3. **"Authoritative" in the title is systems-of-record language.** The row title
   says "Put **authoritative** corporate actions in SQL", which could be
   misread as demanding a sign-off. It does not: the register's Authority rule
   (register v2 L23) and the row's own acceptance cell make clear this is about
   which store is the system of record, not about a human authority. The
   acceptance cell — the operative text for this inventory — contains no
   approval or test verb.

4. **Is executable proof demanded?** No test, replay, or demonstration verb
   appears. The related executable obligation in this subject area sits one row
   downstream: `C-17` requires "one real identifier-change case **tested**" and
   correspondingly carries `REQ-REG-C-17-COMMAND-PROOF` (verified). C-06
   declares `C-17` as its sole dependency, so the tested-case obligation is
   reachable from here without being duplicated onto this row. The goal's closed
   `EXPECTED_COMMAND_PROOF_COMPONENTS` (L3989-3996; validator `:2635`, asserted
   `:2649`) excludes `REG-C-06` and includes `REG-C-17` and `DISP-M-7`, matching
   my reading.

5. **Disposition cross-check.** `disposition_refs` are `M-7` and `6.3`. M-7
   (report L226-238) requires the entity/security-master decision to name, among
   other things, "corporate-action handling" and "one real test case involving
   an identifier change"; §6.3 (L363-365) rules ISIN out as the internal primary
   key. Both are separately ledgered: `DISP-M-7` carries
   `REQ-DISP-M-7-ACCEPTANCE` **and** `REQ-DISP-M-7-COMMAND-PROOF`, and
   `DISP-6-3` carries its own `ACCEPTANCE` item (both verified). So M-7's
   corporate-action-handling requirement is enumerated in the ledger on the row
   whose source text states it, and register v2's Authority rule (L23) keeps the
   narrative from adding obligations to C-06's acceptance cell.

6. **No typed approval implies no missing typed-approval evidence item.** This
   row's `required_approvals` contains only the delegated artifact approval
   (see the APPROVAL review), so there is no approval whose `TYPED_APPROVAL`
   evidence counterpart could be missing — the two inventories are mutually
   consistent.

7. **`gate_refs` = `[]`; `verification_command` = `UNRESOLVED`.** No gate names
   C-06, so no gate-side proof demand exists; `UNRESOLVED` is valid during
   initial ledger construction (goal L500-502).

No omission found.

## Verdict

verdict: CLEAN
