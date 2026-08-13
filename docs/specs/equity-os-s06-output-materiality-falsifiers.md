# S06 — Output, materiality, and observable-falsifier contract

**Status: DRAFT — AWAITING FRESH SOL XHIGH REVIEW**

## Contract purpose

This specification defines the provisional v0 output contract needed to
instrument the manual baseline, the versioned materiality policy, and the
observable-falsifier contract. The output contract remains provisional until
the mandatory post-baseline amendment is completed. This draft does not claim
final A-04 acceptance.

## Authority and ownership

The decision register is the operational authority: “The wording in this
register is authoritative for implementation gates. Narrative reviews explain
rationale but do not override this register.”

| Field | Exact source text |
|---|---|
| Spec ID | `S06` |
| Spec title | `Output, materiality, and observable-falsifier contract` |
| Exact path | `docs/specs/equity-os-s06-output-materiality-falsifiers.md` |
| Primary register IDs | `A-04, A-10` |
| Disposition references | `G-1, G-5, R-4, 6.2` |
| Activation classification | `active-only` |

| ID | Priority | Decision or action | Required evidence / acceptance | Dependencies | Activation-source status |
|---|---:|---|---|---|---|
| A-04 | Critical | Freeze the first output contract | A provisional v0 exists before baseline; final contract after baseline includes event/cutoff, facts, changes, driver analysis, management ledger, thesis impact, observable falsifiers, open questions, calculations, memory draft, and approval record | A-03 for final freeze | Open |
| A-10 | Critical | Define claim materiality policy | Versioned policy combining quantitative magnitude, always-material categories, thesis relevance, source conflict/uncertainty, and coverage-specific overrides; validator test cases approved | A-01, A-02 | Open |

The disposition references contribute these binding interpretations:

- **G-1:** calculations replay according to declared exact, tolerance, or
  stochastic policy; the evidence package is exactly reconstructable; approved
  narrative bytes are immutable and content-hashed. LLM narrative regeneration
  need not be text-identical.
- **G-5:** materiality combines quantitative magnitude, always-material
  categories, thesis relevance, source conflict/uncertainty, and versioned
  coverage-specific overrides. The decision is reviewable and versioned.
- **R-4:** an observable falsifier names the event, metric, management outcome,
  or evidence that would materially weaken or reverse the thesis; a generic
  risk is not a falsifier.
- **6.2:** materiality is not only a financial-statement threshold; governance,
  guidance, thesis relevance, and source conflict are represented.

## Contract stage and amendment gate

This file is the **provisional v0** contract sufficient to instrument A-03. It
must never be represented as the final frozen A-04 contract.

Mandatory gate:

> After A-03 baseline evidence and A-11 bootstrap-thesis acceptance, amend and
> re-review S06 before final A-04 acceptance or dependent final-contract work.

The amendment must use the same maximum review-round policy and require a fresh
delegated Sol xhigh approval. Until that amendment is clean and approved:

- A-04 remains `Open` or `In progress`, never `Accepted`;
- `contract_stage` remains `PROVISIONAL_V0`;
- work that depends on the final A-04 contract is blocked; and
- baseline findings are evidence inputs, not implicit edits or approval.

## Scope

S06 defines:

- the minimum structured output envelope for manual and assisted earnings
  review;
- materiality evaluation inputs, outcomes, policy/version controls, and
  fail-closed behavior;
- the observable-falsifier structure;
- separation of facts, computed results, inferences, forecasts, and opinions;
- content-hash approval and memory-draft isolation; and
- baseline-derived amendment requirements.

### Non-goals

This spec does not define final observation/fact or claim storage schemas,
implement deterministic calculators, approve a company thesis, promote memory,
define distribution/legal sufficiency, or guarantee bit-identical regeneration
of model-written narrative. It does not treat every large value as material or
every small value as immaterial. It does not permit free-form prose to bypass
typed evidence or materiality validation.

## Interfaces and data contracts

### Canonical JSON digest contract

