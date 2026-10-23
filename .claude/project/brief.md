# Project Brief

**Equity-OS** is an agentic equity-research system for Indian markets. The
blueprint calls the product *Funda* (its working title); the product and repo
name is Equity-OS. The Python package is `fundamentals`.

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

## Current state (refreshed 2026-10-11)

- **Phase 0A gate cleared** (bead eqos-3ps closed 2026-08-21); Phase 0.5 product
  code is authorized and shipping. Beads, not this brief, are the source of
  truth for gate and task status.
- **Code:** ~58k lines under `src/fundamentals/` (`ingest`, `store`, `extract`,
  `reconcile`, `thesis`, `news`, `output`, `verify`, `entity`, `api`, `contracts`)
  with tests under `tests/`. Sources: NSE/BSE filings, Screener, Tijori, Upstox.
- **Pilot company:** Apar Industries (epic eqos-4j2), not INFY.
- **Product verdict:** `PILOT_PROVEN: YES` (Apar pilot PASS 2026-10-22:
  `docs/evidence/pilot/report.md`), `CORE_RESEARCH_RELEASE: NO`,
  `VISION_SATISFIED: NO`.
  Scope (2026-10-23, eqos-bnx): the PASS proves the pipeline (PILOT-1…13), not research
  content. The report's analyst sections are still placeholders, so register A-04/B-02 are
  unmet. They must be met before Phase 1 and `CORE_RESEARCH_RELEASE`.

## Stack

- Python 3.12+ managed with `uv`; Pydantic models; ruff / mypy --strict / pytest;
  structlog — matching `.claude/rules/python/`.
- SQLite fact store plus append-only snapshot and protected source-intake stores
  (`src/fundamentals/store/`). Parquet price panels are planned, not built.
- The only direct LLM client is `src/fundamentals/thesis/claude_client.py`.
- Agent framework, memory engine (GBrain vs Git/Markdown/SQL), and quant
  tooling are still **deliberately undecided** (blueprint §9) — do not pick them
  implicitly.

## Constraints / non-negotiables

- The LLM is never the authoritative calculator — numbers come from
  deterministic code with traces (see `invariants.md` for the full doctrine).
- Scope discipline: the blueprint is a reference, **not** the build spec.
  Phase gates in `docs/blueprint/funda-blueprint-implementation-decision-register.md`
  govern what may be built; GBrain, debate, backtesting, portfolio, and
  execution are explicitly outside the first release.
- Repo-relative paths only; explicit staging; `scratchpad/` never committed.
