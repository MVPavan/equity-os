# Screen export probe — Screener.in and Tijori (live, 2026-10-18)

Research only. Observed live under the owner's paid accounts, with the owner's
authorisation (2026-10-18) to automate screen exports. 14 requests in total (Screener 4, Tijori 10), each
at least 2 s apart, 30 s timeouts, redirects refused, a desktop Chrome
User-Agent. Builds on `screener-tijori-endpoint-inventory.md` and
`vendor-terms-screener-tijori-2026-10.md`. Samples are kept in
`scratchpad/screen-probe/` (gitignored). This note contains no cookie values,
tokens or account identifiers. Screen ids are shown as `<id>`.

## Screener.in

### Saved screens

- `/screens/` lists **popular screens only** ("Popular Stock Screens",
  paginated with `?page=`). It does not list the owner's own screens.
- The owner's screens are under the **"Your screens"** heading on
  `GET /explore/`: **8 saved screens**, each linked as `/screens/<id>/<slug>/`
  (7-digit ids). Slugs: `high-growth-micro-cap`, `growing-stocks`,
  `undervalued`, `new-undervalued-fii-investments`, `new-pe-and-peg-less`,
  `high-growth-40`, `new-stocks-2`, plus one screen named after a person
  (name withheld).

### Export request sequence (verified on `high-growth-micro-cap`)

1. `GET /screens/<id>/<slug>/` with `Cookie: sessionid=…`. Returns 200
   `text/html` (~80 KB) and sets the `csrftoken` cookie. The page has exactly
   one `<form method="POST">` whose action is
   `/api/export/screen/?url_name=screen&screen_id=<id>&slug_name=<slug>`.
   Its only field is a hidden `csrfmiddlewaretoken`.
2. `POST` to that action with `Cookie: sessionid=…; csrftoken=…` (both in one
   header), `Content-Type: application/x-www-form-urlencoded`,
   `Referer: <screen page URL>`, `Origin: https://www.screener.in`, and the
   body `csrfmiddlewaretoken=<form token>`.
   Response: **200 `text/csv`**, 14 397 bytes,
   `Content-Disposition: attachment; filename=<slug>.csv`.

This is the same page-then-POST pattern as the watchlist. The probe reused
`ScreenerSessionSource.fetch_navigation` / `post_form` and the watchlist
module's `Set-Cookie` folding, unchanged. Only `url_name` (`screen` instead of
the watchlist view) and the two extra query keys are different.

### Result

- **Completeness:** the page reports "74 results found: Showing page 1 of 2"
  and shows 50 rows. The export has **74 data rows**, so it covers every result
  page and no `?page=` walk is needed. Robots.txt disallows `?page=` anyway.
- Header row, verbatim (24 columns, every record 24 fields wide):
  `Name, BSE Code, NSE Code, ISIN Code, Industry Group, Industry, Current Price, Market Capitalization, Return on capital employed, Price to Earning, Industry PE, PEG Ratio, Price to book value, Profit after tax latest quarter, Profit after tax, YOY Quarterly profit growth, YOY Quarterly sales growth, Profit growth, Sales growth, Net Profit latest quarter, Profit growth 3Years, Profit growth 5Years, OPM, EPS`
- Columns: 6 fixed identity/classification columns, then the screen's own
  display columns. These match the 19 page columns one to one, but under long
  names (`ROCE %` → `Return on capital employed`) and without units.
- **Identifiers:** ISIN is present on 74 of 74 rows. BSE code is blank on 7
  rows, and NSE code is blank on 32 (BSE-only listings). ISIN is the binding key.

### Limits and gaps

- No row cap was seen at 74 rows. Behaviour on large screens (thousands of
  rows) was not tested.
- The CSV carries no units and no as-of date. Units must come from the page
  header (`Rs.Cr.`, `%`).
- The export is not independently addressable: every export needs a fresh page
  GET for the CSRF cookie and the form token.
- Screener has no API ("we don't provide APIs … use the 'Export' option",
  support article). Export is the sanctioned path. The terms do not address
  scripted use (see the terms note).

## Tijori Finance

### Screener surface

- Robots.txt is `User-agent: * Allow: /`, with no disallows.
- The navigation item "Stock Screener" points to `/filter/popular-queries/`.
  Related pages are `/filter/saved-queries/`, `/filter/public-queries/` and
  `/filter/?qt=advanced|basic`. Queries are run on `/filter/?fq=…&aq=…&columns=…`.
