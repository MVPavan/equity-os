# Funda Blueprint — Implementation Decision Register v2

**Companion references**

- `funda-blueprint-final-consolidated-review.md` — frozen architectural rationale
- `funda-third-order-review-disposition-report.md` — disposition of the third-order audit

**Updated:** 12 August 2026  
**Purpose:** Single operational source of truth for decisions, acceptance evidence, and phase gates.

---

## Status legend

- **Open:** decision or work not started.
- **In progress:** active work.
- **Accepted:** decision frozen or acceptance evidence complete.
- **Deferred:** explicitly outside the current phase.
- **Rejected:** evaluated and intentionally not adopted.

## Authority rule

The wording in this register is authoritative for implementation gates. Narrative reviews explain rationale but do not override this register.

---

## A. Phase 0A — Product, sources, measurement, and operating boundary

| ID | Priority | Decision or action | Required evidence / acceptance | Dependencies | Status |
|---|---:|---|---|---|---|
| A-01 | Critical | Freeze initial user and distribution boundary | Written statement covering private/internal use, public or paid distribution, personalization, execution linkage, and intended future boundary; document does not claim legal sufficiency | — | Open |
| A-02 | Critical | Select one discovery company and four consecutive quarters | Quarter 0 is reserved for the manual baseline and bootstrap thesis; Quarters 1–3 are reserved for three assisted incremental updates; source package exists for all quarters and at least one management commitment can be tracked across periods | — | Open |
| A-03 | Critical | Define and perform the manual baseline workflow | Quarter 0 is completed manually with time-stamped reading, source location, verification, calculation, drafting, and approval; the same lightweight instrumentation is used in manual and assisted workflows and its overhead is recorded | A-02, A-04 v0, A-10, A-13 | Open |
| A-04 | Critical | Freeze the first output contract | A provisional v0 exists before baseline; final contract after baseline includes event/cutoff, facts, changes, driver analysis, management ledger, thesis impact, observable falsifiers, open questions, calculations, memory draft, and approval record | A-03 for final freeze | Open |
| A-05 | Critical | Create provider and data-rights register scoped to the declared boundary | For every source: access method, automation, caching, retention, commercial use, derived outputs, redistribution, account limits, point-in-time availability, and replacement path | A-01 | Open |
| A-06 | Critical | Run filing-channel-aware XBRL-versus-PDF spike | Coverage matrix by company, quarter, filing channel, taxonomy/version, statement, segment, note, ownership/share count, restatement behavior, mapping stability, and reconciliation effort | A-02 | Open |
| A-07 | High | Define initial per-workflow budgets | Ceilings or measurement rules for model cost, tool calls, latency, document volume, retries, and analyst minutes | A-13 | Open |
| A-08 | High | Appoint golden-test-set owner | Named owner, repository location, review cadence, and first twenty labeled cases, including prompt-injection/source-confusion cases | — | Open |
| A-09 | Medium | Verify project name and trademark risk | Search record and decision on continued use of “Funda” | — | Open |
| A-10 | Critical | Define claim materiality policy | Versioned policy combining quantitative magnitude, always-material categories, thesis relevance, source conflict/uncertainty, and coverage-specific overrides; validator test cases approved | A-01, A-02 | Open |
| A-11 | Critical | Author and approve bootstrap thesis for the discovery company | Using Quarter 0, a concise initial thesis, assumptions, management commitments, risks, open questions, and observable falsifiers are manually written, approved, versioned, and available before Quarter 1; full initiation remains deferred | A-03 | Open |
| A-12 | High | Define operating calendar, standing budget, and capacity | Weekly builder/analyst capacity, target phase dates, monthly provider/model/infrastructure ceilings, maintenance allowance, and expected company coverage documented | A-01, A-02 | Open |
| A-13 | Critical | Freeze success-metric contract | Versioned definitions and measurement methods for factual accuracy, citation correctness, numerical traceability, unsupported claims, analyst minutes, per-claim verification time, coverage capacity, latency, cost, failure/retry rate, and phase applicability | A-01 | Open |

---

## B. Phase 0.5 — One company, four quarters: one baseline plus three assisted updates

