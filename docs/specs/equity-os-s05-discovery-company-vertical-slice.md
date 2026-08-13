# S05 — Discovery-company vertical slice, manual baseline, and bootstrap thesis

**Status: DRAFT — AWAITING FRESH SOL XHIGH REVIEW**

## Contract purpose

This specification defines the minimum coherent discovery-company experiment:
four consecutive quarters consisting of one manually completed baseline and
bootstrap thesis followed by three reserved assisted incremental updates. It
owns selection, baseline execution, and bootstrap-thesis acceptance. It does
not implement the assisted earnings-review workflow.

## Authority and ownership

The decision register is the operational authority: “The wording in this
register is authoritative for implementation gates. Narrative reviews explain
rationale but do not override this register.”

| Field | Exact source text |
|---|---|
| Spec ID | `S05` |
| Spec title | `Discovery-company vertical slice, manual baseline, and bootstrap thesis` |
| Exact path | `docs/specs/equity-os-s05-discovery-company-vertical-slice.md` |
| Primary register IDs | `A-02, A-03, A-11` |
| Disposition references | `G-4, M-1, 6.8` |
| Activation classification | `active-only` |

| ID | Priority | Decision or action | Required evidence / acceptance | Dependencies | Activation-source status |
|---|---:|---|---|---|---|
| A-02 | Critical | Select one discovery company and four consecutive quarters | Quarter 0 is reserved for the manual baseline and bootstrap thesis; Quarters 1–3 are reserved for three assisted incremental updates; source package exists for all quarters and at least one management commitment can be tracked across periods | — | Open |
| A-03 | Critical | Define and perform the manual baseline workflow | Quarter 0 is completed manually with time-stamped reading, source location, verification, calculation, drafting, and approval; the same lightweight instrumentation is used in manual and assisted workflows and its overhead is recorded | A-02, A-04 v0, A-10, A-13 | Open |
| A-11 | Critical | Author and approve bootstrap thesis for the discovery company | Using Quarter 0, a concise initial thesis, assumptions, management commitments, risks, open questions, and observable falsifiers are manually written, approved, versioned, and available before Quarter 1; full initiation remains deferred | A-03 | Open |

The disposition references contribute these binding interpretations:

- **G-4:** the manual and assisted primary comparisons use different quarters;
  one baseline/bootstrap quarter plus three later assisted quarters is the
  minimum coherent slice. Remaining practice effects are recorded, and
  time-and-motion components are retained alongside total elapsed time.
- **M-1:** Quarter 0 creates a concise analyst-authored bootstrap coverage thesis
  instead of expanding the slice into a full company-initiation product.
- **6.8:** a manual baseline not reused for assisted work plus three assisted
  updates requires four quarters, exactly Q0 through Q3.

## Scope

S05 defines and requires:

1. a reproducible discovery-company selection record;
2. an immutable four-quarter slice manifest;
3. a source package for each of four consecutive quarters;
4. a manually executed and instrumented Quarter 0 baseline;
5. a manually authored, approved, and versioned bootstrap coverage thesis;
6. reservation of Quarters 1–3 for later assisted incremental updates; and
7. an experiment log that preserves overhead, ordering, familiarity, missing
   sources, and other confounds.

### Non-goals

This spec does not automate full company initiation, implement the
earnings-review workflow, create the three assisted reports, select Phase 1
companies, establish provider rights, define final fact or claim schemas, or
claim causal/statistical significance from one company. It does not reuse Q0
as an assisted update. Full automated company initiation remains deferred.

## Interfaces and data contracts

### Canonical JSON digest contract

Every structured-record digest defined by S05 is lowercase SHA-256 of canonical
JSON bytes: UTF-8, object keys sorted, no insignificant whitespace, Unicode
emitted directly, JSON booleans/null, and arrays retained in declared order.
For each record digest, the preimage is the record's complete logical JSON
object with exactly the field that stores that digest omitted. Other digest
fields remain because they bind referenced content. `manifest_sha256`,
`event_sha256`, `package_sha256`, `disposition_sha256`, and `thesis_sha256`
therefore omit only themselves from their respective preimages. Unknown fields
are invalid rather than silently excluded from hashing.

### `DiscoverySliceManifest`

The manifest is immutable after baseline start; corrections create a new
version linked to the prior version and require revalidation of affected work.

| Field | Contract |
|---|---|
| `slice_id` / `manifest_version` | Stable identity and monotonic version |
| `company_id` | Stable internal discovery-company identity |
| `selection_rationale` | Disclosure quality, source availability, structural manageability, and known limitations |
| `quarters` | Exactly four consecutive typed periods with roles `Q0_BASELINE`, `Q1_ASSISTED`, `Q2_ASSISTED`, `Q3_ASSISTED` exactly once |
| `source_package_ids` | One nonempty immutable package reference per quarter |
| `management_commitment_candidate_ids` | At least one commitment observable across periods |
| `selection_evidence_ref_ids` | Content-bound evidence for selection and availability |
| `created_at` / `created_by` | UTC time and accountable actor |
| `manifest_sha256` | Digest of the canonical manifest preimage defined above |

