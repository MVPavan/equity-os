# D1b retained first-party intake witness implementation plan

Status: R2 APPROVE, 2026-10-13, fresh independent Codex session. All W01–W03 from
[R1](../reviews/D1b-retained-intake-witness-plan-r1.md) are addressed; fresh
[R2](../reviews/D1b-retained-intake-witness-plan-r2.md) approves bounded implementation.
The genuine existing-seam RED, implementation and verification remain required.
Tracked by `eqos-u0u.24`; supplements D1b Tasks 11 and 6.

**Origin:** the [failed-XBRL authority ruling](D1b.md#vendor-producer-integration-and-failed-xbrl-authority-ruling--2026-10-13),
the [consumer review ledger](../reviews/D1b-vendor-inputs-handoff-review.md), and root's
2026-10-13 bounded scope ruling. Existing consumer guard `ee3b07f` is accepted.
**Goal:** a PDF-only published generation with an honestly failed XBRL extraction can prove
its original retained XBRL input from independently read metadata, persist that proof, and
replay it by recorded identity without accepting an unrelated failed body.
**Out of scope:** source authorization grants, failed-input issuer verification, Sona ISIN
evidence, live acquisition, financial equivalence, queue changes, full D1b acceptance, and a
repository-wide transaction refactor.
**Constraints:** committed migrations `0001`–`0009` are immutable; add only migration `0010`.
Preserve existing package hash preimages, v1/v2 rows and IDs, pins, results, and old replay.
Every changed production module stays at or below 800 lines. Protected originals and real
databases remain read-only; PostgreSQL verification uses the guarded `eqos_test_*` harness.

## Failure and accepted decisions

The current `RetainedIntake` retains manifest/config hashes and input/store anchors but loses
the original metadata material and selection parameters. Package identity hashes usable
members only. A failed XBRL peer in a PDF-only package therefore cannot derive its intended
physical input from the package. Selecting a candidate's own hash would make the candidate
its own evidence. The accepted consumer refuses this variant until an independent witness
exists; successful-XBRL/failed-PDF consumption remains supported.

Root approves an additive `retain_intake_witness: bool = False` keyword on
`append_first_party_generation`. `False` preserves the current producer contract and omitted
legacy JSON field. `True` requests strict source preparation and durable sealing; the flag
confers no authority. A handoff with no witness keeps the accepted failed-XBRL refusal.
Marked/model-copied legacy test intakes are unchanged. A witness-enabled intake must match
its independently rederived original metadata exactly; a caller-modified binding is refused.

The witness proves consistency with an operator-selected retained input and its recorded
request. Manifest `authorization` text remains recorded metadata. The existing source catalog,
publication, capture rights, identity checks and qualification settings retain their separate
authority. A failed acquisition has no capture and establishes no captured issuer identity.

`ingest_first_party` currently raises `IngestError` after storing attempts when staging fails.
Keep that behavior. Witness preparation precedes ingest; sealing occurs only after ingest
returns a valid `IngestReport` and `_handoff` verifies a package/generation. A raised ingest
returns no handoff and seals no witness. This plan does not make the existing ingest atomic or
convert a staging failure into a successfully published generation. The positive tracer uses
the existing retained APAR schema-unsupported XBRL extraction with a usable unchanged PDF.

## File map and ownership

| File | Responsibility | Owner |
|---|---|---|
| Create `evidence/retained_intake_models.py` | Frozen, versioned source/material/request/witness types; no repository imports | Evidence implementer |
| Create `evidence/retained_intake_source.py` | Descriptor-safe metadata reads, deterministic selection and strict pre-ingest preparation | Evidence implementer |
| Create `evidence/retained_intake_store.py` | Atomic witness storage, normalized FK closure, sealed by-ID reload and full reuse proof | Evidence implementer |
| Create `evidence/retained_intake_proof.py` | Pure durable-material and generation-association reproof shared by fresh consumption and replay | Evidence implementer |
| Modify `evidence/capture_intake.py` | Optional process-local metadata source on `RetainedIntake`; factory records its observed anchors/relative paths and selection | Evidence implementer |
| Modify `evidence/first_party_generation.py` | Opt-in preparation/sealing and optional handoff witness evidence ID | Evidence implementer |
| Modify `pg/identity_seed.py` | Add `EvidenceInputKind.RETAINED_INTAKE` only | Evidence implementer |
| Modify `evidence/repository.py` | Optional typed witness field on `EvidenceInputRecord`; small delegated enrichment in `get_evidence_inputs` | Evidence implementer |
| Create `migrations/0010_retained_intake_witness.sql` | New evidence-kind CHECK branch, append-only witness tables and seal protections | Evidence implementer |
| Modify `compare/vendor_handoff_attempts.py`, `compare/vendor_handoffs.py` | Consume proved witness source bindings and include its exact evidence input in `FirstPartyScope` | Witness consumer implementer, exclusive after this plan's approval |
| Create `compare/retained_intake_replay.py` | Pure manifest-closure and request/pin witness guards; no reads or writes | Witness replay implementer |
| Modify `compare/resolve.py` | Wire the approved witness helper at load/recompute call sites alongside vendor-run changes | Active shared run writer, `eqos-u0u.25`, sole editor |
| Create `tests/fundamentals/test_retained_intake_witness.py` | Existing-seam behavioral baseline, source preparation and producer/consumer proof cases | Root test owner |
| Create `tests/fundamentals/test_retained_intake_witness_store.py` | SQL shape, sealing, permissions, concurrency and byte-identical upgrade | Root test owner |
| Create `tests/fundamentals/test_retained_intake_witness_replay.py` | By-ID replay, exact manifest closure, changed-filesystem and later-attempt isolation | Root test owner |
| Modify `tests/fundamentals/pg_evidence_schema_support.py`, `tests/fundamentals/test_pg_evidence_schema.py` | Seed all six new tables and extend exact all-table/ACL checks without weakening old assertions | Root schema fixture owner |

Production paths in the table are relative to `src/fundamentals/`. Keep
`evidence/first_party_ingest.py` unchanged: it is already 800 lines. The repository is currently
787 lines; put witness queries and validation in the new modules rather than growing it past
the cap. The active `eqos-u0u.25` dispatch owns `resolve.py` and consumes the accepted handoff
module read-only; this dated assignment supersedes the older supplemental plan's broader
consumer ownership description. The witness consumer exclusively edits the two handoff files
after plan approval. Root serializes their main-worktree integration. The witness replay owner
creates only its new helper and never edits `resolve.py`; `.25` wires the approved signatures
after root records the interface handshake. If `.25` has already frozen, root must explicitly
record an ownership transfer before assigning another editor. No overlapping dispatch is allowed.

## Exact contracts

### Source preparation

`RetainedIntakeMetadataSource` is process-local: observed `DirectoryAnchor` values for manifest
and issuer-config roots, canonical relative metadata paths, issuer, quarter, and an immutable
representation-to-kind selection. Anchors are locally observed, never deserialized identities.
The factory still produces the existing bindings/hashes; the additional source is omitted from
serialization. A manually constructed intake without this source remains usable in legacy
mode and is refused in witness mode.

`prepare_retained_intake_witness(intake, *, config, config_root, repository, entity_id, family,
reporting_period_end, basis, framework, pdf_specs) -> PreparedRetainedIntakeWitness` runs before
publication pins, capture registration, attempts, interpretations, or witness writes. Read the
original manifest and required issuer config through their observed descriptor anchors, bounded
to 1 MiB each; verify unchanged directory/file identity across the read. Refuse symlinks,
nonregular files, unsafe paths, replacement, oversized material and missing required config.
Use these exact bytes once to parse and derive hashes, avoiding separate parse/hash reads.

Reapply the current manifest issuer/quarter/kind uniqueness, filename containment, PDF source
and SHA match, filed-at parsing and source-catalog authorization rules. Independently derive
every original request, including an input whose later staging or extraction fails. Compare
the complete sorted derived binding set, manifest/config hashes, PDF source and authority text
to the supplied intake. Verify the retained config's issuer/symbol/period and actual PDF specs
against the verified database identity and requested period at composition time. Basis/framework
remain typed requested scope: failed input metadata does not independently prove either one;
the unchanged extraction identity checks determine observed success or failure.
No caller-provided numerical reading or candidate attempt supplies any of these bindings.

`PreparedRetainedIntakeWitness` contains schema `retained_intake_v1`, exact bounded metadata
bytes with their SHA/size, safe metadata labels, immutable selection parameters, typed package
scope, and sorted `RetainedIntakeRequest` values. Each request names representation, source,
surface, safe original relative path, expected input SHA, `request_key_for` value, raw filed-at
and parsed UTC knowledge time, actual extractor pin and applicable extraction-context material.
PDF context derives from the retained config's actual specs; schema-unsupported XBRL context
derives from the actual mapping version and `unsupported_schema_context`. Acquisition attempts
retain their existing empty extractor and null extraction-context fields. Expected input SHA
is an original binding, not a claim that failed staging observed a body.

### Durable model and SQL boundary

`RetainedIntakeWitness` adds the exact stored evidence input ID, database recorded/sealed
times, package ID and unchanged evidence SHA, publication version/content/state, complete
generation pin projection, qualification settings ID/context digest, and sorted attempt and
capture identities/payloads associated with each original request. Successful package captures
and failed captured peers are distinct dispositions. No capture is fabricated for an acquisition.
Use frozen types with `extra='forbid'`, strict positive IDs, closed schema/source representations,
lowercase SHA-256 shapes, UTC-aware times and duplicate-free canonical ordering.

Migration `0010` extends only the `evidence_inputs.kind` CHECK to admit `RETAINED_INTAKE` and
creates these normalized tables:

Every new table has an ordinary `id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY`,
preserving the existing schema-wide helpers' `RETURNING id` and `WHERE id` contracts.

1. `retained_intake_witnesses`: unique/FK `evidence_input_id`; exact metadata `bytea` and
   hashes/sizes; selection/scope; FK package/settings identity; publication identity; canonical
   versioned payload and digest. Material lengths and digest shapes are SQL checked.
2. `retained_intake_witness_bindings`: FK `witness_id` to the header's ordinary `id`, unique
   witness/representation and witness/binding-id keys; original source/surface,
   path, expected input SHA, request key, filed-at and derived context fields.
3. `retained_intake_witness_attempts`: header FK, typed attempt FK and composite
   witness/binding-id FK to the matching binding.
4. `retained_intake_witness_captures`: header FK, typed capture FK and composite
   witness/binding-id FK to the matching binding.
5. `retained_intake_witness_pins`: header FK, unique witness/artifact and FK to an existing `version_pins`
   row. The loader compares artifact/version/content, including the actual publication pin.
6. `retained_intake_witness_seals`: unique/FK `witness_id`; one seal per witness with canonical closure digest, counts
   and a server-owned `eqos.store_now()` timestamp.

SQL header/binding/link/seal primary IDs are internal storage identities. The handoff and
`EVIDENCE_INPUT` transport continue to name the unique evidence input ID, never the header ID.
The store loads the header by that FK and follows only its normalized witness/binding FKs.

Apply existing UPDATE/DELETE/TRUNCATE rejection to all six tables. Runtime may read and append
unsealed material/associations through the new store; PUBLIC has no access. Every header,
child and seal INSERT, including direct runtime SQL, is **READ COMMITTED only**. Enforce the
isolation guard in database trigger/function entry before acquiring any lock or doing DML;
reject REPEATABLE READ and SERIALIZABLE without changing the caller's isolation. Apply the
same guard to INSERT of the new `RETAINED_INTAKE` evidence kind; existing evidence kinds
retain their current contracts. The Python store likewise refuses a non-READ-COMMITTED caller
transaction before witness DML and never silently changes caller isolation.

Serialize header/child/seal inserts for an existing witness on its common transaction advisory
lock in fixed-search-path, migrator-owned VOLATILE trigger functions. After acquiring the lock, perform
a fresh READ COMMITTED seal check; this sees a concurrently committed seal rather than an
older transaction snapshot. Reject child insertion after a seal, duplicate seals, dangling
FKs and inconsistent seal counts. The seal trigger assigns the server clock, checks package,
settings, request/attempt/capture/pin relations and rejects an explicitly forged clock. For a
new seal, the evidence input's kind/label/content must match the typed witness and its
`recorded_at` must equal the same transaction's server-owned seal time; a caller-backdated
evidence row cannot gain a fresh seal. Exact existing seals are read/reproved, never retimed. Direct
runtime SQL cannot append a child after a concurrent seal. An unsealed or malformed row is
never a consumable witness. Typed FKs and recomputed closure, rather than stored caller JSON,
establish membership; canonical JSON is a checked serialization of that same typed data.

`RetainedIntakeWitnessStore(repository)` uses the existing pool through a bounded helper;
do not refactor the repository or acquire a nested connection while one is held.
`seal(prepared, *, handoff, report) -> RetainedIntakeWitness` reloads the exact package,
settings, publication/version pins, captures and attempts, rederives every association and
records evidence/header/children/seal in one transaction. Refuse caller payload differences
before inserting the witness, and roll back all witness rows on any insert/closure/seal error.
Existing generation rows written by ingest are not falsely claimed to share this transaction.
Require complete reported success/failure request coverage, including captured nonmembers.

The evidence input content hash covers deterministic material hashes/sizes, selector, complete
scope/publication/pins/settings and exact stored association payloads including their stored
clocks. Newly generated evidence/header/binding/link/seal IDs and recorded/sealed times are excluded from
the content preimage. Derive the label from schema/issuer/quarter, never a supplied database
path. Exact repeated/concurrent sealing reuses IDs only after every header, material, child,
label, content and seal payload is reloaded and equal; same hash with a different payload
refuses. Lock before DML and handle competing identical insertions in one whole transaction.
The actual snapshot body is still independently checked by existing capture/extraction code;
metadata material cannot establish a body observation merely by repeating its expected hash.

Root extends the two existing schema fixture files as a disclosed fixture contract expansion:
set `EXPECTED_TABLE_COUNT` to exactly **48**, seed valid rows for all six new tables in reference
order using a genuinely sealed witness from the new store, and return each table's ordinary
primary `id` in the existing seeded map. Preserve every old seed and assertion. The existing
all-table enumeration, populated-row check and runtime/owner UPDATE/DELETE/TRUNCATE loops
must include all six tables. Keep their exact runtime SELECT/INSERT and forbidden mutation
privileges, verify migrator ownership of every new table/sequence/index/function, and explicitly
verify PUBLIC has no new table/sequence/function access. New witness tables are ordinary
runtime-appendable evidence, so do not add them to `PROTECTED_REVIEW_TABLES` to evade checks.
Keep generic `id` insert/read/mutation helpers unchanged. A migration-existence branch may
serve exact historical pre-0010 upgrade fixtures; the current-schema tests require all 48 tables
and a populated, valid sealed witness without any exclusion or new skip.

### Fresh handoff and immutable replay

`FirstPartyGenerationHandoff.retained_intake_witness_id: int | None` names the **evidence input
ID**, defaults to `None`, and is omitted when absent. Witness-mode append prepares before
ingest, constructs/reproves the existing handoff after successful ingest, seals its complete
association, then returns a handoff with that exact ID. It never backfills an old handoff or
chooses a witness by recency. Failure to seal produces no returned handoff.

`reprove_retained_intake_witness(witness, *, package, settings, captures, attempts, pins,
publication) -> tuple[RetainedIntakeRequest, ...]` rehashes and parses durable material,
rederives bindings/context, and checks every normalized association and database clock.
The fresh consumer loads only the handoff's witness evidence ID, verifies kind/label/hash,
sealed material and exact package/publication/generation/settings identity, then uses these
source-derived bindings for attempt validation. Its existing completeness comparison remains
exact source/input/context comparison, never latest selection. Unrelated physical inputs and
other parser contexts before or after this witness do not invalidate the old handoff. Omission
of an actual deciding attempt or one side of a capture/attempt closure still refuses.

Include the witnessed evidence input in `FirstPartyScope.evidence_inputs` and `inputs` using
existing `RunInputKind.EVIDENCE_INPUT`. Existing settings evidence remains included separately.
For `AS_KNOWN`, a witness recorded/sealed after cutoff cannot make its generation selected;
derive the package/input eligibility conservatively from both witness clocks as well as existing
capture/attempt/settings clocks. A forged, naive, contradictory or future-of-store clock refuses;
an honestly later witness is valid but not eligible for an earlier cutoff.

`EvidenceInputRecord` gains an optional typed `retained_intake_witness` value, omitted when
absent. `EvidenceRepository.get_evidence_inputs` enriches only returned `RETAINED_INTAKE` IDs
through `RetainedIntakeWitnessStore.get_by_evidence_ids`. Old kinds execute no witness query.
`ResolvedInputs` already transports the enriched evidence records; add no new resolver field.
`ReplayReader` and SQL `run_inputs` remain unchanged. Missing, duplicate, unsealed or wrong-kind
material for the new kind fails closed. Replay consumes only these manifest-listed evidence IDs
and association IDs already listed as the corresponding package/capture/attempt/settings inputs;
it must reject an association whose required ID escapes the manifest, rather than fetch it.
The witness replay implementer produces two pure APIs in `compare/retained_intake_replay.py`:
`require_witness_manifest_closure(inputs: ResolvedInputs) -> None` and
`require_witness_replay_context(inputs: ResolvedInputs, request: RunRequest, *,
config: LoadedConfig) -> None`. Both use only supplied frozen records and the shared pure proof;
neither owns call sites, performs reads/writes or treats absence of the new evidence kind as an
error. `.25` alone wires the first into `load_inputs` after its existing by-ID completeness checks
and the second before replay's `recompute` engine evaluation. Its witnessed fresh-run composition
must also run the context guard before evaluating a witnessed candidate through `RunEngine`.
Root accepts the exact model/API handshake before `.25` imports or calls these helpers; until
then the public witnessed run route refuses rather than accepting an unproved handoff.
The shared pure reproof uses durable metadata and loaded rows; no original manifest/config file,
latest witness, attempt list, capture lookup, fresh issuer source config or filesystem read is
reachable from witness replay. Existing pinned config loading still proves the normal run pins.

## Tasks and verification

### Task 1: Freeze the existing-seam failure and implement witnessed source/storage

Goal: anchored original material yields a typed prepared witness; exact SQL sealing preserves
its complete generation association and rejects forged, partial or mutable witness records.
Stage: `eqos-u0u.24`.
Files:
- Create: the four evidence helper modules, migration `0010`, and the source/store test files.
- Modify: `capture_intake.py`, `identity_seed.py`, and the small repository evidence-input seam.
- Test: `test_retained_intake_witness.py`, `test_retained_intake_witness_store.py`.
Interfaces:
- Consumes: existing `RetainedIntake`, `IngestReport`, `FirstPartyGenerationHandoff`,
  `EvidenceRepository`, `DirectoryAnchor`, `LoadedConfig` and exact stored generation records.
- Produces: `RetainedIntakeMetadataSource`, `RetainedIntakeRequest`,
  `PreparedRetainedIntakeWitness`, `RetainedIntakeWitness`, preparation/store/reproof APIs above.
Approach: root first writes a positive reverse-XBRL consumer case using the current successful
append and validator APIs. Its current failure at the accepted physical-binding guard is the
genuine behavioral RED. New API/model import failures and setup failures never count. Freeze
that outcome before product edits. Then implement source preparation and the immutable store.
Verification: `scripts/verify.sh red d1b-retained-intake-witness tests/fundamentals/test_retained_intake_witness.py::test_original_retained_reverse_xbrl_handoff_is_consumable`
records the intended guard failure. The source/storage characterization subset of
`uv run pytest -q tests/fundamentals/test_retained_intake_witness.py tests/fundamentals/test_retained_intake_witness_store.py -k 'not original_retained_reverse_xbrl_handoff_is_consumable'`
passes anchored read/selection/material forgery, SQL kind/FK/seal/clock/runtime permission,
idempotence and concurrent seal cases. Add a two-connection case: transaction A establishes a
REPEATABLE READ snapshot before transaction B seals and commits; A then attempts a direct
runtime child INSERT and must refuse before lock/DML, leaving sealed IDs/counts/digest unchanged.
Parametrize all header/child/seal write boundaries for REPEATABLE READ and SERIALIZABLE
refusal. Valid READ COMMITTED competing seals reuse only equal payloads; a child waiting behind
a READ COMMITTED seal sees the committed seal and refuses. Root runs guarded PostgreSQL,
not the implementer.
Test seams: existing append-to-validate reverse fixture; descriptor read replacement; store
transaction failure injection; direct runtime SQL after seal; by-ID evidence reload.
Dependencies: None; the SQL/source parts may be developed concurrently with Task 2 consumers
after this plan and exact interfaces are independently approved.
Risks: test-first. Original failed-peer hashes cannot become their own binding proof. The opt-in
fixture addition for the final positive case is a disclosed contract expansion: root records
and reseals it, preserving the original behavioral failure, rather than claiming unchanged bytes.

### Task 2: Consume the witness through generation, handoff and manifest-only replay

Goal: witnessed failed-XBRL consumption works, while no-witness refusal and old v1/v2 paths
remain exact; replay does not consult changing originals or unlisted source identities.
Stage: `eqos-u0u.24`.
Files:
- Create: `compare/retained_intake_replay.py`, witness replay implementer only.
- Modify: `first_party_generation.py`, evidence implementer; `vendor_handoff_attempts.py`,
  `vendor_handoffs.py`, witness consumer implementer exclusively after approval;
  `resolve.py`, active shared run writer `.25` only after the accepted interface handshake.
- Test: the source test file and new `test_retained_intake_witness_replay.py`; unchanged
  consumer guard and existing first-party generation/bridge/context/replay fixtures.
Interfaces:
- Consumes: Task 1 types/store/reproof APIs, existing report/handoff package and generation IDs.
- Produces: optional evidence-input witness ID on the handoff, proved original request bindings,
  witnessed `FirstPartyScope`, the two pure replay APIs above, and `.25`'s manifest-only durable
  witness replay wiring through `EVIDENCE_INPUT`.
Approach: add only the approved opt-in wrapper behavior; leave legacy and staging failure paths
unchanged. Validate witnessed association before relaxing the one guarded unsupported variant.
Transport complete witness material in the existing by-ID evidence read and enforce manifest
closure before recomputation. Keep the existing successful-member checks and source/context
completeness rules; failed inputs receive no financial or identity promotion.
Verification: `uv run pytest -q tests/fundamentals/test_retained_intake_witness.py tests/fundamentals/test_retained_intake_witness_replay.py tests/fundamentals/test_compare_vendor_handoffs.py tests/fundamentals/test_first_party_generation.py tests/fundamentals/test_first_party_generation_guard.py`
passes the original-source positive case; unrelated body/context attempts before/after; foreign
witness/package/publication/settings/input/schema/clock refusals with no writes; absent witness
legacy guard; exact manifest IDs and by-ID replay with list/FS reads made fatal. Witness creation
before a late cutoff is eligible; the same witness is honestly unselected before its seal time.
Test seams: existing public append/validate; handoff evidence-ID substitution; manifest missing
association ID; fake `ReplayReader` missing or forged typed material; failing list/latest/FS spies.
Dependencies: Task 1 accepted interfaces and verified SQL/storage; root-recorded helper/model
handshake with `.25`, followed by its sole-owner call-site wiring/freeze. Witness and vendor
run integration land serially under root. The witness replay owner does not edit the call site.
Risks: test-first/characterization-first. The optional flag is not a trust credential. Preserve
the two accepted no-witness guard assertions; adding a separate opt-in positive fixture does
not authorize changing them or their archived RED evidence.

### Task 3: Prove upgrade, regressions and the bounded integrated checkpoint

Goal: the new mechanism passes relevant retained/PG integration and immutable upgrade/replay
proof without claiming missing source coverage or full D1b completion.
Stage: `eqos-u0u.24`.
Files:
- Test: the three new witness files and existing vendor/first-party/replay integration files.
- Modify: `tests/fundamentals/pg_evidence_schema_support.py` and
  `tests/fundamentals/test_pg_evidence_schema.py`, Root schema fixture owner only, for the exact
  48-table populated/ACL/mutation contract above; root-owned build notes, progress log and review
  records only after verified results.
Interfaces:
- Consumes: Tasks 1–2 complete witness-aware producer, consumer, replay and migration.
- Produces: exact independent review verdict, fresh verification evidence, local explicit-file
  commit and progress entry; preserved old migration checksums/rows/result/replay evidence.
Approach: run a guarded database with exact committed migrations `0001`–`0009`, seed real
retained Apar v1/v2 rows, a run/manifest/results and accepted queue membership/snapshot, record
IDs and complete payloads, then apply only `0010`. Old rows/pins/queue snapshots and v1/v2 replay
must remain identical. Verify default append/old marked fixture serialization byte-for-byte.
Exercise witnessed actual retained APAR in an isolated database; the private schema-unsupported
mapping is declared synthetic and establishes no real source equivalence. Missing source/ISIN
material remains a separate fail-closed source gate. Independently review before integration.
Verification: the focused three-file witness suite plus existing consumer, first-party generation,
context, actual release, vendor producer, run rules and replay suites pass without added skips;
`uv run pytest -q tests/fundamentals/test_pg_evidence_schema.py` proves all 48 tables seeded,
full immutability/ownership/ACL coverage, and unchanged old assertions. Witnessed-plus-vendor
run replay cases in
`uv run pytest -q tests/fundamentals/test_retained_intake_witness_replay.py tests/fundamentals/test_compare_vendor_runs.py tests/fundamentals/test_compare_runs.py tests/fundamentals/test_compare_run_rules.py`
prove both guards survive `.25`'s shared call-site integration; the public vendor test file is
provided by that existing shared-run plan, not a newly assigned witness edit scope;
scoped Ruff lint/format and strict mypy pass; changed production/test files satisfy the 800-line
cap. Root runs one relevant broad `scripts/verify.sh gate d1b-retained-intake-witness` after the
stable integrated batch and valid root reseal, preserving old recorded failure outcomes. Check
`git status` and immutable migration hashes before claiming this bounded mechanism complete.
Test seams: exact old/new migration directories, retained append/reuse, read-only old-row payload
snapshots, unchanged old manifest replay, runtime immutable witness and queue snapshot reads.
Dependencies: Tasks 1–2, `.25`'s accepted witnessed-plus-vendor call-site integration/freeze,
and independent approval of the integrated implementation.
Risks: Tasks 1–2 form one atomic integration group: the frozen positive consumer case remains
RED until both are present. Develop in an isolated worktree; root lands only the verified group.
The focused checkpoint closes `eqos-u0u.24`, not D1b's integrated public run, authenticated queue
CLI, complete retained source matrix, frozen manifest/e2e or any source-identity gate.

## Plan handoff

Root owns the bead, genuine existing-seam RED, test-contract reseal, guarded PostgreSQL runs,
schema fixture expansion, independent fresh-context critique/approval and final commit/progress
record. Evidence, witness consumer and new pure replay-helper work may run concurrently after
the exact shared interfaces are approved; `.25` alone wires its owned call site after the recorded
handshake, or root records a transfer after its freeze before another editor starts. No user
question is required: root's opt-in decision resolves the compatibility choice. Implementation
starts only after the independent reviewer exercises the source-preparation, seal and replay
boundaries from this plan and returns an approving verdict.

R1 repair record: W01 uses database-enforced READ COMMITTED-only writes and explicit stale-
snapshot/concurrent-seal tests; W02 assigns the exact 48-table schema fixture expansion with
ordinary IDs and preserved all-table/ACL assertions; W03 freezes pure replay helper signatures
and `.25`'s sole call-site ownership with a recorded integration handshake. These are plan
decisions, not claims that the implementation or verification already exists.

## Build notes — 2026-10-13

Root freezes the first existing-seam positive at SHA-256
`ed3006ae91592a8be143ea8eba8d77623e6ae26bef6084d23ef08e087d1533cb`.
Formal `red d1b-retained-intake-witness` records1/1 failed at13:49 UTC. A separate detailed
guarded PG run confirms successful retained XML/PDF registration and PDF package generation,
then the exact existing refusal: "XBRL physical binding is unproven; accepted retained-intake
witness required". This is genuine behavioral RED, not missing API/import or fixture setup.
Production is authorized in the isolated witness worktree; no positive GREEN is claimed yet.

Witness preparation requires original issuer-config material even for an XBRL-only selection,
because the approved contract re-proves issuer/quarter/period from that material. Missing material
refuses in opt-in witness mode; legacy mode retains its existing behavior. This fail-closed ruling
does not authorize a new source filing clock or a replacement SONACOMS original manifest.
