# Filing ingestion, immutable documents, point-in-time capture, and conditional audio

**Spec ID:** S09
**Status:** DRAFT — AWAITING FRESH SOL XHIGH REVIEW
**Activation classification:** Mixed — A-06, B-09, and C-02 are active; C-14 is Deferred
**Exact path:** `docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md`

## Contract status and authority

This document is an implementation contract, not evidence of register
acceptance or activation of conditional audio. The implementation decision
register v2 owns operational decision and gate wording. The disposition
report records the referenced audit decisions. The activated goal supplies
the exact S09 identity and ownership. A fresh Sol xhigh review can grant only
delegated artifact approval. This draft claims neither delegated approval nor
provider, data-rights, analyst, domain, security, budget, or activation
authority.

### Exact ownership and source text

| Register ID | Blueprint phase | Priority | Decision or action — exact register text | Required evidence / acceptance — exact register text | Dependencies — exact register text | Activation status | Current source status |
|---|---|---:|---|---|---|---|---|
| A-06 | 0A | Critical | Run filing-channel-aware XBRL-versus-PDF spike | Coverage matrix by company, quarter, filing channel, taxonomy/version, statement, segment, note, ownership/share count, restatement behavior, mapping stability, and reconciliation effort | A-02 | Open | Open |
| B-09 | 0.5 | High | Start point-in-time capture | Daily/event jobs persist approved membership/security changes, prices, announcements, corporate actions, shareholding changes, hashes, first-seen times, and capture failures | A-05 | Open | Open |
| C-02 | 1 | Critical | Build immutable document registry and object store | Original files, URLs, timestamps, hashes, parser versions, extraction warnings, and first-seen times are preserved | A-05 | Open | Open |
| C-14 | 1 | Medium | Add official-audio transcription where needed | Original audio, model/version, timestamps, confidence, and correction history are preserved | C-02, B-08 | Deferred | Deferred |

The exact program assignment is: **S09 — Filing ingestion, immutable
documents, point-in-time capture, and conditional audio**, with primary
register IDs **A-06, B-09, C-02, C-14** and disposition references **M-9,
R-2**. The pinned snapshot makes S09 mixed: it may specify and later implement
the active A-06/B-09/C-02 scope, but it may specify only the dormant behavior
and activation gate for C-14. Nothing in this spec activates C-14.

| Disposition ref | Exact heading | Exact disposition | Binding effect in this contract |
|---|---|---|---|
| M-9 | Untrusted-document surface | Accept. | Source content remains data, cannot alter control state or invoke execution/secrets, and supplies prompt-injection/source-confusion golden cases. |
| R-2 | Add filing channel and taxonomy version to A-06 | Accept. | Distinguish exchange quarterly-result XBRL, annual channels, issuer documents, and taxonomy/version changes; measure mapping stability, not only field coverage. |

## Scope

### Active scope

1. Define and execute a filing-channel-aware XBRL-versus-PDF coverage spike
   for the selected discovery company and four consecutive quarters.
2. Register original document bytes immutably with acquisition/source
   metadata, content hashes, parser versions, extraction warnings, and
   first-seen knowledge time.
3. Start daily/event-driven point-in-time capture for approved
   membership/security changes, prices, announcements, corporate actions, and
   shareholding changes, recording both successes and failures.
4. Treat every document, parsed field, and retrieved passage as untrusted data
   and preserve exact provenance from derived artifacts to source locations.

### Dormant conditional scope

C-14 defines an official-audio transcription contract only. No audio fetch,
storage, transcription, provider selection, expense, job, migration, or
production dependency may be planned or implemented until the Deferred
activation guard passes and the register is validly reconciled.

### Non-goals

- S09 does not choose the discovery company, approve source/provider rights,
  define fact identity, select an entity/security authority, or implement the
  earnings-review workflow.
- The A-06 spike measures coverage and reconciliation effort; it does not
  declare XBRL or PDF universally authoritative and does not freeze the final
  fact schema.
- Point-in-time capture prevents future loss; it is not a claim to have
  recreated unavailable historical data.
- Parsed text cannot issue tool instructions, override cutoffs, change
  permissions or promotion rules, access secrets, or authorize execution.
