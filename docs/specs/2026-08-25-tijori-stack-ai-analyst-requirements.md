# Tijori Stack — AI Analyst Surface (Future Requirements)

**Status:** Idea / future guideline. No work authorized yet. Recorded 2026-08-25
at the owner's direction; tracked by the open epic bead referenced below.

## What it is

Tijori Stack (`tijoristack.ai`) is a **paid AI-analyst product** from the same
vendor as Tijori Finance, distinct from the `tijorifinance.com` data site whose
acquisition layer we have already built (five `fundamentals tijori-*` CLI
commands). The owner holds a paid subscription and wants its outputs eventually
available to agent consumers through the same acquisition discipline.

## Known surfaces (owner-reported, 2026-08-25)

Four functionalities, by URL:

1. **Atlas** — `https://www.tijoristack.ai/atlas/`
2. **Concall Monitor** — `https://www.tijoristack.ai/concall-monitor/`
3. **Radar** — `https://www.tijoristack.ai/radar/`
4. **Report on Demand** — `https://www.tijoristack.ai/report-on-demand/`

### Report on Demand — three report types

Generated reports are delivered as PDFs from the vendor's S3 bucket
(`tijori-dev.s3.ap-south-1.amazonaws.com/report/...`). Owner-supplied samples
(all dated 20-Feb-2026):

| Report type | Sample |
|---|---|
| Risk Probe Report | `.../report/Risk-Probe-Report/1343-49199-20-Feb-2026.pdf` |
| 5-Year Revenue & EBITDA Estimates | `.../report/5-Year-Revenue-&-EBITDA-Estimates/1345-52428-20-Feb-2026.pdf` |
| Management Credibility Report | `.../report/Management-Credibility-Report/1344-57769-20-Feb-2026.pdf` |

URL shape suggests `<report-type-id>-<document-id>-<date>.pdf` (1343/1344/1345
look like report-type ids; middle number likely a per-report/company id) —
**unverified inference**, confirm during discovery.

## What we have NOT done

Nothing on this product has been probed, captured, or verified. In particular
we do not yet know: auth mechanism (shared session with tijorifinance.com or
separate), whether surfaces are server-rendered or API-backed, report
generation flow (on-demand trigger vs. pre-generated), rate/quota limits on
report generation, or rights posture for AI-generated report content.

## Guidelines for the future build (when authorized)

- Same discipline as the Tijori Finance layer: discovery captures first
  (owner session, headless browser), clean-room parsers against captured
  structure, typed outcomes, provenance anchors, raw retention, live smoke
  across watchlist stocks. See `docs/learnings/financial-site-scraper-patterns.md`.
- Same security constraints: session credentials never in repo/logs/chat and
  never sent to third-party model CLIs; captures and downloaded reports are
  private subscriber content — never committed (rights decision
  A05-DECISION-005 applies until a Stack-specific ruling is made).
- Report PDFs: extraction stays local/deterministic per existing policy.
- **AI-generated content caveat**: these reports are vendor-LLM output, not
  primary-source data. Any facts promoted from them need a provenance class
  that marks them as third-party-derived analysis, never conflatable with
  filed/published figures. Decide this before any fact promotion.
- Rights re-check required: the Tijori Finance scraping decision does not
  automatically cover Tijori Stack; review its terms before building.

## Open questions for discovery

1. Does the `tijorifinance.com` session cookie authenticate `tijoristack.ai`?
2. What does each of Atlas / Concall Monitor / Radar actually contain, and is
   any of it redundant with surfaces we already acquire (e.g. the existing
   concall-monitor page under `/results/` on Tijori Finance)?
3. Report on Demand: request flow, generation latency, quota, and whether
   past reports remain listable/retrievable per company.
4. Report PDF structure: are the three report types stable templates suitable
   for deterministic extraction?
