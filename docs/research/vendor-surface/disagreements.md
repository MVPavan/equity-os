# Disagreements between crawlers (2026-10-28)

Inputs are `out/{opus,sol,astra}` and the shared cache. "Eligible" means the crawler covered a company where the surface appears. All market and account surfaces are eligible to all three crawlers. The consolidator made 7 fresh gateway calls in total, listed in §4.

## 1. Partial coverage: found by fewer crawlers than were eligible

### 1a. Plain misses, confirmed by another crawler's cached 200 body

| Site | Surface (catalog id) | Found by | Missed by | Resolution |
|---|---|---|---|---|
| screener | quick-ratios-api, segments-api, company-announcements, company-sublists-api, company-compare, ratio-search-api, screen-raw, fii-api, hs-search-api, ratio-gallery | opus, astra | sol | Real surfaces: the cached bodies are 200 (sublists returns `[]`). Sol could not read Screener's CDN JavaScript, so it guessed its endpoints from the page controls. |
| screener | company-notebook-modal, stock-alerts-modal, insider-summary, custom-ratios, user-columns, user-quick-ratios, push-notifications, watchlist-manage, changelog, user-public-profile, announcements-user-filters, sectors-filter-api | opus, sol | astra | Real surfaces. Astra recorded the account and settings links as "mutation-controls" or did not follow them. Opus fetched the GETs, all read-only (200, or 302 for the XHR modals). |
| screener | index-page, commodity-page, capsule, pre-listing-company | opus | sol, astra | Real surfaces. Opus fetched the first three; the consolidator fetched pre-listing-company (§4). |
| tijori | chartdata-median-pe-api, universal-search-api, macro-chart-api, sector-ms-chart-api, sector-company-opm-api, filter-field-catalog-api, watchlist-data, site-timeline-more, reports-store, edit-columns | opus | sol, astra | Real surfaces, with opus's cached 200 bodies. Opus mined the per-feature scripts (macro, sector, filters, watchlist, timeline) that the others did not open. Sol listed edit-columns only inside its catch-all "mutation" entry. It is a read-only GET; saving goes through `POST /account/prefs/`. |
| tijori | quarterly-results-api, upcoming-events-api | opus (200), astra (not fetched) | sol | Real surfaces. Opus's page-2 bodies are populated. |
| tijori | financials-popup-chart-api, index-metric-data-api, shareholding-detail-chart-api, portfolio-read-api, portfolio-stock-price-api, portfolio-family-performance-api, portfolio-family-overlap-api, dashboard | sol | opus, astra | The first two and portfolio-family-overlap-api have sol's 200 bodies. shareholding-detail-chart-api and the three portfolio read APIs are script-only templates (catalog `discovery`). The consolidator fetched `/dashboard/` (§4). |
| tijori | financial-statement-compare-api, policy-pages | sol, astra | opus | Real surfaces. compare-api has 200 bodies; the policy pages were seen only as links, which is low value. |
| tijori | llms-txt, filter-public-queries, saved-queries, portfolio-family-summary-api, account-subscription | opus, sol | astra | Real surfaces. Astra listed saved queries and the subscription page under its write controls, without fetching them. |
| tijori | filter-public-queries-api, saved-queries-api, alerts-api, idea-card-body, watchlist-dcf | opus | sol, astra | Real surfaces with opus's cached 200 bodies. Opus recorded each with its landing page; the catalog gives each response its own entry. |
| tijori | filter-popular-queries-api | opus (200), astra (not fetched) | sol | Real surface; opus's body is populated. |

### 1b. Granularity, not misses

- **Opus recorded each company page as one entry** and its section anchors only inside the page's contents prose. On Tijori, that prose omits the following anchors: `#company_timeline_sidepanel`, `#connections`, `#popular_queries`, financials `#price` and `#faqFinancials`, `#faqShareHolding`, and both benchmarking tabs. The presence matrix (§3) shows those anchors on every Tijori overview page that opus fetched, so these are naming gaps, not misses.
- **Astra recorded the Tijori shareholding and benchmarking tabs** as sections only. It fetched both pages, so it is credited with the page entries as well.
- **Sol and astra split statement sections** into consolidated and standalone (sol: `overview`) variants. The catalog keeps one entry per anchor.

### 1c. Missed by all three

