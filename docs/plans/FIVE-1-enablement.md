# FIVE-1 Implementation Plan: five-company enablement

**Status:** draft for Sol plan review. **Bead:** `eqos-awnc`. **Date:** 2026-11-06.
**Origin:** owner order 2026-11-05 step 4 (thorough test on APARINDS, ICICIBANK, LAURUSLABS,
MTARTECH, NETWEB); `docs/plans/FIVE-COMPANY-TEST.md` §2 blockers 1, 2, 4, 5, §8 Q1–Q5, Q7;
`docs/plans/VENDOR-1-P3.md` Task 11 (blocked on a sanctioned acquisition route); orchestrator
rulings: ICICIBANK joins the watchlist; MTARTECH's current series is checked by the orchestrator.
Code facts read at `800b4cc5`. **Inferred** marks anything not read directly.
**Goal:** every company of the five-company test can be onboarded live through a sanctioned
route, gets first-party and vendor evidence for a named list of periods, and runs under one
dictionary and mapping-set version, without touching anything the Stage 4 freeze protects.

**Out of scope:** running the five-company test (its protocol is `FIVE-COMPANY-TEST.md` §5–§6);
a standalone admit command (reading 3); fresh vendor fetches for back periods (reading 2); any
change to the Stage 4 freeze descriptor, holdout record, attempt-3 data or its e2e; Phase 2 and 3
content; live admission scope (FIVE-COMPANY-TEST §8 Q6, owner); promoting any mapping (§7 there).

**Constraints:**
- Never open `stage4_holdout.yaml`, `stage4_manifest.yaml`, `data/holdout/` or `data/raw/onboarding/`.
- Minimal code: every module traces to a gap below; no speculative seams or guards.
- Files stay under 800 lines. `onboard_cli.py` is at 800 and `discovery.py` at 789: Task 1 moves
  the freeze check out of `onboard_cli.py`; `discovery.py` takes net zero lines.
- Standard data is code; nothing is derived, estimated or filled. A watchlist identifier is
  written only from a retained capture that shows it.
- Tests follow `.claude/rules/python/testing.md`: integration through the public commands with a
  fake transport first; unit tests only for the sanction predicate and the master series rule.
- Mypy runs with `--cache-dir=/dev/null`; long gates run as `systemd-run --user` units.

**Shape:** Tasks 1–3 and 5 are code, one commit each after the orchestrator verifies them; Task 6
amends documents; Task 7 gates. Sol reviews this plan, then once at phase end (after Task 7),
closed by one fresh critical review. Task 4 (watchlist) waits on Phase 3 Task 11's captures and
lands after the review as a routine, orchestrator-verified config change. **FIVE-1 writes nothing
live**; its commands are used live by Phase 3 Task 11 and the five-company test under their
protocols, with the additions in "Live protocol" below.

**Estimate:** about 19 summed hours (author's estimate, not measured).

| Task | Implementer | Hours |
|---|---|---|
| 1. Sanctioned acquisition route | Opus | 4 |
| 2. Replayable entity-bound fetches (`compare fallback --generation`) | Opus | 2.5 |
| 3. Named-period acquisition and vendor re-ingest | Opus | 3.5 |
| 4. ICICIBANK on the watchlist | Sonnet | 1 |
| 5. MTARTECH series (branch) | Sonnet | 0.5–1 |
| 6. Document amendments | Sonnet | 1 |
| 7. Gate | orchestrator | 1.5 |
| Sol loops (plan, phase end), closing review | — | 5 |

## Readings

1. **What the freeze protects, and why a re-freeze is wrong.** D6 closed 2026-10-17 (`D6.md`
   "D6 Freeze" step 6): attempt 3 stands as evidence that the *frozen* implementation onboarded
   the held-out company; later phases may change implementation paths; the Stage 4 e2e replays
   attempt 3 and never uses `--acquire`. `_frozen`/`_check_entry` still bind `--acquire` to the
   current held-out attempt, an `APPROVE`d descriptor and no implementation commit since it, so
   every VENDOR-1 commit fails it. What must survive is (a) the append-only descriptor and holdout
   record and attempt 3's chain (`implementation_commit ⊑ descriptor_commit ⊑ acquisition_head`),
   (b) attempt 3's retained data and replay, and (c) the opacity of the held-out identity (D1.6
   leak scan, D1.7). A re-freeze appends an entry for attempt 3 with a post-closure implementation
   commit, mixing development acquisitions into the held-out evidence chain; rejected. The live
   gate also guarantees an acquisition is attributable to committed, reviewed code and a reviewed
   authorisation; the new route keeps that.
