# Equity-OS backend roadmap and pilot acceptance

The single list of backend work still to be done, and the pilot that decides whether the backend
is complete. Detailed plans live in the linked roadmaps and specs. Where this file and a spec
differ, the spec wins. Owner decisions recorded 2026-10-13:
- keep the current order (backend core first);
- verify the backend with a pilot run entirely on the PostgreSQL backend.

## 1. Goal

Equity-OS is an evidence-governed equity research system for Indian markets
(`.claude/project/brief.md`). Its first deliverable is a fixed earnings-review workflow. Given a
company's new quarterly results and the approved prior thesis, it produces a reviewable,
source-backed update of what changed in facts, management commitments, calculations,
uncertainties and thesis.

**The backend is complete when the pilot in §4 passes.** The pilot is one company over four
quarters, run on the backend. Every number in it must be stored, cross-checked and traceable, and
every claim reviewable.

Beyond this file (decision register `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md`):
- Phase 1 (2–3 companies; analyst-effort and results-season gates).
- Phase 2 (memory evaluation).
- Conditional capabilities: GBrain, debate, backtesting, execution.

## 2. Structure

| Part | What | Plan | bd |
|---|---|---|---|
| **Backend core** (data foundation) | Shared PostgreSQL store, dictionary, comparator, ledger, memory, views, onboarding, coverage, shareholding, retention | [core roadmap](workstreams/data-foundation/roadmap.md), [core definition](workstreams/data-foundation/core.md) | epics D1a–D9, label `ws-data-foundation` |
| **Pilot prerequisites** | Workflow and register items the pilot needs that the core does not build | §3 rows P0.x | `eqos-4j2`, register §B |
| **Pilot** (verification phase) | Phase 0.5 on the backend: Apar, Q0 baseline plus three assisted updates | §4 | `eqos-4j2.8` |
| Deferred | Screener/Tijori breadth via the capability registry (`eqos-kx4.5`); Tijori Stack (`eqos-d37`) | — | not needed for the pilot |

Order: D1a → D1b → D2 → D3 → D4 → D5 → D6 → D7 → D8 → D9 → P0 → Pilot. One worker runs at a
time.

## 3. All remaining backend work

| # | Work | Done when | State (2026-10-13) |
|---|---|---|---|
| D1a | Canonical comparison tracer: schema, dictionary, formula engine, evidence model, first-party tables, runs, report | `test_compare_tracer.py` green; phase review approved | Built and committed; review fixes in progress (paused) |
| D1b | Vendors (Screener, Tijori), corroboration, review queue, frozen Stage 1 manifest | `test_data_stage1_e2e.py` matches the manifest (Apar + ten companies) | Not started |
| D2 | Migrate the legacy SQLite fact store; move consumers to PostgreSQL; cutover | Stage 2 e2e green; cutover recorded | Not started |
| D3 | Report ledger: versions, numeric claims citing facts or traces, claim check, approvals, export | Ledger Stage 1 e2e and `test_ledger_export.py` green | Not started |
| D4 | Long-term memory with separate promotion | Ledger Stage 2 e2e green | Not started |
| D5 | Generated read-only views | Ledger Stage 3 e2e green | Not started |
| D6 | Onboarding a company by identifier alone | Stage 4 e2e green on a held-out company | Not started |
| D7 | Coverage: universe registry, screens, watchlist | Ledger Stage 4 e2e green | Not started |
| D8 | Shareholding filing source | Stage 3 e2e green | Not started |
| D9 | Retention, purge and replay after deletion | Ledger Stage 5 e2e green | Not started |
| P0.1 | Mappings for the SEBI 2026-01-31 XBRL taxonomy; fix Q4 FY26 PDF revenue rows | Q4 FY26 and Q1 FY27 Apar filings extract with no `UNSUPPORTED_SCHEMA` | Open bead (found in D1a) |
| P0.2 | Earnings-review workflow reads only PostgreSQL: facts, comparison results, ledger, memory | No pilot code path opens the legacy SQLite store | Covered by D2 consumer port; confirm at P0 |
| P0.3 | Resumable workflow with defined states, retries and failure states (register B-01) | Interrupt-and-resume test per step | Open |
| P0.4 | Source-of-truth matrix (B-03) | Matrix approved by the reviewer | Open |
| P0.5 | Rejected-claim rework path and evidence-package versioning (B-14) | A rejected claim reruns only affected claims and produces v(N+1) | Open |
| P0.6 | Review telemetry wired to ledger claims (B-04, B-13); seeded-error drill | Per-claim disposition and time recorded; drill errors caught | Instrument exists (`fundamentals review`); not yet on the ledger |
| P0.7 | Frozen pilot manifest | Expected values hand-verified from the four quarters' filings, reviewer-approved, committed before the pilot test | Not started |
| P0.8 | `scripts/verify_project.sh` | Runs every D-phase exit plus the pilot test; PASS/FAIL per part | Not started |

