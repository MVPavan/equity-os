# RESTRUCTURE-1: reorganise source, config and tests into buckets

**Status:** drafted, awaiting Sol. **Bead:** `eqos-foec`. **Plan:** `docs/plans/RESTRUCTURE-1.md`.
**Date:** 2026-11-05.

Owner decisions are not reopened here (bucket list, command names, config mirror, README per
folder, source list, permission to change hashes and frozen files for this move). This spec
settles how the move works and keeps the live database working. Statements are marked
**verified** (read or run on 2026-11-05 at `6a8fb9aa`), **inferred**, or **not established**.

## 1. Decision on pins

**Keep every stored pin. Add one table of five rows to `run_config.py`, mapping the digest of the
moved files to the digest already stored. Keep the extractor versions.**

```
digest = sha256(version, each file's path and bytes)      # unchanged
return MOVED_PINS.get(digest, digest)                     # new, one line
```

A digest includes the version string and every file's bytes, so a row matches only the exact
moved bytes at that one version. Editing a pinned file gives a digest with no row, which raises
`VersionContentDriftError` as it does today. Bumping a version does the same, and its old row can
then be deleted. This is the smallest option that leaves every stored value valid.

### What reads a source pin (verified)

| Path | Computes the source hash? | Compared with |
|---|---|---|
| `compare replay` / `replay_run` / `db restore --replay-runs` | No: `replay_inputs` passes the manifest's extractor and vendor pins in | itself |
| `ledger check`, submit, panel, decide | No: nothing under `ledger/`, `output/` or `memory/` imports `run_config`; the sealed digest is a SQL function over version, section and claim rows | n/a |
| `compare run` (`execute_run` → `pin_config`) | Yes | `eqos.version_pins`; the run identity also includes the pins |
| First-party, shareholding and vendor ingest | Yes | `eqos.version_pins` |
| Draft from a run (`api/cli.py`, `require_pins`) | Yes | the run's stored manifest |

So a move without a bridge leaves replay and check intact, and refuses new runs, ingest and drafts.

### Options

| | New extractor versions | Rewrite pins to new hashes | Frozen copies at legacy paths | **`MOVED_PINS` (chosen)** |
|---|---|---|---|---|
| Approved reports, sealed digests | Unchanged | Unchanged | Unchanged | Unchanged |
| `ledger check`, replay | Unchanged | Unchanged, but manifests disagree with the table | Unchanged | Unchanged |
| New runs and drafts | **Break until all retained sources are re-extracted:** selection filters on `extractor_version` (`selection.py`, `resolve_loader.py`, `engine.py`), and drafts refuse older runs | Run identity changes; drafts refuse older manifests | Work, but 15,905 lines stay in the tree as a second copy | Work; same run identity |
| Database | New rows and re-extraction, against "extract once" | **Blocked:** `version_pins` rejects update and delete by trigger; `runs.manifest` is also immutable | None | None |
| Frozen manifests | Name old versions as evidence; must be reconciled | Unaffected | Unaffected | Unaffected |
| Code | Constant bumps, plus a re-extraction campaign | A new migration | Two trees or an import hook | 1 line, 5 rows |

### Live pins (verified read-only)

`version_pins` holds 14 rows, 5 of them extractor pins: `extractor_pdf pdf-occurrences/4`,
`extractor_xbrl xbrl-occurrences/3`, `vendor_extractor:screener-subscriber screener-v1`,
`vendor_extractor:tijori tijori-v4`, `vendor_extractor:upstox upstox-v2`. **All five equal the
digest recomputed from `main`'s bytes.** These are the table's five rows.

The current shareholding versions (`nse-shp-v4` and the three vendor `*-shp-*`) are **not** in
live, so they need no row and take the moved hash on first use.

### Other hashes

- **`parser_sha256` (235 live rows): not affected.** It hashes `inspect.getsource` of one function.
  Verified for the 78 entries of the static `PARSERS` registry: no function text names the package,
  75 equal their live row and 3 are not yet in live. The functions in those modules that import
  inside their bodies are not parsers (`register_tables`, `reparse`, `capture_company` and others).
  Table parsers, gates, `extract_text` and canary markers are **inferred** by the same reasoning;
  Task 3 records every computed digest before and after and requires them equal.
