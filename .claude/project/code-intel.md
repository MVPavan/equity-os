# Code Intelligence (code-intel plugin)

**Recommendation: not yet.** Report-only; nothing enabled.

- **Size / shape:** pre-code — the repo is the harness plus two blueprint
  Markdown docs. Nothing for an LSP or symbol graph to index.
- **Primary language / LSP:** none yet. Python 3.12+ is the confirmed intended
  stack, so the future LSP is Python (pyright/jedi via serena).
- **Index state:** not indexed; no `.serena/` or `.codebase-memory/`.

**Revisit trigger:** when Phase 0.5/1 lands real first-party Python (ingestion,
schemas, state machine, deterministic compute), this becomes a multi-session,
navigation-heavy codebase — exactly the plugin's target. Reassess then; opt-in
steps live in the adoption-report of the meta-harness and in the plugin docs.