Each quarter entry contains period start/end, event/publication timestamp,
knowledge cutoff, role, source-package ID/hash, source completeness assessment,
and explicit gaps. Period labels and source timestamps are never inferred from
filenames.

### `BaselineInstrumentationEvent`

Every baseline action emits an immutable event with:

- `event_id`, `baseline_run_id`, `activity_type`, UTC `started_at` and
  `ended_at`, active-work duration, actor, source/artifact references, and
  `event_sha256`;
- `activity_type` from the closed set `READING`, `SOURCE_LOCATION`,
  `VERIFICATION`, `CALCULATION`, `DRAFTING`, `APPROVAL`, and
  `INSTRUMENTATION_OVERHEAD`; and
- pause/restart reason and correction/supersession link when applicable.

The same event schema and measurement rules must be usable without semantic
changes by the assisted workflow. Instrumentation overhead is separately
recorded and included in total workflow economics.

### `ManualBaselinePackage`

The Q0 package contains:

- manifest and source-package identities/hashes;
- event and knowledge cutoff;
- exact source locations for every recorded fact used;
- registered calculation inputs, assumptions, outputs, code/version, and trace;
- draft artifact and final approved artifact identities/hashes;
- complete instrumentation events and total durations by activity;
- review corrections, source-conflict records, unresolved gaps, and approval
  evidence; and
- `package_sha256` binding all component identities, versions, and referenced
  digests under the canonical preimage contract.

The manual baseline uses only evidence available at its declared cutoff. A
missing source, ambiguous period/unit, unresolved conflict, calculation gap, or
missing approval is recorded and blocks acceptance rather than being silently
filled.

### `SourceConflictDisposition`

Every conflict between source occurrences is preserved under one stable
`conflict_id` with all occurrence IDs/hashes, affected fact/claim/calculation
IDs, conflict description, and status. The closed status set is `OPEN`,
`RESOLVED`, and `EXCLUDED_FROM_BASELINE`. `RESOLVED` requires a typed resolution
of `AUTHORITATIVE_SOURCE_SELECTED`, `SCOPES_DISTINGUISHED`, or
`SOURCE_CORRECTED`, plus nonempty evidence references, rationale, resolver,
timestamp, and current `ANALYST_ACCEPTANCE` bound to the exact disposition.
`EXCLUDED_FROM_BASELINE` requires evidence that every affected item and
dependent output was removed, plus the same typed analyst acceptance. A review,
acknowledgement, or deferred decision does not change `OPEN`; any `OPEN`,
unevidenced, stale, or unmatched disposition blocks baseline acceptance. Every
record carries `disposition_sha256` under the canonical preimage contract, and
the analyst acceptance binds that exact digest.

### `BootstrapCoverageThesis`

The Q0 bootstrap thesis is concise, analyst-authored, immutable by version, and
contains:

| Required section | Contract |
|---|---|
| `current_thesis` | The approved analytical view, not “current truth” or a recommendation |
| `key_assumptions` | Typed assumption, scope, horizon, evidence, and uncertainty |
| `management_commitments` | Commitment, source, date made, due period, and observable outcome |
| `risks` | Specific risk, mechanism, evidence, horizon, and thesis relevance |
| `open_questions` | Question, evidence needed, owner/status if known |
| `observable_falsifiers` | Observable event, metric, management outcome, or evidence that would materially weaken or reverse the thesis |
| `approval_record` | Separate human approval bound to exact canonical thesis bytes/hash |
| `thesis_sha256` | Digest of the canonical thesis preimage defined above |

The thesis version, approval, and hash must be available before any Q1 assisted
run is registered.

## Invariants and fail-closed behavior

1. There is exactly one discovery company and exactly four consecutive
   quarters in the slice.
2. Q0 is baseline/bootstrap only; Q1–Q3 are assisted-update quarters. No quarter
   can occupy two roles or be substituted after baseline start without a new
   manifest version, impact review, and reapproval.
3. All four source packages exist and are content-hashed before A-02 acceptance.
   Known incompleteness is explicit; missing critical evidence blocks baseline
   or assisted use.
4. At least one management commitment has a sourced starting statement and an
   outcome that can be observed in a later reserved quarter.
5. Manual and assisted workflows use the same activity taxonomy, timestamps,
   pause rules, and overhead accounting.
6. The manual baseline is performed before the bootstrap thesis is approved;
   the approved thesis exists before Q1 begins.
7. Approval applies to exact canonical artifact bytes. Later edits create a new
   version and require a new approval; an agent draft never becomes the
   approved thesis.
8. Practice effect, familiarity, source gaps, interruptions, and instrumentation
   overhead remain visible in the experiment log and are not normalized away.
