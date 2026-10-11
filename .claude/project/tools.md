# Tools & Subagents

## Runtimes & tooling (verified on this machine, 2026-08-12)

| Tool | Version / note | Used for |
|---|---|---|
| Python | 3.12.3 | intended product language (no package yet) |
| `uv` | 0.9.8 | package/env manager once `pyproject.toml` exists — never `pip`/`poetry` |
| `bd` (beads) | 1.1.0, embedded Dolt | issue tracking (see `tracking.md`) |
| `codex` CLI | 0.147.0, on PATH | Codex critique/review path is live |

Tool versions above are from 2026-08-12; current: codex-cli 0.162.0, bd 1.3.0.

## Agent stack

Workers and reviewers run through the T3 Code orchestrator under the fixed stack in
`.claude/rules/core/04-agent-stack.md` (Opus 5.5 medium / Sonnet 5.5 medium implement,
GPT-6.1 Sol high reviews). The old codex-adapter plugin path no longer exists; do not use it.

## Web research: DWS (deep web search)

Owner's local evidence tool (owner directive 2026-10-11). Use it for **open-ended web research**:
general/news searches, equity news, anything not covered by a dedicated source. Use the dedicated
acquisition lanes (Screener, Tijori, Upstox, NSE/BSE filings) for their own data — DWS does not
replace them.

- Runs as local Docker services; API on `127.0.0.1:8765` (`/ready` reports status, MCP enabled).
- CLI: from the owner's DWS product checkout (the `dws/` directory holding `compose.yaml`), load
  `.runtime/owner.env`, then `uv run --no-sync dws search "<query>" --limit N`; `fetch`, `read`,
  `retrieve`, `pin`, `crawl` per its `docs/host-integration.md`.
- Use a separate DWS workspace per project scope (e.g. `equity-os`). Cite by `snapshot_id` plus
  returned line/char locations; re-`read` the snapshot to verify a quote.
- Search ranking is provider order, not credibility — select and evaluate a source before treating
  it as evidence. Never put `DWS_TOKEN` in reports, prompts, or committed files.

## Subagent / MCP routing

- **`docs-researcher`** subagent + **`context7`** MCP — library/SDK/API/CLI
  facts; prefer over web search for library docs; never invent APIs. Will
  matter heavily once ingestion/parsing libraries are chosen.
- Implementation and review dispatch: see `04-agent-stack.md` (supersedes the
  native implementer / code-reviewer / spec-reviewer routing). Planning still lives
  in the `planning` skill.
- Use **brainstorming** for open-ended design tradeoffs; the blueprint's open
  decisions (register items with status Open) are the natural inputs.

`.claude/rules/python/` matches the confirmed stack (uv, Pydantic, ruff,
mypy --strict, pytest, structlog) — apply them to all first-party code.
