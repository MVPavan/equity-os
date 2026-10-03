# Product completion temporal admission implementation plan

**Status:** PLAN_READY — candidate for review; no implementation or approval claim.
**Work item:** eqos-xg5. No Beads writes in this planning session.
**Origin:** Current user authorization; `docs/goals/equity-os-product-completion-gold.md` V01, V12 and §5 truthful retrospective Apar demonstration; S09, S11, S12; S10 source-of-truth matrix.
**Goal:** Reject unproved historical sources, pin eligible current/synthetic source bytes, and record new extraction, fact creation and selection at their actual times. Native historical admission is REFUSAL-ONLY in this packet.
**Out of scope:** Product/test changes during this session; historical timestamp backfills; full S09/S11/S12 schema rollout; changing Apar artifacts; pilot demonstration; live retrieval, credentials, cloud, private document inspection, dependency installs, commits, pushes or task-tracker mutations.
**Constraints:** “Post-cutoff source data, later canonical selections, later restatements, and future memory records cannot rewrite the historical package.”
**Constraints:** “Source text and retrieved memory cannot alter permissions, cutoffs, tools, or approval policy.”
**Constraints:** “Preserve existing approved thesis, evidence, and configurations as historical artifacts.”

## Authority and evidence posture

Current explicit instructions authorize this engineering-safety plan. The Gold contract calls for genuine acquisition evidence and separates the successor evaluation approval from independent safety repairs (§5, lines 102–110). The v2 decision register remains authority for decision acceptance; source records, fact records and approved narrative have different authoritative stores under S10. Neither a file nor an approval label is temporal proof by itself.

S09's authority section and S10/S11/S12 headers still describe draft specifications. Use their cited temporal constraints as design inputs requested by the user; this plan does not claim those documents received delegated approval, close their register rows, or infer earlier approved implementation history. Before a wider schema rollout, its owner must check current exact-byte acceptance evidence. This narrow refusal-to-backdate repair does not require successor pilot evaluation acceptance.

Implementation observations below are verified against current code, including concurrent edits, on 2026-10-02. Stale pre-code overlay and Gold's older statement that the store lacks cutoff queries are not implementation evidence. No product tests were run in this planning session; every RED/GREEN statement below is an expectation for implementation.

## Concrete seams and observed failure

