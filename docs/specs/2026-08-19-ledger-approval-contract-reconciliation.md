# Ledger Approval-Contract Reconciliation (RC-2, RC-3, RC-4)

Revision: r2
Status: draft — this document authorizes no canonical write
Approved by: pending explicit current-user approval

## Problem Statement

The canonical ledger does not fully encode three authoritative approval-contract rules:

1. **RC-2 — multi-spec delegated approval:** Twenty rows apply to multiple specifications, but their delegated-approval scopes do not prove exhaustive specification enumeration or bind every covered specification’s current approved bytes. Previous review reasoning incorrectly treated bootstrap-generator symmetry as canonical authority.
2. **RC-3 — `DISP-M-3`:** The row requires competent-human governance over metric and claim-predicate vocabulary additions, but it lacks the corresponding `DOMAIN_EXPERT_ACCEPTANCE` requirement and mirrored typed evidence.
3. **RC-4 — `REG-A-09`:** The row requires both trademark/legal review and a product-owner identity decision, but it lacks the `PRODUCT_OWNER_DECISION` requirement.

These corrections alter fields included in the inventory-review input projection. Applying them separately would repeatedly invalidate SCOPE, EVIDENCE, and APPROVAL reviews and would increase the chance of partially reconciled authority. The correction therefore needs one hash-bound semantic transaction, followed by one inventory-review boundary after all final canonical bytes settle.

Architecture v2 is an approved design input. That approval does not authorize this canonical mutation and does not satisfy any ledger approval.

## Solution

Perform one atomic authority-reconciliation transaction covering exactly 22 canonical component rows:

- 20 RC-2 multi-spec rows;
- `DISP-M-3` for RC-3;
- `REG-A-09` for RC-4.

The transaction also updates the goal contract, its extracted structural enforcement, and the canonical human-review registry so that the new semantics and their authorization are applied together. It must not change product code.

### RC-2: multi-spec delegated approval

For each of the 20 multi-spec rows:

1. `scope_derivation.applicable_spec_ids` remains the exhaustive, sorted, unique coverage set.
2. The row has exactly one component-local `DELEGATED_ARTIFACT_APPROVAL` requirement for the entire set—not one requirement or approval per specification.
3. Its scope uses this canonical semantic form:

   ```text
   <component_id> delegated artifact approval for applicable specs [<sorted comma-separated spec IDs>]
   ```

4. The four affected sequence rows’ existing `SPEC-REVIEW` evidence requirements use the identical scope. No `SPEC-REVIEW` evidence requirement is added to disposition rows; that would reopen RC-1.
5. Policy codification leaves the delegated requirement `UNRESOLVED`. It adds no approval record, matched record, actor, timestamp, or satisfying evidence merely because the user selected the multi-spec policy.
6. Later satisfaction requires one persisted CLEAN combined review whose manifest contains exactly one entry for every enumerated specification:

   - exact specification ID;
   - canonical repository-relative specification path;
   - SHA-256 of the current approved file bytes.

   The manifest’s ID set must equal the row’s `applicable_spec_ids`; subsets, supersets, duplicates, future specifications, and transitive coverage fail validation.

7. One component-local approval record may cite the combined review and all byte-level evidence references. That is one multi-spec approval, not duplicate per-spec approvals.
8. Changing any covered specification’s approved bytes invalidates the current satisfaction for readiness purposes. Prior records remain immutable history, but no approval silently transfers to replacement bytes.

No new per-spec evidence references or approval records are introduced by this policy transaction. Those belong to the later approval-satisfaction event and must be based on an actual combined review.

### RC-3: `DISP-M-3`

Add exactly one unresolved approval requirement:

- Approval ID: `APR-DISP-M-3-02`
- Type: `DOMAIN_EXPERT_ACCEPTANCE`
- Required authority: `Vocabulary authority`
- Scope:

  ```text
  DISP-M-3 human-approval governance rule for metric-registry and claim-predicate-registry additions under S13
  ```

- Status: `UNRESOLVED`
- Actor, timestamp, matched record: `null`
- Evidence references: empty

Add exactly one mirrored typed-evidence requirement:

- Evidence ID: `REQ-DISP-M-3-DOMAIN_EXPERT_ACCEPTANCE-02`
- Evidence type: `DOMAIN`
- Proof mode: `TYPED_APPROVAL`
- Approval IDs: exactly `["APR-DISP-M-3-02"]`
- Scope: byte-for-byte identical to the approval scope
- Status: `UNRESOLVED`
- Evidence references: empty

The requirement approves the governance rule; it does not approve any present or future registry entry. Each actual metric or predicate addition remains subject to the distinct human-approval rule defined under S13.

