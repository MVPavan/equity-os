# Review cycle — orchestration graph (v1) — SUPERSEDED

**Status: superseded by [`v2-build-pipeline.md`](v2-build-pipeline.md) on
2026-08-30.** Kept for adoption history and because its failure modes are the
justification for every change in v2.

v1 was never written as a graph document. It lived as the user-set orchestration
policy (revisions 1–3, 2026-08-27), stored in the `bd` memory
`project-sub-agent-policy-user-set-2026-08` and rendered as
`scratchpad/subagent-orchestration-policy.html`. This file records what it
actually was.

## The graph as it stood at revision 3

```text
PLANNING LOOP
└─ Sol high|xhigh(O) drafts/revises
   ⟳ Opus 5 med|high(C) inner review   ≤3 PER OUTER ROUND (counter resets on bounce)
   ⟳ Fable high(C) outer critique      ≤2 outer rounds   (fallback: Sol xhigh)
   └─ cap breach ──▶ stop, escalate to user with open findings
   └─ plan stays MUTABLE after approval

IMPLEMENTATION LOOP
└─ Terra high|xhigh(O) implements code AND its own tests
   ⟳ orchestrator deterministic gate (pytest / mypy --strict / ruff / hashes / smoke)
   ⟳ Sol high|xhigh(O) inner review    ≤3
   ⟳ Opus 5 med|high(C) outer critique ≤2
   └─ sign-off: Opus 5 high(C) + Sol xhigh(O), both must agree ──▶ user
```

Roster: orchestrator Opus 5 high (the main session) · planner Sol · plan review
Opus 5 · plan critic Fable · implementer Terra · impl review Sol · impl critic
Opus 5 · sign-off Opus 5 high + Sol xhigh.

## Why it was replaced

Evidence came from two audits on 2026-08-29/30: the `coding-ritual` phase-5
planning-loop post-mortem, and a metadata audit of 1,052 local session logs
(1.0 GB, streamed, deduplicated by `requestId`).

### 1. Reviewers were inside the loop

v1 iterated implementer → reviewer → implementer. Every lap was billed. The
audited phase-5 loop ran 17 rounds this way. v2 keeps exactly one loop —
implementer against a script — and makes every model review single-pass.

### 2. No test-writing stage

Terra wrote the implementation and the tests that check it. The
shared-misunderstanding defect class was entirely unguarded. v2 adds a
Claude-family test-writer whose output the implementer may not edit.

### 3. Hard-edge family violations

- `impl-reviewer ≠ implementer`: Terra implemented (OpenAI), Sol reviewed
  (OpenAI). Same family.
- `plan-critic ≠ plan-author`: the Fable-unavailable fallback sent the plan to
  Sol xhigh — the model that wrote it.

### 4. Caps fired correctly; overrides were made blind

The audited loop had v1's exact caps and they worked — its round-3 consolidation
records "Inner-round limit (3) reached", and the outer cap was spent at outer
round 2. It still reached 17 rounds because a human authorised continuation each
time **with no cost information in front of them.** The defect was override
governance, not the limit.

### 5. Orchestrator authored, and its edits caused defects

2 of the 4 findings in the final outer critique originated in orchestrator edits
to the plan (v15/v16). v2 forbids substantive orchestrator edits.

### 6. The MINOR rule was unsafe

v1 folded minors in without re-review. In the audited loop an r9 minor became an
r10 major because the repair was incoherent.

### 7. The context rule was unenforced and unsupported

v1 said retire at ~300k. Nothing checked it, and the orchestrator was measured at
351k average context per call on 2026-08-29. Cost across the audited sessions was
also non-monotonic in context age, so the threshold had no empirical basis.

### 8. Nothing was measured

No instrumentation, no budget, no health metric. The audit below had to be
reconstructed after the fact from raw logs.

## Measured cost under v1

Weighted using cache-read 0.1× and output 5× input.

| Actor | Window | Requests | Total tokens | Avg context/call | In : out | Cached |
|---|---|---:|---:|---:|---:|---:|
| Terra | lifetime, 46 rollouts | 2,695 | 370,480,314 | 137,000 | 301 : 1 | 97.42% |
| Sol | lifetime | — | 38,367,981 | — | 196 : 1 | 93.9% |
| Opus 5 | 2026-08-26 | 1,748 | 446,150,532 | 254,913 | — | — |
| Opus 5 | 2026-08-27 | 865 | 124,518,614 | 143,742 | — | — |
| Opus 5 | 2026-08-28 | 810 | 165,249,738 | 203,528 | 420 : 1 | 97.56% |
| Opus 5 | 2026-08-29 | 358 | 125,903,453 | 351,114 | — | — |

Opus over four days ≈ 107M weighted units against Terra's ≈ 52M lifetime. **The
orchestrator, not the implementer, was the largest single consumer** — and 2026-08-26
Opus alone (446M) exceeded Terra's entire recorded history.

The mechanism is not consumption but resubmission: 2,695 calls × ~137,000 tokens
of context reproduces Terra's input total exactly. Cost within a session is
quadratic in tool calls, because every call re-sends the whole conversation.

## What v1 got right, and v2 keeps

- Plan-stage caps of 3 inner / 2 outer, and escalation to the user on breach.
- Final sign-off by two models from different families, both of whom must agree.
- Rounds only for BLOCKER/MAJOR, with conservative tagging.
- A deterministic gate that runs before any reviewer.
- Every security rail: cookies never to a subagent, private captures never
  committed, synthetic grep-verified fixtures, explicit staging, 429/403 terminal.
