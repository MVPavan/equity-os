# Report ledger, long-term memory, coverage model and data lifecycle

Status: approved
Approved by: approval panel (gpt-6.1-sol high + claude-fable-5-1 high, blind, both APPROVE), 2026-10-12, under the owner autonomy directive
Builds on: [canonical financial data and cross-source comparison](2026-10-11-canonical-financial-data-and-cross-source-comparison.md)
(the "data spec"); same PostgreSQL database, roles and integrity rules (data spec §6). Amends
the data spec's retention and replay assumptions (§6 below).

*Amendment 2026-10-15 (`eqos-uqu.10`, owner directive 2026-10-12): the approval panel is a single
model reviewer; its verdict decides, and the owner may override. Withdrawn: two blind reviewers of
distinct model families, the adjudicator, and `ESCALATE` on disagreement (with the `ESCALATE` kind
and `ESCALATED` status, which had no other source). The reviewer's provider and model are data on
its panel review row (amendment 8). Changed: Solution, O10, §1 entities, rules and lifecycle, §2
decision kinds and lifecycle, §6 item 11, Success Criteria Stage 1. Also (D3 plan G8, G9): the
Display style list gains `trim`, and an owner `SET_POLICY` decision takes the report as subject.
Also (D3 plan, critical review): interpretation decisions are owner-only until follow-up F2
adds panel acceptance with deterministic-provenance replay (a revision cause is descriptive, not
proof that code produced the value); nothing consumes interpretation approvals before F2.
Also (D4 plan amendments A1, A2, C2, C3, R, M9; 2026-10-15, approved by Sol): §2 support predicate and
`RETIRE`, `MemoryStore` operations, memory item fields, the `LESSON` exception, and the quote
guidance-contract binding.*

## Problem Statement

Reports, approvals, the management ledger and the thesis are loose files whose numbers cite
source files by hash, not stored figures. Nothing learned persists between quarters. Nothing
records which stocks exist, are worth capturing, or are covered. The data spec keeps every
capture forever: at full-market scope, thousands of unread originals.

## Solution

PostgreSQL holds two append-only stores next to the data spec's evidence schema:

- **Report ledger:** report versions, Markdown sections, one typed row per numeric claim linked
  to the stored figure it cites, validations, and every decision with its ruling and sealed digest.
- **Long-term memory:** short statements per stock (or cross-stock) with a kind, validity interval
  and status `CANDIDATE → PROMOTED → RETIRED`, linked to supporting claims and versions, full-text
  searchable, reached only through the D-01 `MemoryStore` interface.

Report approval and memory promotion are separate decisions by an **approval panel** (a
single model reviewer) after deterministic checks; the owner may override any. Humans read
generated views (O5); views never flow back.

Coverage is three nested sets: a **universe registry** of all ~5,000 Indian listed stocks
(identity only); owner-**screen**ed stocks, captured on demand; and an owner-chosen
**watchlist** (~50–200), the only stocks with reports. A **retention policy** keeps filing
figures, reports, approvals, memory, comparison runs and outcomes and covered exchange originals forever;
vendor pages and readings keep a finite window ([terms](../research/vendor-terms-screener-tijori-2026-10.md));
other originals expire under hash-checked, crash-safe rules.

## User Stories

As the analyst, I want:

1. every report version, its sections and its approval ruling kept forever and diffable;
2. every number in a report checked against the stored figure it cites before it is approved;
3. report approval never to change long-term memory silently; memory is promoted separately;
4. to ask "what do we know about Apar's cable margins" and get promoted statements with their
   supporting claims, as of a chosen date;
5. management promises tracked against delivery across quarters;
6. to read reports and memory in Markdown or Obsidian without touching the database;
7. to export my own Screener screen and capture and compare only the stocks that pass;
8. to choose the watchlist myself; nothing outside it gets a report.

As the operator, I want:

9. storage to grow with coverage, not the market; deletions recorded, re-downloadable where possible;
10. to know what replays after a deletion.

## Implementation Decisions

### Owner decisions recorded in this spec (2026-10-12, PavanMV)

