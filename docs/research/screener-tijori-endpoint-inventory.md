# Screener.in + Tijori — Subscriber Endpoint Inventory

Working inventory for the acquisition layer (plan of record:
`screener-tijori-acquisition-plan-of-record.md`; rights boundary:
`A05-DECISION-005`). Everything here was observed live under the owner's
paid accounts; entries carry the observation date. **Status: Tijori
first-pass done (2026-08-24); Screener section pending the owner-session
HAR capture.**

## Tijori Finance (verified live 2026-08-24)

### Auth and logged-in markers

- Auth is a single Django session cookie: `Cookie: sessionid=<value>`.
- Logged-in marker: `GET /` responds `302 → /dashboard/` for an
  authenticated session (anonymous gets the marketing homepage). The
  financials page embeds an `is_auth` json_script island — the adapter
  already gates on it.
- Unknown company slug: `302 → /` (never a 404). Redirect-refusal +
  identity check are mandatory; wrong slugs still return a valid 200 page
  for a *different* company if the slug exists.

### Company search / slug resolution

- `GET /api/v1/ind/company_search/?q=<query>` (session cookie required) —
  the site's autocomplete. Returns
  `[{"name", "slug", "type": "companies"}, …]`; also used by us as the
  authoritative slug resolver. US variant exists:
  `/us/api/v1/usa/company/search/`.
- **Slug scheme is historical-name-based and unguessable** — verified
  examples: HFCL → `himachal-futuristic-communications-limited`, CG Power
  → `crompton-greaves-limited`, Eternal → `zomato-ltd`, but MTAR →
  `mtar-technologies-ltd` ("-ltd" suffix), Laurus → `laurus-labs` (no
  suffix), Thermax → `thermax-limited` ("-limited" suffix). Never derive
  slugs; always resolve via the search API and then verify identity on
  the fetched page.

### Financials page

- `GET /company/<slug>/financials/` (~650KB; read the full body — earlier
  truncated reads silently missed the data islands).
- Django `json_script` islands: `fin_tables_data` (~208KB; table keys
  `qt_c`/`qt_s`/`pl_*_s`/`bs_*`/`cf_*`/`fr_*`/`growth`; each table:
  `report_dates` + label-keyed rows with `value` arrays),
  `company_details`, `is_auth`, `financials_locks`, `plan_details`.
- `company_details` is rich: `company`, `company_id`, `symbol`,
  `shortname`, `slug`, `ind_code`, `is_banking`, `mcap`/`mcap_raw`, `pe`,
  `peg`, plus a `quick_look` block of ~17 forensic flags (contingent
  liabilities, depreciation effect, other income, pledge,
  promoter/retail holding trends, …) with sentences and red/green flags —
  a candidate acquisition surface of its own.

### Verified watchlist identity map (all 10, live 2026-08-24)

| NSE symbol | tijori_slug | tijori company_id |
| --- | --- | --- |
| LAURUSLABS | `laurus-labs` | 19736 |
| MTARTECH | `mtar-technologies-ltd` | 42101 |
| SONACOMS | `sona-blw-precision-forgings-ltd` | 43328 |
| THERMAX | `thermax-limited` | 301 |
| TITAN | `titan-company-limited` | 81 |
| NETWEB | `netweb-technologies-india-ltd` | 55416 |
| HFCL | `himachal-futuristic-communications-limited` | 131 |
| POLYCAB | `polycab-india-ltd` | 5794 |
| CGPOWER | `crompton-greaves-limited` | 63 |
| ETERNAL | `zomato-ltd` | 43813 |

