# Runbook: re-crawl Screener and Tijori subscriber surfaces (draft, 2026-10-28)

This merges the methods of the opus, sol and astra crawls. The catalog of record is `catalog.yaml`, and the reference bodies are listed in `snapshots-index.json`.

## 1. Gateway and rules

- **Run every call through the gateway.** Use `python3 -I scripts/vendor_crawl/fetch.py <crawler-id> <url>` from the repo root. The gateway:
  - allows only `www.screener.in` and `www.tijorifinance.com`;
  - never follows redirects and sends no `X-Requested-With`;
  - serves identical URLs from the shared cache for the current UTC date, `cache/<YYYY-MM-DD>/<site>/`, so a cached body is never older than today;
  - writes `STOP-<site>` on a 403, 429, 503 or login redirect. Stop that site at once when this happens.
- **Start a fresh run.** Run on a UTC date that has no `cache/<date>/` directory yet; a same-day re-run reuses that day's bodies. Remove any `STOP-<site>` only after the cause is understood. For every canary in §4, the gateway's JSON line must show `"cached": false`. A canary served from cache proves nothing about drift: re-run it on a new UTC date.
- **Pacing and method.** Alternate the sites and stay under 350 calls per site. Use GET only.
- **Deny-list before fetching anything.** The brief's rule governs: if you are unsure whether a URL acts, do not fetch it; record it as `not_fetched` with a reason.
  - Path words. Match against path segments, not substrings. Split the path on `/`; a word matches a segment that equals it, starts with `<word>-` or `<word>_`, or ends with `-<word>` or `_<word>`. Never match the `{symbol}` or `{slug}` segment after `/company/` (slugs such as `ask-automotive-ltd` are company names). Words: `logout`, `delete`, `remove`, `add`, `create`, `rename`, `save`, `edit`, `follow`, `unfollow`, `subscribe`, `toggle`, `upgrade`, `payment`, `alert`, `connect`, `sync`, `reset`, `refresh`, `ai`, `flag`, `ask`, `mark`, `share-by-email`.
  - Query parameters. Deny any URL whose query has a key `ack`, `acked`, `mark`, `mark_read`, `mark_as_seen`, `seen`, `read` or `dismiss`, or any deny-list word as a key. The cached scripts hold one such GET: `/api/portfolio/task-status/?acked=true` (portfolio `main.js`).
  - Paths: `/insights/company/{id}/flag/`; `/in/watchlist/company/{id}` (unverified membership call next to routes that mutate on GET); `/api/portfolio/task-status/` and `/api/portfolio/refresh-status/` (task polling whose read-only semantics are uncertain); the AI-summary routes `/annual-reports/{id}/summary/` and Tijori `/results/concall-summaries/`. Screener `/concalls/summary/{id}/` is captured, only at the addresses the company page's own Notes buttons advertise (VENDOR-1 §7, owner order 2026-11-05).
  - Allowed despite a word match (established read-only GETs): `/in/edit-columns/`, `/capsules/{id}/stock-alerts/` (a help fragment with no form). Segment matching already lets `/filter/saved-queries/`, `/alerts/`, `/in/alerts/` and `/api/alerts/` through. Read-only summaries such as `/api/portfolio/family_summary/`, `/api/portfolio/{id}/summary/` and `/api/portfolio/{id}/{broker|mf/broker}/summary/` are not on the list.
  - Tijori watchlist `rename`, `add` and `create` mutate on GET (see `not-capturable.md`).
- **Slash-normalising redirects.** A 301 to the same path with a trailing slash is safe to follow by hand. Never follow a redirect to a login, payment or off-host target.

## 2. Start points

1. Fetch `robots.txt`, `sitemap.xml` and the child sitemaps (Screener: screens, companies, posts, static), plus Tijori `llms.txt`.
2. **Company pages.** Fetch one rich company per site: RELIANCE or APARINDS, plus HDFCBANK as a bank. On Screener, fetch both `/company/{SYM}/` and `/consolidated/`. On Tijori, fetch overview, `financials/`, `shareholding/`, `benchmarking/` and `reports/`.
3. **One company of each kind.** Pick each kind from picks.json: insurer (HDFCLIFE, ICICIGI), NBFC (CREDITACC), standalone-only (NETWEB), SME half-yearly (ANONDITA, PPEL), recent IPO (LGEINDIA), renamed (ETERNAL) and thin (KIRANVYPAR). Diff the section ids and row labels across the kinds.
4. **Hubs.**
   - Screener: `/explore/`, `/screens/`, `/market/`, `/filings/`, `/results/latest/`, `/upcoming-results/`, `/concalls/`, `/annual-reports/`, `/announcements/`, `/actions/*`, `/trades/*`, `/ipo/*`, `/people/`, `/ratings/`, `/hs/` and `/fii/`.
   - Tijori: `/in/markets`, `/in/macro`, `/in/raw-materials`, `/sector/{slug}`, `/in/ideas-dashboard/`, `/results/*`, `/filter/*` and `/in/search/`.
   - Account (read-only): watchlists, alerts, notebook, settings and plan pages.

