# S17 — Entity/security master, relationships, and corporate actions

Status: DRAFT — AWAITING FRESH SOL XHIGH REVIEW

## 1. Contract identity and authority

This specification is the sole primary specification for S17. It defines the implementation boundary for entity/security identity, factual relationships, and corporate actions. It does not itself decide C-17 or claim approval of a source hierarchy.

| Program field | Exact value |
|---|---|
| Spec ID | S17 |
| Exact title | Entity/security master, relationships, and corporate actions |
| Exact path | docs/specs/equity-os-s17-entity-security-master-actions.md |
| Primary register IDs | C-06, C-07, C-17 |
| Disposition references | M-7, 6.3 |
| Activation classification | Active-only |
| Initial program disposition | REQUIRED_NOW |
| Amendment ownership | None |

Authority is applied in this order:

1. The live v2 decision register controls decision wording, dependencies, Status, and acceptance.
2. The Exact 25-spec program assigns C-06, C-07, and C-17 only to S17.
3. Disposition M-7 and correction 6.3 qualify the identity model.
4. This contract fails closed if the approved C-17 authority policy is missing, conflicted, or stale.

### Exact register ownership

The following cells reproduce the controlling register text exactly.

| Register ID | Blueprint phase | Priority | Decision or action | Required evidence / acceptance | Dependencies | Activation source status | Primary owner |
|---|---|---:|---|---|---|---|---|
| C-06 | Phase 1 | Critical | Put authoritative corporate actions in SQL | Splits, bonuses, rights, demergers, dividends, ticker changes, and delistings are versioned events | C-17 | Open | S17 — Entity/security master, relationships, and corporate actions |
| C-07 | Phase 1 | High | Put factual entity relationships in bitemporal SQL | Parent/subsidiary, management roles, ownership, cross-holdings, and validity/knowledge intervals are represented | C-17 | Open | S17 — Entity/security master, relationships, and corporate actions |
| C-17 | Phase 1 | High | Decide entity/security master authority | Stable internal company/security IDs; versioned ISIN/symbol/CIN/LEI mappings; source hierarchy, conflicts, valid/knowledge time, and one real identifier-change case tested | A-05, A-06 | Open | S17 — Entity/security master, relationships, and corporate actions |

### Disposition obligations

M-7 requires stable internal company_id and security_id values. ISIN, exchange symbol, CIN, LEI, and other identifiers are versioned external mappings with valid-time and knowledge-time intervals. The decision must name a source hierarchy for each identifier type, a conflict-resolution rule, symbol and listing changes, corporate-action handling, and one real identifier-change test case.

Correction 6.3 is controlling qualification: ISIN is an external identifier. It is a high-value mapping, not the authority for Equity-OS object identity.

## 2. Scope

S17 specifies:

- stable, opaque internal company and security identities;
- stable, opaque person endpoints only where needed to type management relationships;
- versioned external-identifier mappings;
- source assertions and an approved authority/conflict policy;
- bitemporal factual entity relationships;
- versioned corporate-action events;
- point-in-time resolution by valid time and knowledge time;
- interfaces, invariants, failure behavior, approval gates, and tests.

### Non-goals

S17 does not:

- use ISIN, CIN, LEI, exchange symbol, issuer name, or provider key as an internal primary key;
- define provider/data rights, ingestion, document storage, or observation/fact schemas owned by S02, S09, and S12;
- infer factual relationships from prose without evidence and reconciliation;
- compute adjusted prices, portfolio positions, or execution instructions;
- silently merge companies or securities;
- assert that the proposed source order is approved;
- activate a Deferred capability.

## 3. Core data contracts

Every identity, mapping, relationship, and event is append-only or superseded by a new version. Deletion is prohibited for accepted records; invalid records are retained with status and reason.

### 3.1 Shared master-record version envelope

Every Company, Security, and Person version contains record_id, the stable company_id/security_id/person_id, positive monotonic record_version, the type-specific immutable payload below, valid_from/to, knowledge_from/to, source-assertion IDs/content digests, C-17 policy ID/version/digest, authority_state, authority_transition_ids, acceptance_binding, nullable supersedes_record_id/version/digest, created_at, and record_sha256. Version 1 has a null supersedes reference. A later version must name the same stable internal ID and the exact current predecessor; it cannot silently move content to a new internal ID. The valid/knowledge intervals use the same half-open, explicit-unknown rules as identifier mappings; null end means open-ended, never unknown.

