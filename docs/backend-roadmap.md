# Equity-OS backend roadmap and pilot acceptance

The single list of backend work still to be done, and the pilot that decides whether the backend
is complete. Detailed plans live in the linked roadmaps and specs. Where this file and a spec
differ, the spec wins. Owner decisions recorded 2026-10-13:
- keep the current order (backend core first);
- verify the backend with a pilot run entirely on the PostgreSQL backend.

## Names used in this file

Several labels in this repo collide. Always write the qualified form:

| Write | Meaning | Do not confuse with |
|---|---|---|
| core phase D1a … D9 (stage D1a.4) | Backend core phases in [the core roadmap](workstreams/data-foundation/roadmap.md) | Register items D-01…D-05 (memory decisions); owner decision "data spec D3" |
| register A-01, B-03, C-12, D-03 | Decision register `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` | Review findings |
| review finding D1a-R1-A5 | Finding A5 of the D1a phase-end review, round 1 ([findings](workstreams/data-foundation/reviews/D1a-phase-review-r1.md)) | Register A-05 |
| PREP-1 … PREP-8 | Pilot prerequisites (§3) | bd priorities P0–P4; ledger-spec owner decisions P1–P6 |
| PILOT-1 … PILOT-13 | Pilot acceptance checks (§4) | — |
| PQ0 … PQ3 (always with the issuer quarter, e.g. "PQ2 (Q4 FY26)") | Pilot quarters | Issuer quarters Q1–Q4 |
| release Phase 0A / 0.5 / 1 / 2 / 3 | Product release phases (register) | Core phases |
| plan design decision n | Numbered decision inside one plan, cited with the plan, e.g. "D1a plan design decision 10" | Owner decisions in the specs |

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
| **Pilot prerequisites** | Workflow and register items the pilot needs that the core does not build | §3 rows PREP-1…PREP-8 | `eqos-4j2`, register §B |
| **Pilot** (verification phase) | Phase 0.5 on the backend: Apar, PQ0 baseline plus three assisted updates (PQ1–PQ3) | §4 | `eqos-4j2.8` |
| Deferred | Screener/Tijori breadth via the capability registry (`eqos-kx4.5`); Tijori Stack (`eqos-d37`) | — | not needed for the pilot |

Order: D1a → D1b → D2 → D3 → D4 → D5 → D6 → D7 → D8 → D9 → PREP-1…PREP-8 → Pilot. One worker runs at a
time.

## 3. All remaining backend work

