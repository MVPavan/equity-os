# Five-company test: readiness and protocol (draft)

**Status:** draft for the orchestrator; not reviewed. **Bead:** `eqos-awnc`. **Date:** 2026-11-06.
**Origin:** owner order 2026-11-05 step 4; `docs/specs/2026-11-06-vendor-first.md` §9 (what each
company gets) and its D3 promotion rule. Runs after VENDOR-1 Phases 1–3 land.

Read at `19545c8e`. Retained files were listed and counted, never opened for vendor bodies. The live
store was read once through `scratchpad/live-run-1/counts.py` (table counts only). **Inferred**
marks anything not read directly.

## 1. Scope

Exactly five companies, one per industry: APARINDS (power/electrical), ICICIBANK (bank),
LAURUSLABS (pharma), MTARTECH (precision engineering), NETWEB (AI hardware). Per §9 each gets:
onboarding (the bank per §8, NETWEB per §6.2), basis-correct vendor capture, mapped vendor values,
admission with labels, the fallback command, and `eqos vendor measure`.

Not in scope: vendor text beyond what Phase 2 ships; KPIs and divisions; promoting any mapping
(see §7); report drafts for any company but APARINDS (§5.7).

## 2. Readiness by company

Live store at 2026-11-06 (counts): 1 reporting entity, 1 security, 1 onboarding record, 9 filing
packages, 5 runs, 47 fact admissions, 2 `entity_basis_status` rows, 2 `vendor_basis_bindings`.
`vendor_counterexamples` and `vendor_fallback_outcomes` are absent, so migration 0047 is **not
applied live** (Phase 1 Task 13 pending). The one entity is APARINDS (entity 1, per the spec header).

| | APARINDS | LAURUSLABS | MTARTECH | NETWEB | ICICIBANK |
|---|---|---|---|---|---|
| Identity config (`config/companies/identity/`) | yes, `CONSOLIDATED_AND_STANDALONE` | none | none | none | none |
| Data-spec comparison set (`config/coverage/watchlist.yaml`) | yes | yes | yes | yes | **no** |
| Live entity / onboarding record | yes / `PARTIAL` 2026-10-29 | no | no | no | no |
| First-party XBRL retained (`data/raw/watchlist/`) | 8 (2024-10 → 2026-07 filings) | 1 (Dec-2024 qtr, `in-bse-fin`) | 1 (Dec-2024 qtr, `in-bse-fin`) | 0 | 0 |
| Results PDFs retained | 4 qtrs results + transcripts + decks | 1 BSE PDF | 1 BSE PDF | 1 BSE PDF | 0 |
| NSE listings retained | 2 (2026-10-14) | 1 (2026-10-14) | 1 (2026-10-14) | dev listing + probe (2026-10-16) | 0 |
| Screener financials retained | consolidated, 25 files, 2026-10-14; snapshot store 7 captures 2026-10-17..31 (one request key, inferred Apar) | consolidated, 23 files, 2026-09-04 | consolidated, 23 files, 2026-09-04 | **standalone**, 23 files, 2026-09-04 | none |
| Tijori financials retained | 15 tables 2026-10-14 + 1 snapshot capture | 1 snapshot capture 2026-09-05 | 1 snapshot capture 2026-09-05 | 1 snapshot capture 2026-09-05 | none |
| Vendor-surface reference snapshots (2026-10-28) | 31 files | 0 | 0 | 6 files | 0 |
| Onboarding replay generations (`data/raw/onboarding-dev/live-smoke/`) | gen-1..3, complete (12 requests), consolidated | gen-1..3, complete, consolidated | gen-1: **1 request** (stopped after `EQUITY_L`) | gen-1..2: **3 requests** (listings only) | none |
| Issuer config with `pdf_parse` | yes (`config/runs/aparinds-*.yaml`) | none | none | none | none |
| Onboarding test fixtures (`tests/fundamentals/fixtures/onboarding/fixtures.yaml`) | yes | no | no | listings only | no (HDFCBANK, BAJFINANCE, HDFCLIFE refusal fixtures only) |
| Basis the listings indicate | consolidated + standalone | consolidated + standalone (7 + 7 rows) | consolidated + standalone (6 + 6) | **standalone only** (8 Financials rows, 0 consolidated, dev listing and probe) | not retained; inferred both, analysis basis standalone (owner decision 2) |
| NSE series in retained `EQUITY_L` (2026-10-16/17) | `EQ` | `EQ` | `BE` then; **`EQ`** on the master the orchestrator checked 2026-11-06 | `EQ` | `EQ` (2026-11-06 check) |

