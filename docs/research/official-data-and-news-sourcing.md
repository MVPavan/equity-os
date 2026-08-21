# Official / Licensed Sourcing for Indian Filings, Fundamentals, XBRL & News

**Status:** Research draft. **Author:** research analyst (Equity-OS). **Date:** 2026-08-21.
**Scope:** Lawful, official/licensed alternatives to scraping NSE/BSE for (A) Indian listed-company
filings + fundamentals + XBRL, and (B) Indian financial news. Scraping NSE/BSE is held DENY and is
out of scope except to name it as the excluded path.

**Evidence discipline:** Every row/claim carries a source URL + access date. Facts I confirmed on a
source are marked plainly; inferences are marked **[inference]**; unconfirmed items are in
"Open questions / could not verify." **No pricing is fabricated** — where a vendor does not publish
price, this says "not public." Several NSE `nseindia.com` static pages are bot-protected and timed
out on automated fetch; those rows rely on the search-surfaced description of the same official page
(URL cited) and are flagged **[page not directly fetched]**.

---

## Part A — Official / licensed exchange & filing data

| Source | Data covered | Official API / feed? | Rights / redistribution | Cost tier | Notes + citation (accessed 2026-08-21) |
|---|---|---|---|---|---|
| **NSE Data & Analytics Ltd (formerly DotEx International)** — "Paid Corporate Data" | Company **fundamentals, corporate announcements, shareholding pattern** (the disclosures issuers file with NSE); separate real-time/EOD market-price feeds | **Yes, partial.** Official feed products: EOD **Corporate Data via SFTP** (available after 20:00 IST daily) and leased-line real-time market data. Not a modern REST API for fundamentals; it is a licensed file/feed subscription. | Licensed. NSE data to third parties requires a **distribution license**; redistribution only under agreement, or take data via an NSE **authorized data vendor**. | **Paid** (domestic); price **not public** (contact NSE). | Corporate Data subscription page: https://www.nseindia.com/static/market-data/corporate-data-subscription **[page not directly fetched — bot-protected]**; Data & Analytics overview: https://www.nseindia.com/static/nse-data-and-analytics ; data-vending/licensing described at https://www.nseindia.com/static/nse-data-and-analytics/data-information-vending |
| **NSE — XBRL filings** | Ind AS **quarterly/annual financial results + other disclosures in XBRL**, filed issuer→exchange | Filing intake, not an open data API. XBRL is published on the NSE site per-company; single-filing **API-based integration between NSE & BSE** exists for filers (Mar 2026 expansion), i.e. a *submission* pipe, not a public read API. | Display/scrape of the website is governed by NSE terms (DENY here). Structured redistribution needs the licensed Corporate Data feed above. | Website copy = free-to-view (not free-to-redistribute); feed = paid | XBRL info page: https://www.nseindia.com/static/companies-listing/xbrl-information **[timed out on fetch]**; single-filing API expansion: https://taxguru.in/sebi/single-filing-system-expanded-bse-extends-api-based-integration-xbrl-disclosures.html |
| **BSE — Information Products (Corporate Data feed)** | Real-time, EOD, historical **market data** + **Corporate Data** (corporate actions in ISO15022/SWIFT MT564; announcements; company financials) | **Yes.** BSE Information Products subscription; corporate-action data over SWIFT; feed via BSE or its data vendors. | Licensed. Subscription/redistribution via BSE directly or authorized vendors. **International licensing moves in-house to BSE from 2027-01-01** (ends Deutsche Börse exclusivity). | **Paid**; a **Domestic Tariff Sheet PDF exists** but figures were **not machine-extractable** here → treat price as "published-but-unread." | Market data products: https://www.bseindia.com/static/about/xbrl_info.aspx & market_data_products page; tariff PDF: https://www.bseindia.com/downloads1/Information_Products_Pricing_Sheet.pdf ; licensing change: https://scanx.trade/stock-market-news/companies/bse-to-manage-market-data-licensing-directly-from-january-1-2027/44313756 ; contact datafeed@bseindia.com / datafeed.sales@bseindia.com |
| **BSE — XBRL (Listing Centre)** | Announcements + financial results in **XBRL**; XBRL taxonomies (incl. insurance) | Filing intake + single-filing API integration with NSE (effective 2026-03-07 expansion). Read access = website. | Same as NSE: website view is not a redistribution license; structured rights via Information Products. | Website free-to-view; feed paid | About XBRL: https://www.bseindia.com/static/about/xbrl_info.aspx ; XBRL announcements: https://www.microvistatech.com/blog/filing-of-announcements-in-xbrl-format-on-bse-listing-centre ; taxguru (as above) |
| **SEBI Integrated Filing regime** | Governance + financial periodic filings consolidated; XBRL/PDF; single-filing system so a listed entity files once and it propagates across exchanges | **No public open API / no SEC-EDGAR-style bulk download.** It streamlines *filing*, and dissemination remains **on the exchange websites**. | No new redistribution rights for consumers; the readable copies still sit behind exchange terms. | n/a (regulatory framework) | Gazette 2024-12-13; NSE Integrated Filing circular (NSE/CML/2025/02): https://nsearchives.nseindia.com/web/sites/default/files/inline-files/NSE%20Circular%20facilitating%20ease%20of%20doing%20business%20for%20listed%20entities-%20Integrated%20Filing.pdf **[PDF timed out on fetch]**; overview via taxguru (above) |
| **Depositories (NSDL / CDSL)** | Demat holdings, settlement, corporate actions, KYC (CAS) — **not** a financial-statement/XBRL filing repository | No — not relevant as a fundamentals/filings source | n/a | n/a | https://www.sebi.gov.in (depository circulars); CDSL master circular PDF. **Confirmed: depositories are not the filings/XBRL repository.** |
| **Accord Fintech — ACE Equity / ACE Datafeed** (India-native) | **Fundamentals** (40,000+ Indian cos, ~1,750 fields from annual reports), quarterly results, 5-yr histories, corporate announcements, corporate actions, news, MF/commodity/currency | **Yes** — data feed via **FTP and API**; explicitly an **authorized vendor of BSE/NSE/MCX/NCDEX** | **Licensed vendor** (authorized by exchanges). Redistribution/derived-use terms **not stated publicly** → confirm in contract. | **Paid** (enterprise/B2B); price not public | https://www.accordfintech.com/market-data-feed ; https://www.accordfintech.com/ace-equity-nxt |
| **Dion Global** (India-native) | Clean raw datasets: Equity (BSE/NSE), derivatives, IPO, MF, insurance, news, corporate announcements, corporate info — CSV | **Yes** — subscription datasets for websites/apps (CSV) | Vendor license (B2B). Redistribution terms not public. | **Paid**; not public | https://www.dionglobal.com/stock-market-data-content-and-financial-research-solutions.html |
| **CMIE Prowess / ProwessIQ** (India-native) | Deep fundamentals: ~107k companies (5.5k listed + ~101k unlisted), 3,500+ fields, time-series from 1989-90 | Web application + data; API not publicly documented | Academic/enterprise **subscription license**; typically **use-restricted (no onward redistribution)** **[inference from academic-library licensing]** | **Paid** (enterprise/academic); not public | https://prowess.cmie.com/ ; https://www.cmie.com (ProwessIQ product) |
| **LSEG / Refinitiv** | Global incl. India: pricing, index constituents/weights, reference data; equity fundamentals via Refinitiv Data feeds; **Reuters news** | **Yes** — request/response + bulk feeds (RDP/ADS) | Enterprise license; **redistribution/derived works permitted under contract** | **Enterprise** (high); not public | NSE-India page: https://www.lseg.com/en/data-analytics/financial-data/pricing-and-market-data/equities-market-data/national-stock-exchange-india (confirmed: page covers index pricing/reference data; fundamentals sold under broader Refinitiv packages) |
| **Bloomberg** | India fundamentals, pricing, corporate actions, news; Data License / B-PIPE / BQL | **Yes** (enterprise APIs) | Enterprise license; redistribution/derived-use under Data License contract | **Enterprise** (high); not public | Per provider comparison: https://www.globaldatabase.com/bloomberg-vs-refinitiv-vs-sp-capital-iq-which-financial-terminal-is-worth-it |
| **S&P Capital IQ** | Standardized financials, estimates, transactions, screening; global incl. India | **Yes** (feeds/API) | Enterprise; **derivative works + redistribution allowed under agreement** (S&P confirms such terms for its market-data agreements) | **Enterprise**; not public | https://press.spglobal.com/2013-07-15-S-P-Capital-IQ-Announces-Strategic-Agreement-with-Tullett-Prebon-Information-for-Use-and-Redistribution-of-Market-Data |
| **FactSet** | Public-company fundamentals + forecasts, global incl. India | **Yes** (feeds/API) | Enterprise license | **Enterprise**; not public | https://www.globaldatabase.com/top-10-capital-iq-competitors-alternatives-for-2026-ranked |
| **Morningstar** | Fund/ETF analytics; some equity fundamentals | Yes (Direct / feeds) | Enterprise license | **Enterprise**; not public | https://guides.library.upenn.edu/finance/fundamentals |
| **EODHD** | NSE + BSE **fundamentals** (P&L, balance sheet, cash flow, ratios), EOD prices, 60+ exchanges | **Yes** — REST API | Commercial API; **redistribution requires a separate/enterprise plan** — verify | **Paid** (tiered, from low $ to enterprise); base plans public, redistribution terms not confirmed | https://eodhd.com/financial-apis/stock-etfs-fundamental-data-feeds ; https://eodhd.com/lp/fundamental-data-api |
| **FinEdge API** | NSE & BSE fundamentals, P&L/BS/CF, ratios, shareholding, corporate actions, prices | **Yes** — REST API | Commercial API; **source authorization/redistribution rights unverified** — treat cautiously | **Paid**; not fully public | https://www.finedgeapi.com/ |
| **TrueData** | Real-time/EOD **market data** for NSE/BSE/MCX (+ some corporate data); charting APIs | **Yes** — market data API | **Authorized NSE/BSE/MCX data vendor** (market data). Fundamentals depth limited. | **Paid** (retail→pro); some pricing public | https://www.truedata.in/ ; https://www.truedata.in/price |
| **Screener.in / Tickertape / Trendlyne / Tijori** (retail research portals) | Fundamentals, ratios, screens (retail-facing) | **Mostly no public/redistribution API.** Tijori = **no public API**; Screener = Excel export for **personal use**; Trendlyne is SEBI research-analyst-registered but sells access, not a redistribution feed | **Not licensed for redistribution / derived commercial data products.** Programmatic pulls ≈ scraping → **EXCLUDED** for our use | Free tier + paid subscriptions (e.g. Tijori paid from ₹330/mo) | https://drishti.manasija.in/blog/4-best-tijori-alternatives-in-2026 ; https://www.winvesta.in/blog/investors/fundamental-analysis-tools-and-screeners-2026-guide |

