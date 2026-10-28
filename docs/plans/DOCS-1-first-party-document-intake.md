# DOCS-1 — First-party document intake and the daily trigger — Implementation Plan

**Origin:** bead `eqos-msq`; owner targets `docs/goals/2026-10-27-research-report-targets.md`.
Endpoints, counts and hosts: 2026-10-27 APARINDS probe (`scratchpad/vendor-doc-probe/summary.md`).
Builds on `docs/plans/LIVE-RUN-1-prerequisites.md` (`eqos-dna`) without duplicating it.
**Amendment A1** (Tijori primary listing, owner 2026-10-28): approved by gpt-6.1-sol r2 APPROVE
2026-10-28 after r1 REQUEST_CHANGES (13) fixed under orchestrator rulings; r2 notes applied.
**Revision:** r3, fixing Sol r2 `REQUEST_CHANGES` (1–8) by orchestrator ruling: intake state moves
from JSONL events, D8 generation manifests and a tar sidecar into append-only Postgres tables.
**Goal:** for every covered issuer, transcripts, investor presentations, annual reports,
NSE-filed credit-rating documents and results documents are located on NSE (Screener used only
to find links), downloaded from an allowed first-party host, verified, and registered as
retained captures under A05-DECISION-004. Amendment A1 adds Tijori `#companyFilings` as the
primary listing: every document it lists is fetched as a vendor copy under A05-DECISION-005 and
is cited only when an NSE capture is byte-identical (the NSE record is cited) or NSE absence is
proven or it predates 2023-07-01 (the labelled copy is cited). A daily job records every NSE board-meeting and
announcement revision with its observed time, retries pending documents within a bound, and
keeps exactly one bead per released result or concall. Apar is backfilled with 8–12 quarters of
transcripts and presentations and 5 annual reports.
**Out of scope:**
- Extraction of any document: text, guidance claims, management-ledger rows, annual-report notes,
  and the bead's "first-party balance sheet and cash flow" item. Follow-up bead.
- DOCS-1 transcripts as run inputs or `SOURCE_QUOTE` targets: runs keep LIVE-RUN-1's
  manifest-bound route (`evidence transcript`, LIVE-RUN-1 Task 2). Follow-up bead.
- Rating-agency hosts, issuer websites, recordings (OD-1, OD-4, OD-5); Tijori AI reports and Con
  Call Summary (A1); BSE's
  403 (OD-3); unpacking annual-report ZIPs (14 of 17 NSE entries); moving `bse_pdf_source.py`
  onto the shared rules (follow-up bead).
- Edits to the news lane (`news_nse.py`, `news/store.py`) or use of D8 generation manifests;
  edits to `evidence_cli.py`, `capture_intake.py`, `first_party_ingest.py` (LIVE-RUN-1 owns them).
- Automatic update runs or thesis edits of any kind. A trigger creates at most a bead.
**Constraints:**
- Missing inputs fail closed (invariant 10). Point-in-time capture keeps hashes, first-seen times
  and capture failures (invariant 13; register B-09,
  `funda-blueprint-implementation-decision-register-v2.md:59`).
- "PRIVATE / PERSONAL / NON-COMMERCIAL ONLY — no redistribution"
  (`docs/evidence/phase-0a/a-05-rights-decision-004-private-use.md:18`); scope "NSE/BSE public
  listed-company data … announcements" (`:17`). Polite, low volume, no anti-bot evasion.
- Retrieval time is the real fetch instant (`acquiring_fetch` clock, `entity/discovery.py:312-332`);
  registration and first-seen times come from the store clock (`discovery.py:677`). A filing's own
  broadcast time stays a source claim. Nothing is backdated.
- Never commit vendor bytes. Tests read retained bodies through the `retained` marker (fail, never
  skip, on a missing or altered file; `.claude/project/verification.md`). No live network in tests.
- Crisp minimal code (owner 2026-10-14). Budget about 430 lines of Python plus a ~50-line
  migration (r2: ~520 Python, no migration).
- Never open `stage4_holdout.yaml`, `stage4_manifest.yaml`, `data/holdout/` or
  `data/raw/onboarding/`. Never print secrets or vendor readings.

## Findings that shape the design

- **R1. Reused D8 pieces (fetch and register only).** `Request` → `acquiring_fetch(live_transport())`
  → `register_capture` (`entity/discovery.py:284-368, 647-693`; `onboard_cli.py:248-283`; runtime
  pool and `capture_registration` as `shareholding_cli.py:173-183`): exact https host per
  `(source, surface)` (`ORIGINS`, `discovery.py:128-140`), 32 MiB cap (`snapshot_store.py:77`),
  SHA-256, rights from `retention_authority` (`discovery.py:655, 671`). `register_capture`
  publishes the body (`put_capture`, idempotent for an identical record, `snapshot_store.py:145`)
  **before** inserting `capture_refs` in the caller's transaction, and `capture_id` derives from
  retrieval time and blob (`contracts/snapshot.py:382`). A crash between them leaves a published,
  unregistered record under `<snapshot-root>/<source>/<surface>/<request_key>/`, listed by
  `SnapshotStore.list_captures` (`snapshot_store.py:337`).
- **R2. Gaps in the reused pieces.** `ResponseTooLargeError` is a `ValueError`
  (`ingest/http_session.py:40, 83-84`) and `acquiring_fetch` catches only `TimeoutError`/`OSError`,
  so an oversize annual report crashes. `live_transport` sends BSE headers only for
  `BSE_PEER_SEARCH` (`onboard_cli.py:267-268`).
- **R3. NSE gives everything the trigger needs, first-party.** The `nse` wrapper's
  `corporate-announcements`, `corporate-board-meetings` and `annual-reports` endpoints
  (`.venv/…/nse/NSE.py:609-662, 664-717, 719-746`) sit under `NSE_API`, which `live_transport`
  routes to the primed session (`onboard_cli.py:264-265`). Probe: 6 board meetings (one future
  `Financial Results` meeting on 29-Oct-2026), 41 announcements (every attachment on
  `nsearchives.nseindia.com`), 17 annual reports (3 `.pdf`, 14 `.zip`; the 2026 file is 16.15 MB).
- **R4. Screener `#documents` (retained page, sha256 `9b82e322…`)**: `.annual-reports` (15 `li/a`:
  14 `www.bseindia.com`, 1 `archives.nseindia.com`); `.credit-ratings` (6: 4 `www.careratings.com`,
  2 `www.icra.in`); `.concalls` (63 `li`: month label in `div[1]`, then chips; linked =
  `a.button-chip` text `Transcript`/`PPT`/`REC`, absent = `div.button-chip`; Transcript 54 + 9
  absent, PPT 50 + 13, REC 13). "AI Summary" is always a `button`. Every in-window (Oct 2023–Jul
  2026) transcript and PPT link is `www.bseindia.com/stockinfo/AnnPdfOpen.aspx?Pname=<name>.pdf`;
  `apar.com` hosts only recordings. Identity: `read_identity` (`ingest/screener_session_page.py:102-118`),
  checked as D8 does (`shareholding_filing.py:103-106`).
- **R5. Transcript-vs-notice rule (retained announcements, sha256 `356a548d…`).** All four rows in
  category `desc == "Analysts/Institutional Investor Meet/Con. Call Updates"` carry `attchmntText`
  "<Issuer> has informed the Exchange about <subject>": `Transcript` ×1 (31-Jul-2026),
  `Schedule of meet` ×2, `Link of Recording` ×1. **Rule:** in that category, normalised text with
  `about transcript` → TRANSCRIPT; `about schedule of meet` → CONCALL_SCHEDULE; `about link of
  recording` → CONCALL_RECORDING; anything else → **CONCALL_UNRESOLVED** (never downloaded,
  surfaced as a candidate bead). Outside it: `desc == "Investor Presentation"` → PRESENTATION;
  `desc` starting `Credit Rating` → CREDIT_RATING; `desc == "Outcome of Board Meeting"` with text
  containing `financial results` → RESULTS; anything else → OTHER. Evidence is weak (one positive
  in 120 days), so a miss must stay visible, never become a wrong document.