| ID | Priority | Decision or action | Required evidence / acceptance | Dependencies | Status |
|---|---:|---|---|---|---|
| B-01 | Critical | Implement fixed, resumable earnings-review workflow | State definitions, allowed transitions, failure states, immutable step outputs, idempotent retries, and resume behavior documented and tested | A-04, A-10, A-11 | Open |
| B-02 | Critical | Produce three real incremental earnings updates | Quarters 1–3 each consume the approved preceding thesis and include sources, facts, changes, management ledger, thesis impact, falsifiers, calculations, open questions, and approval record | B-01, B-03–B-07, B-11–B-14 | Open |
| B-03 | Critical | Establish source-of-truth matrix | Approved authority table for raw documents, SQL facts, claims, calculations, narrative memory, derivative indices, evidence packages, and reports | — | Open |
| B-04 | Critical | Measure analyst review economics without invalid percentiles | Record each report's total review time; claim count; per-claim disposition and time; source-locate and calculation-check time; accepted/edited/rejected/deferred counts; correction categories; no report-level P90 is used at n=3 | A-03, A-13, B-13 | Open |
| B-05 | Critical | Derive minimum source and fact schemas from actual use | Schema supports raw/normalized values, dimensions, scope, source location, valid time, knowledge time, revisions, definition version, and quality/reconciliation status | A-06, B-11, B-12 | Open |
| B-06 | Critical | Derive minimum typed claim schema | Subject, registered predicate, object, scope, horizon, epistemic class, confidence, materiality result/policy version, status, evidence direction, and supersession are represented | A-10, B-12 | Open |
| B-07 | High | Define minimum deterministic compute | Approved MVP list with input, trace, code-version, missing-input, and reproducibility contracts | A-04 | Open |
| B-08 | High | Record failure taxonomy | Extraction, reconciliation, source, unit, period, calculation, citation, inference, review, cutoff leakage, source-confusion, and document-as-instruction failures categorized | A-08 | Open |
| B-09 | High | Start point-in-time capture | Daily/event jobs persist approved membership/security changes, prices, announcements, corporate actions, shareholding changes, hashes, first-seen times, and capture failures | A-05 | Open |
| B-10 | High | Decide which speculative blueprint fields to remove or defer | Schema-delta document showing retained, deleted, added, and deferred fields with reasons | B-02, B-05, B-06 | Open |
| B-11 | Critical | Specify fact identity, revision-family, and correction semantics | Source occurrence, extraction result, measurement key, revision family, and canonical selection are distinguished; issuer restatement, source correction, parser re-extraction, manual correction, and normalization-policy change have separate reasons; prior-period comparative handling is tested | A-06, B-12 | Open |
| B-12 | Critical | Establish versioned metric and predicate registries | Registry definitions, aliases, object/unit/dimension rules, addition approval, deprecation, and versioning exist; every structured fact/claim resolves to a registered entry; embedding-assisted dedup is optional | A-04, A-06 | Open |
| B-13 | High | Add reviewer-bias and measurement controls | Quarter 0 is not reused for assisted work; instrumentation is symmetric and overhead measured; shadow-mode seeded-error drills cannot be promoted; false-accept/false-reject results are stratified by materiality and epistemic class; optional external spot review procedure defined | A-03, A-08, A-13 | Open |
| B-14 | Critical | Demonstrate human-feedback rework path | A rejected claim triggers the correct invalidation cascade; evidence package v(N+1) is created; only affected calculations/claims are rerun; prior package remains immutable; partial revalidation and reapproval succeed | B-01, B-11 | Open |

---

## C. Phase 1 — Evidence-grounded MVP

