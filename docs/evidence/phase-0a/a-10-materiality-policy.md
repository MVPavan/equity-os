# A-10 Materiality Policy (Draft)

**Policy version:** 1.0.0-approved
**Status:** APPROVED — concrete policy and validator set accepted; magnitude band set to the approved value; analyst policy approval and analyst validator-set approval RECORDED
**Prepared at:** 2026-08-21
**Author:** bounded implementer (drafting agent, not the analyst authority)

## Purpose and boundary

This is the concrete materiality policy required by decision-register v2 A-10,
drafted before the measured Quarter 0 baseline. It combines quantitative
magnitude, thesis relevance, source conflict/uncertainty, coverage-specific
overrides, and the always-material categories, and pairs each with an expected
outcome exercised by `a-10-validator-cases.jsonl`.

Analyst approval of the concrete policy and of the validator set is now
**RECORDED** (see the approval record below) and the magnitude band is set to
its approved value; these are attributable decisions, not inferences from any
other decision. A domain/evaluation authority role, where used, is expressly
self-assumed by the same single principal on the basis stated in the approval
record.

## Outcome vocabulary

Every candidate claim resolves to exactly one outcome:

| Outcome | Meaning |
|---|---|
| `MATERIAL` | The claim is material and must carry full support (source location and/or calculation trace). |
| `REVIEW` | The claim cannot be auto-resolved and requires analyst review before it may enter the output as supported. |
| `NOT_MATERIAL` | The claim is below the materiality threshold and requires no elevated handling. |

## Evaluation dimensions

The policy evaluates six dimensions. Precedence: an always-material category or
a coverage-specific override forces at least `MATERIAL`; an important unresolved
conflict, a missing required input, or a low-confidence result forces at least
`REVIEW`; otherwise quantitative magnitude and thesis relevance decide.

### 1. Always-material categories → `MATERIAL`

A claim in any of the following categories resolves to `MATERIAL` regardless of
magnitude. This is the complete always-material set from the spec:

1. `management_guidance`
2. `restatement`
3. `auditor_qualification`
4. `going_concern`
5. `promoter_pledge`
6. `related_party_transaction`
7. `capital_raise_or_material_dilution`
8. `major_corporate_action`
9. `management_change`
10. `regulatory_action`

### 2. Quantitative magnitude

A magnitude at or above the approved materiality band resolves to `MATERIAL`;
below the band it resolves to `NOT_MATERIAL` unless another dimension elevates
it. The **approved magnitude band** is: **a P&L line item at or above 1% of
revenue from operations, OR a quarter-on-quarter change at or above 5%.** The
validator cases exercise both the above-band and below-band branches against
this band (the quarter-on-quarter change branch at the 5% threshold).

### 3. Thesis relevance

A claim that bears on a tracked management commitment or a stated thesis
assumption resolves to `MATERIAL` even at low magnitude. A claim that is neither
thesis-relevant nor above the magnitude band resolves to `NOT_MATERIAL`.

### 4. Source conflict / uncertainty → `REVIEW`

An important unresolved conflict between sources resolves to `REVIEW`. Both
observations and their provenance remain visible; origin (tier) never resolves
the conflict on its own.

### 5. Coverage-specific overrides → `MATERIAL`

A dimension flagged by the A-06 filing-coverage evidence as a coverage-specific
override forces `MATERIAL` even when magnitude is below band, so that
coverage-fragile measurements are not silently dropped.

### 6. Confidence → `REVIEW`

A low-confidence result, or a claim missing a required analytic input, resolves
to `REVIEW`.

## Required outcomes (summary)

| Condition | Required outcome |
|---|---|
| Any always-material category | `MATERIAL` |
| Coverage-specific override flag | `MATERIAL` |
| Magnitude at/above approved band | `MATERIAL` |
| Bears on tracked commitment / thesis assumption | `MATERIAL` |
| Important unresolved source conflict | `REVIEW` |
| Missing required input | `REVIEW` |
| Low confidence | `REVIEW` |
| Below band, not thesis-relevant, no elevating condition | `NOT_MATERIAL` |

