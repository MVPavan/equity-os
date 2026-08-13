# S13–S15 Independent Review — r1

- Reviewer: `gpt-5.6-sol` / `xhigh`
- CLI session UUID: `019ff901-04b6-7251-a847-34383f441ad0`
- UTC: `2026-08-13T02:48:27Z`
- Review round: `r1`
- Git HEAD: `41e1149e2e5b933dea86e2a29c623583fd5edece`

## SHA-256 binding

| Role | Artifact | SHA-256 |
|---|---|---|
| Prior review | `docs/goals/reviews/specs/equity-os-s13-s15-r0.md` | `f232520540276eb99583f21d580ef04c46ca74006863139b8ac7b1d51b8a60d1` |
| Authority | `docs/goals/equity-os-blueprint-completion.md` lines 129–870 | `dabad7bfe3d2765a5ac9687376029d8587b4b2ac95bc03494155a974e5ddc67f` |
| Authority | `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| Authority | `docs/blueprint/funda-third-order-review-disposition-report.md` | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| Target S13 | `docs/specs/equity-os-s13-claim-schema-vocabulary-evidence.md` | `f1a60a20e24a0d2a457aa71f8d9006316ea461d237ea1faa054fc24176ba3dc4` |
| Target S14 | `docs/specs/equity-os-s14-earnings-review-workflow-rework.md` | `64b88b83b7e60079cdf6a011c28585330a1e2cca583a5d0a10fd117012edaeca` |
| Target S15 | `docs/specs/equity-os-s15-human-review-correction-promotion.md` | `9223e0fcec6f43bb2d47700d4bd9962e5577ae71b152c36149ef35cc634a79cb` |
| Target-only patch | Current Git diff for S13–S15 | `a7f030316fb4f020fbf91eb7c4978b346d246a4643a62b429508c9a46eca68be` |

Target-only status contains only modified S14; S13 and S15 match HEAD. `git diff --check` passed.

## r0 finding dispositions

| r0 finding | Disposition |
|---|---|
| S14 closed state machine omitted rework transitions | **FIXED AS WRITTEN, BUT NOT REGRESSION-FREE.** All five rework edges and typed retry/block/rework targets now exist. The new transition-record regime nevertheless lacks a valid genesis for `REGISTERED`; see r1-I01. |
| S14 allowed unconstrained publication targets | **FIXED — no regression found.** Publication now consumes exact S01 boundary authority, uses three-valued eligibility, and blocks every non-private, stale, ambiguous, or unverifiable target without activating E-08. |
| S14-T04 did not require re-extraction | **FIXED — no regression found.** The body and test now invalidate/supersede the incorrect extraction output and require a new corrected extraction attempt/output before downstream reruns. |

## New findings

### Critical

None.

### Important

1. **r1-I01 — The transition chain cannot represent or prove the initial `REGISTERED` state.**  
   File: `docs/specs/equity-os-s14-earnings-review-workflow-rework.md:87`  
   Related: lines 55, 89–95, 168, 211  
   Load-bearing: **Yes**

   `RunRecord` now derives current state exclusively from the last valid chained transition. However, the closed graph has no genesis transition into `REGISTERED`, no initial transition-record form, and no explicit first-record prior-digest rule. The first declared edge is out of `REGISTERED`. Therefore a newly registered run cannot prove its current state before ingestion, and the first edge cannot prove its `from_state` from the chain. S14-T01 also omits genesis/run-creation coverage. This leaves B-01 state definition, resume, and fail-closed chain validation incomplete.

2. **r1-I02 — S15 does not define the canonical digest preimage required by S14’s approval interface.**  
   File: `docs/specs/equity-os-s15-human-review-correction-promotion.md:59`  
   Related: S15 lines 80, 133; S14 line 115  
   Load-bearing: **Yes**

   `ReviewDecision` and `PromotionDecision` name immutable content digests but do not define a versioned domain separator, canonical serialization, included fields, explicit-null treatment, or exclusion of the digest field itself. S14 now requires independent verification of the complete canonical S15 decision against that digest. The producer and consumer therefore lack a deterministic shared byte contract. Exact-byte approval, rework authorization, promotion authorization, and their acceptance tests cannot be independently verified fail-closed.

### Minor

None.

## Per-spec verdicts

| Spec | Authority | Interfaces | Fail-closed | Approvals | Acceptance | Verdict |
|---|---|---|---|---|---|---|
| S13 | PASS | PASS | PASS | PASS | PASS | **CLEAN** |
| S14 | PASS | FAIL | FAIL | PASS | FAIL | **ISSUES_FOUND** |
| S15 | PASS | FAIL | FAIL | FAIL | FAIL | **ISSUES_FOUND** |

### S13

**CLEAN — APPROVED UNDER DELEGATED GOAL AUTHORITY ONLY** for SHA-256 `f1a60a20e24a0d2a457aa71f8d9006316ea461d237ea1faa054fc24176ba3dc4`.

This approval grants no analyst, domain-expert, product, legal, regulatory, or other human authority. It does not satisfy final B-06 acceptance; the mandatory evidence-derived amendment remains binding.

### S14

**ISSUES_FOUND — not approved.** Authority ownership and both substantive r0 behavior fixes are correct, but r1-I01 prevents a complete fail-closed state/transition contract.

### S15

**ISSUES_FOUND — r0 CLEAN verdict superseded for this hash.** Authority ownership and workflow intent remain correct, but r1-I02 blocks interoperable content-bound approval and promotion verification.

## Batch verdict

**ISSUES_FOUND**

S13 is approved under delegated goal authority only. S14 and S15 remain unapproved; their workflow, review, rework, approval, and promotion dependency cone remains blocked.

## Overall verdict

**ISSUES_FOUND — r1**

- S13: **CLEAN — delegated goal approval only**
- S14: **ISSUES_FOUND — not approved**
- S15: **ISSUES_FOUND — not approved**
- Batch: **not clean; do not record batch approval**