- **Config pins: by content, not path (verified).** Dictionary and mapping digests hash file base
  names and bytes; rounding, policy, definition and alignment hash bytes. Moving a directory whole
  changes none of them. **The move edits no config byte.** Stale comments inside config files stay,
  because several of those files are hashed.
- **`ACCEPTED_CONFIGS`** (`operator_cli.py`) keys four config paths to their bytes. Keys change,
  hashes do not.
- **Stored paths (verified by a read-only sweep of every text and JSON column in `eqos`):** no
  `src/fundamentals` or `tests/fundamentals` anywhere. `config/` appears only in three sealed prose
  fields, and the command name in two more, which no code resolves (inferred from reading the
  fragments). They stay as written. The word also appears in vendor text, as ordinary English.
- **Migrations and frozen manifests:** unchanged. No committed migration needs editing.

## 2. Layout

The list in `eqos-foec` governs. `equity_os/` replaces `src/fundamentals/`; commands become `eqos`
and `eqos-operator`; `migrations/` stays.

**The count does not reconcile:** the owner's list has 65 leaf folders, or 53 when `vendors`,
`lenses` and `commands` count as one each; neither is 56. The list is followed, and `rule.py`
checks against it.

**Tests** mirror at `tests/equity_os/<bucket>/<sub>/` rather than `tests/<bucket>/`, because
`tests/phase_0a` and `tests/equity_os_blueprint` stay outside the gate's scope and
`scripts/verify.sh` needs one test root. Those two folders do not move: they test `scripts/` and
import no product code.

**Fixtures stay at `tests/fundamentals/fixtures/`, whole.** Moving them cannot work without
changing a frozen manifest:

- Manifests name these paths inside a hash chain (each records the path and hash of the next).
- `stage4_support.py` reads `stage4_freeze.yaml` at historical commits by path.
- `config/retention/holds.yaml` lists them and is not edited.

Leaving them also means no script ever touches the restricted files or the `stage4` screen export.
The folder name is a wart, recorded as open question 2.

Shared test modules go to `tests/equity_os/support/` (on `pythonpath`), so `from x_support import`
lines stay byte-identical. `conftest.py` goes to `tests/equity_os/`.

**Old `__init__.py` files (20):** only `thesis/__init__.py` keeps content, moving to
`analysis/thesis_models/__init__.py`, because 62 imports use its names. The other 19 are
docstring-only or re-export names nobody imports, except 13 uses of `contracts`, which the rewriter
resolves to their defining modules. Their docstrings go to READMEs. New packages get a one-line
`__init__.py`.

**Config:** per the `CONFIG` rules in `rule.py`. Constants such as `DICTIONARY_DIR` gain the bucket
prefix, so `config_root` still means `config/`.

## 3. Move map

`rule.py` is an ordered regex table, generated from module names and docstrings, and writes
`moves.tsv` (kind, old, new, flag).

Checked at `6a8fb9aa` plus `research-4` at `45d315f9`: all 338 modules and 20 `__init__.py` on
`main`, 6 replay-only modules, 87 config files and 339 test modules assigned exactly once, with no
destination collisions and no target outside the list. `sourcing/online` and `storage/search` are
empty by design (README only).

The rule and map are drafted under `scratchpad/restructure/`. Plan Task 1 commits them to
`scripts/restructure/`, **because replay on `research-4` needs them**; they are deleted after that
replay.

A map row flagged `judgement` marks a placement a reviewer may reasonably change. Changing one
means editing `rule.py` and regenerating. 60 modules, 4 config files and 61 tests are flagged; test
placement is mechanical (the plurality of imported sub-buckets) and low stakes. The module
judgements that matter are in section 9.

## 4. Move script

`scripts/restructure/move.py`: one command from a clean tree to a moved tree, with no hand steps
outside its data files. It is throwaway and deleted once `research-4` has been replayed.

- **Works only from explicit lists** (`moves.tsv`, plus a named list of scripts). It never walks a
  tree and never opens `stage4_holdout.yaml`, `stage4_manifest.yaml`, `data/holdout/` or
  `data/raw/onboarding/`; it refuses a list naming them. It never reads `data/` at all.
