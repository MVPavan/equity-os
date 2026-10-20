# CUTOVER — production `equity_os`: legacy import, fresh Apar extraction, diff, cutover

**Bead:** `eqos-3zl` (blocks `eqos-4j2.8`). **Status:** approved — Sol (gpt-6.1-sol) `APPROVE` 2026-10-20 after the closing loop. Nothing in
this file has been run against `equity_os`. Review history: `scratchpad/execution/cutover/`.
**Owner authorization (PavanMV, 2026-10-20, chat):** agents may use production `equity_os`; migrate
the legacy SQLite work (`data/store/aparinds.sqlite`) into it; re-run the Apar extractions fresh
into it; report every legacy-vs-fresh difference. The legacy data is research-grade, not sacred: a
difference is reported, not a blocker. The orchestrator writes both `by: PavanMV` gate records
(import; transition), each citing this chat authorization. Sol's `APPROVE` of the reconciliation and
diff reports is enough to reopen; the owner reads the diff report afterwards.
**Source runbook:** D2 plan § "Owner-gated production runbook"
(`docs/workstreams/data-foundation/plans/D2.md`). Rollback only inside the frozen window (D2 ruling R1,
data spec §6 step 7 as amended). Fresh-extraction path: `PILOT-GAP-admission.md`, `PILOT-GAP-alignment.md`
(`cli.PILOT_VERSIONS` = dictionary `v2`, mapping set `v6`, alignment `v2`). Packages: `PREP-7.md` Decision 6.

## Rules for the operator

- Run from the repo root. Every `fundamentals` command targets `EQOS_PG_DB` from `.env` (`equity_os`);
  there is no database flag. PostgreSQL role credentials come from `.env` through `PgSettings`; never
  `cat`/print `.env` or `~/.secrets`. No step needs vendor credentials; if one ever does, use only
  `source scripts/credentials.sh`.
- Do not edit migrations `0001`–`0041`, `config/*` (incl. `legacy_import_manifest.yaml` and the issuer
  configs), frozen manifests or `EXTRACTOR_SOURCES` files. No source edits. Stage nothing in git.
- **Maintenance window:** from Step 0.1 until the Step 7 handoff, only the commands in this runbook
  run against `equity_os`, `$SNAP`, `$BK` or the legacy file. No `fundamentals run`, ingest, compare,
  retention, vendor fetch or scheduled job outside them.
- Any **STOP** returns to the orchestrator with the output; never work around a refusal. STOP
  outcomes needing product work (a new extractor version, capture consolidation) are outside this
  runbook.
- **IRREVERSIBLE** marks a write that the database cannot undo (evidence and fact tables are
  append-only by trigger). Undo is the recovery procedure (R) from a restore-tested matched set.

Constants: `STORE=sqlite-cb02b0f12a1708d0`; `LEGACY_SHA=cb02b0f12a1708d07f4e8f1dbaefd59bb89762897b6de242c03da9f9a8157bd8`;
`SNAP=data/raw/snapshots/v1`; `APAR=data/raw/watchlist/aparinds`; `M=$C/legacy_import_manifest.yaml`.

| PQ | Quarter | Period end | PDF parse config (`--issuer-config`) |
|---|---|---|---|
| PQ0 | FY26_Q2 | 2025-09-30 | `config/aparinds-fy26-q2.yaml` |
| PQ1 | FY26_Q3 | 2025-12-31 | `config/aparinds-fy26-q3.yaml` |
| PQ2 | FY26_Q4 | 2026-03-31 | `config/aparinds-fy26-q4-pg.yaml` |
| PQ3 | FY27_Q1 | 2026-06-30 | `config/aparinds-fy27-q1-pg.yaml` |

### Run directory, state record and guarded execution

- **New run:** `C=data/cutover/run-$(date -u +%Y%m%dT%H%M%SZ)`; `mkdir -p data/cutover && mkdir "$C"`
  (fails if it exists). A resume reuses the same `$C`; only recovery (R) starts a second one.
  `data/` is gitignored.
- `$C/state.log` records each completed step id (`0.6`, `1`, `3.2:FY26_Q2`, …) on its own line,
  appended only after the step's checks pass. Baseline files (`originals.before.sha256`,
  `preflight-inventory.txt`, `B0.path`, `aparinds.sqlite.bak`, `$M` once `3.3` is logged, approved
  `preflight.yaml`/`reconciliation.yaml`, owner records) are written once with `set -o noclobber`
  and never regenerated (a `*.path` pointer that fails validation is kept aside as void, never
  overwritten).
