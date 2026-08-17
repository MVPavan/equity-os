# Inventory review — SEQ-04 / EVIDENCE / r0

**verdict: ISSUES_FOUND**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `SEQ-04` |
| `review_type` | `EVIDENCE` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `cf74831a-f468-43f7-810e-95a86647a977` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-15T13:13:37Z` |

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

`review_inventory_projection(row, "EVIDENCE")` — canonical JSON, extracted from the
checked-in structural validator by `ast` (recording design r2 §3.3) so the
projection is the validator's own, not a transcription:

```json
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"8a721afc72bbd47bd0e7a794b626644b1c2b5b724471d4f5cc997040a60c6700","digest_mode":"UTF8_LINE_SPAN","end_line":454,"evidence_ref_id":"EV-SEQ-04-SOURCE","path":"docs/blueprint/funda-third-order-review-disposition-report.md","scope":"Exact authoritative source occurrence for SEQ-04","start_line":454},{"captured_at":"2026-08-15T07:13:28Z","content_sha256":"9b14f5f327a9ff623cb41c823ab3eeec2d14f2f3ee05b8506313fbb28e83f458","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-SEQ-04-SPEC-DRAFT","path":"docs/specs/equity-os-s06-output-materiality-falsifiers.md","scope":"Current draft specification bytes for SEQ-04","start_line":null},{"captured_at":"2026-08-13T04:19:57Z","content_sha256":"9b14f5f327a9ff623cb41c823ab3eeec2d14f2f3ee05b8506313fbb28e83f458","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-SEQ-04-S06-I7-CURRENT-S06","path":"docs/specs/equity-os-s06-output-materiality-falsifiers.md","scope":"Exact current S06 bytes adjudicated for S06-I7 on SEQ-04","start_line":null},{"captured_at":"2026-08-13T04:19:57Z","content_sha256":"61d74f4b8b9248a75ff48e4508b1b58fb79b884acbbc859328111bb3814f2113","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-SEQ-04-S06-I7-R4","path":"docs/goals/reviews/specs/equity-os-s04-s06-r4.md","scope":"Final ordinary r4 review report finding S06-I7 for SEQ-04","start_line":null},{"captured_at":"2026-08-13T04:19:57Z","content_sha256":"da3ef87f32646fdb3e0f576086aba5070eee0aee3b115f53cb6b40579999e26a","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-SEQ-04-S06-I7-ADJUDICATION","path":"docs/goals/reviews/specs/equity-os-s04-s06-adjudication.md","scope":"Post-cap adjudication upholding S06-I7 and its exact cone for SEQ-04","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: 4. **A-10 and A-13:** define materiality and measurement methods before collecting the baseline.","evidence_id":"REQ-SEQ-04-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"SEQ-04 acceptance and delivery scope","status":"UNRESOLVED"},{"approval_ids":[],"description":"Persisted clean fresh Sol xhigh review of the current specification bytes","evidence_id":"REQ-SEQ-04-SPEC-REVIEW","evidence_ref_ids":[],"evidence_type":"REVIEW","proof_mode":"CONTENT_HASH","scope":"SEQ-04 under S06","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (the recorder recomputes
`reviewed_input_sha256` after Phase A, recording design r2 §3.4):

- `reviewed_input_sha256` (pre-record): `caa8646309d3d9b8ec67847e3cf601747998a2699bcb68cf4674a8563ac1d2b7`
- `reviewed_inventory_sha256` (pre-record): `049f6bde6ae252040f319d8b240cf37fac3779e3ed7b209d80c62a66479e6612`

## Scope of this decision

Per recording design r2 §2.2 and goal L492-494, this review decides whether
`required_evidence` is **complete** — whether the source clause demands any proof
that is not enumerated and classified by proof mode. It does **not** decide
whether any proof has been obtained; every item on this row is legitimately
`UNRESOLVED` with empty `evidence_ref_ids` (goal L484: "An unresolved item has no
evidence refs"). The `EVIDENCE` inventory projection
(`validate_ledger_structural.py:306-311`) covers `required_evidence`,
`evidence_refs`, and `verification_command`.

## The source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` line 454, within
`## 8. Recommended sequence` (L447); `source_title` "Recommended sequence step 4", `source_anchor`
`SEQUENCE-04`:

> 4. **A-10 and A-13:** define materiality and measurement methods before collecting the baseline.

`text_digest` and `EV-SEQ-04-SOURCE.content_sha256` were both recomputed over the
normalized L454-454 span → `8a721afc…`, matching the stored values, and
`source_hash` recomputed over the whole disposition report → `a9021c15…`, matching.

## Reasoning

**Everything on this row that I could verify, I did, and it holds.**
`REQ-SEQ-04-ACCEPTANCE` (`ARTIFACT`/`CONTENT_HASH`) quotes the clause verbatim and
covers both halves of the obligation; `REQ-SEQ-04-SPEC-REVIEW`
(`REVIEW`/`CONTENT_HASH`) is a correctly typed spec-review obligation;
`verification_command` is `UNRESOLVED`, valid during initial ledger construction
(goal L498-500); no `COMMAND_RESULT` item is demanded or permitted, since the
goal-derived validator pins the command-proof population to an exact 25-row set at
`validate_ledger_structural.py:2634-2649` and `SEQ-09` is the only sequence row in
it; no `TYPED_APPROVAL` item is representable, since goal L484-487 requires one to
name component-local approval requirements and no such item anywhere in the ledger
names a `DELEGATED_ARTIFACT_APPROVAL`; and no negative no-implementation item is
demanded, since this row is `REQUIRED_NOW` with `rejection_record: null`. Every
`evidence_refs` digest was recomputed against current bytes this round and every one
matches. Were it not for the finding below, this review would be clean.

**The defect.** This row declares **two** applicable spec artifacts,
`applicable_spec_ids = ["S06","S08"]`, and the declaration is correct — this
component's own `SCOPE` review confirms it against the source clause and against
the goal-derived crosswalk at `validate_ledger_structural.py:2483`. But the row
enumerates obligations covering **one** of them, `S06`:

| Applicable spec | Current artifact evidence on this row | Enumerated evidence obligation |
|---|---|---|
| `S06` | `EV-SEQ-04-SPEC-DRAFT` (`FILE_BYTES`, digest recomputed and matching) | `REQ-SEQ-04-SPEC-REVIEW`, scope `"SEQ-04 under S06"` |
| `S08` | **none** | **none** |

Nothing in the row designates `S06` as the privileged spec. `primary_spec` is
`null` here — as it is on every sequence row and every multi-spec disposition row
— precisely because no single spec owns the component. The row therefore refuses
to name an owning spec in the field the schema provides for it, and then names one
anyway inside an approval `scope` string and an evidence `scope` string, on no
declared basis. I checked what the basis actually is: across all four two-spec
sequence rows the privileged spec is always the spec owning the **first** listed
`source_register_ids` entry (A-10 → S06 here). That is the residue of
the generator behaviour an independent program-level reviewer already named.

**Counterarguments I tested before concluding, because a systemic pattern is
usually a convention rather than a defect.**

- *"It is the uniform ledger-wide convention, so it is intended."* It is uniform:
  all 20 multi-spec canonical rows behave this way (4 sequence + 16 disposition),
  and I confirmed the correspondence the ledger **does** enforce is exact — across
  every row carrying `applicable_spec_ids`, a nonempty spec list holds if and only
  if a `DELEGATED_ARTIFACT_APPROVAL` is present, with zero exceptions. But that
  correspondence is one of *existence*, never of *cardinality*: the ledger enforces
  "at least one applicable spec ⇒ exactly one approval" and never "n specs ⇒ n
  obligations". Uniformity of an unenforced default is not evidence that the
  default is right, and here the written rule says it is not.
- *"The structural validator passes, so the state is contract-compliant."*
  It does pass (exit `0`, rerun this round). But the validator pins the sequence
  crosswalk, the command-proof population, and the single delegated-authority
  string, and nowhere compares approval or evidence cardinality against
  `applicable_spec_ids`. Silence in the validator is not a ruling; r7 §3.10 L816-818
  says as much for the adjacent question — "that is out of scope here and is not
  authorized by silence."
- *"Nothing is lost, because the second spec is inventoried on its own register
  row."* This is the strongest counterargument and it is partly true: A-13
  is independently inventoried on `REG-A-13` with its own
  `"A-13 under S08"` delegated approval and its own
  `REQ-REG-A-13-SPEC-REVIEW`. But `REG-A-13`'s obligations are
  `A-13`'s own; they say nothing about the *sequencing* obligation this clause imposes — that the measurement methods are defined **before** the baseline is collected, jointly with the materiality policy. What this component
  uniquely contributes is exactly the part not covered there.

**What I am not saying.** I am not asserting that the row needs typed business
authorities beyond the delegated one, nor that its `REQ-SEQ-04-ACCEPTANCE` item is
mis-framed — that item quotes the full clause text verbatim, covers both halves of
the obligation, and is correctly classified `ARTIFACT`/`CONTENT_HASH`. The gap is
narrow and specific: the row's declared applicability is two specs and its
enumerated evidence covers one.

**What a clean verdict would assert, and why I cannot assert it.** A `CLEAN`
`EVIDENCE` verdict states that `required_evidence` is complete — that the source
clause demands no proof this row does not enumerate. On these bytes I cannot state
that: the row declares two applicable spec artifacts and enumerates a proof
obligation over one, the executed remediation design says every applicable spec
requires its own, and an independent reviewer has already called the shortfall
load-bearing. Recording `CLEAN` here would be a fabrication of exactly the kind the
contract's digest machinery cannot catch, because the digests would all verify.

---

**verdict: ISSUES_FOUND**

This verdict is **not recordable** as a ledger review object, and that is
correct by design: `validate_ledger_structural.py:320-354` admits exactly one
`verdict` value, `CLEAN`, in a `COMPLETE` review, so a non-clean outcome is
unrepresentable as a review (recording design r2 §2.1). No `EVIDENCE` review
transition is authorized for `SEQ-04`, and this artifact must not be passed to
the recorder. It authorizes no delivery, gate, approval, or transition.
