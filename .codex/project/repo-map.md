# Repository Map

Top-level layout and how to navigate. The repo is pre-code: harness + blueprint
docs only.

| Path | What it is |
|---|---|
| `docs/blueprint/` | The product docs: `funda-blueprint-implementation-decision-register-v2.md` (**canonical** decisions/gates), `funda-blueprint-final-consolidated-review.md` (architecture rationale), `funda-third-order-review-disposition-report.md` (why v2 changed), and the superseded v1 register |
| `.codex/` | Codex-native harness: `skills/`, `agents/`, `hooks/`, `rules/`, `docs/`, project overlay, and the existing Beads-generated config/hook registrations |
| `.claude/` | Preserved legacy/source Claude harness; do not delete or edit as part of Codex migration work |
| `.beads/` | Beads issue tracker (embedded Dolt, db `equity_os`, prefix `equity-os`) + `beads.md` workflow doc |
| `.agents/` | bd-generated OpenAI-agent beads skill — not hand-maintained |
| `CLAUDE.md` / `AGENTS.md` | Always-loaded entry points (harness-installed) |
| `CONTEXT.md` | Domain glossary — use its terms in issues, docs, and code |

Not yet present (expected as work starts): first-party `src/`, `pyproject.toml`,
tests, `docs/specs/`, `docs/workstreams/`, `scratchpad/`.

## Orientation

- To understand the product: read `docs/blueprint/funda-blueprint-final-consolidated-review.md`
  §1–2 (verdict + what to preserve), §7 (first release), §8 (decisions to freeze).
- To find what is decided vs open: the **v2** decision register — every item
  has an ID (A-01…E-10), priority, acceptance evidence, dependencies, status.
- To find actionable work: `bd ready`.
- Phase order: 0A (freeze decisions + XBRL/PDF spike) → 0.5 (one company ×
  four quarters: Q0 baseline + 3 assisted updates) → 1 (2–3-company MVP) →
  later phases gated by measured value.
