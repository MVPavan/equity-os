# Data-Gathering Tools Evaluation — NSE/BSE/Screener/Tijori/FII-DII candidates

**Bead:** eqos-cc5 · **Authorized by:** `A05-DECISION-002` (bounded, one-time,
private evaluation-only carve-out; isolated venvs; low-volume polite calls).
**Date:** 2026-08-20 · **Target slice:** Infosys (INFY / BSE 500209) FY25 quarters.

> **Scope reminder.** This is a private evaluation. It does **not** lift the
> HELD/DENY dispositions of `A05-DECISION-001`. NSE terms prohibit
> systematic/automated collection; BSE/Screener/Tijori terms are unreviewed or
> aggregator-restricted. Nothing here authorizes production, standing, scheduled,
> or bulk use.

Live results captured in isolated per-library venvs under
`scratchpad/lib-eval/` (session scratchpad); result JSONs are cited per row.
Five NSE/BSE libraries were installed and live-tested; six GitHub repos (rows
7,9,10,11,12,14 of inventory §6) were assessed **statically** from their public
GitHub pages only (no server stand-up, no Screener/Tijori live scraping).

---

## Executive summary

| Library / tool | Installs? | Live test result | Best data obtained | Quarter-grain financials / XBRL? | Fit | ToS / maintenance risk |
|---|---|---|---|---|---|---|
| **nselib** (`RuchiTanmay/nselib`) | Yes (PyPI) | WORKS | Price/delivery history **and** parsed **Ind AS XBRL** quarterly financials | **YES — Ind AS XBRL, 65 fields** (parses NSE filing XBRL) | **H** | NSE ToS (scraping-prohibited); maintained |
| **nse** (`BennyThadikaran/NseIndiaApi`) | Yes (PyPI, needs `requests`) | WORKS | Full quote priceInfo; `results_comparison` = 5 quarters P&L; `financial_results` = filing meta + **XBRL link** | **YES — structured P&L (5 qtrs) + XBRL link** | **H** | NSE ToS; actively maintained |
| **nsepython** (`aeron7/nsepython`) | Yes (PyPI) | PARTIAL | Corporate announcements (2917 records, PDF links); `nse_eq` quote **blocked (empty)** | No (announcements/PDF links only) | **L–M** | NSE ToS; quote path blocked |
| **jugaad-data** (`jugaad-py/jugaad-data`) | Yes (needs `pandas`) | WORKS | INFY daily OHLCV + delivery %/qty | No (prices only) | **M** | NSE ToS; maintained |
| **bsedata** (`BseIndiaApi`-family) | Yes (PyPI) | WORKS | BSE live quote (name, price, 52wk, face value, industry) | No (quote snapshot only) | **L–M** | BSE ToS; maintained |
| **tijori-finance-mcp** (row 7) | Static only | Not run | *(claims)* quarterly P&L/BS/CF, KPIs, shareholding, transcripts | Quarterly P&L claimed; **no XBRL**; aggregator-derived | **L** | ⛔ Needs **Tijori login**; Playwright session; ToS-restricted |
| **screener-scraper-pro** (row 9) | Static only | Not run | *(claims)* quarterly results, P&L, BS, CF, ratios, shareholding | Quarterly P&L claimed; **no XBRL**; scraped | **L** | ⛔ Scrapes Screener.in; GPL-3.0; ToS unreviewed |
| **openscreener** (row 10) | Static only | Not run | *(claims)* quarterly results, P&L, BS, CF, ratios (Playwright) | Quarterly P&L claimed; **no XBRL**; scraped | **L** | ⛔ Scrapes Screener.in; MIT; ToS unreviewed |
| **fii-dii-data** (row 11) | Static only | Not run | FII/DII flows, F&O positioning, sector allocation | **No** — no company financials | **L** | ⛔ NSE/NSDL/BSE endpoints; MIT |
| **nse-bse …-mcp** (row 12, Tapetide) | Static only | Not run | *(claims)* quotes, history, quarterly+annual P&L/BS/CF, 326 ratios | Quarterly financials claimed; **no XBRL**; aggregator | **L** | ⛔ Needs **tapetide.com token** (OAuth); aggregator ToS |
| **fii-dii-analysis** (row 14) | Static only | Not run | FII/DII flows (2013–2026) via CORS proxy to NSE | **No** — no company financials | **L** | ⛔ NSE endpoint (via proxy); MIT; ~3 commits |

