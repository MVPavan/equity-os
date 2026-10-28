# Lane 0 — Screener / Tijori extraction and change-resilience audit

Lane 0 audit by gpt-6.1-sol (2026-10-28), reviewed by the orchestrator. Its evidence files stay in the gitignored `scratchpad/lane0-walk/`. The code claims were spot-checked: `tijori_overview_cli.py` writes parsed JSON only, `retention/eligibility.py` has the 12-month vendor window, and the `screener_company_discovery.py` regexes contain no space before `(`.

Date: 2026-10-28. Scope: this checkout, source inspection, named fixture tests inspected, and a bounded authenticated APARINDS walk. Written report only; no product changes, Beads, database access, Git writes, POSTs, login refresh, settings changes, or attachment downloads.

**The owner's full-extraction requirement is not met.** Core financial parsing is broad, but acquisition is selective, raw retention depends on the entry point, and much of both sites is unbuilt. A retained company HTML page does not include subsequently loaded charts, summaries, histories, or document bytes.

## 1. How to read the counts

These are **surface-family implementation counts**, not percentages of either site's data or a census of captures already on disk. A family groups variants of one interface, explicitly named below. Pagination, time windows and all members still need coverage. One-company discovery cannot prove that every sector-specific/company-specific surface has been found.

| Site | Covered: fetch + parser implemented (C) | Raw-only parent-page coverage (R) | Missing acquisition (M) | Inventoried families |
|---|---:|---:|---:|---:|
| Screener | 19 | 3 | 29 | 51 |
| Tijori | 24 | 5 | 24 | 53 |

**C does not mean compliant with raw-first or complete history.** `partial` explicitly identifies gaps; several C paths discard raw bytes. R means the bytes can survive within a retained parent response, with no dedicated parser. Tijori R rows are conditional on retaining the financial page or the D7 other-vendor overview read; the ordinary overview CLI does not retain its HTML. Scratchpad captures from this audit do not upgrade an M to production coverage.

Evidence labels: **Observed-live** = this walk; **Observed-code** = checked source/test; **Historical** = supplied research/probe, not reverified here; **Inference** = consequence or implementation estimate. Subscriber content is private under A05-DECISION-005. The current rights record includes the 2026-10-28 Tijori-copy addendum; a separate rights approval is not needed to capture these vendor surfaces.

## 2. Live walk and its limits

Read `docs/plans/2026-10-28-parallel-sol-lanes.md`, Lane 0 detail, first. Used the identifiers in `config/watchlist.yaml:318`: Screener company 211, warehouses 6594631/2446; Tijori `apar-industries-limited`, company 4290.

Credentials: `scripts/credentials.sh:3` documents `~/.secrets/screener_session` and `~/.secrets/tijori_session`, exported into the usual environment variables. That script can refresh/login when sessions are old (`:12`), so I did **not** source it. The scratch script reads only those two session files into `SecretStr` and injects the same existing transports. No cookie values or response bodies were printed. `ScreenerSessionSource.fetch_navigation/fetch_document` and `TijoriSource._fetch_page_bytes` performed the GETs; the latter private method is the existing raw transport behind Tijori's public fetchers.

The sandbox could not resolve Screener DNS. Ten sandbox attempts failed before any HTTP response; the authorized network escalation then worked. Actual external GETs: **Screener 40, 37 successful and three refused; Tijori 58, 55 successful and three refused**. No retries, redirects followed, concurrent requests to a site, or evasion. The script sleeps 2.1 seconds between operations; recorded minimum request-start spacing was 2.059 seconds for Screener and 2.062 seconds for Tijori. Explicit timeout 25 seconds. Both counts stay below 60 per site, even counting the ten sandbox Screener attempts (50 total). Refusals were not worked around.

Observed-live structure:

- Screener APARINDS consolidated/standalone pages have 11 sections: `chart`, `analysis`, `peers`, `quarters`, `profit-loss`, `balance-sheet`, `cash-flow`, `ratios`, `insights`, `shareholding`, `documents`. No `application/json` islands. The consolidated page advertises 15 schedules, nine holder drill-downs and two segment controls. Sample schedule/investor/segment, peers, quick ratios, corporate actions and related-party responses returned 200.
- The same page advertises 55 concall-summary URLs and an annual-report summary. One of each returned 200. Other paths: `/insights/company/211/flag/` and `/trades/company-211/` returned 200; the quarter-insights navigation GET returned 405; commentary and company-notebook navigation GETs returned 302. Their GET availability through the proper modal flow remains unverified; no POST was attempted.
- Tijori serves all five company tabs: overview, financials, shareholding, benchmarking, reports. The retained overview has 23 distinct JSON-island IDs, including newer `memoryOverviewKeyEvents`, `user_prefs` and `pagesremain`. Financials has 15 table keys. Existing parsers successfully read all 15 financial tables, 10 overview sections, and 29 detailed shareholding rows across 10 periods plus one breakup chart.
- The old `price_chart` island is **absent**. The referenced price-chart script names `/api/v1/ind/chartdata/{id}/price/`; APARINDS returned a JSON envelope with `data` and `status`, with the series encoded inside the `data` string. Debt and capex API responses have the same envelope field names. None of these three APIs has an acquisition path in the audited modules.
- APARINDS overview explicitly embeds **12** `/api/v1/ind/company_op_metrics/4290/<metric_id>/` URLs. All 12 returned 200. No metric-ID guessing was necessary. The source comment saying no acquired artifact publishes IDs is stale.
- Tijori `#companyFilings`: 135 document links, grouped into annual reports, earnings releases, presentations and conference calls. The earlier probe's category counts are 16/14/52/53; no attachment was downloaded. The reports tab exposes six report links in this walk, distinct from company filings.
- Existing events parsing reads 40 company-timeline events, 20 upcoming-result rows, 20 latest-result items, and 231 site-timeline taxonomy/list elements. It correctly labels the site event feed and upcoming-concall feed unacquired. Page-two results GETs returned additional populated HTML. The script-referenced `/results/concall-summaries/api/?page=1` and bare `/timeline/all/` returned 404; these are **not verified usable APIs**. The concall landing page links to Tijori Stack.

