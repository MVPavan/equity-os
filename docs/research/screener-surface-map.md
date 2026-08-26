# Screener.in — Subscriber Surface Map (Phase 2 ground truth)

Captured 2026-08-26 with the owner's Premium session via headless Chromium:
42 pages, every one verified logged-in (Account menu rendered, premium-tagged
feed items). Names below are **verbatim from the site's own markup** (nav
labels, `h1`/`h2`, tab buttons, column headers). Captures live in the session
scratchpad only (private subscriber content, rights decision A05-DECISION-005);
this document is what we keep.

Owner-validated 2026-08-26 ("almost everything looks good"), with one open
question recorded in §8.

## 1. Top navigation

| Menu | Item | URL | Notes |
|---|---|---|---|
| Feed | Feed (Core Watchlist news feed) | `/` | Today / Yesterday announcement items for watchlist companies |
| Feed | Dashboard | `/dash/` | Watchlist snapshot + recent results/announcements; linked from Market Pulse |
| Screens | Stock screens | `/explore/` | §5 |
| Tools ▾ | Create a stock screen | `/screen/new/` | Query builder; submits `POST /screen/raw/` |
| Tools ▾ | Screener AI | `/ai/` | Per-company AI Q&A, wallet-billed (`/ai/usage/`) |
| Tools ▾ | Commodity Prices | `/hs/` | Page title "Product Prices"; HS-code search, 10,000+ commodities, 10 yrs |
| Tools ▾ | Search shareholders | `/people/` | Investor search ("Shareholder name") + Trending Investors |
| Tools ▾ | Company Announcements | `/announcements/` | "Latest Announcements" list + Show More |
| Tools ▾ | Credit rating reports | `/ratings/` | Search by company name |
| Account ▾ | Profile | `/user/account/` | |
| Account ▾ | Alerts | `/alerts/` | Page title "Email preferences" (Account updates) — alerting is email config, not an in-app feed |
| Account ▾ | Notebook | `/notebook/` | + `POST /notebook/export/` |
| Account ▾ | Payments | `/premium/member/` | Premium status + exclusive-features list |
| Account ▾ | AI Usage | `/ai/usage/` | |
| (footer) | What's new? | `/docs/changelog/` | Feature log; e.g. "Added ISIN Codes on CSV Export", "Screener Insights", "Enhanced Corporate Actions Coverage" |

## 2. Market Pulse — `/filings/`

Page `h1` is **Market Pulse**. Its side menu (with live counters) is the hub for
all market-wide feeds:

| Group | Item | URL | Columns / content observed |
|---|---|---|---|
| — | Dashboard | `/dash/` | |
| — | Announcements ("N today") | `/announcements/` | |
| — | Industries Overview ("192 entries") | `/market/` | Industry, No. of Companies, Total Market Cap., Median Market Cap., Median P/E, Wtd. Avg Sales Growth, Wtd. Avg OPM, Wtd. Avg ROCE, Median 1Y Return |
| — | Concalls ("N new") | `/concalls/` | h1 "Latest Concalls"; Company, Pub date, Action; Filters |
| — | Upcoming Concalls | `/concalls/upcoming/` | Company, Date, Time |
| — | Annual Reports | `/annual-reports/` | h1 "Latest Annual Reports"; Filter; very large page (~540KB) |
| — | FII Investment ("Bought N Cr") | `/fii/` | Cumulative FII Net Flow (₹ Cr) chart 1Yr/3Yr/5Yr/7Yr/Max; Sector-wise FII Net Flow: Total AUM, Fortnight change, 1Y flow |
| — | Upcoming Results ("N today") | `/upcoming-results/` | Company, Result date; Filters. (`/results/upcoming/` is a 404 — not the URL) |
| Latest Trades | Bulk Deals | `/trades/bulk/?o=-2` | Company, Person, Date, Type, Value; Filters |
| Latest Trades | Block Deals | `/trades/block/?o=-2` | same shape |
| Latest Trades | SAST Trades | `/trades/sast/?o=-2` | Company, Person name, Date, Type, Percent |
| Latest Trades | Insider Trades | `/trades/insiders/?o=-2` | Company, Name, Date, Type, Value; row detail `/trades/insider-summary-<id>/` **302-redirects to bseindia.com** (BSE blocks headless clients with 403; normal browsers are fine) |
| Corporate Actions | Bonus | `/actions/bonus/?o=-1` | h1 "Bonus Issues"; Company, Ex date, Ratio |
| Corporate Actions | Right | `/actions/right/?o=-1` | h1 "Right Issues"; Company, Ex date, Premium, Ratio |
| Corporate Actions | Split | `/actions/split/?o=-1` | h1 "Stock Splits"; Company, Ex-Date, Old fv, New fv |
| Corporate Actions | Buy Back | `/actions/buyback/?o=-1` | h1 "Stock Buybacks"; Company, Ex date, End date, Offer Type, Max Price, Amount in Cr; Filters |
| Corporate Actions | Dividend | `/actions/dividend/?o=-1` | h1 "Dividends"; Company, Ex date, Div type, Percent; Filters |

