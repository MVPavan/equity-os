# PILOT-E2E Implementation Plan — the pilot exit test

**Origin:** bead `eqos-4j2.8` (P1, parent `eqos-4j2`); `docs/backend-roadmap.md` §4 (PILOT-1…13 and
the verdict). Test path `tests/fundamentals/test_pilot_e2e.py` (fixed by `docs/plans/PREP-7.md`
Decision 8; registered as `E2E["pilot"]` in `test_frozen_manifests.py` and `PILOT_TARGET` in
`scripts/verify_project.sh:10`).
Status: **approved — gpt-6.1-sol APPROVE, 2026-10-20** (r1 REQUEST_CHANGES 2/4/1 → r2 → r3 REQUEST_CHANGES
1/1/0, ruled by the orchestrator after 3 rounds → fresh closing review 0/2/1 → r2 0/1/0 → r3 APPROVE). Owner
decisions of 2026-10-20 (PavanMV): citation amendment (§ PILOT-4 citation route), PILOT-5 contradiction NOT
MET, D8 stays gated and the verdict is CONDITIONAL on D8.

**Goal:** one `pg` + `retained` test on a disposable `eqos_test_*` database. It runs the PREP-7
preflight, drives Apar PQ0 (Q2 FY26) → PQ1 (Q3 FY26) → PQ2 (Q4 FY26) → PQ3 (Q1 FY27) on PostgreSQL,
and asserts every PILOT check code can assert. Expected numbers come only from the frozen
`pilot_manifest.yaml` (or the `stage1_manifest.yaml` it hash-pins); every failing assertion begins
`PILOT-n:`.

**Out of scope:** the owner-gated cutover `eqos-3zl` (the test never opens `equity_os`); PILOT-7's
held-out onboarding (D6 exit); building D8 shareholding; new production abstractions; Sol r2's
arithmetic-reconstruction FORMULA route (rejected by the owner, 2026-10-20); any edit to
`pilot_manifest.yaml` (frozen once this test lands).

**Constraints:** the four quality commands stay green after every task; PG only on `eqos_test_*`;
nothing under `data/` is written (vendor captures are copied into `tmp_path`); the test never opens
`stage4_*`, `data/holdout/`, `data/raw/onboarding/` or `~/.secrets`; 800-line cap per file; owner
minimal-code rule (2026-10-14).

## Evidence (code or probe; probes in `scratchpad/pilot-e2e/probes.md`)

1. **The harness already runs the pilot.** `prep2b_support.Pilot` registers originals, runs `ledger
   import`, watchlists Apar (batch, then owner `ADD`), admits transcripts, ingests the 8 XBRLs and
   runs each quarter `--retrospective --compare-run`. `test_prep2b_run_draft.py:562`
   `test_four_quarter_sequence` already proves cutoffs, the retrospective label, export hash =
   `content_hash`, all `MATCH`, admitted facts and approval superseding the import. Reused, not rebuilt.
2. **Run citations (probe, FY26_Q2 and FY26_Q3 run versions).** `fact.*` cite admitted facts;
   `cmp.*.abs|pct`, `calc.1|3|4` cite traces; guidance cites `SOURCE_QUOTE`. **13 claims per version
   cite an interpretation `FIGURE`**: the 12 `cmp.<role>.<qoq|yoy>.prior` and `calc.2` (tax expense).
   Each version pins only its own comparison run (`run_draft.py:288`). Of the 52 (13 × 4): the 18
   PQ1–PQ3 qoq priors equal the predecessor quarter's `fact.<role>` value and XBRL locator (Sol r2
   probe); the other 34 are 24 yoy priors, 6 PQ0 qoq priors and 4 `calc.2`.
3. **The run never reads `thesis-impact`** (separate dispatch, `api/cli.py:685`); the prior is the
   ledger's approved head.
4. **No pilot code path uses shareholding** (`output`, `ledger`, `api/pipeline*.py`, `api/cli.py`). D8
   is parked (owner, 2026-10-17) and stays in the gate (owner, 2026-10-20), so `verify_project.sh`
   reports D8 `NOT BUILT` and cannot exit 0.
5. **PQ3 segment.** The six roles AGREE and are admitted (`eqos-4j2.33`); only the segment PDF block
   is not located (`eqos-ghv`). No pilot claim is a segment claim.
