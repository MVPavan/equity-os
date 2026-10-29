# Verification

This repo currently has **no first-party application code, build, or CI**.
There are no test/lint/build commands to run for the repo as a whole, so the
health gate is **structural** — do not invent commands.

## Structural gate (run what applies to your change)

1. **Working tree** — `git status` shows only the files you intended to change;
   no `scratchpad/`, no machine-local paths.
2. **JSON/YAML config** — changed `.json` parses
   (`python3 -m json.tool <file> >/dev/null`); changed `.yaml` loads
   (`python3 -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]))" <file>`).
3. **Python scripts** — for any changed `.py`, `python3 -m py_compile <file>`.
4. **Beads** — `bd ready` / `bd list` run without error after task changes.
5. **Doc links** — repo-relative paths referenced in changed docs actually exist.

## Fundamentals product (`pyproject.toml` at repo root)

The `fundamentals` uv project (Python 3.12+) landed with Slice 0. Its gate:

- `uv sync`
- `uv run ruff check src tests/fundamentals` and
  `uv run ruff format --check src tests/fundamentals`
- `uv run mypy --strict src`
- `uv run pytest tests/fundamentals -n 8 --dist loadfile` (xdist, at most 8 workers: the machine is shared; the gate also sets
  `PYTEST_DEBUG_TEMPROOT` outside `/tmp` — see `scripts/verify.sh` `suite_pytest`)

Scope ruff/pytest to owned paths: a bare `uv run ruff check` / `uv run pytest`
also scans pre-existing non-`fundamentals` files (`.codex/`, `scripts/`, and
the `equity_os_blueprint` ledger tests, which have a known content hash-drift
failure) that are outside this product's scope. The structural gate above still
applies to non-Python and non-`fundamentals` changes.

`scripts/verify.sh gate <slice>` runs exactly these four commands plus the
red-proof, skip-guard, diff-coverage, and security-rail checks, and prints a
bounded report with a routing exit code. For a refactor slice, which has no new
behaviour to prove red, `scripts/verify.sh baseline <slice>` records the green
test set first and the gate then requires that same set back instead of a red
proof. Prefer it over running the four by
hand during pipeline work; keep the command list here and in the script
identical. Protocol: `docs/graph-loops/v2-build-pipeline.md`.

### PostgreSQL and retained-capture markers (D1a)

Two pytest markers gate what the suite needs beyond the checkout:

- `pg` — needs the compose PostgreSQL service up (`docker compose up -d postgres`) and
  `.env` complete: `EQOS_PG_HOST`, `EQOS_PG_PORT`, `EQOS_PG_DB`, `EQOS_PG_RUNTIME_PASSWORD`
  (see `.env.example`), plus `eqos_admin.login` and `eqos_migrator.login` in
  `${EQOS_SECRETS_DIR:-~/.secrets}` (bead eqos-z53). Each test gets its own `eqos_test_*` database cloned from a migrated
  template and dropped afterwards; the harness never touches `EQOS_PG_DB`.
- `retained` — reads the gitignored retained Apar originals under
  `data/raw/watchlist/aparinds/`, pinned by SHA-256.

A missing service, incomplete settings, a missing original or a hash mismatch **fails** the
test; nothing skips. The only opt-outs are `-m "not pg"` and `-m "not retained"` — say so
when reporting a run that used them, because the D1a Verify cells require both green.
`uv run pytest tests/fundamentals` and `scripts/verify.sh gate` therefore need the compose
service up.

`uv run fundamentals db check-live` (the `Live DB` row of `scripts/verify_project.sh`) is the
read-only live check: it fails naming the check unless `EQOS_PG_DB` (never `eqos_test_*`) has every
migration recorded with its sha256, the APARINDS fiscal setting and an `OPEN` legacy store.

### Stage 2 recreation check (D2)

D2 adds migrations `0010_legacy_fact_store.sql` and `0011_fact_admissions.sql`. Its exit also
needs `scripts/stage2_recreation_check.sh` to exit 0. On its own throwaway compose projects
(mktemp root, free loopback ports, isolated env, never the live project or `equity_os`) it
rehearses runbook steps 6–9 on copies (step 10's report run is covered by the e2e instead), proves an identical inventory across `down`/`up`, runs
`test_data_stage2_e2e.py` there and restores onto a fresh instance with replay.

### Panel and owner credentials (D3)

`0012_report_ledger.sql` grants to two NOLOGIN group roles, `eqos_panel` and `eqos_owner`, which
`fundamentals db bootstrap` creates if missing (run it before `db migrate` applies 0012). Ledger
commands, `compare queue dispose` and `db bootstrap` read the member logins from 0600 files
outside every runtime config, in `${EQOS_SECRETS_DIR:-~/.secrets}`: `eqos_panel.login` and
`eqos_owner.login`, each one line
`<login>:<password>` (login `[a-z_][a-z0-9_]*`; the file owned by you, no group or other
permission bits). After creating them, re-run `fundamentals db bootstrap` to create the logins;
a missing file skips that login and refuses only the commands that need it. Tests create their
own randomized logins and files in a temporary directory and never read `~/.secrets`.

No completion claim without fresh evidence: run the command, read the output
and exit status, report the actual result.
