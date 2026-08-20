# crawl4AI vs NSE/BSE — INFY FY25 Structured Financials Evaluation

**Bead:** eqos-4jb · **Authorized by:** `A05-DECISION-003` (record digest
`sha256:756c4efbf2cab3dac0606d99f3f402793ee5d64dc972d7eedc5ac5e15ca10d1a`) —
extends `A05-DECISION-002`; one-time, bounded, private evaluation-only carve-out.
**Date:** 2026-08-20 · **Target slice:** Infosys (INFY / BSE 500209) FY25 quarters.
**Comparison baseline:** `docs/research/data-gathering-tools-evaluation.md` (wrapper
libraries, bead eqos-cc5).

> **Scope / rights reminder (non-negotiable).** This is a private, one-time
> technical evaluation. It does **not** lift the `CHN-01` (NSE) / `CHN-02` (BSE)
> decided-DENY dispositions of `A05-DECISION-001`. NSE's terms of use expressly
> prohibit systematic/automated collection including scraping; BSE terms are
> unreviewed. **Even where crawl4AI technically works (it does, for BSE), production,
> standing, scheduled, or bulk use remains HELD/DENY under `A05-DECISION-001`.**
> Nothing here authorizes production adoption. No anti-bot evasion was used.

---

## 1. Install / setup result

| Item | Result |
|---|---|
| Install method | Dedicated `uv` venv (Python 3.12) under session `scratchpad/crawl4ai-eval/` (Docker fallback per authorization — venv path chosen; nothing into repo or system Python) |
| crawl4AI version | **0.9.2** (PyPI, `unclecode/crawl4ai`) |
| Headless browser | Required (Playwright). `playwright install chromium` → **Chrome Headless Shell 151.0.7922.34** installed cleanly |
| Smoke test | `https://example.com/` → `success=True status=200`, harness confirmed working before spending fetch budget |
| Config | Normal Chrome desktop user-agent, `headless=True`, `cache_mode=BYPASS`, `wait_until=networkidle`. **NO** stealth/undetected mode, proxy, CAPTCHA solver, or fingerprint spoofing |

Install verdict: **crawl4AI installs and runs cleanly in an isolated venv; a real
Chromium browser is mandatory and installed without issue.**

## 2. robots.txt findings

- **NSE** (`https://www.nseindia.com/robots.txt`, HTTP 200, 96 bytes — a real robots file):
  ```
  User-agent: *
  Allow: /
  Disallow: /market-data-test
  Sitemap: https://www.nseindia.com/sitemap.xml
  ```
  Every path touched (`/get-quotes/...`, `/companies-listing/...`, `/api/...`) is
  **robots-allowed**; `/market-data-test` (not touched) is the only disallow.
- **BSE** (`https://www.bseindia.com/robots.txt`, HTTP 200, 13,850 bytes): **not a
  real robots.txt** — the server returns the Angular SPA HTML shell for the
  `/robots.txt` route. BSE serves **no robots directives at all**; no disallow
  covers the paths touched (`/stock-share-price/...`, `/corporates/...`,
  `/XBRLFILES/...`). (The SPA-shell-for-any-route behavior is itself the first
  signal that BSE is a heavily JS-rendered single-page app.)

## 3. Per-site, per-fetch results

**Total fetches: NSE 3, BSE 5 = 8** (≤10 total, ≤5/site, sequential, ≥3.2s apart).
Samples saved (<100KB each) under `scratchpad/crawl4ai-eval/*.html|*.md`.

### NSE (3 fetches)

| # | URL | HTTP | Rendered? | Data obtained | Verdict |
|---|---|---|---|---|---|
| 1 | `/get-quotes/equity?symbol=INFY` | **fail (None)** | No — 0 bytes | none | **Akamai block** — navigation died on the Akamai `ACS-GOTO` bot challenge; `success=False`, empty HTML |
| 2 | `/companies-listing/corporate-filings-financial-results` | 200 | Shell only | **none** | **Empty SPA shell** — 9MB of page chrome/nav rendered, correct `<title>`, but grep for `Infosys`/`INFY`, any financial number, and any real `.xml`/XBRL filing link → **zero**. The data grid (XHR-driven) did not populate. Not INFY-filtered anyway |
| 3 | `/api/corporate-financial-results?index=equities&symbol=INFY` | 404 | JSON error | none | Reachable but `"Resource not found"` (param error; the wrapper libs pass `from_date/to_date/period`). crawl4AI's own detector also flagged it as a minimal-content shell |

