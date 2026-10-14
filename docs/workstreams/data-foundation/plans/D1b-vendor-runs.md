# D1b Task 6 Vendor-Run Integration Plan

> **Superseded 2026-10-14** by [D1b-cleanup.md](D1b-cleanup.md): the design this plan describes was deleted or simplified; kept as history.

Status: R4 APPROVE, 2026-10-13; supplements Task 6 of [D1b.md](D1b.md). Source-independent queue SQL may start; authoritative generation/run dispatch still waits for the gates below.

**Origin:** approved D1b Task 6 and [publication repair r3](D1b-publication-repair.md); current seams inspected 2026-10-13; native `cd8151b`, dictionary `95dd442`; Screener authority pending.
**Goal:** consume exact guarded handoffs, replay every deciding id, atomically publish the queue, and return an immutable overlay without changing v1 surfaces.
**Out of scope:** Task 7 commands, approvals, report presentation, live acquisition, retained-source mutation, D1b release, and unretained/unauthorized vendor evidence.
**Out of scope:** Task 11/13 files, repository modules, migrations 0001-0007, publication artifacts, or rights.
**Constraints:** use exact `Fraction` arithmetic; fail closed; never zero-fill or backdate.
**Constraints:** generation and queue times come from `eqos.store_now()`; callers supply no clock.
**Constraints:** every PostgreSQL test uses an isolated `eqos_test_*` database.
**Constraints:** production Python stays at or below 800 lines; `engine.py` receives only a call site.
**Constraints:** the permanent RED uses today's callable API; missing future symbols, PostgreSQL or retained bytes are not REDs.

## Fixed contract decisions

1. Preserve `request_for(..., vendor_sources: tuple[VendorSurfaceRequest, ...] = ())`; extend `execute_run` with keyword-only `first_party_generation: FirstPartyGenerationHandoff | None = None` and `vendor_generations: tuple[VendorGeneration, ...] = ()`. Omitted vendor fields preserve v1 calls and JSON exactly. Any nonempty vendor declaration selects v2; a source/surface-only legacy declaration must raise a typed publication/handoff refusal before capture, attempt, fact, generation or run writes, and it never yields a vendor `SourceValue`.
2. Extend `VendorSurfaceRequest` additively to carry one complete generation request: representation, schema identity, entity, exact `PeriodInterval`, basis, framework, statement family, retained binding (including path/hash/claim), knowledge-time evidence, typed source-specific semantic composer context and expected logical-scope hash. Defaults plus omission of unset fields preserve old constructor/JSON, but incomplete entries are not executable.
   V2 is deliberately one run/package scope: exactly one entity, basis and reporting-period end in `RunScope`, one framework across declarations, and one first-party handoff matching them. Several families, representations and duration kinds may share that end. Another entity, basis, framework or end requires a separate `RunRequest` and handoff.
   Preflight rejects a broader, missing, duplicate or extra declaration/generation set before any write. V1 multi-value scopes stay unchanged. Full declarations are sorted/deduplicated, never collapsed by source/surface.
3. Keep two identities. `evidence_identity_sha256` hashes a versioned canonical document containing `VendorRequest.identity_sha256()`, the complete retained path/hash/time claim, every reloaded primary and supporting capture/body/blob/record identity, schema, publication-derived extractor version and content hash, knowledge evidence, logical-scope hash and semantic composer context. It selects one immutable body and closed row set; every stored attempt keeps that exact request hash in `input_sha256`.
   `logical_scope_sha256` excludes retained path/body/capture identities and `input_sha256`, but includes source, surface, schema, entity, exact `PeriodInterval`, basis, framework, representation, family, extractor version/content and canonical semantic parser context (for example verified issuer binding, section, parent and interpretation-affecting options).
   The fixed producer, not the caller, derives both. It persists the logical hash in the existing `AcquisitionAttempt.extraction_context_sha256` for every v2 acquisition/extraction attempt; no JSON reason convention, foreign key or migration is added. The declaration's expected hash is an untrusted preflight claim and must equal that derivation.
   `VendorScope` carries both hashes and exact ids; the manifest deterministically closes their ingredients through declarations, pins and by-id inputs. Two physical captures may share availability scope but never evidence identity or facts.
