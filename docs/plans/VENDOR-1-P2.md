# VENDOR-1 Phase 2 Implementation Plan

**Status:** draft for Sol plan review. **Bead:** `eqos-awnc`.
**Origin:** `docs/specs/2026-11-06-vendor-first.md` §7, approved by gpt-6.1-sol in round 3 on
2026-11-06. §1–§4 give the owner's order and defaults. Code facts were read at `19545c8e`. Retained
page formats come from `data/raw/vendor-surface/2026-10-28/` and `data/raw/snapshots/v1/`, read for
structure only. The store was **not queried** for this plan; read-only authentication failed, so
no store fact below is established.
**Goal:** Screener and Tijori summary text appears in a report as cited, issuer-bound vendor text.
It is never a number source, and a span holding a numeral is never shown.

**Out of scope:** numbers (Phase 1); banks (Phase 3); the five-company test (§9). Also out:
building the document-extraction model that numeral spans point to (reading 6), and status notes
for cited spans whose capture later expires (reading 8). Any Tijori text reader is out until a
retained capture carries Tijori summary text (reading 2).

**Constraints:**
- Readers are code, because the vendor page formats are fixed. A model only selects span offsets,
  as `extract_text` does today, and code validates and binds every span (CLAUDE.md, Data
  Extraction).
- `vendor_text_claims` never produce occurrences, interpretations or claim values.
- No vendor body, span text or summary wording goes into committed text, logs, test files or
  reports. Tests address retained captures by their coordinates, as `test_vendor_retained.py` does.
- Never open `stage4_holdout.yaml`, `stage4_manifest.yaml`, `data/holdout/` or
  `data/raw/onboarding/`.
- Files stay under 800 lines. `run_draft.py` is already at 808, so Phase 2 changes it by net zero
  lines. New logic goes into new modules.
- Tests follow `.claude/rules/python/testing.md`: feature and end-to-end tests through public
  paths first. Unit tests are only for the numeral rule and span binding.
- Live writes are permanent. Task 2 follows the live protocol below.

**Shape:** Tasks 1 and 3–5 are code, one commit each, verified by the orchestrator. Task 2 is the
phase's only live write: it captures Apar's Screener concall summaries. Task 6 is the gate.
**Sol reviews this plan, then once at phase end**, using the loop in
`.claude/rules/core/04-agent-stack.md` and closing with one fresh critical review.

**Estimate:** about 21 hours summed, the author's estimate, not measured.

| Task | Implementer | Hours |
|---|---|---|
| 1. Screener concall-summary capture surface | Sonnet | 2.5 |
| 2. Live: capture Apar's concall summaries | orchestrator | 2 |
| 3. Readers keyed by (site, surface) | Opus | 4 |
| 4. Span binding and citation | Opus | 4 |
| 5. Numeral rule and the vendor summary block | Opus | 3.5 |
| 6. Gate | orchestrator | 1.5 |
| Sol phase-end loop, closing review, close-out | — | 3.5 |

## What the code shows (read before the readings)

1. **Tijori `concall-monitor` has no text.** The spec calls it a market page that carries many
   issuers. Both retained captures, the 2026-10-28 crawl reference and the snapshot
   `vs.concall-monitor` of 2026-10-30, are the same landing page. It has no table, no data island
   and no issuer markup, only a promotional panel linking to an external product. Several places
   in the repo already say so:
   - `tijori_events_models.py` has `CONCALL_NOT_STATIC_REASON` (dated 2026-08-25) and
     `NOT_STATIC_SURFACES`;
   - `surfaces.yaml` gives the surface `group: NONE`;
   - `docs/research/vendor-surface/catalog.yaml` says "Landing page only; summaries are AI".

   The summaries come from `/results/concall-summaries/api/`, which returned 404 and is
   deny-listed. The company overview's `concall_summary` modal is an empty shell in the retained
   Apar capture.
2. **The Screener concall notes are not on the company page.** Each row of the page's `#documents`
   concalls list carries a "Notes" button pointing at `/concalls/summary/{id}/`. That route is an
   AI summary, excluded by `vendor_surface_fetch.NAMED_PATHS` (enforced by `is_denied`), by
   `runbook.md` §1 and by `not-capturable.md`. It has never been captured.
3. **Span offsets index the reader's normalised text, not the capture bytes.**
   `source_text` joins xpath text nodes with single spaces, and `validate_spans` checks offsets
   against that string.
