# Inventory review — PG-2-01 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `PG-2-01` |
| `review_type` | `EVIDENCE` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `c43733f6-8986-4487-8aa6-2f7b5b723107` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-16T03:52:19Z` |

Role binding: `CONTEXT.md` "Agent roles (harness-wide)" L137-139 and L147 bind
`REVIEWER` to Claude Opus 5 at high effort, independent of any `IMPLEMENTER`
that produced the reviewed content.

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

`review_inventory_projection(row, "EVIDENCE")` — canonical JSON:

```json
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"49518e1c2f8439fbc01285087b7e5efbb6bf9e25cdedf0d7dc631dcb000086f4","digest_mode":"UTF8_LINE_SPAN","end_line":164,"evidence_ref_id":"EV-PG-2-01-SOURCE","path":"docs/blueprint/funda-blueprint-implementation-decision-register-v2.md","scope":"Exact authoritative source occurrence for PG-2-01","start_line":164}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: the selected memory approach improves measurable current-scale workflow outcomes","evidence_id":"REQ-PG-2-01-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"PG-2-01 acceptance and delivery scope","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 —
appending review evidence mutates `evidence_refs` and therefore the input
projection):

- `reviewed_input_sha256` (pre-record): `523ee731b034adbcd11f5dc75133d054afdba5e4e982761fe1618cc8cd480c93`
- `reviewed_inventory_sha256` (pre-record): `0dbdcd7c6be58c5e1de770002d27f16dcf467d189707bdac9ecf80610ef468fa`

## Scope of this decision

