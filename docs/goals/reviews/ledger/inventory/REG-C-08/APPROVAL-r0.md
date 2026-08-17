# Inventory review — REG-C-08 — APPROVAL — r0

**Verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| Component ID | `REG-C-08` |
| Review type | `APPROVAL` |
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
(verified on the row). `EVIDENCE` and `APPROVAL` only; no `SCOPE` artifact.

## Live source occurrence (pinned authority)

`funda-blueprint-implementation-decision-register-v2.md:79` — `C-08`,
"Implement minimum deterministic calculations", acceptance "Growth, margins,
cash conversion, leverage, dilution/share count, guidance comparison, and
reconciliation traces pass tests and fail closed", dependency `B-07`, status
`Open`, priority `High`. Line digest recomputed and equal to `text_digest`.

## Reviewed inventory, exactly as read

`required_approvals` (1 item):

| `approval_id` | `approval_type` | `required_authority` | `scope` | `status` | `actor`/`timestamp`/`matched_record_id` | `evidence_ref_ids` |
|---|---|---|---|---|---|---|
| `APR-REG-C-08-01` | `DELEGATED_ARTIFACT_APPROVAL` | `Delegated fresh Sol xhigh specification reviewer` | `C-08 under S16: Implement minimum deterministic calculations` | `UNRESOLVED` | all `null` | `[]` |

`approval_records` = `[]`. `human_review_id` = `"HR-0004"`.
`security_exception_ids` = `[]`.

## Reasoning

1. **The clause is machine-adjudicated, which is why it carries no business
   authority.** "… pass tests and fail closed" is settled by executing the
   tests, not by anyone's judgement. The goal draws exactly this line: an agent
   may establish a fact that is mechanically establishable, and the human-review
   boundary (L1001-1019) is reserved for "the exact fact or authority an agent
   cannot establish". C-08's predicate is the former.

2. **The `DOMAIN_EXPERT_ACCEPTANCE` question — the one real call here.** The
   calculation-domain authority *is* required in this subject area, but on
   `B-07`, whose clause is "**Approved** MVP list …" and which carries
   `APR-REG-B-07-02` `DOMAIN_EXPERT_ACCEPTANCE` / "Calculation-domain
   authority" (verified by reading `REG-B-07` this pass). C-08 declares `B-07`
   as its sole dependency and implements the list that approval covers. Adding
   a second domain-expert requirement here would assert a second real-world
   decision that the register does not describe, contrary to goal L611-614.
   The approval is placed where the deciding happens; the implementation row
   proves conformance by test.

3. **The `ANALYST_ACCEPTANCE` question, traced through the gate.** `gate_refs`
   = `["PG-1-04", "PG-1-06"]`. `PG-1-04` carries **no** approvals. `PG-1-06`
   *does* carry `ANALYST_ACCEPTANCE` / "Responsible analyst" — but its clause is
   conjunctive ("deterministic calculations satisfy their declared
   exact/tolerance/seeded replay class **and** the approved narrative is bound
   to an artifact hash") with `related_register_ids = ["C-08", "C-16"]`. The
   analyst-acceptance arm belongs to the approved-narrative half, i.e. `C-16`,
   and `REG-C-16` independently carries its own `ANALYST_ACCEPTANCE` (verified).
   So the gate's authority is accounted for on the row whose clause demands it,
   and C-08's half of the gate is the test-passing half. No omission on C-08.

4. **Other candidates rejected.**
   - `PRODUCT_OWNER_DECISION`: which calculations are in the MVP is B-07's
     decision, already approved there.
   - `BUDGET_APPROVAL`, `CAPACITY_COMMITMENT`: no spend or staffing commitment
     in the clause.
   - `SECURITY_EXCEPTION`: "fail closed" is the safe default the clause
     requires, not an exception granted against a control;
     `security_exception_ids = []` is correct.

5. **Disposition refs.** `G-1` and `6.9`. `DISP-G-1` carries its own
   `ANALYST_ACCEPTANCE` (verified); `DISP-6-9` carries only the delegated
   approval. Under register v2's Authority rule (L23) neither adds an approval
   obligation to this register row, and G-1's analyst authority is already
   ledgered on `DISP-G-1`.

6. **Fail-closed boundaries and state.** `blocked_scope = []`,
   `rejection_record = null`, `activation_predicate = null`,
   `program_disposition = REQUIRED_NOW` derived from `Open`/`Open`. No
   activation or exception authority applies.

7. **Delegated approval well-formed.** `APR-REG-C-08-01` uses the single
   program-wide delegated-reviewer literal (goal L577-583), scoped to C-08 under
   S16, paired with `REQ-REG-C-08-SPEC-REVIEW`.

The empty typed-approval set is a correct positive determination (goal L188).
No omission.

## Verdict

verdict: CLEAN