- C-14 dormancy cannot be bypassed because audio is available, convenient, or
  mentioned in a source.

## Interfaces and data contracts

### `FilingCoverageObservation`

Every matrix cell contains `coverage_observation_id`, `company_id`, quarter,
filing channel, source document ID, format (`XBRL`, `PDF`, or another explicit
format), taxonomy name/version when applicable, statement coverage, segment
coverage, note coverage, ownership/share-count coverage, restatement behavior,
mapping-stability result, reconciliation effort, observed gaps, warnings,
evidence refs, and assessor timestamp. Non-applicable taxonomy is explicit;
unknown and absent are distinct.

The filing-channel vocabulary must distinguish at minimum exchange
quarterly-result XBRL, annual filing channels, issuer-hosted documents, and
their taxonomy/version changes. A channel/format comparison is reported per
company and quarter; no aggregate score may hide a missing statement, segment,
note, ownership/share-count, or restatement case.

### `AcquisitionAuthorization`

Every acquisition/capture attempt binds one current authorization snapshot
containing `authorization_id`, exact source/provider/use scope, access,
automation, caching, retention, derived-output, and redistribution decisions,
`rights_policy_ref`, `data_rights_approval_record_id`,
`provider_authorization_applicability`,
`provider_authorization_applicability_evidence_ref`, nullable
`provider_authorization_record_id`, `evaluated_at`, and `valid_until`.
`provider_authorization_applicability` is closed to `REQUIRED`,
`NOT_REQUIRED`, or `UNKNOWN`. `REQUIRED` demands a current matching
`PROVIDER_AUTHORIZATION`; `NOT_REQUIRED` demands current authoritative policy
evidence for that exact scope and has a null provider record; `UNKNOWN`, a
missing applicability field/basis, an inapplicable record shape, stale
evidence, or expired authorization blocks acquisition. Absence never defaults
to `NOT_REQUIRED`.

### `TransformationAuthorization`

Every parse or re-extraction request binds one immutable authorization
snapshot that is current for the exact transformation. It contains
`transformation_authorization_id`, `authorization_snapshot_sha256`,
`document_id`, matching `original_content_sha256`, the historical
`acquisition_authorization_id`, exact source/provider/use scope, operation
(`PARSE` or `REEXTRACT`), parse purpose/schema version, permitted derived-output
types and consumers/destinations, permitted retention class/destination and
deadline, `rights_policy_ref`, `data_rights_approval_requirement_id`,
`data_rights_approval_record_id`,
`provider_authorization_applicability`,
`provider_authorization_applicability_evidence_ref`, nullable
`provider_authorization_requirement_id`, nullable
`provider_authorization_record_id`, `authority_input_digests`, `evaluated_at`,
`valid_from`, and `valid_until`. Every referenced policy, applicability,
approval requirement, approval record, and provider requirement/record has its
exact current content digest in
`authority_input_digests`. That object has exactly the
`rights_policy_ref`, `data_rights_approval_requirement_id`,
`data_rights_approval_record_id`, and
`provider_authorization_applicability_evidence_ref` keys, plus the
`provider_authorization_requirement_id` and
`provider_authorization_record_id` keys when applicability is `REQUIRED`;
every value is the lowercase SHA-256 of the referenced current object's
canonical content. `REQUIRED` provider applicability requires both provider
requirement/record fields to be non-null; `NOT_REQUIRED` requires both to be
null and retains the authoritative applicability evidence; `UNKNOWN` blocks
authorization.
`valid_until` is the earliest non-null expiry among the applicable
transformation, derived-output, retention, rights, and provider authorities; it
is null only when each authoritative input explicitly has no expiry. A missing
or unknown expiry blocks authorization.

