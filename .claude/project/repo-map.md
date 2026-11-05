# Repository Map

Top-level layout and how to navigate.

| Path | What it is |
|---|---|
| `docs/blueprint/` | The product docs: `funda-blueprint-implementation-decision-register-v2.md` (**canonical** decisions/gates), `funda-blueprint-final-consolidated-review.md` (architecture rationale), `funda-third-order-review-disposition-report.md` (why v2 changed), and the superseded v1 register |
| `.claude/` | Installed Claude harness: `rules/`, `skills/`, `agents/`, `commands/`, `hooks/`, `docs/`, `project/` overlay (this file's home) |
| `.beads/` | Beads issue tracker (embedded Dolt, db `equity_os`, prefix `equity-os`) + `beads.md` workflow doc |
| `.codex/` | **bd-generated integration config only** (`config.toml`, `hooks.json`) — *not* a Codex harness; `AGENTS.md`'s `.codex/` references are dangling (see adoption-report) |
| `.agents/` | bd-generated OpenAI-agent beads skill — not hand-maintained |
| `CLAUDE.md` / `AGENTS.md` | Always-loaded entry points (harness-installed) |
| `CONTEXT.md` | Domain glossary — use its terms in issues, docs, and code |
| `equity_os/` | The product package in 11 buckets (`contracts`, `storage`, `coverage`, `companies`, `sourcing`, `extraction`, `normalisation`, `verification`, `analysis`, `publication`, `interface`). Every bucket and sub-bucket has a `README.md` saying what it handles; start there. Commands: `eqos`, `eqos-operator` |
| `config/` | Product config, one folder per bucket (`config/<bucket>/...`); `config/runs/` holds per-run configs. `config/sourcing/sources.yaml` lists every source |
| `tests/equity_os/` | Tests mirroring `equity_os/<bucket>/<sub-bucket>/`; shared helpers in `tests/equity_os/support/`. Fixtures stay at `tests/fundamentals/fixtures/` (frozen manifests name those paths) |
| `migrations/` | Ordered PostgreSQL migrations |
| `scripts/` | `verify.sh` (the gate), `verify_project.sh`, `render_dashboard.py`; `restructure/` holds the RESTRUCTURE-1 move map and script until the `research-4` replay |

Paths before RESTRUCTURE-1 (the old `src/` package, flat `config/` files, the old test folder) map to
today's through `docs/history/restructure-1-moves.tsv`; historical specs, plans and evidence keep the
old paths.

## Orientation

- To understand the product: read `docs/blueprint/funda-blueprint-final-consolidated-review.md`
  §1–2 (verdict + what to preserve), §7 (first release), §8 (decisions to freeze).
- To find what is decided vs open: the **v2** decision register — every item
  has an ID (A-01…E-10), priority, acceptance evidence, dependencies, status.
- To find actionable work: `bd ready`.
- Phase order: 0A (freeze decisions + XBRL/PDF spike) → 0.5 (one company ×
  four quarters: Q0 baseline + 3 assisted updates) → 1 (2–3-company MVP) →
  later phases gated by measured value.
