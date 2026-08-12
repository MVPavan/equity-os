---
name: agent-matrix
description: "Validate Codex subagent model, effort, context, and capability selections against the active runtime and an optional repository Agent Matrix catalog. Use only when the user explicitly asks for Agent Matrix selection or runtime support checks. Do not invent catalog values or apply Claude-only invocation fields to Codex."
---

# Agent Matrix

First check for both repository assets:

- `docs/research/codebases/subagent-runtimes/agent-matrix-values.yaml`
- `tools/agent-matrix/agent_matrix.py`

If either is absent, report that the repository Agent Matrix is not installed and route ordinary Codex work through `$use-codex`. Do not reconstruct the missing catalog from memory. This repository currently lacks both assets.

## Codex selection

1. Read the active `spawn_agent` or collaboration-tool schema and treat its advertised models, reasoning efforts, and context-fork fields as the live invocation contract.
2. If the catalog exists, validate requested static values with its deterministic validator before dispatch.
3. Inherit the parent model and effort when the user did not request an override.
4. Reject unsupported requested values explicitly; never substitute a nearby model, effort, context mode, tool set, or permission.
5. Distinguish catalog membership from live spawn support. Verify runtime behavior when that distinction matters.
6. Keep role instructions in `.codex/agents/` and apply task-specific model or context choices at dispatch time only when the active surface supports them.

Claude Agent fields such as `subagent_type`, `permissionMode`, `CLAUDE_CODE_FORK_SUBAGENT`, or `/subtask` are not Codex invocation fields. Consult the preserved `.claude/skills/agent-matrix/SKILL.md` only from a Claude runtime.
