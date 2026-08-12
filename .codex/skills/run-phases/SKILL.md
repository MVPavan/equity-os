---
name: run-phases
description: "Run every remaining phase of a workstream unattended through the execution skill's workstream scope. Use only when the user invokes $run-phases or explicitly asks to run all remaining phases without stopping."
---

# Run Phases

Invoke the **execution skill** in **workstream scope**
(`.codex/skills/execution/SKILL.md` → scope selector row 1, then
`references/workstream-mode.md`).

This invocation **is** the explicit user opt-in that workstream mode's
auto-approvals and per-phase commits require — record it in the workspace
ledger as workstream-mode.md's preflight directs.

- **Input:** the roadmap path, e.g.
  `$run-phases docs/workstreams/<name>/roadmap.md`. If omitted and
  ambiguous, ask which workstream.