6. **Vendor coverage (Sol r1 probe, observations, not expectations).** Under the pilot pins, for each
   PQ0–PQ3: Screener 12 quarterly interpretations (9 `MAPPED`, 3 `UNMAPPED`); Tijori 23 (2 `MAPPED`:
   revenue, continuing PAT; 21 `UNMAPPED`). Both adapters `COMPLETE`.
7. **Guidance (probe).** No genuinely incompatible same-target, same-horizon, same-scope pair exists
   in the four pilot transcripts (union of configured rules, `load_pdf` +
   `extract_guidance_claims`). The only disjoint pair is conductor EBITDA/MT: FY26_Q2 p12 b5 "guidance
   of 30,000 per metric ton" vs FY26_Q4 p9 b34 "range of INR35,000 to INR36,000 per metric ton". The
   FY26_Q2 context makes 30,000 a floor ("a comfort level below which the EBITDA are not likely to
   drop"; FY26_Q3 p9 "INR30,000-plus"), compatible with 35,000–36,000. Cables growth (25 / 20-plus /
   25) and cables margin (9.5–10 / 10–11) are compatible.
8. **Clock.** The derivation cutoff is the process clock (`api/pipeline.py:575` `completed()`); PG
   stamps rows with the store clock (`eqos-4j2.23`).
9. `PILOT_TARGET` is set; the manifest is committed and approved (payload `ad188b0d…`) in `1b74d77`,
   before any e2e commit, so Decision 8's history check holds.
10. **Label carrier (contract probe).** `NumericClaim.qualifiers` is persisted
   (`numeric_claims.qualifiers text[]`, no CHECK), hashed into the sealed digest
   (`0012_report_ledger.sql:248`) and rendered (`display.py:71–77`); `claim_check` compares
   qualifiers only for `SOURCE_QUOTE` (`:150`); rework's carry gate compares them for every claim
   (`rework._same`, `:121–125`, excludes only `citation`/`unresolved`). An
   interpretation `FIGURE` with no run resolves via `citations._interpretation` (`:227–228`); a fact
   `FIGURE` via `_admitted` over `ANY(pinned_run_ids)` (`:94–99`). No migration, column, `ClaimState`
   or `CitationKind` change is needed.

## PILOT-4 citation route (`eqos-4j2.27`; owner PavanMV 2026-10-20)

Amended doctrine (`docs/backend-roadmap.md` PILOT-4, `.claude/project/invariants.md` 7): current-period
material claims cite an admitted fact or a trace; a comparator-period figure, or the filed tax total
that cannot be admitted (`calc.2`), may cite the company's directly filed first-party value,
**labelled** single-source and not cross-checked; where the predecessor quarter's admitted fact
exists, the claim cites it. Per Evidence 2:

- **18 PQ1–PQ3 qoq priors → predecessor admitted facts** (Sol r2 "Requested QoQ route"). When the
  prior is a run-generated approved version (non-empty `pinned_run_ids`) whose `fact.<role>` cites a
  fact, `cmp.<role>.qoq.prior` takes that citation (`fact_origin`, `fact_origin_id`; `source_sha256`
  stays the comparator XBRL) only if key digest, value and `source_sha256` are equal. One pure check
  `run_draft.predecessor(prior, claims)` enforces this over the prior head's `fact.*` claims, which
  `Prior` keeps from the read `prepare_prior` already does (`run_draft.py:248`). It runs twice:
  (a) **before any write** — `bind_computed` takes it as a callback from `before_commit`
  (`api/cli.py:369–378`) and calls it on the unbound lines before `put_calculation_trace`
  (`run_traces.py:404`), so a mismatch refuses the run before traces, admissions or selections
  persist; (b) in `write_run_draft` after the locked prior-head/digest recheck (`:272–283`), which
  also performs the swap (carried claims already cite the fact and pass through unchanged). The prior
  head's `pinned_run_ids` join the citing version's pins (that head only; rework already carries head
  pins, `:288–290`). No re-admission, reselection or change to `citations._admitted`.
- **34 labelled filed values** (24 yoy priors; 6 PQ0 qoq priors — PQ0's prior is the import, not an
  admitted run; 4 `calc.2`): the existing interpretation `FIGURE` plus the label. Per version:
  PQ0 13, PQ1–PQ3 7 each.