| Seam | Verified behavior and consequence |
|---|---|
| `src/fundamentals/api/pipeline.py:108` | `XbrlInput` carries bytes, hash, source ID and `retrieved_at`, but no retained-evidence reference or first-seen proof. A bare timestamp is not independently proven capture history. |
| `src/fundamentals/api/cli.py:91` | Live `_build_xbrl_input` forwards adapter retrieval time; local mode fabricates it from `config.quarter.knowledge_cutoff` at line 119. Local bytes and config hashes do not establish when the system obtained them. |
| `src/fundamentals/ingest/xbrl_source.py:378` | Adapter records `datetime.now(UTC)` before acquisition. It is a real attempt timestamp, not verified completion/first-seen; a request straddling the cutoff can finish later. |
| `src/fundamentals/ingest/bse_pdf_source.py:251` | BSE results retrieval likewise records attempt-start time before download. This adapter is not the held-PDF input path of `run_pipeline`; preserve its metadata but do not mistake it for successful capture completion. |
| `src/fundamentals/api/pipeline.py:344` | `load_pdf` verifies configured byte hashes, but `LoadedPdf` has no acquisition timestamp. Results extraction at line 371 and guidance extraction at line 445 receive the configured cutoff as fabricated retrieval time. |
| `src/fundamentals/api/pipeline.py:230` | `_build_fact` assigns both knowledge and first-seen time to the cutoff, independently of source eligibility or actual fact creation. |
| `src/fundamentals/contracts/provenance.py` | `retrieved_at`, optional `first_seen_at`, `published_at` and `filed_at` already exist. Keep their meanings separate; timestamp validation at the new admission boundary is necessary. |
| `src/fundamentals/contracts/fact.py:38` | `Fact` has knowledge and first-seen fields, but no distinct extraction-result record. Use actual new-fact times without pretending this implements all S12 envelopes. |
| `src/fundamentals/store/fact_store.py:467` | Current `select_canonical` accepts `selected_at` and defaults to actual UTC time; it rejects selection before fact knowledge/first-seen. `get_canonical` and `query_canonical` now accept cutoff and apply fact and decision eligibility. Preserve these concurrent repairs. |
| `src/fundamentals/store/snapshot_store.py:121` | `get_capture(source_id, surface, request_key, capture_id)` resolves an exact record; `read_body(record)` verifies retained bytes. `CaptureRecord.retrieved_at` supplies neither distinct successful completion nor first-seen/registration proof. Native historical admission must refuse even internally consistent old records. |
| `src/fundamentals/api/cli_parser.py:48` / `cli.py:144` | `build_parser()` registers run flags; `run_command` currently creates output/store directories and opens `FactStore` before admission. Its constructor creates schema and migrates legacy selections. Preflight must move ahead of both operations. |
| `src/fundamentals/ingest/pdf_source.py:151` | `load_pdf(source_id=..., path=..., expected_sha256=...)` hashes a path and then reopens it in PyMuPDF. A digest comparison or post-parse rehash cannot defeat A→B→A substitution. Parse a private staged snapshot instead. |
| `src/fundamentals/store/fact_store.py:411` / `pipeline.py:612` | `put(fact)` can return an existing revision: value identity excludes temporal/parser-version fields. Pipeline currently appends a selection unconditionally. Existing facts have no trustworthy producer-proof field; `legacy_baseline` describes a selection, not proven fact knowledge. |
| `tests/fundamentals/test_pipeline_e2e.py:57` | Existing synthetic XBRL fixture takes the cutoff as its timestamp; deterministic pipeline calls provide no PDF capture metadata. New tests need independent temporal constants, not fixtures derived from cutoff. |

Read-only call-site search also found pipeline/XBRL constructors in `test_phase05_report_artifact.py`, `test_phase05_management_ledger.py`, `test_phase05_run_comparatives.py`, `test_generalization.py`, `test_hardening.py`, and concurrent `test_management_ledger_replay.py`. Account for them during integration rather than weakening admission to keep them passing.

## Five clocks and the derivation boundary

| Clock | Meaning and proposed treatment |
|---|---|
| Source acquisition / system first-seen | Successful receipt of exact source bytes and the earliest proven registration/availability of that version to this system. Preserve separately when evidence distinguishes them. Admission requires both proven values at or before cutoff; attempt-start, source publication and filesystem mtime cannot substitute. A copied archive entering this system today is first-seen today unless independently authoritative evidence proves earlier system availability. |
| Actual parser/run time | UTC time of current execution and extraction completion. Record run start and each source extraction completion; they may occur after the evaluation cutoff. Never set them to cutoff. |
| Fact knowledge / fact first-seen | When this particular reconciled output became known and was first created by the system. For a newly produced fact, stamp reconciliation completion, bounded below by source first-seen and extraction completion. Preserve an existing immutable revision's original times on idempotent reuse. |
| Selection decision time | Actual canonical transition time, bounded below by fact knowledge/first-seen. Keep the store's actual-time default; neither source acquisition nor cutoff supplies this time. A later decision is absent from earlier as-of reads. |
| Evaluation cutoff | Immutable ceiling for retrieved source versions, stored facts, selections, memory and other pre-existing evidence. It is distinct from reporting period, publication filters and run wall time. Changing it creates a successor evaluation/run rather than mutating old evidence. |

**Contract-based inference:** S11's knowledge-cutoff section admits source versions before the cutoff and then explicitly requires downstream stages to operate on the sealed evidence package. S09 distinguishes original documents from derived parsed renditions; S12 gives extraction results their own extraction and knowledge times. Therefore parsing admitted originals during the current run can create new run outputs after cutoff. Those outputs are neither newly retrieved pre-cutoff facts nor records eligible for historical SQL/memory retrieval. This is an interpretation of the cited workflow, not an additional historical waiver.

