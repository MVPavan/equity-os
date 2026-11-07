# LEGACY-1 Implementation Plan

**Status:** approved 2026-11-07 (gpt-6.1-sol, `APPROVE` in plan review 3). Execution waits for the
five-company test's final live window (see Timing); Task 1 also waits for `eqos-ya6`.

**Origin:** Owner approval (2026-11-07) to retire three legacy lanes, on the condition that
nothing still in use is cut. The candidate list comes from the pre-restructure test audit
(`scratchpad/restructure/test-audit.md` §1b). Every keep-or-cut call rests on the caller trace in
`docs/plans/LEGACY-1-trace.md`, measured on `main` at `4dec81c4`. No spec was needed: the work deletes
code and adds no behaviour. Each task leaves `main` green. Revised after plan review round 1
(`scratchpad/legacy-1/rounds/plan-review-1/findings.md`, R1–R12) and the orchestrator's rulings on it.
**Goal:** Remove the commands, modules and tests that no current entry point needs. Keep or migrate
everything that a live path, a live data contract or an open bead still calls.
**Out of scope:**
- The SQLite `FactStore` (`storage/facts/fact_store.py`), its cutover rollback and the default SQLite
  run config. They are LIVE (`cutover.py:45,305` ← `cli.py:318`, `config/sourcing/fundamentals.yaml`).
  Ruled: they stay.
- The pipeline e2e family, reconcile (`agreement`, `fact_view`, `gold_file`, `diagnostics/report`),
  `xbrl_source`, `sec_source` and the `test_phase05_*` files. All of them are LIVE.
- The `screener-financials` and `screener-watchlist` commands. Live data contracts read their output
  (trace, lane 2). Ruled: they stay.
- Function-level dead code inside LIVE modules (for example `gold_file` helpers that only
  `goal_runner` used). That goes to a follow-up bead.
- Renaming or relocating the shared `EXIT_OK` / `EXIT_REFUSED`, `basis_topology` and
  `watchlist_topology`.
- Config schema and data: watchlist `news_aliases` and `wave`, the `news-store` catalog and
  `sources.yaml` entries, retained data under `data/`, `docs/research/validation/`.
- `upstox_candle_retention.py` and the other orphans the trace lists.
- Historical documents. Plans, specs, research, evidence, reviews, workstream plans,
  `scripts/restructure/*` move tables and `docs/history/` keep the old names, as `repo-map.md` requires.
- A deletion route in `scripts/verify.sh`. Acceptance uses the existing gate with one stated
  exception (Evidence procedure).
- Commits, beads and the dashboard, which belong to the orchestrator.

**Constraints:**
- Never edit a committed migration, or any file named in `EXTRACTOR_SOURCES`,
  `SHP_EXTRACTOR_SOURCES` or `VENDOR_EXTRACTORS` (`equity_os/verification/comparison/run_config.py`).
  Checked: no file this plan deletes or modifies is in those sets, and no migration is involved. Any
  edit that would need one stops the task and is reported as a conflict.
- Crisp, minimal code. Delete what is not needed and add nothing speculative
  (`.claude/rules/core/04-agent-stack.md`, "Code size").
- One writer per file. `cli.py` and `cli_parser.py` are edited by every task, so tasks run in order,
  never in parallel.
- Retirement never delays the five-company test. Tasks 2–5 start only after that test's final live
  window has closed and its evidence is recorded (Timing).
- No test runs `-n 24` while another gate or Stage 4 is running. Scoped runs use `-n 8`.
- Stage explicit files only. A deleted file is staged with `git rm <path>`.
- Line numbers below are at `4dec81c4`. At the retirement base the implementer locates each edit by
  name, not by line.
- Each worker records `git status --porcelain` and `git diff` (for paths already dirty) at its start.
  At its end it compares both against that record. It reports every new entry, and every
  already-dirty path whose diff changed, and says which of them are its own task's Files. It reports
  any other change as is and never restores it. It never claims a file is unchanged just because its
  status entry is the same. A clean integration tree before the Evidence procedure is the
  orchestrator's job.

## Size win (measured; method in the trace)

Case counts are node ids from `uv run pytest --collect-only -q` at `4dec81c4`. Whole-file and
product line counts are `wc -l`. Partial-file test lines are approximate (`~`).

| Lane | Product deleted | Product trimmed | Test cases removed | Test lines removed |
|---|---|---|---|---|
| 1 validate/report/thesis/news (Tasks 2, 3) | 35 modules, 9,309 lines | `thesis_models/__init__.py` 122 → docstring; `cli.py`, `cli_parser.py` blocks | 341 (318 in 17 whole files + 12 in `test_bse_pdf.py` + 11 in `test_cli.py`) | 7,232 whole + ~212 partial |
| 2 Screener/Tijori commands (Task 4) | 9 modules, 2,270 lines | `screener_cli_dispatch.py`, `screener_page_cli.py` (~420 lines) | 133 (108 in 10 whole files + 21 + 3 + 1) | 3,474 whole + ~130 partial |
| **Executable now (Tasks 2–4)** | **44 modules, 11,579 lines** | **~420 lines + lane 1 trims** | **474** | **~11,050** |
| 3 Lane B sensitivity (Task 1, parked) | 2 modules, 961 lines | `laneb_sensitivity_model.py` 307 → `MutationClass` (−263) | 77 (73 in 3 whole files + 4 scope-guard parametrizations) | 1,852 whole + 1 |
| **Eventual (all four tasks)** | **46 modules, 12,540 lines** | **~800 lines** | **551** | **~12,900** |

The audit estimated ~760 cases. The gap is what the trace found LIVE: the pipeline e2e, reconcile,
phase05, xbrl and SQLite-store tests, plus the `screener-financials` and `screener-watchlist` CLI
tests. All counts are re-measured at the retirement base by the Evidence procedure; a difference is
reconciled per node id before the first task.

## File map

Paths are relative to `equity_os/` unless they start with `tests/`, `docs/`, `config/`,
`scratchpad/` or are a top-level file.