4. `prepare_vendor_generation(generation: VendorGeneration, *, declaration: VendorSurfaceRequest,
   loaded_config: LoadedConfig, config_root: Path, input_anchor: DirectoryAnchor | None,
   composer_context: VendorComposerContext, repository: EvidenceRepository) ->
   PreparedVendorGeneration` treats the caller model as a claim.
   For a captured input it reloads the pre-registered capture by id, proves its source/surface,
   blob/record hashes and store times, descriptor-reads the declared retained body, dispatches a
   closed source/schema composer (`screener-financials-html-v1` or the actual schedule schema
   `screener-financials-schedule-v1`), recomputes rows and compares every field before storage.
   Composer context (for example Screener issuer binding/section) is rechecked against the
   body, entity/listing evidence and declaration; no injected callable or SHA alone authorizes facts.
   Source headers determine each occurrence's actual interval: an annual or TTM duration stays annual
   or TTM and must match the declaration; it is never stamped with a requested quarter or run end.
5. `append_vendor_generation(generation: VendorGeneration, *, declaration: VendorSurfaceRequest,
   loaded_config: LoadedConfig, config_root: Path, input_anchor: DirectoryAnchor | None,
   composer_context: VendorComposerContext, repository: EvidenceRepository) -> VendorScope` repeats
   preparation and the publication guard before writing; it never trusts a caller-supplied prepared
   object. It persists recomposed rows, interprets/reloads stored
   ids, and returns request/evidence/logical hashes, scope, capture/evidence ids, release-derived role/
   disposition, rights/authority/extractor pins and publication identity. A forged capture,
   occurrence or attempt gives zero generation-table mutation. A captured generation must use a
   pre-registered source; Task 6 does not manufacture capture registration.
6. Capture-free failure is recomposed only through the fixed offline composer for the same complete
   declaration and an actual release authority/extractor/schema. It has no capture, occurrence,
   interpretation or numeric body and at least one exact failed attempt. `UNAVAILABLE` is never
   relabelled `NOT_PUBLISHED`; no Tijori extractor/schema may be invented to admit missing bodies.
7. Before vendor persistence, `validate_first_party_handoff(handoff: FirstPartyGenerationHandoff, *,
   request: RunRequest, config: LoadedConfig, config_root: Path, repository: EvidenceRepository) ->
   FirstPartyScope` freshly re-proves the publication and reloads package, members, captures,
   occurrences, interpretations, attempts, settings/evidence input and alignment proofs by id. It
   proves package evidence hash/family/scope; publication version/hash/
   state; dictionary/formula/mapping/normalisation/alignment/authority/extractor pins; fiscal setting
   ids/value/time; member capture hashes/times and exact occurrence/interpretation/attempt sets and
   bounds; capture-free attempt subset; proof set; qualified rows and `ProvenCondition` closure. It
   matches the single entity/end/basis/framework and applies cutoff/mode eligibility. After Task 11's
   final handoff is accepted, dispatch binds this function to that landed class; Task 6 adds no
   guessed field or parallel context model. It reloads the exact `SettingsRecord` and linked
   `EvidenceInputRecord`, proves its kind/label/content hash, descriptor-reads the source identity
   artifact under `config_root`, and matches its bytes and setting/entity value (resolving from the verified entity/config convention,
   never treating a database label as a path), recomputes the complete settings-record context digest,
   and requires every handed-off interpretation row to contain the same durable reserved trace.
   A time, month or boolean flag alone is never proof. The current Task 11 candidate uses
   `src/fundamentals/evidence/first_party_context.py` trace-in-row with no SQL FK; final symbol names are bound only
   after Task 11 review acceptance. A forged handoff refuses before
   vendor writes and never falls back to v1; an empty-vendor legacy v1 call never enters this path.
