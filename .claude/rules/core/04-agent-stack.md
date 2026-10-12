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

Dispatch every worker through the T3 Code orchestrator (`delegate_task`; results arrive by
notification). Not native subagents, not the Codex adapter.

**Workers run autonomously (owner, 2026-10-11):** the owner cannot open subagent threads to answer
permission prompts, and a prompted worker stalls. Dispatch with `runtimeMode: "auto"` (the
session's own mode; T3 refuses anything broader than the parent, e.g. `full-access`), never
`approval-required`. Keep read-only workers read-only through their brief ("do not edit files,
no git, no bd").

**Rounds are fresh (owner, 2026-10-11):** T3 cannot resume a finished delegated session, so every
round is a fresh `delegate_task` with a lean brief — no transcripts or full prior context. A fix
round gets the artifact plus the findings list; a re-review round gets the artifact, its own prior
findings list, and the fixes. Use a distinct `clientRequestId` per round.

## Autonomous approval (owner, 2026-10-12)

The owner does not approve specs, plans, source interpretations, report versions, memory
promotions or routine decisions, and is never waited on for them. The owner reads finished
reports and makes the financial decisions; they settle only escalated conflicts.

- **Approval = independent corroboration.** At least two reviewers from different model families
  (default `gpt-6.1-sol` high + `claude-fable-5-1` high) get the same artifact and brief, blind to
  each other. Both approve → approved; record reviewers, verdicts and date as the approver.
- **Disagreement** → one adjudication round by a third model (`gpt-6-astra` high) given both
  outputs. Still conflicting → escalate to the owner with the specific point of conflict only.
- A panel model unavailable after one retry (e.g. "at capacity") is replaced by `gpt-6-astra`
  high, keeping the two reviewers in different families; note the substitution in the record.
- Deterministic checks run first; models never compute or invent numbers (see `invariants.md`).
- A review loop not converged after 3 rounds goes to the same panel to decide whether the residual
  findings block; only a panel conflict reaches the owner.
- Otherwise follow the orchestrator's stated recommendation without asking.

## When to review

Only at critical points: a spec or plan, a significant implementation chunk (phase or major
component), and before integrating anything touching financial logic or shared contracts. Routine
tasks — including routine Opus work — skip review.

## Review loop

1. Implementer finishes the chunk.
2. Reviewer reports **every** issue in one pass. Always put this in the brief: "List ALL issues you
   find in a single exhaustive report — do not stop at the first few, do not hold any back for a
   later round. Rank by severity." Reviewers tend to under-report; insist.
3. A fresh implementer round fixes all issues in one go.
4. A fresh reviewer round checks the fixes against the prior findings list and gives a verdict.
5. Repeat 3–4 until approved. Not converged after 3 rounds → escalate to the owner.
6. Loop closed → one **fresh** reviewer session (same model, no prior context) does a critical
   review of everything: nothing broken, nothing wrong. Real findings go to a fresh implementer
   round, then a re-review round verifies them.
7. Orchestrator runs verification and commits.

## Testing

See `.claude/rules/python/testing.md`. In short: the implementer writes tests with the code;
weight goes to integration and end-to-end; unit tests only for dynamic logic.
