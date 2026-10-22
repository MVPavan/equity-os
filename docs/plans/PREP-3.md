# PREP-3 Implementation Plan — the per-quarter workflow resumes after an interruption

**Origin:** `docs/backend-roadmap.md` §3 row PREP-3 ("Resumable workflow with defined states,
retries and failure states (register B-01)"; done when "Interrupt-and-resume test per step") and
§4 PILOT-11 ("One step is interrupted and resumes without duplication"). Register B-01
acceptance: "State definitions, allowed transitions, failure states, immutable step outputs,
idempotent retries, and resume behavior documented and tested". Approved 2026-10-18: Sol r1 REVISE (11),
r2 REVISE (2), r3 **APPROVE** (GPT-6.1 Sol); responses in the last sections.
**Goal:** every step of an Apar quarter's PostgreSQL workflow (register-sources, ingest, run,
submit, approve, export), interrupted at each of its commit boundaries and then re-run, reuses
what committed, adds exactly what the interrupted attempt had left to add, and ends in the state
an uninterrupted attempt reaches. The quarter's state, transitions and failure states are
defined here over rows that already exist.
**Out of scope:**
- A workflow engine, run record, transition chain or attempt table (decision 1); no migration.
- The rework path (REJECT → only affected claims rerun → v(N+1)): PREP-5.
- Memory staging and promotion (decision 5); the advisory `ledger check`/`lifecycle.validate`.
- A `ledger submit` CLI (decision 5). New automatic retries (decision 3); the existing bounded
  retries stay as they are.
- Running the pilot itself (PREP-7/PREP-8); PILOT-11's other two clauses (PREP-5, PREP-6).
**Constraints:**
- Every task leaves `uv run pytest tests/fundamentals`, `uv run mypy --strict src`, `uv run ruff
  check src tests` green. Tests on `eqos_test_*` only (markers `pg`, `retained`).
- No migration edits or additions; nothing under `data/` edited.
- Do not touch hashed extractors, `evidence/vendor_ingest.py`, `compare/resolve_loader.py`,
  `pg/legacy_import.py`, `contracts/source_catalog.py`, frozen `config/aparinds-fy26-q4.yaml`.
- Facts append-only, nothing backdated (invariants 9, 13); a resumed step reuses committed rows,
  it never rewrites them, and nothing it stamps reuses an earlier attempt's instant.
- Owner 2026-10-14: smallest thing that meets the acceptance; tests over machinery.
- **Product code:** none is planned. That is a prediction the tests check, not a claim: the
  findings below say every boundary resumes, finding 2's orphan is handled by policy, and any
  red test is a real defect fixed at its source in that task (systematic-debugging), never by a
  new layer.

## Findings that shape the design (verified in code)

The per-quarter workflow is six operator steps, each a sequence of committed units:

| # | Step (entry point) | Commit boundaries, in order | Re-run behaviour today |
|---|---|---|---|
| S1 | `fundamentals register-sources` → `api/source_intake.register_sources` | per role (XBRL, results PDF, transcript): `installed.json` then `registration.json` (`store/source_intake_store._resolve`); then the locator manifest, published no-clobber; then the CLI returns 0 | A role with a receipt returns it unchanged; an install without a receipt is recovered (`test_source_intake_store.py:263`). A retry after the locator is published refuses: "refusing to overwrite locator manifest" |
| S2 | `fundamentals evidence ingest` → `evidence/first_party_ingest.ingest_first_party` | per member (XBRL, then PDF): capture file published (`stage_retained_member`), then its `capture_refs` row (`_registered`: one transaction); per member its generation (`MemberGeneration.written` → `put_generation`, one transaction); per usable member its interpretations (`put_interpretations`); the package (`put_package`); segment members (`put_segment_members`); package-owned PDF attempts for unlocated families and acquisition-failure attempts (`put_attempts`) | Reuse levels 1–3 (module docstring); `put_package` returns an existing package; an interpretation conflict retries up to `MAX_INTERPRETATION_RETRIES` then raises `IngestError`. **Gap:** the capture file is published before its row commits (finding 2) |
| S3a | Run: preflight (`ledger/run_draft.preflight`) | none (read-only) | Refuses an open period head |
| S3b | Run: admission, extraction, gates, render (`api/pipeline._run_admitted`, steps up to the `before_commit` hook) | none — temp files only | Recomputed |
| S3c | Run: computed traces (`run_traces.bind_computed`, called by the `before_commit` hook that `api/cli.run_command` passes to `run_pipeline`; the hook runs after the render and before any fact is stored) | one transaction per `put_calculation_trace` | Content-hashed: an equal trace returns its id |
| S3d | Run: fact writes (`pipeline._run_admitted` step 10, after the hook) | one SERIALIZABLE transaction per `put` and per `select_canonical` (`store/pg_fact_store.run_serializable`, which retries serialisation failures and raises `FactStoreRetryError` when exhausted) | `put` returns the existing row for an equal (content identity, value hash), which exclude `run_id` and times; an already-current selection is `unchanged` |
| S3e | Run: draft (`run_draft.write_run_draft`'s one READ COMMITTED transaction) | report row, version, claims, in-transaction `AS_KNOWN` check — atomic | Afterwards the open head makes a re-run refuse in preflight |
| S3f | Run: emit (`api/cli.main`, after `run_command` returns) | `--out-json` (`write_bytes_no_clobber`), then `--out` (`write_text`, overwrites) | Lost or half-written if the process dies after S3e (decision 2) |
| S4 | Submit (`lifecycle.submit`; Python only) | one transaction | A repeat after commit refuses (`append_decision` / `TRANSITIONS`) |
| S5 | Approve (`fundamentals ledger decide` → `lifecycle.decide`) | one transaction: its validation row + decision | A repeat after commit refuses |
| S6 | Export (`fundamentals ledger export`) | files only. `--stock`: hash-checks every narrative, refuses any existing destination before writing, then writes file by file. Single `--version-id --out`: overwrites (`write_bytes`) | Database untouched; stock re-export needs a fresh directory |

Consequences:
1. **An interrupted S3 attempt does not duplicate.** The run persists in the order traces (S3c) → facts and selections (S3d) → draft (S3e). S3c and S3d leave committed rows that the
   re-run's `put` / `put_calculation_trace` return; S3e is atomic. This is not "re-running S3
   never adds a version": a closed head deliberately gets a successor (state table).
2. **Ingest can orphan one file** (decision 6): `_registered` publishes the capture through the
   snapshot store, then inserts its row in a transaction. An interruption between the two rolls
   the row back and leaves the capture directory (`record.json` plus a hard link to the shared
   content-addressed blob). The retry's `find` matches only registered captures, so it stages a
   new capture with a fresh store-clock instant (a new `capture_id`, `snapshot.derive_capture_id`)
   and registers that one.
3. **Other leftovers, none a record:** S3c traces with no version or facts (reused by the next run); S3f's
   files (decision 2); a partial S6 directory.
4. **Review states already are a derived state machine.** `VersionStatus` is "derived from the
   decision log and never stored (P1)" (`contracts/ledger.py`) with a closed transition table
   (`lifecycle.TRANSITIONS`). Run eligibility is exactly `preflight`'s checks.
5. `docs/specs/equity-os-s14-earnings-review-workflow-rework.md` is an unreviewed DRAFT
   specifying a `RunRecord`, digest-chained transitions and `StepAttempt`s. B-01's wording does
   not require those records; the roadmap cites B-01, not S14.
6. The pilot has no CLI path to `submit` (PREP-2b excluded it): S4 runs from Python, as
   `lifecycle.submit(runtime_pool, version_id, catalog=…, snapshots=…)` (the call
   `prep2b_support.Pilot.approve` makes). The pilot is therefore CLI plus one documented Python
   call, not CLI-only.

## Decisions (rulings recorded)

1. **Workflow state: derived from existing rows** (accepted r1). The state table below; no new
   table, migration or state code. S14 gets a status line: "Phase 0.5 realisation of B-01 is
   `docs/plans/PREP-3.md`; S14's run record, transition chain and attempt records are deferred
   until a §8 trigger fires." Rejected: S14 as written (migration, engine, S14-T01…T13) — it
   stores state the ledger already derives.
2. **Crash after the draft commits: recover by submit + export** (accepted r1). The version is
   the record and Markdown a generated view (CONTEXT "Source-of-truth hierarchy"). The quarter
   reads `DRAFT`; the operator submits it (decision 1 route), approves it, and `ledger export`
   renders its narrative. No adopt-and-re-emit code. Recoverable: the version, its claims, facts,
   selections, traces, and its narrative via export (hash-checked against `content_hash`).
   Abandoned: the run's `--out-json` dump unless it was written before the interruption (it is
   not reproducible, because the re-run refuses), and the run's own `--out` Markdown (replaced by
   the export). The pilot manifest must not depend on the run's JSON.
