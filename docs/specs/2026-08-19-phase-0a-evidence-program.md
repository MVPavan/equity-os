# Phase 0A Evidence Program

Status: approved
Approved by: Current user on 2026-08-19, bound to pre-approval SHA-256 `5e8bfb585fcb0891e9b04f0a9088b9f2374c7390523316f2fcbc3a080f3b7040`.

## Problem Statement

Equity-OS has an approved architecture and sourcing direction, but it does not
yet have the authority-backed evidence needed to fix the initial operating
boundary, choose and instrument the discovery slice, or judge whether that
slice is safe and useful. Without one coherent evidence program, the Phase 0A
decisions could be produced as disconnected documents whose scopes,
dependencies, measurements, and human authorities do not line up.

## Solution

Run one integrated Phase 0A evidence program covering register items A-01
through A-13. It starts with the product boundary, discovery company, four
quarters, and source package; uses that concrete slice for the filing-channel
spike and manual baseline; then freezes the evidence-derived contracts and
operating controls needed for the next blueprint phase.

The recommended initial distribution boundary is private/internal research.
Public, paid, personalized, and execution-connected uses remain prohibited
unless E-08 is separately activated and satisfied through distinct current
`LEGAL_REVIEW`, `REGULATORY_REVIEW`, and `DISTRIBUTION_APPROVAL` authorities.
This spec does not activate E-08.

Architecture v2 and the three-tier sourcing direction are settled inputs. The
program therefore evaluates official structured/XBRL sources first, uses
official PDFs and other official unstructured documents for demonstrated
coverage gaps, and permits a licensed vendor feed only as a rights-permitted
reconciliation cross-check. It selects no provider, feed, parser, library,
model, or purchase.

Preparatory work may collect, structure, and test evidence autonomously within
an already authorized scope. It may not synthesize a human decision. Every
unresolved product-owner, legal, source-rights, analyst, or expressly assigned
domain/evaluation fixture or metric judgment is a named evidence output with a
fail-closed result until the competent human authority decides it; none is an
open implementation question.

This spec is governed by the v2 decision register and the current blueprint
completion contract. It uses the approved Architecture v2 brief for workflow,
sourcing, and release-boundary constraints without reviving historical spec or
clause-ledger closure as a prerequisite.

## User Stories

1. As the product owner, I want one evidence-backed view of the initial user,
   distribution boundary, discovery slice, and operating constraints, so that
   I can make scoped decisions without implying legal, rights, or domain
   approval.
2. As the analyst, I want the same lightweight instrumentation applied to the
   manual baseline and later assisted reviews, so that review economics can be
   compared without changing the measurement method between lanes.
3. As the source-rights or legal authority, I want each proposed use and product
   identity presented with explicit facts, unknowns, and prohibited actions, so
   that my decision is narrow, attributable, and not inferred from another
   approval.
4. As the analyst or domain authority, I want materiality, output, golden-set,
   and success-metric evidence derived from one real company and source package,
   so that the next blueprint phase does not build against invented thresholds
   or abstract schemas.
5. As the later implementation team, I want every Phase 0A item owned exactly
   once with checkable outputs and dependency order, so that approved evidence
   can be decomposed into work without recreating a row-by-row specification
   program.

## Implementation Decisions

### One integrated program

Phase 0A is one specification and one implementation sequence. The outputs have
different competent authorities, but they share the same discovery slice,
source package, instrumentation, acceptance boundary, and downstream consumer.
Splitting boundary, sources, baseline, evaluation, and operating controls into
separate specs would create cross-spec contract negotiation before any real
workflow evidence exists.

Spec approval approves this program shape and its constraints. It does not
approve a company, a source right, a product identity, a legal conclusion, a
materiality policy, a metric threshold, or a budget. Those remain explicit
outputs of the program.

### Decision and evidence envelope

Every evidence output records its version, exact scope, author, collection or
decision time, source references, and content digest. Every human decision also
records the deciding individual, competent authority role, decision, rationale,
and the exact evidence version reviewed. Missing, stale, conflicting, or
out-of-scope evidence produces `BLOCKED` or `UNKNOWN`, as applicable, and never
an inferred approval.

The competent authorities are:

- **Product owner:** initial distribution boundary, discovery slice, exact
  product identity, budgets, capacity, and success contract.
- **Analyst:** manual baseline, output usability, bootstrap thesis, the A-10
  concrete materiality policy, and coverage-specific analytical judgments.
- **Source-rights authority:** each source/use rights determination; legal
  review is included where the organization requires it.
- **Trademark/legal authority:** product-name search record and legal or
  trademark risk assessment, without selecting the product identity.