2. **Vendor captures need no back-period fetch.** A Screener or Tijori financials page carries
   many quarters and years (inferred from 6,541 Apar occurrences against 9 packages). Onboarding
   already retains one capture per page; "vendor evidence for a named period" is re-ingesting that
   capture for the period end. Only first-party filings are fetched per period.
3. **No admit command.** `run_fallback` calls `admit_run` on the run before anything else
   (`fallback.py`, read), so `compare fallback --run <id>` admits every run it is given, triggered
   or not; the report path admits through `cli._admit`. The test is passable without a new
   command. FIVE-COMPANY-TEST §5.4 stands as written.
4. **One version set for all five: dictionary v4, mapping set v11**, the last Phase 3 sets
   (`VENDOR-1-P3.md` Tasks 6, 12). The check class digests dictionary, mapping set, policy,
   extractors and issuer class (`vendor_first.check_class`, read), and Phase 3 bumps the XBRL and
   Tijori extractors, so splitting non-banks (v2/v9) from the bank (v4/v11) would also split
   every class and make one `measure` over five meaningless.
   **Consequence:** Apar's eligibility `v1` (Phase 1 Task 14, classes under v2/v9 and the
   pre-Phase-3 extractors) matches no class of the test's runs, so no cell in the test can admit
   under §6.5 row 3 (`VENDORS_AGREE_NOT_CHECKED`); Apar's Task 14 counts are the numeric baseline
   only (Phase 3 Task 13 proves the values unchanged), not evidence that carries over; the test's
   `measure` (§5.6) starts every class from zero; Apar must be re-ingested live under v11/v4 like
   the others (§5.2 now applies to Apar). Apar's pilot pins (`PILOT_VERSIONS`) and eligibility
   `v1` stay byte-unchanged, so Apar's report path is unaffected.
5. **Named periods are bounded by onboarding's settings.** `vendor reingest` and runs read
   `FISCAL_YEAR_END_MONTH` with `valid_from <= period_end`, and onboarding's `valid_from` is the
   earliest filing period it read (`derived_settings.py`, read). A named period before that
   refuses (`no fiscal-year-end month`); accepted as the bound, not extended.

## File map

| File | Change | Task |
|---|---|---|
| `equity_os/interface/commands/companies/acquisition_authority.py` | create: `frozen` (moved verbatim from `onboard_cli`), `sanctioned` (Task 1); `entity_fetch` (Task 2) | 1, 2 |
| `equity_os/interface/commands/companies/onboard_cli.py` | modify: `--sanction`, call the module, `_argv`; net fewer lines | 1 |
| `config/acquisition/sanctions/five-company.yaml` | create: the five symbols, purpose, plan path, `review` | 1 |
| `equity_os/companies/onboarding/discovery.py` | modify: generation `as_of` optional when no master was fetched; net zero lines | 2 |
| `equity_os/interface/commands/verification/compare_cli.py` | modify: `fallback --generation N` through `entity_fetch` | 2 |
| `equity_os/verification/admission/fallback.py` | modify: `_acquire`, `_ingest` public as `acquire_group`, `ingest_group`; add `acquire_periods` | 3 |
| `equity_os/interface/commands/extraction/evidence_cli.py` | modify: `evidence acquire` action | 3 |
| `equity_os/interface/commands/sourcing/vendor_reingest.py` + its CLI registration | modify: `source_period_end` / `--captures-of` | 3 |
| `config/coverage/watchlist.yaml` | modify: ICICIBANK entry | 4 |
| `equity_os/companies/onboarding/verification.py` | modify on branch 5B only: accepted series `EQ`, `BE` | 5 |
| `docs/plans/FIVE-COMPANY-TEST.md`, `docs/plans/VENDOR-1-P3.md` (Task 11 commands), `CONTEXT.md` | modify | 6 |
| Tests: `tests/equity_os/companies/onboarding/test_onboarding_acquisition.py`, the fallback test beside `fallback.py`'s existing one, `vendor reingest` test, watchlist-loading tests that pin the stock list | modify/extend | 1–5 |

## Task 1: Sanctioned acquisition route

Goal: `eqos onboard <SYMBOL> --acquire --sanction <path>` acquires a new generation for a symbol a
committed, `APPROVE`d sanction lists, recording the sanction instead of a freeze; the freeze route
and every Stage 4 check are unchanged.