Every structured-record digest defined by S06 is lowercase SHA-256 of canonical
JSON bytes: UTF-8, object keys sorted, no insignificant whitespace, Unicode
emitted directly, JSON booleans/null, and arrays retained in declared order.
For each record digest, the preimage is the record's complete logical JSON
object with exactly the field that stores that digest omitted. Other digest
fields remain because they bind referenced content. `artifact_sha256`,
`candidate_claim_inventory_sha256`, `claim_content_sha256`, `policy_sha256`,
`decision_sha256`, `falsifier_sha256`, and `draft_sha256` therefore omit only
themselves from their respective preimages. Unknown fields are invalid rather
than silently excluded from hashing. The canonical serialization of
`EarningsReviewOutputV0` without `artifact_sha256` is the exact approved output
preimage; changing any narrative string changes those canonical bytes.

### `EarningsReviewOutputV0`

Every output is immutable by version and contains every field below. Empty
collections are explicit; missing required fields fail validation.

| Field | Contract |
|---|---|
| `output_id`, `output_version`, `contract_version` | Stable identity; `contract_version` identifies this provisional v0 until amended |
| `contract_stage` | `PROVISIONAL_V0` or, only after the amendment gate, `FINAL_V1` |
| `company_id`, `run_id`, `evidence_package_id` | Stable identities resolving to authoritative records |
| `candidate_claim_inventory_id` / `candidate_claim_inventory_sha256` | Exact immutable candidate inventory emitted by the producing run |
| `candidate_claim_ids` | Exact lexicographically sorted unique set of every claim in that inventory; no pre-evaluation omission or filtering |
| `event` | Typed event kind, reporting period, publication/occurrence time, exact source set |
| `knowledge_cutoff` | UTC cutoff enforced by the run; every input must be available by it |
| `facts` | Reconciled fact references with source, scope, period, units/currency, valid time, knowledge time, and revision state |
| `changes` | Current/prior fact references, comparable basis, absolute/relative change, and reconciliation note |
| `driver_analysis` | Typed claim references explaining drivers, each with epistemic class, evidence direction, assumptions, and uncertainty |
| `management_ledger` | New, modified, due, and outcome records linked to exact management commitments and sources |
| `thesis_impact` | Explicit unchanged/strengthened/weakened/reversed/uncertain assessment with supporting claim IDs and assumptions |
| `observable_falsifiers` | Typed falsifier records defined below |
| `open_questions` | Question, why it matters, required evidence, owner/status if known |
| `calculations` | Calculation-trace references; the narrative is never the authoritative calculator |
| `memory_draft` | Draft-only proposed canonical-thesis changes with provenance and diff; never promoted by output creation |
| `materiality_decisions` | Exactly one current policy-, inventory-, and claim-content-bound decision for every `candidate_claim_id` |
| `approval_record` | Separate approval reference bound to exact canonical artifact bytes/hash |
| `artifact_sha256` | Digest of the canonical output preimage defined above |

Every narrative claim carries a unique `claim_id` and an epistemic class:
`observed`, `computed`, `inferred`, `forecast`, or `opinion`. Material
observed/computed claims resolve to direct facts or calculation traces.
Material inferred/forecast claims link evidence, assumptions, uncertainty, and
falsifiers. Prose is the display layer, not evidence authority.

### `CandidateClaimInventory`

The producing run opens this append-only inventory before materiality
evaluation, narrative suppression, or output selection. It includes every
structured or narrative assertion proposed, imported, derived, displayed,
used as support, or considered for `facts`, `changes`, `driver_analysis`,
`management_ledger`, `thesis_impact`, `open_questions`, calculations,
falsifiers, or the memory draft, including candidates later rejected or omitted
from display. Each entry contains a unique claim ID, exact content, epistemic
class, origin stage/slot, evidence or calculation references, disposition, and
`claim_content_sha256`. That digest binds the entry's complete canonical
claim-content object with only `claim_content_sha256` omitted, so retaining an
ID while changing content, type, origin, support, or disposition changes the
digest. Every claim-producing stage must append its candidate before the claim
can be evaluated, used, or discarded. The run closes and makes the inventory
immutable only after all such stages are complete, and
`candidate_claim_inventory_sha256` binds its canonical preimage.

Output validation requires an exact-set match between the closed inventory and
`candidate_claim_ids`, an exact one-to-one match between those IDs and
`materiality_decisions`, and registration of every claim ID reachable from any
output field. Each decision must name the output's exact
`candidate_claim_inventory_id` and `candidate_claim_inventory_sha256` and the
matching inventory entry's current `claim_content_sha256`. A claim cannot avoid
evaluation by retaining its ID while changing content, being described as
obviously immaterial, being omitted from the final narrative, or being
introduced only as support.

