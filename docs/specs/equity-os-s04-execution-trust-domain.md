# S04 — Execution trust-domain boundary

**Status: DRAFT — AWAITING FRESH SOL XHIGH REVIEW**

## Contract purpose

This specification defines the fail-closed boundary that must exist before any
Equity-OS output can reach an execution system. It specifies dormant behavior,
activation evidence, interfaces, isolation controls, and approval gates. It does
not activate execution or approve any execution-connected use.

## Authority and ownership

The decision register is the operational authority: “The wording in this
register is authoritative for implementation gates. Narrative reviews explain
rationale but do not override this register.”

| Field | Exact source text |
|---|---|
| Spec ID | `S04` |
| Spec title | `Execution trust-domain boundary` |
| Exact path | `docs/specs/equity-os-s04-execution-trust-domain.md` |
| Primary register IDs | `E-09` |
| Disposition references | `T-4, 6.7` |
| Activation classification | `dormant-only` |

| ID | Priority | Decision or action | Required evidence / acceptance | Dependencies | Activation-source status |
|---|---:|---|---|---|---|
| E-09 | Critical | Keep execution in a separate trust domain | Separate service, credentials, database, deterministic limits, approvals, kill switch, and reconciliation | E-08 | Deferred |

The disposition references contribute these binding interpretations:

- **T-4:** current regulatory verification is mandatory before external, paid,
  personalized, or execution-connected use. A private-use boundary statement
  alone is not evidence of legal sufficiency.
- **6.7:** claims about an existing Temporal, Partner, Bodha, homelab, or
  PostgreSQL deployment are unsupported by the reviewed files and must not be
  treated as architecture facts. No particular infrastructure is selected here.

## Activation classification and guard

E-09 was `Deferred` at the pinned activation snapshot, and S04 owns no active
register row. Therefore S04 is dormant-only. Authoring and reviewing this
contract approves only its gates and dormant behavior; it does not authorize
planning, implementation, credentials, deployment, connection, or operation of
an execution service.

E-09 may leave dormancy only when all of the following are current and valid:

1. the live register records E-08 as `Accepted` and its required current legal
   and regulatory evidence is satisfied for the intended execution-connected
   mode;
2. the canonical activation predicate for E-09 recomputes `TRUE` from current,
   content-bound evidence;
3. a competent human has issued a distinct active `ACTIVATE_DEFERRED` resolution
   whose exact scope is E-09 and whose evidence is bound to the activation
   record; and
4. ledger reconciliation lawfully changes E-09 from `Deferred` to `Open` or
   `In progress` and changes its program disposition from
   `CONDITIONAL_UNACTIVATED` to `CONDITIONAL_ACTIVATED`.

An inferred need, an agent recommendation, completion of this spec, nearby
approval, E-08 dependency satisfaction alone, or a copied ledger label cannot
activate E-09. `FALSE`, `UNKNOWN`, expired, missing, or digest-stale activation
evidence keeps the component dormant.

## Scope

When activated, the execution trust domain must provide:

- a separately deployed service boundary with no in-process execution path from
  the research runtime;
- execution-only credentials unavailable to the research runtime, document
  parsers, retrieval tools, prompts, and generated artifacts;
- an execution-owned database or store, with no shared mutable database tables
  or credentials across the boundary;
- deterministic, versioned pre-trade limits checked independently of model or
  narrative output;
- explicit human approvals bound to an immutable execution request;
- a fail-closed kill switch that prevents new actions and supports controlled
  cancellation where the external venue allows it; and
- reconciliation between authorized requests, submitted actions, external
  acknowledgements, fills or outcomes, cancellations, and internal records.

### Non-goals

This spec does not select a broker, venue, service framework, workflow engine,
database product, hosting environment, order type, trading strategy, portfolio
construction method, or credential manager. It does not define paid/public or
personalized distribution as legally sufficient. It does not enable paper or
live trading, and it does not permit research agents to invoke execution.

## Interfaces and data contracts

