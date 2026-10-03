# Empty screen refusal retention implementation plan

**Origin:** Existing `eqos-3jk` and current user authorization; acquisition path's explicit rule that an error after a retained response cannot discard that evidence.
**Goal:** A `ScreenerSessionError` with an empty or whitespace-only message after capture yields a valid `INCOMPLETE` artifact retaining admitted rows, pages, bodies and typed failure provenance.
**Out of scope:** New acquisition, source rights, scheduling, screen-query interpretation, snapshot migration, dependency or configuration changes.
**Constraints:** Preserve existing exception type and original detail; never invent source content or analytical results. Preserve concurrent edits. No network, credentials, private raw captures, cloud, commits, Beads writes or further workers.

### Task 1: Supply a truthful nonempty refusal summary

Goal: An empty exception message cannot make `ScreenArtifact` construction fail and lose already retained evidence.

Files:
- Modify: `src/fundamentals/ingest/screener_screen.py`.
- Test: create `tests/fundamentals/test_screener_screen_empty_refusal.py`; reuse existing synthetic screen support read-only. Existing screen tests remain regression-only.

Interfaces:
- Consumes: `ScreenerSessionError`, `ScreenFailure`, `ScreenArtifact`, `ScreenRun`, existing screen acquisition function and retained document tuple.
- Produces: Valid existing `INCOMPLETE` output with a nonempty summary when the exception supplied no meaningful message; no new schema or exception class.

Approach: Reproduce an empty-message typed refusal after a synthetic first-page capture through the public acquisition boundary. Keep `ScreenFailure.detail` equal to the original message and its `refusal` equal to the actual exception class. When the summary string has no non-whitespace characters, use a deterministic summary naming the refusal class. Preserve meaningful existing messages and the original failure metadata. Keep the initial failure path that has no retained document raising the original exception. Avoid broad catch changes or fabricated descriptive source messages.

Verification: `.venv/bin/python -m pytest tests/fundamentals/test_screener_screen_empty_refusal.py tests/fundamentals/test_screener_screen.py tests/fundamentals/test_screener_screen_acquire.py -q`. Record the new RED reproduction before implementation and GREEN afterward. Run scoped lint/format and strict mypy on the modified source file.

Test seams: Public screen acquisition with synthetic fetch/read injection. Cover empty and whitespace-only refusals after retained evidence, preserve rows/pages/body digests/type/original detail, preserve a meaningful message unchanged, and a refusal before any response still raises without fabricating a capture.

Dependencies: None; separate ownership from temporal, Upstox and news workers.

Risks: Test-first. A fallback is only a truthful display summary; it must not replace native failure provenance or imply a complete screen. No real source request is needed.

## Document review

The current `ScreenArtifact` requires a truthy `incomplete_reason`, while the typed-exception branch supplies `str(error)` directly. Its failure detail can legally be empty. These existing contracts support the minimal summary fallback without changing persisted schema. The implementation must verify this through the public boundary rather than only calling the private `_incomplete` helper.
