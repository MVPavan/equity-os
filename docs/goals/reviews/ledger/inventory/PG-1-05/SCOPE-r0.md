# Inventory review — PG-1-05 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `PG-1-05` |
| `review_type` | `SCOPE` |
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

`review_inventory_projection(row, "SCOPE")` — canonical JSON. The projection
function was extracted from the checked-in structural validator by `ast`
(recording design r2 §3.3), so the bytes below are the validator's own
projection, not a transcription:

```json
{"activation_predicate":null,"disposition_refs":[],"gate_refs":[],"related_register_ids":["C-15"],"scope_derivation":{"authority_effect":null,"derived_program_disposition":"REQUIRED_NOW","related_register_ids":["C-15"],"rule":"RELATED_REGISTER_SCOPE"}}
```

Digests observed at review time, **pre-record** (the recorder recomputes
`reviewed_input_sha256` after its Phase A evidence append, recording design r2
§3.4 — appending review evidence mutates `evidence_refs` and therefore the input
projection):

- `reviewed_input_sha256` (pre-record): `66696e7877c345c9b8ed0ba54174c83c5c1860bed7023157e297942c1f3da8ba`
- `reviewed_inventory_sha256` (pre-record): `780f7dc942f7946dcfe8dff1c944bef432fc40a65c94e31a443f8e2e6283c9ec`

## Scope of this decision

Per recording design r2 §2.2 and the `SCOPE` review definition, this review
decides whether this component's scope derivation is correct: right kind, right
source anchor, right related register IDs, right disposition and gate refs, and
whether `scope_derivation.semantic_review` is the applicable review slot. The
`SCOPE` inventory projection (`validate_ledger_structural.py:292-305`, goal
L431-432) covers `scope_derivation` minus `semantic_review`, `disposition_refs`,
`gate_refs`, `activation_predicate`, and `related_register_ids`. For a
`phase_gate_clause` the kind-specific keys `applicable_spec_ids` and
`source_register_ids` are *rejected* keys (goal L230-232), so the derivation
object is exactly the four common keys. This review does **not** cover
`required_evidence`, `evidence_refs`, or `required_approvals`; those are decided
by this component's separate `EVIDENCE` and `APPROVAL` reviews.

## The source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line 154,
under `### Phase 1 may exit only when` (register v2 L148), inside `## F. Phase-gate scorecard` (L122); `source_title` "Phase 1 gate clause 5",
`source_anchor` `F-1-05`:

> - post-cutoff data are excluded by tested store/tool controls;

Recomputed this round against current bytes:

- `source_hash` over the whole register file → `26d51b31…`, equal to the stored value.
- `text_digest` over the normalized L154-154 span (`"\n".join(lines[153:154]).strip(" \t\n\r\f\v")`,
  the exact rule at `validate_ledger_structural.py:174-176`) → `66611d4eb86eb74858bd72109eeaa8dce34fcf4b7d7f7bf6431d292c4c4c8a3a`,
  equal to the stored value.
- `EV-PG-1-05-SOURCE.content_sha256` recomputed over the same span → `66611d4eb86eb74858bd72109eeaa8dce34fcf4b7d7f7bf6431d292c4c4c8a3a`,
  equal to the stored value.
- `required_acceptance_text` equals that span with the `- ` list marker and the
  terminal `;` removed, byte for byte.
- Anchor uniqueness holds ledger-wide: `(funda-blueprint-implementation-decision-register-v2.md, F-1-05)` occurs once
  across all 213 rows, and so does the span `(154, 154)` — both recomputed this round
  (`validate_ledger_structural.py:179-180`).

## Reasoning

