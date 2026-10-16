# Roadmap: data-foundation

Status: approved and seeded in bd (`16140d0`); in execution. This is the plan of the backend core
(data foundation). What the core is and how to verify it: [`core.md`](core.md). All backend work
and the pilot that decides project completion: [`../../backend-roadmap.md`](../../backend-roadmap.md). "Panel" in this file now means the single reviewer's approval
(owner, 2026-10-12; `.claude/rules/core/04-agent-stack.md`); the ledger spec states it by its
2026-10-15 amendment (`eqos-uqu.10`).
Specs: [data spec](../../specs/2026-10-11-canonical-financial-data-and-cross-source-comparison.md)
(Stages 1–4, "dS1–dS4") and [ledger spec](../../specs/2026-10-12-report-ledger-memory-and-data-lifecycle.md)
(Stages 1–5, "lS1–lS5"). The ledger spec amends data spec §4–§8 retention and replay (ledger §6).

## Progress

Last updated 2026-10-14. bd (`bd list --label ws-data-foundation`) holds the live state; this
section is the human summary.

| Phase | Stages | State |
|---|---|---|
| D1a Canonical comparison tracer | 7 | Complete. Review fixes committed `22a3c78`; all original and subsequent findings addressed; independent r3 and fresh critical re-review APPROVE. Stable suite 2,787 passed / 8 existing optional skips, strict mypy and Ruff lint/format green. Tracer exit green; epic `eqos-3f9` closed. |
| D1b Vendors, corroboration, queue, Stage 1 acceptance | 6 | Complete. Exit `tests/fundamentals/test_data_stage1_e2e.py` matches the frozen Stage 1 manifest exactly (10 runs, every fixture; manifest Sol-approved and payload-bound, `a5bbba1`). Phase review: three Sol rounds, then a fresh critical review and re-review, APPROVE 2026-10-14 (fixes `a9caa2b`, `5b5cb73`, `241e530`, `e02ba87`). PDF extractor `pdf-occurrences/2`; migrations 0008–0009. SONACOMS dropped (owner, 2026-10-14); eight companies XBRL-only (reviewer ruling D2). Epic `eqos-u0u` closed. |
| D2 Legacy store migration and cutover | 8 | Complete on test databases. Exit `tests/fundamentals/test_data_stage2_e2e.py` matches the frozen Stage 2 manifest (Sol-approved, payload-bound, `c44ec4b`) and `scripts/stage2_recreation_check.sh` exits 0; migrations 0010–0011. Phase review: Sol r1 REJECT (14), fixes `222f796`, r2 APPROVE; fresh critical review REJECT (7), fixes `c4ce74d`, re-review APPROVE 2026-10-15. Full suite 3,268 passed. Epic `eqos-01q` closed. Production import and cutover remain the owner-gated `eqos-3zl`. |
| D3 Report ledger | 9 | Complete on test databases. Exit `tests/fundamentals/test_ledger_stage1_e2e.py` green against the frozen ledger manifest (Sol-approved, payload-bound, `ed1ebce`); `ledger export` reproduces every imported Apar version's content hash. Amendments recorded and Sol-approved (`5b5eb5e`); migrations 0012–0015. Phase review: Sol r1 REJECT (12), fixes, r2, r3 APPROVE (`25be9bb`); fresh critical review REJECT (8; finding 6 parked as `eqos-0eu`), fixes `483b7c6`, re-review APPROVE 2026-10-15. Full suite 3,450 passed. Epic `eqos-uqu` closed. |
| D4 Long-term memory | 5 | Complete on test databases. Exit `tests/fundamentals/test_ledger_stage2_e2e.py` green against the frozen ledger Stage 2 manifest (Sol-approved, payload-bound, `bc4eaae`): a cables-margin item over transcript-bound corrective versions is retrieved only after a panel `PROMOTE`. Plan amendments A1, A2, C2, C3, R, M9 and T1 (first-party transcript admission) Sol-approved; migrations 0016–0020. Phase review: Sol r1 REJECT (5), fixes `078a99b`, r2 APPROVE; fresh critical review REJECT (4), fixes `92491c4`, `607bb67`, re-review APPROVE 2026-10-15 (evidence-layer knowledge-time gaps parked as `eqos-d60`). Full suite 3,578 passed. Epic `eqos-4hi` closed. |
| D5 Generated views | 5 | Complete on test databases. Exit `tests/fundamentals/test_ledger_stage3_e2e.py` green against the frozen ledger Stage 3 manifest (Sol-approved, payload-bound, `d913827`): `ledger export --stock` writes Apar's sealed narratives (each hashing to its content hash), status notes and promoted memory, and the read-only `eqos_reader` role selects two status views and writes nothing. Migration 0021. The optional vault (D5.3) is not built (ruling V1). Phase review: Sol r1 REJECT (4), fixes `ddee0f0`, r2 APPROVE; fresh critical review REJECT (3), fixes `fde6b16`, re-review APPROVE 2026-10-15 (SQL-level SUBMIT hash gap filed as `eqos-7pr`). Full suite 3,601 passed. Epic `eqos-tfb` closed. |
| D6 Identifier-only onboarding | 6 | Not started |
| D7 Coverage model | 6 | Not started |
| D8 Shareholding filing source | 5 | Not started |
| D9 Retention and replay | 9 | Not started |

40 of 66 stages are closed (D1a 7; D1b 6; D2 8; D3 9; D4 5; D5 5, the optional vault closed as not built). D1a's stages are the shared foundation (schema, dictionary, formula
engine, evidence model, decision tables, runs), so their share of the effort exceeds their count.

**Execution loop per phase** (`.claude/rules/core/04-agent-stack.md`):
1. Opus writes the phase plan just in time, and Sol reviews it.
2. Opus builds each stage. The orchestrator verifies it against tests, mypy and the acceptance
   values, then commits it and closes its bd stage.
3. At phase end, Sol does one exhaustive review. Opus fixes, Sol re-reviews, and a fresh Sol
   critical review follows.
4. Exit test green → close the epic.

Only one worker runs at a time (parallel workers hit the API rate limit).

**Estimate (inference from D1a only, not a measurement).** D1a took about 1 day of planning and
review, about 7 hours of build and about 1–2 days of phase review and fixes, so 2–3 days of
wall-clock per phase. The remaining58 stages come to about 3–6 weeks of continuous running.
Riskiest: D1b (live vendor data for ten companies), D2 (real legacy migration and cutover) and D9
(deletion under concurrency). API rate limits are the largest schedule risk.

**Open items found during D1a** (bd beads):
- Mapping set v1 does not cover the SEBI 2026-01-31 XBRL taxonomy (Apar FY26 Q4), and the Q4 PDF
  revenue rows extract `INVALID`. Needed before Q4/FY coverage in D1b.
- `eqos-u0u.7`: resolved source-inventory prerequisite (`a131b74`): all 17 rows have cited EXCLUDED_UNPROVEN dispositions; positive missing-vendor proof remains open.
- `eqos-uqu.10`: ledger spec amended 2026-10-15 to single-reviewer approval (approved with the D3 plan).
- The two former `test_source_intake_store` failures are resolved (`3e966cb`); 42 cases passed.
- The schema-test size issue is resolved (`6077ca3`); original case inventory preserved.
- Migration numbering: `0001`–`0007` are committed; `0006_vendor_and_queue.sql` and `0007_construction_traces.sql` replaced Codex's `0006`–`0010` on 2026-10-14 (the real `equity_os` database had never applied any migration). Once a migration is applied to `equity_os` it is immutable; new SQL takes the next free number (`0008`+). Later phases' planned names (e.g. `0006_views_readonly.sql`) must be renumbered when planned.
- The dev host's wall clock steps backwards (WSL2). Store time comes from the monotonic
  `eqos.store_now()`.

## Conventions

- **One phase per spec stage, except dS1.** Every phase ends with a demoable result. dS1 is split
  into a tracer, D1a (one company and period through the first-party extraction check on
  PostgreSQL, checked against spec-stated values), and D1b (vendors, corroboration, queue,
  amendment, frozen Stage 1 manifest and e2e). The full Stage 1 frozen manifest, in D1b, gates every
  dependent phase. No other stage is split or merged, because each has its own acceptance
  criteria and its own amendment gate.
- **Paths are proposed.** The phase plan fixes the file map at elaboration. A change of stage
  scope needs a roadmap edit. Proposed new packages under `src/fundamentals/`:
  `pg/` (settings, pool, migrations runner), `canon/` (dictionary, mappings, formulas),
  `evidence/` (occurrences, interpretations, selection), `compare/` (comparator, runs, queue),
  `ledger/`, `memory/`, `coverage/` and `retention/`. SQL migrations go in `migrations/`. New
  tests are flat files in `tests/fundamentals/`. Tests that need PostgreSQL carry a `pg` pytest
  marker (so `-m "not pg"` excludes them); Verify cells run whole files with no marker filter.
  PostgreSQL tests use a dedicated test database and never touch the main one (data spec §6).
