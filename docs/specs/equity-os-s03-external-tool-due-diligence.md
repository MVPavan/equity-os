# S03 — Optional external-tool dependency due diligence

**Status: DRAFT — AWAITING FRESH SOL XHIGH REVIEW**

## 1. Contract identity

This specification owns S03 and only register items E-06 and E-07. It defines dormant evaluation gates for OpenBB, FinanceHarness, and Vibe-Trading. It does not activate, adopt, install, integrate, purchase, contact, or operate any external tool.

## 2. Authority and ownership

The decision register is operationally authoritative: **“The wording in this register is authoritative for implementation gates. Narrative reviews explain rationale but do not override this register.”**

| Source | Exact source text | Contract effect |
|---|---|---|
| Exact 25-spec table, S03 | `S03 | Optional external-tool dependency due diligence | docs/specs/equity-os-s03-external-tool-due-diligence.md | E-06, E-07 | 6.7` | This file is the sole primary spec owner for E-06 and E-07. |
| Register E-06 | `Medium | Evaluate OpenBB deployment | If used, it remains out of process and behind Funda contracts; license and replacement path approved | A-05 | Deferred` | Dormant conditional evaluation; any later use remains out of process and behind Equity-OS contracts. |
| Register E-07 | `Medium | Verify FinanceHarness and Vibe-Trading before reuse | Exact repositories, licenses, test quality, provider assumptions, and pinned versions recorded | — | Deferred` | Dormant conditional evaluation; names alone are not verified dependencies. |
| Disposition 6.7 | `Infrastructure assumptions are unsupported by the reviewed files` `The report's references to Temporal, Partner, Bodha, an existing homelab, or an existing PostgreSQL deployment may come from context outside the two documents. They should remain outside the architecture record until explicitly confirmed. The underlying general recommendation—do not build a bespoke workflow engine and migrate storage only when earned—remains sound.` | No unsupported infrastructure assumption may enter the architecture or a tool evaluation. |

### Activation classification

S03 is **dormant-only** at the pinned draft snapshot: E-06 and E-07 are both `Deferred`. This draft approves only the gates and dormant behavior. It does not approve evaluation work beyond structural readiness, implementation, or adoption.

## 3. Scope

S03 defines:

- a typed request that can propose evaluation of one named external tool;
- a typed, content-bound proof that E-06's exact A-05/S02 prerequisite is accepted and current;
- a mechanically testable activation predicate for each Deferred register row;
- a common `ExternalToolDueDiligenceRecord`;
- OpenBB-specific out-of-process and contract-boundary requirements;
- FinanceHarness and Vibe-Trading repository, license, test-quality, provider-assumption, and pinned-version verification requirements; and
- an adoption decision that is strictly separate from due-diligence completion.

## 4. Non-goals

- No repository lookup, web research, cloning, installation, execution, network access, or provider contact in this draft.
- No assertion that a named repository, license, maintainer, release, or integration exists.
- No adoption or implementation of OpenBB, FinanceHarness, or Vibe-Trading.
- No in-process OpenBB deployment.
- No source/provider rights decision duplicated from S02/A-05.
- No inference that Temporal, Partner, Bodha, a homelab, PostgreSQL, or any other infrastructure is available or selected.
- No bespoke workflow-engine commitment or premature storage migration.
- No delegated approval claimed by this authoring session.

## 5. Interfaces and data contracts

### 5.1 `ExternalToolEvaluationRequest`

The closed request contains:

| Field | Contract |
|---|---|
| `request_id` | Stable immutable request identity. |
| `tool_key`, `register_id` | `OPENBB`/`E-06`, or `FINANCEHARNESS` or `VIBE_TRADING`/`E-07`; cross-row combinations fail. |
| `proposed_use`, `required_capabilities` | Nonempty exact scope; no generic evaluation authorization. |
| `boundary_ref` | For E-06, required `{boundary_id, boundary_version, boundary_content_sha256}` matching the current S01 boundary referenced by S02. For E-07, required only when the proposed use reaches a boundary-scoped source. |
| `provider_rights_register_ref` | For E-06, required `{register_id, version, content_sha256}` naming the exact current S02 `ProviderRightsRegister`; otherwise nullable only when A-05 is not applicable to E-07's exact proposed use. |
| `source_rights_record_refs` | Exact sorted array of `{rights_record_id, source_id, content_sha256}` required by the proposed use. Each reference must occur in the bound S02 register; the array is empty only when the exact proposed use requires no source/provider operation. |
| `a05_prerequisite_proof_ref` | Required for E-06: `{evidence_ref_id, content_sha256}` naming the current proof below. Null for E-07. |
| `request_evidence_refs` | Current content-addressed evidence for the proposal. |
| `requested_by`, `requested_at` | Descriptive requester and UTC time. `requested_by` supplies no authority. |
| `status` | `DRAFT`, `PROPOSED`, `WITHDRAWN`, or `RESOLVED`. |
| `proposed_use_sha256` | Derived digest binding the exact proposed-use projection below. |
| `request_sha256` | Lowercase SHA-256 of the exact preimage below. |