- Every code block is saved as a file and runs as its own shell,
  `bash -c '. scratchpad/cutover/guard.sh; . "$1"' _ <block file>`, with `C`, `BK`, `BK0`, `SNAP`,
  `APAR`, `M`, `LEGACY_SHA` exported. `guard.sh` is a new file of exactly:

  ```bash
  set -euo pipefail; set -o noclobber
  stop() { echo "STOP: $*" >&2; exit 1; }
  # put <file> <line>: append to $C/<file>; a failed append ends the block.
  put() { printf '%s\n' "$2" >>"$C/$1" || stop "cannot append to $C/$1"; }
  # run <log> "<allowed exit codes>" <command...>: attempt n writes $C/<log>.<n>.out/.err (never
  # reused) and logs (attempt, rc, argv) to $C/exits.log; an allowed code points $C/<log>.out at
  # that attempt, any other code ends the block's shell.
  run() {
    local log=$1 ok=$2 rc=0 n=1; shift 2
    while [ -e "$C/$log.$n.out" ]; do n=$((n+1)); done
    "$@" >"$C/$log.$n.out" 2>"$C/$log.$n.err" || rc=$?
    put exits.log "$log.$n"$'\t'"$rc"$'\t'"$*"
    case " $ok " in *" $rc "*) ln -sfnT "$log.$n.out" "$C/$log.out" || stop "publish $log.out"
                               return 0 ;; esac
    stop "$log.$n exit $rc (see $C/$log.$n.err)"
  }
  done_step() { put state.log "$1"; }
  is_done() { grep -qxF "$1" "$C/state.log" 2>/dev/null; }
  # backup <name> <parent>: one matched set, recorded in <name>.path. A retained attempt that
  # printed exactly one `published` line (logged or not) is adopted, never re-taken. A pointer
  # is published atomically and validated on resume; an invalid one is kept aside as void.
  backup() {
    [ -s "$C/$1.path" ] && [ -f "$(cat "$C/$1.path")/manifest.yaml" ] && return 0
    [ -e "$C/$1.path" ] && { mv "$C/$1.path" "$C/$1.path.void.$(date +%s%N)" || stop "void $1.path"; }
    local out; out=$(ls -v "$C"/backup-"$1".*.out 2>/dev/null | tail -1) || true
    if [ -z "$out" ] || [ "$(grep -c $'^published\t' "$out")" != 1 ]; then
      run "backup-$1" 0 uv run fundamentals db backup --out "$2" --snapshot-root "$SNAP"
      out="$C/backup-$1.out"
    fi
    [ "$(grep -c $'^published\t' "$out")" = 1 ] || stop "backup-$1 output"
    local set; set=$(cut -f2 "$out")
    [ -f "$set/manifest.yaml" ] || stop "$set has no manifest"
    { printf '%s\n' "$set" >|"$C/$1.path.tmp" && mv "$C/$1.path.tmp" "$C/$1.path"; } \
      || stop "cannot write $1.path"
  }
  # restore <name> [--replay-runs]: the set into a test database and an empty root, both new per
  # attempt; only an existing attempt path advances the suffix.
  restore() {
    local name=$1 low=${1,,} n=1; shift
    while [ -e "scratchpad/cutover/restore-$low-$n" ]; do n=$((n+1)); done
    mkdir "scratchpad/cutover/restore-$low-$n" || stop "mkdir restore-$low-$n"
    run "restore-$name" 0 uv run fundamentals db restore --set "$(cat "$C/$name.path")" \
      --database "eqos_test_cutover_${low}_$n" --snapshot-root "scratchpad/cutover/restore-$low-$n" \
      --live-snapshot-root "$SNAP" "$@"
  }
  # resume_branch: the resume entry point from run-directory artifacts alone, no database call.
  resume_branch() {
    if [ ! -e "$C/B0.path" ] && ! compgen -G "$C/backup-B0.*.out" >/dev/null; then echo new-run
    elif ! is_done 0.6; then echo finish-B0
    elif [ ! -e "$M" ] || ! is_done 3.3; then echo first-missing-step
    else echo status; fi
  }
  ```

  `errexit` is a backstop only (it is off inside `&&`/`||`/`if` contexts): every check in a block is
  written `<check> || stop "<what>"`, and every evidence append, pointer and state write goes
  through `put`, `run` or `backup`, which stop on failure. A failure exits the block's shell with
  1 before its next command. The operator starts a block only after the previous one exited 0; a
  nonzero block is a STOP.
- **Guard check** (`scratchpad/cutover/test_guard.sh`, file-only, temporary `$C`), passing before
  Step 0. Each case exits 1 and a following marker never runs: a loop whose second `run` returns a
  disallowed code; `diff -r … || stop`; an unchecked `false`; `run` with `exits.log` a directory;
  `done_step` with `state.log` a directory; `restore` with `scratchpad/cutover` unwritable (no loop).
  Also: a repeated `run` writes attempt 2 and `.out` points at it; `backup` adopts an attempt
  output with one `published` line without invoking `db backup`; `resume_branch` prints `finish-B0`
  for that `$C` and for `B0.path` + `0.5` without `0.6`, and `first-missing-step` for `$M` without
  `3.3` and for a B0 recovery directory (`0.5`, `0.6`, no `$M`); a failed `B0.path` write (leaves
  only `.path.tmp`) and a seeded empty `B0.path` are each recovered by the next `backup B0`, which
  voids any invalid pointer, re-adopts the retained output and writes a valid pointer without
  invoking `db backup`.

### Resume map (after any interruption)

First run `resume_branch` (artifacts only, before any database call):
- `new-run`: no backup was attempted, so nothing changed in the database; Step 0 from 0.1 in a new
  `$C`.
- `finish-B0`: B0 was attempted or recorded but not restore-tested. Never recapture baselines:
  check `aparinds.sqlite.bak` against `LEGACY_SHA` and `sha256sum -c originals.before.sha256`,
  bootstrap if 0.3 showed the roles absent, then re-run the 0.5–0.6 block, which adopts a published
  B0 (an attempt without a `published` line is retried; a CLI refusal of the parent is a STOP).
- `first-missing-step`: `$M` is not yet copied and logged (before 3.3, or a B0 recovery directory);
  no `legacy status`. Continue at the first step id not in `state.log` (a B0 recovery directory:
  Step 1); a quarter id `3.2:<Q>` absent means re-run only that quarter (an ingest of an already
  registered package reuses it).