Each verified by parsing the `company_details` island on the slug's
financials page and matching `symbol` to the watchlist NSE symbol
(fail-closed; a first-match body grep is NOT safe — peer widgets carry
other companies' symbols earlier in the page).

### Full company-page surface map (headless owner-session crawl, 2026-08-25)

Company sub-pages: `/company/<slug>/` (overview), `/financials/`,
`/shareholding/`, `/benchmarking/`, `/reports/`.

**Overview page islands** (all Django json_script, one GET, TITAN sizes):
`price_chart` (110KB, ~4,400 daily points ≈ 17y), `intraday_price` (75 pts),
`price_returns` (1d…10y), `price_chart_peers`, `corporate_actions`
(Bonus/Dividend/Rights/Split), `ratios_table` (12), `peers_table_data`,
`ms-charts` (market share), `custom_fin_table` (10 — operational KPIs /
custom financials), `metrics` (25), `company_details_data` (identity, mcap,
PE, quick_look forensic flags), `overview_locks`, `plan_details`,
`is_auth`, `is_banking`, `companyId`.

**Financials page**: `fin_tables_data` (15 tables — fully covered by
`fundamentals tijori-tables`), `financials_locks`, `company_details`,
`peersList`, `metrics`, plus the shared price islands.

**Shareholding page**: data is server-rendered HTML (3 tables;
Overview/Trend/Detailed tabs) — NOT islands; parser would be HTML-table
based. Page also embeds estimate/scenario content (5-year revenue/EBITDA
estimates, scenario probabilities, FY26E–FY30E estimates table, assumptions
and risk, triggers).

**Ancillary JSON APIs called by the pages** (session cookie; all verified
live 2026-08-25): `/api/v1/ind/company_op_metrics/<company_id>/<metric_id>/`
(time series), `/api/v1/ind/fund_flow_analysis_data/<company_id>/`
(sources/uses of funds, 1yr/3yr/...), `/api/v1/ind/balance_sheet_snap_shot/
<company_id>/` (BS snapshot), `/api/v1/ind/cash_flow_waterfall/<company_id>/`,
`/timeline/company/?company_id=<id>&timestamp=0` (events timeline),
`/in/watchlist/company/<id>` (watchlist membership),
`/ideas-dashboard/buyback/card-body/` (ideas fragments).

**Site-level**: `/dashboard/`, `/in/ideas-dashboard/`, `/in/search/` are
thin shells (no data islands); their content loads via fragments.

**Exact sub-tab names per company tab** (in-page anchor nav, verified live
2026-08-25 under premium; owner-confirmed count):

- Overview (11): Custom Ratios `#custom_ratios`, Custom Financials
  `#custom_financials`, Forensics `#forensics`, Market Share `#marketshare`,
  Revenue Mix `#revenuemix` (Product Wise / Location Wise / Operating Profit /
  Asset Break-Up ×2), Operational Metrics `#operationalmetrics`, Peer
  Comparison `#competitors`, Brands `#brands`, Corporate Actions
  `#corporateactions`, Connections `#connections`, Knowledge Base
  `#knowledgebase`; plus unanchored sections Key Ratios, About, Timeline, and
  the owner's own custom financial statement.
- Financials (9): Price `#price`, Growth Table `#growth_table`, Balance Sheet
  `#balance_sheet` (+ Balance Sheet Snapshot / Comparison), Profit & Loss
  `#profit_and_loss`, Cash Flow `#cash_flow`, Cash Flow Analysis
  `#cash_flow_analysis` (+ Fund Flow Analysis / Comparison), Ratios `#ratios`,
  Quarterly Results `#quarterly_results`, Reverse DCF `#reverse_dcf`.
- Shareholding (3): Overview `#overview`, Trend `#trend`, Detailed `#detailed`.
- Benchmarking (2): Financial `#benchmarking-financial`, Business
  `#benchmarking-business`.
- Reports: no sub-nav; report cards with free/paid access flow.

Results section (site-level): `/results/quarterly-results/` (filters: market
cap, sorting, companies, sectors, date range), `/results/upcoming-events/`
(company/date/time/link), `/results/concall-monitor/` (AI concall summaries).

Note: an embedded sample-report modal ("5 Year Revenue & EBITDA Estimates",
scenario tables, "Analyst Watchlist") renders in the DOM of every company
page — it is a global template, not per-tab content.

Priority order for future table/parser coverage (Phase 4): corporate_actions,
ratios_table, custom_fin_table (KPIs), ms-charts, price islands, fund-flow /
BS-snapshot / CF-waterfall APIs, shareholding HTML tables, timeline,
upcoming-events + concall monitor.

## Screener.in — first pass (owner HAR + headless capture, 2026-08-24)

- Auth: single `sessionid` cookie. Logged-in marker candidates observed in
  page HTML: `logout` / `account` strings present when authenticated (exact
  fail-closed assertion string to be pinned in Phase 2 from anonymous-vs-auth
  diff).
- **Everything observed so far is server-rendered plain HTTP** — the
  logged-in dashboard, watchlist, screens, and ratio pages issued no data
  XHRs at all (only analytics beacons to `rybbit.screener.in`). No JS wall.
- From the owner HAR (company page flow): `GET /company/<SYM>/consolidated/`
  (main document); XHR-ish fragments `GET /api/company/<id>/quick_ratios/`,
  `/api/company/<id>/peers/` (HTML fragments), `/api/company/<id>/chart/?q=…`
  (JSON), `/api/company/search/?q=…&v=5&fts=1` (JSON); announcements pages
  `/announcements/{important,recent,search}/<id>/`. NOTE: two distinct
  numeric id namespaces appeared (chart/announcements id ≠ quick_ratios/peers
  id) — resolve the mapping in Phase 2 before trusting either.
- From the headless dashboard capture, subscriber surfaces (all `GET`,
  server-rendered): core watchlist `/watchlist/` + `/watchlist/<id>/` +
  `/watchlist/add/`; custom-ratio builder `/ratios/` → `/ratios/new/`
  (`/columns/` is 404); screens `/screens/`, `/screen/new/`, saved screen
  pages `/screens/<id>/<slug>/`; alerts `/alerts/`; notebook `/notebook/`;
  filings `/filings/`; latest results `/results/latest/`; people `/people/`;
  ratings `/ratings/`; insider trades `/trades/insider-summary-<id>/`;
  account `/user/account/`; premium status `/premium/member/`.
- No sanctioned bulk API/export surface observed yet (the flip condition);
  the `/api/` namespace looks page-support-oriented, not a public API.

Cookie handling for both sites: owner-supplied session cookies live in
`~/.secrets/` (0600), injected at composition root via environment
variable, never committed, logged, or passed to third-party model CLIs.
