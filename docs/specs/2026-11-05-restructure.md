# RESTRUCTURE-1: reorganise source, config and tests into buckets

**Status:** approved 2026-11-05: approver gpt-6.1-sol, `APPROVE` after one fix round. **Bead:** `eqos-foec`. **Plan:** `docs/plans/RESTRUCTURE-1.md`.
**Date:** 2026-11-05.

Owner decisions are not reopened here (bucket list, command names, config mirror, README per
folder, source list, permission to change hashes and frozen files for this move). This spec
settles how the move works and keeps the live database working. Statements are marked
**verified** (read or run on 2026-11-05 at `6a8fb9aa` or `2430d745`), **inferred**, or **not
established**.

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

The table's weakness is that it accepts the moved bytes as equivalent without judging them. The
moved bytes are therefore what gets proved: section 4 checks them, and the deliberate edits inside
pinned files are listed there one by one.

### What reads a source pin (verified)

| Path | Computes the source hash? | Compared with |
|---|---|---|
| `replay_run` (`db restore --replay-runs`, `compare report` on shareholding runs). No `compare replay` command exists; `compare_cli` has `run`, `report`, `queue` | No: `replay_inputs` passes the manifest's extractor and vendor pins in | stored results (`restore_check.replay`) |
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
  The other hash-producing call sites are `identity_gate` and `topology_gate`
  (`vendor_surface_capture.py:247,265,661`) and `continuation` (`vendor_surface_market.py:382`).
  `continuation` is verified: no package name and no import in its text. The two gates, table
  parsers, `extract_text` and canary markers are **inferred** by the same reasoning. The plan
  records every call site's digest before and after, keyed by its persisted `parser_version`, and
  requires them equal.
- **Config pins: by content, not path (verified).** Dictionary and mapping digests hash file base
  names and bytes; rounding, policy, definition and alignment hash bytes. Moving a directory whole
  changes none of them. **The move edits no config byte.** Stale comments inside config files stay,
  because several of those files are hashed.
- **`ACCEPTED_CONFIGS`** (`operator_cli.py`) keys four config paths to their bytes. Keys change,
  hashes do not.
- **Wire identifiers in sealed captures:** `PAGE_OUTCOME_KIND` and `ACQUISITION_OUTCOME_KIND` are
  built from `__module__`, so a move would change the `native_kind` that new capture records store.
  Sealed `record.json` captures hold the outcome on disk (verified on one record, whose kind was a
  different vendor path); which stored records carry these two strings is not established, since
  `data/` is not searched. No code compares the field, and no live column holds it (below). Both are
  frozen to today's text by explicit edits, listed in section 4. No other code derives a stored value from
  `__module__`; `type(x).__name__` has no module in it.
- **Stored paths (verified by read-only sweeps of all 405 text and JSON columns in `eqos`):** no
  dotted `fundamentals.<package>.<module>` name anywhere (a control pattern on `version_pins` did
  hit, so the sweep works), and no `src/fundamentals` or `tests/fundamentals` anywhere. `config/` appears only in three sealed prose
  fields, and the command name in two more, which no code resolves (inferred from reading the
  fragments). They stay as written. The word also appears in vendor text, as ordinary English.
- **Migrations and frozen manifests:** unchanged. No committed migration needs editing.

## 2. Layout

The list in `eqos-foec` governs. `equity_os/` replaces `src/fundamentals/`; commands become `eqos`
and `eqos-operator`; `migrations/` stays.

**The count does not reconcile:** the owner's list has 65 leaf folders, or 53 when `vendors`,
`lenses` and `commands` count as one each; neither is 56. The list is followed, and `rule.py`
checks against it.

**Composition config stays together.** `api/config.py`, `watchlist_config.py` and
`wave_selection.py` all go to `interface/entry`: `watchlist_config` imports `api/config`, so
splitting them gave a `coverage` to `interface` edge. `coverage/watchlist` therefore holds no
module and is empty by design with a README, like `sourcing/online` and `storage/search`.
`config/coverage/watchlist.yaml` stays where the config rule puts it. Four lower modules still
import `watchlist_config` upward; that is today's dependency, recorded rather than fixed.

