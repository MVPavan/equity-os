# PILOT-GAP memory — the workflow writes and retrieves long-term memory (eqos-4j2.25, eqos-4j2.20)

**Origin:** bead eqos-4j2.25 (PREP-4 matrix review r1, Sol, 2026-10-18, pilot blocker): "no
production caller stages memory via PgMemoryStore (tests do: `test_ledger_stage2_e2e.py:359`).
Also missing a sequential-workflow retrieval boundary: export retrieves at `cutoff=None`. Include
staging retry/natural key (see eqos-4j2.20)." Source-of-truth matrix
(`docs/blueprint/source-of-truth-matrix.md`) row **Long-term memory** (:38) and Gap 3 (:52).
Acceptance: `docs/backend-roadmap.md:105` **PILOT-5** — "Items promoted after PQ1 (Q3 FY26) are
retrieved in PQ2 and PQ3 with provenance, at the actual sequential evaluation boundaries (after
the prior promotion, later events excluded). A contradicted item is surfaced. Separately,
retrieval at a historical source cutoff returns nothing the pilot created." D4 clauses: ledger
spec `docs/specs/2026-10-12-report-ledger-memory-and-data-lifecycle.md` §2 (:281–337: entities,
lifecycle, revalidation, "retrieval at a cutoff derives … only from records at or before it",
`MemoryStore` interface, "the comparator and report checks never read memory") and Stage 2
acceptance (:559–575).
Status: **approved — gpt-6.1-sol APPROVE, 2026-10-19** (r1 REQUEST_CHANGES 7 → r2 APPROVE; fresh closing
REQUEST_CHANGES 3 → APPROVE). Orchestrator ruling: this plan lands **before** PILOT-GAP-admission (now blocked
on `eqos-4j2.33`); admission adapts to the shared `RunDraft(...)` call (`api/cli.py:344`) afterwards.
**Goal:** a production command stages a memory item (idempotently on retry); promotion uses the
existing owner `ledger decide`; every PostgreSQL `fundamentals run` retrieves the stock's promoted
memory at a store-clock boundary it captures before the pipeline starts, and seals the boundary,
item ids, flags and support ids into that quarter's draft heading. The pipeline and every check
stay memory-blind.

## Findings verified in code (file:line)

1. **No production stager.** `PgMemoryStore.stage` (`src/fundamentals/memory/pg_store.py:39–50`)
   has no caller under `src/`. The only stage in the end-to-end test is
   `tests/fundamentals/test_ledger_stage2_e2e.py:359`.
2. **Promotion already has a production path:** `ledger decide MEMORY_ITEM <id> PROMOTE`, ruling on
   stdin, as owner (`api/ledger_cli.py:172–191` → `lifecycle.decide`). No panel CLI
   (`ledger_cli.py:115–150` registers `decide`, `check`, `import`, `export`); that is F1, eqos-tqf.
3. **Nothing retrieves at an evaluation boundary.** `_export_stock` (`ledger_cli.py:257–288`)
   retrieves once at `cutoff=None`. The run never reads memory (`api/cli.py:302` `preflight` →
   `:339` pipeline → `:358` `write_run_draft`).
4. **`created_at` is not the evaluation boundary** (Sol r1): the pipeline finishes before
   `write_run_draft` creates the version (`cli.py:339`, `:358`), so a promotion during the run
   would precede `created_at`.
5. **The store clock is monotonic and writes.** `eqos.store_now()` issues
   `GREATEST(clock_timestamp, last + 1µs)` under an advisory lock, `setval`s a sequence and caches
   per transaction (`migrations/0005_store_clock_cache_and_keyless_dimensions.sql:24–58`); so it
   cannot run in a READ ONLY transaction, and every row stamped later has a strictly larger time.
   Memory `recorded_at` (`0016:96`) and decision `recorded_at` (`0012:315`) use it.
   `run_draft.py` already imports `_NOW` (`SELECT eqos.store_now()`, `lifecycle.py:111`; used at
   `run_draft.py:280`). `store_now` releases its session advisory lock before returning
   (0005:40 lock, :51 unlock), so a clock read alone does not order against an uncommitted writer.
