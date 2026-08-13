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
- a content-bound proposed-use source inventory derived independently of proposer-supplied rights references;
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
| `proposed_use`, `required_capabilities` | Nonempty exact scope; no generic evaluation authorization. `required_capabilities` must exactly equal the independently derived authoritative capability inventory below. |
| `required_capability_inventory_ref` | Required `{inventory_id, inventory_version, content_sha256}` naming the current independently derived `RequiredCapabilityInventory`. |
| `boundary_ref` | For E-06, required `{boundary_id, boundary_version, boundary_content_sha256}` matching the current S01 boundary referenced by S02. For E-07, required only when the proposed use reaches a boundary-scoped source. |
| `provider_rights_register_ref` | For E-06, required `{register_id, version, content_sha256}` naming the exact current S02 `ProviderRightsRegister`; otherwise nullable only when A-05 is not applicable to E-07's exact proposed use. |
| `proposed_use_source_inventory_ref` | Required `{inventory_id, inventory_version, content_sha256}` naming the current independently derived inventory below. |
| `source_rights_record_refs` | Exact sorted array of `{rights_record_id, source_id, content_sha256}` for the inventory's source set. Each reference must occur in the bound S02 register; the array is empty only when the current inventory proves that the exact proposed use requires no source/provider operation. |
| `a05_prerequisite_proof_ref` | Required for E-06: `{evidence_ref_id, content_sha256}` naming the current proof below. Null for E-07. |
| `request_evidence_refs` | Current content-addressed evidence for the proposal. |
| `requested_by`, `requested_at` | Descriptive requester and UTC time. `requested_by` supplies no authority. |
| `status` | `DRAFT`, `PROPOSED`, `WITHDRAWN`, or `RESOLVED`. |
| `proposed_use_sha256` | Derived digest binding the exact proposed-use projection below. |
| `request_sha256` | Lowercase SHA-256 of the exact preimage below. |

Canonical JSON is UTF-8 JSON with sorted keys, no insignificant whitespace, Unicode emitted directly, JSON booleans/null, and arrays retained in declared order. `request_sha256` is SHA-256 of the closed request with only `request_sha256` omitted. `proposed_use_sha256` is SHA-256 of canonical JSON for exactly `{tool_key, register_id, proposed_use, required_capabilities, required_capability_inventory_ref, boundary_ref, provider_rights_register_ref, proposed_use_source_inventory_ref, source_rights_record_refs}`. Unknown fields fail validation.

### 5.2 `RequiredCapabilityInventory`

The closed inventory contains `inventory_id`, `version`, `tool_key`,
`register_id`, `proposed_use`, `capability_declaration_refs`,
`required_capabilities`, `effective_at`, `supersedes`, and `content_sha256`.
It is generated from the current Equity-OS-owned interface contracts,
accepted workflow manifests, configuration schemas, and proposed data-flow
entry/exit contracts that define what the exact proposed use must accomplish.
It does not read the request's `required_capabilities`, capability-to-source
mappings, source inventory, S02 register, or rights-record references.

Every declaration reference is content-addressed and every capability key is
unique and sorted. `content_sha256` hashes canonical JSON of the complete
closed inventory with only `content_sha256` omitted. The authoritative
capability set is `C = set(required_capabilities)`. The request is valid only
when its required-capability set equals `C` exactly; a missing, extra,
duplicate, ambiguous, stale, or unsupported declaration makes the request
unresolved.

### 5.3 `ProposedUseSourceInventory`

The closed inventory contains `inventory_id`, `version`, `tool_key`, `register_id`, `proposed_use`, `required_capability_inventory_ref`, `required_capabilities`, `boundary_ref`, `capability_source_map_refs`, `entries`, `effective_at`, `supersedes`, and `content_sha256`. Each `capability_source_map_ref` is `{map_id, map_version, content_sha256}` and resolves to a closed mapping containing `map_id`, `version`, one `capability_key`, content-addressed `use_surface_refs`, unique sorted `source_ids`, `derivation_evidence_refs`, `effective_at`, `supersedes`, and `content_sha256`; its digest is SHA-256 of canonical JSON for the mapping with only `content_sha256` omitted. There is exactly one current mapping for every member of `C` and no mapping for a key outside `C`. Each inventory entry contains one stable `source_id`, the exact `capability_keys` that reach it, and the mapping's content-addressed `use_surface_refs` for every adapter, interface, configuration, manifest, or proposed data-flow path that can cause the source/provider operation.

