# D1b publication repair review

Status: implementation plan R3 APPROVE, 2026-10-13. Codex session (handoff run), fresh independent
spec/security review. This approves implementing the repair; it does not approve a release or
claim actual review/receipt evidence for a future candidate.

The initial implementation passed 16 focused PostgreSQL/ID cases but independent review found
nine Important gaps. Green mechanics alone do not establish the publication authority boundary.

| R1 finding | Approved concrete repair |
|---|---|
| RELEASED path equality does not prove committed reviewed bytes | Fixed receipt and deterministic candidate A → receipt/review C → current H lifecycle, exact blobs and subject binding |
| Generation boundaries accept unjoined drafts | Fresh proof and pinning before Task 11/Task 6 authoritative writes, exact publication digest, zero-write refusal; explicitly separate legacy/draft paths |
| Derived source masquerades with first-party surface | Complete declared source/surface classification; unknown/derived sources require publication |
| Authority strings/hashes can invent roles or rights | Closed actual A05 private-use projections; exact evidence content; Upstox remains diagnostic-only with no surface authority |
| Ledger-only mutation passes replay | Optional publication pin in `PinnedVersions`, RunStore and replay checks; new migration 0007, v1 defaults omitted |
| Synthetic check and pins use different pools | Database check and pin writes use one repository connection and transaction |
| Version traversal and symlink/TOCTOU paths | Canonical single-component versions and descriptor reads of regular, no-follow members |
| Extractor and mapping schema mismatch | Exact source/surface/schema join to the pinned extractor bundle |
| Tests are synthetic mirrors and omit real boundaries | Exhaustive public-seam refusal/no-write/run/replay/migration/receipt/path/authority matrix; eventual real release proof remains root-owned |

Plan R1 requested six concrete additions: the non-self-referential commit lifecycle, a fixed trusted
receipt contract independent of Task 7 approval, named producer seams/owners, semantic authority
projection, exhaustive acceptance matrix, and explicit repository ownership. Plan R2 confirmed
those repairs but retained two Important gaps: constructible public models could masquerade as
loader proof, and C was not deterministically identifiable. R3 closes both by reloading fixed-path
receipt/Git evidence at the authoritative boundary and deriving the unique first-parent introduction
of both exact receipt/review blobs. Replacement and ambiguous histories refuse; unrelated later
commits remain valid. All prior findings are addressed; no new spec issues remain.

The [approved repair plan](../plans/D1b-publication-repair.md) defines the exact APIs, ownership,
commit/receipt lifecycle, semantic rights boundary and acceptance matrix. Actual coordinator review
and commit establish operational reviewer identity; runtime verifies that committed record, never
claiming a hash, path, model or state authenticates an external reviewer by itself.

Original publication RED disclosure is preserved: one genuine feature failure, eleven new-keyword
API failures and one fixture failure. The corrected old-loader replay proves the strengthened
absence guard; original outcomes remain intact. The repair's separate formal proof records
**12/12 genuine existing-public-behavior failures** before source edits. The earlier zero-collected
UV cache attempt is infrastructure and is not counted. Future source/SQL release acceptance,
independent implementation review and the actual A/C artifact commits remain open.

VERDICT: APPROVE (implementation plan only)