Estimate (inference from D1a only): D1a–D9 take 3–6 weeks of continuous running, and P0 plus
the pilot take about 1–2 weeks more. The pilot also needs the owner's time (§4, check 12).

## 4. Pilot acceptance: how the pilot decides completion

**Scope.** Apar Industries consolidated, four program quarters, every step on the PostgreSQL
backend:

| Program | Quarter | Role |
|---|---|---|
| Q0 | Q2 FY26 (30-Sep-2025) | Manual baseline and bootstrap thesis (starting figures owner-confirmed 2026-10-12) |
| Q1 | Q3 FY26 (31-Dec-2025) | Assisted update 1 |
| Q2 | Q4 FY26 (31-Mar-2026) | Assisted update 2 (audited, full year) |
| Q3 | Q1 FY27 (30-Jun-2026) | Assisted update 3 |

**Checks.** Each check exercises one backend capability. Expected values come from the frozen
pilot manifest (P0.7), never from code output.

| # | Capability | Pass condition |
|---|---|---|
| 1 | Ingest and extraction check (D1a) | All four quarters' XBRL and PDF ingested. Every applicable row has a state, and none is filled with zero. Q0 matches the manifest: PBT 340.56 / 340.53 crore, OPM 8.06% |
| 2 | Corroboration (D1b) | Screener and Tijori compared per quarter; the Apar opex gap against Screener equals its pre-registered outcome; every untrusted outcome has a queue item |
| 3 | PostgreSQL only (D2) | Legacy Apar facts reconciled; the pilot opens no SQLite store |
| 4 | Ledger (D3) | Each update is a ledger version. 100% of material numerical claims cite a fact id or calculation trace, and the claim check passes. Reviewer approval is recorded. Export reproduces each version's hash |
| 5 | Memory (D4) | Items promoted after Q1 are retrieved in Q2 and Q3 with provenance. A contradicted item is surfaced. No retrieval returns anything after the quarter's cutoff |
| 6 | Views (D5) | Each version and the promoted memory render read-only |
| 7 | Onboarding (D6) | A held-out second company onboards by identifier alone and produces a comparison report |
| 8 | Coverage (D7) | Apar is on the watchlist through the decision chain; drafting for a non-watchlisted stock is refused |
| 9 | Shareholding (D8) | Each quarter's promoter, public and institution aggregates are compared against vendors and cited where the update uses them |
| 10 | Retention and replay (D9) | After the pilot, a purge dry-run lists only eligible blobs. Purge, restore and replay of the Q0 run reproduce its results, and no held evidence is deleted |
| 11 | Workflow integrity (P0.3–P0.6) | One step is interrupted and resumes without duplication. One claim is rejected → only affected claims rerun → package v(N+1). The seeded-error drill is caught |
| 12 | Review measurement (register §F) | Owner review time recorded for Q0 and each of Q1–Q3, with per-claim dispositions and correction categories |
| 13 | Reproducibility | Each quarter's comparison run replays from its manifest. Full suite, mypy and ruff are clean |

**Verdict.**
- **PASS:** every D-phase exit is green and checks 1–13 all pass. `scripts/verify_project.sh`
  exits 0, and the pilot report (each check with its evidence links) has the reviewer's approval.
  This sets `PILOT_PROVEN: YES` in the brief and closes Phase 0.5.
- **FAIL:** any check that fails names the backend part at fault. That part is reopened, fixed and
  re-verified, then the pilot is re-run from the failed check onward.

Check 12 depends on the owner reviewing four reports; it is the one step that cannot run
autonomously. Whether the workflow actually saves review time is judged at Phase 1 (register
C-12), not here.
