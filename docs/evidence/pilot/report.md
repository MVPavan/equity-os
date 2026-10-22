# Pilot report: Apar, PQ0–PQ3 (PILOT-E2E)

**Verdict: CONDITIONAL** while any of the roadmap's [conditions](../../backend-roadmap.md#pilot-conditions) is open. PILOT-9 is met
([PILOT-9](../../plans/PILOT-9.md)). PASS, Phase 0.5 closure and `PILOT_PROVEN: YES` stay reserved.
`eqos-4j2.8` stays open.

Plan: [PILOT-E2E](../../plans/PILOT-E2E.md). Checks: [backend roadmap §4](../../backend-roadmap.md).
Gate test: `tests/fundamentals/test_pilot_e2e.py` (one ordered `test_pilot_end_to_end`; helpers in
`tests/fundamentals/pilot_e2e_support.py`). Expected values come only from the frozen
`pilot_manifest.yaml`; failing assertions begin `PILOT-n:`.

Full gate at `032258a` (code as `4a7e50a`, after the D8 closing-review fixes; 2026-10-21, 20:04:02Z–22:11:05Z): `scripts/verify_project.sh` exit 0, every row PASS (D1a–D9, frozen manifests, amendment records, Pilot, Pytest, Mypy, Ruff, Ruff format); `uv run pytest tests/fundamentals` 4401 passed, 9 skipped (1:45:44); `mypy --strict src` no issues in 326 files; ruff clean. Pilot e2e 248.1 s in the gate. The preceding run at `4a7e50a` failed only `test_stage2_end_to_end` ("derivation clock moved backwards", wall-clock guard); it passed alone and in this run; known flake `eqos-0bp` (cause not yet diagnosed).

Gate logs: `scratchpad/project-verification.7Y9zfv/` (`14.log` Pilot, `15.log` Pytest, `16.log` Mypy, `17.log` Ruff, `18.log` Ruff format, `10.log` D8; local, not committed).

## Checks

| ID | Status | Evidence |
|---|---|---|
| PILOT-1 | MET | Independent expected row inventory from the pinned dictionary and retained disclosures (`pilot_e2e_support.py`): no missing or extra rows, both sides `VALUE` where located, no zero fill, PQ0 PBT 340.56 / 340.53 and OPM `C7_OPM` equal the manifest, PQ3 segment block is an explicit failure state (`eqos-ghv` stays open) |
| PILOT-2 | MET | Per quarter, both vendors `COMPLETE`; each row's queue items equal what the routing policy proposes; `UNAVAILABLE` sides keep failure evidence; PQ0 opex `{pair, triage, queue}` equals the manifest. Policy agreement is an integration check, not independent proof of every routing rule; mapped cells are not asserted as corroboration |
| PILOT-3 | MET | Disposable legacy import, `reconciled.equal()` and cutover (`test_cutover_rollback.Window`), then the no-SQLite guard. Production cutover `eqos-3zl` done 2026-10-20: reconciliation equal, status OPEN, Sol round B APPROVE |
| PILOT-4 | MET | Per version: the 46 non-quote values equal `quarters[Q].claims`, source cutoff and retrospective label, claim check, owner `APPROVE`, export sha256 = `content_hash`; qoq priors of PQ1–PQ3 cite the predecessor's `fact.<role>`; `FILED` claims keyed only `cmp.*.prior` / `calc.2` with the rendered suffix; counts in the filed-value section |
| PILOT-5 | MET (contradiction clause waived) | Boundary retrieval, replay, late events excluded, empty retrieval at a historical source cutoff, supersession G → G′ with G's provenance equal to the PQ1 cables claim support and PQ2's transition asserted `MODIFIED` (`_pilot5`) |
| PILOT-6 | MET | `ledger export --stock APARINDS --status-notes --memory` as the runtime role, read-only; narratives hash to `content_hash`; `memory.md` lists the promoted ids |
| PILOT-7 | MET (via D6 exit) | D6 exit `tests/fundamentals/test_data_stage4_e2e.py`: 3 passed in the gate at `032258a` (held-out onboarding by identifier alone); the holdout stays blind and was not touched |
| PILOT-8 | MET | Head is the owner `ADD`; after owner `REMOVE` a runtime draft is refused "is not on the watchlist" with report/version counts unchanged |
| PILOT-9 | MET | Per quarter, `pilot_e2e_support.pilot9` (Task 3 block, `70bbb1f`) matches the frozen `shareholding` section; citation clause vacuous (`_pilot9_vacuity`). See § PILOT-9 |
| PILOT-10 | MET | Real-clock classify, backup, dry-run, purge, guarded `db restore --replay-runs`: listed set equals the eligible set, no hold root listed, held blobs hash-verified. An empty purge is not observed deletion; positive deletion is D9's exit |
| PILOT-11 | MET (owner blind drill removed by owner ruling 2026-10-22) | (i) interrupt after `admit_run`, retry without duplication; (ii) PQ2 v1 rejected on `cmp.revenue.qoq.prior`, only QoQ lines rerun, successor v(N+1) approved; (iii) seeded shadow states are not `ANSWER` and owner approval is refused. Human detection of review-only seeds is no longer a condition: the owner is not in the loop (ruling 2026-10-22) |
| PILOT-12 | MET (instrumentation; owner timing removed by owner ruling 2026-10-22) | Five run-generated versions each have exactly one `review_sessions` row, full `claim_reviews` coverage, the scripted PQ2 rejection and the two-session report totals. Scripted times are instrumentation; owner review timing is not measured (owner ruling 2026-10-22) |
| PILOT-13 | MET | `restore_check.replay` returns `((), ())` on the live and the restored database. Suite, mypy and ruff: see the full-suite line |

