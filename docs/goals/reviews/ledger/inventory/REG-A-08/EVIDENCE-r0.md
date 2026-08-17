# Inventory review — REG-A-08 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-A-08` |
| `review_type` | `EVIDENCE` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `90676a15-0b66-4e7c-9fd2-f1b300d6e780` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-16T13:44:34Z` |

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
additionally re-hashed by hand against its current target bytes this round —
`FILE_BYTES` objects over whole-file bytes, `UTF8_LINE_SPAN` objects over the
`\n`-joined, whitespace-trimmed span — and all matched.

## Register-row review applicability, verified on this row

`REG-A-08` has `kind == "register_row"`. Its `scope_derivation` reads exactly

```json
{
 "authority_effect": null,
 "derived_program_disposition": "REQUIRED_NOW",
 "related_register_ids": [],
 "rule": "REGISTER_STATUS",
 "semantic_review": null
}
```

so `scope_derivation.semantic_review` **is `null`**, checked on the live row
rather than assumed. Two independent mechanisms make that the applicable-review
rule: `validate_ledger_preimplementation.py:200-204` builds the per-row check
list as `APPROVAL` + `EVIDENCE` always and appends `SCOPE` only
`if row["kind"] != "register_row"`; and the goal fixes the null slot for this
kind at L208-211, mechanized at goal L2886
(`assert derivation["semantic_review"] is None`). This row therefore carries
**two** applicable reviews, `EVIDENCE` and `APPROVAL`, and no `SCOPE` review
exists to record. No `SCOPE` artifact was written for `REG-A-08`.

One consequence is worth stating rather than leaving implicit: the `SCOPE`
inventory projection (`validate_ledger_structural.py:293-305`) is the only
projection that covers `disposition_refs`, `gate_refs`, `activation_predicate`,
and `related_register_ids`. On a register row those fields are covered by the
**input** projection — so any mutation to them stales both reviews below — but
they are not the subject of a per-component semantic review, by contract. The
scope of a register row comes from the pinned v2 register itself.

## Reviewed inventory, exactly as read

`review_inventory_projection(row, "EVIDENCE")` — canonical JSON:

```json
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"f3242a22721b00ddd070a09c6bf8d98b4eae059c140fe6145903337854421389","digest_mode":"UTF8_LINE_SPAN","end_line":38,"evidence_ref_id":"EV-REG-A-08-SOURCE","path":"docs/blueprint/funda-blueprint-implementation-decision-register-v2.md","scope":"Exact authoritative source occurrence for REG-A-08","start_line":38},{"captured_at":"2026-08-15T07:13:28Z","content_sha256":"5da8bf5f31e29833885d7e0bf74ecfc2a550fb9c24415ef5123fa47c938e2957","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-REG-A-08-SPEC-DRAFT","path":"docs/specs/equity-os-s07-golden-set-failure-reviewer-controls.md","scope":"Current draft specification bytes for REG-A-08","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: Named owner, repository location, review cadence, and first twenty labeled cases, including prompt-injection/source-confusion cases","evidence_id":"REQ-REG-A-08-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"REG-A-08 acceptance and delivery scope","status":"UNRESOLVED"},{"approval_ids":[],"description":"Persisted clean fresh Sol xhigh review of the current specification bytes","evidence_id":"REQ-REG-A-08-SPEC-REVIEW","evidence_ref_ids":[],"evidence_type":"REVIEW","proof_mode":"CONTENT_HASH","scope":"A-08 under S07: Appoint golden-test-set owner","status":"UNRESOLVED"},{"approval_ids":["APR-REG-A-08-02"],"description":"Current NAMED_OWNER_COMMITMENT evidence from Golden-set owner","evidence_id":"REQ-REG-A-08-NAMED_OWNER_COMMITMENT","evidence_ref_ids":[],"evidence_type":"NAMED_OWNER","proof_mode":"TYPED_APPROVAL","scope":"A-08 under S07: Appoint golden-test-set owner","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `eea64b6b4b1fd7ec32b407f37bab4ff10c09d3c413cb778b270ea763ec595988`
- `reviewed_inventory_sha256` (pre-record): `580e31cbf2dd5363d1805682395c204b27de76056fc3572d4a63d45fef70b41f`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line
38, register ID `A-08`, title "Appoint golden-test-set owner":

```text
| A-08 | High | Appoint golden-test-set owner | Named owner, repository location, review cadence, and first twenty labeled cases, including prompt-injection/source-confusion cases | — | Open |
```

- `source_hash` recomputed over the whole pinned v2 register →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L38 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `f3242a22721b00ddd070a09c6bf8d98b4eae059c140fe6145903337854421389`, matching the row and
  matching `EV-REG-A-08-SOURCE.content_sha256`.
- `required_acceptance_text` equals the source row's acceptance cell byte for
  byte, and `register_id`/`source_title` equal its ID and decision cells
  (checked by comparison, not by eye).
- Register `Status` cell: `Open`; `Priority`: `High`; `Dependencies`:
  `—`. Row `program_disposition`: `REQUIRED_NOW`; `delivery_status`:
  `SPEC_DRAFT`; `gate_result`: `NOT_EVALUATED`.

## Reasoning

**What this review decides.** Whether `required_evidence` on `REG-A-08`
enumerates every proof obligation the A-08 clause demands. All three items are
`UNRESOLVED` with empty `evidence_ref_ids`.

**The clause, restated from the bytes.** A-08 demands four things: a named
owner, a repository location, a review cadence, and the first twenty labeled
cases, "including prompt-injection/source-confusion cases".
`required_acceptance_text`, the `ACCEPTANCE` description less its prefix, and
register line 38 agree byte for byte.

**Enumerated: three items.** `REQ-REG-A-08-ACCEPTANCE` (`ARTIFACT` /
`CONTENT_HASH`), `REQ-REG-A-08-SPEC-REVIEW` (`REVIEW` / `CONTENT_HASH`), and
`REQ-REG-A-08-NAMED_OWNER_COMMITMENT` (`NAMED_OWNER` / `TYPED_APPROVAL`, paired
to `APR-REG-A-08-02`). The first demand of the clause is literally a *named
owner*, and this is one of only three rows in the ledger pairing a `NAMED_OWNER`
evidence item to a `NAMED_OWNER_COMMITMENT` requirement.

**The demand I probed hardest: are the twenty labeled cases executable proof?**
This clause pushes concrete test material into existence, so a missing
`COMMAND_RESULT` item was the live hypothesis. I rejected it. A-08's demand is
that the cases *exist and are labeled* — an artifact property, provable by
content hash. The executable obligations in this cone are placed elsewhere and
are placed explicitly: `DISP-M-9`, one of this row's dispositions, *is* in the
pinned `EXPECTED_COMMAND_PROOF_COMPONENTS` manifest (`:2635-2649`) and carries
a `COMMAND_RESULT` item for its test-case demand; and the automation question
is the phase gate `PG-05-10`'s ("the first golden cases are automated or
consistently reviewable"), carried on its own row. `REG-A-08` is absent from
that manifest, and since the manifest is asserted equal to the actual
`COMMAND_RESULT`-bearing set, adding an item here would fail structural
validation.

**Security shape, checked.** "prompt-injection/source-confusion cases" is the
one security-flavoured phrase in this batch, so I tested whether a `SECURITY`-
typed evidence item is missing. It is not. `SECURITY` evidence in this contract
attaches to an approved security *exception*; this clause grants no exception,
it mandates test coverage. `security_exception_ids` is `[]` and nothing in the
clause claims a deviation.

**Where the injection cases come from.** `disposition_refs` are `M-6`, `M-9`,
`6.6`. `DISP-M-9` ("Untrusted-document surface") ends with "prompt-injection and
source-confusion cases enter the golden set" and lists `A-08` among its
`related_register_ids`; `DISP-M-6` (reviewer and builder are the same person)
also lists `A-08`. Re-reading both, neither makes a proof demand of A-08 that
A-08's own clause does not, and neither is omitted from its own row's
inventory. *(Noted without acting on it: `DISP-6-6`'s `related_register_ids` is
`["B-13", "C-10"]` and does not include `A-08`, although `A-08` lists `6.6` in
`disposition_refs`. `disposition_refs` sits in the `SCOPE` inventory projection
(`:293-305`), which a register row does not have; it is outside both
inventories I am auditing here, so I record the observation and take no finding
on it.)*

**`evidence_refs` as read.** `EV-REG-A-08-SOURCE` (`UTF8_LINE_SPAN` L38-38,
digest equal to `text_digest`) and `EV-REG-A-08-SPEC-DRAFT` (`FILE_BYTES` over
the S07 spec, `captured_at` 2026-08-15T07:13:28Z, refreshed by HR-0004). Both
re-hashed this round; both resolve.

**`verification_command`.** `mode` `UNRESOLVED`, no commands — consistent.

**Conclusion.** `required_evidence` is complete for the A-08 clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `REG-A-08`'s `required_evidence` inventory is correct at the input bytes pinned
above.