### Blockers and gaps found

1. **MTARTECH series (resolved).** `verification.master_rows` accepts only `EQ` rows; MTARTECH
   was `BE` on 2026-10-17 (its live-smoke generation stops after `EQUITY_L`), but the retained
   master metadata the orchestrator checked on 2026-11-06 lists all five as `EQ`. No code change
   (FIVE-1 Task 5). A different series on the acquisition day is an observed refusal, reviewed.
2. **Live acquisition is gated by the Stage 4 freeze.** `eqos onboard --acquire` requires
   `--freeze-descriptor`, which checks the held-out attempt, an `APPROVE`d descriptor and no
   implementation commit since the freeze (`onboard_cli._frozen`, `_check_entry`). VENDOR-1 is
   such a commit. Without `--acquire`, onboarding replays a retained generation; the live-smoke
   generations were made outside the CLI ("live smoke (no freeze)", `eqos-h4h.10`) and predate
   Phase 1's standalone surfaces, so NETWEB and MTARTECH have no usable generation.
3. **Onboarding pins mapping set `v5`** (`ONBOARDING_VERSIONS`), while vendor-first runs on `v9`
   (standalone vendor entries exist only there). Every new company needs an `evidence ingest` and
   a `vendor reingest` under `v9` after onboarding.
4. **One period per new company.** Onboarding ingests the latest filing only
   (`onboard_cli._ingest`), and `vendor reingest` re-ingests only captures an earlier attempt of
   that (entity, period end) cites. No command ingests a retained vendor capture for another
   period, so a new company has one three-way period and no vendor-only period. Its fallback has
   nothing to trigger on; only APARINDS (vendor occurrences across many periods, inferred from
   6,541 occurrences against 9 packages) can exercise fallback.
5. **No admit command.** `admit_run` is called only by the report draft path (`cli._admit`) and,
   per plan Task 10, inside `compare fallback`. The protocol assumes `compare fallback --run <id>`
   admits the triggering run first; if Task 10 does not, a thin `compare admit --run <id>` is
   needed.
6. **Phase 1 is not finished.** Landed on `main`: Tasks 1–8 and 11 (0047, 0048, display rules and
   `vendor reingest`, mapping set `v9`, standalone onboarding, vendor-only runs, policy and pins,
   check class and `vendor measure`, admission rows). Pending: Task 9 (citation, labels in
   render), Task 10 (`compare fallback`, `results_filing.py`), Task 12 (gate; bd notes record an
   incomplete gate), Tasks 13–14 (live migrate and Apar re-measure; eligibility `v1` not yet
   drafted). `origin/main` is at `87c2ba98`, behind `main`.
7. **Phases 2 and 3 have no plan.** The bank route (framework value, `BANK` issuer class,
   dictionary v5, bank mappings) does not exist; nothing for ICICIBANK is retained.
8. **D3 cannot promote anything from this test** (§7).

## 3. Prerequisites by step

| Step | Needs | State |
|---|---|---|
| Migrations 0047, 0048 live | Phase 1 Task 13 | pending |
| Mapping set `v9`, Tijori display rules v5 | Tasks 2, 3 | landed |
| Standalone-only onboarding | Task 4 | landed |
| Vendor-only runs, default vendor sides | Task 5 | landed |
| Policy, T1, filing state, pins | Task 6 | landed |
| Check class, `vendor measure` | Task 7 | landed |
| §6.5 admission rows, labels, withdrawal | Task 8 | landed |
| Labels in citation and render | Task 9 | pending |
| `compare fallback` | Task 10 | pending |
| Eligibility artifact `v1` (Apar) | Task 14 + Sol `APPROVE` | pending |
| Vendor text readers, numeral rule | Phase 2 | not planned |
| Bank framework, issuer class `BANK`, dictionary v5, bank mappings | Phase 3 | not planned |
| A sanctioned live acquisition route outside the Stage 4 freeze | `eqos onboard --acquire --sanction` (FIVE-1 Task 1; §8 Q1) | closed |
| MTARTECH series | `EQ` on the 2026-11-06 master (§8 Q2) | resolved |
| Vendor ingest for periods other than the onboarded one | `evidence acquire` and `vendor reingest --captures-of` (FIVE-1 Task 3; §8 Q3) | closed |