**NSE net: NO usable INFY financials or XBRL.** The quote page is hard-blocked by
Akamai; the results listing returns an empty JS shell. Same wall the empty-shell
paths hit in the library eval (`nsepython`'s blocked `nse_eq`).

### BSE (5 fetches)

| # | URL | HTTP | Rendered? | Data obtained | Verdict |
|---|---|---|---|---|---|
| 1 | `/stock-share-price/infosys-ltd/infy/500209/` | 200 | **Yes** | company page + P&L widgets | Full page rendered (title `Infosys Ltd Live Stock Price…`) |
| 2 | `/stock-share-price/infosys-ltd/infy/500209/financials-results/` | 200 | **Yes** | **quarter-grain P&L, 15 line items × 5 quarters + annual** | **HIT** — see §4. Real numbers rendered from the SPA's in-page XHRs |
| 3 | `https://api.bseindia.com/BseIndiaAPI/api/ComprsvResults/w?...` | 301 | Access Denied | none | **Akamai block** — direct top-level fetch of the data API → `"Access Denied" Reference #`. (Yet the same API succeeds *inside* the page as a same-origin XHR — see §5) |
| 4 | `/corporates/Comp_Results?Code=500209` | 200 | **Yes** | **filing index: FY25 quarters + direct Ind AS XBRL `.xml` links** | **HIT** — server-rendered aspx, not blocked. Rows for Mar-25, Dec-24, Sep-24 (Standalone & Consolidated) each with an XBRL link |
| 5 | `/XBRLFILES/FourOneUploadDocument/Main_Ind_As_500209_1612025193639.xml` | 200 | **Yes** | **real Ind AS XBRL, Q3 FY25 consolidated** | **HIT** — 437KB, namespace `in-bse-fin`, 742 tagged facts. Downloaded and parsed (see §4) |

**BSE net: YES — full quarter-grain financials AND first-party Ind AS XBRL obtained.**

## 4. Data actually obtained (BSE)

**(a) Rendered quarter-grain P&L** — BSE financials-results page (fetch 2), `in Cr.`,
standalone default (consolidated one click away). Default window = latest 5 quarters
(**Jun-25 → Jun-26**, i.e. Q1 FY26–Q1 FY27) + annual **FY 25-26**:

| Line (₹ Cr) | Jun-26 | Mar-26 | Dec-25 | Sep-25 | Jun-25 | FY25-26 |
|---|---|---|---|---|---|---|
| Revenue | 39,957 | 38,641 | 37,996 | 36,907 | 35,275 | 1,48,819 |
| Total Income | 40,831 | 39,704 | 40,273 | 39,175 | 36,157 | 1,55,310 |
| PBT | 10,161 | 9,956 | 9,671 | 10,469 | 8,660 | 38,757 |
| Net Profit | 7,249 | 7,975 | 7,363 | 7,759 | 6,114 | 29,211 |
| EPS | 17.87 | 19.67 | 17.85 | 18.68 | 14.72 | 70.87 |

(Full 15-row taxonomy — Other Income, Expenditure, Interest, PBDT, Depreciation,
Tax, Equity, CEPS, OPM%, NPM% — plus a FY22–FY26 annual-trends table, all rendered.)

> **FY25-quarter nuance (accuracy).** Because today is 2026-08, the *default* 5-quarter
> window shows **FY26** quarters, not the FY25 quarters (Jun-24…Mar-25). **FY25 annual**
> is present in the annual-trends table; the **FY25 quarters** are one link away via the
> "Prior Period" page (fetch 4), which crawl4AI reached and rendered in full.

**(b) FY25 filing index with XBRL links** — `/corporates/Comp_Results?Code=500209`
(fetch 4) lists FY25 rows with direct Ind AS XBRL `.xml` URLs, e.g.:
- Consolidated **Mar-25** → `/XBRLFILES/IFIndasUploadDocument/Integrated_Finance_Ind_As_500209_1062025192516.xml`
- Standalone/Consolidated **Dec-24** → `/XBRLFILES/FourOneUploadDocument/Main_Ind_As_500209_1612025193816.xml` / `..._1612025193639.xml`
- Consolidated **Sep-24** → `/XBRLFILES/FourOneUploadDocument/Main_Ind_As_500209_17102024194837.xml`

**(c) Real Ind AS XBRL downloaded** — fetch 5 pulled the **Q3 FY25 (Dec-24)
consolidated** file. Namespace `in-bse-fin` (the same taxonomy `nselib` parses from
NSE). Sample facts (`contextRef="OneD"` = the Oct–Dec 2024 quarter):

| Fact | XBRL value | ₹ Cr |
|---|---|---|
| RevenueFromOperations | 417640000000 | 41,764 |
| ProfitBeforeTax | 96700000000 | 9,670 |
| ProfitLossForPeriod | 68220000000 | 6,822 |

These match Infosys' published Q3 FY25 consolidated results (revenue ≈₹41,764 Cr,
net profit ≈₹6,806–6,822 Cr) — plausibility-checked, not independently audited.

## 5. Why BSE worked and the direct API did not — the mechanism

This is the crux, and it is **not evasion**. crawl4AI runs a **real headless
Chromium**. When it loads the BSE financials-results page, the page's own
JavaScript fires **same-origin XHRs** to `api.bseindia.com` carrying the browser's
cookies, `Origin`, and `Referer`; Akamai lets those through, so the DOM populates
and the markdown extractor captures the table. A **direct top-level request** to the
same `api.bseindia.com` endpoint (fetch 3) has no such context and is **Akamai-blocked
(301 "Access Denied")** — exactly the wall the wrapper libraries hit. The
`/corporates/Comp_Results` aspx page and the static `/XBRLFILES/*.xml` files are
plain server-rendered / static assets and are **not** Akamai-gated at all. So a
browser-rendering crawler reaches BSE data that a bare HTTP client cannot — using
only a normal user-agent, no proxy, no CAPTCHA, no fingerprint spoofing.