3. **Retries are manual** (accepted r1): a retry is re-running the same command. No new
   automatic retry. The existing bounded ones stay: `run_serializable`'s serialisation retry and
   ingest's interpretation-conflict retry.
4. **Interruption is in-process and scoped** (accepted r1). A test wrapper raises
   `Interrupted(BaseException)` before or after the n-th call at a boundary, so no
   `except Exception` swallows it and psycopg rolls back any open transaction. Each wrapper is
   installed inside its own `monkeypatch.context()` that ends right after the interrupted call;
   the fixture's monkeypatch (the test-database env `Pilot` sets, which `PgSettings()` reads on
   every CLI call, and the credential directory) is never undone. Commit atomicity under a real
   kill is PostgreSQL's guarantee, not ours.
5. **Scope edges** (accepted r1): memory `stage` dedupe and a `ledger submit` CLI become
   follow-up beads.
6. **The ingest orphan: accepted orphan policy, no product code** (orchestrator ruling, option b).
   Checked first for an existing mechanism (option a): nothing sweeps unregistered capture
   directories. `retention.purge` detects one only indirectly and only once the shared blob is
   purge-eligible: a blob with no registered users reports `UNREGISTERED`; when the blob has
   users, deleting it meets the orphan's body link, `SnapshotStore.delete_blob` returns
   `UNKNOWN_LINK`, and the purge reports an `IncompleteBlob` ("a blob the operator must register or
   remove before purge completes") and keeps the bytes. `entity/discovery.store_captures` has the
   same publish-then-register order and no reuse. So (a) does not cover it. (b) holds because an
   unregistered capture is not a record: first-party reads go through `capture_refs`
   (`retained_capture`, `Registration.find`); `SnapshotStore.list_captures` is called only by
   `api/three_source_cli.py` and `ingest/upstox_candle_retention.py`, neither on a first-party
   surface; and the retry registers exactly one capture with an honest, fresh instant. PILOT-11's
   "without duplication" is about records, so (c) is not triggered; reusing the orphan would also
   pass off its retrieval instant as the retry's. **Recovery procedure** (documented here and in
   the test docstring): an orphan is a capture directory under
   `<store>/<source>/<surface>/<request_key>/<capture_id>/` whose `(source, surface,
   request_key, capture_id)` has no `capture_refs` row. Leave it, or remove that directory (never
   the blob) before a purge, which otherwise reports `UNREGISTERED` (no registered users) or
   `UNKNOWN_LINK` (deletion meets the orphan link).

## Defined states (the B-01 documentation)

A quarter's state is read, never stored. It is a function of the period's **head** (latest
earnings-update version, `run_draft._head`): `version_status(head)`, or `NONE` when there is no
version. These are mutually exclusive by construction. A second, independent read is
**runnable**: `preflight` passes. S14's names are in brackets for traceability.

| State | Read from | Next action |
|---|---|---|
| `NONE`, not runnable (`BLOCKED`) | no head; `preflight` refuses (an original not a retained first-party capture, an XBRL not `MAPPED`, the predecessor head not `APPROVED`) | register/ingest the original, or approve the predecessor |
| `NONE`, runnable [REGISTERED…CALCULATED] | no head; `preflight` passes | S3 run |
| `DRAFT` [DRAFTED] | head status | S4 submit (Python route) |
| `IN_REVIEW` [HUMAN_REVIEW] | head status | S5 approve, or `REQUEST_CHANGES` / `REJECT` |
| `APPROVED` [APPROVED] | head status (`APPROVE` or `IMPORTED_APPROVAL`) | S6 export; the next quarter may become runnable; a deliberate successor run is allowed |
| `HISTORICAL` | head status (`IMPORT_SEAL`: an imported, sealed version) | S3 run if runnable: the run drafts its successor |
| `CHANGES_REQUESTED`, `REJECTED`, `WITHDRAWN` | head status | S3 run if runnable → a successor version (PREP-5 shapes its content) |

