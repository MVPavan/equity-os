# Inventory review — DISP-M-2 / EVIDENCE / r0

**verdict: ISSUES_FOUND**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-M-2` |
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
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"96f0c2eb2f7b560d54ec98d18c6515a90048f6093ebe3942ba5d4396103ba24f","digest_mode":"UTF8_LINE_SPAN","end_line":166,"evidence_ref_id":"EV-DISP-M-2-SOURCE","path":"docs/blueprint/funda-third-order-review-disposition-report.md","scope":"Exact authoritative source occurrence for DISP-M-2","start_line":130},{"captured_at":"2026-08-15T07:13:28Z","content_sha256":"61094a92688a7393eeedf99cd1a8759be874b5f9fd775374984d748c73d3376d","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-DISP-M-2-SPEC-DRAFT","path":"docs/specs/equity-os-s12-observation-fact-identity-schema.md","scope":"Current draft specification bytes for DISP-M-2","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: ### M-2 — Fact identity and revision semantics\n\n**Disposition: Accept; the required model is richer than a single key.**\n\nThe system needs to distinguish four concepts:\n\n1. **source occurrence:** the value as it appears in a specific source location;\n2. **extraction result:** parser/model output for that occurrence and parser version;\n3. **economic measurement slot:** the intended metric, entity, period, scope, dimensions, and definition;\n4. **approved canonical selection:** the observation Funda currently uses for a specified knowledge cutoff.\n\nA robust design should include:\n\n```text\nmeasurement_key\n  = entity\n  + metric definition/version\n  + period\n  + statement/consolidation scope\n  + dimension set\n  + accounting/adjustment basis\n\nobservation_id\n  = immutable source occurrence\n\nrevision_family_id\n  = observations believed to represent the same measurement slot\n\nrevision_reason\n  = issuer restatement\n  | source correction\n  | parser re-extraction\n  | manual correction\n  | normalization-policy change\n```\n\nA parser upgrade should normally create a new extraction result, not silently rewrite the economic observation. Restatements, reclassifications, and segment-definition changes require explicit reconciliation rather than automatic supersession by key.","evidence_id":"REQ-DISP-M-2-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"DISP-M-2 acceptance and delivery scope","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (the recorder must recompute both
after its Phase A evidence append, per recording design r2 §3.4 — appending review
evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `ce4c0fd031780e4c18e68be9b8818ab48dc62b5febf55d248a507b360163c03e`
- `reviewed_inventory_sha256` (pre-record): `d296ac6f31ddb53cb29033de03afe14ac640f459d2eb20f571602c46193ebb52`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` lines 130-166, anchor
`M-2`, `source_title` "Fact identity and revision semantics":

> ### M-2 — Fact identity and revision semantics
>
> **Disposition: Accept; the required model is richer than a single key.**
>
> The system needs to distinguish four concepts:
>
> 1. **source occurrence:** the value as it appears in a specific source location;
> 2. **extraction result:** parser/model output for that occurrence and parser version;
> 3. **economic measurement slot:** the intended metric, entity, period, scope, dimensions, and definition;
> 4. **approved canonical selection:** the observation Funda currently uses for a specified knowledge cutoff.
>
> A robust design should include:
>
> ```text
> measurement_key
>   = entity
>   + metric definition/version
>   + period
>   + statement/consolidation scope
>   + dimension set
>   + accounting/adjustment basis
>
> observation_id
>   = immutable source occurrence
>
> revision_family_id
>   = observations believed to represent the same measurement slot
>
> revision_reason
>   = issuer restatement
>   | source correction
>   | parser re-extraction
>   | manual correction
>   | normalization-policy change
> ```
>
> A parser upgrade should normally create a new extraction result, not silently rewrite the economic observation. Restatements, reclassifications, and segment-definition changes require explicit reconciliation rather than automatic supersession by key.


Recomputed this round against current bytes:

- `source_hash` over the whole file → `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`, equal to the stored value.
- `text_digest` over the normalized L130-166 span
  (CRLF-to-LF normalized, surrounding ASCII whitespace trimmed) →
  `96f0c2eb2f7b560d54ec98d18c6515a90048f6093ebe3942ba5d4396103ba24f`, equal to the stored value.
- `required_acceptance_text` equals that normalized span byte for byte.
- Every `evidence_refs` object on this row was re-hashed against current bytes and
  matches its stored `content_sha256`.

## Reasoning

`required_evidence` enumerates one item:

| `evidence_id` | `evidence_type` | `proof_mode` | `status` | refs | `approval_ids` |
|---|---|---|---|---|---|
| `REQ-DISP-M-2-ACCEPTANCE` | `ARTIFACT` | `CONTENT_HASH` | `UNRESOLVED` | `[]` | `[]` |

