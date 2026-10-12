# Vendor terms: Screener.in and Tijori Finance (research, 2026-10-12)

Method: DWS workspace `equity-os` (id 9a9ee2b7-c972-40d3-b89b-1f2d8acca6a4), captured 2026-10-12. "L" = line number in the `dws read` text of that snapshot. Not legal advice; text vs inference are kept separate.

## Snapshots

| Doc | URL | snapshot_id | Last updated |
|---|---|---|---|
| Screener ToS | https://www.screener.in/guides/terms/ | 65ed909e-e493-4727-9091-7971ac07ebb6 | "Last updated Aug 01, 2018" (L40) |
| Screener Privacy | https://www.screener.in/guides/privacy/ | 50a3f6d0-f38e-4a78-92ed-c69638906152 | "Last updated July 01, 2018" (L40) |
| Screener robots.txt | https://www.screener.in/robots.txt | ff8344ee-f625-40d7-9a14-89f6b950df00 | n/a |
| Screener export help | https://support.screener.in/article/28-export-screen-results | cb9ce357-8700-4e3a-ad89-03ebfb8c75b7 | "Last updated on May 22, 2021" (L56) |
| Screener features | https://www.screener.in/features/ | 0f51f204-fad6-467c-8e3f-cbefca8b0ff8 | none shown |
| Tijori Terms of Use | https://www.tijorifinance.com/terms-of-use | 44266aaf-ee7c-44d1-abb1-3c805fcf0715 | **no date on page** |
| Tijori Privacy | https://www.tijorifinance.com/privacy-policy | ab27e5f6-e8d0-4401-9cfc-7d8564468545 | **no date on page** |
| Tijori FAQ | https://www.tijorifinance.com/faq/ | 6616ca0a-ed59-421b-9531-00f80519e21e | footer "© 2026" (L316) |
| Tijori robots.txt | https://www.tijorifinance.com/robots.txt | 7570ed53-1538-4c65-ad4e-1b02569bdaab | n/a |
| Tijori llms.txt | https://www.tijorifinance.com/llms.txt | fbadf5f6-fc0b-463f-8a21-c946f44fc0e7 | n/a |

Both vendors' legal texts are old or undated; the operative terms may differ from what a logged-in user is shown at signup (not checked: signup-flow/checkout T&Cs, premium page, any in-app terms).

---

## 1. Screener.in (Mittal Analytics Private Limited)

### a. Automated access, scraping, bots, rate limits, APIs
- ToS: **not addressed** — no mention of scraping, bots, crawlers, automated access, or rate limits (checked full text, 107 lines).
- Closest clause (ToS L54): "Permission is granted to use the materials (information or software) on Site for personal, non-commercial transitory viewing only." and L56 "modify or copy the materials;" — a general copy prohibition, not scraping-specific.
- robots.txt (L3-8): "User-agent: *" … "Disallow: /user/*", "Disallow: /*?q=", "Disallow: /*?sort=", "Disallow: /*?limit=", "Disallow: /*?page=", "Disallow: /company/source/quarter/*". Notably, query-string screen URLs (`?q=`) and paginated/sorted results are disallowed for crawlers.
- Export help (L11): "Though we don't provide APIs on Screener, you can use the 'Export' option to download the results in a CSV."

### b. Running saved/custom screens programmatically while logged in
- **Not addressed** in ToS or Privacy. Export help L9 says export is intended for "import[ing] our screen results in Python / Java / R / Pandas or any other script" — so scripted use of the *exported CSV* is contemplated; scripted driving of the website UI is not mentioned.

### c. Storing, caching, retaining downloaded data
- ToS L62: "Upon terminating your viewing of these materials or upon the termination of this license, you must destroy any downloaded materials in your possession whether in electronic or printed format."
- ToS L56: license bars you to "modify or copy the materials" and "'mirror' the materials on any other server" (L60: "transfer the materials to another person or "mirror" the materials on any other server.").
- No retention period stated for user-held data. The license "may be terminated by us at any time" (L62), at which point destroy-downloads applies.
- Privacy policy (L105-111) covers only Screener's retention of *your personal info*, not your retention of their data.

### d. Personal vs commercial, redistribution, internal research tool
- ToS L54: "personal, non-commercial transitory viewing only"; L57: "use the materials for any commercial purpose, or for any public display (commercial or non-commercial)"; L60: no transfer to others/mirroring.
- "Internal research tool": **not addressed**. Whether an internal, non-public, non-commercial research pipeline is "personal" is ambiguous.

### e. Official API / export and limits
- No API ("we don't provide APIs", export help L11).
- Export CSV: "The 'Export' option is available only in the premium. Also, the premium users can add up to 50 columns." (L37). "download a CSV with all the columns and all the results" (L29). Features page L55-57: "Export to Excel … Create your own models."
- Row/day/rate limits: **not addressed** in fetched pages.

