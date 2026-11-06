# VENDOR-1 Phase 2 Implementation Plan

**Status:** approved, gpt-6.1-sol plan review 3 (APPROVE, 2026-11-06). Implementation notes from
that review:
- An imported successor that inherits S still refuses atomically when S > its own K.
- Exercise `--frozen` and `--budget` through the public CLI.
- Grant the runtime role SELECT and INSERT on `version_source_cutoffs`, and verify it through that
  role.

**Bead:** `eqos-awnc`.
**Origin:** `docs/specs/2026-11-06-vendor-first.md` §7, approved by gpt-6.1-sol in round 3 on
2026-11-06, as amended by the Phase 2 scope amendment (§7, from this review). §1–§4 give the
owner's order and defaults. Code facts were read at `19545c8e` and rechecked at `b9e96e4a`.
Retained page formats come from `data/raw/vendor-surface/2026-10-28/` and `data/raw/snapshots/v1/`,
read for structure only. The store was **not queried** for this plan; read-only authentication
failed, so no store fact below is established.
**Goal:** Screener summary text, including the concall summaries, appears in a private report as
cited, issuer-bound vendor text. It is never a number source, and a span holding a numeral is never
shown. Tijori text is deferred (reading 2); Phase 2 does not claim it.

**Out of scope:** numbers (Phase 1); banks (Phase 3); the five-company test (§9). Also out:
the document-extraction model that consumes numeral pointers (reading 6 defines the handoff it
uses), status notes for cited spans whose capture later expires (reading 8), and any Tijori text
reader (reading 2).

**Constraints:**
- Readers are code, because the vendor page formats are fixed. A model only selects span offsets,
  as `extract_text` does today, and code validates and binds every span (CLAUDE.md, Data
  Extraction).
- `vendor_text_claims` never produce occurrences, interpretations or claim values.
- Private stored and sealed reports may hold only reviewed, bound, numeral-free spans. No vendor
  body, span text or summary wording goes into committed files, test files, ordinary logs or public
  artifacts; diagnostics are coordinates and counts. Tests address retained captures by their
  coordinates, as `test_vendor_retained.py` does.
- Never open `stage4_holdout.yaml`, `stage4_manifest.yaml`, `data/holdout/` or
  `data/raw/onboarding/`.
- Files stay at or under 800 lines. `run_draft.py` is at 808 (F15); Task 5 brings it to ≤ 800 by a
  coherent extraction, not line folding. New logic goes into new modules.
- New migrations are numbered `0051` or later (`0049` exists; P1's phase-fix round takes `0052`
  and Phase 3 `0053`). This phase has no live `db migrate`; P1 Task 13 may apply `0051` to live
  first (amended 2026-11-06).
- Tests follow `.claude/rules/python/testing.md`: feature and end-to-end tests through public
  paths first. Unit tests are only for the numeral rule and span binding.
- Live writes are permanent. Task 2 follows the live protocol below.

**Shape:** Tasks 1 and 3–5 are code, one commit each, verified by the orchestrator. Task 2 is the
phase's only live write: it captures Apar's Screener concall summaries. Task 6 is the gate.
**Sol reviews this plan, then once at phase end**, using the loop in
`.claude/rules/core/04-agent-stack.md` and closing with one fresh critical review.

**Estimate:** about 23 hours summed, the author's estimate, not measured.

| Task | Implementer | Hours |
|---|---|---|
| 1. Screener concall-summary capture surface | Sonnet | 2.5 |
| 2. Live: capture Apar's concall summaries | orchestrator | 2.5 |
| 3. Readers keyed by (site, surface) | Opus | 4 |
| 4. Eligible spans, binding and citation | Opus | 5.5 |
| 5. The vendor summary block | Opus | 3.5 |
| 6. Gate | orchestrator | 1.5 |
| Sol phase-end loop, closing review, close-out | — | 3.5 |

## What the code shows (read before the readings)

1. **Tijori `concall-monitor` has no text.** Both retained captures, the 2026-10-28 crawl
   reference and the snapshot `vs.concall-monitor` of 2026-10-30, are the same landing page. It
   has no table, no data island and no issuer markup. `tijori_events_models.py`
   (`CONCALL_NOT_STATIC_REASON`, `NOT_STATIC_SURFACES`), `surfaces.yaml` (`group: NONE`) and
   `catalog.yaml` ("Landing page only; summaries are AI") say so. The summary API
   `/results/concall-summaries/api/` returned 404 and is deny-listed.
