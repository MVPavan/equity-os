# Graph loops — adoption history

How this repo orchestrates multi-model work, and how that has changed. One file
per adopted version, newest first. These are **orchestrator documents**: they are
deliberately not rules under `.claude/rules/` and not listed in
`.claude/project/docs-index.md`, because loading them into every agent's context
is the exact cost they exist to avoid. Workers get the parts that apply to them,
in their brief.

| Version | Adopted | Status | Shape |
|---|---|---|---|
| [v2 — build pipeline](v2-build-pipeline.md) | 2026-08-30 | **current** | Pipeline. One loop (implementer ⟳ script), every model review single-pass. Tests written first by a different family than the implementer; deterministic gate with a red proof + diff coverage standing in for mutation. |
| [v1 — review cycle](v1-review-cycle.md) | 2026-08-27 | superseded | Cycle. Reviewers inside the loop, up to 3 inner × 2 outer rounds. No test-writing stage, no mutation, no instrumentation. |

**The change in one sentence:** v1 was a cycle whose loop was billed; v2 is a
pipeline whose only loop is free.

**Known gap:** mutation testing is deferred — v2 ships with a red proof and diff
coverage in its place, and keeps implementation review at 2 passes until
mutation lands. See
[v2 § Mutation and its stand-in](v2-build-pipeline.md#mutation-and-its-stand-in).
`scripts/verify.sh` was built 2026-09-02 and closes the other half of this gap.

## Provenance

v2 is adapted from the `coding-ritual` project's `docs/graph-loops/build-loop.md`
v4.1, which that project adopted 2026-08-29 after its phase-5 token audit. Our
adaptation keeps its pipeline shape, seam rule, and family-alternation ranking,
and substitutes our verification commands, our routing table, and the
acquisition-workstream security rails. Its mutation gate is **not** adopted —
it does not exist in that repo (see the known gap above).

The evidence that drove the change — the phase-5 loop post-mortem and a metadata
audit of 1,052 local session logs — is summarised in
[v1-review-cycle.md](v1-review-cycle.md) under "Why it was replaced".
