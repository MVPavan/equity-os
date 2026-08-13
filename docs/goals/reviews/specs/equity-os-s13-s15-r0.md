# S13–S15 Independent Review — r0

- Reviewer: `gpt-5.6-sol` / `xhigh`
- UTC: `2026-08-13T02:35:26Z`
- Committed baseline: `fa4cd53605914bf10376ad9b6264971711ff1f07`
- Review round: `r0`

## SHA-256 binding

| Role | Artifact | SHA-256 |
|---|---|---|
| Authority | `docs/goals/equity-os-blueprint-completion.md` lines 129–870 | `dabad7bfe3d2765a5ac9687376029d8587b4b2ac95bc03494155a974e5ddc67f` |
| Authority | `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| Authority | `docs/blueprint/funda-third-order-review-disposition-report.md` | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| Target S13 | `docs/specs/equity-os-s13-claim-schema-vocabulary-evidence.md` | `f1a60a20e24a0d2a457aa71f8d9006316ea461d237ea1faa054fc24176ba3dc4` |
| Target S14 | `docs/specs/equity-os-s14-earnings-review-workflow-rework.md` | `389ff11dc693c38ae1cf6dc48a84d88b24e29a7050b9eacd985fecf55b2c3ea6` |
| Target S15 | `docs/specs/equity-os-s15-human-review-correction-promotion.md` | `9223e0fcec6f43bb2d47700d4bd9962e5577ae71b152c36149ef35cc634a79cb` |

## Per-spec verdicts

### S13 — CLEAN

Authority ownership, title, path, register text, priorities, statuses, dependencies, and disposition references exactly cover B-06, B-12, C-04, G-5, M-3, and 6.2. The spec correctly remains provisional, preserves the mandatory evidence-derived B-06 amendment gate, declares active-only scope, supplies fail-closed validation and registry invariants, uses distinct delegated/domain approvals, and provides adequate acceptance coverage.

`CLEAN` is delegated goal approval for the exact reviewed hash, effective when persisted with the required review evidence. It is not personal user approval or non-delegated human authority.

### S14 — ISSUES_FOUND

The owned register rows and disposition references are accurate, and the active-only classification, dependency inventory, immutable-output/rework principles, typed analyst approvals, scale-trigger guard, and no-mandatory-amendment classification are correct. The findings below prevent delegated approval.

### S15 — CLEAN

Authority ownership, register text, statuses, dependencies, and disposition coverage exactly cover C-05, C-10, M-5, M-6, and 6.6. Review decisions, correction/supersession records, approval separation, atomic promotion receipts, seeded-error isolation, and fail-closed guards are coherent. The S19/D-03 boundary is explicitly non-activating and blocks promotion until separately activated authority and an authoritative transaction exist.

`CLEAN` is delegated goal approval for the exact reviewed hash, effective when persisted with the required review evidence. It is not personal user approval or non-delegated human authority.

## Critical findings

None.

## Important findings

1. **S14’s supposedly closed state machine does not declare its rework transitions.**
   File: `docs/specs/equity-os-s14-earnings-review-workflow-rework.md:55`
   Load-bearing: **Yes**

   The contract declares a fixed linear path and says no other transition is legal, but `REJECT` and `EDIT` subsequently re-enter an arbitrary earliest affected step without defining transitions from `HUMAN_REVIEW` to `INGESTED`, `EXTRACTED`, `RECONCILED`, `CALCULATED`, or `DRAFTED`. It likewise lacks a typed transition record carrying the blocked/rework resume target. Consequently, B-01’s required state definitions and allowed transitions are not exact, M-5’s correction transitions are underdefined, and S14-T01 cannot exhaustively test the graph. See also lines 57–66, 70–76, and 100–113.

2. **S14 permits an unconstrained publication target using only analyst acceptance.**
   File: `docs/specs/equity-os-s14-earnings-review-workflow-rework.md:94`
   Load-bearing: **Yes**

   `PublicationReceipt` accepts a free publication target and may be created from `APPROVED`; the only declared update approval is `ANALYST_ACCEPTANCE` at lines 128–136. The contract does not constrain publication to the current A-01/S01 internal boundary or require the appropriate typed production/distribution authority when a target crosses that boundary. The opening disclaimer does not mechanically enforce the restriction. This conflicts with the deferred external-use gate at `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md:116` and the non-delegation boundary at `docs/goals/equity-os-blueprint-completion.md:838`. S14 must consume the active distribution boundary and fail closed for every target outside it.

3. **The rejected-extraction acceptance test does not require re-extraction.**
   File: `docs/specs/equity-os-s14-earnings-review-workflow-rework.md:170`
   Load-bearing: **Yes**

   S14-T04 requires downstream reconciliation, calculation, claim, draft, and review work to rerun, but never requires the incorrect extraction output to be invalidated/superseded or a corrected extraction output to be produced. That omission permits the test to pass without proving M-5’s explicit re-extraction path or the body’s earliest-incorrect-step rule at lines 102–108.

## Minor findings

None.

## Batch verdict

**ISSUES_FOUND**

S13 and S15 are mutually consistent and clean. Primary ownership, source status, dependencies, disposition coverage, and active-only classification are correct across all three targets. S14’s closed-transition, publication-authority, and verification gaps block batch consistency and the S14-dependent workflow/rework cone.

## Overall verdict

**ISSUES_FOUND — r0**

- S13: **CLEAN — delegated goal approval only**
- S14: **ISSUES_FOUND — not approved**
- S15: **CLEAN — delegated goal approval only**
- Batch: **not clean; do not record batch approval**