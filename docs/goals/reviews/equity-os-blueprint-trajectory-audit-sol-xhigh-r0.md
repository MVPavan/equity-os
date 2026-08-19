# Verdict: `RECOVERABLE_DRIFT`

**Product architecture: on path. Delivery trajectory: recoverably drifting. Current governance route: not the best path forward.**

Equity-OS still points at the intended product: a private, evidence-governed earnings-review system with deterministic calculations, point-in-time evidence, human approval, and separately controlled execution. The 25-spec set has not lost the external-project or later-method intent.

The drift is operational. The program has built a pre-code governance system—213 ledger rows, three review classes, hash-chained transitions, embedded validators, 25 prerequisite specs, and hundreds of review artifacts—before selecting the discovery company, running the XBRL/PDF spike, performing the manual baseline, or learning from one real quarterly workflow. That reverses the blueprint’s central instruction: derive durable contracts from actual use and keep future options outside the critical path. `docs/blueprint/funda-blueprint-final-consolidated-review.md:13-21`, `docs/blueprint/funda-blueprint-final-consolidated-review.md:91-118`

This is recoverable rather than fundamental because no first-party product code embodies a wrong architecture, the approved architecture remains aligned, and the future methods are correctly represented as conditional evaluations rather than assumed dependencies.

## Epistemic status

### VERIFIED

- The v2 decision register remains the operational product authority; the disposition report explains its corrections, and the consolidated review is rationale rather than implementation authority. `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md:21-23`, `docs/goals/equity-os-blueprint-completion.md:58-77`
- The first releasable product is a source-backed incremental quarterly thesis update, not autonomous stock selection. `docs/blueprint/funda-blueprint-final-consolidated-review.md:85-88`, `docs/blueprint/funda-blueprint-final-consolidated-review.md:560-598`
- Phase order is 0A decisions and evidence, then a one-company/four-quarter vertical slice, then the evidence-grounded MVP, with memory and later capabilities conditionally evaluated. `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md:27-64`, `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md:68-118`
- The repository remains pre-code. No application package or product roadmap exists; the current work is ledger/review/reconciliation machinery. This matches the project brief’s declared state. `.codex/project/brief.md:22-33`
- The architecture artifact received a clean independent review and explicit user approval. `.beads/issues.jsonl:6`, `docs/goals/architecture/equity-os-architecture-of-record-v2-review-r3.md:3-31`
- The three-tier sourcing direction was selected, but the A-05 rights evidence and A-06 coverage spike remain outstanding. `.beads/issues.jsonl:4`, `docs/goals/architecture/architecture-brief-v2.md:423-459`
- A fresh audit probe found the preimplementation gate still `ready=false`: 110 pending reviews, zero stale reviews, and one unresolved no-implementation proof. This matches the recorded handoff. `docs/goals/handoff/HANDOFF-2026-08-19.md:18-20`
- The structural validator could not complete during this audit because its `bd --readonly` lookup attempted to acquire a database lock in the read-only sandbox. Therefore this audit makes no fresh structural-pass claim. A previous live run is recorded as passing. `.beads/issues.jsonl:44`

### INFERENCE

- The governance system has displaced product discovery. This follows from the concentration of current artifacts and commits in ledger/review mechanics while every empirical Phase 0A action remains open.
- The 25-spec taxonomy preserves conceptual coverage, but requiring every dormant future-method spec to be approval-complete before Phase 0A product work is disproportionate.
- The current architecture can survive a governance reset because it is product-focused and deliberately leaves most tool choices undecided. `docs/goals/architecture/architecture-brief-v2.md:484-506`

### SPECULATION

- If the current process continues unchanged, implementation may conform to speculative contracts more strongly than to evidence from the first real workflow.
- A poorly bounded simplification could lose useful authority traceability. The correction therefore needs an explicitly approved, archived supersession—not informal bypassing of the activated goal.

## Intended product and method/repository roles

