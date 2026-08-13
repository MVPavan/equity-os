# S02 — Source rights, providers, and consensus-data policy

**Status: DRAFT — AWAITING FRESH SOL XHIGH REVIEW**

## 1. Contract identity

This specification owns S02 and only register items A-05 and C-13. It defines the source/provider data-rights register and the fail-closed decision contract for consensus estimates. It records required evidence and competent-human decisions; it does not grant provider rights, legal sufficiency, credentials, purchases, redistribution rights, or consensus-data access.

## 2. Authority and ownership

The decision register is operationally authoritative: **“The wording in this register is authoritative for implementation gates. Narrative reviews explain rationale but do not override this register.”**

| Source | Exact source text | Contract effect |
|---|---|---|
| Exact 25-spec table, S02 | `S02 | Source rights, providers, and consensus-data policy | docs/specs/equity-os-s02-source-rights-providers-consensus-policy.md | A-05, C-13 | T-4, R-3` | This file is the sole primary spec owner for A-05 and C-13. |
| Register A-05 | `Critical | Create provider and data-rights register scoped to the declared boundary | For every source: access method, automation, caching, retention, commercial use, derived outputs, redistribution, account limits, point-in-time availability, and replacement path | A-01 | Open` | Active obligation; every source must be evaluated against S01's declared boundary. |
| Register C-13 | `Medium | Decide treatment of consensus estimates | Licensed and necessary, or explicitly excluded from the MVP | A-05 | Open` | Active obligation; default is exclusion until both necessity and rights are proven. |
| Disposition T-4 | `Disposition: Partially accept.` `A-01 can define the intended product boundary without completing legal analysis. It should avoid claiming that the chosen boundary is legally sufficient. Current regulatory verification becomes mandatory before external, paid, personalized, or execution-connected use, not necessarily before documenting the initial private-use intent.` | Rights analysis is scoped to the intended boundary and cannot manufacture legal sufficiency. |
| Disposition R-3 | `Disposition: Accept.` `The intended use boundary determines which rights are required. A-05 should be scoped to the initial boundary while retaining fields for future commercial/public modes. This prevents an open-ended legal exercise from blocking the private research slice.` | The register carries current-mode decisions and explicit future-mode fields without treating future rights as current rights. |

### Activation classification

S02 is **active-only** at the pinned draft snapshot: A-05 and C-13 are both `Open`. It has no Deferred register component and no activation predicate.

## 3. Scope

S02 defines:

- one versioned `ProviderRightsRegister` containing one `SourceRightsRecord` per source;
- the lifecycle for proposed, reviewed, approved, restricted, denied, expired, and replaced source access;
- exact separation among access, automation, caching, retention, commercial use, derived outputs, redistribution, account limits, point-in-time availability, and replacement path;
- a versioned `ConsensusDataDecision` that either proves consensus data is licensed and necessary for the MVP or explicitly excludes it; and
- boundary-change invalidation rules so private/internal rights never silently carry into commercial, public, personalized, or execution-connected modes.

## 4. Non-goals

- No provider selection, purchase, contracting, credential access, or external coordination by an agent.
- No claim that terms, licenses, or intended use are legally sufficient.
- No ingestion implementation; S09 owns ingestion and capture behavior.
- No external-tool dependency evaluation; S03 owns E-06 and E-07.
- No paid/public/personalized distribution approval; S01 owns E-08.
- No provider terms inferred from marketing copy, prior knowledge, or missing evidence.
- No delegated approval claimed by this authoring session.

## 5. Interfaces and data contracts

### 5.1 `ProviderRightsRegister`

The register contains `register_id`, `boundary_id`, `boundary_version`, `version`, `effective_at`, `records`, `supersedes`, and `approval_record_ids`. It is invalid if its S01 boundary reference is absent, stale, or not content-hash bound.

### 5.2 `SourceRightsRecord`