- **Imports:** rewrites through the map using AST positions. All four forms exist in product,
  script and test code: from-module (10,534 names), from-package-import-submodule (273), `import x.y`
  (48), re-exported symbol (75). A `from` whose names now live in different packages is split.
- **Pinned files:** imports only, nothing else.
- **Other strings:** rewrites a dotted name only when it names a mapped module (with an attribute
  suffix allowed), and `src/fundamentals/...` paths through the map. A name of an old *package* with
  no row fails the run until `edits.tsv` handles it, so every guard test naming a package gets a
  deliberate decision.
- **Left alone (not modules):** `RUN_AUTHOR`, the `fundamentals-narrate:` author prefix (both go
  into sealed rows), logger names, temp prefixes, `AUTHORIZATION`, and `config/fundamentals.yaml`.
- **`Path(__file__)` depth:** recomputes `parents[n]` so each of the 21 source and the test uses
  reach the same directory; `parent / "fixtures"` becomes the repo-rooted fixture path.
- **`edits.tsv`:** the deliberate edits, as exact path, old text and new text. Each must match its
  stated number of times or the run fails. This is what makes the result replayable and reviewable.
- **Then:** `ruff --select I --fix` and `ruff format` on changed Python only, `pyproject.toml`,
  `uv lock`, and a generated `MOVED_PINS`.

**Proof the move is logic-free**, run by the script:

- For every module, the AST with imports removed equals the old one, once string constants naming
  the package are masked. Rows in `edits.tsv` are the only listed exceptions.
- For the 40 pinned files, no masking is allowed.
- The legacy digests are computed from the old bytes before moving, and must equal the live rows
  recorded in Task 3.

### Known deliberate edits

- `run_config.py`: source lists, `_SOURCE_ROOT`, directory constants, `MOVED_PINS`.
- `operator_cli.py`: `ACCEPTED_CONFIGS` keys, usage and `prog`. `coverage_cli.py`: `_OWN_MODULES`.
  `onboard_cli.py`: the printed `fundamentals compare run`.
- `pyproject.toml`: scripts, wheel, ruff `src`, mypy path, pytest `pythonpath`, distribution name
  to `equity-os`. `scripts/verify.sh`: `SRC_SCOPE`, `TEST_SCOPE`, `COV_SCOPE`. `scripts/verify_project.sh`,
  `scripts/stage2_recreation_check.sh`, `scripts/vendor_surface_bakeoff.py`.
- `stage4_support.py`: add `equity_os` to `IMPL`, `LEAK_ROOTS` and `SELECTION_ROOTS`, **keeping**
  `src`; `DISCOVERY` stays the old path because it is read from history. Adding the root matters:
  without it the leak scan would silently stop covering product code.
- `test_frozen_manifests.py`: `E2E` paths, and `--follow` in `test_approved_payload_preceded_its_e2e`.
  Without `--follow` the e2e's "first commit" becomes the move commit, and the test passes while
  proving less.
- **Frozen-manifest `config/` sources:** manifests stay frozen; readers resolve recorded paths
  through one test helper, `recorded_path(repo, path)`, which returns the recorded path if it exists
  and otherwise applies the `config/` prefix map. Sites: `test_frozen_manifests.py`,
  `manifest_support.py` (`Selection`, which the opaque stage 4 check also uses),
  `stage3_data_support.py`, `pilot_manifest_check.py`.
- **Guards that scan a package:** `test_coverage_batch.py` (`screens.__file__.parent`),
  `test_upstox_scope_guards.py`, `test_phase3_map.py`, `test_memory_store.py`. Each is pointed at the
  same set of modules it scans today. A package split must not narrow a guard.
- `test_derived_settings.py`: seed bytes are read at the old paths, and `SEED_PINS` is recomputed.
  It pins two historical versions over moved path strings; the seed bytes it hashes do not change.

Expect more once the tree runs. They are found by the gate and added to `edits.tsv`.

## 5. Sequence: one atomic scripted change

The plan skill's default for a wide refactor is expand, migrate in batches, contract. **No green
split exists here**, so this is its named exception, one atomic commit group on an integration
branch:

- Expanding would need a `fundamentals` alias for 358 modules, and batches would hold two import
  roots at once, including across cycles between old packages.
- A pinned file's bytes can change only once per table of digests, so batches would mean several
  tables or none.
- Each batch would need its own 50-minute gate.
- Replay on `research-4` needs one reproducible function of a tree, not a chain of states.

The daily intake is paused, so nothing needs to run during the move. Green is promised at the end
of the branch, and the branch lands only after both the gate and the rehearsal pass on it. Nothing
is half-moved on `main` at any point.

## 6. Gate changes (before the move, on `main`)

`scripts/verify.sh` would misfire on a rename in three ways, all **verified by reading it**:

1. `git diff -U0 base -- newpath` reports a moved file as wholly added, so the fixture rails scan
   old test content as new. These are STOP rails, which must never be worked around. **Fix:** derive
   added lines from one `git diff -U0 -M` over the tree, so a rename contributes only its changed
   lines.
2. `over-800-lines` fails on any changed `.py` above 800. 3 source and 14 test modules already are,
   and a few at 796–799 may wrap past it. Those breaches are separate work. **Fix:** a size list
   read by the check, `scripts/restructure/oversize.txt`, generated by the move, deleted with the
   script, and followed by a bead.
3. The refactor test set compares node ids, which contain paths. **Fix, without touching the gate:**
   the script translates `<slice>-baseline.json` through the map, so the same tests must come back
   green under their new paths.

## 7. Import rule, source list, READMEs (after the move)

**Import rule.** Order, low to high: contracts, storage, coverage, companies, sourcing, extraction,
normalisation, verification, analysis, publication, interface. A module imports its own bucket or
lower. Today's exceptions go in `tests/equity_os/support/allowed_backward_imports.txt`. A test
parses the tree, fails on any pair not listed, and allows the list to shrink. Under this map and
order there are **211** backward edges against the brief's 187. Both are counts of today's code
under some placement; the difference has not been traced and does not change the rule. The move
preserves them.

**Source list.** `config/sourcing/sources.yaml`, plus one file per vendor, states every source and
its surfaces. It is read only by a test, so this is no logic edit:
`tests/equity_os/contracts/sourcing/test_source_list.py` fails unless the list equals the union of
`source_catalog.py`'s catalog, `surfaces.yaml` and the Upstox route registry, in both directions.
Code keeps its current sources of truth; making vendors drive the code is later work.

**READMEs:** 80 in `equity_os/` (11 buckets, 65 leaves, and the 4 `vendors`, `vendors`, `lenses`,
`commands` parents): what it handles, what it does not, what it reads and writes. Prose only, in
commits after the move. The stage 4 leak scan covers them.

**Docs.** Update living docs only (`.claude/project/*`, `.codex/project/*`, `AGENTS.md`,
`CLAUDE.md`, `docs/backend-roadmap.md`). Historical specs, plans and evidence keep their old paths,
and `docs-index.md` states where the map is.

**Scheduled prompt.** One task exists and is disabled (the daily document intake); its text is
updated and it stays disabled.

## 8. Replay on `research-4` (designed, not done)

`research-4` touches none of the 40 pinned files (verified), so its `MOVED_PINS` come out equal.
Procedure after `main` has moved: merge the pre-move tip of `main` into `research-4`, run the same
script, then merge the moved `main`. The two moved trees then differ only by `research-4`'s own
work. Migration `0046` is unaffected. The map already covers its 6 new modules and 9 new test files,
and Task 1 proves the map and edit list apply to it without writing anything.

## 9. Judgement calls worth review