- **R6. Covered issuers** are entities whose latest `WATCHLIST` decision is `ADD`
  (`eqos.watchlisted`, `migrations/0026_watchlist.sql:17-21`; CONTEXT "Watchlist (covered)";
  `config/watchlist.yaml` is *not* coverage). Runtime has SELECT on `eqos.decisions`
  (`migrations/0012…sql:481`). Symbol and ISIN from `latest_slice` (as `shareholding_cli._entity`
  `:312-322`). Live has no `ADD` until LIVE-RUN-1 step C4.
- **R7. Probe rows carry relative-time keys** (`difference` in announcements; `diff`, `sysTime` in
  board meetings — inference from names) that would make every run look like a revision.
- **R8. Backup boundary.** `db backup` dumps every `eqos` table (`pg/backup.py:78-81, 234`) and every
  registered capture body. New tables are therefore covered with no sidecar. An unregistered
  crash remnant in the snapshot store is not in the backup, and need not be.
- **R9. Rehearsal check.** `db check-live` refuses test databases (`api/db_cli.py:137`);
  `scratchpad/research1-a1/check_rehearsal.py` runs it with a hard-coded `TARGET`.
- **R10. Migration pattern.** Append-only triggers as `migrations/0040_review_telemetry.sql:58-76`;
  runtime SELECT/INSERT as `0012…sql:481`. Next free number `0043` (LIVE-RUN-1 adds none, `:22`).

## Design (smallest that meets the goal)

1. **State lives in three append-only tables** (migration 0043, below). A listing fetch, its
   registered body and the parsed observation revisions commit in one transaction; a document
   attempt and its registration commit in one transaction. A crash before either commit changes
   nothing in the DB, so the next run repeats that step. `db backup`/restore covers all of it.
2. **Everything is derived by query** (no queue, cursor or manifest): latest revision per
   occurrence, pending documents, listing coverage, beads to reconcile.
3. **Types.** `DocumentKind(StrEnum)` in `contracts/source_catalog.py` builds the document
   surfaces; ingestion imports it (existing direction, `entity/discovery.py:48`). NSE/Screener
   readers are pure functions; the DB access is one small module; the CLI orchestrates.
4. **Surfaces** (all `SourceRole.DIAGNOSTIC`, `_EXCHANGE_RIGHTS`): `("nse",
   ANNOUNCEMENTS_LISTING | BOARD_MEETINGS_LISTING | ANNUAL_REPORTS_LISTING)` on `www.nseindia.com`;
   `("nse-documents", NSE_<KIND>)` on `nsearchives.nseindia.com`; `("bse-documents", BSE_<KIND>)` on
   `www.bseindia.com`. The Screener page reuses `SCREENER_PAGE` (A05-005). No document can
   reconcile; no interpretation runs on any capture.

### Migration `0043_document_intake.sql` (outline, ~50 lines)

```sql
CREATE TABLE eqos.document_listings (          -- one row per listing fetch, OK or not
    id bigserial PRIMARY KEY,
    entity_id bigint NOT NULL,
    symbol text NOT NULL,
    surface text NOT NULL,                      -- ANNOUNCEMENTS_LISTING | BOARD_MEETINGS_LISTING
                                                -- | ANNUAL_REPORTS_LISTING | SCREENER_PAGE
    span_from date, span_to date,               -- NULL for unwindowed listings
    retrieved_at timestamptz NOT NULL,          -- real fetch instant
    outcome text NOT NULL,                      -- OK | HTTP_xxx | TIMEOUT | TRANSPORT_ERROR | ...
    capture_ref_id bigint REFERENCES eqos.capture_refs (id),
    recorded_at timestamptz NOT NULL DEFAULT eqos.store_now(),
    CHECK ((outcome = 'OK') = (capture_ref_id IS NOT NULL)));
CREATE TABLE eqos.document_observations (      -- one row per revision of an occurrence
    id bigserial PRIMARY KEY,
    listing_id bigint NOT NULL REFERENCES eqos.document_listings (id),
    occurrence_key text NOT NULL,
    payload_sha256 text NOT NULL,
    payload jsonb NOT NULL,                     -- stable_row(row): bm_date, attachment URL, ...
    observed_at timestamptz NOT NULL);          -- = the listing's retrieved_at
CREATE INDEX ON eqos.document_observations (occurrence_key, observed_at DESC, id DESC);
CREATE TABLE eqos.document_attempts (          -- one row per fetch attempt per (revision, URL)
    id bigserial PRIMARY KEY,
    observation_id bigint NOT NULL REFERENCES eqos.document_observations (id),
    url text NOT NULL,
    attempted_at timestamptz NOT NULL,          -- real fetch instant
    outcome text NOT NULL,                      -- OK | WRONG_TYPE | TOO_LARGE | HTTP_xxx | TIMEOUT | ...
    body_sha256 text,                           -- when a body was received (OK, WRONG_TYPE)
    capture_ref_id bigint REFERENCES eqos.capture_refs (id),
    recorded_at timestamptz NOT NULL DEFAULT eqos.store_now(),
    CHECK ((outcome = 'OK') = (capture_ref_id IS NOT NULL)));
CREATE INDEX ON eqos.document_attempts (observation_id, url);
-- DO block over the three names, as 0040:58-74: reject_row_mutation, reject_truncate.
GRANT SELECT, INSERT ON eqos.document_listings, eqos.document_observations,
    eqos.document_attempts TO eqos_runtime;
GRANT USAGE ON SEQUENCE <the three id sequences> TO eqos_runtime;
GRANT SELECT ON <the three> TO eqos_panel, eqos_owner, eqos_purge;
```

Coverage is a third table, not derived from observations: an OK span with zero rows must count
as covered, and a failed fetch must be kept (invariant 13). Observations do not repeat the span.

## Open decisions

| # | Decision | Recommendation |
|---|---|---|
| OD-1 | **Credit-rating PDFs on CARE/ICRA.** A05-004 covers NSE/BSE only (`a-05-…-004:17`). | **Use only NSE-filed rating announcements; add no rights record now.** Screener's 6 agency links are observed and never fetched. Task 5 records for each NSE rating document whether it is a **rationale** or only an **intimation**; no rationale → open the rights-research bead (agency terms unread; no claim made about them). |
| OD-2 | **Tijori-hosted copies.** | **Superseded by Amendment A1 (owner, 2026-10-28).** Tijori `#companyFilings` is the primary listing and every listed document is fetched from Tijori. A byte-identical NSE capture is the cited record (`CORROBORATED`). Where NSE absence is proven, or the filing predates 2023-07-01, the Tijori copy is cited as a labelled vendor copy (`VENDOR_COPY`) under A05-005, which allows personal non-commercial storing (`docs/research/vendor-terms-screener-tijori-2026-10.md:61, 69`). Every other outcome is retained but uncitable. A Tijori copy is never treated as an exchange original. |
| OD-3 | **BSE 403.** | **Separate bead (systematic-debugging).** NSE is primary. BSE requests record `HTTP_403` and are never worked around. Also affects `news_bse` and `goal_runner`'s live PDF path. |
| OD-4 | **Recordings.** | **Out of scope.** Likely over 32 MiB, no transcription path. The NSE "Link of Recording" row is still an observation. |
| OD-5 | **Issuer-site host.** | **Exclude from v1.** A05-004 does not name issuer websites; every in-window Apar transcript and PPT is on BSE (R4). |

## Tasks

### Task 1: Surfaces, migration, fetch-and-register, intake state

Goal: one document attempt fetches a link on its pinned host, refuses a wrong type, and in one
transaction registers the body and records the attempt; listings and their observation revisions
commit together; an unchanged repeat of the latest revision is a no-op.

Files:
- Create: `migrations/0043_document_intake.sql`, `src/fundamentals/pg/document_intake.py`
- Modify: `src/fundamentals/contracts/source_catalog.py` (`DocumentKind`; descriptors `:180-197`,
  surfaces `:271-311`), `src/fundamentals/entity/discovery.py` (`ORIGINS` `:128-140`, outcome
  constant `:116-120`, `acquiring_fetch` `:316-330`), `src/fundamentals/api/onboard_cli.py`
  (`:267-268`)