- **Domain or evaluation authority:** preparation or validation of expressly
  assigned validator fixtures, metric methods, and golden-set labels; the
  evidence names the individual who holds each role.

No authority is transferable by implication. In particular, architecture
approval, source-rights approval, analyst acceptance, and program-spec approval
cannot satisfy a product-owner, trademark/legal, or expressly assigned
domain/evaluation validation decision.

### Exact scope and primary ownership

The following table is the sole primary-ownership mapping in this spec. Its ID
set must equal `{A-01, A-02, A-03, A-04, A-05, A-06, A-07, A-08, A-09, A-10,
A-11, A-12, A-13}` with no duplicate primary owner.

| Register item | Primary evidence output | Checkable content and decision boundary |
|---|---|---|
| A-01 | Initial Boundary Decision | Identifies intended users and classifies private/internal, public, paid, personalized, execution-linked, and intended-future use separately. The proposed initial result is private/internal allowed and every external or execution-linked mode prohibited. The product owner decides; the record expressly does not claim legal sufficiency. |
| A-02 | Discovery Slice Selection | Names one company and four consecutive quarters, reserves Quarter 0 for the manual baseline/bootstrap thesis and Quarters 1–3 for assisted updates, proves a source package exists for each quarter, and identifies at least one management commitment trackable across the period. The product owner selects; the analyst attests analytical suitability. |
| A-03 | Manual Baseline Package | Records time-stamped reading, exact source location, verification, deterministic or manual calculation trace, drafting, review, correction, and analyst approval for Quarter 0. Instrumentation uses the same event definitions intended for assisted reviews and reports its own overhead. |
| A-04 | Output Contract | Produces a provisional v0 before baseline work is measured, then an evidence-derived final version after the baseline. It covers the event and cutoff, facts, changes, drivers, management ledger, thesis impact, observable falsifiers, open questions, calculations, non-canonical memory draft, and approval record. The analyst accepts usability; the product owner approves scope. |
| A-05 | Source Rights Package | Enumerates every source in the selected source package and records access method, automation, caching, retention, commercial use, derived outputs, redistribution, account limits, point-in-time availability, and replacement path for the exact intended use. Each use has a current source-rights decision; missing or ambiguous rights are `UNKNOWN` and deny acquisition, transformation, or use. |
| A-06 | Filing Coverage Spike | Compares the selected company and quarters by filing channel, taxonomy/version, statement, segment, note, ownership/share count, restatement behavior, mapping stability, and reconciliation effort. It preserves unknown, absent, and not-applicable as distinct results and reports gaps per company-quarter rather than hiding them in an aggregate score. |
| A-07 | Workflow Budget Contract | Defines a `CEILING` or `MEASUREMENT_RULE` for model cost, tool calls, latency, document volume, retries, and analyst minutes. An unapproved ceiling is represented as `CEILING_NOT_APPROVED`, not as unlimited capacity. The product owner approves ceilings after the measurement method exists. |
| A-08 | Golden Set Charter and Initial Set | Names the accountable owner and individual, repository location, review cadence, label authority, and at least twenty expert-labeled initial cases. The set includes prompt-injection and source-confusion cases plus representative source, period, unit, citation, numerical-trace, unsupported-claim, and materiality failures. |
| A-09 | Product Identity Decision Pair | Produces (1) a search record and risk assessment from the trademark/legal authority covering continued use of “Funda” and the exact candidate identity, and (2) a separate product-owner decision selecting or rejecting that exact identity. The records have different decision types and neither can satisfy or infer the other. |
| A-10 | Materiality Policy and Validator Set | Versions quantitative magnitude rules, thesis relevance, source conflict/uncertainty, coverage-specific overrides, and always-material categories covering guidance, restatements, auditor qualifications, going concern, promoter pledges, related-party transactions, capital raises or material dilution, major corporate actions, management changes, and regulatory actions. An always-material category resolves to material; an important unresolved conflict, missing input, or low-confidence result resolves to review required. The analyst approves the concrete policy and validator set; a domain or evaluation authority may only prepare or validate expressly assigned fixtures or metrics. |
| A-11 | Approved Bootstrap Thesis | Uses the accepted Quarter 0 baseline to record a concise thesis, assumptions, management commitments, risks, open questions, and observable falsifiers. The analyst authors and approves an exact version before Quarter 1 can begin; the artifact is not full company initiation. |
| A-12 | Operating Capacity Contract | Records weekly builder and analyst capacity, target dates, monthly provider/model/infrastructure ceilings, maintenance allowance, and expected company coverage. The product owner approves it against the selected company, observed manual work, and available personnel rather than an assumed throughput. |
| A-13 | Success Metric Contract | Versions definitions, units, scopes, collection methods, phase applicability, and correction rules for factual accuracy, citation correctness, numerical traceability, unsupported claims, analyst minutes, per-claim verification time, coverage capacity, latency, cost, and failure/retry rate. The product owner approves targets; the analyst and evaluation authority accept the collection method. |

