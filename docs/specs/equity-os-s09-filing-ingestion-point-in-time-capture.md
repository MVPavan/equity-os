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

### `SourceDocument`

| Field | Contract |
|---|---|
| `document_id` | Stable internal identifier for one acquired byte sequence. |
| `source_url`, `access_method`, `source_channel` | Exact origin and approved acquisition path. |
| `original_content_sha256`, `byte_length`, `media_type` | File-byte identity; mismatch creates a new occurrence and a visible conflict. |
| `source_published_at`, `retrieved_at`, `first_seen_at` | Separately defined timestamps; `first_seen_at` supplies knowledge-time evidence and is never backdated. |
| `valid_time` | Applicable period/event interval when determinable; unknown remains explicit. |
| `parser_name`, `parser_version`, `parse_attempt_id` | Exact parser identity per attempt; reparsing never overwrites the original. |
| `extraction_warnings` | Structured warning codes and affected locations. |
| `supersedes_document_id`, `revision_reason` | Optional explicit relationship; byte changes never silently replace prior bytes. |
| `rights_policy_ref`, `capture_run_id` | Approved rights/source-policy reference and acquisition run provenance. |

Original bytes are immutable. Parsed renditions are derived, versioned
objects and must retain byte offsets, pages, tables, timestamps, or equivalent
exact locations back to the original.

### `CaptureEvent`

Required fields are `capture_event_id`, `job_id`, source/provider, capture
kind (`MEMBERSHIP_SECURITY_CHANGE`, `PRICE`, `ANNOUNCEMENT`,
`CORPORATE_ACTION`, or `SHAREHOLDING_CHANGE`), internal entity/security refs,
source occurrence, payload/document hash, source published/valid time,
retrieved time, first-seen time, outcome (`CAPTURED`, `NO_EVENT`, or `FAILED`),
failure code/detail, attempt number, retry relation, rights-policy ref, and
evidence refs. A `NO_EVENT` record is allowed only when the approved source was
successfully checked; a failed fetch is `FAILED`, never `NO_EVENT`.

### `ParseAttempt`

Each parse/re-extraction attempt is append-only and records document hash,
parser/model and version, configuration hash, timestamps, outputs, warnings,
confidence where applicable, and failure state. A parser upgrade creates a
new attempt; it cannot rewrite the source occurrence or erase prior warnings.

### Dormant `OfficialAudioArtifact`

If and only if C-14 is validly activated, an audio artifact must record the
original audio bytes/hash, official source and URL, acquisition and first-seen
timestamps, media metadata, model and version, configuration, transcript
segments with source timestamps, segment confidence, human corrections,
supersession history, and rights-policy reference. Transcripts are derived
evidence and never replace the original audio.

### Required interfaces

- S02 supplies approved source, provider, caching, retention, automation, and
  data-rights policy references; S09 does not infer them.
- S05 supplies the discovery company and four-quarter source-package scope to
  A-06.
- S07 supplies the failure taxonomy and prompt-injection/source-confusion
  fixtures, including `DOCUMENT_AS_INSTRUCTION` behavior.
- S11 consumes immutable document IDs/hashes and first-seen knowledge time for
  run manifests and cutoff enforcement.
- S12 consumes source occurrences and parse attempts but owns fact identity,
  reconciliation, and schema evolution.
- S17 supplies stable internal company/security identities and corporate-
  action semantics; capture retains unresolved mappings rather than guessing.

## Invariants and fail-closed behavior

1. Original bytes are immutable and content-addressed. Same URL plus changed
   bytes creates a new document occurrence; hash mismatch never overwrites.
2. URLs, timestamps, hashes, parser versions, extraction warnings, and
   first-seen times are mandatory for accepted C-02 evidence. Missing values
   fail closed or remain explicitly unresolved.
3. `first_seen_at` is acquisition evidence, not source publication time. It
   cannot be backdated to simulate point-in-time history.
4. Unknown, unavailable, not applicable, failed, and no-event states are
   distinct. Capture failures are persisted and visible to retry/coverage
   metrics.
5. Only sources and uses approved under S02/A-05 may be automated, cached,
   retained, or transformed. Missing or expired rights evidence blocks the
   affected acquisition.
6. Source content is data, never instructions. It cannot alter tools,
   permissions, cutoffs, prompts with control authority, promotion rules,
   credentials, external calls, or execution.
7. Derived text retains exact provenance. Unsupported or ambiguous mappings
   remain unresolved and enter reconciliation; the system does not guess.
8. Point-in-time jobs are idempotent by source occurrence/payload hash while
   preserving distinct attempts and failures.
9. A-06 must measure filing channel and taxonomy/version changes plus mapping
   stability and reconciliation effort, not only nominal field coverage.