8. Later-attempt selection first uses exact source/surface/entity/end/basis/framework/representation/
   family and pinned extractor as coarse checks, then requires
   `attempt.extraction_context_sha256 == VendorScope.logical_scope_sha256`; the logical hash closes the
   full interval, schema, duration kind and semantic context that the attempt columns omit. Maximum
   eligible `(attempted_at, attempt_id)` wins. A later no-binding acquisition failure or changed-
   capture extraction failure in the same logical scope suppresses stale success despite a different
   `input_sha256`. Different interval/duration, family, schema, extractor content or semantic context
   cannot suppress it. Exact `input_sha256`, capture and evidence ids still select facts and never
   merge two physical captures. A later unhanded success cannot substitute facts. Replay uses only
   manifest ids and never scans current attempts.
9. Every handed-off and considered vendor row is closed in `RunManifest.inputs`. Existing schema
   labels carry the semantics without a migration: `SELECTED` means used, `FAILED_ATTEMPT` means
   failed, and `NOT_SELECTED` means unused. Used interpretation closure includes operands and every
   `ProvenCondition.evidence_interpretation_ids`; every deciding capture, occurrence, attempt,
   alignment proof and actual calculation trace is included. First-party context closure additionally
   records the exact `SETTINGS_RECORD` and `EVIDENCE_INPUT` as `SELECTED`; the selected interpretation
   ids seal their embedded durable trace. Do not invent a `CALCULATION_TRACE` id for that trace-in-row.
10. `QueueItem.run_id` remains the public creating-run field. Add `QueueRunMembership(run_id,
   item_id, origin_run_id, recorded_at)` and optional `QueueOverlay.memberships`. Empty membership
   is omitted from JSON and retains the old equality validator and constructor behavior. New
   overlays validate open items and accepted dispositions through membership, allowing an item
   created by an earlier run to be reused by the named run while preserving its origin.
11. Routing adds draft APIs and retains the accepted Task 5 `route_pair`, `route_status` and
   `route_unmapped_occurrence` wrappers. `QueueItemDraft` contains the key, pair identity, outcome,
   severity, diagnostic/reason fields, source refs and exact attempt/interpretation/occurrence ids;
   it contains no item id, run id, input hash, predecessor or time. Existing pure routing tests
   and default JSON remain valid.
12. Queue publication uses migration 0006 as written. Its base lock/predecessor identity is
   `(key digest or null, pair identity, outcome)`. Before any queue item/input/link mutation,
   derive each base identity's signed 64-bit advisory key from the first eight bytes of its
   canonical SHA-256, deduplicate the actual keys, and acquire every transaction lock in ascending
   signed-integer order. All callers use this order regardless of draft order; hash collisions
   serialize distinct identities safely. Then process drafts in canonical base/payload order.
   `input_sha256` hashes a versioned canonical
   document containing severity, diagnostic, routing reason, reason code, fully sorted source-ref
   JSON, and separately tagged/sorted occurrence, interpretation and attempt associations. The SQL
   writer reloads authoritative association provenance and includes occurrence first-seen,
   interpretation recorded-at and attempt attempted-at clocks. Reordering reuses; any material
   payload/evidence change creates a predecessor-linked item. Reuse verifies the sealed payload.
13. The `RunStore` cursor transaction alone is atomic: queue failure rolls back its new `runs`,
   `run_versions`, `run_inputs`, `results`, `result_source_values`, `result_surfaced_restatements`,
   `pair_outcomes`, `pair_adjustments`, `queue_items`, `queue_item_inputs` and `queue_run_items`.
   Earlier authorized/idempotent global `version_pins`, definition sets, pre-registered
   captures and guarded evidence generations may remain. A bad publication/handoff/provenance
   preflight writes no generation or run facts; do not claim all-table rollback.
