# A-04 Output Contract v0 (Provisional)

**Record version:** 1.0.0-approved
**Status:** APPROVED — provisional section shape (v0) accepted as-is; analyst usability acceptance and product-owner scope approval RECORDED (see approval record)
**Prepared at:** 2026-08-21
**Author:** bounded implementer (drafting agent, not a decision maker)

## Purpose and boundary

This is the provisional output contract required by decision-register v2 A-04,
frozen **before** the first measured Quarter 0 baseline action. It freezes the
**sections and shape only**. It does not invent a generalized schema, does not
fill baseline content, and does not set field-level formats derived from
evidence that does not yet exist. The evidence-derived final contract is a
separate later artifact (`a-04-output-contract-final.md`) produced after the
A-03 baseline.

The analyst usability acceptance and the product-owner scope approval are now
**RECORDED** (see the approval record below). They approve the v0 section shape
as-is; they are attributable decisions, not inferences from spec approval,
register status, or any other decision.

## Frozen output sections (v0)

The v0 output for the discovery workflow consists of exactly the following
ordered sections. Their internal content is filled only during the measured
baseline; here only their presence and ordering are frozen.

| # | Section | Frozen intent (shape, not content) |
|---|---|---|
| 1 | `event_and_cutoff` | Identifies the event under review and the exact information cutoff governing what may enter the output. |
| 2 | `facts` | Observed results, each carrying its exact source location; unsupported observed facts do not enter. |
| 3 | `changes` | Period-over-period changes relative to the prior recorded state. |
| 4 | `drivers` | Analyst driver analysis explaining the changes. |
| 5 | `management_ledger` | Management commitments tracked across periods (guidance and other commitments). |
| 6 | `thesis_impact` | Effect of this event on the bootstrap thesis. |
| 7 | `observable_falsifiers` | Concrete, observable conditions that would falsify stated interpretations. |
| 8 | `open_questions` | Unresolved analytical questions, including unfilled coverage gaps. |
| 9 | `calculations` | Computed results, each carrying its calculation trace; the LLM is never the authoritative calculator. |
| 10 | `non_canonical_memory_draft` | A draft memory note explicitly marked non-canonical; it never becomes a source of truth. |
| 11 | `approval_record` | The human approval record for the output, or its explicit fail-closed absence. |

The section identifier set and order above are the frozen v0 contract shape.

## Fail-closed support rules (shape-level)

- A `facts` entry without an exact source location is not a supported fact.
- A `calculations` entry without a calculation trace is not a supported result.
- The `non_canonical_memory_draft` is never canonical and never a source.
- The `approval_record` records real deciders or explicit PENDING; it never
  infers approval from another decision.

## Approval record (v0)

| Approval | Authority | State |
|---|---|---|
| Output usability acceptance | Analyst | **APPROVED** — the analyst accepts this 11-section shape as-is. |
| Output scope approval | Product owner | **APPROVED** — the product owner approves this scope. |

- **Decider:** PavanMV (mvpavan42@gmail.com), acting as product owner and
  analyst. For this single-principal private project the evaluation-authority
  role is expressly self-assumed on the same basis already used for the analyst
  attestation (`A02-ATTEST-001`) and the A-08 approval (`A08-APPROVAL-001`).
- **Decision date:** 2026-08-21.
- **Verbatim instruction (2026-08-21):** "Approve all with defaults." — given
  in direct reply to a plain-language explanation of the four items and their
  recommended defaults.

This approves the section set and ordering only; it fills no baseline content
and does not stand in for the evidence-derived A-04 final contract.

## Record digest convention and payload

This record uses the non-self-referential SHA-256 convention stated in A-01:
UTF-8 canonical JSON with recursively sorted keys, preserved array order, no
whitespace/BOM, and every `record_digest` field excluded from its input. It
digests no source content.

```json
{"approval":{"analyst_usability_acceptance":"APPROVED","product_owner_scope_approval":"APPROVED"},"artifact_id":"A-04","baseline_content_populated":false,"contract_kind":"OUTPUT_CONTRACT_V0_PROVISIONAL","decider":"PavanMV (mvpavan42@gmail.com), product owner and analyst; for this single-principal private project the evaluation-authority role is expressly self-assumed on the same basis as A02-ATTEST-001 and A-08 (A08-APPROVAL-001)","decision_date":"2026-08-21","document_version":"1.0.0-approved","frozen_shape_only":true,"prepared_at":"2026-08-21","scope":"Provisional output section shape frozen before the first measured Q0 baseline action; no baseline content is filled; the evidence-derived final contract is A-04 final after the A-03 baseline.","sections":["event_and_cutoff","facts","changes","drivers","management_ledger","thesis_impact","observable_falsifiers","open_questions","calculations","non_canonical_memory_draft","approval_record"],"verbatim_instruction":"Approve all with defaults. (2026-08-21)"}
```

**Record digest:** `sha256:136277b6ac362af0b00d89751c7fc085f77230fe307c2035e5e79a81f42478d5`

## Authorities

- `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` — A-04 clause (sections required by the output contract).
- `docs/specs/2026-08-19-phase-0a-evidence-program.md` — A-04 primary-ownership boundary.
- Analyst (usability) and product owner (scope): decisions **APPROVED** 2026-08-21 by PavanMV (see approval record above).
