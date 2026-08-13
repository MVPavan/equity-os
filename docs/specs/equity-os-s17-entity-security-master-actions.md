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

### 3.1 Company

Company contains company_id, legal-name history reference, entity type, jurisdiction, lifecycle status, created_at, and provenance. company_id is opaque, stable, non-reusable, and has no embedded external meaning.

### 3.2 Security

Security contains security_id, issuer company_id, security type/class, currency, listing lifecycle, created_at, and provenance. One company may issue multiple securities. A listing is not a company and a symbol is not a security identity.

### 3.3 ExternalIdentifierMapping

Each mapping contains mapping_id, subject_type, subject_id, identifier_type, normalized_value, issuing_authority/market, valid_from, valid_to, knowledge_from, knowledge_to, source_assertion_ids, resolution_status, resolution_decision_id, supersedes_mapping_id, and mapping_digest.

Intervals are half-open. Null valid_to or knowledge_to means open-ended, not unknown. Unknown endpoints use explicit unknown fields and cannot be represented by guessed dates.

Supported initial identifier types include ISIN, EXCHANGE_SYMBOL, CIN, and LEI. Adding a type requires a versioned policy entry, normalization rules, collision rules, and human approval.

### 3.4 SourceAssertion

A source assertion preserves assertion_id, source document/location, captured bytes hash, issuer/source identity, observed value, parsed value, parser version, valid-time claim, knowledge time, confidence/quality flags, and supersession linkage. Assertions never become authoritative merely because multiple providers repeat them.

### 3.5 EntityRelationship

Each relationship contains relationship_id, subject_company_id, predicate, object_company_id or object_person_id, quantitative attributes where applicable, valid_from/to, knowledge_from/to, source assertion IDs, approval/reconciliation status, supersession linkage, and digest.

Initial predicates are PARENT_OF, SUBSIDIARY_OF, MANAGEMENT_ROLE_AT, OWNS, and CROSS_HOLDING_WITH. Inverse edges are derived views unless separately asserted; they are never separate authorities.

### 3.6 CorporateAction

Each action contains corporate_action_id, action_type, issuer_company_id, affected security_ids, announcement/ex/reference/record/payment dates with explicit semantics, terms as typed fields, currency/unit, valid time, knowledge time, source assertions, status, revision/supersession linkage, reconciliation decision, and digest.

Initial action types are SPLIT, BONUS, RIGHTS, DEMERGER, DIVIDEND, TICKER_CHANGE, and DELISTING. A ticker change versions the mapping; it does not replace company_id or security_id. A split, bonus, rights issue, or demerger records affected and resulting securities explicitly and never rewrites prior observations.

## 4. C-17 authority and conflict policy

The source hierarchy below is a proposed implementation default and remains non-authoritative until S17-G02 is satisfied. “Official” means the exact source approved under A-05 for the initial operating boundary.

| Data type | Proposed primary authority | Proposed secondary corroboration | Fail-closed conflict rule |
|---|---|---|---|
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

Output: exactly one company_id/security_id plus the selected mapping and evidence, or a typed AMBIGUOUS, NOT_FOUND, CONFLICT, OUTSIDE_VALID_TIME, or OUTSIDE_KNOWLEDGE_TIME result. Ambiguous resolution never returns a best guess.

### 5.2 Resolve subject state

Input: company_id or security_id, valid_at, known_at.

Output: all active identifiers, listings, relationships, and corporate actions whose valid and knowledge intervals include the query points, with source and reconciliation records.

### 5.3 Record assertion

Input: immutable source/evidence identity, observed identifier/relationship/action payload, parser identity, captured_at, and asserted temporal semantics.

Output: a new SourceAssertion and candidate record. It never mutates an accepted mapping/event.

### 5.4 Reconcile conflict

Input: conflicting record IDs, exact policy version, human decision record, rationale, selected outcome, and evidence.

Output: a versioned resolution and any newly accepted mapping/relationship/action. The decision cannot erase rejected assertions.

### 5.5 Query corporate actions and relationships

Every query requires valid_at and known_at. Omitting known_at is invalid for evidence packages and historical replay. Results include the policy version and record digests used.

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

## 7. Evidence and typed approval gates

All entries begin unresolved. This draft and an automated review are not human authority.

