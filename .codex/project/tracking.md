# Issue Tracking

This repo uses **bd (beads)** for durable issue tracking.

- **Backend:** embedded Dolt (`.beads/`), database `equity_os`.
- **Issue prefix:** `equity-os` (auto-detected; issues like `equity-os-klx`).
- **Sync remote:** `git+https://github.com/MVPavan/equity-os.git`
  (`sync.remote` in `.beads/config.yaml` — the repo's own git remote).
- **JSONL export:** `export.auto: true`.
- **Initialized:** 2026-08-12 during adoption. History, verified facts only:
  an earlier `bd init` commit (f881e51) was reverted in b3e4570 (reason not
  recorded in git). At adoption time the untracked working-tree
  `.beads/config.yaml` carried a stale `sync.remote` pointing at a nonexistent
  `agent-os.git`, which made `bd init` fail on clone; the remote was corrected
  and `bd init` re-run successfully (c9dade1). Note `bd init` auto-commits its
  integration files (`.beads/`, `.agents/`, `.codex/settings.json`, `.codex/`
  config, `AGENTS.md`, `CLAUDE.md`) and `.beads/issues.jsonl` is auto-exported
  (untracked until committed).

Workflow, agent context profiles, and the session-completion protocol live in
**`.beads/beads.md`**. Run `bd prime` for runtime context, `bd ready` for
actionable work.

Authority split: the decision register's **Status column is the canonical
record of decision status**; beads issues track the execution work and
reference register IDs in their descriptions — they do not duplicate decision
state.
