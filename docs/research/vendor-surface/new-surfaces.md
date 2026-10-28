# New surfaces: catalog entries with `existing` = `none`, `raw_only` or `partial` (2026-10-28)

There are 155 entries in all:
- Screener: 59 `none`, 5 `raw_only` and 1 `partial`.
- Tijori: 73 `none`, 13 `raw_only` and 4 `partial`.

`(R)` marks `raw_only`, meaning the bytes survive in a retained parent page but no reader parses them. `(R, D7)` marks the eight Tijori overview sections retained only on the D7 path; the ordinary overview CLI discards the HTML. `(P)` marks `partial`: some parts are parsed and the rest are not (see `existing.parts` in the catalog). The ranking reflects usefulness for fundamentals research and is a judgement, not a measurement. Ids match `catalog.yaml`.

## Tier 1: company history and evidence that nothing else captures

| # | Site:id | Why |
|---|---|---|
| 1 | screener:chart-api | Price, DMA, volume, PE, EPS, sales and margin, EV/EBITDA, P/B and Mcap/Sales series up to Max days |
| 2 | tijori:chartdata-valuation-api (+ chartdata-price-api, chartdata-median-pe-api) | Valuation history with median bands. The legacy `price_chart` island is gone, so the APIs are now the only source (T30) |
| 3 | screener:section-documents (R), tijori:overview-company-filings (R, D7) | Listings of annual reports, credit ratings, concalls and announcements. This is the index to primary sources; the linked files are off-host and were not opened |
| 4 | screener:section-insights (R) | Company-specific operating KPIs (e.g. ARPU, AUM, order book, ANDA filings) |
| 5 | tijori:benchmarking-benchmarking-financial (+ tijori:company-benchmarking, tijori:benchmarking-benchmarking-business) | Sector KPI peer tables: CASA, NIM, GNPA, VNB, embedded value, order book, inventory days |
| 6 | tijori:financials-popup-chart-api | Long history per statement row |
| 7 | tijori:capex-api, tijori:debt-api | Capex and debt series with event overlays |
| 8 | tijori:revenue-mix-history-api | Segment and geography mix over time. T14 holds only the latest island |
| 9 | screener:company-announcements | Per-company filing feed: recent, important and searchable |
| 10 | tijori:shareholding-trend (R), tijori:shareholding-overview (P) | Category trend over quarters. The overview breakup chart is parsed; the Overview table and the Trend are not. Raw is kept only on the D8 path |
| 11 | screener:company-trades | Insider, bulk, block and SAST deals for one company |
| 12 | tijori:financial-statement-compare-api | Side-by-side statement comparison, delivered as nested JSON |
| 13 | tijori:shareholding-detail-chart-api | Holder-level history (script template; unsampled) |
| 14 | screener:quarter-source-pdf | Redirect to the exchange results PDF for each quarter; the target is off-host and never fetched. Link extraction exists (RowLink) |
| 15 | screener:forecasts | Forecast table fragment; 404 for banks |
| 16 | screener:commentary-modal | Extended company commentary (XHR-only; unverified) |
| 17 | tijori:company-reports | Existing Stack reports, which may be generated content; purchase and generation are excluded |
| 18 | tijori:financials-reverse-dcf (R) | Shell and defaults only (T26) |
| 19 | tijori:overview-customers (R, D7), tijori:overview-suppliers (R, D7), tijori:overview-brands (R, D7), tijori:overview-connections (R, D7) | Named customers, suppliers, brands and group connections; no reader |
| 20 | tijori:overview-operationalmetrics (P) | The overview embeds the `company_op_metrics` URLs, but nothing discovers them: T18 acquires only manually supplied metric ids |
| 21 | tijori:market-share-api (+ tijori:market-share-peer-companies-api) | Company market-share series. The `{ticker}` comes from `ms-charts` `all_peers` or from the peer-companies endpoint (discovery only, unfetched); the NSE symbol 404s |
| 22 | tijori:overview-quick-view (P) | T13 parses company details and forensic flags only; its Price, Valuation, Capex and Debt charts come from the chart APIs in rows 2 and 7 |
| 23 | screener:company-page (P) | Raw-only part: About, Key Points (with source refs), company name and headline metadata. S01 parses only session, identity and basis evidence |

## Tier 2: market context and event calendars

- **Screener:** results-latest, upcoming-results, concalls-feed, annual-reports-feed, announcements-feed, corporate-actions-feed, trades-feed, ratings-feed, market-pulse, market-overview, market-level, ipo, pre-listing-company, fii-page, fii-api, people-search, person-page, product-prices, commodity-page, hs-search-api, hs-data-api.
- **Tijori:** quarterly-results-api, upcoming-events-api, concall-monitor, sector-page, sector-ms-chart-api, sector-company-opm-api, sector-area-chart-api, index-search-api, index-data-api, index-metric-data-api, markets, markets-indices-widget-api, macro, macro-chart-api, raw-materials, ideas-dashboard, idea-page, idea-card-body.

## Tier 3: definitions, tools and identity (needed for reproducibility, not data)

