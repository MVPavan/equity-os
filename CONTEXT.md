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
The cited records of a report version, sealed by its digest; the frozen set of documents, facts, and calculations a run (or debate) works from. Built once per run; downstream steps do not fetch new evidence. Once retention expires its originals, it reconstructs by hash-matched re-fetch of exchange originals, while expired vendor material leaves only capture records, tombstones and comparison outcomes (retention-replay record). Exception (owner 2026-10-28, DOCS-1 A1): a document with no exchange original may be cited as a labelled Tijori vendor copy; it reconstructs only by hash-matched re-fetch from Tijori. Separately (owner 2026-11-06, VENDOR-1 decision 1): both vendor witnesses of an admitted vendor number are kept privately, never committed, while a sealed report cites them and within each vendor's licence; expiry or licence end of either withdraws the admission for new reports, and sealed reports keep their stored values with a visible note.
_Avoid_: context (unqualified)

**Admission label**:
The label on every admitted number (VENDOR-1): "checked against filing" (either the agreeing vendors' value, retained because the filing agrees within declared precision, or the admissible filed value, used when the filing differs or the vendors are unmapped, disagree or are imprecise) or "vendors agree, not checked against filing" (no filing, admitted only for an eligible check class). The label does not say which value was admitted or what the vendors did; the vendor outcome and filing state stay in the run's comparison results, reachable from the admission. A calculation carries the weaker label of its inputs.
_Avoid_: confidence, verified (unqualified)

**Check class**:
The digest of everything that makes vendor-agreement evidence comparable: canonical id, period kind, basis, framework, issuer class, both vendors' mapping entries with their mapping-set version, both extractor versions, dictionary version and vendor-first policy version. Any version change makes a new class with no evidence; one filing counterexample blocks the class.
_Avoid_: category, concept (unqualified)

**Pilot source package**:
The five frozen input files of one pilot quarter (XBRL, results PDF, transcript PDF, QoQ and YoY comparator XBRLs), pinned by id and sha256 in the pilot manifest. The input a run must read, not the evidence package it produces.
_Avoid_: evidence package (for the inputs)

**Valid time / knowledge time**:
The bitemporal pair: when a fact applies vs when the system could have known it. Every other timestamp must have a precise definition.
_Avoid_: date (unqualified), as-of (ambiguous)

**Point-in-time capture**:
The daily/event-driven persistence of index membership, prices, announcements, corporate actions, and shareholding with hashes and first-seen times. Starts with the first build because pre-capture history cannot be cleanly recreated; backtesting comes much later.
_Avoid_: backfill (capture prevents future loss; it does not recreate the past)

**Source-of-truth hierarchy**:
The authority table proposed by the blueprint: immutable object store for originals, SQL for facts/claims/events/approvals, registered calculation store for traces, PostgreSQL rows for the approved narrative (Markdown is a generated view; versioned files stay the record until the Stage 1 cutover is approved), rebuildable indices for retrieval. Formal acceptance is register item B-03 (open); its narrative row is amended by the report-ledger record.
_Avoid_: single source of truth (there are several, by role)

**Watchlist (covered)**:
The stocks the owner has chosen to cover with reports: an owner-only `ADD`/`REMOVE` decision with verbatim reason, sealed on a verified identity and a completed capture batch. Only watchlisted stocks get drafted reports; a new member's first report is a `BOOTSTRAP_THESIS` (amendment 1).
_Avoid_: the universe registry (every listed stock, no coverage implied), captured stocks (data captured by a batch, not covered), `config/coverage/watchlist.yaml` (the data spec's comparison set)

**Onboarding outcome**:
The result of onboarding a company from its identifier alone: `ONBOARDED` (run `COMPLETE`), `PARTIAL` (run `INCOMPLETE`, listing exactly the excluded verification units), `IDENTITY_CONFLICT` or `UNSUPPORTED`. `NOT_AUTHORISED` is a per-unit state, not an outcome. Defined in the D6 plan.
_Avoid_: onboarding status (ambiguous with run status)

**Acquisition sanction**:
A committed, stamped file under `config/acquisition/sanctions/` that lists the symbols a live acquisition may fetch, authorising `eqos onboard --acquire` without the Stage 4 freeze; it authorises symbols and purpose only, never an implementation.
_Avoid_: freeze descriptor (the Stage 4 record), approval of code

**Verification unit**:
One namespace or source whose identity binding onboarding verifies separately (exchange, XBRL entity, each vendor, the results PDF), with its own evidence and state.
_Avoid_: check (unqualified)

**Held-out company**:
The Stage 4 company drawn by a recorded, reproducible procedure before any D6 implementation, never used in development, and identified only in its holdout record and the Stage 4 manifest.
_Avoid_: test company, sample company

**Attempt**:
One pre-registered draw of a held-out company with its prediction; a failed or seen attempt is burned and a new one drawn, never revised.

**Implementation freeze**:
The committed descriptor naming the code and configuration revision after which nothing under `src/` or `config/` may change before the Stage 4 run.

### Analysis & review

**Deterministic compute**:
Registered, traceable calculation code — the only authoritative calculator. Two tiers: *minimum* (growth, margins, cash conversion, leverage, dilution bridges, guidance comparison) in the MVP; *model-grade* (DCF/SOTP/WACC, sector packs) later.
_Avoid_: the model calculating (the LLM never is)

**Calculation trace**:
The registered record of inputs, assumptions, outputs, and code version behind a computed number.
_Avoid_: scratchpad (model scratchpads are never a product record)

**Thesis**:
The current **approved analytical view** of a company — versioned narrative, never "current truth". Updates are incremental and diff-reviewed. Every run draft derives `thesis_impact` and `observable_falsifiers`: each falsifier's code-computed status against the thesis version approved at its derivation cutoff, threshold cited as a `THESIS_CLAIM`.
_Avoid_: current truth, recommendation (a regulated research-distribution concept — gated by the distribution boundary)

**Management ledger**:
The tracked record of management promises: new, modified, due, and outcomes.
_Avoid_: guidance tracker

**Memory promotion**:
The separate, approved action that lets a drafted claim or narrative change affect the canonical thesis. Agents draft, validators attach QA, and promotion is a separate decision by the approval panel or the owner role (override kept) (owner directive 2026-10-12).
_Avoid_: auto-save, sync

**Approval panel / owner role / runtime role**:
The product's decision roles. The **runtime role** (drafting agents) inserts drafts, content and submissions, never approvals. The **approval panel** is one configured model reviewer acting after deterministic checks; its verdict decides. The **owner role** records verbatim rulings and may override the panel. Docs name these roles; models are configuration.
_Avoid_: model names, the analyst (as approver)

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

### Agent roles (harness-wide)

**Orchestrator**:
The main session model. Owns scope classification, planning, context curation, dispatch, review routing, approval handling, and final synthesis. Never implements and reviews the same artifact itself.
_Avoid_: coordinator (in role-binding contexts), named model lanes

**Implementer**:
An independent subagent that writes or edits artifacts (code, docs, migrations) inside a bounded scope handed to it by the orchestrator.
_Avoid_: worker (in role-binding contexts), named model lanes

**Reviewer**:
An independent subagent that reviews an implementer's output. Always a separate agent and context from the implementer of the same artifact — never the same agent on both sides.
_Avoid_: named model lanes

Docs, goals, prompts, rules, and beads must reference these role names, never hard-coded model or vendor names. The current model bindings are owned by `.claude/rules/core/04-agent-stack.md` (owner directive 2026-10-11/12); the table below mirrors it.

| Role | Current binding |
|---|---|
| Orchestrator | the main session |
| Implementer | Claude Opus 5.5 medium |
| Reviewer (and approver) | GPT-6.1 Sol high |