2. **The Screener concall notes are not on the company page.** Each `#documents` concalls row
   carries a "Notes" button pointing at `/concalls/summary/{id}/`, an AI route excluded by
   `vendor_surface_fetch.NAMED_PATHS`, `runbook.md` §1 and `not-capturable.md`. Never captured.
3. **Span offsets index the reader's normalised text, not the capture bytes.**
4. **Ledger claims are all `NumericClaim`.** Prose cites a capture only through a location marker
   `{{s:<capture>|<anchor>}}` (`resolve_location`, first-party PDF only). A vendor `SOURCE_QUOTE`
   already resolves to `None`, so a numeric claim citing only a span is `UNRESOLVED`.
5. **`extract_text` writes only `vendor_text_claims` and `vendor_outcomes`**, under parser version
   `claims:<model>:spans.v2`, pinned to the digest of `inspect.getsource(extract_text)`. Claims
   carry `model_id` and `prompt_version`; outcomes carry the joined version; there is no foreign
   key between them.
6. **Vendor identity lives in `vendor_basis_bindings`, not in `identity_layers`.**
   `latest_slice` serves only `ISIN`, `NSE_SYMBOL` and `BSE_SCRIP`. A binding row holds
   `screener_company_id`, its proving `capture_ref_id` (identity read by `read_identity`) and
   `recorded_at`; the capture's URL, with the Screener slug, is in `capture_addresses`.
7. **Versions persist only `knowledge_cutoff`** (= the derivation cutoff). Checking and sealing
   (`lifecycle.py`) pass it to `resolve_location`; the source cutoff is not stored.
8. **`render_section` substitutes every `{{c:…|…}}` token**, and `scan_section` reports
   unlabelled prose (`- none`, an unmarked heading line) as `UNLABELLED_PROSE`.

## Readings (as ruled by Sol, review 1)

1. **The Screener concall-notes source — accepted.** Lift the exclusion for
   `/concalls/summary/{id}/` only. GET-only, reached only through the company page's own buttons,
   pacing, hosts, stop behaviour and every other denied route unchanged. Tijori's AI route and
   Screener's `/annual-reports/{id}/summary/` stay denied. The licence question (spec §11) stays
   open.
2. **The Tijori reader — accepted: none in Phase 2.** §7 is amended (Phase 2 scope amendment).
   The orchestrator files the Tijori-route bead. The `(site, surface)` key still lands.
3. **Offsets and the capture hash — accepted with a condition.** Offsets index the reader's text;
   resolution re-reads verified retained bytes, requires valid non-empty bounds, the full anchor
   and slice equality with the stored `text`; the hash is `capture_refs.blob_sha256`. A reader
   change fails only where it changes a referenced slice or binding. The extraction identity is
   bumped separately (Task 3). Expiry or licence end is unavailable evidence (unresolved); a body
   whose bytes no longer match the hash is an integrity failure and raises.
4. **The company reference — revised.** Identity comes from `vendor_ids` (Task 4), never
   `latest_slice`:
   - company id: the unique `screener_company_id` over the entity's `vendor_basis_bindings` rows
     recorded by the knowledge cutoff;
   - slug: the `/company/<slug>/` segment of those bindings' capture addresses, unique;
   - missing, conflicting or late (recorded after the cutoff) evidence → no binding.

   Per reader: a company page binds by its own identity element (`read_identity`);
   `company-announcements` binds by the company id in its registered address; a feed item binds
   by its own `/company/<slug>/` link and a span must lie inside one item; the concall summary
   binds by the own reference Task 2 records, or the branch stops (Task 2 exit). Parent lineage
   never binds; the concall id is never a company id.
5. **What counts as a numeral — accepted.** Any Unicode numeric character or a match of
   `numeral_scan`'s number-word lexicon, on the raw span, with no date or period exemption.
   Enforced at every report-use boundary (Task 4), together with a refusal of `{{` and `}}`.