4. **Ledger claims are all `NumericClaim`.** Prose cites a capture only through a location marker
   `{{s:<capture>|<anchor>}}`, which `resolve_location` resolves (first-party PDF only). A
   `SOURCE_QUOTE` citation of a vendor capture already resolves to `None` through
   `_first_party_capture`, so a numeric claim citing only a span is already `UNRESOLVED`.
5. **`extract_text` already writes only `vendor_text_claims` and `vendor_outcomes`.** No code
   reads `vendor_text_claims` apart from backup and restore checks.
6. **No document-extraction model exists.** The only guidance extractor,
   `guidance_extractor.py`, is rule-based.

## Readings (open questions; recommended reading for Sol to rule)

1. **The Screener concall-notes source.** The notes exist only at the deny-listed AI route. The
   owner order of 2026-11-05 ("Screener and Tijori are the main sources for numbers and processed
   text") postdates the crawl brief's AI exclusion of 2026-10-28, and §7, approved by Sol, names
   this reader.

   Recommended reading: lift the exclusion for `/concalls/summary/{id}/` only. It stays GET-only
   and is reached only through the company page's own buttons, and every other runbook rule
   stands. Tijori's AI route and Screener's `/annual-reports/{id}/summary/` stay denied. The
   licence question in spec §11 stays open. If Sol or the owner rules the exclusion stands, drop
   Tasks 1–2 and the concall reader; Phase 2 then ships with the three existing Screener readers.
2. **The Tijori reader.** No retained capture carries Tijori summary text, and no verified route
   serves any. Recommended reading: build no Tijori reader in Phase 2, since code written against
   a format nobody has seen is a guess. Acceptance "both readers produce validated spans" then
   passes for Screener only. The Tijori half is parked with that reason, and a bead is filed to
   find a Tijori text route under the runbook. This needs Sol's ruling, as an amendment to §7. The
   `(site, surface)` key still lands, so the Tijori reader is one table entry when the evidence
   exists.
3. **Offsets and the capture hash.** Recommended reading:
   - offsets index the reader's text for that `(site, surface)`;
   - resolution re-runs the reader on the retained body and requires the slice to equal the stored
     span `text`;
   - the capture hash is `capture_refs.blob_sha256`.

   A reader change that moves text therefore fails closed, so no reader version is needed. A
   licence-end tombstone (text `NULL`) fails it too.
4. **The company reference.** Recommended reading:
   - a company-scope page binds by its own identity element (`read_identity`, as
     `screener_documents` does), compared with the entity's held `SCREENER_COMPANY_ID` at the
     cutoff date (`identity_layers.latest_slice`);
   - `company-announcements` is an XHR fragment with no identity element, so it binds by the
     company id in its captured request path;
   - a market page (`announcements-feed`) binds per item, by the item's own `/company/<slug>/`
     link against the held `SCREENER_SLUG`, and a span must lie wholly inside one bound item;
   - the concall summary binds by its own identity markup if Task 2 finds one. Otherwise it binds
     by the request path's company id, if the address carries one. Otherwise it refuses. Parent
     lineage never binds.
5. **What counts as a numeral.** "Any numeral (per `numeral_scan.py`)": any Unicode numeric
   character, or a match of `numeral_scan`'s number-word lexicon. Dates and period labels are not
   exempt here, since a vendor's "Q2" or date is itself an unverified vendor fact.
6. **The extraction pointer.** Recommended reading: no new code. The privately stored
   `vendor_text_claims` row is the pointer. Its consumer, the document-extraction model, does not
   exist (see "What the code shows", item 6). A bead is filed for when that model is built.
7. **Which spans render.** Recommended reading: `CLAIM` spans only, never `NAME`, taken from:
   - the latest capture per `(site, surface, request_key)` registered by the report's source
     cutoff;
   - that capture's latest completed extraction (`OK` or `PARTIAL` outcome).

   Spans with the same text are shown once. There is one block per (vendor, surface, capture
   date). Resolution keeps `resolve_location`'s contract: the version's knowledge cutoff, which is
   never earlier than the source cutoff. The block does not claim that a summary belongs to the
   report's quarter. Its heading says what was captured and when.
8. **Expiry of a cited span after sealing.** The spec is silent. The sealed bytes never change, and
   a later re-check reports the location unresolved. Recommended reading: no status note in
   Phase 2, with a bead filed. Phase 1's `status_note` covers admitted numbers only.

## File map

| Path | Change | Responsibility |
|---|---|---|
| `equity_os/sourcing/surfaces/vendor_surface_fetch.py` | modify | drop `/concalls/summary/` from `NAMED_PATHS` |
| `config/sourcing/vendor_surface/surfaces.yaml`, `config/sourcing/sources.yaml` | modify | `concall-summary` surface and its capture-spec entry |
| `equity_os/sourcing/surfaces/vendor_surface_expand.py` | modify | `screener_concall_summaries` expansion from `company-page` |
| `docs/research/vendor-surface/runbook.md`, `not-capturable.md` | modify | the narrowed AI-route line |
| `equity_os/extraction/surfaces/vendor_text_readers.py` | create | `READERS`, `ReaderText`, `TextItem`, the four Screener readers |
| `equity_os/extraction/model/vendor_surface_claims.py` | modify | `SURFACES` and `source_text` move out; the query keys on (site, surface) |
| `equity_os/publication/checking/vendor_text.py` | create | `VT_ANCHOR`, `bound_span`, `issuer_spans` |
| `equity_os/publication/checking/citations.py` | modify | `resolve_location` vendor-text branch |
| `equity_os/publication/checking/numeral_scan.py` | modify | `has_numeral` |
| `equity_os/publication/drafting/vendor_summary.py` | create | the vendor summary section |
| `equity_os/publication/drafting/run_draft.py` | modify (net zero) | add the section to `derived_sections` |
| `tests/equity_os/sourcing/surfaces/test_vendor_surface_fetch.py` | modify | concall summary allowed; other AI routes denied |
| `tests/equity_os/extraction/model/test_vendor_surface_claims.py` | modify | readers, keyed query, retained captures |
| `tests/equity_os/publication/checking/test_vendor_text_citation.py` | create | binding, resolution, numeric-claim refusal (`pg`) |
| `tests/equity_os/interface/workflows/test_data_stage2_e2e.py` | modify | the rendered block through the real report path |

## Task 1: Screener concall-summary capture surface

Goal: `eqos vendor capture --symbol <S> --surface concall-summary` fetches exactly the
`/concalls/summary/{id}/` addresses advertised by that issuer's retained company page. Every other
AI route stays denied.

Files:
- Modify: `vendor_surface_fetch.py`, `surfaces.yaml`, `sources.yaml` (Screener `capture_specs`),
  `vendor_surface_expand.py`, `runbook.md`, `not-capturable.md`
- Test: `test_vendor_surface_fetch.py`, plus one replay case in
  `tests/equity_os/sourcing/surfaces/test_vendor_surface_company.py`

Interfaces:
- Produces:
  - surface `concall-summary` (`site: screener-subscriber`, `scope: COMPANY`,
    `path: /concalls/summary/{concall_id}/`, `group: NONE`, `cadence: AFTER_RESULTS`,
    `expand: screener_concall_summaries`);
  - `parent_surface` maps it to `company-page`;
  - `EXPANSIONS["screener_concall_summaries"]`, one `child(spec, context, concall_id=...)` per
    distinct advertised id.

Approach: Reading 1. Remove only the `/concalls/summary/` entry. `/results/concall-summaries/`
and the `/annual-reports/` summary rule stay. The expansion reads the button addresses from the
`#documents` concalls rows of the parent page, which `read_identity` has already verified. It
fetches nothing else. Edit the runbook and not-capturable lines to say what is now captured and
why (VENDOR-1 §7, owner order 2026-11-05).

Verification:
- `is_denied` is false for `/concalls/summary/1/` and still true for `/results/concall-summaries/`
  and `/annual-reports/1/summary/`.
- Replay over Apar's retained company page yields one request per distinct Notes button, with
  none from another page.
- `test_screener_documents.py` and the vendor-surface suites pass unchanged.

Dependencies: None. Phase 1 already landed the `sources.yaml` header line.

Risks: the route may need XHR headers that the gateway does not send. Task 2 finds out, and a
refused fetch is recorded, not worked around.

## Live protocol (Task 2)

Phase 1's live protocol (`docs/plans/VENDOR-1-P1.md`, steps 1–6) applies verbatim, with these
changes:
- The rehearsal fetches into a scratch `--snapshot-root` against the restored copy. The live run
  fetches again into `data/raw/snapshots/v1`.
- Deltas compare tables, row counts and outcome codes. They do not compare bodies or hashes,
  since two fetches can differ.
- Calls stay under the runbook's 350 per site, rehearsal and live together.
- Task 2 never runs while Phase 1 Tasks 13–14 are live; step 5's drift check would stop either
  task.

## Task 2: Live: capture Apar's concall summaries

Goal: The store retains Apar's Screener concall summaries. The plan's open format facts are
recorded from those captures, as structure only.

Files: none committed. Logs, capture coordinates and the structure notes go in
`scratchpad/vendor-first/p2-ground/`.

Commands, from the main checkout on Task 1's tip:
`eqos vendor capture --symbol APARINDS --surface concall-summary`. Allowed changes:
`capture_refs`, `vendor_outcomes`, capture attempts and the blobs.

Record, from the retained bodies and as structure only:
- the summary region's xpath;
- whether the page carries an identity element, a company link or neither (reading 4);
- whether its text is list items or prose;
- the count of items holding a numeral (reading 5).

Before Task 2, Task 1's suites, mypy and ruff pass, and `eqos db check-live` is clean.

Verification:
- the live protocol passes;
- every advertised summary is `RETAINED` or has a recorded refusal outcome;
- no other surface or issuer was fetched, as the fetch log shows.

Dependencies: Task 1.

Risks: permanent, outward-facing reads of the vendor. If every fetch is refused, Phase 2 falls back
to reading 1's alternative and the result goes to the phase review.

## Task 3: Readers keyed by (site, surface)

Goal: Every supported `(site, surface)` has a code reader that returns its normalised text with
each item's range and company reference. `extract_text` processes exactly those surfaces. The
three existing readers return byte-identical text.

Files:
- Create: `equity_os/extraction/surfaces/vendor_text_readers.py`
- Modify: `vendor_surface_claims.py`
- Test: `test_vendor_surface_claims.py` (`retained`, `pg`)

Interfaces:
- Consumes: Task 2's capture coordinates and structure notes.
- Produces:
  - `TextItem(start: int, end: int, company: CompanyRef)`;
  - `CompanyRef(namespace: IdentifierNamespace, value: str)`;
  - `ReaderText(text: str, items: tuple[TextItem, ...])`;
  - `READERS: Mapping[tuple[Site, str], Callable[[bytes, CaptureReference], ReaderText]]` for
    Screener `company-page`, `company-announcements`, `announcements-feed` and `concall-summary`;
  - `read_text(site, surface, body, ref) -> ReaderText`, which raises `ValueError` for an
    unsupported pair.

Approach: §7 "Readers by site", with reading 4 for each reader's company reference. The text is
built exactly as `source_text` builds it today, so stored offsets stay valid. Items record where
each item's parts land in the joined string.
- A company page is one item with the page's identity.
- An announcements fragment is one item with the request path's company id.
- The feed has one item per `announcement-item`, with its `/company/<slug>/` link.
- A concall summary is one item with its reference per Task 2. With no reference, its reader
  yields no items, so its spans can never bind.

`extract_text` selects captures by `(source_id, surface)` pairs from `READERS` and calls
`read_text(...).text` in place of `source_text`. Its model step, prompt and outcome identity are
unchanged. A reader with empty text records an `EMPTY` outcome without a model call.

Verification:
- On the retained Apar captures, each existing reader's text has the same sha256 as
  `source_text` gives before the change. This is the characterization; record the digests first.
- The concall reader returns non-empty text from Task 2's captures, with items covering it.
- With a scripted model reply over that text, `extract_text` stores validated spans for the
  concall capture.
- Afterwards, `SELECT count(*) FROM eqos.interpretations WHERE capture_ref_id IN (SELECT
  capture_ref_id FROM eqos.vendor_text_claims)` is 0 (acceptance: never a number source).
- The test prints item counts and numeral-free item counts per surface, as counts only, for the
  phase review.

Dependencies: Task 2.

Risks: characterization first. A whitespace change in the join would silently invalidate every
stored span; the digest test catches it.

## Task 4: Span binding and citation

Goal: A prose location marker naming a vendor span resolves only when:
- the span is a stored span of a retained, unexpired capture;
- its offsets re-read to the stored text;
- the capture hash matches;
- the capture was registered by the cutoff;
- the span lies inside an item bound to the report's issuer.

A numeric claim citing only a span is refused, and the same claim citing a fact id passes.

Files:
- Create: `equity_os/publication/checking/vendor_text.py`
- Modify: `citations.py` (`resolve_location` only)
- Test: `tests/equity_os/publication/checking/test_vendor_text_citation.py` (`pg`, retained
  captures)

Interfaces:
- Consumes: `read_text`, `ReaderText`, `TextItem` (Task 3); `latest_slice` (identity layers);
  `retained_capture`.
- Produces:
  - `VT_ANCHOR`, the anchor grammar `vt:<start>-<end>:<blob_sha256>` (no `|` or `}`);
  - `bound_span(cursor, capture_ref_id: int, start: int, end: int, sha256: str, *,
    entity_id: int, cutoff: datetime, snapshots: SnapshotStore) -> str | None`;
  - `issuer_spans(cursor, *, entity_id, cutoff, snapshots) -> tuple[IssuerSpan, ...]` with
    `IssuerSpan(capture_ref_id, site, surface, registered_at, start, end, sha256, text)`, the
    reading-7 selection with every span passed through `bound_span`.

Approach: §7 "Bound to the report" and "Resolvable reference", readings 3, 4 and 7. `bound_span`
is the only gate, and the drafting path (Task 5) and resolution share it. It requires all of:
- a `vendor_text_claims` row with exactly those offsets on that capture, with non-null text;
- the capture in `RETAINED` or `RESTORED` state;
- `registered_at` at or before `cutoff`;
- `blob_sha256` equal to `sha256`;
- the re-read slice equal to the stored text;
- one item containing `[start, end)` whose reference matches the entity's held identifier in
  that namespace at the cutoff date.

`resolve_location` routes an anchor matching `VT_ANCHOR` to `bound_span`, and passes when the
result is non-empty. The first-party PDF branch is unchanged. `SOURCE_QUOTE` resolution is not
touched: a vendor capture stays unresolvable as a claim citation, which is how a numeric claim
citing a span is refused. No new claim-check code.

Verification, with each case on one retained span:
- the bound span resolves;
- it fails for another issuer's item on the feed;
- it fails when registered after the cutoff;
- it fails with offsets shifted by one;
- it fails with a different hash;
- it fails after the capture's licence end (the tombstoned text);
- it fails when the reader output changes (a monkeypatched reader).

A `NumericClaim` whose `SOURCE_QUOTE` citation names the span's capture checks `UNRESOLVED`. The
same claim citing an admitted fact id checks `MATCH`. The existing location tests pass unchanged.

Dependencies: Task 3. Phase 1 Task 9 must have landed (`citations.py`).

Risks: binding is the one authority decision; test-first on the refusal cases. The market-feed
case needs an item of another held issuer; if the retained feed has none, the fixture adds a
second entity holding that item's slug.

## Task 5: Numeral rule and the vendor summary block

Goal: A sealed report shows every bound, numeral-free `CLAIM` span in a block headed with vendor,
surface and capture date and marked `vendor summary — guidance, not evidence`. A span with a
numeral is absent.

Files:
- Create: `equity_os/publication/drafting/vendor_summary.py`
- Modify: `numeral_scan.py` (`has_numeral`), `run_draft.py` (net zero lines)
- Test: `test_data_stage2_e2e.py` (one case), plus unit cases for `has_numeral` in the existing
  `test_audit_numeral_scan.py`

Interfaces:
- Consumes: `issuer_spans`, `VT_ANCHOR` (Task 4).
- Produces:
  - `has_numeral(text: str) -> bool` (reading 5);
  - `VENDOR_SUMMARY = "vendor_summary"`;
  - `vendor_summary_section(cursor, *, entity_id, cutoff, snapshots) -> tuple[str, str]`, the
    section key and body.

Approach: §7 "Numerals". Starting from `issuer_spans` at the update's source cutoff, the function
keeps `CLAIM` spans where `has_numeral` is false. For each (vendor, surface, capture date) it
writes:
- one heading line, e.g. "Screener — concall-summary, captured 2026-11-07 — vendor summary —
  guidance, not evidence";
- one `{{e:inferred}}` paragraph per span with its location marker.

With no spans, the body is `- none`. In `write_run_draft`, the section joins `derived_sections`.
Fold a line elsewhere so the file stays at 808 lines. The existing `scan_section` then requires
each marker to resolve at seal (Task 4). The heading's date is a structural date, and the markers
are stripped before the numeral search.

Verification: the Stage 2 end-to-end, through `main(["run", ..., "--compare-run", id])` to the
seal, with Task 3's retained concall capture and scripted spans (one numeral-free, one with a
digit, one with a number word):
- the sealed body holds the first span and its heading with the guidance marking, and not the
  other two;
