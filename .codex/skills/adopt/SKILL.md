---
name: adopt
description: "Adopt the reusable agent harness to the current repository by refreshing only project-overlay facts. Use when the user invokes $adopt or asks to orient the harness to a new repository."
---

# Adopt

Use this after the setup has been copied into a target repository root.

## Goal

Keep the core harness stable. Update only `.codex/project/*` with facts derived from the current repo.

## Workflow

1. Read:
   - `AGENTS.md`
   - `CONTEXT.md` when present
   - `.codex/project/*.md`
2. Scan the target repo in this order:
   - root instruction files
   - README and design docs
   - manifests, lock files, CI, and test config
   - relevant source and test directories
3. Use this authority order:
   - repo reality
   - current config and CI
   - maintained docs
   - older docs
   - explicit assumptions
4. Verify claims against the actual repo when possible.
5. Update only:
   - `.codex/project/brief.md`
   - `.codex/project/repo-map.md`
   - `.codex/project/verification.md`
   - `.codex/project/invariants.md`
   - `.codex/project/docs-index.md`
   - `.codex/project/tools.md`
   - `.codex/project/tracking.md`
   - `.codex/project/learnings.md`
   - `.codex/project/code-intel.md`
   - `.codex/project/adoption-report.md`
   - `CONTEXT.md` (repo root) — seed the domain glossary from repo reality: only terms actually
     observed, each with avoid-synonyms, glossary only (no implementation details); format per the
     `domain-modeling` skill. If the repo's vocabulary is thin, keep it short — `domain-modeling`
     grows it lazily.
6. Use repo-relative paths only.
7. For `standard` or `deep` adoption work, use a native read-only Codex reviewer to challenge major assumptions before finalizing.
8. Stop and present the adoption report for review.

## Code intelligence

While scanning, assess whether the repo benefits from persistent code-intelligence
indexing: a substantial, multi-session, navigation-heavy codebase benefits; a
tiny or throwaway repo does not. Record the assessment, primary language/LSP,
and observed index state in `.codex/project/code-intel.md`.

Do not install or enable tooling automatically. If indexing is warranted, name
the requirement and verify the currently available Codex-native option before
proposing exact setup steps.

## Rules

- Do not rewrite core rules, agents, commands, or skills unless the user asks.
- Do not copy unverifiable design-doc claims into project facts.
- Do not invent verification commands. If local commands are unclear, say so in `verification.md` and
  keep the completion gate structural until real code, manifests, or CI exist.
- If the repo has a language-specific stack, document the observed commands and any mismatch with
  `.codex/rules/` in the adoption report.
