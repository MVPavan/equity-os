# Handoff: autonomous Codex run on the backend core (2026-10-13)

Brief for one long, unattended Codex session. It continues the backend core from where the Claude
session paused. Read this file first, then follow the repo read order in `AGENTS.md`.

## Authority (owner, 2026-10-13)

- Work autonomously. Never wait on the owner. If something is ambiguous, pick the fail-closed
  option, write the choice into the phase plan's build notes, and keep going.
- **You may commit to `main`** each verified item (small commits, explicit file staging). This
  overrides the Beads conservative profile for this run. **Do not push.**
- Review: this run replaces the Claude/Sol stack in `.claude/rules/core/04-agent-stack.md`. Use
  fresh Codex sub-sessions as the reviewer where the queue asks for review. In each review brief,
  say: "List ALL issues you find in a single exhaustive report. Do not stop at the first few. Rank
  them by severity." Record the reviewer as "Codex session (handoff run)". The owner will have
  these reviews re-checked by Sol later.

## Hard rules (never break)

- Never commit `.env` or credentials. Never print secrets.
- Stage explicit files only. No `git add .` or `-A`, no force, no `reset --hard`, no `clean`, no
  amend, no push.
- Never touch the `equity_os` database or the Postgres data directory. Tests use `eqos_test_*`
  databases only. No destructive docker commands.
- Never modify `data/raw/`. Use retained captures only. There are no vendor credentials, so make no
  live vendor fetches.
- Never edit applied migrations `0001`–`0004`. New schema means a new migration. `0005` is
  uncommitted work in progress, so you may still edit it until it is first committed. The next
  free migration number after that is `0006`; the roadmap's `0002_review_queue.sql` name is stale.
- Financial logic: exact `Fraction` arithmetic, fail closed, never zero-fill, never backdate.
  Knowledge times come from `eqos.store_now()`. Expected values come from source documents, never
  from code output (`.claude/project/invariants.md`).
- Repo-relative paths only in committed files. `scratchpad/` is never committed.
- Commit trailer: `Co-Authored-By: Codex <noreply@openai.com>`.

## Start state

- Last commit is the one that adds this file. The working tree has **uncommitted partial fixes**
  for the D1a phase-end review (Areas A and C, plus `migrations/0005_…sql`). Keep them. They are
  the starting point, not noise.
- Findings and their per-item status: [`reviews/D1a-phase-review-r1.md`](reviews/D1a-phase-review-r1.md).
- PostgreSQL 18 runs in compose (see `.claude/project/verification.md` for the setup and commands).
- Verification commands: `uv run ruff check src tests/fundamentals`,
  `uv run ruff format --check src tests/fundamentals`, `uv run mypy --strict src`,
  `uv run pytest tests/fundamentals`. There are two known pre-existing failures in
  `test_source_intake_store` (tracked separately). Every other failure is yours to fix.

## Work queue (in order; one item at a time)

Each item loops like this:
1. Write or adjust the test first.
2. Implement.
3. Run the four checks.
4. Commit.
5. `bd close` / `bd update` with `--actor codex`.
6. Append one line to the log at the bottom of this file and commit it.

1. **Make the tree green.** Fix the 3 mypy errors. Get the suite back to only the known failures.
   Commit the Area A work so far (including migration 0005) as one commit.
2. **Finish Area A**, then **Area C**, then **Area B**. The file scopes overlap, so work strictly
   in sequence. Take every finding to done as its "Fix:" line describes. Area B also owns the
   selection side of A4. Exit check: `test_compare_tracer.py` is green with the Apar values
   unchanged:
   - PBT 340.56 / 340.53 crore;
   - OPM 8.06%;
   - revenue 5,715.42 crore;
   - total expenses 5,402.29 crore;
   - profit 251.70 crore;
   - EPS 62.66.
3. **Phase review loop for D1a.** A fresh reviewer session checks every finding against the code.
   Fix any residuals, then re-review. After 3 rounds without convergence, rule on each residual
   finding (fix it, or park it with a recorded reason). Then run one fresh critical review of the
   whole phase. Close the D1a epic `eqos-3f9`. Update the Progress table in
   [`roadmap.md`](roadmap.md).
4. **D1b plan.** Use the planning skill (Elaborate) on the D1b roadmap row. Save it to
   `plans/D1b.md` and get it reviewed by a fresh session. Then run
   `scripts/verify.sh red <slice>` before any D1b code.
5. **D1b stages**, one at a time, following the plan. Note: Screener and Tijori work uses retained
   captures under `data/raw/watchlist/` only.
6. Continue down [`docs/backend-roadmap.md`](../../backend-roadmap.md) §3 (D2 onward) only after
   D1b's exit test is green.

## Stop conditions (park, log the reason, move to the next unblocked item)

- Anything that needs live vendor access or new credentials.
- The D2 cutover or anything else that writes to the real `equity_os` database.
- PILOT-12 and other owner-time steps.
- A question that is the owner's financial judgment.

## Progress log

Append `YYYY-MM-DD HH:MM — item — result — commit` below. A new session resumes from the last line.

- 2026-10-13 — handoff written; D1a fixes paused mid-Area A (see reviews file).
- 2026-10-13 03:49 — goal preparation (`eqos-lob`) — [dated activation goal](../../goals/2026-10-13-autonomous-backend-completion.md) and index verified; fresh-context readback PASS; implementation not started, next is queue item 1 — 2e65b1d
