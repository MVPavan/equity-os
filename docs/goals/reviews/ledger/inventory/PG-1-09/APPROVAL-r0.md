# Inventory review — PG-1-09 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `PG-1-09` |
| `review_type` | `APPROVAL` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `c43733f6-8986-4487-8aa6-2f7b5b723107` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-16T03:52:19Z` |

Role binding: `CONTEXT.md` "Agent roles (harness-wide)" L137-139 and L147 bind
`REVIEWER` to Claude Opus 5 at high effort, independent of any `IMPLEMENTER`
that produced the reviewed content.

## Input hashes read for this review

| Input | SHA-256 |
|---|---|
| `docs/goals/equity-os-blueprint-completion.md` (active goal) | `f15f7ab5a4e425dec3877ab7f1f7594687979060e4dbcd49390a8a8d5fedb85f` |
| `docs/goals/equity-os-blueprint-component-ledger.jsonl` (canonical ledger) | `de236d7e8dcf02e307ec58797f5722ae2f85d1d8cdba57d4ecc07df5383c9c97` |
| `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` (pinned v2 register) | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| `docs/blueprint/funda-third-order-review-disposition-report.md` (pinned disposition report) | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| `scripts/equity_os_blueprint/validate_ledger_structural.py` (structural validator) | `731d0d8b208b577967c92e3992e7ec1a4333cdecbf89f6951c32d2ec469436f9` |
| `scripts/equity_os_blueprint/validate_ledger_preimplementation.py` | `f7a225a1f99cb85c92cde3094505a92a746552280eb45dae0253a71ab9048013` |
| `scripts/equity_os_blueprint/extract_goal_validators.py` | `5d20d796666d1154fb3c84ba4fa7407ee82819510a5ac06254f7f4a3126c6f2a` |
| `docs/goals/equity-os-blueprint-human-review-needed.md` | `094fcdfab74a3f4c6fdb82b1520fc4d13b636ac0e9ed10194e5d607aed2ce9af` |
| `CONTEXT.md` (role binding) | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r2.md` (artifact format) | `adf908ac8cec01a55a53438624c6a8913f673f5b7cecd3e955fc4919f73803fb` |

Fresh structural validation at these exact bytes:
`python3 scripts/equity_os_blueprint/validate_ledger_structural.py --repo-root .`
→ exit `0` (run at review time).

## Reviewed inventory, exactly as read

`review_inventory_projection(row, "APPROVAL")` — canonical JSON:

```json
{"approval_records":[],"human_review_id":["HR-0004"],"required_approvals":[{"actor":null,"approval_id":"APR-PG-1-09-01","approval_type":"CAPACITY_COMMITMENT","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Capacity owner","scope":"PG-1-09 capacity commitment","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 —
appending review evidence mutates `evidence_refs` and therefore the input
projection):

- `reviewed_input_sha256` (pre-record): `33a43a14079d9af52ae63a68080e6cbedf638941191dafd3708b2619be2507c8`
- `reviewed_inventory_sha256` (pre-record): `e0618eb40187bf6704432ceb4c12d60199fd398ee66943221fbe793bffcc7b02`

## Scope of this decision

Goal L188: `required_approvals` "exhaustively declares the component's typed
approval obligations", and "Empty `required_approvals` means a completed,
evidenced determination that no approval is required, not an unknown
inventory." Goal L535-537 fixes the derivation inputs: "Every component derives
`required_approvals` from its exact source acceptance text, dependencies, phase
gates, transitions, fail-closed boundaries, and any approved security
exception." This review decides completeness of that list — whether the source
clause demands an authority whose sign-off is not enumerated — not whether any
approval has been obtained.

## The source clause, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md`
L158, the ninth bullet under `### Phase 1 may exit only when`
(L148), inside `## F. Phase-gate scorecard` (L122):

> - peak results-season capacity is accepted for the selected universe;

- `source_hash` recomputed over the whole register file → `26d51b31…`, matches
  the stored value.
- `text_digest` recomputed over the normalized L158 span →
  `c4248b18af2a75ebef45d3ea65a2ed079caa78ab89eed64d90004a4c7e649064`, equal to
  the stored `text_digest` and to `EV-PG-1-09-SOURCE.content_sha256`.
- `required_acceptance_text` equals that bullet with the list marker and the
  terminal punctuation stripped, byte for byte.

## Reasoning

**The one enumerated requirement is correct.** `APR-PG-1-09-01`,
`CAPACITY_COMMITMENT`, `required_authority` "Capacity owner", scope "PG-1-09
capacity commitment", `status: UNRESOLVED` with null actor, null timestamp, no
matched record and no evidence — the state goal L588-591 prescribes for a
requirement that has not yet been decided. The authority literal is the single
allowed value for this type: goal L566 and
`validate_ledger_structural.py:2570-2613` admit exactly `Capacity owner`, and
`:2629-2632` rejects anything outside the map.