- **`balance-sheet-snapshot-api`.** No crawler listed it, but the existing code uses it (T16, `ingest/tijori_analysis_models.py:49`). The consolidator fetched it: 200 JSON, `{status, data[].field_name, data[].data}`.
- **Templates in cached scripts that no crawler listed.** All are never-fetched `discovery` entries in the catalog: `portfolio-broker-summary-api` and `portfolio-family-analytics-api` (portfolio `main.js`), `markets-indices-widget-api` (`markets/markets-indices.js:190`), `filter-popular-query-results-api` (`filters/filters.js:892`). `site-timeline-upcoming` (`timeline/timeline.js`) was seen by opus and not followed. The first merge had also folded sol's `stock_price` and family-performance routes into `portfolio-read-api`; they are separate entries again.
- **`/in/watchlist/company/{id}`.** `docs/research/screener-tijori-endpoint-inventory.md` lists it as an observed watchlist-membership call. It is not referenced in any cached script and no crawler found it. It was **not fetched**, because its effect is unverified and the neighbouring `/add/` and `/rename/` routes mutate on GET. **Unresolved.**

## 2. Contradictions on status or method

| # | Surface | Conflict | Resolution |
|---|---|---|---|
| 1 | screener investors-api | Sol got a 404 on a guessed `/api/company/{id}/shareholders/?category=`. Opus and astra got 200 on `/api/3/{id}/investors/{class}/{period}/`. | Sol's guess was wrong. The real template is in `/static/js/utils.*.js`, which is the same-host mirror of the CDN JavaScript. |
| 2 | screener JavaScript reachability | Sol said Screener's JavaScript was unreachable (CDN). Opus and astra read `/static/js/utils.*.js` through the gateway. | Resolved: the mirror is cached with a 200 (`getUrls()`). Sol's guessed routes are superseded by the templates from utils.js. |
| 3 | tijori company-reports | Sol and astra excluded the reports tab as AI or report generation. Opus fetched it (200). | The tab is a read-only GET. Its only form is the logout POST. Purchase runs through Razorpay checkout JavaScript, and Generate is a button action. The page is capturable; its controls are not. |
| 4 | screener screen-new | Opus fetched it. Sol and astra treated it as a mutation. | The page's only form is `GET /screen/raw/`, so it is a read-only query builder. |
| 5 | screener premium | Opus fetched `/premium/member/`. Sol and astra stopped at the `/premium/` redirect because the link was labelled Payments. | `/premium/member/` is a plan-status page with no forms, so it is read-only. Payment links inside it stay excluded. |
| 6 | screener forecasts | Astra skipped it, citing generation semantics. Opus fetched it (200). | It is a read-only HTML fragment with no forms. It returns 404 for HDFCBANK, which has no forecaster for banks. |
| 7 | tijori op-metrics-api | Sol and astra did not fetch it. Opus did (200). | Read-only, and already used by the existing code (T18). The overview page embeds the metric ids. |
| 8 | tijori fund-flow-api, cash-flow-waterfall-api | Astra got 301 on the slashless URLs. Opus and sol did not list them. | The consolidator fetched the trailing-slash forms: both return 200 JSON (§4). |
| 9 | screener company-consolidated-empty-shell | Opus marked it `ok`; sol and astra marked it `empty`. | This is a terminology difference. The bodies are 200 with section shells and no period columns (NETWEB, ICICIGI, PPEL, LGEINDIA). LGEINDIA is an empty shell too: all five basis-scoped sections have zero period headers. Tijori's LGEINDIA consolidated coverage is separately partial (new-surfaces.md warning 2). |
| 10 | tijori watchlist, alerts, site-timeline, portfolio-family-summary-api | Opus marked them `empty`; sol and astra marked them `ok`. | Both are right: the response shapes are valid and the test account has no content. |
| 11 | tijori search, portfolio, alerts, account-management, plans, features | Sol recorded a 301 only; astra followed it to the 200. | Not a conflict. These are slashless-to-slash redirects. |
| 12 | screener company modals: actions, commentary, notebook, stock alerts, insider summary | All three got 302 on a plain GET. | The actions modal is fetched by the existing code with `X-Requested-With` (`ingest/screener_session.py`). **The other four are unresolved**: the gateway cannot send that header. |
| 13 | screener hs-data-api | Opus got 404; astra did not fetch it. | Resolved by the consolidator: 200 JSON for an 8-digit HS code (`74031100`). The API takes ITC-HS trade codes, not the 10-digit WPI codes that `/api/hs/search/` returns. |
| 14 | tijori market-share-api | Opus got 404 with the NSE symbol. | **Ticker source known; unfetched.** `market-share-chart.js` (line ~43) takes `{ticker}` from the `ms-charts` island's `all_peers[].ticker` (absent from today's APARINDS island) or, when `company_ms` and `ms_locks.historic` hold, from `/api/v1/ind/market_share_peer_companies/{company_id}/{chart_company_id}/` (`data[][1]`). That endpoint is catalogued as `market-share-peer-companies-api` (discovery only). |
| 15 | tijori filter-advanced-search-api | Opus got 500. | Opus used an unknown field name. The existing code drives this endpoint (T24); it was not re-fetched. |