| Path | Change | Task |
|---|---|---|
| `interface/commands/verification/upstox_sensitivity_cli.py`, `verification/diagnostics/laneb_sensitivity.py` | delete | 1 |
| `verification/diagnostics/laneb_sensitivity_model.py` | modify: keep only `MutationClass` (all 9 members, values unchanged) and a one-line docstring | 1 |
| `tests/equity_os/verification/diagnostics/test_laneb_sensitivity.py`, `test_laneb_sensitivity_render.py`, `tests/equity_os/interface/commands/verification/test_laneb_sensitivity_report.py`, `tests/equity_os/support/laneb_sensitivity_fixtures.py` | delete | 1 |
| `tests/equity_os/verification/diagnostics/test_upstox_scope_guards.py` | modify: drop `laneb_sensitivity.py` from `LANE_B_MODULES` | 1 |
| `interface/commands/verification/validate_cli.py`, `interface/commands/publication/report_cli.py`, `interface/workflows/goal_runner.py`, `interface/workflows/report_builder.py`, `interface/workflows/comparatives.py`, `sourcing/exchange/comparator_cache.py`, `sourcing/exchange/bse_source.py`, `sourcing/exchange/bse_pdf_source.py`, `sourcing/vendors/screener/screener_source.py`, `extraction/results_pdf/ocr_engine.py`, `extraction/results_pdf/pdf_ocr_recovery.py` | delete | 2 |
| `interface/commands/publication/thesis_cli.py`, `interface/commands/publication/adjudication_cli.py`, `interface/entry/wave_selection.py`, `analysis/thesis_models/{adapters,adjudication,codex_client,contracts,draft_parser,pipeline,prompt,render,verifier}.py` | delete | 2 |
| `interface/workflows/run_comparatives.py` | modify: take `REASON_INCOMPATIBLE`, `REASON_SELECTION_FAILED` and `_unavailable` verbatim from `comparatives.py` | 2 |
| `analysis/thesis_models/__init__.py` | modify: docstring only, no re-exports | 2 |
| `extraction/results_pdf/pdf_number_parser.py`, `sourcing/vendors/screener/screener_session.py` | modify: docstring/comment sentences that name a deleted module as current (listed in Task 2) | 2 |
| `tests/equity_os/interface/workflows/test_goal_runner.py`, `test_audit_gold.py`, `test_report_builder.py`, `test_comparatives.py`, `test_audit_r1_amount_tokens.py`, `test_audit_r1_judgments.py`, `test_audit_thesis_numbers.py`, `tests/equity_os/sourcing/exchange/test_bse.py`, `tests/equity_os/sourcing/vendors/screener/test_screener.py`, `tests/equity_os/extraction/results_pdf/test_pdf_ocr.py`, `test_pdf_derived.py`, `tests/equity_os/analysis/thesis_models/test_thesis.py`, `test_thesis_admission_label.py`, `tests/equity_os/interface/commands/publication/test_thesis_adjudication.py`, `tests/equity_os/verification/comparison/test_thesis_cli.py` | delete | 2 |
| `tests/equity_os/extraction/results_pdf/test_bse_pdf.py` | modify: delete 12 functions (listed in Task 2) | 2 |
| `tests/equity_os/interface/entry/test_cli.py` | modify: keep only the two Tijori credential tests | 2 |
| `tests/equity_os/extraction/xbrl/test_phase05_run_comparatives.py` | modify: line 46 imports from `run_comparatives` | 2 |
| `tests/equity_os/companies/onboarding/test_retention_classes.py` | modify: line 65 becomes `LEGACY_SCREENER_SOURCE = "screener"` | 2 |
| `config/coverage/watchlist.yaml` | modify: the two `validate --watchlist` comment blocks (`:40-43`, `:177-179`) | 2 |
| `pyproject.toml`, `uv.lock` | modify: drop the `ocr` extra, the `rapidocr_onnxruntime` mypy override and the `tests/equity_os/interface/commands/publication` pythonpath entry (Task 2); drop the `tests/equity_os/extraction/news` and `tests/equity_os/sourcing/news` pythonpath entries (Task 3); run `uv lock` | 2, 3 |
| `interface/commands/sourcing/news_cli.py`, `contracts/sourcing/news.py`, `extraction/news/` (`__init__.py`, `entity.py`, `events.py`, `README.md`), `sourcing/news/` (`__init__.py`, `health.py`, `news_bse.py`, `news_common.py`, `news_et.py`, `news_nse.py`, `README.md`), `storage/records/news_store.py` | delete | 3 |
| `tests/equity_os/sourcing/news/test_news.py`, `tests/equity_os/extraction/news/test_news_filing_dedup.py` | delete | 3 |
| `interface/commands/sourcing/tijori_cli_dispatch.py`, `tijori_{tables,shareholding,overview,analysis,events}_cli.py`, `screener_company_cli.py`, `interface/commands/verification/screener_watchlist_corroborate_cli.py`, `verification/diagnostics/screener_watchlist_corroborate.py` | delete | 4 |
| `interface/commands/sourcing/screener_cli_dispatch.py` | modify: drop the `screener-page` and `screener-company` branches | 4 |
| `interface/commands/sourcing/screener_page_cli.py` | modify: drop the command; keep `basis_topology` and `watchlist_topology` | 4 |
| `sourcing/vendors/screener/screener_company_parts.py`, `sourcing/vendors/screener/screener_watchlist_models.py` | modify: one docstring sentence each that names a retired command as current (Task 4) | 4 |
| `tests/equity_os/extraction/vendors/tijori/test_tijori_overview_cli.py`, `tests/equity_os/interface/commands/sourcing/test_screener_company_cli.py`, `test_screener_session_cli.py`, `tests/equity_os/interface/commands/verification/test_screener_watchlist_corroborate_report.py`, `tests/equity_os/verification/diagnostics/test_screener_watchlist_corroborate.py`, `tests/equity_os/sourcing/vendors/tijori/test_tijori_{shareholding,analysis,events,tables}_cli.py`, `tests/equity_os/support/tijori_cli_support.py` | delete | 4 |
| `tests/equity_os/interface/commands/sourcing/test_vendor_command_refusals.py`, `tests/equity_os/extraction/vendors/screener/test_screener_company_hardening.py`, `tests/equity_os/sourcing/vendors/tijori/test_phase3_tijori_retention.py` | modify: delete the retired-command cases and tails (listed in Task 4) | 4 |
| `tests/equity_os/interface/commands/sourcing/test_screener_topology.py` | create only if `test_screener_session_cli.py` holds `basis_topology` / `watchlist_topology` tests at the base: they move here verbatim | 4 |
| `interface/entry/cli.py`, `interface/entry/cli_parser.py` | modify: drop each lane's imports, dispatch blocks and parser registrations; update `_DESCRIPTION` | 1–4 |
| READMEs: `verification/diagnostics/` (1), `interface/`, `interface/entry/`, `interface/workflows/`, `interface/commands/{verification,publication}/`, `extraction/results_pdf/`, `sourcing/exchange/`, `sourcing/vendors/screener/`, `sourcing/transport/`, `analysis/`, `analysis/thesis_models/` (2), `sourcing/`, `extraction/`, `storage/records/`, `contracts/sourcing/`, `interface/commands/sourcing/`, `sourcing/transport/` (3), `interface/commands/sourcing/` (3, 4) | modify: drop the retired names and descriptions (each task edits its own lines) | 1–4 |
| `scratchpad/legacy-1/<slice>/` (not committed) | create: base and closing evidence (Evidence procedure) | 1, 5 |