No domain-expert resolution or approval record is created during reconciliation. Later satisfaction requires a separate active `SATISFY_APPROVAL` human resolution from a competent human acting as `Vocabulary authority`, bound to the exact scope and then-current governed bytes. That resolution must be linked bidirectionally through the canonical human-review artifact and mirrored by the typed evidence requirement.

The current user’s process authorization cannot satisfy this domain-expert requirement.

### RC-4: `REG-A-09`

Preserve the existing delegated-artifact and `LEGAL_REVIEW` requirements and add exactly one unresolved approval requirement:

- Approval ID: `APR-REG-A-09-03`
- Type: `PRODUCT_OWNER_DECISION`
- Required authority: `Product owner`
- Scope:

  ```text
  REG-A-09 product identity decision under S01: continued use or replacement of "Funda" after trademark-risk review
  ```

- Status: `UNRESOLVED`
- Actor, timestamp, matched record: `null`
- Evidence references: empty

No mirrored typed-evidence requirement is added. `PRODUCT_OWNER_DECISION` is not one of the canonical typed-evidence categories; its proof is the matching approval record and active human resolution.

Satisfaction requires a fresh, explicit `SATISFY_APPROVAL` resolution from a human acting under `Product owner` authority. The resolution must bind the exact `ProductIdentityDecision` identity and content digest. A legal decision does not imply the product decision, and the product decision does not imply legal clearance.

The current policy choice, Architecture v2 approval, reconciliation authorization, or push authorization does not satisfy `APR-REG-A-09-03`, even if the same individual could separately act as product owner.

### Affected components and fields

| Finding | Component | Applicable specs | Semantic mutations |
|---|---|---|---|
| RC-2 | `SEQ-02` | `S01`, `S02` | Delegated-approval scope; existing `SPEC-REVIEW` scope |
| RC-2 | `SEQ-03` | `S05`, `S09` | Delegated-approval scope; existing `SPEC-REVIEW` scope |
| RC-2 | `SEQ-04` | `S06`, `S08` | Delegated-approval scope; existing `SPEC-REVIEW` scope |
| RC-2 | `SEQ-08` | `S12`, `S13` | Delegated-approval scope; existing `SPEC-REVIEW` scope |
| RC-2 | `DISP-6-2` | `S06`, `S13` | Delegated-approval scope |
| RC-2 | `DISP-6-4` | `S19`, `S20` | Delegated-approval scope |
| RC-2 | `DISP-6-6` | `S07`, `S15` | Delegated-approval scope |
| RC-2 | `DISP-6-7` | `S03`, `S04` | Delegated-approval scope |
| RC-2 | `DISP-6-9` | `S11`, `S16` | Delegated-approval scope |
| RC-2 | `DISP-G-1` | `S06`, `S11`, `S16` | Delegated-approval scope |
| RC-2 | `DISP-G-4` | `S05`, `S18` | Delegated-approval scope |
| RC-2 | `DISP-G-5` | `S06`, `S13` | Delegated-approval scope |
| RC-2 | `DISP-M-4` | `S11`, `S25` | Delegated-approval scope |
| RC-2 | `DISP-M-5` | `S14`, `S15` | Delegated-approval scope |
| RC-2 | `DISP-M-6` | `S07`, `S15` | Delegated-approval scope |
| RC-2 | `DISP-M-8` | `S08`, `S18` | Delegated-approval scope |
| RC-2 | `DISP-M-9` | `S07`, `S09` | Delegated-approval scope |
| RC-2 | `DISP-R-1` | `S19`, `S20` | Delegated-approval scope |
| RC-2 | `DISP-R-5` | `S10`, `S14` | Delegated-approval scope |
| RC-2 | `DISP-T-4` | `S01`, `S02`, `S04` | Delegated-approval scope |
| RC-3 | `DISP-M-3` | `S13` | Add domain-expert approval and mirrored typed evidence |
| RC-4 | `REG-A-09` | `S01` | Add product-owner approval |

All 22 rows additionally receive the append-only reconciliation human-review link and corresponding transition-history update described below.

### Review invalidation and rerun boundary

Every existing pretransaction inventory-review artifact for an affected row becomes historical prestate evidence and must not be recorded against the posttransaction ledger. This includes reviews previously marked CLEAN.

Every existing affected `*-r0.md` artifact is byte-preserved. Before the semantic transaction, capture its repository-relative path and file-byte SHA-256; any missing file, byte drift, overwrite, deletion, or rename aborts. The r0 artifacts remain intentionally untracked throughout the semantic transaction, consistent with the current recorder rule that artifacts are untracked at record time. They are historical only and are never submitted to the refreshed recorder or manifest as current evidence.