| Element | Intended role | Current preservation | Judgment |
|---|---|---|---|
| First product | Fixed, resumable earnings-review workflow producing a reviewed, source-backed incremental thesis update | Preserved in S05/S06/S14/S15 and Architecture v2 | On path |
| XBRL/PDF sourcing | Empirical Phase 0A coverage spike; structured official sources first, official documents fill demonstrated gaps | Preserved; three-tier direction selected, spike not run | Correct design, missing evidence |
| Point-in-time capture | Begin with the first build so future history is not lost; backtesting stays late | Preserved in S09/B-09 | On path |
| Deterministic compute | Minimum traced calculations in MVP; model-grade valuation later | Preserved in S16 and deferred S21 | On path |
| Human review | Primary promotion authority and headline economic metric | Preserved in S07/S08/S15/S18 | On path |
| GBrain | Candidate behind an engine-neutral `MemoryStore`; compare against no memory and Git/Markdown/SQL | Preserved as dormant three-arm evaluation in S20 | On path |
| OpenBB | Optional out-of-process provider adapter, never core authority | Preserved as dormant due diligence in S03 | On path |
| FinanceHarness / Vibe-Trading | Verify repository identity, license, tests, provider assumptions, and pinned versions before reuse | Preserved as dormant due diligence in S03 | On path |
| Debate / forensic review | Later experiment against a single senior-reviewer baseline | Preserved as deferred E-03/S23 | On path |
| Quantitative validation | Later use of accumulated point-in-time history with explicit leakage controls | Preserved as deferred E-05/E-10/S25 | On path |
| VectorBT / NautilusTrader / broker integration | Decisions that deliberately wait until evidence and review workflows exist | Not part of the initial implementation dependency graph, correctly | Not lost |
| Temporal, Partner, Bodha, homelab, existing PostgreSQL | Unsupported assumptions that must not enter the architecture record | Explicitly excluded | Correctly rejected |

The authoritative grounding is clear: GBrain remains a benchmark candidate; OpenBB and the two repository candidates remain due-diligence subjects; debate and quant are later value-gated capabilities. `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md:93-118`, `docs/specs/equity-os-s03-external-tool-due-diligence.md:7-22`, `docs/specs/equity-os-s20-memory-benchmark-gbrain.md:7-39`, `docs/blueprint/funda-blueprint-final-consolidated-review.md:624-639`

## Evidence table

