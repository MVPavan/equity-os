# Docs Index

Authoritative docs and when to read them.

| Doc | Read when |
|---|---|
| `docs/blueprint/funda-blueprint-final-consolidated-review.md` | **First for any product/architecture question** — approved direction, doctrine, first-release contract (§7), decisions to freeze (§8) |
| `docs/blueprint/funda-blueprint-implementation-decision-register.md` | Checking what is decided vs open — every decision has an ID (A-01…E-09), acceptance evidence, and status; phase-gate scorecard in §F |
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
