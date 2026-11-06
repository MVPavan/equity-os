# Not capturable by a plain GET (2026-10-28)

This table is deduplicated across the three crawlers. "Existing" marks a surface that repo code already reaches by another method.

## Crawler hazard: GET URLs that change state

| Site | URL | Effect | Evidence |
|---|---|---|---|
| tijori | `/in/watchlist/{id}/rename/{name}` | Renames a watchlist | `watchlist.js`: `$.ajax({url})` with the default method, GET |
| tijori | `/in/watchlist/{id}/add/{company_id}` | Adds a company | `watchlist.js` `addCompany`, GET |
| tijori | `/in/watchlist/create` | Creates a watchlist | `watchlist.js`, GET |
| tijori | `/api/portfolio/{id}/broker/connect` | Can start a broker connection | `/static/react/portfolio/main.js`, coded as a GET |
| tijori | `/api/portfolio/task-status/?acked=true` | Acknowledges a finished portfolio task | `main.js` `fetch(...)`, GET; the query flag changes state |
| tijori | `/api/portfolio/task-status/?timeout=`, `/api/portfolio/refresh-status/?task_id=` | Task polling; read-only semantics uncertain | `main.js`; skipped under the brief's "unsure means do not fetch" rule |
| screener | `/screen/delete/{id}/`, `/watchlist/add/`, `/user/account/delete/` | Mutations exposed as links | Seen as links and forms; never fetched |

A link-following crawler must deny-list `rename`, `add`, `create`, `remove`, `delete`, `connect`, `sync`, `reset`, `refresh`, `mark` and `logout` path words, plus `ack`/`acked`/`mark`/`seen`/`read`-style query keys, on both sites before it issues any GET (full rule: `runbook.md` §1).

## Table