**Why this type and not another.** The clause's verb is "**is accepted**", and
its object is *capacity*. Goal L535-537 derives `required_approvals` from "exact
source acceptance text, dependencies, phase gates, transitions, fail-closed
boundaries"; the text here names an acceptance act over a capacity claim, which
is `CAPACITY_COMMITMENT` and nothing else in the closed vocabulary. This is one
of only six phase-gate clauses carrying any typed approval, and it fits the
measured pattern exactly: the acceptance act is inside the gate's own object,
not upstream of it (contrast `PG-1-08` in this batch, whose "agreed threshold"
is a yardstick fixed beforehand).

**Corroboration from the register cone.** Both related register rows carry the
same type: `REG-C-01` and `REG-C-18` each carry `CAPACITY_COMMITMENT` /
"Capacity owner", each paired with its own `CAPACITY`-typed evidence item. So
the authority this gate names is the authority its own scope cone already
recognises — and, per goal L613-615, the gate's obligation is recorded
separately rather than inferred from theirs, which is what a distinct
`approval_id` and a distinct scope string accomplish.

**Is the list complete — is a *second* authority demanded?** Swept against the
closed vocabulary:

| Type | Why it is not additionally demanded |
|---|---|
| `BUDGET_APPROVAL` | The clause accepts *capacity*, not spend. Peak-season capacity and standing budget are separated in the source itself: `A-12` carries both `BUDGET_APPROVAL` and `CAPACITY_COMMITMENT` and is gated by `PG-0A-07`, while `C-01`/`C-18` — this clause's cone — carry capacity only. Adding a budget authority here would import `A-12`'s obligation across a gate boundary. |
| `NAMED_OWNER_COMMITMENT` | No owner is appointed. Its three instances are the golden-set, model-grade-compute, and event-monitoring owners. "Capacity owner" is already the authority of the `CAPACITY_COMMITMENT` type, not a separate named-owner obligation. |
| `ANALYST_ACCEPTANCE` | The analyst is the *subject* being measured (reviews per analyst), not the accepting authority. No thesis, narrative, or output is accepted. |
| `PRODUCT_OWNER_DECISION` | Nothing deferred is activated; `C-01` and `C-18` are both `Open`. Contrast `PG-2-05` in this batch, where the accepted object is operational burden under a dormant Phase 2 scope and the authority is the product owner. |
| `DOMAIN_EXPERT_ACCEPTANCE` | Throughput measurement is not a calculation, data, entity, or vocabulary judgment. |
| `MEMORY_PROMOTION` | Nothing is promoted to canonical memory. |
| `DATA_RIGHTS_APPROVAL`, `LEGAL_REVIEW`, `REGULATORY_REVIEW` | No acquisition, licence, or regulated activity. |
| `DISTRIBUTION_APPROVAL`, `EXECUTION_TRUST_DOMAIN_APPROVAL` | Nothing distributed; no execution boundary. |

**No `DELEGATED_ARTIFACT_APPROVAL`, and that is structural.** All 123
delegated-artifact requirements sit on `register_row` (60), `disposition_item`
(32), `first_release_deferral` (13), `sequence_clause` (10), and `scale_trigger`
(8) rows. **Zero sit on a `phase_gate_clause`** — 0 of 35. That type approves an
artifact (goal L577-582; L957-976), and a §F gate bullet owns none:
`primary_spec` is `null` on every phase-gate row. The artifact approvals sit on `REG-C-01` and `REG-C-18` under S18.

**The near-miss, checked explicitly.** `C-18`'s acceptance says capacity is
"measured and accepted **or mitigated**". One could argue the mitigation branch
implies a second decision authority — a product owner accepting a mitigated
posture. I rejected it: the §F bullet quotes only the acceptance branch ("is
accepted"), and the contract inventories the exact occurrence, not the register
row's fuller text. `C-18`'s own row is where the mitigation branch lives, and
`REG-C-18` carries no product-owner requirement either. Inventing one here would
be inference from a neighbouring text into this clause's obligations.

**Remaining projection fields.** `approval_records: []` — consistent with
one `UNRESOLVED` requirement and no decision yet (goal L188: one record satisfies at most one requirement). `human_review_id: "HR-0004"` — the reconciliation entry recorded over `HR-0004`'s 144-ID scope, which 134 canonical rows link; goal L189 permits exactly `null`, one `HR-####` string, or a sorted array of at least two. `open_findings` is `[]`
and `blocked_scope` is `[]`, so no finding-driven link is expected.
`security_exception_ids: []` — the clause crosses no trust boundary, and no
security exception exists anywhere in the ledger (0 of 213 rows).

**Residuals.** None.

---

**verdict: CLEAN**

This review grants no authority (goal L624-626) and authorizes no delivery,
gate, or transition.
