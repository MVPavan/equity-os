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
| `docs/research/pdf-extraction-bakeoff.md` | Building or changing document extraction — measured verdicts on PageIndex, the scanned-page vision lane, deterministic table extraction, and XBRL/EDGAR tooling, plus the proposed pipeline contract |
| `docs/research/screener/surface-map.md` | Any Screener (Phase 2) work — owner-validated map of every subscriber surface with exact site names, URLs, APIs, the two company-id namespaces, redirect-to-BSE facts, and the observed 429 rate limit |
| `docs/research/screener/industry-classification.md` | Sector/industry mapping — Screener's full 4-tier classification tree (12/22/58/188) with codes and counts |
| `docs/research/screener/ratio-library.md` | Writing or parsing Screener queries/columns — all 374 field names usable in `/screen/raw/?query=` and Manage columns |
| `docs/research/upstox-api-surface-inventory.md` | **Any Upstox work — the authority.** Full endpoint surface organized on Upstox's own doc tree, with CORE/MAYBE/EXCLUDE, access tier, and a confidence grade per row (A = verified live). Records why the six statement/ratio fundamentals endpoints are refused. |
| `docs/research/upstox-api-schemas/` | Writing any Upstox parser — six per-sector schema files verified field-by-field against 129 live responses, plus `VERIFICATION.md` ranking the traps that break a strict parser. `instruments.md` carries a 2026-09-04 corrections block: `instrument_type` is NOT the equity discriminator (the ISIN is), and filtering on it silently dropped two of ten pinned stocks. `fundamentals.md` carries a 2026-09-04 **Lane B live verification** block (29 live GETs) — an invalid ISIN is indistinguishable from an empty company, `full_statement` stays annual under `time_period=quarterly`, and the summary and full blocks of one payload can disagree |
| `docs/research/upstox-integration-plan.md` | **Implementing Upstox — the plan of record (v2).** Module layout, contracts, five ordered slices with acceptance tests, open decisions and ranked risks. Leads with the verified traps that silently corrupt data (`to_date` before `from_date`, most-recent-first rows, `dd Mon yyyy` dates, `SEGMENT\|ISIN` keys). Supersedes the v1 draft in `scratchpad/` |
| `docs/research/upstox-rights-record.md` | **Before any live Upstox call.** The Gate 0 rights record, `PROPOSED` and unapproved: what the terms actually say (quoted, with the phrases that are absent), the unresolved question of whether the website ToU governs the developer API, and the finding that the unauthenticated instrument files are the *least* covered surface, not the most. Every `UNKNOWN` denies its operation |
| `docs/research/upstox-api-evaluation.md` | Historical — the 2026-08-24 pre-token evaluation. Partly superseded: its kill criterion fired on 2026-09-03. Read the inventory instead |

Not yet present, expected later: `docs/specs/` (brainstorming output),
`docs/workstreams/<name>/roadmap.md` (phase plans), and the smaller
implementation artifacts the review recommends (§10: `MVP-001-earnings-review.md`,
`ADR-001-system-of-record.md`, `data-contracts-v0.md`, `evaluation-plan.md`,
`provider-rights-register.md`, `dependency-due-diligence.md`).
- [Session handoff 2026-08-19](../../docs/goals/handoff/HANDOFF-2026-08-19.md) — authoritative resume point for the blueprint-completion goal (state, pending work, user decisions); architecture artifact source in docs/goals/architecture/

## Learnings

- [Financial-site scraper patterns](../../docs/learnings/financial-site-scraper-patterns.md) — earned patterns from the Tijori breadth build (2026-08-25); read before building any new source adapter (esp. Screener Phase 2).
