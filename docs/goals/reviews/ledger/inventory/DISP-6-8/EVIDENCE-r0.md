# Inventory review — DISP-6-8 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-6-8` |
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
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"a89f9e82f82755171c1c7daaa8977390c37aa800f0ce8e085f9506d0f86d2323","digest_mode":"UTF8_LINE_SPAN","end_line":394,"evidence_ref_id":"EV-DISP-6-8-SOURCE","path":"docs/blueprint/funda-third-order-review-disposition-report.md","scope":"Exact authoritative source occurrence for DISP-6-8","start_line":383},{"captured_at":"2026-08-15T07:13:28Z","content_sha256":"3f3e371f7a71683c3befed5e6f0d6daff4bd2a5f630ad4aa9b62c31b1070885e","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-DISP-6-8-SPEC-DRAFT","path":"docs/specs/equity-os-s05-discovery-company-vertical-slice.md","scope":"Current draft specification bytes for DISP-6-8","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: ### 6.8 The repaired measurement design no longer fits three quarters\n\nThe review retains a one-company, three-quarter slice while also requiring a manual baseline on quarters not reused for assisted runs. Because B-02 requires three assisted incremental updates, these conditions cannot all hold simultaneously. The minimum internally consistent slice is:\n\n```text\nQuarter 0: manual baseline + approved bootstrap thesis\nQuarter 1: assisted incremental update 1\nQuarter 2: assisted incremental update 2\nQuarter 3: assisted incremental update 3\n```\n\nThe revised register therefore uses four consecutive quarters. This adds one quarter of source material but removes a fundamental experiment-design contradiction.","evidence_id":"REQ-DISP-6-8-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"DISP-6-8 acceptance and delivery scope","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (recorder recomputes after
Phase A, recording design r2 §3.4):

- `reviewed_input_sha256` (pre-record): `4ac020791efc6d89879a53bf4e62669ee70417c044f87dcdf4f99572125221d9`
- `reviewed_inventory_sha256` (pre-record): `af8c75ce636c75f602dabd8666dc5e4d09b4821a63b25c540c31d3d318e9de01`

## Scope of this decision

Completeness of `required_evidence` only (goal L492-494). The single item is
legitimately `UNRESOLVED` with empty `evidence_ref_ids` (goal L484).

## The source clause, re-read this round

Disposition report L383-394 (twelve lines, including the fenced quarter table):

> ### 6.8 The repaired measurement design no longer fits three quarters
>
> … The minimum internally consistent slice is:
> `Quarter 0: manual baseline + approved bootstrap thesis`,
> `Quarter 1..3: assisted incremental update 1..3`.
> The revised register therefore uses four consecutive quarters. This adds one
> quarter of source material but removes a fundamental experiment-design
> contradiction.

`text_digest` and `EV-DISP-6-8-SOURCE.content_sha256` both recomputed over the
normalized L383-394 span → `a89f9e82…`, matching. The fenced block is inside the
span and therefore inside both digests.

## Reasoning

**Obligation decomposition.** Three: (a) the vertical slice uses four consecutive
quarters; (b) Quarter 0 is the manual baseline plus approved bootstrap thesis and
Quarters 1–3 are the three assisted updates; (c) one additional quarter of source
material is acquired. The single `REQ-DISP-6-8-ACCEPTANCE` item
(`ARTIFACT`/`CONTENT_HASH`) quotes the whole clause, fenced table included, so
the exact quarter assignment is inside the obligation's own description and
cannot drift.

**Obligation (c) is the one worth interrogating — is a source-availability proof
missing?** "This adds one quarter of source material" is a statement about the
world, not about a document, and `A-02`'s acceptance independently requires
"source package exists for all quarters". So an `ARTIFACT`/`CONTENT_HASH` item
over the spec text might look insufficient. It is not, for two reasons. First,
the obligation §6.8 creates is the *design* — that the slice be four quarters
long — and it discharges into S05's text and the register's; whether the fourth
quarter's filings actually exist is `A-02`'s acceptance, inventoried on
`REG-A-02`. Second, an evidence item here asserting source availability would
duplicate `REG-A-02`'s obligation on a row that does not own the discovery-company
selection. The `EVIDENCE` review's question is whether *this clause's* demands are
enumerated, and the acquisition consequence is a consequence of `A-02`'s
selection, not an independent demand of §6.8.

**`COMMAND_RESULT` — absent, and correctly so.** `DISP-6-8` is not in
`EXPECTED_COMMAND_PROOF_COMPONENTS` (`validate_ledger_structural.py:2635-2649`),
and neither is `REG-A-02` nor `REG-B-02` — the whole cone of this clause is
outside the pinned command-proof population. That is coherent: what §6.8 requires
is that a design be internally consistent, and consistency between a quarter count
and an update count is established by reading the register and spec, not by
running a program. The two `6.x` rows that *are* in the pinned set (`DISP-6-6`,
`DISP-6-9`) both assert runtime properties; this one asserts an experiment design.

**`TYPED_APPROVAL` — unrepresentable.** The row's only approval requirement is
`APR-DISP-6-8-01`, a `DELEGATED_ARTIFACT_APPROVAL`; ledger-wide, all 123 such
requirements are covered by zero `TYPED_APPROVAL` items (goal L595-598). Note the
clause's phrase "approved bootstrap thesis" — the approval it refers to is
`REG-B-02`'s `ANALYST_ACCEPTANCE`, which carries its own paired `TYPED_APPROVAL`
item on that row; it is a description of what Quarter 0 produces, not a new
obligation here (see this component's `APPROVAL` review).

**No negative "no-implementation" proof.** `REQUIRED_NOW` active control,
`rejection_record: null`, not among the 13 `first_release_deferral` rows or
`DISP-R-1`, and not named by the `NO_IMPLEMENTATION_REQUIREMENT_MAP`
(`validate_ledger_structural.py:2671`).

**Framing check.** "Current proof satisfying: ### 6.8 The repaired measurement
design no longer fits three quarters …" reads correctly: the proof is that the
current design *is* the four-quarter one, which is an affirmative, presently
satisfiable obligation.

**`evidence_refs`.** Two references, both re-verified against current bytes:
`EV-DISP-6-8-SOURCE` (`UTF8_LINE_SPAN` L383-394, digest `a89f9e82…`, captured
`2026-08-13T02:49:11Z`) and `EV-DISP-6-8-SPEC-DRAFT` (`FILE_BYTES` over
`docs/specs/equity-os-s05-discovery-company-vertical-slice.md`, digest
`3f3e371f…`, captured `2026-08-15T07:13:28Z`). Both resolve to live repository
paths and both captures precede this review's timestamp. The `UTF8_LINE_SPAN`
mode is the right choice for a twelve-line span inside a large document, and its
recomputation over the fenced block matched exactly.

**`verification_command` observation, not a finding.** `mode: UNRESOLVED`,
permitted during initial ledger construction (goal L498-500); outside the pinned
command-proof population, so the eventual resolution is `NOT_APPLICABLE` with its
own evidenced reviewer attestation.

**Residuals.** None.

---

**verdict: CLEAN**

`required_evidence` for `DISP-6-8` is complete at the input bytes pinned above.
This review satisfies no evidence item and authorizes no delivery, gate,
approval, or transition.