| # | Work | Done when | State (2026-10-18) |
|---|---|---|---|
| D1a | Canonical comparison tracer: schema, dictionary, formula engine, evidence model, first-party tables, runs, report | `test_compare_tracer.py` green; phase review approved | Complete; fixes `22a3c78`, independent phase/critical re-reviews approved; full suite and quality checks green |
| D1b | Vendors (Screener, Tijori), corroboration, review queue, frozen Stage 1 manifest | `test_data_stage1_e2e.py` matches the manifest (Apar + ten companies) | Complete (Sol APPROVE 2026-10-14) |
| D2 | Migrate the legacy SQLite fact store; move consumers to PostgreSQL; cutover | Stage 2 e2e green; cutover recorded | Complete on test databases (Sol APPROVE 2026-10-15); production cutover is owner-gated `eqos-3zl` |
| D3 | Report ledger: versions, numeric claims citing facts or traces, claim check, approvals, export | Ledger Stage 1 e2e and `test_ledger_export.py` green | Complete (Sol APPROVE 2026-10-15) |
| D4 | Long-term memory with separate promotion | Ledger Stage 2 e2e green | Complete (Sol APPROVE 2026-10-15) |
| D5 | Generated read-only views | Ledger Stage 3 e2e green | Complete (Sol APPROVE 2026-10-15) |
| D6 | Onboarding a company by identifier alone | Stage 4 e2e green on a held-out company | Complete (Sol APPROVE 2026-10-17); D6b extractor v2 complete |
| D7 | Coverage: universe registry, screens, watchlist | Ledger Stage 4 e2e green | Tasks 1–4 done; Tasks 5–6 wait on the owner's Screener CSV export |
| D8 | Shareholding filing source | Stage 3 e2e green | Parked (owner ruling 2026-10-17) |
| D9 | Retention, purge and replay after deletion | Ledger Stage 5 e2e green | Complete (Sol APPROVE 2026-10-18) |
| PREP-1 | Mappings for the SEBI 2026-01-31 XBRL taxonomy; fix Q4 FY26 PDF revenue rows | Q4 FY26 and Q1 FY27 Apar filings (PQ2, PQ3) extract with no `UNSUPPORTED_SCHEMA` | Done `ba1c068` (mapping set v5; `eqos-51d` closed) |
| PREP-2 | Earnings-review workflow reads only PostgreSQL: facts, comparison results, ledger, memory | No pilot code path opens the legacy SQLite store | Done: PREP-2/2b (`docs/plans/PREP-2b.md`); pilot configs name only the PostgreSQL store and the run writes the D3 ledger; closing review Sol APPROVE 2026-10-18 (`f8bcc8b`); legacy impersonation parked `eqos-4j2.22` |
| PREP-3 | Resumable workflow with defined states, retries and failure states (register B-01) | Interrupt-and-resume test per step | Done: `tests/fundamentals/test_prep3_resume.py`; states and failure states in `docs/plans/PREP-3.md`; closing review Sol APPROVE 2026-10-18 |
| PREP-4 | Source-of-truth matrix (B-03) | Matrix approved by the reviewer | Done: [matrix](blueprint/source-of-truth-matrix.md), Sol APPROVE 2026-10-18 (r1 REVISE 11 → r2 APPROVE). Pilot gaps it records: `eqos-4j2.24` fact admission, `.25` memory, `.26` thesis-impact, `.27` PILOT-4 citation contract |
| PREP-5 | Rejected-claim rework path and evidence-package versioning (B-14) | A rejected claim reruns only affected claims and produces v(N+1) | Done: [plan](plans/PREP-5.md), `tests/fundamentals/test_prep5_rework.py`; migration 0039 (`decisions.rejected_claims`, bounded `operand_count`), selective rework with a pre-write gate, `--full-successor` recovery. Sol phase APPROVE 2026-10-19 (r1 REVISE 3 → r2 APPROVE; closing REVISE 2 → APPROVE) |
| PREP-6 | Review telemetry wired to ledger claims (B-04, B-13); seeded-error drill | Per-claim disposition and time recorded; drill errors caught | Instrument exists (`fundamentals review`); not yet on the ledger |
| PREP-7 | Frozen pilot manifest | Expected values hand-verified from the four quarters' filings, reviewer-approved, committed before the pilot test; per quarter the IST-correct source cutoff, the reviewed package (ids + sha256) and the retrospective designation | Not started |
| PREP-8 | `scripts/verify_project.sh` | Runs every D-phase exit plus the pilot test; PASS/FAIL per part | Verifier foundation built `9781763`; all exits registered, actual pilot target unresolved and NOT BUILT; full project gate pending |

Estimate (inference from D1a only): D1a–D9 take 3–6 weeks of continuous running, and PREP work plus
the pilot take about 1–2 weeks more. The pilot also needs the owner's time (§4, PILOT-12).

## 4. Pilot acceptance: how the pilot decides completion