14. Overlay capture calls `eqos.store_now()` once in its read transaction; SQL returns the same
    timestamp as `as_of` and its UTC epoch-microsecond integer as `recorded_position`. Re-read
    requires the exact pair and refuses a mismatch. Membership is selected through
    `queue_run_items`; item and final-disposition rows must be at or before that position. Only a
    protected `queue_dispositions` row bound to an `ACCEPT` receipt closes an item. A rejected
    proposal leaves it open. Task 6 reads this state; Task 7 still owns all public decision writes.
15. Actual-release authority is pending. Synthetic mechanics may prepare in `eqos_test_*`, but no
    real positive run or completion claim may start until candidate A is committed, a fresh review
    examines exactly A, receipt/review commit C is committed, current H proves A -> C -> H with
    unchanged selected/receipt bytes, and the committed real-release assertion passes. Catalog roles
    are closed by that release. Upstox `income-statement`, `balance-sheet`, `cash-flow` and
    `key-ratios` have diagnostic classification but no `SurfaceAuthority`; each request refuses
    before capture/attempt/fact/run writes. Missing Tijori, Upstox and NETWEB evidence remains open.

## File map and ownership

| Owner | Exclusive implementation files | Responsibility |
|---|---|---|
| Public RED/acceptance | create `tests/fundamentals/test_compare_vendor_runs.py`; consume existing retained oracles | Permanent current-API refusal RED, then gated public v2 acceptance |
| Vendor producer | create `src/fundamentals/compare/vendor_inputs.py`, `tests/fundamentals/test_compare_vendor_inputs.py`; modify `src/fundamentals/evidence/vendor_screener.py`, `vendor_offline.py` | Guarded persistence, fixed-composer evidence/logical identities, exact `VendorScope` |
| Queue SQL | create `src/fundamentals/compare/queue.py`, `tests/fundamentals/test_compare_queue.py`; modify `src/fundamentals/contracts/review_queue.py` | Additive draft/membership contracts, cursor-level create/reuse/predecessor/link and store-clock overlays |
| Shared run writer | create `src/fundamentals/compare/vendor_handoffs.py`, `vendor_resolution.py`, `vendor_rows.py`; modify the named shared files under `src/fundamentals/compare/` and focused existing run tests | First-party reproof, run contracts, resolution, source-qualified rows, closure, status and atomic call site |

After fresh R3 approval, the independent Task 3 queue SQL owner may start while publication and
Task 11 context repairs remain under review. Task 2 waits for Task 13's accepted producer-facing API;
Task 4's handoff consumer waits for the accepted final Task 11 and Task 13 contracts. This sequencing
does not block source-independent queue mechanics and grants no real-release execution or acceptance.
Only the queue SQL owner edits the queue contract; only the shared run writer edits run contracts and
call sites. It does not touch `run_config.py`, evidence contracts/repository modules or migration 0007 until
the publication repair is accepted and handed off; it then consumes the final symbols as landed.

### Task 1: Capture the permanent public refusal RED

Goal: a vendor-declared v1/unjoined request refuses before any generation or run write.
Stage: `eqos-u0u.3`.
Files:
- Create: `tests/fundamentals/test_compare_vendor_runs.py`.
- Modify: None.
- Test: one permanent current-API RED node.
Interfaces:
- Consumes: today's two-field `VendorSurfaceRequest`, `RunRequest`, `execute_run` and table counts.
- Produces: `test_vendor_declared_v1_request_refuses_without_joined_handoffs`.
Approach: manually declare a Screener source/surface on today's request and call today's
`execute_run` with no future keyword/import. Use `pytest.raises(ValueError, match=...)` and assert
unchanged `capture_refs`, `occurrences`, `interpretations`, `acquisition_attempts` and `runs`. Current code reaches the v1 resolver, so the behavioral
assertion fails. Keep this test unchanged after implementation; its final behavior remains refusal.
The authorized SONACOMS positive path and later-failure path are different tests added only after
their final API types and loader-verified handoffs exist; the existing hand-read literal remains a
characterization and missing API cannot be reported as their RED.
Verification: `scripts/verify.sh red d1b-vendor-runs tests/fundamentals/test_compare_vendor_runs.py::test_vendor_declared_v1_request_refuses_without_joined_handoffs` records an assertion failure after collection and PostgreSQL setup.
Test seams: current public execute and exact before/after table counts; no retained input required.
Dependencies: current D1a public run seam.
Risks: test-first; an infrastructure failure is not RED evidence.

