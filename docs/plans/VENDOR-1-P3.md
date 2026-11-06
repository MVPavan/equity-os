# VENDOR-1 Phase 3 Implementation Plan: banks

**Status:** draft for Sol plan review. **Bead:** `eqos-awnc`.
**Origin:** `docs/specs/2026-11-06-vendor-first.md` §8 (authoritative), with §1–§4 (owner order;
decision 2: ICICIBANK's analysis basis is standalone) and §6.8 step 1 (the raw listing and fetch
helpers). Code facts were read at `19545c8e`. Phase 1 Task 10 (`results_filing.py`,
`nse_filings.filing_for`, the extracted announcements step) is in flight on another branch; this
plan uses the interfaces in `docs/plans/VENDOR-1-P1.md` Task 10.
**Goal:** ICICIBANK onboards as `BANK` under the framework its own filing evidences, and a
comparison run on its retained filing period gives values for shared and bank rows and
`NOT_APPLICABLE` for non-financial-only rows, with Apar unchanged.

**Out of scope:** NBFCs and insurers (stay `UNSUPPORTED`); any bank other than ICICIBANK; bank
eligibility evidence (no `BANK` class is measured, so row 3 of §6.5 cannot apply); report drafting,
thesis models and the Stage 2 report path for a bank; vendor text (Phase 2); moving Apar's pilot
pins (`PILOT_VERSIONS`, `interface/entry/cli.py`) to the new dictionary or mapping set; admitting
facts on live; the five-company test (§9); bank KPIs, segments or divisions beyond what the filed
statements carry (Data Extraction rule).

**Constraints:**
- Grounding comes first, and nothing later presumes a bank filing format. Every task's content that
  depends on the grounding record is written as a branch below and fixed at Task 3.
- Standard filed statements and XBRL lines are code; nothing is derived, estimated or filled
  (CLAUDE.md, Data Extraction). A capability the filing does not carry stays refused with a
  stated reason (§8 step 5).
- The migration takes the next free number at task start (`0049` at `19545c8e`; `0048` is Phase 1's
  `admission_class`). Committed migrations, dictionary versions and mapping sets are never edited.
- Live writes are permanent. Tasks 2, 11 and 13 follow the live protocol below.
- No vendor body, vendor value or embedded mapping example in committed text, logs or reports.
- Never open `stage4_holdout.yaml`, `stage4_manifest.yaml`, `data/holdout/` or `data/raw/onboarding/`.
- Files stay under 800 lines. `engine.py` is at 787 and `onboard_cli.py` at 785: new logic goes into
  new modules beside them.
- Tests follow `.claude/rules/python/testing.md`: integration through public commands first; unit
  tests only for the form classification, issuer applicability and the framework predicate.
- Minimal code: every module traces to §8; no speculative seams.

**Shape:** Task 1 is code; Task 2 grounds live; Task 3 resolves the branches and amends this plan
(Sol reviews the amendment as a plan review). Tasks 4–9 are code, one commit each after the
orchestrator verifies them. Task 10 gates. Task 11 migrates and onboards live; Task 12 writes the
vendor bank mappings from the captures Task 11 retained; Task 13 re-ingests and runs the
acceptance comparison live, with admission on the rehearsal copy only. **Sol reviews this plan, the
Task 3 amendment, then once at phase end**, closed by one fresh critical review.