### Part A key findings
- **Does NSE offer an official licensed API for fundamentals/XBRL?** **Partial.** NSE (via NSE Data &
  Analytics Ltd) sells a licensed **Corporate Data** subscription covering **fundamentals, corporate
  announcements and shareholding pattern**, delivered as **EOD files over SFTP** (not a modern REST
  API, and XBRL as a *structured redistributable product* is not clearly offered separately). Price
  not public.
- **Does BSE offer an official licensed API for fundamentals/XBRL?** **Partial/Yes for feeds.** BSE
  **Information Products** include a licensed **Corporate Data** feed (announcements, corporate
  actions over SWIFT MT564, company financials); XBRL is filed via the Listing Centre. It is a
  licensed **feed subscription**, priced in a published (but here unreadable) domestic tariff sheet;
  international licensing comes in-house to BSE on 2027-01-01.
- **Central regulatory repository?** **No open bulk/EDGAR-equivalent.** SEBI's **Integrated Filing**
  regime consolidates *filing* and syncs across exchanges via API integration, but public
  **dissemination is still on the exchange websites** — it grants no new redistribution rights and no
  free structured API. Depositories (NSDL/CDSL) are **not** a financials/XBRL source.
- **XBRL specifically:** The primary XBRL (issuer→exchange, per SEBI LODR) is officially published on
  the **NSE and BSE websites**; the only route with clear usage/redistribution rights is a **licensed
  exchange Corporate Data feed** or a **licensed authorized vendor** (Accord/Dion) — the free website
  copy carries no redistribution rights (that path = scraping = DENY).

