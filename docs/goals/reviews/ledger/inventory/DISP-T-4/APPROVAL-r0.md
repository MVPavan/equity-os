# Inventory review — DISP-T-4 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-T-4` |
| `review_type` | `APPROVAL` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `4e983789-a352-4ab6-9d42-4e7bdc2941f6` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-15T13:22:11Z` |

Role binding: `CONTEXT.md` "Agent roles (harness-wide)" L137-139 and L147 bind
`REVIEWER` to Claude Opus 5 at high effort, in an agent and context independent
of any `IMPLEMENTER` that produced the reviewed content. The digest above is the
`CONTEXT.md` bytes at review time and is an immutable historical capture.

## Input hashes read for this review

| Input | SHA-256 |
|---|---|
| `docs/goals/equity-os-blueprint-completion.md` (active goal contract) | `f15f7ab5a4e425dec3877ab7f1f7594687979060e4dbcd49390a8a8d5fedb85f` |
| `docs/goals/equity-os-blueprint-component-ledger.jsonl` (canonical ledger) | `de236d7e8dcf02e307ec58797f5722ae2f85d1d8cdba57d4ecc07df5383c9c97` |
| `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` (pinned v2 decision register) | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| `docs/blueprint/funda-third-order-review-disposition-report.md` (pinned third-order disposition report) | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| `scripts/equity_os_blueprint/validate_ledger_structural.py` (structural validator) | `731d0d8b208b577967c92e3992e7ec1a4333cdecbf89f6951c32d2ec469436f9` |
| `scripts/equity_os_blueprint/validate_ledger_preimplementation.py` (preimplementation validator) | `f7a225a1f99cb85c92cde3094505a92a746552280eb45dae0253a71ab9048013` |
| `scripts/equity_os_blueprint/extract_goal_validators.py` (extractor) | `5d20d796666d1154fb3c84ba4fa7407ee82819510a5ac06254f7f4a3126c6f2a` |
| `docs/goals/equity-os-blueprint-human-review-needed.md` (canonical human-review artifact) | `094fcdfab74a3f4c6fdb82b1520fc4d13b636ac0e9ed10194e5d607aed2ce9af` |
| `CONTEXT.md` (role binding) | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r2.md` (artifact format, design r2 §2.2) | `adf908ac8cec01a55a53438624c6a8913f673f5b7cecd3e955fc4919f73803fb` |

Fresh structural validation at these exact bytes:
`python3 scripts/equity_os_blueprint/validate_ledger_structural.py --repo-root .`
→ exit `0` (run at review time). Every `evidence_refs` entry on this row was
additionally re-hashed by hand against its current target bytes this round and
matched.

## Reviewed inventory, exactly as read

`review_inventory_projection(row, "APPROVAL")` — canonical JSON:

```json
{"approval_records":[],"human_review_id":["HR-0004"],"required_approvals":[{"actor":null,"approval_id":"APR-DISP-T-4-01","approval_type":"DELEGATED_ARTIFACT_APPROVAL","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Delegated fresh Sol xhigh specification reviewer","scope":"T-4 under S01","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `63e98eacc5dec431c3ea59db92441b78603612ccbffb63a75a6ceb94318d4aa3`
- `reviewed_inventory_sha256` (pre-record): `7c6903166a9a0f5a762bd88e61b06d5ee85730365793d7f38fc3d42c49808d8d`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` lines 299-303, anchor `T-4`, title "Regulatory verification before boundary statement":

> ### T-4 — Regulatory verification before boundary statement
>
> **Disposition: Partially accept.**
>
> A-01 can define the intended product boundary without completing legal analysis. It should avoid claiming that the chosen boundary is legally sufficient. Current regulatory verification becomes mandatory before external, paid, personalized, or execution-connected use, not necessarily before documenting the initial private-use intent.

- `source_hash` recomputed over the whole file → `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`, matching the row.
- `text_digest` recomputed over the normalized L299-303 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `862a0792e4271b735f2ec8646f1dbc2334a587944592a518434c6beb9dae20d7`, matching the row.
- `required_acceptance_text` equals that normalized span byte for byte
  (checked by comparison, not by eye).
- The crosswalk for this row is pinned by the structural validator at
  `validate_ledger_structural.py:2427-2479` (`EXPECTED_DISPOSITION_CROSSWALK`),
  which fixes `applicable_spec_ids` and `related_register_ids` and derives the
  `primary_spec` shape from the spec count.