Fit = suitability for the A-06 structured-financials gap specifically, not general utility.

---

## KEY QUESTION — can any tool obtain quarter-grain structured financials / Ind AS XBRL for INFY FY25?

**YES — verified live, for two tools, both via NSE's own corporate-filings endpoint.**

- **nselib** downloaded and parsed INFY's **Ind AS XBRL** for Q1 FY25 (Apr–Jun 2024,
  Consolidated, Audited) into **65 structured line items**: RevenueFromOperations
  `393150000000` (₹39,315 Cr), ProfitBeforeTax `90210000000`, ProfitLossForPeriod
  `63740000000` (₹6,374 Cr), Basic EPS `15.38`, plus reporting-period dates,
  standalone/consolidated flag, currency, and the full P&L taxonomy. These figures
  match Infosys' published Q1 FY25 consolidated results. Evidence:
  `scratchpad/lib-eval/result-nselib-financials.json`.
- **NseIndiaApi** returned the same INFY Q1 FY25 filing **XBRL link** (symbol-filtered)
  via `financial_results()`, and via `results_comparison("INFY")` returned **5 recent
  quarters** of structured P&L directly (no XBRL parse needed): e.g. Q3 FY25 (Oct–Dec 2024)
  consolidated net profit `635800` Lakhs (₹6,358 Cr), Basic EPS `15.31`, current/deferred
  tax, depreciation, face value. Evidence: `scratchpad/lib-eval/result-nse-financials.json`.

Aggregator tools (Tijori MCP, screener-scraper-pro, openscreener, Tapetide MCP)
*advertise* quarterly P&L/BS/CF, but as **scraped or aggregator-derived numbers, not
Ind AS XBRL**, and every one sits behind a login, paid token, or unreviewed ToS. They
are **partials at best and rights-blocked**; not verified live in this evaluation.

**Bottom line:** the structured-financials gap for INFY FY25 **can be closed** — but only
from NSE's first-party XBRL filings (nselib / NseIndiaApi), which are exactly the
NSE endpoints `A05-DECISION-001` holds as ToS-prohibited. Closing it in production is a
**rights decision**, not a technical gap.

---

## Thorough NSE+BSE capability matrix (round 2)

Round 1 focused on NSE and left BSE thin (bsedata quote only). Round 2 enumerated
each library's **actual installed public API** (read from source/docstrings in the
per-library venvs) and live-tested the fundamentals-relevant surface for **both**
exchanges, INFY-scoped. Same bounds (`A05-DECISION-002`): isolated venvs, ≤15 live
calls/lib, ≥2.5s apart, stop-on-block, small samples. **No calls were blocked this
round** — every NSE and BSE endpoint tested returned data (note: round 1's
`nsepython.nse_eq` block was endpoint-specific; the financials endpoints below use
different paths that worked). Evidence: `scratchpad/lib-eval/result-r2-*.json`.

### Consolidated matrix — library × capability

Legend: **XBRL** = parses/returns Ind AS XBRL; **struct** = structured numeric P&L
(no XBRL parse); **link** = returns a filing/XBRL URL only; **filings** = filing
announcements + PDF/attachment URLs; **✔** = works; **≈** = works but market-wide
(client-side INFY filter needed); **✗ n/s** = not supported by the API;
**✗ blocked** = endpoint returned empty/blocked; **—** = exchange not covered.

