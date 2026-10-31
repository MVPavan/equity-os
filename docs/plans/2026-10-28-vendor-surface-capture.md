# Vendor Surface Capture Implementation Plan

**Origin:** owner decisions 1–9 of 2026-10-28 (VENDOR-SURFACE, epic `eqos-aa6`), applied to the
catalog `docs/research/vendor-surface/` (`catalog.yaml`, `snapshots-index.json`,
`new-surfaces.md`, `not-capturable.md`, `runbook.md`) and bound by the lane 0 audit
`docs/research/2026-10-28-screener-tijori-extraction-audit.md` (§6 findings 1–5, §9 gap plan).
No separate spec: the owner decisions are the spec. Revision 2 applies the orchestrator's 28
rulings on Sol's first review (REVISE, 28 findings) and its size cuts; revision 3 applies the
15 accepted findings of the second review (REVISE); revision 4 applies the orchestrator's
rulings on the residual findings of the third. The orchestrator creates the bd stage per task
under `eqos-aa6`; this draft had no bd access.

**Status:** approved by orchestrator ruling after three Sol rounds (2026-10-28).

**Goal:** every non-account Screener and Tijori surface is fetched on a schedule for the covered
watchlist (and once for on-demand stocks). Each response is registered as a capture before any
parsing, and every number is read by code into append-only stored values keyed by cell
position. A small model only proposes group-3 label mappings and selects free-text spans; code
accepts or rejects each proposal. One command catches silent drift.

**Out of scope:**
- Account pages (watchlists, portfolio, alerts, saved screens, profile, settings, plans). They
  are never fetched; the list is in §2.
- Off-host bodies: BSE/NSE PDFs, rating agencies, `files.tijorifinance.com`, Excel downloads,
  issuer IR sites. These belong to DOCS-1 (`docs/plans/DOCS-1-first-party-document-intake.md`).
- Everything in `not-capturable.md`: POST, action, XHR-only flows other than the GET modals named
  here, AI routes and payment.
- Stocks outside the universe (decision 5). This excludes `screener:pre-listing-company`.
- **Raw-loss paths outside this workflow.** This plan fixes the raw-loss paths its own commands
  invoke (the new capture path, and the `tijori-overview` and `tijori-shareholding` commands in
  Task 20). It does **not** close the audit's finding 2. Each remaining path becomes one
  follow-up bead, filed by the orchestrator when this plan is approved:
  1. onboarding decode before publication;
  2. screen-export validation before storage;
  3. legacy P&L: `goal_runner` `fetch_pl` and `ScreenerSource.fetch`;
  4. eager `tijori-analysis` and `tijori-events`;
  5. Screener `_publish` rollback.
- Editing pinned parsers to fix the audit's drift holes. This plan detects those holes (Task 19)
  but does not repair them.
- Promoting vendor values into the canonical fact store or reconciliation. Values here are
  vendor observations, not admitted facts. G0 adapters (Task 8) store reader output as vendor
  values only.
- Extending the canonical dictionary with operating-KPI fields.
- Changing the vendor retention window or any other eligibility rule beyond the one hold-root
  member in Task 1. Licence-end deletion is unchanged.
- Parsers for surfaces with no retained 200 response (§2, "pending a 200"). They are captured and
  kept; their parsers are written when a retained 200 exists (one follow-up bead).

**Constraints:**
- Invariant 6: the LLM is never the authoritative calculator. No number comes from a model.
- Invariant 7: every material numerical claim links to a fact ID or calculation trace. Here every
  stored value carries its `capture_ref_id`, its cell position and its verbatim `raw_text`.
- Invariant 8: output is labelled by epistemic class (`EpistemicClass` in
  `contracts/guidance_claim.py`). Code-read cells are `observed`. An accepted model mapping and a
  model-selected claim span are `inferred`, never `observed`.
- Invariant 9: facts are append-only and revision-aware. The new tables reject UPDATE, DELETE
  and TRUNCATE except the licence-end tombstone, and a reparse appends rows under a new parser
  version.
- Invariant 10: missing inputs fail closed. An unaccepted mapping stays unmapped, an unreadable
  expected cell makes the outcome `PARTIAL`, and a failed parse is `FAILED`, never empty.
- Invariant 13: point-in-time capture starts with the first build.
- Frozen code: do not edit committed migrations (0001–0043, with 0043 from DOCS-1), frozen
  manifests (including `ledger_stage5_manifest.yaml`), any file hashed in
  `compare/run_config.py` `VENDOR_EXTRACTORS` (for example `ingest/tijori_source.py`,
  `tijori_tables.py`, `tijori_page.py`, `tijori_common.py`, `screener_session_models.py`,
  `screener_session_page.py`, `screener_financials_*.py`, `screener_company_discovery.py`,
  `screener_company_models.py`, `screener_company_artifacts.py`, `screener_shareholding.py`,
  `tijori_shareholding*.py`), `evidence/vendor_ingest.py` or `pg/legacy_import.py`. Importing
  them is allowed. New behaviour goes in new modules and new migrations (0044 and 0045; 0043 is
  DOCS-1, which merges first).
- Python rules: `.claude/rules/python/{coding-style,testing,safety}.md`. That means frozen
  Pydantic models, enums for fixed sets, mypy strict, structlog, no `os.environ` in business
  logic, timeouts on all I/O, and `uv` only.
- Owner code-size rule: smallest code that meets each decision. The orchestrator checks each diff
  against the task's size estimate (§3); an overrun of more than 30% needs a stated reason.
- Do not copy vendor values into committed files. Retained bodies stay under gitignored `data/`.
  Test assertions may name a handful of hand-read cell values.
- Times: every stored time derives from the capture's `retrieved_at` or the store clock
  (`Registration.store_clock`), never a fresh `now()` inside parsing or storage.

## 1. Design in one page

**Single fetch path.** New module `ingest/vendor_surface_fetch.py`. Every GET this plan issues
goes through `VendorFetcher.get`, which applies these rules in order:
1. URL boundary: scheme `https` only; the authority must equal the site's exact authority
   (`www.screener.in` or `www.tijorifinance.com`, no port, no userinfo).
2. The path is normalised (percent-decoded once, dot segments removed, duplicate slashes
   collapsed) **before** the runbook §1 deny-list (path-segment words, query keys, named paths,
   two allowed exceptions). A denied URL raises and is never fetched.
3. GET only.
4. Durable stop: if `STOP-<site>` exists under the stop directory, the site is refused.
5. Cross-process exclusivity: one session advisory lock per site
   (`pg_try_advisory_lock(hashtext('eqos.vendor_surface.<site>'))`), held for the command. A
   second command on the same site refuses at start, so pacing and stop state are never split
   between processes. No cross-process pacer exists in the repo; this lock is the smallest
   substitute.
6. A per-site `RequestPacer` from `ingest/http_session.py` at 1.5 s
   (`DEFAULT_MIN_REQUEST_SPACING_SECONDS`).
7. The session cookie, never logged.
8. `NoRedirectHandler`: redirects are never followed; the `Location` header is kept.
9. The body is read through `read_bounded_capture`; its `BodyCompleteness` is preserved on the
   capture record (a `PARTIAL` or `ABSENT` body is never stored as `COMPLETE`).
10. **Registered before anything else.** `SnapshotStore.put_capture` writes the body and record,
    then the capture is registered in `eqos.capture_refs` through `capture_registration(pool)` /
    `Registration.insert` (with its URL in `capture_addresses`). The registration trigger
    classifies it `VENDOR`, so backup (`pg/backup.py`) and purge (`retention/purge.py` blob
    inventory) see it. Source ids `screener-subscriber` and `tijori`; surface `vs.<catalog-id>`;
    request key = sha256 hex of the URL (the `entity/discovery.register_capture` convention).
11. A 403, 429 or 503, or a 3xx whose `Location` path contains `login` or `signin`, is stored,
    and `SiteStopped` is raised **carrying the stored `Fetched`**. The
    capture coordinator (`capture`, Task 4) registers it, records its outcome `UNUSABLE` with the
    refusal in `detail`, and writes `STOP-<site>` in `finally`, holding the site lock throughout. The marker stays until a person
    removes it after diagnosis (runbook §6).
12. A per-site budget of 350 requests per command. Work over the budget stays due.

The existing adapters (`ScreenerSessionSource`, `TijoriSource`) stay as they are.

**Surface table.** `config/vendor_surface/surfaces.yaml` is a finite list: one entry per fetched
catalog id, giving id, site, scope, path template, parse group, cadence, `xhr` and, for
templated children, the **name** of an expansion function (`expand: tijori_op_metrics`). There
is no general `parent + param_pattern` mechanism. Expansion functions are small named functions
in `vendor_surface_expand.py`, each reading one parent's retained body. Catalog metadata
(`url_pattern`, `scope`, reference sha256) is read from `catalog.yaml`, never copied.

**Section contract.** A parent page capture (Screener company page, Tijori overview, financials,
shareholding and benchmarking pages) is fetched once and parsed into one tree once. The parent
dispatches each section parser listed for it in the surface table (`sections: [...]`). Each
section yields its own outcome keyed by its **logical surface id** (for example
`section-documents`) and the parent's `capture_ref_id`. Sections are never fetched.

**Parse after registration.** `ingest/vendor_surface_parse.py` holds one registry,
`PARSERS[(site, surface)] -> ParserEntry(version, parse)`. A parser reads the bytes the store
hands back (`store.read_body`), never the in-memory bytes, plus a `ParseContext` (Task 4): the
request's verified `CompanyIds` (identity, bound `BasisTopology`, warehouse and vendor ids),
the requested basis, the retrieval context (`url`, `retrieved_at`, body sha256, capture id) and,
for a child, the parent input its reader needs. Nothing in the context is read off the response.
One transaction writes the outcome row and all its values:
- `eqos.vendor_outcomes`: one row per (capture, logical surface, parser version). Status `OK`,
  `PARTIAL`, `EMPTY`, `FAILED`, `UNUSABLE` or `KEPT`, kept separately from the HTTP outcome.
- `eqos.vendor_values`: one row per cell or point, keyed by (`table_key`, `row_index`,
  `column_index`) with a source `locator`; labels are data.

Parser versions are namespaced by site and surface: `<site>:<surface>.v<n>` for new parsers and
`<site>:<surface>.reader.v<n>` for G0 adapters, with `<site>` `screener` or `tijori` (for example
`screener:company-search-api.reader.v1`). Two sites' same-named surfaces never share a version.

**Topology never blocks capture.** Every surface of every covered or on-demand stock is fetched
and kept whatever its topology state. Topology gates only the parsing and usable status of
**basis-scoped** requests (`Request.basis` set: the Screener company page per basis, its
statement sections, schedules, segments and the other per-basis requests). With no bound
topology, each basis-scoped capture gets an `UNUSABLE` outcome (`detail`: `topology unknown`)
under the gate version `<site>:gate.topology.v1`, is listed in the report's `incomplete`, and
nothing else stops. Once a topology is bound, `vendor reparse` (and the next run) parses those
captures under the real parser version. The topology comes from verified vendor-binding
evidence keyed to the registry entity (Task 7), in order: `config/watchlist.yaml`; the
onboarding verification's consolidated page capture (`entity/discovery.py:550`,
`entity/verification.py:282`); a first-capture verification of the two registered company pages.
An unmarked single-basis page leaves that basis unknown; standalone-only is never inferred
(`screener_session_page.py:141`).

**Usable.** A capture is usable when its outcome status is `OK`, `PARTIAL`, `EMPTY` or `KEPT`.
HTTP errors, stops, failed identity or basis checks (`read_page_evidence`,
`classify_financials_body`) and `FAILED` parses are not usable. A body whose `BodyCompleteness`
is not `COMPLETE` is kept as a prefix, but no parser runs on it and its outcome is `UNUSABLE`,
for every group including G4 `KEPT`: it never completes an acquisition or satisfies cadence.
Only a usable capture satisfies cadence.

**Group 0.** Surfaces with existing readers get thin adapters (Task 8) that call the reader on
the retained bytes with its existing inputs (from `ParseContext`) and convert its output to
`VendorValue` rows. No second reader is written. A G0 reader that cannot run is an incomplete
outcome, never `KEPT`.

**Model.** `ingest/vendor_surface_model.py` holds one OpenAI-compatible chat-completions adapter
with response-byte, output-token and retry bounds. `config/vendor_surface/model.yaml` has
`model_id: null` until the owner selects one; the runtime commands refuse without it. The model
only proposes label → field mappings (code accepts or rejects, Task 16) and selects text spans
(code stores the span text, Task 18).

**Retention.** Owner decision 7 (2026-10-28): vendor-surface captures are kept. Task 1 adds a
keep-all hold root, `VENDOR_SURFACE_KEEP`, matching registered captures whose surface starts with
`vs.`. The age-based vendor window, its tests and the frozen Stage 5 oracle are untouched.
Licence end still wins (it is checked before holds), and the new tables join the licence-end
guard and tombstone (Task 3).