`record_sha256` is SHA-256 of the program's canonical JSON containing record type/ID/version, stable internal ID, every type-specific payload field, both temporal intervals, source-assertion IDs/content digests, policy ID/version/digest, supersedes reference, and created_at. It excludes the digest itself, derived authority_state, authority_transition_ids, and acceptance_binding. Any content change creates a new version and transition chain.

At most one ACCEPTED version for one stable internal ID may cover the same valid_at/known_at pair. Accepting a successor and superseding its predecessor must be linked by the same policy or human-resolution evidence; a gap, fork, stale predecessor, overlapping accepted pair, or attempt to reuse a stable ID for a distinct real-world subject fails closed. Business lifecycle/listing values and their legal transitions come only from the approved versioned C-17 policy; an unknown or unapproved value cannot be accepted.

### 3.2 Company

Company uses the shared version envelope and contains a legal-name-history ID/version/digest, entity type, jurisdiction, and policy-registered lifecycle value. company_id is opaque, stable, non-reusable, and has no embedded external meaning.

### 3.3 Security

Security uses the shared version envelope and contains issuer company_id, security type/class, currency, and policy-registered listing-lifecycle value. One company may issue multiple securities. A listing is not a company and a symbol is not a security identity.

### 3.4 Person

Person uses the shared version envelope and contains a sourced name-history ID/version/digest. person_id is opaque, stable, and non-reusable. It exists only to type relationship endpoints; a name, provider key, or employment record is never the person identity.

### 3.5 EntityParticipant and predicate contracts

An EntityParticipant is a tagged pair of `participant_type` (`COMPANY`, `PERSON`, or `SECURITY`) and the corresponding stable `participant_id`. The tag and ID kind must agree. Every relationship validates the following predicate-specific roles before it can leave CANDIDATE:

| Predicate | Subject role | Object role | Required predicate attributes |
|---|---|---|---|
| PARENT_OF | COMPANY | COMPANY | Relationship scope; ownership attributes only when asserted by the source |
| SUBSIDIARY_OF | COMPANY | COMPANY | Relationship scope; ownership attributes only when asserted by the source |
| MANAGEMENT_ROLE_AT | PERSON | COMPANY | Versioned role type, source-reported role title, and appointment scope; appointment/cessation timing is carried by the relationship valid-time interval |
| OWNS | COMPANY or PERSON | COMPANY or SECURITY | Ownership basis and scope; quantity, percentage, denominator, and as-of semantics are typed when asserted and never guessed |
| CROSS_HOLDING_WITH | COMPANY | COMPANY | Symmetric relationship stored once with endpoints ordered by stable ID; each directional interest and its denominator/scope are separate typed attributes |

Any other participant pairing fails validation. Predicate-attribute definitions are versioned under the approved C-17 relationship policy and require the existing S17-G04 domain acceptance; unregistered role or ownership semantics remain unresolved.

### 3.6 ExternalIdentifierMapping

Each mapping contains mapping_id, subject_type, subject_id, identifier_type, normalized_value, issuing_authority/market, valid_from, valid_to, knowledge_from, knowledge_to, source_assertion IDs and content digests, policy ID/version/digest, authority_state, authority_transition_ids, acceptance_binding, supersedes_mapping_id, and mapping_digest.

Intervals are half-open. Null valid_to or knowledge_to means open-ended, not unknown. Unknown endpoints use explicit unknown fields and cannot be represented by guessed dates.

Supported initial identifier types include ISIN, EXCHANGE_SYMBOL, CIN, and LEI. Adding a type requires a versioned policy entry, normalization rules, collision rules, and human approval.

### 3.7 SourceAssertion

A source assertion preserves assertion_id, source document/location, captured bytes hash, issuer/source identity, observed value, parsed value, parser version, valid-time claim, knowledge time, confidence/quality flags, and supersession linkage. Assertions never become authoritative merely because multiple providers repeat them.

### 3.8 EntityRelationship

Each relationship contains relationship_id, typed subject EntityParticipant, predicate, typed object EntityParticipant, the predicate-specific attributes above, valid_from/to, knowledge_from/to, source assertion IDs and content digests, policy ID/version/digest, authority_state, authority_transition_ids, acceptance_binding, supersession linkage, and digest.

