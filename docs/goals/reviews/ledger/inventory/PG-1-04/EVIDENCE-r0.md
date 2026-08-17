# Inventory review — PG-1-04 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `PG-1-04` |
| `review_type` | `EVIDENCE` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `9e80cd5e-6230-475f-937f-f1db62fa5746` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-16T04:05:18Z` |

Role binding: `CONTEXT.md` "Agent roles (harness-wide)" binds `REVIEWER` to
Claude Opus 5 at high effort, in an agent and context independent of any
`IMPLEMENTER` that produced the reviewed content. The digest above is the
`CONTEXT.md` bytes at review time and is an immutable historical capture.

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

Fresh structural validation at these exact bytes:
`python3 scripts/equity_os_blueprint/validate_ledger_structural.py --repo-root .`
→ exit `0` (run at review time).

## Reviewed inventory, exactly as read

`review_inventory_projection(row, "EVIDENCE")` — canonical JSON, produced by the
validator's own projection function, `ast`-extracted from
`validate_ledger_structural.py` per recording design r2 §3.3:

```json
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"301f510a422dcd06974fe1c7e2dfbc542af662e82a7333f7911355f4182006f4","digest_mode":"UTF8_LINE_SPAN","end_line":153,"evidence_ref_id":"EV-PG-1-04-SOURCE","path":"docs/blueprint/funda-blueprint-implementation-decision-register-v2.md","scope":"Exact authoritative source occurrence for PG-1-04","start_line":153}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: missing inputs fail closed","evidence_id":"REQ-PG-1-04-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"PG-1-04 acceptance and delivery scope","status":"UNRESOLVED"},{"approval_ids":[],"description":"Reproducible command result proving the current PG-1-04 acceptance obligation","evidence_id":"REQ-PG-1-04-COMMAND-PROOF","evidence_ref_ids":[],"evidence_type":"COMMAND_RESULT","proof_mode":"COMMAND","scope":"PG-1-04 command proof","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (the recorder recomputes
`reviewed_input_sha256` after its Phase A evidence append, recording design r2
§3.4 — appending review evidence mutates `evidence_refs` and therefore the input
projection):

- `reviewed_input_sha256` (pre-record): `e73540c56859228c8c11c17f54b741d11d753b8c65b0bef15e4b67843de03eec`
- `reviewed_inventory_sha256` (pre-record): `ea2778c65cd7eacbe8006636b5e0945e04c7dea958a5babd1b66864ef5ef0683`

## Scope of this decision

Per recording design r2 §2.2, this review decides one question: is
`required_evidence` **complete** — does the source clause demand any proof that
is not enumerated? Goal L492-495 fixes the standard: a clean review "proves that
every source-required acceptance item is represented and classified by proof
mode; it does not satisfy an evidence item." This is an audit of the obligation
list, **not** of whether any proof has been obtained; every item on this row is
`UNRESOLVED`, which is the correct state at `INVENTORIED` delivery. The
`EVIDENCE` inventory projection (goal L433-434) covers `required_evidence`,
`evidence_refs`, and `verification_command`.

## The source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line 153,
under `### Phase 1 may exit only when` (register v2 L148), inside `## F. Phase-gate scorecard` (L122); `source_title` "Phase 1 gate clause 4",
`source_anchor` `F-1-04`:

> - missing inputs fail closed;

Recomputed this round against current bytes:

- `source_hash` over the whole register file → `26d51b31…`, equal to the stored value.
- `text_digest` over the normalized L153-153 span (`"\n".join(lines[152:153]).strip(" \t\n\r\f\v")`,
  the exact rule at `validate_ledger_structural.py:174-176`) → `301f510a422dcd06974fe1c7e2dfbc542af662e82a7333f7911355f4182006f4`,
  equal to the stored value.
- `EV-PG-1-04-SOURCE.content_sha256` recomputed over the same span → `301f510a422dcd06974fe1c7e2dfbc542af662e82a7333f7911355f4182006f4`,
  equal to the stored value.
- `required_acceptance_text` equals that span with the `- ` list marker and the
  terminal `;` removed, byte for byte.
- Anchor uniqueness holds ledger-wide: `(funda-blueprint-implementation-decision-register-v2.md, F-1-04)` occurs once
  across all 213 rows, and so does the span `(153, 153)` — both recomputed this round
  (`validate_ledger_structural.py:179-180`).

## Reasoning

`required_evidence` enumerates two items:

| `evidence_id` | `evidence_type` | `proof_mode` | `status` | refs | `approval_ids` |
|---|---|---|---|---|---|
| `REQ-PG-1-04-ACCEPTANCE` | `ARTIFACT` | `CONTENT_HASH` | `UNRESOLVED` | `[]` | `[]` |
| `REQ-PG-1-04-COMMAND-PROOF` | `COMMAND_RESULT` | `COMMAND` | `UNRESOLVED` | `[]` | `[]` |

