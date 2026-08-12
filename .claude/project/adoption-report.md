# Adoption Report

Harness adopted into **equity-os** via `/adopt`. Date: 2026-08-12.

## What this repo is

**Equity-OS** — an agentic, evidence-governed equity-research system for
Indian markets, currently **pre-code**: the repo holds the harness, beads
tracking, and two authoritative blueprint docs under `docs/blueprint/`
(consolidated review + implementation decision register, both dated
2026-08-07). The blueprint's working title is *Funda*; the user chose
**Equity-OS** as the product name (blueprint item A-09 — name/trademark check —
remains open).

## Inputs read

- `CLAUDE.md`, `AGENTS.md`, `CONTEXT.md` (as installed), the `/adopt` command.
- Both blueprint docs in full.
- Skeleton overlay under `.claude/project/` (all files were still the
  meta-repo's *coding-ritual* content).
- `.gitignore`, `git remote -v`, `git status`, `git log`, `.beads/config.yaml`,
  `.claude/` tree (rules, skills, agents, commands, hooks, docs).
- Tool availability: `bd` 1.1.0, `codex` CLI 0.147.0, `uv` 0.9.8,
  Python 3.12.3 — all verified on PATH.

## User decisions (asked and answered during adoption)

1. **Stack:** Python 3.12+ / `uv` / Pydantic / ruff / mypy --strict / pytest /
   structlog; SQLite + immutable object store + Parquet per blueprint Phase 1.
   Agent framework and memory engine deliberately open. (The full toolchain
   list was in the option text the user selected during this adoption's Q&A —
   confirmation lives in this session record, not in a repo file.)
2. **Name:** Equity-OS (Funda = blueprint working title only).
3. **Beads:** re-initialize now with the corrected sync remote.
4. **AGENTS.md:** leave as-is despite dangling `.codex/` references (below).

## Actions taken beyond the overlay

- **Fixed `.beads/config.yaml` `sync.remote`** from a stale `agent-os.git`
  (nonexistent; `bd init` failed on clone against it — observed firsthand this
  session) to `git+https://github.com/MVPavan/equity-os.git`, then re-ran
  `bd init` successfully (db `equity_os`, prefix `equity-os`). Why the earlier
  init commit f881e51 was reverted (b3e4570) is *not* recorded in git — its
  committed config already had the correct remote; no causal claim is made.
- Note: `bd init` **auto-committed** its integration files (c9dade1):
  `.beads/`, `.agents/`, `.claude/settings.json`, `.codex/config.toml` +
  `hooks.json`, `AGENTS.md`, `CLAUDE.md`. bd-owned behavior; surfaced here, not
  something agents may imitate. `.beads/issues.jsonl` (auto-export) is
  currently untracked.
- Created and claimed tracking issue `equity-os-klx` for this adoption.

## Files updated (overlay)

`.claude/project/`: `brief.md`, `repo-map.md`, `docs-index.md`,
`verification.md`, `invariants.md`, `tools.md`, `tracking.md`, `learnings.md`
(reset; one new entry on the bd-init remote failure), `code-intel.md`, this
report. Repo root: `CONTEXT.md` (glossary seeded from the blueprint's actual
vocabulary + the harness work-management terms).

The meta-repo's Codex-CLI learnings entries were removed with the reset — they
belong to the harness meta-repo, not here.

## Conflicts / gaps (flagged, not fixed)

- **`AGENTS.md` points at `.codex/…` throughout**, but `.codex/` here contains
  only bd-generated `config.toml`/`hooks.json` — no Codex harness, no
  `.codex/project/` or `.codex/rules/`. A Codex agent following it lands on
  missing files. User chose to leave it (Codex-side harness may be installed
  later).
- **`CLAUDE.md` template leftovers:** the *External Submodules* section
  (`reference_harnesses/`, `.gitmodules`), the *harness-lifecycle curation*
  rule (`.claude/rules/harness-lifecycle/curation.md`), and read-order entries
  for `docs/research/` reference things that don't exist in this repo. Dormant
  rather than harmful; trim when convenient (core files — not touched without
  an explicit ask).
- **No CI / no verification commands exist.** The completion gate stays
  structural (see `verification.md`); real commands get pinned when
  `pyproject.toml` lands. No commands were invented.
- **`.gitignore` is beads-only** — it does not yet ignore `scratchpad/`,
  Python artifacts (`__pycache__/`, `.venv/`), or `.serena/`. Worth extending
  before first code.

## Code intelligence

Not warranted yet (pre-code repo); see `code-intel.md`. Revisit when Phase
0.5/1 Python lands — at that point the codebase becomes the plugin's target
shape, and opt-in would be: register the marketplace, enable
`"code-intel@code-intel"`, `/code-intel:setup` (per machine),
`/code-intel:index-repo` (per repo).

## Codex critique

Run per adopt step 7 (`--role critique`; first attempt at xhigh effort timed
out at 10 min, retry at high effort completed — session
019ff739-9f0a-7cc0-bdab-2366834280e0). Verdict: "revise before adoption",
6 findings. Disposition:

- **Valid, fixed:** (a) beads-failure history over-claimed — f881e51's
  committed config already had the correct remote, so the causal story was cut
  to firsthand-verified facts (tracking.md, learnings.md, above); (b)
  register-vs-beads status authority was ambiguous — register Status column is
  now canonical everywhere; (c) `scratchpad/` was stated as gitignored but is
  not — invariant reworded; (d) open register items (B-03/B-05/B-06) were
  phrased as settled — glossary and invariants now mark them provisional;
  (e) Phase 0A summary omitted A-03/A-04/A-07 — brief expanded; (f) glossary
  overgeneralizations (point-in-time vs backfill, promotion role, phase gates,
  "recommendation") tightened.
- **Noise, dropped with reason:** "toolchain beyond Python/uv/SQLite is
  unconfirmed" — the user selected an option that explicitly listed the full
  toolchain (Codex couldn't see the Q&A); "code-intel opt-in commands
  unsupported" — they come verbatim from the `/adopt` command, an authorized
  input; "'each phase has an exit gate' overstates" — review §11 says each
  later phase must pass a measurable value gate (wording still tightened to
  cite the formal scorecards).

## Recommended next steps

1. Review this report, the overlay, and `CONTEXT.md`; commit when satisfied
   (nothing staged by me; c9dade1 was bd's own commit).
2. Start Phase 0A as a workstream: all nine register A-items are Open —
   distribution boundary (A-01), discovery company (A-02), **manual analyst
   baseline (A-03), output contract (A-04)**, source-rights register (A-05),
   XBRL-vs-PDF spike (A-06), **workflow budgets (A-07)**, golden-set owner
   (A-08), name/trademark check (A-09) — ready to become beads issues.
3. Extend `.gitignore` (scratchpad, Python artifacts) before first code.
4. Decide the `AGENTS.md`/`.codex` story before any Codex-driven session relies
   on it.
