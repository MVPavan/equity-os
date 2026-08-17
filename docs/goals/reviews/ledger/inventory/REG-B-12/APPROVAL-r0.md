# Inventory review — REG-B-12 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-B-12` |
| `review_type` | `APPROVAL` |
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

`review_inventory_projection(row, "APPROVAL")` — canonical JSON
(`validate_ledger_structural.py:292-318`, extracted by `ast` and executed in an isolated
namespace this round rather than transcribed):

```json
{"approval_records":[],"human_review_id":[],"required_approvals":[{"actor":null,"approval_id":"APR-REG-B-12-01","approval_type":"DELEGATED_ARTIFACT_APPROVAL","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Delegated fresh Sol xhigh specification reviewer","scope":"B-12 under S13: Establish versioned metric and predicate registries","status":"UNRESOLVED","timestamp":null},{"actor":null,"approval_id":"APR-REG-B-12-02","approval_type":"DOMAIN_EXPERT_ACCEPTANCE","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Vocabulary authority","scope":"B-12 under S13: Establish versioned metric and predicate registries","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (the recorder must recompute both after
its Phase A evidence append, per recording design r2 §3.4 — appending review evidence
mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `7316ae869d4fd7e4ba71d48bdea6e75f9d3df0a15793823aad8d1c10b2032cc3`
- `reviewed_inventory_sha256` (pre-record): `5a3851cf3b8425c72c8b17c33f13948a11161834e9df4066bfbcf8a9e45cfcb4`

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

**What authority the clause demands.** One, named in the source
text: among the six registry facilities that must exist is "**addition approval**". A
registry whose additions require approval demands an approving authority, and the
inventory has to say who.

**What is enumerated.** Two requirements. `APR-REG-B-12-01`,
`DELEGATED_ARTIFACT_APPROVAL`, for the S13 specification. And `APR-REG-B-12-02`,
`DOMAIN_EXPERT_ACCEPTANCE`, required authority "**Vocabulary authority**", same scope
string "B-12 under S13: Establish versioned metric and predicate registries", both
`UNRESOLVED`.

**Why "Vocabulary authority" is the right pick, and why that is not a default.** The
closed map at goal L562-575 allows `DOMAIN_EXPERT_ACCEPTANCE` five authority strings:
Calculation-domain authority, Data-domain authority, Entity-data authority,
Equity-research domain expert, and Vocabulary authority. The map is discriminating in
practice, and I checked how the ledger uses it rather than assuming: `B-07` ("Define
minimum deterministic compute") takes **Calculation-domain** authority; `B-03`
("Establish source-of-truth matrix") takes **Data-domain** authority; `C-17` ("Decide
entity/security master authority") takes **Entity-data** authority. The subject of
`B-12`'s approval is metric and predicate vocabulary, so Vocabulary authority is the
competent one, and the closed map forces the exact string once the type is right.

**Why this cannot be folded into the delegated approval.** Goal L970-975 states that
delegation "does not include analyst acceptance, **domain-expert acceptance**, ... Only
the competent real person or external authority may supply those decisions." A row whose
source text says "addition approval" and which carried only `APR-REG-B-12-01` would let
the delegated spec reviewer appear to cover a decision the contract reserves. That is the
omission this review exists to catch, and it is not present here.

**The second candidate, rejected.** "deprecation" and "versioning" also appear in the
clause and are lifecycle acts. They do not generate additional requirements: a deprecation
is a vocabulary decision at the same scope, made by the same authority, and goal L613-614
permits two requirements only "where one real-world decision covers two approval types or
scopes" — that is, where the decisions are genuinely distinct. Splitting one vocabulary
authority's remit into "additions" and "deprecations" would create a requirement no single
real decision could satisfy without inventing a second resolution.

**Why no `PRODUCT_OWNER_DECISION`.** "Establish versioned metric and predicate registries"
is an engineering deliverable inside Phase 0.5, not a product-boundary or
released-contract freeze, and the row's Status cell is `Open`, so neither the plain
"Product owner" pattern (`A-01`, `A-02`, `A-04`, `A-13`, `C-13`, `E-03`) nor the
deferred-scope activation pattern, which attaches only to `Deferred` rows, reaches it.

**Gate and link cross-checks.** `gate_refs` is `["PG-05-06"]`; I read that row and its
`required_approvals` is `[]`, so the gate contributes nothing. `human_review_id` is `null`
and `REG-B-12` occurs zero times in the canonical human-review artifact, so forward and
reverse links agree (goal L189). `approval_records` `[]`; `security_exception_ids` `[]`.

**Residuals.** None. The approval list is complete against the clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition, and grants no
non-delegated authority (goal L615-617). It records only that the component's
`required_approvals` obligation list is complete against its source clause at the input
bytes pinned above; every requirement in it remains `UNRESOLVED`.
