# RESTRUCTURE-1 Implementation Plan

**Status:** drafted, awaiting Sol. **Bead:** `eqos-foec`.
**Origin:** `docs/specs/2026-11-05-restructure.md`; owner decisions recorded in `eqos-foec`.
**Goal:** Move source, config and tests into the owner's buckets in one scripted commit, with every
stored pin, sealed digest and report still valid and `eqos` replacing `fundamentals`.

**Out of scope:** search design; the lens interface; every stage reading from storage; vendor-first
sources; model extraction; testing on five companies; fixing 800-line breaches; fixing backward
imports; renaming fixtures; replaying `research-4` (designed and dry-checked only).

**Constraints:**
- The move has no logic edits. Every exception is a row in `edits.tsv`.
- No committed migration or frozen manifest changes. No config file byte changes.
- The script never opens `stage4_holdout.yaml`, `stage4_manifest.yaml`, `data/holdout/` or
  `data/raw/onboarding/`, and never reads `data/`.
- Nothing writes to the live database. Rehearsal runs only in `eqos_test_*`.
- Minimal code. The script and map are deleted after `research-4` is replayed.
- Pytest at most 8 workers. A gate takes about 50 minutes; run it as a `systemd-run --user` unit
  (learnings: long gates).
- Check mypy with `--cache-dir=/dev/null`.
- Stage explicit files only; no machine-local paths, figures or document bodies in committed text.

**Shape:** Tasks 1–2 land on `main` and change no behaviour. Tasks 3–6 are **one atomic commit
group** on branch `restructure-1` in a worktree: no green split exists (spec §5), so green is
promised only at the end of Task 5, and `main` sees the whole move at Task 7. Task 8 onward are
ordinary commits on the moved `main`. Sol reviews at spec and plan, and again after Task 5, before
landing.

## Task 1: Commit the map and rule

Goal: `scripts/restructure/rule.py` regenerates `moves.tsv` byte-identically, every module, config
file and test is assigned exactly once for `main` and `research-4`, and `judgement_calls.tsv` is
available for review.

Files:
- Create: `scripts/restructure/rule.py`, `moves.tsv`, `judgement_calls.tsv`, `pinned_files.txt`
  (from the drafts under `scratchpad/restructure/`, after Sol rules on placements).

Interfaces:
- Produces: `moves.tsv` columns `kind, old, new, flag`, with kinds `module`, `init`, `config`,
  `test`; `pinned_files.txt`, the 40 relative paths `_sources_sha256` hashes today.

Approach: Apply Sol's placement rulings to the regex table, not to the TSV. Keep the coverage
checks: assigned once, no collision, target in the owner's list, restricted names absent.

Verification: `python3 scripts/restructure/rule.py HEAD 45d315f9` prints `COVERAGE OK` and exit 0;
a second run leaves `git diff --stat` empty. Delete one rule in a scratch copy: it exits non-zero
naming the module.

Dependencies: None.

Risks: A commit on `main` adds a module before the move; the rule fails loud on it, which is why
Task 7 re-runs it.

## Task 2: Make the gate rename-aware

Goal: A moved file contributes only its changed lines to the fixture rails, and a listed oversize
file does not fail the size check; behaviour on a tree with no renames is unchanged.

Files:
- Modify: `scripts/verify.sh`
- Test: a scratch repo exercise, with results recorded in the commit message; there is no suite for
  this script.

Interfaces:
- Produces: `VERIFY_OVERSIZE_LIST`, an optional file of repo paths the size check skips.

Approach: Replace the per-path added-lines loop with one `git diff -U0 -M <base>` over the changed
set, split by destination file, keeping untracked-file handling. Filter the size check through the
list. Leave every rail's patterns alone.

Verification: In a scratch git repo with a fixture containing a harvested id, a pure rename plus one
changed import raises no rail, while a newly added line containing the id still raises STOP. On
`main`, `scripts/verify.sh baseline restructure-pre` then `gate restructure-pre` passes unchanged.
That baseline run also serves Task 5.

Dependencies: None.

Risks: This is a security rail, and a wrong diff could hide a real leak; hence the required
negative case. Characterization-first: run the negative case before and after the edit.

