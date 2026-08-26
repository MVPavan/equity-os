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
for `peers/` and `quick_ratios/` but the **company id** for `chart/` and
`schedules/`; `/api/3/<company_id>/…` and `/api/segments/<company_id>/…` use
the company id. Both must be mapped per watchlist company and asserted per
endpoint; never assume one namespace.

### 3a. Click-driven endpoints (captured 2026-08-26, TITAN, 3 interaction passes)

Every "+" row, tab, toggle, and modal on the company page was clicked with
network recording. Results, with response shapes:

| Control | Request | Response shape |
|---|---|---|
| Quarters / P&L / BS / CF expandable rows (`Sales +`, `Expenses +`, `Other Income +`, `Net Profit +`, `Borrowings +`, `Other Liabilities +`, `Fixed Assets +`, `Other Assets +`, `Cash from Operating/Investing/Financing Activity +`) | `GET /api/company/<company_id>/schedules/?parent=<Row label>&section=<quarters|profit-loss|balance-sheet|cash-flow>&consolidated=` | JSON `{sub_row: {period: "value string"}}`; values are display strings ("3,302", "25.99%") |
| Investors drill-downs (`Promoters +`, `FIIs +`, `DIIs +`, `Government +`, `Public +`, `Others +`) | `GET /api/3/<company_id>/investors/{promoters|foreign_institutions|domestic_institutions|government|public|others}/quarterly/` | JSON `{holder_name: {period: "pct", "setAttributes": {"data-person-url": "/people/<id>/<slug>/"}}}` |
| Investors `Quarterly` / `Yearly` | none — client-side toggle over data already in the page | — |
| Investors `Trades` | **navigates** to `/trades/company-<company_id>/` | page: insider/bulk/block trade tables (Person, Quantity, Avg Price, Value in Rs. Lacs) |
| `Product Segments` (Quarters, P&L) | `GET /api/segments/<company_id>/{quarters|profit-loss}/1/?consolidated=true` | HTML `<table class="data-table">` fragment; `tbody[data-segment-line]` per line: Sales, Sales Growth %, Profit, Profit Growth %, Profit %, Capital Employed, ROCE %; per-segment rows (e.g. Jewellery, Watches & Clocks, eyewear, Others, Unallocated) |
| `Related Party` (P&L) | **navigates** to `/results/rpt/<company_id>/consolidated/` | page: `data-table` of parties (53 for TITAN, "Parent Co." tags) × transaction lines × years; Screener flags it "Experimental new feature" |
| `Corporate actions` (BS) | modal `GET /company/actions/<company_id>/` | HTML: Equity History / Dividend / Bonus / Split tables (Date, Details) |
| Insights `Quarterly` | `GET /insights/company/<company_id>/quarter/?is_consolidated=1` | HTML: KPI rows (e.g. "Jewellery Market Share (India) %") with per-quarter value + source quote + BSE PDF `#page=` link |
| Insights `Yearly` | in page (`data-tab-id="yearly-insights"`) | same shape, annual |
| Documents › Announcements `Recent` / `Important` / `Search` | `GET /announcements/{recent|important}/<company_id>/`; search form `POST /announcements/search/<company_id>/results/` (field `q`) | HTML list; items link to BSE PDFs; `All` → bseindia.com |
| Documents › Annual reports / Credit ratings / Concalls | **inline in page** (no request) | Annual reports: BSE PDF links per year (2012–2026); Credit ratings: CARE/CRISIL/ICRA links; Concalls: per quarter `Transcript` / `PPT` / `REC` links + `AI Summary` modal `GET /concalls/summary/<concall_id>/`; `Add Missing` modal `/concalls/add-<company_id>/` |
| Chart metric tabs (`name="metrics"` button values) | `GET /api/company/<company_id>/chart/?q=<metrics>&days=<N>&consolidated=true` with `days` ∈ 30/180/365/1095/1825/3650/10000 (`Max`) | JSON `{"datasets": [{"metric", "label", "values": [[date, value, {extra}], …]}]}` |
| — `Price` | `q=Price-DMA50-DMA200-Volume` | Price on NSE, 50 DMA, 200 DMA, Volume (with `{"delivery": pct}`) — daily |
| — `PE Ratio` | `q=Price to Earning-Median PE-EPS` | PE (daily), Median PE, TTM EPS (quarterly) |
| — `Sales & Margin` | `q=GPM-OPM-NPM-Quarter Sales` | quarterly, back to 2005 |
| — `EV / EBITDA` | `q=EV Multiple-Median EV Multiple-EBITDA` | daily multiple + quarterly EBITDA |
| — `Price to Book` | `q=Price to book value-Median PBV-Book value` | |
| — `Market Cap / Sales` | `q=Market Cap to Sales-Median Market Cap to Sales-Sales` | |
| Peers `Edit Columns` | navigates to `/user/columns/?next=…` | Manage columns: 374 selectable fields (see `ratio-library.md`); saved via `POST` with `csrfmiddlewaretoken` + `data` |
| Header `Export to Excel` | link on page (per-company XLSX) | not exercised |