Evidence: `requests.jsonl` contains paths, outcomes, UTC times, hashes, byte counts and structure; bodies are under `screener/` and `tijori/`. `parse-checks.json`, `hook-drift-check.json`, `segment-false-absence.json`, and `module-sizes.json` contain reproducible local findings. These scratch files are private audit evidence, not registered production captures.

## 3. Retention and function key for the matrices

All paths below are repository-relative defaults; this audit did not inspect production data directories or a database.

| Key | Fetch/parser implementation | Retention on that path |
|---|---|---|
| SP | `ingest/screener_session.py:115`, `ScreenerSessionSource.fetch_company_page`; `api/screener_page_cli.py:103`, `run_screener_page_command` | `data/raw/watchlist/screener-page/<stock>/<basis>/screener_page.raw.html` + metadata hash/time. Identity/basis interpretation happens before publication. |
| SF | `ingest/screener_financials.py`, `read_financials`; `screener_financials_tables.py:196/247`, `read_section/read_growth_section`; `_sweep_schedules(:249)` and nested reader | `data/raw/watchlist/screener-financials/<stock>/<basis>/screener_financials_page.raw.html`, `schedules/`, metadata/failures. Bytes accumulate in memory before parsing; publication follows the sweep (`api/screener_financials_cli.py:184/216`). |
| SC | `ingest/screener_company.py:137`, `read_company`; part functions in `screener_company_parts.py` | `data/raw/watchlist/screener-company/<stock>/<basis>/screener_company_page.raw.html`, `documents/`, part JSON, metadata/failures. Parsed before durable publication (`api/screener_company_cli.py:180/211`). |
| SW | `ingest/screener_watchlist.py`, `acquire_watchlist`, `read_watchlist_table`, `read_watchlist_export` | `data/raw/screener-watchlist/<id-or-core>/watchlist.raw.html`, `watchlist.raw.csv`, artifact hash/time. `api/screener_watchlist_cli.py:90` acquires/parses before writing. |
| SX/TX | `ingest/screen_export.py:143/189`, `export_screener/export_tijori`; `result_rows(:217)` | Successful exports go through `coverage/screens.py:156/175`, `record_screen_run/_store`, into `SnapshotStore` + capture refs. Formula/schema/count checks precede retention. Screener export is POST; inspected only, not exercised. |
| TF | `ingest/tijori_source.py:204`, `fetch_financials_page`; `tijori_retention.py:94`, `retain_tijori_tables`; `tijori_tables.py:716`, `build_all_tijori_tables` | `data/raw/snapshots/v1/tijori/financials/<request_key>/<capture_id>/body.html` + capture record/hash/time; typed JSON in `data/raw/watchlist/tijori-tables/<stock>/`. Retained before financial-table parsing; auth/identity classification still happens first. |
| TO | `ingest/tijori_source.py:309/450`, `fetch_overview/parse_overview_bytes`; `tijori_overview.py:272`, `build_tijori_overview`; builders in `tijori_overview_sections.py`, `tijori_overview_company.py`, `tijori_overview_revenue_mix.py` | Ordinary `api/tijori_overview_cli.py:78/96` writes only section JSON under `data/raw/watchlist/tijori-overview/<stock>/`. **No HTML retained.** D7's conditional other-vendor read retains a whole overview in snapshots (`coverage/screen_review.py:192/199/224`), but is not a general overview capture job. |
| TS | `ingest/tijori_source.py:283/472`, `fetch_shareholding/parse_shareholding_bytes`; `tijori_shareholding.py:525`, `build_tijori_shareholding` | Ordinary `api/tijori_shareholding_cli.py:72/83` writes only typed JSON under `data/raw/watchlist/tijori-shareholding/<stock>/`. D8 separately registers page captures through `api/shareholding_cli.py`; the ordinary CLI has **no HTML retention**. |
| TA | `ingest/tijori_source.py:334`, `fetch_analysis`; `tijori_analysis.py:373/414/471/497`, respective builders | `data/raw/watchlist/tijori-analysis/<stock>/<section>[-metric].raw.json` and typed JSON/hash/time. All requested documents must fetch **and parse** before the CLI writes any (`api/tijori_analysis_cli.py:161/189`). |
| TE | `ingest/tijori_source.py:377`, `fetch_events`; `tijori_events.py`, `build_tijori_events`; company fragment builder in `tijori_events_company.py` | `data/raw/watchlist/tijori-events/<stock-or-market>/<surface>.raw.html` + typed JSON/hash/time; parsing all requests precedes writing (`api/tijori_events_cli.py:199/227`). |
| ID | `entity/discovery.py:541`, `_vendors`, with `screener_search_url(:163)` and existing onboarding GET sender (`api/onboard_cli.py:263`) | Successful search/page bodies logged in memory, generation files via `write_generation(:335)`, then `register_capture(:647)` / snapshots. Search parsers verify identity; not a universal retain-before-interpret path. |

Prefixes in this table are `src/fundamentals/`. `—` in a matrix means no implemented surface-specific fetch/parser found, not a rights denial. A generic transport capable of arbitrary GETs does not count as an acquisition implementation.

## 4. Screener coverage matrix

Fixture keys: F = `tests/fundamentals/test_screener_financials.py` + nested tests; C = `test_screener_company.py`, `test_screener_company_documents.py`, `test_screener_company_hardening.py`; W = `test_screener_watchlist.py` + `test_screener_watchlist_acquire.py`; I = onboarding fixtures/tests. These are checked-in synthetic structure fixtures, not proof that today's entire site is covered. Fixtures were inspected, not executed as a suite.

