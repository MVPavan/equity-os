# Learnings

Durable, verified, likely-to-recur patterns for **this** repo. Capture only
after a verified fix or a repeated pattern — not speculation. Keep each entry
short: what was observed, why it matters, how to apply it.

Format per entry:

```
## <short title>  (<YYYY-MM-DD>)
- Observed: <what happened / the pattern>
- Why it matters: <consequence>
- Apply: <concrete guidance>
```

## Stale `sync.remote` in `.beads/config.yaml` breaks `bd init`  (2026-08-12)

- Observed: at adoption the working-tree `.beads/config.yaml` carried another
  repo's `sync.remote` (`agent-os.git`, nonexistent); `bd init` tried to clone
  it and failed with "Repository not found". Corrected the remote, init
  succeeded. (Why the earlier init commit f881e51 was reverted is not
  recorded — its committed config already had the correct remote.)
- Why it matters: `bd init` fails closed on a wrong/unreachable `sync.remote`.
- Apply: when adopting into a new repo, set `sync.remote` to the repo's own
  git remote **before** running `bd init`.

## A `time.sleep` default argument defeats every `monkeypatch` of it  (2026-09-03)

- Observed: extracting `RequestPacer` (eqos-zfu) gave `wait_for_slot` the
  signature `sleep: Callable[[float], None] = time.sleep`. Python evaluates a
  default at function-definition time, so the real `time.sleep` was captured at
  import. `tests/fundamentals/test_screener_session.py` patches
  `fundamentals.ingest.screener_session.time.sleep` — that patch mutates the
  shared `time` module and had worked for years, but it could not reach an
  already-bound default. The suite really slept 1.5 s and the spacing assertion
  failed (2.28 s run, down to 0.74 s after the fix).
- Why it matters: the failure mode is a *slow, flaky* test, not a clear error.
  Had the assertion been looser it would have passed while silently sleeping —
  the same trap hides in any injected clock, sleeper, or `now()`.
- Apply: never bind a patchable callable as a default argument. Default to
  `None` and resolve inside the body (`wait = time.sleep if sleep is None else
  sleep`). Applies equally to `datetime.now`, `uuid4`, and `random`.

## `mypy --strict` catches `config or Default()` aliasing bugs  (2026-09-03)

- Observed: in the same extraction, `__init__` read
  `RequestPacer(config.min_request_spacing_seconds)` one line after
  `self._config = config or ScreenerSessionConfig()`. Every test passes a
  config, so 1,284 tests stayed green; the default-constructed path would have
  raised `AttributeError`. mypy flagged it as `union-attr`.
- Why it matters: the `x or Default()` idiom leaves the narrower parameter in
  scope, and reading the parameter instead of the attribute is invisible to a
  test suite that never exercises the default.
- Apply: after `self._x = x or Default()`, read `self._x` for the rest of the
  constructor. Run `mypy --strict` before trusting a green suite on any
  constructor change.

## A filtered source may not report a namespace absent  (2026-09-04)

- Observed: the Upstox entity adapter (Slice 1, eqos-rdb) emitted
  `reported_absent=(BSE_SCRIP,)` whenever its rows carried no BSE listing.
  `entity_map.py:303` derives `Entity.conflicted` from any `CONFLICTED`
  namespace, and `_coverage` treats "source reported absent" as an assertion
  that conflicts with any stated value — so a correctly pinned stock became
  conflicted and `EntityMap.lookup` returned `None` for it. The slice's own
  headline acceptance test caught it: the entity re-keyed to its ISIN exactly
  as designed and was then unreachable.
- Why it matters: the adapter reads a *filtered* catalog (only `NSE_EQ`/`EQ`
  and `BSE_EQ`/`A` rows are retained). Absence in our rows is our filter, not
  the vendor's silence. Reporting it as vendor silence states our own
  processing as a source claim, and the map is built to trust exactly that
  distinction — so the lie propagates into an unreachable entity rather than
  into a visible error. Slice 1 would have removed a lookup path while
  claiming to add one.
- Apply: only a source that carried the whole namespace and published nothing
  may set `reported_absent`. If any of your own filtering, sampling or
  projection could have emptied it, emit nothing — that is
  `MissingReason.NOT_SUPPLIED`, which is the truth. Check this whenever a new
  `SourceRecord` producer is written.

