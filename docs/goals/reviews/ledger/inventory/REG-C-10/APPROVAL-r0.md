# Inventory review — REG-C-10 — APPROVAL — r0

**Verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| Component ID | `REG-C-10` |
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

`REG-C-10.kind == "register_row"`; `scope_derivation.semantic_review` is `null`
(verified on the row). `EVIDENCE` and `APPROVAL` only; no `SCOPE` artifact.

## Live source occurrence (pinned authority)

`funda-blueprint-implementation-decision-register-v2.md:81` — `C-10`,
"Establish correction, supersession, and promotion workflow", acceptance
"Corrections create new versions; invalidated items remain auditable; canonical
promotion is separately approved; split-brain writes are prevented",
dependencies `B-03, B-14`, status `Open`, priority `High`. Line digest
recomputed and equal to `text_digest`.

## Reviewed inventory, exactly as read

`required_approvals` (2 items):

| `approval_id` | `approval_type` | `required_authority` | `scope` | `status` | `actor`/`timestamp`/`matched_record_id` | `evidence_ref_ids` |
|---|---|---|---|---|---|---|
| `APR-REG-C-10-01` | `DELEGATED_ARTIFACT_APPROVAL` | `Delegated fresh Sol xhigh specification reviewer` | `C-10 under S15: Establish correction, supersession, and promotion workflow` | `UNRESOLVED` | all `null` | `[]` |
| `APR-REG-C-10-02` | `MEMORY_PROMOTION` | `Responsible analyst` | `C-10 under S15: Establish correction, supersession, and promotion workflow` | `UNRESOLVED` | all `null` | `[]` |

`approval_records` = `[]`. `human_review_id` = `"HR-0004"`.
`security_exception_ids` = `[]`.

## Reasoning

1. **The clause states its approval demand explicitly.** "Canonical promotion is
   **separately approved**" is one of only two acceptance cells in this batch
   that uses an approval verb in the passive voice about an ongoing operation
   (the other, B-07, approves a one-time artifact). The word "separately" is
   load-bearing: the promotion sign-off must not be inferred from the
   correction workflow's own controls.

2. **The enumerated type and authority are correct.** `APR-REG-C-10-02` is
   `MEMORY_PROMOTION` with `required_authority = "Responsible analyst"`, the
   sole literal the goal's closed table permits for that type (goal L563-575;
   validator `REQUIRED_AUTHORITY_VOCABULARY` at `:2586`). `MEMORY_PROMOTION`
   rather than `ANALYST_ACCEPTANCE` is the right choice: the vocabulary carries
   a dedicated type for promotion to canonical, and the goal warns that using a
   second string or a nearby type for an authority that already has one is a
   permanent matching trap (L557-559, L546-549: an unrepresented authority "may
   not be collapsed into a nearby type"). Note both types share the same
   authority literal, so the distinction is carried by the type, and it is drawn
   correctly here.

3. **The other three conjuncts demand no authority.** "Corrections create new
   versions", "invalidated items remain auditable", and "split-brain writes are
   prevented" are workflow and storage properties adjudicated by inspection and
   test, not by a sign-off. Under the goal's human-review boundary (L1001-1019),
   an agent-establishable fact does not become an approval obligation.

4. **Candidates tested and rejected.**
   - `ANALYST_ACCEPTANCE`: would duplicate the promotion authority under a
     second type for the same real-world decision — the inferred coverage
     forbidden at goal L611-614.
   - `PRODUCT_OWNER_DECISION` / "Product owner for memory adoption": that
     literal exists in the vocabulary but attaches to *adopting* a memory
     approach (Phase 2, D-series), not to promoting an individual item inside an
     already-adopted workflow. C-10's clause is Phase 1 and item-level.
   - `SECURITY_EXCEPTION`: split-brain prevention is the control, not an
     exception to one; `security_exception_ids = []` is correct.

5. **Dependencies.** `B-03` (source-of-truth matrix) and `B-14`
   (human-feedback rework path). `REG-B-14` carries its own
   `ANALYST_ACCEPTANCE`, which stays there (goal L188: one approval never
   implies another). C-10 correctly does not restate it.

6. **Gates.** `gate_refs` = `["PG-1-07"]` — "corrections, invalidation,
   supersession, and promotion are auditable". I read it: `required_approvals`
   is `[]`. So the gate imposes no authority beyond what this row enumerates.
   The gate asks for auditability; the approval for promotion sits here.

7. **Disposition refs.** `M-5`, `M-6`, `6.6`. `DISP-M-5` carries its own
   `ANALYST_ACCEPTANCE`; `DISP-M-6` and `DISP-6-6` carry only the delegated
   approval (all verified). Under register v2's Authority rule (L23) none adds
   an approval obligation to this register row, and M-5's analyst authority is
   already ledgered where its source text sits.

8. **Delegated approval well-formed.** `APR-REG-C-10-01` uses the single
   program-wide delegated-reviewer literal (goal L577-583), scoped to C-10 under
   S15, paired with `REQ-REG-C-10-SPEC-REVIEW`.

Both demanded authorities are enumerated; no omission.

## Verdict

verdict: CLEAN