| Field | Type / allowed values | Contract |
|---|---|---|
| `source_id`, `source_name` | stable string, display string | Unique identity and human-readable label. |
| `source_category` | controlled string | Official filing, exchange disclosure, issuer material, licensed vendor, transcript/audio, market data, consensus, or explicitly added reviewed category. |
| `evidence_as_of`, `evidence_refs` | UTC time, nonempty array when reviewed | Bind the exact current terms, contract, license, or primary-source evidence. |
| `access_method` | structured record | Manual, API, download, feed, or other reviewed method; unknown is explicit. |
| `automation` | rights decision | `UNKNOWN`, `PROHIBITED`, `RESTRICTED`, or `APPROVED`. |
| `caching` | rights decision plus conditions | Includes duration and storage constraints. |
| `retention` | rights decision plus duration/deletion duty | No indefinite default. |
| `commercial_use` | rights decision plus scope | Separate from access. |
| `derived_outputs` | rights decision plus definition | Names allowed derived artifacts. |
| `redistribution` | rights decision plus audience/channel | Separate from derived-output permission. |
| `account_limits` | structured limits | Seats, requests, volume, concurrency, geography, or unknown. |
| `point_in_time_availability` | structured finding | What can be known and retained at a historical cutoff. |
| `replacement_path` | structured plan | Approved alternative or explicit `NONE`; never a fabricated provider. |
| `intended_modes` | array | Each decision is scoped to exact S01 boundary modes. |
| `decision_state` | lifecycle enum | `PROPOSED`, `UNDER_REVIEW`, `APPROVED`, `RESTRICTED`, `DENIED`, `EXPIRED`, or `REPLACED`. |
| `approval_record_ids` | array | Separate typed records for applicable rights and provider authority. |
| `supersedes` | nullable record ID | Preserves immutable history. |

Every rights dimension is independent. An `APPROVED` record with an `UNKNOWN` dimension does not authorize that dimension.

### 5.3 `ConsensusDataDecision`

The decision contains `decision_id`, `mvp_scope`, `necessity` (`NECESSARY` or `NOT_NECESSARY`), `necessity_rationale`, `provider_source_ids`, `license_evidence_refs`, `permitted_uses`, `excluded_uses`, `approval_record_ids`, `effective_at`, and `supersedes`.

Only two terminal outcomes are valid:

1. `INCLUDED_LICENSED_AND_NECESSARY`: necessity is `NECESSARY`, every provider record is current and approved for every actual mode and operation, and typed approvals are satisfied.
2. `EXCLUDED_FROM_MVP`: necessity is `NOT_NECESSARY`, the product contract and dependent interfaces explicitly reject consensus inputs, and a competent product-owner decision is recorded.

Anything else is `UNRESOLVED` and behaves as excluded.

## 6. Invariants and fail-closed behavior

1. A-05 cannot pass before S01/A-01 supplies the exact declared boundary.
2. Every source used by the product has exactly one current rights record; duplicates, gaps, or stale boundary references fail.
3. Missing or ambiguous rights resolve to `UNKNOWN`, which denies the operation.
4. Permission to access does not imply automation, caching, retention, commercial use, derived-output, or redistribution permission.
5. Private/internal permission does not imply public, paid, personalized, or execution-connected permission.
6. Terms, contracts, and approvals are time-bound where their source is time-bound; expiry blocks use.
7. Account or volume limits are enforced upstream of access; exceeding a limit fails closed and records the failure.
8. No credentials, purchase, provider contact, or external-service enrollment occurs without its distinct competent-human authorization.
9. Consensus data is excluded unless the exact terminal outcome `INCLUDED_LICENSED_AND_NECESSARY` is proven.
10. Replacement paths are evaluated independently; failure of a primary source does not authorize an unreviewed substitute.
11. Delegated artifact approval proves only that the specification passed review; it grants no provider, rights, legal, purchase, credential, or external-service authority.
12. Records are append-only by version; corrections supersede and never silently overwrite.

