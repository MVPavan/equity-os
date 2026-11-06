# VENDOR-1: vendor-first sourcing with filing checks

**Status:** approved (gpt-6.1-sol APPROVE, review round 3, 2026-11-06). **Bead:** eqos-awnc. **Date:** 2026-11-06.
Amended 2026-11-06 per Phase 1 plan review 2 (gpt-6.1-sol), and per Phase 3 plan review 1
(gpt-6.1-sol, amendments A1–A6: §6.1, §6.6, §8).

Code facts were read at `77637a17`; store facts were queried read-only. **Inferred** and **not
established** mark everything else. Measurement figures come from
`scratchpad/vendor-first/measure-1/`, Apar only (entity 1, the store's one reporting entity).

## 1. Owner order (2026-11-05) and how it is read

1. Screener and Tijori are the main sources for numbers and processed text.
2. NSE/BSE filings are the fallback, used when the vendors disagree or don't map.
3. Every mechanism is built.
4. Next step after this spec: a test on APARINDS, ICICIBANK (a bank), LAURUSLABS, MTARTECH, NETWEB.

**Reading:** vendor-first sourcing with filing checks. The vendor candidate is chosen first. A
filing's presence alone never changes the source. The filed value is used only when vendor sourcing
fails, or when a filing comparison establishes a difference. "Filings prove numbers" governs
checking and fallback; it does not make filings primary.

## 2. Owner decisions (defaults in force)

Each stands until the owner changes it.

1. **Numeric retention.** Admitted vendor numeric cells (both witnesses of a vendor-sourced fact)
   are kept privately, never committed to the public repo, for as long as a sealed report cites
   them, within each vendor's licence and terms. Expiry or licence end for either witness
   withdraws the admission for new reports; existing sealed reports keep their stored values with
   a visible note. This is a separate exception from DOCS-1 (`CONTEXT.md`, Evidence package),
   which covers labelled Tijori copies of documents with no exchange original and is unchanged.
2. **ICICIBANK analysis basis: standalone.** Recorded as the analysis basis, separately from the
   bases the issuer actually reports.
3. **Headline lines** (revenue, PAT, EPS) get no special case; the label is always shown.
4. **Scope of eligibility:** the five-company pilot and the owner's private reports. Admitting a
   vendor value without a filing check anywhere wider needs a new owner decision.

## 3. Phases

Each phase ships on its own, closes with its own Sol review, and leaves the system consistent.

| Phase | Scope |
|---|---|
| 1. Core | Numbers on non-bank issuers: mapping and extraction fixes, standalone-only onboarding, vendor-first selection and admission, eligibility, citation, fallback workflow, retention |
| 2. Vendor text | Tijori and Screener summaries as cited vendor text; numeral rule |
| 3. Banks | Bank route grounded in a retained ICICIBANK filing |

All three land before the five-company test (§9).

## 4. Non-goals

- Feeding `eqos.vendor_values` (the raw-first cell store) into comparison; the occurrence path
  holds the same tables.
- Operating KPIs, divisions, volumes, capacity (model work from documents, Data Extraction rule).
- Upstox (stays diagnostic). Review-queue severities and the trust overlay.
- A mutable eligibility system. Eligibility is one pinned artifact plus counterexample blocking.
- NBFCs and insurers (stay `UNSUPPORTED`).

## 5. What the measurement found

| Finding | Number |
|---|---|
| Concept-periods with a Screener, a Tijori and a filed value | 8, all quarterly revenue, all agree |
| Tijori interpretations | 20 `MAPPED`, 2,030 `UNMAPPED`, 10 `INVALID` (`UNIT_MISMATCH`, `pl_c_s`) |
| Screener interpretations | 297 `MAPPED`, 210 `UNMAPPED`, 9 `PERIOD_AMBIGUOUS` |
| Screener FY `finance_costs` vs filing | 7.70–7.78% off in all 7 pairs; quarterly matches. Inferred: a definition difference |
| Standalone values stored | none |

Eight points of one concept cannot answer the owner's question; Phase 1 exists to make the
re-measurement mean something.

## 6. Phase 1: the core

### 6.1 Mapping and the label inventory

Vendor row labels are standard data: the reviewed per-surface mapping files
(`config/normalisation/mappings/screener/…`, `…/tijori/…`) are extended, new versions, no new
mechanism. `map_labels` may draft entries; comparison never reads `vendor_label_proposals`.

- Each mapping file gains an `unmapped:` list. Every native statement label in the retained
  captures (site, section, basis, label; Tijori `fr_c` ratios excluded, since ratios are computed
  by code) has exactly one disposition: an entry, or an `unmapped` item with a reason. This
  **is** the frozen inventory; no separate file.
- Entries default to `EQUIVALENCE_UNPROVEN`. A label whose definition is known to differ is
  `RELATED_NOT_EQUIVALENT` and never votes; Screener annual interest vs `finance_costs` is in this
  class unless the phase explains the 7.7%.
- Standalone tables (Tijori `*_s` sections, the Screener standalone page) get entries. Capture
  standalone vendor tables for STANDALONE_ONLY issuers and whenever a separately recorded owner
  analysis-basis decision selects standalone, including ICICIBANK when the issuer reports both
  bases. Acquisition, interpretations, keys and comparisons retain the selected basis; this choice
  never changes the issuer's reported-basis status or pairs standalone with consolidated.
  Standalone never pairs with consolidated.
- Dimensioned keys: an entry keeps its dimensions where the vendor table carries them. Dimension
  members are enumerated from the filing package today; where a key's members cannot be
  enumerated without a package, the cell refuses with an explicit reason instead of dropping the
  dimension.

**Units and precision cannot come from a mapping file.** `MappingEntry` has no raw-unit field;
`vendor_tijori.py` (`extract_tijori`, the `scoped_row` branch) sets unit, scale and declared
precision only for the one section named in `config/normalisation/mappings/tijori/v1/display.yaml`
(`qt_c`), and `UNKNOWN_UNIT` elsewhere, which `interpret.py` (`interpret`, the `policy.units`
lookup) rejects as `INVALID`/`UNIT_MISMATCH`. Fix:

- `display.yaml` v2 becomes a list of rules, one per supported (section, basis), each with its own
  `unit_evidence_ref` and `precision_evidence_ref` taken from a retained capture. Sections without
  a rule stay `UNKNOWN_UNIT` and fail closed.
- The extractor applies the rule of the row's own section; its version is bumped
  (`VENDOR_EXTRACTORS` in `run_config.py` pins it), and retained captures are re-ingested.
- Precision is never inferred from serialized digits.

Before re-measurement, retained first-party packages are re-interpreted under the new mapping set.

### 6.2 Standalone-only onboarding

Today `discovery.py` refuses `STANDALONE_BASIS` when the filing window has no consolidated row,
`ListingRow.qualifies` (`nse_filings.py`) accepts only consolidated rows, `derived_settings.py`
hard-codes `BasisStatus.CONSOLIDATED_AND_STANDALONE`, and onboarding ingests with
`Basis.CONSOLIDATED`. NETWEB is expected to be standalone-only (inferred; its listing decides).
Change, from listing evidence only:

- **Filing selection.** When the window holds standalone rows and no consolidated row, discovery
  selects the standalone integrated Financials rows (the qualifying predicate takes the basis) and
  runs the same instance, entity, identity and framework checks on their XBRL. The instance is
  registered under a standalone XBRL source entry in `source_catalog.py` (today's
  `NSE_XBRL_INSTANCE` names the consolidated source). Any consolidated row keeps today's path.
- **Basis status.** Derived settings write `STANDALONE_ONLY` when discovery selected standalone
  filings, `CONSOLIDATED_AND_STANDALONE` otherwise; the value is never defaulted.
- **Ingest and pairing.** On this standalone-only path, onboarding ingests with `Basis.STANDALONE`. For a `STANDALONE_ONLY`
  entity, consolidated cells are `NOT_APPLICABLE` and no consolidated vendor table pairs with a
  standalone filing or vendor table.

### 6.3 Vendor-only runs and default vendor sides

`engine.py` `_group_periods` takes reporting currency only from filing-package interpretations,
and `ApplicabilityContext.disclosed_rows` comes from the package, so a company-period with vendor
captures and no filing package cannot run. Fix: when a group has no filing package, the engine
resolves context from evidenced metadata: currency from the vendor occurrences' evidenced unit
(§6.1 rules), framework, fiscal year and basis status from identity settings, `disclosed_rows`
from the vendor tables' structure (rows present, never values), period kind from the vendor
column. Nothing is defaulted; a missing input refuses the group.

`compare_cli.py` defaults `--vendor` to empty. Change: financial-results runs include Screener and
Tijori by default, including fallback reruns (§6.8).

### 6.4 Predicates

Policy file `config/verification/vendor_first/policy/v1.yaml`, pinned through `eqos.version_pins`
like every run artifact: `precision_limit: '0.005'`, `min_clean_key_periods: 4`. This is a
separate field from the comparison policy's triage `magnitude_threshold`, which is not reused.

Per cell, each side is an interval: value ± half a unit of its declared precision (zero width when
exact). S = Screener, T = Tijori, F = the run's first-party side.

**T1, vendor outcome.** First match wins:

1. `VENDOR_UNMAPPED`: S or T is absent, not `MAPPED`, not a DIRECT interpretation, not `VALUE`, or
   its entry is `RELATED_NOT_EQUIVALENT`. Constructed values are excluded here; derived figures
   are calculated by code from admitted facts.
2. `VENDORS_DISAGREE`: the S and T intervals are disjoint.
3. `VENDORS_IMPRECISE`: let m = max(|S|, |T|). If m = 0, either side has non-zero width. Else the
   wider half-width exceeds `precision_limit` × m.
4. `VENDORS_AGREE`.

The pair-outcome distinction `AGREE` / `AGREE_UNQUALIFIED` plays no part in T1; mapping tier
enters only through rule 1 and through the check class (§6.6).

**Filing state of a cell.** First match wins:

1. `FILING_ABSENT`: every first-party side is `NO_VALUE`, with no acquisition, extraction or
   interpretation failure.
2. `FILING_FAILED`: any first-party side is `UNAVAILABLE` or `INVALID`, or a non-absent cell fails
   today's first-party admission rule.
3. `FILING_DIFFERS`: admissible, and F is disjoint from the S interval or from the T interval.
4. `FILING_AGREES`: admissible, and F intersects both.

"Differs" means either vendor, not only the chosen one: a counterexample to "the vendors agree, so
the filing matches".

### 6.5 One admission path

`admit_run` keeps one path. Before any row is evaluated, every cell with T1 `VENDORS_AGREE` and
`FILING_DIFFERS` records a counterexample (§6.6) in the admission transaction, whatever row then
applies. A filing/vendor mismatch can itself open a non-diagnostic `HIGH` item
(`routing.py`, `_pair_route`), so such a cell may refuse at row 0a; its counterexample is still
recorded. Per cell, first match wins:

| # | Condition | Admitted value | Label |
|---|---|---|---|
| 0a | An open non-diagnostic `HIGH` item names the cell | none | refusal `REVIEW_OPEN` |
| 0b | `FILING_FAILED` | none | refusal `FILING_UNRESOLVED` |
| 1 | `VENDORS_AGREE`, `FILING_AGREES` | vendor value and its declared precision | `CHECKED_AGAINST_FILING` |
| 2 | `VENDORS_AGREE`, `FILING_DIFFERS` | filed value | `CHECKED_AGAINST_FILING` |
| 3 | `VENDORS_AGREE`, `FILING_ABSENT`, class eligible (§6.6) | vendor value | `VENDORS_AGREE_NOT_CHECKED` |
| 4 | `VENDORS_AGREE`, `FILING_ABSENT`, class not eligible | none | refusal `CHECK_REQUIRED` |
| 5 | T1 is `VENDOR_UNMAPPED`, `VENDORS_DISAGREE` or `VENDORS_IMPRECISE`; filing admissible | filed value | `CHECKED_AGAINST_FILING` |
| 6 | As 5, `FILING_ABSENT` | none | refusal with the T1 outcome |

The vendor value is the narrower interval's (tie: Screener). Rows 0a–0b run before any source is
chosen, so vendor agreement never bypasses a failed or contested filing. Refusals in rows 4 and 6
are **triggers** (§6.8); 0a and 0b go to the review queue as today.

**Labels.** Two, the owner's: `CHECKED_AGAINST_FILING` ("checked against filing") and
`VENDORS_AGREE_NOT_CHECKED` ("vendors agree, not checked against filing"). When the filing agrees
within declared precision, the selected vendor value and precision are retained and labelled
`CHECKED_AGAINST_FILING`; otherwise that label carries the admissible filed value. The comparison
outcome (T1, filing state) is not a label; it stays in the run's results and pair records,
reachable from the admission's `result_id`.

**Vendor bridge.** `fact_for` today requires a known occurrence knowledge time and builds anchors
for XBRL and PDF only. For a vendor value it:

- anchors natively: Tijori as `JSON_ISLAND`, Screener as `HTML_TABLE` (both in
  `SourceAnchorType`); an occurrence lacking a required anchor field raises `BridgeError`;
- sets the fact's knowledge time to the later of the two witnesses' capture-registration times.
  The occurrences keep `KnowledgeTimeStatus.UNKNOWN`; no publication time is invented;
- records both witnesses: the chosen interpretation as today, the other in
  `witness_interpretation_id`. Epistemic class `observed`; bridge version `admission-bridge/2`.

**Which admission authorises a selected fact.** Selection stays per fact row (`select_admitted` →
`select_canonical`). `read_selected` takes the label from the latest admission of the selected row
whose `overlay_position` is at or before the cutoff; the knowledge-time witness stays the earliest,
as in `citations.py`. `SelectedFact` gains `label`. Historical cutoffs return the same facts as
before.

**Migration `migrations/0047_admission_label.sql`.** 0046 stays reserved for research-4; the runner
is filename-ordered and gap-tolerant (`migrations.py`).

- `fact_admissions`: `label text NOT NULL DEFAULT 'CHECKED_AGAINST_FILING'`, then `DROP DEFAULT`
  (every existing row is a first-party filed value that passed the first-party rule, so no UPDATE
  is needed and the row-mutation trigger stays untouched); `witness_interpretation_id bigint NULL
  REFERENCES eqos.interpretations`; `eligibility_version text NULL`; a check that a
  `VENDORS_AGREE_NOT_CHECKED` row has both a witness and an eligibility version.
- `eqos.vendor_counterexamples (id, class_digest, result_id → results, run_id → runs,
  recorded_at DEFAULT eqos.store_now())`, `UNIQUE (class_digest, result_id)`, append-only with the
  existing `reject_mutation` triggers. It stores no vendor value.
- `eqos.row_captures`: the `fact_admissions` branch also yields `witness_interpretation_id`, so
  retention guards hold both witnesses' captures.

0047 also extends the `run_versions` pin CHECK for `vendor_first_policy` and `eligibility`, and
creates append-only `vendor_fallback_outcomes`.

### 6.6 Eligibility: a pinned artifact plus counterexample blocking

**Check class** = digest of (canonical id, period kind, basis, framework, issuer class, the
Screener entry and the Tijori entry with their mapping-set version, both extractor versions,
dictionary version, `vendor_first` policy version). Any version change makes a new class with no
evidence, so incompatible evidence is invalidated by identity, not by a rule. Issuer class is an
identity setting (`NON_FINANCIAL` for every onboarded issuer today, since onboarding refuses
financial issuers; `BANK` in Phase 3). In Phase 1, issuer class is resolved from positively
evidenced onboarding provenance known at the cutoff; absent or unsupported provenance yields no
class. From Phase 3, issuer class is the ISSUER_CLASS setting backed by verified filing-form
evidence (§8 step 2); the Phase 1 rule remains only for previously onboarded non-financial issuers
without a new explicit class.

**Artifact.** `eqos vendor measure --available-from <timestamp>` (product code replacing the
scratch `measure*.py`) reads stored run results and writes
`config/verification/vendor_first/eligibility/v1.yaml`. Measurement includes only cells whose T1
outcome is `VENDORS_AGREE`; clean evidence additionally requires `FILING_AGREES`. Per class it
records the distinct key-periods (dedup identity: `key_digest`) in `FILING_AGREES` and
`FILING_DIFFERS`, their run ids, `eligible` (≥ `min_clean_key_periods` agrees, 0 differs), the
command's code version, and `available_from`. `available_from` is the argument, fixed before the
file is generated and written into it; the command refuses a value earlier than the latest
recorded time of any counted run. Nothing depends on the file's later commit time. The artifact
holds counts and ids, no vendor values, and is committed after review. Runs pin it through
`eqos.version_pins`; the admission records it in `eligibility_version`. In `AS_KNOWN` mode a cutoff
before `available_from` sees no eligibility.

**Pilot evidence only.** Eligibility is scoped to the exact mapping entries and conditions in the
class. Four clean key-periods are provisional pilot evidence, valid only within owner decision 4;
they establish no reusable concept class.

**Counterexample blocking.** A counterexample is recorded per §6.5, independently of the cell's
admission row. From then on:

- a class with any counterexample is not eligible, whatever the artifact says; the artifact is the
  reviewed baseline, the store is the override, and nothing waits for a file edit;
- `read_selected` returns nothing for a selected fact whose authorising label is
  `VENDORS_AGREE_NOT_CHECKED` and whose class has a counterexample recorded at or before the
  cutoff; earlier cutoffs are unchanged. The cell refuses on the next run and becomes a trigger;
- sealed reports keep their stored values; a later status note accompanying the unchanged sealed
  report shows "class later contradicted by a
  filing on ‹date›".

### 6.7 Citation

`citations.py` `_admitted` resolves a fact only when every admission's capture is first-party;
calculation inputs resolve the same way. Change: an admission with a `witness_interpretation_id`
resolves when both witnesses' captures are retained catalog vendor captures of the two
vendor-primary sources, and the admission is not withdrawn (§6.6, §6.9). The resolved citation
carries the label. A calculation shows the weakest label among its inputs. Nothing else in
citation resolution changes.

### 6.8 Fallback workflow

`admit_run`'s outcome already lists refusals; triggers are rows 4 and 6 of §6.5, grouped per
(entity, period end, basis), since a filing covers a whole period. A new subcommand
`eqos compare fallback --run <id>` consumes that list and, per company-period, runs:

1. **Acquire.** No existing route lists and fetches NSE financial-results XBRL for a named
   company-period. `discovery.py` fetches the results listings and XBRL only during onboarding,
   for the latest two filings (`FILINGS_CHECKED`) of a six-quarter window; `NseXbrlSource`
   (`xbrl_source.py`) is the legacy consolidated-only pilot download and registers no capture;
   `eqos documents backfill` without vendor flags reads announcements, meetings and annual
   reports, never the results listings, and only for covered issuers (`documents_cli.py`
   `_Pass._issuers`). The new route reuses those helpers and takes the entity, its held NSE symbol
   and ISIN, period end and basis from the triggering run, so no intake pass over other issuers
   runs and watchlist coverage is not changed:
   - **XBRL:** fetch the legacy and integrated listings (`nse_filings.listing_url`,
     `LEGACY_LISTING`, `INTEGRATED_LISTING`) through `discovery.acquiring_fetch` and
     `register_capture`; parse with `listing_rows`; keep rows with the requested period end and
     basis and collapse them to the latest broadcast as `filing_window` does (a tie or a missing
     broadcast ends `FILING_UNAVAILABLE`); fetch that row's `xbrl_url` the same way.
   - **Results PDF:** the announcements step of `documents_cli._Pass` (`_listing` on
     `ANNOUNCEMENTS`, then `_documents`) is extracted into a function over one issuer and one span,
     called for this entity over the period end to seven days after the XBRL broadcast; the
     `RESULTS_CATEGORIES` row (`first_party_documents.py`) gives the PDF.
2. **Ingest.** Write the package manifest with `onboard_cli.package_manifest` and call
   `ingest_first_party` with the requested basis, as onboarding's `_ingest` does. The PDF joins the
   package when the issuer has a `pdf_parse` config, as `eqos evidence ingest` requires; otherwise
   the package is XBRL-only and the PDF stays retained.
3. **Compare.** A fresh `eqos compare run` for the period (vendor sides included by default).
4. **Admit.** `admit_run` on that run.

Terminal outcome per company-period, printed and stored with the run id: `ADMITTED` (every trigger
cell admitted), `FILING_UNAVAILABLE` (no filing acquirable; cells stay refused), `FILING_UNRESOLVED`
(extraction failed or review opened; review queue owns it), `STILL_REFUSED` (listing the cells and
reasons). No retries beyond those the acquisition layer already has.

### 6.9 Retention

Owner decision 1 applies. Mechanically:

- the vendor captures behind both witnesses stay private (store and retained blobs, never the
  repo), are held by the retention guard through `row_captures` (§6.5) while a sealed report cites
  the fact, and follow each vendor's retention and licence terms in the source catalog;
- when either witness's capture expires or its vendor's licence ends, the admission is withdrawn
  for new reports: `read_selected` and citation resolution refuse it; sealed reports keep their
  stored bytes and values; their status note shows "vendor source expired ‹date›";
- a backup restore does not resurrect a withdrawn admission; only a hash-matched re-fetch from the
  vendor within licence makes the capture `RESTORED` and the admission usable again.

### 6.10 Display

Every renderer reading `read_selected` prints the label text beside the number (today
`equity_os/interface/entry/cli.py`); thesis-model adapters pass it where they pass
`single_sourced`. A fact without a label fails the render.

### 6.11 Phase 1 acceptance (code-checked on retained Apar captures unless noted)

1. **Inventory.** Every native statement label in the retained Apar Tijori and Screener captures
   (excluding `fr_c`) has exactly one disposition; the phase report gives cell counts per
   disposition under the pinned mapping version. In sections with a display rule, Tijori
   `INVALID`/`UNIT_MISMATCH` = 0.
2. **Units and precision.** Every supported Tijori (section, basis) has a rule with both evidence
   refs; a fixture row in an unsupported section stays `UNKNOWN_UNIT`; a value whose digits
   suggest another precision gets the rule's.
3. **Three-way coverage.** The command computes the expected set from reviewed mappings with full
   keys (entity, canonical id, period, basis, framework, dimensions); a fresh run has a three-way
   comparison for each member, and a dimensioned key that cannot be enumerated refuses
   explicitly. The report states the measured count.
4. **Standalone-only onboarding.** A fixture whose listings hold only standalone rows onboards with
   standalone filings verified, basis status `STANDALONE_ONLY` and a standalone package; a
   consolidated vendor table is not paired with its standalone filing, and its consolidated cells
   are `NOT_APPLICABLE`. Apar onboards as before.
5. **Runs.** An ordinary `eqos compare run` with no vendor flags has Screener and Tijori sides. A
   case with vendor captures and no filing package, occurrence or interpretation produces a
   complete run and a row-3 admission under a pinned eligibility fixture.
6. **Admission.** One case per row of §6.5, including: failed filing plus agreeing vendors refuses
   `FILING_UNRESOLVED`; an agreeing filing keeps the vendor value and precision; agreeing vendors,
   a differing filing and an already open `HIGH` item refuse `REVIEW_OPEN` and still record the
   counterexample. Existing admission tests pass with label `CHECKED_AGAINST_FILING`.
7. **Predicates.** Unit cases: disjoint precise intervals → `VENDORS_DISAGREE`; intersecting
   coarse → `VENDORS_IMPRECISE`; half-width exactly at the limit → agree; m = 0 both exact →
   agree, else imprecise; F disjoint from one vendor only → `FILING_DIFFERS`.
8. **Eligibility.** Same stored results and arguments give byte-identical output. Key-periods
   whose T1 is `VENDORS_IMPRECISE` contribute zero clean observations, even with `FILING_AGREES`.
   A version mismatch gives `CHECK_REQUIRED`. A counterexample in run N blocks row 3 in run N+1
   with the artifact unchanged, and `read_selected` drops the earlier unchecked fact for later
   cutoffs only.
9. **Citation.** Through the existing filing-backed Stage 2 report path, a fixture withholding the
   quarter's filing package from the comparison run seals a report citing a row-3 fact and a
   calculation using it. Both citations resolve with the admission label; `row_captures` returns
   both vendor witnesses' captures. Reports for quarters without filings are outside Phase 1.
10. **Retention.** Expiry, and separately licence end, of either witness withdraws the admission
    for a new report; the sealed report keeps its value with the note (the status note of §6.9); a backup restore does not
    revive it; a hash-matched re-fetch does.
11. **Fallback.** On an Apar period whose filing is withheld from the first run, the command
    acquires the XBRL and results PDF for that period only, ingests, reruns with vendor sides and
    ends `ADMITTED`; an unavailable filing ends `FILING_UNAVAILABLE` with cells still refused; no
    other issuer is fetched and coverage is unchanged.
12. **Known difference.** No FY `finance_costs` cell is admitted under row 3.
13. **Labels.** The rendered output carries a label for every number.
14. **Gate.** `scripts/verify.sh gate` passes; mypy strict and ruff clean.

## 7. Phase 2: vendor text

`vendor_surface_claims.extract_text` queries Screener captures only, through a Screener-only
reader, over `SURFACES` = three Screener surfaces; Tijori `concall-monitor` is a market-scope
surface in `config/sourcing/vendor_surface/surfaces.yaml`.

- **Readers by site.** `SURFACES` becomes keyed by (site, surface); the reader table gains the
  Tijori `concall-monitor` reader and the Screener company-page concall notes reader. Both are
  fixed vendor page formats, so the readers are code.
- **Bound to the report.** A span is usable in a report only if code resolves the span's company
  reference to the report's issuer (a market page carries many issuers) and its capture was
  registered at or before the report's cutoff.
  For vendor text, capture registration must be at or before the report's source cutoff S, while
  the selected extraction outcome, its claim rows and the issuer-binding evidence must be recorded
  at or before its knowledge cutoff K; the same boundaries apply during drafting, checking and
  sealing.
- **Resolvable reference.** A report cites a span as (`capture_ref_id`, offsets, capture hash);
  citation resolution re-reads the offsets from the retained capture and refuses a mismatch.
- **Never a number source.** `vendor_text_claims` never produce occurrences or interpretations.
  The claim check refuses a span as evidence for a claim with a numeric object.
- **Numerals.** A span containing any numeral (per `numeral_scan.py`) is never rendered; it stays
  private as an extraction pointer that directs the document-extraction model to the transcript or
  presentation, whose extractions carry their own page and quote. Spans without numerals render in
  a block headed with vendor, surface and capture date and marked
  `vendor summary — guidance, not evidence`.

**Phase 2 scope amendment (2026-11-06).** Readers remain keyed by `(site, surface)`. Phase 2 implements Screener's existing text surfaces and a reader for the summary reached through the issuer's advertised `/concalls/summary/{concall_id}/` links, provided retained captures establish both its text region and a resolvable own issuer reference. Tijori's `concall-monitor` retained captures contain no summary text, and no working authorised summary route has been established. The Tijori reader is deferred to a tracked follow-up until such a route and retained summary format are evidenced; Phase 2 completion does not claim Tijori text coverage. All issuer, cutoff, citation, numeral and no-number-source rules below continue to apply.

**Acceptance.** The supported Screener readers produce validated spans from retained captures, including the grounded concall-summary reader. The deferred Tijori reader is not counted as completed acceptance. A span of another
issuer, or captured after the cutoff, is refused; a citation with altered offsets fails; a numeric
claim citing only a span is refused and passes when it cites a fact ID; a span with a numeral is
absent from the render; no `interpretations` row references a text-claim capture. Gate as Phase 1.

## 8. Phase 3: banks

Onboarding verifies Ind AS (`verification.py`), derived settings write an Ind AS framework
(`derived_settings.py`), discovery refuses financial issuers and non-Ind AS filings and does not
acquire the results PDF (`discovery.py`), and results runs assume Ind AS; `AccountingFramework`
has `IND_AS`, `IFRS`, `US_GAAP`, `UNKNOWN`. Inferred, not established: Indian banks file in the
Banking Regulation Act Third Schedule format, not under Ind AS. The store holds no ICICIBANK entity
or capture. So the bank route starts from evidence:

1. **Ground.** Acquire and retain the ICICIBANK XBRL and results PDF through the raw listing and
   fetch helpers of §6.8 step 1, before onboarding eligibility, framework or schema validation.
   Record from them: framework, XBRL schema and taxonomy, statement layout, bases reported. Every
   later step cites this record. Retained but unsupported evidence grants no onboarding authority.
   Grounding uses entity-free listing, acquisition and retention primitives. It does not call an
   onboarding eligibility, framework or supported-schema filter to decide which candidate evidence
   can be retained. It creates no entity, onboarding decision, setting, package or interpretation.
   Grounding captures use a retention-only authority surface and are not eligible as first-party
   comparison members merely by being retained. Ambiguous candidates and missing evidence are
   recorded and stop dependent decisions rather than being defaulted. Each decided claim identifies
   its capture hash, basis, period and element/context or page/quote; the reviewed record
   distinguishes prior bank fixtures from ICICIBANK evidence.
2. **Framework and onboarding.** Add the framework value the filing evidences (only if no existing
   value fits). Onboarding verification and derived settings accept it for issuer class `BANK`,
   set from evidence. NBFCs and insurers stay `UNSUPPORTED`. ICICIBANK's analysis basis is
   standalone (owner decision 2), stored apart from its reported bases.
   Store ISSUER_CLASS as a setting backed by verified filing-form evidence: an uncontested
   IntegratedFinance_IndAS form yields NON_FINANCIAL and an uncontested IntegratedFinance_Banking
   form yields BANK; NBFC, insurer, unknown and conflicting forms remain unsupported. An
   accounting-framework value alone does not classify a newly onboarded issuer. Settings resolve by
   effective period and recorded cutoff. The Phase 1 provenance rule remains only for previously
   onboarded non-financial issuers without a new explicit class; unusable explicit evidence never
   falls back to that rule. Store ANALYSIS_BASIS separately, backed by a reviewed owner-decision
   binding to issuer, value and immutable decision content. ICICIBANK's binding is STANDALONE.
   Reported-basis status comes from the evidenced listing window, independently of the selected
   analysis basis.
3. **Dictionary v4.** Shared concepts stay shared for banks: PBT, tax, PAT, EPS, share capital,
   reserves, total assets and any other row whose definition holds for both. Applicability on
   issuer class restricts only sector-specific rows, layouts and formulas: bank-only rows (interest
   earned, interest expended, provisions and contingencies, deposits, advances, investments as a
   bank line) and non-financial-only rows and formulas (revenue from operations, cost of
   materials, inventories, working-capital formulas).
4. **Discovery, context, extraction, comparison.** Discovery accepts the evidenced bank filing
   family; the engine context carries issuer class; XBRL and PDF mapping entries for the bank rows
   are written from the retained filing; vendor entries from ICICIBANK's Tijori and Screener
   captures, with §6.1 display rules where Tijori bank tables differ.

   *Steps 2 and 4:* Issuer class and accounting framework are separate decisions. The filing form establishes issuer class; the framework requires a declaration whose
   meaning is evidenced for the relevant filing. When the declaration is available only in a
   retained results PDF, its verified issuer, period and basis association and exact declaration
   are carried as framework evidence; a Banking form alone is not a substitute for that
   declaration. Conflicting or unassessed evidence grants no authority. Results keys and every
   ingest/reingest/fallback path use the evidenced framework governing the entity and period at
   the knowledge cutoff, with selected packages required to agree. Supported PDFs join packages
   through the existing hash-pinned intake contract; unsupported PDFs stay retained with an
   explicit limitation.
5. **Refuse the rest.** Any capability the filing does not support (e.g. a statement or segment
   table absent from it) stays refused with a stated reason; nothing is guessed.

**Acceptance.** The grounding record exists with its capture ids, retained before any onboarding
check ran. ICICIBANK onboards as `BANK` with the evidenced framework; an NBFC fixture stays
`UNSUPPORTED`. A compare run on the retained filing period gives values for shared and bank rows
and `NOT_APPLICABLE` for non-financial-only rows. Demonstrate admissions under §6.5 on a rehearsal
copy, with positive admissions for the supported admissible acceptance cells and explicit expected
refusals for unsupported or contested cells. No admission is written on live in this phase. No
BANK vendor-only eligibility is established by this acceptance run; §6.5 row 3 remains unavailable
for BANK. Freeze expected shared/bank value keys and unsupported capabilities from the reviewed
grounding evidence before acceptance, so an entirely refused run cannot pass. Dictionary v4
extends published v3; v1–v3 remain immutable. On a rehearsal copy, reproduce Apar's approved v2/v9
baseline and compare it with v4 under the candidate mapping/extractor versions using the same
retained captures, cutoff and scope, with all required candidate interpretations materialized.
Existing results preserve canonical key, state, value, interval and reason semantics; added rows
have an explicit family/applicability disposition. Use v3 as an intermediate control. This is
numeric regression acceptance, not inherited eligibility: changes to dictionary, mapping or either
vendor extractor create new check classes with no evidence until separately measured. Apar's live
pilot pins do not move in Phase 3. Gate as Phase 1.

## 9. What the five-company test gets, and D3

For each company: onboarding (the bank per §8, NETWEB per §6.2 if its listings show standalone
only), basis-correct vendor capture, mapped vendor values, admission with labels, the fallback
command, and `eqos vendor measure`.

The test supplies evidence toward D3; it does not qualify mappings by itself. A mapping is promoted
to `EQUIVALENCE_DEMONSTRATED` only when ≥5 distinct companies inside that mapping's own
qualification scope (surface, schema, basis, period kind, conditions) carry it and a discriminating
case exists. ICICIBANK is outside every non-financial mapping's scope and a standalone-only NETWEB
outside every consolidated one, so most mappings will not reach five from this test; only mappings
whose sample and discrimination requirements both pass are promoted.

## 10. Document amendments

Made by Phase 1 (Phase 3 for the bank lines), in
`docs/specs/2026-10-11-canonical-financial-data-and-cross-source-comparison.md`:

- **§4, replace** "Vendor observations, including API-document-anchored ones, never get fact
  authority (the API-document bar stays)." **with** "Vendor observations get no fact authority,
  except under VENDOR-1 (`docs/specs/2026-11-06-vendor-first.md` §6.5, owner order 2026-11-05):
  within that spec's pilot scope, a Screener and a Tijori observation that agree may be admitted
  with their own `JSON_ISLAND` / `HTML_TABLE` anchors and a visible label. API-document-anchored
  observations stay barred."
- **Stage 2, replace** "A vendor observation cannot be admitted as a fact (API-document bar
  holds)." **with** "A vendor observation is admitted only under VENDOR-1 §6.5 (API-document bar
  holds)."