Its `description` was recomputed this round and is byte-equal to
`"Current proof satisfying: "` plus the row's exact `required_acceptance_text` —
which for this row is the full 37-line span including the fenced
`measurement_key` / `observation_id` / `revision_family_id` / `revision_reason`
block. The whole pseudo-schema is therefore inside the obligation, not summarised
away.

**Clause-by-clause coverage.** The clause requires the system to distinguish four
concepts, to include the five-part identity model in the fenced block, and to
observe two rules — a parser upgrade normally creates a new extraction result
rather than silently rewriting the observation, and restatements /
reclassifications / segment-definition changes require explicit reconciliation
rather than automatic supersession by key. All of this is schema and semantics that
the S12 specification must state, provable by hashing its approved bytes; one
`ARTIFACT`/`CONTENT_HASH` item classifies it correctly.

I examined whether a `COMMAND` obligation is missing, because this clause's
related register `B-11` does carry one (`REQ-REG-B-11-COMMAND-PROOF`, answering
`B-11`'s "prior-period comparative handling is tested"). It is not missing: the
`M-2` clause contains no test or verification sentence — the word "tested" appears
in `B-11`'s register acceptance, not in this occurrence — and the program-level
evidence-inventory review's list of components with unclassified mechanical
obligations does not name `DISP-M-2`. Classification stands.

**`evidence_refs`.** Two objects, both recomputed and current:
`EV-DISP-M-2-SOURCE` (`UTF8_LINE_SPAN`, disposition report L130-166 — the widest
span in this batch) and `EV-DISP-M-2-SPEC-DRAFT` (`FILE_BYTES`, S12 draft).

**`verification_command`.** `UNRESOLVED` — permitted at this stage (goal
L~504-506); consistent with no `COMMAND`-classified requirement.

## Finding 1 — `required_evidence` omits the persisted specification review

**Severity:** Important. **Load-bearing:** yes — `required_evidence` is a terminal
gating collection (`validate_ledger_structural.py:2299`, `assert_complete_proof`),
so an obligation missing from it is an obligation the gate cannot demand.

**What is missing.** This row's `required_approvals` contains `APR-DISP-M-2-01`,
`DELEGATED_ARTIFACT_APPROVAL`, `Delegated fresh Sol xhigh specification reviewer`,
scope `M-2 under S12`. Under goal L598-600 a record satisfying that requirement
is an `approval_records` entry with `authority_source` `DELEGATED_AUTOMATED`, and
that record "has null human-resolution fields and **carries the persisted clean
`REVIEWER`-role review**". The persisted review of S12's current
specification bytes is therefore a proof this component needs.
`required_evidence` neither enumerates nor classifies it.

The component already carries the artifact the missing item would bind:
`EV-DISP-M-2-SPEC-DRAFT` is a `FILE_BYTES` reference to `docs/specs/equity-os-s12-observation-fact-identity-schema.md` — the exact
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
   emits `REQ-DISP-M-2-SPEC-REVIEW` for this component. The canonical ledger contains
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
   evidence to be "current and **component-local**". S12 owns register rows
   B-05, B-10, B-11, C-03, each of which carries its own `REQ-REG-*-SPEC-REVIEW`; none of them
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
`REQ-DISP-M-2-SPEC-REVIEW`, `evidence_type` `REVIEW`, `proof_mode` `CONTENT_HASH`,
`status` `UNRESOLVED`, `evidence_ref_ids` `[]`, `approval_ids` `[]`, `scope`
`M-2 under S12`, description "Persisted clean fresh Sol xhigh review of the
current specification bytes" — the exact shape the other 91 rows carry. Because
`required_evidence` and `evidence_refs` are both inside
`review_input_projection`, that edit must happen before any review on this row is
digested, per recording design r2 §3.4.

---

**verdict: ISSUES_FOUND**

**This artifact is not recordable as a `COMPLETE` review, and that is correct.**
`validate_ledger_structural.py:342` accepts exactly one `verdict` value on a
`COMPLETE` review, `CLEAN`; there is no schema slot for a negative verdict. Per
recording design r2 §5.4 the `EVIDENCE` review on `DISP-M-2` therefore stays
`PENDING`, this artifact is the durable record of the finding, and the finding
belongs in `open_findings` on `DISP-M-2` with severity, load-bearing status, artifact
and disposition — written by a tool with a different safety envelope, not by this
review.

Because a row's applicable reviews must be recorded all-at-once or not at all
(recording design r2 §3.4), no review on `DISP-M-2` is recordable while this finding
stands.

This review authorizes no delivery, gate, approval, or transition.
