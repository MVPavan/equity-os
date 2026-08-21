# A-07 Workflow Budget Contract

**Record version:** 1.0.0-final
**Status:** ACCEPTED — per-report workflow budget ceilings approved by the product owner; every dimension is an approved CEILING, none is unlimited
**Prepared at:** 2026-08-21
**Author:** bounded implementer (recording agent, not the decision maker)

## Purpose and boundary

This is the `WorkflowBudgetContract` required by decision-register v2 A-07. It
records, for each per-report workflow dimension, an approved `CEILING` with its
unit, scope, evidence version, decision state, authority, and the record digest
below. It selects no provider, model, or infrastructure product.

## Basis (recorded honestly)

These ceilings are **FORWARD PRODUCT-OWNER ESTIMATES** for a personal project.
Q0 was executed via the multi-model method (`bd memory
methodology-q0-thesis-multimodel-2026-08-21`), **not** a timed manual pass, so
these values are **NOT derived from observed manual Q0 minutes**. They are honest
forward estimates constrained as approved ceilings. The governance rule holds:
every dimension is an approved `CEILING` (never "unlimited").

## Per-report ceilings

| Dimension | Decision state | Value | Unit | Scope | Evidence version | Authority | Approval |
|---|---|---|---|---|---|---|---|
| model cost | `CEILING` | 50 | INR | per report | forward-estimate-2026-08-21 | product owner | APPROVED |
| tool calls | `CEILING` | 60 | count | per report | forward-estimate-2026-08-21 | product owner | APPROVED |
| latency | `CEILING` | 15 | minutes | per report end-to-end | forward-estimate-2026-08-21 | product owner | APPROVED |
| document volume | `CEILING` | 10 | documents | per report | forward-estimate-2026-08-21 | product owner | APPROVED |
| retries | `CEILING` | 3 | count | per report | forward-estimate-2026-08-21 | product owner | APPROVED |
| analyst minutes | `CEILING` | 20 | minutes | per report | forward-estimate-2026-08-21 | product owner | APPROVED |

## Approval

- **Decider:** PavanMV (mvpavan42@gmail.com), product owner.
- **Decision date:** 2026-08-21.
- **Verbatim instruction (2026-08-21):** "Accept all the defaults."
- **Authority role:** product owner; approval state APPROVED.
- **Scope of this approval:** the six per-report ceilings above. No provider,
  model, or infrastructure product is selected.

## Record digest convention and payload

Non-self-referential SHA-256 per the A-01 convention (UTF-8 canonical JSON,
recursively sorted keys, preserved array order, no whitespace/BOM, every
`record_digest` field excluded). No source content is digested.

```json
{"approval":{"authority_role":"product_owner","state":"APPROVED"},"artifact_id":"A-07","basis":"FORWARD PRODUCT-OWNER ESTIMATE for a personal project. Q0 was executed via the multi-model method (bd memory methodology-q0-thesis-multimodel-2026-08-21), not a timed manual pass; these ceilings are NOT derived from observed manual Q0 minutes and are honest forward estimates constrained as approved ceilings, never unlimited.","ceilings":{"analyst_minutes":{"authority":"product_owner","decision_state":"CEILING","evidence_version":"forward-estimate-2026-08-21","scope":"per report","unit":"minutes","value":20},"document_volume":{"authority":"product_owner","decision_state":"CEILING","evidence_version":"forward-estimate-2026-08-21","scope":"per report","unit":"documents","value":10},"latency":{"authority":"product_owner","decision_state":"CEILING","evidence_version":"forward-estimate-2026-08-21","scope":"per report end-to-end","unit":"minutes","value":15},"model_cost":{"authority":"product_owner","decision_state":"CEILING","evidence_version":"forward-estimate-2026-08-21","scope":"per report","unit":"INR","value":50},"retries":{"authority":"product_owner","decision_state":"CEILING","evidence_version":"forward-estimate-2026-08-21","scope":"per report","unit":"count","value":3},"tool_calls":{"authority":"product_owner","decision_state":"CEILING","evidence_version":"forward-estimate-2026-08-21","scope":"per report","unit":"count","value":60}},"contract_kind":"WORKFLOW_BUDGET_CONTRACT","decider":"PavanMV (mvpavan42@gmail.com), product owner","decision_date":"2026-08-21","document_version":"1.0.0-final","prepared_at":"2026-08-21","scope":"Per-report workflow budget ceilings for the private Phase 0A operating envelope. Every dimension is an approved CEILING; none is unlimited. No provider, model, or infrastructure product is selected here.","verbatim_instruction":"Accept all the defaults. (2026-08-21)"}
```

**Record digest:** `sha256:0c2864ebeec61e7bc43c20d2b83c3bcaaeb53dfc7ccbd222be43afb5fa330c95`

## Authorities

- `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` — A-07 workflow-budget clause.
- `docs/plans/2026-08-19-phase-0a-evidence-program.md` — Task 8 required dimensions and decision-state rule.
- Product owner: ceilings APPROVED 2026-08-21 by PavanMV (see approval above).
