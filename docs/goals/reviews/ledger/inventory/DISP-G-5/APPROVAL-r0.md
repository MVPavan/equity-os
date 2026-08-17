# Inventory review — DISP-G-5 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-G-5` |
| `review_type` | `APPROVAL` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `a88da077-0dfc-49ab-bb1a-df4e8266291b` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-15T13:16:03Z` |

Role binding: `CONTEXT.md` "Agent roles (harness-wide)" binds `REVIEWER` to
Claude Opus 5 at high effort, in an agent and context independent of any
`IMPLEMENTER` that produced the reviewed content. The digest above is the
`CONTEXT.md` bytes at review time and is an immutable historical capture.

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
{"approval_records":[],"human_review_id":["HR-0001","HR-0004"],"required_approvals":[{"actor":null,"approval_id":"APR-DISP-G-5-01","approval_type":"DELEGATED_ARTIFACT_APPROVAL","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Delegated fresh Sol xhigh specification reviewer","scope":"G-5 under S06","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (the recorder must recompute both
after its Phase A evidence append, per recording design r2 §3.4 — appending review
evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `3784cc2355215c3b43b79bb6c4e70ca20371fbe0348224b6fb1a40df180140c7`
- `reviewed_inventory_sha256` (pre-record): `79f4694dbc84f2321f1e8a461ce15ffeed1e880025ee189dd1bf6f3b4c194e83`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` lines 102-116, anchor
`G-5`, `source_title` "Undefined materiality":

> ### G-5 — Undefined materiality
>
> **Disposition: Accept, but broaden the remedy.**
>
> The validator cannot enforce “all material claims” until materiality is operationally defined. A single quantitative percentage is insufficient because a small number may still be thesis-critical, governance-critical, or legally significant.
>
> The minimum materiality policy should combine:
>
> - **quantitative magnitude:** relative to the relevant statement line, segment, guidance range, equity, enterprise value, or prior assumption;
> - **always-material categories:** guidance, restatements, auditor qualifications, going-concern language, promoter pledges, related-party transactions, capital raises, material dilution, major corporate actions, management changes, and regulatory actions;
> - **thesis relevance:** whether the item changes an assumption, catalyst, risk, valuation input, management-credibility assessment, or thesis breaker;
> - **uncertainty and source conflict:** unresolved contradictions or low-confidence extraction of an otherwise important item;
> - **coverage-level overrides:** company- or mandate-specific thresholds stored with a policy version.
>
> The materiality decision itself should be reviewable and versioned.


Recomputed this round against current bytes:

- `source_hash` over the whole file → `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`, equal to the stored value.
- `text_digest` over the normalized L102-116 span
  (CRLF-to-LF normalized, surrounding ASCII whitespace trimmed) →
  `299faaca255a6bf92cf524c3251a5e269f1e46ad112799f732005b09432542c0`, equal to the stored value.
- `required_acceptance_text` equals that normalized span byte for byte.
- Every `evidence_refs` object on this row was re-hashed against current bytes and
  matches its stored `content_sha256`.

## Reasoning

**Enumerated.** One requirement:

| `approval_id` | `approval_type` | `required_authority` | `scope` | `status` |
|---|---|---|---|---|
| `APR-DISP-G-5-01` | `DELEGATED_ARTIFACT_APPROVAL` | `Delegated fresh Sol xhigh specification reviewer` | `G-5 under S06` | `UNRESOLVED` |

Type in the closed vocabulary (goal L~538-548); authority literal is the shared
value enforced at `validate_ledger_structural.py:2620-2631`.

**Source-clause scan for omitted authorities.** Remit per goal L188; derivation
basis per goal L535-537.

Report L102-116 prescribes the content of a minimum materiality policy — five
combining ingredients — and closes "The materiality decision itself should be
**reviewable and versioned**." Two candidate authority readings were examined:

1. *"reviewable"*. Reviewability is a property required of the artifact, not an
   authorization event, and it names no actor. The contract's own reviewing
   mechanism for artifacts of this kind is the `REVIEWER`-role review that the
   delegated approval already carries, and goal L~624-626 is explicit that such a
   review "grants no non-delegated authority". So "reviewable" is discharged by the
   enumerated delegated approval and demands nothing further.
2. *The always-material category list* — guidance, restatements, auditor
   qualifications, going-concern language, promoter pledges, related-party
   transactions, capital raises, material dilution, major corporate actions,
   management changes, regulatory actions. This is substantive equity-research
   judgement, and the related register `REG-A-10` does carry
   `DOMAIN_EXPERT_ACCEPTANCE` / `Equity-research domain expert`. Rejected as an
   omission here because the clause prescribes *what the policy must combine*, not
   that a domain expert must sign this occurrence; `A-10` is where the register
   places that sign-off, and the sibling occurrence `DISP-6-2`, which relates the
   same `A-10` and `C-04`, likewise carries only the delegated approval. Adding it
   here would duplicate one authority across a register decision and an occurrence
   that merely broadens its remedy.

No dependency, phase gate, transition, or fail-closed boundary in the clause
introduces a further authority.

**`human_review_id`.** `["HR-0001", "HR-0004"]` — the array shape goal L~192-196
permits ("a sorted unique array of at least two IDs"), verified sorted and unique,
and normalized by `normalized_human_review_id` to the same sorted list inside this
projection. `HR-0001` is the entry bound to this row's open blocking finding
`S06-I7`; `HR-0004` is the entry every canonical row in this batch links. Both
resolve into the one canonical human-review artifact. This is the only row in the
batch with a compound link, and the append-only growth rule (`null -> string`,
`null -> sorted array`, or an existing link -> a sorted superset) is satisfied.

**`approval_records`.** `[]`. Correct and required: no approval decision has been
made on this component, and goal L~588-592 says a requirement missing actor,
timestamp, evidence, authorization proof, or matching record stays `UNRESOLVED`.
Each requirement here carries `actor: null`, `timestamp: null`,
`evidence_ref_ids: []`, `matched_record_id: null`, `status: "UNRESOLVED"` —
internally consistent, and consistent with `approval_records` being empty. An
`APPROVED` record with no requirement, or a `SATISFIED` requirement with no record,
would each have been a defect; neither is present.

**`security_exception_ids`.** `[]`. The clause raises no fail-closed security
boundary and no security exception has been approved, so an empty list is the
correct completed determination rather than an unknown.

**Relationship to the open finding.** `S06-I7`'s own record proposes a
`required_authority` of "Explicit rank-1 current-user authority" with
`approval_type` `GOAL_OR_PROCESS_AUTHORIZATION`, required for "Any post-cap S06
remediation and separate fresh exact-byte Sol xhigh review mechanism". I examined
whether that belongs in `required_approvals` and concluded it does not: it is an
authority required to *authorize a remediation route* after the r4 review cap, not
an approval obligation of this component's own source clause, and the finding
records it as `NOT_AUTHORIZED` / `fix.status`. It is correctly held in
`open_findings`, which is a different collection from the one this review covers.
**This CLEAN verdict clears nothing about `S06-I7`**, which remains
`OPEN_BLOCKING` with `delivery_status` `REVIEW_BLOCKED`.

**Conclusion.** `required_approvals` is complete: the clause demands no authority
beyond the delegated approval of the owning specification artifact.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition, and grants no
authority of any kind (goal L~624-626). It records only that `DISP-G-5`'s
`required_approvals` inventory is complete at the input bytes pinned above.