**Scope.** Apar Industries consolidated, four program quarters, every step on the PostgreSQL
backend. The pilot is a **retrospective workflow demonstration**: every original was acquired in
2026-09, after the quarters it covers, so it cannot prove historical possession or the absence of
hindsight. Each quarter has a source cutoff (its transcript's NSE filing instant, IST-parsed),
which selects the historical package, and a derivation cutoff (the run's completion), which is
the version's knowledge time; real acquisition, registration and approval times are kept
(`docs/plans/PREP-2b.md`, "Retrospective contract").

| Pilot quarter | Issuer quarter | Role |
|---|---|---|
| PQ0 | Q2 FY26 (30-Sep-2025) | Manual baseline and bootstrap thesis (starting figures owner-confirmed 2026-10-12) |
| PQ1 | Q3 FY26 (31-Dec-2025) | Assisted update 1 |
| PQ2 | Q4 FY26 (31-Mar-2026) | Assisted update 2 (audited, full year) |
| PQ3 | Q1 FY27 (30-Jun-2026) | Assisted update 3 |

**Checks.** Each check exercises one backend capability. Expected values come from the frozen
pilot manifest (PREP-7), never from code output.

| ID | Capability | Pass condition |
|---|---|---|
| PILOT-1 | Ingest and extraction check (D1a) | All four quarters' XBRL and PDF ingested. Every applicable row has a state, and none is filled with zero. PQ0 (Q2 FY26) matches the manifest: PBT 340.56 / 340.53 crore, OPM 8.06% |
| PILOT-2 | Corroboration (D1b) | Screener and Tijori compared per quarter; the Apar opex gap against Screener equals its pre-registered outcome; every untrusted outcome has a queue item |
| PILOT-3 | PostgreSQL only (D2) | Legacy Apar facts reconciled; the pilot opens no SQLite store |
| PILOT-4 | Ledger (D3) | Each update is a ledger version. 100% of material numerical claims cite a fact id or calculation trace (guidance: its source quote), and the claim check passes. Each version carries the retrospective label and both cutoffs. Reviewer approval is recorded. Export reproduces each version's hash |
| PILOT-5 | Memory (D4) | Items promoted after PQ1 (Q3 FY26) are retrieved in PQ2 and PQ3 with provenance, at the actual sequential evaluation boundaries (after the prior promotion, later events excluded). A contradicted item is surfaced. Separately, retrieval at a historical source cutoff returns nothing the pilot created |
| PILOT-6 | Views (D5) | Each version and the promoted memory render read-only |
| PILOT-7 | Onboarding (D6) | A held-out second company onboards by identifier alone and produces a comparison report |
| PILOT-8 | Coverage (D7) | Apar is on the watchlist through the decision chain; drafting for a non-watchlisted stock is refused |
| PILOT-9 | Shareholding (D8) | Each quarter's promoter, public and institution aggregates are compared against vendors and cited where the update uses them |
| PILOT-10 | Retention and replay (D9) | After the pilot, a purge dry-run lists only eligible blobs. Purge, restore and replay of the PQ0 run reproduce its results, and no held evidence is deleted |
| PILOT-11 | Workflow integrity (PREP-3…PREP-6) | One step is interrupted and resumes without duplication. One claim is rejected → only affected claims rerun → package v(N+1). The seeded-error drill is caught |
| PILOT-12 | Review measurement (register §F) | Owner review time recorded for PQ0 and each of PQ1–PQ3, with per-claim dispositions and correction categories |
| PILOT-13 | Reproducibility | Each quarter's comparison run replays from its manifest. Full suite, mypy and ruff are clean |

**Verdict.**
- **PASS:** every D-phase exit is green and PILOT-1…PILOT-13 all pass. `scripts/verify_project.sh`
  exits 0, and the pilot report (each check with its evidence links) has the reviewer's approval.
  This sets `PILOT_PROVEN: YES` in the brief and closes Phase 0.5.
- **FAIL:** any check that fails names the backend part at fault. That part is reopened, fixed and
  re-verified, then the pilot is re-run from the failed check onward.

PILOT-12 depends on the owner reviewing four reports; it is the one step that cannot run
autonomously. Whether the workflow actually saves review time is judged at Phase 1 (register
C-12), not here.