6. **The extraction pointer — revised: a documented handoff, no Phase 2 code.** The contract the
   future consumer implements:
   - **Pointer:** a `CLAIM` row holding a numeral, from the selected extraction (reading 7), with
     its provenance `(capture_ref_id, surface, start, end, blob_sha256)`.
   - **Target:** the first-party document the vendor page links for that item: for a concall
     summary, the Transcript or PPT link of the issuer company page's `#documents` concalls row
     whose Notes button carries the summary's registered address; for an announcement item, its
     exchange PDF link. A company-page span has no target.
   - **Found:** the target counts only if its address is a retained first-party capture
     (`capture_addresses`) of the same issuer; extractions from it carry their own page and quote.
   - **Unresolved:** otherwise the result is `TARGET_UNRESOLVED` with a reason (`NO_LINK`,
     `NOT_RETAINED`, `OTHER_ISSUER`). The pointer never supplies a number.
7. **Which spans render — accepted with a condition.** Two clocks: capture registration by the
   source cutoff S; claim and outcome rows and identity evidence recorded by the knowledge cutoff
   K. Per `(site, surface, request_key)`, the latest capture registered by S (ties: higher
   `capture_ref_id`); per capture, the latest completed outcome (`OK`, `PARTIAL` or `EMPTY`)
   recorded by K (ties: higher outcome id), whose rows are the `CLAIM` rows joined exactly on
   capture, surface, `model_id` and `prompt_version`. An `EMPTY` or zero-row latest extraction
   yields nothing; earlier extractions are never revived. `FAILED` and `UNUSABLE` are not
   completions. Equal texts are shown once, keeping the lowest `(capture_ref_id, start)`. The same
   rule applies at drafting, checking and sealing. Headings state vendor, surface and capture
   date, not the report quarter.
8. **Expiry of a cited span after sealing — accepted.** Sealed bytes never change; a later
   re-check reports the location unresolved. No status note in Phase 2 (bead). This adds no
   automatic revalidation and no text-retention exception.

## File map

| Path | Change | Responsibility |
|---|---|---|
| `equity_os/sourcing/surfaces/vendor_surface_fetch.py` | modify | drop `/concalls/summary/` from `NAMED_PATHS` |
| `config/sourcing/vendor_surface/surfaces.yaml`, `config/sourcing/sources.yaml` | modify | `concall-summary` surface and its capture-spec entry |
| `docs/research/vendor-surface/catalog.yaml` | modify | Screener `concall-summary` entry (Task 1; evidence updated after Task 2) |
| `equity_os/sourcing/surfaces/vendor_surface_expand.py` | modify | `screener_concall_summaries` expansion from `company-page` |
| `docs/research/vendor-surface/runbook.md`, `not-capturable.md` | modify | the narrowed AI-route line |
| `equity_os/extraction/surfaces/vendor_text_readers.py` | create | `READERS`, `ReaderText`, `TextItem`, the four Screener readers |
| `equity_os/extraction/model/vendor_surface_claims.py` | modify | keyed query, address input, `spans.v3` |
| `migrations/0051_version_source_cutoff.sql` | create | `eqos.version_source_cutoffs` |
| `equity_os/contracts/publication/ledger.py`, `equity_os/storage/records/store.py` | modify | `VersionDraft.source_cutoff`; `create_version` writes the row, `read_version` loads it |
| `equity_os/interface/commands/sourcing/vendor_surface_cli.py`, `equity_os/sourcing/surfaces/vendor_surface_capture.py` | modify | `--frozen` request set and `--budget` for `vendor capture` |
| `equity_os/publication/revision/rework.py` | modify | the vendor section is regenerated, never a preserved scaffold |
| `equity_os/publication/checking/vendor_text.py` | create | `VT_ANCHOR`, `vendor_ids`, `eligible_spans` |
| `equity_os/publication/checking/numeral_scan.py` | modify | `has_numeral` |
| `equity_os/publication/checking/citations.py` | modify | `resolve_location` vendor branch, `source_cutoff` argument |
| `equity_os/publication/approval/lifecycle.py` | modify | pass the version's source cutoff to `resolve_location` |
| `equity_os/publication/drafting/vendor_summary.py` | create | the vendor summary section |
| `equity_os/publication/drafting/run_draft.py` | modify | add the section; set `source_cutoff`; extraction to ≤ 800 lines |
| `tests/equity_os/sourcing/surfaces/test_vendor_surface_fetch.py`, `test_vendor_surface_company.py` | modify | deny rule; expansion replay |
| `tests/equity_os/extraction/model/test_vendor_surface_claims.py` | modify | readers, keyed query, upgrade, retained captures |
| `tests/equity_os/publication/checking/test_vendor_text_citation.py` | create | binding, clocks, resolution, refusals (`pg`) |
| `tests/equity_os/publication/checking/test_audit_numeral_scan.py` | modify | `has_numeral` cases |
| `tests/equity_os/interface/workflows/test_data_stage2_e2e.py` | modify | the rendered block and seal refusals through the real path |