**`news/store.py` is persistence:** it goes to `storage/records/news_store.py`. It is the only
renamed module, because `ledger/store.py` has the same basename in that folder.

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

Shared test modules go to `tests/equity_os/support/` (on `pythonpath`), so absolute
`from x_support import` lines stay byte-identical. The modules themselves are not byte-identical:
their product imports and `Path(__file__)` depths change. `conftest.py` goes to `tests/equity_os/`.

**Relative test imports (verified, AST over the mapped test modules):** 9 statements in 5 files,
none in product code. The script resolves each against the old module identity
(`tests/fundamentals/<module>`). Eight name a support module and become absolute imports, including
the two inside `compare_tables_support.py`, which would otherwise have no parent package once
imported absolutely. The ninth is `test_compare_diagnostic` importing `test_compare_corroboration`;
the map keeps the two side by side, so it stays relative and resolves.

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

Checked at `2430d745` plus `research-4` at `45d315f9`: all 338 modules and 20 `__init__.py` on
`main`, 6 replay-only modules, 87 config files and 339 test modules assigned exactly once, with no
destination collisions and no target outside the list. `sourcing/online`, `storage/search` and
`coverage/watchlist` are empty by design (README only), and `rule.py` fails on any other empty leaf.

The rule and map are drafted under `scratchpad/restructure/`. They are committed to
`scripts/restructure/` on `main` once the edit list settles, **because replay on `research-4` needs
them**, and are deleted after that replay.

A map row flagged `judgement` marks a placement a reviewer may reasonably change. Changing one
means editing `rule.py` and regenerating. 60 modules, 4 config files and 62 tests are flagged; test
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
- **Bindings:** every rewritten import must bind the same local name, at the same scope, to the
  mapped target of what it bound before. A relative import resolves against the old module identity
  first. Moving an import into a function is an `edits.tsv` row with a written reason.
- **Pinned files:** imports, plus the listed rows below, nothing else.
- **Other strings:** rewrites a dotted name only when it names a mapped module (with an attribute
  suffix allowed), and `src/fundamentals/...` paths through the map. A name of an old *package* with
  no row fails the run until `edits.tsv` handles it, so every guard test naming a package gets a
  deliberate decision.
- **Left alone (not modules):** `RUN_AUTHOR`, the `fundamentals-narrate:` author prefix (both go
  into sealed rows), logger names, temp prefixes, `AUTHORIZATION`, and the two frozen wire
  identifiers below.
- **Config paths in code:** rewritten through the map, including literals split across `/`
  (`_REPO_ROOT / "config" / "watchlist.yaml"`, used by several command modules), the default path
  in `cli_parser.py`, `run_traces.py`, `risk_probe.py`, `guidance_targets.py`, `db_cli.py`,
  `coverage_cli.py`, `vendor_surface_cli.py`, and `config_root / "watchlist.yaml"` in
  `documents_cli.py`. A path under `config/` in code with no map row fails the run.
- **`Path(__file__)` depth:** recomputes `parents[n]` so each of the 21 source and the test uses
  reach the same directory; `parent / "fixtures"` becomes the repo-rooted fixture path.
- **`edits.tsv`:** the deliberate edits, as exact path, old text and new text. Each must match its
  stated number of times or the run fails. This is what makes the result replayable and reviewable.
- **Then:** `ruff --select I --fix` and `ruff format` on changed Python only, `pyproject.toml`,
  `uv lock`, and a generated `MOVED_PINS`.

**Proof the move is logic-free**, run by the script:

- For every module, the AST with imports removed equals the old one, once string constants naming
  the package are masked. Rows in `edits.tsv` are the only listed exceptions.
- Its imports, mapped, bind the same names at the same scopes as the old ones.
- For the 40 pinned files, no masking is allowed, and the only non-import differences are the rows
  listed below.
- The legacy digests are computed from the old bytes before moving, and must equal the live rows
  recorded before the move.

### Known deliberate edits