- `status`: read `$C/state.log` and `run status 0 uv run fundamentals legacy status --manifest "$M"`
  (prints label, store, state and legal next commands), then the table below.

A regenerated candidate (`legacy preflight`/`reconcile` overwrite `--out`) is written to a fresh
path `$C/<name>.resume-<n>.yaml` and compared with the approved payload; the approved file is kept.
The database is the truth: a status past a step whose id is missing (`3.4` → `IMPORTED`, `6.2` →
`CUTOVER_FROZEN`, `7.1` → `OPEN`) means the step committed before it was logged, and its id is
appended before continuing. Steps without a status are re-run: ingest and compare reuse what
committed, a backup is adopted as above, and each restore attempt takes new names.

| Status | Continue at |
|---|---|
| `NOT_IMPORTED` | 3.4 with the already approved `$M`/`preflight.yaml` if a fresh-path preflight's payload matches it; else Sol round A on the new candidate |
| `IMPORTED` | 3.5 (reconcile), then Step 4 for quarters not in `state.log` (`compare run` prints `created<TAB>false` for a reused run), then Step 5 (a partial `$C/diff` or `$C/diff-repeat` is first moved to `$C/diff.void-<n>`, never deleted) |
| `CUTOVER_FROZEN` | 6.3 if not in `state.log` (B1 adopted if attempted, new restore attempt), else 7.1; the window is open: reopen or rollback only |
| `ROLLED_BACK` | Step 6.5 rules; re-cutover needs a fresh reconciliation and approval |
| `OPEN` | Step 7.2 checks; rollback is gone, recovery is (R) from `B1` |

Step 0's "STORE already exists" STOP applies only when `state.log` has no `3.4`. After 7.2 the
run's leftover `eqos_test_cutover_*` databases and `scratchpad/cutover/restore-*` roots are dropped
through the test-database tooling; nothing else.

## Prerequisite P — fresh rehearsal (before Step 0)

`scripts/stage2_recreation_check.sh` cannot pass today: its final restore (line 213) omits the
required witness flag (`db restore` exits 2), and its EXIT trap deletes `$ROOT` with the
reconciliation in it. **P is separate, Sol-reviewed prerequisite work** (its own bead, outside this
no-source-edit scope): add `--live-snapshot-root "$ROOT/snap"` to that restore and copy
`$ROOT/reconciliation.payload` to a caller-given output path before exit. Then run it fresh; it must
exit 0, and its payload is saved as `$C/rehearsal-reconciliation.yaml`. **STOP** until P passes.

## Step 0 — Maintenance window, preflight (read-only), baseline backup, restore test

1. **Quiesce.** Before any hash, copy or backup:
   - `docker compose ps` shows `equity-os` healthy; `docker compose port postgres 5432` prints
     `127.0.0.1:<port>`.
   - The operator checks, and records in `$C/quiesce.txt`: no `fundamentals` process
     (`pgrep -af fundamentals` empty); no cron/systemd/scheduled task that runs `fundamentals`;
     `pg_stat_activity` for `equity_os` shows no session except the probe (printed by 0.3).
   - `ls data/store/aparinds.sqlite*` shows no `-wal`, `-shm` or `-journal` sidecar; else STOP.
   - `chmod a-w data/store/aparinds.sqlite` (reversible: `chmod u+w`). The five configs routing
     through `fact_store_id` are refused anyway until reopen (`open_fact_store`).
2. `sha256sum data/store/aparinds.sqlite` equals `LEGACY_SHA`. Hash every file under `$APAR/nse` and
   `$APAR/nse_pdf` into `$C/originals.before.sha256`. `cp -p data/store/aparinds.sqlite
   "$C/aparinds.sqlite.bak"`; its sha256 equals `LEGACY_SHA`.
