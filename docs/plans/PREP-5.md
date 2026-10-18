# PREP-5 Implementation Plan — a rejected claim reworks only its affected claims into v(N+1)

**Origin:** `docs/backend-roadmap.md` §3 row PREP-5 ("Rejected-claim rework path and
evidence-package versioning (B-14)"; done when "A rejected claim reruns only affected claims and
produces v(N+1)") and §4 PILOT-11 ("One claim is rejected → only affected claims rerun → package
v(N+1)"). Register B-14 acceptance: "A rejected claim triggers the correct invalidation cascade;
evidence package v(N+1) is created; only affected calculations/claims are rerun; prior package
remains immutable; partial revalidation and reapproval succeed". Source-of-truth matrix
(`docs/blueprint/source-of-truth-matrix.md`) row "Evidence packages" and Gap 1.
Status: **approved** — reviewer gpt-6.1-sol, verdict APPROVE, 2026-10-18 (plan r1–r3 REVISE 10/4/1,
orchestrator ruling; closing review REVISE 7, re-reviews REVISE 5/1, orchestrator rulings A–D, final
APPROVE; all tables at the end).
**Goal:** a reviewer names claims of an `IN_REVIEW` run draft N when requesting changes; after the
operator corrects an input, re-running the quarter writes N+1 that carries every unaffected
claim's records and rendered line from N, re-derives only the affected lines against the
corrected evidence, refuses before any write if anything outside them moved, validates in full
and can be approved, while N stays unchanged.
**Out of scope:**
- A package table, digest or export (decision 1). Frozen pilot manifest: PREP-7.
- Correction tooling: how an operator fixes a config, mapping, capture or code (A3).
- Per-claim review time, dispositions, diff-only review UI: PREP-6 / C-05.
- Panel (model reviewer) naming claims: `ledger/panel.py` is untouched; a `REQUEST_CHANGES`
  naming no claims reruns everything, as today.
- A `ledger submit` CLI (`eqos-4j2.21`, accepted limitation): N+1 is submitted by
  `lifecycle.submit`, as in PREP-3.
- Rework of imported versions (they cannot be `SUBMIT`ted, so cannot receive `REQUEST_CHANGES`).
- Making the pipeline's in-memory parse, gates and render selective (decision 4, open question 1).
- Register B-14 Status: the register is hash-pinned; approval is recorded in the roadmap row and
  this plan, as PREP-4 did for B-03.
**Constraints:**
- Every task leaves `uv run pytest tests/fundamentals`, `uv run mypy --strict src`,
  `uv run ruff check src tests/fundamentals`, `uv run ruff format --check src tests/fundamentals`
  green. Tests on `eqos_test_*` only (markers `pg`, `retained`).
- Migrations 0001–0038 are immutable; one new migration, `0039`.
- Ledger rows are append-only; versions are sealed at `SUBMIT`; status is derived from the
  decision log, never stored (P1). Models never author amounts (invariant 6).
- Do not touch hashed extractors, `evidence/vendor_ingest.py`, `compare/resolve_loader.py`,
  `pg/legacy_import.py`, `contracts/source_catalog.py`, frozen `config/aparinds-fy26-q4.yaml`,
  or anything under `data/` (tests write synthetic files under `tmp_path` only).
- Owner 2026-10-14: smallest thing that meets the acceptance; tests over machinery.

## Findings that shape the design (verified in code)

1. **Rejection is version-level only.** `decisions` has `REQUEST_CHANGES` and `REJECT` on a
   `REPORT_VERSION` (0012, `lifecycle.TRANSITIONS`: panel or owner, head `SUBMIT`) with a free-text
   `ruling`; no row names a claim. `validation_claim_states` are checker states, not verdicts.
2. **A closed head already gets a successor.** `run_draft.preflight` and `write_run_draft` refuse
   only an open head; on `CHANGES_REQUESTED` the run writes a version with `predecessor_id = head`;
   `eqos.version_number` (0014) gives N+1.
3. **Today's run re-derives everything.** `run_command` (`api/cli.py:303`) runs the whole pipeline;
   its `before_commit` hook runs `run_traces.bind_computed`, which looks up every operand,
   computes every trace (`conclude`) and stores them (`put_calculation_trace`); then pipeline step
   10 stores every role's fact and changes canonical selections; only then does
   `write_run_draft` open its transaction. Reuse by content hash makes equal rows, not selective
   execution, and any refusal in `write_run_draft` comes after those writes (Sol r1 1, 6).
4. **The `before_commit` hook is the last point before any persistent write**, and every value
   the draft will carry is already in memory there: the `EarningsUpdate` (facts, comparatives,
   calculations, rendered guidance) and the extracted `GuidanceClaim`s.
5. **The seal pins trace ids, not operand membership.** `version_sealed_digest` (0012) hashes
   citation ids; `calculation_trace_operands` refuses UPDATE/DELETE (0029) but not a late INSERT
   at an unused ordinal (`UNIQUE (calculation_trace_id, ordinal)`, 0001:363). The only writer,
   `_insert_trace` (`repository.py:700`), inserts a new trace's operands right after its row, in
   the same transaction, at ordinals `0..n-1` (`enumerate(trace.operands)`); a content-hash hit
   inserts none. `get_calculation_traces` re-checks each trace's hash over its operand rows; the
   ledger resolver (`citations.py:397`) does not (Sol r2 3). Retention purge (0029) UPDATEs only
   the value columns `reject_mutation_except_tombstone` lists, so any other trace column — a new
   one included — is immutable.
6. **Claim dependencies are recoverable from rows.** A run draft emits `FIGURE` on a fact row
   (`fact_rows.file_sha256`) or an interpretation (`capture_refs.blob_sha256`), `CALCULATION` on a
   trace whose operands carry `key_digest` and `interpretation_id`, and `SOURCE_QUOTE` on a capture
   with an `anchor`. Fact claims and trace operands key the same measurement equally
   (`measurement_key`; A4).
7. **A version's text is lines of placeholders.** `_sections` (`run_draft.py:448`) builds each
   non-heading body as `## <key>`, the section's `INTROS` sentence, then `- ` lines (`- none` when
   empty). Intros carry meaning: the changes intro defines the subtraction direction (Sol r2 4);
   a line names its claims by `{{c:<key>|<style>}}` (`display.PLACEHOLDER`). Changes lines hold a
   prior, an absolute and a percent claim; results, calculations and guidance lines one each;
   unavailable lines none. The heading section is run metadata (cutoffs, prior pin, originals).
8. **Approval needs a state for every claim** of the latest `AS_KNOWN` validation (0012).
9. **Guidance bounds are not contract-bound.** `GuidanceContract` (`contracts/ledger.py:281`) is
   metric, scope, horizon, unit, constant currency; the bounds are checked against the numbers
   in the quote (`claim_check._quote_means_claim` → `guidance_quote_holds`). r1's finding 7
   ("bounds bind only to a sealed import") was wrong. A guidance value comes from the transcript,
   so a value-changing correction drill uses a filing, not guidance (Task 4).
10. **Comparator XBRLs pass no whole-filing gate.** `run_comparatives` hash-checks, parses and
    selects one prior per concept; cross-foot and XBRL↔PDF cross-check apply to the current
    filing only (revenue is a default cross-check concept). A comparator with one changed
    measurement is therefore a valid corrected filing.