The Market Pulse page body itself shows "Latest Trades" and "Corporate Actions"
summaries. `?o=` is the default sort parameter.

## 3. Company page — `/company/<SYMBOL>/consolidated/` and `/company/<SYMBOL>/`

Sub-nav tabs (verbatim): Chart · Analysis · Peers · Quarters · Profit & Loss ·
Balance Sheet · Cash Flow · Ratios · Investors · Documents · Notebook · AI.
Section element ids: `chart analysis peers quarters profit-loss balance-sheet
cash-flow ratios insights shareholding documents` (note `insights` has no tab;
`Investors` tab → `#shareholding`).

| Section | Sub-features (verbatim) | Data path |
|---|---|---|
| Header `#top` | Export to Excel, Follow, website link, BSE: code, NSE: symbol, F&O tag, About + Key Points (Read More), ratio cards, "Add ratio to table" | quick ratios `GET /api/company/<warehouse_id>/quick_ratios/` |
| Chart `#chart` | Ranges 1M 6M 1Yr 3Yr 5Yr 10Yr Max; metric tabs Price (Price on NSE, 50 DMA, 200 DMA, Volume), PE Ratio, Sales & Margin, EV / EBITDA, Price to Book, Market Cap / Sales, More; Alerts | `GET /api/company/<company_id>/chart/?q=Price-DMA50-DMA200-Volume&days=365&consolidated=true` |
| Analysis `#analysis` | Pros / Cons | in-page |
| Peers `#peers` | Peer comparison table, show all, Edit Columns, "Detailed Comparison with:"; industry breadcrumb links | `GET /api/company/<warehouse_id>/peers/`; industry pages `/market/<L1>/<L2>/<L3>/<L4>/` |
| Quarters `#quarters` | Product Segments toggle; expandable rows Sales +, Expenses +, Other Income +, Net Profit +; per-quarter source links `/company/source/quarter/<company_id>/<month>/<year>/` (**redirect to BSE PDF**) | in-page + XHR on expand |
| Profit & Loss `#profit-loss` | Related Party; Product Segments; expandables Sales +, Expenses +, Other Income +, Net Profit + | in-page + XHR on expand |
| Balance Sheet `#balance-sheet` | Corporate actions; expandables Borrowings +, Other Liabilities +, Fixed Assets +, Other Assets + | in-page + XHR on expand |
| Cash Flow `#cash-flow` | expandables Cash from Operating / Investing / Financing Activity + | in-page + XHR on expand |
| Ratios `#ratios` | ratio rows; customizable via Manage quick_ratios / Manage columns | in-page |
| Insights `#insights` | Yearly / Quarterly toggle; Source; Flag error | in-page |
| Investors `#shareholding` | Quarterly / Yearly toggle; Trades tab; drill-downs Promoters +, FIIs +, DIIs +, Government +, Public +, Others + | in-page + XHR on expand |
| Documents `#documents` | Announcements (Recent / Important / Search / All), Annual reports, Credit ratings, Concalls (per-concall AI Summary; Add Missing) | links resolve to BSE/NSE PDFs |
| Notebook | per-company notes | |
| AI | `/ai/company/<company_id>/` — canned prompts (business model, red flags, 3-yr evolution, growth outlook, management commentary, key products table, guidance vs delivery); tiers "Fast + Intelligent" / "Expert Intelligence" | vendor-LLM output |

### Identity: two numeric id namespaces (live-verified on one page)

TITAN carries `data-company-id="3437"` **and** `data-warehouse-id="6599273"`.
The same API path template `/api/company/<id>/…` takes the **warehouse id**
for `peers/` and `quick_ratios/` but the **company id** for `chart/`. Both
must be mapped per watchlist company and asserted per endpoint; never assume
one namespace.

## 4. Watchlist and user configuration