- Test: `tests/fundamentals/test_document_intake.py` (new, `pg`)

Interfaces:
- `DocumentKind(StrEnum)`: `TRANSCRIPT`, `PRESENTATION`, `ANNUAL_REPORT`, `CREDIT_RATING`, `RESULTS`.
- Outcome constants `TOO_LARGE` (in `discovery.py`), `WRONG_TYPE`; `TERMINAL = {WRONG_TYPE,
  TOO_LARGE, HTTP_404, HTTP_410}`; every other non-`OK` outcome is retryable.
- In `pg/document_intake.py` (the only SQL; class `DocumentIntake(conn)`):
  - `record_listing(listing, observations) -> int`: inserts the listing row and, for each parsed
    `(occurrence_key, payload)`, a revision **unless its `payload_sha256` equals the latest
    revision of that occurrence** (ordered `observed_at DESC, id DESC`). A→B→A gives three rows.
    Returns rows inserted.
  - `latest(entity_id, surface) -> list[Observation]`; `attempts(observation_id, url) -> list[Attempt]`;
    `record_attempt(...)`; `coverage(entity_id, surface) -> date | None`.

Approach:
- One comprehension over `DocumentKind` × two hosts adds the document surfaces; exact hosts go in
  `ORIGINS`. `acquiring_fetch` catches `ResponseTooLargeError` as `TOO_LARGE`, no body.
  `live_transport` sends `_BSE_HEADERS` for any `www.bseindia.com` request (the honest browser
  headers `bse_pdf_source.py:23-31` documents).
- `refusal(kind, body)`: `%PDF-` required; `PK\x03\x04` also allowed for `ANNUAL_REPORT`.
- Every OK body goes through `register_capture` (its own `capture_refs` row on its own request
  route; identical bytes share one content-addressed blob). No "already registered" lookup is
  needed: idempotency is per attempt, not per blob.
- About 120 lines Python (catalog ~25, discovery/onboard ~10, intake module ~85) + ~50 SQL.

Verification (slice `DOCS-1-T1`; every task follows this form): `scripts/verify.sh red DOCS-1-T1
tests/fundamentals/test_document_intake.py` records each new test failing first, then
`scripts/verify.sh gate DOCS-1-T1`; `test_bse_pdf.py`, `test_shareholding_filing.py` and the
migration tests stay green.

Test seams (`pg`, `eqos_test_*` DB, runtime role): UPDATE/DELETE on each table raise. **Finding 6:**
payloads A, B, A for one occurrence → three rows, `latest` = the third; a fourth A → no row. A PDF
and an `ANNUAL_REPORT` ZIP register with A05-004 `authority_refs` and the attempt's `attempted_at`;
HTML records `WRONG_TYPE` with `body_sha256`, no capture; `HTTP_403`, `TOO_LARGE` (a send raising
`ResponseTooLargeError`) record no capture.

Dependencies: None.

Risks: annual reports over 32 MiB become `TOO_LARGE` gaps (cap not raised); `live_transport`
refuses redirects, so a redirected BSE page is `HTTP_30x`, fail closed.

### Task 2: Screener `#documents` reader

Goal: given an identity-checked Screener page, return every annual report, credit rating,
transcript and PPT link as a `DocumentLink`, plus absent-chip counts. AI summaries and
Screener-hosted URLs never appear; a page for another company yields nothing.

Files: Create `src/fundamentals/ingest/screener_documents.py`; Test
`tests/fundamentals/test_screener_documents.py` (new).

Interfaces:
- `DocumentLink(BaseModel, frozen)` (in `ingest/first_party_documents.py`, Task 3): `kind`,
  `period: str` (source label), `url`, `host`, `found_on`, `filed_at: datetime | None`.
- `read_screener_documents(page: bytes, *, expected_company_id: int) -> ScreenerDocuments`
  (`links`, `absent: Mapping[DocumentKind, int]`, `recordings: int`). Concall `period` = month
  label; annual-report `period` = trailing year of the anchor text; credit-rating `period` = anchor
  text. Raises `IdentityAmbiguousError` or `ValueError` on identity mismatch.

Approach: XPath under `//section[@id="documents"]`: `li/a` in `.annual-reports` and
`.credit-ratings`; `a.button-chip` with text `Transcript`/`PPT` in `.concalls li`; absent chips
from `div.button-chip`. `button` elements are never read. Links on any host are kept (the fetch
rule decides); non-http(s) dropped. About 70 lines.

Verification: slice `DOCS-1-T2`.

Test seams (`retained`): the orchestrator copies `company_APARINDS_consolidated.html` to the
gitignored `data/raw/watchlist/aparinds/docs-probe-2026-10-27/`, pinned by full SHA-256 (prefix
`9b82e322`). Literal counts from R4: 15 annual reports (14 BSE, 1 NSE); 6 credit ratings (4 CARE,
2 ICRA); 54 transcripts and 50 PPTs linked, absent 9 and 13, 13 recordings; no `www.screener.in`
host and no `/concalls/summary/` URL; `expected_company_id=212` raises.

Dependencies: Task 3 (`DocumentLink`). Risks: low; a layout change gives zero links, which Task 5
exposes.

### Task 3: NSE readers and the fetch rule

Goal: announcements classify by R5; each listing row becomes `(occurrence_key, stable payload)`;
a board meeting's date is readable from its payload; the annual-report listing gives one link per
entry; a link maps to a pinned request or to nothing.

Files: Create `src/fundamentals/ingest/first_party_documents.py`; Test
`tests/fundamentals/test_nse_documents.py` (new).

Interfaces:
- `AnnouncementClass(StrEnum)`: the five document kinds' announcement classes plus
  `CONCALL_SCHEDULE`, `CONCALL_RECORDING`, `CONCALL_UNRESOLVED`, `OTHER`.
- `classify_announcement(row)`; `announcement_link(row) -> DocumentLink | None` (document classes
  with an `nsearchives.nseindia.com` attachment only).
- `stable_row(row) -> dict`: the row without `VOLATILE_KEYS = ("difference", "diff", "sysTime")`.
- `listing_rows(surface, body) -> list[tuple[str, dict]]`: occurrence keys — announcements
  `seq_id` (a row without one is refused and printed, fail closed); board meetings
  `symbol|bm_purpose|bm_timestamp`; annual reports `fileName`; Screener links their URL.
- `meeting_date(payload) -> date | None` (from `bm_date`).
- `annual_report_links(body)`; `nse_listing_url(surface, symbol, from_date, to_date)`
  (`dd-mm-YYYY`, `NSE.py:639-660, 694-715`; annual reports `index` + `symbol`, `:746`).
- `document_request(link) -> Request | None`: rewrites `AnnPdfOpen.aspx?Pname=X` to BSE
  `AttachHis/X`; `("nse-documents", f"NSE_{kind}")` / `("bse-documents", f"BSE_{kind}")` by exact
  host; `None` for any other host.

Approach: pure functions over parsed JSON, a constant for every literal. An amendment either keeps
the occurrence key (a new revision) or changes it (a new occurrence); neither is dropped. Whether
NSE edits in place or re-broadcasts is unknown (inference); both are covered. About 110 lines.

Verification: slice `DOCS-1-T3`; `test_news.py` stays green (untouched).

Test seams (`retained`): the three probe JSONs are copied beside the Screener page and pinned
(prefixes `356a548d`, `c39e71c6`, `3f0cc030`). Assert:
- **Announcements (41):** every row has `seq_id`; exactly 1 TRANSCRIPT (31-Jul-2026); 2
  CONCALL_SCHEDULE, 1 CONCALL_RECORDING, 1 PRESENTATION, 1 CREDIT_RATING, 0 CONCALL_UNRESOLVED;
  exactly 1 RESULTS (24-Jul-2026), the 30-Jun fund-raising outcome `OTHER`; every link host
  `nsearchives.nseindia.com`.
- **Board meetings (6):** exactly one `Financial Results` with `meeting_date` 2026-10-29;
  re-parsing gives identical keys and payload hashes; changing only a `VOLATILE_KEYS` field leaves
  the hash unchanged.