6. **Retrieval at a cutoff is complete and tested:** items, head decisions, successor `PROMOTE`
   and the support predicate filter `recorded_at <= cutoff` (`retrieval.py:48–63`);
   `PgMemoryStore.retrieve` runs it in one REPEATABLE READ, READ ONLY snapshot (`pg_store.py:82–97`,
   `:103–108`). `RetrievedItem` carries `id`, `needs_revalidation`, `supports`
   (`contracts/memory.py:106–122`); each `SupportRef` has `target` (the `memory_supports` column,
   e.g. `claim_id`, `SupportTarget` :44–53) and `target_id` (:80–87).
7. **The heading is sealed run metadata.** `_sections` (`run_draft.py:539–575`) builds section 0
   (`HEADING`) with `{{e:computed}}`, cutoffs, prior and originals; it is in `content_hash`
   (:275). Its numerals must be structural (`ledger/numeral_scan.py:22–40`): ISO timestamps and ids
   of the form `name:123` pass. Rework ignores ordinal 0 (`rework.py:235`); review requires only
   that it has no placeholder (`review.py:158–162`). `test_four_quarter_sequence`
   (`test_prep2b_run_draft.py:437`) already asserts heading content per quarter with `in`.
8. **No natural key.** `memory_items` has only a GIN index (`0016:6–25`; statement ≤ 500 chars,
   :11); `stage` is a plain `INSERT … RETURNING id` (`pg_store.py:22–25`). Runtime has SELECT and
   INSERT only (0016:243–245). PostgreSQL 18; `NULLS NOT DISTINCT` used in 0005/0006.
