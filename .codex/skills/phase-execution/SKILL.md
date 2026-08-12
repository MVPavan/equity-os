---
name: phase-execution
description: "Execute one phase of a workstream roadmap through the execution skill's phase scope. Use when the user invokes $phase-execution or asks to start a named roadmap phase."
---

# Phase Execution

Invoke the **execution skill** in **phase scope**
(`.codex/skills/execution/SKILL.md` → Phase scope).

- **Input:** phase id and roadmap path, e.g.
  `$phase-execution E --roadmap docs/workstreams/<name>/roadmap.md`. If the
  roadmap is omitted and ambiguous, ask which workstream.
- Workstream-mode auto-approvals do **not** apply here — deep-phase plans
  still require user approval.
