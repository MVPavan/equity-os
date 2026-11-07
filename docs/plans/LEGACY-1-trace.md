# LEGACY-1 trace: what current entry points call in the three legacy lanes

2026-11-07. Read-only trace on `main` at `4dec81c4`. The plan that acts on it is `docs/plans/LEGACY-1.md`.
Corrected after plan review round 1 (R5, R7, R10): see "Round 1 corrections" at the end.

## Method (what was measured, and how)

- **Import graph.** An AST pass over all 449 modules under `equity_os/` and `scripts/`. It covers every
  `import` / `from … import`, including function-local ones, with relative imports resolved. Dynamic
  imports were searched with `grep importlib|__import__`. There is one in product code, in
  `thesis_models/claude_client.py:105`, and it imports `anthropic` only.
- **Roots.** The `eqos` and `eqos-operator` scripts (`pyproject.toml:37-38`) are
  `interface/entry/cli.py:main` and `interface/entry/operator_cli.py:main`. The other roots are
  `cli_parser.py` and every `scripts/*.py`. `scripts/verify.sh` runs pytest only, so it reaches no
  product module directly. `config/` names no Python module. It does name data paths, listed under
  "Data contracts" below.
- **Classification.** LIVE reach is computed from the roots, with the retiring command modules
  removed **only as targets of `cli.py` / `cli_parser.py`**. Each lane's reach is computed from its
  command modules. A lane module outside LIVE reach is DEAD. One inside both is SHARED. Then the
  plan's migrations (below) were simulated by deleting the migrated edges and recomputing.
- **Data contracts.** Data contracts are file layouts that one command writes and a live command
  reads. They were traced by grepping the live code for the retiring commands' names and output
  roots. An import graph cannot see them.
- **Tests.** A test file "goes with" a module if it imports it. The check is transitive through
  `tests/equity_os/support/*` and through test-to-test imports (`from test_goal_runner import …`).
  Command invocations were also traced by grepping the subcommand strings (`main(["validate", …])`).
  Case counts come from `uv run pytest --collect-only -q` over the affected files. That collection
  ran 666 node ids and executed no tests. Re-measured in round 1: the 31 lane 1–2 files collect 531
  ids, the full suite 5,800, and the selector method of the plan's Evidence procedure yields 474 ids
  for Tasks 2–4. No tests were executed. Line counts come from `wc -l`. A partial-file count is
  the AST span of the named test functions.

DEAD below means **no non-test caller**. "DEAD, kept as test seam" means no product caller. The module
is kept because the tests of a live parser drive that parser through it (see the plan).

## Lane 1 — legacy validate / report / thesis lane

Commands: `validate` (`verification/validate_cli.py`), `report` (`publication/report_cli.py`),
`thesis` and `adjudicate` (`publication/thesis_cli.py`, `publication/adjudication_cli.py`), and
`news` (`sourcing/news_cli.py`). They are dispatched at `cli.py:636-659` and registered at
`cli_parser.py:142-226`.

### DEAD (35 modules, 9,309 lines, measured)

| Module | Lines | Only callers |
|---|---|---|
| `interface/commands/verification/validate_cli.py` | 170 | `cli.py` dispatch |
| `interface/commands/publication/report_cli.py` | 190 | `cli.py` dispatch |
| `interface/commands/publication/thesis_cli.py` | 326 | `cli.py`, `cli_parser.py` (also hosts `add_wave_arg`, used only by the validate/report parsers) |
| `interface/commands/publication/adjudication_cli.py` | 221 | `thesis_cli.py`, `cli_parser.py` |
| `interface/commands/sourcing/news_cli.py` | 574 | `cli.py`, `cli_parser.py` |
| `interface/entry/wave_selection.py` | 23 | `report_cli.py:31`, `thesis_cli.py:45`, `validate_cli.py:22` |
| `interface/workflows/goal_runner.py` | 1,087 | `validate_cli.py:23`, `report_cli.py:33` |
| `interface/workflows/report_builder.py` | 285 | `report_cli.py:34` |
| `interface/workflows/comparatives.py` | 353 | DEAD after migration: see SHARED |
| `sourcing/exchange/comparator_cache.py` | 137 | `report_cli.py:36`, `goal_runner.py:94`, `comparatives.py:28` (DEAD once `comparatives.py` goes) |
| `sourcing/exchange/bse_source.py` | 798 | `goal_runner.py:84,91` |
| `sourcing/exchange/bse_pdf_source.py` | 391 | `goal_runner.py:77-83`, `report_cli.py:35` |
| `sourcing/vendors/screener/screener_source.py` (Slice-1 Screener) | 389 | `goal_runner.py:100` |
| `extraction/results_pdf/ocr_engine.py` | 114 | `goal_runner.py:49`, `report_cli.py:22`, `pdf_ocr_recovery.py:41` |
| `extraction/results_pdf/pdf_ocr_recovery.py` | 425 | `goal_runner.py:60` |
| `analysis/thesis_models/{adapters,adjudication,codex_client,contracts,draft_parser,pipeline,prompt,render,verifier}.py` | 2,144 | `thesis_cli.py`, `adjudication_cli.py`, the package `__init__` |
| `contracts/sourcing/news.py`, `extraction/news/{__init__,entity,events}.py`, `sourcing/news/{__init__,health,news_bse,news_common,news_et,news_nse}.py`, `storage/records/news_store.py` | 1,682 | `news_cli.py` only (with each other) |