`authorization_snapshot_sha256` is lowercase SHA-256 of canonical JSON for
all snapshot fields listed above except that digest itself. Before parser
invocation and again before any output becomes consumable, the validator
recomputes the snapshot digest, resolves every authority input from its
authoritative store, and requires matching live content digests, exact
document/hash and operation/output/retention scope, and a current validity
window. For each bound approval, the validator resolves the exact requirement
ID and requires `status=SATISFIED`; its non-null `matched_record_id` must equal
the bound record ID and identify one current record with `decision=APPROVED`.
The requirement and record must match exactly on approval type, required
authority/authority, scope, actor, timestamp, and evidence; the record's
`authority_source` must be `HUMAN_RESOLUTION`. Each data-rights or provider
record must in turn resolve, by its bound decision ID and content digest, to the
current active immutable human resolution with
`decision_type=SATISFY_APPROVAL`, the same scope and authority basis, and a
competent human actor. Validation covers the complete approval inventory: one
requirement matches exactly one record/resolution, and no approval record ID or
resolution decision ID may match a second requirement. Missing or unmatched
requirements, a non-`SATISFIED` status, a non-`APPROVED` record, a stale or
wrong-purpose resolution, digest staleness, expiry, revocation, supersession,
field mismatch, reuse, or scope mismatch rejects the request; a mid-attempt
failure leaves the attempt `FAILED` and no output consumable. An
acquisition-time authorization is historical provenance only and never
substitutes for this current check.

Renewal appends a new `TransformationAuthorization` with a new ID and digest,
even when only an expiry changes. It never mutates or silently refreshes an old
snapshot. A later parse/re-extraction must bind the renewed snapshot; prior
attempt records, historical output hashes, and the `SourceDocument` acquisition
authorization remain immutable audit evidence. Derived-output bytes remain
subject to their bound retention policy. Continued retention or use after the
bound authorization ceases to be current fails closed, and a renewal does not
silently reauthorize the old attempt or output. This does not rewrite
acquisition-time provenance or assert retention of original bytes beyond their
separately authorized policy.

### `SourceDocument`

| Field | Contract |
|---|---|
| `document_id` | Stable internal identifier for one acquired byte sequence. |
| `source_url`, `access_method`, `source_channel` | Exact origin and approved acquisition path. |
| `original_content_sha256`, `byte_length`, `media_type` | File-byte identity; mismatch creates a new occurrence and a visible conflict. |
| `source_published_at`, `retrieved_at`, `first_seen_at` | Separately defined timestamps; `first_seen_at` supplies knowledge-time evidence and is never backdated. |
| `valid_time` | Applicable period/event interval when determinable; unknown remains explicit. |
| `supersedes_document_id`, `revision_reason` | Optional explicit relationship; byte changes never silently replace prior bytes. |
| `acquisition_authorization_id`, `capture_run_id` | Exact current `AcquisitionAuthorization` snapshot and acquisition run provenance. |

Original bytes are immutable. Parsed renditions are derived, versioned
objects and must retain byte offsets, pages, tables, timestamps, or equivalent
exact locations back to the original. `SourceDocument` stores neither parser
identity nor a singular/current parse-attempt pointer; append-only
`ParseAttempt` records link back to the immutable document.

### `CaptureEvidenceValue`

The `CaptureEvent` evidence fields `source_occurrence_ref`,
`payload_or_document_sha256`, `source_published_at`, `source_valid_time`,
`retrieved_at`, and `first_seen_at` are tagged values containing `state`,
nullable `value`, `reason_code`, and evidence refs. `state` is closed to
`PRESENT`, `UNAVAILABLE_DUE_TO_FAILURE`, `SOURCE_NOT_PROVIDED`, or
`NOT_APPLICABLE`. `PRESENT` requires a non-null typed value and every other
state requires a null value plus a typed reason. `UNAVAILABLE_DUE_TO_FAILURE`
is legal only for a `FAILED` event whose recorded failure stage prevented the
value from being observed. `SOURCE_NOT_PROVIDED` requires evidence that the
source was successfully reached but omitted that field. `NOT_APPLICABLE` is
legal only for source-published or valid time when the capture kind has no such
semantic. Unknown or missing state is invalid; absence never implies any
non-present state.

### `CaptureEvent`

