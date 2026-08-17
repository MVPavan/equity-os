# Inventory review — DISP-6-3 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-6-3` |
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
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"1229dceb7624a05b00ff7b56a390013260bbd87947fe74372ab21695f0514880","digest_mode":"UTF8_LINE_SPAN","end_line":365,"evidence_ref_id":"EV-DISP-6-3-SOURCE","path":"docs/blueprint/funda-third-order-review-disposition-report.md","scope":"Exact authoritative source occurrence for DISP-6-3","start_line":363},{"captured_at":"2026-08-15T07:13:28Z","content_sha256":"dbb6b8600de771e9ae668208a9893394321ce67fb366c706c2d9c98985ee85aa","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-DISP-6-3-SPEC-DRAFT","path":"docs/specs/equity-os-s17-entity-security-master-actions.md","scope":"Current draft specification bytes for DISP-6-3","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: ### 6.3 ISIN is an external identifier\n\nUse an internal stable identifier as the primary key. ISIN is a high-value mapping, not the authority for Funda object identity.","evidence_id":"REQ-DISP-6-3-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"DISP-6-3 acceptance and delivery scope","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (recorder recomputes after
Phase A, recording design r2 §3.4):

- `reviewed_input_sha256` (pre-record): `bc29cafeff2b8f079afaf2465d3b9bef679825f492e722dc83ec7cef0b72ee6f`
- `reviewed_inventory_sha256` (pre-record): `e7d85f78d6c6311ef9a4c89c7b3883170be3efb3db7816b03c370b32da9041e3`

## Scope of this decision

Completeness of `required_evidence` only (goal L492-494). The single item is
legitimately `UNRESOLVED` with empty `evidence_ref_ids` (goal L484).

## The source clause, re-read this round

Disposition report L363-365:

> ### 6.3 ISIN is an external identifier
>
> Use an internal stable identifier as the primary key. ISIN is a high-value
> mapping, not the authority for Funda object identity.

`text_digest` and `EV-DISP-6-3-SOURCE.content_sha256` both recomputed over the
normalized span → `1229dceb…`, matching.

## Reasoning

**What the clause demands, and what it does not.** Two obligations: (a) the
entity/security master uses an internal stable identifier as primary key; (b)
ISIN is modelled as a mapping and never as identity authority. Both are
properties of the S17 specification's data model, provable by content hash over
that artifact. The single `REQ-DISP-6-3-ACCEPTANCE` item
(`ARTIFACT`/`CONTENT_HASH`, scope "DISP-6-3 acceptance and delivery scope")
quotes the whole clause and covers both.

**The tempting extra item — a runtime identifier test — checked and correctly
absent.** §6.3's related register row `C-17` demands "one real identifier-change
case tested", which *is* a mechanical obligation. So the question is real: should
`DISP-6-3` carry a `COMMAND_RESULT` item? No, and this is locatable rather than a
judgment call: `EXPECTED_COMMAND_PROOF_COMPONENTS`
(`validate_ledger_structural.py:2635-2649`) pins the exact 25-row command-proof
population, `DISP-6-3` is not in it, and **`REG-C-17` is**. The identifier-change
test is inventoried once, on the register row that demands it. §6.3 itself
demands a modelling decision — which identifier is authoritative — and no argv
decides that. Adding a command item here would duplicate `REG-C-17`'s obligation
and would fail the pinned-set assertion; both readings agree.

**Granularity.** One `-ACCEPTANCE` item quoting the full text is the ledger-wide
convention across all 169 canonical rows; multi-sentence acceptance texts are
never split by sentence. The two sentences here are one design decision stated
positively and then negatively, so splitting them would produce two items with
identical proof mode and scope.

**`TYPED_APPROVAL` — unrepresentable.** The row's only approval requirement is
`APR-DISP-6-3-01`, a `DELEGATED_ARTIFACT_APPROVAL`; ledger-wide, all 123 such
requirements are covered by zero `TYPED_APPROVAL` items, because that record
carries its own persisted clean `REVIEWER`-role review (goal L595-598). Note
specifically that the `DOMAIN_EXPERT_ACCEPTANCE` / "Entity-data authority"
requirement relevant to this subject matter sits on `REG-C-17`, together with its
own paired `TYPED_APPROVAL` evidence item — so that obligation is inventoried,
just not on this row (see this component's `APPROVAL` review, which decides that
question independently).

**No negative-proof item.** `REQUIRED_NOW` active control, `rejection_record:
null`, defers nothing; `current_no_implementation_proof` is vacuous for such a
row.

**`evidence_refs`.** Two references, both re-verified against current bytes:
`EV-DISP-6-3-SOURCE` (`UTF8_LINE_SPAN` L363-365, digest `1229dceb…`, captured
`2026-08-13T02:49:11Z`) and `EV-DISP-6-3-SPEC-DRAFT` (`FILE_BYTES` over
`docs/specs/equity-os-s17-entity-security-master-actions.md`, digest
`dbb6b860…`, captured `2026-08-15T07:13:28Z`). Both resolve to live repository
paths, so the validator's per-run digest check (`:210-233`) passes, and both
captures precede this review's timestamp.

**Framing check.** "Current proof satisfying: ### 6.3 …" reads correctly for an
affirmative design mandate.

**`verification_command` observation, not a finding.** `mode: UNRESOLVED`,
permitted during initial ledger construction (goal L498-500). Because this row is
outside the pinned command-proof population, its eventual resolution is
`NOT_APPLICABLE` with its own evidenced reviewer attestation — a future
obligation on `verification_command`, not a missing `required_evidence` item.

**Residuals.** None.

---

**verdict: CLEAN**

`required_evidence` for `DISP-6-3` is complete at the input bytes pinned above.
This review satisfies no evidence item and authorizes no delivery, gate,
approval, or transition.