## 4. Order and why

1. **APARINDS.** Already onboarded; retained data for every step; its Phase 1 Task 14 numbers are
   the baseline, so a regression shows at once. The only company that can exercise fallback
   (gap 4).
2. **LAURUSLABS.** The ordinary consolidated non-financial path, with complete prior generations:
   the first new onboarding, least likely to fail for reasons outside the test.
3. **MTARTECH.** Same path (`EQ`, blocker 1 resolved). Run after Laurus so any refusal is not
   confused with a path defect.
4. **NETWEB.** The new standalone-only path (§6.2): new code on live, after the ordinary path is
   proven.
5. **ICICIBANK.** Depends on Phase 3, the least evidenced route; last, so its failures cannot
   disturb the other four.
6. **`vendor measure`** once over all five, after every run, because a check class spans
   companies.

Each company finishes (or stops with a recorded outcome) before the next starts.

## 5. Protocol

Placeholders: `<KEY>` entity key (the NSE symbol), `<PE>` period end, `<b>` basis
(`consolidated` | `standalone`), `<RUN>` run id, `<G>` generation, `<ROOT>` =
`data/raw/five-company/<KEY>`, `<SNAP>` = `data/raw/snapshots/v1`, `<STORE>` the store id
`compare fallback` requires, `<SAN>` = `config/acquisition/sanctions/five-company.yaml`, `<PE0>` a
source period end whose cited vendor captures also hold `<PE>`. Every argument is resolved by
read-only queries and written into `commands.txt` before rehearsal (§6). Every command that takes
versions uses `--dictionary v5 --mapping-set v12`, the Phase 3 sets, for all five (§8 Q5).
`eqos onboard` takes no version flags: it keeps its own pins, and §5.2 re-ingests under `v5`/`v12`.

Standard checks run after **every** command (§6 step 3); the per-step checks below are additional.

### Periods and roles (Q5, F09)

Per entity and basis, `commands.txt` enumerates the period ends that both vendors' captures cover
and onboarding's settings window admits (read-only queries saved beside it; settings are never
extended; a period before the window refuses) and freezes each one's role before rehearsal:

- (a) *filing-check*: `evidence acquire` then `vendor reingest --captures-of`, both before its run.
- (b) *fallback*: a genuinely vendor-only period, with `vendor reingest --captures-of` but **no**
  `evidence acquire`; it is run, then `compare fallback` acquires it.
- (c) the fresh post-fallback rerun that fallback creates.
- (d) *final-pin positive*: an evidenced cell where both vendors agree and no admissible filed
  value exists, in a class that can qualify from the (a)–(c) checks alone, with **no**
  `evidence acquire` and no fallback for that cell before the final-pin segment (§5.6.1).

If live history offers no package-free eligible period for (b), the fallback branch is shown on
the isolated rehearsal fixture and the live limitation is reported; live evidence is never deleted
to make one.

### 5.0 Baseline (read-only)

`eqos db check-live`; table counts; per company: reporting entity, onboarding records,
`entity_basis_status`, settings, packages by (period end, basis), occurrences and interpretations
by (source, mapping set, extractor version, status), runs and pins. **Pass:** check-live green,
0047/0048 in the ledger, APARINDS interpretations under `v9` (Task 13 done), eligibility `v1`
committed.

### 5.1 Onboard

```
eqos onboard <KEY> --raw-root <ROOT> --snapshot-root <SNAP> --acquire --sanction <SAN>   # rehearsal
eqos onboard <KEY> --raw-root <ROOT> --snapshot-root <SNAP> --generation <G>             # live replay
```
(the sanction route of §8 Q1; each acquisition runs on a recorded gated tip. It never uses the
Stage 4 freeze, the holdout record or the manifest.)