Not changed, checked by grep: `CONTEXT.md` and both repo maps name only kept entry points;
`.claude/project/brief.md:47` names `claude_client.py`, which stays; `.claude/project/docs-index.md`
points at measurement records, not at commands; `tests/equity_os/support/moved_support.py` uses the
retired names only in barred-name checks. `docs/research/upstox-lane-b-first-measurement.md` Part 3
stays a record of a finished run. `docs/workstreams/status.md:44` (eqos-4ff) is a generated mirror,
refreshed by the orchestrator. FIVE-1's `validate` sentence is history by the time retirement runs.

Reviewed residuals (kept on purpose; the per-task greps below do not search for them):
`scripts/restructure/*` move tables and `oversize.tsv` (history); `moved_support.py` barred names;
`extraction/vendors/screener/screener_session_models.py:8,32` (pinned in `VENDOR_EXTRACTORS`; old
`fundamentals.ingest.screener_source` spelling); lineage prose in `screener_financials_cli.py:3,164`
("mirrors `screener-page`"); fixture and id strings that only contain a command-like word
(`screener-page.html`, `test-screener-page`, `screener-page-not-the-capture`,
`tijori-shareholding-tree-v1`); live test names that contain `report_cli` as a substring
(`trusted_report_cli_composition`, `test_report_cli_prints_the_run`); `scripts/render_dashboard.py`
news rows and layout blocks (dashboard, orchestrator-owned follow-up); the live vendor READMEs
(`equity_os/extraction/vendors/README.md:3`, `equity_os/sourcing/vendors/README.md:3`). Every
executable-reference grep excludes `scripts/restructure/` with the pathspec `':!scripts/restructure/'`.

## Kept on purpose (LIVE or SHARED, with the recommendation)

| Module | Recommendation | Reason |
|---|---|---|
| `comparatives.py` | Migrate, then delete (Task 2) | Live use is 15 lines (`run_comparatives.py:31-35`); the rest is `goal_runner`/`report` only |
| `thesis_models/__init__.py` | Keep, trim to a docstring (Task 2) | Live imports of `thesis_models.client` (`narrate.py:27`) run it, and today it loads the whole dead drafter |
| `thesis_models/{claude_client,client,settings,subprocess_runner}.py` | Keep | `ledger_cli.py:62`, `narrate.py:27-28`, `claude_client.py:22` |
| `laneb_sensitivity_model.py` | Keep, trim to `MutationClass` (Task 1) | `three_source.py:33`, `review_queue/triage.py:15`. The values may be persisted through triage, so they stay unchanged |
| `screener_cli_dispatch.py` | Keep, trim (Task 4) | `EXIT_OK` / `EXIT_REFUSED` are imported by 11 live modules and 29 test files. It still dispatches the two kept commands |
| `screener_page_cli.py` | Keep, trim (Task 4) | `basis_topology` ← `vendor_surface_capture.py:40`; VENDOR-1 P3 Task 5 adds `watchlist_topology` here |
| `screener-financials` command (`screener_financials_cli.py`, `sourcing/vendors/screener/screener_financials.py`) | Keep (ruled) | The only producer of the layout read by `upstox_crosscheck_cli.py:402` and `three_source_cli.py:139`. Open Lane B beads eqos-s2g and eqos-hvh need fresh captures in it |
| `screener-watchlist` command (`screener_watchlist_cli.py`) | Keep (ruled) | Its artifact is S1 of the live `entity-map` (`entity_map_sources.py:3,121`) |
| `sourcing/vendors/screener/screener_company.py`, `sourcing/vendors/tijori/tijori_retention.py` | Keep (follow-up bead) | No product caller after Task 4. They remain the integration seams that drive the live parsers and the live `tijori_capture` seal (`support/screener_company_support.py:38,266`, `test_phase3_tijori_retention.py:241-254`). Deleting them would delete parser protection |
| `fact_store.py`, its rollback and default config, `xbrl_source.py`, `sec_source.py`, `pipeline*.py`, `run_comparatives.py`, reconcile modules | Keep (ruled for the store) | LIVE (trace, lane 1) |

## Timing and in-flight work

**Window.** Tasks 2–5 run after the five-company test's final live window and its evidence capture
are recorded, and never delay it. By then VENDOR-1 P3 Tasks 4–11 and FIVE-1 have landed, so no
acquisition, rehearsal or live interval uses the tree and no other plan writes these files.
FIVE-1 Task 4 updates its existing tests normally and needs no amendment. Task 1 runs only after its
own prerequisite (Task 1, Dependencies). Each tree this plan produces gets its own gate evidence;
no earlier tip's approval transfers to it.

| Candidate file | In-flight change | Resolution |
|---|---|---|
| `screener_page_cli.py` | VENDOR-1 P3 Task 5 adds `watchlist_topology` (`VENDOR-1-P3.md:773,1076`) | Landed before the window. Task 4 keeps `basis_topology` and `watchlist_topology` in place |
| `test_screener_session_cli.py` (deleted in Task 4) | P3 Task 5 may put topology tests here | Task 4 moves them verbatim to `test_screener_topology.py` first; their new ids go in `moved.ids` |
| Deleted or edited test files that FIVE-1 Task 4 or P3 changed (`test_cli.py`, `test_goal_runner.py`, `test_news.py`, the Tijori CLI tests, `support/tijori_cli_support.py`) | Their tests may change before the window | The Evidence procedure re-collects at the base and reconciles every manifest difference per node id |
| `comparatives.py` (deleted in Task 2) | `VENDOR-1-P3.md:267` names it as a user of `validate_nse_entity_identities` (no edit planned) | No code conflict; the P3 sentence becomes history. `xbrl_identity.py` is pinned and is not touched |
| `cli.py` | The `research-4` branch changes its run-draft imports | The RESTRUCTURE-1 replay of `research-4` may hit an import-block conflict near this plan's hunks. Whoever runs the replay resolves it |
| Five-company test | It uses none of the retired commands (`grep` of `FIVE-COMPANY-TEST.md`) | It runs before retirement, on the unretired tree |

## Evidence procedure (orchestrator; slice `S`)

`S` is `legacy-1` for Tasks 2–5 and `legacy-1-lane3` for Task 1. `D` is `scratchpad/legacy-1/<S>`.
`COLLECT` is this exact command, run from the repo root:
`PYTEST_DEBUG_TEMPROOT="${XDG_CACHE_HOME:-$HOME/.cache}/equity-os/pytest-tmp" uv run pytest tests/equity_os --collect-only -q -p no:cacheprovider -p no:warnings`.
`IDS <log> <out>` is: the log's last line reads `N tests collected`, then
`grep -E '^tests/equity_os/[^[:space:]]*::' <log> | sort -u > <out>` (whole lines, so parameter ids
keep their spaces) and `wc -l < <out>` equals `N`.

