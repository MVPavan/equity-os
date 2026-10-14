# D1b vendor acquisition pin repair

> **Superseded 2026-10-14** by [D1b-cleanup.md](D1b-cleanup.md): the design this plan describes was deleted or simplified; kept as history.

Status: APPROVE, 2026-10-13, fresh independent Codex session (handoff run). Supplements vendor-run Task 2;
tracked under `eqos-u0u.19`. Root owns the additive SQL migration and its focused tests.

The guarded vendor persistence test reaches the actual append API and passes captured-source,
stored-generation, ID/idempotence and forgery checks, then fails at the capture-free FAILED
acquisition. Immutable `acquisition_attempts_check1` requires every ACQUISITION attempt to have
`extractor_version=''`. The approved logical-availability contract instead needs the actual
released vendor extractor version/content in its logical hash and coarse lookup. Root's current
result is 1 failed / 14 existing publication-persistence cases passed; this is product evidence,
not a setup failure. No existing row or migration may be rewritten.

## Bounded fix and acceptance

1. Root adds `migrations/0008_vendor_acquisition_context.sql`. Replace only the named acquisition
   extractor CHECK with its original permitted branches plus one narrow branch for ACQUISITION
   attempts with representation HTML/JSON, no filing package, no capture, a nonempty extractor
   version and a nonnull lowercase 64-hex `extraction_context_sha256`. Existing first-party
   acquisitions with empty extractor versions remain valid. The independent EXTRACTION CHECK
   still requires an actual capture and nonempty extractor; all FK, uniqueness, immutability,
   role and clock protections remain unchanged. No table, field, backfill or privilege is added.
2. The guard/recomposer still requires applicable actual publication, source authority, schema
   and released extractor before constructing that vendor attempt. SQL shape is not authority.
   Do not erase the pin/logical hash, relabel the failure as extraction or fabricate a capture.
3. Root writes focused `test_vendor_acquisition_context.py` before migration implementation.
   A genuine current-SQL RED inserts the required failed vendor acquisition shape through the
   existing runtime role. Positive coverage proves both HTML and JSON and legacy first-party
   acquisition shapes. Negative coverage refuses a vendor filing package, capture-bearing
   acquisition pin, missing/malformed logical hash and capture-free/empty-extractor EXTRACTION.
4. An isolated byte-identical 0001–0007 upgrade retains preexisting run, result, attempt and
   queue identities/payloads and v1 by-ID replay. After the additive migration, the exact vendor
   capture-free append succeeds with authoritative clocks, full attempt payload equality and
   the same logical scope as an earlier successful physical capture. IDs and actual request
   hashes remain distinct. No new body or source equivalence is asserted.
5. Run focused guarded PostgreSQL producer/schema/upgrade and legacy acquisition tests, scoped
   Ruff lint/format and relevant mypy; independently review this narrow constraint delta and
   the producer fix round before integration. Commit verified explicit files and progress-log
   each item. Queue visibility is reserved for separate migration 0009 and its reviewed plan.

Fail closed until migration and producer reproof both pass. This amendment supersedes the
earlier assumption that the existing acquisition CHECK admitted the required vendor pin; it
changes no source rights, financial assertion, old migration or full-stage acceptance gate.
