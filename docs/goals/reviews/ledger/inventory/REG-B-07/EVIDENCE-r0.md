# Inventory review — REG-B-07 — EVIDENCE — r0

**Verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| Component ID | `REG-B-07` |
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

`REG-B-07.kind == "register_row"` and its `scope_derivation.semantic_review` is
`null` (verified on the row; goal L208-211,
`validate_ledger_preimplementation.py:200-204`). Two applicable reviews only:
`EVIDENCE` and `APPROVAL`. No `SCOPE` artifact.

## Live source occurrence (pinned authority)

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md:57`,
section **B. Phase 0.5**, register ID `B-07`, status `Open`, priority `High`:

> | B-07 | High | Define minimum deterministic compute | Approved MVP list with input, trace, code-version, missing-input, and reproducibility contracts | A-04 | Open |

Recomputed `UTF8_LINE_SPAN` digest of line 57:
`f70333be9da6edfad3ae847c16670f538615b16fd0d343511174195854f6b58c` — equals
`text_digest` and `EV-REG-B-07-SOURCE.content_sha256`. `required_acceptance_text`
is byte-identical to the acceptance cell.

## Reviewed inventory, exactly as read

`required_evidence` (3 items):

| `evidence_id` | `evidence_type` | `proof_mode` | `status` | `approval_ids` |
|---|---|---|---|---|
| `REQ-REG-B-07-ACCEPTANCE` | `ARTIFACT` | `CONTENT_HASH` | `UNRESOLVED` | `[]` |
| `REQ-REG-B-07-SPEC-REVIEW` | `REVIEW` | `CONTENT_HASH` | `UNRESOLVED` | `[]` |
| `REQ-REG-B-07-DOMAIN_EXPERT_ACCEPTANCE` | `DOMAIN` | `TYPED_APPROVAL` | `UNRESOLVED` | `["APR-REG-B-07-02"]` |

- `…-ACCEPTANCE.description` = "Current proof satisfying: Approved MVP list with
  input, trace, code-version, missing-input, and reproducibility contracts".
- `…-SPEC-REVIEW.description` = "Persisted clean fresh Sol xhigh review of the
  current specification bytes", scope "B-07 under S16: Define minimum
  deterministic compute".
- `…-DOMAIN_EXPERT_ACCEPTANCE.description` = "Current DOMAIN_EXPERT_ACCEPTANCE
  evidence from Calculation-domain authority".

All three `UNRESOLVED` with empty `evidence_ref_ids`.

`evidence_refs` (2): `EV-REG-B-07-SOURCE` (`UTF8_LINE_SPAN`, register v2:57,
`2026-08-13T02:49:11Z`) and `EV-REG-B-07-SPEC-DRAFT` (`FILE_BYTES`,
`docs/specs/equity-os-s16-minimum-deterministic-compute.md`,
`b3d436e95b874445cb9000a7ee89c69c5a9bcdee03433865b83280e09842b3d6`,
`2026-08-15T07:13:28Z`). Both recomputed against current bytes: current.

`verification_command` = `{"mode": "UNRESOLVED", "commands": [],
"not_applicable_review": null}`.

## Reasoning

1. **Clause decomposition.** B-07 has two distinct proof demands, not one.
   (a) An **approved** MVP list of deterministic calculations — an act of
   acceptance by a competent authority. (b) Five **contracts** the list must
   carry: input, trace, code-version, missing-input, and reproducibility.

2. **The approval half is typed, not collapsed into the artifact.** Demand (a)
   is enumerated as `REQ-REG-B-07-DOMAIN_EXPERT_ACCEPTANCE`, `DOMAIN` /
   `TYPED_APPROVAL`, naming `APR-REG-B-07-02` in `approval_ids`. This is exactly
   what the goal requires: domain evidence "always uses `TYPED_APPROVAL` and the
   typed approval/human-review path, never a fabricated shell command"
   (L487-490), and a `TYPED_APPROVAL` item must name component-local
   requirements (L484-487). `APR-REG-B-07-02` is component-local — verified in
   this row's `required_approvals`. Had the "Approved" been folded into the
   `ARTIFACT` item alone, that would have been an omission; it is not.

3. **The contracts half.** Demand (b) is carried verbatim in
   `REQ-REG-B-07-ACCEPTANCE.description`. All five named contracts appear;
   none is dropped. `ARTIFACT`/`CONTENT_HASH` is the correct class — the MVP
   list with its contracts is a document whose bytes are the proof.

4. **Does "reproducibility contracts" demand executable proof here?** This is
   the one substantive call on this row. It does not, because B-07 is the
   *definition* row: it obliges the program to state the contracts, while the
   *satisfaction* of those contracts is C-08 ("… pass tests and fail closed")
   and C-16 ("Exact-class operators replay exactly …"), both of which do carry
   `COMMAND_RESULT` items — I read both rows and confirmed
   `REQ-REG-C-08-COMMAND-PROOF` and `REQ-REG-C-16-COMMAND-PROOF` exist. C-08
   declares `B-07` as a dependency, so the definition→execution chain is intact.
   The goal's closed set `EXPECTED_COMMAND_PROOF_COMPONENTS` (L3989-3996;
   validator `:2635`, asserted `:2649`) excludes `REG-B-07` and includes
   `REG-C-08` and `REG-C-16`, which is the same allocation I reached
   independently.

5. **Disposition cross-check.** `disposition_refs` are `G-1` and `6.9`. G-1
   (report L47-59) splits reproducibility into deterministic-calculation replay,
   evidence-package reconstruction, and immutable narrative bytes; 6.9 (L396-398)
   says bit-exactness applies only to operators designed for exact replay and
   that floating-point/optimization/stochastic operators need declared
   tolerances, pinned environments, and stored seeds. Both are the *content* the
   reproducibility contract must express, and both are separately ledgered:
   `DISP-G-1` carries `ACCEPTANCE` + `ANALYST_ACCEPTANCE` + `COMMAND-PROOF`, and
   `DISP-6-9` carries `ACCEPTANCE` + `COMMAND-PROOF` (both verified in the
   ledger). Under register v2's Authority rule (L23) the narrative does not add
   obligations to this register row, and nothing is lost program-wide.

6. **`verification_command` = `UNRESOLVED`** is valid during initial ledger
   construction (goal L500-502) and is not an inventory gap.

7. **`gate_refs` = `[]`.** B-07 is not named by any phase-gate clause, so there
   is no gate-side proof demand to reconcile. (Its downstream C-08 is named by
   `PG-1-04` and `PG-1-06`, which is where the gate-level proof lands.)

No omission found; the three enumerated items exactly cover the clause's two
demands plus the standing spec-review obligation.

## Verdict

verdict: CLEAN