9. **Triggers on a conflicting insert** (corrects r1's risk note): the BEFORE INSERT triggers on
   `memory_items` are `record_memory_item` (0016:88–99, :222) and `refuse_after_promote` (0018:15,
   refusing writes after a same-transaction promotion; a retry runs in its own transaction). The first checks that a superseded target
   exists with the same stock and kind (immutable facts) and stamps `recorded_at`; it does not
   require the target to be `PROMOTED`. Support validity is checked by deferred AFTER INSERT
   constraint triggers (0016:224, 0017:186, 0019:24). `ON CONFLICT DO NOTHING` inserts no item
   row, so those never fire and no support rows are inserted.
10. **Promotion of a correction needs its predecessor still `PROMOTE`d with no promoted
    successor** (0016:153–158); a `REJECTED`/`RETIRED` item cannot be re-promoted by correction.
11. **Tests that stage identical content and expect distinct items** (break under the key):
    `test_memory_store.py:278`, `:322` (expects a fresh id after `:301`'s identical stage), `:330`,
    `:359–360`; `test_memory_retrieval.py:90`/`:93` (`:93` equals `:90`), `:182`/`:183`, and `:192`
    (becomes a retry: returns the id instead of refusing); `test_memory_promotion.py:241`/`:245`,
    and `:338`/`:344` (cross-stock LESSON: `:344` restages `:338`'s key with a claim support and
    expects the LESSON support predicate's `CheckViolation`; it would hit `MemoryStageConflictError`).
    The rig's `draft()` uses one `STATEMENT` (`tests/fundamentals/memory_support.py:42`, :132–148).
    Refused-then-repeated stages (`test_memory_promotion.py:264–267`, :321–326) roll back the first
    insert, so they do not collide. `test_memory_races.py:35` `race()` runs two owner connections.
12. **Pilot quarters:** `Pilot` (`tests/fundamentals/prep2b_support.py:81`) runs FY26_Q2 (bootstrap),
    FY26_Q3 (PQ1), FY26_Q4 (PQ2), FY27_Q1 (PQ3) (:55–60); `run` (:219), `approve` (:243),
    `validate` (:238), `version` (:229). `run_command` calls `run_pipeline` through the module
    global (`cli.py:273` `partial(run_pipeline, …)`), so a test can wrap it.
13. **The queue lock orders memory-visible writes against a clock read.** `eqos.lock_queue()`
    (`0009:19–41`, granted to runtime :41, to panel/owner `0012:479`) is a transaction-level
    advisory lock that refuses a transaction that already read the store clock (55000, `0009:30–34`).
    Every memory decision takes it before its stamp (`check_memory_decision`, `0016:140`), as does
    every support-falsifying write: validations and successor/`WITHDRAW` report decisions
    (`lock_support_writer`, `0017:164–194`). Python helper `lock_queue(cursor)`
    (`compare/queue.py:86`), used before `_NOW` in `approval_check` (`lifecycle.py:213–215`).

## Decisions

1. **Stager = `fundamentals ledger stage <item.yaml>`**, runtime role. The file is a
   `MemoryItemDraft` (`contracts/memory.py:64–77`) — no new model. Prints `memory item <id>`.
   Refusals (`psycopg.Error`, `ValueError`, `ValidationError`, `yaml.YAMLError`) are already
   `LEDGER_FAILURES` (`ledger_cli.py:101–112`) → `EXIT_REFUSED`.
2. **Promotion stays `ledger decide MEMORY_ITEM <id> PROMOTE` (owner).** No new code.
3. **Natural key = the item's columns** `(entity_id, kind, statement, epistemic_class, valid_from,
   valid_to, supersedes_item_id)`, `UNIQUE NULLS NOT DISTINCT`, migration
   `0041_memory_natural_key.sql`. Why a migration: only a unique index makes concurrent identical
   stages converge whoever the writer is (the triggers are authoritative, `pg_store.py:1–3`); an
   advisory lock in Python would hold only for writers that take it. `stage` inserts with
   `ON CONFLICT DO NOTHING RETURNING id`; on no row it reads the existing id by a null-safe
   (`IS NOT DISTINCT FROM`) lookup and its support set. Same set → return that id, nothing written.
   Different set → `MemoryStageConflictError(ValueError)`. Supports live in another table, hence
   the compare.
4. **Terminal retry stays terminal.** An exact retry of a `REJECTED` or `RETIRED` item returns its
   original id; its decision history is unchanged. No recovery advice in the error or docs
   (finding 10).
5. **One required quarterly retrieval step, inside `fundamentals run`.** After `preflight` and
   before the pipeline, the PG branch calls `recall(pool, prior.entity_id)` (new, `run_draft.py`):
   it takes the boundary in its own transaction (finding 5: not READ ONLY) as `boundary(cursor)`:
   `lock_queue(cursor)` then `_NOW` (finding 13). Any promotion or invalidation stamped earlier has
   committed before the lock is granted; any later one stamps after the boundary. Then `PgMemoryStore(pool).retrieve("", stock=…, cutoff=boundary)` (promoted only),
   and returns one heading line:
   `Memory retrieved at store time <boundary ISO>: memory:<id> (needs revalidation: yes|no;
   supports claim:<id>, version:<id>); … ` or `…: none.` Support labels are
   `target.value.removesuffix("_id")` + id (`claim`, `version`, `definition_record`,
   `disposition`, `decision`, `capture_ref`) — structural ids (finding 7). Statements are not
   copied (they may hold numerals; items are immutable and reachable by id).
6. **Persistence = the version's sealed heading.** `RunDraft` gains `memory: str`; `_sections`
   appends it to the heading paragraph after "Originals first seen". It is sealed in the content
   hash, so the boundary, ids, flags and provenance stay bound to that quarter's version; a rework
   run gets its own line (its own later evaluation). No table, no migration for this. The pilot
   test reads it with `store.read_version(...).sections[0].body`.
7. **Memory-blind checks.** The line is not passed to `run_pipeline`, `before_commit` or
   `check_version` as memory: the checks perform no memory retrieval or semantic use of it
   (`check_version` does scan the persisted heading text, which passes; finding 7). The comparator and claim checks are
   unchanged (spec §2 :337).
8. **Invalidation = `needs revalidation: yes` at the boundary** after a demonstrated support
   invalidation (Sol OQ5); genuine contradiction evidence is eqos-4j2.8's. Provenance = support ids; `retrieval.support_refs`/`provenance` give
   the structured path to citations and captures (Sol OQ6).
9. **Dropped from r1:** per-version `<stem>.memory.md` export, `VersionIdentity.created_at`,
   `format_memory(as_of=…)`. `ledger export` of a version already carries its heading, so the
   export needs no change; `memory.md` stays the current view.

## Assumptions

- PQ1's draft claims check `MATCH` after the owner's approval check (`test_four_quarter_sequence`
  asserts every claim `MATCH`), so a PQ1 `fact.*` claim is a valid support.
- A later `RETROSPECTIVE` validation of the supporting version fails the claim support and flags
  the item (as `test_memory_promotion.py:236–245` shows for staging); it does not affect the next
  quarter's preflight, which reads decisions (`run_draft.py:206–209`).
- The pilot's real contradiction scenario is eqos-4j2.8's; the test uses this device.

## Shared files with eqos-4j2.24 (`docs/plans/PILOT-GAP-admission.md`) — sequence memory first (orchestrator ruling 2026-10-19)

| File / function | Admission | Memory |
|---|---|---|
| `src/fundamentals/api/cli.py` `run_command` PG branch | manifest check, `skip_roles`, admit+select in `before_commit`, `RunDraft(facts=…)` | one line after `prior = preflight(…)` (:302), `memory=` kwarg in `RunDraft(…)` (:344) |
| `tests/fundamentals/prep2b_support.py` `Pilot` | edits `run`, adds `compare_run` | uses only (no edit) |
| `tests/fundamentals/test_prep2b_run_draft.py` | e2e host | not touched |

No other shared file: admission does not touch `ledger/run_draft.py`, `memory/`, `ledger_cli.py`
or migrations (it claims none; this plan takes 0041). Memory lands first and its pilot test runs on today's
`Pilot`; admission later puts `--compare-run` in `Pilot`'s shared argv path, which memory's tests then inherit. eqos-4j2.27 also edits
`api/ledger_cli.py` — sequence, never parallel.

## File map

| File | Change | Task |
|---|---|---|
| `migrations/0041_memory_natural_key.sql` | create: one unique index | 1 |
| `src/fundamentals/memory/pg_store.py` | `stage(cursor, draft)` module function (conflict read, `MemoryStageConflictError`); `PgMemoryStore.stage` wraps it | 1 |
| `tests/fundamentals/test_memory_store.py` | retry/conflict test; distinct statements at :278, :322, :330, :359–360 | 1 |
| `tests/fundamentals/test_memory_retrieval.py` | distinct statements at :93, :183; :192 asserts the retry returns `item` with nothing written, plus a distinct-statement stage that still refuses | 1 |
| `tests/fundamentals/test_memory_promotion.py` | :245 a distinct statement (still refused); :344 a distinct statement, keeps its `CheckViolation` assertion | 1 |
| `tests/fundamentals/test_memory_races.py` | `race(…, role=PgRole.OWNER)`; one concurrent staging test | 1 |
| `src/fundamentals/api/ledger_cli.py` | `stage` action | 2 |
| `src/fundamentals/ledger/run_draft.py` | `boundary`, `recall`; `RunDraft.memory`; heading line in `_sections` | 2 |
| `src/fundamentals/api/cli.py` | `recall` call; `memory=` | 2 |
| `tests/fundamentals/test_pilot_memory.py` | create: sequential pilot memory e2e | 2 |
| `tests/fundamentals/test_memory_races.py` | one overlapping-promotion boundary test | 2 |

## Size estimate (not measured)

- Source: ~50 lines (migration ~4, `stage` ~20, CLI action ~12, `recall` ~12, `RunDraft`/heading
  ~2, `cli.py` ~2). r1's export loop, `VersionIdentity.created_at` and `as_of` are gone.
- Tests: ~150 new lines (retry/conflict ~25, concurrency ~25, pilot e2e ~100) plus ~15 edited.
- Two tasks, both Opus (Task 1 concurrency semantics; Task 2 is the acceptance).

## Tasks

### Task 1: Staging is idempotent on its natural key (closes eqos-4j2.20)

Files: create `migrations/0041_memory_natural_key.sql`; modify `memory/pg_store.py`,
`test_memory_store.py`, `test_memory_retrieval.py`, `test_memory_promotion.py`,
`test_memory_races.py`.

Interfaces:
- Produces: index `memory_items_natural_key`; `stage(cursor, draft) -> int` in `pg_store.py`;
  `PgMemoryStore.stage(draft) -> int` (same signature; runs `stage` in one transaction);
  `MemoryStageConflictError(ValueError)`.

Approach: `_ITEM` gains `ON CONFLICT DO NOTHING`. No row → null-safe `SELECT id` on the key
columns, then its supports as `(target, target_id)`; compare as sets with the draft's. Equal →
return the id; else raise. Supports are inserted only on a fresh insert. READ COMMITTED (the
default) lets the follow-up select see a concurrent committer's row.

Tests (medium, `pg`):
- `test_memory_store.py`, one parametrized test: retry after staging, after `PROMOTE`, after
  `REJECT_CANDIDATE`, after `RETIRE`, and after support invalidation each returns the original id;
  "nothing written" = memory item, support and decision row counts unchanged; the item's status
  is unchanged (a terminal item stays terminal). The same columns with a different support set
  raise `MemoryStageConflictError`, counts unchanged.
- `test_memory_races.py`, one test, two runtime connections via `race`: the holder stages a draft
  and holds; the waiter blocks on the index. Case identical → the waiter returns the holder's id,
  one item row, its full support set. Case different supports → `MemoryStageConflictError`.
- Finding-11 sites get distinct `statement=` values so each tests what it names; `:192` keeps the
  retry-after-invalidation assertion explicitly.

Verification: `uv run pytest tests/fundamentals/test_memory_store.py tests/fundamentals/test_memory_promotion.py tests/fundamentals/test_memory_races.py tests/fundamentals/test_memory_retrieval.py tests/fundamentals/test_ledger_stage2_e2e.py tests/fundamentals/test_pg_migrations.py`;
`uv run mypy --strict src`; `uv run ruff check src tests/fundamentals`.

Risk: medium. Index creation fails if a database already holds duplicates (none expected: no
production stager). 0041 first detects duplicate key groups and, if any, raises listing their
ids for an explicit owner disposition; it never deletes rows. Other test files staging identical content may surface in the full run; fix
them the same way.

### Task 2: `ledger stage` and the quarterly retrieval step

Files: modify `api/ledger_cli.py`, `ledger/run_draft.py`, `api/cli.py`,
`tests/fundamentals/test_memory_races.py`; create `tests/fundamentals/test_pilot_memory.py`.

Interfaces:
- Produces: CLI `fundamentals ledger stage <path>` → `memory item <id>`, exit 0, or
  `EXIT_REFUSED`; `boundary(cursor) -> datetime`; `recall(pool, entity_id) -> str`; `RunDraft.memory: str` (required; `cli.py:344`
  is the only constructor under `src/`).

Approach: `stage` reads YAML, `MemoryItemDraft.model_validate`, runtime pool,
`PgMemoryStore.stage`. `recall` per Decision 5; `_sections` adds `f"{run.memory}\n"` to the
heading paragraph.

Test (large-ish, `pg`, `retained`; one test on `Pilot`, in order):
1. Run and approve FY26_Q2, then FY26_Q3 (PQ1): PQ1's heading line ends `: none.`
2. `ledger stage item_a.yaml` twice (a PQ1 `fact.*` claim as support) → same id printed; owner
   `PROMOTE` (lifecycle).
3. Run FY26_Q4 (PQ2): its line lists `memory:<a>` with `needs revalidation: no` and
   `supports claim:<id>`; approve.
4. Invalidate A's support (RETROSPECTIVE validation of the PQ1 version); stage item B (a PQ2
   claim support).
5. Run FY27_Q1 (PQ3) with `run_pipeline` wrapped to promote B first (an event after retrieval and
   before draft creation): the line lists A with `needs revalidation: yes` (invalidation
   surfaced) and not B. This is an **invalidation integration test**, not genuine contradiction
   evidence; that stays outstanding for eqos-4j2.8 and this test alone does not satisfy PILOT-5's
   contradiction clause.
6. Replay: for PQ2 and PQ3, parse the boundary from the line; `retrieve(cutoff=boundary)` gives
   exactly the listed ids and flags; at `cutoff=None` B is present.
7. Historical: for PQ1–PQ3, `retrieve(cutoff=update.source_cutoff)` from each run's own result is
   `()`; the assertion message carries the cutoff values (evidence for eqos-4j2.8).

Test (medium, `pg`, `test_memory_races.py`): `race` with hold = an owner `PROMOTE` of a staged
item (takes the queue lock and stamps), wait = `boundary(cursor)`, observed blocked on the holder.
After the holder commits: the waiter's boundary > `held_at`; the line built from
`retrieve(cutoff=boundary)` lists the item; a later replay at the same cutoff gives the same line.

Verification: `uv run pytest tests/fundamentals/test_pilot_memory.py tests/fundamentals/test_memory_races.py tests/fundamentals/test_prep2b_run_draft.py tests/fundamentals/test_prep6_review.py`;
then `uv run pytest tests/fundamentals`; `uv run mypy --strict src`;
`uv run ruff check src tests/fundamentals`; `uv run ruff format --check src tests/fundamentals`.

Risk: medium. Runtime of four pilot quarters (as `test_four_quarter_sequence`). Boundary skew is
closed by the queue lock (Decision 5, finding 13); a run waits for an in-flight promotion or
invalidation to commit.

## Interactions with open beads

- **eqos-4j2.20** — closed by Task 1.
- **eqos-4j2.24** (admission) — lands first; see the shared-files table.
- **eqos-4j2.27** — also edits `api/ledger_cli.py`; sequence, never parallel.
- **eqos-4j2.8** (pilot run) — consumes `ledger stage`, `ledger decide … PROMOTE` and the heading
  line; designs the real contradiction scenario.
- **eqos-tqf** (F1 panel CLI) — panel promotion arrives there.
- **eqos-3p6** — imported PQ0 versions cannot support memory until an owner `AS_KNOWN` validation.
- After landing: update matrix row :38 and Gap 3 (:52), then close eqos-4j2.25.

## Not verified

- That `memory.pg_store` imported into `ledger.run_draft` creates no import cycle transitively
  (direct modules checked: none of `ledger/{store,citations,display,lifecycle,panel}.py` or
  `memory/*` imports `run_draft`).
- That a RETROSPECTIVE validation of a retrospective pilot version flags (not errors) under the
  pilot fixture.
- Test files beyond finding 11 that stage identical content (`tests/` not grepped recursively).
- That no test outside the named files asserts the exact heading text.

r2 (Sol APPROVE 2026-10-19) notes applied: finding 9 trigger list, Decision 7 wording; the race helper must capture `MemoryStageConflictError` (test_memory_races.py:55) at implementation.

## r1 findings → resolution

| # | Finding | Resolution |
|---|---|---|
| 1 | P1 export-after-all-quarters is hollow | Export expansion dropped. Retrieval is a required step inside each quarter's `fundamentals run` (Decision 5), sealed into that version (Decision 6); Task 2 asserts it quarter by quarter before advancing. Checks stay memory-blind (Decision 7). |
| 2 | P1 `created_at` is not the boundary | Boundary = `store_now()` taken by `recall` before the pipeline (findings 4–5). Task 2 step 5 promotes B between retrieval and draft creation (excluded); step 6 replays at the boundary and shows B present later. |
| 3 | P2 invalid re-promotion advice | Exact terminal retry returns the original id; no recovery advice (Decision 4, finding 10); Task 1 asserts terminal status and history unchanged. |
| 4 | P2 missed natural-key collisions | Finding 11 adds `test_memory_retrieval.py:90/:93`, `:182/:183`, `:192` and `test_memory_store.py:322`; file map owns them; `:192` keeps an explicit retry-after-invalidation test. |
| 5 | P2 arbitrary historical datetime | Task 2 step 7 uses each run's own `source_cutoff`; pilot items absent there, present at later boundaries (steps 3, 5); cutoffs in the assertion message. |
| 6 | P3 false trigger-risk claim | Corrected (finding 9). Task 1 tests retries after promotion, rejection, retirement and support invalidation; "nothing written" = no new item, support or decision rows. |
| 7 | P3 no concurrent staging test | Task 1 adds one two-connection test (identical; conflicting supports) via `race`. |

## closing r1 findings → resolution

| # | Finding | Resolution |
|---|---|---|
| 1 | P2 boundary can replay a different set | `boundary(cursor)` takes `lock_queue` before `_NOW` (Decision 5, finding 13: memory decisions `0016:140`, support-falsifying writes `0017:164–194`; `store_now` unlocks at `0005:51`). Task 2 adds a `race` test: overlapping `PROMOTE`, heading equals replay at the same cutoff. Risk note replaced. |
| 2 | P2 `test_memory_promotion.py:338/:344` collision | Finding 11 and the file map: `:344` gets a distinct statement and keeps its `CheckViolation` assertion (Task 1). |
| 3 | P3 contradiction mislabelled | Task 2 step 5 and Decision 8 call it an invalidation integration test; genuine contradiction evidence stays outstanding for eqos-4j2.8. |
| — | Note: pre-existing duplicates block 0041 | Task 1 risk: 0041 detects duplicates and raises with their ids for explicit disposition; never deletes. |
