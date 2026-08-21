# Goal: Multi-Stock Pipeline Validation (Fundamentals)

**Type:** runnable goal file — self-contained spec for a loop-style autonomous runner.
**Owner:** PavanMV. **Created:** 2026-08-21. **Status:** ready to run once preconditions hold.

A loop runner should read this, do the work, check itself against the **Definition of
Done**, and repeat until DONE or BLOCKED — surfacing only what needs a human.

---

## Objective

Validate that the Fundamentals extraction pipeline generalizes beyond Infosys by running it
over ≥5 structurally-different stocks and cross-checking every material fact across ALL
available sources. Remove single-stock bias; produce a per-stock reference and a discrepancy
report. Loop over the stock set until each stock reconciles or its discrepancies are recorded.

## Preconditions (do not start until all true)

- [ ] Pipeline built and green: `uv run pytest tests/fundamentals` passes; the Infosys Q1
      acceptance test passes (`ProfitLossForPeriod == 6,374` bound to the Apr–Jun 2024 context).
- [ ] Rights: NSE/BSE private-use (`A05-DECISION-004`); Screener/Tijori as derived cross-check
      only (`bd` memory `validation-multistock-goldloop-2026-08-21`). No external-model upload;
      no anti-bot evasion.
- [ ] Watchlist available: `docs/research/watchlist.md`.

## Scope

**Wave 1 (5 maximally-different domains):** Laurus Labs · MTAR Technologies · Sona BLW ·
Thermax · Titan.
**Wave 2 (after Wave 1 DONE):** one per remaining domain — Netweb, HFCL, Polycab, CG Power,
Eternal (adjust to availability).

**Period per stock:** the latest reported quarter for which a first-party filing exists.

**Sources to cross-check per fact** (use every one that has the stock):
NSE (nselib / NseIndiaApi, context-aware XBRL) · BSE (crawl4AI / `bse`, XBRL) · issuer PDF
(deterministic parse) · Screener · Tijori · SEC (only if a US listing exists — usually absent).

## Loop procedure (per stock)

1. Resolve the NSE symbol + BSE scrip; record which sources actually have the stock.
2. Pull the latest-quarter P&L (+ balance-sheet / cash-flow headline items) from every
   available source, each fact provenance-anchored.
3. Parse context-aware (bind to the correct quarter context; reject standalone/segment/
   prior-year/YTD distractors — the same trap classes as the Infosys oracle).
4. Cross-check each material fact across sources: mark `AGREE` (≥2 first-party sources match
   within decimals-derived tolerance), `MINOR_DIFF`, or `CONFLICT`.
5. Write the stock's **reference file** (`data/gold/<symbol>-<quarter>.json`, gitignored):
   each material fact, its value, the sources that agreed, provenance, and status.
6. Surface for human adjudication ONLY: `CONFLICT`s, low-confidence facts, and any material
   fact with < 2 independent sources.
7. On re-runs: regress the fresh extraction against the stored reference; flag any drift.

## Definition of Done (the loop checks itself against this)

A stock is **DONE** when:
- [ ] Every material P&L line item is either `AGREE` across ≥2 first-party sources, OR carries a
      recorded human adjudication for its `CONFLICT` / single-source status.
- [ ] Cross-foot identities hold (decimals-derived tolerance).
- [ ] A reference file exists at `data/gold/<symbol>-<quarter>.json` with full provenance.
- [ ] No un-sourced number entered the reference (fail-closed).
- [ ] A per-stock report lists agreed facts, discrepancies, and which sources were available.

The **goal is DONE** when all Wave-1 stocks are DONE and a roll-up report exists comparing
extraction robustness across the 5 (which trap classes appeared, which sources covered what,
any pipeline generalization gaps found). Then optionally proceed to Wave 2.

**BLOCKED** (stop and surface, do not loop forever): a stock has no reachable first-party
source; a source needs credentials not available; or a pipeline defect prevents parsing —
report the exact blocker.

## Guardrails

- Human-authoritative on judgment: the runner extracts + cross-checks; a human adjudicates
  `CONFLICT`s and owns any thesis. Aggregator (Screener/Tijori) numbers are cross-check only,
  never source-of-record.
- Polite/low-volume per source; stop on a hard block; no evasion; private/personal use only.
- Every material computed result needs a calculation trace; the model is never the
  authoritative calculator.

## Outputs

- Per-stock reference files: `data/gold/<symbol>-<quarter>.json` (gitignored).
- Per-stock validation reports + a Wave-1 roll-up: `docs/research/validation/`.
- Discrepancy queue for human adjudication.
