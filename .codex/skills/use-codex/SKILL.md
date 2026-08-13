---
name: use-codex
description: "Use when a task needs Codex invocation routing, a sub-agent, a custom role, independent review or research, or a live Codex capability check."
---

# Use Codex

Codex is the active runtime. Work inline when delegation adds no value. When
delegation is authorized, launch every sub-agent through an isolated Codex CLI
run; do not use a host-native spawn surface or a Claude-side `codex-adapter`.

## Choose the path

| Need | Path |
| --- | --- |
| Small, reversible task | Work inline and self-check. |
| Standard bounded implementation | Launch one Codex CLI sub-agent with the `implementer` role constraints and `workspace-write`, then verify locally. |
| Spec or quality review | Launch `spec-reviewer` or `code-reviewer` through Codex CLI with a read-only sandbox. |
| Current library/API/CLI facts | Launch `docs-researcher` through Codex CLI with a read-only sandbox, or use the relevant official documentation skill inline. |
| Heavy or numerous stock documents | Split the sources into bounded packages and launch each through a separate Luna Codex CLI agent: `high` by default, `xhigh` for dense, ambiguous, cross-document, or high-stakes reading. |
| Deep independent analysis | Launch Codex CLI sub-agents only when the user, `AGENTS.md`, or the active skill authorizes delegation. |
| Live Codex runtime truth | Inspect the installed CLI (`codex doctor --json`, `codex debug models`, or `codex debug prompt-input`) and report the actual output. |

Custom role definitions live in `.codex/agents/`. Name the role and include its
file path and constraints in the CLI prompt; `codex exec` does not select these
repository roles by name.

## Select model and effort

Use only these project-approved model classes:

| Class | Model |
| --- | --- |
| Low end | `gpt-5.6-luna` |
| Mid tier | `gpt-5.6-terra` |
| SOTA tier | `gpt-5.6-sol` |

Use only `medium`, `high`, or `xhigh` reasoning effort. Do not consult or run
Agent Matrix: it is disabled for this repository until the user re-enables it.

The stock-document lane covers annual reports, financial filings, quarterly
results, earnings materials, investor presentations, transcripts, exchange
disclosures, and similarly heavy or numerous equity-research sources. Luna
output is candidate research or evidence. A fresh Sol `xhigh` review must occur
before it becomes authoritative financial interpretation or feeds a spec, plan,
implementation, ledger acceptance, or completion claim.

The CLI shape is:

```bash
codex exec -C . -m <model> -c 'model_reasoning_effort="<effort>"' -s <read-only|workspace-write> --ephemeral '<prompt>'
```

## Rules

1. Delegate only when the user, `AGENTS.md`, or the active skill authorizes it.
2. Every sub-agent runs through `codex exec` with an explicit approved model and effort. Do not silently substitute another model, effort, route, or host-side work.
3. Keep independent reviews read-only. Grant `workspace-write` only to bounded implementation work.
4. Give sub-agents concrete tasks, file pointers, constraints, and output contracts; do not paste the whole session history.
5. Verify sub-agent claims against the actual files and command output before acting on them.
6. On capacity or authentication failure, retry once, then continue without the optional review and report the skip. Small tasks skip independent review unless risk is unusual.
7. For model, session, or capability truth, prefer live CLI evidence over catalog assumptions. Catalog visibility does not prove successful execution.

Use `.codex/skills/execution/SKILL.md` for approved implementation work and `.codex/skills/code-review/SKILL.md` for review protocol.