## 3. Content claims checked against the cached bodies

Company-page presence was checked from all cached company pages: 41 Screener views, which include five non-pick pages, and 19 Tijori overviews. Section and anchor ids, and the documents sub-headings, were matched by regex.

**Confirmed:**
- **Screener documents.** The Credit ratings block is absent for ETERNAL and KIRANVYPAR, and Concalls is absent for KIRANVYPAR (opus).
- **Screener insights.** `#insights` is absent for PPEL (sol, astra), and also for the pre-listing page.
- **Screener PPEL heading.** The heading is "Half Yearly Results" on standalone and "Quarterly Results" on the forced consolidated view (sol). The pre-listing EAAA page shows the reverse. The heading is therefore not a reliable periodicity marker.
- **Screener Product Segments.** The control is absent for NETWEB, ANONDITA and CREDITACC (opus).
- **Tijori forensics.** Absent for HDFCLIFE and ICICIGI (opus, astra, sol).
- **Tijori market share.** Present for HDFCBANK, HDFCLIFE, ICICIGI, RELIANCE, APARINDS, AUROPHARMA, HINDUNILVR, TCS, NTPC and ETERNAL. Absent for NETWEB, ANONDITA, GODREJPROP, PPEL, ASIANENE, KIRANVYPAR, CREDITACC and LGEINDIA.
- **Tijori corporate actions.** Absent for ETERNAL, LGEINDIA and PPEL.
- **Tijori operational metrics.** Absent for ANONDITA only.
- **Tijori customers.** Present for APARINDS, NTPC and ASIANENE.
- **Tijori brands.** Present for HDFCBANK, RELIANCE, HINDUNILVR, APARINDS, LGEINDIA and ETERNAL.
- **Tijori SME quarters (opus, corrected).** ANONDITA and PPEL `fin_tables_data.qt_s` each emit 10 quarterly column labels spanning Mar, Jun, Sep and Dec, but coverage is sparse and zero-padded: ANONDITA has values in 4 columns and every Jun and Dec column is all zero; PPEL has values in 2. Opus's "10 populated columns" was wrong. Screener shows Mar and Sep only.

**No contradictions found.** The per-kind tables in the three `notes.md` files agree wherever their company sets overlap.

## 4. Consolidator calls (7 of 40)

| URL | Status | Purpose |
|---|---|---|
| `tijori /api/v1/ind/balance_sheet_snap_shot/4290/` | 200 JSON | 1c |
| `screener /company/id/1286273/consolidated/` | 200 | pre-listing-company |
| `tijori /api/v1/ind/fund_flow_analysis_data/4290/` | 200 JSON | §2 #8 |
| `screener /api/hs/74031100/data/` | 200 JSON | §2 #13 |
| `tijori /api/v1/ind/cash_flow_waterfall/4290/` | 200 JSON | §2 #8 |
| `screener /company/id/1286273/` | 200 | pre-listing standalone variant |
| `tijori /dashboard/` | 200 | dashboard (link-only before) |

## Unresolved

1. The Screener commentary, notebook and stock-alert modals, and the insider-summary page, are XHR-only and cannot be verified through the gateway. Their observed 302 and `Location` are in the catalog `reference` and `snapshots-index.json` (`kind: error`).
2. Tijori `company_market_share_data`: the ticker comes from `market-share-peer-companies-api`, which is unfetched.
3. Tijori `/in/watchlist/company/{id}`: its semantics are unverified, so it was not fetched.
4. Tijori `sector-area-chart-api`: the template is `/api/v1/sector/area-chart/{metric_id}/` (sector page `plot_area_chart_for_metric`); not fetched.
5. Tijori portfolio read APIs: they need a portfolio id, and the test account has none.
6. Tijori `/api/portfolio/task-status/` and `/refresh-status/`: read-only semantics uncertain (`?acked=true` acknowledges a task), so they are deny-listed.
