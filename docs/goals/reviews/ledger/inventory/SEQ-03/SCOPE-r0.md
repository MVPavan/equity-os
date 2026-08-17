# Inventory review — SEQ-03 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `SEQ-03` |
| `review_type` | `SCOPE` |
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

`review_inventory_projection(row, "SCOPE")` — canonical JSON, extracted from the
checked-in structural validator by `ast` (recording design r2 §3.3) so the
projection is the validator's own, not a transcription:

```json
{"activation_predicate":null,"disposition_refs":[],"gate_refs":[],"related_register_ids":[],"scope_derivation":{"applicable_spec_ids":["S05","S09"],"authority_effect":null,"derived_program_disposition":"REQUIRED_NOW","related_register_ids":[],"rule":"PROGRAM_WIDE_ACTIVE_CONTROL","source_register_ids":["A-02","A-06"]}}
```

Digests observed at review time, **pre-record** (the recorder recomputes
`reviewed_input_sha256` after Phase A, recording design r2 §3.4):

- `reviewed_input_sha256` (pre-record): `bf75467e141b1b7609d92bfee768249598cbf8edb7a361778ccb58fe67844de0`
- `reviewed_inventory_sha256` (pre-record): `3030677da7c0d155f417eb4fb77c7beb7fa307ae1a7de260121e34aa0cff106a`

## Scope of this decision

Per recording design r2 §2.2 and the `SCOPE` review definition, this review
decides whether this component's scope derivation is correct: right kind, right
source anchor, right related register IDs, right disposition and gate refs, and
whether `scope_derivation.semantic_review` is the applicable review slot. The
`SCOPE` inventory projection (`validate_ledger_structural.py:293-305`) covers
`scope_derivation` minus `semantic_review`, `disposition_refs`, `gate_refs`,
`activation_predicate`, and `related_register_ids` — so for a `sequence_clause`
it also covers the kind-specific keys `source_register_ids` and
`applicable_spec_ids` (goal L230-231). It does **not** cover `required_evidence`,
`evidence_refs`, or `required_approvals`; those are decided by this component's
separate `EVIDENCE` and `APPROVAL` reviews.

## The source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` line 453, within
`## 8. Recommended sequence` (L447); `source_title` "Recommended sequence step 3", `source_anchor`
`SEQUENCE-03`:

> 3. **A-02 and A-06:** select the discovery company, four consecutive quarters, and run the channel-aware XBRL/PDF spike.

`text_digest` and `EV-SEQ-03-SOURCE.content_sha256` were both recomputed over the
normalized L453-453 span → `b2d83fec…`, matching the stored values, and
`source_hash` recomputed over the whole disposition report → `a9021c15…`, matching.

## Reasoning

**Kind and derivation rule.** `sequence_clause` is correct: the occurrence is a
numbered step of the disposition report's `## 8. Recommended sequence` (L447),
introduced by "The clean sequence is:" (L449). It is not a `disposition_item`
(those are the `### <id> — <title>` findings with an explicit
"**Disposition:**" verdict, and carry `rule=AUTHORITATIVE_OCCURRENCE`), not a
`phase_gate_clause` (it states no exit condition), and not a `register_row` (it
has no register ID, priority, or Status cell; `register_id`, `priority`, and
`source_status` are all `null`). Goal L244 fixes the rule for the kind as
`PROGRAM_WIDE_ACTIVE_CONTROL`, and goal L247 makes that rule always derive
`REQUIRED_NOW` with no related register IDs; `validate_ledger_structural.py:1512`
and `:2499-2506` assert exactly that. The stored values match, and the
substantive check the rule leaves open passes: a recommended program sequence
orders the whole program, so it is program-wide by construction rather than
scoped to any one register decision.