11. **0018 makes a memory PROMOTE the transaction's last ledger write** by a
    `refuse_after_promote` trigger on every ledger and queue table.
12. **N's claims are all resolved; a skeleton is not.** `SUBMIT` requires no `unresolved` claim
    (0014); the uncited `_valued` claim (`import_mapping.py:407`) has `unresolved = True`, and
    `cite` (`run_traces.py:337`) sets it `False` (Sol r2 1).
13. **N takes no further decision after `REQUEST_CHANGES`.** `APPROVE`/`REQUEST_CHANGES`/`REJECT`
    need head `SUBMIT` (`lifecycle.py:67`, `0014_ledger_review_fixes.sql:117`). A
    `CHANGES_REQUESTED` or `REJECTED` head is closed (`lifecycle.OPEN` = `DRAFT`, `IN_REVIEW`), so a
    run writes its successor; a head without claim rejections gets today's full run.

## Decisions

1. **Evidence package = the version's cited records; no new table.** N's package is, per claim,
   the input atoms `rework.inputs` derives (decision 3). Identity (report, `version_number`),
   integrity N's `sealed_digest` plus bounded operand membership (`operand_count`, 0039) and
   trace-hash verification on read, lineage the version chain. "Prior package remains immutable" is proven
   by re-deriving N's inputs and rerun set after the rework and by a direct-SQL expansion attempt.
   Rejected: an `evidence_packages` table (duplicates the version chain and seal).
2. **A rejected claim is a key in a typed, immutable column of its `REQUEST_CHANGES` decision**
   (closing r2 ruling C). `decisions.rejected_claims text[]` (0039): a CHECK keeps it NULL unless
   `subject_kind = 'REPORT_VERSION'` and `kind = 'REQUEST_CHANGES'`, and non-empty when set; a
   BEFORE INSERT trigger refuses (23514) a duplicate key or one that is not a `claim_key` of the
   subject version. Written in the decision's own INSERT, so it inherits the decision's lock and
   head check (0014 `check_decision`), immutability (0012 `reject_mutation`),
   `refuse_after_promote` (0018) and grants; no transaction, time or restore guard is needed.
   Written by `ledger decide REPORT_VERSION <id> REQUEST_CHANGES --claim <key> …`. `REJECT` and
   claim-less `REQUEST_CHANGES` behave as today (full rerun). Not hashed into `decision_sha256`:
   0014's `stamp_decision` is recomputed nowhere in `src`, so including it would copy that
   function for no check; row immutability is the guarantee.
   Rejected: a `claim_rejections` table (needed a same-transaction guard that is not restore-safe;
   closing r2 4, 5); keys in `ruling`; a `CLAIM` subject kind; `REJECT` with claims.