| Company | Expected outcome | Checked | Pass |
|---|---|---|---|
| APARINDS | not re-run live (record exists); replay of gen-3 on the rehearsal copy only | outcome vs live record | same outcome, units and basis as the live record |
| LAURUSLABS | `ONBOARDED` or `PARTIAL`; basis consolidated | stdout units; `onboarding_records`; `entity_basis_status = CONSOLIDATED_AND_STANDALONE`; settings `REPORTING_FRAMEWORK = IND_AS` cited `DISCOVERY`; one package, XBRL source `nse-indas-xbrl-consolidated`; Screener and Tijori occurrences for `<PE>` | all hold; no unit `NOT_AUTHORISED` without a stated reason; the printed `compare run` command names the consolidated basis |
| MTARTECH | as LAURUSLABS | as LAURUSLABS | as LAURUSLABS; a non-`EQ` master on the day is a recorded refusal, reviewed, not a pass |
| NETWEB | `ONBOARDED`/`PARTIAL`; basis status `STANDALONE_ONLY` | `entity_basis_status = STANDALONE_ONLY`; package basis standalone, XBRL source the standalone NSE entry; Screener page fetched on the standalone path; no consolidated vendor occurrence pairs with the package | all hold (acceptance 4 on live) |
| ICICIBANK | Phase 3 route: grounding record first (§8 step 1), then `ONBOARDED`/`PARTIAL` as issuer class `BANK`, analysis basis standalone stored apart from reported bases | grounding record capture ids precede every onboarding check; framework the filing evidences; issuer class `BANK` | all hold; an NBFC/insurer is still `UNSUPPORTED` (fixture, not live) |

### 5.2 Re-interpret under `v12`

```
eqos evidence ingest --retrieval-manifest <ROOT>/gen-<G>/retrieval-manifest.json --issuer <KEY> \
  --quarter <Q> --period-end <PE> --basis <b> --raw-root <ROOT>/gen-<G> --snapshot-root <SNAP> \
  --mapping-set v12 --dictionary v5
eqos vendor reingest --entity <KEY> --period-end <PE> --basis <b> --mapping-set v12 --dictionary v5
```
Apar is re-ingested live under `v5`/`v12` like the others. Per role (a) period:
```
eqos evidence acquire --entity <KEY> --basis <b> --period-end <PE> --mapping-set v12 --dictionary v5 \
  --snapshot-root <SNAP> --raw-root <ROOT> [--issuer-config <yaml>] [--generation <G>]
eqos vendor reingest --entity <KEY> --period-end <PE> --basis <b> --mapping-set v12 --dictionary v5 \
  --captures-of <PE0>
```
One period per `evidence acquire` command and generation. It prints `<PE> package <id>`,
`FILING_UNAVAILABLE` or `FILING_UNRESOLVED` and exits `INCOMPLETE` unless ingested. Role (b)
periods run only the `vendor reingest --captures-of` line. **Checked:** interpretations under `v12` per (representation,
status); Tijori `INVALID`/`UNIT_MISMATCH` in sections with a display rule; NETWEB vendor
interpretations on standalone sections only. **Pass:** zero `UNIT_MISMATCH` in ruled sections;
every Tijori row in an unruled section is `UNKNOWN_UNIT`, never a value; per package, first-party
counts per (representation, status) under `v12` equal those under `v5`.

### 5.3 Compare

```
eqos compare run --entity <KEY> --period-end <PE> --basis <b> --mode as_known \
  --dictionary v5 --mapping-set v12 --eligibility v1
```
`v1` is Apar's pilot artifact; under `v5`/`v12` it matches no class, so these runs cannot admit
under §6.5 row 3 (FIVE-1 reading 4). Row 3 under the final pins is exercised in §5.6.1.
No `--vendor` (Screener and Tijori by default). APARINDS: every period end in its Task 14 scope,
plus the vendor-only period ends chosen for fallback (5.5). Others: the onboarded `<PE>` and their role (a)/(b) periods.
**Checked:** run status; `run_versions` pins (`vendor_first_policy`, `eligibility`); three-way
cells per (canonical id, period); T1 outcomes and filing states from results and pair records;
the `COVERAGE` lines; open `HIGH` queue items. **Pass:** run complete (exit `SUCCESS` or
`SUCCESS_WITH_OPEN_HIGH` with every `HIGH` item listed); Screener and Tijori sides present; for
NETWEB no consolidated cell has a value (all `NOT_APPLICABLE`); for ICICIBANK non-financial-only
rows `NOT_APPLICABLE`, shared and bank rows valued; `COVERAGE` `missing = 0`, or each missing key
listed for review.