- **Unresolved:** a concall-category row "about Concall Transcript Submission" is
  `CONCALL_UNRESOLVED` with no link; the same text elsewhere is `OTHER`.
- **Annual reports:** 17 links (3 `.pdf`, 14 `.zip`); latest five `toYr` are 2022–2026.
- **Fetch rule:** `AnnPdfOpen` maps to AttachHis; `None` for `www.careratings.com`, `apar.com`,
  `files.tijorifinance.com`.

Dependencies: Task 1 (`DocumentKind`).

Risks:
- **Medium: the transcript rule rests on one positive row (R5).** Unresolved candidates and Task 5's
  per-quarter check are the safeguards; a rule change needs a new retained fixture.
- **Medium: `AnnPdfOpen` → `AttachHis` is inference** (no BSE document downloaded). Task 5 checks.
- **`VOLATILE_KEYS` is inferred from names.** Task 5 step 5 checks two runs with no new filings
  insert zero revisions; a churning field is added by ruling.

### Task 4: `documents backfill` and the reconciling `documents daily`

Goal: one idempotent pass per issuer that records listings and revisions, completes pending
documents within a bound, recovers a saved-but-unregistered body without the network, and
reconciles beads from all retained observations.

Files: Create `src/fundamentals/api/documents_cli.py`; Modify `src/fundamentals/api/cli.py`
(`:667`), `src/fundamentals/api/cli_parser.py` (`:227`); Test
`tests/fundamentals/test_documents_daily.py` (new, `pg`, `retained`).

Interfaces:
- `documents backfill --symbol S --from D --to D --snapshot-root P [--annual-reports N]
  [--screener --config-root config]` (the issuer must be covered, R6).
- `documents daily --snapshot-root P --lock-root L`.
- `run_documents(args, *, send: Send, clock, bd: BdRunner) -> int` (test seam).
  `BdRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]`; live runner
  `subprocess.run(["bd", …], timeout=30, capture_output=True, text=True)`.
- Exit `SUCCESS`; `INCOMPLETE` (any `GAP`, `UNCOVERED`, `UNCOVERED_ISSUER` or refused row);
  `FAILURE` (lock held, ledger/registry read failed, bd call failed).

Approach — one pass, in order (requests spaced 3 s, `shareholding_cli.PAUSE_SECONDS`):
0. **Serialise.** Non-blocking `fcntl.flock` on `<lock-root>/documents.lock`; held → `FAILURE`,
   no requests. bd calls happen inside the lock, one at a time.
1. **Coverage.** Covered = `WATCHLIST` entities with `eqos.watchlisted` true, on the runtime role;
   symbol and ISIN from `latest_slice(today)`. No unique NSE symbol → `UNCOVERED_ISSUER`, skipped.
2. **Windows.** Per issuer and windowed listing, `covered_to` = end of the unbroken union, from the
   earliest, of OK `document_listings` spans, **each capped at the date (IST) of its
   `retrieved_at`** — coverage never runs past the day a listing was read (finding 2).
   Announcements: `covered_to − 3` to today. Board meetings: `covered_to − 3` to **today + 90**,
   so the future window is re-read every day while the watermark stays at today. No coverage →
   from today − 3 (`backfill`: `--from`). Spans ≤ 31 days, ≤ 12 per run, oldest first; a failed
   span is recorded with its outcome and stops that listing's advance; it and later spans print
   `UNCOVERED\t<SYMBOL>\t<surface>\t<from>\t<to>` and are retried from the same `covered_to`.
3. **Listings → revisions.** Each fetched listing commits in **one transaction**: the body via
   `register_capture`, the `document_listings` row, and `record_listing`'s revisions. Rows whose
   ISIN differs from the master's EQ ISIN are refused and printed. `backfill` also reads the
   annual-report listing (latest N `toYr`) and, with `--screener`, the identity-checked page.
   Board-meeting attachments are notices, never fetched.
4. **Pending documents.** For each issuer's latest revision with a link that `document_request`
   maps, *for that (revision, URL)*: complete if any attempt is `OK`; terminal if any attempt is in
   `TERMINAL`; exhausted at 5 retryable attempts. Otherwise pending (findings 4, 5: a new revision,
   even with the same URL as an earlier `HTTP_404`, starts with no attempts). For each pending one:
   a. **Recover first (finding 1).** `store.list_captures(source, surface, sha256(request.key))`;
      the newest record with **no `capture_refs` row** and `retrieved_at ≥` the revision's
      `observed_at` is a crash remnant: its body (verified by the store) is registered with
      `register_capture` at its original `retrieved_at`, and an `OK` attempt is recorded. No request.
   b. Else fetch; `refusal` → `WRONG_TYPE`; in **one transaction** `register_capture` (OK only)
      and `record_attempt` (outcome, real `attempted_at`, `body_sha256`, `capture_ref_id`).
   Terminal or exhausted → `GAP\t<SYMBOL>\t<kind>\t<occurrence_key>\t<outcome>` every run.
5. **Reconcile beads** from *all* latest revisions in the DB: RESULTS/TRANSCRIPT/PRESENTATION →
   ref `docs-trigger:<entity_id>:<occurrence_key>` (label `update-run`; revisions add none);
   CONCALL_UNRESOLVED → `docs-candidate:<entity_id>:<occurrence_key>` (label `doc-classification`;
   description names date and filename; classifying is a human ruling). One lookup per run:
   `bd list --all --external-contains docs- --limit 0 --json --brief`; non-zero exit, timeout or
   unparsable JSON → `BD_LOOKUP_FAILED`, nothing created, `FAILURE`; an empty list is valid. Each
   missing ref gets `bd create "<title>" -t task -l <label> --external-ref <ref> -d "<desc>"`;
   existing beads, open or closed, are left alone; a create failure stops with `FAILURE`.
   Lines: `TRIGGER\t<SYMBOL>\t<kind>\t<date>\t<key>\t<created|exists>`, `CANDIDATE\t…`.
6. **Scheduled meetings.** Each latest Financial Results meeting dated today or later prints
   `RESULTS_SCHEDULED\t<SYMBOL>\t<meeting date>\t<key>`; no bead.

About 130 lines.

Verification: slice `DOCS-1-T4`.

Test seams: a fake `send` serves the retained listings by URL, synthetic PDF bytes, scripted
failures and a stub master CSV, and records calls; a fake `clock` advances days; a fake `bd` keeps
an in-memory list, fails on demand, records calls. APARINDS is `ADD`ed via test helpers on the
CLI's role. Cases:
- **First run / second run:** one `RESULTS_SCHEDULED` (2026-10-29); one bead per RESULTS,
  TRANSCRIPT, PRESENTATION; documents registered. Second identical run: no new revision, attempt,
  capture or bead; no document request; every `TRIGGER` says `exists`.
- **Board meetings (finding 2):** day D run; on D+1 the listing adds a meeting for D+7 → one new
  revision, `RESULTS_SCHEDULED` D+7; on D+2 its `bm_date` changes to D+8 → a second revision,
  latest shows D+8. After each run `covered_to` for board meetings is that run's date.
- **Identical bytes (finding 4):** the PRESENTATION and RESULTS attachments are byte-identical under
  two URLs → two `OK` attempts, two `capture_refs` rows, one blob (`blob_inventory`); the next run
  requests neither.
- **Same URL, new revision (finding 5):** a transcript URL returns `HTTP_404` (terminal, `GAP`);
  a new revision of that occurrence with the same URL is fetched once and registers; the old
  revision's 404 stays recorded.
- **Crash before observation commit (finding 1a):** `record_listing` raises after the listing body
  is published → no `document_listings`/observation rows, `covered_to` unchanged; the restart
  re-requests that span and records it.
- **Crash after body saved, before registration (finding 1b):** `record_attempt` raises after
  `register_capture`'s publish → no attempt, no `capture_refs` row, the record is on its route.
  Restart with `send` raising `OSError` for every request: listings record `TRANSPORT_ERROR` and
  print `UNCOVERED`; the document is registered from the retained record with its original
  `retrieved_at`, an `OK` attempt is recorded, and **no document request is sent**.
