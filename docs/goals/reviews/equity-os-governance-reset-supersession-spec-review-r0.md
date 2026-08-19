# Independent review

Exact draft SHA-256 verified: `520625602765e2219eb5117c0260b29ef188f5beb761d845be750c9cffa5919f`.

## Critical

### 1. The old goal remains operationally active

**Evidence:** The draft asserts that the old goal’s `ACTIVE`/`RUNNING` text loses effect when `CURRENT` selects the new contract (`docs/specs/2026-08-19-governance-reset-supersession.md:42`). But the old goal says it was activated through the goal tool and may run while its tool-controlled state is `RUNNING` (`docs/goals/equity-os-blueprint-completion.md:3`); its loop explicitly rereads goal-tool control state and requires cancellation or authority revocation to enter the cancelled state (`docs/goals/equity-os-blueprint-completion.md:1272`). Nothing establishes that a repository `CURRENT` file changes that external lifecycle state.

**Consequence:** The goal tool and future agents can still identify the exhaustive contract as active and resume its ledger/review loop despite the new pointer. Two mechanisms would claim current authority.

**Minimum correction:** Make the switch require a verified goal-tool cancellation/authority-revocation transition. Change the old goal’s visible header to `SUPERSEDED` with a pointer to the replacement; Git history preserves its original bytes, so byte-immutability is unnecessary for this file.

## Important

### 2. The archive manifest recreates the exhaustive inventory exercise

**Evidence:** The draft requires every historical artifact to be enumerated with byte length, SHA-256, Git blob ID, role, and preservation mode, then requires every entry and every archived review to be reread and verified (`docs/specs/2026-08-19-governance-reset-supersession.md:48`, `:64`). Archive closure and byte verification remain permanent success criteria (`docs/specs/2026-08-19-governance-reset-supersession.md:166`). This conflicts with the authoritative document strategy’s instruction to avoid review-document recursion (`docs/blueprint/funda-third-order-review-disposition-report.md:466`).

**Consequence:** Supersession becomes another comprehensive inventory, hashing, and verification project—the cycle the reset is meant to stop.

**Minimum correction:** Use the switch commit’s Git tree as the archive. Commit any genuinely untracked historical evidence once, unchanged. Record only the superseded goal path and switch commit identity; remove the per-file archive manifest and historical-review revalidation.

### 3. The “thin” index is a second 60-row ledger

**Evidence:** Every register row must be duplicated with status, normalized-row hash, dispositions, ownership, build artifact, evidence, approvals, blockers, and deferred state (`docs/specs/2026-08-19-governance-reset-supersession.md:77`). A validator must continuously recompute the projection. Yet the v2 register already declares itself the single operational source of truth for decisions, status, dependencies, evidence, and gates (`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md:21`).

**Consequence:** Every register transition creates synchronized updates, hashing, validation, and drift failures in a second representation. This is materially smaller than 213 rows but preserves the same governance-platform architecture.

**Minimum correction:** Keep status and Deferred/Rejected state only in the v2 register. The current index should contain only the current phase, relevant register IDs, active evidence/build references, blockers, and the next gate. Add later-phase rows only when that phase becomes current.

### 4. Per-phase hash manifests continue proof-system construction

**Evidence:** Each phase gate requires a content-hashed manifest mapping every §F clause to hashed evidence and approvals (`docs/specs/2026-08-19-governance-reset-supersession.md:113`); the top-level readiness record also carries hashed gate evidence (`docs/specs/2026-08-19-governance-reset-supersession.md:82`). The register already contains the exact phase-exit clauses (`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md:122`).

**Consequence:** Each phase accumulates another hash-rich evidence subsystem whose integrity must itself be implemented, reviewed, and maintained before product work can advance.

**Minimum correction:** At phase exit, create one small reviewed decision record mapping the applicable §F clauses to repository evidence paths and human decisions. Let its Git commit bind the bytes; do not hash every referenced item or duplicate the mapping in the current index.

### 5. The switch ceremony contains redundant review and transaction testing

**Evidence:** The draft requires review of both the exact specification and implementation candidate (`docs/specs/2026-08-19-governance-reset-supersession.md:107`), while the risk matrix separately requires an exact integrated HIGH review (`docs/specs/2026-08-19-governance-reset-supersession.md:131`). It also requires a temporary-worktree commit simulation and injected failure despite explicitly relying on normal Git atomicity (`docs/specs/2026-08-19-governance-reset-supersession.md:168`).

**Consequence:** Ambiguous duplicate review gates and bespoke switch testing can produce another review/fix cycle before any Phase 0A evidence work. The worktree test proves little beyond Git’s existing commit semantics.

**Minimum correction:** Count this review as the exact-spec review. Require one independent HIGH review of the final switch diff—no separate implementation-candidate review beyond it. Remove the temporary-worktree and failure-injection test; validate the staged paths and pointer, commit normally, then verify the committed state.

## Verdict

**ISSUES_FOUND**

Minimal target design:

1. Cancel/revoke the old goal in the goal tool and visibly mark it superseded.
2. Preserve historical material through Git history, without an archive manifest.
3. Use one small `CURRENT` contract naming the authorities, approved Architecture v2 evidence, current phase, relevant row IDs, blockers, and risk-based review policy.
4. Keep all 60 statuses and Deferred/Rejected safety solely in the v2 register.
5. Use one simple §F gate record per completed phase and one independent review of the final governance-switch diff.