| Library | NSE structured financials | NSE XBRL | BSE structured financials | BSE XBRL | Announcements / filings | Shareholding | Corp actions / board mtgs | Price / OHLCV |
|---|---|---|---|---|---|---|---|---|
| **nselib** (NSE-only) | ✔ struct (via master) | **✔ XBRL** (parses 65 fields) | — | — | ✔ filings (results master) | ✗ n/s | ≈ actions + event calendar | ✔ |
| **nse / NseIndiaApi** | **✔ struct** (`results_comparison`, 5 qtrs) | ✔ **link** (`financial_results`) | — | — | ✔ (symbol-filtered) | **✔ promoter/public/empTrust + XBRL link** | ✔ actions, board mtgs, annual reports | ✔ (quote) |
| **nsepython** | **✔ struct** (`nse_past_results`, 5 qtrs) | ✔ **link** (`nse_results` master) | ✗ n/s | ✗ n/s | ✔ (`nsefetch` corp-announcements) | ✗ n/s | ≈ `nse_events` (market-wide) | ✗ blocked (`nse_eq`) |
| **jugaad-data** | ✗ n/s | ✗ n/s | ✗ **struct** — **filings only** | ✗ (PDF attachments, no XBRL) | ✔ **BSE** filings + PDF URLs (incl. "Result"/"Board Meeting" categories) | ✗ n/s | ✗ (only via BSE announcement categories) | ✔ NSE OHLCV; BSE = no price method |
| **bsedata** (BSE-only) | ✗ n/s | ✗ n/s | ✗ n/s | ✗ n/s | ✗ n/s | ✗ n/s | ✗ n/s | ✔ **BSE quote** (adds mkt cap, face value, 52wk, depth) |

nselib also exposes `pe_ratio(trade_date)` → per-symbol P/E for ~1,547 stocks
(INFY filterable) — a valuation datum, not a statement.

### Per-library round-2 findings (new vs round 1)

- **nse / NseIndiaApi — biggest gains.** Beyond round 1's `results_comparison` +
  `financial_results`, the installed API also has, all **symbol-filtered and all
  verified live**: **`shareholding("INFY")`** → 21 quarters of promoter+group
  (13.82%), public (85.97%), employee-trust (0.21%) holdings, each with a
  **shareholding-pattern XBRL link** (`SHP_*.xml`); `actions()` (20 corporate
  actions incl. "Dividend – Rs 25 Per Share"); `boardMeetings()` (8, incl. the
  Q3 FY25 results-meeting intimation with an XBRL attachment); `annual_reports()`
  (17 years of AR PDF links); and `announcements(symbol=…)`. This is by far the
  richest first-party NSE surface. Evidence: `result-r2-nseindiaapi.json`.
- **nselib — round-1 correction.** `corporate_actions_for_equity`,
  `event_calendar_for_equity`, and `pe_ratio` take **no symbol arg** — they return
  market-wide tables (178 / 807 / 1,547 rows) that must be filtered to INFY
  client-side. `event_calendar` surfaced INFY's Q3 FY25 "Financial Results" board
  meeting (16-Jan-2025). Still NSE-only; no shareholding, no BSE. Evidence:
  `result-r2-nselib.json`.
- **nsepython — round-1 correction.** Not announcements-only: **`nse_past_results("INFY")`
  returns 5 quarters of structured P&L** (Q3 FY25 Oct–Dec 2024 consolidated net
  profit `635800` Lakh = ₹6,358 Cr, basic EPS 15.31, current/deferred tax,
  depreciation, face value) — the **same NSE `results-comparision` endpoint** as
  NseIndiaApi, so a third route to the *same* data, not a new source. `nse_results`
  gives the filing master with XBRL links. `nse_eq` quote still blocked. **No BSE
  helpers exist** in the installed API. Evidence: `result-r2-nsepython.json`.
- **jugaad-data — real BSE coverage found.** The `jugaad_data.bse.BSELive` module
  (missed in round 1) live-returns **BSE corporate announcements for scrip 500209**
  with PDF **attachment URLs**, across categories `Board Meeting`, `Company Update`,
  `Others`, `Result` (22 rows in the FY25 Q1 window). This is the only tested route
  into BSE *filings* — but it is **announcement metadata + PDF links, NOT structured
  financials and NOT parsed XBRL** (the default `category="Result"` args are treated
  as "no filter" by the library, a quirk to note). No BSE live-price method exists in
  this module. Evidence: `result-r2-jugaad-bse.json`.