### Task 2: Persist one guarded vendor generation

Goal: retained bytes and a closed composer, rather than caller-built models, produce an exact stored
`VendorScope`; every provenance or publication refusal leaves generation tables unchanged.
Stage: `eqos-u0u.3`.
Files:
- Create: `src/fundamentals/compare/vendor_inputs.py`, `tests/fundamentals/test_compare_vendor_inputs.py`.
- Modify: `src/fundamentals/evidence/vendor_screener.py`, `vendor_offline.py` only for the two
  deterministic hashes and v2 attempt context.
- Test: vendor input and publication-persistence tests.
Interfaces:
- Consumes: `require_published_generation`, `pin_published_generation`, descriptor-safe retained
  reads, pre-registered capture by-id reads, closed Screener/offline composers, repository writes
  and `interpret_generation`.
- Produces: `PreparedVendorGeneration`, `VendorScope`, read-only preparation and guarded append APIs.
Approach: implement decisions 3-6 as two phases. Fixed composers derive the logical hash from the
complete requested interval, accepted extractor content and semantic context; they put it on every
v2 attempt while keeping the full request hash in `input_sha256`. Preparation reloads publication,
captures and raw primary/supporting bytes; derives the evidence hash; re-extracts through the declared
source/schema context; verifies source-printed periods and actual entity/basis/family; and compares the
complete recomposed draft. It never trusts caller rows, attempts or hashes. Append repeats the guard,
pins the release, writes only recomposed rows, interprets stored occurrences and reloads exact ids.
Capture-free failures come only from the fixed offline composer with the same logical hash contract.
Verification: `uv run pytest tests/fundamentals/test_compare_vendor_inputs.py tests/fundamentals/test_vendor_publication_persistence.py` passes forged capture/occurrence/attempt no-write cases; evidence-versus-logical hash fixtures; changed/missing binding with stable logical scope; quarter/FY/TTM separation; actual annual/TTM intervals not relabelled as a requested quarter; raw reread; schema/right/pin refusal; idempotence; and capture-free truth.
Test seams: guarded producer boundary; `RELEASED` evidence is tested only after root supplies the
real reviewed release, while loader-validated `SYNTHETIC` mechanics stay inside `eqos_test_*`.
Dependencies: Task 13 accepted API handoff; real-positive acceptance still waits for A -> C -> H.
Risks: test-first; repository files are near 800 lines and remain untouched.

### Task 3: Publish and read queue state on the run cursor

Goal: cursor-level queue helpers create or exactly reuse immutable items, serialize predecessor
selection, link membership to the current run, and reconstruct receipt-protected overlays at a
machine-proved store-clock position.
Stage: `eqos-u0u.3`.
Files:
- Create: `src/fundamentals/compare/queue.py`, `tests/fundamentals/test_compare_queue.py`.
- Modify: `src/fundamentals/contracts/review_queue.py` additively.
- Test: queue PostgreSQL integration tests.
Interfaces:
- Consumes: frozen `QueueItemDraft`, `QueueItem`, `QueueRunMembership`, `QueueOverlay`, migration
  0006 tables/triggers and an existing psycopg `Cursor`.
