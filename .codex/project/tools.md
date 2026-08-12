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

Codex is the native runtime and the authenticated `codex` CLI is available for
live discovery or explicitly isolated runs. Follow
`.codex/skills/use-codex/SKILL.md` for inline, subagent, role, and CLI routing.
Independent review remains best-effort: retry a capacity failure once, report a
skip, and omit it for `small` tasks unless risk is unusual.

## Subagent / MCP routing

- **`docs-researcher`** — current library/SDK/API/CLI facts from primary
  sources; use repository-configured documentation tools when available and
  never invent APIs.
- **implementer / code-reviewer / spec-reviewer** — core harness agents for
  bounded build → review work (reviewers follow the `code-review` skill;
  planning lives in the `planning` skill, dispatch in `execution`).
- Use **brainstorming** for open-ended design tradeoffs; the blueprint's open
  decisions (register items with status Open) are the natural inputs.

`.codex/rules/python/` matches the confirmed stack (uv, Pydantic, ruff,
mypy --strict, pytest, structlog) — apply them to all first-party code.
