---
name: use-codex
description: "Choose the Codex-native execution path for review, diagnosis, implementation, research, critique, or live capability checks in this repository. Use when deciding between inline work, native subagents, custom agent roles, and an isolated Codex CLI run. Do not route through Claude-only codex-adapter plugins."
---

# Use Codex

Codex is the active runtime. Use native collaboration and repository assets directly; never send work through a Claude-side `codex-adapter` plugin.

## Choose the path

| Need | Path |
| --- | --- |
| Small, reversible task | Work inline and self-check. |
| Standard bounded implementation | Dispatch one native subagent with the `implementer` role instructions, then verify locally. |
| Spec or quality review | Dispatch `spec-reviewer` or `code-reviewer`; keep reviewers read-only. |
| Current library/API/CLI facts | Dispatch `docs-researcher` or use the relevant official documentation skill. |
| Deep independent analysis | Use native subagents only when the user, `AGENTS.md`, or the active skill authorizes delegation. |
| Live Codex runtime truth | Inspect the installed CLI (`codex doctor --json`, `codex debug models`, or `codex debug prompt-input`) and report the actual output. |
| Explicitly requested isolated CLI session | Use `codex exec` with the requested model and sandbox; do not use it as the routine path from an already-running Codex session. |

Custom role definitions live in `.codex/agents/`. If the active collaboration surface cannot select a role by name, include the role file path and its constraints in the dispatch instead of inventing unsupported fields.

## Rules

1. Inherit the parent model and reasoning effort by default. Override them only when the user, `AGENTS.md`, or the active skill explicitly requires it.
2. Honor an explicitly requested model or CLI route. Do not silently substitute another model or host-side work.
3. Keep independent reviews read-only. Grant `workspace-write` only to bounded implementation work.
4. Give subagents concrete tasks, file pointers, constraints, and output contracts; do not paste the whole session history.
5. Verify subagent claims against the actual files and command output before acting on them.
6. On capacity or authentication failure, retry once, then continue without the optional review and report the skip. Small tasks skip independent review unless risk is unusual.
7. For model, session, or capability truth, prefer live CLI evidence over catalog assumptions. Skill visibility does not prove that every spawn surface supports model selection.

Use `.codex/skills/execution/SKILL.md` for approved implementation work and `.codex/skills/code-review/SKILL.md` for review protocol.
