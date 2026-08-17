# Inventory review — PG-05-08 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `PG-05-08` |
| `review_type` | `EVIDENCE` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `3c844df3-fdab-4e89-929b-89fcbc8223d4` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-16T03:50:06Z` |

Role binding: `CONTEXT.md` "Agent roles (harness-wide)" L137-139 binds `REVIEWER` to
Claude Opus 5 at high effort, in an agent and context independent of any `IMPLEMENTER`
that produced the reviewed content. The digest above is the `CONTEXT.md` bytes at review
time and is an immutable historical capture, never re-verified against later bytes
(`validate_ledger_structural.py:250-262`).

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

Fresh validation at these exact bytes, run this round:
`python3 scripts/equity_os_blueprint/validate_ledger_structural.py --repo-root .` → exit `0`;
`python3 scripts/equity_os_blueprint/extract_goal_validators.py --check` → exit `0`, so the
structural validator's pinned manifests are the goal's own bytes, not a downstream
paraphrase of them.

## Reviewed inventory, exactly as read

`review_inventory_projection(row, "EVIDENCE")` — canonical JSON
(`validate_ledger_structural.py:292-318`, extracted by `ast` and executed in an isolated
namespace this round rather than transcribed):

```json
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"1df28677bf9ab56b1b400421824ddf0902b84c6df556e282bec2234f0c1270a2","digest_mode":"UTF8_LINE_SPAN","end_line":144,"evidence_ref_id":"EV-PG-05-08-SOURCE","path":"docs/blueprint/funda-blueprint-implementation-decision-register-v2.md","scope":"Exact authoritative source occurrence for PG-05-08","start_line":144}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: the rejected-claim rework path and evidence-package versioning are demonstrated","evidence_id":"REQ-PG-05-08-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"PG-05-08 acceptance and delivery scope","status":"UNRESOLVED"},{"approval_ids":[],"description":"Reproducible command result proving the current PG-05-08 acceptance obligation","evidence_id":"REQ-PG-05-08-COMMAND-PROOF","evidence_ref_ids":[],"evidence_type":"COMMAND_RESULT","proof_mode":"COMMAND","scope":"PG-05-08 command proof","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (the recorder must recompute both after
its Phase A evidence append, per recording design r2 §3.4 — appending review evidence
mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `37b2b3249a271a6c2a1cfddd0c9d3f4b837cf5a3a928444a54221abfba0dbada`
- `reviewed_inventory_sha256` (pre-record): `5ff4858849057fe02d70c76f1225e98d17d83454b6c149c0e93d9cf177190124`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line 144,
anchor `F-0.5-08`, the 8th bullet under the
`### Phase 0.5 may exit only when` heading at line 135, inside
`## F. Phase-gate scorecard` (line 122):

> - the rejected-claim rework path and evidence-package versioning are demonstrated;

- `source_hash` recomputed over the whole register file →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L144 span (CRLF→LF, surrounding ASCII
  whitespace trimmed) → `1df28677bf9ab56b1b400421824ddf0902b84c6df556e282bec2234f0c1270a2`, matching the row.
- `required_acceptance_text` is that span with the `- ` list marker and the trailing
  `;` removed — compared programmatically, not by eye.
- `EV-PG-05-08-SOURCE` is a `UTF8_LINE_SPAN` reference over exactly that one line
  (`start_line == end_line == 144`); its `content_sha256` recomputes to the same digest,
  so the row's only evidence object resolves against current bytes.

## Reasoning

**What the clause demands.** "the rejected-claim rework path and evidence-package
versioning are demonstrated" demands an executed demonstration of a multi-step mechanism.
"Demonstrated" is stronger than "exists" or "is documented": the mechanism must be shown
working.

**What is enumerated.** Two obligations:

1. `REQ-PG-05-08-ACCEPTANCE` — `ARTIFACT` / `CONTENT_HASH`, description byte-equal to
   `"Current proof satisfying: " + required_acceptance_text` (checked programmatically),
   carrying both objects and the word "demonstrated".
2. `REQ-PG-05-08-COMMAND-PROOF` — `COMMAND_RESULT` / `COMMAND`, description "Reproducible
   command result proving the current PG-05-08 acceptance obligation". `COMMAND_RESULT`
   forces `proof_mode == "COMMAND"` (`validate_ledger_structural.py:2130-2131`).

**This is the row in the batch where the command obligation is load-bearing, and it is
present.** `PG-05-08` is one of only 25 components — and one of only six phase-gate rows —
in `EXPECTED_COMMAND_PROOF_COMPONENTS` (`:2635-2649`), the closed manifest the validator
asserts for exact set equality at `:2649`. Because `extract_goal_validators.py --check`
exits `0` at these bytes, that manifest is goal text. I verified membership by recomputing
the actual command-proof component set from the ledger, not by reading the constant. The
program-level evidence-inventory review r0 (Critical finding 2) named `PG-05-08` among the
rows whose demonstration obligations lacked command evidence; at these bytes the
obligation exists, and this row carries the `HR-0004` link and `TR-PG-05-08-001` under
which it was added.

**The one thing I checked and did not find missing: the command-proof `scope`.** It reads
"PG-05-08 command proof" — terse next to `PG-2-04`'s, which spells out a twelve-term
conjunction. Goal L270-272 puts an "observable conjunction" into the command-proof scope,
so a terse scope could look like a dropped obligation. It is not: that requirement is
mechanized as a single-row manifest for `PG-2-04` alone (`:2551-2581`), because `PG-2-04`
is the row whose activation predicate was converted into a proof obligation. `PG-05-08`
never had a predicate, so it has no conjunction to carry, and its scope matches the
uniform `"<CID> command proof"` form used by `PG-1-04`, `PG-1-05`, `PG-1-06`, and
`PG-2-03` — all four checked directly this round.

**No typed-approval obligation is missing.** B-14's acceptance ends "partial revalidation
and reapproval succeed", and `REG-B-14` does carry `REQ-REG-B-14-ANALYST_ACCEPTANCE-02`.
But this clause's demand is that the path be *demonstrated*: the reapproval step is
internal to the mechanism being exercised, and the analyst's standing acceptance
obligation is carried by `REG-B-14`, which lists this gate in its `gate_refs`. See the
`APPROVAL` review for this component, where I take the same question head-on.

**State.** Both items `UNRESOLVED`, empty refs. `evidence_refs` is the single source span
re-hashed above. `verification_command.mode == "UNRESOLVED"` with no commands: note the
command *obligation* (`required_evidence`) and the command *declaration*
(`verification_command`) are separate collections, and the goal permits `UNRESOLVED`
during initial ledger construction. Declaring the argv is later, evidenced work — its
absence now is not an obligation omission.

**Residuals.** None. The obligation list is complete against the clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition, and it satisfies no
evidence item. It records only that the component's `required_evidence` obligation list
is complete against its source clause at the input bytes pinned above; every item in it
remains `UNRESOLVED`.