3. `run preflight-inventory 0 uv run python scratchpad/cutover/preflight.py`; the output is
   `$C/preflight-inventory.out`. A new probe (about 70 lines) on one **admin** connection
   (`PgRole.ADMIN`, the role `db backup` already uses) in a single `REPEATABLE READ, READ ONLY`
   transaction; it changes no grant and prints, sorted:
   - `current_database()`, which must be `equity_os`, and other `pg_stat_activity` sessions on it;
   - `pg_roles` presence of the migrator, runtime and group roles and the purge login;
   - whether schema `eqos` exists; if not, `schema: ABSENT`, then the two empty baseline-id
     sections below, and stop printing here;
   - `eqos_meta.schema_migrations` (filename, sha256), each compared with `migrations/<file>`;
   - `count(*)` for every `eqos.*` table;
   - `eqos.version_pins` rows (artifact, version, sha), each compared with the pin current code
     computes (`load_run_config(Path("config"), PILOT_VERSIONS)`; vendor rows via
     `vendor_version_pin`): `MATCH`, `DRIFT` or `NOT_CURRENT`, naming `vendor_extractor:*` tijori-v4
     and screener-v1;
   - retention state: `count(*)` of `eqos.licence_ends`, `capture_states` with `state='EXPIRED'`,
     `eqos.retention_pending`; whether `$SNAP/.retention/expiry-journal-head.json` exists;
   - every `eqos.capture_refs` row grouped by `source_id`, and whether each re-hashes under `$SNAP`
     (`SnapshotStore(SNAP).read_capture_verified`). The 8 legacy originals (4 XBRL
     `90baae0b 87a5dd95 be8ef651 f76a131a`, 4 results PDFs `8be1b8de 2f9c6d5a 17f5bc04 c0c2b2fa`) are
     listed separately;
   - for APARINDS: its `eqos.reporting_entities` row, `listings` (venue, symbol) and
     `settings_records` `FISCAL_YEAR_END_MONTH` values; plus `eqos.fact_stores`,
     `fact_store_events`, `legacy_imports`, and `runs` for APARINDS;
   - `baseline_capture_ids` and `baseline_interpretation_ids`: every `capture_refs.id` and
     `interpretations.interpretation_id`, sorted (empty on ABSENT). No evidence is written between
     0.3 and 3.2 (Step 1 seeds identity only), so Step 5 classifies reused versus created evidence
     by exact set difference against these.

   **Supported starting states:** (a) schema ABSENT; (b) schema PRESENT with a checksum-valid
   contiguous prefix that includes `0030` (backup and restore refuse a PRESENT set before `0030`).
   **STOP if** any of these holds:
   - the state is neither (a) nor (b). An older prefix needs an owner-ruled protection step (an
     admin `pg_dump -Fc` of `equity_os` into `$C/pre-0030.dump` plus `$SNAP` hashes, restore-tested
     by hand) before any migration; this runbook does not cover it;
   - an applied migration's sha differs from its file;
   - any pin the PQ0–PQ3 compare runs use is `DRIFT` (`version_pins` is immutable);
   - any capture row does not re-hash under `$SNAP`. Captures under any other root are a hard STOP:
     `db backup` and `verify_import` each read one root. Resolving it needs an approved consolidation
     that copies and re-verifies the exact registered records and blobs under one root, then uses
     that root for import, ingests and backups alike; a changed manifest root alone never suffices;
   - `fact_stores` already holds `STORE` and `state.log` has no `3.4`;
   - a session other than the probe is connected, or `retention_pending` is non-empty.
