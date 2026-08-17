# Inventory review — DISP-R-2 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-R-2` |
| `review_type` | `EVIDENCE` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `4e983789-a352-4ab6-9d42-4e7bdc2941f6` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-15T13:22:11Z` |

Role binding: `CONTEXT.md` "Agent roles (harness-wide)" L137-139 and L147 bind
`REVIEWER` to Claude Opus 5 at high effort, in an agent and context independent
of any `IMPLEMENTER` that produced the reviewed content. The digest above is the
`CONTEXT.md` bytes at review time and is an immutable historical capture.

## Input hashes read for this review

| Input | SHA-256 |
|---|---|
| `docs/goals/equity-os-blueprint-completion.md` (active goal contract) | `f15f7ab5a4e425dec3877ab7f1f7594687979060e4dbcd49390a8a8d5fedb85f` |
| `docs/goals/equity-os-blueprint-component-ledger.jsonl` (canonical ledger) | `de236d7e8dcf02e307ec58797f5722ae2f85d1d8cdba57d4ecc07df5383c9c97` |
| `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` (pinned v2 decision register) | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| `docs/blueprint/funda-third-order-review-disposition-report.md` (pinned third-order disposition report) | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| `scripts/equity_os_blueprint/validate_ledger_structural.py` (structural validator) | `731d0d8b208b577967c92e3992e7ec1a4333cdecbf89f6951c32d2ec469436f9` |
| `scripts/equity_os_blueprint/validate_ledger_preimplementation.py` (preimplementation validator) | `f7a225a1f99cb85c92cde3094505a92a746552280eb45dae0253a71ab9048013` |
| `scripts/equity_os_blueprint/extract_goal_validators.py` (extractor) | `5d20d796666d1154fb3c84ba4fa7407ee82819510a5ac06254f7f4a3126c6f2a` |
| `docs/goals/equity-os-blueprint-human-review-needed.md` (canonical human-review artifact) | `094fcdfab74a3f4c6fdb82b1520fc4d13b636ac0e9ed10194e5d607aed2ce9af` |
| `CONTEXT.md` (role binding) | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r2.md` (artifact format, design r2 §2.2) | `adf908ac8cec01a55a53438624c6a8913f673f5b7cecd3e955fc4919f73803fb` |

Fresh structural validation at these exact bytes:
`python3 scripts/equity_os_blueprint/validate_ledger_structural.py --repo-root .`
→ exit `0` (run at review time). Every `evidence_refs` entry on this row was
additionally re-hashed by hand against its current target bytes this round and
matched.

## Reviewed inventory, exactly as read

`review_inventory_projection(row, "EVIDENCE")` — canonical JSON:

```json
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"3d0a31e472130586bd54f8bdb7b1ffd37c617d6067cf628d24d982e0125fa0d8","digest_mode":"UTF8_LINE_SPAN","end_line":329,"evidence_ref_id":"EV-DISP-R-2-SOURCE","path":"docs/blueprint/funda-third-order-review-disposition-report.md","scope":"Exact authoritative source occurrence for DISP-R-2","start_line":325},{"captured_at":"2026-08-15T07:13:28Z","content_sha256":"a1f7477881ac2fb0497b02bcf1bce897219565d6fc521fdd3589a9006fae1c4c","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-DISP-R-2-SPEC-DRAFT","path":"docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md","scope":"Current draft specification bytes for DISP-R-2","start_line":null},{"captured_at":"2026-08-13T04:29:50Z","content_sha256":"a1f7477881ac2fb0497b02bcf1bce897219565d6fc521fdd3589a9006fae1c4c","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-DISP-R-2-S09-R3-N1-CURRENT-S09","path":"docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md","scope":"Exact current S09 bytes adjudicated for S09-r3-N1 on DISP-R-2","start_line":null},{"captured_at":"2026-08-13T04:29:50Z","content_sha256":"496d4874e89f119176f06dde057c8500fd36c45d740d1976c833b890c75abab6","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-DISP-R-2-S09-R3-N1-R4","path":"docs/goals/reviews/specs/equity-os-s07-s09-r4.md","scope":"Final ordinary r4 review report retaining S09-r3-N1 for DISP-R-2","start_line":null},{"captured_at":"2026-08-13T04:29:50Z","content_sha256":"95f7cbcaa3c4530cf56412b20b563435f0fc2bd2452c12bcff7549e561df1bf3","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-DISP-R-2-S09-R3-N1-ADJUDICATION","path":"docs/goals/reviews/specs/equity-os-s07-s09-adjudication.md","scope":"Post-cap adjudication upholding S09-r3-N1 and its exact cone for DISP-R-2","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: ### R-2 — Add filing channel and taxonomy version to A-06\n\n**Disposition: Accept.**\n\nThe XBRL/PDF spike should explicitly distinguish exchange quarterly-result XBRL, annual channels, issuer documents, and taxonomy/version changes. The spike should measure mapping stability, not merely field coverage.","evidence_id":"REQ-DISP-R-2-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"DISP-R-2 acceptance and delivery scope","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `34350b141c63030330e4fb10c6e56407f641d9451a9a888e268428ac3462702e`
- `reviewed_inventory_sha256` (pre-record): `05d4742ff8820e1d23e5171bf8e4bbc7a05ff6510a30a6b5e1a446a47d2ff5a5`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` lines 325-329, anchor `R-2`, title "Add filing channel and taxonomy version to A-06":

> ### R-2 — Add filing channel and taxonomy version to A-06
>
> **Disposition: Accept.**
>
> The XBRL/PDF spike should explicitly distinguish exchange quarterly-result XBRL, annual channels, issuer documents, and taxonomy/version changes. The spike should measure mapping stability, not merely field coverage.

- `source_hash` recomputed over the whole file → `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`, matching the row.
- `text_digest` recomputed over the normalized L325-329 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `3d0a31e472130586bd54f8bdb7b1ffd37c617d6067cf628d24d982e0125fa0d8`, matching the row.
- `required_acceptance_text` equals that normalized span byte for byte
  (checked by comparison, not by eye).
- The crosswalk for this row is pinned by the structural validator at
  `validate_ledger_structural.py:2427-2479` (`EXPECTED_DISPOSITION_CROSSWALK`),
  which fixes `applicable_spec_ids` and `related_register_ids` and derives the
  `primary_spec` shape from the spec count.

## Reasoning

**What this review decides.** Whether `required_evidence` is a *complete*
enumeration of the proof this component's source clause demands. It is not a
judgment that any proof has been obtained: every item here is `UNRESOLVED` with
empty `evidence_ref_ids`, which the validator requires of an unresolved item
(`validate_ledger_structural.py:2138-2139`), and this review does not change that.

**How completeness is testable at all.** Each item's `description` opens
"Current proof satisfying:" and then embeds the clause verbatim. I compared that
embedded text with `required_acceptance_text` and with the freshly normalized
source span, byte for byte, and all three agree. So no demand in the clause falls
outside the enumerated obligation's scope, and the completeness question reduces
to a sharper one: does any demand in the clause require a *different proof mode*
— `COMMAND` or `TYPED_APPROVAL` — that is not separately enumerated? The closed
vocabularies are the goal's typed-evidence section, mechanized at
`validate_ledger_structural.py:2124-2137`, where `COMMAND_RESULT` forces
`COMMAND` and every human evidence type forces `TYPED_APPROVAL`.

**Enumerated.** One item: `REQ-DISP-R-2-ACCEPTANCE`, `ARTIFACT` /
`CONTENT_HASH`, scope "DISP-R-2 acceptance and delivery scope", `UNRESOLVED`.

