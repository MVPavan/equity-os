# Upstox API Evaluation (2026-08-24)

Process: GPT-5.6 Luna research (web, citation-tagged) → Opus 5 adversarial
citation audit (all 16 load-bearing citations fetched and verified; zero
hallucinated endpoints) → orchestrator consolidation. Full reports:
`scratchpad/council/upstox-api-research/` (session-local; this doc is the
durable record).

> ## SUPERSEDED IN PART — 2026-09-03
>
> **The kill criterion in this document has fired.** The independence test was
> run and Upstox's fundamentals **share lineage with Screener**: Upstox's
> `operating_profit` is Screener's *Profit before tax* to the crore (12/12 data
> points across 3 companies and both bases), and Upstox reproduces Screener's
> divergence from the BSE filing on TITAN's Jun-2026 net profit (1777 vs the
> filed 1699). Per this document's own rule — "identical-digit agreement with
> Screener's errors = shared lineage -> drop the fundamentals lane" — the six
> statement/ratio endpoints are **refused**.
>
> What survives, and is now verified live: the **price lane** (candles are
> split/bonus adjusted, daily history to Jan 2000), the **instrument master**
> (100% ISIN coverage on equity rows), **suspended instruments** (delisting
> detection), **corporate actions**, **share holdings**, and **FII/DII activity**.
> Those have no XBRL or Screener counterpart, so lineage does not bear on them.
>
> Also corrected here: this document records "only 4 periods" and "no as-of
> field" as inference — both are now confirmed fact. `time_period=quarterly` is
> silently ignored on balance sheet and cash flow (income statement only).
>
> **Reframed 2026-09-03 (same day, owner decision).** The refusal above stands
> for *adjudication* and is reversed for *verification*. Upstox's statement
> endpoints are non-independent, which makes them useless as a third vote and
> useful as a parse-check on Screener's HTML scraping: because the upstream
> number is the same, a disagreement isolates to our parser. `income-statement`,
> `balance-sheet`, `cash-flow` and `key-ratios` return as **Lane B** —
> log-only, barred from reconciliation. `profile` and `competitors` remain
> refused. See `docs/research/upstox-integration-plan.md` §1, §6.9, §9.6.
>
> Current authority: `docs/research/upstox-api-surface-inventory.md` for the
> endpoint surface, `docs/research/upstox-integration-plan.md` for what is
> built and why.

## Verdict: PILOT-FIRST, with the price lane leading

Adopt-worthy on its own merits: **price / instrument-master / corporate-actions**.
Unproven until tested: **fundamentals** (vendor independence unknown).

## Verified facts

- **Access**: trading + market-data APIs are free. The **Analytics Token** is
  the key artifact: free, read-only, **1-year validity, no OAuth redirect, no
  daily manual login** (the classic Indian broker-API pain is absent). One
  token per account. Unknown: whether Developer-App creation requires a KYC'd
  trading account (likely, undocumented).
- **Fundamentals API exists** (launched 2026-05-11): 8 endpoints keyed by ISIN
  — income statement, balance sheet, cash flow, key ratios, shareholdings,
  profile, corporate actions, competitors. `type=consolidated|standalone`.
  BUT (all verified against endpoint docs + staff forum posts):
  - only **4 periods** of history (staff-confirmed limitation);
  - `full_statement` is **annual-only**; quarterly = 3 summary lines;
  - values in **INR crore** (rounded) vs our rupee-exact XBRL;
  - key ratios = **current snapshot of 6 ratios**, no time series;
  - balance-sheet summary = total assets + total liabilities only;
  - shareholding = 5 buckets, percentages only, no pledge data;
  - **no data-vendor attribution anywhere** → independence from
    Screener/Tijori's upstream is unknown;
  - no change-detection/earnings-calendar endpoint; no as-of/version
    dimension (restatements overwrite silently → snapshot-and-hash at fetch).
- **Price lane**: daily OHLCV **back to Jan 2000**, minutes from 2022;
  50 req/s / 500/min / 2000 per 30 min. Split/bonus adjustment UNDOCUMENTED —
  must be tested against a known split before trust.
- **Instrument master**: daily ~6 AM IST JSON, NSE+BSE, with `isin`,
  `instrument_key`, `trading_symbol`, `instrument_type`; separate
  suspended-instruments file. Directly solves watchlist ISIN normalization
  (bead eqos-6v2) and gives delisting/suspension detection.
- **Terms**: website ToU broadly prohibit storing/redistribution; an Upstox
  staff forum answer (2026-06-25) explicitly permits caching/storing responses
  for internal application use, no attribution required — informal, not a
  contract. Safe envelope: private internal research, no public display, no
  redistribution. Written confirmation worth requesting.

## The decisive risk (Opus finding)

If Upstox's fundamentals come from the same aggregator feeding Screener or
Tijori, it is NOT a third opinion — agreement would be lineage, not
corroboration, injecting false confidence into a fail-closed reconciler.
**Independence must be tested, not assumed**: where Screener disagrees with
XBRL, check which side Upstox lands on; identical-digit agreement with
Screener's errors = shared lineage → drop the fundamentals lane.

## Pilot plan (~1 day once a token exists)

0. Owner creates Developer App + Analytics Token (records whether KYC account
   was required). BLOCKING.
1. Independence test: 10 ISINs (3 large, 3 mid, 2 with known restatements,
   1 dual-listed, 1 recent IPO); three-way compare Upstox vs XBRL vs
   Screener/Tijori on statements. Kill criterion above.
2. Depth/shape: count periods; probe undocumented `time_period=quarterly` on
   BS/CF; record crore precision to size the reconciliation tolerance.
3. Price smoke: candles across a known split + bonus; deep pull 2000→today.
4. Instrument master: join to watchlist by ISIN both directions; measure
   misses.

Decision rule: 3+4 pass → adopt price/instruments/corp-actions lane
(snapshot raw + hash, private-only). 1 proves independence → add fundamentals
as a 4-period annual cross-check with explicit crore tolerance. 1 fails →
price lane only; record the why.

## Role in the stack (if adopted)

XBRL stays source of record. Screener/Tijori stay the rich derived layers.
Upstox becomes: (a) the free high-volume price/volume + universe/lifecycle
lane we currently lack entirely, (b) corporate-action cross-check, and
(c) possibly a bounded third fundamentals opinion. It does NOT replace
scraping: 4 periods of crore-rounded annuals cannot validate the depth and
granularity Screener/Tijori give us.