- **Label mechanism:** one closed qualifier `FILED = "filed"` in `display.py`. `_Binder.figure`
  (`run_traces.py:210`, the only producer of interpretation figures: priors and `calc.2`) sets it;
  the predecessor swap removes it. **Rework carry:** a regenerated QoQ prior arrives with `FILED`
  while its stored predecessor-backed claim has none, so `Gate.line` would refuse every carried QoQ
  line. `rework._same` therefore drops `FILED` from both qualifier tuples when the stored claim is not
  `SOURCE_QUOTE`, and still carries the stored claim unchanged. Chosen over normalizing the
  candidate's binding before `Gate.line` because it is one comparison in one function and does not
  duplicate the swap in `run_traces`; it is safe because the carried claim's own label is rechecked by
  the resolver gate below. All other qualifier comparisons and guidance semantics are unchanged.
  `render_claim` appends the constant suffix " (filed value, single
  source, not cross-checked)" for `FILED` regardless of the slot's `qual` flag, so the narrative
  cannot drop it while the claim carries it. `citations.resolve` returns unresolved when
  (`FILED ∈ qualifiers`) ≠ (interpretation `FIGURE` with no run): a missing or false label fails the
  claim check as `UNRESOLVED` and blocks approval.
- Kept unchanged: admission rules, sources, frozen manifest, trace kinds, schema; cutoff and
  first-party checks on every cited input (`citations.py:404–409`, `claim_check.py:88–94`).

## PILOT checks (authoritative)

Every expected value comes from the manifests or a recorded probe; no number is typed into the test.

