# Inventory review — DISP-R-4 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-R-4` |
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
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"5b47fb8bb6e04161603fe15b37b17c534201e957fc53f6d8212dbb83180cee07","digest_mode":"UTF8_LINE_SPAN","end_line":341,"evidence_ref_id":"EV-DISP-R-4-SOURCE","path":"docs/blueprint/funda-third-order-review-disposition-report.md","scope":"Exact authoritative source occurrence for DISP-R-4","start_line":337},{"captured_at":"2026-08-15T07:13:28Z","content_sha256":"9b14f5f327a9ff623cb41c823ab3eeec2d14f2f3ee05b8506313fbb28e83f458","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-DISP-R-4-SPEC-DRAFT","path":"docs/specs/equity-os-s06-output-materiality-falsifiers.md","scope":"Current draft specification bytes for DISP-R-4","start_line":null},{"captured_at":"2026-08-13T04:19:57Z","content_sha256":"9b14f5f327a9ff623cb41c823ab3eeec2d14f2f3ee05b8506313fbb28e83f458","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-DISP-R-4-S06-I7-CURRENT-S06","path":"docs/specs/equity-os-s06-output-materiality-falsifiers.md","scope":"Exact current S06 bytes adjudicated for S06-I7 on DISP-R-4","start_line":null},{"captured_at":"2026-08-13T04:19:57Z","content_sha256":"61d74f4b8b9248a75ff48e4508b1b58fb79b884acbbc859328111bb3814f2113","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-DISP-R-4-S06-I7-R4","path":"docs/goals/reviews/specs/equity-os-s04-s06-r4.md","scope":"Final ordinary r4 review report finding S06-I7 for DISP-R-4","start_line":null},{"captured_at":"2026-08-13T04:19:57Z","content_sha256":"da3ef87f32646fdb3e0f576086aba5070eee0aee3b115f53cb6b40579999e26a","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-DISP-R-4-S06-I7-ADJUDICATION","path":"docs/goals/reviews/specs/equity-os-s04-s06-adjudication.md","scope":"Post-cap adjudication upholding S06-I7 and its exact cone for DISP-R-4","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: ### R-4 — Add observable falsifiers\n\n**Disposition: Accept.**\n\nThe output contract should state what observable event, metric, management outcome, or evidence would materially weaken or reverse the current thesis. This is distinct from listing generic risks.","evidence_id":"REQ-DISP-R-4-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"DISP-R-4 acceptance and delivery scope","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `9ee3c78b356b9d624a71ea6dd1bfff1fcb32909f858f14538bf067ea9b456788`
- `reviewed_inventory_sha256` (pre-record): `3d3d38906d023ee1fb5e783487aa60e77fa9949e03a2ad7faaef8595cb65eca5`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` lines 337-341, anchor `R-4`, title "Add observable falsifiers":

> ### R-4 — Add observable falsifiers
>
> **Disposition: Accept.**
>
> The output contract should state what observable event, metric, management outcome, or evidence would materially weaken or reverse the current thesis. This is distinct from listing generic risks.

- `source_hash` recomputed over the whole file → `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`, matching the row.
- `text_digest` recomputed over the normalized L337-341 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `5b47fb8bb6e04161603fe15b37b17c534201e957fc53f6d8212dbb83180cee07`, matching the row.
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

**Enumerated.** One item: `REQ-DISP-R-4-ACCEPTANCE`, `ARTIFACT` /
`CONTENT_HASH`, scope "DISP-R-4 acceptance and delivery scope", `UNRESOLVED`.

**Demand-by-demand.** Two demands, both content-shaped: the output contract must
state what observable event, metric, management outcome, or evidence would
materially weaken or reverse the current thesis; and that statement must be
distinct from a generic risk list. Both are decidable by reading the S06
specification bytes, which is what `CONTENT_HASH` binds.

**The analyst trap, checked.** Falsifiers are analytical content, and the goal
forces analyst evidence to `TYPED_APPROVAL`. The question is whether *this*
component owes an analyst acceptance. It does not: acceptance of the output
contract is A-04's obligation and is enumerated there as
`REQ-REG-A-04-ANALYST_ACCEPTANCE` (`ANALYST` / `TYPED_APPROVAL`) paired to an
`ANALYST_ACCEPTANCE` requirement, alongside `PRODUCT_OWNER_DECISION`. What R-4
demands is that the contract *contain* a falsifier statement of the right shape —
provable by inspection, without an analyst's judgment about whether the
particular falsifiers are the right ones. That judgment is A-04's, once, in its
own scope.

**No command obligation.** Nothing here is executable, and neither `DISP-R-4` nor
REG-A-04 appears in `EXPECTED_COMMAND_PROOF_COMPONENTS` (`:2635-2649`).

**`evidence_refs` as read — five objects.** `EV-DISP-R-4-SOURCE`
(`UTF8_LINE_SPAN` L337-341, hash equal to the row's `text_digest`) and
`EV-DISP-R-4-SPEC-DRAFT` (`FILE_BYTES` over the S06 spec) are the ordinary pair.
`EV-DISP-R-4-S06-I7-CURRENT-S06`, `-R4` and `-ADJUDICATION` were attached by the
`BLOCK` transitions recording the open load-bearing finding `S06-I7`; they are
finding evidence carried inside the projected `evidence_refs`, not
`required_evidence` items, and they neither add nor discharge an obligation. All
five re-hashed this round and matched their stored digests.

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

**Conclusion.** `required_evidence` is complete for this clause. The open
`S06-I7` blocker is untouched by this review.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `DISP-R-4`'s `required_evidence` inventory is correct at the input bytes pinned above.