The report can use the fresh output of its current sealed-source computation. The same output, once stored as a fact, is unavailable to `query_canonical(cutoff=earlier_cutoff)` until both its true knowledge/first-seen and its selection time are eligible. Retrieving a pre-existing parser result, approved thesis or ledger version remains cutoff governed. A parser upgrade never grants its results an old knowledge time merely because the original document is old.

This bounded plan does not prove complete S11 manifest persistence, all ancillary retrieval filtering, S12 parser-result identity, or V12 exact historical package reconstruction. In particular comparator configs and management-ledger reads in the pipeline are additional shared seams: their owners must supply cutoff-safe pre-existing inputs before an entire run may claim historical replay compliance. Source admission proves this narrower boundary.

### Same-quarter local ledger replay compatibility

The accepted management-ledger identity is its complete anchored `GuidanceClaim`, not extraction-rule syntax. At the pipeline seam, a repeat of the same quarter may reuse the unchanged persisted ledger only when its retained `quarter_claims` contain complete claims and the newly extracted claim set is exactly equal in every field except the two honest acquisition observations `provenance.retrieved_at` and `provenance.first_seen_at`. Match stable claim keys and full validated model values; do not drop values, units, metric, horizon, scope, qualifiers, epistemic class, quote, source, content hash or locator fields. Legacy ledgers lacking complete retained claims receive no relaxed replay inference. Validate the reused provenance clocks as aware UTC and eligible for the current cutoff/current derivation before reuse. Current report guidance and source audits retain their new actual clocks; the unchanged ledger retains its original bytes and provenance as a reused persisted artifact. No fresh claim is assigned the older timestamps and the ledger's strict conflict checks remain unchanged.

Different rule syntax that produces exactly the same complete anchored output claim is not a ledger conflict under the existing contract. A rule change producing any different retained claim field remains a conflict. This does not certify which old parser/rule produced a legacy claim; durable producer identity remains separately unproved under eqos-unv. The coordinator's initial fix brief overrequired refusal for any rule change, which the approved ledger never recorded; that extra requirement is corrected here rather than invented as a new ledger contract. Cover identical local replay with advancing clocks, changed non-clock claim fields, unavailable legacy full claims, and semantically equivalent rule syntax. No ledger schema or implementation change is authorized.

## Candidate method: exact input references, one admission boundary

Introduce `src/fundamentals/api/source_admission.py`, keeping storage and parser schemas unchanged. The following are proposed APIs, not claims about existing interfaces:

| Interface | Contract |
|---|---|
| `RetainedSourceRef` | Frozen validated `source_id`, `surface`, `request_key`, `capture_id`, `source_sha256`, `record_sha256`. The four coordinates are passed exactly to existing `SnapshotStore.get_capture`; hashes pin integrity only. No datetime or authority-string field. |
| `SourceCaptureEvidence` / `SourceEvidenceResolver.resolve(ref) -> SourceCaptureEvidence` | Internal trusted composition-root evidence: source/hash, aware UTC successful completion `acquired_at` and system `first_seen_at`, exact reference binding. Only trusted direct synthetic tests supply this resolver here. Object validation does not establish authority; CLI cannot deserialize these evidence objects or select a resolver. |
| `PipelineSourceRefs` | Exactly one reference for each of `xbrl`, `results_pdf`, `transcript_pdf`; missing/duplicate/misbound entries refuse. |
| `AdmittedSource` | Source/hash, acquisition/first-seen times and binding; mode `trusted_direct` or `new_local_capture`. There is no native historical success mode in this packet. |
| `prepare_pipeline_sources(...) -> ContextManager[AdmittedPipelineInputs]` | Required keywords: `xbrl_bytes`, `xbrl_source_id`, `xbrl_sha256`, `results_pdf_path`, `results_pdf_sha256`, `results_source_id`, `transcript_pdf_path`, `transcript_pdf_sha256`, `transcript_source_id`, `cutoff`, `run_started_at`; optional `source_refs=None`, `evidence_resolver=None`, `clock=None` (a `Callable[[], datetime]`). Composition roots unpack existing XbrlInput; this module never imports pipeline.py, avoiding a cycle. Owns one local read per PDF, immutable XBRL bytes, all admissions and staged PDF lifetime. CLI samples actual run start before acquisition; direct pipeline samples before preparing. Production uses actual UTC; tests may inject a clock. |
| `AdmittedPipelineInputs` | Frozen run start/cutoff, all admitted bindings, pinned XBRL bytes and internally staged PDF paths. Produced only by the preparation context, consumed while it remains open. Bind config source IDs/hashes/cutoff before use. |
| `PipelineTemporalEvidence` / `FactTemporalAudit` | New result-only typed wrappers in `pipeline.py`: source/run/extraction clocks; per stored row persisted knowledge/first-seen, current derivation completion, selection action, `persisted_basis="unproved_producer"`, `historical_certification=False`. Never enrich or overwrite a legacy stored `Fact`. |

