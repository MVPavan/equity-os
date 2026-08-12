# Funda Review-on-Review Disposition Report

**Materials assessed**

- `funda-review-analysis-report(1).html`
- `funda-blueprint-final-consolidated-review.md`
- `funda-blueprint-implementation-decision-register.md`

**Assessment date:** 12 August 2026  
**Purpose:** Determine which third-order review findings should be accepted, modified, rejected, or deferred, and translate the result into an implementable document strategy.

---

## 1. Executive verdict

The third-order review is strong and materially improves the two Funda review documents. It correctly identifies that several apparently rigorous gates are not executable as written and that important build-defining semantics are still implicit.

The right response is **not** to accept the report wholesale. Its central findings are valid, but several proposed remedies need refinement:

- the narrative reproducibility gate is ambiguous rather than inherently impossible;
- claim-level observations improve operational measurement but do not become statistically independent merely because there are many of them;
- materiality cannot be reduced to one percentage threshold;
- ISIN should be a versioned external identifier, not Funda's database primary key;
- seeded errors belong in an isolated test or shadow artifact, never in the publishable workflow;
- model-weight leakage is a standing limitation of historical replay, not a blocker for current-period earnings review;
- the recommendation to cancel the three-arm memory benchmark is too strong and should be rejected;
- references to an existing Temporal, Partner, Bodha, homelab, or PostgreSQL setup are not supported by the reviewed documents and should not enter the formal architecture record unless separately confirmed;
- the reviewer’s own measurement repair creates a new contradiction: a non-reused manual baseline plus three assisted updates requires at least four quarters, not the retained three-quarter slice.

### Final disposition

| Review area | Disposition |
|---|---|
| Five gate-spec findings | All point to real issues; four accepted directly, one accepted with narrower wording |
| Nine missing decisions | All identify genuine omissions; several remedies are simplified or split by phase |
| Four traceability-drift findings | Three accepted; one partially accepted |
| Five calls to amend or reverse | Three accepted, one retained as an operational note, one rejected |
| Proposed register rows | Most adopted in revised form |
| D-02 replacement | Rejected; D-02 is retained and reframed |

The **implementation decision register should now be the single operational source of truth for gates and open decisions**. The consolidated review should remain a frozen architectural reference rather than be repeatedly rewritten after every audit.

---

## 2. Gate-spec audit

### G-1 — Narrative reproducibility

**Disposition: Accept with modification.**

The sentence “the report is reproducible from frozen inputs and registered versions” is ambiguous. It may be read as bit-identical regeneration, which is not a safe guarantee for an LLM-generated narrative. However, the gate is not permanently unpassable because the exact approved artifact can be stored and retrieved by hash.

Use three separate guarantees:

1. **Deterministic calculations:** replay under frozen inputs, code, runtime, and operator policy. Exact-class accounting operators should match exactly; floating-point or optimization operators should remain within declared tolerances; stochastic operators require a stored seed and distribution checks.
2. **Evidence package:** exactly reconstructable from registered source, fact, claim, and cutoff identifiers.
3. **Narrative:** the approved published bytes are immutable and bound to a content hash; a later regeneration must be audited against the same approved claim set but need not be text-identical.

This correction belongs in the output contract, run manifest, and Phase 1 gate.

### G-2 — P90 from three reports

**Disposition: Accept.**

A report-level 90th percentile from three updates is not useful. Phase 0.5 should report the three observed totals directly rather than manufacture a percentile.

Claim-level timing is useful, but it is operational telemetry rather than a statistically independent sample. Claims within one report share the same company, sources, model run, and reviewer. Therefore:

- record total analyst minutes for each report;
- record median and distribution summaries for claim dispositions;
- stratify by claim type and correction category;
- do not make statistical-significance claims from the three-report pilot;
- introduce report-level percentiles only after a materially larger run history exists.

### G-3 — Cross-company economics comparison

**Disposition: Accept.**

Comparing assisted work on unfamiliar Phase 1 companies with a manual baseline from the now-familiar discovery company confounds company complexity, analyst familiarity, and tooling effect.

The gate should use:

- a manual baseline for each Phase 1 company or a matched historical quarter;
- normalized operational measures such as verification time per material claim, source-locate time, and correction time;
- explicit complexity descriptors such as document count, page count, claim count, and number of reconciliation exceptions;
- total report time retained as a business metric, but not treated as a portable causal measure by itself.

### G-4 — Practice effect

**Disposition: Accept.**

The same analyst should not manually review a quarter and then use the tool on the same quarter as the primary economics comparison. Familiarity will make the second pass faster.

A practical solo-builder design is:

- use **one baseline/bootstrap quarter plus three later assisted quarters**, making the minimum coherent discovery slice four consecutive quarters;
- use different quarters for manual and assisted runs;
- counterbalance order where possible across companies;
- preserve the confound in the experiment log when it cannot be removed;
- rely on time-and-motion components, not only whole-report elapsed time.

### G-5 — Undefined materiality

**Disposition: Accept, but broaden the remedy.**

The validator cannot enforce “all material claims” until materiality is operationally defined. A single quantitative percentage is insufficient because a small number may still be thesis-critical, governance-critical, or legally significant.

The minimum materiality policy should combine:

- **quantitative magnitude:** relative to the relevant statement line, segment, guidance range, equity, enterprise value, or prior assumption;
- **always-material categories:** guidance, restatements, auditor qualifications, going-concern language, promoter pledges, related-party transactions, capital raises, material dilution, major corporate actions, management changes, and regulatory actions;
- **thesis relevance:** whether the item changes an assumption, catalyst, risk, valuation input, management-credibility assessment, or thesis breaker;
- **uncertainty and source conflict:** unresolved contradictions or low-confidence extraction of an otherwise important item;
- **coverage-level overrides:** company- or mandate-specific thresholds stored with a policy version.

The materiality decision itself should be reviewable and versioned.

---

## 3. Missing-decision audit

### M-1 — Thesis cold start

**Disposition: Accept.**

The first incremental workflow requires a prior approved thesis, but no bootstrap path exists. Do not expand Phase 0.5 into a full initiation product. Use the first of four consecutive quarters as the manual baseline/bootstrap quarter and create a concise analyst-authored **bootstrap coverage thesis** containing current thesis, key assumptions, management commitments, risks, open questions, and observable falsifiers. Approve and version it before the three later assisted updates.

Full company initiation remains deferred.

### M-2 — Fact identity and revision semantics

**Disposition: Accept; the required model is richer than a single key.**

The system needs to distinguish four concepts:

1. **source occurrence:** the value as it appears in a specific source location;
2. **extraction result:** parser/model output for that occurrence and parser version;
3. **economic measurement slot:** the intended metric, entity, period, scope, dimensions, and definition;
4. **approved canonical selection:** the observation Funda currently uses for a specified knowledge cutoff.

A robust design should include:

```text
measurement_key
  = entity
  + metric definition/version
  + period
  + statement/consolidation scope
  + dimension set
  + accounting/adjustment basis

observation_id
  = immutable source occurrence

revision_family_id
  = observations believed to represent the same measurement slot

revision_reason
  = issuer restatement
  | source correction
  | parser re-extraction
  | manual correction
  | normalization-policy change
```

A parser upgrade should normally create a new extraction result, not silently rewrite the economic observation. Restatements, reclassifications, and segment-definition changes require explicit reconciliation rather than automatic supersession by key.

### M-3 — Predicate and metric vocabulary governance

**Disposition: Accept with a simpler Phase 0.5 implementation.**

Typed claims are ineffective without controlled predicates and metric definitions. The first version needs:

- a small versioned metric registry;
- a small versioned claim-predicate registry;
- aliases and deprecated terms;
- definition, expected object type, units/dimensions, and scope rules;
- a human approval rule for additions.

Embedding-assisted duplicate suggestions are optional later. They should not be a Phase 0.5 dependency for a registry containing only dozens of entries.

### M-4 — Knowledge-time enforcement and leakage

**Disposition: Accept, split into two policies.**

**Current and historical data access controls** are implementation requirements:

- every run has a cutoff;
- SQL, document, memory, and fact retrieval enforce `knowledge_time <= cutoff`;
- canonical fact and relationship selection is evaluated **as of that cutoff**, so later corrections or restatements do not retroactively rewrite a historical package;
- tool calls declare whether they are cutoff-aware;
- historical replay permits only approved archived or time-bounded sources;
- tests deliberately insert post-cutoff records and verify that retrieval excludes them.

