Verdict: COMPLIANT — narrow migration implementation and focused acceptance design.

⚠️ Cannot verify from diff: final corrected upgrade/producer PostgreSQL acceptance is still a coordinator gate. The inspected complete migration run has eleven passing shape cases and one pre-upgrade fixture failure (`vendor-acquisition-context-green.log:100`). Root has corrected that constructed queue witness from unsupported MISMATCH to the existing keyless UNMAPPED shape (`tests/fundamentals/test_vendor_acquisition_context.py:159`); read the fresh upgrade result before claiming verified mechanism completion. The outstanding vendor handoff XBRL input finding is a separate boundary and does not invalidate this correct narrow SQL delta. Actual release rights, full public dispatch/replay integration and source acceptance are outside this review.

Requirements:

- **Exact old acquisition branches preserved:** `migrations/0008_vendor_acquisition_context.sql:7` retains `stage <> 'ACQUISITION' OR extractor_version = ''` exactly from `migrations/0001_evidence.sql:229`. The new alternative adds only HTML/JSON, null package, null capture, nonempty extractor and nonnull lowercase 64-hex context (`0008_vendor_acquisition_context.sql:9`–`:15`), as approved at `docs/workstreams/data-foundation/plans/D1b-vendor-acquisition-repair.md:16`.
- **NULL fails closed for the new pinned branch:** explicit `extraction_context_sha256 IS NOT NULL` at `migrations/0008_vendor_acquisition_context.sql:14` makes missing context false rather than SQL UNKNOWN. Representation/extractor/stage remain NOT NULL under the existing table contract (`migrations/0001_evidence.sql:205`, `:213`, `:219`); package/capture nullity tests are explicit booleans. The old empty-extractor acquisition branch remains intentionally unchanged, including its original acceptance scope.
- **Independent extraction protections remain:** only `acquisition_attempts_check1` is replaced (`migrations/0008_vendor_acquisition_context.sql:3`). The separate actual-capture/nonempty-extractor EXTRACTION CHECK at `migrations/0001_evidence.sql:228`, contextual uniqueness at `migrations/0005_store_clock_cache_and_keyless_dimensions.sql:87`, foreign keys, store clocks, immutability and runtime role protections are untouched. No table, field, privilege, data backfill or source authority is added by the seventeen-line migration.
- **Required current-SQL behavioral RED exists:** the real runtime insert of both needed vendor shapes failed before implementation, after collection and PostgreSQL setup (`scratchpad/execution/data-foundation-resume-2026-10-13/vendor-acquisition-context-red.log:2`–`:4`). These are two genuine CHECK refusals, not missing APIs or infrastructure errors.
- **Relevant positive/refusal matrix is covered:** HTML/JSON preserve every supplied attempt field and an actual store-assigned time (`tests/fundamentals/test_vendor_acquisition_context.py:51`); legacy empty-extractor first-party acquisition remains admitted (`:63`). Broader package/capture forms, missing/malformed/uppercase context and nonempty XBRL acquisition are refused with unchanged attempt counts (`:78`). Capture-free or empty-extractor EXTRACTION remains refused (`:101`). The inspected root checkpoint confirms all eleven shape nodes passed; the only failed node is the separate upgrade fixture, not a constraint-shape regression.
- **Historical upgrade boundaries are explicit:** the isolated old database applies byte-copied 0001–0007 only (`tests/fundamentals/test_vendor_acquisition_context.py:112`), and the new copied directory adds through 0008 (`:139`). The upgrade assertion requires exactly one applied filename, 0008 (`:186`). The test retains real first-party ingestion and a real v1 run, complete run identity/manifest/results, complete attempt rows, queue item/membership rows, and actual by-ID v1 replay (`:143`, `:171`, `:188`, `:207`). Changing only the invalid constructed queue outcome to UNMAPPED does not weaken these before/after assertions or any financial oracle.
- **Producer source/identity gate remains separate:** the SQL admits a row shape rather than publication/rights. The approved guard requirement is preserved at `docs/workstreams/data-foundation/plans/D1b-vendor-acquisition-repair.md:23`; the vendor producer still re-proves actual publication, authority/schema/extractor before creating its real capture-free ACQUISITION (`vendor_input_proof.py:119`, `:140`) and preserves its pin/logical hash. Full producer persistence/ID/scope proof must be independently green after the migration; this review does not substitute the direct shape inserts for that acceptance.