`DRAFT` and `IN_REVIEW` are `lifecycle.OPEN`: preflight refuses a run. Every other head is
closed, and a run then drafts a **successor** whose predecessor is that head — the PREP-2b
behaviour (`test_prep2b_run_draft.test_prior_refusals` runs FY26_Q2 again after approving its
first draft), which PREP-3 keeps.

**Retry versus successor.** Retrying an interrupted attempt and starting a successor are the same
command; the head tells them apart. An interrupted run committed no version (S3e is atomic), so
the head is unchanged and the re-run is the retry: it creates the one version the first attempt
would have. A run that got past S3e leaves a `DRAFT` head, so a re-run refuses: that refusal is
how the operator knows the attempt completed (recover per decision 2). A run on a head that was
already closed before the operator started is a deliberate successor, not a retry.

**Imported-head bootstrap.** `preflight` skips the `APPROVED`-predecessor check when the period
has a `BOOTSTRAP_THESIS` report; the pilot's first quarter starts from the imported versions
(`ledger import`), so its head may be `HISTORICAL` and its first run drafts that head's successor.
A later quarter whose predecessor head is `HISTORICAL` is not runnable ("has no APPROVED head").

Allowed transitions: `NONE`/closed → `DRAFT` only through S3 (preflight, then the locked
in-transaction check); every decision edge is `lifecycle.TRANSITIONS`, which this plan does not
restate or change. S14's `PUBLISHED` is not a state: export is a read-only rendering (E-08
deferred). Immutable outputs: capture rows and receipts never rewritten, fact rows append-only,
selections chained, traces content-hashed, versions sealed by digest, decisions chained.

## Failure states (by execution boundary)

A failure never undoes a commit, and a retry is the same command (decision 3) unless the
exception column says otherwise.