## Validator set

The concrete validator cases live in
`docs/evidence/phase-0a/a-10-validator-cases.jsonl`. Every line is one JSON
object. The set includes one valid case per always-material category (each
requiring `MATERIAL`), above/below magnitude-band cases, thesis-relevant and
not-relevant cases, an important-unresolved-conflict case, a missing-input case,
and a low-confidence case (each `REVIEW` where required), a coverage-override
case, and minimal malformed fixtures the validator must reject
(`REJECT_MALFORMED`). No case embeds real source content or a human decision.
This set is the **approved validator set**: every case now carries
`approval_state: APPROVED` citing the decider and date in the approval record
below, and each per-case digest is recomputed accordingly.

## Approval record

| Approval | Authority | State |
|---|---|---|
| Concrete materiality policy | Analyst | **APPROVED** |
| Validator case set | Analyst | **APPROVED** |
| Magnitude band value | Analyst | **APPROVED** — set to the value in §2 |

- **Decider:** PavanMV (mvpavan42@gmail.com), acting as analyst and product
  owner. For this single-principal private project the evaluation-authority
  role is expressly self-assumed on the same basis already used for
  `A02-ATTEST-001` and the A-08 approval (`A08-APPROVAL-001`).
- **Decision date:** 2026-08-21.
- **Verbatim instruction (2026-08-21):** "Approve all with defaults." — given in
  direct reply to a plain-language explanation of the four items and their
  recommended defaults.
- **Effect:** approves the concrete policy, sets the magnitude band to the
  approved value in §2, and approves the validator case set. Every case in
  `a-10-validator-cases.jsonl` now carries `approval_state: APPROVED` with its
  per-case digest recomputed.

## Record digest convention and payload

Non-self-referential SHA-256 per the A-01 convention (UTF-8 canonical JSON,
recursively sorted keys, preserved array order, no whitespace/BOM, every
`record_digest` field excluded). No source content is digested.

```json
{"always_material_categories":["management_guidance","restatement","auditor_qualification","going_concern","promoter_pledge","related_party_transaction","capital_raise_or_material_dilution","major_corporate_action","management_change","regulatory_action"],"approval":{"analyst_policy_approval":"APPROVED","analyst_validator_set_approval":"APPROVED"},"artifact_id":"A-10","decider":"PavanMV (mvpavan42@gmail.com), product owner and analyst; for this single-principal private project the evaluation-authority role is expressly self-assumed on the same basis as A02-ATTEST-001 and A-08 (A08-APPROVAL-001)","decision_date":"2026-08-21","dimensions":["quantitative_magnitude","thesis_relevance","source_conflict_uncertainty","coverage_specific_override","always_material_category","confidence"],"magnitude_band":"a P&L line item at or above 1% of revenue from operations, OR a quarter-on-quarter change at or above 5%","outcome_enum":["MATERIAL","REVIEW","NOT_MATERIAL"],"policy_version":"1.0.0-approved","prepared_at":"2026-08-21","scope":"Concrete approved materiality policy and its validator case set; the magnitude band is set to the approved value and the validator case outcomes are the approved set. Frozen in shape before the measured Q0 baseline.","validator_cases_ref":"docs/evidence/phase-0a/a-10-validator-cases.jsonl","verbatim_instruction":"Approve all with defaults. (2026-08-21)"}
```

**Record digest:** `sha256:8792ecee0bf9a184453ac9565582794453051deb0e2ebe3d227ad776043d78fe`

## Authorities

- `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` — A-10 clause (policy dimensions and always-material categories).
- `docs/specs/2026-08-19-phase-0a-evidence-program.md` — A-10 primary-ownership boundary and outcome semantics.
- Analyst (policy + validator set + magnitude band): decision **APPROVED** 2026-08-21 by PavanMV (see approval record above).