- **Retry and outage:** timeouts on runs 1–2, registered on run 3 (three attempts); five timeouts
  → `GAP` on run 6, no sixth request. Coverage ends at D; at D+10 the middle span fails → it and
  later spans `UNCOVERED`, closed next run; at D+400, 12 spans then `UNCOVERED`.
- **bd:** a closed bead holding a ref → no create; `bd list` exits 1 → no create, `FAILURE`, next
  good run creates; `bd create` raises → `FAILURE`, revisions retained, restart creates exactly
  the missing beads; a concurrent second run exits `FAILURE` and sends nothing.
- **Unresolved / coverage / backfill:** an unfamiliar concall row gives one `docs-candidate` bead
  and no fetch; an `ADD`ed issuer absent from `config/watchlist.yaml` is processed, one with no NSE
  symbol prints `UNCOVERED_ISSUER`, no `ADD` sends nothing; a wrong-company Screener page prints
  `refused screener identity`; a CARE link is observed, never sent.

Dependencies: Tasks 1–3.

Risks: bd runs from product code only as the two commands above, with a timeout and no shell.
Recovery (4a) relies on the local snapshot store; a remnant lost with the disk is refetched.

### Task 5: Apar backfill and activation (orchestrator, operational, no code)

**Acceptance** counts registered first-party captures only, per kind. A kind below target is
reported **`NOT MET — accepted with blocked gaps (n)`**, never `MET`, and only when every missing
item is a named blocked gap; any unnamed shortfall fails.

| Kind | Target | Allowed blocked-gap reasons |
|---|---|---|
| Transcripts | ≥ 8 of the 12 quarters Oct 2023–Jul 2026 | no exchange copy; BSE `HTTP_403` (OD-3); `TOO_LARGE` |
| Presentations | ≥ 8 of the same quarters | same |
| Annual reports | 5 (FY2022–FY2026) | `TOO_LARGE`; ZIP with no reachable BSE PDF |
| Credit ratings | every NSE-filed rating row in the window | none (NSE host) |
| Results | every quarter's RESULTS row in the window | none (NSE host) |

**Ordering with `eqos-dna`.** Tasks 1–4 code may land while LIVE-RUN-1 runs (no shared files).
**Neither the migration nor any DOCS-1 write reaches live until LIVE-RUN-1 Task 5 step 6 (Close)
is done, including its post-run backup** (LIVE-RUN-1 needs rehearsal-equal deltas and "0
transcript … captures"). The four LIVE-RUN-1 quarters register again on `(nse-documents,
NSE_TRANSCRIPT)`: harmless, and a hash cross-check.

Steps (output teed to `scratchpad/docs-1/logs/`, mode 700):
0. **Preflight (read-only).** `db check-live` → 0; counts; LIVE-RUN-1 step 6 recorded in `eqos-dna`;
   APARINDS `ADD`ed (LIVE-RUN-1 C4).
1. **Rehearsal (network).** `db backup`; restore into `eqos_test_docs1_*`; apply 0043 there; run
   `documents backfill --symbol APARINDS --from 2023-07-01 --to 2026-10-27 --annual-reports 5
   --screener --snapshot-root <scratch>` against it. **Pass:** every in-scope document is
   `registered`, or a known blocked outcome (BSE `HTTP_403`, `TOO_LARGE`) recorded as an attempt
   and not registered; a second run sends no document request for completed or terminal items and
   leaves known failures refused. Check with `scratchpad/docs-1/check_rehearsal.py` (copy of R9's
   helper, `TARGET` = that DB). Drop the DB.
2. **Live.** Apply 0043 (`db migrate`); same backfill against live with
   `--snapshot-root data/raw/snapshots/v1`; check-live → 0. Per-kind outcome counts must equal the
   rehearsal's; a difference stops the run for inspection (remote change is possible; a re-run is
   idempotent and retries only pending items).
3. **Acceptance report (read-only scratchpad helper).** The table with achieved counts and named
   gaps, then one line per Screener concall row Oct 2023–Jul 2026: kinds registered, or `GAP` with
   its reason. Screener shows a transcript but no exchange copy registered → **stop**: read that
   quarter's NSE rows and either extend R5 (new fixture, back to Task 3) or record a blocked gap.
   Print whether each LIVE-RUN-1 transcript SHA-256 equals its `retrieval-manifest-v2.json` pin
   (mismatch → finding for `eqos-dna`). **OD-1:** record `rationale` or `intimation` per
   CREDIT_RATING capture id in `eqos-msq` notes, quoting nothing.
4. **Backup and recovery drill.** `db backup`; restore into a fresh `eqos_test_docs1r_*` DB; run the
   rehearsal check; confirm the three tables' row counts and `retrieved_at`/`attempted_at`/
   `observed_at` equal live's, the `HTTP_403`/`TOO_LARGE` attempts are present, and every OK
   attempt's capture reads back. Drop the DB. Record the backup id in `eqos-msq` notes.
5. **Activate** (needs steps 2–4). T3 `schedule_task`, bound to the orchestrator thread:
   `{"type":"fixed_time","timeOfDay":"21:30","weekdays":[0,1,2,3,4,5,6]}` — **daily, Sunday
   included, 21:30 Asia/Kolkata** (orchestrator ruling). Verify with `list_scheduled_tasks` that the
   cadence is every day and the next run is the next 21:30 Asia/Kolkata (correct, re-check and
   record if zone or day numbering differs). Prompt: (1) `uv run fundamentals documents daily
   --snapshot-root data/raw/snapshots/v1 --lock-root data/raw/documents`, then `db check-live` → 0;
   (2) anything inserted → `db backup`; (3) report exit code, counts and every `GAP`, `UNCOVERED*`,
   `CANDIDATE … created`, `BD_LOOKUP_FAILED` line; two `FAILURE`s in a row → debugging bead. First
   two runs: confirm no new filings means zero new revisions (Task 3 risk).
6. **Close.** Record acceptance table, gaps and backup id in `eqos-msq` notes. File follow-ups:
   extraction; run admission for DOCS-1 transcripts; BSE 403 (OD-3); `bse_pdf_source` onto the
   shared rules; annual reports in the daily pass.

Failure branch: stop at the first unexpected result. Every pass is idempotent and may be re-run
after a fix.

Risks: every live write is permanent (append-only). The rehearsal and live run each hit the
network (~100 requests at 3 s); results can differ between them, which step 2 surfaces. Quarter
matching in step 3 is by eye, since it runs once.

## Review and self-check

Sol reviews this plan, then once at phase end over Tasks 1–4 (`04-agent-stack.md`).
- **Sol r2 → r3:** 1 → Design 1, Task 4 steps 3, 4a and the two crash tests; 2 → Task 4 step 2
  and the board-meeting test; 3 → no D8 manifests (Out of scope, R1); 4 → Task 4 step 4 and the
  identical-bytes test; 5 → Task 4 step 4 and the same-URL test; 6 → `record_listing` (latest-only
  no-op) and the A→B→A test; 7, 8 → R8, no tar sidecar, Task 5 step 4. Sol notes → Task 5 step 1
  (rehearsal expectation) and the acceptance wording (`NOT MET — accepted with blocked gaps`).
- **Cut by the DB move:** the `register` subcommand, `acquire`/generations, `find_request`,
  `listing_window`, `keep_revisions`, `latest()` on the news store, `raw_subcategory` reuse, the
  events root, the tar sidecar and its drill.
- **Kept** as the ruling lists (bead reconciliation, bd `--all`, fail-closed lookup, flock,
  ledger coverage, CONCALL_UNRESOLVED, schedule, rights, OD-1–5, LIVE-RUN-1 ordering).
- **Inferences still open, each checked by a named test or step:** `AnnPdfOpen` → `AttachHis`;
  `VOLATILE_KEYS`; NSE's amendment behaviour; whether the board-meeting endpoint filters by
  meeting date (the D+90 window assumes so); T3 day numbering and timezone.

## Review record and orchestrator rulings (2026-10-27)

gpt-6.1-sol: r1 REQUEST_CHANGES (13), r2 REQUEST_CHANGES (8), r3 REQUEST_CHANGES (3 P2). In r2 the
orchestrator ruled that intake state moves to Postgres. r3 found all eight r2 findings fixed. The
loop did not converge in 3 rounds, so the orchestrator rules on the r3 residuals (agent-stack rule
5). These amendments bind and override any conflicting text above:

1. **Migration sequencing.** DOCS-1 Tasks 1–4 start only after LIVE-RUN-1 Close, including its
   backup. Migration 0043 therefore never sits in a checkout that LIVE-RUN-1's checks run from.
   The live preflight follows RESEARCH-1 A1's pattern:
   1. `db check-live --migrations-dir <copy of migrations/ minus 0043>` passes.
   2. Run `db migrate`.
   3. `db check-live` with the default dir passes.
2. **Failed initial spans.** The discovery start is the earliest start of any recorded failed span
   that a later successful span has not covered. Only when there is none does it fall back to the
   rule above (last unbroken success, or `today − 3`). Test: the first run fails on D, the next runs
   on D+1 and D+2, and the original D−3..D interval is retried until covered.
3. **Backfill passes.** The rehearsal and live backfill repeat bounded catch-up passes (≤12 spans of
   ≤31 days per listing per pass) until no listing reports `UNCOVERED`. Only then do the per-kind
   completeness check and the unchanged-repeat check run. A 1,215-day interval needs at least four
   passes per windowed listing. Requests are estimated from the number of passes; live compares
   outcomes with the rehearsal only after its own catch-up completes.
- Notes: "no new capture" means **no new document capture**, because repeated listing fetches
  intentionally create listing captures. The board-meeting endpoint's filtering field is verified
  during the rehearsal before the daily window is trusted.

The plan is approved on these rulings. The phase-end Sol review covers the implementation.

## Amendment A1 — Tijori primary listing (owner, 2026-10-28; r1 fixes Sol A1-r1 1–13)

**Ruling (binding; overrides conflicting text above, including OD-2).** BSE returns 403, and
Tijori has copies back to 2010. Tijori `#companyFilings` is therefore the **primary** listing,
and every document it lists is fetched from `files.tijorifinance.com` and retained under
A05-DECISION-005 (`docs/evidence/phase-0a/a-05-rights-decision-005-subscriber-scraping.md`,
scope "documents"). A Tijori copy is never an exchange original, and only two outcomes are
**citable**:
- `CORROBORATED`: an NSE capture, or a PDF member of an NSE ZIP, has the Tijori copy's SHA-256.
  The cited record is that NSE capture (and member).
