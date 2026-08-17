# Inventory review — PG-0A-02 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `PG-0A-02` |
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
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"b13b104b6d04b56a955bf4eb3b8daa6855f571d7e255ed44b4e6ac2ebbe14fb1","digest_mode":"UTF8_LINE_SPAN","end_line":127,"evidence_ref_id":"EV-PG-0A-02-SOURCE","path":"docs/blueprint/funda-blueprint-implementation-decision-register-v2.md","scope":"Exact authoritative source occurrence for PG-0A-02","start_line":127}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: source rights are scoped to that boundary","evidence_id":"REQ-PG-0A-02-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"PG-0A-02 acceptance and delivery scope","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (the recorder must recompute both after
its Phase A evidence append, per recording design r2 §3.4 — appending review evidence
mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `6bfc6737876df8fe546952ac5774bade7071a260f656987e2f95dc8537ec2d3d`
- `reviewed_inventory_sha256` (pre-record): `23d3777e3f0f2e99addc4f83b2161f85ef69c86b4770183d9eac5cb90b9241f7`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line 127,
anchor `F-0A-02`, the 2nd bullet under the
`### Phase 0A may exit only when` heading at line 124, inside
`## F. Phase-gate scorecard` (line 122):

> - source rights are scoped to that boundary;

- `source_hash` recomputed over the whole register file →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L127 span (CRLF→LF, surrounding ASCII
  whitespace trimmed) → `b13b104b6d04b56a955bf4eb3b8daa6855f571d7e255ed44b4e6ac2ebbe14fb1`, matching the row.
- `required_acceptance_text` is that span with the `- ` list marker and the trailing
  `;` removed — compared programmatically, not by eye.
- `EV-PG-0A-02-SOURCE` is a `UTF8_LINE_SPAN` reference over exactly that one line
  (`start_line == end_line == 127`); its `content_sha256` recomputes to the same digest,
  so the row's only evidence object resolves against current bytes.

## Reasoning

**What the clause demands.** "source rights are scoped to that boundary" demands a
consistency relation between two artifacts: the provider and data-rights register (A-05)
and the declared product boundary (A-01, via the preceding clause `PG-0A-01`). Proof is
that the rights register exists and its declared scope matches the boundary.

**What is enumerated.** One obligation, `REQ-PG-0A-02-ACCEPTANCE` — `ARTIFACT` /
`CONTENT_HASH`, scope "PG-0A-02 acceptance and delivery scope", description byte-equal to
`"Current proof satisfying: " + required_acceptance_text` (checked programmatically), so
"scoped to that boundary" — the relational half, and the substantive one — is carried into
the obligation rather than reduced to "a rights register exists".

**Why one content-hashed artifact obligation covers a two-artifact relation.** The
relation is checkable by reading both documents; it is not a second act by a second party
and so does not need a second typed obligation. The evidence offered against this
obligation must establish the scoping, not merely the register's existence, because the
clause text is carried verbatim.

**What I checked for and did not find missing.** A-05's acceptance enumerates eleven
attributes the rights register must record per source — "access method, automation,
caching, retention, commercial use, derived outputs, redistribution, account limits,
point-in-time availability, and replacement path". None of that is imported here, and none
should be: those are `REG-A-05`'s obligations under `REQ-REG-A-05-ACCEPTANCE`, and
`REG-A-05` lists this gate in `gate_refs`. Likewise the substantive rights determination is
`REQ-REG-A-05-DATA_RIGHTS_APPROVAL` (`DATA_RIGHTS` / `TYPED_APPROVAL`) — see the `APPROVAL`
review for this component, where I address whether it should be duplicated here.

**No command obligation is missing.** No test, replay, or demonstration language;
`PG-0A-02` is absent from the goal-owned `EXPECTED_COMMAND_PROOF_COMPONENTS` manifest
asserted for exact set equality at `:2649`, and so is `REG-A-05`.

**State.** `UNRESOLVED`, empty refs. `evidence_refs` is the single source span re-hashed
above; `verification_command` is `UNRESOLVED`.

**Residuals.** None. The obligation list is complete against the clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition, and it satisfies no
evidence item. It records only that the component's `required_evidence` obligation list
is complete against its source clause at the input bytes pinned above; every item in it
remains `UNRESOLVED`.
