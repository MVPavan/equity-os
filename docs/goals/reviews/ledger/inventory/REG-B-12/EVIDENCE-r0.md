# Inventory review — REG-B-12 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-B-12` |
| `review_type` | `EVIDENCE` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `4fc94e50-8bc8-416d-b8e5-e7ce4ad128d0` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-16T13:54:44Z` |

Role binding: `CONTEXT.md` "Agent roles (harness-wide)" L137-139 binds `REVIEWER` to
Claude Opus 5 at high effort, in an agent and context independent of any `IMPLEMENTER`
that produced the reviewed content. The digest above is the `CONTEXT.md` bytes at review
time and is an immutable historical capture, never re-verified against later bytes
(`validate_ledger_structural.py:250-262`).

## Review types applicable to this component

`REG-B-12` has `kind == "register_row"`. Its `scope_derivation.semantic_review` is `null`,
which I verified on the row itself before writing: the contract fixes that null for a
register row (goal L208-211, mechanized at goal L2886
`assert derivation["semantic_review"] is None`), because a register row's scope comes from
the pinned v2 register itself. `validate_ledger_preimplementation.py:200-204` builds the
applicable check set as `APPROVAL` + `EVIDENCE` always and appends `SCOPE` only
`if row["kind"] != "register_row"`. This component therefore has exactly **two**
applicable reviews — `EVIDENCE` and `APPROVAL` — and no `SCOPE` artifact exists or should
exist for it.

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
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"5d0deaff492ac62ce1af17c6b7a698e3ab4953367b4ccb0bd1ea7d9bd263f84e","digest_mode":"UTF8_LINE_SPAN","end_line":62,"evidence_ref_id":"EV-REG-B-12-SOURCE","path":"docs/blueprint/funda-blueprint-implementation-decision-register-v2.md","scope":"Exact authoritative source occurrence for REG-B-12","start_line":62},{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"f1a60a20e24a0d2a457aa71f8d9006316ea461d237ea1faa054fc24176ba3dc4","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-REG-B-12-SPEC-DRAFT","path":"docs/specs/equity-os-s13-claim-schema-vocabulary-evidence.md","scope":"Current draft specification bytes for REG-B-12","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: Registry definitions, aliases, object/unit/dimension rules, addition approval, deprecation, and versioning exist; every structured fact/claim resolves to a registered entry; embedding-assisted dedup is optional","evidence_id":"REQ-REG-B-12-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"REG-B-12 acceptance and delivery scope","status":"UNRESOLVED"},{"approval_ids":[],"description":"Persisted clean fresh Sol xhigh review of the current specification bytes","evidence_id":"REQ-REG-B-12-SPEC-REVIEW","evidence_ref_ids":[],"evidence_type":"REVIEW","proof_mode":"CONTENT_HASH","scope":"B-12 under S13: Establish versioned metric and predicate registries","status":"UNRESOLVED"},{"approval_ids":["APR-REG-B-12-02"],"description":"Current DOMAIN_EXPERT_ACCEPTANCE evidence from Vocabulary authority","evidence_id":"REQ-REG-B-12-DOMAIN_EXPERT_ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"DOMAIN","proof_mode":"TYPED_APPROVAL","scope":"B-12 under S13: Establish versioned metric and predicate registries","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (the recorder must recompute both after
its Phase A evidence append, per recording design r2 §3.4 — appending review evidence
mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `7316ae869d4fd7e4ba71d48bdea6e75f9d3df0a15793823aad8d1c10b2032cc3`
- `reviewed_inventory_sha256` (pre-record): `ac65e65cfb12bccc8ef10c0e4be33995b33b9bcb9f6d0662acdf7a4e29a70270`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line 62, anchor
`B-12`, a row of the decision table whose header is at line 49,
inside `## B. Phase 0.5 — One company, four quarters: one baseline plus three assisted updates` (line 47):

> | B-12 | Critical | Establish versioned metric and predicate registries | Registry definitions, aliases, object/unit/dimension rules, addition approval, deprecation, and versioning exist; every structured fact/claim resolves to a registered entry; embedding-assisted dedup is optional | A-04, A-06 | Open |

- `source_hash` recomputed over the whole register file →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L62 span (CRLF→LF, surrounding ASCII
  whitespace trimmed) → `5d0deaff492ac62ce1af17c6b7a698e3ab4953367b4ccb0bd1ea7d9bd263f84e`, matching the row.
- `required_acceptance_text` is the 4th table cell ("Required evidence / acceptance") of
  that line; I compared it programmatically against the row's stored value, not by eye.
- The `Status` cell reads `Open`, matching the row's `source_status` and
  `activation_source_status`; `program_disposition` is `REQUIRED_NOW`.