---

## Part B — News aggregator options

| News source | API? | Rights / redistribution | Cost | India coverage | Citation (accessed 2026-08-21) |
|---|---|---|---|---|---|
| **GDELT Project** | **Yes** (open datasets, BigQuery, files, AWS) | **Open: unrestricted academic/commercial use AND redistribution, no fee** | **Free** | **Global incl. India** (indexes Indian outlets). Note: article **metadata, tone, entities, links** — *not* full article text | https://www.gdeltproject.org/about.html ; https://registry.opendata.aws/gdelt/ |
| **Accord Fintech — news feed** (bundled in ACE Datafeed) | **Yes** (FTP/API) | **Licensed** B2B vendor feed (India news + corporate announcements + fundamentals in one contract); redistribution terms to confirm | Paid; not public | **India-focused** | https://www.accordfintech.com/market-data-feed |
| **Wire services — PTI / Reuters(LSEG) / Bloomberg / Dow Jones** | Yes (enterprise feeds) | **Fully licensed editorial redistribution** under subscription; PTI is India's largest agency, subscription-only | **Paid → enterprise**; not public | PTI = strongest India-native editorial; Reuters/Bloomberg = global+India | https://en.wikipedia.org/wiki/Press_Trust_of_India ; LSEG/Bloomberg feeds as above |
| **Marketaux** | Yes (REST) | Commercial; redistribution limited — **verify per plan** | Free tier + paid | India tickers filterable, depth varies | https://qveris.ai/guides/financial-news-api-for-ai-agents/ |
| **Finnhub** | Yes (REST + WebSocket) | Commercial; redistribution limited — verify | Free tier + paid | Global; India coverage partial | https://qveris.ai/guides/financial-news-api-for-ai-agents/ |
| **Alpha Vantage (News & Sentiment)** | Yes (REST) | Commercial; **exchange-licensed for data**; news redistribution limited | Free tier + paid | US-centric; India news thin | https://www.alphavantage.co/best_stock_market_api_review/ |
| **NewsData.io / TheNewsAPI / APITube** | Yes (REST) | Commercial; some **offer commercial-use tiers**; still verify republish rights | Free tier + paid | Global incl. India (varies) | https://newsdata.io/blog/best-stock-news-api/ ; https://www.thenewsapi.com/tos |
| **NewsAPI.org** | Yes (REST) | **Restrictive:** free = **non-commercial**; **no republishing article content** (title/desc/URL only); redistribution needs separate terms | Free (dev) + paid | Global incl. India | https://newsapi.org/terms ; https://newsapi.org/pricing |
| **Moneycontrol / Economic Times / Mint** | **No official licensed data API.** RSS feeds exist (personal reading only) | Content is **copyrighted; no public feed license**; RSS ≠ redistribution right; programmatic bulk = scraping → **EXCLUDED** | RSS free (personal) | Best India editorial depth, but **not licensable as a feed** to us | https://newsloth.com/popular-rss-feeds/moneycontrol-rss-feeds ; "no official public API": https://www.quora.com/How-is-moneycontrol-com-getting-its-stock-data |

