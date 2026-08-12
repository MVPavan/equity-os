# Funda Agentic Stock-Research Blueprint
## Consolidated Final Review

**Blueprint reviewed:** `funda-agentic-stock-research-blueprint(1).md`  
**Additional review incorporated:** `funda-blueprint-review-o5.md`  
**Consolidation date:** 7 August 2026  
**Reviewer stance:** Technical, product, data-governance, and delivery review. This is not legal or investment advice.

---

## 1. Final verdict

**Approve the architectural direction. Do not approve the blueprint as the direct implementation specification. Approve a tightly constrained earnings-review MVP once the decisions and corrections in this review are incorporated.**

The blueprint is unusually strong on evidence governance, deterministic computation, point-in-time integrity, memory poisoning, false multi-agent diversity, evaluation discipline, India-specific normalization, and the separation of research from execution. Its central product judgment is correct: Funda should become a persistent, evidence-governed equity-research system, not an autonomous stock-picking chatbot.

Its principal weakness is not architectural error. It is **scope, sequencing, and operating economics**. The document specifies enough layers, schemas, integrations, sector packs, evaluation systems, monitoring services, quantitative infrastructure, and execution controls to describe a substantial multi-year platform. Without an explicit team, budget, calendar, and first-user operating model, that completeness can become a substitute for shipping.

The consolidated recommendation is therefore:

> **Build one real earnings-update workflow end to end; derive the durable contracts from actual use; start point-in-time capture immediately; make analyst review time a first-class metric; and force every later component—including GBrain, debate, backtesting, and execution—to beat a simpler baseline before adoption.**

### Decision summary

| Area | Consolidated assessment |
|---|---|
| Product thesis | Strong and differentiated |
| Design principles | Preserve substantially unchanged |
| Evidence and deterministic-compute boundaries | Correct; make more explicit operationally |
| Current schema | Directionally useful, but too speculative and text-heavy to freeze |
| Current phase plan | Good gate-based structure, but too broad and partially mis-sequenced |
| GBrain | Plausible Phase 2 candidate, not a predetermined dependency |
| First workflow | Fixed-state earnings review, not a general autonomous planner |
| Pilot | One company × three quarters first; then two or three core companies; then stress cases |
| India data layer | Highest execution risk and likely moat |
| Human review | Under-designed; must be measured in analyst minutes |
| Backtesting and execution | Correctly late; point-in-time collection must nevertheless begin now |
| Build readiness | Conditional approval after the critical decisions below are frozen |

---

## 2. What should be preserved

The following elements are the strongest parts of the blueprint and should remain central to the product.

### 2.1 The trust boundaries

The formulation below should remain the system’s operating doctrine:

> SQL records what happened. Curated memory preserves what was learned. Deterministic code calculates implications. Agents investigate, challenge, and explain. Execution remains separately controlled.

The classification of output as **observed, computed, inferred, forecast, or opinion** is essential. It prevents later retrieval from silently converting interpretation into fact.

### 2.2 Numbers are calculated, not narrated

The language model may choose assumptions, identify missing inputs, explain sensitivities, and challenge a model. It should not be the authoritative calculator for DCF, WACC, ratios, share-count bridges, risk measures, or portfolio constraints.

### 2.3 Memory is curated and reviewable

The promotion chain from raw source to extracted observation, reconciled fact, interpretation, hypothesis, and approved conclusion is one of the blueprint’s most important design choices. The warning that memory can become a self-confirmation machine is correct and should shape both the data model and the user interface.

### 2.4 Point-in-time integrity is foundational

The separation of represented period, publication time, effective time, ingestion time, revisions, units, currencies, and source versions is essential for historical research reconstruction and any later backtesting. This is more important than the choice of orchestration framework.

### 2.5 Debate follows grounding

Bull/bear review should receive one frozen evidence package and deterministic calculations. Multiple agents do not create independent evidence, and multiple prompts to the same model do not create a genuine investment committee.

### 2.6 Research correctness is separate from outcome

The blueprint correctly separates:

1. research correctness;
2. forecast calibration;
3. decision quality; and
4. realized outcome.

That distinction should remain in the evaluation framework and in any future learning or memory-promotion logic.

### 2.7 Code rights and data rights are different

The blueprint is right that open-source code does not confer rights to underlying financial data. Provider terms, storage rights, commercial-use rights, derived-output rights, and redistribution limits must be treated as architecture inputs.

### 2.8 The first milestone is an incremental thesis update

The most defensible initial product is not “AI stock picks.” It is a source-backed quarterly update that retrieves prior beliefs, reconciles new facts, updates deterministic analysis, shows exactly what changed, preserves disagreement, and stages a reviewed thesis update with no invented numbers.

---

## 3. The central problem: the blueprint is too complete to be the build specification

The blueprint currently combines at least six different artifacts:

- strategy and product vision;
- repository survey;
- architecture decision record;
- data-model specification;
- implementation roadmap;
- security, evaluation, and compliance policy.

This makes it a valuable reference document, but a poor document from which to begin coding. Its breadth also conflicts with its own principle that complexity must earn its place against a simpler baseline.

The additional review estimates the full scope at roughly **two to four engineer-years**. That should be treated as a planning heuristic rather than a validated estimate, but the direction is credible: the full design includes many data domains, sector packs, governed memory, evaluation infrastructure, monitoring, two-stage quant validation, and an execution boundary.

### Required correction

Insert a **Phase 0.5 vertical slice** ahead of the durable platform build:

- one company;
- three consecutive quarters;
- one earnings update for each quarter;
- semi-manual ingestion where necessary;
- a deliberately disposable or minimally durable schema;
- a real analyst review step;
- measured approval time and correction categories.

The purpose is not to demonstrate a polished product. It is to discover what the fact model, claim model, source model, review interface, and calculation traces actually require. The durable schema should be derived from those three real updates rather than finalized in advance.

---

## 4. Reconciled differences between the reviews

The two reviews agree on the architecture but emphasize different corrections. The following decisions reconcile their apparent differences.

### 4.1 “Keep the strongest sections verbatim” versus “split and revise the document”

Preserve the **substance** of the design principles, evaluation separation, temporal-leakage policy, and gated roadmap. Do not preserve every implementation detail unchanged. The source-of-truth hierarchy, schema, pilot, and phase sequencing need revision.

### 4.2 One-company experiment versus a diversified six-company pilot

Use a staged pilot:

1. **Discovery slice:** one company across three quarters.
2. **Core product pilot:** two or three non-financial companies with good disclosures.
3. **Stress-test pilot:** one bank or NBFC, one conglomerate, and one disclosure/corporate-action edge case.

A separate bounded XBRL coverage spike may sample six representative companies without making all six part of the first production pilot.

### 4.3 GBrain as a likely dependency versus GBrain as an experiment

GBrain should be a **preferred candidate behind a `MemoryStore` interface**, not a committed dependency. It must beat both:

- no persistent memory; and
- Git-versioned Markdown plus SQL/SQLite search and optional embeddings.

### 4.4 Deterministic compute in Phase 1 versus Phase 3

Split compute into two levels:

- **Minimum deterministic compute in the MVP:** growth, margins, cash conversion, leverage, share-count/dilution bridges, reported-to-adjusted reconciliation, guidance comparison, and simple valuation references where inputs are available.
- **Model-grade compute later:** sector-specific normalization, DCF/SOTP, WACC, bank/NBFC/insurance models, peer valuation, detailed scenarios, and full tie-outs.

### 4.5 Backtesting in Phase 6 versus point-in-time capture now

Backtesting remains late. **Point-in-time data capture begins immediately.** Historical membership, announcements, prices, shareholding changes, and corporate actions cannot be reconstructed perfectly later.

---

## 5. Critical changes required before implementation

### 5.1 Make the first workflow a fixed state machine

The first earnings-review workflow should be explicit and resumable:

```text
Register run and cutoff
  → ingest approved documents
  → resolve company and security
  → parse and classify sections
  → extract typed observations
  → reconcile observations
  → execute minimum deterministic calculations
  → retrieve prior approved thesis
  → build a frozen evidence package
  → validate claims
  → draft the incremental update
  → human review
  → publish
  → optionally promote approved memory changes
```

A planner may initially do only a bounded job: identify unresolved evidence gaps and request an allowlisted additional tool call. It should not redesign the whole workflow on each run.

### 5.2 Declare one source-of-truth hierarchy

The blueprint currently gives important roles to SQL, raw files, GBrain Markdown, GBrain’s database, calculation traces, and published reports. These need an explicit authority order.

| Information | Authority |
|---|---|
| Original filing, announcement, transcript, or recording | Immutable object/document store |
| Source identity, timestamps, hashes, parser metadata | SQL |
| Reported and normalized facts | SQL, append-only and revision-aware |
| Corporate events and factual relationships | SQL, bitemporal |
| Calculation inputs, outputs, assumptions, and code version | Deterministic calculation store registered in SQL |
| Claim status, evidence links, approvals, and supersession | SQL |
| Current approved analytical narrative | Git-versioned Markdown or GBrain Markdown |
| Embeddings, graph index, reranking store | Rebuildable derivative index |
| Published memo | Versioned artifact registered in SQL |

Every approved narrative version should have a content hash or Git commit recorded in SQL. Promotion should use a staged write or transactional-outbox pattern so the structured store and narrative memory cannot silently diverge.

Use **“current approved analytical view”**, not “current truth,” for thesis pages. Facts can be authoritative; a thesis remains an interpretation.

### 5.3 Strengthen the fact schema before freezing it

A financial observation needs more than `metric_id`, value, and period. The minimum durable representation should cover:

```text
raw reported value
normalized numeric value
raw unit and normalized unit
raw currency and normalized currency
standalone / consolidated scope
accounting basis
instant versus duration
exact period dates and fiscal labels
segment / geography / product / customer dimensions
continuing versus discontinued operations
reported / adjusted / company-defined / Funda-normalized status
source table, row, column, page, cell, or timestamp
valid time
knowledge time
revision sequence
superseded observation
quality and reconciliation status
```

For example, “revenue” may mean consolidated revenue, standalone revenue, segment revenue, continuing-operations revenue, or an adjusted company-defined measure. These cannot safely share an undimensioned fact row.

Adopt one formal bitemporal vocabulary:

- **valid time:** when the fact or relationship applies;
- **knowledge time:** when Funda could have known it.

Other timestamps may remain, but each must have a precise definition.

### 5.4 Add typed claims, not only claim prose

Natural-language claim text is necessary for analyst review but insufficient for contradiction and supersession.

Add fields such as:

```text
subject_entity_id
predicate_id
object_value or object_entity_id
scope / dimension
time horizon
valid_from / valid_to
epistemic_class
confidence
status
supersedes_claim_id
```

Examples:

```text
Company X | expects | EBITDA margin | 18–20% | FY2028 | management guidance
Company X | has risk | customer concentration | high | current | analyst inference
Project Y | commissioning date | Q4 FY2027 | management promise
```

The prose claim remains the display layer; typed fields power comparison, retrieval, and review.

### 5.5 Put corporate actions and factual relationships in SQL

Large adjusted price panels belong in Parquet. The authoritative corporate-action events do not.

Splits, bonuses, rights issues, demergers, mergers, dividends, ticker changes, delistings, and adjustment factors should be represented as versioned SQL events with referential integrity. Adjusted series can then be derived into Parquet.

Likewise, subsidiaries, parent relationships, management roles, promoter holdings, cross-holdings, and other factual links should live in bitemporal SQL and may be mirrored into the memory graph for retrieval.

### 5.6 Resolve XBRL versus PDF parsing immediately

This is the highest-leverage tactical uncertainty in the India ingestion plan.

Run a short spike across representative issuers and quarters to measure:

- headline-statement coverage;
- segment and note coverage;
- standalone versus consolidated handling;
- restatement behavior;
- ownership and share-count coverage;
- mapping stability across issuers;
- effort required to reconcile XBRL and PDF values.

The likely architecture is hybrid: XBRL for standardized headline facts and PDF/table extraction for notes, segments, commentary, ownership, and company-specific definitions. The spike should establish the actual split rather than assume it.

### 5.7 Start point-in-time capture in the first build

Do not wait for the backtesting phase. Begin daily or event-driven capture of at least:

- index membership and security master changes;
- bhavcopy or approved price snapshots;
- exchange/company announcements;
- corporate actions;
- shareholding and pledge changes;
- source hashes and first-seen timestamps.

This does not mean building the backtest engine early. It means starting the historical clock now, because lost point-in-time history cannot be recreated cleanly later.

### 5.8 Make data rights a Phase 0 gate

Before an adapter becomes part of the product, record:

```text
access method
permitted automation
permitted caching
retention period
commercial-use rights
derived-output rights
redistribution restrictions
user/account restrictions
point-in-time availability
replacement source
```

Provider and rights decisions should precede framework decisions. A technically elegant connector is unusable if Funda cannot lawfully store, process, or expose the data in the intended product mode.

### 5.9 Make GBrain earn its complexity

Run a three-arm evaluation:

1. no persistent memory;
2. Git + Markdown + SQL/SQLite FTS and optional embeddings;
3. GBrain behind `MemoryStore`.

Measure:

- prior-thesis recall;
- management-promise recall;
- contradiction detection;
- stale-claim detection;
- retrieval precision;
- analyst correction time;
- unsupported-claim rate;
- latency and cost;
- operational and upgrade burden.

GBrain should be promoted only if its hybrid retrieval and graph features produce a meaningful advantage.

### 5.10 Do not depend on raw model scratchpads

Store evidence packages, source references, tool calls, structured decisions, validation outcomes, and concise rationales. Do not make long model scratchpads or hidden reasoning traces a required product record. They are noisy, may contain sensitive material, and are not the authoritative explanation of a result.

### 5.11 Build the golden test set in week one

The evaluation fixtures are a durable asset and should not be treated as a later checklist item.

Start with approximately twenty expert-labeled cases covering:

- core quarterly facts;
- standalone/consolidated distinctions;
- restatements and definition changes;
- share-count or dilution reconstruction;
- management-promise outcomes;
- source-to-claim mappings;
- citation correctness;
- historical-cutoff questions.

Give the set an explicit owner and add cases continuously as the vertical slice exposes failures.

### 5.12 Make human review economics a headline product metric

The product’s value depends on how quickly a qualified analyst can verify and approve an update.

Track at least:

- analyst minutes per approved update;
- number of claims reviewed;
- percentage accepted unchanged;
- corrections by category;
- time spent locating the cited source;
- time spent checking calculations;
- unresolved items per report;
- median and 90th-percentile approval time.

The review interface should support:

- claim-level accept/reject/edit;
- side-by-side source panes;
- direct navigation to page, table cell, or audio timestamp;
- visible calculation inputs and trace;
- **diff-only review** for incremental updates;
- explicit promotion of only approved memory changes.

Phase 1 should not exit merely because reports are accurate. It should show a pre-agreed reduction in review effort versus the manual baseline established in Phase 0.5.

### 5.13 Define the review and promotion operating model

For the initial private system:

- agents may create drafts;
- validators may attach QA results but may not promote;
- the analyst approves or rejects material claims;
- only approved claims affect the canonical thesis;
- corrections create a new version rather than rewriting history;
- invalidated items remain auditable;
- the reviewer sees the exact evidence and calculation trace before approval.

For a future team product, add coverage ownership, reviewer roles, second approval for recommendation-state changes, and access controls for private theses and portfolio information.

### 5.14 Add an explicit resourcing and operating budget

The blueprint needs a planning section containing:

- team size and required skills;
- target calendar for the vertical slice and MVP;
- monthly data-provider budget;
- model and infrastructure budget;
- analyst-review capacity;
- expected company coverage;
- support and maintenance burden;
- explicit features deferred beyond the MVP.

Also set workflow cost ceilings before implementation. The exact values should be calibrated during the vertical slice, but every run must have a budget for tokens, tool calls, latency, and analyst time.

### 5.15 Treat concall audio as a Funda-owned data capability

Where transcripts are absent or delayed, ingest the official recording and generate a timestamped transcript using a reviewed speech-recognition pipeline. Preserve:

- original audio;
- file hash and source;
- transcription model/version;
- speaker segmentation confidence;
- timestamp-level citations;
- correction history.

This is a credible India-specific advantage, but it should follow the core document-and-fact vertical slice rather than distract from it.

### 5.16 Clarify regulatory and distribution gates

The source review flags the 2025 Research Analyst guidance and retail-algorithm framework as material constraints. These claims should be independently checked against current official text and counsel before product launch.

The architecture decision is nevertheless clear:

- the **distribution boundary**—private internal use versus paid, public, or personalized research—must be a hard gate before coverage automation scales;
- live or automated execution must remain separately gated and may be infeasible or costly depending on the current broker, exchange, and regulatory requirements;
- the run manifest, source trail, model manifest, and human approval can become a compliance advantage rather than merely overhead.

### 5.17 Keep OpenBB out of the core authority path

If OpenBB is adopted, run it behind Funda’s provider contract and preferably out of process as a separate REST/MCP service. Funda should not expose OpenBB-specific schemas to the research layer or make its availability necessary for interpreting stored facts.

License and deployment implications still require review. The architecture should make removal or replacement straightforward.

### 5.18 Verify external projects before dependency promotion

Before GBrain, FinanceHarness, Vibe-Trading, or another fast-moving project becomes a direct dependency, confirm:

- exact repository identity;
- license;
- maintainer count and bus factor;
- recent activity and release cadence;
- test quality;
- security posture;
- data-provider assumptions;
- migration and export path;
- ability to pin a known-good version.

The blueprint’s own verification limitations are appropriate. The correction is to align dependency status with that uncertainty.

---

## 6. Revised delivery sequence

### Phase 0A — Freeze the product and legal boundary

**Decide:**

- first user and distribution mode;
- one discovery company;
- approved source set and rights;
- manual baseline workflow;
- cost and review-time measurement method;
- owner of the golden test set;
- the exact output contract.

**Also run:** a bounded XBRL-versus-PDF coverage spike.

**Exit:** no unresolved ambiguity about what the first workflow produces, who reviews it, or which sources may be used.

### Phase 0.5 — One company, three quarters

**Build only enough to produce three real incremental updates.** Semi-manual steps are acceptable.

Deliverables:

- immutable source package for each quarter;
- extracted observations and reconciliations;
- minimum deterministic calculations;
- prior-view and change comparison;
- claim-level review;
- analyst-time measurements;
- failure log;
- revised minimum schemas based on actual use.

**Exit:** the team can explain which fields, states, review actions, and calculations are truly necessary and can discard the speculative ones.

### Phase 1 — Evidence-grounded earnings-review MVP

Expand to two or three non-financial companies with good disclosures.

Include:

- fixed state machine;
- SQLite structured store;
- immutable document storage;
- XBRL/PDF hybrid ingestion as indicated by the spike;
- fact and claim contracts;
- point-in-time snapshot jobs;
- minimum deterministic compute;
- management-promise ledger;
- claim-level review interface;
- cited Markdown/HTML report;
- full run, source, calculation, model, cost, and approval manifests.

Exclude:

- mandatory GBrain;
- general autonomous planning;
- multi-agent debate;
- broad sector valuation;
- consensus estimates unless licensed and necessary;
- backtesting;
- portfolio construction;
- execution.

**Exit:** factual and numerical quality gates pass, and analyst review effort improves materially against the manual baseline.

### Phase 2 — Persistent-memory experiment