## Task 1: Screener concall-summary capture surface

Goal: `eqos vendor capture --symbol <S> --surface screener:concall-summary` fetches the issuer's
company page as today and then exactly the `/concalls/summary/{id}/` addresses it advertises.
Every other AI route stays denied.

Files:
- Modify: `vendor_surface_fetch.py`, `surfaces.yaml`, `sources.yaml` (Screener `capture_specs`),
  `catalog.yaml`, `vendor_surface_expand.py`, `vendor_surface_capture.py`,
  `vendor_surface_cli.py`, `runbook.md`, `not-capturable.md`
- Test: `test_vendor_surface_fetch.py`, plus replay and frozen-set cases in
  `test_vendor_surface_company.py`

Interfaces:
- Produces:
  - surface `concall-summary` (`site: screener-subscriber`, `scope: COMPANY`,
    `path: /concalls/summary/{concall_id}/`, `group: NONE`, `cadence: AFTER_RESULTS`,
    `expand: screener_concall_summaries`);
  - a same-id Screener `catalog.yaml` entry (`scope: company`, the same `url_pattern`), its
    evidence status "not yet captured", updated from Task 2's structure record;
  - `parent_surface` maps it to `company-page`;
  - `EXPANSIONS["screener_concall_summaries"]`, one `child(spec, context, concall_id=...)` per
    distinct advertised id;
  - `vendor capture --frozen <file> --budget <n>` (R2-03): `<file>` lists the permitted registered
    addresses, one per line; `capture_company(..., frozen: frozenset[str] | None = None)` refuses
    any request outside it before fetching, and once the parent pages are fetched and expanded
    (they run first), stops if the requested-or-pending set differs from it in either direction,
    before any child is fetched. The stop exits non-zero and names the differing addresses'
    coordinates. `--budget` sets `VendorFetcher(site_budget=n)`, which counts every actual
    request, parents and identity pages included.

Approach: Reading 1. Remove only the `/concalls/summary/` entry. The expansion reads the Notes
button addresses from the `#documents` concalls rows of the parent page, which `read_identity` has
verified. Edit the runbook and not-capturable lines to say what is now captured and why (VENDOR-1
§7, owner order 2026-11-05). Catalog validation stays on.

Verification:
- `load_specs` over the real `surfaces.yaml` and `catalog.yaml` succeeds (the public config path).
- `is_denied` is false for `/concalls/summary/1/` and still true for `/results/concall-summaries/`
  and `/annual-reports/1/summary/`.
- Replay over Apar's retained company page yields one request per distinct Notes button.
- With a scripted opener, a parent advertising a child outside the frozen set, or missing one,
  stops with no child fetched; a budget smaller than the set stops at the budget, and no unlisted
  child is ever fetched.
- `test_screener_documents.py` and the vendor-surface suites pass unchanged.

Dependencies: None.

Risks: the route may need XHR headers the gateway does not send. Task 2 finds out; a refused fetch
is recorded, not worked around.

## Live protocol (Task 2)

Phase 1's live protocol (`docs/plans/VENDOR-1-P1.md`, steps 1–6) applies, with these changes:
- **Footprint.** The command fetches the company page and its identity pages, parses its
  configured sections, then fetches the advertised summaries. Allowed tables: `capture_refs`,
  `capture_addresses`, `retention_classes`, `vendor_parser_versions`, `vendor_outcomes`,
  `vendor_values` and `vendor_basis_bindings` (company page; Apar's bindings exist, so no new
  binding row is expected), capture attempts and blobs. Every pre-existing row stays unchanged
  (fingerprints).
- **Bindings.** `commands.txt` writes the snapshot root as `${SNAPSHOT_ROOT}`; a sidecar
  `bindings.txt` (hashed with it) fixes the two permitted differences: rehearsal = the restored
  `eqos_test_*` database and a scratch root, live = `equity_os` and `data/raw/snapshots/v1`.
- **Equivalence.** Live must equal rehearsal on the set of `(surface, registered address,
  issuer)` requests, their outcome codes, and table deltas and row counts. Only body and blob
  hashes may differ.