3. **Affected = one-hop shared inputs; the rerun unit is the line.** A claim's atoms:
   `(blob, key_digest)` for a `FIGURE` (fact row file or interpretation capture blob) and for
   each operand of a `CALCULATION` (operand interpretation's capture blob, operand key digest);
   `(blob, anchor)` for a `SOURCE_QUOTE`. Affected = rejected claims plus every claim of N with an
   atom among the rejected claims' atoms. **Rerun set** = every claim on an N line that holds an
   affected claim (a line is re-rendered whole, so its line-mates are re-derived with it).
   Carried = the rest. Any other citation kind, a claim with no record, or an operand that is not
   one interpretation raises (fail closed; r1 10).
   Example (FY26_Q2): rejecting `cmp.revenue.qoq.prior` reruns that changes line (prior, abs,
   pct). Rejecting `fact.revenue` affects it, the revenue QoQ/YoY abs and pct and the income −
   revenue gap; line closure adds the two revenue `prior` figures.
   Rejected: downstream-only closure (misses siblings sharing the defective input); transitive
   closure (spreads through PBT and income to the whole statement).
4. **Selective derivation, full evidence read (Sol r2 ruling: acceptable).** The guarantee,
   precisely: operand binding, trace derivation and every persistent write are selective; the
   in-memory arithmetic is not. The pipeline still parses, gates (cross-foot, XBRL↔PDF, quote
   anchors) and renders every value of the corrected sources in memory — whole-filing checks a
   corrected filing must pass, and the values the boundary compares (finding 4). For a carried
   claim there is no operand lookup, no `conclude`, no trace storage, no fact write or canonical
   selection; N+1 reuses N's claim row (citation and resolution) and N's line text. Only rerun
   lines are bound (`_Binder.operand`/`figure`/`trace`, `put_calculation_trace`) and only rerun
   fact roles are written.
   Rejected: making `pipeline_steps`/`run_comparatives` selective (would skip whole-filing gates
   on corrected evidence and remove the drift check's inputs); equality-after-full-rerun (r1's
   design; refused by Sol r1 1 and 4).
5. **The change boundary is enforced in `before_commit`, before any write.** For each claim
   line the corrected run would produce, by its claim keys: keys all carried → the line text and
   every claim field except binding state (`citation`, `unresolved`, and a quote's `quote` and
   `anchor`) must equal N's, N's claim must be resolved (finding 12; else refused), and N's
   claim rows are used whole, binding included; keys meeting the rerun set and not the carried
   set → rerun (changed, new or dropped keys allowed: they are the rework's output); any other
   line → refused (a carried key drifted or mixed in, or every key is new — an unexplained
   addition). After all lines: every carried N line was produced, and each non-heading section's
   scaffold — its body with every claim line removed (`## <key>`, intro, unavailable and `- none`
   lines, blank lines, in order) — equals N's (Sol r2 4); then the sources check of decision 8
   runs. Any refusal raises `RunDraftError`
   naming the keys or section before the hook returns, so no trace, fact, selection or version
   is written (r1 3, 6, 7). Run metadata allowed to differ: the heading section only.
6. **Revalidation: partial derivation checks, full `AS_KNOWN` safeguard; review set derivable.**
   Rerun claims are re-checked by the binder (interpretation equality, exact recomputation); N+1
   then gets the existing in-transaction `AS_KNOWN` check over every claim (finding 8). The
   re-review set is N+1's keys minus `rework.plan(N).carried`, reproducible from N's rows.
   Reapproval is the existing submit + `APPROVE`.
7. **A refused rework is recovered by `--full-successor`, not on N** (Sol r2 2, r3). N cannot be
   re-decided (finding 13) and there is no override flag. When a correction moves something
   outside the rerun set (including a value turning unavailable or the reverse, open question
   2): `fundamentals run … --full-successor`, accepted only when the head is `CHANGES_REQUESTED`
   with claim rejections, runs today's full path and writes into N+1's sealed heading
   `Full successor of version:<N> (full rework requested; rejected <keys>)` from
   `Prior.full_successor`, a `Successor` (expected head N, rejected keys) set by `preflight`.
   N is unchanged; N+1 validates fully, must be submitted and approved; its re-review set is
   all its claims. No new decision kind, table or migration change.
8. **Head and sources are checked before the first write; the head is re-verified at draft
   write** (closing r2 rulings A, B). `write_run_draft` takes the period's closed head as
   `predecessor_id` (`run_draft.py:210`, `:238`), so a successor that closed after preflight would
   silently become the predecessor; and traces (`repository.py:643`) and facts/selections
   (`pg_fact_store.py:163`) commit in their own transactions before it. So:
   - `run_draft.check_head(cursor, prior, period)` refuses unless the period's head equals the
     expected one (`Prior.rework.head` or `Prior.full_successor.head`). It is the hook's first act
     in both modes (a plain read, before any write), and `write_run_draft` calls it again on its
     own cursor right after `_require_closed`, under the WATCHLIST lock it already takes (`:197`),
     so a mismatched predecessor or heading is never written.
   - Rework runs only: `_check_sources`'s hash/cutoff predicate (`run_draft.py:427-445`) is
     factored into `check_blobs`, which `Gate.close` calls after the boundary holds and before
     pending traces are stored, on the run's in-memory sources: each rerun operand's capture
     blob (`_Binder.operand` already has `source.file_sha256`), each rerun claim's
     `source_sha256`, and every carried claim's input blobs (`Rework.blobs`, already derived by
     `rework.plan`), so a source a carried claim cites is checked before any write too. Allowed: the run's originals, the prior's entries and `Rework.blobs`
     (carried claims cite N's admitted captures); cutoff: the update's `source_cutoff`, with
     `--retrospective` publication times or first-seen otherwise. `_check_sources` still runs at
     draft write, now through `check_blobs`.
   A successor committed between the pre-write check and the draft write is refused at the draft
   write, after the rerun's writes: a stated residual of the class of the in-transaction
   `AS_KNOWN` and database-error refusals (PREP-3: retry = rerun; carried records are reused).
   No new lock, held connection or 0026 change; ordinary runs unchanged; `--full-successor` is
   today's full path plus `check_head`.
9. **PREP-5 reworks after comparator and config corrections only** (closing r1 2). With a source
   manifest the current XBRL digest comes from the approved binding (`api/cli.py:218`) and the
   registered bytes are read by reference (`api/source_admission.py:279`), so a rework run cannot
   swap one of the three registered current sources (XBRL, results PDF, transcript). Replacing one
   goes through fresh source intake (new approved binding, registration, locator) and
   `--full-successor`. No new code.

## Assumptions

- **A1** The rework run uses the same command as N's; a rerun with no correction is allowed and
  re-derives the rerun set to equal values (Sol r1: fine; the reapproval is explicit).
- **A2** Only run drafts are reworked (finding 6's three citation kinds).
- **A3** The operator corrects before the run: a config or mapping fix is a new
  `ApprovedIntakeContext` with the new `approved_config_sha256` and the same source bindings; a
  corrected comparator filing is a newly captured, evidence-ingested original the config points
  at. The run's three registered current sources are not re-registered for either (no fallback;
  Sol r1 A3). A corrected current source is outside selective rework (decision 9).
- **A4** Fact claim keys and trace operand keys digest equally (finding 6). Task 3's exact-set
  case fails if not; then the atom uses the measurement key fields instead, a local change.

## Open questions (orchestrator rules; none is the owner's financial judgment)

1. ~~Decision 4's reading of "only affected calculations are rerun"~~ — ruled acceptable by Sol
   r2, with the guarantee stated as in decision 4.
2. **Stated limitation: a rerun value that becomes unavailable (or the reverse)** changes a
   section scaffold and is refused by decision 5 (Sol r2 ruling: acceptable given recovery).
   Recovery: decision 7. No pilot drill needs it.
3. **PREP-6** reads `decisions.rejected_claims` as its rejected disposition and the review set of
   decision 6, which covers additions, replacements and presentation changes, since all of them
   can occur only on rerun lines (Sol r1 ruling); a `--full-successor` version is reviewed whole.

## Stated limitations

- Available↔unavailable rerun values: open question 2.
- **Registered current sources** are not replaceable by selective rework (decision 9): fresh
  intake + `--full-successor`.
- **Residual post-write refusals (closing r2 ruling A).** Head and sources are checked before the
  first write (decision 8). Still possible after the rerun's writes, inside the draft write: a
  successor committed by a concurrent ledger writer after the pre-write check (refused by the
  draft-write `check_head`), the in-transaction `AS_KNOWN` validation, and database errors. Such a
  refusal leaves committed what today's ordinary run leaves (finding 3): the rerun traces and
  operands (content-addressed, uncited, reused by hash) and the rerun roles' fact rows and
  canonical selections (no version cites them); carried claims write nothing. Recovery is a
  rerun (PREP-3). One transaction is not used: fact writes run SERIALIZABLE with bounded retry on
  their own connection (`pg_fact_store.py:163`), the draft READ COMMITTED (`run_draft.py:195`).
- **Operand bound is the writer's count.** `operand_count` closes a trace at the count
  `_insert_trace` writes. A trace inserted by hand (a role holding INSERT) with a count above its
  operands leaves free ordinals; no run cites such a trace, and `get_calculation_traces` fails its
  hash check if one is used.
- **Rejected claims are not in `decision_sha256`** (decision 2).

## Size (estimates, not measured)

| Task | src Δ | tests Δ | docs Δ |
|---|---|---|---|
| 1 `rejected_claims` and `operand_count` (0039, writer, store, lifecycle, CLI) | +45 (SQL ~32) | +75 | — |
| 2 Package inputs, rerun set and scaffolds (`rework.plan`, `rework.rejected`) | +90 | +60 | — |
| 3 Selective rework run with the before-write boundary, head and source checks; `--full-successor` | +180 (net, incl. moves) | +190 | — |
| 4 Corrected-filing drill, reapproval, source refusals (PILOT-11) | — | +135 | — |
| 5 Record the realisation | — | — | ±20 |

Total ≈ 283 Python + 32 SQL src, ≈ 460 test, down from r5's ≈ 305 + 72 and 505. Removed: the
`claim_rejections` table, its grants and transaction/time guards, `insert_claim_rejections`
(−45 SQL, −12 Python); `created_xid` and the cited-trace rule (−10 SQL); `hold`, the
`write_draft` split and the held connection (−26); and their tests — restore collisions,
savepoint, tombstone `created_xid`, two-connection operand race, rejection PROMOTE and runtime
privilege (covered by decisions' existing tests), lock probe, Task 4's record-creating race
(≈ −90). Added: `operand_count` and the `rejected_claims` check (+15 SQL), `check_head`,
`check_blobs` factoring and the binder's blob set (+21), and tests for the draft-write head
re-check and the source refusals (+45).
New files: `migrations/0039_rework.sql`,
`src/fundamentals/ledger/rework.py`, `tests/fundamentals/test_prep5_rework.py`. Implementer: Opus
for Tasks 1–4 (one worker, sequential), Sonnet for Task 5.

### Task 1: A `REQUEST_CHANGES` decision records the claims it rejects; stored traces cannot grow

Goal: `ledger decide REPORT_VERSION <id> REQUEST_CHANGES --claim <key> [--claim <key> …]` on an
`IN_REVIEW` version records the decision with `rejected_claims` set; a duplicate or unknown key,
or `--claim` on another kind or subject, is refused with nothing written. No operand row can be
added to a stored trace beyond the operands its writer stored, before or after a restore.

Files:
- Create: `migrations/0039_rework.sql`
- Modify: `src/fundamentals/evidence/repository_calc.py`, `src/fundamentals/evidence/repository.py`
  (`:702` passes `operand_count` unless `trace_params` carries it), `src/fundamentals/contracts/ledger.py`,
  `src/fundamentals/ledger/store.py`, `src/fundamentals/ledger/lifecycle.py`,
  `src/fundamentals/api/ledger_cli.py`
- Test: `tests/fundamentals/test_prep5_rework.py`

Interfaces:
- Consumes: `lifecycle.decide`, `lifecycle.append_decision`, `store.insert_decision`;
  `calc_sql.INSERT_TRACE`, `trace_params`.
- Produces: columns `eqos.decisions.rejected_claims text[]` and
  `eqos.calculation_traces.operand_count integer`; `DecisionRecord.rejected_claims:
  tuple[str, ...] | None = None`; keyword `rejected_claims: tuple[str, ...] = ()` on
  `store.insert_decision` (stored as a list, NULL when empty); keyword `claims: tuple[str, ...] =
  ()` on `lifecycle.decide`, passed through `append_decision`'s `**fields`; repeatable `--claim`
  on `ledger decide`.

Approach: The migration
1. `ALTER TABLE eqos.decisions ADD COLUMN rejected_claims text[]` with `CHECK (rejected_claims
   IS NULL OR (subject_kind = 'REPORT_VERSION' AND kind = 'REQUEST_CHANGES' AND
   cardinality(rejected_claims) > 0))`; a BEFORE INSERT trigger `check_rejected_claims` refusing
   (23514) when the array has a duplicate, or a key with no `numeric_claims` row of
   `(version_id = NEW.subject_id, claim_key = key)` (a NULL element never matches, so it is
   refused too). It fires after `check_decision` (alphabetical), so the version exists and the
   head is checked. Mutation, `refuse_after_promote` and grants are the table's own.
2. `ALTER TABLE eqos.calculation_traces ADD COLUMN operand_count integer CHECK (operand_count >=
   0)` (existing rows NULL: closed); a BEFORE INSERT trigger on `eqos.calculation_trace_operands`
   refusing (23514) unless `NEW.ordinal >= 0` and `NEW.ordinal < (SELECT operand_count FROM
   eqos.calculation_traces WHERE id = NEW.calculation_trace_id)` (NULL → refused). With the
   existing `UNIQUE (calculation_trace_id, ordinal)` and a writer that fills `0..n-1` in the
   trace's own transaction, every ordinal of a stored trace is taken: the operand set is fixed by
   rows, with no transaction ids or clocks, so a restore cannot reopen it. The 0029 mutation
   trigger already refuses changing `operand_count` (not among its tombstone columns).
The writer: `INSERT_TRACE` lists `_TRACE_COLUMNS` plus `operand_count`, and the insert passes
`len(trace.operands)` after `trace_params(trace)`; reads (`TRACES_BY_ID`) are unchanged.
`insert_decision` adds the column; `decide` passes `rejected_claims=claims`; `_decide` passes
`tuple(args.claim)`. The database is the only validator (its 23514 surfaces through the CLI's
existing `psycopg.Error` handling, `ledger_cli.py:148`). Check whether `test_pg_migrations.py`,
`pg/backup.py`, `pg/restore_check.py` list columns explicitly; add the new ones where they do.

Verification: `uv run pytest tests/fundamentals/test_prep5_rework.py -m "pg and retained" -k
"rejection or operand"`, then `uv run pytest tests/fundamentals/test_pg_migrations.py
tests/fundamentals/test_ledger_lifecycle.py tests/fundamentals/test_prep2b_traces.py`.

Tests (two parametrized refusal tests; the CLI happy path is in Tasks 3–4):
- Rejections, as owner (pattern of `test_ledger_lifecycle.py:492`), each refused with no new
  decision row: unknown key and duplicate key via the CLI; `--claim` with `REJECT`; a key that is
  a claim of another version (why: the set must name claims of the version under review).
  Assert SQLSTATE 23514 for the direct-insert cases (why: an ACL error would pass without the
  trigger). UPDATE of `rejected_claims` as the test migrator → `reject_mutation`'s refusal.
- Operand bound, as the runtime pool (the trace writer) after `put_calculation_trace` stored a
  two-operand trace with `operand_count = 2`, parametrized: ordinal 2 → 23514; ordinal 0 →
  23505 (unique); a trace row inserted by the migrator with `operand_count` NULL (a pre-0039
  row) → 23514 at ordinal 0 (why: Sol r2 3 and closing r2 5 — a cited trace must not take an
  operand, now or after a restore, which preserves the rows that close it). With
  `eqos.tombstone` set, an UPDATE of `operand_count` as the migrator → refused.

Dependencies: None.

Risks: low. The likeliest miss is a column list (`INSERT_TRACE` placeholders, backup/restore
lists).

### Task 2: A version's package and its rerun set are derived from verified rows

Goal: `rework.plan(cursor, repository, head)` returns `None` unless `head` is
`CHANGES_REQUESTED` with `rejected_claims`; otherwise a `Rework` holding N's claims by key, N's
lines per section (text and keys), the rerun and carried key sets (decision 3) and N's cited
blobs, and each non-heading section's scaffold (decision 5). Traces are read through
`EvidenceRepository.get_calculation_traces` (hash re-checked).
Unsupported shapes raise `RunDraftError` before grouping.

Files:
- Create: `src/fundamentals/ledger/rework.py`
- Test: `tests/fundamentals/test_prep5_rework.py`

Interfaces:
- Consumes: `decisions.rejected_claims`, `DecisionRecord.rejected_claims` (Task 1);
  `store.chain_head`, `store.read_version`, `version_status`;
  `EvidenceRepository.get_calculation_traces`, `get_interpretations`, `get_capture_refs`;
  `display.PLACEHOLDER`; `RunDraftError` from `run_traces`.
- Produces: `rejected(cursor: Cursor[Any], head: int) -> tuple[str, ...]` (the version's chain
  head's `rejected_claims`, sorted; empty unless that head is a `REQUEST_CHANGES` with them; used
  by `plan` and `preflight`); `Atom = tuple[str, str]`; `inputs(claims: Mapping[str, NumericClaim], traces:
  Mapping[int, StoredTrace], blobs: Mapping[int, str], facts: Mapping[int, str]) -> dict[str,
  frozenset[Atom]]` (pure: claim key → atoms; `blobs` interpretation id → capture blob, `facts`
  fact origin id → file sha256); `Rework` (frozen: `head: int`, `claims: Mapping[str,
  NumericClaim]`, `lines: Mapping[str, tuple[tuple[str, frozenset[str]], ...]]`, `rerun:
  frozenset[str]`, `carried: frozenset[str]`, `blobs: frozenset[str]`, `scaffolds: Mapping[str,
str]`); `scaffold(body: str) -> str` (pure: the body without lines holding a `PLACEHOLDER`);
`plan(cursor: Cursor[Any],
  repository: EvidenceRepository, head: int) -> Rework | None`. `rework.py` imports neither
  `run_draft` nor `cli`.

Approach: `plan` reads the rejected keys by `rejected` (`store.chain_head` of the version; a
`REQUEST_CHANGES` head is terminal, finding 13), `store.read_version(head)`, the cited traces
through the repository, their operand interpretations and capture blobs, and the cited fact rows'
`file_sha256` (one parameterized query); `inputs` refuses any operand whose `interpretation_id` is
`None` (nested trace or neither), any `COMPARISON`/`POLICY` citation and any claim with no record,
then builds atoms; affected and line closure per decision 3; lines from each section body (lines
holding a `PLACEHOLDER`, keys by it), scaffolds by `scaffold`. No caching, no model.

Verification: `uv run pytest tests/fundamentals/test_prep5_rework.py -k "inputs or plan"`.

Tests:
- `inputs` unit, parametrized over shapes (why: a silently dropped operand shrinks the rerun set
  and carries a stale claim): nested-trace operand, operand with neither id, `COMPARISON`,
  `POLICY`, unresolved claim → `RunDraftError`; a two-operand trace → both atoms.
- On a `Pilot` FY26_Q2 draft, submitted, then `REQUEST_CHANGES` via `lifecycle.decide(claims=…)`:
  parametrized exact rerun sets, keys named in the test — `cmp.revenue.qoq.prior` → its line's
  three keys; `fact.revenue` → decision 3's example set; a guidance key → itself.
- Package immutability: record `plan(N)` and `inputs`; a direct-SQL operand insert into one of
  N's cited traces is refused (Task 1's bound) and leaves them equal (why: N's package must not expand under an unchanged seal).

Dependencies: 1.

Risks: medium — A4; fix the atom, not the test.

### Task 3: A rework run derives only the rerun lines and refuses any other movement before writing

Goal: with N's head `CHANGES_REQUESTED` with claim rejections, `fundamentals run` writes N+1 whose
carried claims are N's claim rows' citations and lines, whose rerun lines are re-derived; only
rerun traces are computed and stored, only rerun fact roles written. A correction that moves a
carried value or line text, or adds an unexplained claim, is refused inside `before_commit` with
no trace, fact, selection or version written. Runs without claim rejections behave as today.

Files:
- Modify: `src/fundamentals/ledger/rework.py`, `src/fundamentals/ledger/run_traces.py`,
  `src/fundamentals/ledger/run_draft.py`, `src/fundamentals/api/pipeline.py`,
  `src/fundamentals/api/cli.py`
- Test: `tests/fundamentals/test_prep5_rework.py`

Interfaces:
- Consumes: `rework.plan`, `Rework` (Task 2); `bind_computed`, `_Binder`; `preflight`,
  `write_run_draft`, `_results`, `_quote`, `_guided`, `_status`, `_shown`; `run_pipeline`.
- Produces: `Prior.rework: Rework | None` (set by `preflight` from the period's head);
  `Rework.gate(body: Callable[[str, Sequence[str]], str], admit: Callable[[frozenset[str]],
  None]) -> Gate` with `Gate.line(section: str,
  text: str, claims: tuple[NumericClaim, ...]) -> tuple[NumericClaim, ...] | None` (N's claims
  for a carried line, `None` for a rerun line, `()` for a key-less line, `RunDraftError`
  otherwise; every line is recorded in order) and `Gate.close(blobs: frozenset[str]) -> None`
  (decision 5's after-all checks: carried lines all seen, `scaffold(body(section, recorded
  lines))` equals N's per section; then `admit(blobs | the rerun claims' source_sha256s | Rework.blobs)`,
  decision 8); `run_draft.section_body(key, lines) -> str` (factored out of `_sections`, used by
  both); `--full-successor` on `fundamentals run`; `run_draft.Successor` (frozen: `head: int`,
  `rejected: tuple[str, ...]`) and `Prior.full_successor: Successor | None` (decisions 7–8,
  read by `_sections` for the heading line and by `check_head` for the expected head);
  `run_draft.check_head(cursor: Cursor[Any], prior: Prior, period: str) -> None` and
  `run_draft.check_blobs(cursor: Cursor[Any], blobs: Set[str], *, allowed: Set[str], cutoff:
  datetime, retrospective: Retrospective | None, catalog: SourceCatalog) -> None` (decision 8;
  `_check_sources` collects its blobs and calls `check_blobs`); `_Binder.blobs: set[str]` (each
  bound operand's `source.file_sha256`); `run_traces.Carry` (a `Protocol` with `line` and
  `close`) and keyword `carry: Carry | None = None` on `bind_computed`, which calls
  `carry.close(frozenset(binder.blobs))`; `run_draft.gate_lines(cursor, gate, update, guidance, prior,
  catalog) -> None` (results and guidance lines through the gate); keyword `skip_roles:
  frozenset[FactRole] = frozenset()` on `run_pipeline`; `before_commit` now receives
  `(update, guidance_claims)`; `_shown` moves to `run_traces` (it renders a `Line`).

Approach: In `bind_computed`, operands become zero-argument cached lookups and each changes or
calculations line is built first as a skeleton (the uncited `_valued` claims `figure`/`trace`
return, with no lookup or `conclude`); with `carry`, `carry.line(section, _shown(skeleton),
claims)` decides: carried → the line with N's claims; rerun → the line is bound as today. Key-less
lines (unavailable) go through `carry.line` too, so the gate records every line. `carry.close()`
runs before `put_calculation_trace`, so pending traces are stored only after the whole boundary
holds. `run_draft` factors the results and guidance line builders out of `write_run_draft` (text
plus claim; a results claim is uncited when its role has no fact ref) so `gate_lines` and
`write_run_draft` share them; `write_run_draft` substitutes N's claim for a carried key, calls
`check_head` after `_require_closed` (under its existing WATCHLIST lock) when an expected head is
set, and `_check_sources` also allows `Prior.rework.blobs` (carried claims cite N's captures,
already admitted for N; the full `AS_KNOWN` check re-resolves them). The pipeline passes
guidance claims to `before_commit` and skips step 10's writes (canonical and PDF-confirm) for
`skip_roles`. In `cli`, when `prior.rework` or `prior.full_successor` is set, the hook's first
call is `check_head` on a pooled cursor (plain read), before any write. The rework hook then
builds `gate = prior.rework.gate(run_draft.section_body, admit)`, where `admit` calls
`check_blobs` with the run's `xbrl`/`pdfs`, the prior's entries and `Rework.blobs` as allowed,
the update's `source_cutoff` and `retrospective`; calls `gate_lines`, then
`bind_computed(carry=gate)`; `skip_roles` = roles whose `fact.<role>` key is carried. Otherwise
the run is today's.
`--full-successor` (decision 7): before the non-PostgreSQL return (`api/cli.py:277`), a
`--full-successor` run on a SQLite store is refused (`RunDraftError`) before the pipeline runs;
`preflight` refuses it unless the head is `CHANGES_REQUESTED` with claim rejections, then leaves
`Prior.rework = None` and sets `Prior.full_successor = Successor(head, rework.rejected(...))`,
which `_sections` writes as one heading line (`full rework requested`, N, rejected keys) and
`check_head` checks as the expected head (decision 8); nothing else changes (today's full
path).

Verification: `uv run pytest tests/fundamentals/test_prep5_rework.py -m "pg and retained" -k
"rework or boundary"`, then `uv run pytest tests/fundamentals/test_prep2b_run_draft.py
tests/fundamentals/test_prep2b_traces.py tests/fundamentals/test_prep3_resume.py` (ordinary runs
and resume unchanged), then the full gate.

Tests (spies by `monkeypatch` on `run_traces.conclude`, `_Binder.operand`,
`EvidenceRepository.put_calculation_trace`, `PgFactStore.put`, `PgFactStore.select_canonical`):
- Rerun with no correction, rejecting `fact.revenue`: N+1 written; `conclude` and
  `put_calculation_trace` ran exactly for the rerun traces (revenue QoQ/YoY abs and pct, the gap),
  `_Binder.operand` exactly for the operand keys named in the test (current revenue, the two
  revenue priors, current income), `put`/`select_canonical` only for the revenue role; every
  carried claim row equals N's including citation ids and `unresolved = False`, every carried
  line's text equals N's (why: proves the unaffected calculations did not execute, not merely that
  they deduplicated; and that an unchanged skeleton, unresolved by construction, is not refused —
  Sol r2 1).
- Guidance-only rework, rejecting the cables guidance key with no correction: N+1 written;
  zero `_Binder.operand`, `conclude`, `put_calculation_trace`, `put` and `select_canonical` calls
  (why: no rerun line has a computed or fact claim, so nothing may bind or write).
- Boundary refusals, parametrized (rejected key, correction → key named); each rejection's
  `ledger decide` is asserted to succeed first (why: a refused rejection would leave a head
  without claim rejections and test today's full run): `fact.profit_before_tax` rejected,
  cables guidance `label` changed → the cables key (presentation drift on a carried line, with a
  fact role in the rerun set so a write would otherwise follow); a guidance key rejected, a copy
  of the cables rule under a new metric added → the new key (unexplained addition); a guidance
  key rejected, `run_draft.INTROS[CHANGES]` monkeypatched to "(prior − current)" → the changes
  section (why: the intro defines the sign of every carried change; Sol r2 4). The numeric
  drift case needs Task 4's synthetic filing and lives there. Each: `RunDraftError`; zero
  `put`, `select_canonical` and
  `put_calculation_trace` calls; counts of `fact_rows`, `fact_selections`, `calculation_traces`,
  `calculation_trace_operands`, `report_versions`, `numeric_claims` unchanged (why: a refusal
  after writes would leave a canonical selection and traces no version cites).
- Supplementary: cables guidance rejected, its `label` changed → N+1 differs from N only in that
  claim's `metric_label` and its line.
- Full successor (decision 7): after the `fact.profit_before_tax`/cables-label refusal, the
  same run with
  `--full-successor` → N+1 with the changed label, the heading line `full rework requested`
  naming N and the rejected keys, `conclude` for every trace; N+1 validates in full, is
  submitted and approved; N's status and sealed digest unchanged. `--full-successor` on a head
  without claim rejections → `RunDraftError`. `--full-successor` with a SQLite store config →
  `RunDraftError` before the pipeline; the SQLite store holds no fact row (why: `cli.py:277`
  would otherwise run the full pipeline with no eligibility check).
- Head re-verification, parametrized over selective rework (rejecting `fact.revenue`) and
  `--full-successor` (why: Sol r3 — a stale preflight would otherwise write N+2 under a heading
  naming N), with a competing successor N+1 written and closed (submitted, `REQUEST_CHANGES`):
  (a) before the hook → `RunDraftError` from the pre-write check; zero `put_calculation_trace`,
  `put` and `select_canonical` calls; zero new `report_versions`, `numeric_claims`,
  `calculation_traces`, `calculation_trace_operands`, `fact_rows`, `fact_selections` rows;
  (b) from inside the first `put_calculation_trace` call (after the pre-write check) →
  `RunDraftError` from the draft-write check; zero new `report_versions` and `numeric_claims`
  (why: closing r2 ruling A — the residual window leaves only rerun writes, never a version on
  the wrong predecessor).

Dependencies: 2.

Risks: medium-high. The skeleton/bind split must keep `test_prep2b_traces.py` green; the line
closure must make every line all-carried or all-rerun, else the mixed-line refusal fires on an
honest correction (the exact-set tests of Task 2 catch it).

### Task 4: A corrected filing reworks its dependent claims into an approved v(N+1) (PILOT-11)

Goal (PILOT-11 second clause, B-14): with N's head `CHANGES_REQUESTED` naming
`cmp.revenue.qoq.prior`, a re-run on a corrected QoQ comparator filing that changes only FY26_Q1
revenue writes N+1 (`predecessor_id = N`, version number + 1) in which the rerun line carries the
independently computed new values against the new filing, every other claim keeps N's citations
(the other QoQ priors still cite the old filing), only the rerun calculations executed; N+1
validates `AS_KNOWN`, submits and is approved; N's status, sealed digest, content hash, package
inputs and rerun set are unchanged.

Files:
- Test: `tests/fundamentals/test_prep5_rework.py` (and, if needed, a small helper in
  `tests/fundamentals/prep2b_support.py`)

Interfaces:
- Consumes: Tasks 1–3; `prep2b_support.Pilot`, `Ingest` (`evidence_support`),
  `retained_intake_from_manifest`, `published_package`, `parse_instance`, `RUN_PERCENT_PLACES`,
  `ApprovedIntakeContext`, `lifecycle.submit`, `version_status`, `store.sealed_digest`.
- Produces: `test_corrected_filing_reworks_only_dependent_claims` (PILOT-11 evidence).

Approach, in order:
1. `pilot.run("FY26_Q2")` → N; submit. Record N's sealed digest, content hash, `inputs`, and
   counts of `calculation_traces`, `fact_rows`, `fact_selections`.
2. `main(["ledger", "decide", "REPORT_VERSION", N, "REQUEST_CHANGES", "--claim",
   "cmp.revenue.qoq.prior"])` as owner, ruling on stdin; assert exit 0 and the decision's
   `rejected_claims == ("cmp.revenue.qoq.prior",)`. Only now record the baseline
   `plan(N).rerun` (it needs the rejection; Sol r3 note).
3. Synthetic corrected filing under `tmp_path`: the FY26_Q1 comparator's bytes with the one
   consolidated FY26_Q1 `RevenueFromOperations` fact raised by Δ = ₹100 crore; assert exactly one
   substitution and, by `parse_instance`, exactly one observation changed. Write it under the
   temporary input root's `nse/` directory. A test copy of the retrieval manifest appends one
   entry for it under a distinct kind, `xbrl-consolidated-comparator-corrected` (Sol r2 verified:
   reusing the original quarter/kind fails intake with "2 entries … expected 1"), with source id
   `nse-indas-xbrl-consolidated` and the original FY26_Q1 filing's publication time (a
   restatement published by the cutoff); evidence-ingest it through
   `retained_intake_from_manifest` on that copy, selecting that kind, so its capture is
   first-party, retained and interpreted under `RUN_CONTEXT`; `published_package(...,
   quarter=None)` keeps both hashes. Repin the copy's sha256 in the Pilot's tmp
   `config/ledger_import.yaml` (the pin `_retrospective` reads). No production schema change.
4. Correct: the test's FY26_Q2 config copy points `comparators.qoq` at the synthetic file (path,
   sha256); corrected context = `dataclasses.replace(context, approved_config_sha256=…)` (A3).
5. Re-run with `run_command(parse_args([*argv, "--retrospective", <manifest copy>]),
   intake_context=corrected)` under the Task 3 spies → N+1.
6. Expected values derived in the test from N's carried current revenue C and prior P:
   P′ = P + 100; abs = C − P′; pct = (C − P′) / P′ × 100 rounded half-even to
   `RUN_PERCENT_PLACES`; assert they differ from N's. Assert N+1's three rerun claims equal them
   and cite the synthetic filing's interpretation and new traces; `conclude` ran exactly twice
   (abs, pct); `_Binder.operand` exactly for current revenue and the corrected QoQ prior; no
   `put`/`select_canonical`; every other claim row and line equals N's; the
   other QoQ prior figures cite the old filing (why: finding 4 — a new filing must not force
   unaffected claims to rebind).
7. N: status `CHANGES_REQUESTED`; sealed digest, content hash, `inputs` equal step 1's and
   `plan(N).rerun` equals step 2's.
8. `Pilot.approve(N+1)` → `APPROVED`; N unchanged.

Numeric drift refusal, same setup on a fresh `Pilot`: reject `fact.profit_before_tax` instead
(asserting the decision succeeded), run on the synthetic comparator → `RunDraftError` naming
`cmp.revenue.qoq.prior` (a carried value moved), with Task 3's zero-write assertions (why: an
input changed outside the rejected claims' reach; carrying N's value would publish a stale one,
taking the new one would bypass review). The way forward, `--full-successor`, is covered in Task
3.

Source refusals before any write, parametrized, same setup as steps 1–4 on a fresh `Pilot`
(why: closing r2 3 — `_check_sources` at draft write ran after the rerun's writes): the manifest
copy gives the synthetic filing a publication time after the source cutoff → `RunDraftError`
naming the cutoff; `run_draft.check_blobs` wrapped to drop the synthetic hash from `allowed` →
`RunDraftError` naming the package; the manifest copy includes the corrected comparator but
omits the original comparator that carried claims still cite → `RunDraftError` naming that
carried source (closing r3 1). Each with Task 3's zero-write assertions, although the
unraced run (step 5) adds two traces with their operands.

Verification: `uv run pytest tests/fundamentals/test_prep5_rework.py -m "pg and retained" -k
corrected_filing`, then the full gate.

Dependencies: 3.

Risks: medium — test plumbing (the manifest path is Sol-verified). If intake still refuses the
added entry, stop and report; do not change the drill to a non-filing correction.

### Task 5: Record the realisation

Goal: the docs say what an evidence package is and that the selective rework path exists.

Files:
- Modify: `docs/backend-roadmap.md` (PREP-5 row → done with the test file, after Sol phase
  approval), `docs/blueprint/source-of-truth-matrix.md` (Evidence packages row: the version's
  cited records, identity (report, version number), integrity `sealed_digest` plus bounded operand
  membership (`operand_count`), writer `fundamentals run`; Ledger row: `decisions.rejected_claims`
  (0039), `--claim`; Gap 1:
  resolved by PREP-5, frozen inputs remain PREP-7),
  `docs/specs/2026-10-12-report-ledger-memory-and-data-lifecycle.md` (§1 entities: one line on a
  `REQUEST_CHANGES` decision's rejected claims, "amended 2026-10-18, PREP-5"), `CONTEXT.md` (Evidence package: one sentence).

Approach: Sonnet; docs only.

Verification: `.claude/project/verification.md` structural checks; every linked path exists.

Dependencies: 4.

Risks: low.

## How PREP-5 meets each B-14 clause

| B-14 clause | Where |
|---|---|
| A rejected claim triggers the correct invalidation cascade | Decisions 2, 3; Task 2 exact sets |
| Evidence package v(N+1) is created | Decision 1; Task 4 (version N+1, chain position, cited records) |
| Only affected calculations/claims are rerun | Decisions 4, 5; Task 3 call-level spies and boundary refusals; Task 4 step 6 |
| Prior package remains immutable | Decision 1; Task 1 `operand_count` bound tests (incl. a pre-0039 row); Task 2 expansion test; Task 3 full successor; Task 4 step 7 |
| Partial revalidation and reapproval succeed | Decision 6; Task 4 steps 6, 8 |

## Interaction with open beads (Sol r1 rulings)

- `eqos-4j2.21` (no `ledger submit` CLI): stays an accepted limitation; N+1 is submitted by
  `lifecycle.submit`.
- `eqos-4j2.24` (fact admission): unresolved by PREP-5. PREP-5 moves the rework's refusal before
  fact writes; when admission is wired into the run it must also refuse before writes, or late
  refusal returns. PREP-5 does not close or narrow it.
- `eqos-4j2.25` (memory writes): not completed by approving a report; PREP-5 writes no memory.
- `eqos-4j2.27` (PILOT-4 citation contract): independent; PREP-5 neither depends on nor implies
  its closure. If it changes the citation kinds a run emits, `rework.inputs` refuses the new
  kind until it is added.

## Self-review

- Coverage: every B-14 clause maps to a task; PILOT-11's second clause is Task 4.
- Placeholders: none; claim keys are named and read from the stored draft.
- Names: `rejected_claims`, `operand_count`, `claims=`, `--claim`, `Atom`, `inputs`, `Rework`,
  `plan`, `scaffold`, `Gate`, `Carry`, `gate_lines`, `section_body`, `carry=`, `skip_roles=`,
  `--full-successor`, `Successor`, `Prior.full_successor`, `rejected`, `check_head`,
  `check_blobs`, `_Binder.blobs` are defined once and consumed as defined.
- Gaps named: Stated limitations (open question 2, decision 9, the residual post-write refusals,
  the writer-count operand bound, `decision_sha256`); the comparator drill exercises no current-filing fact rewrite
  (Task 3's `fact.revenue` case covers the fact-role rerun path).

## r1 findings → resolution

| # | Sol r1 finding | Resolution |
|---|---|---|
| 1 | Full recomputation is not selective rerun | Decision 4: carried claims reuse N's records, only rerun lines are bound; Task 3 call-level spies (`conclude`, `put_calculation_trace`, `operand`, fact `put`/`select_canonical`); full `AS_KNOWN` kept (decision 6); boundary put to Sol as open question 1 |
| 2 | Seal does not freeze operand membership; direct SQL bypasses digest check | 0039 trigger refuses operands on a cited trace (Task 1); `plan` reads traces through the hash-checking repository (Task 2); expansion test (Task 2) |
| 3 | Unrestricted new keys bypass the boundary | Decision 5: new keys only on rerun lines; all-new lines refused; review set includes them (decision 6); Task 3 addition test |
| 4 | Corrected capture defeats selective rework | Carried claims keep N's citations, so a new blob rebinds only rerun lines; Task 4 synthetic single-measurement comparator with known dependents |
| 5 | Label drill cannot prove the numeric cascade; bounds claim wrong | Finding 9 corrected (verified at `contracts/ledger.py:281` and `claim_check`); Task 4 value-changing drill with independently derived values; label test kept as supplementary (Task 3) |
| 6 | Refusal after fact/trace/selection writes | Decision 5: the whole boundary runs in `before_commit`, `close()` before trace storage, fact writes only for rerun roles; Task 3 refusals assert zero write calls and unchanged counts incl. `fact_selections` |
| 7 | Equal claim rows do not preserve rendered meaning | Carried lines must equal N's text and are N's text; label/placeholder drift on a carried line is refused (Task 3); only the heading may differ |
| 8 | SQL tests do not reach the triggers | Task 1: authorized-role tests asserting 23514, runtime denial separately, mutation via the migrator incl. DELETE/TRUNCATE, wrong-kind and wrong-version |
| 9 | 0039 omits PROMOTE-last-write | `refuse_after_promote` on `claim_rejections` and an ordering test (Task 1) |
| 10 | Inner joins drop unsupported operands | `inputs` checks each operand object and refuses before grouping; parametrized unit test (Task 2) |

## r2 findings → resolution

| # | Sol r2 finding | Resolution |
|---|---|---|
| 1 | Unchanged skeletons differ from N in `unresolved` | Finding 12; decision 5 excludes binding state (`citation`, `unresolved`, a quote's `quote`/`anchor`), requires N's claim resolved and reuses its row whole; Task 3 no-correction test asserts `unresolved = False` on carried rows |
| 2 | Refused selective rework has no recovery | Finding 13; decision 7 recovery (r3 ruling: `--full-successor` only; the r2 replay bridge was removed); Task 3 full-successor test |
| 3 | Operand guard races the first citation | Finding 5; Task 1: operands insertable only in the trace's creation transaction via `calculation_traces.created_xid` (`xmin` rejected: purge and savepoints), matching `_insert_trace`; "already cited" check dropped; two-connection race test |
| 4 | Section intros escape the boundary | Finding 7; decision 5 compares each non-heading section's scaffold (heading, intro, key-less lines); `scaffold`, `section_body`, `Rework.scaffolds`; Task 3 changes-intro drift test while a guidance claim is rejected |
| — | Rulings and manifest | Decision 4 states the selectivity guarantee precisely; open question 2 states the available↔unavailable limitation with decision 7's recovery; Task 4 step 3 uses kind `xbrl-consolidated-comparator-corrected` under the temporary input root's `nse/` |

## r3 findings → resolution

| # | Sol r3 finding / ruling | Resolution |
|---|---|---|
| 1 | `--full-successor` drops the locked-head check; a stale preflight writes N+2 under a heading naming N | Decision 8: under the existing lock, the period's closed head (`run_draft.py:210`, used as `predecessor_id` at `:238`) must equal `Prior.rework.head` or `Prior.full_successor`, else refused; Task 3 approach and parametrized race test (competing successor closed between preflight and writing → refused, nothing written) |
| — | Recovery ruling: keep only `--full-successor` | Replay bridge removed (decision 7, Task 4, open question 4, size, B-14 table); sealed reason now `full rework requested` (N and rejected keys kept); Task 3 full-successor test covers full validation, submission, approval and N's unchanged seal |
| — | Notes | Task 1 savepoint-insertion and retention-tombstone `created_xid` tests; Task 4 records baseline `plan(N).rerun` after step 2 |

## Closing r1 findings → resolution

| # | Sol closing r1 finding / ruling | Resolution |
|---|---|---|
| 1 | Locked-head refusal after committed trace/fact writes (P1) | Fallback branch of the ruling (measured below). Decision 8: one held READ COMMITTED transaction whose first act in `before_commit`, before any write, takes the WATCHLIST and prior subject locks and checks the expected head; the draft is written on it (`hold`, `write_draft`). Residual post-write refusals documented in Stated limitations. Tests: Task 3 race asserts zero write calls and unchanged trace/operand/fact/selection/version/claim rows, plus a lock probe during trace storage; Task 4 record-creating race |
| 2 | A3 cannot replace a registered current source | Scope limited (ruling): decision 9, A3, Stated limitations; replacement = fresh intake + `--full-successor`. No code |
| 3 | Restored txids reopen insertion | Task 1: the cited-trace refusal is kept alongside the creation-transaction rule for operands; rejections also need `created_at = eqos.store_now()` (store clock strictly increasing, sequence restored); restore-collision refusal test. Uncited restored traces and the 0012 guards: Stated limitations |
| 4 | Drills name `fact.pbt` | `fact.profit_before_tax` (`contracts/role.py:14`, `run_draft.py:344`) in Task 3 refusals and full successor and Task 4 drift; each rejection decision asserted to succeed first |
| 5 | `_Binder.operand` spied, not asserted | Task 3: exact operand-key set for the `fact.revenue` rerun; guidance-only rework asserts zero `operand`, `conclude`, trace-storage and fact-write calls; Task 4 step 6 operand set |
| 6 | `--full-successor` bypassed on SQLite | Task 3: refused before `api/cli.py:277`'s non-PostgreSQL return; test asserts refusal before the pipeline and no SQLite fact row |
| 7 | Full-successor interface drops heading data | `Successor` (head, rejected keys) on `Prior.full_successor`, built by `preflight` via `rework.rejected`; `_sections` reads it (no cursor), `hold` checks `head` |

Closing r1 finding 1 was resolved by the held-lock fallback in r5; r6 replaces it (closing r2).

## Closing r2 findings → resolution

| # | Sol closing r2 finding / ruling | Resolution |
|---|---|---|
| 1 | Held prior lock + separately transacted fact writes form a lock cycle (P1) | Ruling A: held transaction, `hold`, `write_draft`, held connection and the WATCHLIST/prior lock holding removed. Decision 8: `check_head` before the first write (plain read) and again in `write_run_draft` under its existing lock, both modes. Concurrent successor in between: stated residual. Task 3 head re-verification test (a) before the hook, (b) after the pre-write check |
| 2 | 0026 does not lock every version insert (P1) | Moot under ruling A: no lock is relied on to exclude version inserts; the draft-write `check_head` refuses a wrong predecessor whoever inserted it. No 0026 change |
| 3 | `_check_sources` can run before the first write (P2) | Ruling B: predicate factored into `check_blobs`; called by `Gate.close` after the boundary, before trace storage, on in-memory operand blobs and rerun claim sources (decision 8). Task 4 package and cutoff refusals with zero writes |
| 4 | Rejection guard names nonexistent `created_at` (P2) | Ruling C: `claim_rejections` and its transaction/time guards removed; rejections are `decisions.rejected_claims` (decision 2, Task 1) — no guard needed |
| 5 | Timestamp predicate not restore-safe (P2) | Ruling C: `created_xid`, the `txid_current()`/`store_now()` predicates and the cited-trace rule removed. `calculation_traces.operand_count` + an operand BEFORE INSERT bound (`0 <= ordinal < operand_count`, NULL refuses) with the existing unique ordinal; state is in rows, so restore-safe and race-free (Task 1) |
| — | Implementer note (collision tests via migrator; disable named trigger) | Collision tests removed; Task 1 uses the migrator only to insert a NULL-count trace row and to attempt UPDATEs, no trigger disabled |

Rows of earlier tables naming `claim_rejections`, `created_xid`, `hold`/`write_draft`, the
cited-trace rule or the lock probe are superseded by this table.

## Closing r3 findings → resolution

| # | Finding | Resolution |
|---|---|---|
| 1 | Carried sources bypass the early cutoff check (P2) | `Gate.close` admits carried claims' input blobs (`Rework.blobs`) with the rerun sources (decision 8); Task 4 adds the omitted-original-comparator manifest case with zero-write assertions. Implementer note: Task 1 lists `repository.py:702`. |
