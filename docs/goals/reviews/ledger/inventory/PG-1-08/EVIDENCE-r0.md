# Inventory review — PG-1-08 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `PG-1-08` |
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
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"a30cba48f316e0439924b15b38e4971c3febbb97d99243f69a739ca219c4e2dd","digest_mode":"UTF8_LINE_SPAN","end_line":157,"evidence_ref_id":"EV-PG-1-08-SOURCE","path":"docs/blueprint/funda-blueprint-implementation-decision-register-v2.md","scope":"Exact authoritative source occurrence for PG-1-08","start_line":157}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: analyst effort improves against matched or per-company baselines by the agreed threshold, with confounds disclosed","evidence_id":"REQ-PG-1-08-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"PG-1-08 acceptance and delivery scope","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 —
appending review evidence mutates `evidence_refs` and therefore the input
projection):

- `reviewed_input_sha256` (pre-record): `30a21cc7444012e779bf57b938faba0ec48366bed6c8c2ddc7355e0e5b48ca02`
- `reviewed_inventory_sha256` (pre-record): `a51731c76749ade15a467c6a279597d3a06fcd44839521197c4da77e4b05cf9f`

## Scope of this decision

Goal L492-494: a `COMPLETE` clean `REVIEWER`-role evidence review "proves that
every source-required acceptance item is represented and classified by proof
mode; it does not satisfy an evidence item." This review decides **completeness
of the obligation list only**. Every item on this row is legitimately
`UNRESOLVED` with empty `evidence_ref_ids` (goal L484: "An unresolved item has
no evidence refs") — that is not a finding.

## The source clause, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md`
L157, the eighth bullet under `### Phase 1 may exit only when`
(L148), inside `## F. Phase-gate scorecard` (L122):

> - analyst effort improves against matched or per-company baselines by the agreed threshold, with confounds disclosed;

- `source_hash` recomputed over the whole register file → `26d51b31…`, matches
  the stored value.
- `text_digest` recomputed over the normalized L157 span →
  `a30cba48f316e0439924b15b38e4971c3febbb97d99243f69a739ca219c4e2dd`, equal to
  the stored `text_digest` and to `EV-PG-1-08-SOURCE.content_sha256`.
- `required_acceptance_text` equals that bullet with the list marker and the
  terminal punctuation stripped, byte for byte.

## Reasoning

**What the clause actually demands.** Three obligations, all of which land on
the same artifact: (a) analyst effort is compared against *matched or
per-company* baselines — a stated choice of comparator; (b) the improvement
meets "the agreed threshold"; (c) remaining confounds are disclosed. Obligation
(c) is a disclosure inside the reported result, and (a) and (b) are properties
of that same evaluation. `REQ-PG-1-08-ACCEPTANCE` quotes the whole clause
verbatim and is scoped to "PG-1-08 acceptance and delivery scope", so all three
fall inside one `ARTIFACT`/`CONTENT_HASH` obligation over the evaluation
artifact.

**Granularity is a ledger-wide convention, not a per-row choice.** Every
canonical row but one carries exactly one `REQ-<component_id>-ACCEPTANCE`
`ARTIFACT`/`CONTENT_HASH` item quoting the full acceptance text — 168 such items
across 169 canonical rows, the single exception being `DISP-R-1`, whose
acceptance item was deliberately replaced by the `NO-IMPLEMENTATION`
requirement. Multi-clause acceptance texts are never split into per-phrase
items anywhere in the ledger. So a second item on this row would have to be a
*different kind of proof*, not a fragment of the same text.

**"The agreed threshold" is not a fourth evidence obligation.** It is tempting
to read the past participle as demanding a separate proof that a threshold was
agreed. It does not, for two reasons I checked rather than assumed. First,
goal L484-487 types evidence by *proof mode*, and an agreement is an approval,
so any such obligation would have to appear as a `TYPED_APPROVAL` item naming a
component-local `required_approvals` entry — and this row has none (see below,
and the `APPROVAL` review). Second, the agreement is upstream: `C-12`'s own
acceptance says "**Pre-agreed** improvement is evaluated…", and `REG-C-12`
carries `ANALYST_ACCEPTANCE` / "Responsible analyst" paired 1:1 with
`REQ-REG-C-12-ANALYST_ACCEPTANCE`. The threshold's provenance is proved on
`C-12`; this gate proves the comparison against it.

**`COMMAND_RESULT` / `COMMAND` — checked, correctly absent, and in fact
forbidden.** The command-proof population is pinned as an exact set *equality*,
not a lower bound: goal L3989-4003 and `validate_ledger_structural.py:2635-2649`
assert `actual_command_proof_components == EXPECTED_COMMAND_PROOF_COMPONENTS`
over 25 named rows. The phase-gate members of that set are `PG-05-08`,
`PG-1-04`, `PG-1-05`, `PG-1-06`, `PG-2-03`, and `PG-2-04`. `PG-1-08` is not among
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
`validate_ledger_structural.py:2553-2562`. Both of `PG-1-08`'s related rows, `B-04` and `C-12`, were `Open` at activation and are `Open` now, so this clause never had a conjunction a predicate would have carried. The prose and the
pinned set are consistent; that sentence is about `PG-2-04`.

On the merits this is the least arguable absence in the batch: "improves … by
the agreed threshold, with confounds disclosed" turns on a judged comparison
and a prose disclosure. Goal L487-490 is explicit that analyst evidence "always
uses `TYPED_APPROVAL` and the typed approval/human-review path, never a
fabricated shell command", and an argv whose exit code decides whether confounds
were adequately disclosed would be exactly that fabrication.

**`TYPED_APPROVAL` — unrepresentable here.** Goal L485-486 requires such an item
to name component-local `required_approvals` entries; this row's list is empty.
Note the asymmetry with `PG-1-09` in this same batch, which does carry a
`CAPACITY_COMMITMENT` requirement and therefore *does* carry the paired
`CAPACITY`-typed item — the two rows show the convention working in both
directions.

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
artifact to have reviewed or delegated-approved. The spec-review and delegated-approval obligations sit on `REG-B-04` and `REG-C-12`, both under S18, each carrying its own `REQ-*-SPEC-REVIEW` item.

**`REEVALUATION-CONTROL` item — checked and inapplicable.** All 8 exist on
`scale_trigger` rows (`SCALE-SQLITE-01`…`04`, `SCALE-WORKFLOW-01`…`04`), whose
acceptance text *is* a trigger condition and therefore needs a separate proof
that the control is recorded "without requiring its condition to occur". This clause states a one-time Phase 1
evaluation outcome, not a standing trigger.

**`evidence_refs`.** One reference, re-verified: `EV-PG-1-08-SOURCE`,
`UTF8_LINE_SPAN` over register v2 L157-157, digest
`a30cba48f316e0439924b15b38e4971c3febbb97d99243f69a739ca219c4e2dd`, captured
`2026-08-13T02:49:11Z`. Path re-resolved and span digest recomputed this round;
both match, and the capture precedes this review's timestamp.

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

`required_evidence` for `PG-1-08` is complete at the input bytes pinned above.
This review satisfies no evidence item and authorizes no delivery, gate,
approval, or transition.
