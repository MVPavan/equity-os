# India-Focused News Sourcing — Free/Open Options

**Produced by:** GPT 5.6 Sol Luna (via Codex CLI) with live web search, 2026-08-21.
**Status:** NON-AUTHORITATIVE research. **Citations are model-produced and must be
spot-verified before adoption** — GPT-family models sometimes cite plausible-but-wrong
URLs. Listing a tool here is not adoption or a rights decision.
**Rights note:** editorial-news scraping is a SEPARATE terms-of-service surface from the
NSE/BSE scraping approved under `A05-DECISION-004`; every publisher below has its own
terms (most permit personal/non-commercial RSS reading only, and prohibit automated
scraping/redistribution).

## Ranked free shortlist

1. **Official publisher RSS + `feedparser`** (BSD-2-Clause) — cheapest, no API key. Direct
   Indian coverage (ET Markets, LiveMint, Business Standard, Moneycontrol). Catch: headlines +
   excerpts + links only, not full article text; publisher terms are personal/non-commercial.
2. **Marketaux** (API, free tier) — best *company-specific* fit; Infosys explicitly supported as
   `INFY.NS` with symbol/exchange/country/sentiment filters. Catch: 100 req/day, 3 articles/req,
   snippets only, token required.
3. **GDELT DOC 2.0** (free, keyless) — broad discovery with `sourcecountry:india`, domain/tone
   filters; permits use + redistribution with attribution. Catch: media-monitoring dataset, not an
   equity feed; rolling 3-month window, 250-result cap.
4. **NSE/BSE corporate announcements** — most authoritative for company *events* (results, board
   meetings, Reg-30). Catch: regulatory disclosures, not editorial news; NSE ToS prohibits automated
   collection (already covered by our A-05 decisions).
5. **NewsLookout** (GPL-3.0, PyPI 3.0.0 Mar-2026) — plugin crawler with Indian source modules.
   Catch: GPL, plugin parity unverified, scraping still bound by publisher terms.

## Data-class distinction (important)

- **Regulatory disclosures** (NSE/BSE announcements) — primary-source *events*; our libs/crawl4AI
  already cover these. NSE itself states filings are displayed without verification of accuracy.
- **Editorial news** (Moneycontrol/ET/LiveMint/BS/Reuters) — context, quotes, analysis; paywalled
  or copyrighted; separate rights surface.
- **Aggregated news APIs** (Marketaux/NewsAPI/GDELT) — metadata/snippets/links/sentiment, NOT a
  licence to reproduce full articles.

## Evaluation table (spot-verify citations before use)

| Source / repo | Type | India coverage | Access | Free? | License / ToS | Maintenance |
|---|---|---|---|---|---|---|
| Marketaux | API | INFY.NS verified; India filter | REST, token | 100/day, 3/req | snippets+links only | active |
| GDELT DOC 2.0 | API/dataset | `sourcecountry:india` | HTTP, no key | Yes | use+redistribute w/ attribution | mature, old docs |
| gdelt-doc-api | Py client | via GDELT | wrapper | Yes | MIT | older |
| NewsAPI | API | `country=in` | key | 100/day, dev-only, 24h delay | no production use | restricted free tier |
| Finnhub | API | poor (NA-only company news) | key | Yes | US-only decisive | active |
| Alpha Vantage | API | India unverified | key | 25/day | individual research = "commercial" | risky terms |
| NewsLookout | crawler | MC/LiveMint/BS/ET modules | scraping | Yes | GPL-3.0 + publisher ToS | PyPI 3.0.0 Mar-2026 |
| news-please | crawler | no India adapters; crawls URLs/RSS | HTML/RSS/CommonCrawl | Yes | Apache-2.0 | 1.6.16 Sep-2025 |
| Trafilatura | extractor | works on fetched HTML/RSS | extraction | Yes | Apache-2.0 (v1.8+) | 2.2.0 Jul-2026 |
| Newspaper4k | extractor | parses Indian URLs | HTML | Yes | MIT | 0.9.6 Jul-2026 |
| feedparser | RSS parser | any valid RSS/Atom | parse, no key | Yes | BSD-2-Clause | 6.0.14 Jul-2026 |
| ET RSS | official RSS | markets/companies | RSS | personal-use | no aggregate/resell | current |
| LiveMint RSS | official RSS | companies/markets | RSS | personal-noncommercial | licence for more | current |
| Business Standard RSS | official RSS | companies/markets/finance | RSS | public | no scrape/redistribute | current |
| Moneycontrol RSS | official RSS | markets/companies | RSS hub | view-free | ToS prohibits bots/scrapers | English feed empty in live check |
| Reuters RSS | licensed | India coverage | authenticated | not free | licensed only | commercial product |

## Avoid / risky

- Moneycontrol scrapers as a production dependency — MIT code ≠ content rights; MC ToS prohibits automated scraping.
- Original `newspaper3k` — unmaintained since 2020; use the Newspaper4k fork.
- `nsepython` for announcements — unofficial, stale, broken-endpoint issues.
- Finnhub / Alpha Vantage for Indian company news — NA-only / India-unverified + "commercial use" terms.
- Proxy rotation / CAPTCHA-solving / Cloudflare bypass / stealth scraping — riskier and unnecessary for an RSS-first pipeline (aligns with our standing no-evasion boundary).

## Recommendation (from the research)

Cheapest defensible personal pipeline: **`feedparser` against official ET / LiveMint / Business
Standard (and any working Moneycontrol) RSS**, retaining only title + source + timestamp + short
permitted excerpt + canonical URL. Add **Marketaux** for entity-aware company matching (INFY.NS
supported) and **GDELT** for broader discovery. Keep **NSE/BSE disclosures as a separate
primary-event stream**, not editorial news. No single GitHub repo suffices — the design is a small
RSS collector + Marketaux/GDELT + a separately governed regulatory-filings adapter.