## Task 3: Write the move script and record today's values

Goal: `move.py` turns a clean tree into a moved tree, with the logic-free proof passing and every
restricted name refused; pre-move pin and parser digests are recorded.

Files:
- Create: `scripts/restructure/move.py`, `edits.tsv`, `capture_digests.py`
- Test: runs against a throwaway worktree of `main` at branch `restructure-1`.

Interfaces:
- Consumes: `moves.tsv`, `pinned_files.txt`.
- Produces: `move.py [--check REF]`; `oversize.txt`; a `MOVED_PINS` mapping in the moved
  `run_config.py`; `digests-before.json`, holding the five stored pin digests and the parser digest
  of every registered parser, gate, `extract_text` and canary marker.

Approach: As spec §4, in order: refuse a dirty tree; compute legacy digests from old bytes; `git mv`;
rewrite imports through AST positions, splitting a `from` whose names scatter; rewrite mapped
dotted strings and `src/fundamentals/...` paths outside pinned files; recompute `parents[n]`; handle
`__init__.py` per the map; apply `edits.tsv` with exact match counts; update `pyproject.toml` and
`uv lock`; run ruff on changed Python only; run the proof; print any old-package name with no row
and exit non-zero. It reads only the listed files. `capture_digests.py` runs after
`register_tables` on the specs from `surfaces.yaml`, and works on old and new import roots via an
argument.

Verification: `move.py --check 45d315f9` writes nothing and exits 0 once the edit list settles. In
the worktree, `uv sync`, then `ruff check`, `ruff format --check`, and `mypy --strict equity_os
--cache-dir=/dev/null` pass. A new process per module imports each alone with no failure.
`eqos --help` works inside and outside the repo root. `strace -f -e openat` on one script run, or an
equivalent audit hook, shows no restricted path opened.

Dependencies: Tasks 1, 2.

Risks: The largest unknown is the size of `edits.tsv`. A hidden import cycle may appear (spec §12).
A comment inside a multi-line `from` is lost by regeneration: the script fails on it instead, and a
row handles it.

## Task 4: Add the pin bridge and prove it on the digests

Goal: On the moved tree, the five live versions compute exactly their stored digests, and any edit
to a pinned file does not.

Files:
- Modify (through `edits.tsv` and script output): `equity_os/verification/comparison/run_config.py`
- Test: existing `test_compare_config_pins.py`, `test_derived_settings.py` under their new paths.

Interfaces:
- Consumes: legacy digests from Task 3.
- Produces: `MOVED_PINS: Mapping[str, str]`, moved digest to stored digest, five rows, looked up on
  the last line of `_sources_sha256`.

Approach: The script computes the moved digest for each of the five (version, sources) pairs and
writes the table. `digests-after.json` must equal `digests-before.json`. Shareholding versions get
no row (not in live).

Verification: `capture_digests.py` before and after compared with `diff`: identical. Named test
files pass with `-m "not retained"` as a quick check; the gate runs them in full.

Test seams: `extractor_pin`, `vendor_extractor_pin`, and `_SOURCE_ROOT` monkeypatching, as the
existing tests already do.

Dependencies: Task 3.

Risks: Any later change to a pinned file's imports moves its digest, which is drift and correct.
The table is regenerated on any re-run of the script, so a stale table cannot survive a re-run.

## Task 5: Pass the full gate on the moved tree

Goal: The same node ids that passed before pass now, under their mapped paths, with no rail tripped.

Files:
- Modify: `edits.tsv` only, for what the gate finds. Every fix re-runs the script from `main`'s tip;
  the branch is never hand-edited.
- Test: `scripts/verify.sh gate restructure-pre`.

Interfaces:
- Consumes: the Task 2 baseline; `oversize.txt`.
- Produces: `restructure-pre-baseline.json` translated through the map in the worktree's gate
  directory.

Approach: Copy `data/` into the worktree with `cp -a` (learnings: worktree gates; symlinks fail
`O_NOFOLLOW`). It is about 1.5 GB and includes the restricted directories because the stage 4 tests
need them; this is environment setup outside the move script, and nothing reads or prints them.
Copy `.env`. Then translate the baseline and run the gate. Expect failures in guard tests and
literal paths on the first pass; fix through `edits.tsv`, re-run the script, and re-run only the
failing files, keeping the full gate for the last pass.