Fresh reviews use only collision-free `*-r1.md` paths alongside the preserved r0 files. Review creation aborts if any intended r1 target already exists; no path is reused, truncated, or overwritten. The refreshed recorder and its manifest must select exactly the r1 path for each current review slot and reject an r0 selection, an r0/r1 ambiguity, a duplicate slot, or any current-evidence path other than the exact expected r1 path.

In inventory-review artifact paths, parsed bodies, and manifests, `r0`, `r1`, … identify an artifact-local inventory-review generation namespace. This namespace is independent of canonical ledger row `review_round`, which records applicable specification, plan, and implementation artifact review and open-finding progression. For this batch, the refreshed recorder must require inventory generation `1` consistently in the current artifact path, parsed body, and manifest; it must neither compare that generation with nor modify the row's canonical `review_round`. The semantic transaction and every later inventory-recording batch must preserve the exact canonical `review_round` prestates: `DISP-6-2`, `DISP-G-1`, `DISP-G-5`, `DISP-R-5`, and `SEQ-04` remain at `4`; the other seventeen affected rows remain at `0`.

After final transaction bytes settle:

- Nineteen RC-2 rows other than `DISP-R-1` require fresh SCOPE, EVIDENCE, and APPROVAL reviews: 57 artifacts.
- `DISP-M-3` requires fresh SCOPE, EVIDENCE, and APPROVAL reviews: 3 artifacts.
- `REG-A-09` requires fresh EVIDENCE and APPROVAL reviews: 2 artifacts. No synthetic SCOPE review is introduced.
- Immediate posttransaction total: exactly 62 fresh review artifacts.
- `DISP-R-1` receives its three fresh reviews only during T2, after its final no-implementation evidence settles.
- Final affected-row total across the immediate round and T2: exactly 65 artifacts.

All review types for one row must be based on the same final row bytes and recorded atomically as one row batch. An earlier CLEAN SCOPE review cannot be combined with a later EVIDENCE or APPROVAL review.

Durability occurs only in the later review-recording batch, not in the semantic transaction. For every row recorded by that batch, the batch explicitly stages and commits both its byte-preserved historical r0 artifacts and its current r1 artifacts together with that batch's canonical ledger recording change. The r0 files remain historical inputs excluded from the current-evidence manifest; staging them for durability does not make them current. `DISP-R-1` has no pretransaction r0 artifacts and remains reserved for T2.

### Hash-bound user-authorization gate

Canonical application is forbidden until all of the following exist:

1. Final r2 bytes of this specification.
2. An independent CLEAN review of those exact bytes by role `REVIEWER`, actual model `gpt-5.6-sol`, effort `high`.
3. A concrete atomic reconciliation design and complete before/after mutation manifest derived from this specification.
4. An independent CLEAN review of the exact reconciliation design and manifest by role `REVIEWER`, actual model `gpt-5.6-sol`, effort `high`.
5. A transaction implementation produced by role `IMPLEMENTER`, actual model `gpt-5.6-terra`, effort `high`, plus its independent CLEAN review and exact hashes.
6. Successful isolated success-path and rollback/recovery rehearsals against exact prestate copies, using conspicuously labelled stand-ins for the not-yet-existent user-response timestamp and the two record-file post-state hashes.
7. A fully rendered approval question containing every concrete binding below and only the two expressly permitted dynamic post-state-hash placeholders.
8. A fresh exact current-user response given after items 1–7 are available.

The user approval must bind:

- exact paths and SHA-256 values for this specification, its CLEAN review, the reconciliation design, its mutation manifest, the implementation, and every independent CLEAN review of those artifacts;
- exact prestate hashes of the goal contract, ledger, human-review artifact, extracted structural validator, preimplementation validator, and inventory-review recorder;
- exact deterministic poststate hashes of the amended goal contract and its extracted structural validator;
- the exact 22-component scope above;
- the complete allowed field-class manifest and per-component before/after digests;
- the closed construction rules in this specification and the reviewed transaction design for `HR-0006`, `HRD-0006-001`, and exactly 22 append-only `AUTHORITY_RECONCILIATION` transitions, including the exact response-timestamp derivation, digest bases, ordering, link post-states, transition IDs, transition sequences, old/new values, and hash-chain rules;
- fixed identities `HR-0006` and `HRD-0006-001`, plus every fixed evidence and transition identity named by the reviewed design;
- explicit dynamic placeholders `<LEDGER_POST_SHA256>` and `<HUMAN_REVIEW_POST_SHA256>` for only the ledger and human-review poststate file hashes;
- transaction evidence bindings `IMPLEMENTER`, actual model `gpt-5.6-terra`, effort `high`, and `REVIEWER`, actual model `gpt-5.6-sol`, effort `high`;
- the successful rehearsal-evidence digest;
- an explicit statement that the transaction codifies approval obligations but satisfies none of RC-2, RC-3, or RC-4;
- authorization to apply exactly that transaction and no broader mutation.