- **§8 outcome table, replace** "e.g. bank, NBFC or insurer, a foreign listing, or no Ind AS
  filing" **with** "e.g. NBFC or insurer, a foreign listing, or no filing in a supported
  framework; banks per VENDOR-1 §8" (Phase 3).
- **Stage 4, replace** "A financial-sector issuer gives `UNSUPPORTED`" **with** "An NBFC or
  insurer gives `UNSUPPORTED`" (Phase 3).
- **Out of Scope, replace** the row "Bank, NBFC and insurer row sets" **with** "NBFC and insurer
  row sets" (Phase 3).
- `config/sourcing/sources.yaml` header: the `vendor cross-check` role line becomes "derived
  aggregator whose values are compared with first-party values, and, for Screener and Tijori under
  VENDOR-1, the primary number source within its pilot scope". Role values are unchanged, so
  `test_source_list.py` still holds.
- `CONTEXT.md` gains **Admission label** (the two labels) and **Check class**; the Evidence package
  entry gains one sentence for owner decision 1, kept apart from the DOCS-1 sentence.

## 11. Risks

- **Shared vendor definitions.** Both vendors can define a line the same wrong way; agreement then
  says nothing. Counterexample blocking catches it on first contact with a filing; classes measured
  only on Apar remain exposed.
- **Small sample.** Four clean key-periods is a weak bar, accepted only within owner decision 4.
- **Precision.** Row 1 keeps the vendor value and precision even when the filing is exact; admitted
  numbers carry vendor precision (₹1 crore on Screener).
- **Vendor licence for summaries.** Whether showing numeral-free Tijori summary spans is within its
  terms is not established; the source catalog's role and retention authority gate capture.
- **Bank formats.** Not established until Phase 3 step 1.
- **Template drift.** A relabelled vendor row becomes `UNMAPPED` and fails closed; the existing
  drift check catches it.
