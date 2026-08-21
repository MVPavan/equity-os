# Libs-Pipeline Capability — Full Achievable INFY Dataset via Wrapper Libraries

**Target:** Infosys (INFY / BSE 500209). **Authorized by:** `A05-DECISION-004`
(private, personal, non-commercial; polite/low-volume; no redistribution; no
evasion). **Date:** 2026-08-21.

Prior rounds proved individual endpoints work
(`docs/research/data-gathering-tools-evaluation.md`). This round assembles the
**complete** first-party picture: if a production (private) data layer is built
on these libs, exactly what fundamentals data is reachable for one issuer, how
complete, how clean, and with what provenance. All figures below were pulled
**live this session** in the isolated venvs and saved as structured samples
under `scratchpad/lib-eval/infy-full-pull/` (cited per row).

> **Method note.** No aggregators (Screener/Tijori) — first-party libs only.
> Polite bounds held: ≤15 calls/lib, ≥2.6s apart, INFY-scoped, stop-on-block.
> No calls were blocked. Session call totals: **NseIndiaApi 9, nselib 4
> (XBRL downloads), jugaad-data 1.** nsepython / bsedata / `bse` not re-called
> this round (cited from rounds 2–3).

---

## 1. Assembled INFY data inventory (what was actually pulled)

### 1.1 Quarterly financial results — P&L summary (NseIndiaApi)
`results_comparison("INFY")` → **5 quarters**, **75 fields/quarter**, amounts in
**Rupees Lakhs**. Clean per-quarter P&L (revenue, net profit, EPS, current/
deferred tax, depreciation, face value), each row tagged to its own reporting
period. Evidence: `infy-full-pull/nseindiaapi-full.json` → `results_comparison`.

| Quarter | Consol net profit (₹ Cr) | Basic EPS (cont.) |
|---|---|---|
| Q3 FY25 (Oct–Dec 24) | 6,358 | 15.31 |
| Q2 FY25 (Jul–Sep 24) | 6,813 | 16.41 |
| Q1 FY25 (Apr–Jun 24) | 5,768 | 13.90 |
| Q4 FY24 (Jan–Mar 24) | 8,480 | 20.43 |
| Q3 FY24 (Oct–Dec 23) | 6,552 | 15.79 |

### 1.2 Filing history + XBRL links (NseIndiaApi)
`financial_results(symbol=INFY, quarterly, 2023-04-01 … 2025-08-20)` → **16
filings** = **8 quarters** (Q4 FY23 → Q3 FY25), **each in both Standalone and
Consolidated**, **all Audited, all with an Ind AS XBRL link**. This is the
symbol-filtered filing master that feeds the XBRL parse. Evidence:
`nseindiaapi-full.json` → `financial_results_meta`; deduped XBRL URLs in
`infy-full-pull/xbrl-manifest.json`.

> **Freshness caveat (observed).** This session the financials endpoints
> (`results_comparison` and `financial_results`) returned data only **through
> Q3 FY25 (Dec 2024)** — Q4 FY25 and FY26 quarters were absent despite the
> broadcast window extending to Aug 2025, while `shareholding`/`actions`/
> `annual_reports` were current to mid-2026. Treat the financials endpoint as
> possibly lagging/cached; a production pull must verify latest-quarter presence,
> not assume it.

### 1.3 Ind AS XBRL — the authoritative structured source (nselib parse)
Downloaded and parsed the **Consolidated** Ind AS XBRL for 4 quarters via the
`in-bse-fin` taxonomy (`http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin`).
Field density is **not uniform** — it depends on the filing type. Evidence:
`infy-full-pull/nselib-xbrl-deep.json`.

| Quarter (Consolidated) | Distinct XBRL fact tags | Contents |
|---|---|---|
| Q1 FY25 (Apr–Jun 24) | **76** | P&L + EPS + segment metadata |
| Q3 FY25 (Oct–Dec 24) | **77** | P&L + EPS + segment metadata |
| Q2 FY25 (Jul–Sep 24) | **219** | P&L **+ full Balance Sheet + Cash-Flow Statement** |
| Q4 FY24 (Jan–Mar 24) | **227** | P&L **+ full Balance Sheet + Cash-Flow Statement** |

The 151 extra tags in the half-year (Q2) and full-year (Q4) filings are the
complete Ind AS Balance Sheet and Cash-Flow taxonomy — `Assets`,
`BorrowingsCurrent/Noncurrent`, `CashAndCashEquivalents`,
`CashFlowsFromUsedInOperating/Investing/FinancingActivities`, and the full
indirect-method reconciliation (`AdjustmentsFor…`). So the XBRL delivers:
**interim quarters → P&L + EPS + segment (~76 facts); half-year & annual →
complete P&L + BS + CF statement set (~220+ facts).** This is materially richer
and more authoritative than the flat 75-field `results_comparison` summary.