- the draft validates `AS_KNOWN`;
- a report for another issuer shows `- none`.

Unit cases:
- a digit, a non-ASCII numeral, a number word, a date and a period label are all numerals;
- plain prose is not.

Dependencies: Task 4. Phase 1 Task 9 must have landed (`run_draft.py`, the Stage 2 e2e).

Risks: summaries may be mostly numerals, which would leave the block mostly empty. Task 3's counts
show this and go to the phase review; nothing is tuned to raise them.

## Task 6: Gate

Goal: The implementation tip passes the integrated gate.

Approach: on the tip holding Tasks 1 and 3–5, run `scripts/verify.sh gate vendor-1-p2` as a
`systemd-run --user` unit. Save its log and the revision in `scratchpad/vendor-first/gate-2/`. A
fix round that touches gated code re-runs the gate.

Verification: exit 0, mypy strict and ruff clean.

Dependencies: Tasks 1–5.

**Then: the Sol phase-end review.** It covers:
- the phase diff;
- the Task 2 live logs and structure notes;
- the Task 3 counts;
- the gate log;
- each reading as applied.

It runs the review loop, then one fresh closing review. After `APPROVE`:
- refresh `docs/status/dashboard.html`;
- record the verdict on `eqos-awnc`;
- file beads for: the Tijori text route (reading 2), the document-extraction model consuming
  numeral pointers (reading 6), status notes for expired spans (reading 8), and the summary
  licence (spec §11).