**`related_register_ids` = `[]`, and why that is not a loss.** This is the one
place a sequence clause is easy to get wrong, because the clause visibly names
register IDs. Goal L233-235 keeps the two axes apart: `related_register_ids` is
*source semantics* and `applicable_spec_ids` is *artifact applicability*, and
"neither may be padded or inferred from the other". `PROGRAM_WIDE_ACTIVE_CONTROL`
forbids related register IDs outright (goal L247), so the register IDs the clause
names are carried in the kind-specific `source_register_ids` key instead
(goal L230-231). The information is therefore preserved, in the field the
contract assigns to it, and `[]` here is required rather than merely permitted.

**`source_register_ids` = `["A-02","A-06"]`, verified against the clause.** The
clause carries two obligations matching its two IDs: "select the discovery
company, four consecutive quarters" is `A-02`; "run the channel-aware XBRL/PDF
spike" is `A-06`. `validate_ledger_structural.py:2482` pins the same pair, and the
stored value matches after sorting. This row is one of the four repaired by the
`applicable_spec_ids` half of scope-derivation finding 6; the repair is confirmed
here against the clause text.

**`applicable_spec_ids` = `["S05","S09"]`, resolved independently.** `A-02` is
inventoried on `REG-A-02`, approval scope
`"A-02 under S05: Select one discovery company and four consecutive quarters"`,
spec draft `docs/specs/equity-os-s05-discovery-company-vertical-slice.md` ⇒ `S05`.
`A-06` is inventoried on `REG-A-06`, approval scope
`"A-06 under S09: Run filing-channel-aware XBRL-versus-PDF spike"`, spec draft
`docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md` ⇒ `S09`.
The closure `{S05, S09}` matches the stored list exactly. The split is
substantive: company/quarter selection is vertical-slice scope, while the
filing-channel spike is ingestion scope, and the clause requires both at step 3.

**The derivation is right; the downstream inventory does not follow it.** Only
`S05` has current artifact evidence on this row and only `S05` is covered by an
enumerated obligation. That is outside the `SCOPE` projection and is recorded as a
finding in this component's `EVIDENCE` and `APPROVAL` reviews, neither of which is
clean. The scope derivation itself is complete and correct.

**Source anchor and span.** `SEQUENCE-03` at L453-453. `text_digest` recomputed
over the normalized span → `b2d83fec…`, matching; `required_acceptance_text`
equals that span byte for byte. Anchor and span unique within the source path.

**`disposition_refs` and `gate_refs`, both `[]`.** `gate_refs` is a
register-row-only field: it is pinned by the `gate_map` equality at
`validate_ledger_structural.py:2655-2664`, which computes it from
`phase_gate_clause` rows and compares it only against `register_rows`; all 109
non-register canonical rows carry `[]`. For `disposition_refs` I checked the
populated populations rather than assuming: it is nonempty on exactly three
closed sets — 56 register rows via the curated crosswalk, the 32 `DISP-*`
self-identifications, and the 8 `SCALE-*` rows pinned at `:2652-2653`. All 73
other canonical rows, including every sequence clause, carry `[]`. Section 8 of
the disposition report is a recommendation section, not a numbered finding, so
there is no `<id>` for a sequence step to reference. `[]` is correct.

**`activation_predicate` = `null`.** Required: goal L288-290 permits an
activation predicate only on a component that is not already `REQUIRED_NOW`, and
`PROGRAM_WIDE_ACTIVE_CONTROL` forces `REQUIRED_NOW`. `activation_record` and
`activation_source_status` are likewise `null`.

**Applicable review slot.** This is a non-register canonical row, so
`validate_ledger_preimplementation.py:200-204` appends `SCOPE` to its checks
(`SCOPE` is appended only `if row["kind"] != "register_row"`).
`scope_derivation.semantic_review` is present, non-`null`, `status=PENDING`, with
exactly the 10-key `PENDING` set and no role-binding keys. It is the applicable
slot, and it is the slot this review is written against.

**Cross-check.** `derived_program_disposition` = `program_disposition` =
`REQUIRED_NOW`; `authority_effect` `null`.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `SEQ-03`'s scope derivation is correct at the input bytes pinned
above.
