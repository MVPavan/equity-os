# Inventory review — PG-0A-05 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `PG-0A-05` |
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
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"99fc48702b6d6c27d6c4977ef188e96e6ec901beb5c738683a4c6ae9e8a14a2d","digest_mode":"UTF8_LINE_SPAN","end_line":130,"evidence_ref_id":"EV-PG-0A-05-SOURCE","path":"docs/blueprint/funda-blueprint-implementation-decision-register-v2.md","scope":"Exact authoritative source occurrence for PG-0A-05","start_line":130}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: materiality and success-metric contracts are versioned","evidence_id":"REQ-PG-0A-05-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"PG-0A-05 acceptance and delivery scope","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (the recorder recomputes
`reviewed_input_sha256` after its Phase A evidence append, recording design r2
§3.4 — appending review evidence mutates `evidence_refs` and therefore the input
projection):

- `reviewed_input_sha256` (pre-record): `a3dba5caddc9b012345cd5270eefa3b2d2a1c5e08dc8dfcb5c2aa71917ec0593`
- `reviewed_inventory_sha256` (pre-record): `62f455e40934b2ce012557069f14795838f5ac3c842895083550b087a0d496c6`

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

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line 130,
under `### Phase 0A may exit only when` (register v2 L124), inside `## F. Phase-gate scorecard` (L122); `source_title` "Phase 0A gate clause 5",
`source_anchor` `F-0A-05`:

> - materiality and success-metric contracts are versioned;

Recomputed this round against current bytes:

- `source_hash` over the whole register file → `26d51b31…`, equal to the stored value.
- `text_digest` over the normalized L130-130 span (`"\n".join(lines[129:130]).strip(" \t\n\r\f\v")`,
  the exact rule at `validate_ledger_structural.py:174-176`) → `99fc48702b6d6c27d6c4977ef188e96e6ec901beb5c738683a4c6ae9e8a14a2d`,
  equal to the stored value.
- `EV-PG-0A-05-SOURCE.content_sha256` recomputed over the same span → `99fc48702b6d6c27d6c4977ef188e96e6ec901beb5c738683a4c6ae9e8a14a2d`,
  equal to the stored value.
- `required_acceptance_text` equals that span with the `- ` list marker and the
  terminal `;` removed, byte for byte.
- Anchor uniqueness holds ledger-wide: `(funda-blueprint-implementation-decision-register-v2.md, F-0A-05)` occurs once
  across all 213 rows, and so does the span `(130, 130)` — both recomputed this round
  (`validate_ledger_structural.py:179-180`).

## Reasoning

`required_evidence` enumerates one item:

| `evidence_id` | `evidence_type` | `proof_mode` | `status` | refs | `approval_ids` |
|---|---|---|---|---|---|
| `REQ-PG-0A-05-ACCEPTANCE` | `ARTIFACT` | `CONTENT_HASH` | `UNRESOLVED` | `[]` | `[]` |

The acceptance item's `description` was recomputed this round and is byte-equal
to `"Current proof satisfying: "` concatenated with this row's exact
`required_acceptance_text`. Every item is `UNRESOLVED` with
`evidence_ref_ids=[]`, which goal L483-484 requires ("An unresolved item has no
evidence refs") and which is the correct state for a component at
`delivery_status=INVENTORIED`.

**Clause-by-clause coverage — this clause is a conjunction, and I checked that a
single item can carry it.** The clause has two conjuncts: the materiality
contract is versioned (A-10) and the success-metric contract is versioned (A-13).
The single acceptance item's description quotes the whole clause verbatim, so
both conjuncts are inside its scope, and both are the same kind of proof —
versioned document bytes. Goal L492-495 requires every source-required acceptance
item to be "represented and classified by proof mode"; it does not require one
`required_evidence` object per grammatical conjunct when the conjuncts share a
proof mode and a scope. Contrast `PG-1-06`, whose two conjuncts have *different*
proof modes (mechanical replay versus a human narrative approval) and which
therefore correctly carries three items. Here both conjuncts are
`ARTIFACT`/`CONTENT_HASH`, and a split would produce two items with identical
type, mode, status, and scope.

**No `COMMAND` item is owed — but this is the near-miss in the Phase 0A block, so
I checked it directly.** A-10's acceptance column ends "validator test cases
**approved**", which is a mechanical obligation, and `REG-A-10` accordingly
carries `REQ-REG-A-10-COMMAND-PROOF` (`COMMAND_RESULT`/`COMMAND`) — one of only
25 `COMMAND` requirements in the ledger. That obligation belongs to A-10's own
register row, not to this gate: the gate clause says only that the contracts "are
versioned", and goal L494 scopes an evidence-inventory review to what the
**source-required** acceptance items are for *this* component's clause. Importing
A-10's test-case obligation here would also be an inference across components
that goal L439 works against ("evidence must be current and component-local").
The obligation is inventoried, on the row whose source text demands it.

**No `TYPED_APPROVAL` item is owed.** `required_approvals` is empty here, so a
typed item would name nothing (goal L485-487). Note that both related registers
do carry non-delegated authorities — `REG-A-10` a `DOMAIN_EXPERT_ACCEPTANCE`,
`REG-A-13` a `PRODUCT_OWNER_DECISION` — and this component carries neither;
whether that is correct is this component's `APPROVAL` review's decision, and it
is decided there.

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
obligation, and `verification_command` is where the concrete argv lands later.

**`evidence_refs`.** One object, `EV-PG-0A-05-SOURCE`, a
`UTF8_LINE_SPAN` binding to register v2 L130-130 with scope "Exact authoritative source occurrence for PG-0A-05".
I re-hashed it against current bytes: `99fc48702b6d6c27d6c4977ef188e96e6ec901beb5c738683a4c6ae9e8a14a2d`, equal to
the stored `content_sha256`. Every one of the 35 phase-gate rows carries exactly
one evidence ref and it is always its own source span, so nothing on this row is
missing a binding it would otherwise have.

**Corroboration, treated as corroboration only.** `PG-0A-05` appears in neither
list of the program-level evidence-inventory review and is absent from HR-0004's
affected set (`human_review_id` is `null`). Independent reading and prior review
agree.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition, and it
satisfies no evidence item (goal L494-495). It records only that this
component's `required_evidence` inventory is complete at the input bytes pinned
above.
