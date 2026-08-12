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
6. **Codex harness** — after changing migrated harness assets, run
   `python3 .codex/skills/migrate-claude-to-codex/scripts/migrate_claude_to_codex.py verify --repo .`.
   When hooks or `.rules` change, also exercise representative allow/block
   fixtures and confirm `codex execpolicy check` reports the intended match.

## Once first-party Python code lands

The intended stack is Python 3.12+ / `uv` (see `brief.md`). When
`pyproject.toml` exists, replace this gate with the real commands — expected
shape, to be pinned then, not assumed now:

- `uv run ruff format --check .` and `uv run ruff check .`
- `uv run mypy --strict <package>`
- `uv run pytest`

Update this file in the same change that introduces `pyproject.toml`.

No completion claim without fresh evidence: run the command, read the output
and exit status, report the actual result.
