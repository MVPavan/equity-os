# A-12 Operating Capacity Contract

**Record version:** 1.0.0-final
**Status:** ACCEPTED — operating capacity envelope approved by the product owner; every value is an approved CEILING or a defined MEASUREMENT_RULE, none is unlimited
**Prepared at:** 2026-08-21
**Author:** bounded implementer (recording agent, not the decision maker)

## Purpose and boundary

This is the `OperatingCapacityContract` required by decision-register v2 A-12. It
records weekly builder and analyst capacity, the pilot target, the monthly
model/infrastructure ceiling, the maintenance allowance, and expected company
coverage. Each value carries its unit, scope, evidence version, decision state,
authority, and the record digest below. It procures and selects no provider,
model, or infrastructure product.

## Basis (recorded honestly)

These values are **FORWARD PRODUCT-OWNER ESTIMATES** for a personal project. Q0
was executed via the multi-model method (`bd memory
methodology-q0-thesis-multimodel-2026-08-21`), **not** a timed manual pass, so
they are **NOT derived from observed manual Q0 minutes**. They are honest forward
estimates of available personal time and coverage ambition, traceable to
explicit product-owner approval and the single-principal personnel fact. Every
value is an approved `CEILING` or a defined `MEASUREMENT_RULE` (never
"unlimited").

## Capacity envelope

| Field | Decision state | Value | Unit | Scope | Evidence version | Authority | Approval |
|---|---|---|---|---|---|---|---|
| weekly builder capacity | `CEILING` | 5 | hours/week | single-principal builder/dev time | forward-estimate-2026-08-21 | product owner | APPROVED |
| weekly analyst capacity | `CEILING` | 2 | hours/week | single-principal analyst/review time | forward-estimate-2026-08-21 | product owner | APPROVED |
| pilot target date | `MEASUREMENT_RULE` | Infosys Q1 output within the current build cycle | milestone | pilot delivery target | forward-estimate-2026-08-21 | product owner | APPROVED |
| monthly model/infra ceiling | `CEILING` | 2000 | INR/month | monthly provider/model/infrastructure spend | forward-estimate-2026-08-21 | product owner | APPROVED |
| maintenance allowance | `CEILING` | 1 | hours/week | single-principal maintenance time | forward-estimate-2026-08-21 | product owner | APPROVED |
| expected company coverage | `MEASUREMENT_RULE` | start 1 (Infosys) scaling toward 5-10 | companies | program coverage ambition | forward-estimate-2026-08-21 | product owner | APPROVED |

The two `MEASUREMENT_RULE` rows (pilot target, expected coverage) are ambition
milestones to be observed and recorded against, not hard numeric ceilings; they
are never "unlimited" spending or throughput.

## Approval

- **Decider:** PavanMV (mvpavan42@gmail.com), product owner.
- **Decision date:** 2026-08-21.
- **Verbatim instruction (2026-08-21):** "Accept all the defaults."
- **Authority role:** product owner; approval state APPROVED.
- **Scope of this approval:** the six capacity values above, traceable to
  product-owner approval and the single-principal personnel fact. No provider,
  model, or infrastructure product is procured or selected.

## Record digest convention and payload

Non-self-referential SHA-256 per the A-01 convention (UTF-8 canonical JSON,
recursively sorted keys, preserved array order, no whitespace/BOM, every
`record_digest` field excluded). No source content is digested.

```json
{"approval":{"authority_role":"product_owner","state":"APPROVED"},"artifact_id":"A-12","basis":"FORWARD PRODUCT-OWNER ESTIMATE for a personal project. Q0 was executed via the multi-model method (bd memory methodology-q0-thesis-multimodel-2026-08-21), not a timed manual pass; capacity and coverage values are honest forward estimates of available personal time and ambition, traceable to product-owner approval and the single-principal personnel fact, not to observed manual Q0 minutes.","capacity":{"expected_company_coverage":{"authority":"product_owner","decision_state":"MEASUREMENT_RULE","evidence_version":"forward-estimate-2026-08-21","scope":"program coverage ambition","unit":"companies","value":"start 1 (Infosys) scaling toward 5-10"},"maintenance_allowance":{"authority":"product_owner","decision_state":"CEILING","evidence_version":"forward-estimate-2026-08-21","scope":"single-principal maintenance time","unit":"hours/week","value":1},"monthly_model_infra_ceiling":{"authority":"product_owner","decision_state":"CEILING","evidence_version":"forward-estimate-2026-08-21","scope":"monthly provider/model/infrastructure spend","unit":"INR/month","value":2000},"pilot_target_date":{"authority":"product_owner","decision_state":"MEASUREMENT_RULE","evidence_version":"forward-estimate-2026-08-21","scope":"pilot delivery target","unit":"milestone","value":"Infosys Q1 output within the current build cycle"},"weekly_analyst_capacity":{"authority":"product_owner","decision_state":"CEILING","evidence_version":"forward-estimate-2026-08-21","scope":"single-principal analyst/review time","unit":"hours/week","value":2},"weekly_builder_capacity":{"authority":"product_owner","decision_state":"CEILING","evidence_version":"forward-estimate-2026-08-21","scope":"single-principal builder/dev time","unit":"hours/week","value":5}},"contract_kind":"OPERATING_CAPACITY_CONTRACT","decider":"PavanMV (mvpavan42@gmail.com), product owner","decision_date":"2026-08-21","document_version":"1.0.0-final","prepared_at":"2026-08-21","scope":"Operating capacity envelope for the private Phase 0A build: weekly builder/analyst capacity, pilot target, monthly infra ceiling, maintenance allowance, and expected company coverage. No provider, model, or infrastructure product is procured or selected here.","verbatim_instruction":"Accept all the defaults. (2026-08-21)"}
```

**Record digest:** `sha256:a762b685c3225fee143adb400f1e280d20b669b0ebdb7283aa1f7efb7619fbe3`

## Authorities

- `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` — A-12 operating-capacity clause.
- `docs/plans/2026-08-19-phase-0a-evidence-program.md` — Task 8 required capacity fields.
- Product owner: capacity envelope APPROVED 2026-08-21 by PavanMV (see approval above).