The two record-file poststate hashes cannot honestly exist before the response. The response's real UTC timestamp participates in `HRD-0006-001.content_sha256`; that resolution digest participates in all 22 transitions; those transitions determine the ledger poststate; and the entry/resolution determine the human-review poststate. A rehearsal timestamp would therefore produce stand-in hashes, not canonical hashes. No timestamp or poststate hash may be fabricated, guessed, or represented as final before the response.

After the exact response, the executor must capture its real timestamp from the authoritative response record. If that timestamp is unavailable or ambiguous, the single-authorization construction is unsound and canonical application aborts; a separately reviewed two-confirmation design is then required. Otherwise the executor deterministically constructs the real ledger and human-review candidates from the already authorized closed rules, computes `<LEDGER_POST_SHA256>` and `<HUMAN_REVIEW_POST_SHA256>`, and durably journals those hashes, all semantic-target preimages, and the complete authorization package before the first canonical replacement. The two journaled values are construction outcomes constrained by the prior approval, not invented pre-response approval facts.

Candidate generation and validation happen outside canonical targets. Immediately before replacement, compare-and-swap re-verifies every prestate hash and every construction postcondition. After replacement, all deterministic and semantic postconditions run against canonical paths. Any hash, scope, identity, timestamp, field-class, link, transition, review-preservation, validation, or dirty-tree mismatch rolls back all four semantic targets to byte-identical preimages. Incomplete rollback enters durable `RECOVERY_REQUIRED` and blocks further canonical mutation.

A CLEAN review is evidence for the user’s decision; it is not user authorization. Architecture v2 approval and the repository-scoped commit/push authority also do not replace this gate.

## User Stories

- As the current user, I want one exact, reviewable reconciliation scope so my approval cannot be interpreted as authority to mutate unrelated ledger fields.
- As a specification reviewer, I want a multi-spec approval to enumerate every covered specification and bind its current bytes so coverage cannot be inferred from one representative file.
- As a ledger maintainer, I want one combined approval per multi-spec component so I do not create redundant per-spec approval requirements.
- As a vocabulary authority, I want `DISP-M-3` to require a distinct human decision before its governance obligation can be satisfied.
- As a product owner, I want the product-identity decision for `REG-A-09` to remain distinct from trademark or legal review.
- As an inventory reviewer, I want all reconciliation mutations completed before I review final row bytes so earlier reviews are not mixed with later inputs.
- As an operator, I want an atomic, recoverable transaction so interruption cannot leave the goal contract, validator, ledger, and human-review registry semantically inconsistent.

## Implementation Decisions

1. **Architecture:** Use the approved Architecture v2 model. Do not reopen architecture selection.

2. **Transaction boundary:** RC-2, RC-3, and RC-4 are one semantic authority reconciliation because they share the same canonical review-input boundary and current-user authorization. Separate canonical transactions would add no authority isolation and would create avoidable stale-review rounds.

3. **Canonical transaction targets:** The atomic semantic transaction includes only:

   - the goal contract’s multi-spec, approval, human-link, and reconciliation invariants;
   - the extracted structural validator corresponding to that goal contract;
   - the 22 affected ledger rows;
   - one new canonical human-review entry and its one active reconciliation resolution.

   The preimplementation validator and extractor remain byte-preserved because readiness semantics and extraction mechanics do not change. The current inventory recorder is not used after the transaction until its pins, exact r1-path selection, r0/r1 ambiguity rejection, and projection checks have been separately refreshed, reviewed, and rehearsed. That tooling refresh is operational follow-up, not another semantic ledger reconciliation, and must not mutate ledger rows.

4. **Reconciliation human review:** Use the next sequence-safe current identities, which are `HR-0006` and `HRD-0006-001` for the present prestate.

   - Entry type: `DECISION`
   - Decision authority: `GOAL_OR_PROCESS_AUTHORIZATION`
   - Resolution type: `RECONCILE_AUTHORITY`
   - Actor type: `HUMAN`
   - Actor role: `CURRENT_USER`
   - Scope: exactly the 22 canonical component IDs in this specification
   - State: resolved only after the fresh hash-bound user response

