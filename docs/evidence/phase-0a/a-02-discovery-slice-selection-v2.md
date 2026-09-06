# A-02 Discovery Slice Selection — v2 (Apar Industries)

**Record version:** 2.0.0
**Status:** RECORDED — product-owner selection stated in-session 2026-09-06; window confirmed and
analyst-suitability attestation supplied by `A02-ATTEST-002`
(`docs/evidence/phase-0a/a-02-analyst-attestation-v2.md`, 2026-09-06). Supersedes v1.1.0 (Infosys)
for Phase 0.5 work.
**Recorded at:** 2026-09-06
**Author:** orchestrating agent (recording agent, not the decision maker)

## Binding approval event

On 2026-09-06 the product owner (PavanMV) replaced the Infosys discovery slice with Apar
Industries Ltd and required the latest reported quarter to be inside the window. Verbatim:
"Apar and I want analysis including latest quarter".

## Selected vertical slice

**Decision text (scope):** `A-02 Apar Industries issuer Q2 FY26–Q1 FY27 mapped to program Q0–Q3`.

| Program | Issuer quarter | Quarter end | Role |
|---|---|---|---|
| Q0 | Q2 FY26 | 30-Sep-2025 | Timed manual baseline and bootstrap thesis only |
| Q1 | Q3 FY26 | 31-Dec-2025 | Assisted incremental update |
| Q2 | Q4 FY26 | 31-Mar-2026 | Assisted incremental update (audited, FY close) |
| Q3 | Q1 FY27 | 30-Jun-2026 | Assisted incremental update (latest reported) |

Identity: NSE symbol `APARINDS`, BSE scrip `532259`, ISIN `INE372A01015`, company name as filed
"APAR INDUSTRIES LIMITED" (read from the Jun-2026 consolidated instance).

## Evidence retained by epistemic class

### Facts (read from NSE on 2026-09-06)
- Consolidated Ind AS XBRL exists for all four quarters on the NSE Integrated Filing listing
  (`integrated-filing-results`), broadcast 29-Oct-2025, 29-Jan-2026, 28-May-2026, 24-Jul-2026.
- The NSE announcements feed carries, for each quarter, the outcome-of-board-meeting results
  PDF, an investor presentation and a concall transcript (transcripts filed 06-Nov-2025,
  04-Feb-2026, 04-Jun-2026, 31-Jul-2026); a press release for Q1–Q3.
- Instances declare `in-capmkt` taxonomy versions `2025-01-31` (Sep/Dec-2025) and `2026-01-31`
  (Mar/Jun-2026); the shipped parser yields the headline P&L concepts once those namespaces are
  registered.

### Inferences
- Every quarter carries at least one management commitment traceable across periods (Apar
  guides on segment volumes and margins in each call); to be confirmed at Q0.

### Data gaps
- No PDF has been downloaded or read yet; document contents are unverified.
- Screener/Tijori identity for Apar is not mapped (out of scope for the first-party update).

## Analyst-suitability fail-closed gate

**A-02 v2 status: RECORDED (gate discharged 2026-09-06).** Attestation `A02-ATTEST-002` in
`docs/evidence/phase-0a/a-02-analyst-attestation-v2.md` supplies the five fields of the v1 gate,
scope "Apar Industries Ltd (APARINDS), issuer Q2 FY26–Q1 FY27, program Q0 manual baseline /
bootstrap thesis plus Q1–Q3 assisted incremental updates; private/internal boundary only".

## Supersession

This record (v2.0.0) supersedes v1.1.0 for Phase 0.5 work as of 2026-09-06.
The Infosys Q0 artefacts (A-03, A-11) remain valid Phase 0A evidence and are not reused.

## Authorities

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` row A-02;
`docs/workstreams/fundamentals-pilot/phase-0.5-assisted-updates-plan.md`.
