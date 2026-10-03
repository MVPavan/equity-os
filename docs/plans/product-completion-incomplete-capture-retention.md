# Incomplete Upstox Capture Retention Implementation Plan

**Status:** PLAN_READY — implementation proposal; no product implementation or independent review performed in this planning pass.
**Origin:** User-assigned eqos-9xc packet under `docs/goals/equity-os-product-completion-gold.md`; retain available bounded/interrupted response evidence without changing factual authority.
**Goal:** Every attempted Upstox response retains its available bounded bytes and native typed outcome, distinguishes complete/partial/absent evidence, and excludes incomplete evidence from downstream replay.
**Out of scope:** New sources, source rights, authentication, broker execution, scheduling, live-source validation, replacement snapshot storage, private-document access, cloud, dependency installation, commits/pushes, and Beads writes in this planning pass.
**Constraints:** Preserve prior and concurrent edits. CLIENT_BLOCKED remains native nonretryable. No hidden retries. Preserve versioned captures and idempotency. Additive contracts stay within existing capture/source authority. Factual authority and human decision gates remain intact.

## Read-first implementation observations

These are current source observations, not claims that tests have passed:

| Seam | Observed behavior and implication |
| --- | --- |
| `src/fundamentals/ingest/upstox_source.py`: `_request_bytes`, `fetch`, `_retain_response`, `_refuse_terminal_status` | HTTPError bodies are read before status classification. Exceptions raised inside that handler bypass sibling exception handlers. Oversize/interrupted error reads can escape without a native refusal or retained capture. Success-body failures lose the bytes and status already available. Only the existing 429 loop retries requests; transport retryability metadata does not itself retry. |
| `src/fundamentals/ingest/http_session.py`: `read_bounded` | The actual imported helper performs one `read(max_bytes + 1)` and discards oversize bytes by raising. It does not retain exception partials or prove EOF after short reads. `upstox_transport.py` does not exist in this checkout; target this actual helper module, without creating a duplicate transport. |
| `src/fundamentals/ingest/upstox_retention.py`: `seal_capture` | Hashes supplied bytes into an ordinary BlobRef; no completeness distinction. Existing authority is `UPSTOX_RIGHTS`, citing `owner-decision-2026-09-04`. |
| `src/fundamentals/contracts/snapshot.py`: `CaptureRecord.make`, `record_sha256`, `derive_capture_id` | Version 1; frozen models; extra fields forbidden. IDs bind retrieval instant and body digest. The record digest includes serialized fields, so adding default serialized fields would change old digests and idempotency. |
| `src/fundamentals/store/snapshot_store.py`: `put_capture`, `read_body` | Existing immutable content-addressed blobs, staged atomic publication, hash/size verification and conflict detection are suitable. `read_body` currently returns every retained blob. |
| `src/fundamentals/ingest/upstox_candle_retention.py`: `candle_version`, `replay_candle_versions` | Checks successful outcome before parsing, but has no completeness gate. `read_tijori_capture` in `verify/three_source_inputs.py` also reads through SnapshotStore. A store read guard protects these consumers without changing other source policies. |
| `src/fundamentals/api/upstox_cli.py`: `_fetch_retained` | Republishes attached failed captures and reseals successes. Both source and CLI seals must produce identical version-2 metadata to avoid conflicts. |

The pre-code project overlay is not implementation evidence. Existing synthetic tests and source are the baseline. No old capture is opened or rewritten for planning.

## Settled representation and digest semantics

Use the existing `body: BlobRef | None` for retained bytes; add only completeness and a typed read issue. No second blob ledger and no claimed digest for unavailable original bytes.

