# D1b Task 6 queue visibility and provenance repair

Status: R2 APPROVE, 2026-10-13, fresh independent Codex session (handoff run). Supplements the approved
[vendor-run plan](D1b-vendor-runs.md). All R1 findings are addressed; bounded implementation
is authorized. Owner: `eqos-u0u.17`. Existing migrations 0001–0007 remain immutable.

## Evidence and authority ruling

Fresh independent queue R1 finds four Important defects: late-commit overlay drift, closure
without the accepted receipt verifier, autocommit partial publication and forged source labels.
The original ten scoped cases pass: nine PostgreSQL and one pure. Four coordinator regressions reach
the implemented public helpers and genuinely fail; no missing API or infrastructure error is
counted as RED. The two valid proof files are `d1b-queue-visibility-red.json` and
`d1b-queue-provenance-red.json` in the isolated checkout's `scratchpad/gate/`.

Migration 0005's effective store clock is transaction-stable and issued before commit. Even a
repeatable-read capture cannot make a later timestamp-only reread immutable. The latest
coordinator ruling requires a durable visibility seal. This supersedes the timestamp-only
mechanism of vendor-run decision 14 and authorizes additive migration 0009 for that concrete
need. No clock is backdated, old row rewritten or financial judgment inferred.

## Exclusive implementation ownership

- Queue owner: existing `compare/queue.py`, optional new `compare/queue_overlay.py`, additive
  `contracts/review_queue.py`, existing queue tests and new queue visibility/provenance tests.
- The same bounded owner may draft `migrations/0009_queue_overlay_snapshots.sql` and focused
  `test_queue_overlay_snapshots.py`; root owns migration acceptance, PostgreSQL execution and
  integration. No other migration, approval producer, repository, run writer or config is edited.
- Root records all test amendments and preserves the four new RED outcomes. Production Python
  files stay at or below 800 lines. Task 7's actual external authenticator remains separate.

## Contracts

1. `publish_queue_drafts` requires its cursor to be inside an active caller transaction before
   any query, advisory lock or DML. An autocommit connection inside an explicit transaction is
   valid; an idle/autocommit cursor refuses with no queue-table mutation. The helper never opens,
   commits or substitutes a transaction. Signed lock deduplication/order stays unchanged.
2. Reload actual source, surface and representation with every tagged evidence ID and clock.
   Compare evidence against the draft's source references and the stored run's declared scope
   before mutation. Every evidenced side must match actual provenance. Extra references may
   describe a missing counterpart only when that counterpart is declared by the run's routing
   scope; arbitrary vendor identities never qualify. Preserve omitted first-party identities and
   legitimate missing-side routes. Final role/diagnostic classification remains the verified
   Task 6 resolver's responsibility; a queue claim cannot substitute for it. Include the proved
   provenance in the versioned input digest; immutable payload/association reuse stays exact.
3. Add one append-only `queue_overlay_snapshots` table naming the existing run, actual `as_of`,
   its exact UTC epoch-microsecond `recorded_position`, and sorted exact visible membership-item
   and final-disposition-candidate IDs. Arrays must be duplicate-free and refer only to rows
   visible to that capture. It stores visibility, not a caller-supplied trust decision. The
   database enforces uniqueness of `(run_id, as_of, recorded_position)`. A second capture in the
   same transaction reuses only an identical complete ID set; intervening own writes producing
   different sets at that same triple refuse. No conflicting seal is overwritten or silently reused.
4. Runtime may SELECT snapshots and execute a narrowly scoped, migrator-owned capture function
   taking only a run ID. Runtime and PUBLIC cannot directly INSERT/UPDATE/DELETE/TRUNCATE snapshot
   rows or forge timestamps/ID arrays. The function has a fixed safe search path, fully qualified
   SQL and no dynamic identifiers. It derives IDs from existing queue tables, calls
   `eqos.store_now()` once, and derives the position in SQL. No caller clock, blob or row set is
   accepted. The database function itself refuses unless transaction isolation is REPEATABLE READ
   or SERIALIZABLE; direct runtime calls cannot bypass the MVCC contract. The Python capture uses
   REPEATABLE READ, retrying only serialization failures, at most three complete transactions.
   Retry exhaustion raises a typed failure without a returned seal. Other errors are not retried.
   Each successful capture commits its visibility seal atomically before returning.
5. `capture_queue_overlay(pool, *, run_id)` captures and returns the actual sealed visibility.
   `read_queue_overlay(pool, *, run_id, as_of, recorded_position)` requires the exact existing
   captured triple and reloads only its named immutable IDs. A mathematically matching but
   uncaptured timestamp/position refuses. Late membership or disposition commits cannot change
   an existing overlay; a fresh capture may include them. Origin run IDs and membership times
   remain unchanged. Empty legacy membership JSON/constructor behavior remains unchanged.
6. On the same read connection, every candidate closure reuses `reload_verified_receipt` to
   prove actual subject/proposal digests, protected raw evidence hash and authenticated decision
   document. Require ACCEPT and exact disposition/proposal/receipt binding. The item, membership,
   proposal, receipt, review-evidence and disposition clocks must all be at or before the sealed
   position. Invalid, missing, rejected or out-of-position proof never closes the item; it stays
   open. Verification failures are explicit in the helper/report evidence, never represented as
   authenticated approvals. A snapshot's candidate ID alone grants no closure authority.
7. Existing constructed SQL immutability fixtures remain schema-only evidence. Root authorizes
   replacing the queue test's invalid seeded-ACCEPT closure expectation with open-item assertions
   and adding a distinct valid, fully bound synthetic ACCEPT through the existing verifier path.
   This strengthens the trust contract; it does not claim actual project or owner approval.

## Verification and acceptance

- Preserve all existing queue lock/digest/reuse/predecessor/membership properties and four
  genuine RED outcomes. Root may mechanically format the new tests with whole-AST equality
  evidence and explicitly reseal them; no numerical or refusal assertion is weakened.
- PostgreSQL proves no-write autocommit refusal; forged source/surface/representation refusal;
  fixed rereads across late membership and fully verified ACCEPT commits; fresh-capture visibility;
  exact pair/triple validation; and invalid subject/proposal/raw/document/late-proof closure refusal.
- Direct runtime capture calls prove isolation refusal, same-transaction identical-seal reuse and
  differing-set refusal. Concurrent captures prove complete MVCC views; retry tests prove the
  three-attempt bound and typed exhaustion, with no fabricated successful result.
- Migration tests prove runtime cannot forge/mutate/truncate snapshots, the capture function
  derives its own clocks/sets, rejected closures stay open, and a byte-identical 0001–0008 database
  upgrades without changing stored run/result/queue identities or v1 replay. Historical upgrade
  witnesses apply exactly their named migration boundary rather than assuming the latest directory.
- Run focused guarded PostgreSQL tests, legacy queue/contracts/approval tests, Ruff lint/format
  and strict mypy; independent fix re-review must address all four R1 findings. Full integration
  quality is batched after the run/producer/queue sources freeze. Actual release/source/Task 7
  approval acceptance and full D1b remain separately gated.

Fail closed if the seal, complete provenance or proof cannot be established. Do not disable a
trigger, widen a privilege, reinterpret fixture evidence as real approval or rewrite an old migration.
