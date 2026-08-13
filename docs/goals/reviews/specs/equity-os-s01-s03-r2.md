# S01–S03 Independent Specification Review — r2

## Model / effort / session UUID / UTC

- **Model:** `gpt-5.6-sol`
- **Effort:** `xhigh`
- **Session UUID:** `019ff90f-7f0a-7573-9495-0102850e0f9f`
- **UTC:** `2026-08-13T03:03:36Z`
- **Current HEAD:** `ef2181d18fe036fd23e2bdffb809455b1049e2d0`
- **Method:** Fresh independent, read-only self-review; no delegation, Codex CLI, memory, web, or edits.
- **Scoped state:** S01 and S03 have uncommitted r1-fix changes; S02 matches HEAD.

## Hashes

| Artifact | SHA-256 |
|---|---|
| Goal authority, complete file | `dabad7bfe3d2765a5ac9687376029d8587b4b2ac95bc03494155a974e5ddc67f` |
| Goal authority, lines 129–870 | `1650313cacaf9a6ae26eac637639f5783dfec967a7189751540a9c27469f3a0e` |
| Decision register v2 | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| Disposition report | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| r0 report | `bb94f53f79f1b970e93e1c868197c8d04dd2c287ddf8898d0c3436e028482751` |
| r1 report | `187cac74ad7bc8d376253fd6e088f3a4645f1ad2a8efab8f6408b1eb7523ad40` |
| S01 current target | `1ad276cfa854b760a627b067be5aabe3b36019998a9ad5d1b52194c2dbd4af49` |
| S02 current target | `3d6ff743aee72beb8d734af25353970668dbb2a3fe8d4b336a9fd9af76d59211` |
| S03 current target | `6a957c67b96e2b96d10aad2a6808fab284f3ca2e2d742d20a3b6d49748794c8d` |
| r1-bound targets → current target diff | `c30dc7af4aa3b34ef46fee165f8800bd6bef022be73a8bedddb345566bdf2d09` |

## r2

Full regression covered r0, r1, goal lines 129–870, both operational authorities, all three current targets, and the complete r1-to-current target diff. `git diff --check` passed with exit `0`.

## Prior dispositions

All six r0 findings remain resolved under the current hashes.

| r1 finding | r2 disposition | Evidence |
|---|---|---|
| S01 Important — distribution gate not content-bound | **RESOLVED** | Boundary, request, predicate, gate, and approval bindings are now explicit and mutation-tested: [S01:85](docs/specs/equity-os-s01-product-identity-operating-distribution-boundary.md:85), [S01:91](docs/specs/equity-os-s01-product-identity-operating-distribution-boundary.md:91), [S01:145](docs/specs/equity-os-s01-product-identity-operating-distribution-boundary.md:145). |
| S01 Minor — scope/schema mismatch for exclusions and owner | **RESOLVED** | Both fields now occur in the closed `OperatingBoundary`: [S01:72](docs/specs/equity-os-s01-product-identity-operating-distribution-boundary.md:72). |
| S03 Important — whole-register hash self-invalidated E-06 activation | **RESOLVED** | The prerequisite now binds only the live A-05 row projection; E-06 transition reconciliation is separately required: [S03:82](docs/specs/equity-os-s03-external-tool-due-diligence.md:82), [S03:86](docs/specs/equity-os-s03-external-tool-due-diligence.md:86), [S03:178](docs/specs/equity-os-s03-external-tool-due-diligence.md:178). |
| S03 Important — proposed-use rights set was asserted | **PARTIALLY RESOLVED; REMAINS OPEN** | Source derivation is now independent of supplied rights references, but its capability roots remain proposer-controlled. `required_capabilities` and the mapping-reference set lack an independently derived authoritative inventory or exact-equality check. Omitting a provider-bearing capability and its map can therefore still produce internally consistent `P == rights refs`: [S03:58](docs/specs/equity-os-s03-external-tool-due-diligence.md:58), [S03:74](docs/specs/equity-os-s03-external-tool-due-diligence.md:74), [S03:76](docs/specs/equity-os-s03-external-tool-due-diligence.md:76). **Important; load-bearing.** |

## New findings

### S02 — Important, load-bearing

1. **`ConsensusDataDecision` cannot mechanically bind or represent its claimed terminal decision.**

   The declared record lacks an outcome/result field and a content digest, yet subsequent rules depend on exact outcomes `INCLUDED_LICENSED_AND_NECESSARY` and `EXCLUDED_FROM_MVP`. Approval records therefore cannot bind the exact necessity rationale, provider set, permitted uses, exclusions, and terminal outcome; those contents can change without mechanically staling C-13 approval.

   **Locations:** [S02:91](docs/specs/equity-os-s02-source-rights-providers-consensus-policy.md:91), [S02:93](docs/specs/equity-os-s02-source-rights-providers-consensus-policy.md:93), [S02:95](docs/specs/equity-os-s02-source-rights-providers-consensus-policy.md:95), [S02:139](docs/specs/equity-os-s02-source-rights-providers-consensus-policy.md:139).

   Require an explicit derived terminal result, canonical digest preimage, current content binding from every applicable approval, and mutation/staleness fixtures.

### S03 — Important, load-bearing

1. **The adoption-bearing due-diligence record is not content-addressed.**

   `ExternalToolDueDiligenceRecord` contains repository, license, pin, tests, security, provider, replacement, findings, approval IDs, and an adoption-capable result, but no version or aggregate content digest. The specification asserts that changes stale review and adoption evidence without defining a value that those records bind. A changed license, security finding, provider assumption, or replacement path can therefore remain attached to prior approval identifiers.

   **Locations:** [S03:95](docs/specs/equity-os-s03-external-tool-due-diligence.md:95), [S03:113](docs/specs/equity-os-s03-external-tool-due-diligence.md:113), [S03:133](docs/specs/equity-os-s03-external-tool-due-diligence.md:133), [S03:145](docs/specs/equity-os-s03-external-tool-due-diligence.md:145), [S03:165](docs/specs/equity-os-s03-external-tool-due-diligence.md:165).

   Require immutable version identity, a canonical `content_sha256`, exact approval/review bindings to that digest, and mutation fixtures proving stale decisions fail.

## Per-spec verdicts

| Spec | Verdict |
|---|---|
| S01 | **CLEAN** — both r1 findings resolved; full regression found no new finding |
| S02 | **ISSUES_FOUND** — one new load-bearing Important finding |
| S03 | **ISSUES_FOUND** — one unresolved r1 Important and one new load-bearing Important |
| Critical findings | **None** |
| Minor findings | **None** |

## Batch verdict

**ISSUES_FOUND — not approvable at r2.**

The S01 boundary binding is repaired, and S03 no longer has the whole-register transition cycle. The batch remains blocked by incomplete capability-root derivation, an unbound C-13 decision record, and an unbound external-tool due-diligence/adoption record.

## Overall verdict

**ISSUES_FOUND — no S01–S03 batch delegated artifact approval is granted.**

A future `CLEAN` grants approval only under delegated goal authority. It cannot imply personal user approval or legal, regulatory, provider-rights, security, distribution, purchase, credential, external-service, or adoption authority.