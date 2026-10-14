# Agent Stack and Review Loop

Owner directive (PavanMV, 2026-10-11; narrowed 2026-10-12; Sonnet added 2026-10-14). Fixed until the owner names a change —
do not switch models, efforts, or roles on your own judgment. Overrides older routing in skills,
`tools.md`, and memory where they conflict.

## Roles

Three models, nothing else (owner, 2026-10-12, extended 2026-10-14). No other model — no Fable
or Astra — implements, reviews or approves.

| Role | Model | Scope |
|---|---|---|
| Orchestrator | the main session | Scoping, planning, worker briefs, integration, final verification, commits, beads. May make tiny edits (a few lines) directly. |
| Implementer (complex) | `claude-opus-5-5`, effort `medium` | Anything complicated: cross-file design, financial logic, schema, fix rounds on review findings, plans, audits. |
| Implementer (simple) | `claude-sonnet-5-5`, effort `medium` | Anything trivial or straightforward: mechanical edits, renames, deletions already decided, doc updates, single-file changes with a clear spec. The orchestrator decides; when unsure, use Opus. |
| Reviewer | `gpt-6.1-sol`, effort `high` | Reviews specs, plans and significant implementation chunks; its approval is the approval. |

Dispatch every worker through the T3 Code orchestrator (`delegate_task`; results arrive by
notification). Not native subagents, not the Codex adapter. Sol's T3 option is
`reasoningEffort`, not `effort`.

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
reports and makes the financial decisions.

- **Approval = Sol's `APPROVE` verdict** at the end of the review loop. Record reviewer, verdict
  and date as the approver.
- Sol unavailable (e.g. "at capacity", rate limit) → retry later; never substitute another model.
- Deterministic checks run first; models never compute or invent numbers (see `invariants.md`).
- Otherwise follow the orchestrator's stated recommendation without asking.

Targets: Opus `{"providerInstanceId":"claudeAgent","model":"claude-opus-5-5","options":{"effort":"medium"}}`;
Sonnet same with `"model":"claude-sonnet-5-5"`; Sol `{"providerInstanceId":"codex","model":"gpt-6.1-sol","options":{"reasoningEffort":"high"}}`.

## Code size (owner, 2026-10-14)

Crisp, to-the-point solutions over lots of code. Every module must trace to a spec or acceptance
requirement; build the smallest thing that meets it. No speculative seams, proof layers or
guards for scenarios the spec does not require. Reviews judge necessity and size, not only
correctness: "could this be half the code?" is a valid finding.

## When to review

Only at critical points: a spec or plan, and once per **phase** at its end (owner, 2026-10-12:
lowered bar for speed). Stages inside a phase are not Sol-reviewed; the orchestrator verifies each
stage (tests, mypy, acceptance values) and commits it. The phase-end review covers everything the
phase built and runs the loop below. Routine tasks skip review.

## Review loop

1. Implementer finishes the chunk.
2. Sol reports **every** issue in one pass. Always put this in the brief: "List ALL issues you
   find in a single exhaustive report — do not stop at the first few, do not hold any back for a
   later round. Rank by severity." Reviewers tend to under-report; insist.
3. A fresh implementer round (Opus, or Sonnet if every fix is trivial) fixes all issues in one go.
4. A fresh Sol round checks the fixes against its prior findings list and gives a verdict. It
   raises new findings only for regressions or gaps that would make acceptance unpassable;
   smaller refinements come back as notes.
5. Repeat 3–4 until approved. Not converged after 3 rounds → the orchestrator rules on each
   residual finding (fix, or park with a recorded reason) and continues; only a question that is
   the owner's financial judgment goes to the owner.
6. Loop closed → one **fresh** Sol session (no prior context) does a critical review of
   everything: nothing broken, nothing wrong. Real findings go to a fresh implementer round, then a
   re-review round verifies them.
7. Orchestrator runs verification and commits.

## Testing

See `.claude/rules/python/testing.md`. In short: the implementer writes tests with the code;
weight goes to integration and end-to-end; unit tests only for dynamic logic.
