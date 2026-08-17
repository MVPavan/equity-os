# Inventory review — DISP-G-5 / EVIDENCE / r0

**verdict: ISSUES_FOUND**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-G-5` |
| `review_type` | `EVIDENCE` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `a88da077-0dfc-49ab-bb1a-df4e8266291b` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-15T13:16:03Z` |

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

`review_inventory_projection(row, "EVIDENCE")` — canonical JSON:

```json
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"299faaca255a6bf92cf524c3251a5e269f1e46ad112799f732005b09432542c0","digest_mode":"UTF8_LINE_SPAN","end_line":116,"evidence_ref_id":"EV-DISP-G-5-SOURCE","path":"docs/blueprint/funda-third-order-review-disposition-report.md","scope":"Exact authoritative source occurrence for DISP-G-5","start_line":102},{"captured_at":"2026-08-15T07:13:28Z","content_sha256":"9b14f5f327a9ff623cb41c823ab3eeec2d14f2f3ee05b8506313fbb28e83f458","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-DISP-G-5-SPEC-DRAFT","path":"docs/specs/equity-os-s06-output-materiality-falsifiers.md","scope":"Current draft specification bytes for DISP-G-5","start_line":null},{"captured_at":"2026-08-13T04:19:57Z","content_sha256":"9b14f5f327a9ff623cb41c823ab3eeec2d14f2f3ee05b8506313fbb28e83f458","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-DISP-G-5-S06-I7-CURRENT-S06","path":"docs/specs/equity-os-s06-output-materiality-falsifiers.md","scope":"Exact current S06 bytes adjudicated for S06-I7 on DISP-G-5","start_line":null},{"captured_at":"2026-08-13T04:19:57Z","content_sha256":"61d74f4b8b9248a75ff48e4508b1b58fb79b884acbbc859328111bb3814f2113","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-DISP-G-5-S06-I7-R4","path":"docs/goals/reviews/specs/equity-os-s04-s06-r4.md","scope":"Final ordinary r4 review report finding S06-I7 for DISP-G-5","start_line":null},{"captured_at":"2026-08-13T04:19:57Z","content_sha256":"da3ef87f32646fdb3e0f576086aba5070eee0aee3b115f53cb6b40579999e26a","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-DISP-G-5-S06-I7-ADJUDICATION","path":"docs/goals/reviews/specs/equity-os-s04-s06-adjudication.md","scope":"Post-cap adjudication upholding S06-I7 and its exact cone for DISP-G-5","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: ### G-5 — Undefined materiality\n\n**Disposition: Accept, but broaden the remedy.**\n\nThe validator cannot enforce “all material claims” until materiality is operationally defined. A single quantitative percentage is insufficient because a small number may still be thesis-critical, governance-critical, or legally significant.\n\nThe minimum materiality policy should combine:\n\n- **quantitative magnitude:** relative to the relevant statement line, segment, guidance range, equity, enterprise value, or prior assumption;\n- **always-material categories:** guidance, restatements, auditor qualifications, going-concern language, promoter pledges, related-party transactions, capital raises, material dilution, major corporate actions, management changes, and regulatory actions;\n- **thesis relevance:** whether the item changes an assumption, catalyst, risk, valuation input, management-credibility assessment, or thesis breaker;\n- **uncertainty and source conflict:** unresolved contradictions or low-confidence extraction of an otherwise important item;\n- **coverage-level overrides:** company- or mandate-specific thresholds stored with a policy version.\n\nThe materiality decision itself should be reviewable and versioned.","evidence_id":"REQ-DISP-G-5-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"DISP-G-5 acceptance and delivery scope","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (the recorder must recompute both
after its Phase A evidence append, per recording design r2 §3.4 — appending review
evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `3784cc2355215c3b43b79bb6c4e70ca20371fbe0348224b6fb1a40df180140c7`
- `reviewed_inventory_sha256` (pre-record): `ffab65d9c2769249fadd50a6160506b5c0aa539f2ac75e8daf5ed7d90a2f7822`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` lines 102-116, anchor
`G-5`, `source_title` "Undefined materiality":

> ### G-5 — Undefined materiality
>
> **Disposition: Accept, but broaden the remedy.**
>
> The validator cannot enforce “all material claims” until materiality is operationally defined. A single quantitative percentage is insufficient because a small number may still be thesis-critical, governance-critical, or legally significant.
>
> The minimum materiality policy should combine:
>
> - **quantitative magnitude:** relative to the relevant statement line, segment, guidance range, equity, enterprise value, or prior assumption;
> - **always-material categories:** guidance, restatements, auditor qualifications, going-concern language, promoter pledges, related-party transactions, capital raises, material dilution, major corporate actions, management changes, and regulatory actions;
> - **thesis relevance:** whether the item changes an assumption, catalyst, risk, valuation input, management-credibility assessment, or thesis breaker;
> - **uncertainty and source conflict:** unresolved contradictions or low-confidence extraction of an otherwise important item;
> - **coverage-level overrides:** company- or mandate-specific thresholds stored with a policy version.
>
> The materiality decision itself should be reviewable and versioned.