## 2. Surface disposition (all 202 catalog ids)

Groups follow decisions 2–4. **G0** surfaces are captured and parsed through existing readers.
**G1** to **G3** surfaces get new code parsers. **TXT** is model-selected free text. **DISC**
surfaces are fetched for discovery only. **G4** surfaces are fetched and kept but not parsed.
**X** surfaces are never fetched.

| Group | Site | Catalog ids |
|---|---|---|
| G1 series | screener | chart-api, fii-api, hs-data-api |
| G1 series | tijori | chartdata-price-api, chartdata-valuation-api, chartdata-median-pe-api, capex-api, debt-api, revenue-mix-history-api, financials-popup-chart-api, financial-statement-compare-api, macro-chart-api, sector-ms-chart-api, sector-company-opm-api, index-data-api, index-metric-data-api |
| G2 tables/lists | screener | section-documents, company-trades, company-announcements, results-latest, upcoming-results, concalls-feed, annual-reports-feed, announcements-feed, market-pulse, corporate-actions-feed, trades-feed, ipo, ratings-feed, market-level, index-page, person-page, screen-raw (HTML, Task 10's table reader) |
| G2 tables/lists | tijori | overview-company-filings, overview-customers, overview-suppliers, overview-brands, overview-connections, shareholding-overview (Overview table), shareholding-trend, quarterly-results-api, upcoming-events-api, raw-materials |
| G3 cells + label proposals | screener | section-insights, company-compare |
| G3 cells + label proposals | tijori | company-benchmarking, benchmarking-benchmarking-financial, benchmarking-benchmarking-business |
| TXT | screener | company-page (About, Key Points; its headline is G0), plus the subject text of rows already parsed from company-announcements and announcements-feed |
| DISC | tijori | overview-operationalmetrics (supplies the `company_op_metrics` URLs) |
| G0 | screener | company-consolidated-empty-shell, section-quarters, section-profit-loss, section-balance-sheet, section-cash-flow, section-ratios, section-shareholding, quick-ratios-api, peers-api, schedules-api, investors-api, segments-api, related-party, corporate-actions-modal (XHR GET), company-search-api |
| G0 | tijori | company-overview (registry islands and revenuemix; its `memoryOverviewKeyEvents` AI part is G4), overview-custom-ratios, overview-custom-financials, overview-forensics, overview-marketshare, overview-revenuemix, overview-competitors, overview-corporateactions, company-financials, financials-growth-table, financials-balance-sheet, financials-profit-and-loss, financials-cash-flow, financials-ratios, financials-quarterly-results, company-shareholding, shareholding-detailed, fund-flow-api, cash-flow-waterfall-api, balance-sheet-snapshot-api, op-metrics-api, company-timeline-api, company-search-api, quarterly-results, upcoming-events |
| G4 pending a 200 | screener | commentary-modal (TXT once a 200 is retained) |
| G4 pending a 200 | tijori | shareholding-detail-chart-api, market-share-api, sector-area-chart-api, markets-indices-widget-api (G1 once a 200 is retained), market-share-peer-companies-api (DISC once a 200 is retained), filter-advanced-search-api (only a 500 is retained; its reader is chosen once a 200 is) |
| G4 kept, not parsed | screener | section-chart (duplicate of chart-api), section-peers (duplicate of peers-api), section-analysis (machine pros/cons), forecasts (tool defaults, not reported data), quarter-source-pdf (302 kept; its Location is the link, which RowLink already extracts), ratio-search-api, explore, screens-list, screen-page, sectors-filter-api, market-overview, people-search, fii-page (duplicate of fii-api), insider-summary, product-prices, hs-search-api, commodity-page (duplicate of hs-data-api), ratio-gallery, user-public-profile, capsule, changelog, features, guides, support, sitemap, robots |
| G4 kept, not parsed | tijori | overview-company-timeline-sidepanel (empty shell; its data is company-timeline-api), overview-quick-view (its price, valuation, capex and debt parts duplicate the chart APIs), overview-knowledgebase, overview-popular-queries, overview-discussions-and-analysis, financials-price (duplicate of chartdata-price-api), financials-reverse-dcf (shell), financials-balance-sheet-snapshot, financials-fundflow-analysis and financials-cash-flow-analysis (empty chart shells; their data is balance-sheet-snapshot-api, fund-flow-api and cash-flow-waterfall-api; orchestrator amendment 2026-10-29), financials-faqfinancials, shareholding-faqshareholding, company-reports (generated Stack reports), financial-company-search-api, universal-search-api, search-page, markets, macro, sector-page, index-search-api, filter, filter-popular-queries, filter-popular-queries-api, filter-popular-query-results-api, filter-public-queries, filter-public-queries-api, filter-field-catalog-api, ideas-dashboard, concall-monitor (AI summaries), reports-store, features, faq, whats-new, sitemap, robots, llms-txt, policy-pages |
| X account | screener | company-notebook-modal, company-sublists-api, screen-new, announcements-user-filters, dashboard-feed, watchlist, watchlist-manage, alerts, stock-alerts-modal, user-account, user-columns, user-quick-ratios, custom-ratios, push-notifications, notebook-list, premium |
| X account | tijori | saved-queries, saved-queries-api, plans, watchlist, watchlist-data, watchlist-dcf, portfolio, portfolio-family-summary-api, portfolio-family-overlap-api, portfolio-read-api, portfolio-stock-price-api, portfolio-broker-summary-api, portfolio-family-analytics-api, portfolio-family-performance-api, alerts, alerts-api, site-timeline, site-timeline-more, site-timeline-upcoming, account-management, account-subscription, edit-columns, dashboard |
| X universe | screener | pre-listing-company |

Counts: G1 16, G2 29, G3 5, TXT 1 id, DISC 1, G0 43, G4 pending a 200 7, G4 60, X 40. Total
202. Screener `watchlist` and Tijori `site-timeline` have existing readers but are account
pages, so they are not fetched.

**Acceptance rule (all parsed groups).** A parser counts as accepted only when a test runs it on
a retained **200** response. Discovery JS, a script template or a 404 does not count. That is
why seven surfaces sit in "G4 pending a 200".

**Company expansion (finite, named).** Each templated company child names one expansion function:

| Function | Parent capture | Children |
|---|---|---|
| `tijori_op_metrics` | overview-operationalmetrics | op-metrics-api `company_op_metrics` URLs |
| `tijori_revenue_mix_items` | company-overview | revenue-mix-history-api item ids |
| `tijori_popup_fields` | company-financials | financials-popup-chart-api fields |
| `tijori_compare_selector` | company-financials | financial-statement-compare-api column selector |
| `screener_schedules` | Screener company page (both bases) | schedules-api parents (`showSchedule(`) |
| `screener_nested_schedules` | schedules-api response | the nested schedules its `sub_rows[*].nested_schedule_call` advertise. The bound is the reader's `MAX_SCHEDULE_DEPTH = 3` (`screener_financials_models.py:86`), which counts the company page as depth 1: at most two schedule-request levels; a call advertised by a depth-3 schedule is reported incomplete, not fetched |
| `screener_investors` | Screener company page | investors-api classes (`showShareholders(`) |
| `screener_segments` | Screener company page | segments-api (`showSegment(`) |
| `screener_compare_peers` | covered universe | company-compare peers: other covered-watchlist stocks only; with one covered stock there is no compare |

Handler regexes tolerate whitespace before `(` (audit finding 4 shape).

**Market traversal (finite, per hub).** Every known level is listed; nothing else is followed.

| Hub (parent) | Level path | Child surfaces |
|---|---|---|
| Screener `/market/` | macro-sector `IN##` → sector `IN####` → industry `IN######` → basic industry `IN#########` (four levels) | market-level, each listed page paginated (Task 11) |
| Screener company page (verified) | benchmark index tags | index-page: `capture-due` follows them during company capture; `capture --market` routes through the latest verified retained company page per address |
| Screener `people-search` | person links | person-page |
| Screener `hs-search-api` | HS-code (`/commodity/`) links | hs-data-api |
| Tijori company overview (verified; aa6.24) | its one sector link (`/sector/None` = none), so only covered companies' sectors | sector-page → sector-ms-chart-api (`chart_id`), sector-company-opm-api (`metric_id`); sector-area-chart-api is kept only (pending a 200) |
| Tijori `markets` | index ids | index-data-api → index-metric-data-api (`metric`) |
| Tijori `macro` | indicator ids | macro-chart-api |
| Screener `screens-list` (first page) | screen links | screen-page (G4) |
| Screener `screen-page` (first page) | author profile links | user-public-profile (G4) |
| Screener `hs-search-api` (first result page) | commodity links | commodity-page (G4) |
| Tijori `filter-popular-queries`, `filter-public-queries` (first result page) | query links | filter-popular-query-results-api (G4) |

The G4 rows are bounded: only instances linked from the hub's first page or first result page
are fetched. Exhaustive enumeration of every screen, HS code, person or query is out of scope
(the owner's finite-breadth ruling).

A hub whose retained body yields zero children for a listed level is a gap in the run report
and fails Task 11's retained test, which is how a wrong row in this table is caught.

**Pagination.** Progress is tracked per **logical traversal**, keyed by (site, surface, the
normalised path, the stable filter parameters). Moving parameters (page, cursor, and the Tijori
date window) are excluded, so two `market-level` paths are two traversals and a date window
started yesterday is the same traversal today. On resume, the active date window and cursor are
recovered from the traversal's retained request URLs (its captures' addresses), never recomputed
from today. Each traversal
has a stable start boundary: the newest stable row id (the row's link or announcement id), upper
date or cursor of the previous **completed** traversal with that key. A run pages back (`?p=` /
`page=`) until a page contains the boundary or the run has fetched 20 pages (`INCOMPLETE`). A
capped traversal resumes on the next run from the continuation recovered from retained outcomes
(its last fetched page, fetched again, since prepended rows only push rows to later pages)
towards the same boundary. The boundary advances only when the traversal completes; it then
becomes the newest row of the traversal's first page. Tijori date-range feeds start at the last
completed traversal's upper date, not a fixed number of days. `company-timeline-api` follows its
own cursor parameter until the cursor is exhausted or equals the last completed cursor.

## 3. Phases and size

| Phase | Tasks | Exit (demoable; each names expected, completed, refused and incomplete work) | Size |
|---|---|---|---|
| 1 Tracer | 1–5 | The tracer test runs `main(["vendor", "capture", "--symbol", "APARINDS", "--surface", "screener:chart-api"])` against retained responses and a disposable database: the capture is registered, its points stored in one transaction, the canary green; the run report gives expected = the page plus one request per `#chart` metric set, completed = the page and the retained metric set, incomplete = the metric sets the fake opener answers with 404, refused 0. A backup/restore test keeps the capture with its rows. A 48-month-old vendor-surface capture is `HELD`. | ~1,750 |
| 2 Company breadth | 6–10 | `vendor capture --symbol APARINDS` (one live run) keeps every non-account company surface; G0 adapters, G1 and G2 values are stored; the report lists expected, completed, refused (denied, stopped) and incomplete (gaps, missing slug, topology unknown) counts. Retained tests pass for the 18 picked companies. | ~1,785 |
| 3 Market and cadence | 11–14 | Two live `vendor capture-due` runs on one day: the second does no new work unless a feed shows a new event or an acquisition is unfinished; both reports name expected, completed, refused and incomplete work. A new results row moves that company's statements to pending until the vendor shows the new period. | ~1,520 |
| 4 G3, labels, text | 15–18 | G3 cells are stored by position. The bake-off key is reviewed (model-checked), then scored by `scripts/vendor_surface_bakeoff.py`, and the report committed. The runtime commands are proven with a fake model and refuse with no owner-selected model. Owner selection and live runtime use come after this phase, not inside it. | ~1,265 |
| 5 Drift and raw-first | 19–20 | `vendor canary` runs runbook S1–S8 and T1–T8 live; mutation fixtures fail it with the check named; `tijori-overview` and `tijori-shareholding` register raw before parsing. The five follow-up beads are filed. | ~605 |

**Total: about 6,925 changed lines**, derived from the per-task estimates below:

| Task | Source | Config/data | Tests | Ripple | Total |
|---|---|---|---|---|---|
| 1 Keep hold | 25 | 5 | 40 | 30 | 100 |
| 2 Fetch boundary | 195 | 0 | 130 | 0 | 325 |
| 3 Capture store | 315 | 0 | 140 | 80 | 535 |
| 4 Tracer and CLI | 435 | 20 | 175 | 0 | 630 |
| 5 Canary core | 90 | 0 | 70 | 0 | 160 |
| 6 Reference bodies | 120 | 0 | 0 | 0 | 120 |
| 7 Company capture | 295 | 120 | 185 | 0 | 600 |
| 8 G0 adapters | 290 | 0 | 140 | 0 | 430 |
| 9 G1 company | 200 | 0 | 110 | 0 | 310 |
| 10 G2 company | 200 | 15 | 110 | 0 | 325 |
| 11 Market traversal | 245 | 75 | 150 | 0 | 470 |
| 12 G1 market | 150 | 0 | 80 | 0 | 230 |
| 13 G2 market | 240 | 0 | 110 | 0 | 350 |
| 14 Cadence | 260 | 20 | 190 | 0 | 470 |
| 15 G3 cells | 150 | 0 | 90 | 0 | 240 |
| 16 Label proposals | 290 | 15 | 130 | 30 | 465 |
| 17 Bake-off script | 130 | 150 | 50 | 0 | 330 |
| 18 Text spans | 140 | 0 | 90 | 0 | 230 |
| 19 Runbook canaries | 280 | 0 | 140 | 0 | 420 |
| 20 Raw-first TO/TS | 85 | 0 | 100 | 0 | 185 |
| **Total** | **4,135** | **420** | **2,230** | **140** | **6,925** |

Source includes migrations (0044 about 175 lines in Task 3, 0045 about 60 in Task 16). Config
and data includes `surfaces.yaml` and the bake-off key. Ripple is edits to existing tests that
enumerate tables or hold roots. The generated `kinds-index.json` is not counted.

**Checks.** Each task runs its own test file plus `uv run mypy --strict src` and `uv run ruff
check`. The full `uv run pytest tests/fundamentals` and `scripts/verify.sh gate` run once at each
phase end, then the Sol phase-end review.

## 4. Tasks

### Phase 1 — Tracer bullet

### Task 1: Keep-all hold for vendor-surface captures

Goal: a registered capture whose surface starts with `vs.` is `HELD` by `VENDOR_SURFACE_KEEP` at
any age, unless its licence has ended. Every other capture's eligibility is unchanged; the Stage
5 oracle and the existing retention tests pass unmodified.

Files:
- Modify: `src/fundamentals/contracts/retention.py` (`HoldRoot` member); `src/fundamentals/retention/holds.py` (one root in `_FACTS`, the prefix read from `holds.yaml`); `src/fundamentals/retention/eligibility.py` (one member added to `_VENDOR_HOLDS`); `config/retention/holds.yaml` (`keep_surface_prefix: "vs."` with a dated comment); `docs/workstreams/data-foundation/plans/D9.md` (dated retention-policy note: owner 2026-10-28, vendor-surface captures kept)
- Modify (ripple): tests that enumerate `HoldRoot`, as the full suite reveals
- Test: `tests/fundamentals/test_retention_eligibility.py` (two cases), `tests/fundamentals/test_retention_holds.py` or its existing equivalent (one `pg` case)

Interfaces:
- Consumes: `capture_facts`, `pinned_roots`, `eligibility` (existing).
- Produces: `HoldRoot.VENDOR_SURFACE_KEEP`; `VENDOR_SURFACE_PREFIX = "vs."` (read from `holds.yaml`).

Approach:
- The hold root is one line in the `roots` CTE: `SELECT 'VENDOR_SURFACE_KEEP', 'C', id FROM
  eqos.capture_refs WHERE starts_with(surface, %(keep_prefix)s)`.
- `eligibility()` honours only `_VENDOR_HOLDS` for vendor-bounded sources (D9 R3), so the
  member is added there (orchestrator-approved). This changes no window, no anchor and no
  existing verdict, because no existing capture has a `vs.` surface.
- Licence end is checked before holds, so licence-end deletion is unchanged.

Verification: `uv run pytest tests/fundamentals -k "retention or stage5"` passes with no edits to
existing assertions; new cases: a `vs.` vendor capture at 48 months is `HELD`
(`VENDOR_SURFACE_KEEP`); the same capture after its licence end is `ELIGIBLE`
(`LICENCE_END`); a `pg` case shows `capture_facts` returns the root for a `vs.` registration.

Dependencies: None.

Risks: a test that asserts the exact `HoldRoot` member list needs one line. About 100 lines.

### Task 2: The vendor fetch boundary

Goal: one GET path that:
- refuses non-HTTPS, non-exact-authority and deny-listed URLs (after path normalisation) before
  any network call;
- refuses a site with a `STOP-<site>` marker or held by another process's site lock;
- paces each site, never follows a redirect and keeps the `Location`;
- stores every response, including errors and stops, with the true `BodyCompleteness`;
- raises `SiteStopped` after a 403, 429, 503 or login redirect;
- enforces a per-site budget.

Registration in PostgreSQL is Task 3; this task returns the stored `CaptureRecord` and the
redirect `Location`.

Files:
- Create: `src/fundamentals/ingest/vendor_surface_fetch.py`
- Test: `tests/fundamentals/test_vendor_surface_fetch.py`

Interfaces:
- Consumes: `SnapshotStore.put_capture`, `RequestPacer`, `NoRedirectHandler`,
  `read_bounded_capture` (`ingest/http_session.py`); `classify_http_status`,
  `transport_failure_outcome`, `TIJORI_RIGHTS` (`ingest/tijori_capture.py`); `CaptureRecord.make`,
  `RequestIdentity`, `BlobRef`, `BodyCompleteness`.
- Produces:
  - `Site(StrEnum)`: `SCREENER = "screener-subscriber"`, `TIJORI = "tijori"`.
  - `SITE_AUTHORITY: Mapping[Site, str]`.
  - `SiteSession(BaseModel)`: `site: Site`, `session_cookie: SecretStr`, `cookie_name: str`.
  - `SiteStopped(Exception)` (carries `site` and the stored `fetched: Fetched | None`; `None`
    when refused by an existing marker); `SiteBusy(Exception)`.
  - `normalise(url: str) -> str`; `is_denied(url: str) -> bool` (on the normalised form);
    `request_key(url: str) -> str` (sha256 hex).
  - `Fetched(BaseModel)`: `record: CaptureRecord`, `url: str`, `location: str | None`.
  - `class VendorFetcher`:
    - `__init__(self, store: SnapshotStore, sessions: Mapping[Site, SiteSession], opener: OpenerDirector, stop_dir: Path, lock: SiteLock, *, spacing_seconds: float = 1.5, site_budget: int = 350, timeout_seconds: float = 30.0, max_bytes: int = 20_000_000)`;
    - `get(self, site: Site, surface: str, url: str, *, xhr: bool = False) -> Fetched`;
    - `remaining(self, site: Site) -> int`.
  - `SiteLock(Protocol)`: `acquire(site: Site) -> bool`; `PgSiteLock(pool)` implements it with
    `pg_try_advisory_lock(hashtext('eqos.vendor_surface.' || site))` on one held connection.

Approach:
- Port runbook §1 literally on the normalised path: segment words (equal, `<word>-`/`<word>_`
  prefix, `-<word>`/`_<word>` suffix), skipping the segment after `/company/`; deny query keys
  (`ack`, `acked`, `mark`, `mark_read`, `mark_as_seen`, `seen`, `read`, `dismiss`, plus any deny
  word); deny the named paths; allow the two exceptions.
- Surface stored as `vs.<catalog-id>`. Rights: `TIJORI_RIGHTS` for both sites (A-05 decision 005).
- Stop: store first, then raise
  `SiteStopped(fetched=...)`; the coordinator registers it and records `UNUSABLE`, then writes
  `STOP-<site>` (capture id and status) in `finally`, still holding the site lock (Task 4).
- Log the URL with its query redacted; never the cookie.

Verification: `uv run pytest tests/fundamentals/test_vendor_surface_fetch.py`, one parametrised
table:
- deny-list rows for every word and key; the company-slug exemption (`ask-automotive-ltd`); both
  exceptions; `/filter/saved-queries/` allowed; `?acked=true` denied; `/%2e%2e/watchlist/` and
  `//in//watchlist` denied after normalisation;
- `http://`, `screener.in` (no `www`), `www.screener.in:8443` and `user@www.screener.in` refused;
- a fake 429 stores the capture and raises `SiteStopped` carrying the stored `Fetched`; the
  coordinator attempts registration before writing the marker, including when registration fails;
- a 302 to `/login/` stops the site; a 302 off-host is stored with its `Location` and no stop;
- a truncated read stores `BodyCompleteness.PARTIAL`;
- a held `SiteLock` raises `SiteBusy`.

Test seams: `VendorFetcher.get` with an injected opener and lock; `is_denied`, `normalise`.

Dependencies: None.

Risks: Tijori login paths beyond `/account/signin` are unverified; any same-host 3xx containing
`login` or `signin` stops. About 325 lines.

### Task 3: Capture store — registration, outcomes and values

Goal: a fetched response is registered in `eqos.capture_refs`, and an outcome with all its values
is written in one transaction against that registration. The new tables are append-only, join the
licence-end guard and tombstone, and survive backup and restore with their capture.

Files:
- Create: `migrations/0044_vendor_values.sql`; `src/fundamentals/store/vendor_values_store.py`
- Modify (ripple): tests that enumerate `eqos` tables, grants or backup tables (`pg_evidence_schema_support.py`, `test_ledger_integrity.py`, `test_ledger_stage3_e2e.py`, `test_derived_settings.py`, `evidence_support.py`, the data stage 2 backup list), as the full suite reveals
- Test: `tests/fundamentals/test_vendor_values_store.py`

Interfaces:
- Consumes: `Fetched` (Task 2); `capture_registration`, `Registration.insert`,
  `Registration.store_clock` (`evidence/capture_retention.py`); `CaptureReference`.
- Produces:
  - `OutcomeStatus(StrEnum)`: `OK`, `PARTIAL`, `EMPTY`, `FAILED`, `UNUSABLE`, `KEPT`;
    `USABLE: frozenset[OutcomeStatus]` = {`OK`, `PARTIAL`, `EMPTY`, `KEPT`}.
  - `VendorValue(BaseModel)`: `table_key: str`, `row_index: int`, `column_index: int`,
    `locator: str`, `row_label: str`, `column_label: str`, `raw_text: str`,
    `value: Decimal | None`, `unit: str | None = None`, `basis: str | None = None`,
    `link: str | None = None`, `padded: bool = False`, `expected_numeric: bool = False`.
  - `Outcome(BaseModel)`: `surface: str` (logical id), `parser_version: str`,
    `parser_sha256: str`, `status: OutcomeStatus`, `symbol: str | None`, `detail: str | None`,
    `values: tuple[VendorValue, ...] = ()`, `rejected_count: int | None = None`,
    `traversal_key: str | None = None`, `traversal_page: int | None = None`,
    `traversal_done: bool = False`.
  - `register(pool, fetched: Fetched) -> CaptureReference`.
  - `VendorValuesStore(pool)` with `record(ref: CaptureReference, outcome: Outcome, *,
    row_count: int, conn: Connection | None = None) -> int` (outcome id; with `conn` it joins the
    caller's transaction, which Task 18 uses for its claims rows) and
    `has_outcome(capture_ref_id: int, surface: str, parser_version: str) -> bool`.
  - `ParserVersionDrift(Exception)`.
  - `eqos.vendor_basis_bindings` (Task 7 writes and reads it).

Approach:
- `register` runs `Registration.insert` inside `capture_registration(pool)`, with
  `registered_at`/`first_seen_at` from `store_clock()` and the URL as the address.
- Migration 0044, following `0040_review_telemetry.sql` and `0029_retention_purge.sql`:
  - `eqos.vendor_parser_versions(parser_version PK, parser_sha256)`: a version is bound to one
    content hash; `record` inserts on first use and raises `ParserVersionDrift` on a mismatch.
  - `eqos.vendor_outcomes`: `id`, `capture_ref_id` FK `capture_refs`, `surface`,
    `parser_version` FK, `symbol`, `status` CHECK, `row_count`, `rejected_count`, `detail`,
    `traversal_key`, `traversal_page`, `traversal_done` (Task 11), `recorded_at`; unique
    (`capture_ref_id`, `surface`, `parser_version`) and unique (`id`, `capture_ref_id`).
  - `eqos.vendor_values`: `outcome_id`, `capture_ref_id` FK `capture_refs` (so the guard sees the
    capture), the `VendorValue` columns; composite FK (`outcome_id`, `capture_ref_id`) →
    `vendor_outcomes` (`id`, `capture_ref_id`), so a value can never name another outcome's
    capture; unique (`outcome_id`, `table_key`, `row_index`, `column_index`).
  - Triggers per table: `eqos.retention_guard()` BEFORE INSERT (licence-ended source refused);
    `reject_mutation_except_tombstone('value', 'raw_text', 'row_label', 'column_label', 'link')`
    on `vendor_values` and `reject_mutation()` on the others for UPDATE/DELETE;
    `reject_mutation()` BEFORE TRUNCATE.
  - `CREATE OR REPLACE eqos.tombstone_vendor_capture` with its 0029 body unchanged plus one
    statement nulling the capture's **content** columns in `vendor_values`: `value`, `raw_text`,
    `row_label`, `column_label` and `link` (every column whose text is read off the body,
    including document and announcement titles stored as `row_label`). **Structure** stays:
    `outcome_id`, `capture_ref_id`, `table_key`, `row_index`, `column_index`, `locator`,
    `unit`, `basis`, `padded`, `expected_numeric`, and the outcome rows.
  - `eqos.vendor_basis_bindings` (append-only, same triggers): `entity_id`, `basis`,
    `screener_company_id`, `warehouse_id`, `capture_ref_id` FK `capture_refs` (the page that
    proved it), `evidence` CHECK (`ONBOARDING`, `FIRST_CAPTURE`), `recorded_at`; unique
    (`entity_id`, `basis`). Only positive bindings are rows; an absent row is unknown.
  - Grants: INSERT and SELECT to the runtime role, sequences to match; nothing else.
- `record` writes the outcome and its values in one transaction with the caller's explicit
  `row_count`; when `outcome.values` is non-empty it must equal their number.
- **Pin rule:** `parser_sha256` is the sha256 of the registered parse function's own source
  (`inspect.getsource(entry.parse)`), computed once per process. Adding or editing another parser
  in the same module never drifts an existing version; a change to a shared helper is versioned
  by bumping its callers' `version` in the same diff.

Verification: `uv run pytest tests/fundamentals/test_vendor_values_store.py` (`pg`):
- **backup/restore:** register a capture, record an outcome with two values, run the existing
  backup and restore, and assert the capture, its blob and both values come back together;
- **licence end:** after a `licence_ends` row for the source, `record` is refused with
  `BEYOND_AUTHORITY`;
- a failing value insert leaves no outcome row (one transaction);
- a value whose `capture_ref_id` differs from its outcome's capture is refused (composite FK);
- the tombstone nulls `row_label`, `column_label`, `link`, `value` and `raw_text` and keeps the
  positions;
- UPDATE, DELETE and TRUNCATE are refused;
- the same `parser_version` with a different hash raises `ParserVersionDrift`; the namespaced
  versions `screener:company-search-api.reader.v1` and `tijori:company-search-api.reader.v1` both
  record in one database; adding a second
  parser function to the module leaves the first one's hash unchanged.
Then the full suite once for the table-enumeration ripple.

Dependencies: 1, 2.

Risks: the ripple (2026-10-19 learning). Replacing `tombstone_vendor_capture` copies its 0029
body; diff it against 0029 in review. About 535 lines.

### Task 4: Tracer — chart API end to end, with CLI wiring

Goal: `fundamentals vendor capture --symbol APARINDS --surface screener:chart-api`:
- fetches and registers the Screener company page, checks login and identity (`assert_logged_in`,
  `read_identity` against `CompanyIds.screener_company_id`), then basis with `read_page_evidence`
  when `CompanyIds.topology` is bound, and records the page outcome (`KEPT`, or `UNUSABLE` with
  `topology unknown` under the gate version, §1);
- takes `data-company-id` from the retained page and fetches `chart-api` (not basis-scoped) for
  each metric set in the page's `#chart` controls with `days=10000`, whatever the topology;
- parses each retained body into points, stored with one outcome per capture;
- prints a run report of expected, completed, refused and incomplete requests.

`fundamentals vendor reparse --surface screener:chart-api` re-parses registered captures without
network access, appending outcomes under the current parser version.

Files:
- Create: `config/vendor_surface/surfaces.yaml` (company-page and chart-api only); `src/fundamentals/ingest/vendor_surface_specs.py`; `src/fundamentals/ingest/vendor_surface_parse.py`; `src/fundamentals/ingest/vendor_surface_series.py`; `src/fundamentals/ingest/vendor_surface_capture.py`; `src/fundamentals/api/vendor_surface_cli.py`; `tests/fundamentals/vendor_surface_support.py` (shared harness: request-index loader, fake opener over retained bodies, disposable-database fixture)
- Modify: `src/fundamentals/api/cli_parser.py` (`add_vendor_parser`); `src/fundamentals/api/cli.py` (`main` calls `dispatch_vendor_command(args, ...)` after the existing dispatchers)
- Test: `tests/fundamentals/test_vendor_surface_tracer.py`

Interfaces:
- Consumes: `VendorFetcher`, `Site`, `Fetched`, `PgSiteLock` (Task 2); `register`,
  `VendorValuesStore`, `VendorValue`, `Outcome`, `OutcomeStatus` (Task 3);
  `read_page_evidence`, `parse_document`, `assert_logged_in`, `read_identity`
  (`screener_session_page`); `read_number`
  (`screener_financials_tables`); `open_pool(PgSettings(), PgRole.RUNTIME)`;
  `_screener_credentials_from_env`, `_tijori_credentials_from_env` (`api/cli.py`);
  `basis_topology(stock)` (`api/screener_page_cli.py`) and `StockConfig.identifiers`
  (`api/watchlist_config.py`); `BasisTopology`, `Basis`.
- Produces:
  - `ParseGroup(StrEnum)`: `SERIES`, `TABLE`, `CELLS`, `TEXT`, `DISCOVERY`, `READER`, `NONE`.
  - `Cadence(StrEnum)`: `DAILY`, `WEEKLY`, `AFTER_RESULTS`; `Scope(StrEnum)`: `COMPANY`, `MARKET`.
  - `SurfaceSpec(BaseModel)`: `site: Site`, `id: str`, `scope: Scope`, `path: str`,
    `group: ParseGroup`, `cadence: Cadence`, `xhr: bool = False`, `expand: str | None = None`,
    `sections: tuple[str, ...] = ()`, `selector: str | None = None`.
  - `load_specs(path: Path, catalog: Path) -> tuple[SurfaceSpec, ...]` (path templates checked
    against `catalog.yaml` `url_pattern`).
  - `CompanyIds(BaseModel)`: `nse_symbol: str`, `isin: str`, `tijori_slug: str | None`,
    `tijori_company_id: int | None`, `screener_company_id: int | None`,
    `topology: BasisTopology | None`; `company_ids(stock: StockConfig) -> CompanyIds` copies the
    verified identifiers from `config/watchlist.yaml` (topology via `basis_topology`). It never
    reads a response; for a stock without configured topology, Task 7 binds it.
  - `ParseContext(BaseModel)`: `ids: CompanyIds | None`, `basis: Basis | None`, `url: str`,
    `retrieved_at: datetime`, `body_sha256: str`, `capture_id: str`,
    `parent: Mapping[str, Any] | None = None` (the expansion's reader inputs for a child: hook,
    parent label, periods).
  - `Body` (holds bytes; `tree()` parses once);
    `Parser = Callable[[Body, ParseContext], tuple[VendorValue, ...]]`;
    `ParserEntry(BaseModel)`: `version: str`, `parse: Parser`;
    `PARSERS: Mapping[tuple[Site, str], ParserEntry]`.
  - `Request(BaseModel)`: `spec: SurfaceSpec`, `url: str`, `ids: CompanyIds | None`,
    `basis: Basis | None = None`, `parent: Mapping[str, Any] | None = None`,
    `due_since: datetime | None`.
  - `RunReport(BaseModel)`: `expected: int`, `completed: int`, `refused: tuple[str, ...]`,
    `incomplete: tuple[str, ...]`, `stopped_sites: tuple[Site, ...]`.
  - `parse_and_record(store, values, ref, record, request) -> tuple[OutcomeStatus, ...]`:
    builds the `ParseContext` from the request and record, then dispatches the spec's own parser
    and each section parser on one `Body`.
  - `capture(fetcher, store, pool, values, request: Request) -> CaptureReference`: fetch,
    register, then `parse_and_record`. On `SiteStopped` with a stored `Fetched` it registers the
    response, records `UNUSABLE` (`detail`: the refusal) and re-raises, so the run loop drops the
    site's remaining requests and lists it in `stopped_sites`.
  - `reparse(store, pool, values, spec) -> int` (captures with no outcome under the spec's
    current parser version, including topology-gated ones).
  - `dispatch_vendor_command(args, *, opener_factory, pool_factory, store_factory, sessions_factory) -> int | None`.
  - CLI: `vendor capture --symbol S [--tijori-slug T] [--surface site:id ...] [--snapshot-root PATH]`, `vendor reparse --surface site:id`; all capture roots share `data/STOP-<site>`.

Approach:
- Outcome rules in `parse_and_record`, first match wins: a non-OK HTTP capture → `UNUSABLE`
  with the HTTP outcome in `detail`; a body that is not `BodyCompleteness.COMPLETE` → `UNUSABLE`
  (`detail`: the completeness), with no parser run, for every group; a basis-scoped request
  (`request.basis` set) whose `ids.topology` is `None` → `UNUSABLE` (`detail`: `topology unknown`)
  under `<site>:gate.topology.v1`, reported incomplete, never guessed, and no other request is
  affected; a parser exception → `FAILED`; zero values → `EMPTY`; any value
  with `expected_numeric` and `value is None` → `PARTIAL`; `NONE`-group specs → `KEPT`.
- The parse time is `record.retrieved_at`-anchored; no `now()` below the CLI.
- JSON is decoded with `parse_float=Decimal`; Screener text cells go through `read_number`.
- Chart parser: `table_key` = metric set, `row_index` = point index, `column_index` = dataset
  index, `locator` = JSON pointer, labels = date and dataset label.
- `--surface` limits work to those specs plus the parents they need.
- Composition root: `dispatch_vendor_command` receives factories for the opener, pool, store and
  sessions; tests inject them.

Verification: `uv run pytest tests/fundamentals/test_vendor_surface_tracer.py` (`retained`, `pg`):
- runs `main(["vendor", "capture", "--symbol", "APARINDS", "--surface", "screener:chart-api", ...])`
  with the fake opener serving retained responses and a disposable database;
- asserts 4 datasets with 248 points each, two hand-read points equal to their `raw_text`, and the
  report's exact counts: expected = page + one per `#chart` metric set; completed = page + the
  retained set; incomplete = the sets the fake opener answers with 404; refused 0;
- a raising parser leaves the capture registered and the outcome `FAILED`;
- a fake 429 on the second metric set: that capture is registered with an `UNUSABLE` outcome
  before the run stops, no further Screener request is made, and the report lists the site in
  `stopped_sites`;
- a truncated chart body (`PARTIAL` completeness) and a truncated `KEPT`-group body are both
  `UNUSABLE` and do not count as completed;
- a stock with no configured topology records the page `UNUSABLE` (`topology unknown`) and lists
  it incomplete, while every chart-api metric set is still fetched and its points stored;
- `reparse` after a version bump appends a second outcome with no network; after a topology is
  supplied, `reparse` parses the gated page under its real version.

Test seams: `main`, `parse_and_record`, `reparse`, `PARSERS`.

Dependencies: 2, 3.

Risks: `cli.py` is a long dispatcher chain; add one call, no restructuring. About 630 lines.

### Task 5: Canary core (three checks)

Goal: `fundamentals vendor canary --yield-only` exits non-zero, naming site, surface, request and
check, when any of these holds:
1. **Row-count drop:** a request's latest usable outcome has fewer than half the rows of the
   previous usable outcome of the same request, surface and parser version (zero counts).
2. **Expected request without outcome:** a registered capture has no outcome row, or a
   non-templated company spec for a covered stock has no outcome within twice its cadence.
3. **Parser version:** comparisons in check 1 are only within one parser version; the first
   outcome under a new version is `NO_BASELINE` (info).

Files:
- Create: `src/fundamentals/ingest/vendor_surface_canary.py`
- Modify: `src/fundamentals/api/vendor_surface_cli.py`
- Test: `tests/fundamentals/test_vendor_surface_canary.py`

Interfaces:
- Consumes: `vendor_outcomes`, `USABLE` (Task 3); `load_specs` (Task 4); `covered_universe`
  (Task 14, optional: absent before Task 14, check 2's second clause is skipped and says so).
- Produces: `Drift(BaseModel)`: `site: Site`, `surface: str`, `request_key: str`, `check: str`,
  `detail: str`; `yield_drift(pool, since: datetime) -> tuple[Drift, ...]`.

Approach: two SQL queries with window functions. A standalone-only issuer's consolidated shell is
`EMPTY` every time; EMPTY→EMPTY is not a drop.

Verification: one `pg` test, parametrised: OK(10)→OK(4) drifts; OK(10)→EMPTY drifts;
EMPTY→EMPTY does not; v1 OK(10)→v2 OK(1) is `NO_BASELINE`; a capture with no outcome drifts.
The CLI exits 1 naming the check.

Dependencies: 3, 4.

Risks: the 50% threshold is a judgement; it is a constant with its reason in a comment. About 160
lines.

**Phase 1 exit:** expected: Tasks 1–5 green, the tracer `main([...])` test green against retained
responses; completed: one live tracer run, polite and logged, report printed; refused: none
expected; incomplete: none expected. Then the full suite, `scripts/verify.sh gate` and the Sol
phase-end review.

### Phase 2 — Company breadth (tier 1)

### Task 6: Promote the per-kind reference bodies

Goal: the 18 picked companies' company-surface bodies from the 2026-10-28 crawl are copied to
`data/raw/vendor-surface/2026-10-28/kinds/<site>/<SYMBOL>/<catalog-id>__<request-key-12>__<basis>.<ext>`
(request key = sha256 of the URL, first 12 hex; basis `consolidated`, `standalone` or `na`), and
indexed by a committed `docs/research/vendor-surface/kinds-index.json` (symbol, site, id, url,
request_key, basis, status, sha256, path). The shared harness loads both indexes through one
loader.

Files:
- Create: `scripts/vendor_crawl/promote_kinds.py`; `docs/research/vendor-surface/kinds-index.json` (generated)
- Modify: `tests/fundamentals/vendor_surface_support.py` (`load_request_index` reads both `snapshots-index.json` and `kinds-index.json`)

Interfaces:
- Consumes: the throwaway cache `scratchpad/vendor-crawl/cache/2026-10-28/<site>/*.json|.body`, `scratchpad/vendor-crawl/picks.json`, `catalog.yaml` `url_pattern`.
- Produces: `kinds-index.json` rows; `load_request_index() -> Mapping[str, IndexRow]` keyed by URL.

Approach: a stdlib script run with `python3 -I`. It matches each cached URL to a catalog
`url_pattern`, copies (never moves) the body, refuses to overwrite and verifies the sha256 after
copying. Non-company URLs are skipped and counted. The status is recorded so tests can enforce
the 200 rule.

Verification: the script prints counts per site and symbol; `python3 -m json.tool` passes on the
index; a re-run refuses to overwrite; `git status` shows only the script, the index and the
support file.

Dependencies: None. Run before anyone clears the scratchpad cache (urgent).

Risks: the 18 companies' bodies exist only in the scratchpad cache. About 120 lines.

### Task 7: Every company surface captured — expansion, gates, sections, slugs

Goal: `vendor capture --symbol SYM` fetches, registers and dispatches every company-scope surface
in §2 for one stock:
- parents first, then children through the named expansion functions of §2;
- section parsers dispatched from their parent capture (section contract, §1);
- an identity gate per site: Screener by login and `data-company-id` (`read_identity`), Tijori by
  `classify_financials_body` with `expected_symbol=SYM`. A failed identity gate records the page
  `UNUSABLE` and stops that company on that site (its children would be another company's).
  Topology never gates fetching: every company surface is fetched and kept, and only
  basis-scoped outcomes wait for a bound topology (§1);
- the topology is bound once per entity by `bind_topology` (below) and reused;
- the Tijori slug: `--tijori-slug` if given, else `config/watchlist.yaml`
  `SourceIdentifiers.tijori_slug`, else resolved through `entity/discovery.py`
  (`tijori_candidate` on the ISIN search, then `tijori_page_state`). An unresolved slug is
  reported as incomplete for this run only; it is retried on every run until resolved, never a
  permanent skip.

Files:
- Create: `src/fundamentals/ingest/vendor_surface_expand.py`; `src/fundamentals/ingest/vendor_surface_topology.py`
- Modify: `config/vendor_surface/surfaces.yaml` (company entries); `src/fundamentals/ingest/vendor_surface_capture.py`; `src/fundamentals/api/vendor_surface_cli.py`
- Test: `tests/fundamentals/test_vendor_surface_company.py`

Interfaces:
- Consumes: `capture`, `Request`, `RunReport`, `SurfaceSpec`, `CompanyIds`, `ParseContext`
  (Task 4); `read_page_evidence`; `classify_financials_body`; `tijori_candidate`,
  `tijori_page_state` (`entity/verification.py`); `load_request_index` (Task 6);
  `read_identity`, `read_markers` (`screener_session_page`); `eqos.vendor_basis_bindings` (Task 3).
- Produces:
  - `EXPANSIONS: Mapping[str, Callable[[Body, ParseContext], tuple[Request, ...]]]` (the §2
    functions; each child `Request` carries the parent's `ids`, `basis` and its reader inputs in
    `parent`);
  - `resolve_tijori_slug(fetcher, ids: CompanyIds) -> str | None`;
  - `company_requests(specs, ids) -> tuple[Request, ...]` (parents) and `capture_company(fetcher, store, pool, values, specs, ids) -> RunReport`;
  - `bind_topology(pool, store, ids: CompanyIds, entity_id: int, pages: Mapping[Basis, CaptureReference]) -> BasisTopology | None`.

Approach:
- An expansion that finds nothing on a parent that should advertise children (by the canary
  markers) is reported in `incomplete`, never silent.
- Modals use `xhr: true` (corporate-actions-modal).
- `company-compare` uses `screener_compare_peers`; with one covered stock it records no request
  and says so in the report.
- `screener_nested_schedules` runs on each schedules-api response, reads
  `sub_rows[*].nested_schedule_call`, and stops at `MAX_SCHEDULE_DEPTH = 3` counting the company
  page as depth 1 (two schedule-request levels).
- `bind_topology` (one function, about 60 lines), in order: (1) `ids.topology` from
  `config/watchlist.yaml`, returned as is; (2) the entity's `eqos.vendor_basis_bindings` rows;
  if none, the onboarding verification's verified Screener page capture (consolidated,
  `entity/discovery.py:550`, `entity/verification.py:282`) is re-read from the store; (3) the
  two company pages this run registered. A basis is bound only when its page shows the expected
  `data-company-id`, a `data-warehouse-id` and that basis's marker (`read_identity`,
  `read_markers`); each proof is one row (`ONBOARDING` or `FIRST_CAPTURE`). A topology is
  returned only when both bases are bound; otherwise `None` (unknown). An unmarked page binds
  nothing, so standalone-only is never inferred; such a stock needs its topology in
  `config/watchlist.yaml`. No extra request is made: the two pages are fetched anyway.

Verification: retained test through the shared harness for APARINDS, HDFCBANK, NETWEB and
ANONDITA: the captured surface ids equal the expected company set per kind (NETWEB has no
consolidated warehouse; ANONDITA has no Product Segments); a body with `showSchedule (` still
expands; a nested schedule advertised by a retained schedules-api body's
`sub_rows[*].nested_schedule_call` is fetched once, and a call advertised by a depth-3 schedule
is reported incomplete; a Tijori page for the wrong symbol records `UNUSABLE` and stops Tijori for
that company; **topology:** HDFCBANK with its watchlist topology removed still fetches every
company surface, binds both bases from the two retained pages (`FIRST_CAPTURE` rows) and parses
them; NETWEB with its topology removed fetches every surface, binds nothing (unmarked
standalone page), lists its basis-scoped outcomes incomplete (`topology unknown`) and parses its
non-basis surfaces; a second run reuses the stored bindings;
a missing slug resolved through a fake ISIN search proceeds; an unresolvable slug appears in
`incomplete` and the next run tries again.

Test seams: `capture_company` with the injected opener.

Dependencies: 4, 6.

Risks: per-kind URLs the crawl never fetched have no reference body; those cases test refusal
only. About 600 lines.

### Task 8: G0 reader adapters

Goal: each G0 surface's retained capture is parsed by its existing reader through a thin
adapter, dispatched after registration, and stored as vendor values with an outcome. No reader is
edited or rewritten.

Files:
- Create: `src/fundamentals/ingest/vendor_surface_readers.py`
- Modify: `src/fundamentals/ingest/vendor_surface_parse.py` (registry)
- Test: `tests/fundamentals/test_vendor_surface_readers.py`

Interfaces:
- Consumes: `Body`, `ParseContext`, `VendorValue`, `PARSERS` (Task 4); the existing readers
  below, each called with its existing inputs, taken from `ParseContext` (identity, basis,
  topology, `url`, `retrieved_at`, body sha256, capture id as `document_id`, and the parent
  inputs a child needs). No reader computes a time.

  | G0 family | Reader | Inputs beyond the body |
  |---|---|---|
  | Screener company-consolidated-empty-shell | `read_page_evidence` (`BASIS_UNAVAILABLE` → `EMPTY`) | basis, topology |
  | Screener section-quarters, -profit-loss, -balance-sheet, -cash-flow, -ratios | `read_section`, `read_growth_section` (P&L) | parent page tree, `source_id`, `retrieved_at` |
  | Screener section-shareholding | `read_shareholding_table` | periodicity |
  | Screener schedules-api | `read_schedule`; nested: `read_nested_schedule` | section, parent label, `expands`, basis, periods (from the parent section) |
  | Screener investors-api | `read_investor_bucket` | `InvestorHook`, parent shareholding table |
  | Screener segments-api | `screener_segments.read_segments` | `SegmentHook`, parent section table |
  | Screener quick-ratios-api, peers-api, related-party, corporate-actions-modal | `screener_company_fragments.read_quick_ratios`, `read_peers` (company id, basis), `read_related_party`, `read_corporate_actions` | as listed |
  | Screener company-search-api | `entity/verification.screener_candidate` | symbol |
  | Tijori company-overview and the overview-* sections | `build_tijori_overview` (`section=` per id) | slug, symbol, `tijori_company_id`, `retrieved_at` |
  | Tijori overview-forensics | `build_company_details` (`tijori_overview_company.py:243`; its `quick_look` checklist from the `company_details_data` island) | `SectionContext` |
  | Tijori company-financials and financials-* tables | `TijoriSource.parse_all_tables_bytes` | slug, symbol, `tijori_company_id`, `retrieved_at` |
  | Tijori company-shareholding, shareholding-detailed | `build_tijori_shareholding` | slug, symbol, `tijori_company_id`, `retrieved_at` |
  | Tijori fund-flow-api, cash-flow-waterfall-api, balance-sheet-snapshot-api, op-metrics-api | `build_tijori_analysis` (`TijoriAnalysisSection` per id) | slug, symbol, company id, sha256, `retrieved_at`, `metric_id` (op-metrics) |
  | Tijori company-timeline-api, quarterly-results, upcoming-events | `build_tijori_events` (`TijoriEventsSurface` per id) | sha256, `retrieved_at`, slug, symbol, company id |
  | Tijori company-search-api | `entity/verification.tijori_candidate` | none |

  The Tijori overview reader is `build_tijori_overview`, not `parse_overview_bytes`, because the
  latter stamps `now()` (`tijori_source.py:450`).
- Produces: one `PARSERS` entry per G0 surface, version `"<site>:<surface>.reader.v1"`; one converter per
  reader output type (`table_rows_to_values`, `tijori_tables_to_values`, …).

Approach: one converter per reader output type, not per surface; surfaces sharing a reader share
a converter. Cell identity is positional (Task 3). A reader's own failure is `FAILED` with its
message. Source unit and basis go into `unit` and `basis`; a cell the reader reports as padded
(SME zero-padded columns) gets `padded=True`; an expected numeric cell the reader cannot read
makes the outcome `PARTIAL`.

Verification: retained tests on APARINDS and one SME kind, parametrised over every row of the
table above: each family yields rows, two hand-read values match, a padded column is flagged, an
unreadable numeric cell gives `PARTIAL`, and a context missing a required input (for example no
`tijori_company_id`) gives `FAILED`, not `KEPT`. Explicit cases:
- **expected empty:** NETWEB's company-consolidated-empty-shell gives `EMPTY`, not `FAILED`;
- **deferred readers:** filter-advanced-search-api (only a retained 500, so `UNUSABLE` by the
  HTTP rule) and overview-company-timeline-sidepanel (G4 `KEPT`) have no reader test here; the
  test asserts neither has a G0 `PARSERS` entry;
- **namespacing:** the Screener and Tijori company-search-api adapters both record outcomes in
  one database, under their two namespaced versions.

Test seams: `PARSERS`.

Dependencies: 4, 6.

Risks: another overview id may turn out to have no covering `TijoriOverviewSection` member; it
is then `FAILED` (`detail`: `no reader`), listed incomplete and moved to a follow-up parser bead,
never `KEPT`. About 430 lines.

### Task 9: G1 company series parsers

Goal: each G1 company surface has one parser that stores every point with its verbatim text:
Tijori chartdata-price-api, chartdata-valuation-api, chartdata-median-pe-api, capex-api,
debt-api, revenue-mix-history-api, financials-popup-chart-api, financial-statement-compare-api
(Screener chart-api is Task 4).

Files:
- Modify: `src/fundamentals/ingest/vendor_surface_series.py`; `src/fundamentals/ingest/vendor_surface_parse.py`
- Test: `tests/fundamentals/test_vendor_surface_series.py`

Interfaces:
- Consumes: `Body`, `VendorValue`, `PARSERS` (Task 4).
- Produces: one `PARSERS` entry per surface, `"<site>:<surface>.v1"`; `tijori_data(body: bytes) -> Any`
  (decodes the `{data, status}` envelope, including the JSON string inside `data`, with `Decimal`
  lexemes).

Approach: one small function per surface over its observed shape (`eod_price` rows; valuation
`[[date, value], ...]`; median-PE horizon keys; capex/debt `[{name, data}]`; statement-compare
nested rows). Shape violations raise and record `FAILED`; never skipped.

Verification: retained tests through the shared harness, parametrised over every surface and the
kinds that have a 200 body: rows > 0, two hand-read values, a truncated variant `FAILED`.

Test seams: `PARSERS`.

Dependencies: 4, 6.

Risks: shape variance across kinds. About 310 lines.

### Task 10: G2 company table parsers

Goal: the G2 company surfaces are parsed by code into positional cells with verbatim labels:
- Screener: section-documents (four blocks: Announcements, Annual reports, Credit ratings,
  Concalls; each row is title, date and link), company-trades, company-announcements;
- Tijori: overview-company-filings, overview-customers, overview-suppliers, overview-brands,
  overview-connections, the shareholding-overview Overview table (`var chartData`),
  shareholding-trend (`var trendData`).

Files:
- Create: `src/fundamentals/ingest/vendor_surface_tables.py`
- Modify: `src/fundamentals/ingest/vendor_surface_parse.py`; `config/vendor_surface/surfaces.yaml` (`selector` values)
- Test: `tests/fundamentals/test_vendor_surface_tables.py`

Interfaces:
- Consumes: `Body`, `VendorValue`, `PARSERS`, `SurfaceSpec.selector` (Task 4).
- Produces: `read_html_table(tree, selector: str, table_key: str) -> tuple[VendorValue, ...]`
  (header cells → `column_label`, first cell → `row_label`, `href` → `link`, a row whose cell
  count differs from the header raises); `read_js_var(body: bytes, name: str) -> Any`; registry
  entries `"<site>:<surface>.v1"`.

Approach: the generic reader wherever the body is a plain `<table>`; one function per card list
or script variable. An absent block on a kind that lacks it is `EMPTY` for that `table_key`,
decided by the block heading's absence, never by catching an exception.

Verification: retained tests on APARINDS, ETERNAL, KIRANVYPAR and HDFCLIFE: documents blocks
present or absent per the catalog's `varies_by`; **company-trades with repeated row labels stores
every row, distinguished by `row_index`** (ruling 3's integration case); two hand-read rows per
surface; a ragged row `FAILED`.

Test seams: `PARSERS`, `read_html_table`.

Dependencies: 4, 6.

Risks: Tijori card markup may not be tabular. About 325 lines.

**Phase 2 exit:** expected: every company surface in §2 for APARINDS; completed: one live
`vendor capture --symbol APARINDS` within budget, outcomes recorded; refused: deny-listed and
stopped requests listed (expected none); incomplete: expansion gaps, `topology unknown` and
pending-a-200 surfaces listed. Canary green; full suite, gate and Sol review.

### Phase 3 — Market breadth (tier 2) and cadence

### Task 11: Market traversal and pagination

Goal: `vendor capture --market` fetches, registers and dispatches every market-scope surface in
§2 by the finite traversal table of §2, paginates feeds by stable row id, continues Tijori date
ranges from the last completed boundary, and continues `company-timeline-api` by its cursor.

Files:
- Modify: `config/vendor_surface/surfaces.yaml` (market entries); `src/fundamentals/ingest/vendor_surface_expand.py` (one function per traversal row); `src/fundamentals/ingest/vendor_surface_capture.py`; `src/fundamentals/api/vendor_surface_cli.py`
- Test: `tests/fundamentals/test_vendor_surface_market.py`

Interfaces:
- Consumes: `capture`, `Request`, `RunReport`, `EXPANSIONS` (Tasks 4 and 7); `feed_rows` (Task 13).
- Produces: `market_requests(specs, pool) -> tuple[Request, ...]`; `capture_market(...) -> RunReport`;
  `MAX_FEED_PAGES = 20`; `traversal_key(request) -> str` (site, surface, normalised path, stable
  filter parameters; page, cursor and date-window parameters excluded); `progress(pool, key) ->
  Progress`, where `Progress(BaseModel)` has `boundary: Boundary | None` (from the last outcome
  with `traversal_done`), `resume_page: int | None` (the highest `traversal_page` recorded under
  the key since that completion, or `None`) and `resume_url: str | None` (that page's retained
  request URL, from which the active date window and cursor are read), and `Boundary(BaseModel)`
  has `row_id: str | None`, `date_to: date | None`, `cursor: str | None`.

Approach:
- Each page's outcome records `traversal_key` and `traversal_page`; the page that reaches the
  boundary or the last page records `traversal_done`. Only a completed traversal sets the next
  boundary. A capped traversal is `INCOMPLETE` in the report and resumes next run from
  `resume_page` towards the same boundary; nothing outside the retained outcomes holds state.
- The G4 hub rows fetch only links found on the hub's first page or first result page.
- Tijori date ranges are `MM/DD/YYYY,MM/DD/YYYY` from the last completed `date_to` to today when
  a traversal starts; a resumed traversal keeps the window in `resume_url`.
- `robots.txt`, `sitemap.xml` and `llms.txt` are fetched weekly as G4.

Verification: retained tests through the shared harness: each traversal row yields > 0 children
from its named hub (the inferred index, person and HS hubs are confirmed or corrected here),
including the bounded G4 rows; the four market levels are reached; pagination stops on the seen
row id even when a newer page repeats a date; with a cap of 2, a 5-page traversal resumes at
page 2 on the second run and page 4 on the third, completes, and only then advances its boundary;
two `market-level` paths keep separate progress; a capped Tijori date-window traversal resumed on
the next day keeps its original window (same key, window read from the retained URL); a timeline
cursor continues until exhausted.

Test seams: `capture_market`, `progress`.

Dependencies: 7, 13.

Risks: the four market levels and HS codes may exceed one run's budget; Task 14's ordering
carries the rest over. About 470 lines.

### Task 12: G1 market series parsers

Goal: parsers for the G1 market surfaces: Screener fii-api, hs-data-api; Tijori macro-chart-api,
sector-ms-chart-api, sector-company-opm-api, index-data-api, index-metric-data-api.

Files:
- Modify: `src/fundamentals/ingest/vendor_surface_series.py`; `src/fundamentals/ingest/vendor_surface_parse.py`
- Test: `tests/fundamentals/test_vendor_surface_series.py`

Interfaces:
- Consumes: `tijori_data` (Task 9); `VendorValue`, `PARSERS` (Task 4).
- Produces: one `PARSERS` entry per surface, `"<site>:<surface>.v1"`.

Approach: one small function per surface over its retained 200 shape. `hs-data-api` keeps the HS
code in `table_key`.

Verification: retained tests, parametrised: rows > 0, two hand-read values, `FAILED` on
truncation.

Test seams: `PARSERS`.

Dependencies: 9.

Risks: none beyond shape variance. About 230 lines.

### Task 13: G2 market table parsers

Goal: parsers for the G2 market surfaces:
- Screener: results-latest, upcoming-results, concalls-feed, annual-reports-feed,
  announcements-feed, market-pulse, corporate-actions-feed, trades-feed, ipo, ratings-feed,
  market-level, index-page, person-page, screen-raw (an HTML table, read by `read_html_table`);
- Tijori: quarterly-results-api, upcoming-events-api (both scoped by `company_ids=` to the covered
  companies, aa6.26), raw-materials. Idea pages are not tied to a covered company and are dropped
  (aa6.26, `not-capturable.md`).

Only the feeds (spec flag `feed: true`) convert to `FeedRow`: results-latest, upcoming-results,
concalls-feed, annual-reports-feed, announcements-feed, corporate-actions-feed, trades-feed, ipo,
ratings-feed; Tijori quarterly-results-api and upcoming-events-api. Each feed row carries its
stable row id (link or announcement id), the company link or symbol, and its date only where the
feed shows a full one. Ratings and annual-report rows are undated or year-only: `row_date` is
`None`, a year stays a cell, and retrieval time stays capture metadata; no date is invented. The
other G2 market surfaces (market-pulse, a hub of category links and counts; market-level,
index-page, person-page, screen-raw, raw-materials) keep only
positional cells and links; no date is validated on them.

Files:
- Modify: `src/fundamentals/ingest/vendor_surface_tables.py`; `src/fundamentals/ingest/vendor_surface_parse.py`; `config/vendor_surface/surfaces.yaml`
- Test: `tests/fundamentals/test_vendor_surface_tables.py`

Interfaces:
- Consumes: `read_html_table`, `PARSERS` (Task 10).
- Produces: registry entries `"<site>:<surface>.v1"`; `SurfaceSpec.feed: bool = False`;
  `FeedRow(BaseModel)`: `row_id: str`, `company: str`, `row_date: date | None = None`;
  `feed_rows(spec, values: tuple[VendorValue, ...]) -> tuple[FeedRow, ...]` (refuses a non-feed
  spec).

Approach: the generic table reader with selectors where possible; one function per Tijori card
fragment; on a feed whose rows show a full date, dates are parsed by code from the column's
observed format and an unparseable one makes the outcome `FAILED`.

Verification: retained tests, parametrised per surface: rows > 0 and two hand-read rows; for
each feed, `feed_rows` returns a stable row id and company for each row, and a date only on the
dated feeds; ratings-feed and annual-reports-feed rows have `row_date is None` with the year kept
as a cell; `feed_rows` refuses market-pulse.

Test seams: `PARSERS`, `feed_rows`.

Dependencies: 10.

Risks: Screener's headings mislead on periodicity (data-quality warning 1); labels are taken
verbatim and nothing is inferred. About 350 lines.

### Task 14: Universe and cadence — `vendor capture-due`

Goal: `fundamentals vendor capture-due`, run by the owner's cron (one documented crontab line),
captures whatever is due, oldest-due first, and nothing else:
- the universe is the covered watchlist: entities whose latest WATCHLIST decision is ADD
  (`eqos.watchlisted`), resolved to the NSE symbol and ISIN via `eqos.registry_view` (segment
  `NSE_EQ`, status `LISTED`), with vendor ids from `company_ids` (Task 4) and topology from
  `bind_topology` (Task 7); every surface is captured whatever the topology, and only a stock
  whose topology stays unknown has its basis-scoped outcomes reported incomplete;
- due-ness counts only usable captures (§1);
- a second same-day run does no new work unless a feed shows a new event or an acquisition is
  unfinished (capped traversal, pending statement refresh, unexpanded children, unresolved slug).

| Cadence | Surfaces | Due when |
|---|---|---|
| `DAILY` | company price and valuation (screener chart-api; tijori chartdata-price, chartdata-valuation, chartdata-median-pe) and market event feeds (announcements, results, corporate actions, deals/trades, calendars/upcoming) | no usable capture since 00:00 UTC today |
| `AFTER_RESULTS` | statements (screener company-page both bases, schedules-api, segments-api; tijori company-financials, financials-popup-chart-api, financial-statement-compare-api) | a results trigger is pending for the company (below), or the company has no usable statement capture |
| `WEEKLY` | everything else | no usable capture in the last 7 days |

**Results trigger.** A trigger is a results-feed row (Screener results-latest, Tijori
quarterly-results-api) identified by its `row_id`, with `first_seen` = the `retrieved_at` of the
first capture that contained it. It creates one **obligation** per surface × basis: each
`AFTER_RESULTS` vendor surface for each basis the company's topology publishes (Screener company
page per basis, schedules-api, segments-api; Tijori company-financials,
financials-popup-chart-api, financial-statement-compare-api). An instance meets the refresh rule
when it has a usable capture after `first_seen` that shows a latest period column newer than the
latest period before `first_seen` (a child with no period header: a usable capture after its
parent's satisfying capture). An obligation is satisfied only when **every required expanded
instance** of its surface and basis (each schedule, segment and popup chart the parent's
satisfying capture advertises) meets the rule; a missing or failed child keeps it pending. While
the topology is unknown, no basis obligation exists and the statements are reported incomplete
each run, captured on the `WEEKLY` cadence. Each run captures only the pending obligations again (at most
once a day each); an obligation is exhausted after 10 attempts and reported `INCOMPLETE`
(explicit, every run). The company trigger clears only when every obligation is satisfied or
exhausted. All of this is computed from stored outcomes and values; no new table.

**Budget order.** All due requests are sorted by `due_since` (oldest first; never-captured first);
children of an expanded parent inherit the parent capture's time, so an unfinished expansion
continues on the next run before newer work.

On-demand capture of an owner screen stock stays `vendor capture --symbol` (Task 7); it never
enters the schedule.

Files:
- Create: `src/fundamentals/ingest/vendor_surface_due.py`
- Modify: `src/fundamentals/api/vendor_surface_cli.py`; `config/vendor_surface/surfaces.yaml` (cadence per entry); `docs/research/vendor-surface/runbook.md` (§6: the cron line, the `STOP-<site>` reset rule, the site lock)
- Test: `tests/fundamentals/test_vendor_surface_due.py`

Interfaces:
- Consumes: `CompanyIds`, `company_ids` (Task 4); `company_requests`, `resolve_tijori_slug`, `bind_topology`, `EXPANSIONS` (Task 7); `market_requests`
  (Task 11); `feed_rows`, `FeedRow` (Task 13); `USABLE` (Task 3).
- Produces:
  - `is_due(spec: SurfaceSpec, last_usable: datetime | None, now: datetime, trigger_pending: bool) -> bool`;
  - `pending_triggers(pool, ids: CompanyIds) -> tuple[Trigger, ...]`, `Trigger(BaseModel)`:
    `row_id: str`, `first_seen: datetime`, `obligations: tuple[Obligation, ...]`;
    `Obligation(BaseModel)`: `site: Site`, `surface: str`, `basis: Basis | None`,
    `attempts: int`, `state: ObligationState` (`PENDING`, `SATISFIED`, `EXHAUSTED`);
  - `covered_universe(pool) -> tuple[CompanyIds, ...]` (topology filled by `bind_topology`);
  - `due_requests(pool, specs, now) -> tuple[Request, ...]` (sorted);
  - CLI `vendor capture-due`: exits 1 if any site stopped or any request was refused.

Approach: run order is market daily feeds first (so triggers exist), then everything else by
`due_since`. `now` is read once at the CLI root and passed down.

Verification:
- `is_due` parametrised over the three cadences, including first capture and an `UNUSABLE`-only
  history (still due);
- `covered_universe` `pg` case: ADD, REMOVE, ADD;
- integration (shared harness): a second same-day run makes zero requests; with a new feed row it
  makes only the triggered ones;
- trigger: with both Screener bases and Tijori financials required, the consolidated page
  showing the new period satisfies only its own obligation; the trigger stays pending (and
  refetches only the other two) until the standalone page and Tijori show it or exhaust after 10
  attempts, and an exhausted obligation is `INCOMPLETE`;
- expanded instances: of two required consolidated schedules, one refreshed and one `FAILED`,
  the schedules-api consolidated obligation stays pending and only the failed one is refetched;
- **budget:** with a budget of 3 and 7 due requests across three runs, every request is captured
  exactly once and oldest first.

Test seams: `is_due`, `pending_triggers`, `due_requests`, CLI exit code.

Dependencies: 7, 11, 13.

Risks: "latest period column" reads the G0 adapter's statement column labels; an unreadable
header keeps that obligation pending (fail closed). About 470 lines.

**Phase 3 exit:** expected: the covered universe's due set; completed: two live `capture-due`
runs on one day, the second doing no new work without a new event or unfinished acquisition;
refused and incomplete listed in both reports. Canary green; full suite, gate and Sol review.

### Phase 4 — Group 3, label proposals, bake-off, free text

### Task 15: G3 cell parsers

Goal: the G3 surfaces are parsed by code into positional cells with verbatim row and column
labels:
- Screener: section-insights (Yearly and Quarterly; the "Standalone data" tag goes to `basis`,
  per data-quality warning 4), company-compare (peers per §2);
- Tijori: benchmarking-benchmarking-financial (table reader) and
  benchmarking-benchmarking-business, read by two named readers: `benchmark_business_cards(tree)`
  for the KPI cards and `benchmark_business_charts(body)` for the chart `var` data.

No mapping happens here.

Files:
- Create: `src/fundamentals/ingest/vendor_surface_cells.py`
- Modify: `src/fundamentals/ingest/vendor_surface_parse.py`
- Test: `tests/fundamentals/test_vendor_surface_cells.py`

Interfaces:
- Consumes: `read_html_table`, `read_js_var` (Task 10); `VendorValue`, `PARSERS` (Task 4).
- Produces: `PARSERS` entries `"<site>:<surface>.v1"`; `benchmark_business_cards`,
  `benchmark_business_charts`; `cell_labels(pool, site: Site, surface: str) -> tuple[LabelSample, ...]`,
  where `LabelSample(BaseModel)` has `label: str`, `units: frozenset[str]` (the distinct
  `unit` values code read from that label's cells) and `per_share: bool` (code found per-share
  evidence: "per share", "/share", "₹/sh" or "EPS", case-insensitive, in the label or its unit).

Approach: as for G2. Benchmarking `n/a` cells keep `raw_text` with `value=None` and are not
`expected_numeric`.

Verification: retained tests on APARINDS, HDFCBANK, HDFCLIFE and CREDITACC: rows, kind-specific
labels (insurer KPIs for HDFCLIFE), the basis tag, and the card and chart readers each yielding
rows.

Test seams: `PARSERS`, `cell_labels`.

Dependencies: 10.

Risks: none beyond markup variance. About 240 lines.

### Task 16: Label proposals, code acceptance, and the model adapter

Goal: `fundamentals vendor map-labels --site S --surface ID` asks the owner-selected model once
per unasked G3 label (per prompt and dictionary version) for a proposed dictionary field. Code
**accepts** a proposal only when all three hold:
1. the reply's label equals the asked label verbatim;
2. the target is a `canonical_id` in the loaded dictionary;
3. the label's code-read unit is compatible with the target's `value_kind` (table below).

Otherwise the label is stored unmapped with a reason. Accepted mappings carry
`epistemic_class = inferred`.

| Code-read unit of the label's cells | Compatible `ValueKind` |
|---|---|
| currency amount (₹, Rs., Cr, Lakh) without per-share evidence | `CURRENCY_AMOUNT` |
| currency with per-share evidence (`LabelSample.per_share`) | `PER_SHARE_AMOUNT` |
| `%` | `PERCENTAGE` |
| `x` or bare ratio | `RATIO` |
| days | `DAYS` |
| bare count | `COUNT` |
| unknown, mixed, or per-share evidence on a non-currency unit | none (unmapped) |

A currency total never maps to `PER_SHARE_AMOUNT`, and an ambiguous label stays unmapped
(`contracts/canonical.py:19`: kinds are never interconverted).

Files:
- Create: `migrations/0045_vendor_labels_claims.sql`; `src/fundamentals/ingest/vendor_surface_model.py`; `src/fundamentals/ingest/vendor_surface_labels.py`; `config/vendor_surface/model.yaml` (`model_id: null`)
- Modify: `src/fundamentals/api/vendor_surface_cli.py`; table-enumerating tests (ripple)
- Test: `tests/fundamentals/test_vendor_surface_labels.py`

Interfaces:
- Consumes: `cell_labels`, `LabelSample` (Task 15); `canon.dictionary.load_dictionary(root,
  version)`; `DictionaryRow.value_kind`; `EpistemicClass` (`contracts/guidance_claim.py`).
- Produces:
  - `ModelReply(BaseModel)`: `text: str`, `input_tokens: int`, `output_tokens: int`;
  - `LabelModel(Protocol)`: `model_id: str`, `complete(self, system: str, user: str) -> ModelReply`;
  - `ChatCompletionsModel(model_id, base_url, api_key: SecretStr, *, timeout_seconds: float = 60.0, max_response_bytes: int = 200_000, max_output_tokens: int = 512, max_retries: int = 2)`;
  - `ModelSettings(BaseModel)`: `model_id: str | None`, `base_url`, `key_file`,
    `prompt_version`, `dictionary_version`; `ModelNotSelected(Exception)`;
  - `MapReason(StrEnum)`: `MAPPED`, `NOT_IN_DICTIONARY`, `LABEL_ALTERED`, `UNIT_INCOMPATIBLE`,
    `MODEL_UNMAPPED`, `MALFORMED_REPLY`;
  - `UNIT_KINDS: Mapping[str, frozenset[ValueKind]]` (the table above);
  - `accept(sample: LabelSample, reply_text: str, fields: Mapping[str, ValueKind]) -> tuple[str | None, MapReason]`;
  - `map_labels(pool, model: LabelModel, settings: ModelSettings, site: Site, surface: str, fields) -> int`.

Approach:
- Migration 0045 (pattern of Task 3: guard, mutation and truncate triggers, grants):
  - `eqos.vendor_label_proposals` (append-only): `source_id`, `surface`, `label`, `units`,
    `field` (nullable), `reason`, `epistemic_class` (CHECK `inferred` when `field` is set),
    `model_id`, `prompt_version`, `dictionary_version`, `prompt`, `raw_response`, `recorded_at`.
    The current mapping of a label is its latest row; a correction is a new row
    (`model_id = 'correction:<author>'`). No uniqueness on label.
  - `eqos.vendor_text_claims` (Task 18 uses it): `capture_ref_id` FK, `surface`, `kind` (CHECK
    `NAME`/`CLAIM`), `span_start`, `span_end`, `text`, `model_id`, `prompt_version`,
    `epistemic_class` (CHECK `inferred`), `recorded_at`; unique (`capture_ref_id`, `surface`,
    `model_id`, `prompt_version`, `kind`, `span_start`, `span_end`). Tombstone extended to null
    `text`.
- `map_labels` takes `pg_advisory_xact_lock(hashtext('eqos.vendor_label_map'))` per label
  transaction; a label already asked under the same model, prompt and dictionary version is
  skipped. A crash between the model call and the insert may ask again; exactly-once is not
  promised.
- The CLI refuses with `ModelNotSelected` (exit 2) when `model_id` is null. The key is read at the
  CLI root from `${EQOS_SECRETS_DIR:-~/.secrets}/<key_file>`.
- The prompt asks for strict JSON `{"label": ..., "field": ... | null}`; the model never sees
  values.

Verification: `accept` parametrised: verbatim + dictionary + compatible → `MAPPED`; recased label
→ `LABEL_ALTERED`; unknown field → `NOT_IN_DICTIONARY`; `%` label to a `CURRENCY_AMOUNT` field →
`UNIT_INCOMPATIBLE`; "EPS (₹)" to a `PER_SHARE_AMOUNT` field → `MAPPED`; "Sales (₹ Cr)" to a
`PER_SHARE_AMOUNT` field → `UNIT_INCOMPATIBLE`; non-JSON → `MALFORMED_REPLY`. A `pg` test with a fake model: each label
asked once across two runs; the raw response, prompt and versions stored; a correction row
supersedes. The CLI with `model_id: null` exits 2. No test calls a real model.

Test seams: `accept`, `map_labels` with a fake `LabelModel`.

Dependencies: 15.

Risks: dictionary v3 has no operating KPIs (CASA, NIM, ARPU, order book); most G3 labels stay
unmapped, which is correct. The POST to a model provider is outside the vendor GET-only rule.
About 465 lines.

### Task 17: Bake-off evaluation script

Goal: `uv run python scripts/vendor_surface_bakeoff.py --candidates <yaml>` (a bounded evaluation
script, not a product command) scores each candidate against a model-checked key and writes
`docs/research/vendor-surface/bakeoff-<date>.md`. For labels it reports, per candidate and for
the always-unmapped baseline: positive-label accuracy (correct field on key rows whose field is
set), false mappings (an accepted field that differs from the key), abstentions (unmapped where
the key has a field), and cost (tokens × configured price). For spans it reports precision and
recall of accepted spans against key spans (exact offsets). It never writes `model.yaml`.

Files:
- Create: `scripts/vendor_surface_bakeoff.py`; `config/vendor_surface/label_key.yaml` (`{site, surface, label, field | null, why}` per row); `config/vendor_surface/span_key.yaml` (`{capture, kind, span_start, span_end}` per row)
- Test: `tests/fundamentals/test_vendor_surface_bakeoff.py`

Interfaces:
- Consumes: `accept`, `ChatCompletionsModel`, `LabelModel` (Task 16); the G3 parsers and
  `cell_labels` over `kinds-index.json` bodies (Tasks 6, 15); `validate_spans` (Task 18).
- Produces: `score_labels(answers, key) -> LabelScore` (`accuracy`, `false_mappings`,
  `abstentions`); `score_spans(accepted, key) -> SpanScore` (`precision`, `recall`).

Approach: the key is drafted by an implementer with a `why` citing the dictionary `meaning`,
reviewed by Sol, and recorded as **model-checked** (not human-checked). Sequence, each a separate
step: key review → scoring run → owner selects `model_id` in `model.yaml` → runtime use.

Verification: `score_labels` and `score_spans` unit tests (arithmetic, baseline scores zero false
mappings); one run with two fake models gives the expected table.

Test seams: `score_labels`, `score_spans`.

Dependencies: 6, 15, 16, 18.

Risks: a model-drafted key can bias toward similar models; Sol's review and the `why` column
mitigate. About 330 lines, of which the keys are about 150.

### Task 18: Free-text span extraction

Goal: `fundamentals vendor extract-text` sends each unprocessed text capture (Screener
company-page About and Key Points; announcement subject text from parsed company-announcements
and announcements-feed rows) to the owner-selected model. The model returns spans (kind, start,
end). Code stores `text = source[start:end]` for each span inside the source; paraphrases and
numerical interpretation are never stored. Every processed capture gets an outcome in
`eqos.vendor_outcomes` (parser version `claims:<model_id>:<prompt_version>`) through
`VendorValuesStore.record(..., row_count=<accepted spans>)` with `rejected_count` on the outcome,
even when zero spans are accepted.

Files:
- Create: `src/fundamentals/ingest/vendor_surface_claims.py`
- Modify: `src/fundamentals/api/vendor_surface_cli.py`
- Test: `tests/fundamentals/test_vendor_surface_claims.py`

Interfaces:
- Consumes: `LabelModel`, `ModelSettings`, `ModelNotSelected` (Task 16); `VendorValuesStore`,
  `Outcome` (Task 3); `Body`, `parse_document`.
- Produces: `ClaimKind(StrEnum)`: `NAME`, `CLAIM`; `Span(BaseModel)`: `kind`, `start: int`,
  `end: int`; `source_text(site: Site, surface: str, body: bytes) -> str` (code-extracted,
  whitespace-normalised); `validate_spans(source: str, reply_text: str) -> tuple[tuple[Span, ...], int]`
  (accepted, rejected); `extract_text(pool, store, model, settings) -> int`.

Approach: a span is rejected when out of bounds, empty or overlapping an earlier accepted span of
the same kind. Each capture is processed once per model and prompt version (outcome uniqueness).
The claims rows and the outcome are written in one transaction (`record(..., conn=...)`).

Verification: `validate_spans` parametrised (in-bounds kept; out-of-bounds and empty rejected;
text equals the source slice); a retained test that `source_text` on APARINDS returns the About
text; a fake-model `pg` test stores spans labelled `inferred` and an outcome with counts, and a
reply with zero valid spans still records an outcome.

Test seams: `validate_spans`, `source_text`.

Dependencies: 3, 16.

Risks: off-host filing and concall bodies are DOCS-1; DOCS-1 can reuse `validate_spans`. About
230 lines.

**Phase 4 exit:** expected: G3 cells for the 18 kinds, the label and span keys, the bake-off
report; completed: key reviewed by Sol (model-checked), scoring run, report committed; refused:
`map-labels` and `extract-text` with no selected model (exit 2, proven by test); incomplete: owner
model selection and live runtime fills, which follow this phase. Full suite, gate and Sol review.

### Phase 5 — Drift and raw-first

### Task 19: `vendor canary` — runbook canaries as one command

Goal: `fundamentals vendor canary` exits 0 only when all hold, otherwise naming each failed check:
- every runbook §4 check (S1–S8, T1–T8) passes on a fresh live fetch through the fetch path, each
  response registered;
- handler count: on S1, elements whose `onclick` names `showSchedule`, `showShareholders` or
  `showSegment` (whitespace tolerated) equal the count the pinned discovery regexes decode (audit
  finding 4, detected without editing the pinned parser);
- growth rows: no `#profit-loss` growth range-table data row has a cell count other than 2;
- `yield_drift` (Task 5) is empty.

Files:
- Modify: `src/fundamentals/ingest/vendor_surface_canary.py`; `src/fundamentals/api/vendor_surface_cli.py`
- Test: `tests/fundamentals/test_vendor_surface_canary.py`

Interfaces:
- Consumes: `VendorFetcher`, `register` (Tasks 2, 3); `yield_drift`, `Drift` (Task 5);
  `read_page_hooks` (`screener_company_discovery`); `read_js_var` (Task 10).
- Produces: `Canary(BaseModel)`: `name: str`, `site: Site`, `url: str`,
  `check: Callable[[CaptureRecord, bytes], tuple[str, ...]]`; `CANARIES: tuple[Canary, ...]`;
  `run_canaries(fetcher, store, pool) -> tuple[Drift, ...]`.

Approach: one function per runbook row's markers. S4 takes its `parent` label from S1's retained
body; T7 computes its date range; S8 expects a 302 and T8 a 302 to `/dashboard/`. No cache. Each
canary capture is registered and gets an outcome (parser version `canary.<name>.v1`: `OK` when
its check passes, including an expected redirect control, `FAILED` with the check named
otherwise) **before** `yield_drift` runs, so the canary never flags its own captures.

Verification: retained tests run every canary on the 2026-10-28 reference bodies and all pass,
and `yield_drift` afterwards reports nothing for the canary's own captures (the S8 and T8
redirects included);
mutation fixtures (parametrised through the shared harness) each fail with the canary named: S1
with `showSchedule (`; S1 with one period `<th>` removed; T1 with the `ratios_table` island
emptied; T4 with `eod_price: []`; a growth row with 3 cells.

Test seams: `run_canaries` with a fake opener; each `Canary.check`.

Dependencies: 5, 7, 10.

Risks: S7's `utils.<hash>.js` URL comes from the page's `cdn-static` script tag; a changed tag is
itself drift. About 420 lines.

### Task 20: Raw-first for the Tijori overview and shareholding commands

Goal: `tijori-overview` and `tijori-shareholding` fetch through the shared `capture` path
(Task 4; surfaces `vs.company-overview` and `vs.company-shareholding`), which registers the
capture and records its outcome through the Task 8 adapter on success and failure, and on a stop
registers the response with an `UNUSABLE` outcome before re-raising. The command then builds its
artifact from `store.read_body(record)` with `build_tijori_overview` or
`build_tijori_shareholding`, passing `retrieved_at=record.retrieved_at`. Not `parse_overview_bytes` or `parse_shareholding_bytes`:
they stamp `now()` (`tijori_source.py:450`, `:472`).
A parse failure leaves the capture registered and readable. This closes the "TO" and "TS" rows of
audit finding 2 only.

Files:
- Modify: `src/fundamentals/api/tijori_overview_cli.py`; `src/fundamentals/api/tijori_shareholding_cli.py`
- Test: the existing overview and shareholding CLI tests, plus one raw-first case each

Interfaces:
- Consumes: `VendorFetcher`, `SiteSession`, `Site` (Task 2); `VendorValuesStore` (Task 3);
  `capture`, `Request` (Task 4); the G0 overview and shareholding adapters (Task 8); `yield_drift`
  (Task 5);
  `build_tijori_overview` (`ingest/tijori_overview.py`), `build_tijori_shareholding`
  (`ingest/tijori_shareholding.py`) (imported only, not edited).
- Produces: no new names; each command gains `--snapshot-root` (default `data/raw/snapshots/v1`).

Approach: replace the `source.fetch_overview` and `source.fetch_shareholding` calls at the
composition root; the pinned `tijori_source.py` is not edited; artifact output is unchanged.

Verification: existing tests pass; per command, parametrised: success records an `OK` outcome;
an injected parse failure leaves the capture registered with its hash and retrieval time and a
`FAILED` outcome; a fake 429 registers the response with an `UNUSABLE` outcome and writes the
stop; after each case `yield_drift` reports no drift. The artifact's retrieval time equals the
capture's `retrieved_at`.

Test seams: the CLI entry functions with an injected fetcher.

Dependencies: 4, 5, 8.

Risks: the five out-of-scope raw-loss paths stay open; each is a follow-up bead. About 185 lines.

**Phase 5 exit:** expected: all canaries and the two raw-first commands; completed: a live
`vendor canary` green and the mutation fixtures red; refused: none expected; incomplete: the five
follow-up beads (out-of-scope list) and the pending-a-200 parsers, filed. Full suite, gate, the
Sol phase-end review and the closing critical review.

## 5. Resolved questions (rulings of 2026-10-28)

1. **Model adapter:** one OpenAI-compatible adapter with response-byte, output-token and retry
   bounds (Task 16). No SDK dependency.
2. **Bake-off key:** drafted by an implementer, reviewed by Sol, recorded as model-checked, never
   as human-checked (Task 17).
3. **Tijori slug:** resolved and verified through `entity/discovery.py`; an explicit failure only
   until resolved, retried every run (Task 7).
4. **company-compare:** stays G3; peers are other covered-watchlist stocks; with one covered
   stock there is no compare (Task 7).
5. **Filing and concall text:** on-host text now (Task 18); DOCS-1 reuses `validate_spans`.
6. **Market breadth:** the finite traversal table in §2, covering every known level.
7. **Stops:** durable `STOP-<site>` markers, reset by hand after diagnosis; one site lock across
   commands (Task 2, runbook §6).
8. **`forecasts` and `section-analysis`:** G4.

## 6. Open questions

None. The `_VENDOR_HOLDS` line (Task 1) is orchestrator-approved.

Residual risk: a single-basis stock with an unmarked page and no `config/watchlist.yaml` topology
stays `topology unknown` (kept, not parsed) until a person adds its topology; and the first-capture
binding trusts the marker plus warehouse id on the page it gates, which the canaries watch.

## 7. Self-review

1. **Spec coverage.**

   | Decision | Covered by |
   |---|---|
   | 1 (fetch and keep, raw first) | Tasks 2, 3, 4, 7, 11, 20 |
   | 2 (code parse) | Tasks 4, 8, 9, 10, 12, 13, 15 |
   | 3 (model only for labels and text; bake-off; model id as config) | Tasks 16, 17, 18 |
   | 4 (group 4 listed by id) | §2 |
   | 5 (universe) | Tasks 7, 14 |
   | 6 (cadence, one command) | Task 14 |
   | 7 (retention: keep) | Task 1 |
   | 8 (deny-list, pacing, stop statuses, GET only) | Task 2 |
   | 9 (drift) | Tasks 5, 19 |

   Audit: finding 1 is §2 and Tasks 7, 11; finding 2 is Tasks 2, 3, 20 for this workflow's paths,
   plus five follow-up beads (not closed here); finding 3 is Task 1; finding 4 is Task 19
   (detect) and Task 7 (tolerant expansion); finding 5 is Tasks 7, 11 (advertised URLs,
   pagination, `INCOMPLETE`).
2. **Placeholder scan.** No "TBD" or "similar to Task N"; each parser task names its surfaces and
   behaviours under test.
3. **Name consistency.** `VendorFetcher`, `Site`, `SiteSession`, `Fetched`, `PgSiteLock`,
   `is_denied`, `normalise`, `request_key` (Task 2); `register`, `VendorValuesStore`,
   `VendorValue`, `Outcome`, `OutcomeStatus`, `USABLE` (Task 3); `SurfaceSpec`, `ParseGroup`,
   `Cadence`, `Scope`, `Body`, `PARSERS`, `ParserEntry`, `Request`, `RunReport`,
   `parse_and_record`, `capture`, `reparse`, `dispatch_vendor_command`, `CompanyIds`,
   `company_ids`, `ParseContext` (Task 4); `yield_drift`,
   `Drift` (Task 5); `load_request_index` (Task 6); `EXPANSIONS`,
   `resolve_tijori_slug`, `company_requests`, `capture_company`, `bind_topology` (Task 7); `tijori_data` (Task 9);
   `read_html_table`, `read_js_var` (Task 10); `market_requests`, `traversal_key`, `progress`,
   `Progress`, `Boundary` (Task 11); `FeedRow`, `feed_rows` (Task 13); `covered_universe`, `due_requests`,
   `pending_triggers`, `Trigger`, `Obligation` (Task 14); `cell_labels`, `LabelSample` (Task 15); `LabelModel`,
   `ChatCompletionsModel`, `ModelSettings`, `MapReason`, `accept` (Task 16); `validate_spans`
   (Task 18). Each is consumed verbatim later.
4. **Gap-naming pass.**
   - Migrations: 0044 (Task 3, including `vendor_basis_bindings`) and 0045 (Task 16), with the
     table-enumeration ripple.
   - Retention: Task 1's hold and the D9 policy note; licence-end guard and tombstone (Task 3).
   - Rollout: the cron line, stop reset and site lock in runbook §6 (Task 14).
   - Glossary: no new `CONTEXT.md` term; "vendor value" is a plain description.
   - Docs: the orchestrator adds one `docs-index.md` line for this plan when approved.
   - Follow-ups: five raw-loss beads and one pending-a-200 parser bead.
