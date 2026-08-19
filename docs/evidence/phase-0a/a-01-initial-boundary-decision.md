# A-01 Initial Boundary Decision

**Record version:** 1.0.0
**Status:** RECORDED — product-owner decision captured; not a legal-sufficiency finding
**Recorded at:** 2026-08-19T20:28:25Z
**Author:** bounded implementer (recording agent, not the decision maker)

## Binding approval event

- **Event reference:** `eqos-3ps` notes, `BINDING USER DECISION 2026-08-19`, obtained with `bd show eqos-3ps --json`.
- **Timestamp:** `2026-08-19` only. The recorded event has date precision; no time-of-day is present, so none is inferred.
- **Principal:** current user/product-owner principal provided by the handoff. No identifiable personal name is recorded or inferred.
- **Decision text (verbatim scope):** `A-01 private/internal-only with public, paid, personalized, and execution-linked modes prohibited`.
- **Presented scope:** the approved five-flat-stage Phase 0A evidence program; S1 owns A-01/A-02. The same event selects the Infosys issuer Q1–Q4 FY25 mapping to program Q0–Q3 and expressly preserves separate analyst-suitability and per-source/use-rights decisions as fail-closed.

## Initial operating boundary

| Mode | Initial decision | Meaning in this record |
|---|---|---|
| Private/internal | **ALLOWED** | Sole initially allowed research operating mode. |
| Public distribution | **PROHIBITED** | No public outputs or distribution are authorized. |
| Paid distribution | **PROHIBITED** | No paid, commercial, or subscription distribution is authorized. |
| Personalized output | **PROHIBITED** | No recipient-specific research output is authorized. |
| Execution-linked use | **PROHIBITED** | No trading, order-routing, execution, or execution-linked workflow is authorized. |
| Intended future boundary | **UNDECIDED** | Any change to the initial boundary requires a separate competent decision and applicable legal/rights review. |

## Limits and downstream gates

This is the initial product-owner boundary required by decision-register v2 A-01. It is **not legal advice, a legal review, a rights decision, or a claim of legal sufficiency**. It does not authorize source acquisition, automation, caching, retention, derived outputs, redistribution, product code, provider selection, Phase 0.5 execution, or any external/execution-linked mode.

Decision-register v2 A-01 remains an Open register item. The Phase 0A exit scorecard also requires source rights scoped to this boundary; this record does not satisfy that separate gate.

## Record digest convention and payload

Every created record uses `sha256:<lowercase-hex>` of the UTF-8 canonical JSON payload: recursively sort object keys, preserve array order, use no whitespace or byte-order mark, and exclude every `record_digest` field from the digest input. The digest is therefore non-self-referential. No source-content bytes are included.

```json
{"artifact_id":"A-01","authority_event_ref":"eqos-3ps notes:BINDING USER DECISION 2026-08-19","boundary":{"execution_linked":"PROHIBITED","paid":"PROHIBITED","personalized":"PROHIBITED","private_internal":"ALLOWED","public":"PROHIBITED"},"decision_date":"2026-08-19","decider":"current user/product-owner principal provided by the handoff (no identity recorded)","document_version":"1.0.0","recorded_at":"2026-08-19T20:28:25Z","scope":"Initial private/internal research operating boundary; does not authorize public, paid, personalized, execution-linked, rights, or legal activity."}
```

**Record digest:** `sha256:e5e21a8a3fed481921bee4eeb879a8908896de69b01b716a5502d540470ffe8b`

## Authorities

- `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` — A-01 and Phase 0A gate clauses.
- `eqos-3ps` approval-history note identified above — product-owner decision authority.