| Check | Test action | Failing assertion (`PILOT-n:`) | Not met here / external gate |
|---|---|---|---|
| PILOT-1 | Every XBRL and PDF `evidence ingest` (harness). Per admission run, an **expected applicable-row inventory** derived by the test from the pinned dictionary (non-deprecated rows outside shareholding × the quarter's periods) and the retained package disclosures (the manifest's XBRL/PDF locators) | Run row identities ≠ inventory (missing or extra); a located side not `VALUE` at its lex; a row with no extracted value carries a value (no zero fill); PQ0 `fact.profit_before_tax` / `calc.4` ≠ manifest (340.56 / 340.53); PQ0 `opm_pct\|Q\|-\|DERIVED` ≠ `C7_OPM.spec_literal_2dp` (manifest `pilot_checks.PILOT-1` → stage1); PQ3 segment block not an explicit failure state, or valued | Coverage stays the approved narrow PDF set; not every row needs a value. `eqos-ghv` stays open |
| PILOT-2 | Per quarter: copy A-SCR/A-TIJ into `tmp_path`, `ingest_vendor` for the quarter end, `compare run --vendor …` under the pilot pins as a separate run (admission reads only its own run's overlay) | Either vendor identity missing or not `COMPLETE`; a role without a vendor side or explicit status; per row, the set of queue items ≠ exactly what the existing routing policy proposes for it (`compare.routing` `_pair_route` / `_status_route`; e.g. none for PQ0 opex H3 `ANOMALY / NOISE / queue none` and inapplicable rows, while a `FILING_ONLY` row still gets any extraction or mismatch item the policy routes); an operational `UNAVAILABLE` side without its run failure evidence (attempt); PQ0 `opex_excl_finance_and_da\|Q\|-\|DERIVED` `{pair, triage, queue}` ≠ manifest `pilot_checks.PILOT-2` (a FAIL to investigate; pins never change). A mapped cell is not asserted as corroboration | — |
| PILOT-3 | Before the runs, `test_cutover_rollback.Window` imports and reconciles the legacy copy, then cuts over; during the runs the no-SQLite guard (`test_prep2_pilot_pg.py:73`) | `reconciled.equal()` false; `cutover.FactStore` or `sqlite3.connect` reached | Production cutover `eqos-3zl` gates acceptance |
| PILOT-4 | Per version: (a) `source_cutoff`, `retrospective.manifest_sha256`; (b) `pilot_manifest_check.citations_allowed`; (c) the 46 non-quote keys equal `quarters[Q].claims` (`figure` `Decimal == v`; `pct`, `calc.3` `v` quantized `0.01` `ROUND_HALF_EVEN`; `abs`, `calc.1`, `calc.4` exact; `Fraction` parse, unit scale from `pilot_manifest_check`); claim check; owner `APPROVE` row; sha256 of `ledger export <id>` and `--stock` output = `content_hash` | Any of those; a material numerical claim citing neither an admitted fact, a trace nor a labelled filed value (guidance: `SOURCE_QUOTE`); a `FILED` claim keyed other than `cmp.*.prior` / `calc.2`, or rendered without the suffix; a PQ1–PQ3 `cmp.*.qoq.prior` not citing the predecessor's `fact.<role>`; `FILED` count ≠ 13 (PQ0) / 7 (PQ1–PQ3); any `POLICY` or `COMPARISON` claim | Needs Task 2 (`eqos-4j2.27`). The 34 filed values are single-source, not cross-checked |
| PILOT-5 | The `test_pilot_memory` sequence (boundary retrieval, replay, later events excluded, empty retrieval at a historical cutoff) plus a **supersession** scenario: after PQ1, promote A (PQ1 `fact.*`) and G (PQ1 `cables_revenue_growth` claim); after PQ2, promote G′ superseding G (PQ2 claim, `MODIFIED`) | PQ3's sealed line lacks A or G′, or lists retired G; `provenance(G′)` lacks G and its support; non-empty retrieval at a run's `source_cutoff` | **Contradiction clause NOT MET** (owner, 2026-10-20): untestable on Apar's real sources (Evidence 7); nothing is manufactured. The test covers supersession only, which is not contradiction evidence |
| PILOT-6 | `ledger export --stock APARINDS --status-notes --memory` as the runtime role, read-only transaction | Non-zero exit; a narrative not hashing to its `content_hash`; `memory.md` missing a promoted id | — |
| PILOT-7 | — | — | D6 exit `test_data_stage4_e2e.py` (holdout stays blind) |
| PILOT-8 | Watchlist head is the owner `ADD`; at the end owner `REMOVE` via `ledger decide`, then a runtime draft | Head not `ADD`; draft not refused "is not on the watchlist", or any row written | — |
| PILOT-9 | Vacuity over every version | Any shareholding key or section | **NOT MET; verdict CONDITIONAL on D8** (owner, 2026-10-20). Vacuity is recorded, not counted as met |
| PILOT-10 | Real store clock: `retention classify`, `db backup`, `retention purge --dry-run --snapshot-root <tmp>`, `purge`, `db restore --replay-runs` into a fresh `eqos_test_*` | Listed set ≠ `retention.eligibility` eligible set; listed ∩ hold roots (manifest package hashes via `holds.yaml`, version-cited blobs) ≠ ∅; `restore_check.replay(admission + vendor run ids)` ≠ `((), ())`; a held blob fails its hash | Records actual counts; an empty purge is not observed deletion. Positive deletion: D9 exit |
| PILOT-11 | (i) PQ1 run interrupted after `admit_run` (`interrupted(..., cli, "admit_run", after=True)`), then retried. (ii) PQ2 v1 rejected on `cmp.revenue.qoq.prior` through `review start\|claim\|finish` (`REQUEST_CHANGES`); `rework.plan`; successor approved. (iii) Last: `_shadow(_seeds(PQ0 claims))` | (i) with `test_prep3_resume.ids/added/delta/claims`: interrupted attempt leaves no version and committed admissions but no selections; retry reuses the registered comparison run (no new `runs` row), adds no `fact_rows`/`fact_admissions`, keeps every committed logical id (committed facts ⊆ admitted rows, committed traces ⊆ cited), every new trace is cited (no orphan), exactly one PQ1 draft. (ii) plan ≠ `QOQ`; with the PREP-5 `calls` spies (`test_prep5_rework.py:399–419`): `conclude` keys ≠ the QOQ trace keys, `admit_run` ≠ `[0]`, `select_admitted` ≠ `[]`, fact/admission counts change; carried claims or ordered lines differ; successor not v(N+1) of the predecessor with its digest. (iii) states ≠ `ANSWER`; owner APPROVE not refused | Detecting review-only seeds needs the owner's blind run `eqos-4j2.30`; stays unmet until independent evidence exists |
| PILOT-12 | **Five run-generated versions** (PQ0, PQ1, PQ2 rejected, PQ2 successor, PQ3) each reviewed through `review start\|claim\|finish` with scripted dispositions and the `_ticking` clock; **four final approved** quarter versions | A version without exactly one `review_sessions` row; `claim_reviews` not covering its review set; PQ2 v1's category/dispositions ≠ the scripted rejection; the successor's review set ≠ its rework rereview set; report-chain totals ≠ the sum of both PQ2 sessions | Scripted times are instrumentation only; the owner's real review of four reports (Owner Q1) |
| PILOT-13 | `restore_check.replay(run ids)` on the live, then the restored database | ≠ `((), ())` | Suite, mypy, ruff: `verify_project.sh` |

## Bead rulings

| Bead | Ruling |
|---|---|
| `eqos-4j2.23` derivation clock | Blocks; Task 1 fixes it (PG path: cutoff from `repository.store_clock`) |
| `eqos-4j2.27` citation contract | **Open; Task 2 implements it** (§ PILOT-4 citation route); closes when its PG tests pass. Export check: the test hashes single-version exports; no CLI guard needed |
| `eqos-4j2.26` thesis-impact YAML | Parked: the pilot never calls it (Evidence 3). Not evidence the command's authority problem is fixed |
| `eqos-4j2.32` PILOT-9 | Shareholding unused (Evidence 4); PILOT-9 NOT MET, verdict CONDITIONAL on D8 (owner, 2026-10-20); open until D8 is built |
| `eqos-ghv` PQ3 segment | Not blocking; the test asserts an explicit failure state. The parser bug stays open |
| `eqos-4j2.21` submit CLI | Not blocking; the test submits via `lifecycle.submit`. Needed first if the owner reviews by hand |
| `eqos-4j2.22` legacy impersonation | Parked (2026-10-18); this test does not reopen it |
| `eqos-4j2.30` blind drill | PILOT-11 / verdict gate; not automatable |
| `eqos-4j2.9` register A-rows | Separate housekeeping |
| `eqos-3zl` cutover | Gates the verdict and closing `eqos-4j2.8`; not inferable from a disposable rehearsal |
| `eqos-4j2.8` | Closes only on a PASS verdict; a CONDITIONAL verdict leaves it open |

## Owner questions

Decided 2026-10-20 (PavanMV): **D8** stays gated, verdict CONDITIONAL on D8, PILOT-9 not met by
absence (was Q1); **citations** — the amendment above (was Q4); **PILOT-5** contradiction NOT MET,
supersession only (was Q5). Open:

1. **PILOT-12.** When will you review the four quarter versions? PQ0 = the FY26_Q2 run version
   (recommended) or the imported bootstrap? Hand review needs `eqos-4j2.21` first.
2. **`eqos-3zl`.** GO-AHEAD for the production cutover.

## Tasks

### Task 1: Store-clock derivation cutoff (`eqos-4j2.23`) — Opus, test-first

- Files: the pipeline/CLI PG call site; one regression case in `test_prep2b_run_draft.py`.
- Red: process clock monkeypatched 2 s behind; FY26_Q2's draft must still pass `AS_KNOWN` (fails
  `POST_CUTOFF` today). Fix: on the PG path the cutoff is sampled from the store clock after the
  trace/admission/selection writes. SQLite path unchanged; `test_real_clock_retrospective` stays green.
