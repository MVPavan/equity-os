# Phase 0.5 — the three assisted updates (Apar Industries, program Q0–Q3)

**Status:** APPROVED 2026-09-06 for §8 decisions 1 and 3; A-02 v2 attested the same day
(`docs/evidence/phase-0a/a-02-discovery-slice-selection-v2.md`). Decision 2 (who produces the
manual Q0 and when) is open; steps 0, 1 and 3–6 proceed regardless.

## 1. Owner decision that drives this plan

On 2026-09-06 the product owner replaced Infosys with **Apar Industries Ltd (NSE `APARINDS`,
BSE 532259, ISIN INE372A01015)** and asked for the latest reported quarter to be inside the
analysed window. The latest consolidated result on NSE is the quarter ended 30-Jun-2026 (Q1 FY27,
filed 24-Jul-2026). The window is therefore:

| Program | Issuer quarter | Quarter end | Role | XBRL filed | Transcript filed |
|---|---|---|---|---|---|
| Q0 | Q2 FY26 | 30-Sep-2025 | Manual baseline + bootstrap thesis (timed) | 29-Oct-2025 | 06-Nov-2025 |
| Q1 | Q3 FY26 | 31-Dec-2025 | Assisted update 1 | 29-Jan-2026 | 04-Feb-2026 |
| Q2 | Q4 FY26 | 31-Mar-2026 | Assisted update 2 (audited, FY close) | 28-May-2026 | 04-Jun-2026 |
| Q3 | Q1 FY27 | 30-Jun-2026 | Assisted update 3 (latest) | 24-Jul-2026 | 31-Jul-2026 |

Everything in the table was read from NSE on 2026-09-06 (Integrated Filing listing and the
announcements feed; listings saved under `scratchpad/apar/`, not committed). Every quarter has a
consolidated Ind AS XBRL, an outcome-of-board-meeting results PDF, an investor presentation and a
concall transcript; Q1–Q3 also have a press release. No quarter is missing a document.

## 2. Where Phase 0.5 stands against register §F after the change

| §F exit criterion | Infosys state | Apar state |
|---|---|---|
| Bootstrap thesis approved | DONE (A-11 v1.0.0) | NOT STARTED — owner writes it at Q0 |
| Q0 manual baseline produced and reviewed | DONE (A-03), untimed | NOT STARTED — this time timed per A-07/A-13 |
| Three assisted updates produced and reviewed | NOT STARTED | NOT STARTED |
| Review times recorded (baseline + three) | NOT STARTED | NOT STARTED |
| Claim-level telemetry, correction categories | NOT STARTED | NOT STARTED |
| Source-of-truth matrix | NOT DONE | NOT DONE |
| Fact identity/revision rules, registries | PARTIAL (append-only fact store; no metric registry) | same |
| Rejected-claim rework path, package versioning | NOT DONE | NOT DONE |
| Point-in-time capture started | DONE 2026-09-05 | DONE (reuse the snapshot store) |
| Golden cases automated | PARTIAL (watchlist gold only) | NOT STARTED for Apar |

A-04 output contract, A-07 budget contract and A-13 metric contract are company-agnostic and
stay in force. The Infosys Q0 artefacts stay on record as Phase 0A evidence; they are not reused.

## 3. What the pipeline can and cannot do for Apar today (verified 2026-09-06)

1. **NSE listing path is wrong for this window.** `xbrl_source.fetch_consolidated_quarter` reads
   NSE's `corporates-financial-results` feed, which stops at Dec-2024 for Apar. Mar-2025 onward
   is served by `integrated-filing-results` (rows carry `qe_Date`, `consolidated`, `xbrl`,
   `broadcast_Date`). A second listing path is needed; download and verification stay as they are.
2. **Parser refuses the real instances on namespace alone.** The shipped `in-capmkt` spec pins
   `…/2023-03-31/in-capmkt`; Apar's Sep-2025 and Dec-2025 instances declare `2025-01-31`, the
   Mar-2026 and Jun-2026 instances declare `2026-01-31`. With only the namespace patched, the
   shipped parser yields 75 observations from the Jun-2026 instance including
   RevenueFromOperations, ProfitBeforeTax, ProfitLossForPeriod and basic EPS under context `OneD`
   (the quarter; `FourD` is year-to-date). Scope, period and identity concepts match the spec
   unchanged. The fix is two registered taxonomy versions, not a new parser.
3. **PDFs are not on the results listing.** `pdf_attach` is null for every Apar row; the results
   PDF, press release, presentation and transcript are attachments on the NSE announcements feed
   (`attchmntFile`). The retention step reads that feed; `bse_pdf_source` is the fallback.