| Intended design | Current path | Gap | Impact | Evidence |
|---|---|---|---|---|
| Learn from one manual baseline and three real assisted updates before freezing durable schemas | All 25 specs must be authored and approved before product implementation | Contracts precede the evidence meant to shape them | Premature abstraction and rework risk | `docs/blueprint/funda-third-order-review-disposition-report.md:447-462`; `docs/goals/equity-os-blueprint-completion.md:864-878` |
| Use smaller build artifacts; keep repository survey and long watchlist outside the critical path | Exact 25-spec program plus cross-spec audit is a universal prerequisite | Future-option documentation sits in the present critical path | Delays the discovery slice without reducing its main risks | `docs/blueprint/funda-blueprint-final-consolidated-review.md:643-665`; `docs/goals/equity-os-blueprint-completion.md:815-852` |
| Preserve traceability sufficient to enforce register authority | 213 rows: 169 canonical occurrences plus 44 aliases, with content-bound scope/evidence/approval reviews | Clause-level traceability has become its own platform | High maintenance and reviewer-failure surface before product evidence exists | `docs/goals/equity-os-blueprint-completion.md:126-190`; `docs/goals/equity-os-blueprint-completion.md:779-813` |
| Avoid review-document recursion | Goal embeds structural, preimplementation, and terminal programs and requires repeated artifact reviews | Review infrastructure recursively generates more reviewed infrastructure | Governance progress is mistaken for product progress | `docs/blueprint/funda-third-order-review-disposition-report.md:466-475`; `docs/goals/equity-os-blueprint-completion.md:1321-1333`, `docs/goals/equity-os-blueprint-completion.md:4602-4867` |
| Start Phase 0A with boundary, company, rights, source spike, metrics, and baseline | Architecture and sourcing direction are approved, but no discovery company, source package, A-06 evidence, baseline, or roadmap exists | The empirical starting conditions remain absent | No product learning has occurred | `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md:31-43`; `docs/goals/architecture/architecture-brief-v2.md:354-367` |
| Review proportionately to risk | Every spec, product task, phase, and final state receives separate review layers; document rounds run through r0–r4 | Blanket review policy exceeds the repository’s own lean/risk-based operating rule | Bottlenecks, capacity failures, and reviewer-created reconciliation work | `docs/goals/equity-os-blueprint-completion.md:893-930`; `AGENTS.md:29-47`, `AGENTS.md:55-57` |
| Later methods remain conditional and must beat simpler baselines | S03, S04, and S20–S25 are explicitly dormant-only | No material method/repository coverage is lost | This part of the decomposition is correct | `docs/goals/equity-os-blueprint-completion.md:854-862`; `docs/goals/architecture/architecture-brief-v2.md:290-327` |
| Correct ledger authority gaps without unnecessary churn | RC-2/3/4 changes four canonical files and 22 rows, leaves readiness false, then requires 65 fresh reviews and a recorder refresh | Correct semantics are coupled to another large governance cycle | Further delay with no product evidence produced | `docs/goals/reviews/ledger/equity-os-blueprint-rc234-reconciliation-design-r1.md:55-68`; `docs/goals/reviews/ledger/equity-os-blueprint-rc234-reconciliation-design-r1.md:326-355` |

## Proportionality judgment

| Control | Judgment | Correction |
|---|---|---|
| Architecture gate | **Keep** | It resolved a real system-boundary question and is already approved. Do not reopen it for ledger-only changes. |
| Phase gate discipline | **Keep** | Retain evidence-based 0A/0.5/1 exits and explicit deferred activation. |
| Preimplementation gate | **Simplify materially** | Gate product code on the load-bearing Phase 0A evidence and current-phase build contracts—not on full closure of every dormant method and every normalized narrative occurrence. |
| 25-spec split | **Keep as reference taxonomy; remove as universal critical-path gate** | Use phase-scoped, smaller build artifacts. Dormant specs remain archived conditional contracts. |
| Canonical ledger | **Supersede with a thinner decision/evidence index** | Track the 60 register rows, disposition references, current status, owner, phase evidence, and approvals. Archive the 213-row ledger and its histories read-only. |
| Per-component inventory reviews | **Stop** | Review authority mapping once per phase/spec boundary; do not triple-review every canonical clause and alias. |
| Agent roles | **Keep** | Orchestrator/Implementer/Reviewer independence is sound. Model/vendor bindings are operational configuration, not product architecture. |
| Review policy | **Make risk-based** | Require independent review for architecture, trust boundaries, authority changes, schema migrations, security-sensitive code, and phase gates. Batch or self-check low-risk work. |
| TERM-0001 lane-token migration | **Defer or close as non-product work** | Historical model metadata does not justify blocking Phase 0A. `.beads/issues.jsonl:45` |

## RC-2 / RC-3 / RC-4 decision

### `SUPERSEDE`

Do **not** apply the current transaction as the next strategic step.

The defects are real:

- RC-2 must bind a multi-spec approval to the complete enumerated spec set and current bytes.
- RC-3 requires distinct domain authority over vocabulary governance.
- RC-4 requires a product-owner identity decision separate from legal review. `docs/specs/2026-08-19-ledger-approval-contract-reconciliation.md:9-27`

But the proposed repair changes four governance artifacts, adds HR-0006 and 22 transitions, satisfies none of the underlying approvals, keeps `ready=false`, makes 62 reviews historical, requires 65 replacements, and requires another recorder refresh. `docs/goals/reviews/ledger/equity-os-blueprint-rc234-reconciliation-design-r1.md:57-68`, `docs/goals/reviews/ledger/equity-os-blueprint-rc234-reconciliation-design-r1.md:326-355`

