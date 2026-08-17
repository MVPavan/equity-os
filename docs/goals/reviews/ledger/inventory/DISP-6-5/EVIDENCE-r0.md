# Inventory review — DISP-6-5 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-6-5` |
| `review_type` | `EVIDENCE` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `13edf3cc-a5b0-4217-8730-759de344e6db` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-15T13:10:41Z` |

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

Fresh structural validation at these exact bytes → exit `0`.

## Reviewed inventory, exactly as read

`review_inventory_projection(row, "EVIDENCE")` — canonical JSON:

```json
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"82f00975f69fda912663f80143996c5fe812213cfb7a8288cc72dbc9a3bee314","digest_mode":"UTF8_LINE_SPAN","end_line":373,"evidence_ref_id":"EV-DISP-6-5-SOURCE","path":"docs/blueprint/funda-third-order-review-disposition-report.md","scope":"Exact authoritative source occurrence for DISP-6-5","start_line":371},{"captured_at":"2026-08-15T07:13:28Z","content_sha256":"3b66cb90a76ab8f62eef203de2beabff5171c556146071974cc48e926374bbd2","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-DISP-6-5-SPEC-DRAFT","path":"docs/specs/equity-os-s25-quant-validation-historical-leakage.md","scope":"Current draft specification bytes for DISP-6-5","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: ### 6.5 Model-weight leakage is scoped to historical claims\n\nIt is a standing caveat for historical LLM replay and agent-alpha claims. It is not a reason to weaken current-period evidence controls or block the current earnings-review MVP.","evidence_id":"REQ-DISP-6-5-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"DISP-6-5 acceptance and delivery scope","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (recorder recomputes after
Phase A, recording design r2 §3.4):

- `reviewed_input_sha256` (pre-record): `916bbb948f34a0792518fa5c39efdc874dbee5f6bf88052c8c2b12a2e59ddf5a`
- `reviewed_inventory_sha256` (pre-record): `3880bcb9ebf6f2c9fb0797f4e0bcd7d099818d2e8e1c5ddfae50770d42459ddf`

## Scope of this decision

Completeness of `required_evidence` only (goal L492-494). The single item is
legitimately `UNRESOLVED` with empty `evidence_ref_ids` (goal L484).

## The source clause, re-read this round

Disposition report L371-373:

> ### 6.5 Model-weight leakage is scoped to historical claims
>
> It is a standing caveat for historical LLM replay and agent-alpha claims. It
> is not a reason to weaken current-period evidence controls or block the
> current earnings-review MVP.

`text_digest` and `EV-DISP-6-5-SOURCE.content_sha256` both recomputed over the
normalized span → `82f00975…`, matching.

## Reasoning

**Obligation decomposition.** Two obligations, both about what the S25 artifact
must say: (a) model-weight leakage is recorded as a standing caveat scoped to
historical LLM replay and agent-alpha claims; (b) that caveat is bounded — it
does not weaken current-period evidence controls and does not block the current
earnings-review MVP. Obligation (b) is a *negative scope statement*, which is
still an artifact-content obligation: what must be provable is that S25 says it.
The single `REQ-DISP-6-5-ACCEPTANCE` item (`ARTIFACT`/`CONTENT_HASH`) quotes the
whole clause, so both are represented and classified.

**Why (b) does not generate a separate item.** A tempting reading is that (b)
creates an obligation on the *other* scope it protects — that someone must prove
current-period evidence controls were not weakened. That would be an obligation
on `C-15` ("Enforce run knowledge cutoff across stores and tools") and on the MVP
rows, not on this one. §6.5 imposes nothing new on them; it declines to impose
anything. An evidence item asserting "prove we did not weaken C-15 because of
6.5" would be a proof obligation with no source demand behind it, and the
`EVIDENCE` review's job is completeness against the clause, not invention beyond
it.

**`COMMAND_RESULT` — absent, and correctly so.** `DISP-6-5` is not in
`EXPECTED_COMMAND_PROOF_COMPONENTS` (`validate_ledger_structural.py:2635-2649`),
and this is the informative case: **`REG-E-10` is in that set**. `E-10`'s
acceptance opens "Store/tool leakage controls are tested" — a genuinely
mechanical obligation — and the ledger inventories its command proof there.
§6.5 adds no testable control of its own; it *classifies* one leakage channel as
uncontrollable and disclosure-only, which is by construction not something a
command can verify. The division is exact: testable leakage controls on
`REG-E-10`, the untestable-by-nature caveat on `DISP-6-5`.

**`TYPED_APPROVAL` — unrepresentable.** The row's only approval requirement is
`APR-DISP-6-5-01`, a `DELEGATED_ARTIFACT_APPROVAL`; ledger-wide all 123 such
requirements are covered by zero `TYPED_APPROVAL` items (goal L595-598). The
product-owner activation authority for the deferred `E-10` scope sits on
`REG-E-10`, not here (see this component's `APPROVAL` review).

**No negative "no-implementation" proof.** `DISP-6-5` is a `REQUIRED_NOW` active
control with `rejection_record: null`; it is not one of the 13
`first_release_deferral` rows nor `DISP-R-1`, and the
`NO_IMPLEMENTATION_REQUIREMENT_MAP` (`validate_ledger_structural.py:2671`) does
not name it.

**Framing check — deliberately performed, because this row sits over deferred
scope.** The description reads "Current proof satisfying: ### 6.5 Model-weight
leakage is scoped to historical claims …". The r0 program-level evidence review
flagged that a positively framed "current proof satisfying <deferred capability>"
inverts the boundary on deferral rows. It does not reproduce here: what must be
proven now is that S25 *states* the caveat and its bound — a present, satisfiable
documentation obligation — not that any historical replay was performed. The
deferred thing is `E-10`'s policy publication, which is `REG-E-10`'s row, not this
one.

**`evidence_refs`.** Two references, both re-verified against current bytes:
`EV-DISP-6-5-SOURCE` (`UTF8_LINE_SPAN` L371-373, digest `82f00975…`, captured
`2026-08-13T02:49:11Z`) and `EV-DISP-6-5-SPEC-DRAFT` (`FILE_BYTES` over
`docs/specs/equity-os-s25-quant-validation-historical-leakage.md`, digest
`3b66cb90…`, captured `2026-08-15T07:13:28Z`). Both resolve to live repository
paths and both captures precede this review's timestamp.

**`verification_command` observation, not a finding.** `mode: UNRESOLVED`,
permitted during initial ledger construction (goal L498-500); outside the pinned
command-proof population, so the eventual resolution is `NOT_APPLICABLE` with its
own evidenced reviewer attestation.

**Residuals.** None.

---

**verdict: CLEAN**

`required_evidence` for `DISP-6-5` is complete at the input bytes pinned above.
This review satisfies no evidence item, activates no deferred scope, and
authorizes no delivery, gate, approval, or transition.