NSE, by contrast, guards even the top-level HTML document with an Akamai sensor
challenge (`ACS-GOTO`) that failed the quote-page navigation outright, and its
results listing is a pure client-rendered shell whose data grid never populated in
the crawl.

---

## KEY QUESTION — does crawl4AI get past NSE/BSE bot-protection to reach INFY FY25 quarter-grain financials/XBRL that the wrapper libraries could NOT?

**PARTIAL — split by exchange, and it *changes the picture for BSE*:**

- **NSE: NO.** crawl4AI did **worse** than the libraries here. The quote page is
  Akamai-hard-blocked (navigation failure) and the results listing is an empty JS
  shell — no INFY financials, no XBRL. The wrapper libs (`nselib`, `NseIndiaApi`)
  *did* get NSE XBRL, but via NSE's JSON API with library-managed cookies, not by
  browser rendering.
- **BSE: YES.** crawl4AI obtained what the library eval **never got from BSE**:
  full quarter-grain P&L (15 line items) rendered on the financials page, a FY25
  filing index with direct Ind AS XBRL links, and a **real downloaded Q3 FY25
  consolidated XBRL file** (`in-bse-fin`, 742 facts). In the library eval, BSE
  yielded only a `bsedata` quote snapshot — **no financials, no XBRL**.

So crawl4AI **does not defeat NSE's protection**, but it **opens BSE as a
first-party Ind AS XBRL source** that the wrapper libraries could not crack — the
same class of data (`in-bse-fin` XBRL) the libs previously obtained only from NSE.

## Comparison verdict vs the wrapper-library approach

| Dimension | Wrapper libraries (eqos-cc5) | crawl4AI (this eval) |
|---|---|---|
| INFY quarter-grain P&L | **Yes**, from **NSE** (`results_comparison`, 5 qtrs) | **Yes**, from **BSE** (15 line items × 5 qtrs + annual) |
| Ind AS XBRL (`in-bse-fin`) | **Yes**, from **NSE** (`nselib` parsed 65 fields) | **Yes**, from **BSE** (downloaded + fact-verified) |
| NSE access | Works via JSON API (cookie-primed HTTP) | **Blocked** (Akamai challenge + empty shell) |
| BSE financials/XBRL | **No** (quote snapshot only) | **Yes** (rendered P&L + XBRL links + file) |
| Anti-bot handling | Library-managed NSE cookies | Real browser context; **no evasion** |
| Cost / weight | Lightweight HTTP libs | Heavy (full Chromium per crawl) |

**Bottom line.** crawl4AI does **not** change the picture for NSE — same wall (in
fact a harder one, since it can't even open the guarded HTML). It **does** change the
picture for **BSE**: a browser-rendering general crawler reaches BSE's quarter-grain
financials and first-party Ind AS XBRL that every wrapper library missed, giving a
**second independent first-party source** (BSE, scrip 500209) for the exact same
`in-bse-fin` XBRL the libs got from NSE. The structured-financials gap for INFY FY25
is therefore **technically closable from BSE via browser rendering**, at higher
operational cost (headless Chromium) and lower reliability than the NSE library path.

**But the verdict is a rights decision, not a technical one.** BSE's XBRL is the
issuer's own regulatory Ind AS filing — a first-party source — yet automated/bulk
retrieval remains **HELD/DENY under `A05-DECISION-001`**, and BSE's ToS are
unreviewed. This evaluation confirms feasibility for BSE; it does **not** authorize
production, standing, scheduled, or bulk use. The most promising *rights-clear*
direction remains scoping the issuer/regulator filing itself (the underlying Ind AS
XBRL) rather than scraping either exchange's protected surface.

---

## Evidence index (session scratchpad — not committed)

`scratchpad/crawl4ai-eval/`:
- `crawl_eval.py` (harness), `.venv/` (crawl4ai 0.9.2 + Chromium 151)
- `nse-robots.txt`, `bse-robots.txt`
- NSE: `nse-fetch1.{html,md}` (blocked, 0 bytes), `nse-fetch2.*` (shell), `nse-fetch3.*` (404)
- BSE: `bse-fetch1.*`, `bse-fetch2.*` (rendered P&L), `bse-fetch3.*` (Akamai 301),
  `bse-prior-fetch1.*` (XBRL link index), `bse-xbrl-fetch1.*` (downloaded Q3 FY25 XBRL)

**Verification status:** All results first-party, run this session in an isolated
venv with a real headless browser. HTTP statuses, rendered content, and XBRL facts
are captured in the saved samples. Financial figures cross-checked against Infosys'
published FY25 results for plausibility; not independently audited. No evasion tooling
used; evaluation stopped at the NSE hard block as instructed and recorded it.
