# r1 verdict: ISSUES_FOUND — S19 approved; S20/S21 approval withheld

## Review binding

| Field | Value |
|---|---|
| Model / effort | `gpt-5.6-sol` / `xhigh` |
| CLI session UUID | `019ff901-b0b2-7360-a0e8-f06df7bc20fb` |
| Review round | `r1` |
| UTC | `2026-08-13T02:49:00Z` |
| r0 baseline | `fa4cd53605914bf10376ad9b6264971711ff1f07` |
| Current HEAD | `41e1149e2e5b933dea86e2a29c623583fd5edece` |
| Target-only diff SHA-256 | `5dc0f8065bff668d70300762bfc8b06ad1b45add762c70e9d172c45413e5f2bf` |
| Diff integrity | `git diff --check` passed; no staged target diff |

The target blobs at r0 baseline and current HEAD are identical; the reviewed r0 fixes are the current working-tree target-only diff.

## SHA-256 binding

| Role | Artifact | SHA-256 |
|---|---|---|
| r0 report | `equity-os-s19-s21-r0.md` | `15e4c3043412fb48071394d87b17256831d8f4a485b72ab4842b8067917bb231` |
| Authority | `equity-os-blueprint-completion.md` | `dabad7bfe3d2765a5ac9687376029d8587b4b2ac95bc03494155a974e5ddc67f` |
| Authority | `funda-blueprint-implementation-decision-register-v2.md` | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| Authority | `funda-third-order-review-disposition-report.md` | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| Target S19 | `equity-os-s19-memory-store-promotion.md` | `17c50829c062dadf4a8b2edb6c0eb403c246d4966d5498a99f106fc4620e5da7` |
| Target S20 | `equity-os-s20-memory-benchmark-gbrain.md` | `87b8755b236d1bd0d377b52bfdb8be491dfc0b22e7cd0f93aed40a06466efb50` |
| Target S21 | `equity-os-s21-conditional-model-grade-compute.md` | `e0608b88e1582fa872065dec93cf47117ff0608c96ec8557568b042de1e8f1c1` |

## r0 finding dispositions

| r0 | r1 disposition | Evidence |
|---|---|---|
| 1. S19 deletion bypass | **ADDRESSED** | Deletion is now staged, CAS-protected, canonically hashed, separately promoted, atomically visible, and mechanically tested at [S19:67](docs/specs/equity-os-s19-memory-store-promotion.md:67), [S19:74](docs/specs/equity-os-s19-memory-store-promotion.md:74), [S19:84](docs/specs/equity-os-s19-memory-store-promotion.md:84), [S19:98](docs/specs/equity-os-s19-memory-store-promotion.md:98), and [S19:155](docs/specs/equity-os-s19-memory-store-promotion.md:155). |
| 2. S19 D-03 predicate/D-01 enforcement | **ADDRESSED** | The stable predicate, exact expression, live D-01 `Accepted` evidence, evaluation digest, activation-resolution binding, and negative fixtures are frozen at [S19:117](docs/specs/equity-os-s19-memory-store-promotion.md:117), [S19:125](docs/specs/equity-os-s19-memory-store-promotion.md:125), [S19:130](docs/specs/equity-os-s19-memory-store-promotion.md:130), and [S19:165](docs/specs/equity-os-s19-memory-store-promotion.md:165). |
| 3. S20 unauthorized D-04 dependency | **ADDRESSED** | D-01 readiness was removed; D-04 explicitly has no register dependency at [S20:184](docs/specs/equity-os-s20-memory-benchmark-gbrain.md:184) and [S20:230](docs/specs/equity-os-s20-memory-benchmark-gbrain.md:230). |
| 4. S20 controlled D-05 outcomes/reevaluation | **ADDRESSED** | Both conclusive outcomes now map to `Accepted`/`VERIFIED`, insufficient evidence cannot pass, exact-outcome product approval is mandatory, and D-02/D-05 reopening is controlled at [S20:152](docs/specs/equity-os-s20-memory-benchmark-gbrain.md:152), [S20:154](docs/specs/equity-os-s20-memory-benchmark-gbrain.md:154), and [S20:220](docs/specs/equity-os-s20-memory-benchmark-gbrain.md:220). |
| 5. S21 unimplementable C-08 predicate | **ADDRESSED** | The fixed predicate uses content-bound `STRING/EVIDENCE_JSON` status evidence rather than `REGISTER_STATUS`, with exact leaves and negative fixtures at [S21:126](docs/specs/equity-os-s21-conditional-model-grade-compute.md:126), [S21:132](docs/specs/equity-os-s21-conditional-model-grade-compute.md:132), and [S21:181](docs/specs/equity-os-s21-conditional-model-grade-compute.md:181). |
| 6. S21 method/adjustment approval | **ADDRESSED** | Method definitions and tie-out adjustments are versioned, digest-bound, separately approved, traced, and covered by rejection fixtures at [S21:64](docs/specs/equity-os-s21-conditional-model-grade-compute.md:64), [S21:72](docs/specs/equity-os-s21-conditional-model-grade-compute.md:72), [S21:153](docs/specs/equity-os-s21-conditional-model-grade-compute.md:153), and [S21:173](docs/specs/equity-os-s21-conditional-model-grade-compute.md:173). |