| ID | Subscriber surface / endpoint family | Fetch; raw retention | Parse / fixture | Disposition |
|---|---|---|---|---|
| S01 | Company document, consolidated and standalone | SP; full page | Session/identity/basis, `test_screener_session.py` | C; used as input; one basis per invocation |
| S02 | Quarterly financials `#quarters` | SP/SF; parent | `read_section`; F | C; used |
| S03 | Annual P&L `#profit-loss`, TTM | SF; parent | `read_section`; F | C; used |
| S04 | Balance sheet `#balance-sheet` | SF; parent | `read_section`; F | C; used |
| S05 | Cash flow `#cash-flow` | SF; parent | `read_section`; F | C; used |
| S06 | Ratios `#ratios` | SF; parent | `read_section`; F | C |
| S07 | Growth ranges within P&L | SF; parent | `read_growth_section`; F | C, partial drift checks; see finding 4 |
| S08 | Level-2 `/api/company/211/schedules/?parent=&section=&consolidated=` | `fetch_schedule`, SF raw schedules | `read_schedule`, `screener_financials_schedules.py`; F | C; discovered parents, not every possible API parameter |
| S09 | Advertised level-3 schedules | SF + `screener_financials_nested.py`, raw schedules | `test_screener_financials_nested.py` | C, partial beyond depth 3; bound is explicit |
| S10 | Shareholding quarterly/yearly page tables | SC parent | `screener_shareholding.py`, `read_shareholding_table`; C | C; D8 also consumes retained pages |
| S11 | Holder buckets `/api/3/<id>/investors/<bucket>/<periodicity>/` | SC raw documents | `read_investor_bucket`; C | C; disclosed holders only, source's ≥1% rule retained |
| S12 | Product segments, quarterly/annual `/api/segments/...` | SC raw documents | `screener_segments.py`, `read_segments`; C | C; page-advertised types only; unlinked geography `/2/` historically exists, not traversed |
| S13 | Related-party `/results/rpt/211/consolidated/` | SC raw documents | `read_related_party`; C | C; URL-bound, not body-verified |
| S14 | Company corporate-action modal `/company/actions/211/` and offered tabs | SC raw documents | `read_corporate_actions`; C | C |
| S15 | Peers `/api/company/6594631/peers/`, chosen columns | SC raw documents | `read_peers`; C | C; body self-row/basis verified |
| S16 | Header/default and custom quick ratios | SC parent + `/api/company/6594631/quick_ratios/` raw | `read_quick_ratios`; C | C; captures owner's selected ratios, not whole field library |
| S17 | Direct formula `/screen/raw/?query=...` + CSV export | SX, snapshots after validation | Formula echo, CSV, result count; screen-export fixtures | C; only configured formulas; export POST not live-tested |
| S18 | Core/named watchlist HTML and CSV | SW | Table/export cross-check; W | C, partial: other list names reported, not auto-captured; industry grouping unverified |
| S19 | Company autocomplete `/api/company/search/` | ID; generation/snapshot | Identity resolver; I | C; bounded symbol search |
| S20 | About, business/key points, analysis pros/cons and headline company metadata | SP/SF/SC parent | No dedicated content parser | R; retained but mostly unused |
| S21 | `#documents`: annual-report, rating, concall transcript/PPT/recording link tables | SP/SF/SC parent | Financial PDF-row hrefs only; no complete documents-section reader in this checkout | R, partial: listings retained, linked bytes not fetched |
| S22 | Inline recent announcements inside `#documents` | SP/SF/SC parent | No dedicated reader | R; recent subset only |
| S23 | Company chart JSON: Price/volume/DMAs, PE/EPS, sales/margins, EV/EBITDA, PB/book, market-cap/sales; time ranges | —; live sample `/api/company/211/chart/` captured only by audit | — | M |
| S24 | Company trades `/trades/company-211/` | —; live 200 | — | M |
| S25 | Company insights quarter/flags `/insights/company/211/...` | —; flags live 200, quarter GET 405 | — | M; quarter interaction method not verified |
| S26 | Extended commentary `/wiki/company/211/commentary/v2/` | —; navigation GET 302 | — | M; modal access not verified |
| S27 | Annual-report AI summary `/annual-reports/<id>/summary/` | —; live 200 | — | M |
| S28 | Concall AI summaries `/concalls/summary/<id>/` | —; one live 200, 55 page hooks | — | M |
| S29 | Actual annual reports, rating PDFs, results, transcripts, presentations and announcement attachments; historical company announcement fragments/search | —; recent/important fragments live 200; external links not followed | — | M; parent link retention does not retain documents or full history |
| S30 | Concall recordings / audio/video links | — | — | M; links in parent only, third-party hosts need host-specific handling |
| S31 | Company Export-to-Excel workbook | —; historically advertised | — | M; access/method not exercised |
| S32 | `/market/` + macro-sector/sector/industry/basic-industry pages, tables and exports | —; overview and APAR's industry page live 200 | — | M; historical 12/22/58/188 hierarchy needs refresh |
| S33 | Market Pulse `/filings/` summary | —; live 200 | — | M; this is trades/actions, not a filings API |
| S34 | Market announcements `/announcements/`, filters/Show More | — | — | M |
| S35 | Latest/upcoming concalls `/concalls/`, `/concalls/upcoming/` | —; both live 200 | — | M; includes links/summaries/filter/pagination variants |
| S36 | Market annual-report feed `/annual-reports/` | —; live 200 | — | M |
| S37 | Upcoming results `/upcoming-results/`, watchlist/month/page filters | —; live 200, 25 first-page rows | — | M |
| S38 | Latest results `/results/latest/`, month and pagination | —; live 200, 25 result tables | — | M |
| S39 | `/fii/` flows, sector AUM/fortnight/history charts | —; live 200 | — | M |
| S40 | Market bulk/block/SAST/insider trades and detail | —; navigation links observed | — | M |
| S41 | Market bonus/right/split/buyback/dividend feeds | —; navigation links observed | — | M |
| S42 | `/ipo/` upcoming/recent/below-IPO/rights | —; live 200 | — | M |
| S43 | `/people/` shareholder search, trending investors, person holdings pages | —; search landing live 200; holder person links retained but not followed | — | M |
| S44 | `/ratings/` company rating search/feed | —; landing live 200 | — | M |
| S45 | `/hs/` commodity/product-price search and historical series | —; landing live 200 | — | M |
| S46 | `/explore/`, `/screens/`, owner's saved/public screens, definitions, sorts, pages, exports | —; explore and one owner's saved screen live 200 | Raw-formula lane S17 does not enumerate saved screens | M |
| S47 | `/user/columns/`, `/user/quick_ratios/`, `/ratios/`, custom-ratio definitions/library | —; first two live 200 | — | M; S16 captures selected values only |
| S48 | Feed `/`, dashboard `/dash/` and watchlist-specific news | —; both live 200 | — | M |
| S49 | Notebook `/notebook/`, company notes `/notebook/211/`, export | —; aggregate live 200, company navigation 302; no export POST | — | M |
| S50 | Alerts/preferences/profile/premium account state | —; historically reachable and current navigation linked | — | M; read-only metadata only; settings writes outside task |
| S51 | Screener AI existing company view, answers and usage | —; current company hook/navigation observed | — | M; no new paid inference or mutation invoked |

