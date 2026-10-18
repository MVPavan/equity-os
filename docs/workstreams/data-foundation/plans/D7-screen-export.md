# D7 Screen Export Implementation Plan

Status: approved r3 — Sol r1, r2 REVISE; r3 **APPROVE** (GPT-6.1 Sol, 2026-10-18). Dispositions at the end.
**Revised 2026-10-18 (direct formula queries, end of file): approved by Sol (direct-query r2 APPROVE, 2026-10-18); the revision overrides the sections it names.**
**Origin:** bead `eqos-351`; owner decisions 2026-10-18 (automated export of both vendors' saved
screens, no HTML results extraction, cross-check as diagnostics, legacy deleted); evidence
[`screen-export-probe.md`](../../../research/screen-export-probe.md); amends [D7](D7.md); absorbs
`eqos-8hp`. **Goal:** one owner command exports a configured screen from **both** Screener (CSV)
and Tijori (JSON), retains every response as a capture, binds members fail-closed, and makes each
one-sided or unresolved member a review item; D7 Stage 4 runs over a derived extract of it.
**Out of scope:** scheduling; HTML results extraction; any `?q=`, `?page=`, `?sort=`, `?limit=`
Screener URL; other-vendor reads beyond S5's fixed table; screen values as financial figures; live
batch acquisition (D7 Q2); `eqos-s02` (binding uses only frozen namespaces).
**Constraints:**
- Migrations forward-only, `0001`–`0032` immutable; adds the next two free numbers (`0033`, `0034`;
  re-check at dispatch). Strict mypy, ruff, frozen Pydantic, enums, structlog; files ≤ 800 lines.
- Requests only: Screener `/explore/`, `/screens/<id>/<slug>/`, that page's export form action;
  Tijori `/api/filter_queries/search/?owner=true&limit=100&offset=0`, `…/advanced_search/`; plus
  S5's one-page reads (Screener company page, Tijori overview) through the existing readers.
  ≥ 2 s between request attempts (S3), 30 s timeouts, redirects refused, existing credential loaders,
  no cookie or token logged, no account identifier committed (ids read at run time).
- Committed fixtures hold development companies only; full exports stay gitignored in
  `data/raw/screen-exports/`. No live network in the suite; opt-in smoke `RUN_SCREEN_EXPORT_LIVE=1`.

## Rulings (Sol r1 rulings (a)–(e) applied)

- **S1 Amendment (ruling a).** A new amendment record (Task 1) replaces the whole ledger spec §4
  **Screens** paragraph (`docs/specs/2026-10-12-report-ledger-memory-and-data-lifecycle.md`
  lines 356–359, quoted verbatim as *before*) with:
  > **Screens.** A screen definition is owner-authored text saved at a vendor (a Screener saved
  > screen or a Tijori saved query), versioned with a hash of the definition as fetched. A screen
  > run is the vendor's own export of that saved screen, fetched by the system on an owner command:
  > Screener's export form (CSV) and Tijori's saved-query results endpoint (JSON). The system
  > never requests `?q=` or other query-string screen URLs and requests only the endpoints the
  > amendment record lists. A screen run records who ran it, when, its definition and results
  > captures (`VENDOR`) and its members, each resolved by exchange identifiers to a registry row
  > or `UNRESOLVED`. A member found on one side only, or unresolved, is a review item until the
  > owner disposes it.

  D7.md's constraint, R5 (now: only `coverage export` makes requests) and Q1 cite the record,
  which needs its own real Sol approval (Task 1), not this plan's.