**Base (immediately before the slice's first task, on a clean integration tree, no other gate running):**
1. `git rev-parse HEAD > D/base-rev.txt`.
2. `scripts/verify.sh baseline <S>` prints `ROUTE: PASS` and writes `scratchpad/gate/<S>-baseline.json`
   (the passed node ids and the skipped count).
3. `COLLECT > D/collect-before.log 2>&1` exits 0; `IDS D/collect-before.log D/before.ids`.
4. Write the slice's removal selectors (the exact lists in the task's Approach: one full-path
   `file::` per deleted test file, one `file::function` per deleted function, one full node id per
   removed parametrization) to `D/selectors.txt`, then `grep -F -f D/selectors.txt D/before.ids > D/manifest.ids`.
   Its count must equal this plan's measured count (474 for `legacy-1`, 77 for `legacy-1-lane3`).
   Every difference is reconciled per node id against the commits since `4dec81c4`: an id that tests a
   retired command stays in the manifest; one that tests live behaviour moves, with its new id in
   `D/moved.ids` (empty file if none). The reviewed manifest is frozen before the first task starts.
5. Skip ceiling for this run, by code: `python3 -c 'import json,sys;b=json.load(open(sys.argv[1]));m=set(open(sys.argv[2]).read().split("\n"))-{""};print(b["skipped"]-len(m-set(b["tests"])))' scratchpad/gate/<S>-baseline.json D/manifest.ids > D/skips.txt`.
   The base is green, so a manifest id outside the passed set was skipped (no manifest file uses
   `xfail`). This drops the retired skips, such as the two optional real-engine OCR tests
   (`test_pdf_ocr.py:509-516`, `test_goal_runner.py:990-997`), from the ceiling.

