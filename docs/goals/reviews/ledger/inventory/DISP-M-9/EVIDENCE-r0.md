# Inventory review — DISP-M-9 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-M-9` |
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
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"4271ab940f3e90d9d2ad320339c64bebbd3ae32ccf82f6b020be9b8bf521ee74","digest_mode":"UTF8_LINE_SPAN","end_line":262,"evidence_ref_id":"EV-DISP-M-9-SOURCE","path":"docs/blueprint/funda-third-order-review-disposition-report.md","scope":"Exact authoritative source occurrence for DISP-M-9","start_line":252},{"captured_at":"2026-08-15T07:13:28Z","content_sha256":"5da8bf5f31e29833885d7e0bf74ecfc2a550fb9c24415ef5123fa47c938e2957","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-DISP-M-9-SPEC-DRAFT","path":"docs/specs/equity-os-s07-golden-set-failure-reviewer-controls.md","scope":"Current draft specification bytes for DISP-M-9","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: ### M-9 — Untrusted-document surface\n\n**Disposition: Accept.**\n\nAdd explicit failure and test cases for document text being treated as instructions. The operational controls are:\n\n- source content is data, not control text;\n- retrieved text cannot change tools, permissions, cutoffs, or promotion rules;\n- memory drafts show provenance at promotion time;\n- no document-originated instruction can invoke execution or secrets;\n- prompt-injection and source-confusion cases enter the golden set.","evidence_id":"REQ-DISP-M-9-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"DISP-M-9 acceptance and delivery scope","status":"UNRESOLVED"},{"approval_ids":[],"description":"Reproducible command result proving the current DISP-M-9 acceptance obligation","evidence_id":"REQ-DISP-M-9-COMMAND-PROOF","evidence_ref_ids":[],"evidence_type":"COMMAND_RESULT","proof_mode":"COMMAND","scope":"DISP-M-9 command proof","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `0859b908b24771e29ddb5013c779c38d7423b89028dbce7b754803e3e399df97`
- `reviewed_inventory_sha256` (pre-record): `b02d5c53fca4d6bb081feeb61391b9463a14456ac82a94c6c36fa387c88256fd`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` lines 252-262, anchor `M-9`, title "Untrusted-document surface":

> ### M-9 — Untrusted-document surface
>
> **Disposition: Accept.**
>
> Add explicit failure and test cases for document text being treated as instructions. The operational controls are:
>
> - source content is data, not control text;
> - retrieved text cannot change tools, permissions, cutoffs, or promotion rules;
> - memory drafts show provenance at promotion time;
> - no document-originated instruction can invoke execution or secrets;
> - prompt-injection and source-confusion cases enter the golden set.

- `source_hash` recomputed over the whole file → `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`, matching the row.
- `text_digest` recomputed over the normalized L252-262 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `4271ab940f3e90d9d2ad320339c64bebbd3ae32ccf82f6b020be9b8bf521ee74`, matching the row.
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

**Enumerated.** Two items, and this is the only row in the batch with a second
one: `REQ-DISP-M-9-ACCEPTANCE` (`ARTIFACT` / `CONTENT_HASH`) and
`REQ-DISP-M-9-COMMAND-PROOF` (`COMMAND_RESULT` / `COMMAND`, scope "DISP-M-9
command proof"). Both `UNRESOLVED` with empty refs.

**Demand-by-demand.** Of the clause's five controls, four are policy and
architecture statements provable by inspecting the specification text: source
content is data not control text; retrieved text cannot change tools,
permissions, cutoffs, or promotion rules; memory drafts show provenance at
promotion time; no document-originated instruction can invoke execution or
secrets. The fifth — "prompt-injection and source-confusion cases enter the
golden set" — together with the lead-in demand to "Add explicit failure and
**test cases**", is executable, and it is exactly what the second item covers.
The pairing is confirmed structurally: `DISP-M-9` is one of the 25 components in
the validator's pinned `EXPECTED_COMMAND_PROOF_COMPONENTS` manifest
(`:2635-2649`), and `COMMAND_RESULT` forces `proof_mode == COMMAND` (`:2130-2131`),
which the item satisfies.

**Typed-approval demands, checked.** Golden-set ownership is the obvious
candidate, since the clause pushes cases into the golden set. That obligation is
enumerated where the source puts it: REG-A-08 carries
`REQ-REG-A-08-NAMED_OWNER_COMMITMENT` (`NAMED_OWNER` / `TYPED_APPROVAL`) paired to
a `NAMED_OWNER_COMMITMENT` requirement for the "Golden-set owner". Failure-taxonomy
categorisation is REG-B-08's. Neither is this component's to restate.

**Security shape, checked.** This is the batch's one security clause, so I tested
whether a `SECURITY`-typed evidence item is missing. It is not: `SECURITY`
evidence attaches to an approved security *exception*, and this clause grants no
exception — it mandates controls. `security_exception_ids` is `[]` on this row
and nothing in the clause claims a deviation.

**`evidence_refs` as read.** Two objects, both re-hashed this round:
`EV-DISP-M-9-SOURCE` (`UTF8_LINE_SPAN` L252-262, `content_sha256` equal to the
row's `text_digest`) and `EV-DISP-M-9-SPEC-DRAFT` (`FILE_BYTES` over the S07
spec, `captured_at` 2026-08-15T07:13:28Z — refreshed by the HR-0004 transaction).
Both resolve against current bytes.

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

**`verification_command`.** Mode `UNRESOLVED` with no commands. On this row that
matters more than elsewhere, because the enumerated `COMMAND` obligation will need
`mode == COMMANDS` with a registered command object before it can ever be
`SATISFIED`. That is a forward obligation on a pre-implementation row
(`gate_result` is `NOT_EVALUATED`), and the goal admits `UNRESOLVED` during
initial ledger construction. The obligation itself is enumerated, which is what
this review audits.

**Conclusion.** `required_evidence` is complete for this clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `DISP-M-9`'s `required_evidence` inventory is correct at the input bytes pinned above.