**Model-weight leakage** is different. It cannot be eliminated and must be disclosed for historical LLM evaluation. It does not invalidate current-period earnings review, where the run date is current and the model is not being evaluated as if it were historically ignorant.

### M-5 — Human-feedback rework transitions

**Disposition: Accept.**

“Resumable” must include correction after human review, not only restart after a crash. The workflow needs:

- immutable step outputs;
- idempotent step re-entry;
- evidence-package versioning;
- dependency-aware invalidation;
- partial revalidation when only a subset changes;
- a clear path from rejected claim to source correction, re-extraction, recalculation, redrafting, and reapproval.

SQLite plus explicit state and attempt tables is sufficient for Phase 0.5. A durable workflow platform should be adopted only after observed rework/concurrency complexity justifies it.

### M-6 — Reviewer and builder are the same person

**Disposition: Accept with safeguards.**

“Accepted unchanged” is not a standalone quality metric because careless review can maximize it. Add:

- edit/reject accuracy on known golden cases;
- false-accept and false-reject categories, stratified by materiality and epistemic class;
- periodic seeded-error drills in a **shadow copy or test-mode report only**;
- seeded errors that cover wrong period, unit, source, unsupported claim, and fabricated citation;
- occasional external spot review where practical.

Never inject a known falsehood into the artifact that can be promoted or published.

### M-7 — Entity and security master authority

**Disposition: Accept, but do not use ISIN as the internal primary key.**

Funda should use stable internal `company_id` and `security_id` values. ISIN, exchange symbol, CIN, LEI, and other identifiers are versioned external mappings with valid-time and knowledge-time intervals.

The decision must name:

- source hierarchy for each identifier type;
- conflict-resolution rule;
- symbol and listing changes;
- corporate-action handling;
- one real test case involving an identifier change.

### M-8 — Results-season throughput

**Disposition: Accept and fold into the success-metric contract.**

Coverage capacity during clustered reporting periods is a product constraint. It need not become a separate architecture subsystem, but the register should track:

- reports reviewable per analyst per week;
- peak-week document and claim volume;
- backlog age;
- percent of updates completed before the next material event;
- capacity at the selected Phase 1 company count.

### M-9 — Untrusted-document surface

**Disposition: Accept.**

Add explicit failure and test cases for document text being treated as instructions. The operational controls are:

- source content is data, not control text;
- retrieved text cannot change tools, permissions, cutoffs, or promotion rules;
- memory drafts show provenance at promotion time;
- no document-originated instruction can invoke execution or secrets;
- prompt-injection and source-confusion cases enter the golden set.

---

## 4. Register-to-review traceability audit

### T-1 — Operating budget and calendar disappeared

**Disposition: Accept.**

Per-run ceilings do not replace a team/calendar/provider budget. Add a separate row for weekly builder capacity, target phase dates, monthly provider/model/infrastructure ceilings, analyst-review capacity, and maintenance burden.

### T-2 — Success metrics are scattered

**Disposition: Accept.**

Create one versioned success-metric contract covering definitions, units, measurement procedures, and phase applicability for:

- factual accuracy;
- citation correctness;
- numerical traceability;
- unsupported-claim rate;
- analyst minutes;
- verification time per claim;
- coverage capacity;
- latency;
- model/tool cost;
- failure and retry rates.

All phase gates should reference this contract.

### T-3 — Gate wording lives in multiple places

**Disposition: Accept.**

The implementation register should own the live gate wording. The consolidated review should state principles and rationale but should no longer be edited as the operational checklist.

### T-4 — Regulatory verification before boundary statement

**Disposition: Partially accept.**

A-01 can define the intended product boundary without completing legal analysis. It should avoid claiming that the chosen boundary is legally sufficient. Current regulatory verification becomes mandatory before external, paid, personalized, or execution-connected use, not necessarily before documenting the initial private-use intent.

---

## 5. Calls to amend or reverse

### R-1 — Cancel D-02 memory benchmark

**Disposition: Reject.**

