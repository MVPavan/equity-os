# Build loop — orchestration graph (v2)

**Audience: the orchestrator only.** Deliberately NOT a rule under `.claude/rules/`
and NOT listed in `.claude/project/docs-index.md` — loading this into every
agent's context is the exact cost this protocol exists to avoid. Workers receive
the parts that apply to them, in their brief.

Supersedes [`v1-review-cycle.md`](v1-review-cycle.md). Adopted with the user
2026-08-30 after auditing the phase-5 planning loop in the `coding-ritual`
project and our own four-day Claude/Codex token usage. Prior art:
`coding-ritual` `docs/graph-loops/build-loop.md` v4.1 — the shape below is
adapted from it, with our verification commands, our routing, and our
acquisition-workstream security rails.

## The graph

```text
PLAN (once per slice of work)
└─ Sol high|xhigh(O) drafts ⟳ Opus 5 med|high(C) ≤3 ⟳ Fable 5.1 high(C) ≤2 ──▶ user approves ──▶ FROZEN
   └─ work cut by DEPENDENCY LAYER: session/transport → parsing → evidence → CLI surface

PER SLICE   (only if the plan names the slice's public seam — see Seam rule)
│
├─ 1. Opus 5 med(C)  ──▶ tests/  acceptance tests, one per plan requirement ID
│                        reuses tests/fundamentals/*_support.py fixtures
├─ 2. Sol(O)         ──▶ reviews the TESTS: req-IDs-vs-names + assertion strength  [1 pass]
├─ 3. orchestrator   ──▶ grep requirement IDs vs test names     ← contract completeness, free
│     └─ RED PROOF   ──▶ run the new tests NOW; every one must FAIL   ← stands in for mutation
│
├─ 4. Terra(O)       ──▶ implement: "make these pass, do not edit tests/"
│                        runs TARGETED tests only; never the full gate
│                        MAY edit its own unit tests
│
├─ 5. scripts/verify.sh   ← deterministic, zero model tokens      [NOT BUILT YET]
│      └─ emits ≤8 lines + a ROUTE (see Routing)          ⟳ back to 4 until green
│
├─ 6. Opus 5 high(C) ──▶ reviews the IMPLEMENTATION  [only on green + teeth check passed]
├─ 7. Sol high(O)    ──▶ critic                      [after convergence]
│     └─ v0: 2 passes with one fix round between 6 and 7; 1 pass each once mutation lands
└─ 8. orchestrator   ──▶ verify only NEW blocker/major claims by hand

PER SLICE CLOSE
├─ live smoke — real subscriber session against ≥3 watchlist symbols, both bases
└─ sign-off — Fable 5.1 high(C) + Sol xhigh(O), both must agree ──▶ user
```

**The one loop that exists is step 4 ⟳ 5, and it costs zero model tokens.**
Every model review is single-pass except implementation review, which runs at 2
passes while mutation is absent (see "Mutation and its stand-in"). v1's cost came
from putting reviewers inside the loop; see
[`v1-review-cycle.md`](v1-review-cycle.md).

## Slices and the seam rule

A slice is **a set of modules buildable and gateable together whose dependencies
are already in the tree** — cut by dependency layer, never by feature. The
Screener workstream ran this way already: Slice 0 session/page → Slice 1
financials+schedules → Slice 2 company sub-documents.

**Seam rule.** Write acceptance tests before the implementer **iff the plan names
the slice's public seam** (the models, the error family, the CLI exit codes).
Otherwise the slice's first job is to freeze the seam and its tests follow.

For acquisition slices the seam is only nameable after ground truth exists.
Live capture is therefore a precondition of the plan stage, not a step inside a
slice, and it stays the orchestrator's own work — cookies never reach a subagent.

## Cross-family alternation

Claude(C) ↔ OpenAI(O) at every hand-off. Two families and five roles means not
all pairs can alternate, so they rank:

| Edge | Strength |
|---|---|
| test-writer ≠ implementer | hard — the shared-misunderstanding defect class |
| test-reviewer ≠ test-writer | hard — otherwise the contract is unchecked |
| impl-reviewer ≠ implementer | hard — **v1 violated this** (Terra implemented, Sol reviewed) |
| plan-critic ≠ plan-author | hard — **v1's Fable fallback violated this** (Sol critiquing Sol) |
| impl-reviewer ≠ test-writer | soft; **accepted violation** — both are Opus 5, split only by effort (med vs high) and a fresh session |

**Family is the constraint; effort and model size are free.** The user set both
Claude slots to Opus 5 on 2026-09-02, overriding the inherited "a Claude slot can
be Sonnet" guidance: the test contract and the implementation review are the two
places a cheap model's miss is most expensive, and while mutation is absent they
carry more of the assurance load than the doc originally assumed.

Roster: plan Sol / plan-review Opus 5 / plan-critic Fable 5.1 (fallback: Opus 5
high, **fresh session**, never Sol) / tests Opus 5 medium / test-review Sol /
implement Terra / impl-review Opus 5 high / critic Sol / sign-off Fable 5.1 high
+ Sol xhigh.

## How each role is invoked

**Every role is spawned as a CLI subprocess, not through the Agent tool.**
Claude-family roles go through `claude -p`; OpenAI-family roles go through the
codex-runner per [`.claude/commands/use-codex.md`](../../.claude/commands/use-codex.md).
Both are independent processes: their transcripts never enter the orchestrator's
context, only their final answer does. That is the "delegate EVIDENCE, keep
ANSWERS" rule enforced by the runtime rather than by discipline.

Adopted 2026-09-02. It supersedes Agent-tool dispatch for pipeline roles because
`claude -p` accepts `--model <full-id>` **and `--effort`**, which the Agent tool
cannot express (its `model` is a four-value alias enum and effort is
definition-layer only).

| Step | Role | Command |
|---|---|---|
| PLAN | plan author | `codex-run -e high "<brief>"` |
| PLAN | plan review | `claude -p --model claude-opus-5 --effort medium --permission-mode plan "<brief>"` |
| PLAN | plan critic | `claude -p --model claude-fable-5-1 --effort high --permission-mode plan "<brief>"` |
| 1 | acceptance tests | `claude -p --model claude-opus-5 --effort medium --permission-mode acceptEdits "<brief>"` |
| 2 | test review | `codex-run --role review "<brief>"` |
| 4 | implement | `codex-run --role implement -m gpt-5.6-terra -w "<brief>"` |
| 6 | impl review | `claude -p --model claude-opus-5 --effort high --permission-mode plan "<brief>"` |
| 7 | critic | `codex-run --role review -e xhigh "<brief>"` |
| close | sign-off | the Fable command + `codex-run -e xhigh`; both must agree |

`codex-run` = `node "$CLAUDE_PLUGIN_ROOT/scripts/codex-run.mjs"`, resolved by the
`codex-runner` skill.

### Briefing a CLI worker

A worker gets no conversation history. The brief is the whole contract, and it is
**paths, not pasted content** — the subprocess reads the repo itself:

```
Read <role-prompt path> and follow it.
Task: <one paragraph>.
Files you own: <explicit list>.
Verification: <exact commands>.
Constraints: <the security rails that apply to this role>.
Return: <the exact output shape wanted>.
```

Add `--add-dir <path>` for anything outside the cwd. Never paste a cookie, a HAR,
or a capture into a brief — cite the path and let the process read it, and never
brief a third-party CLI on either.

### Verified behaviour — Claude Code `2.1.258`, live runs 2026-09-02

- `--model` takes an alias (`fable`, `opus`, `sonnet`, `haiku`) or a full ID.
  `claude-fable-5-1` is accepted, and the alias `fable` resolves to it — both
  confirmed by reading `modelUsage` from `--output-format json`. Pin the full ID
  in pipeline commands; the alias is *latest* and will move under you.