## Dependency order and parallelism

1 → 2 → 3 → 4 → 5 → 6 → review.
- Tasks 1–3 touch no Phase 1 file, so they run while Phase 1 Tasks 9–10 are in flight.
- Tasks 4 and 5 start only after Phase 1 Task 9 lands, because they edit `citations.py`,
  `run_draft.py` and the Stage 2 e2e after it.
- Task 2 never overlaps Phase 1's live Tasks 13–14.
- No two Phase 2 tasks share a file.

## Interactions with Phase 1

- **What Phase 2 needs from Task 9:**
  - the final `resolve_location` signature, unchanged in Task 9's plan;
  - `run_draft.write_run_draft`'s `derived_sections` line;
  - the Stage 2 e2e fixture.

  Phase 2 does not use labels, `ResolvedCitation.admission_label` or `status_note`.
- **No label on the vendor block.** The block carries no `AdmissionLabel`, so Task 9's rule "a
  required-role claim without a label qualifier fails the render" is unaffected: the block has no
  claims. If Task 9 instead makes every rendered section require a label, the block's
  guidance marking is its label, and Task 9 must exempt sections without claims.
- Task 10 (fallback) and the eligibility and admission paths are not touched.

## Self-review

- **Spec coverage.**
  - Readers by site → T3 (T1–T2 for the concall source; Tijori per reading 2).
  - Bound to the report → T4.
  - Resolvable reference → T4.
  - Never a number source → T3 (interpretations query) and T4 (claim refusal).
  - Numerals → T5 (pointer per reading 6).
- **Acceptance.**
  - Readers produce validated spans → T3, Screener only (reading 2).
  - Another issuer or post-cutoff refused → T4.
  - Altered offsets fail → T4.
  - Numeric claim refused, then passes with a fact id → T4.
  - A numeral span absent from the render → T5.
  - No interpretation on a text capture → T3.
  - Gate → T6.
- **Names.** `read_text`, `ReaderText`, `TextItem` (T3) → T4. `bound_span`, `issuer_spans`,
  `VT_ANCHOR` (T4) → T5.
- **Gaps named.** The concall source (reading 1); Tijori (reading 2); offsets (3); binding (4);
  numerals (5); the pointer consumer (6); selection and cutoff (7); expiry after sealing (8);
  licence (spec §11, unchanged). The store was not queried.