The inventory generator first resolves the current capability inventory and verifies exact equality among `C`, the request capability set, the source inventory capability set, and the mapping-key set. It then deterministically traverses those content-addressed mappings and all reachable use surfaces for the exact proposed scope. It does not read `source_rights_record_refs` or derive either capability or source membership from the S02 register or its rights records. Every authoritative capability and reachable source operation must be accounted for; a missing, extra, ambiguous, duplicate, or stale declaration or mapping makes the inventory unresolved. An empty source inventory is valid only when current mapping evidence proves that every member of nonempty `C` performs no source/provider operation. Entries are unique and sorted by `source_id`; the authoritative proposed-use source set is `P = set(entries[*].source_id)`.

The inventory's `tool_key`, `register_id`, `proposed_use`, `required_capability_inventory_ref`, `required_capabilities`, and `boundary_ref` must exactly equal the request fields. `content_sha256` is SHA-256 of canonical JSON for the closed inventory with only `content_sha256` omitted. The request is valid only when both inventories freshly recompute, all capability sets equal `C`, and `P == set(source_rights_record_refs[*].source_id)` with exactly one current rights-record reference per member. A nonempty `P` also requires a current `provider_rights_register_ref`; no supplied reference may substitute for independent derivation of `C` or `P`.

### 5.4 `A05PrerequisiteProof`

The E-06 proof is a component-local, content-addressed `EVIDENCE_JSON` object containing `proof_id`, `register_id` (exactly `A-05`), `a05_authority_ref`, `boundary_ref`, `provider_rights_register_ref`, `proposed_use_source_inventory_ref`, `source_rights_record_refs`, `proposed_use_sha256`, `dependency_satisfied`, `evaluated_at`, `valid_until`, and `content_sha256`. `a05_authority_ref` is exactly `{source_path, register_id, row_projection_sha256}`, where `source_path` is `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md`, `register_id` is `A-05`, and `row_projection_sha256` hashes canonical JSON for the live row projection `{register_id, blueprint_phase, priority, decision_or_action, required_evidence_or_acceptance, dependencies, source_status}`. The projected values must exactly match the authoritative A-05 row and `source_status` must be `Accepted`. `content_sha256` is SHA-256 of canonical JSON for the closed proof with only `content_sha256` omitted.

`dependency_satisfied` is derived, never trusted. It is `true` only when the live authoritative A-05 row projection freshly matches `a05_authority_ref` and is exactly `Accepted`; the proposed-use inventory and its independent mapping evidence freshly recompute; the S02 register digest freshly recomputes; that register is bound to the same current accepted S01 boundary; every referenced rights-record ID/source/digest freshly recomputes and is current in that register; `P` from the inventory is exactly the rights-record reference set; every applicable right permits that use; and `proposed_use_sha256` recomputes from the request. A known unmet condition produces `false`. Missing, expired, ambiguous, or digest-stale inputs make the proof unresolved.

The proof deliberately binds the A-05 row projection rather than the whole mutable register file. A legal E-06-only Status transition therefore does not stale this prerequisite proof; any A-05 row mutation does. This component-local binding does not replace the goal's separate whole-file `STATUS_SOURCE_RECONCILIATION` and refreshed-review requirements after a legal register Status transition.

### 5.5 Activation predicates

- `AP-E06-OPENBB-EVALUATION` evaluates `TRUE` only when a current request freshly matches `request_sha256`, has `tool_key=OPENBB`, `register_id=E-06`, `status=PROPOSED`, and a nonempty exact proposed use; its boundary, proposed-use source inventory, S02 register, rights-record, and prerequisite-proof IDs and digests all freshly recompute; the independently derived inventory set exactly equals the rights-record reference set; and the proof's `dependency_satisfied` is current `true`. A current proof showing A-05 is not `Accepted`, an incomplete mapping, or unsatisfied exact rights scope evaluates `FALSE`; missing, expired, ambiguous, or digest-stale request, inventory, mapping, or proof evidence evaluates `UNKNOWN`.
- `AP-E07-REUSE-EVALUATION` evaluates `TRUE` only when a current content-hash-valid request has `tool_key` equal to `FINANCEHARNESS` or `VIBE_TRADING`, `register_id=E-07`, `status=PROPOSED`, and a nonempty exact proposed use; its independently derived inventory and mapping evidence freshly recompute; and, when `P` is nonempty, its current S02 register and exact-equality rights-record references validate. Missing, ambiguous, or stale request, inventory, mapping, or applicable rights evidence evaluates `UNKNOWN`.