4. **Backup parents.** A PRESENT set needs its parent to hold the retention authority files
   (`licence-ends.json`, `expiry-journal.json`); a new `--out` initialises authority only when
   `_retention_preflight` proves the database untouched, and a nonempty parent without authority is
   refused. An ABSENT set initialises nothing. So, from 0.3:
   - **Schema ABSENT:** B0 goes alone into `BK0=data/backups/equity_os-absent-<run stamp>`, which
     must not exist; no PRESENT set ever goes there. `BK=data/backups/equity_os` must not exist; its
     first PRESENT backup (B1, or a failed-state backup in (R)) initialises its authority.
   - **PRESENT, no retention history** (zero licence ends, zero EXPIRED captures, no journal-head
     file): `BK=data/backups/equity_os`, which must not exist; B0 initialises its authority.
   - **History present:** `BK` is the existing directory that past `retention purge --backup-dir`
     runs used; it must contain both authority files. Not found → STOP; never initialise new
     authority over history. Its `licence-ends.json` must list exactly the database's licence ends
     (a filed end the database lacks would be inserted by the backup's reconcile), else STOP.
   Record `BK` and `BK0` (if any) in `$C/BK.path`. Each set's own parent is `dirname` of its
   `<name>.path`.
5–6. **Baseline backup B0** (reads only; on ABSENT it records `schema_state: ABSENT`) and its
   **restore test** into a test database (`db restore` refuses non-`eqos_test_` names). Cold start:
   if 0.3 showed the roles absent, `run bootstrap 0 uv run fundamentals db bootstrap` between the
   two lines (roles and logins only, after B0 is published). A missing purge-login credential file
   makes restore exit 2 (`RoleSecretError`) → STOP.

   ```bash
   backup B0 "${BK0:-$BK}"; is_done 0.5 || done_step 0.5
   restore B0; done_step 0.6
   ```

   Exit 0 is the pass (`RestoreCheck.ok` is not serialized; the CLI exits 0 only when it holds).
   `$C/restore-B0.out` is the check's JSON: `counts_equal`, `schema_equal`, `run_ids_equal`,
   `fk_valid`, `faithful`, `delta_ok` true and every mismatch list empty. `counts_equal` compares
   the restored database with `B0`'s `manifest.yaml` before purge-first; the manifest counts match
   0.3.

### (R) Production recovery procedure — defined now, executed only on need

Run only on a STOP after an IRREVERSIBLE step that forward repair cannot fix, by the orchestrator's
written ruling in `$C/recovery.md` under the 2026-10-20 authorization. The set is chosen from the
table at the end of this file. **Data-loss boundary:** every write after the set, all of it cutover
writes because the maintenance window holds.
1. Keep writers stopped (maintenance window).
2. Preserve the failed state: `backup failed-<step> "$BK"` if it still succeeds; it is never deleted.
3. `restore <set>`, with `--replay-runs` where the set has runs (not an ABSENT `B0`); it must exit 0.
   This is the faithful-restoration proof: pre-purge `counts_equal`, plus `delta_ok` (purge-first
   added exactly its reported retention rows: always one `purge_runs` and at least one
   `purge_run_closures` row).
4. **Swap**, on an admin connection to the `postgres` maintenance database, autocommit, with
   `pg_stat_activity` showing no session on either database. Before the first rename, write
   `$C/recovery-swap.txt` (noclobber) with `SET`, `TARGET=eqos_test_cutover_<set>_<n>` (the
   accepted restore), `FAILED=equity_os_failed_<UTC stamp>` and the `pg_database.oid` of
   `equity_os` and of `TARGET`. Each (re)entry reads `pg_database` and acts only when every
   existing name carries its recorded oid:

   | Names present | Stage | Action |
   |---|---|---|
   | `equity_os`, `TARGET` | neither done | `ALTER DATABASE equity_os RENAME TO <FAILED>;` |
   | `FAILED`, `TARGET` | first done | `ALTER DATABASE <TARGET> RENAME TO equity_os;` — if it fails and cannot be retried, `ALTER DATABASE <FAILED> RENAME TO equity_os;` and STOP |
   | `equity_os` (target oid), `FAILED` | both done | step 5 |
   | anything else, or an oid mismatch | — | STOP |

   Both databases are always kept. `$SNAP` is untouched (append-only; captures written after the
   set stay as unreferenced files) and each parent keeps its role.
5. Validate before any writer. ABSENT `B0`: the 0.3 probe reports `current_database()=equity_os` and
   `schema: ABSENT`; roles are cluster-wide and survive, so the continuation is Step 1. Otherwise the
   probe's pins equal the set's; its table counts equal the set manifest's except for rows added
   to `purge_runs`, `purge_run_closures`, `licence_ends`, `capture_states` and `purge_records` (the
   purge-first delta `delta_ok` verified); `legacy status` shows the set's state; and
   `backup recovered "$BK"` plus `restore recovered` pass. `recovered` is the new baseline.
6. **New run record.** Continue in a new run directory `$C'`; `$C/recovered.md` names it and `$C`
   stays as evidence of the discarded writes. Copy into `$C'` (`cp -pL`) only what the set still
   makes true. `B0`: the Step 0 baselines (`quiesce.txt`, `originals.before.sha256`,
   `aparinds.sqlite.bak`, `preflight-inventory.out`, `BK.path`, `rehearsal-reconciliation.yaml`),
   `B0.path` (PRESENT: `recovered.path` as `B0.path`), and a `state.log` of `0.5`, `0.6`; every
   later run id, approval, owner record and diff is void and is redone. `B1`: additionally `$M`, the approved
   `preflight.yaml`, `owner-import.yaml`, the approved `reconciliation.yaml`, `owner-transition.yaml`,
   the accepted `ingest-*`/`compare-*` outputs, `diff/`, `recovered.path` as `B1.path`, and the
   `state.log` ids through `6.3`. Then continue at `resume_branch`.

## Step 1 — Migrations up to 0041, issuer identity — IRREVERSIBLE (forward-only DDL)

- `ls migrations | tail -1` must be `0041_memory_natural_key.sql`; no `0042` exists.
- Schema ABSENT: `run bootstrap 0 uv run fundamentals db bootstrap` (if not run in 0.6).

```bash
run migrate 0 uv run fundamentals db migrate
[ "$(head -c 8 "$C/migrate.out")" = $'applied\t' ] || stop "migrate output"
run seed-identity 0 uv run python -c "
import psycopg
from pathlib import Path
from fundamentals.pg.identity_seed import load_issuer_identity, seed_issuer_identity
from fundamentals.pg.settings import PgRole, PgSettings
with psycopg.connect(PgSettings().conninfo(PgRole.RUNTIME)) as conn:
    identity = load_issuer_identity(Path('config/identity/aparinds.yaml'))
    print(seed_issuer_identity(conn, identity).model_dump_json())"
run preflight-after-migrate 0 uv run python scratchpad/cutover/preflight.py
```

`seed_issuer_identity` is idempotent (insert-or-find per row, one transaction) and runs whatever
0.3 showed: an APARINDS entity seeded from the entity map lacks the fiscal-year-end setting that
ingest requires. Before `done_step 1` the operator confirms in `preflight-after-migrate.out`: 41
migration rows, every sha matching; APARINDS with its NSE and BSE listings and exactly one
`FISCAL_YEAR_END_MONTH` value, equal to the identity file's; then `done_step 1`. Otherwise STOP.

## Step 2 — Decisions for the two open D2 runbook issues

- **`snapshot_root`** in `config/legacy_import_manifest.yaml` (`data/raw/snapshots/v1`) is kept byte
  for byte: the importer reads bound originals only through it (`legacy_import._bindings_hold`)
  and `db backup` takes one root, so Step 3 ingests the 8 originals under `$SNAP`. Proof:
  `unresolved_originals: []` in preflight, every bound `capture_ref_id` re-hashing under `$SNAP`
  (0.3/3.2), `verify_import` passing, B1 archiving them. FY26 `results` and `press-release` share
  one sha per quarter, so `--member pdf=results` registers all 4 PDF originals.
- **D2 step 10** (`fundamentals run` on a past quarter) is refused by design and not attempted;
  no cutoff is rewritten. Its replacement is B1's replay restore (6.3) and the routing check (7.2).

## Step 3 — Register originals, legacy import, reconcile

1. Writers are already frozen (0.1).
2. **Ingest the PQ0–PQ3 packages (XBRL and results PDF) under the pilot pins.** These are the fresh
   extraction and they register the 8 originals the import binds, so they run first. **IRREVERSIBLE.**

   ```bash
   for q in FY26_Q2:2025-09-30:fy26-q2 FY26_Q3:2025-12-31:fy26-q3 FY26_Q4:2026-03-31:fy26-q4-pg FY27_Q1:2026-06-30:fy27-q1-pg; do
     IFS=: read -r Q END CFG <<<"$q"; is_done "3.2:$Q" && continue
     run "ingest-$Q" "0 4" uv run fundamentals evidence ingest \
       --retrieval-manifest "$APAR/retrieval-manifest-v2.json" --issuer APARINDS --quarter "$Q" \
       --period-end "$END" --basis consolidated --raw-root "$APAR" --snapshot-root "$SNAP" \
       --member xbrl=xbrl-consolidated --member pdf=results \
       --issuer-config "config/aparinds-$CFG.yaml" --dictionary v2 --mapping-set v6
     run "ingest-check-$Q" 0 uv run python scratchpad/cutover/diff_legacy_fresh.py \
       --check-ingest "$Q:$END" --issuer-config "config/aparinds-$CFG.yaml"
     done_step "3.2:$Q"
   done
   ```

   Exit 0 is expected. **Exit 4 (`INCOMPLETE`)** is accepted only as retained incomplete evidence
   where both member generations are still usable (e.g. PQ3's unlocated segment block inside a
   COMPLETE PDF, `eqos-ghv`). `--check-ingest` (after either exit, before `done_step`) applies Step
   5's binding read-only to that quarter's APARINDS consolidated package and exits nonzero unless:
   the XBRL and PDF captures are both in the package, each with a reusable COMPLETE generation;
   the XBRL has at least one MAPPED interpretation; and every remaining failure is a PDF family
   failure inside that COMPLETE generation. A whole-PDF `PARSE_FAILED` (or any other non-COMPLETE
   member) is a STOP; so is any other ingest exit. Full incomplete reasons come from the stored
   attempts, not the short output lines. Then hash `$APAR` again: `$C/originals.after.sha256` equals
   the before file; `done_step 3.2`.
3. **Manifest copy.** `$M` is unapproved until `3.3` is logged, so a copy left by an interruption
   is replaced:

   ```bash
   cp config/legacy_import_manifest.yaml "$M"; cmp config/legacy_import_manifest.yaml "$M" || stop "manifest copy"
   done_step 3.3
   ```
4. Preflight, Sol round A, owner record, import. The import is **IRREVERSIBLE** (immutable rows).

   ```bash
   run legacy-preflight 0 uv run fundamentals legacy preflight --manifest "$M" --out "$C/preflight.yaml"
   # $C/legacy-preflight.out is exactly: preflight<TAB>$C/preflight.yaml<TAB>True
   ```

   **Sol round A** (`gpt-6.1-sol`, high) reviews `$M` and `$C/preflight.yaml`; its `approval:` line
   goes onto these copies only. The orchestrator then writes `$C/owner-import.yaml`:

   ```yaml
   # owner chat authorization PavanMV 2026-10-20: orchestrator writes this record
   {by: PavanMV, date: 2026-10-20, database: equity_os, operations: [IMPORT],
    approved_payload_sha256: <preflight payload sha>}
   ```

   ```bash
   run legacy-import 0 uv run fundamentals legacy import --manifest "$M" \
     --preflight "$C/preflight.yaml" --owner "$C/owner-import.yaml"
   done_step 3.4
   # expect: imported<TAB>sqlite-cb02b0f12a1708d0<TAB>rows=43<TAB>selections=24<TAB>created=True
   ```
5. **Reconcile:** `run reconcile 0 uv run fundamentals legacy reconcile --manifest "$M" --out
   "$C/reconciliation.yaml"`; the output line ends `equal=True`. Compare it with
   `$C/rehearsal-reconciliation.yaml` on this **portable projection** only (both originals are kept):
   `translation_version`, `translation_sha256`, and per store `label`, `store_id`, `check`,
   `fingerprint_before`, `fingerprint_after`, bindings as sorted `(file_sha256, blob_sha256)`, and
   cutoffs as `(cutoff, rows, rows_sha256, equal)`. Not compared: `database`, `legacy_stores`
   (database-wide inventory) and `capture_ref_id`, which is database-local; instead each production
   `capture_ref_id` must be a `$SNAP`-verified registration of that `blob_sha256` (2a). Any
   projection difference is a STOP. Then `run status 0 uv run fundamentals legacy status --manifest
   "$M"`; its line shows state `IMPORTED`. `done_step 3.5`.

## Step 4 — Fresh compare runs, PQ0–PQ3 — IRREVERSIBLE (append-only runs)

```bash
for q in FY26_Q2:2025-09-30 FY26_Q3:2025-12-31 FY26_Q4:2026-03-31 FY27_Q1:2026-06-30; do
  Q=${q%%:*} END=${q#*:}; is_done "4:$Q" && continue
  run "compare-$Q" "0 3 4" uv run fundamentals compare run --entity APARINDS --period-end "$END" \
    --basis consolidated --dictionary v2 --mapping-set v6 --alignment-rules v2
  done_step "4:$Q"
done
```

Each `compare-$Q.out` is `run<TAB>id`, `status<TAB>…`, `created<TAB>true|false`; the diff script reads them (Step 5).
Exit 0 or 3 is recorded. **Exit 4 is accepted only for a quarter whose ingest was an accepted exit 4**
(the same retained incomplete evidence); its unavailable-source reasons are kept and reported. Exit 4
elsewhere, 5 or 2 is a STOP. The six-role expectation (`eqos-4j2.33`: the six roles `AGREE` in each
quarter) is checked by the diff script from the runs' stored results, separately from the exit code;
a miss is reported, not fixed here. Comparator XBRLs and vendor runs belong to the pilot (`eqos-4j2.8`).

## Step 5 — Deterministic diff: legacy facts vs fresh extraction

**Script:** `scratchpad/cutover/diff_legacy_fresh.py`, a one-off audit, not product code. It reads
on one connection in one `REPEATABLE READ, READ ONLY` transaction, computes in exact `Decimal` with
no tolerance and no rounding; no model computes a number.

```bash
run diff-a 0 uv run python scratchpad/cutover/diff_legacy_fresh.py --store sqlite-cb02b0f12a1708d0 \
  --run-dir "$C" --out "$C/diff"
run diff-b 0 uv run python scratchpad/cutover/diff_legacy_fresh.py --store sqlite-cb02b0f12a1708d0 \
  --run-dir "$C" --out "$C/diff-repeat"
diff -r "$C/diff" "$C/diff-repeat" >/dev/null || stop "diff not reproducible"
done_step 5
```

- **Inputs, validated first** (any failure exits nonzero before output): the four `compare-$Q.out`
  run ids, each run's primary selected `run_inputs` `PACKAGE` row (the one at its requested period
  end; supporting packages the resolver also selects, e.g. FY26_Q3's for FY26_Q4, are permitted)
  resolving to that period end's APARINDS consolidated package, whose XBRL and PDF captures are the `$SNAP`-verified registrations of that
  quarter's originals; the pins (dictionary `v2`, mapping set `v6`, and the current
  `normalisation_policy_version` and per-representation `extractor_version`, as in 0.3); the
  baseline-id sections of `preflight-inventory.out`. An id in the baseline is reused evidence, any
  other was created by this cutover; no timestamp is used.