| Surface | Exact name | URL | Notes |
|---|---|---|---|
| Watchlist | Core Watchlist | `/watchlist/<id>/` | Ratio columns: CMP Rs., Mar Cap Rs.Cr., ROCE %, P/E, Ind PE, PEG, CMP / BV, PAT Qtr Rs.Cr., PAT 12M Rs.Cr., Qtr Profit Var %, Qtr Sales Var %, Profit growth %, Sales growth %, NP Qtr Rs.Cr., Profit Var 3Yrs %, Profit Var 5Yrs %; "Industry" grouping toggle; **Export** → `GET /api/export/screen/?url_name=goto_sublist&sublist_id=<id>` (CSV; changelog: includes ISIN codes) |
| Manage stocks | Add companies to Core Watchlist | `/user/stocks/<id>/` | |
| New watchlist | + Create New Watchlist | `/watchlist/add/` | multiple watchlists supported |
| Columns | Manage columns | `/user/columns/` | full ratio library (~160KB page) |
| Quick ratios | Manage quick_ratios | `/user/quick_ratios/` | header ratios (~170KB page) |

## 5. Screens, results, IPO

| Surface | Sections (verbatim `h2`) | URL |
|---|---|---|
| Stock screens | Your screens · Popular themes · Popular formulas · Price or Volume · Quarterly results · Valuation Screens · Popular stock screens · Browse sectors | `/explore/` |
| Query builder | Create a Search Query | `/screen/new/` → `POST /screen/raw/` |
| Latest results | h1 "Latest quarterly results"; Filters; month navigation `?result_update_date__month=M&result_update_date__year=YYYY` | `/results/latest/` |
| IPO | Upcoming IPOs · Recent IPOs · Below IPO Price · Upcoming Rights; columns Name, Subscription Period, Listing Date, M.Cap, Subscription, PE, ROCE | `/ipo/` |
| Industry table | `h1` "<Industry> Companies" with the same ratio columns as the watchlist; Export | `/market/<L1>/<L2>/<L3>/<L4>/` |

## 6. Transport facts

- Everything above is server-rendered HTML over plain HTTPS with the `sessionid`
  cookie; the only XHRs on a company page are the three `/api/company/…` calls.
- An expired cookie yields a **valid anonymous page** (no error). Every fetch
  must assert a positive logged-in marker (Account menu with Profile/Alerts/
  Notebook/Payments/AI Usage; `plausible-event-user=premium` on feed items).
- Outbound document links (`/company/source/quarter/…`, `/trades/insider-summary-…`,
  announcement PDFs) redirect to bseindia.com / nseindia.com — Screener does
  not host filings.
- Analytics endpoints (`/api/script.js`, `/api/track`, `/api/site/tracking-config/…`)
  are page telemetry, not data.

## 7. Not yet captured (click-driven; next discovery round)

Expandable "+" row contents (schedules), Product Segments and Related Party
views, Investors drill-down rows, Documents tab contents, Edit Columns modal,
the watchlist Export CSV body, Filters panels on the feeds, screen query
results pages.

## 8. Open question — industry classification levels

Owner observation: from `/explore/` → Browse sectors, "Agriculture, Commercial
and Construction Vehicles" opens a `/market/…` page whose breadcrumb is
Industries › Industrials › Capital Goods › Agriculture, Commercial and
Construction Vehicles — but that name does not appear in the 192-row
Industries Overview at `/market/`.

**Resolved 2026-08-26 (full crawl):** the classification is a 4-tier tree,
URL `/market/<T1>/<T2>/<T3>/<T4>/` (NSE/AMFI-style Macro Sector › Sector ›
Industry › Basic Industry): 12 › 22 › 58 › 188 nodes. Each surface shows only
one tier:

| Surface | Tier shown | Count |
|---|---|---|
| `/explore/` → Browse sectors | Tier 3 (Industry) | 58 |
| `/market/` Industries Overview | Tier 4 (Basic industry) only | 188 rows (menu counter says 192) |
| Tier 1 / Tier 2 pages | reachable only via breadcrumbs or URL | 12 / 22 |

Every tier page has the same layout: breadcrumb, child-list with company
counts ("Consumer Durables - 355"), and a paginated company table with the
watchlist ratio columns + Export. Owner's example: `IN07` Industrials › `IN0702`
Capital Goods › `IN070202` Agricultural, Commercial & Construction Vehicles
(19 companies) › Tractors 2, Commercial Vehicles 4, Construction Vehicles 6,
Dealers-Commercial Vehicles, Tractors, Construction Vehicles 1. Tier-4 counts
sum to 13, not 19: some companies carry a tier-3 industry with no listed
basic industry, which also explains "192 entries" vs 188 rows. The complete
tree is in `screener-industry-classification.md`.

## 9. Rate limiting (observed)

Sequential authenticated GETs at ~0.6 s spacing returned **HTTP 429 after
~40 requests** (crawl of 2026-08-26). The Phase 2 fetcher must treat 429 as
a typed outcome with backoff and cap burst size well below this; never retry
blindly.