The acceptance item's `description` was recomputed this round and is byte-equal
to `"Current proof satisfying: "` concatenated with this row's exact
`required_acceptance_text`. Every item is `UNRESOLVED` with
`evidence_ref_ids=[]`, which goal L483-484 requires ("An unresolved item has no
evidence refs") and which is the correct state for a component at
`delivery_status=INVENTORIED`.

**Clause-by-clause coverage — two obligations, two items, and the split is
correct.** "Missing inputs fail closed" asserts a **runtime behaviour**, not a
document property, so it needs both:

- `REQ-PG-1-04-ACCEPTANCE` (`ARTIFACT`/`CONTENT_HASH`) binds the current
  specification/implementation bytes that define the fail-closed behaviour, scope
  "PG-1-04 acceptance and delivery scope".
- `REQ-PG-1-04-COMMAND-PROOF` (`COMMAND_RESULT`/`COMMAND`), "Reproducible command
  result proving the current PG-1-04 acceptance obligation", scope "PG-1-04
  command proof". This is the item that makes the behaviour provable rather than
  merely described. Register C-08's acceptance is explicit that the behaviour is
  tested — "reconciliation traces **pass tests and fail closed**" — so a command
  obligation is source-required here, and it is present.

Goal L265-272 is directly on point for this kind: an aggregated `REQUIRED_NOW`
phase-gate clause carries no activation predicate, and "the observable
conjunction that a predicate would have carried lives instead in the exact
`scope` of that component's **command-proof obligation**". This row has that
obligation, with the scope string the contract expects.

**Is a third item owed?** I looked for one and found none. The clause names no
approval or acceptance authority, so no `TYPED_APPROVAL` item (goal L485-487);
`REG-C-08` itself carries only the delegated specification approval, so there is
no non-delegated authority in the neighbourhood to have been dropped. There is no
second behaviour in the clause — "missing inputs fail closed" is a single
predicate, unlike `PG-1-06`'s two conjuncts, which is exactly why that row carries
three items and this one carries two.

**No `REVIEW` item is owed, and I checked the invariant rather than assuming
it.** On 123 of the 169 canonical rows a `DELEGATED_ARTIFACT_APPROVAL` is paired
with a `REQUIRED_EVIDENCE` item `REQ-<CID>-SPEC-REVIEW` ("Persisted clean fresh
Sol xhigh review of the current specification bytes"). The 46 rows that carry no
delegated approval — all 35 `phase_gate_clause` rows, all 6
`document_strategy_clause` rows, all 4 `authority_clause` rows, and `SEQ-11` —
carry no such item, and none of them carries the item without the approval. This
row is in that set. The reason is structural rather than conventional: a
`DELEGATED_ARTIFACT_APPROVAL` is scoped to a specification artifact
(`"<X> under <Sxx>: …"`), and a `phase_gate_clause` has `primary_spec=null` and
cannot carry `applicable_spec_ids` at all (goal L230-232 makes it a rejected
key). With no owned spec artifact there is no artifact whose persisted review
could be required. So the absence is correct here, and it is *not* the open
Important finding 1 of
`docs/goals/reviews/ledger/equity-os-blueprint-evidence-inventory-r0.md`, which
concerns the 32 disposition rows that **do** carry the delegated approval.

**`verification_command` = `{"mode": "UNRESOLVED", "commands": [],
"not_applicable_review": null}`.** Not merely permitted — required at this stage.
Goal L501-502 says `UNRESOLVED` "has no commands, review, results, or
`verified_at` and is valid during initial ledger construction only", and
`validate_ledger_structural.py:2258-2262` enforces exactly that shape on the
`UNRESOLVED` branch — `commands == []`, `not_applicable_review is None`,
`verification_result == []`, `verified_at is None` — all four of which hold on
this row, whose `delivery_status` is `INVENTORIED`. The HR-0004 transaction pin
at `:3083-3084` additionally asserts `UNRESOLVED` on **every** row of the
post-transaction ledger, so the value is currently fixed program-wide. It is
therefore not an
evidence gap, and it is not a substitute for classification either: the
`COMMAND` proof mode on a `required_evidence` item is what declares a mechanical
obligation, and `verification_command` is where the concrete argv lands later. The `COMMAND` requirement above is the declaration of the
obligation; the argv lands in `verification_command` at a later stage, and the
two are not substitutes.

**`evidence_refs`.** One object, `EV-PG-1-04-SOURCE`, a
`UTF8_LINE_SPAN` binding to register v2 L153-153 with scope "Exact authoritative source occurrence for PG-1-04".
I re-hashed it against current bytes: `301f510a422dcd06974fe1c7e2dfbc542af662e82a7333f7911355f4182006f4`, equal to
the stored `content_sha256`. Every one of the 35 phase-gate rows carries exactly
one evidence ref and it is always its own source span, so nothing on this row is
missing a binding it would otherwise have.

**Provenance of the command item, checked.** This row's `human_review_id` is
`HR-0004`. `PG-1-04` is inside HR-0004's affected-component set in
`docs/goals/equity-os-blueprint-human-review-needed.md` (L334), alongside
`PG-05-08`, `PG-1-05`, `PG-1-06`, `PG-2-03`, and `PG-2-04` — precisely the six §F
clauses the program-level evidence-inventory review's Critical finding 2 named as
having "explicit test/replay/demonstration obligations" and no command evidence.
The finding named this row, the reconciliation remediated this row, and the item
is present with the expected shape. I verified the presence and shape directly
rather than inferring them from the reconciliation record.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition, and it
satisfies no evidence item (goal L494-495). It records only that this
component's `required_evidence` inventory is complete at the input bytes pinned
above.