- Produces: `publish_queue_drafts(cursor, *, run_id, drafts) -> tuple[QueueItem, ...]`,
  `capture_queue_overlay(pool, *, run_id) -> QueueOverlay`, and
  `read_queue_overlay(pool, *, run_id, as_of, recorded_position) -> QueueOverlay`.
Approach: implement decision 12's versioned digest document and base-identity advisory lock without
opening a pool connection in the cursor helper. Reload typed associations and provenance clocks on
that cursor. Overlay SQL joins membership, sealed inputs, protected dispositions and ACCEPT receipts.
Verification: `uv run pytest tests/fundamentals/test_compare_queue.py -k "digest or reuse or predecessor or concurrent or overlay or receipt or store_clock"` passes reorder-invariant reuse; successor creation for every immutable payload or typed evidence change; authoritative-clock binding; concurrent one-item reuse; reversed concurrent multi-item batches with no deadlock and exact shared item/link reuse; accepted-close/rejected-open; and origin membership.
Test seams: real migration-0006 schema in `eqos_test_*`; no Task 7 command or approval producer.
Dependencies: migration 0006 produces the draft/membership contracts; the later independently
approved [visibility repair](D1b-queue-visibility-repair.md) adds 0009's durable captured ID seal
and supersedes the timestamp-only overlay assumption before Task 5 integration.
Risks: test-first; the advisory lock key and canonical digest must be identical in every caller.

### Task 4: Resolve exact handoffs into real vendor sides

Goal: fresh execution and by-id replay produce the same source-qualified values, corroboration
pairs, statuses and evidence closure, including a later failed attempt suppressing stale success.
Stage: `eqos-u0u.3`.
Files:
- Create: `src/fundamentals/compare/vendor_handoffs.py`, `vendor_resolution.py`, `vendor_rows.py`
  (all under `src/fundamentals/compare/`).
- Modify: `src/fundamentals/compare/resolve_models.py`, `resolve_loader.py`, `resolve.py`,
  `engine.py`, `engine_rows.py` (all in the same directory).
- Test: `tests/fundamentals/test_compare_vendor_runs.py`, existing run-rule tests.
Interfaces:
- Consumes: freshly validated `FirstPartyScope`, exact `VendorScope` values, `attempt_available`,
  by-id replay readers, `SourceQualifiedSide` and `corroboration_result`.
- Produces: the first-party validator, handoff-bounded `ResolvedInputs`, exact selected vendor state,
  source-qualified rows/pairs, recursive dispositions and source/surface/request failures.
Approach: after Task 11 acceptance, bind the validator to its final landed handoff fields/helpers and
reprove the settings row, evidence-input row, source artifact/hash and embedded context on every row;
timestamps/flags cannot substitute. Validate the complete first-party handoff before vendor append.
Fresh vendor loading starts from exact scope ids and filters later attempts by decision 8's logical
hash; exact request/capture ids still select facts. Build each value from one source/surface/capture
and vendor-only operands. Preserve invalid/ambiguous evidence, call `corroboration_result`, exclude
diagnostics from votes, make non-diagnostic unavailable INCOMPLETE, and replay via `load_inputs` only.
Verification: `uv run pytest tests/fundamentals/test_compare_vendor_runs.py -k "first_party_context or request_collision or source_qualified or stale_success or replay_by_id or qualification_closure or capture_free" tests/fundamentals/test_compare_run_rules.py` passes forged-handoff no-write; by-id settings/evidence/artifact/hash and all-row trace reproof; manifest context closure; same-end multi-family separation; same-result ambiguity refusal; quarter/FY/TTM collision isolation; later no-binding acquisition failure; changed-capture extraction failure; non-suppression across duration/family/schema/context; distinct physical evidence; and replay list-spy cases.
Test seams: exact by-id handoff rows and source bytes, public result/manifest ids, attempt queries, and a
list-spy that fails if replay scans current evidence.
Dependencies: Tasks 1-2; accepted Task 11 and Task 13 handoffs.
Risks: test-first; keep `engine.py` at or below 800 lines by placing vendor assembly in new modules.