All messages are immutable, versioned, uniquely identified, content-hashed, and
auditable. Unknown fields, schema versions, identities, or enum values fail
closed.

### `ExecutionIntent`

The research domain may produce an inert candidate only. The candidate cannot
be submitted directly and has no credential-bearing or executable field.

| Field | Contract |
|---|---|
| `intent_id` | Stable unique identifier |
| `schema_version` | Registered interface version |
| `research_artifact_id` / `research_artifact_sha256` | Exact approved source artifact and bytes |
| `company_id` / `security_id` | Stable internal identities; external symbols are mappings, not authority |
| `proposed_action` | Typed candidate action from a closed enum |
| `quantity_or_notional` | Typed value with currency/unit and no implicit conversion |
| `constraints` | Explicit time, price, exposure, and validity bounds |
| `rationale_claim_ids` | References only; prose cannot change control logic |
| `created_at` / `expires_at` | UTC timestamps; expired intent is invalid |
| `content_sha256` | Hash of canonical intent content |

### `ExecutionAuthorization`

The execution domain accepts a candidate only after producing a separate,
immutable authorization record.

| Field | Contract |
|---|---|
| `authorization_id` | Stable unique identifier |
| `intent_id` / `intent_sha256` | Exact bound candidate |
| `approver_identity` / `authority_basis` | Competent human identity and current authority evidence |
| `decision` | `APPROVED`, `DENIED`, `REVOKED`, or `EXPIRED` |
| `approved_limits` | Limits no broader than the intent and deterministic policy |
| `timestamp` / `expires_at` | UTC, current at submission |
| `evidence_ref_ids` | Nonempty content-bound approval evidence |
| `authorization_sha256` | Hash of the complete authorization record |

### `ExecutionRequest` and `ExecutionOutcome`

An `ExecutionRequest` is created inside the execution domain from one current
approved authorization. It binds the authorization hash, exact security
mapping version, venue/account identity, deterministic-limit-policy version,
idempotency key, and request hash. An `ExecutionOutcome` records request hash,
external acknowledgement identifiers, typed state transitions, quantities and
prices with units/currencies, venue timestamps, ingestion timestamps, source
evidence, correction/supersession links, and outcome hash.

No free-form text controls routing, credentials, limits, account selection,
approval, kill-switch state, or submission.

## Invariants and fail-closed behavior

1. Research and execution are separate trust domains: separate process/service,
   credentials, mutable data authority, and network authorization.
2. No untrusted document, retrieved text, model output, claim, memory draft, or
   research artifact can invoke execution or obtain execution secrets.
3. Every submitted request binds exactly one unexpired intent, one current human
   authorization, one deterministic policy version, and one idempotency key.
4. Deterministic limits can narrow or reject an approved intent; no model,
   narrative, or operator bypass can broaden it.
5. Missing identity mappings, stale prices or reference data, ambiguous units,
   hash mismatches, unavailable approval evidence, failed reconciliation, or an
   unhealthy dependency blocks submission.
6. Kill-switch state defaults to `BLOCKED` on startup, loss of authoritative
   state, reconciliation breach, or control-plane uncertainty. Re-enabling
   requires a fresh typed human approval and evidence of resolved cause.
7. Duplicate idempotency keys cannot create duplicate external actions.
8. Reconciliation is append-only and preserves conflicting observations;
   corrections supersede records and never silently overwrite them.
9. A research-side record of `approved`, a clean Sol review, or this contract's
   approval is never execution authorization.
10. An approved security exception is explicit, time-bounded, narrow, and
    auditable; no exception may collapse the trust domains or bypass approval,
    deterministic limits, kill switch, or reconciliation.

## Evidence and typed human-approval gates

The following are distinct obligations. One record cannot satisfy two gates.
Sol review can satisfy only `DELEGATED_ARTIFACT_APPROVAL`; it cannot supply any
human authority below.