Canonical JSON is UTF-8 JSON with sorted keys, no insignificant whitespace, Unicode emitted directly, JSON booleans/null, and arrays retained in declared order. `request_sha256` is SHA-256 of the closed request with only `request_sha256` omitted. `proposed_use_sha256` is SHA-256 of canonical JSON for exactly `{tool_key, register_id, proposed_use, required_capabilities, boundary_ref, provider_rights_register_ref, source_rights_record_refs}`. Unknown fields fail validation.

### 5.2 `A05PrerequisiteProof`

The E-06 proof is a component-local, content-addressed `EVIDENCE_JSON` object containing `proof_id`, `register_id` (exactly `A-05`), `a05_source_status`, `register_authority_sha256`, `boundary_ref`, `provider_rights_register_ref`, `source_rights_record_refs`, `proposed_use_sha256`, `dependency_satisfied`, `evaluated_at`, `valid_until`, and `content_sha256`. `register_authority_sha256` is lowercase SHA-256 of the exact current v2 decision-register file bytes. `content_sha256` is SHA-256 of canonical JSON for the closed proof with only `content_sha256` omitted.

`dependency_satisfied` is derived, never trusted. It is `true` only when the live authoritative A-05 row is exactly `Accepted`; `register_authority_sha256` is current; the S02 register digest freshly recomputes; that register is bound to the same current accepted S01 boundary; every referenced rights-record ID/source/digest freshly recomputes and is current in that register; the record-reference set is exactly the set required by the proposed use; every applicable right permits that use; and `proposed_use_sha256` recomputes from the request. A known unmet condition produces `false`. Missing, expired, ambiguous, or digest-stale inputs make the proof unresolved.

### 5.3 Activation predicates

- `AP-E06-OPENBB-EVALUATION` evaluates `TRUE` only when a current request freshly matches `request_sha256`, has `tool_key=OPENBB`, `register_id=E-06`, `status=PROPOSED`, and a nonempty exact proposed use; its boundary, S02 register, rights-record, and prerequisite-proof IDs and digests all freshly recompute; and the proof's `dependency_satisfied` is current `true`. A current proof showing A-05 is not `Accepted` or the exact rights scope is unsatisfied evaluates `FALSE`; missing, expired, ambiguous, or digest-stale request or proof evidence evaluates `UNKNOWN`.
- `AP-E07-REUSE-EVALUATION` evaluates `TRUE` only when a current content-hash-valid request has `tool_key` equal to `FINANCEHARNESS` or `VIBE_TRADING`, `register_id=E-07`, `status=PROPOSED`, and a nonempty exact proposed use. Missing or stale evidence evaluates `UNKNOWN`.

A true predicate never supplies activation authority. Each row additionally requires its own active canonical `ACTIVATE_DEFERRED` human resolution bound to the row, exact request ID/digest and proposed-use digest, exact scope, predicate ID/digest, and predicate evidence. The `activation_record` and its `PRODUCT_OWNER_DECISION` approval record must both carry the same canonical resolution decision ID and content digest; copied scope or authority strings never pass.

### 5.4 `ExternalToolDueDiligenceRecord`

