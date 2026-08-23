# India-Focused News Lane — Source Research

**Date:** 2026-08-23 · **Researcher:** GPT-5.6-Luna (Codex, web-cited) · **Curated by:** orchestrator.
**Purpose:** pick free, ToS-compatible sources for a per-stock news/announcements lane
(personal/private use), feeding the Fundamentals pipeline with provenance-first events.

## Recommended architecture (three source families)

1. **First-party filings (authoritative):** NSE official RSS + corporate filings
   ([NSE RSS](https://www.nseindia.com/static/rss-feed)) and the existing BSE
   `bse.announcements()` client + issuer attachments — expanded beyond `Result` to the
   material-event categories below.
2. **Regulatory context:** SEBI RSS ([sebi.gov.in/rss.html](https://www.sebi.gov.in/rss.html)) —
   market-wide, no per-stock filter; marked `regulatory`, never issuer-originated.
3. **Media context:** ET Markets RSS
   ([economictimes RSS](https://economictimes.indiatimes.com/rss.cms)) — store metadata + links
   only (personal/noncommercial per ET terms), never article bodies. GDELT DOC API as optional
   discovery/backfill (rate-limited, entity-link locally).

**Media-only items are `context_only`. An event is `confirmed`/material ONLY when a first-party
filing or issuer PDF backs it.**

## Verdicts per candidate (key ones)

| Source | Verdict |
|---|---|
| NSE RSS + filings | **Core.** Official, structured; issuer-uploaded, not exchange-verified |
| BSE `bse`/BseIndiaApi | **Core, unofficial.** Active (v3.3.0 May-2026); pin version, health-check, throttle |
| SEBI RSS | Supplementary regulatory context only |
| ET Markets RSS | **Best media lane** — metadata/links only per ToS |
| Business Standard RSS | Only after ToS review — terms restrict automated access and ML use |
| GDELT DOC API | Optional discovery/backfill; 3-month window, 250 results, rate-limited |
| Google News RSS | **Avoid as core** — terms prohibit automated monitoring; manual discovery only |
| GNews API | Occasional secondary (100 req/day, 12h delay) |
| NewsAPI | **Avoid** — free tier prohibits production use, 24h delay |
| Alpha Vantage / Finnhub | Experimental / exclude (India coverage unproven or absent) |
| GitHub scrapers (`stock-news-monitor`, `stockbot-india`, `desiquant`) | **Design references only**, never dependencies |

## BSE categories to ingest beyond `Result`

Priority: **Board Meeting** (results/dividend/buyback outcomes) · **Corp. Action** (dividend,
bonus, split, rights, buyback, delisting) · **Company Update / Others** (Reg-30 events:
acquisitions, disposals, KMP/auditor changes, ratings, litigation, fraud/default, CIRP,
earnings-call notices) · **AGM/EGM** · **Insider Trading / SAST** (promoter pledges, large-holder
moves). Persist raw `CATEGORYNAME`/`SUBCATNAME`/headline/timestamp/attachment/payload — do not
hard-code today's subcategory strings.
([BSE constants](https://bennythadikaran.github.io/BseIndiaApi/Constants.html),
[NSE XBRL filing categories](https://www.nseindia.com/static/companies-listing/xbrl-information))

## Fail-closed event model

- Immutable `observations` per source occurrence: issuer_id, exchange_symbol, ISIN,
  source_family, source_url, attachment_url, published_at, observed_at, raw
  title/category/subcategory, payload hash, parser version.
- Derived deduplicated `events`: dedupe by normalized URL + issuer + event type + title
  similarity + time window — retaining every original observation.
- Entity matching ladder: ISIN/scrip → exact NSE/BSE symbol → unambiguous alias →
  **quarantine as unresolved** (never guess).
- **A 200-OK but stale/empty feed is a source-health failure, not "no news."**

## Open questions (validate with live probes)

- Real latency of NSE RSS vs BSE polling vs ET RSS across trading days.
- Stability of BSE subcategory strings for routing (vs keyword/Regulation mapping).
- ET/BS metadata storage acceptability for this private deployment.
- Entity false-positives for common company names; syndicated-story clustering.
