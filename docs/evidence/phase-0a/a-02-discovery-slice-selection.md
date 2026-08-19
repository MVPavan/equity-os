# A-02 Discovery Slice Selection

**Record version:** 1.0.0
**Status:** BLOCKED — product-owner selection is recorded, but no current identifiable analyst-suitability attestation has been found
**Recorded at:** 2026-08-19T20:28:25Z
**Author:** bounded implementer (recording agent, not the decision maker)

## Binding approval event

- **Event reference:** `eqos-3ps` notes, `BINDING USER DECISION 2026-08-19`, obtained with `bd show eqos-3ps --json`.
- **Timestamp:** `2026-08-19` only. The event has no recorded time-of-day; none is inferred.
- **Principal:** current user/product-owner principal provided by the handoff. No personal identity is recorded or inferred.
- **Decision text (verbatim scope):** `A-02 Infosys issuer Q1-Q4 FY25 mapped to program Q0-Q3`.
- **Presented scope:** the same approval binds S1 A-01/A-02 in the five-flat-stage Phase 0A evidence program and states that the separate analyst-suitability attestation remains required and fail-closed.

## Selected vertical slice

| Program quarter | Issuer quarter | Operating role |
|---|---|---|
| Q0 | Infosys Q1 FY25 | Manual baseline and bootstrap thesis only. |
| Q1 | Infosys Q2 FY25 | Assisted incremental update. |
| Q2 | Infosys Q3 FY25 | Assisted incremental update. |
| Q3 | Infosys Q4 FY25 | Assisted incremental update. |

The selected discovery company is **Infosys Ltd (INFY)**. The mapping follows the non-authoritative shortlist's workflow assumption and the binding product-owner selection. It does not authorize Phase 0.5 product implementation.

## Shortlist evidence retained by epistemic class

### Facts

- The shortlist records issuer-hosted financial-results-and-auditors'-reports PDFs for all four FY25 quarters: Q1 (July 18, 2024; quarter ended June 30), Q2 (October 17, 2024; quarter and half-year ended September 30), Q3 (January 16, 2025; quarter and nine months ended December 31), and Q4 (April 17, 2025; quarter and year ended March 31).
- Q1 management guidance was 3%–4% constant-currency revenue growth and 20%–22% operating margin; Q2 changed revenue guidance to 3.75%–4.5% while retaining margin guidance; Q3 changed revenue guidance to 4.5%–5% while retaining margin guidance; Q4 reported FY25 constant-currency growth of 4.2% and FY26 guidance of 0%–3% revenue growth and 20%–22% operating margin. The inventory identifies the recorded official-source references for this cross-period commitment chain.
- The shortlist records official NSE/BSE financial-results discovery channels, but not a direct per-quarter XBRL file link.

### Inferences

- Infosys was ranked as the preferred discovery candidate because it has the cleanest repeatable manual discovery path and clearest guidance trail.
- It is the strongest candidate for a manual baseline because the recorded materials have consistent source naming, explicit document dates, statutory result PDFs, management transcripts, and a guidance-versus-actual trail.

### Data gaps

- Structured-data availability for the exact INFY FY25 quarters, guidance field coverage, exchange-file retention, and a stable direct XBRL file link were not established.
- Public access does not establish permission for automation, caching, retention, derived outputs, or redistribution; rights remain a separate fail-closed decision.

## Analyst-suitability fail-closed gate

**A-02 status: BLOCKED. Stage S1 (`eqos-3ps.1`) status: BLOCKED for acceptance.** No current, identifiable analyst-suitability attestation for this exact Infosys Q1–Q4 FY25 / program Q0–Q3 slice was found in the bounded authority evidence.

The missing decision record must supply all of:

1. Attesting analyst's identifiable name and role.
2. Attestation timestamp and current-validity basis.
3. Exact scope: Infosys Ltd (INFY), issuer Q1–Q4 FY25, and program Q0 manual baseline/bootstrap plus Q1–Q3 assisted updates.
4. Suitability conclusion, including competence/authority for the intended private/internal workflow.
5. Attributable evidence reference and any limits, conflicts, or required supervision.

Until that record is supplied and scope-matched, this artifact is not accepted and must not be used to claim A-02 or S1 completion.

## Record digest convention and payload

This record uses the non-self-referential SHA-256 convention stated in A-01: UTF-8 canonical JSON with recursively sorted keys, preserved array order, no whitespace/BOM, and every `record_digest` field excluded from its input. It does not digest or fetch source content.

```json
{"artifact_id":"A-02","authority_event_ref":"eqos-3ps notes:BINDING USER DECISION 2026-08-19","company":"Infosys Ltd (INFY)","document_version":"1.0.0","issuer_to_program_mapping":["Q1 FY25->Q0 manual baseline/bootstrap thesis","Q2 FY25->Q1 assisted incremental update","Q3 FY25->Q2 assisted incremental update","Q4 FY25->Q3 assisted incremental update"],"recorded_at":"2026-08-19T20:28:25Z","status":"BLOCKED","suitability_attestation":"MISSING: current identifiable, scope-matched analyst attestation","scope":"Infosys issuer Q1-Q4 FY25 selected for program Q0-Q3; private/internal boundary only."}
```

**Record digest:** `sha256:f48d3b9303ce8e16a5f45a751519899096d5d4d10bba33ae843309d5c614bce3`

## Authorities

- `eqos-3ps` approval-history note identified above — binding product-owner selection.
- `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` — A-02 and Phase 0A gate clauses.
- `docs/research/phase-0a-discovery-company-shortlist.md` — non-authoritative facts, inferences, and gaps retained above.
- `docs/evidence/phase-0a/source-package-inventory.json` — metadata-only recorded official-source references; not source content or a rights decision.
