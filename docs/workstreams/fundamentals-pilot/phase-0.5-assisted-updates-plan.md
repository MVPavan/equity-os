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
| Q0 baseline + bootstrap thesis produced and reviewed | DONE — A-03 facts owner-confirmed; A-11 thesis via the multi-model method | NOT STARTED — method reopened 2026-09-07, see §8 decision 2 |
| Three assisted updates produced and reviewed | NOT STARTED | NOT STARTED |
| Review times recorded (baseline + three) | NOT STARTED | NOT STARTED |
| Claim-level telemetry, correction categories | NOT STARTED | INSTRUMENT BUILT 2026-09-07 (`fundamentals review`), no sessions yet |
| Source-of-truth matrix | NOT DONE | NOT DONE |
| Fact identity/revision rules, registries | PARTIAL (append-only fact store; no metric registry) | PARTIAL — metric registry + frozen predicate registry landed 2026-09-07 (`verify/metric_registry.py`, `verify/thesis_predicates.py`) |
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
   **DONE 2026-09-06** (commits 9235dde, and the config commit that follows it). All four
   quarters render end-to-end from `config/aparinds-*.yaml`. Findings: NSE serves these
   quarters only through `integrated-filing-results`; instances declare `in-capmkt`
   2025-01-31 / 2026-01-31 and identify the entity by BSE scrip; the results PDFs are scanned
   (unit word garbled in Q4 FY26 and Q1 FY27; "Profit" garbled in Q2 FY26); Apar tags PBT after
   exceptional items and before associates; Q3 FY26's PDF cannot bind the post-exceptional PBT
   row, so that quarter's PDF cross-check covers four of the five headline figures.
2. **Q0 baseline and bootstrap thesis (owner).** Produce the A-03-shaped fact baseline and an
   A-11-shaped thesis with explicit observable falsifiers for the Sep-2025 package.
   **CORRECTION 2026-09-07:** the first draft of this plan described step 2 as a *timed manual
   pass* "per A-07/A-13". That misread both contracts. A-07 and A-13 each state in their own
   approved text that Q0 "was executed via the multi-model method (bd memory
   `methodology-q0-thesis-multimodel-2026-08-21`), **not** a timed manual pass", and that their
   ceilings and targets are forward product-owner estimates **not** derived from observed manual
   Q0 minutes. The standing product-owner method (2026-08-21) is: independent multi-model
   generation, orchestrator cross-verification, and human adjudication of divergent, material and
   low-confidence points only. The owner confirms the facts; the owner does not author the thesis.
   → verify: fact baseline owner-confirmed; thesis marked ANALYST-APPROVED; adjudicated exceptions
   listed with the owner's ruling on each.
3. **Comparatives from stored facts.** Point the comparator at the retained instances so each
   update states QoQ and YoY with trace ids, fail-closed on a missing prior.
   **DONE 2026-09-07** (slice phase05-sB, commit d8f80b6). `comparators.qoq/yoy` blocks in the
   four Apar configs pin the prior instances by sha256; taxonomy drift (in-bse-fin → in-capmkt,
   2025 → 2026 revision) is accepted per instance and printed once in the §3 trace. All four
   window quarters render QoQ and YoY for every P&L line with no unavailable row.
4. **Management ledger across quarters.** Carry each guidance/commitment claim from quarter N
   into N+1 with transcript anchors on both ends (new / reaffirmed / modified / met / missed).
   **DONE 2026-09-07** (slice phase05-sC, commits 1755670, 7ee9a6b). Ledger at
   `data/ledger/aparinds-management-ledger.json`; statuses NEW / REAFFIRMED / MODIFIED / CARRIED
   (met / missed is the predicate evaluator's job, step 5). Guidance rules are per-config and
   transcript-derived (management-spoken lines only). Operating rule: the ledger only accepts a
   later quarter, so a re-run of an already-recorded quarter requires deleting the ledger file
   and replaying the window in order (Q2-FY26 → Q3-FY26 → Q4-FY26 → Q1-FY27); follow-up bead filed.
5. **Thesis impact against the approved prior thesis.** For each falsifier in the Q0 thesis,
   evaluate stored facts → strengthened / weakened / unchanged / unresolved with fact ids.
   **DONE 2026-09-07** (slice phase05-sD, commits b1869ae, e7ec02a, 835357d). Dispositions are
   WEAKENED / HELD / UNRESOLVED (deterministic; "strengthened" is analyst narrative, not a
   predicate). `fundamentals thesis-impact --report-json <run --out-json> --thesis
   docs/evidence/phase-0.5/<approved thesis>.yaml --out <md>`; exit 1 when any falsifier is
   WEAKENED. Smoke-tested on the real Q3 FY26 and Q1 FY27 artifacts.
6. **Review telemetry and approval record (B-04, B-13).** `review` command: session start/stop,
   per-claim disposition and correction category, approval record beside the report.
   **DONE 2026-09-07** (slice phase05-sE, commit 1cdac76). `fundamentals review start --report-json
   <json> --session <dir>`, `review list`, `review claim --claim <id> --disposition accepted|edited|
   rejected|deferred [--category …] [--seconds N] [--note …]`, `review finish --decision
   approved|rejected --decider "<name>" --verbatim "<text>"` writes `summary.json` and
   `approval_record.md`; instrumentation overhead is measured and reported.
7. **Run the three assisted updates in order,** owner reviewing each before the next is generated;
   seeded-error drill on one report; then write the source-of-truth matrix and claim schema from
   the evidence produced, re-score §F, and update the register rows.

Steps 3–6 carry the same verification lines as the Infosys draft (fail-closed on missing prior,
anchors resolve on both ends, every falsifier gets exactly one disposition, record carries total
minutes and per-claim time). Steps 3, 4, 5, 6 are independent of each other and can run as
parallel slices once step 1 lands; step 7 needs all of them.

Build record for steps 3–6 (2026-09-07): one red-proof acceptance file per slice authored by
Opus, implementation by Codex gpt-5.6-terra (owner directive), gate `scripts/verify.sh gate
<slice>` PASS on every commit (1848 tests green, ruff, mypy --strict, skips at baseline). Step 7
is now unblocked by the agent side; it waits on step 2 (owner Q0).

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
2. **(Reopened 2026-09-07 after the correction in §4 step 2.)** Confirm that the standing
   2026-08-21 multi-model Q0 method extends to Apar, or choose another basis. The owner's Q0 work
   under that method is fact confirmation plus exception adjudication, not authoring an analysis.
   Falsifiers can be grounded in management's own quote-anchored commitments (the ledger built in
   step 4), which turns adjudication into verification rather than valuation.
3. Review time and per-claim dispositions recorded locally under `data/` as the B-04 instrument.
