# Inventory review — PG-2-03 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `PG-2-03` |
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
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"09818df2446031daa36f27d021f18ce227574eb8a49dc5f452e1b64594352ed7","digest_mode":"UTF8_LINE_SPAN","end_line":166,"evidence_ref_id":"EV-PG-2-03-SOURCE","path":"docs/blueprint/funda-blueprint-implementation-decision-register-v2.md","scope":"Exact authoritative source occurrence for PG-2-03","start_line":166}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: canonical promotion cannot diverge from SQL metadata","evidence_id":"REQ-PG-2-03-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"PG-2-03 acceptance and delivery scope","status":"UNRESOLVED"},{"approval_ids":[],"description":"Reproducible command result proving the current PG-2-03 acceptance obligation","evidence_id":"REQ-PG-2-03-COMMAND-PROOF","evidence_ref_ids":[],"evidence_type":"COMMAND_RESULT","proof_mode":"COMMAND","scope":"PG-2-03 command proof","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 —
appending review evidence mutates `evidence_refs` and therefore the input
projection):

- `reviewed_input_sha256` (pre-record): `243008294a0c9ecf90d27c75e7180f0a39ddd2a1817c1613deb3963c5f7c917a`
- `reviewed_inventory_sha256` (pre-record): `9403fe36e83767480b52a57774a6250c132c3a36efcc98c3af0e7ae38c90ccf5`

## Scope of this decision

Goal L492-494: a `COMPLETE` clean `REVIEWER`-role evidence review "proves that
every source-required acceptance item is represented and classified by proof
mode; it does not satisfy an evidence item." This review decides **completeness
of the obligation list only**. Every item on this row is legitimately
`UNRESOLVED` with empty `evidence_ref_ids` (goal L484: "An unresolved item has
no evidence refs") — that is not a finding.

## The source clause, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md`
L166, the third bullet under `### Phase 2 may exit only when`
(L162), inside `## F. Phase-gate scorecard` (L122):

> - canonical promotion cannot diverge from SQL metadata;

- `source_hash` recomputed over the whole register file → `26d51b31…`, matches
  the stored value.
- `text_digest` recomputed over the normalized L166 span →
  `09818df2446031daa36f27d021f18ce227574eb8a49dc5f452e1b64594352ed7`, equal to
  the stored `text_digest` and to `EV-PG-2-03-SOURCE.content_sha256`.
- `required_acceptance_text` equals that bullet with the list marker and the
  terminal punctuation stripped, byte for byte.

## Reasoning

**What the clause actually demands.** An impossibility claim: canonical
promotion **cannot** diverge from SQL metadata. Two obligations are enumerated
and they are the right two:

- `REQ-PG-2-03-ACCEPTANCE`, `ARTIFACT`/`CONTENT_HASH`, quoting the clause
  verbatim, scope "PG-2-03 acceptance and delivery scope" — the definition of
  the promotion transaction whose design makes divergence impossible.
- `REQ-PG-2-03-COMMAND-PROOF`, `COMMAND_RESULT`/`COMMAND`, scope "PG-2-03
  command proof" — the executed demonstration.

**Why the command proof is mandatory here and absent from the batch's other
nine non-command rows.** `PG-2-03` is one of the 25 rows in the pinned
`EXPECTED_COMMAND_PROOF_COMPONENTS` set (goal L3989-4003;
`validate_ledger_structural.py:2635-2649`), asserted as an exact set equality —
so for this row the item is not merely permitted, it is required: removing it
would make the actual set a strict subset and fail structural validation, just
as adding one to `PG-1-07` would fail it from the other side. Goal L484-485 is
consistent: `evidence_type: COMMAND_RESULT` forces `proof_mode: COMMAND`
(mechanized at goal L3484-3485), and the stored item satisfies that.

The substantive reason, checked rather than assumed: an impossibility claim
cannot be proved by an artifact alone. A design document asserting that partial
writes cannot create split-brain state is a claim about the design; the proof is
an executed run in which promotion cases were attempted and zero divergences and
zero partial-write escapes were observed. That is exactly what `AP-PG-2-03`
counts — `promotion_cases_executed > 0` alongside two zero-valued counters — and
the command proof is what produces those numbers. The pattern holds across the
pinned set's phase-gate members: `PG-1-04` (missing inputs fail closed),
`PG-1-05` (post-cutoff data excluded by tested controls), `PG-2-04` (correction,
deletion, backup, export **tested**) are all executed-behaviour claims, while
the batch's artifact-shaped clauses ("auditable", "visible", "surfaced",
"recorded", "improves") are not.

