# Independent S04–S06 Review — r0

- **Reviewer:** `gpt-5.6-sol` / `xhigh`
- **UTC time:** `2026-08-13T02:36:15Z`
- **Committed baseline:** `fa4cd53605914bf10376ad9b6264971711ff1f07`
- **Baseline binding:** reviewed files match baseline; `git diff fa4cd53` exit `0`
- **Review mode:** fresh, independent, read-only

## SHA-256 binding

| Role | Artifact | SHA-256 |
|---|---|---|
| Authority | `docs/goals/equity-os-blueprint-completion.md` | `dabad7bfe3d2765a5ac9687376029d8587b4b2ac95bc03494155a974e5ddc67f` |
| Authority scope | Goal lines 129–870 | `1650313cacaf9a6ae26eac637639f5783dfec967a7189751540a9c27469f3a0e` |
| Authority | `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| Authority | `docs/blueprint/funda-third-order-review-disposition-report.md` | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| Target | `docs/specs/equity-os-s04-execution-trust-domain.md` | `b003df35a3af03b8e2bd3af60e254669ef584abb5b3f0d7ac45ff20c11e22f1a` |
| Target | `docs/specs/equity-os-s05-discovery-company-vertical-slice.md` | `ff97c32377fb93876262187b48bcb5fb4ad6464040a81f7eabdfb1328562b51f` |
| Target | `docs/specs/equity-os-s06-output-materiality-falsifiers.md` | `9454522096a062dd7e54fcc95f8c88c6a952176d62cc0d919057c5b8729cdf0a` |

## S04 — ISSUES_FOUND

Ownership, title, path, E-09 text/priority/status/dependency, T-4/6.7 coverage, dormant-only classification, and the deferred-activation guard otherwise match authority.

### Critical

| ID | Finding | File:line | Load-bearing |
|---|---|---|---|
| S04-C1 | `ExecutionAuthorization` is presented as the typed human authorization for executable requests, but it does not bind to the canonical approval record and immutable human resolution required by the goal: no `human_review_id`, `resolution_decision_id`, resolution digest, or explicit canonical approval-record reference exists. Internally supplied approver identity and authority-evidence fields could therefore be mistaken for authoritative approval. The request-level gate and tests do not close this gap. | `docs/specs/equity-os-s04-execution-trust-domain.md:122`, `:126`, `:130`, `:187`, `:203` | **Yes** |

### Important

| ID | Finding | File:line | Load-bearing |
|---|---|---|---|
| S04-I1 | Digest preimages are not implementable exactly. `authorization_sha256` is described as hashing the “complete authorization record,” which contains that hash, while intent, request, and outcome hashes likewise lack a canonical encoding and explicit digest-field exclusion. Hash-binding, replay, and audit tests cannot be deterministic under this contract. | `docs/specs/equity-os-s04-execution-trust-domain.md:115`, `:131`, `:135`, `:138`, `:141` | **Yes** |

### Minor

None.

## S05 — ISSUES_FOUND

Ownership, title, path, A-02/A-03/A-11 text/priority/status/dependencies, G-4/M-1/6.8 coverage, active-only classification, four-quarter design, and full-initiation deferral otherwise match authority.

### Critical

None.

### Important

| ID | Finding | File:line | Load-bearing |
|---|---|---|---|
| S05-I1 | The fail-closed invariant says an unresolved source conflict blocks acceptance, but the scenario permits acceptance after the conflict is merely “explicitly reviewed.” Review alone is not resolution and could bypass the stronger invariant. The pass condition must require an evidenced resolution or typed disposition that no longer leaves the conflict unresolved. | `docs/specs/equity-os-s05-discovery-company-vertical-slice.md:119`, `:120`, `:121`, `:212`, `:213`, `:214` | **Yes** |
| S05-I2 | Manifest, instrumentation-event, and package digest contracts do not define canonical serialization or exclusion of their own digest fields. Consequently the required byte-mutation/staleness test has no unique expected digest computation. | `docs/specs/equity-os-s05-discovery-company-vertical-slice.md:83`, `:92`, `:99`, `:117`, `:203` | **Yes** |

### Minor

None.

## S06 — ISSUES_FOUND

Ownership, title, path, A-04/A-10 text/priority/status/dependencies, G-1/G-5/R-4/6.2 coverage, active-only classification, provisional-stage guard, and post-baseline amendment requirement otherwise match authority.

### Critical

None.

### Important

| ID | Finding | File:line | Load-bearing |
|---|---|---|---|
| S06-I1 | Materiality coverage is circular and escapable. The output requires decisions only for claims “requiring evaluation,” while the invariant requires decisions only for claims already known to be material. No rule proves that every potentially material claim was evaluated, so an omitted decision can evade A-10 validation and evidence requirements. | `docs/specs/equity-os-s06-output-materiality-falsifiers.md:111`, `:159`, `:160`, `:190`, `:191`, `:241` | **Yes** |
| S06-I2 | The spec invents a waiver allowing a thesis impact to contain no observable falsifier when an analyst separately approves “none applicable.” A-04 and R-4 provide no such exception, and the approval inventory defines no matching approval type, authority, evidence contract, or acceptance test for it. | `docs/specs/equity-os-s06-output-materiality-falsifiers.md:205`, `:206`, `:207`, `:222`, `:232` | **Yes** |
| S06-I3 | The final-freeze guard requires A-03 and the amendment but omits A-11. This conflicts with the authoritative disposition sequence and S05’s binding sequence, both of which place bootstrap-thesis approval before final A-04 freeze. As written, S06 can approve `FINAL_V1` before the thesis and its falsifiers exist. | `docs/specs/equity-os-s06-output-materiality-falsifiers.md:53`, `:55`, `:61`, `:267`, `:288`; `docs/specs/equity-os-s05-discovery-company-vertical-slice.md:231`, `:233` | **Yes** |
| S06-I4 | `artifact_sha256` is a field inside the output but is defined as the hash of the exact output bytes, making the digest self-referential. Policy, decision, falsifier, and memory-draft hashes likewise lack canonical preimages and digest-field exclusions. Required mutation and stale-proof tests are therefore underspecified. | `docs/specs/equity-os-s06-output-materiality-falsifiers.md:113`, `:136`, `:157`, `:174`, `:184`, `:261` | **Yes** |

### Minor

None.

## Batch verdict

**ISSUES_FOUND**

The batch is internally consistent on ownership, register status, activation classification, disposition assignment, typed approval vocabulary, and separation of delegated review from personal user approval. It is not approvable because:

1. All three specs lack exact, non-self-referential content-digest contracts.
2. S04 does not securely connect executable-request authorization to the canonical human-resolution authority.
3. S05 contains a fail-open conflict-review path.
4. S06 permits unevaluated materiality and an unauthorized no-falsifier exception.
5. S05 and S06 disagree on whether A-11 must precede final A-04 freeze.

## Overall verdict

**ISSUES_FOUND — r0 blocks delegated goal approval for S04, S05, S06, and the S04–S06 batch.**

No personal user approval is asserted or implied.