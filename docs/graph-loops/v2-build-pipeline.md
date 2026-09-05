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
├─ 0. orchestrator   ──▶ live capture ──▶ GROUND-TRUTH.md   ← cookies never leave here
├─ 1. Sol high|xhigh(O) drafts                              ← cap ≈250 lines
├─ 2. Opus 5 high(C) ──▶ FIRST CONTACT, then coherence            [1 round]
│        walks every plan rule against the captures BEFORE reasoning about it
├─ 3. Fable 5.1 high(C) ──▶ outer critic                          [1 round]
├─ 4. orchestrator   ──▶ every line marked INFERENCE gets a live probe from the
│                        reserved budget, or is rewritten as an open question
└─ user approves ──▶ FROZEN
   └─ work cut by DEPENDENCY LAYER: session/transport → parsing → evidence → CLI surface

PER SLICE   (only if the plan names the slice's public seam — see Seam rule)
│
├─ 1. Opus 5 med(C)  ──▶ tests/  one test function per BEHAVIOUR, ≈30 lines each
│                        reuses tests/fundamentals/*_support.py fixtures
├─ 2. Sol(O)         ──▶ reviews the TESTS: requirement coverage + assertion strength  [1 pass]
├─ 3. orchestrator   ──▶ grep requirement IDs vs test names     ← contract completeness, free
│     └─ RED PROOF   ──▶ run the new tests NOW; every one must FAIL   ← stands in for mutation
│
├─ 4. Terra(O)       ──▶ implement: "make these pass, do not edit tests/"
│                        runs scripts/verify.sh ITSELF, in its own loop
│                        MAY edit its own unit tests
│      └─ ⟳ until green — costs the orchestrator nothing
│
├─ 5. orchestrator   ──▶ scripts/verify.sh ONCE, at acceptance
│                        the two things no implementer can prove about itself:
│                        the red proof exists, and the acceptance hashes still hold
│
├─ 6. Opus 5 high(C) ──▶ reviews the IMPLEMENTATION  [only on green]
├─ 7. Sol high(O)    ──▶ critic                      [after convergence]
│     └─ v0: 2 passes with one fix round between 6 and 7; 1 pass each once mutation lands
└─ 8. orchestrator   ──▶ verify only NEW blocker/major claims by hand

PER SLICE CLOSE
├─ live probe — every shape the plan could only infer, from the reserved budget
├─ live smoke — real subscriber session against ≥3 watchlist symbols, both bases
└─ sign-off — Fable 5.1 high(C) + Sol xhigh(O), both must agree ──▶ user
```

**The only loop that exists lives inside step 4, and the orchestrator is not in
it.** Every model review is single-pass except implementation review, which runs
at 2 passes while mutation is absent (see "Mutation and its stand-in"). v1's cost
came from putting reviewers inside the loop; see
[`v1-review-cycle.md`](v1-review-cycle.md).

### Revised 2026-09-02 after the Slice 3 retrospective

Slice 3 shipped correct code, but it cost ~$39 of Claude plus ~1.0M Codex tokens
for 610 source lines and produced a 3:1 test-to-source ratio against 0.85:1 for
the three slices before it. A Fable 5.1 strategic review
(`scratchpad/slice3/fable-strategic.json`) found the shape, not the effort, was
wrong, and the graph above is the corrected one. What changed and why:

| Was | Now | Because |
|---|---|---|
| plan review ≤3 inner + ≤2 outer | 1 inner + 1 outer, inner does FIRST CONTACT first | 3 coherence rounds approved the plan without opening a capture; the round that finally did found 4 of the slice's 10 blockers |
| an INFERENCE could be frozen and tested | it cannot | SL3-10 was frozen while labelled an inference, survived 7 rounds, and refused every legitimate 1-to-50-row screen |
| one acceptance test per requirement ID | one per behaviour | 14 IDs became 14 functions averaging 97 lines; the first failing assert hides the rest |
| implementer ran targeted tests; orchestrator ran the gate | implementer runs the gate; orchestrator runs it once at acceptance | the implementer's honest "32 passed" was true while ruff was failing — because a sandbox fault stopped it running ruff at all |
| uncovered line → implementer | uncovered line → orchestrator, advisory | an implementer briefed "do not edit tests/" has no legal move but to call it a contract gap, which is exactly what it did |

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

## Freezing rule — no inference survives a freeze

**A plan line the plan itself cannot support from a capture may not be frozen,
and may not have an acceptance test written against it.** It gets a live probe
from the slice's request budget, or it is rewritten as an open question and the
behaviour is left unconstrained until evidence exists.

This is the most expensive lesson of Slice 3 and it was entirely self-inflicted.
The plan wrote, in as many words, *"Requiring the scoped active numeric anchor on
a single-page populated result is an explicit inference; contrary live evidence
requires plan revision"* — and then froze the rule, tested it, implemented it,
and deferred the check to slice-close smoke. All captured populated pages
happened to be multi-page, so the inference looked safe. It was not: Screener
renders no pagination controls at all when a result fits on one page, so the
frozen rule refused every legitimate 1-to-50-row screen. It survived seven plan
rounds, a test rewrite and a full implementation. One HTTP request would have
killed it before the freeze.

Marking something an inference is not a mitigation. It is a reason to spend a
request or to stop writing the rule.

### Request budget

The subscriber boundary is ~40 authenticated requests before rate limiting, and
**429/403 is terminal**. That forbids iteration, not probing, and the two get
confused. Slice 3 spent 4 requests and had roughly 36 unused.

Per slice: **~10 requests for capture, 5 reserved for probes** — some spent
before the freeze on flagged inferences, the rest at slice close against every
shape the plan could only infer. A probe is one request that decides a rule.
Refusing to spend one is how a coherent, wrong plan reaches production.

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
| PLAN | plan review (first contact, then coherence) | `claude -p --model claude-opus-5 --effort high --permission-mode plan "<brief>"` |
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

**Always give a codex worker `UV_CACHE_DIR=.uv-cache`** in every `uv` command you
put in its brief. This machine's real cache is `/data/all_cache/uv_cache`, which
is outside the workspace, so `workspace-write` mounts it read-only and every
`uv run` that needs to resolve anything dies with
`failed to open file … Read-only file system (os error 30)`. Slice 3's
implementer could therefore not run `ruff` or `mypy` at all, and reported
"32 passed" — true, and missing the two failing checks it had been unable to
start. `.uv-cache/` is gitignored. This one line is why the implementer can now
own its own verification.

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
scripts/verify.sh red      <slice> <pytest-target>... capture the red proof
scripts/verify.sh baseline <slice>                    record a refactor baseline
scripts/verify.sh gate     <slice>                    run the gate
scripts/verify.sh reseal   <slice> <proof-file>       reopened contract only
```

**`reseal` is the only legitimate way an acceptance file changes after its red
proof was taken**, and it exists because reopening a contract is not a rare
event — Slice 3 needed it when a frozen rule turned out to refuse every
legitimate single-page result. It re-hashes the acceptance files and touches
nothing else; the recorded outcomes stay exactly as captured, because they *are*
the proof and this is not a way to re-take it. It refuses without a proof file
naming what was amended and showing the amended assertion failing against the
implementation it was wrong about. Without that, resealing and an implementer
quietly rewriting its own contract are the same operation.

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
5. **diff coverage — advisory only** — `--cov-report=json` missing lines ∩
   `git diff -U0 HEAD` changed lines, plus every line of an untracked new `src/`
   file. Reported, never routed, never failing. Note the `HEAD` in that
   intersection: it is a **pre-commit** check wearing a standing check's clothes.
   The moment the slice is committed its uncovered lines vanish from the gate,
   so do not read a later green as evidence they were covered.
6. **rails** — nothing under `scratchpad/` or `data/` tracked · no machine-local
   path · no `sessionid`-shaped literal · no `.py` over 800 lines · no run of
   ≥60 characters shared verbatim between a line this change ADDED and any page
   under `scratchpad/screener_discovery/`, which is how a pasted private capture
   is caught without needing a list of real holder names. The two fixture rails
   (that one and the identifier rail below) read only added lines — the `+` side
   of `git diff -U0 HEAD` plus the whole content of an untracked file. The
   path and cookie rails stay whole-file: a secret anywhere in a file about to
   be committed is a STOP whoever wrote it.

**Refactor slices take the `baseline` route instead of the red proof.** A pure
refactor adds no behaviour, so it has nothing to prove red and ROUTE PASS is
unreachable by construction. `scripts/verify.sh baseline <slice>` runs the suite
and records `scratchpad/gate/<slice>-baseline.json` — the passed and skipped
counts and the sorted node id of every test that passed; it refuses unless the
run is green. The gate then swaps check 2 for a **test-set** check: the set of
node ids passing now must equal the recorded set, and a single id added or
removed routes CONTRACT ("a refactor changed the test set"). Exactly one proof
may exist per slice; both a red proof and a baseline is itself a CONTRACT.
Checks 1 and 3–6 are unchanged on either route. **What the baseline cannot see:**
an assertion rewritten in place, under the same node id, passes the test-set
check. That is the route's stated limit, not a gap — a change that needs new
assertions is behaviour and takes the red proof. Both proof files live under
`scratchpad/gate/`, which is the orchestrator's; an implementer that deletes or
writes one has left its brief.

**The fixture rails scan added lines because whole-file scanning has a standing
false positive.** Editing one import line in
`tests/fundamentals/test_comparatives.py` fired the identifier rail on `2023`, a
calendar year the file had carried since before the rail existed. A leak is
something a change writes; what was already in the file is not this slice's, and
a rail that re-accuses every prior line trains its reader to wave STOPs through.

**The identifier rail false-positives on short ids, and that is the right
trade.** It word-matches every 4-plus-digit company id found in the captures
against the lines this change added under `tests/`. Real companies have ids as short as four digits, so
an ordinary number in prose can collide — a docstring saying "a 1012-test gate"
tripped it against `/company/1012/`. Triage a STOP by asking *where* the number
appears before assuming a leak: a fixture value is a real finding, a test count
in a comment is not. Do not narrow the rail to reduce noise. A missed leak is
unrecoverable; a false STOP costs two minutes.

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

## Acceptance tests — what to write, and what not to

**One test function per behaviour, not per requirement ID.** Requirement IDs are
a plan's bookkeeping; they are not a test plan. Slice 3 mapped 14 IDs to 14
functions averaging 97 lines against a house average of 28, and the cost is not
just length: pytest stops at the first failing assert, so a 97-line function
reports one defect per run and hides the rest behind it. Aim near 30 lines. The
IDs-vs-names grep at step 3 checks that every ID is *covered*, which does not
require that every ID own exactly one function.

**Do not write these.** They passed review in Slice 3 and should not have:

- **Model-field inventories** — asserting the exact set of fields on a Pydantic
  model. This pins the plan's shape, not any behaviour, and fails on every
  harmless addition.
- **Forbidden-flag matrices** — one case per CLI flag that must not exist. The
  parser either accepts a flag or does not; enumerating absences tests argparse.
- **Enum membership checks** — asserting a `StrEnum` contains the members it is
  written to contain.
- **Assertions about the fixture builder** rather than about the code under test.

The test each of these should have been: does the seam *refuse* the thing the
field, flag or member exists to prevent?

**Do write these.** Also from Slice 3, and these are why its tests have real
teeth where earlier slices' do not:

- **Receiver identity** — assert *which* collaborator was called, not only that
  a call happened.
- **Decoy values** — a fixture href pointing at page 999 that a correct
  implementation must never follow. A test that cannot be fooled is worth five
  that merely pass.
- **Minimal fixtures** — the smallest shape that still satisfies the production
  selector, so the test fails when the selector quietly widens.
- **Write-order recording** — for anything with a rollback or no-clobber
  guarantee.

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

### Substitute 2 — diff coverage (kills unexercised code) — ADVISORY

```
uv run pytest tests/fundamentals --cov=src/fundamentals --cov-report=term-missing
```

Intersect the missed lines with the changed lines from `git diff`. Any line the
slice added or changed that no test executes is listed by file:line **as an
advisory line in the report, and routes to the orchestrator for triage — never
to the implementer, and never as a failing route.**

Downgraded 2026-09-02. Two faults, one design and one arithmetic:

- **It had no legal resolution.** The implementer is briefed "do not edit
  `tests/`", so an uncovered line leaves it exactly one move: call the gap a
  contract problem and hand it back. Slice 3's implementer classified all seven
  uncovered lines that way. Four were ordinary validation reachable by calling a
  function with bad input. That misclassification was **structurally forced, not
  dishonest** — the brief left no other answer.
- **Coverage is not the metric, and treating it as one manufactures tests.**
  It produced 4 of Slice 3's 41 tests, under 5% of the suite — a small
  contributor, but every one of them existed to satisfy the check rather than to
  pin a behaviour someone cared about.

It is kept, not deleted, because it earns its keep occasionally: one of those
four found a branch the implementer had called dead and which is in fact
reachable. An advisory line costs nothing; a route costs a round.

**Documented-uncovered lines are legitimate.** A line whose only trigger is a
path-traversal construction or a post-write race does not need a test written to
chase it. Record why, in the commit, and move on.

### What this does and does not buy

| Defect class | Caught by |
|---|---|
| Test asserts nothing meaningful | red proof |
| New code path never exercised | diff coverage (advisory — it reports, you judge) |
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
| changed line in `src/` executed by no test | orchestrator — advisory, does not fail the gate |
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

**Who runs the gate.** The implementer runs `scripts/verify.sh` in its own loop —
that is the loop, and it costs the orchestrator nothing. The orchestrator runs it
**once, at acceptance**, for the two things the script proves that no implementer
can prove about itself: that the acceptance files still hash to what the red
proof recorded, and that the red proof exists at all. Eight lines of output.

Revised 2026-09-02. The earlier rule — implementer runs targeted tests, script
runs the gate — assumed the implementer *could* run the gate and was merely not
asked to. It could not: the read-only `UV_CACHE_DIR` fault above stopped `ruff`
and `mypy` from starting. Fix the sandbox and most of this argument dissolves.

**But the implementer's counts are not authoritative, and this is measured, not
theoretical.** In the first run under the new rule the implementer reported
`996 passed, 14 skipped` where the same tree on the host gave `1003 passed, 7
skipped` — seven tests skip inside the codex sandbox that run outside it — and
its own `verify.sh` invocation reported `0 <= baseline 7` skips, a third number
again. Nothing was wrong with the code and nothing was misreported; the sandbox
is simply a different environment.

Two consequences. **The skip-guard baseline is host-calibrated**, so an
implementer can see it pass on a number the host would fail, or fail on a number
the host would pass. And **the orchestrator's single acceptance run is what
decides**, not because the implementer is untrusted, but because it is the only
run taken in the environment the baseline was measured in. Read the
implementer's gate output as a signal that it converged, never as the result.

## What each check answers — none replaces another

| Question | Answered by |
|---|---|
| Does the code do what the tests say? | the implementer's own targeted run |
| Did anything else break; does it typecheck and lint? | the gate inside verify.sh |
| Would the tests notice if the code were WRONG? | v0: red proof, plus advisory diff coverage; later: mutants |
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
- **Cross-family alternation does not diversify evidence when every role reads
  the same `GROUND-TRUTH.md`.** Five roles across two model families all
  inherited Slice 3's single derived document, so a fact absent from it was
  absent from every one of them. Diversity of *models* is not diversity of
  *evidence*. The only cure is the first-contact pass and the probe budget.

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
