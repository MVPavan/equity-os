# Verification

The `equity-os` uv project (`pyproject.toml` at the repo root) has a real test gate,
below. The structural gate still applies to non-Python and non-product changes.

## Structural gate (run what applies to your change)

1. **Working tree** — `git status` shows only the files you intended to change;
   no `scratchpad/`, no machine-local paths.
2. **JSON/YAML config** — changed `.json` parses
   (`python3 -m json.tool <file> >/dev/null`); changed `.yaml` loads
   (`python3 -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]))" <file>`).
3. **Python scripts** — for any changed `.py`, `python3 -m py_compile <file>`.
4. **Beads** — `bd ready` / `bd list` run without error after task changes.
5. **Doc links** — repo-relative paths referenced in changed docs actually exist.
6. **Codex harness** — after changing migrated harness assets, run
   `python3 .codex/skills/migrate-claude-to-codex/scripts/migrate_claude_to_codex.py verify --repo .`.
   When hooks or `.rules` change, also exercise representative allow/block
   fixtures and confirm `codex execpolicy check` reports the intended match.

## Fundamentals product (`pyproject.toml` at repo root)

- `uv sync`
- `uv run ruff check equity_os tests/equity_os` and
  `uv run ruff format --check equity_os tests/equity_os`
- `uv run mypy --strict equity_os`
- `uv run pytest tests/equity_os`

Scope ruff/pytest to owned paths; `scripts/verify.sh gate <slice>` runs these four plus the
pipeline checks. The authoritative copy is `.claude/project/verification.md`.

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
`uv run pytest tests/equity_os` and `scripts/verify.sh gate` therefore need the compose
service up.

No completion claim without fresh evidence: run the command, read the output
and exit status, report the actual result.
