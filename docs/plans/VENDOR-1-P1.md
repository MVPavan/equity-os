# VENDOR-1 Phase 1 Implementation Plan

**Status:** approved (gpt-6.1-sol APPROVE, plan review round 4, 2026-11-06). **Bead:** `eqos-awnc`.
**Origin:** `docs/specs/2026-11-06-vendor-first.md` §6 (approved, gpt-6.1-sol, round 3,
2026-11-06; amended per plan review 2 at `f137d3d7`), with the five implementation notes from
Sol's approving review, each placed in its task. Code facts were read at `b07e668f`, the report
path (Task 9) again at `b8328040`; store facts were queried read-only.
**Goal:** Non-bank issuers get vendor-first numbers: Screener and Tijori values that agree are
admitted with a visible label, checked against the filing where one exists, and the filing is
fetched for the requested period when the vendors fail.

**Out of scope:** vendor text (Phase 2); banks, the bank framework and dictionary v4 (Phase 3);
the five-company test (§9); `eqos.vendor_values` in comparison; KPIs and divisions; Upstox beyond
its current diagnostic role; review-queue severities; any mutable eligibility system; NBFCs and
insurers; promoting any mapping to `EQUIVALENCE_DEMONSTRATED`; admitting facts on live; a report
path for a quarter with no filing (the Stage 2 draft reads the quarter's XBRL, results PDF and
transcript; see Task 9).

**Constraints:**
- The migration is `migrations/0047_admission_label.sql`; `0046` stays reserved for `research-4`.
- Committed migrations and frozen manifests are never edited.
- Minimal code: every module traces to a spec section below; no speculative seams or guards.
- Live writes are permanent. Tasks 13 and 14 follow the live protocol below.
- No vendor body, vendor value or embedded mapping example in committed text, logs or reports;
  the eligibility artifact and phase report hold counts and ids only.
  **Exception (owner, 2026-11-07; phase-review finding 16):** one vendor reading entered history
  in commit `39ffae57` (a test docstring) and was removed from the tree by `b129905c`. The owner
  chose to keep that history rather than rewrite the unpushed commits; the current tree holds no
  vendor value. The rule stands for all new text.
- Never open `stage4_holdout.yaml`, `stage4_manifest.yaml`, `data/holdout/` or
  `data/raw/onboarding/`.
- Files stay under 800 lines. `engine.py` is at 800, `onboard_cli.py` at 785 and
  `interface/entry/cli.py` at 810, so new logic goes into new modules beside them, and Task 9
  moves `cli.py`'s `_comparison` and `_admit` out rather than growing it.
- Tests follow `.claude/rules/python/testing.md` and the owner policy of 2026-11-05: integration,
  end-to-end and feature tests through public commands first; unit tests only for the predicates,
  the check-class digest and the admission rows.
- Mypy runs with `--cache-dir=/dev/null`. Long gates run as `systemd-run --user` units
  (learnings: long gates).