- `VENDOR_COPY`: NSE absence is proven (`nse-none`, below), or the document predates
  2023-07-01 with no NSE candidate (`nse-unlisted`, the owner/orchestrator historical exception). The cited record is
  the Tijori copy, labelled vendor copy.

Every other outcome (`MISMATCH`, `AMBIGUOUS`, `NSE_PENDING`, `NSE_UNAVAILABLE`, `UNDATED`,
`ZIP_UNREADABLE`) is retained but **uncitable**, counted in daily output and reported by Task 5.
v1 has no manual-resolution mechanism; if `MISMATCH` proves common, a later bead adds an
identity rule. The daily trigger stays NSE board meetings and announcements. Out of scope:
Tijori AI reports (`/reports/`), Con Call Summary (a modal with 0 links) and recordings.

**Facts (probe 2026-10-27, `scratchpad/vendor-doc-probe/summary.md`, and code):**
- Tijori company_id 4290, slug `apar-industries-limited`. `GET /company/<slug>/` renders a
  static `#companyFilings` table: Annual Report 16 (2011–2026), Earnings Release 14 (2022–2026),
  Investor Presentation 52 (2013–2026), Conference Call 53 (2010–2026), Con Call Summary 0.
  That is 135 links, all under `files.tijorifinance.com/insight/india/4290/<Kind>/`. The page
  was not retained, and no Tijori document was downloaded.
- This is the page the code already fetches as `TIJORI_OVERVIEW = ("tijori", "overview")`
  (`contracts/source_catalog.py:241`; registered as `INDEPENDENT_VENDOR`, HTML, A05-005, `:305`;
  URL `{base}/company/{slug}/`, `ingest/tijori_source.py:123`). The fetch is authenticated with
  a 30 s timeout and 3 attempts (`tijori_source.py:164-165, 558`), via
  `fetch_overview_bytes` (`ingest/tijori_screen_fetch.py:51`). The identity gate is
  `TijoriSource.parse_overview_bytes(..., section=COMPANY_DETAILS)` (`tijori_source.py:450`),
  used by `coverage/screen_review.py:305-318`; it checks the `company_details_data` symbol and
  company_id (`ingest/tijori_overview.py:108-157`).
- `ORIGINS` has no entry for `TIJORI_OVERVIEW` (`entity/discovery.py:128-140`), and
  `authorised` requires one (`:273-281`). `live_transport` sends the Tijori session cookie only
  when `source_id == "tijori"` (`api/onboard_cli.py:257-270`).
- APARINDS's verified Tijori identifiers are in `config/watchlist.yaml:331-332`
  (`needs_verification: []`), and the gate is `unverified_tijori_fields()`
  (`api/watchlist_config.py:133`).
- Task 1's `DocumentIntake.attempts` returns outcomes only, and its OK-span query `_OK_SPANS`
  is private (`pg/document_intake.py`), so the match needs two additive reads (Interfaces).

**Design (no DDL; no change to any Task 1–4 interface; additional SELECTs only):**
1. The Tijori page reuses `TIJORI_OVERVIEW`, just as Task 2 reuses `SCREENER_PAGE`. It becomes
   one more **unwindowed listing** in `documents backfill` and `documents daily`, behind a
   `--tijori` flag. Its rows are `DocumentLink`s keyed by full URL, query string included, as
   Screener links are (Task 3); a changed URL is a new occurrence. They go through
   `record_listing` unchanged.
2. Document surfaces are `("tijori-documents", f"TIJORI_{kind}")` for each mapped kind. Each is
   PDF, `SourceRole.DIAGNOSTIC`, `_SUBSCRIBER_RIGHTS`, on `files.tijorifinance.com`, and the
   source gets one `SourceDescriptor(source_id="tijori-documents",
   source_class=SourceClass.DERIVED, evidence_role=EvidenceRole.DIAGNOSTIC_ONLY)`. Task 4 step 4
   (attempts, bounds, `GAP`, recovery) applies unchanged. Only the link-to-request map widens:
   `document_request(link) or tijori_document_request(link)`.
3. **The citation is computed at read time** by a pure function over the latest revisions,
   their OK attempts' `body_sha256`, and ZIP member digests pre-computed before the call. A1
   adds no table and no migration 0044.
4. `daily --tijori` also refreshes the NSE annual-report listing (the whole listing, no
   `--annual-reports` cap), so pending NSE annual reports are fetched by step 4 as usual.
5. Tijori revisions never create beads; step 5 reads announcement revisions only. NSE-only
   documents are still fetched exactly as before.

**Candidates.** The kind map is Annual Report → ANNUAL_REPORT, Conference Call → TRANSCRIPT,
Investor Presentation → PRESENTATION, and Earnings Release → RESULTS only if Step 0 rules it the
results statement (otherwise Earnings Release is skipped in v1, like Con Call Summary). Any
other heading carrying links is refused (layout drift). Candidates are NSE `DocumentLink`s of
the same kind in the issuer's latest revisions:
- **ANNUAL_REPORT:** NSE annual-report entries whose `toYr` equals the row's year label, if
  Step 0 confirmed the label; otherwise every NSE annual-report entry (match by SHA-256 only).
  Its **coverage** is an `OK` annual-report listing fetch on this run.
- **Other kinds:** NSE announcement links whose broadcast date (IST) lies in
  `[row date − 7, row date + 7]`. Its **coverage** is that the union of `OK` announcement spans
  (each capped at its retrieval date, as `coverage` does; adjacent spans join) contains the whole
  interval. A month-only row date (Step 0 ruling, 2026-10-28) uses `[first day of month − 7,
  last day of month + 7]`, and its month decides the 2023-07-01 cutoff. A row with no month is
  `UNDATED` and has no candidates.
- **Unresolved:** for a TRANSCRIPT, any `CONCALL_UNRESOLVED` announcement (from `latest` +
  `classify_announcement`, dated by `an_dt`) inside the interval.