5. **Human-link growth:** For every affected row, define the poststate mechanically as `sorted(set(prestate) | {"HR-0006"})`. The exact current-prestate-to-poststate mapping is:

   | Component | Exact prestate | Exact poststate |
   |---|---|---|
   | `SEQ-02` | `HR-0004` | `HR-0004`, `HR-0006` |
   | `SEQ-03` | `HR-0004` | `HR-0004`, `HR-0006` |
   | `SEQ-04` | `HR-0001`, `HR-0004` | `HR-0001`, `HR-0004`, `HR-0006` |
   | `SEQ-08` | `HR-0004` | `HR-0004`, `HR-0006` |
   | `DISP-6-2` | `HR-0001`, `HR-0004` | `HR-0001`, `HR-0004`, `HR-0006` |
   | `DISP-6-4` | `HR-0004` | `HR-0004`, `HR-0006` |
   | `DISP-6-6` | `HR-0004` | `HR-0004`, `HR-0006` |
   | `DISP-6-7` | `HR-0004` | `HR-0004`, `HR-0006` |
   | `DISP-6-9` | `HR-0004` | `HR-0004`, `HR-0006` |
   | `DISP-G-1` | `HR-0001`, `HR-0004` | `HR-0001`, `HR-0004`, `HR-0006` |
   | `DISP-G-4` | `HR-0004` | `HR-0004`, `HR-0006` |
   | `DISP-G-5` | `HR-0001`, `HR-0004` | `HR-0001`, `HR-0004`, `HR-0006` |
   | `DISP-M-3` | `HR-0004` | `HR-0004`, `HR-0006` |
   | `DISP-M-4` | `HR-0004` | `HR-0004`, `HR-0006` |
   | `DISP-M-5` | `HR-0004` | `HR-0004`, `HR-0006` |
   | `DISP-M-6` | `HR-0004` | `HR-0004`, `HR-0006` |
   | `DISP-M-8` | `HR-0004` | `HR-0004`, `HR-0006` |
   | `DISP-M-9` | `HR-0004` | `HR-0004`, `HR-0006` |
   | `DISP-R-1` | `HR-0004`, `HR-0005` | `HR-0004`, `HR-0005`, `HR-0006` |
   | `DISP-R-5` | `HR-0003`, `HR-0004` | `HR-0003`, `HR-0004`, `HR-0006` |
   | `DISP-T-4` | `HR-0004` | `HR-0004`, `HR-0006` |
   | `REG-A-09` | `HR-0004` | `HR-0004`, `HR-0006` |

   `HR-0001`, `HR-0003`, and `HR-0005` are therefore preserved on every affected row where they already exist. `HR-0002`, every human-review link on every unaffected row, and every existing human-review entry/resolution remain globally byte-preserved. The goal's A12 restriction is narrowed only enough to admit conforming `HR-0006` over this exact 22-component scope; every other unexpected overlap still fails.

6. **Transition history:** Each affected row appends exactly one `AUTHORITY_RECONCILIATION` transition for append-only `human_review_id` growth, bound to `HRD-0006-001`. Existing transition entries remain byte-for-byte prefixes. `transition_history_sha256` is recomputed from the resulting history.

   Approval and evidence inventories are not transition-replay fields; their authorized before/after values are instead bound by the transaction manifest and reconciliation resolution. No synthetic transition type is invented for them.

7. **Allowed ledger field classes:**

   - RC-2 rows: the existing delegated requirement’s `scope`;
   - RC-2 sequence rows only: the existing `SPEC-REVIEW` evidence requirement’s `scope`;
   - `DISP-M-3`: append one `required_approvals` item and one `required_evidence` item;
   - `REG-A-09`: append one `required_approvals` item;
   - all 22 rows: append-only `human_review_id`, one corresponding transition-history entry, and its recomputed history digest.

   Inventory-review projection digests may change only as derived consequences of these semantic fields when later reviews are recorded.

8. **Forbidden ledger mutations:** Preserve all unrelated bytes, including:

   - component identity, kind, source coordinates, authority rank, ownership, and applicability sets;
   - dispositions, delivery states, gates, blockers, activation/rejection records, and implementation state;
   - existing evidence and approval items;
   - all approval records;
   - all evidence references;
   - all approval and evidence statuses;
   - existing human-review entries and resolutions;
   - review slots and review-round state during reconciliation;
   - security exceptions, aliases, and unrelated rows.

9. **RC-1 boundary:** Do not add disposition `SPEC-REVIEW` evidence requirements, do not impose generator symmetry, and do not change the RC-1 ruling.

10. **Approval separation:** The reconciliation resolution authorizes the contract correction only. RC-2 delegated approvals, the RC-3 domain-expert approval, and the RC-4 product-owner decision remain unresolved until independently satisfied under their own authority and evidence rules.

11. **Transaction evidence bindings:** Authorization, design, manifest, implementation, review artifacts, and the canonical human-review evidence record use role and invocation fields separately:

   - role `REVIEWER`; actual model `gpt-5.6-sol`; effort `high`;
   - role `IMPLEMENTER`; actual model `gpt-5.6-terra`; effort `high`.

   These are evidence bindings for this transaction only. Model names are not roles and these bindings do not redefine the reusable domain roles in `CONTEXT.md`. No review that affects the hash-bound authorization or canonical transaction is trivial or skippable.