## 7. Evidence and typed human-approval gates

| Gate | Required evidence | Required typed authority | Fail-closed result |
|---|---|---|---|
| Register completeness | One current `SourceRightsRecord` for every used source, bound to current S01 boundary and exact evidence | `DATA_RIGHTS_APPROVAL` for each source/scope; `LEGAL_REVIEW` when legal interpretation is required | Source operation prohibited. |
| Provider access | Current primary provider terms/contract and exact access scope | `PROVIDER_AUTHORIZATION`; additionally `PURCHASE_AUTHORIZATION`, `CREDENTIAL_ACCESS_APPROVAL`, `EXTERNAL_SERVICE_APPROVAL`, or `EXTERNAL_COORDINATION_APPROVAL` when applicable | No access or enrollment. |
| Operational mode | Evidence for each requested automation/caching/retention/derived-output/redistribution operation | Separate applicable `DATA_RIGHTS_APPROVAL` records | Unknown or unapproved operation denied. |
| Consensus inclusion | Necessity analysis plus current provider/license evidence covering actual inputs, retention, calculations, output, and distribution mode | `PRODUCT_OWNER_DECISION`, `DATA_RIGHTS_APPROVAL`, and applicable `PROVIDER_AUTHORIZATION`/`LEGAL_REVIEW` | Consensus excluded. |
| Consensus exclusion | Explicit MVP exclusion and dependent-interface rejection test | `PRODUCT_OWNER_DECISION` | C-13 remains unresolved, with consensus still blocked. |
| Delegated spec approval | Persisted clean fresh-context Sol xhigh review bound to this file and source hashes | `DELEGATED_ARTIFACT_APPROVAL` only | Spec remains draft; no rights gate is affected. |

No source evidence or approval may be invented. Every non-delegated approval is a distinct canonical human resolution with actor, authority, exact scope, timestamp, evidence, and decision. This draft contains no satisfied approval record.

## 8. Acceptance tests and verification

1. Inventory fixture: any used source absent from the register fails.
2. Boundary fixture: a stale or missing S01 boundary reference invalidates all dependent rights decisions.
3. Dimension-independence fixture: access approval with caching `UNKNOWN` blocks caching.
4. Mode-isolation fixture: private/internal rights cannot authorize public or paid use.
5. Evidence fixture: missing, changed, expired, or non-primary evidence blocks the affected operation.
6. Limit fixture: an account-limit breach prevents the request and records a typed failure.
7. Replacement fixture: a primary-source failure does not switch to an unapproved replacement.
8. Consensus inclusion fixture: `NECESSARY` without full current licensing and typed approvals remains `UNRESOLVED` and excluded.
9. Consensus exclusion fixture: `EXCLUDED_FROM_MVP` rejects consensus fields and provider calls at interfaces.
10. Approval fixture: one human decision cannot satisfy two approval types or scopes.
11. Audit fixture: changed provider terms create a superseding version and preserve prior decisions.

Verification evidence must contain schema-test output, boundary and denial fixtures, exact source/license content hashes, and the applicable typed human records. A fresh Sol xhigh reviewer must verify exact A-05/C-13 and T-4/R-3 coverage before delegated artifact approval can be recorded.

## 9. Dependencies and amendment gate

- A-05 depends on S01/A-01.
- C-13 depends on A-05.
- S09 ingestion and point-in-time capture may consume only approved source operations from this contract.
- S03 external-tool evaluation must consume relevant A-05 rights decisions rather than duplicate them.

S02 has **no mandatory evidence-derived provisional amendment gate** in the goal's four-row amendment table. Any accepted S01 boundary change, provider-term change, license change, source replacement, consensus-necessity change, or intended-mode change invalidates the affected decisions and requires a superseding artifact, fresh evidence, fresh Sol xhigh review, and fresh applicable human approvals before use resumes.