## A trading series is not a security type  (2026-09-04)

- Observed: the Upstox instrument filter retained `NSE_EQ`/`EQ` and
  `BSE_EQ`/`A`, the two combinations the schema census had counted. On the
  first live entity-map build, 2 of 10 pinned watchlist stocks (HFCL,
  MTARTECH) were missing. Both trade in NSE series `BE` and BSE group `T` —
  trade-to-trade. A full scan then showed the filter was wrong in both
  directions: it dropped real companies, and `NSE_EQ`/`EQ` itself carries 176
  ETFs (`INF` issuers) that it was admitting as listed companies.
- Why it matters: the failure was **silent**. No anomaly, no schema drift, no
  count that looked wrong — the rows simply were not there, and the entity map
  reported 0 conflicts while being blind to two of the ten stocks the whole
  system exists to track. A filter that drops rows can only be checked against
  something you already know should be present.
- Root cause: a census enumerates the categories that *happened to be counted*.
  Turning that enumeration into a filter encodes the sample as the population.
  `instrument_type` is a trading-restriction series (137 distinct values inside
  the two cash segments); it says how a security may be traded, not what it is.
- Apply: filter on what the data *declares itself to be*, not on a category
  list. Here the ISIN carries it — `INE` (company) plus issue-type `01` (equity
  shares), both required. When you must filter, write a test that asserts a
  known member of the population survives it, and prefer a known-awkward member
  (a suspended stock, a trade-to-trade stock) over a typical one.

## An empty success payload can mean "no such entity"  (2026-09-04)

- Observed: the Upstox Lane B verification asked `/v2/fundamentals/{isin}/
  corporate-actions` for a fabricated ISIN. It answered HTTP 200 with
  `{"status":"success","data":[]}` — byte-identical to a real company that has
  no corporate actions. The integration plan had proposed exactly the guard this
  defeats: *"`OK_EMPTY` requires `status == "success"` and `data == []`"*.
- Why it matters: a typo'd or stale identifier reads as a true negative. The
  sweep completes, the report is clean, and the company is simply missing —
  which is the same silent-drop failure shape as the instrument filter.
- Apply: when a lookup's not-found case is indistinguishable from its empty
  case, no response check can recover it. Move the guard **before** the request:
  validate the identifier structurally (an ISIN check digit is deterministic and
  free) and only ask about identifiers already present in a catalog or artifact
  you hold. Check this for every new per-entity endpoint.

## A period label is only a key within one periodicity  (2026-09-04)

- Observed: `income-statement?time_period=quarterly` returns a payload whose
  `time_period` says `quarterly`, whose summary block is quarterly, and whose
  `full_statement` block is still annual. Both label their columns `Mar 2026`.
  The summary↔`full_statement` identity check joins on that label, so on the
  live TITAN response it compared one quarter's revenue (27,104 cr) against the
  financial year's (88,136 cr) and reported three confident disagreements — one
  per identity, all false.
- Why it matters: the two blocks arrive in one HTTP response, so nothing about
  the transport hints that they are on different clocks. The check looked like
  a working drift detector; it was manufacturing findings.
- Apply: before joining two series on a period label, assert both carry the same
  periodicity, and skip rather than compare when they do not. Never derive one
  block's periodicity from the response envelope — measure each block's own.

## Name similarity between two vendors is not evidence of a mapping  (2026-09-04)

- Observed: Lane B mapped Upstox's `total_liability` onto Screener's
  `Total Liabilities` row. Screener's row is the *balancing total* — it equals
  Screener's own `Total Assets` on every period of every company checked — while
  Upstox's field is liabilities excluding equity. The comparator reported a
  five-figure ANOMALY on all four TITAN periods (15,703 / 11,622 / 9,390 /
  11,901 crore) while the underlying numbers agreed to the crore. The correct
  mapping is `Borrowings + Other Liabilities`, which is exact on Mar-2026.
- Why it matters: this is precisely the failure `screener_crosscheck`'s own
  docstring warns about, committed by the module that warns about it. A false
  anomaly on every company and period reads as a catastrophic parser defect that
  does not exist, and it is the fastest way to get a log-only check switched off.