| ID | Priority | Decision or action | Required evidence / acceptance | Dependencies | Status |
|---|---:|---|---|---|---|
| C-01 | Critical | Expand to two or three core non-financial companies | Companies selected for disclosure quality, history, differing but manageable structures, and feasible peak-season review capacity | A-12 | Open |
| C-02 | Critical | Build immutable document registry and object store | Original files, URLs, timestamps, hashes, parser versions, extraction warnings, and first-seen times are preserved | A-05 | Open |
| C-03 | Critical | Implement append-only observation and revision model | Restatements and conflicting observations are preserved; no silent overwrite; model follows B-11 identity semantics | B-11 | Open |
| C-04 | Critical | Implement materiality- and epistemic-class-aware claim validation | Material observed/computed claims require direct source or calculation support; material inferences/forecasts require linked evidence, explicit assumptions, uncertainty, and correct labeling; contradiction and materiality reasoning are visible | A-10, B-06 | Open |
| C-05 | Critical | Build claim-level review UI/workflow | Accept, reject, edit, defer, source jump, calculation inspection, diff-only review, provenance display for memory drafts, and safe shadow-test mode are supported | B-13, B-14 | Open |
| C-06 | Critical | Put authoritative corporate actions in SQL | Splits, bonuses, rights, demergers, dividends, ticker changes, and delistings are versioned events | C-17 | Open |
| C-07 | High | Put factual entity relationships in bitemporal SQL | Parent/subsidiary, management roles, ownership, cross-holdings, and validity/knowledge intervals are represented | C-17 | Open |
| C-08 | High | Implement minimum deterministic calculations | Growth, margins, cash conversion, leverage, dilution/share count, guidance comparison, and reconciliation traces pass tests and fail closed | B-07 | Open |
| C-09 | High | Implement complete run manifest | Inputs, cutoff, source/evidence-package versions, tools, models, prompts, code versions, costs, calculations, QA, approvals, and exact published-artifact hash are registered | C-16 | Open |
| C-10 | High | Establish correction, supersession, and promotion workflow | Corrections create new versions; invalidated items remain auditable; canonical promotion is separately approved; split-brain writes are prevented | B-03, B-14 | Open |
| C-11 | High | Prohibit product dependence on raw model scratchpads | Stored records are evidence, tool traces, structured decisions, QA results, and concise rationales | — | Open |
| C-12 | High | Set Phase 1 analyst-economics gate | Pre-agreed improvement is evaluated against per-company or matched-quarter baselines; workload-normalized metrics and total report time are reported; remaining confounds are disclosed | A-13, B-04 | Open |
| C-13 | Medium | Decide treatment of consensus estimates | Licensed and necessary, or explicitly excluded from the MVP | A-05 | Open |
| C-14 | Medium | Add official-audio transcription where needed | Original audio, model/version, timestamps, confidence, and correction history are preserved | C-02, B-08 | Deferred |
| C-15 | Critical | Enforce run knowledge cutoff across stores and tools | SQL/document/memory retrieval applies `knowledge_time <= cutoff`; canonical selections are resolved as of the cutoff so later restatements/corrections do not rewrite history; tool gateway records cutoff capability; tests insert and reject post-cutoff records | B-03, C-02, C-03 | Open |
| C-16 | Critical | Implement layered reproducibility and artifact approval | Exact-class operators replay exactly; floating-point/optimization outputs meet declared tolerances; stochastic operators store seeds and test distributions; evidence package reconstructs exactly; approved narrative bytes are immutable and bound to content hash | B-03, B-07, C-08 | Open |
| C-17 | High | Decide entity/security master authority | Stable internal company/security IDs; versioned ISIN/symbol/CIN/LEI mappings; source hierarchy, conflicts, valid/knowledge time, and one real identifier-change case tested | A-05, A-06 | Open |
| C-18 | Medium | Validate results-season throughput | Peak-week reviews per analyst, claim/document volume, backlog age, and completion capacity for the Phase 1 universe are measured and accepted or mitigated | A-12, A-13, C-01 | Open |

---

## D. Phase 2 — Memory evaluation

| ID | Priority | Decision or action | Required evidence / acceptance | Dependencies | Status |
|---|---:|---|---|---|---|
| D-01 | Critical | Implement `MemoryStore` interface before choosing engine | Retrieval, staged write, promotion, correction, deletion, export, cutoff filtering, and provenance contracts are engine-neutral | C-15 | Open |
| D-02 | Critical | Run current-scale three-arm memory benchmark | All arms receive the same authoritative prior artifacts; compare no persistent memory/manual context assembly, Git/Markdown/SQL retrieval, and GBrain on longitudinal tasks, retrieval misses, contradiction/staleness detection, analyst time, unsupported claims, latency, cost, and operations; result governs current adoption only; re-evaluation triggers are precommitted | C-05, D-01, D-04 | Deferred |
| D-03 | High | Define canonical memory promotion transaction | Narrative content hash/commit is registered in SQL; partial writes cannot create split-brain state | D-01 | Deferred |
| D-04 | High | Verify GBrain repository and dependency posture | Repository, license, maintainers, activity, tests, security, export path, and pinned version recorded | — | Deferred |
| D-05 | High | Decide GBrain adoption | Adopt only if current-scale benchmark benefit exceeds operational and upgrade burden; a non-adoption result does not prevent later trigger-based reevaluation | D-02, D-04 | Deferred |

---

## E. Phase 3 and later — Conditional capabilities

