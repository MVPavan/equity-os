# Pilot report: Apar, PQ0–PQ3 (PILOT-E2E)

**Verdict: CONDITIONAL on D8.** PILOT-9 is not met (shareholding not built). PASS, Phase 0.5 closure
and `PILOT_PROVEN: YES` stay reserved. `eqos-4j2.8` stays open.

Plan: [PILOT-E2E](../../plans/PILOT-E2E.md). Checks: [backend roadmap §4](../../backend-roadmap.md).
Gate test: `tests/fundamentals/test_pilot_e2e.py` (one ordered `test_pilot_end_to_end`; helpers in
`tests/fundamentals/pilot_e2e_support.py`). Expected values come only from the frozen
`pilot_manifest.yaml`; failing assertions begin `PILOT-n:`.

Full suite at `7c640ad`: `uv run pytest tests/fundamentals` 4291 passed, 9 skipped (1:31:35), exit 0. `mypy --strict src` and ruff clean. `scripts/verify_project.sh` after the production cutover: every row PASS (Pilot, Pytest, Mypy, Ruff, frozen manifests), "Project incomplete: 0 failed, 1 not built" (D8), exit 1 as expected.

## Checks

| ID | Status | Evidence |
|---|---|---|
| PILOT-1 | MET | Independent expected row inventory from the pinned dictionary and retained disclosures (`pilot_e2e_support.py`): no missing or extra rows, both sides `VALUE` where located, no zero fill, PQ0 PBT 340.56 / 340.53 and OPM `C7_OPM` equal the manifest, PQ3 segment block is an explicit failure state (`eqos-ghv` stays open) |
| PILOT-2 | MET | Per quarter, both vendors `COMPLETE`; each row's queue items equal what the routing policy proposes; `UNAVAILABLE` sides keep failure evidence; PQ0 opex `{pair, triage, queue}` equals the manifest. Policy agreement is an integration check, not independent proof of every routing rule; mapped cells are not asserted as corroboration |
| PILOT-3 | MET (rehearsal); production cutover EXTERNAL | Disposable legacy import, `reconciled.equal()` and cutover (`test_cutover_rollback.Window`), then the no-SQLite guard. Production cutover `eqos-3zl` gates acceptance |
| PILOT-4 | MET | Per version: the 46 non-quote values equal `quarters[Q].claims`, source cutoff and retrospective label, claim check, owner `APPROVE`, export sha256 = `content_hash`; qoq priors of PQ1–PQ3 cite the predecessor's `fact.<role>`; `FILED` claims keyed only `cmp.*.prior` / `calc.2` with the rendered suffix; counts in the filed-value section |
| PILOT-5 | MET (contradiction clause waived) | Boundary retrieval, replay, late events excluded, empty retrieval at a historical source cutoff, supersession G → G′ with G's provenance equal to the PQ1 cables claim support and PQ2's transition asserted `MODIFIED` (`_pilot5`) |
| PILOT-6 | MET | `ledger export --stock APARINDS --status-notes --memory` as the runtime role, read-only; narratives hash to `content_hash`; `memory.md` lists the promoted ids |
| PILOT-7 | EXTERNAL | D6 exit `tests/fundamentals/test_data_stage4_e2e.py`; the holdout stays blind and was not touched |
| PILOT-8 | MET | Head is the owner `ADD`; after owner `REMOVE` a runtime draft is refused "is not on the watchlist" with report/version counts unchanged |
| PILOT-9 | NOT MET | The test records that no shareholding key or section exists; absence is not credited as met. D8 is parked (`eqos-4j2.32` open) |
| PILOT-10 | MET | Real-clock classify, backup, dry-run, purge, guarded `db restore --replay-runs`: listed set equals the eligible set, no hold root listed, held blobs hash-verified. An empty purge is not observed deletion; positive deletion is D9's exit |
| PILOT-11 | MET except blind drill (EXTERNAL) | (i) interrupt after `admit_run`, retry without duplication; (ii) PQ2 v1 rejected on `cmp.revenue.qoq.prior`, only QoQ lines rerun, successor v(N+1) approved; (iii) seeded shadow states are not `ANSWER` and owner approval is refused. Detecting review-only seeds needs the owner's blind run `eqos-4j2.30` |
| PILOT-12 | MET (instrumentation); owner timing EXTERNAL | Five run-generated versions each have exactly one `review_sessions` row, full `claim_reviews` coverage, the scripted PQ2 rejection and the two-session report totals. Scripted times are instrumentation only; the owner's real review of four reports is open |
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

## Waiver

PILOT-5's contradiction clause is waived for the Apar pilot (owner, 2026-10-20): Apar's retained
sources contain no genuine contradiction and none was manufactured. It is tested on a later stock that
has one.

## Review record

Reviewer gpt-6.1-sol, all 2026-10-20.

- Phase review: r1 (6 P2, 1 P3), r2 (2 P2), r3 APPROVE.
- Closing review: 1 P2 (`FILED` accepted outside the comparator/tax keys), 1 P3 (PILOT-5 support and
  `MODIFIED` not bound). Both fixed; re-review APPROVE.

Commits: `171bd47`, `38eac49`, `4c318e4`, `4de844d`, `7c640ad`.

## Open external items

- Production cutover `eqos-3zl`: done 2026-10-20 (status OPEN; legacy 43/43 EQUAL to fresh).
- Owner blind drill `eqos-4j2.30`.
- Owner review timing (PILOT-12; Owner Q1 in the plan).
- D8 shareholding (PILOT-9; `eqos-4j2.32`).
