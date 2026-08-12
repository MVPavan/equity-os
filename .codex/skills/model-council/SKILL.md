---
name: model-council
description: "Use when the user asks to run one task through named council members with a named judge: several agents or models solve the same task independently, then the judge consolidates. Trigger on model council, convene the council, or any brainstorming, research, design, or review request that names both members and a judge. Do not run without user-named members and judge."
---

# Model Council

User-named council members each solve the same task independently and blind to each other; a user-named judge consolidates their reports. The deliverable always contains every member's full report AND the judge's consolidation. Unlike `perspective-council` (one model, five lenses), members here are distinct agents/models the user picks.

**Hard requirement:** the user names the members and the judge — every time. If either is missing, ask in plain chat text (never a modal) and wait. Never substitute defaults.

## Member resolution

| User says | Run as |
|---|---|
| codex, gpt, or no specific Codex model | Fresh native Codex subagent inheriting the session model |
| A model explicitly advertised by the active spawn surface | Fresh native subagent with that model override |
| Any other named model or provider | Ask the user how to reach it; do not substitute |

The judge resolves the same way; it gets a fresh agent even if its type matches a member's.

## Process

1. **Brief.** Write one shared task brief: the task, pointers to relevant files/context, constraints, and the deliverable — "a self-contained report: your solution, reasoning, and open questions." Every member receives it verbatim; no per-member steering unless the user asks.
2. **Dispatch.** All members in parallel, one fresh agent each, none sees another's output. Save each report verbatim to `<run-dir>/<member>.md` (default `scratchpad/council/<topic-slug>/`; user may name a path). A member that fails gets one retry, then report the gap loudly — never backfill with your own answer.
3. **Judge.** The judge agent gets the brief plus all reports, attributed by member name. It consolidates — it does not re-solve: where members converge; where they conflict, which position wins, and why; the best-of synthesis / recommended answer; gaps no member covered. Save to `<run-dir>/consolidation.md`.
4. **Deliver.** In chat: the judge's consolidation in full, a one-paragraph position summary per member, and paths to all saved reports. If the reports are short or the user wants everything inline, include them in full. Never truncate or drop a saved report.

## Rules

- Identical brief to every member; independence is the point.
- Judge overrides a majority only with stated reasoning.
- Attribute the judge's inputs by name — anonymization is for `perspective-council`, not here; the user chose these members and wants to compare them.
