# Inventory review — PG-0A-04 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `PG-0A-04` |
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
{"activation_predicate":null,"disposition_refs":[],"gate_refs":[],"related_register_ids":["A-06"],"scope_derivation":{"authority_effect":null,"derived_program_disposition":"REQUIRED_NOW","related_register_ids":["A-06"],"rule":"RELATED_REGISTER_SCOPE"}}
```

Digests observed at review time, **pre-record** (the recorder recomputes
`reviewed_input_sha256` after its Phase A evidence append, recording design r2
§3.4 — appending review evidence mutates `evidence_refs` and therefore the input
projection):

- `reviewed_input_sha256` (pre-record): `e4f6f32b974ced17b33ee7dd82ff0447833524428f610f17dff3f5b422f23ffe`
- `reviewed_inventory_sha256` (pre-record): `237dc7ce95b8c2c058b6e158bf18a14b4b65799a69630a6a3efbbd8caa44b463`

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

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line 129,
under `### Phase 0A may exit only when` (register v2 L124), inside `## F. Phase-gate scorecard` (L122); `source_title` "Phase 0A gate clause 4",
`source_anchor` `F-0A-04`:

> - the filing-channel-aware XBRL/PDF spike is complete;

Recomputed this round against current bytes:

- `source_hash` over the whole register file → `26d51b31…`, equal to the stored value.
- `text_digest` over the normalized L129-129 span (`"\n".join(lines[128:129]).strip(" \t\n\r\f\v")`,
  the exact rule at `validate_ledger_structural.py:174-176`) → `32bf518aef5b569586f4925b5814b82f7993976d80356a08ea06b6fca08837fa`,
  equal to the stored value.
- `EV-PG-0A-04-SOURCE.content_sha256` recomputed over the same span → `32bf518aef5b569586f4925b5814b82f7993976d80356a08ea06b6fca08837fa`,
  equal to the stored value.
- `required_acceptance_text` equals that span with the `- ` list marker and the
  terminal `;` removed, byte for byte.
- Anchor uniqueness holds ledger-wide: `(funda-blueprint-implementation-decision-register-v2.md, F-0A-04)` occurs once
  across all 213 rows, and so does the span `(129, 129)` — both recomputed this round
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

**`related_register_ids` = `["A-06"]`, checked on the merits.** A-06 (register
L36) is "Run filing-channel-aware XBRL-versus-PDF spike". The clause is "the
filing-channel-aware XBRL/PDF spike is complete". The distinguishing adjective
"filing-channel-aware" appears verbatim in both, and A-06 is the only register
row in the whole v2 register containing the string "spike". This is the least
ambiguous mapping in the Phase 0A block.

**Contrary candidates, considered and rejected.** A-06 has three downstream
consumers — `B-05` and `B-11` list A-06 as a dependency, and `C-17` does too.
None belongs here: the clause gates the *spike*, not what is derived from it, and
each consumer has its own home (`B-05` → `PG-05-07` and `PG-1-03`, `B-11` →
`PG-05-06`; `C-17` is claimed by no gate at all, which is a §F source fact, not a
derivation defect — §F simply has no bullet for the entity/security master).

**Back-reference verified.** `REG-A-06.gate_refs == ["PG-0A-04"]` exactly; A-06
is claimed by this gate and no other.

**Aggregation → `REQUIRED_NOW`.** `REG-A-06` is `REQUIRED_NOW`
(`source_status=Open`), so the single-element aggregate is `REQUIRED_NOW` under
goal L248-250. Stored `derived_program_disposition` and `program_disposition`
both match.

**`disposition_refs` = `[]`.** I checked the populated populations rather than
assuming. Across the 169 canonical rows `disposition_refs` is nonempty on exactly
three closed sets — the 32 `disposition_item` self-identifications, 56
`register_row` crosswalk entries, and the 8 `SCALE-*` rows — and empty on all 73
rows of the remaining four kinds, including all 35 phase-gate clauses. The
convention is that a disposition-report finding is crosswalked to the *register
decisions* it changes, and a gate clause inherits that linkage through its
related registers rather than duplicating it: here `A-06` → `M-9`, `R-2`. That inheritance
is live — for example the disposition report's own T-2 (L274, "Success metrics
are scattered") ends "All phase gates should reference this contract" (L291) and
is carried on `A-07`, `A-12`, and `A-13`, reached from the gate side through
`related_register_ids`. Duplicating those IDs onto this row would mix the two
axes goal L233-235 keeps apart, and would not be an exact source semantic of this
clause. Note that R-2 (disposition report L325,
"Add filing channel and taxonomy version to A-06") is the finding that *created*
this clause's distinguishing adjective; it is carried on `A-06`, where the
register change landed, and reaches this gate through the related-register edge.

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

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that this component's scope derivation is correct at the input bytes pinned
above.