| Gate | Approval type | Required authority | Minimum evidence | Fail-closed result |
|---|---|---|---|---|
| S04 artifact review | `DELEGATED_ARTIFACT_APPROVAL` | Fresh Sol xhigh reviewer under delegated goal authority | Clean persisted review, reviewed source hashes, round, timestamp | Spec remains draft |
| Deferred activation | `GOAL_OR_PROCESS_AUTHORIZATION` | Competent human process/product authority issuing `ACTIVATE_DEFERRED` for E-09 | Current predicate proof, E-08 dependency proof, canonical resolution and content digest | E-09 remains dormant |
| Execution trust-domain design | `EXECUTION_TRUST_DOMAIN_APPROVAL` | Competent human accountable for the execution boundary | Reviewed threat model, architecture, control inventory, test evidence | No implementation/deployment approval |
| Current regulatory posture | `REGULATORY_REVIEW` | Competent current regulatory authority for intended mode | Jurisdiction, use mode, obligations, disclosures, timestamped evidence | No execution-connected use |
| Current legal posture | `LEGAL_REVIEW` | Competent current legal authority for intended mode | Scope-specific written review with limits and expiry/review date | No execution-connected use |
| Credential access | `CREDENTIAL_ACCESS_APPROVAL` | Credential/account owner | Named principals, exact scopes, expiry, rotation/revocation evidence | No credential issuance or use |
| External venue/service | `EXTERNAL_SERVICE_APPROVAL` | Competent service/account authority | Exact provider, account, terms, limits, environment, evidence | No external connection |
| Production enablement | `PRODUCTION_APPROVAL` | Competent production owner | Current test, reconciliation, rollback/kill-switch, observability evidence | Non-production only |
| Each executable request | `EXECUTION_TRUST_DOMAIN_APPROVAL` | Competent human execution approver | Exact intent hash, limits, account, expiry, immutable authorization | Request rejected |
| Any security deviation | `SECURITY_EXCEPTION` | Competent security authority | Narrow scope, rationale, compensating controls, owner, expiry | Deviation prohibited |

Purchase or external coordination needs separate `PURCHASE_AUTHORIZATION` or
`EXTERNAL_COORDINATION_APPROVAL` when applicable. They are never inferred from
another gate.

## Acceptance tests and verification

S04 is acceptable as a specification only after a fresh Sol xhigh review finds
its source ownership, dormant guard, interfaces, evidence inventory, and
approval inventory complete and clean. E-09 acceptance additionally requires
implementation evidence for all register acceptance clauses.

Required executable tests after activation include:

1. prove the research runtime cannot read execution credentials, mutate the
   execution database, or reach submission endpoints;
2. submit document text and model output containing execution instructions and
   prove no action or secret access occurs;
3. reject missing, expired, revoked, mismatched, or wrong-scope authorization;
4. reject unknown schema/enum values, ambiguous units, stale mappings, and hash
   mismatches;
5. prove deterministic limits reject over-limit and malformed requests even
   when the intent is human-approved;
6. replay one idempotency key and prove at-most-once external submission;
7. activate the kill switch before, during, and after submission and verify the
   defined safe state;
8. inject lost, duplicate, reordered, conflicting, and corrected external
   outcomes and prove reconciliation is complete and append-only;
9. prove restart defaults to blocked until authoritative state and current
   approvals are reconstructed; and
10. demonstrate that every request, authorization, external acknowledgement,
    outcome, correction, and reconciliation result is hash-bound and auditable.

Verification results must identify exact commands, immutable output evidence,
exit codes, source/artifact hashes, and execution time. Agent reports and
ledger-authored labels are not proof.

## Dependencies

- **E-08 / S01:** the paid/public/personalized/execution-connected boundary and
  current legal/regulatory gate must be accepted before E-09 activation.
- **S17:** security identity and versioned external identifier mappings are
  consumed but not owned here.
- **S11:** immutable run/artifact identities and hashes are consumed but not
  owned here.
- **S25:** historical/quant validation does not imply execution authority.

There is no amendment gate assigned to S04. Any change to its pinned ownership,
source semantics, dormant classification, or authority requirements requires
formal authority reconciliation and fresh review; it cannot be treated as an
ordinary editorial amendment.
