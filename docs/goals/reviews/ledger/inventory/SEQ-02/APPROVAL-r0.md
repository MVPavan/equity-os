# Inventory review — SEQ-02 / APPROVAL / r0

**verdict: ISSUES_FOUND**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `SEQ-02` |
| `review_type` | `APPROVAL` |
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

`review_inventory_projection(row, "APPROVAL")` — canonical JSON, extracted from the
checked-in structural validator by `ast` (recording design r2 §3.3) so the
projection is the validator's own, not a transcription:

```json
{"approval_records":[],"human_review_id":["HR-0004"],"required_approvals":[{"actor":null,"approval_id":"APR-SEQ-02-01","approval_type":"DELEGATED_ARTIFACT_APPROVAL","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Delegated fresh Sol xhigh specification reviewer","scope":"SEQ-02 under S02","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (the recorder recomputes
`reviewed_input_sha256` after Phase A, recording design r2 §3.4):

- `reviewed_input_sha256` (pre-record): `ff4a76203f9523a3dbda66bd61c4f2304d4fc001a137c773d77df69147136aaa`
- `reviewed_inventory_sha256` (pre-record): `e630391dd6cd458f3f35b87880b20064b753e44e8aa82ff8836442838442cca0`

## Scope of this decision

Per recording design r2 §2.2 and goal L534-537, this review decides whether
`required_approvals` is **complete** — whether the source clause demands any
authority whose sign-off is not enumerated. It does **not** decide whether any
approval has been obtained; `UNRESOLVED` with a null actor, null timestamp, and
no matched record is the correct current state (goal L590-593). The `APPROVAL`
inventory projection (`validate_ledger_structural.py:312-318`) covers
`required_approvals`, `approval_records`, `human_review_id`, and
`security_exception_ids`.

## The source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` line 452, within
`## 8. Recommended sequence` (L447); `source_title` "Recommended sequence step 2", `source_anchor`
`SEQUENCE-02`:

> 2. **A-05 and A-09:** rights review scoped to that boundary; name check in parallel.

`text_digest` and `EV-SEQ-02-SOURCE.content_sha256` were both recomputed over the
normalized L452-452 span → `fc80e36b…`, matching the stored values, and
`source_hash` recomputed over the whole disposition report → `a9021c15…`, matching.

## Reasoning

**Everything on this row that I could verify, I did, and it holds.**
`APR-SEQ-02-01` is correctly typed `DELEGATED_ARTIFACT_APPROVAL` with the single
ledger-wide authority literal `"Delegated fresh Sol xhigh specification reviewer"`
that structural validation requires every such requirement to share
(`assert len(delegated_artifact_authorities) == 1`), and it carries the correct
`UNRESOLVED` shape — null actor, null timestamp, empty evidence, null
`matched_record_id` (goal L590-593). `approval_records` is `[]`, correct while
nothing is `SATISFIED`. `security_exception_ids` is `[]` and the clause raises no
fail-closed boundary. I walked the closed 21-type vocabulary (goal L540-549) and
found no named business authority this clause asks anyone to exercise; no
requirement anywhere in the ledger uses `GOAL_OR_PROCESS_AUTHORIZATION`.
`human_review_id` normalizes correctly. Were it not for the finding below, this
review would be clean.

**The defect.** This row declares **two** applicable spec artifacts,
`applicable_spec_ids = ["S01","S02"]`, and the declaration is correct — this
component's own `SCOPE` review confirms it against the source clause and against
the goal-derived crosswalk at `validate_ledger_structural.py:2481`. But the row
enumerates obligations covering **one** of them, `S02`:

| Applicable spec | Enumerated approval obligation on this row |
|---|---|
| `S02` | `APR-SEQ-02-01`, `DELEGATED_ARTIFACT_APPROVAL`, scope `"SEQ-02 under S02"` |
| `S01` | **none** |

Nothing in the row designates `S02` as the privileged spec. `primary_spec` is
`null` here — as it is on every sequence row and every multi-spec disposition row
— precisely because no single spec owns the component. The row therefore refuses
to name an owning spec in the field the schema provides for it, and then names one
anyway inside an approval `scope` string and an evidence `scope` string, on no
declared basis. I checked what the basis actually is: across all four two-spec
sequence rows the privileged spec is always the spec owning the **first** listed
`source_register_ids` entry (A-05 → S02 here). That is the residue of
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
  row."* This is the strongest counterargument and it is partly true: A-09
  is independently inventoried on `REG-A-09` with its own
  `"A-09 under S01"` delegated approval and its own
  `REQ-REG-A-09-SPEC-REVIEW`. But `REG-A-09`'s obligations are
  `A-09`'s own; they say nothing about the *sequencing* obligation this clause imposes — that the name check runs at step 2, **in parallel** with the rights review, and scoped to the boundary fixed at step 1. What this component
  uniquely contributes is exactly the part not covered there.

**What I am not saying.** I am not asserting that the row needs typed business
authorities beyond the delegated one, nor that its `REQ-SEQ-02-ACCEPTANCE` item is
mis-framed — that item quotes the full clause text verbatim, covers both halves of
the obligation, and is correctly classified `ARTIFACT`/`CONTENT_HASH`. The gap is
narrow and specific: the row's declared applicability is two specs and its
enumerated approval covers one.

**What a clean verdict would assert, and why I cannot assert it.** A `CLEAN`
`APPROVAL` verdict states that `required_approvals` is complete — that the source
clause demands no authority whose sign-off this row does not enumerate. On these
bytes I cannot state that: the row declares two applicable spec artifacts and
enumerates a delegated approval over one, the executed remediation design says every
applicable spec requires its own delegated artifact-approval obligation, and an
independent reviewer has already called the shortfall load-bearing. Recording
`CLEAN` here would be a fabrication the contract's digest machinery cannot catch,
because the digests would all verify.

---

**verdict: ISSUES_FOUND**

This verdict is **not recordable** as a ledger review object, and that is
correct by design: `validate_ledger_structural.py:320-354` admits exactly one
`verdict` value, `CLEAN`, in a `COMPLETE` review, so a non-clean outcome is
unrepresentable as a review (recording design r2 §2.1). No `APPROVAL` review
transition is authorized for `SEQ-02`, and this artifact must not be passed to
the recorder. It authorizes no delivery, gate, approval, or transition.
