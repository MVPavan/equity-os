# Equity-OS completion work list — 2026-10-11

Owner-reviewed priority list of everything left to reach `VISION_SATISFIED`. Rows are
deduplicated: finishing a row delivers every earlier item listed under *Absorbs*. Beads remain the
work-state authority; this file is the ordering and grouping the owner accepted ("looks fine",
PavanMV, 2026-10-11). Current verdicts: `PILOT_PROVEN: NO`, `CORE_RESEARCH_RELEASE: NO`,
`VISION_SATISFIED: NO` (see `docs/evidence/product-completion/vision-acceptance.json`).

| # | Work item | Done means | Absorbs | Who | Depends on |
|---|---|---|---|---|---|
| 1 | Housekeeping | Refreshed `brief.md` committed; stale beads (eqos-0xb.6/.9/.10, eqos-4j2.9, eqos-283, eqos-4ff) closed or re-scoped | — | Agent; owner confirms closures | — |
| 2 | Cross-source data foundation | Approved canonical field spec (every filed line item + vendor formula rows) × sources XBRL, results PDF, Screener, Tijori, Upstox, exchange shareholding filing; comparator over all six; per-company settings generated, not hand-written; Apar + 10 watchlist companies captured and reconciled (incl. the ~4.4 cr operating-expense gap vs Screener); PBT after associate share (340.53) and OPM as rows; bank/NBFC row set | eqos-al0, eqos-s2g, eqos-ya6, eqos-s02, eqos-mv8, eqos-7qe, eqos-hvh, eqos-rdb, eqos-f2m | Agent + owner spec approval + Upstox token | — |
| 3 | Commitment extraction | Model proposes commitments with exact quotes, code verifies each against the hashed page span; issuer-agnostic; Apar transcripts swept for missed commitments | regex guidance rules | Agent | — |
| 4 | Point-in-time integrity | True acquisition/extraction/producer evidence on every fact; locator-failure recovery; exact rebuild of an earlier run; later restatement leaves it unchanged (V12) | eqos-xg5, eqos-unv, eqos-j0z | Agent | — |
| 5 | Owner pilot decisions | Q0 signed off with actual minutes; monitoring policy adopted; retrospective-demonstration successor terms accepted | eqos-4j2.3, eqos-4j2.14 | **Owner** (agent prepares) | 2, 3, 4 |
| 6 | Apar sequential reviews → `PILOT_PROVEN` | Q1 → review → Q2 → review → Q3; seeded-error drill; actual minutes; Phase 0.5 exit accepted | eqos-4j2.8, eqos-4j2 | **Owner** + agent | 5 |
| 7 | Workflow robustness | Rejected claim invalidates downstream and yields a new package; published-artifact correction; crash → resume/rerun without duplicate canonical changes (V04 correction part, V05) | — | Agent | — (demo uses 6) |
| 8 | Calculation breadth | Cash conversion, leverage, dilution as registered traced calculations on balance-sheet/cash-flow rows; definitions accepted (V03) | — | Agent + owner definition sign-off | 2 |
| 9 | Core research release | 2–3 core companies end-to-end; same runs produce install docs, cost/time/failure measurements, golden cases (V09 core, V11) | — | **Owner** + agent | 6, 7, 8 |
| 10 | Later-capability activation decisions | Activation rulings for V06–V08, V10, V13; scope of automated initiation and portfolio/risk | — | **Owner** | 9 |
| 11 | Memory, monitoring, valuation | Activated capabilities built and proven (V06, V07, V08) | — | Agent | 10 |
| 12 | Peers, experiments, challenge | Peer comparison/shortlists on canonical definitions, Screener/Tijori breadth, preregistered experiments, bull/bear challenge (V09 peers, V10, V13) | eqos-kx4.5, eqos-kx4.6, eqos-d37 | Agent | 10 (2 for peers) |
| 13 | Acceptance mapping (continuous) | Every requirement bound to proof or approved exclusion; final verdict | eqos-2oj | Agent | all |

Critical path: 2, 3, 4 in parallel (disjoint code) → 5 → 6 → 9 → 10 → 11/12. Rows 1 and 7 fit
anywhere; row 8 starts once row 2's spec is approved.

Monitoring direction recorded on eqos-4j2.14 (2026-10-11, not yet adopted policy): any breach opens
a warning; it clears after 3 consecutive non-breaching quarters; a breach while open joins the open
episode; analyst may close early with a recorded reason.