- **Requires `2.1.258` or newer.** On the CLI this repo had before 2026-09-02,
  `claude-fable-5-1` was rejected as `unrecognized_model` and the run answered
  anyway on a fallback model. Check `claude --version` before trusting a roster.
- **HAZARD — an unusable model ID still exits 0.** On `2.1.258` a bogus ID no
  longer silently substitutes a model, but it returns a result envelope with
  zero tokens, `total_cost_usd: 0`, no `modelUsage`, and **exit status 0**. A
  caller that only checks the exit code sees an empty answer as a completed role.
  **Mitigation, mandatory for sign-off and both review steps:** pass
  `--output-format json` and assert `modelUsage` contains the intended model
  before accepting the result. This is also how the two facts above were proven.
- `--effort` accepts `low|medium|high|xhigh|max` and warns loudly on anything
  else (`Unknown --effort value … ignoring it`), so a valid value is applied
  rather than silently dropped. Effort is still not observable from inside the
  child.
- Codex model IDs are fixed by `use-codex.md`: `gpt-5.6-sol` (account default,
  `-m` omittable), `gpt-5.6-terra` for large implementations, `gpt-5.6-luna` for
  cheap fan-out. Never probe the CLI for model IDs.

## verify.sh — deterministic, runs BEFORE any reviewer

**Built 2026-09-02: [`scripts/verify.sh`](../../scripts/verify.sh).** Reviewing
on a red gate spends a reviewer on what a script does free.

```
scripts/verify.sh red  <slice> <pytest-target>...   capture the red proof
scripts/verify.sh gate <slice>                      run the gate
```

`gate` runs six checks, cheapest first, in ~28s on a clean tree:

1. **tests-untouched** — every acceptance file is re-hashed against the SHA-256
   recorded in the red proof. Hashing rather than `git diff` because a new test
   file is usually untracked, where `git diff` sees nothing.
2. **red proof** — `scratchpad/gate/<slice>-red.json` exists and every
   acceptance test in it was red before the implementer ran.
3. **gate** — the four commands exactly as `.claude/project/verification.md`
   declares them: `uv run pytest tests/fundamentals -q` · `uv run ruff check src
   tests/fundamentals` · `uv run ruff format --check src tests/fundamentals` ·
   `uv run mypy --strict src`. A gate that checks a different scope than the
   project claims is a gate that lies, so the two files must stay identical.
4. **skip guard** — the skip count may not exceed the pinned baseline (7,
   measured 2026-09-02: all opt-in live fetches or the absent OCR wheel).
   Adding `@pytest.mark.skip` is the cheapest way to fake a green gate; this is
   the only check here with no counterpart in the prior art.
5. **diff coverage** — `--cov-report=json` missing lines ∩ `git diff -U0 HEAD`
   changed lines, plus every line of an untracked new `src/` file.
6. **rails** — nothing under `scratchpad/` or `data/` tracked · no machine-local
   path · no `sessionid`-shaped literal · no `.py` over 800 lines · no run of
   ≥60 characters shared verbatim between a changed file and any page under
   `scratchpad/screener_discovery/`, which is how a pasted private capture is
   caught without needing a list of real holder names.

**Bounded output is the contract.** At most 8 status lines and exactly one
`ROUTE:` line. Test names are capped at 4 plus a count; tracebacks and the full
lists go to `scratchpad/gate/<slice>-<ts>.log`. An unbounded list of 37 node IDs
is the same context poisoning as a traceback — a red gate is the one path that
can put thousands of tokens into the orchestrator's context, where every later
call in the session re-sends them.

**Exit code is the route**, so a caller branches without parsing text:
`0 PASS` · `1 IMPL` · `2 CONTRACT` · `3 STOP` · `4 DIAGNOSE`. Worse routes win,
and `STOP` is never downgraded by a later check.

Self-tested 2026-09-02 against four cases, all correct: an acceptance test that
already passes routes CONTRACT; genuinely red tests produce the proof; an
implementer editing an acceptance test is caught as `modified`; deleting one is
caught as `deleted`.