12. **Atomicity and recovery:** The transaction uses manifest-controlled compare-and-swap semantics:

   - exclusive transaction lock;
   - exact prestate content hashes and modes;
   - startup refusal when a prior nonterminal journal exists;
   - candidate generation outside canonical targets;
   - full candidate validation before the first replacement;
   - durable journal transitions;
   - deterministic same-filesystem atomic replacement;
   - postreplacement hash and semantic validation;
   - reverse-order rollback for any failure, including interruption;
   - `RECOVERY_REQUIRED` fail-closed state if complete rollback cannot be proven.

   A failure before the first replacement changes no canonical target. A later failure must prove full restoration or block all further canonical mutation.

13. **Baseline preservation:** Existing ledger, human-review, and transition-history baseline prefixes remain byte-for-byte intact. The current transition baseline manifest, including its fixed prefix population, is not regenerated from poststate data.

14. **Readiness:** `ready` remains `false` throughout reconciliation and the immediate review round. It cannot become true until all required review inventories are current, all other preimplementation conditions pass, and `DISP-R-1` T2 has completed with its final no-implementation evidence and three current reviews.

15. **Repository-scoped commit and push authority:** The current user previously granted repository-scoped commit/write/delete/review/push authority and later answered `Push: yes`; this specification preserves that authority only for this repository. Commit and push remain outside the atomic canonical transaction. They may occur only after the semantic transaction has passed every postcondition and a subsequent independent reviewed checkpoint has passed. That authority does not authorize broader mutation, relax the manifest, permit unreviewed bytes, or extend beyond this repository.

16. **Separate runtime defect:** The structural validator's Beads `--readonly` runtime defect is tracked separately as `eqos-3sn.1.4`. It is not a semantic target, does not weaken any reconciliation postcondition, and is not repaired or worked around by this transaction.

## Success Criteria

1. The reconciliation manifest names exactly 22 unique canonical component IDs: the 20 RC-2 rows, `DISP-M-3`, and `REG-A-09`.

2. Exactly 20 rows have two or more sorted unique `applicable_spec_ids` and exactly one `DELEGATED_ARTIFACT_APPROVAL` requirement whose scope enumerates that exact set using the canonical scope form.

3. The four sequence rows have an existing `SPEC-REVIEW` evidence requirement with a scope byte-for-byte equal to their delegated-approval scope.

4. Zero disposition rows gain a `SPEC-REVIEW` evidence requirement.

5. Removing, adding, duplicating, reordering, or implicitly inheriting an RC-2 specification ID causes structural validation to fail.

6. An RC-2 approval cannot be `SATISFIED` unless one CLEAN combined review manifest exactly matches the applicable-spec set and every recorded byte digest matches the current approved specification file.

7. The transaction adds exactly one approval requirement and one typed-evidence requirement to `DISP-M-3`, with the IDs, type, authority, proof mode, linked approval ID, scope, and unresolved shape specified above.

8. `DISP-M-3` has no new approval record or invented domain-expert resolution.

9. The transaction adds exactly one `PRODUCT_OWNER_DECISION` requirement to `REG-A-09`, with the ID, authority, scope, and unresolved shape specified above.

10. `REG-A-09` gains no product-owner typed-evidence requirement, approval record, or invented product decision. Its existing legal requirement remains unchanged.

11. The transaction adds zero approval records across all 22 rows and changes zero existing approval or evidence statuses to `SATISFIED`.

12. `HR-0006` contains exactly the 22 affected component IDs, and `HRD-0006-001` is its sole active `RECONCILE_AUTHORITY` resolution.

13. Every affected row's links equal `sorted(set(prestate) | {"HR-0006"})` and match the exact 22-row table. In particular, all existing `HR-0001`, `HR-0003`, and `HR-0005` links are retained; `HR-0002` and all unrelated rows and links remain globally byte-identical.

14. Exactly 22 new `human_review_id` reconciliation transitions are appended—one per affected row. Every prior transition entry remains an exact prefix, and every resulting transition-history digest verifies.

15. The authorized field-level diff contains only the allowed field classes stated in this specification. Any additional semantic field change aborts before canonical replacement.

16. Existing canonical rows outside the 22-ID scope remain byte-for-byte identical.

17. The fixed ledger, human-review, and transition baseline prefixes and their committed digests remain unchanged.

18. Goal-contract extraction reports no embedded/extracted validator drift.

19. Structural validation passes against the complete candidate and again against canonical poststate.

20. The preimplementation validator reports `ready=false` after reconciliation. It must report no false readiness caused by the new policy, approval requirements, or review states.

