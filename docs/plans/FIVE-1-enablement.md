# FIVE-1 Implementation Plan: five-company enablement

**Status:** approved 2026-11-06 by orchestrator ruling under the agent-stack rule for a loop that has not
converged after 3 rounds. There were four gpt-6.1-sol rounds. Review 4 found only R4-01 (P2).
The orchestrator applied Sol's stated smallest fix: `IDENTITY_REJECTED` is fatal in pass 1, a
mixed-capture case is added, and the write-pass limits now include already-expired captures and the
insertion gate. The phase-end Sol review covers the implementation. **Bead:** `eqos-awnc`. **Date:** 2026-11-06.
**Origin:** owner order 2026-11-05 step 4 (thorough test on APARINDS, ICICIBANK, LAURUSLABS,
MTARTECH, NETWEB); `docs/plans/FIVE-COMPANY-TEST.md` §2 blockers 2, 4, 5, §8 Q1, Q3–Q5, Q7;
`docs/plans/VENDOR-1-P3.md` Task 11 (blocked on a sanctioned acquisition route); orchestrator
rulings: ICICIBANK joins the comparison config; MTARTECH is `EQ` on the current master.
Code facts read at `800b4cc5`, rechecked at `6d722569`, `f19d2d54` and `454d7633`. **Inferred** marks anything not read directly.
**Goal:** every company of the five-company test can be onboarded live through a sanctioned
route, gets first-party and vendor evidence for a named list of periods, and runs under one
dictionary and mapping-set version, without touching anything the Stage 4 freeze protects.

## Review 1 dispositions

| Item | Change | Section |
|---|---|---|
| F01 | Orchestrator runs the opaque Stage 4 leak check over uncommitted symbol-bearing changes before the first commit holding them, and on the final tip; FAIL stops before commit and acquisition, no identity inference, no swap | Leak check rule; Task 7 |
| F02 | Sanction must resolve inside `config/acquisition/sanctions/`; bytes of that canonical path equal `HEAD`'s blob; outside file and outward symlink tested | Task 1 |
| F03 | One period per `evidence acquire` command and generation; repeated flag dropped; fallback refuses before fetching if a run triggers more than one group; duplicate refusal kept | Tasks 2, 3 |
| F04 | Five-company protocol gains a final-pin segment: commit a new eligibility version, fresh runs at or after its `available_from`, positive row-3 admission or a recorded limitation | Reading 4; Task 6 |
| F05 | Document-intake tables added to both fixed allowlists | Live protocol |
| F06 | One protected-root check, before any filesystem access or fetch, in `evidence acquire` and `compare fallback` (acquire and replay) and the sanction route; Stage 4's frozen replay untouched | Tasks 1–3 |
| F07 | Strict onboarding replay by default; masterless replay only in an explicit entity-fetch mode | Task 2 |
| F08 | Sanction records a payload digest, the approved plan commit and the commit recording Sol's `APPROVE`; each acquisition runs on a recorded gated tip | Task 1; Live protocol |
| F09 | Scenario roles frozen in `commands.txt`; the fallback period is not pre-acquired; triggers are refusal-derived | Task 6 |
| F10 | `ingest_group` returns the existing `IngestReport`; output names its package id and distinguishes unavailable from unresolved; settings-bound and fresh-cutoff checks tested | Task 3 |
| F11 | `--captures-of` exits `INCOMPLETE` on no source capture, a missing vendor or a target period absent from the capture's occurrences; nothing relabelled | Task 3 |
| F12 | Task 1 owns `onboarding_support.py` and the freeze tests; patches retarget to `acquisition_authority` | Task 1 |
| F13 | Orchestrator ruling 2: worktree implementation; no FIVE-1 commit on the main checkout from Phase 1 Task 13 start to Task 14 end; one revision per acquisition, rehearsal and live | Interleaving |
| F14 | Task 5 is 5A only (no code); 5B/5C, `verification.py`, their tests and estimate deleted; FIVE-COMPANY-TEST updated | Task 5; FIVE-COMPANY-TEST |
| Q1 | Accepted with F01/F02/F08: orchestrator stamps Sol's actual plan `APPROVE` over the payload this plan fixes | Task 1 |
| Q2 | Accepted: no sanction; unique held symbol and ISIN, unknown entity refuses before transport, protected-root check, no holdout lookup | Task 3 |
| Q3 | 5A; obsolete branches removed | Task 5 |
| Q4 | Accepted with F03/F07 | Task 2 |
| Q5 | Periods enumerated from actual shared vendor coverage and settings per entity/basis; roles frozen; settings not extended | Task 6 |
| Q6 | Accepted with F04's final-pin segment | Task 6 |
| Q7 | Wave-2; a required identifier no retained capture shows blocks the entry; comparison config only | Task 4 |
| Ruling 1 | FIVE-1 no longer edits `VENDOR-1-P3.md`; Phase 3 owns its imports/test seams for the moved module | Task 6; Interleaving |

## Review 2 dispositions

| Item | Change | Section |
|---|---|---|
| R2-01 | `commands.txt` gains role (d) *final-pin positive*: an evidenced, agreeing, filing-absent cell of a class that qualifies from the other genuine checks, never acquired or fallen back on before the final segment; its filing absence is re-checked immediately before the positive run; no such cell (for any reason) means the isolated positive fixture plus a recorded live limitation; the segment after the artifact commit runs on a new gated revision holding the artifact, with a refreshed inventory, before its rehearsal | Task 6 |
| R2-02 | `--captures-of` looks up the current generation at the source period `PE0` (capture, extractor version, entity, basis, framework, extraction context), extracts once at `PE0` only where none matches, then writes only the `PE` attempt and missing interpretations over the stored occurrence ids; the integration test counts extractor calls | Task 3 |
| Open note 1 | The one-group refusal is described as a property of the public `compare run` builder, not of stored runs | Task 2 |

