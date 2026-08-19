# Docs Index

Authoritative docs and when to read them.

| Doc | Read when |
|---|---|
| `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` | **Canonical for all implementation gates** — "single operational source of truth" for decisions (IDs A-01…E-10), acceptance evidence, dependencies, status, phase-gate scorecards (§F), and SQLite/state-table scale-up triggers (§H) |
| `docs/blueprint/funda-blueprint-final-consolidated-review.md` | Product/architecture rationale — approved direction, doctrine, first-release contract (§7); narrative only, does **not** override the v2 register |
| `docs/blueprint/funda-third-order-review-disposition-report.md` | Why v2 says what it says — disposition of the third-order audit (accepted/modified/rejected findings, document strategy) |
| `docs/blueprint/funda-blueprint-implementation-decision-register.md` | Superseded v1 register — historical reference only; use v2 |
| `CONTEXT.md` | Naming anything — the domain glossary; use its terms, avoid its listed synonyms |
| `.beads/beads.md` | Beads workflow, agent context profiles, session-completion protocol |
| `.claude/project/brief.md` → `verification.md` → `invariants.md` | Orienting in a new session (standard read order) |
| `.claude/rules/core/03-ak-guidelines.md` | Coding rules that reduce common LLM mistakes |
| `.claude/rules/python/` | Writing any first-party Python (style, safety, testing) |
| `.claude/commands/use-codex.md` | Any Codex invocation — authoritative rules and roles |
| `.claude/docs/` | Harness-shipped background (codex usage guide, beads/mlflow adoption notes) — reference only, not project facts |

Not yet present, expected later: `docs/specs/` (brainstorming output),
`docs/workstreams/<name>/roadmap.md` (phase plans), and the smaller
implementation artifacts the review recommends (§10: `MVP-001-earnings-review.md`,
`ADR-001-system-of-record.md`, `data-contracts-v0.md`, `evaluation-plan.md`,
`provider-rights-register.md`, `dependency-due-diligence.md`).
- [Session handoff 2026-08-19](../../docs/goals/handoff/HANDOFF-2026-08-19.md) — authoritative resume point for the blueprint-completion goal (state, pending work, user decisions); architecture artifact source in docs/goals/architecture/