- Verify: `uv run pytest tests/fundamentals/test_prep2b_run_draft.py
  tests/fundamentals/test_prep3_resume.py tests/fundamentals/test_pilot_memory.py`; the four quality
  commands.

### Task 2: PILOT-4 citations (`eqos-4j2.27`) — Opus, test-first

- Files: `ledger/run_draft.py` (`Prior` keeps the head's `fact.*`, `predecessor` check, swap,
  pins), `ledger/run_traces.py` (`figure` sets `FILED`; check callback before traces persist),
  `api/cli.py` (`before_commit` passes the check to `bind_computed`), `ledger/rework.py` (`_same`
  ignores `FILED` for non-guidance claims), `ledger/display.py` (`FILED`, suffix),
  `ledger/citations.py` (label gate in `resolve`);
  a new PG test `test_pilot_citations.py` on `prep2b_support.Pilot` (`test_prep2b_run_draft.py` is
  at 735 lines).
- Positive (`eqos_test_*`, real runs): FY26_Q2 → approve → FY26_Q3. FY26_Q3's 6 qoq priors cite
  FY26_Q2's `fact.<role>` and resolve `MATCH`; its pins ⊇ FY26_Q2's; its 7 `FILED` claims (FY26_Q2:
  13) resolve `MATCH` and render the suffix; both versions approve.
- Rework carry (PG, after the approved predecessor): reject FY26_Q3's `cmp.revenue.qoq.prior`,
  rework; only that line reruns, and the other five qoq priors are carried with their predecessor
  `fact.<role>` citations, empty qualifiers and `MATCH`; the successor approves.