- **Legacy side:** all 43 `eqos.fact_rows` of `STORE`, joined to `legacy_fact_translations` and
  `legacy_evidence_bindings`; each row keeps its handle as `legacy_row_id`. Value:
  `legacy_base = Decimal(normalized_value) * Decimal(scale)` (`scale` is a positive multiplicative
  factor, not an exponent) for the supported units `INR crore` (scale 10000000) and `INR per share`
  (scale 1); the unit fixes the row's kind and currency (INR). Source: `file_sha256`,
  `anchor`, revision ordinal, `canonical_status`; representation from the original.
- **Fresh side, bound to the ingested generation.** Per quarter and member, the current occurrence
  set comes from the ingest's reuse path (`first_party_extract.extract_member` inside the read-only
  transaction, so an attempted write fails the script); for the PDF it binds attempts to
  `extraction_context_sha256 = pdf_statement_specs_sha256` of that quarter's `--issuer-config`.
  No reusable complete generation → exit nonzero. Selected, under those pins and scope APARINDS
  CONSOLIDATED: `DIRECT` interpretations whose `occurrence_id` is in the set, `CONSTRUCTED` ones
  whose operands all are (`first_party_ingest._interpretations`), unsuperseded within that
  population; all statuses and periods. Each keeps `interpretation_id`, `value` (base units),
  `currency`, `value_kind`, capture blob sha, and `occurrence_id` plus locator (`DIRECT`) or
  `construction_rule_id` plus operand ids (`CONSTRUCTED`).