| Site | Surface / URL | Class | Reason |
|---|---|---|---|
| screener | `/user/company/export/{warehouse_id}/` (company Excel) | POST | `formaction` form with CSRF |
| screener | `/api/export/screen/?url_name=&screen_id|sublist_id=` (screen and watchlist CSV) | POST | Existing code fetches the page, then POSTs (S17, S18) |
| screener | `/insights/company/{id}/quarter/?is_consolidated=` | POST-only | 405 on GET for all three crawlers |
| screener | `/announcements/search/{id}/` results | POST | Search submit (the landing page is GET and is in the catalog) |
| screener | `/api/company/{id}/add/{list}/`, `/remove/{list}/` | action | Follow/unfollow |
| screener | `/insights/company/{id}/flag/`, `/concalls/add-{id}/`, `/alerts/add-screen-{id}/` | action | Feedback, add-missing and alert-create flows |
| screener | `/password_change/`, `/user/account/email/`, `/user/account/delete/`, `/login/`, logout | account | Credential, account or session changes |
| screener | `/company/actions/{id}/`, `/wiki/company/{id}/commentary/v2/`, `/notebook/{id}/`, `/alerts/stock-{wid}/`, `/trades/insider-summary-{id}/` | XHR-only | 302 without `X-Requested-With`; the actions modal is existing (S14). In the catalog with redirect references |
| screener | `/ai/`, `/ai/usage/`, `/ai/company/{id}/` | AI | Excluded by brief |
| screener | `/annual-reports/{id}/summary/` | AI | AI summary; the audit saw 200 on GET (S27), but it is excluded. `/concalls/summary/{id}/` is captured since VENDOR-1 Phase 2 (only via the company page's Notes buttons) |
| screener | `/premium/` payment links | payment | Plan page is in the catalog; payment is not |
| screener | `bseindia.com` (AnnPdfOpen, xml-data/corpfiling, HIS_ANN_RPT, bseplus AnnualReport), `nsearchives`/`archives.nseindia.com` | off-host | Filings, annual reports and results PDFs (S21, S29); `/company/source/quarter/...` redirects here |
| screener | crisil.com, icra.in, careratings.com and other rating agencies | off-host | Credit-rating documents |
| screener | issuer IR sites (transcripts, PPT, mp3), youtube, sebi.gov.in, s3/cloudfront | off-host | Concall material and offer documents (S30) |
| screener | concall audio `<audio data-src=...m3u8>` | JS-only | Seen in JS only |
| screener | `cdn-static.screener.in/js/*`, `cdn-media` receipts | off-host | JS is mirrored on `www.screener.in/static/js/` |
| tijori | `excel.tijorifinance.com/company/excel/{id}/{token}/{cons|stand}_{id}.xlsx`, `/portfolio/excel/Upload_Template.xlsx` | off-host | Excel downloads; both scopes are linked even when consolidated tables are absent |
| tijori | `files.tijorifinance.com/...` (AR, ER, IP, CC, other), `files.tijoristack.ai` | off-host | 135 APARINDS filings (T36) |
| tijori | `/account/prefs/{key}/` | POST | Table-preference persistence |
| tijori | `/api/portfolio/analysis/{risk|prod|geog|asset}_breakup/`, `top_holdings/`, `pe_ratio/` | POST | Portfolio analytics |
| tijori | `/api/portfolio/{id}/transactions/get_bsd/` | POST | POST despite its name |
| tijori | `{baseUrl}mark_as_seen/` (`price_alerts/price_alerts.js`; base set by the page) | POST | Marks triggered alerts as seen |
| tijori | portfolio broker connect, sync, reset, refresh, delete, import | action | React portfolio bundle |
| tijori | `/in/watchlist/{id}/remove/` | POST | Watchlist removal |
| tijori | Concall summary modal; `/results/concall-summaries/api/` | AI | "Powered by Claude"; 404 "Invalid result type" |
| tijori | Generate Reports / memory overview; report purchase (Razorpay) | AI / payment | The reports tab itself is GET and is in the catalog |
| tijori | `/accounts/logout/` (POST), `/account/signin`, `/account/signup` | account | Session |
| tijori | twitter, valuepickr, substack and youtube links in `#discussions_and_analysis` | off-host | Third-party discussion |
| tijori | `/us/api/v1/usa/...` | out of scope | US market variant |

## Dropped from the capture spec after live runs (2026-10-30/31, eqos-aa6.22)

Each row never returned a usable page in live runs, so `config/vendor_surface/surfaces.yaml` no longer lists it and nothing requests it. The catalog entry stays as the research record.

| Site | Surface / URL | Class | Reason |
|---|---|---|---|
| screener | `quarter-source-pdf` `/company/source/quarter/{company_id}/{month}/{year}/` | off-host | Every month 302s to `bseindia.com` AnnPdfOpen; redirects are never followed |
| tijori | `company-benchmarking` `/company/{slug}/benchmarking/` | moved | 301 to `/company/{slug}/factors/`, which has no retained reference to build readers from |
| tijori | `market-share-api` `/api/v1/ind/company_market_share_data/{ticker}/` | no parameter | The NSE symbol 404s ("Market share data not available!"); the vendor ticker is absent from the APARINDS island |
| tijori | `index-search-api` `/api/v1/sector/index-search/{q}/` | no parameter | A blank term 404s; any term would be invented, and index ids come from `/in/markets` |
| tijori | `index-metric-data-api` `/api/v1/sector/index-metric-data/{index_id}/{metric}` | no parameter | All 27 widget-field metrics 500; no retained page advertises the metric names |
| tijori | `filter-popular-query-results-api` `/api/filter_queries/popular-query/results/?financial=` | broken | All 22 advertised queries 500; the `filters.js` toggle values were never retained |

## Dropped from the capture spec: not tied to a covered company (2026-10-31, eqos-aa6.26)

Owner directive: fetch only what the covered universe needs. The catalog entry stays as the research record. The Tijori result feeds (`quarterly-results-api`, `upcoming-events-api`) stay, but now send the covered companies' Tijori ids in `company_ids=`; the `quarterly-results`, `upcoming-events` and `whats-new` pages keep only their first page.

| Site | Surface / URL | Class | Reason |
|---|---|---|---|
| tijori | `idea-page` `/ideas-dashboard/{slug}/` | out of scope | Not tied to a covered company: one page per market-wide idea theme (19 advertised) |
| tijori | `idea-card-body` `/ideas-dashboard/{slug}/card-body/` | out of scope | Not tied to a covered company: the card fragment of each idea theme |