| New API in `contracts/snapshot.py` | Contract |
| --- | --- |
| `BodyCompleteness(StrEnum)` | `COMPLETE="complete"`, `PARTIAL="partial"`, `ABSENT="absent"`. Complete means the response stream ended normally within the read budget; it does not mean the content parsed or was analytically accepted. |
| `BodyReadIssue(StrEnum)` | `LIMIT_EXCEEDED`, `READ_INTERRUPTED`, `NON_BYTES`, `READ_BUDGET_EXCEEDED`, with corresponding lower-case wire values. Independent of the native acquisition outcome. No arbitrary exception messages or header dumps. |
| `CaptureRecord.body_completeness: BodyCompleteness | None` | None only for legacy version 1. Required explicitly for version 2. |
| `CaptureRecord.body_read_issue: BodyReadIssue | None` | Version 2 read-failure reason; None for normal EOF or an HTTPError with no available body stream. Version 1 excludes this field. |
| `CaptureRecord.effective_body_completeness` | Version 2 returns its explicit state. Version 1 maps a body to legacy complete and no body to absent, preserving existing read behavior; this compatibility inference is not new proof of historical EOF. |
| `CaptureRecord.complete_body_sha256` | Returns the BlobRef digest only for effective COMPLETE; otherwise None. Consumers requiring original-response identity use this property after the replay guard. |
| `IncompleteSnapshotError(SnapshotError, ValueError)` | Typed refusal carrying capture ID/state, never response bytes. ValueError compatibility matches existing replay consumer catches. |

Version-2 invariants: COMPLETE requires a BlobRef, permits zero-byte `b""`, and requires no read issue. PARTIAL requires a nonempty BlobRef and a read issue. ABSENT requires `body is None`; it can have a read issue when the attempt failed before any bytes were available. PARTIAL/ABSENT cannot carry `OutcomeCode.OK` or `OK_EMPTY`. HTTP error responses can be COMPLETE while their acquisition outcome is failed. An empty but interrupted stream is ABSENT, not a fabricated complete empty response.

`BlobRef.content_sha256` always hashes exactly the retained bytes; its byte_count is their length. For PARTIAL this is a prefix/evidence digest, never the complete original-response digest. `record_sha256` binds the completeness and read issue for version 2. Keep `derive_capture_id` and blob addresses unchanged: same instant/prefix with different completeness is a record conflict, never an overwrite. Distinct retrieval instants retain separate attempts even when bytes are identical.

### Serialization and migration

Keep request-identity schema version 1 and existing `CaptureRecord.make(...)` callers defaulting to version 1. Introduce a separate `CAPTURE_SCHEMA_VERSION = 2`; do not globally bump `SCHEMA_VERSION`, which also participates in request hashing. Extend `CaptureRecord.make` with keyword-only schema_version/body_completeness/body_read_issue parameters. Upstox `seal_capture` explicitly produces version 2; unchanged source lanes continue producing version 1.

Extend `seal_capture` with keyword-only `body_completeness: BodyCompleteness | None = None` and `body_read_issue: BodyReadIssue | None = None`. Its compatibility default maps supplied bytes to COMPLETE and None to ABSENT for existing complete-only success resealers. The source always passes explicit state for both successes and failures; a failed source read never uses that default. The CLI failure path republishes the attached record without resealing it. This preserves the current CLI API without an extra shared-path edit.

Accept only capture versions 1 and 2. Validate that version 1 has no non-None new metadata; serialize version 1 with both new fields omitted using the model serializer, including nested serialization. Its canonical JSON shape, record_sha256, request hash and capture ID must remain unchanged. Serialize version 2 with explicit completeness and nullable read issue. Unknown versions and inconsistent states fail closed. Version-2 absence of completeness is a validation error, not a guessed default.

Migration is read compatibility plus new Upstox writes; there is no on-disk rewrite, relabeling of old evidence, rehash, or directory rename. Old code cannot read version-2 records because of extra-field refusal: deploy the updated capture reader and replay guard with the writer as one atomic integration group. Rollback to an old reader cannot interpret the new records; preserve them and restore the compatible reader rather than deleting or converting them.

## Bounded read contract

Add `BoundedBodyRead` as a frozen dataclass in `http_session.py`, with `raw_body: bytes | None`, `completeness: BodyCompleteness`, and `issue: BodyReadIssue | None`. Add `read_bounded_capture(response: ReadableResponse, max_bytes: int, *, timeout_seconds: float, expected_bytes: int | None = None) -> BoundedBodyRead`. Capture enums are bottom-layer imports, with no lane import. Keep existing `read_bounded` behavior and callers unchanged; Upstox alone adopts the new helper.