- **Screener:**
  - Raw-only page sections: section-chart (R), section-peers (R) and section-analysis (R). Section-analysis holds the machine-generated pros/cons.
  - explore, screens-list, screen-page, screen-new, ratio-gallery, ratio-search-api, sectors-filter-api, company-compare, index-page, company-sublists-api.
  - Account settings pages: user-columns, user-quick-ratios, custom-ratios.
- **Tijori:**
  - Search: financial-company-search-api, universal-search-api, search-page.
  - Screening: filter, filter-popular-queries, filter-popular-queries-api, filter-popular-query-results-api, filter-public-queries, filter-public-queries-api, filter-field-catalog-api, saved-queries, saved-queries-api.
  - edit-columns.
  - Raw-only page sections: financials-price (R), overview-knowledgebase (R, D7), overview-popular-queries (R, D7).

## Tier 4: account, static or boilerplate (low research value)

- **Screener:** dashboard-feed, notebook-list, company-notebook-modal, alerts, stock-alerts-modal, user-account, push-notifications, premium, watchlist-manage, announcements-user-filters, insider-summary, capsule, user-public-profile, changelog, features, guides, support, sitemap, robots.
- **Tijori:**
  - Account and portfolio: dashboard, watchlist, watchlist-data, watchlist-dcf, portfolio, portfolio-family-summary-api, portfolio-family-overlap-api, portfolio-read-api, portfolio-stock-price-api, portfolio-broker-summary-api, portfolio-family-analytics-api, portfolio-family-performance-api, alerts, alerts-api, site-timeline-more, site-timeline-upcoming, account-management, account-subscription.
  - AI-generated raw-only part: company-overview (P), whose `memoryOverviewKeyEvents` island is outside the overview section registry (the registry islands and revenuemix are parsed).
  - Off-site links: overview-discussions-and-analysis (R, D7).
  - Static and policy pages: plans, features, faq, whats-new, policy-pages, sitemap, robots, llms-txt, reports-store.
  - Templated FAQ sections: financials-faqfinancials (R), shareholding-faqshareholding (R).

## Data-quality warnings

1. **SME half-yearly filers.**
   - Tijori `fin_tables_data.qt_*` emits 10 quarterly column labels spanning Mar, Jun, Sep and Dec for ANONDITA and PPEL, with sparse, zero-padded coverage: ANONDITA has values in 4 columns and every Jun and Dec column is all zero; PPEL has values in 2. Screener shows Mar and Sep only. Treat zero cells for half-yearly filers as padding, not reported figures.
   - Screener's heading is no guide either. It reads "Half Yearly Results" on PPEL standalone but "Quarterly Results" on the forced consolidated view, and the reverse on the pre-listing EAAA page. Infer periodicity from the column months.
2. **Empty consolidated shells.** `/company/{sym}/consolidated/` returns 200 with no period columns for standalone-only issuers (NETWEB, ICICIGI, PPEL) and for LGEINDIA: all five basis-scoped sections have zero period headers. Tijori's LGEINDIA consolidated coverage is partial: it has consolidated P&L keys but no consolidated BS, CF or quarterly tables. A table being present is not evidence of coverage.
3. **Insurer, bank and NBFC layouts differ between the sites.**

   | Kind | Screener | Tijori |
   |---|---|---|
   | Insurers | Generic Sales/OPM template; insurer KPIs appear only in #insights | Insurance P&L (Operating Profit from Premiums, Income From Investments); no forensics |
   | Banks and NBFCs | Financing template (Revenue, Financing Profit, Financing Margin %, GNPA/NNPA); the ratios table shrinks to ROE % | NBFC CREDITACC on the manufacturing template; banks have their own `is_banking` set |

   Do not cross-check line items between the sites by label.
4. **Mixed basis in Screener #insights.** Some KPI rows carry a "Standalone data" tag while shown on the consolidated page.
5. **AI-generated or boilerplate content:**
   - Screener `#analysis` pros/cons.
   - Screener annual-report and concall AI summaries (excluded).
   - The `/annual-reports/` "optimism" filter.
   - Tijori concall summaries ("Powered by Claude").
   - Tijori `#faq*` sections, which are templated Q&A.
   - The Tijori `peg_sample_report` "5 Year Revenue & EBITDA Estimates" modal, which is the same on every company page and is not company data.
6. **Account-dependent payloads.** Screener `quick_ratios`, peers columns and watchlist columns, and Tijori custom ratios and custom financials, reflect the owner's chosen settings. They are not a fixed field set.
7. **Payload encoding.** Many Tijori `/api/v1` responses carry a JSON string inside `data`. `company_search` serves JSON as `text/html`.
8. **Silent absence.** Sections disappear without a placeholder. A button does not guarantee data: HDFCLIFE's "others quarterly" holder call returns `{}`.
9. **Stale slugs.** Tijori slugs keep old names: HDFCLIFE is `hdfc-standard-life...`, ETERNAL is `zomato-ltd`, ASIANENE is `asian-oilfield-services-limited`. Resolve slugs by search and verify identity on the page.