The benchmark's purpose is to decide whether GBrain is justified **for Funda at the scale and workload that exist when Phase 2 begins**. A result showing no advantage at that scale is not a false negative; it is a valid reason not to adopt the dependency yet. The arms must be fair: each receives access to the same authoritative prior artifacts, while the benchmark varies how context is persisted, retrieved, and assembled.

The reviewer is right that such a result must not be interpreted as a permanent verdict on all future scales. Therefore retain D-02 and amend it as follows:

- state that the result governs current adoption only;
- define minimum query/task coverage and avoid a ceiling-only test set;
- include operational burden, not just retrieval quality;
- instrument retrieval misses and contradictions caught later by humans;
- predefine re-evaluation triggers based on corpus size, cross-company graph needs, and observed miss rate.

This combines a present-scale benchmark with a trigger-based future reconsideration.

### R-2 — Add filing channel and taxonomy version to A-06

**Disposition: Accept.**

The XBRL/PDF spike should explicitly distinguish exchange quarterly-result XBRL, annual channels, issuer documents, and taxonomy/version changes. The spike should measure mapping stability, not merely field coverage.

### R-3 — Make A-05 depend on A-01

**Disposition: Accept.**

The intended use boundary determines which rights are required. A-05 should be scoped to the initial boundary while retaining fields for future commercial/public modes. This prevents an open-ended legal exercise from blocking the private research slice.

### R-4 — Add observable falsifiers

**Disposition: Accept.**

The output contract should state what observable event, metric, management outcome, or evidence would materially weaken or reverse the current thesis. This is distinct from listing generic risks.

### R-5 — Predefine the SQLite migration trigger

**Disposition: Retain as an operational note, not a new critical decision.**

SQLite remains appropriate for the vertical slice and small pilot. Record migration triggers in the storage ADR, such as persistent writer contention, multi-user remote access, reliability requirements, or operational complexity that exceeds a single-writer design.

---

## 6. Corrections to the third-order review

The following reviewer statements should not be copied into the formal Funda record without qualification.

### 6.1 “Hundreds of claims” do not create hundreds of independent samples

Claim-level telemetry is useful, but claims are clustered within reports and companies. Use it for operations and error analysis, not unsupported significance claims.

### 6.2 Materiality is not only a financial-statement threshold

The proposed percentage rule is one component. Governance, guidance, thesis relevance, and source conflict must also be represented.

### 6.3 ISIN is an external identifier

Use an internal stable identifier as the primary key. ISIN is a high-value mapping, not the authority for Funda object identity.

### 6.4 D-02 answers a present adoption question

A small-corpus benchmark may correctly show that a simpler store is sufficient. Future triggers should reopen the question; the benchmark should not be cancelled on the assumption that a larger future corpus might behave differently.

### 6.5 Model-weight leakage is scoped to historical claims

It is a standing caveat for historical LLM replay and agent-alpha claims. It is not a reason to weaken current-period evidence controls or block the current earnings-review MVP.

### 6.6 Seeded errors require isolation

They are reviewer-QA tests, not production data. Use shadow reports or golden fixtures and prevent all promotion paths from touching them.

### 6.7 Infrastructure assumptions are unsupported by the reviewed files

The report's references to Temporal, Partner, Bodha, an existing homelab, or an existing PostgreSQL deployment may come from context outside the two documents. They should remain outside the architecture record until explicitly confirmed. The underlying general recommendation—do not build a bespoke workflow engine and migrate storage only when earned—remains sound.

### 6.8 The repaired measurement design no longer fits three quarters

The review retains a one-company, three-quarter slice while also requiring a manual baseline on quarters not reused for assisted runs. Because B-02 requires three assisted incremental updates, these conditions cannot all hold simultaneously. The minimum internally consistent slice is:

```text
Quarter 0: manual baseline + approved bootstrap thesis
Quarter 1: assisted incremental update 1
Quarter 2: assisted incremental update 2
Quarter 3: assisted incremental update 3
```

The revised register therefore uses four consecutive quarters. This adds one quarter of source material but removes a fundamental experiment-design contradiction.

### 6.9 Bit-exact computation is not universal

The review correctly separates computation from narrative, but “bit-exact” should apply only to operators designed for exact replay. Floating-point, optimization, and stochastic calculations require declared tolerances, pinned environments, and stored seeds as applicable.