Files:
- Create: `acquisition_authority.py`; `config/acquisition/sanctions/five-company.yaml`
- Modify: `onboard_cli.py`
- Test: `test_onboarding_acquisition.py` (integration, tmp git repo as the freeze tests use);
  one parametrized unit test of `sanctioned`

Interfaces:
- Consumes: `IMPLEMENTATION_PATHS`, `SOURCE_CHECKOUT`, `DEFAULT_CONFIG_ROOT`, `_git`, `_sha256`
  (moved with `frozen`).
- Produces: `frozen(descriptor: Path, config_root: Path) -> dict[str, Any]` (today's `_frozen`,
  same output); `sanctioned(path: Path, config_root: Path, symbol: str, roots: tuple[Path, Path])
  -> dict[str, Any]` returning `{"sanction": <repo-relative path>, "sanction_sha256",
  "acquisition_head"}`; generation authorisation string `sanction <path>@<head>`. Sanction file
  schema: `{symbols: [str], purpose: str, plan: str, review: {reviewer, verdict, date}}`.

Approach: move `_frozen`, `_check_entry`, `_tree`, `_freezes`, `_git` to the new module unchanged
(`onboard_cli` imports `frozen`). `sanctioned` refuses unless: the sanction file is in the running
checkout and `--config-root` is its `config` (as `frozen`); `git status --porcelain` over
`IMPLEMENTATION_PATHS` is empty and the file's bytes equal `HEAD`'s blob (committed, not merely
supplied); its fields are exactly the schema's; `review.verdict == APPROVE`; the symbol is listed;
neither `--raw-root` nor `--snapshot-root` resolves under `data/raw/onboarding/` or
`data/holdout/`. `--sanction` and `--freeze-descriptor` are mutually exclusive; `--acquire` needs
one. `acquisition.json` carries the sanction fields and no `attempt`, so it can never be read as
held-out evidence. The sanction file lists the five symbols (MTARTECH per Task 5's branch) with
`plan: docs/plans/FIVE-1-enablement.md` and is stamped with Sol's plan `APPROVE` (reviewer,
verdict, date) by the orchestrator, as the freeze descriptor's review is. Because it sits under
`config/`, the D1.6 leak scan covers it: if any listed symbol were the held-out company the scan
fails opaquely (Task 7), and nobody reads the held-out identity.

Verification: `uv run --no-sync pytest -n 4 tests/equity_os/companies/onboarding/test_onboarding_acquisition.py`
and the onboarding suite green: sanctioned acquire then replay is identical and leaks nothing;
refusals for an unlisted symbol, a non-`APPROVE` review, an uncommitted or edited sanction, a root
under either protected directory, both or neither authorisation flag; every existing freeze test
passes unchanged. `wc -l onboard_cli.py` < 800.

Dependencies: none.

Risks: a moved function's behaviour drifting; the move is verbatim and the existing freeze tests
are the characterisation. Phase 3 Tasks 1, 5, 7, 12 also edit `onboard_cli.py`: one writer at a
time, Task 1 first.

## Task 2: Replayable entity-bound fetches

Goal: `compare fallback` writes every fetch it makes as a generation under `--raw-root`, and
`--generation N` replays one without opening a socket, so a live fallback can equal its rehearsal
(FIVE-COMPANY-TEST §8 Q4).

Files:
- Modify: `discovery.py`, `acquisition_authority.py`, `compare_cli.py`
- Test: the existing fallback integration test, extended

Interfaces:
- Consumes: `acquiring_fetch`, `replay_fetch`, `write_generation`, `live_transport`, `now`.
- Produces: `DiscoveryManifest.as_of: date | None` (set only when the log holds the NSE master);
  `compare fallback ... [--generation N]`; a shared `entity_fetch(raw_root: Path, generation: int
  | None, issuer: str, authorization: str) -> tuple[Fetch, Callable[[], None]]` (fetch, and the
  writer to call after the work) in `acquisition_authority.py`, used again by Task 3.

Approach: `write_generation` sets `as_of` from the master when one was fetched, else `None`;
`replay_fetch` checks the master/`as_of` pair only when `as_of` is set. Onboarding always fetches
the master first, so its generations and replay checks are unchanged. `entity_fetch` replays
`gen-N` or acquires and writes `gen-<next>` with the fallback's authorisation string. Fallback
needs no sanction: spec §6.8 scopes it to the triggering run's own issuer and periods.