Initial predicates are PARENT_OF, SUBSIDIARY_OF, MANAGEMENT_ROLE_AT, OWNS, and CROSS_HOLDING_WITH. Inverse edges are derived views unless separately asserted; they are never separate authorities.

### 3.9 CorporateAction

Each action contains corporate_action_id, action_type, issuer_company_id, affected security_ids, announcement/ex/reference/record/payment dates with explicit semantics, terms as typed fields, currency/unit, valid time, knowledge time, source assertion IDs and content digests, policy ID/version/digest, event_status, authority_state, authority_transition_ids, acceptance_binding, revision/supersession linkage, and digest.

Initial action types are SPLIT, BONUS, RIGHTS, DEMERGER, DIVIDEND, TICKER_CHANGE, and DELISTING. A ticker change versions the mapping; it does not replace company_id or security_id. A split, bonus, rights issue, or demerger records affected and resulting securities explicitly and never rewrites prior observations.

`event_status` is one of ANNOUNCED, CONFIRMED, EFFECTIVE, or CANCELLED. Across immutable action versions, the only forward transitions are ANNOUNCED to CONFIRMED, EFFECTIVE, or CANCELLED and CONFIRMED to EFFECTIVE or CANCELLED. EFFECTIVE and CANCELLED are terminal; a correction creates a new version rather than an illegal reverse transition.

### 3.10 Authority state, transition, and digest contract

`authority_state` is derived for every Company, Security, Person, ExternalIdentifierMapping, EntityRelationship, and CorporateAction version from an append-only transition chain and is one of CANDIDATE, CONFLICTED, ACCEPTED, REJECTED, SUPERSEDED, or REVOKED. A new record starts CANDIDATE. The only legal transitions are CANDIDATE to CONFLICTED, ACCEPTED, or REJECTED; CONFLICTED to ACCEPTED or REJECTED; and ACCEPTED to SUPERSEDED or REVOKED. REJECTED, SUPERSEDED, and REVOKED are terminal. Corrections and reacceptance create a new CANDIDATE version; no state can be caller-supplied or inferred from recency.

Every authority transition contains transition_id, record type/ID and record content digest, consecutive sequence, from_state, to_state, reason, policy ID/version/content digest, evidence IDs/content digests, nullable human_review_id, nullable approval_record_id, nullable resolution_decision_id and resolution_content_sha256, previous_transition_sha256, and transition_sha256. The transition digest is SHA-256 of the program's canonical JSON of every preceding transition field except `transition_sha256`. The first previous hash is null; every later transition names the immediately preceding digest. A human reconciliation must bind the exact active canonical resolution and its matching approval record; stale, revoked, mismatched-scope, mismatched-purpose, or content-digest-mismatched decisions fail.

`acceptance_binding` declares `POLICY_MATCH` or `HUMAN_RECONCILIATION`, the current approved policy ID/version/digest, and the applicable approval-record and canonical-resolution bindings. POLICY_MATCH is valid only when the approved policy deterministically selects the record without a material conflict. HUMAN_RECONCILIATION is mandatory for CONFLICTED to ACCEPTED and includes the exact policy-designated human decision. Missing or stale bindings prohibit ACCEPTED. A master-record version cannot inherit acceptance from a mapping, relationship, action, predecessor version, or another stable internal ID.

For ExternalIdentifierMapping, EntityRelationship, and CorporateAction, the named record digest is SHA-256 of the program's canonical JSON of every immutable payload field listed in its contract, including source assertion IDs/content digests, policy ID/version/digest, and supersession linkage, but excluding the digest itself, derived `authority_state`, `authority_transition_ids`, and `acceptance_binding`. Company, Security, and Person use the shared master-record preimage above. Each transition and human resolution binds that immutable record digest; changing content requires a new record/version and transition chain.

## 4. C-17 authority and conflict policy

The source hierarchy below is a proposed implementation default and remains non-authoritative until S17-G02 is satisfied. “Official” means the exact source approved under A-05 for the initial operating boundary.