1. Read chunks up to 64 KiB, accumulating a contiguous prefix until `b""` proves EOF. Short reads are not EOF. Request no more than the remaining `max_bytes + 1` observation budget. At most `max_bytes` bytes are retained; the one-byte overflow probe is deliberately discarded and represented by LIMIT_EXCEEDED. Stop immediately on overflow; never drain the rest of a response.
2. On `http.client.IncompleteRead`, append its bytes-valued `.partial` from the failed read to the already-returned prefix, within the cap. Explicitly handle the known Python chunked-reader wrapper: its outer partial contains completed chunks and its immediate `IncompleteRead` cause may contain additional contiguous interrupted-chunk bytes. Append both disjoint segments within the remaining cap for that known wrapper; do not concatenate arbitrary exception chains or duplicate segments. Prove this with a real `HTTPResponse` backed by a synthetic socket/file, including cap clipping. Handle `URLError`, TimeoutError and OSError similarly, using bytes-valued `.partial` only if supplied. A nonbytes return or nonbytes partial is NON_BYTES, preserving the prefix already obtained. Catch these specific expected read failures; unexpected exceptions and process cancellation propagate.
3. If valid nonnegative Content-Length was available before reading, pass it as expected_bytes and require matching length at EOF. It never changes the cap or allocates a buffer. A mismatch is READ_INTERRUPTED; a length above the cap still allows bounded prefix retention. Ignore malformed length as unavailable framing, with no inference from it. HTTP transfer framing remains urllib's responsibility; no new HTTP parser.
4. Stop after 1,024 read calls or when elapsed monotonic read time reaches timeout_seconds; mark READ_BUDGET_EXCEEDED. Check time before each read and after it; even a late EOF is refused after the deadline. Reads use the existing opener/socket timeout. No thread, hidden retry, second opener call, or new scheduling policy. The deadline is checked only between helper read calls; an individual read can outlast it indefinitely while underlying reads continue making progress. Do not advertise strict cancellation or a strict wall-clock bound against a malicious slow stream.
5. With normal protocol-conforming reads, helper-owned peak payload storage is at most `2 * max_bytes + 64 KiB + 1` during conversion, plus fixed bookkeeping; there is no list of all chunks. The cap does not claim to bound allocations already made inside urllib or an exception's `.partial`. Discard transient probe/exception references promptly. SnapshotStore verification has its existing bounded-by-blob copies; this is not a claim of total process RSS.

Enforce UpstoxConfig ceilings of 32 MiB compressed/retained body and 192 MiB decompressed body, matching current defaults; positive smaller limits remain valid. There is no decompression in the capture reader. Partial gzip evidence stays compressed and is never sent to catalog decompression. Preserve the existing 120-second request-timeout ceiling and all pacing, request-count and 429 budget limits. Consume/dispose each failed attempt before starting its permitted retry; close HTTPError streams in a finally block and do not keep prior response payloads on the source.

## Outcome precedence and refusal

Capture status/media type/encoding before reading. Classify HTTP errors by status independently of body-read success; attach body completeness/issue and retained metadata to the resulting UpstoxFetchError before publication.

| Response/attempt | Raised outcome and evidence behavior | Requests |
| --- | --- | --- |
| 403 or 451, with complete/oversize/interrupted/nonbytes/no stream body | `UpstoxBlockedError`; native `CLIENT_BLOCKED`; retryable False. Preserve available prefix and actual status. Read issue cannot replace the block. | Exactly one. |
| 401 with any body state | `UpstoxAuthExpiredError`; native AUTH_EXPIRED; retain actual status and body evidence. | Exactly one. |
| Other nonredirect HTTP error except 429 | Existing REQUEST_REJECTED outcome; retain body/read issue. | Exactly one. |
| 429 with any body state | Native RATE_LIMITED retained once for each actual attempt before existing backoff. Keep only the already-configured bounded 429 loop, including exhaustion. Incomplete body does not add a retry or reset its budget. | Existing configured count only. |
| 2xx with normal bounded EOF | Existing successful UpstoxFetch; version-2 COMPLETE, even for empty bytes. Parser failure remains separately typed downstream. | Exactly one. |
| 2xx with LIMIT_EXCEEDED, READ_INTERRUPTED or READ_BUDGET_EXCEEDED | UpstoxFetchError/TRANSPORT_ERROR, actual status retained; PARTIAL if bytes exist, otherwise ABSENT. No successful UpstoxFetch. | Exactly one; retryable metadata does not schedule a retry. |
| 2xx with NON_BYTES | Existing SCHEMA_DRIFT outcome; preserve any prefix and status. | Exactly one. |
| Opener fails before a response exists | Existing TRANSPORT_ERROR with ABSENT, no invented status/header/body; attach READ_INTERRUPTED when failure is an expected transport exception. | Exactly one. |

