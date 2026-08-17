# Inventory review — DISP-R-4 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-R-4` |
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
{"approval_records":[],"human_review_id":["HR-0001","HR-0004"],"required_approvals":[{"actor":null,"approval_id":"APR-DISP-R-4-01","approval_type":"DELEGATED_ARTIFACT_APPROVAL","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Delegated fresh Sol xhigh specification reviewer","scope":"R-4 under S06","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `9ee3c78b356b9d624a71ea6dd1bfff1fcb32909f858f14538bf067ea9b456788`
- `reviewed_inventory_sha256` (pre-record): `08e359898bddf44f5632eef538e56288861302b325cb360a3ad2b099dc0d49b5`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` lines 337-341, anchor `R-4`, title "Add observable falsifiers":

> ### R-4 — Add observable falsifiers
>
> **Disposition: Accept.**
>
> The output contract should state what observable event, metric, management outcome, or evidence would materially weaken or reverse the current thesis. This is distinct from listing generic risks.

- `source_hash` recomputed over the whole file → `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`, matching the row.
- `text_digest` recomputed over the normalized L337-341 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `5b47fb8bb6e04161603fe15b37b17c534201e957fc53f6d8212dbb83180cee07`, matching the row.
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

**Declared.** One requirement: `APR-DISP-R-4-01`, `DELEGATED_ARTIFACT_APPROVAL`,
authority "Delegated fresh Sol xhigh specification reviewer", scope "R-4 under
S06".

**Is any authority missing?** The clause demands that the output contract state
observable falsifiers. `ANALYST_ACCEPTANCE` and `PRODUCT_OWNER_DECISION` are the
candidates, and both are declared — on REG-A-04, the row this occurrence amends,
which carries `ANALYST_ACCEPTANCE` ("Responsible analyst") with paired
`ANALYST`/`TYPED_APPROVAL` evidence, `PRODUCT_OWNER_DECISION` ("Product owner"),
and the delegated approval. That is the right placement: accepting the output
contract, including whether its falsifiers are the right falsifiers, is an
analyst judgment about A-04. This component's obligation is that the contract
*contain* a falsifier statement distinct from a generic risk list, which a
delegated specification reviewer can check against the source clause. Declaring an
analyst acceptance here as well would record one real-world decision twice.

**Scope string.** "R-4 under S06" matches the single `applicable_spec_ids` entry
and the `primary_spec` object, and S06 is REG-A-04's owning spec.

**Requirement state, read as stored.** `status` `UNRESOLVED`, `actor` `null`,
`timestamp` `null`, `evidence_ref_ids` `[]`, `matched_record_id` `null` — the
combination the goal prescribes when actor, timestamp, evidence, authorization
proof, or a matching record is missing. `approval_records` is `[]`, which is
correct: records are append-only evidence of decisions that actually happened,
and none has. The `required_authority` string is the single repo-wide delegated
literal, which the validator pins to exactly one value across every
`DELEGATED_ARTIFACT_APPROVAL` requirement in the ledger
(`validate_ledger_structural.py:3977-3987`); this row uses that string.

**Human-review links.** `human_review_id` normalizes to `["HR-0001","HR-0004"]`,
a sorted unique array reached by append-only growth: `null` → `"HR-0001"` by the
`REFERENCE_APPEND` recording the `S06-I7` blocker, then → `["HR-0001","HR-0004"]`
by `AUTHORITY_RECONCILIATION` under `HRD-0004-001`. HR-0001 is the open human-review
entry for `S06-I7`. Neither link is an approval, and `approval_records` is empty.

**Interaction with the open blocker.** `S06-I7` is open and load-bearing on this
row. A blocker is a delivery and review-state condition, not an approval
obligation; nothing about it adds a `required_approvals` entry, and this review
does not clear it.

**Security exceptions.** `security_exception_ids == []`.

**Conclusion.** `required_approvals` is complete for this clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `DISP-R-4`'s `required_approvals` inventory is correct at the input bytes pinned above.