| Data type | Proposed primary authority | Proposed secondary corroboration | Fail-closed conflict rule |
|---|---|---|---|
| Company master attributes | Official corporate registry designated by policy | Issuer regulatory filing | Conflicting real-world identity, jurisdiction, entity type, or lifecycle evidence blocks acceptance or supersession; name similarity never merges IDs |
| Security master attributes | Official exchange or depository security master designated by policy | Issuer regulatory filing | Conflicting issuer, class, currency, or listing-lifecycle evidence blocks acceptance; a listing or symbol never replaces security_id |
| Person endpoint identity | Issuer regulatory filing or official disclosure designated by relationship policy | Another approved official filing | Conflicting identity evidence remains unresolved; matching names or provider keys never merge person_id values |
| ISIN | Official depository/security-master record | Official exchange record or issuer regulatory filing | Preserve all assertions; do not select a canonical mapping until the primary authority or an approved reconciliation resolves the conflict |
| Exchange symbol and listing status | Official exchange security master, circular, or listing notice | Issuer regulatory filing; approved depository record | Resolve per exchange and validity interval; never treat the same text symbol across markets or time as one identity |
| CIN | Official corporate registry record | Issuer regulatory filing | Registry conflict blocks canonical mapping pending reconciliation |
| LEI | Official LEI registry record | Issuer regulatory filing or approved official registry mirror | Registry conflict blocks canonical mapping pending reconciliation |
| Corporate action | Official exchange/corporate-action notice designated by policy | Issuer filing and approved depository record | Material term/date/security conflict blocks downstream adjustment and requires a versioned decision |
| Entity relationship | Issuer regulatory filing or official registry designated by predicate policy | Approved exchange filing or other source permitted by A-05 | Conflicting scope, percentage, role, or interval is preserved and remains unresolved until reconciled |

The approved policy must identify exact source names, access methods, rights status, identifier normalization, effective-date rules, and the competent resolver for every type. Provider convenience, ingest order, recency alone, and model confidence are not authority rules.

## 5. Required interfaces

### 5.1 Resolve external identifier

Input: identifier type/value, issuing authority or market, valid_at, known_at, and intended subject type.

Output: exactly one company_id/security_id plus the selected mapping, the exact consumable subject master-record version, and evidence, or a typed AMBIGUOUS, NOT_FOUND, CONFLICT, OUTSIDE_VALID_TIME, OUTSIDE_KNOWLEDGE_TIME, POLICY_UNAVAILABLE, RECORD_INVALID, or INCOMPLETE_AUTHORITY result. Ambiguous resolution never returns a best guess.

A mapping is selectable only when its recomputed authority_state is ACCEPTED, its identifier/subject types and intervals match the query, its approved policy and acceptance binding are current at `known_at`, every bound source assertion is resolvable, its subject resolves to exactly one consumable master-record version at the same valid_at/known_at pair, and no unresolved material conflict applies. A missing/stale policy or approval binding returns POLICY_UNAVAILABLE; an illegal transition, broken chain, invalid endpoint, or content-digest mismatch returns RECORD_INVALID; absent master authority returns INCOMPLETE_AUTHORITY; an unresolved material conflict returns CONFLICT.

### 5.2 Resolve subject state

Input: company_id, security_id, or person_id, valid_at, known_at.

Output: the exact authoritative Company/Security/Person version plus all authoritative identifiers, listings, relationships, and corporate actions whose valid and knowledge intervals include the query points and satisfy the consumption predicates below, with source, policy, transition, and reconciliation records; otherwise a typed CONFLICT, POLICY_UNAVAILABLE, RECORD_INVALID, or INCOMPLETE_AUTHORITY result. If the subject's master version or any requested dependent record is non-consumable, the resolver returns the applicable failure instead of silently omitting it and presenting a complete state.

### 5.3 Record assertion

Input: immutable source/evidence identity, observed master/identifier/relationship/action payload, parser identity, captured_at, and asserted temporal semantics.

Output: a new SourceAssertion and candidate record. It never mutates an accepted master, mapping, relationship, or event.

### 5.4 Reconcile conflict

Input: conflicting record IDs and content digests, exact policy ID/version/content digest, human-review ID, approval-record ID, active resolution decision ID/content digest, rationale, selected outcome, and evidence IDs/content digests.

Output: an append-only CONFLICTED-to-ACCEPTED or CONFLICTED-to-REJECTED transition and any newly accepted Company/Security/Person/mapping/relationship/action version. The decision cannot erase rejected assertions, reuse a decision for another scope, mutate the reconciled payload, or transfer acceptance between stable internal IDs.

### 5.5 Query corporate actions and relationships