## 5. Tijori coverage matrix

Fixture keys: F = `test_tijori_tables.py`, `test_phase3_tijori_retention.py`; O = `test_tijori_overview.py`; H = `test_tijori_shareholding.py`; A = `test_tijori_analysis.py`; E = `test_tijori_events.py`. All paths are under `tests/fundamentals/`. Missing surfaces have no dedicated fixture/parser in the inspected checkout.

| ID | Subscriber surface / endpoint family | Fetch; raw retention | Parse / fixture | Disposition |
|---|---|---|---|---|
| T01 | Financials `fin_tables_data`: all 15 quarterly/P&L/BS/CF/ratio/growth keys, both bases, summary/detail | TF; full HTML before table parse | `build_all_tijori_tables`; F | C; all 15 parsed live |
| T02 | Shareholding detailed HTML tree `#company_detailed` | TS; ordinary CLI no raw, D8 separate retained lane | `build_tijori_shareholding`; H | C; 29 rows live; raw gap in ordinary CLI |
| T03 | Shareholding rendered breakup charts | TS; same raw gap | `tijori_shareholding_breakup.py`; H | C; one breakup parsed live; does not cover every Trend widget |
| T04 | Overview `corporate_actions` | TO; no raw in ordinary CLI | `build_corporate_actions`; O | C, retention partial |
| T05 | Overview `ratios_table` | TO; same | `build_ratios`; O | C, retention partial |
| T06 | Overview `custom_fin_table`, custom statement/KPI rows | TO; same | `build_custom_financials`; O | C; values present, extra metric history T18 requires API |
| T07 | Market share `ms-charts` | TO; same | `build_market_share`; O | C |
| T08 | `peers_table_data` | TO; same | `build_peers`; O | C; configured comparison fields |
| T09 | `price_returns` | TO; same | `build_price_returns`; O | C |
| T10 | `intraday_price` | TO; same | `build_price_series`; O | C |
| T11 | Legacy `price_chart` island | TO; same | `build_price_series`; O | C **historical/partial**: absent live; current price API T30 missing |
| T12 | `price_chart_peers` | TO; same | `build_price_chart_peers`; O | C |
| T13 | `company_details_data`, identity/headlines and `quick_look` forensic flags | TO; same | `build_company_details`, `tijori_overview_company.py`; O | C; flags/unknown payloads retained structurally, not every forensics interaction |
| T14 | Revenue mix: product/location/profit/assets breakup variants | TO; same | `tijori_overview_revenue_mix.py`, `build_revenue_mix`; O | C; 17 elements live |
| T15 | `/api/v1/ind/fund_flow_analysis_data/4290/`, all returned windows | TA; raw after parse | `build_fund_flow`; A | C; 74 elements live |
| T16 | `/api/v1/ind/balance_sheet_snap_shot/4290/` | TA; raw after parse | `build_balance_sheet_snapshot`; A | C; 10 elements live |
| T17 | `/api/v1/ind/cash_flow_waterfall/4290/` | TA; raw after parse | `build_cash_flow_waterfall`; A | C; 70 elements live |
| T18 | `/api/v1/ind/company_op_metrics/4290/<metric>/` | TA; raw after parse, **manual IDs** | `build_op_metrics`; A | C, partial: default breadth skips it despite 12 discoverable URLs |
| T19 | Upcoming results `/results/upcoming-events/` first document | TE; raw after parse | `build_upcoming`; E | C, partial: 20 rows, no continuation |
| T20 | `/results/quarterly-results/` first document | TE; raw after parse | `build_quarterly_results`; E | C, partial: 20 items, no continuation |
| T21 | `/in/timeline` filter taxonomy/watchlists/portfolios/sectors/scalars | TE; raw after parse | `build_site_timeline`; E | C; 231 taxonomy/list elements, **not events** |
| T22 | `/timeline/company/?company_id=4290&timestamp=0` | TE; raw after parse | `build_company_timeline`; E | C, partial: 40 events, initial cursor only |
| T23 | Company autocomplete `/api/v1/ind/company_search/` | ID; generation/snapshot | Identity resolver | C; bounded identity search, not all search modes |
| T24 | Formula `/api/filter_queries/advanced_search/` including returned columns | TX; snapshots after checks | Formula echo/count/row checks; screen-export fixtures | C; configured formulas only; not exercised live |
| T25 | Financial-page extra islands: `company_details`, `peersList`, `metrics`, locks, plan | TF whole HTML | Identity/access subset parsed; remainder no complete parser | R; retained unused fields remain reparseable |
| T26 | Reverse DCF HTML/input defaults in financial page | TF whole HTML | Explicitly excluded from overview contract | R **shell/defaults only**; interactive outputs not acquired |
| T27 | Overview About, brands, customers, connections, knowledge-base, `memoryOverviewKeyEvents`/memory-overview content | Whole overview only via conditional D7 retained read | No complete section-specific reader | R, conditional/partial; lazy extensions must be discovered |
| T28 | `#companyFilings` listing and concall-summary controls | Same conditional overview retention | No complete listing parser here | R, partial: 135 hrefs, no attachment bytes |
| T29 | Shared `user_prefs`, plan/access/view metadata, pagination configuration | TF parent; some TO/TE fields modeled | Partial metadata readers only | R; not a complete subscriber-preferences capture |
| T30 | Current historical price/valuation chart API `/api/v1/ind/chartdata/4290/<metric>/` | —; price variant live 200 | — | M; legacy T11 does not fetch it |
| T31 | `/api/v1/ind/capex/4290/`, `/debt/4290/` and chart key-event overlays | —; first two live 200 | — | M |
| T32 | Shareholding Overview/Trend tables and trend histories/interactions | TS fetches the parent but ordinary CLI loses its raw; targeted parser selects detailed table only | No complete Overview/Trend parser | M for durable breadth; detailed/breakups counted T02/03 |
| T33 | Benchmarking Financial `#benchmarking-financial`, selected peers/fields | —; tab live 200 | — | M |
| T34 | Benchmarking Business `#benchmarking-business`, revenue/operating-profit comparisons | —; tab live 200 | — | M |
| T35 | `/company/<slug>/reports/`, existing Stack report links/files | —; tab live 200, six links | — | M; entitlement/file retrieval not tested, no purchase invoked |
| T36 | Actual annual-report, earnings-release, presentation and transcript copies on `files.tijorifinance.com` | — | DOCS-1 A1 is a plan; source files absent in this checkout | M; 135 listed APAR documents |
| T37 | Company Con Call Summary modal/content | —; control observed, not document hrefs | — | M; do not confuse with transcript PDFs |
| T38 | Older company timeline pages / cursor continuation | —; `timestamp=0` hard-coded by TE | Existing row parser potentially reusable | M; T22 is only the first batch |
| T39 | Site timeline event feed, filters and subsequent pages | —; shell explicitly declares `xhr_not_acquired`; bare `/timeline/all/` GET 404 | — | M; proper request parameters/flow unverified |
| T40 | Upcoming/latest-result API continuations, filters/date ranges/detail views | —; both page-two APIs live 200 | Existing first-page parsers not wired to pagination | M; site script endpoint paths verified |
| T41 | Upcoming-concall feed within results page | —; empty lazy container declared by TE | — | M; endpoint still needs flow verification |
| T42 | Concall-monitor / external Tijori Stack summaries | —; landing only; referenced summary API GET 404 | Explicitly unavailable in TE | M; cross-product entitlement not verified, not proof of absence |
| T43 | `/in/markets`, index/market data and histories | —; live 200, islands `niche_headers`, `data` | — | M |
| T44 | Industry/sector/niche comparison and index series/search APIs | —; markets scripts reference sector/index endpoints | — | M; per-industry request arguments still need inventory |
| T45 | `/in/macro` indicators/history | —; live 200 | — | M |
| T46 | `/in/raw-materials` commodity data/history | —; live 200 | — | M |
| T47 | `/in/ideas-dashboard/` + 19 linked idea categories/card fragments | —; dashboard live 200; buyback/capex/deleveraging/merger/demerger/fundraise/insider/whales/gainers/losers etc. linked | — | M; finite category enumeration not in code |
| T48 | `/dashboard/` subscriber feed/cards | —; live 200 | — | M |
| T49 | `/in/watchlist`, every list's membership, columns, company association `/in/watchlist/company/4290` | —; list and membership live 200 | — | M; TE only preserves list names/IDs as timeline filters |
| T50 | `/in/portfolio/`, existing holdings/family summaries | —; live 200 (slashless path 301) | — | M; no trading or account mutation attempted |
| T51 | `/in/search`, `/filter/`, saved/public/popular queries and query metadata/results variants | —; search/popular/saved landing pages live 200 | TX only executes specified financial formula | M |
| T52 | `/in/edit-columns/`, custom ratios/financial definitions and libraries | —; financial-column GET live 200 | — | M; selected values T06 do not preserve definitions |
| T53 | Alerts, account/subscription/readable saved configuration and change log | —; navigation-linked; not exercised for account state | — | M; settings writes excluded |