Required fields are `capture_event_id`, `event_version`, nullable
`supersedes_event_version`, `capture_attempt_id`, `job_id`, exact target
source/provider/locator, `attempted_at`, capture kind
(`MEMBERSHIP_SECURITY_CHANGE`, `PRICE`, `ANNOUNCEMENT`, `CORPORATE_ACTION`, or
`SHAREHOLDING_CHANGE`), source-subject identity and locator,
`identity_resolution_state` (`RESOLVED`, `UNRESOLVED`, or `NOT_APPLICABLE`),
nullable internal entity/security refs, nullable mapping version, one tagged
`CaptureEvidenceValue` for every field above, outcome (`CAPTURED`, `NO_EVENT`,
or `FAILED`), nullable failure stage/code/detail, attempt number, retry
relation, `acquisition_authorization_id`, and evidence refs. `RESOLVED`
requires every applicable internal ref plus
mapping version; `UNRESOLVED` requires null internal refs, the unmodified
source-native name/identifiers, exact source locator, and a reason;
`NOT_APPLICABLE` requires a typed rationale and is the only state permitting a
null source-subject identity. A later mapping appends a monotonic event version
with the same point-in-time payload and explicit supersession; it does not
rewrite capture time or raw identity.

`CAPTURED` requires `PRESENT` source occurrence, payload/document hash,
retrieved time, and first-seen time. `NO_EVENT` requires a `PRESENT` successful-
check occurrence, response/query-result hash, retrieved time, and first-seen
time; a failed fetch is `FAILED`, never `NO_EVENT`. `FAILED` requires a
failure stage, code, and detail and preserves every value observed before the
failure as `PRESENT`; any value that could not be observed is explicitly
`UNAVAILABLE_DUE_TO_FAILURE`. Thus even a pre-response failure is persisted by
its stable attempt identity, exact target, attempted time, authorization, and
retry relation without fabricating source occurrence, hash, or source time.

### `ParseAttempt`

Each parse/re-extraction attempt is append-only and records stable
`parse_attempt_id`, `document_id`, matching document hash, monotonic
`attempt_sequence` within the document, nullable
`predecessor_parse_attempt_id`, nullable `retry_of_parse_attempt_id`, parse
purpose/schema version, parser/model and version, configuration hash, start and
completion timestamps, output refs and hashes, warnings, confidence where
applicable, exact `transformation_authorization_id` and
`authorization_snapshot_sha256`, `authorization_checked_at`,
nullable `authorization_rechecked_at`, and status (`SUCCEEDED`, `PARTIAL`, or
`FAILED`). The first timestamp is immediately before parser invocation; the
second is immediately before output publication and is mandatory for any
attempt with output refs. The first check and any second check must fall within
the interval beginning at `valid_from` and ending at `valid_until` when that
field is non-null. `evaluated_at <= authorization_checked_at`; when the second
check exists, `authorization_checked_at <= authorization_rechecked_at`. Both
checks must resolve the same snapshot ID/digest; no output-bearing attempt may
omit the second check. Sequence one has no predecessor; every later attempt
names the immediately preceding attempt, and a retry must name an earlier
attempt for the same document. Unknown IDs, cross-document links, gaps, forks,
cycles, authorization ID/digest mismatch, or authorization scope that does not
cover the attempt and every output invalidate the history.

A parser upgrade or retry appends a new attempt and never mutates the document,
prior attempt, output, or warning. Every parsed rendition and consumer stores
the exact `parse_attempt_id` it uses; there is no implicit current attempt.
Unknown, document/hash-mismatched, or non-`SUCCEEDED` attempts fail closed for
consumers that require a complete parse. A request without a current valid
`TransformationAuthorization` is rejected before parser invocation and cannot
create derived output; rejected-request evidence must prove that the parser
was not called. If final authorization revalidation fails, the append-only
attempt is `FAILED`, any provisional output is non-consumable, and the original
`SourceDocument` acquisition provenance and authorization history remain
unchanged. Original-byte retention continues to follow its separately bound
acquisition policy.

### Dormant `OfficialAudioArtifact`

If and only if C-14 is validly activated, an audio artifact must record the
original audio bytes/hash, official source and URL, acquisition and first-seen
timestamps, media metadata, model and version, configuration, transcript
segments with source timestamps, segment confidence, human corrections,
supersession history, and rights-policy reference. Transcripts are derived
evidence and never replace the original audio.

### Required interfaces

- S02 supplies approved source, provider, caching, retention, automation, and
  data-rights policy references, including the typed provider-authorization
  applicability, exact approval requirement-to-record/resolution matches,
  current requirement/record content digests, transformation/derived-output/
  retention scope, renewal/revocation state, and evidence; S09 does not infer
  them.