- **Frozen request set.** Preflight (read-only, no network request) replays Task 1's expansion
  over the latest retained Apar company page and writes `frozen.txt`: the parent, identity pages
  and advertised summary addresses, P of them. It is hashed with `commands.txt`. Rehearsal and
  live both run with `--frozen frozen.txt`, so a changed parent stops the command before any child
  is fetched (Task 1).
- **Combined budget.** 2P ≤ 350, or stop. Rehearsal runs with `--budget P`; live runs with
  `--budget min(P, 350 − R)`, where R is the rehearsal's actual request count from its log.
  Preflight makes no request, so rehearsal plus live never exceeds 350.
- **Stops.** Stop before live if: rehearsal stopped on the frozen set or budget, any auth refusal
  occurred, or a site `STOP-<site>` marker exists. A stop is never cleared to continue; its log
  stays in `p2-ground/`. The post-command equivalence comparison remains a separate check.
- **Serial ownership.** The orchestrator runs Task 2 and Phase 1 Tasks 13–14 one at a time, never
  overlapping. Each baseline and rehearsal is taken on the main revision after the preceding live
  task; no earlier rehearsal is reused.

## Task 2: Live: capture Apar's concall summaries

Goal: The store retains Apar's Screener concall summaries, and a structure record establishes
whether a span can bind.

Files: none committed except the catalog evidence update (orchestrator). Logs, capture coordinates
and the structure record go in `scratchpad/vendor-first/p2-ground/`.

Commands, from the main checkout on Task 1's tip:
`eqos vendor capture --symbol APARINDS --surface screener:concall-summary --frozen
frozen.txt --budget <n>` (live protocol).

Record, from the retained bodies and as structure only:
- the summary region's xpath;
- the own company reference: an identity element, or a company link (`/company/<slug>/`) unique on
  the page, with its xpath;
- whether its text is list items or prose;
- the count of items holding a numeral (reading 5).

Before Task 2: Task 1's suites, mypy and ruff pass, and `eqos db check-live` is clean.

Verification:
- the live protocol passes;
- every advertised summary is `RETAINED` or has a recorded refusal outcome;
- the fetch log shows only Apar's company-page lineage and its advertised summaries.

**Exit condition.** The record names the summary region and one unambiguous own company reference
that matches Apar's `vendor_ids`. If none exists, or every fetch is refused, the concall branch
stops: the concall reader is not built, the orchestrator revises the §7 amendment and acceptance
before Task 3, and Phase 2 continues with the three existing readers, reported as such.

Dependencies: Task 1.

Risks: permanent, outward-facing reads of the vendor.

## Task 3: Readers keyed by (site, surface)

Goal: Every supported `(site, surface)` has a code reader that returns its normalised text with
each item's range and company reference. `extract_text` processes exactly those surfaces. The
three existing readers return byte-identical text.

Files:
- Create: `equity_os/extraction/surfaces/vendor_text_readers.py`
- Modify: `vendor_surface_claims.py`
- Test: `test_vendor_surface_claims.py` (`retained`, `pg`)

Interfaces:
- Consumes: Task 2's structure record.
- Produces:
  - `TextItem(start: int, end: int, company: CompanyRef)`;
  - `CompanyRef(namespace: IdentifierNamespace, value: str)`;
  - `ReaderText(text: str, items: tuple[TextItem, ...])`;
  - `READERS: Mapping[tuple[Site, str], Callable[[bytes, str], ReaderText]]` (body, registered
    address) for Screener `company-page`, `company-announcements`, `announcements-feed` and
    `concall-summary`;
  - `read_text(site, surface, body, url) -> ReaderText`, which raises `ValueError` for an
    unsupported pair or an address whose host or route does not match the surface.

Approach: §7 "Readers by site", with reading 4 per reader. Text is built exactly as `source_text`
builds it today, so stored offsets stay valid; items record where each item's parts land.
- A company page is one item with the page's identity.
- An announcements fragment is one item with the company id in its address.
- The feed has one item per `announcement-item`, with its `/company/<slug>/` link.
- A concall summary is one item with the own reference from Task 2's record.

`extract_text` selects captures by `(source_id, surface)` from `READERS`, loads each capture's
registered address once (`capture_addresses`; missing → `UNUSABLE`, no model call) and calls
`read_text(...).text`. Its prompt wording is unchanged, but `PROMPT_VERSION` becomes `spans.v3`,
since the changed function has a new source digest. Earlier captures are reprocessed under
`spans.v3` by the existing "no outcome for this version" rule whenever `extract_text` next runs
(not run live in Phase 2); `spans.v2` rows stay, and reading 7 selects the latest completed
extraction. An empty reader text records `EMPTY` without a model call.