Compare no memory, Git/Markdown/SQL, and GBrain. Promote GBrain only if it wins on retrieval quality and analyst economics.

### Phase 3 — Model-grade compute and sector stress tests

Add one bank or NBFC, one conglomerate, and one difficult disclosure/corporate-action case. Build only the sector packs demanded by those tests.

### Phase 4 — Adversarial review

Compare a single senior-reviewer baseline with bull/bear and specialized forensic review. Retain the extra agents only if they find additional valid issues at acceptable cost.

### Phase 5 — Monitoring and incremental automation

Add event listeners, materiality rules, promise deadlines, thesis breakers, and a review queue. Do not rerun a full report for immaterial events.

### Phase 6 — Quantitative validation

Use the point-in-time history already collected. Keep deterministic screens and event studies separate from LLM-agent historical claims.

### Phase 7 and beyond — Paper and optional execution

Keep portfolio state, deterministic limits, credentials, and order APIs in a separate trust domain. Live execution is optional and not required for product success.

---

## 7. Recommended first release

### Product definition

> **Given a company’s new quarterly-result package and an approved prior thesis, Funda produces a reviewable, source-backed update showing what changed in the facts, management commitments, calculations, uncertainties, and thesis.**

### Inputs

- quarterly result release and notes;
- relevant exchange announcements;
- annual report sections where needed;
- transcript or official concall audio;
- approved prior thesis and open questions;
- approved market and corporate-action data;
- frozen knowledge cutoff.

### Output contract

1. **Event and cutoff** — documents included, first-seen times, and knowledge cutoff.
2. **Reported facts** — exact source references and normalized dimensions.
3. **Changes** — YoY, QoQ, prior-period, and versus prior assumptions where available.
4. **Driver analysis** — clearly separated observed evidence and inference.
5. **Management ledger** — new promises, modified promises, due items, and outcomes.
6. **Thesis impact** — strengthened, weakened, unchanged, or unresolved, with reasons.
7. **Open questions** — missing or contradictory evidence requiring review.
8. **Calculation appendix** — trace IDs, inputs, assumptions, code version, and quality flags.
9. **Memory draft** — proposed changes that are not promoted automatically.
10. **Approval record** — accepted, edited, rejected, and deferred claims.

### Minimum quality gates

- every material numerical claim links to a fact ID or calculation trace;
- every material factual claim resolves to the correct source passage, cell, page, or timestamp;
- units, currency, period, and standalone/consolidated scope are explicit;
- no missing input is silently fabricated;
- unsupported conclusions remain hypotheses or open questions;
- the report is reproducible from the frozen inputs and registered versions;
- analyst approval time and corrections are measured;
- memory promotion is a separate approved action.

---

## 8. Decisions that should be frozen now

Before implementation begins, resolve these items:

1. **User and distribution boundary:** internal/private research versus future client/public output.
2. **Discovery company:** one company with three consecutive quarters and adequate source material.
3. **Core pilot:** two or three non-financial companies after the discovery slice.
4. **Approved source rights:** access, storage, automation, and derived-output permissions.
5. **XBRL/PDF strategy:** measured coverage and reconciliation plan.
6. **Source-of-truth hierarchy:** authority for documents, facts, claims, calculations, narrative, and indices.
7. **First workflow:** fixed earnings-review state machine and failure states.
8. **Output contract:** exact sections, claim classes, and approval record.
9. **Minimum fact and claim schemas:** derived from the vertical slice and then versioned.
10. **Minimum deterministic calculations:** what must exist in the MVP.
11. **Human review model:** reviewer, promotion authority, and correction process.
12. **Success metrics:** accuracy, citation correctness, analyst minutes, coverage capacity, latency, and cost.
13. **Golden-set ownership:** person responsible for labels, updates, and regression review.
14. **Dependency policy:** criteria for promoting GBrain, OpenBB, and repository code into the core.
15. **Deferred scope:** explicit exclusion of debate, broad valuation, backtesting, portfolio, and execution from the MVP.

---

## 9. Decisions that can wait