- S05 supplies the discovery company and four-quarter source-package scope to
  A-06.
- S07 supplies the failure taxonomy and prompt-injection/source-confusion
  fixtures, including `DOCUMENT_AS_INSTRUCTION` behavior.
- S11 consumes immutable document IDs/hashes and first-seen knowledge time for
  run manifests and cutoff enforcement.
- S12 consumes source occurrences and exact parse-attempt IDs but owns fact
  identity, reconciliation, and schema evolution.
- S17 later supplies stable internal company/security identities and corporate-
  action semantics. B-09 captures source-native identity before S17 when
  necessary and appends a mapped event/version later; it never guesses or
  makes S17 a capture prerequisite.

## Invariants and fail-closed behavior

1. Original bytes are immutable and content-addressed. Same URL plus changed
   bytes creates a new document occurrence; hash mismatch never overwrites.
2. URLs, timestamps, hashes, and first-seen times are mandatory on accepted
   source-document evidence. Parser/model versions, attempt identity, output
   refs, extraction warnings, and the exact current transformation-
   authorization ID/digest are mandatory on each parse-attempt record; missing
   or implicit parse or authorization identity blocks parser invocation and use
   of the derived output.
3. `first_seen_at` is acquisition evidence, not source publication time. It
   cannot be backdated to simulate point-in-time history.
4. Unknown, unavailable, not applicable, failed, and no-event states are
   distinct. Every nullable capture-evidence value has an outcome-compatible
   typed state and reason. Capture failures are persisted even when failure
   prevented observing source occurrence, payload, or source time, and remain
   visible to retry/coverage metrics.
5. Only sources and uses approved under S02/A-05 may be automated, cached,
   retained, or transformed. Acquisition and transformation use distinct
   immutable snapshots. Every transformation approval binds one exact
   `SATISFIED` requirement to its unique current `APPROVED`, purpose-matching
   record/resolution; record or resolution reuse across requirements fails.
   Missing, denied, unresolved, unmatched, non-`SATISFIED`, expired, revoked,
   superseded, stale, wrong-scope, reused, or digest-mismatched transformation/
   derived-output/retention authority blocks parser invocation or output
   consumption without rewriting acquisition-time evidence; renewal requires a
   new exact snapshot.
6. Source content is data, never instructions. It cannot alter tools,
   permissions, cutoffs, prompts with control authority, promotion rules,
   credentials, external calls, or execution.
7. Derived text retains exact provenance. Unsupported or ambiguous mappings
   retain raw source identity, remain `UNRESOLVED`, and enter reconciliation;
   the system does not guess or block B-09 capture solely because S17 identity
   is not yet available.
8. Point-in-time jobs are idempotent first by stable capture-attempt identity;
   successful checks additionally deduplicate by source occurrence/payload
   hash, while distinct retries and failures remain append-only.
9. A-06 must measure filing channel and taxonomy/version changes plus mapping
   stability and reconciliation effort, not only nominal field coverage.
10. C-14 remains dormant until every activation condition below passes. A
    dormant component cannot enter planned, implementing, or verified state.
11. A consumer that requires an internal entity/security identity fails closed
    on an `UNRESOLVED` capture event; that downstream restriction does not
    rewrite, discard, or prevent the point-in-time event record.

## Deferred activation guard for C-14

The component ledger must retain a non-null typed predicate named
`AP-C14-OFFICIAL-AUDIO-NEEDED`. Its closed expression is:

```json
{"op":"ALL","args":[
  {"op":"COMPARE","metric_id":"MTR-C14-OFFICIAL-AUDIO-REQUIRED","comparator":"EQ","expected":true},
  {"op":"COMPARE","metric_id":"MTR-C14-SOURCE-OFFICIAL","comparator":"EQ","expected":true},
  {"op":"COMPARE","metric_id":"MTR-C14-RIGHTS-CURRENT","comparator":"EQ","expected":true}
]}
```