Because no canonical target has yet changed, this is the lowest-cost point to supersede it with a user-approved governance simplification:

1. Preserve the three semantic corrections.
2. Express RC-2 once in a phase/spec approval manifest rather than twenty component-local approval structures.
3. Retain RC-3 and RC-4 as ordinary typed decision requirements.
4. Archive the current ledger, reviews, and transition histories unchanged.
5. Start a thinner versioned decision/evidence index under an explicitly superseding goal contract.

This is not abandonment: the authority corrections survive. It is not a local simplification of the reviewed transaction: altering that transaction would invalidate its reviewed hashes. It must be a deliberate rank-1 supersession. If the user declines to supersede the activated governance contract, then finishing the exact reviewed RC transaction is the only safe fallback.

## Ordered correction plan

### Immediate

1. **Freeze further canonical ledger work.** Do not apply RC-2/3/4, start the 65-review refresh, or begin TERM-0001.
2. **Approve a governance-reset decision.** Explicitly supersede the activated completion contract while preserving its audit artifacts as immutable history.
3. **Create a thin program index.** Minimum fields: register ID, current authority status, phase, owner/build artifact, evidence refs, human approvals, blocker, and deferred activation predicate.
4. **Convert the 25 specs into reference material.** Do not discard them; remove dormant-only specifications from the Phase 0A/0.5 readiness gate.
5. **Create the missing workstream roadmap** with only 0A → 0.5 → 1 → conditional D-01, as the current contract itself anticipated. `docs/goals/equity-os-blueprint-completion.md:903-913`

### Required before product implementation

1. Complete Phase 0A in the register’s actual order:

   - A-01 boundary;
   - A-05 rights and A-09 name work;
   - A-02 company/four quarters and A-06 measured channel spike;
   - A-10 materiality and A-13 measurement;
   - A-04 provisional output;
   - A-03 manual baseline and A-11 bootstrap thesis;
   - then freeze the final output and minimum workflow-derived contracts.

   `docs/blueprint/funda-third-order-review-disposition-report.md:447-462`

2. Replace the universal spec gate with the smaller build set recommended by the architectural review:

   - earnings-review workflow;
   - system-of-record ADR;
   - evidence-derived data contracts;
   - evaluation plan;
   - provider-rights register;
   - dependency due diligence.

   `docs/blueprint/funda-blueprint-final-consolidated-review.md:643-665`

3. Keep the approved architecture, evidence boundaries, fixed workflow, fail-closed computation, point-in-time capture, and human promotion controls unchanged.
4. Review only the current phase’s load-bearing contracts before code. Schema details that the baseline is supposed to discover must remain provisional.
5. Begin point-in-time capture with the first product build; do not wait for quantitative validation. `docs/blueprint/funda-blueprint-final-consolidated-review.md:291-302`

### Later and conditional

- Run the GBrain three-arm benchmark only after the MVP produces real longitudinal workloads.
- Evaluate OpenBB, FinanceHarness, and Vibe-Trading only when a concrete capability need exists.
- Evaluate debate only against a single-senior-reviewer baseline.
- Start quantitative validation only after sufficient honest point-in-time history exists.
- Keep execution in a separate trust domain and outside the definition of product success.

## Final judgment

Equity-OS has not lost its blueprint. It has lost sequencing discipline.

The architecture, first workflow, source controls, deterministic-compute boundary, human review model, and external-method evaluation strategy are fundamentally sound. The current delivery process is not: it has made exhaustive governance completeness the prerequisite for the experiment that was supposed to determine which contracts are necessary.

The corrective principle is therefore:

> **Preserve the product architecture and authority history; supersede the governance platform; finish Phase 0A evidence; derive the build contracts from the real four-quarter workflow; and make every later repository or method earn adoption against a simpler baseline.**