### SHARED (2): migrate the caller, then retire

| Module | Live use (file:line) | Legacy use |
|---|---|---|
| `interface/workflows/comparatives.py` | `run_comparatives.py:31-35` imports `REASON_INCOMPATIBLE`, `REASON_SELECTION_FAILED` and `_unavailable` (15 lines). `run_comparatives` ← `pipeline.py:513` ← `cli.py:117,321` (`eqos run`). | Everything else, through `collect_comparatives` and `derive_comparator_periods`: `goal_runner.py:76`, `report_cli.py:32` |
| `analysis/thesis_models/__init__.py` (122 lines) | It runs whenever a live module imports a submodule: `ledger_cli.py:62` (`claude_client`), `narrate.py:27-28` (`client`, `settings`). It re-exports the whole drafter, so it loads the dead modules into every ledger and narrate run. | `thesis_cli.py:20` is the only `from equity_os.analysis.thesis_models import` |

### LIVE: named lane 1 in the audit, but called by current paths (keep)

| Module | Live caller (file:line) |
|---|---|
| `interface/workflows/pipeline.py` (the "pipeline_e2e family") | `cli.py:117` import, `cli.py:321` `run_pipeline` (`eqos run`) |
| `interface/workflows/pipeline_steps.py` | `pipeline.py:69,72` |
| `interface/workflows/run_comparatives.py` | `pipeline.py:513` |
| `verification/comparison/agreement.py` (reconcile) | `fact_view.py:19`, `gold_file.py:28`, `diagnostics/report.py:12` |
| `verification/comparison/fact_view.py` (reconcile) | `publication/checking/citations.py:86` |
| `verification/diagnostics/gold_file.py` (reconcile) | `three_source_cli.py:68`, `three_source_inputs.py:51` |
| `verification/diagnostics/report.py` (reconcile) | `fact_view.py:20` |
| `sourcing/exchange/xbrl_source.py` (the "xbrl" adapter) | `cli.py:140`, used at `cli.py:192` (`eqos run --xbrl-mode live`) |
| `sourcing/exchange/sec_source.py` (the "sec" adapter) | `pipeline_steps.py:35`, called through `run_sec_cross_check` at `pipeline.py:507` on every run |
| `storage/facts/fact_store.py` (the SQLite half of the store) | `cutover.py:45,305` (`open_fact_store`, ← `cli.py:318`: the SQLite store without a store id or after `ROLLED_BACK`); `legacy_import.py:49`; `pg_fact_store.py:25`; `pipeline.py:95`; `earnings_update.py:40`; `run_draft.py:108`; `admission.py:47`. The default `config/sourcing/fundamentals.yaml:28` (`store_db: ":memory:"`, no `fact_store_id`) takes the SQLite branch at `cli.py:332-335`, and so does `config/runs/aparinds-fy26-q4.yaml` (`store_db: data/store/aparinds.sqlite`) |
| `analysis/thesis_models/claude_client.py` | `ledger_cli.py:62` |
| `analysis/thesis_models/client.py` | `narrate.py:27`, `claude_client.py:20`, `subprocess_runner.py:20` |
| `analysis/thesis_models/settings.py` | `narrate.py:28`, `claude_client.py:21` |
| `analysis/thesis_models/subprocess_runner.py` | `claude_client.py:22` |
| `extraction/xbrl/*`, `extraction/results_pdf/{pdf_number_parser,pdf_source,…}` | Pipeline and pins (`run_config.py:71-98`). The audit's `phase05_*`, `xbrl` and `pdf_scope` test files test these modules, not dead ones |

