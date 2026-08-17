# Inventory review — REG-C-06 — APPROVAL — r0

**Verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| Component ID | `REG-C-06` |
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

`REG-C-06.kind == "register_row"`; `scope_derivation.semantic_review` is `null`
(verified on the row). `EVIDENCE` and `APPROVAL` only; no `SCOPE` artifact.

## Live source occurrence (pinned authority)

`funda-blueprint-implementation-decision-register-v2.md:77` — `C-06`, "Put
authoritative corporate actions in SQL", acceptance "Splits, bonuses, rights,
demergers, dividends, ticker changes, and delistings are versioned events",
dependency `C-17`, status `Open`, priority `Critical`. Line digest recomputed
and equal to `text_digest`.

## Reviewed inventory, exactly as read

`required_approvals` (1 item):

| `approval_id` | `approval_type` | `required_authority` | `scope` | `status` | `actor`/`timestamp`/`matched_record_id` | `evidence_ref_ids` |
|---|---|---|---|---|---|---|
| `APR-REG-C-06-01` | `DELEGATED_ARTIFACT_APPROVAL` | `Delegated fresh Sol xhigh specification reviewer` | `C-06 under S17: Put authoritative corporate actions in SQL` | `UNRESOLVED` | all `null` | `[]` |

`approval_records` = `[]`. `human_review_id` = `"HR-0004"`.
`security_exception_ids` = `[]`.

## Reasoning

1. **The clause states a modelling property, not a decision.** "Splits …
   delistings **are versioned events**" asserts how the store represents seven
   event classes. There is no approval verb, no named role, and no acceptance
   threshold. On its face nothing beyond the standing delegated spec review is
   demanded.

2. **The candidate omission worth testing: `DOMAIN_EXPERT_ACCEPTANCE` /
   "Entity-data authority".** This is the real question on this row, because
   C-06's sibling `C-17` — its sole dependency, in the same S17 spec and the
   same disposition family `M-7`/`6.3` — *does* carry
   `APR-REG-C-17-02` `DOMAIN_EXPERT_ACCEPTANCE` with `Entity-data authority`
   (verified by reading `REG-C-17`). Why does that authority not also land here?
   Because the clauses differ in kind: C-17's clause is "**Decide** entity/
   security master authority" — an act of deciding a data-authority question,
   which is precisely what a domain authority signs off. C-06's clause consumes
   that decision and obliges the program to represent corporate actions
   accordingly. Disposition M-7 (report L226-238) confirms the split: the
   bullets it requires — source hierarchy, conflict-resolution rule, symbol and
   listing changes, corporate-action handling, one real test case — are things
   "**the decision** must name", i.e. obligations of C-17's decision, not
   separate obligations of C-06's schema. Placing a second, independent
   domain-expert sign-off on C-06 would be exactly the inferred coverage goal
   L611-614 forbids.

3. **Other candidates rejected.**
   - `DATA_RIGHTS_APPROVAL` / `PROVIDER_AUTHORIZATION`: corporate-action data
     sourcing and rights are `A-05`'s clause, not this one.
   - `ANALYST_ACCEPTANCE`: no analyst judgement is being accepted; the
     correctness of the event model is a schema question.
   - `PRODUCT_OWNER_DECISION`: no scope or boundary decision is implicated.

4. **Dependency.** `C-17`'s own approvals remain on `C-17` (goal L188: one
   approval never implies another). C-06 correctly does not restate them.

5. **Gates.** `gate_refs` = `[]` — no phase-gate clause names `C-06` in its
   `related_register_ids`, so no gate-side authority applies.

6. **Fail-closed boundaries.** `blocked_scope = []`,
   `security_exception_ids = []`, `rejection_record = null`,
   `activation_predicate = null`, `program_disposition = REQUIRED_NOW` derived
   from `Open`/`Open`. Nothing here implicates a security exception or an
   activation authority.

7. **Delegated approval well-formed.** `APR-REG-C-06-01` carries the single
   program-wide delegated-reviewer literal (goal L577-583), scoped to C-06 under
   S17, and is the counterpart of `REQ-REG-C-06-SPEC-REVIEW`.

The empty typed-approval set is a positive determination that no business
authority is required (goal L188), and it is correct. No omission.

## Verdict

verdict: CLEAN