**Kind.** `phase_gate_clause` is correct. The occurrence is a bullet in the
register's `## F. Phase-gate scorecard` (L122) under a `### Phase … may exit
only when` heading — i.e. a phase exit condition. It is not a `register_row`
(no ID / Priority / Status cells; `register_id`, `priority`, `source_status`,
and `activation_source_status` are all `null`, as the kind requires), not a
`disposition_item` (those are `### <id> — <title>` findings in the disposition
report carrying an explicit "**Disposition:**" verdict and
`rule=AUTHORITATIVE_OCCURRENCE`), and not a `sequence_clause` (those are the
numbered steps of the disposition report's `## 8. Recommended sequence`). Goal
L141 fixes the population as "One object per bullet in v2 §F", count 35;
`validate_ledger_structural.py:362` pins that count and I recounted 35 this
round.

**Rule.** Goal L239 permits exactly two rules for this kind:
`RELATED_REGISTER_SCOPE` or `ACTIVE_NEGATIVE_CONTROL`. `ACTIVE_NEGATIVE_CONTROL`
is wrong here: goal L263-264 defines it as a control that "activates no
capability: it proves that named capabilities stay dormant or rejected", and the
one clause in §F with that shape is `PG-1-11` (L160, "GBrain, debate,
backtesting, and execution remain outside the release unless separately
approved"), which is indeed the only row in the ledger carrying it. This clause
requires a capability to be *delivered*, not to stay out, so
`RELATED_REGISTER_SCOPE` is the correct and only remaining rule.
`authority_effect` is `null`, which `RELATED_REGISTER_SCOPE` requires
(`validate_ledger_structural.py:1550-1551`).

**`related_register_ids` = `["C-15"]`, matched phrase by phrase.** C-15 (register
L86) is "Enforce run knowledge cutoff across **stores and tools**", acceptance
"SQL/document/memory retrieval applies `knowledge_time <= cutoff`; canonical
selections are resolved as of the cutoff so later restatements/corrections do not
rewrite history; tool gateway records cutoff capability; **tests insert and reject
post-cutoff records**". The clause is "post-cutoff data are excluded by tested
store/tool controls". Every element lines up: "post-cutoff" ↔ "post-cutoff
records"; "store/tool controls" ↔ "stores and tools" / "tool gateway"; "tested" ↔
"tests insert and reject". C-15 is the only register decision about the knowledge
cutoff in Phase 1.

**Contrary candidates, considered and rejected.** `E-10` ("Publish
historical-replay leakage policy") is the other leakage-facing decision and lists
C-15 as its dependency, but it is a Phase 3 `Deferred` row, so relating it would
also change the aggregation (goal L248-251 would then have to consider a dormant
row) and would import deferred scope into a Phase 1 gate. `C-02` and `C-03` are
C-15's dependencies, not the control the clause names. Both rejected as
inference.

**Back-reference verified.** `REG-C-15.gate_refs == ["PG-1-05"]` exactly — a
one-to-one gate/register relation confirmed from both ends, with the `gate_map`
equality holding.

**Aggregation → `REQUIRED_NOW`.** `REG-C-15` is `REQUIRED_NOW`
(`source_status=Open`); single-element aggregate is `REQUIRED_NOW`. Stored values
agree. I note that `E-10`, had it been related, is `Deferred`, which is precisely
why the exactness of this single-element set is load-bearing for the derived
disposition and not merely tidy.

**`disposition_refs` = `[]`.** I checked the populated populations rather than
assuming. Across the 169 canonical rows `disposition_refs` is nonempty on exactly
three closed sets — the 32 `disposition_item` self-identifications, 56
`register_row` crosswalk entries, and the 8 `SCALE-*` rows — and empty on all 73
rows of the remaining four kinds, including all 35 phase-gate clauses. The
convention is that a disposition-report finding is crosswalked to the *register
decisions* it changes, and a gate clause inherits that linkage through its
related registers rather than duplicating it: here `C-15` → `G-1`, `M-4`, `6.9`. That inheritance
is live — for example the disposition report's own T-2 (L274, "Success metrics
are scattered") ends "All phase gates should reference this contract" (L291) and
is carried on `A-07`, `A-12`, and `A-13`, reached from the gate side through
`related_register_ids`. Duplicating those IDs onto this row would mix the two
axes goal L233-235 keeps apart, and would not be an exact source semantic of this
clause. M-4 (disposition report L182,
"Knowledge-time enforcement and leakage") is the finding this clause exists to
close, and it is carried on C-15.

**`gate_refs` = `[]`.** `gate_refs` is a register-side back-reference, not a
self-reference. `validate_ledger_structural.py:2659-2666` builds `gate_map` *from*
`phase_gate_clause` rows' `related_register_ids` and asserts equality only
against `register_rows`; nothing constrains `gate_refs` on a non-register row. I
recomputed the map this round: 39 register rows carry gate refs, the map matches
every one of them exactly, and **0 of the 109 non-register canonical rows carry
any**. `[]` is the correct and uniform value here.

**`activation_predicate` = `null`.** Required, not optional. Goal L288-290: "A
component whose derived disposition is `REQUIRED_NOW` — including one that became
`REQUIRED_NOW` by related-register aggregation — has `activation_predicate=null`",
and goal L265-267 repeats it for this kind specifically. `activation_record` and
`activation_source_status` are likewise `null`. Goal L292-294 forbids any
"phase-gate exemption" to this rule, so the value is forced.

**Applicable review slot.** This is a non-register canonical row, so
`validate_ledger_preimplementation.py:200-204` appends `SCOPE` to its checks
(`SCOPE` is appended only `if row["kind"] != "register_row"`).
`scope_derivation.semantic_review` is present, non-`null`, `status=PENDING`, with
exactly the 10-key `PENDING` set and no role-binding keys — verified this round.
It is the applicable slot, and it is the slot this review is written against.

**Spec ownership.** `primary_spec` is `null`, which goal L184 permits "only when
`scope_derivation` explicitly supplies program-wide or related-register
ownership" — `RELATED_REGISTER_SCOPE` supplies exactly that. `applicable_spec_ids`
is absent because goal L230-232 makes it a *rejected* key for every kind except
`disposition_item` and `sequence_clause`; the validator enforces the exact key set
at `:1519-1520`. So this gate owns no spec artifact, and cannot.

**One field deliberately outside this decision.** `human_review_id = "HR-0004"`
sits in the `APPROVAL` inventory projection (goal L435-436), not the `SCOPE` one,
and is decided by this component's `APPROVAL` review.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that this component's scope derivation is correct at the input bytes pinned
above.