21. Exactly 62 immediate fresh inventory-review artifacts are produced from posttransaction bytes, and they are recorded only in complete row-atomic batches.

22. `DISP-R-1` receives no premature correction-round inventory recording. Its three current reviews are produced and recorded only during T2 after final no-implementation evidence settles.

23. Across the immediate round and T2, exactly 65 affected-row inventory reviews exist for final applicable bytes: 21 SCOPE, 22 EVIDENCE, and 22 APPROVAL reviews.

24. Every existing affected r0 review artifact remains byte-identical at its captured pretransaction path and digest. No r0 artifact is accepted as current for a posttransaction row.

25. Every fresh review is created at its exact collision-free r1 path; any existing target aborts. The refreshed manifest selects only r1 as current and rejects r0/r1 ambiguity, duplicate slots, path reuse, and r0 selection.

26. Each later review-recording batch commits its applicable preserved r0 artifacts and current r1 artifacts together with that batch's canonical ledger recording change, while only r1 is current evidence.

27. Pre-response rehearsal proves the deterministic targets and closed construction using labelled stand-ins only. Post-response construction uses the authoritative real response timestamp, journals the two resulting record-file hashes before replacement, and proves the exact intended poststate. No fabricated timestamp or hash is accepted.

28. Fault injection proves either complete rollback of all semantic targets to byte-identical prestate or durable `RECOVERY_REQUIRED`.

29. The canonical apply uses the exact approved prestate hashes, deterministic poststate hashes, artifact/design/review/implementation hashes, scope, fixed IDs, field manifest, and closed construction rules. The ledger and human-review files equal the two post-response journaled outcome hashes. Any drift or construction mismatch invalidates authorization and aborts application.

30. The preimplementation validator and extractor remain byte-identical. The Beads `--readonly` defect remains separate under `eqos-3sn.1.4`.

31. Commit and push occur only after the semantic transaction and a subsequent independent reviewed checkpoint pass, outside the atomic transaction and within this repository only.

32. No product code is created or changed.

## Testing Decisions

Testing is specification- and transaction-focused.

1. **Static manifest tests**

   - Verify the exact 22-component set.
   - Verify the exact RC-2 spec mappings.
   - Verify deterministic sorted scope generation.
   - Verify the allowed field-class diff.

2. **RC-2 positive tests**

   - Accept one combined approval over an exact two-spec set.
   - Accept one combined approval over the exact three-spec sets for `DISP-G-1` and `DISP-T-4`.
   - Verify one requirement and one record cover the set without per-spec duplicates.

3. **RC-2 negative tests**

   - Reject a representative-spec-only review.
   - Reject a subset, superset, duplicate, unsorted, future-spec, or transitively inferred set.
   - Reject a byte digest from a prior specification version.
   - Reject several independent per-spec reviews presented as though they were the required combined approval.
   - Reject satisfaction without a persisted CLEAN combined review.

4. **RC-3 tests**

   - Reject the row when the domain approval or mirrored evidence is absent.
   - Reject mismatched approval IDs or scopes.
   - Reject non-`DOMAIN` evidence, non-`TYPED_APPROVAL` proof, or an unauthorized actor.
   - Reject a process-authorization resolution presented as domain-expert acceptance.
   - Confirm reconciliation leaves the requirement unresolved.

5. **RC-4 tests**

   - Reject the row when the product-owner requirement is absent.
   - Reject legal review as a substitute for the product decision.
   - Reject process authorization as a substitute for product-owner authorization.
   - Reject a product decision not bound to the exact identity-decision digest.
   - Confirm no unsupported typed-evidence item is introduced.

6. **Human-link tests**

   - Verify exact append-only link growth for all 22 rows.
   - Verify `SEQ-04`, `DISP-6-2`, `DISP-G-1`, and `DISP-G-5` retain `HR-0001`; `DISP-R-5` retains `HR-0003`; and `DISP-R-1` retains `HR-0004` and `HR-0005`.
   - Verify every existing `HR-0002` link and every link on every unaffected row is byte-preserved.
   - Reject removal, replacement, or unexpected additional human-review IDs.
   - Verify forward and reverse links for `HR-0006`.

7. **Review-freshness tests**

   - Capture and recheck every affected r0 path and file-byte digest; reject overwrite, deletion, rename, or byte drift.
   - Confirm every r0 artifact is historical and non-recordable as current against poststate.
   - Reject creation when an intended r1 path exists; reject any manifest with r0 selection, r0/r1 ambiguity, duplicate slots, path reuse, or a non-r1 current path.
   - Confirm row-atomic recording rejects mixed inventory-review generations or mixed review-input digests.
   - Confirm each recording batch stages its applicable r0 and r1 artifacts with the canonical ledger recording change while selecting only r1 as current.
   - Confirm the 62 immediate and 3 T2 review counts and review-type distribution.