### 3b. Schedule body facts (learned in Slice 1)

- **Nested schedules exist.** Some sub-rows carry a reserved key
  `isExpandable` whose value is a string `Company.showSchedule("<Sub-row>", …)`
  (e.g. Other Assets → Trade receivables), i.e. a THIRD level opens from the
  sub-row. Reserved keys seen in schedule bodies: `setAttributes` (dict, e.g.
  `{"class": "strong"}` marks the site's own subtotal rows) and `isExpandable`
  (string). Level-3 schedules are recorded but not acquired yet (follow-up
  bead).
- Reconciliation facts (2026-08-26, TITAN/NETWEB/HFCL): page rows and sub-rows
  are rounded to whole crores independently (±1 per addend); the page rounds
  where the API keeps fractions (0.42 → 0); Fixed Assets page row = Gross
  Block − Accumulated Depreciation; Net Profit and Cash from Operating
  Activity families are restatement/hierarchical mixes, not flat sums.

### 3c. Sub-document facts (learned in Slice 2, 2026-08-26, TITAN/NETWEB/ETERNAL/HFCL)

- **Discovery is page-driven.** Investor buckets come from
  `Company.showShareholders('<bucket>', '<quarterly|yearly>', this)` buttons
  (sets vary: NETWEB has no government/others rows; ETERNAL has no promoters
  row); segments from `Segment.showSegment('<section>', '<type>')` (absent on
  NETWEB, LAURUSLABS, MTARTECH, SONACOMS; only type `'1'` is ever offered —
  `/2/` exists server-side as a geographic split but no page links it);
  Related Party / Corporate actions / Trades from `data-url` attributes (the
  standalone and standalone-only pages link `/results/rpt/<id>/` without the
  `consolidated/` suffix).
- **Investors API** values are 2-dp percent strings; every holder carries
  `setAttributes.data-person-url`; `/yearly/` exists alongside `/quarterly/`.
  Promoters are fully disclosed and sum to the page row (TITAN 52.90, HFCL
  28.29 exact; NETWEB 66.99 vs 66.98 rounding). All other buckets list only
  holders ≥ 1 %, so their sums sit below the page row (TITAN DIIs 8.07 vs
  15.15); `{}` is legitimate when no holder crosses 1 % (TITAN government,
  0.19 %).
- **Segments API selects basis by the VALUE `consolidated=true`** — blank and
  absent are byte-identical and mean standalone (the schedules API uses key
  presence instead). Fragment = one `data-table` with a
  `tbody[data-segment-line]` per line (Sales, Sales Growth %, Profit, Profit
  Growth %, Profit %, Capital Employed, ROCE %); `%` alone renders a blank
  growth cell. Segment Sales do **not** reliably sum to the page Sales row in
  either direction (re-measured across all periods, Slice 2): TITAN omits
  eliminations and exceeds the page by 105–184 per quarter and 70–552 per year;
  ETERNAL matches exactly except Mar/Jun 2024, where its `Less: Intersegment`
  row deducts 17/23 the page's Sales row does not; HFCL matches within ±1
  recently but is 261 short in Mar 2016, where it published four segment lines
  against today's five. Only the **newest** comparable period is dependable:
  every correct capture is at or above the page there, while a standalone body
  against a consolidated page is below on every period (TITAN, −3,114 on the
  newest quarter) — so that, not the aggregate, is the usable basis gate.
  Fragment periods are a **contiguous window** of the page section's labels, not
  a suffix: `quarters` trims the oldest column, `profit-loss` trims the page's
  trailing `TTM`. A standalone-only company queried with `consolidated=true`
  returns a header-only shell (no periods).
- **Related Party** is a modal fragment (no nav, no identity, no basis marker)
  flagged "Experimental new feature"; parties are `tr.strong` header rows with
  optional tags (Parent Co., Subsidiary, Associate, JV, Key Person, Relative);
  year columns vary per company (6–12); line labels repeat with case variants.
  NETWEB's consolidated URL returns an empty table.
- **Corporate actions** tabs vary per company (equityhistory, dividend, bonus,
  split, esops, prefissue); one `<tbody>` per event with year + "Mon DD" and a
  title/detail pair.
- **Peers** fragment rows carry `data-row-company-id`; the requesting company
  is always present with an href that ends in `/consolidated/` only on the
  consolidated warehouse id (identity + basis are assertable from the body).
  Self row is not necessarily first (HFCL, NETWEB: row 3). Column ids are the
  full field names in `th[data-tooltip]`. Standalone lists carry one extra
  peer row.
- **Quick ratios** fragment (`li[data-source="quick-ratio"]`) is the owner's
  Manage-quick_ratios list (51 rows), values differ per basis; the page's
  `#top-ratios` uses the same markup with `data-source="default"`.

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
- **`X-Requested-With: XMLHttpRequest` is load-bearing on the sub-documents**
  (verified live 2026-08-26): without it `/company/actions/<id>/` answers
  **HTTP 302 to the company page** rather than the modal body, and the peers
  fragment differs slightly. The browser sends the header on every company-page
  XHR and on none of its navigations, so a fetcher must send it on the
  schedules / investors / segments / modal / peers / quick-ratios requests and
  **not** on the company page itself.
- An expired cookie yields a **valid anonymous page** (no error). Every fetch
  must assert a positive logged-in marker (Account menu with Profile/Alerts/
  Notebook/Payments/AI Usage; `plausible-event-user=premium` on feed items).
- Outbound document links (`/company/source/quarter/…`, `/trades/insider-summary-…`,
  announcement PDFs) redirect to bseindia.com / nseindia.com — Screener does
  not host filings.
- Analytics endpoints (`/api/script.js`, `/api/track`, `/api/site/tracking-config/…`)
  are page telemetry, not data.

## 7. Screens (explored 2026-08-26)

| Surface | URL | Facts |
|---|---|---|
| Explore | `/explore/` | `Your screens` (owner had 8), Popular themes (6), Popular formulas (3), Price or Volume (5), Quarterly results (4), Valuation Screens (5), Popular stock screens (9), Browse sectors (58 tier-3 industries) — each screen link is `/screens/<id>/<slug>/` |
| Saved screen results | `/screens/<id>/<slug>/` | table with the watchlist ratio columns (plus any custom columns, e.g. All time high, Down %); `?page=N` pagination; `?sort=<field>&order=desc`; the query expression is shown in a `<textarea>`; `Edit Columns` → `/user/columns/?next=…`; **Export** is a `POST` form to `/api/export/screen/?url_name=screen&screen_id=<id>&slug_name=…` (GET returns 405) |
| **Raw query by URL** | `GET /screen/raw/?sort=&order=&source=&query=<expr>&page=N&limit=25|50` | returns `h1` "Query Results" with the same table — arbitrary screens **without saving**; e.g. `query=Market Capitalization > 10000 AND Return on capital employed > 20` → 50 rows/page |
| Query builder | `/screen/new/` → `POST /screen/raw/` | same engine; saving a screen is a separate account mutation (not exercised) |
| Watchlist export | `POST /api/export/screen/?url_name=goto_sublist&sublist_id=<id>` | CSV/XLSX incl. ISIN (per changelog); POST-only (GET 405) |

Query language fields = the 374 names in `ratio-library.md` (e.g.
`Market Capitalization`, `Return on capital employed`, `Sales growth 3Years`).

## 7a. Still not captured

Export POST bodies (need CSRF token + form data), Edit-Columns save flow,
screen create/save, `Search` announcements results, Notebook contents, the
watchlist `Industry` grouping view, Filters panels on Market Pulse feeds.

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
tree is in `industry-classification.md`.

## 9. Rate limiting (observed)

Sequential authenticated GETs at ~0.6 s spacing returned **HTTP 429 after
~40 requests** (crawl of 2026-08-26). The Phase 2 fetcher must treat 429 as
a typed outcome with backoff and cap burst size well below this; never retry
blindly.

## 10. Standalone vs consolidated (decision + observed facts)

**Decision (owner, 2026-08-26): consolidated is the default basis; standalone
is acquired only as an explicit fallback/comparison, and every artifact records
which basis it actually got.** Rationale: group economics is what valuation
and peer comparison use; Tijori's `*_c` tables and the XBRL consolidated gold
set are consolidated; Screener itself links to `/consolidated/` wherever it
exists.

Observed facts:

- URL basis: `/company/<SYMBOL>/consolidated/` vs `/company/<SYMBOL>/`
  (standalone). The consolidated page carries a positive marker
  **"Consolidated Figures"** and per-section **"View Standalone"** links to
  the bare URL; assert the marker, never infer basis from the URL alone.
- Standalone-only companies: Screener links them without `/consolidated/`;
  behaviour of `/consolidated/` for such companies (redirect vs standalone
  content under the consolidated URL) is **unverified** — Slice 0 must test
  with a standalone-only watchlist company (e.g. NETWEB) and record the
  outcome as a typed basis fact.
- **Warehouse id is per basis** (probe of all ten watchlist stocks,
  2026-08-26): e.g. TITAN consolidated `data-warehouse-id=6599273`,
  standalone `1093`; company id (3437) is the same on both. So
  `peers/` and `quick_ratios/` results are basis-scoped by which warehouse
  id you call; config must hold one warehouse id per basis.
- Standalone-only company (NETWEB): `/company/NETWEB/consolidated/` returns
  **HTTP 200 with no basis marker and no warehouse id** — a quiet degenerate
  page, not a redirect or 404; the standalone page has a warehouse id but
  also no marker (no toggle offered). Basis must be established from
  positive markers + warehouse-id presence, never from status or URL.
- XHR flags: `chart/?…&consolidated=true`, `segments/…/?consolidated=true`,
  `insights/…/quarter/?is_consolidated=1`, `results/rpt/<id>/consolidated/`.
- **`schedules/` selects basis by the PRESENCE of the `consolidated` query
  key, not its value** (verified 2026-08-26 against TITAN page totals):
  `consolidated=`, `consolidated=true` and `consolidated=false` all return
  the consolidated schedule (Borrowings sub-rows sum to 30,621 = consolidated
  page row); omitting the key entirely returns standalone (sum 23,009 =
  standalone page row). Row sets differ per basis (standalone Borrowings has
  no "Other Borrowings"). The standalone page's own JS calls the URL without
  the key. Any client must build the URL by basis and reconcile the sub-row
  sum to the page row it expands.