**Shape:** Tasks 1–11 are code and land on `main` one commit each after the orchestrator verifies
them (tests, mypy, ruff, the task's acceptance). Nothing in them writes live. Task 12 runs the
full gate on the implementation revision. Task 13 applies the migration, re-interprets Apar's
retained first-party packages and re-ingests its retained vendor captures live under mapping set
`v9`; Task 14 re-measures Apar and drafts the eligibility artifact and phase report. **Sol reviews
this plan, then once at phase end** (after Task 14), over the whole phase diff, the Task 12 gate
log, the live logs and the report, by the loop in `.claude/rules/core/04-agent-stack.md`, closed
by one fresh critical review (owner rule; it stays). No task is Sol-reviewed on its own. The
eligibility artifact and the phase report are committed only after `APPROVE`.

**Estimate:** a summed task budget of about 76 hours (the sum of the rows below, not elapsed
time; the author's estimate, not measured). 57 before review 1, 73 after it; review 2 adds Task 9's
reordered report path (+2), the live pre-command checks (+0.5) and the scope exclusion (+0.5).
Gates and the two live tasks dominate.

| Task | Implementer | Hours |
|---|---|---|
| 1. Migration 0047 and the vendor-first contracts | Opus | 3 |
| 2. Tijori display rules, shared fixture, `vendor reingest` | Opus | 3.5 |
| 3. Mapping set v9: inventory and standalone entries | Opus | 5.5 |
| 4. Standalone-only onboarding | Opus | 6 |
| 5. Vendor-only runs, run status, default vendor sides | Opus | 5 |
| 6. Policy, predicates and run pins | Opus | 4 |
| 7. Check class, eligibility artifact, `eqos vendor measure` | Opus | 5 |
| 8. One admission path | Opus | 6.5 |
| 9. Citation, retention, report values and labels | Opus | 12 |
| 10. Fallback workflow | Opus | 7 |
| 11. Document amendments | Sonnet | 1 |
| 12. Pre-live gate | orchestrator | 2 |
| 13. Live: migrate, re-interpret, re-ingest Apar | orchestrator | 4.5 |
| 14. Apar re-measurement | Opus, orchestrator runs live | 4 |
| Sol phase-end loop, closing review, close-out | — | 7 |

## Readings (Sol's rulings, review 1)

1. **Issuer class** (§6.6) is read, not stored, in Phase 1. Ruling: accepted with a condition.
   `issuer_class(conn, entity_id, cutoff)` returns `NON_FINANCIAL` only on positive onboarding
   provenance known at the cutoff: an `onboarding_records` row for the entity with outcome
   `ONBOARDED` or `PARTIAL`, and a `REPORTING_FRAMEWORK = IND_AS` settings record whose evidence
   input is the `DISCOVERY` kind that onboarding's `derived_settings.write` cites (written only
   after `financial_rule` passes), both recorded at or before the cutoff. Anything else (no
   onboarding record, another evidence kind, a later record, another framework) returns `None`:
   no check class, so row 3 cannot apply and `measure` counts nothing for that entity. An Ind AS
   setting alone never implies `NON_FINANCIAL`. Apar (entity 1): `PARTIAL` record and a
   `DISCOVERY`-cited Ind AS setting, both 2026-10-29 (read-only query).
2. **Fallback outcome storage:** accepted. 0047 adds append-only `eqos.vendor_fallback_outcomes`,
   and also extends the `run_versions` pin CHECK (finding 1).
3. **Label on `AdmissionRecord`:** accepted as an addition to `SelectedFact`. The report path
   also takes the admitted value, precision and provenance (Task 9, findings 4, 5, 12).
4. **Refusal codes:** the vocabulary mapping is accepted (today's four first-party codes are the
   detail of `FILING_UNRESOLVED`; `OPEN_HIGH` becomes `REVIEW_OPEN`). The restriction "refusal
   assertions change only by this mapping" is withdrawn: `AdmissionOutcome.refusals` keeps its
   pair shape, the detail travels separately, and obsolete vendor-exclusion assertions are
   replaced by the new policy's conditions (Task 8).

## File map

| Path | Change | Responsibility |
|---|---|---|
| `migrations/0047_admission_label.sql` | create | §6.5 columns and check, counterexamples, `row_captures` witness branch, fallback outcomes, `run_versions` pin CHECK |
| `equity_os/contracts/verification/vendor_first.py` | create | `AdmissionLabel`, `VendorOutcome`, `FilingState`, `FallbackOutcome`, label texts |
| `config/normalisation/mappings/tijori/v5/display.yaml` | create | per-(section, basis) unit and precision rules |
| `equity_os/extraction/vendors/tijori/vendor_tijori.py` | modify | apply the row's own section rule; version bump |
| `equity_os/verification/comparison/run_config.py` | modify | `VENDOR_EXTRACTORS` (Task 2); policy and eligibility load, pin and `require_pins` (Task 6) |
| `config/normalisation/mappings/{screener/v4,tijori/v5}/financials.yaml`, `config/normalisation/mappings/v9.yaml` | create | new vendor entry files with `unmapped:` lists and standalone entries; mapping set v9 |
| `equity_os/normalisation/mapping/mapping_models.py` | modify | accept the `unmapped:` list |
| `equity_os/interface/commands/sourcing/vendor_surface_cli.py` | modify | thin `vendor reingest` and `vendor measure` handlers |
| `equity_os/sourcing/exchange/nse_filings.py` | modify | `collapse`, `qualifies(basis)`, `filing_for` |
| `equity_os/contracts/sourcing/source_catalog.py` | modify | standalone NSE XBRL source and surface |
| `equity_os/companies/onboarding/{discovery,verification,derived_settings,discovery_origins}.py` | modify | thread the selected basis |
| `equity_os/extraction/packages/capture_intake.py` | modify | authorise the basis's XBRL source |
| `equity_os/interface/commands/companies/onboard_cli.py` | modify | ingest, vendor adapters, PDF exclusion and compare command on the basis |
| `equity_os/verification/comparison/engine_vendor_context.py` | create | context for a group with no filing package |
| `equity_os/verification/comparison/engine.py` | modify | call it (net zero lines) |
| `equity_os/verification/comparison/run.py` | modify | `operational_failures`: absence is not failure |
| `equity_os/interface/commands/verification/compare_cli.py` | modify | default vendor sides; `--eligibility`; `fallback` action |
| `config/verification/vendor_first/policy/v1.yaml` | create | `precision_limit`, `min_clean_key_periods` |
| `equity_os/verification/admission/vendor_first.py` | create | policy loader, T1, filing state, check class, issuer class |
| `equity_os/verification/admission/eligibility.py` | create | artifact model, load, measure, coverage, counterexample reads and writes |
| `equity_os/contracts/measurement/evidence.py`, `equity_os/contracts/verification/config_versions.py` | modify | `PinnedVersions` and `ConfigVersions` fields `vendor_first_policy`, `eligibility` |
| `equity_os/verification/admission/admission.py` | modify | §6.5 rows, labels, vendor bridge, `read_selected` |
| `equity_os/publication/checking/citations.py` | modify | witness branch, `admission_label`, withdrawal |
| `equity_os/interface/entry/draft_admission.py` | create | `_comparison` and `_admit` from `cli.py`, split into the report path's first four steps |
| `equity_os/interface/entry/cli.py` | modify | the five-step report-path order; `PILOT_VERSIONS.mapping_set = "v9"` |
| `equity_os/interface/workflows/pipeline.py` | modify | `admitted` values replace the role observations' values before the render |
| `equity_os/publication/drafting/{earnings_update,run_draft,display}.py`, `equity_os/analysis/calculations/run_traces.py` | modify | `AdmittedFact` on the rendered fact; admitted operands; labels into claims |
| `equity_os/analysis/thesis_models/{contracts,adapters,render}.py` | modify | `ValidatedFact.admission_label` |
| `equity_os/publication/export/export.py` | modify | "Source notes" section of `status_note` |
| `equity_os/sourcing/exchange/results_filing.py` | create | acquire one period's results XBRL and PDF |
| `equity_os/interface/commands/sourcing/documents_cli.py` | modify | extract the announcements step as a function |
| `equity_os/verification/admission/fallback.py` | create | the four fallback steps and terminal outcome |
| `docs/specs/2026-10-11-canonical-financial-data-and-cross-source-comparison.md`, `config/sourcing/sources.yaml`, `CONTEXT.md` | modify | §10 amendments (Phase 1 lines) |
| `config/verification/vendor_first/eligibility/v1.yaml`, `docs/evidence/vendor-first/phase-1-report.md` | create (Task 14, committed after `APPROVE`) | the reviewed artifact and the measured counts |

Version numbers: the next free mapping set is `v9`, Screener financials `v4`, Tijori `v5`
(tree at `b07e668f`); the implementer re-reads the tree at Task 2 and Task 3 start and uses the
next free numbers if `research-4` took any. Tests live under `tests/equity_os/<bucket>/<sub-bucket>/`,
beside the modules they cover.

## Task 1: Migration 0047 and the vendor-first contracts

Goal: A migrated database stores labels, witnesses, eligibility versions, counterexamples,
fallback outcomes and the two new run pins; existing admissions keep their content.

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
  recorded_at DEFAULT eqos.store_now())`; `run_versions` pin values `vendor_first_policy` and
  `eligibility`.

Approach: As §6.5. Add `label` with the default, then drop the default; existing rows need no
UPDATE, so the row-mutation trigger stays. The check requires a witness and an eligibility version
on `VENDORS_AGREE_NOT_CHECKED` rows. Both new tables are append-only with the existing
`reject_mutation` triggers and runtime `SELECT, INSERT` grants, as 0011 does. Drop and re-add
`run_versions_pin_check` as 0009 does, with its twelve values plus the two new ones.
`CREATE OR REPLACE` `eqos.row_captures` from its last definition (0028) with one added `UNION ALL`
yielding `witness_interpretation_id` in the `fact_admissions` branch; nothing else in the body
changes.

Verification: the test applies migrations up to 0045 to a fresh `eqos_test_*` database, inserts a
first-party admission, then applies 0047: that row reads `CHECKED_AGAINST_FILING` and its other
columns are unchanged. After 0047: an insert naming a label succeeds; an insert without a label
fails `NOT NULL`; an unchecked row without a witness fails the check; a `run_versions` row with pin
`eligibility` inserts and one with an unknown pin fails; an UPDATE on a counterexample raises;
`row_captures` on an admission with a witness returns both captures. `eqos db check-live` is not
run here (live apply is Task 13).

Dependencies: None.

Risks: the `row_captures` body is copied from 0028; a later migration that changed it would be
silently reverted. The implementer diffs the function as installed in a migrated test database
against 0028's text before replacing it. Admission inserts written before Task 8 omit `label` and
would fail after 0047; Task 8 is the only writer and lands before any live apply.

## Task 2: Tijori display rules, shared fixture, `vendor reingest`

Goal: Every supported Tijori (section, basis) evidences its unit and precision, unsupported
sections stay `UNKNOWN_UNIT`, and retained captures can be re-ingested under the new extractor.

Files:
- Create: `config/normalisation/mappings/tijori/v5/display.yaml`
- Modify: `vendor_tijori.py`, `run_config.py` (`VENDOR_EXTRACTORS` only), `onboard_cli.py`
  (`TIJORI_DISPLAY` path), `vendor_surface_cli.py` (a thin `reingest` handler)
- Test: `tests/equity_os/extraction/vendors/test_vendor_retained.py` (`retained`, `pg`): one
  module-scoped fixture that extracts and interprets the retained Apar Screener and Tijori
  financials captures; Task 3 adds its inventory tests to the same module

Interfaces:
- Produces: `TijoriDisplay` becomes `TijoriDisplayRules(rules: tuple[TijoriDisplayRule, ...])`,
  one rule per `(section, basis)` with its own `unit_evidence_ref` and `precision_evidence_ref`;
  `load_tijori_display(path) -> TijoriDisplayRules`; `vendor_tijori.EXTRACTOR_VERSION` bumped;
  `eqos vendor reingest --entity <key> --period-end <date> --basis <basis> --mapping-set <v>
  --dictionary <v>`, which calls `ingest_vendor_retained` over that entity-period's retained
  Screener and Tijori financials captures under the current extractors and the named mapping set,
  as `onboard_cli._ingest` does. The handler only parses arguments and calls it.

Approach: §6.1, units and precision. Each rule cites a retained capture (the render script and a
measured section), never digits in the island. The extractor picks the rule of the row's own
section and basis; a section without one keeps `UNKNOWN_UNIT`, so `interpret` still refuses it.
`fr_c` gets no rule. The v1 file stays, since frozen pins may name it.

Verification: on the fixture, sections with a rule give zero `INVALID`/`UNIT_MISMATCH`
interpretations; a fixture row in a section without a rule stays `UNKNOWN_UNIT`; a value whose
digits suggest another precision gets the rule's (acceptance 2). `eqos vendor reingest` on an
`eqos_test_*` copy adds interpretations under the new versions and leaves older ones untouched.

Dependencies: None.

Risks: Tijori's annual and balance-sheet tables may render with different units from `qt_c`;
each rule needs its own evidence, and a section the evidence does not settle stays unsupported
rather than guessed. Characterization first: record today's `qt_c` output and require it unchanged.

## Task 3: Mapping set v9: inventory and standalone entries

Goal: Every native statement label in the retained Apar Screener and Tijori captures (`fr_c`
excepted) has exactly one disposition in the new mapping files, the known definition differences
cannot vote, and mapping set `v9` interprets first-party filings exactly as `v6` does.

Files:
- Create: `config/normalisation/mappings/screener/v4/financials.yaml`,
  `config/normalisation/mappings/tijori/v5/financials.yaml`, `config/normalisation/mappings/v9.yaml`
  (v6's entry files with the two vendor files replaced)
- Modify: `mapping_models.py` (the `unmapped:` list: label, section, basis, reason),
  `interface/entry/cli.py` (`PILOT_VERSIONS.mapping_set = "v9"`)
- Test: `test_vendor_retained.py` (Task 2's module and fixture)

Interfaces:
- Consumes: Task 2's display rules and fixture.
- Produces: mapping set `v9` used by every later task; `UnmappedLabel` model.

Approach: §6.1. Entries default to `EQUIVALENCE_UNPROVEN`. Screener annual interest against
`finance_costs` is `RELATED_NOT_EQUIVALENT` (the 7.7% is not explained). Standalone tables (Tijori
`*_s` sections, the Screener standalone page) get entries; standalone never pairs with
consolidated. Dimensioned entries keep their dimensions. `map_labels` may draft entries; the files
are reviewed, and comparison never reads `vendor_label_proposals`. Labels are standard data, so no
parser or per-company rule is written. `v9` keeps v6's XBRL, PDF and construction files, so a
comparison under `v9` needs first-party interpretations under `v9`: Task 13 re-interprets the
retained packages with the existing `eqos evidence ingest`.

Verification: the test walks every native label in the retained captures and finds exactly one
disposition each; it prints cell counts per disposition (acceptance 1); a label removed from a
file fails it by name. No FY `finance_costs` Screener entry votes (acceptance 12, data half). On
an `eqos_test_*` copy, `eqos evidence ingest --mapping-set v9` over one retained Apar package gives
the same first-party interpretation counts per (representation, status) as `v6`. The existing
Stage 2 end-to-end passes with `PILOT_VERSIONS` at `v9`.

Dependencies: Task 2.

Risks: the inventory is large (2,030 Tijori and 210 Screener labels are unmapped today); most
will be `unmapped` with a reason, which is correct. The test must read labels from the captures,
not from the mapping file, or it proves nothing. `_comparison` (Task 9) pins runs to
`PILOT_VERSIONS`; if a stored v6 run must still pass it for an existing report's rework, the
existing Stage 2 tests show it and the implementer reports it rather than widening the check.

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
  `filing_window` and Task 10; `ListingRow.qualifies(basis: str) -> bool`;
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
never a default (today's line 135 hard-codes it). Applicability and vendor-side selection already
key on basis status and basis; the test proves it rather than adding code.

Verification: a replay fixture whose listings hold only standalone rows onboards: standalone
XBRL verified, `STANDALONE_ONLY`, a standalone package; a compare run gives its consolidated cells
`NOT_APPLICABLE`, and a consolidated vendor table is never paired with the standalone filing
(acceptance 4). Apar's retained onboarding generation replays to identical states, settings and
package bytes before and after.

Test seams: `discover` over `replay_fetch`; `onboard` on an `eqos_test_*` database.

Dependencies: Task 3 (standalone vendor entries).

Risks: characterization first, on Apar's replay. The fixture's standalone XBRL instances are
synthetic copies with standalone scope; the implementer documents how each was made.

## Task 5: Vendor-only runs, run status, default vendor sides

Goal: A company-period with vendor captures and no filing package produces a `COMPLETE` run;
a real acquisition or extraction failure still makes a run `INCOMPLETE`; an ordinary
`eqos compare run` with no vendor flags has Screener and Tijori sides.

Files:
- Create: `equity_os/verification/comparison/engine_vendor_context.py`
- Modify: `engine.py` (`_group_periods`, `_context` delegate when no package; net zero lines),
  `run.py` (`operational_failures`), `compare_cli.py` (`--vendor` default)
- Test: `tests/equity_os/verification/comparison/test_vendor_only_run.py` (`pg`, through
  `eqos compare run`)

Interfaces:
- Produces: `vendor_group_context(...) -> tuple[str | None, ApplicabilityContext]`: currency from
  the vendor occurrences' evidenced unit, framework, fiscal year and basis status from identity
  settings, `disclosed_rows` from the vendor tables' row presence, period kind from the vendor
  column; a missing input raises `RunResolutionError`. `DEFAULT_VENDORS: tuple[tuple[str, str],
  ...]` (Screener page, Tijori financials) in `compare_cli`.

Approach: §6.3. Nothing is defaulted. A dimensioned key whose members cannot be enumerated
without a package refuses with an explicit reason instead of dropping the dimension (§6.1). The
default applies to financial-results runs only, including fallback reruns.

Run status (finding 3). With no package, `select_key` already gives first-party sides `NO_VALUE`
with `NO_ELIGIBLE_PACKAGE`, which `operational_failures` does not count. The one new absence is a
vendor side with `NO_ATTEMPT` (no capture of that surface for the company-period), which defaults
now make common: `operational_failures` stops counting it. Everything else stays a failure:
a failed acquisition or extraction attempt (`engine_attempts._imposed`),
`NOT_EXTRACTED_UNDER_PINS`, `NOT_INTERPRETED_UNDER_PINS`, on either role. No live run holds a
vendor `NO_ATTEMPT` side today (read-only query: the one `INCOMPLETE` run, 5, fails on first-party
PDF `NOT_INTERPRETED_UNDER_PINS`), so no stored status changes; the replay tests confirm it.

Verification, all through `eqos compare run` on `eqos_test_*`: vendor captures with no filing
package, occurrence or interpretation give a `COMPLETE` run with vendor values and first-party
sides `NO_VALUE`/`NO_ELIGIBLE_PACKAGE`; the same with a failed first-party acquisition attempt for
the period gives `INCOMPLETE` naming it; a missing currency refuses the group; a non-enumerable
dimensioned key refuses with its reason; a run with no flags has both vendor sides, and one with a
vendor never captured for the period is still `COMPLETE` (acceptance 5, run half). Existing
comparison tests pass unchanged.

Dependencies: Task 2.

Risks: default vendors change new run requests, so a new run without flags differs from an old
one; stored runs keep their own identity and replay unchanged, which the existing replay tests
show.

## Task 6: Policy, predicates and run pins

Goal: T1 and the filing state are computed exactly as §6.4 defines them, and a run's policy and
eligibility versions are chosen, stored and reloaded through the same pin path as every other
artifact.

Files:
- Create: `config/verification/vendor_first/policy/v1.yaml`,
  `equity_os/verification/admission/vendor_first.py` (predicates and policy)
- Modify: `evidence.py` (`PinnedVersions.vendor_first_policy`, `.eligibility`: `VersionPin |
  None`, excluded when None, as `comparison_semantics` is), `config_versions.py`
  (`ConfigVersions.vendor_first_policy: str | None = "v1"`, `.eligibility: str | None = None`,
  both carried by `of`), `run_config.py` (`load_run_config` loads and pins each named version;
  `pin_config` stores them; `require_pins` compares them), `compare_cli.py` (`--eligibility`)
- Test: `tests/equity_os/verification/admission/test_vendor_first_predicates.py` (unit), and one
  `pg` round-trip case in the same module

Interfaces:
- Consumes: `VendorOutcome`, `FilingState` (Task 1).
- Produces: `VendorFirstPolicy(version, precision_limit: Decimal, min_clean_key_periods: int)`;
  `load_vendor_first_policy(path) -> VendorFirstPolicy`; `vendor_outcome(row: ResultRow, mapping:
  MappingSet, policy) -> tuple[VendorOutcome, SourceValue | None]` (the chosen, narrower side;
  tie Screener); `filing_state(row: ResultRow, admissible: bool) -> FilingState`.

Approach: §6.4. Each side's interval is the stored `lower`/`upper`. Rule 1 of T1 reads the entry
tier through the mapping set; constructed values are excluded. "Differs" means either vendor.
Filing state reads the row's first-party sides: `FILING_ABSENT` only when every first-party side
is `NO_VALUE` (no package, no member, or the line not in the filing); any `UNAVAILABLE` or
`INVALID` first-party side is `FILING_FAILED`, like a cell that fails today's rule (§6.4 as
amended).
Pins: the eligibility artifact exists only after Task 14's review, so `ConfigVersions.eligibility`
defaults to `None` and a run without an eligibility pin can never reach row 3 (Task 8). The run's
pins are the only source of the versions admission and reruns use; nothing reads "the current
file".

Verification: unit cases of acceptance 7: disjoint precise → `VENDORS_DISAGREE`; intersecting
coarse → `VENDORS_IMPRECISE`; half-width exactly at the limit → agree; m = 0 both exact → agree,
else imprecise; F disjoint from one vendor only → `FILING_DIFFERS`; a first-party `UNAVAILABLE`
side → `FILING_FAILED`. Round trip on `eqos_test_*`: a run with both pins publishes,
`RunStore.read_manifest` reads them back from `run_versions`, `ConfigVersions.of` names them, and
`require_pins` refuses a policy file whose bytes changed. Old run manifests serialize
byte-identically (both pins omitted when None).

Dependencies: Tasks 1, 2, 5 (`run_config.py` is edited by Task 2 first and `compare_cli.py` by
Task 5 first, then only by this task).

Risks: test-first; these are the financial predicates.

## Task 7: Check class, eligibility artifact, `eqos vendor measure`

Goal: The same stored results and arguments give a byte-identical eligibility artifact, and the
command proves three-way coverage of the expected set per run.

Files:
- Create: `equity_os/verification/admission/eligibility.py`
- Modify: `vendor_first.py` (check class, issuer class), `vendor_surface_cli.py` (a thin `measure`
  handler)
- Test: `tests/equity_os/verification/admission/test_eligibility.py` (`pg`; one feature test on a
  fresh run)

Interfaces:
- Consumes: Task 6's `vendor_outcome`, `filing_state`, policy and pins.
- Produces: `check_class(row, *, mapping, extractor_pins, dictionary_version, policy_version,
  issuer_class) -> str`; `issuer_class(conn, entity_id, cutoff) -> str | None` (reading 1);
  `EligibilityArtifact`, `ClassEvidence(class_digest, agrees, differs, run_ids, eligible)`;
  `load_eligibility(path) -> EligibilityArtifact`; `measure(pool, available_from) ->
  EligibilityArtifact`; `coverage(pool, run_id) -> Coverage(expected, three_way, refused:
  Mapping[key_digest, reason], missing)`; `counterexample_at(cursor, class_digest, cutoff) ->
  datetime | None`; `record_counterexample(cursor, class_digest, result_id, run_id) -> None`;
  `eligible(artifact, class_digest, *, cutoff, mode, cursor) -> bool`;
  `eqos vendor measure --available-from <timestamp> --out <path>`, which also prints
  `COVERAGE <run_id> <expected> <three_way> <refused> <missing>` lines.

Approach: §6.6. Only `VENDORS_AGREE` cells count; clean needs `FILING_AGREES`; dedup by
`key_digest`. The command refuses an `available_from` earlier than the latest recorded time of any
counted run, writes it into the file, and records its code version. In `AS_KNOWN`, a cutoff before
`available_from` sees no eligibility; a class with any counterexample at or before the cutoff is
not eligible. An entity whose issuer class is `None` has no class and contributes nothing.
Coverage (§6.11 #3): the expected set is every full key (entity, canonical id, period, basis,
framework, dimensions) that both vendors' reviewed `v9` entries map for the run's scope; each
member is three-way (Screener, Tijori and first-party sides all present in the run's results),
refused with the explicit reason Task 5 gives a non-enumerable dimension, or missing. `missing`
is an unexplained gap.

Verification: two runs of the command on the same store and arguments give identical bytes;
`VENDORS_IMPRECISE` key-periods add zero clean observations even with `FILING_AGREES`; an early
`available_from` is refused; an entity without onboarding provenance gets no class (acceptance 8,
artifact half). Feature test: a fresh `eqos compare run` on a fixture with a dimensioned and an
undimensioned key gives `missing = 0`, the dimensioned key three-way where the package enumerates
its members and refused with its reason where not (acceptance 3). The digest unit test changes
each component in turn and expects a new class.

Dependencies: Task 6.

Risks: the digest must take every listed component, or incompatible evidence is reused.

## Task 8: One admission path

Goal: `admit_run` admits by §6.5's rows with labels, records counterexamples before any row, and
`read_selected` returns labelled facts and drops withdrawn unchecked ones for later cutoffs only.

Files:
- Modify: `equity_os/verification/admission/admission.py`
- Test: `tests/equity_os/verification/admission/test_vendor_first_admission.py` (`pg`); the
  existing `test_admission.py`

Interfaces:
- Consumes: Tasks 6 and 7, `AdmissionLabel` (Task 1).
- Produces: `AdmissionRefusal` members `REVIEW_OPEN`, `FILING_UNRESOLVED`, `CHECK_REQUIRED`,
  `VENDOR_UNMAPPED`, `VENDORS_DISAGREE`, `VENDORS_IMPRECISE`, `NOT_REPORTED`; `FilingFailure`
  (today's four first-party codes); `AdmissionOutcome.refusals` keeps its shape
  `tuple[tuple[str, AdmissionRefusal], ...]`; `AdmissionOutcome.filing_failures:
  tuple[tuple[str, FilingFailure], ...]` (the detail of each `FILING_UNRESOLVED`);
  `AdmissionOutcome.triggers: tuple[tuple[int, date, Basis], ...]` (rows 4 and 6 grouped);
  `AdmissionRecord.label`, `.witness_interpretation_id`, `.eligibility_version`;
  `SelectedFact.label`, `.decimals`; `BRIDGE_VERSION = "admission-bridge/2"`;
  `read_selected(store, key, *, cutoff, mode, pool: ConnectionPool) -> SelectedFact | None`.

Approach: §6.5. Today's `_decide` becomes the filing-admissible test. Counterexamples for every
`VENDORS_AGREE` + `FILING_DIFFERS` cell are written first in the same serializable transaction.
Rows 0a and 0b run before any source is chosen. Row 1 keeps the vendor value and its precision;
rows 2 and 5 the filed value. Row 3 needs the run's eligibility pin: a run without it, or a run
without a `vendor_first_policy` pin (every run before Task 6), never reaches row 3, and a run
without the policy pin is admitted by rows 0a, 0b, 5 and 6 only, as today. The vendor bridge
anchors Tijori as `JSON_ISLAND` and Screener as `HTML_TABLE` (a missing anchor field raises
`BridgeError`), takes the later of the two witnesses' capture-registration times as knowledge
time, leaves occurrences `UNKNOWN`, and stores the other witness and the pinned eligibility
version. `read_selected` takes the label from the latest admission of the selected row at or
before the cutoff; the knowledge-time witness stays the earliest, as in `citations.py`.
Withdrawal (§6.6, §6.9) applies only to a fact whose authorising label is
`VENDORS_AGREE_NOT_CHECKED`: a counterexample of its class at or before the cutoff returns
nothing. Retention applies to both kinds of vendor-valued fact: an expired or licence-ended
witness returns nothing. The report path's `admit_roles` (Task 9) reads `refusals` unchanged.

Tests: one case per row of §6.5, including: failed filing plus agreeing vendors refuses
`FILING_UNRESOLVED` with its `FilingFailure`; an agreeing filing keeps the vendor value and
precision; agreeing vendors, a differing filing and an open `HIGH` item refuse `REVIEW_OPEN` and
still record the counterexample (acceptance 6). A version mismatch gives `CHECK_REQUIRED`; a run
with no eligibility pin gives `CHECK_REQUIRED`; a counterexample in run N blocks row 3 in run N+1
with the artifact unchanged, and `read_selected` drops the earlier unchecked fact for later
cutoffs only, while a row-1 fact of the same class stays selected (acceptance 8, finding 6). The
Task 5 vendor-only fixture gives a row-3 admission under a pinned eligibility fixture
(acceptance 5). No FY `finance_costs` cell is admitted under row 3 (acceptance 12). In
`test_admission.py`, admitted-value assertions are kept and refusal names follow reading 4; the
"vendor values are never admitted" assertion (line 210) becomes: on that first-party-only run
(no policy pin), no vendor interpretation is admitted; the API-document assertion and the
first-party characterisation stay. Historical cutoffs return the same facts as before.

Test seams: `admit_run`, `read_selected` on `eqos_test_*`.

Dependencies: Tasks 5, 7.

Risks: the riskiest task. Test-first, from the §6.5 table; characterization of the current
first-party admissions on the existing fixtures before the edit.

## Task 9: Citation, retention, report values and labels

Goal: A report shows, for every admitted number, the admitted value with its label, and its
calculations use the admitted values; a sealed report citing a row-3 fact and a calculation using
it resolve with the label while both witnesses are retained and licensed, and stop resolving for
new reports once either is not, while the sealed bytes never change.

Files:
- Create: `equity_os/interface/entry/draft_admission.py` (`_comparison` and `_admit` from
  `cli.py`, split into steps 1–4 below)
- Modify: `cli.py` (step order), `interface/workflows/pipeline.py` (`admitted`),
  `publication/drafting/earnings_update.py` (`AdmittedFact`, `RenderedFact.admitted`),
  `publication/drafting/run_draft.py` (`_results`),
  `publication/drafting/display.py` (label suffixes), `analysis/calculations/run_traces.py`
  (admitted operands), `citations.py` (`_admitted`, the calculation path),
  `publication/export/export.py` (`status_note`), `analysis/thesis_models/{contracts,adapters,
  render}.py`
- Test: `tests/equity_os/publication/checking/test_vendor_citation.py` (`pg`); extend the Stage 2
  end-to-end (`test_data_stage2_e2e.py`)

Interfaces:
- Consumes: Task 8's records, columns and `SelectedFact.label`.
- Produces: `run_versions(pool, run_id, entity_id, config) -> tuple[RunManifest,
  ConfigVersions]`; `admit_roles(pool, store_id, run_id, config, entity_id, carried) ->
  dict[FactRole, tuple[MeasurementKey, AdmissionRecord]]`; `check_sources(pool, manifest, chosen,
  config, xbrl, pdfs, versions) -> None`; `select_roles(pool, store_id, run_id, chosen) ->
  dict[str, FactRef]` (all four in `draft_admission.py`); `AdmittedFact(ref, value, decimals,
  provenance, label, interpretation_id, witness_interpretation_id)` in `earnings_update.py`;
  `run_pipeline(..., admitted: Mapping[FactRole, AdmittedFact] | None = None)`;
  `bind_computed(..., admitted: Mapping[FactRole, AdmittedFact] | None = None)`;
  `RenderedFact.admitted: AdmittedFact | None`; `ResolvedCitation.admission_label:
  AdmissionLabel | None`, set only for admitted facts and calculations; `weakest(labels) ->
  AdmissionLabel` (`VENDORS_AGREE_NOT_CHECKED` is weaker); `ValidatedFact.admission_label`
  (`ValidatedFact.label` stays the metric name).

Approach: §6.7, §6.9, §6.10.
- **Report path order (plan review 2, findings 1 and 2).** Today `_comparison` runs before the
  pipeline and `_admit` (admit, member check, select) runs last inside `before_commit`, after
  `bind_computed`, `bind_probe` and `bind_credibility` have bound the filed values; the pipeline
  ignores `before_commit`'s return (`pipeline.py:541`) and has already built comparatives and
  calculations from the filed observations (`pipeline.py:498`, `:513`). The PostgreSQL branch of
  `eqos run --compare-run <id>` becomes, in order:
  1. **Static run validation**, `run_versions` (the first half of `_comparison`): a `COMPLETE`
     `AS_KNOWN` run of this entity and quarter; `ConfigVersions.of(manifest.pinned)` equals
     `PILOT_VERSIONS` on every base field (all but `vendor_first_policy` and `eligibility`); then
     `require_pins(load_run_config(root, ConfigVersions.of(manifest.pinned), vendors=<(source_id,
     surface) of each pinned vendor extractor>), manifest.pinned)`. So the current vendor
     extractors, policy and eligibility files are checked against the run's own pins (Task 6 loads
     the last two). Today's `load_run_config(root, PILOT_VERSIONS)` (`cli.py:520`) computes no
     vendor pins and no eligibility, so `require_pins` (`run_config.py:361`) refuses every run with
     vendor sides, including every default-vendor run.
  2. **Admission**, `admit_roles`: `check_head`, then `admit_run(run_id)`, then each non-carried
     required role's record by key. Keys come from `config.concepts.roles` and the quarter, each in
     its role's own unit and value kind (`CRORE` for monetary roles, the per-share unit for
     `BASIC_EPS`; `measurement_key` includes the value kind, `import_mapping.py:382`), not from the
     rendered update, which does not exist yet; the characterization test shows every required
     role's key, EPS included, equals today's `_admit` key. A refused or
     absent role refuses with its refusal, as today.
  3. **Witness/package validation**, `check_sources` (the second half of `_comparison` and
     `_admit`'s member check, one function): a filed-valued record (rows 2, 5) must come from a
     member of the run's single selected package for the quarter, published by the cutoff and
     holding the run's own XBRL and results PDF (today's rules, unchanged); a vendor-valued record
     (rows 1, 3) passes when its two witnesses are retained catalog captures (`RETAINED` or
     `RESTORED`, no `licence_ends` row) of the two vendor-primary sources registered by the cutoff,
     and a row-3 record also carries the run's pinned eligibility version. The run may select no
     package for the quarter only when every chosen record is row 3.
  4. **Selection**, `select_roles`: `select_admitted` per role, unchanged. Admissions and
     selections now persist before the pipeline; a later pipeline failure leaves them, and a rerun
     finds them already in place. `select_admitted` is not idempotent (`select_canonical` appends,
     `pg_fact_store.py:252`), so `select_roles` keeps today's history/head guard from `_admit`
     (`cli.py:613`); a failed-pipeline-then-rerun case asserts no duplicate selection.
  5. **Drafting**: `run_pipeline(..., admitted=...)`, then `before_commit` as today without
     `_admit`, then `RunDraft` from `result.update` and the selected refs.
- **Admitted values (finding 4, plan review 2 finding 1).** The pipeline takes the admitted facts.
  At step 7, after the cross-foot and cross-check gates have run on the filed values, each
  admitted role's observation in `role_obs` takes the admitted value in report units: admitted
  monetary facts hold base INR (`admission.py:225`) and pipeline monetary observations use crore
  (`xbrl_parser.py:516`), so the adapter converts value and precision at this boundary (per-share
  values unchanged); calculation operands stay in base units. Rendered facts, `collect_run_comparatives(current=...)` and
  `build_calculations` then derive from the admitted values through the existing code: nothing is
  recomputed outside the pipeline, `before_commit` still returns nothing, and `result.update` is
  the report update. `RenderedFact.admitted` carries the admitted fact; `RenderedFact.sources`
  stays the quarter's filed provenance, so the filed-only consumers resolve as today: the filed tax
  and share-of-associates figures (`bind_computed`, `run_traces.py:470`), `admitted_xbrl` for
  `bind_probe` and `bind_credibility` (`run_traces.py:583`), and the comparatives' prior lookups.
  The rendered source line and the claim cite the admitted fact's provenance and label. In
  `bind_computed`, each `reported` operand and each comparative's `current` operand of an
  admitted role is the `OperandValue` that `filed` would build, from the admitted fact's own
  interpretation (`interpretation_id`), with no capture lookup and no blob added; a carried role
  reads its admitted fact back from the head's admission (amended 2026-11-06, phase-review
  finding 3). `_compute` (`run_traces.py:315`) then checks traces against run
  values computed from the same admitted values, so a vendor value passes and a real mismatch
  still refuses. Comparator and filed-tax figures stay filed, labelled as today. Without
  `admitted` (the non-PostgreSQL path) nothing changes.
- **Labels in sealed bytes (finding 7).** The label is bound into the claim when the draft is
  built, as the two label qualifiers; `render_claim` prints `LABEL_TEXT` from them, like `FILED`.
  So `narrative` and `content_hash` cover the label and stay deterministic. A required-role claim
  without a label qualifier fails the render.
- **Later notes (finding 7).** `render_claim` stays database-free. `export.status_note` gains a
  "Source notes" section: for each admitted fact the version cites, "vendor source expired
  ‹date›" or "class later contradicted by a filing on ‹date›" from `row_captures`, capture state,
  `licence_ends` and `counterexample_at`. Sealed narrative bytes and digests never change.
- **Citation.** An admission with a witness resolves when both captures are retained catalog
  captures of the two vendor-primary sources (`eqos.capture_state` in `RETAINED` or `RESTORED`, no
  `licence_ends` row) and, for a `VENDORS_AGREE_NOT_CHECKED` admission only, the class has no
  counterexample at or before the report's cutoff. `ResolvedCitation.admission_label` comes from
  the admission; quote, policy and comparison citations leave it `None`. A calculation carries
  `weakest` of its inputs' labels. Nothing else in resolution changes.
- **Thesis models.** Adapters pass `admission_label` from the evidence where they pass
  `single_sourced`; it is never inferred from `single_sourced`.

Verification: Stage 2 end-to-end through the real entry command (`main(["run", ...,
"--compare-run", id])`, as `test_data_stage2_e2e.py` does), the draft write and the seal, each case
starting with no admissions for the run: (a) a row-1 run whose filing agrees with the vendors
within precision but with a different value: `PipelineResult.update` and the stored draft hold the
vendor value with "checked against filing"; the sealed calculation and change lines and their
stored traces differ from the filed-value results and equal those computed from the admitted
values; the filed tax line, the probe and the credibility binding still resolve against the
quarter's XBRL (acceptance 13, finding 4, plan review 2 finding 1); (b) a default-vendor run with
the quarter's filing package withheld, pinned to the eligibility fixture, passes static
validation, is admitted by the command (row 3), passes source validation, selects, seals, and
every number shows its label (acceptance 9 as amended, 13); (c) a run whose pinned vendor
extractor differs from the current code refuses at static validation with no admission written. Citation test: acceptance 9 (fact and calculation resolve with the label;
`row_captures` returns both witnesses' captures) and 10 (expiry, and separately licence end, of
either witness withdraws the admission for a new report; a backup restore does not revive it; re-fetch
revival is deferred by the scope amendment below); a contradicted class withdraws the row-3 fact and keeps the row-1
fact of the same class; after each, `export_version` bytes and the stored content hash are
unchanged and `status_note` shows the note. A quote and a policy citation resolve with no label.

Dependencies: Task 8; Task 3 (`PILOT_VERSIONS`).

Risks: the source-validation change is the one authority change in the report path; Sol reads
it at phase end. Moving admission and selection before the pipeline is the one ordering change;
characterization first: today's Stage 2 end-to-end on a first-party run gives the same admitted
keys, selections and values. Case (b) exercises the row-3 path through the only report path that
exists, which reads the quarter's filing for its other sections; a report for a quarter with no
filing is outside Phase 1 (acceptance 9 as amended). The restore behaviour comes from migrations 0028–0031; the test uses their existing
commands (vendor re-fetch revival: scope amendment below).

**Scope amendment (2026-11-06, phase-review finding 8; approval: Sol phase re-review 2, APPROVE 2026-11-06).** The
citation test's acceptance 10 case covers the fail-closed part only: expiry, and separately licence
end, of either witness withdraws the admission for a new report, and a backup restore does not
revive it. Hash-verified vendor re-fetch revival is out of Phase 1 scope and tracked by `eqos-g5eh`
(spec acceptance 10, amendment). Reason: no vendor capture in the five-company test reaches expiry
or licence end during the phase (vendor captures become purge-eligible only twelve months after
registration, `VENDOR_WINDOW_MONTHS` in `storage/retention/eligibility.py`, and a licence end is an
explicit operator mark that the phase does not make), and revival needs a new authorised vendor
re-fetch path: restore and refetchability are exchange-only today
(`migrations/0031_retention_fixes.sql`, `storage/retention/refetch.py`).

## Task 10: Fallback workflow

Goal: `eqos compare fallback --run <id>` acquires, for each triggered company-period only, the
results XBRL and PDF, ingests, reruns with vendor sides, admits, and stores one terminal outcome.

Files:
- Create: `equity_os/sourcing/exchange/results_filing.py`,
  `equity_os/verification/admission/fallback.py`
- Modify: `nse_filings.py` (`filing_for`), `documents_cli.py` (extract the announcements step),
  `compare_cli.py` (`fallback` action, thin)
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
  `ingest_first_party` takes the requested basis and the triggering run's mapping set.
- Compare and admit: a fresh run with default vendors and the triggering run's pins, then
  `admit_run`.
No retries beyond the acquisition layer's. Entity, symbol, ISIN, period and basis come from the
triggering run, so no other issuer is fetched and watchlist coverage is unchanged.

Verification: one replay-backed test through `eqos compare fallback` on an `eqos_test_*` copy,
parameterised over: an Apar period whose filing is withheld from the first run → `ADMITTED` after
acquiring that period's XBRL and PDF only (acceptance 11); an unavailable filing →
`FILING_UNAVAILABLE` with its cells still refused; a filing whose extraction fails →
`FILING_UNRESOLVED`; a filing that leaves a trigger cell refused → `STILL_REFUSED` listing it; a
standalone basis → the standalone XBRL source; a results-PDF declaration whose `sha256` differs
from the acquired document → refused before ingest. Each case asserts the stored
`vendor_fallback_outcomes` row and a fetch log naming only that issuer and period; coverage tables
are unchanged. No helper unit tests. `documents backfill`'s existing tests pass unchanged.

Dependencies: Tasks 4, 8.

Risks: characterization first for the extracted documents step. The issuer-config PDF declaration
is per issuer; for an issuer without `pdf_parse`, the outcome rests on XBRL alone, as the spec
allows.

## Task 11: Document amendments

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

## Task 12: Pre-live gate

Goal: The implementation revision passes the integrated gate before anything writes live.

Approach: on the tip holding Tasks 1–11, run `scripts/verify.sh gate vendor-1-p1` as a
`systemd-run --user` unit; save its log and the revision in `scratchpad/vendor-first/gate-1/`.
The log goes to the phase review. A later code change (a fix round) re-runs the gate only if it
touches code the gate covers; doc-only changes do not.

Verification: exit 0, mypy strict and ruff clean (acceptance 14).

Dependencies: Tasks 1–11 committed.

## Live protocol (Tasks 13 and 14)

1. **Inventory.** Before the rehearsal, the task writes its command list to
   `scratchpad/vendor-first/live-<n>/commands.txt` (every argument explicit, inputs from read-only
   queries saved beside it) and records its sha256. Rehearsal and live run that file, in order,
   unchanged.
2. **Baseline.** Immediately before the rehearsal, `eqos db backup` of live, restored into a fresh
   `eqos_test_*` (`eqos db restore`). The restored copy's per-table counts and fingerprints must
   equal live's at that moment, or the task stops.
3. **Checks after each command**, rehearsal and live alike: the live check (schema, seed and legacy
   store only). Live runs `eqos db check-live`. That command refuses any `eqos_test_*` target, so
   the rehearsal runs the same read-only checker, `check_live` in `storage/database/live_check.py`,
   through a scratchpad helper (`uv run --no-sync python`, not committed) on a migrator connection
   to the named rehearsal database, with the same migrations directory and issuer identity; each
   result is recorded against its actual target database (amended 2026-11-06, phase-review finding
   13). Then counts of every `eqos` table; business-key summaries (interpretations by entity,
   representation, mapping set, extractor version and status; packages by entity, period and basis;
   runs by status with their `run_versions` pins; `run_inputs` by kind and disposition; results and
   source values by state and reason; queue items by severity; version pins by artifact and
   version); and a fingerprint of every pre-existing row of the touched tables, which must not
   change. New rows are compared with ids and timestamps normalised. The scripts extend
   `scratchpad/live-run-1/{counts,delta}.py`; they are scratch, not committed.
4. **Allowed changes.** Each command's expected tables are stated in its task. A rehearsal delta
   outside them stops the task before live. Each live delta, summary and fingerprint set must
   equal the rehearsal's; the first mismatch stops the task before the next command.
5. **Before live (plan review 2, finding 3).** Immediately before the first live command, live's
   per-table counts, fingerprints, migration ledger, `eqos db check-live` result and every `eqos`
   sequence's `last_value` must equal those recorded at the baseline backup. Before each later
   live command, live must equal the baseline plus the rehearsed deltas of the commands already
   run. Any drift (a competing write) stops the task; it restarts from step 2 (new backup, new
   rehearsal), never continues on the old rehearsal.
6. Drop the rehearsal database at the end.

## Task 13: Live: migrate, re-interpret, re-ingest Apar

Goal: Live has migrations 0047–0049, 0051 (if landed) and 0052, Apar's retained first-party packages
interpreted under mapping set `v9`, and its retained Screener and Tijori captures interpreted under
the new extractor and `v9`, with no other change.

Files: none committed. Logs in `scratchpad/vendor-first/live-1/`.

Commands, in order, with the main checkout on the tip Task 12 gated:
1. `eqos db migrate`. It applies every pending migration, so before the rehearsal `commands.txt`
   freezes the exact pending list (the live ledger against `migrations/` at the gated tip) and
   each one's allowed objects; any other pending migration stops the run (amended 2026-11-06,
   phase-review finding 14). The list expected now: 0047 (its objects); 0048 (`fact_admissions`
   column `class_digest` and constraint `fact_admissions_unchecked_class`); 0049 (function
   `check_screen_member_unpaired` and its `BEFORE INSERT` trigger on `screen_members`); 0051
   (`0051_version_source_cutoff.sql`, P2 Task 4, if landed by then: the report-version source
   cutoff table and its guard); 0052 (`0052_admission_witness_edges.sql`: the second witness's
   edges in `row_captures`). Allowed: the migration ledger and those objects, nothing else.
2. `eqos evidence ingest --mapping-set v9 --dictionary v2` for each retained Apar first-party
   package (the list, with its retrieval manifest, issuer config and members, comes from a
   read-only query over `filing_packages` and the retained manifests, as LIVE-RUN-1 ran them).
   Allowed: interpretations and their figures, version pins, and any attempt rows the rehearsal
   shows ingest writing; packages, occurrences and captures unchanged. `commands.txt` names each
   package's actual comparison baseline, the mapping set of its latest interpretations (from a
   read-only query; most are `v6`, none is assumed). Code check: per package, interpretation
   counts per (representation, status) under `v9` equal those under that package's baseline.
3. `eqos vendor reingest --mapping-set v9 --dictionary v2` for each Apar period end with retained
   vendor financials captures. Allowed: occurrences, interpretations, attempts and version pins.
   Also allowed: the new interpretations' figures, that is their construction traces
   (`calculation_traces`, `calculation_trace_operands`) for constructed rules. These are new rows
   only; every pre-existing row stays unchanged. (Orchestrator ruling, 2026-11-07, stage A
   rehearsal: a constructed Screener rule writes one trace and its operands per new
   interpretation. Step 2 already allows figures.)

Verification: the live protocol passes at every step; interpretations under the new versions show
zero Tijori `INVALID`/`UNIT_MISMATCH` in sections with a rule. A package with no retained manifest
is listed in the log, never re-extracted another way, and its (period end, basis) is a
measurement-scope exclusion for Task 14.

Dependencies: Task 12.

Risks: permanent writes. Rollback is not possible for the rows; a wrong extractor version means a
new version and another re-ingest, never an edit.

## Task 14: Apar re-measurement

Goal: Code computes, from fresh live runs, Apar's three-way coverage, outcome counts and the
eligibility artifact; the phase report states the numbers and no vendor value.

Files:
- Create, committed only after Sol's `APPROVE`: `config/verification/vendor_first/eligibility/v1.yaml`,
  `docs/evidence/vendor-first/phase-1-report.md`. Not committed: run logs in
  `scratchpad/vendor-first/measure-2/`.

Approach, under the live protocol:
1. Commands: one `eqos compare run --mapping-set v9 --dictionary v2` with no vendor flags and no
   eligibility pin per Apar (period end, consolidated), as known, excluding Task 13's
   measurement-scope exclusions. The report lists each exclusion and its reason as an explicit
   scope exclusion; no expected key inside a run's declared scope is ever dropped to reach
   `missing = 0`. Allowed: runs, `run_versions`,
   `run_inputs`, results, result source values, surfaced restatements, pair outcomes and
   adjustments, review-queue items and their support rows, version pins and definition-set rows
   the rehearsal shows. Also allowed: the comparison's calculation traces (`calculation_traces`,
   `calculation_trace_operands`), as new rows only. Result source values, run inputs and queue
   item traces reference them. (Orchestrator ruling, 2026-11-07, Task 14 stage A.) No `admit_run`
   on live.
2. **Measure:** `eqos vendor measure` on live, read-only, with `--available-from` fixed before the
   run and later than every counted run. The phase report is generated by code from the command's
   output and read-only queries: counts per disposition (acceptance 1), the `COVERAGE` lines
   (acceptance 3), T1 outcomes, filing states, classes eligible and their key-period counts, and
   the comparison with §5's figures. Every number in the report comes from that output.

Verification: rerunning `measure` gives identical bytes; the report's figures match the command's
output line for line; every `COVERAGE` line has `missing = 0`, and any non-zero `missing` blocks
acceptance 3 and goes to the phase review with the keys; `git status` shows only the two drafted
files.

Dependencies: Task 13.

Risks: live runs are permanent. If coverage is thin (few three-way cells), the report says so;
nothing is tuned to raise it.

**Then: Sol phase-end review** of the phase diff (Tasks 1–11), the Task 12 gate log, the Task
13–14 logs, the drafted artifact and report, by the loop in `.claude/rules/core/04-agent-stack.md`,
then one fresh closing review. Fix rounds that change code re-run the affected tasks' tests and
the gate (Task 12 rule), and Task 14 only if a finding changes measured results (new runs, never
edits). After `APPROVE`: commit the artifact and report, refresh `docs/status/dashboard.html`,
record the verdict on `eqos-awnc`, and file beads for anything parked.

## Dependency order

1 and 2 start in parallel. 3 and 5 after 2; 6 after 1 and 5; 4 after 3; 7 after 6; 8 after 7; 9 and 11 after 8 (9 also after 3); 10 after 4 and 8; 12 after 1–11; 13 after 12; 14 after
13; review after 14.

Shared files have one writer at a time: `run_config.py` (2, then 6), `compare_cli.py` (5, then 6,
then 10), `vendor_surface_cli.py` (2, then 7), `onboard_cli.py` (2, then 4), `cli.py` (3, then 9),
`admission.py` (8 only), `nse_filings.py` (4, then 10). The chains above already order them; no
two tasks that share a file run in parallel.

## Self-review

- **Spec coverage:** §6.1 → T2, T3 (dimension refusal: T5). §6.2 → T4. §6.3 → T5. §6.4 → T6.
  §6.5 → T1, T8. §6.6 → T6 (pins), T7, T8. §6.7 → T9. §6.8 → T10. §6.9 → T1 (`row_captures`),
  T8, T9. §6.10 → T9. §10 Phase 1 lines → T11. Acceptance: 1 → T3, T14; 2 → T2; 3 → T7, T14;
  4 → T4; 5 → T5, T8; 6 → T8; 7 → T6; 8 → T7, T8; 9, 10 → T9; 11 → T10; 12 → T3, T8; 13 → T9;
  14 → T12.
- **Sol's spec notes:** 1 → T4; 2, 3, 4, 5 → T10.
- **Plan review 1:** 1 → T1, T6, T8; 2 → T3, T13; 3 → T5, T6; 4, 5 → T9; 6 → T8, T9; 7 → T9;
  8 → live protocol, T13, T14; 9 → T12; 10 → T1; 11 → T8; 12 → T9; 13 → T7, T14; 14 → T10;
  15 → dependency order; 16 → T9 (merged), T2/T3 (one fixture), thin handlers in
  `vendor_surface_cli.py` and `compare_cli.py`; the closing review stays.
- **Plan review 2:** 1 → T9 (admitted values, `admitted` seam in `pipeline.py`, case a); 2 → T9
  (report path order, static validation reload, cases b and c); 3 → live protocol step 5;
  refinements: scope exclusion → T13, T14; per-package baseline → T13; summed task budget →
  Estimate.
- **Names:** `collapse`, `xbrl_source_id` (T4) → T10; `vendor_outcome`, `filing_state` (T6) → T7,
  T8; `check_class`, `eligible`, `record_counterexample`, `counterexample_at` (T7) → T8, T9;
  `AdmissionRecord.label` (T8) → T9; `AdmissionOutcome.triggers` (T8) → T10.
- **Spec gaps:** all five were ruled by Sol in plan review 2 and applied to the spec at
  `f137d3d7`: §6.4 filing states (T6), acceptance 9 through the filing-backed report path (T9),
  §6.5 and §6.1 doc sync (T1, T13), §6.6 issuer class from onboarding provenance (reading 1, T7),
  and the status note in §6.6 and §6.9 (T9).