Name collisions the brief warned about, now resolved:

- `comparatives` is SHARED. The live `run_comparatives.py` and the PG-lane `contracts/verification/comparative.py` both stay.
- `phase05` names test files only. Every `test_phase05_*` file imports live modules (`pipeline_steps`,
  `run_comparatives`, `xbrl_source`, `thesis_predicates` ← `falsifier_status.py:23`, `management_ledger`
  ← `earnings_update.py:39`), so all of them stay.
  `test_phase05_run_comparatives.py:46` imports `REASON_SELECTION_FAILED` from `comparatives` and is
  repointed.
- `xbrl` is entirely LIVE.

### Lane 1 tests (measured)

Deleted whole (17 files, 7,232 lines, 318 cases):

| File | Cases | Goes with |
|---|---|---|
| `analysis/thesis_models/test_thesis.py` | 29 | thesis drafter |
| `analysis/thesis_models/test_thesis_admission_label.py` | 1 | thesis adapters |
| `interface/commands/publication/test_thesis_adjudication.py` | 23 | `thesis`, `adjudicate` |
| `verification/comparison/test_thesis_cli.py` | 15 | `thesis_cli` |
| `interface/workflows/test_audit_r1_amount_tokens.py` | 18 | `thesis_models` verifier (imports `test_thesis`) |
| `interface/workflows/test_audit_r1_judgments.py` | 13 | the same |
| `interface/workflows/test_audit_thesis_numbers.py` | 17 | the same |
| `extraction/news/test_news_filing_dedup.py` | 18 | news |
| `sourcing/news/test_news.py` | 46 | news |
| `extraction/results_pdf/test_pdf_ocr.py` | 19 | OCR lane |
| `extraction/results_pdf/test_pdf_derived.py` | 5 | OCR lane (every test runs through `extract_consolidated_pl_via_ocr`) |
| `sourcing/exchange/test_bse.py` | 19 | `bse_source` (18 of 18 functions) |
| `sourcing/vendors/screener/test_screener.py` | 11 | `screener_source` |
| `interface/workflows/test_goal_runner.py` | 36 | `goal_runner` |
| `interface/workflows/test_audit_gold.py` | 7 | `goal_runner` (imports `test_goal_runner`) |
| `interface/workflows/test_report_builder.py` | 9 | `report_builder` |
| `interface/workflows/test_comparatives.py` | 32 | `report_cli._cached_stock`, `goal_runner`, `report_builder`, the dead half of `comparatives` |

Edited:

| File | Change | Measured |
|---|---|---|
| `extraction/results_pdf/test_bse_pdf.py` | Delete the 12 functions that use `goal_runner` / `bse_pdf_source`. Keep the 17 live `pdf_number_parser` tests | −12 cases, ~110 lines |
| `interface/entry/test_cli.py` | Delete the 10 validate/report/thesis functions. Keep `test_tijori_session_cookie_is_sufficient_credentials` and `test_tijori_email_password_without_cookie_is_rejected` (live `env_credentials`) | −11 cases, ~102 lines |
| `extraction/xbrl/test_phase05_run_comparatives.py:46` | Import `REASON_SELECTION_FAILED` from `run_comparatives` | 1 line |
| `companies/onboarding/test_retention_classes.py:65` | Replace the `screener_source.SOURCE_ID` import with the literal `"screener"`. Four more retention test files import this file and `test_backup_restore` transitively, so it unblocks them too | 1–2 lines |

**Lane 1 total: 35 modules / 9,309 product lines; 341 cases / ~7,444 test lines.** The audit
estimated about 557 cases and 14,900 lines. The difference is the LIVE half (pipeline e2e, reconcile,
phase05, xbrl, the SQLite store), which stays.

## Lane 2 — standalone Screener and Tijori acquisition commands

Commands: `screener-page`, `screener-company`, `screener-financials`, `screener-watchlist`,
`screener-watchlist-corroborate`, `tijori-{tables,shareholding,overview,analysis,events}`. They are
dispatched at `cli.py:552-562,585-587`, and registered at `cli_parser.py:227-236`.

