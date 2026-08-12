# Equity-OS

An agentic, evidence-governed equity-research system for Indian markets, in
blueprint stage. This glossary is the repo's vocabulary — use these terms in
issue titles, docs, and code; avoid the listed synonyms.

## Language

### Product & scope

**Equity-OS**:
The product and repo name — a persistent, evidence-governed equity-research system, not an autonomous stock-picking chatbot.
_Avoid_: Funda (the blueprint's working title; use only when citing the blueprint docs)

**Blueprint**:
The approved reference set in `docs/blueprint/`: the consolidated review (architecture rationale), the v2 decision register (operational authority), and the third-order disposition report. Strategy reference, **not** the build specification.
_Avoid_: spec, design doc

**Decision register**:
The single operational source of truth for decisions, spikes, and phase gates (`funda-blueprint-implementation-decision-register-v2.md`, IDs A-01…E-10; v1 is superseded). Its wording is authoritative for implementation gates — narrative reviews do not override it. Its Status column is the canonical record of decision status; beads issues reference register IDs for execution tracking.
_Avoid_: backlog

**Blueprint phase**:
A delivery stage from the register (0A, 0.5, 1, 2, …), each with an exit gate in the v2 scorecard (§F). Qualify as "blueprint phase" when a workstream also has phases (a roadmap unit materialised as a bd epic).
_Avoid_: milestone, sprint

**Vertical slice**:
Blueprint phase 0.5 — one discovery company across four consecutive quarters: Quarter 0 is the manual baseline + bootstrap thesis, Quarters 1–3 are three assisted incremental updates; schemas derived from actual use.
_Avoid_: prototype, POC

**Discovery company**:
The single company chosen for the vertical slice, with four consecutive quarters of source material (register A-02).

**Earnings-review workflow**:
The first product workflow: a fixed, resumable state machine from run registration through ingestion, extraction, reconciliation, deterministic calculation, drafting, human review, and publication. Not an autonomous planner.
_Avoid_: pipeline (ambiguous), agent loop

### Evidence & data

**Observation**:
A typed value extracted from a source, with raw/normalized value, units, currency, scope, dimensions, exact source location, and temporal fields. Pre-reconciliation. (Final schema is derived from the vertical slice — register B-05, open.)
_Avoid_: data point

**Fact**:
A reconciled observation in the append-only, revision-aware SQL store. Restatements supersede; nothing is silently overwritten.
_Avoid_: number, value (unqualified)

**Claim**:
A typed assertion — subject, predicate, object, scope, horizon, epistemic class, confidence, status, supersession — with prose as the display layer. Material claims must resolve to a fact ID, calculation trace, or exact source location. (Final schema is derived from the vertical slice — register B-06, open.)
_Avoid_: statement, insight

**Epistemic class**:
The mandatory label on output: observed / computed / inferred / forecast / opinion. Prevents retrieval from converting interpretation into fact.
_Avoid_: confidence level (that is a separate field)

**Evidence package**:
The frozen set of documents, facts, and calculations a run (or debate) works from. Built once per run; downstream steps do not fetch new evidence.
_Avoid_: context (unqualified)

**Valid time / knowledge time**:
The bitemporal pair: when a fact applies vs when the system could have known it. Every other timestamp must have a precise definition.
_Avoid_: date (unqualified), as-of (ambiguous)

**Point-in-time capture**:
The daily/event-driven persistence of index membership, prices, announcements, corporate actions, and shareholding with hashes and first-seen times. Starts with the first build because pre-capture history cannot be cleanly recreated; backtesting comes much later.
_Avoid_: backfill (capture prevents future loss; it does not recreate the past)

**Source-of-truth hierarchy**:
The authority table proposed by the blueprint: immutable object store for originals, SQL for facts/claims/events/approvals, registered calculation store for traces, versioned Markdown for the approved narrative, rebuildable indices for retrieval. Formal acceptance is register item B-03 (open).
_Avoid_: single source of truth (there are several, by role)

### Analysis & review

**Deterministic compute**:
Registered, traceable calculation code — the only authoritative calculator. Two tiers: *minimum* (growth, margins, cash conversion, leverage, dilution bridges, guidance comparison) in the MVP; *model-grade* (DCF/SOTP/WACC, sector packs) later.
_Avoid_: the model calculating (the LLM never is)

**Calculation trace**:
The registered record of inputs, assumptions, outputs, and code version behind a computed number.
_Avoid_: scratchpad (model scratchpads are never a product record)

**Thesis**:
The current **approved analytical view** of a company — versioned narrative, never "current truth". Updates are incremental and diff-reviewed.
_Avoid_: current truth, recommendation (a regulated research-distribution concept — gated by the distribution boundary)

**Management ledger**:
The tracked record of management promises: new, modified, due, and outcomes.
_Avoid_: guidance tracker

**Memory promotion**:
The separate, human-approved action that lets a drafted claim or narrative change affect the canonical thesis. In the initial private operating model: agents draft, validators attach QA, only the analyst promotes.
_Avoid_: auto-save, sync

**Golden set**:
The owned, expert-labeled evaluation fixtures (~20 cases to start), grown continuously from observed failures (register A-08).
_Avoid_: test data (unqualified)

**Analyst review economics**:
The headline product metric: analyst minutes per approved update, accepted-unchanged rate, correction categories, source-location time.
_Avoid_: accuracy (necessary but not this)

**Distribution boundary**:
The hard gate between private/internal research and any paid, public, or personalized output (register A-01, E-08). Regulatory, not stylistic.

### Work management (harness-wide)

**Workstream**:
A named body of work under `docs/workstreams/` with a roadmap and bd epics.
_Avoid_: project, initiative

**Roadmap**:
The phased plan of one workstream; **phase** = one roadmap unit (one bd epic); **stage** = one deliverable inside a phase (one bd task).
_Avoid_: plan (that is the per-phase document)

**Spec**:
The approved output of brainstorming (`docs/specs/YYYY-MM-DD-<topic>.md`) — the commitment to build.
_Avoid_: requirements doc, design doc

**Bead**:
One durable work item in bd (prefix `equity-os`). In-turn steps are not beads.
_Avoid_: ticket, todo

**Ready-for-agent**:
Specified enough for autonomous execution — the intake gate in `.beads/beads.md`. Distinct from `bd ready` (merely unblocked).
_Avoid_: ready (unqualified)
