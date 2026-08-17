# Inventory review — DISP-6-9 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-6-9` |
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
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"bd66104f1f5d50f20c3d0e191ea675db1e6cbc4dc93c5469635b8f66ff054354","digest_mode":"UTF8_LINE_SPAN","end_line":398,"evidence_ref_id":"EV-DISP-6-9-SOURCE","path":"docs/blueprint/funda-third-order-review-disposition-report.md","scope":"Exact authoritative source occurrence for DISP-6-9","start_line":396},{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"f6158ce7d04109cbb954a4113bd43046428028abd30c34f0652ca3aae52ccf8e","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-DISP-6-9-SPEC-DRAFT","path":"docs/specs/equity-os-s11-run-manifest-cutoff-reproducibility.md","scope":"Current draft specification bytes for DISP-6-9","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: ### 6.9 Bit-exact computation is not universal\n\nThe review correctly separates computation from narrative, but “bit-exact” should apply only to operators designed for exact replay. Floating-point, optimization, and stochastic calculations require declared tolerances, pinned environments, and stored seeds as applicable.","evidence_id":"REQ-DISP-6-9-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"DISP-6-9 acceptance and delivery scope","status":"UNRESOLVED"},{"approval_ids":[],"description":"Reproducible command result proving the current DISP-6-9 acceptance obligation","evidence_id":"REQ-DISP-6-9-COMMAND-PROOF","evidence_ref_ids":[],"evidence_type":"COMMAND_RESULT","proof_mode":"COMMAND","scope":"DISP-6-9 command proof","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (recorder recomputes after
Phase A, recording design r2 §3.4):

- `reviewed_input_sha256` (pre-record): `db44dad35c6af1da83fa0a3219476e046fcbe6e0690babcb30dbb94f18745941`
- `reviewed_inventory_sha256` (pre-record): `03261f8acd1354cf8160260b065eef0b00364a36dcb7bd6376cb5434d406979b`

## Scope of this decision

Completeness of `required_evidence` only (goal L492-494). Both items are
legitimately `UNRESOLVED` with empty `evidence_ref_ids` (goal L484).

## The source clause, re-read this round

Disposition report L396-398:

> ### 6.9 Bit-exact computation is not universal
>
> The review correctly separates computation from narrative, but "bit-exact"
> should apply only to operators designed for exact replay. Floating-point,
> optimization, and stochastic calculations require declared tolerances, pinned
> environments, and stored seeds as applicable.

`text_digest` and `EV-DISP-6-9-SOURCE.content_sha256` both recomputed over the
normalized span → `bd66104f…`, matching.

## Reasoning

**Two items, and the split is exactly where the clause splits.** `DISP-6-9` is
one of the 25 rows in the pinned command-proof population
(`EXPECTED_COMMAND_PROOF_COMPONENTS`, `validate_ledger_structural.py:2635-2649`),
so completeness has a documentation half and an enforcement half:

1. `REQ-DISP-6-9-ACCEPTANCE` — `ARTIFACT` / `CONTENT_HASH`, quoting the whole
   clause. This covers the **classification** obligation: which operators are
   designed for exact replay, and the declaration of tolerances, pinned
   environments, and seeds. A declaration is by definition a document artifact,
   and it must exist before any test can check against it.
2. `REQ-DISP-6-9-COMMAND-PROOF` — `COMMAND_RESULT` / `COMMAND`, scope "DISP-6-9
   command proof". This covers the **behavioural** obligation: exact-class
   operators actually replay exactly, tolerance-class outputs actually fall
   within the declared bounds, and stochastic operators actually reproduce from
   stored seeds. Nothing but a run establishes that.

The clause's own phrase "as applicable" is what makes both necessary: which
requirement applies to which operator is a declared fact (item 1), and whether
the operator honours it is an observed fact (item 2). An inventory with only
item 1 would let a spec declare a tolerance no code respects; only item 2 would
leave the tolerance undeclared and therefore untestable.

**Cross-check against the register.** `C-16`'s acceptance — "Exact-class
operators replay exactly; floating-point/optimization outputs meet declared
tolerances; stochastic operators store seeds and test distributions" — contains
both halves in the same sentence, and `REG-C-16` and `REG-C-08` are *both* in the
pinned command-proof set alongside this row. So three components in this clause's
cone carry command obligations, which is consistent rather than duplicative:
`REG-C-08` proves the minimum calculation set, `REG-C-16` proves the layered
replay policy, and `DISP-6-9` proves the specific correction that bit-exactness
is not universal.

**A consequence worth recording for later rounds.** Because this row carries a
`proof_mode == "COMMAND"` requirement, its `verification_command` may **not**
resolve to `NOT_APPLICABLE`: `validate_ledger_structural.py:2335-2340` asserts, in
the `NOT_APPLICABLE` branch of `assert_complete_proof`, that no evidence
requirement has `proof_mode == "COMMAND"`. It must reach `mode: "COMMANDS"` with
`verification_result` entries whose `output_ref_ids` cover this item's evidence
refs (`:2328-2334`). Its current `mode: UNRESOLVED` is permitted only "during
initial ledger construction" (goal L498-500). A future obligation on
`verification_command`, not a missing `required_evidence` item.

**`TYPED_APPROVAL` — unrepresentable, and the contrast that proves it is
deliberate.** The row's only approval requirement is `APR-DISP-6-9-01`, a
`DELEGATED_ARTIFACT_APPROVAL`; ledger-wide all 123 such requirements are covered
by zero `TYPED_APPROVAL` items (goal L595-598). The instructive comparison is
`DISP-G-1`, which shares this row's `C-08`/`C-16` register scope but *does* carry
an `ANALYST_ACCEPTANCE` requirement and a matching
`REQ-DISP-G-1-ANALYST_ACCEPTANCE-02` `TYPED_APPROVAL` item — because `G-1`'s third
guarantee is about approved narrative bytes. §6.9's first sentence explicitly
hands the narrative side back to that separation, so no analyst-approval evidence
item belongs here.

**No negative "no-implementation" proof.** `REQUIRED_NOW` active control,
`rejection_record: null`, not among the 13 `first_release_deferral` rows or
`DISP-R-1`.

**Framing check.** "Current proof satisfying: ### 6.9 …" reads correctly for an
affirmative requirement on active compute scope.

**`evidence_refs`.** Two references, both re-verified against current bytes:
`EV-DISP-6-9-SOURCE` (`UTF8_LINE_SPAN` L396-398, digest `bd66104f…`) and
`EV-DISP-6-9-SPEC-DRAFT` (`FILE_BYTES` over
`docs/specs/equity-os-s11-run-manifest-cutoff-reproducibility.md`, digest
`f6158ce7…`). Both resolve to live repository paths. I note one factual
difference from the rest of the batch and record it as verified rather than
anomalous: this row's `SPEC-DRAFT` `captured_at` is `2026-08-13T02:49:11Z`, the
original capture, whereas the other ten rows' draft references were recaptured at
`2026-08-15T07:13:28Z` during the HR-0004 transaction. That is consistent with
that transaction's current-digest repair applying only to references whose bytes
had gone stale; this one had not, its digest verifies against current bytes, and
its capture still precedes this review's timestamp.

**Residuals.** None.

---

**verdict: CLEAN**

`required_evidence` for `DISP-6-9` is complete at the input bytes pinned above:
a declaration obligation and a replay obligation, matching the clause's two
halves. This review satisfies no evidence item and authorizes no delivery, gate,
approval, or transition.