### `MaterialityPolicy`

A policy is immutable by version and contains:

| Field | Contract |
|---|---|
| `policy_id`, `version`, `effective_from`, `supersedes` | Stable identity, version history, and effective time |
| `quantitative_rules` | Metric/basis, comparison base, operator, threshold, unit/currency, scope, and rationale |
| `always_material_categories` | At minimum guidance, restatements, auditor qualifications, going concern, promoter pledges, related-party transactions, capital raises, material dilution, major corporate actions, management changes, and regulatory actions |
| `thesis_relevance_rules` | Assumption, catalyst, risk, valuation input, management credibility, and thesis-breaker effects |
| `uncertainty_conflict_rules` | Low-confidence extraction, unresolved contradiction, missing source, and conflicting-source treatment |
| `coverage_overrides` | Company/mandate scope, rule changed, rationale, approver, effective/expiry time, and evidence |
| `precedence` | Fail-closed combination rules defined below |
| `validator_fixture_ids` | Approved positive, negative, boundary, conflict, and override cases |
| `approval_record_ids` | Current typed human approvals bound to exact policy and fixture hashes |
| `policy_sha256` | Canonical policy-content hash |

Policy precedence is fixed:

1. any applicable always-material category yields `MATERIAL`;
2. any applicable thesis-relevance rule yielding material impact yields
   `MATERIAL`;
3. unresolved source conflict, required-input absence, or important low
   confidence yields `REVIEW_REQUIRED`, never `NOT_MATERIAL`;
4. a current approved coverage override applies only to its exact scope and may
   not suppress always-material categories without a separately approved policy
   amendment; and
5. quantitative rules are evaluated on explicit comparable bases. Unknown,
   ambiguous, or unit-incompatible inputs yield `REVIEW_REQUIRED`.

### `MaterialityDecision`

Each decision contains `decision_id`, `claim_id`, `claim_content_sha256`,
`candidate_claim_inventory_id`, `candidate_claim_inventory_sha256`,
`policy_id/version/hash`, evaluated quantitative inputs and rule results,
matched always-material categories, thesis-relevance results,
conflict/uncertainty state, applied coverage override and approval, result,
rationale, reviewer state, evidence references, timestamp, and
`decision_sha256`. It also contains one explicit dimension evaluation for each
of `QUANTITATIVE`, `ALWAYS_MATERIAL`, `THESIS_RELEVANCE`,
`UNCERTAINTY_CONFLICT`, and `COVERAGE_OVERRIDE`. Every rule in every dimension
records its inputs, evidence, and `MATCHED`, `NOT_MATCHED`, `NOT_APPLICABLE`, or
`UNKNOWN` result; `NOT_APPLICABLE` requires a rationale. Evaluation is
exhaustive and does not short-circuit after a material match.

The closed result set is `MATERIAL`, `NOT_MATERIAL`, and `REVIEW_REQUIRED`.
`NOT_MATERIAL` requires complete inputs and a reasoned policy result; it is not
the default. Candidate-inventory, claim-content, policy, or evidence changes
invalidate the decision and require evaluation against the changed content.

### `ObservableFalsifier`

Each falsifier contains:

- `falsifier_id` and the exact thesis/assumption/claim IDs it tests;
- `observable_type`: `EVENT`, `METRIC`, `MANAGEMENT_OUTCOME`, or `EVIDENCE`;
- a measurable observation definition, scope, source class, period/horizon,
  comparator/trigger when applicable, and expected evaluation cadence;
- `thesis_effect`: `MATERIALLY_WEAKEN` or `REVERSE`;
- current state: `UNOBSERVED`, `SUPPORTED`, `TRIGGERED`, `CONFLICTED`, or
  `UNKNOWN`, with evidence and evaluation timestamp; and
- version, supersession link, owner/status if known, and
  `falsifier_sha256`.

A risk statement without an observable trigger and specified thesis effect is
invalid. `UNKNOWN` or `CONFLICTED` cannot be silently treated as untriggered.