| Placement | Why it could go elsewhere |
|---|---|
| `evidence/vendor_ingest`, `vendor_shareholding` → `extraction/surfaces` | No shared vendor folder exists; both span vendors |
| `evidence/selection`, `reconcile/agreement`, `fact_view`, `verify/comparison_key`, `cross_check`, `crossfoot` → `verification/comparison` | `selection` is close to admission; `crossfoot` is used by a pinned adapter |
| `evidence/alignment`, `capture_interpretation` → `normalisation/mapping` | Could be verification or extraction |
| `ledger/store` → `storage/records`; `ledger/run_traces` → `analysis/calculations` | Could be publication; both import upward |
| `ledger/importer`, `import_mapping` → `publication/revision`; `output/*`, `ledger/display` → `publication/drafting` | Import is history rather than revision; display or render could be export |
| `ingest/{screener,upstox}_crosscheck`, `screener_watchlist_{crosscheck,corroborate}` → `verification/diagnostics` | They read vendor bytes too |
| `ingest/tijori_overview`, `screener_watchlist_models`, `upstox_instruments`, `upstox_candle_retention` → `sourcing/vendors/*` | Mixed fetch and reading |
| `ingest/screen_export`, `tijori_screen_fetch`, `api/watchlist_config`, `wave_selection` → `coverage/*` | They perform fetches, or are composition config |
| `api/coverage_cli` → `commands/sourcing`; `thesis_cli`, `adjudication_cli` → `commands/publication` | The list has no `commands/coverage` or `commands/analysis` |
| `news/store` → `sourcing/news`, not `storage/records` | Same basename as `ledger/store`; the move renames nothing |
| `pg/approvals` → `storage/database`; `pg/legacy_import`, `cutover` → `storage/facts`; `pg/identity_seed` → `companies/identity` | Could all be `storage/database` |
| `reconcile/report` → `verification/diagnostics` | It is a contract, but it imports upward, and `contracts/` must import nothing above |
| `contracts/evidence`, `qualification`, `guidance_claim` → `measurement`; `config_versions`, `versioning` → `verification` | `evidence` spans sourcing and measurement |

The full list is `judgement_calls.tsv` beside the map.

## 10. Acceptance

1. Coverage check passes; `rule.py` regenerates `moves.tsv` byte-identically.
2. The script's logic-free proof passes on all modules; the 40 pinned files differ only in imports.
3. `scripts/verify.sh gate` on the moved tree: ruff, `mypy --strict` (fresh cache), and the same
   node ids green as the translated baseline; skips no higher than the baseline.
4. On a restored copy in `eqos_test_*`, using the moved code, compared with the same copy using old
   code: every report version's `ledger check` output and sealed digest, every run's replay output,
   `version_pins`, and all computed parser digests are identical. A new `compare run` for an
   existing request returns the stored run. A draft from an existing run is not refused. One
   version goes through submit and panel. Editing one byte of a pinned file raises drift.
5. After landing: `eqos db check-live` exits 0 and live row counts are unchanged, since the move
   writes nothing to the live database.
6. `fundamentals` and `fundamentals-operator` no longer exist as commands; `eqos` and
   `eqos-operator` do.
7. Import rule and source-list tests pass, and each fails on a seeded violation.
8. A README exists in every bucket and sub-bucket.

## 11. Open questions (none block drafting)

1. **Sub-bucket count:** 56 stated, list gives 65 or 53. Default: follow the list.
2. **`tests/fundamentals/fixtures/` keeps its name.** Renaming needs changing frozen manifests, the
   stage 4 history readers and `holds.yaml`, which the owner reserved for a proven need. Default:
   keep it; a later rename is its own decision.
3. **`tests/equity_os/` instead of `tests/`.** Default: as designed, see section 2.
4. **Distribution name `equity-os`** was not named by the owner. Default: rename, since one
   `uv lock` entry changes and no such package remains.

## 12. Not established

- What the two restricted YAML files contain, by instruction. If they name a moved path that goes
  past `Selection`, the opaque stage 4 test fails and the fix goes through `recorded_path`; they are
  never edited.
- The complete `edits.tsv`, until the tree runs.
- Whether removing eager `__init__` imports exposes an import cycle that today's import order hides.
  Task 2 imports every module alone in a fresh process. A cycle found there is fixed by moving one
  import inline through `edits.tsv`, recorded as a listed exception. In a pinned file that would
  change its bytes but not its logic; none is expected.
- Whether `content_sha256` values inside `ledger_stage1_manifest.yaml` are anything other than
  report content hashes (inferred); the gate would show a dependence.
- Whether Python resolves the root-level `equity_os` differently under hatch's editable install; Task
  2 checks that `eqos` runs from outside the repo root as well as inside it.