1. **Native references always refuse historical admission.** A native adapter performs only read-only resolution with `get_capture(ref.source_id, ref.surface, ref.request_key, ref.capture_id)` and ordinary `read_body(record)`; verifies exact coordinates, record/body hashes, outcome and rights, then raises typed `SourceAdmissionError` for missing completion/first-seen/registration proof. A fabricated old record with valid IDs/hashes still refuses. Consume the parallel completeness guard through `read_body`, never `read_evidence_body`; legacy effective completeness is compatibility, not proof. No arbitrary JSON importer, authority strings, digest-only certification or native successful-history test is authorized.
2. **Local fallback is current-run capture only.** Read each input once, hash those bytes, and sample actual completion/first-seen after the bytes are fully available. A new capture after a cutoff at/before run start refuses that run, even if adapter attempt time is earlier. Require both times ≤ cutoff. Bare `XbrlInput.retrieved_at`, publication/mtime and a CLI clock override are never proof. No fallback after an invalid retained reference. A future/current evaluation cutoff can admit a genuinely completed local capture, but this packet does not persist reusable capture registration or certify history for later runs.
3. **Pin bytes concretely.** Validate all three inputs before either PDF loader, XBRL parser or guidance/financial extraction runs. Then write the admitted PDF byte buffers into a random `TemporaryDirectory` with mode 0700, files created exclusively with mode 0600 and made read-only after writing/closing; keep paths internal and delete the directory on exit/refusal. Existing `load_pdf` receives only these private staged paths and admitted hashes. Never reopen caller PDF paths for parsing or rely on before/after hash checks. Original-path A→B→A substitution cannot affect this snapshot. XBRL uses the immutable admitted byte buffer with recomputed digest. Protect staging from external path replacement; no public staging-path override. These are ephemeral private directories, not CLI output/store directories.
4. **Separate derived output from persisted reuse.** Record actual extraction and reconciliation completion. New candidate facts use actual reconciliation knowledge/first-seen and admitted provenance; current-run reports use this derivation. `put` returns authoritative persisted facts/times, which may differ from the candidate. Read `get_selection_history(revision.content_identity)` and `get_canonical(revision.content_identity, cutoff=actual_decision_time)`; skip selection only when that effective revision is already the returned row. For A→B→A, append a new actual-time decision using `select_canonical(row_id, reason, selected_at=actual_decision_time, expected_selection_id=head_id)`; a stale predecessor or invalid clock refuses, without retry/backdating. Prior decisions/fact timestamps remain immutable. Never use the evaluation cutoff to decide current effective selection.
5. **Preflight CLI before mutable initialization.** Register only `--source-admission-manifest` and `--source-admission-store` (both optional, default None, required together when used) in existing `cli_parser.build_parser()` run arguments. Manifest is the three exact coordinate references above, rejects unknown fields/timestamp assertions; store option identifies the native read-only resolver root. `run_command` samples run start before input acquisition, validates config/issuer/quarter, resolves source references and enters `prepare_pipeline_sources` before output/store mkdir or `FactStore(...)`. Only after preparation succeeds may it open the store and call `run_pipeline(..., admitted_inputs=prepared)`. Pipeline consumes those pinned inputs without second admission/read; direct callers omit the optional keyword and preparation occurs before any parser or append to their already-open store. Preserve old direct `argparse.Namespace` callers via absent-option defaults. Native references refuse before store construction, even with valid retained bytes. Local XBRL no longer receives cutoff as retrieval time. This packet adds no retrieval/download functionality; live acquisition still has its existing source-side effects and supplies no historical proof.

