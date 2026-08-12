# Funda Blueprint — Implementation Decision Register

**Companion to:** `funda-blueprint-final-consolidated-review.md`  
**Created:** 7 August 2026  
**Purpose:** Convert the consolidated review into trackable decisions, spikes, and phase gates.

---

## Status legend

- **Open:** decision or work not started.
- **In progress:** active work.
- **Accepted:** decision frozen or acceptance evidence complete.
- **Deferred:** explicitly outside the current phase.
- **Rejected:** evaluated and intentionally not adopted.

---

## A. Phase 0A — Product, sources, and operating boundary

| ID | Priority | Decision or action | Required evidence / acceptance | Status |
|---|---:|---|---|---|
| A-01 | Critical | Freeze initial user and distribution boundary | Written statement covering private/internal use, public or paid distribution, personalization, and intended future boundary | Open |
| A-02 | Critical | Select one discovery company and three consecutive quarters | Source package exists for each quarter; at least one management commitment can be tracked across periods | Open |
| A-03 | Critical | Define the manual baseline workflow | Time-stamped steps for how an analyst currently reads, verifies, calculates, writes, and approves an update | Open |
| A-04 | Critical | Freeze the first output contract | Approved list of sections, evidence labels, calculation appendix, open questions, memory draft, and approval record | Open |
| A-05 | Critical | Create provider and data-rights register | For every source: automation, caching, retention, commercial use, derived outputs, redistribution, account limits, and replacement path | Open |
| A-06 | Critical | Run XBRL-versus-PDF spike | Coverage matrix by company, quarter, statement, segment, note, ownership/share count, and reconciliation effort | Open |
| A-07 | High | Define initial workflow budgets | Initial ceilings or measurement rules for model cost, tool calls, latency, document volume, retries, and analyst minutes | Open |
| A-08 | High | Appoint golden-test-set owner | Named owner, repository location, review cadence, and first twenty labeled cases | Open |
| A-09 | Medium | Verify project name and trademark risk | Search record and decision on continued use of “Funda” | Open |

---

## B. Phase 0.5 — One company, three quarters

| ID | Priority | Decision or action | Required evidence / acceptance | Status |
|---|---:|---|---|---|
| B-01 | Critical | Implement a fixed, resumable earnings-review state machine | State definitions, allowed transitions, failure states, and run-resume behavior documented and tested | Open |
| B-02 | Critical | Produce three real incremental earnings updates | Each update includes sources, facts, changes, management ledger, thesis impact, calculations, open questions, and approval record | Open |
| B-03 | Critical | Establish source-of-truth matrix | Approved authority table for raw documents, SQL facts, claims, calculations, narrative memory, indices, and reports | Open |
| B-04 | Critical | Measure analyst review economics | Median and 90th-percentile review time, accepted-unchanged rate, correction categories, and source-verification time | Open |
| B-05 | Critical | Derive minimum source and fact schemas from actual use | Schema supports raw/normalized values, dimensions, scope, source location, valid time, knowledge time, revisions, and quality status | Open |
| B-06 | Critical | Derive minimum typed claim schema | Subject, predicate, object, scope, horizon, epistemic class, confidence, status, and supersession are represented | Open |
| B-07 | High | Define minimum deterministic compute | Approved list of calculations required for the MVP, with input and trace contracts | Open |
| B-08 | High | Record failure taxonomy | Extraction, reconciliation, source, unit, period, calculation, citation, inference, and review failures categorized | Open |
| B-09 | High | Start point-in-time capture | Daily/event jobs persist membership/security changes, prices, announcements, corporate actions, shareholding changes, hashes, and first-seen times | Open |
| B-10 | High | Decide which speculative blueprint fields to remove or defer | Schema-delta document showing retained, deleted, added, and deferred fields with reasons | Open |

---

## C. Phase 1 — Evidence-grounded MVP