| Gate | Type | Required authority | Required evidence | Blocks |
|---|---|---|---|---|
| S17-G01 | DELEGATED_ARTIFACT_APPROVAL | Fresh gpt-5.6-sol xhigh reviewer under delegated goal authority | Persisted clean review, exact source hashes, review round, reviewer/session identity, timestamp, and artifact hash | Spec approval and planning |
| S17-G02 | PRODUCT_OWNER_DECISION | Human product owner competent to set product data authority | Approved, versioned source hierarchy, conflict policy, resolver roles, and exact source names for every identifier/action/relationship type | C-17 acceptance and all implementation |
| S17-G03 | DATA_RIGHTS_APPROVAL | Competent human/data-rights authority | Current A-05-backed approval for every automated source and retained field | Ingestion or automated refresh from that source |
| S17-G04 | DOMAIN_EXPERT_ACCEPTANCE | Competent human corporate-actions/entity-data expert | Acceptance of identity semantics, temporal rules, action terms, relationship predicates, and the real identifier-change fixture | C-06, C-07, and C-17 acceptance |
| S17-G05 | ANALYST_ACCEPTANCE | Human analyst responsible for the workflow | Review of conflict presentation and point-in-time resolution on the real case | Phase 1 workflow acceptance |

Required evidence inventory:

- approved source-authority and conflict-policy artifact with content hash;
- source-rights records linked to the policy;
- schema/constraint and migration artifacts;
- source-assertion, reconciliation, bitemporal query, and corporate-action fixtures;
- one real, source-linked identifier-change case exercising old and new mappings at different valid/knowledge cutoffs;
- typed approval records for S17-G02 through S17-G05;
- current delegated review and verification outputs bound to artifact hashes.

## 8. Acceptance tests and verification

| Test ID | Required proof |
|---|---|
| S17-T01 | Changing a symbol, ISIN, company name, listing, CIN, or LEI never changes company_id or security_id. |
| S17-T02 | One company with multiple securities and one security with sequential listings resolves without collapsing concepts. |
| S17-T03 | valid_at and known_at queries return historically correct mappings and exclude later corrections. |
| S17-T04 | Conflicting source assertions remain preserved and produce CONFLICT until approved reconciliation. |
| S17-T05 | Overlapping accepted mappings for one identifier/authority interval and different subjects are rejected by constraints. |
| S17-T06 | A real identifier-change case resolves the old and new identifiers over their correct intervals and retains both source histories. |
| S17-T07 | Split, bonus, rights, demerger, dividend, ticker-change, and delisting fixtures each create versioned events with source evidence. |
| S17-T08 | Revising corporate-action terms creates a new version and leaves the prior known-at view reproducible. |
| S17-T09 | Parent/subsidiary, management-role, ownership, and cross-holding fixtures preserve direction, scope, validity, knowledge, and evidence. |
| S17-T10 | Missing valid_at/known_at, unknown policy versions, unresolved conflicts, absent source evidence, and unapproved sources fail closed. |
| S17-T11 | Downstream fact/calculation requests cannot consume an unresolved subject or material corporate-action term. |
| S17-T12 | Corporate-action records cannot carry credentials, executable instructions, or account-operation side effects. |

Verification requires schema checks, constraint tests, bitemporal query fixtures, the real identifier-change case, current source/evidence hashes, and all applicable approvals. Mechanical tests cannot satisfy data-rights, product-owner, domain, or analyst gates.

## 9. Dependencies, activation, and amendment guards

- C-17 depends on A-05 source/data-rights decisions and A-06 filing-channel evidence. Exact source policy cannot be accepted before those inputs exist.
- C-06 and C-07 depend on accepted C-17 authority and conflict policy.
- S09 owns ingestion and point-in-time capture; S12 owns observation/fact identity. S17 consumes their evidence contracts and owns only master/relationship/action semantics.
- Deferred activation guard: not applicable to owned rows. C-06, C-07, and C-17 were Open at activation, so S17 is active-only. No owned capability may be marked dormant or advanced through an ACTIVATE_DEFERRED record.
- Amendment gate: no evidence-derived provisional amendment gate is assigned to S17. A later approved change to source hierarchy, conflict policy, identifier normalization, or temporal semantics requires a versioned policy, impact/migration evidence, fresh Sol review, and repetition of every affected human approval; it may not rewrite historical resolutions.