Every query requires valid_at and known_at. Omitting known_at is invalid for evidence packages and historical replay. Results include the policy version and record digests used.

`consumable_master(record, valid_at, known_at)` is TRUE if and only if the Company/Security/Person version's authority_state is ACCEPTED, its transition chain and record digest recompute, policy and acceptance bindings are current, valid and knowledge intervals contain the query points, every source assertion/digest resolves, it is the sole accepted version covering that query pair, and no material conflict remains.

`consumable(record, valid_at, known_at)` for a mapping, relationship, or action is TRUE if and only if authority_state is ACCEPTED, the transition chain and content digest recompute, policy and acceptance bindings are current, participant tags satisfy the predicate contract, valid and knowledge intervals contain the query points, every bound evidence digest resolves, every referenced Company/Security/Person endpoint is consumable at the same query pair, and no material conflict remains. A corporate action may affect calculations only when `consumable` is TRUE, `event_status=EFFECTIVE`, and the query satisfies the action's typed date semantics; ANNOUNCED or CONFIRMED actions may be returned as accepted evidence but cannot drive an effective adjustment, and CANCELLED actions never drive one.

## 6. Invariants and fail-closed behavior

1. Internal IDs are stable, opaque, never reused, and unaffected by name, symbol, listing, ISIN, CIN, or LEI changes.
2. A company, issued security, and exchange listing are distinct concepts.
3. Every selected external mapping resolves through an approved policy version and current source evidence.
4. Valid time and knowledge time are independently stored and queried; ingestion time may not substitute for either without an explicit semantic definition.
5. Later corrections never retroactively rewrite what was knowable at an earlier cutoff.
6. Conflicting assertions remain visible. Recency, provider order, or model confidence cannot silently choose a winner.
7. Overlapping accepted mappings for the same identifier/authority interval that resolve to different subjects are prohibited.
8. Corporate actions are versioned events; changes create revisions/supersession, never in-place mutation.
9. Relationships require typed predicates, direction, interval, source, and scope. Missing temporal or evidence fields block acceptance.
10. Query APIs fail if valid_at or known_at is absent where point-in-time behavior matters.
11. Unresolved identity or action conflicts block dependent facts, calculations, and reports that require that resolution.
12. No corporate-action record may invoke execution or mutate an external account.
13. CANDIDATE, CONFLICTED, REJECTED, SUPERSEDED, REVOKED, illegally transitioned, stale-policy, stale-resolution, or digest-mismatched records are never authoritative inputs.
14. Company, Security, and Person authority is version-local. A predecessor, external identifier, accepted relationship, or same-name record cannot confer authority on a candidate master version.
15. Every relationship/action endpoint and identifier-mapping subject resolves to a consumable master-record version at the same valid_at/known_at pair; incomplete master authority blocks the dependent record.

## 7. Evidence and typed approval gates

All entries begin unresolved. This draft and an automated review are not human authority.

| Gate | Type | Required authority | Required evidence | Blocks |
|---|---|---|---|---|
| S17-G01 | DELEGATED_ARTIFACT_APPROVAL | Fresh gpt-5.6-sol xhigh reviewer under delegated goal authority | Persisted clean review, exact source hashes, review round, reviewer/session identity, timestamp, and artifact hash | Spec approval and planning |
| S17-G02 | PRODUCT_OWNER_DECISION | Human product owner competent to set product data authority | Approved, versioned source hierarchy, conflict policy, resolver roles, and exact source names for every master/identifier/action/relationship type | C-17 acceptance and all implementation |
| S17-G03 | DATA_RIGHTS_APPROVAL | Competent human/data-rights authority | Current A-05-backed approval for every automated source and retained field | Ingestion or automated refresh from that source |
| S17-G04 | DOMAIN_EXPERT_ACCEPTANCE | Competent human corporate-actions/entity-data expert | Acceptance of identity semantics, temporal rules, action terms, relationship predicates, and the real identifier-change fixture | C-06, C-07, and C-17 acceptance |
| S17-G05 | ANALYST_ACCEPTANCE | Human analyst responsible for the workflow | Review of conflict presentation and point-in-time resolution on the real case | Phase 1 workflow acceptance |

Required evidence inventory:

- approved source-authority and conflict-policy artifact with content hash;
- source-rights records linked to the policy;
- schema/constraint and migration artifacts;
- source-assertion, core master-record version/digest/lifecycle, typed participant/predicate, authority-state transition, reconciliation, bitemporal query, and corporate-action fixtures;
- one real, source-linked identifier-change case exercising old and new mappings at different valid/knowledge cutoffs;
- typed approval records for S17-G02 through S17-G05;
- current delegated review and verification outputs bound to artifact hashes.

## 8. Acceptance tests and verification

| Test ID | Required proof |
|---|---|
| S17-T01 | Changing a symbol, ISIN, company name, listing, CIN, or LEI never changes company_id or security_id. |
| S17-T02 | One company with multiple securities and one security with sequential listings resolves without collapsing concepts. |
| S17-T03 | valid_at and known_at queries return historically correct mappings and exclude later corrections. |
| S17-T04 | Conflicting source assertions remain preserved and produce CONFLICT until a policy-designated human reconciliation binds the exact record, policy, approval record, active resolution decision, and content digests. |
| S17-T05 | Overlapping accepted mappings for one identifier/authority interval and different subjects are rejected by constraints. |
| S17-T06 | A real identifier-change case resolves the old and new identifiers over their correct intervals and retains both source histories. |
| S17-T07 | Split, bonus, rights, demerger, dividend, ticker-change, and delisting fixtures each create versioned events with a closed event_status and source evidence; only an ACCEPTED EFFECTIVE version can drive an adjustment. |
| S17-T08 | Revising corporate-action terms creates a new version and leaves the prior known-at view reproducible. |
| S17-T09 | Parent/subsidiary, management-role, ownership, and cross-holding fixtures enforce the predicate endpoint table. In particular, MANAGEMENT_ROLE_AT requires PERSON-to-COMPANY endpoints plus role type/title/scope, and wrong endpoint tags or missing predicate attributes fail. |
| S17-T10 | Missing valid_at/known_at, unknown or stale policy versions, illegal authority/event transitions, unresolved conflicts, absent source evidence, unapproved sources, stale/revoked resolutions, and digest mismatches fail closed. |
| S17-T11 | Downstream fact/calculation requests consume only records satisfying the exact ACCEPTED-state predicate; every other authority state and every non-EFFECTIVE corporate-action adjustment is rejected. |
| S17-T12 | Corporate-action records cannot carry credentials, executable instructions, or account-operation side effects. |
| S17-T13 | Mutating an endpoint, predicate attribute, action term, source assertion digest, policy digest, or supersession link changes the record digest and invalidates the prior transition chain, reconciliation, and downstream proof. |
| S17-T14 | Company, Security, and Person fixtures prove version-local ACCEPTED authority: changing type, issuer, lifecycle/listing value, name-history reference, interval, source/policy digest, or predecessor link changes record_sha256 and requires a new CANDIDATE version and transition chain. Copying predecessor or dependent-record acceptance is rejected. |
| S17-T15 | Point-in-time resolution selects exactly one ACCEPTED master-record version for each stable internal ID. A fork, stale predecessor, overlapping accepted pair, broken supersession link, missing source/authority binding, or non-consumable endpoint returns RECORD_INVALID or INCOMPLETE_AUTHORITY and blocks mappings, relationships, actions, and downstream calculations. |

Verification requires schema checks, participant/predicate and state-machine constraint tests, bitemporal query fixtures, the real identifier-change case, current source/evidence hashes, and all applicable approvals. Mechanical tests cannot satisfy data-rights, product-owner, domain, or analyst gates.

## 9. Dependencies, activation, and amendment guards

- C-17 depends on A-05 source/data-rights decisions and A-06 filing-channel evidence. Exact source policy cannot be accepted before those inputs exist.
- C-06 and C-07 depend on accepted C-17 authority and conflict policy.
- S09 owns ingestion and point-in-time capture; S12 owns observation/fact identity. S17 consumes their evidence contracts and owns only master/relationship/action semantics.
- Deferred activation guard: not applicable to owned rows. C-06, C-07, and C-17 were Open at activation, so S17 is active-only. No owned capability may be marked dormant or advanced through an ACTIVATE_DEFERRED record.
- Amendment gate: no evidence-derived provisional amendment gate is assigned to S17. A later approved change to source hierarchy, conflict policy, identifier normalization, or temporal semantics requires a versioned policy, impact/migration evidence, fresh Sol review, and repetition of every affected human approval; it may not rewrite historical resolutions.
