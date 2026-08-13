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

The request contains `request_id`, `tool_key` (`OPENBB`, `FINANCEHARNESS`, or `VIBE_TRADING`), `register_id`, `proposed_use`, `required_capabilities`, `boundary_version`, `request_evidence_refs`, `requested_by`, `requested_at`, and `status` (`DRAFT`, `PROPOSED`, `WITHDRAWN`, or `RESOLVED`). `requested_by` is descriptive only; activation authority comes exclusively from the canonical human resolution.

### 5.2 Activation predicates

- `AP-E06-OPENBB-EVALUATION` evaluates `TRUE` only when a current content-hash-valid request has `tool_key=OPENBB`, `register_id=E-06`, `status=PROPOSED`, a nonempty exact proposed use, and the referenced A-05/S02 boundary-and-rights scope exists. Missing or stale evidence evaluates `UNKNOWN`.
- `AP-E07-REUSE-EVALUATION` evaluates `TRUE` only when a current content-hash-valid request has `tool_key` equal to `FINANCEHARNESS` or `VIBE_TRADING`, `register_id=E-07`, `status=PROPOSED`, and a nonempty exact proposed use. Missing or stale evidence evaluates `UNKNOWN`.

A true predicate never supplies activation authority. Each row additionally requires its own active canonical `ACTIVATE_DEFERRED` human resolution bound to the row, exact scope, predicate ID, predicate digest, and evidence.

### 5.3 `ExternalToolDueDiligenceRecord`

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

### 5.4 OpenBB isolation contract

If E-06 is later activated and adoption is separately approved, OpenBB must run out of process behind an Equity-OS-owned adapter. Core domain objects must not expose OpenBB-specific types. Requests and responses are schema-validated; timeouts, budgets, retries, provider errors, and unavailable data are explicit. Provider access still passes S02 rights gates. Failure or removal of OpenBB must leave an approved replacement or a clean disabled capability, not corrupt canonical data.

## 6. Invariants and fail-closed behavior

1. Both owned rows remain dormant while their register Status is `Deferred`.
2. A tool name, nearby plan, dependency declaration, or delegated spec approval cannot activate a row.
3. Each row requires its own current true predicate and distinct canonical `ACTIVATE_DEFERRED` human resolution.
4. Evaluation completion is not adoption. `ELIGIBLE_FOR_SEPARATE_ADOPTION_DECISION` performs no install or integration.
5. Unknown repository identity, ambiguous fork, absent primary license evidence, unpinned version, untested critical behavior, unresolved provider assumption, or missing replacement path fails the evaluation.
6. OpenBB, if ever used, is out of process and behind Equity-OS contracts; in-process coupling is rejected.
7. External-tool outputs never become authoritative facts merely because a tool produced them.
8. Provider/data rights are consumed from S02 and cannot be inferred from an external tool's technical ability.
9. Unsupported infrastructure assumptions remain explicitly `UNCONFIRMED` and cannot justify adoption.
10. No credentials, purchase, service enrollment, cloning, network access, or external coordination occurs without separate competent-human authorization.
11. Changed repository, license, pinned version, proposed use, provider assumption, or security posture invalidates prior review and adoption evidence.
12. Delegated artifact approval is not product, provider, rights, legal, security-exception, external-service, purchase, credential, or adoption authority.

## 7. Evidence and typed human-approval gates