Scope: exactly NEW `migrations/0008_vendor_acquisition_context.sql` and NEW `tests/fundamentals/test_vendor_acquisition_context.py`, with named existing SQL/schema/harness seams read only to check the old branch and historical boundary. Queue visibility remains separately reserved for migration 0009 (`docs/workstreams/data-foundation/plans/D1b-vendor-acquisition-repair.md:39`). Overall edit/commit scope remains the coordinator's responsibility because no Git package was supplied and Git was prohibited.

Invariants: no existing migration edit, source/credential/retained-input mutation, added privilege, backfill, clock rewrite or blanket rights waiver appears in the new migration. The test harness creates only guarded `eqos_test_*` databases and does not address the real application database (`tests/fundamentals/test_vendor_acquisition_context.py:113`, `:115`, `:128`). No reviewer PostgreSQL, tests, Git, Beads, network or product-file writes occurred; only this requested scratch report was written.

Unexpected extras: none. Issues — Critical: none. Important: none. Minor: none identified in this narrow implementation review.

Checks: inspected the entire approved acquisition repair plan, entire migration, complete 209-line test artifact, original acquisition/extraction CHECKs, contextual uniqueness, pre-code RED summary and the available guarded verification log. Did not rerun any suite. No migration-completion claim is made until the coordinator reads fresh corrected upgrade and producer results.

VERDICT: APPROVE — the independent 0008 delta is compliant; preserve the separately pending verification and vendor handoff/source gates.

## Coordinator verification and acceptance-file amendment

The fresh corrected matrix is **26 passed in 9.98s**: all twelve acquisition/context cases,
including real retained Apar v1 run/results/manifest/attempts/queue upgrade and by-ID replay,
and all fourteen historical publication-persistence cases. The vendor child's thirty-eight
producer cases also pass after the new constraint, including captured/capture-free same-logical
scope, complete stored payload reproof and concurrent shared-capture sections. Scoped Ruff lint
and format pass. This accepts the narrow migration, not full vendor-run/source acceptance.

Root explicitly authorizes resealing the acquisition test file after adding the separately
reviewed upgrade witness and fixing its constructed keyless queue outcome to UNMAPPED, as
required by unchanged migration 0006. The original two HTML/JSON positive test bodies and their
genuine pre-code CHECK failures remain unchanged; no original recorded outcome is retaken or
relabeled. The upgrade witness additionally seals an actual deciding attempt association and
compares every queue-item/input/membership row before and after migration. The original RED
file SHA-256 was `9dbec7312e9e027a1a57c509210d25370d889df3e06b8717d6898e9ca603ffbb`;
the final test SHA-256 is `16f81cdc7d443c736a0aa59f870ae7b43aa67e365ca010c2c07906d3985007ef`.
These additions are upgrade characterization, not extra claimed historical RED cases.
Migration SHA-256: `2a37734ae277916bd7216538cdc5cf033bd7cd5f440fe983302f74f3261e1333`.

Historical publication compatibility separately found a fixture boundary defect: its named
0006-to-0007 test applied the whole growing migration directory and then correctly reported an
unexpected 0008. Root copies exactly the existing 0001–0007 bytes into the private upgrade
directory. All twenty-five original assertion ASTs are preserved; one new assertion checks
the seven-file inventory. The exact applied-0007 list and all old row/pin assertions remain.
Its file SHA changes from `24466a57d7d5768f18883cce6ec9320f7c281b300213eaf741df0de1b0acbd4d`
to `0aa1ffb38fba6d03234d2e0f5b6aa4c515e0aac0622863718756a4a4339f4322`.
Root authorizes this fixture-only publication reseal separately, preserving the original
thirteen publication RED outcomes. Actual selected release bytes, old migrations, roles,
financial oracles and original runtime assertions are unchanged.
