# Equity-OS autonomous backend completion goal — 2026-10-13

Status: work resumed by owner, 2026-10-13. The paused checkpoint below is historical; formal
integration acceptance remains FAIL/STOP until the recorded fixes pass. Preparation task: `eqos-lob`.

## Resume steering — 2026-10-13

The owner explicitly requested resuming this goal. Continue normal bounded execution, beginning
with `eqos-hdz` and `eqos-490` in independent file scopes. Existing autonomy, local commit authority,
no-push rule and protected boundaries persist. The tool control currently still reports paused;
available goal tools cannot change that control to active. Work proceeds under the explicit resume
instruction without creating a replacement goal or claiming the control changed.

## Historical pause steering — 2026-10-13

The owner reported that limits reset and requested finishing already spawned work, then pausing
at a verified checkpoint. Existing schema, adapter, corroboration and offline-boundary work is
frozen and independently approved within its stated scope. Start no new implementation batch.
The final integration attempt, explicit-file commits and handoff are recorded below. The goal
tool is paused at this checkpoint. Subsequent work uses normal bounded execution only after an
explicit resume or new task.

D1a is verified complete under its disclosed four-check/tracer/review closure route; its missing
historical red proof remains missing. D1b Tasks 2–5 have an approved scoped checkpoint, covering
shared schema, draft Screener extraction, offline unavailable seams and pure corroboration tables.
These task-level proofs do not establish full D1b stage acceptance. Full vendor source proofs and
Tasks 6, 7, 9, 10, 11 and 13 remain open; no shared v2 release or real approval authentication is
claimed. Resume from the [D1b build notes](../workstreams/data-foundation/plans/D1b.md#paused-scoped-checkpoint--2026-10-13)
and live state. Commits: schema `119ae48`, pure decisions `fdae6ee`, Screener draft `7489b8d`,
offline boundaries `1eeaf69`; each has a committed progress-log entry. Migration `0006` is now
immutable; future schema uses `0007` or the next free number.

Formal frozen gate: **2,877 passed, 1 failed, 8 existing skips**; Ruff lint/format and strict mypy
passed. All 74 recorded D1b RED nodes passed and all current seals match. The existing cutoff
refusal node failed only in the coverage-suite run; its four focused coverage cases then passed.
Cause remains unproved (`eqos-hdz`). The privacy scanner returned STOP on monetary oracle/
synthetic-value collisions and a generic metadata field (`eqos-490`). The gate is not PASS;
no rail was disabled, and committing the inspected, unaffected offline scope does not resolve it.
The real project verifier also records 12 NOT BUILT exits/governance/pilot obligations.
After explicit resume, investigate these two gate findings before claiming stable acceptance or
starting another implementation batch. Then follow the actual D1b publication/run dependencies.

## Objective

Advance the authorized Equity-OS backend work to completion, using as much safe parallel
execution as available capacity permits. Continue through verified, eligible work until the
objective is achieved or the runtime budget is exhausted. Preserve a resumable checkpoint at
every completed item. Budget exhaustion or parked work is not project completion.

The product maintains an approved analytical view of Indian companies across quarters: retained
evidence → reconciled figures → deterministic calculations → reviewable earnings updates →
separately approved memory. Backend acceptance is the Apar four-quarter PostgreSQL pilot.

## Authority and references

This file records the owner's latest instructions of 2026-10-13: work autonomously, maximize
parallel execution, and resolve document conflicts using the latest applicable document.
Use recorded document/revision/decision dates, not filesystem modification times. This instruction
supersedes older one-worker scheduling rules. On activation the owner also explicitly authorized
ignoring enforced sequence and using relevant, risk-scaled verification. Overlap independent
queue items and Areas A/C/B with exclusive ownership; preserve genuine data/interface dependencies,
acceptance gates and the handoff's hard protections. Batch broad checks on stable integrations,
using focused proofs during development; omit redundant checks for trivial changes.
If dates tie and precedence remains ambiguous, choose fail closed and record the ruling in the
current phase plan's build notes. Do not ask the owner questions or infer financial judgments.

Read [the current handoff](../workstreams/data-foundation/handoff-codex-2026-10-13.md), then the
repository read order in `AGENTS.md`. Consult these sources when their work becomes active:

| Source | Use |
|---|---|
| [Core definition](../workstreams/data-foundation/core.md), [core roadmap](../workstreams/data-foundation/roadmap.md), [backend roadmap](../backend-roadmap.md) | Scope, stage dependencies, prerequisites and pilot acceptance |
| [Data spec](../specs/2026-10-11-canonical-financial-data-and-cross-source-comparison.md), [ledger/lifecycle spec](../specs/2026-10-12-report-ledger-memory-and-data-lifecycle.md) | Build contracts; resolve conflicts by the dated authority rule above |
| [D1a plan](../workstreams/data-foundation/plans/D1a.md), [D1a findings](../workstreams/data-foundation/reviews/D1a-phase-review-r1.md), live Beads | Current tasks, findings and verified work state |
| [Decision register](../blueprint/funda-blueprint-implementation-decision-register-v2.md), [architecture v2](architecture/architecture-brief-v2.md), [Gold goal](equity-os-product-completion-gold.md), [vision checkpoint](../evidence/product-completion/vision-acceptance.md) | Broader release gates and vision; refresh old status claims against newer evidence |
| `.claude/project/verification.md`, `.claude/project/invariants.md` | Required checks and financial/provenance invariants |

## Work inventory and acceptance

1. Preserve the existing uncommitted Area A/C work and migration `0005`. Fix the three reported
   mypy errors, establish the exact known-failure baseline (`eqos-hz0`, two source-intake cases),
   and commit the verified Area A starting work, including `0005`, without staging Area C.
2. Finish D1a Areas A, C and B through independent parallel file scopes. Implement every finding's
   specified fix, with tests first for meaningful behavior changes.
   Area B owns A4's selection change. Verify every previously reported fix against current code.
3. Run D1a's fresh independent review/fix/re-review loop. After three non-convergent rounds,
   record a fix-or-park ruling for every residual; run a fresh critical review of the whole phase.
   Close `eqos-3f9` and update roadmap progress only when its exit and review requirements hold.
   D1a's original red proof is missing: disclose that limitation and never claim its historical
   `verify.sh gate` passed. Follow the handoff's explicit four-check/tracer/review closure route;
   record this dated authority ruling in D1a build notes. Red-proof gates apply from D1b onward.
4. Elaborate and independently review `plans/D1b.md` under the data-foundation workstream.
   Record `scripts/verify.sh red <slice>` before each D1b implementation stage. Build retained
   vendor adapters, corroboration, queue, amendments and the source-verified frozen manifest;
   commit the approved manifest before its e2e test. Proceed only after D1b's exit is green.
5. Continue D2–D9, PREP-1–PREP-8 and the pilot, respecting actual
   dependencies. Park prohibited steps, record reasons, and select the next unblocked item.
   Later research capabilities require their recorded activation gates; do not activate them by
   treating an older whole-product goal as blanket permission.

## Parallel execution and item completion

Across eligible queue items, dispatch independent bounded tasks with explicit file ownership.
One writer owns shared contracts, configuration, migrations and test
support per batch. Tell every worker others are editing and require preservation of their work.
Use available slots for implementation, source verification and fresh independent review; rotate
finished workers out. Run integrated ingest checks after extractor edits are frozen; establish
test-harness isolation before concurrent PostgreSQL runs. Follow the execution skill; use planning
for new phase plans and test-first/debugging/security skills where applicable.

Every verified item: obtain relevant behavior proof → implement → verify the affected surface
(all four handoff checks at stable integration/phase gates) → commit explicit files
with `Co-Authored-By: Codex <noreply@openai.com>` → update/close Beads using `--actor codex` and
evidence → append `YYYY-MM-DD HH:MM — item — result — commit` to the handoff progress log and
commit that log. Preserve unrelated changes; the known baseline failures are not a clean-suite
claim. Fresh reviewers must receive: "List ALL issues you find in a single exhaustive report.
Do not stop at the first few. Rank them by severity." Record them as "Codex session (handoff run)".

## Protected boundaries and completion evidence

Never push, expose/commit credentials, rewrite unrelated changes, modify `data/raw/`, fetch live
vendor data, touch the real `equity_os` database or PostgreSQL data directory, or run destructive
Docker commands. PostgreSQL tests use `eqos_test_*` only. Applied migrations `0001`–`0004` are
immutable; `0005` becomes immutable at its first commit; subsequent schema work takes the next
free number. Use exact `Fraction` arithmetic, `eqos.store_now()` knowledge times, honest capture
times and source-derived expectations. Never zero-fill or backdate; commit repo-relative paths
only and keep `scratchpad/` untracked.

Park work requiring live access/new credentials, actual D2 cutover, owner-time steps including
PILOT-12, or owner financial judgment. Rehearsals do not satisfy an operational cutover or human
measurement gate; keep dependent acceptance blocked and continue eligible independent work.

Core completion requires all ten phase exits, approved source-verified manifests/amendments,
fresh quality checks and evidence-backed phase closures. Backend completion additionally requires
PILOT-1–PILOT-13, `scripts/verify_project.sh` exit 0 and an approved evidence-linked pilot report.
Keep `PILOT_PROVEN`, `CORE_RESEARCH_RELEASE` and `VISION_SATISFIED` separate; claim each only when
its own documented proof passes. At a runtime stop, record commits, checks/failures, parked work,
worker state and the exact next item in the progress log and Beads before handing off.

**First action on activation:** read the latest progress log and live Beads/git state; if queue
item 1 remains unfinished, claim it and run the four baseline checks before changing code.