| ID | Priority | Decision or action | Required evidence / acceptance | Dependencies | Status |
|---|---:|---|---|---|---|
| E-01 | High | Add model-grade financial compute | Statement tie-outs, DCF/SOTP/WACC, sensitivities, and sector definitions are reproducible and fail closed | C-08 | Deferred |
| E-02 | High | Add stress-test companies | One bank/NBFC, one conglomerate, and one difficult disclosure/corporate-action case | C-01 | Deferred |
| E-03 | High | Evaluate bull/bear and forensic review | Compare with single senior-reviewer baseline; retain only if incremental valid issue detection justifies cost | C-04, C-05 | Deferred |
| E-04 | High | Add event monitoring | Alerts identify which fact, assumption, catalyst, promise, falsifier, or thesis breaker changed; immaterial events do not rewrite thesis | C-04 | Deferred |
| E-05 | High | Begin controlled quant validation | Uses collected point-in-time data; leakage, revisions, universe history, fees, liquidity, and benchmark are disclosed | B-09, E-10 | Deferred |
| E-06 | Medium | Evaluate OpenBB deployment | If used, it remains out of process and behind Funda contracts; license and replacement path approved | A-05 | Deferred |
| E-07 | Medium | Verify FinanceHarness and Vibe-Trading before reuse | Exact repositories, licenses, test quality, provider assumptions, and pinned versions recorded | — | Deferred |
| E-08 | Critical | Gate paid/public/personalized research on current legal review | Current regulatory obligations, disclosures, reviewer responsibilities, and distribution controls documented for the intended mode | A-01 | Deferred |
| E-09 | Critical | Keep execution in a separate trust domain | Separate service, credentials, database, deterministic limits, approvals, kill switch, and reconciliation | E-08 | Deferred |
| E-10 | High | Publish historical-replay leakage policy | Store/tool leakage controls are tested; model-weight leakage is disclosed as an uncontrollable limitation; historical LLM results are not represented as clean alpha evidence | C-15 | Deferred |

---

## F. Phase-gate scorecard

### Phase 0A may exit only when

- the initial product boundary is documented;
- source rights are scoped to that boundary;
- one discovery company and four consecutive quarters—one baseline/bootstrap plus three assisted—are selected;
- the filing-channel-aware XBRL/PDF spike is complete;
- materiality and success-metric contracts are versioned;
- the provisional output contract exists;
- operating capacity and standing budget are documented;
- the golden-set owner and initial cases exist.

### Phase 0.5 may exit only when

- the bootstrap thesis is approved;
- Quarter 0 manual baseline/bootstrap and three real assisted updates for Quarters 1–3 have been produced and reviewed;
- the manual baseline and all three report-level review times are recorded;
- claim-level review telemetry and correction categories are available without invalid percentile claims;
- the source-of-truth matrix is approved;
- fact identity/revision rules and metric/predicate registries are in use;
- minimum fact and claim schemas are based on actual workflow evidence;
- the rejected-claim rework path and evidence-package versioning are demonstrated;
- point-in-time capture has started;
- the first golden cases are automated or consistently reviewable.

### Phase 1 may exit only when

- all numerical claims classified as material under A-10 resolve to a fact or calculation trace;
- all factual claims classified as material under A-10 resolve to the correct source location;
- units, period, currency, statement scope, and definition are explicit;
- missing inputs fail closed;
- post-cutoff data are excluded by tested store/tool controls;
- deterministic calculations satisfy their declared exact/tolerance/seeded replay class and the approved narrative is bound to an artifact hash;
- corrections, invalidation, supersession, and promotion are auditable;
- analyst effort improves against matched or per-company baselines by the agreed threshold, with confounds disclosed;
- peak results-season capacity is accepted for the selected universe;
- cost, latency, failures, and retries are visible;
- GBrain, debate, backtesting, and execution remain outside the release unless separately approved.

### Phase 2 may exit only when

- the selected memory approach improves measurable current-scale workflow outcomes;
- stale and contradicted conclusions are surfaced;
- canonical promotion cannot diverge from SQL metadata;
- correction, deletion, backup, and export have been tested;
- operational burden is acceptable;
- future re-evaluation triggers are recorded regardless of the current engine decision.

---

## G. Explicitly deferred from the first release

- full company initiation as an automated product;
- GBrain as a mandatory dependency;
- generalized autonomous planning;
- multi-agent investment committee;
- full-universe daily research;
- broad sector-pack library;
- licensed consensus estimates unless essential;
- portfolio construction;
- historical LLM alpha claims;
- paper trading;
- live execution;
- local-model optimization without a Funda-specific benchmark;
- migration to a distributed workflow engine or PostgreSQL before observed need.

---

## H. Storage and workflow scale-up triggers

These are operating notes, not Phase 0.5 blockers.

### Reconsider SQLite when

- persistent writer-lock contention affects ingestion or review;
- multiple remote users require concurrent writes;
- availability, backup, or failover requirements exceed the embedded deployment;
- operational workarounds become more complex than migration.

### Reconsider the simple state table when

- long-running workflows require durable timers/signals across services;
- human rework and invalidation paths cannot be maintained clearly;
- concurrency and retries create duplicate side effects despite idempotency controls;
- workflow observability becomes a material operating burden.

No specific replacement technology is committed by this register.

---

*End of implementation decision register v2.*