Verification: The gate prints `test-set OK ... node ids identical to baseline`, skips within the
baseline, ruff and mypy green, and rails clear. `test_frozen_manifests.py` including `-k
stage4_holdout`, `test_stage4_manifest.py`, and `test_approved_payload_preceded_its_e2e` are in
that set; confirm by name in the log.

Dependencies: Task 4.

Risks: A test's parametrized id may embed a path, which shows as add and remove; translate it in
the baseline step. A green result reached by narrowing a guard is the main review concern: Sol
reads every `edits.tsv` row touching a test.

## Task 6: Rehearse on a restored copy

Goal: Moved code, against a restored copy of live, gives exactly the old code's results, and new
writes are accepted.

Files:
- Create: `scratchpad/restructure/rehearse.sh` (not committed).

Interfaces:
- Consumes: a fresh `db backup` from live (a read-only transaction with lock files, verified from
  `pg/backup.py`) or the latest existing set if no live change has happened since.
- Produces: `before/` and `after/` output directories, compared with `diff -r`.

Approach: Restore into a fresh `eqos_test_*` with `db restore --set ... --replay-runs` using the
**old** code in the main checkout. With the old code, record for all report versions `ledger check`
output and `eqos.version_sealed_digest`; for all runs `compare replay` output; `version_pins`; table
row counts. Point the worktree's `EQOS_PG_DB` at the same database and record the same with `eqos`.
Then, moved code only, in order: `compare run` for an existing request returns the stored run id
(unchanged identity); a draft from an existing run is not refused; one new draft version goes through
submit and a recorded panel response (`rehearsal_allowed` governs); a re-ingest of a retained capture
pins with no drift; edit one byte of a pinned file in the worktree, confirm `VersionContentDriftError`,
and revert. Finally drop the database.

Verification: `diff -r before after` is empty. Each moved-code step prints its expected result. The
rehearsal log names the database and it matches `eqos_test_*`; no command ran against `equity_os`.

Test seams: the CLI commands, not internals.

Dependencies: Task 5.

Risks: `scratchpad/live-run-1/live-scratch/lq.sh` names `fundamentals`, the old `config/*` paths and
the live database, and changes directory on source; the rehearsal does not use it. Its update belongs
to Task 9. A restore failing for an old set (older than migration 0030) means taking a new backup.

**Then: Sol phase-end review** of the map, script, `edits.tsv`, gate log and rehearsal diff, running
the review loop in `.claude/rules/core/04-agent-stack.md`. Fix rounds change data files and re-run
Tasks 3–6 as far as needed. Landing needs `APPROVE`.

## Task 7: Land

Goal: `main` holds the moved tree in one commit; `eqos db check-live` passes; live is unchanged.

Files:
- Modify: everything in `moves.tsv`, as one commit.

Interfaces:
- Consumes: Sol's approval; the approved `edits.tsv` and map.

Approach: Confirm `main`'s tip is the branch's base; if it moved, re-run `rule.py` and the script from
the new tip and re-run the gate. Record live table counts. Fast-forward `main` to the branch's single
commit. Run `uv sync`. Remove the old `fundamentals` entry points by that sync, and confirm with
`which`. Record the pre-move tip's hash in the commit message: replay needs it.

Verification: `eqos db check-live --migrations-dir migrations` exits 0. Counts are equal. `git log
--follow` on one pinned file shows its old history. `test -e src || echo gone`. `git status` is clean
except `.beads/issues.jsonl`.

Dependencies: Task 6 and `APPROVE`.

Risks: Anything else using the checkout is broken from here until `uv sync`: run them back to back
with no other agent active. Rollback is `git revert` of one commit plus `uv sync`; no database state
needs undoing.

## Task 8: Add the import rule and source list

Goal: A new backward import fails a test; a code source missing from the list, or a list entry
missing from code, fails a test.

Files:
- Create: `tests/equity_os/test_import_rule.py`, `tests/equity_os/support/allowed_backward_imports.txt`,
  `config/sourcing/sources.yaml`, `config/sourcing/<vendor>.yaml` per vendor,
  `tests/equity_os/contracts/sourcing/test_source_list.py`