10. C-14 remains dormant until every activation condition below passes. A
    dormant component cannot enter planned, implementing, or verified state.

## Deferred activation guard for C-14

The component ledger must retain a non-null typed predicate named
`AP-C14-OFFICIAL-AUDIO-NEEDED`. Its expression is a `COMPARE` leaf requiring
the boolean metric `MTR-C14-OFFICIAL-AUDIO-REQUIRED` to equal `true`. The
metric source is a current, component-local `EVIDENCE_JSON` gap assessment and
its RFC 6901 pointer is `/official_audio_transcription_required`.

That gap assessment must identify company/event scope, the approved textual
and filing sources checked, the material information need not satisfied by
those sources, the official audio source, source/provider-rights references,
and the evidence-backed boolean. Missing evidence, a false/unknown value,
expired rights, a stale digest, or a non-official source evaluates the
predicate as false or unknown and cannot activate C-14.

Activation additionally requires all of the following:

1. C-02 immutable document storage and B-08 failure handling are evidenced;
2. the predicate is freshly recomputed `TRUE` from current evidence;
3. a competent human issues a distinct active `ACTIVATE_DEFERRED` resolution
   for exact C-14 scope through the canonical human-review artifact;
4. the matching `PRODUCT_OWNER_DECISION` approval and activation record bind
   that resolution, predicate digest, evidence, actor, authority, scope, and
   timestamp; and
5. the register status transition and authority reconciliation validate before
   any C-14 planning or implementation begins.

Goal activation, this spec, a coordinator, an agent, availability of audio, or
matching ledger-authored strings cannot supply activation authority. If C-14
is later rejected, no-implementation evidence and the distinct human rejection
path are required; dormancy is not rejection.

## Evidence and typed approval gates

| Gate | Required proof | Typed authority | Fail-closed result |
|---|---|---|---|
| Delegated spec approval | Fresh clean Sol xhigh review bound to exact S09 bytes and persisted evidence | `DELEGATED_ARTIFACT_APPROVAL` | S09 remains draft; no dependency treats it as approved. |
| Filing-spike fitness | Complete four-quarter channel/taxonomy coverage matrix and reconciliation evidence | `DOMAIN_EXPERT_ACCEPTANCE` | A-06 remains unresolved. |
| Source acquisition and storage | Current access, automation, caching, retention, derived-output, and redistribution evidence for exact use | `DATA_RIGHTS_APPROVAL` and, where applicable, `PROVIDER_AUTHORIZATION` | Fetch/store/parse/capture is blocked for the affected source. |
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
- Parser upgrades append attempts and preserve prior outputs/warnings.
- Every capture kind persists hash and first-seen time; failed fetches remain
  failures and are never converted to no-event.
- Late-arriving documents do not receive fabricated earlier knowledge time.
- A hostile document cannot modify tool permissions, cutoff, promotion,
  credentials, external calls, or execution and is recorded under the S07
  taxonomy.
- Unapproved/expired source rights block acquisition and transformation.

### Deferred-scope tests

- With predicate `FALSE` or `UNKNOWN`, stale/missing evidence, missing human
  resolution, or current register status `Deferred`, every audio planning,
  fetch, storage, transcription, and implementation entry point rejects.
- A copied `true` label, goal activation, coordinator decision, or Sol review
  cannot activate C-14.
- Only a current `TRUE` predicate plus bound human resolution, approval,
  activation record, dependency evidence, and legal register reconciliation
  can unlock the C-14 cone.
- After valid activation, original audio, model/version, timestamps,
  confidence, and correction history are mandatory and append-only.

The implementation plan must declare argv-style commands for schema and
coverage validation, content-addressing/immutability tests, idempotent capture,
failure persistence, adversarial-document controls, and dormant activation
tests. Verification persists command/output hashes, exit status, scope hashes,
and execution time. Agent assertions are not proof.

## Dependencies and sequencing

- A-06 depends exactly on A-02; the discovery company/four-quarter package is
  selected before the coverage spike.
- B-09 depends exactly on A-05; approved rights/source scope precedes capture.
- C-02 depends exactly on A-05; immutable storage does not authorize source
  acquisition by itself.
- C-14 depends exactly on C-02 and B-08 and additionally remains behind its
  Deferred activation guard.
- The recommended authoritative sequence places A-02/A-06 after the initial
  boundary and rights work and before schema derivation; C-14 is not part of
  that active sequence.

## Amendment gate

No mandatory evidence-derived amendment gate is assigned to S09 in the
Exact 25-spec program. A later valid activation of C-14 requires register and
ledger reconciliation plus fresh content-bound review; it does not silently
amend this draft or authorize implementation. Any source-semantic, ownership,
or activation-contract change requires explicit authority reconciliation and
fresh Sol xhigh review.