- Apply: every entry in a cross-vendor name map must be demonstrated on live
  data from both sides before it ships — matching labels are a hypothesis, not
  evidence. Prefer a reconstruction from rows whose sum you have checked over a
  single row whose name matches. See
  [`docs/research/upstox-lane-b-first-measurement.md`](../../docs/research/upstox-lane-b-first-measurement.md).

## Validate only the part of an artifact you read  (2026-09-04)

- Observed: `upstox-crosscheck` loaded Screener sections through the full
  `SectionTable` model. A retained capture written before `ScheduleStrategy` and
  `SubRowKind` gained required fields then failed with 16 validation errors —
  none in a field any comparison touches — and the whole run refused before
  comparing anything.
- Why it matters: it couples a consumer to parts of a producer's schema it has
  no interest in, and turns unrelated schema evolution into a hard failure of a
  log-only lane. Retained artifacts outlive the models that wrote them.
- Apply: when reading someone else's artifact, declare a narrow model of exactly
  the fields you use, `extra="ignore"`, and keep those fields strict. Reuse the
  producer's full model only when you actually depend on all of it.

## A tolerance formula is not frozen until it is recomputed on the boundary case  (2026-09-04)

- Observed: the level-3 plan wrote the percent-of-sales tolerance as
  `0.5 + 100 × (Σ half_ulp(addend) + r × half_ulp(Sales)) / Sales`. The `×100`
  belongs on the addend term only; applied to the `r` term it made the band
  ≈27 pp on the ground-truth boundary case, wide enough to admit any breakdown.
  The test author caught it by recomputing the band on the two numbers the plan
  itself named (127/156 vs 82 % must hold; 120/156 vs 82 % must fail) — the
  literal formula let the 120 case pass.
- Why it matters: a wrong tolerance is the quietest defect a reconciliation
  gate can carry — every run is green, the artifact says RECONCILED, and the
  gate has stopped gating. The plan reviewers read the formula as prose and
  approved it; only arithmetic on a named case exposed it.
- Apply: every tolerance or identity in a plan must carry one hold case and one
  fail case with concrete numbers, and the test must pin hold/fail behaviour,
  not the tolerance value. Recompute the band on both before freezing.

## A nested body can lag the page it hangs under  (2026-09-04)

- Observed: HFCL's level-3 `Trade receivables` body carried Mar 2014 … Mar 2025
  while the page and its level-2 parent carried Mar 2015 … Mar 2026 — Screener
  had not yet populated the FY26 breakdown. TITAN and NETWEB matched exactly,
  which is what the ground truth had recorded as a fact.
- Why it matters: two companies agreeing is not a universal; the third one
  falsified it on the first live smoke. The partial-alignment rule inherited
  from level 2 marked the family UNVERIFIED and exited 2 with everything
  retained — the fail-closed behaviour did its job without knowing the cause.
- Apply: label window facts observed on a sample as `VERIFIED on <n>` and keep
  the alignment gate strict; decide separately, with the owner, whether an
  older-only overlap should reconcile on the overlap.

## A sensitivity harness must not charge the comparator for cells nobody could detect  (2026-09-04)

- Observed: the Lane B seeded-mutation harness first reported overall
  sensitivity 0.19 and tier-1 0.28. The final figure was 0.96 with no change to
  the comparator. Three harness defects, all the same shape: a cell was counted
  `UNDETECTED` where detection was impossible — the period had no Upstox report
  (136 of 140 tier-1 "misses"), the mutation targeted a column the comparator
  never reads (`STALE_PERIOD` read 0 of 600), or the class was row-scoped and
  every untouched period of the row was scored (17 / 48 for one changed cell).
- Why it matters: a false low is worse than a false high here. It is read as
  "the comparator is blind", it would set every 5(c) threshold against the wrong
  number, and nothing in the summary distinguishes it from a real result.
- Apply: the denominator of a detection ratio is only the cells the mutation
  actually altered AND the comparator actually read. Make applicability per
  cell from the class's own rule (never by comparing outcomes), give every
  "could not detect" reason its own named bucket, and before trusting any class
  that reports zero, prove it can fire on one cell of real data.

