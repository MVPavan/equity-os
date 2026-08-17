# Inventory review — REG-C-12 — APPROVAL — r0

**Verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| Component ID | `REG-C-12` |
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

`REG-C-12.kind == "register_row"`; `scope_derivation.semantic_review` is `null`
(verified on the row). `EVIDENCE` and `APPROVAL` only; no `SCOPE` artifact.

## Live source occurrence (pinned authority)

`funda-blueprint-implementation-decision-register-v2.md:83` — `C-12`, "Set
Phase 1 analyst-economics gate", acceptance "Pre-agreed improvement is
evaluated against per-company or matched-quarter baselines; workload-normalized
metrics and total report time are reported; remaining confounds are disclosed",
dependencies `A-13, B-04`, status `Open`, priority `High`. Line digest
recomputed and equal to `text_digest`.

## Reviewed inventory, exactly as read

`required_approvals` (2 items):

| `approval_id` | `approval_type` | `required_authority` | `scope` | `status` | `actor`/`timestamp`/`matched_record_id` | `evidence_ref_ids` |
|---|---|---|---|---|---|---|
| `APR-REG-C-12-01` | `DELEGATED_ARTIFACT_APPROVAL` | `Delegated fresh Sol xhigh specification reviewer` | `C-12 under S18: Set Phase 1 analyst-economics gate` | `UNRESOLVED` | all `null` | `[]` |
| `APR-REG-C-12-02` | `ANALYST_ACCEPTANCE` | `Responsible analyst` | `C-12 under S18: Set Phase 1 analyst-economics gate` | `UNRESOLVED` | all `null` | `[]` |

`approval_records` = `[]`. `human_review_id` = `"HR-0004"`.
`security_exception_ids` = `[]`.

## Reasoning

1. **"Pre-agreed" is an authority demand in temporal form.** The clause requires
   that an improvement threshold be *agreed in advance* of evaluation. That is a
   commitment by a person, not a computable fact, so it falls squarely inside
   the goal's human-review boundary (L1001-1019) and must be a typed approval.
   `APR-REG-C-12-02` enumerates it as `ANALYST_ACCEPTANCE` with
   `required_authority = "Responsible analyst"`, the sole literal the goal's
   closed table permits for that type (goal L563-575; validator
   `REQUIRED_AUTHORITY_VOCABULARY` at `:2586`).

2. **Type selection checked, not assumed.** The nearby alternative is
   `PRODUCT_OWNER_DECISION`, since a "gate" sounds like a product-scope call.
   It does not fit: the quantity being agreed is *analyst effort improvement*,
   measured in the analyst's own workload, and the goal's product-owner literals
   are scoped to deferred-scope activation and memory adoption. Disposition G-3
   (report L75-86) and G-4 (L88-100), which are this clause's source, frame the
   judgement entirely in analyst-workload terms. `ANALYST_ACCEPTANCE` is the
   competent type.

3. **The other two conjuncts demand no authority.** "Workload-normalized metrics
   and total report time are reported" and "remaining confounds are disclosed"
   are reporting duties discharged by the artifact. Disclosure is not approval.

4. **Gate cross-check — deliberately traced, because it is the likeliest place
   an authority could hide.** `gate_refs` = `["PG-1-08"]`, whose clause is
   "analyst effort improves against matched or per-company baselines by the
   **agreed threshold**, with confounds disclosed". I read `PG-1-08`: its
   `required_approvals` is `[]`. That is consistent rather than a gap — the
   gate consumes a threshold whose agreement is C-12's obligation, and the
   program records the authority once, on the row that establishes it. The
   contrasting case in this same batch is `PG-1-09`, which *does* carry a
   `CAPACITY_COMMITMENT` because its clause performs an acceptance
   ("capacity **is accepted**") rather than referring to one made elsewhere.

5. **Dependencies.** `A-13` (success-metric contract) and `B-04` (analyst-
   economics instrumentation). Both are separate canonical rows; `REG-B-04`
   carries only the delegated approval (verified this pass), which is correct
   for an instrumentation row. Goal L188 forbids importing dependency
   authorities here, and nothing needs importing.

6. **Disposition refs.** `G-2`, `G-3`, `G-4`, `M-8`, `6.1`. I read all five in
   the disposition report; none names an approving authority — they prescribe
   measurement method and caveats. Each is separately ledgered
   (`DISP-G-2`, `DISP-G-3`, `DISP-G-4`, `DISP-M-8`, `DISP-6-1`), and each
   carries only the standard delegated approval (verified). Register v2's
   Authority rule (L23) governs precedence in any case.

7. **Fail-closed boundaries and state.** `blocked_scope = []`,
   `security_exception_ids = []`, `rejection_record = null`,
   `activation_predicate = null`; `program_disposition = REQUIRED_NOW` derived
   from `Open`/`Open`.

8. **Delegated approval well-formed.** `APR-REG-C-12-01` uses the single
   program-wide delegated-reviewer literal (goal L577-583), scoped to C-12 under
   S18, paired with `REQ-REG-C-12-SPEC-REVIEW`.

Both demanded authorities are enumerated; no omission.

## Verdict

verdict: CLEAN