| # | Decision | Applied in |
|---|---|---|
| O1 | PostgreSQL is both the report ledger and long-term memory; append-only; JSONB only for small variable-shape extras | §1, §2 |
| O2 | Report approval and memory promotion are separate decisions | §1, §2 |
| O3 | Memory full-text search is built-in PostgreSQL search; vector search only on measured need | §2 |
| O4 | Memory sits behind the D-01 `MemoryStore` interface so the GBrain benchmark (D-02, D-05) stays possible | §2 |
| O5 | Human views are generated, never stored as authority: Markdown export, optional one-way read-only Obsidian vault, optional read-only dashboard (tool deferred) | §3 |
| O6 | Universe registry of all listed stocks, refreshable from the Upstox instrument list, identity use only | §4 |
| O7 | Capture is on demand from an owner-chosen screen; never a whole-market sync | §4 |
| O8 | Reports only for an owner-chosen watchlist (~50–200) | §4 |
| O9 | Retention: filing figures, reports, approvals, memory, comparison outcomes forever; covered-stock exchange originals forever; other results PDFs/XBRL deleted one quarter after verification (address + hash kept; re-fetch must hash-match); vendor pages and readings 4 quarters plus open-review holds, never extended by coverage, purged at licence end. Its clause "old comparison runs dropped unless cited" is withdrawn (2026-10-12): on-demand results are kilobytes | §5, §6 |
| O10 | Report versions, theses, memory decisions and review-queue items are decided by the approval panel (one reviewer's verdict; amended 2026-10-15); interpretations are owner-decided until F2 (amended 2026-10-15); the owner is never waited on and keeps override/withdraw, watchlist, screens and financial decisions | §1, §2, §6 |

Decided defaults (adopted 2026-10-12):

| # | Default | Applied in |
|---|---|---|
| P1 | Report and memory status is derived from the decision log, never a mutable column | §1, §2 |
| P2 | Report content hash = SHA-256 of the deterministic **narrative** rendering (sections with placeholders filled; no status); the export reproduces those bytes | §1, §3 |
| P3 | "Covered stock" = on the watchlist at capture time, or later added; covered originals exclude vendor material (O9) | §5 |
| P4 | "One quarter after verification" = three calendar months after the verification time | §5 |
| P5 | Purges run only on an explicit command (the orchestrator may run it) with a dry-run report; never scheduled | §5 |

### Decision-register amendments (scope stated exactly)

Against decision register v2. The amendment record citing this spec is part of Stage 1 (items
3, 5, 7, 8), Stage 4 (item 1) and Stage 5 (items 2, 6):

1. **§G "full company initiation as an automated product"** — clarified, not lifted. Screen-driven
   capture is not initiation (the owner chooses the screen and launches each batch; no report is
   drafted). The amendment permits **assisted, approval-gated initiation for owner-chosen
   watchlist stocks**: a first report is a bootstrap thesis (as A-11), agent-drafted and
   panel-approved (§1), owner override kept. Still deferred: system-chosen coverage, unapproved
   initiation, full-universe daily research.
2. **C-16** ("evidence package reconstructs exactly") — qualified: an evidence package whose
   exchange originals expired reconstructs by re-fetch with hash match; one whose vendor material
   expired keeps only outcomes and tombstones (§6).
3. **B-03** authority matrix, narrative row only: the approved narrative's authority moves from
   versioned Markdown files to PostgreSQL rows; Markdown is a generated view. Files stay the
   record until this is panel-approved (Stage 1 cutover).
4. Input to **D-03** (deferred): with narrative and metadata in one database, promotion is one
   transaction, so no narrative/SQL split-brain.
5. **§G last bullet** (PostgreSQL before observed need): the data spec's override covers the
   financial data layer only; this extends it to the report ledger and memory (O1).
6. **C-02** ("original files … preserved"): qualified — originals of non-covered stocks and all
   vendor material expire under §5; capture records, addresses, hashes and first-seen times are preserved forever.
7. Input to **D-01**: "deletion" means retirement; memory rows are never physically removed.
8. **Invariant 11** ("human-approved" promotion) and CONTEXT.md ("only the analyst promotes";
   role names, never model names): amended by the owner's 2026-10-12 autonomy directive.
   Promotion stays a separate decision, by the panel or the owner (override kept); panel models
   are configuration per `.claude/rules/core/04-agent-stack.md`, never named here.

Unchanged: the data spec's market-wide capture deferral, §H triggers, GBrain deferrals.

### 0. Staged delivery

| Stage | Delivers | Depends on | Accepted when |
|---|---|---|---|
| 1. Report ledger | Report, version, section, claim, validation, QA-record, decision and panel-review entities; panel and owner commands and roles; claim check; import of the Apar FY26_Q2–FY27_Q1 updates, the Q0 thesis and the management ledger; deterministic narrative export | Data spec Stages 1–2 | Criteria pass vs frozen manifest; panel approves amendments 3, 5, 7, 8 |
| 2. Long-term memory | `MemoryStore` interface and PostgreSQL implementation; memory items, support links, promotion decisions; full-text search; cutoff retrieval; revalidation flags | 1 | Criteria pass |
| 3. Generated views | Markdown export of reports, status notes and memory; read-only role; Obsidian vault export if built | 1, 2 | Criteria pass |
| 4. Coverage model | Universe registry and refresh; screens and screen runs; owner-launched capture batches; watchlist; §G amendment | Data spec Stage 4 | Criteria pass; panel approves amendment 1 |
| 5. Retention and replay | Retention classes, one-off classification of existing captures, transitive holds, eligibility, crash-safe purge, tombstones, store extension, re-fetch with hash check, amended backup/restore | 1, 2, 4 | Criteria pass; panel approves amendments 2, 6 and §6 |

Until Stage 1 passes and amendment 3 is approved, existing files stay the record.

### 1. Report ledger

**Entities** (all append-only: update and delete rejected by trigger; runtime role lacks UPDATE
and DELETE, as data spec §6):

| Entity | Holds |
|---|---|
| Report | Stock (entity id, data spec §3), period, kind (`BOOTSTRAP_THESIS`, `EARNINGS_UPDATE`, later by version). One per stock × period × kind |
| Report version | Report id, number, predecessor id, author (human, or agent run id with model and prompt version), knowledge cutoff, pinned run ids, content hash (P2), created-at |
| Import source | Version id, source path, bytes and SHA-256 of each imported file |
| Report section | Version id, ordinal, section key, Markdown text with placeholders and markers (below), section hash |
| Numeric claim | Version id, section id, claim key; measurement key (metric, entity, period, basis, dimensions, framework); value kind, unit, currency, scale; value, or bounds and horizon for guidance; qualifiers ("plus", "about"); display precision and rounding; epistemic class; citation. No display text |
| Validation | Version id, checker version, run mode, queue-overlay position, pinned-input hash, per-claim and version-level states, result digest, recorded-at |
| QA record | Imported automated gate results (e.g. XBRL↔PDF cross-check). Never a decision |
| Panel review | Provider, model, effort, brief version, reviewed sealed digest, verdict, full rationale text and hash; inserted in its decision's transaction |
| Decision | Subject (report version, memory item, queue item or interpretation; the report for an owner `SET_POLICY` decision, amended 2026-10-15), kind, sequence, predecessor id, sealed digest, validation id (`APPROVE`), panel review id (panel verdicts), original approval hash (`IMPORTED_APPROVAL`), owner's verbatim ruling, decider and recorded-at (set by trigger), decided-on (imports, at stated precision), decision digest |

`EARNINGS_UPDATE` section keys follow the existing artifact.

A `REQUEST_CHANGES` decision on a report version may name rejected claims, which are reworked selectively into v(N+1) (amended 2026-10-18, PREP-5).

**Rules** (enforced by trigger or the decision commands):

- **Numeric coverage:** narrative numbers come only from claims. A numeral in section text
  outside a placeholder blocks submission (`UNREGISTERED_NUMBER`) unless structural: section
  ordinals, list numbering, period labels (e.g. FY26_Q3), dates, footnote markers, parsed
  identifier and provenance fields (version ids, hashes, source-location coordinates, taxonomy
  ids) and registered formula literals (`× 100`). Unregistered analytical numbers still block.
- **Display:** a placeholder `{{c:<claim key>|<style>}}` renders deterministically from the
  claim's typed value, unit, scale, qualifiers, precision and rounding, shaped by a closed-enum
  style: grouping (none, Indian, international), explicit `+`, unit shown/omitted, qualifier
  shown/omitted, range form (`9.5–10%` or `9.5%, 10%`), trailing fractional zeros kept or trimmed
  (`trim`; amended 2026-10-15). Style `quote` (`SOURCE_QUOTE` only)
  renders the verified verbatim quote, exempt from the numeral scan. No free display text; styles
  sit in section text, so the seal covers them.
- **Prose labels and locations** (invariants 7–8, until B-06; at `SUBMIT`, imports exempt):
  each paragraph carries an epistemic-class marker `{{e:<class>}}`; an observed one needs a claim
  placeholder or a resolving `{{s:<capture id>|<anchor>}}`; else `UNLABELLED_PROSE` /
  `UNCITED_PROSE` blocks. This proves presence only; reviewers judge fit.
- **Seal:** a version's content is its row, sections, claims with citations and import sources;
  a memory item's is its row and supports. Content inserts after a version's `SUBMIT` or
  `IMPORT_SEAL`, or an item's first decision, are refused. Sealed digest = SHA-256 over that
  content in key order; `SUBMIT`/`IMPORT_SEAL`/`PROMOTE` carry it and the trigger recomputes it.
  Validations, QA records, panel reviews and decisions are not content and append later.
- **Authorization:** the runtime role (drafting agents) may insert drafts, content,
  validations, memory candidates, `SUBMIT`, and proposed dispositions and interpretations (no
  amounts), nothing else; a proposal is the decision subject, and the data
  spec's disposition and interpretation-approval commands refuse the runtime role. Other decisions come only from the **panel role**
  (`panel` command) or the **owner role** (`decide`, prompting for the verbatim ruling); neither
  credential is in any config the runtime or drafting agents read.
- **Models never author amounts** (invariant 6): the panel only accepts or rejects (`ACCEPT`/`REJECT`) records whose
  amounts come from deterministic code (e.g. a measured difference) or the owner; a panel
  decision supplying an amount (explained amount, `MANUAL_CORRECTION` value) is refused.
- **Approval panel:** the `panel` command first runs the subject's deterministic gates (claim
  check, support eligibility); any failure refuses with no model call. One reviewer (configured)
  reviews the artifact and brief; its verdict decides (amended 2026-10-15). The trigger refuses
  a panel verdict without its own panel review naming the decision's sealed digest. Reviewers
  return verdicts and rationale only. The panel role is refused
  on a subject whose chain holds an owner decision.