| Gate | Required evidence | Required typed authority | Fail-closed result |
|---|---|---|---|
| Deferred-row activation | Current true predicate evidence for the exact row and scope | `PRODUCT_OWNER_DECISION` expressed through a canonical `ACTIVATE_DEFERRED` resolution | Row remains dormant. |
| Repository and version identity | Primary repository evidence and immutable pin | No human approval substitutes for missing proof | Evaluation unresolved. |
| License and data rights | Primary license/terms plus S02 provider/right records for proposed use | `LEGAL_REVIEW` and applicable `DATA_RIGHTS_APPROVAL`/`PROVIDER_AUTHORIZATION` | Evaluation rejected or blocked. |
| Security boundary | Threat/trust-boundary evidence, permissions, dependency posture, and resolved findings | Applicable `EXTERNAL_SERVICE_APPROVAL`; any exception requires distinct `SECURITY_EXCEPTION` | Evaluation/adoption blocked. |
| Credentials, purchase, or coordination | Exact need, scope, and external evidence | Distinct `CREDENTIAL_ACCESS_APPROVAL`, `PURCHASE_AUTHORIZATION`, or `EXTERNAL_COORDINATION_APPROVAL` as applicable | Action prohibited. |
| Adoption | Complete current due-diligence record, clean review, no load-bearing blocker, and exact proposed-use decision | Separate `PRODUCT_OWNER_DECISION`; OpenBB also requires approval of the out-of-process contract and replacement path | No adoption or implementation. |
| Delegated spec approval | Persisted clean fresh-context Sol xhigh review bound to this file and source hashes | `DELEGATED_ARTIFACT_APPROVAL` only | Spec remains draft; no activation or adoption gate is affected. |

One approval satisfies at most one typed requirement. All non-delegated authority must come from canonical human resolutions with actor, competence basis, exact scope, timestamp, evidence, and decision. This draft contains no satisfied approval, activation, or adoption record.

## 8. Acceptance tests and verification

1. Dormancy fixture: no request or false/unknown predicate permits evaluation work to be treated as active.
2. Authority fixture: a true predicate without its row-specific canonical activation resolution cannot transition E-06 or E-07.
3. Row-isolation fixture: activating E-06 does not activate E-07, and vice versa.
4. Repository fixture: ambiguous repository identity or moving-only version reference fails.
5. License fixture: missing primary license evidence or unresolved obligation blocks eligibility.
6. Provider fixture: a technically available provider without an approved S02 rights record cannot be used.
7. OpenBB boundary fixture: an in-process design or leaked tool-specific core type fails.
8. Replacement fixture: removal/failure with neither an approved replacement nor clean disable path fails.
9. Adoption-separation fixture: completed due diligence cannot produce installation, integration, or `ADOPTED` without separate product-owner authority.
10. Infrastructure fixture: references to Temporal, Partner, Bodha, homelab, or PostgreSQL remain unconfirmed unless separately evidenced; unconfirmed fields cannot support a decision.
11. Change fixture: repository, license, pin, proposed-use, provider, or security change stales all dependent review evidence.
12. Approval fixture: delegated artifact approval cannot satisfy any activation, legal, rights, security, provider, credential, purchase, service, or adoption gate.

Verification evidence must include schema-test output, all fail-closed fixture output, exact repository/license/version evidence hashes when evaluation is activated, and applicable typed human records. A fresh Sol xhigh reviewer must verify exact E-06/E-07 and disposition 6.7 coverage before delegated artifact approval can be recorded.

## 9. Dependencies, Deferred activation guard, and amendment gate

- E-06 depends on A-05/S02; even an activated evaluation cannot bypass that dependency.
- E-07 has no register dependency, but all applicable provider/data-rights operations still consume S02 decisions.
- S03 has no product implementation dependency because both rows are dormant.

No S03 implementation Bead, roadmap item, plan, installation, integration, or operational change may proceed while the applicable register row remains `Deferred`. At terminal dormant evaluation, each predicate must recompute current `FALSE`; `UNKNOWN` does not pass. If activated, the predicate must recompute current `TRUE`, the canonical activation resolution must remain current, and the register transition must be legal before planning begins.

S03 has **no mandatory evidence-derived provisional amendment gate** in the goal's four-row amendment table. Any later activation, tool-scope change, repository/license/version change, provider-assumption change, security finding, or proposed adoption requires a superseding contract/evaluation record, fresh Sol xhigh review, and fresh applicable human decisions. Dormant gate approval never becomes implementation approval by amendment or implication.
