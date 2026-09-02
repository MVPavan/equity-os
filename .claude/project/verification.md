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
- `uv run pytest tests/fundamentals`

Scope ruff/pytest to owned paths: a bare `uv run ruff check` / `uv run pytest`
also scans pre-existing non-`fundamentals` files (`.codex/`, `scripts/`, and
the `equity_os_blueprint` ledger tests, which have a known content hash-drift
failure) that are outside this product's scope. The structural gate above still
applies to non-Python and non-`fundamentals` changes.

`scripts/verify.sh gate <slice>` runs exactly these four commands plus the
red-proof, skip-guard, diff-coverage, and security-rail checks, and prints a
bounded report with a routing exit code. Prefer it over running the four by
hand during pipeline work; keep the command list here and in the script
identical. Protocol: `docs/graph-loops/v2-build-pipeline.md`.

No completion claim without fresh evidence: run the command, read the output
and exit status, report the actual result.