### Minimal execution order

1. **Boundary, discovery company, and source package.** Prepare and obtain the
   A-01 decision; select the A-02 company and quarters; enumerate the exact
   source package; then complete the applicable A-05 rights decisions before
   any new acquisition, transformation, or use.
2. **A-06 spike and manual-baseline foundation.** Run the filing-channel spike
   on rights-permitted package content while preparing the manual workflow.
   Freeze the A-04 provisional v0, A-10 policy, and A-13 measurement method
   before the first measured A-03 baseline action.
3. **Manual baseline, final output, and thesis.** Execute and approve the A-03
   baseline; use its evidence to finalize A-04; then author and approve A-11.
   Quarter 1 remains blocked until the exact approved bootstrap thesis exists.
4. **Budgets, capacity, evaluation, and identity.** Derive A-07 and A-12 from
   the accepted measurement evidence; establish A-08; complete both A-09
   decisions. These activities may start earlier when they do not assume an
   unsettled company, source right, measurement definition, or boundary.
5. **Integrated acceptance.** Validate exact A-01 through A-13 coverage,
   dependency satisfaction, current authority, digest integrity, and all
   success criteria below. Blueprint-phase exit remains governed by the v2
   register rather than a copied status table or paraphrased gate.

### Three-tier sourcing behavior

The source package records filing channel independently from sourcing tier.
Tier 1 official structured/XBRL content is evaluated first for each required
measurement. Tier 2 official unstructured content fills only gaps demonstrated
by the A-06 matrix and retains exact locations in immutable original content.
Tier 3, if later licensed and rights-permitted, may record a reconciliation
observation but cannot become primary, fill a missing official-source gap, or
win a conflict merely because it came from a vendor.

A source disagreement remains visible for analyst disposition. Unknown rights,
unknown cutoff eligibility, missing source location, or a gap that no permitted
tier fills stays blocked or becomes an explicit analytical open question in the
output; it never becomes an improvised fact.

### Measurement behavior

Manual and assisted workflows use one versioned instrumentation vocabulary and
collection method. A measurement records actor, start and end semantics, scope,
units, exclusions, correction lineage, and instrumentation overhead. Changing a
definition creates a successor version and does not rewrite earlier results.

Metric targets and budget ceilings are evidence-derived human decisions. Cost,
latency, and throughput cannot compensate for a failed quality or rights check.
Small samples are reported as observations; the program does not invent
percentile claims unsupported by sample size.

## Success Criteria

### Happy path

1. Given the program's evidence inventory, an exact-set check finds every ID
   from A-01 through A-13 once as primary ownership, no ID outside that set,
   and no duplicate evidence output claiming primary ownership.
2. Given the selected company and four quarters, every quarter has an identified
   source package, rights disposition for each intended operation, cutoff-aware
   provenance, and at least one management commitment spanning periods.
3. Given the Quarter 0 package, the A-06 matrix is complete at its declared
   dimensions and the manual baseline can be reconstructed from timestamps,
   source locations, calculation traces, corrections, instrumentation events,
   and the exact analyst approval.
4. Given the accepted baseline, the final output contract, bootstrap thesis,
   materiality policy, success metrics, workflow budgets, capacity contract,
   and golden set all cite the evidence versions from which they were derived
   and carry the required human decisions.
5. Given a documentary Phase 0.5 entry-readiness review, the applicable v2 gate
   evidence is current and the exact approved bootstrap thesis is present; a
   draft, missing, stale, or hash-mismatched thesis fails the documentary check.
   Run-registration and state-machine enforcement are deferred to B-01.

### Error and edge cases

| Condition | Required behavior |
|---|---|
| A source or intended use is missing from the rights package | The operation is `UNKNOWN` and denied; no unregistered fallback source is substituted. |
| Rights permit access but not automation, transformation, retention, derived output, or redistribution | Only the independently permitted operations may proceed; access permission is not widened. |
| Structured and official unstructured sources disagree | Both observations and provenance remain visible; an analyst records the disposition, and an important unresolved conflict requires review. |
| A required filing dimension is absent, unknown, or not applicable | The matrix preserves the distinct state and company-quarter location; no aggregate score converts it to covered. |
| Instrumentation fails or its overhead is not measurable | The affected comparison is invalid and cannot support a metric target, budget, or capacity decision. |
| A material observed or computed result lacks an exact source location or calculation trace | Validation fails; the result cannot enter the accepted baseline, output contract evidence, or bootstrap thesis as supported. |
| A human decision is absent, stale, out of scope, or made by the wrong authority | The dependent output is blocked; another approval is not reused or inferred. |
| Trademark/legal review and product-owner identity selection disagree or one is absent | Product identity remains undecided and continued use is not authorized by the other record. |
| Fewer than twenty golden cases exist, labels lack competent ownership, or injection/source-confusion cases are absent | A-08 acceptance fails; cases are not padded with unlabeled or duplicate fixtures. |
| A company lacks four usable consecutive quarters or a trackable management commitment | The company is rejected and selection returns to A-02; requirements are not waived. |