R2-02's bypass (`reuse=`, public context digests, extractor-call spies) is withdrawn by the
review 3 ruling below.

## Review 3 dispositions

| Item | Change | Section |
|---|---|---|
| R3-01 | **Orchestrator ruling (three rounds without convergence): the extraction bypass is removed, no version is bumped.** The bypass edited `vendor_ingest.py`, `vendor_screener.py` and `vendor_tijori.py`, which every vendor extractor source set hashes (`run_config.py` `VENDOR_EXTRACTORS`, `_sources_sha256`), so it forced coordinated version transitions across every vendor extractor and Phase 3's allocations. The parse it avoided is deterministic: the same extractor over the same retained bytes and binding yields identical occurrences, and storage reuses identical rows by capture, extractor version and anchor key and rejects a different payload (`repository.py` `_insert_occurrences`, `OccurrenceConflictError`). The evidence is therefore stored once in substance; the repo's "extract once" rule targets model extraction and stored results, not re-running a deterministic parser over the same bytes. `--captures-of` re-runs today's ingest per target, with its logic in `vendor_reingest.py` alone (hashed by no source set). `reuse=`, the context-digest renames and the call-counting spies are deleted. **Pin inventory: FIVE-1 edits no content-pinned file**, so it needs no transition and no coordination with Phase 3's reserved versions (`VENDOR-1-P3.md` "Version and pin inventory"); Task 7 checks this mechanically | Task 3; File map; Task 7 |
| R3-02 | Two passes. A check pass parses every cited capture's adapters with no target write, establishes target coverage per required vendor across all its sections (a quarter is covered by `QUARTERS`; annual sections lacking it do not count against it) and checks each parsed occurrence against any stored one under the same anchor. Only then the write pass runs today's ingest at `PE`. A refusal writes no row at any period; a failed section still records its failure and the others proceed. Tests: a June quarter on a March year-end, and a target missing only from the vendor ingested second | Task 3 |
| Note (partial interpretations) | Not reachable under re-parse. `_interpretations` (`vendor_ingest.py`) reuses when any row of the generation exists under the current pins, but each generation's rows come from one `put_interpretations` transaction (`repository.py`), so for a given occurrence set they are all present or none. A partial set needs the occurrence set itself to change under one extractor version, which means a different payload for a stored anchor (e.g. a changed fiscal-year-end month moving the annual periods); the check pass refuses exactly that before any write. No hashed edit and no version transition is needed | Task 3 |

**Out of scope:** running the five-company test (its protocol is `FIVE-COMPANY-TEST.md` §5–§6);
a standalone admit command (reading 3); fresh vendor fetches for back periods (reading 2); any
change to the Stage 4 freeze descriptor, holdout record, attempt-3 data or its e2e; Phase 2 and 3
content, including `VENDOR-1-P3.md`; live admission scope (FIVE-COMPANY-TEST §8 Q6, owner);
promoting any mapping (§7 there).

**Constraints:**
- Never open `stage4_holdout.yaml`, `stage4_manifest.yaml`, `data/holdout/` or `data/raw/onboarding/`.
  No new code path reads the holdout record or manifest; tests use synthetic sentinels.
- Minimal code: every module traces to a gap below; no speculative seams or guards.
- Files stay at most 800 lines. `onboard_cli.py` is at 800 and `discovery.py` at 789: Task 1 moves
  the freeze check out of `onboard_cli.py`; `discovery.py` stays at most 800.
- Standard data is code; nothing is derived, estimated or filled. A comparison-config identifier
  is written only from a retained capture that shows it.
- Tests follow `.claude/rules/python/testing.md`: integration through the public commands with a
  fake transport first; unit tests only for the sanction predicate.
- Mypy runs with `--cache-dir=/dev/null`; long gates run as `systemd-run --user` units.

**Leak check rule (F01, orchestrator ruling 3).** Before the first commit that contains a sanction,
config or test change naming any of the five symbols (Task 1's sanction and tests, Task 3's tests,
Task 4's entry), the orchestrator runs the Stage 4 leak check (`test_stage4_manifest.py::test_stage4_holdout[leaks]`, D1.6:
committed history since selection plus the current and untracked tree under `equity_os`, `src`,
`config`, `tests`) over a checkout holding those uncommitted changes, and again on the final tip.
It records PASS/FAIL only. A FAIL stops everything before commit and acquisition: nobody infers
which file or symbol failed, searches subsets or swaps a company; the orchestrator reports to the
owner. Neither implementer nor reviewer runs it.

**Shape:** Tasks 1–3 are code, one commit each after the orchestrator verifies them; Task 5 is a
recorded fact; Task 6 amends documents; Task 7 gates. Sol reviews this plan, then once at phase end
(after Task 7), closed by one fresh critical review. Task 4 waits on Phase 3 Task 11's captures and
lands after the review as a routine, orchestrator-verified config change. **FIVE-1 writes nothing
live**; its commands are used live by Phase 3 Task 11 and the five-company test under their
protocols, with the additions in "Live protocol" below.

