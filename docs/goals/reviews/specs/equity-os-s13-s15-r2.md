# S13–S15 Independent Review — r2

**Overall verdict: ISSUES_FOUND — r2**

- Reviewer: `gpt-5.6-sol` / `xhigh`
- CLI session UUID: `019ff90e-ec7f-77b2-86fe-0736a91c5196`
- UTC: `2026-08-13T03:03:17Z`
- Git HEAD: `ef2181d18fe036fd23e2bdffb809455b1049e2d0`
- Review round: `r2`
- Review mode: independent, read-only, no delegation, Codex CLI, memory, web, or edits
- Target `git diff --check`: **PASS**

## SHA-256 binding

| Role | Artifact | SHA-256 |
|---|---|---|
| Prior review | `docs/goals/reviews/specs/equity-os-s13-s15-r0.md` | `f232520540276eb99583f21d580ef04c46ca74006863139b8ac7b1d51b8a60d1` |
| Prior review | `docs/goals/reviews/specs/equity-os-s13-s15-r1.md` | `d66d2de7bf745900b088d71c5e983755d50a615d929575394e351f562b67293c` |
| Authority, full file | `docs/goals/equity-os-blueprint-completion.md` | `dabad7bfe3d2765a5ac9687376029d8587b4b2ac95bc03494155a974e5ddc67f` |
| Authority, requested lines | Goal lines 129–870 | `1650313cacaf9a6ae26eac637639f5783dfec967a7189751540a9c27469f3a0e` |
| Authority | `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| Authority | `docs/blueprint/funda-third-order-review-disposition-report.md` | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| Target S13 | `docs/specs/equity-os-s13-claim-schema-vocabulary-evidence.md` | `f1a60a20e24a0d2a457aa71f8d9006316ea461d237ea1faa054fc24176ba3dc4` |
| Target S14 | `docs/specs/equity-os-s14-earnings-review-workflow-rework.md` | `38325bac56b853154211392beec0d4b29fbbc4d7c0ea72c610287187d09e07f1` |
| Target S15 | `docs/specs/equity-os-s15-human-review-correction-promotion.md` | `44feb50cf0be4ef8a2a6b25204f1e383410475dcc3462b026f966037a8536c6b` |
| Target-only patch | Current Git diff for S13–S15 against bound HEAD | `5acf7f4971cedf402136a5a9de32f98b64703165e3d00a55e685d643913d315c` |

Target-only status contains modified S14 and S15; S13 matches HEAD. The repository has unrelated dirty files, excluded from this binding.

## Prior finding dispositions

| Prior finding | r2 disposition |
|---|---|
| r0 — S14 omitted rework transitions | **FIXED — no regression in the five declared `HUMAN_REVIEW` rework edges.** r2-I01 concerns the separate post-approval/post-publication correction case. |
| r0 — S14 allowed unconstrained publication targets | **FIXED — original distribution-boundary defect remains resolved.** r2-I02 concerns artifact-mode isolation, not the S01/A-01 target boundary. |
| r0 — S14-T04 did not require re-extraction | **FIXED — no regression.** Incorrect extraction output must be invalidated/superseded and replaced before downstream reruns. |
| r1-I01 — no genesis for `REGISTERED` | **FIXED — no regression.** Atomic `null → REGISTERED` genesis, registration digest, first-record rules, chain validation, and negative tests are present. |
| r1-I02 — S15 canonical digest preimages undefined | **FIXED AS WRITTEN.** Exact members, versioned domain separators, RFC 8785 canonicalization, explicit-null handling, reference ordering, independent recomputation, and negative tests now exist. r2-I02 and r2-I03 are semantic binding omissions beyond digest determinism. |

## New findings

### Critical

None.

### Important

1. **r2-I01 — The closed workflow cannot represent correction after `APPROVED` or `PUBLISHED`.**  
   File: `docs/specs/equity-os-s14-earnings-review-workflow-rework.md:55`  
   Related: S14 lines 65–71, 149, 169, 220; S15 lines 117–123, 178  
   Load-bearing: **Yes**

   Every correction/rework edge originates at `HUMAN_REVIEW`, while the graph declares no transition from `APPROVED` or `PUBLISHED` back to review or an affected step. No successor-run correction protocol supplies the missing alternative.

   This conflicts with S14-T07’s correction of previously approved bytes, S14’s requirement that invalidated approvals and publication receipts cease to be current, and S15’s accepted-claim correction/reapproval flow. The chain can therefore remain authoritatively `APPROVED` or `PUBLISHED` after its approval or receipt has been invalidated. C-10 correction semantics and fail-closed resume behavior are incomplete.

2. **r2-I02 — `ReviewDecision` cannot prove the typed production approval that S14 uses for publication.**  
   File: `docs/specs/equity-os-s15-human-review-correction-promotion.md:59`  
   Related: S15 lines 55, 86, 132–145, 183; S14 lines 118, 124–133  
   Load-bearing: **Yes**

   The canonical `ReviewDecision` omits both `approval_type` and `artifact_mode`; it binds only a bare `task_id`, without an immutable `ReviewTask` digest. S14 verifies that decision and treats a current `ACCEPT` as `ANALYST_ACCEPTANCE`, but its publication eligibility record and predicate bind neither the review task nor production mode/provenance.

   Consequently, a digest-valid `ACCEPT` from a shadow/golden task or a non-publishable claim-review scope is not mechanically distinguishable from the typed production acceptance required for `APPROVED → PUBLISHED`. This violates S15’s one-to-one approval separation and server-side shadow/golden isolation. A copied task ID or inferred mode cannot supply the missing content-bound authority.

3. **r2-I03 — Promotion does not bind the distinct current analyst acceptance on which it depends.**  
   File: `docs/specs/equity-os-s15-human-review-correction-promotion.md:76`  
   Related: lines 80, 121–123, 132, 145, 181  
   Load-bearing: **Yes**

   `PromotionRequest` calls its input “accepted” but contains no exact `ANALYST_ACCEPTANCE` decision ID or resolution digest. `PromotionDecision` binds only the request, and the receipt binds only request/promotion-decision identities. The contract also does not require the promotion adapter to resolve, independently verify, and bind the current exact-byte analyst acceptance.

   A structurally valid request can therefore assert an accepted artifact without content-bound proof of that separate authority, and revocation, staleness, wrong scope, or substitution cannot be established from the promotion closure. S15-T06 checks sequencing but lacks absent, stale, revoked, wrong-scope, and hash-mismatched analyst-acceptance cases.

### Minor

None.

## Per-spec verdicts

| Spec | Authority | Interfaces | Fail-closed | Approvals | Acceptance | Verdict |
|---|---|---|---|---|---|---|
| S13 | PASS | PASS | PASS | PASS | PASS | **CLEAN** |
| S14 | PASS | FAIL | FAIL | FAIL | FAIL | **ISSUES_FOUND** |
| S15 | PASS | FAIL | FAIL | FAIL | FAIL | **ISSUES_FOUND** |

### S13

**CLEAN — APPROVED UNDER DELEGATED GOAL AUTHORITY ONLY** for SHA-256 `f1a60a20e24a0d2a457aa71f8d9006316ea461d237ea1faa054fc24176ba3dc4`, effective only when this r2 evidence is persisted as required.

This grants no analyst, domain-expert, product, legal, regulatory, production, distribution, or other human authority. It does not satisfy final B-06 acceptance; the evidence-derived amendment gate remains binding.

### S14

**ISSUES_FOUND — not approved.**

The r1 genesis repair is correct, but r2-I01 leaves the state graph unable to represent post-approval correction, and r2-I02 leaves publication unable to prove production-mode typed acceptance.

### S15

**ISSUES_FOUND — not approved.**

The r1 canonical-byte repair is deterministic, but r2-I02 omits approval type and immutable artifact-mode binding, while r2-I03 leaves promotion unbound from the separate current analyst acceptance.

## Batch verdict

**ISSUES_FOUND**

S13 is clean under delegated goal authority only. S14 and S15 remain unapproved. Their workflow, correction, publication, approval, and promotion dependency cone remains blocked.

## Overall verdict

**ISSUES_FOUND — r2**

- S13: **CLEAN — delegated goal approval only**
- S14: **ISSUES_FOUND — not approved**
- S15: **ISSUES_FOUND — not approved**
- Batch: **not clean; do not record batch approval**