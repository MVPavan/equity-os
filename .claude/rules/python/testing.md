# Python Testing

Owner policy (2026-10-11): fewer, more robust tests. Token cost of exhaustive unit tests is not
worth it for code that models write reliably.

- Use `pytest` unless the repo already standardizes on a different framework.
- The implementer writes tests alongside the code; no separate test-author step.
- **Weight goes to integration and end-to-end tests:** real pipeline runs over retained sources,
  cross-source comparisons, full workflow paths.
- **Unit tests only for dynamic logic:** calculations and formulas, transforms, matching and
  corroboration rules, tolerance checks — especially anything financial.
- **No unit tests for static things:** Pydantic model declarations (frozen, typed models already
  reject wrong types and missing fields at construction), config fields, constants, enums, thin
  wrappers. Pydantic does not check meaning — a well-typed number can come from the wrong formula —
  so that is what the remaining unit and end-to-end tests target.
- For a risky change to existing behaviour, capture the current behaviour first (one
  characterization or integration test), not a test per function.
- Test sizes — **small:** one process, no I/O, milliseconds; **medium:** local I/O or test
  databases, no external services, seconds; **large:** external services, minutes.
- Test behavior through public interfaces, not private implementation details.
- Prefer parametrization and shared fixtures over repetitive test bodies.
- Do not mock internals by default; mock hard external boundaries when needed.
- Reuse the repo's existing test directories, fixtures, and markers where they exist.
- The exact commands to trust live in `.claude/project/verification.md`.