## A convergence rule fires on its evidence, not on a coincidence  (2026-09-04)

- Observed: Lane B's "Upstox-side" alibi was built as *an internal Upstox
  contradiction on the same line and period*. On the first real replay it
  exonerated THERMAX revenue on two periods where Screener sat ~50 crore from
  both Upstox figures. The rule Part 1 of the measurement doc had earned was
  two-sided — the contradiction **and** Screener agreeing with Upstox's own
  `full_statement` — and the implementation had kept only the half that is
  easy to key on.
- Why it matters: an alibi that fires on coincidence removes lines from the
  warn queue on evidence that says nothing about them. POLYCAB (0.25 crore
  from the full_statement) was the case the rule was written for; THERMAX
  passed the same check with no such agreement.
- Apply: when a diagnostic rule is stated as "A and B", key the code on both
  and write the negative test from a real case where A held and B did not.
  Carry the values the rule needs on the structured note, not just the labels.

## A gate rail judges what the change wrote, and fails closed on what it cannot read  (2026-09-05)

- Observed: the captured-identifier rail grepped every *changed* test file
  for ids harvested from private captures. Editing one import line in
  `test_comparatives.py` fired it on `2023`, a calendar year the file had
  carried since before the rail existed; a refactor slice could not gate at
  all because ROUTE PASS needs a red proof. In the same fix, an unreadable
  baseline file produced an empty comparison that printed `test-set OK`.
- Why it matters: a rail that re-accuses pre-existing lines trains its reader
  to wave STOPs through, which is worse than no rail. A proof check that
  prints OK on an empty input is a fail-open in a security gate.
- Apply: scope fixture rails to the `+` side of `git diff -U0 HEAD` plus
  untracked-file content; keep secret rails whole-file. Give refactors their
  own route (`scripts/verify.sh baseline <slice>`: green test set recorded,
  set equality demanded back). Whenever a check compares against a recorded
  file, branch on "could not read" before "no difference".

## 2026-09-06 — SEBI Integrated Filings (NSE, Mar-2025 onward)
- NSE's `corporates-financial-results` listing stops at Dec-2024 for issuers that moved to the
  Integrated Filing format; the rows live at `/integrated-filing-results` (`qe_Date`,
  `consolidated`, `xbrl`, `broadcast_Date`; no `fromDate`/`isin`). `NseXbrlSource` falls back to it.
- Instances declare a DATED `in-capmkt` namespace (`.../2025-01-31/in-capmkt`,
  `.../2026-01-31/in-capmkt`); every revision must be registered in `xbrl_taxonomies` or the
  parser fails closed. The entity identifier is the BSE scrip under
  `http://www.sebi.gov.in/in-capmkt/ScripCode`, so `xbrl.accepted_entity_ids` and
  `xbrl.entity_id_aliases` must be declared per issuer.
- Scanned results PDFs carry the issuer's own OCR text layer; the unit word and even "Profit"
  can be garbled. Declare `pdf_parse.printed_unit` (fills a missing marker only) and
  `pdf_parse.label_overrides`; a row whose label is split across text lines cannot be bound
  and must be excluded from `concepts.cross_check` for that quarter with a comment.

## 2026-09-07 — Codex implementer sandbox and the full-suite gate
- The Codex `--role implement` sandbox has no network, so `tests/fundamentals/test_sec.py`
  reports 7 "SEC EDGAR unreachable" skips and `scripts/verify.sh gate` prints
  `skips FAIL 15 > baseline 8 / ROUTE: CONTRACT`. Tell the implementer up front that this
  exact signature is environmental; the orchestrator re-runs the gate with network before
  committing. Any other new skip is real.
- The gate runs the whole suite, so a second slice's red acceptance file in
  `tests/fundamentals/` pollutes the running implementer's gate. Record the red proof at the
  tree path (a few seconds), then park the file in `scratchpad/phase05/staged/` until that
  slice is dispatched; moving it back restores the proof hash. Test authors write to the
  staged path directly and locate the repo root by walking up to `config/fundamentals.yaml`.