### DEAD (11 modules; 9 deleted, 2 kept as test seams)

| Module | Lines | Only callers |
|---|---|---|
| `interface/commands/sourcing/tijori_cli_dispatch.py` | 162 | `cli.py:82,553` |
| `interface/commands/sourcing/tijori_{tables,shareholding,overview,analysis,events}_cli.py` | 1,007 | `tijori_cli_dispatch`, `cli_parser.py:35-41` |
| `interface/commands/sourcing/screener_company_cli.py` | 512 | `screener_cli_dispatch.py:22-35`, `cli_parser.py:26` |
| `interface/commands/verification/screener_watchlist_corroborate_cli.py` | 148 | `cli.py:88,581`, `cli_parser.py:48` |
| `verification/diagnostics/screener_watchlist_corroborate.py` | 441 | `screener_watchlist_corroborate_cli.py:28` |
| `sourcing/vendors/screener/screener_company.py` (kept: test seam) | 389 | `screener_company_cli.py:47`. `support/screener_company_support.py` drives the live `screener_company_parts`, `_sweep`, `_discovery` and `_models` parsers through `read_company` (5 test files) |
| `sourcing/vendors/tijori/tijori_retention.py` (kept: test seam) | 173 | `tijori_cli_dispatch.py:44`, `tijori_tables_cli.py:20`. `test_phase3_tijori_retention.py` proves the live `tijori_capture` seal through it |

### LIVE by data contract (keep the command)

| Command | Live reader that needs its output layout |
|---|---|
| `screener-financials` (`screener_financials_cli.py`, `sourcing/vendors/screener/screener_financials.py`) | Lane B: `upstox_crosscheck_cli.py:29,169,223,402` (`--screener-root` = "root of screener-financials output: `<root>/<symbol>/<basis>/`"). Three-source: `three_source_cli.py:139` defaults to `data/raw/watchlist/screener-financials`. Open bead **eqos-s2g**: "acquire standalone Screener financials for the sweep set … run upstox-crosscheck --basis standalone". Open bead **eqos-hvh**: "one retained bank Screener section". No other producer writes this layout. `vendor_surface_*` writes the snapshot store |
| `screener-watchlist` (`screener_watchlist_cli.py`) | `companies/identity/entity_map_sources.py:3,121`: S1 of the live `entity-map` command (`cli.py:589-590`) is "a published `screener-watchlist` artifact". The `sourcing/vendors/screener/screener_watchlist.py` library is LIVE too (`coverage/screens/screen_export.py:37`) |

### SHARED (2): keep, trim to the live part

| Module | Live use (file:line) |
|---|---|
| `interface/commands/sourcing/screener_cli_dispatch.py` | `EXIT_OK` / `EXIT_REFUSED`, imported by 11 live modules: `ledger_cli.py:74`, `legacy_cli.py:22`, `entity_map_cli.py:36`, `db_cli.py:37`, `coverage_cli.py:65`, `evidence_cli.py:74`, `upstox_cli.py:50`, `retention_cli.py:44`, `review_cli.py:35`, `upstox_crosscheck_cli.py:86`, and the dying `screener_watchlist_corroborate_cli.py:27`. Also imported by 29 test files, and `test_phase3_cli.py:723` pins its `EXIT_REFUSED`. It still dispatches the kept `screener-financials` and `screener-watchlist` |
| `interface/commands/sourcing/screener_page_cli.py` | `basis_topology` ← `sourcing/surfaces/vendor_surface_capture.py:40,137`. VENDOR-1 P3 Task 5 adds `watchlist_topology` to this file (`VENDOR-1-P3.md:773,1075-1078`) |

The parsers under `extraction/vendors/{screener,tijori}/`, `sourcing/vendors/tijori/{tijori_source,
tijori_capture,tijori_overview}.py` and `screener_session.py` are LIVE through `vendor_surface_readers`,
`vendor_surface_capture`, `onboard_cli`, `coverage_cli`, `screen_review` and `run_config` pins, as the
brief stated. They stay.

### Lane 2 tests (measured)