### `MemoryDraft`

The memory draft contains the approved prior thesis ID/hash, proposed diff,
supporting claim/fact/calculation references, provenance, authoring run, and
`draft_sha256`. It is always `DRAFT`; only a separate human-approved memory
promotion transaction may affect the canonical thesis.

## Invariants and fail-closed behavior

1. Every output declares event, knowledge cutoff, evidence package, contract
   version/stage, and exact artifact hash.
2. Every candidate claim appears in the closed candidate inventory and has
   exactly one explicit current materiality decision bound to that exact
   inventory ID/hash and claim-content digest and covering every policy
   dimension and rule. Every material claim has the evidence required for its
   epistemic class. Any inventory, content, or decision mismatch, skipped
   dimension, or missing support blocks approval.
3. `REVIEW_REQUIRED`, unknown policy version, stale policy hash, missing
   coverage-override approval, unit/period ambiguity, or unresolved source
   conflict blocks a final materiality result and output approval.
4. Always-material categories cannot be downgraded by a quantitative threshold
   alone.
5. Facts, calculations, inferences, forecasts, and opinions remain typed and
   visibly distinct. Retrieval or prose cannot convert one class into another.
6. Calculation results resolve to registered traces. Exact-class operators
   replay exactly; tolerance-class operators use declared tolerances;
   stochastic operators retain seeds and distribution tests where applicable.
7. The evidence package reconstructs from registered identifiers. Approved
   narrative bytes are immutable and hash-bound; regenerated prose is a new
   artifact requiring review, not proof of reproduction.
8. Every thesis impact contains at least one observable falsifier; generic
   risks and a no-falsifier approval or waiver do not satisfy the requirement.
9. Memory drafts never write canonical thesis state. Output approval and memory
   promotion are separate human decisions.
10. Any mutation to source evidence, candidate inventory, candidate claim
    content, policy, materiality decision, output, calculation trace, falsifier,
    or approval makes dependent proofs stale.
11. `FINAL_V1` is forbidden until A-03 baseline evidence exists, A-11 has a
    current approved and versioned bootstrap thesis, and the S06 amendment has
    received a fresh clean Sol xhigh delegated approval plus all required human
    acceptance.

## Evidence and typed human-approval gates

Each gate is separate and requires one matching record. A clean Sol review can
satisfy only delegated artifact approval and never supplies analyst, domain,
legal, regulatory, distribution, or memory-promotion authority.

| Gate | Approval type | Required authority | Minimum evidence | Fail-closed result |
|---|---|---|---|---|
| Initial S06 v0 review | `DELEGATED_ARTIFACT_APPROVAL` | Fresh Sol xhigh reviewer under delegated goal authority | Persisted clean review, exact source/artifact hashes, review round, timestamp | S06 remains draft; baseline blocked |
| Materiality policy and validator fixtures | `ANALYST_ACCEPTANCE` | Competent analyst accountable for materiality judgments | Exact policy/fixture hashes, boundary/conflict cases, decision and authority evidence | A-10 remains open |
| Coverage-specific override | `ANALYST_ACCEPTANCE` | Competent analyst for the named coverage scope | Exact override, rationale, scope, effective/expiry time, evidence | Override ignored |
| Provisional v0 use for baseline | `ANALYST_ACCEPTANCE` | Competent baseline analyst | Exact v0 hash, instrumentability assessment, known gaps | A-03 cannot consume v0 |
| Post-baseline amended S06 review | `DELEGATED_ARTIFACT_APPROVAL` | Fresh Sol xhigh reviewer under delegated goal authority | Baseline evidence, amended hash, finding/fix history, clean review | A-04 cannot be final |
| Final output-contract acceptance | `ANALYST_ACCEPTANCE` | Competent analyst accountable for the first output contract | Exact final contract and fixtures, baseline-derived changes, current A-11 thesis approval/version/hash, known limits | A-04 remains open |
| Each output artifact | `ANALYST_ACCEPTANCE` | Competent reviewing analyst | Exact artifact hash, evidence package, materiality decisions, corrections | Artifact is unapproved |
| Canonical-thesis update | `MEMORY_PROMOTION` | Competent analyst authorized to promote memory | Exact prior thesis, proposed diff/hash, provenance, approval resolution | Memory draft remains noncanonical |