**Close (on the slice's final revision, clean integration tree, no other gate running):**
1. `git rev-parse HEAD > D/final-rev.txt`. `git log --format='%h %s' "$(cat D/base-rev.txt)..HEAD"`
   lists only this slice's commits. A commit from another plan in that range has each of its added or
   removed node ids reconciled into `D/reconciled.ids` (`+id` or `-id`, one per line, with the commit);
   never a whole file, never a count.
2. `COLLECT > D/collect-after.log 2>&1` exits 0; `IDS D/collect-after.log D/after.ids`.
3. Exact set check, both commands exit 0:
   `diff <(comm -23 D/before.ids D/after.ids) <( { cat D/manifest.ids; sed -n 's/^-//p' D/reconciled.ids 2>/dev/null; } | sort -u)` and
   `diff <(comm -13 D/before.ids D/after.ids) <( { cat D/moved.ids; sed -n 's/^+//p' D/reconciled.ids 2>/dev/null; } | sort -u)`.
4. Gate: `VERIFY_SCOPE_BASE="$(cat D/base-rev.txt)" VERIFY_BASELINE_SKIPS="$(cat D/skips.txt)" scripts/verify.sh gate <S>`.
   This is the one exception to a normal gate: the refactor route's test-set check is expected to
   fail, because the slice removes tests. Accepted only when every line holds: `baseline OK`,
   `gate OK` (pytest, ruff, format, mypy --strict), `skips OK`, `rails OK`, and `test-set FAIL`, with
   exit 2 and `ROUTE: CONTRACT  a refactor changed the test set`. Any STOP, any other FAIL or any other
   CONTRACT reason rejects the slice. Coverage stays advisory. No changed file is over 800 lines at
   `4dec81c4` (largest edited: `test_bse_pdf.py`, 778, shrinking); if one is at the base, only a file
   legitimately listed through `VERIFY_OVERSIZE_LIST` may pass, and no size check is waived.
5. Outcome check on that gate's log (`scratchpad/gate/<S>-<ts>.log`), exit 0:
   `diff <(awk '/^=== test-set drift ===$/{f=1;next} /^=== /{f=0} f' <log> | sed -n 's/^-//p' | sort -u) <(comm -12 D/manifest.ids <(python3 -c 'import json,sys;print("\n".join(json.load(open(sys.argv[1]))["tests"]))' scratchpad/gate/<S>-baseline.json | sort -u))`,
   and the drift's `+` lines equal `D/moved.ids` that passed. A retained id that passed at the base and
   does not pass now appears as an extra `-` line and rejects the slice. Reconciled ids extend both
   sides exactly as in step 3.
6. Record the result as "LEGACY-1 `<S>`: deletion exception, CONTRACT test-set only", never as a gate
   PASS or as live acceptance.

## Task 1: Retire `upstox-crosscheck-sensitivity` (parked)

Goal: `eqos` no longer offers `upstox-crosscheck-sensitivity`. Lane B crosscheck, triage and
three-source behave as before, because `MutationClass` is unchanged.

Files:
- Delete: `interface/commands/verification/upstox_sensitivity_cli.py`,
  `verification/diagnostics/laneb_sensitivity.py`, the four Lane 3 test files in the file map.
- Modify: `verification/diagnostics/laneb_sensitivity_model.py`, `interface/entry/cli.py`
  (imports `95-97`, dispatch `577-579`), `interface/entry/cli_parser.py` (imports `55-57`, call
  `264`), `verification/diagnostics/README.md`, `tests/equity_os/verification/diagnostics/test_upstox_scope_guards.py`.
- Test: the existing triage, three-source and scope-guard tests, unchanged apart from `LANE_B_MODULES`.

Interfaces:
- Consumes: none.
- Produces: `laneb_sensitivity_model.MutationClass`, with the same 9 members and values.

Approach: Run the Evidence procedure's Base for `legacy-1-lane3`. Selectors: the three test files
`tests/equity_os/verification/diagnostics/test_laneb_sensitivity.py::`,
`tests/equity_os/verification/diagnostics/test_laneb_sensitivity_render.py::`,
`tests/equity_os/interface/commands/verification/test_laneb_sensitivity_report.py::`, and the four
scope-guard ids `test_upstox_scope_guards.py::test_no_upstox_module_imports_the_fact_store_or_the_reconciler[upstox_sensitivity_cli.py]`,
`…[laneb_sensitivity.py]`, `test_upstox_scope_guards.py::test_only_the_transport_module_names_an_upstox_origin[upstox_sensitivity_cli.py]`
and `…[laneb_sensitivity.py]` (written as full node ids). `_upstox_modules()` discovers
`upstox*.py` and appends `LANE_B_MODULES`, so deleting the CLI and the `LANE_B_MODULES` row removes
exactly those four. Then delete the two modules and four test files. Reduce
`laneb_sensitivity_model.py` to `MutationClass` plus a docstring saying it is the defect vocabulary
that triage and three-source use. Remove the import and dispatch block from `cli.py` and the parser
registration from `cli_parser.py`. Drop the `laneb_sensitivity.py` row from `LANE_B_MODULES`. Remove
"and its sensitivity" from the diagnostics README. Then run the Evidence procedure's Close for
`legacy-1-lane3`.

Verification:
1. `uv run ruff check equity_os tests/equity_os && uv run ruff format --check equity_os tests/equity_os && uv run mypy --strict equity_os` exits 0.
2. `git grep -nE 'equity_os\.[a-z_.]*\b(upstox_sensitivity_cli|laneb_sensitivity)\b|crosscheck-sensitivity|SensitivityReport|SensitivityCell' -- equity_os scripts ':!scripts/restructure/' config 'tests/equity_os/**.py'` prints only `moved_support.py` lines.
3. `uv run python -c "from equity_os.interface.entry.cli_parser import build_parser as b; a=b()._subparsers._group_actions[0].choices; assert 'upstox-crosscheck-sensitivity' not in a"` exits 0.
4. Scoped tests: `T=$( { echo tests/equity_os/verification/diagnostics/test_upstox_scope_guards.py; git grep -lE 'laneb_sensitivity_model|three_source|review_queue|laneb_triage|equity_os\.interface\.entry\.cli\b|equity_os\.interface\.entry import cli|cli_parser' -- 'tests/equity_os/**.py'; } | sort -u ); test -n "$T" && PYTEST_DEBUG_TEMPROOT="${XDG_CACHE_HOME:-$HOME/.cache}/equity-os/pytest-tmp" uv run pytest -n 8 $T` passes.
5. The Evidence procedure's Close for `legacy-1-lane3` is accepted (77 ids removed, none added).

Dependencies: Hard prerequisite: bead eqos-ya6 is resolved and its resolution states that its sweep
replay no longer needs the sensitivity harness. Until then this task stays outside the executable
batch and is not dispatched. It runs after Task 5 (it edits `cli.py` and `cli_parser.py`).

Risks: `MutationClass` values may be persisted through triage, so the members stay. eqos-s2g notes
the standalone basis has "no sensitivity figure"; if a new figure is needed, eqos-ya6 is not resolved
in the sense above and the task stays parked.

## Task 2: Retire `validate`, `report`, `thesis` and `adjudicate` with the gold loop, the OCR lane, the Slice-1 adapters and the multi-model drafter

Goal: `eqos` no longer offers `validate`, `report`, `thesis` or `adjudicate`. `eqos run` (PG and
SQLite branches) still produces its QoQ/YoY comparatives through `run_comparatives`. Ledger narration
(`narrate.py`) and `ledger_cli` still reach the model through `thesis_models.client` and
`claude_client`, with nothing else loaded.

One task, not two: `analysis/thesis_models/adapters.py:38` imports `goal_runner.StockReport` under
`TYPE_CHECKING`, and the validate/report parsers use `thesis_cli.add_wave_arg` and `wave_selection`.
Deleting either half alone fails `mypy --strict` or `cli_parser`.

Files:
- Delete: the 23 Task 2 product modules and the 15 Task 2 test files in the file map.
- Modify: `interface/workflows/run_comparatives.py`, `analysis/thesis_models/__init__.py`,
  `interface/entry/cli.py` (imports for `report_cli`, `validate_cli` and `thesis_cli` `58-62`, `99`;
  dispatch `640-650` and `656-658`), `interface/entry/cli_parser.py` (`VALIDATE_COMMAND`,
  `REPORT_COMMAND`, imports `12` and `19-23`, the parser blocks at `142-226`, `_DEFAULT_WATCHLIST_PATH`
  if unused), `extraction/results_pdf/pdf_number_parser.py`, `sourcing/vendors/screener/screener_session.py`,
  `config/coverage/watchlist.yaml`, `pyproject.toml`, `uv.lock`,
  `tests/equity_os/extraction/results_pdf/test_bse_pdf.py`, `tests/equity_os/interface/entry/test_cli.py`,
  `tests/equity_os/extraction/xbrl/test_phase05_run_comparatives.py`,
  `tests/equity_os/companies/onboarding/test_retention_classes.py`, and the READMEs of `interface/`,
  `interface/entry/`, `interface/workflows/`, `interface/commands/verification/`,
  `interface/commands/publication/`, `extraction/results_pdf/`, `sourcing/exchange/`,
  `sourcing/vendors/screener/`, `sourcing/transport/`, `analysis/` and `analysis/thesis_models/`.
- Test: `test_phase05_run_comparatives.py` and `test_pipeline_e2e.py` prove that the moved names
  still drive the run's comparatives; `test_narrate_flow.py`, `test_narrate_refusals.py`,
  `test_narrate_checks.py` and the ledger CLI tests prove narration, all unchanged.

Interfaces:
- Consumes: none.
- Produces:
  - `run_comparatives.REASON_INCOMPATIBLE`, `run_comparatives.REASON_SELECTION_FAILED` and
    `run_comparatives._unavailable(kind, period_start, period_end, reason) -> ComparativeChange`,
    moved verbatim with the `date` import they need; the run's output stays byte-identical.
  - `equity_os.analysis.thesis_models` is a package of `claude_client`, `client`, `settings` and
    `subprocess_runner`, with no package-level re-exports.

Approach: Move the three names into `run_comparatives.py` and delete its `comparatives` import.
Delete the modules and test files. Reduce `thesis_models/__init__.py` to its docstring, rewritten to
"Model clients for ledger narration", and rewrite the `thesis_models` README to that one line.
Remove the dispatch and parser wiring for all four commands.

In `test_bse_pdf.py`, delete `test_download_falls_back_to_attachlive_on_404`,
`test_nse_xbrl_and_bse_results_pdf_reconcile_to_agree`, `test_parse_filed_at_tolerates_bad_values`,
`test_pdf_split_revenue_yields_single_first_party_for_revenue`, the three `test_select_results_row_*`
functions, `test_standalone_only_pdf_is_skipped_not_blocked`,
`test_to_announcement_rejects_non_pdf_and_parses_size` and the three `test_verify_*` functions, and
the helpers and imports they leave unused. Keep the 17 `pdf_number_parser` tests.

In `test_cli.py`, delete the eight `test_validate_*` functions, `test_report_and_thesis_accept_wave_option`
(2 ids) and `test_thesis_wave_filter_selects_only_that_waves_symbols`, with `_validate_args`,
`_FakeClient`, `_write_gold`, `_thesis_args`, `_WAVE1_SYMBOLS`, `_WAVE2_SYMBOLS`, `_QUARTER` and every
import they leave unused. What remains is `pytest`, `_tijori_credentials_from_env` and the two Tijori
credential tests; set the module docstring to name them. In `test_retention_classes.py`, replace the
`screener_source` import with `LEGACY_SCREENER_SOURCE = "screener"`: the catalog still lists that id
at `source_catalog.py:200`.

Prose that names a deleted module as current: in `pdf_number_parser.py` remove the OCR-recovery
sentences of the module docstring (`:31-37`, ending the paragraph at the text-layer lane) and drop
`goal_runner, ` from the comment at `:78`; in `screener_session.py:3-5` drop the "sibling of
`screener_source`" clause. In `watchlist.yaml` delete the `validate --watchlist` sentences at
`:40-43` and `:177-179`, keeping the sentences that say each stock carries its own `wave`. No key or
value changes.

Remove the `ocr` optional extra, the `rapidocr_onnxruntime` mypy override and the
`tests/equity_os/interface/commands/publication` pythonpath entry (its only file is deleted), then
run `uv lock`. Edit each README line that names a deleted path or describes deleted behaviour:
`interface/README.md` (the goal runner and comparatives), `interface/entry/README.md:3` (wave
selection), `interface/workflows/README.md` (goal runner, report building, comparatives),
`interface/commands/verification/README.md` (`validate`), `interface/commands/publication/README.md`
(`report`, `thesis`, `adjudicate`), `extraction/results_pdf/README.md` (the OCR recovery lane),
`sourcing/exchange/README.md:3` (BSE results and PDFs, the comparator file cache),
`sourcing/vendors/screener/README.md:3` (the older derived quarterly P&L adapter),
`sourcing/transport/README.md` (keeps `sec_source.py`, drops `exchange/bse_source.py`,
`exchange/bse_pdf_source.py` and `vendors/screener/screener_source.py`), `analysis/README.md` (the
multi-model thesis layer).

Removal selectors (Evidence procedure, `legacy-1`): the 15 deleted test files as `file::`; in
`test_bse_pdf.py` the 12 functions above as `file::function`; in `test_cli.py` the 10 functions above
as `file::function`. Measured: 277 ids (254 in whole files, 12 + 11 in edited files at `4dec81c4`).

Verification:
1. Lint, format and mypy as in Task 1, plus `uv lock --check`, all exit 0.
2. `git grep -nE 'equity_os\.[a-z_.]*\b(goal_runner|validate_cli|report_cli|report_builder|comparatives|comparator_cache|bse_source|bse_pdf_source|screener_source|ocr_engine|pdf_ocr_recovery|thesis_cli|adjudication_cli|wave_selection|thesis_models\.(adapters|adjudication|codex_client|contracts|draft_parser|pipeline|prompt|render|verifier))\b|from equity_os\.analysis\.thesis_models import|rapidocr' -- equity_os scripts ':!scripts/restructure/' config pyproject.toml 'tests/equity_os/**.py'` prints only `moved_support.py` lines. Module names are matched only as dotted `equity_os.` paths, so live names such as `trusted_report_cli_composition` do not match.
3. ``git grep -nEi 'goal.runner|validate_cli|report_cli|report_builder|comparatives|comparator|bse_source|bse_pdf|screener_source|ocr|thesis_cli|adjudicat|wave selection|multi-model|derived quarterly|results and PDFs|`(validate|report|thesis)`' -- 'equity_os/**README.md'`` prints nothing (at `4dec81c4` every hit is in a README this task edits), and `git grep -n 'validate --watchlist' -- config` prints nothing.
4. The Task 1 parser check, with `'validate'`, `'report'`, `'thesis'` and `'adjudicate'` absent.
5. `uv run python -c "import sys, equity_os.publication.narration.narrate; assert not any(m.startswith('equity_os.analysis.thesis_models.') and m.rsplit('.',1)[1] not in {'client','settings','claude_client','subprocess_runner'} for m in sys.modules)"` exits 0.
6. Scoped tests: `T=$( { printf '%s\n' tests/equity_os/extraction/results_pdf/test_bse_pdf.py tests/equity_os/interface/entry/test_cli.py tests/equity_os/extraction/xbrl/test_phase05_run_comparatives.py tests/equity_os/companies/onboarding/test_retention_classes.py; git grep -lE 'run_comparatives|equity_os\.interface\.workflows\.pipeline|equity_os\.analysis\.thesis_models|narrate|ledger_cli|equity_os\.interface\.entry\.cli\b|equity_os\.interface\.entry import cli|cli_parser|pdf_number_parser|screener_session\b|from test_retention_classes|watchlist\.yaml' -- 'tests/equity_os/**.py'; } | sort -u ); test -n "$T" && PYTEST_DEBUG_TEMPROOT="${XDG_CACHE_HOME:-$HOME/.cache}/equity-os/pytest-tmp" uv run pytest -n 8 $T` passes.

Dependencies: The Evidence procedure's Base for `legacy-1`, taken in the window (Timing).

Risks: Characterization comes first: `test_phase05_run_comparatives.py` and `test_pipeline_e2e.py`
already pin the run's comparatives. They must pass unchanged apart from the one import line.
eqos-bnx slice 3 ("wiring the judgment-only drafter") is RESEARCH-3 narrate; its plan modifies only
`settings.py` and `claude_client.py` (`RESEARCH-3-S3-ledger-narrate.md:305`), and both stay.

## Task 3: Retire `news`

Goal: `eqos` no longer offers `news`, and no news module remains.

Files:
- Delete: the Task 3 product files (including both `news/` packages with their READMEs) and the 2
  test files in the file map.
- Modify: `interface/entry/cli.py` (import `67`, dispatch `636-638`), `interface/entry/cli_parser.py`
  (import `25`, call `225`), `pyproject.toml`, `uv.lock`, and the READMEs of `sourcing/`,
  `extraction/`, `storage/records/`, `contracts/sourcing/`, `interface/commands/sourcing/` and
  `sourcing/transport/` (`news/news_et.py`).
- Test: none added.

Interfaces:
- Consumes: none.
- Produces: none.

Approach: Delete the files and remove the wiring. Drop the `tests/equity_os/extraction/news` and
`tests/equity_os/sourcing/news` pythonpath entries (both folders are now empty) and run `uv lock`.
Edit the README lines that describe news feeds, news events, the news JSONL store and news
provenance. Leave the watchlist `news_aliases` field, the `news-store` entry in
`config/sourcing/sources.yaml` and the catalog untouched: they are config schema and registered ids.

Removal selectors (Evidence procedure, `legacy-1`): `tests/equity_os/sourcing/news/test_news.py::`
and `tests/equity_os/extraction/news/test_news_filing_dedup.py::`. Measured: 64 ids.

Verification:
1. Lint, format and mypy as in Task 1, plus `uv lock --check`, all exit 0.
2. `git grep -nE 'equity_os\.[a-z_.]*\b(news_cli|news_store|news_bse|news_et|news_nse|news_common)\b|equity_os\.(contracts\.sourcing|extraction|sourcing)\.news\b|NewsObservationStore|tests/equity_os/(extraction|sourcing)/news' -- equity_os scripts ':!scripts/restructure/' config pyproject.toml 'tests/equity_os/**.py'` prints only `moved_support.py` lines.
3. `git grep -nEi 'news' -- 'equity_os/**README.md'` prints nothing.
4. The parser check, with `'news'` absent.
5. Scoped tests: `T=$( git grep -lE 'watchlist_config|source_catalog|equity_os\.interface\.entry\.cli\b|equity_os\.interface\.entry import cli|cli_parser' -- 'tests/equity_os/**.py' | sort -u ); test -n "$T" && PYTEST_DEBUG_TEMPROOT="${XDG_CACHE_HOME:-$HOME/.cache}/equity-os/pytest-tmp" uv run pytest -n 8 $T` passes.

Dependencies: Task 2, because both edit `cli.py`, `cli_parser.py` and `pyproject.toml`.

Risks: none beyond the shared files.

## Task 4: Retire the Tijori commands, `screener-page`, `screener-company` and `screener-watchlist-corroborate`

Goal: `eqos` no longer offers `tijori-tables`, `tijori-shareholding`, `tijori-overview`,
`tijori-analysis`, `tijori-events`, `screener-page`, `screener-company` or
`screener-watchlist-corroborate`. `screener-financials`, `screener-watchlist`, vendor surface
capture, the retained-Tijori seal and parse seam, and every importer of `EXIT_OK` / `EXIT_REFUSED`
behave as before.

Files:
- Delete: the 9 Task 4 product modules and the 10 Task 4 test files in the file map.
- Modify: `interface/commands/sourcing/screener_cli_dispatch.py`,
  `interface/commands/sourcing/screener_page_cli.py`, `interface/entry/cli.py` (Tijori import `82`
  and dispatch `552-556`; corroborate import `87-89` and dispatch `585-587`),
  `interface/entry/cli_parser.py` (imports `26`, `30`, `35-41` and `48-50`; calls `227-232`, `234`
  and `236`), `sourcing/vendors/screener/screener_company_parts.py`,
  `sourcing/vendors/screener/screener_watchlist_models.py`, `test_vendor_command_refusals.py`,
  `test_screener_company_hardening.py`, `test_phase3_tijori_retention.py`, and
  `interface/commands/sourcing/README.md` (no Tijori command remains there).
- Create: `tests/equity_os/interface/commands/sourcing/test_screener_topology.py`, only if
  `test_screener_session_cli.py` holds topology tests at the base.
- Test: `test_screener_financials_cli.py`, `test_screener_watchlist_cli.py`,
  `test_screener_financials_nested.py`, `test_phase3_cli.py` (its exit-code parity test imports
  `screener_cli_dispatch`), the retained `test_phase3_tijori_retention.py` tests and the
  vendor-surface tests, all unchanged apart from the edits below.

Interfaces:
- Consumes: none.
- Produces:
  - `screener_cli_dispatch` keeps `dispatch_screener_command`, now only for `screener-financials`
    and `screener-watchlist`, and `EXIT_OK`, `EXIT_REFUSED` and `EXIT_BASIS_UNAVAILABLE`, unchanged.
  - `screener_page_cli` keeps `basis_topology(stock: StockConfig) -> BasisTopology` and
    `watchlist_topology(config_root, symbol) -> BasisTopology | None`.

Approach: First, if `test_screener_session_cli.py` holds any test of `basis_topology` or
`watchlist_topology`, move it verbatim into `test_screener_topology.py` (new ids go in `moved.ids`;
the old ids are already in the manifest).

In `screener_cli_dispatch.py`, drop the `screener_company_cli` and `screener_page_cli` imports,
`_run_company`, `_report_company`, the company and page entries of `SCREENER_COMMANDS`, and the page
tail of `dispatch_screener_command`. A command that is neither financials nor watchlist then never
reaches it, because `SCREENER_COMMANDS` gates entry. Drop any `_*_LINE` constant left unused, and the
docstring's "Mirrors `tijori_cli_dispatch`" clause. In `screener_page_cli.py`, delete everything
except `basis_topology`, `watchlist_topology` and their imports. Rewrite the docstring to "The
configured Screener basis topology of a watchlist stock".

In `test_vendor_command_refusals.py`, keep only the two `screener-financials` `_CASES` rows (the
`not verified` and `refusing to overwrite` cases). Delete
`test_the_market_wide_events_run_refuses_without_a_cookie` and the `screener_page_cli`,
`screener_company_cli` and Tijori references.

In `test_screener_company_hardening.py`, delete
`test_a_redirected_sub_document_fails_its_part_and_the_run_continues`,
`test_a_symlinked_documents_directory_is_refused`,
`test_a_duplicated_page_table_column_fails_only_its_own_part`, the `screener_company_cli` import and
`_argv`.

In `test_phase3_tijori_retention.py`, delete `_run_cli`, `_cli_failure_line` and
`test_cli_writes_json_and_capture_and_exit_codes`. Keep `test_parse_failure_keeps_committed_capture`
and its assertions through `:381` (OK capture, exact retained body, no tables, the financials-island
parse error). Remove its CLI tail (`:383-387`) and its `capsys` parameter, and rewrite its docstring
to "A page the parser cannot read is still retained, with the parse error recorded. The bytes are
kept so a parser gap is fixed and replayed, never re-fetched." Drop imports this leaves unused
(`main`). In the module docstring, replace the `tijori-tables` sentence (`:7-9`) with one that states
what is protected without naming the retired command.

Prose: in `screener_company_parts.py:286-288` reword to "Parsed here rather than taken from a Slice 1
artifact, so it needs no `screener-financials` output for this stock."; in
`screener_watchlist_models.py:289-291` put the `screener-watchlist-corroborate` sentence in the past
tense ("the retired `screener-watchlist-corroborate` resolved them …"). In
`interface/commands/sourcing/README.md:3` drop "Tijori" from the command list.

Removal selectors (Evidence procedure, `legacy-1`): the 10 deleted test files as `file::`;
`test_vendor_command_refusals.py::test_the_market_wide_events_run_refuses_without_a_cookie` and the
20 removed `test_a_vendor_command_refuses_before_its_first_request[...]` ids, written in full (every
id of that function except `[screener-financials-screener_company_id--False-not verified]` and
`[screener-financials--screener_financials_meta.json-False-refusing to overwrite]`); the three
hardening functions as `file::function`;
`test_phase3_tijori_retention.py::test_cli_writes_json_and_capture_and_exit_codes`. Measured: 133 ids
(108 + 21 + 3 + 1).

Verification:
1. Lint, format and mypy as in Task 1, all exit 0.
2. `git grep -nE 'equity_os\.[a-z_.]*\b(tijori_cli_dispatch|tijori_(tables|shareholding|overview|analysis|events)_cli|screener_company_cli|screener_watchlist_corroborate(_cli)?)\b|tijori_cli_support' -- equity_os scripts ':!scripts/restructure/' config 'tests/equity_os/**.py'` prints only `moved_support.py` lines.
3. `git grep -nE '"(tijori-(tables|shareholding|overview|analysis|events)|screener-page|screener-company|screener-watchlist-corroborate)"' -- equity_os 'tests/equity_os/**.py'` prints nothing: no exact command string remains as an invocation, registry entry or constant. Strings that only contain such a word (reviewed residuals) do not match. `git grep -nE 'tijori-(tables|shareholding|overview|analysis|events)\b|screener-page|screener-company|corroborate' -- 'equity_os/**README.md'` prints nothing. The live vendor READMEs (`equity_os/extraction/vendors/README.md`, `equity_os/sourcing/vendors/README.md`) stay as they are; the acquisition-command README line this task edits is reviewed by reading it, not by this grep.
4. The parser check, with the eight commands absent and `'screener-financials'` and `'screener-watchlist'` present.
5. Scoped tests: `T=$( { printf '%s\n' tests/equity_os/interface/commands/sourcing/test_vendor_command_refusals.py tests/equity_os/extraction/vendors/screener/test_screener_company_hardening.py tests/equity_os/sourcing/vendors/tijori/test_phase3_tijori_retention.py; ls tests/equity_os/interface/commands/sourcing/test_screener_topology.py 2>/dev/null; git grep -lE 'screener_cli_dispatch|screener_page_cli|screener_financials|screener_watchlist|screener_company|tijori_retention|tijori_capture|vendor_surface|entity_map|three_source|upstox_crosscheck|equity_os\.interface\.entry\.cli\b|equity_os\.interface\.entry import cli|cli_parser' -- 'tests/equity_os/**.py'; } | sort -u ); test -n "$T" && PYTEST_DEBUG_TEMPROOT="${XDG_CACHE_HOME:-$HOME/.cache}/equity-os/pytest-tmp" uv run pytest -n 8 $T` passes.

Dependencies: Task 3, because of `cli.py`.

Risks: `screener_company.py` and `tijori_retention.py` stay as test seams (follow-up bead).

## Task 5: Closing verification for Tasks 2–4

Goal: The full suite is green on the final revision of Tasks 2–4, the removed node ids are exactly
the frozen manifest, and no retained test lost its outcome.

Files:
- Create: the Close files under `scratchpad/legacy-1/legacy-1/` (not committed).
- Test: the full suite, through the gate.

Interfaces:
- Consumes: Tasks 2–4; `scratchpad/legacy-1/legacy-1/{base-rev.txt,before.ids,manifest.ids,moved.ids,skips.txt}`
  and `scratchpad/gate/legacy-1-baseline.json` from the Base.
- Produces: the accepted deletion-exception record for `legacy-1`.

Approach: Run the Evidence procedure's Close for `legacy-1`. Sensitivity (Task 1) stays intact and
is not part of this slice.

Verification: Close steps 1–5 all hold: collection exits 0 with the id count check; both `diff`s
exit 0 (474 ids removed at `4dec81c4` counts, plus only reconciled ids; added ids equal `moved.ids`);
the gate shows `baseline OK`, `gate OK`, `skips OK`, `rails OK` and `test-set FAIL` only, with
`ROUTE: CONTRACT  a refactor changed the test set`; the drift's `-` lines equal the manifest's
base-passed ids.

Dependencies: Tasks 2–4.

Risks: A removed id outside the manifest means a test was lost by accident. It is restored before
completion, never added to the manifest after the freeze.

## Follow-up beads (for the orchestrator to file)

- Repoint the Screener and Tijori parser tests away from `screener_company.read_company` and
  `tijori_retention` to the live surface boundaries, then delete those two seams.
- Move `EXIT_OK` / `EXIT_REFUSED`, `basis_topology` and `watchlist_topology` out of `*_cli` modules.
- Remove function-level dead code left in LIVE modules (`gold_file`, `diagnostics/report`,
  `watchlist_config.news_aliases`/`wave`).
- Close eqos-4ff (`goal_runner.py` split) and eqos-msq.6 (`bse_pdf_source.py` document rules), which
  Task 2 makes obsolete.
- Dashboard (orchestrator): drop the `sourcing/news` and `extraction/news` rows in
  `scripts/render_dashboard.py` `STATUS` together with their `LAYOUT` blocks (`box()` indexes both,
  so dropping only the rows raises `KeyError`). Refresh the goal-runner and OCR descriptions too,
  then render to check.
- Reword the lineage prose in `screener_financials_cli.py`: "the two commands write into the same
  tree" goes stale once `screener-page` is retired. State the inherited refusal, no-clobber and
  publishing contract directly.

## Rulings (orchestrator, 2026-11-07, on plan review round 1)

- Timing: retirement runs after the five-company test's final live window and evidence capture, and
  never delays it. FIVE-1 Task 4 updates its tests normally; no FIVE-1 amendment.
- Lane 3: Task 1 is parked until eqos-ya6 is resolved and confirms its sweep replay no longer needs
  the harness. The SQLite store, its rollback and default config stay. `screener-financials` and
  `screener-watchlist` stay.
- Gate: the existing gate on the final revision, with one exception for the test-set component, plus
  the exact removal-manifest check. Rails OK, no STOP, no other unexplained CONTRACT.
- Skips: a reduced `VERIFY_BASELINE_SKIPS` computed from the baseline, with outcome comparison
  through the gate's test-set drift.

## Self-review

- Spec coverage: every brief requirement maps to a section. File map, task order and per-task
  verification are above. Non-goals are in "Out of scope". LIVE/SHARED recommendations are in "Kept
  on purpose". Pin and migration conflicts are in Constraints (none found). In-flight work and timing
  are in "Timing". Docs are in the file map, the README greps and "Not changed". Sizes are in "Size win".
- Placeholder scan: no TBD/TODO. Every deleted function and parametrization is named.
- Names: `run_comparatives.REASON_SELECTION_FAILED` is produced in Task 2 and consumed by
  `test_phase05_run_comparatives.py`. `MutationClass` (Task 1), `basis_topology` and
  `watchlist_topology` (Task 4) keep their names. Evidence file names are defined once in the
  Evidence procedure and consumed by Tasks 1 and 5.
- Gaps named: the gate exception, the `adapters.py` → `goal_runner` type import (why Task 2 is one
  task), moved topology tests, reconciliation of other plans' test changes, the research-4 replay
  conflict, the test seams, the dashboard rows and the beads made obsolete.