Redirects remain outcome-free UpstoxRedirectError, checked before reading; no redirect target is followed or new classified capture manufactured. Credentials, origin and run-budget refusals stay pre-attempt/outcome-free. No status is inferred from body text and no new block detector is introduced.

`fetch` and `_retain_response` pass the explicit read state to `seal_capture`; failed errors carry `body_completeness` and `body_read_issue` alongside existing raw_body/http_status/media_type/content_encoding/capture_record. Do not read a failed stream again while attaching metadata. Publish exactly once per attempt; outer fetch/CLI reuse the attached record. Exhausted 429 errors copy all metadata from the last recorded attempt, including status/encoding/state, rather than only its bytes.

Persistence failures propagate as the existing `SnapshotError` subclasses and raw `OSError` failures; the implementation must not report successful durable retention or continue a retry after publication fails. Do not replace the acquisition outcome with an invented status; keep the acquisition refusal as exception context when storage publication fails.

## Safe replay and evidence inspection

Make `SnapshotStore.read_body(record)` require effective COMPLETE before exposing bytes to existing parsers. ABSENT keeps MissingSnapshotError; PARTIAL raises IncompleteSnapshotError. Add `read_evidence_body(record)` for explicit private inspection of retained complete/partial bytes, using the same path/symlink/hash/size verification; absent still raises MissingSnapshotError. This API does not make data eligible for analysis.

Add an explicit completeness check at the start of `candle_version` so refusal is a CandleReplayError even if a caller supplies inconsistent success metadata. `replay_candle_versions` continues skipping non-success acquisition outcomes; incomplete failures remain in `list_captures`, never in CandleSeriesVersion or composed coverage. Complete malformed captures retain their existing replay failure behavior. Neither a parseable partial JSON prefix nor a partial gzip document establishes facts, observations, coverage or a complete source digest.

The centralized guard covers `read_tijori_capture` without changing its authority or parser. Exercise that consumer's error translation with synthetic injected records. Compatibility Upstox crosscheck replay uses its existing complete UpstoxFetch artifact path; no new artifact format or fallback to partial blobs is introduced. Validate its existing no-fetch/no-credentials tests rather than rebuilding that replay subsystem.

## File map before tasks

| File | Single responsibility in eventual implementation |
| --- | --- |
| `src/fundamentals/contracts/snapshot.py` | Completeness/read-issue enums, v1/v2 validation/serialization, complete digest property and typed incomplete refusal. |
| `src/fundamentals/store/snapshot_store.py` | Guard ordinary reads and expose verified evidence reads; retain storage layout and publication machinery. |
| `src/fundamentals/ingest/http_session.py` | Add bounded evidence reader without altering legacy read_bounded. |
| `src/fundamentals/ingest/upstox_retention.py` | Seal explicit version-2 read state under existing rights. |
| `src/fundamentals/ingest/upstox_source.py` | Status precedence, partial attachment, ceilings, stream closure and unchanged retry decisions. Coordinate this already-dirty path with its current writer before execution. |
| `src/fundamentals/ingest/upstox_candle_retention.py` | Explicit replay refusal before candle parsing. |
| `tests/fundamentals/test_phase3_snapshot.py` | Legacy digest/idempotency and complete/partial/absent storage contracts. |
| `tests/fundamentals/test_http_session.py` | Synthetic chunk/read-failure and consumption-budget proofs. |
| `tests/fundamentals/test_upstox_source.py` | Public typed refusal, pacing/retry and configuration proofs. |
| `tests/fundamentals/test_upstox_retention.py` | End-to-end prefix retention, replay exclusion and version preservation. |
| `tests/fundamentals/test_upstox_capture_integration.py` | Real-source synthetic opener plus shared store/CLI integration. |

