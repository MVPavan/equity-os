# Project Brief

**Equity-OS** is an agentic equity-research system for Indian markets, in its
**pre-code blueprint stage**. The blueprint's working title for the product is
*Funda* (name/trademark check still open — decision A-09); the repo and product
name going forward is Equity-OS.

## Product thesis (from the approved blueprint review)

A persistent, **evidence-governed** equity-research system — not an autonomous
stock-picking chatbot. Operating doctrine:

> SQL records what happened. Curated memory preserves what was learned.
> Deterministic code calculates implications. Agents investigate, challenge,
> and explain. Execution remains separately controlled.

First deliverable: a **fixed-state earnings-review workflow** — given a
company's new quarterly-result package and an approved prior thesis, produce a
reviewable, source-backed update showing what changed in facts, management
commitments, calculations, uncertainties, and thesis.

## Current state

No first-party source code, no CI, no README. The repo holds the agent harness
(`.claude/`), beads tracking (`.beads/`), and two authoritative blueprint docs
under `docs/blueprint/` (the **v2 decision register is the operational
authority**; the consolidated review is rationale). Next milestones: **Phase
0A** — freeze the distribution boundary, discovery company, source rights,
manual baseline, output contract, materiality policy, success-metric contract,
budgets/capacity, and the XBRL-vs-PDF spike (register items A-01…A-13, all
currently Open) — then **Phase 0.5** (vertical slice: one company × four
quarters — Quarter 0 manual baseline + bootstrap thesis, Quarters 1–3
assisted updates).

## Intended stack (user-confirmed 2026-08-12)

- Python 3.12+ managed with `uv`; Pydantic models; ruff / mypy --strict / pytest;
  structlog — matching `.claude/rules/python/`.
- SQLite structured store + immutable document/object store + Parquet for
  derived price panels (blueprint Phase 1).
- Agent framework, memory engine (GBrain vs Git/Markdown/SQL), and quant
  tooling are **deliberately undecided** (blueprint §9) — do not pick them
  implicitly.

## Constraints / non-negotiables

- The LLM is never the authoritative calculator — numbers come from
  deterministic code with traces (see `invariants.md` for the full doctrine).
- Scope discipline: the blueprint is a reference, **not** the build spec.
  Phase gates in `docs/blueprint/funda-blueprint-implementation-decision-register.md`
  govern what may be built; GBrain, debate, backtesting, portfolio, and
  execution are explicitly outside the first release.
- Repo-relative paths only; explicit staging; `scratchpad/` never committed.
