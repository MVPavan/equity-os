# Independent S16–S18 Review

- **Reviewer:** `gpt-5.6-sol/xhigh`
- **Round:** `r0`
- **Review time:** `2026-08-13T02:34:26Z` UTC
- **Committed baseline:** `fa4cd53`
- **Mode:** Independent, read-only review
- **CLEAN semantics:** Delegated artifact approval under the activated goal only; never personal user approval. No CLEAN verdict is issued below.

## SHA-256 binding

All values are SHA-256 of the current on-disk file bytes.

| Role | Artifact | Reviewed scope | SHA-256 |
|---|---|---|---|
| Authority | `docs/goals/equity-os-blueprint-completion.md` | Lines 129–870 | `dabad7bfe3d2765a5ac9687376029d8587b4b2ac95bc03494155a974e5ddc67f` |
| Authority | `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` | Complete file | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| Authority | `docs/blueprint/funda-third-order-review-disposition-report.md` | Complete file | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| Target | `docs/specs/equity-os-s16-minimum-deterministic-compute.md` | Complete file | `b58228bdb6b17d85816ef1cf402bf2dd531b115e70d905d770ed4193692f557d` |
| Target | `docs/specs/equity-os-s17-entity-security-master-actions.md` | Complete file | `bb041e7324bb460bed28ab0901cfbbd879a8ae12e9218ead3e14a5278565fbe4` |
| Target | `docs/specs/equity-os-s18-universe-review-economics-throughput.md` | Complete file | `8479734d8678294892e377d03dac7cd4a03ae93f2b6cd12d069942eb9b4d225b` |

## S16 — ISSUES_FOUND

Authority ownership, exact register text, Open statuses, dependencies, Active-only classification, title/path, and lack of assigned provisional-amendment ownership are otherwise correct.

### Critical

None.

### Important

1. **Operator approval state does not encode all required one-to-one approvals.**
   **Load-bearing: YES.**
   `docs/specs/equity-os-s16-minimum-deterministic-compute.md:93` allows `APPROVED` with “a resolvable approval record,” but `:163` and `:164` establish distinct product-owner and domain-expert requirements. The goal’s one-record-per-requirement rule prohibits one generic record from satisfying both. The operator contract needs explicit requirement/record bindings and a conjunction rule before an operator becomes executable. As written, an operator could be marked approved with only one applicable human authority.

2. **Assigned G-1 evidence-package reproducibility is declared but not closed by an acceptance gate.**
   **Load-bearing: YES.**
   `docs/specs/equity-os-s16-minimum-deterministic-compute.md:38`, `:41`, and `:44` treat all three G-1 guarantees as obligations, while `:177`–`:194` test calculation replay and narrative hashing but never require exact reconstruction of the evidence package from registered source, fact, claim, and cutoff identifiers. `:200` names S10/S11 as interface suppliers but does not require their applicable reconstruction gate to pass. S16 must either narrow its owned G-1 slice explicitly or add a cross-spec acceptance dependency proving guarantee two.

### Minor

1. **The dormant stochastic path lacks a mechanical negative guard.**
   **Load-bearing: NO for the current MVP.**
   `docs/specs/equity-os-s16-minimum-deterministic-compute.md:86` admits `STOCHASTIC`, but `:88` does not require a non-null seed policy for that class and the interface has no distribution-check policy. Although `:139` excludes stochastic operators until amendment, `:181`–`:194` contain no test rejecting an approved stochastic definition before such an amendment. This becomes load-bearing if stochastic compute is proposed.

## S17 — ISSUES_FOUND

Authority ownership, exact register rows, Open statuses, dependencies, title/path, M-7/6.3 classification, Active-only classification, and amendment/deferred guards are correct.

### Critical

None.

### Important

1. **`EntityRelationship` cannot faithfully represent the required management-role relationship.**
   **Load-bearing: YES.**
   `docs/specs/equity-os-s17-entity-security-master-actions.md:93` fixes every relationship subject as `subject_company_id`, while `:95` includes `MANAGEMENT_ROLE_AT`, whose natural subject is a person and whose object is the company. No `Person` contract, participant-role union, or management-role attributes are defined. The fixture at `:197` therefore cannot prove a stable, directionally typed implementation of C-07 management roles. The endpoint model must support typed company/person/security participants and predicate-specific roles.

2. **Authority-bearing record states are not closed or transition-defined.**
   **Load-bearing: YES.**
   `docs/specs/equity-os-s17-entity-security-master-actions.md:81`, `:93`, and `:99` use `resolution_status`, approval/reconciliation status, and corporate-action `status` without enums, legal transitions, or an exact rule identifying which states are consumable. Yet `:124`, `:152`, `:156`, and `:192` depend on selected, accepted, unresolved, and conflicting state semantics. Implementations could disagree about when a mapping, relationship, or action becomes authoritative, defeating the fail-closed contract.

### Minor

None.

## S18 — ISSUES_FOUND

Authority ownership, exact register rows, Open statuses, dependencies, title/path, Active-only classification, G-2/G-3/M-8/6.1 coverage, human gate types, and amendment/deferred guards are otherwise correct.

### Critical

None.

### Important

1. **The C-18 capacity interface cannot mechanically bind or reproduce its acceptance decision.**
   **Load-bearing: YES.**
   `docs/specs/equity-os-s18-universe-review-economics-throughput.md:111`–`:115` defines `CapacityWindow` without A-12/A-13 policy IDs and versions, pre-agreed limits, evaluation-method version, typed `PASS|FAIL|BLOCKED` result, result digest, or approval-record bindings. The rule at `:139` requires evaluation against pre-agreed limits, but `:194` only reproduces measures and `:196` tests shortfall handling without defining the threshold evaluation object. The free-form `decision status` cannot prove accepted-or-mitigated C-18 completion.

### Minor

1. **G-4 counterbalancing is omitted rather than explicitly attempted or declined.**
   **Load-bearing: NO.**
   The disposition requires counterbalancing order where possible across companies at `docs/blueprint/funda-third-order-review-disposition-report.md:98`. S18’s G-4 summary at `docs/specs/equity-os-s18-universe-review-economics-throughput.md:42` and Phase 1 rules at `:129`–`:133` record practice/order effects as confounds but never require a counterbalancing attempt or an evidenced reason it is infeasible.

## Batch verdict

**ISSUES_FOUND**

The three specifications are consistent on primary ownership, authoritative register reproduction, activation classification, dependency direction, delegated-review boundaries, and the absence of assigned evidence-derived provisional amendments. No accidental Deferred activation or duplicate register ownership was found.

The batch is not approval-ready because:

- S16 does not close its operator approval conjunction or all claimed G-1 coverage.
- S17 lacks an implementable management-role endpoint model and closed authoritative state semantics.
- S18 lacks a content-bound, mechanically reproducible C-18 capacity evaluation contract.

## Overall verdict

**ISSUES_FOUND — delegated goal approval withheld for S16, S17, and S18 at r0.**