All three metrics are Boolean `EVIDENCE_JSON` metrics in the same current,
component-local gap assessment. Their respective RFC 6901 pointers are
`/official_audio_transcription_required`, `/official_audio_source_confirmed`,
and `/source_provider_rights_current`. The rights metric's `valid_until` equals
the earliest non-null expiry across every applicable underlying source- and
provider-rights record. It may be null only when every authoritative record
explicitly has no expiry; a missing or unknown expiry evaluates the metric
`UNKNOWN`. Explicitly non-official or invalid rights values evaluate their
leaf `FALSE`; missing evidence evaluates the affected leaf `UNKNOWN`, while
stale evidence or expired `valid_until` invalidates the current evaluation and
blocks activation. Three-valued `ALL` evaluation governs resolved/current
leaves.

That gap assessment must identify company/event scope, the approved textual
and filing sources checked, the material information need not satisfied by
those sources, the official audio source, source/provider-rights references,
and all three evidence-backed booleans. Missing evidence, a false/unknown value,
expired rights, a stale digest, or a non-official source evaluates the
predicate as false or unknown and cannot activate C-14.

For an evaluated predicate, `evaluation_sha256` is SHA-256 of the governing
canonical JSON object with exactly `predicate_id`, `expression`, `metrics`,
deterministically `resolved_values`, current source/evidence
`digest_sources`, `result`, and `evaluated_at`. The validator recomputes every
value, the three-valued result, and this preimage from live evidence. An
unevaluated or `UNKNOWN` predicate has null `evaluated_at` and digest; copied
values or a ledger-authored digest never establish truth.

The C-14 `activation_record` contains `activation_record_id`,
`decision=ACTIVATE_DEFERRED`, C-14 component/register IDs, exact scope,
predicate ID and current `activation_predicate_sha256`, authority, actor, UTC
timestamp, nonempty exact predicate/evidence refs, `approval_record_id`,
`human_resolution_decision_id`, and `human_resolution_sha256`. The
`PRODUCT_OWNER_DECISION` approval and activation record must carry the same
canonical decision ID and `content_sha256` for one active immutable
`ACTIVATE_DEFERRED` human resolution and must copy its actor, authority, scope,
timestamp, purpose, and evidence exactly. Stale, revoked, superseded,
wrong-purpose, differently scoped, or merely string-matching records fail.

Activation additionally requires all of the following:

1. C-02 immutable document storage and B-08 failure handling are evidenced;
2. the predicate is freshly recomputed `TRUE` from current evidence;
3. a competent human issues a distinct active `ACTIVATE_DEFERRED` resolution
   for exact C-14 scope through the canonical human-review artifact;
4. the matching `PRODUCT_OWNER_DECISION` approval and activation record bind
   that resolution, predicate digest, evidence, actor, authority, scope, and
   timestamp; and
5. the legal register status transition and
   `STATUS_SOURCE_RECONCILIATION` validate before any C-14 planning or
   implementation begins. The reconciliation binds nonempty old/new source
   evidence, occurs in the same global history as the legal `Deferred` to
   `Open` or `In progress` `source_status` transition, and is followed by the
   required status-only Sol review and refreshed content-bound reviews.

`AUTHORITY_RECONCILIATION` is not used for that status-only activation. It is
required only if source, ownership, or contract semantics also change, in
which case the separate active `RECONCILE_AUTHORITY` resolution and updated
approved contract must exist before dependent work resumes.

Goal activation, this spec, a coordinator, an agent, availability of audio, or
matching ledger-authored strings cannot supply activation authority. If C-14
is later rejected, no-implementation evidence and the distinct human rejection
path are required; dormancy is not rejection.

## Evidence and typed approval gates