4. **Config is Infosys-specific.** `config/fundamentals.yaml` pins INFY Q1 FY25 and a synthetic
   XBRL fixture; an Apar profile is needed (symbol, scrip, ISIN, taxonomy `in-capmkt`).
5. **Workflow gaps are unchanged from the Infosys assessment:** no cross-quarter comparatives
   from stored facts, no management ledger across quarters, no thesis-impact against an approved
   prior thesis, no review telemetry or approval record.

## 4. Steps (each independently verifiable)

0. **Re-open A-02.** Owner attests the v2 record (Apar, window above). Until then nothing below
   is authorised. → verify: attestation file exists with the verbatim line and date.
1. **Acquire and retain the four-quarter package.** Register the two `in-capmkt` namespace
   versions; add the Integrated Filing listing path; retain the four consolidated instances and
   the sixteen PDFs under `data/raw/watchlist/aparinds/{nse,nse_pdf}/` with a retrieval manifest
   (sha256, URL, retrieved_at). Add the Apar config profile.
   → verify: `run --issuer APARINDS --quarter Q1-FY27` parses the real instance; the Jun-2026
   figures in the manifest match the XBRL (Revenue 6,591.06 cr; PBT 622.34 cr; PAT 467.45 cr;
   basic EPS 116.37); Q4 FY26 uses `OneD` not `FourD`.
2. **Q0 manual baseline and bootstrap thesis (owner).** Timed manual pass over the Sep-2025
   package producing the A-03-shaped baseline and an A-11-shaped thesis with explicit observable
   falsifiers. The agent does not pre-compute anything for this step.
   → verify: baseline record with elapsed minutes; thesis marked ANALYST-APPROVED.
3. **Comparatives from stored facts.** Point the comparator at the retained instances so each
   update states QoQ and YoY with trace ids, fail-closed on a missing prior.
4. **Management ledger across quarters.** Carry each guidance/commitment claim from quarter N
   into N+1 with transcript anchors on both ends (new / reaffirmed / modified / met / missed).
5. **Thesis impact against the approved prior thesis.** For each falsifier in the Q0 thesis,
   evaluate stored facts → strengthened / weakened / unchanged / unresolved with fact ids.
6. **Review telemetry and approval record (B-04, B-13).** `review` command: session start/stop,
   per-claim disposition and correction category, approval record beside the report.
7. **Run the three assisted updates in order,** owner reviewing each before the next is generated;
   seeded-error drill on one report; then write the source-of-truth matrix and claim schema from
   the evidence produced, re-score §F, and update the register rows.

Steps 3–6 carry the same verification lines as the Infosys draft (fail-closed on missing prior,
anchors resolve on both ends, every falsifier gets exactly one disposition, record carries total
minutes and per-claim time). Steps 3, 4, 5, 6 are independent of each other and can run as
parallel slices once step 1 lands; step 7 needs all of them.

## 5. Estimate

Step 1 about one day of agent work. Step 2 is owner time: one to two sessions. Steps 3–6 three to
four days of agent work (test-first, Opus subagents, one slice each). Step 7 is three owner review
sessions at the 20-minute ceiling plus the drill, and half a day of agent work for the matrix and
register update. Roughly one and a half weeks of agent work plus five owner sessions.

## 6. Out of scope

Screener, Tijori and Upstox for Apar (the update is first-party only: NSE XBRL, results PDF,
transcript). Memory promotion. Any new source. Re-running Infosys.

## 7. Proposed beads (filed only on approval)

Under epic eqos-4j2: close eqos-4j2.1 as superseded by shipped code; new children
`a02-v2-apar-attestation` (owner), `apar-package-retention`, `q0-manual-baseline-apar` (owner),
`comparatives-from-stored-facts`, `management-ledger`, `thesis-impact`, `review-telemetry`,
`assisted-updates-q1-q3` (blocked by all of the above), `sot-matrix-and-claim-schema`; plus a
housekeeping task to bring the register's A-rows in line with the 0A exit record and the A-02 v2.

## 8. Decisions needed from the product owner

1. Window as in §1 (Q0 = Sep-2025 manual, Q3 = Jun-2026 latest). Alternative: Q0 = Jun-2025 and
   four assisted quarters; more owner review time, one more package.
2. Step 2 is a timed manual pass done by you before any assisted output exists for Apar. Confirm
   you will do it, or say if Q0 should instead be assisted-with-full-review (weaker §F evidence).
3. Review time and per-claim dispositions recorded locally under `data/` as the B-04 instrument.