| Field | Contract |
|---|---|
| `evaluation_id`, `tool_key`, `register_id` | Stable identity and exact owned row. |
| `proposed_use`, `required_capabilities`, `non_goals` | Exact bounded evaluation scope. |
| `repository_identity` | Exact canonical repository URL/identifier and evidence; unresolved until proven. |
| `license` | Exact license/version, obligations, compatibility analysis, and primary evidence. |
| `pinned_version` | Immutable commit/release/content digest; mutable branches or tags alone fail. |
| `maintainer_and_activity_evidence` | Current provenance, maintenance, release, and support evidence where relevant. |
| `test_quality` | Test inventory, execution evidence, coverage limitations, and known failures; marketing claims do not pass. |
| `security_posture` | Trust boundaries, permissions, credentials, network/file access, dependencies, advisories, and unresolved risks. |
| `provider_assumptions` | Every provider, credential, data format, geography, account, limit, and rights dependency. |
| `data_flow` | Inputs, outputs, storage, telemetry, retention, derived data, and boundary crossings. |
| `contract_mapping` | Mapping to Equity-OS interfaces without leaking provider/tool types into core contracts. |
| `replacement_path` | Tested or evidence-backed exit/export/replacement path and migration limits. |
| `operational_burden` | Deployment, monitoring, upgrade, backup, failure, and maintenance costs. |
| `findings` | Severity, evidence, affected scope, disposition, and blocker state. |
| `evidence_refs`, `approval_record_ids` | Current content-bound proof and typed decisions. |
| `result` | `UNRESOLVED`, `REJECT`, `ELIGIBLE_FOR_SEPARATE_ADOPTION_DECISION`, or `ADOPTED`. Due diligence alone may reach only the third value. |
| `supersedes` | Prior immutable record when evidence or scope changes. |

### 5.5 OpenBB isolation contract

If E-06 is later activated and adoption is separately approved, OpenBB must run out of process behind an Equity-OS-owned adapter. Core domain objects must not expose OpenBB-specific types. Requests and responses are schema-validated; timeouts, budgets, retries, provider errors, and unavailable data are explicit. Provider access still passes S02 rights gates. Failure or removal of OpenBB must leave an approved replacement or a clean disabled capability, not corrupt canonical data.

## 6. Invariants and fail-closed behavior

1. Both owned rows remain dormant while their register Status is `Deferred`.
2. A tool name, nearby plan, dependency declaration, or delegated spec approval cannot activate a row.
3. Each row requires its own current true predicate and distinct canonical `ACTIVATE_DEFERRED` human resolution; its activation and approval records must bind that same active resolution by decision ID and digest.
4. Evaluation completion is not adoption. `ELIGIBLE_FOR_SEPARATE_ADOPTION_DECISION` performs no install or integration.
5. Unknown repository identity, ambiguous fork, absent primary license evidence, unpinned version, untested critical behavior, unresolved provider assumption, or missing replacement path fails the evaluation.
6. OpenBB, if ever used, is out of process and behind Equity-OS contracts; in-process coupling is rejected.
7. External-tool outputs never become authoritative facts merely because a tool produced them.
8. E-06 cannot activate unless the live A-05 row is exactly `Accepted` and the request's exact S01 boundary, S02 register, applicable rights-record IDs/digests, and prerequisite-proof digest are current and mutually consistent. Provider/data rights cannot be inferred from an external tool's technical ability.
9. Unsupported infrastructure assumptions remain explicitly `UNCONFIRMED` and cannot justify adoption.
10. No credentials, purchase, service enrollment, cloning, network access, or external coordination occurs without separate competent-human authorization.
11. Changed repository, license, pinned version, proposed use, S01 boundary, S02 register or rights record, provider assumption, or security posture invalidates the affected request, predicate, review, activation, and adoption evidence.
12. Delegated artifact approval is not product, provider, rights, legal, security-exception, external-service, purchase, credential, or adoption authority.

## 7. Evidence and typed human-approval gates

| Gate | Required evidence | Required typed authority | Fail-closed result |
|---|---|---|---|
| Deferred-row activation | Current true predicate evidence for the exact row, request ID/digest, proposed-use digest, and scope; E-06 additionally requires current `dependency_satisfied=true` proof bound to live A-05 `Accepted` and the exact S01/S02 IDs and digests | `PRODUCT_OWNER_DECISION` approval record and activation record both bound to the same active canonical `ACTIVATE_DEFERRED` resolution decision ID and digest | Row remains dormant. |
| Repository and version identity | Primary repository evidence and immutable pin | No human approval substitutes for missing proof | Evaluation unresolved. |
| License and data rights | Primary license/terms plus S02 provider/right records for proposed use | `LEGAL_REVIEW` and applicable `DATA_RIGHTS_APPROVAL`/`PROVIDER_AUTHORIZATION` | Evaluation rejected or blocked. |
| Security boundary | Threat/trust-boundary evidence, permissions, dependency posture, and resolved findings | Applicable `EXTERNAL_SERVICE_APPROVAL`; any exception requires distinct `SECURITY_EXCEPTION` | Evaluation/adoption blocked. |
| Credentials, purchase, or coordination | Exact need, scope, and external evidence | Distinct `CREDENTIAL_ACCESS_APPROVAL`, `PURCHASE_AUTHORIZATION`, or `EXTERNAL_COORDINATION_APPROVAL` as applicable | Action prohibited. |
| Adoption | Complete current due-diligence record, clean review, no load-bearing blocker, and exact proposed-use decision | Separate `PRODUCT_OWNER_DECISION`; OpenBB also requires approval of the out-of-process contract and replacement path | No adoption or implementation. |
| Delegated spec approval | Persisted clean fresh-context Sol xhigh review bound to this file and source hashes | `DELEGATED_ARTIFACT_APPROVAL` only | Spec remains draft; no activation or adoption gate is affected. |