- **S2 Config (finding 3).** `config/screens.yaml`: a list of `{name, screener: <slug>, tijori:
  <saved query name>}`, both required. A slug or name absent from, or appearing twice in, the
  owner's listing refuses the export. CLI `fundamentals coverage export --screen <name>
  --snapshot-root <dir>`. Both vendors are fetched and checked before anything is written; a
  failure on either side writes nothing. No single-vendor branch exists.
- **S3 Transport and retention (findings 5, 7, 8, 9, 11).**
  - Surfaces: Screener page `SCREENER_SCREEN_PAGE = ("screener-subscriber", "SCREEN_DEFINITION")`,
    `Representation.HTML`; Screener CSV stays on `SCREEN_EXPORT` (`CSV`; comment updated); Tijori
    listing and results on `TIJORI_SCREEN = ("tijori", "SCREEN_RESULTS")`, `JSON`. All role
    `IDENTITY`, subscriber rights (D9 classes them `VENDOR` by source id).
  - Every response is stored through `entity.discovery.store_captures`. `screen_runs` gains
    `vendor`, `provenance`, `definition_capture_ref_id` (Screener page / Tijori listing); the
    existing `capture_ref_id` is the results capture (CSV / `advanced_search` JSON).
  - Definition versioning: screen text is the definition as fetched — Screener: the saved query
    text from the screen page (the probe did not retain a screen page, so Task 3 pins the element
    from the A1 page capture; zero or two such elements refuses); Tijori: the matched listing
    entry's `financial_query`, `alt_query`, `extra_cols` as canonical JSON. Prefixed `screener:` /
    `tijori:`. `eqos.screens` already keys on the text's SHA-256, so editing a saved screen under
    the same slug yields a new screen row.
  - Tijori JSON: `TijoriSource.fetch_json(url) -> bytes` over the existing request path refuses
    any status but 200 and any media type but `application/json` (`TijoriFetchError`).
  - Tijori listing: refuses when `next` is non-null or `count ≠ len(results)` (truncated).
  - Pacing (r2-3), every attempt ≥ 2.0 s apart, no new pacer: `ScreenerSessionConfig(
    min_request_spacing_seconds=2.0)` (its `RequestPacer` runs before every attempt, 429 retries
    included, `screener_session.py:385-386`); `TijoriSourceConfig(max_retries=1)` disables
    Tijori's retry (`tijori_source.py:166`, `:594`) and each Tijori call waits on one
    `RequestPacer(2.0)` (`http_session.py:168`); a transient Tijori failure refuses the export.
- **S4 Binding (ruling d, finding 10).** Registry membership only; not a vendor identity
  verification, and nothing writes identity layers.
  - Screener rows bind by **ISIN** to the registry's `LISTED` listing (NSE if present, else BSE):
    unknown ISIN → `UNKNOWN_ISIN`; two listings in one segment → `AMBIGUOUS_CODE`; a supplied NSE
    or BSE code naming a different listing → `CONFLICTING_CODES`.
  - Tijori rows bind by the **unique current NSE symbol**; a supplied `scripcode` (≠ 0) must name
    the same listing (else `CONFLICTING_CODES`); blank symbol → `NO_CODE` (BSE alone does not bind
    a Tijori row); if the ISIN's verified entity has a `TIJORI_SLUG` that differs from the row's
    `slug` → `CONFLICTING_CODES` (veto). An absent verified slug passes binding but is reported as
    "slug not verified", never as identity verified.
- **S5 Review items (findings 1, 2, 4, 10; ruling b).**
  - Item identity: `(pair_id, member_id)` — one `screen_run_pairs` row per export, one member of
    either run. Item status, separate from value availability:
    `UNRESOLVED` (the member did not bind; its reason) · `ABSENT` (bound, no member of the other
    run bound to the same ISIN, and the other run has no unresolved member) · `NOT_PROVEN` (bound,
    no bound counterpart, but the other run has unresolved members — `candidate_member_ids` lists
    those sharing an NSE or BSE code, possibly empty). Members bound on both sides are not items.
  - View `eqos.screen_review_items` (all items) and `eqos.screen_review_pending` (items with no
    disposition). No `queue_items` rows: D1b items need a comparison `run_id`, measurement key and
    pair identity (`0006:55-69`), and a pseudo-run would fabricate one.
  - Disposition: append-only `eqos.screen_member_dispositions (pair_id, member_id, kind, reason,
    evidence_ref, decided_by DEFAULT current_user, recorded_at DEFAULT eqos.store_now())`, `UNIQUE
    (pair_id, member_id)`; kinds reused from `queue_dispositions`: `ACCEPTED_AS_DEFINITION`
    (definitions differ, e.g. boundary market cap), `MAPPING_FIX`, `DISMISSED`; non-empty reason and
    evidence; a trigger refuses a member outside the pair's runs; owner INSERT only (`0025` pattern).
  - Values: no duplicate payload; locator = results capture + `screen_members.row_number` (CSV
    row / Tijori `data` index), hydrated verbatim via `SnapshotStore.read_capture_verified`.
  - Other vendor's values (r2-1): existing readers, one request per item. After the export
    commits, each pending `ABSENT`/`NOT_PROVEN` item whose NSE symbol names a
    `config/watchlist.yaml` stock with verified other-vendor identifiers gets one read: Screener
    only → `TijoriSource.fetch_overview` (one identity-gated overview page;
    `TijoriCompanyDetailsSection`, `tijori_overview_models.py:661`); Tijori only →
    `fetch_company_page` (one identity-gated page, built as `screener_company_cli.py:150`, no
    sub-documents) read by `top_ratios_list` + `read_quick_ratios` (`#top-ratios`). Bytes go
    through `store_captures`; `screen_other_vendor_reads (pair_id, member_id, capture_ref_id, gap)`,
    exactly one of the last two, records it; the printer re-reads the bytes with the same reader.
    Fixed correspondences (member's column verbatim → other vendor's field), no mapping framework:

    | Member's side | Column (evidence) | Other vendor's field (evidence) |
    |---|---|---|
    | Screener CSV | `Market Capitalization` (probe :49) | Tijori `market_cap` (:677) |
    | Screener CSV | `Price to Earning` (probe :49) | Tijori `price_earnings` (:678) |
    | Screener CSV | `PEG Ratio` (probe :49) | Tijori `price_earnings_growth` (:679) |
    | Tijori results | `<span>latest</span>Mcap<span>Cr</span>` (probe :108) | Screener `Market Cap` |

    `Market Cap` is evidenced only by `synthetic_screener_company.html`; Task 5 confirms it on a
    retained development page or drops the row. Other columns print `FIELD_NOT_EXPOSED`. Gaps
    instead of a read: `MEMBER_UNRESOLVED` (no listing), `NOT_VERIFIED` (no watchlist stock or
    other-vendor ids unverified, e.g. `unverified_screener_fields()`), `READ_REFUSED` (identity
    gate or non-OK outcome). Values print as vendor text side by side, never compared or stored.
