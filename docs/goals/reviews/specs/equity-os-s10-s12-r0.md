# S10–S12 Independent Specification Review

- **Reviewer:** `gpt-5.6-sol/xhigh`
- **Round:** `r0`
- **Review time:** `2026-08-13T02:35:36Z`
- **Committed baseline / current HEAD:** `fa4cd53`
- **Mode:** Independent, read-only
- **Approval meaning:** `CLEAN` would constitute delegated goal approval only, never personal user approval. No `CLEAN` verdict is issued in this review.

## Content bindings

| Role | Artifact | SHA-256 |
|---|---|---|
| Authority | `docs/goals/equity-os-blueprint-completion.md` — reviewed lines 129–870; hash binds complete file | `dabad7bfe3d2765a5ac9687376029d8587b4b2ac95bc03494155a974e5ddc67f` |
| Authority | `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| Authority | `docs/blueprint/funda-third-order-review-disposition-report.md` | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| Target | `docs/specs/equity-os-s10-source-of-truth-evidence-retention.md` | `aa21636384f2a15200718e9ec446ebab8baca51be2c4ab7b802011f4e807d4f4` |
| Target | `docs/specs/equity-os-s11-run-manifest-cutoff-reproducibility.md` | `9fff8f62f40a47b86f07ceb1082dd74a2cd1ad8410f064ab4864d8f9bf9a8b8d` |
| Target | `docs/specs/equity-os-s12-observation-fact-identity-schema.md` | `0a983c727537dcb34b3339aabf58e6c063f148ee06c01d35141d55b37264d0c9` |

## Findings

### Critical

#### F-01 — Specification approval is circularly blocked on product behavior

**Load-bearing:** Yes
**Affected:** S10, S11, S12

The goal prohibits product implementation until the specification program has clean delegated approval ([goal:645](docs/goals/equity-os-blueprint-completion.md:645), [goal:673](docs/goals/equity-os-blueprint-completion.md:673), [goal:730](docs/goals/equity-os-blueprint-completion.md:730)). Each target nevertheless requires behavioral proof before its initial delegated artifact approval:

- S10 requires sealed-package reconstruction, rejected writes, correction/deletion behavior, and workflow resumption proof ([S10:183](docs/specs/equity-os-s10-source-of-truth-evidence-retention.md:183)).
- S11 requires executable adapter, retrieval, gateway, manifest, and replay behavior ([S11:200](docs/specs/equity-os-s11-run-manifest-cutoff-reproducibility.md:200)).
- S12 requires identity, migration, canonical-switch, and cutoff behavior to be proved ([S12:291](docs/specs/equity-os-s12-observation-fact-identity-schema.md:291)).

Those are substantially implementation acceptance tests, not merely tests that the specification structurally declares the required cases. As written, approval requires product behavior while product work requires approval.

The initial delegated-approval gates must require review of the declared contract, fixtures, and test specifications. Actual behavioral execution should gate the corresponding register-row acceptance or implementation phase.

### Important

#### F-02 — Manifest hashes lack an exact canonical byte contract

**Load-bearing:** Yes
**Affected:** S10, S11

Both contracts make content hashes authoritative but define them only as hashes of “canonical manifest bytes”:

- `EvidencePackageManifest.manifest_sha256` ([S10:86](docs/specs/equity-os-s10-source-of-truth-evidence-retention.md:86), [S10:101](docs/specs/equity-os-s10-source-of-truth-evidence-retention.md:101))
- `RunManifest.manifest_sha256` ([S11:84](docs/specs/equity-os-s11-run-manifest-cutoff-reproducibility.md:84), [S11:105](docs/specs/equity-os-s11-run-manifest-cutoff-reproducibility.md:105))

Neither specification defines or explicitly imports an encoding contract covering key order, collection order, timestamp normalization, Unicode, numbers, nulls, and absent fields. Logically identical manifests can therefore produce different hashes. This undermines package reconstruction, artifact binding, and cross-store consistency.

#### F-03 — Evidence-package parentage does not identify an immutable parent version

**Load-bearing:** Yes
**Affected:** S10

S10 defines `evidence_package_id` as stable across monotonically increasing versions, but `parent_package_id` names only an ID ([S10:90](docs/specs/equity-os-s10-source-of-truth-evidence-retention.md:90), [S10:99](docs/specs/equity-os-s10-source-of-truth-evidence-retention.md:99)). It therefore cannot identify which immutable version is the parent and may simply point back to the same version family.

This conflicts with S11’s exact package binding by ID, version, and hash ([S11:94](docs/specs/equity-os-s11-run-manifest-cutoff-reproducibility.md:94)). Parentage needs an exact version/hash reference.

#### F-04 — S11 permits an unprovable cutoff escape

**Load-bearing:** Yes
**Affected:** S11

S11 permits `NOT_CUTOFF_CAPABLE` tools in current-period runs when policy and source rights allow them and their observation time is recorded ([S11:125](docs/specs/equity-os-s11-run-manifest-cutoff-reproducibility.md:125)). Recording invocation observation time does not prove that returned content was known at or before the run cutoff.

This contradicts S11’s own invariant that every retrieved record carry knowledge-time proof at or before cutoff ([S11:157](docs/specs/equity-os-s11-run-manifest-cutoff-reproducibility.md:157)) and weakens C-15. Such output must be denied or quarantined from authoritative evidence unless every admitted record independently proves cutoff eligibility.

#### F-05 — Run, attempt, package, and late-bound artifact state are not coherently versioned

**Load-bearing:** Yes
**Affected:** S11; interface with S10

A run can have multiple attempts ([S11:78](docs/specs/equity-os-s11-run-manifest-cutoff-reproducibility.md:78)), but `RunManifest` contains a singular evidence-package binding described as belonging “to the attempt” ([S11:94](docs/specs/equity-os-s11-run-manifest-cutoff-reproducibility.md:94)). `AttemptManifest` then adds package version again ([S11:107](docs/specs/equity-os-s11-run-manifest-cutoff-reproducibility.md:107)).

Additionally, approval and published-artifact fields begin empty and are later populated ([S11:101](docs/specs/equity-os-s11-run-manifest-cutoff-reproducibility.md:101)), while changing a manifest hash in place is forbidden ([S11:168](docs/specs/equity-os-s11-run-manifest-cutoff-reproducibility.md:168)). The contract does not define immutable manifest versions or append-only events that resolve these transitions.

Consequently, a multi-attempt run cannot be reconstructed unambiguously from the declared interface.

#### F-06 — Canonical-selection interval transitions contradict append-only storage

**Load-bearing:** Yes
**Affected:** S12; interface with S11

S12 says a canonical selection is never updated in place, but instructs implementations to “close the prior knowledge interval” before appending the new selection ([S12:76](docs/specs/equity-os-s12-observation-fact-identity-schema.md:76)). No immutable closure event, successor-derived end bound, or transactional non-overlap constraint is defined.

S11 assumes exactly one selection whose interval contains a cutoff ([S11:134](docs/specs/equity-os-s11-run-manifest-cutoff-reproducibility.md:134)). Concurrent or partial selection writes could therefore produce overlapping open intervals or require mutation of the prior record. The contract needs an explicit atomic, append-only transition model and a fail-closed uniqueness invariant.

#### F-07 — Event-level canonical-selection approval authority is undefined

**Load-bearing:** Yes
**Affected:** S12

S12 requires selector authority/evidence for canonical selections ([S12:136](docs/specs/equity-os-s12-observation-fact-identity-schema.md:136)) and says parser results cannot become facts or selections without required approval evidence ([S12:238](docs/specs/equity-os-s12-observation-fact-identity-schema.md:238)). Its approval table defines:

- policy-level `DOMAIN_EXPERT_ACCEPTANCE`;
- `ANALYST_ACCEPTANCE` for manual correction; and
- amendment approvals.

It does not define the typed requirement governing an initial selection, issuer restatement, source correction, parser-induced fact revision, or normalization-policy change ([S12:244](docs/specs/equity-os-s12-observation-fact-identity-schema.md:244)). The contract must either define the event-level mapping or explicitly delegate that closed mapping to S15. A vague selector-authority field cannot satisfy the goal’s typed, one-to-one approval model.

### Minor

#### F-08 — “Source occurrence” and “observation” are both separate and synonymous

**Load-bearing:** No
**Affected:** S12

The scope promises separation of “source occurrence” and “observation” ([S12:43](docs/specs/equity-os-s12-observation-fact-identity-schema.md:43)), while the identity table merges them into one `Source occurrence / observation` concept and one `observation_id` ([S12:69](docs/specs/equity-os-s12-observation-fact-identity-schema.md:69)). The terminology should consistently declare whether these are synonyms or separate lifecycle objects.

## Per-spec verdicts

### S10 — `ISSUES_FOUND`

Findings: **F-01, F-02, F-03**.

The exact title/path, B-03 and C-11 ownership, register wording, priorities, dependencies, `Open` activation statuses, active-only classification, and T-3/R-5 dispositions are otherwise correctly represented. The retention, scratchpad prohibition, typed approval separation, scale-trigger guard, and source-of-truth fail-closed rules are substantively aligned.

### S11 — `ISSUES_FOUND`

Findings: **F-01, F-02, F-04, F-05**.

The exact title/path, C-09/C-15/C-16 ownership, source wording, dependencies, `Open` statuses, active-only classification, and G-1/M-4/6.9 dispositions are otherwise correct. The layered replay classes and separation between artifact immutability and narrative regeneration are aligned with authority.

### S12 — `ISSUES_FOUND`

Findings: **F-01, F-06, F-07, F-08**.

The exact title/path, B-05/B-10/B-11/C-03 ownership, register text, priorities, dependencies, `Open` statuses, active-only classification, and M-2 disposition are otherwise correct. Both mandatory amendment gates and their provisional/deferred guards accurately preserve the goal’s evidence-derived sequencing.

## Batch verdict

**`ISSUES_FOUND — NOT APPROVED`**

The three documents are broadly aligned on ownership, authority, status, dependencies, disposition coverage, activation classification, deferred/amendment controls, and non-delegated approval boundaries. The batch is not internally closed, however: initial approval is circularly coupled to implementation proof, package/run versioning is ambiguous, cutoff enforcement has an escape path, and canonical-selection transitions and authority are underspecified.

## Overall verdict

**`ISSUES_FOUND`**

Delegated goal approval is withheld for S10, S11, and S12 at `r0`. The load-bearing findings require correction followed by a fresh `r1` review.