Verification: fallback acquire (fake transport) then replay of the written generation gives equal
outcomes, captures and packages on two fresh `eqos_test_*` databases; an altered body refuses;
onboarding replay tests unchanged.

Dependencies: Task 1 (same new module).

Risks: loosening the onboarding replay check; the master/`as_of` test of an onboarding generation
without a master must still refuse (existing test, kept).

## Task 3: Named-period acquisition and vendor re-ingest

Goal: for an onboarded entity, `eqos evidence acquire --entity <KEY> --basis <b> --period-end
<PE> [--period-end ...] --mapping-set <m> --dictionary <d> --snapshot-root <dir> --raw-root <dir>
[--issuer-config <yaml>] [--generation N]` fetches and ingests each named period's results filing
exactly as the fallback does, and `eqos vendor reingest ... --captures-of <PE0>` ingests the
captures cited at `PE0` for `--period-end`.

Files:
- Modify: `fallback.py`, `evidence_cli.py`, `vendor_reingest.py` and its CLI registration
- Test: one integration test per command over retained Apar-like fixtures with a fake transport

Interfaces:
- Consumes: `acquire_results` (`results_filing.py`), `entity_fetch` (Task 2), `load_run_config`.
- Produces: `acquire_group`, `ingest_group` (today's `_acquire`, `_ingest`, renamed);
  `acquire_periods(pool, entity_id: int, ends: Sequence[date], basis: Basis, *, fetch, roots,
  config: LoadedConfig, issuer_config: Path | None) -> list[tuple[date, int | None,
  FallbackOutcome | None]]` (package id, or `FILING_UNAVAILABLE`/`FILING_UNRESOLVED`);
  `reingest(..., source_period_end: date | None = None)`.

Approach: `acquire_periods` loops the named ends through `acquire_group` and `ingest_group`; the
authorisation string is `named-period acquisition of <KEY>`; no run, admission or outcome row is
written. The command prints one line per period and exits `INCOMPLETE` unless every period
ingests. `--mapping-set` and `--dictionary` are required, so no default can split versions.
`--captures-of` selects the captures by the attempts at `PE0` (default `--period-end`, today's
behaviour); no new vendor fetch (reading 2). Periods before onboarding's earliest `valid_from`
refuse (reading 5).

Verification: named-period acquire then replay ingests equal packages; a period with no filing
prints `FILING_UNAVAILABLE` and exits `INCOMPLETE`; `vendor reingest --captures-of` yields
occurrences for the target period from the source period's capture, and without the flag the
existing reingest test is unchanged; fallback tests unchanged.

Dependencies: Task 2.

Risks: Phase 3 Task 7 edits `fallback._acquire`/`_ingest` (source argument, per-entity
framework) and Tasks 7, 12 edit `vendor_reingest.py`: Task 3 lands first and Phase 3 rebases onto
the public names, which also gives ICICIBANK's named periods the bank framework. `_ingest` today
fixes `IND_AS`; until Phase 3 Task 7, named-period ingest is non-bank only.

## Task 4: ICICIBANK on the watchlist

Goal: `load_watchlist_config(config/coverage/watchlist.yaml).stock("ICICIBANK")` returns an
entry whose every identifier is shown by a retained capture.

Files:
- Modify: `config/coverage/watchlist.yaml`
- Test: the watchlist-loading tests that pin the stock list or count (found by `git grep -n
  watchlist.yaml -- 'tests/**.py'`), updated

Interfaces:
- Consumes: Phase 3 Task 2's grounding record (NSE symbol, ISIN, BSE scrip) and Task 11's
  retained Screener and Tijori captures (company id, warehouse id per basis, Tijori slug and id).
- Produces: the ICICIBANK `StockConfig`: `domain: Bank`, `wave: Wave-2`, `quarter` = Phase 3's
  pinned acceptance period with `filing_taxonomy: in-capmkt`, `screener_warehouse_id_*` per the
  bases the capture shows (null where the page shows none, as NETWEB).

Approach: each value is copied from the named capture by a read-only query; a value no capture
shows stays absent or goes in `needs_verification`, never guessed. Notes record the bank route.

Verification: the updated tests pass; a scan of the commands that iterate the watchlist (coverage,
validate) shows ICICIBANK refused with a reason where a bank is unsupported, not a crash.

Dependencies: Phase 3 Task 11. Lands after the FIVE-1 review (routine, orchestrator-verified).

Risks: batch commands over every stock gaining a failing bank row; the scan above catches it.

## Task 5: MTARTECH series (branch)

Goal: MTARTECH's onboarding outcome is decided before the sanction is stamped.

The orchestrator reads the current NSE `EQUITY_L` series (one read-only fetch it already plans).

- **5A, series `EQ`:** no code. MTARTECH stays in the sanction; the test expects FIVE-COMPANY-TEST
  §5.1's ordinary outcome.
- **5B, still `BE`, owner accepts `BE`:** `verification.master_rows` accepts series `EQ` and `BE`
  (one constant). Test: parametrized `master_rows` over `EQ`, `BE` (rows returned) and `BZ`,
  `SM` (none). Safe for Stage 4 because the draw reads its own `NOT_EQ` rule in the holdout
  checker, which does not import `master_rows` (read: only `documents_cli` does), and the held-out
  company was drawn with an `EQ` row, so its replay is unchanged (Task 7 confirms). `documents_cli`
  then accepts `BE` too, consistently.
- **5C, still `BE`, owner swaps the company:** no code. The sanction lists the replacement; if it
  is not on the watchlist, a Task 4-style entry follows from its own retained captures.

Verification: 5B: the unit test and the onboarding suite green. 5A/5C: the sanction's symbol list.

Dependencies: before Task 1's sanction is stamped; 5B's code is independent of Tasks 1–3. Phase 3
Task 5 may edit `verification.py`: one writer at a time.

Risks: `BE` is trade-to-trade; nothing downstream reads the series, so 5B changes only admission.

## Task 6: Document amendments

Goal: the five-company protocol and Phase 3 Task 11 name the routes this plan builds.

Files: `FIVE-COMPANY-TEST.md` (§3 rows for Q1–Q3 closed; §5.1 `--acquire --sanction`; §5.2 for
all five including Apar, with `evidence acquire` and `vendor reingest --captures-of` per named
period; every command `--dictionary v4 --mapping-set v11`; reading 4's consequence in §5.6; §8
Q1–Q5, Q7 answered by this plan), `VENDOR-1-P3.md` Task 11 (`--sanction
config/acquisition/sanctions/five-company.yaml` in place of `--freeze-descriptor D`; dependency
names FIVE-1 Task 1), `CONTEXT.md` (one entry: *acquisition sanction*).

Approach: edits only; `VENDOR-1-P3.md` is edited by whichever of its fix round and this task lands
second, serialised by the orchestrator.

Verification: `grep -n freeze-descriptor docs/plans/VENDOR-1-P3.md docs/plans/FIVE-COMPANY-TEST.md`
shows only the historical mention; structural checks in `.claude/project/verification.md` pass.

Dependencies: Tasks 1–3, 5.

## Task 7: Gate

Goal: the tip holding Tasks 1–3, 5 and 6 passes `scripts/verify.sh gate five-1` (log and revision
in `scratchpad/five-1/gate/`), mypy strict and ruff clean; and, in the main checkout where the
onboarding and holdout data exist, the orchestrator runs `test_stage4_manifest.py` and
`test_data_stage4_e2e.py` (the real-repo leak scan and the attempt-3 replay) and records PASS/FAIL
only.

Verification: gate exit 0; both Stage 4 suites PASS. A leak-scan FAIL means a sanctioned symbol is
the held-out company: stop, and the owner swaps it (never inspect which).

Dependencies: Tasks 1–3, 5, 6.

**Then: Sol phase-end review** of the FIVE-1 diff, the gate log and the Stage 4 PASS records, by
the loop in `.claude/rules/core/04-agent-stack.md`, then one fresh closing review. After `APPROVE`:
refresh `docs/status/dashboard.html`, record the verdict on `eqos-awnc`, file beads for anything
parked. Task 4 follows Phase 3 Task 11.

## Live protocol

FIVE-1 writes nothing live. Its fetching commands, when Phase 3 Task 11 or the five-company test
use them, follow `VENDOR-1-P1.md` "Live protocol" steps 1–6 and `VENDOR-1-P3.md`'s acquisition
boundary: each fetching command runs once as an acquisition against a throwaway `eqos_test_*`
restored from the baseline backup, with scratch copies of both roots; rehearsal and live replay
the same generation (`--generation N`, its manifest sha256 in `commands.txt`), so inputs are equal
by construction; new files under both roots (path, sha256) must equal the rehearsal's. Allowlist
rows added to Phase 3's table:

| Command | Tables allowed to change |
|---|---|
| `onboard --sanction` replay | as Phase 3's `onboard` replay row |
| `evidence acquire` replay | captures (`capture_refs`, `capture_addresses`, `capture_states`); package and extraction tables as Phase 3's `evidence ingest` row; `version_pins` |
| `compare fallback` replay | as `evidence acquire`, plus the `compare run` row's tables, `fact_stores`, `fact_store_events`, `fact_rows`, `fact_selections`, `fact_admissions`, `vendor_counterexamples`, `vendor_fallback_outcomes` (rehearsal confirms the set against `admit_run`'s write paths before live) |