## New findings

No Critical or Minor findings.

1. **Important — S20 activation predicates remain partly prose-defined and lack mechanical acceptance coverage.**  
   **Location:** [S20:180](docs/specs/equity-os-s20-memory-benchmark-gbrain.md:180)  
   **Load-bearing:** `yes`

   D-02 and D-05 use ambiguous phrases such as “accepted/current dependency states,” “activated D-04,” and “current completed evidence” without freezing exact expression trees, metric IDs, types, sources, pointers, expected values, or digest preimages. D-04 names a pointer but not its exact comparison leaf. No acceptance fixture exercises `FALSE`, `UNKNOWN`, stale evidence, wrong dependency state, or resolution mismatch for these predicates. This conflicts with the goal’s requirement that activation predicates be data rather than prose at [goal:257](docs/goals/equity-os-blueprint-completion.md:257) and leaves all three Deferred activation transitions non-deterministic.

2. **Important — S20’s accepted-row reevaluation transition omits D-04.**  
   **Location:** [S20:160](docs/specs/equity-os-s20-memory-benchmark-gbrain.md:160)  
   **Load-bearing:** `yes`

   Reopening rules, approval gates, invariants, and tests cover only accepted D-02 and D-05 at [S20:176](docs/specs/equity-os-s20-memory-benchmark-gbrain.md:176), [S20:201](docs/specs/equity-os-s20-memory-benchmark-gbrain.md:201), and [S20:222](docs/specs/equity-os-s20-memory-benchmark-gbrain.md:222). A reevaluation involving a new GBrain revision or refreshed due-diligence package also advances accepted D-04 and therefore requires its own `REOPEN_ACCEPTED` resolution and `Accepted → Open` source reconciliation. Without that path, stale D-04 acceptance can be reused or its evidence replaced without the goal-mandated transition.

3. **Important — S21 does not bind assumption-set and sector-definition approvals at calculation admission.**  
   **Location:** [S21:78](docs/specs/equity-os-s21-conditional-model-grade-compute.md:78)  
   **Load-bearing:** `yes`

   The request carries only assumption-set and sector-definition IDs/versions, not their content digests or approval-record IDs. Their gates likewise omit exact digest binding at [S21:155](docs/specs/equity-os-s21-conditional-model-grade-compute.md:155). Recording digests and approvals later in the trace does not prove the correct approved preimage was selected before execution. Acceptance tests cover sector version failures but not wrong hash/scope/approval binding, and contain no negative approval fixtures for assumption sets at [S21:169](docs/specs/equity-os-s21-conditional-model-grade-compute.md:169). This leaves same-version content substitution and wrong approval selection insufficiently fail-closed.

## Per-spec verdicts

| Spec | Authority | Interface/fail-closed | Typed approval/acceptance | Verdict |
|---|---|---|---|---|
| S19 | Pass | Pass | Pass | **CLEAN — approved under delegated goal authority for SHA-256 `17c508…5da7` only** |
| S20 | Pass | Benchmark/adoption core passes; activation and D-04 reopening incomplete | Incomplete | **ISSUES_FOUND — approval withheld** |
| S21 | Pass | Method and adjustment fixes pass; assumption/sector admission remains incomplete | Incomplete | **ISSUES_FOUND — approval withheld** |

## Batch verdict

**ISSUES_FOUND.** All six r0 findings are addressed, but three new load-bearing Important findings block S20, S21, and their dependent cones.

## Overall verdict

**NOT CLEAN.** Delegated goal approval is granted only to the bound S19 artifact. It does not imply personal user approval or any analyst, domain, legal, rights, budget, capacity, production, distribution, security, provider, or other non-delegated authority. S20 and S21 require fixes and a fresh `r2`.