## Reasoning

**What this review decides.** Whether `required_approvals` *exhaustively*
declares the typed approval obligations this component's source clause demands.
It is not a judgment that any approval has been obtained, and it grants none:
goal L624-626 states that neither this completeness review nor a `REVIEWER`-role
approval grants any non-delegated authority.

**The test applied.** The goal derives `required_approvals` from the component's
exact source acceptance text, dependencies, gates, transitions, and fail-closed
boundaries, over a closed 21-type vocabulary with no generic escape hatch. The
delegated type is deliberately narrow: goal L~968-975 excludes analyst
acceptance, domain-expert acceptance, memory promotion, legal sufficiency,
provider or data rights, budget or capacity commitments, regulatory approval,
production approval, named-owner commitment, credentials, purchases, external
coordination, distribution, external-service approval, and execution-system
operation from delegation. So the question for each row is whether its clause
demands any of those, or a `GOAL_OR_PROCESS_AUTHORIZATION`, beyond the one
declared requirement.

**Declared.** One requirement: `APR-DISP-T-4-01`, `DELEGATED_ARTIFACT_APPROVAL`,
authority "Delegated fresh Sol xhigh specification reviewer", scope "T-4 under
S01".

**Is any authority missing? — the batch's hardest case.** The clause is about
regulatory verification, and `REGULATORY_REVIEW`, `LEGAL_REVIEW`,
`DISTRIBUTION_APPROVAL` and `EXECUTION_TRUST_DOMAIN_APPROVAL` are all in the
closed vocabulary and all excluded from delegation. If this component owed any of
them, declaring only the delegated approval would be a real omission. It owes
none, and the clause says so in its own disposition: "Partially accept" is
precisely the ruling that current regulatory verification is *not* required before
documenting the initial private-use intent. The obligations for the modes it does
gate are declared on the rows this component's derivation names — REG-E-08 carries
`LEGAL_REVIEW` ("Competent legal reviewer"), `REGULATORY_REVIEW` ("Competent
regulatory reviewer"), `DISTRIBUTION_APPROVAL` ("Distribution owner") and a
`PRODUCT_OWNER_DECISION` for activating deferred scope; REG-E-09 carries
`EXECUTION_TRUST_DOMAIN_APPROVAL` ("Execution-boundary owner"). Both rows are
`CONDITIONAL_UNACTIVATED`, so those authorities are declared and dormant, which is
exactly the arrangement this clause describes. Declaring a regulatory approval on
`DISP-T-4` would pull a deferred obligation into a `REQUIRED_NOW` row and
contradict the source.

**And the reverse check.** REG-A-01, the row whose acceptance text this clause
amended, carries `PRODUCT_OWNER_DECISION` ("Product owner") for the boundary
decision itself. This component's obligation is the narrower documentary one —
that A-01 not claim legal sufficiency, and that the gate be stated — which a
delegated specification reviewer can verify against the clause.

**Scope string.** "T-4 under S01". Three specs apply and `primary_spec` is `null`,
so the scope string names S01, the spec owning both REG-A-01 and REG-E-08.

**Requirement state, read as stored.** `status` `UNRESOLVED`, `actor` `null`,
`timestamp` `null`, `evidence_ref_ids` `[]`, `matched_record_id` `null` — the
combination the goal prescribes when actor, timestamp, evidence, authorization
proof, or a matching record is missing. `approval_records` is `[]`, which is
correct: records are append-only evidence of decisions that actually happened,
and none has. The `required_authority` string is the single repo-wide delegated
literal, which the validator pins to exactly one value across every
`DELEGATED_ARTIFACT_APPROVAL` requirement in the ledger
(`validate_ledger_structural.py:3977-3987`); this row uses that string.

**Human-review links.** `human_review_id` normalizes to `["HR-0004"]`, appended
by `TR-DISP-T-4-003` under `HRD-0004-001` as a `null` → string growth. It carries
no approval authority for this component.

**Security exceptions.** `security_exception_ids == []`. The clause imposes a
gate; it grants no exception to one.

**Conclusion.** `required_approvals` is complete for this clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `DISP-T-4`'s `required_approvals` inventory is correct at the input bytes pinned above.