A true predicate never supplies activation authority. Each row additionally requires its own active canonical `ACTIVATE_DEFERRED` human resolution bound to the row, exact request ID/digest and proposed-use digest, exact scope, predicate ID/digest, and predicate evidence. The `activation_record` and its `PRODUCT_OWNER_DECISION` approval record must both carry the same canonical resolution decision ID and content digest; copied scope or authority strings never pass.

### 5.6 `ExternalToolDueDiligenceRecord`

| Field | Contract |
|---|---|
| `evaluation_id`, `evaluation_version`, `tool_key`, `register_id` | Stable identity, positive immutable version, and exact owned row. |
| `request_ref` | Exact `{request_id, request_sha256, proposed_use_sha256, required_capability_inventory_ref}` for the activated evaluation scope. |
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
| `evidence_refs`, `approval_bindings` | Current content-bound proof and one-to-one typed decisions, each bound to this exact evaluation identity/version/content digest. |
| `result` | `UNRESOLVED`, `REJECT`, or `ELIGIBLE_FOR_SEPARATE_ADOPTION_DECISION`. Due diligence never represents adoption. |
| `supersedes` | Prior immutable record when evidence or scope changes. |
| `content_sha256` | SHA-256 of canonical JSON for every closed field from `evaluation_id` through `supersedes`, excluding `approval_bindings` and `content_sha256`; collections retain declared order and unknown fields fail. |

Every body-field change requires a successor `evaluation_version` and new
digest. Review evidence and every legal, rights, security, provider, and
product requirement bind the exact evaluation ID, version, and digest. A stale
or digest-mismatched record cannot support eligibility or adoption.

### 5.7 `ExternalToolAdoptionDecision`

Adoption is a separate closed record containing `adoption_decision_id`,
`tool_key`, `register_id`, `evaluation_ref` (`evaluation_id`,
`evaluation_version`, `content_sha256`), `proposed_use_sha256`,
`decision` (`ADOPT` or `DO_NOT_ADOPT`), `rationale`, `effective_at`,
`supersedes`, `content_sha256`, and `approval_binding`. Its content digest
hashes every field except itself and `approval_binding`. `ADOPT` is effective
only when the referenced due-diligence result is currently
`ELIGIBLE_FOR_SEPARATE_ADOPTION_DECISION`, its digest freshly recomputes, no
load-bearing blocker remains, and a distinct current `PRODUCT_OWNER_DECISION`
binding names this exact adoption-decision digest and canonical human
resolution. Adoption never rewrites the due-diligence result.

### 5.8 OpenBB isolation contract

If E-06 is later activated and adoption is separately approved, OpenBB must run out of process behind an Equity-OS-owned adapter. Core domain objects must not expose OpenBB-specific types. Requests and responses are schema-validated; timeouts, budgets, retries, provider errors, and unavailable data are explicit. Provider access still passes S02 rights gates. Failure or removal of OpenBB must leave an approved replacement or a clean disabled capability, not corrupt canonical data.

## 6. Invariants and fail-closed behavior

