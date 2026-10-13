# Equity-OS resume checkpoint — 2026-10-13

Owner requested: finish the already-started group, commit it, save progress and pause.
No new implementation batch may start before an explicit resume.
This file is the current resume pointer; historical pause notes retain their original dates.
Beads holds live task state. This document consolidates authority, evidence and next scope.

## Current checkpoint

D1a is accepted complete. D1b has substantial verified mechanisms but its full source
acceptance remains open. **8 of66 stages accepted**: seven D1a and one D1b amendment.
D2–D9 and the backend pilot have not started. Passing mechanism tests do not close those stages.

Public vendor checkpoint committed `cd76f3a`; per-item log `064031b`. Independent R2
APPROVE;31 guarded PostgreSQL and100 pure cases pass. Exact handed-off generations are
prepared before writes; source-qualified rows, queue rollback/reuse and by-ID replay are tested.
Witness group209e4ad and per-item logf22c579 are committed. Independent R2/R3 approvals,
full3398-test behavior run and separately cleared final documentation rails are recorded below.

## What to read and how to resolve authority

1. This checkpoint and the last entries in
   [handoff progress log](handoff-codex-2026-10-13.md#progress-log).
2. `AGENTS.md`, `CONTEXT.md`, `.codex/project/brief.md`, `.codex/project/repo-map.md`,
   `.codex/project/docs-index.md`, `.codex/project/verification.md`,
   `.codex/project/invariants.md`; `bd prime` for tracker context.
3. [Active goal](../../goals/2026-10-13-autonomous-backend-completion.md),
   [backend roadmap](../../backend-roadmap.md), [core definition](core.md),
   [core roadmap](roadmap.md). The requested data-foundation definition is `core.md`.
4. [Data spec](../../specs/2026-10-11-canonical-financial-data-and-cross-source-comparison.md)
   and [ledger/lifecycle spec](../../specs/2026-10-12-report-ledger-memory-and-data-lifecycle.md),
   current decision register and applicable source-authority artifacts.
5. [D1b plan](plans/D1b.md), [public run supplement](plans/D1b-vendor-runs.md),
   [witness supplement](plans/D1b-first-party-intake-witness.md) and their linked reviews.

Latest explicit owner steering wins conflicts: safe parallel execution is authorized;
old one-worker/order and Claude model-routing statements are historical. Requirements and
acceptance dependencies still apply. Use the latest applicable dated ruling; never infer a
source approval, financial judgment or acceptance waiver from an older broad goal.
Do not ask questions: select the fail-closed option and record it in the plan's build notes.

## Completed and committed engineering

| Area | Evidence / checkpoint |
|---|---|
| D1a canonical tracer | `22a3c78`, phase and fresh critical re-reviews approved; baseline2787tests, source-stated Apar figures preserved. |
| D1b data-layer amendments | `c77657d`; exactly two independently approved register amendments. |
| Retained inventory and adapters | Source inventory disposition review, Screener extraction/native drafts, offline unavailable/Tijori boundaries; missing captures remain excluded honestly. |
| Dictionary/native construction |259legacyrows preserved plus one source-backed derived aggregate; native scope, dimensions, qualification and operand provenance tested. |
| Actual joined v2 release | C=`a4002bb`, exact-A review and separate release receipt;32selected blobs/pins preserved. Actual retained Apar v2 append/reuse and v1 compatibility pass. |
| Vendor acquisition | `2d15c1d` migration0008 and `9e43fd5` exact source-qualified generation producer. |
| First-party producer/consumer | Exact settings/context/member/attempt/capture/row handoff, `ee3b07f` bounded consumer; new positive witness proves the selected physical intake/request binding. It does not verify a failed body's issuer identity or grant source authority. |
| Queue visibility | `f8eba1c` migration0009; exact immutable visibility, shared-cursor publication, isolation/reuse/rollback and actual v1 upgrade replay. |
| Public vendor execution | `cd76f3a`; exact all-claim preflight, corroboration rows, immutable overlay, public run and by-ID replay. |
| Current SONACOMS identity | `3df9421`, independently evidenced six fields from seven anchors; current instrument ISIN evidence grants no historical interval or financial rights. |
| Project verifier mechanism | `9781763`; truthfully reports unbuilt exits/pilot; actual full-project PASS remains absent. |

Detailed witness acceptance and review findings:
[R2 implementation review](reviews/D1b-retained-intake-witness-implementation-r2.md).
Public review and explicit limits:
[public checkpoint review](reviews/D1b-public-vendor-run-checkpoint.md).

## Exact next resume scope

Start by reading this final checkpoint and `bd show` for `eqos-u0u.29`, `.25`, `.28`, `.30`.
Task7 `.29` is **open**: authenticated review commands, immutable overlay/report behavior,
receipt-linked approval evidence. No Task7 implementation or new plan was started at pause.
Write/review a bounded plan first and capture genuine callable-seam regressions before repair.
Use independent workers only with exclusive ownership; Root owns shared integration.

Still-open D1b obligations:

| Bead / stage | Remaining acceptance |
|---|---|
| `eqos-u0u.29` / Task7 / D1b.3 | Authenticated approve/reject/rework commands, actual receipt proof, immutable queue/report CLI and status integration. |
| `eqos-u0u.25` / Task6 | Actual retained SONACOMS868Cr comparison and complete source acceptance; mechanism-only synthetic positives are insufficient. |
| `eqos-u0u.28` | SONACOMS original intake/source-clock/framework evidence. Identity prerequisite alone is complete. |
| `eqos-u0u.30` | Late links to already-listed occurrences have no provable creation clock. The producer aggregates descriptions across periods while the public guard requires each witness at the requested end. Resolve both actual retained acceptance limits; no invented clocks or old SQL edits. |
| D1b.1 and D1b.2 | Retained Apar vendor positives, Tijori, authority-qualified Upstox diagnostics, ten-company and NETWEB failure/correction/ambiguity coverage. |
| `eqos-u0u.5` / D1b.5 | Independently hand-verified source expectations and reviewer-approved frozen Stage1 manifest, committed before its e2e test. |
| `eqos-u0u.6` / D1b.6 | Actual Stage1 e2e against that manifest, full phase review plus fresh critical review and formal gate. |
| `eqos-hdz` | Historical one-off cutoff failure cause UNKNOWN; unchanged focused and multiple full passes do not explain it. |

SONACOMS source details: raw Screener Dec2024 consolidated Sales868Cr; native XML revenue
8679674000INR. The retained XML lacks the framework declaration required by the current intake
contract; original retrieval/filing/publication knowledge-clock authority is absent. No filename,
PDF board date, validation retrieval claim or current instrument catalog supplies that authority.
Fail closed. A future additive UNKNOWN-clock contract requires its own approved plan and proof.
All four Upstox financial surfaces remain EXCLUDED/no financial authority/no writes/nonvoting.
No live fetch, borrowed Apar equivalence, fabricated original manifest or backdating is authorized.

## Remaining backend roadmap

| Phase | Stages | Scope |
|---|---|---|
| D1b |6 | Finish source-qualified comparison/queue and frozen Stage1 acceptance. |
| D2 |8 | Legacy reconciliation, PostgreSQL consumer port and cutover. Actual production cutover is parked. |
| D3 |9 | Report ledger versions, claims, fact/trace citations, approval and reproducible export. |
| D4 |5 | Separate memory promotion, source provenance, historical retrieval and contradiction. |
| D5 |5 | Read-only generated report and memory views. |
| D6 |6 | Identifier-only held-out company onboarding. |
| D7 |6 | Universe, coverage decisions, screens and watchlist. |
| D8 |5 | First-party shareholding ingestion and source-qualified comparison. |
| D9 |9 | Retention holds, purge, backup/restore and replay after deletion. |

Then PREP-1…8: remaining taxonomy/PDF mappings; PostgreSQL-only earnings workflow;
resumable states/retries; approved source matrix; rejected-claim rework/versioning;
ledger review telemetry and seeded-error drill; frozen four-quarter pilot manifest;
complete project-verifier targets.

Final backend goal: Apar consolidated PQ0(Q2FY26), PQ1(Q3FY26), PQ2(Q4FY26), PQ3(Q1FY27)
earnings review entirely on PostgreSQL, with source-backed numbers, traceable/reviewable claims,
ledger versions, cutoff-safe memory, held-out onboarding, coverage/shareholding and purge/restore
replay. All D-phase exits and PILOT-1…13 pass; `scripts/verify_project.sh` exits0;
reviewer approves the linked pilot report. Only then `PILOT_PROVEN: YES` and Phase0.5 closure.
PILOT-12 requires actual owner review measurements and remains parked. Later product phases,
GBrain, debate, backtesting and execution retain their separate activation gates.

## Operating boundaries on resume

Local commits with explicit files and Codex trailer are authorized; **never push** or sync a
Dolt remote. Beads is the task tracker; update with `--actor codex` and preserve old notes.
Never stage the passive `.beads/issues.jsonl` baseline change. Never stage scratchpad.
Never print or commit secrets, edit `.env` or `data/raw/`, fetch new vendor data, touch the real
`equity_os` database/PGdata, or run destructive Docker. Tests use `eqos_test_*` only.
Migrations0001–0010 are committed and immutable; future SQL takes0011 or the next free number. Keep32released
v2 blobs/pins unchanged, exact Fraction arithmetic, genuine source expectations and store clocks.
No zero filling, guessed source authority, fake approval, clock backdating or weakened gates.

Verification uses the existing uv environment, an isolated temporary `UV_CACHE_DIR`,
and `uv run --no-sync`. Formal original-scope gate uses `UV_NO_SYNC=1 VERIFY_SCOPE_BASE=05b2634`.
Read terminal output/exit status; do not claim PASS from a live process. Batch stable checks;
rerun only for changes, failures or unresolved concerns. Keep existing ignored worktrees as
evidence; no cleanup/rewrites required. All workers must be terminal before pausing.

## Final checkpoint entry

Prepared 2026-10-13 16:24 UTC for goal pause after this final documentation commit.

- Code commits: public vendor checkpoint `cd76f3a`, witness group `209e4ad`.
  Per-item progress commits: `064031b`, `f22c579`.
- Final full suite: **3398 passed /8existing skips**,1605.66s. Full Ruff lint/format
  and strict mypy pass. Independent public R2 and witness R2/R3 reviews approve.
- Preserve the actual formal wrapper result: STOP/exit3 solely for old R1 prose repeating
  prohibited path-pattern literals. That prose is corrected. Exact unchanged security block
  rerun against original full scope exits0 and reports all rails clear; no gate/rail disabled.
  No duplicate26-minute test run for that documentation-only correction.
- Synthetic public witness test's pg marker added as metadata-only classification: complete
  test function/assertion AST unchanged, same1node collected for pg and deselected for not-pg,
  explicit Root reseal. Source/test bodies remain those exercised by the full suite.
  These separately verified corrections do not relabel the preserved wrapper result as PASS.
- Diff coverage:633unexecuted changed lines, advisory. No100%coverage or phase-completion claim.
- `.15`, `.20`, `.24` closed within technical acceptance. `.25`, `.28` remain unfinished;
  `.29` and `.30` open; full D1b epic/stages remain open. `eqos-hdz` cause remains UNKNOWN.
- All workers terminal; full verification and rail recheck processes terminal. No new batch.
- Source verification logs and frozen worktrees remain ignored under `scratchpad/`:
  `scratchpad/gate/d1b-retained-intake-witness-20261013T154700Z.log`,
  `scratchpad/execution/data-foundation-resume-2026-10-13/final-rails-recheck-root.log`,
  `scratchpad/worktrees/data-foundation-public-runs`,
  `scratchpad/worktrees/data-foundation-intake-witness`.
- Expected final Git status: only original passive `.beads/issues.jsonl` change; never stage it.
  All requested code, reviews, progress and this resume document committed locally; never pushed.
- On explicit resume: inspect `git status`, latest handoff log and `bd show eqos-u0u.29`;
  read its approved parent plans, then write/review the Task7 plan before implementation.
  Do not automatically reopen old completed technical tasks or begin D2 before Stage1 acceptance.