- **bsedata — fuller quote, still quote-only.** `getQuote("500209")` returns 24
  fields — round 1 undersold it: it includes **`marketCapFull` (₹4,58,641 Cr),
  `marketCapFreeFloat`, faceValue, 52-wk, weightedAvgPrice, 2-wk avg qty, and 5-level
  buy/sell depth**. But the whole API is `getQuote / getBhavCopyData / getIndices /
  topGainers / topLosers / getScripCodes / verifyScripCode` — **no financials, no
  announcements, no shareholding**. The task-mentioned `getPeriodTrend` does **not
  exist** in this installed version. `verifyScripCode` needs a locally-downloaded
  scrip master (`stk.json`) and errors without it (a local-cache gap, not a block).
  Evidence: `result-r2-bsedata.json`.

### Updated answers to the three key questions

1. **Does any lib add a NEW route to quarter-grain structured financials or XBRL —
   especially for BSE?**
   - **NSE:** `nsepython.nse_past_results` is a third route to structured 5-quarter
     P&L, but it hits the **same** NSE `results-comparision` endpoint as
     NseIndiaApi — a new *function*, not a new *source*. Also newly surfaced: an
     **NSE shareholding-pattern XBRL** (`SHP_*.xml`) via `NseIndiaApi.shareholding`
     (a shareholding XBRL, not a P&L one).
   - **BSE:** **No.** No tested library returns structured BSE financials or parsed
     BSE XBRL. The only real BSE route (`jugaad-data` `BSELive`) yields **filing
     announcements + PDF attachment links** (incl. the "Result" category), and
     `bsedata` is quote-only. **BSE fundamentals remain PDF-filing-level at best** —
     no wrapper closes the BSE structured-financials/XBRL gap.
2. **Which libs expose shareholding / promoter-pledge data (§16.2, no source today)?**
   - **Shareholding: only `NseIndiaApi.shareholding("INFY")`** — promoter+group,
     public, and employee-trust percentages per quarter (21 quarters), each with a
     shareholding-pattern XBRL link. It is the sole tested source for the §16.2
     shareholding capture kind (NSE, first-party). No other tested lib exposes it.
   - **Promoter pledge: no source found.** The shareholding pattern gives promoter
     *holding %*, not *encumbered/pledged %*; promoter-pledge disclosure is a separate
     filing that **none** of the tested wrappers surface. The pledge half of §16.2
     stays unsourced.
3. **Consolidated capability matrix:** see the table above (lib × {NSE financials,
   NSE XBRL, BSE financials, BSE XBRL, announcements, shareholding, corp actions,
   price}, each marked works / market-wide / blocked / not-supported).

**Rights caveat unchanged.** Every working route above is an NSE or BSE endpoint that
`A05-DECISION-001` holds ToS-**denied** for automated/production use (NSE
scraping-prohibited; BSE all-operations denied). Round 2 widens *what is technically
reachable* (NSE shareholding especially) but changes nothing about rights: adoption is
a rights decision, not a capability gap. BSE structured financials/XBRL are **not even
technically reachable** through these wrappers — only PDF filings are.

### Live calls this round (per library)

| Library | Live calls (round 2) | Notes |
|---|---|---|
| nse / NseIndiaApi | 6 | shareholding, actions, boardMeetings, annual_reports, announcements, + 1 shareholding re-fetch |
| nselib | 4 | corporate_actions, event_calendar (×1 after a client-side param retry), pe_ratio (×2) |
| jugaad-data (BSE) | 2 | BSE result-announcements, BSE all-announcements |
| nsepython | 2 | nse_past_results, nse_events |
| bsedata | 1 | getQuote (verifyScripCode failed locally, no network call) |

All ≤15/lib, ≥2.5s apart, INFY/500209-scoped, no blocks.

Round-2 harnesses: `eval_r2_nselib.py`, `eval_r2_nseindiaapi.py`, `eval_r2_nsepython.py`,
`eval_r2_jugaad_bse.py`, `eval_r2_bsedata.py` (session scratchpad, not committed).

---

## Per-library detail

### nselib — `RuchiTanmay/nselib` (inventory §6 row 6) — Fit H
- Installed in `nselib-venv`; Python 3.13.
- `price_volume_and_deliverable_position_data("INFY")` → 3 rows real INFY data
  (`result-nselib.json`).