## 6. Ranked findings and concrete failure scenarios

### 1. P1 — Broad capture coverage is missing, including discoverable data behind retained HTML

Observed-code: `src/fundamentals/contracts/source_catalog.py:274` authorizes only seven `screener-subscriber` surface names and five Tijori names; `screener/SCREENER_DOCS` is a separate declaration. This is an authority table, **not an extraction inventory**. It does not route the numerous overview/analysis/events CLI artifacts into registered captures. `tijori_overview_models.py:61` enumerates 11 sections; no benchmarking/reports/market/watchlist acquisition is implemented there. `screener_company_models.py:162` enumerates only six company parts.

Observed-live: historical price moved from an HTML island into the chart API, and document/summary controls point to separate bodies. Retaining the parent alone cannot reconstruct them. **Failure:** an owner revisits an old chart or concall after the vendor changes it; we have neither that API response nor the summary/document, despite retaining the parent page.

Smallest fix: add the missing raw GET requests to the existing capture paths, including page-advertised metric URLs; register each response separately with the request, outcome, hash and retrieval instant. No financial/parser model is needed for unused surfaces. Capture-only work is independent of later semantic extraction. Do not count the approved DOCS-1 plan as shipped code in this checkout: its proposed `documents_cli`/`tijori_documents` files are absent; its explicitly excluded Stack reports, summaries and recordings still remain Lane 0 gaps even after that plan lands (`docs/plans/DOCS-1-first-party-document-intake.md:20`).

### 2. P1 — Raw-first is not an end-to-end invariant; some parsed surfaces retain no raw response

Observed-code:

- `api/tijori_overview_cli.py:78/96` and `api/tijori_shareholding_cli.py:72/83` fetch parsed objects and write JSON only. Their source methods return no raw body (`ingest/tijori_source.py:283/309`). A hash in an artifact cannot recreate the HTML. Thus every overview section and ordinary detailed-shareholding/breakup capture on those commands is **parsed without raw retention**. D7/D8 retained routes are exceptions, not a repair of these commands.
- `ingest/tijori_source.py:227` (`fetch_pl`), `:247` (`fetch_table`) and `:266` (`fetch_all_tables`) also discard page bytes after parsing. `api/goal_runner.py:677` still calls `fetch_pl`; the legacy Screener goal path calls `ScreenerSource.fetch` at `goal_runner.py:635`, whose return excludes bytes (`ingest/screener_source.py:329`). This is not dead API surface.
- `api/tijori_analysis_cli.py:161` and `api/tijori_events_cli.py:199` eagerly fetch/parse **all** requested documents before their first disk write. A malformed last API response loses earlier successful responses too. Each source method builds the parsed artifact before returning its raw-body wrapper (`tijori_source.py:366/412`).
- Screener `read_financials/read_company` run before `_publish` (`api/screener_financials_cli.py:184/190`, `api/screener_company_cli.py:180/187`). Expected part/schedule refusals often survive in in-memory lists and are then published: good, but not durable raw-first. A page identity/basis failure inside `fetch_company_page` (`screener_session.py:143`) returns no bytes to its caller; a discovery exception before the sweep also prevents publication. `_publish` rollback deletes this invocation's raw files if later artifact output fails (`screener_company_cli.py:260`, `screener_financials_cli.py:268`).
- Both formula exporters validate before a `VendorExport` can reach `coverage/screens.py:156` for storage (`ingest/screen_export.py:150/198`). Failed formula echoes/counts/schema responses are therefore not durable captures. Onboarding likewise logs/decodes before generation/snapshot publication (`entity/discovery.py:312/335`).

**Failure:** a site changes one label or island; parsing raises, and the exact response needed to update the parser is lost. Fix the order at these composition roots: persist bounded response bytes and the capture record first, then parse retained bytes, then write a separate extraction outcome. Keep failed extraction evidence when publishing the extraction fails. Reuse `SnapshotStore`; no new generic scraping framework.

The best existing example is `tijori_retention.py:109`: it stores every classified financials attempt, rereads the retained body and only then builds tables (`:134`). Auth/identity classification occurs before storage (`tijori_capture.py:285`), but those errors become stored outcomes rather than escaping. Strictly, even this path interprets classification islands before persistence; it nevertheless preserves the response on classified schema/auth failures.

Additional timestamp gap: `screener_company_sweep.py:78`'s retained `CompanyDocument` stores raw/hash/URL but drops `fetched_at`. Successful parsed cell provenance carries the response time, while a failed-to-parse document's failure record has no independent retrieval instant (`screener_company_artifacts.py:461`). The top-level time is the **parent page's** time (`screener_company.py:167`). Use one capture record per response so an unparsed/failed body is independently timed.

### 3. P1 — “Keep everything” conflicts with the active vendor-expiry policy

Observed-code: `retention/eligibility.py:20/56` makes VENDOR/IDENTITY bytes eligible after 12 months. `migrations/0027_retention_classes.sql:9/19` classifies Screener/Tijori as vendor; the covered-stock exemption is specifically for exchange-refetchable captures (`:116`). Open queue/screen holds can extend vendor retention, but merely using a capture in a report does not grant perpetual preservation (`retention/eligibility.py:23/42`). Licence-end handling is also explicitly destructive by policy.

**Failure:** a correctly captured unused response is purged a year later, defeating an unqualified requirement to keep it for future reparsing. This audit did not run a purge or inspect live retention rows. The smallest change is an explicit retention-policy amendment for this authorized keep-all vendor collection, followed by its narrow implementation/migration and purge tests. Do not silently reinterpret the new owner's instruction as the older 12-month policy, or silently change all first-party retention.

### 4. P1 — Some layout drift becomes false absence or partial success

Observed-code: `screener_company_discovery.py:153/183` finds advertised handlers but silently `continue`s when the regex no longer parses. `screener_financials_tables.py:310/316` does the same for schedules. The regexes allow either quote style, but require `name(` without a separating space (`company_discovery.py:87/92`, `financials_tables.py:70`).

Fresh offline check against this walk's APAR page: changing only valid JavaScript formatting to `showSchedule (...)`, `showShareholders (...)`, `showSegment (...)` changed discovered counts **15/9/2 → 0/0/0**, without an exception. A subsequent segments-only `read_company` returned **`complete=True`, `offered=False`, no failures, zero segment tables, one page request**. `screener_company_parts.py:210` calls that missing hook `NOT_OFFERED`. This is a concrete false issuer-property result caused by layout/handler drift.

Other example: `screener_financials_tables.py:265` skips growth rows whose cell count is no longer two; a third display column can silently remove a row, while a section with surviving range tables remains OK (`:295`). The legacy quarterly parser ignores renamed headline rows and extra unmatched columns, raising only if **all** observations disappear (`screener_source.py:241/246/264`).

Smallest fix: for these observed handler-bearing elements, refuse/report any handler that cannot be decoded; tolerate the valid spacing change in the local regex. For the growth table, distinguish its header from data rows and record/refuse malformed data rows. Add mutation fixtures for these exact changes. This does not require a general JavaScript interpreter, schema registry or page-wide strictness.

### 5. P2 — Implemented APIs are omitted by default, and pagination is not acquisition completeness

Observed-code: `tijori_analysis_models.py:95` and CLI help claim IDs are not published; `api/tijori_analysis_cli.py:115` therefore skips metrics without `--metric-id`. The live APAR page contradicts that premise with 12 explicit URLs. Existing builders already support the responses: discovery is the missing small step.

`tijori_events_models.py:58` hard-codes company `timestamp=0`; `tijori_source.py:403` fetches just one URL. `tijori_events.py:283` records `declared_shown/declared_total`, but fetch logic does not continue. Live page-two result APIs work. **Failure:** a command succeeds with 20 items or 40 events, and a consumer assumes it captured the history. The capability reporting correctly says the site timeline feed is absent; it does not make result/history pagination complete.