## Live smoke before any one-shot live run  (2026-10-16)
- Observed: D6 attempt 1 was frozen with every test green, then the live acquisition hit
  BSE `PeerSmartSearch` 403. The transport's custom User-Agent was refused; the Task 0b probe's
  `Mozilla/5.0 (X11; Linux x86_64)` was accepted. Tests replace the transport, so request
  headers were never exercised. The fix touched `src/` after the freeze, so the attempt burned.
- Why it matters: a header- or session-level defect costs a held-out draw and a re-review cycle.
- Apply: before freezing for a live one-shot, run the real transport against a development
  company on a scratch `eqos_test_*` DB and require every surface OK
  (`scratchpad/execution/d6/live_smoke.py` pattern: `discover` + `live_transport`).
- Follow-up (attempt 2 burn, same day): a transport-only smoke on one company still missed an
  ingest-time framework rejection that 9 of 11 dev companies hit. Smoke the FULL path (discover,
  admission, ingest, printed compare) over several dev companies, and test that every admission
  predicate agrees with the ingest predicate it precedes
  (`scratchpad/execution/d6/live_onboard_smoke.py`).

## Recursive searches leak opaque paths  (2026-10-17)
- Observed: during the extractor-v2 plan, an author's `grep -l` over `tests/` listed the held-out
  manifest's filename, and a reviewer's `grep` printed one header line from it: the exclusion
  globs did not match the full searched paths. No identifier was exposed.
- Why it matters: the opaque contract is breached by a search, not just by opening a file; on an
  open attempt that would force a burn.
- Apply: never search `tests/` or `data/` recursively while opaque artifacts exist; search an
  explicit list of permitted files, or load inputs in Python. Put this line in every brief.

## WSL wall clock steps backwards; clock-ordering checks flake  (2026-10-17)

- Observed: `time.time()` on this WSL host stepped back 0.81s and 1.11s within a 20s probe.
  `source_admission`'s "derivation clock moved backwards" then fails whichever pipeline test
  straddles a step (a different test each full run, sometimes in an isolated module run).
- Why it matters: a red full suite here is often environmental, not the change under test.
- Apply: on that error, rerun the test and note it on eqos-0bp; do not chase it in feature
  code. Durable fix is host time sync or a monotonic test clock (eqos-0bp).

## Pinned extractor sources are frozen bytes  (2026-10-19)

- Observed: screen-export commits edited `ingest/tijori_source.py` and
  `ingest/screener_session_models.py` without a version bump. Both files are hashed into the
  vendor extractor pins (`compare/run_config.py` `VENDOR_EXTRACTORS`). Databases pinned
  earlier raised `VersionContentDriftError`. Targeted suites passed; only the full suite
  caught it (`test_derived_settings`).
- Why it matters: a version bump is no cheap way out, because frozen manifests and fixtures
  name the old versions.
- Apply: before editing an ingest file, check whether it is listed in `VENDOR_EXTRACTORS`.
  If it is, put new code in an unpinned module. Run the full suite once per phase.

## A new table breaks every table-enumerating test  (2026-10-19)

- Observed: migration 0040 added two tables. Eight tests outside the phase's own suites
  failed: the evidence-schema count and grant checks, plus the backup table lists in the
  ledger stage 1/2 and data stage 2 end-to-end tests. A worker had stated that no other test
  lists tables, and the targeted suites were green.