- **Decision chain** (as FactStore `canonical_selections`): per subject, unique sequence,
  predecessor id and digest = SHA-256(row fields + predecessor digest); an insert naming a stale
  head is refused; recorded-at is never caller-supplied.

**Citations.** Every numeric claim carries exactly one citation kind. `FIGURE` and
`CALCULATION` cite first-party values only; a vendor figure enters a report only as a
`COMPARISON` difference.

| Kind | Cites | Used for |
|---|---|---|
| `FIGURE` | A fact id or an interpretation id plus the run id that judged it | Reported figures |
| `CALCULATION` | A calculation trace id (data spec §1) | Growth, margins, deltas |
| `SOURCE_QUOTE` | Non-vendor capture id, typed anchor, verbatim quote; guidance contract as the existing ledger entry (metric, bounds, unit, horizon, scope, constant-currency, qualifiers such as "plus" or "about") | Management guidance and other quoted numbers (the data spec's dictionary excludes guidance) |
| `COMPARISON` | A comparison result (run id, measurement key, source pair); the claim holds its delta, never a vendor reading | Stated cross-source gaps (the ~4.5 crore Screener opex gap) |
| `POLICY` | An owner decision holding the value; only an import may self-cite its version's own record | Owner-selected falsifier thresholds (e.g. Q0 F1 11.55) |

Non-numeric claims stay prose in sections until register B-06 freezes the claim schema.

**Times.** First-seen time is the capture registration (for legacy files, the retrieval
manifest), never a time written inside a report. A date-only cutoff ends at 24:00 IST that day.

**Claim check** (dynamic logic; unit-tested row by row). First matching row wins:

| # | Condition | State |
|---|---|---|
| 1 | Citation does not resolve | `UNRESOLVED` |
| 2 | An input time after the cutoff or missing (C-15), per mode (data spec §5). Both: fact and occurrence knowledge and first-seen times, incl. every operand's; quote capture registration; comparison run time. `AS_KNOWN` also: interpretation recorded-at, selection time, policy decision recorded-at. Imported self-cited `POLICY`: none | `POST_CUTOFF` |
| 3 | Value kind, unit, currency or scale differs | `UNIT_MISMATCH` |
| 4 | Measurement key differs | `KEY_MISMATCH` |
| 5 | `FIGURE`/`CALCULATION`/`POLICY`/`COMPARISON`: claim value ≠ cited value (imported self-cited `POLICY`: the parsed source field) at the claim's display precision and rounding mode | `VALUE_MISMATCH` |
| 6 | `SOURCE_QUOTE`: quote not verbatim at the anchor | `QUOTE_NOT_FOUND` |
| 7 | `SOURCE_QUOTE`: the existing guidance gate (`_guidance_quote_holds`, bounds in the quote) fails; qualifiers are not what the quote states; or metric, scope, horizon, unit or constant-currency differ from the citation's guidance contract (compared field by field, not parsed from the quote) | `QUOTE_MEANING_MISMATCH` |
| 8 | Cited cell untrusted (data spec §5) at the validation's overlay position | `MATCH_UNTRUSTED` |
| 9 | Otherwise | `MATCH` |

A drafted quote claim's guidance contract is bound only by deterministic recomputation from the panel `IMPORT_SEAL`-sealed management-ledger source of an import citing the same quote (same capture blob hash, parsed anchor and quote): exactly one distinct contract, or none (fail closed). Contracts for quotes no sealed import covers remain open (bead `eqos-0eu`) (amended 2026-10-15, D4 plan M9/G1).

Each check appends a validation. Approval binds the latest, which must be `AS_KNOWN`, cover the
sealed digest, have no version-level state, and every claim `MATCH` or `MATCH_UNTRUSTED` (listed
in the status note); else it blocks. `RETROSPECTIVE` validations (imports, hindsight) never bind
an approval. A later failing validation never alters an approval; it shows and may prompt `WITHDRAW`.

**Report version lifecycle** (status derived from the decision log, P1):

| From | Decision | To |
|---|---|---|
| — | version created | `DRAFT` |
| — | imported (`IMPORT_SEAL` in the import transaction) | `HISTORICAL`, or `APPROVED` with an `IMPORTED_APPROVAL` (below) |
| `DRAFT` | `SUBMIT` | `IN_REVIEW` |
| `IN_REVIEW` | `APPROVE` (sealed digest and validation as above) | `APPROVED` |
| `IN_REVIEW` | `REQUEST_CHANGES` / `REJECT` | `CHANGES_REQUESTED` / `REJECTED` |
| `APPROVED` / `HISTORICAL` | a descendant approved (every such ancestor) | `SUPERSEDED` |
| `APPROVED` / `SUPERSEDED` | `WITHDRAW` | `WITHDRAWN` |

A correction is always a new version of the **same report** (same stock, period, kind) naming an
earlier version as predecessor; each version has at most one successor, so lineage is acyclic.
The predecessor must be terminal (not `DRAFT`, `IN_REVIEW`) at the successor's
`SUBMIT`; supersession goes to every `APPROVED` or `HISTORICAL` ancestor
(one approved version per report) and commits with the successor's approval. Approving a
report changes no memory item.

**Import** (via the panel command, no model call; sources unchanged; times never backdated):

- Each imported version is sealed by `IMPORT_SEAL` in its import transaction, with its source
  files stored as import sources. The mapping must be lossless or that version's import fails:
  every Markdown-derived section, rendered, equals its byte range in the source file, and every
  YAML field maps to one section or claim with an equal parsed value.
- An `IMPORTED_APPROVAL` needs contemporaneous evidence binding the ruling to bytes (a commit or
  record made with the ruling, holding the files); its **original approval hash** is those files'
  SHA-256s then, apart from the sealed digest; it binds no validation. No evidence, or other bytes
  → `HISTORICAL`. Import validations are `RETROSPECTIVE`; exports call the narrative a representation.
- Earnings updates FY26_Q2–FY27_Q1 import `HISTORICAL` (decided); their `approval_record`
  sections are automated QA gates → QA records, never decisions.
- Q0 thesis: the Markdown and its YAML twin both import; YAML-only content (tagged assumptions,
  open questions, falsifier thresholds as self-cited `POLICY` claims) becomes sections and
  claims. Ruling: decided-on 2026-09-07 (date precision), PavanMV, "accept all"; `APPROVED` only
  if the evidence rule holds (the manifest records which).
- Management ledger: every `history` revision, not only first/latest, becomes a `SOURCE_QUOTE`
  claim on that quarter's version (e.g. FY26_Q3 cables revenue growth 20%, quoted "20%-plus"),
  anchored from the ledger or that quarter's report; none found → `UNRESOLVED`.
- Claims resolve by measurement key and source hash, else `UNRESOLVED`.

### 2. Long-term memory

**Entities:**

| Entity | Holds |
|---|---|
| Memory item | Stock (entity id, or none for cross-stock kinds), kind, statement (short plain text, length-capped), epistemic class, valid-from, valid-to (open allowed), recorded-at (knowledge time for C-15), supersedes-item id, content hash, small JSONB extras (content hash and extras are not stored: the recomputed sealed digest is the content hash and nothing needs extras; amended 2026-10-15, D4 plan C3) |
| Memory support | Item id → numeric claim, report version, definition record (data spec §5), queue disposition, decision, or capture. Every item has ≥1 support, inserted with the item |
| Decision | As §1; kinds `PROMOTE`, `REJECT_CANDIDATE`, `RETIRE` (panel or owner role). Until the real reviewer adapter (F1) ships, `RETIRE` is owner-only; F1 delivers panel retirement (amended 2026-10-15, D4 plan A2) |

**Kinds.** The data spec's definition records and mapping facts are the sole authority for how a
source's number is defined; memory never restates them.

| Kind | Holds | Required support |
|---|---|---|
| `COMPANY_UNDERSTANDING` | Business model, segments, drivers, structure | Approved report version or claim |
| `MANAGEMENT_TRACK_RECORD` | A promise and its delivery outcome (met, missed, modified, withdrawn) | The guidance `SOURCE_QUOTE` claim and the outcome claim |
| `THESIS_AND_WARNING` | Current thesis summary, falsifier and warning states | Approved thesis or update version |
| `SOURCE_QUIRK` | Qualitative source behaviour (publication lag, layout changes); one changing a number's meaning must be a definition record or mapping fact, which the item only points to | Definition record, queue disposition or capture |
| `OWNER_RULING` | Owner research rulings and preferences (not harness rules) | Decision with verbatim ruling |
| `LESSON` | A mistake and its correction | Rejected version, queue disposition or decision |

**Support predicate:** every support meets its kind's requirement: a version in the stated status
(`APPROVED` for "approved"; `SUPERSEDED` fails) whose latest validation is `AS_KNOWN`, covers its
sealed digest, has no version-level state and has every claim `MATCH` (an imported `APPROVED` version only once one exists); a
claim in such a version; an unsuperseded disposition. Checked at staging and in the `PROMOTE` transaction at READ COMMITTED under the queue lock, which every write that can falsify a support (a validation, a withdrawal, a superseding approval, a disposition) also holds from before its first store-clock read; any failure refuses, and a `PROMOTE` at REPEATABLE READ or SERIALIZABLE is refused. It is re-checked when the `PROMOTE` transaction commits, so `PROMOTE` cannot itself falsify a support afterwards; `PROMOTE` must be the last ledger or queue write of its transaction (amended 2026-10-15, D4 plan A1).

**`LESSON` exception:** a `LESSON` may cite a version whose head is `REJECT` as evidence that a mistake occurred, never that version's claims, which stay untrusted (amended 2026-10-15, D4 plan R).

**Lifecycle** (status derived from decisions, P1):

| From | Decision | To |
|---|---|---|
| — | item staged (agent or human) | `CANDIDATE` |
| `CANDIDATE` | `PROMOTE` | `PROMOTED` |
| `CANDIDATE` | `REJECT_CANDIDATE` | `REJECTED` |
| `PROMOTED` | `RETIRE`, or a superseding item promoted (same transaction) | `RETIRED` |

A correction supersedes a `PROMOTED` item of the same stock and kind; its `PROMOTE` refuses
unless that item is still `PROMOTED` and retires it in the same transaction (one promoted
successor at most). Valid-to closes the time a statement describes; retirement closes its standing as
memory (a true historical statement can be valid-to 2026-03-31 and still promoted).

**Revalidation.** A `PROMOTED` item derives `NEEDS_REVALIDATION` when any support fails the
support predicate (e.g. its version superseded or withdrawn). Retrieval at a cutoff derives
statuses, validations, dispositions and flags only from records at or before it, so later events
never leak back. The panel (or owner) re-promotes (a new item) or retires.

**Search.** A generated full-text column over the statement with a GIN index; queries filter by
stock, kind, status and cutoff. Vector search (pgvector) only if the D-02 benchmark measures
misses full-text search causes.

**`MemoryStore` interface (D-01).** Engine-neutral: retrieve (query, stock, kinds, cutoff →
promoted items with supports and flags, as known at cutoff); stage; promote; correct; retire;
export; provenance (item → supports → figures and captures). In D4 these map to `decide` (promote, retire), `stage(supersedes_item_id=…)` (correct) and, for export, D5.1 (amended 2026-10-15, D4 plan C2). PostgreSQL is D-02's
"Git/Markdown/SQL" arm; a GBrain arm implements the same interface. The comparator and report
checks never read memory.

### 3. Generated views

- **Markdown export:** renders each version's narrative, whose bytes hash to its content hash
  (P2; C-16 "approved narrative bytes bound to content hash"), plus a **status note** per report (derived status, decisions, latest validation, untrusted claims,
  revalidation flags), and promoted memory per stock. Status never alters narrative bytes.
- **Obsidian vault export (optional):** one-way into an uncommitted directory: a folder per
  stock, wikilinked notes, a hash manifest; re-export moves edited files to a conflicts folder.
- **Dashboard:** reads through a **read-only role** (SELECT on views); tool deferred.

### 4. Coverage model

**Universe registry.** One row per listing for all Indian listed stocks (name, ISIN, NSE symbol,
BSE scrip code, segment, listing status, first- and last-seen times), in its own table: unverified
candidates that never write the data spec's identity layers (§3); capture still needs §8
verification. Refreshed idempotently on owner command from the Upstox instrument list, cataloged
**identity-only** (distinct from its diagnostic-only financials role); an ISIN seen under a new
symbol records a candidate identity event. **Catalog basis** for every vendor source (Screener,
Tijori): personal, single-owner, non-commercial research; no redistribution; views stay local.

**Screens.** A screen definition is owner-authored text (e.g. a Screener custom screen),
versioned with a hash. Its only input is a results CSV the owner exported from Screener; the
system never requests `?q=` URLs. A screen run records who ran it, when, the CSV capture
(`VENDOR`) and its members, each resolved by exchange identifiers to a registry row or `UNRESOLVED`.

**Capture batch.** The owner launches a batch over all or some members of a screen run. Each
stock goes through data spec onboarding (§8) and a comparison run; no other stock is captured.
Nothing is scheduled.

**Watchlist.** `ADD` and `REMOVE` are owner-only decisions with verbatim reason, in a per-stock
chain (as §1) sealed on the verified identity (data spec §8) and a completed capture batch. Only
watchlisted stocks get reports; drafting for any other stock is refused. A first report for a
new member is a `BOOTSTRAP_THESIS` (amendment 1). The data spec's "ten watchlist companies" are a
capture and comparison set, not this watchlist; none is on it without an owner `ADD`.

| Set | Size | Contents | Grows by |
|---|---|---|---|
| Universe registry | ~5,000 | Identity only | Owner-run refresh |
| Captured | Screen-dependent | Figures, comparisons | Owner-launched batch |
| Watchlist (covered) | ~50–200 | Reports, memory, exchange originals kept forever | Owner decision |

### 5. Retention

**Classes** (assigned at capture; Stage 5 classifies existing captures once by source and the
stock's watchlist status, registration time from the capture record, verification unknown until
a run verifies). **Catalog authority:** no capture outlives its source's catalog retention
(vendor: four quarters plus open-review holds, ending at licence end); intake, class upgrade or
hold creation that would exceed it is refused (no exception contracts yet). **Vendor payload** (occurrences and interpretations from a vendor capture, and
calculation-trace operand values, bounds and results derived from them) shares its capture's retention.

| Class | Applies to | Original bytes kept | Always kept |
|---|---|---|---|
| `COVERED` | Any non-vendor original for a covered stock (P3), incl. transcripts; a non-covered one not filed on an exchange | Forever | Everything |
| `EXCHANGE_REFETCHABLE` | Exchange-filed originals of non-covered stocks (results PDFs, XBRL, shareholding, transcripts, presentations) | Three months after verification (P4), unless held | Capture record, address, hash, first-seen time, occurrences, interpretations |
| `VENDOR` | Every vendor page, API response and screen CSV, covered or not, with its payload | Four quarters from registration unless an open queue item holds it; never past licence end | Capture record, hash, first-seen time, payload tombstones (id, capture id, measurement key, first-seen time, purge record), comparison outcomes |
| `IDENTITY` | Instrument lists | Four quarters, unless held | Capture record, hash, the registry rows it produced |

**Verified:** a `COMPLETE` run covers the filing package; no open queue item references it.

**Holds** are transitive: an original is held if reachable from a root (claim → fact,
interpretation, calculation operands, canonical selection → occurrence → capture; quote or
support → capture). Roots: every report version; every memory item and support; every queue
item and disposition; legacy evidence bindings (data spec §6); identity events and onboarding
outcomes; qualification fixture sets (data spec §2); frozen acceptance-manifest inputs; a covered
stock. Only an open queue item holds `VENDOR` material; other roots may reference it without
extending its window, resolving after expiry to the record and tombstones. Run manifests and
outcomes never hold.

**Eligibility** (dynamic logic; unit-tested): class, registration and verification times, holds,
licence end and now → `KEEP`, `HELD(reasons)` or `ELIGIBLE(since)` per capture. A **blob**
(content-addressed, hard-linked into capture bodies) is eligible only when every capture using
it is. Missing verification time is `KEEP`. After a licence end every capture of that source is
`ELIGIBLE`, holds notwithstanding.

**Retention lock** (one PostgreSQL advisory lock; a crash releases it). Writers take it shared at
transaction level, opening the transaction first: capture intake (blob lookup through
registration), hold-creating writes (claims, supports, versions, queue items, watchlist add,
bindings) and re-fetch. Only backup (shared, snapshot through archive verification) and purge
(exclusive, eligibility recheck through completion) hold it at session level on a dedicated,
non-pooled connection. A waiting writer re-reads state: one needing bytes of
an `EXPIRED` capture, or holding beyond catalog authority, is refused. Watchlist add upgrades only
non-vendor originals within catalog authority, recording `RETENTION_LIMITED` for the rest.

**Store extension.** `record.json` is never rewritten; expiry state lives in the database, so a
missing body on a non-`EXPIRED` capture is corruption. Two new SnapshotStore operations take its
writer flock: delete a blob and its links; relink a re-fetched, hash-checked blob into an
`EXPIRED` capture (not `put_capture`).

**Purge** (P5) — an explicit command, dry-run first, under a dedicated **purge role** (the runtime
role still cannot delete):

1. Before an `EXCHANGE_REFETCHABLE` deletion, a re-fetch probe on a sample per source must
   hash-match; a failure halts that source's deletions and queues a HIGH item.
2. Take the retention lock exclusively, held until step 5 completes; re-check
   eligibility; commit purge intents (`PURGE_PENDING`) and an open purge run.
3. Delete through SnapshotStore: the blob and every hard link to it; an already-missing file
   counts as deleted (idempotent).
4. Commit the purge record (capture id, class, reason, address, hash, probe result, UTC time)
   and `EXPIRED`; for `VENDOR`, in the same transaction tombstone its payload and remove vendor
   values from result rows, keeping each outcome (status, reason, delta class, delta).
5. Take a fresh verified backup, delete older backup sets (pg_dump + capture archive) holding
   bytes this purge expired, then close the run.

Recording a vendor's **licence end** (owner command) first appends it to `licence-ends.json`
beside the backups (never in a backup set), then purges all its material. A restore adds any
licence end from that file missing in the restored database, then purges, before any other role
connects; a missing or unreadable file refuses startup.

**Derived amounts** (comparison deltas, queue items, dispositions, explained amounts,
`COMPARISON` claims) are kept as outcomes, not payload; with the first-party value they reveal
the vendor figure (A-05 open).

Recovery: the purge command first finishes pending intents under the lock (intact and now held →
cancelled; else steps 3–5), then any open run (step 5). Every other lock holder refuses to start
while any intent is `PURGE_PENDING` or a run is open, naming the purge command.

**Capture record states:**

| From | Event | To |
|---|---|---|
| — | captured | `RETAINED` |
| `RETAINED` / `RESTORED` | purge intent | `PURGE_PENDING` |
| `PURGE_PENDING` | purge completes / cancelled | `EXPIRED` / previous state |
| `EXPIRED` (not `VENDOR`) | re-fetch hash matches | `RESTORED` (same capture id, registration and first-seen times; retention applies again) |
| `EXPIRED` | re-fetch hash differs | stays `EXPIRED`; `REFETCH_MISMATCH` recorded, HIGH item; the new bytes become a new capture through normal intake, never a substitute |

### 6. Replay after deletion, and data-spec amendments

**What replay means now:**

| Replay | Possible when | How |
|---|---|---|
| Comparison replay of a run | Its vendor readings retained | Data spec §5, from the manifest and stored occurrences; unaffected by exchange original deletion |
| Re-extraction from an exchange original | Retained, or re-fetched with hash match | Re-fetch from the recorded address; mismatch fails closed (`REFETCH_MISMATCH`) |
| Re-extraction from a vendor capture | Only while retained | After expiry this, and replay of runs using its readings, reports `ORIGINAL_EXPIRED`; outcomes and tombstones remain. A fresh fetch is a new capture |

**Data-spec clauses amended** (the amendment record lists these exactly):

1. User story 12, "any past comparison exactly reproducible from its recorded inputs": while its
   vendor readings are retained; otherwise only outcomes remain.
2. §4 "Capture records and blobs stay in the existing snapshot store, referenced by the
   database": capture records stay forever; blobs follow §5 classes.
3. §5 "Runs and reproducibility", "Replay uses only the manifest…": while vendor readings are
   retained; otherwise `ORIGINAL_EXPIRED`.
4. §6 "Schema and integrity" (immutable evidence, runtime role without DELETE): unchanged for
   the runtime role; a purge role may delete only vendor payload (leaving tombstones), vendor
   values in result rows (never outcomes), and blobs and links, always with a purge record. All
   else is never deleted; §4 "immutable" occurrences exclude vendor readings.
5. §6 "Backup and restore (D2)", "an archive of every capture record and blob the database
   references": every **retained** blob; expired captures listed with address and hash; purge
   step 5 and restore as §5.
6. §6 restore test, "every referenced capture … resolves with a matching hash": every retained
   capture; every expired one has a purge record.
7. §7 shareholding filing "retained like other filings": under the §5 classes.
8. §8 discovery captures "retained as identity evidence": under the `IDENTITY` class and holds.
9. Stage 2 criterion "every referenced capture resolves … one stored run replays identically":
   as in 6; the replayed run's vendor readings must be retained.
10. §0 "a later stage never relaxes an earlier stage's acceptance": items 9 and 12 are
    panel-approved cross-spec amendments, not a later stage relaxing it.
11. §5 review queue and analyst interface ("record dispositions"): items routed to a human are
    dispositioned by the approval panel (§1: `ACCEPT`/`REJECT` of a proposed disposition,
    amounts from code or the owner); owner dispositions remain and outrank. Interpretations
    needing approval are owner-decided until F2 adds panel acceptance with deterministic-provenance
    replay (amended 2026-10-15).
12. §2 qualification and Stage 1 acceptance: a demonstrated mapping keeps its recorded
    measurement after its vendor fixtures expire but cannot be re-measured; a rerun over expired
    vendor fixtures reports `ORIGINAL_EXPIRED` for those rows.

Invariant 13 (point-in-time capture) holds: non-vendor occurrences and their times are kept
forever; vendor readings keep their first-seen time in tombstones. The comparator never reads reports or memory.


## Success Criteria

Each stage's acceptance run matches a **frozen expected manifest**, hand-verified, never
generated by the tested code.

### Stage 1: report ledger

- Apar FY26_Q2–FY27_Q1 updates and the Q0 thesis import; every claim's check state matches the
  manifest under `RETROSPECTIVE` validation (e.g. FY27_Q1 revenue 6,591.06 `POST_CUTOFF`: first
  seen 2026-09-06T15:31Z per the retrieval manifest, after the 2026-07-31 cutoff; the report
  JSON's `retrieved_at` 2026-07-31T15:44:41Z is the transcript's filing time, not evidence; a
  corrective version with an honest later cutoff gives `MATCH`; Q0 F1 11.55, self-cited `POLICY`,
  `MATCH` against its YAML field); every Q0 YAML field lands; every ledger history revision is a
  claim (FY26_Q3 cables revenue growth displays "**20%**", qualifier omitted; its quote "20%-plus"
  in `quote` style). No time is backdated.
- Every import carries an `IMPORT_SEAL`; a fixture with one numeral altered fails the lossless
  check. No `approval_record` becomes a decision; Q0 imports `APPROVED` (decided-on 2026-09-07,
  date precision; then-approved files' SHA-256s) or `HISTORICAL` as the manifest records; evidence
  binding other bytes gives `HISTORICAL`; the earnings updates are `HISTORICAL`.
- An `AS_KNOWN` validation of a draft citing an interpretation recorded after its cutoff gives
  `POST_CUTOFF`; approval binding a `RETROSPECTIVE` validation is refused; a draft self-citing
  `POLICY` is refused.
- Byte-identical to the source: FY27_Q1 revenue "6,591.06" (unit omitted, facts table) and
  "6591.06" (trace) from one claim; "+29.1%"; FY26_Q3 margin guidance "9.5–10%" and its quote
  "guiding about 9.5%, 10%". Ids, hashes, `× 100` and `quote` text pass the numeric scan.
- Each version's export reproduces its content hash, byte-identically on re-export; a status
  change leaves narrative bytes unchanged.
- A revenue digit changed in a claim's value gives `VALUE_MISMATCH` and changes its generated display; a calculation with one operand first seen after
  the cutoff gives `POST_CUTOFF`; a period swap gives `KEY_MISMATCH`; a guidance quote with bounds
  changed (9.5–10 → 9.5–11), "plus" dropped, or a wrong metric, scope or constant-currency flag
  gives `QUOTE_MEANING_MISMATCH`; a bare numeral in section text gives `UNREGISTERED_NUMBER`; an
  observed paragraph with no location gives `UNCITED_PROSE`; each blocks approval.
- After `SUBMIT`, adding a claim or section, or a wrong sealed digest, is refused; a validation
  appended later leaves the sealed digest unchanged.
- The runtime role cannot insert any decision but `SUBMIT`, nor an unproposed or amount-bearing disposition, nor update/delete
  ledger rows; owner and panel decisions record their role and DB recorded-at; a
  decision naming a stale head is refused.
- Panel (fake adapter; amended 2026-10-15): a reviewer `APPROVE` → `APPROVED`, its text,
  provider and model recorded. Refused: a panel verdict without its review, a review of another
  digest, a panel-supplied amount, a panel decision on a subject whose chain holds an owner
  decision; a failing claim check refuses with no model call.
- A disposition making a cited cell untrusted appends a new validation; the approval still binds
  its original validation.
- A correction supersedes the old version, which can still be withdrawn; v1 approved, v2
  rejected, v3 approved → v1 `SUPERSEDED`; v1 approved, v2 `HISTORICAL`, v3 approved → v1 and v2
  `SUPERSEDED`; a successor submitted
  while its predecessor is `IN_REVIEW`, a predecessor from another report, or a second successor
  is refused. Approval changes no memory item.

### Stage 2: long-term memory

- A `MANAGEMENT_TRACK_RECORD` candidate for the Apar cables EBITDA margin guidance (9.5–10% in
  FY26_Q3, 10–11% in FY27_Q1), supported by both quote claims from corrective versions approved in
  the test database, is retrieved only after a panel `PROMOTE`; staging from `HISTORICAL` is refused.
- A cutoff before promotion or recorded-at excludes the item (C-15); search for "cables margin"
  returns it; stock, kind and status filters work.
- A promoted superseding item retires the old one atomically; a second successor cannot then be
  promoted; both stay in provenance; superseding across stock or kind is refused.
- No support, a support added after a decision, a non-`MATCH` claim support, or a version lacking
  an all-`MATCH` `AS_KNOWN` validation is refused; a
  `SOURCE_QUIRK` with a capture support is accepted.
- A support's version withdrawn, or a non-`MATCH` validation appended, between staging and
  `PROMOTE` (incl. a version directly supporting `COMPANY_UNDERSTANDING`) makes `PROMOTE` refuse.
- Withdrawing or superseding a supporting version, or any later validation of a support that has
  a non-`MATCH` claim or a version-level state, flags `NEEDS_REVALIDATION` (and refuses `PROMOTE`); retrieval at a cutoff before that event shows no flag.
- No comparator or claim-check path reads memory.

### Stage 3: generated views

- Status notes show status, latest validation, untrusted claims; the read-only role selects
  views and writes nothing.
- If built: the Apar vault has one folder, a note per version, resolving wikilinks; a hand-edited
  note moves to conflicts on re-export.

### Stage 4: coverage model

- A registry load from a retained instrument list yields the expected rows; reloading changes
  nothing; an ISIN under a new symbol records a candidate event, changing no verified identity.
- A screen run from a five-member CSV fixture resolves them; a batch over three captures and
  compares exactly those; the other two have none.
- Drafting for a non-watchlisted stock, and adding an unverified or uncaptured stock, are
  refused; add and remove are owner decisions with verbatim reasons. Nothing is scheduled.

### Stage 5: retention and replay

- Eligibility fixtures, one per class and hold root (incl. a superseded version, a closed
  disposition, an identity event, a qualification fixture set, a pre-existing capture), match
  the manifest; a non-covered XBRL with no verification time is `KEEP`.
- Two captures sharing a blob: one held keeps blob and links; both eligible removes all.
- The dry-run lists exactly the eligible blobs; the purge deletes them, marks captures `EXPIRED`
  with purge records, and keeps non-vendor occurrences, interpretations and facts.
- Crashes after intent commit, file deletion and the `EXPIRED` commit converge on rerun; no non-expired capture
  lacks bytes; a missing body on a non-`EXPIRED` capture reads as corruption.
- A hold-creating write during a purge waits; then a `SOURCE_QUOTE` claim on the expired capture
  is refused, a `FIGURE` claim on its facts proceeds. After a crash post-deletion, backup and
  hold-creating writes refuse until purge recovery. A purge waits for a running backup's archive
  verification. Same-blob intake during a purge ends with the body present.
- A re-fetch through a fake fetcher returning the same bytes restores the capture with its
  original first-seen time, and re-extraction reproduces the stored occurrences; different bytes
  give `REFETCH_MISMATCH`, HIGH, and the expired evidence is not replaced.
- Expired vendor capture: re-extraction and replay of runs using it report `ORIGINAL_EXPIRED`;
  readings and derived trace values are tombstones; outcomes and deltas remain.
- Covered originals are never eligible; watchlist add moves retained exchange originals to
  `COVERED`, vendor captures keep their window. Intake beyond catalog retention, and a
  `SOURCE_QUOTE` on a vendor capture, are refused; a support or onboarding outcome referencing one
  is accepted without extending its window; an open queue item holds one past four quarters until
  closed. Recording a licence end purges all that vendor's material, holds notwithstanding.
- A backup restores: retained captures hash-match, expired ones have purge records. After a
  purge no older backup set holds expired bytes; restoring a pre-purge set purges them first, and
  one predating a licence end purges that vendor's material.

## Testing Decisions

- **Integration tests** on the PostgreSQL test database per mechanism; one **end-to-end test**
  per stage against its frozen manifest over retained Apar artifacts.
- **Unit tests only for dynamic logic:** claim check (both modes); numeric and prose-marker
  scans; display; quote meaning; eligibility and holds; panel verdict rules; status and chain digests.
- Only the fetcher, purge crash points and reviewer calls are mocked; no network.

## Out of Scope

| Item | Reason | Status |
|---|---|---|
| Typed non-numeric claims | Register B-06 open | Deferred |
| Vector search | Only on measured need (O3) | Deferred |
| GBrain adoption | D-02/D-05 | Deferred |
| Two-way vault sync or editing in the vault | Owner decision O5 | Rejected |
| Dashboard tool | Owner decision O5 | Deferred |
| Quarterly or scheduled whole-market capture | Owner decision O7; data spec deferral | Rejected |
| System-selected coverage; unapproved initiation | Register §G | Deferred |
| Scheduled purge | P5 | Rejected |
| Vendor blob compression | Small at on-demand scope | Deferred |
| Multi-user authorization | Single-owner local system | Rejected |
| Retention exception contracts; physical memory removal | Rights-driven | Deferred |
| Off-machine backups | Data spec | Deferred |

## Open Questions

- **Provider rights (A-05):** conservative defaults applied from the vendor-terms research; open:
  Tijori's derivative-works clause, Upstox terms, and whether kept derived amounts (§5) are allowed.
- **Re-fetch stability:** addresses stable for years? Probe sample size?
- **Legacy-fact claims:** do historical versions with `UNRESOLVED` claims (resolved through
  origin-qualified ids) need a corrective re-issue?

## Further Notes

- **Glossary (CONTEXT.md):** "Memory promotion" and role names change with amendment 8; the
  "Source-of-truth hierarchy" with amendment 3 and §5. "Watchlist" differs from the data spec's (§4).
