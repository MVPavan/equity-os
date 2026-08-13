# S13 — Claim schema, vocabulary registries, and evidence validation

**Status: DRAFT — AWAITING FRESH SOL XHIGH REVIEW**

This document is an implementation contract, not evidence of delegated approval. It does not grant analyst, domain, product, legal, regulatory, or other human authority.

## 1. Authority and ownership

The v2 decision register states exactly: “The wording in this register is authoritative for implementation gates. Narrative reviews explain rationale but do not override this register.” If this contract conflicts with the register, the register wins and implementation stops pending amendment and fresh review.

| Ownership field | Exact source text |
|---|---|
| Spec ID | `S13` |
| Spec title | `Claim schema, vocabulary registries, and evidence validation` |
| Exact path | `docs/specs/equity-os-s13-claim-schema-vocabulary-evidence.md` |
| Primary register IDs | `B-06, B-12, C-04` |
| Disposition references | `G-5, M-3, 6.2` |
| Activation classification | `active-only` |

The owned register rows are reproduced without semantic rewriting:

| ID | Priority | Decision or action | Required evidence / acceptance | Dependencies | Status |
|---|---:|---|---|---|---|
| B-06 | Critical | Derive minimum typed claim schema | Subject, registered predicate, object, scope, horizon, epistemic class, confidence, materiality result/policy version, status, evidence direction, and supersession are represented | A-10, B-12 | Open |
| B-12 | Critical | Establish versioned metric and predicate registries | Registry definitions, aliases, object/unit/dimension rules, addition approval, deprecation, and versioning exist; every structured fact/claim resolves to a registered entry; embedding-assisted dedup is optional | A-04, A-06 | Open |
| C-04 | Critical | Implement materiality- and epistemic-class-aware claim validation | Material observed/computed claims require direct source or calculation support; material inferences/forecasts require linked evidence, explicit assumptions, uncertainty, and correct labeling; contradiction and materiality reasoning are visible | A-10, B-06 | Open |

Disposition authority is limited to these exact findings:

- `G-5 — Undefined materiality`: materiality combines quantitative magnitude, always-material categories, thesis relevance, uncertainty/source conflict, and coverage-level overrides; the decision is versioned and reviewable.
- `M-3 — Predicate and metric vocabulary governance`: begin with small versioned metric and predicate registries, aliases/deprecations, definitions, expected object types, units/dimensions, scope rules, and human approval for additions; embedding-assisted duplicate suggestions are optional later.
- `6.2 Materiality is not only a financial-statement threshold`: a percentage threshold alone is insufficient; governance, guidance, thesis relevance, and source conflict also apply.

## 2. Scope

This contract owns:

1. The logical invariants and evidence-driven derivation procedure for the minimum typed claim schema.
2. Versioned metric and claim-predicate registry contracts.
3. Validation rules that combine epistemic class, materiality, evidence, assumptions, uncertainty, contradictions, and supersession.
4. Amendment tests that prevent the provisional B-06 contract from being mistaken for a final physical schema.

### Non-goals

- Selecting a final table layout, ORM, database engine, or complete field catalogue before vertical-slice evidence exists.
- Defining the A-10 materiality policy; S13 consumes its approved, versioned result.
- Owning observation/fact identity or revision families, which belong to S12.
- Owning deterministic calculation operators or traces, which belong to S16.
- Allowing embedding-assisted registry deduplication to block Phase 0.5.
- Treating confidence as an epistemic class or prose as the authoritative claim representation.

## 3. Logical interfaces and data contracts

Names below define logical payloads. The B-06 amendment may refine names and physical representation, but it may not remove their required semantics without authority reconciliation.

### 3.1 `TypedClaim`