Recomputed this round against current bytes:

- `source_hash` over the whole file → `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`, equal to the stored value.
- `text_digest` over the normalized L102-116 span
  (CRLF-to-LF normalized, surrounding ASCII whitespace trimmed) →
  `299faaca255a6bf92cf524c3251a5e269f1e46ad112799f732005b09432542c0`, equal to the stored value.
- `required_acceptance_text` equals that normalized span byte for byte.
- Every `evidence_refs` object on this row was re-hashed against current bytes and
  matches its stored `content_sha256`.

## Reasoning

`required_evidence` enumerates one item:

| `evidence_id` | `evidence_type` | `proof_mode` | `status` | refs | `approval_ids` |
|---|---|---|---|---|---|
| `REQ-DISP-G-5-ACCEPTANCE` | `ARTIFACT` | `CONTENT_HASH` | `UNRESOLVED` | `[]` | `[]` |

Its `description` was recomputed this round and is byte-equal to
`"Current proof satisfying: "` plus the row's exact `required_acceptance_text`.

**Clause-by-clause coverage.** The clause requires a minimum materiality policy
combining five named ingredients, and closes "The materiality decision itself
should be reviewable and versioned." All six statements are content of the S06
output/materiality contract, provable by hashing the approved specification bytes;
one `ARTIFACT`/`CONTENT_HASH` item classifies them correctly.

I examined whether a `COMMAND_RESULT`/`COMMAND` item is missing, because this
clause's *related* register `A-10` does carry one (`REQ-REG-A-10-COMMAND-PROOF`,
answering `A-10`'s "validator test cases approved"). It is not missing here: this
clause states no test obligation of its own — it prescribes the policy's content
and its versioning — and the enforcement test lives on `A-10`, where the ledger
already declares it. The sibling `DISP-6-2`, which relates the same two registers,
likewise carries only an acceptance item. The program-level evidence-inventory
review's list of components with unclassified mechanical obligations does not name
`DISP-G-5`.

**`evidence_refs`.** Five objects — the most of any row in this batch — all
recomputed against current bytes this round and all matching:
`EV-DISP-G-5-SOURCE` (`UTF8_LINE_SPAN`, disposition report L102-116);
`EV-DISP-G-5-SPEC-DRAFT` (`FILE_BYTES`, S06 draft);
`EV-DISP-G-5-S06-I7-CURRENT-S06`, `EV-DISP-G-5-S06-I7-R4` and
`EV-DISP-G-5-S06-I7-ADJUDICATION`. The last three are exactly the three IDs listed
in `open_findings[0].evidence_ref_ids`, so this row's open blocking finding
`S06-I7` is evidenced component-locally, as goal L439 requires. That is a positive
result of this review, not an incidental observation: an `OPEN_BLOCKING`
load-bearing finding with dangling or stale evidence would have been a defect in
the `EVIDENCE` inventory, and it is neither.

**`verification_command`.** `UNRESOLVED` with empty commands and null review —
permitted during initial ledger construction (goal L~504-506); structural
validation exits `0`.

**This review clears nothing about `S06-I7`.** The finding remains
`OPEN_BLOCKING`, `delivery_status` remains `REVIEW_BLOCKED`, and nothing here
bears on it.

## Finding 1 — `required_evidence` omits the persisted specification review

**Severity:** Important. **Load-bearing:** yes — `required_evidence` is a terminal
gating collection (`validate_ledger_structural.py:2299`, `assert_complete_proof`),
so an obligation missing from it is an obligation the gate cannot demand.

**What is missing.** This row's `required_approvals` contains `APR-DISP-G-5-01`,
`DELEGATED_ARTIFACT_APPROVAL`, `Delegated fresh Sol xhigh specification reviewer`,
scope `G-5 under S06`. Under goal L598-600 a record satisfying that requirement
is an `approval_records` entry with `authority_source` `DELEGATED_AUTOMATED`, and
that record "has null human-resolution fields and **carries the persisted clean
`REVIEWER`-role review**". The persisted review of S06's current
specification bytes is therefore a proof this component needs.
`required_evidence` neither enumerates nor classifies it.

The component already carries the artifact the missing item would bind:
`EV-DISP-G-5-SPEC-DRAFT` is a `FILE_BYTES` reference to `docs/specs/equity-os-s06-output-materiality-falsifiers.md` — the exact
bytes whose persisted review is unaccounted for.

**Why this is an omission and not a modelling choice — four independent measures,
all recomputed this round at the pinned ledger bytes.**

1. **The ledger's own pairing invariant holds everywhere except this kind.** Of the
   169 canonical rows, 123 carry a `DELEGATED_ARTIFACT_APPROVAL` requirement. 91 of
   them also carry a `REVIEW`/`CONTENT_HASH` item `REQ-<COMPONENT_ID>-SPEC-REVIEW`
   with description "Persisted clean fresh Sol xhigh review of the current
   specification bytes" and a scope equal to the approval's scope: all 60
   `register_row`, all 13 `first_release_deferral`, all 8 `scale_trigger`, and the
   10 `sequence_clause` rows that carry the approval. The remaining 32 — every
   `disposition_item`, including this one — carry none. The invariant also holds in
   the reverse direction: no row lacking the approval carries the item, on any kind.
   The pairing fails on exactly one kind, and this component is in it.