If an output crosses the current private/internal boundary, S01's distinct
`LEGAL_REVIEW`, `REGULATORY_REVIEW`, and `DISTRIBUTION_APPROVAL` gates apply.
They are never inferred from output or analyst approval.

## Acceptance tests and verification

### Provisional v0 tests

1. Validate a complete output fixture containing every required field and each
   epistemic class.
2. Reject missing event/cutoff, unresolved fact/calculation references, absent
   approval, missing hash, or an untyped claim.
3. Reconstruct an evidence package exactly and verify the approved narrative
   bytes by hash without requiring regenerated prose to be text-identical.
4. Exercise materiality fixtures covering every quantitative boundary, every
   always-material category, thesis relevance, source conflict, low confidence,
   and a scoped override.
5. Prove small-but-governance-critical and thesis-critical items are material;
   prove a large-looking but noncomparable value cannot be automatically
   classified.
6. Reject `NOT_MATERIAL` when required inputs are missing, conflicting,
   ambiguous, unit-incompatible, or policy-stale.
7. Assert the closed candidate inventory, `candidate_claim_ids`, and
   materiality decisions are exact matching sets; require every decision to
   bind the exact inventory ID/hash and matching claim-content digest and every
   policy rule in all five dimensions to have an explicit result for every
   candidate.
8. Omit an apparently immaterial, rejected, display-suppressed, or support-only
   candidate or its decision and prove approval fails closed.
9. Change one candidate's content, epistemic class, support, or disposition
   while retaining its `claim_id`; prove its prior decision and output approval
   become stale and approval remains blocked until that exact changed claim is
   reevaluated under the current inventory and policy.
10. Reject a generic risk and a zero-falsifier thesis impact even when an analyst
   supplies a no-falsifier approval; accept each observable type only when
   trigger, horizon, evidence source, and thesis effect are explicit.
11. Trigger, conflict, and invalidate falsifier evidence and prove the thesis
   impact becomes review-required.
12. Attempt to promote a memory draft through output approval and prove canonical
   thesis state is unchanged.
13. Compute output, candidate-inventory, claim-content, policy, decision,
    falsifier, and memory-draft digests from their canonical JSON preimages;
    prove key order and insignificant whitespace do not change a digest, each
    own digest field is excluded without recursion, referenced digests remain
    bound, and any canonical-preimage content mutation or referenced
    evidence/calculation byte mutation makes all dependent approvals and
    verification results stale.

### Mandatory amendment verification

After A-03 and A-11, the amendment must:

1. inventory every baseline output field used, missing, ambiguous, redundant,
   or added outside v0;
2. reconcile those observations into explicit retained, changed, added, and
   deferred contract decisions with evidence;
3. rerun all v0 fixtures plus baseline-derived fixtures;
4. receive a fresh clean Sol xhigh review and separate analyst acceptance bound
   to the amended bytes;
5. resolve the current approved A-11 bootstrap-thesis version/hash and its
   observable falsifiers;
6. attempt final freeze with complete A-03 and clean amendment evidence but a
   missing, stale, or unapproved A-11 thesis and prove it fails closed; and
7. prove `contract_stage=FINAL_V1` is impossible until all six prior steps
   pass.

Verification results must identify exact command argv, repository-relative
scope, expected and actual exit code, immutable output evidence, content hashes,
and execution timestamp. Agent reports, copied status strings, and unaudited
screenshots are not proof.

## Dependencies

- **A-10** depends on A-01 boundary and A-02 discovery-company selection.
- **A-03 / S05** consumes provisional A-04 v0 and the A-10 policy.
- **A-04 final freeze** depends on completed A-03 baseline evidence, then a
  current approved A-11 bootstrap thesis, then the mandatory S06
  amendment/re-review.
- **S11/S16** own run-manifest/reproducibility and deterministic-compute details;
  S06 consumes their identifiers and traces without duplicating ownership.
- **S13** owns the final claim schema and vocabulary registry; S06 defines
  output-level requirements and materiality semantics only.
- **S15/S19** own review/promotion transactions; S06 requires their distinct
  approvals and fail-closed separation.

The provisional contract can support A-03 but cannot unblock any dependency
that requires final A-04 acceptance.
