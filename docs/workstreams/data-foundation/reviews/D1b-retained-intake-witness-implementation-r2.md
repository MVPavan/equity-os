# Retained intake witness implementation R2 — 2026-10-13

Reviewer: Codex session (handoff run), independent read-only witness reviewer.
Scope: original-source preparation, opt-in producer, six-table seal/store, consumer,
shared replay closure/context and exact migration upgrade. Full gate is Root's final step.

| Finding / original pending proof | Verdict | Evidence |
|---|---|---|
| W-I01 failed-XBRL peer PDF catalog omitted | ADDRESSED | Source is reconstructed from reproved sealed issuer configuration using the original intake catalog contract; conflicts refuse. Core28-case packet passes. |
| Store invariants, races and rollback | ADDRESSED |47 store cases cover FK/content/clock/closure faults, six sealed-table guards, all isolation boundaries, rollback, equal concurrent seals, genuine stale RR and real RC lock wait/refusal. |
| Complete schema fixtures/permissions | ADDRESSED |48 ordinary id-PK tables genuinely populated, six new tables seeded through actual producer/store seal; original13 mutation/ownership/schema cases pass. |
| Exact populated upgrade | ADDRESSED | Actual retained v1/v2 runs under1–9; only10 applied; all42 existing tables, rows, IDs, run/results/manifests/queue/pins unchanged, both by-ID replays pass. |
| Shared public fresh/replay wiring | ADDRESSED | Closure checked after exact by-ID load; context before both engines; integrated synthetic witnessed vendor run and frozen-ID replay pass. |
| Substitutions and foreign contexts | ADDRESSED | Eight handoff plus schema/input/clock substitutions refuse; closure and filesystem/repository prohibition cases pass. Context-only positive holds extractor identity unchanged. |
| W-R02 future witness re-entered AS_KNOWN engine | ADDRESSED | Shared context refuses any future witness before evaluation, even all-NOT_SELECTED. Actual recompute sentinel proves engine never constructed; new1/1 genuine RED before repair. RETROSPECTIVE unchanged. |
| W-R03 PUBLIC ACL test omitted guards | ADDRESSED | Exact non-vacuous12-function inventory includes SECURITY DEFINER guards; complete PUBLIC ACL query passes. |

Final focused repair packet: **27 passed in89.39s**. Corrected context-only
specificity case: **1 passed in4.63s**. Integrated public witnessed single:
**1 passed in6.00s**. Full Ruff/format495files and strict mypy278sourcefiles pass.
Reviewed0010 SHA-256:
`5f9426ef4e611472e6dc0e46c133c3ac4a5fb67107a1d732c16c8cc0436c9026`.
Migrations0001–0009 remain byte-identical. All modified Python files are at most800lines.

No new Critical or Important mechanism defect found. The reviewer inspected the assigned
atomic group and Root's fresh terminal logs; performed no edits, Git, Beads, PostgreSQL
or network operations. Original RED outcomes and disclosed fixture/format reseals are
preserved in the [reseal proof](D1b-retained-intake-witness-reseal.json).

Proof limits:

- RC test seals before starting its child; later common-lock wait proves serialization
  and sealed-child refusal, not a seal committed during the wait. SQL contains the
  VOLATILE post-lock visibility check. Atomic publication prevents a visible uncommitted
  parent; the build notes record this without fabricated visibility or clocks.
- SQL CASE setup, PUBLIC-query cast, nonexistent-node and source-clock fixture failures
  are preserved as infrastructure/fixture failures, excluded from behavior RED claims.
- Full stable gate remains a separate final condition. This approval establishes neither
  actual SONACOMS equivalence nor complete vendor coverage, D1b exit or project completion.

VERDICT: APPROVE the bounded reviewed group, subject to final broad verification.

## Final integration repair R3

The first broad main attempt found that eager optional metadata anchoring rejected legacy
intake on the real checkout's configuration parent. Two actual existing nodes reproduced
UnsafePathError; that failed broad attempt was interrupted with exit130, never reported PASS.
Two new synthetic unsafe-parent cases failed2/2 before repair.

Independent R3 review verdicts:

| Boundary | Verdict | Evidence |
|---|---|---|
| Legacy factory compatibility | ADDRESSED | SnapshotError is caught only around optional metadata anchors; mandatory input/store anchors, parsing, bindings and hashes retain their old contract. |
| Strict opted-in source refusal | PRESERVED | Missing metadata refuses before publication verification or repository/generation writes; the two new cases assert no repository calls. |
| Main positive metadata fixtures | ADDRESSED | Declared private exact metadata copies retain original hashes, bindings and input/store anchors. No financial-original or real permission change. Explicit missing-metadata negative remains. |

Actual main packet: **52 passed in86.27s**, including positive/source cases,
legacy integration/run rules and historical queue upgrade. Reviewed capture_intake.py
SHA-256 `d7fae88fdb051c8009c63b5e81118e8b0133a611eafa2ed889be752009c153b4`,345lines.
Independent reviewer made no edits or tool-side mutations and found no new Critical or
Important issue. Original source assertions and the new two-case regression AST remain
unchanged under the disclosed fixture reseal.

VERDICT: APPROVE the bounded R3 repair; final stable broad gate remains required.

## Root final verification

Frozen full suite: **3398 passed,8existing skips**,1605.66s; full Ruff lint/format and
strict mypy pass. The formal wrapper returns STOP only for prohibited path-pattern
literals in the old R1 review's prose, not a test or production failure. Root preserves
that result, removes those literal patterns without changing the review verdict, and
reruns the exact unchanged security block on the full original scope. All rails clear.

The final synthetic public test receives its missing pg classification marker. The
complete test function/assertion AST and unfiltered test membership remain unchanged;
pg collection selects1 node and not-pg deselects it. This metadata-only fix is explicitly
resealed. No duplicate full suite is run for prose/marker-only changes. The build notes
distinguish combined passing evidence from the preserved formal-wrapper STOP.
