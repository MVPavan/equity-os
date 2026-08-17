# Inventory review — REG-B-07 — APPROVAL — r0

**Verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| Component ID | `REG-B-07` |
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

`REG-B-07.kind == "register_row"`; `scope_derivation.semantic_review` is `null`
(verified on the row). `EVIDENCE` and `APPROVAL` only; no `SCOPE` artifact.

## Live source occurrence (pinned authority)

`funda-blueprint-implementation-decision-register-v2.md:57` — `B-07`, "Define
minimum deterministic compute", acceptance "Approved MVP list with input,
trace, code-version, missing-input, and reproducibility contracts", dependency
`A-04`, status `Open`, priority `High`. Line digest recomputed and equal to
`text_digest`.

## Reviewed inventory, exactly as read

`required_approvals` (2 items):

| `approval_id` | `approval_type` | `required_authority` | `scope` | `status` | `actor`/`timestamp`/`matched_record_id` | `evidence_ref_ids` |
|---|---|---|---|---|---|---|
| `APR-REG-B-07-01` | `DELEGATED_ARTIFACT_APPROVAL` | `Delegated fresh Sol xhigh specification reviewer` | `B-07 under S16: Define minimum deterministic compute` | `UNRESOLVED` | all `null` | `[]` |
| `APR-REG-B-07-02` | `DOMAIN_EXPERT_ACCEPTANCE` | `Calculation-domain authority` | `B-07 under S16: Define minimum deterministic compute` | `UNRESOLVED` | all `null` | `[]` |

`approval_records` = `[]`. `human_review_id` = `"HR-0004"`.
`security_exception_ids` = `[]`.

## Reasoning

1. **The clause names an approval act.** "**Approved** MVP list …" is the only
   register row in this batch whose acceptance text opens with the approval
   verb. The obligation is therefore real and must be typed, not left implicit.

2. **The enumerated authority is the competent one.** The subject matter is the
   set of deterministic financial calculations the system will compute, so the
   competent authority is the calculation domain. `APR-REG-B-07-02` is
   `DOMAIN_EXPERT_ACCEPTANCE` with `required_authority = "Calculation-domain
   authority"`, which is one of the five literals the goal's closed
   required-authority table permits for that type (goal L563-575:
   `Calculation-domain authority`, `Data-domain authority`, `Entity-data
   authority`, `Equity-research domain expert`, `Vocabulary authority`), and the
   structural validator enforces membership (`REQUIRED_AUTHORITY_VOCABULARY`,
   validator `:2586`; goal L3946-3952). A different literal would be a permanent
   matching trap under the byte-for-byte rule at goal L557-559; this one is
   correct.

3. **Is a second authority demanded?** I tested three candidates:
   - `PRODUCT_OWNER_DECISION` — the clause frames the MVP list as a technical
     definition of computable quantities, not a product-scope decision. Register
     rows that do carry a product-owner obligation are the deferral-activation
     rows, not this one.
   - `BUDGET_APPROVAL` — nothing in the clause commits spend.
   - `ANALYST_ACCEPTANCE` — the analyst accepts *outputs* (`REG-C-16`'s approved
     narrative, `DISP-G-1`, `DISP-M-5`, all of which I read and which do carry
     `ANALYST_ACCEPTANCE`), not the definition of the operator list.
   None is demanded by the clause text.

4. **Dependency.** `A-04` (freeze the first output contract) is its own
   canonical row with its own obligations. Goal L188 forbids one approval
   implying another, so A-04's authorities do not migrate onto B-07.

5. **Gates.** `gate_refs` = `[]` — no phase-gate clause names B-07 in its
   `related_register_ids`, so there is no gate-side authority to import. The
   Phase 1 gate clause that touches deterministic compute (`PG-1-06`) relates to
   `C-08` and `C-16`, not to `B-07`.

6. **Disposition refs.** `G-1` and `6.9`. G-1 is dispositioned "Accept with
   modification" and `DISP-G-1` separately carries its own
   `ANALYST_ACCEPTANCE` obligation (verified in the ledger); 6.9 is a
   definitional correction with no authority. Under register v2's Authority rule
   (L23) neither adds an approval obligation to this register row, and the one
   authority G-1 does imply is already ledgered on `DISP-G-1`.

7. **Fail-closed boundaries.** "missing-input … contracts" is a fail-closed
   requirement, but a fail-closed *behaviour* demands proof, not an approval;
   its executable proof lands on `REG-C-08` / `PG-1-04`. `blocked_scope = []`,
   `security_exception_ids = []`, `rejection_record = null`,
   `activation_predicate = null` — no exception or activation authority applies.

8. **Delegated approval well-formed.** `APR-REG-B-07-01` carries the single
   program-wide delegated-reviewer literal (goal L577-583) with a
   component-and-spec-specific scope, and is the counterpart of the
   `REQ-REG-B-07-SPEC-REVIEW` evidence item.

Both authorities the clause demands are enumerated; no omission.

## Verdict

verdict: CLEAN
