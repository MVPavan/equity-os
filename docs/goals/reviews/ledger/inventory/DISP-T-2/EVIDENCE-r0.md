# Inventory review — DISP-T-2 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-T-2` |
| `review_type` | `EVIDENCE` |
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

`review_inventory_projection(row, "EVIDENCE")` — canonical JSON:

```json
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"34af3a7c44b6c048ae93b3e489f9e1441f899f132586806c924b753e891905e2","digest_mode":"UTF8_LINE_SPAN","end_line":291,"evidence_ref_id":"EV-DISP-T-2-SOURCE","path":"docs/blueprint/funda-third-order-review-disposition-report.md","scope":"Exact authoritative source occurrence for DISP-T-2","start_line":274},{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"96add3840a6ff8c6280a70a75242b20a1615e50e9a49236d1bd3636f7e22d9ba","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-DISP-T-2-SPEC-DRAFT","path":"docs/specs/equity-os-s08-success-metrics-budgets-capacity.md","scope":"Current draft specification bytes for DISP-T-2","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: ### T-2 — Success metrics are scattered\n\n**Disposition: Accept.**\n\nCreate one versioned success-metric contract covering definitions, units, measurement procedures, and phase applicability for:\n\n- factual accuracy;\n- citation correctness;\n- numerical traceability;\n- unsupported-claim rate;\n- analyst minutes;\n- verification time per claim;\n- coverage capacity;\n- latency;\n- model/tool cost;\n- failure and retry rates.\n\nAll phase gates should reference this contract.","evidence_id":"REQ-DISP-T-2-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"DISP-T-2 acceptance and delivery scope","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `b3975a80328c84a4e3452fc0995aaa8fec7b7a2d2f31c43dfd0f182854384aba`
- `reviewed_inventory_sha256` (pre-record): `4071994771511a5891b85152f40a3480bb8cef2f341c23a983fa48abc0e833a6`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` lines 274-291, anchor `T-2`, title "Success metrics are scattered":

> ### T-2 — Success metrics are scattered
>
> **Disposition: Accept.**
>
> Create one versioned success-metric contract covering definitions, units, measurement procedures, and phase applicability for:
>
> - factual accuracy;
> - citation correctness;
> - numerical traceability;
> - unsupported-claim rate;
> - analyst minutes;
> - verification time per claim;
> - coverage capacity;
> - latency;
> - model/tool cost;
> - failure and retry rates.
>
> All phase gates should reference this contract.

- `source_hash` recomputed over the whole file → `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`, matching the row.
- `text_digest` recomputed over the normalized L274-291 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `34af3a7c44b6c048ae93b3e489f9e1441f899f132586806c924b753e891905e2`, matching the row.
- `required_acceptance_text` equals that normalized span byte for byte
  (checked by comparison, not by eye).
- The crosswalk for this row is pinned by the structural validator at
  `validate_ledger_structural.py:2427-2479` (`EXPECTED_DISPOSITION_CROSSWALK`),
  which fixes `applicable_spec_ids` and `related_register_ids` and derives the
  `primary_spec` shape from the spec count.

## Reasoning

**What this review decides.** Whether `required_evidence` is a *complete*
enumeration of the proof this component's source clause demands. It is not a
judgment that any proof has been obtained: every item here is `UNRESOLVED` with
empty `evidence_ref_ids`, which the validator requires of an unresolved item
(`validate_ledger_structural.py:2138-2139`), and this review does not change that.

**How completeness is testable at all.** Each item's `description` opens
"Current proof satisfying:" and then embeds the clause verbatim. I compared that
embedded text with `required_acceptance_text` and with the freshly normalized
source span, byte for byte, and all three agree. So no demand in the clause falls
outside the enumerated obligation's scope, and the completeness question reduces
to a sharper one: does any demand in the clause require a *different proof mode*
— `COMMAND` or `TYPED_APPROVAL` — that is not separately enumerated? The closed
vocabularies are the goal's typed-evidence section, mechanized at
`validate_ledger_structural.py:2124-2137`, where `COMMAND_RESULT` forces
`COMMAND` and every human evidence type forces `TYPED_APPROVAL`.

