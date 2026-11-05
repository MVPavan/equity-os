# Vendor-surface crawl brief (epic eqos-aa6)

Goal: find **every** surface that Screener (www.screener.in) and Tijori (www.tijorifinance.com)
show a logged-in subscriber. A surface is a page, a section or tab of a page, an XHR, fragment
or API endpoint, a download, or a document link. Your inventory is cross-checked against the
inventories of other crawlers working independently, so a surface you miss counts as a gap.
Describe surfaces; do not collect data.

## Hard rules
1. **Network.** Run `python3 -I scripts/vendor_crawl/fetch.py <your-crawler-id> <url>` from
   the repo root. This is the only way you may reach the network: no
   curl, wget, browser, or other HTTP client. Each call prints one JSON line. The `body` field
   is a path, and you may read only the bodies printed for your own calls.
2. **Read only GET pages that change nothing.** Never fetch logout links, and never fetch any
   URL that performs an action. That includes anything with logout, delete, remove, add, follow,
   unfollow, subscribe, toggle, save, edit, create, upgrade, payment, alert-create or
   share-by-email in its path or query, and AI or "ask" features. If you are unsure whether a
   URL acts, do not fetch it; record it as `not_fetched` with a reason. Make no POSTs, submit no
   forms, and change no settings.
3. **Load.** The gateway sets the pace. Alternate between Screener and Tijori between calls
   wherever you can, so neither site sees a burst. Your budget is 350 requests per site. If the
   gateway refuses a call or reports a STOP, stop crawling that site at once and record it in
   your notes.
4. **Independence.** Do not read the following:
   - the repo's `equity_os/`, `src/`, `tests/` or `docs/`;
   - `scratchpad/` outside your own output directory, except this brief, `fetch.py` and
     `picks.json`;
   - `scratchpad/vendor-crawl/cache/` and `requests.jsonl`;
   - other crawlers' output.

   Discover everything from the sites themselves: links, `data-*` URL attributes, inline and
   linked JavaScript (it is fine to fetch the site's own JS files to find endpoints), robots.txt,
   sitemaps, help and FAQ pages.
5. **Secrets.** Never print, store or touch cookies or `~/.secrets`.
6. **No numbers.** Do not copy financial values into your output. Name the fields and columns
   only.
7. **Files.** Write only to `scratchpad/vendor-crawl/out/<your-crawler-id>/`. Do not use git or
   bd, and do not edit any other file.

## What to cover
- **Every company in your list, on both sites.** Use `picks.json` for URLs; AUROPHARMA's URLs
  you resolve yourself. Different kinds of company show different sections: banks, insurers,
  NBFCs, SMEs that report half-yearly, standalone-only companies, recent IPOs, renamed and
  thin-coverage companies. Record which sections appear, disappear or change for each kind.
- **On every company page:** every section and tab, the consolidated and standalone views,
  every expandable row or "details" fragment (for example, the schedules behind a line item),
  peers, shareholding, documents (announcements, annual reports, credit ratings, concall
  transcripts, presentations, recordings), exports and downloads, charts and their data
  endpoints, and any other links.
- **Market-wide surfaces:** screens (public and saved), industries and sectors, results,
  calendars and events, IPOs, announcement feeds, people and directors pages, search and
  autocomplete endpoints (GET only), and anything else in the navigation, footer or sitemap.
- **Account surfaces (read-only):** watchlists, saved screens, alerts lists, portfolio pages,
  your own profile, and plan/feature pages. Exports are allowed when they are plain GET
  downloads.
- **Endpoint behaviour, recorded as you go:** formats (HTML, JSON, XLSX, PDF), pagination,
  date-range parameters, how fragments are loaded, and what an unauthenticated or redirected
  response looks like. Record a status, not a body.

## Output (in `scratchpad/vendor-crawl/out/<your-crawler-id>/`)
- **`screener.yaml` and `tijori.yaml`.** Each holds a list of surfaces with these keys:
  - `id` (short kebab-case)
  - `scope` (company | market | account)
  - `url_pattern` (for example `/company/{symbol}/consolidated/`)
  - `example_url` (one exact URL you fetched)
  - `example_sha256` (the sha256 of that fetch, from the gateway)
  - `format`
  - `discovered_via` (link | data-attr | js | sitemap | robots | guess)
  - `contents` (fields, columns and sections, by name)
  - `varies_by` (which company kinds change it, and how)
  - `companies_seen` (a list of symbols)
  - `status` (ok | empty | redirect | not_fetched | error), with a reason when it is not ok
  - `notes`

  The single example per surface is the reference snapshot. Pick its company deliberately: the
  richest one, or the one that shows the variant.
- **`notes.md`**, with three parts:
  1. **The method, written as a runbook.** Write it so that someone can redo the crawl when the
     site changes: where to start, how you found the hidden endpoints, what to check first.
  2. **What differs by company kind.**
  3. **Anomalies, the request counts you used, and anything you could not reach and why.**

Reply with a short summary only: the number of surfaces per site, the five most surprising
finds, and anything you were blocked on.
