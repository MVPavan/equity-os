# Inventory review — PG-05-08 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `PG-05-08` |
| `review_type` | `APPROVAL` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `3c844df3-fdab-4e89-929b-89fcbc8223d4` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-16T03:50:06Z` |

Role binding: `CONTEXT.md` "Agent roles (harness-wide)" L137-139 binds `REVIEWER` to
Claude Opus 5 at high effort, in an agent and context independent of any `IMPLEMENTER`
that produced the reviewed content. The digest above is the `CONTEXT.md` bytes at review
time and is an immutable historical capture, never re-verified against later bytes
(`validate_ledger_structural.py:250-262`).

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

Fresh validation at these exact bytes, run this round:
`python3 scripts/equity_os_blueprint/validate_ledger_structural.py --repo-root .` → exit `0`;
`python3 scripts/equity_os_blueprint/extract_goal_validators.py --check` → exit `0`, so the
structural validator's pinned manifests are the goal's own bytes, not a downstream
paraphrase of them.

## Reviewed inventory, exactly as read

`review_inventory_projection(row, "APPROVAL")` — canonical JSON
(`validate_ledger_structural.py:292-318`, extracted by `ast` and executed in an isolated
namespace this round rather than transcribed):

```json
{"approval_records":[],"human_review_id":["HR-0004"],"required_approvals":[],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (the recorder must recompute both after
its Phase A evidence append, per recording design r2 §3.4 — appending review evidence
mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `37b2b3249a271a6c2a1cfddd0c9d3f4b837cf5a3a928444a54221abfba0dbada`
- `reviewed_inventory_sha256` (pre-record): `97690c6bdaa272b10410d8e6282fe908df7a46302da6a6197299f8bb98ef8958`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line 144,
anchor `F-0.5-08`, the 8th bullet under the
`### Phase 0.5 may exit only when` heading at line 135, inside
`## F. Phase-gate scorecard` (line 122):

> - the rejected-claim rework path and evidence-package versioning are demonstrated;

- `source_hash` recomputed over the whole register file →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L144 span (CRLF→LF, surrounding ASCII
  whitespace trimmed) → `1df28677bf9ab56b1b400421824ddf0902b84c6df556e282bec2234f0c1270a2`, matching the row.
- `required_acceptance_text` is that span with the `- ` list marker and the trailing
  `;` removed — compared programmatically, not by eye.
- `EV-PG-05-08-SOURCE` is a `UTF8_LINE_SPAN` reference over exactly that one line
  (`start_line == end_line == 144`); its `content_sha256` recomputes to the same digest,
  so the row's only evidence object resolves against current bytes.

## Reasoning

**What authority the clause demands.** On its face, none: "the rejected-claim rework
path and evidence-package versioning are demonstrated" asserts that a mechanism was
exercised, and the exercise either happened or it did not.

**What is enumerated.** `required_approvals == []`. Per goal L188 this is a positive
determination and this review affirms it — but this is the row in the batch where I had to
work hardest to reach that conclusion, so the reasoning is set out in full.

**The argument for a missing `ANALYST_ACCEPTANCE`.** B-14 (register L64), this clause's
sole related register, ends its acceptance with "partial revalidation and **reapproval**
succeed". The program-level approval-inventory review r0 read exactly that phrase as
requiring an analyst authority, listing `REG-B-14` under "Four register rows omit
source-required non-delegated approvals — `REG-B-14`: missing `ANALYST_ACCEPTANCE`;
reapproval must succeed at register-v2.md:64". That finding was acted on: `REG-B-14` now
carries `APR-REG-B-14-02`, `ANALYST_ACCEPTANCE` / `Responsible analyst`, plus
`REQ-REG-B-14-ANALYST_ACCEPTANCE-02`. If the rework path cannot be demonstrated without a
real reapproval, the gate that demands the demonstration arguably demands the authority
too.

**Why I concluded it is not missing here.**

1. **The clause's condition is the demonstration, not the approval.** The reapproval is a
   step *inside* the mechanism under test, in the same way the invalidation cascade and
   the immutability of the prior package are. The gate condition is that the path works.
   Contrast `PG-05-01` and `PG-05-05`, whose gate condition *is* an approval state ("is
   approved") and which correspondingly carry the approval requirement their register row
   carries. That distinction — does the clause assert an approval state, or does it assert
   that something was built, recorded, or exercised — is applied consistently across all
   35 phase-gate rows in the ledger: exactly six carry a non-delegated requirement, and
   each of those six says "approved", "reviewed", "accepted", or "acceptable" in its own
   text. This clause says "demonstrated".
2. **The authority is enumerated where it binds.** `REG-B-14` holds the analyst
   requirement and lists `PG-05-08` in its `gate_refs`, so the two are coupled: the gate
   cannot be evaluated against a register row whose own approval obligation is unmet. The
   authority is not absent from the program; it is enumerated on the row whose acceptance
   text creates it.
3. **The proof mode the clause does demand is present.** What "demonstrated" adds over
   "exists" is executability, and that is carried by `REQ-PG-05-08-COMMAND-PROOF` — see
   the `EVIDENCE` review for this component. The clause's distinctive demand is met by the
   obligation the contract actually assigns to it.

I record the counter-argument because it is genuine and a later reader should be able to
re-open it on new information. On these bytes and this clause text, the empty list is
correct.

**Check against the rest of the closed vocabulary.** Rework and versioning engage no
budget, capacity, named-owner, rights, legal, regulatory, production, distribution,
security, or execution authority; none of those surfaces appears in the clause or in
B-14's acceptance text.

**Why no delegated artifact approval.** No `phase_gate_clause` row carries one;
`primary_spec` is `null`.

**Rest of the projection.** `approval_records == []`; `security_exception_ids == []`;
`human_review_id` normalizes to `["HR-0004"]`, and `PG-05-08` appears in the canonical
human-review artifact (2 occurrences, verified by lookup), consistent with
`TR-PG-05-08-001`. It is not in `EXPECTED_PRIOR_HR_LINKS`.

**Residuals.** None. The empty approval list is complete against the clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition, and grants no
non-delegated authority (goal L624-626). It records only that the component's
`required_approvals` obligation list is complete against its source clause at the input
bytes pinned above.