Smallest fix: discover advertised metric URLs, retain each; follow the site's evidenced continuation/cursor until exhausted, with a run budget and a recorded incomplete checkpoint if it cannot finish politely. Reuse the existing row readers when the returned fragment matches. Report captured vs declared counts separately. Do not invent routes for the two 404s observed here.

### 6. P2 — Surface boundaries exist, but several files still combine unrelated layouts

Observed-code count: **59 files, 24,388 lines** for exactly `ingest/screener_*.py`, `ingest/tijori_*.py`, `api/screener_*_cli.py`, `api/tijori_*_cli.py`. No file is at or above 800 lines. The largest are:

| File under `src/fundamentals/ingest/` | Lines | Assessment |
|---|---:|---|
| `tijori_events_models.py` | 782 | Mostly contracts for several event surfaces; size alone is not a defect. |
| `tijori_source.py` | 778 | 27 methods/functions; transport, page verification, financial/shareholding/overview/analysis/events entry points. Concrete coupling: `tijori_screen_fetch.py:1` documents a separate fetch module because edits to this file would drift an extractor pin. |
| `screener_financials_models.py` | 765 | Contracts, URL rules, schedule vocabulary; cohesive enough to avoid a size-only rewrite. |
| `tijori_tables.py` | 751 | Contracts plus recursive table building; one island family, not 15 independent HTML parsers. |
| `tijori_events_html.py` | 692 | Several event layouts collected in one file. |
| `tijori_events.py` | 691 | Several event builders, auth and metadata handling. |
| `screener_financials_schedules.py` | 688 | Schedule-family semantics, largely one responsibility. |
| `tijori_overview_models.py` | 687 | Multiple section contracts; no need to split just for line count. |

`screener_company_fragments.py` (675 lines) owns four different layouts: related party, actions, peers, ratios (`read_related_party:128`, other readers in the same file). `tijori_overview_sections.py` (575) owns actions/ratios/custom financials/market share/peers/price builders. These are not one-module-per-surface. Constants/locators are generally local and named, but are spread across `*_models`, `*_discovery`, `*_tables`, `*_fragments`, and the independent legacy parser. A shared class rename can therefore touch several files.

Duplication: AST comparison found the same `_collect_anchors` body in `tijori_overview_common.py:232`, `tijori_analysis.py:220`, `tijori_events_common.py:268`; their collision **policies differ**, so do not blindly merge all three validators. More consequentially, `screener_source.py:208` and `screener_financials_tables.py:196` independently parse the same quarterly-table layout with different partial-data and retention behavior. The legacy parser is still called by the goal runner. **Failure:** one site label/layout correction lands in the subscriber parser, while the legacy goal path quietly emits a reduced set.

Smallest action: fix the live capture gaps first. When changing a particular layout, move only that parser and its selectors into one small module if it reduces the touched files. Route the remaining legacy quarterly consumer through the retained parser when that consumer is next changed. Keep a shared anchor-walk helper only if another fix requires touching all copies. A blanket 24k-line rewrite or arbitrary 800-line slicing is not justified.

## 7. Good practices and fixture evidence to keep

| Practice | Concrete source/test evidence | What it prevents |
|---|---|---|
| Auth, identity and basis checked positively | `screener_session_page.py:156`; `test_screener_session.py:227/247/416`; `tijori_source.py:740` | Anonymous HTTP-200 pages, wrong warehouse/basis, peer-company decoys becoming facts. |
| Endpoint-specific basis rules, not a shared guessed flag | `screener_financials_models.py:488`; `screener_company_models.py:14`; `test_screener_financials.py:48` | Schedules use key presence; segments require value `true`. Reusing one rule would return standalone data. |
| Page-driven hooks, scoped sections, duplicate/ambiguity checks | `screener_company_discovery.py:108/297`; `screener_company.py:100`; hardening fixtures | Wrong section/duplicate control selection; keep it and close the demonstrated unparsed-hook hole. |
| Missing owner section is drift, distinct from absent control | `screener_company_sweep.py:57`, owning sections in `screener_company.py:103` | Calling an entire removed section “not published.” |
| Refused sub-document evidence and partial-run state | `screener_company_sweep.py:161`; `screener_financials.py:298`; `test_screener_company_hardening.py:101` | One bad modal discarding other completed parts, and a limited run claiming full acquisition. Persistence timing still needs finding 2. |
| Tijori duplicate-island conflict and precision handling | `tijori_page.py:125/147`; `tijori_common.py:85`; `test_tijori_overview.py:120` | Conflicting duplicates accepted by order; JSON floats destroying decimal lexemes. Identical known duplicates remain legal. |
| Strict structural/schema failures | `tijori_shareholding_table.py:92`, `tijori_analysis.py:541`; `test_tijori_analysis.py:427/531` | Missing `data` becoming OK-empty; malformed nested rows becoming fabricated values. |
| Unknown/malformed data preserved and status exposed | `tijori_tables.py:738`; `tijori_overview.py:186`; `test_screener_financials.py:152/165`; `test_tijori_overview.py:303/836` | Unknown fields lost, ragged rows shifted under wrong period, invalid charts reported as empty. |
| Honest source identity/verification strength | `tijori_analysis_models.py:37`; `screener_company_artifacts.py:413`; investor/segment fixture assertions | URL-only bindings promoted into body proof; lower-bound holder totals called complete ownership. |
| Per-attempt Screener pacing, bounded reads, redirect refusal, sanitized credentials | `screener_session.py:388/403`; `http_session.py`; `test_screener_session.py:211/300/373` | Leaked cookies, redirected login mistaken for data, rate-limit hammering. Tijori analysis/events loops lack an equivalent shared pacer; add pacing when extending those loops, not parallel requests. |
| Snapshot/no-clobber primitives already exist | `snapshot_store.py:145/254`; `api/artifact_writer.py:50`; `test_phase3_tijori_retention.py:278/366` | Evidence replacement, hash mismatch, parser failure deleting the only retained attempt in the TF path. |
| Capability honesty for static shells | `test_tijori_events.py:666/682`; `tijori_events_models.py:96` | Timeline taxonomy count being mistaken for event count; empty concall container called an acquired feed. |

