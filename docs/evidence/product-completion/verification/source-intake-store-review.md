Verdict: **APPROVE — scoped clock fix and regression, both spec and quality.**

1. **ADDRESSED — Important orphan-recovery rollback finding, shared by both reviews.**  
   [source_intake_store.py:158](../../../../src/fundamentals/store/source_intake_store.py:158) retains the preceding actual sample. Every subsequent sample must be nondecreasing, preserving the initial LOCAL_READ completion floor transitively. Recovery completion, observation and registration use this guard at [line 220](../../../../src/fundamentals/store/source_intake_store.py:220). There is no clamping or backdating; the reported rollback refuses before receipt publication.

   [test_source_intake_store.py:290](../../../../tests/fundamentals/test_source_intake_store.py:290) creates a real installed-only orphan through public staging, restarts the store, exercises `10 → 11/12 → 1/2 → 3/4`, and asserts refusal, absent receipt, unchanged installation and retained original bytes.

2. **ADDRESSED incidentally — Minor intermediate reopening warning.**  
   The future-ceiling sample now updates the same retained clock state at [line 193](../../../../src/fundamentals/store/source_intake_store.py:193); the subsequent ceiling at [line 205](../../../../src/fundamentals/store/source_intake_store.py:205) rejects regression against it. No additional clock sample, public clock parameter or importer was introduced. The [public scratch probe:25](../../../../scratchpad/execution/product-gold-second-batch/intake-task1-fix-r1-reopen-probe.py:25) verifies `11/12/11/13` refusal, immutable receipt bytes and subsequent forward reopening.

**Verification accepted:** The [RED log:49](../../../../scratchpad/execution/product-gold-second-batch/intake-task1-fix-r1-red.log:49) shows behavioral failure—`DID NOT RAISE SourceRegistrationError`—rather than an import or syntax failure. The [GREEN log:132](../../../../scratchpad/execution/product-gold-second-batch/intake-task1-fix-r1-green.log:132) records **75 passes, exit 0**, including unchanged forward recovery and identical-receipt tests; [line 110](../../../../scratchpad/execution/product-gold-second-batch/intake-task1-fix-r1-green.log:110) records **148 fsync boundaries and 30 uncertain receipts reopened**. Static checks passed. No suites were repeated.

**Preservation verified:** Live protected files match the reviewed r0 snapshot byte-for-byte; both changed files match r1. Context, registration schema, SnapshotStore and wire/hash construction remain unchanged. The [preservation evidence:1](../../../../scratchpad/execution/product-gold-second-batch/intake-task1-fix-r1-preservation.log:1) agrees with those comparisons. Read-only Git status was inspected.

**New Important delta issues: none.**

**Acceptance boundary:** This approves the bounded fix only. Actual private-source proof and native pipeline release remain uncertified; Task 2 and the final integrated gate remain pending. The earlier 223-test shared gate and rename-mock adaptation are separate evidence, as recorded in the [fix report:5](../../../../scratchpad/execution/product-gold-second-batch/intake-task1-fix-r1-report.log:5).