# D9 Task 8 frozen ledger Stage 5 manifest review (round 3)

VERDICT: APPROVE  
Reviewer: gpt-6.1-sol  
Date: 2026-10-17  
Reviewed payload SHA-256: `e094ce2628c15f7de46e0b40ea519185e12c4be28da05a1fca0cbb5152ccb328`

The independently recomputed payload matches. This approval covers the D9 Task 8 frozen Stage 5 manifest: fixture bindings, setup, eligibility, probes, purge and redaction, preservation, recovery, backup, re-fetch, five-run replay inventory and both restores. It does **not** establish Task 9 runtime acceptance.

**Residual verdicts**

- **Finding 3 — FIXED.** Intake now precedes RUN-L, which replaces RUN-L0 as the batch’s same-entity run. This removes the evidence-free execution that failed currency resolution. All five stored runs have expectations at all five replay checkpoints. [Manifest:42](/data/codes/equity-os/tests/fundamentals/fixtures/data_foundation/ledger_stage5_manifest.yaml:42), [manifest:486](/data/codes/equity-os/tests/fundamentals/fixtures/data_foundation/ledger_stage5_manifest.yaml:486)
- **Finding 10 — FIXED.** Required nested content, preservation capture references, purge-run declarations, record/probe invocation relationships, COMPLETE-event run relationships and complete crash-state coverage now address the reported residuals. [Checker:64](/data/codes/equity-os/tests/fundamentals/ledger_stage5_check.py:64), [checker:121](/data/codes/equity-os/tests/fundamentals/ledger_stage5_check.py:121), [checker:189](/data/codes/equity-os/tests/fundamentals/ledger_stage5_check.py:189)

Findings **1, 2, 4–9, 11 and 12 remain FIXED** within this re-review’s scope. No regressions or new acceptance-blocking findings were identified.

**Rulings on questions 1–5**

1. **ADD after registration is accepted.** R2 did not require ADD first. With no subsequent REMOVE, `capture_covered` covers L-X under the revised ordering, consistent with plan case C3. [Migration:110](/data/codes/equity-os/migrations/0027_retention_classes.sql:110), [plan:597](/data/codes/equity-os/docs/workstreams/data-foundation/plans/D9.md:597)

2. **RUN-L is acceptable as the batch run.** The batch trigger requires a same-entity run and matching listing identity; it imposes no run-status requirement. `execute_run` publishes its computed status, including INCOMPLETE. Unlike RUN-L0, RUN-L follows evidence intake. This is a source-based feasibility conclusion; PostgreSQL execution was not performed. [Batch trigger:100](/data/codes/equity-os/migrations/0025_coverage_batches.sql:100), [execute_run:133](/data/codes/equity-os/src/fundamentals/compare/run.py:133)

3. **Omitting frozen `retention_limited` rows is accepted for Task 8.** Its inventory does not require those rows; the manifest freezes the relevant VENDOR classes and eligibility. C3 separately requires `retention_limited` coverage. Do not interpret this ruling as validating W-CSV’s membership in that view. [Plan:542](/data/codes/equity-os/docs/workstreams/data-foundation/plans/D9.md:542), [migration:128](/data/codes/equity-os/migrations/0027_retention_classes.sql:128)

4. **The five replay checkpoints are sufficient.** D0 and D2 remain preservation checkpoints; neither needs an additional direct replay for this approval. Every declared run has all five required replay expectations. [Manifest:397](/data/codes/equity-os/tests/fundamentals/fixtures/data_foundation/ledger_stage5_manifest.yaml:397), [checker:207](/data/codes/equity-os/tests/fundamentals/ledger_stage5_check.py:207)

5. **Pattern-based resolution is accepted with a non-blocking limitation.** A fresh mutation adding `Q9` to preservation `capture_of` passes. Thus the checker does not universally reject arbitrary malformed reference names. The current payload uses the declared naming forms; broader field-aware validation is a refinement. [Checker:75](/data/codes/equity-os/tests/fundamentals/ledger_stage5_check.py:75)

**Verification and notes**

Fresh checks verified all **26 source hashes**, the derived M-Q4 hash, Python syntax, the base checker, all **10 built-in mutations**, and all **39 mutations** in `mutate.py`. The checker contains **51 required paths**, rather than the reported 53. `test_frozen_manifests.py` remains 798 lines.

The disclosed r3 provenance is accepted under the earlier scoped exception and reviewer clarifications. This approval does not recertify r1’s original independence claim.

The author’s reported 92-pass/one-approval-failure run was not rerun. No files were edited; no `bd`, database, network or state-changing Git commands were run. Opaque paths and `~/.secrets` were not accessed. Final Git status showed the same changed paths as at review start.
