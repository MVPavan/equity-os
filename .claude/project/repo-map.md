# Repository Map

Top-level layout and how to navigate. The repo is pre-code: harness + blueprint
docs only.

| Path | What it is |
|---|---|
| `docs/blueprint/` | The two authoritative product docs: `funda-blueprint-final-consolidated-review.md` (architecture + product judgment) and `funda-blueprint-implementation-decision-register.md` (trackable decisions, spikes, phase gates) |
| `.claude/` | Installed Claude harness: `rules/`, `skills/`, `agents/`, `commands/`, `hooks/`, `docs/`, `project/` overlay (this file's home) |
| `.beads/` | Beads issue tracker (embedded Dolt, db `equity_os`, prefix `equity-os`) + `beads.md` workflow doc |
| `.codex/` | **bd-generated integration config only** (`config.toml`, `hooks.json`) — *not* a Codex harness; `AGENTS.md`'s `.codex/` references are dangling (see adoption-report) |
| `.agents/` | bd-generated OpenAI-agent beads skill — not hand-maintained |
| `CLAUDE.md` / `AGENTS.md` | Always-loaded entry points (harness-installed) |
| `CONTEXT.md` | Domain glossary — use its terms in issues, docs, and code |

Not yet present (expected as work starts): first-party `src/`, `pyproject.toml`,
tests, `docs/specs/`, `docs/workstreams/`, `scratchpad/`.

## Orientation

- To understand the product: read `docs/blueprint/funda-blueprint-final-consolidated-review.md`
  §1–2 (verdict + what to preserve), §7 (first release), §8 (decisions to freeze).
- To find what is decided vs open: the decision register — every item has an ID
  (A-01…E-09), priority, acceptance evidence, and status.
- To find actionable work: `bd ready`.
- Phase order: 0A (freeze decisions + XBRL/PDF spike) → 0.5 (one company ×
  three quarters) → 1 (2–3-company MVP) → later phases gated by measured value.
