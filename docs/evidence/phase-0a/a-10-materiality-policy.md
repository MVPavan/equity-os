# A-10 Materiality Policy (Draft)

**Policy version:** 0.0.0-draft-pending-approval
**Status:** DRAFT — concrete policy and validator set drafted; NOT approved; analyst policy approval and analyst validator-set approval PENDING
**Prepared at:** 2026-08-21
**Author:** bounded implementer (drafting agent, not the analyst authority)

## Purpose and boundary

This is the concrete materiality policy required by decision-register v2 A-10,
drafted before the measured Quarter 0 baseline. It combines quantitative
magnitude, thesis relevance, source conflict/uncertainty, coverage-specific
overrides, and the always-material categories, and pairs each with an expected
outcome exercised by `a-10-validator-cases.jsonl`.

No approval is recorded here. Analyst approval of the concrete policy and of the
validator set is **PENDING** and is not inferred from any other decision. A
domain/evaluation authority may only prepare or validate its expressly assigned
fixtures; that assignment and any such validation are also **PENDING**.

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

A normalized magnitude at or above the draft materiality band resolves to
`MATERIAL`; below the band it resolves to `NOT_MATERIAL` unless another
dimension elevates it. The draft band value itself is **PENDING analyst
approval** and is deliberately not fixed as an authoritative threshold here; the
validator cases use a placeholder band to exercise both the above-band and
below-band branches.

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
| Magnitude at/above draft band | `MATERIAL` |
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
(`REJECT_MALFORMED`). No case embeds real source content or a human decision;
every case carries `approval_state: PENDING`.

## Approval record — fail-closed

| Approval | Authority | State |
|---|---|---|
| Concrete materiality policy | Analyst | **PENDING** |
| Validator case set | Analyst | **PENDING** |
| Expressly assigned fixture validation | Domain/evaluation authority | **PENDING / UNASSIGNED** |

## Record digest convention and payload

Non-self-referential SHA-256 per the A-01 convention (UTF-8 canonical JSON,
recursively sorted keys, preserved array order, no whitespace/BOM, every
`record_digest` field excluded). No source content is digested.

```json
{"always_material_categories":["management_guidance","restatement","auditor_qualification","going_concern","promoter_pledge","related_party_transaction","capital_raise_or_material_dilution","major_corporate_action","management_change","regulatory_action"],"approval":{"analyst_policy_approval":"PENDING","analyst_validator_set_approval":"PENDING"},"artifact_id":"A-10","dimensions":["quantitative_magnitude","thesis_relevance","source_conflict_uncertainty","coverage_specific_override","always_material_category","confidence"],"outcome_enum":["MATERIAL","REVIEW","NOT_MATERIAL"],"policy_version":"0.0.0-draft-pending-approval","prepared_at":"2026-08-21","scope":"Concrete draft materiality policy and its validator case set, frozen in shape before the measured Q0 baseline; magnitude bands and outcomes are draft pending analyst approval.","validator_cases_ref":"docs/evidence/phase-0a/a-10-validator-cases.jsonl"}
```

**Record digest:** `sha256:e83156f3a0e63a4146d07dfe7c7115f544c3bd189f829761f6f9604fb0e1cc09`

## Authorities

- `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` — A-10 clause (policy dimensions and always-material categories).
- `docs/specs/2026-08-19-phase-0a-evidence-program.md` — A-10 primary-ownership boundary and outcome semantics.
- Analyst (policy + validator set): decision **PENDING**, not recorded here.
