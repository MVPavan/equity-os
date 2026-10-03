# Docs Index

Authoritative docs and when to read them.

| Doc | Read when |
|---|---|
| `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` | **Canonical for all implementation gates** — "single operational source of truth" for decisions (IDs A-01…E-10), acceptance evidence, dependencies, status, phase-gate scorecards (§F), and SQLite/state-table scale-up triggers (§H) |
| `docs/blueprint/funda-blueprint-final-consolidated-review.md` | Product/architecture rationale — approved direction, doctrine, first-release contract (§7); narrative only, does **not** override the v2 register |
| `docs/blueprint/funda-third-order-review-disposition-report.md` | Why v2 says what it says — disposition of the third-order audit (accepted/modified/rejected findings, document strategy) |
| `docs/blueprint/funda-blueprint-implementation-decision-register.md` | Superseded v1 register — historical reference only; use v2 |
| `docs/goals/equity-os-blueprint-completion.md` | Reviewing or activating the end-to-end blueprint-completion goal contract; apply it only after explicit activation |
| `docs/goals/equity-os-product-completion-gold.md` | Starting or resuming the user-requested product-completion run: vision acceptance, independent work lanes, current baseline, and full-product verdict |
| `docs/evidence/product-completion/handoff-2026-10-03.md` | Resuming after the owner-requested October 3 pause: committed work, verification evidence, remaining Beads and exact restart procedure |
| `docs/evidence/product-completion/vision-acceptance.md` | Latest product-completion evidence checkpoint; JSON companion binds requirements to source revisions and records unresolved scope and proof |
| `docs/evidence/product-completion/retrospective-evaluation-contract-proposal.md` | Proposed honest Apar evaluation after actual capture; requires the applicable owner decision before changing evaluation contracts |
| `docs/evidence/product-completion/retained-source-inventory.json` | Retained document paths, sizes and hashes; inventory alone does not prove durable backup or restore |
| `CONTEXT.md` | Naming anything — the domain glossary; use its terms, avoid its listed synonyms |
| `.beads/beads.md` | Beads workflow, agent context profiles, session-completion protocol |
| `.codex/project/brief.md` → `verification.md` → `invariants.md` | Orienting in a new session (standard read order) |
| `.codex/rules/core/03-ak-guidelines.md` | Coding rules that reduce common LLM mistakes |
| `.codex/rules/python/` | Writing any first-party Python (style, safety, testing) |
| `.codex/skills/use-codex/SKILL.md` | Choosing a Codex-native invocation path, role, or live capability check |
| `.codex/docs/` | Harness-shipped background (codex usage guide, beads/mlflow adoption notes) — reference only, not project facts |

Specs live under `docs/specs/`; workstream roadmaps live under
`docs/workstreams/<name>/roadmap.md`. Consult the applicable workstream for
its current build contracts rather than assuming the blueprint's proposed
artifact names exist (§10: `MVP-001-earnings-review.md`,
`ADR-001-system-of-record.md`, `data-contracts-v0.md`, `evaluation-plan.md`,
`provider-rights-register.md`, `dependency-due-diligence.md`).