Interfaces:
- Produces: the bucket order constant, in the import test only.

Approach: The import test walks `equity_os/` ASTs, computes (file, imported module) pairs that point
upward, and fails on any not in the allow-list; the list may shrink. Generate the source files once
from `source_catalog.py`'s catalog and `surfaces.yaml` and the Upstox route registry, then review by
hand. The source test compares both ways and names what differs. No product code reads either.

Verification: Both tests pass on the tree. Seed a scratch edit with an upward import, and one
catalog surface removed from the YAML: each fails naming the item.

Dependencies: Task 7.

Risks: The registry may have sources outside these three today; each found is listed or raised, not
ignored.

## Task 9: Write READMEs, update docs and prompts

Goal: Every bucket and sub-bucket has a README, living docs name the new paths and commands, and the
one scheduled prompt uses `eqos`.

Files:
- Create: 80 `equity_os/**/README.md`
- Modify: `.claude/project/{repo-map,docs-index,verification,tools}.md` and their `.codex` mirrors as
  they apply, `.claude/rules/python/*` where paths appear, `AGENTS.md`, `CLAUDE.md`,
  `docs/backend-roadmap.md`, `.env.example`, `scripts/render_dashboard.py` if it names paths,
  `.claude/project/learnings.md` (one entry on the bridge).

Approach: Each README has: handles; does not handle; reads and writes, from module docstrings and
imports, checked against the code by the writer. A one-line-per-module list is not enough for a
bucket README. Update the disabled scheduled task's text through `schedule_task`, leaving it disabled.
Update `scratchpad/live-run-1/live-scratch/lq.sh`'s command and config paths (not committed).
Historical docs stay, with one line in `docs-index.md` pointing at the map.

Verification: A script over the `moves.tsv` targets checks a README exists in every folder. `grep -l`
over the living doc list finds no `src/fundamentals`, `uv run fundamentals` or old `config/` paths.
`test_frozen_manifests.py -k stage4_holdout` still passes after the README commit. A final full gate
on `main` passes.

Dependencies: Task 8.

Risks: READMEs drift; keep them to what a reader cannot get from `ls`. `bd remember` entries naming old
paths are updated by the orchestrator, not in a commit.

## Task 10: Record what is left

Goal: Follow-ups exist as beads and the status dashboard is current.

Files:
- Modify: `docs/status/*` through the existing render step.

Approach: Orchestrator files beads for: replay on `research-4`, then delete `scripts/restructure/` and
`VERIFY_OVERSIZE_LIST`; the existing 800-line breaches; a decision on renaming fixtures; retiring
`MOVED_PINS` rows as versions bump. It records Sol's verdict on `eqos-foec` and closes the epic.

Verification: `bd show` on each. `git status` clean except what the orchestrator intends.

Dependencies: Task 9.

## Self-review

- **Spec coverage:** pins §1 → Tasks 3, 4, 6. Layout and map §2–3 → Tasks 1, 3. Script §4 → Task 3. Atomic
  sequence §5 → shape note, Task 7. Gate §6 → Tasks 2, 5. Import rule, sources, READMEs §7 → Tasks 8, 9.
  Replay §8 → Task 3 `--check`, Task 10. Acceptance §10: items 1 → T1; 2 → T3; 3 → T5; 4 → T6; 5–6 → T7;
  7 → T8; 8 → T9.
- **Named blockers:** backward imports → T8. `parents[n]` → T3. `verify.sh`, pyproject, ruff, mypy, pytest
  → T3 (edits), T2. `.claude` rules and docs → T9. Scheduled prompts → T9. Fixtures and support modules →
  spec §2, T3. `tests/phase_0a`, `tests/equity_os_blueprint` → unchanged, spec §2. `ledger_stage4_check.py`
  → moves to support, imports only; screen export `stage4` → not moved. Restricted files → T3 audit.
- **Gaps named:** the `.codex/` mirrors are included in T9. `:memory:.ses` at the root is untracked and
  untouched. Docs generated into `graphify-out/`, if any, are out of scope.