**Persisted-fact limitation:** Current `Fact`/`StoredRevision` APIs cannot prove whether knowledge times came from the trustworthy producer or legacy cutoff backdating; hashes, parser version and `legacy_baseline` cannot distinguish that. Conservatively mark every returned persisted revision `unproved_producer` in the audit-only wrapper, including otherwise unchanged reuse. Preserve and expose its actual persisted times separately from current extraction; historical certification is blocked. This permits honest current derivation and unchanged-selection reuse without blessing old records. A legacy duplicate after reopen must return this explicit unproved basis; no fresh admission retroactively certifies it. No store/schema edit or full extraction-identity repair belongs here.

**Named follow-up requirement: TRUSTWORTHY_REUSABLE_TEMPORAL_INTAKE.** A separately reviewed production producer/verifier must bind exact bytes to completed acquisition, trustworthy first-seen and registration/availability, with durable retrieval and a proof of fact production when certifying persisted fact knowledge. Its exact proof interface does not exist in the inspected APIs. Coordinator will create the follow-up Beads item; this author creates none. Completing this packet does not complete that requirement, enable native historical success, or certify durable history. Synthetic direct resolver/clock injection remains composition-root authority and is never CLI datetime proof.

## File ownership and shared seams

**This session owns only:** `docs/plans/product-completion-temporal-admission.md`. All other files are read-only, including concurrent edits.

**Proposed implementation ownership, to be assigned before execution:**

| File | Responsibility |
|---|---|
| Create `src/fundamentals/api/source_admission.py` | Typed references, refusal-only native adapter, trusted direct resolver boundary, local admission and protected staged-byte context. No durable capture importer. |
| Modify `src/fundamentals/api/pipeline.py` | Consume/admit pinned inputs before extraction; actual output clocks, effective-selection reuse and typed audit-only unproved persisted basis. Shared with ledger/comparator work: one designated integrator applies the merged patch. |
| Modify `src/fundamentals/api/cli.py` | Preflight before output directories/store construction, forward admitted context without rereading, and honest local XBRL construction. |
| Modify `src/fundamentals/api/cli_parser.py` | Only register the two optional retained-reference run flags; preserve existing defaults/subcommands. Do not duplicate the parser in cli.py. |
| Create `tests/fundamentals/test_pipeline_temporal_admission.py` | Independent public `run_pipeline` boundary and persisted-store observations. |
| Create `tests/fundamentals/test_cli_temporal_admission.py` | Offline public CLI composition-root tests using synthetic local documents and native retained metadata. |
| Modify the eight existing caller test files named below | Explicit synthetic source evidence and independent clocks, limited to affected fixtures/calls; preserve assertions and concurrent behavior. |

The existing caller tests are `test_pipeline_e2e.py`, `test_phase05_report_artifact.py`, `test_phase05_management_ledger.py`, `test_phase05_run_comparatives.py`, `test_generalization.py`, `test_hardening.py`, `test_management_ledger_replay.py`, and `test_cli.py`, all under `tests/fundamentals/`. Coordinate the ledger files with their active owner; no competing writer. Existing `test_store_temporal.py` is read-only reference coverage.

**Forbidden implementation files:** `src/fundamentals/store/fact_store.py`, `src/fundamentals/store/snapshot_store.py`, `src/fundamentals/contracts/{fact,provenance,snapshot}.py`, `src/fundamentals/output/management_ledger.py`, `src/fundamentals/api/run_comparatives.py`, `src/fundamentals/api/config.py`, the XBRL/BSE adapters and extractor modules, other source/CLI modules, all existing Apar configs and approved evidence/theses, `.beads/`, harness files, lockfiles and dependency manifests. If the candidate needs any such edit, return the exact interface limitation to its owner before expanding scope. This is especially relevant to retained first-seen evidence and full S12 re-extraction identity.