**Enumerated.** One item: `REQ-DISP-T-2-ACCEPTANCE`, `ARTIFACT` /
`CONTENT_HASH`, scope "DISP-T-2 acceptance and delivery scope", `UNRESOLVED`.

**Demand-by-demand.** This is the batch's longest clause and the one with the
most demands: create one versioned success-metric contract; have it cover
definitions, units, measurement procedures, and phase applicability; do so for
ten named metric families — factual accuracy, citation correctness, numerical
traceability, unsupported-claim rate, analyst minutes, verification time per
claim, coverage capacity, latency, model/tool cost, and failure and retry rates;
and have all phase gates reference the contract. Every one of those is a property
of documents: what the contract says, and what the gate definitions cite. The
single `CONTENT_HASH` item, whose description embeds all eighteen lines verbatim,
therefore covers the whole clause.

**Is a command proof missing?** Latency, model/tool cost, and failure and retry
rates are mechanically measurable, and that is the strongest candidate for an
omitted `COMMAND_RESULT` obligation in this batch. The clause demands their
*definitions, units, and measurement procedures* — not their measurement. The
measuring obligations exist elsewhere and are enumerated there: six phase-gate
components carry `COMMAND_RESULT` items in the pinned
`EXPECTED_COMMAND_PROOF_COMPONENTS` manifest (`:2635-2649`), while REG-A-13, the
contract row itself, carries none. A disposition that folds metric definitions
into a contract cannot owe more executable proof than the contract row.

**The cross-reference demand.** "All phase gates should reference this contract"
is a demand about the gate definitions rather than the contract, but it remains a
document-content question and is provable by content hash over the gate text
together with the contract. It is inside the embedded description, so it is inside
the enumerated obligation; it is not expressed as `gate_refs`, which is a
register-only field.

**Typed-approval demands, checked.** Freezing the contract is a decision, and
REG-A-13 enumerates it as a `PRODUCT_OWNER_DECISION` requirement. This clause
demands consolidation, not the freeze, so no `TYPED_APPROVAL` evidence item is
owed here.

**`evidence_refs` as read.** Two objects, both re-hashed this round:
`EV-DISP-T-2-SOURCE` (`UTF8_LINE_SPAN` L274-291, `content_sha256` equal to the
row's `text_digest`) and `EV-DISP-T-2-SPEC-DRAFT` (`FILE_BYTES` over the S08
spec). Both resolve against current bytes.

**Kind-level asymmetry, checked and dismissed.** All 32 `disposition_item` rows,
including this one, declare a `DELEGATED_ARTIFACT_APPROVAL` requirement but carry
no `REVIEW`-typed evidence item, whereas every `register_row` (60),
`first_release_deferral` (13), `scale_trigger` (8) and 10 of 11 `sequence_clause`
rows carry a `REQ-*-SPEC-REVIEW` item alongside the same approval type. I counted
this across all 169 canonical rows rather than assuming it. It is not an omission
of source-demanded proof: the goal makes the delegated approval *record* itself
the carrier — "that record has null human-resolution fields and carries the
persisted clean `REVIEWER`-role review" — and the validator forbids `approval_ids`
on any non-`TYPED_APPROVAL` item (`:2135-2137`), so the `REQ-*-SPEC-REVIEW` items
on other kinds are not a contractual link to the approval either. The delegated
approval remains an unsatisfied obligation on this row regardless, so no proof is
lost. Recorded as a repo-wide inventory-style observation, not a finding against
this component.

**`verification_command`.** Mode `UNRESOLVED`, no commands, no
`not_applicable_review`. The goal admits `UNRESOLVED` "during initial ledger
construction only", and this row is pre-implementation — `gate_result` is
`NOT_EVALUATED` and nothing is `VERIFIED`. It is a forward obligation to resolve
to `COMMANDS` or `NOT_APPLICABLE` before terminal use, not a present gap in the
`required_evidence` enumeration this review audits.

**Conclusion.** `required_evidence` is complete for this clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `DISP-T-2`'s `required_evidence` inventory is correct at the input bytes pinned above.