- Why it matters: the regressions surface only in the full suite, after the phase review.
- Apply: a migration that adds a table also adds it to a family set in
  `tests/fundamentals/ledger_support.py` (or its family's support module). Run the full suite
  before the phase review, not after it.

## Docker Desktop can bind the PG data dir to empty VM storage after a WSL restart  (2026-10-23)

- Observed: after WSL restarts (2026-10-14, 10-15, 10-22), Docker Desktop restarted
  `equity-os-postgres-1` before the WSL path was visible. The bind resolved to an empty
  VM-local filesystem (`none`, 16G), and the image entrypoint ran initdb. All DB work for
  9 days, including the production cutover, went to storage that the next restart wiped.
  The 4401-test gate stayed green because it uses only isolated test DBs. Recovered from
  backup B2 (eqos-89z).
- Why it matters: data loss is silent. The app sees a healthy, empty server.
- Apply: `compose.yaml` refuses to start without `$EQOS_PG_DATA_DIR/.eqos-host-mount`.
  Never create that sentinel anywhere but the verified real data dir. Apply compose changes
  with `docker compose up -d postgres` (a restart keeps the old config). If PG looks empty,
  run `docker exec equity-os-postgres-1 df -h /var/lib/postgresql`: it must show the host
  disk, not `none`.

## Worktree gates need the gitignored retained data  (2026-10-28)

- Observed: T3 worktrees get only tracked files. The DOCS-1 full gate reported 713 failures, and
  VENDOR-SURFACE fix runs reported 5. Every one was a missing retained file under `data/`
  (`data/store/aparinds.sqlite`, `data/raw/watchlist/aparinds/`, `onboarding-dev`, `infy-fy25`,
  `data/reports/`). None was a code fault.
- Why it matters: a missing-data failure looks like a regression and wastes a gate run.
- Apply: before gating in a worktree, **copy** (`cp -a`) each of main's `data/` entries that the
  worktree lacks. Do not symlink: the snapshot reader opens directories with `O_NOFOLLOW` and
  raises `UnsafePathError` on a symlinked directory. Leave only
  `data/holdout` as a symlink, because it must never be opened; a byte copy of
  `data/raw/onboarding` is fine (the stage4 e2e test needs a real directory).
  Copy all of `data/`, not only the directories you expect a test to need; partial copies cost
  a second gate run. Prove parity by diffing `find . -type f` between the checkouts, with
  `holdout` pruned. Then read the failure messages:
  "retained ... missing" or a FileNotFoundError under `data/` is environmental.

## A stale `.mypy_cache` hid a mypy failure on main  (2026-10-28)

- Observed: `mypy --strict src` passed on main only from its cache. A fresh worktree, and
  `--cache-dir=/dev/null`, failed on the optional `rapidocr_onnxruntime` import (the `ocr`
  extra was not installed). Neither an inline `import-untyped` nor an `import` ignore code
  satisfies strict mode in both the installed and the absent case.
- Why it matters: gates in fresh checkouts fail on code that main reports clean.
- Apply: check mypy claims with `--cache-dir=/dev/null`. For optional extras, use a
  `[[tool.mypy.overrides]]` entry with `ignore_missing_imports = true`, not an inline ignore.

## Long gates: run as systemd user units with `UMask=0022`  (2026-10-28)

- Observed: a full gate under contention runs past the 2-hour background-task cap. `setsid nohup`
  processes died when the Claude Code process exited. `systemd-run --user` units survive that,
  but their default umask is `0002`: every test-created file was group-writable, the snapshot
  store refused them ("unsafe ownership or permissions"), and about 532 tests failed in each of
  three gates.
- Why it matters: the gate fails on environment, not code, and it costs a full run.
- Apply: `systemd-run --user --collect -p UMask=0022 -E PATH="$PATH" -E HOME="$HOME"
  --working-directory=<checkout> bash -c 'umask 0022; ...'`. Then wait on a `done` marker file.

## Full suite on xdist: 2h39m serial -> 25m on 16 workers  (2026-10-29)

- Observed: serial gate suite 9554 s (2:39:14), 4438 passed. `-n 16 --dist load`: 32m23s,
  but module fixtures were rebuilt on every worker (60-160 s setups) and 9 tests failed
  "configuration ancestor changed during operation: /tmp" — the approved-config loader
  refuses when any ancestor's ctime moves, and `/tmp`'s moved ~15x a minute.
  `-n 16 --dist loadfile` with tmp_path under `~/.cache/equity-os/pytest-tmp`: 25m01s,
  4443 passed; the only reds were "clock moved backwards" flakes that pass in isolation.
  Slowest single tests (contended): stage4 e2e 425 s, pilot e2e 412 s — the floor.
- Why it matters: tmp_path under `/tmp` turns that refusal into a flake; tmp_path under a
  checkout breaks the `test_verify_*` sandbox repos (they inherit its `pyproject.toml`).
- Apply: run the full suite through `scripts/verify.sh` (`suite_pytest`), or pass the same
  `-n 16 --dist loadfile` and `PYTEST_DEBUG_TEMPROOT`. Keep `verify.sh red` serial: it reads
  `sys.modules` in-process, which xdist workers would hide.