## 3. Finding hidden endpoints

- **Screener.**
  - The page exposes `data-company-id` and `data-warehouse-id`.
    - `company_id` keys schedules, chart, investors, segments, trades, announcements, forecasts and RPT.
    - `warehouse_id` keys peers, quick_ratios and stock alerts.
  - Controls name their loaders: `Company.showSchedule(parent, section)`, `Company.showShareholders(class, period)`, `Segment.showSegment(...)`, plus `data-url` and `Modal.openInModal` targets.
  - The CDN JavaScript is off-host. Fetch its same-host mirror instead: `https://www.screener.in/static/js/utils.<hash>.js`, taking the hash from the page's `cdn-static` script tag. Its `getUrls()` lists every API template. Do not guess routes; sol's guessed shareholder route returned 404.
- **Tijori.**
  - Most company data is in `<script type="application/json" id=...>` islands (`fin_tables_data`, `company_details_data`, `ratios_table`, `custom_fin_table`, `ms-charts`, `peers_table_data`, `corporate_actions`, `companyId`).
  - The rest comes from per-feature scripts under `/static/javascript/`: `company/overview/price-chart.js`, `company/financials/fin-tables.js`, `company-modal-popup.js`, `flow-analysis.js`, `market-share-chart.js`, `company-timeline.js`, `company-benchmarking.js`, `watchlist/watchlist.js`, `markets/markets-indices.js`, `timeline/timeline.js`, and the macro, sector, filter and results scripts; plus the portfolio bundle at `/static/react/portfolio/main.js` (not under `/static/javascript/`).
  - Check each `$.ajax` call's `type`. A missing `type` means GET.
  - The overview embeds its own `company_op_metrics` URLs, so metric ids never need guessing.
- **Request quirks.**
  - Screener modals (`/company/actions/`, `/wiki/.../commentary/v2/`, `/notebook/{id}/`, `/alerts/stock-{wid}/`) 302 without `X-Requested-With`.
  - Screener `/insights/company/{id}/quarter/` is POST-only.
  - Tijori dates use `MM/DD/YYYY,MM/DD/YYYY`.
  - Tijori `/in/timeline/self/more` needs `timelinetype=self`.
  - The Tijori company timeline pages by the cursor in its trailing rows, starting at `timestamp=0`.
  - Screener `/api/hs/{code}/data/` takes 8-digit HS codes, not the WPI codes that search returns.

## 4. Canary checks (run first after any site change)

All ids are for APARINDS: Screener company 211 and warehouse 6594631; Tijori slug `apar-industries-limited` and company 4290. Each check passes only if its status matches and every marker holds.