**Granularity is a ledger-wide convention, not a per-row choice.** Every
canonical row but one carries exactly one `REQ-<component_id>-ACCEPTANCE`
`ARTIFACT`/`CONTENT_HASH` item quoting the full acceptance text — 168 such items
across 169 canonical rows, the single exception being `DISP-R-1`, whose
acceptance item was deliberately replaced by the `NO-IMPLEMENTATION`
requirement. Multi-clause acceptance texts are never split into per-phrase
items anywhere in the ledger. So a second item on this row would have to be a
*different kind of proof*, not a fragment of the same text.

**Command-proof `scope` — checked against the one pinned counter-example.**
This item's scope is the plain form, "PG-2-03 command proof", matching
`PG-05-08`, `PG-1-04`, `PG-1-05`, and `PG-1-06`. Only `PG-2-04` carries an
expanded conjunction in its scope string, and that string is pinned verbatim at
`validate_ledger_structural.py:2553-2562`. Goal L266-272 explains why exactly
one row differs: the conjunction "that a predicate would have carried" moves
into the command-proof scope only for a clause that *lost* its predicate by
aggregating to `REQUIRED_NOW`. `PG-2-03` kept its predicate, so its observable
conjunction lives in `AP-PG-2-03` and its scope string stays plain. The two rows
are the contract's own worked example of the rule, and neither is missing
anything.

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

**`TYPED_APPROVAL` — unrepresentable here.** Goal L485-486 requires such an item
to name component-local `required_approvals` entries; this row's list is empty.

**Negative "no-implementation" proof — not demanded.** All 14
`*-NO-IMPLEMENTATION` items sit on the 13 `first_release_deferral` rows and
`DISP-R-1` (verified ledger-wide). This row is a positive obligation with
`rejection_record: null`, for which `current_no_implementation_proof` returns
`(True, [])` at `validate_ledger_structural.py:2690-2692`; the predicate is
vacuous and there is nothing for such an item to prove.

**`SPEC-REVIEW` item — correctly absent.** The 91 `REQ-*-SPEC-REVIEW` items sit
on rows that own a specification artifact. `primary_spec` is `null` on this row
and on all 35 phase-gate rows (verified), and **no phase-gate row carries a
`DELEGATED_ARTIFACT_APPROVAL`** — 0 of 35, against 123 such requirements
elsewhere. The two facts are the same fact: a §F scorecard bullet owns no
artifact to have reviewed or delegated-approved. The spec-review and delegated-approval obligations sit on `REG-D-03` under S19.

**`REEVALUATION-CONTROL` item — checked and inapplicable.** All 8 exist on
`scale_trigger` rows (`SCALE-SQLITE-01`…`04`, `SCALE-WORKFLOW-01`…`04`), whose
acceptance text *is* a trigger condition and therefore needs a separate proof
that the control is recorded "without requiring its condition to occur". 

**`evidence_refs`.** One reference, re-verified: `EV-PG-2-03-SOURCE`,
`UTF8_LINE_SPAN` over register v2 L166-166, digest
`09818df2446031daa36f27d021f18ce227574eb8a49dc5f452e1b64594352ed7`, captured
`2026-08-13T02:49:11Z`. Re-resolved and recomputed this round; matches. Note
that the `COMMAND` item will eventually need `verification_command.mode ==
COMMANDS` with a declared command and output refs (goal L503-507, L3675-3689);
its absence now is what `status: UNRESOLVED` records, not a completeness gap.

**`verification_command` observation, not a finding.** `mode: UNRESOLVED` with
no commands. Goal L498-502 permits `UNRESOLVED` "during initial ledger
construction only"; the ledger is in that state and structural validation
passes. Unlike the batch's other rows, this one may **not** later resolve to
`NOT_APPLICABLE`: goal L508-515 and L3693-3695 require that a `NOT_APPLICABLE`
policy hold only when no requirement has `proof_mode: COMMAND`, and this row has
one. `PG-2-03` must eventually declare `COMMANDS`. That is a future obligation
on `verification_command`, not a missing `required_evidence` item.

**Residuals.** None.

---

**verdict: CLEAN**

`required_evidence` for `PG-2-03` is complete at the input bytes pinned above.
This review satisfies no evidence item and authorizes no delivery, gate,
approval, or transition.