One approval satisfies at most one typed requirement. All non-delegated authority must come from canonical human resolutions with actor, competence basis, exact scope, timestamp, evidence, and decision. This draft contains no satisfied approval, activation, or adoption record.

## 8. Acceptance tests and verification

1. Dormancy fixture: no request or false/unknown predicate permits evaluation work to be treated as active.
2. E-06 prerequisite fixture: A-05 `Open`, `In progress`, `Deferred`, or `Rejected`; a changed authority digest; a missing/wrong S01 or S02 ID; a stale register or rights-record digest; a nonexact source-record set; an unapproved applicable right; or a mismatched proposed-use digest prevents E-06 activation (`FALSE` when current and known, otherwise `UNKNOWN`).
3. Authority-binding fixture: a true predicate without its row-specific canonical activation resolution, or with a mismatched request/scope/predicate/resolution ID or digest between the activation and approval records, cannot transition E-06 or E-07.
4. Row-isolation fixture: activating E-06 does not activate E-07, and vice versa.
5. Repository fixture: ambiguous repository identity or moving-only version reference fails.
6. License fixture: missing primary license evidence or unresolved obligation blocks eligibility.
7. Provider fixture: a technically available provider without the exact current approved S02 rights record cannot be used.
8. OpenBB boundary fixture: an in-process design or leaked tool-specific core type fails.
9. Replacement fixture: removal/failure with neither an approved replacement nor clean disable path fails.
10. Adoption-separation fixture: completed due diligence cannot produce installation, integration, or `ADOPTED` without separate product-owner authority.
11. Infrastructure fixture: references to Temporal, Partner, Bodha, homelab, or PostgreSQL remain unconfirmed unless separately evidenced; unconfirmed fields cannot support a decision.
12. Change fixture: repository, license, pin, proposed use, S01 boundary, S02 register/right record, provider, or security change stales all dependent request, predicate, activation, and review evidence.
13. Approval fixture: delegated artifact approval cannot satisfy any activation, legal, rights, security, provider, credential, purchase, service, or adoption gate.

Verification evidence must include schema-test output, all fail-closed fixture output, exact repository/license/version evidence hashes when evaluation is activated, and applicable typed human records. A fresh Sol xhigh reviewer must verify exact E-06/E-07 and disposition 6.7 coverage before delegated artifact approval can be recorded.

## 9. Dependencies, Deferred activation guard, and amendment gate

- E-06 depends on A-05/S02; even an activated evaluation cannot bypass that dependency.
- E-07 has no register dependency, but all applicable provider/data-rights operations still consume S02 decisions.
- S03 has no product implementation dependency because both rows are dormant.

No S03 implementation Bead, roadmap item, plan, installation, integration, or operational change may proceed while the applicable register row remains `Deferred`. At terminal dormant evaluation, each predicate must recompute current `FALSE`; `UNKNOWN` does not pass.

E-06 activation sequencing is closed: (1) persist the immutable content-hashed request and exact proposed-use digest; (2) establish live A-05 `Accepted` and persist the current content-hashed prerequisite proof and S01/S02 references; (3) recompute `AP-E06-OPENBB-EVALUATION=TRUE`; (4) obtain the active canonical `ACTIVATE_DEFERRED` human resolution for that exact bound scope; (5) perform one validated transition that atomically persists the matching activation and `PRODUCT_OWNER_DECISION` approval records carrying the same resolution ID/digest and moves E-06 from `Deferred` to `Open` or `In progress`; only then may evaluation planning begin. Reordering, omission, later digest staleness, resolution revocation/supersession, or a current predicate other than `TRUE` blocks or re-blocks the dependent work.

S03 has **no mandatory evidence-derived provisional amendment gate** in the goal's four-row amendment table. Any later activation, tool-scope change, repository/license/version change, provider-assumption change, security finding, or proposed adoption requires a superseding contract/evaluation record, fresh Sol xhigh review, and fresh applicable human decisions. Dormant gate approval never becomes implementation approval by amendment or implication.