- **S6 Stage 4 members (ruling c, finding 6).** Keep ETERNAL, POLYCAB, TITAN (batch), THERMAX,
  CGPOWER: replay needs retained generations (development companies only), held-out rules bar
  committing others, and the spec criterion is a five-member fixture. No realistic filter returns
  exactly these five, so production `coverage export` keeps every completeness check and the full
  A1/A2 responses stay retained, never committed;
  - the committed fixture is a **derived extract**: "remove every data row whose ISIN (Screener) /
    NSE symbol (Tijori) is not one of the five; nothing else changes; the Screener page is reduced
    to its definition element" — `total_results` and the page count still state the full counts;
  - the manifest records `derived_fixture: {rule, source_captures: [{vendor, role, sha256}],
    rows_kept, fixture_sha256}`; the e2e replays it through `record_screen_run` and the review
    views, not `export_screener`/`export_tijori`, whose count checks it would fail.

## Tasks

### Task 1: Amendment record (Screens paragraph)

Goal: a record amends spec §4 Screens as S1, approved by its own Sol review; D7.md cites it.
Files: Create `docs/blueprint/amendments/2026-10-18-screen-export.md` (`ledger_clause: §4:screens`,
verbatim before/after, permitted endpoints, `?q=` prohibition, vendor-terms note),
`reviews/D7-amendment-2-review.md` (Sol's real report, `VERDICT: APPROVE`, subject digest); Modify
`test_amendment_records.py` (`RECORDS["screen_export"]`), `D7.md` (constraint, R5, Q1).
Verification: `uv run pytest tests/fundamentals/test_amendment_records.py -k screen_export`.
Dependencies: none; Sol reviews the record before Task 4 merges. Estimate: ~60 doc, +6 test. Sonnet.

### Task 2: Delete the legacy query-URL subsystem (`eqos-8hp`)

Goal: nothing can request `/screen/raw/?query=`; `screener-screen` is gone. Files: Delete
`ingest/screener_screen{,_models}.py`, `api/screener_screen_cli.py`, `tests/fundamentals/
screener_screen_{fixtures,support}.py`, `test_screener_screen{,_acquire,_cli,_empty_refusal,
_oracle,_signoff}.py`; Modify `api/cli_parser.py`, `api/screener_cli_dispatch.py`,
`ingest/screener_session.py` (`fetch_screen_page`, only caller `screener_screen.py:221`), legacy
references in `test_phase3_outcomes.py`, `test_screener_watchlist_cli.py`, `test_coverage_batch.py`.
Verification: `grep -rn "screener_screen\|screener-screen\|fetch_screen_page" src tests` empty;
`fundamentals screener-screen` is an invalid choice; `pytest -k "screener or coverage or phase3"` green.
Dependencies: none. Estimate: −~2,500, ~15 edited. Sonnet.

### Task 3: Vendor export transport

Goal: from recorded responses, `export_screener(source, slug)` and `export_tijori(source, name)`
return a `VendorExport`; each refuses on: name absent or duplicated, truncated Tijori listing,
non-200 or wrong media type (both vendors), ragged CSV, missing `ISIN Code`, page result count ≠ CSV
rows, `total_results` ≠ `len(data)`, Screener definition element absent or duplicated.
Files: Create `src/fundamentals/ingest/screen_export.py`, `config/screens.yaml`; Modify
`ingest/tijori_source.py` (`fetch_json`, S3), `contracts/source_catalog.py` (`SCREENER_SCREEN_PAGE`,
`TIJORI_SCREEN`, `SCREEN_EXPORT` comment), `ingest/screener_watchlist.py` (promote `_cookie_state`,
`_export_form` to public names, no behaviour change); Test `tests/fundamentals/test_screen_export.py`,
fixtures `tests/fundamentals/fixtures/screen_export/`.
Interfaces: Consumes `ScreenerSessionSource.fetch_navigation`, `.post_form`;
`read_watchlist_export` (`screener_watchlist.py:226`) for the CSV; `TijoriSource` credentials.
Produces `ScreenConfig(name, screener: str, tijori: str)`, `load_screen_config(path)`;
`ScreenVendor`; `ScreenFetch(url, body, retrieved_at)`; `VendorExport(vendor, screen_text,
definition: ScreenFetch, results: ScreenFetch, rows: tuple[dict[str, str], ...])`.
Approach: Screener: GET `/explore/`, match the slug among "Your screens"; GET the page, read the
definition element and result count; POST its one export form as the watchlist does. Tijori: GET
the owner listing, match `name`; GET `advanced_search` with the stored `financial_query`,
`alt_query`, `extra_cols`, `query_id` and the probe's fixed flags (module constants). Rows keep
values as text. Fixtures: markup reduced to the elements read, headers/keys verbatim, development
rows only, no credential or account name. Opt-in live smoke asserts the count checks (`tmp_path`).
Verification: `uv run pytest tests/fundamentals/test_screen_export.py` — happy paths; each refusal
above, incl. Tijori 203, `text/html` and a listing with `next` set; a fake clock (patched
`time.monotonic`/`time.sleep`) shows every attempt ≥ 2.0 s apart incl. a Screener 429-then-200
retry; a Tijori 503 is attempted once and refuses; exactly 3 Screener and 2 Tijori requests.
Dependencies: Task 2. Estimate: ~160 src, ~25 Tijori/catalog/watchlist, ~135 test. Opus.

### Task 4: Paired screen runs, binding and the `export` command

Goal: `coverage export --screen <name>` records one Screener and one Tijori run
(`AUTOMATED_EXPORT`) linked to their definition and results captures, plus their pair; members
bind per S4; `coverage screen-run` no longer exists; `coverage batch` works unchanged.
Files: Create `migrations/0033_screen_export.sql` (`screen_runs.vendor`, `.provenance` — existing
rows backfilled `SCREENER`/`OWNER_EXPORT`, defaults then dropped — `.definition_capture_ref_id`
required unless `OWNER_EXPORT`; `screen_members.isin`, `.slug`; reason check gains
`UNKNOWN_ISIN`; `screen_run_pairs (id, screener_run_id, tijori_run_id)` with vendor checks,
owner INSERT, SELECT to all); Modify `coverage/screens.py` (`record_screen_run(pool, export,
snapshots) -> ScreenRun`, ISIN and Tijori rules), `api/coverage_cli.py` (`export` replaces
`screen-run`: fetch both, then one transaction writes captures, runs and pair); Test
`test_coverage_batch.py` (setup via `coverage export` over Task 3 fixtures, patched `build_opener`).
Produces `ScreenRun.vendor`, `ScreenMember.isin`/`slug`, `UnresolvedReason.UNKNOWN_ISIN`,
`ExportResult(screener: ScreenRun, tijori: ScreenRun, pair_id: int)`.
Verification: `pytest tests/fundamentals/test_coverage_{batch,registry}.py` — each S4 reason; both
capture refs resolve to stored bytes; an edited same-slug definition makes a second screen row; a
Tijori failure writes nothing; runtime INSERT refused; existing batch assertions hold.
Dependencies: Tasks 1 (approved), 3. Estimate: ~50 SQL, +80/−25 src, ~70 test. Opus.

### Task 5: Membership review items, other-vendor reads, holds

Goal: per pair, `screen_review_items` returns exactly the S5 items; `screen_review_pending` drops
disposed ones; S5 reads are retained; pending items hold their evidence; the owner disposes items.
Holds (r2-2), inside `0034`: `holds.py` `_FACTS` gains one root arm `OPEN_SCREEN_REVIEW` → both
runs' definition and results captures and the pair's read captures while the pair has a pending
item; `HoldRoot.OPEN_SCREEN_REVIEW` joins `_VENDOR_HOLDS` (`eligibility.py:23`). The last
disposition drops the root; licence end already wins (`eligibility.py:36`). Pair, disposition and
read inserts take the retention lock (`BEFORE INSERT` → `eqos.retention_shared()`, `0028:69`).
Files: Create `migrations/0034_screen_review.sql` (views, `screen_member_dispositions`,
`screen_other_vendor_reads`, membership and lock triggers, grants incl. SELECT to `eqos_purge`);
Modify `retention/holds.py` (+~8), `eligibility.py`, `contracts/retention.py` (+1 each),
`api/coverage_cli.py` (reads after commit; `coverage review --pair`, called by `export`;
`coverage dispose --pair --member --kind --reason --evidence`); Test `test_screen_review.py` (`pg`).
Verification: five shared, one only on each side, one unresolved Tijori member sharing a BSE code
with the Screener-only member → exactly: that `UNRESOLVED`, the Screener-only `NOT_PROVEN` with it
as candidate, the Tijori-only `ABSENT`; hydrated rows equal fixture rows; a disposition clears
pending; a second disposition, empty reason, foreign member and runtime INSERT are refused. Reads
(recorded development fixtures): a verified Screener-only member prints Tijori `market_cap`,
`price_earnings`, others `FIELD_NOT_EXPOSED`; unverified → `NOT_VERIFIED`, no request; identity
mismatch → `READ_REFUSED`. Holds (fake `now` past 12 months): pending → `HELD` by
`OPEN_SCREEN_REVIEW`; all disposed → `ELIGIBLE`/`WINDOW`; licence end while pending → `LICENCE_END`.
Dependencies: Task 4. Estimate: ~75 SQL, ~110 src, ~130 test. Opus.

### Task 6: D7 Task 5 as amended — frozen Stage 4 manifest

Goal: D7 Task 5 unchanged except: `header.csv_provenance` becomes `export_provenance:
AUTOMATED_EXPORT` plus the `derived_fixture` block (S6); `screen` adds the Tijori run's five
members and the expected review items (none for a five-on-both fixture); `check_ledger_stage4`
rejects any provenance but `AUTOMATED_EXPORT` and a missing `derived_fixture`.
Otherwise as D7 Task 5. The aid derives the fixture by the S6 rule, records source SHA-256s, and
hand-verifies the five rows (ISIN, NSE, BSE) against the full retained bytes. Task 3's Screener
definition element is pinned from the A1 capture before the manifest is accepted. Commit it alone.
Dependencies: Task 5; owner actions A1–A2. Estimate: as D7 + ~15 lines. Opus.

### Task 7: D7 Task 6 as amended — Stage 4 end-to-end

Goal: D7 Task 6 unchanged except the screen step replays the derived fixture through
`record_screen_run` and the pair (socket guard on, no transport; a ~20-line test loader builds the
two `VendorExport`s) and asserts both runs' members and review items match the manifest.
Verification: as D7 Task 6, then `test_frozen_manifests.py -k ledger_stage4` (order check live).
Dependencies: Tasks 1, 6 (manifest committed first). Estimate: as D7 + ~35 lines. Opus.

## Verification (gate)

`uv run ruff check src tests/fundamentals`, `ruff format --check`, `uv run mypy --strict src`,
`uv run pytest tests/fundamentals` (pg and retained up); the Task 2 grep empty; `git status` shows
only mapped files; D7's own phase gate still applies. Net estimate: ~+500 src/SQL (Tasks 3–5),
~+385 test, ~60 doc, −~2,500 deleted.

**Risks:** vendor drift and untested row caps → fail-closed refusals, live smoke; terms silent on
scripted use (amendment); `screener-screen`, `coverage screen-run` disappear (owner told).

## Owner actions

- **A1/A2:** save a Screener screen (give its slug) and a Tijori query `d7-stage4`, same filter
  (e.g. `Market Capitalization > 20000`), results including all five; the orchestrator confirms.
  **A3 (optional):** more `config/screens.yaml` entries; the person-named screen is never committed.

## r1 and r2 dispositions

r1 (all fixed): 1, 2, 4, 10 → S5/Task 5 (1 superseded by r2-1); 3 → S2; 5, 7, 9, 11 → S3/Task 3;
6 → S6/Task 7; 8 → S3 (superseded by r2-3). Rulings (a) S1; (b) S5; (c) S6; (d) S4; (e) Task 6.

r2 (all fixed as ruled): 1 → S5 reads: existing one-page readers, verified members
only, four-row table, named gaps. 2 → Task 5 holds: `OPEN_SCREEN_REVIEW` vendor hold, lock
triggers, release on disposition, licence end first, in `0034`. 3 → S3: Screener 2.0 s per
attempt (covers 429 retries), Tijori retries disabled; fake-clock test with a retry (Task 3).

## Sol r3 implementation note

S5's Tijori read needs a small byte-retention seam: `fetch_overview()` returns parsed sections
only. Expose the same fetched bytes for `store_captures` and replay through
`parse_overview_bytes`; no second request, never serialise parsed sections as the capture.

## Revision 2026-10-18: direct formula queries

Owner direction 2026-10-18: no screens are saved at Screener or Tijori; the system runs
owner-authored formulas directly at each vendor, exports and keeps the files. Evidence: the
orchestrator's live probe of 2026-10-18 (raw responses in `scratchpad/raw-probe/`, not committed).
Unchanged: pairing both vendors, captures and row locators, S4 binding, S5 review items, other-vendor
reads and `OPEN_SCREEN_REVIEW`, ≥ 2 s pacing, no-retry Tijori, fail-closed refusals, S6 derived
fixture rule, Tasks 5 and 7. Everything below overrides the named text above.

- **Task 2** (done, `c56ec39`) stays: the legacy `screener-screen` subsystem is gone. Its goal line
  "nothing can request `/screen/raw/?query=`" no longer holds; only `coverage export` requests it,
  through `ScreenerSessionSource.fetch_navigation` (which already redacts `query` in logged URLs).

- **S1.** The amendment's After paragraph is the revised record's
  ([2026-10-18-screen-export](../../../blueprint/amendments/2026-10-18-screen-export.md), digest
  `a5155fbe…42be`), approved by Sol r2 on 2026-10-18 ([review](../reviews/D7-amendment-3-review.md));
  the r3 approval of the old digest does not carry over. Task 1 is redone: new Sol report, approvals block restored.
- **Constraints, requests.** *Screen-query requests* (only these carry a formula): Screener `GET
  /screen/raw/?query=<formula>` (`query` the only parameter; never `sort`, `order`, `page`, `limit`,
  `source_id`) and `POST` to its one export form action (validated exactly, see S3); Tijori `GET
  /api/filter_queries/advanced_search/?financial=<formula>&is_checked=False&whales=False&is_sme=False`.
  *Approved diagnostic reads* (S5, unchanged, after the export commits, one page per pending
  `ABSENT`/`NOT_PROVEN` item, existing readers): the Screener company page (`SCREENER_FINANCIALS`
  reader, as `screener_company_cli.py:150`) and the Tijori overview page (`fetch_overview`); neither
  carries a formula. No other request is made. `/explore/`, `/screens/<id>/<slug>/` and the Tijori
  saved-query listing are no longer requested.
  The `?q=`, `?page=`, `?sort=`, `?limit=` ban stands (robots.txt, 2026-10-18; `?query=` matches
  none of its rules).
- **S2 Config.** `config/screens.yaml`: a list of `{name, screener: <Screener formula>, tijori:
  <Tijori formula>}`, all non-empty, names unique. The formulas are owner-authored text in the repo;
  nothing is matched against a vendor listing, so "absent or appearing twice in the owner's
  listing" is dropped.
- **S3 Definition versioning.** The definition is the configured formula: `screen_text` is
  `screener:<formula>` / `tijori:<formula>` from config, hashed as before (a formula edit makes a
  new `eqos.screens` row). Screener: the raw page is still retained as the definition capture
  (`SCREENER_SCREEN_PAGE`), the vendor's echo — its single `textarea[name=query]` must equal the
  configured formula, else refuse — and its "N results found" must equal the CSV row count.
  *Formula equality everywhere*: collapse runs of whitespace to one space and strip the ends on both
  sides, then compare exactly. *Export action* (r1-2): parse the form action (HTML-unescaped); path
  exactly `/api/export/screen/`, query keys exactly `{query, url_name}`, each once, `query` equal to
  the configured formula, `url_name` equal to the literal `raw_query`, no fragment; else
  refuse. Tijori: one request; `total_results` must equal `len(data)`; the response's `financial_q`
  must be present and equal the configured formula and `alternate_q` null or empty (r1-1), else
  refuse; the run's `definition_capture_ref_id` is its results capture (validated as above; the
  request URL carries the formula). Verified from the retained probe: `financial_q ==
  'Market Capitalization > 20000'`, `alternate_q` null, Screener textarea (unescaped) identical.
  Dropped: the Tijori listing refusal (`next`/`count`), saved-query parameters (`alt_query`,
  `extra_cols`, `columns`, `alternate`, `source`, `query_id`).