### Task 5: Integrate public execution and atomic queue publication

Goal: the final public v2 API validates closed handoffs, publishes run/results/queue atomically,
returns an immutable overlay, and leaves all v1 calls and dumps byte-for-byte compatible.
Stage: `eqos-u0u.3`.
Files:
- Modify: `src/fundamentals/compare/run_models.py`, `routing.py`, `run.py`, `run_store.py`,
  `tests/fundamentals/test_compare_runs.py`, `test_compare_config_pins.py`, `test_compare_run_rules.py`.
- Create: None.
- Test: public vendor-run and compatibility matrices.
Interfaces:
- Consumes: Tasks 2-4 outputs and final publication/first-party contracts.
- Produces: additive full `VendorSurfaceRequest`, exact `request_for`/`execute_run` extensions,
  draft routing, `RunStore.publish(..., queue_drafts: Sequence[QueueItemDraft] = ())`, `STAGE_QUEUE`,
  optional `RunRecord.queue_overlay`, and open-HIGH-aware `exit_status`.
Approach: require exactly one first-party package scope; validate its durable context reproof; require
every full vendor declaration to match its entity/basis/framework/reporting end; and prepare every
claim read-only. Reject another end, entity, basis, framework, missing/duplicate/extra claim, or an
ambiguous stored result-side identity before append. Append guarded generations, resolve/draft, then
publish drafts after pairs and before commit on the RunStore cursor. Existing identical v2 runs must
already have exact links. Queue faults assert rollback only for decision 13's per-run tables; global
pins, definitions, pre-registered captures and guarded evidence may remain. Replay reads ids, not queue.
Verification: `uv run pytest tests/fundamentals/test_compare_vendor_runs.py tests/fundamentals/test_compare_queue.py tests/fundamentals/test_compare_runs.py tests/fundamentals/test_compare_config_pins.py tests/fundamentals/test_compare_run_rules.py` passes incomplete-declaration refusal; one-handoff same-end multi-family/duration matching; other-end/entity/basis/framework prewrite refusal; per-run-table rollback snapshots; evidence persistence; concurrency; replay; and every v1 API/JSON cell.
Test seams: `STAGE_QUEUE` fault with explicit table snapshots; concurrent calls; legacy dumps.
Dependencies: Tasks 2-4; publication owner has frozen and handed off `run_config.py`, `run_store.py`,
`run.py`, evidence contracts/repository APIs and migration 0007 before this task edits shared files.
Risks: test-first; one shared writer avoids publication/run-store conflicts and nested pool checkout.

### Task 6: Run the two-level acceptance matrix

Goal: mechanism tests and actual retained/released evidence are reported separately, with every
Task 6 public compatibility and evidence obligation named honestly.
Stage: `eqos-u0u.3`.
Files:
- Modify: `tests/fundamentals/test_compare_vendor_runs.py` only for final guarded arguments.
- Create: None.
- Test: focused Task 6 matrix.
Interfaces:
- Consumes: completed Tasks 1-5 and root's committed A, fresh review, C, H and real-release proof.
- Produces: fresh evidence for v1 compatibility, synthetic mechanism behavior, actual retained
  SONACOMS execution, replay, queue overlay and explicit parked vendor obligations.