| Step | Failure (raised as) | What persists | Resume |
|---|---|---|---|
| S1 | `SourceRegistrationError` in preflight of pins | nothing | fix the cause, retry |
| S1 | `SourceRegistrationError` or interruption mid-roles | receipts of earlier roles | retry: those receipts are returned, the rest registered |
| S1 | interruption after locator publication | all receipts and the locator | **exception:** retry refuses "refusing to overwrite locator manifest". Completion = the locator parses to the submitted refs and every role resolves through `SourceIntakeStore.get_registration` (what admission's `resolve_verified` reads). Proceed to S2 with that locator |
| S2 | `VersionContentDriftError` | nothing (raised before any write) | fix the pinned content |
| S2 | staging failure (`SourceRegistrationError`, `IntakeError`, `SnapshotError`, `OSError` per member) → `IngestError` at the end | other members' captures, generations, interpretations, package; durable `FAILED` acquisition attempts | fix the member, retry: committed members reuse, a new attempt row is a new observation |
| S2 | `refuse_ineligible` refusal; `IngestError` (reuse rejected, retries exhausted, no fiscal-year end) | earlier members' capture rows and generations, interpretations of members already processed | fix the cause, retry; reuse levels 1–3 |
| S2 | interruption between capture publication and its row | an orphan capture directory (decision 6) | retry; orphan per decision 6 |
| S3a/b | `RunDraftError` (preflight), `SourceAdmissionError`, `PipelineError` (cross-foot, cross-check, guidance anchor) | nothing | deterministic: fix the input, retry |
| S3c | `RunDraftError` in `bind_computed` (no formula; raised before any trace insert) | nothing | deterministic: fix the input, retry |
| S3c | interruption after trace k | traces 1..k only; no fact, selection or version | retry reuses those traces and adds the rest |
| S3d | `FactStoreFrozenError`, `FactStoreRetryError`, `CanonicalSelectionError`, interruption | the complete trace sequence, plus the facts and selections committed before it | retry reuses them (`FactStoreFrozenError`: reopen the store or route to another, which then gets new rows) |
| S3e | `RunDraftError` at write (prior changed, does not validate), interruption | S3c traces, S3d facts and selections; no version | retry reuses them; a validation failure repeats until the input is fixed (PREP-5) |
| S3f | interruption, `FileExistsError` on `--out-json` | the `DRAFT` version, maybe the JSON | **exception:** retry refuses (open head); recover per decision 2 |
| S4/S5 | `DecisionRefusedError` before writing; interruption before commit | nothing | retry |
| S4/S5 | interruption after commit | the decision (and S5's validation) | **exception:** retry refuses with `DecisionRefusedError`; the state already reads `IN_REVIEW` / `APPROVED` |
| S6 | `ValueError` (hash mismatch, unsafe name), `FileExistsError`, interruption mid-write | files already written; database untouched | **exception:** stock export into the same directory refuses; export into a fresh directory |

## Tests: what "resumes without duplication" asserts

Primary-key uniqueness is PostgreSQL's job and proves nothing here. Every case asserts:
1. **Reuse:** the ids committed before the retry (snapshotted then) are the ones the resumed
   output uses — the same capture rows, generation/occurrence ids, interpretation ids, package
   id, fact rows, selections and trace ids.
2. **Equivalence:** the scoped per-table row-count delta and the semantic output of the resumed
   attempt equal those of an uninterrupted attempt: for ingest the `IngestReport` (package
   present, occurrence count, interpretation counts, attempt outcomes); for the run the draft's
   claims (claim key, value, status) and `Pilot.validate` all `MATCH`. The uninterrupted
   baseline is one function-scoped fixture per step that clones its own `eqos_test_*` database
   from `pg_template`, runs the step once and keeps only ids-free values.
3. **Exactly the remainder:** rows added by the retry = baseline delta − rows the interrupted
   attempt committed (except the documented new rows: a fresh capture after an orphan, a new
   acquisition-attempt observation).
4. **Fired:** every injected wrapper recorded its interruption; a case whose boundary the
   fixture cannot reach is removed from the parametrization with a reason, never passed vacuously.
5. **Stable:** one further plain re-run adds zero rows (`Ingest.table_counts`).

Uniqueness checks on natural keys may stay as a supplementary assertion, nothing more.

## Size (estimates, not measured)

| Task | src Δ | tests Δ | docs Δ |
|---|---|---|---|
| 1 S1–S2 resume | 0 unless a test finds a defect | +130 | — |
| 2 S3 resume (PILOT-11) | 0 unless a test finds a defect | +130 | — |
| 3 S4–S6 resume | 0 | +60 | — |
| 4 S14 status line, roadmap row | — | — | ±4 |

All tests in one new file, `tests/fundamentals/test_prep3_resume.py`.

### Task 1: Register-sources and ingest resume without duplication

Goal: S1 and S2 interrupted at each boundary, then retried, satisfy the five assertions above.
Files: Create `tests/fundamentals/test_prep3_resume.py`. Product code only if a case is red.
Interfaces: Produces `Interrupted(BaseException)`; `interrupt(patch: pytest.MonkeyPatch, owner:
object, name: str, *, after: bool, nth: int = 1) -> list[int]` (wraps `owner.name` on the scoped
`patch` to raise before or after its `nth` call; the returned list records firings);
the function-scoped baseline fixtures. Reuse `Ingest.table_counts` (no new counts helper).
Approach:
- **S1** (on `prep2b_support.Pilot`, its `registered` path): interrupt
  `SourceIntakeStore.register_capture` after call 1 (between originals) and after call 3 (before
  locator publication); interrupt `cli.register_sources` after it returns (published, not
  acknowledged). Each case keeps the original manifest bytes, approved context and register argv from its one
  `Pilot.registered()` call and retries the same CLI command with them; it never calls
  `registered()` again after an interruption (it stamps captures with `datetime.now()` and caches
  only after registration completes, so a second call would make new capture ids, new receipts
  keyed by capture coordinates in `source_intake_store`, and, after locator publication, refs
  differing from the locator). The first two end with three receipts, each byte-identical to any receipt
  that existed before the retry, and one locator. The third refuses to overwrite, and the
  completion check in the failure table holds without rewriting the locator. Keep citing
  `test_source_intake_store.py:263` for the install-without-receipt case; do not copy it.
- **S2** (the `ingest` fixture, default XBRL + PDF intake), parametrized over: capture row insert
  (`capture_retention.Registration.insert`, before: the orphan case); `put_generation` after
  call 1 (XBRL stored, PDF not); `put_interpretations` after call 1; `put_package` after;
  `put_segment_members` after; `put_attempts` after (package-owned PDF attempts) only if the
  fixture writes any, else removed with the reason. `put_attempts` delegates to
  `put_generation`, so a `put_generation` wrapper counts those calls too; call 1 on a fresh
  ingest is still the XBRL generation. The orphan case asserts exactly one
  `capture_refs` row per (source, surface, request key), `list_captures` for that route returns
  two records, and names the orphan (the one with no row) in the assertion message; the
  registered capture's `registered_at` is later than the orphan's `retrieved_at`.
Verification: `uv run pytest tests/fundamentals/test_prep3_resume.py -m "pg and retained" -k "register or ingest"`.
Dependencies: none. Risks: medium — reuse levels are untested under interruption; a fix could
touch the pinned reuse rules (rerun `test_evidence_first_party.py`).

### Task 2: The run resumes at every boundary (PILOT-11's evidence)

Goal: an FY26_Q2 run on `prep2b_support.Pilot` interrupted at each S3 boundary, then retried,
satisfies the five assertions and ends with exactly one `DRAFT` for the period. The fact-write
cases (b)/(c) are named `test_run_resumes_after_interrupted_fact_writes` and is PILOT-11's first-clause
evidence.
Files: Modify `tests/fundamentals/test_prep3_resume.py`.
Interfaces: Consumes Task 1's helpers; `Pilot.run`, `Pilot.validate`, `Pilot.approve`.
Approach (each wrapper in its own `monkeypatch.context()`):
- Persistence order, asserted by the cases: traces → facts/selections → draft. An interruption
  after the first trace leaves that trace and no fact, selection or version; one during the fact
  writes leaves the complete trace sequence and the facts written so far.
- (a) `EvidenceRepository.put_calculation_trace` after call 1: the committed trace's id is reused
  and the remaining traces are added exactly once; `fact_rows` and `fact_selections` are
  unchanged by the interrupted attempt.
- (b) `PgFactStore.put` after call 2; (c) `PgFactStore.select_canonical` after call 1: all traces
  are already committed and reused; the retry adds only the remaining facts and selections.
- (d) inside the draft transaction: the in-transaction `AS_KNOWN` check (`check_version` as
  `run_draft` calls it) raises after the version insert; nothing of S3e survives.
- (e) after the draft commits, through `main([...run argv, "--out-json", j, "--out", m])`: the
  JSON write (`cli.write_bytes_no_clobber`) interrupted before (no files) and after (JSON only,
  the between-files boundary). In both, the re-run refuses before the pipeline with
  `fact_rows`, `fact_selections`, `report_versions`, `calculation_traces` unchanged; the head is
  `DRAFT`; the test finds the version from the head, submits it by the Python route and approves
  it (`Pilot.approve`), exports it with `ledger export --version-id V --out f`, and checks
  `sha256(f)` equals the stored `content_hash`.
Verification: `uv run pytest tests/fundamentals/test_prep3_resume.py -m "pg and retained" -k run`.
Dependencies: 1. Risks: low; a red is a real duplicate, fixed in this task.

### Task 3: Submit, approve and export resume without duplication

Goal: S4/S5 interrupted inside their transaction leave no decision (and, for S5, no validation)
row, and a retry records exactly one; interrupted after commit, a retry refuses with
`DecisionRefusedError`, adds no row, and the state reads `IN_REVIEW` / `APPROVED`. S6 stock export
interrupted after its first file leaves the database untouched; a retry into the same directory
refuses with `FileExistsError` and writes nothing; a retry into a fresh directory produces every
file, each narrative hashing to its version's `content_hash`.
Files: Modify `tests/fundamentals/test_prep3_resume.py`.
Approach: `ledger.store.insert_decision` called through then interrupted (inside the
transaction) for the before-commit case; `lifecycle.submit` / `decide` called twice for the
after-commit case. Export via `main(["ledger", "export", "--stock", …, "--out", d])` with the
module's file open interrupted before its second call (the stock has several sealed versions).
Verification: `uv run pytest tests/fundamentals/test_prep3_resume.py -m "pg and retained"`; then
the full gate (`uv run pytest tests/fundamentals`, `uv run mypy --strict src`, `uv run ruff check
src tests`).
Dependencies: 2. Risks: low.

### Task 4: Record the realisation

Goal: S14's header carries decision 1's status line; the roadmap PREP-3 row reads done with the
test file; register B-01's Status changes only after Sol's phase approval, by the orchestrator.
Files: Modify `docs/specs/equity-os-s14-earnings-review-workflow-rework.md` (status line only),
`docs/backend-roadmap.md` (PREP-3 row).
Approach: Sonnet; docs only; no change to S14's body.
Verification: `.claude/project/verification.md` structural checks; the linked paths exist.
Dependencies: 3. Risks: low.

## Follow-up beads (decision 5)

- Memory `stage` retry duplicates a candidate item: add a natural-key reuse or document it as
  agent-side.
- `ledger submit` CLI for the pilot's operational runs (PREP-7); until then the Python route in
  finding 6.

## Risk notes

- The plan predicts every boundary already resumes. A red case is fixed at the key or reuse
  rule, not with a new layer; if a fix needs more than a local change, it comes back for a
  ruling before code.
- Decision 6 leaves orphan capture directories by design; a purge reports them, and an operator
  removes them by the recovery procedure. If a later reader starts listing first-party routes
  from disk, this policy must be revisited.
- Decision 2 leaves the run's JSON dump unrecoverable after a post-commit crash.
- Ruling 1 means S14 is not implemented in Phase 0.5. If B-01 is read as needing stored
  transition records, decision 1 reopens before any code.

## Review r1 responses

| # | Finding | Change |
|---|---|---|
| 1 | `monkeypatch.undo()` drops the test-DB env | Decision 4: each wrapper in its own `monkeypatch.context()`; `interrupt` takes the scoped patch; the fixture's monkeypatch is never undone |
| 2 | Ingest FS→DB orphan omitted | Finding 2 + decision 6: option (b) accepted orphan policy with evidence that no existing mechanism sweeps it (purge only reports `UNREGISTERED` / `UNKNOWN_LINK`) and no first-party reader sees it; recovery procedure; Task 1 orphan case counting files and rows; the "no product code" claim is now a prediction the tests check |
| 3 | Task 1 seams wrong | Task 1 S2 parametrized over the real boundaries: capture row, generation, interpretations, package, segment members, package-owned attempts where reachable; "fired" assertion |
| 4 | Register-sources resume uncovered | S1 table row and failure rows; Task 1 S1 cases between originals, before locator publication, after publication; completion check without overwrite |
| 5 | Duplicate-key assertions vacuous | "Tests" section: reuse of snapshotted ids, equivalence to an uninterrupted baseline, exactly-the-remainder, fired, stable; uniqueness supplementary |
| 6 | Partial trace sequence not interrupted | Task 2 (a): `put_calculation_trace` after call 1 |
| 7 | Post-draft recovery unproved | Decision 2 lists recoverable vs abandoned artifacts; Task 2 (e) covers before-JSON and between-files and runs submit, approve and a hash-checked export |
| 8 | Derived states overlap | State = head status or `NONE` (mutually exclusive) plus a separate `runnable` read; retry-versus-successor and imported-head bootstrap paragraphs; consequence 1 narrowed; PREP-2b successor behaviour kept |
| 9 | Failure table wrong | Failure table rebuilt per execution boundary including ingest, with durable attempts and the state-dependent exceptions (S1 locator, S3f, S4/S5 after commit, S6) |
| 10 | Command and export details | `register-sources`; single-version `--out` overwrites, stock export no-clobber; Task 3 uses stock export for the partial-directory case |
| 11 | Existing ingest retry overlooked | Out of scope and decision 3: "no new automatic retries; the existing bounded retries stay" (serialisation and interpretation-conflict) |

## Review r2 responses

| # | Finding | Change |
|---|---|---|
| 4 | Retries re-enter `Pilot.registered()`, making new capture ids and refs that differ from the locator | Task 1 S1: each case keeps the original manifest bytes, approved context and register argv and retries the same CLI command; `registered()` is never called again after an interruption |
| 9 | Run persistence order wrong | Verified against d8380c7: `cli.run_command` passes a `before_commit` hook to `run_pipeline`; the hook (`bind_computed`) runs after the render and before fact writes. Order is now traces (S3c) → facts/selections (S3d) → draft (S3e); S3 table, failure table and Task 2 assertions match |
| n1 | `SUPERSEDED` in the state table | Removed: it describes an older version with an approved descendant, not the head |
| n2 | Purge wording | A blob with no registered users reports `UNREGISTERED`; `UNKNOWN_LINK` applies when deletion meets the orphan link |
| n3 | Baselines function-scoped | Accepted by Sol; no new test infrastructure, the plan's "module-scoped" baseline wording is now "function-scoped" |

## Sol r3 notes (APPROVE, non-blocking)

- The r1 response row for finding 6 should read Task 2 (a), not (c).
- The S3c failure row: a no-formula refusal happens before any trace insert; distinguish it from an
  interruption after trace k when implementing.