2. **The reviewed generator makes the pairing unconditional.**
   `scripts/equity_os_blueprint/generate_initial_ledger.py:398-402` appends
   `REQ-<COMPONENT_ID>-SPEC-REVIEW` inside `add_approval` whenever
   `approval_type == "DELEGATED_ARTIFACT_APPROVAL"`, with no kind exemption, and the
   disposition builder calls exactly that at `:590`. Executed this round into a
   scratch output path — the generator refuses canonical paths by construction — it
   emits `REQ-DISP-G-5-SPEC-REVIEW` for this component. The canonical ledger contains
   no such item.
3. **A prior `REVIEWER`-role review already recorded it, and it alone was never
   remediated.** The program-level evidence-inventory review
   `docs/goals/reviews/ledger/equity-os-blueprint-evidence-inventory-r0.md` carries
   Important finding 1: "All 32 disposition components omit required review
   evidence — Load-bearing: YES." Every other finding in that review has since been
   remediated in the canonical ledger, and each remediation was re-verified this
   round: Critical 2 (no `COMMAND` requirements anywhere) — 25 now exist, including
   on `DISP-M-4`, `DISP-M-5`, `DISP-M-6` and `DISP-M-7` in this same batch;
   Critical 3 (deferrals framed as positive delivery) — `REQ-DEF-*-NO-IMPLEMENTATION`
   now exists on all 13; Important 2 (approval/review phase gates misclassified) —
   `PG-05-01`, `PG-05-02`, `PG-05-05` and `PG-1-09` now carry typed approval
   evidence; Important 3 (scale triggers) — `REQ-SCALE-*-REEVALUATION-CONTROL` now
   exists on all 8. Important 1 is the single finding of that review still open, and
   it covers exactly this component's kind. Recording design r2 §2.2 states that the
   program-level reviews and the 447 per-component reviews "are separate obligations
   and both must hold", so that finding is not discharged by this review's existence.
4. **The proof cannot be borrowed from a sibling row.** Goal L439 requires review
   evidence to be "current and **component-local**". S06 owns register rows
   A-04, A-10, each of which carries its own `REQ-REG-*-SPEC-REVIEW`; none of them
   can discharge this component's obligation.

**Contrary reading, stated and answered.** The narrowest reading of the contract's
evidence-inventory standard is goal L493-495 — a complete clean review "proves that
every **source-required** acceptance item is represented and classified by proof
mode". The delegated specification review is not demanded by the disposition-report
clause; it is a program-process obligation from the goal's specification programme.
On that reading the omission falls outside this review's remit and this review
would be `CLEAN`. I do not adopt it, for three reasons: (i) `required_evidence` is
the component's proof-obligation list, and an obligation this component provably
has is absent from it; (ii) measures 1 and 2 show this programme treats the
persisted specification review as a component-local `required_evidence` item on
every other kind, so the 32 disposition rows are residue rather than a deliberate
model; (iii) a prior `REVIEWER`-role review already classified it load-bearing and
it has never been dispositioned. Where the reading is contestable, the contract's
own recording rule resolves it: a review that is not certainly clean stays
`PENDING` (recording design r2 §5.4), which is the outcome recorded here.

**Suggested remediation (not authorised by this review).** Add one
`required_evidence` object to this row: `evidence_id`
`REQ-DISP-G-5-SPEC-REVIEW`, `evidence_type` `REVIEW`, `proof_mode` `CONTENT_HASH`,
`status` `UNRESOLVED`, `evidence_ref_ids` `[]`, `approval_ids` `[]`, `scope`
`G-5 under S06`, description "Persisted clean fresh Sol xhigh review of the
current specification bytes" — the exact shape the other 91 rows carry. Because
`required_evidence` and `evidence_refs` are both inside
`review_input_projection`, that edit must happen before any review on this row is
digested, per recording design r2 §3.4.

---

**verdict: ISSUES_FOUND**

**This artifact is not recordable as a `COMPLETE` review, and that is correct.**
`validate_ledger_structural.py:342` accepts exactly one `verdict` value on a
`COMPLETE` review, `CLEAN`; there is no schema slot for a negative verdict. Per
recording design r2 §5.4 the `EVIDENCE` review on `DISP-G-5` therefore stays
`PENDING`, this artifact is the durable record of the finding, and the finding
belongs in `open_findings` on `DISP-G-5` with severity, load-bearing status, artifact
and disposition — written by a tool with a different safety envelope, not by this
review.

Because a row's applicable reviews must be recorded all-at-once or not at all
(recording design r2 §3.4), no review on `DISP-G-5` is recordable while this finding
stands.

This review authorizes no delivery, gate, approval, or transition.