- **Row date** for the 2023-07-01 test: the row's date; a year-only annual-report label `Y`
  counts as `Y-12-31`, so the exception is never widened.
- **Candidate state:** `OK` with digests (the capture's SHA-256, or for a ZIP the SHA-256 of
  each `.pdf` member), `PENDING`, `UNAVAILABLE` (terminal or exhausted under Task 4 step 4,
  `TOO_LARGE` included) or `ZIP_UNREADABLE`.

**Precedence (first that holds; computed only for a Tijori copy with an `OK` attempt — otherwise
Task 4's pending or `GAP` rule applies):**
1. Non-annual row without a month → `UNDATED` (it has no date or candidates, so no
   higher outcome can hold).
2. A candidate digest equals the Tijori SHA-256 → `CORROBORATED`, citing the lowest
   `capture_ref_id`, then the lowest member name.
3. Row date before 2023-07-01 with no candidate → `VENDOR_COPY nse-unlisted` (orchestrator ruling
   2026-10-28: an NSE candidate that exists, e.g. a pre-2023 annual report, falls through to 4–5,
   because the owner rule keeps an existing NSE original as the record). No candidate, no
   unresolved row, and covered → `VENDOR_COPY nse-none`.
4. ≥ 2 candidates, or an unresolved row → `AMBIGUOUS`.
5. Exactly one candidate: `PENDING` → `NSE_PENDING`; `UNAVAILABLE` → `NSE_UNAVAILABLE`;
   `ZIP_UNREADABLE` → `ZIP_UNREADABLE`; `OK` → `MISMATCH`. No candidate, not covered →
   `NSE_PENDING`.

**ZIP digests.** For each NSE `ANNUAL_REPORT` OK capture whose body starts `PK\x03\x04`, the CLI
opens it with stdlib `zipfile` from memory and streams each `.pdf` member through `sha256` in
chunks, stopping at 64 MiB decompressed per member; nothing is written to disk. A corrupt,
encrypted or over-cap archive makes that candidate `ZIP_UNREADABLE`. The member name is kept in
the result.

### Step 0 (orchestrator, before Task 4b; network, read-only)

A throwaway `scratchpad/docs-1/capture_tijori_page.py` does four things:
1. Builds `TijoriSource(TijoriSourceConfig(credentials=_tijori_credentials_from_env()))`.
2. Calls `fetch_overview_bytes(source, "apar-industries-limited")`.
3. Runs the identity gate (`parse_overview_bytes`, expected `APARINDS` / 4290).
4. Writes the bytes, mode 600, to the gitignored
   `data/raw/watchlist/aparinds/docs-probe-2026-10-28/tijori_company_apar-industries-limited.html`.

It prints only these, and no body or cookie: the SHA-256; per-heading link counts; the
`#companyFilings` column labels; how many rows carry a day-level date.

It then GETs the first Annual Report link without the cookie (30 s timeout, no retry) and prints
only the HTTP status and whether the body starts with `%PDF-`. Outcomes:
- **`200` + `%PDF-`:** no cookie needed.
- **`401`/`403`, or a login HTML page:** Task 4b adds `"tijori-documents"` to `live_transport`'s
  cookie map (one line, `onboard_cli.py:257-260`). The owner's own session on Tijori's own host,
  no evasion. Step 0 repeats the GET with the cookie and must see `200` + `%PDF-`; else stop.
- **Any other response** (non-`200`, a non-PDF non-login `200`, or a transport failure): stop and
  report.

Two document checks (downloads to the same gitignored directory, mode 600; facts only in notes):
- **Earnings Release.** Open the first Earnings Release file. If it is the quarterly results
  statement, the kind is RESULTS; otherwise Earnings Release is skipped in v1.
- **Annual-report year label.** Download the Tijori annual report labelled with the latest year
  and the NSE `toYr` entry for that year (URL from the retained 2026-10-27 probe JSON). Equal
  SHA-256, or the same fiscal year on both covers → the label holds; otherwise annual reports
  match by SHA-256 only.

Drift: a heading count below the probe's, or a missing heading → stop. Higher counts (new
filings) are recorded and pinned by the tests. No row with a day-level date → stop (every
non-annual row would be `UNDATED`). Facts go in the `eqos-msq` notes.

### Task 4b: Tijori `#companyFilings` reader and listing

Goal: an identity-checked Tijori page yields every mapped-heading link as a `DocumentLink`.
`documents backfill`/`daily --tijori` records the page as a listing and fetches each link on its
Tijori surface under A05-005. Each fetched Tijori copy gets a read-time `Citation`. A page for
another company, an off-prefix link or a missing table yields nothing.

Files:
- Create: `src/fundamentals/ingest/tijori_documents.py` (reader, request map, ZIP digests, match
  rule)
- Modify: `src/fundamentals/contracts/source_catalog.py` (the Tijori document surfaces and the
  `tijori-documents` descriptor), `src/fundamentals/entity/discovery.py` (`ORIGINS`:
  `TIJORI_OVERVIEW` → `www.tijorifinance.com`, document surfaces → `files.tijorifinance.com`),
  `src/fundamentals/pg/document_intake.py` (two reads), `src/fundamentals/api/documents_cli.py`
  and `src/fundamentals/api/cli_parser.py` (`--tijori`; `--config-root` also on `daily`, default
  `config`); `src/fundamentals/api/onboard_cli.py` only if Step 0 requires the cookie
- Test: `tests/fundamentals/test_tijori_documents.py` (new, `retained`); add cases to
  `tests/fundamentals/test_documents_daily.py`

Interfaces:
- `TIJORI_KINDS: Mapping[str, DocumentKind]` (the kind map per Step 0); `TIJORI_SKIPPED`
  (headings ignored); `TIJORI_DOCUMENT_SURFACES` (one comprehension over the kinds).
- `read_tijori_documents(page: bytes, *, slug: str, expected_symbol: str,
  expected_company_id: int) -> tuple[DocumentLink, ...]`. It runs the identity gate first, so
  `TijoriOverviewIdentityError` propagates. It reads `//*[@id="companyFilings"]` rows. Fields:
  `period` = the row's label, `filed_at` = the row's date when it has one, `found_on = "tijori"`.
  It raises `ValueError` when `#companyFilings` is missing or has no heading rows, when an
  unknown heading has links, or when any link under a mapped heading is not
  `https://files.tijorifinance.com/insight/india/<expected_company_id>/…`. A table with headings
  and no links is a valid empty listing.
- `tijori_document_request(link: DocumentLink) -> Request | None`. Only for `https` on
  `files.tijorifinance.com`; it percent-encodes the path (`Annual Report` contains a space).
  Task 3's `document_request` still returns `None` for that host, and its test stands.
- `zip_pdf_digests(body: bytes) -> tuple[tuple[str, str], ...] | None` (member name, SHA-256;
  `None` = unreadable).
- `Citation(StrEnum)`: `CORROBORATED`, `VENDOR_COPY`, `AMBIGUOUS`, `NSE_PENDING`,
  `NSE_UNAVAILABLE`, `MISMATCH`, `UNDATED`, `ZIP_UNREADABLE`; `CITABLE = {CORROBORATED,
  VENDOR_COPY}`. `Candidate(BaseModel, frozen)`: `capture_ref_id: int | None`, `state`,
  `digests: tuple[tuple[str, str], ...]` (member `""` for a plain PDF).
  `cite(row_date: date | None, annual: bool, tijori_sha256: str, candidates:
  Sequence[Candidate], *, unresolved: bool, covered: bool) -> tuple[Citation, str]` (pure; the
  second value is the reason for `VENDOR_COPY`, else `"<capture_ref_id>[:<member>]"` for
  `CORROBORATED`, else `""`). `covers(spans, start, end) -> bool` (pure).
- `DocumentIntake` (additive SELECTs, no DDL): `ok_attempt(observation_id, url) ->
  tuple[str, int, str] | None` (the OK attempt's `body_sha256`, `capture_ref_id` and its
  `capture_refs.capture_id`, one SELECT with a join); `ok_spans(entity_id, surface) ->
  list[tuple[date, date]]` (runs the existing `_OK_SPANS`). The CLI reads a ZIP body with the
  existing `store.list_captures` + `store.read_body`, picking the record by `capture_id`.