> **XBRL context caveat (important for the parser).** Each fact appears under
> multiple `xbrli:context` refs (current quarter, cumulative YTD, prior-year
> quarter, prior year). Naive first-value extraction — which both nselib's
> built-in `.find()` helper and a generic enumerator do — is **context-blind**
> and can return a YTD/comparative value where the current-quarter value was
> intended (e.g. parsed `ProfitLossForPeriod` for Q3 FY25 = ₹6,822 Cr vs the
> per-quarter `results_comparison` ₹6,358 Cr). A production XBRL parser **must**
> resolve facts by their context ref and the period-instant/duration to map each
> number to the right column. The **field enumeration** above is reliable; the
> **naive per-fact values are not** until context-bound.

### 1.4 Shareholding pattern (NseIndiaApi)
`shareholding("INFY")` → **21 quarters**, **33 fields/row**, each with a
shareholding-pattern XBRL link (`SHP_*.xml`). Top-level breakdown: **promoter +
group / public / employee-trust** %. Evidence: `nseindiaapi-full.json` →
`shareholding`.

| As of | Promoter+grp % | Public % | Emp-trust % |
|---|---|---|---|
| 30-Jun-2026 | 13.82 | 85.97 | 0.21 |
| 31-Mar-2026 | 14.38 | 85.38 | 0.23 |
| 31-Dec-2025 | 14.52 | 85.24 | 0.24 |

- **No promoter-pledge / encumbrance field** (`has_pledge_field = False`).
- **FII/DII split is not in the top-level fields** — only promoter/public/
  emp-trust. A finer FII/DII/government/public breakdown requires **parsing the
  linked `SHP_*.xml`** (not done this round), not the summary rows.

### 1.5 Corporate actions (NseIndiaApi)
`actions("INFY")` → **20** structured actions with ex/record dates: e.g.
`Dividend – Rs 25 Per Share` (ex 10-Jun-2026), `Buy Back` (14-Nov-2025),
`Interim Dividend – Rs 23 Per Share` (27-Oct-2025). Evidence: `nseindiaapi-full.json` → `actions`.

### 1.6 Board meetings (NseIndiaApi)
`boardMeetings("INFY", FY24–FY25)` → **19** meetings with date, purpose, and an
XBRL prior-intimation attachment (results-approval meetings identifiable by
`bm_purpose`/`bm_desc`). Evidence: `nseindiaapi-full.json` → `boardMeetings`.

### 1.7 Corporate announcements (NseIndiaApi)
`announcements(symbol=INFY, 2025-05-01 … 2025-08-20)` → **84 rows**, **20
fields/row**, each with a **PDF attachment URL**, a `hasXbrl` flag, and a
`desc` category (e.g. `Updates`, `Copy of Newspaper Publication`). Symbol- and
date-filtered server-side; results-only filtering is by `desc`/category
client-side. Content is **PDF links, not parsed text**. Evidence:
`nseindiaapi-full.json` → `announcements`.

### 1.8 Annual reports (NseIndiaApi)
`annual_reports("INFY")` → **17 years** of AR PDF links with file sizes.
Evidence: `nseindiaapi-full.json` → `annual_reports`.

### 1.9 Price / OHLCV (jugaad-data + NseIndiaApi)
- `jugaad_data.nse.stock_df("INFY", …)` → daily **OHLCV + delivery qty/%**,
  **15 columns** (OPEN/HIGH/LOW/CLOSE/VWAP/VOLUME/VALUE/NO OF TRADES/DELIVERY
  QTY/DELIVERY %/…). Reliable historical series. Evidence:
  `infy-full-pull/jugaad-price.json`.
- `NseIndiaApi.quote("INFY")` → snapshot with `orderBook`, `tradeInfo`,
  `priceInfo` (52-wk high/low, daily/annual volatility, price band, tick size),
  `secInfo`. Intraday LTP/open/close fields populate only during a live market
  session (empty when market closed).

---

## 2. Pipeline-readiness table (per data type)

Legend: **COMPLETE** = fully reachable & structured; **PARTIAL** = reachable but
summary-level or needs extra parse; **MISSING** = not reachable via these libs.

