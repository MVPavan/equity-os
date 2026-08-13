# Independent S04–S06 Review — r1

**Overall verdict: ISSUES_FOUND — delegated goal approval is blocked.**

## Review identity and binding

- **Reviewer:** `gpt-5.6-sol` / `xhigh`
- **CLI session UUID:** `019ff901-b0a3-7871-9450-667c188f6f89`
- **Review round:** `r1`
- **UTC:** `2026-08-13T02:51:12Z`
- **Bound commit:** `f9553b68bc3dda0dce3994ae12ea33ba093a0b45`
- **Mode:** independent, read-only; no delegation, Codex CLI invocation, memory, web, or edits
- **Terminal target state:** target worktree diff empty; `git diff --check` exit `0`
- **Target-only r0-fix patch SHA-256:** `eb780c6ffcf62972bfd984f3dd544045f88cfee647898181fee064d622f9815d`

## SHA-256 binding

| Role | Artifact | SHA-256 |
|---|---|---|
| Authority | `docs/goals/equity-os-blueprint-completion.md` | `dabad7bfe3d2765a5ac9687376029d8587b4b2ac95bc03494155a974e5ddc67f` |
| Authority scope | Goal lines 129–870 | `1650313cacaf9a6ae26eac637639f5783dfec967a7189751540a9c27469f3a0e` |
| Authority | `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| Authority | `docs/blueprint/funda-third-order-review-disposition-report.md` | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| Prior review | `docs/goals/reviews/specs/equity-os-s04-s06-r0.md` | `4dc64c2fbf14acbab0d17886120b87f2ef7b32cc86f2ffbd4e0fc8f58c7854cf` |
| Target | `docs/specs/equity-os-s04-execution-trust-domain.md` | `90b55faa545aac3eaec46220b7229dfdb562746ab4b83983ba2949e8dc286990` |
| Target | `docs/specs/equity-os-s05-discovery-company-vertical-slice.md` | `781ad526e08e26caac23059c3187979892aa087e5e03cef13db2837310668817` |
| Target | `docs/specs/equity-os-s06-output-materiality-falsifiers.md` | `da152869d1f63e0155f60867c663c8382e60345ee261f95350baadc72d7b87e8` |

## r0 finding dispositions

| r0 finding | r1 disposition | Evidence |
|---|---|---|
| S04-C1 | **RESOLVED** | Authorization now resolves through the canonical approval record, human-review entry, immutable resolution, and recomputed resolution digest; stale and mismatched authority is rejected. |
| S04-I1 | **RESOLVED** | All four record hashes now use the governing canonical-JSON preimage rule, excluding only their own digest fields, with semantic-mutation tests. |
| S05-I1 | **RESOLVED** | Review alone no longer resolves a conflict. Acceptance requires evidenced `RESOLVED` or fully evidenced `EXCLUDED_FROM_BASELINE`; `OPEN` and review-only cases block. |
| S05-I2 | **RESOLVED** | Manifest, instrumentation-event, package, conflict-disposition, and thesis digests now have canonical, non-self-referential preimages and mutation tests. |
| S06-I1 | **RESOLVED AS WRITTEN** | A closed candidate inventory, exact ID-set equality, one decision per candidate, exhaustive dimensions, and omission tests remove the original circular “claims requiring evaluation” escape. A distinct content-binding defect remains below. |
| S06-I2 | **RESOLVED** | The unauthorized no-falsifier waiver was removed from invariants, approvals, and tests. |
| S06-I3 | **RESOLVED** | A-11 approval/version/hash now precedes final A-04 freeze throughout the stage guard, acceptance gate, tests, and dependency sequence. |
| S06-I4 | **RESOLVED** | Output, inventory, policy, decision, falsifier, and memory-draft hashes now use explicit canonical preimages excluding their own digest field. |

## New findings

### S04-C2 — Critical

- **File:line:** [docs/specs/equity-os-s04-execution-trust-domain.md:79](docs/specs/equity-os-s04-execution-trust-domain.md:79), lines 139–169, 184–196, 221, 241–254
- **Load-bearing:** **Yes**

The canonical approval chain is still not bound one-to-one to the immutable executable request. `ExecutionAuthorization` binds the intent, limits, and account scope; `ExecutionRequest` is created afterward and binds the authorization only in the request-to-authorization direction. Neither the authorization nor its human resolution binds `request_id`, `request_sha256`, or the idempotency key, and no single-use/consumption rule exists.

Consequently, one approved authorization can support multiple request hashes using different idempotency keys. The at-most-once test covers replay of one key only, so it does not detect authorization reuse. This contradicts the spec’s own requirement that human approval be bound to the immutable execution request and can permit duplicate external actions.

### S04-I2 — Important

- **File:line:** [docs/specs/equity-os-s04-execution-trust-domain.md:33](docs/specs/equity-os-s04-execution-trust-domain.md:33), lines 50–52, 163–170, 216–221, 235–262, 270–271
- **Load-bearing:** **Yes**

Current regulatory, legal, credential-access, external-service, and production approvals are declared fail-closed gates, but the submission interface re-resolves only the per-request execution approval. No typed submission dependency or acceptance test rejects a request after one of those environment-level approvals expires, is revoked, or becomes stale.

Activation-time E-08 evidence is insufficient for later execution-connected use. The generic phrase “unhealthy dependency” does not define the exact approval IDs, digests, scopes, or runtime check needed to enforce these gates.

### S05-I3 — Important

- **File:line:** [docs/specs/equity-os-s05-discovery-company-vertical-slice.md:138](docs/specs/equity-os-s05-discovery-company-vertical-slice.md:138), lines 138–152, 202–218, 246–248
- **Load-bearing:** **Yes**

The r0 fix introduced a distinct, current `ANALYST_ACCEPTANCE` for every source-conflict disposition, but the typed human-approval gate inventory does not declare that dynamic obligation. It lists only selection, baseline, and thesis approval.

Under the goal’s one-record-per-requirement rule, baseline acceptance cannot also satisfy a conflict-disposition requirement. The interface and acceptance test require the missing approval while the approval inventory omits it, preventing a complete, unambiguous approval inventory.

### S06-I5 — Important

- **File:line:** [docs/specs/equity-os-s06-output-materiality-falsifiers.md:115](docs/specs/equity-os-s06-output-materiality-falsifiers.md:115), lines 138–157, 189–204, 302–319
- **Load-bearing:** **Yes**

Materiality closure is exact only by `claim_id`. The inventory binds exact claim content and has its own digest, but `MaterialityDecision` binds neither the candidate-inventory ID/hash nor an immutable claim-content digest.

A claim’s content can therefore change while retaining its ID and an earlier materiality decision; the set-equality tests still pass. Rehashing and reapproving the output protects artifact provenance but does not prove the policy was reevaluated against the changed claim. The decision must bind the exact inventory and claim content, with a same-ID content-mutation rejection test.

## Per-spec verdicts

| Spec | Verdict | Basis |
|---|---|---|
| S04 | **ISSUES_FOUND** | r0 findings are fixed, but executable approval is not bound one-to-one to the request, and current environment approvals are not precisely enforced at submission. |
| S05 | **ISSUES_FOUND** | r0 findings are fixed, but the source-conflict approval introduced by the fix is absent from the typed approval inventory. |
| S06 | **ISSUES_FOUND** | r0 findings are fixed, but materiality decisions are not content-bound to the exact candidate claim they classify. |

## Batch verdict

**ISSUES_FOUND**

Authority ownership, register text/status/dependencies, activation classification, four-quarter sequencing, A-11 ordering, canonical digest rules, no-falsifier behavior, and the original fail-closed corrections now align. The batch still fails full interface and typed-approval closure because all four new findings are load-bearing.

## Overall verdict

**ISSUES_FOUND — r1 blocks delegated goal approval for S04, S05, S06, and the S04–S06 batch.**

No `DELEGATED_ARTIFACT_APPROVAL` is granted. A future `CLEAN` verdict would mean delegated goal approval only; it would not constitute or imply personal user approval or any analyst, product, legal, regulatory, security, production, credential, external-service, or execution authority.