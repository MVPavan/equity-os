# PREP-2 Implementation Plan — pilot run opens no SQLite store

**Origin:** `docs/backend-roadmap.md` §3 row PREP-2; bead `eqos-4j2.16`; audit 2026-10-18; Sol
plan review r1 (`REVISE`) with orchestrator rulings R1–R4; r2 **APPROVE** (GPT-6.1 Sol, 2026-10-18).
**Goal:** `fundamentals run` on the four `config/aparinds-*.yaml` refuses without an `OPEN`
PostgreSQL fact store and never constructs the SQLite `FactStore`.
**Out of scope:**
- The run → report-ledger draft writer, reading the guidance prior from PostgreSQL, and deleting
  the JSON management ledger: split to PREP-2b (see "Split out").
- Running the production cutover `eqos-3zl` (an operational step; see decision 2).
- Removing SQLite for non-pilot configs (synthetic INFY/TCS fixtures keep `store_db`).
- Memory retrieval (the run reads no memory; D4 retrieval stays a separate command).
**Constraints:**
- "No pilot code path opens the legacy SQLite store" (roadmap §3 PREP-2); bead: "a test proves
  the pilot run refuses without a PostgreSQL store".
- `ROLLED_BACK` still routes to SQLite (explicit operator rollback) when a `store_db` is configured.
- Tests only on `eqos_test_*` (`tests/fundamentals/pg_support.py`); retained Apar bytes read-only
  under the `retained` marker; nothing under `data/` edited. No migration edits or additions.
- Every task leaves `uv run pytest tests/fundamentals` green; test adaptations live in the task
  that changes the interface (R4).

## Design decisions (settled)

1. **Fail-closed by config, not a global ban.** `store_db` becomes optional. `open_fact_store`
   refuses (`FactStoreRequiredError`) when there is no store id and no `store_db`, and when the
   state is `ROLLED_BACK` with no `store_db`. SQLite is refused only for configs that omit
   `store_db`; the pilot configs drop it. Ruling R3.
2. **Store id is set now.** `origin_id_for(sha256)` from `config/legacy_import_manifest.yaml` =
   `sqlite-cb02b0f12a1708d0`. Before cutover the pilot configs refuse (no `OPEN` state). The
   cutover `eqos-3zl` is owner-approved 2026-10-18 and runs as a separate operational step; this
   plan only requires `fundamentals legacy status` to show that id `OPEN` before PQ1. Ruling R3.
3. **Comparison results: the run consumes none; it ingests retained source documents.** The
   run's QoQ/YoY comparatives come from `collect_run_comparatives` (`api/pipeline.py:495-505`),
   which reads each declared prior-quarter NSE XBRL filing's bytes from
   `data/raw/watchlist/aparinds/nse/` (`config/aparinds-fy26-q3.yaml:100-112`), verifies the
   pinned SHA-256 (`api/run_comparatives.py:56-70`), parses it with `parse_instance` (:72-78) and
   computes the change in-run (`api/comparatives.py:218` `_calculate`). No derived comparison
   result is read from a file or SQLite. The D1 comparison results (`eqos.results`,
   `pair_outcomes`, written by `compare/run_store.py:136-173`) are vendor-vs-filing results that
   `pipeline.py` and `cli.py` never import. This is source-document ingestion of retained bytes,
   which satisfies "comparison results … from PostgreSQL"; no code change. Ruling R2.