Verification:
- On the retained Apar captures, each existing reader's text has the same sha256 as `source_text`
  gives before the change (characterization; record the digests first).
- The concall reader returns non-empty text from Task 2's captures, with items covering it.
- With a scripted model reply, `extract_text` stores validated spans for the concall capture.
- Upgrade: on a store already holding a `spans.v2` parser-version row and its outcomes and claims,
  `extract_text` records `spans.v3` outcomes, and every earlier row is unchanged.
- Over all supported text captures, `SELECT count(*) FROM eqos.interpretations WHERE
  capture_ref_id IN (SELECT capture_ref_id FROM eqos.vendor_text_claims)` is 0, and the
  `occurrences` count is unchanged by `extract_text` (never a number source).
- The test prints item counts and numeral-free item counts per surface, counts only.

Dependencies: Task 2 (its exit condition met).

Risks: a whitespace change in the join would invalidate every stored span; the digest test
catches it.

## Task 4: Eligible spans, binding and citation

Goal: One function decides which vendor spans a report may use, and drafting, checking and sealing
all use it. A numeric claim citing only a span is refused; the same claim citing a fact id passes.

Files:
- Create: `equity_os/publication/checking/vendor_text.py`,
  `migrations/0051_version_source_cutoff.sql`
- Modify: `numeral_scan.py` (`has_numeral`), `citations.py` (`resolve_location`), `lifecycle.py`
  (the two `resolve_location` partials), `contracts/publication/ledger.py`
  (`VersionDraft.source_cutoff`), `store.py` (`create_version`, `read_version`)
- Test: `test_vendor_text_citation.py` (`pg`, retained captures), `test_audit_numeral_scan.py`

Interfaces:
- Consumes: `read_text`, `ReaderText`, `TextItem` (Task 3); `retained_capture`.
- Produces:
  - `has_numeral(text: str) -> bool` (reading 5);
  - `VT_ANCHOR`, the anchor grammar `vt:<start>-<end>:<blob_sha256>` (no `|` or `}`);
  - `vendor_ids(cursor, *, entity_id, known_by) -> VendorIds | None` (reading 4);
  - `eligible_spans(cursor, *, entity_id, source_cutoff, knowledge_cutoff, snapshots,
    capture_ref_id=None) -> tuple[IssuerSpan, ...]` with `IssuerSpan(capture_ref_id, site,
    surface, registered_at, start, end, sha256, text)`;
  - `VersionDraft.source_cutoff: datetime | None = None` (outside `content_hash`, which covers
    sections and claims only);
  - `eqos.version_source_cutoffs(version_id PK → report_versions, source_cutoff NOT NULL)`, below;
  - `resolve_location(..., source_cutoff: datetime | None)`; `lifecycle.py` passes
    `draft.source_cutoff` from `read_version`.

The cutoff row (R2-02, R2-04). Migration `0051`:
- a `BEFORE INSERT` trigger takes `eqos.lock_subject('REPORT_VERSION', NEW.version_id)` and
  refuses unless the version's `created_xid = txid_current()` (the row is written only in the
  version's creating transaction, so never attached late or to an old sealed version) and
  `NEW.source_cutoff <= report_versions.knowledge_cutoff`;
- `check_version_seal` (`0012`) is installed on the table too;
- `reject_mutation` refuses update, delete and truncate, as for `report_sections`.

`create_version` writes at most one row, right after the version row: the draft's
`source_cutoff` if set (an explicit run cutoff wins); otherwise the predecessor's row if one
exists; otherwise none, and the version resolves no vendor location. `read_version` loads the
row by a left join, so narration, which copies `read_version`'s draft with `predecessor_id`, keeps
its predecessor's boundary and never widens it. Existing sealed digests are untouched.

Approach: §7 "Bound to the report" and "Resolvable reference", readings 3, 4, 5 and 7.
`eligible_spans` applies reading 7's selection, then per selected capture, once:
- the capture is `RETAINED` or `RESTORED`, its body hash equals `blob_sha256` (mismatch raises);
- its registered address is loaded and `read_text` runs once;
- `vendor_ids` at K gives the issuer's company id and slug.