1. Both owned rows remain dormant while their register Status is `Deferred`.
2. A tool name, nearby plan, dependency declaration, or delegated spec approval cannot activate a row.
3. Each row requires its own current true predicate and distinct canonical `ACTIVATE_DEFERRED` human resolution; its activation and approval records must bind that same active resolution by decision ID and digest.
4. Evaluation completion is not adoption. `ELIGIBLE_FOR_SEPARATE_ADOPTION_DECISION` performs no install or integration, and only a separate content-bound `ExternalToolAdoptionDecision` can represent adoption.
5. Unknown repository identity, ambiguous fork, absent primary license evidence, unpinned version, untested critical behavior, unresolved provider assumption, or missing replacement path fails the evaluation.
6. OpenBB, if ever used, is out of process and behind Equity-OS contracts; in-process coupling is rejected.
7. External-tool outputs never become authoritative facts merely because a tool produced them.
8. E-06 cannot activate unless the live A-05 row projection is exactly `Accepted` and the request's exact S01 boundary, proposed-use source inventory, S02 register, applicable rights-record IDs/digests, and prerequisite-proof digest are current and mutually consistent; the independently derived source set and rights-reference set must be exactly equal. Provider/data rights cannot be inferred from an external tool's technical ability.
9. Unsupported infrastructure assumptions remain explicitly `UNCONFIRMED` and cannot justify adoption.
10. No credentials, purchase, service enrollment, cloning, network access, or external coordination occurs without separate competent-human authorization.
11. Changed repository, license, pinned version, proposed use, authoritative capability inventory, capability-to-source mapping, proposed-use source inventory, S01 boundary, A-05 row projection, S02 register or rights record, provider assumption, or security posture requires a superseding evaluation version and invalidates every review, approval, eligibility, and adoption binding to the prior digest.
12. Delegated artifact approval is not product, provider, rights, legal, security-exception, external-service, purchase, credential, or adoption authority.

## 7. Evidence and typed human-approval gates

| Gate | Required evidence | Required typed authority | Fail-closed result |
|---|---|---|---|
| Deferred-row activation | Current true predicate evidence for the exact row, request ID/digest, proposed-use digest, source-inventory ID/digest, exact derived source set, and scope; E-06 additionally requires current `dependency_satisfied=true` proof bound to the live accepted A-05 row projection and exact S01/S02 IDs and digests | `PRODUCT_OWNER_DECISION` approval record and activation record both bound to the same active canonical `ACTIVATE_DEFERRED` resolution decision ID and digest | Row remains dormant. |
| Repository and version identity | Primary repository evidence and immutable pin | No human approval substitutes for missing proof | Evaluation unresolved. |
| License and data rights | Primary license/terms plus S02 provider/right records for proposed use | `LEGAL_REVIEW` and applicable `DATA_RIGHTS_APPROVAL`/`PROVIDER_AUTHORIZATION` | Evaluation rejected or blocked. |
| Security boundary | Threat/trust-boundary evidence, permissions, dependency posture, and resolved findings | Applicable `EXTERNAL_SERVICE_APPROVAL`; any exception requires distinct `SECURITY_EXCEPTION` | Evaluation/adoption blocked. |
| Credentials, purchase, or coordination | Exact need, scope, and external evidence | Distinct `CREDENTIAL_ACCESS_APPROVAL`, `PURCHASE_AUTHORIZATION`, or `EXTERNAL_COORDINATION_APPROVAL` as applicable | Action prohibited. |
| Adoption | Complete current due-diligence ID/version/content digest with eligible result, clean review, no load-bearing blocker, and exact content-bound adoption decision | Separate `PRODUCT_OWNER_DECISION` bound to the adoption-decision digest; OpenBB also requires distinct approval of the out-of-process contract and replacement path | No adoption or implementation. |
| Delegated spec approval | Persisted clean fresh-context Sol xhigh review bound to this file and source hashes | `DELEGATED_ARTIFACT_APPROVAL` only | Spec remains draft; no activation or adoption gate is affected. |

One approval satisfies at most one typed requirement. All non-delegated authority must come from canonical human resolutions with actor, competence basis, exact scope, timestamp, evidence, and decision. This draft contains no satisfied approval, activation, or adoption record.

## 8. Acceptance tests and verification