Existing `tests/fundamentals/test_phase3_tijori_retention.py`, `test_upstox_cli.py`, and `test_upstox_crosscheck_replay.py` are regression-only dependencies; no changes planned. No dependency or lockfile changes. This planning pass owns only this document.

## Implementation tasks

### Task 1: Preserve incomplete evidence through the public fetch boundary

Goal: A synthetic oversized 403 retains its bounded prefix as PARTIAL in the existing store and raises native nonretryable CLIENT_BLOCKED; complete successes and legacy captures remain readable and idempotent.

Files:
- Create: None.
- Modify: `src/fundamentals/contracts/snapshot.py`, `src/fundamentals/store/snapshot_store.py`, `src/fundamentals/ingest/http_session.py`, `src/fundamentals/ingest/upstox_retention.py`, `src/fundamentals/ingest/upstox_source.py`.
- Test: `tests/fundamentals/test_phase3_snapshot.py`, `tests/fundamentals/test_http_session.py`, `tests/fundamentals/test_upstox_source.py`, `tests/fundamentals/test_upstox_retention.py`.

Interfaces:
- Consumes: Existing RequestIdentity, BlobRef, OutcomeRecord, SnapshotRights, CaptureRecord.make, SnapshotStore.put_capture/read_body, ReadableResponse and UpstoxSource.fetch.
- Produces: BodyCompleteness, BodyReadIssue, CAPTURE_SCHEMA_VERSION, IncompleteSnapshotError, CaptureRecord fields/properties/keyword extensions, SnapshotStore.read_evidence_body, BoundedBodyRead, read_bounded_capture and version-2 seal_capture keyword parameters; failed-fetch completeness/issue attributes.

Approach: Test-first tracer bullet across source, sealing and store. Add the explicit v1-preserving serializer before enabling v2 writes. Implement the bounded helper and status-before-read handling without moving adapter status semantics into http_session. Pass explicit COMPLETE from successful source acquisition and explicit failed state from errors; existing complete-only CLI resealing uses the documented seal_capture compatibility default. Keep the legacy helper unchanged. Source writer and shared-contract/store writer must integrate with current source/CLI resealers; this task is one atomic integration group, not separately deployable horizontal fragments.

Verification: `.venv/bin/pytest -q tests/fundamentals/test_phase3_snapshot.py tests/fundamentals/test_http_session.py tests/fundamentals/test_upstox_source.py tests/fundamentals/test_upstox_retention.py` — passes, after recording the named new RED failures against baseline.

Test seams: Public source.fetch with a scripted synthetic urllib opener; HTTPError backed by BytesIO; CaptureRecord.model_validate_json/model_dump; store.put_capture/get_capture/read_body/read_evidence_body. Freeze clocks and capture request counts; no network or real credential factory.

Named RED tests: `test_oversized_403_retains_prefix_and_native_nonretryable_block`; `test_partial_evidence_is_refused_by_read_body_but_inspectable`; `test_v1_canonical_digest_and_republication_do_not_change`; `test_v2_state_invariants_and_unknown_versions_are_refused`; `test_v2_prefix_digest_never_claims_complete_body_digest`; `test_v1_nested_serialization_omits_new_metadata`; `test_new_upstox_complete_capture_republication_is_idempotent`.

Dependencies: None in code; before execution, obtain exclusive ownership of the named dirty/shared paths and a current reviewed implementation packet through the coordinator. No new Beads dependency is written here.

Risks: Test-first required. Record identity drift, false complete evidence and loss of CLIENT_BLOCKED are material failures. Preserve unrelated current edits rather than rewriting whole modules.

### Task 2: Prove interrupted success/error behavior and finite consumption

Goal: Every expected read failure retains only demonstrably available prefix bytes with actual status and a typed read issue, and request/read/memory budgets cannot silently expand.