- **Keyed comparison** (MAPPED fresh rows and legacy rows with a supported unit): key = quarter
  (from the original), representation, `canonical_id`, `period_start`, `period_end`,
  `period_instant`, `basis`, `value_kind`, `currency`, `dimension_hash`. A kind or currency
  disagreement therefore lands on two keys, reported `LEGACY_ONLY` and `FRESH_ONLY`. Status per key:
  - `EQUAL` (`fresh_base == legacy_base`);
  - `DIFFERS`, with both original values and units, both base values and
    `delta = fresh_base − legacy_base` labelled with the comparison unit (`INR` or `INR per share`);
  - `LEGACY_ONLY`; `FRESH_ONLY`;
  - `MULTIPLE_FRESH`: more than one fresh row on a key; every fresh row is paired against every
    legacy row on the key (or none), each pair with its own status. Multiplicity is reported, never
    resolved.
- **Keyless diagnostics:** a legacy row with an unsupported unit is its own row `UNIT_MISMATCH`
  (raw value and unit shown, nothing converted). Fresh `UNMAPPED`, `PERIOD_AMBIGUOUS` and `INVALID`
  rows are each their own row `FRESH_NOT_MAPPED` with status, `reason`, raw label, period, unit and
  locator as stored; no canonical concept is invented.
- **Ordering and coverage:** rows sort by (key with nulls as empty, `legacy_row_id`,
  `interpretation_id`). The script asserts that the set of `legacy_row_id`s in the output equals the
  43 legacy rows and the set of `interpretation_id`s equals the selected fresh rows (a repeated
  reference under `MULTIPLE_FRESH` is allowed), and that each key yields max(1, legacy rows) ×
  max(1, fresh rows) output rows; a drop or extra exits nonzero.
- **Outputs:** `$C/diff/diff.csv`; `$C/diff/summary.md` (script-computed counts per quarter × status
  with current and comparative columns split, the run ids, pins, reused/created evidence, ingest and
  compare INCOMPLETE reasons, and the six-role `AGREE` check per quarter); `$C/diff/inputs.sha256`.
  No wall-clock time in any body.