Then each selected `CLAIM` row is kept only if: valid non-empty bounds, non-null text, the slice
equals the stored text, one item contains `[start, end)` with a reference equal to the issuer's,
`has_numeral` is false, and the text holds neither `{{` nor `}}`.

`resolve_location` routes an anchor matching `VT_ANCHOR` to `eligible_spans(...,
capture_ref_id=<capture>)` and passes only if the anchor's offsets and hash are among the results.
A `None` source cutoff (no row: pre-migration, or no explicit or inherited cutoff) resolves
nothing. The first-party
PDF branch is unchanged. `SOURCE_QUOTE` resolution is not touched; a vendor capture stays
unresolvable as a claim citation. `ResolvedCitation.admission_label` stays `None` for
non-admission references. The global `scan_section` rules are not changed.

Verification, each on one retained span:
- the bound span resolves;
- it fails for another issuer's feed item, for a span crossing two feed items, and when the
  issuer's company link is missing or ambiguous;
- capture registered after S fails, including S < registration ≤ K;
- an extraction or claim recorded after K fails; a binding recorded after K fails;
- a newer `EMPTY` extraction hides older spans; a `NAME` row at the same offsets fails;
- offsets shifted by one, out of range, or a different hash fail;
- after licence end (tombstoned text) it fails; a monkeypatched reader that moves the slice fails;
- `has_numeral` unit cases: a digit, a non-ASCII numeral, a number word, a date and a period label
  are numerals; plain prose is not.

The cutoff row (`pg`):
- inserting a first row for an existing version in a later transaction fails, sealed or not;
  update, delete and truncate fail; S > K fails;
- a version with no row resolves nothing, and every sealed digest recorded before the migration
  still verifies;
- narration of a version with S1 stores S1; a fresh same-period successor with S2 ≠ S1 stores S2
  and resolves against S2 at drafting, checking and sealing; a draft with no cutoff whose
  predecessor has S1 stores S1; one with neither stores no row.

A `NumericClaim` whose `SOURCE_QUOTE` names the span's capture checks `UNRESOLVED`; the same claim
citing an admitted fact id checks `MATCH`, with Task 9's label and witnesses. If the store refuses
inserting a vendor `SOURCE_QUOTE`, the refusal is asserted in memory through `check_claim`. Phase
1's admitted-fact path and the existing location tests pass unchanged.

Dependencies: Task 3. Phase 1 Task 9 must have landed (`citations.py`, `lifecycle.py`).

Risks: binding is the one authority decision; test-first on the refusal cases. If the retained
feed has no item of another held issuer, the fixture adds a second entity whose binding holds that
item's slug.

## Task 5: The vendor summary block

Goal: A sealed report shows every eligible span in a block headed with vendor, surface and capture
date and marked `vendor summary — guidance, not evidence`. A numeral span is absent, and a revised
draft that adds one cannot seal.

Files:
- Create: `equity_os/publication/drafting/vendor_summary.py`
- Modify: `run_draft.py`, `rework.py`
- Test: `test_data_stage2_e2e.py`

Interfaces:
- Consumes: `eligible_spans`, `VT_ANCHOR` (Task 4).
- Produces:
  - `VENDOR_SUMMARY = "vendor_summary"`;
  - `vendor_summary_section(cursor, *, entity_id, source_cutoff, knowledge_cutoff, snapshots)
    -> tuple[str, str] | None`, the section key and body, or `None` with no spans.

Approach: §7 "Numerals". From `eligible_spans` (no second filter), for each (vendor, surface,
capture date):
- one Markdown heading, e.g. `### Screener — concall-summary, captured 2026-11-07 — vendor
  summary — guidance, not evidence`;
- one `{{e:inferred}}` paragraph per span with its location marker.

With no spans the section is omitted. `write_run_draft` adds the section when present and sets
`VersionDraft.source_cutoff = update.source_cutoff`.

Rework (R2-01): the section is regenerated on every run, so it is neither a carried line nor a
preserved scaffold. `rework.py:255` excludes `VENDOR_SUMMARY` alongside `DERIVED | DISCLOSED |
NARRATIVE`, which keeps it out of `Rework.scaffolds` and `Rework.lines`; `Gate.close` therefore
never calls `section_body` for it. No other section's scaffold check changes. After Task 9 lands, remeasure `run_draft.py`
and move one coherent, self-contained part of it into a new module so it ends at ≤ 800 lines; no
line folding and no unrelated refactor.

