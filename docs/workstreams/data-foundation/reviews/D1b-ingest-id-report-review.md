# D1b ingest ID report review

Status: R2 APPROVE, 2026-10-13. Codex session (handoff run), fresh independent bounded
code-quality review. This accepts the exact-ID report prerequisite, not the full Task 11
published-version producer or Task 13 release.

R1 returned three Important findings. All are addressed:

| Finding | Resolution and proof |
|---|---|
| Member identity omits source/surface/extractor and the test assumes default versions | Each member now carries the actual stored capture source/surface and `MemberGeneration.extractor_version`; an explicit extractor override is checked against actual stored occurrences |
| Required additive field breaks exported constructor and old payloads | `members` defaults to an empty tuple and its empty default is omitted from serialization; old construction and `model_validate` payloads retain their former output shape |
| One fresh success path does not prove reuse or partial failures | Guarded PostgreSQL tests prove identical re-ingest IDs and evidence-table counts, the extractor override, and an unauthorized member's attempt with no invented generation |

The report obtains occurrence IDs from the exact stored member generation and interpretation
IDs from `_interpretations`' exact returned rows. It never searches for a latest row or relabels
an existing generation. Member order and ID order are deterministic. Existing numeric extraction,
qualification, selection, clocks and interpretation behavior are unchanged.

Fresh root verification: **15 passed** on isolated `eqos_test_*` databases, including the new
identity tests and all existing reprocessing cases; scoped Ruff lint/format and strict mypy pass.
R2 inspected the actual code/test changes and that frozen log; no new blocking findings remain.

## Test-first and reopened contract evidence

The first existing-public-ingest RED succeeded in storing a legitimate Apar package, then failed
because `IngestReport` lacked its exact member IDs. Its original one failed outcome remains
recorded. Mechanical Ruff formatting and an independently requested strengthening then added
source/surface/extractor expectations derived from stored rows, retaining every ID assertion.
Before the identity fix, a separate formal proof recorded **3/3 genuine failures** for that
stronger identity case, the legacy constructor, and the extractor override. Root observed GREEN
after the fix. Reuse/partial cases are disclosed characterization cases, not invented RED.

The original sealed file changed from SHA-256
`5013458f020ffb9976c10f6b8564f07135e66979e05a24bc0d32aa7f5ecf83e9` to
`15904e13fca76c5df1055da8661718294bd565bc5fa175e1909e7fefdccdb7dd`.
This document is the explicit orchestrator reopening proof; resealing preserves the original
outcome and the additional genuine identity proof. No financial oracle was added or weakened.

The full producer test remains parked outside executable acceptance under `scratchpad/`, pending
the accepted publication/write-guard handoff. No authoritative shared v2 generation, owner receipt,
financial approval or full D1b acceptance is established by this prerequisite.

VERDICT: APPROVE