## Dependency order and interleaving

5 decided → 1 (sanction stamped) → 2 → 3 ; {1, 2, 3, 5} → 6 → 7 → Sol review ;
Phase 3 Task 11 → 4. Parallel: 1 and 5B, then 2 after 1 (`acquisition_authority.py`); 3 after 2.

With VENDOR-1:
- **Phase 1 Tasks 9, 10** (finishing): FIVE-1 code starts after both land; Task 3 builds on Task
  10's `fallback.py` and `results_filing.py` as on `main`. Task 9 owns `interface/entry/cli.py`;
  FIVE-1 does not touch it.
- **Phase 1 Tasks 12–14** (pending): FIVE-1 commits after Task 12's gate tip is recorded; Tasks
  13–14 run live on that gated tip, unaffected. FIVE-1 has no live window.
- **Phase 2** (plan in review): no shared files expected.
- **Phase 3** (plan in review): FIVE-1 Tasks 1–3 and 5B land before Phase 3 Task 1 starts coding,
  so Phase 3's shared-file order (`onboard_cli.py`, `fallback.py`, `vendor_reingest.py`,
  `verification.py`) begins from them and Phase 3's Task 10 gate covers them. Phase 3 Task 11 uses
  the sanction once the FIVE-1 review approves. Task 4 waits on Task 11.
