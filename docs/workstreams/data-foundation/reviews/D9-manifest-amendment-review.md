# D9 Task 8 frozen ledger Stage 5 manifest amendment review (r4)

VERDICT: APPROVE  
Reviewer: gpt-6.1-sol  
Date: 2026-10-18  
Reviewed payload SHA-256: `d33c46b76b57ebac5184ce0535507cb85361d6768c0620b2be1aba371b926500`

Approval covers only the r4 delta from `ea1d626` in the Stage 5 manifest and its structural checker. It does not establish Task 9 runtime acceptance.

**Per-claim verdicts**

1. **Record digest convention — APPROVE.** Pre-D9 `CaptureRecord.record_sha256` hashes canonical JSON without a newline; the store appends one LF when writing `record.json`. The r3 whole-file convention was incorrect. Fresh recomputation confirms all four replacement literals: each retained record equals its canonical JSON plus exactly one LF. The source-file hashes remain unchanged, and the restore literals agree with the corrected fixture digests. The checker requires `record_digests`, the correct `<label>-REC` source, and equality between the declared digest and fixture literal. [Manifest:72](/data/codes/equity-os/tests/fundamentals/fixtures/data_foundation/ledger_stage5_manifest.yaml:72), [checker:107](/data/codes/equity-os/tests/fundamentals/ledger_stage5_check.py:107)

2. **A-SCR extraction attempts, 1 → 4 — APPROVE.** Pre-D9 Stage 1 support ingests four sections of the same capture, and each ingest stores an EXTRACTION attempt. The attempts have distinct section-dependent extraction-context hashes. The expected count is four; the provenance’s uniqueness explanation needs the non-blocking correction below. [Manifest:395](/data/codes/equity-os/tests/fundamentals/fixtures/data_foundation/ledger_stage5_manifest.yaml:395), [section-dependent context:473](/data/codes/equity-os/src/fundamentals/evidence/vendor_screener.py:473)

3. **U-APQ interpretation values and counts — APPROVE.** Independent fixture enumeration gives 12 row groups with four history points each: 48 occurrences. Five selected groups give 20 INVALID interpretations; seven unselected groups give 28 UNMAPPED interpretations. Pre-D9 interpretation code leaves UNMAPPED values null and returns no value for unsupported precision. Removing `interpretations.value` from `cleared_before` corrects an unattainable non-null precondition. The replacement explicitly freezes the null baseline and exact counts. [Manifest:396](/data/codes/equity-os/tests/fundamentals/fixtures/data_foundation/ledger_stage5_manifest.yaml:396)

4. **Mapping sets — APPROVE.** Both X-Q4 and X-Q5 reference the 2026-01-31 taxonomy. Mapping set v5 supplies its entries and predates D9 (`ba1c068` is an ancestor of `da39b45`). The vendor entry files are shared with v4. Fresh inspection confirms that none of the three v5-only files contains a fixture blob hash, so this change adds no fixture qualification hold. [Manifest:66](/data/codes/equity-os/tests/fundamentals/fixtures/data_foundation/ledger_stage5_manifest.yaml:66), [v5 configuration:1](/data/codes/equity-os/config/mappings/v5.yaml:1)

5. **Extended provenance — ACCEPTED.** The header discloses the implementation-disagreement trigger, independent re-derivation, named pre-D9 sources, and the author’s declaration of no D9/e2e-code access. My independent checks support the amended expectations. The author’s access history remains a declaration, not something this review independently proves. [Manifest:5](/data/codes/equity-os/tests/fundamentals/fixtures/data_foundation/ledger_stage5_manifest.yaml:5)

**Issues — no acceptance blockers; two Minor provenance inaccuracies**

- **Minor — “no unique key” is inaccurate.** The provenance at [manifest:5](/data/codes/equity-os/tests/fundamentals/fixtures/data_foundation/ledger_stage5_manifest.yaml:5) omits migration 0005’s replacement unique constraint, which includes `extraction_context_sha256`. Four attempts remain attainable because the section participates in that digest. The precise explanation is “the replacement key distinguishes sections through extraction context.” [Migration:87](/data/codes/equity-os/migrations/0005_store_clock_cache_and_keyless_dimensions.sql:87)
- **Minor — “I16 selection” cites the wrong rule.** The same provenance line should cite Stage 1 **I18**, with I11 for mapping selection. I16 concerns the Q3 package kind. The explicit selected labels and seven unmapped rows independently support the counts, so this citation error does not undermine them. [Stage 1 manifest:119](/data/codes/equity-os/tests/fundamentals/fixtures/data_foundation/stage1_manifest.yaml:119)

**Rulings**

- **(a) U-APQ is acceptable for this amendment.** The supplied r1 ruling required a non-empty fixture to prove Upstox numeric-payload and `disclosure.anomalies` redaction. U-APQ retains that proof through populated occurrence values and removal of the anomalies path. It does **not** prove a non-null Upstox interpretation value becoming null. A-05’s requirement to clear every selected interpretation value remains binding through the unchanged inventory requirement; Screener and Tijori retain non-vacuous interpretation-value checks. This is an explicit evidence limitation, not an A-05 exemption. [Manifest:77](/data/codes/equity-os/tests/fundamentals/fixtures/data_foundation/ledger_stage5_manifest.yaml:77), [inventory:42](/data/codes/equity-os/docs/blueprint/amendments/2026-10-12-a05-derived-amounts.md:42)
- **(b) R15 independence is preserved within the previously accepted scoped exception.** A disagreement report can identify what needs rechecking without supplying the replacement oracle. These replacements are independently derivable from retained bytes and pre-D9 contracts. The e2e has no first commit yet, so the required approval-before-first-e2e-commit ordering remains attainable. This does not recertify r1’s original independence claim. [R15:341](/data/codes/equity-os/docs/workstreams/data-foundation/plans/D9.md:341)
- **(c) No unrelated changes were found.** Additional edits are consequential: backup/restore digest wording, the two restore digest literals, tombstone count semantics, provenance/date changes, and resetting approval metadata to PENDING.

**Verification and limits**

Fresh read-only checks confirmed the exact payload, all **26 source hashes**, four canonical record digests, Upstox counts, taxonomy references, mapping additions, the base structural checker, all **10 built-in mutations**, and **three focused r4 mutations**.

No PostgreSQL or e2e execution was performed. No files were edited; no `bd`, database, network, or state-changing Git commands were run. Opaque paths and `~/.secrets` were not accessed. Final Git status matched the initial changed-path inventory.