## Mutation and its stand-in

**Prior-art check, 2026-09-01.** `coding-ritual` has no `scripts/verify.sh`, no
mutation script, and no `scratchpad/gate/`. Its v4.1 document is aspirational on
exactly this component — the only `verify.py` in that repo is product code
(`workflow_interpreter/supervisor/verify.py`, the interpreter's own §7.3 evidence
engine), not a build gate. We are not adopting a proven mechanism; we would be
first to build it. So the claim "single-pass reviews are safe *because* mutation
proves the tests have teeth" is an argument, not a measured result.

Mutation answers one question: **would the tests notice if the code were wrong?**
Two deterministic substitutes answer most of it for far less work, and v0 ships
with those instead. **Approved by the user 2026-09-02** as an interim measure —
mutation remains the target state, not a discarded idea.

### Substitute 1 — the red proof (kills vacuous tests)

Because tests are written *before* the implementer runs, they are naturally red
at that moment. Capture it rather than reconstruct it.

After step 3, before Terra is dispatched:

```
uv run pytest <the new acceptance tests> -q
```

Every acceptance test MUST fail. Record test names and outcomes to
`scratchpad/gate/<slice>-red.json`. **Any acceptance test that PASSES before the
implementation exists is vacuous** — it asserts nothing the code controls — and
routes to the orchestrator as a contract gap.

`verify.sh` later asserts that file exists, covers every acceptance test by name,
and that all of them were red. No worktrees, no stashing, no re-running history.

### Substitute 2 — diff coverage (kills unexercised code)

```
uv run pytest tests/fundamentals --cov=src/fundamentals --cov-report=term-missing
```

Intersect the missed lines with the changed lines from `git diff`. Any line the
slice added or changed that no test executes is listed by file:line and routes to
the implementer.

### What this does and does not buy

| Defect class | Caught by |
|---|---|
| Test asserts nothing meaningful | red proof |
| New code path never exercised | diff coverage |
| Exercised and asserted, but too weakly (off-by-one, wrong sign, wrong boundary) | **only mutation** — uncovered mechanically in v0 |

The residue is covered by judgment, not machinery: slice step 2 already has Sol
reviewing the tests for **assertion strength**. That is the human-judgment form of
the same check.

**Consequence, and it is not optional:** while mutation is absent, implementation
review runs at **2 passes, not 1** — Opus 5 high, then Sol as critic, with one fix
round permitted between them. Dropping to single-pass is earned by landing
mutation, not by adopting this document.

### When we do build it

Do not hand-roll the mutant planting v4.1 describes. Python already has
`mutmut` and `cosmic-ray`; scope either to the slice diff rather than the package.
That turns "half a day of tree-copying machinery" into a scoped tool invocation,
and it is the only remaining step to single-pass reviews.

### Routing

| Verdict | Route |
|---|---|
| gate FAIL | implementer |
| acceptance test PASSED before implementation (vacuous) | orchestrator — a CONTRACT gap, not a bug |
| changed line in `src/` executed by no test | implementer |
| *(when mutation lands)* mutant survived in an ACCEPTANCE test | orchestrator — CONTRACT gap |
| *(when mutation lands)* mutant survived in a UNIT test | implementer |
| protected-file hash changed | **STOP** — orchestrator, policy breach |
| fixture grep hit real data | **STOP** — orchestrator, security rail |
| live smoke 429/403 | **STOP** — terminal, escalate to user, never work around |
| >3 failures, mypy avalanche, unfamiliar error class | diagnostician subagent → ONE paragraph |

**No standing observer agent.** A fresh observer must be onboarded to judge a
failure, and onboarding costs more than a 6-line shaped summary. Routing is the
irreducible orchestrator job because context is the only thing the orchestrator
holds that a fresh agent does not. **Delegate EVIDENCE, keep ANSWERS.**

