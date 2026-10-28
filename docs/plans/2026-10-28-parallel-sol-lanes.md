# Parallel Sol lanes (2026-10-28)

**Why:** the owner has spare GPT-6.1 Sol capacity (resets 2026-10-29/30). These lanes are
independent of the critical path (LIVE-RUN-1 → DOCS-1 merge → RESEARCH-3) and can run in
parallel without touching its files.

**Constraints for every lane:**
- **Database:** the shared PostgreSQL server carries the LIVE-RUN-1 full-suite gates until they
  finish. Run targeted tests only until then (eqos-0bp flakes under load).
- **Isolation:** implementation lanes work in their own worktree, and merge only after a Sol
  review.
- **Size:** the owner's minimal-code rule binds. Sol briefs forbid defensive bloat, and the
  orchestrator checks every diff's size (memory `gpt-overdefensive-regulation`).
- **Concurrency:** 3–4 lanes at once, which is the orchestrator's review bandwidth.

| # | Lane | Beads | Sol role | Output | Owner OK needed |
|---|---|---|---|---|---|
| 0 | **Screener + Tijori full-extraction audit**: what every subscriber-reachable surface contains, compared with what we capture, retain and parse; and whether the code survives site changes | new | Reviewer (read-only, plus a polite live inventory under A05-005) | Coverage matrix, structure findings, a plan to close the gaps | No |
| 1 | **Cheaper, reliable gates**: a multi-slice gate from one suite run, and the flaky full-suite failures | eqos-5h1, eqos-0bp, eqos-1kq, eqos-7fa, eqos-283 | Implementer (worktree) | Fixes, so that 4 slices cost about 2.5 h instead of about 10 h | **Yes** (Sol as implementer) |
| 2 | **PDF extraction diagnosis**: root cause and the smallest fix for each bug (fixes come later, as new parser versions, never as edits to pinned parsers) | eqos-ghv (P1), eqos-djv, eqos-n21, eqos-dol | Diagnostician (read-only) | Root cause, evidence and a fix proposal per bug | No |
| 3 | **Whole-repo critical audit**: invariant violations, dead code, oversized modules (e.g. `goal_runner.py`, eqos-4ff) and spec drift, judged against "could this be half the code?" | new beads from its findings | Reviewer (read-only) | Ranked findings, which become beads | No |
| 4 | **RESEARCH-3 plan**, from the approved spec `docs/specs/2026-10-27-research-3-thesis-analysis.md` (S1 risk probe → S2 credibility → S3 narrate). Execution waits for LIVE-RUN-1 | eqos-bnx | Plan author, or reviewer if Opus writes it | The plan, reviewed by a fresh Sol session | **Yes** if Sol writes it |

**Owner decision (2026-10-28):**
- Lanes 1, 2 and 3 are approved, with Sol implementing lane 1. The orchestrator is accountable
  for their quality.
- Lane 4 is not run now.
- Sequencing: lanes 1–3 start only after the lane 0 Screener/Tijori report has been presented to
  the owner.

**Not worth running now:**
- **BSE 403:** Tijori now covers most of what the BSE copies would add.
- **Daily-trigger scheduling:** it needs a short spec conversation with the owner first.
- **Document content extraction:** nothing is downloaded until the DOCS-1 Task 5 backfill.

## Lane 0 detail: owner requirement (2026-10-28)

> Everything Screener and Tijori show is extracted and kept, whether or not we use it today.

Rights: A05-DECISION-005 already covers any surface the owner's paid accounts reach, for
private, non-commercial use, with retention. Polite fetching only; no anti-bot evasion.

The audit answers four questions:
1. **Coverage.** List each site's subscriber-reachable surfaces: company pages and their sections,
   tabs, XHR fragments and APIs; market, industry, screens, events and timelines; documents.
   For each, record: captured? raw bytes retained? parsed? Sources are the endpoint inventory
   (`docs/research/screener-tijori-endpoint-inventory.md`), the existing ingest modules (about
   24k lines, `src/fundamentals/ingest/screener_*`, `tijori_*`), and a polite live walk of one
   company (APARINDS).
2. **Raw first.** Is every surface retained as raw bytes before parsing, so that a site change
   breaks only the parser and old captures stay re-parseable?
3. **Change resilience.** Are selectors and locators kept in one place per surface? Are parsers
   isolated per surface, so that one layout change touches one module? Does drift fail closed
   and get reported, rather than silently returning empty data? Are there fixture tests per
   surface? Is any module monolithic or above 800 lines?
4. **Gap plan.** What is the smallest way to capture every uncovered surface? Raw capture
   first; parsers only where the data is used.

## VENDOR-SURFACE crawl (epic eqos-aa6, owner 2026-10-28)

The owner asked for three models (Opus 5.5 high, GPT-6.1 Sol high, GPT-6 Astra high) to crawl
Screener and Tijori independently and find every surface. GPT-6 Astra joins for this crawl only,
as a one-off exception the owner named to the agent stack. Coverage: the core six are crawled by
all three models; every other company by two. All three models also crawl the market-wide and
account pages.

| Company | Type | Tier | Crawlers |
|---|---|---|---|
| HDFCBANK | Bank | Large | all 3 |
| HDFCLIFE | Life insurer | Large | all 3 |
| RELIANCE | Conglomerate | Large | all 3 |
| APARINDS | Manufacturing (pilot baseline) | Mid | all 3 |
| NETWEB | Standalone-only | Small | all 3 |
| SME on NSE Emerge (rule) | Half-yearly reporting | Micro | all 3 |
| CREDITACC | NBFC | Small | Opus + Sol |
| ICICIGI | General insurer | Large | Opus + Sol |
| TCS | IT services | Large | Opus + Sol |
| LGEINDIA | Recent IPO | Large | Opus + Sol |
| LAURUSLABS | Pharma | Mid | Sol + Astra |
| HINDUNILVR | FMCG, foreign-parent subsidiary | Large | Sol + Astra |
| GODREJPROP | Real estate | Mid | Sol + Astra |
| SME on BSE (rule) | Half-yearly, BSE-only | Micro | Sol + Astra |
| NTPC | Public-sector utility | Large | Astra + Opus |
| ETERNAL | Renamed (Zomato) | Large | Astra + Opus |
| Mainboard micro-cap (rule) | Thin coverage | Micro | Astra + Opus |
| Nano-cap on the BE series (rule) | Trade-for-trade | Nano | Astra + Opus |

**Rule picks** (`eqos-aa6.2`): the largest company by market cap in the band, among those with at
least two filed periods. Every company's tier and listing is verified on the sites before
crawling.

**Politeness.** Every request goes through `scratchpad/vendor-crawl/fetch.py`, which is the only
network path. It allows GET only, to two allowlisted hosts, and does not follow redirects. Across
all crawlers there is an 8 s gap per site and a cap of 1,200 requests per site per day. Any 403,
429 or 503, or a redirect to login, writes a STOP file for that site. A URL cache stops repeat
fetches of the same page. Crawlers alternate between sites. They make no POSTs and take no paid,
AI or settings actions.