| # | URL | Expect |
|---|---|---|
| S1 | `/company/APARINDS/consolidated/` | 200; 11 `<section id>` (`chart analysis peers quarters profit-loss balance-sheet cash-flow ratios insights shareholding documents`); logged in: `a[href='/user/account/']` and `form[action='/logout/']` both present (the subscriber-session proof the existing adapter uses); `data-company-id="211"`, `data-warehouse-id="6594631"` and `data-consolidated="true"` (the consolidated basis; standalone carries warehouse 2446 and no marker); at least 1 `showSchedule(` and at least 1 `showShareholders(`; in each of `#quarters #profit-loss #balance-sheet #cash-flow #ratios`, the data table has at least 1 period `<th>` (`Mon YYYY` or `TTM`), at least 1 body row, every body row has exactly one value `<td>` per period `<th>`, and at least 1 row has every value cell non-blank; `#documents` has h3 Announcements, Annual reports, Credit ratings, Concalls |
| S2 | `/company/NETWEB/consolidated/` | 200; `section#quarters` exists, and its data table has zero period `<th>` (the empty-shell detector still works) |
| S3 | `/company/ANONDITA/` | `#quarters` heading "Half Yearly Results"; period months are only Mar and Sep |
| S4 | `/api/company/211/schedules/?parent={label from an S1 showSchedule button}&section=quarters&consolidated=true` | 200 JSON object with at least 1 key; every value is a non-empty object keyed by period labels (`Mon YYYY`). Anything else, including an error envelope, fails |
| S5 | `/api/3/211/investors/promoters/quarterly/` | 200 JSON with at least 1 holder; every holder is an object keyed by period labels (`Mon YYYY`) beside period fields and metadata (the retained fixture includes `setAttributes`), so an error envelope fails |
| S6 | `/api/company/211/chart/?q=Price-DMA50-DMA200-Volume&days=365&consolidated=true` | 200 JSON; `datasets` holds Price, DMA50, DMA200 and Volume, each with a non-empty `values` array |
| S7 | `/static/js/utils.<hash>.js` | 200; `getUrls` contains `getChartMetric`, `tradeData` and `getSegments` |
| S8 | `/company/actions/211/` with no header | 302 (a 200 would mean the modal's XHR-only protection has changed) |
| T1 | `/company/apar-industries-limited/` | 200; islands parse and their nested payloads are non-empty: `company_details_data` has non-empty `company` and `company_id`; `ratios_table` is a non-empty list, every item with a `name` and a non-empty `value`; `custom_fin_table` is a non-empty list, every item with non-empty `report_dates` and non-empty `data.sub_rows`, each row's `value` a list as long as `report_dates`; every `ms-charts` item has a non-empty `data`; `peers_table_data` is a list that collectively contains a non-empty `columns` and a non-empty `data` (separate objects); `corporate_actions` has at least 1 non-empty list; `companyId` a positive integer; div ids `custom_ratios`, `forensics`, `revenuemix`, `operationalmetrics`, `company_filings`; at least 1 `company_op_metrics/4290/` URL; the `price_chart` island is still absent |
| T2 | `/company/apar-industries-limited/financials/` | `fin_tables_data` has 15 keys including `qt_c`, `qt_s`, `growth`; every table has a non-empty `report_dates` and non-empty `data`, and every statement row's `value` array is non-empty and as long as `report_dates` |
| T3 | `/company/apar-industries-limited/shareholding/` | `#overview`, `#trend` and `#detailed` present; the Overview script's `var chartData` is a non-empty list of `[category label, number]` rows (the 2026-10-28 body has no header row); `var trendData` is a non-empty list whose every series has a non-empty `data` list of point lists; the detailed table has rows |
| T4 | `/api/v1/ind/chartdata/4290/price/` | 200 `{data, status}`; `data` parses as a JSON object whose `eod_price` is a non-empty list |
| T5 | `/api/v1/ind/fund_flow_analysis_data/4290/` (trailing slash) | 200 JSON `{data, status}`; `data` is a non-empty list (not `[]` or `{}`); every item has a non-empty `name` and a non-empty `data` object |
| T6 | `/timeline/company/?company_id=4290&timestamp=0` | 200; at least 1 event row (a row with a non-blank `td.event` and a non-blank `td.content`) plus a cursor |
| T7 | `/results/quarterly-results/api/?page=2&sort_by=latest&mcap=&timeline_type=all&sectors=&company_ids=&daterange={MM/DD/YYYY,MM/DD/YYYY}` | 200; at least 1 result card (`.result_item` with a non-blank `.result_item__header` and `.result_item__body`) |
| T8 | `/` | 302 to `/dashboard/`, which is the logged-in marker. Anything else means the session has expired |

Exact-request acceptance is incomplete until matching responses are retained: the retained canary test is a shape/control test for S4 (another basis), S5, T4 and T6 (another company), T7 (page 1 for page 2), and S8 and T8 (synthetic redirects).

## 5. Record keeping

- **Catalog entries.** Record one entry per URL pattern. Its example URL must be fetched exactly, and its sha256 must come from the gateway. Name fields only; never copy values.
- **Snapshots.** Reference bodies live in `data/raw/vendor-surface/<date>/<site>/` (gitignored), one file per distinct body; section entries point at their parent page body plus an `anchor`. `snapshots-index.json` rows carry `kind`: `response` (200), `error` (non-200, with `status` and any `location`) or `discovery` (the script or page that names a never-fetched or non-200 surface). The 2026-10-28 consolidation used throwaway generators hand-mapped to that crawl's three outputs (not committed); a new crawl consolidates fresh against this catalog and never overwrites an earlier date's store.
- **Diffing.** A full recrawl always repeats the whole §2 navigation and the §3 script-discovery walk. The canaries check only their named surfaces; passing canaries never narrow discovery. Then diff the new catalog's ids and contents against the previous run.

## 6. Scheduled capture

- **One cron line.** The owner's crontab runs the cadence command once a day, after 00:00 UTC (cron reads the machine's local time; any one daily slot works). `EQOS_REPO` is the checkout's root, set in the crontab; the log directory must exist:

  ```
  30 2 * * * cd "$EQOS_REPO" && set -a && . ./.env && set +a && uv run --no-sync fundamentals vendor capture-due >> data/logs/vendor-capture-due.jsonl 2>&1
  ```

  Each run writes one JSON report line (expected, completed, refused, incomplete, stopped sites) and exits 1 when a site is stopped or a request was refused. A second run on the same UTC day does no new work unless a feed shows a new event or an acquisition is unfinished.
- **`STOP-<site>` reset.** A 403, 429, 503 or login redirect writes `data/STOP-<site>` and stops that site for every later run. Remove the file only after a person has diagnosed the cause (session expired, rate limit, site change); the next run resumes the site's due work oldest first.
- **Site lock.** Each command holds one PostgreSQL session advisory lock per site for its whole run. A second command on the same site (an overlapping cron run, or a manual `vendor capture`) refuses that site at start; it is never run in parallel.
