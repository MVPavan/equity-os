# Inventory review — DISP-G-1 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-G-1` |
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
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"ea24b6386565704043e6a7fc2ff923d2c514d23384dd07a684420bc1fa0c4572","digest_mode":"UTF8_LINE_SPAN","end_line":59,"evidence_ref_id":"EV-DISP-G-1-SOURCE","path":"docs/blueprint/funda-third-order-review-disposition-report.md","scope":"Exact authoritative source occurrence for DISP-G-1","start_line":47},{"captured_at":"2026-08-15T07:13:28Z","content_sha256":"9b14f5f327a9ff623cb41c823ab3eeec2d14f2f3ee05b8506313fbb28e83f458","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-DISP-G-1-SPEC-DRAFT","path":"docs/specs/equity-os-s06-output-materiality-falsifiers.md","scope":"Current draft specification bytes for DISP-G-1","start_line":null},{"captured_at":"2026-08-13T04:19:57Z","content_sha256":"9b14f5f327a9ff623cb41c823ab3eeec2d14f2f3ee05b8506313fbb28e83f458","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-DISP-G-1-S06-I7-CURRENT-S06","path":"docs/specs/equity-os-s06-output-materiality-falsifiers.md","scope":"Exact current S06 bytes adjudicated for S06-I7 on DISP-G-1","start_line":null},{"captured_at":"2026-08-13T04:19:57Z","content_sha256":"61d74f4b8b9248a75ff48e4508b1b58fb79b884acbbc859328111bb3814f2113","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-DISP-G-1-S06-I7-R4","path":"docs/goals/reviews/specs/equity-os-s04-s06-r4.md","scope":"Final ordinary r4 review report finding S06-I7 for DISP-G-1","start_line":null},{"captured_at":"2026-08-13T04:19:57Z","content_sha256":"da3ef87f32646fdb3e0f576086aba5070eee0aee3b115f53cb6b40579999e26a","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-DISP-G-1-S06-I7-ADJUDICATION","path":"docs/goals/reviews/specs/equity-os-s04-s06-adjudication.md","scope":"Post-cap adjudication upholding S06-I7 and its exact cone for DISP-G-1","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: ### G-1 — Narrative reproducibility\n\n**Disposition: Accept with modification.**\n\nThe sentence “the report is reproducible from frozen inputs and registered versions” is ambiguous. It may be read as bit-identical regeneration, which is not a safe guarantee for an LLM-generated narrative. However, the gate is not permanently unpassable because the exact approved artifact can be stored and retrieved by hash.\n\nUse three separate guarantees:\n\n1. **Deterministic calculations:** replay under frozen inputs, code, runtime, and operator policy. Exact-class accounting operators should match exactly; floating-point or optimization operators should remain within declared tolerances; stochastic operators require a stored seed and distribution checks.\n2. **Evidence package:** exactly reconstructable from registered source, fact, claim, and cutoff identifiers.\n3. **Narrative:** the approved published bytes are immutable and bound to a content hash; a later regeneration must be audited against the same approved claim set but need not be text-identical.\n\nThis correction belongs in the output contract, run manifest, and Phase 1 gate.","evidence_id":"REQ-DISP-G-1-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"DISP-G-1 acceptance and delivery scope","status":"UNRESOLVED"},{"approval_ids":["APR-DISP-G-1-02"],"description":"Typed ANALYST_ACCEPTANCE proof for G-1 analyst acceptance","evidence_id":"REQ-DISP-G-1-ANALYST_ACCEPTANCE-02","evidence_ref_ids":[],"evidence_type":"ANALYST","proof_mode":"TYPED_APPROVAL","scope":"G-1 analyst acceptance","status":"UNRESOLVED"},{"approval_ids":[],"description":"Reproducible command result proving the current DISP-G-1 acceptance obligation","evidence_id":"REQ-DISP-G-1-COMMAND-PROOF","evidence_ref_ids":[],"evidence_type":"COMMAND_RESULT","proof_mode":"COMMAND","scope":"DISP-G-1 command proof","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (recorder recomputes after
Phase A, recording design r2 §3.4):

- `reviewed_input_sha256` (pre-record): `de150af438f6f0bd491f0a622f5a20f14ebc87528a67adc2ca0674b97332f16e`
- `reviewed_inventory_sha256` (pre-record): `993b89e3215cb2d075f94c11b5711a180ffb39651a148a63c034806f4568e84b`

## Scope of this decision

Completeness of `required_evidence` only (goal L492-494). All three items are
legitimately `UNRESOLVED` with empty `evidence_ref_ids` (goal L484).

## The source clause, re-read this round

Disposition report L47-59 — `### G-1 — Narrative reproducibility`, disposition
"Accept with modification", prescribing three separate guarantees
(1. deterministic calculations replay under frozen inputs/code/runtime/operator
policy, with exact/tolerance/seeded classes; 2. the evidence package is exactly
reconstructable from registered identifiers; 3. the approved published bytes are
immutable and content-hash bound, and a regeneration is audited against the same
approved claim set without needing to be text-identical), and closing "This
correction belongs in the output contract, run manifest, and Phase 1 gate."

`text_digest` and `EV-DISP-G-1-SOURCE.content_sha256` both recomputed over the
normalized L47-59 span → `ea24b638…`, matching.

## Reasoning

**Three `required_evidence` items — the richest list in the batch, and each maps
to a distinct guarantee.**

1. `REQ-DISP-G-1-ACCEPTANCE` — `ARTIFACT` / `CONTENT_HASH`, quoting the whole
   clause including all three guarantees. This carries the **declaration**
   obligation: the output contract and run manifest must *say* which guarantee
   applies where, and the acceptance text pins the exact wording so it cannot
   drift.
2. `REQ-DISP-G-1-ANALYST_ACCEPTANCE-02` — `ANALYST` / `TYPED_APPROVAL`, scope
   "G-1 analyst acceptance", `approval_ids: ["APR-DISP-G-1-02"]`. This carries
   **guarantee 3**: "the approved published bytes are immutable" presupposes an
   approval act, and goal L487-489 requires that analyst evidence "always uses
   `TYPED_APPROVAL` and the typed approval/human-review path, never a fabricated
   shell command". The item names its component-local approval requirement, as
   goal L484-487 demands.
3. `REQ-DISP-G-1-COMMAND-PROOF` — `COMMAND_RESULT` / `COMMAND`, scope "G-1
   command proof". This carries **guarantees 1 and 2**: whether exact-class
   operators replay exactly, whether tolerance-class outputs fall inside their
   declared bounds, and whether an evidence package actually reconstructs from
   registered identifiers are all observed facts about running code.
   `DISP-G-1` is in the pinned command-proof population
   (`EXPECTED_COMMAND_PROOF_COMPONENTS`, `validate_ledger_structural.py:2635-2649`).

**Is any guarantee unrepresented?** No — the mapping above is total, and it is
also the reason the list is three items rather than one: unlike every other row
in this batch, `G-1` demands three *different kinds* of proof (a document, a
human approval, and a program run), and the contract's proof modes are exactly
that three-way distinction. Collapsing them would put a human approval behind an
exit code, which goal L487-489 forbids by name.

**Is any item redundant?** I checked the reverse direction too. Dropping the
`ANALYST` item would leave `APR-DISP-G-1-02` with no evidence obligation, which
would break the ledger-wide 1:1 pairing (verified: all 13 `ANALYST_ACCEPTANCE`
requirements in the ledger are covered by a `TYPED_APPROVAL` item, and so are all
6 `DOMAIN_EXPERT_ACCEPTANCE`, 6 `CAPACITY_COMMITMENT`, 6 `BUDGET_APPROVAL`, 5
`DATA_RIGHTS_APPROVAL`, 5 `LEGAL_REVIEW`, 3 `NAMED_OWNER_COMMITMENT`, and the
single `MEMORY_PROMOTION`, `DISTRIBUTION_APPROVAL`, and `REGULATORY_REVIEW`).
Dropping the command item would leave guarantees 1 and 2 asserted but never
exercised. Dropping the acceptance item would leave the classification
undeclared. All three are load-bearing.

**No `TYPED_APPROVAL` item for `APR-DISP-G-1-01`.** That is the delegated artifact
approval, and ledger-wide all 123 `DELEGATED_ARTIFACT_APPROVAL` requirements are
covered by zero `TYPED_APPROVAL` items, because that record "carries the
persisted clean `REVIEWER`-role review" itself (goal L595-598). So the row's two
approval requirements are correctly represented by exactly one evidence item.

**A consequence worth recording for later rounds.** Because this row carries a
`proof_mode == "COMMAND"` requirement, its `verification_command` may **not**
resolve to `NOT_APPLICABLE` (`validate_ledger_structural.py:2335-2340`); it must
reach `mode: "COMMANDS"` with results whose `output_ref_ids` cover that item's
evidence refs (`:2328-2334`). Its current `mode: UNRESOLVED` is permitted only
"during initial ledger construction" (goal L498-500).

**No negative "no-implementation" proof.** `REQUIRED_NOW` active control,
`rejection_record: null`, not among the 13 `first_release_deferral` rows or
`DISP-R-1`.

**Framing check.** "Current proof satisfying: ### G-1 — Narrative reproducibility
… " reads correctly for an accept-with-modification finding on active scope.

**`evidence_refs` — five objects, all re-verified against current bytes, and the
last three are not an inventory gap.**

| ID | Mode | Target | Verified |
|---|---|---|---|
| `EV-DISP-G-1-SOURCE` | `UTF8_LINE_SPAN` L47-59 | disposition report | `ea24b638…` matches |
| `EV-DISP-G-1-SPEC-DRAFT` | `FILE_BYTES` | `docs/specs/equity-os-s06-output-materiality-falsifiers.md` | `9b14f5f3…` matches |
| `EV-DISP-G-1-S06-I7-CURRENT-S06` | `FILE_BYTES` | same S06 file | `9b14f5f3…` matches |
| `EV-DISP-G-1-S06-I7-R4` | `FILE_BYTES` | `docs/goals/reviews/specs/equity-os-s04-s06-r4.md` | `61d74f4b…` matches |
| `EV-DISP-G-1-S06-I7-ADJUDICATION` | `FILE_BYTES` | `docs/goals/reviews/specs/equity-os-s04-s06-adjudication.md` | `da3ef87f…` matches |

The last three are linked from `open_findings[0].evidence_ref_ids`, not from any
`required_evidence` item, and that is correct: they evidence the `S06-I7`
finding, which is not an acceptance obligation. The contract requires only the
converse direction — a satisfied item has nonempty component-local refs (goal
L484-485). All five `captured_at` values precede this review's timestamp.

**Residuals.** None. The `S06-I7` block remains open and this review neither
resolves nor narrows it.

---

**verdict: CLEAN**

`required_evidence` for `DISP-G-1` is complete at the input bytes pinned above:
a declaration item, a typed analyst-approval item, and a command item, one per
guarantee class. This review satisfies no evidence item and authorizes no
delivery, gate, approval, or transition.