Files:
- Create: None.
- Modify: `src/fundamentals/ingest/http_session.py`, `src/fundamentals/ingest/upstox_source.py`.
- Test: `tests/fundamentals/test_http_session.py`, `tests/fundamentals/test_upstox_source.py`, `tests/fundamentals/test_upstox_retention.py`.

Interfaces:
- Consumes: BoundedBodyRead, read_bounded_capture, BodyCompleteness/BodyReadIssue and UpstoxFetchError state from Task 1; existing UpstoxConfig/429 counters.
- Produces: Proven stream-partial exception handling, configuration ceilings, failure metadata propagation, stream closure and finite read-call/deadline behavior described above; no additional public API.

Approach: Extend the same helper/source integration with adversarial synthetic streams. Include a first successful chunk followed by IncompleteRead.partial, a TimeoutError after a chunk, an interruption before bytes, and a nonbytes chunk after bytes. Never catch BaseException. Parameterize terminal 403/451/401/other status with each body failure and no fp. Exercise complete and incomplete 429 retries/exhaustion under the same configured count, and storage failure before retry, including raw `OSError` injected during publication of a retained 429 attempt. Cover Python chunked-response outer/inner `IncompleteRead` partials using a socket-free real `HTTPResponse`; retained `abcde` (and a clipped variant) must remain PARTIAL/READ_INTERRUPTED with actual 403, native CLIENT_BLOCKED, one request and stream closure. Script EOF and monotonic time; avoid real sleeps or allocating maximum-size bodies in tests.

Verification: `.venv/bin/pytest -q tests/fundamentals/test_http_session.py tests/fundamentals/test_upstox_source.py tests/fundamentals/test_upstox_retention.py` — all named cases pass with exact opener/read-call bounds and typed outcomes.

Test seams: Synthetic ReadableResponse.read, IncompleteRead.partial, fake monotonic clock, opener calls, patched sleep and HTTPError.close. Public UpstoxConfig validation and fetch exceptions expose the decisions.

Named RED tests: `test_short_read_requires_eof_before_complete`; `test_read_at_cap_probes_eof_and_over_cap_retains_only_cap`; `test_incomplete_read_appends_only_unreturned_partial`; `test_chunked_http_response_preserves_outer_and_inner_disjoint_partials`; `test_200_interruption_retains_status_and_prefix_without_retry`; `test_nonbytes_after_prefix_retains_prefix_and_schema_drift`; `test_empty_interruption_is_absent_not_complete_empty`; `test_content_length_mismatch_is_incomplete`; `test_read_call_and_elapsed_budgets_stop_dribbling_stream`; `test_terminal_status_wins_over_each_body_read_failure`; `test_incomplete_429_preserves_exact_existing_retry_budget`; `test_http_error_stream_is_closed_on_all_exits`; `test_storage_failure_stops_retry_and_preserves_refusal_context`; `test_config_refuses_body_limits_above_hard_ceilings`.

Dependencies: Task 1.

Risks: Test-first required. An exception's partial bytes must not be appended twice; buffering must stop on the first bounded failure. The between-read deadline is not strict cancellation. Tests must expose that limitation instead of claiming a stronger guarantee.

### Task 3: Prove replay exclusion and integrated compatibility

Goal: Partial evidence cannot produce a candle version, coverage, parsed source facts or a successful CLI acquisition; later complete versions remain replayable and unchanged legacy captures retain their prior identities.

Files:
- Create: None.
- Modify: `src/fundamentals/ingest/upstox_candle_retention.py`.
- Test: `tests/fundamentals/test_upstox_retention.py`, `tests/fundamentals/test_upstox_capture_integration.py`, `tests/fundamentals/test_phase3_snapshot.py`.

Interfaces:
- Consumes: CaptureRecord.effective_body_completeness/complete_body_sha256, IncompleteSnapshotError, SnapshotStore read APIs, existing candle_version/replay_candle_versions, and CLI attached-record republication.
- Produces: Explicit CandleReplayError for incomplete input; regression evidence for existing CandleReplayResult, CLI retention and shared-store consumers. No new workflow/store architecture.