Do not block the vertical slice on:

- the final autonomous-agent framework;
- the final memory engine;
- PostgreSQL versus GBrain’s team-scale database;
- multiple model providers for debate;
- the full sector ontology;
- a universal valuation library;
- VectorBT versus another first-pass quant tool;
- NautilusTrader or broker integration;
- portfolio construction;
- live execution.

These choices become clearer after the evidence pipeline and review workflow produce real usage data.

---

## 10. Recommended document set after this review

The original blueprint should remain the broad **strategy and architecture reference**. Implementation should proceed from separate, smaller artifacts:

1. **`MVP-001-earnings-review.md`**  
   Exact state machine, inputs, outputs, failure behavior, and human review.

2. **`ADR-001-system-of-record.md`**  
   Authority boundaries for documents, SQL, calculations, memory, indices, and reports.

3. **`data-contracts-v0.md`**  
   Minimum source, fact, claim, relationship, calculation, and run contracts derived from Phase 0.5.

4. **`evaluation-plan.md`**  
   Golden cases, tolerances, citation tests, historical cutoffs, review-time metrics, and cost budgets.

5. **`provider-rights-register.md`**  
   Data access, automation, storage, commercial-use, and redistribution terms.

6. **`dependency-due-diligence.md`**  
   Repository identity, license, maturity, test quality, upgrade risk, and exit strategy.

The repository survey and long watchlist should remain reference material rather than sit in the critical implementation path.

---

## 11. Approval conditions

Development of the constrained MVP is approved once the following are complete:

- the distribution boundary is documented;
- one discovery company and three quarters are selected;
- source rights are recorded;
- the XBRL/PDF spike is complete;
- the fixed workflow and output contract are frozen;
- the source-of-truth matrix is accepted;
- a minimum golden set exists with an owner;
- the manual review baseline is measured;
- minimum deterministic calculations are defined;
- GBrain, debate, broad sector models, backtesting, and execution are explicitly outside the first release.

The complete platform roadmap should not be treated as committed scope. Each later phase must pass a measurable value gate.

---

## 12. Final assessment

The blueprint has **no fatal architectural flaw**. It contains several unusually mature ideas: evidence classes, governed memory, point-in-time integrity, deterministic finance, false-diversity awareness, leakage disclosure, and separation of research from execution.

The next risk is organizational rather than conceptual: attempting to build the architecture as described before learning from one real analyst workflow.

The final consolidated judgment is therefore:

> **Preserve the principles. Narrow the product. Derive the schema from three real earnings updates. Start point-in-time capture now. Make analyst review time as important as citation accuracy. Treat GBrain and multi-agent debate as experiments. Ship the evidence-grounded incremental thesis update before building the research operating system around it.**

---

## Appendix A — Consolidated priority order

### Critical before or during Phase 0.5

1. Product/distribution boundary.
2. One-company, three-quarter vertical slice.
3. Fixed workflow and output contract.
4. XBRL-versus-PDF spike.
5. Source-of-truth hierarchy.
6. Data-rights register.
7. Point-in-time capture jobs.
8. Golden test-set owner and first cases.
9. Manual analyst-time baseline.
10. Minimum fact and claim contracts.

### High before Phase 1 exit

1. Claim-level review and diff-only workflow.
2. Minimum deterministic compute.
3. Corporate actions and relationships in SQL.
4. Full calculation and run manifests.
5. Cost, latency, and analyst-time budgets.
6. Two- or three-company core pilot.
7. Clear correction, supersession, and promotion process.
8. No reliance on raw model scratchpads.

### Later and conditional

1. GBrain after a three-arm benchmark.
2. Concall audio ASR after core ingestion works.
3. Sector-specific model packs when stress cases demand them.
4. Bull/bear and forensic debate after a single-reviewer baseline.
5. Monitoring after incremental updates are reliable.
6. Backtesting after sufficient point-in-time history exists.
7. Paper/live execution only under a separate legal, security, and operating decision.

---

*End of consolidated final review.*