4. **Known exception, dated 2026-10-18, closed by PREP-2b:** until PREP-2b lands, the run keeps
   its JSON management ledger exactly as today (`ledger_path` stays in the pilot configs), so the
   roadmap's "ledger" wording does not yet hold. PREP-2's acceptance ("no pilot code path opens
   the legacy SQLite store") is unaffected.

## File map

| File | Responsibility | Δ lines |
|---|---|---|
| `src/fundamentals/pg/cutover.py` | `open_fact_store` refusal; `FactStoreRequiredError` | +8 |
| `src/fundamentals/api/config.py` | `store_db: str \| None`; `store_db_path` returns `None` | +2 |
| `src/fundamentals/api/cli.py` (232–240) | mkdir only for a real path | ±2 |
| `config/aparinds-fy26-q2/q3/q4.yaml`, `fy27-q1.yaml` | drop `store_db`; add `fact_store_id` | ±2 each |
| `tests/fundamentals/test_prep2_pilot_pg.py` (new) | config shape + refusal proof | +70 |
| `tests/fundamentals/test_cutover_rollback.py` | `None`/`None` refusal; `ROLLED_BACK` without path | +20 |

### Task 1: Pilot configs refuse without an OPEN PostgreSQL store

Goal: every Apar config loads with `fact_store_id == "sqlite-cb02b0f12a1708d0"` and
`store_db is None`; `fundamentals run` on any of them refuses unless that store is `OPEN` and
never constructs `FactStore`; all existing suites stay green.
Files:
- Create: `tests/fundamentals/test_prep2_pilot_pg.py`
- Modify: `src/fundamentals/pg/cutover.py`, `src/fundamentals/api/config.py`,
  `src/fundamentals/api/cli.py`, the four `config/aparinds-*.yaml`
- Test: `tests/fundamentals/test_prep2_pilot_pg.py`, `tests/fundamentals/test_cutover_rollback.py`
Interfaces:
- Consumes: `store_state`, `FactStoreState`, `FactStoreFrozenError` (existing, `pg/cutover.py`).
- Produces: `open_fact_store(store_id: str | None, store_db_path: str | None, *, pool_factory)`;
  `FactStoreRequiredError(Exception)` in `pg/cutover.py`; `FundamentalsConfig.store_db: str |
  None`; `store_db_path(config_path) -> str | None`.
Approach: test-first. `store_id is None and store_db_path is None` raises before `pool_factory`
is called; `ROLLED_BACK` with a `None` path raises `FactStoreRequiredError`. In `_run`, the mkdir
runs only for a non-`None`, non-`:memory:` path. Configs keep `ledger_path` (decision 4).
Existing-test impact (adapted in this task): `test_cutover_rollback.py:65,178,186` kept, plus
the two refusal cases. `test_data_stage2_e2e.py:95` sets an explicit `store_db` and
`fact_store_id`: unchanged. Synthetic `store_db`/`:memory:` configs: unchanged. No test that loads
a committed Apar config reads `store_db` (grep of the six files naming `aparinds-fy2*`).
Verification: `uv run pytest tests/fundamentals/test_prep2_pilot_pg.py
tests/fundamentals/test_cutover_rollback.py` green, then `uv run pytest tests/fundamentals`
green; `uv run mypy --strict src`; `uv run ruff check src tests`.
Test seams: `main(["run", "--config", <tmp copy of aparinds-fy26-q3.yaml>, ...])` with
`cutover.FactStore` monkeypatched to raise; `load_config` on the committed configs.
Dependencies: None.
Risks: low. A store with no events still raises `FactStoreFrozenError(None)` (existing).

## The proving test — `tests/fundamentals/test_prep2_pilot_pg.py`

1. `test_committed_pilot_configs_name_only_postgres` (small): each Apar config has the store id
   above and no `store_db`.
2. `test_pilot_run_refuses_without_postgres_store` (`pg`, `retained`): a tmp copy of
   `aparinds-fy26-q3.yaml` (a) with `fact_store_id` removed → `FactStoreRequiredError` before any
   pool; (b) pointing at an `IMPORTED` (not reopened) store → `FactStoreFrozenError`. In both,
   `cutover.FactStore` raises if constructed and `fact_rows` / `report_versions` counts are
   unchanged.

## Split out — PREP-2b: run writes its earnings update as a ledger draft

Owns the run → PostgreSQL `DRAFT` earnings-update writer, the PG guidance-prior read, and removal
of the JSON management-ledger persistence (and closes decision 4). PILOT-4 depends on it.
Carried requirements from Sol r1 (Sol's fix in each):
- F2: the D3 mapper rejects live output (`import_mapping.py:85-86,133-136`) → own design, not a
  mapper fork.
- F3: bind computed claims to registered PG calculation traces (27 unresolved today).
- F4: `_cited` needs `legacy_fact_translations`/`legacy_evidence_bindings`; resolve PG-written
  facts directly.
- F5: run twins as `import_sources` make `check_version` treat the draft as imported and leave
  guidance unbound without `IMPORT_SEAL` → distinct source/citation path for run drafts.
- F6: only PQ0 initialises without a prior; later quarters require the immediate predecessor;
  test an empty-ledger Q3 refusal.
- F7: check the predecessor report's head version (a newer `DRAFT` blocks); test
  HISTORICAL→DRAFT, APPROVED→DRAFT, DRAFT-only. A `DRAFT` prior refuses (R3).
- F8: pass the exact aware cutoff datetime, not a date; test a timestamp between cutoff and
  day-end.
- F9: the stage-2 fixture needs watchlist membership, a bootstrap version and transcript captures.
- F10: positive path uses real `submit`/`check`/`decide`, not `ledger_support.approve`.
- F11: pin the consumed prior version/digest; one PG stale-predecessor test replaces the deleted
  JSON ones.
- F12/R4: test adaptations live in the task that changes each interface.

## r1 dispositions

1. Comparison results → decision 3 (no stored results consumed; retained-byte ingestion).
2. → split to PREP-2b (Out of scope; F2).
3. → split to PREP-2b (F3).
4. → split to PREP-2b (F4).
5. → split to PREP-2b (F5).
6. → split to PREP-2b (F6).
7. → split to PREP-2b (F7).
8. → split to PREP-2b (F8).
9. → split to PREP-2b (F9).
10. → split to PREP-2b (F10).
11. → split to PREP-2b (F11).
12. → Constraints (green after every task) and Task 1 "Existing-test impact"; carried as F12.
P3. → decisions 1 and 2 (settled rulings; cutover owner-approved 2026-10-18, separate step);
   old open decision 5 (DRAFT prior refusal) → PREP-2b F7.

## Implementation ruling (orchestrator, 2026-10-18)

The frozen ledger Stage 5 manifest pins `config/aparinds-fy26-q4.yaml` by SHA-256, and
`test_approved_payload_preceded_its_e2e` forbids amending it after its e2e (`4f0d4ca`). So that
file stays byte-identical as D9 evidence, and the pilot's Q4 run uses
`config/aparinds-fy26-q4-pg.yaml` (the same config with `fact_store_id` in place of `store_db`).
`test_prep2_pilot_pg.py` names the four pilot configs explicitly.
