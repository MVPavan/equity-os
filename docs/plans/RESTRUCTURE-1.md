# RESTRUCTURE-1 Implementation Plan

**Status:** approved 2026-11-05: approver gpt-6.1-sol, `APPROVE` after one fix round. **Bead:** `eqos-foec`.
**Origin:** `docs/specs/2026-11-05-restructure.md`; owner decisions recorded in `eqos-foec`.
**Goal:** Move source, config and tests into the owner's buckets in one scripted commit, with every
stored pin, sealed digest and report still valid and `eqos` replacing `fundamentals`.

**Out of scope:** search design; the lens interface; every stage reading from storage; vendor-first
sources; model extraction; testing on five companies; fixing 800-line breaches; fixing backward
imports; an import-order test (deferred by Sol's scope cut); renaming fixtures; the real replay on
`research-4` (designed and rehearsed only).

**Constraints:**
- The move has no logic edits. Every exception is a row in `edits.tsv`.
- No committed migration or frozen manifest changes. No config file byte changes.
- The script never opens `stage4_holdout.yaml`, `stage4_manifest.yaml`, `data/holdout/` or
  `data/raw/onboarding/`, and never reads `data/`. Those directories are never copied.
- Nothing writes to the live database. Rehearsal runs only in `eqos_test_*`, with its own snapshot
  root.
- Minimal code. The script and map are deleted after `research-4` is replayed.
- Pytest at most 8 workers. A gate takes about 50 minutes; run it as a `systemd-run --user` unit
  (learnings: long gates).
- Check mypy with `--cache-dir=/dev/null`.
- Stage explicit files only; no machine-local paths, figures or document bodies in committed text.

**Shape:** Task 1 lands on `main` and changes no behaviour. Task 2 ends by committing
`scripts/restructure/` to `main` as the pre-move tip `P`. Tasks 2–5 work on candidate branches
`restructure-1-c<N>`, each holding a move commit and an overlay commit on `P` (spec §5). A rebuild
is a new branch, so nothing is rewritten. `main` sees the move only at Task 6. Sol reviews at spec
and plan, and after Task 5.

**Where things run (spec §5):** script work runs in a disposable worktree with no `data/`.
Everything needing retained data runs in the main checkout, switched to the candidate, with the
checkout held exclusively; the orchestrator confirms no other agent is using it. Nothing under
`data/` is copied or linked.

**Estimate:** about 17 hours elapsed, against about 35 for the previous ten-task plan. Neither was
measured; both are the author's estimates, and gate runtime dominates. Each extra final gate adds
about an hour.

| Task | Hours |
|---|---|
| 1. Make the gate rename-aware, take the baseline | 2.5 |
| 2. Build the transformation: map, script, edits, pin bridge, digests | 5 |
| 3. Write the overlay: READMEs, source list, docs | 2 |
| 4. Rehearse cutover and database, run the final gate | 4 |
| 5. Rehearse the replay | 0.5 |
| Sol phase-end review and fix round | 2 |
| 6. Land and close out | 1 |

## Task 1: Make the gate rename-aware

Goal: A reviewed moved file contributes only its changed lines to the fixture rails, and a listed
oversize file passes only at or under its ceiling. With neither variable set, the gate is unchanged.

Files:
- Modify: `scripts/verify.sh`
- Test: a scratch repo exercise (below), results recorded in the commit message; there is no suite
  for this script.

Interfaces:
- Produces: `VERIFY_RENAME_MAP` (a `moves.tsv`), `VERIFY_OVERSIZE_LIST` (path, pre-move lines,
  ceiling).

Approach: As spec §6. In the added-lines loop, a destination with a same-domain row takes its lines
from `git diff -U0 -M <base> -- <old> <new>`, with both paths given so git can pair them. All other
paths keep the existing branch. The size check compares against the list before its `head -3`
truncation. Leave every rail's patterns alone. The existing gate needs no other change, because
`git diff --name-only` lists a rename by its destination.

Verification: Characterization first: run the negative cases before and after the edit. In a scratch
git repo (copy of the script, a one-test `pyproject`, a capture folder holding a harvested id, and a
test file already containing that id), the gate's rails line shows:

| Case | Expected |
|---|---|
| Mapped same-domain rename plus one changed import, committed | no rail |
| Same, staged only | no rail |
| Same, unstaged (`mv`, destination untracked) | STOP, full scan |
| Mapped rename whose added line holds the id | STOP |
| Unmapped rename into `tests/` | STOP, full scan |
| Mapped row crossing into `tests/` from outside | STOP, full scan |
| Untracked new test file holding the id | STOP |
| Ordinary added leak in an unrenamed file | STOP |
| Any rename with `VERIFY_RENAME_MAP` unset | as the old script |

Listed file at ceiling passes; one line above fails; an unlisted file above 800 fails. Then, on
`main`, `scripts/verify.sh baseline restructure-pre` and `gate restructure-pre` pass.

Dependencies: None.

Risks: This is a security rail, and a wrong diff could hide a real leak; hence the table. The STOP
cases are the point of it.

## Task 2: Build the transformation

Goal: One command turns `P` into a moved tree with the logic-free proof passing, the five live pins
reproduced through the bridge, every restricted name refused, and each parser digest unchanged.

Files:
- Create, in `scripts/restructure/` (developed in the scratchpad, committed to `main` as `P` when the
  edit list settles): `rule.py`, `moves.tsv`, `judgement_calls.tsv`, `pinned_files.txt`, `move.py`,
  `edits.tsv`, `oversize.tsv`, `capture_digests.py`, `translate_baseline.py`, `param_ids.tsv`.
- Test: the disposable worktree.

Interfaces:
- Produces: `move.py`, which ends with a committed move commit recording `P`; a `MOVED_PINS` table in
  the moved `run_config.py`; `digests-before.json` and `digests-after.json`.

Approach: As spec §4, in order: refuse a dirty tree; compute legacy digests from old bytes; `git mv`;
rewrite imports through AST positions, splitting a `from` whose names scatter and resolving relative
test imports against the old module identity; rewrite mapped dotted strings, `src/fundamentals/...`
and `config/...` paths outside pinned files; recompute `parents[n]`; handle `__init__.py` per the
map; apply `edits.tsv` with exact match counts; update `pyproject.toml` and `uv lock`; run ruff on
changed Python only; generate `MOVED_PINS` for the five (version, sources) pairs; run the proof,
including name-and-scope equality of mapped import bindings; print any old-package name or
config path with no row and exit non-zero. It reads only the listed files.

**`edits.tsv` rows for review, known now:**
- In pinned files, the only two: `PAGE_OUTCOME_KIND` and `ACQUISITION_OUTCOME_KIND` frozen to their
  literal text (spec §4).
- `repo_root` in both config classes.
- The rest of spec §4's "Known deliberate edits".

`capture_digests.py` runs on old and new import roots by argument. It records every hash-producing
call site keyed by persisted `parser_version`: `PARSERS` entries, table parsers after
`register_tables` on the specs from `surfaces.yaml`, `identity_gate`, `topology_gate`, `continuation`,
`extract_text` and canary markers.

Verification, in the worktree:
- `rule.py P 45d315f9` prints `COVERAGE OK`; a second run leaves the map identical.
- `uv sync`, then ruff check and format, and `mypy --strict equity_os --cache-dir=/dev/null`.
- A new process per module imports each alone.
- `digests-after.json` equals `digests-before.json`; the five computed pins equal the five read-only
  from live. Editing one byte of a pinned file raises drift in `test_compare_config_pins.py`.
- `repo_root` on each mapped config file `FundamentalsConfig` or `WatchlistConfig` loads returns the
  repo; on a temporary folder's config it returns what it does today.
- `native_kind` from both frozen constants equals the old module-derived text.
- Tests that need no retained data pass, as a quick check.
- `strace -f -e openat` on one script run, or an equivalent audit hook, shows no restricted path
  opened.

Dependencies: Task 1.

Risks: The largest unknown is the size of `edits.tsv`. A hidden import cycle may appear (spec §12). A
comment inside a multi-line `from` is lost by regeneration: the script fails on it instead, and a row
handles it. A green result reached by narrowing a guard is the main review concern: Sol reads every
row touching a test.

## Task 3: Write the overlay

Goal: The overlay commit holds every README, the source list and its one test, and the living docs,
ready before the final gate.

Files:
- Create: 80 `equity_os/**/README.md`; `config/sourcing/sources.yaml`;
  `tests/equity_os/contracts/sourcing/test_source_list.py` (under 30 lines).
- Modify: `.claude/project/{repo-map,docs-index,verification,tools}.md` and their `.codex` mirrors as
  they apply, `.claude/rules/python/*` where paths appear, `AGENTS.md`, `CLAUDE.md`,
  `docs/backend-roadmap.md`, `.env.example`, `scripts/render_dashboard.py` if it names paths,
  `.claude/project/learnings.md` (one entry on the bridge).

Approach: One precise sentence per leaf and a short paragraph per bucket, from module docstrings,
checked against the code by the writer. Generate `sources.yaml` once from `BUILTIN_SOURCES`,
`VENDOR_SURFACES`, `surfaces.yaml` and `ROUTES`. Historical docs stay, with one line in
`docs-index.md` pointing at the map. These are new files or files the script does not edit, so the
commit cherry-picks onto any rebuild.

Verification: A one-off check over the `moves.tsv` targets finds a README in every folder. `grep -l`
over the living doc list finds no `src/fundamentals`, `uv run fundamentals` or old `config/` paths.
The source test passes, and fails naming the item when one entry is removed by hand.

Dependencies: Task 2.

Risks: The registry may hold sources outside these four sets; each found is listed or raised, not
ignored. If the test cannot stay under 30 lines, defer it to a bead and keep the list.

## Task 4: Rehearse cutover and database, run the final gate

Goal: On the committed candidate, the real venv upgrades cleanly; moved code matches old code on
restored data and writes new records correctly; and the final gate passes.

Files:
- Create, not committed: `scratchpad/restructure/rehearse.sh`, a small `replay_one.py` calling
  `restore_check.replay` for one run id, and the updated `scratchpad/live-run-1/live-scratch/lq.sh`.

Interfaces:
- Consumes: a fresh `db backup` from live (a read-only transaction with lock files, verified from
  `pg/backup.py`) or the latest existing set if no live change has happened since.
- Produces: `old/` and `new/` output folders, a normalised diff, a write-delta file per side.

Approach, in order, in the main checkout, holding it exclusively. Every command names its own
`eqos_test_*` database and scratch snapshot root:

1. **Old side, on `P`.** Restore copy A with `db restore --set ... --replay-runs`. Record
   mismatches and expired runs, counts, `version_pins`, sealed digests and parser digests. Run
   `ledger check` for every report version, then record the counts again.
2. **Cutover.** `git switch` the candidate, `uv sync`. `eqos --help` and `eqos-operator --help` work
   inside the repo and, by the venv's path, outside it; `fundamentals` and `fundamentals-operator` are
   gone by `which`. Update `lq.sh`'s command and config paths, then source it with a harmless
   `eqos_test_*` target and confirm it resolves them. Prepare the scheduled task's prompt text,
   leaving the task disabled and unsent until Task 6.
3. **Moved side.** Restore copy B from the same set; the same recording as step 1. Compare with A
   (spec §10 item 4). Normalise only the validation id, plus any field added to an enumerated list
   with a reason. Each side's write delta must be exactly its new validation rows.
4. **New writes on copy B.** Select read-only a retained first-party item and a retained vendor capture
   with no extraction row; if either has none, synthesise one for a test-only entity using existing
   test helpers. `evidence ingest` and the vendor ingest route each add extraction and interpretation
   rows, shown by the delta; the stored pins are unchanged. `compare run` with a new cutoff reports a
   new run. Draft from it; `ledger check`; submit; a recorded `provider: rehearsal` APPROVE bound to
   that version (`rehearsal_allowed` governs). Then `ledger check`, `replay_one.py` and `ledger export`
   on those new records. A `compare run` for an existing request returns its stored run.
5. **Drift.** Edit one byte of a pinned file, confirm `VersionContentDriftError`, and undo it by
   restoring that file's single edit by hand. `git status` shows it clean.
6. **Final gate** on the candidate:
   `VERIFY_SCOPE_BASE=P VERIFY_RENAME_MAP=... VERIFY_OVERSIZE_LIST=... scripts/verify.sh gate
   restructure-pre`, after `translate_baseline.py` writes the baseline.
7. **History.** For each `E2E` file, `git log --follow --diff-filter=A` reaches the first commit
   recorded from `P`.
8. **Back to `main`,** `uv sync`, confirm the old commands return, drop both test databases.

Failures in step 6: fix through `edits.tsv` or the overlay, build a new candidate, and re-run only the
failing files. Keep a full gate for the last pass. A fix to `scripts/restructure/` moves `P`, and the
next gate uses that new recorded `P`.

Verification: Spec §10 items 3–7 and each step's expected result. The log names each database, and it
matches `eqos_test_*`. `test_frozen_manifests.py` including `-k stage4_holdout`,
`test_stage4_manifest.py`, and `test_approved_payload_preceded_its_e2e` appear by name in the gate
log.

Test seams: the CLI commands, not internals, apart from `replay_one.py`.

Dependencies: Tasks 2, 3.

Risks: A restore failing for an old set (older than migration 0030) means taking a new backup. A
parametrized id embedding a path shows as add and remove: list it in `param_ids.tsv`. The main
checkout is unavailable to others during this task.

## Task 5: Rehearse the replay

Goal: The spec's replay sequence works on the state it really transforms, without altering
`research-4`.

Files: none committed. A disposable branch from `45d315f9` in a disposable worktree.

Approach: Merge `P`, run `move.py`. Build the moved tree of `P` alone and confirm it equals the
candidate's move commit; then `git merge -s ours` that commit and merge the candidate.

Verification: Both merges complete without a hand fix. The diff against the candidate names only
`research-4`'s own work, under mapped paths. `MOVED_PINS` is byte-equal. Ruff, mypy and importing each
module pass. `git rev-parse research-4` still gives `45d315f9`. Delete the disposable branch and
worktree.

Dependencies: Tasks 2, 3. It needs no retained data.

Risks: A conflict here is a real replay problem and goes to the review, not a hand fix.

**Then: Sol phase-end review** of the map, script, `edits.tsv`, overlay, gate log, rehearsal output
and replay result, running the review loop in `.claude/rules/core/04-agent-stack.md`. Fix rounds
change data files and re-run Tasks 2–5 only as far as needed. Landing needs `APPROVE`.

## Task 6: Land and close out

Goal: `main` holds the moved tree; `eqos db check-live` passes; live is unchanged; follow-ups exist.

Files:
- Modify: everything in `moves.tsv` and the overlay, by fast-forward. `docs/status/*` through the
  existing render step.

Interfaces:
- Consumes: Sol's approval, with the approved candidate as the only thing landed.

Approach: Confirm `main`'s tip is `P`; if it moved, rebuild from the new tip and re-run the gate.
Record live table counts. Fast-forward `main` to the candidate. Run `uv sync`. Remove the leftover
ignored `__pycache__` folders under `src/` and `tests/fundamentals/` (only those), so `src/` is gone.
Update the disabled scheduled task's text through `schedule_task`, leaving it disabled. The
orchestrator updates `bd remember` entries naming old paths, records Sol's verdict on `eqos-foec`,
and files one bead each for: the real `research-4` replay and then deleting `scripts/restructure/`
and both gate variables; the import-order test; the 800-line breaches; a decision on renaming
fixtures; retiring `MOVED_PINS` rows as versions bump.

Verification: `eqos db check-live --migrations-dir migrations` exits 0. Counts are equal. `git log
--follow` on one pinned file shows its old history. `test -e src || echo gone`. `git status` is clean
except `.beads/issues.jsonl`. `bd show` on each new bead.

Dependencies: Tasks 4, 5 and `APPROVE`.

Risks: Rollback is `git revert` of the two commits plus `uv sync`; no database state needs undoing.
The cutover was rehearsed on this checkout in Task 4.

## Self-review

- **Spec coverage:** pins §1 → T2, T4. Layout and map §2–3 → T2. Script §4 → T2. Sequence and route §5
  → shape note, T4, T6. Gate §6 → T1, T4. Source list and READMEs §7 → T3. Replay §8 → T5. Acceptance
  §10: 1–2 → T2; 3–7 → T4; 8 → T5; 9 → T6; 10 → T3.
- **Named blockers:** backward imports → deferred, bead in T6. `parents[n]`, `repo_root` → T2.
  `verify.sh` → T1; pyproject, ruff, mypy, pytest → T2. `.claude` rules and docs → T3. Scheduled prompt
  → T4 text, T6 update. Fixtures and support modules → spec §2, T2. `tests/phase_0a`,
  `tests/equity_os_blueprint` → unchanged, spec §2. `ledger_stage4_check.py` → moves to support;
  screen export `stage4` → not moved. Restricted files → T2 audit, spec §5.
- **Gaps named:** the `.codex/` mirrors are in T3. `:memory:.ses` at the root is untracked and
  untouched. Docs generated into `graphify-out/`, if any, are out of scope.