### Part B key finding — two distinct classes
1. **Corporate-announcement "news" (regulatory disclosures)** — board-meeting intimations, results
   announcements, trading-window closures, fraud/default disclosures. **Officially available via the
   exchange Corporate Data feeds** (NSE Corporate Data / BSE Information Products) or licensed vendors
   (Accord/Dion). This is *primary regulatory data*, not editorial.
2. **Editorial news** — moneycontrol/ET/Mint/wires. Licensable **only** via wire services (PTI,
   Reuters/LSEG, Bloomberg, Dow Jones) or news APIs; the Indian consumer news sites do **not** sell a
   public feed and must not be scraped.

---

## Lawful path recommendation

Ranked by (rights-clarity → coverage → cost). All three avoid scraping.

**1. Single licensed India-native vendor: Accord Fintech (ACE Equity / ACE Datafeed) — or Dion Global.**
   *Best overall fit.* One **authorized BSE/NSE/MCX/NCDEX** vendor delivers **fundamentals + quarterly
   results + corporate announcements + news** over **FTP/API** in one contract, India-focused. Highest
   coverage-per-effort for an Indian-issuer product like Infosys. **Cost tier: paid / enterprise B2B
   (price not public — must quote).** Caveat: get **redistribution / derived-use rights written into
   the contract** (not stated publicly).

