# Inventory review — DISP-6-2 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-6-2` |
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
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"295d805b384dfd06599d314799fa46854da59b2a85f8bcff60219cbc74f66d05","digest_mode":"UTF8_LINE_SPAN","end_line":361,"evidence_ref_id":"EV-DISP-6-2-SOURCE","path":"docs/blueprint/funda-third-order-review-disposition-report.md","scope":"Exact authoritative source occurrence for DISP-6-2","start_line":359},{"captured_at":"2026-08-15T07:13:28Z","content_sha256":"9b14f5f327a9ff623cb41c823ab3eeec2d14f2f3ee05b8506313fbb28e83f458","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-DISP-6-2-SPEC-DRAFT","path":"docs/specs/equity-os-s06-output-materiality-falsifiers.md","scope":"Current draft specification bytes for DISP-6-2","start_line":null},{"captured_at":"2026-08-13T04:19:57Z","content_sha256":"9b14f5f327a9ff623cb41c823ab3eeec2d14f2f3ee05b8506313fbb28e83f458","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-DISP-6-2-S06-I7-CURRENT-S06","path":"docs/specs/equity-os-s06-output-materiality-falsifiers.md","scope":"Exact current S06 bytes adjudicated for S06-I7 on DISP-6-2","start_line":null},{"captured_at":"2026-08-13T04:19:57Z","content_sha256":"61d74f4b8b9248a75ff48e4508b1b58fb79b884acbbc859328111bb3814f2113","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-DISP-6-2-S06-I7-R4","path":"docs/goals/reviews/specs/equity-os-s04-s06-r4.md","scope":"Final ordinary r4 review report finding S06-I7 for DISP-6-2","start_line":null},{"captured_at":"2026-08-13T04:19:57Z","content_sha256":"da3ef87f32646fdb3e0f576086aba5070eee0aee3b115f53cb6b40579999e26a","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-DISP-6-2-S06-I7-ADJUDICATION","path":"docs/goals/reviews/specs/equity-os-s04-s06-adjudication.md","scope":"Post-cap adjudication upholding S06-I7 and its exact cone for DISP-6-2","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: ### 6.2 Materiality is not only a financial-statement threshold\n\nThe proposed percentage rule is one component. Governance, guidance, thesis relevance, and source conflict must also be represented.","evidence_id":"REQ-DISP-6-2-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"DISP-6-2 acceptance and delivery scope","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (recorder recomputes after
Phase A, recording design r2 §3.4):

- `reviewed_input_sha256` (pre-record): `0e2fd7e9c2cf4105c75c87f377dba0054f947578effd9bd3a1db44c5c063b057`
- `reviewed_inventory_sha256` (pre-record): `ec1606232a53b41be7848bffc59266c7040f8c491d8014626c05dfc30b7a38f2`

## Scope of this decision

Completeness of `required_evidence` only (goal L492-494). The single item is
legitimately `UNRESOLVED` with empty `evidence_ref_ids` (goal L484).

## The source clause, re-read this round

Disposition report L359-361:

> ### 6.2 Materiality is not only a financial-statement threshold
>
> The proposed percentage rule is one component. Governance, guidance, thesis
> relevance, and source conflict must also be represented.

`text_digest` and `EV-DISP-6-2-SOURCE.content_sha256` both recomputed over the
normalized span → `295d805b…`, matching.

## Reasoning

**Obligation decomposition — a four-element list, deliberately checked.** §6.2 is
the clause in this batch most likely to demand more than one proof, because it
enumerates four things that "must also be represented": governance, guidance,
thesis relevance, source conflict. I considered whether each element should be
its own `required_evidence` item. It should not, for two reasons that are
checkable rather than stylistic:

1. *The elements are components of one artifact obligation, not four separate
   proofs.* What is provable is that the materiality policy in S06 represents all
   four; there is no independent artifact for "governance materiality". A single
   `ARTIFACT`/`CONTENT_HASH` item over the acceptance text is the exact shape of
   that obligation, and its `description` quotes all four elements verbatim so
   nothing is lost from the record.
2. *The ledger never splits an enumerated acceptance text by element.* Verified
   across all 169 canonical rows: each carries exactly one
   `REQ-<component_id>-ACCEPTANCE` item quoting the full text, including rows
   whose acceptance text is a multi-item bulleted list (e.g. `DISP-G-2`'s
   five-bullet list, `DISP-M-5`'s bulleted rework requirements). Splitting here
   would be a unique deviation, and the resulting per-element items would have no
   distinct proof mode or scope.

**`COMMAND_RESULT` — absent, and correctly so.** `DISP-6-2` is not in
`EXPECTED_COMMAND_PROOF_COMPONENTS` (`validate_ledger_structural.py:2635-2649`).
That is the right answer semantically as well: the mechanical obligation implied
by materiality — `A-10`'s "validator test cases approved" — is inventoried as a
command proof on **`REG-A-10`**, which *is* in the pinned set. §6.2 itself
demands representation in a policy, provable by content hash. Putting a second
command proof here would duplicate `REG-A-10`'s obligation on a row that owns the
policy's *content* requirement rather than its test suite.

**`TYPED_APPROVAL` — unrepresentable.** The row's only approval requirement is
`APR-DISP-6-2-01`, a `DELEGATED_ARTIFACT_APPROVAL`; verified ledger-wide that
all 123 such requirements are paired with zero `TYPED_APPROVAL` evidence items,
because that record carries its own persisted clean `REVIEWER`-role review (goal
L595-598). Every non-delegated requirement type that *does* need one
(`ANALYST_ACCEPTANCE`, `DOMAIN_EXPERT_ACCEPTANCE`, `BUDGET_APPROVAL`,
`CAPACITY_COMMITMENT`, `DATA_RIGHTS_APPROVAL`, `LEGAL_REVIEW`,
`NAMED_OWNER_COMMITMENT`, `MEMORY_PROMOTION`, `DISTRIBUTION_APPROVAL`,
`REGULATORY_REVIEW`) is paired 1:1 ledger-wide; this row carries none of them.

**No negative-proof item.** `REQUIRED_NOW` active control, `rejection_record:
null`, defers nothing.

**`evidence_refs` — five objects, and why the extra three are *not* an
inventory gap.** All five re-verified against current bytes and all
`captured_at` values precede this review's timestamp:

| ID | Mode | Target | Verified |
|---|---|---|---|
| `EV-DISP-6-2-SOURCE` | `UTF8_LINE_SPAN` L359-361 | disposition report | digest matches |
| `EV-DISP-6-2-SPEC-DRAFT` | `FILE_BYTES` | `docs/specs/equity-os-s06-output-materiality-falsifiers.md` | `9b14f5f3…` matches |
| `EV-DISP-6-2-S06-I7-CURRENT-S06` | `FILE_BYTES` | same S06 file | `9b14f5f3…` matches |
| `EV-DISP-6-2-S06-I7-R4` | `FILE_BYTES` | `docs/goals/reviews/specs/equity-os-s04-s06-r4.md` | `61d74f4b…` matches |
| `EV-DISP-6-2-S06-I7-ADJUDICATION` | `FILE_BYTES` | `docs/goals/reviews/specs/equity-os-s04-s06-adjudication.md` | `da3ef87f…` matches |

The last three are linked from `open_findings[0].evidence_ref_ids`, not from any
`required_evidence` item. That is correct, not an omission: they evidence the
`S06-I7` finding — its final ordinary r4 report, the post-cap adjudication that
upheld it, and the exact S06 bytes adjudicated — and a finding is not an
acceptance obligation. The `EVIDENCE` review must not be misread as demanding
that every `evidence_refs` entry be claimed by a `required_evidence` item; the
contract requires the converse direction only (a satisfied item has nonempty
component-local refs, goal L484-485). I note that `EV-DISP-6-2-SPEC-DRAFT` and
`EV-DISP-6-2-S06-I7-CURRENT-S06` carry the same digest over the same path with
different `captured_at` and different `scope`; that is two distinct assertions
about the same bytes (current draft vs. exact bytes adjudicated) and
`evidence_ref_id` uniqueness is preserved.

**Framing check.** "Current proof satisfying: ### 6.2 …" reads correctly for an
affirmative "must be represented" requirement.

**`verification_command` observation, not a finding.** `mode: UNRESOLVED`,
permitted during initial ledger construction (goal L498-500). Not in the pinned
command-proof set, so the eventual resolution is `NOT_APPLICABLE` with its own
evidenced reviewer attestation. A future obligation on `verification_command`,
not a missing `required_evidence` item.

**Residuals.** None. The four-element granularity question above is recorded as
resolved, not as an open doubt.

---

**verdict: CLEAN**

`required_evidence` for `DISP-6-2` is complete at the input bytes pinned above.
This review satisfies no evidence item, authorizes nothing, and does not clear
the open `S06-I7` block.
