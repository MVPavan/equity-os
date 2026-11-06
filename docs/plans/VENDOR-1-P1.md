# VENDOR-1 Phase 1 Implementation Plan

**Status:** draft, for Sol plan review. **Bead:** `eqos-awnc`.
**Origin:** `docs/specs/2026-11-06-vendor-first.md` §6 (approved, gpt-6.1-sol, round 3,
2026-11-06), with the five implementation notes from Sol's approving review, each placed in its
task. Code facts were read at `7647aff3`; store facts were queried read-only.
**Goal:** Non-bank issuers get vendor-first numbers: Screener and Tijori values that agree are
admitted with a visible label, checked against the filing where one exists, and the filing is
fetched for the requested period when the vendors fail.

**Out of scope:** vendor text (Phase 2); banks, the bank framework and dictionary v4 (Phase 3);
the five-company test (§9); `eqos.vendor_values` in comparison; KPIs and divisions; Upstox beyond
its current diagnostic role; review-queue severities; any mutable eligibility system; NBFCs and
insurers; promoting any mapping to `EQUIVALENCE_DEMONSTRATED`; admitting facts on live.

**Constraints:**
- The migration is `migrations/0047_admission_label.sql`; `0046` stays reserved for `research-4`.
- Committed migrations and frozen manifests are never edited.
- Minimal code: every module traces to a spec section below; no speculative seams or guards.
- Live writes are permanent. A task that writes live first rehearses the same commands on an
  `eqos_test_*` copy, then checks the database after each live write, and stops at the first
  deviation from the rehearsal.
- No vendor body, vendor value or embedded mapping example in committed text, logs or reports;
  the eligibility artifact and phase report hold counts and ids only.
- Never open `stage4_holdout.yaml`, `stage4_manifest.yaml`, `data/holdout/` or
  `data/raw/onboarding/`.
- Files stay under 800 lines. `engine.py` is at 800 and `onboard_cli.py` at 785, so new logic
  goes into new modules beside them.
- Tests follow `.claude/rules/python/testing.md` and the owner policy of 2026-11-05: integration,
  end-to-end and feature tests first; unit tests only for the predicates and admission rows.
- Mypy runs with `--cache-dir=/dev/null`. Long gates run as `systemd-run --user` units
  (learnings: long gates).