**Estimate:** a summed task budget of about 58 hours (author's estimate, not measured).

| Task | Implementer | Hours |
|---|---|---|
| 1. Grounding command | Opus | 3.5 |
| 2. Live grounding and the grounding record | orchestrator, Opus drafts the reading | 3 |
| 3. Branch resolution (plan amendment) | orchestrator | 2 |
| 4. Contracts and migration | Opus | 2 |
| 5. Bank onboarding | Opus | 7 |
| 6. Dictionary v4 and issuer applicability | Opus | 6 |
| 7. Engine context and run framework | Opus | 5 |
| 8. First-party bank mappings, mapping set v10 | Opus | 5 |
| 9. Document amendments | Sonnet | 1 |
| 10. Pre-live gate | orchestrator | 2 |
| 11. Live: migrate, onboard ICICIBANK | orchestrator | 3 |
| 12. Vendor bank mappings, mapping set v11 | Opus | 4 |
| 13. Live: re-ingest, compare; rehearsal admission | orchestrator | 4 |
| Sol loops (Task 3 amendment, phase end), closing review | — | 10 |

## Readings (the plan's, for Sol to rule on)

1. **Grounding is entity-free.** The store holds no ICICIBANK entity, and Phase 1's
   `announcement_documents` takes an `entity_id` and writes entity-bound intake rows
   (`documents_cli._Pass`). Grounding therefore uses only the request-level helpers:
   `nse_filings.listing_url`, `listing_rows`, `filing_for` (Phase 1 Task 10), `discovery.acquiring_fetch`
   and `register_capture`, and for the PDF `first_party_documents.nse_listing_url`, `listing_rows`,
   `classify_announcement`, `observed_link` and `document_request`. No entity, intake or document
   row is written.
2. **The grounding XBRL needs a neutral source.** The catalog's XBRL sources are
   `nse-indas-xbrl-consolidated` / `-standalone` (`source_catalog.py`), `FIRST_PARTY`. Registering a
   bank instance there would label it Ind AS and make it interpretable. Grounding adds one
   identity-role surface, `("nse-xbrl-grounding", "NSE_XBRL_INSTANCE")`, `Representation.XBRL`,
   `SourceRole.IDENTITY`, exchange rights: retained, never interpreted, granting no onboarding
   authority (§8 step 1). The PDF uses the existing DOCS-1 `nse-documents` surface. Onboarding
   (Task 11) fetches its own instances through discovery under the first-party source Task 5 adds.
3. **Analysis basis is a setting, apart from basis status.** No analysis-basis field exists. Task 4
   adds `SettingKey.ANALYSIS_BASIS`, written at onboarding from an `OWNER_DECISION` evidence input
   (the spec file's path and sha256, decision 2). Basis status keeps meaning "bases the issuer
   reports", from the listing (Task 5).
4. **Issuer class is a setting for new onboardings; Apar keeps reading 1.** Task 4 adds
   `SettingKey.ISSUER_CLASS`, which Task 5 writes from the filing's IntegratedFinance form.
   `vendor_first.issuer_class` returns the `ISSUER_CLASS` setting when one is recorded with
   `DISCOVERY` evidence by the cutoff, else Phase 1's reading-1 rule (`NON_FINANCIAL` on an
   `IND_AS` `DISCOVERY` setting). Apar's live rows are not touched.
5. **Issuer applicability is consulted only where declared.** Dictionary v1–v3 rows declare none
   and decide exactly as today; a v4 row declares its issuer classes, and a v4 run whose group has
   no resolved issuer class refuses the group (nothing defaulted, as §6.3).
6. **"Apar unchanged under v4"** means: an Apar run under dictionary v4 (and mapping set v10/v11)
   gives, for every row present under its live baseline (dictionary `v2`, mapping set `v9`), the
   same state, value, interval and reason; every row v3 or v4 adds is either absent from the
   financial-results run or `NOT_APPLICABLE` by the issuer-applicability rule. Checked on an
   `eqos_test_*` copy, never by live runs.
7. **Admission evidence is from the rehearsal copy.** Phase 1 does not admit on live; this phase
   keeps that. "Admissions under §6.5" is shown by `admit_run` on Task 13's rehearsal copy and by
   the integration test, never on live.

## Conditional branches (fixed at Task 3 from the grounding record)

Each branch names the record field that decides it and what each arm changes. An arm not listed
here stops the phase at Task 3 for a plan amendment.

| # | Decided by | Arm | Changes |
|---|---|---|---|
| B1 | framework declaration (XBRL text blocks, PDF notes, page and quote) | **B1a** an existing `AccountingFramework` value's declaration phrase is printed | no enum change; Task 5 verifies that value |
| | | **B1b** another framework is declared (inferred: Banking Regulation Act Third Schedule, RBI) | Task 4 adds one `AccountingFramework` value named for the declaration; Task 5 adds its phrases to `FRAMEWORK_DECLARATIONS` with the quote's page cited |
| | | **B1c** no framework is declared anywhere | stop: framework stays `UNKNOWN`, ICICIBANK is refused, Task 3 amends the plan |
| B2 | IntegratedFinance form namespace segment | **B2a** `IntegratedFinance_Banking` | Task 5 maps form `Banking` → `BANK` |
| | | **B2b** any other form | stop at Task 3 |
| B3 | element namespace of the facts | **B3a** a registered `in-capmkt` revision (`xbrl_taxonomies._ALL_TAXONOMIES`) | Task 8 adds bank entries to a new `xbrl/v6/in_capmkt_banking.yaml` under that `schema_identity` |
| | | **B3b** an unregistered namespace | Task 8 also registers a `TaxonomySpec` and the file uses the new `schema_identity` |
| B4 | identity facts present (name, ISIN, symbol, scrip, scope, period-end concepts) | **B4a** as for Ind AS filers | no identity change |
| | | **B4b** the issuer is named in another concept (HDFCBANK files `NameOfBank`, `d6-capability.md` note 4) or another concept differs | Task 5 reads the evidenced concept for the `BANK` form only |
| B5 | bases on the listings | **B5a** consolidated and standalone | Task 5: discovery selects standalone filings (analysis basis), basis status `CONSOLIDATED_AND_STANDALONE` |
| | | **B5b** standalone only | §6.2 path unchanged: `STANDALONE_ONLY` |
| | | **B5c** consolidated only | stop: decision 2 is unsatisfiable; owner question |
| B6 | listing row `type` of the bank's integrated rows | **B6a** `Integrated Filing- Financials` | no change |
| | | **B6b** another value | Task 5 widens `ListingRow.qualifies` to the evidenced value for that form only |
| B7 | results PDF text layer | **B7a** text layer with the statement lines | Task 8 adds `pdf/v3/results_layout_banking.yaml` entries for lines the layout prints; ICICIBANK gets a `pdf_parse` config |
| | | **B7b** no text layer, or the layout cannot be read as standard data | PDF stays retained, package is XBRL-only (§6.8 step 2), PDF claims `NOT_ASSESSED` |
| B8 | statements and lines in the XBRL (P&L, balance sheet, segment, per period kind) | per statement | present → mapped in Task 8; absent → refused with reason (§8 step 5), dictionary rule `when_statement_present` |
| B9 | vendor tables in Task 11's captures (sections, units, labels) | **B9a** Tijori bank sections carry units a §6.1 rule can evidence | Task 12 adds `display.yaml` rules for them |
| | | **B9b** no evidencing unit | those sections stay `UNKNOWN_UNIT` and fail closed |
| B10 | rounding level and currency facts (`derived_settings._declared`) | **B10a** present as for Ind AS filers | no change |
| | | **B10b** under other concepts or absent | Task 5 reads the evidenced concepts; absent → derived settings refuse (no default) |

## File map

| Path | Change | Task | Responsibility |
|---|---|---|---|
| `equity_os/companies/onboarding/grounding.py` | create | 1 | acquire, register and describe one issuer's latest results XBRL (each listed basis) and PDF |
| `equity_os/interface/commands/companies/ground_cli.py` | create | 1 | thin `eqos onboard ground` handler |
| `equity_os/contracts/sourcing/source_catalog.py` | modify | 1, 5 | `NSE_XBRL_GROUNDING` identity surface (1); bank first-party XBRL sources (5) |
| `docs/evidence/vendor-first/icicibank-grounding.md` | create | 2 | the grounding record: capture ids, hashes, code-read structure, cited reading |
| `docs/plans/VENDOR-1-P3.md` | modify | 3 | branch resolution |
| `equity_os/contracts/companies/issuer_class.py` | create | 4 | `IssuerClass` (`NON_FINANCIAL`, `BANK`) |
| `equity_os/companies/identity/identity_seed.py` | modify | 4 | `SettingKey.ISSUER_CLASS`, `ANALYSIS_BASIS`; `EvidenceInputKind.OWNER_DECISION` |
| `equity_os/contracts/measurement/observation.py` | modify | 4 (B1b) | one `AccountingFramework` value |
| `migrations/0049_issuer_class.sql` | create | 4 | settings-key and evidence-kind CHECKs |
| `equity_os/companies/onboarding/{verification,discovery,derived_settings}.py`, `equity_os/sourcing/exchange/nse_filings.py` | modify | 5 | form classification, framework, identity, analysis-basis selection, basis status |
| `equity_os/extraction/packages/member_identity.py`, `capture_intake.py` | modify | 5 | framework phrases (B1b); authorise the bank XBRL source |
| `equity_os/companies/onboarding/bank_onboarding.py` | create | 5 | analysis-basis and issuer-class inputs for onboarding (keeps `onboard_cli.py` under 800) |
| `equity_os/verification/admission/vendor_first.py` | modify | 5 | `issuer_class` per reading 4 |
| `config/normalisation/dictionary/v4/*` | create | 6 | v3 plus issuer applicability and bank rows |
| `equity_os/normalisation/dictionary/{dictionary,applicability}.py` | modify | 6 | `issuer_applicability`, context `issuer_class`, the decision step |
| `equity_os/verification/comparison/engine_issuer_context.py` | create | 7 | per-entity framework and issuer class from settings |
| `equity_os/verification/comparison/{engine,engine_vendor_context,run_family}.py` | modify | 7 | use it (engine net ≤ +10 lines) |
| `equity_os/interface/commands/extraction/evidence_cli.py`, `onboard_cli.py`, `interface/commands/sourcing/vendor_reingest.py`, `verification/comparison/fact_view.py` | modify | 7 (B1b) | framework from the entity's setting, not the `IND_AS` constant |
| `config/normalisation/mappings/xbrl/v6/in_capmkt_banking.yaml`, `pdf/v3/results_layout_banking.yaml` (B7a), `mappings/v10.yaml` | create | 8 | bank first-party entries; mapping set v10 = v9 + these |
| `equity_os/extraction/xbrl/xbrl_taxonomies.py` | modify | 8 (B3b) | register the namespace |
| `config/normalisation/mappings/{screener/v5,tijori/v6}/financials.yaml`, `tijori/v6/display.yaml` (B9a), `mappings/v11.yaml` | create | 12 | bank vendor entries and `unmapped:` lists; mapping set v11 = v10 + these |
| `docs/specs/2026-10-11-canonical-financial-data-and-cross-source-comparison.md`, `CONTEXT.md` | modify | 9 | §10 Phase 3 lines; **Issuer class**, **Analysis basis** |
| `docs/evidence/vendor-first/phase-3-report.md` | create (Task 13, committed after `APPROVE`) | 13 | measured counts, no vendor value |

Version numbers are the next free at `19545c8e`; the implementer re-reads the tree at task start.
Tests live under `tests/equity_os/<bucket>/<sub-bucket>/` beside the modules they cover.

## Task 1: Grounding command

Goal: `eqos onboard ground SYMBOL` acquires and retains, for the latest listed results period, each
listed basis's integrated XBRL instance and that period's results PDF, registers every body as a
capture, and prints a structure-only description, without writing any entity, onboarding,
settings, package or interpretation row.

Files:
- Create: `equity_os/companies/onboarding/grounding.py`, `equity_os/interface/commands/companies/ground_cli.py`
- Modify: `source_catalog.py` (`NSE_XBRL_GROUNDING`), the CLI registration beside `add_onboard_parser`
- Test: `tests/equity_os/companies/onboarding/test_grounding.py` (`pg`, replay fetch over the
  retained HDFCBANK dev fixtures as a stand-in bank)

Interfaces:
- Consumes: `listing_url`, `listing_rows`, `LEGACY_LISTING`, `INTEGRATED_LISTING`,
  `filing_for(rows, period_end, basis) -> ListingRow | None` (Phase 1 Task 10); `acquiring_fetch`,
  `replay_fetch`, `register_capture`, `EQUITY_MASTER_URL`, `master_rows`; `first_party_documents.nse_listing_url`,
  `listing_rows`, `classify_announcement`, `observed_link`, `document_request`, `RESULTS_CATEGORIES`.
- Produces: `ground(store, pool, fetch, symbol) -> Grounding`; `Grounding` (frozen):
  `symbol`, `isin`, `period_end`, `bases: tuple[Basis, ...]`, `captures: tuple[GroundedCapture, ...]`
  (unit, url, `capture_ref_id`, sha256), and `structure: GroundedStructure` — per instance: schemaRefs,
  root namespace URIs, IntegratedFinance form segments, element namespaces, the sorted local names
  of facts (no values), text-block concepts; per PDF page: whether a text layer exists and its
  lines matching any `FRAMEWORK_DECLARATIONS` phrase or the words "prepared in accordance with".

Approach: master row → ISIN; both listings; the latest period end with any qualifying-or-not
integrated row; `filing_for` per basis present (a tie or missing broadcast is printed, not
resolved); fetch each `xbrl_url`; announcements listing over period end to seven days after the
latest broadcast; results-category document fetched. All requests go through `acquiring_fetch` and
are registered under the surfaces of reading 2. The structure is read by code from the retained
bytes (lxml over the instance, `pdf_source.load_pdf` over the PDF); the command writes it as JSON to a path
argument. No interpretation, no mapping set, no financial rule.

Verification: the test grounds the replayed bank and asserts the capture rows, that no row exists
in `entities`, `onboarding_records`, `settings_records`, `filing_packages` or `interpretations`,
and that the structure JSON names the `Banking` form and no Ind AS declaration (the existing
`test_identity_namespace.py` pin on the same fixture). A replay missing the PDF ends with the XBRL
retained and the PDF reported absent. Ruff, mypy strict on the touched modules.

Dependencies: Phase 1 Task 10 on `main` (`filing_for`).

Risks: the announcements listing may hold several results documents in the span; the command
retains every results-category PDF of the span and lists them, choosing none.

## Live protocol (Tasks 2, 11 and 13)

Phase 1's live protocol (`VENDOR-1-P1.md`, "Live protocol", steps 1–6) applies unchanged:
command inventory with sha256; baseline `eqos db backup` restored into a fresh `eqos_test_*` copy
whose counts and fingerprints equal live's; after every command, rehearsal and live alike,
`eqos db check-live`, per-table counts, business-key summaries and fingerprints of pre-existing
rows; each command's allowed tables stated in its task; live deltas equal the rehearsal's; live
equals the baseline (counts, fingerprints, ledger, sequences) immediately before the first live
command, else restart from the backup; drop the rehearsal database at the end. Scripts extend
`scratchpad/live-run-1/{counts,delta}.py`. Logs in `scratchpad/vendor-first/live-p3-<n>/`.

**Phase 1 windows.** No Phase 3 live task runs between a Phase 1 Task 13 or 14 baseline and its
last live command, or the reverse: each would see the other as drift (protocol step 5). Task 11
also requires Phase 1 Task 13 done (0047 and 0048 applied live).

## Task 2: Live grounding and the grounding record

Goal: ICICIBANK's latest results XBRL (each listed basis) and results PDF are retained in live, and
`docs/evidence/vendor-first/icicibank-grounding.md` records framework, XBRL schema and taxonomy,
statement layout and bases reported, each claim citing a capture id with element or page and quote,
before any onboarding check runs.

Files:
- Create: `docs/evidence/vendor-first/icicibank-grounding.md`. Not committed: logs and the
  structure JSON in `scratchpad/vendor-first/live-p3-1/`.

Commands, under the live protocol: one `eqos onboard ground ICICIBANK --structure <path>` with live
transport. Allowed: blob store, capture and capture-reference rows for the grounding, master,
listing and document surfaces; nothing else.

Approach: the record's facts section is generated by code from the structure JSON: capture ids,
sha256, form segments, namespaces, schemaRefs, fact local names per statement concept group,
text-layer status per PDF page. The reading section (Opus drafts) states, per branch B1–B8, the
arm the evidence supports, each with its page and quote or element; a code check confirms every
quote is present in the retained capture's text (CLAUDE.md, "a model finds; it does not vouch").
What code cannot confirm (a page with no text layer) reads `NOT_ASSESSED`. The record states the
time of grounding and that no onboarding check had run (no `onboarding_records` row for the ISIN).

Verification: the live protocol passes; the quote check exits 0; a read-only query shows the
capture rows and no ICICIBANK entity; the record's capture ids resolve to retained blobs whose
sha256 match.

Dependencies: Task 1; Phase 1 windows rule.

Risks: a live fetch is permanent and cheap; a failed fetch is retried only by rerunning the whole
command under a fresh baseline. If the PDF is absent from the span, the record says so and B7 is
decided `B7b`.

## Task 3: Branch resolution (plan amendment)

Goal: Every branch B1–B10 is fixed by a cited line of the grounding record (B9 after Task 11), and
this plan says which arm each later task implements.

Files: Modify `docs/plans/VENDOR-1-P3.md` (a "Resolved branches" section; arms not taken are struck
from Tasks 4–8 and 12).

Approach: the orchestrator maps each record line to an arm. A stop arm (B1c, B2b, B5c, or any
evidence outside the table) halts the phase with a written amendment, and only B5c is an owner
question (decision 2). Sol reviews the amendment as a plan review, by the loop in
`.claude/rules/core/04-agent-stack.md`.

Verification: every arm cites a record line; Sol `APPROVE`.

Dependencies: Task 2.

## Task 4: Contracts and migration

Goal: The store and contracts can hold an issuer class, an analysis basis with owner-decision
evidence, and (B1b) the bank framework.

Files:
- Create: `equity_os/contracts/companies/issuer_class.py`, `migrations/0049_issuer_class.sql`
- Modify: `identity_seed.py` (`SettingKey.ISSUER_CLASS`, `SettingKey.ANALYSIS_BASIS`,
  `EvidenceInputKind.OWNER_DECISION`); B1b: `observation.py` (one `AccountingFramework` value);
  `vendor_first.py` (`NON_FINANCIAL` becomes `IssuerClass.NON_FINANCIAL`)
- Test: the existing migration suite (upgrade from 0048, checks reject an unknown key)

Interfaces:
- Produces: `IssuerClass` StrEnum; the two setting keys; the evidence kind; (B1b) the framework value.

Approach: 0049 replaces the `settings_records` setting-key CHECK and the `evidence_inputs` kind
CHECK with the lists plus the new values (as 0022 did); no table, no backfill.

Verification: `scripts/verify.sh` migration tests on `eqos_test_*`; mypy, ruff.

Dependencies: Task 3.

Risks: if Phase 1 or Phase 2 claims 0049 first, take the next free number.

## Task 5: Bank onboarding

Goal: `eqos onboard ICICIBANK` onboards as `BANK` with the evidenced framework, standalone filings
verified as the analysis basis, and the evidenced basis status; an NBFC (retained BAJFINANCE) and an
insurer (HDFCLIFE) still end `UNSUPPORTED` (`FINANCIAL_OR_UNKNOWN_SECTOR`); Apar onboards as before.

Files:
- Create: `equity_os/companies/onboarding/bank_onboarding.py`
- Modify: `verification.py` (`financial_rule` → `issuer_form(instance) -> IssuerClass | None`;
  `framework_state` takes the framework; B4b identity concept), `member_identity.py` (B1b phrases;
  `verify_xbrl_framework` accepts the `Banking` form for the bank framework only), `discovery.py`
  (classification step, analysis-basis selection, bank XBRL source), `nse_filings.py`
  (`filing_window(rows, as_of, basis=None)`: a given basis selects that basis; B6b `qualifies`),
  `derived_settings.py` (framework and `ISSUER_CLASS` from the form; `ANALYSIS_BASIS`; basis status
  from bases listed, not from the selected basis; B10b), `source_catalog.py` and `capture_intake.py`
  (bank XBRL sources per basis, `FIRST_PARTY`), `onboard_cli.py` (one call into
  `bank_onboarding`), `vendor_first.py` (`issuer_class` per reading 4)
- Test: `test_onboarding_verification.py` (existing financial-issuer cases: HDFCBANK case moves to
  the bank route; BAJFINANCE, HDFCLIFE unchanged), `tests/equity_os/companies/onboarding/test_bank_onboarding.py`
  (`pg`, replay of the Task 2 retained ICICIBANK captures plus the vendor pages Task 11 will fetch,
  served from the replay folder)

Interfaces:
- Consumes: `IssuerClass`, setting keys, `OWNER_DECISION` (Task 4); the grounding record (B1, B2,
  B4, B5, B6, B10).
- Produces: `issuer_form(body: bytes) -> IssuerClass | None` (`IndAS` → `NON_FINANCIAL`, `Banking`
  → `BANK`, else `None`); `issuer_class(conn, entity_id, cutoff) -> IssuerClass | None`;
  `XBRL_SOURCES[(IssuerClass, Basis)]`; `onboard --analysis-basis {standalone,consolidated}`
  (required for a `BANK` form, refused for `NON_FINANCIAL`), with `--decision <spec path>` naming
  the owner-decision input.

Approach: the form is read once per instance as today (namespace URI, never the URL prefix,
`d6-capability.md` §2). `None` refuses as today. For `BANK`, discovery selects the analysis basis's
filings (B5a) or the §6.2 path (B5b), and runs the same instance, entity, identity and framework
checks with the bank framework; derived settings write framework, issuer class (`DISCOVERY`
evidence), analysis basis (`OWNER_DECISION` evidence) and basis status from the bases the window
lists (`CONSOLIDATED_AND_STANDALONE` when both, `STANDALONE_ONLY` when standalone only). Ingest
and vendor capture follow the selected basis as today (`onboard_cli` passes `derived.basis`), so
standalone vendor tables are fetched without changing §6.1's trigger.

Verification: replay integration: ICICIBANK → `ONBOARDED` or `PARTIAL` (vendor units may be
unverified on bank pages; B9), settings rows with their evidence kinds, a standalone package; Apar
replay unchanged (existing onboarding tests pass); BAJFINANCE and HDFCLIFE `UNSUPPORTED`; a bank
form without `--analysis-basis` refuses before any write; unit cases for `issuer_form` over the four
retained forms. `issuer_class` returns `NON_FINANCIAL` for Apar's live-shaped provenance and `BANK`
for the new settings.

Dependencies: Task 4.

Risks: characterization first: run the current onboarding suite before editing `discovery.py`.
The HDFCBANK pin tests change meaning (bank no longer refused); the change is stated in the commit,
and the NBFC and insurer pins stay.

## Task 6: Dictionary v4 and issuer applicability

Goal: Under dictionary v4, shared rows apply to both issuer classes, bank-only rows to `BANK` only,
non-financial-only rows and formulas to `NON_FINANCIAL` only, decided before any value; under v1–v3
every decision is unchanged.

Files:
- Create: `config/normalisation/dictionary/v4/*` (v3's nine files, `metadata.yaml` version and
  `scope` line rewritten; bank rows; `issuer_applicability` on family defaults and on rows that
  differ)
- Modify: `dictionary.py` (`DictionaryRow.issuer_applicability: frozenset[IssuerClass] | None`,
  read from family defaults like `basis_applicability`), `applicability.py`
  (`ApplicabilityContext.issuer_class: IssuerClass | None = None`; `ISSUER_RULE_ID =
  "issuer.row_issuer_applicability"`; the check runs after the basis checks)
- Test: `tests/equity_os/normalisation/dictionary/test_issuer_applicability.py` (unit: the decision
  table); the dictionary load tests for v4

Interfaces:
- Consumes: `IssuerClass` (Task 4); grounding record B8 (which statements and lines exist).
- Produces: `DictionaryRow.issuer_applicability`; `ApplicabilityContext.issuer_class`;
  `ISSUER_RULE_ID`; `IssuerContextMissingError` raised when a row declares issuer applicability and
  the context has no class.

Approach: §8 step 3. Shared rows (PBT, tax, PAT, EPS, share capital, reserves, total assets, and
any other row whose v3 `meaning` holds for a bank as the grounding record shows) declare both
classes. Bank-only rows are added only for lines the retained ICICIBANK filing carries (interest
earned, interest expended, provisions and contingencies, deposits, advances, investments as a bank
line, or the record's names), each `meaning` citing the record. Non-financial-only rows and every
formula over them (revenue from operations, cost of materials, inventories, working-capital
formulas in `derived.yaml`) declare `NON_FINANCIAL`. A bank statement the filing lacks gets no row
and no rule (B8). The row decision is not a judgment: each row's classes come from its family
default unless the row names its own; the reviewer checks every override against the record.

Verification: unit cases: shared row × both classes → rule decides; bank row × `NON_FINANCIAL` →
`NOT_APPLICABLE` by `ISSUER_RULE_ID`; v3 row × `BANK` → unchanged decision (not consulted); v4 row ×
`None` → `IssuerContextMissingError`. Integration on retained Apar data (`pg`, `retained`): a run
under dictionary v4 equals the live-shaped v2 baseline per reading 6.

Dependencies: Task 4; Task 3 (B8).

Risks: the v3 → v4 copy must be byte-for-byte except the stated changes; the test diffs the trees.

## Task 7: Engine context and run framework

Goal: A financial-results group resolves its framework and issuer class from the entity's settings
at the cutoff, so a bank group's keys carry the bank framework and its applicability carries
`BANK`; Apar's groups resolve `IND_AS` and `NON_FINANCIAL` exactly as their packages declare.

Files:
- Create: `equity_os/verification/comparison/engine_issuer_context.py`
- Modify: `engine.py` (`self._framework` per group; context gets `issuer_class`),
  `engine_vendor_context.py` (use the same resolver), `run_family.py` (`FINANCIAL_RESULTS.framework`
  becomes `None`: per entity); B1b only: `evidence_cli.py`, `onboard_cli.py`, `vendor_reingest.py`,
  `fact_view.py` take the entity's framework where they pass `AccountingFramework.IND_AS`
- Test: `tests/equity_os/verification/comparison/test_bank_run.py` (`pg`, retained ICICIBANK replay)

Interfaces:
- Consumes: `issuer_class` resolution rule (Task 5), `ApplicabilityContext.issuer_class` (Task 6).
- Produces: `group_identity(inputs, entity_id, cutoff) -> tuple[AccountingFramework, IssuerClass | None]`.

Approach: the framework is the entity's `REPORTING_FRAMEWORK` setting at the cutoff (the vendor-only
path already reads it); a group whose package framework differs refuses, as the package filter does
today. Issuer class follows reading 4 over the loaded settings. The `SHAREHOLDING` family keeps its
fixed `UNKNOWN` framework. `xbrl_parser.py:538` (legacy parser, `IND_AS` hard-coded) is not on the
results-run path and is not touched (noticed, reported).

Verification: Apar comparison suites pass unchanged; the bank run test gives values for shared and
bank rows, `NOT_APPLICABLE` for non-financial-only rows by `ISSUER_RULE_ID`, and refuses a group
under v4 whose entity has no issuer class.

Dependencies: Tasks 5, 6.

Risks: entities in test fixtures without a `REPORTING_FRAMEWORK` setting now refuse; characterize
first and add the setting to fixtures that lack it, never a default.

## Task 8: First-party bank mappings, mapping set v10

Goal: The retained ICICIBANK XBRL (and, B7a, results PDF) interpret its shared and bank lines
`MAPPED` under mapping set v10; lines not mapped are stored `UNMAPPED`; Apar interprets identically
under v10 and v9.

Files:
- Create: `config/normalisation/mappings/xbrl/v6/in_capmkt_banking.yaml`, `mappings/v10.yaml`;
  B7a: `pdf/v3/results_layout_banking.yaml` and ICICIBANK's `pdf_parse` config
- Modify: B3b: `xbrl_taxonomies.py`
- Test: `tests/equity_os/extraction/xbrl/test_bank_mapping.py` (`retained`)

Interfaces:
- Consumes: v4 row ids (Task 6); grounding record (B3, B7, B8).
- Produces: mapping set `v10` = v9 entry files plus the bank files.

Approach: entries from the retained filing only (§8 step 4), each with an `evidence_ref` citing
capture sha, element and context (PDF: page and label). A selector that also matches an Apar element
is refused by the set's uniqueness check; bank entries are scoped by their element names, so Apar's
interpretation does not change. Elements whose meaning the filing does not evidence stay unmapped
with the reason in the file header (as `xbrl/v5`).

Verification: under v10 the retained ICICIBANK instance gives `MAPPED` for every v4 shared and bank
row the record lists; Apar's retained packages give equal interpretation counts per
(representation, status) under v9 and v10.

Dependencies: Task 6; Task 3 (B3, B7, B8).

## Task 9: Document amendments

Goal: The data spec and glossary say what Phase 3 built.

Files: Modify `docs/specs/2026-10-11-canonical-financial-data-and-cross-source-comparison.md` (§8
outcome table, Stage 4, Out of Scope lines, §10 verbatim); `CONTEXT.md` (**Issuer class**:
`NON_FINANCIAL` or `BANK`, read from the filing's IntegratedFinance form; **Analysis basis**: the
basis an owner decision fixes for analysis, apart from the bases an issuer reports).

Verification: every linked path exists; `test_source_list.py` passes.

Dependencies: Task 5 (names settled).

## Task 10: Pre-live gate

Goal: The tip holding Tasks 1 and 4–9 passes `scripts/verify.sh gate vendor-1-p3` (run as a
`systemd-run --user` unit, log and revision saved in `scratchpad/vendor-first/gate-3/`); mypy
strict and ruff clean. Task 12's code reruns the gate before Task 13.

Dependencies: Tasks 4–9 committed.

## Task 11: Live: migrate, onboard ICICIBANK

Goal: Live has 0049 and ICICIBANK onboarded as `BANK`, with its standalone package and vendor
captures retained.

Commands, under the live protocol, main checkout on the Task 10 tip:
1. `eqos db migrate` (0049). Allowed: ledger and the two CHECK constraints.
2. `eqos onboard ICICIBANK --acquire --analysis-basis standalone --decision docs/specs/2026-11-06-vendor-first.md`
   with mapping set v10 and dictionary v4. Allowed: what the rehearsal shows onboarding writing
   (entity, identifiers, onboarding record and units, settings, evidence inputs, captures,
   package, occurrences, interpretations, attempts, version pins).

Verification: protocol passes; read-only queries show `ISSUER_CLASS = BANK` and the framework
setting with `DISCOVERY` evidence, `ANALYSIS_BASIS = STANDALONE` with `OWNER_DECISION` evidence, the
basis status B5 decided, and a standalone package whose XBRL capture sha equals the grounding
record's for that period (if discovery selected it).

Dependencies: Task 10; Phase 1 Task 13 done; Phase 1 windows rule.

Risks: permanent; a wrong setting is superseded by a new record, never edited.

## Task 12: Vendor bank mappings, mapping set v11

Goal: ICICIBANK's retained Screener and Tijori standalone financials captures map their shared and
bank rows under mapping set v11; every native statement label has one disposition (§6.1).

Files:
- Create: `config/normalisation/mappings/screener/v5/financials.yaml`, `tijori/v6/financials.yaml`,
  B9a: `tijori/v6/display.yaml`; `mappings/v11.yaml`
- Test: the Phase 1 inventory test parameterised over the ICICIBANK captures (`retained`); Apar's
  inventory unchanged

Approach: Task 3's B9 resolution first (an amendment line, no Sol round unless an arm stops). Bank
labels whose definition is known to differ from the filed line are `RELATED_NOT_EQUIVALENT`; the
rest `EQUIVALENCE_UNPROVEN`. A Tijori section with no evidenced unit stays without a rule (B9b).
No vendor value in committed text.

Verification: inventory complete for ICICIBANK and unchanged for Apar; Tijori `INVALID`/`UNIT_MISMATCH`
= 0 in sections with a rule; gate rerun (Task 10 rule).

Dependencies: Task 11 (captures), Task 8.

## Task 13: Live: re-ingest, compare; rehearsal admission

Goal: Live has ICICIBANK's vendor captures interpreted under v11 and one comparison run on the
retained filing period with values for shared and bank rows and `NOT_APPLICABLE` for
non-financial-only rows; on the rehearsal copy, `admit_run` gives admissions under §6.5, and Apar's
results under v4 equal its baseline (reading 6).

Commands, under the live protocol:
1. `eqos evidence ingest --mapping-set v11 --dictionary v4` for ICICIBANK's package.
2. `eqos vendor reingest --mapping-set v11 --dictionary v4` for its period end.
3. `eqos compare run --mapping-set v11 --dictionary v4 --basis standalone` for that period (vendor
   sides by default).
Rehearsal-copy only, after command 3: `admit_run` on the run; an Apar `compare run` under v11/v4 per
Apar period with a retained package.

Verification: code reads the run's results: every v4 shared and bank row the record lists has a
`VALUE` result or an explicit refusal reason; every non-financial-only row is `NOT_APPLICABLE` by
`ISSUER_RULE_ID`; rehearsal admissions are rows 1, 2 or 5 or a stated refusal, and no row 3
(no `BANK` eligibility); Apar's rows equal its v2/v9 baseline. The phase report is generated by code
from these outputs (counts and ids only). The acceptance item "the grounding record exists with its
capture ids, retained before any onboarding check ran" is checked by query: every grounding capture
`registered_at` precedes ICICIBANK's first `onboarding_records.recorded_at`.

Dependencies: Task 12 and its gate rerun.

**Then: Sol phase-end review** of the phase diff (Tasks 1, 4–9, 12), the grounding record, the
Task 3 amendment, the gate logs, the Task 2, 11 and 13 logs and the drafted report, by the loop in
`.claude/rules/core/04-agent-stack.md`, then one fresh closing review. After `APPROVE`: commit the
report, refresh `docs/status/dashboard.html`, record the verdict on `eqos-awnc`, file beads for
anything parked.

## Dependency order

1 → 2 → 3 → 4 → {5, 6} in parallel → 7 (after 5, 6); 8 after 6; 9 after 5; 10 after 4–9; 11 after
10; 12 after 11 and 8; 13 after 12's gate rerun; review after 13.

Parallel: 5 and 6 (disjoint files); 8 and 9 alongside 7. Shared files, one writer at a time:
`source_catalog.py` (1, then 5), `vendor_first.py` (4, then 5), `onboard_cli.py` (5, then 7 for
B1b), `nse_filings.py` (Phase 1 Task 10, then 5).

## Interactions

- **Phase 1 Task 10** (in flight): Task 1 consumes `filing_for`; Task 5 edits `nse_filings.py` only
  after Task 10 lands. Phase 1's `announcement_documents` is not used before onboarding (reading 1);
  after Task 11 the fallback route works for ICICIBANK unchanged, with the bank XBRL source chosen
  by `XBRL_SOURCES[(issuer class, basis)]`, which Task 5 must thread into Task 10's
  `results_filing.acquire_results` (it takes the basis today; one call-site change).
- **Phase 1 Task 9** (in flight): touches `interface/entry/cli.py`; Phase 3 does not, and
  `PILOT_VERSIONS` stays `v2`/`v9`.
- **Phase 1 Tasks 13–14** (live, pending): the windows rule above; Task 11 needs 0047/0048 live.
  Phase 1's eligibility artifact holds `NON_FINANCIAL` classes only; the class digest includes the
  dictionary version, so Apar classes under v4 would start with no evidence, which is why Apar's
  pins do not move in this phase.
- **Phase 2** (vendor text, planned separately): no shared code files expected
  (`vendor_surface_claims.py`, `surfaces.yaml`); shared `CONTEXT.md` edits are serialised; migration
  numbers are taken at task start by whichever phase lands first. ICICIBANK text spans need no
  Phase 3 work.

## Open questions (spec silent; recommended reading in bold)

1. Which period does grounding retain? **The latest listed results period, every basis listed for
   it, and that period's results PDF; one period suffices for the record, and discovery fetches
   its own two filings.**
2. Where does the grounding record live, and what does it hold? **Committed
   `docs/evidence/vendor-first/icicibank-grounding.md`: code-generated structure and capture ids,
   plus a cited reading whose quotes code confirms; no values.**
3. How is the bank XBRL registered before its family is established? **Reading 2: a neutral
   identity-role grounding surface; first-party bank sources only after Task 5.**
4. Where are issuer class and analysis basis stored? **Readings 3 and 4: two settings, issuer class
   from `DISCOVERY`, analysis basis from a new `OWNER_DECISION` input.**
5. What is the "Apar unchanged" baseline? **Reading 6: Apar's live pins `v2`/`v9`, row by row;
   v3/v4-added rows absent or `NOT_APPLICABLE`.**
6. Are admissions shown on live? **No (reading 7): rehearsal copy and test; live admission stays
   out of scope as in Phase 1.**
7. Should grounding also capture vendor pages, removing the v10 → v11 step? **No: §8 step 1 names
   XBRL and PDF; onboarding captures the vendor pages, and one extra mapping set is cheaper than a
   second capture route.**
8. How is the bank framework named (B1b)? **From the declaration text the record quotes, chosen at
   Task 3 and ruled by Sol in the amendment review.**
9. Does a bank's results PDF join the package? **Only on B7a with mapping entries for lines whose
   labels the format prescribes; otherwise retained, XBRL-only package.**
10. Does Task 1's code need the full gate before Task 2 writes live? **No: Task 2 writes captures
    only; the affected suites, mypy and ruff suffice, and Task 10 gates everything before the
    schema and onboarding writes.**

## Spec gaps found against the code

1. §8 says bank formats are not established and the store holds no bank capture; true for
   ICICIBANK, but the repo already pins bank evidence from HDFCBANK (`d6-capability.md` §2, notes 4;
   `test_identity_namespace.py`): the `IntegratedFinance_Banking` form, the same `in-capmkt-ent`
   xsd name, `NameOfBank` instead of `NameOfTheCompany`, and no framework declared in the XBRL.
   It does not replace grounding but should shape it (B1, B4).
2. §8 places the framework check in `verification.py`; the predicate and phrases live in
   `extraction/packages/member_identity.py` (`verify_xbrl_framework`, `integrated_ind_as`,
   `FRAMEWORK_DECLARATIONS`), and `IND_AS` is hard-coded in `run_family.RUN_FAMILIES`,
   `engine.RUN_FRAMEWORK`, `evidence_cli.FRAMEWORK`, `onboard_cli.py` (three call sites),
   `vendor_reingest.py`, `fact_view.py` and `xbrl_parser.py:538`.
3. The run framework is fixed per filing family, not per entity; §8 step 4 says only "the engine
   context carries issuer class". Task 7 resolves framework per entity.
4. §6.8's PDF helper is entity-bound, and grounding precedes any entity; the catalog has no XBRL
   source that is not labelled Ind AS (readings 1, 2).
5. Decision 2 has no home: no analysis-basis field exists; `filing_window` always prefers
   consolidated; `derived_settings._BASIS_STATUS` derives basis status from the selected basis, so
   selecting standalone for a bank that reports both would wrongly write `STANDALONE_ONLY`.
6. §6.6 resolves issuer class from Ind AS onboarding provenance (`vendor_first.issuer_class`), which
   cannot yield `BANK`; §8 step 2 says "set from evidence" without saying where it is stored.
7. Dictionary: the latest is v3 and the pilot pins v2, so "v4" is v3 plus banks, and "unchanged" needs
   a baseline. `ApplicabilityRule`/`DictionaryRow` have no issuer-class field (`extra="forbid"`),
   so v4 needs code, not only config; v3's `scope` line says banks are excluded.
8. NBFCs file the `IntegratedFinance_NBFC` form under Ind AS (`_NBFC_INDAS_` instances), so issuer
   class must key on the form, never on the framework; a framework-only rule would admit NBFCs.
9. No migration is named; new setting keys need the `settings_records` CHECK replaced (0049).
10. Acceptance "admissions under §6.5" does not say live or rehearsal; Phase 1 excludes live
    admission. With no `BANK` eligibility, row 3 can never apply to ICICIBANK in Phase 3.
11. §6.1 fetches standalone vendor tables only for `STANDALONE_ONLY` entities; a bank reporting both
    bases is not covered by that trigger (resolved here because onboarding captures on the selected
    basis).

## Self-review

- **Spec coverage:** §8 step 1 → T1, T2; step 2 → T4, T5; step 3 → T6; step 4 → T5 (discovery),
  T7 (context), T8 (first-party mappings), T12 (vendor mappings and display rules); step 5 → T6
  (no row for an absent statement), T8 and T12 (`unmapped` with reasons), B8. §10 Phase 3 lines → T9.
  Acceptance: grounding record before onboarding → T2, T13 query; `BANK` with evidenced framework →
  T5, T11; NBFC `UNSUPPORTED` → T5; compare values / `NOT_APPLICABLE` → T7, T13; admissions → T13
  (rehearsal); Apar unchanged under v4 → T6, T8, T13; gate → T10.
- **Names:** `issuer_form`, `issuer_class`, `XBRL_SOURCES[(IssuerClass, Basis)]` (T5) → T7, Phase 1
  Task 10 call site; `IssuerClass`, setting keys (T4) → T5–T7; `issuer_applicability`,
  `ISSUER_RULE_ID`, `IssuerContextMissingError` (T6) → T7, T13; `group_identity` (T7); `ground`,
  `Grounding` (T1) → T2.
- **Placeholders:** branch-dependent content is named by branch and arm, never left open.