| Field | Contract |
|---|---|
| `claim_id` | Stable unique identity for this immutable claim version. |
| `subject` | Typed subject reference; unresolved or free-floating subjects fail validation. |
| `predicate_ref` | Exact predicate registry entry and version; aliases resolve to one non-deprecated canonical entry. |
| `object` | Typed value/reference compatible with the predicate's declared object type, unit, dimensions, and scope. |
| `scope` | Explicit company/security/segment/statement or other registered scope required by the predicate. |
| `horizon` | Explicit temporal horizon; it does not substitute for valid time or knowledge time on evidence. |
| `epistemic_class` | Exactly one of `observed`, `computed`, `inferred`, `forecast`, or `opinion`. |
| `confidence` | Separate from epistemic class; representation and scale are frozen by the amendment evidence. |
| `materiality_result` | Reviewable result produced under `materiality_policy_version`; unknown or stale results block material-claim validation. |
| `materiality_policy_version` | Immutable reference to the approved A-10 policy version. |
| `status` | Versioned lifecycle state; accepted status never erases prior versions. Final states are derived during the B-06 amendment. |
| `evidence_links` | Nonempty typed links where required, each with evidence direction and an exact fact, calculation trace, or source-location target. |
| `assumption_refs` | Explicit assumptions required for material `inferred` and `forecast` claims. |
| `uncertainty` | Explicit uncertainty required for material `inferred` and `forecast` claims. |
| `supersedes_claim_id` | Prior claim version when superseding; the prior claim remains auditable. |
| `contradiction_refs` | Known contradicting evidence or claims and their resolution state. |

`evidence direction` is mandatory claim semantics, but its final controlled vocabulary is evidence-derived under B-06. Until that amendment freezes the vocabulary, implementations must preserve the source direction without coercing it into a guessed enum.

### 3.2 `MetricDefinitionVersion`

Each entry contains a stable metric ID, immutable version, name, definition, allowed aliases, deprecation status and replacement, value/object type, unit and dimension rules, scope rules, definition version, effective interval, and the typed approval reference for its addition. An alias may resolve to exactly one canonical metric version and may not form a chain or cycle.

### 3.3 `PredicateDefinitionVersion`

Each entry contains a stable predicate ID, immutable version, name, definition, allowed aliases, deprecation status and replacement, expected subject type, expected object type, unit/dimension constraints, scope rules, and the typed approval reference for its addition. A structured claim must resolve to exactly one current or explicitly pinned historical entry.

### 3.4 `ClaimValidationRequest` and result

The request binds the immutable claim version, evidence-package version, run cutoff, materiality-policy version, metric/predicate registry versions, referenced facts, calculation traces, sources, assumptions, and contradictions. The result is immutable and contains `PASS`, `FAIL`, or `BLOCKED`, rule outcomes, visible materiality reasoning, visible contradiction reasoning, exact failed references, validator version, and input digest.

`PASS` means the declared rules were satisfied for those exact bytes and versions. It does not grant human acceptance or memory promotion.

## 4. Invariants and fail-closed behavior

1. Every structured fact and claim resolves to a registered, version-pinned entry; missing, ambiguous, deprecated-without-explicit-pin, or type-incompatible resolution blocks the claim.
2. Subject, predicate, object, scope, horizon, epistemic class, confidence, materiality result/policy version, status, evidence direction, and supersession semantics are never silently defaulted.
3. Material `observed` claims require direct exact-source support. Material `computed` claims require a registered calculation trace. Missing support is `FAIL`, not a warning.
4. Material `inferred` and `forecast` claims require linked evidence, explicit assumptions, explicit uncertainty, correct epistemic labeling, and visible reasoning. Missing any element is `FAIL`.
5. `opinion` never masquerades as observed, computed, inferred, or forecast evidence.
6. Unresolved materiality, unknown policy version, unavailable evidence, stale registry version, unresolved source conflict, or cutoff-ineligible support returns `BLOCKED` or `FAIL`; it never passes by omission.
7. Contradictory evidence remains visible even if a claim passes after a documented resolution.
8. Registry updates append versions. Renames, aliases, deprecations, and changed definitions do not rewrite historical claims.
9. A registry addition is unusable until its required competent-human approval is active and content-bound.
10. Supersession creates a new claim version and an explicit link; no accepted claim is overwritten or deleted.

## 5. Evidence and typed approval gates

| Gate | Approval type | Required authority | Evidence required | Fail-closed rule |
|---|---|---|---|---|
| Initial or amended S13 artifact | `DELEGATED_ARTIFACT_APPROVAL` | Fresh `gpt-5.6-sol` xhigh reviewer under delegated goal authority | Persisted clean review, exact source hashes, review round, timestamp, and reviewed artifact hash | Current status remains draft until the separate review record exists; this author cannot approve it. |
| Add metric definition | `DOMAIN_EXPERT_ACCEPTANCE` | Competent human domain steward identified by the program | Immutable proposed definition/version, conflicts/aliases checked, scope and unit rules, actor authority basis, decision, timestamp, and content digest | Entry remains inactive if any field or human resolution is absent, denied, revoked, expired, or stale. |
| Add claim-predicate definition | `DOMAIN_EXPERT_ACCEPTANCE` | Competent human domain steward identified by the program | Immutable proposed definition/version, expected types, scope rules, conflicts/aliases checked, actor authority basis, decision, timestamp, and content digest | Entry remains inactive under the same conditions. |