- **Inside pinned files, part of the moved bytes the table accepts (listed for review; there are
  exactly two):**
  - `ingest/screener_session_models.py`: `PAGE_OUTCOME_KIND` becomes the literal
    `"fundamentals.ingest.screener_session_models.PageOutcome"`.
  - `ingest/upstox_source.py`: `ACQUISITION_OUTCOME_KIND` becomes the literal
    `"fundamentals.ingest.upstox_source.AcquisitionOutcome"`.
- **Repo root:** `FundamentalsConfig.repo_root` (`api/config.py:581`) and `WatchlistConfig.repo_root`
  (`api/watchlist_config.py:279`) return `parent.parent` of the config file, which from
  `config/<bucket>/x.yaml` would be `config/`. Both become "the parent of the nearest ancestor named
  `config`, or else `parent.parent` as today", which also keeps configs loaded from temporary test
  folders working (inferred; the gate shows it). The plan checks `repo_root` on every mapped config
  file these classes load.
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

The branch holds two commits, built on the pre-move tip `P` (the `main` commit carrying
`scripts/restructure/`): the **move commit**, which only the script writes, and one **overlay
commit** with the READMEs, source list, its test and the living docs. A rebuild re-runs the script
and cherry-picks the overlay, so these are new candidate branches and nothing is rewritten.

**The candidate is committed before any history check.** `test_approved_payload_preceded_its_e2e`
reads commits and fails on an uncommitted tree.

**Where it runs:** script work happens in a disposable worktree with no `data/`, which is enough for
ruff, mypy, importing each module and tests needing no retained data. Everything that needs retained
data runs **in the main checkout**, switched to the candidate branch: `data/`, `.env`, the
`scratchpad/` capture folders the rails scan and the real `.venv` are already there. Nothing is
copied, so no restricted directory is copied or read by this route; a switch does not touch files
equal on both commits, and fixtures do not move. The existing opaque tests open restricted files
only as they do on every gate today. `../equity-os-research-4` was checked (`ls -la` only): it has
`data/holdout` as a symlink and a real `data/raw/onboarding`, because
`.claude/project/learnings.md` records that the stage 4 e2e needs a real directory there. A symlink
therefore cannot replace that directory, and repeating that copy is ruled out. The cost is that the
main checkout is exclusively held during these runs, which the orchestrator arranges; `research-4`
has its own checkout and is unaffected.

## 6. Gate changes (before the move, on `main`)

`scripts/verify.sh` would misfire on a rename, **verified by reading it**. A gate on a tree with
neither variable below set behaves as it does today.

1. **Fixture rails.** `git diff -U0 base -- newpath` reports a moved file as wholly added, so the
   rails scan old test content as new. These are STOP rails, which must never be worked around, and
   generic rename detection would weaken them: a file renamed into `tests/` from elsewhere must get
   the full scan. **Fix:** optional `VERIFY_RENAME_MAP` names the reviewed `moves.tsv`. A destination
   gets changed-lines-only treatment only if all hold: it has a row, old and new are in the same
   protection domain (both under `tests/`, or neither), and `git diff -U0 -M base -- old new` reports
   a rename. Every other case falls to today's full scan: an unmapped rename, a domain-crossing row,
   an untracked destination, a rename below git's similarity threshold.
