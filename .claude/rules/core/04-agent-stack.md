# Agent Stack and Review Loop

Owner directive (PavanMV, 2026-10-11). Fixed until the owner names a change — do not switch
models, efforts, or roles on your own judgment. Overrides older routing in skills, `tools.md`, and
memory where they conflict.

## Roles

| Role | Model | Scope |
|---|---|---|
| Orchestrator | the main session | Scoping, planning, worker briefs, integration, final verification, commits, beads. May make tiny edits (a few lines) directly. |
| Main implementer | `claude-opus-5-5`, effort `medium` | Big or complex work: multi-file features, standard/deep tasks. |
| Small-task worker | `claude-sonnet-5-5`, effort `medium` | Small, low-ambiguity work: single-file edits, config, docs, mechanical changes. |
| Reviewer | `gpt-6.1-sol`, effort `high` | Specs, plans, significant implementation chunks. |

Dispatch every worker through the T3 Code orchestrator (`delegate_task`, then `task_status`;
continue a worker by messaging its child thread). Not native subagents, not the Codex adapter.

## When to review

Only at critical points: a spec or plan, a significant implementation chunk (phase or major
component), and before integrating anything touching financial logic or shared contracts. Routine
tasks — including routine Opus work — skip review.

## Review loop

1. Implementer finishes the chunk.
2. Reviewer reports **every** issue in one pass. Always put this in the brief: "List ALL issues you
   find in a single exhaustive report — do not stop at the first few, do not hold any back for a
   later round. Rank by severity." Reviewers tend to under-report; insist.
3. The **same implementer session** fixes all issues in one go.
4. The **same reviewer session** checks the fixes and gives a verdict (not a fresh review).
5. Repeat 3–4 until approved. Not converged after 3 rounds → escalate to the owner.
6. Loop closed → one **fresh** reviewer session (same model, no prior context) does a critical
   review of everything: nothing broken, nothing wrong. Real findings go back to the implementer's
   session; that fresh reviewer verifies the fixes.
7. Orchestrator runs verification and commits.

## Testing

See `.claude/rules/python/testing.md`. In short: the implementer writes tests with the code;
weight goes to integration and end-to-end; unit tests only for dynamic logic.
