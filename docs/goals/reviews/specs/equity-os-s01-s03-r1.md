# S01–S03 Independent Specification Review — r1

**Overall verdict: ISSUES_FOUND — delegated artifact approval is not granted.**

- **Reviewer:** `gpt-5.6-sol` / `xhigh`
- **CLI session UUID:** `019ff902-3d39-79b0-be9a-6e7e706ed0ed`
- **UTC:** `2026-08-13T02:51:13Z`
- **Review round:** `r1`
- **Current commit:** `f9553b68bc3dda0dce3994ae12ea33ba093a0b45`
- **r0 baseline:** `fa4cd53605914bf10376ad9b6264971711ff1f07`
- **Method:** Independent, read-only review; no delegation, Codex CLI, memory, web, or edits.
- **Target state:** Clean against current `HEAD`; the r0 fixes were committed concurrently during review without changing the reviewed contents.

## SHA-256 binding

| Artifact | SHA-256 |
|---|---|
| Goal authority, complete file | `dabad7bfe3d2765a5ac9687376029d8587b4b2ac95bc03494155a974e5ddc67f` |
| Goal authority, lines 129–870 | `1650313cacaf9a6ae26eac637639f5783dfec967a7189751540a9c27469f3a0e` |
| Decision register v2 | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| Disposition report | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| r0 report | `bb94f53f79f1b970e93e1c868197c8d04dd2c287ddf8898d0c3436e028482751` |
| S01 | `c99133b267dbd0ba28901db26fa47684dcd24b78f73e2c1ebb0021fdedf55b87` |
| S02 | `3d6ff743aee72beb8d734af25353970668dbb2a3fe8d4b336a9fd9af76d59211` |
| S03 | `f0fe7799683513c575c80fcf22722bd3afa6027ee853b9454aa20f161e32c410` |
| r0-baseline-to-current target diff | `39d0706e153582c4caf0561f57fbc4e2d2432255d29e8371ab965e1592ded761` |
| Current target working-tree diff | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` — empty |

## r0 finding dispositions

| r0 finding | r1 disposition | Evidence |
|---|---|---|
| S01 Important 1 — pre-A-01 operating authorization ambiguity | **RESOLVED** | S01 now blocks every operation before exact A-01 acceptance and approval binding: [S01:33](docs/specs/equity-os-s01-product-identity-operating-distribution-boundary.md:33), [S01:89](docs/specs/equity-os-s01-product-identity-operating-distribution-boundary.md:89), [S01:121](docs/specs/equity-os-s01-product-identity-operating-distribution-boundary.md:121). |
| S01 Important 2 — unresolved A-09 bypass | **RESOLVED** | Working label and approved name are separated; approved identity requires current decision ID, digest, A-09 acceptance, and typed authority: [S01:60](docs/specs/equity-os-s01-product-identity-operating-distribution-boundary.md:60), [S01:78](docs/specs/equity-os-s01-product-identity-operating-distribution-boundary.md:78), [S01:127](docs/specs/equity-os-s01-product-identity-operating-distribution-boundary.md:127). |
| S02 Important 1 — unbound S01 dependency | **RESOLVED** | The register now carries and freshly validates boundary ID, version, and content digest: [S02:50](docs/specs/equity-os-s02-source-rights-providers-consensus-policy.md:50), [S02:52](docs/specs/equity-os-s02-source-rights-providers-consensus-policy.md:52). |
| S02 Important 2 — circular source completeness | **RESOLVED** | An independently derived, content-bound `SourceUsageInventory` supplies the authoritative set and exact `U == R` validation: [S02:59](docs/specs/equity-os-s02-source-rights-providers-consensus-policy.md:59), [S02:105](docs/specs/equity-os-s02-source-rights-providers-consensus-policy.md:105), [S02:132](docs/specs/equity-os-s02-source-rights-providers-consensus-policy.md:132). |
| S02 Minor 1 — incomplete A-05 dimension matrix | **RESOLVED** | The operational gate and fixture enumerate every A-05 dimension: [S02:123](docs/specs/equity-os-s02-source-rights-providers-consensus-policy.md:123), [S02:134](docs/specs/equity-os-s02-source-rights-providers-consensus-policy.md:134). |
| S03 Important 1 — E-06 did not bind/enforce A-05 | **RESOLVED AS WRITTEN** | Exact S01/S02/right-record references, digests, A-05 `Accepted`, prerequisite proof, and activation sequencing are now required: [S03:58](docs/specs/equity-os-s03-external-tool-due-diligence.md:58), [S03:72](docs/specs/equity-os-s03-external-tool-due-diligence.md:72), [S03:164](docs/specs/equity-os-s03-external-tool-due-diligence.md:164). The new regression findings below still block S03. |

## New findings

### S01 — ISSUES_FOUND

#### Important

1. **The distribution gate is not content-bound to the boundary or activation request.**

   - **Location:** [S01:84](docs/specs/equity-os-s01-product-identity-operating-distribution-boundary.md:84), [S01:114](docs/specs/equity-os-s01-product-identity-operating-distribution-boundary.md:114)
   - **Load-bearing:** Yes

   `DistributionBoundaryGate` carries only `boundary_version`; it lacks the boundary ID/digest and the content-hashed boundary-change request or predicate reference. Consequently, the assertion that every gate is “current” is not mechanically provable from the interface, and a review or distribution decision can remain attached to different boundary content. Require exact boundary and activation-request IDs/digests and test boundary/request mutation.

#### Minor

1. **The declared `OperatingBoundary` scope and its closed schema disagree.**

   - **Location:** [S01:29](docs/specs/equity-os-s01-product-identity-operating-distribution-boundary.md:29), [S01:56](docs/specs/equity-os-s01-product-identity-operating-distribution-boundary.md:56), [S01:80](docs/specs/equity-os-s01-product-identity-operating-distribution-boundary.md:80)
   - **Load-bearing:** No

   Scope promises `exclusions` and `owner`, but neither exists in the closed field table, while unknown fields fail validation. Add typed fields or remove those promises.

### S02 — CLEAN

All r0 findings are resolved. Full regression review found no new Critical, Important, or Minor finding.

### S03 — ISSUES_FOUND

#### Important

1. **The whole-register authority hash makes E-06 activation self-invalidating.**

   - **Location:** [S03:72](docs/specs/equity-os-s03-external-tool-due-diligence.md:72), [S03:78](docs/specs/equity-os-s03-external-tool-due-diligence.md:78), [S03:164](docs/specs/equity-os-s03-external-tool-due-diligence.md:164)
   - **Load-bearing:** Yes

   The prerequisite proof must hash the exact current v2 file. The required `E-06: Deferred → Open/In progress` transition then changes that same file, immediately staling the proof, request, and predicate; line 164 re-blocks work on that staleness. A post-transition hash cannot satisfy the required pre-transition `TRUE` evaluation. Bind the proof to the authoritative A-05 row/projection rather than the whole mutable register, or define a non-circular transition/reconciliation mechanism and fixture.

2. **The proposed-use rights set is asserted, not independently derived.**

   - **Location:** [S03:57](docs/specs/equity-os-s03-external-tool-due-diligence.md:57), [S03:60](docs/specs/equity-os-s03-external-tool-due-diligence.md:60), [S03:74](docs/specs/equity-os-s03-external-tool-due-diligence.md:74)
   - **Load-bearing:** Yes

   The proposer supplies `proposed_use` and `source_rights_record_refs`, while the proof claims those references are exactly the required set. No independent proposed-use inventory or deterministic capability-to-source mapping defines the expected set, so an omitted provider/source can pass after recomputing the supplied hashes. Add a content-bound, independently derived proposed-use source inventory and require exact equality.

## Verdicts

| Scope | Verdict |
|---|---|
| S01 | **ISSUES_FOUND** — one load-bearing Important, one non-load-bearing Minor |
| S02 | **CLEAN** |
| S03 | **ISSUES_FOUND** — two load-bearing Important findings |
| Batch | **ISSUES_FOUND** — not approvable at r1 |
| Overall | **ISSUES_FOUND — no delegated artifact approval** |

`git diff --check` passed with exit `0`, and the three target paths are clean against current `HEAD`. No files were edited by this review.

A future `CLEAN` would constitute only approval under delegated goal authority. It would not imply the user’s personal approval or any product, legal, regulatory, provider-rights, security, distribution, purchase, credential, or adoption authority.