2. **`over-800-lines`** fails on any changed `.py` above 800. 3 source and 10 test modules on `main`
   already are (the earlier draft's 14 was wrong), and 10 more sit within 10 lines of it. **Fix:**
   optional `VERIFY_OVERSIZE_LIST` names `oversize.tsv` (path, pre-move lines, ceiling). A file above
   800 passes only if listed and at or under its ceiling; a new or grown file fails. Only mapped
   files can be listed. The ceiling is pre-move lines plus an allowance of 15, justified because the
   logic-free proof shows growth is formatting only, and every row is reviewed. The list is deleted
   with the script, and the breaches stay separate work.
3. **Test set.** Node ids contain paths. **Fix, without touching the gate:** `translate_baseline.py`
   writes `<slice>-baseline.json` from the kept original, with its digest recorded. It replaces only
   the exact mapped path before `::`, keeps test names, and applies an enumerated, reviewed list of
   parameter-id changes. It asserts the translation is injective, cardinality is equal, and the
   inverse returns the original. New ids from the overlay's test are an enumerated addition, so the
   same gate command stays the one final route.
4. **Scope.** On a committed candidate, the default scope base `HEAD` would make the diff empty and
   the rails vacuous. Every moved-tree gate sets `VERIFY_SCOPE_BASE=P`, the recorded parent of the
   move commit, with no exceptions. The two variables above are set on the same line.

## 7. Source list, READMEs (on the candidate, before the final gate)

**Import rule: deferred** (Sol's scope cut, followed): no import-order test and no ledger of edges in
this work. A bead holds it, with this order, low to high: contracts, storage, coverage, companies,
sourcing, extraction, normalisation, verification, analysis, publication, interface. Under the map
there are 214 backward edges (211 before the placement changes). The brief's 187 could not be
reproduced: no count tried gives it (top-level imports only 209, unconditional only 205, file to
sub-bucket 125, sub-bucket to module 149), and its derivation is not recorded, so the cause is
**not established**. The move preserves whatever exists.

**Source list.** One file, `config/sourcing/sources.yaml`, maps each source id to its surfaces. No
product code reads it. One test under 30 lines,
`tests/equity_os/contracts/sourcing/test_source_list.py`, fails unless it equals, in both
directions, the union of `BUILTIN_SOURCES.entries`, `VENDOR_SURFACES`, `surfaces.yaml` and Upstox
`ROUTES`. Those shapes are verified to be plain attributes, so it fits; there is no sync framework.
Code keeps its current sources of truth; making vendors drive the code is later work.

**READMEs:** 80 in `equity_os/` (11 buckets, 65 leaves, and the `sourcing/vendors`,
`extraction/vendors`, `lenses` and `commands` parents). One precise sentence per leaf and a short
paragraph per bucket, saying what it handles and what it does not. They are in the overlay commit,
so the final gate and the stage 4 leak scan cover them.

**Docs.** Update living docs only (`.claude/project/*`, `.codex/project/*`, `AGENTS.md`,
`CLAUDE.md`, `docs/backend-roadmap.md`). Historical specs, plans and evidence keep their old paths,
and `docs-index.md` states where the map is.

**Operational helpers and the scheduled prompt come before landing.** `lq.sh` is updated and its
updated text prepared for the prompt of the one disabled scheduled task (the daily document intake)
during the cutover rehearsal. The task stays disabled throughout.

## 8. Replay on `research-4` (designed and rehearsed; the real replay is later)

`research-4` touches none of the 40 pinned files (verified), so its `MOVED_PINS` come out equal.
Procedure after `main` has moved: merge `P` into `research-4`, run the same script, confirm the
moved tree of `P` alone equals `main`'s move commit, record that commit with `git merge -s ours`, then
merge the moved `main`. The two moved trees then differ only by `research-4`'s own work. The `-s ours`
step is needed because a plain merge conflicts in import blocks: both sides rename the same import
lines identically, and `research-4`'s added imports sort next to them (rehearsal, 2026-11-05). Migration `0046` is
unaffected. The map already covers its 6 new modules and 9 new test files.

The whole sequence is rehearsed on disposable branches cut from `45d315f9`, without altering
`research-4`, because that is the state the replay really transforms. A dry check of raw `45d315f9`
would test the wrong tree. Since the merge base, `main` and `research-4` change no path in common
(verified by name, up to `2430d745`), so the first merge is expected clean.

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
| `ingest/screen_export`, `tijori_screen_fetch` → `coverage/screens` | They perform fetches |
| `api/watchlist_config`, `wave_selection` → `interface/entry` | Coverage reads them, and four lower modules import upward; settled by the composition-config ruling |
| `api/coverage_cli` → `commands/sourcing`; `thesis_cli`, `adjudication_cli` → `commands/publication` | The list has no `commands/coverage` or `commands/analysis` |
| `pg/approvals` → `storage/database`; `pg/legacy_import`, `cutover` → `storage/facts`; `pg/identity_seed` → `companies/identity` | Could all be `storage/database` |
| `reconcile/report` → `verification/diagnostics` | It is a contract, but it imports upward, and `contracts/` must import nothing above |
| `contracts/evidence`, `qualification`, `guidance_claim` → `measurement`; `config_versions`, `versioning` → `verification` | `evidence` spans sourcing and measurement |

The full list is `judgement_calls.tsv` beside the map.

## 10. Acceptance

1. Coverage check passes; `rule.py` regenerates `moves.tsv` byte-identically.
2. The script's logic-free proof passes on all modules; the 40 pinned files differ only in imports
   and the two listed rows.
3. `VERIFY_SCOPE_BASE=P ... scripts/verify.sh gate` on the committed candidate: ruff, `mypy --strict`
   (fresh cache), the same node ids green as the translated baseline plus the enumerated additions,
   skips no higher than the baseline, rails clear.
4. **Restored proof.** Two copies restored independently from one backup set, one under old code and
   one under moved code. `db restore --replay-runs` reports no mismatches, and equal expired sets.
   `ledger check` output for every report version matches once the enumerated fields are normalised:
   only the validation id, unless a further field is listed with a reason. Semantic validation rows
   match on claim and version states, sealed digests and `version_pins`, and each side's write delta
   is exactly its new validation rows. Parser digests match per persisted `parser_version`.
5. **New writes on the moved copy, retained or synthetic inputs only:** a first-party ingest and a
   vendor ingest that each add extraction and interpretation rows; a `compare run` that reports a new
   run; a draft from it; a `ledger check`; submit and a recorded `rehearsal` APPROVE bound to that
   version; then check, replay and export of those new records. A `compare run` for an existing
   request returns the stored run. Editing one byte of a pinned file raises drift.
6. **Cutover rehearsed:** on the real venv, an old install upgraded to the renamed distribution has
   `eqos` and `eqos-operator` working inside and outside the repo root, and `fundamentals` and
   `fundamentals-operator` gone. Going back to `P` restores the old commands.
7. `git log --follow` on each moved e2e reaches its recorded introduction commit.
8. Replay rehearsed on disposable branches: the moved trees differ only by `research-4`'s work.
9. After landing: `eqos db check-live` exits 0 and live row counts are unchanged, since the move
   writes nothing to the live database.
10. The source-list test passes and fails on one removed entry, tried once by hand; a README exists
    in every bucket and sub-bucket.

## 11. Open questions (none block drafting)

1. **Sub-bucket count:** 56 stated, list gives 65 or 53. Default: follow the list.
2. **`tests/fundamentals/fixtures/` keeps its name.** Renaming needs changing frozen manifests, the
   stage 4 history readers and `holds.yaml`, which the owner reserved for a proven need. Default:
   keep it; a later rename is its own decision.
3. **`tests/equity_os/` instead of `tests/`.** Default: as designed, see section 2.
4. **Distribution name `equity-os`** was not named by the owner. Default: rename, since one
   `uv lock` entry changes and no such package remains.

## 12. Not established

- What produced the brief's 187 backward edges (section 7).
- Whether a retained first-party and a vendor capture exist that the restored copy has not extracted.
  The rehearsal selects them read-only at its start; if either does not exist, it uses synthetic
  input for a test-only entity through the existing test helpers.

- What the two restricted YAML files contain, by instruction. If they name a moved path that goes
  past `Selection`, the opaque stage 4 test fails and the fix goes through `recorded_path`; they are
  never edited.
- The complete `edits.tsv`, until the tree runs.
- Whether removing eager `__init__` imports exposes an import cycle that today's import order hides.
  The plan imports every module alone in a fresh process. A cycle found there is fixed by moving one
  import inline through `edits.tsv`, recorded with its reason. In a pinned file that would add a third
  listed row; none is expected.
- Whether `content_sha256` values inside `ledger_stage1_manifest.yaml` are anything other than
  report content hashes (inferred); the gate would show a dependence.
- Whether Python resolves the root-level `equity_os` differently under hatch's editable install; the
  cutover rehearsal checks that `eqos` runs from outside the repo root as well as inside it.