Approach (in `documents_cli`, per covered issuer, only with `--tijori`):
- The stock comes from `<config-root>/watchlist.yaml` by NSE symbol.
  `unverified_tijori_fields()` must be empty; otherwise, or if the stock is absent, print
  `UNCOVERED\t<SYMBOL>\ttijori\t-\t-`.
- Fetch the page with `acquiring_fetch(live_transport())` on `TIJORI_OVERVIEW`: one request,
  spaced 3 s, on the existing 30 s timeout path. On failure record the listing with its outcome
  and print `UNCOVERED`. On `TijoriOverviewIdentityError` print `refused tijori identity`; on the
  reader's `ValueError` print `refused tijori listing`; both are `INCOMPLETE`, as Screener is.
- With `daily --tijori`, read the NSE annual-report listing too (Design 4).
- Otherwise run Task 4 step 3 (one transaction) and step 4.
- After step 4, build candidates per Tijori copy and call `cite`. Print one line per outcome,
  zeros included, summed over issuers: `CITE\t<outcome>\t<count>`. Exit code unchanged.
- Size: about 170 lines of Python (reader ~45, ZIP digests ~15, `cite` + `covers` ~35, catalog,
  descriptor and origins ~10, intake reads ~10, CLI ~55, cookie ≤ 1). Two SELECT strings, no DDL.
  Total DOCS-1 ≈ 600 lines of Python plus the 0043 migration.

Verification (slice `DOCS-1-T4b`): `scripts/verify.sh red DOCS-1-T4b
tests/fundamentals/test_tijori_documents.py tests/fundamentals/test_documents_daily.py` records
each new test failing first. Then `scripts/verify.sh gate DOCS-1-T4b`. Every Task 1–4 test stays
green and unmodified, and runs without `--tijori` send no Tijori request.

Test seams:
- **Reader (`retained`, Step 0 fixture pinned by full SHA-256).** Counts are the probe's unless
  Step 0 recorded new ones: ANNUAL_REPORT 16, PRESENTATION 52, TRANSCRIPT 53, RESULTS 14 if
  mapped. There are no Con Call Summary links. Every path starts `/insight/india/4290/` on
  `files.tijorifinance.com`. ANNUAL_REPORT years run 2011–2026 and TRANSCRIPT years 2010–2026.
  `expected_company_id=4291` and `expected_symbol="APARIND"` each raise. Every link maps to a
  `tijori-documents` request, and `document_request` maps none of them.
- **Reader negatives (small, synthetic pages that pass the identity gate):** a page with one
  Annual Report link under `/insight/india/4291/` raises `ValueError`; a page without
  `#companyFilings` raises `ValueError`.
- **Match rule (small, synthetic):**
  - One case per precedence line (1–5).
  - One permutation case: two candidates whose digests both match, given in both orders, cite
    the lower `capture_ref_id` each time.
  - Interval edge: spans ending at row date + 6 → `NSE_PENDING`; ending at + 7 → `VENDOR_COPY
    nse-none`.
  - A post-2023-07-01 TRANSCRIPT with a `CONCALL_UNRESOLVED` row in its interval is `AMBIGUOUS`.
  - ZIP: a member byte-identical to the Tijori PDF → `CORROBORATED` with that member name; a ZIP
    whose only member differs → `MISMATCH`; malformed bytes → `ZIP_UNREADABLE`.
- **CLI (`pg`, fake `send`, as Task 4):**
  - A `--tijori` run registers Tijori copies with A05-005 `authority_refs` on
    `("tijori-documents", "TIJORI_TRANSCRIPT")`.
  - A Tijori transcript byte-identical to the NSE one prints `CITE\tCORROBORATED\t1`.
  - A Tijori-only presentation in a covered interval prints `CITE\tVENDOR_COPY\t1`.
  - The second identical run sends no document request and creates no bead; Tijori rows never
    create a bead.
  - A wrong-company page prints `refused tijori identity`, and the exit is `INCOMPLETE`.
  - A covered issuer missing from `watchlist.yaml` prints `UNCOVERED … tijori`.
  - A Tijori `HTTP_403` five times gives `GAP` and no sixth request.

Dependencies: Tasks 1–4 (it lands after them; the Task 1–4 code is not touched beyond the named
additive lines) and Step 0.

Risks:
- **Medium: the ±7-day interval is inferred.** An NSE filing more than 7 days from the Tijori
  row date falls outside it, so that Tijori copy is cited `nse-none` although NSE has it. Task 5's
  sample of `nse-none` is the check.
- **NSE ZIP annual reports** corroborate through a byte-identical PDF member; a re-rendered PDF
  is `MISMATCH` (uncitable at any age). A corrupt or over-64 MiB member is
  `ZIP_UNREADABLE`. Tijori ARs over 32 MiB are `TOO_LARGE` gaps.

### Effect on Task 5 (overrides its text where they conflict)

- **Command.** Steps 1–2 run `documents backfill --symbol APARINDS --from 2023-07-01
  --to 2026-10-27 --annual-reports 17 --screener --tijori --config-root config …`. All 17 NSE
  annual reports give every Tijori AR (2011–2026) a candidate. The step 5 daily prompt adds
  `--tijori --config-root config`, and its report list (Task 5 step 5 (3)) adds every `CITE`
  line.
- **Requests.** The run adds one page, ~135 Tijori documents (probe count) and ≤ 12 more NSE
  annual reports. That is ~150 requests at 3 s, ~8 min, in a single pass (the listing is
  unwindowed), for the rehearsal and again live. Each daily run adds two listing requests.
- **Acceptance.** A quarter or year counts if it has a registered NSE original **or** a
  registered Tijori copy whose citation is `CORROBORATED` or `VENDOR_COPY`. The report shows
  separate columns: NSE original; `CORROBORATED`; `VENDOR_COPY` (`nse-none` / `nse-unlisted`);
  and the count of each uncitable outcome. "Counts first-party only" is replaced by this
  labelled union. BSE `HTTP_403` stops being an allowed blocked-gap reason wherever a citable
  Tijori copy exists.
- **Step 3 additions.** Report counts per outcome and per kind; no rate thresholds. The
  orchestrator inspects a sample of each uncitable outcome and of `nse-none`: an R5 miss goes
  back to Task 3; common `MISMATCH` opens the identity-rule bead. The LIVE-RUN-1 transcript
  SHA-256 check also covers the matching Tijori copies.
- **Step 4** checks the Tijori rows and captures as well.

### A1 Step 0 record and orchestrator rulings (2026-10-28)

Step 0 (Sol, APARINDS): page `200`; counts AR 16, Earnings Release 14, Presentation 52,
Conference Call 53 (all equal the probe); prefix `files.tijorifinance.com/insight/india/4290/<Kind>/`;
cookieless document GETs return `200` PDF (no cookie needed); **no row carries a day-level date**
(month only). Rulings:
1. **Month-only dates** do not stop A1. The candidate interval widens to the whole month ± 7 days
   (above). Citability is unchanged: a hash match is identity at any window width, and `nse-none`
   still needs full OK coverage of the wider interval, so a wider window can only add `AMBIGUOUS`,
   never a wrong citation. Step 0's "no day-level date → stop" is superseded by this ruling.
2. **Earnings Release → `RESULTS`.** Its first page reads "Financial Results of the Company for
   the Financial Year ended March 31, 2026", the results statement.
3. **Annual year label = NSE `toYr`:** the one pair checked (2026 = 2026) agrees, so the label is
   used.

### Phase-review deviation (2026-10-28)

Bead external refs key on the entity id, not the symbol (final critical review: a symbol change
duplicated release beads); the symbol stays in the bead title and output lines.

### A1 open question

1. **NSE depth before 2023-07** (orchestrator recommendation: no for now). Pre-2023-07-01
   Tijori copies with no NSE candidate are cited `nse-unlisted` under the historical exception.
   Listing NSE further back costs about one pass (12 spans) per year per windowed listing and
   would only add corroboration. This does not affect the Task 5 window.