## Ordered implementation tasks

### Task 1: Reject ineligible sources through the real pipeline

Goal: A post-cutoff or unproved historical XBRL, results PDF or transcript cannot enter numeric/guidance extraction or leave facts/ledger output behind; eligible synthetic retained inputs still render a report.

Files:
- Create: `src/fundamentals/api/source_admission.py`, `tests/fundamentals/test_pipeline_temporal_admission.py`.
- Modify: `src/fundamentals/api/pipeline.py`; affected deterministic caller fixtures from the owned file map in the same atomic integration group.
- Test: `tests/fundamentals/test_pipeline_temporal_admission.py`.

Interfaces:
- Consumes: existing `XbrlInput`, held PDF paths/hashes, `FundamentalsConfig.quarter.knowledge_cutoff`, `SnapshotStore.get_capture/read_body`, `CaptureRecord`, `Provenance`.
- Produces: `RetainedSourceRef`, `SourceCaptureEvidence`, `SourceEvidenceResolver`, `PipelineSourceRefs`, `AdmittedSource`, `prepare_pipeline_sources`, `AdmittedPipelineInputs`; optional `run_pipeline` keywords `source_refs`, `evidence_resolver`, `clock`, `admitted_inputs`. Reject incompatible prepared-context/ref/clock combinations rather than readmit.

Approach: Test-first tracer bullet. Author independent source-time/cutoff constants and synthetic PDFs/XML. Exercise current `run_pipeline` to establish a genuine behavior failure before adding optional metadata interfaces. Validate UTC, exact source hashes, successful evidence and each of the three source purposes. Build the native resolver with a strict unsupported-evidence refusal and the honest local fallback. Admission finishes before financial/guidance extraction or mutable output. Invalid source evidence never silently switches to local fallback.

Verification: `.venv/bin/python -m pytest -q tests/fundamentals/test_pipeline_temporal_admission.py` after confirming the existing interpreter is available; no install. RED: current public calls accept unproved old-cutoff sources and PDFs can be swapped between loader hash and open. GREEN: independently late XBRL/results/transcript refuse before any PDF loader or parser invocation; only trusted direct synthetic evidence can prove historical source eligibility, including equality at cutoff. Naive/non-UTC proof, wrong source/hash/digest, missing body, partial body and failed outcome refuse. An internally consistent fabricated old native capture refuses missing first-seen/registration/completion proof. New local capture finishing after cutoff at/before run start refuses. Failures append no revisions/selection transitions and leave ledger/report bytes unchanged.

Adversarial public-boundary proof: at the loader boundary replace the original PDF A with B before parser open, then restore A after open. Exercise results and transcript independently through `run_pipeline`, asserting either typed refusal or the admitted A values/anchors/hash; B must never reach extracted output. Repeat with permanent replacement. Observe actual parsed values, not merely a digest assertion. Loaders must receive only private staged paths; a later transcript refusal must occur before the results loader is called.

Test seams: Public `run_pipeline`, `PipelineResult`, `FactStore.get_revisions/get_selection_history`, reopened store, temporary ledger bytes. No private `_build_fact` assertions and no tests that merely compare implementation helper output to itself.

Dependencies: None.

Risks: Test-first. Optional signatures preserve source compatibility but historical success compatibility cannot be retained honestly. Native records lack first-seen: rejection is required when evidence cannot establish it. Tasks 1–2 are one atomic integration group because existing store/pipeline tests cannot safely promise intermediate historical timestamp behavior.

### Task 2: Keep source, extraction, fact and selection clocks separate

Goal: Trusted synthetic historical source admission renders fresh outputs with true times; newly persisted facts/selections remain absent from earlier as-of queries. Native historical success remains unsupported.

Files:
- Create: None.
- Modify: `src/fundamentals/api/pipeline.py`, `tests/fundamentals/test_pipeline_temporal_admission.py`, affected caller fixtures from the owned file map.
- Test: `tests/fundamentals/test_pipeline_temporal_admission.py`, existing `tests/fundamentals/test_store_temporal.py`.