Approach: first prove v1 omission/JSON/replay, the permanent refusal RED now green, pure routing and
first-party results. Synthetic `eqos_test_*` tests prove mechanics only. After A -> fresh review ->
C -> H and the committed real-release assertion, add (do not rewrite Task 1 into) the authorized
new-API SONACOMS test with a pre-registered capture and exact handoff. Assert the hand-read Dec-2024
Sales literal `868 crore` at the retained `#quarters` Sales row and its bound body hash/location,
plus exact ids/pins/authority, real side/pair, queue membership and by-id replay. The later-failure
test changes or removes the retained binding but keeps the same logical-scope hash, proving that
logical availability suppresses stale success while the new exact request hash keeps evidence
distinct. Do not use APAR. Every Upstox `income-statement`,
`balance-sheet`, `cash-flow` and `key-ratios` request asserts no capture/attempt/fact/run mutation
while authority is absent. Missing Tijori/Upstox/NETWEB positive evidence remains an acceptance block.
Verification: `uv run pytest tests/fundamentals/test_compare_runs.py tests/fundamentals/test_compare_config_pins.py tests/fundamentals/test_compare_run_rules.py tests/fundamentals/test_compare_corroboration.py tests/fundamentals/test_compare_diagnostic.py` passes the fresh v1/public matrix; `uv run pytest tests/fundamentals/test_compare_vendor_inputs.py tests/fundamentals/test_compare_queue.py tests/fundamentals/test_compare_vendor_runs.py -m "pg and retained"` passes only with the actual reviewed release and retained SONACOMS evidence.
Test seams: isolated synthetic mechanics versus committed `RELEASED` authority and retained bytes.
Dependencies: Tasks 1-5 and the exact A -> fresh review -> C -> H gate. Full D1b release still waits
for the approved main plan's missing Tijori/Upstox/NETWEB evidence.
Risks: the focused implementation may be green while D1b Stage 1 remains correctly blocked.

## Build notes — 2026-10-13

Root records two additive integration rulings after inspecting the accepted handoff/API seams.
Fresh `execute_run` may take keyword-only `vendor_input_anchor: DirectoryAnchor | None = None`.
Captured claims require the explicitly observed directory anchor and guarded body/metadata reproof
before any append; capture-free offline claims may omit it. Do not guess a root from configuration,
cwd or a retained filename. The process-local anchor is absent from logical request/run identity,
manifest and legacy v1 JSON, grants no publication rights, and is unnecessary for by-ID replay.

Applicability context is re-proved from the exact first-party generation: package statement scope,
source-derived fiscal setting, and basis artifacts tied to the handoff's exact evidence identity,
including their key, value and stored metadata. Segment evidence must be inside the handoff's
closed IDs and match exact entity/basis/period/dimensions with real stored clocks and cutoff.
Ambiguous or absent context refuses; fresh resolution must close every consumed evidence ID,
and replay cannot use latest fiscal/segment/package scans.

Root's first frozen24-case public PG probe returns15 PASS /9 FAIL in29.96s. Original six refusal
contracts pass. The later cases fail at a missing private `fixtureco-fy26-q2.yaml` settings artifact,
before their intended behavior boundary. This is an invalid fixture/probe for those nine cases,
not a public API GREEN/RED claim; repair fixture construction without weakening production proof,
preserve all original assertions/literals, and rerun. Actual SONACOMS acceptance remains separate.

At the owner-requested pause checkpoint, the independent R2 public review is APPROVE;
all three preflight findings and the NOT_APPLICABLE/replay association defects are fixed.
The frozen31 PostgreSQL cases and100 pure cases pass. The original24 public cases,
original v1 prefix and six original refusal outcomes remain preserved. Mechanical
helper split preserves24 declaration ASTs,64 assertions, numerical literals and100
node IDs, with712/267-line test/helper files. Root explicitly approves proof resealing
for disclosed fixture expansion, formatting and that mechanical split; no historical
outcome is replaced. See [checkpoint review](../reviews/D1b-public-vendor-run-checkpoint.md).

Historical segment link creation time is unprovable under the immutable existing
schema, and actual multi-period segment acceptance remains unverified. These are
follow-up acceptance limits, not waived phase requirements. After the public writer
froze resolve.py, Root takes exclusive ownership of the additional witness closure
and context guard calls in that file for the joined checkpoint.