- `EV-REG-B-12-SOURCE` is a `UTF8_LINE_SPAN` reference over exactly that one line
  (`start_line == end_line == 62`) and its `content_sha256` recomputes to the same
  digest; `EV-REG-B-12-SPEC-DRAFT` is a `FILE_BYTES` reference whose digest I recomputed
  against the current spec file. Both of the row's evidence objects resolve against
  current bytes.

## Reasoning

**What the clause demands.** Three conjuncts of three different
characters. (a) Six registry facilities "**exist**" — definitions, aliases,
object/unit/dimension rules, **addition approval**, deprecation, versioning. (b) "every
structured fact/claim **resolves** to a registered entry" — a universally quantified
property of live data. (c) "embedding-assisted dedup **is optional**" — an explicit
non-obligation.

**What is enumerated.** Three obligations: `REQ-REG-B-12-ACCEPTANCE`
(`ARTIFACT`/`CONTENT_HASH`), verified byte-equal to the prefixed `required_acceptance_text`
so all three conjuncts survive; `REQ-REG-B-12-SPEC-REVIEW` (`REVIEW`/`CONTENT_HASH`); and
`REQ-REG-B-12-DOMAIN_EXPERT_ACCEPTANCE` — `DOMAIN` / `TYPED_APPROVAL`, "Current
DOMAIN_EXPERT_ACCEPTANCE evidence from Vocabulary authority", carrying
`approval_ids: ["APR-REG-B-12-02"]`.

**Conjunct (a): "addition approval" is correctly given a typed item.** A registry whose
additions require approval demands proof of the approving authority, and goal L487-490
requires domain evidence to use `TYPED_APPROVAL` and the typed approval/human-review
path rather than a shell command. The item is present, correctly typed, and links its
component-local approval requirement in `approval_ids` per goal L485-486.

**Conjunct (b) is the item I checked hardest, and it is a proof-mode question, not a
missing obligation.** "every structured fact/claim resolves to a registered entry" reads
like a mechanically checkable universal, and a reasonable reviewer could argue for a
`COMMAND_RESULT` item. `REG-B-12` is absent from `EXPECTED_COMMAND_PROOF_COMPONENTS`
(`validate_ledger_structural.py:2635-2649`), but I did not simply defer to that manifest,
because deferring to it would make this review a restatement of the contract rather than a
check on it. I applied an independent test over the register: every one of the ten
register rows in that manifest contains explicit test, replay, or execution language —
"tested" (`B-01`, `B-11`, `C-17`, `E-10`), "tests insert and reject" (`C-15`), "test cases
approved" (`A-10`), "pass tests" (`C-08`), "replay exactly" / "reconstructs exactly"
(`C-16`), "reproducible" (`E-01`), "succeed" (`B-14`).
`B-12`'s verbs are "exist", "resolves", "is optional", which is the same state-descriptive
class as `C-06` ("are versioned events"), `C-07` and `B-06` ("are represented"), and
`C-09` ("are registered") — none of which carries a command item. The independent test and
the contract manifest agree. I record this explicitly because it is the closest call in
this batch: the conjunct *is* enumerated, verbatim, inside
`REQ-REG-B-12-ACCEPTANCE`; what is at issue is only which mode of proof will discharge it,
and both the source wording and the contract classify it as content.

**Conjunct (c) is correctly not converted into an obligation.** "embedding-assisted dedup
is optional" demands no proof, and the mirror carries the word "optional" rather than
silently promoting the clause to a requirement. Manufacturing an obligation from an
explicitly optional term would be an invented obligation, which is the mirror-image error
of a dropped one and equally a completeness defect.

**On the disposition references.** `disposition_refs` is `["G-5", "M-3", "6.2"]`. `M-3`
does say the first version needs "a human approval rule for additions" — which L62 already
carries as "addition approval" — while `G-5` and `6.2` concern materiality and bear on
`A-10`/`C-04`, not on registry evidence. Under the register's Authority rule (register
L23) none of the three can add a gate obligation beyond L62's wording, and none needs to.

**State.** Three items `UNRESOLVED`, empty refs; `verification_command` `UNRESOLVED`.
`human_review_id` is `null` and `REG-B-12` occurs zero times in the canonical
human-review artifact — links agree in both directions. The L62 span and S13 draft bytes
both re-hash to their recorded digests.

**Residuals.** None. The obligation list is complete against the clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition, and it satisfies no
evidence item. It records only that the component's `required_evidence` obligation list is
complete against its source clause at the input bytes pinned above; every item in it
remains `UNRESOLVED`.
