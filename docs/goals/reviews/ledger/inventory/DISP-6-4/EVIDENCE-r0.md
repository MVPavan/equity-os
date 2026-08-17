# Inventory review — DISP-6-4 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-6-4` |
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
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"25f209688a463141578b299c3781bb9fc36837b5e0e8acc331ae9a1a6fb33afc","digest_mode":"UTF8_LINE_SPAN","end_line":369,"evidence_ref_id":"EV-DISP-6-4-SOURCE","path":"docs/blueprint/funda-third-order-review-disposition-report.md","scope":"Exact authoritative source occurrence for DISP-6-4","start_line":367},{"captured_at":"2026-08-15T07:13:28Z","content_sha256":"4948d0f84240cd58b107da1272ed2b90a386bc3fb9ebb6228faac8b98be9c483","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-DISP-6-4-SPEC-DRAFT","path":"docs/specs/equity-os-s20-memory-benchmark-gbrain.md","scope":"Current draft specification bytes for DISP-6-4","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: ### 6.4 D-02 answers a present adoption question\n\nA small-corpus benchmark may correctly show that a simpler store is sufficient. Future triggers should reopen the question; the benchmark should not be cancelled on the assumption that a larger future corpus might behave differently.","evidence_id":"REQ-DISP-6-4-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"DISP-6-4 acceptance and delivery scope","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (recorder recomputes after
Phase A, recording design r2 §3.4):

- `reviewed_input_sha256` (pre-record): `9bff37a60e123d84e5b0fc7acfc34c60c1c4b1e2b514b0f8b1747346162b9b48`
- `reviewed_inventory_sha256` (pre-record): `91a009d4a69991f370a7e53d7a4f22ec33d743b783c6478b14b1f5948e25fc61`

## Scope of this decision

Completeness of `required_evidence` only (goal L492-494). The single item is
legitimately `UNRESOLVED` with empty `evidence_ref_ids` (goal L484).

## The source clause, re-read this round

Disposition report L367-369:

> ### 6.4 D-02 answers a present adoption question
>
> A small-corpus benchmark may correctly show that a simpler store is
> sufficient. Future triggers should reopen the question; the benchmark should
> not be cancelled on the assumption that a larger future corpus might behave
> differently.

`text_digest` and `EV-DISP-6-4-SOURCE.content_sha256` both recomputed over the
normalized span → `25f20968…`, matching.

## Reasoning

**Obligation decomposition.** Three assertions: (a) a small-corpus result showing
a simpler store suffices is a *valid* result for the present adoption question;
(b) future triggers reopen the question; (c) the benchmark is not cancelled on
future-scale speculation. All three are statements about how the S20 artifact
must frame the benchmark and its reopening, and all three are provable by content
hash over that artifact. The single `REQ-DISP-6-4-ACCEPTANCE` item
(`ARTIFACT`/`CONTENT_HASH`) quotes the whole clause and covers all three.

**The candidate omission specific to this row: a re-evaluation-control item.**
§6.4 says "Future triggers should reopen the question", and the ledger *does*
have a dedicated obligation shape for exactly that — `REQ-<CID>-REEVALUATION-CONTROL`
— so this is a real question rather than a formality. It is not an omission here:
those items exist on exactly eight rows, all of `kind == "scale_trigger"`
(`SCALE-SQLITE-01..04` with `disposition_refs == ["R-5"]` and
`SCALE-WORKFLOW-01..04` with `["M-5"]`), and each corresponds to a **named,
enumerated trigger** drawn from findings R-5 and M-5. §6.4 names no trigger; it
says triggers "should reopen the question" and leaves their enumeration to `D-02`,
whose register acceptance already ends "re-evaluation triggers are precommitted".
There is no memory-store `scale_trigger` row to attach a control to, and inventing
a `REEVALUATION-CONTROL` item on a `disposition_item` would be the only such
instance in the ledger. The obligation is inventoried where it is enumerable —
`REG-D-02` and `REG-D-05` — and represented here through the acceptance text.

**`COMMAND_RESULT` — absent, and correctly so.** `DISP-6-4` is not in
`EXPECTED_COMMAND_PROOF_COMPONENTS` (`validate_ledger_structural.py:2635-2649`),
and neither is `REG-D-02` or `REG-D-05`. That is coherent: the benchmark's
mechanical obligations are dormant — both register rows are `Deferred` /
`CONDITIONAL_UNACTIVATED` — and §6.4 does not demand that the benchmark be *run*
now, only that it not be cancelled and that its reopening be precommitted. There
is no argv that decides "this was not cancelled". Adding a command item would
both fail the pinned-set assertion and assert an obligation the clause does not
make.

**`TYPED_APPROVAL` — unrepresentable.** The row's only approval requirement is
`APR-DISP-6-4-01`, a `DELEGATED_ARTIFACT_APPROVAL`; ledger-wide, all 123 such
requirements are covered by zero `TYPED_APPROVAL` items, because that record
carries its own persisted clean `REVIEWER`-role review (goal L595-598). The
activation authority relevant to this subject — `PRODUCT_OWNER_DECISION` /
"Product owner authorized to activate deferred blueprint scope", plus "Product
owner for memory adoption" — sits on `REG-D-02` and `REG-D-05` (see this
component's `APPROVAL` review), not here.

**No negative "no-implementation" proof — checked, because this row is about
dormant scope.** Those items belong to the 13 `first_release_deferral` rows and
`DISP-R-1`. `DISP-6-4` is not a deferral row: it is a `REQUIRED_NOW` active
control *about* deferred scope, with `rejection_record: null`, so
`current_no_implementation_proof` is vacuous for it and the
`NO_IMPLEMENTATION_REQUIREMENT_MAP` (`validate_ledger_structural.py:2671`) does
not name it. The dormancy of `D-02`/`D-05` is proved elsewhere, by the
`ACTIVE_NEGATIVE_CONTROL` row `PG-1-11`, whose related register IDs include both.

**Framing check — the one framing risk on this row.** The description reads
"Current proof satisfying: ### 6.4 D-02 answers a present adoption question …".
The r0 program-level evidence review flagged that positively framed "current
proof satisfying <deferred capability>" descriptions invert the boundary on
deferral rows. This row is adjacent to that pathology because its subject matter
*is* deferred — so I checked it rather than assuming. It does not reproduce:
what must be proven is not that a benchmark ran, but that the S20 artifact
carries the non-cancellation framing and precommitted triggers, which is a
present, satisfiable obligation. The framing is correct.

**`evidence_refs`.** Two references, both re-verified against current bytes:
`EV-DISP-6-4-SOURCE` (`UTF8_LINE_SPAN` L367-369, digest `25f20968…`, captured
`2026-08-13T02:49:11Z`) and `EV-DISP-6-4-SPEC-DRAFT` (`FILE_BYTES` over
`docs/specs/equity-os-s20-memory-benchmark-gbrain.md`, digest `4948d0f8…`,
captured `2026-08-15T07:13:28Z`). Both resolve to live repository paths and both
captures precede this review's timestamp. Note the draft evidence points at S20,
not at S19 — consistent with S20 being the artifact that carries the obligation,
even though `applicable_spec_ids` lists both.

**`verification_command` observation, not a finding.** `mode: UNRESOLVED`,
permitted during initial ledger construction (goal L498-500); outside the pinned
command-proof population, so the eventual resolution is `NOT_APPLICABLE` with its
own evidenced reviewer attestation.

**Residuals.** None.

---

**verdict: CLEAN**

`required_evidence` for `DISP-6-4` is complete at the input bytes pinned above.
This review satisfies no evidence item, activates no deferred scope, and
authorizes no delivery, gate, approval, or transition.