| Data type | Readiness | Best lib | Refresh cadence | Provenance / quality caveat |
|---|---|---|---|---|
| Quarterly P&L (summary) | **COMPLETE** | NseIndiaApi `results_comparison` | Quarterly (≈4×/yr, ~1 day post board meeting) | Derived NSE summary (Lakhs), 5 qtrs only; cross-check vs XBRL. Freshness lag observed (see §1.2). |
| Full P&L + BS + CF (statement set) | **COMPLETE** (authoritative) | nselib XBRL parse (links via NseIndiaApi) | Quarterly; **BS+CF only in H1 & FY filings** | Issuer's filed Ind AS XBRL — source of record. Interim qtrs = P&L only (~76 facts); H1/FY = full set (~220+). **Context-aware parsing required** (§1.3). |
| Shareholding (holdings) | **COMPLETE** | NseIndiaApi `shareholding` | Quarterly | Promoter/public/emp-trust %, 21 qtrs, + SHP XBRL link. |
| Shareholding (FII/DII split, pledge) | **PARTIAL / MISSING** | (parse `SHP_*.xml`) / — | Quarterly | FII/DII needs the SHP-XBRL parse; **promoter pledge has no field in any lib**. |
| Corporate actions (dividends/buyback) | **COMPLETE** | NseIndiaApi `actions` | Event-driven | Structured, ex/record dates. |
| Board meetings | **COMPLETE** | NseIndiaApi `boardMeetings` | Event-driven | Date/purpose + XBRL intimation link. |
| Announcements / filings | **COMPLETE (as PDF links)** | NseIndiaApi `announcements` | Daily / event-driven | Metadata + **PDF URLs** — content needs the PDF pipeline. |
| Annual reports | **COMPLETE (as PDF links)** | NseIndiaApi `annual_reports` | Annual | 17 yrs of PDF links; content needs PDF pipeline. |
| Price / OHLCV | **COMPLETE** | jugaad-data `stock_df` (+ NseIndiaApi `quote` snapshot) | Daily / intraday | OHLCV + delivery; quote intraday fields market-hours only. |
| Management guidance / commentary / transcript / notes narrative | **MISSING** | — (PDF/transcript pipeline) | Quarterly | Not in any XBRL/structured lib — qualitative, PDF/audio only. |
| BSE structured financials / BSE Ind AS XBRL | **PARTIAL / MISSING** | `bse` summary; jugaad `BSELive` PDFs | Quarterly | `bse.resultsSnapshot` = ~6 summary lines, latest ~2 qtrs; **no BSE financial XBRL** (rounds 2–3). NSE XBRL is the structured route. |

---

## 3. End-to-end verdict

### Best single lib-stack for an INFY production (private) pull
**Three first-party NSE libs, no aggregators:**
1. **NseIndiaApi (`nse`) — the spine.** One clean symbol-filtered surface for
   P&L summary, filing master + XBRL links, shareholding, corporate actions,
   board meetings, announcements, annual reports, and quote metadata.
2. **nselib — the XBRL parser.** Turns the filing XBRL links into the
   authoritative Ind AS fact set (full P&L, and BS+CF for H1/FY filings) via the
   `in-bse-fin` taxonomy. This is the highest-value structured source.
3. **jugaad-data — price/OHLCV history** (delivery-adjusted).

`nsepython` (announcements/duplicate P&L route, quote blocked), `bsedata`/`bse`
(BSE quote + thin summary), and jugaad's `BSELive` (BSE PDF announcements) add
nothing the NSE stack doesn't cover better — except BSE-specific coverage, which
remains PDF/summary-level with **no BSE financial XBRL**.

### What the libs-pipeline gives you end-to-end for one company
A private pipeline on this stack yields, first-party and largely structured:
**8 quarters of filing history with authoritative Ind AS XBRL** (full P&L every
quarter; complete Balance Sheet + Cash-Flow every half-year and year-end),
a **5-quarter clean P&L summary**, **21 quarters of shareholding**, **all
dividends/buybacks and board-meeting dates**, the **full announcements &
annual-report filing stream (as PDF links)**, and **daily OHLCV + delivery**.
For quantitative fundamentals of one issuer, the libs can be the **primary
structured-data source** — provenance is the issuer's own regulatory XBRL, which
beats any aggregator restatement.

### What still requires the PDF / transcript pipeline
The libs give **numbers and filing pointers, not narrative**. Still out of reach
structurally and needing the PDF/transcript layer:
- **Management guidance & outlook** (revenue-growth/margin guidance) — not in XBRL.
- **Earnings-call transcript & MD&A commentary** — audio/PDF only.
- **Segment commentary and notes-to-accounts narrative** — XBRL carries segment
  *numbers* but not the qualitative notes.
- **Press-release qualitative content** — the announcement stream is PDF links only.
- **Promoter pledge / encumbrance** — a separate disclosure no wrapper surfaces.
- **BSE-side full statements / BSE Ind AS XBRL** — PDF filings at best.
- **FII/DII granular split** — needs the linked SHP XBRL parsed (not the summary).

**One-line verdict.** Yes — for INFY these first-party NSE libs (NseIndiaApi +
nselib XBRL + jugaad-data) can be the **primary structured-data source** for
quantitative fundamentals, prices, shareholding, actions and the filing index,
with the **PDF/transcript pipeline filling the narrative/guidance layer** the
XBRL and structured endpoints cannot provide — subject to context-aware XBRL
parsing and a latest-quarter freshness check, and within the private/
non-commercial `A05-DECISION-004` boundary.

---

## Evidence index (session scratchpad — not committed)
- `scratchpad/lib-eval/infy-full-pull/nseindiaapi-full.json` — all NseIndiaApi captures
- `scratchpad/lib-eval/infy-full-pull/xbrl-manifest.json` — per-quarter XBRL URLs
- `scratchpad/lib-eval/infy-full-pull/nselib-xbrl-deep.json` — 4-quarter XBRL fact enumeration
- `scratchpad/lib-eval/infy-full-pull/jugaad-price.json` — OHLCV + delivery sample
- Harnesses: `full_nseindiaapi.py`, `full_nselib_xbrl.py` (session scratchpad)

**Verification status.** Live first-party pulls this session in isolated venvs.
XBRL field counts are exact element enumerations; naive per-fact values are
context-unbound (see §1.3). Figures cross-checked against Infosys published
results for plausibility, not independently audited.