**Demand-by-demand.** The clause makes two demands, both on the *design* of the
A-06 spike: that it explicitly distinguish exchange quarterly-result XBRL, annual
channels, issuer documents, and taxonomy/version changes; and that it measure
mapping stability rather than merely field coverage. Both are satisfied by the
S09 specification text stating them, which is a content-hash obligation.

**Is a command proof missing?** "The spike should measure mapping stability" is
the sentence that could imply an executable obligation, so I tested it against the
register row that owns the spike. REG-A-06's acceptance text is itself the
measurement demand ("Coverage matrix by company, quarter, filing channel,
taxonomy/version … mapping stability, and reconciliation effort"), and REG-A-06
carries no `COMMAND_RESULT` item and does not appear in the pinned
`EXPECTED_COMMAND_PROOF_COMPONENTS` manifest (`:2635-2649`). That is coherent: a
spike's output is a produced coverage matrix — an artifact — not a repository
command. A disposition amending the spike's design cannot demand more proof than
the spike row itself.

**Typed-approval demands, checked.** The clause names filing sources — exchange
XBRL, annual channels, issuer documents. Access rights to sources are A-05's
obligation and are enumerated there as `REQ-REG-A-05-DATA_RIGHTS_APPROVAL`
(`DATA_RIGHTS` / `TYPED_APPROVAL`); this clause demands only that the spike
distinguish the channels, which needs no named authority.

**`evidence_refs` as read — five objects, and why three of them are here.**
`EV-DISP-R-2-SOURCE` (`UTF8_LINE_SPAN` L325-329, hash equal to the row's
`text_digest`) and `EV-DISP-R-2-SPEC-DRAFT` (`FILE_BYTES` over the S09 spec) are
the ordinary pair. The other three —
`EV-DISP-R-2-S09-R3-N1-CURRENT-S09`, `-R4` and `-ADJUDICATION` — were attached by
the `BLOCK` transitions that recorded the upheld load-bearing finding `S09-r3-N1`,
and they carry the r4 review report and the post-cap adjudication. They sit inside
the `EVIDENCE` projection because `evidence_refs` is projected whole, but they are
finding evidence, not `required_evidence` items, and they neither add nor discharge
an obligation. All five re-hashed this round and matched.

**Kind-level asymmetry, checked and dismissed.** All 32 `disposition_item` rows,
including this one, declare a `DELEGATED_ARTIFACT_APPROVAL` requirement but carry
no `REVIEW`-typed evidence item, whereas every `register_row` (60),
`first_release_deferral` (13), `scale_trigger` (8) and 10 of 11 `sequence_clause`
rows carry a `REQ-*-SPEC-REVIEW` item alongside the same approval type. I counted
this across all 169 canonical rows rather than assuming it. It is not an omission
of source-demanded proof: the goal makes the delegated approval *record* itself
the carrier — "that record has null human-resolution fields and carries the
persisted clean `REVIEWER`-role review" — and the validator forbids `approval_ids`
on any non-`TYPED_APPROVAL` item (`:2135-2137`), so the `REQ-*-SPEC-REVIEW` items
on other kinds are not a contractual link to the approval either. The delegated
approval remains an unsatisfied obligation on this row regardless, so no proof is
lost. Recorded as a repo-wide inventory-style observation, not a finding against
this component.

**`verification_command`.** Mode `UNRESOLVED`, no commands, no
`not_applicable_review`. The goal admits `UNRESOLVED` "during initial ledger
construction only", and this row is pre-implementation — `gate_result` is
`NOT_EVALUATED` and nothing is `VERIFIED`. It is a forward obligation to resolve
to `COMMANDS` or `NOT_APPLICABLE` before terminal use, not a present gap in the
`required_evidence` enumeration this review audits.

**Conclusion.** `required_evidence` is complete for this clause. The open
`S09-r3-N1` blocker is untouched by this review.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `DISP-R-2`'s `required_evidence` inventory is correct at the input bytes pinned above.