**Estimate:** about 18.5 summed hours (author's estimate, not measured).

| Task | Implementer | Hours |
|---|---|---|
| 1. Sanctioned acquisition route | Opus | 4.5 |
| 2. Replayable entity-bound fetches (`compare fallback --generation`) | Opus | 2.5 |
| 3. Named-period acquisition and vendor re-ingest | Opus | 3.5 |
| 4. ICICIBANK in the comparison config | Sonnet | 1 |
| 5. MTARTECH series | — | 0 |
| 6. Document amendments | Sonnet | 1 |
| 7. Gate | orchestrator | 1 |
| Sol loops (plan, phase end), closing review | — | 5 |

## Readings

1. **What the freeze protects, and why a re-freeze is wrong.** D6 closed 2026-10-17 (`D6.md`
   "D6 Freeze" step 6): attempt 3 stands as evidence that the *frozen* implementation onboarded
   the held-out company; later phases may change implementation paths; the Stage 4 e2e replays
   attempt 3 and never uses `--acquire`. `_frozen`/`_check_entry` still bind `--acquire` to the
   current held-out attempt, an `APPROVE`d descriptor and no implementation commit since it, so
   every VENDOR-1 commit fails it. What must survive is (a) the append-only descriptor and holdout
   record and attempt 3's chain, (b) attempt 3's retained data and replay, and (c) the opacity of
   the held-out identity (D1.6 leak scan, D1.7). A re-freeze would mix development acquisitions
   into the held-out evidence chain; rejected. The sanction route never calls `frozen`,
   `_check_entry` or any holdout/manifest reader. An acquisition stays attributable to committed,
   reviewed code (a recorded gated tip) and a reviewed authorisation (the stamped sanction).
2. **Vendor captures need no back-period fetch.** A Screener or Tijori financials page carries
   many quarters and years (inferred from 6,541 Apar occurrences against 9 packages); extraction
   already stores occurrences for every period on the page under their own periods. A run's vendor
   side, however, reads the latest *attempt* at its own period end (`vendor_sides._latest`), so
   "vendor evidence for a named period" is an attempt at that end citing a capture that holds
   occurrences for it. Only first-party filings are fetched per period.
3. **No admit command.** `run_fallback` calls `admit_run` on the run before collecting triggers,
   triggered or not (`fallback.py`, read), so `compare fallback --run <id>` admits every run it is
   given and is a write even when it fetches nothing. FIVE-COMPANY-TEST §5.4 stands.
4. **One version set for all five: dictionary v5, mapping set v12**, the last Phase 3 sets
   (`VENDOR-1-P3.md` Tasks 6, 12; renumbered 2026-11-06 because the results-PDF fixes
   `eqos-djv/ghv/dol/n21` take dictionary v4 and mapping set v10 first). The check class digests
   dictionary, mapping set, policy, extractors and issuer class (`vendor_first.check_class`, read), so v5/v12 does not pool bank and
   non-bank evidence; classes stay distinct by canonical id, basis, framework and issuer class.
   **Consequence:** Apar's eligibility `v1` (classes under v2/v9 and the pre-Phase-3 extractors)
   matches no class of the test's runs, so the test's first runs cannot admit under §6.5 row 3;
   Apar's Task 14 counts are the numeric baseline only; Apar is re-ingested live under v5/v12 like
   the others. `measure` reads every policy-pinned stored run, older classes included
   (`eligibility.py`), so the test reports final-pin classes separately. Apar's pilot pins and `v1`
   stay byte-unchanged. Row 3 under the final pins is exercised by the test's final-pin segment
   (Task 6, F04).
5. **Named periods are bounded by onboarding's settings.** `vendor reingest` and runs read
   `FISCAL_YEAR_END_MONTH` with `valid_from <= period_end`, and onboarding's `valid_from` is the
   earliest filing period it read (`derived_settings.py`, read). A named period before that
   refuses (`no fiscal-year-end month`); accepted as the bound, not extended.

## File map

| File | Change | Task |
|---|---|---|
| `equity_os/interface/commands/companies/acquisition_authority.py` | create: `frozen` (moved verbatim with `SOURCE_CHECKOUT`, `IMPLEMENTATION_PATHS`, helpers), `ordinary_roots`, `sanctioned` (Task 1); `entity_fetch` (Task 2) | 1, 2 |
| `equity_os/interface/commands/companies/onboard_cli.py` | modify: `--sanction`, call the module, `_argv`; net fewer lines | 1 |
| `config/acquisition/sanctions/five-company.yaml` | create: payload and stamp | 1 |
| `equity_os/companies/onboarding/discovery.py` | modify: entity-fetch mode for `write_generation` and `replay_fetch` | 2 |
| `equity_os/interface/commands/verification/compare_cli.py` | modify: `fallback --generation N` through `entity_fetch` | 2 |
| `equity_os/verification/admission/fallback.py` | modify: `_acquire`, `_ingest` public as `acquire_group`, `ingest_group` (returns the report); one-group guard | 2, 3 |
| `equity_os/interface/commands/extraction/evidence_cli.py` | modify: `evidence acquire` action | 3 |
| `equity_os/interface/commands/sourcing/vendor_reingest.py` + its CLI registration | modify: `--captures-of` (check pass, then today's ingest) | 3 |
| `config/coverage/watchlist.yaml` | modify: ICICIBANK entry | 4 |
| `docs/plans/FIVE-COMPANY-TEST.md`, `CONTEXT.md` | modify | 6 |
| Tests: `tests/equity_os/support/onboarding_support.py`, `test_onboarding_acquisition.py`, the fallback test beside `fallback.py`'s existing one, the `vendor reingest` test, watchlist-loading tests that pin the stock list | modify/extend | 1–4 |

**No content-pinned file (R3-01).** No file above is in a hashed extractor source set
(`run_config.py` `EXTRACTOR_SOURCES`, `SHP_EXTRACTOR_SOURCES`, `VENDOR_EXTRACTORS`). No FIVE-1
change alters how pinned inputs become results, so `_SEMANTICS_VERSION` stays. Phase 3's reserved
versions are untouched.

## Task 1: Sanctioned acquisition route

Goal: `eqos onboard <SYMBOL> --acquire --sanction <path>` acquires a new generation for a symbol a
committed, stamped sanction lists, recording the sanction instead of a freeze; the freeze route
and every Stage 4 check are unchanged.

Files:
- Create: `acquisition_authority.py`; `config/acquisition/sanctions/five-company.yaml`
- Modify: `onboard_cli.py`; `tests/equity_os/support/onboarding_support.py`
- Test: `test_onboarding_acquisition.py` (integration, tmp git repo as the freeze tests use);
  one parametrized unit test of `sanctioned`

Interfaces:
- Produces: `frozen(descriptor: Path, config_root: Path) -> dict[str, Any]` (today's `_frozen`,
  same output); `ordinary_roots(*roots: Path) -> None` (refuses a root that resolves, symlinks
  followed, under `SOURCE_CHECKOUT/data/raw/onboarding` or `SOURCE_CHECKOUT/data/holdout`; no
  filesystem access beyond `resolve`); `sanctioned(path: Path, config_root: Path, symbol: str)
  -> dict[str, Any]` returning `{"sanction": <repo-relative path>, "sanction_sha256",
  "acquisition_head"}`; generation authorisation string `sanction <path>@<head>`.
- Sanction schema: `{symbols: [str], purpose: str, plan: str, plan_commit: str, review: {reviewer,
  verdict, date, review_commit, payload_sha256}}`. `payload_sha256` is the sha256 of
  `yaml.safe_dump({symbols, purpose, plan, plan_commit}, sort_keys=True)` (the D1.1 payload rule).

Approach: move `_frozen`, `_check_entry`, `_tree`, `_freezes`, `_git` and the constants they use
to the new module unchanged (`onboard_cli` imports `frozen`). `sanctioned` refuses unless: the
resolved file lies in `<running checkout>/config/acquisition/sanctions/` and `--config-root` is
the checkout's `config` (as `frozen`); `git status --porcelain` over `IMPLEMENTATION_PATHS` is
empty and the bytes at that canonical repo-relative path equal `HEAD`'s blob; its fields are
exactly the schema's; `payload_sha256` matches; `plan_commit` and `review_commit` are ancestors of
`HEAD`; `review.verdict == APPROVE`; the symbol is listed. `ordinary_roots(raw_root,
snapshot_root)` runs first. `--sanction` and `--freeze-descriptor` are mutually exclusive;
`--acquire` needs one. `acquisition.json` carries the sanction fields and no `attempt`, so it can
never be read as held-out evidence.

The committed sanction's payload is fixed by this plan, so the plan's `APPROVE` covers exactly
it: `symbols: [APARINDS, ICICIBANK, LAURUSLABS, MTARTECH, NETWEB]`, `purpose: owner order
2026-11-05 step 4, five-company test`, `plan: docs/plans/FIVE-1-enablement.md`, `plan_commit`:
the commit of the Sol-approved plan text. The orchestrator stamps `review` with Sol's actual
verdict and `review_commit`, the commit that records that `APPROVE` in the repo. The stamp
authorises the symbols and purpose only, never an implementation: which code may acquire is the
gated tip rule in "Live protocol". A new symbol is a new sanction file, payload and review. The
leak check rule runs before the commit holding the file.

Verification: `uv run --no-sync pytest -n 4 tests/equity_os/companies/onboarding/test_onboarding_acquisition.py`
and the onboarding suite green: sanctioned acquire then replay is identical; refusals for an
unlisted symbol, a non-`APPROVE` verdict, a payload digest mismatch (a copied stamp over a changed
symbol list), an uncommitted or edited sanction, an otherwise valid committed sanction outside the
sanctions directory, a symlink there resolving outside it, a root under either protected
directory and a symlink into one (synthetic checkout, no real protected data), both or neither
authorisation flag; a sentinel holdout record in the synthetic checkout is never opened by the
sanction route. Existing freeze tests keep their scenarios and assertions; only their
`SOURCE_CHECKOUT` patches (`onboarding_support.py`, the `other_checkout` case) move to
`acquisition_authority`, and the `other_checkout` case still refuses on the checkout check.
`wc -l onboard_cli.py` < 800.

Dependencies: none.

Risks: a moved function's behaviour drifting; the move is verbatim and the existing freeze tests
are the characterisation. Phase 3 Tasks 1, 5, 7, 12 also edit `onboard_cli.py`; see Interleaving.

## Task 2: Replayable entity-bound fetches

Goal: `compare fallback` writes every fetch it makes as a generation under `--raw-root`, and
`--generation N` replays one without opening a socket, so a live fallback can equal its rehearsal
(FIVE-COMPANY-TEST §8 Q4).

Files:
- Modify: `discovery.py`, `acquisition_authority.py`, `compare_cli.py`, `fallback.py`
- Test: the existing fallback integration test, extended; onboarding replay tests

Interfaces:
- Consumes: `acquiring_fetch`, `replay_fetch`, `write_generation`, `live_transport`, `now`.
- Produces: `DiscoveryManifest.as_of: date | None`; `write_generation(..., entity: bool = False)`
  and `replay_fetch(folder, *, entity: bool = False)`; `compare fallback ... [--generation N]`;
  `entity_fetch(raw_root: Path, generation: int | None, issuer: str, authorization: str, send:
  Callable[[], Send]) -> tuple[Fetch, Callable[[], None]]` (fetch, and the writer to call after the
  work) in `acquisition_authority.py`; the caller passes `live_transport`, so existing test patches
  of `onboard_cli.live_transport` still apply.

Approach: default mode is today's onboarding rule, unchanged: exactly one NSE master entry and a
non-null `as_of` equal to its retrieval date, on write and replay. Entity mode writes `as_of: null`
and replay requires `as_of` null and no master entry. Only `entity_fetch` uses entity mode.
`entity_fetch` calls `ordinary_roots(raw_root)` first, then replays `gen-N` or acquires and
writes `gen-<next>`. Every request in a generation stays unique (`replay_fetch`'s duplicate
refusal is kept): `run_fallback` refuses before any fetch when more than one group triggers,
because each group requests the same two listings (`results_filing.acquire_results`). This is a
property of the bounded public interface, not a stored-run invariant: `RunScope.period_ends` and
`.bases` are tuples (`run_models.py`), but the public builder `run.request_for`, which `compare
run` uses, makes one entity, period end and basis, and fallback groups result rows, not the
earlier operands a year-end run loads, so an ordinary run triggers at most one group. Fallback
needs no sanction: spec §6.8 scopes it to the triggering run's own issuer and periods.

Verification: fallback acquire (fake transport) then replay of the written generation gives equal
outcomes, captures and packages on two fresh `eqos_test_*` databases; an altered body refuses; a
two-group run refuses before fetching; protected raw/snapshot roots and symlinks into them refuse
on acquire and replay; onboarding replay refuses `as_of: null` with a master, a missing master and
a wrong date; an entity generation replays only in entity mode; existing onboarding replay tests
unchanged.

Dependencies: Task 1 (same new module).

## Task 3: Named-period acquisition and vendor re-ingest

Goal: for an onboarded entity, `eqos evidence acquire --entity <KEY> --basis <b> --period-end <PE>
--mapping-set <m> --dictionary <d> --snapshot-root <dir> --raw-root <dir> [--issuer-config <yaml>]
[--generation N]` fetches and ingests one named period's results filing exactly as the fallback
does, one period per command and generation; and `eqos vendor reingest ... --period-end <PE>
--captures-of <PE0>` records vendor evidence at `PE` from the captures cited at `PE0`.

Files:
- Modify: `fallback.py`, `evidence_cli.py`, `vendor_reingest.py` and its CLI registration
- Test: one integration test per command over retained Apar-like fixtures with a fake transport

Interfaces:
- Consumes: `acquire_results`, `entity_fetch` (Task 2), `load_run_config`, `ordinary_roots`.
- Produces: `acquire_group` (today's `_acquire`, renamed); `ingest_group(...) -> IngestReport |
  None` (today's `_ingest` returning the `ingest_first_party` report, `None` on `IntakeError` or
  `IngestError`); `ingested(report: IngestReport | None) -> bool` (today's success predicate,
  used by `run_fallback`); `reingest(..., captures_of: date | None = None)`.

Approach: the `evidence acquire` action resolves `<KEY>` to one entity (unknown refuses before
transport), calls `ordinary_roots` and `entity_fetch` (authorisation `named-period acquisition of
<KEY> <PE>`), then `acquire_group` and `ingest_group` for `(entity, PE, basis)`; `acquire_group`
already refuses unless the entity holds exactly one NSE symbol and one ISIN. No run, admission or
outcome row is written; no holdout lookup. It prints `<PE> package <id>` from
`report.package_id`, `FILING_UNAVAILABLE` (no filing) or `FILING_UNRESOLVED` (intake refused or an
extraction failed), and exits `INCOMPLETE` unless ingested. The identity, basis, PDF-hash,
per-period settings and extraction-failure checks are fallback's, unchanged. `--mapping-set` and
`--dictionary` are required, so no default can split versions.

`--captures-of PE0` selects the captures by the attempts at `PE0` (default `--period-end`, today's
behaviour). Without the flag, behaviour is today's. With it, `reingest` runs two passes, all in
`vendor_reingest.py`; no extractor, ingest or storage file changes (R3-01):

1. **Check pass (no attempt, occurrence or interpretation write).** For every cited capture, read
   its verified body and build `_adapters` as today, with the fiscal-year-end month at `PE`. Compare
   each adapter's version pin read-only against any stored one (`vendor_extractor_pin`; drift
   refuses), then call its extract on the body. *Orchestrator ruling (closing review 5): no
   writes on refusal wins over the earlier `pin_versions` call here, which committed pins and
   advanced `version_pins_id_seq` on refusal; pins are registered only after the check pass, by
   the write pass's `ingest_vendor`.* An adapter
   raising `VendorExtractionError` with outcome `IDENTITY_REJECTED` is a capture, entity or basis
   refusal (`vendor_tijori.py` `_NO_BASIS`; `vendor_screener.py` identity and basis checks). It is
   fatal: the command exits `INCOMPLETE` naming the capture, with nothing written (R4-01). Any other
   `VendorExtractionError` is a section failure. That adapter contributes nothing here, and pass 2
   still ingests it and records its failure attempt as today. Then, before any write:
   - **Coverage per required vendor.** For each of Screener and Tijori, the union of its adapters'
     occurrences, across every section and cited capture, must hold an occurrence whose period
     ends at `PE`. Section filtering stays each adapter's own, as today: a Screener section's parse
     yields only that section's rows, and its attempt cites only those. A quarterly target is
     covered by `QUARTERS`; `PROFIT_LOSS`, `CASH_FLOW` and `BALANCE_SHEET` lacking it (annual ends,
     own instants, `vendor_screener._period`) do not count against it.
   - **Stored agreement.** A parsed occurrence whose capture, extractor version and anchor key are
     already stored (`list_capture_occurrences(capture, version)`) must equal that row without its
     id, which is storage's own rule.

   Any failure exits `INCOMPLETE` naming the gap, with nothing written at any period.
2. **Write pass.** Today's per-adapter `ingest_vendor_retained` at `PE`, unchanged. The same
   extractor re-parses the same verified bytes under the same binding, so it yields the
   occurrences pass 1 checked. `put_generation` reuses the stored identical rows (same ids, own
   periods, `UNKNOWN` knowledge time, the capture's first-seen time from `put_capture_ref`) and adds
   one `PE` attempt per adapter; `_interpretations` reuses the generation's rows under the current
   pins, or writes them all.

**Why this order.** `put_generation` commits each adapter's generation separately
(`repository.py`), so any check left to the per-adapter loop could follow an earlier adapter's
committed `PE` attempt. Coverage and payload agreement are therefore settled before the first
write. The check pass does not ingest at `PE0`: doing so would add a `PE0` attempt on every
command and move what `PE0` runs read (`vendor_sides._latest`). A few refusals stay
write-pass limits, as today: a capture already or newly expired or purge-pending whose bytes remain
(`ingest_vendor_retained`); evidence the insertion gate rejects (`discovery_gate.py`); and a store
error. They fall outside this guarantee and may leave earlier adapters' `PE` attempts committed. Without stored agreement, a changed binding
(for example a different fiscal-year-end month at `PE`) would raise `OccurrenceConflictError`
part-way through, or leave a generation's interpretations partial (Review 3 note). The command
re-parses each capture twice per target; the parse is deterministic and cheap, so this is accepted.

It exits `INCOMPLETE` naming the gap, before writing, when no capture is cited at `PE0`, or when
Screener or Tijori has none. Nothing is relabelled; no new vendor fetch (reading 2). Periods before
onboarding's earliest `valid_from` refuse (reading 5).

Verification: named-period acquire then replay ingests equal packages and prints the stored
package id; a period with no filing prints `FILING_UNAVAILABLE` and a failed intake
`FILING_UNRESOLVED`, both `INCOMPLETE`; a period before the settings window refuses; the new
package's knowledge time is the acquisition's, so an `AS_KNOWN` run at an earlier cutoff does not
select it; an unknown entity and a protected root refuse with no request sent. `vendor reingest
--captures-of`: a target the capture holds yields a `PE` attempt per adapter whose occurrences
carry their own source periods, with the capture's original availability and `UNKNOWN` vendor
knowledge time; the new interpretations are invisible at earlier `AS_KNOWN` cutoffs. **Stored
once:** after a first target `PE1`, a second target `PE2` over the same captures leaves the
capture's occurrence rows and interpretation rows unchanged in count; its attempts cite the same
occurrence ids as `PE1`'s; and it adds exactly one attempt per adapter at `PE2` and none at any
other period. **Non-year-end target:** on a March year-end entity, a June quarter that `QUARTERS`
holds and the annual sections lack succeeds, with an attempt for every section. **Missing target
with no partial write:** a target held by Screener but not Tijori (Tijori ingested second in
today's order) exits `INCOMPLETE` with attempt, occurrence and interpretation counts unchanged at
every period; so does a target in no section. **Stored disagreement:** a fiscal-year-end month at
`PE` differing from the one the stored generation used exits `INCOMPLETE` with nothing written.
A Screener section whose adapter refuses with a non-identity outcome records its failure attempt
at `PE` while the other sections proceed. **Mixed captures (R4-01):** one valid and one
basis-rejected capture for the same vendor, with target coverage from both vendors, exits
`INCOMPLETE` with attempt, occurrence and interpretation counts unchanged at every period. Absent source captures, an absent vendor and a basis mismatch each exit
`INCOMPLETE` with no write; without the flag the existing reingest test is unchanged; fallback
tests unchanged.

Dependencies: Task 2.

Risks: Phase 3 Task 7 edits `fallback`'s acquire/ingest (source argument, per-entity framework)
and Tasks 7, 12 edit `vendor_reingest.py`: FIVE-1 lands first and Phase 3 rebases onto the public
names, which gives named-period ingest the bank framework too. Until then `ingest_group` fixes
`IND_AS`, so named-period ingest is non-bank only.

## Task 4: ICICIBANK in the comparison config

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

Approach: each value is copied from the named capture by a read-only query. A required identifier
no capture shows blocks the entry: it is not added and the gap is recorded. This is the comparison
config only, not product watchlist membership or a coverage decision. The leak check rule runs
before its commit.

Verification: the updated tests pass; the commands that iterate the comparison config (coverage,
validate) refuse ICICIBANK with a reason where a bank is unsupported, not a crash; coverage
decisions are unchanged.

Dependencies: Phase 3 Task 11. Lands after the FIVE-1 review (routine, orchestrator-verified).

## Task 5: MTARTECH series

Settled, no code: the retained NSE master metadata the orchestrator checked on 2026-11-06 lists
all five symbols as series `EQ`. MTARTECH stays in the sanction and FIVE-COMPANY-TEST §5.1 expects
its ordinary outcome. If the master on the acquisition day differs, onboarding's existing
`master_rows` refusal is the observed outcome, recorded and reviewed; nothing widens to `BE`.

## Task 6: Document amendments

Goal: the five-company protocol names the routes this plan builds and the scenarios review 1
requires. FIVE-1 does not edit `VENDOR-1-P3.md` (its Task 11 already names `--sanction`).

Files: `FIVE-COMPANY-TEST.md`, `CONTEXT.md` (one entry: *acquisition sanction*).

`FIVE-COMPANY-TEST.md` edits:
- §3 rows for Q1, Q3 closed; §5.1 `--acquire --sanction` acquisition and `--generation` replay;
  every command `--dictionary v5 --mapping-set v12`; §8 Q1, Q3–Q5, Q7 answered by this plan.
- **Periods and roles (Q5, F09).** Per entity and basis, `commands.txt` enumerates the period ends
  that both vendors' captures cover and onboarding's settings window admits (read-only queries
  saved beside it; settings never extended), and freezes each one's role: (a) *filing-check*:
  `evidence acquire` then `vendor reingest --captures-of`, both before its run; (b)
  *fallback*: a genuinely vendor-only period, with `vendor reingest --captures-of` but **no**
  `evidence acquire`, run, then `compare fallback` acquires it; (c) the fresh post-fallback rerun
  fallback creates; (d) *final-pin positive* (R2-01): an evidenced cell where both vendors agree
  and no admissible filed value exists, in a class that can qualify from the (a)–(c) checks alone,
  with **no** `evidence acquire` and no fallback for that cell before the final-pin segment.
  §5.5's expectations become refusal-derived: a run's trigger groups are its
  stored `CHECK_REQUIRED`, `VENDOR_UNMAPPED`, `VENDORS_DISAGREE`, `VENDORS_IMPRECISE` refusals, so
  a filing-present run may still trigger. If live history offers no package-free eligible period,
  the fallback branch is shown on the isolated rehearsal fixture and the live limitation reported;
  live evidence is never deleted to make one.
- **Final-pin segment (F04, Q6), after §5.6.** Sol reviews and the orchestrator commits the
  measured draft as a new eligibility version (never `v1`, never backdated, no mapping promoted,
  BANK classes excluded as Phase 3 specifies). **Artifact boundary:** `commands.txt` then names a
  new gated revision that contains that artifact (the loaded config tree, `run_config.py`), and
  the remaining commands are re-inventoried on it before this segment's rehearsal; the
  equal-revision rule applies to that revision, and nothing runs the artifact from the older
  tree. Immediately before the positive run, a read-only query saved beside `commands.txt` shows
  the role-(d) cell still has no admissible filed value. Fresh runs at a cutoff at or after its
  `available_from`, over the role-(d) periods, then admit. **Pass:** the role-(d) cell admits as `VENDORS_AGREE_NOT_CHECKED` with
  both witnesses and the artifact pin; its citation shows the label; a calculation over it shows
  the weaker label. On isolated rehearsal copies: the same cell at a cutoff before
  `available_from` refuses, and a counterexample in the class blocks it. If no suitable live
  role-(d) cell exists, whether no class qualifies, no vendor-only agreeing input remains, or the
  pre-run query finds a filed value, the limitation is recorded and the positive case runs on a
  clearly identified isolated fixture; live unchecked admission is then not claimed. Evidence is
  never deleted and no cutoff is backdated to make a cell.
- Reading 4's consequence in §5.6: final-pin classes reported separately from older classes.

Approach: edits only.

Verification: `grep -n freeze-descriptor docs/plans/FIVE-COMPANY-TEST.md` shows only the
historical mention; structural checks in `.claude/project/verification.md` pass.

Dependencies: Tasks 1–3.

## Task 7: Gate

Goal: the tip holding Tasks 1–3 and 6 passes `scripts/verify.sh gate five-1` (log and revision in
`scratchpad/five-1/gate/`), mypy strict and ruff clean; `git diff --name-only <base>..<tip>` names
no file in `EXTRACTOR_SOURCES`, `SHP_EXTRACTOR_SOURCES` or `VENDOR_EXTRACTORS` (R3-01); and the
orchestrator runs the leak check
on that tip and `test_data_stage4_e2e.py` (attempt-3 replay) where the protected data exist,
recording PASS/FAIL only.

Verification: gate exit 0; both Stage 4 suites PASS. A FAIL stops as the leak check rule says.

**Amendment (orchestrator ruling, 2026-11-06; Sol phase-end review 1, F5).** This amendment
replaces "gate exit 0" above.
- **Red proof not applicable.** Under the 2026-10-11 testing policy (tests are written with the
  code; `.claude/rules/python/testing.md`), the gate's red-proof line does not apply to FIVE-1.
  Its `ROUTE: CONTRACT` result is expected and recorded as such; no retrospective red evidence is
  made.
- **Pass condition.** Task 7 passes when the gate's pytest, ruff, format, mypy, skips and rails
  lines are all OK on one revision R. The only pytest exceptions are the Stage 4 tests that need
  protected inputs absent from the gate worktree, which are never copied there.
- **Stage 4 on R.** The orchestrator runs those Stage 4 tests (the leak check and
  `test_data_stage4_e2e.py`) on the main checkout while main's `HEAD` equals R. It records R, each
  exit status and an opaque PASS or FAIL only.

Dependencies: Tasks 1–3, 6.

**Then: Sol phase-end review** of the FIVE-1 diff, the gate log, the call graph of the new
authority routes and the orchestrator's Stage 4 PASS records, by the loop in
`.claude/rules/core/04-agent-stack.md`, then one fresh closing review. After `APPROVE`: refresh
`docs/status/dashboard.html`, record the verdict on `eqos-awnc`, file beads for anything parked.
Task 4 follows Phase 3 Task 11.

## Live protocol

FIVE-1 writes nothing live. Its fetching commands, when Phase 3 Task 11 or the five-company test
use them, follow `VENDOR-1-P1.md` "Live protocol" steps 1–6 and `VENDOR-1-P3.md`'s acquisition
boundary: each fetching command runs once as an acquisition against a throwaway `eqos_test_*`
restored from the baseline backup, with scratch copies of both roots; rehearsal and live replay
the same generation (`--generation N`, its manifest sha256 in `commands.txt`); new files under
both roots (path, sha256) must equal the rehearsal's. Additions:

- **Gated tip (F08, F13).** `commands.txt` names the gated tip the commands run on: FIVE-1's
  reviewed gate tip, or a later phase's gated tip under that phase's protocol (Phase 3 Task 11 on
  its Task 10 tip). Acquisition, rehearsal and live each record `git rev-parse HEAD` and the
  `config/` tree id, and all equal that tip; an onboarding generation's recorded
  `acquisition_head` (`acquisition.json`) equals it, and each entity acquisition's HEAD and
  `config/` tree id, recorded in `commands.txt` with its generation number and manifest sha256,
  equal it. Before every command the working tree must also be clean over `IMPLEMENTATION_PATHS`
  and the config root (empty `git status --porcelain`), and the inventoried config root must be
  the gated checkout's `config/`; `entity_fetch` refuses uncommitted implementation paths on
  acquisition and replay (closing review 7). Any difference stops before the next command.
- **Windows.** Live write windows are mutually exclusive across FIVE-COMPANY-TEST, VENDOR-1 phases
  and anything else, as Phase 3's windows rule states.

Allowlist rows, fixed before the rehearsal and never widened from its output (an unexpected table
is a reviewed amendment):

| Command | Tables allowed to change |
|---|---|
| `onboard --sanction` replay | as Phase 3's `onboard` replay row |
| `evidence acquire` replay | captures (`capture_refs`, `capture_addresses`, `retention_classes`, the last by 0027's `classify_capture` trigger on each new capture); document intake (`document_listings`, `document_observations`, `document_attempts`, from `announcement_documents`, with or without `pdf_parse`); package and extraction tables as Phase 3's `evidence ingest` row; `version_pins` |
| `vendor reingest --captures-of` | as Phase 3's `vendor reingest` row |
| `compare fallback` replay | as `evidence acquire` (captures `capture_refs`, `capture_addresses`, `retention_classes`), plus the `compare run` row's tables, `fact_stores`, `fact_store_events`, `fact_rows`, `fact_selections`, `fact_admissions`, `vendor_counterexamples`, `vendor_fallback_outcomes` (derived from `admit_run`'s write paths before the rehearsal) |

Each listed table's own sequence may advance, no other. Coverage decisions and watchlist
membership must be unchanged after every command.

## Dependency order and interleaving

1 (leak check, then commit) → 2 → 3 → 6 → 7 → Sol review ; Phase 3 Task 11 → 4 (leak check,
then commit). Task 5 is settled.

With VENDOR-1 (orchestrator rulings 1–2):
- **Phase 1 Tasks 9, 10:** FIVE-1 code starts after both land; Task 3 builds on Task 10's
  `fallback.py` and `results_filing.py` as on `main`. FIVE-1 does not touch `interface/entry/cli.py`.
- **Phase 1 Tasks 13–14 (live window):** FIVE-1 implementation may proceed in worktrees. No FIVE-1
  commit lands on the main checkout from the start of Phase 1 Task 13 until Task 14 completes.
- **Phase 2:** no shared files expected.
- **Phase 3: serialised by file, not by plan.** FIVE-1's edits to `onboard_cli.py`,
  `discovery.py` and `fallback.py` land before any Phase 3 task edits those files; Phase 3 tasks
  touching none of them proceed. Phase 3 Task 11 is gated on FIVE-1 Tasks 1–2 and FIVE-1's reviewed
  gate. Phase 3 updates its own imports and test seams for the moved authority module.
- **Five-company test:** starts after Phase 3 Task 13 (v5/v12 and the extractor bumps final) and
  FIVE-1 Task 4, with every command under v5/v12 (reading 4).

## Self-review

- **Gap coverage:** 1 freeze route → T1, T7, reading 1; 2 named periods → T2, T3, readings 2, 5;
  3 admit → reading 3 (no task); 4 comparison config → T4; 5 MTARTECH → T5 (settled `EQ`); 6 one
  version set → reading 4, T3 (required flags), T6.
- **Names:** `frozen`, `ordinary_roots`, `sanctioned` (T1); `entity_fetch`, entity mode (T2) → T3;
  `acquire_group`, `ingest_group`, `ingested`, `captures_of` (T3) → Phase 3 Task 7.
- **Placeholders:** none; `plan_commit` and `review_commit` are filled at stamping.
