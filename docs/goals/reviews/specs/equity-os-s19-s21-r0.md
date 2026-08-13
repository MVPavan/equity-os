# r0 verdict: ISSUES_FOUND — delegated approval withheld

- **Reviewer:** `gpt-5.6-sol/xhigh`
- **Review round:** `r0`
- **UTC time:** `2026-08-13T02:35:09Z`
- **Committed baseline:** `fa4cd53605914bf10376ad9b6264971711ff1f07`
- **Binding:** Reviewed files have no working-tree differences from that baseline.

## SHA-256 binding

| Role | Artifact | SHA-256 |
|---|---|---|
| Authority | `docs/goals/equity-os-blueprint-completion.md` | `dabad7bfe3d2765a5ac9687376029d8587b4b2ac95bc03494155a974e5ddc67f` |
| Authority | `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| Authority | `docs/blueprint/funda-third-order-review-disposition-report.md` | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| Target S19 | `docs/specs/equity-os-s19-memory-store-promotion.md` | `dd5e20f95e790398f21c49af7e75e4f64ae7001578f841577d8551806a05273f` |
| Target S20 | `docs/specs/equity-os-s20-memory-benchmark-gbrain.md` | `6c6969a5922bbdb75b229650554103b3a4aac5c153f79e15ca89e02f2b08f7b5` |
| Target S21 | `docs/specs/equity-os-s21-conditional-model-grade-compute.md` | `df8ed8d10c933f0e1e8ce81988d7f16ee97ff2b618ecec6ff377f552f81ebd5a` |

## Per-spec verdicts

| Spec | Verdict | Authority/disposition assessment |
|---|---|---|
| S19 | **ISSUES_FOUND** | D-01/D-03 ownership, source text, current statuses, R-1/6.4 scope, and mixed activation are correctly represented. Deletion and D-03 activation remain load-bearing gaps. |
| S20 | **ISSUES_FOUND** | D-02/D-04/D-05 ownership, source text, dormant-only classification, benchmark evidence, and R-1/6.4 disposition are substantially complete. Dependency and controlled-status handling are not clean. |
| S21 | **ISSUES_FOUND** | E-01 ownership, Deferred status, C-08 dependency, lack of direct disposition ownership, interfaces, fail-closed calculations, and amendment guard are substantially aligned. Activation and method-approval contracts are incomplete. |

## Critical findings

None.

## Important findings

1. **S19 deletion can change effective memory state without a defined promotion, compare-and-swap, or typed-approval transition.**
   **Location:** [docs/specs/equity-os-s19-memory-store-promotion.md:81](/data/codes/equity-os/docs/specs/equity-os-s19-memory-store-promotion.md:81)
   **Load-bearing:** `yes`

   `delete` ambiguously “creates a logical tombstone or withdrawal revision,” but does not say whether that revision remains staged or immediately changes canonical visibility. Unlike `PromotionRequest`, it carries no expected-prior pointer, resolution digest, or approval identifier. The tests prove tombstone/export preservation but not approval rejection, stale-pointer handling, canonical invisibility before promotion, concurrency, or atomic retrieval behavior. An adapter could therefore satisfy the written interface while bypassing the canonical promotion boundary. Define the exact deletion state transition, authorization type, compare-and-swap behavior, and corresponding mechanical tests.

2. **S19 does not freeze an exact D-03 predicate or mechanically enforce D-01 at the activation transition.**
   **Location:** [docs/specs/equity-os-s19-memory-store-promotion.md:112](/data/codes/equity-os/docs/specs/equity-os-s19-memory-store-promotion.md:112)
   **Load-bearing:** `yes`

   The predicate ID is illustrative—“such as”—rather than a stable contract, and its expression tests only `/memory_promotion/atomic_transaction_required`. D-01 is an exact register dependency, but appears only later as a prose blocker at [line 150](/data/codes/equity-os/docs/specs/equity-os-s19-memory-store-promotion.md:150). Consequently, the specified predicate and human resolution could authorize the Deferred-to-active transition before D-01 acceptance. Freeze the predicate identity and encode a mechanically verifiable D-01 dependency condition supported by the goal’s closed predicate schema.

3. **S20 introduces an unauthorized D-01 readiness dependency for D-04.**
   **Location:** [docs/specs/equity-os-s20-memory-benchmark-gbrain.md:174](/data/codes/equity-os/docs/specs/equity-os-s20-memory-benchmark-gbrain.md:174)
   **Load-bearing:** `yes`

   D-04’s authoritative register dependency is `—`, and S20 itself confirms that at [line 216](/data/codes/equity-os/docs/specs/equity-os-s20-memory-benchmark-gbrain.md:216). Requiring “S19 D-01 readiness” as D-04 activation evidence creates a new blocking edge without authority reconciliation. Remove that condition or formally amend and reconcile the register dependency.

4. **S20 does not map benchmark/adoption outcomes or reevaluation triggers onto the goal’s controlled source-status transitions.**
   **Location:** [docs/specs/equity-os-s20-memory-benchmark-gbrain.md:140](/data/codes/equity-os/docs/specs/equity-os-s20-memory-benchmark-gbrain.md:140)
   **Load-bearing:** `yes`

   The spec defines three D-05 outcomes and future trigger-driven reevaluation, but never states:

   - whether `ADOPT_CURRENT_SCALE` and `DO_NOT_ADOPT_CURRENT_SCALE` both complete D-05 as `Accepted`;
   - that `NO_DECISION_INSUFFICIENT_EVIDENCE` cannot support `Accepted` or `VERIFIED`;
   - that a later D-02 rerun or D-05 reconsideration after acceptance requires the goal-mandated `REOPEN_ACCEPTED` human resolution and source reconciliation;
   - whether the exact-scope `PRODUCT_OWNER_DECISION` is required for both conclusive decisions, rather than only positive adoption.

   A crossed-trigger test currently opens consideration without validating the required controlled-state transition ([line 209](/data/codes/equity-os/docs/specs/equity-os-s20-memory-benchmark-gbrain.md:209)). This leaves the central R-1 reevaluation path non-executable.

5. **S21’s C-08 acceptance predicate cannot be implemented using the goal’s declared `REGISTER_STATUS` metric semantics.**
   **Location:** [docs/specs/equity-os-s21-conditional-model-grade-compute.md:120](/data/codes/equity-os/docs/specs/equity-os-s21-conditional-model-grade-compute.md:120)
   **Load-bearing:** `yes`

   The predicate ID is again illustrative—“such as”—and the first condition requires C-08 to be exactly `Accepted`, “derived from live register Status.” The goal’s closed `REGISTER_STATUS` metric is only a boolean that becomes true for any `Open`, `In progress`, or `Accepted` row ([goal line 289](/data/codes/equity-os/docs/goals/equity-os-blueprint-completion.md:289)); it cannot distinguish `Accepted`. Freeze the predicate identity and either bind exact acceptance through supported content-bound evidence or reconcile the goal predicate schema.

6. **S21 lacks typed competent approval for the financial method definitions that control DCF, SOTP, WACC, and accepted tie-out adjustments.**
   **Location:** [docs/specs/equity-os-s21-conditional-model-grade-compute.md:64](/data/codes/equity-os/docs/specs/equity-os-s21-conditional-model-grade-compute.md:64)
   **Load-bearing:** `yes`

   `definition_ref` governs formula/method behavior, and the trace records approvals only for assumptions and sector definitions. The typed gate table likewise requires `DOMAIN_EXPERT_ACCEPTANCE` only for sector definitions ([line 137](/data/codes/equity-os/docs/specs/equity-os-s21-conditional-model-grade-compute.md:137)). Thus a reproducible but financially incorrect DCF/SOTP/WACC method—or a known tie-out adjustment—can pass without exact-version competent acceptance. Mechanical reproducibility proves repeatability, not methodological validity. Add an exact-scope typed approval requirement and rejection tests for unapproved, expired, or wrong-version calculation-method definitions and accepted adjustments.

## Minor findings

None.

## Batch verdict

**ISSUES_FOUND.** Ownership, quoted authority, source statuses, primary dependencies, disposition allocation, dormancy boundaries, evidence expectations, and delegated-versus-human authority separation are mostly consistent. The six Important findings are load-bearing and block the affected components and dependent cones.

## Overall verdict

**NOT CLEAN. S19, S20, and S21 are not approved under delegated goal authority at r0.**

A future `CLEAN` verdict would constitute delegated goal approval of the reviewed specifications only. It would not constitute or imply personal user approval or any non-delegated human, domain, analyst, legal, provider, budget, production, or external authority.