Every human approval must be a distinct canonical resolution binding actor, human actor type, authority basis, exact scope, decision, timestamp, evidence, and immutable content digest. A model, coordinator, inferred condition, nearby approval, or matching string cannot supply or widen it. One approval satisfies at most one declared requirement.

## 6. Mandatory B-06 amendment gate

This initial contract is intentionally provisional. It defines invariants, derivation procedure, fixtures, and amendment checks; it does **not** claim a final minimum claim schema.

The exact gate is: derive the B-06 minimum from A-10/B-12 and actual vertical-slice use, then amend and freshly review S13 before dependent claim implementation continues. The amendment must include:

1. A field-by-field derivation ledger linking each retained, added, changed, or deferred field to actual workflow evidence.
2. Frozen controlled vocabularies that this draft deliberately leaves evidence-derived, including claim status, confidence representation, and evidence direction.
3. Fixtures covering every epistemic class, materiality branch, contradiction path, registry version/deprecation path, and supersession path.
4. Compatibility and migration tests proving historical claims remain readable and unmodified.
5. Fresh Sol xhigh review and a new delegated-artifact approval record. Previous review evidence does not approve amended bytes.

While the amendment is due, dependent claim-schema implementation is blocked. A provisional contract may not be represented as final B-06 acceptance.

## 7. Activation guard

S13 is `active-only` at the pinned draft snapshot because B-06, B-12, and C-04 are all `Open`; it owns no `Deferred` register row. Therefore no deferred capability is activated by this contract. If an owned row is later changed to `Deferred`, or ownership expands to a deferred row, implementation stops until the canonical authority and activation inventory are reconciled and this spec is amended and freshly reviewed.

## 8. Dependencies

Authoritative dependencies are exact:

- B-06 depends on A-10 and B-12.
- B-12 depends on A-04 and A-06.
- C-04 depends on A-10 and B-06.

Interface dependencies are S06 for the A-10 materiality policy, S09 for A-06 source evidence, S12 for fact/observation identity, S14 for workflow integration, S15 for human review/supersession, and S16 for calculation traces. These references do not transfer primary ownership.

## 9. Acceptance tests and verification

| Test | Fixture/action | Required result |
|---|---|---|
| S13-T01 Registry resolution | Submit claims/facts with current, aliased, unknown, cyclic-alias, deprecated, and type-incompatible entries. | Only an unambiguous valid pinned entry resolves; every other case fails closed. |
| S13-T02 Epistemic support | Exercise material observed, computed, inferred, forecast, and opinion claims with one required support element removed per case. | Observed requires exact source; computed requires trace; inferred/forecast require evidence, assumptions, uncertainty, and label; missing items fail. |
| S13-T03 Materiality | Exercise quantitative, always-material, thesis-relevant, conflict/uncertainty, and coverage-override cases. | Approved A-10 version is bound and reasoning visible; unknown/stale policy blocks. |
| S13-T04 Contradiction | Present supporting and contradicting evidence. | Contradiction and resolution remain visible and content-bound. |
| S13-T05 Supersession | Correct an accepted claim. | New version and explicit supersession link exist; prior version remains auditable. |
| S13-T06 Addition approval | Add metric and predicate definitions with absent, model-authored, denied, stale, and valid human resolutions. | Only distinct valid competent-human approvals activate the additions. |
| S13-T07 Cutoff | Reference otherwise valid evidence after the run cutoff. | Validation fails; evidence is not silently dropped or substituted. |
| S13-T08 Amendment | Attempt final B-06 acceptance without vertical-slice derivation evidence and fresh review. | Gate fails and dependent implementation remains blocked. |

Verification is complete only when these tests are automated against the implementation, all owned register acceptance text has current evidence, the mandatory amendment gate has been satisfied when due, and a fresh independent Sol xhigh review is clean. Structural presence of this file is not product verification.