**2. Direct exchange licensed feeds: NSE Corporate Data (SFTP) + BSE Information Products.**
   The most authoritative/primary path — data straight from the source with clear licensing, including
   the **XBRL-origin fundamentals and announcements**. Downsides: **two contracts**, **file/SFTP + SWIFT
   delivery rather than a clean REST API**, and pricing is **not public** (NSE contact; BSE tariff
   sheet exists). **Cost tier: paid.** Best when provenance/primary-source fidelity matters most.

**3. Global enterprise vendor with redistribution rights: LSEG/Refinitiv, S&P Capital IQ, Bloomberg,
   or FactSet.** Cleanest **contractual redistribution/derived-works rights** and one feed for
   fundamentals **and** Reuters/Bloomberg news, global + India. **Cost tier: enterprise (highest),
   price not public.** Overkill/expensive if the product is India-only, but unbeatable on rights
   clarity. A lighter commercial middle option is **EODHD** (public NSE/BSE fundamentals API) *if* its
   redistribution plan checks out.

**News, specifically:**
- **Free + fully redistributable:** **GDELT** (open license, global incl. India) — but metadata/links,
  not full article text.
- **Best single licensed India news option:** the **Accord Fintech news feed** (India-focused,
  licensed, bundled with the fundamentals you already need) for product-integrated news; or a **wire
  service (PTI for India-native, Reuters/LSEG for global+India)** when you need full editorial
  redistribution rights.

**Explicitly free-but-scraping (EXCLUDED, DENY):** NSE/BSE website pages, Screener.in / Tickertape /
Trendlyne / Tijori programmatic pulls, and moneycontrol/ET/Mint scraping or RSS-as-a-feed. Free to
*read*, **not licensed to ingest/redistribute**.

---

## Open questions / could not verify
- **Exact pricing** for NSE Corporate Data, BSE Information Products, Accord, Dion, CMIE, and the
  enterprise vendors — **none publish figures**; BSE's domestic tariff PDF exists but was **not
  machine-extractable** in this environment (poppler/pdftotext unavailable). Marked "not public."
- **Redistribution / derived-use rights** for Accord, Dion, EODHD, FinEdge — feeds are licensed, but
  whether the license permits building a *derived data product* (vs. internal use only) is **not
  stated publicly** and must be confirmed in contract.
- Whether NSE/BSE sell **XBRL itself as a distinct structured redistributable product** (vs. bundled
  "Corporate Data") — not confirmed; likely delivered inside the Corporate Data feed. **[inference]**
- Several **`nseindia.com` official pages were bot-protected** and timed out on automated fetch
  (Corporate Data subscription, XBRL info, Integrated Filing PDF). Their contents here rest on
  search-surfaced descriptions of those same official URLs — **verify by opening in a browser**.
- **India-specific depth** of Marketaux/Finnhub/NewsData.io/TheNewsAPI news — providers advertise
  global coverage; per-outlet India depth and republish rights need per-plan confirmation.
- **CMIE ProwessIQ API** existence/terms — product is web-app + subscription; a redistribution-grade
  API was **not confirmed**.
- FinEdge API's **exchange authorization** status — unverified (treat cautiously vs. authorized
  vendors like Accord/TrueData).