8. **Atomicity tests**

   - Exercise pre-response success using isolated copies and conspicuously labelled stand-in timestamps/hashes; prove stand-in record-file hashes are never treated as canonical.
   - Exercise post-response candidate construction from the authoritative real response timestamp and prove both computed record-file hashes are journaled before replacement.
   - Inject failure before the first replacement, between replacements, during postvalidation, and during rollback.
   - Exercise interruption handling for normal exceptions, base exceptions, and termination signals.
   - Verify journal replay and startup refusal for every nonterminal state.
   - Verify all four semantic targets roll back together; modes, hashes, r0 artifacts, and unrelated dirty-worktree bytes are preserved.

9. **Final gates**

   - Run goal/extracted-validator consistency checks.
   - Run structural validation.
   - Run preimplementation validation and confirm fail-closed `ready=false`.
   - Verify the preimplementation validator and extractor hashes are unchanged and report the separate `eqos-3sn.1.4` runtime defect without conflating it with semantic validation.
   - Check the exact canonical diff and repository status, obtain the subsequent independent reviewed checkpoint pass, then commit and push outside the atomic transaction.

## Out of Scope

- Reopening or modifying RC-1.
- Adding disposition `SPEC-REVIEW` evidence for generator symmetry.
- Sourcing-tier policy or its ledger encoding.
- Satisfying any RC-2 delegated approval.
- Inventing or satisfying the RC-3 domain-expert resolution.
- Making or satisfying the RC-4 product-identity decision.
- Performing trademark or legal review.
- Approving actual metric or predicate registry additions.
- Completing `DISP-R-1` T2.
- Product-code design or implementation.
- Changes to unrelated component rows, specifications, approval contracts, or evidence inventories.
- Regenerating canonical data from bootstrap-generator behavior.
- Concrete implementation code and exact shell commands. The ordering and authority constraints for later commit/push and review-recording durability remain binding.

## Open Questions

None. This r2 specification remains a draft until a fresh independent review of its exact bytes returns `CLEAN` and the current user gives the exact hash-bound approval defined above. This document does not approve itself and authorizes no canonical write.

## Further Notes

Canonical authority and invariants:

- `docs/goals/equity-os-blueprint-completion.md`
- `docs/goals/equity-os-blueprint-component-ledger.jsonl`
- `docs/goals/handoff/HANDOFF-2026-08-19.md`
- `docs/goals/handoff/nonclean-review-triage-2026-08-17.md`
- `docs/goals/reviews/ledger/equity-os-blueprint-rc1-forensic-audit-r0.md`

Applicable blueprint and specification authority includes the cited passages and current bytes under:

- `docs/blueprint/`
- `docs/specs/`

Current review evidence is under:

- `docs/goals/reviews/ledger/inventory/SEQ-02/`
- `docs/goals/reviews/ledger/inventory/SEQ-03/`
- `docs/goals/reviews/ledger/inventory/SEQ-04/`
- `docs/goals/reviews/ledger/inventory/SEQ-08/`
- `docs/goals/reviews/ledger/inventory/DISP-6-2/`
- `docs/goals/reviews/ledger/inventory/DISP-6-4/`
- `docs/goals/reviews/ledger/inventory/DISP-6-6/`
- `docs/goals/reviews/ledger/inventory/DISP-6-7/`
- `docs/goals/reviews/ledger/inventory/DISP-6-9/`
- `docs/goals/reviews/ledger/inventory/DISP-G-1/`
- `docs/goals/reviews/ledger/inventory/DISP-G-4/`
- `docs/goals/reviews/ledger/inventory/DISP-G-5/`
- `docs/goals/reviews/ledger/inventory/DISP-M-3/`
- `docs/goals/reviews/ledger/inventory/DISP-M-4/`
- `docs/goals/reviews/ledger/inventory/DISP-M-5/`
- `docs/goals/reviews/ledger/inventory/DISP-M-6/`
- `docs/goals/reviews/ledger/inventory/DISP-M-8/`
- `docs/goals/reviews/ledger/inventory/DISP-M-9/`
- `docs/goals/reviews/ledger/inventory/DISP-R-1/`
- `docs/goals/reviews/ledger/inventory/DISP-R-5/`
- `docs/goals/reviews/ledger/inventory/DISP-T-4/`
- `docs/goals/reviews/ledger/inventory/REG-A-09/`

Transaction, validation, review-recording, and recovery semantics are grounded in the current structural validator, preimplementation validator, inventory-review recorder, journal tooling, and the reviewed HR-0004/HR-0005 reconciliation designs. Bootstrap-generator behavior is non-authoritative unless expressly imported by the goal contract.
