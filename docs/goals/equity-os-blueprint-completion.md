# Equity-OS Blueprint Completion Goal

## Supersession and activation

This document supersedes the former process and gating contract at this canonical path. Git history preserves the former 5,918-line contract and all tracked historical material in the switch commit's parent; historical artifacts remain evidence at their existing paths, not current readiness prerequisites unless this contract or the v2 decision register makes one relevant. Any genuinely untracked historical evidence needed for audit may be added unchanged once in that commit; no historical artifact is reread merely to complete the switch.

This working-tree replacement is a governance-switch candidate only. It becomes the current contract only through the normal, narrowly staged switch commit. A failed commit makes no switch. A later defect blocks affected work and is corrected by a later visible commit; history is not rewritten.

## Continuing authority

The authority hierarchy is:

1. [`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md`](../blueprint/funda-blueprint-implementation-decision-register-v2.md) is the sole operational source for register decisions, statuses, dependencies, required evidence, Deferred and Rejected controls, and phase gates. Its wording wins over this contract on any conflict; affected work is blocked until a normal corrective commit updates this index.
2. [`docs/blueprint/funda-third-order-review-disposition-report.md`](../blueprint/funda-third-order-review-disposition-report.md) is the v2 interpretation and audit trail. It explains rationale and does not override v2.
3. Approved Architecture v2 remains the architecture of record: [`docs/goals/architecture/equity-os-architecture-of-record-v2.html`](architecture/equity-os-architecture-of-record-v2.html), its [companion brief](architecture/architecture-brief-v2.md), and its [independent CLEAN review](architecture/equity-os-architecture-of-record-v2-review-r3.md). The current-user Architecture v2 approval is recorded in Bead `eqos-jce`.

All product scope governed by v2 remains intact, including the first-release work and later conditional capabilities. No Deferred or Rejected item is active merely because another dependency is satisfied: it requires v2 and every required human authority to activate it explicitly. This contract neither changes provider, tool, runtime, nor model bindings.

## Current-phase index

| Field | Content |
|---|---|
| `phase` | `0A` — product, sources, measurement, and operating boundary. |
| `relevant_register_ids` | `A-01`, `A-02`, `A-03`, `A-04`, `A-05`, `A-06`, `A-07`, `A-08`, `A-09`, `A-10`, `A-11`, `A-12`, `A-13`. |
| `evidence_build_references` | [`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md`](../blueprint/funda-blueprint-implementation-decision-register-v2.md); [`docs/goals/architecture/equity-os-architecture-of-record-v2.html`](architecture/equity-os-architecture-of-record-v2.html); [`docs/goals/architecture/architecture-brief-v2.md`](architecture/architecture-brief-v2.md); [`docs/goals/architecture/equity-os-architecture-of-record-v2-review-r3.md`](architecture/equity-os-architecture-of-record-v2-review-r3.md). |
| `human_decision_references` | [`docs/specs/2026-08-19-governance-reset-supersession.md`](../specs/2026-08-19-governance-reset-supersession.md); Bead `eqos-jce` (Architecture v2 approval); Bead `eqos-9x8` (three-tier sourcing direction). |
| `blockers` | The normal governance-switch commit is pending. Phase 0A evidence and decisions for the operating boundary, discovery slice, manual baseline and bootstrap thesis, provisional output contract, source rights, filing coverage, budgets, golden set, product identity, materiality, capacity, and success metrics are not yet established as v2-required evidence. |
| `next_gate` | [v2 decision register §F, Phase 0A exit gate](../blueprint/funda-blueprint-implementation-decision-register-v2.md). |

## Readiness and exit discipline

Phase 0A evidence work may proceed when its relevant v2 prerequisites and required human or rights decisions are satisfied. Historical process closure and dormant future-method work are not universal prerequisites.

Phase 0.5 product implementation requires the complete v2 Phase 0A exit gate, approved relevant build contracts, and continuing Architecture v2 approval. Phase 1 and later require every preceding applicable v2 §F gate, applicable row dependencies, and explicit activation authority. Dependency satisfaction alone never activates Deferred scope.

At every phase exit, create one small reviewed decision record that maps each applicable v2 §F clause to repository evidence paths and human decisions without copying register statuses or gate prose. Its Git commit binds the record bytes. Missing, conflicting, or stale evidence blocks exit; no pass is inferred.

## Review policy

Classify work by its highest matching risk before acceptance.

| Risk | Scope | Required review |
|---|---|---|
| `LOW` | Reversible work with no product behavior, authority, trust-boundary, persistence, or external-effect change. | Author self-check and relevant tests. |
| `STANDARD` | Product behavior, persisted records, or cross-component interfaces not meeting `HIGH`. | Author self-check and relevant tests, plus one independent integrated review at slice or release acceptance. |
| `HIGH` | Governance or authority; architecture; distribution or execution boundaries; security, rights, external integrations, canonical schemas or migrations; human approval or memory promotion; phase gates; production release. | One independent review of exact integrated bytes, plus every required human authority. |

The approved specification's independent review is its review evidence. Correcting its findings does not create another specification-review round. The final governance-switch diff receives exactly one independent `HIGH` review of its exact integrated bytes. Architecture v2 is reopened only for a proposed change to its component boundaries, trust model, CAN/CANNOT contract, or first-release/later split. Review evidence never supplies product-owner, vocabulary-domain, legal, rights, analyst, security-exception, or production authority.

## Retained authority semantics

**RC-2 — multi-artifact approval.** A combined approval may cover only a declared complete sorted set of specs or build artifacts, identified by ID and canonical path, with the referenced Git commit binding exact bytes. The approved set must equal the declared scope; no subset, superset, duplicate, inferred, transitive, changed-byte, component-local, or duplicate per-spec approval qualifies.

**RC-3 — vocabulary domain authority.** Metric-registry and claim-predicate-registry additions require distinct typed `DOMAIN_EXPERT_ACCEPTANCE` from the competent Vocabulary authority. Process approval does not approve an entry; each addition still needs the entry-level approval required by S13.

**RC-4 — product identity authority.** A-09 requires trademark or legal review and a separate typed `PRODUCT_OWNER_DECISION` for the exact product identity. Neither satisfies the other; architecture, governance, or repository-operation approval satisfies neither.