| Gate | Required proof | Typed authority | Fail-closed result |
|---|---|---|---|
| Delegated spec approval | Fresh clean Sol xhigh review bound to exact S09 bytes and persisted evidence | `DELEGATED_ARTIFACT_APPROVAL` | S09 remains draft; no dependency treats it as approved. |
| Filing-spike fitness | Complete four-quarter channel/taxonomy coverage matrix and reconciliation evidence | `DOMAIN_EXPERT_ACCEPTANCE` | A-06 remains unresolved. |
| Source acquisition, storage, and transformation | Current `AcquisitionAuthorization` for exact acquisition/capture scope; every parse/re-extraction separately binds a digest-valid current `TransformationAuthorization` for the exact document/hash, operation, derived outputs, and retention, plus each exact `SATISFIED` approval requirement and its unique current `APPROVED`, purpose-matching record/resolution; `REQUIRED` provider applicability has a matching provider requirement/record and `NOT_REQUIRED` has authoritative applicability evidence | `DATA_RIGHTS_APPROVAL`; additionally `PROVIDER_AUTHORIZATION` iff applicability is `REQUIRED` | Missing/`UNKNOWN` applicability or missing, denied, unresolved, unmatched, non-`SATISFIED`, expired, revoked, stale, wrong-scope, superseded, reused, or digest-mismatched proof blocks the affected fetch/store/capture or parser invocation/output consumption. Acquisition-time evidence remains immutable and does not reauthorize transformation. |
| Capture-domain fitness | Approved capture kinds/sources, failure behavior, and point-in-time semantics | `DOMAIN_EXPERT_ACCEPTANCE` | B-09 remains unresolved. |
| C-14 activation | Current true predicate plus exact active human activation resolution and bound record | `PRODUCT_OWNER_DECISION` | C-14 remains `Deferred`; no planning or implementation. |
| Audio transcript analytical use, after activation | Original/audio/transcript provenance and explicit acceptance for scoped use | `ANALYST_ACCEPTANCE` | Transcript cannot support an approved claim or narrative. |

Provider and data-rights approvals are consumed from their authoritative
records and do not transfer primary ownership to S09. Purchase, credential, or
external-service needs require their own typed approvals. Every
non-delegated record must resolve through the canonical human-review artifact;
a Sol review supplies none of those authorities.

## Acceptance tests and verification

### Active-scope tests

- Exact ownership is A-06, B-09, C-02, and C-14, with only C-14 Deferred.
- The A-06 matrix covers the selected company and all four quarters across
  filing channel, taxonomy/version, statement, segment, note,
  ownership/share count, restatement behavior, mapping stability, and
  reconciliation effort.
- Exchange quarterly-result XBRL, annual channels, issuer documents, and
  taxonomy/version changes are distinguishable.
- Same URL/same bytes deduplicates safely; same URL/changed bytes appends a new
  immutable occurrence; hash mismatch and missing original bytes fail.
- A document remains immutable while parser retries/upgrades append stable,
  monotonic attempt IDs; prior outputs/warnings remain addressable, every
  derived rendition binds one exact successful attempt and that attempt's exact
  current transformation-authorization ID/digest; implicit-current, unknown,
  cross-document, failed, forked, cyclic, or authorization-mismatched
  references reject.
- Parse/re-extraction negative fixtures cover missing authorization; expired,
  revoked, superseded, or stale authority inputs; wrong document/hash,
  operation, derived-output type/consumer/destination, retention class/
  destination/deadline, or provider scope; unknown expiry; and mutated snapshot
  or authority-input digests. Each rejects before parser invocation, or fails
  final revalidation with no consumable output, while leaving `SourceDocument`
  acquisition provenance and acquisition-authorization history unchanged;
  original-byte retention still follows the acquisition policy.
- Approval-binding negative fixtures cover a missing or unknown requirement ID;
  each non-`SATISFIED` requirement state (`UNRESOLVED`, `DENIED`, `REVOKED`,
  and `EXPIRED`); a null, unknown, or different `matched_record_id`; a matched
  record whose decision is not `APPROVED`; mismatched approval type, authority,
  scope, actor, timestamp, evidence, authority source, requirement/record
  content digest, resolution decision ID/content digest, or
  `SATISFY_APPROVAL` purpose; a stale, superseded, or revoked resolution; and
  the same approval record ID or resolution decision ID matched to two
  requirements. Every fixture rejects before parser invocation or at final
  revalidation with no consumable output.
- A mid-attempt fixture expires, revokes, supersedes, or changes the scope or
  content digest of one authority input after `authorization_checked_at` and
  before `authorization_rechecked_at`; the attempt becomes `FAILED`, publishes
  no consumable output, and preserves its immutable attempt and acquisition
  evidence.