- Fail-closed mutations: (1) **absent predecessor pin** — pins without the prior head's runs → qoq
  priors `UNRESOLVED`, approval refused; (2) **mismatched key / value** — prior `fact.<role>` digest
  or value ≠ the run's prior, through the public run → refused. Baseline taken after source
  registration and comparison setup, before the run; after the refusal no added traces/operands,
  `fact_rows`, admissions, selections, reports, versions or claims; (3) **missing label** — `FILED`
  stripped from a filed claim, or set on a fact claim → `UNRESOLVED`; (4) **late inputs** — a cited
  predecessor admission/selection, or a filed capture, after the derivation cutoff → `POST_CUTOFF`.
- Existing tests that build interpretation-figure claims by hand get the label; nothing else changes.
- Verify: the new test; `test_prep2b_run_draft.py`, `test_prep5_rework.py`, `test_prep3_resume.py`;
  the four quality commands.

### Task 3: The cumulative e2e — Opus. **Starts after Task 2**

- File: `test_pilot_e2e.py` (over 750 lines → helpers to `pilot_e2e_support.py`).
- One module-scoped autouse preflight (PREP-7 step 0: working manifest bytes = `git show HEAD:<path>`;
  `manifest_support.approved(committed, committed)`), then one ordered `test_pilot_end_to_end`
  calling one helper per PILOT row of the table above, in order: PILOT-3, PILOT-8 `ADD`, the quarter
  loop (run, PILOT-1, PILOT-2, PILOT-4, PILOT-5 steps, PILOT-11 (i)/(ii), PILOT-12), then PILOT-6,
  PILOT-13, PILOT-10, PILOT-11 (iii), PILOT-8 refusal, PILOT-9.
- Reuse inventory (no generic scenario runner): `Pilot`, `_pilot`; `pilot_manifest_check`;
  `manifest_support.approved`; `test_cutover_rollback.Window`; `test_prep3_resume.interrupted/ids/
  added/delta/claims`; `test_prep5_rework.calls`; `test_prep6_review._start/_claim/_finish/_ticking/
  _sources/_seeds/_shadow/ANSWER`; `test_pilot_memory` boundary helpers; `stage1_e2e_support.row_key`
  and `Stage._ingest` arguments for `ingest_vendor`.
- Completion: commit the e2e (owner-authorized; the approved manifest is in its parent), then run the
  four quality commands — `test_frozen_manifests.py:763–764` needs that commit, so every task ends green.
- Verify: the e2e green; `data/` capture sha256s unchanged; three scratchpad mutation probes,
  never committed and never editing the committed manifest: a changed manifest `v` in a copy fails
  `PILOT-4:`, a stripped `FILED` label fails `PILOT-4:`, and a deleted applicable row fails
  `PILOT-1:`.
- Risk: high (runtime; cross-module reuse; vendor runs under v6 are new).

### Task 4: Review loop, report and landing — orchestrator

- Sol phase review of Tasks 1–3 per `04-agent-stack.md`, then a fresh closing review.
- `docs/evidence/pilot/report.md`: each check with its evidence and "not met / external" reason; the
  34 filed values listed as single-source, not cross-checked; verdict **CONDITIONAL on D8** (PILOT-9
  not met) with PILOT-5's contradiction clause NOT MET; Sol approved; `docs/backend-roadmap.md` Pilot row and §4 links.
- Tasks 1–3 are committed at their own completion, in order (the e2e last, in Task 3).
- Record bead rulings with `bd` notes; close `eqos-4j2.27` after Task 2. Keep `eqos-4j2.8` open: the
  verdict is CONDITIONAL (D8; PILOT-5 contradiction NOT MET) and Owner Q1–Q2 are open.
- Verify: `uv run pytest tests/fundamentals`; `scripts/verify_project.sh` (`Pilot | PASS`; non-zero
  exit with exactly `1 not built`, D8); `git status`.

## Risks

- Runtime: four runs, five versions, vendor runs, backup and restore in one test — a gate, not a
  unit test.
- A wrong frozen manifest value cannot be repaired (any edit fails Decision 8's history check); a
  mismatch is a FAIL to diagnose.
- WSL wall-clock steps (`eqos-0bp`) can flake source-admission ordering: rerun once and note it.
- PILOT-10 may be vacuous on eligibility under the real clock.