Verification: the Stage 2 end-to-end, through `main(["run", ..., "--compare-run", id])` to the
seal, with Task 3's retained concall capture and scripted spans (one numeral-free, one with a
digit, one with a number word, one with a date or period label, one holding a valid existing
`{{c:…}}` key):
- the sealed body holds the first span under its heading, and none of the others;
- the draft validates `AS_KNOWN`;
- claim rework: rejecting an ordinary results claim and rerunning through the normal rework path
  regenerates the same vendor section and reaches checking and sealing;
- a revision that adds the number-word span, the date span or the `{{c:…}}` span with its valid
  marker fails checking and sealing with the vendor citation refusal, not a rework error;
- a report for another issuer has no vendor section and seals.

Dependencies: Task 4. Phase 1 Task 9 must have landed (`run_draft.py`, the Stage 2 e2e).

Risks: summaries may be mostly numerals, leaving the block mostly empty. Task 3's counts show
this; nothing is tuned to raise them.

## Task 6: Gate

Goal: The implementation tip passes the integrated gate.

Approach: on the tip holding Tasks 1 and 3–5, run `scripts/verify.sh gate vendor-1-p2` as a
`systemd-run --user` unit. Save its log and the revision in `scratchpad/vendor-first/gate-2/`. A
fix round that touches gated code re-runs the gate.

Verification: exit 0, mypy strict and ruff clean, `run_draft.py` ≤ 800 lines.

Dependencies: Tasks 1–5.

**Then: the Sol phase-end review.** It covers the phase diff, the Task 2 live logs and structure
record, the Task 3 counts, the gate log, and each reading as applied. It runs the review loop,
then one fresh closing review. After `APPROVE`:
- refresh `docs/status/dashboard.html`;
- record the verdict on `eqos-awnc`, stating Screener completion and Tijori deferred;
- file beads for: the Tijori text route (reading 2), the pointer consumer (reading 6), status
  notes for expired spans (reading 8), and the summary licence (spec §11).

## Dependency order and parallelism

1 → 2 → 3 → 4 → 5 → 6 → review, strictly serial, so no two Phase 2 tasks write a file at once.
- Tasks 1–3 share no file with in-flight Phase 1 work. Task 1 edits `sources.yaml`, which Phase 1
  Task 11 also edited; Task 11 is on main, so there is no active writer conflict.
- Tasks 4 and 5 start only after Phase 1 Task 9 lands (`citations.py`, `lifecycle.py`,
  `run_draft.py`, the Stage 2 e2e).
- Task 2 and Phase 1 Tasks 13–14 run serially (live protocol, serial ownership).

## Interactions with Phase 1

- **From Task 9:** the final `resolve_location` signature (Task 4 adds `source_cutoff`), the
  `lifecycle.py` call sites, `write_run_draft`'s `derived_sections` line, and the Stage 2 e2e
  fixture. Task 10 (`compare fallback`) has landed and is not touched.
- **No label on the vendor block.** It has no `NumericClaim` rows; Task 9's rule covers
  required-role numeric claims, not every section. The guidance marking is not an admission label,
  and `ResolvedCitation.admission_label` stays `None` for non-admission references.
- Phase 1's `status_note` covers admitted numbers; reading 8's deferral is compatible.

## Self-review

- **Spec coverage.**
  - Readers by site → T1–T3 (Screener; Tijori deferred by the §7 amendment).
  - Bound to the report → T4 (`vendor_ids`, two clocks).
  - Resolvable reference → T4.
  - Never a number source → T3 (interpretations and occurrences) and T4 (claim refusal).
  - Numerals → T4 (report-use rule) and T5 (render); the pointer handoff → reading 6.
- **Acceptance (as amended).**
  - The supported Screener readers, including concall summary, produce validated spans → T3.
  - Another issuer, or captured after S, or known after K, refused → T4.
  - Altered offsets fail → T4.
  - Numeric claim refused, then passes with a fact id → T4.
  - A numeral span absent from the render and unsealable on revision → T5.
  - No interpretation on a text capture → T3.
  - Gate → T6.
- **Names.** `read_text`, `ReaderText`, `TextItem` (T3) → T4. `has_numeral`, `eligible_spans`,
  `vendor_ids`, `VT_ANCHOR` (T4) → T5.
- **Gaps named.** Concall grounding (Task 2 exit); Tijori (reading 2); the pointer consumer
  (reading 6); expiry after sealing (reading 8); licence (spec §11). The store was not queried.