Fixture coverage is strong for **implemented families**, not for every subscriber surface. Reviewed financial, schedule/nested, company fragments/holders, watchlist, overview/revenue-mix, analysis, shareholding, events and retention files named above. Most fixtures reproduce August TITAN/other-company structures with synthetic values. Fresh APAR replay passed the implemented Tijori families described in section 2. It does not validate missing APIs, pagination, documents or special industry layouts. No recursive test-content search, full-suite run, DB rehearsal or production acceptance was performed.

## 8. Stale research and unchecked assumptions

- `docs/research/screener-tijori-endpoint-inventory.md:7` says Screener HAR capture is pending, despite its later own observations and shipped parsers. Its future Tijori priority list is mostly implemented now; benchmarking/reports/market breadth are not. Its financial `price_chart` island assumption is false on this live APAR page. Its note about the sample five-year estimates modal is useful: this is shared sample content, not proof of company-specific forecasts.
- `docs/research/screener-tijori-acquisition-plan-of-record.md:49` describes the phased build, not current coverage. Its sanctioned-export flip condition fired, as the later inventory records; SX/SW now implement export paths. It is not a current acceptance ledger.
- `docs/research/screener/surface-map.md:151` historically labels watchlist export GET; its later §7 correctly says POST. This audit used no POST. The map's “only three API XHRs” wording is too narrow: its own schedule/investor/segment/modal sections and today's summary hooks show more requests. The historical classification and ratio-library counts were not fully recrawled.
- `scratchpad/vendor-doc-probe/summary.md` remains useful for document link types and category counts. Its distinction between Tijori static transcript listings and the external concall-monitor product is correct. It is a probe, not evidence that document acquisition/parser code has landed. DOCS-1 has an approved A1 plan but absent implementation files in this checkout.
- APAR's controls do not prove that banks, insurance, SME, other sectors or differently entitled pages expose no extra surfaces. Some linked exports/AI interactions require POST or paid actions and were intentionally not exercised. The two Tijori 404s, Screener modal redirects and quarter-insights 405 are unresolved acquisition details, not permission failures or proof the data does not exist.

## 9. Smallest gap-closing plan

Sizes below are **inferred engineering effort for one implementer**, excluding document-volume download time and separate product features; they are not measured completion times. Reuse existing transports, capture records, snapshots and parsers. Add no general crawler engine, new storage layer or parser for unused content.

| Step | Minimal deliverable | Size / risk | Evidence needed to finish |
|---|---|---|---|
| 1 | Make every current acquisition retain a per-response capture before semantic parsing; preserve failures and independent retrieval time. Repair TO/TS/legacy P&L, eager TA/TE/SX ordering. Amend the vendor retention ceiling for this keep-all requirement. | M, 2–3 days; medium/high because persistence and the deliberate purge policy change. | Inject a parser failure after each fetch; bytes/hash/time still readable; replay uses no network. Verify the revised retention rule cannot age out unused covered vendor captures. |
| 2 | Close company breadth with raw captures: APAR-advertised operating-metric URLs, live chartdata/debt/capex, both benchmarking modes, reports, missing overview/Trend content, Screener charts/insights/trades/commentary/AR+concall summaries. Keep endpoint handling beside its surface. | M, 3–5 days; medium, with unresolved modal/entitlement flows. | Inventory every data-bearing hook in each acquired page; every known GET target has a retained response or explicit refusal, not an unmentioned skip. Preserve paid-interaction boundaries; do not generate new paid reports merely to test capture. |
| 3 | Land/reuse DOCS-1 listing/document intake, fetch all vendor-listed originals/copies, and add the out-of-scope summaries/Stack/recording/export surfaces separately where the subscribed account already has access. Raw first; no content extraction unless used. | M/L, 2–4 days incremental engineering plus paced download time; medium/high because multiple hosts, formats, history and private entitlements. | Reconcile all listing hrefs/categories/history to captured blobs or specific gaps; links alone do not count. Preserve vendor-copy/first-party identity and A1 citation rules. |
| 4 | Capture account/site breadth as finite request lists: market/industry/sector, trades/actions/results/announcements, commodities/macro/FII, idea cards, all saved screens/lists/columns and existing readable notes/configuration. Follow evidenced page/cursor continuations with checkpoints. | L, 4–6 days; medium/high discovery uncertainty, especially filtered feeds. | Each matrix M has an implemented raw path and fixture of its request/response structure, or a specifically observed inaccessible state. Reconcile result totals and cursor exhaustion; a shell or page one is not complete. |
| 5 | Close demonstrated drift holes; refresh the inventory from actual capture manifests, and run a polite one-company canary plus a few structurally discriminating fixtures. Extract/split a parser only when a real layout fix would otherwise touch multiple responsibilities. | S/M, 1–2 days initially; medium. | Whitespace-handler and growth-column mutations produce explicit drift; fixture-per-used-parser passes; old captures reparse offline. New unused endpoints need retention/request fixtures, not invented semantic schemas. |

**Before calling the full requirement done:** every inventoried family and newly discovered data-bearing hook needs an explicit disposition; all relevant pages/history/time ranges must exhaust their continuations; every captured response must be durably hash/time-addressed before semantic parsing and retained under the new keep-all policy; every used parser needs an isolated failure outcome and fixtures; report counts must reconcile to retained captures rather than invocation success. Clearly record company universe and acquisition cadence/history scope. This audit is an APAR surface walk, not a full-market history collection or authority to silently narrow “everything” to the current watchlist/first page.

The present evidence supports implementing the gap plan. It does **not** support certifying comprehensive subscriber extraction today.

Final audit verification: all **92 retained response bodies** were reread and matched their recorded SHA-256 and byte counts; the 51-row Screener and 53-row Tijori matrices were mechanically recounted to the totals in section 1. Both external request-start spacings exceeded two seconds. Git status was clean; the report and all audit artifacts are ignored scratchpad files. No product test suite or DB gate was run.

VERDICT: REQUIREMENT NOT MET