1. Dormancy fixture: no request or false/unknown predicate permits evaluation work to be treated as active.
2. E-06 prerequisite fixture: A-05 `Open`, `In progress`, `Deferred`, or `Rejected`; a changed A-05 row-projection digest; a missing/wrong S01 or S02 ID; a stale inventory, mapping, register, or rights-record digest; a nonexact source-record set; an unapproved applicable right; or a mismatched proposed-use digest prevents E-06 activation (`FALSE` when current and known, otherwise `UNKNOWN`).
3. Authority-binding fixture: a true predicate without its row-specific canonical activation resolution, or with a mismatched request/scope/predicate/resolution ID or digest between the activation and approval records, cannot transition E-06 or E-07.
4. Proposed-use inventory fixture: independently derive `C` and `P`; omitting or adding a request capability, declaration, or mapping, changing a capability-inventory digest, using duplicate/mismatched map keys, omitting/adding a source, leaving a reachable path unaccounted, deriving membership from supplied rights references, using a stale mapping, or claiming an empty source set without per-capability no-source proof prevents activation.
5. Authority-transition fixture: the legal E-06 `Deferred` to `Open`/`In progress` Status mutation leaves an otherwise current A-05 row-projection proof valid, while any A-05 projection mutation stales it and prevents activation; separate goal-level whole-file reconciliation remains mandatory before work resumes.
6. Row-isolation fixture: activating E-06 does not activate E-07, and vice versa.
7. Repository fixture: ambiguous repository identity or moving-only version reference fails.
8. License fixture: missing primary license evidence or unresolved obligation blocks eligibility.
9. Provider fixture: a technically available provider without the exact current approved S02 rights record cannot be used.
10. OpenBB boundary fixture: an in-process design or leaked tool-specific core type fails.
11. Replacement fixture: removal/failure with neither an approved replacement nor clean disable path fails.
12. Adoption-separation fixture: completed due diligence cannot produce installation or integration; an `ADOPT` record with a stale/mismatched evaluation digest, changed evaluation bytes under the same identity, a non-eligible result, or absent/wrong-scope/reused product-owner binding remains ineffective.
13. Infrastructure fixture: references to Temporal, Partner, Bodha, homelab, or PostgreSQL remain unconfirmed unless separately evidenced; unconfirmed fields cannot support a decision.
14. Change fixture: repository, license, pin, proposed use, capability inventory, mapping/source inventory, S01 boundary, A-05 row projection, S02 register/right record, provider, or security change requires a successor evaluation version and stales all dependent request, predicate, activation, review, approval, and adoption evidence.
15. Approval fixture: delegated artifact approval cannot satisfy any activation, legal, rights, security, provider, credential, purchase, service, or adoption gate.

Verification evidence must include schema-test output, all fail-closed fixture output, exact repository/license/version evidence hashes when evaluation is activated, and applicable typed human records. A fresh Sol xhigh reviewer must verify exact E-06/E-07 and disposition 6.7 coverage before delegated artifact approval can be recorded.

## 9. Dependencies, Deferred activation guard, and amendment gate

- E-06 depends on A-05/S02; even an activated evaluation cannot bypass that dependency.
- E-07 has no register dependency, but all applicable provider/data-rights operations still consume S02 decisions.
- S03 has no product implementation dependency because both rows are dormant.

No S03 implementation Bead, roadmap item, plan, installation, integration, or operational change may proceed while the applicable register row remains `Deferred`. At terminal dormant evaluation, each predicate must recompute current `FALSE`; `UNKNOWN` does not pass.

E-06 activation sequencing is closed: (1) independently derive and persist the current content-hashed proposed-use source inventory; (2) persist the immutable content-hashed request, exact proposed-use digest, and exact-equality rights-reference set; (3) establish live A-05 `Accepted` and persist the current content-hashed prerequisite proof bound to the A-05 row projection and exact S01/S02 references; (4) recompute `AP-E06-OPENBB-EVALUATION=TRUE`; (5) obtain the active canonical `ACTIVATE_DEFERRED` human resolution for that exact bound scope; (6) perform one validated transition that atomically persists the matching activation and `PRODUCT_OWNER_DECISION` approval records carrying the same resolution ID/digest and moves E-06 from `Deferred` to `Open` or `In progress`; and (7) complete the goal's separate whole-file Status-source reconciliation and refreshed content-bound reviews before evaluation planning begins. The E-06-only Status mutation does not stale the A-05 row-projection proof. Reordering, omission, relevant digest staleness, resolution revocation/supersession, or a current predicate other than `TRUE` blocks or re-blocks the dependent work.

S03 has **no mandatory evidence-derived provisional amendment gate** in the goal's four-row amendment table. Any later activation, tool-scope change, capability-to-source mapping or proposed-use inventory change, A-05/S01/S02 dependency change, repository/license/version change, provider-assumption change, security finding, or proposed adoption requires a superseding contract/evaluation record, fresh Sol xhigh review, and fresh applicable human decisions. Dormant gate approval never becomes implementation approval by amendment or implication.