**Why the orchestrator runs no gate by hand:** every reason to re-run it requires
only that something *other than the implementer* run it. A script satisfies that.

## What each check answers — none replaces another

| Question | Answered by |
|---|---|
| Does the code do what the tests say? | the implementer's own targeted run |
| Did anything else break; does it typecheck and lint? | the gate inside verify.sh |
| Would the tests notice if the code were WRONG? | v0: red proof + diff coverage; later: mutants |
| Does it work against the real subscriber surface? | live smoke, ≥3 symbols, both bases |
| Was a required behaviour never written at all? | requirement-IDs-vs-names grep |
| Did we leak private data or touch a protected file? | the rails in verify.sh step 3 |

### Known blind spots

- **Mutation cannot catch a double that shares the code's misunderstanding.**
  Only executing the real collaborator (a live fetch) finds these.
- **Mutation cannot catch a scenario nobody wrote** — the IDs-vs-names grep is
  the only cheap check for this.
- **A killed mutant proves a test CAN fail, not that it tests what its name
  claims.** Read the body.
- **Synthetic fixtures cannot prove a live-surface fact.** Every surface claim
  traces to a capture under `scratchpad/screener_discovery/`, never to a fixture.
- Reviewer claims are not evidence. Verify NEW blocker/major claims by hand;
  skip re-verifying closed ones.

## Severity and rounds

Rounds exist only for BLOCKER/MAJOR. Tag conservatively — behaviour, bound, or
security is MAJOR.

MINORs get no round of their own, **but any semantic change made because of a
MINOR must appear in the next reviewed diff.** Only genuinely editorial changes
skip re-review. v1's blanket "minors are not re-reviewed" is unsafe: in the
audited phase-5 loop an r9 minor was folded into a repair and r10 found that
repair materially incoherent.

## The orchestrator does not author

The orchestrator consolidates findings, routes, runs the deterministic gate, does
all live capture, and commits. It does **not** make substantive edits to the plan
or the implementation. Any such edit voids the current approval and re-enters
review. In the audited loop, 2 of the 4 findings in the final outer critique
originated in orchestrator edits.

## Economics (why the shape is what it is)

Cost within one agent session is **quadratic in tool calls**: cumulative input ≈
N × C_final/2, because every call re-sends the whole conversation.

Measured 2026-08-26 → 08-29 (see [`v1-review-cycle.md`](v1-review-cycle.md) for
the full audit):

| Actor | Avg context per call | Input : output | Cached share |
|---|---:|---:|---:|
| Terra (implementer) | 137,000 | 301 : 1 | 97.4% |
| Opus 5 (orchestrator, 08-28) | 203,528 | 420 : 1 | 97.6% |
| Opus 5 (orchestrator, 08-29) | **351,114** | — | — |

**Health metric: average context re-sent per call. Investigate above 250k.**
Token totals are the wrong metric — 97% of them are cheap cache reads, and the
headline overstates real cost by roughly 7×.

Consequences already adopted:

- Retire on **measured context**, not a nominal threshold. v1's unenforced 300k
  rule was being exceeded at the moment it was audited.
- **Implementer tool-call cap.** Because cost is quadratic, splitting one
  251-call session into three cuts its input by ~67%, not ~0%.
- **The orchestrator reads nothing large directly.** Any multi-file sweep, log
  scan, or corpus analysis goes to a cheap subagent that returns conclusions
  only. A 1.0 GB / 1,052-file audit cost 53k tokens as a Sonnet subagent; run
  inline it would have entered orchestrator context and been re-billed on every
  remaining call of the session.

## Security rails — unchanged from v1, non-negotiable

- Session cookies and the owner HAR never reach any subagent, prompt, log, or
  third-party CLI.
- Private captures are readable by agents for ground truth, never committed.
  Fixtures are synthetic and grep-verified.
- Explicit git staging only — no `git add .`, no `-A`, no `--no-verify`, no
  force-push.
- 429/403 is terminal. Nothing here authorises working around a block.