- **File-only checks** (`scratchpad/cutover/test_diff.py`, pytest, no database): the real crore
  example (legacy `5479.73` INR crore, scale `10000000` → `54797300000` INR, `EQUAL` to a fresh
  `54797300000`), an `INR per share` example, a null-key `UNMAPPED` row, two fresh rows on one key,
  an unsupported unit (`UNIT_MISMATCH`), a currency disagreement on otherwise equal keys (one
  `LEGACY_ONLY`, one `FRESH_ONLY`), a `CONSTRUCTED` row's provenance, an older PDF location context
  under the same version pins whose interpretations are excluded, and for `--check-ingest` a
  COMPLETE PDF with one failed family (accepted) beside a whole-PDF `PARSE_FAILED` member
  (rejected). All pass before 3.2 runs.

## Step 6 — Sol review, cutover marker, new-state proof

1. **Sol round B** (fresh `delegate_task`, `reasoningEffort: high`) receives `$C/reconciliation.yaml`,
   `rehearsal-reconciliation.yaml`, `preflight.yaml`, the `ingest-*`/`compare-*` outputs, `exits.log`,
   `diff/`, the diff script and its checks, and `preflight-inventory.out`. The brief carries the
   exhaustive-findings sentence from `04-agent-stack.md`. The loop runs until `APPROVE`. The approval
   line goes on `$C/reconciliation.yaml`. The orchestrator writes `$C/owner-transition.yaml`
   (`by: PavanMV`, `operations: [CUTOVER, REOPEN, ROLLBACK]`, that payload's sha, the same comment).
2. **Cutover marker** (reversible inside the window):

   ```bash
   run cutover 0 uv run fundamentals legacy cutover --manifest "$M" --report "$C/reconciliation.yaml" \
     --owner "$C/owner-transition.yaml"
   done_step 6.2
   ```

   It writes the `CUTOVER_FROZEN` event; `legacy status` shows `CUTOVER_FROZEN`.
3. **B1 and its replay proof, before reopen:**

   ```bash
   backup B1 "$BK"; restore B1 --replay-runs; done_step 6.3
   ```

   Exit 0 with `restore-B1.out`'s JSON showing `replay_mismatches` empty for the four compare runs.
   A failure is a STOP while rollback is still available.
4. **Rollback window:** from the cutover event until `legacy reopen`; the maintenance window holds.
5. **Rollback steps** (on a STOP inside the window):
   1. `run rollback 0 uv run fundamentals legacy rollback --manifest "$M" --report
      "$C/reconciliation.yaml" --owner "$C/owner-transition.yaml"`.
   2. `legacy status` shows `ROLLED_BACK`.
   3. `sha256sum data/store/aparinds.sqlite` equals `LEGACY_SHA`; then `chmod u+w` the file.
   4. Never open the file through `FactStore` before a re-cutover attempt: opening it migrates it,
      and cutover is then refused `FINGERPRINT_CHANGED`; the way out is a re-import with
      `new_import: true` in a new manifest copy, approved again.

   The PostgreSQL ingests, compare runs and imported rows stay (append-only, harmless). After
   rollback only `aparinds-fy26-q4.yaml` (`store_db`) runs; the `fact_store_id` configs raise
   `FactStoreRequiredError`.

## Step 7 — Reopen and post-cutover check

1. **Reopen — IRREVERSIBLE: closes the rollback window.** Only after Sol `APPROVE` (6.1), `6.3` in
   `state.log`, and status `CUTOVER_FROZEN`:

   ```bash
   run reopen 0 uv run fundamentals legacy reopen --manifest "$M" --report "$C/reconciliation.yaml" \
     --owner "$C/owner-transition.yaml"
   done_step 7.1
   ```
2. **Checks**, all required; a failure is recovered by (R) from `B1`, which restores
   `CUTOVER_FROZEN` and with it the rollback choice:
   - `run status-open 0 uv run fundamentals legacy status --manifest "$M"` shows `OPEN`.
   - `run reconcile-post 0 uv run fundamentals legacy reconcile --manifest "$M" --out
     "$C/reconciliation-post.yaml"`; the file is byte-equal to the approved payload (the
     reconciliation without its `approval:` line).
   - `run routing 0 uv run python scratchpad/cutover/routing_check.py` (about 25 lines):
     `open_fact_store(STORE, None, pool_factory=...)` is a `PgFactStore`; at the reconciliation's last
     cutoff it rebuilds the sorted `(row_id, content_identity, value_hash, selection_id,
     selection_sha256)` tuples from `query_canonical(cutoff=...)` and `get_selection_history` (as
     `cutover._sqlite_rows` does), and `sha256(json.dumps(rows))` equals that cutoff's `rows_sha256`
     with `rows` = 24.
   - `backup B2 "$BK"; restore B2 --replay-runs` exits 0. `done_step 7.2`.
3. End the maintenance window: no more `chmod`; writers may resume.
4. Hand off with the orchestrator's `bd` notes on `eqos-3zl`: `$C`, run ids, diff summary counts and
   Sol verdicts. `eqos-4j2.8` is unblocked. The owner reads `$C/diff/summary.md` afterwards.

## Irreversible points and recovery sets

| Step | Effect | Recovery set |
|---|---|---|
| before 1 | nothing changed | none needed |
| 1 | Migrations to 0041; APARINDS identity seed | `B0` via (R) |
| 3.2 / 4 | Ingest and compare runs (append-only) | `B0` via (R) |
| 3.4 | Legacy import (immutable rows) | `B0` via (R) |
| 6.3 onwards | `B1` is `CUTOVER_FROZEN`, so recovery to it reopens the rollback window | `B1` via (R) |
| 7.1 | Reopen: rollback window closed, PostgreSQL authoritative | `B1` via (R) |

Reversible: chmod (0.1) and cutover (6.2, by `legacy rollback` until reopen).
