# Tools & Subagents

## Runtimes & tooling (verified on this machine, 2026-08-12)

| Tool | Version / note | Used for |
|---|---|---|
| Python | 3.12.3 | intended product language (no package yet) |
| `uv` | 0.9.8 | package/env manager once `pyproject.toml` exists — never `pip`/`poetry` |
| `bd` (beads) | 1.1.0, embedded Dolt | issue tracking (see `tracking.md`) |
| `codex` CLI | 0.147.0, on PATH | Codex critique/review path is live |

Nothing to install or build yet — the repo is pre-code.

## Codex

The codex-adapter plugin is installed and `codex` is authenticated, so the
one-way critic path is live. Follow `.claude/commands/use-codex.md` for which
command/role to use. Best-effort: one retry on capacity error, then proceed and
log the skip. Skip Codex for `small` tasks.

## Subagent / MCP routing

- **`docs-researcher`** subagent + **`context7`** MCP — library/SDK/API/CLI
  facts; prefer over web search for library docs; never invent APIs. Will
  matter heavily once ingestion/parsing libraries are chosen.
- **implementer / code-reviewer / spec-reviewer** — core harness agents for
  bounded build → review work (reviewers follow the `code-review` skill;
  planning lives in the `planning` skill, dispatch in `execution`).
- **claude-max** — heaviest, most open-ended tasks.
- Use **brainstorming** for open-ended design tradeoffs; the blueprint's open
  decisions (register items with status Open) are the natural inputs.

`.claude/rules/python/` matches the confirmed stack (uv, Pydantic, ruff,
mypy --strict, pytest, structlog) — apply them to all first-party code.
