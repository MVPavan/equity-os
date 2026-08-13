# Agent Operating Guide

Always-loaded entry point — every line here costs context. Detail lives in the pointed-to docs; keep it there.
Core harness is stable; repo-specific facts live in `.codex/project/`.

## Critical guidelines

- We have limited amount of time. Dont unecessarily spend time on checking/reviewing trivial things, time is critical, you will be killed if we run out of time. Make best use of it.
- Prioritize factual accuracy over agreement with me.
- Point out errors and unchecked assumptions in my thinking.
- When I ask you to assess something, do so critically and avoid grade inflation.
- Distinguish certain knowledge from inference from speculation.
- If unsure, say so. Never fabricate citations, data, or examples.

## Read Order

1. `AGENTS.md`, then `CONTEXT.md` (domain glossary — use its terms, flag conflicts)
2. `.codex/project/`: `brief.md`, `repo-map.md` (folder structure + how to orient), `docs-index.md`, `verification.md`, `invariants.md`
3. `docs/research/` — when working from prior research, runtime comparisons, or provider/tooling decisions
4. `docs/workstreams/<name>/roadmap.md` (active workstream plan) + generated workstream mirrors — when a workstream exists
5. Relevant rules under `.codex/rules/`
6. `reference_harnesses/<name>/` docs — only when the task is explicitly about that reference submodule

## Coding guideline

1. Follow `.codex/rules/core/03-ak-guidelines.md` — coding rules that reduce common LLM mistakes.
2. Use `html-artifact` only when the user asks for HTML, or when the deliverable is purely for human reading and richer structure clearly helps. Do not use it for agent prompts, README files, harness docs, or other Markdown-native repo files.

## Working Mode

Classify the task before acting.

- `small`: 1-2 files, low ambiguity, reversible. Execute directly, then self-check.
- `standard`: bounded feature, bug fix, or refactor. Short plan before coding.
- `deep`: cross-cutting, high-risk, or ambiguous. Brainstorm, plan, review, execute via subagents, capture learnings.

Lean by default. Match ceremony to scope and risk.

## Process Before Execution

- unclear or exploratory request: brainstorm first
- an approved spec plus multi-step code work: plan first
- newly written spec or plan docs: review the document before execution
- risky behavior change or fragile legacy area: test-first or characterization-first
- bug, failure, or confusing behavior: systematic-debugging before proposing fixes
- approved plan with bounded tasks: subagent-driven development
- about to claim success: verify before completion

If the user already supplied a clear, approved plan, do not re-run brainstorming.

## Execution

Approved implementation work runs through the **execution skill** (three scopes: task / phase / workstream; entry commands `/phase-execution N` and `/run-phases` in Claude Code, `$phase-execution N` and `$run-phases` in Codex). Full cycle: planning → dispatch → review → TDD/debugging as routed → verification. Phase inventory: `docs/workstreams/<name>/roadmap.md`; work-state in Beads.

## Codex And Claude

Codex-native assets live in `.codex/`: skills, custom agents, hooks, rules, config, project facts, and legacy reference docs. Use `$use-codex` for current invocation choices. Codex review/critique remains best-effort: `small` tasks skip it unless risk is unusual; capacity errors get one retry, then proceed without it and log the skip. Claude Code assets under `.claude/` remain as a legacy/source harness for Claude-specific runs.

## Tools & Subagents

Unsure about a library/SDK/API/CLI (methods, signatures, config, versions)? Use official/reference docs via the `docs-researcher` agent/skill path where available; never invent APIs. Use brainstorming for open-ended project research, tradeoffs, and requirements decisions. Tool routing details live in `.codex/project/tools.md`.

## Verification

No completion claims without fresh evidence.

1. Identify the command that proves the claim.
2. Run it.
3. Read the output and exit status.
4. Report the actual result.
5. Check `git status` before presenting completion.

Source of truth: `.codex/project/verification.md` and `.codex/project/invariants.md`.

Until the repo has real first-party code and CI, use the structural checks in `.codex/project/verification.md`.

## Learnings

Record verified, likely-to-recur patterns in `.codex/project/learnings.md` (format + rules in its header).

## Git Safety

- Stage explicit files only. No `git add .`, `git add -A`, `--no-verify`, force-push, `reset --hard`, `clean`, `restore`, or `checkout` rewrites without explicit approval.
- Small reversible commits. Do not amend unless the user asks.
- Do not overwrite unrelated user changes.
- Do not encode machine-local absolute paths in plans, prompts, docs, or rules.
- Use `scratchpad/` for throwaway work — gitignored, never commit it.

## External Submodules

Third-party **reference harness** repos are tracked as Git submodules under `reference_harnesses/` (see `.gitmodules`). The parent repo tracks their commit pointers only — they are read-only references, never copied into the local harness. Do not edit submodule internals unless the task is explicitly submodule-local; for upstream sync, update and stage the submodule path. Borrow only the smallest durable pattern (see `harness_learnings/reference-harness-workflow.md`).

## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Workflow, rules, agent context profiles, and the session-completion protocol live in **[`.beads/beads.md`](.beads/beads.md)**. Run `bd prime` for runtime context.

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:970c3bf2 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Agent Context Profiles

The managed Beads block is task-tracking guidance, not permission to override repository, user, or orchestrator instructions.

- **Conservative (default)**: Use `bd` for task tracking. Do not run git commits, git pushes, or Dolt remote sync unless explicitly asked. At handoff, report changed files, validation, and suggested next commands.
- **Minimal**: Keep tool instruction files as pointers to `bd prime`; use the same conservative git policy unless active instructions say otherwise.
- **Team-maintainer**: Only when the repository explicitly opts in, agents may close beads, run quality gates, commit, and push as part of session close. A current "do not commit" or "do not push" instruction still wins.

## Session Completion

This protocol applies when ending a Beads implementation workflow. It is subordinate to explicit user, repository, and orchestrator instructions.

1. **File issues for remaining work** - Create beads for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Handle git/sync by active profile**:
   ```bash
   # Conservative/minimal/default: report status and proposed commands; wait for approval.
   git status

   # Team-maintainer opt-in only, unless current instructions forbid it:
   git pull --rebase
   bd dolt push
   git push
   git status
   ```
5. **Hand off** - Summarize changes, validation, issue status, and any blocked sync/commit/push step

**Critical rules:**
- Explicit user or orchestrator instructions override this Beads block.
- Do not commit or push without clear authority from the active profile or the current user request.
- If a required sync or push is blocked, stop and report the exact command and error.
<!-- END BEADS INTEGRATION -->

<!-- BEGIN BEADS CODEX SETUP: generated by bd setup codex -->
## Beads Issue Tracker

Use Beads (`bd`) for durable task tracking in repositories that include it. Use the `beads` skill at `.agents/skills/beads/SKILL.md` (project install) or `~/.agents/skills/beads/SKILL.md` (global install) for Beads workflow guidance, then use the `bd` CLI for issue operations.

### Quick Reference

```bash
bd ready                # Find available work
bd show <id>            # View issue details
bd update <id> --claim  # Claim work
bd close <id>           # Complete work
bd prime                # Refresh Beads context
```

### Rules

- Use `bd` for all task tracking; do not create markdown TODO lists.
- Run `bd prime` when Beads context is missing or stale. Codex 0.129.0+ can load Beads context automatically through native hooks; use `/hooks` to inspect or toggle them.
- Keep persistent project memory in Beads via `bd remember`; do not create ad hoc memory files.

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.
<!-- END BEADS CODEX SETUP -->