| ID | Priority | Decision or action | Required evidence / acceptance | Status |
|---|---:|---|---|---|
| C-01 | Critical | Expand to two or three core non-financial companies | Companies selected for disclosure quality, history, and differing but manageable structures | Open |
| C-02 | Critical | Build immutable document registry and object store | Original files, URLs, timestamps, hashes, parser versions, and extraction warnings are preserved | Open |
| C-03 | Critical | Implement append-only fact and revision model | Restatements and conflicting observations are preserved; no silent overwrite | Open |
| C-04 | Critical | Implement claim/evidence validation | Material claims cannot publish without source or calculation support; contradiction status is visible | Open |
| C-05 | Critical | Build claim-level review UI/workflow | Accept, reject, edit, defer, source jump, calculation inspection, and diff-only review are supported | Open |
| C-06 | Critical | Put authoritative corporate actions in SQL | Splits, bonuses, rights, demergers, dividends, ticker changes, and delistings are versioned events | Open |
| C-07 | High | Put factual entity relationships in bitemporal SQL | Parent/subsidiary, management roles, ownership, cross-holdings, and validity intervals are represented | Open |
| C-08 | High | Implement minimum deterministic calculations | Growth, margins, cash conversion, leverage, dilution/share count, guidance comparison, and reconciliation traces pass tests | Open |
| C-09 | High | Implement complete run manifest | Inputs, cutoff, sources, tools, models, prompts, code versions, costs, calculations, QA, and approvals are registered | Open |
| C-10 | High | Establish correction and supersession workflow | Corrections create new versions; invalidated items remain auditable; canonical promotion is separately approved | Open |
| C-11 | High | Prohibit product dependence on raw model scratchpads | Stored records are evidence, tool traces, structured decisions, QA results, and concise rationales | Open |
| C-12 | High | Set Phase 1 analyst-economics gate | Pre-agreed improvement versus Phase 0.5 manual baseline is demonstrated | Open |
| C-13 | Medium | Decide treatment of consensus estimates | Licensed and necessary, or explicitly excluded from the MVP | Open |
| C-14 | Medium | Add official-audio transcription where needed | Original audio, model/version, timestamps, confidence, and correction history are preserved | Deferred |

---

## D. Phase 2 — Memory evaluation

| ID | Priority | Decision or action | Required evidence / acceptance | Status |
|---|---:|---|---|---|
| D-01 | Critical | Implement `MemoryStore` interface before choosing engine | Retrieval, staged write, promotion, correction, deletion, and export contracts are engine-neutral | Open |
| D-02 | Critical | Run three-arm memory benchmark | Compare no memory, Git/Markdown/SQL, and GBrain on recall, contradiction, stale claims, analyst time, unsupported claims, latency, and cost | Deferred |
| D-03 | High | Define canonical memory promotion transaction | Narrative content hash/commit is registered in SQL; partial writes cannot create split-brain state | Deferred |
| D-04 | High | Verify GBrain repository and dependency posture | Repository, license, maintainers, activity, tests, security, export path, and pinned version recorded | Deferred |
| D-05 | High | Decide GBrain adoption | Adopt only if benchmark benefit exceeds operational and upgrade burden | Deferred |

---

## E. Phase 3 and later — Conditional capabilities

| ID | Priority | Decision or action | Required evidence / acceptance | Status |
|---|---:|---|---|---|
| E-01 | High | Add model-grade financial compute | Statement tie-outs, DCF/SOTP/WACC, sensitivities, and sector definitions are reproducible and fail closed | Deferred |
| E-02 | High | Add stress-test companies | One bank/NBFC, one conglomerate, and one difficult disclosure/corporate-action case | Deferred |
| E-03 | High | Evaluate bull/bear and forensic review | Compare with single senior-reviewer baseline; retain only if incremental valid issue detection justifies cost | Deferred |
| E-04 | High | Add event monitoring | Alerts identify which fact, assumption, catalyst, promise, or thesis breaker changed; immaterial events do not rewrite thesis | Deferred |
| E-05 | High | Begin controlled quant validation | Uses collected point-in-time data; leakage, revisions, universe history, fees, liquidity, and benchmark are disclosed | Deferred |
| E-06 | Medium | Evaluate OpenBB deployment | If used, it remains out of process and behind Funda contracts; license and replacement path approved | Deferred |
| E-07 | Medium | Verify FinanceHarness and Vibe-Trading before reuse | Exact repositories, licenses, test quality, provider assumptions, and pinned versions recorded | Deferred |
| E-08 | Critical | Gate any paid/public research on current legal review | Current regulatory obligations, disclosures, reviewer responsibilities, and distribution controls documented | Deferred |
| E-09 | Critical | Keep execution in a separate trust domain | Separate service, credentials, database, deterministic limits, approvals, kill switch, and reconciliation | Deferred |

---

## F. Phase-gate scorecard

### Phase 0.5 may exit only when

- three real updates have been produced and reviewed;
- analyst review time is measured;
- the source-of-truth matrix is approved;
- minimum fact and claim schemas are based on actual workflow evidence;
- the XBRL/PDF split is understood;
- point-in-time capture has started;
- the first golden cases are automated or reviewable.

### Phase 1 may exit only when

- all material numerical claims resolve to a fact or calculation trace;
- material citations resolve to the correct source location;
- units, period, currency, and statement scope are explicit;
- missing inputs fail closed;
- corrections and supersession are auditable;
- analyst effort improves against the baseline by the agreed threshold;
- cost, latency, and failures are visible;
- GBrain, debate, backtesting, and execution remain outside the release unless separately approved.

### Phase 2 may exit only when

- the selected memory approach improves measurable workflow outcomes;
- stale and contradicted conclusions are surfaced;
- canonical promotion cannot diverge from SQL metadata;
- correction, deletion, backup, and export have been tested;
- operational burden is acceptable.

---

## G. Explicitly deferred from the first release

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
- local-model optimization without a Funda-specific benchmark.

---

*End of implementation decision register.*