### 5.4 Admit

Via `compare fallback --run <RUN>` (5.5), which admits the run first (gap 5). **Checked:**
`fact_admissions` rows by `label`; refusals by reason; `vendor_counterexamples` rows;
`witness_interpretation_id` and `eligibility_version` on every `VENDORS_AGREE_NOT_CHECKED` row.
**Pass:** each admitted cell's row matches §6.5 recomputed by code from the run's results (one
expected row per cell, all equal); no `VENDORS_AGREE_NOT_CHECKED` on a class with a
counterexample; no FY `finance_costs` cell under row 3; every row with T1 `VENDORS_AGREE` and
`FILING_DIFFERS` has a counterexample whatever its row.

### 5.5 Fallback

```
eqos compare fallback --run <RUN> --store-id <STORE> --snapshot-root <SNAP> --raw-root <ROOT> \
  [--issuer-config <yaml>] [--generation <G>]
```
Rehearsal acquires into its raw root; live replays with `--generation` (§8 Q4). A run's trigger
groups are its stored `CHECK_REQUIRED`, `VENDOR_UNMAPPED`, `VENDORS_DISAGREE` and
`VENDORS_IMPRECISE` refusals, so a filing-present run may still trigger; expectations are derived
from those stored refusals, not from filing presence. Fallback refuses before fetching if one run
triggers more than one group. **Role (b) periods** (all companies): expected per company-period
`ADMITTED`, `FILING_UNAVAILABLE`, `FILING_UNRESOLVED` or `STILL_REFUSED`; the fallback period is
not pre-acquired. **Other runs:** a run with no such refusal expects no trigger and no
acquisition; one with such a refusal expects the outcome its refusal group implies. **Checked:** `vendor_fallback_outcomes` rows; the fetch log names only that issuer and
period; new captures and packages only for triggered (entity, period end, basis); watchlist and
coverage tables unchanged. **Pass:** every trigger group has exactly one stored terminal outcome;
no other issuer fetched; `ADMITTED` groups have no refused trigger cell in the rerun.

### 5.6 Measure

```
eqos vendor measure --available-from <T> --out scratchpad/five-company/eligibility-v2.yaml
```
Once, after all five. `<T>` fixed before the command and later than every counted run.
**Checked:** classes, `FILING_AGREES`/`FILING_DIFFERS` key-period counts per class, run ids; rerun
gives identical bytes. `measure` reads every policy-pinned stored run, older classes included;
final-pin classes (dictionary `v5`, mapping set `v12`) are reported separately from older ones.
**Pass:** byte-identical rerun; no vendor value in the file; counts match
read-only queries over the same runs. The file is a draft; it is committed only after Sol's
`APPROVE` and pinned in later runs, never in the runs it measured.

### 5.6.1 Final-pin segment (F04, Q6)

Sol reviews and the orchestrator commits the measured draft as a new eligibility version (never
`v1`, never backdated, no mapping promoted, BANK classes excluded as Phase 3 specifies).
**Artifact boundary:** `commands.txt` then names a new gated revision that contains that artifact
(the loaded config tree, `run_config.py`), and the remaining commands are re-inventoried on it
before this segment's rehearsal; the equal-revision rule (§6) applies to that revision, and nothing
runs the artifact from the older tree. Immediately before the positive run, a read-only query saved
beside `commands.txt` shows the role-(d) cell still has no admissible filed value. Fresh `compare
run` commands at a cutoff at or after the artifact's `available_from`, over the role-(d) periods,
then admit. **Pass:** the role-(d) cell admits as `VENDORS_AGREE_NOT_CHECKED` with both witnesses
and the artifact pin; its citation shows the label; a calculation over it shows the weaker label.
On isolated rehearsal copies: the same cell at a cutoff before `available_from` refuses, and a
counterexample in the class blocks it. If no suitable live role-(d) cell exists (no class
qualifies, no vendor-only agreeing input remains, or the pre-run query finds a filed value), the
limitation is recorded and the positive case runs on a clearly identified isolated fixture; live
unchecked admission is then not claimed. Evidence is never deleted and no cutoff is backdated to
make a cell.