### Out of bounds

- This spec does not define successful public, paid, personalized, or
  execution-connected distribution.
- This spec does not define provider selection, procurement, credentials, or a
  technical ingestion implementation.
- This spec does not define assisted Quarter 1–3 product behavior or claim that
  Phase 0.5 has begun.
- This spec does not define full initiation, generalized schemas, or future
  analytical methods.
- This spec does not redefine the v2 register's phase-exit authority.

## Testing Decisions

Testing occurs at the evidence-contract seam because Phase 0A produces
decisions, fixtures, and measured workflow evidence rather than product code.
Tests assert externally reviewable records and fail-closed outcomes, not the
layout or filenames chosen during planning.

1. **Structural contract tests:** validate required fields, enum values,
   versions, digests, exact A-01 through A-13 set equality, source-package to
   rights-record set equality, four-quarter continuity, and twenty-case minimum.
   The v2 register is the expected contract; historical ledgers are not test
   inputs.
2. **Integrated baseline reconstruction:** replay the evidence trail from the
   selected Quarter 0 source package through the manual output and bootstrap
   thesis. The test passes only when every accepted material observed result
   resolves to its exact source, every accepted material computed result
   resolves to its calculation trace, supported interpretations retain their
   evidence and assumptions, and every correction remains visible.
3. **Instrumentation equivalence:** feed equivalent manual and assisted-shaped
   events into the metric definitions and verify identical scope, timing,
   correction, and overhead treatment. No assisted research run is required to
   test the event contract in Phase 0A.
4. **Authority and negative-path tests:** exercise missing, stale, conflicting,
   and wrong-role decisions; unknown rights; absent cutoff evidence; source
   conflicts; incomplete filing coverage; missing material support; and
   trademark/product-owner mismatch. Each must yield the specified blocked,
   denied, failed, or review-required outcome.
5. **Domain fixture tests:** run the approved A-10 validator cases and A-08
   golden cases at their declared evaluation seam. Results remain stratified by
   materiality and epistemic class, and shadow or fixture outcomes cannot be
   treated as production approval.

There is no existing first-party code or CI seam to reuse. Planning may choose
the smallest automation needed for these checks after this spec is approved;
the check semantics above remain implementation-independent.

## Out of Scope

- Phase 0.5 product implementation and the three assisted quarterly updates —
  deferred to the next applicable blueprint phase after its entry conditions
  are satisfied.
- Provider, feed, parser, extraction library, database, hosting, model, or agent
  selection; procurement, provider contact, enrollment, and credential use —
  deferred to separately authorized implementation or adoption decisions.
- Public, paid, personalized, or execution-connected output, plus any claim of
  legal sufficiency — prohibited while E-08 remains `Deferred`. Any later mode
  requires distinct current `LEGAL_REVIEW`, `REGULATORY_REVIEW`, and
  `DISTRIBUTION_APPROVAL` authorities; this spec does not activate E-08.
- Historical 25-spec closure, clause-ledger reconciliation, per-row status
  mirrors, copied phase-gate prose, and dormant future-method work — rejected as
  prerequisites or outputs of this evidence program.
- Full company initiation, generalized autonomous planning, broad schemas,
  model-grade compute, memory-engine selection, debate, backtesting, portfolio,
  and execution — deferred because Phase 0A needs only evidence for the fixed
  discovery workflow.

## Open Questions

None.

## Further Notes

This approval accepts the evidence-program spec only and does not itself decide A-01 boundary, A-02 company/quarters, source rights, legal conclusions, budgets, materiality, metrics, product identity, or Phase 0.5 entry.

Architecture v2 approval is recorded by `eqos-jce`. The three-tier sourcing
decision is recorded by `eqos-9x8`; therefore, the Architecture v2 brief's
historical “proposed” label for that sourcing section no longer represents the
decision state, while its rights, provenance, cutoff, conflict, and fail-closed
constraints remain applicable.

Unknown implementation choices are deliberately absent from Open Questions.
If a choice is needed to produce an in-scope evidence output, it is made during
planning within this spec's constraints; if it selects a provider, tool,
library, model, purchase, external interaction, future capability, or widened
distribution mode, it is outside this spec and requires its own authority.