---

## 7. Accepted register changes

The revised register accompanying this report implements the following changes.

### New or expanded Phase 0A decisions

- materiality policy;
- bootstrap thesis;
- operating calendar and standing budget;
- single success-metric contract;
- A-05 dependency on A-01;
- filing-channel and taxonomy-version coverage in A-06;
- provisional output contract before baseline, final freeze after baseline.

### New or expanded Phase 0.5 decisions

- four-quarter discovery design: one manual baseline/bootstrap quarter and three assisted updates;
- fact identity, revision-family, and correction semantics;
- versioned metric and predicate registries;
- reviewer-bias controls and isolated seeded-error drills;
- human-feedback rework path, evidence-package versions, and invalidation rules;
- removal of report-level P90 from the three-update pilot.

### New or expanded Phase 1 decisions

- cutoff enforcement across stores and tools;
- layered reproducibility and artifact-hash approval;
- entity/security master authority;
- results-season throughput and backlog capacity;
- materiality policy referenced by the claim validator;
- economics gate measured per company and normalized by review workload.

### Memory decision

- retain the three-arm benchmark;
- define the result as a current-scale adoption decision;
- add telemetry and re-evaluation triggers.

### Historical evaluation

- disclose model-weight leakage;
- distinguish it from controllable store/tool leakage.

---

## 8. Recommended sequence

The clean sequence is:

1. **A-01:** document intended user/distribution boundary without claiming legal sufficiency.
2. **A-05 and A-09:** rights review scoped to that boundary; name check in parallel.
3. **A-02 and A-06:** select the discovery company, four consecutive quarters, and run the channel-aware XBRL/PDF spike.
4. **A-10 and A-13:** define materiality and measurement methods before collecting the baseline.
5. **A-04 v0:** create a provisional output/claim contract sufficient to instrument the baseline.
6. **A-03 and A-11:** perform the manual baseline on Quarter 0 and author the bootstrap thesis; reserve Quarters 1–3 for assisted updates.
7. **A-04 final:** freeze the first-release contract, including falsifiers and artifact-hash approval.
8. **B-11 and B-12:** freeze the first fact-identity and vocabulary rules exposed by the baseline.
9. **B-01/B-14:** build the fixed workflow with the rejected-claim rework path as a mandatory test.
10. **B-02 onward:** produce the three assisted incremental updates and refine the remaining schema from real failures.

This ordering avoids both circularity and premature freezing: the baseline has a provisional contract to measure against, while the durable contract is frozen only after the baseline exposes actual needs.

---

## 9. Document strategy

Do not create another full rewrite of the consolidated architectural review. Use this structure:

- **`funda-blueprint-final-consolidated-review.md`** — frozen rationale and architectural judgment;
- **`funda-blueprint-implementation-decision-register-v2.md`** — authoritative live decisions and gates;
- **`funda-third-order-review-disposition-report.md`** — audit trail explaining which external review findings were accepted, modified, or rejected;
- later, create the smaller build artifacts already recommended: MVP workflow spec, system-of-record ADR, data contracts, evaluation plan, provider-rights register, and dependency due diligence.

This avoids review-document recursion while preserving traceability.

---

## 10. Final judgment

The third-order review succeeds at its main task: it exposes that several gates were rhetorically rigorous but operationally underdefined. The most important accepted corrections are materiality, thesis cold start, fact identity, cutoff enforcement, human-feedback rework, reviewer-bias controls, and a single success-metric contract.

Its largest overreach is the categorical claim that the GBrain benchmark should be cancelled. The correct decision is to benchmark present value, decline adoption when a simpler system is sufficient, and reopen the decision only when measured retrieval failures or corpus structure justify it.

The implementation posture after this audit is therefore:

> **Freeze the architectural review. Promote the revised register to the live source of truth. Repair measurement and identity semantics before collecting the baseline. Build the vertical slice with rework and cutoff controls. Treat memory as a measured current-scale decision with explicit future re-evaluation triggers.**

---

*This is a technical and product-design assessment, not legal or investment advice. Regulatory and data-rights questions require current primary-source review for the intended deployment mode.*