- **`financial_results_for_equity`**: the `period` param is a *date window*
  (`1D/1W/1M/3M/6M/1Y`), NOT the reporting cadence — the reporting cadence is
  `fin_period` (default `Quarterly`, also `Half-Yearly`/`Annual`). The original
  failure (`period="Quarterly" not valid`) was a caller error, not a capability gap.
- Bounded re-test (INFY-only, **2 live calls**: master list + INFY XBRL, avoiding the
  library's default loop over *all* companies): master list returned 140 quarterly
  filings incl. an `xbrl` URL column; INFY's XBRL
  (`INDAS_109110_1192961_18072024074507.xml`) parsed to 65 Ind AS fields. Evidence:
  `result-nselib-financials.json`. Source read: `get_func.py::get_financial_results_master`
  (namespace `in-bse-fin`, ~60-key taxonomy).
- **Caveat:** the public `financial_results_for_equity()` iterates XBRL downloads over
  *every* filer in the window — polite/bulk-safe use requires the symbol-filtered
  master + single-XBRL pattern used here, not the stock call.

### nse — `BennyThadikaran/NseIndiaApi` (inventory §6 row 4) — Fit H
- Installed in `NseIndiaApi-venv`; needed `requests` (the earlier import failure was
  only the missing dep). After install: `quote("INFY")` returns full `priceInfo`
  (where nsepython's `nse_eq` was blocked) and `announcements()` (`result-nse.json`).
- Static read of `NSE.py`: `financial_results(segment, period, symbol, from_date, to_date)`
  (symbol-filterable, returns filing meta + XBRL link) and `results_comparison(symbol)`
  (last ~5 quarters revenue/net-profit/EPS, amounts in **Rupees Lakhs**).
- Bounded live test (**2 live calls**): both verified for INFY —
  `result-nse-financials.json`. Cleaner API surface than nselib for the financials use
  case (symbol filter, direct P&L summary), but does **not** auto-parse the full XBRL —
  it hands back the XBRL URL.

### nsepython — `aeron7/nsepython` (inventory §6 row 3) — Fit L–M
- `nse_eq("INFY")` returned **empty** (blocked). `nsefetch` corporate-announcements
  returned **2917 records** with PDF attachment links (`result-nsepython.json`).
- Announcements + PDF links only — **no structured financials, no XBRL**. Would need
  its own quote-path fixing; superseded by NseIndiaApi for quotes.

### jugaad-data — `jugaad-py/jugaad-data` (inventory §6 row 8) — Fit M
- Needed `pandas` (the earlier import failure was only the missing dep). After install:
  `stock_df("INFY", …)` → 3 rows OHLCV **plus delivery qty/%** (`result-jugaad-data.json`).
- Prices/delivery only — **no financials**. Solid for the price slice; not for A-06.

### bsedata — `BseIndiaApi`-family (inventory §6 row 5) — Fit L–M
- `getQuote("500209")` **works** (contrary to the earlier IndexError note; the captured
  `result-bsedata.json` shows success): company name, current/previous prices, 52-wk
  high/low, face value, industry group.
- Live **quote snapshot only** — **no financials, no XBRL**. BSE ToS unretrievable/denied.

### Static-only GitHub repos (inventory §6 rows 7, 9, 10, 11, 12, 14)
Assessed from public GitHub pages; **not installed or run** (rights-denied and/or
require login/paid tokens). Sources: the six repo README pages.

- **row 7 `LaZZy0v0/tijori-finance-mcp`** — MCP wrapping Tijori Finance via Playwright.
  Advertises quarterly P&L/BS/CF, KPIs, segment revenue, shareholding, transcripts.
  **Requires a Tijori account login**; sessions expire. MIT code, but underlying data is
  Tijori's (aggregator ToS; README itself says "personal research only, do not
  redistribute"). ~13 stars, last update Jun 2026. **No XBRL.**
- **row 9 `VishwaGauravIn/screener-scraper-pro`** — TypeScript scraper of Screener.in.
  Advertises quarterly results, P&L, BS, CF, ratios, shareholding. No login/key, but
  **directly scrapes Screener.in** (ToS unreviewed). GPL-3.0, ~19 stars. **No XBRL.**
- **row 10 `Na1neeth/openscreener`** — Python/Playwright scraper of Screener.in;
  similar coverage, exports JSON/DataFrame. MIT, ~15 stars, Py3.10+. **No XBRL**, same
  Screener ToS exposure.
- **row 11 `MrChartist/fii-dii-data`** — FII/DII flows, F&O positioning, sector
  allocation from NSE/NSDL/BSE. **No company financials.** MIT, ~39 stars, active
  (cron-driven). Out of scope for A-06 (flows, not statements).
- **row 12 `Tapetide-hq/nse-bse-indian-stock-market-data-mcp`** — MCP with 34 tools
  incl. quarterly+annual P&L/BS/CF and 326 ratios over ~8,200 stocks. **Requires a
  tapetide.com token / Google OAuth** (aggregator API; free tier exists). MIT code,
  ~61 stars. **No XBRL**; aggregator-derived, rights-undecided.
- **row 14 `thisisamu/fii-dii-analysis`** — Static single-file dashboard of FII/DII
  flows via a CORS proxy to NSE. **No company financials.** MIT, ~1 star, ~3 commits.

---

## Recommendation

**Shortlist (≤3) worth a future production rights decision:**
1. **nselib** — the only tool that returns **parsed Ind AS XBRL** quarter-grain
   financials end-to-end. Highest value for the A-06 gap. Requires the symbol-filtered
   single-XBRL access pattern (not the stock `financial_results_for_equity()` loop) to
   stay polite.
2. **NseIndiaApi (`nse`)** — cleanest first-party surface: symbol-filtered filing +
   XBRL link, plus a ready `results_comparison` 5-quarter P&L summary and working
   quotes. Strong complement/alternative to nselib.
3. *(Conditional)* **jugaad-data** — only if the price/delivery slice is also wanted;
   it does **not** touch the financials gap.

**Drop / do not pursue for A-06:**
- **nsepython** — quote path blocked; announcements-only; superseded by NseIndiaApi.
- **bsedata** — quote snapshot only.
- **All six GitHub repos** — either FII/DII flows (rows 11, 14 — wrong data class) or
  aggregator scrapers/MCPs behind login/paid/ToS walls (rows 7, 9, 10, 12) that provide
  scraped P&L, **never XBRL**, and carry unreviewed Screener/Tijori/Tapetide terms.

**Honest bottom line.** These libraries **do** close the structured-financials gap for
INFY FY25 — but the only two that deliver *actual Ind AS XBRL / structured statements*
(nselib, NseIndiaApi) obtain them from NSE's own corporate-filings endpoints, which are
precisely what `A05-DECISION-001` holds as ToS-prohibited. The aggregator tools that
would sidestep NSE add their own (stricter) ToS and login/paid barriers and still don't
provide XBRL. So the gap is **technically closable but not rights-clear**: the decision
is legal/rights, not technical. Note also that NSE's corporate-filings XBRL is a
**republication of the issuer's BSE/NSE Ind AS filing** — a first-party issuer/regulator
source (the exchange filing itself) may be obtainable without relying on a
scraping-prohibited API, and is worth scoping before any production adoption.

---

## Evidence index (session scratchpad — not committed)
- `scratchpad/lib-eval/result-nselib.json`, `result-nselib-financials.json`
- `scratchpad/lib-eval/result-nse.json`, `result-nse-financials.json`
- `scratchpad/lib-eval/result-nsepython.json`
- `scratchpad/lib-eval/result-jugaad-data.json`
- `scratchpad/lib-eval/result-bsedata.json`
- Harnesses: `eval_nse.py`, `eval_nselib_financials.py`, `eval_nseindiaapi_financials.py`

**Verification status:** Live results are first-party (run this session in isolated
venvs). GitHub repo rows are **unverified** static reads of public README pages — feature
claims are the authors', not tested here. Figures cross-checked against Infosys' published
Q1 FY25 results for plausibility; not independently audited.