- Saved queries are listed by an XHR from `static/javascript/filters/saved-query.js`:
  `GET /api/filter_queries/search/?owner=true&limit=100&offset=0`. The response
  is JSON `{count, next, previous, results[]}`. Each result carries `id`,
  `name`, `description`, `financial_query`, `alt_query`, `extra_cols` and
  `created_by`.
  **The owner has 0 saved queries** (`count` 0), so no saved query was run and
  none was created. Saved queries are addressed by `id`, but "Run Query" does
  not use the id. It re-submits the stored text as
  `/filter/?fq=<financial_query>&aq=<alt_query>&columns=<extra_cols>`.

### Export

- There is **no server-side export**. The "Export" button is a DataTables
  `excel` button that builds the .xlsx in the browser from data the page
  already holds. It is shown only when the `plan_detail` json_script island is
  `"premium"`, and this account is premium. That client-side export renames
  column 2 to `bsecode` and omits the serial-number and additional-info columns.
- So the page-backing JSON is the export's own data source:
  - `GET /api/filter_queries/advanced_search/?financial=<urlencoded fq>&is_checked=<bool>&whales=<bool>&is_sme=<…>[&columns=<extra cols>][&alternate=<aq>]&source=<…>&query_id=<id>`
    is used for advanced, basic and saved queries.
  - `GET /api/filter_queries/popular-query/results/?<same params>` is used for
    popular queries.
  - Required: `Cookie: sessionid=…` only. The probe sent
    `X-Requested-With: XMLHttpRequest`, as jQuery does. No CSRF token is needed
    for these GETs.
- Response (verified with the popular "Companies Doing Major Expansion" query,
  `capex/Net Block > 0.5 AND Market Capitalization > 500`, through both
  endpoints): **200 `application/json`**, 66 KB, keys
  `alternate_q, columns, data, extra_columns, financial_q, footer_calc, total_results`.
  `total_results` is 236 and `data` holds all 236 rows in one response. Paging
  is done in the browser, so the response has no server-side pagination.
- `columns`, verbatim:
  `name, scripcode, nse symbol, segment, <span>latest</span>Capex<span></span>, <span>latest</span>Mcap<span>Cr</span>, <span>latest</span>Net Block<span>Cr</span>`.
  Metric columns embed the period and unit as HTML (`latest`, `Cr`). Each row
  also carries `slug`. Values are typed (`scripcode` int, metrics float).
- **Identifiers:** `nse symbol` is non-blank on 236 of 236 rows.
  `scripcode` (the BSE code) is `0` on 33 rows. `slug` is present on every
  row. **There is no ISIN.** Rows bind to issuers by NSE symbol, then BSE code,
  with the slug resolved by the existing identity checks.

### Limits and gaps

- The premium copy advertises "Stock Screener – Unlimited queries". Free
  accounts have a monthly query cap (number not stated). No row cap was seen
  at 236 rows. Large result sets were not tested.
- No saved query exists, so automating a saved query means either the owner
  saves one in the UI first, or the stored `financial_query` is read from the
  saved-queries API and replayed. This probe did neither.
- The JSON endpoint is undocumented page plumbing. The terms do not address
  scripted use, and the FAQ says "Public developer APIs are currently limited".
  The parameter names come from `filters.js` and may change without notice.

## Recommended acquisition path, most sanctioned first

| Rank | Vendor | Path | Why |
|---|---|---|---|
| 1 | Screener | Saved screen page GET, then `POST /api/export/screen/?url_name=screen&screen_id=<id>&slug_name=<slug>` | The vendor's own Export button, the vendor's named alternative to an API; CSV of every result with ISIN; same transport as the watchlist acquirer |
| 2 | Tijori | `GET /api/filter_queries/advanced_search/?financial=…` (saved query text taken from `/api/filter_queries/search/?owner=true`) | Page-backing JSON. It feeds the premium Export button, which has no server-side counterpart. Full results in one typed response, but no ISIN |
| 3 | Either | Parse the results-table HTML | Not needed. Screener HTML is paginated (`?page=` is robots-disallowed). Tijori renders the table from the same JSON |

Open points for whoever builds this: test both paths on a large screen to
look for row caps; an issuer-binding rule for Tijori rows that lack an ISIN;
and whether the owner will save Tijori queries in the UI.