## Filed values (single source, not cross-checked)

Per the owner amendment (PavanMV, 2026-10-20), comparator-period figures and the filed tax total
(`calc.2`) cite the directly filed first-party value, labelled "(filed value, single source, not
cross-checked)". Counts: 13 filed claims in FY26_Q2 and 7 in each of FY26_Q3, FY26_Q4 and FY27_Q1
(PQ1–PQ3 qoq priors cite the predecessor's admitted fact instead). The production resolver refuses
`FILED` on any other key.

Generated from `pilot_manifest.yaml` (`v` as frozen; EPS in INR per share, other values INR crore):

| Quarter | Key | Filed value |
|---|---|---|
| FY26_Q2 | `calc.2` | 88.83 |
| FY26_Q2 | `cmp.basic_eps.qoq.prior` | 65.45 |
| FY26_Q2 | `cmp.basic_eps.yoy.prior` | 48.27 |
| FY26_Q2 | `cmp.profit_before_tax.qoq.prior` | 352.51 |
| FY26_Q2 | `cmp.profit_before_tax.yoy.prior` | 256.7 |
| FY26_Q2 | `cmp.profit_for_period.qoq.prior` | 262.91 |
| FY26_Q2 | `cmp.profit_for_period.yoy.prior` | 193.88 |
| FY26_Q2 | `cmp.revenue.qoq.prior` | 5104.16 |
| FY26_Q2 | `cmp.revenue.yoy.prior` | 4644.51 |
| FY26_Q2 | `cmp.total_expenses.qoq.prior` | 4776.44 |
| FY26_Q2 | `cmp.total_expenses.yoy.prior` | 4420.59 |
| FY26_Q2 | `cmp.total_income.qoq.prior` | 5128.95 |
| FY26_Q2 | `cmp.total_income.yoy.prior` | 4677.29 |
| FY26_Q3 | `calc.2` | 79.15 |
| FY26_Q3 | `cmp.basic_eps.yoy.prior` | 43.55 |
| FY26_Q3 | `cmp.profit_before_tax.yoy.prior` | 238.56 |
| FY26_Q3 | `cmp.profit_for_period.yoy.prior` | 174.91 |
| FY26_Q3 | `cmp.revenue.yoy.prior` | 4716.42 |
| FY26_Q3 | `cmp.total_expenses.yoy.prior` | 4512.04 |
| FY26_Q3 | `cmp.total_income.yoy.prior` | 4750.6 |
| FY26_Q4 | `calc.2` | 75.48 |
| FY26_Q4 | `cmp.basic_eps.yoy.prior` | 62.23 |
| FY26_Q4 | `cmp.profit_before_tax.yoy.prior` | 340.09 |
| FY26_Q4 | `cmp.profit_for_period.yoy.prior` | 249.97 |
| FY26_Q4 | `cmp.revenue.yoy.prior` | 5209.76 |
| FY26_Q4 | `cmp.total_expenses.yoy.prior` | 4886.8 |
| FY26_Q4 | `cmp.total_income.yoy.prior` | 5226.89 |
| FY27_Q1 | `calc.2` | 155.15 |
| FY27_Q1 | `cmp.basic_eps.yoy.prior` | 65.45 |
| FY27_Q1 | `cmp.profit_before_tax.yoy.prior` | 352.51 |
| FY27_Q1 | `cmp.profit_for_period.yoy.prior` | 262.91 |
| FY27_Q1 | `cmp.revenue.yoy.prior` | 5104.16 |
| FY27_Q1 | `cmp.total_expenses.yoy.prior` | 4776.44 |
| FY27_Q1 | `cmp.total_income.yoy.prior` | 5128.95 |

## PILOT-9

Plan: [PILOT-9](../../plans/PILOT-9.md). Evidence: the Task 3 block of `test_pilot_end_to_end`
(`runs += [pilot9(pilot, quarter) for quarter in QUARTERS]`, helper `pilot_e2e_support.pilot9`,
commit `70bbb1f`) against the `shareholding` section of `pilot_manifest.yaml` (commit `eab81b0`,
gpt-6.1-sol APPROVE 2026-10-21, payload `93164041b9cc1734aaa258ef8a062a0d8321170836e39a4a978f562d3f5566b7`;
review `scratchpad/execution/d8/pilot9-task2-r1-sol.md`). Vendor readings live only in the private,
hash-pinned companion, not in git.

| Quarter | Instant | Selected filing | Frozen rows | Point checks | Run status |
|---|---|---|---|---|---|
| FY26_Q2 | 2025-09-30 | gen-4 `SHP_1548120` | 20 | 11 | `COMPLETE` |
| FY26_Q3 | 2025-12-31 | gen-5 `SHP_1602404` | 20 | 11 | `COMPLETE` |
| FY26_Q4 | 2026-03-31 | gen-6 `SHP_1648747` | 20 | 14 | `COMPLETE` |
| FY27_Q1 | 2026-06-30 | Stage 3 gen-2 (pinned Stage 3 run, package and point checks) | Stage 3 | Stage 3 | Stage 3 |

- Per quarter the CLI ingest, `compare run --family shareholding` and `compare report` match the
  frozen rows, outcomes, statuses, queue items, selected filing and vendor evidence identities;
  formed vendor pairs stay `NOT_COMPARABLE / PRECISION_UNSUPPORTED`. Drift fails `PILOT-9: <quarter>`.
- Upstox prints no Sep 2025 or Dec 2025 column: `NO_VALUE` at PQ0/PQ1, no point line, run status
  unchanged. It stays diagnostic.
- **Citations (Decision 3).** No pilot update uses shareholding, so the update-citation clause is
  vacuous; `_pilot9_vacuity` asserts no version carries a shareholding key or section. Separately, the
  `compare report` point lines' assumption labels ("denominator assumed, not vendor-stated") are
  asserted directly. Report labels are not update citations; no sealing, export or citation-survival
  path is claimed.
- **Vendor timing (Decision 4).** These are later-acquired historical-period comparisons: every
  vendor capture was taken after all four source cutoffs (PQ0–PQ2 on 2026-10-21, § Acquisition; PQ3
  in gen-2, 2026-10-20T15:57:00Z–15:57:44Z), and each
  comparison is a separate store-clock `as_known` run made when the e2e runs. They are excluded from
  historical update evidence and do not establish point-in-time vendor knowledge. The first-party side
  is cutoff-clean. Run times: each run is created on a fresh test database when the e2e runs and is not retained; the cited execution is the gate run under "Gate logs".
- Versions (Amendment A1): the 2025-09-30 filing is in the 2025-05-31 SHP taxonomy, so extraction
  moved to `nse-shp-v3` and mapping set v8 (`8b036b7`); the Stage 3 manifest was re-approved at
  payload `731ea8be74398e1b5b4308b58f8f4f293ae06a31d1f9c06b8a31d6d75b6550d6` (`698fcd6`).
- Runtime (2026-10-21): pilot e2e 237.9 s; Stage 3 e2e 94.5 s.

## Acquisition

Decision 1: three live runs of the existing `shareholding acquire` on 2026-10-21, for the PILOT-9
purpose under the existing registered-source authority. The CLI's fixed authorisation string
("plan D8 Task 4") is preserved and is not new authority. Metadata from each generation's
`data/raw/shareholding/APARINDS/gen-N/discovery-manifest.json` (UTC):

| Generation | Instant | Requests | Captured | Outcome |
|---|---|---|---|---|
| gen-3 | 2025-09-30 | 15 | 12:14:17Z–12:15:01Z | Failed attempt: Upstox `HTTP_401`; kept, not used |
| gen-4 | 2025-09-30 | 15 | 12:15:21Z–12:16:06Z | All `OK` (retry of gen-3) |
| gen-5 | 2025-12-31 | 15 | 12:16:19Z–12:17:03Z | All `OK` |
| gen-6 | 2026-03-31 | 15 | 12:17:07Z–12:17:51Z | All `OK` |

PQ3 reuses the retained gen-2. Raw generations are private and gitignored.

## Waiver

PILOT-5's contradiction clause is waived for the Apar pilot (owner, 2026-10-20): Apar's retained
sources contain no genuine contradiction and none was manufactured. It is tested on a later stock that
has one.

## Review record

Reviewer gpt-6.1-sol, all 2026-10-20.

- Phase review: r1 (6 P2, 1 P3), r2 (2 P2), r3 APPROVE.
- Closing review: 1 P2 (`FILED` accepted outside the comparator/tax keys), 1 P3 (PILOT-5 support and
  `MODIFIED` not bound). Both fixed; re-review APPROVE.

Commits: `33b73de`, `11bb672`, `47981be`, `1dbbb90`, `9b2e7d1`.

## Open external items

- Production cutover `eqos-3zl`: done 2026-10-20 (status OPEN; legacy 43/43 EQUAL to fresh).
- The roadmap's [conditions](../../backend-roadmap.md#pilot-conditions), which include the owner blind drill `eqos-4j2.30`, owner review
  timing (PILOT-12; Owner Q1) and D8's phase approval (Sol D8 r4, which also closes `eqos-4j2.32`).