- **Five-company test:** starts after Phase 3 Task 13 (v4/v11 and the extractor bumps final) and
  FIVE-1 Task 4, with every command under v4/v11 (reading 4).

## Open questions (with recommended readings)

1. **Who signs a sanction?** Recommended: Sol's plan `APPROVE` stamped by the orchestrator, as the
   freeze descriptor is (autonomy directive); the owner order 2026-11-05 is the purpose. A new
   symbol is a new sanction file with its own review.
2. **Should `evidence acquire` require a sanction?** Recommended: no. Like fallback, it is bound to
   an already onboarded entity's own identifiers, and that entity's onboarding was sanctioned or
   frozen.
3. **MTARTECH still `BE`: 5B or 5C?** Recommended: 5B (accept `BE`). It is one constant, keeps the
   owner's named five, and `BE` is the same issuer and ISIN; the owner decides only if the
   orchestrator finds `BE`.
4. **Fallback replay (Task 2) in scope?** Recommended: yes. Without it a live fallback is not
   rehearsable; the cost is a few lines, shared with Task 3.
5. **Which named periods?** Recommended: per company, every period end inside onboarding's
   settings window that both vendor captures cover, fixed by read-only queries in `commands.txt`;
   for Apar, the Task 14 scope plus the vendor-only ends chosen for fallback.
6. **Is Apar's re-ingest under v11/v4 live acceptable?** Recommended: yes, it adds rows beside the
   existing ones and moves no pilot pin; Phase 3 Interactions already expects a bead for it, which
   this test closes.
7. **Wave for ICICIBANK.** Recommended `Wave-2`; `Wave-1` is the original five-domain set.

## Self-review

- **Gap coverage:** 1 freeze route → T1, T7, readings 1, open Q1; 2 named periods → T2, T3,
  readings 2, 5; 3 admit → reading 3 (no task); 4 watchlist → T4; 5 MTARTECH → T5; 6 one version
  set → reading 4, T3 (required flags), T6.
- **Names:** `frozen`, `sanctioned` (T1); `entity_fetch`, optional `as_of` (T2) → T3;
  `acquire_group`, `ingest_group`, `acquire_periods`, `source_period_end` (T3) → Phase 3 Task 7.
- **Placeholders:** none; branch content is named by arm (5A–5C).
- **Unnamed seams:** CONTEXT term and the P3 Task 11 command → T6; leak scan and attempt-3 replay
  run only where the data exist → T7 in the main checkout.