9. Results are descriptive for the slice. Report-level percentiles or claims of
   independent claim-level samples are prohibited at this scale.
10. Full initiation remains deferred; the bootstrap thesis cannot be relabeled
    as a completed initiation product.
11. Every source conflict is either evidentially `RESOLVED` or fully
    `EXCLUDED_FROM_BASELINE` under a current typed analyst disposition before
    baseline acceptance. `OPEN` and merely reviewed conflicts remain blockers.

## Evidence and typed human-approval gates

The obligations below are distinct. A clean Sol review may satisfy only the
delegated artifact approval and cannot approve company selection, baseline
work, or the thesis.

| Gate | Approval type | Required authority | Minimum evidence | Fail-closed result |
|---|---|---|---|---|
| S05 artifact review | `DELEGATED_ARTIFACT_APPROVAL` | Fresh Sol xhigh reviewer under delegated goal authority | Persisted clean review, source hashes, round, timestamp | Spec remains draft |
| Discovery-company and quarter selection | `PRODUCT_OWNER_DECISION` | Competent human product owner | Exact company, four-quarter manifest, source availability, rationale, conflicts | A-02 remains open |
| Q0 manual baseline acceptance | `ANALYST_ACCEPTANCE` | Competent analyst who reviewed the completed baseline | Exact package hash, timing log, source locations, calculations, corrections | A-03 remains open |
| Bootstrap thesis acceptance | `ANALYST_ACCEPTANCE` | Competent analyst accountable for the coverage thesis | Exact thesis version/hash, complete required sections, source evidence | A-11 remains open and Q1 is blocked |

If company/source selection requires rights, provider, budget, capacity,
purchase, credentials, or external coordination decisions, the corresponding
typed approvals remain separately required under S02/S08 and the canonical
human-review process. None is inferred from product-owner or analyst approval.

## Acceptance tests and verification

### Structural acceptance

1. Parse the manifest and assert one company, four unique consecutive quarters,
   and the exact Q0/Q1/Q2/Q3 role sequence.
2. Resolve and hash every source package; assert one package per quarter and at
   least one cross-period management commitment candidate.
3. Assert every manual-baseline activity type is instrumented and overhead is
   recorded using the same schema declared for assisted runs.
4. Assert every baseline fact and calculation resolves to an exact source or
   registered calculation trace and respects the declared cutoff.
5. Assert the baseline package has a current analyst approval bound to its exact
   hash.
6. Assert the bootstrap thesis contains every required section, has a distinct
   current analyst approval bound to exact canonical bytes, and predates Q1
   registration.
7. Assert Q0 is absent from assisted-run inputs and Q1–Q3 have no completed
   assisted output at the S05 acceptance point.
8. Compute manifest, instrumentation-event, baseline-package,
   conflict-disposition, and thesis digests from their canonical JSON
   preimages; prove key order and insignificant whitespace do not change a
   digest, each own digest field is excluded without recursion, referenced
   digests remain bound, and any semantic record mutation or referenced
   source/artifact byte mutation makes the associated approval and downstream
   readiness stale.
9. For every source conflict, assert a current evidenced `RESOLVED` or
   `EXCLUDED_FROM_BASELINE` disposition with matching analyst acceptance;
   reject `OPEN`, review-only, unevidenced, stale, or partially excluded cases.

### Scenario acceptance

- Reject a three-quarter manifest, non-consecutive periods, reused Q0, missing
  source package, or missing management commitment candidate.
- Pause and resume a manual activity without losing active time or double
  counting overhead.
- Record a discovered source conflict without overwriting either occurrence;
  prove baseline acceptance remains blocked until an evidenced `RESOLVED` or
  `EXCLUDED_FROM_BASELINE` typed disposition is accepted, and that explicit
  review alone does not unblock it.
- Attempt Q1 registration without the approved bootstrap thesis and prove it
  fails closed.

Verification results must store exact command argv, exit code, immutable output
evidence, artifact hashes, and execution time. Agent statements and status
labels alone are not proof.

## Dependencies and sequence

- **A-02:** has no register dependency and precedes all other S05 work.
- **A-03:** requires A-02 plus provisional A-04 v0 from S06, materiality policy
  A-10 from S06, and success metrics A-13 from S08.
- **A-11:** requires the completed A-03 baseline.
- **B-02 / S14:** later owns production of the Q1–Q3 assisted updates; S05 only
  reserves those quarters and supplies the approved preceding thesis.

The binding operational sequence is: select company/four quarters; define
materiality and measurement; establish A-04 v0; perform Q0 baseline; approve
the bootstrap thesis; freeze the final A-04 contract; then begin Q1–Q3 assisted
updates.

There is no evidence-derived amendment gate assigned to S05. A source or
selection change after baseline start is a new manifest version with impact
review and fresh human approvals, not silent amendment of history.