Interfaces:
- Consumes: Task 1 `AdmittedSource`, existing `Fact`, `Provenance`, `FactStore.put/select_canonical/query_canonical/get_canonical`.
- Produces: `PipelineTemporalEvidence`, `FactTemporalAudit`, admitted provenance, actual new candidate fact times, unchanged effective-selection reuse and actual-time A→B→A decisions.

Approach: Use trusted direct synthetic resolver and clock injection to make five clocks independent. Record actual source extraction/reconciliation completions; use persisted `revision.fact` times on reuse separately from current derivation. Check effective current canonical row through the existing APIs before selection; pass the observed head selection ID for an actual transition. Do not interpret a found revision as a still-effective selection. Every returned persisted fact carries explicit unproved producer basis in the new audit wrapper; no old fact is mutated. Assert comparator/ledger behavior is preserved without claiming their historical admission repaired.

Verification: `.venv/bin/python -m pytest -q tests/fundamentals/test_pipeline_temporal_admission.py tests/fundamentals/test_store_temporal.py`. RED: current public calls backdate newly derived fact times and append decisions on unchanged reruns. GREEN: independently proven source times differ from actual extraction/fact/selection times; earlier as-of reads exclude new facts and later reads include them. Run A twice: unchanged effective row preserves revision timestamps and exact selection history. Run A→B→A: final A reuses its original immutable revision/times but appends a third actual-time selection; intermediate cutoffs still select B, earlier cutoffs A. Close/reopen before each assertion. Seed a synthetic legacy cutoff-backdated duplicate, reopen, then derive the same fact: original fact bytes/times remain unchanged, audit exposes `unproved_producer` and blocks historical certification despite newly valid source admission. Audit completion records this run, never the old fact knowledge time. Full parser extraction identity remains deferred.

Test seams: `PipelineResult.update`/stored revisions/temporal evidence and public as-of store reads after close/reopen. The RED oracle uses externally fixed source/run times, not config-derived timestamps.

Dependencies: Task 1; atomic integration with Task 1.

Risks: Test-first. The store's current value-based idempotency does not fully distinguish same-value parser upgrades; this packet must not claim S12 extraction identity completion. A backwards wall-clock or selection earlier than fact creation must fail, not backdate. Full historical replay also requires cutoff-safe comparator, ledger and prior narrative inputs from their owners.

### Task 3: Wire honest offline caller admission and integrate existing callers

Goal: Public CLI accepts exact retained-reference flags but refuses native history; eligible local capture stays honest. Direct synthetic composition-root evidence remains injectable; old Apar configs and approvals remain byte-identical.

Files:
- Create: `tests/fundamentals/test_cli_temporal_admission.py`.
- Modify: `src/fundamentals/api/cli.py`, narrowly `src/fundamentals/api/cli_parser.py`, `src/fundamentals/api/source_admission.py`, eight caller test files in the owned file map as necessary for explicit synthetic evidence.
- Test: New temporal tests plus named affected existing suites.

Interfaces:
- Consumes: Task 1 `RetainedSourceRef`, `PipelineSourceRefs`, `SourceEvidenceResolver`; Task 2 `PipelineTemporalEvidence`; existing config path methods and `XbrlInput`.
- Produces: Optional public `run` metadata-reference flags, validated exact-reference manifest resolution, honest local XBRL time and no-cutoff timestamp fallback.

Approach: Test-first offline `main(argv)` wiring through the existing parser; no alternate parser or mocked preparation/resolver proving success. Config/identity/reference and all-source preparation precede output/store mkdir and FactStore construction. Forward the admitted context unchanged into the pipeline; assert each original input is read once and parsing uses staged paths. Direct Namespace callers lacking new attributes retain omitted-option behavior. Synthetic old-cutoff success belongs only in direct resolver-injected pipeline tests; CLI old native metadata always refuses. Never change production cutoffs to rescue tests. Preserve financial/report/replay/comparator assertions and concurrent edits.