Goal L492-494: a `COMPLETE` clean `REVIEWER`-role evidence review "proves that
every source-required acceptance item is represented and classified by proof
mode; it does not satisfy an evidence item." This review decides **completeness
of the obligation list only**. Every item on this row is legitimately
`UNRESOLVED` with empty `evidence_ref_ids` (goal L484: "An unresolved item has
no evidence refs") — that is not a finding.

## The source clause, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md`
L164, the first bullet under `### Phase 2 may exit only when`
(L162), inside `## F. Phase-gate scorecard` (L122):

> - the selected memory approach improves measurable current-scale workflow outcomes;

- `source_hash` recomputed over the whole register file → `26d51b31…`, matches
  the stored value.
- `text_digest` recomputed over the normalized L164 span →
  `49518e1c2f8439fbc01285087b7e5efbb6bf9e25cdedf0d7dc631dcb000086f4`, equal to
  the stored `text_digest` and to `EV-PG-2-01-SOURCE.content_sha256`.
- `required_acceptance_text` equals that bullet with the list marker and the
  terminal punctuation stripped, byte for byte.

## Reasoning

**What the clause actually demands.** One comparative result: that the selected
memory approach improves measurable current-scale workflow outcomes. It is a
single evaluative finding over `D-02`'s benchmark output, not a set of separable
obligations, and `REQ-PG-2-01-ACCEPTANCE` (`ARTIFACT`/`CONTENT_HASH`,
description quoting the clause verbatim, scope "PG-2-01 acceptance and delivery
scope") carries it. `CONTENT_HASH` over an `ARTIFACT` is the right proof mode:
the thing to bind is the benchmark report's bytes.

**Granularity is a ledger-wide convention, not a per-row choice.** Every
canonical row but one carries exactly one `REQ-<component_id>-ACCEPTANCE`
`ARTIFACT`/`CONTENT_HASH` item quoting the full acceptance text — 168 such items
across 169 canonical rows, the single exception being `DISP-R-1`, whose
acceptance item was deliberately replaced by the `NO-IMPLEMENTATION`
requirement. Multi-clause acceptance texts are never split into per-phrase
items anywhere in the ledger. So a second item on this row would have to be a
*different kind of proof*, not a fragment of the same text.

**Predicate evidence is not a `required_evidence` obligation — checked, not
assumed.** Every metric on this row is `EVIDENCE_JSON` and will eventually need
a `FILE_BYTES` evidence object to point at, so it is fair to ask whether an
item is missing for it. It is not. Goal L342-343 makes that evidence an
**activation** precondition ("Activation requires a current recomputed `TRUE`,
nonempty current predicate evidence when any `EVIDENCE_JSON` metric is used"),
delivered through `evidence_refs` and recorded in
`activation_record.predicate_evidence_ref_ids` (goal L361-363) — not through
`required_evidence`. I confirmed the convention holds ledger-wide: of the 20
canonical rows carrying an activation predicate, **none** carries a
predicate-evidence `required_evidence` item, and the only non-`ACCEPTANCE` items
those rows carry are `SPEC-REVIEW`, `COMMAND-PROOF`, and typed-approval items.
Inventing one here would be a shape the contract does not define.

**`COMMAND_RESULT` / `COMMAND` — checked, correctly absent, and in fact
forbidden.** The command-proof population is pinned as an exact set *equality*,
not a lower bound: goal L3989-4003 and `validate_ledger_structural.py:2635-2649`
assert `actual_command_proof_components == EXPECTED_COMMAND_PROOF_COMPONENTS`
over 25 named rows. The phase-gate members of that set are `PG-05-08`,
`PG-1-04`, `PG-1-05`, `PG-1-06`, `PG-2-03`, and `PG-2-04`. `PG-2-01` is not among
them, so adding a `COMMAND_RESULT` item here would make the actual set a strict
superset and fail structural validation outright. The review question is
therefore not "could someone write a command for this clause" but "does the
contract demand one" — and the contract both declines to demand it and forbids
it.

**The one goal sentence that could be read to demand one, and why it does
not.** Goal L266-272 says that an "aggregated `REQUIRED_NOW` phase-gate clause
carries no activation predicate; the observable conjunction that a predicate
would have carried lives instead in the exact `scope` of that component's
command-proof obligation." Read as a universal, that sentence would demand a
command proof on every aggregated-`REQUIRED_NOW` phase-gate clause and would
contradict the pinned set on 24 rows. I measured the antecedent instead of
assuming it. The sentence speaks of "the observable conjunction that a
predicate *would have* carried", and a predicate is carried only by a component
derived `CONDITIONAL_UNACTIVATED` or `CONDITIONAL_ACTIVATED` (goal L284-292) —
i.e. only by a clause whose related register set is entirely dormant. I checked
all 34 `RELATED_REGISTER_SCOPE` phase-gate clauses: **`PG-2-04` is the only one
that reaches `REQUIRED_NOW` over a register set containing a dormant row**
(`D-01` `Open`, `D-03` `Deferred`), and it is exactly the row whose command-proof
`scope` carries the twelve-term conjunction pinned verbatim at
`validate_ledger_structural.py:2553-2562`. `PG-2-01` is `CONDITIONAL_UNACTIVATED` and *does* carry a predicate, `AP-PG-2-01`, so the sentence — which is about a clause that has **no** predicate because aggregation made it `REQUIRED_NOW` — does not describe this row at all. Its observable conjunction lives in the predicate, exactly where the contract puts it for a dormant clause. The prose and the
pinned set are consistent; that sentence is about `PG-2-04`.

That is the cleanest case in the batch: for a conditional Phase 2 gate the
contract has already chosen where the machine-readable conjunction goes, and it
is the `activation_predicate`, pinned at
`validate_ledger_structural.py:2525-2545`. A parallel `COMMAND_RESULT`
obligation would duplicate it in an untyped form.

**`TYPED_APPROVAL` — unrepresentable here.** Goal L485-486 requires such an item
to name component-local `required_approvals` entries; this row's list is empty.
The contrast within this batch is instructive: `PG-2-05`, the other Phase 2
clause turning on a judgment, *does* carry a `PRODUCT_OWNER_DECISION` — and
still carries no typed evidence item, because the closed `evidence_type`
vocabulary at goal L479-482 has no product-owner category. Here there is no
requirement to name at all.

**Negative "no-implementation" proof — not demanded.** All 14
`*-NO-IMPLEMENTATION` items sit on the 13 `first_release_deferral` rows and
`DISP-R-1` (verified ledger-wide). This row is a positive obligation with
`rejection_record: null`, for which `current_no_implementation_proof` returns
`(True, [])` at `validate_ledger_structural.py:2690-2692`; the predicate is
vacuous and there is nothing for such an item to prove. `PG-2-01` is dormant, not
rejected — `program_disposition` is `CONDITIONAL_UNACTIVATED`, which is a
"why the program accounts for it" label and not a delivery or rejection claim
(goal L197).

**`SPEC-REVIEW` item — correctly absent.** The 91 `REQ-*-SPEC-REVIEW` items sit
on rows that own a specification artifact. `primary_spec` is `null` on this row
and on all 35 phase-gate rows (verified), and **no phase-gate row carries a
`DELEGATED_ARTIFACT_APPROVAL`** — 0 of 35, against 123 such requirements
elsewhere. The two facts are the same fact: a §F scorecard bullet owns no
artifact to have reviewed or delegated-approved. The spec-review and delegated-approval obligations sit on `REG-D-02` and `REG-D-05`, both under S20.

**`REEVALUATION-CONTROL` item — checked and inapplicable.** All 8 exist on
`scale_trigger` rows (`SCALE-SQLITE-01`…`04`, `SCALE-WORKFLOW-01`…`04`), whose
acceptance text *is* a trigger condition and therefore needs a separate proof
that the control is recorded "without requiring its condition to occur". Note that `D-02`'s acceptance does end
"re-evaluation triggers are precommitted" — but that obligation is inventoried
by `PG-2-06`, the §F bullet that names it, not by this one. This clause is about
the improvement result.

**`evidence_refs`.** One reference, re-verified: `EV-PG-2-01-SOURCE`,
`UTF8_LINE_SPAN` over register v2 L164-164, digest
`49518e1c2f8439fbc01285087b7e5efbb6bf9e25cdedf0d7dc631dcb000086f4`, captured
`2026-08-13T02:49:11Z`. Re-resolved and recomputed this round; matches.

**`verification_command` observation, not a finding.** `mode: UNRESOLVED` with
no commands. Goal L498-502 permits `UNRESOLVED` "during initial ledger
construction only"; the ledger is in that state and structural validation
passes. Because this row is outside the pinned command-proof
population, it will eventually need `NOT_APPLICABLE` with its own evidenced
`REVIEWER`-role attestation (goal L508-515) rather than `COMMANDS`. That is a future obligation on `verification_command`, not a
missing `required_evidence` item.

**Residuals.** None.

---

**verdict: CLEAN**

`required_evidence` for `PG-2-01` is complete at the input bytes pinned above.
This review satisfies no evidence item and authorizes no delivery, gate,
approval, or transition.