- **Frozen manifests come first.** Every phase except D1a has a manifest stage. Its file is
  hand-verified from source documents, panel-approved, and committed before the e2e stage runs.
  Code under test never generates it (both specs' Success Criteria). One shared test,
  `tests/fundamentals/test_frozen_manifests.py` (created in D1b.5, one parameter per manifest),
  checks each header's hand-verification and panel-approval records and that the manifest's first
  commit precedes its e2e test's first commit.
- **Amendment records** live in `docs/blueprint/amendments/`. One shared test,
  `tests/fundamentals/test_amendment_records.py` (created in D1b.4, one parameter per record),
  checks that each record cites its spec, lists exactly its amendments, records panel approval
  (reviewers, verdicts, date) per amendment, and that its doc links resolve.
- **Fixtures** are the real retained captures named in the specs. Failure, correction and
  ambiguity fixtures withhold, mark or re-interpret those captures; they never invent values.
- **Test focus** follows `.claude/rules/python/testing.md`: integration and e2e on the PostgreSQL
  test database first, and unit tests only for dynamic financial logic.
- **Gate per phase:** `scripts/verify.sh gate <slice>` (`.claude/project/verification.md`),
  plus the Verify cells below. D1a did not capture the gate's red proof (`verify.sh red`)
  before building, so its gate cannot pass. From D1b on, run `scripts/verify.sh red <slice>`
  on each stage's acceptance tests before dispatching the implementer.
- **Owner-reserved steps.** Data spec §6 steps 1 and 3 (import-manifest confirmation,
  unresolved-originals preflight) and the Stage 2 cutover approval go to the approval panel under
  the owner's 2026-10-12 autonomy directive. The orchestrator executes them and informs the owner.

---

## D1a: Canonical comparison tracer (dS1, part 1)

**Goal.** Take Apar Q2 FY26 consolidated from retained first-party captures through occurrences,
interpretations, the extraction check and a run on PostgreSQL to the report CLI. This proves
schema, dictionary, engine, first-party adapters, extraction tables and runs end to end before
vendors and the queue are added. Only evidence tables are written; legacy SQLite stays the fact
system of record.

| # | Stage | Create/modify paths | Verify |
|---|---|---|---|
| 1 | PostgreSQL service, evidence schema and identity tables | `compose.yaml`, `.env.example`, `src/fundamentals/pg/`, `migrations/0001_evidence.sql` (occurrences, interpretations, definition sets, runs, results; entity, security and listing tables seeded from the existing entity map), `pyproject.toml` (driver dep, `pg` marker) | `uv run pytest tests/fundamentals/test_pg_evidence_schema.py`: runtime role UPDATE/DELETE on every evidence table is refused; migration role owns the schema; nulls-equal identity constraints hold; entity, security and listing rows seeded from the existing entity map each carry a stable internal id |
| 2 | Canonical dictionary v1, applicability rules and loader | `config/dictionary/v1/`, `src/fundamentals/canon/dictionary.py`, `src/fundamentals/canon/applicability.py`, `docs/specs/artifacts/dictionary-v1-manifest.md` | `uv run pytest tests/fundamentals/test_canon_dictionary_load.py tests/fundamentals/test_canon_applicability.py`: dangling ids, unit-algebra mismatches, cycles, member-of-member aggregation lists and duplicate selectors each fail the load loudly; the resolved v1 manifest's counts per family match the committed manifest; applicability is decided before any value is examined: balance-sheet rows are `NOT_APPLICABLE` for a Q1 or Q3 package with no balance sheet and applicable for the September half-year package; a standalone-only issuer's consolidated rows are `NOT_APPLICABLE` |
| 3 | Formula, interval and period-aggregation engine | `src/fundamentals/canon/formula.py`, `src/fundamentals/canon/interval.py`, `src/fundamentals/canon/period_aggregation.py` | `uv run pytest tests/fundamentals/test_canon_formula.py tests/fundamentals/test_canon_interval.py`: exact rational evaluation, half-even storage with outward bounds, temporal roles (CLOSING/OPENING/AVERAGE), dimensional aggregation, Q4 = FY − 9M with `REVISION_INCOMPATIBLE`, and the calculation-state table row by row |
| 4 | First-party adapters, occurrences, interpretations and package selection (XBRL `in-bse-fin` + `in-capmkt`, PDF) | `config/mappings/xbrl/`, `config/mappings/pdf/`, `src/fundamentals/evidence/`, `src/fundamentals/contracts/acquisition_outcome.py` | `uv run pytest tests/fundamentals/test_evidence_first_party.py tests/fundamentals/test_evidence_selection.py`: Apar Q2 FY26 `profit_before_tax` 340.56 and `profit_before_tax_incl_associates` 340.53 crore; OPM 8.06% has a stored trace; missing-value states are never zero-filled; package selection under cutoff and mode (unit); the correction, family, revision (first-party part) and dimensional (segment member, elimination basis) fixtures behave as written; `UNMAPPED` lines are kept |
| 5 | Pair, extraction and derived-extraction decision tables | `src/fundamentals/compare/tables.py`, `src/fundamentals/compare/triage.py`, `config/comparison_policy/v1.yaml` | `uv run pytest tests/fundamentals/test_compare_extraction_tables.py`: the pair, extraction and derived-extraction tables row by row; triage at the 0.5% threshold; adjacent integer counts never agree; a single-representation family gives extraction `NOT_APPLICABLE` |
| 6 | Runs, manifests, replay and report CLI | `src/fundamentals/compare/run.py`, `src/fundamentals/api/compare_cli.py` (`run`, `report`) | `uv run pytest tests/fundamentals/test_compare_runs.py`: two concurrent default-cutoff reruns over unchanged evidence produce one run and no duplicate rows; replay from the manifest alone reproduces the run; a dictionary, mapping or definition-set change produces a new run; with the database unreachable, `fundamentals compare run` exits nonzero and leaves no visible partial run; the Q1/Q3 no-balance-sheet fixture reports balance-sheet rows `NOT_APPLICABLE`, never `NO_SOURCE` |
| 7 | Tracer end-to-end | `tests/fundamentals/test_compare_tracer.py` | `uv run pytest tests/fundamentals/test_compare_tracer.py`: a run over Apar Q2 FY26 retained first-party captures on the test database, then the `fundamentals compare report` CLI shows revenue, total income, total expenses, `profit_for_period` and basic EPS with extraction `AGREE`, PBT 340.56 and 340.53 crore, headline 340.53, and OPM 8.06% with its trace (spec-stated values; the frozen manifest is D1b's) |

**Spec refs.** Data spec §0, §1 (incl. applicability), §2 first-party mappings, §3 identity
layers and basis, §4, §5 (pair outcomes, tolerance, extraction status, runs), §6 (service
contract, schema and integrity, concurrency, credentials), Success Criteria Stage 1 (Apar happy
path, calculation, correction, family, revision, dimensional, unreachable-database cases).
**Exit (D1a):** `uv run pytest tests/fundamentals/test_compare_tracer.py` is green: `uv run
fundamentals compare report` shows the Apar Q2 FY26 consolidated extraction check from
PostgreSQL.
**Test focus.** The tracer e2e over retained Apar captures and the integration of adapters → runs.
Unit tests cover only stages 2 (applicability), 3, 5 and package selection (interval and
rational arithmetic, decision tables, temporal roles, revision compatibility, the 0.5% threshold).
**Risk.** Deep: this is the new shared store and the first-party decision tables, and every later
phase builds on its contracts.
**Supersedes:** `eqos-ya6` (relative-figure triage is replaced by the 0.5% policy threshold).

## D1b: Vendors, corroboration, queue and Stage 1 acceptance (dS1, part 2)

**Goal.** Add the vendor adapters and source authority, corroboration and trust, the review queue
and dispositions, then run the canonical comparison for Apar and the watchlist companies (nine; SONACOMS dropped by the owner 2026-10-14) and
match the frozen Stage 1 manifest.

| # | Stage | Create/modify paths | Verify |
|---|---|---|---|
| 1 | Vendor adapters and source authority (Screener, Tijori, Upstox diagnostic) | `config/mappings/screener/`, `config/mappings/tijori/`, `config/mappings/upstox/`, `src/fundamentals/evidence/vendor_*.py`, source catalog entry for Upstox diagnostic-only | `uv run pytest tests/fundamentals/test_evidence_vendor.py`: Tijori's TTM column is stored as TTM; Upstox annual data on a quarterly request is stored as annual; the NETWEB degenerate consolidated page and the empty Upstox response yield no values; an unregistered surface gives `NOT_AUTHORISED`; a vendor capture is never eligible before its registration time; Screener "Total Liabilities" maps to no liabilities row; Tijori `qt_c` "Net Profit" maps to `profit_continuing_after_tax` |
| 2 | Corroboration table, trust view and diagnostic routing | `src/fundamentals/compare/tables.py`, `src/fundamentals/compare/routing.py` | `uv run pytest tests/fundamentals/test_compare_corroboration.py tests/fundamentals/test_compare_diagnostic.py`: the corroboration table row by row (unit); one demonstrated vendor mismatching while another agrees gives `CONFLICT`; an `INVALID` only vendor gives `NOT_COMPARABLE`, never `FILING_ONLY` or `NO_SOURCE`; the September half-year balance sheet with no vendor counterpart gives `FILING_ONLY`; `NO_SOURCE` arises only for applicable rows; diagnostic pairs never enter a status; Upstox summary vs `full_statement` (NETWEB, POLYCAB) with disjoint intervals gives `NOT_COMPARABLE` with `VENDOR_INTERNAL_CONFLICT`, MEDIUM, both occurrences retained (owner amendment 2026-10-14: Upstox precision is undocumented, so Upstox pairs are `NOT_COMPARABLE`/`PRECISION_UNSUPPORTED`, MEDIUM; conflict only via evidenced contradictory semantics) |
| 3 | Review queue, dispositions and run exit statuses | `src/fundamentals/compare/queue.py`, `src/fundamentals/compare/run.py`, `src/fundamentals/api/compare_cli.py` (queue commands), `migrations/0002_review_queue.sql` | `uv run pytest tests/fundamentals/test_compare_queue.py`: queue items are append-only and keyed per the spec; `ACCEPTED_AS_DEFINITION` changes no result, and a new definition set produces a new run; the failure fixture makes the run `INCOMPLETE`, and replay of a run with a failed attempt reproduces `UNAVAILABLE`; an `UNMAPPED` line is queued LOW; exit statuses separate success, success with open HIGH items, `INCOMPLETE` and failure |
| 4 | Register amendment (§G last bullet; first-release target for the data layer) | `docs/blueprint/amendments/2026-10-11-data-layer-postgresql.md`, `tests/fundamentals/test_amendment_records.py` | `uv run pytest tests/fundamentals/test_amendment_records.py -k data_layer`: the record cites the data spec, lists exactly the two changed items, records panel approval (reviewers, verdicts, date), and its doc links resolve |
| 5 | Frozen Stage 1 manifest | `tests/fundamentals/fixtures/data_foundation/stage1_manifest.yaml`, `tests/fundamentals/test_frozen_manifests.py` | `uv run pytest tests/fundamentals/test_frozen_manifests.py -k stage1`: the header records the hand verification against named source documents (path, sha256, locator) and the Sol approval of the **finished manifest** (reviewer, verdict, date). It freezes complete keys, both representations, every diagnostic pair (endpoints, outcome, reason, severity, diagnostic flag), source defaults and queue identities/multiplicity. It pre-registers: the Apar opex-vs-Screener outcome (`ANOMALY`/`NOISE`, no queue item); the Tijori `qt_c` displayed-precision re-measurement rule and per-company cases; the THERMAX `ANOMALY`/`MAGNITUDE` arithmetic. Every Stage 1 Success Criteria case is dispositioned (existing retained test, this manifest, a named D1b.6 fixture, or a recorded unit exception: E1, E2, E4, E8, OPM, family). Lexemes are re-read at their locators and derived values re-evaluated with `Fraction`. Its first commit precedes the first commit of `test_data_stage1_e2e.py` |
| 6 | Stage 1 end-to-end | `tests/fundamentals/test_data_stage1_e2e.py` | `uv run pytest tests/fundamentals/test_data_stage1_e2e.py` matches the manifest exactly: every applicable row for Apar and the nine companies (SONACOMS dropped, owner 2026-10-14); the Apar opex-vs-Screener outcome equals the pre-registered `ANOMALY`/`NOISE` with no queue item; THERMAX revenue is `ANOMALY`/`MAGNITUDE`, MEDIUM; NETWEB runs with no consolidated package (all consolidated rows `NOT_APPLICABLE`, no standalone leakage); the failure fixture, including complete-then-failed on the same surface, makes the run `INCOMPLETE`, exits `INCOMPLETE` and replays as `UNAVAILABLE`; the marked complete-then-`NOT_PUBLISHED` Tijori attempt leaves `NO_VALUE`/`NOT_PUBLISHED`, corroboration `FILING_ONLY`, run `COMPLETE`, exit not `INCOMPLETE`, replay equal; a failed Upstox attempt leaves the run `COMPLETE`; the diagnostic fixture meets the split proof of the owner amendment of 2026-10-14 (a trusted Q3 FY25 continuing-PAT cell, the explicit `PRECISION_UNSUPPORTED` rule test, retained Apar Upstox diagnostics on evidenced keys and an Upstox–Screener diagnostic on a shared key); retained marked cases for the invalid-only vendor (E7), restatement over Apar FY/9M (E16), issuer correction omitting a line (K2), the unrelated-discrepancy HIGH (C6), correction cutoffs and two-unsuperseded ambiguity (K1), and the D1 pre-/post-elimination keys; vendor CLI `INCOMPLETE` exit (E12/E13); a completed run with open HIGH items exits success |

**Spec refs.** Data spec §2 vendor mappings and qualification, §3 (source authority, basis), §5
(source roles, corroboration, trust, routing, queue, analyst interface), §8 component boundaries,
decision-register amendment, Success Criteria Stage 1, Testing Decisions.
**Exit (D1b):** `uv run pytest tests/fundamentals/test_data_stage1_e2e.py` passes against the
frozen manifest; within it, `uv run fundamentals compare report` shows Apar Q2 FY26 consolidated
with every source's state, both statuses and the queue items.
**Test focus.** The e2e over retained captures and the integration of vendor adapters → runs →
queue. Unit tests cover only the corroboration table and routing rules.
**Risk.** Deep: corroboration and trust decide what every later phase may admit or cite. Plan
note: name the queue-disposition and interpretation-approval commands explicitly in this phase's
plan (the data spec only says "record dispositions"); D3 gates them by role.
**Absorbs:** `eqos-al0` (net-profit mapping freeze; the data spec retargets it to
`profit_continuing_after_tax`). **Touches:** `eqos-s2g` (standalone basis: D1a/D1b cover only NETWEB
`NOT_APPLICABLE` behaviour; standalone coverage of the sweep set stays open).

## D2: Legacy store migration and cutover (dS2)

**Goal.** Import the legacy SQLite fact store into PostgreSQL losslessly, move fact-store
consumers onto it behind the existing interfaces, admit first-party facts by policy, prove
backup and restore, and rehearse rollback.

| # | Stage | Create/modify paths | Verify |
|---|---|---|---|
| 1 | SQLite baseline characterization | `tests/fundamentals/test_fact_store_baseline.py` | `uv run pytest tests/fundamentals/test_fact_store_baseline.py` records the current canonical selections at several cutoffs, green on SQLite before any port |
| 2 | Import preflight, freeze and lossless import | `src/fundamentals/pg/legacy_import.py`, `src/fundamentals/pg/approvals.py`, `migrations/0010_legacy_fact_store.sql`, `config/legacy_import_manifest.yaml` | `uv run pytest tests/fundamentals/test_legacy_import.py`: the import manifest and the unresolved-originals preflight each carry a recorded panel approval, and the importer refuses either without one; counts and per-row hashes match; every recomputed selection digest equals its stored digest; two stores with colliding ids import without merging; re-importing the same fingerprint changes nothing, and a different one is refused; source fingerprints are unchanged; every evidence binding resolves |
| 3 | PostgreSQL-backed fact store and role translation | `src/fundamentals/store/fact_store.py` (interface kept), `src/fundamentals/store/pg_fact_store.py`, `src/fundamentals/canon/role_translation.py` | `uv run pytest tests/fundamentals/test_fact_store_baseline.py tests/fundamentals/test_pipeline_e2e.py`, parametrized over both store backends: the consumer tests pass on PostgreSQL, and cutoff queries equal the SQLite baseline |
| 4 | Admission policy | `src/fundamentals/evidence/admission.py`, `migrations/0011_fact_admissions.sql`, `src/fundamentals/output/pnl_lines.py` | `uv run pytest tests/fundamentals/test_admission.py tests/fundamentals/test_pipeline_e2e.py tests/fundamentals/test_report_builder.py`: a vendor observation is never admitted; only `AGREE` (or single-representation `NOT_APPLICABLE`) first-party cells are admitted, and `AGREE_UNQUALIFIED`, invalid, missing and one-sided cells are refused; the amended D1b diagnostic-fixture cell (Apar Q2 FY26 `total_income`, open MEDIUM diagnostic Upstox item) is admitted and the same cell with an open non-diagnostic HIGH is refused; the admission record stores run id, result id, interpretation, occurrence and overlay position; admission is atomic and idempotent and never selects; the Apar Q2 FY26 consumer report shows filed tax 88.83, ETR 26.08%, headline PBT incl. associates 340.53, PAT 251.70, with no PBT − PAT on either report path |
| 5 | Matched backup and restore | `src/fundamentals/pg/backup.py`, `src/fundamentals/api/db_cli.py` | `uv run pytest tests/fundamentals/test_backup_restore.py`: the set is restored into a fresh test database and an empty snapshot directory; every referenced capture, incl. every bound imported-fact original, hash-matches; one stored run replays identically; the manifest comes from the same exported snapshot as the dump |
| 6 | Cutover and frozen-window rollback | `src/fundamentals/pg/cutover.py` | `uv run pytest tests/fundamentals/test_cutover_rollback.py`: cutover is refused without Sol's recorded approval of the reconciliation report bound to the actual database (and, off `eqos_test_*`, the owner's authorization record), and the cutover marker records that approval and the last imported ids with writers frozen; a write during the freeze is refused, persists nothing, and succeeds when retried after the decision (not lost); rollback inside the window restores SQLite authority (routing opens the unchanged legacy file; cutoff queries equal the baseline); a rollback whose checks fail switches nothing across all target stores; after writers reopen, rollback is refused |
| 7 | Frozen Stage 2 manifest | `tests/fundamentals/fixtures/data_foundation/stage2_manifest.yaml`, `tests/fundamentals/test_frozen_manifests.py` | `uv run pytest tests/fundamentals/test_frozen_manifests.py -k stage2`: header records hand verification and panel approval; first commit precedes `test_data_stage2_e2e.py`'s |
| 8 | Stage 2 end-to-end | `tests/fundamentals/test_data_stage2_e2e.py`, `scripts/stage2_recreation_check.sh` | `uv run pytest tests/fundamentals/test_data_stage2_e2e.py` runs import → reconciliation → cutover → frozen-window rollback → reconciliation → re-cutover → reopen → admission and consumers → backup/restore → replay, and matches the manifest. Container recreation, fresh-instance restore and loopback: `scripts/stage2_recreation_check.sh` exits 0 — on its own uniquely owned compose projects (never the live `equity-os` project) it proves an identical state inventory across `down`/`up`, reruns the e2e green, restores the matched set onto a fresh cluster with one run replayed, and checks the running service is published only on 127.0.0.1 at the configured port |

**Spec refs.** Data spec §4 (boundary with the fact store), §6 (backup and restore D2; legacy
SQLite import D5 steps 1–7), Success Criteria Stage 2; ledger spec §6 items 5, 6 and 9 (read
ahead: D9 amends this backup and restore).
**Exit (D2):** the implementation and the full rehearsal are accepted on test databases: the
Stage 2 e2e is green against the frozen manifest, `scripts/stage2_recreation_check.sh` exits 0,
and the phase-end Sol review approves. **Production cutover** of `equity_os` is a separate,
owner-gated bead, `eqos-3zl` (owner go-ahead plus Sol approval of the production reconciliation
report); it must complete before the pilot (PILOT-3).
**Test focus.** Characterization first (stage 1), then integration over the real legacy files
and the full-path e2e. Unit targets: the approval/owner gate rule and the digest/chain rule.
**Risk.** Deep: a migration of the fact system of record. SQLite rollback exists only inside the
frozen cutover window; once PostgreSQL writers reopen, PostgreSQL is authoritative and recovery is
verified matched backups plus forward repair (spec §6 step 7, amended 2026-10-14).
**Absorbs:** part of `eqos-unv`. The import preserves legacy producer history byte for byte and
labels it unproved; binding new revisions to producer identity stays open unless the D2 plan
takes it in.

## D3: Report ledger (lS1)

**Goal.** Move reports, approvals, the Q0 thesis and the management ledger into append-only
PostgreSQL rows. Every numeric claim is checked against the stored figure it cites. Decisions come
from the approval panel or the owner role, and a deterministic narrative export reproduces the
content hash.

| # | Stage | Create/modify paths | Verify |
|---|---|---|---|
| 1 | Ledger schema, seal, decision chain and roles | `migrations/0012_report_ledger.sql`, `src/fundamentals/ledger/` | `uv run pytest tests/fundamentals/test_ledger_integrity.py`: after `SUBMIT`, content inserts and a wrong sealed digest are refused; a later validation leaves the digest unchanged; a stale-head decision is refused; recorded-at is set by trigger; the runtime role can insert no decision except `SUBMIT`, no unproposed or amount-bearing disposition, and no update or delete; the chain digest (unit) |
| 2 | Claim check, numeral and prose scans, display | `src/fundamentals/ledger/claim_check.py`, `src/fundamentals/ledger/numeral_scan.py`, `src/fundamentals/ledger/display.py` | `uv run pytest tests/fundamentals/test_ledger_claim_check.py tests/fundamentals/test_ledger_display.py`: the claim-check table row by row in both modes; a draft self-citing `POLICY` is refused (only an import may self-cite); byte-identical "6,591.06", "6591.06", "+29.1%", "9.5–10%" and the "guiding about 9.5%, 10%" quote; the `QUOTE_MEANING_MISMATCH` variants; the `UNREGISTERED_NUMBER`, `UNLABELLED_PROSE` and `UNCITED_PROSE` cases; ids, hashes, `× 100` and quotes pass the scan |
| 3 | Version lifecycle and decision commands | `src/fundamentals/ledger/lifecycle.py`, `src/fundamentals/api/ledger_cli.py` (`decide`) | `uv run pytest tests/fundamentals/test_ledger_lifecycle.py`: v1 approved / v2 rejected / v3 approved supersedes v1; v1 approved / v2 `HISTORICAL` / v3 approved supersedes v1 and v2; a successor submitted while its predecessor is `IN_REVIEW`, a predecessor from another report, and a second successor are each refused; approval binds only an `AS_KNOWN` validation |
| 4 | Approval panel command and role gating of D1b queue commands | `src/fundamentals/ledger/panel.py`, `src/fundamentals/api/panel_cli.py`, `src/fundamentals/compare/queue.py` | `uv run pytest tests/fundamentals/test_ledger_panel.py` with a fake reviewer adapter (single reviewer, amended 2026-10-15): a reviewer `APPROVE` → `APPROVED`, its text, provider and model recorded as data. Refused: a panel verdict without its review, a review of another digest, a panel-supplied amount, a panel decision on a subject whose chain holds an owner decision, and a failing claim check (no model call). The runtime role is refused on the disposition and interpretation-approval commands and may only propose. A cited cell made untrusted by a later overlay change appends a new validation, and the approval still binds its original validation. Panel verdict rules (unit). Kinds are keyed by subject, and accept/reject applies to amount-bearing records (plan note) |
| 5 | Imports: earnings updates FY26_Q2–FY27_Q1, Q0 thesis, management ledger | `src/fundamentals/ledger/importer.py` | `uv run pytest tests/fundamentals/test_ledger_import.py`: each version carries an `IMPORT_SEAL`; a fixture with one altered numeral fails the lossless check; `approval_record` sections become QA records, never decisions; Q0 is `APPROVED` or `HISTORICAL` per the evidence rule; every ledger history revision is a claim |
| 6 | Deterministic narrative export | `src/fundamentals/ledger/export.py` | `uv run pytest tests/fundamentals/test_ledger_export.py`: export bytes hash to the content hash and are identical on re-export; a status change leaves narrative bytes unchanged |
| 7 | Register amendments 3, 5, 7 and 8; CONTEXT.md glossary update | `docs/blueprint/amendments/2026-10-12-report-ledger.md`, `CONTEXT.md`, `.claude/project/invariants.md` | `uv run pytest tests/fundamentals/test_amendment_records.py -k "ledger_stage1 or context_glossary"`: the record lists exactly amendments 3, 5, 7 and 8, each with panel approval recorded; CONTEXT.md "Memory promotion" and its role names match amendment 8 and name no model. The narrative authority cutover (amendment 3) is recorded only after stage 9 is green (edge D3.7 → D3.9) |
| 8 | Frozen ledger Stage 1 manifest | `tests/fundamentals/fixtures/data_foundation/ledger_stage1_manifest.yaml`, `tests/fundamentals/test_frozen_manifests.py` | `uv run pytest tests/fundamentals/test_frozen_manifests.py -k ledger_stage1`: header records hand verification and panel approval; first commit precedes `test_ledger_stage1_e2e.py`'s |
| 9 | Ledger Stage 1 end-to-end | `tests/fundamentals/test_ledger_stage1_e2e.py` | `uv run pytest tests/fundamentals/test_ledger_stage1_e2e.py` matches the manifest: FY27_Q1 revenue 6,591.06 is `POST_CUTOFF` under `RETROSPECTIVE`, and a corrective version with an honest cutoff gives `MATCH`; Q0 F1 11.55 self-cited `POLICY` gives `MATCH`; FY26_Q3 cables growth displays "**20%**" |

**Spec refs.** Ledger spec O1, O2, O10, P1 and P2; amendments 3, 5, 7 and 8; §1 (entities, rules,
citations, times, claim check, lifecycle, import); §3 (Markdown export, narrative part); Success
Criteria Stage 1 (its "approval changes no memory item" is verified in D4.2, once memory exists);
data spec §5 (trust, queue) and §1 (calculation traces) as cited targets.
**Exit (D3):** the ledger Stage 1 e2e is green, and `uv run pytest tests/fundamentals/test_ledger_export.py`
shows `uv run fundamentals ledger export` reproducing every imported Apar version's content hash.
The files remain the record until amendment 3 is approved.
**Test focus.** The import e2e over the real Apar artifacts; integration for triggers, roles and
the panel with fake adapters. Unit tests cover only the claim check, scans, display, quote
meaning, panel verdict rules and the chain digest.
**Risk.** Deep: this sets the authority for every reported number (invariants 6–8 and 11) and
the trigger-enforced panel and role rules.
**Touches:** `eqos-4j2.8` (assisted updates Q1–Q3). It stays outside this workstream and runs after
D3, as D3 ledger versions; D3 builds the numeric claim schema it will use (non-numeric claims stay
with B-06).

## D4: Long-term memory (lS2)

**Goal.** Store promoted, supported, time-bounded statements per stock behind the D-01
`MemoryStore` interface. The statements are full-text searchable and retrievable as of a cutoff,
and are promoted only by a separate panel or owner decision.

| # | Stage | Create/modify paths | Verify |
|---|---|---|---|
| 1 | `MemoryStore` interface and PostgreSQL schema | `src/fundamentals/memory/store.py` (Protocol), `src/fundamentals/memory/pg_store.py`, `migrations/0016_memory.sql` | `uv run pytest tests/fundamentals/test_memory_store.py`: an item without support is refused; a support added after a decision is refused; superseding across stock or kind is refused; no comparator or claim-check module imports `fundamentals.memory` (import-graph assertion) |
| 2 | Support predicate, promotion and supersession | `migrations/0017_memory_support.sql`, `src/fundamentals/memory/status.py` | `uv run pytest tests/fundamentals/test_memory_promotion.py tests/fundamentals/test_memory_status.py`: staging from `HISTORICAL` is refused; a non-`MATCH` claim support or a version without an all-`MATCH` `AS_KNOWN` validation is refused; a support's version withdrawn, or a non-`MATCH` validation appended, between staging and `PROMOTE` (incl. a version directly supporting `COMPANY_UNDERSTANDING`) committed before `PROMOTE` makes `PROMOTE` refuse, and one waiting on `PROMOTE` commits later in store time and flags the item (lock order proven by observing the blocked backend), for supersession, withdrawal, non-`MATCH` and version-level validations and disposition supersession; a SERIALIZABLE `PROMOTE` is refused; a `PROMOTE` followed in its own transaction by a withdrawal, a failing validation, a supersession or any other ledger or queue write is refused; a promoted successor retires its predecessor atomically and a second successor is refused; a `SOURCE_QUIRK` with a capture support is accepted; approving a ledger version changes no memory item; status derivation and the chain digest (unit) |
| 3 | Search, cutoff retrieval and revalidation flags | `src/fundamentals/memory/retrieval.py` | `uv run pytest tests/fundamentals/test_memory_retrieval.py`: "cables margin" finds the item; the stock, kind and status filters work; a cutoff before promotion or recorded-at excludes it; withdrawing or superseding a supporting version (incl. a directly supporting version), or a later validation of a support with a non-`MATCH` claim or a version-level state, flags `NEEDS_REVALIDATION` and refuses `PROMOTE`; a cutoff before that event shows no flag |
| 4 | Frozen ledger Stage 2 manifest | `tests/fundamentals/fixtures/data_foundation/ledger_stage2_manifest.yaml`, `tests/fundamentals/test_frozen_manifests.py` | `uv run pytest tests/fundamentals/test_frozen_manifests.py -k ledger_stage2`: header records hand verification and panel approval; first commit precedes `test_ledger_stage2_e2e.py`'s |
| 5 | Ledger Stage 2 end-to-end | `tests/fundamentals/test_ledger_stage2_e2e.py` | `uv run pytest tests/fundamentals/test_ledger_stage2_e2e.py`: the Apar cables EBITDA-margin `MANAGEMENT_TRACK_RECORD` (9.5–10% in FY26_Q3, 10–11% in FY27_Q1), supported by both quote claims from corrective approved versions, is retrieved only after a panel `PROMOTE`, matching the manifest |

**Plan:** `plans/D4.md` (Sol APPROVE 2026-10-15); amendments A1, A2, C2, C3, R, M9 recorded in the ledger spec.

**Spec refs.** Ledger spec O3, O4, §2 (entities, kinds, support predicate, lifecycle,
revalidation, search, `MemoryStore`), amendment 7 (retirement, not deletion), Success Criteria
Stage 2; Success Criteria Stage 1 "approval changes no memory item".
**Exit (D4):** the Stage 2 e2e is green; within it, `MemoryStore.retrieve("cables margin",
stock=Apar, cutoff=…)` returns the promoted item with supports and provenance.
**Test focus.** Integration on the support predicate, its race against concurrent withdrawal,
and cutoff leakage. Unit tests only for status derivation and the chain digest
(`test_memory_status.py`).
**Risk.** Deep: this enforces invariant 11 (separate promotion), and a promotion race or cutoff
leak would corrupt long-term knowledge.

## D5: Generated views (lS3)

**Goal.** Give people read-only Markdown views of reports, status notes and promoted memory, with
an optional Obsidian vault export. Nothing flows back from the views.

| # | Stage | Create/modify paths | Verify |
|---|---|---|---|
| 1 | Status notes and memory export | `src/fundamentals/ledger/export.py`, `src/fundamentals/memory/export.py` | `uv run pytest tests/fundamentals/test_views_export.py`: status notes show the derived status, decisions, latest validation, untrusted claims and revalidation flags; promoted memory exports per stock; narrative bytes are unchanged by status |
| 2 | Read-only role over views | `migrations/0021_views_readonly.sql` | `uv run pytest tests/fundamentals/test_views_readonly_role.py`: the read-only role can SELECT the views, and every INSERT, UPDATE and DELETE is refused |
| 3 | Obsidian vault export (optional) | `src/fundamentals/views/vault.py` | `uv run pytest tests/fundamentals/test_views_vault.py`: the Apar vault has one folder and a note per version; wikilinks resolve; a hand-edited note moves to the conflicts folder on re-export. If the D5 plan drops the vault, this stage closes as "not built" with that reason, and the manifest records no vault rows |
| 4 | Frozen ledger Stage 3 manifest | `tests/fundamentals/fixtures/data_foundation/ledger_stage3_manifest.yaml`, `tests/fundamentals/test_frozen_manifests.py` | `uv run pytest tests/fundamentals/test_frozen_manifests.py -k ledger_stage3`: header records hand verification and panel approval, and whether the vault is in scope; first commit precedes `test_ledger_stage3_e2e.py`'s |
| 5 | Ledger Stage 3 end-to-end | `tests/fundamentals/test_ledger_stage3_e2e.py` | `uv run pytest tests/fundamentals/test_ledger_stage3_e2e.py`: `fundamentals ledger export --status-notes --memory` writes Apar's views matching the manifest; the read-only role reads them and writes nothing; the vault rows match if built |

**Spec refs.** Ledger spec O5, P2, §3, Success Criteria Stage 3.
**Exit (D5):** the ledger Stage 3 e2e is green.
**Test focus.** Integration and the e2e only. There is no dynamic financial logic here.
**Risk.** Standard: one-way read views over records that D3 and D4 already sealed.

## D6: Identifier-only onboarding (dS4)

**Goal.** Onboard a company from its identifier alone, with per-namespace verification evidence.
Onboarding fails closed and runs a comparison with no code or configuration change.

| # | Stage | Create/modify paths | Verify |
|---|---|---|---|
| 1 | Held-out company pre-registration (before any other D6 stage starts) | `tests/fundamentals/fixtures/data_foundation/stage4_holdout.yaml`, `tests/fundamentals/test_frozen_manifests.py`, `tests/fundamentals/stage4_support.py` | `uv run pytest tests/fundamentals/test_frozen_manifests.py -k stage4_holdout`: the record holds the identifier, pre-registered outcome and run status, and panel approval; its first commit precedes the first commit of `src/fundamentals/entity/discovery.py`; the identifier appears in no file under `src/`, `config/` or `tests/` other than the holdout record and the Stage 4 manifest |
| 2 | Temporal identity relationships and identity events | `migrations/0022_identity_events.sql`, `src/fundamentals/entity/identity_layers.py` | `uv run pytest tests/fundamentals/test_identity_layers.py`: identifier relationships are temporal with provenance; ISIN and symbol changes, symbol reuse, mergers, demergers and delistings are explicit events, never inferred; entity, security and listing ids from D1a.1 stay stable; the existing entity map reads as the latest slice |
| 3 | Discovery, per-namespace verification and onboarding outcomes | `src/fundamentals/entity/discovery.py`, `src/fundamentals/entity/verification.py` | `uv run pytest tests/fundamentals/test_onboarding_verification.py`: discovery captures are kept as identity evidence and are never comparison-eligible until verified; an ambiguous-identifier fixture gives `IDENTITY_CONFLICT` with no eligible captures or interpretations and a HIGH operator item; a financial-sector issuer gives `UNSUPPORTED`; an unauthorised surface gives `NOT_AUTHORISED`; the verification predicates (unit) |
| 4 | Settings derived from evidence | `src/fundamentals/entity/derived_settings.py` | `uv run pytest tests/fundamentals/test_derived_settings.py`: printed units, fiscal calendar, basis status and document locations come from evidence and are versioned; a settings change does not reinterpret stored observations |
| 5 | Implementation freeze and frozen Stage 4 manifest | `tests/fundamentals/fixtures/data_foundation/stage4_manifest.yaml`, `tests/fundamentals/fixtures/data_foundation/stage4_freeze.yaml`, `tests/fundamentals/test_frozen_manifests.py`, `tests/fundamentals/stage4_support.py` | `uv run pytest tests/fundamentals/test_frozen_manifests.py -k stage4`: header records hand verification, panel approval and the implementation-freeze commit; the manifest's first commit precedes `test_data_stage4_e2e.py`'s |
| 6 | Stage 4 end-to-end on the held-out company | `tests/fundamentals/test_data_stage4_e2e.py` | `uv run pytest tests/fundamentals/test_data_stage4_e2e.py`: given only its identifier, the held-out company reaches `ONBOARDED` (run `COMPLETE`) or `PARTIAL` (run `INCOMPLETE`, listing exactly the excluded namespaces) as pre-registered, and its run matches the manifest; the test asserts `git diff --quiet <freeze commit> -- src config` |

**Spec refs.** Data spec §3 (identity layers, settings, basis, source authority) and §8, Success
Criteria Stage 4; ledger spec §6 item 8 (discovery captures fall under `IDENTITY` retention once
D9 lands).
**Exit (D6):** the Stage 4 e2e is green with no code or configuration change between the recorded
implementation freeze and the run; the held-out company was recorded before the phase started and
appears in no development file.
**Test focus.** E2e on the held-out company; integration for the conflict and unsupported paths.
There are no unit tests beyond the verification predicates.
**Risk.** Deep: wrong identity silently attaches figures to the wrong company, and the held-out
discipline is easy to break.
**Absorbs:** `eqos-s02` (vendor ids enter as verified namespaces). **Touches:** `eqos-hvh` (banks
become `UNSUPPORTED` at onboarding; the bank name map stays deferred).

## D7: Coverage model (lS4)

**Goal.** Add the three nested coverage sets. The universe registry holds identity only. An
owner-exported screen drives a capture batch that onboards and compares exactly the chosen
members. Watchlist changes are owner-only decisions that gate report drafting.

| # | Stage | Create/modify paths | Verify |
|---|---|---|---|
| 1 | Universe registry and idempotent refresh (Upstox list, identity-only catalog role) | `migrations/0008_coverage.sql`, `src/fundamentals/coverage/registry.py`, source catalog entry | `uv run pytest tests/fundamentals/test_coverage_registry.py`: a retained instrument list yields the expected rows; a reload changes nothing; an ISIN under a new symbol records a candidate event and leaves verified identity unchanged |
| 2 | Screens, screen runs and capture batches | `src/fundamentals/coverage/screens.py`, `src/fundamentals/coverage/batch.py`, `src/fundamentals/api/coverage_cli.py` | `uv run pytest tests/fundamentals/test_coverage_batch.py`: a five-member CSV fixture resolves; a batch over three members onboards and compares exactly those three, and the other two have nothing; no `?q=` request is made; nothing is scheduled |
| 3 | Watchlist decisions and the drafting gate | `src/fundamentals/coverage/watchlist.py`, `src/fundamentals/ledger/lifecycle.py` | `uv run pytest tests/fundamentals/test_coverage_watchlist.py`: `ADD`/`REMOVE` are owner-only and carry a verbatim reason; adding an unverified or uncaptured stock is refused; drafting for a stock off the watchlist is refused; a new member's first report must be `BOOTSTRAP_THESIS` |
| 4 | Register amendment 1 (§G clarification) | `docs/blueprint/amendments/2026-10-12-report-ledger.md` | `uv run pytest tests/fundamentals/test_amendment_records.py -k ledger_stage4`: the record lists amendment 1 with panel approval recorded |
| 5 | Frozen ledger Stage 4 manifest | `tests/fundamentals/fixtures/data_foundation/ledger_stage4_manifest.yaml`, `tests/fundamentals/test_frozen_manifests.py` | `uv run pytest tests/fundamentals/test_frozen_manifests.py -k ledger_stage4`: header records hand verification and panel approval; first commit precedes `test_ledger_stage4_e2e.py`'s |
| 6 | Ledger Stage 4 end-to-end | `tests/fundamentals/test_ledger_stage4_e2e.py` | `uv run pytest tests/fundamentals/test_ledger_stage4_e2e.py` matches `ledger_stage4_manifest.yaml`: registry load and reload, screen run, three-member batch via `fundamentals coverage batch`, and the watchlist and drafting refusals |

**Spec refs.** Ledger spec O6–O8, amendment 1, §4, Success Criteria Stage 4; data spec §8 (each
batch member onboards through D6).
**Exit (D7):** the ledger Stage 4 e2e is green; within it, `uv run fundamentals coverage batch`
over a screen-run subset captures and compares only that subset.
**Test focus.** Integration and e2e over the CSV and instrument-list fixtures. No unit tests are
needed.
**Risk.** Standard: it reuses D6 onboarding and the D3 decision chain, and adds no new financial
logic.
**Touches:** `eqos-kx4.5` (Screener screens and watchlist surfaces). The screen input here is an
owner-exported CSV only, so that bead's capability-registry scope is not absorbed.

## D8: Shareholding filing source (dS3)

**Goal.** Add the exchange shareholding filing as the first-party shareholding source, with
explicit instant, category hierarchy, denominator, share class and completeness. Compare it with
Screener and Tijori (Upstox diagnostic).

| # | Stage | Create/modify paths | Verify |
|---|---|---|---|
| 1 | Catalog registration with role and retention authority | source catalog entry, `src/fundamentals/contracts/source_catalog.py` | `uv run pytest tests/fundamentals/test_source_catalog.py`: the filing is registered before any capture; a capture attempted before registration gives `NOT_AUTHORISED` |
| 2 | Acquisition, retention and occurrences | `src/fundamentals/ingest/shareholding_filing.py`, `config/mappings/shareholding_filing/` | `uv run pytest tests/fundamentals/test_shareholding_filing.py`: Apar and ≥2 watchlist companies are captured under recorded authority with explicit instant, category, denominator, share class and completeness; holder drill-downs are `THRESHOLDED` with the threshold recorded; an absent holder is never zero |
| 3 | Category hierarchy, denominators and vendor mappings (Tijori from real captures only) | `config/dictionary/v1/` (shareholding rows, minor version), `config/mappings/screener/`, `config/mappings/tijori/` | `uv run pytest tests/fundamentals/test_shareholding_compare.py`: different denominators are never paired; vendor "Public" maps only to its aggregate; a DII built by dimensional aggregation is compared at the DII aggregate only |
| 4 | Frozen Stage 3 manifest | `tests/fundamentals/fixtures/data_foundation/stage3_manifest.yaml`, `tests/fundamentals/test_frozen_manifests.py` | `uv run pytest tests/fundamentals/test_frozen_manifests.py -k stage3`: header records hand verification, panel approval and the extraction status (`NOT_APPLICABLE` or paired) taken from the retained representations; first commit precedes `test_data_stage3_e2e.py`'s |
| 5 | Stage 3 end-to-end | `tests/fundamentals/test_data_stage3_e2e.py` | `uv run pytest tests/fundamentals/test_data_stage3_e2e.py` matches the manifest, including the extraction status and Apar's promoter, public and institution aggregates against each vendor |

**Spec refs.** Data spec §7, §3 (source authority), §5 (shareholding roles), Success Criteria
Stage 3; ledger spec §6 item 7.
**Exit (D8):** the Stage 3 e2e is green; within it, `uv run fundamentals compare report` shows
Apar's promoter, public and institution aggregates against each vendor.
**Test focus.** E2e over real retained filings and vendor captures; integration for denominator
and aggregate pairing. Unit tests only if the dimensional aggregation gains new operators.
**Risk.** Deep: a new first-party source with an authority prerequisite, plus denominator and
category semantics where a wrong pairing yields plausible but false corroboration.

## D9: Retention and replay (lS5)

**Goal.** Make storage scale with coverage, not with the market. The phase adds retention classes,
transitive holds, an eligibility function, a retention lock with a backup amended for expired
captures, a crash-safe, lock-guarded purge with tombstones, re-fetch with a hash check, and
restore that purges first.

| # | Stage | Create/modify paths | Verify |
|---|---|---|---|
| 1 | Register amendments 2 and 6 and the data-spec clause amendments (ledger §6); A-05 derived-amounts panel decision | `docs/blueprint/amendments/2026-10-12-report-ledger.md`, `docs/blueprint/amendments/2026-10-12-a05-derived-amounts.md` | `uv run pytest tests/fundamentals/test_amendment_records.py -k "ledger_stage5 or a05"`: the record lists amendments 2 and 6 and data-spec §6 items 1–12, each with panel approval; the A-05 record states the panel's decision on keeping derived amounts (ledger §5), cites `docs/research/vendor-terms-screener-tijori-2026-10.md`, and records reviewers, verdicts and date |
| 2 | Retention classes, one-off classification and catalog authority | `migrations/0009_retention.sql`, `src/fundamentals/retention/classes.py` | `uv run pytest tests/fundamentals/test_retention_classes.py`: existing captures classify once by source and watchlist status; intake, class upgrade or hold creation beyond catalog retention is refused; a `SOURCE_QUOTE` claim on a vendor capture is refused; a watchlist add upgrades only non-vendor originals and records `RETENTION_LIMITED` for the rest |
| 3 | Holds and eligibility | `src/fundamentals/retention/holds.py`, `src/fundamentals/retention/eligibility.py` | `uv run pytest tests/fundamentals/test_retention_eligibility.py tests/fundamentals/test_retention_holds.py`: one fixture per class and per hold root matches its expected outcome; a non-covered XBRL with no verification time is `KEEP`; a blob shared by a held capture is kept and is removed only when every user is eligible; an open queue item holds vendor material past four quarters until closed, and other roots do not extend its window; after a licence end everything is `ELIGIBLE` |
| 4 | Retention lock, SnapshotStore extension and amended backup set | `src/fundamentals/retention/lock.py`, `src/fundamentals/store/snapshot_store.py`, `src/fundamentals/pg/backup.py` | `uv run pytest tests/fundamentals/test_retention_lock_backup.py`: intake and hold-creating writes take the lock shared at transaction level; backup holds it shared at session level on a dedicated connection through archive verification; a backup archives every retained blob and lists each expired capture with address, hash and purge record; delete-blob-and-links and relink take the SnapshotStore writer flock and never rewrite `record.json`; a missing body on a non-`EXPIRED` capture reads as corruption |
| 5 | Purge with recovery | `src/fundamentals/retention/purge.py`, `src/fundamentals/api/retention_cli.py` | `uv run pytest tests/fundamentals/test_retention_purge.py` with a fake fetcher: the dry-run lists exactly the eligible blobs; before `EXCHANGE_REFETCHABLE` deletions a per-source probe must hash-match, and a probe failure halts that source's deletions and queues a HIGH item; crashes after the intent commit, after file deletion and after the `EXPIRED` commit converge on rerun; after a crash post-deletion, backup and hold-creating writes refuse until purge recovery, which takes its step-5 backup inside the purge lock session; a purge waits for a running backup's archive verification; a hold-creating write waits, then a `SOURCE_QUOTE` claim on the expired capture is refused and a `FIGURE` claim on its facts proceeds; same-blob intake during a purge ends with the body present; vendor payloads become tombstones and outcomes remain, per the A-05 record; non-vendor occurrences, interpretations and facts are preserved; step 5 leaves no older backup set holding expired bytes |
| 6 | Re-fetch, `REFETCH_MISMATCH` and `ORIGINAL_EXPIRED` replay | `src/fundamentals/retention/refetch.py`, `src/fundamentals/compare/run.py` | `uv run pytest tests/fundamentals/test_retention_refetch.py` with a fake fetcher: re-fetch takes the retention lock shared at transaction level; the same bytes give `RESTORED` with the original first-seen time, and re-extraction reproduces the occurrences; different bytes give `REFETCH_MISMATCH` (HIGH) and leave the capture expired; re-extraction and replay over an expired vendor capture give `ORIGINAL_EXPIRED` |
| 7 | Restore with purge-first, and licence ends | `src/fundamentals/pg/backup.py`, `src/fundamentals/retention/licence.py` | `uv run pytest tests/fundamentals/test_retention_restore.py`: recording a licence end appends it to `licence-ends.json` beside the backups, then purges all that vendor's material, holds notwithstanding; restoring a pre-purge set, or one predating a licence end, purges before any other role connects; retained captures hash-match and expired ones have purge records; a missing or unreadable `licence-ends.json` refuses startup |
| 8 | Frozen ledger Stage 5 manifest | `tests/fundamentals/fixtures/data_foundation/ledger_stage5_manifest.yaml`, `tests/fundamentals/test_frozen_manifests.py` | `uv run pytest tests/fundamentals/test_frozen_manifests.py -k ledger_stage5`: header records hand verification and panel approval; first commit precedes `test_ledger_stage5_e2e.py`'s |
| 9 | Ledger Stage 5 end-to-end | `tests/fundamentals/test_ledger_stage5_e2e.py` | `uv run pytest tests/fundamentals/test_ledger_stage5_e2e.py` matches the manifest: `fundamentals retention purge --dry-run`, a real purge, re-fetch, replay and restore over the eligibility fixtures |

**Spec refs.** Ledger spec O9, P3–P5, §5, §6, amendments 2 and 6, Open Questions (A-05), Success
Criteria Stage 5; data spec §6 (backup D2, as amended).
**Exit (D9):** the ledger Stage 5 e2e is green; within it, `uv run fundamentals retention purge
--dry-run` lists exactly the eligible blobs, and a real purge followed by restore matches the
manifest.
**Test focus.** Integration on crash points, lock interleavings and backup/restore; e2e against
the manifest. Unit tests only for eligibility and holds. Only the fetcher, purge crash points and
reviewer calls are mocked.
**Risk.** Deep: this phase physically deletes evidence under concurrency, so a mistake loses
history that cannot be recreated (invariant 13).

---

## Dependencies

### Phase → phase

| Edge | Reason |
|---|---|
| D1b → D1a | Vendors, corroboration and the queue extend the tracer's schema, tables and runs |
| D2 → D1b | The import binds legacy facts to measurement keys and retained captures; admission reads run results and the queue overlay; the frozen Stage 1 manifest gates dependent phases |
| D3 → D1b | `FIGURE`/`CALCULATION`/`COMPARISON` citations resolve to D1 interpretations, traces and results; the panel gates D1b's disposition commands |
| D3 → D2 | `FIGURE` cites fact ids, which D2 serves from PostgreSQL (`PgFactStore`, D2.6; ledger spec Stage 1 depends on data Stages 1–2). Production legacy facts reach PostgreSQL through the owner-gated `eqos-3zl`, which the pilot (PILOT-3) depends on, not D3 |
| D4 → D3 | Memory supports are approved versions, claims and decisions from the ledger |
| D5 → D3, D4 | Views render ledger versions and promoted memory |
| D6 → D1b, D2 | Onboarding runs a comparison and writes identity next to the migrated fact store (dS4 depends on 1, 2) |
| D7 → D6 | Every batch member onboards through D6 |
| D7 → D3 | Not in the ledger spec's dependency column, confirmed by both structure reviewers: watchlist `ADD`/`REMOVE` use D3's per-subject decision chain and owner role, and the drafting gate refuses ledger drafts |
| D8 → D1b | The shareholding rows, mappings and comparator extend D1's dictionary, evidence model, tables and source authority |
| D9 → D2, D3, D4, D6, D7 | It amends D2's backup; hold roots are legacy bindings, report versions, claims, memory supports, identity events, onboarding outcomes and covered (watchlisted) stocks |

**Not edges.** D8 is independent of D2–D7 and may run any time after D1b. It sits late only
because it is off the critical path (D1a → D1b → D2 → D3 → D4 → D9 and D1a → D1b → D2 → D6 → D7 →
D9). If D8 lands after D9, D8's intake must assign retention classes itself (ledger §6 item 7).
D5 blocks nothing.

### Stage → stage (complete; seed exactly these)

One row per stage. `bd dep add <stage> <prereq>` once for every prerequisite listed. A
prerequisite is listed when the stage directly uses its output, even if another listed
prerequisite already implies it. "—" means no prerequisite. Stages within a phase with no edge
between them are independent and may run in any order or in parallel.

| Stage | Needs | Reason |
|---|---|---|
| D1a.1 | — | First stage of the store |
| D1a.2 | — | Dictionary and applicability are configuration with a loader |
| D1a.3 | D1a.2 | Formulas and temporal roles come from dictionary ids and kinds |
| D1a.4 | D1a.1, D1a.2, D1a.3 | Adapters write occurrences and interpretations to the schema, keyed by dictionary ids; derived rows evaluate formulas |
| D1a.5 | D1a.2, D1a.3 | Tables read row kinds and applicability; interval agreement and calculation states come from the engine |
| D1a.6 | D1a.1, D1a.4, D1a.5 | A run pins adapter inputs and table outcomes into run and result rows |
| D1a.7 | D1a.6 | The tracer drives a run and the report CLI |
| D1b.1 | D1a.1, D1a.2, D1a.4 | Vendor adapters reuse the occurrence and interpretation model, selection and dictionary ids |
| D1b.2 | D1a.5, D1b.1 | Corroboration consumes pair outcomes; the diagnostic cases need vendor captures |
| D1b.3 | D1a.6, D1b.2 | Queue items come from routed outcomes of a run; exit statuses extend the run |
| D1b.4 | — | Documentation record; creates the shared amendment test |
| D1b.5 | — | Hand-verified from source documents; creates the shared manifest test |
| D1b.6 | D1b.3, D1b.5 | The e2e needs the full run and queue path and the frozen manifest |
| D2.1 | — | Characterizes SQLite as it is |
| D2.2 | D2.1, D1a.1, D1a.2 | Characterize before importing; bindings reference D1a captures; translation targets measurement keys |
| D2.3 | D2.1, D2.2, D1a.2 | Consumers move only after the baseline and a reconciled import; role translation uses dictionary ids |
| D2.4 | D2.3, D1a.6, D1b.3 | Admission writes through the PostgreSQL fact store using run results at a queue-overlay position |
| D2.5 | D1a.1, D1a.6, D2.2 | Backs up the schema, captures and bound imported-fact originals; restore replays one stored run |
| D2.6 | D2.2, D2.3, D2.5 | Cutover needs the approved reconciliation, ported consumers and a verified backup |
| D2.7 | D1b.5 | Extends the shared manifest test |
| D2.8 | D2.4, D2.6, D2.7 | The e2e runs the full import-to-rollback path against the frozen manifest |
| D3.1 | D2.6 | Ledger rows cite PostgreSQL fact ids that exist only after cutover |
| D3.2 | D3.1, D1b.2, D1b.3 | The claim check resolves citations and reads trust at a queue-overlay position |
| D3.3 | D3.1, D3.2 | Lifecycle decisions use the chain; approval binds a claim-check validation |
| D3.4 | D3.1, D3.2, D3.3, D1b.3 | The panel's deterministic gate is the claim check, it records decisions through the lifecycle, and it role-gates D1b's queue commands |
| D3.5 | D3.1, D3.2, D3.3 | Imports validate retrospectively and seal through the lifecycle |
| D3.6 | D3.1, D3.5 | Export reproduces the imported versions' hashes |
| D3.7 | D1b.4, D3.9 | Extends the shared amendment test; the amendment 3 narrative cutover is recorded only after the ledger e2e is green |
| D3.8 | D1b.5 | Extends the shared manifest test |
| D3.9 | D3.4, D3.5, D3.6, D3.8 | The e2e needs panel, imports, export and the frozen manifest |
| D4.1 | D3.1 | Supports reference ledger versions and claims |
| D4.2 | D4.1, D3.3, D3.4 | Promotion is a panel or owner decision on approved versions |
| D4.3 | D4.2, D3.3 | Retrieval filters on promotion status; flags follow version withdrawal and supersession |
| D4.4 | D1b.5 | Extends the shared manifest test |
| D4.5 | D3.5, D4.2, D4.3, D4.4 | The e2e promotes from imported Apar quote claims and retrieves against the frozen manifest |
| D5.1 | D3.6, D4.3 | Extends the narrative export and renders promoted memory and flags |
| D5.2 | D3.1, D4.1 | The views select from ledger and memory tables |
| D5.3 | D5.1 | The vault reuses the Markdown export |
| D5.4 | D1b.5 | Extends the shared manifest test |
| D5.5 | D5.1, D5.2, D5.3, D5.4 | The e2e covers exports, the read-only role and the vault (or its "not built" close) |
| D6.1 | D1b.5 | Extends the shared manifest test; must close before any other D6 stage starts |
| D6.2 | D6.1, D1a.1 | Holdout first; events extend the D1a identity tables |
| D6.3 | D6.1, D6.2, D1a.4, D1b.1, D1b.3, D2.6 | Holdout first; verification writes identity events and reuses the first-party and vendor adapters and source authority; raises HIGH operator items through the queue (D1b.3); onboarding writes land in PostgreSQL after cutover (D2.6) |
| D6.4 | D6.3 | Settings derive from verified onboarding evidence |
| D6.5 | D6.1, D6.3, D6.4 | The freeze follows the implementation; the manifest expands the pre-registered outcome |
| D6.6 | D6.5, D1b.3 | The e2e onboards and runs a comparison against the frozen manifest |
| D7.1 | D6.2, D1b.1 | Registry candidate events sit next to the identity events and never write them; the Upstox identity-only catalog role extends source authority |
| D7.2 | D7.1, D6.3, D6.4, D1b.3 | Screen members resolve to registry rows; batches onboard through verification and run comparisons |
| D7.3 | D7.2, D6.3, D3.1, D3.3 | `ADD` is sealed on verified identity and a completed batch; the watchlist chain reuses the ledger decision chain and `decide`; the drafting gate refuses ledger drafts |
| D7.4 | D1b.4, D7.3 | Extends the shared amendment test; amendment 1 describes the gate D7.3 enforces |
| D7.5 | D1b.5 | Extends the shared manifest test |
| D7.6 | D7.2, D7.3, D7.5 | The e2e runs batch and watchlist paths against the frozen manifest |
| D8.1 | D1b.1 | Extends the source-authority model |
| D8.2 | D8.1, D1a.4 | Capture only after registration; occurrences use the evidence model |
| D8.3 | D8.2, D1a.2, D1a.5, D1b.1, D1b.2 | Shareholding rows are a dictionary minor version; pairing uses the pair and corroboration tables over vendor mappings |
| D8.4 | D8.2, D1b.5 | The extraction status is recorded from retained representations; extends the shared manifest test |
| D8.5 | D8.3, D8.4, D1b.3 | The e2e runs a comparison against the frozen manifest |
| D9.1 | D1b.4 | Extends the shared amendment test |
| D9.2 | D1b.1, D3.2, D7.3 | Classification reads catalog retention and watchlist status; refuses `SOURCE_QUOTE` claims on vendor captures |
| D9.3 | D9.2, D1b.3, D2.2, D3.1, D4.1, D6.2, D6.3 | Eligibility reads classes; hold roots are queue items, legacy bindings, versions and claims, supports, identity events and onboarding outcomes |
| D9.4 | D9.2, D2.5 | Backup lists expired captures by retention state; amends D2's matched backup |
| D9.5 | D9.1, D9.3, D9.4 | Purge keeps derived amounts per the A-05 record, rechecks eligibility and ends with the amended backup under the lock |
| D9.6 | D9.5, D1a.6 | Re-fetch relinks into expired captures and reuses the probe fetcher; replay reports `ORIGINAL_EXPIRED` |
| D9.7 | D9.4, D9.5 | Restore and licence ends use the amended backup set and run a purge |
| D9.8 | D1b.5 | Extends the shared manifest test |
| D9.9 | D9.5, D9.6, D9.7, D9.8 | The e2e runs purge, re-fetch, replay and restore against the frozen manifest |

## Resolved questions

Recorded from the structure review (panel: Fable 5.1 high and GPT-6 Astra high, the latter
substituting for GPT-6.1 Sol at capacity; both REVISE, consistent; 2026-10-12).

1. **Owner-reserved data-spec §6 steps** go to the panel, the orchestrator executes, and the owner
   is informed (see Conventions; D2.2, D2.6 and D2 exit).
2. **D7 → D3** is confirmed.
3. **D1 size.** Split into the D1a tracer and D1b.
4. **Amendment records** live in `docs/blueprint/amendments/`.
5. **`eqos-4j2.8`** stays outside this workstream and runs after D3 as ledger versions (D3
   Touches).

## Core completion

The core is complete when all ten phase exits above are green and every phase epic is
closed. [`core.md`](core.md#how-to-verify-the-core-is-complete) has the full definition.
Four parts, all mechanical:
1. Every phase exit test passes.
2. Every frozen manifest and amendment record passes its shared test (`test_frozen_manifests.py`,
   `test_amendment_records.py`), including manifest-before-e2e commit order.
3. The suite passes: `uv run pytest tests/fundamentals`, `uv run mypy --strict src`, and ruff
   check and format.
4. Every phase's end-of-phase reviewer approval is recorded on its closed epic.

Core completion is necessary but not sufficient: the project completes when the pilot in
[`../../backend-roadmap.md`](../../backend-roadmap.md) passes.

**To build: `scripts/verify_project.sh`** (backend roadmap P0.8). One command that runs parts 1–3 and the pilot test, prints PASS/FAIL per
phase, and exits nonzero unless every part passes. A phase not yet built reports `NOT BUILT`
rather than skipping. Add it with D1b, the first phase that has a frozen manifest, and extend it
as each phase lands its exit test.