Verification: `.venv/bin/python -m pytest -q tests/fundamentals/test_cli_temporal_admission.py tests/fundamentals/test_pipeline_temporal_admission.py tests/fundamentals/test_store_temporal.py` is the mandatory public proof. Through `main(argv)`, prove both new flags are accepted by the real parser and a valid old native record reaches typed admission refusal, not an unknown-option failure. Omitted flags and direct omitted-keyword callers remain callable. CLI never accepts datetime/clock evidence. For each independently ineligible XBRL/results/transcript, test an absent database and a synthetic legacy database: absent DB/output directories remain absent; legacy DB schema, rows and bytes remain unchanged (no FactStore migration), with no selections, ledger or report writes. Use standard read-only SQLite inspection rather than opening FactStore to verify refusal. Observe FactStore constructor was never invoked. Eligible local capture uses a synthetic evaluation cutoff genuinely later than real acquisition and forwards the prepared bytes; no overridden production clock.

Separately run affected caller suites only after confirming public synthetic fixture paths; exclude/report private-dependent cases. Run with live/model opt-ins unset. Use existing ruff/mypy configuration on owned Python files; unavailable tools are reported, never installed. This planning session runs no product tests or git commands.

Test seams: Public CLI `main(argv)` return or typed refusal/exit behavior, temporary outputs and read-only database observations; direct `run_pipeline` for trusted resolver injection. Do not mock `_build_xbrl_input` to prove chronology or expose a test resolver/clock as CLI proof.

Dependencies: Tasks 1 and 2; native resolver must fail unsupported history before CLI integration.

Risks: Test-first. Old direct callers remain callable but may now reject; this is the intended honest compatibility limit. Active edits to pipeline and ledger tests require one integrator. Do not run private fixture suites or network/model opt-ins as a substitute for the named public synthetic tests; identify any unavailable private-dependent case in the result.

## Admission threat model, migration limits and decision gate

Assets are truthful temporal eligibility, immutable source bindings and earlier fact/selection/report history. External CLI metadata, supplied Python objects, local files and document text cross the evidence boundary. Abuse cases include an old arbitrary timestamp, a record digest with swapped bytes, an attempt that finishes after cutoff, a copied archive asserting original first-seen, and document instructions asking to relax cutoff. Validate typed references, UTC, identity/digest/outcome/rights and current trusted proof; keep text out of control policy. Bound metadata input size using existing local parsing conventions and retain source-purpose diagnostics without raw documents or credentials. No new authentication, upload endpoint or external service is introduced.

Native historical admission is refusal-only pending TRUSTWORTHY_REUSABLE_TEMPORAL_INTAKE. Existing config SHA-256 proves content integrity only. Preserve legacy fact bytes/times and expose unproved persisted producer basis in this packet's audit-only wrapper; this blocks historical certification rather than assigning that duty silently to another owner. No historical adapter/importer, durable proof persistence or database backfill is included. Ordinary successful CLI/store initialization may perform existing store migration after admission; refusal must precede initialization and perform none.

**Distinct product-owner question, required only for the real pilot demonstration:** Which exact successor evaluation contract, input versions and actual system-knowledge cutoff are accepted for `RETROSPECTIVE_WORKFLOW_DEMONSTRATION`, and what explicit method/scope disposition applies if the original phase gate requires unavailable historical capture? Gold §5 requires that decision. Neither this plan nor unchanged earlier exact-byte Apar approvals answers it. Continue engineering refusal-to-backdate repair independently; do not run the reviewed pilot sequence until successor acceptance is recorded.

**Implementation handoff condition:** assign exclusive shared-file ownership; coordinator re-reviews these corrections to the saved independent report; implement the atomic Tasks 1–2 group before Task 3. RED first exercises currently available public arguments with unproved historical inputs; missing proposed keywords/imports do not count as behavioral RED. Review must verify all five finding proofs above and no cutoff/publication/mtime fallback. This author uses no additional agents. Follow-up production proof and genuine successor/pilot acceptance remain separate requirements, not completion claims for this packet.