- **Task 3.** `export_screener(source, formula)`, `export_tijori(source, formula)`. Refusals: empty
  formula; non-200 or wrong media type (both); not logged in; textarea absent, duplicated or not
  equal to the formula; no or two result counts; export action failing the S3 check (wrong path,
  extra or missing query key, repeated key, `query` ≠ formula, `url_name` ≠ `raw_query`, fragment —
  each fixture keeps the row count equal so only the action check can refuse it); ragged CSV; no
  `ISIN Code`; page count ≠ CSV rows; `total_results` ≠ `len(data)`; Tijori `financial_q` missing or
  ≠ formula, `alternate_q` non-empty (each with `total_results == len(data)`). Fixtures:
  delete `explore.html`, `tijori-listing.json`; `screen.html` becomes the reduced raw-query page.
  Requests: exactly 2 Screener, 1 Tijori; fake-clock pacing test unchanged.
- **Task 4.** No new migration. Every `0034_screen_export.sql` column keeps a meaning: `definition_capture_ref_id`
  (Screener raw page; Tijori = results capture, satisfying the `AUTOMATED_EXPORT` check),
  `screen_members.isin`, `.slug` (Tijori row `slug`, still S4's veto). `record_screen_run` stores one
  Tijori capture, not two.
- **S6 / Task 6.** The source captures come from one `coverage export --screen d7-stage4` run on an
  owner command, `d7-stage4` configured as `Market Capitalization > 20000` at both vendors (probe:
  Screener 380 rows, Tijori 376, all five members in both). Derived rule unchanged; the Screener page
  is reduced to the textarea and page info. Task 3's textarea element is already pinned by the probe.
- **Status of Tasks 3–5 and stale text (r1-4).** Tasks 3–5 are committed (`a8a1d24`: 3–4;
  `116e3f2`: 5) against the saved-screen design and need the direct-query adaptation above in a
  follow-up change, with no new SQL: the committed migrations are `0034_screen_export.sql` (Task 4)
  and `0035_screen_review.sql` (Task 5), immutable. Overrides: the constraints' "`0033`, `0034`" mean
  `0034`/`0035` as committed; Task 5's `0034` (views, dispositions, reads, holds arm) means
  `0035_screen_review.sql`; Task 4's "edited same-slug definition makes a second screen row" test
  becomes "editing the configured formula in config yields a new `eqos.screens` row (new definition
  hash)"; Task 6 depends on Task 5 only (A1–A2 removed).
- **Owner actions.** A1/A2 are dropped (nothing to save). A3 becomes: further `config/screens.yaml`
  formulas; a person-named screen is never committed.
- **Estimate.** Net deletion: ~−40 src (`screen_export.py` loses explore matching, listing and
  saved-query parameters, gains the echo and action checks), ~−30 test, −2 fixtures, no SQL.

### Review r1 responses (Sol r1 on digest `66e770b7…f815`, REVISE)

1. P1 Tijori binding → S3, Task 3: `financial_q` must equal the configured formula
   (whitespace-normalised), `alternate_q` null or empty; refusal cases added; the results capture
   stays the definition capture.
2. P2 export action → S3 exact parse (path, keys `{query, url_name}` once each, `query` = formula,
   `url_name` = `raw_query`, no fragment); equal-row-count refusal fixtures in Task 3; amendment
   Permitted endpoints and `change` text updated.
3. P3 allowlist → constraints split into screen-query requests and the restored S5 diagnostic reads
   (Screener company page, Tijori overview); amendment mirrors it.
4. P3 stale text → explicit overrides: migrations `0034`/`0035` as committed, formula-edit test
   replaces the same-slug test, Task 6 drops A1–A2, Tasks 3–5 marked committed.