- Renewal fixtures prove that an old snapshot cannot be treated as current or
  have its expiry/digest edited in place. A new parse/re-extraction proceeds
  only with the new authorization ID/digest; prior attempt/output hashes and
  acquisition-time evidence remain byte-for-byte unchanged. A fixture also
  rejects continued use or retention of an old derived output after its bound
  authority ceases to be current; renewal permits a fresh output only through a
  new parse/re-extraction bound to the renewed snapshot.
- Every successfully captured kind persists hash and first-seen time; a
  no-event outcome carries successful-check occurrence/hash evidence; neither
  may use unavailable evidence states.
- A fetch that fails before any response still persists a `FAILED` event with
  stable attempt identity, target, attempted time, failure stage/code/detail,
  and explicitly unavailable occurrence/hash/source-time values. Partial
  failures preserve observed values and reject fabricated or untagged nulls.
- A B-09 event captured before S17 retains exact raw source identity with
  `identity_resolution_state=UNRESOLVED` and null internal refs; later mapping
  appends a resolved version, while downstream identity-dependent use rejects
  the unresolved event.
- Late-arriving documents do not receive fabricated earlier knowledge time.
- A hostile document cannot modify tool permissions, cutoff, promotion,
  credentials, external calls, or execution and is recorded under the S07
  taxonomy.
- Unapproved/expired source rights block acquisition and transformation.
- Provider applicability `REQUIRED`, `NOT_REQUIRED`, `UNKNOWN`, and missing are
  tested: only `REQUIRED` with a matching current authorization or
  `NOT_REQUIRED` with authoritative current basis can proceed.

### Deferred-scope tests

- With predicate `FALSE` or `UNKNOWN`, stale/missing evidence, missing human
  resolution, or current register status `Deferred`, every audio planning,
  fetch, storage, transcription, and implementation entry point rejects.
- A copied `true` label, goal activation, coordinator decision, or Sol review
  cannot activate C-14.
- Only a current `TRUE` predicate plus bound human resolution, approval,
  activation record, dependency evidence, and legal register reconciliation
  can unlock the C-14 cone.
- Predicate fixtures independently make the material-need, official-source,
  and rights-current leaves false, unknown, stale, or expired; canonical digest
  recomputation rejects any changed preimage or mismatched rights expiry.
- Activation fixtures reject mismatched resolution ID/digest, actor, authority,
  scope, timestamp, purpose, evidence, predicate digest, or approval binding.
- Status-only activation rejects `AUTHORITY_RECONCILIATION` and accepts only a
  legal `Deferred` transition with same-history `STATUS_SOURCE_RECONCILIATION`,
  old/new source evidence, status-only review, and refreshed content-bound
  reviews.
- After valid activation, original audio, model/version, timestamps,
  confidence, and correction history are mandatory and append-only.

The implementation plan must declare argv-style commands for schema and
coverage validation, content-addressing/immutability tests, idempotent capture,
failure persistence, transformation-authorization digest/scope/lifecycle
and approval-binding/one-to-one fixtures, adversarial-document controls, and
dormant activation tests.
Verification persists command/output hashes, exit status, scope hashes, and
execution time. Agent assertions are not proof.

## Dependencies and sequencing

- A-06 depends exactly on A-02; the discovery company/four-quarter package is
  selected before the coverage spike.
- B-09 depends exactly on A-05; approved rights/source scope precedes capture.
  S17 is not a B-09 dependency: source-native identity is captured unresolved
  until a later mapping can be appended.
- C-02 depends exactly on A-05; immutable storage does not authorize source
  acquisition by itself.
- C-14 depends exactly on C-02 and B-08 and additionally remains behind its
  Deferred activation guard.
- The recommended authoritative sequence places A-02/A-06 after the initial
  boundary and rights work and before schema derivation; C-14 is not part of
  that active sequence.

## Amendment gate

No mandatory evidence-derived amendment gate is assigned to S09 in the
Exact 25-spec program. A status-only C-14 activation requires legal register
transition, `STATUS_SOURCE_RECONCILIATION`, status-only review, and fresh
content-bound review; it does not silently amend this draft or authorize
implementation. Any source-semantic, ownership, or activation-contract change
instead requires explicit `AUTHORITY_RECONCILIATION`, its canonical human
resolution, an updated approved contract, and fresh Sol xhigh review.