Deleted whole (10 files, 3,474 lines, 108 cases): `extraction/vendors/tijori/test_tijori_overview_cli.py`
(13), `interface/commands/sourcing/test_screener_company_cli.py` (12),
`interface/commands/sourcing/test_screener_session_cli.py` (16, `screener-page`),
`interface/commands/verification/test_screener_watchlist_corroborate_report.py` (10),
`verification/diagnostics/test_screener_watchlist_corroborate.py` (13),
`sourcing/vendors/tijori/test_tijori_{shareholding,analysis,events,tables}_cli.py` (8, 13, 17, 6),
`support/tijori_cli_support.py`.

Edited:

| File | Change | Measured |
|---|---|---|
| `interface/commands/sourcing/test_vendor_command_refusals.py` | Keep the 2 `screener-financials` cases. Delete the 20 other `_CASES` rows and `test_the_market_wide_events_run_refuses_without_a_cookie` | −21 cases |
| `extraction/vendors/screener/test_screener_company_hardening.py` | Delete the 3 functions that run `screener-company` through `main` | −3 cases, ~80 lines |
| `sourcing/vendors/tijori/test_phase3_tijori_retention.py` | Delete `_run_cli`, `_cli_failure_line` and `test_cli_writes_json_and_capture_and_exit_codes`. `test_parse_failure_keeps_committed_capture` stays: `:375-381` assert the retention/parse seam (OK capture, exact body, no tables, the island parse error) and only its tail `:383-387` runs `tijori-tables`, so only the tail goes | −1 case, ~47 lines |

**Lane 2 total: 9 modules / 2,270 product lines deleted, plus the two trims; 133 cases / ~3,600
test lines.** The audit's ~150 CLI cases included `screener-financials` and `screener-watchlist`,
which stay.

## Lane 3 — `upstox-crosscheck-sensitivity`

The command is `UPSTOX_SENSITIVITY_COMMAND = "upstox-crosscheck-sensitivity"`
(`upstox_sensitivity_cli.py:89`). The brief's `upstox-sensitivity` is the same command. It is dispatched
at `cli.py:577-579` and registered at `cli_parser.py:264`.

| Module | Class | Evidence |
|---|---|---|
| `interface/commands/verification/upstox_sensitivity_cli.py` (366) | DEAD | `cli.py:96`, `cli_parser.py:55` only |
| `verification/diagnostics/laneb_sensitivity.py` (595) | DEAD | `upstox_sensitivity_cli.py:69` only |
| `verification/diagnostics/laneb_sensitivity_model.py` (307) | SHARED | `MutationClass` ← `three_source.py:33` and `review_queue/triage.py:15` (← `comparison/tables.py:42`). The other 263 lines (cells, counts, report) are used only by the dead pair |

Tests (4 files, 1,852 lines, 73 cases): `verification/diagnostics/test_laneb_sensitivity.py` (50),
`test_laneb_sensitivity_render.py` (12), `interface/commands/verification/test_laneb_sensitivity_report.py`
(11), and `support/laneb_sensitivity_fixtures.py`. One edit: `verification/diagnostics/test_upstox_scope_guards.py:53`
lists `laneb_sensitivity.py` in `LANE_B_MODULES` and raises if the file is missing, so that row goes.
`_upstox_modules()` also discovers `upstox*.py`, and both of its parametrized tests use `path.name`
ids, so the deletion removes 4 retained-file ids too: `[upstox_sensitivity_cli.py]` and
`[laneb_sensitivity.py]` of `test_no_upstox_module_imports_the_fact_store_or_the_reconciler` and of
`test_only_the_transport_module_names_an_upstox_origin` (collected).
`test_compare_extraction_tables.py:97` and `test_phase3_compare.py:61` import only `MutationClass`
and stay. The triage tests stay: triage is live.

**Lane 3 total: 2 modules / 961 product lines plus a 263-line trim; 77 cases (73 + 4) / 1,852 test
lines.** Operational consumer: open bead eqos-ya6's sweep replay may still need the harness, so the
plan parks this lane until that bead is resolved.

## Summary counts

| Lane | DEAD | LIVE | SHARED | Deleted (measured) |
|---|---|---|---|---|
| 1 | 35 | 14 (listed) | 2 | 35 modules, 9,309 lines; 341 cases, ~7,444 test lines |
| 2 | 11 (9 deleted, 2 kept as seams) | 2 commands by data contract (+ the parser layer) | 2 | 9 modules, 2,270 lines (+~420 trimmed); 133 cases, ~3,600 test lines |
| 3 | 2 | 0 | 1 | 2 modules, 961 lines (+263 trimmed); 77 cases, 1,852 test lines (parked) |

