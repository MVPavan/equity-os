# D1b queue mechanism acceptance checkpoint

Status: APPROVE, 2026-10-13, bounded `eqos-u0u.17` mechanism and `eqos-u0u.26` schema fixture.
Full Task 6 public run integration, Task 7 authentication producer and Stage 1 remain open.

Fresh independent [R2](D1b-queue-review-r2.md) found the remaining vendor-representation guard
and missing required verification. [R3](D1b-queue-review-r3.md) approves every Q1–Q4/R2 finding:
durable immutable visibility; full same-connection accepted-receipt verification and proof
clocks; active caller transactions before SQL; exact source/surface/representation routing;
concurrent complete MVCC captures; and actual retained v1 by-ID replay across 0009. Invalid
proofs stay open with explicit failures. All old digest/locking/reuse/predecessor/origin rules
are retained. Actual external/owner authentication is not inferred from schema fixtures.

Root's isolated final queue matrix is **40 passed in 10.32s**. Main's queue/full-schema/existing
vendor SQL matrix is **62 passed in 10.69s**. Scoped Ruff lint/format and strict mypy pass.
The full-schema fixture correctly requires all42 populated tables and extends the protected
SELECT-only table set; it creates a snapshot through the approved runtime function under
REPEATABLE READ. Old explicit pre-0009 upgrade helper calls remain compatible. Fresh independent
[fixture review](D1b-queue-schema-fixture-review.md) APPROVE confirms all original assertions
and the unchanged main schema acceptance test bytes. No SQL privilege is widened.

Earlier verification remains historical: first27 PASS/5 missing-fixture setup errors, then32
PASS; main first collected none because two guessed test paths did not exist, then51 PASS/
2 old inventory expectations failed. These are not behavioral RED or current acceptance.
No production fix was inferred from those fixture failures; the current positive checks above
prove the required new table and stronger permissions rather than excluding them from tests.

## Acceptance-file amendments

Four original existing-helper PG regressions remain genuine RED, covering late membership/
fake closure and autocommit/forged provenance. Root authorizes resealing their two files only
for disclosed additive source-component/proof/representation verification, preserving those
four original failed-node assertions and outcomes. The two new representation regressions
were separately captured before repair; detailed execution proves **DID NOT RAISE ValueError**
at actual publication, never a setup error. Their bodies remain unchanged; later proof-clock
and concurrency/replay cases are characterization rather than invented historical RED.

The primary acceptance fixture's old SQL-only seeded ACCEPT expectation is replaced with
open-item assertions and a separate fully bound synthetic verifier ACCEPT, as explicitly
authorized by the independently approved repair plan. This proves authentication mechanics;
it supplies no actual owner decision. The added snapshot fixture import only registers the
existing migrator fixture and changes no assertion or product/migration byte.

Root reseal authority uses this durable report. Final original outcomes remain intact in
`d1b-queue-visibility-red.json`, `d1b-queue-provenance-red.json` and the separate two-case
`d1b-queue-representation-r2-red.json`. Migration0009 changes only its approved snapshot/
capture function/ACL surface; committed0001–0008 remain byte-identical and immutable.
