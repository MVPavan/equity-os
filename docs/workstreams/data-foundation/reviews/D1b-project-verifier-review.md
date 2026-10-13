# D1b Task 12 independent verifier review

VERDICT: APPROVE

Reviewer: Codex `/root/review_verifier_and_amendment` (independent of implementer).
Review date: 2026-10-13.
Scope: `scripts/verify_project.sh` and `tests/fundamentals/test_verify_project.py`; D1b Task 12 implementation and dispatch/control-flow proof only.

## Spec compliance

- COMPLIANT: explicit required slots cover D1a, D1b, D2–D9, D3 export, frozen manifests, amendment records and Pilot. Targets match the roadmap and the additional export requirement in `docs/workstreams/data-foundation/core.md:74`; `scripts/verify_project.sh:52–65`.
- COMPLIANT: an unresolved approved pilot path remains a required `NOT BUILT` slot, with no arbitrary runtime path override; `scripts/verify_project.sh:9–10,38–48,65`.
- COMPLIANT: command failures are accumulated, remaining parts continue, and any failed or absent required part produces nonzero; `scripts/verify_project.sh:24–48,73–77`.
- COMPLIANT: full pytest, strict mypy, Ruff check and format use the authoritative scopes without PG/retained marker exclusions; `scripts/verify_project.sh:67–71`, `.codex/project/verification.md:27–33,43–49`.
- COMPLIANT: the script explicitly states that its result does not close epics or replace independent approval records; `scripts/verify_project.sh:2–5`. This implements the check, without claiming project completion.
- COMPLIANT: the controlled subprocess tests prove dispatch and failures rather than representing synthetic files as financial or pilot evidence; `tests/fundamentals/test_verify_project.py:85–170`. The future all-present test registers its synthetic pilot only in an isolated copy, while production remains unresolved; lines 138–156.
- COMPLIANT: no new vendor capture, database operation, financial acceptance oracle or later-phase implementation exists in this owned change.

## Severity-ranked issues

- Critical: none.
- Important: none.
- Minor: none.

## Evidence and limits

- Fresh reviewer check: `bash -n scripts/verify_project.sh`, exit 0.
- Implementer evidence reviewed: five acceptance tests red before the missing script was created, followed by `5 passed in 0.79s`, scoped Ruff/format and shell syntax checks; `scratchpad/execution/data-foundation-autonomous-2026-10-13/project-verifier-report.md`.
- No redundant test rerun was warranted by source inspection. No real full-project verification was performed by this reviewer. The coordinator must execute the actual command at stable integration and report its real outcomes; the unresolved production Pilot slot necessarily keeps project completion false. This remaining phase-gate action is explicitly separate from Task 12 completion in `docs/workstreams/data-foundation/plans/D1b.md:715–721`.
- The implementer reports that formatting changed the sealed red-proof test hash. If the coordinator uses the hash-sealed pipeline gate, record the authorized nonsemantic reseal; do not rewrite historical red evidence. This does not invalidate the focused green proof or require another broad suite.

VERDICT: APPROVE
