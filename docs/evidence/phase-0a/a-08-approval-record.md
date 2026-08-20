# A-08 Approval Record — A08-APPROVAL-001

Product-owner approval of the A-08 golden-set corpus, discharging the authority
fields of `docs/evidence/phase-0a/a-08-golden-set-charter.md` (§"The approval
record must, to discharge these fields", conditions 1–5).

## Decision

| Field | Value |
| --- | --- |
| Approval record ID | `A08-APPROVAL-001` |
| Decision | **APPROVE** |
| Decision date | 2026-08-20 |
| Decider | PavanMV (mvpavan42@gmail.com), current user/product-owner principal |
| Accountable owner role | product owner |
| Accountable individual | PavanMV (mvpavan42@gmail.com) |
| Label authority | PavanMV (mvpavan42@gmail.com) |
| Qualification/mandate basis | Product-owner mandate, personally assumed. The decider is the product-owner principal of record for this program and explicitly directed that the approval be recorded in their name. No professional credential is claimed or recorded. |
| Adopted review cadence | On corpus release; after a material observed failure; at least every 90 days (the charter's proposed cadence, adopted). |

## Adjudication (charter condition 3: per-case, not blanket)

Method: the decider was shown the enumerated 32-case plain-English disposition
table (one row per case: case_id, trap type, situation, expected outcome),
committed at
`docs/evidence/phase-0a/reviews/a-08/a08-golden-set-review-r2.md`, covering the
corpus at version `0.3.0-prepared`
(`sha256:e0d0d947e711c960346f4587fad459dc845c397caa482c5eea8334c6fcbeb306`),
and replied directly beneath it. Every case `A08-SYN-001` through `A08-SYN-032`
is adjudicated **ACCEPTED_AS_PREPARED**; no case was amended or rejected.

Verbatim decider instructions (both 2026-08-20):

1. "yeah, fix it and approve with my name."
2. "Adjudicated and approved" — in direct reply to the enumerated 32-case table.

## Review lineage

Three independent adversarial review rounds preceded this approval
(Reviewer and Implementer in separate independent sessions):

- r0: ISSUES_FOUND 3C/7I/5M — `reviews/a-08/a08-golden-set-review-r0.md`
- r1: ISSUES_FOUND 0C/2I/3M — `reviews/a-08/a08-golden-set-review-r1.md`
- r2: **CLEAN 0C/0I/0M** — `reviews/a-08/a08-golden-set-review-r2.md`

## Promotion

On this approval, all 32 case `label` blocks were promoted:
`state=APPROVED_EXPERT_LABEL`, `authority_state=APPROVED`, authority fields
filled with the values above citing `A08-APPROVAL-001`, case-set version
`0.3.0-prepared` → `1.0.0-approved`, all per-record digests recomputed.

- Promoted `a-08-golden-set.jsonl@1.0.0-approved` —
  `sha256:7ce02a93e21ff285be670e8397c31fc6e7e83661c704d4de46d4d89f83a73221`
- Mechanical validation: `check_golden_set.py` → `ALL CHECKS PASSED` (exit 0)
  against the promoted file.

## Limits

This record approves the 32 synthetic golden-set cases and their dispositions
as expert labels under the stated mandate basis, and adopts the review cadence.
It does **not** supply an analyst suitability attestation, any source-rights
decision, any legal/trademark assessment, any product-identity decision, or
any other A-09 authority; those remain separate, fail-closed gates.

## Record digest convention and payload

Same convention as A-01: `sha256:<hex>` of the UTF-8 canonical JSON payload
(recursively sorted keys, compact separators, no digest field in the input).

```json
{"accountable_individual_name":"PavanMV (mvpavan42@gmail.com)","accountable_owner_role":"product owner","adjudicated_artifacts":{"a-08-golden-set-charter.md@pre-approval":"sha256:6d44c9160feca9d489c1b46414a1ab2a711b5757a047c83b982206f9d39bb0f2","a-08-golden-set.jsonl@0.3.0-prepared":"sha256:e0d0d947e711c960346f4587fad459dc845c397caa482c5eea8334c6fcbeb306"},"adjudicated_case_ids":["A08-SYN-001","A08-SYN-002","A08-SYN-003","A08-SYN-004","A08-SYN-005","A08-SYN-006","A08-SYN-007","A08-SYN-008","A08-SYN-009","A08-SYN-010","A08-SYN-011","A08-SYN-012","A08-SYN-013","A08-SYN-014","A08-SYN-015","A08-SYN-016","A08-SYN-017","A08-SYN-018","A08-SYN-019","A08-SYN-020","A08-SYN-021","A08-SYN-022","A08-SYN-023","A08-SYN-024","A08-SYN-025","A08-SYN-026","A08-SYN-027","A08-SYN-028","A08-SYN-029","A08-SYN-030","A08-SYN-031","A08-SYN-032"],"adjudication_method":"individual review of the enumerated 32-case plain-English disposition table (docs/evidence/phase-0a/reviews/a-08/a08-golden-set-review-r2.md); every case adjudicated ACCEPTED_AS_PREPARED","adopted_review_cadence":"on corpus release; after a material observed failure; at least every 90 days","approval_record_id":"A08-APPROVAL-001","artifact_id":"A-08","decider":"PavanMV (mvpavan42@gmail.com), current user/product-owner principal","decision":"APPROVE","decision_date":"2026-08-20","label_authority_name":"PavanMV (mvpavan42@gmail.com)","label_authority_qualification_basis":"product-owner mandate, personally assumed; no professional credential claimed","promoted_artifact":{"a-08-golden-set.jsonl@1.0.0-approved":"sha256:7ce02a93e21ff285be670e8397c31fc6e7e83661c704d4de46d4d89f83a73221"},"scope":"Approves the 32 synthetic golden-set cases and their dispositions as expert labels under the stated mandate basis. Does not supply analyst suitability attestation, source rights, legal/trademark assessment, product-identity decision, or any A-09 authority.","verbatim_instructions":["yeah, fix it and approve with my name. (2026-08-20)","Adjudicated and approved (2026-08-20, in direct reply to the enumerated 32-case table)"]}
```

**Record digest:** `sha256:8ea379e801eff8b46dea08a7535f9407894f19c91d46fb22dbfe34fe53fa2ee9`
