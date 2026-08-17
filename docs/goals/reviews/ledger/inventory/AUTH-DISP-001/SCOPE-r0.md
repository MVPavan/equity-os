# Inventory review — AUTH-DISP-001 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `AUTH-DISP-001` |
| `review_type` | `SCOPE` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `47c148f8-1c4c-4ed7-88b5-49996aea69bf` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-15T12:53:38Z` |

Role binding: `CONTEXT.md` "Agent roles (harness-wide)" L137-139 and L147 bind
`REVIEWER` to Claude Opus 5 at high effort, in an agent and context independent
of any `IMPLEMENTER` that produced the reviewed content. The digest above is the
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

`review_inventory_projection(row, "SCOPE")` — canonical JSON:

```json
{"activation_predicate":null,"disposition_refs":[],"gate_refs":[],"related_register_ids":[],"scope_derivation":{"authority_effect":null,"derived_program_disposition":"REQUIRED_NOW","related_register_ids":[],"rule":"PROGRAM_WIDE_ACTIVE_CONTROL"}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `d4d2d8e94f8f06488a163f43d3f041177b7a644d397732c3cd23bbe5b4e97e34`
- `reviewed_inventory_sha256` (pre-record): `a9dd60c5b7d09531f54342a3bd757624a0d25211784829a28dfcf3f214f76d10`

The `SCOPE` inventory projection is byte-identical across all four
`authority_clause` rows, because every field it covers is fixed by kind. That is
a property of the projection, not of the review: what differs per component, and
what this review actually decided, is whether the *occurrence* justifies that
fixed derivation. Recorded here so a later reader does not mistake a shared
digest for a copied review.

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` line 41, inside
`### Final disposition` (L30) under `## 1. Executive verdict` (L14):

> The **implementation decision register should now be the single operational
> source of truth for gates and open decisions**. The consolidated review should
> remain a frozen architectural reference rather than be repeatedly rewritten
> after every audit.

- `source_hash` `a9021c15…` recomputed over the whole file → matches.
- `text_digest` recomputed over the normalized L41-41 span
  (`\n`-joined, surrounding ASCII whitespace trimmed) →
  `dae9a4412809fe3be5f496a4f1bf1b4b830c262961a48f45de5a26899f1724fa`,
  equal to the stored `text_digest`.
- `required_acceptance_text` equals that normalized span byte for byte.
- Structural validator `expected_authority_clause_lines`
  (`validate_ledger_structural.py:377-406`) pins `AUTH-DISP-001` to exactly this
  path and to `source_start_line == source_end_line == 41`; the row matches.

## Reasoning

**Kind.** The occurrence is the closing authority statement of the report's
executive-verdict disposition, and it allocates operational authority between two
whole documents. It is not one of the report's 32 numbered findings
(`G-1`…`G-5`, `M-1`…`M-9`, `T-1`…`T-4`, `R-1`…`R-5`, `6.1`…`6.9`), each of which
is separately inventoried as a `DISP-*` `disposition_item` carrying its own
ordinal in `disposition_refs`; line 41 carries no ordinal and disposes of no
individual review finding. `disposition_item` (rule `AUTHORITATIVE_OCCURRENCE`,
`authority_effect` in {`ACTIVE_CONTROL`, `REJECTED_PROPOSAL`,
`FOLLOW_RELATED_SCOPE`}) would therefore be wrong. `authority_clause` with
`source_title` "Disposition authority rule" is the correct kind.

**Derivation rule.** For `authority_clause` the rule is not a free choice: goal
L243 fixes `authority_clause` → `PROGRAM_WIDE_ACTIVE_CONTROL`, mechanized at
`validate_ledger_structural.py:1511` (`required_rule_by_kind`), and `:1547-1549`
then forces `related_register_ids == []`, `authority_effect is None`, and
`derived == "REQUIRED_NOW"`. Goal L247-248 states the same rule in prose. The
stored `derived_program_disposition` is `REQUIRED_NOW` and `program_disposition`
agrees. The real question the rule leaves open is whether the clause genuinely is
a program-wide active control rather than register-scoped: it is — it names no
register row and governs which document holds gate authority for the whole
program.

**Related register IDs.** `[]` is both contractually forced and semantically
right: the clause refers to the register as a document, not to any of the 60
register decisions. There is no register ID it could name without narrowing an
explicitly program-wide statement.

**Source anchor.** `AUTHORITY-RULE-001` is a clause ordinal. Goal L182 requires
the anchor to be unique *within that path*; verified across all 213 rows: the
disposition-report path has zero duplicate `source_anchor` values and zero
duplicate `(source_start_line, source_end_line)` spans. The literal is shared
with `AUTH-REG-001`, but that row lives in the register path, so the
within-path uniqueness rule is not touched.

**Disposition and gate refs.** `disposition_refs == []` and `gate_refs == []`.
`gate_refs` is populated only on register rows — 39 of 60 — and is pinned by the
`gate_map` equality at `validate_ledger_structural.py:2660-2664`; no rule
populates it for any non-register kind, and all 109 non-register canonical rows
carry `[]`. `disposition_refs` is populated on exactly three closed populations:
56 register rows via the curated crosswalk, the 32 `DISP-*` self-identifications,
and the 8 `SCALE-*` rows pinned at `:2652-2653`. All 73 remaining canonical rows
carry `[]`, including every `authority_clause`, `document_strategy_clause`,
`phase_gate_clause`, `sequence_clause`, and `first_release_deferral`. `[]` here
is the contract's uniform treatment of program-wide controls, whose scope is
supplied by the derivation rule rather than by ref arrays.

**Activation predicate.** `null`, required: goal L288-290 states that a component
whose derived disposition is `REQUIRED_NOW` has `activation_predicate=null`.

**Applicable review slot.** `AUTH-DISP-001` is a non-register canonical row, so
`validate_ledger_preimplementation.py:200-204` appends `SCOPE` to its checks, and
`scope_derivation.semantic_review` is the slot this review fills. It is present,
non-`null`, `PENDING`, and carries exactly the 10-key `PENDING` set with no
role-binding keys. Contrast the 60 `register_row` rows, where the contract fixes
`semantic_review = null` (goal L208-211) and no `SCOPE` review exists.

**Double-inventory check.** `DISP-T-3` (disposition report L293, "Gate wording
lives in multiple places") also asserts that the register owns live gate wording.
It is a distinct occurrence at a distinct span, inventoried as its own
`disposition_item` with `disposition_refs == ["T-3"]`. Since the contract
inventories exact occurrences, two rows for two occurrences is correct, not a
duplicate.

**Residuals.** None. Every field in the reviewed inventory was checked against
either a mechanized rule or the live source occurrence.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `AUTH-DISP-001`'s scope derivation is correct at the input bytes
pinned above.
