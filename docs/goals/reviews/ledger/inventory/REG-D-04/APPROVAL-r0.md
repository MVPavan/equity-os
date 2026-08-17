# Inventory review — REG-D-04 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-D-04` |
| `review_type` | `APPROVAL` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `c625bbd5-cbd8-40b2-823c-20422d619435` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-16T13:58:44Z` |

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

Fresh structural validation at these exact bytes → exit `0`
(`python3 scripts/equity_os_blueprint/validate_ledger_structural.py --repo-root .`).

## Applicable review slots for this component

This component is a `register_row`, so it has exactly **two** applicable review
slots. `scope_derivation.semantic_review` is contractually `null` (goal
L208-211, mechanized at `validate_ledger_structural.py:1532`), and
`validate_ledger_preimplementation.py:199-204` builds `checks` as `APPROVAL` +
`EVIDENCE` and appends `SCOPE` only when `row["kind"] != "register_row"`. I
confirmed on this row's live bytes that `scope_derivation` is
`{"authority_effect": null, "derived_program_disposition": "CONDITIONAL_UNACTIVATED",
"related_register_ids": [], "rule": "REGISTER_STATUS", "semantic_review": null}`.
No `SCOPE` artifact exists or may exist for this component.

## Row facts, re-read this round

| Field | Value as read |
|---|---|
| `kind` | `register_row` |
| `register_id` / `source_anchor` | `D-04` / `D-04` |
| `source_path` L100-100 | `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` |
| `source_status` / `activation_source_status` | `Deferred` / `Deferred` |
| `program_disposition` / `delivery_status` | `CONDITIONAL_UNACTIVATED` / `SPEC_DRAFT` |
| `priority` / `blueprint_phase` | `High` / `2` |
| `primary_spec` | `S20` — docs/specs/equity-os-s20-memory-benchmark-gbrain.md |
| `dependencies` / `gate_refs` | `[]` / `[]` |
| `disposition_refs` / `human_review_id` | `["R-1", "6.4"]` / `"HR-0004"` |
| `text_digest` (recomputed this round) | `f7eb7eadf35a05fa44a2528cde96094b88415335663240992362cedc3f7bbda8` |

## Reviewed inventory, exactly as read

`review_inventory_projection(row, "APPROVAL")` — canonical JSON:

```json
{"approval_records":[],"human_review_id":["HR-0004"],"required_approvals":[{"actor":null,"approval_id":"APR-REG-D-04-01","approval_type":"DELEGATED_ARTIFACT_APPROVAL","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Delegated fresh Sol xhigh specification reviewer","scope":"D-04 under S20: Verify GBrain repository and dependency posture","status":"UNRESOLVED","timestamp":null},{"actor":null,"approval_id":"APR-REG-D-04-02","approval_type":"PRODUCT_OWNER_DECISION","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Product owner authorized to activate deferred blueprint scope","scope":"D-04 under S20: Verify GBrain repository and dependency posture","status":"UNRESOLVED","timestamp":null},{"actor":null,"approval_id":"APR-REG-D-04-03","approval_type":"LEGAL_REVIEW","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Competent dependency-license reviewer","scope":"D-04 under S20: Verify GBrain repository and dependency posture","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record**:

- `reviewed_input_sha256` (pre-record): `a090df009c8a03bb1ad79dc317afd2826422bf7de12fb97e69bc443ce6f223d2`
- `reviewed_inventory_sha256` (pre-record): `baa995bcc75d9cc610da4c03dc0b7cc5aad4961677ffa2ae5654754bcc77faa7`

Both were recomputed this round with `canonical_sha256` /
`review_input_projection` / `review_inventory_projection` extracted from the
checked-in structural validator by `ast` (never imported), per design r2 §3.3.

## Scope of this decision

Completeness of `required_approvals` only: does this row's source clause,
dependencies, gates, transitions, or fail-closed boundaries (goal L535-537)
demand an authority whose sign-off is not enumerated? Whether any approval has
been obtained is out of scope. Goal L188 makes an approval inventory a
completed, evidenced determination, so each enumerated obligation is affirmed
and each absent one is affirmed as absent, not skipped.

## The source clause, re-read this round

Register L100, table `## D. Phase 2 — Memory evaluation` (header L95-96), the single table row for `D-04`:

> | D-04 | High | Verify GBrain repository and dependency posture | Repository, license, maintainers, activity, tests, security, export path, and pinned version recorded | — | Deferred |

Column 4 ("Required evidence / acceptance") is the acceptance text:

> Repository, license, maintainers, activity, tests, security, export path, and pinned version recorded

`text_digest` and `EV-REG-D-04-SOURCE.content_sha256` were both recomputed
this round over the normalized L100-100 span → `f7eb7eadf35a05fa44a2528cde96094b88415335663240992362cedc3f7bbda8`,
matching the stored values. The register's ID, priority, title, acceptance text,
dependencies, and status cells were each byte-compared against the corresponding
ledger fields; all six match.

## Reasoning

**Program-wide facts recomputed this round** (not transcribed from any peer
artifact), used in the sweeps below:

- The required-authority map is closed at 12 approval types with pinned literal
  authorities (`REQUIRED_AUTHORITY_VOCABULARY`,
  `validate_ledger_structural.py:2586-2612`; goal L555-576), and every
  `required_approvals` entry outside it is rejected (`:2629-2631`).
  `DELEGATED_ARTIFACT_APPROVAL` is exempt from the literal pin but must use one
  identical nonempty authority string everywhere (`:2623-2628`, `:2633`).
- `GOAL_OR_PROCESS_AUTHORIZATION`, `PROVIDER_AUTHORIZATION`,
  `PRODUCTION_APPROVAL`, `EXTERNAL_SERVICE_APPROVAL`, `SECURITY_EXCEPTION`,
  `CREDENTIAL_ACCESS_APPROVAL`, `PURCHASE_AUTHORIZATION` and
  `EXTERNAL_COORDINATION_APPROVAL` appear in the goal's approval-type list
  (L539-549) but **not** in the required-authority table, and goal L583-584
  states such a type "has no obligation in this inventory". None is
  representable in `required_approvals` today.
- Where each remaining authority actually lives, recomputed over all 213 rows:
  `MEMORY_PROMOTION`/`Responsible analyst` → `REG-C-10` only;
  `DOMAIN_EXPERT_ACCEPTANCE` → `REG-B-07` (`Calculation-domain authority`),
  `REG-B-12` (`Vocabulary authority`), `REG-B-03` + `PG-05-05`
  (`Data-domain authority`), `REG-C-17` (`Entity-data authority`), `REG-A-10`
  (`Equity-research domain expert`); `DATA_RIGHTS_APPROVAL` → `REG-A-05`,
  `REG-C-13`, `REG-C-14`, `REG-E-04`, `REG-E-06`; `REGULATORY_REVIEW` and
  `DISTRIBUTION_APPROVAL` → `REG-E-08` only;
  `EXECUTION_TRUST_DOMAIN_APPROVAL` → `REG-E-09` only;
  `NAMED_OWNER_COMMITMENT` → `REG-A-08`, `REG-E-01`, `REG-E-04`.
- The activate-deferred obligation is exactly disposition-keyed: across all 60
  `register_row` components, a `PRODUCT_OWNER_DECISION` with authority
  `Product owner authorized to activate deferred blueprint scope` is present on
  every `CONDITIONAL_UNACTIVATED` row and absent from every other row — zero
  exceptions.
- `approval_records` and `security_exception_ids` are empty on all 213 rows, so
  the remaining projection fields carry no unenumerated obligation.

**The three enumerated obligations, affirmed.** `APR-REG-D-04-01` delegated
artifact approval over `S20`; `APR-REG-D-04-02` activate-deferred
`PRODUCT_OWNER_DECISION` (required — the row is `CONDITIONAL_UNACTIVATED`,
`Deferred`/`Deferred`); `APR-REG-D-04-03` `LEGAL_REVIEW` with authority
`Competent dependency-license reviewer`.

**The `LEGAL_REVIEW` authority literal is the right one of three.** The closed
table allows three strings under `LEGAL_REVIEW`. Recomputed ledger-wide this
round: `Competent dependency-license reviewer` is used on exactly `REG-D-04`,
`REG-E-06` and `REG-E-07` — the three rows that examine a third-party dependency;
`Competent legal reviewer` only on `REG-E-08` (paid/public research);
`Competent trademark or legal reviewer` only on `REG-A-09` (project name). GBrain
is a dependency, so the dependency-licence variant is correct and the
one-string-per-authority invariant is preserved.

**`SECURITY_EXCEPTION` — the trap this clause sets, checked twice.** The clause
requires "security" to be recorded. `SECURITY_EXCEPTION` is in the goal's
approval-type list (L548) but is **absent from the closed required-authority
table**, so goal L583-584 gives it no obligation in this inventory and
`:2629-2631` would reject it outright. Independently, on the merits: an exception
authorizes a deviation from a control, and this clause proposes no deviation — it
asks for a posture to be written down. Corroborating, `security_exception_ids` is
`[]` on this row and on all 213 rows.

**`PURCHASE_AUTHORIZATION` and `EXTERNAL_SERVICE_APPROVAL` checked.** Verifying a
dependency's posture could precede acquiring it, and both types exist in the
goal's approval-type list (L548-549). Neither is in the required-authority table,
so neither carries an obligation (goal L583-584). On the merits the clause also
commits nothing: GBrain is open-source, and this row records facts rather than
procuring anything. If adoption follows, the decision is `D-05`'s.

**`DOMAIN_EXPERT_ACCEPTANCE` checked.** "maintainers, activity, tests" are
software-supply-chain observations, not data, calculation, entity, vocabulary or
equity-research determinations. All five domain authorities are located elsewhere
(`REG-B-03`/`PG-05-05`, `REG-B-07`, `REG-C-17`, `REG-B-12`, `REG-A-10`).

**Sweep of the remaining closed vocabulary.**

| Type | Why it is not demanded by this clause |
|---|---|
| `ANALYST_ACCEPTANCE`, `MEMORY_PROMOTION` | No analyst output and no memory item is promoted (`REG-C-10` holds that authority). |
| `BUDGET_APPROVAL`, `CAPACITY_COMMITMENT`, `NAMED_OWNER_COMMITMENT` | Due diligence commits no spend or capacity and appoints no owner; the predicate `AP-D04-GBRAIN-DUE-DILIGENCE-NEED` tests one boolean, `gbrain_due_diligence_required`, and names no resource metric. |
| `DATA_RIGHTS_APPROVAL` | The "export path" concerns Funda's own data leaving the dependency, not acquiring third-party data; `Data-rights authority` sits on `REG-A-05`, `C-13`, `C-14`, `E-04`, `E-06`. |
| `REGULATORY_REVIEW`, `DISTRIBUTION_APPROVAL` | Nothing regulated and nothing distributed; both live on `REG-E-08` alone. |
| `EXECUTION_TRUST_DOMAIN_APPROVAL` | No execution boundary (`REG-E-09` alone). |

**Gate and dependency sweep — vacuous here, and that is the point.** This is the
only component of the eleven with **both** `gate_refs: []` and `dependencies: []`
(register column 5 is "—"). Goal L535-537 derives `required_approvals` from the
acceptance text, dependencies, gates, transitions, and fail-closed boundaries;
two of those five sources are empty by construction on this row, so the clause
text is the whole input, and it yields exactly the licence authority already
enumerated.

**Remaining projection fields.** `approval_records: []`; `human_review_id`
normalizes to `["HR-0004"]` (a link, not an obligation);
`security_exception_ids: []`.

**Residuals.** None.

---

**verdict: CLEAN**

`required_approvals` for `REG-D-04` is complete at the input bytes pinned above.
This review grants no authority (goal L624-626) and authorizes no delivery,
gate, or transition.
