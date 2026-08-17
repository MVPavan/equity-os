# Inventory review — DISP-M-2 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-M-2` |
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
{"approval_records":[],"human_review_id":["HR-0004"],"required_approvals":[{"actor":null,"approval_id":"APR-DISP-M-2-01","approval_type":"DELEGATED_ARTIFACT_APPROVAL","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Delegated fresh Sol xhigh specification reviewer","scope":"M-2 under S12","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (the recorder must recompute both
after its Phase A evidence append, per recording design r2 §3.4 — appending review
evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `ce4c0fd031780e4c18e68be9b8818ab48dc62b5febf55d248a507b360163c03e`
- `reviewed_inventory_sha256` (pre-record): `67830ef4cd2925f0d19378062e6731895185b514db579f6efd839d9b703e1352`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` lines 130-166, anchor
`M-2`, `source_title` "Fact identity and revision semantics":

> ### M-2 — Fact identity and revision semantics
>
> **Disposition: Accept; the required model is richer than a single key.**
>
> The system needs to distinguish four concepts:
>
> 1. **source occurrence:** the value as it appears in a specific source location;
> 2. **extraction result:** parser/model output for that occurrence and parser version;
> 3. **economic measurement slot:** the intended metric, entity, period, scope, dimensions, and definition;
> 4. **approved canonical selection:** the observation Funda currently uses for a specified knowledge cutoff.
>
> A robust design should include:
>
> ```text
> measurement_key
>   = entity
>   + metric definition/version
>   + period
>   + statement/consolidation scope
>   + dimension set
>   + accounting/adjustment basis
>
> observation_id
>   = immutable source occurrence
>
> revision_family_id
>   = observations believed to represent the same measurement slot
>
> revision_reason
>   = issuer restatement
>   | source correction
>   | parser re-extraction
>   | manual correction
>   | normalization-policy change
> ```
>
> A parser upgrade should normally create a new extraction result, not silently rewrite the economic observation. Restatements, reclassifications, and segment-definition changes require explicit reconciliation rather than automatic supersession by key.


Recomputed this round against current bytes:

- `source_hash` over the whole file → `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`, equal to the stored value.
- `text_digest` over the normalized L130-166 span
  (CRLF-to-LF normalized, surrounding ASCII whitespace trimmed) →
  `96f0c2eb2f7b560d54ec98d18c6515a90048f6093ebe3942ba5d4396103ba24f`, equal to the stored value.
- `required_acceptance_text` equals that normalized span byte for byte.
- Every `evidence_refs` object on this row was re-hashed against current bytes and
  matches its stored `content_sha256`.

## Reasoning

**Enumerated.** One requirement:

| `approval_id` | `approval_type` | `required_authority` | `scope` | `status` |
|---|---|---|---|---|
| `APR-DISP-M-2-01` | `DELEGATED_ARTIFACT_APPROVAL` | `Delegated fresh Sol xhigh specification reviewer` | `M-2 under S12` | `UNRESOLVED` |

Type in the closed vocabulary (goal L~538-548); authority literal is the shared
value enforced at `validate_ledger_structural.py:2620-2631`.

**Source-clause scan for omitted authorities.** Remit per goal L188; derivation
basis per goal L535-537.

Report L130-166 — the batch's longest occurrence — is written entirely as a
modelling prescription: four concepts to distinguish, a fenced identity schema, and
two rules about how revisions must be handled. Scanned in full for authorization
language, including the fenced block. The only candidate is the closing sentence:
"Restatements, reclassifications, and segment-definition changes **require explicit
reconciliation** rather than automatic supersession by key."

Examined and rejected as an omitted authority. "Explicit reconciliation" names a
*process* the system must perform — a deliberate, recorded mapping between
observations — not a person or role whose sign-off is required, and the closed
approval vocabulary (goal L~538-548) contains no type that fits a reconciliation
step. The corroborating evidence is that all three of this component's related
registers — `REG-B-05`, `REG-B-11`, `REG-C-03` — carry the delegated artifact
approval and nothing else, even though `B-11`'s own acceptance restates the same
reconciliation semantics. If reconciliation demanded a typed authority, it would
have surfaced on those register decisions first.

Goal L~552-556 is the relevant safety valve, and it is not triggered here: it
applies when a source requires an authority the vocabulary cannot represent, and
requires reconciliation and explicit approval before that row advances. This clause
requires no authority at all.

**`human_review_id`.** `"HR-0004"`, a single `HR-####` string (goal L~192-196),
normalized to `["HR-0004"]` in this projection.

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

**Conclusion.** `required_approvals` is complete: the clause demands no authority
beyond the delegated approval of the owning specification artifact.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition, and grants no
authority of any kind (goal L~624-626). It records only that `DISP-M-2`'s
`required_approvals` inventory is complete at the input bytes pinned above.