### Inference (Screener)
- The ToS is a generic site-use licence: "transitory viewing", destroy-on-termination, no copy/mirror. Read literally it forbids *any* persistent local copy of "materials", which is hard to reconcile with Screener's own premium CSV export — so the clause is likely not enforced against ordinary export users, but there is no text granting retention rights. (Inference; no vendor statement.)
- Export to CSV is the vendor-sanctioned programmatic path; paying for premium and exporting is the lowest-risk way to get data. Scripted navigation/query of the website against robots.txt `?q=` disallow is the weaker position.
- The "destroy downloaded materials on termination" clause conflicts with indefinite retention if the account/licence ends.

---

## 2. Tijori Finance (Tijori Financial Services Private Limited)

### a. Automated access, scraping, bots, rate limits, APIs
- Terms of Use: **not addressed** by name (no "scrape/bot/crawl/automated/rate limit" in text; searched keywords).
- Closest (Terms L125-126, §2): "not to copy, reproduce, recompile, decompile, assemble, disassemble, distribute, publish, display, modify or upload to, create derivative works from, transmit, or in any way exploit any part of the Service."
- robots.txt (L1-2, L16-17, L19-20): "User-agent: *  Allow: /" and explicit Allow for GPTBot, ClaudeBot, Claude-User, PerplexityBot etc.; L31: "# LLM and agent guidance: https://www.tijorifinance.com/llms.txt". llms.txt L12-13 points to the sitemap "rather than crawling navigation" and L15-17 says "Watchlists, portfolios, alerts, saved screens and the corporate-events timeline need a signed-in account".
- FAQ L253-255: "Does Tijori provide APIs or developer access? Public developer APIs are currently limited. Users with enterprise or custom data requirements may contact our support team to discuss available options."

### b. Running saved/custom screens programmatically while logged in
- **Not addressed.** Related quota text (Terms L198, in premium-plan popup copy): "Stock Screener - Unlimited queries" (premium) and "Monthly Limit Exceeded … Unlimited Filter queries" (L204, L229) — implies free accounts have a monthly query cap (exact number not stated in fetched pages).

### c. Storing, caching, retaining downloaded data
- Terms L132-135 (§3): "Any use of this Website or its contents, including copying or storing it or them in whole or part, other than for your own personal, non-commercial use is prohibited without the prior written permission of us."
- No retention period for downloaded data. Privacy policy (L268-277, "Retention of Data") covers only Tijori's handling of *your personal data*.

### d. Personal vs commercial, redistribution, internal tool
- Terms L134-137: "You may not reproduce, publish, transmit, distribute, display, modify, create derivative works from, sell or participate in any sale of or exploit in any way, in whole or in part any of the contents on this Website for any purpose."
- L125-126 also bars "create derivative works from … in any way exploit any part of the Service."
- Internal research tool: **not addressed**; "your own personal, non-commercial use" is the only permitted category.

### e. Official API / export and limits
- FAQ L217-219: "Can I download financial data? Yes. Financial data downloads are available to paid subscribers." (Format/limits not stated.)
- FAQ L255: APIs limited; enterprise/custom arrangements via support.
- Premium plan: "Historic Data of 6000+ Metrics", "Stock Screener - Unlimited queries" (Terms L192, L198).

### Inference (Tijori)
- Terms contain an internal tension: L134 permits storing/copying for "personal, non-commercial use", but L137 ("for any purpose") and L125-126 prohibit derivative works/exploitation. Extracted figures feeding a model/report could be read as "derivative works". Unresolved without vendor clarification.
- robots.txt/llms.txt are permissive to AI crawlers for public pages, which suggests the vendor tolerates reading of public pages; this is not a licence and does not cover logged-in/saved-screen or paid data.
- Safest route: use paid financial-data download for personal use, and email support to ask about (i) scripted screen runs, (ii) retention of figures, (iii) an enterprise/data arrangement.

---

## Risk summary (inference; not legal advice)

| Question | Screener.in | Tijori Finance |
|---|---|---|
| Programmatic screen runs (logged in) | **Medium** — ToS silent; no API; robots disallows `?q=`; CSV export (premium) is the sanctioned automated-friendly path | **Medium** — silent; "exploit in any way" clause; screen queries capped on free tier; no public API |
| 4-quarter retention of downloaded pages/exports | **Medium** — no period stated; "transitory viewing", "mirror" and destroy-on-termination wording argue against persistent copies | **Medium** — storing allowed only for "personal, non-commercial use"; no period stated |
| Indefinite retention of extracted/derived figures | **Medium-High** — destroy downloaded materials on termination; no right to retain; derived-figure retention untouched by text | **High** — "create derivative works from … for any purpose" prohibited; personal-use-only carve-out; internal research tool not covered |

Overall: neither vendor grants a licence suited to a standing internal research pipeline; both are silent on bots/rate limits. Seek written confirmation (support) before building a persistent scraping/retention layer; prefer official exports under a paid plan, and keep figures non-redistributed.