## Other findings

- **Orphans (no importer at all, outside the lanes):** `sourcing/vendors/upstox/upstox_candle_retention.py`
  (the audit's candle item), `storage/memory/store.py`, `contracts/measurement/period.py`. These are
  not in scope.
- **Pins.** None of the deleted or modified files is in `EXTRACTOR_SOURCES`, `SHP_EXTRACTOR_SOURCES`
  or `VENDOR_EXTRACTORS` (`run_config.py:71-185`). The only pinned paths near the lanes are the
  Tijori parsers and `tijori_source.py`, and they stay untouched. No migration is involved: the news
  store is JSONL and the adjudication queue is a file.
- **`moved_support.OLD_PACKAGES`** lists 32 of the retired modules by name. Every use is a
  barred-name check (`test_phase3_*`, `test_upstox_scope_guards`), except `old_package_files("coverage")`,
  which reads files and holds none of them. Stale names are harmless there.
- **The gate has no deletion route.** `scripts/verify.sh gate` needs a red proof or a refactor
  baseline. A baseline fails on any removed node id (`verify.sh:578-609`, "a refactor that adds,
  removes or renames a test is not a refactor"). Either way a test-deleting slice routes CONTRACT.
  The refactor route still runs every other check (lint, mypy, suite, 800-line, skips, rails) and
  writes the exact `+id`/`-id` drift of the passed set to its log, which the plan uses as its
  outcome check under one stated exception.
- **Beads made obsolete:** eqos-4ff (split `goal_runner.py`) and eqos-msq.6 (move `bse_pdf_source.py`
  onto the document rules). eqos-bnx's description cites `api/thesis_cli.py` as the old drafter.
  RESEARCH-3 narrate uses only the kept `client` / `settings` / `claude_client`.

## Round 1 corrections (2026-11-07)

- **Lane 1 cannot split at validate/report vs thesis.** `analysis/thesis_models/adapters.py:37-38`
  imports `goal_runner.StockReport` under `TYPE_CHECKING`, so deleting `goal_runner` before the
  drafter fails `mypy --strict`; and the validate/report parsers use `thesis_cli.add_wave_arg` and
  `wave_selection`. The plan retires the four commands in one task (277 ids: 254 in 15 whole files,
  12 in `test_bse_pdf.py`, 11 in `test_cli.py`). It also removes R2's uncollectable intermediate
  state of `test_cli.py` (`:26` imports `validate_cli`).
- **Counts.** Tasks 2–4 (executable now): 474 ids (lane 1 341, lane 2 133). Lane 3 (parked): 77.
  Eventual total 551. The earlier 548 missed the 4 scope-guard ids and counted the retained
  `test_parse_failure_keeps_committed_capture` as deleted.
- **Navigation text missed earlier (R10).** `interface/entry/README.md:3` (wave selection),
  `sourcing/exchange/README.md:3` (BSE results/PDFs, comparator file cache),
  `sourcing/vendors/screener/README.md:3` (older derived quarterly P&L adapter),
  `interface/commands/sourcing/README.md:3` (Tijori commands), `config/coverage/watchlist.yaml:40-43,177-179`
  (`validate --watchlist`), and prose in live modules that names a deleted module as current:
  `extraction/results_pdf/pdf_number_parser.py:31-37,78`, `sourcing/vendors/screener/screener_session.py:3-5`,
  `screener_company_parts.py:286-288`, `screener_watchlist_models.py:289-291`. Pyproject pythonpath
  entries for folders that empty: `tests/equity_os/interface/commands/publication`,
  `tests/equity_os/extraction/news`, `tests/equity_os/sourcing/news`.
- **Reviewed residuals (kept).** `scripts/restructure/*` (history, incl. `oversize.tsv:3`),
  `moved_support.py` barred names, `screener_session_models.py:8,32` (pinned in `VENDOR_EXTRACTORS`),
  lineage prose in `screener_financials_cli.py:3,164`, fixture/id strings that only contain a
  command-like word, live test names containing `report_cli` as a substring
  (`test_phase05_report_artifact.py:211`, `test_pipeline_e2e.py:341`, `test_compare_runs.py:638`),
  and `scripts/render_dashboard.py:93,100` (dashboard rows for the news folders; orchestrator).