Approach: Test-first with a prefix that itself parses as valid JSON, proving that parsing cannot override completeness. Keep failed attempts inspectable through list_captures/read_evidence_body; never include them in versions/coverage. Follow an incomplete attempt with a complete response for the same series and verify both immutable records and unchanged later replay. Inject an inconsistent success record at the defensive read seam to exercise the guard even though v2 construction refuses it. Test read_tijori_capture's existing ValueError translation using synthetic inputs. Run existing CLI success/reseal, failed attached-capture, no-fetch and no-credentials regressions; change shared CLI code only if a failing test proves a metadata propagation defect, then coordinate that exact file with its owner before editing.

Verification: `.venv/bin/pytest -q tests/fundamentals/test_phase3_snapshot.py tests/fundamentals/test_http_session.py tests/fundamentals/test_upstox_source.py tests/fundamentals/test_upstox_retention.py tests/fundamentals/test_upstox_capture_integration.py tests/fundamentals/test_phase3_tijori_retention.py tests/fundamentals/test_upstox_cli.py tests/fundamentals/test_upstox_crosscheck_replay.py` — all pass without source/auth calls.

Test seams: SnapshotStore public reads/listing, candle_version/replay_candle_versions, read_tijori_capture and production CLI dispatch with injected synthetic source/openers. Use fixture tokens only; no real source documents.

Named RED tests: `test_parseable_partial_json_cannot_become_candle_version`; `test_partial_gzip_is_never_decompressed_or_parsed`; `test_incomplete_attempt_keeps_later_complete_series_version`; `test_partial_capture_is_translated_to_unreadable_tijori_input`; `test_partial_then_complete_same_instant_is_conflict_not_overwrite`; `test_cli_failed_capture_republication_preserves_completeness_and_digest`; `test_capture_versions_share_blob_without_overwriting_evidence_state`.

Dependencies: Tasks 1 and 2; current capture/replay baseline interfaces must remain available. No new source rights or human analytical decision is a prerequisite to these synthetic repairs.

Risks: Test-first required. Some existing readers use raw compatibility artifacts rather than SnapshotStore; do not add a partial-artifact route or pretend the guard validates independently supplied files. Exclusion must be enforced before decoding, not after parse success.

## Verification, unresolved choices and handoff

Implementation verification uses the existing environment only: if `.venv/bin/pytest`, `.venv/bin/mypy`, or `.venv/bin/ruff` is unavailable, report the missing tool and do not install it. After the scoped regression above, run `.venv/bin/mypy --strict src/fundamentals`, and `.venv/bin/ruff check` plus `.venv/bin/ruff format --check` on the explicitly modified Python files and tests. Record commands, exit statuses and any concurrent baseline failures separately. Check `git diff --check` and `git status --short` before the implementation verdict. Do not claim full Gold completion from this packet.

No unresolved product representation choice remains in this proposal: explicit three-state evidence, typed read issue, v2 Upstox writes/v1-preserving reader, prefix digest semantics, centralized replay refusal and unchanged retry policy are selected. An implementer must resolve two operational facts before editing: current ownership of already-dirty source/retention/store integration paths, and availability of the existing local verification tools. These do not authorize changing another worker's code or adding dependencies. If either prevents the packet, return NEEDS_CONTEXT with that exact fact; do not invent a new contract or scheduling lane.

Independent plan critique and fresh-context authoring exercise are intentionally unperformed because this task explicitly prohibits subagents. The plan is self-reviewed, not independently approved. The coordinator retains the existing implementation/review/human gates and decides when this concrete packet is eligible for execution. No Beads state was changed and no authority was promoted.

**Next execution surface:** task-scope execution of eqos-9xc, starting with Task 1's named RED tests after shared-path ownership and the current review gate are satisfied. Planning output: PLAN_READY.

## Independent review corrections

The independent review at `scratchpad/execution/product-gold-second-batch/response-plan-review-report.md` found one important interrupted-chunk retention gap and two factual wording errors. This revision incorporates its exact known-wrapper handling and socket-free boundary test, the actual between-read deadline limitation, and propagation of raw OS publication errors. Coordinator document review confirms these corrections remain within the original bounded contract; implementation still requires RED/GREEN evidence and independent spec and quality review.