**Shape:** Tasks 1–12 are code and land on `main` one commit each after the orchestrator verifies
them (tests, mypy, ruff, the task's acceptance). Nothing in them writes live. Task 13 applies the
migration and re-ingests Apar's retained vendor captures live; Task 14 re-measures Apar and drafts
the eligibility artifact and phase report. **Sol reviews this plan, then once at phase end**
(after Task 14), over the whole phase diff, the live logs and the report, by the loop in
`.claude/rules/core/04-agent-stack.md`. No task is Sol-reviewed on its own. The eligibility
artifact and the phase report are committed only after `APPROVE`.

**Estimate:** about 57 hours elapsed, the author's estimate, not measured. Gates dominate.

| Task | Implementer | Hours |
|---|---|---|
| 1. Migration 0047 and the vendor-first contracts | Sonnet | 2 |
| 2. Tijori display rules and re-ingest | Opus | 3.5 |
| 3. Mapping inventory and standalone entries | Opus | 5 |
| 4. Standalone-only onboarding | Opus | 6 |
| 5. Vendor-only runs and default vendor sides | Opus | 4 |
| 6. Policy and predicates | Opus | 2 |
| 7. Check class, eligibility artifact, `eqos vendor measure` | Opus | 4 |
| 8. One admission path | Opus | 6 |
| 9. Citation and retention | Opus | 4 |
| 10. Display | Sonnet | 2 |
| 11. Fallback workflow | Opus | 6 |
| 12. Document amendments | Sonnet | 1 |
| 13. Live: migrate and re-ingest Apar | orchestrator | 2 |
| 14. Apar re-measurement | Opus, orchestrator runs live | 2.5 |
| Sol phase-end loop, closing review, close-out | — | 7 |

## Readings this plan takes (Sol to rule at plan review)

1. **Issuer class** (§6.6) is read, not stored, in Phase 1: `NON_FINANCIAL` for an entity whose
   `REPORTING_FRAMEWORK` setting was written by onboarding, because `derived_settings._declared`
   writes it only after `financial_rule` passes on the verified XBRL. Phase 3 adds the stored
   `BANK` value. This avoids a settings CHECK change and a live write for Apar.
2. **Fallback outcome storage** (§6.8 "printed and stored with the run id"): 0047 adds one
   append-only table, `eqos.vendor_fallback_outcomes`. §6.5 lists 0047's contents without it, so
   this is an addition to the spec's migration list.
3. **Renderer** (§6.10): no product code calls `read_selected` today. The report path
   (`interface/entry/cli.py` `_admit`) reads `admit_run`'s records, so the label travels on
   `AdmissionRecord` as well as `SelectedFact`.
4. **Refusal codes** (§6.5): `AdmissionRefusal` takes the spec's names. Today's first-party codes
   (`EXTRACTION_NOT_AGREE`, `NOT_SINGLE_REPRESENTATION`, `NO_DIRECT_OCCURRENCE`,
   `KNOWLEDGE_TIME_UNKNOWN`) become the detail of `FILING_UNRESOLVED`, and `OPEN_HIGH` becomes
   `REVIEW_OPEN`. Existing admission tests keep every admitted-value assertion; their refusal
   assertions change only by this mapping.

## File map

| Path | Change | Responsibility |
|---|---|---|
| `migrations/0047_admission_label.sql` | create | §6.5 columns and check, counterexamples, `row_captures` witness branch, fallback outcomes |
| `equity_os/contracts/verification/vendor_first.py` | create | `AdmissionLabel`, `VendorOutcome`, `FilingState`, label texts |
| `config/normalisation/mappings/tijori/v2/display.yaml` | create | per-(section, basis) unit and precision rules |
| `equity_os/extraction/vendors/tijori/vendor_tijori.py` | modify | apply the row's own section rule; version bump |
| `equity_os/verification/comparison/run_config.py` | modify | `VENDOR_EXTRACTORS` pin, mapping-set and policy pins |
| `config/normalisation/mappings/{screener,tijori}/<next>/financials.yaml` | create | new mapping versions with `unmapped:` lists, standalone entries |
| `equity_os/normalisation/mapping/mapping_models.py` | modify | accept the `unmapped:` list |
| `equity_os/interface/commands/sourcing/vendor_surface_cli.py` | modify | register `vendor reingest` and `vendor measure` |
| `equity_os/interface/commands/sourcing/vendor_first_cli.py` | create | the two commands' bodies |
| `equity_os/sourcing/exchange/nse_filings.py` | modify | `collapse`, `qualifies(basis)`, `filing_for` |
| `equity_os/contracts/sourcing/source_catalog.py` | modify | standalone NSE XBRL source and surface |
| `equity_os/companies/onboarding/{discovery,verification,derived_settings}.py` | modify | thread the selected basis |
| `equity_os/extraction/packages/capture_intake.py` | modify | authorise the basis's XBRL source |
| `equity_os/interface/commands/companies/onboard_cli.py` | modify | ingest, vendor adapters, PDF exclusion and compare command on the basis |
| `equity_os/verification/comparison/engine_vendor_context.py` | create | context for a group with no filing package |
| `equity_os/verification/comparison/engine.py` | modify | call it (net zero lines) |
| `equity_os/interface/commands/verification/compare_cli.py` | modify | default vendor sides; `fallback` action |
| `config/verification/vendor_first/policy/v1.yaml` | create | `precision_limit`, `min_clean_key_periods` |
| `equity_os/verification/admission/vendor_first.py` | create | policy loader, T1, filing state, check class |
| `equity_os/verification/admission/eligibility.py` | create | artifact model, load, measure, counterexample reads and writes |
| `equity_os/contracts/measurement/evidence.py` | modify | `PinnedVersions.vendor_first_policy`, `.eligibility` |
| `equity_os/verification/admission/admission.py` | modify | §6.5 rows, labels, vendor bridge, `read_selected` |
| `equity_os/publication/checking/citations.py` | modify | witness branch, label, withdrawal |
| `equity_os/interface/entry/cli.py`, `equity_os/publication/drafting/*`, `equity_os/analysis/thesis_models/{contracts,adapters,render}.py` | modify | label beside every number; sealed-report notes |
| `equity_os/sourcing/exchange/results_filing.py` | create | acquire one period's results XBRL and PDF |
| `equity_os/interface/commands/sourcing/documents_cli.py` | modify | extract the announcements step as a function |
| `equity_os/verification/admission/fallback.py` | create | the four fallback steps and terminal outcome |
| `docs/specs/2026-10-11-canonical-financial-data-and-cross-source-comparison.md`, `config/sourcing/sources.yaml`, `CONTEXT.md` | modify | §10 amendments (Phase 1 lines) |
| `config/verification/vendor_first/eligibility/v1.yaml`, `docs/evidence/vendor-first/phase-1-report.md` | create (Task 14, committed after `APPROVE`) | the reviewed artifact and the measured counts |

Tests live under `tests/equity_os/<bucket>/<sub-bucket>/`, beside the modules they cover.

## Task 1: Migration 0047 and the vendor-first contracts

Goal: A migrated database stores labels, witnesses, eligibility versions, counterexamples and
fallback outcomes, and `row_captures` returns both witnesses' captures for an admission.

Files:
- Create: `migrations/0047_admission_label.sql`, `equity_os/contracts/verification/vendor_first.py`
- Test: `tests/equity_os/storage/database/test_admission_label_migration.py` (`pg`)

Interfaces:
- Produces: `AdmissionLabel` (`CHECKED_AGAINST_FILING`, `VENDORS_AGREE_NOT_CHECKED`) with
  `LABEL_TEXT: Mapping[AdmissionLabel, str]` ("checked against filing", "vendors agree, not checked
  against filing"); `VendorOutcome` (`VENDOR_UNMAPPED`, `VENDORS_DISAGREE`, `VENDORS_IMPRECISE`,
  `VENDORS_AGREE`); `FilingState` (`FILING_ABSENT`, `FILING_FAILED`, `FILING_DIFFERS`,
  `FILING_AGREES`); `FallbackOutcome` (`ADMITTED`, `FILING_UNAVAILABLE`, `FILING_UNRESOLVED`,
  `STILL_REFUSED`). Columns `fact_admissions.label`, `.witness_interpretation_id`,
  `.eligibility_version`; tables `eqos.vendor_counterexamples`, `eqos.vendor_fallback_outcomes
  (id, run_id → runs, entity_id, period_end, basis, outcome, rerun_id NULL → runs, cells jsonb,
  recorded_at DEFAULT eqos.store_now())`.

Approach: As §6.5. Add `label` with the default, then drop the default; existing rows need no
UPDATE, so the row-mutation trigger stays. The check requires a witness and an eligibility version
on `VENDORS_AGREE_NOT_CHECKED` rows. Both new tables are append-only with the existing
`reject_mutation` triggers and runtime `SELECT, INSERT` grants, as 0011 does. `CREATE OR REPLACE`
`eqos.row_captures` from its last definition (0028) with one added `UNION ALL` yielding
`witness_interpretation_id` in the `fact_admissions` branch; nothing else in the body changes.

Verification: the test applies migrations to a fresh `eqos_test_*` database: an existing-shape
insert gets `CHECKED_AGAINST_FILING`; an unchecked row without a witness fails the check; an
UPDATE on a counterexample raises; `row_captures` on an admission with a witness returns both
captures. `eqos db check-live` is not run here (live apply is Task 13).

Dependencies: None.

Risks: the `row_captures` body is copied from 0028; a later migration that changed it would be
silently reverted. The implementer diffs the function as installed in a migrated test database
against 0028's text before replacing it.

## Task 2: Tijori display rules and re-ingest

Goal: Every supported Tijori (section, basis) evidences its unit and precision, unsupported
sections stay `UNKNOWN_UNIT`, and retained captures can be re-ingested under the new extractor.

Files:
- Create: `config/normalisation/mappings/tijori/v2/display.yaml`,
  `equity_os/interface/commands/sourcing/vendor_first_cli.py` (its `reingest` half)
- Modify: `vendor_tijori.py`, `run_config.py` (`VENDOR_EXTRACTORS`), `onboard_cli.py`
  (`TIJORI_DISPLAY` path), `vendor_surface_cli.py` (register `reingest`)
- Test: `tests/equity_os/extraction/vendors/tijori/test_vendor_tijori_display.py` (`retained`)

Interfaces:
- Produces: `TijoriDisplay` becomes `TijoriDisplayRules(rules: tuple[TijoriDisplayRule, ...])`,
  one rule per `(section, basis)` with its own `unit_evidence_ref` and `precision_evidence_ref`;
  `load_tijori_display(path) -> TijoriDisplayRules`; `vendor_tijori.EXTRACTOR_VERSION` bumped;
  `eqos vendor reingest --entity <key> --period-end <date> --basis <basis>`, which runs
  `ingest_vendor_retained` over that entity-period's retained Screener and Tijori financials
  captures under the current extractors and mapping set.

Approach: §6.1, units and precision. Each rule cites a retained capture (the render script and a
measured section), never digits in the island. The extractor picks the rule of the row's own
section and basis; a section without one keeps `UNKNOWN_UNIT`, so `interpret` still refuses it.
`fr_c` gets no rule. The v1 file stays, since frozen pins may name it.

Verification: on retained Apar captures, sections with a rule give zero `INVALID`/`UNIT_MISMATCH`
interpretations; a fixture row in a section without a rule stays `UNKNOWN_UNIT`; a value whose
digits suggest another precision gets the rule's (acceptance 2). The reingest command on an
`eqos_test_*` copy adds interpretations under the new versions and leaves older ones untouched.

Dependencies: None.

Risks: Tijori's annual and balance-sheet tables may render with different units from `qt_c`;
each rule needs its own evidence, and a section the evidence does not settle stays unsupported
rather than guessed. Characterization first: record today's `qt_c` output and require it unchanged.

## Task 3: Mapping inventory and standalone entries

Goal: Every native statement label in the retained Apar Screener and Tijori captures (`fr_c`
excepted) has exactly one disposition in the new mapping files, and the known definition
differences cannot vote.

Files:
- Create: the next mapping versions of `config/normalisation/mappings/screener/…/financials.yaml`
  and `…/tijori/…/financials.yaml`, and the mapping-set file that pins them
- Modify: `mapping_models.py` (the `unmapped:` list: label, section, basis, reason), `run_config.py`
  (mapping-set pin)
- Test: `tests/equity_os/normalisation/mapping/test_vendor_inventory.py` (`retained`)

Interfaces:
- Consumes: Task 2's display rules (for the `INVALID` count).
- Produces: mapping-set version `<next>` used by every later task; `UnmappedLabel` model.

Approach: §6.1. Entries default to `EQUIVALENCE_UNPROVEN`. Screener annual interest against
`finance_costs` is `RELATED_NOT_EQUIVALENT` (the 7.7% is not explained). Standalone tables (Tijori
`*_s` sections, the Screener standalone page) get entries; standalone never pairs with
consolidated. Dimensioned entries keep their dimensions. `map_labels` may draft entries; the files
are reviewed, and comparison never reads `vendor_label_proposals`. Labels are standard data, so no
parser or per-company rule is written.

Verification: the test walks every native label in the retained captures and finds exactly one
disposition each; it prints cell counts per disposition (acceptance 1); a label removed from a
file fails it by name. No FY `finance_costs` Screener entry votes (acceptance 12, data half).

Dependencies: Task 2.

Risks: the inventory is large (2,030 Tijori and 210 Screener labels are unmapped today); most
will be `unmapped` with a reason, which is correct. The test must read labels from the captures,
not from the mapping file, or it proves nothing.

## Task 4: Standalone-only onboarding

Goal: An issuer whose listings hold only standalone rows onboards with standalone filings
verified, `STANDALONE_ONLY` basis status and a standalone package; Apar onboards exactly as before.

Files:
- Modify: `nse_filings.py`, `source_catalog.py`, `discovery.py`, `verification.py`,
  `derived_settings.py`, `capture_intake.py`, `onboard_cli.py`, `discovery_origins.py` (standalone
  Screener URL)
- Test: `tests/equity_os/companies/onboarding/test_standalone_onboarding.py` (`pg`, replay fixture)

Interfaces:
- Produces: `nse_filings.collapse(rows) -> tuple[list[ListingRow], bool]` (latest broadcast per
  `(period_end, basis)`, groups with a missing broadcast dropped, tie flag), used by
  `filing_window` and Task 11; `ListingRow.qualifies(basis: str) -> bool`;
  `FilingWindow.basis: Basis`; source id `nse-indas-xbrl-standalone` with surface
  `NSE_XBRL_INSTANCE`; `capture_intake.xbrl_source_id(basis: Basis) -> str`;
  `DerivedSettings.basis: Basis`.

Approach: §6.2, from listing evidence only. Sol note 1: thread the basis through the whole path,
not just the catalog: `instance_state`, `ingest_identity_state` (`PackageBasis`),
`screener_page_state`, `tijori_page_state` (verification.py lines 171, 282, 335), `authorise` and
`_source_id` (capture_intake.py lines 224, 313), and every `Basis.CONSOLIDATED` in `onboard_cli`
(`_ingest`, `_vendor_adapters`, `_screener`, `exclude_pdf`, `compare_command`). Discovery selects
standalone Financials rows only when the window holds standalone rows and no consolidated row; any
consolidated row keeps today's path. Derived settings write the basis status discovery selected,
never a default. Applicability and vendor-side selection already key on basis status and basis;
the test proves it rather than adding code.

Verification: a replay fixture whose listings hold only standalone rows onboards: standalone
XBRL verified, `STANDALONE_ONLY`, a standalone package; a compare run gives its consolidated cells
`NOT_APPLICABLE`, and a consolidated vendor table is never paired with the standalone filing
(acceptance 4). Apar's retained onboarding generation replays to identical states, settings and
package bytes before and after.

Test seams: `discover` over `replay_fetch`; `onboard` on an `eqos_test_*` database.

Dependencies: Task 3 (standalone vendor entries).

Risks: characterization first, on Apar's replay. The fixture's standalone XBRL instances are
synthetic copies with standalone scope; the implementer documents how each was made.

## Task 5: Vendor-only runs and default vendor sides

Goal: A company-period with vendor captures and no filing package produces a complete run, and an
ordinary `eqos compare run` with no vendor flags has Screener and Tijori sides.

Files:
- Create: `equity_os/verification/comparison/engine_vendor_context.py`
- Modify: `engine.py` (`_group_periods`, `_context` delegate when no package; net zero lines),
  `compare_cli.py` (`--vendor` default)
- Test: `tests/equity_os/verification/comparison/test_vendor_only_run.py` (`pg`)

Interfaces:
- Produces: `vendor_group_context(...) -> tuple[str | None, ApplicabilityContext]`: currency from
  the vendor occurrences' evidenced unit, framework, fiscal year and basis status from identity
  settings, `disclosed_rows` from the vendor tables' row presence, period kind from the vendor
  column; a missing input raises `RunResolutionError`. `DEFAULT_VENDORS: tuple[tuple[str, str],
  ...]` (Screener page, Tijori financials) in `compare_cli`.

Approach: §6.3. Nothing is defaulted. A dimensioned key whose members cannot be enumerated
without a package refuses with an explicit reason instead of dropping the dimension (§6.1). The
default applies to financial-results runs only, including fallback reruns.

Verification: a fixture with vendor captures and no filing package, occurrence or interpretation
gives a complete run with vendor values and first-party sides `UNAVAILABLE`; a missing currency
refuses the group; a non-enumerable dimensioned key refuses with its reason; a run with no flags
has both vendor sides (acceptance 5, run half). Existing comparison tests pass unchanged.

Dependencies: Task 2.

Risks: default vendors change new run requests, so a new run without flags differs from an old
one; stored runs keep their own identity and replay unchanged, which the existing replay tests
show.

## Task 6: Policy and predicates

Goal: T1 and the filing state are computed exactly as §6.4 defines them, from stored source
intervals and declared precision.

Files:
- Create: `config/verification/vendor_first/policy/v1.yaml`,
  `equity_os/verification/admission/vendor_first.py` (predicates and policy)
- Modify: `evidence.py` (`PinnedVersions.vendor_first_policy: VersionPin | None`, excluded when
  None, as `comparison_semantics` is), `run_config.py` (load and pin)
- Test: `tests/equity_os/verification/admission/test_vendor_first_predicates.py` (unit)

Interfaces:
- Consumes: `VendorOutcome`, `FilingState` (Task 1).
- Produces: `VendorFirstPolicy(version, precision_limit: Decimal, min_clean_key_periods: int)`;
  `load_vendor_first_policy(path) -> VendorFirstPolicy`; `vendor_outcome(row: ResultRow, mapping:
  MappingSet, policy) -> tuple[VendorOutcome, SourceValue | None]` (the chosen, narrower side;
  tie Screener); `filing_state(row: ResultRow, admissible: bool) -> FilingState`.

Approach: §6.4. Each side's interval is the stored `lower`/`upper`. Rule 1 of T1 reads the entry
tier through the mapping set; constructed values are excluded. "Differs" means either vendor.

Verification: unit cases of acceptance 7: disjoint precise → `VENDORS_DISAGREE`; intersecting
coarse → `VENDORS_IMPRECISE`; half-width exactly at the limit → agree; m = 0 both exact → agree,
else imprecise; F disjoint from one vendor only → `FILING_DIFFERS`. Old run manifests serialize
byte-identically (the pin is omitted when None).

Dependencies: Task 1.

Risks: test-first; these are the financial predicates.

## Task 7: Check class, eligibility artifact, `eqos vendor measure`

Goal: The same stored results and arguments give a byte-identical eligibility artifact, and the
command reports three-way coverage per run.

Files:
- Create: `equity_os/verification/admission/eligibility.py`
- Modify: `vendor_first.py` (check class), `vendor_first_cli.py` (its `measure` half),
  `vendor_surface_cli.py` (register `measure`), `evidence.py` (`PinnedVersions.eligibility`,
  excluded when None), `run_config.py`
- Test: `tests/equity_os/verification/admission/test_eligibility.py` (`pg`)

Interfaces:
- Consumes: Task 6's `vendor_outcome`, `filing_state`, policy.
- Produces: `check_class(row, *, mapping, extractor_pins, dictionary_version, policy_version,
  issuer_class) -> str`; `issuer_class(conn, entity_id, cutoff) -> str` (reading 1);
  `EligibilityArtifact`, `ClassEvidence(class_digest, agrees, differs, run_ids, eligible)`;
  `load_eligibility(path) -> EligibilityArtifact`; `measure(pool, available_from) ->
  EligibilityArtifact`; `counterexample_at(cursor, class_digest, cutoff) -> datetime | None`;
  `record_counterexample(cursor, class_digest, result_id, run_id) -> None`;
  `eligible(artifact, class_digest, *, cutoff, mode, cursor) -> bool`;
  `eqos vendor measure --available-from <timestamp> --out <path>`, which also prints
  `COVERAGE <run_id> <expected> <three_way> <refused>` lines.

Approach: §6.6. Only `VENDORS_AGREE` cells count; clean needs `FILING_AGREES`; dedup by
`key_digest`. The command refuses an `available_from` earlier than the latest recorded time of any
counted run, writes it into the file, and records its code version. In `AS_KNOWN`, a cutoff before
`available_from` sees no eligibility; a class with any counterexample at or before the cutoff is
not eligible. The expected coverage set comes from reviewed mappings with full keys (§6.11 #3).

Verification: two runs of the command on the same store and arguments give identical bytes;
`VENDORS_IMPRECISE` key-periods add zero clean observations even with `FILING_AGREES`; an early
`available_from` is refused (acceptance 8, artifact half; acceptance 3, coverage half).

Dependencies: Tasks 1, 6.

Risks: the digest must take every listed component, or incompatible evidence is reused; a unit
test changes each component in turn and expects a new class.

## Task 8: One admission path

Goal: `admit_run` admits by §6.5's rows with labels, records counterexamples before any row, and
`read_selected` returns labelled facts and drops blocked unchecked ones for later cutoffs only.

Files:
- Modify: `equity_os/verification/admission/admission.py`
- Test: `tests/equity_os/verification/admission/test_vendor_first_admission.py` (`pg`); the
  existing `test_admission.py` (refusal mapping only, reading 4)

Interfaces:
- Consumes: Tasks 6 and 7, `AdmissionLabel` (Task 1).
- Produces: `AdmissionRefusal` members `REVIEW_OPEN`, `FILING_UNRESOLVED`, `CHECK_REQUIRED`,
  `VENDOR_UNMAPPED`, `VENDORS_DISAGREE`, `VENDORS_IMPRECISE`, `NOT_REPORTED`;
  `FilingFailure` (today's four first-party codes); `AdmissionOutcome.refusals:
  tuple[tuple[str, AdmissionRefusal, FilingFailure | None], ...]`; `AdmissionOutcome.triggers:
  tuple[tuple[int, date, Basis], ...]` (rows 4 and 6 grouped); `AdmissionRecord.label`,
  `.witness_interpretation_id`; `SelectedFact.label`; `BRIDGE_VERSION = "admission-bridge/2"`;
  `read_selected(store, key, *, cutoff, mode, pool: ConnectionPool) -> SelectedFact | None`.

Approach: §6.5. Today's `_decide` becomes the filing-admissible test. Counterexamples for every
`VENDORS_AGREE` + `FILING_DIFFERS` cell are written first in the same serializable transaction.
Rows 0a and 0b run before any source is chosen. Row 1 keeps the vendor value and its precision;
rows 2 and 5 the filed value. The vendor bridge anchors Tijori as `JSON_ISLAND` and Screener as
`HTML_TABLE` (a missing anchor field raises `BridgeError`), takes the later of the two witnesses'
capture-registration times as knowledge time, leaves occurrences `UNKNOWN`, and stores the other
witness. `read_selected` takes the label from the latest admission of the selected row at or
before the cutoff; the knowledge-time witness stays the earliest, as in `citations.py`.
Retention withdrawal (Task 9) also applies here: an expired or licence-ended witness returns
nothing.

Verification: one case per row of §6.5, including: failed filing plus agreeing vendors refuses
`FILING_UNRESOLVED`; an agreeing filing keeps the vendor value and precision; agreeing vendors, a
differing filing and an open `HIGH` item refuse `REVIEW_OPEN` and still record the counterexample
(acceptance 6). A version mismatch gives `CHECK_REQUIRED`; a counterexample in run N blocks row 3
in run N+1 with the artifact unchanged, and `read_selected` drops the earlier unchecked fact for
later cutoffs only (acceptance 8). The Task 5 vendor-only fixture gives a row-3 admission under a
pinned eligibility fixture (acceptance 5). No FY `finance_costs` cell is admitted under row 3
(acceptance 12). Existing admission tests pass with `CHECKED_AGAINST_FILING`, and historical
cutoffs return the same facts as before.

Test seams: `admit_run`, `read_selected` on `eqos_test_*`.

Dependencies: Tasks 1, 5, 6, 7.

Risks: the riskiest task. Test-first, from the §6.5 table; characterization of the current
first-party admissions on the existing fixtures before the edit.

## Task 9: Citation and retention

Goal: A sealed report citing a row-3 fact, and a calculation using it, both resolve with the
label while both witnesses are retained and licensed, and stop resolving for new reports once
either is not.

Files:
- Modify: `citations.py` (`_admitted`, the calculation path), the sealed-report renderer
  (`publication/drafting/display.py` `render_claim`, confirmed against `ledger export`)
- Test: `tests/equity_os/publication/checking/test_vendor_citation.py` (`pg`)

Interfaces:
- Consumes: Task 8's columns and `SelectedFact.label`.
- Produces: `ResolvedCitation.label: AdmissionLabel`; `weakest(labels) -> AdmissionLabel`
  (`VENDORS_AGREE_NOT_CHECKED` is weaker); notes "vendor source expired ‹date›" and "class later
  contradicted by a filing on ‹date›".

Approach: §6.7 and §6.9. An admission with a witness resolves when both captures are retained
catalog captures of the two vendor-primary sources (`eqos.capture_state` in `RETAINED` or
`RESTORED`, no `licence_ends` row) and the class has no counterexample at or before the report's
cutoff. Nothing else in resolution changes. Sealed reports keep their stored values; a later
render adds the note.

Verification: acceptance 9 (both resolve with the label; `row_captures` returns both witnesses'
captures) and 10: expiry, and separately licence end, of either witness withdraws the admission
for a new report; the sealed report keeps its value with the note; a backup restore does not
revive it; a hash-matched re-fetch does.

Dependencies: Task 8.

Risks: the restore and re-fetch behaviour comes from migrations 0028–0031; the test uses their
existing commands rather than new code.

## Task 10: Display

Goal: Every rendered number carries its label, and a fact without one fails the render.

Files:
- Modify: `interface/entry/cli.py` (`_admit`), `publication/drafting/earnings_update.py`,
  `analysis/thesis_models/{contracts,adapters,render,prompt}.py`
- Test: extend the existing Stage 2 end-to-end (`test_data_stage2_e2e.py`) with a label
  assertion; one render test for the missing-label failure

Interfaces:
- Consumes: `AdmissionRecord.label`, `LABEL_TEXT`.
- Produces: thesis `Fact.label: AdmissionLabel` beside `single_sourced`.

Approach: §6.10, reading 3. `_admit`'s package-member check stays for filed values; for a
vendor-valued record it checks the result row's first-party representative capture instead,
reached through `result_id`, so a row-1 fact is not refused for being a vendor capture.

Verification: acceptance 13 on the end-to-end render; a fact built without a label raises.

Dependencies: Task 8.

Risks: the member-check change is the one guard this task alters; Sol reads it at phase end.

## Task 11: Fallback workflow

Goal: `eqos compare fallback --run <id>` acquires, for each triggered company-period only, the
results XBRL and PDF, ingests, reruns with vendor sides, admits, and stores one terminal outcome.

Files:
- Create: `equity_os/sourcing/exchange/results_filing.py`,
  `equity_os/verification/admission/fallback.py`
- Modify: `nse_filings.py` (`filing_for`), `documents_cli.py` (extract the announcements step),
  `compare_cli.py` (`fallback` action)
- Test: `tests/equity_os/verification/admission/test_fallback.py` (`pg`, `retained`, replay fetch)

Interfaces:
- Consumes: `collapse` and `xbrl_source_id` (Task 4), `AdmissionOutcome.triggers` (Task 8),
  `DEFAULT_VENDORS` (Task 5), `vendor_fallback_outcomes` (Task 1).
- Produces: `nse_filings.filing_for(rows, period_end, basis) -> ListingRow | None` (None on a tie
  or missing broadcast); `acquire_results(conn, store, fetch, *, entity_id, symbol, isin,
  period_end, basis) -> ResultsFiling | None`; `announcement_documents(conn, store, fetch, *,
  entity_id, symbol, isin, span) -> list[CaptureReference]`; `run_fallback(pool, run_id, ...) ->
  list[tuple[int, date, Basis, FallbackOutcome]]`.

Approach: §6.8, with Sol notes 2–5.
- XBRL: both listings through `acquiring_fetch` and `register_capture`; `filing_for` reuses the
  collapse rule with the requested period end and basis only, dropping `filing_window`'s six-quarter
  and consolidated filters (note 5).
- PDF: `announcement_documents` is the announcements listing and document step for one issuer and
  one span (period end to seven days after the XBRL broadcast), kept to `RESULTS_CATEGORIES`
  results PDFs of that span. It does not transplant `_Pass._documents`, which walks several
  document kinds and every stored observation (note 3). `_Pass` calls the extracted function, so
  `documents backfill` behaves as before.
- Ingest: the XBRL entry comes from `onboard_cli.package_manifest`; the PDF needs its own manifest
  entry, plus a results-PDF declaration whose `sha256` equals the acquired document's (note 2,
  `capture_intake.py` lines 307, 321), and joins the package only when the issuer config has a
  `pdf_parse` block; otherwise the package is XBRL-only and the PDF stays retained (note 4).
  `ingest_first_party` takes the requested basis.
- Compare and admit: a fresh run with default vendors, then `admit_run`.
No retries beyond the acquisition layer's. Entity, symbol, ISIN, period and basis come from the
triggering run, so no other issuer is fetched and watchlist coverage is unchanged.

Verification: acceptance 11 on an `eqos_test_*` copy with a replay fetch: an Apar period whose
filing is withheld from the first run ends `ADMITTED` after acquiring that period's XBRL and PDF
only; an unavailable filing ends `FILING_UNAVAILABLE` with its cells still refused; the fetch log
names no other issuer or period; coverage tables are unchanged. `documents backfill`'s existing
tests pass unchanged.

Test seams: the `compare fallback` command and the fetch log.

Dependencies: Tasks 4, 5, 8.

Risks: characterization first for the extracted documents step. The issuer-config PDF declaration
is per issuer; for an issuer without `pdf_parse`, the outcome rests on XBRL alone, as the spec
allows.

## Task 12: Document amendments

Goal: The data spec, source list header and glossary say what Phase 1 built.

Files:
- Modify: `docs/specs/2026-10-11-canonical-financial-data-and-cross-source-comparison.md` (§4 and
  Stage 2 lines only), `config/sourcing/sources.yaml` (header role line), `CONTEXT.md`
  (**Admission label**, **Check class**, one Evidence-package sentence for owner decision 1)

Approach: §10's Phase 1 replacements, verbatim. The §8, Stage 4 and Out-of-Scope lines wait for
Phase 3.

Verification: `test_source_list.py` passes; the changed YAML loads; every linked path exists.

Dependencies: Task 8 (names settled).

Risks: none beyond wording.

## Task 13: Live: migrate and re-ingest Apar

Goal: Live has migration 0047 and Apar's retained Screener and Tijori captures interpreted under
the new extractor and mapping set, with no other change.

Files: none committed. Rehearsal and live logs in `scratchpad/vendor-first/live-1/`.

Approach, in order, with the main checkout on the tip that holds Tasks 1–12:
1. **Rehearse.** Restore the latest backup set into an `eqos_test_*` database (`eqos db
   restore`). Record table counts. Apply 0047 (`eqos db migrate`), record the delta; run `eqos
   vendor reingest` for each Apar period end with retained vendor financials captures (the list is
   computed by a read-only query and saved), record the delta. Expected: only the 0047 objects,
   then only occurrences, interpretations, attempts and version pins rise.
2. **Live,** through `lq.sh`, the same commands one at a time. After each: `eqos db check-live`,
   counts, and the delta compared with the rehearsal's. Stop at the first deviation and report.
3. Drop the rehearsal database.

Verification: each live delta equals its rehearsal delta; `check-live` passes after each step;
interpretations under the new versions show zero Tijori `INVALID`/`UNIT_MISMATCH` in sections
with a rule.

Dependencies: Tasks 1–12 committed.

Risks: permanent writes. Rollback is not possible for the rows; a wrong extractor version means a
new version and another re-ingest, never an edit.

## Task 14: Apar re-measurement

Goal: Code computes, from fresh live runs, Apar's three-way coverage, outcome counts and the
eligibility artifact; the phase report states the numbers and no vendor value.

Files:
- Create, committed only after Sol's `APPROVE`: `config/verification/vendor_first/eligibility/v1.yaml`,
  `docs/evidence/vendor-first/phase-1-report.md`. Not committed: run logs in
  `scratchpad/vendor-first/measure-2/`.

Approach:
1. **Rehearse** on an `eqos_test_*` restore taken after Task 13: one `eqos compare run` with no
   vendor flags per Apar (period end, consolidated), as known, under the new pins; then `eqos
   vendor measure --available-from <now>`. Record the deltas (runs, results, source values, pairs,
   queue items, version pins only).
2. **Live:** the same runs one at a time, each followed by `check-live`, counts and the delta
   check; stop at the first deviation. No `admit_run` on live.
3. **Measure:** `eqos vendor measure` on live, read-only, with `--available-from` fixed before
   the run and later than every counted run. The phase report is generated by code from the
   command's output and read-only queries: counts per disposition (acceptance 1), coverage per run
   (acceptance 3), T1 outcomes, filing states, classes eligible and their key-period counts, and
   the comparison with §5's figures. Every number in the report comes from that output.

Verification: rerunning `measure` gives identical bytes; the report's figures match the
command's output line for line; `git status` shows only the two drafted files.

Dependencies: Task 13.

Risks: live runs are permanent. If coverage is thin (few three-way cells), the report says so;
nothing is tuned to raise it.

**Then: Sol phase-end review** of the phase diff (Tasks 1–12), the Task 13–14 logs, the drafted
artifact and report, by the loop in `.claude/rules/core/04-agent-stack.md`, then one fresh
closing review. Fix rounds that change code re-run the affected tasks' tests, and Task 14 only if
a finding changes measured results (new runs, never edits). After `APPROVE`: the full gate
(`scripts/verify.sh gate vendor-1-p1`), commit the artifact and report, refresh
`docs/status/dashboard.html`, record the verdict on `eqos-awnc`, and file beads for anything
parked.

## Dependency order

1, 2 and 6 start in parallel. 3 after 2; 5 after 2; 4 after 3; 7 after 1 and 6; 8 after 1, 5,
6, 7; 9, 10 and 12 after 8; 11 after 4, 5, 8; 13 after 1–12; 14 after 13; review after 14.

## Self-review

- **Spec coverage:** §6.1 → T2, T3 (dimension refusal: T5). §6.2 → T4. §6.3 → T5. §6.4 → T6.
  §6.5 → T1, T8. §6.6 → T7, T8. §6.7 → T9. §6.8 → T11. §6.9 → T1 (`row_captures`), T8, T9.
  §6.10 → T10. §10 Phase 1 lines → T12. Acceptance: 1 → T3, T14; 2 → T2; 3 → T7, T14; 4 → T4;
  5 → T5, T8; 6 → T8; 7 → T6; 8 → T7, T8; 9, 10 → T9; 11 → T11; 12 → T3, T8; 13 → T10;
  14 → every task and the final gate.
- **Sol's notes:** 1 → T4; 2, 3, 4, 5 → T11.
- **Placeholders:** none; the mapping-set version is written `<next>` because it is the next free
  number at Task 3, which the implementer reads from the tree.
- **Names:** `collapse`, `xbrl_source_id` (T4) → T11; `vendor_outcome`, `filing_state` (T6) → T7,
  T8; `check_class`, `eligible`, `record_counterexample`, `counterexample_at` (T7) → T8, T9;
  `AdmissionRecord.label` (T8) → T10; `AdmissionOutcome.triggers` (T8) → T11.
- **Gaps named:** issuer class, fallback outcome table, renderer and refusal codes → the four
  readings above, for Sol. Pins for old runs → `exclude_if` in T6 and T7. Live apply of 0047 →
  T13. Dashboard and bead → close-out. Banks, vendor text and the five-company test → later
  phases. Re-extracting other issuers → none exist in the store.