### 5.7 Report draft

APARINDS only (the only issuer with a run config, results PDF, transcript and `pdf_parse`), via the
existing `eqos run` draft path on its latest quarter, after Task 9. **Pass:** every number rendered
with its label; citations resolve with the label; a calculation shows its weakest input label.
Others: out of scope (no run config, no `pdf_parse`).

## 6. Live protocol

Writes live: 5.1 (onboarding records, entities, securities, settings, captures, packages,
occurrences, interpretations, attempts; snapshot-store files), 5.2 (interpretations, occurrences,
attempts, version pins), 5.3 (runs and their result tables, queue items, version pins), 5.4/5.5
(fact rows, admissions, selections, counterexamples, fallback outcomes; for APARINDS also captures
and packages). 5.0 and 5.6 are read-only (5.6 writes one scratch file).

As `docs/plans/VENDOR-1-P1.md` "Live protocol", per company:

1. **Inventory.** `scratchpad/five-company/<KEY>/commands.txt`, every argument explicit, inputs
   from saved read-only queries; record its sha256. Rehearsal and live run that file unchanged.
2. **Baseline.** `eqos db backup` of live, restored into a fresh `eqos_test_*`; counts and
   fingerprints equal live's, or stop.
3. **Checks after each command:** `eqos db check-live`; counts of every `eqos` table; business-key
   summaries (as Phase 1, plus admissions by label, counterexamples by class, fallback outcomes);
   fingerprints of pre-existing rows of touched tables, unchanged.
4. **Allowed changes** per step as listed above; a rehearsal delta outside them stops before live;
   each live delta must equal the rehearsal's.
5. **Before live:** live equals the baseline (counts, fingerprints, ledger, check-live, sequences);
   before each later command, baseline plus rehearsed deltas. Any drift restarts from step 2.
6. **Network steps.** Onboarding and fallback fetch. Rehearsal acquires into a rehearsal raw root
   and snapshot root; live **replays** the rehearsal's retained generation (`--generation`) so its
   writes equal the rehearsal's. Fallback and `evidence acquire` replay the same way
   (`--generation`, §8 Q4).
7. Drop the rehearsal database and rehearsal snapshot root at the end.

Live writes are permanent. Admissions in 5.4/5.5 are the first on live (Phase 1 admitted none) and
change what later APARINDS reports select (§8 Q6).

## 7. D3: what this test can promote

A mapping reaches `EQUIVALENCE_DEMONSTRATED` only with ≥5 distinct companies inside its own scope
(surface, schema, basis, period kind, conditions) plus a discriminating case. Here: consolidated
non-financial scope has at most APARINDS, LAURUSLABS, MTARTECH (3);
standalone vendor tables are fetched only for `STANDALONE_ONLY` entities, so standalone scope has
NETWEB (1); ICICIBANK is in bank scope alone (1). **Expected promotions: zero.** Pass criterion:
the test report claims no promotion and lists, per mapping, the companies and discriminating cases
it contributed.

## 8. Open questions

1. **Live acquisition route.** Answered by `docs/plans/FIVE-1-enablement.md` Task 1:
   `eqos onboard --acquire --sanction <file>`, a committed, stamped sanction listing the symbols;
   no re-freeze, and the Stage 4 freeze checks are unchanged.
2. **MTARTECH series.** Resolved: `EQ` on the 2026-11-06 master; no `BE` widening, no swap
   (FIVE-1 Task 5).
3. **More than one period per new company.** Answered by FIVE-1 Task 3: `evidence acquire` per
   named period and `vendor reingest --captures-of`.
4. **Fallback replay.** Answered by FIVE-1 Task 2: `compare fallback --generation N`.
5. **Dictionary.** Answered by FIVE-1 reading 4: all five under dictionary `v5`, mapping set `v12`.
6. **Live admission scope.** Owner decision 4 covers the pilot. Admitting live also changes
   APARINDS's future report selection; confirm, or admit into a separate fact store.
7. **ICICIBANK in the comparison set.** Answered by FIVE-1 Task 4: a comparison-config entry
   written only from identifiers a retained capture shows; a missing identifier blocks it.
